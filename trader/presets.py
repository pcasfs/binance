from __future__ import annotations

from dataclasses import replace
from typing import Any

from trader.config import Settings
from trader.runtime_config import load_runtime_config


def preset_names() -> list[str]:
    return sorted(_presets())


def apply_preset(settings: Settings, preset: str) -> Settings:
    if preset == "symbol-optimized":
        return apply_symbol_preset(settings, preset, settings.symbol, settings.interval)

    presets = _presets()
    if preset not in presets:
        valid = ", ".join(preset_names())
        raise ValueError(f"Unknown preset '{preset}'. Choose one of: {valid}")
    values = dict(presets[preset] or {})
    updated = replace(settings, **values)
    updated.validate()
    return updated


def apply_symbol_preset(settings: Settings, preset: str, symbol: str, interval: str) -> Settings:
    if preset != "symbol-optimized":
        return apply_preset(settings, preset)

    preset_config = _presets().get("symbol-optimized")
    if not isinstance(preset_config, dict):
        raise ValueError("symbol-optimized preset is missing from config/live.yaml.")

    required_interval = str(preset_config.get("interval", "1h"))
    if interval != required_interval:
        raise ValueError(f"symbol-optimized preset is only validated for interval={required_interval}.")

    symbols = preset_config.get("symbols", {})
    if not isinstance(symbols, dict):
        raise ValueError("symbol-optimized symbols must be an object in config/live.yaml.")

    symbol = symbol.upper()
    if symbol not in symbols:
        valid = ", ".join(sorted(symbols))
        raise ValueError(f"symbol-optimized has no settings for {symbol}. Choose one of: {valid}")

    values = dict(symbols[symbol])
    updated = replace(settings, symbol=symbol, interval=interval, **values)
    updated.validate()
    return updated


def _presets() -> dict[str, Any]:
    presets = load_runtime_config().get("presets", {})
    if not isinstance(presets, dict):
        raise ValueError("presets must be an object in config/live.yaml.")
    return presets
