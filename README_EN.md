# NovaTradeCore

A service for normalized trade ingestion and deterministic risk assessment using Django 5.2 LTS, Python 3.12/3.13 and PostgreSQL. [Русский](README.md).

The API authenticates service Bearer tokens, limits requests and validates monetary input before persistence. Calculations use `Decimal`; decimal JSON values are strings. The application exposes ASGI, while Django ORM transactions run through a thread-sensitive `sync_to_async` boundary. A message broker, WebSocket alerts and automatic TypeScript generation are not implemented.

## Development setup

Install Docker with Compose v2, `make` and Python 3.12+. Local checks also require [uv](https://docs.astral.sh/uv/); CI uses version 0.12.23.

```bash
git clone https://github.com/Artem7898/novatradecore.git
cd novatradecore
make init       # generates .env secrets without overwriting an existing file
make up         # services, build, explicit release (migrate + collectstatic), then app
```

The API listens at `http://127.0.0.1:8000`. `/health/live/` checks the process; `/health/ready/` checks database and cache access. Development Compose uses source bind mounts and reload. PostgreSQL and Redis are not published externally. Admin users are created explicitly:

```bash
docker compose run --rm web python manage.py createsuperuser
```

`.env` contains secrets and is excluded from Git and the Docker build context. `.env.example` documents configuration without shared default passwords. Do not include `.env` in logs or reports.

## API

`POST /api/v1/trades/ingest/`

Send `Authorization: Bearer <service-token>` and `Content-Type: application/json`. Use a token configured in `INGEST_API_TOKENS`; do not put credentials in source files or shell history.

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

Input contract:

- `price` and `quantity` are positive finite decimal **strings** with at most 11 integer and 9 fractional digits (20 total). Exponent notation and a leading sign are rejected. JSON numbers, `NaN`, infinity and out-of-range values are rejected.
- Symbols use `BASE/QUOTE`; supported quotes are `USD`, `USDT` and `USDC`. Identifiers must be nonblank and contain no whitespace; `exchange_id` is limited to 50 and `trade_id` to 100 characters.
- `side` is `BUY` or `SELL`. Unknown fields are rejected.
- `(exchange_id, trade_id)` is the idempotency key. A replay must contain the same trade data.

Responses contain `id`, `symbol`, `side`, `price`, `quantity`, `notional`, `quote_currency`, `risk` and `created_at`. Decimal values are JSON strings. `notional = price × quantity` is the trade value in its quote currency, **not P&L**. Position cost basis, profit and fees are not calculated. The risk threshold treats USD/USDT/USDC at nominal 1:1 parity; no FX conversion or stablecoin depeg assessment is performed.

Current risk rules add 60 points for notional strictly above 1,000,000 quote units and 40 points for quantity strictly above 10,000. A score of at least 50 is high risk. These simple thresholds need business approval before use in trading decisions.

| HTTP | Meaning |
|---|---|
| 201 | New trade persisted |
| 200 | Identical event already exists |
| 401 | Missing or invalid Bearer token |
| 409 | Existing event key has different trade data |
| 413 | Request body exceeds 64 KiB |
| 422 | Invalid JSON or input contract violation |
| 429 | Client rate limit exceeded; see `Retry-After` |
| 503 | A service dependency is unavailable |

## Environment and checks

`uv.lock` fixes Python dependencies. `dev` is the default dependency group; install the `load` group separately.

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest --cov --cov-report=term-missing
uv run --frozen python manage.py makemigrations --check --dry-run
uv run --frozen pre-commit install
```

Test settings default to isolated SQLite and local cache for fast checks. PostgreSQL-specific behavior requires PostgreSQL tests. Set `TEST_DATABASE_ENGINE=postgresql` and `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` for a local PostgreSQL instance; the test user needs permission to create a test database. CI runs Python 3.12/3.13 with PostgreSQL 16 and Redis 7 and checks types, formatting, migrations, wheel/Docker builds, dependencies and coverage.

Update dependencies with `uv lock`, then rerun checks. Audit all locked dependencies, including test/load tools, with:

```bash
uv export --frozen --all-groups --no-emit-project --format requirements-txt --output-file /tmp/novatrade-requirements.txt
uv run --frozen pip-audit --disable-pip --no-deps --require-hashes -r /tmp/novatrade-requirements.txt
```

## Production and measurements

Use the separate `docker-compose.production.yml`, a trusted TLS reverse proxy and deployment-specific secrets. Production requires explicit `SECRET_KEY`, `ALLOWED_HOSTS`, `INGEST_API_TOKENS`, database password and `REDIS_URL`. Run migrations through the separate Compose `release` service with a table-owner role before starting the application; the runtime database role is restricted to DML. Production additionally requires `MIGRATION_DATABASE_USER`, `MIGRATION_DATABASE_PASSWORD` and `POSTGRES_ADMIN_PASSWORD`. An existing PostgreSQL volume requires reviewed role provisioning first. Use a maintenance window: pause ingestion and stop all old replicas before migration `0003`; the helper stops only its local Compose web service. Trade records are read-only in admin. The [operations runbook](docs/operations.md) covers deployment, token rotation, backups and rollback limitations.

For load measurements, run `uv sync --frozen --group load`, then `make benchmark`. Set `BENCHMARK_TOKEN` for a remote target; the script can also read `local-ingestor` from the local `.env`. Parameters and output are documented in the [runbook](docs/operations.md#нагрузочные-измерения). Throughput must be measured for the actual deployment, including failures and latency.

The historical `Locust_2026-05-01-14h15_…csv` is retained as audit evidence: 33,711 requests, 15,837 failures (46.98%), p95 270 ms. It describes the old implementation and does not establish current performance. HFT throughput, zero downtime and 15K writes/s are not promised.

[Architecture](architecture.mmd) · [Modernization status and external actions](docs/modernization.md)

## License

**Proprietary — all rights reserved.** Author: Artem Alimpiev, [ORCID](https://orcid.org/0009-0007-6740-7242). Use and redistribution require the rights holder's authorization.
