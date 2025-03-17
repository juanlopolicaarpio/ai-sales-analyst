#!/usr/bin/env python3
"""
Test script to verify Shopify integration with real data.
This script uses the environment variables for Shopify credentials.
"""

import asyncio
import sys
from pathlib import Path
import uuid
from datetime import datetime, timedelta
from sqlalchemy.sql import text  # Import text at the module level

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db
from app.core.agent import sales_analyst_agent
from app.core.shopify_client import ShopifyClient
from app.db import crud, models
from app.services.analytics import update_shopify_products, update_shopify_orders, get_sales_data
from app.config import settings

async def test_shopify_with_real_data():
    """Test Shopify integration with real shop data."""
    print("Testing Shopify integration with real data...")

    # Get a database session
    async for db in get_async_db():
        try:
            # Get or create test user
            user = await crud.get_user_by_email(db, "test@example.com")
            if not user:
                user_data = {
                    "id": str(uuid.uuid4()),
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "hashed_password": "not_a_real_hash",
                    "is_active": True
                }
                user = await crud.create_user(db, user_data)
                print("✅ Created test user")
            else:
                print("✅ Using existing test user")

            # Get or create Shopify store using environment variables
            admin_url = settings.SHOPIFY_STORE_URL
            if not admin_url:
                print("❌ SHOPIFY_STORE_URL not set in environment")
                return False

            # Extract store name from admin URL if it's an admin URL
            if "admin.shopify.com/store/" in admin_url:
                store_name = admin_url.split("admin.shopify.com/store/")[1].split("/")[0]
                store_url = f"{store_name}.myshopify.com"
                print(f"Extracted store domain: {store_url} from admin URL")
            else:
                # Assume it's already a proper domain
                store_url = admin_url
                # Clean URL if needed (remove https://, trailing slashes, etc.)
                if "://" in store_url:
                    store_url = store_url.split("://")[1]
                store_url = store_url.strip("/")

            # Use existing store or create new one
            existing_stores = await crud.get_stores_by_user(db, str(user.id))
            store = None
            
            for s in existing_stores:
                if s.store_url == store_url:
                    store = s
                    print(f"✅ Using existing store: {store.name}")
                    break
            
            if not store:
                # Create new store with credentials from environment
                store_data = {
                    "id": str(uuid.uuid4()),
                    "name": f"Shopify Store ({store_url})",
                    "platform": "shopify",
                    "store_url": store_url,  # This is now the proper myshopify.com domain
                    "api_key": settings.SHOPIFY_API_KEY,
                    "api_secret": settings.SHOPIFY_API_SECRET,
                    "access_token": settings.SHOPIFY_API_SECRET,  # Use API secret as access token
                    "is_active": True
                }
                
                store = await crud.create_store(db, store_data)
                print(f"✅ Created Shopify store connection for {store_url}")
                
                # Associate user with store
                stmt = text("""
                INSERT INTO store_user_association (user_id, store_id)
                VALUES (:user_id, :store_id)
                """)
                await db.execute(stmt, {"user_id": str(user.id), "store_id": str(store.id)})
                await db.commit()

            # Test Shopify connection
            client = ShopifyClient(store)
            shop_info = await client.get_shop_info()
            print(f"✅ Successfully connected to Shopify shop: {shop_info.get('shop', {}).get('name')}")
            
            # Fetch products
            products = await client.get_products(limit=10)
            print(f"✅ Successfully fetched {len(products)} products")
            
            # Fetch orders
            orders = await client.get_orders(limit=10)
            print(f"✅ Successfully fetched {len(orders)} orders")
            
            # Update products in database - PROPERLY AWAITED
            print("Updating products in database...")
            await update_shopify_products(db, store)
            
            # Count products in database
            count_query = text(f"SELECT COUNT(*) FROM products WHERE store_id = '{store.id}'")
            result = await db.execute(count_query)
            product_count = result.scalar()
            print(f"🔍 Database has {product_count} products")
            
            # Update orders in database - PROPERLY AWAITED
            print("Updating orders in database...")
            since_date = datetime.utcnow() - timedelta(days=30)
            await update_shopify_orders(db, store, since_date)
            
            # Count orders in database
            count_query = text(f"SELECT COUNT(*) FROM orders WHERE store_id = '{store.id}'")
            result = await db.execute(count_query)
            order_count = result.scalar()
            print(f"🔍 Database has {order_count} orders")
            
            # Get real sales data using your existing function
            print("\nGetting real sales data for OpenAI test...")
            sales_data = await get_sales_data(db, str(store.id), "last_7_days", "UTC")
            
            # Print summary of the data
            print(f"Total orders: {sales_data['summary']['total_orders']}")
            print(f"Total sales: ${sales_data['summary']['total_sales']:.2f}")
            
            if sales_data['top_products']:
                print("\nTop products:")
                for idx, product in enumerate(sales_data['top_products'], 1):
                    print(f"{idx}. {product['name']}: ${product['revenue']:.2f} ({product['quantity']} units)")
            
            # Test OpenAI integration with real data
            print("\nTesting OpenAI integration with real shop data...")
            
            # Use AI agent to analyze the data
            user_context = {
                "name": user.full_name or "Store Owner",
                "store_name": shop_info.get('shop', {}).get('name', store.name),
                "platform": "Shopify",
                "timezone": "UTC"
            }
            
            query = "What were my top selling products in the last 7 days? Any insights on how I can improve sales?"
            
            response = await sales_analyst_agent.analyze_query(
                query=query,
                user_context=user_context,
                sales_data=sales_data
            )
            
            print("\n✅ OpenAI integration test successful!")
            print("AI Response:")
            print(response)
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Shopify integration test: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Run the Shopify integration test with real data."""
    success = await test_shopify_with_real_data()
    
    print("\n=== SHOPIFY INTEGRATION TEST SUMMARY ===")
    print(f"Integration Test: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())