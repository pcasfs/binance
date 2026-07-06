from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_notional: Decimal


@dataclass(frozen=True)
class QuantityPlan:
    raw_quantity: Decimal
    quantity: Decimal
    notional: Decimal
    is_valid: bool
    reason: str


def parse_symbol_rules(symbol_info: dict[str, Any]) -> SymbolRules:
    filters = {item["filterType"]: item for item in symbol_info.get("filters", [])}
    lot_filter = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE") or {}
    min_notional_filter = filters.get("MIN_NOTIONAL") or {}
    min_notional = min_notional_filter.get("notional") or min_notional_filter.get("minNotional") or "0"
    return SymbolRules(
        symbol=str(symbol_info["symbol"]),
        min_qty=Decimal(str(lot_filter.get("minQty", "0"))),
        max_qty=Decimal(str(lot_filter.get("maxQty", "0"))),
        step_size=Decimal(str(lot_filter.get("stepSize", "1"))),
        min_notional=Decimal(str(min_notional)),
    )


def plan_order_quantity(usdt_per_trade: Decimal, mark_price: Decimal, rules: SymbolRules) -> QuantityPlan:
    raw_quantity = usdt_per_trade / mark_price
    quantity = round_down(raw_quantity, rules.step_size)
    notional = quantity * mark_price

    if quantity <= 0:
        return QuantityPlan(raw_quantity, quantity, notional, False, "quantity rounds down to zero")
    if rules.min_qty > 0 and quantity < rules.min_qty:
        return QuantityPlan(raw_quantity, quantity, notional, False, f"quantity below minQty {rules.min_qty}")
    if rules.max_qty > 0 and quantity > rules.max_qty:
        return QuantityPlan(raw_quantity, quantity, notional, False, f"quantity above maxQty {rules.max_qty}")
    if rules.min_notional > 0 and notional < rules.min_notional:
        return QuantityPlan(raw_quantity, quantity, notional, False, f"notional below minNotional {rules.min_notional}")
    return QuantityPlan(raw_quantity, quantity, notional, True, "ok")


def round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value // step) * step


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
