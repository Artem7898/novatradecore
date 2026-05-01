from pydantic import BaseModel, Field
from typing import Literal

class TradeSchemaIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, examples=["SOL/USDT"])
    side: Literal["BUY", "SELL"]
    price: str = Field(..., examples=["150.250000000"]) # Принимаем как строку для 100% точности Decimal
    quantity: str = Field(..., examples=["10.500000000"])
    exchange_id: str = Field(..., examples=["binance"])
    trade_id: str = Field(..., examples=["txn_8x9z..."])