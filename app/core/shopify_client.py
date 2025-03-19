# shopify_client.py
import time
import json
import shopify
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import httpx
from loguru import logger
import re

from app.config import settings
from app.db.models import Store


class ShopifyClient:
    """Shopify API client for interfacing with Shopify stores."""
    
    def __init__(self, store: Store):
        """
        Initialize the Shopify client.
        
        Args:
            store: Store object with Shopify credentials.
        """
        self.store = store
        self.session = None
        self.api_version = '2023-10'  # Update to latest version as needed
        
        # Extract the actual store domain from admin URL if needed
        store_url = store.store_url
        if "admin.shopify.com/store/" in store_url:
            match = re.search(r'store/([^/]+)', store_url)
            if match:
                store_name = match.group(1)
                store_url = f"{store_name}.myshopify.com"
                logger.info(f"Extracted store domain: {store_url} from admin URL")
        
        # Clean up URL format (remove protocol)
        if store_url.startswith('https://'):
            store_url = store_url[8:]
        elif store_url.startswith('http://'):
            store_url = store_url[7:]
            
        self.shop_url = store_url
        self.access_token = store.access_token or settings.SHOPIFY_ACCESS_TOKEN
        
        logger.info(f"Initialized Shopify client for shop: {self.shop_url}")
        
    def _initialize_session(self):
        """Initialize or reinitialize the Shopify session."""
        if not self.access_token:
            raise ValueError("No Shopify access token found for store")
        
        shop_url = f"https://{self.store.api_key}:{self.access_token}@{self.shop_url}"
        self.session = shopify.Session(shop_url, self.api_version, self.access_token)
        shopify.ShopifyResource.activate_session(self.session)
        
    def close_session(self):
        """Close the Shopify session."""
        if self.session:
            shopify.ShopifyResource.clear_session()
            self.session = None
    
    async def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        """
        Make an authenticated request to the Shopify API.
        
        Args:
            endpoint: API endpoint path.
            method: HTTP method.
            params: Query parameters.
            data: Request body data.
        
        Returns:
            dict: API response.
        """
        base_url = f"https://{self.shop_url}/admin/api/{self.api_version}"
        url = f"{base_url}/{endpoint}.json"
        
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Making Shopify API request to: {url}")
        logger.debug(f"Using access token: {'*' * 5}{self.access_token[-4:] if self.access_token else 'None'}")
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    logger.warning(f"Shopify rate limit hit. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    return await self._make_request(endpoint, method, params, data)
                
                if response.status_code >= 400:
                    logger.error(f"Shopify API error: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error in request to {url}: {str(e)}")
                raise
    
    async def get_shop_info(self) -> Dict[str, Any]:
        """
        Get information about the shop.
        
        Returns:
            dict: Shop information.
        """
        try:
            return await self._make_request("shop")
        except Exception as e:
            logger.error(f"Error fetching shop info: {e}")
            raise
    
    async def get_orders(
        self, 
        since_id: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
        status: str = "any",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get orders from the shop.
        
        Args:
            since_id: Only return orders after this ID.
            created_at_min: Only return orders created after this time.
            created_at_max: Only return orders created before this time.
            status: Order status (any, open, closed, cancelled).
            limit: Maximum number of orders to return.
        
        Returns:
            list: List of orders.
        """
        params = {
            "status": status,
            "limit": limit
        }
        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        if created_at_max:
            params["created_at_max"] = created_at_max.isoformat()
        
        try:
            response = await self._make_request("orders", params=params)
            return response.get("orders", [])
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise
    
    async def get_products(
        self, 
        since_id: Optional[str] = None,
        product_type: Optional[str] = None,
        vendor: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get products from the shop.
        
        Args:
            since_id: Only return products after this ID.
            product_type: Filter by product type.
            vendor: Filter by vendor.
            limit: Maximum number of products to return.
        
        Returns:
            list: List of products.
        """
        params = {"limit": limit}
        if since_id:
            params["since_id"] = since_id
        if product_type:
            params["product_type"] = product_type
        if vendor:
            params["vendor"] = vendor
        
        try:
            response = await self._make_request("products", params=params)
            return response.get("products", [])
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            raise
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get a product by ID.
        
        Args:
            product_id: Shopify product ID.
        
        Returns:
            dict: Product information.
        """
        try:
            response = await self._make_request(f"products/{product_id}")
            return response.get("product", {})
        except Exception as e:
            logger.error(f"Error fetching product {product_id}: {e}")
            raise
    
    async def get_customers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get customers from the shop.
        
        Args:
            limit: Maximum number of customers to return.
        
        Returns:
            list: List of customers.
        """
        try:
            response = await self._make_request("customers", params={"limit": limit})
            return response.get("customers", [])
        except Exception as e:
            logger.error(f"Error fetching customers: {e}")
            raise
    
    async def get_order_count(
        self, 
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
        status: str = "any"
    ) -> int:
        """
        Get the number of orders.
        
        Args:
            created_at_min: Only count orders created after this time.
            created_at_max: Only count orders created before this time.
            status: Order status (any, open, closed, cancelled).
        
        Returns:
            int: Number of orders.
        """
        params = {"status": status}
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        if created_at_max:
            params["created_at_max"] = created_at_max.isoformat()
        
        try:
            response = await self._make_request("orders/count", params=params)
            return response.get("count", 0)
        except Exception as e:
            logger.error(f"Error fetching order count: {e}")
            raise
    
    async def get_inventory_level(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get inventory levels for a product.
        
        Args:
            product_id: Shopify product ID.
        
        Returns:
            list: Inventory levels.
        """
        try:
            product = await self.get_product(product_id)
            variant_ids = [variant["id"] for variant in product.get("variants", [])]
            
            inventory_items = []
            for variant_id in variant_ids:
                inventory_item_id = await self._get_inventory_item_id(variant_id)
                if inventory_item_id:
                    levels = await self._make_request(
                        "inventory_levels", 
                        params={"inventory_item_ids": inventory_item_id}
                    )
                    inventory_items.extend(levels.get("inventory_levels", []))
            
            return inventory_items
        except Exception as e:
            logger.error(f"Error fetching inventory for product {product_id}: {e}")
            raise
    
    async def _get_inventory_item_id(self, variant_id: str) -> Optional[str]:
        """
        Get the inventory item ID for a variant.
        
        Args:
            variant_id: Shopify variant ID.
        
        Returns:
            str: Inventory item ID.
        """
        try:
            response = await self._make_request(f"variants/{variant_id}")
            variant = response.get("variant", {})
            return variant.get("inventory_item_id")
        except Exception as e:
            logger.error(f"Error fetching variant {variant_id}: {e}")
            return None
    
    async def get_analytics_report(
        self, 
        report_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get analytics report from Shopify.
        
        Args:
            report_type: Type of report (sales, orders, etc.)
            start_date: Start date for the report.
            end_date: End date for the report.
        
        Returns:
            dict: Report data.
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        if report_type == "sales_by_location":
            query = """
            {
              salesByLocationAnalytics(
                startDate: "%s", 
                endDate: "%s",
                first: 50
              ) {
                nodes {
                  salesByLocation {
                    locationName
                    netSales
                    orderCount
                  }
                }
              }
            }
            """ % (start_str, end_str)
        elif report_type == "conversion_rate":
            query = """
            {
              shopifyAnalytics(
                startDate: "%s", 
                endDate: "%s"
              ) {
                onlineStoreSessions
                onlineStoreConversionRate
                totalOrders
              }
            }
            """ % (start_str, end_str)
        else:
            raise ValueError(f"Unsupported report type: {report_type}")
        
        try:
            response = await self._make_request(
                "graphql", 
                method="POST",
                data={"query": query}
            )
            return response.get("data", {})
        except Exception as e:
            logger.error(f"Error fetching analytics report {report_type}: {e}")
            raise
    
    async def get_geolocation_data(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get geographic distribution of orders.
        
        Args:
            start_date: Start date for orders to include.
            end_date: End date for orders to include.
        
        Returns:
            list: Geo data summary.
        """
        try:
            orders = await self.get_orders(
                created_at_min=start_date,
                created_at_max=end_date,
                limit=250
            )
            
            geo_data = {}
            for order in orders:
                shipping_address = order.get("shipping_address", {})
                if not shipping_address:
                    continue
                
                country = shipping_address.get("country", "Unknown")
                province = shipping_address.get("province", "Unknown")
                city = shipping_address.get("city", "Unknown")
                
                if country not in geo_data:
                    geo_data[country] = {
                        "total_orders": 0,
                        "total_sales": 0,
                        "regions": {}
                    }
                
                geo_data[country]["total_orders"] += 1
                geo_data[country]["total_sales"] += float(order.get("total_price", 0))
                
                if province:
                    if province not in geo_data[country]["regions"]:
                        geo_data[country]["regions"][province] = {
                            "total_orders": 0,
                            "total_sales": 0,
                            "cities": {}
                        }
                    
                    geo_data[country]["regions"][province]["total_orders"] += 1
                    geo_data[country]["regions"][province]["total_sales"] += float(order.get("total_price", 0))
                    
                    if city:
                        if city not in geo_data[country]["regions"][province]["cities"]:
                            geo_data[country]["regions"][province]["cities"][city] = {
                                "total_orders": 0,
                                "total_sales": 0
                            }
                        
                        geo_data[country]["regions"][province]["cities"][city]["total_orders"] += 1
                        geo_data[country]["regions"][province]["cities"][city]["total_sales"] += float(order.get("total_price", 0))
            
            result = []
            for country, country_data in geo_data.items():
                country_info = {
                    "country": country,
                    "total_orders": country_data["total_orders"],
                    "total_sales": country_data["total_sales"],
                    "regions": []
                }
                
                for region, region_data in country_data["regions"].items():
                    region_info = {
                        "name": region,
                        "total_orders": region_data["total_orders"],
                        "total_sales": region_data["total_sales"],
                        "cities": []
                    }
                    
                    for city, city_data in region_data["cities"].items():
                        city_info = {
                            "name": city,
                            "total_orders": city_data["total_orders"],
                            "total_sales": city_data["total_sales"]
                        }
                        region_info["cities"].append(city_info)
                    
                    country_info["regions"].append(region_info)
                
                result.append(country_info)
            
            result.sort(key=lambda x: x["total_sales"], reverse=True)
            
            return result
        except Exception as e:
            logger.error(f"Error fetching geo data: {e}")
            return []


# End of ShopifyClient class
