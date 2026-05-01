from django.contrib import admin
from trades.models import Trade  # Импортируем из модуля models!

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("id", "symbol", "side", "price", "quantity", "exchange_id", "is_high_risk", "created_at")
    list_filter = ("symbol", "side", "exchange_id", "is_high_risk", "created_at")
    search_fields = ("trade_id", "symbol")
    readonly_fields = ("id", "trade_id", "created_at")
    ordering = ("-created_at",)