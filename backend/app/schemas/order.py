from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class OrderItem(BaseModel):
    product_name: str
    quantity: int
    price: float

class OrderCreate(BaseModel):
    client_id: int
    client_type: Optional[str] = None
    items: List[OrderItem]
    shipping_address: str

class OrderResponse(BaseModel):
    id: int
    client_id: int
    total_amount: float
    discount: float = 0
    final_amount: float
    status: str
    shipping_address: str
    created_at: datetime
    applied_rules: Optional[List[str]] = None
    
    class Config:
        from_attributes = True