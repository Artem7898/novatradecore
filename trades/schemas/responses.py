"""JSON response contracts; monetary values serialize as plain strings."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class RiskAssessmentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_high_risk: bool
    risk_score: Decimal = Field(ge=0, le=100)
    reason: str | None = None


class TradeSchemaOut(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    price: Decimal
    quantity: Decimal
    notional: Decimal
    quote_currency: str
    risk: RiskAssessmentOut
    created_at: datetime

    @field_serializer("price", "quantity", "notional", when_used="json")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")
