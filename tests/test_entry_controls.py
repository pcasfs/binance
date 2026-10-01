from decimal import Decimal
from unittest import TestCase

from trader.bot import TradingBot
from tests.test_presets import base_settings


class FakeSummary:
    def __init__(self) -> None:
        self.blocked: list[tuple[str, str]] = []

    def record_blocked(self, symbol: str, reason: str) -> None:
        self.blocked.append((symbol, reason))


class EntryControlsTest(TestCase):
    def test_short_entry_is_blocked_before_position_or_order_checks(self) -> None:
        settings = base_settings()
        bot = TradingBot.__new__(TradingBot)
        bot.summary = FakeSummary()
        events: list[tuple[str, dict]] = []
        bot._record_event = lambda event_type, **kwargs: events.append((event_type, kwargs))
        bot._has_open_position = lambda *args: self.fail("position lookup should not run")

        placed = bot._order("BTCUSDT", settings, "SHORT", Decimal("100000"))

        self.assertFalse(placed)
        self.assertEqual(bot.summary.blocked[0][0], "BTCUSDT")
        self.assertIn("disabled", bot.summary.blocked[0][1])
        self.assertEqual(events[0][0], "ENTRY_BLOCKED")

    def test_btc_uses_symbol_specific_trade_amount(self) -> None:
        settings = base_settings()

        self.assertEqual(settings.trade_amount_for("BTCUSDT"), 130)
        self.assertEqual(settings.trade_amount_for("ETHUSDT"), 20)
