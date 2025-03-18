import sys
import os

# Path to the file
file_path = '/app/app/core/scheduler.py'

# Check if the file exists
if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

# Create a new version of the scheduler.py file
new_content = '''
import os
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger
from app.db.database import AsyncSessionLocal
from app.config import settings
from app.db import crud, models
from app.services.analytics import analyze_sales_data
from app.services.anomaly_detection import detect_anomalies
from app.services.reporting import send_daily_report

# Create a synchronous session for Celery tasks
# Since Celery tasks run synchronously, we need a synchronous DB session
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql+asyncpg://"):
    sync_db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
else:
    sync_db_url = db_url

engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize Celery
celery = Celery(
    "ai_sales_analyst",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configure Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Set up periodic tasks
celery.conf.beat_schedule = {
    "fetch_new_orders_hourly": {
        "task": "app.core.scheduler.fetch_new_orders",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "detect_anomalies_hourly": {
        "task": "app.core.scheduler.detect_hourly_anomalies",
        "schedule": crontab(minute=5),  # Every hour at minute 5
    },
    "daily_sales_report": {
        "task": "app.core.scheduler.generate_daily_reports",
        "schedule": crontab(hour=0, minute=15),  # Every day at 00:15 UTC
    },
}

@celery.task
def fetch_new_orders():
    """Fetch new orders from all active stores."""
    try:
        logger.info("Starting fetch_new_orders task")
        db = SessionLocal()
        try:
            # Get all active stores
            stores = db.query(models.Store).filter(models.Store.is_active == True).all()
            logger.info(f"Found {len(stores)} active stores")
            for store in stores:
                # Convert to string for the task
                logger.info(f"Queueing update_store_data for store: {store.name} ({store.id})")
                update_store_data.delay(str(store.id))
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error scheduling fetch_new_orders: {e}")

@celery.task
def update_store_data(store_id: str):
    """Update data for a specific store."""
    try:
        logger.info(f"Starting update_store_data for store {store_id}")
        db = SessionLocal()
        try:
            # Get the most recent order date to use as starting point
            latest_order = (
                db.query(models.Order)
                .filter(models.Order.store_id == store_id)
                .order_by(models.Order.order_date.desc())
                .first()
            )
            
            start_date = None
            if latest_order:
                # Get orders since the last order date
                start_date = latest_order.order_date
                logger.info(f"Fetching orders since {start_date}")
            else:
                # If no orders, get orders from the last 30 days
                start_date = datetime.utcnow() - timedelta(days=30)
                logger.info(f"No previous orders, fetching orders from the last 30 days")
            
            # Get the store
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if not store:
                logger.error(f"Store not found: {store_id}")
                return
            
            logger.info(f"Processing data for store: {store.name} ({store.store_url})")
            
            # Process orders based on platform
            if store.platform == "shopify":
                logger.info("Using Shopify integration")
                # Call sync version or use event loop to run async functions
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    from app.services.analytics import update_shopify_orders, update_shopify_products
                    logger.info("Fetching orders from Shopify...")
                    loop.run_until_complete(update_shopify_orders(db, store, start_date))
                    logger.info("Fetching products from Shopify...")
                    loop.run_until_complete(update_shopify_products(db, store))
                    logger.info("Successfully updated Shopify data")
                except Exception as e:
                    logger.error(f"Error in Shopify data update: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    loop.close()
                
            # Count how many orders we have now
            order_count = db.query(models.Order).filter(models.Order.store_id == store_id).count()
            product_count = db.query(models.Product).filter(models.Product.store_id == store_id).count()
            logger.info(f"Store now has {order_count} orders and {product_count} products")
            
            # After updating data, analyze it
            logger.info("Queueing analysis task")
            analyze_sales_data.delay(store_id)
            
            return f"Updated store data: {order_count} orders, {product_count} products"
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating store data for {store_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"

@celery.task
def analyze_sales_data(store_id: str):
    """Analyze sales data for insights."""
    try:
        logger.info(f"Starting sales data analysis for store {store_id}")
        db = SessionLocal()
        try:
            import asyncio
            from app.services.analytics import analyze_store_performance
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Run the async function in a loop
                logger.info("Running store performance analysis...")
                results = loop.run_until_complete(analyze_store_performance(db, store_id))
                
                # Process results and create insights
                if results["status"] == "success":
                    # Here you could generate insights from the results
                    logger.info(f"Successfully analyzed sales data for store {store_id}")
                    logger.info(f"Summary: {results['summary']}")
                else:
                    logger.warning(f"Analysis returned non-success status: {results['status']}")
                    if "message" in results:
                        logger.warning(f"Message: {results['message']}")
            except Exception as e:
                logger.error(f"Error in analyze_store_performance: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                loop.close()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error analyzing sales data for {store_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())

@celery.task
def detect_hourly_anomalies():
    """Detect anomalies hourly for all stores."""
    try:
        logger.info("Starting detect_hourly_anomalies task")
        db = SessionLocal()
        try:
            stores = db.query(models.Store).filter(models.Store.is_active == True).all()
            logger.info(f"Found {len(stores)} active stores for anomaly detection")
            for store in stores:
                logger.info(f"Queueing anomaly detection for store: {store.name} ({store.id})")
                detect_anomalies_for_store.delay(str(store.id))
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in detect_hourly_anomalies: {e}")

@celery.task
def detect_anomalies_for_store(store_id: str):
    """Detect anomalies for a specific store."""
    try:
        logger.info(f"Starting anomaly detection for store {store_id}")
        db = SessionLocal()
        try:
            # Call the anomaly detection service
            import asyncio
            from app.services.anomaly_detection import detect_anomalies
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Set a lookback period of 30 days for anomaly detection
                logger.info("Running anomaly detection...")
                anomalies = loop.run_until_complete(detect_anomalies(db, store_id, lookback_days=30))
                logger.info(f"Detected {len(anomalies)} anomalies")
            finally:
                loop.close()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error detecting anomalies for {store_id}: {e}")

@celery.task
def generate_daily_reports():
    """Generate and send daily reports for all stores."""
    try:
        logger.info("Starting generate_daily_reports task")
        db = SessionLocal()
        try:
            # Get all active stores
            stores = db.query(models.Store).filter(models.Store.is_active == True).all()
            logger.info(f"Found {len(stores)} active stores for daily reports")
            
            # Generate reports for each store
            for store in stores:
                logger.info(f"Queueing report generation for store: {store.name} ({store.id})")
                generate_store_report.delay(str(store.id))
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in generate_daily_reports: {e}")

@celery.task
def generate_store_report(store_id: str):
    """Generate and send daily report for a specific store."""
    try:
        logger.info(f"Starting report generation for store {store_id}")
        db = SessionLocal()
        try:
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if not store:
                logger.error(f"Store not found: {store_id}")
                return
            
            # Get all users associated with this store
            users = db.query(models.User).join(
                models.store_user_association,
                models.User.id == models.store_user_association.c.user_id
            ).filter(
                models.store_user_association.c.store_id == store_id,
                models.User.is_active == True
            ).all()
            
            logger.info(f"Found {len(users)} users for store {store.name}")
            
            # Generate and send report to each user
            for user in users:
                # Check if user wants daily reports
                if (user.preferences and 
                    user.preferences.notification_preferences and 
                    user.preferences.notification_preferences.get("daily_summary", True)):
                    
                    logger.info(f"Generating report for user: {user.email}")
                    
                    # Use send_daily_report from reporting.py
                    import asyncio
                    from app.services.reporting import send_daily_report
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(send_daily_report(db, store_id, str(user.id)))
                        if success:
                            logger.info(f"Successfully sent report to {user.email}")
                        else:
                            logger.warning(f"Failed to send report to {user.email}")
                    finally:
                        loop.close()
                else:
                    logger.info(f"User {user.email} has disabled daily reports")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error generating report for {store_id}: {e}")
'''

# Write the new content to the file
with open(file_path, 'w') as f:
    f.write(new_content)

print(f"✅ Successfully updated {file_path}")
