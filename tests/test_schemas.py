"""The public wire contract rejects ambiguous or unrepresentable monetary values."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from trades.schemas.requests import TradeSchemaIn


@pytest.mark.parametrize("field", ["price", "quantity"])
@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-0",
        "-0.000000001",
        "-1",
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "abc",
        "",
        " ",
        "1e3",
        "1e1000000",
        "0.0000000001",
        "100000000000",
        "99999999999.9999999999",
        1,
        1.5,
        True,
        None,
    ],
)
def test_reject_invalid_money(trade_payload: dict[str, str], field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TradeSchemaIn.model_validate({**trade_payload, field: value})


@pytest.mark.parametrize("value", ["0.000000001", "1", "99999999999.999999999"])
def test_accept_representable_money(trade_payload: dict[str, str], value: str) -> None:
    trade = TradeSchemaIn.model_validate({**trade_payload, "price": value, "quantity": value})
    assert trade.price == Decimal(value)
    assert trade.quantity == Decimal(value)


@pytest.mark.parametrize("symbol", ["SOL/BTC", "ETH/ETH", "BTC", "", "btc/usdt", "A" * 20 + "/USD"])
def test_reject_unsupported_markets(trade_payload: dict[str, str], symbol: str) -> None:
    with pytest.raises(ValidationError):
        TradeSchemaIn.model_validate({**trade_payload, "symbol": symbol})


@pytest.mark.parametrize("symbol", ["SOL/USD", "BTC/USDT", "ETH/USDC"])
def test_accept_supported_quote_currencies(trade_payload: dict[str, str], symbol: str) -> None:
    assert TradeSchemaIn.model_validate({**trade_payload, "symbol": symbol}).symbol == symbol


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trade_id", ""),
        ("trade_id", " \t"),
        ("trade_id", "a" * 101),
        ("exchange_id", ""),
        ("exchange_id", " \n"),
        ("exchange_id", "a" * 51),
        ("side", "buy"),
        ("side", "HOLD"),
    ],
)
def test_reject_invalid_identifiers_and_side(trade_payload: dict[str, str], field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TradeSchemaIn.model_validate({**trade_payload, field: value})


def test_reject_unknown_fields(trade_payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        TradeSchemaIn.model_validate({**trade_payload, "risk_score": "0"})


@given(units=st.integers(min_value=1, max_value=10**20 - 1))
def test_valid_money_round_trips_without_float(units: int) -> None:
    # Generate every representable positive numeric(20,9) amount, including extremes.
    amount = f"{units // 10**9}.{units % 10**9:09d}"
    payload = {
        "symbol": "SOL/USDT",
        "side": "BUY",
        "price": amount,
        "quantity": amount,
        "exchange_id": "binance",
        "trade_id": "property-example",
    }
    trade = TradeSchemaIn.model_validate(payload)
    expected = Decimal(amount)
    assert trade.price == expected
    assert trade.quantity == expected
    serialized = trade.model_dump(mode="json")
    assert isinstance(serialized["price"], str)
    assert isinstance(serialized["quantity"], str)
    assert TradeSchemaIn.model_validate(serialized).price == expected
