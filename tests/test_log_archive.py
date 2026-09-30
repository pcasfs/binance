from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from trader.log_archive import LogArchiveConfig, build_analysis_pack, upload_analysis_pack


class FakeS3Client:
    def __init__(self) -> None:
        self.calls = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None) -> None:
        self.calls.append((filename, bucket, key, ExtraArgs))


class LogArchiveTest(TestCase):
    def test_builds_analysis_pack_with_both_log_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            live_orders = root / "live_orders.csv"
            events = root / "events.csv"
            output = root / "analysis_pack_full.txt"
            live_orders.write_text("time,symbol\n1,BTCUSDT\n", encoding="utf-8")
            events.write_text("time,event_type\n2,ORDER\n", encoding="utf-8")

            build_analysis_pack(live_orders, events, output)

            content = output.read_text(encoding="utf-8")
            self.assertIn("### live_orders.csv\n", content)
            self.assertIn("1,BTCUSDT", content)
            self.assertIn("### events.csv\n", content)
            self.assertIn("2,ORDER", content)

    def test_uploads_to_fixed_s3_key_with_server_side_encryption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            live_orders = root / "live_orders.csv"
            events = root / "events.csv"
            live_orders.write_text("orders\n", encoding="utf-8")
            events.write_text("events\n", encoding="utf-8")
            client = FakeS3Client()
            config = LogArchiveConfig(
                bucket="private-log-bucket",
                prefix="binance-bot/logs",
                pack_path=root / "analysis_pack_full.txt",
            )

            pack_path, object_key = upload_analysis_pack(config, str(live_orders), str(events), client)

            self.assertEqual(pack_path, root / "analysis_pack_full.txt")
            self.assertEqual(object_key, "binance-bot/logs/analysis_pack_full.txt")
            self.assertEqual(len(client.calls), 1)
            _, bucket, key, extra_args = client.calls[0]
            self.assertEqual(bucket, "private-log-bucket")
            self.assertEqual(key, object_key)
            self.assertEqual(extra_args["ServerSideEncryption"], "AES256")

    def test_requires_bucket_before_uploading(self) -> None:
        config = LogArchiveConfig(bucket="", prefix="logs", pack_path=Path("pack.txt"))

        with self.assertRaisesRegex(ValueError, "S3 bucket is not configured"):
            upload_analysis_pack(config, "missing-live.csv", "missing-events.csv", FakeS3Client())
