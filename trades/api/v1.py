"""Authenticated HTTP adapter for transactional trade ingestion."""

import json
from typing import Literal, cast

import structlog
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from trades.api.dependencies import get_ingest_service
from trades.api.security import authorize_ingest
from trades.schemas.requests import TradeSchemaIn
from trades.schemas.responses import RiskAssessmentOut, TradeSchemaOut
from trades.services.ingest_trade import TradeConflictError

logger = structlog.get_logger(__name__)


@csrf_exempt
@require_POST
async def ingest_trade(request: HttpRequest) -> JsonResponse:
    denied = await authorize_ingest(request)
    if denied is not None:
        return denied
    try:
        data = TradeSchemaIn.model_validate(json.loads(request.body))
    except RequestDataTooBig:
        return JsonResponse({"error": "Request body too large"}, status=413)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError, RecursionError):
        return JsonResponse({"error": "Invalid trade payload"}, status=422)

    try:
        trade, created = await get_ingest_service().ingest(data)
    except TradeConflictError:
        return JsonResponse({"error": "Event key conflicts with an existing trade"}, status=409)
    except DatabaseError:
        logger.error("trade_storage_unavailable")
        return JsonResponse({"error": "Trade storage unavailable"}, status=503)

    result = TradeSchemaOut(
        id=str(trade.id),
        symbol=trade.symbol,
        side=cast(Literal["BUY", "SELL"], trade.side),
        price=trade.price,
        quantity=trade.quantity,
        notional=trade.notional,
        quote_currency=trade.quote_currency,
        risk=RiskAssessmentOut(risk_score=trade.risk_score, is_high_risk=trade.is_high_risk, reason=trade.risk_reason),
        created_at=trade.created_at,
    )
    logger.info("trade_ingested", created=created, exchange=data.exchange_id)
    return JsonResponse(result.model_dump(mode="json"), status=201 if created else 200)


urlpatterns = [path("ingest/", ingest_trade, name="ingest_trade")]
