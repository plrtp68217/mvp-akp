"""Реестр переменных движка правил.

Гибридная модель переменных:
  * системные — прямые поля orders (описаны здесь, в коде);
  * кастомные — заводятся админом, хранятся в custom_variables, значения берутся
    из orders.metadata_json по source_path.

Модуль намеренно не зависит от FastAPI/HTTP — только SQLAlchemy Session для чтения
кастомных переменных. Это позволяет тестировать движок как чистый Python.
"""
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.custom_variable import CustomVariable

# Системные переменные — прямые поля orders. Меняются только разработчиком.
# resolver: callable(order) -> value
SYSTEM_VARIABLES: dict[str, dict] = {
    "total": {
        "label": "Сумма заказа",
        "type": "number",
        "enum": None,
        "resolver": lambda order: order.total,
    },
    "status": {
        "label": "Статус заказа",
        "type": "string",
        "enum": None,
        "resolver": lambda order: order.status,
    },
    "items_count": {
        "label": "Количество товаров",
        "type": "number",
        "enum": None,
        "resolver": lambda order: order.items_count,
    },
}


def get_nested(data: Any, path: str) -> Optional[Any]:
    """Достаёт значение из вложенного dict по точечному пути (customer.loyalty.level).

    Возвращает None, если путь не разрешается (нет ключа, не dict по дороге и т.п.).
    """
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def coerce_value(raw: Any, value_type: str) -> Optional[Any]:
    """Приводит сырое значение из metadata_json к заявленному типу.

    Не доверяем сырым данным: при невозможности привести — возвращаем None,
    чтобы движок трактовал переменную как отсутствующую, а не падал.
    """
    if raw is None:
        return None

    try:
        if value_type == "number":
            if isinstance(raw, bool):
                # bool — подкласс int, но как число трактовать его не хотим
                return None
            return float(raw)
        if value_type == "boolean":
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                low = raw.strip().lower()
                if low in ("true", "1", "yes"):
                    return True
                if low in ("false", "0", "no"):
                    return False
                return None
            if isinstance(raw, (int, float)):
                return bool(raw)
            return None
        if value_type == "string":
            return str(raw)
    except (TypeError, ValueError):
        return None

    return None


def _custom_resolver(
    source_path: Optional[str], value_type: str
) -> Callable[[Any], Optional[Any]]:
    """Строит resolver для кастомной переменной (замыкание по пути и типу).

    Без source_path (выходная переменная-target) читать неоткуда — resolver всегда
    возвращает None, поэтому в context такая переменная не попадает и как вход не
    используется, но остаётся в реестре (валидна как action.target).
    """

    def resolver(order: Any) -> Optional[Any]:
        if not source_path:
            return None
        raw = get_nested(order.metadata_json or {}, source_path)
        return coerce_value(raw, value_type)

    return resolver


def build_registry(db: Session) -> dict:
    """Возвращает {var_key: {"label", "type", "enum", "resolver": callable(order)->value}}.

    Системные переменные + активные кастомные (мягко удалённые исключены).
    """
    registry: dict[str, dict] = {}

    for key, meta in SYSTEM_VARIABLES.items():
        registry[key] = dict(meta)

    custom_vars = db.query(CustomVariable).filter(CustomVariable.is_active == True).all()
    for cv in custom_vars:
        registry[cv.key] = {
            "label": cv.label,
            "type": cv.value_type,
            "enum": cv.enum_values,
            "resolver": _custom_resolver(cv.source_path, cv.value_type),
        }

    return registry
