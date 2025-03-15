import time
import json
import shopify
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import httpx
from loguru import logger

from app.config import settings
from app.db.models import Store


class ShopifyClient:
    """Shopify API client for interfacing with Shopify stores."""
    
    def __init__(self, store: Store):
        """
        Initialize the Shopify client.
        
        Args:
            store: Store object with Shopify credentials
        """
        self.store = store
        self.session = None
        self.api_version = '2023-10'  # Update to latest version as needed
        
    def _initialize_session(self):
        """Initialize or reinitialize the Shopify session."""
        if not self.store.access_token:
            raise ValueError("No Shopify access token found for store")
        
        # Initialize the Shopify session with private app credentials
        shop_url = f"https://{self.store.api_key}:{self.store.access_token}@{self.store.store_url}"
        self.session = shopify.Session(shop_url, self.api_version, self.store.access_token)
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
            endpoint: API endpoint path
            method: HTTP method
            params: Query parameters
            data: Request body data
        
        Returns:
            dict: API response
        """
        base_url = f"https://{self.store.store_url}/admin/api/{self.api_version}"
        url = f"{base_url}/{endpoint}.json"
        
        headers = {
            "X-Shopify-Access-Token": self.store.access_token,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
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
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                logger.warning(f"Shopify rate limit hit. Waiting {retry_after} seconds.")
                time.sleep(retry_after)
                return await self._make_request(endpoint, method, params, data)
            
            response.raise_for_status()
            return response.json()
    
    async def get_shop_info(self) -> Dict[str, Any]:
        """
        Get information about the shop.
        
        Returns:
            dict: Shop information
        """
        try:
            return await self._make_request("shop")
        except Exception as e:
            logger.error(f"Error fetching shop info: {e}")
            raise
    
    async def get_orders(self, 
                    since_id: Optional[str] = None,
                    created_at_min: Optional[datetime] = None,
                    created_at_max: Optional[datetime] = None,
                    status: str = "any",
                    limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders from the shop.
        
        Args:
            since_id: Only return orders after this ID
            created_at_min: Only return orders created after this time
            created_at_max: Only return orders created before this time
            status: Order status (any, open, closed, cancelled)
            limit: Maximum number of orders to return
        
        Returns:
            list: List of orders
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
    
    async def get_products(self, 
                      since_id: Optional[str] = None,
                      product_type: Optional[str] = None,
                      vendor: Optional[str] = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get products from the shop.
        
        Args:
            since_id: Only return products after this ID
            product_type: Filter by product type
            vendor: Filter by vendor
            limit: Maximum number of products to return
        
        Returns:
            list: List of products
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
            product_id: Shopify product ID
        
        Returns:
            dict: Product information
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
            limit: Maximum number of customers to return
        
        Returns:
            list: List of customers
        """
        try:
            response = await self._make_request("customers", params={"limit": limit})
            return response.get("customers", [])
        except Exception as e:
            logger.error(f"Error fetching customers: {e}")
            raise
    
    async def get_order_count(self, 
                         created_at_min: Optional[datetime] = None,
                         created_at_max: Optional[datetime] = None,
                         status: str = "any") -> int:
        """
        Get the number of orders.
        
        Args:
            created_at_min: Only count orders created after this time
            created_at_max: Only count orders created before this time
            status: Order status (any, open, closed, cancelled)
        
        Returns:
            int: Number of orders
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
            product_id: Shopify product ID
        
        Returns:
            list: Inventory levels
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
            variant_id: Shopify variant ID
        
        Returns:
            str: Inventory item ID
        """
        try:
            response = await self._make_request(f"variants/{variant_id}")
            variant = response.get("variant", {})
            return variant.get("inventory_item_id")
        except Exception as e:
            logger.error(f"Error fetching variant {variant_id}: {e}")
            return None