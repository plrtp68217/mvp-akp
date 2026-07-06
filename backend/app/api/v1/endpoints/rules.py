# app/api/rules.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.connection import get_db
from app.schemas.rule import RuleCreate, RuleUpdate, RuleResponse, RuleList
from app.services.rule_service import RuleService, RuleValidationError

router = APIRouter(prefix="/rules", tags=["rules"])

@router.post("/", response_model=RuleResponse, status_code=201)
def create_rule(
    rule: RuleCreate,
    db: Session = Depends(get_db)
):
    """Создать новое правило"""
    service = RuleService(db)
    try:
        return service.create(rule)
    except RuleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.get("/", response_model=RuleList)
def get_rules(
    skip: int = Query(0, ge=0, description="Пропустить N записей"),
    limit: int = Query(100, ge=1, le=1000, description="Количество записей"),
    active_only: bool = Query(False, description="Только активные правила"),
    db: Session = Depends(get_db)
):
    """Получить список всех правил"""
    service = RuleService(db)
    rules = service.get_all(skip=skip, limit=limit, active_only=active_only)
    return {
        "rules": rules,
        "total": len(rules)
    }

@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """Получить правило по ID"""
    service = RuleService(db)
    rule = service.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return rule

@router.patch("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: int,
    rule_update: RuleUpdate,
    db: Session = Depends(get_db)
):
    """Обновить правило"""
    service = RuleService(db)
    rule = service.update(rule_id, rule_update)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return rule

@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """Удалить правило"""
    service = RuleService(db)
    if not service.delete(rule_id):
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return None

@router.post("/{rule_id}/toggle", response_model=RuleResponse)
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """Включить/выключить правило"""
    service = RuleService(db)
    rule = service.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    
    rule_update = RuleUpdate(is_active=not rule.is_active)
    return service.update(rule_id, rule_update)