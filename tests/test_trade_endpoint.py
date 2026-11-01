"""Invalid requests are rejected at the public boundary before persistence."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from django.db import OperationalError
from django.test import AsyncClient

URL = "/api/v1/trades/ingest/"


async def test_missing_authorization_is_rejected(trade_payload: dict[str, str]) -> None:
    response = await AsyncClient().post(URL, trade_payload, content_type="application/json")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_authentication_precedes_payload_validation() -> None:
    response = await AsyncClient().post(URL, "{", content_type="application/json")
    assert response.status_code == 401


@pytest.mark.parametrize("body", ["{", "null", "[]", "true", '"string"'])
async def test_malformed_or_nonobject_json_is_422(body: str, auth_headers: dict[str, str]) -> None:
    response = await AsyncClient().post(URL, body, content_type="application/json", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", "-1"),
        ("quantity", "0"),
        ("price", "NaN"),
        ("price", "1e1000000"),
        ("quantity", "0.0000000001"),
        ("price", 1.5),
        ("symbol", "SOL/BTC"),
        ("trade_id", " "),
    ],
)
async def test_invalid_trade_is_422_before_persistence(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
    field: str,
    value: object,
) -> None:
    # Database access is forbidden for this test: returning 422 must need no storage.
    response = await AsyncClient().post(
        URL,
        json.dumps({**trade_payload, field: value}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_database_error_is_503_without_leaking_details(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    service = Mock()
    service.ingest = AsyncMock(side_effect=OperationalError("password=private-database-secret"))
    with patch("trades.api.v1.get_ingest_service", return_value=service):
        response = await AsyncClient().post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    assert response.status_code == 503
    assert "private-database-secret" not in response.content.decode()


async def test_only_post_is_allowed(auth_headers: dict[str, str]) -> None:
    response = await AsyncClient().get(URL, headers=auth_headers)
    assert response.status_code == 405


async def test_liveness_needs_no_database() -> None:
    response = await AsyncClient().get("/health/live/")
    assert response.status_code == 200
