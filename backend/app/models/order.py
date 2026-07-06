from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.sql import func

from app.core.connection import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    total = Column(Float, nullable=False, default=0)              # системная переменная
    status = Column(String(50), default="pending")               # системная переменная
    items_count = Column(Integer, nullable=False, default=0)     # системная переменная
    # Расширяемое хранилище для кастомных данных заказа
    # (источник значений для кастомных переменных).
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=func.now())
