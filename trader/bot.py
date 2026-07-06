from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from trader.binance_client import BinanceFuturesClient
from trader.config import Settings
from trader.models import Candle
from trader.presets import apply_symbol_preset
from trader.risk import pnl_pct
from trader.strategy import Strategy, build_strategy
from trader.symbol_rules import SymbolRules, plan_order_quantity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LivePosition:
    side: str
    amount: Decimal
    entry_price: Decimal
    mark_price: Decimal
    notional: Decimal

    @property
    def is_open(self) -> bool:
        return self.amount != 0


class TradingBot:
    def __init__(
        self,
        settings: Settings,
        symbols: list[str] | None = None,
        interval: str | None = None,
        preset: str = "default",
    ) -> None:
        base_interval = interval or settings.interval
        self.symbols = [symbol.upper() for symbol in (symbols or [settings.symbol])]
        self.symbol_settings = {
            symbol: apply_symbol_preset(settings, preset, symbol, base_interval)
            for symbol in self.symbols
        }
        self.settings = settings
        if not settings.dry_run and (not settings.api_key or not settings.api_secret):
            raise ValueError("API keys are required to run live trading with DRY_RUN=false.")
        self.client = BinanceFuturesClient(settings.api_key, settings.api_secret, settings.testnet)
        self.strategies: dict[str, Strategy] = {
            symbol: build_strategy(symbol_settings)
            for symbol, symbol_settings in self.symbol_settings.items()
        }
        self.last_action: dict[str, str | None] = {symbol: None for symbol in self.symbols}
        self.daily_date = datetime.now(timezone.utc).date()
        self.daily_realized_pnl = Decimal("0")
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
        self._symbol_rules: dict[str, SymbolRules] = {}

    def run_forever(self) -> None:
        first_settings = next(iter(self.symbol_settings.values()))
        logger.info(
            "Starting live bot symbols=%s interval=%s testnet=%s dry_run=%s",
            ",".join(self.symbols),
            first_settings.interval,
            self.settings.testnet,
            self.settings.dry_run,
        )
        while True:
            try:
                self.tick()
            except KeyboardInterrupt:
                logger.info("Stopped by user.")
                return
            except Exception:
                logger.exception("Tick failed.")
            time.sleep(self.settings.poll_seconds)

    def tick(self) -> None:
        self._roll_daily_state_if_needed()
        for symbol in self.symbols:
            self._tick_symbol(symbol)

    def _tick_symbol(self, symbol: str) -> None:
        settings = self.symbol_settings[symbol]
        strategy = self.strategies[symbol]
        raw = self.client.get_klines(symbol, settings.interval, limit=max(300, strategy.warmup_candles + 20))
        candles = [
            Candle(int(item[0]), Decimal(item[1]), Decimal(item[2]), Decimal(item[3]), Decimal(item[4]), Decimal(item[5]), int(item[6]))
            for item in raw
        ]
        signal = strategy.signal(candles)
        mark_price = self.client.mark_price(symbol)
        self._manage_open_positions(symbol, settings, mark_price)
        logger.info("%s signal=%s reason=%s mark=%s", symbol, signal.action, signal.reason, mark_price)
        if signal.action in {"LONG", "SHORT"} and signal.action != self.last_action[symbol]:
            if self._order(symbol, settings, signal.action, mark_price):
                self.last_action[symbol] = signal.action

    def _order(self, symbol: str, settings: Settings, action: str, mark_price: Decimal) -> bool:
        if self._has_open_position(symbol, mark_price):
            logger.info("%s entry blocked: symbol already has an open position.", symbol)
            return False
        if self._daily_loss_limit_hit(settings):
            logger.warning("%s entry blocked: daily loss limit reached.", symbol)
            return False
        if self._cooldown_active():
            logger.warning("%s entry blocked: cooldown is active.", symbol)
            return False
        if self._funding_unfavorable(symbol, action, settings):
            logger.info("%s entry blocked: funding rate is unfavorable for %s.", symbol, action)
            return False

        side = "BUY" if action == "LONG" else "SELL"
        quantity_plan = plan_order_quantity(
            Decimal(str(settings.usdt_per_trade)),
            mark_price,
            self._rules(symbol),
        )
        if not quantity_plan.is_valid:
            logger.warning("%s entry blocked: invalid order quantity: %s", symbol, quantity_plan.reason)
            return False
        quantity = quantity_plan.quantity
        logger.info("%s order intent side=%s positionSide=%s quantity=%s notional=%s", symbol, side, action, quantity, quantity_plan.notional)
        if settings.dry_run:
            return True
        self._place_market_order(
            settings=settings,
            symbol=symbol,
            side=side,
            quantity=quantity,
            position_side=action,
            action="entry",
            requested_price=mark_price,
            stop_loss=self._stop_price(action, mark_price, settings),
            take_profit=self._target_price(action, mark_price, settings),
        )
        return True

    def _manage_open_positions(self, symbol: str, settings: Settings, fallback_mark_price: Decimal) -> None:
        if settings.dry_run:
            return
        for position in self._positions(symbol, fallback_mark_price):
            if not position.is_open or position.entry_price <= 0:
                continue
            pnl = pnl_pct(position.side, position.entry_price, position.mark_price)
            if pnl <= -Decimal(str(settings.stop_loss_pct)):
                logger.warning("%s %s stop loss triggered pnl=%s", symbol, position.side, pnl)
                self._close(symbol, settings, position)
            elif pnl >= Decimal(str(settings.take_profit_pct)):
                logger.info("%s %s take profit triggered pnl=%s", symbol, position.side, pnl)
                self._close(symbol, settings, position)

    def _positions(self, symbol: str, fallback_mark_price: Decimal) -> list[LivePosition]:
        output: list[LivePosition] = []
        for item in self.client.positions(symbol):
            side = item.get("positionSide", "BOTH")
            if side not in {"LONG", "SHORT"}:
                continue
            output.append(
                LivePosition(
                    side=side,
                    amount=Decimal(item["positionAmt"]),
                    entry_price=Decimal(item["entryPrice"]),
                    mark_price=Decimal(item.get("markPrice") or fallback_mark_price),
                    notional=abs(Decimal(item["notional"])),
                )
            )
        return output

    def _close(self, symbol: str, settings: Settings, position: LivePosition) -> None:
        quantity = abs(position.amount)
        if quantity == 0:
            return
        side = "SELL" if position.side == "LONG" else "BUY"
        logger.info("%s close intent side=%s positionSide=%s quantity=%s", symbol, side, position.side, quantity)
        response = self._place_market_order(
            settings=settings,
            symbol=symbol,
            side=side,
            quantity=quantity,
            position_side=position.side,
            action="exit",
            requested_price=position.mark_price,
            stop_loss=None,
            take_profit=None,
        )
        if response is not None:
            realized = (position.mark_price - position.entry_price) * quantity
            if position.side == "SHORT":
                realized = -realized
            self._record_closed_trade(realized)
            self.last_action[symbol] = None

    def _place_market_order(
        self,
        settings: Settings,
        symbol: str,
        side: str,
        quantity: Decimal,
        position_side: str,
        action: str,
        requested_price: Decimal,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> dict[str, Any] | None:
        try:
            response = self.client.market_order(symbol, side, quantity, position_side)
        except Exception as exc:
            self._write_order_log(
                settings,
                symbol=symbol,
                side=position_side,
                action=action,
                quantity=quantity,
                requested_price=requested_price,
                filled_price=None,
                stop_loss=stop_loss,
                take_profit=take_profit,
                order_id=None,
                status="ERROR",
                error_message=str(exc),
            )
            raise

        filled_price = self._filled_price(response)
        self._write_order_log(
            settings,
            symbol=symbol,
            side=position_side,
            action=action,
            quantity=quantity,
            requested_price=requested_price,
            filled_price=filled_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_id=response.get("orderId"),
            status=str(response.get("status", "UNKNOWN")),
            error_message="",
        )
        return response

    def _has_open_position(self, symbol: str, mark_price: Decimal) -> bool:
        if self.settings.dry_run:
            return False
        return any(position.is_open for position in self._positions(symbol, mark_price))

    def _rules(self, symbol: str) -> SymbolRules:
        if symbol not in self._symbol_rules:
            self._symbol_rules[symbol] = self.client.symbol_rules(symbol)
        return self._symbol_rules[symbol]

    def _daily_loss_limit_hit(self, settings: Settings) -> bool:
        limit = Decimal("0")
        if settings.daily_loss_limit_usdt > 0:
            limit = Decimal(str(settings.daily_loss_limit_usdt))
        elif settings.daily_loss_limit_pct > 0:
            limit = Decimal(str(settings.starting_balance)) * Decimal(str(settings.daily_loss_limit_pct)) / Decimal("100")
        return limit > 0 and self.daily_realized_pnl <= -limit

    def _cooldown_active(self) -> bool:
        return time.time() < self.cooldown_until

    def _funding_unfavorable(self, symbol: str, action: str, settings: Settings) -> bool:
        if settings.max_abs_funding_rate <= 0:
            return False
        funding_rate = self.client.funding_rate(symbol)
        threshold = Decimal(str(settings.max_abs_funding_rate))
        if action == "LONG":
            return funding_rate > threshold
        return funding_rate < -threshold

    def _record_closed_trade(self, realized_pnl: Decimal) -> None:
        self.daily_realized_pnl += realized_pnl
        if realized_pnl < 0:
            self.consecutive_losses += 1
            if (
                self.settings.max_consecutive_losses > 0
                and self.consecutive_losses >= self.settings.max_consecutive_losses
                and self.settings.cooldown_minutes > 0
            ):
                self.cooldown_until = time.time() + self.settings.cooldown_minutes * 60
                logger.warning(
                    "Cooldown started for %s minutes after %s consecutive losses.",
                    self.settings.cooldown_minutes,
                    self.consecutive_losses,
                )
        else:
            self.consecutive_losses = 0

    def _roll_daily_state_if_needed(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self.daily_date:
            self.daily_date = today
            self.daily_realized_pnl = Decimal("0")
            self.consecutive_losses = 0
            self.cooldown_until = 0.0

    def _write_order_log(
        self,
        settings: Settings,
        symbol: str,
        side: str,
        action: str,
        quantity: Decimal,
        requested_price: Decimal,
        filled_price: Decimal | None,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
        order_id: object,
        status: str,
        error_message: str,
    ) -> None:
        path = Path(settings.live_order_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "time",
                "symbol",
                "side",
                "action",
                "quantity",
                "requested_price",
                "filled_price",
                "stop_loss",
                "take_profit",
                "order_id",
                "status",
                "error_message",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if new_file:
                writer.writeheader()
            writer.writerow(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "side": side,
                    "action": action,
                    "quantity": str(quantity),
                    "requested_price": str(requested_price),
                    "filled_price": "" if filled_price is None else str(filled_price),
                    "stop_loss": "" if stop_loss is None else str(stop_loss),
                    "take_profit": "" if take_profit is None else str(take_profit),
                    "order_id": "" if order_id is None else str(order_id),
                    "status": status,
                    "error_message": error_message,
                }
            )

    @staticmethod
    def _filled_price(response: dict[str, Any]) -> Decimal | None:
        for key in ("avgPrice", "price"):
            value = response.get(key)
            if value not in (None, "", "0", 0):
                return Decimal(str(value))
        return None

    @staticmethod
    def _stop_price(side: str, entry_price: Decimal, settings: Settings) -> Decimal:
        if side == "LONG":
            return entry_price * (Decimal("1") - Decimal(str(settings.stop_loss_pct)))
        return entry_price * (Decimal("1") + Decimal(str(settings.stop_loss_pct)))

    @staticmethod
    def _target_price(side: str, entry_price: Decimal, settings: Settings) -> Decimal:
        if side == "LONG":
            return entry_price * (Decimal("1") + Decimal(str(settings.take_profit_pct)))
        return entry_price * (Decimal("1") - Decimal(str(settings.take_profit_pct)))
