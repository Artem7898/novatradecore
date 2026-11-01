"""Trade records are immutable in admin; writes go through ingestion invariants."""

from django.contrib import admin
from django.http import HttpRequest

from trades.models import Trade


@admin.register(Trade)
# Django's runtime ModelAdmin is not subscriptable; use the concrete model attribute.
class TradeAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    list_display = ("id", "symbol", "side", "price", "quantity", "exchange_id", "is_high_risk", "created_at")
    list_filter = ("symbol", "side", "exchange_id", "is_high_risk", "created_at")
    search_fields = ("trade_id", "symbol")
    readonly_fields = (
        "id",
        "symbol",
        "side",
        "price",
        "quantity",
        "exchange_id",
        "trade_id",
        "pnl",
        "notional",
        "quote_currency",
        "risk_score",
        "risk_reason",
        "is_high_risk",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Trade | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Trade | None = None) -> bool:
        return False
