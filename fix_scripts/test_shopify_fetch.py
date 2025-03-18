import asyncio
import logging
from sqlalchemy import select
from app.db.database import get_async_db
from app.db import crud, models
from app.core.shopify_client import ShopifyClient
from app.services.analytics import update_shopify_orders, update_shopify_products
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fetch_data():
    """Test fetching data from Shopify for the first store."""
    print("Testing data fetch from Shopify...")
    
    async for db in get_async_db():
        try:
            # Get the first store
            query = await db.execute(select(models.Store).where(models.Store.is_active == True))
            store = query.scalars().first()
            
            if not store:
                print("❌ No active stores found in database")
                return
                
            print(f"Using store: {store.name} ({store.store_url})")
            
            # Create ShopifyClient
            client = ShopifyClient(store)
            print(f"Initialized ShopifyClient with shop_url: {client.shop_url}")
            
            # Test connection by getting shop info
            try:
                shop_info = await client.get_shop_info()
                if "shop" in shop_info:
                    print(f"✅ Connected to Shopify store: {shop_info['shop']['name']}")
                else:
                    print("❌ Failed to get shop info")
                    return
            except Exception as e:
                print(f"❌ Error connecting to Shopify: {e}")
                return
                
            # Set date range for the last 30 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            print(f"Fetching orders from {start_date} to {end_date}")
            
            # Count orders and products before update
            result = await db.execute(select(models.Order).where(models.Order.store_id == store.id))
            order_count_before = len(result.scalars().all())
            
            result = await db.execute(select(models.Product).where(models.Product.store_id == store.id))
            product_count_before = len(result.scalars().all())
            
            print(f"Before update: {order_count_before} orders, {product_count_before} products")
            
            # Fetch orders and products
            print("Fetching orders from Shopify...")
            await update_shopify_orders(db, store, start_date)
            
            print("Fetching products from Shopify...")
            await update_shopify_products(db, store)
            
            # Count orders and products after update
            result = await db.execute(select(models.Order).where(models.Order.store_id == store.id))
            order_count_after = len(result.scalars().all())
            
            result = await db.execute(select(models.Product).where(models.Product.store_id == store.id))
            product_count_after = len(result.scalars().all())
            
            print(f"After update: {order_count_after} orders, {product_count_after} products")
            print(f"Added {order_count_after - order_count_before} orders and {product_count_after - product_count_before} products")
            
            print("✅ Data fetch test completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fetch_data())
