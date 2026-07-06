# MVP AKP — Backend (Rule Engine для заказов)

Бекенд системы, где администратор через UI-конструктор создаёт правила вида
`condition → action`, а при оформлении заказа движок прогоняет активные правила и
возвращает результат применённых действий (например, `{"discount": 600}`).

Правила хранятся как **JSON-структуры** (не строковый DSL) и исполняются безопасно —
**без `eval()`**.

---

## Стек

- **FastAPI** — HTTP API
- **SQLAlchemy 2.x** — ORM
- **SQLite** — хранилище (dev/MVP)
- **Pydantic v2** — валидация схем
- **pytest** — юнит-тесты движка

---

## Архитектура

Зависимости строго в одну сторону:

```
routers (app/api/v1/endpoints) → services → engine/registry → models
```

`registry.py` и `rule_engine.py` — **чистый Python**: не импортируют FastAPI, ничего не
знают про HTTP, что позволяет тестировать движок без поднятия сервера/БД.

```
app/
├── main.py                       # создание FastAPI-приложения, init БД
├── core/
│   ├── config.py                 # Settings (DATABASE_URL)
│   └── connection.py             # engine, SessionLocal, Base, get_db, init_database
├── models/
│   ├── order.py                  # Order (системные переменные + metadata_json)
│   ├── rule.py                   # Rule (condition/action = JSON, priority)
│   └── custom_variable.py        # CustomVariable
├── schemas/
│   ├── order.py                  # OrderCreate/OrderResponse
│   ├── rule.py                   # ConditionBlock/ActionBlock/RuleCreate/...
│   └── variable.py               # CustomVariableCreate/VariableList/...
├── services/
│   ├── registry.py               # SYSTEM_VARIABLES, build_registry, get_nested, coerce_value
│   ├── rule_engine.py            # build_context, evaluate_condition, execute_actions, apply_rules
│   ├── rule_service.py           # CRUD правил, validate_rule_variables, process_order
│   └── variable_service.py       # CRUD кастомных переменных, мягкое удаление
└── api/v1/
    ├── router.py                 # сборка роутеров под /api/v1
    └── endpoints/
        ├── rules.py              # /rules
        ├── variables.py          # /variables
        └── orders.py             # /orders
```

---

## Модель данных

### `orders`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID заказа |
| total | Float | Сумма заказа — **системная переменная** |
| status | String | Статус — **системная переменная** |
| items_count | Integer | Кол-во товаров — **системная переменная** |
| metadata_json | JSON | Расширяемое хранилище (источник кастомных переменных) |
| created_at | DateTime | Дата создания |

### `rules`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID правила |
| name | String | Название для админа (в логике не участвует) |
| condition | JSON | `{"operator": "AND"\|"OR", "conditions": [...]}` |
| action | JSON | `{"actions": [...]}` |
| priority | Integer | Порядок применения (меньше = раньше), default `100` |
| is_active | Boolean | Включено ли правило |
| created_at / updated_at | DateTime | Служебные |

### `custom_variables`
| Поле | Тип | Назначение |
|---|---|---|
| id | Integer, PK | ID переменной |
| key | String, unique | Техническое имя (regex `^[a-z_][a-z0-9_]*$`) |
| label | String | Человекочитаемое имя для UI |
| value_type | String | `number` \| `string` \| `boolean` |
| source_path | String, nullable | Путь в `orders.metadata_json` (точечная нотация). **Пусто** — для выходных переменных (только `target`) |
| enum_values | JSON, nullable | Список допустимых строковых значений (только при `value_type == string`) |
| is_active | Boolean | Мягкое включение/отключение |
| created_at / updated_at | DateTime | Служебные |

---

## Переменные

Гибридная модель:

- **Системные** — прямые поля `orders` (`total`, `status`, `items_count`), описаны в коде
  (`SYSTEM_VARIABLES` в `registry.py`), меняются только разработчиком.
- **Кастомные** — заводятся админом, значения берутся из `orders.metadata_json` по
  `source_path` и приводятся к заявленному типу (`coerce_value`) — сырым данным не доверяем.
- **Выходные** — частный случай кастомных **без `source_path`**: ниоткуда не читаются,
  используются только как `action.target`. Нужны, чтобы фронт знал `label`/`value_type`
  и корректно подписал результат прогона.

Удаление кастомной переменной — **мягкое** (`is_active=False`), чтобы не ломать правила,
которые на неё ссылаются.

