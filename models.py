from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    phone           = Column(String(20), unique=True, nullable=False, index=True)
    name            = Column(String(100), nullable=True)
    default_address = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Float, nullable=False)
    stock       = Column(Integer, default=0)
    category    = Column(String(100), nullable=True)
    image_url   = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    items            = Column(JSON, nullable=False)   # [{"product_id", "name", "qty", "price"}]
    total            = Column(Float, nullable=False)
    delivery_address = Column(Text, nullable=True)
    status           = Column(String(50), default="pendiente_pago")
    payment_id       = Column(String(200), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")


# Conexión
engine       = create_engine(settings.database_url)
