from unittest import TestCase

from trader.config import Settings
from trader.presets import apply_symbol_preset, preset_names


def base_settings() -> Settings:
    return Settings(
        api_key="",
        api_secret="",
        testnet=True,
        dry_run=True,
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
        order_error_cooldown_minutes=60,
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


class SymbolOptimizedPresetTest(TestCase):
    def test_symbol_optimized_is_available(self) -> None:
        self.assertIn("symbol-optimized", preset_names())

    def test_applies_sol_1h_settings(self) -> None:
        settings = apply_symbol_preset(base_settings(), "symbol-optimized", "SOLUSDT", "1h")

        self.assertEqual(settings.symbol, "SOLUSDT")
        self.assertEqual(settings.interval, "1h")
        self.assertEqual(settings.stoch_threshold_long, 35.0)
        self.assertEqual(settings.stoch_threshold_short, 65.0)
        self.assertEqual(settings.stop_loss_pct, 0.020)
        self.assertEqual(settings.take_profit_pct, 0.030)

    def test_rejects_non_1h_symbol_optimized(self) -> None:
        with self.assertRaises(ValueError):
            apply_symbol_preset(base_settings(), "symbol-optimized", "BTCUSDT", "30m")
