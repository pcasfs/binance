from decimal import Decimal
from unittest import TestCase

from trader.models import Candle
from trader.strategy import EmaCrossStrategy, HeikinAshiStochStrategy


def candle(close: str) -> Candle:
    value = Decimal(close)
    return Candle(0, value, value, value, value, Decimal("1"), 0)


class EmaCrossStrategyTest(TestCase):
    def test_returns_hold_when_not_enough_candles(self) -> None:
        signal = EmaCrossStrategy(3, 5).signal([candle("1"), candle("2")])
        self.assertEqual(signal.action, "HOLD")

    def test_detects_long_cross(self) -> None:
        candles = [candle(value) for value in ["6", "6", "6", "6", "6", "6", "6", "8"]]
        signal = EmaCrossStrategy(3, 5).signal(candles)
        self.assertEqual(signal.action, "LONG")

    def test_detects_short_cross(self) -> None:
        candles = [candle(value) for value in ["6", "6", "6", "6", "6", "8", "6", "6"]]
        signal = EmaCrossStrategy(3, 5).signal(candles)
        self.assertEqual(signal.action, "SHORT")


class HeikinAshiStochStrategyTest(TestCase):
    def test_heikin_ashi_calculation_matches_upbit_helper(self) -> None:
        candles = [
            Candle(0, Decimal("10"), Decimal("12"), Decimal("9"), Decimal("11"), Decimal("1"), 0),
            Candle(0, Decimal("11"), Decimal("14"), Decimal("10"), Decimal("13"), Decimal("1"), 0),
        ]

        ha = HeikinAshiStochStrategy._heikin_ashi(candles)

        self.assertEqual(ha[0].close, Decimal("10.5"))
        self.assertEqual(ha[0].open, Decimal("10.5"))
        self.assertEqual(ha[1].close, Decimal("12"))
        self.assertEqual(ha[1].open, Decimal("10.5"))
