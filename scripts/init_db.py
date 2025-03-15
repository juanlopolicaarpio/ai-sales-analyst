#!/usr/bin/env python3
"""
Database initialization script for development and testing.
This script creates tables and adds sample data to the database.
"""

import os
import sys
import asyncio
import datetime
import uuid
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

from app.config import settings
from app.db.database import Base
from app.db.models import User, Store, UserPreference, Order, Product, OrderItem, Message, SalesInsight


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def init_db():
    """Initialize the database with tables and sample data."""
    from app.config import settings, get_database_url
    
    # Get database URL
    db_url = get_database_url()
    
    # Convert to async URL if needed
    if db_url.startswith("postgresql://"):
        async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = db_url
    
    print(f"Connecting to database: {async_db_url}")
    
    # Create async engine
    engine = create_async_engine(async_db_url)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Add sample data
    async with async_session() as session:
        # Create a test user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="test@example.com",
            hashed_password=pwd_context.hash("password123"),
            full_name="Test User",
            is_active=True,
            is_superuser=False,
            slack_user_id="U12345678",
            whatsapp_number="+1234567890"
        )
        session.add(user)
        await session.flush()
        
        # Create user preferences
        preferences = UserPreference(
            user_id=user_id,
            notification_channel="slack",
            daily_report_time="17:00",
            timezone="America/New_York",
            notification_preferences={
                "sales_alerts": True,
                "anomaly_detection": True,
                "daily_summary": True
            }
        )
        session.add(preferences)
        
        # Create a test store
        store_id = uuid.uuid4()
        store = Store(
            id=store_id,
            name="Test Shopify Store",
            platform="shopify",
            store_url="test-store.myshopify.com",
            api_key="test_api_key",
            api_secret="test_api_secret",
            access_token="test_access_token",
            is_active=True
        )
        session.add(store)
        await session.flush()
        
        # Associate user with store
        stmt = """
        INSERT INTO store_user_association (user_id, store_id)
        VALUES (:user_id, :store_id)
        """
        await session.execute(stmt, {"user_id": user_id, "store_id": store_id})
        
        # Create sample products
        products = []
        product_data = [
            {"name": "Premium T-Shirt", "price": 29.99, "inventory": 100},
            {"name": "Wireless Headphones", "price": 89.99, "inventory": 50},
            {"name": "Phone Case", "price": 19.99, "inventory": 200},
            {"name": "Fitness Tracker", "price": 129.99, "inventory": 75},
            {"name": "Sunglasses", "price": 59.99, "inventory": 150}
        ]
        
        for i, p_data in enumerate(product_data):
            product = Product(
                id=uuid.uuid4(),
                store_id=store_id,
                platform_product_id=f"prod_{i+1}",
                name=p_data["name"],
                description=f"Description for {p_data['name']}",
                sku=f"SKU{i+1}",
                price=p_data["price"],
                inventory_quantity=p_data["inventory"],
                product_type="Clothing" if "Shirt" in p_data["name"] else "Accessories",
                vendor="Test Vendor",
                tags="sample",
                is_active=True,
                product_data={"id": f"prod_{i+1}", "title": p_data["name"]},
                created_at=datetime.datetime.utcnow()
            )
            session.add(product)
            products.append(product)
        
        await session.flush()
        
        # Create sample orders
        for i in range(1, 21):  # 20 sample orders
            order_date = datetime.datetime.utcnow() - datetime.timedelta(days=i % 10)
            order_id = uuid.uuid4()
            order = Order(
                id=order_id,
                store_id=store_id,
                platform_order_id=f"order_{i}",
                order_number=f"#{1000+i}",
                order_status="paid",
                customer_name=f"Customer {i}",
                customer_email=f"customer{i}@example.com",
                total_price=round(99.99 + i * 10, 2),
                currency="USD",
                order_date=order_date,
                order_data={"id": f"order_{i}", "number": f"#{1000+i}"}
            )
            session.add(order)
            await session.flush()
            
            # Add 1-3 products to each order
            for j in range(min(3, (i % 3) + 1)):
                product = products[(i + j) % len(products)]
                item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    product_id=product.id,
                    platform_product_id=product.platform_product_id,
                    product_name=product.name,
                    variant_name="Default",
                    sku=product.sku,
                    quantity=i % 3 + 1,
                    price=product.price
                )
                session.add(item)
        
        # Create sample messages
        message_data = [
            {"direction": "incoming", "content": "What were my sales yesterday?"},
            {"direction": "outgoing", "content": "Your sales yesterday were $1,234.56 from 12 orders."},
            {"direction": "incoming", "content": "Show me my top products"},
            {"direction": "outgoing", "content": "Here are your top products: 1. Premium T-Shirt ($599.80), 2. Wireless Headphones ($449.95), 3. Phone Case ($299.85)"}
        ]
        
        for i, m_data in enumerate(message_data):
            message = Message(
                id=uuid.uuid4(),
                user_id=user_id,
                channel="slack",
                direction=m_data["direction"],
                content=m_data["content"],
                metadata={"timestamp": datetime.datetime.utcnow().isoformat()},
                created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=i)
            )
            session.add(message)
        
        # Create sample insights
        insight_data = [
            {
                "type": "daily_summary",
                "title": "Daily Sales Summary",
                "description": "Yesterday you had 8 orders totaling $876.43, which is 12% higher than the previous day.",
                "is_anomaly": False
            },
            {
                "type": "anomaly",
                "title": "Unusual Sales Drop",
                "description": "Sales on Tuesday were 35% lower than average for that day of the week.",
                "is_anomaly": True,
                "severity": 4
            },
            {
                "type": "trend",
                "title": "Rising AOV",
                "description": "Your average order value has increased by 15% over the past week.",
                "is_anomaly": False
            }
        ]
        
        for i, ins_data in enumerate(insight_data):
            insight = SalesInsight(
                id=uuid.uuid4(),
                store_id=store_id,
                insight_type=ins_data["type"],
                title=ins_data["title"],
                description=ins_data["description"],
                metrics={"value": 100, "change": 0.12},
                is_anomaly=ins_data["is_anomaly"],
                severity=ins_data.get("severity", 1),
                insight_date=datetime.datetime.utcnow() - datetime.timedelta(days=i),
                is_sent=True
            )
            session.add(insight)
        
        # Commit all changes
        await session.commit()
    
    print("Database initialized with sample data")


if __name__ == "__main__":
    asyncio.run(init_db())