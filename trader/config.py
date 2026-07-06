from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from trader.runtime_config import load_runtime_config


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    testnet: bool
    dry_run: bool
    symbol: str
    interval: str
    strategy: str
    leverage: int
    margin_type: str
    usdt_per_trade: float
    starting_balance: float
    max_position_usdt: float
    fee_rate: float
    slippage_rate: float
    fast_ema: int
    slow_ema: int
    stoch_threshold_long: float
    stoch_threshold_short: float
    wick_tolerance: float
    adx_threshold: float
    sma_period: int
    stop_loss_pct: float
    take_profit_pct: float
    daily_loss_limit_usdt: float
    daily_loss_limit_pct: float
    max_consecutive_losses: int
    cooldown_minutes: int
    max_abs_funding_rate: float
    live_order_log_path: str
    poll_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        config = load_runtime_config()
        settings_config = config["settings"]
        capital_config = config["capital"]
        fees_config = config["fees"]
        ema_config = config["ema_cross"]
        ha_config = config["heikin_ashi_stoch"]
        risk_config = config["risk"]
        settings = cls(
            api_key=os.getenv("BINANCE_API_KEY", ""),
            api_secret=os.getenv("BINANCE_API_SECRET", ""),
            testnet=_bool("BINANCE_TESTNET", True),
            dry_run=_bool("DRY_RUN", True),
            symbol=str(settings_config["symbol"]).upper(),
            interval=str(settings_config["interval"]),
            strategy=str(settings_config["strategy"]).lower(),
            leverage=int(settings_config["leverage"]),
            margin_type=str(settings_config["margin_type"]).upper(),
            usdt_per_trade=float(capital_config["usdt_per_trade"]),
            starting_balance=float(capital_config["starting_balance"]),
            max_position_usdt=float(capital_config["max_position_usdt"]),
            fee_rate=float(fees_config["fee_rate"]),
            slippage_rate=float(fees_config["slippage_rate"]),
            fast_ema=int(ema_config["fast_ema"]),
            slow_ema=int(ema_config["slow_ema"]),
            stoch_threshold_long=float(ha_config["stoch_threshold_long"]),
            stoch_threshold_short=float(ha_config["stoch_threshold_short"]),
            wick_tolerance=float(ha_config["wick_tolerance"]),
            adx_threshold=float(ha_config["adx_threshold"]),
            sma_period=int(ha_config["sma_period"]),
            stop_loss_pct=float(ha_config["stop_loss_pct"]),
            take_profit_pct=float(ha_config["take_profit_pct"]),
            daily_loss_limit_usdt=float(risk_config["daily_loss_limit_usdt"]),
            daily_loss_limit_pct=float(risk_config["daily_loss_limit_pct"]),
            max_consecutive_losses=int(risk_config["max_consecutive_losses"]),
            cooldown_minutes=int(risk_config["cooldown_minutes"]),
            max_abs_funding_rate=float(risk_config["max_abs_funding_rate"]),
            live_order_log_path=str(settings_config["live_order_log_path"]),
            poll_seconds=int(settings_config["poll_seconds"]),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.strategy not in {"ema_cross", "heikin_ashi_stoch"}:
            raise ValueError("STRATEGY must be ema_cross or heikin_ashi_stoch.")
        if self.fast_ema >= self.slow_ema:
            raise ValueError("FAST_EMA must be smaller than SLOW_EMA.")
        if not 0 < self.stoch_threshold_long < self.stoch_threshold_short < 100:
            raise ValueError("Stoch thresholds must satisfy 0 < long < short < 100.")
        if self.sma_period < 2:
            raise ValueError("SMA_PERIOD must be at least 2.")
        if self.usdt_per_trade <= 0 or self.starting_balance <= 0:
            raise ValueError("Trade amount and starting balance must be positive.")
        if self.usdt_per_trade > self.max_position_usdt:
            raise ValueError("USDT_PER_TRADE cannot exceed MAX_POSITION_USDT.")
        if self.daily_loss_limit_usdt < 0 or self.daily_loss_limit_pct < 0:
            raise ValueError("Daily loss limits cannot be negative.")
        if self.max_consecutive_losses < 0 or self.cooldown_minutes < 0:
            raise ValueError("Cooldown settings cannot be negative.")
        if self.max_abs_funding_rate < 0:
            raise ValueError("MAX_ABS_FUNDING_RATE cannot be negative.")
