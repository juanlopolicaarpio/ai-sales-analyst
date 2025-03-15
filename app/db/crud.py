from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_

from app.db import models


# User CRUD operations
async def get_user(db: AsyncSession, user_id: str):
    """Get a user by ID."""
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str):
    """Get a user by email."""
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalars().first()

async def get_user_by_slack_id(db: AsyncSession, slack_id: str):
    """Get a user by Slack ID."""
    result = await db.execute(select(models.User).where(models.User.slack_user_id == slack_id))
    return result.scalars().first()

async def get_user_by_whatsapp(db: AsyncSession, whatsapp_number: str):
    """Get a user by WhatsApp number."""
    result = await db.execute(select(models.User).where(models.User.whatsapp_number == whatsapp_number))
    return result.scalars().first()

async def create_user(db: AsyncSession, user_data: Dict[str, Any]):
    """Create a new user."""
    db_user = models.User(**user_data)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, user_id: str, user_data: Dict[str, Any]):
    """Update a user."""
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    db_user = result.scalars().first()
    if db_user:
        for key, value in user_data.items():
            setattr(db_user, key, value)
        await db.commit()
        await db.refresh(db_user)
    return db_user


# Store CRUD operations
async def get_store(db: AsyncSession, store_id: str):
    """Get a store by ID."""
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    return result.scalars().first()

async def get_stores_by_user(db: AsyncSession, user_id: str):
    """Get all stores for a user."""
    result = await db.execute(
        select(models.Store)
        .join(models.store_user_association)
        .where(models.store_user_association.c.user_id == user_id)
    )
    return result.scalars().all()

async def create_store(db: AsyncSession, store_data: Dict[str, Any]):
    """Create a new store."""
    db_store = models.Store(**store_data)
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    return db_store

async def update_store(db: AsyncSession, store_id: str, store_data: Dict[str, Any]):
    """Update a store."""
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    db_store = result.scalars().first()
    if db_store:
        for key, value in store_data.items():
            setattr(db_store, key, value)
        await db.commit()
        await db.refresh(db_store)
    return db_store


# Order CRUD operations
async def create_order(db: AsyncSession, order_data: Dict[str, Any]):
    """Create a new order."""
    db_order = models.Order(**order_data)
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    return db_order

async def get_order_by_platform_id(db: AsyncSession, store_id: str, platform_order_id: str):
    """Get an order by platform ID."""
    result = await db.execute(
        select(models.Order).where(
            and_(
                models.Order.store_id == store_id,
                models.Order.platform_order_id == platform_order_id
            )
        )
    )
    return result.scalars().first()

async def get_orders_by_date_range(
    db: AsyncSession, 
    store_id: str, 
    start_date: datetime, 
    end_date: datetime
):
    """Get orders within a date range."""
    result = await db.execute(
        select(models.Order).where(
            and_(
                models.Order.store_id == store_id,
                models.Order.order_date >= start_date,
                models.Order.order_date <= end_date
            )
        )
    )
    return result.scalars().all()


# Product CRUD operations
async def create_product(db: AsyncSession, product_data: Dict[str, Any]):
    """Create a new product."""
    db_product = models.Product(**product_data)
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

async def get_product_by_platform_id(db: AsyncSession, store_id: str, platform_product_id: str):
    """Get a product by platform ID."""
    result = await db.execute(
        select(models.Product).where(
            and_(
                models.Product.store_id == store_id,
                models.Product.platform_product_id == platform_product_id
            )
        )
    )
    return result.scalars().first()

async def update_product(db: AsyncSession, product_id: str, product_data: Dict[str, Any]):
    """Update a product."""
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    db_product = result.scalars().first()
    if db_product:
        for key, value in product_data.items():
            setattr(db_product, key, value)
        await db.commit()
        await db.refresh(db_product)
    return db_product


# Message CRUD operations
async def create_message(db: AsyncSession, message_data: Dict[str, Any]):
    """Create a new message."""
    db_message = models.Message(**message_data)
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def get_user_messages(db: AsyncSession, user_id: str, limit: int = 10):
    """Get recent messages for a user."""
    result = await db.execute(
        select(models.Message)
        .where(models.Message.user_id == user_id)
        .order_by(models.Message.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# Insight CRUD operations
async def create_insight(db: AsyncSession, insight_data: Dict[str, Any]):
    """Create a new sales insight."""
    db_insight = models.SalesInsight(**insight_data)
    db.add(db_insight)
    await db.commit()
    await db.refresh(db_insight)
    return db_insight

async def get_recent_insights(db: AsyncSession, store_id: str, days: int = 7, limit: int = 20):
    """Get recent insights for a store."""
    since_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(models.SalesInsight)
        .where(
            and_(
                models.SalesInsight.store_id == store_id,
                models.SalesInsight.created_at >= since_date
            )
        )
        .order_by(models.SalesInsight.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def get_unsent_insights(db: AsyncSession, store_id: str):
    """Get insights that haven't been sent yet."""
    result = await db.execute(
        select(models.SalesInsight)
        .where(
            and_(
                models.SalesInsight.store_id == store_id,
                models.SalesInsight.is_sent == False
            )
        )
        .order_by(models.SalesInsight.created_at.desc())
    )
    return result.scalars().all()

async def mark_insight_as_sent(db: AsyncSession, insight_id: str):
    """Mark an insight as sent."""
    result = await db.execute(select(models.SalesInsight).where(models.SalesInsight.id == insight_id))
    db_insight = result.scalars().first()
    if db_insight:
        db_insight.is_sent = True
        await db.commit()
        await db.refresh(db_insight)
    return db_insight

async def update_insight_feedback(db: AsyncSession, insight_id: str, feedback: str):
    """Update insight feedback."""
    result = await db.execute(select(models.SalesInsight).where(models.SalesInsight.id == insight_id))
    db_insight = result.scalars().first()
    if db_insight:
        db_insight.feedback = feedback
        await db.commit()
        await db.refresh(db_insight)
    return db_insight