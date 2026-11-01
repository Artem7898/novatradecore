from trades.services.ingest_trade import IngestTradeService


def get_ingest_service() -> IngestTradeService:
    return IngestTradeService()
