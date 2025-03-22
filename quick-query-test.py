#!/usr/bin/env python3
"""
Interactive chat test with the AI Sales Analyst.

This script allows for continuous conversation with the AI to test
context retention and dialogue capabilities with LangChain integration.
"""

import asyncio
import sys
from pathlib import Path
import uuid
import json
from datetime import datetime, timedelta
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


async def fetch_latest_data(db, test_user):
    """Fetch the latest data from Shopify to ensure fresh data for testing."""
    print("\n=== FETCHING LATEST DATA ===")
    
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
            return True
        else:
            print("❌ No stores found for this user")
            return False
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        import traceback
        traceback.print_exc()
        return False


async def interactive_conversation(db, test_user):
    """
    Have an interactive conversation with the AI.
    This mode allows testing the memory capabilities of LangChain.
    """
    print("\n=== INTERACTIVE CONVERSATION MODE ===")
    print("Type your messages to the AI Sales Analyst and press Enter to send.")
    print("Type 'exit', 'quit', or 'bye' to end the conversation.")
    print("Type 'clear memory' to reset the conversation memory.")
    print("Type 'debug' to see debug information about conversation memory.")
    print("-" * 60)
    
    # Extract email from test_user immediately to avoid async issues later
    # This is important because SQLAlchemy might try to lazily load properties later
    user_email = test_user.email  # Eagerly load this attribute
    conversation_channel = "test"
    user_identifier = {"email": user_email}
    
    # Create a header for the conversation
    print("\n🤖 AI Sales Analyst: Hello! I'm your AI sales analyst assistant.")
    print("   I can help analyze your sales data, identify trends, and provide insights.")
    print("   What would you like to know about your store's performance?\n")
    
    # Interactive loop
    while True:
        # Get user input
        user_message = input("You: ").strip()
        
        # Exit commands
        if user_message.lower() in ["exit", "quit", "bye"]:
            print("\n🤖 AI Sales Analyst: Goodbye! Have a great day!")
            break
        
        # Clear memory command
        if user_message.lower() == "clear memory":
            print("\nClearing conversation memory...")
            await message_processor.clear_user_memory(user_identifier, conversation_channel)
            print("Memory cleared! The AI will start with a fresh conversation.")
            continue
        
        # Debug command
        if user_message.lower() == "debug":
            # Simple debug info
            print("\n=== DEBUG INFO ===")
            print(f"User: {user_email}")
            print(f"Conversation channel: {conversation_channel}")
            # Could add more debug info here in the future
            print("=================")
            continue
        
        # Skip empty messages
        if not user_message:
            continue
        
        try:
            # Process the message
            response, metadata = await message_processor.process_message(
                db=db,
                message_text=user_message,
                user_identifier=user_identifier,
                channel=conversation_channel
            )
            
            # Print AI response
            print(f"\n🤖 AI Sales Analyst: {response}\n")
            
        except Exception as e:
            print(f"\n❌ Error processing message: {e}")
            import traceback
            traceback.print_exc()
async def guided_conversation(db, test_user):
    """
    Run a guided conversation with scripted follow-up questions to show context retention.
    This helps demonstrate the memory capabilities of LangChain.
    """
    print("\n=== GUIDED CONVERSATION DEMO ===")
    print("This will run a series of related questions to demonstrate conversation memory.")
    print("Press Enter after each response to continue to the next question.")
    print("-" * 60)
    
    # Reset memory to start fresh
    await message_processor.clear_user_memory({"email": test_user.email}, "test")
    
    # Series of related questions that build on previous context
    conversation = [
        "What were my total sales last month?",
        "How does that compare to the previous month?",
        "Which regions performed best?",
        "What about the worst performing regions?",
        "Why do you think those regions performed poorly?",
        "What were the top products in my best region?",
        "Give me three recommendations to improve sales in my underperforming regions."
    ]
    
    for i, query in enumerate(conversation, 1):
        print(f"\nQuestion #{i}: \"{query}\"")
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
        
        # Wait for user input before continuing
        if i < len(conversation):
            input("Press Enter to continue to the next question...")


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


async def geo_query_test(db, test_user):
    """Special test for geographic data queries."""
    print("\n=== GEOGRAPHIC DATA TEST ===")
    print("This will test the geographic data extraction and reporting.")
    print("-" * 60)
    
    # Reset memory to start fresh
    await message_processor.clear_user_memory({"email": test_user.email}, "test")
    
    # Series of geography-related questions
    geo_queries = [
        "What regions have my products been selling in?",
        "Which countries generate the most revenue?",
        "What are my top 3 cities by sales?",
        "How are my sales in Asia compared to North America?",
        "What regions should I focus on to grow my business?",
        "What regions are underperforming?"
    ]
    
    for i, query in enumerate(geo_queries, 1):
        print(f"\nGeographic Query #{i}: \"{query}\"")
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
        
        # Wait for user input before continuing
        if i < len(geo_queries):
            input("Press Enter to continue to the next query...")


async def main():
    """Run the chat integration test."""
    print("=== ENHANCED CHAT INTEGRATION TEST ===")
    print("This script tests the AI Sales Analyst with LangChain conversation memory")
    
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
            
            # Fetch latest data
            data_fetched = await fetch_latest_data(db, test_user)
            if not data_fetched:
                print("⚠️ Warning: Failed to fetch latest data. Continuing with existing data...")
            
            # Choose test mode
            while True:
                print("\nTest Options:")
                print("1. Interactive conversation (you chat with the AI)")
                print("2. Guided conversation demo (with follow-up questions)")
                print("3. Geographic data test (test the geo data fix)")
                print("4. Test a specific query")
                print("5. Exit")
                
                choice = input("Select an option (1-5): ").strip()
                
                if choice == "1":
                    await interactive_conversation(db, test_user)
                elif choice == "2":
                    await guided_conversation(db, test_user)
                elif choice == "3":
                    await geo_query_test(db, test_user)
                elif choice == "4":
                    query = input("\nEnter your query: ").strip()
                    await test_specific_query(db, test_user, query)
                elif choice == "5":
                    print("Exiting test script.")
                    break
                else:
                    print("Invalid option selected. Please try again.")
            
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