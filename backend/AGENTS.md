# AGENTS.md — Rule Engine для системы заказов

Этот файл описывает архитектуру и договорённости для движка правил (rule engine),
применяемого к заказам (orders). Используй его как источник истины при написании кода.

## Контекст проекта

Стек: **FastAPI + SQLAlchemy + SQLite**.

Идея: админ создаёт правила вида `condition -> action` через UI-конструктор
(выбор переменной, оператора, значения — без свободного текста). Когда покупатель
оформляет заказ, бекенд прогоняет все активные правила через движок и возвращает
результат применённых действий (например, `{"discount": 600}`).

## Принятые архитектурные решения

1. **Формат хранения condition/action — JSON**, не строковый DSL.
   Причина: конструктор в UI и так собирает структуру, а не текст; JSON не требует
   парсера и безопаснее, чем `eval()`-подобные строковые выражения.

2. **Логика условий — плоский список с AND/OR, без вложенности.**
   Одно правило = один блок условий, все объединены одним оператором (либо все AND,
   либо все OR). Вложенные группы условий сознательно не реализуем на этом этапе.

3. **Операторы (`>`, `<`, `>=`, `<=`, `==`, `!=`) и операции действий
   (`set`, `add`, `subtract`, `percent_of`, `multiply`) — жёстко зашиты в коде**,
   не редактируются админом и не хранятся в БД. Это фиксированный enum.

4. **Переменные — гибридные: системные (в коде) + кастомные (в БД).**
   - Системные переменные — прямые поля `orders` (`total`, `status`, `items_count`),
     описаны в Python-словаре, меняются только разработчиком через код/деплой.
   - Кастомные переменные — заводятся админом через UI, хранятся в таблице
     `custom_variables`, значения берутся из JSON-поля `orders.metadata_json` по
     указанному пути (`source_path`), без изменения схемы БД.

5. **Значения из `metadata_json` приводятся к заявленному типу (`coerce_value`)
   перед использованием в движке** — не доверяем сырым данным.

6. **Удаление переменных — мягкое (`is_active=False`)**, чтобы не ломать
   уже существующие правила, ссылающиеся на них.

## Схема таблиц

### `orders`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID заказа |
| total | Float | Сумма заказа — системная переменная |
| status | String | Статус заказа — системная переменная |
| items_count | Integer | Кол-во товаров — системная переменная |
| metadata_json | JSON | Расширяемое хранилище для кастомных данных заказа (источник для кастомных переменных) |
| created_at | DateTime | Дата создания |

### `custom_variables`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID переменной |
| key | String, unique | Техническое имя, используется в condition/action JSON (regex `^[a-z_][a-z0-9_]*$`) |
| label | String | Человекочитаемое имя для UI |
| value_type | String (`number`\|`string`\|`boolean`) | Тип значения, определяет доступные операторы в UI |
| source_path | String | Путь внутри `orders.metadata_json` (поддержка точечной нотации, напр. `customer.loyalty.level`) |
| enum_values | JSON, nullable | Ограниченный список допустимых строковых значений (только если `value_type == string`) |
| is_active | Boolean | Мягкое включение/отключение переменной |
| created_at / updated_at | DateTime | Служебные |

### `rules`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID правила |
| name | String | Название для админа (не участвует в логике) |
| condition | JSON | `{"operator": "AND"|"OR", "conditions": [{"variable", "op", "value"}, ...]}` |
| action | JSON | `{"actions": [{"target", "op", "value"?, "source"?}, ...]}` |
| priority | Integer | Порядок применения правил (меньше = раньше) |
| is_active | Boolean | Включено ли правило |
| created_at / updated_at | DateTime | Служебные |

## Структура проекта

```
app/
├── models.py           # SQLAlchemy: Order, Rule, CustomVariable
├── schemas.py          # Pydantic: ConditionBlock, ActionBlock, RuleCreate, CustomVariableCreate
├── registry.py         # SYSTEM_VARIABLES, build_registry(), get_nested(), coerce_value()
├── engine.py           # build_context(), evaluate_condition(), execute_actions(), apply_rules()
├── services/
│   ├── rules_service.py       # create_rule, validate_rule_variables, process_order
│   └── variables_service.py   # CRUD для custom_variables + проверка использования перед удалением
└── routers/
    ├── rules.py         # POST/GET /rules
    ├── variables.py     # POST/GET /variables (объединённый список system+custom)
    └── orders.py        # POST /orders -> вызывает process_order
```

Зависимости строго в одну сторону: `routers -> services -> engine/registry -> models`.
`engine.py` и `registry.py` не импортируют FastAPI и ничего не знают про HTTP —
это позволяет тестировать их как чистый Python без поднятия БД/сервера.

## Ключевые функции (контракты)

```python
# registry.py
def build_registry(db: Session) -> dict:
    """Возвращает {var_key: {"label", "type", "enum", "resolver": callable(order)->value}}"""

def coerce_value(raw, value_type: str):
    """Приводит сырое значение из metadata_json к number/boolean/string"""

# engine.py
def build_context(order: Order, registry: dict) -> dict:
    """Возвращает {var_key: значение} для конкретного заказа"""

def evaluate_condition(condition: dict, context: dict) -> bool:
    """Проверяет один condition-блок (AND/OR) против context"""

def execute_actions(action: dict, context: dict) -> dict:
    """Выполняет action-блок, возвращает {target: значение}"""

def apply_rules(order: Order, rules: list[Rule], registry: dict) -> dict:
    """Прогоняет все правила по приоритету, возвращает объединённый результат"""
```

## Открытые вопросы (не решены, требуют внимания при реализации)

- **Конфликт правил на один `target`**: если два правила пишут в одно и то же
  поле результата (например, две скидки), сейчас побеждает правило с бóльшим
  приоритетом (`.update()` перезаписывает). Нужно решить: перезапись, суммирование
  или максимум — и явно захардкодить это поведение в `apply_rules`.
- **Что если переменная удалена/деактивирована, а правило её использует**:
  `evaluate_condition` должен трактовать отсутствие переменной в `context` как `False`,
  не должен кидать `KeyError`.
- **Валидация ссылок на переменные при создании правила**: `validate_rule_variables`
  должен проверять, что все `variable`/`source`/`target` из condition/action
  существуют в `build_registry(db)`, иначе — 422 с понятной ошибкой.

## Задача для Claude Code

Реализовать модули `models.py`, `schemas.py`, `registry.py`, `engine.py`,
`services/*`, `routers/*` согласно контрактам выше, с юнит-тестами на `engine.py`
(граничные случаи: несуществующая переменная в условии, деление/умножение на
нестандартные значения, приоритет и конфликт двух правил на один `target`).
