from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.core.connection import Base

class Rule(Base):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    condition = Column(String, nullable=False)   # например: "order.total > 1000"
    action = Column(String, nullable=False)      # например: "discount = 10"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())