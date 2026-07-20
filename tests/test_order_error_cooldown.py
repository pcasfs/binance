from decimal import Decimal
from unittest import TestCase

from trader.bot import TradingBot
from trader.config import Settings


def settings_with_order_error_cooldown(minutes: int) -> Settings:
    return Settings(
        api_key="",
        api_secret="",
        testnet=True,
        dry_run=False,
        symbol="BTCUSDT",
        interval="1h",
        strategy="heikin_ashi_stoch",
        leverage=2,
        margin_type="ISOLATED",
        usdt_per_trade=20,
        starting_balance=1000,
        max_position_usdt=100,
        fee_rate=0.0004,
        slippage_rate=0.0002,
        fast_ema=9,
        slow_ema=21,
        stoch_threshold_long=32,
        stoch_threshold_short=68,
        wick_tolerance=0.0018,
        adx_threshold=20,
        sma_period=200,
        stop_loss_pct=0.015,
        take_profit_pct=0.0375,
        daily_loss_limit_usdt=0,
        daily_loss_limit_pct=0,
        max_consecutive_losses=0,
        cooldown_minutes=0,
        order_error_cooldown_minutes=minutes,
        max_abs_funding_rate=0,
        live_order_log_path="logs/live_orders.csv",
        event_log_path="logs/events.csv",
        daily_summary_dir="logs/daily",
        daily_summary_retention_days=90,
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_enabled=True,
        telegram_timeout_seconds=10,
        poll_seconds=15,
    )


class FailingClient:
    def market_order(self, symbol: str, side: str, quantity: Decimal, position_side: str) -> dict:
        raise RuntimeError("Margin is insufficient")


class FakeSummary:
    def __init__(self) -> None:
        self.order_errors: list[tuple[str, str]] = []

    def record_order_error(self, symbol: str, message: str) -> None:
        self.order_errors.append((symbol, message))


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


class OrderErrorCooldownTest(TestCase):
    def test_entry_order_error_starts_cooldown_and_does_not_raise(self) -> None:
        settings = settings_with_order_error_cooldown(60)
        bot = TradingBot.__new__(TradingBot)
        bot.client = FailingClient()
        bot.summary = FakeSummary()
        bot.notifier = FakeNotifier()
        bot.order_error_cooldown_until = {}
        bot._record_event = lambda *args, **kwargs: None
        bot._write_order_log = lambda *args, **kwargs: None

        result = bot._place_market_order(
            settings=settings,
            symbol="ETHUSDT",
            side="BUY",
            quantity=Decimal("0.05"),
            position_side="LONG",
            action="entry",
            requested_price=Decimal("1800"),
            stop_loss=Decimal("1773"),
            take_profit=Decimal("1854"),
        )

        self.assertIsNone(result)
        self.assertTrue(bot._order_error_cooldown_active("ETHUSDT", "LONG"))
        self.assertEqual(len(bot.summary.order_errors), 1)
        self.assertEqual(len(bot.notifier.messages), 1)

    def test_exit_order_error_does_not_start_entry_cooldown(self) -> None:
        settings = settings_with_order_error_cooldown(60)
        bot = TradingBot.__new__(TradingBot)
        bot.client = FailingClient()
        bot.summary = FakeSummary()
        bot.notifier = FakeNotifier()
        bot.order_error_cooldown_until = {}
        bot._record_event = lambda *args, **kwargs: None
        bot._write_order_log = lambda *args, **kwargs: None

        result = bot._place_market_order(
            settings=settings,
            symbol="ETHUSDT",
            side="SELL",
            quantity=Decimal("0.05"),
            position_side="LONG",
            action="exit",
            requested_price=Decimal("1770"),
            stop_loss=None,
            take_profit=None,
        )

        self.assertIsNone(result)
        self.assertFalse(bot._order_error_cooldown_active("ETHUSDT", "LONG"))
