"""Repair the historical no-op migration for both existing and fresh installs."""

from django.db import migrations, models


def create_index(apps, schema_editor):
    concurrent = "CONCURRENTLY " if schema_editor.connection.vendor == "postgresql" else ""
    if concurrent:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT i.indisvalid FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = %s AND n.nspname = current_schema()",
                ["idx_trades_symbol_created"],
            )
            existing = cursor.fetchone()
            if existing and not existing[0]:
                raise RuntimeError("idx_trades_symbol_created is invalid; rebuild it concurrently before retrying")
    schema_editor.execute(
        f"CREATE INDEX {concurrent}IF NOT EXISTS idx_trades_symbol_created ON trades_trade (symbol, created_at DESC)"
    )


def drop_index(apps, schema_editor):
    concurrent = "CONCURRENTLY " if schema_editor.connection.vendor == "postgresql" else ""
    schema_editor.execute(f"DROP INDEX {concurrent}IF EXISTS idx_trades_symbol_created")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("trades", "0003_financial_contract")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(create_index, drop_index, atomic=False)],
            state_operations=[
                migrations.AddIndex(
                    "trade", models.Index(fields=["symbol", "-created_at"], name="idx_trades_symbol_created")
                )
            ],
        )
    ]
