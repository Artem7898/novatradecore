# NovaTradeCore

Сервис приёма нормализованных сделок и детерминированной оценки риска на Django 5.2 LTS, Python 3.12/3.13 и PostgreSQL. [English](README_EN.md).

API проверяет сервисный Bearer-токен, ограничивает частоту запросов и валидирует денежные значения перед записью. Расчёты используют `Decimal`; числовые значения передаются в JSON строками. Приложение имеет ASGI-интерфейс, а транзакции Django ORM выполняются через `sync_to_async` в потоке. Брокер сообщений, WebSocket-алерты и автоматическая генерация TypeScript не реализованы.

## Запуск для разработки

Нужны Docker с Compose v2, `make` и Python 3.12+. Для локальных проверок установите [uv](https://docs.astral.sh/uv/); версия CI — 0.12.23.

```bash
git clone https://github.com/Artem7898/novatradecore.git
cd novatradecore
make init       # создаёт .env со случайными секретами; не перезаписывает существующий файл
make up         # сервисы, сборка, отдельный release (migrate + collectstatic), затем приложение
```

API доступен на `http://127.0.0.1:8000`; `/health/live/` проверяет процесс, `/health/ready/` — доступ к БД и кэшу. Compose для разработки использует reload и bind mount исходников. PostgreSQL и Redis не публикуются во внешнюю сеть. Пользователи админ-панели не создаются автоматически:

```bash
docker compose run --rm web python manage.py createsuperuser
```

`.env` содержит секреты и исключён из Git и Docker build context. `.env.example` описывает переменные, но не является готовой конфигурацией с общими паролями. Не передавайте `.env` в отчёты и журналы.

## API

`POST /api/v1/trades/ingest/`

Заголовки: `Authorization: Bearer <service-token>` и `Content-Type: application/json`. Используйте значение токена из своей конфигурации `INGEST_API_TOKENS`; не записывайте его в исходники или историю команд.

```json
{
  "symbol": "SOL/USDT",
  "side": "BUY",
  "price": "150.250000000",
  "quantity": "10.500000000",
  "exchange_id": "binance",
  "trade_id": "example-trade-001"
}
```

Контракт входных данных:

- `price` и `quantity` — JSON-строки с положительными конечными десятичными значениями: до 11 цифр до точки и до 9 после неё (20 всего). Экспоненциальная запись и ведущий знак не принимаются. JSON numbers, `NaN`, бесконечность и значения вне диапазона отклоняются.
- `symbol` имеет формат `BASE/QUOTE`; поддерживаются котировки `USD`, `USDT`, `USDC`. Идентификаторы не могут быть пустыми или содержать пробелы; `exchange_id` — до 50, `trade_id` — до 100 символов.
- `side` — `BUY` или `SELL`. Неизвестные поля отклоняются.
- `(exchange_id, trade_id)` — ключ идемпотентности. Повтор должен содержать те же данные сделки.

В ответе возвращаются `id`, `symbol`, `side`, `price`, `quantity`, `notional`, `quote_currency`, `risk` и `created_at`. Десятичные значения сериализуются строками. `notional = price × quantity` — стоимость сделки в валюте котировки, **не P&L**. Прибыль, себестоимость позиции и комиссии этот сервис не рассчитывает. Для порога риска USD/USDT/USDC принимаются в номинальном соотношении 1:1; это не FX-конвертация и не оценка отклонения stablecoin от привязки.

Текущие правила риска: стоимость строго больше 1 000 000 единиц котировки добавляет 60 баллов, количество строго больше 10 000 — 40 баллов. Сделка считается high risk при сумме от 50 баллов. Это простые пороги, которые следует согласовать с бизнес-правилами до использования в торговых решениях.

| HTTP | Значение |
|---|---|
| 201 | Новая сделка сохранена |
| 200 | Идентичное событие уже сохранено |
| 401 | Bearer-токен отсутствует или неверен |
| 409 | Тот же ключ события содержит другие данные |
| 413 | Тело запроса превышает 64 КиБ |
| 422 | Некорректный JSON или нарушение входного контракта |
| 429 | Превышен лимит клиента; см. `Retry-After` |
| 503 | Зависимость сервиса недоступна |

## Окружение и проверки

Зависимости фиксируются в `uv.lock`; `package-lock.json` для Python не используется. `dev` — группа по умолчанию, `load` устанавливается отдельно.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest --cov --cov-report=term-missing
uv run --frozen python manage.py makemigrations --check --dry-run
uv run --frozen pre-commit install
```

Тестовые настройки по умолчанию используют изолированную SQLite БД и локальный кэш. Они подходят для быстрых проверок; PostgreSQL-специфичное поведение проверяется отдельно. Для локальной PostgreSQL задайте `TEST_DATABASE_ENGINE=postgresql`, `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`. Тестовый пользователь БД должен иметь право создавать тестовую базу. CI запускает тесты с PostgreSQL 16 и Redis 7 на Python 3.12/3.13, проверяет типы, форматирование, миграции, сборку wheel и Docker, зависимости и покрытие.

Обновление зависимостей выполняйте через `uv lock`, затем повторяйте проверки. Для аудита всех зафиксированных зависимостей, включая test/load:

```bash
uv export --frozen --all-groups --no-emit-project --format requirements-txt --output-file /tmp/novatrade-requirements.txt
uv run --frozen pip-audit --disable-pip --no-deps --require-hashes -r /tmp/novatrade-requirements.txt
```

## Production и измерения

Используйте отдельный `docker-compose.production.yml`, TLS на доверенном reverse proxy и собственные секреты. Production-настройки требуют явных `SECRET_KEY`, `ALLOWED_HOSTS`, `INGEST_API_TOKENS`, пароля БД и `REDIS_URL`. Миграции выполняются отдельным Compose-сервисом `release` с ролью владельца таблиц до запуска приложения; runtime-роль БД ограничена DML. Для production также нужны отдельные `MIGRATION_DATABASE_USER`, `MIGRATION_DATABASE_PASSWORD` и `POSTGRES_ADMIN_PASSWORD`. Существующий PostgreSQL volume требует предварительного provisioning ролей. Обновление выполняется в окне обслуживания: остановите ingestion и все старые реплики до миграции `0003`; helper останавливает только локальный Compose web. Записи сделок в admin доступны только для чтения. [Runbook](docs/operations.md) описывает запуск, ротацию ключей, резервные копии и ограничения отката.

Для нагрузки установите `uv sync --frozen --group load` и используйте `make benchmark`; для удалённого стенда задайте `BENCHMARK_TOKEN`; локально скрипт также умеет читать ключ `local-ingestor` из собственной `.env`. Параметры, формат результатов и порядок измерения описаны в [runbook](docs/operations.md#нагрузочные-измерения). Пропускная способность зависит от окружения и должна измеряться с учётом ошибок и задержек.

Исторический CSV `Locust_2026-05-01-14h15_…csv` оставлен для воспроизводимости аудита: 33 711 запросов, 15 837 ошибок (46,98%), p95 270 мс. Он относится к прежней реализации и не подтверждает производительность текущей версии. Обещаний HFT, zero-downtime или 15K записей/с проект не даёт.

[Архитектура](architecture.mmd) · [План модернизации и внешние действия](docs/modernization.md)

## Лицензия

**Proprietary — все права защищены.** Автор: Артем Алимпиев, [ORCID](https://orcid.org/0009-0007-6740-7242). Использование и распространение требуют разрешения правообладателя.
