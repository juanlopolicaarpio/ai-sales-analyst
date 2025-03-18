import sys
import os

# Path to the file
file_path = '/app/quick-query-test.py'

# Check if the file exists
if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

# Read the current content
with open(file_path, 'r') as f:
    content = f.read()

# Modify the test_chat_conversation function to fetch data first
updated_conversation_function = '''
async def test_chat_conversation(db, test_user):
    """Simulate a chat conversation with the AI Sales Analyst."""
    print("\\n=== STARTING CHAT CONVERSATION ===")
    
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
            from datetime import datetime, timedelta
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
        print(f"\\nUser Query #{i}: \\"{query}\\"")
        print("-" * 60)
        
        # Process the message using the message processor
        response, metadata = await message_processor.process_message(
            db=db,
            message_text=query,
            user_identifier={"email": test_user.email},
            channel="test"
        )
        
        print("\\nAI Response:")
        print(response)
        print("-" * 60)
        
        # Give the user a chance to read the response
        if i < len(queries):
            input("Press Enter to continue to next query...")
'''

# Replace the function
import re
pattern = r"async def test_chat_conversation\(db, test_user\):.*?if i < len\(queries\):\s+input\(\"Press Enter to continue to next query\.\.\.\"\)"
updated_content = re.sub(pattern, updated_conversation_function, content, flags=re.DOTALL)

# Also fix the SQL query to use SQLAlchemy text properly
updated_content = updated_content.replace(
    "stmt = text(\"\"\"",
    "from sqlalchemy.sql import text\n        stmt = text(\"\"\""
)

# Write the modified content back to the file
with open(file_path, 'w') as f:
    f.write(updated_content)

print(f"✅ Successfully updated {file_path}")
