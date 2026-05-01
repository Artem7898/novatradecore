<div align="center">

# NovaTradeCore

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0-green.svg)](https://www.djangoproject.com/)
[![Type Checker](https://img.shields.io/badge/pyright-strict-red.svg)](https://github.com/microsoft/pyright)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

**Высокопроизводительный движок обработки сделок и оценки рисков для DeFi-экосистем**

Строгая типизация · Decimal-арифметика · Нативная асинхронность · Zero-downtime

</div>

---

## Обзор

**NovaTradeCore** — это высокопроизводительный движок для обработки торговых данных и оценки рисков, разработанный для экосистем DeFi. Проект обеспечивает строгую типизацию, использует `Decimal` для всех финансовых расчётов (недопустимо использование `float` для P&L), и полностью асинхронную архитектуру — готов к нагрузкам high-frequency trading.

---

## Ключевые архитектурные решения

| Решение | Описание |
|---------|----------|
| **Строгая типизация** | `pyright --strict` + Pydantic v2 + Django ORM с `Decimal` везде. Никаких неявных `float` в P&L. |
| **Нативная асинхронность (Django 5 + psycopg3)** | Полная асинхронная обработка запросов, асинхронные методы ORM, без узких мест `sync_to_async`. |
| **Архитектура без Celery** | Фоновые задачи обрабатываются лёгкими асинхронными воркерами (`NovaTask`) + RabbitMQ/Kafka. |
| **Умное управление кэшем** | Адаптивный TTL и политики вытеснения для горячих торговых символов. |
| **Горячие миграции** | `CREATE INDEX CONCURRENTLY` и схемные изменения без простоя. |

---

## Быстрый старт (Docker)

Все сервисы (PostgreSQL, Redis, Grafana, Uvicorn) оркестрируются через Docker Compose.

### 1. Клонирование и настройка окружения

```bash
git clone https://github.com/Artem7898/novatradecore
cd novatradecore
cp .env.example .env
```

### 2. Сборка и запуск

```bash
docker compose up --build -d
```

### 3. Доступ к сервисам

| Сервис | URL | Учётные данные |
|--------|-----|----------------|
| API и админ-панель | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | Задаются в `.env` — измените сразу после запуска |
| Grafana | [http://127.0.0.1:3000/](http://127.0.0.1:3000/) | `admin` / `admin` |

---

## Настройка мониторинга (Grafana)

Grafana автоматически подключается к встроенному источнику данных PostgreSQL.

### Добавление источника данных

1. Перейдите в **Connections → Add data source → PostgreSQL**
2. Заполните параметры:

| Параметр | Значение |
|----------|----------|
| Host | `postgres:5432` |
| Database | `novatrade` |
| User | `nova` |
| Password | `nova_pass` |

---

## Примеры SQL-запросов

### Запросы в секунду (RPS)

```sql
SELECT 
  DATE_TRUNC('minute', created_at) AS time,
  COUNT(id) AS requests
FROM trades_trade 
GROUP BY time 
ORDER BY time;
```

### Доля высокорисковых сделок

```sql
SELECT 
  DATE_TRUNC('minute', created_at) AS time,
  COUNT(CASE WHEN is_high_risk = true THEN 1 END) AS high_risk,
  COUNT(id) AS total
FROM trades_trade 
GROUP BY time 
ORDER BY time;
```

---

## Нагрузочное тестирование (Locust)

В комплект входит `locustfile.py` для симуляции HFT-трафика.

### Запуск тестирования

```bash
# 1. Запустите стек
docker compose up -d

# 2. Установите Locust (или запустите внутри контейнера)
pip install locust
locust -f locustfile.py --host http://127.0.0.1:8000
```

3. Откройте [http://localhost:8089](http://localhost:8089)
4. Укажите количество пользователей (например, 50) и время разгона (10 секунд)

**Ожидаемый результат:** 200–500 RPS на среднем оборудовании без заметной деградации задержек.

---

## Локальная установка (без Docker)

Если вы предпочитаете запуск без Docker (потребуется локальный PostgreSQL):

```bash
pip install -e ".[dev]"
cp .env.example .env
# Отредактируйте .env, указав ваш локальный PostgreSQL (например, 127.0.0.1)
python manage.py migrate --skip-checks
python manage.py runserver 0.0.0.0:8000
```

---

## Качество кода (Pyright Strict)

Обеспечение использования `Decimal` везде и выявление типовых ошибок:

```bash
pyright .
```

**Ожидаемый результат:** `0 errors, 0 warnings`. Любое использование `float` в P&L или метриках риска запрещено.

---

## Тестирование

```bash
pytest -v --cov=trades --cov-report=term-missing
```

Покрытие включает тесты асинхронных эндпоинтов, верификацию Decimal-арифметики и правила риск-движка.

---

## Рекомендации для production

### 1. Строгая валидация Decimal

Всегда используйте `Decimal` от wire до базы данных.

Pydantic `TradeSchemaIn` валидирует входные данные и отклоняет любые числовые `float`.

### 2. Горячие миграции

Предполагается, что таблица `trades_trade` может превысить 500 млн строк.
Никогда не используйте стандартную миграцию с `LOCK TABLE`. Вместо этого используйте `atomic = False` и ручной SQL:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_created 
ON trades_trade (symbol, created_at DESC NULLS LAST);
```

`CONCURRENTLY` позволяет избежать простоя и блокировок.

### 3. Асинхронные подключения к БД

В `settings.py` настройте `CONN_MAX_AGE` и health-checks:

```python
"CONN_MAX_AGE": 60,
"CONN_HEALTH_CHECKS": True,
```

Это поддерживает пулы соединений psycopg3 в активном состоянии и предотвращает переподключения под нагрузкой.

---

## Лицензия

**Proprietary** — все права защищены.
#### Автор проекта Артем Алимпиев 
#### https://orcid.org/0009-0007-6740-7242 

Это программное обеспечение предназначено только для авторизованного использования. Распространение или реверс-инжиниринг запрещены.

---

<div align="center">

*Построено для высокочастотной обработки DeFi-сделок. Никаких float. Никакого простоя.*

</div>
