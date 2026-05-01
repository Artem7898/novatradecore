import structlog
from decimal import Decimal, InvalidOperation
from trades.schemas.requests import TradeSchemaIn
from trades.schemas.responses import RiskAssessmentOut

logger = structlog.get_logger(__name__)


class RiskEngineService:
    MAX_SINGLE_TRADE_USD = Decimal("1000000.00")

    async def assess_trade_risk(self, trade: TradeSchemaIn) -> RiskAssessmentOut:
        log = logger.bind(symbol=trade.symbol, exchange=trade.exchange_id)
        try:
            price = Decimal(trade.price)
            quantity = Decimal(trade.quantity)
            trade_volume_usd = price * quantity

            score = Decimal("0.0")
            reason: str | None = None

            if trade_volume_usd > self.MAX_SINGLE_TRADE_USD:
                score += Decimal("60.0")
                reason = "Large trade volume"

            if quantity > Decimal("10000.00"):
                score += Decimal("40.0")
                reason = f"{reason}; Suspicious qty" if reason else "Suspicious qty"

            is_high_risk = score >= Decimal("50.0")
            return RiskAssessmentOut(
                is_high_risk=is_high_risk,
                risk_score=score,
                reason=reason
            )
        except (InvalidOperation, TypeError) as e:
            log.error("risk_calc_error", error=str(e))
            raise ValueError(f"Invalid decimal math in payload: {e}")