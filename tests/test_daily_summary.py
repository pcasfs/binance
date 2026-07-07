import tempfile
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest import TestCase

from test_presets import base_settings
from trader.daily_summary import DailySummaryLogger


class DailySummaryLoggerTest(TestCase):
    def test_writes_daily_summary_and_removes_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(base_settings(), daily_summary_dir=temp_dir, daily_summary_retention_days=1)
            old_day = date.today() - timedelta(days=3)
            old_file = Path(temp_dir) / f"daily_summary_{old_day.isoformat()}.md"
            old_file.write_text("old", encoding="utf-8")

            logger = DailySummaryLogger(settings, ["BTCUSDT"], "1h", "symbol-optimized")
            logger.record_signal("BTCUSDT", "LONG")

            self.assertFalse(old_file.exists())
            current_files = list(Path(temp_dir).glob("daily_summary_*.md"))
            self.assertEqual(len(current_files), 1)
            self.assertIn("LONG signals: 1", current_files[0].read_text(encoding="utf-8"))
