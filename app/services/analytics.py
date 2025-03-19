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
from app.utils.helpers import get_date_range
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
    
    # FIXED: Use selectinload to eager load order_items instead of lazy loading
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
    
    # FIXED: Use selectinload for previous orders too
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
    
    # Get top products
    product_sales = {}
    for order in orders:
        for item in order.order_items:  # Now safely using eager-loaded relationship
            if item.product_id not in product_sales:
                product_sales[item.product_id] = {
                    "name": item.product_name,
                    "revenue": 0,
                    "quantity": 0
                }
            product_sales[item.product_id]["revenue"] += item.price * item.quantity
            product_sales[item.product_id]["quantity"] += item.quantity
    
    # Sort for top and bottom products
    sorted_products = sorted(
        product_sales.values(),
        key=lambda x: x["revenue"],
        reverse=True
    )
    
    top_products = sorted_products[:10]
    bottom_products = sorted_products[-10:] if len(sorted_products) > 10 else []
    
    # Fetch geo data if requested
    geo_data = []
    if include_geo_data:
        try:
            # Get the store to initialize ShopifyClient
            store_result = await db.execute(select(models.Store).where(models.Store.id == store_id))
            store = store_result.scalars().first()
            
            if store:
                client = ShopifyClient(store)
                geo_data = await client.get_geolocation_data(start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching geo data: {e}")
    
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
        "top_products": top_products,
        "bottom_products": bottom_products,
        "geo_data": geo_data,
        "conversion": conversion_data,
        "anomalies": [],  # This would be populated by the anomaly detection service
    }
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