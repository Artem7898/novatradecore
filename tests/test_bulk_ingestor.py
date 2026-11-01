"""Bulk ingestion has the same delivery contract and atomicity as a single trade."""

from decimal import Decimal

import pytest

from trades.models import Trade
from trades.schemas.requests import TradeSchemaIn
from trades.services.bulk_ingestor import BulkIngestorService


async def test_empty_batch_needs_no_database() -> None:
    assert await BulkIngestorService().bulk_insert_trades([]) == []


async def test_oversized_batch_is_rejected_before_storage(trade_payload: dict[str, str]) -> None:
    trade = TradeSchemaIn.model_validate(trade_payload)
    with pytest.raises(ValueError):
        await BulkIngestorService().bulk_insert_trades([trade] * 5001)


@pytest.mark.django_db(transaction=True)
async def test_batch_preserves_order_and_replays_identical_events(trade_payload: dict[str, str]) -> None:
    first = TradeSchemaIn.model_validate(trade_payload)
    second = TradeSchemaIn.model_validate({**trade_payload, "trade_id": "trade-002", "price": "200"})
    results = await BulkIngestorService().bulk_insert_trades([second, first, second])
    assert [trade.trade_id for trade in results] == ["trade-002", "trade-001", "trade-002"]
    assert results[0].id == results[2].id
    assert results[0].notional == Decimal("2100")
    assert await Trade.objects.acount() == 2


@pytest.mark.django_db(transaction=True)
async def test_conflicting_event_rolls_back_entire_batch(trade_payload: dict[str, str]) -> None:
    first = TradeSchemaIn.model_validate(trade_payload)
    conflicting = TradeSchemaIn.model_validate({**trade_payload, "price": "999"})
    with pytest.raises(ValueError):
        await BulkIngestorService().bulk_insert_trades([first, conflicting])
    assert await Trade.objects.acount() == 0
