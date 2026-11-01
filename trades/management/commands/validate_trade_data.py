"""Read-only preflight usable before and after the financial migration."""

from argparse import ArgumentParser
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count
from pydantic import ValidationError

from trades.models import Trade
from trades.schemas.requests import TradeSchemaIn


class Command(BaseCommand):
    help = "Validate legacy records before migration; never changes data"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--check-downgrade", action="store_true", help="Check global trade_id uniqueness for rollback"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if Trade._meta.db_table not in connection.introspection.table_names():
            self.stdout.write(self.style.SUCCESS("No trade table exists yet; no legacy data to validate."))
            return
        invalid = 0
        samples: list[str] = []
        rows = Trade.objects.order_by("pk").values_list(
            "id", "symbol", "side", "price", "quantity", "exchange_id", "trade_id", "risk_score"
        )
        for pk, symbol, side, price, quantity, exchange, event, risk in rows.iterator(chunk_size=1000):
            try:
                TradeSchemaIn.model_validate(
                    {
                        "symbol": symbol,
                        "side": side,
                        "price": format(price, "f"),
                        "quantity": format(quantity, "f"),
                        "exchange_id": exchange,
                        "trade_id": event,
                    }
                )
                if not isinstance(risk, Decimal) or not risk.is_finite() or not 0 <= risk <= 100:
                    raise ValueError("Invalid risk score")
            except (ValidationError, ValueError):
                invalid += 1
                if len(samples) < 10:
                    samples.append(str(pk))
        if invalid:
            raise CommandError(f"{invalid} invalid legacy trades; sample IDs: {', '.join(samples)}. No data changed.")
        if options["check_downgrade"] and (
            Trade.objects.order_by().values("trade_id").annotate(total=Count("id")).filter(total__gt=1).exists()
        ):
            raise CommandError("Cross-exchange trade_id duplicates prevent downgrade. No data changed.")
        self.stdout.write(self.style.SUCCESS("Trade data preflight passed. No data changed."))
