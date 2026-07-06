from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

# Операторы сравнения и операции действий — фиксированный enum, зашитый в коде.
ConditionOp = Literal[">", "<", ">=", "<=", "==", "!="]
LogicalOp = Literal["AND", "OR"]
ActionOp = Literal["set", "add", "subtract", "percent_of", "multiply"]


class ConditionItem(BaseModel):
    variable: str = Field(..., description="Ключ переменной из реестра")
    op: ConditionOp
    value: Any


class ConditionBlock(BaseModel):
    operator: LogicalOp = "AND"
    conditions: List[ConditionItem] = Field(default_factory=list)


class ActionItem(BaseModel):
    target: str = Field(..., description="Куда пишем результат")
    op: ActionOp
    value: Optional[Any] = None
    source: Optional[str] = Field(
        None, description="Ключ переменной-операнда из реестра (для арифметики)"
    )


class ActionBlock(BaseModel):
    actions: List[ActionItem] = Field(default_factory=list)


class RuleBase(BaseModel):
    name: str
    condition: ConditionBlock
    action: ActionBlock
    priority: int = 100
    is_active: bool = True


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    condition: Optional[ConditionBlock] = None
    action: Optional[ActionBlock] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class RuleResponse(RuleBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RuleList(BaseModel):
    rules: List[RuleResponse]
    total: int
