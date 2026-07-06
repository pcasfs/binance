from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal

from trader.config import Settings
from trader.data_loader import load_candles
from trader.models import Candle, Trade
from trader.report import print_report, summarize
from trader.risk import exit_reason
from trader.strategy import build_strategy

UTC = timezone.utc

@dataclass
class OpenPosition:
    side: str
    entry_time: int
    entry_price: Decimal
    quantity: Decimal


class Backtester:
    def __init__(
        self,
        settings: Settings,
        symbol: str,
        interval: str,
        side: str = "both",
        start: str | None = None,
        end: str | None = None,
        log_trades: bool = False,
    ) -> None:
        self.settings = settings
        self.symbol = symbol.upper()
        self.interval = interval
        self.side = side
        self.start_ms = self._parse_utc_ms(start, is_end=False)
        self.end_ms = self._parse_utc_ms(end, is_end=True)
        self.log_trades = log_trades
        self.strategy = build_strategy(settings)
        self.balance = Decimal(str(settings.starting_balance))
        self.equity_curve: list[Decimal] = [self.balance]
        self.trades: list[Trade] = []
        self.position: OpenPosition | None = None

    def run(self, print_summary: bool = True) -> dict[str, object]:
        candles = load_candles(self.symbol, self.interval)
        signals = self.strategy.signal_series(candles) if hasattr(self.strategy, "signal_series") else None
        last_period_candle: Candle | None = None

        for index in range(self.strategy.warmup_candles, len(candles)):
            candle = candles[index]
            if self.end_ms is not None and candle.open_time > self.end_ms:
                break

            if self._in_period(candle.open_time):
                last_period_candle = candle
                self._maybe_exit(candle)
                self.equity_curve.append(self._mark_equity(candle.close))

            if self.position is None and index + 1 < len(candles):
                next_candle = candles[index + 1]
            else:
                next_candle = None

            if self.position is None and next_candle is not None and self._in_period(next_candle.open_time):
                history = candles[: index + 1]
                signal = signals[index] if signals is not None else self.strategy.signal(history)
                if self._is_allowed_signal(signal.action):
                    self._open(signal.action, next_candle)

        if self.position is not None and last_period_candle is not None and self.log_trades:
            pnl = self._pnl_pct(self.position.side, self.position.entry_price, last_period_candle.close)
            print(
                f"{self._icon('EVAL')} [미청산 평가] {self._fmt_time(last_period_candle.close_time)} | "
                f"평가가: {self._fmt_price(last_period_candle.close)} | 수익률: {pnl:+.2f}%"
            )

        if print_summary:
            print_report(self.symbol, self.interval, self.balance, self.equity_curve, self.trades)
        metrics = summarize(self.balance, self.equity_curve, self.trades)
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "balance": self.balance,
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "metrics": metrics,
        }

    def _open(self, side: str, candle: Candle) -> None:
        entry_price = candle.open
        quantity = Decimal(str(self.settings.usdt_per_trade)) / entry_price
        fee = entry_price * quantity * Decimal(str(self.settings.fee_rate))
        self.balance -= fee
        self.position = OpenPosition(side=side, entry_time=candle.open_time, entry_price=entry_price, quantity=quantity)
        if self.log_trades:
            label = "매수 진입" if side == "LONG" else "숏 진입"
            print(f"{self._icon('ENTRY')} [{label}] {self._fmt_time(candle.open_time)} | 체결가: {self._fmt_price(entry_price)}")

    def _maybe_exit(self, candle: Candle) -> None:
        if self.position is None:
            return
        decision = exit_reason(
            self.position.side,
            self.position.entry_price,
            candle.high,
            candle.low,
            Decimal(str(self.settings.stop_loss_pct)),
            Decimal(str(self.settings.take_profit_pct)),
        )
        if decision is None:
            return
        reason, exit_price = decision
        self._close(candle, exit_price, reason)

    def _close(self, candle: Candle, exit_price: Decimal, reason: str) -> None:
        if self.position is None:
            return
        direction = Decimal("1") if self.position.side == "LONG" else Decimal("-1")
        gross = (exit_price - self.position.entry_price) * self.position.quantity * direction
        fee = exit_price * self.position.quantity * Decimal(str(self.settings.fee_rate))
        pnl = gross - fee
        pnl_pct = self._pnl_pct(self.position.side, self.position.entry_price, exit_price)
        self.balance += pnl
        self.trades.append(
            Trade(
                side=self.position.side,
                entry_time=self.position.entry_time,
                exit_time=candle.close_time,
                entry_price=self.position.entry_price,
                exit_price=exit_price,
                quantity=self.position.quantity,
                pnl=pnl,
                fee=fee,
                reason=reason,
                pnl_pct=pnl_pct,
            )
        )
        if self.log_trades:
            label = "매수 청산" if self.position.side == "LONG" else "숏 청산"
            reason_label = "손절" if reason == "stop_loss" else "익절"
            target_pct = Decimal(str(self.settings.stop_loss_pct if reason == "stop_loss" else self.settings.take_profit_pct)) * 100
            sign = "-" if reason == "stop_loss" else "+"
            print(
                f"{self._icon('EXIT')} [{label}] {self._fmt_time(candle.close_time)} | "
                f"사유: {reason_label}({sign}{target_pct:.2f}%) | 수익률: {pnl_pct:+.2f}%"
            )
        self.position = None

    def _mark_equity(self, price: Decimal) -> Decimal:
        if self.position is None:
            return self.balance
        direction = Decimal("1") if self.position.side == "LONG" else Decimal("-1")
        unrealized = (price - self.position.entry_price) * self.position.quantity * direction
        return self.balance + unrealized

    def _is_allowed_signal(self, action: str) -> bool:
        if action == "LONG":
            return self.side in {"both", "long"}
        if action == "SHORT":
            return self.side in {"both", "short"}
        return False

    def _in_period(self, timestamp_ms: int) -> bool:
        if self.start_ms is not None and timestamp_ms < self.start_ms:
            return False
        if self.end_ms is not None and timestamp_ms > self.end_ms:
            return False
        return True

    @staticmethod
    def _pnl_pct(side: str, entry_price: Decimal, exit_price: Decimal) -> Decimal:
        direction = Decimal("1") if side == "LONG" else Decimal("-1")
        return (exit_price - entry_price) / entry_price * direction * Decimal("100")

    @staticmethod
    def _parse_utc_ms(value: str | None, is_end: bool) -> int | None:
        if not value:
            return None
        if len(value) == 10:
            day = datetime.fromisoformat(value).date()
            parsed = datetime.combine(day, time.max if is_end else time.min, tzinfo=UTC)
        else:
            parsed = datetime.fromisoformat(value.replace(" ", "T"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)

    @staticmethod
    def _fmt_time(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _fmt_price(price: Decimal) -> str:
        return f"{price:,.2f}"

    @staticmethod
    def _icon(kind: str) -> str:
        icons = {"ENTRY": "ENTRY", "EXIT": "EXIT", "EVAL": "EVAL"}
        return icons[kind]
