import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_

from loguru import logger
import pandas as pd
import numpy as np

from app.db import crud, models
from app.utils.helpers import get_date_range, format_currency, format_percentage
from app.core.shopify_client import ShopifyClient


async def get_sales_data(
    db: AsyncSession,
    store_id: str,
    time_range: str = "today",
    timezone: str = "UTC",
    include_geo_data: bool = False,
    include_conversion_rate: bool = False,
    specific_start_date: Optional[datetime] = None,
    specific_end_date: Optional[datetime] = None,
    top_products_limit: int = 10,  # Changed default to 10
    bottom_products_limit: int = 10,  # Added parameter with default of 10
) -> Dict[str, Any]:
    """
    Get sales data for a specific time range.

    Args:
        db: Database session
        store_id: Store ID
        time_range: Time range (today, yesterday, last_7_days, last_30_days, custom)
        timezone: User's timezone
        include_geo_data: Whether to include geographic data
        include_conversion_rate: Whether to include conversion rate data
        specific_start_date: Custom start date (for custom time range)
        specific_end_date: Custom end date (for custom time range)
        top_products_limit: Maximum number of top products to return
        bottom_products_limit: Maximum number of bottom products to return

    Returns:
        dict: Sales data
    """
    # Get date range based on time_range or specific dates
    if time_range == "custom" and specific_start_date and specific_end_date:
        start_date = specific_start_date
        end_date = specific_end_date
    else:
        start_date, end_date = get_date_range(time_range, timezone)

    # Convert to timezone-naive datetimes (to match the stored order_date)
    if start_date.tzinfo:
        start_date = start_date.replace(tzinfo=None)
    if end_date.tzinfo:
        end_date = end_date.replace(tzinfo=None)

    # Use selectinload to eager load order_items instead of lazy loading
    stmt = select(models.Order).where(
        and_(
            models.Order.store_id == store_id,
            models.Order.order_date >= start_date,
            models.Order.order_date <= end_date
        )
    ).options(selectinload(models.Order.order_items))

    result = await db.execute(stmt)
    orders = result.scalars().all()

    # Get orders for the previous period for comparison
    duration = (end_date - start_date).days + 1
    prev_start_date = start_date - timedelta(days=duration)
    prev_end_date = end_date - timedelta(days=duration)

    prev_stmt = select(models.Order).where(
        and_(
            models.Order.store_id == store_id,
            models.Order.order_date >= prev_start_date,
            models.Order.order_date <= prev_end_date
        )
    ).options(selectinload(models.Order.order_items))

    prev_result = await db.execute(prev_stmt)
    prev_orders = prev_result.scalars().all()

    # Calculate summary metrics
    total_sales = sum(order.total_price for order in orders)
    total_orders = len(orders)
    average_order_value = total_sales / total_orders if total_orders > 0 else 0

    prev_total_sales = sum(order.total_price for order in prev_orders)
    prev_total_orders = len(prev_orders)
    prev_average_order_value = prev_total_sales / prev_total_orders if prev_total_orders > 0 else 0

    # Calculate changes
    sales_change = (total_sales - prev_total_sales) / prev_total_sales if prev_total_sales > 0 else 0
    orders_change = (total_orders - prev_total_orders) / prev_total_orders if prev_total_orders > 0 else 0
    aov_change = (average_order_value - prev_average_order_value) / prev_average_order_value if prev_average_order_value > 0 else 0

    # Get top products and calculate growth rates
    product_sales = {}
    prev_product_sales = {}

    # Current period product sales
    for order in orders:
        for item in order.order_items:
            product_id = str(item.product_id) if item.product_id else f"unknown_{item.platform_product_id}"
            if product_id not in product_sales:
                product_sales[product_id] = {
                    "name": item.product_name,
                    "revenue": 0,
                    "quantity": 0
                }
            # Calculate correctly - item.price * item.quantity
            product_sales[product_id]["revenue"] += item.price * item.quantity
            product_sales[product_id]["quantity"] += item.quantity

    # Debug logging - verify product sales aren't exceeding total sales
    total_product_revenue = sum(p["revenue"] for p in product_sales.values())
    logger.info(f"Total sales: {total_sales}, Total product revenue: {total_product_revenue}")
    if total_product_revenue > total_sales * 1.1:  # Allow 10% margin for rounding
        logger.warning(f"Product revenue ({total_product_revenue}) significantly exceeds total sales ({total_sales})!")
        # Cap product revenue to match total sales
        if total_product_revenue > 0:
            scale_factor = total_sales / total_product_revenue
            for product_id in product_sales:
                product_sales[product_id]["revenue"] *= scale_factor
            logger.info(f"Scaled product revenues by factor {scale_factor}")

    # Previous period product sales for growth calculation
    for order in prev_orders:
        for item in order.order_items:
            product_id = str(item.product_id) if item.product_id else f"unknown_{item.platform_product_id}"
            if product_id not in prev_product_sales:
                prev_product_sales[product_id] = {
                    "revenue": 0,
                    "quantity": 0
                }
            prev_product_sales[product_id]["revenue"] += item.price * item.quantity
            prev_product_sales[product_id]["quantity"] += item.quantity

    # Calculate growth rates for products
    for product_id, product in product_sales.items():
        prev_revenue = prev_product_sales.get(product_id, {}).get("revenue", 0)
        if prev_revenue > 0:
            product["growth_rate"] = (product["revenue"] - prev_revenue) / prev_revenue
        else:
            product["growth_rate"] = 1.0  # 100% growth for new products

    # Sort products by revenue
    sorted_by_revenue = sorted(
        product_sales.values(),
        key=lambda x: x["revenue"],
        reverse=True
    )

    # Sort products by growth rate
    sorted_by_growth = sorted(
        product_sales.values(),
        key=lambda x: x.get("growth_rate", 0),
        reverse=True
    )

    # Get top/bottom products by revenue
    top_products = sorted_by_revenue[:top_products_limit] if sorted_by_revenue else []
    
    # Handle bottom products - make sure we have enough products
    if len(sorted_by_revenue) >= bottom_products_limit:
        bottom_products = sorted_by_revenue[-bottom_products_limit:]
        bottom_products.reverse()  # Reverse to show worst performer first
    else:
        bottom_products = sorted_by_revenue.copy()  # Copy all if fewer than limit
        bottom_products.reverse()   # Reverse to show worst performer first

    # Get growing and declining products by growth rate
    growing_products = [p for p in sorted_by_growth if p.get("growth_rate", 0) > 0][:top_products_limit]
    
    # Get declining products (negative growth rate)
    declining_candidates = [p for p in sorted_by_growth if p.get("growth_rate", 0) < 0]
    
    if declining_candidates:
        # Take the most declining products first (sort ascending by growth rate)
        declining_products = sorted(declining_candidates, key=lambda x: x.get("growth_rate", 0))[:bottom_products_limit]
    else:
        declining_products = []  # No declining products

    # Log the top products for debugging
    logger.info(f"Number of top products identified: {len(top_products)}")
    for i, product in enumerate(top_products[:5], 1):
        logger.info(f"Top product {i}: {product.get('name', 'Unknown')} - Revenue: {product.get('revenue', 0):.2f}")

    # Also log declining products if available
    if declining_products:
        logger.info(f"Number of declining products identified: {len(declining_products)}")
        for i, product in enumerate(declining_products[:3], 1):
            logger.info(f"Declining product {i}: {product.get('name', 'Unknown')} - Growth Rate: {product.get('growth_rate', 0):.2f}")

    # Fetch geo data if requested
    geo_data = []
    if include_geo_data:
        try:
            logger.info(f"Attempting to extract geographic data from {len(orders)} orders")
            # Extract directly from orders first
            geo_data = extract_geo_data_from_orders(orders)
            logger.info(f"Extracted geo data from orders: {len(geo_data)} countries")
            
            # Only if extraction produced no results, try Shopify API
            if not geo_data:
                try:
                    # Get the store to initialize ShopifyClient
                    store_result = await db.execute(select(models.Store).where(models.Store.id == store_id))
                    store = store_result.scalars().first()
                    
                    if store:
                        client = ShopifyClient(store)
                        shop_geo_data = await client.get_geolocation_data(start_date, end_date)
                        if shop_geo_data and len(shop_geo_data) > 0:
                            geo_data = shop_geo_data
                            logger.info(f"ShopifyClient geo data obtained: {len(geo_data)} countries")
                except Exception as shopify_error:
                    logger.error(f"Error from ShopifyClient.get_geolocation_data: {shopify_error}")
        except Exception as e:
            logger.error(f"Error in main geo data block: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # Fetch conversion rate data if requested
    conversion_data = {}
    if include_conversion_rate:
        try:
            # Get the store to initialize ShopifyClient
            if not store:  # Only fetch if we didn't already
                store_result = await db.execute(select(models.Store).where(models.Store.id == store_id))
                store = store_result.scalars().first()

            if store:
                client = ShopifyClient(store)
                analytics = await client.get_analytics_report("conversion_rate", start_date, end_date)

                if "shopifyAnalytics" in analytics:
                    shop_analytics = analytics["shopifyAnalytics"]
                    conversion_data = {
                        "sessions": shop_analytics.get("onlineStoreSessions", 0),
                        "conversion_rate": shop_analytics.get("onlineStoreConversionRate", 0),
                        "orders": shop_analytics.get("totalOrders", 0)
                    }
        except Exception as e:
            logger.error(f"Error fetching conversion data: {e}")

    # Format the response
    return {
        "time_period": {
            "range_type": time_range,
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "average_order_value": average_order_value,
        },
        "comparison": {
            "sales_change": sales_change,
            "orders_change": orders_change,
            "aov_change": aov_change,
            "previous_sales": prev_total_sales,
            "previous_orders": prev_total_orders,
            "previous_aov": prev_average_order_value,
        },
        "top_products_count": top_products_limit,  # Include the requested count
        "bottom_products_count": bottom_products_limit,  # Include the requested count
        "top_products": top_products,
        "bottom_products": bottom_products,
        "growing_products": growing_products,
        "declining_products": declining_products,
        "geo_data": geo_data,
        "conversion": conversion_data,
        "anomalies": [],  # This would be populated by the anomaly detection service
    }
def extract_geo_data_from_orders(orders):
    """
    Extract geographic data directly from order data.
    This is a fallback method when the Shopify API geo data fetch fails.

    Args:
        orders: List of order objects

    Returns:
        list: Processed geographic data
    """
    geo_data = {}
    address_count = 0
    total_orders = len(orders)
    
    logger.info(f"Extracting geo data from {total_orders} orders")
    
    # First, log some debug info about the order structure
    if orders:
        try:
            sample_order = orders[0]
            logger.info(f"Sample order type: {type(sample_order).__name__}")
            logger.info(f"Sample order attributes: {dir(sample_order)[:20]}")
            
            # Check if order_data exists and is accessible
            has_order_data = hasattr(sample_order, 'order_data')
            logger.info(f"Sample order has order_data attribute: {has_order_data}")
            
            if has_order_data:
                # Check the type of order_data
                order_data_type = type(sample_order.order_data).__name__
                logger.info(f"order_data type: {order_data_type}")
                
                # If order_data is a string, try to parse it
                if order_data_type == 'str':
                    try:
                        import json
                        sample_data = json.loads(sample_order.order_data)
                        logger.info(f"Parsed order_data from string, keys: {list(sample_data.keys())}")
                    except:
                        logger.error("Failed to parse order_data string as JSON")
                else:
                    # Assume it's a dict or similar
                    try:
                        sample_data = sample_order.order_data
                        if hasattr(sample_data, 'keys'):
                            logger.info(f"order_data keys: {list(sample_data.keys())[:10]}")
                    except:
                        logger.error("Error accessing order_data keys")
        except Exception as e:
            logger.error(f"Error inspecting sample order: {e}")

    # Enhanced address extraction and processing
    for order in orders:
        try:
            # Handle different order data formats
            order_data = None
            
            # Check if order_data exists as an attribute
            if hasattr(order, 'order_data'):
                order_data = order.order_data
                
                # If order_data is a string, try to parse it as JSON
                if isinstance(order_data, str):
                    try:
                        import json
                        order_data = json.loads(order_data)
                    except:
                        logger.warning(f"Failed to parse order_data string for order {getattr(order, 'id', 'unknown')}")
            
            # If we still don't have order_data, try the raw attribute
            if not order_data and hasattr(order, 'raw'):
                order_data = order.raw
            
            # If we have no order data at all, skip this order
            if not order_data:
                continue
            
            # Try to get shipping address - look in multiple possible locations
            shipping_address = None
            
            # Check Shopify structure
            if isinstance(order_data, dict):
                # 1. Direct shipping_address
                if 'shipping_address' in order_data:
                    shipping_address = order_data['shipping_address']
                
                # 2. Check in shipping object
                elif 'shipping' in order_data and isinstance(order_data['shipping'], dict):
                    shipping_address = order_data['shipping'].get('address')
                
                # 3. Check in customer's default address
                elif 'customer' in order_data and isinstance(order_data['customer'], dict):
                    if 'default_address' in order_data['customer']:
                        shipping_address = order_data['customer']['default_address']
                    # Look in addresses array
                    elif 'addresses' in order_data['customer'] and isinstance(order_data['customer']['addresses'], list) and order_data['customer']['addresses']:
                        shipping_address = order_data['customer']['addresses'][0]
                
                # 4. Try billing address as last resort
                elif 'billing_address' in order_data:
                    shipping_address = order_data['billing_address']
            
            # If we couldn't find an address, skip this order
            if not shipping_address:
                continue
            
            address_count += 1
            
            # Extract and normalize location data with better handling for sub-regions
            country = shipping_address.get('country', 'Unknown')
            province = shipping_address.get('province', '')
            city = shipping_address.get('city', '')
            
            # Additional location data that might be available
            district = shipping_address.get('district', '')
            barangay = shipping_address.get('barangay', '')  # For Philippines
            suburb = shipping_address.get('suburb', '')
            # Extract district/area from address lines if not found directly
            address1 = shipping_address.get('address1', '')
            address2 = shipping_address.get('address2', '')
            
            # Further subdivision for Philippines specifically
            if country == "Philippines" and not province:
                # Try to extract province from the address
                province_keywords = ["province", "provinces"]
                for address_part in [address1, address2]:
                    if address_part:
                        # Look for phrases like "Manila province" or "province of Manila"
                        for keyword in province_keywords:
                            if keyword in address_part.lower():
                                parts = address_part.lower().split(keyword)
                                if len(parts) > 1:
                                    possible_province = parts[0].strip() if keyword == "province" else parts[1].strip()
                                    if possible_province:
                                        province = possible_province.title()
                                        break
            
            # Try to extract city/municipality from address if not found
            if country == "Philippines" and not city and (address1 or address2):
                city_keywords = ["city", "municipality", "town"]
                for address_part in [address1, address2]:
                    if address_part:
                        for keyword in city_keywords:
                            if keyword in address_part.lower():
                                parts = address_part.lower().split(keyword)
                                if len(parts) > 1:
                                    possible_city = parts[0].strip() if keyword == "city" else parts[1].strip()
                                    if possible_city:
                                        city = possible_city.title()
                                        break
            
            # If we have a barangay but no district, use barangay as district
            if country == "Philippines" and barangay and not district:
                district = barangay
            
            # Handle empty values
            if not country or country.strip() == '':
                country = 'Unknown'
            if not province or province.strip() == '':
                province = 'Unknown Region'
            if not city or city.strip() == '':
                city = 'Unknown City'
            if not district or district.strip() == '':
                district = 'Unknown District'
            
            # If city is just the province name repeated, clear it to avoid duplication
            if city.lower() == province.lower():
                city = 'Unknown City'
            
            # Initialize country data if not exists
            if country not in geo_data:
                geo_data[country] = {
                    'total_orders': 0,
                    'total_sales': 0,
                    'regions': {}
                }
            
            # Update country stats
            geo_data[country]['total_orders'] += 1
            geo_data[country]['total_sales'] += order.total_price
            
            # Initialize region data if not exists
            if province not in geo_data[country]['regions']:
                geo_data[country]['regions'][province] = {
                    'total_orders': 0,
                    'total_sales': 0,
                    'cities': {}
                }
            
            # Update region stats
            geo_data[country]['regions'][province]['total_orders'] += 1
            geo_data[country]['regions'][province]['total_sales'] += order.total_price
            
            # Initialize city data if not exists
            if city not in geo_data[country]['regions'][province]['cities']:
                geo_data[country]['regions'][province]['cities'][city] = {
                    'total_orders': 0,
                    'total_sales': 0,
                    'districts': {}
                }
            
            # Update city stats
            geo_data[country]['regions'][province]['cities'][city]['total_orders'] += 1
            geo_data[country]['regions'][province]['cities'][city]['total_sales'] += order.total_price
            
            # Add district level if we have it (for more detailed breakdowns)
# Add district level if we have it (for more detailed breakdowns)
            if district != 'Unknown District':
                if 'districts' not in geo_data[country]['regions'][province]['cities'][city]:
                    geo_data[country]['regions'][province]['cities'][city]['districts'] = {}
                    
                if district not in geo_data[country]['regions'][province]['cities'][city]['districts']:
                    geo_data[country]['regions'][province]['cities'][city]['districts'][district] = {
                        'total_orders': 0,
                        'total_sales': 0
                    }
                    
                geo_data[country]['regions'][province]['cities'][city]['districts'][district]['total_orders'] += 1
                geo_data[country]['regions'][province]['cities'][city]['districts'][district]['total_sales'] += order.total_price
            
        except Exception as e:
            logger.error(f"Error processing order for geo data: {e}")
    
    logger.info(f"Found addresses in {address_count} out of {total_orders} orders")
    
    # Convert geo_data dict to list format with enhanced structure
    result = []
    for country, country_data in geo_data.items():
        # Convert regions dict to list
        regions_list = []
        for region_name, region_data in country_data['regions'].items():
            # Convert cities dict to list
            cities_list = []
            for city_name, city_data in region_data['cities'].items():
                # Convert districts dict to list if they exist
                districts_list = []
                if 'districts' in city_data:
                    for district_name, district_data in city_data['districts'].items():
                        districts_list.append({
                            'name': district_name,
                            'total_orders': district_data['total_orders'],
                            'total_sales': district_data['total_sales']
                        })
                    
                    # Sort districts by total sales
                    districts_list.sort(key=lambda x: x['total_sales'], reverse=True)
                
                city_info = {
                    'name': city_name,
                    'total_orders': city_data['total_orders'],
                    'total_sales': city_data['total_sales']
                }
                
                # Only add districts if we have them
                if districts_list:
                    city_info['districts'] = districts_list
                
                cities_list.append(city_info)
            
            # Sort cities by total sales
            cities_list.sort(key=lambda x: x['total_sales'], reverse=True)
            
            regions_list.append({
                'name': region_name,
                'total_orders': region_data['total_orders'],
                'total_sales': region_data['total_sales'],
                'cities': cities_list
            })
        
        # Sort regions by total sales
        regions_list.sort(key=lambda x: x['total_sales'], reverse=True)
        
        country_info = {
            'country': country,
            'total_orders': country_data['total_orders'],
            'total_sales': country_data['total_sales'],
            'regions': regions_list
        }
        result.append(country_info)
    
    # Sort countries by total sales
    result.sort(key=lambda x: x['total_sales'], reverse=True)
    
    # Log the results for debugging
    logger.info(f"Extracted geo data: {len(result)} countries with data")
    if result:
        for country in result[:3]:  # Log top 3 countries
            logger.info(f"Country: {country['country']}, Sales: {country['total_sales']:.2f}, Orders: {country['total_orders']}")
            for region in country['regions'][:3]:  # Log top 3 regions per country
                logger.info(f"  Region: {region['name']}, Sales: {region['total_sales']:.2f}, Orders: {region['total_orders']}")
                for city in region['cities'][:3]:  # Log top 3 cities per region
                    logger.info(f"    City: {city['name']}, Sales: {city['total_sales']:.2f}, Orders: {city['total_orders']}")
    
    return result
async def update_shopify_orders(db: AsyncSession, store: models.Store, since_date: Optional[datetime] = None):
    """
    Update orders from Shopify.

    Args:
        db: Database session
        store: Store model
        since_date: Only get orders since this date
    """
    # Initialize Shopify client
    client = ShopifyClient(store)

    try:
        # Get orders from Shopify
        orders = await client.get_orders(
            created_at_min=since_date,
            status="any",
            limit=250  # Max allowed by Shopify
        )

        # Process each order
        for order_data in orders:
            # Check if we already have this order
            existing_order = await crud.get_order_by_platform_id(
                db, str(store.id), str(order_data["id"])
            )

            if not existing_order:
                # Create new order
                # Convert timezone-aware datetime to timezone-naive by replacing tzinfo
                order_date = None
                if "created_at" in order_data:
                    # Handle different datetime formats
                    try:
                        if order_data["created_at"].endswith('Z'):
                            # ISO format with Z suffix
                            order_date = datetime.fromisoformat(order_data["created_at"].replace("Z", "+00:00"))
                        else:
                            # Try standard ISO format
                            order_date = datetime.fromisoformat(order_data["created_at"])
                    except ValueError:
                        # Fallback to basic parsing if isoformat fails
                        from dateutil import parser
                        order_date = parser.parse(order_data["created_at"])

                    # Make timezone-naive for PostgreSQL
                    if order_date and order_date.tzinfo:
                        order_date = order_date.replace(tzinfo=None)
                else:
                    # Use current time if created_at is missing (should not happen)
                    order_date = datetime.utcnow()

                new_order = {
                    "store_id": str(store.id),
                    "platform_order_id": str(order_data["id"]),
                    "order_number": order_data["name"],
                    "order_status": order_data["financial_status"],
                    "customer_name": f"{order_data.get('customer', {}).get('first_name', '')} {order_data.get('customer', {}).get('last_name', '')}".strip(),
                    "customer_email": order_data.get("customer", {}).get("email"),
                    "total_price": float(order_data["total_price"]),
                    "currency": order_data["currency"],
                    "order_date": order_date,  # Use timezone-naive datetime
                    "order_data": order_data
                }

                order = await crud.create_order(db, new_order)

                # Process order items
                for item_data in order_data.get("line_items", []):
                    # Check if product_id exists and is not None
                    if item_data.get("product_id") is None:
                        continue

                    # Check if we have this product
                    product = await crud.get_product_by_platform_id(
                        db, str(store.id), str(item_data["product_id"])
                    )

                    # Create order item
                    order_item = {
                        "order_id": str(order.id),
                        "product_id": str(product.id) if product else None,
                        "platform_product_id": str(item_data["product_id"]),
                        "product_name": item_data["name"],
                        "variant_name": item_data.get("variant_title", ""),
                        "sku": item_data.get("sku", ""),
                        "quantity": item_data["quantity"],
                        "price": float(item_data["price"])
                    }

                    await db.execute(models.OrderItem.__table__.insert().values(**order_item))

        await db.commit()
    except Exception as e:
        logger.error(f"Error updating Shopify orders: {e}")
        await db.rollback()
        raise
    finally:
        # Close Shopify session
        client.close_session()


async def update_shopify_products(db: AsyncSession, store: models.Store):
    """
    Update products from Shopify.

    Args:
        db: Database session
        store: Store model
    """
    # Initialize Shopify client
    client = ShopifyClient(store)

    try:
        # Get products from Shopify
        products = await client.get_products(limit=250)  # Max allowed by Shopify

        # Process each product
        for product_data in products:
            # Check if we already have this product
            existing_product = await crud.get_product_by_platform_id(
                db, str(store.id), str(product_data["id"])
            )

            # Prepare product data
            product_info = {
                "store_id": str(store.id),
                "platform_product_id": str(product_data["id"]),
                "name": product_data["title"],
                "description": product_data.get("body_html"),
                "product_type": product_data.get("product_type"),
                "vendor": product_data.get("vendor"),
                "tags": product_data.get("tags"),
                "is_active": not product_data.get("published_at") is None,
                "product_data": product_data
            }

            # Get first variant for price and inventory information
            if product_data.get("variants"):
                variant = product_data["variants"][0]
                product_info["price"] = float(variant.get("price", 0))
                product_info["compare_at_price"] = float(variant.get("compare_at_price", 0)) if variant.get("compare_at_price") else None
                product_info["sku"] = variant.get("sku")
                product_info["inventory_quantity"] = variant.get("inventory_quantity", 0)

            if existing_product:
                # Update existing product
                await crud.update_product(db, str(existing_product.id), product_info)
            else:
                # Create new product
                await crud.create_product(db, product_info)

        await db.commit()
    except Exception as e:
        logger.error(f"Error updating Shopify products: {e}")
        await db.rollback()
        raise
    finally:
        # Close Shopify session
        client.close_session()


async def analyze_store_performance(db: AsyncSession, store_id: str) -> Dict[str, Any]:
    """
    Analyze store performance over time.

    Args:
        db: Database session
        store_id: Store ID

    Returns:
        dict: Performance analysis
    """
    # Get all orders for the store
    # For a real implementation, this would need pagination
    result = await db.execute(
        models.Order.__table__.select()
        .where(models.Order.store_id == store_id)
        .order_by(models.Order.order_date)
    )
    orders = result.fetchall()

    # Convert to DataFrame for easier analysis
    orders_df = pd.DataFrame(orders)

    if orders_df.empty:
        return {
            "status": "no_data",
            "message": "No order data available for analysis"
        }

    # Convert order_date to datetime
    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])

    # Set order_date as index
    orders_df.set_index("order_date", inplace=True)

    # Resample to daily frequency
    daily_sales = orders_df.resample("D")["total_price"].sum()
    daily_orders = orders_df.resample("D")["id"].count()

    # Calculate rolling averages (7-day)
    rolling_sales = daily_sales.rolling(window=7).mean()
    rolling_orders = daily_orders.rolling(window=7).mean()

    # Calculate growth rates
    sales_growth = daily_sales.pct_change(periods=7)  # Week-over-week
    orders_growth = daily_orders.pct_change(periods=7)  # Week-over-week

    # Find the latest values
    latest_sales = daily_sales.iloc[-1]
    latest_orders = daily_orders.iloc[-1]
    latest_avg_order_value = latest_sales / latest_orders if latest_orders > 0 else 0

    # Calculate growth vs. one week ago
    sales_vs_last_week = sales_growth.iloc[-1] if len(sales_growth) > 0 else 0
    orders_vs_last_week = orders_growth.iloc[-1] if len(orders_growth) > 0 else 0

    # Calculate monthly totals
    monthly_sales = orders_df.resample("M")["total_price"].sum()
    monthly_orders = orders_df.resample("M")["id"].count()

    # Get customer data
    unique_customers = len(orders_df["customer_email"].unique())

    # Format the response
    return {
        "status": "success",
        "summary": {
            "total_sales": orders_df["total_price"].sum(),
            "total_orders": len(orders_df),
            "unique_customers": unique_customers,
            "average_order_value": orders_df["total_price"].mean(),
        },
        "recent": {
            "latest_daily_sales": latest_sales,
            "latest_daily_orders": latest_orders,
            "latest_avg_order_value": latest_avg_order_value,
            "sales_growth_weekly": sales_vs_last_week,
            "orders_growth_weekly": orders_vs_last_week,
        },
        "historical": {
            "daily_sales": daily_sales.to_dict(),
            "daily_orders": daily_orders.to_dict(),
            "monthly_sales": monthly_sales.to_dict(),
            "monthly_orders": monthly_orders.to_dict(),
        }
    }