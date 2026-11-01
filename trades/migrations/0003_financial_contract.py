"""Preserve legacy P&L while introducing exact notional and event identity.

Transactional data validation/backfill can lock a large table. Run preflight and
take a backup in a maintenance window; this migration does not promise zero downtime.
"""

import re
from decimal import Decimal, Inexact, localcontext

from django.db import migrations, models


def backfill(apps, schema_editor):
    Trade = apps.get_model("trades", "Trade")
    alias = schema_editor.connection.alias
    pattern = re.compile(r"[A-Z0-9]{1,14}/(?:USD|USDT|USDC)")
    batch = []
    for trade in Trade.objects.using(alias).order_by("pk").iterator(chunk_size=1000):
        if (
            not trade.price.is_finite()
            or not trade.quantity.is_finite()
            or not 0 < trade.price < Decimal("100000000000")
            or not 0 < trade.quantity < Decimal("100000000000")
            or not trade.risk_score.is_finite()
            or not 0 <= trade.risk_score <= 100
            or trade.side not in ("BUY", "SELL")
            or pattern.fullmatch(trade.symbol) is None
            or not trade.exchange_id
            or any(c.isspace() for c in trade.exchange_id)
            or not trade.trade_id
            or any(c.isspace() for c in trade.trade_id)
        ):
            raise ValueError(
                f"Legacy trade {trade.pk} violates the new contract. "
                "Run validate_trade_data and explicitly repair invalid records before retrying."
            )
        with localcontext() as context:
            context.prec = 40
            context.traps[Inexact] = True
            trade.notional = trade.price * trade.quantity
        trade.quote_currency = trade.symbol.rsplit("/", 1)[1]
        batch.append(trade)
        if len(batch) == 1000:
            Trade.objects.using(alias).bulk_update(batch, ["notional", "quote_currency"], batch_size=1000)
            batch.clear()
    if batch:
        Trade.objects.using(alias).bulk_update(batch, ["notional", "quote_currency"], batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [("trades", "0002_add_hot_index_trades")]

    operations = [
        migrations.AddField("trade", "notional", models.DecimalField(max_digits=40, decimal_places=18, null=True)),
        migrations.AddField("trade", "quote_currency", models.CharField(max_length=20, null=True)),
        migrations.AddField("trade", "risk_reason", models.CharField(max_length=200, null=True, blank=True)),
        migrations.RunPython(backfill, migrations.RunPython.noop),
        migrations.AlterField("trade", "notional", models.DecimalField(max_digits=40, decimal_places=18)),
        migrations.AlterField("trade", "quote_currency", models.CharField(max_length=20)),
        migrations.AlterField(
            "trade", "pnl", models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)
        ),
        migrations.AlterField(
            "trade", "side", models.CharField(max_length=4, choices=[("BUY", "BUY"), ("SELL", "SELL")])
        ),
        migrations.AlterField("trade", "trade_id", models.CharField(max_length=100)),
        migrations.AddConstraint(
            "trade", models.UniqueConstraint(fields=["exchange_id", "trade_id"], name="trade_exchange_event_unique")
        ),
        migrations.AddConstraint(
            "trade",
            models.CheckConstraint(
                condition=models.Q(price__gt=0, price__lt=Decimal("100000000000")), name="trade_price_valid"
            ),
        ),
        migrations.AddConstraint(
            "trade",
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0, quantity__lt=Decimal("100000000000")), name="trade_quantity_valid"
            ),
        ),
        migrations.AddConstraint(
            "trade",
            models.CheckConstraint(
                condition=models.Q(notional__gt=0, notional__lt=Decimal("10000000000000000000000")),
                name="trade_notional_valid",
            ),
        ),
        migrations.AddConstraint(
            "trade",
            models.CheckConstraint(condition=models.Q(risk_score__gte=0, risk_score__lte=100), name="trade_risk_valid"),
        ),
        migrations.AddConstraint(
            "trade", models.CheckConstraint(condition=models.Q(side__in=["BUY", "SELL"]), name="trade_side_valid")
        ),
    ]