---

## Формат правил

### Условие (`condition`) — плоский список с AND/OR (без вложенности)

```json
{
  "operator": "AND",
  "conditions": [
    {"variable": "total", "op": ">", "value": 5000},
    {"variable": "loyalty_level", "op": "==", "value": "gold"}
  ]
}
```

Операторы сравнения (фиксированный enum): `>`, `<`, `>=`, `<=`, `==`, `!=`.

### Действие (`action`)

```json
{
  "actions": [
    {"target": "discount", "op": "percent_of", "source": "total", "value": 10}
  ]
}
```

Операции (фиксированный enum):

| op | Смысл | Операнд |
|---|---|---|
| `set` | записать значение | литерал `value` или значение переменной `source` |
| `add` | прибавить | `operand + value` |
| `subtract` | вычесть | `operand - value` |
| `multiply` | умножить | `operand * value` |
| `percent_of` | процент от | `operand * value / 100` |

Операнд для арифметики = `context[source]` (если задан `source`), иначе текущее
накопленное значение по `target`. `target` — имя выходного поля результата.

---

## Поведение движка

- **AND** — истинно, если истинны все условия; **OR** — если хотя бы одно.
  Пустой список условий: AND → `true`, OR → `false`.
- **Отсутствующая/деактивированная переменная** в условии трактуется как `false`
  (никаких `KeyError`).
- **Несравнимые типы** (например число со строкой) → условие `false`.
- **Некорректный операнд** действия (не число / `None`) → действие пропускается,
  движок не падает.
- **Приоритет и конфликт**: правила применяются по возрастанию `priority`
  (меньше = раньше). Если два правила пишут в один `target`, **побеждает применённое
  последним** — правило с бóльшим номером `priority` перезаписывает результат (`dict.update`).

---

## Валидация правил

При создании правила `validate_rule_variables` проверяет, что все `variable`
(условия), `source` и `target` (действия) существуют в реестре
(`build_registry` = системные + активные кастомные). Иначе — **HTTP 422** с перечнем
неизвестных переменных.

---

## API

Базовый префикс — `/api/v1`. Интерактивная документация: `GET /docs`.

### Переменные

#### `POST /api/v1/variables/` — создать кастомную переменную

Входная переменная (читается из `metadata_json`):

```bash
curl -X POST http://localhost:8000/api/v1/variables/ \
  -H "Content-Type: application/json" \
  -d '{
        "key": "loyalty_level",
        "label": "Уровень лояльности",
        "value_type": "string",
        "source_path": "customer.loyalty.level",
        "enum_values": ["silver", "gold", "platinum"]
      }'
```

```json
{
  "key": "loyalty_level",
  "label": "Уровень лояльности",
  "value_type": "string",
  "source_path": "customer.loyalty.level",
  "enum_values": ["silver", "gold", "platinum"],
  "id": 1,
  "is_active": true,
  "created_at": "2026-07-06T10:00:00"
}
```

Выходная переменная (только как `target`, без `source_path`):

```bash
curl -X POST http://localhost:8000/api/v1/variables/ \
  -H "Content-Type: application/json" \
  -d '{"key": "discount", "label": "Скидка", "value_type": "number"}'
```

Ошибка при дубликате `key` → **409**.

#### `GET /api/v1/variables/` — объединённый список (system + custom)

```bash
curl http://localhost:8000/api/v1/variables/
```

```json
{
  "variables": [
    {"key": "total",         "label": "Сумма заказа",       "value_type": "number", "enum": null, "source": "system"},
    {"key": "status",        "label": "Статус заказа",      "value_type": "string", "enum": null, "source": "system"},
    {"key": "items_count",   "label": "Количество товаров", "value_type": "number", "enum": null, "source": "system"},
    {"key": "loyalty_level", "label": "Уровень лояльности", "value_type": "string", "enum": ["silver","gold","platinum"], "source": "custom"},
    {"key": "discount",      "label": "Скидка",             "value_type": "number", "enum": null, "source": "custom"}
  ],
  "total": 5
}
```

### Правила

#### `POST /api/v1/rules/` — создать правило

```bash
curl -X POST http://localhost:8000/api/v1/rules/ \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Скидка 10% для gold от 5000",
        "priority": 10,
        "condition": {
          "operator": "AND",
          "conditions": [
            {"variable": "total", "op": ">", "value": 5000},
            {"variable": "loyalty_level", "op": "==", "value": "gold"}
          ]
        },
        "action": {
          "actions": [
            {"target": "discount", "op": "percent_of", "source": "total", "value": 10}
          ]
        }
      }'
```

