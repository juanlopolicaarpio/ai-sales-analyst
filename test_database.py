#!/usr/bin/env python3
"""
Test script to verify database connection.
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db, Base, engine
from app.db import models, crud
from app.config import settings
from app.db.models import User, Store
import uuid


async def test_database_connection():
    """Test database connection and basic operations."""
    print("Testing database connection...")

    try:
        # Create tables
        async with engine.begin() as conn:
            # For testing only - would use Alembic in production
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Successfully connected to database and created tables")
        return True
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False


async def test_basic_crud():
    """Test basic CRUD operations."""
    print("\nTesting basic CRUD operations...")
    
    try:
        # Get a database session
        async for db in get_async_db():
            # Create a test user
            user_id = str(uuid.uuid4())
            user_data = {
                "id": user_id,
                "email": f"test_{user_id[:8]}@example.com",
                "full_name": "Test User",
                "hashed_password": "not_a_real_hash",
                "is_active": True
            }
            
            user = await crud.create_user(db, user_data)
            print(f"✅ Created user: {user.email}")
            
            # Retrieve the user
            retrieved_user = await crud.get_user(db, str(user.id))
            if retrieved_user and retrieved_user.email == user.email:
                print(f"✅ Retrieved user successfully")
            else:
                print(f"❌ Failed to retrieve user")
            
            # Create a test store
            store_data = {
                "id": str(uuid.uuid4()),
                "name": "Test Store",
                "platform": "shopify",
                "store_url": "test-store.myshopify.com",
                "api_key": "test_key",
                "api_secret": "test_secret",
                "is_active": True
            }
            
            store = await crud.create_store(db, store_data)
            print(f"✅ Created store: {store.name}")
            
            return True
    except Exception as e:
        print(f"❌ CRUD operations error: {e}")
        return False


async def main():
    """Run all database tests."""
    # Test database connection
    db_conn_success = await test_database_connection()
    
    # Only test CRUD if connection works
    crud_success = False
    if db_conn_success:
        crud_success = await test_basic_crud()
    
    # Summary
    print("\n=== DATABASE TEST SUMMARY ===")
    print(f"Database Connection: {'✅ SUCCESS' if db_conn_success else '❌ FAILED'}")
    print(f"CRUD Operations: {'✅ SUCCESS' if crud_success else '❌ FAILED'}")
    print("============================")


if __name__ == "__main__":
    asyncio.run(main())