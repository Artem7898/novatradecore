"""Persistent trades with database-enforced financial invariants."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from django.db import models


class Trade(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol: models.CharField[str, str] = models.CharField(max_length=20, db_index=True)
    side: models.CharField[str, str] = models.CharField(max_length=4, choices=[("BUY", "BUY"), ("SELL", "SELL")])
    price: models.DecimalField[Decimal, Decimal] = models.DecimalField(max_digits=20, decimal_places=9)
    quantity: models.DecimalField[Decimal, Decimal] = models.DecimalField(max_digits=20, decimal_places=9)
    exchange_id: models.CharField[str, str] = models.CharField(max_length=50, db_index=True)
    trade_id: models.CharField[str, str] = models.CharField(max_length=100)
    # Retained only for historical data. New ingestion never writes or returns P&L.
    pnl: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    notional: models.DecimalField[Decimal, Decimal] = models.DecimalField(max_digits=40, decimal_places=18)
    quote_currency: models.CharField[str, str] = models.CharField(max_length=20)
    risk_score: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0")
    )
    risk_reason: models.CharField[str | None, str | None] = models.CharField(max_length=200, null=True, blank=True)
    is_high_risk: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True, db_index=True)

    # Django installs a model-specific manager; its base stub uses invariant Manager[Model].
    objects: ClassVar[models.Manager[Trade]] = models.Manager()  # pyright: ignore[reportIncompatibleVariableOverride]

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["symbol", "-created_at"], name="idx_trades_symbol_created")]
        constraints = [
            models.UniqueConstraint(fields=["exchange_id", "trade_id"], name="trade_exchange_event_unique"),
            models.CheckConstraint(
                condition=models.Q(price__gt=0, price__lt=Decimal("100000000000")), name="trade_price_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0, quantity__lt=Decimal("100000000000")), name="trade_quantity_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(notional__gt=0, notional__lt=Decimal("10000000000000000000000")),
                name="trade_notional_valid",
            ),
            models.CheckConstraint(condition=models.Q(risk_score__gte=0, risk_score__lte=100), name="trade_risk_valid"),
            models.CheckConstraint(condition=models.Q(side__in=["BUY", "SELL"]), name="trade_side_valid"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} {self.side} {self.quantity}@{self.price}"
