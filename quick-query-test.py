#!/usr/bin/env python3
"""
Test script to simulate a chat conversation using real Shopify data.

This script uses the message_processor to simulate a user asking questions
about their Shopify store, similar to how they would via Slack, WhatsApp, or email.
"""

import asyncio
import sys
from pathlib import Path
import uuid
import json
from datetime import datetime
from loguru import logger

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db
from app.core.message_processor import message_processor
from app.core.shopify_client import ShopifyClient
from app.db import crud, models
from app.config import settings


async def setup_test_env(db):
    """Set up test user and store with real Shopify credentials."""
    print("Setting up test environment...")
    
    # Create or get test user
    test_user = await crud.get_user_by_email(db, "test@example.com")
    if not test_user:
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "not_real_password",
            "is_active": True
        }
        test_user = await crud.create_user(db, user_data)
        print(f"Created new test user: {test_user.email}")
    else:
        print(f"Using existing test user: {test_user.email}")
    
    # Create or get test store with real Shopify credentials
    stores = await crud.get_stores_by_user(db, str(test_user.id))
    test_store = None
    
    if stores:
        # Check if any existing store uses Shopify
        for store in stores:
            if store.platform == "shopify":
                test_store = store
                break
    
    if not test_store:
        # Create new store with Shopify credentials
        store_data = {
            "id": str(uuid.uuid4()),
            "name": f"Shopify Store ({settings.SHOPIFY_STORE_URL})",
            "platform": "shopify",
            "store_url": settings.SHOPIFY_STORE_URL,
            "api_key": settings.SHOPIFY_API_KEY or "",
            "api_secret": settings.SHOPIFY_API_SECRET or "",
            "access_token": settings.SHOPIFY_ACCESS_TOKEN,
            "is_active": True
        }
        test_store = await crud.create_store(db, store_data)
        
        # Associate user with store
        from sqlalchemy.sql import text
        stmt = text("""
        INSERT INTO store_user_association (user_id, store_id)
        VALUES (:user_id, :store_id)
        """)
        await db.execute(stmt, {"user_id": str(test_user.id), "store_id": str(test_store.id)})
        await db.commit()
        
        print(f"Created new test store: {test_store.name}")
    else:
        print(f"Using existing store: {test_store.name}")
        
        # Update store with current credentials
        update_data = {
            "store_url": settings.SHOPIFY_STORE_URL,
            "api_key": settings.SHOPIFY_API_KEY or test_store.api_key,
            "api_secret": settings.SHOPIFY_API_SECRET or test_store.api_secret,
            "access_token": settings.SHOPIFY_ACCESS_TOKEN
        }
        test_store = await crud.update_store(db, str(test_store.id), update_data)
        print("Updated store with current Shopify credentials")
    
    # Set up user preferences
    preferences = await db.execute(
        models.UserPreference.__table__.select().where(models.UserPreference.user_id == test_user.id)
    )
    user_preferences = preferences.fetchone()
    
    if not user_preferences:
        # Create user preferences
        preferences_data = {
            "id": str(uuid.uuid4()),
            "user_id": str(test_user.id),
            "notification_channel": "email",
            "daily_report_time": "09:00",
            "timezone": "UTC",
            "notification_preferences": {
                "sales_alerts": True,
                "anomaly_detection": True,
                "daily_summary": True
            }
        }
        await db.execute(models.UserPreference.__table__.insert().values(**preferences_data))
        await db.commit()
        print("Created user preferences")
    
    return test_user


async def test_chat_conversation(db, test_user):
    """Simulate a chat conversation with the AI Sales Analyst."""
    print("\n=== STARTING CHAT CONVERSATION ===")
    
    # First, fetch latest data from Shopify
    print("Fetching latest data from Shopify before starting conversation...")
    try:
        # Get the user's store
        stores = await crud.get_stores_by_user(db, str(test_user.id))
        if stores:
            store_id = str(stores[0].id)
            store = stores[0]
            print(f"Store ID: {store_id}")
            
            # Manually call update_shopify_orders and update_shopify_products
            from app.services.analytics import update_shopify_orders, update_shopify_products
            
            # Use last 30 days for data fetching
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=30)
            
            print("Fetching orders from Shopify...")
            await update_shopify_orders(db, store, start_date)
            
            print("Fetching products from Shopify...")
            await update_shopify_products(db, store)
            
            print("✅ Data fetch completed")
            
            # Count orders and products
            from sqlalchemy import func, select
            from app.db.models import Order, Product
            
            result = await db.execute(select(func.count()).select_from(Order).where(Order.store_id == store_id))
            order_count = result.scalar()
            
            result = await db.execute(select(func.count()).select_from(Product).where(Product.store_id == store_id))
            product_count = result.scalar()
            
            print(f"Store has {order_count} orders and {product_count} products in database")
        else:
            print("❌ No stores found for this user")
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        import traceback
        traceback.print_exc()
    
    # List of queries to test
    queries = [
        "How were my sales yesterday?",
        "What are my top selling products?",
        "Which products have the highest revenue this month?",
        "Have there been any unusual patterns in my sales recently?",
        "Give me a summary of my store's performance over the last week"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\nUser Query #{i}: \"{query}\"")
        print("-" * 60)
        
        # Process the message using the message processor
        response, metadata = await message_processor.process_message(
            db=db,
            message_text=query,
            user_identifier={"email": test_user.email},
            channel="test"
        )
        
        print("\nAI Response:")
        print(response)
        print("-" * 60)
        
        # Give the user a chance to read the response
        if i < len(queries):
            input("Press Enter to continue to next query...")


async def test_specific_query(db, test_user, query):
    """Test a specific user query."""
    print("\n=== TESTING SPECIFIC QUERY ===")
    print(f"Query: \"{query}\"")
    print("-" * 60)
    
    # Process the message
    response, metadata = await message_processor.process_message(
        db=db,
        message_text=query,
        user_identifier={"email": test_user.email},
        channel="test"
    )
    
    print("\nAI Response:")
    print(response)
    print("-" * 60)


async def main():
    """Run the chat integration test."""
    print("=== CHAT INTEGRATION TEST WITH SHOPIFY DATA ===")
    
    # Check if required environment variables are set
    if not all([settings.SHOPIFY_STORE_URL, settings.SHOPIFY_ACCESS_TOKEN, settings.OPENAI_API_KEY]):
        print("❌ Missing required environment variables.")
        print("Please ensure SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN, and OPENAI_API_KEY are set.")
        return
    
    async for db in get_async_db():
        try:
            # Set up test environment
            test_user = await setup_test_env(db)
            
            # Display user and store information
            print(f"\nTest User ID: {test_user.id}")
            print(f"Test User Email: {test_user.email}")
            
            # Verify user has associated stores
            stores = await crud.get_stores_by_user(db, str(test_user.id))
            if not stores:
                print("❌ No stores associated with test user. Something went wrong during setup.")
                return
                
            print(f"Store count: {len(stores)}")
            print(f"Store details: {stores[0].name} (ID: {stores[0].id})")
            
            # Choose test mode
            print("\nTest Options:")
            print("1. Run full conversation (multiple queries)")
            print("2. Test a specific query")
            
            choice = input("Select an option (1/2): ").strip()
            
            if choice == "1":
                await test_chat_conversation(db, test_user)
            elif choice == "2":
                query = input("\nEnter your query: ").strip()
                await test_specific_query(db, test_user, query)
            else:
                print("Invalid option selected.")
            
            print("\n=== TEST COMPLETE ===")
            
        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="INFO")  # Add handler with INFO level
    
    asyncio.run(main())
