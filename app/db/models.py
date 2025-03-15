import uuid
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, JSON, Enum, Table
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

# Association tables
store_user_association = Table(
    'store_user_association',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id')),
    Column('store_id', UUID(as_uuid=True), ForeignKey('stores.id'))
)


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Messaging Identifiers
    slack_user_id = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    
    # Relationships
    messages = relationship("Message", back_populates="user")
    stores = relationship("Store", secondary=store_user_association, back_populates="users")
    preferences = relationship("UserPreference", back_populates="user", uselist=False)


class UserPreference(Base):
    """User preferences for notifications and reports."""
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    notification_channel = Column(String, default="slack")  # slack, whatsapp, email
    daily_report_time = Column(String, default="17:00")
    timezone = Column(String, default="UTC")
    notification_preferences = Column(JSON, default=lambda: {
        "sales_alerts": True,
        "anomaly_detection": True,
        "daily_summary": True
    })
    
    # Relationships
    user = relationship("User", back_populates="preferences")


class Store(Base):
    """Store model for e-commerce platform integration."""
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    platform = Column(String, nullable=False)  # shopify, woocommerce, etc.
    store_url = Column(String, nullable=False)
    api_key = Column(String, nullable=True)
    api_secret = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    users = relationship("User", secondary=store_user_association, back_populates="stores")
    orders = relationship("Order", back_populates="store")
    products = relationship("Product", back_populates="store")


class Order(Base):
    """Order model for e-commerce orders."""
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"))
    platform_order_id = Column(String, nullable=False)
    order_number = Column(String, nullable=False)
    order_status = Column(String, nullable=False)
    customer_name = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    total_price = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    order_date = Column(DateTime, nullable=False)
    order_data = Column(JSON, nullable=False)  # Raw order data
    
    # Relationships
    store = relationship("Store", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    """Order item model for products in orders."""
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    platform_product_id = Column(String, nullable=False)
    product_name = Column(String, nullable=False)
    variant_name = Column(String, nullable=True)
    sku = Column(String, nullable=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")


class Product(Base):
    """Product model for e-commerce products."""
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"))
    platform_product_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sku = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    compare_at_price = Column(Float, nullable=True)
    inventory_quantity = Column(Integer, nullable=True)
    product_type = Column(String, nullable=True)
    vendor = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    product_data = Column(JSON, nullable=False)  # Raw product data
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")


class Message(Base):
    """Message model for chat interactions."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    channel = Column(String, nullable=False)  # slack, whatsapp, email
    direction = Column(String, nullable=False)  # incoming, outgoing
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, nullable=True)  # Additional data about the message (renamed from 'metadata')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="messages")


class SalesInsight(Base):
    """Model for storing generated sales insights and anomalies."""
    __tablename__ = "sales_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"))
    insight_type = Column(String, nullable=False)  # daily_summary, anomaly, trend
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    metrics = Column(JSON, nullable=True)  # Related metrics
    is_anomaly = Column(Boolean, default=False)
    severity = Column(Integer, nullable=True)  # 1-5, 5 being most severe
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    insight_date = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    feedback = Column(String, nullable=True)  # User feedback on insight