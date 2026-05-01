import pytest
from django.test import AsyncClient
from trades.models import Trade


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_ingest_trade_success():
    client = AsyncClient()
    payload = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "price": "65000.000000000",
        "quantity": "1.500000000",
        "exchange_id": "binance",
        "trade_id": "test_txn_001"
    }

    response = await client.post("/api/v1/trades/ingest/", payload, content_type="application/json")

    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "BTC/USDT"
    assert data["risk"]["is_high_risk"] is False

    # Проверяем, что Decimal не превратился в float (в JSON он строка)
    assert data["price"] == "65000.000000000"

    # Проверка БД
    assert await Trade.objects.acount() == 1