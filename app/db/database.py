import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import get_database_url

# Get database URL from config
database_url = get_database_url()

# Convert to async URL if needed
if database_url.startswith("postgresql://"):
    async_database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    async_database_url = database_url

# Create async engine
engine = create_async_engine(
    async_database_url,
    echo=False,
    future=True,
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create declarative base for models
Base = declarative_base()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields db sessions
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise