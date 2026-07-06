from __future__ import annotations

import csv
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from trader.binance_client import BinanceFuturesClient
from trader.config import Settings
from trader.models import Candle

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def csv_path(symbol: str, interval: str) -> Path:
    return DATA_DIR / f"{symbol.upper()}_{interval}.csv"


def download_to_csv(settings: Settings, symbol: str, interval: str, days: int) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = BinanceFuturesClient(testnet=False)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    rows: list[list[str]] = []
    cursor = start_ms
    while cursor < end_ms:
        batch = client.get_klines(symbol, interval, limit=1500, start_time=cursor, end_time=end_ms)
        if not batch:
            break
        for item in batch:
            rows.append([str(item[0]), item[1], item[2], item[3], item[4], item[5], str(item[6])])
        cursor = int(batch[-1][6]) + 1
        time.sleep(0.15)

    path = csv_path(symbol, interval)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["open_time", "open", "high", "low", "close", "volume", "close_time"])
        writer.writerows(rows)
    print(f"Saved {len(rows)} candles to {path}")
    return path


def load_candles(symbol: str, interval: str) -> list[Candle]:
    path = csv_path(symbol, interval)
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}. Run download first.")
    candles: list[Candle] = []
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            candles.append(
                Candle(
                    open_time=int(row["open_time"]),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=Decimal(row["volume"]),
                    close_time=int(row["close_time"]),
                )
            )
    return candles
