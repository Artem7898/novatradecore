"""Database invariants protect financial records even when callers bypass the API."""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import DataError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from trades.models import Trade


@pytest.fixture
def stored_trade() -> Trade:
    return Trade.objects.create(
        symbol="SOL/USDT",
        side="BUY",
        price=Decimal("150.25"),
        quantity=Decimal("10.5"),
        notional=Decimal("1577.625"),
        quote_currency="USDT",
        exchange_id="binance",
        trade_id="constraint-example",
        risk_score=Decimal("0"),
        is_high_risk=False,
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("price", Decimal("0")),
        ("price", Decimal("-1")),
        ("price", Decimal("100000000000")),
        ("quantity", Decimal("0")),
        ("quantity", Decimal("-1")),
        ("quantity", Decimal("100000000000")),
        ("notional", Decimal("0")),
        ("notional", Decimal("-1")),
        ("notional", Decimal("10000000000000000000000")),
        ("risk_score", Decimal("-1")),
        ("risk_score", Decimal("100.01")),
        ("side", "HOLD"),
    ],
)
def test_database_rejects_invalid_financial_records(stored_trade: Trade, field: str, invalid: object) -> None:
    with pytest.raises((IntegrityError, DataError)), transaction.atomic():
        Trade.objects.filter(pk=stored_trade.pk).update(**{field: invalid})
    stored_trade.refresh_from_db()
    assert stored_trade.price == Decimal("150.25")
    assert stored_trade.quantity == Decimal("10.5")
    assert stored_trade.notional == Decimal("1577.625")
    assert stored_trade.risk_score == Decimal("0")
    assert stored_trade.side == "BUY"


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("field", ["price", "quantity", "notional", "risk_score"])
def test_postgresql_rejects_nan_in_numeric_columns(stored_trade: Trade, field: str) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL NaN ordering requires a real PostgreSQL constraint test")
    column = connection.ops.quote_name(field)
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE trades_trade SET {column} = 'NaN'::numeric WHERE id = %s", [stored_trade.pk])


@pytest.mark.django_db(transaction=True)
def test_financial_migration_upgrade_and_rollback_preserve_legacy_pnl() -> None:
    old_target = [("trades", "0002_add_hot_index_trades")]
    latest_target = [("trades", "0004_concurrent_symbol_index")]
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        legacy = executor.loader.project_state(old_target).apps.get_model("trades", "Trade")
        old_row = legacy.objects.create(
            symbol="SOL/USDT",
            side="BUY",
            price=Decimal("150.25"),
            quantity=Decimal("10.5"),
            exchange_id="binance",
            trade_id="legacy-upgrade",
            pnl=Decimal("7.25"),
            risk_score=Decimal("60"),
            is_high_risk=True,
        )
        # The current preflight must query only columns that existed in the old schema.
        call_command("validate_trade_data", stdout=StringIO())

        MigrationExecutor(connection).migrate(latest_target)
        upgraded = Trade.objects.get(pk=old_row.pk)
        assert upgraded.notional == Decimal("1577.625")
        assert upgraded.quote_currency == "USDT"
        assert upgraded.pnl == Decimal("7.25")
        assert upgraded.risk_score == Decimal("60")
        with connection.cursor() as cursor:
            indexes = connection.introspection.get_constraints(cursor, "trades_trade")
        assert indexes["idx_trades_symbol_created"]["index"]
        assert indexes["idx_trades_symbol_created"]["columns"] == ["symbol", "created_at"]

        call_command("validate_trade_data", check_downgrade=True, stdout=StringIO())
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        legacy = executor.loader.project_state(old_target).apps.get_model("trades", "Trade")
        rolled_back = legacy.objects.get(pk=old_row.pk)
        assert rolled_back.pnl == Decimal("7.25")
        assert rolled_back.price == Decimal("150.25")
        assert rolled_back.quantity == Decimal("10.5")
        MigrationExecutor(connection).migrate(latest_target)
        assert Trade.objects.get(pk=old_row.pk).notional == Decimal("1577.625")
    finally:
        # Never leave the shared test database in a historical schema after a failure.
        MigrationExecutor(connection).migrate(latest_target)


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_invalid_legacy_record_aborts_financial_migration_atomically() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("Validate transactional DDL rollback against the production PostgreSQL backend")
    old_target = [("trades", "0002_add_hot_index_trades")]
    latest_target = [("trades", "0004_concurrent_symbol_index")]
    legacy_model = None
    record_id = None
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        legacy_model = executor.loader.project_state(old_target).apps.get_model("trades", "Trade")
        row = legacy_model.objects.create(
            symbol="SOL/USDT",
            side="BUY",
            price=Decimal("-1"),
            quantity=Decimal("10.5"),
            exchange_id="binance",
            trade_id="invalid-legacy-upgrade",
            pnl=Decimal("7.25"),
            risk_score=Decimal("0"),
            is_high_risk=False,
        )
        record_id = row.pk

        with pytest.raises(ValueError, match="violates the new contract.*Run validate_trade_data"):
            MigrationExecutor(connection).migrate(latest_target)

        # A rejected backfill must roll back its schema additions and migration record too.
        with connection.cursor() as cursor:
            columns = {column.name for column in connection.introspection.get_table_description(cursor, "trades_trade")}
        assert not {"notional", "quote_currency", "risk_reason"} & columns
        applied = MigrationRecorder(connection).applied_migrations()
        assert ("trades", "0003_financial_contract") not in applied
        assert ("trades", "0004_concurrent_symbol_index") not in applied
        unchanged = legacy_model.objects.get(pk=record_id)
        assert unchanged.price == Decimal("-1")
        assert unchanged.pnl == Decimal("7.25")

        # Repair is an explicit operator decision; retry can then complete normally.
        legacy_model.objects.filter(pk=record_id).update(price=Decimal("150.25"))
        MigrationExecutor(connection).migrate(latest_target)
        repaired = Trade.objects.get(pk=record_id)
        assert repaired.notional == Decimal("1577.625")
        assert repaired.pnl == Decimal("7.25")
    finally:
        if legacy_model is not None and record_id is not None:
            legacy_model.objects.filter(pk=record_id).update(price=Decimal("150.25"))
        MigrationExecutor(connection).migrate(latest_target)
