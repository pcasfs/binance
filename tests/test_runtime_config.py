from unittest import TestCase

from trader.runtime_config import load_runtime_config


class RuntimeConfigTest(TestCase):
    def test_live_config_contains_symbol_optimized_preset(self) -> None:
        config = load_runtime_config()
        preset = config["presets"]["symbol-optimized"]

        self.assertEqual(preset["interval"], "1h")
        self.assertIn("BTCUSDT", preset["symbols"])
        self.assertIn("DOGEUSDT", preset["symbols"])

    def test_env_only_values_are_not_strategy_config(self) -> None:
        config = load_runtime_config()

        self.assertIn("capital", config)
        self.assertIn("risk", config)
        self.assertIn("heikin_ashi_stoch", config)

    def test_live_config_is_long_only_with_btc_specific_amount(self) -> None:
        config = load_runtime_config()

        self.assertEqual(config["settings"]["allowed_entry_sides"], ["LONG"])
        self.assertEqual(config["capital"]["usdt_per_trade"], 65)
        self.assertEqual(config["capital"]["symbol_usdt_per_trade"]["BTCUSDT"], 130)
        self.assertGreaterEqual(config["capital"]["max_position_usdt"], 130)
