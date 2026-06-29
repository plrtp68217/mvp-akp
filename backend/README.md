Пользователю в UI будет предоставляться:
- набор переменных: total, discount, ...
- набор операторов: +, -, *, :

И с помощью них он будет строить условия и действия:
- condition: total > 1000
- action: discount = total * 0.8

```python
rule.action = "discount = total * 0.1"
# result = {'total': 1500, 'discount': 0}
# action_parts = ['discount ', ' total * 0.1']
# field = 'discount'
# value = eval('total * 0.1', {}, result)  # 1500 * 0.1 = 150
# result['discount'] = 150
```

```python
rule.action = "order.discount = 10"
# action_parts = ['order.discount ', ' 10']
# field = 'order.discount'
# value = 10
# result['order.discount'] = 10  # Установит плоский ключ
```

```python
# Исходные данные
result = {
    "total": 1500,
    "client_type": "vip",
    "discount": 0
}

# Правило из БД
rule.action = "discount = total * 0.1"

# Обработка
action_parts = rule.action.split('=', 1)
if len(action_parts) == 2:
    field = action_parts[0].strip()  # 'discount'
    value = eval(action_parts[1].strip(), {}, result)  # eval('total * 0.1', {}, result) → 150
    result[field] = value  # result['discount'] = 150

print(result)
# {'total': 1500, 'client_type': 'vip', 'discount': 150}
```
