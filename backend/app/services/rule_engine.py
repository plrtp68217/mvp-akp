"""Движок правил.

Работает на JSON-структурах condition/action (не строковый DSL, без eval()).
Чистый Python: не импортирует FastAPI и ничего не знает про HTTP/БД — на вход
принимает уже построенный registry (dict с resolver'ами) и объект заказа.

Контракты (см. AGENTS.md):
    build_context(order, registry)     -> dict {var_key: value}
    evaluate_condition(condition, ctx) -> bool
    execute_actions(action, ctx)       -> dict {target: value}
    apply_rules(order, rules, registry) -> dict (объединённый результат)
"""
import operator
from typing import Any, Callable

# Операторы сравнения для condition — жёстко зашиты, не редактируются админом.
OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

# Операции действий — фиксированный enum.
ACTION_OPS = frozenset({"set", "add", "subtract", "percent_of", "multiply"})


def build_context(order: Any, registry: dict) -> dict:
    """Возвращает {var_key: значение} для конкретного заказа.

    Отсутствующая/ошибочная переменная (resolver кинул или вернул None) в context
    не попадает — движок трактует её как «нет значения».
    """
    context: dict[str, Any] = {}
    for key, meta in registry.items():
        try:
            value = meta["resolver"](order)
        except Exception:
            continue
        if value is not None:
            context[key] = value
    return context


def evaluate_condition(condition: dict, context: dict) -> bool:
    """Проверяет один condition-блок (плоский AND/OR) против context.

    Отсутствие переменной в context трактуется как False (не KeyError).
    Пустой список условий: AND -> True, OR -> False (семантика all()/any()).
    Неизвестный оператор сравнения -> элемент False (правило просто не срабатывает).
    """
    if not condition:
        return False

    logical = str(condition.get("operator", "AND")).upper()
    items = condition.get("conditions", []) or []

    results: list[bool] = []
    for item in items:
        variable = item.get("variable")
        op_symbol = item.get("op")
        expected = item.get("value")

        if variable not in context:
            results.append(False)
            continue

        compare = OPERATORS.get(op_symbol)
        if compare is None:
            results.append(False)
            continue

        try:
            results.append(bool(compare(context[variable], expected)))
        except TypeError:
            # Несравнимые типы (напр. число с None/строкой) -> условие не выполнено.
            results.append(False)

    if logical == "OR":
        return any(results)
    return all(results)


def _to_number(value: Any):
    """Пытается привести операнд к числу; None, если не число (bool отвергаем)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def execute_actions(action: dict, context: dict) -> dict:
    """Выполняет action-блок, возвращает {target: значение}.

    Операнд для арифметики берётся из context[source], если задан source,
    иначе из уже накопленного результата по target (по умолчанию 0).
    Некорректные (не числовые) операнды не роняют движок — действие пропускается.
    """
    result: dict[str, Any] = {}
    if not action:
        return result

    for item in action.get("actions", []) or []:
        target = item.get("target")
        op = item.get("op")
        if target is None or op not in ACTION_OPS:
            continue

        value = item.get("value")
        source = item.get("source")

        if op == "set":
            # set: либо литерал value, либо значение переменной source.
            result[target] = context.get(source) if source is not None else value
            continue

        # Арифметика: operand (op) value.
        if source is not None:
            operand = _to_number(context.get(source))
        else:
            operand = _to_number(result.get(target, 0))
        rhs = _to_number(value)

        if operand is None or rhs is None:
            continue

        if op == "add":
            result[target] = operand + rhs
        elif op == "subtract":
            result[target] = operand - rhs
        elif op == "multiply":
            result[target] = operand * rhs
        elif op == "percent_of":
            result[target] = operand * rhs / 100

    return result


def apply_rules(order: Any, rules: list, registry: dict) -> dict:
    """Прогоняет все правила по приоритету, возвращает объединённый результат.

    Порядок: по возрастанию priority (меньше = раньше). Конфликт двух правил на
    один target разрешается перезаписью — последнее применённое (больший номер
    priority) побеждает (dict.update).
    """
    context = build_context(order, registry)
    result: dict[str, Any] = {}

    for rule in sorted(rules, key=lambda r: getattr(r, "priority", 0)):
        if evaluate_condition(rule.condition, context):
            result.update(execute_actions(rule.action, context))

    return result
