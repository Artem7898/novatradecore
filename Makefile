COMPOSE ?= docker compose
PRODUCTION_COMPOSE ?= docker compose -f docker-compose.production.yml
RELEASE_SERVICE ?= web
BENCHMARK_HOST ?= http://127.0.0.1:8000
BENCHMARK_USERS ?= 5
BENCHMARK_DURATION ?= 30s

.PHONY: init sync services build migrate static release up production-up down test lint check benchmark

init:
	python scripts/init_env.py

sync:
	uv sync --frozen

services:
	$(COMPOSE) up -d postgres redis

build:
	$(COMPOSE) build web

migrate:
	$(COMPOSE) run --rm $(RELEASE_SERVICE) python manage.py migrate --noinput

static:
	$(COMPOSE) run --rm $(RELEASE_SERVICE) python manage.py collectstatic --noinput

release:
	$(MAKE) migrate
	$(MAKE) static

up:
	$(MAKE) services
	$(MAKE) build
	$(MAKE) release
	$(COMPOSE) up -d web

production-up:
	$(MAKE) COMPOSE="$(PRODUCTION_COMPOSE)" services
	$(MAKE) COMPOSE="$(PRODUCTION_COMPOSE)" build
	$(PRODUCTION_COMPOSE) stop web
	$(PRODUCTION_COMPOSE) run --rm release python manage.py validate_trade_data
	$(MAKE) COMPOSE="$(PRODUCTION_COMPOSE)" RELEASE_SERVICE=release release
	$(PRODUCTION_COMPOSE) up -d web

down:
	$(COMPOSE) down

test:
	uv run --frozen pytest

lint:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen pyright

check:
	$(MAKE) lint
	$(MAKE) test

benchmark:
	uv run --frozen --group load python scripts/benchmark.py --host "$(BENCHMARK_HOST)" --users "$(BENCHMARK_USERS)" --duration "$(BENCHMARK_DURATION)"
