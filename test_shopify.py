#!/usr/bin/env python3
"""
Test script for Shopify integration.
"""

import asyncio
import os
import sys
from pathlib import Path
import json
from loguru import logger

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db
from app.core.shopify_client import ShopifyClient
from app.db.models import Store, User
from app.config import settings
import uuid


async def test_shopify_with_real_data():
    """Test the Shopify integration with real data."""
    print("Testing Shopify integration with real data...")
    
    try:
        # Ensure we're using store environment variables
        if not settings.SHOPIFY_ACCESS_TOKEN:
            print("❌ No SHOPIFY_ACCESS_TOKEN found in environment variables")
            return False
            
        if not settings.SHOPIFY_STORE_URL:
            print("❌ No SHOPIFY_STORE_URL found in environment variables")
            return False
            
        print(f"Access Token: {'*' * 5}{settings.SHOPIFY_ACCESS_TOKEN[-4:] if settings.SHOPIFY_ACCESS_TOKEN else ''}")
        print(f"Store URL: {settings.SHOPIFY_STORE_URL}")
        
        # Create a test store for the integration test
        store = Store(
            id=str(uuid.uuid4()),
            name="Test Shopify Store",
            platform="shopify",
            store_url=settings.SHOPIFY_STORE_URL,
            api_key=settings.SHOPIFY_API_KEY or "",
            api_secret=settings.SHOPIFY_API_SECRET or "",
            access_token=settings.SHOPIFY_ACCESS_TOKEN,
            is_active=True
        )
        
        # Create a test user
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            is_active=True
        )
        print("✅ Created test user")
        
        # Initialize ShopifyClient with our store
        client = ShopifyClient(store)
        print(f"✅ Created Shopify store connection for {client.shop_url}")
        
        # Test getting shop info
        shop_info = await client.get_shop_info()
        print("\n=== SHOP INFO ===")
        print(json.dumps(shop_info, indent=2))
        print("=================\n")
        
        # Test getting some orders
        orders = await client.get_orders(limit=3)
        print(f"✅ Retrieved {len(orders)} orders")
        
        if orders:
            print("\n=== FIRST ORDER ===")
            # Print just some basic order info to avoid too much output
            order_summary = {
                "id": orders[0]["id"],
                "order_number": orders[0]["name"],
                "total_price": orders[0]["total_price"],
                "created_at": orders[0]["created_at"],
                "customer": orders[0].get("customer", {}).get("email", "No customer email")
            }
            print(json.dumps(order_summary, indent=2))
            print("==================\n")
        
        # Test getting some products
        products = await client.get_products(limit=3)
        print(f"✅ Retrieved {len(products)} products")
        
        if products:
            print("\n=== FIRST PRODUCT ===")
            # Print just some basic product info
            product_summary = {
                "id": products[0]["id"],
                "title": products[0]["title"],
                "product_type": products[0]["product_type"],
                "created_at": products[0]["created_at"],
                "variants_count": len(products[0]["variants"])
            }
            print(json.dumps(product_summary, indent=2))
            print("====================\n")
        
        print("✅ Shopify integration tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in Shopify integration test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the test."""
    success = await test_shopify_with_real_data()
    
    print("\n=== SHOPIFY INTEGRATION TEST SUMMARY ===")
    print(f"Integration Test: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print("========================================")


if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="DEBUG")  # Add handler with DEBUG level
    
    asyncio.run(main())