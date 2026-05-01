from django.db import models
from decimal import Decimal
import uuid

class Trade(models.Model):
    """Ядро данных. В строгом режиме Pyright поля не должны быть None без явного указания."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol = models.CharField(max_length=20, db_index=True)
    side = models.CharField(max_length=4) # BUY / SELL
    price = models.DecimalField(max_digits=20, decimal_places=9)
    quantity = models.DecimalField(max_digits=20, decimal_places=9)
    exchange_id = models.CharField(max_length=50, db_index=True)
    trade_id = models.CharField(max_length=100, unique=True)
    pnl = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.0"))
    is_high_risk = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


    def __str__(self) -> str:
        return f"{self.symbol} {self.side} {self.quantity}@{self.price}"