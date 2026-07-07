from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("config/live.yaml")

DEFAULT_RUNTIME_CONFIG: dict[str, Any] = {
    "settings": {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "strategy": "heikin_ashi_stoch",
        "leverage": 2,
        "margin_type": "ISOLATED",
        "poll_seconds": 15,
        "live_order_log_path": "logs/live_orders.csv",
        "daily_summary_dir": "logs/daily",
        "daily_summary_retention_days": 90,
    },
    "capital": {
        "usdt_per_trade": 100,
        "starting_balance": 1000,
        "max_position_usdt": 100,
    },
    "fees": {
        "fee_rate": 0.0004,
        "slippage_rate": 0.0002,
    },
    "ema_cross": {
        "fast_ema": 9,
        "slow_ema": 21,
    },
    "heikin_ashi_stoch": {
        "stoch_threshold_long": 32,
        "stoch_threshold_short": 68,
        "wick_tolerance": 0.0018,
        "adx_threshold": 20,
        "sma_period": 200,
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.0375,
    },
    "risk": {
        "daily_loss_limit_usdt": 0,
        "daily_loss_limit_pct": 0,
        "max_consecutive_losses": 0,
        "cooldown_minutes": 0,
        "max_abs_funding_rate": 0,
    },
    "notifications": {
        "telegram_enabled": True,
        "telegram_timeout_seconds": 10,
    },
    "presets": {
        "default": {},
        "optimized": {
            "stoch_threshold_long": 20,
            "stoch_threshold_short": 80,
            "wick_tolerance": 0.0005,
            "adx_threshold": 20,
            "stop_loss_pct": 0.020,
            "take_profit_pct": 0.045,
        },
        "optimized-long": {
            "stoch_threshold_long": 20,
            "stoch_threshold_short": 80,
            "wick_tolerance": 0.0018,
            "adx_threshold": 25,
            "stop_loss_pct": 0.020,
            "take_profit_pct": 0.045,
        },
        "symbol-optimized": {
            "interval": "1h",
            "symbols": {
                "BTCUSDT": {
                    "stoch_threshold_long": 32,
                    "stoch_threshold_short": 68,
                    "wick_tolerance": 0.0020,
                    "adx_threshold": 20,
                    "stop_loss_pct": 0.010,
                    "take_profit_pct": 0.045,
                },
                "ETHUSDT": {
                    "stoch_threshold_long": 32,
                    "stoch_threshold_short": 68,
                    "wick_tolerance": 0.0018,
                    "adx_threshold": 25,
                    "stop_loss_pct": 0.015,
                    "take_profit_pct": 0.030,
                },
                "SOLUSDT": {
                    "stoch_threshold_long": 35,
                    "stoch_threshold_short": 65,
                    "wick_tolerance": 0.0018,
                    "adx_threshold": 20,
                    "stop_loss_pct": 0.020,
                    "take_profit_pct": 0.030,
                },
                "DOGEUSDT": {
                    "stoch_threshold_long": 32,
                    "stoch_threshold_short": 68,
                    "wick_tolerance": 0.0020,
                    "adx_threshold": 20,
                    "stop_loss_pct": 0.020,
                    "take_profit_pct": 0.0375,
                },
            },
        },
    },
}


@lru_cache(maxsize=4)
def load_runtime_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = Path(config_path)
    config = deepcopy(DEFAULT_RUNTIME_CONFIG)
    if not path.exists():
        return config

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a YAML object at the top level.")
    return deep_merge(config, loaded)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = deep_merge(output[key], value)
        else:
            output[key] = value
    return output
