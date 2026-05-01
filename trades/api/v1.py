import json
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.urls import path
import structlog

from trades.schemas.requests import TradeSchemaIn
from trades.schemas.responses import TradeSchemaOut
from trades.services.risk_engine import RiskEngineService
from trades.api.dependencies import get_risk_service
from trades.models import Trade

logger = structlog.get_logger(__name__)

@csrf_exempt
@require_POST
async def ingest_trade(request) -> JsonResponse:
    try:
        payload = json.loads(request.body)
        trade_data = TradeSchemaIn(**payload)
    except Exception as e:
        logger.warning("validation_failed", error=str(e))
        return JsonResponse({"error": "Validation error", "details": str(e)}, status=422)

    risk_service = get_risk_service()
    try:
        risk_assessment = await risk_service.assess_trade_risk(trade_data)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=503)

    price_dec = Decimal(trade_data.price)
    quantity_dec = Decimal(trade_data.quantity)

    try:
        # Идеальный метод для Django 5 + psycopg (работает через async I/O, без потоков)
        trade = await Trade.objects.acreate(
            symbol=trade_data.symbol,
            side=trade_data.side,
            price=price_dec,
            quantity=quantity_dec,
            exchange_id=trade_data.exchange_id,
            trade_id=trade_data.trade_id,
            pnl=(price_dec * quantity_dec) if risk_assessment.is_high_risk else None,
            risk_score=risk_assessment.risk_score,
            is_high_risk=risk_assessment.is_high_risk,
        )
    except Exception as e:
        logger.error("db_save_failed", error=str(e))
        # Если дубликат (trade_id) или БД упала — возвращаем 503, но НЕ убиваем сервер
        return JsonResponse({"error": "Database error"}, status=503)

    response_obj = TradeSchemaOut(
        id=str(trade.id),
        symbol=trade.symbol,
        side=trade.side,
        price=trade.price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        risk=risk_assessment,
        created_at=trade.created_at,
    )

    logger.info("trade_ingested", trade_id=trade.trade_id, is_high_risk=trade.is_high_risk)

    # mode='json' заставляет Pydantic конвертировать Decimal в строки для JSON
    return JsonResponse(
        response_obj.model_dump(mode='json'),
        status=201
    )

urlpatterns = [
    path("ingest/", ingest_trade, name="ingest_trade"),
]