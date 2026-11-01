"""Exact arithmetic for the supported numeric(20, 9) operands."""

from decimal import Decimal, Inexact, localcontext


def calculate_notional(price: Decimal, quantity: Decimal) -> Decimal:
    """Multiply validated operands without the default 28-digit rounding."""
    with localcontext() as context:
        context.prec = 40
        context.traps[Inexact] = True
        return price * quantity
