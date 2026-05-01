from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime

class RiskAssessmentOut(BaseModel):
    is_high_risk: bool
    risk_score: Decimal
    reason: str | None = None

class TradeSchemaOut(BaseModel):
    id: str
    symbol: str
    side: str
    price: Decimal
    quantity: Decimal
    pnl: Decimal | None = None
    risk: RiskAssessmentOut
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)