```json
{
  "name": "Скидка 10% для gold от 5000",
  "condition": { "operator": "AND", "conditions": [ ... ] },
  "action": { "actions": [ ... ] },
  "priority": 10,
  "is_active": true,
  "id": 1,
  "created_at": "2026-07-06T10:05:00"
}
```

Ссылка на несуществующую переменную → **422**:

```json
{ "detail": "Неизвестные переменные: ghost_var" }
```

#### Остальные операции с правилами

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/v1/rules/` | список (`skip`, `limit`, `active_only`), отсортирован по `priority` |
| `GET` | `/api/v1/rules/{id}` | получить правило (404, если нет) |
| `PATCH` | `/api/v1/rules/{id}` | частичное обновление |
| `DELETE` | `/api/v1/rules/{id}` | жёсткое удаление (204) |
| `POST` | `/api/v1/rules/{id}/toggle` | инвертировать `is_active` |

### Заказы

#### `POST /api/v1/orders/` — создать заказ и прогнать правила

```bash
curl -X POST http://localhost:8000/api/v1/orders/ \
  -H "Content-Type: application/json" \
  -d '{
        "total": 6000,
        "status": "paid",
        "items_count": 2,
        "metadata": {"customer": {"loyalty": {"level": "gold"}}}
      }'
```

Совпадение (total > 5000 и gold) → скидка 10% от 6000 = 600:

```json
{
  "id": 1,
  "total": 6000.0,
  "status": "paid",
  "items_count": 2,
  "metadata_json": {"customer": {"loyalty": {"level": "gold"}}},
  "created_at": "2026-07-06T10:10:00",
  "applied_actions": {"discount": 600.0}
}
```

Без совпадения (например `level = silver`) — `"applied_actions": {}`.

---

## Запуск

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
# http://localhost:8000/docs
```

> ⚠️ Схема БД менялась относительно ранних версий. При апгрейде удалите старый
> `database.db` — миграций пока нет, таблицы создаются автоматически при старте
> (`init_database`).

### Настройки

`app/core/config.py` читает `DATABASE_URL` (по умолчанию `sqlite:///./database.db`),
можно переопределить через `.env` или переменную окружения.

---

## Тесты

Юнит-тесты движка (чистый Python, без БД):

```bash
cd backend
python -m pip install -r requirements-dev.txt   # ставит pytest
python -m pytest tests/ -v
```

Покрыто: несуществующая переменная в условии, AND/OR и пустой список условий,
несравнимые типы, все операции действий (`set/add/subtract/multiply/percent_of`),
некорректные операнды, порядок по `priority` и конфликт двух правил на один `target`.

---

## Возможные доработки

**Функциональность**
- **CRUD переменных в API**: сейчас в роутере только `POST`/`GET`. Обновление,
  мягкое/жёсткое удаление и проверка использования (`find_rules_using`) реализованы в
  `VariableService`, но не проброшены в эндпоинты — добавить `PATCH`/`DELETE /variables/{key}`.
- **Настраиваемая стратегия конфликта**: сейчас захардкожена перезапись по приоритету.
  Вынести выбор (перезапись / суммирование / максимум) на уровень правила или таргета.
- **Вложенные группы условий** (сейчас только плоский AND/OR).
- **Предпросмотр/симуляция** правила на тестовом заказе без сохранения.
- **Логирование прогонов**: какие правила сработали для конкретного заказа (аудит).

**Надёжность и качество**
- **Миграции БД** (Alembic) вместо `create_all` + ручного удаления `database.db`.
- **Транзакционность `process_order`**: сейчас заказ коммитится до прогона правил —
  при желании не сохранять «пустые» прогоны или сохранять результат действий вместе с заказом.
- **Валидация `enum_values` в условиях**: проверять, что `value` строковой переменной с
  `enum_values` входит в допустимый список.
- **Валидация совместимости оператора и типа** переменной (например `>` для строк).
- **Интеграционные тесты** на роутеры и сервисы (сейчас юнит-тесты только на движок).

**Инфраструктура**
- **Аутентификация/авторизация** админских эндпоинтов (создание правил и переменных).
- **CORS** и конфигурация окружений (dev/prod).
- **Пагинация и фильтры** для списков правил/переменных, единый формат ошибок.
