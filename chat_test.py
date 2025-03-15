#!/usr/bin/env python3
"""
Interactive chat test with the AI Sales Analyst.
"""

import asyncio
import sys
from pathlib import Path
import uuid

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.message_processor import message_processor
from app.db.database import get_async_db
from app.db import crud, models


async def create_test_user_and_store(db):
    """Create a test user and store for the chat test."""
    # Check if the test user already exists
    test_user = await crud.get_user_by_email(db, "test@example.com")
    
    if not test_user:
        # Create test user
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "not_a_real_hash",
            "is_active": True
        }
        test_user = await crud.create_user(db, user_data)
        print(f"Created test user: {test_user.email}")
    else:
        user_id = str(test_user.id)
        print(f"Using existing test user: {test_user.email}")
    
    # Check if the test user has any stores
    stores = await crud.get_stores_by_user(db, user_id)
    
    if not stores:
        # Create a test store
        store_id = str(uuid.uuid4())
        store_data = {
            "id": store_id,
            "name": "Test Store",
            "platform": "shopify",
            "store_url": "test-store.myshopify.com",
            "api_key": "test_key",
            "api_secret": "test_secret",
            "is_active": True
        }
        store = await crud.create_store(db, store_data)
        print(f"Created test store: {store.name}")
        
        # Associate user with store
        stmt = """
        INSERT INTO store_user_association (user_id, store_id)
        VALUES (:user_id, :store_id)
        """
        await db.execute(stmt, {"user_id": user_id, "store_id": store_id})
        await db.commit()
    else:
        print(f"User already has {len(stores)} store(s)")
    
    return test_user


async def chat_loop():
    """Run an interactive chat loop with the AI agent."""
    print("=== AI Sales Analyst Chat Test ===")
    print("Type your sales queries. Type 'exit' to quit.")
    print("Sample queries:")
    print("- What were my sales yesterday?")
    print("- What are my top-selling products?")
    print("- How does this week compare to last week?")
    print("")
    
    async for db in get_async_db():
        # Create test user and store
        test_user = await create_test_user_and_store(db)
        
        while True:
            query = input("\nYou: ").strip()
            
            if query.lower() in ["exit", "quit", "bye"]:
                print("Exiting chat test.")
                break
                
            # Process the message using your message processor
            response, metadata = await message_processor.process_message(
                db=db,
                message_text=query,
                user_identifier={"email": test_user.email},
                channel="test"
            )
            
            print(f"\nAI: {response}")


if __name__ == "__main__":
    asyncio.run(chat_loop())