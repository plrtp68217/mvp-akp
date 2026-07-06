from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    total: float = Field(..., ge=0, description="Сумма заказа (системная переменная)")
    status: str = "pending"
    items_count: int = Field(0, ge=0, description="Количество товаров")
    # Источник значений для кастомных переменных.
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderResponse(BaseModel):
    id: int
    total: float
    status: str
    items_count: int
    metadata_json: Dict[str, Any]
    created_at: datetime
    # Результат применённых движком действий, напр. {"discount": 600}.
    applied_actions: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
