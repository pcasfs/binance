from unittest import TestCase

from trader.bot import TradingBot


def kline(open_time: int, close_time: int, close: str = "100") -> list[object]:
    return [open_time, close, close, close, close, "1", close_time]


class LiveCandleFilterTest(TestCase):
    def test_excludes_unfinished_last_kline(self) -> None:
        candles = TradingBot._closed_candles_from_klines(
            [
                kline(0, 3_599_999, "100"),
                kline(3_600_000, 7_199_999, "101"),
                kline(7_200_000, 10_799_999, "102"),
            ],
            now_ms=7_210_000,
        )

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[-1].close_time, 7_199_999)

    def test_waits_for_close_grace_period(self) -> None:
        candles = TradingBot._closed_candles_from_klines(
            [
                kline(0, 3_599_999, "100"),
                kline(3_600_000, 7_199_999, "101"),
            ],
            now_ms=7_200_500,
        )

        self.assertEqual(len(candles), 1)
