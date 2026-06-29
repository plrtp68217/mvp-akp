from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.connection import Base

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False)
    client_type = Column(String(50), nullable=True)
    total_amount = Column(Float, nullable=False, default=0)
    discount = Column(Float, default=0)
    final_amount = Column(Float, nullable=False, default=0)
    status = Column(String(50), default="pending")
    shipping_address = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    order = relationship("Order", back_populates="items")