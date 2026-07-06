from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

ValueType = Literal["number", "string", "boolean"]

# Техническое имя переменной: латиница/цифры/подчёркивание, не с цифры.
KEY_PATTERN = r"^[a-z_][a-z0-9_]*$"


class CustomVariableBase(BaseModel):
    key: str = Field(..., pattern=KEY_PATTERN, description="Техническое имя")
    label: str
    value_type: ValueType
    source_path: Optional[str] = Field(
        None,
        description="Путь в orders.metadata_json (пусто для выходных переменных-target)",
    )
    enum_values: Optional[List[str]] = None

    @model_validator(mode="after")
    def _enum_only_for_string(self):
        if self.enum_values is not None and self.value_type != "string":
            raise ValueError("enum_values допустимы только при value_type == 'string'")
        return self


class CustomVariableCreate(CustomVariableBase):
    pass


class CustomVariableUpdate(BaseModel):
    label: Optional[str] = None
    source_path: Optional[str] = None
    enum_values: Optional[List[str]] = None
    is_active: Optional[bool] = None


class CustomVariableResponse(CustomVariableBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VariableListItem(BaseModel):
    """Унифицированный элемент объединённого списка system + custom для UI."""

    key: str
    label: str
    value_type: ValueType
    enum: Optional[List[str]] = None
    source: Literal["system", "custom"]


class VariableList(BaseModel):
    variables: List[VariableListItem]
    total: int
