from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from trader.config import Settings


@dataclass
class DailyStats:
    day: date
    started_at: datetime
    symbols: list[str]
    interval: str
    preset: str
    ticks: int = 0
    hold_signals: int = 0
    long_signals: int = 0
    short_signals: int = 0
    blocked_entries: int = 0
    entries: int = 0
    exits: int = 0
    order_errors: int = 0
    tick_errors: int = 0
    realized_pnl: Decimal = Decimal("0")
    last_error: str = ""
    last_events: list[str] = field(default_factory=list)


class DailySummaryLogger:
    def __init__(self, settings: Settings, symbols: list[str], interval: str, preset: str) -> None:
        self.directory = Path(settings.daily_summary_dir)
        self.retention_days = settings.daily_summary_retention_days
        self.symbols = symbols
        self.interval = interval
        self.preset = preset
        self.last_flush_ts = 0.0
        self.stats = self._new_stats()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_files()
        self.write()

    def roll_if_needed(self) -> None:
        if datetime.now(timezone.utc).date() != self.stats.day:
            self.write()
            self.stats = self._new_stats()
            self._cleanup_old_files()
            self.write()

    def record_signal(self, symbol: str, action: str) -> None:
        self.stats.ticks += 1
        if action == "LONG":
            self.stats.long_signals += 1
            self._add_event(f"{symbol} LONG signal")
            self.write()
        elif action == "SHORT":
            self.stats.short_signals += 1
            self._add_event(f"{symbol} SHORT signal")
            self.write()
        else:
            self.stats.hold_signals += 1

    def record_blocked(self, symbol: str, reason: str) -> None:
        self.stats.blocked_entries += 1
        self._add_event(f"{symbol} blocked: {reason}")
        self.write()

    def record_entry(self, symbol: str, side: str, quantity: Decimal, notional: Decimal) -> None:
        self.stats.entries += 1
        self._add_event(f"{symbol} {side} entry qty={quantity} notional={notional:.4f}")
        self.write()

    def record_exit(self, symbol: str, side: str, realized_pnl: Decimal) -> None:
        self.stats.exits += 1
        self.stats.realized_pnl += realized_pnl
        self._add_event(f"{symbol} {side} exit realized_pnl={realized_pnl:.4f}")
        self.write()

    def record_order_error(self, symbol: str, message: str) -> None:
        self.stats.order_errors += 1
        self.stats.last_error = message
        self._add_event(f"{symbol} order error: {message}")
        self.write()

    def record_tick_error(self, message: str) -> None:
        self.stats.tick_errors += 1
        self.stats.last_error = message
        self._add_event(f"tick error: {message}")
        self.write()

    def write(self) -> None:
        path = self.directory / f"daily_summary_{self.stats.day.isoformat()}.md"
        path.write_text(self._render(), encoding="utf-8")

    def _new_stats(self) -> DailyStats:
        now = datetime.now(timezone.utc)
        return DailyStats(
            day=now.date(),
            started_at=now,
            symbols=self.symbols,
            interval=self.interval,
            preset=self.preset,
        )

    def _render(self) -> str:
        updated_at = datetime.now(timezone.utc).isoformat()
        events = "\n".join(f"- {event}" for event in self.stats.last_events) or "- No notable events yet."
        return (
            f"# Daily Trading Summary - {self.stats.day.isoformat()}\n\n"
            f"- Updated UTC: {updated_at}\n"
            f"- Started UTC: {self.stats.started_at.isoformat()}\n"
            f"- Symbols: {', '.join(self.stats.symbols)}\n"
            f"- Interval: {self.stats.interval}\n"
            f"- Preset: {self.stats.preset}\n\n"
            "## Counts\n\n"
            f"- Symbol ticks: {self.stats.ticks}\n"
            f"- HOLD signals: {self.stats.hold_signals}\n"
            f"- LONG signals: {self.stats.long_signals}\n"
            f"- SHORT signals: {self.stats.short_signals}\n"
            f"- Blocked entries: {self.stats.blocked_entries}\n"
            f"- Entries: {self.stats.entries}\n"
            f"- Exits: {self.stats.exits}\n"
            f"- Order errors: {self.stats.order_errors}\n"
            f"- Tick errors: {self.stats.tick_errors}\n\n"
            "## PnL\n\n"
            f"- Realized PnL since bot start today: {self.stats.realized_pnl:.4f} USDT\n\n"
            "## Last Error\n\n"
            f"{self.stats.last_error or 'None'}\n\n"
            "## Recent Events\n\n"
            f"{events}\n"
        )

    def _add_event(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.stats.last_events.append(f"{timestamp} UTC - {message}")
        self.stats.last_events = self.stats.last_events[-20:]

    def _cleanup_old_files(self) -> None:
        cutoff = datetime.now(timezone.utc).date().toordinal() - self.retention_days
        for path in self.directory.glob("daily_summary_*.md"):
            try:
                day_text = path.stem.replace("daily_summary_", "")
                file_day = date.fromisoformat(day_text)
            except ValueError:
                continue
            if file_day.toordinal() < cutoff:
                path.unlink(missing_ok=True)
