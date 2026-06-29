from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class RuleBase(BaseModel):
    name: str
    condition: str = Field(..., description="Например: order.total > 1000")
    action: str = Field(..., description="Например: discount = 10")
    is_active: bool = True

class RuleCreate(RuleBase):
    pass

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    condition: Optional[str] = None
    action: Optional[str] = None
    is_active: Optional[bool] = None

class RuleResponse(RuleBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class RuleList(BaseModel):
    rules: list[RuleResponse]
    total: int