from __future__ import annotations

from decimal import Decimal


def pnl_pct(side: str, entry_price: Decimal, current_price: Decimal) -> Decimal:
    if side == "LONG":
        return (current_price - entry_price) / entry_price
    return (entry_price - current_price) / entry_price


def exit_reason(side: str, entry_price: Decimal, high: Decimal, low: Decimal, stop_loss_pct: Decimal, take_profit_pct: Decimal) -> tuple[str, Decimal] | None:
    if side == "LONG":
        stop = entry_price * (Decimal("1") - stop_loss_pct)
        target = entry_price * (Decimal("1") + take_profit_pct)
        if low <= stop:
            return "stop_loss", stop
        if high >= target:
            return "take_profit", target
    else:
        stop = entry_price * (Decimal("1") + stop_loss_pct)
        target = entry_price * (Decimal("1") - take_profit_pct)
        if high >= stop:
            return "stop_loss", stop
        if low <= target:
            return "take_profit", target
    return None
