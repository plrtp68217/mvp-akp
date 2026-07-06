from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.connection import Base


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # {"operator": "AND"|"OR", "conditions": [{"variable", "op", "value"}, ...]}
    condition = Column(JSON, nullable=False)
    # {"actions": [{"target", "op", "value"?, "source"?}, ...]}
    action = Column(JSON, nullable=False)
    priority = Column(Integer, nullable=False, default=100)  # меньше = раньше
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
