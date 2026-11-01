"""Bounded transactional batches using the same invariants as single ingestion."""

from asgiref.sync import sync_to_async
from django.db import close_old_connections, transaction

from trades.models import Trade
from trades.schemas.requests import TradeSchemaIn
from trades.services.ingest_trade import IngestTradeService


class BulkIngestorService:
    MAX_BATCH_SIZE = 5000

    def _insert(self, data: list[TradeSchemaIn]) -> list[Trade]:
        service = IngestTradeService()
        close_old_connections()
        try:
            with transaction.atomic():
                return [service.persist(item)[0] for item in data]
        finally:
            close_old_connections()

    async def bulk_insert_trades(self, data: list[TradeSchemaIn]) -> list[Trade]:
        """Commit a validated batch atomically; no throughput guarantee is implied."""
        if len(data) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch must contain at most {self.MAX_BATCH_SIZE} trades")
        return await sync_to_async(self._insert, thread_sensitive=True)(data) if data else []
