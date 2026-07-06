from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.custom_variable import CustomVariable
from app.models.rule import Rule
from app.schemas.variable import CustomVariableCreate, CustomVariableUpdate


class VariableConflictError(ValueError):
    """Кастомная переменная с таким key уже существует."""


class VariableInUseError(ValueError):
    """Переменную нельзя жёстко удалить — на неё ссылаются правила."""


class VariableService:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> List[CustomVariable]:
        return self.db.execute(
            select(CustomVariable).where(CustomVariable.is_active == True)
        ).scalars().all()

    def get_by_key(self, key: str) -> Optional[CustomVariable]:
        return self.db.execute(
            select(CustomVariable).where(CustomVariable.key == key)
        ).scalars().first()

    def create(self, data: CustomVariableCreate) -> CustomVariable:
        if self.get_by_key(data.key) is not None:
            raise VariableConflictError(f"Переменная '{data.key}' уже существует")

        variable = CustomVariable(**data.model_dump())
        self.db.add(variable)
        self.db.commit()
        self.db.refresh(variable)
        return variable

    def update(self, key: str, data: CustomVariableUpdate) -> Optional[CustomVariable]:
        variable = self.get_by_key(key)
        if not variable:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(variable, field, value)

        self.db.commit()
        self.db.refresh(variable)
        return variable

    def find_rules_using(self, key: str) -> List[Rule]:
        """Правила, ссылающиеся на переменную в condition (variable) или action (source).

        JSON хранится в БД; проверку делаем в Python, чтобы не зависеть от диалекта.
        """
        used: List[Rule] = []
        for rule in self.db.execute(select(Rule)).scalars().all():
            condition = rule.condition or {}
            action = rule.action or {}
            in_condition = any(
                c.get("variable") == key for c in condition.get("conditions", [])
            )
            in_action = any(
                a.get("source") == key or a.get("target") == key
                for a in action.get("actions", [])
            )
            if in_condition or in_action:
                used.append(rule)
        return used

    def soft_delete(self, key: str) -> Optional[CustomVariable]:
        """Мягкое удаление (is_active=False) — не ломает правила, ссылающиеся на переменную."""
        variable = self.get_by_key(key)
        if not variable:
            return None
        variable.is_active = False
        self.db.commit()
        self.db.refresh(variable)
        return variable

    def hard_delete(self, key: str) -> bool:
        """Жёсткое удаление; запрещено, если переменную используют правила."""
        variable = self.get_by_key(key)
        if not variable:
            return False
        if self.find_rules_using(key):
            raise VariableInUseError(
                f"Переменная '{key}' используется в правилах — используйте мягкое удаление"
            )
        self.db.delete(variable)
        self.db.commit()
        return True
