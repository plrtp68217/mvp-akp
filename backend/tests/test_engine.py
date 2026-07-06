"""Юнит-тесты чистого движка правил (без БД/сервера).

Реестр строится вручную как обычный dict с resolver'ами, заказ — простой объект.
"""
from types import SimpleNamespace

import pytest

from app.services.rule_engine import (
    apply_rules,
    build_context,
    evaluate_condition,
    execute_actions,
)


def make_order(total=1000, status="paid", items_count=3, metadata=None):
    return SimpleNamespace(
        total=total,
        status=status,
        items_count=items_count,
        metadata_json=metadata or {},
    )


def system_registry():
    return {
        "total": {"resolver": lambda o: o.total},
        "status": {"resolver": lambda o: o.status},
        "items_count": {"resolver": lambda o: o.items_count},
    }


def rule(name, condition, action, priority=100):
    return SimpleNamespace(
        name=name, condition=condition, action=action, priority=priority
    )


# --- build_context -----------------------------------------------------------

def test_build_context_skips_none_and_errors():
    registry = {
        "total": {"resolver": lambda o: o.total},
        "missing": {"resolver": lambda o: None},
        "boom": {"resolver": lambda o: (_ for _ in ()).throw(KeyError("x"))},
    }
    ctx = build_context(make_order(total=500), registry)
    assert ctx == {"total": 500}


# --- evaluate_condition ------------------------------------------------------

def test_missing_variable_is_false_not_keyerror():
    condition = {"operator": "AND", "conditions": [{"variable": "ghost", "op": ">", "value": 0}]}
    # Переменной нет в context — ожидаем False, без исключения.
    assert evaluate_condition(condition, {"total": 100}) is False


def test_and_all_true():
    ctx = {"total": 1500, "items_count": 5}
    condition = {
        "operator": "AND",
        "conditions": [
            {"variable": "total", "op": ">", "value": 1000},
            {"variable": "items_count", "op": ">=", "value": 5},
        ],
    }
    assert evaluate_condition(condition, ctx) is True


def test_and_one_false():
    ctx = {"total": 500, "items_count": 5}
    condition = {
        "operator": "AND",
        "conditions": [
            {"variable": "total", "op": ">", "value": 1000},
            {"variable": "items_count", "op": ">=", "value": 5},
        ],
    }
    assert evaluate_condition(condition, ctx) is False


def test_or_one_true():
    ctx = {"total": 500, "status": "vip"}
    condition = {
        "operator": "OR",
        "conditions": [
            {"variable": "total", "op": ">", "value": 1000},
            {"variable": "status", "op": "==", "value": "vip"},
        ],
    }
    assert evaluate_condition(condition, ctx) is True


def test_empty_conditions_and_true_or_false():
    assert evaluate_condition({"operator": "AND", "conditions": []}, {}) is True
    assert evaluate_condition({"operator": "OR", "conditions": []}, {}) is False


def test_incomparable_types_are_false():
    # число сравнивается со строкой -> TypeError внутри -> False
    ctx = {"total": 100}
    condition = {"operator": "AND", "conditions": [{"variable": "total", "op": ">", "value": "abc"}]}
    assert evaluate_condition(condition, ctx) is False


# --- execute_actions ---------------------------------------------------------

def test_action_set_literal():
    action = {"actions": [{"target": "discount", "op": "set", "value": 600}]}
    assert execute_actions(action, {}) == {"discount": 600}


def test_action_set_from_source():
    action = {"actions": [{"target": "shipping", "op": "set", "source": "total"}]}
    assert execute_actions(action, {"total": 999}) == {"shipping": 999}


def test_action_add_subtract_multiply():
    action = {
        "actions": [
            {"target": "x", "op": "set", "value": 10},
            {"target": "x", "op": "add", "value": 5},
            {"target": "x", "op": "subtract", "value": 3},
            {"target": "x", "op": "multiply", "value": 2},
        ]
    }
    # ((10 + 5) - 3) * 2 = 24
    assert execute_actions(action, {})["x"] == 24


def test_action_percent_of_source():
    action = {"actions": [{"target": "discount", "op": "percent_of", "source": "total", "value": 10}]}
    # 10% от 6000 = 600
    assert execute_actions(action, {"total": 6000}) == {"discount": 600}


def test_action_non_numeric_operand_is_skipped():
    # source указывает на строку -> действие пропускается, движок не падает
    action = {"actions": [{"target": "discount", "op": "multiply", "source": "status", "value": 2}]}
    assert execute_actions(action, {"status": "paid"}) == {}


def test_action_none_value_is_skipped():
    action = {"actions": [{"target": "discount", "op": "add", "source": "total", "value": None}]}
    assert execute_actions(action, {"total": 100}) == {}


def test_unknown_action_op_is_skipped():
    action = {"actions": [{"target": "x", "op": "divide", "value": 2}]}
    assert execute_actions(action, {}) == {}


# --- apply_rules -------------------------------------------------------------

def gt_total(threshold, target, value, op="set", priority=100):
    return rule(
        f"total>{threshold}->{target}={value}",
        {"operator": "AND", "conditions": [{"variable": "total", "op": ">", "value": threshold}]},
        {"actions": [{"target": target, "op": op, "value": value}]},
        priority=priority,
    )


def test_apply_rules_priority_order_and_conflict_override():
    order = make_order(total=2000)
    registry = system_registry()
    # Оба правила пишут в discount; побеждает применённое последним (больший priority).
    r_low = gt_total(1000, "discount", 100, priority=10)
    r_high = gt_total(1000, "discount", 500, priority=20)
    # Передаём в «неотсортированном» виде — движок сам сортирует по priority.
    result = apply_rules(order, [r_high, r_low], registry)
    assert result == {"discount": 500}


def test_apply_rules_only_matching_rules_apply():
    order = make_order(total=800)
    registry = system_registry()
    r = gt_total(1000, "discount", 500)  # условие total>1000 не выполнено
    assert apply_rules(order, [r], registry) == {}


def test_apply_rules_missing_variable_does_not_crash():
    order = make_order()
    registry = system_registry()
    r = rule(
        "ghost",
        {"operator": "AND", "conditions": [{"variable": "ghost", "op": ">", "value": 0}]},
        {"actions": [{"target": "discount", "op": "set", "value": 1}]},
    )
    assert apply_rules(order, [r], registry) == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
