"""Public API tests use real persistence and exercise delivery semantics."""

from decimal import Decimal
from uuid import UUID

import pytest
from django.db import connection
from django.test import AsyncClient

from trades.models import Trade

pytestmark = pytest.mark.django_db(transaction=True)
URL = "/api/v1/trades/ingest/"


async def test_ingest_persists_exact_money_and_notional(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    response = await AsyncClient().post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    assert response.status_code == 201
    result = response.json()
    saved = await Trade.objects.aget(id=UUID(result["id"]))
    assert saved.price == Decimal("150.250000000")
    assert saved.quantity == Decimal("10.500000000")
    assert saved.notional == Decimal("1577.625000000000000000")
    assert Decimal(result["price"]) == saved.price
    assert Decimal(result["quantity"]) == saved.quantity
    assert Decimal(result["notional"]) == saved.notional
    assert all(isinstance(result[field], str) for field in ("price", "quantity", "notional"))
    assert result["quote_currency"] == "USDT"
    assert result["risk"]["is_high_risk"] is False
    assert result["created_at"]
    assert "pnl" not in result


@pytest.mark.postgresql
async def test_maximum_amounts_preserve_full_product(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("SQLite cannot guarantee PostgreSQL numeric(40,18) precision")
    amount = "99999999999.999999999"
    response = await AsyncClient().post(
        URL,
        {**trade_payload, "price": amount, "quantity": amount},
        content_type="application/json",
        headers=auth_headers,
    )
    assert response.status_code == 201
    result = response.json()
    expected = Decimal("9999999999999999999800.000000000000000001")
    assert Decimal(result["notional"]) == expected
    saved = await Trade.objects.aget(id=result["id"])
    assert saved.notional == expected


async def test_replayed_trade_is_idempotent(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    client = AsyncClient()
    first = await client.post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    replay = await client.post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert await Trade.objects.acount() == 1


async def test_equivalent_decimal_spellings_replay_the_same_event(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    client = AsyncClient()
    first = await client.post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    replay = await client.post(
        URL,
        {**trade_payload, "price": "150.25", "quantity": "10.5"},
        content_type="application/json",
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert await Trade.objects.acount() == 1


async def test_conflicting_replay_does_not_change_saved_trade(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    client = AsyncClient()
    first = await client.post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    conflict = await client.post(
        URL,
        {**trade_payload, "price": "999"},
        content_type="application/json",
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert conflict.status_code == 409
    assert await Trade.objects.acount() == 1
    assert (await Trade.objects.aget()).price == Decimal(trade_payload["price"])


async def test_trade_id_is_scoped_to_exchange(
    trade_payload: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    client = AsyncClient()
    first = await client.post(URL, trade_payload, content_type="application/json", headers=auth_headers)
    other = await client.post(
        URL,
        {**trade_payload, "exchange_id": "other-exchange"},
        content_type="application/json",
        headers=auth_headers,
    )
    assert first.status_code == other.status_code == 201
    assert first.json()["id"] != other.json()["id"]
    assert await Trade.objects.acount() == 2
