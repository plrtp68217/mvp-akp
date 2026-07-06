from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.rule import Rule
from app.schemas.order import OrderCreate
from app.schemas.rule import RuleCreate, RuleUpdate
from app.services.registry import build_registry
from app.services.rule_engine import apply_rules


class RuleValidationError(ValueError):
    """Ссылка правила указывает на несуществующую переменную реестра."""


def validate_rule_variables(rule_data: RuleCreate, registry: dict) -> None:
    """Проверяет, что все variable/source/target из condition/action есть в реестре.

    variable/source — входы (что читаем из заказа). target — выход (куда пишем результат);
    он тоже обязан быть зарегистрированной переменной, чтобы фронтенд знал её label/type
    и мог корректно отобразить результат прогона правил. Бросает RuleValidationError —
    роутер отдаст 422.
    """
    known = set(registry.keys())
    referenced: set[str] = set()

    for cond in rule_data.condition.conditions:
        referenced.add(cond.variable)
    for act in rule_data.action.actions:
        referenced.add(act.target)
        if act.source is not None:
            referenced.add(act.source)

    unknown = sorted(referenced - known)
    if unknown:
        raise RuleValidationError(
            "Неизвестные переменные: " + ", ".join(unknown)
        )


class RuleService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Rule]:
        query = select(Rule)
        if active_only:
            query = query.where(Rule.is_active == True)
        query = query.order_by(Rule.priority).offset(skip).limit(limit)
        return self.db.execute(query).scalars().all()

    def get_by_id(self, rule_id: int) -> Optional[Rule]:
        return self.db.get(Rule, rule_id)

    def create(self, rule_data: RuleCreate) -> Rule:
        # Валидация ссылок на переменные до записи в БД.
        validate_rule_variables(rule_data, build_registry(self.db))

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

    def process_order(self, order_data: OrderCreate) -> Tuple[Order, dict]:
        """Создаёт заказ, прогоняет активные правила, возвращает (order, applied_actions)."""
        order = Order(
            total=order_data.total,
            status=order_data.status,
            items_count=order_data.items_count,
            metadata_json=order_data.metadata,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        registry = build_registry(self.db)
        active_rules = self.db.execute(
            select(Rule).where(Rule.is_active == True)
        ).scalars().all()

        applied_actions = apply_rules(order, active_rules, registry)
        return order, applied_actions
