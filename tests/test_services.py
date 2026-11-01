"""Business boundaries remain deterministic and independent of HTTP or storage."""

from decimal import Decimal, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trades.domain.money import calculate_notional
from trades.schemas.requests import TradeSchemaIn
from trades.services.risk_engine import RiskEngineService


@pytest.mark.parametrize(
    ("price", "quantity", "expected_score", "high_risk"),
    [
        ("100", "1", "0", False),
        ("100", "10000", "0", False),
        ("100.000000001", "10000", "60", True),
        ("1", "10000.000000001", "40", False),
        ("200", "10000.000000001", "100", True),
    ],
)
def test_risk_boundaries(
    trade_payload: dict[str, str],
    price: str,
    quantity: str,
    expected_score: str,
    high_risk: bool,
) -> None:
    trade = TradeSchemaIn.model_validate({**trade_payload, "price": price, "quantity": quantity})
    result = RiskEngineService().assess_trade_risk(trade)
    assert result.risk_score == Decimal(expected_score)
    assert result.is_high_risk is high_risk
    assert Decimal("0") <= result.risk_score <= Decimal("100")


def test_large_volume_reason_is_present(trade_payload: dict[str, str]) -> None:
    trade = TradeSchemaIn.model_validate({**trade_payload, "price": "200", "quantity": "10000"})
    result = RiskEngineService().assess_trade_risk(trade)
    assert result.is_high_risk
    assert result.reason and "Large trade volume" in result.reason


def test_notional_is_exact_even_with_small_callers_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 6
        actual = calculate_notional(Decimal("99999999999.999999999"), Decimal("99999999999.999999999"))
    assert actual == Decimal("9999999999999999999800.000000000000000001")


@given(a=st.integers(min_value=1, max_value=10**20 - 1), b=st.integers(min_value=1, max_value=10**20 - 1))
def test_notional_matches_integer_arithmetic(a: int, b: int) -> None:
    price = Decimal(f"{a // 10**9}.{a % 10**9:09d}")
    quantity = Decimal(f"{b // 10**9}.{b % 10**9:09d}")
    product = a * b
    expected = Decimal(f"{product // 10**18}.{product % 10**18:018d}")
    assert calculate_notional(price, quantity) == expected
