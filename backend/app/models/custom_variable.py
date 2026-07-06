from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.connection import Base


class CustomVariable(Base):
    __tablename__ = "custom_variables"

    id = Column(Integer, primary_key=True, index=True)
    # Техническое имя, используется в condition/action JSON (regex ^[a-z_][a-z0-9_]*$)
    key = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False)          # человекочитаемое имя для UI
    value_type = Column(String, nullable=False)     # number | string | boolean
    # Путь внутри orders.metadata_json (точечная нотация: customer.loyalty.level).
    # Необязателен: выходные переменные (используемые только как action.target)
    # ниоткуда не читаются, поэтому source_path у них отсутствует.
    source_path = Column(String, nullable=True)
    # Ограниченный список допустимых строковых значений (только для value_type == string)
    enum_values = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)       # мягкое включение/отключение
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
