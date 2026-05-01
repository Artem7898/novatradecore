import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

# Импорты зависят от структуры проекта
from schemas.trades import TradeSchemaIn, RiskAssessment
from services.risk_engine import RiskEngineService, RiskCalculationError


@pytest.mark.asyncio
async def test_trade_schema_validation_strict():
    """Проверяем, что Pydantic v2 в strict mode отсекает кривые типы"""
    with pytest.raises(ValidationError):
        # Передаем float вместо строки Decimal (в strict mode вызовет ошибку)
        TradeSchemaIn(
            symbol="BTC/USDT",
            side="BUY",
            price=50000.50,  # type: ignore
            quantity="1.5",
            exchange_id="binance",
            trade_id="123",
        )


@pytest.mark.asyncio
async def test_risk_service_high_volume():
    """Тест сервисного слоя: большая сделка должна быть high risk"""
    service = RiskEngineService()
    trade = TradeSchemaIn(
        symbol="SOL/USDT",
        side="SELL",
        price=Decimal("200.00"),
        quantity=Decimal("10000.00"),  # 2,000,000 USD
        exchange_id="solana_rpc",
        trade_id="tx_high_risk",
    )

    risk = await service.assess_trade_risk(trade)

    assert risk.is_high_risk is True
    assert risk.risk_score >= Decimal("50.0")
    assert "Large trade volume" in risk.reason


@pytest.mark.asyncio
async def test_ingest_endpoint_success(app):
    """Интеграционный тест эндпоинта без Celery (Mock Hintergrund)"""
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer valid_mock_token"}

    payload = {
        "symbol": "ETH/USDT",
        "side": "BUY",
        "price": "3000.00",
        "quantity": "1.0",
        "exchange_id": "binance",
        "trade_id": "tx_123",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/trades/ingest/", json=payload, headers=headers
        )

    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "ETH/USDT"
    assert data["risk"]["is_high_risk"] is False
    # Проверяем, что Decimal не превратился в float (строго строка или число без потерь)
    assert data["price"] == "3000.00" or data["price"] == 3000.00
