<div align="center">

# NovaTradeCore

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0-green.svg)](https://www.djangoproject.com/)
[![Type Checker](https://img.shields.io/badge/pyright-strict-red.svg)](https://github.com/microsoft/pyright)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

**High-performance trade ingestion and risk assessment engine for DeFi ecosystems**

Strict Typing · Decimal Arithmetic · Native Async · Zero-downtime

</div>

---

## Overview

**NovaTradeCore** is a high-performance trade ingestion and risk assessment engine built for DeFi ecosystems. The project enforces strict type safety, uses `Decimal` for all financial calculations (no `float` allowed for P&L), and features a fully asynchronous architecture — ready for high-frequency trading workloads.

---

## Key Architectural Solutions

| Solution | Description |
|----------|-------------|
| **Strict Type Safety** | `pyright --strict` + Pydantic v2 + Django ORM with `Decimal` everywhere. No implicit `float` in P&L. |
| **Native Async (Django 5 + psycopg3)** | Full async request handling, async ORM methods, no `sync_to_async` bottlenecks. |
| **No-Celery Architecture** | Background tasks handled by lightweight async workers (`NovaTask`) + RabbitMQ/Kafka. |
| **Smart Cache Eviction** | Adaptive TTL and eviction policies for hot trade symbols. |
| **Hot Migrations** | `CREATE INDEX CONCURRENTLY` and zero-downtime schema changes. |

---

## Quick Launch (Docker)

All services (PostgreSQL, Redis, Grafana, Uvicorn) are orchestrated with Docker Compose.

### 1. Clone & Environment

```bash
git clone <your-repo-link>
cd novatradecore
cp .env.example .env
```

### 2. Build & Run

```bash
docker compose up --build -d
```

### 3. Access

| Service | URL | Credentials |
|---------|-----|-------------|
| API & Admin Panel | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | Set in `.env` — change immediately after launch |
| Grafana | [http://127.0.0.1:3000/](http://127.0.0.1:3000/) | `admin` / `admin` |

---

## Monitoring Setup (Grafana)

Grafana automatically connects to the built-in PostgreSQL data source.

### Add Data Source

1. Go to **Connections → Add data source → PostgreSQL**
2. Fill in the parameters:

| Parameter | Value |
|-----------|-------|
| Host | `postgres:5432` |
| Database | `novatrade` |
| User | `nova` |
| Password | `nova_pass` |

---

## Example Queries

### Requests per second (RPS)

```sql
SELECT 
  DATE_TRUNC('minute', created_at) AS time,
  COUNT(id) AS requests
FROM trades_trade 
GROUP BY time 
ORDER BY time;
```

### High-risk trade ratio

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

## Load Testing (Locust)

A `locustfile.py` is included to simulate HFT traffic.

### Running Tests

```bash
# 1. Start the stack
docker compose up -d

# 2. Install Locust (or run inside a container)
pip install locust
locust -f locustfile.py --host http://127.0.0.1:8000
```

3. Open [http://localhost:8089](http://localhost:8089)
4. Set the number of users (e.g., 50) and ramp-up time (10 seconds)

**Expected Result:** 200–500 RPS on modest hardware with no noticeable latency degradation.

---

## Local Setup (Bare Metal)

If you prefer running without Docker (you'll need a local PostgreSQL instance):

```bash
pip install -e ".[dev]"
cp .env.example .env
# Edit .env to point to your local postgres (e.g., 127.0.0.1)
python manage.py migrate --skip-checks
python manage.py runserver 0.0.0.0:8000
```

---

## Code Quality (Pyright Strict)

Enforce `Decimal` everywhere and catch type errors:

```bash
pyright .
```

**Expected Output:** `0 errors, 0 warnings`. All `float` usage in P&L or risk metrics is forbidden.

---

## Testing

```bash
pytest -v --cov=trades --cov-report=term-missing
```

Coverage includes async endpoint tests, Decimal math verification, and risk engine rules.

---

## Production Recommendations

### 1. Strict Decimal Validation

Always use `Decimal` from the wire to the database.

Pydantic `TradeSchemaIn` validates inputs and rejects any numeric `float`.

### 2. Hot Migrations

Assume the `trades_trade` table can grow beyond 500M rows.
Never use standard migration that acquires `LOCK TABLE`. Instead, use `atomic = False` and manual SQL:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_created 
ON trades_trade (symbol, created_at DESC NULLS LAST);
```

`CONCURRENTLY` avoids downtime and locks.

### 3. Async Database Connections

In `settings.py`, tune `CONN_MAX_AGE` and health checks:

```python
"CONN_MAX_AGE": 60,
"CONN_HEALTH_CHECKS": True,
```

This keeps psycopg3 connection pools alive and avoids reconnects under load.

---

## License

**Proprietary** — all rights reserved.
#### The author of the project is Artem Alimpiev

This software is for authorized use only. Redistribution or reverse engineering is prohibited.

---

<div align="center">

*Built for high-frequency DeFi trade processing. No floats. No downtime.*

</div>
