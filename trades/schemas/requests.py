"""The single wire contract for normalized trade ingestion."""

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

_DECIMAL_STRING = re.compile(r"(?:0|[1-9][0-9]{0,10})(?:\.[0-9]{1,9})?", re.ASCII)


class TradeSchemaIn(BaseModel):
    """Accept financial amounts only as bounded, positive decimal strings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9]{1,14}/(?:USD|USDT|USDC)$")
    side: Literal["BUY", "SELL"]
    price: Decimal = Field(gt=0, max_digits=20, decimal_places=9, allow_inf_nan=False)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=9, allow_inf_nan=False)
    exchange_id: str = Field(min_length=1, max_length=50, pattern=r"^\S+$")
    trade_id: str = Field(min_length=1, max_length=100, pattern=r"^\S+$")

    @field_validator("price", "quantity", mode="before")
    @classmethod
    def parse_money(cls, value: object) -> Decimal:
        """Reject floats, exponents and excess precision before Decimal math."""
        if not isinstance(value, str) or len(value) > 21 or _DECIMAL_STRING.fullmatch(value) is None:
            raise ValueError("Use an unsigned decimal string with at most 11 integer and 9 fractional digits")
        return Decimal(value)

    @field_serializer("price", "quantity", when_used="json")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")

    @property
    def quote_currency(self) -> str:
        return self.symbol.rsplit("/", 1)[1]
