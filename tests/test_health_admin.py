"""Operational endpoints and admin cannot bypass the ingestion contract."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib import admin
from django.db import OperationalError
from django.test import AsyncClient, RequestFactory, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError

from trades.models import Trade


def test_admin_trade_mutations_are_disabled() -> None:
    model_admin = admin.site._registry[Trade]
    request = RequestFactory().get("/admin/")
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


@pytest.mark.django_db(transaction=True)
async def test_readiness_checks_database_and_cache() -> None:
    response = await AsyncClient().get("/health/ready/")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "failure", [OperationalError("private-db-detail"), RedisConnectionError("private-redis-detail")]
)
async def test_readiness_is_unavailable_without_leaking_details(failure: Exception) -> None:
    with patch("config.health.sync_to_async", return_value=AsyncMock(side_effect=failure)):
        response = await AsyncClient().get("/health/ready/")
    assert response.status_code == 503
    assert "private" not in response.content.decode()


async def test_deeply_nested_json_is_client_error(auth_headers: dict[str, str]) -> None:
    response = await AsyncClient().post(
        "/api/v1/trades/ingest/",
        "[" * 2000 + "]" * 2000,
        content_type="application/json",
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_oversized_body_is_rejected(auth_headers: dict[str, str], trade_payload: dict[str, str]) -> None:
    with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
        response = await AsyncClient().post(
            "/api/v1/trades/ingest/", trade_payload, content_type="application/json", headers=auth_headers
        )
    assert response.status_code == 413


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
async def test_concurrent_replays_create_exactly_one_trade(
    auth_headers: dict[str, str], trade_payload: dict[str, str]
) -> None:
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("Concurrent transaction acceptance requires PostgreSQL")
    responses = await asyncio.gather(
        *(
            AsyncClient().post(
                "/api/v1/trades/ingest/", trade_payload, content_type="application/json", headers=auth_headers
            )
            for _ in range(5)
        )
    )
    assert sorted(response.status_code for response in responses) == [200, 200, 200, 200, 201]
    assert len({response.json()["id"] for response in responses}) == 1
    assert await Trade.objects.acount() == 1
