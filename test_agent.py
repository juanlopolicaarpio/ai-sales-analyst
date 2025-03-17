#!/usr/bin/env python3
"""
Test script to verify OpenAI integration and data fetching functionality.
"""

import os
import sys
import asyncio
from pathlib import Path
import json

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.agent import sales_analyst_agent
from app.config import settings
from dotenv import load_dotenv


async def test_openai_connection():
    """Test the connection to OpenAI API."""
    print("Testing OpenAI connection...")
    
    try:
        # Simple test query
        query = "What were my total sales yesterday?"
        user_context = {"name": "Test User", "store_name": "Test Store", "platform": "Shopify", "timezone": "UTC"}
        
        # Sample sales data
        sales_data = {
            "time_period": {
                "range_type": "yesterday",
                "start_date": "2023-03-15 00:00:00",
                "end_date": "2023-03-15 23:59:59",
            },
            "summary": {
                "total_sales": 1234.56,
                "total_orders": 12,
                "average_order_value": 102.88,
            }
        }
        
        # Call the agent
        response = await sales_analyst_agent.analyze_query(
            query=query,
            user_context=user_context,
            sales_data=sales_data
        )
        
        print("\n=== AI RESPONSE ===")
        print(response)
        print("===================\n")
        print("✅ OpenAI connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to OpenAI: {e}")
        return False


async def test_shopify_fetch():
    """Test fetching data from Shopify (if credentials are available)."""
    from app.core.shopify_client import ShopifyClient
    from app.db.models import Store
    
    print("\nTesting Shopify connection...")
    
    # Check if Shopify credentials are available
# Check if Shopify credentials are available
    if not all([settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_SECRET, settings.SHOPIFY_STORE_URL, settings.SHOPIFY_ACCESS_TOKEN]):
        print("❌ Shopify credentials not configured. Set SHOPIFY_API_KEY, SHOPIFY_API_SECRET, SHOPIFY_STORE_URL, and SHOPIFY_ACCESS_TOKEN in .env")
        return False    
    try:
        # Create a test store object
        test_store = Store(
            id="test-id",
            name="Test Store",
            platform="shopify",
            store_url=settings.SHOPIFY_STORE_URL,
            api_key=settings.SHOPIFY_API_KEY,
            api_secret=settings.SHOPIFY_API_SECRET,
            access_token=settings.SHOPIFY_API_SECRET  # Using API secret as token for private app
        )
        
        # Initialize client
        client = ShopifyClient(test_store)
        
        # Fetch shop info
        shop_info = await client.get_shop_info()
        print("\n=== SHOP INFO ===")
        print(json.dumps(shop_info, indent=2))
        print("=================\n")
        
        # Try to fetch orders
        orders = await client.get_orders(limit=5)
        print(f"Successfully fetched {len(orders)} orders")
        
        if orders:
            print("Sample order info:")
            print(json.dumps(orders[0], indent=2)[:500] + "...")
        
        print("✅ Shopify connection successful!")
        return True
    
    except Exception as e:
        print(f"❌ Error connecting to Shopify: {e}")
        return False


async def main():
    """Run all tests."""
    # Load environment variables
    load_dotenv()
    
    # Check if OpenAI API key is configured
    if not settings.OPENAI_API_KEY:
        print("❌ OpenAI API key not configured. Set OPENAI_API_KEY in .env")
        return
    
    # Test OpenAI connection
    openai_success = await test_openai_connection()
    
    # Skip Shopify test for now
    shopify_success = False
    print("\nSkipping Shopify test (requires asyncpg package)")
    
    # Summary
    print("\n=== TEST SUMMARY ===")
    print(f"OpenAI Connection: {'✅ SUCCESS' if openai_success else '❌ FAILED'}")
    print(f"Shopify Connection: SKIPPED")
    print("====================")
if __name__ == "__main__":
    asyncio.run(main())