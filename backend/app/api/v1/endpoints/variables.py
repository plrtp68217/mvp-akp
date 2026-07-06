from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.connection import get_db
from app.schemas.variable import (
    CustomVariableCreate,
    CustomVariableResponse,
    VariableList,
    VariableListItem,
)
from app.services.registry import SYSTEM_VARIABLES
from app.services.variable_service import VariableConflictError, VariableService

router = APIRouter(prefix="/variables", tags=["variables"])


@router.post("/", response_model=CustomVariableResponse, status_code=201)
def create_variable(
    variable: CustomVariableCreate,
    db: Session = Depends(get_db),
):
    """Завести кастомную переменную (значение берётся из orders.metadata_json)."""
    service = VariableService(db)
    try:
        return service.create(variable)
    except VariableConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/", response_model=VariableList)
def list_variables(db: Session = Depends(get_db)):
    """Объединённый список переменных: системные + активные кастомные."""
    items: list[VariableListItem] = []

    for key, meta in SYSTEM_VARIABLES.items():
        items.append(
            VariableListItem(
                key=key,
                label=meta["label"],
                value_type=meta["type"],
                enum=meta.get("enum"),
                source="system",
            )
        )

    service = VariableService(db)
    for cv in service.list_active():
        items.append(
            VariableListItem(
                key=cv.key,
                label=cv.label,
                value_type=cv.value_type,
                enum=cv.enum_values,
                source="custom",
            )
        )

    return VariableList(variables=items, total=len(items))
