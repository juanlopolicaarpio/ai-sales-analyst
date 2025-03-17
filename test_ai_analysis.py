#!/usr/bin/env python3
"""
Simple test for OpenAI integration with mock sales data.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.agent import sales_analyst_agent


async def test_ai_analysis():
    """Test the AI's ability to analyze sales data."""
    print("Testing AI Sales Analysis...")
    
    # Create mock sales data
    mock_sales_data = {
        "time_period": {
            "range_type": "last_7_days",
            "start_date": "2025-03-08 00:00:00",
            "end_date": "2025-03-15 23:59:59",
        },
        "summary": {
            "total_sales": 12500.75,
            "total_orders": 85,
            "average_order_value": 147.07,
        },
        "comparison": {
            "sales_change": 0.15,
            "orders_change": 0.10,
            "aov_change": 0.05,
            "previous_sales": 10870.25,
            "previous_orders": 77,
            "previous_aov": 141.17,
        },
        "top_products": [
            {"name": "Premium T-Shirt", "revenue": 3500.00, "quantity": 50},
            {"name": "Wireless Headphones", "revenue": 2800.00, "quantity": 20},
            {"name": "Phone Case", "revenue": 1950.00, "quantity": 65},
            {"name": "Fitness Tracker", "revenue": 1520.00, "quantity": 10},
            {"name": "Sunglasses", "revenue": 1200.00, "quantity": 15}
        ],
        "anomalies": [
            {
                "type": "unusually_high_sales",
                "date": "2025-03-14",
                "value": 2500.00,
                "expected_value": 1800.00,
                "percentage_change": 0.39,
                "severity": 3,
                "description": "Sales on Friday were 39% higher than expected."
            }
        ],
    }
    
    # Set up user context
    user_context = {
        "name": "Test User",
        "store_name": "Example E-commerce Store",
        "platform": "Shopify",
        "timezone": "UTC"
    }
    
    # List of sample queries to test
    test_queries = [
        "What were my top selling products in the last week?",
        "How did my sales compare to the previous period?",
        "Did you notice any unusual patterns in my sales data?",
        "What's my average order value and how has it changed?",
        "Can you give me a summary of my overall performance and suggest improvements?"
    ]
    
    print("\n=== Testing AI responses with mock sales data ===")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n----- Test Query {i} -----")
        print(f"Query: {query}")
        
        try:
            response = await sales_analyst_agent.analyze_query(
                query=query,
                user_context=user_context,
                sales_data=mock_sales_data
            )
            
            print(f"\nAI Response:")
            print(response)
            print("-----------------------")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n=== AI Testing Complete ===")


if __name__ == "__main__":
    asyncio.run(test_ai_analysis())