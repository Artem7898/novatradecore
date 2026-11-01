"""Admission control rejects unknown clients and enforces a shared per-client quota."""

import asyncio
import os
import uuid
from unittest.mock import Mock

import pytest
from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from django.test import RequestFactory

from trades.api.security import authorize_ingest

TOKEN = "test-token-for-novatradecore-tests-0123456789"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    local_cache = caches["default"]
    if isinstance(local_cache, LocMemCache):
        local_cache.clear()
    yield
    if isinstance(local_cache, LocMemCache):
        local_cache.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization",
    ["", "Bearer", "Basic user:password", "Bearer wrong-token", "Bearer \N{SNOWMAN}", "Bearer " + "x" * 1025],
)
async def test_unknown_credentials_are_rejected(authorization):
    request = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=authorization)
    response = await authorize_ingest(request)
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_service_bearer_key_is_required_and_scheme_is_case_insensitive():
    request = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"bearer {TOKEN}")
    assert await authorize_ingest(request) is None


@pytest.mark.asyncio
async def test_no_configured_credentials_fail_closed(settings):
    settings.INGEST_API_TOKENS = {}
    request = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert (await authorize_ingest(request)).status_code == 401


@pytest.mark.asyncio
async def test_quota_returns_retry_after_and_resets_in_next_window(settings, monkeypatch):
    settings.INGEST_RATE_LIMIT = 1
    monkeypatch.setattr("trades.api.security.time", lambda: 119.0)
    request = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert await authorize_ingest(request) is None
    limited = await authorize_ingest(request)
    assert limited.status_code == 429
    assert limited["Retry-After"] == "1"
    monkeypatch.setattr("trades.api.security.time", lambda: 120.0)
    assert await authorize_ingest(request) is None


@pytest.mark.asyncio
async def test_concurrent_admission_cannot_exceed_client_quota(settings, monkeypatch):
    settings.INGEST_RATE_LIMIT = 10
    monkeypatch.setattr("trades.api.security.time", lambda: 120.0)
    requests = [
        RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}") for _ in range(30)
    ]
    responses = await asyncio.gather(*(authorize_ingest(request) for request in requests))
    assert sum(response is None for response in responses) == 10
    assert sum(response is not None and response.status_code == 429 for response in responses) == 20


@pytest.mark.asyncio
async def test_clients_have_independent_quotas(settings, monkeypatch):
    settings.INGEST_RATE_LIMIT = 1
    settings.INGEST_API_TOKENS = {"first-client": TOKEN, "second-client": "a-different-service-key-0123456789"}
    monkeypatch.setattr("trades.api.security.time", lambda: 120.0)
    first = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    second = RequestFactory().post(
        "/api/v1/trades/ingest/", HTTP_AUTHORIZATION="Bearer a-different-service-key-0123456789"
    )
    assert await authorize_ingest(first) is None
    assert (await authorize_ingest(first)).status_code == 429
    assert await authorize_ingest(second) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_operation", ["add", "incr"])
async def test_cache_outage_rejects_requests_without_logging_credentials(monkeypatch, capsys, failing_operation):
    if failing_operation == "incr":
        monkeypatch.setattr(LocMemCache, "add", Mock(return_value=False))
    monkeypatch.setattr(LocMemCache, failing_operation, Mock(side_effect=RuntimeError("redis://:sensitive@cache/0")))
    request = RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    response = await authorize_ingest(request)
    assert response.status_code == 503
    assert response["Retry-After"] == "1"
    output = capsys.readouterr().out
    assert "sensitive" not in output
    assert TOKEN not in output


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_shares_atomic_quota_across_concurrent_clients(settings, monkeypatch):
    redis_url = os.getenv("TEST_REDIS_URL")
    if redis_url is None and os.getenv("TEST_DATABASE_ENGINE") == "postgresql":
        redis_url = os.getenv("REDIS_URL")
    if redis_url is None:
        pytest.skip("Set TEST_REDIS_URL to validate admission control against Redis")
    monkeypatch.setattr("trades.api.security.time", lambda: 120.0)
    # Use an isolated prefix and expiring keys; never flush the external Redis database.
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": f"test-admission-{uuid.uuid4().hex}",
            "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
        }
    }
    settings.INGEST_RATE_LIMIT = 5
    requests = [
        RequestFactory().post("/api/v1/trades/ingest/", HTTP_AUTHORIZATION=f"Bearer {TOKEN}") for _ in range(30)
    ]
    responses = await asyncio.gather(*(authorize_ingest(request) for request in requests))
    assert sum(response is None for response in responses) == 5
    assert sum(response is not None and response.status_code == 429 for response in responses) == 25
