#!/usr/bin/env python3
"""
Quick test script to verify the setup of the AI Sales Analyst application.
This script tests:
1. Database connection
2. OpenAI integration
3. Slack, WhatsApp, and Email configurations (optional)
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db, engine, Base
from app.core.agent import sales_analyst_agent
from app.config import settings
from app.utils.logger import logger


async def test_database_connection():
    """Test connection to the database."""
    print("\n=== Testing Database Connection ===")
    try:
        # Create a database session
        async for db in get_async_db():
            # Try a simple query
            from sqlalchemy.sql import text
            result = await db.execute(text("SELECT 1"))
            value = result.scalar()
            
            if value == 1:
                print("✅ Database connection successful!")
                return True
            else:
                print("❌ Database connection check failed")
                return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False


async def test_openai_integration():
    """Test OpenAI integration."""
    print("\n=== Testing OpenAI Integration ===")
    
    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set in environment variables")
        return False
    
    try:
        # Simple test query
        query = "Give me a quick sales summary."
        user_context = {"name": "Test User", "store_name": "Test Store", "platform": "Test Platform", "timezone": "UTC"}
        
        # Sample sales data
        sales_data = {
            "time_period": {
                "range_type": "today",
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "summary": {
                "total_sales": 1234.56,
                "total_orders": 10,
                "average_order_value": 123.46,
            },
            "comparison": {
                "sales_change": 0.15,
                "orders_change": 0.10,
                "aov_change": 0.05,
                "previous_sales": 1073.53,
                "previous_orders": 9,
                "previous_aov": 119.28,
            },
            "top_products": [
                {"name": "Test Product 1", "revenue": 500.00, "quantity": 5},
                {"name": "Test Product 2", "revenue": 300.00, "quantity": 3}
            ]
        }
        
        # Call the agent
        response = await sales_analyst_agent.analyze_query(
            query=query,
            user_context=user_context,
            sales_data=sales_data
        )
        
        if response:
            print(f"✅ OpenAI integration successful!")
            print("Sample response preview:")
            print(response[:150] + "..." if len(response) > 150 else response)
            return True
        else:
            print("❌ OpenAI returned empty response")
            return False
    except Exception as e:
        print(f"❌ OpenAI integration error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integrations():
    """Test integration settings."""
    print("\n=== Testing Integration Configurations ===")
    
    integrations = {
        "Slack": bool(settings.SLACK_BOT_TOKEN and settings.SLACK_SIGNING_SECRET),
        "WhatsApp (Twilio)": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER),
        "Email": bool(settings.EMAIL_HOST and settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD),
        "Shopify": bool(settings.SHOPIFY_STORE_URL and settings.SHOPIFY_ACCESS_TOKEN)
    }
    
    for name, is_configured in integrations.items():
        status = "✅ Configured" if is_configured else "⚠️ Not configured"
        print(f"{name}: {status}")
    
    return True


async def run_tests():
    """Run all tests."""
    try:
        # Test database connection
        db_result = await test_database_connection()
        
        # Test OpenAI integration
        openai_result = await test_openai_integration()
        
        # Test integration configurations
        integration_result = await test_integrations()
        
        # Summary
        print("\n=== Test Summary ===")
        print(f"Database Connection: {'✅ SUCCESS' if db_result else '❌ FAILED'}")
        print(f"OpenAI Integration: {'✅ SUCCESS' if openai_result else '❌ FAILED'}")
        print(f"Integration Configs: {'✅ SUCCESS' if integration_result else '⚠️ WARNING'}")
        
        if db_result and openai_result:
            print("\n✅ Basic requirements met! You can run the application.")
        else:
            print("\n❌ Some critical components failed. Please fix the issues before running the application.")
    except Exception as e:
        print(f"Error during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run tests
    asyncio.run(run_tests())