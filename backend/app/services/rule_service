# app/services/rule_service.py
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleUpdate

class RuleService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Rule]:
        query = select(Rule)
        if active_only:
            query = query.where(Rule.is_active == True)
        query = query.offset(skip).limit(limit)
        return self.db.execute(query).scalars().all()
    
    def get_by_id(self, rule_id: int) -> Optional[Rule]:
        return self.db.get(Rule, rule_id)
    
    def create(self, rule_data: RuleCreate) -> Rule:
        rule = Rule(**rule_data.model_dump())
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def update(self, rule_id: int, rule_data: RuleUpdate) -> Optional[Rule]:
        rule = self.get_by_id(rule_id)
        if not rule:
            return None
        
        update_data = rule_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)
        
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def delete(self, rule_id: int) -> bool:
        rule = self.get_by_id(rule_id)
        if not rule:
            return False
        
        self.db.delete(rule)
        self.db.commit()
        return True