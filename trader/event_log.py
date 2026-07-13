from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from trader.config import Settings


EVENT_FIELDS = [
    "time",
    "event_type",
    "symbol",
    "side",
    "signal",
    "reason",
    "message",
    "error",
    "mark_price",
    "entry_price",
    "quantity",
    "notional",
    "stop_loss",
    "take_profit",
    "pnl_pct",
    "distance_to_stop_pct",
    "distance_to_take_profit_pct",
    "close",
    "sma200",
    "stoch_k",
    "stoch_d",
    "prev_stoch_k",
    "prev_stoch_d",
    "adx",
    "ha_open",
    "ha_high",
    "ha_low",
    "ha_close",
    "position_amount",
    "order_id",
    "status",
]


class EventLogger:
    def __init__(self, settings: Settings) -> None:
        self.path = Path(settings.event_log_path)

    def record(self, event_type: str, **values: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()
        row = {field: "" for field in EVENT_FIELDS}
        row["time"] = datetime.now(timezone.utc).isoformat()
        row["event_type"] = event_type
        for key, value in values.items():
            if key in row:
                row[key] = self._format(value)

        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _format(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return str(value)
        return str(value)
