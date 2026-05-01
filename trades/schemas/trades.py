from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class TradeSchemaIn(BaseModel):
    """Схема входящего normalized события от NovaTask"""
    symbol: str = Field(..., min_length=1, max_length=20, examples=["SOL/USDT"])
    side: Literal["BUY", "SELL"]
    price: Decimal = Field(..., gt=0, decimal_places=9, examples=["150.25"])
    quantity: Decimal = Field(..., gt=0, decimal_places=9, examples=["10.5"])
    exchange_id: str = Field(..., examples=["binance", "solana_rpc"])
    trade_id: str = Field(..., examples=["txn_8x9z..."])

    model_config = ConfigDict(frozen=True)  # Иммутабельность для потокобезопасности


class RiskAssessment(BaseModel):
    is_high_risk: bool
    risk_score: Decimal = Field(..., ge=0, le=100)
    reason: str | None = None


class TradeSchemaOut(BaseModel):
    """Ответ API для фронтенда сгенерирует TS-типы"""
    id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    price: Decimal
    quantity: Decimal
    pnl: Decimal | None = None  # Strict null check для Pyright
    risk: RiskAssessment
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)  # Для маппинга из SQLModel/NovaModel