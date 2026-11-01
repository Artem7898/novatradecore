"""Transactional ingestion, shared by HTTP and bounded batches."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import close_old_connections, transaction

from trades.domain.money import calculate_notional
from trades.models import Trade
from trades.schemas.requests import TradeSchemaIn
from trades.services.risk_engine import RiskEngineService


class TradeConflictError(ValueError):
    """An event key was reused with different trade data."""


class IngestTradeService:
    def __init__(self, risk_service: RiskEngineService | None = None) -> None:
        self.risk_service = risk_service or RiskEngineService()

    def persist(self, data: TradeSchemaIn) -> tuple[Trade, bool]:
        """Run inside the caller's synchronous transaction."""
        risk = self.risk_service.assess_trade_risk(data)
        trade, created = Trade.objects.get_or_create(
            exchange_id=data.exchange_id,
            trade_id=data.trade_id,
            defaults={
                "symbol": data.symbol,
                "side": data.side,
                "price": data.price,
                "quantity": data.quantity,
                "notional": calculate_notional(data.price, data.quantity),
                "quote_currency": data.quote_currency,
                "risk_score": risk.risk_score,
                "risk_reason": risk.reason,
                "is_high_risk": risk.is_high_risk,
            },
        )
        if not created and (trade.symbol, trade.side, trade.price, trade.quantity) != (
            data.symbol,
            data.side,
            data.price,
            data.quantity,
        ):
            raise TradeConflictError("The event key already exists with different trade data")
        return trade, created

    def _ingest(self, data: TradeSchemaIn) -> tuple[Trade, bool]:
        close_old_connections()
        try:
            with transaction.atomic():
                return self.persist(data)
        finally:
            # Non-HTTP callers do not receive Django's request-finished cleanup.
            close_old_connections()

    async def ingest(self, data: TradeSchemaIn) -> tuple[Trade, bool]:
        # Django ORM remains synchronous; keep the whole transaction on one thread.
        return await sync_to_async(self._ingest, thread_sensitive=True)(data)
