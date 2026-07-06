from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: int


@dataclass(frozen=True)
class Signal:
    action: str
    reason: str


@dataclass(frozen=True)
class Trade:
    side: str
    entry_time: int
    exit_time: int
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal
    fee: Decimal
    reason: str
    pnl_pct: Decimal
