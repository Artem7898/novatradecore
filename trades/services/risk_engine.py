"""Deterministic risk rules for supported USD-denominated quote markets."""

from decimal import Decimal

from trades.domain.money import calculate_notional
from trades.schemas.requests import TradeSchemaIn
from trades.schemas.responses import RiskAssessmentOut


class RiskEngineService:
    """Score nominal quote amounts; this service is not an FX oracle."""

    MAX_SINGLE_TRADE_NOTIONAL = Decimal("1000000")

    def assess_trade_risk(self, trade: TradeSchemaIn) -> RiskAssessmentOut:
        score = Decimal("0")
        reasons: list[str] = []
        if calculate_notional(trade.price, trade.quantity) > self.MAX_SINGLE_TRADE_NOTIONAL:
            score += Decimal("60")
            reasons.append("Large trade volume")
        if trade.quantity > Decimal("10000"):
            score += Decimal("40")
            reasons.append("Suspicious qty")
        return RiskAssessmentOut(is_high_risk=score >= 50, risk_score=score, reason="; ".join(reasons) or None)
