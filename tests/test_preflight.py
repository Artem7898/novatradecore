"""Read-only preflight works for legacy schemas and never prints trade payloads."""

from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from uuid import UUID

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from trades.models import Trade


def test_preflight_succeeds_before_trade_table_exists() -> None:
    output = StringIO()
    with (
        patch("django.db.connection.introspection.table_names", return_value=[]),
        patch("trades.management.commands.validate_trade_data.Trade.objects") as manager,
    ):
        call_command("validate_trade_data", stdout=output)
    manager.order_by.assert_not_called()
    assert output.getvalue()


@pytest.mark.parametrize("risk", [Decimal("0"), Decimal("NaN"), Decimal("101")])
def test_invalid_legacy_data_reports_only_record_ids(risk: Decimal) -> None:
    record_id = UUID("11111111-1111-4111-8111-111111111111")
    sensitive_values = ["SECRET/USDT", "private-exchange", "private-event"]
    price = Decimal("-1") if risk == 0 else Decimal("1")
    row = (record_id, sensitive_values[0], "BUY", price, Decimal("2"), *sensitive_values[1:], risk)
    with (
        patch("django.db.connection.introspection.table_names", return_value=["trades_trade"]),
        patch("trades.management.commands.validate_trade_data.Trade.objects") as manager,
    ):
        manager.order_by.return_value.values_list.return_value.iterator.return_value = iter([row])
        with pytest.raises(CommandError) as failure:
            call_command("validate_trade_data", stdout=StringIO())
    message = str(failure.value)
    assert str(record_id) in message
    assert "1 invalid legacy trades" in message
    assert all(value not in message for value in sensitive_values)


def test_preflight_limits_samples_without_losing_invalid_count() -> None:
    records = [
        (UUID(int=number), "SOL/USDT", "BUY", Decimal("0"), Decimal("1"), "binance", "event", Decimal("0"))
        for number in range(1, 13)
    ]
    with (
        patch("django.db.connection.introspection.table_names", return_value=["trades_trade"]),
        patch("trades.management.commands.validate_trade_data.Trade.objects") as manager,
    ):
        manager.order_by.return_value.values_list.return_value.iterator.return_value = iter(records)
        with pytest.raises(CommandError) as failure:
            call_command("validate_trade_data", stdout=StringIO())
    message = str(failure.value)
    assert "12 invalid legacy trades" in message
    assert str(UUID(int=10)) in message
    assert str(UUID(int=11)) not in message


@pytest.mark.django_db(transaction=True)
def test_valid_current_rows_pass_without_being_changed() -> None:
    trade = Trade.objects.create(
        symbol="SOL/USDT",
        side="BUY",
        price=Decimal("150.25"),
        quantity=Decimal("10.5"),
        notional=Decimal("1577.625"),
        quote_currency="USDT",
        exchange_id="binance",
        trade_id="preflight-valid",
        risk_score=Decimal("0"),
        pnl=Decimal("7.25"),
    )
    before = list(Trade.objects.values())
    output = StringIO()
    call_command("validate_trade_data", stdout=output)
    assert "passed" in output.getvalue()
    assert list(Trade.objects.values()) == before
    assert Trade.objects.get(pk=trade.pk).pnl == Decimal("7.25")


@pytest.mark.django_db(transaction=True)
def test_downgrade_preflight_rejects_cross_exchange_duplicates_without_changes() -> None:
    fields = {
        "symbol": "SOL/USDT",
        "side": "BUY",
        "price": Decimal("150.25"),
        "quantity": Decimal("10.5"),
        "notional": Decimal("1577.625"),
        "quote_currency": "USDT",
        "trade_id": "same-event",
        "risk_score": Decimal("0"),
    }
    Trade.objects.create(**fields, exchange_id="binance")
    Trade.objects.create(**fields, exchange_id="another-exchange")
    with pytest.raises(CommandError, match="Cross-exchange trade_id duplicates prevent downgrade"):
        call_command("validate_trade_data", check_downgrade=True, stdout=StringIO())
    assert Trade.objects.count() == 2
