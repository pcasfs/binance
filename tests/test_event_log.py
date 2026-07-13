from __future__ import annotations

import csv
import tempfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from test_presets import base_settings
from trader.event_log import EventLogger


class EventLoggerTest(TestCase):
    def test_writes_events_csv_with_analysis_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.csv"
            settings = replace(base_settings(), event_log_path=str(path))

            logger = EventLogger(settings)
            logger.record(
                "POSITION_CHECK",
                symbol="SOLUSDT",
                side="SHORT",
                mark_price=Decimal("79.18"),
                entry_price=Decimal("78.04"),
                stop_loss=Decimal("79.6008"),
                pnl_pct=Decimal("-1.4607"),
                stoch_k=Decimal("72.1"),
                adx=Decimal("21.3"),
            )

            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_type"], "POSITION_CHECK")
            self.assertEqual(rows[0]["symbol"], "SOLUSDT")
            self.assertEqual(rows[0]["side"], "SHORT")
            self.assertEqual(rows[0]["mark_price"], "79.18")
            self.assertEqual(rows[0]["stop_loss"], "79.6008")
            self.assertEqual(rows[0]["pnl_pct"], "-1.4607")
            self.assertEqual(rows[0]["stoch_k"], "72.1")
