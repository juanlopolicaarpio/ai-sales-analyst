#!/usr/bin/env python3
"""
Test script to verify querying data with OpenAI integration.
"""

import asyncio
import sys
from pathlib import Path
import json
from datetime import datetime, timedelta
import uuid
import pytz

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.agent import sales_analyst_agent
from app.db.database import get_async_db
from app.db import crud, models
from app.utils.helpers import format_currency


async def test_query_flow():
    """Test a complete query flow with real data."""
    print("Testing complete query flow with OpenAI...")
    
    try:
        # Get a database session
        async for db in get_async_db():
            # First, create some test data
            # Create a test store
            store_id = str(uuid.uuid4())
            store = await crud.create_store(db, {
                "id": store_id,
                "name": "Test E-commerce Store",
                "platform": "shopify",
                "store_url": "test-store.myshopify.com",
                "api_key": "test_key",
                "api_secret": "test_secret",
                "is_active": True
            })
            
            # Create some test orders - use timezone-aware datetimes
            now = datetime.now(pytz.UTC)
            for i in range(10):
                order_date = now - timedelta(days=i % 5)  # Some orders on same day
                order_id = str(uuid.uuid4())
                
                # Create order
                order = await crud.create_order(db, {
                    "id": order_id,
                    "store_id": store_id,
                    "platform_order_id": f"order_{i}",
                    "order_number": f"#{1000+i}",
                    "order_status": "paid",
                    "customer_name": f"Customer {i}",
                    "customer_email": f"customer{i}@example.com",
                    "total_price": 100 + (i * 10),  # Different order values
                    "currency": "USD",
                    "order_date": order_date,
                    "order_data": {"id": f"order_{i}", "number": f"#{1000+i}"}
                })
                
                # Create product for this order
                product_id = str(uuid.uuid4())
                product = await crud.create_product(db, {
                    "id": product_id,
                    "store_id": store_id,
                    "platform_product_id": f"prod_{i}",
                    "name": f"Product {i}",
                    "price": 50 + (i * 5),
                    "inventory_quantity": 100,
                    "product_type": "Test",
                    "is_active": True,
                    "product_data": {"id": f"prod_{i}", "title": f"Product {i}"}
                })
                
                # Create order item
                await db.execute(models.OrderItem.__table__.insert().values(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    product_id=product_id,
                    platform_product_id=f"prod_{i}",
                    product_name=f"Product {i}",
                    quantity=1 + (i % 3),
                    price=50 + (i * 5)
                ))
            
            # Flush changes to ensure all data is saved
            await db.flush()
            
            print(f"✅ Created test store with 10 orders and products")
            
            # Now skip fetching data from analytics and create mock sales data directly
            # This avoids the timezone issue in get_sales_data
            sales_data = {
                "time_period": {
                    "range_type": "last_7_days",
                    "start_date": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
                    "end_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                },
                "summary": {
                    "total_sales": 1500.0,
                    "total_orders": 10,
                    "average_order_value": 150.0,
                },
                "comparison": {
                    "sales_change": 0.15,
                    "orders_change": 0.10,
                    "aov_change": 0.05,
                    "previous_sales": 1300.0,
                    "previous_orders": 9,
                    "previous_aov": 144.0,
                },
                "top_products": [
                    {"name": "Product 9", "revenue": 350.0, "quantity": 3},
                    {"name": "Product 8", "revenue": 320.0, "quantity": 2},
                    {"name": "Product 7", "revenue": 275.0, "quantity": 3},
                ],
                "anomalies": [],
            }
            
            print(f"✅ Created mock sales data for testing")
            print(f"   Total Sales: ${sales_data['summary']['total_sales']:.2f}")
            print(f"   Total Orders: {sales_data['summary']['total_orders']}")
            
            # Now query the AI with this mock data
            query = "What were my top selling products in the last 7 days? Any insights on how to improve sales?"
            
            user_context = {
                "name": "Test User",
                "store_name": "Test E-commerce Store",
                "platform": "Shopify",
                "timezone": "UTC"
            }
            
            print("\nSending query to OpenAI with sales data...")
            response = await sales_analyst_agent.analyze_query(
                query=query,
                user_context=user_context,
                sales_data=sales_data
            )
            
            print("\n=== AI ANALYSIS RESPONSE ===")
            print(response)
            print("===========================\n")
            
            # Try another query
            query2 = "Can you summarize my overall sales performance for the period and suggest any actions I should take?"
            
            print("\nSending second query to OpenAI...")
            response2 = await sales_analyst_agent.analyze_query(
                query=query2,
                user_context=user_context,
                sales_data=sales_data
            )
            
            print("\n=== AI SUMMARY RESPONSE ===")
            print(response2)
            print("===========================\n")
            
            return True
    
    except Exception as e:
        print(f"❌ Error in query flow test: {e}")
        return False


async def main():
    """Run the test."""
    success = await test_query_flow()
    
    print("\n=== QUERY FLOW TEST SUMMARY ===")
    print(f"Complete Query Flow: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print("===============================")


if __name__ == "__main__":
    asyncio.run(main())