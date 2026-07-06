from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from trader.config import Settings
from trader.models import Candle, Signal


class Strategy:
    warmup_candles = 1

    def signal(self, candles: list[Candle]) -> Signal:
        raise NotImplementedError


class EmaCrossStrategy(Strategy):
    def __init__(self, fast_period: int, slow_period: int) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.warmup_candles = slow_period + 3

    def signal(self, candles: list[Candle]) -> Signal:
        if len(candles) < self.warmup_candles:
            return Signal("HOLD", f"Need at least {self.warmup_candles} candles.")

        closes = [candle.close for candle in candles]
        fast = self._ema_series(closes, self.fast_period)
        slow = self._ema_series(closes, self.slow_period)
        prev_fast, last_fast = fast[-2], fast[-1]
        prev_slow, last_slow = slow[-2], slow[-1]

        if prev_fast <= prev_slow and last_fast > last_slow:
            return Signal("LONG", f"EMA{self.fast_period} crossed above EMA{self.slow_period}.")
        if prev_fast >= prev_slow and last_fast < last_slow:
            return Signal("SHORT", f"EMA{self.fast_period} crossed below EMA{self.slow_period}.")
        return Signal("HOLD", "No EMA cross.")

    @staticmethod
    def _ema_series(values: list[Decimal], period: int) -> list[Decimal]:
        multiplier = Decimal("2") / Decimal(period + 1)
        ema = values[0]
        output = [ema]
        for value in values[1:]:
            ema = (value - ema) * multiplier + ema
            output.append(ema)
        return output


@dataclass(frozen=True)
class HeikinAshiPoint:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


class HeikinAshiStochStrategy(Strategy):
    def __init__(
        self,
        sma_period: int = 200,
        stoch_threshold_long: Decimal = Decimal("32"),
        stoch_threshold_short: Decimal = Decimal("68"),
        wick_tolerance: Decimal = Decimal("0.0018"),
        adx_threshold: Decimal = Decimal("20"),
    ) -> None:
        self.sma_period = sma_period
        self.stoch_threshold_long = stoch_threshold_long
        self.stoch_threshold_short = stoch_threshold_short
        self.wick_tolerance = wick_tolerance
        self.adx_threshold = adx_threshold
        self.warmup_candles = max(sma_period, 35)

    def signal(self, candles: list[Candle]) -> Signal:
        if len(candles) < self.warmup_candles:
            return Signal("HOLD", f"Need at least {self.warmup_candles} candles.")
        return self.signal_series(candles)[-1]

    def signal_series(self, candles: list[Candle]) -> list[Signal]:
        df = self._indicator_frame(candles)
        signals: list[Signal] = []
        for index in range(len(df)):
            if index < self.warmup_candles:
                signals.append(Signal("HOLD", f"Need at least {self.warmup_candles} candles."))
                continue

            curr = df.iloc[index]
            prev = df.iloc[index - 1]
            required = ["sma", "stoch_k", "stoch_d", "adx", "ha_open", "ha_high", "ha_low", "ha_close"]
            if curr[required].isna().any() or prev[["stoch_k", "stoch_d"]].isna().any():
                signals.append(Signal("HOLD", "Indicators are not warmed up."))
                continue

            is_ha_bullish = curr["ha_close"] > curr["ha_open"]
            is_ha_bearish = curr["ha_close"] < curr["ha_open"]
            no_lower_wick = abs(curr["ha_open"] - curr["ha_low"]) / curr["ha_open"] < float(self.wick_tolerance)
            no_upper_wick = abs(curr["ha_high"] - curr["ha_open"]) / curr["ha_open"] < float(self.wick_tolerance)
            golden_cross = (
                prev["stoch_k"] <= prev["stoch_d"]
                and curr["stoch_k"] > curr["stoch_d"]
                and curr["stoch_k"] < float(self.stoch_threshold_long)
            )
            death_cross = (
                prev["stoch_k"] >= prev["stoch_d"]
                and curr["stoch_k"] < curr["stoch_d"]
                and curr["stoch_k"] > float(self.stoch_threshold_short)
            )
            trend_up = curr["close"] > curr["sma"]
            trend_down = curr["close"] < curr["sma"]
            trend_strength = curr["adx"] > float(self.adx_threshold)

            if trend_up and golden_cross and is_ha_bullish and no_lower_wick and trend_strength:
                signals.append(Signal("LONG", self._reason_float("long", curr)))
            elif trend_down and death_cross and is_ha_bearish and no_upper_wick and trend_strength:
                signals.append(Signal("SHORT", self._reason_float("short", curr)))
            else:
                signals.append(Signal("HOLD", "No Heikin-Ashi/StochRSI setup."))
        return signals

    def _indicator_frame(self, candles: list[Candle]) -> pd.DataFrame:
        df = pd.DataFrame(
            {
                "open": [float(candle.open) for candle in candles],
                "high": [float(candle.high) for candle in candles],
                "low": [float(candle.low) for candle in candles],
                "close": [float(candle.close) for candle in candles],
            }
        )

        ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
        ha_open = ha_close.copy()
        if len(ha_open) > 0:
            ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
            for index in range(1, len(ha_open)):
                ha_open.iloc[index] = (ha_open.iloc[index - 1] + ha_close.iloc[index - 1]) / 2
        df["ha_open"] = ha_open
        df["ha_high"] = pd.concat([df["high"], ha_open, ha_close], axis=1).max(axis=1)
        df["ha_low"] = pd.concat([df["low"], ha_open, ha_close], axis=1).min(axis=1)
        df["ha_close"] = ha_close
        df["sma"] = df["close"].rolling(self.sma_period).mean()

        rsi_values = self._pandas_rsi(df["close"], length=14)
        min_rsi = rsi_values.rolling(14).min()
        max_rsi = rsi_values.rolling(14).max()
        stoch = 100 * (rsi_values - min_rsi) / (max_rsi - min_rsi).replace(0, pd.NA)
        df["stoch_k"] = stoch.rolling(3).mean()
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()
        df["adx"] = self._pandas_adx(df["high"], df["low"], df["close"], length=14)
        return df

    @staticmethod
    def _pandas_rsi(series: pd.Series, length: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _pandas_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_values = true_range.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
        plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr_values
        minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr_values
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
        return dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    @staticmethod
    def _reason_float(side: str, row: pd.Series) -> str:
        return (
            f"HA/Stoch {side}: close={row['close']:.2f}, StochK={row['stoch_k']:.2f}, "
            f"StochD={row['stoch_d']:.2f}, ADX={row['adx']:.2f}, SMA={row['sma']:.2f}"
        )

    def _signal_at(
        self,
        candles: list[Candle],
        index: int,
        ha: list[HeikinAshiPoint],
        stoch_k: list[Decimal | None],
        stoch_d: list[Decimal | None],
        adx_values: list[Decimal | None],
        sma_values: list[Decimal | None],
    ) -> Signal:
        if index < self.warmup_candles:
            return Signal("HOLD", f"Need at least {self.warmup_candles} candles.")

        curr = candles[index]
        prev = candles[index - 1]
        curr_ha = ha[index]
        curr_k = stoch_k[index]
        curr_d = stoch_d[index]
        prev_k = stoch_k[index - 1]
        prev_d = stoch_d[index - 1]
        curr_adx = adx_values[index]
        sma = sma_values[index]

        if curr_k is None or curr_d is None or prev_k is None or prev_d is None or curr_adx is None or sma is None:
            return Signal("HOLD", "Indicators are not warmed up.")

        is_ha_bullish = curr_ha.close > curr_ha.open
        is_ha_bearish = curr_ha.close < curr_ha.open
        no_lower_wick = abs(curr_ha.open - curr_ha.low) / curr_ha.open < self.wick_tolerance
        no_upper_wick = abs(curr_ha.high - curr_ha.open) / curr_ha.open < self.wick_tolerance
        golden_cross = prev_k <= prev_d and curr_k > curr_d and curr_k < self.stoch_threshold_long
        death_cross = prev_k >= prev_d and curr_k < curr_d and curr_k > self.stoch_threshold_short
        trend_up = curr.close > sma
        trend_down = curr.close < sma
        trend_strength = curr_adx > self.adx_threshold

        if trend_up and golden_cross and is_ha_bullish and no_lower_wick and trend_strength:
            return Signal("LONG", self._reason("long", curr, prev, curr_k, curr_d, curr_adx, sma))
        if trend_down and death_cross and is_ha_bearish and no_upper_wick and trend_strength:
            return Signal("SHORT", self._reason("short", curr, prev, curr_k, curr_d, curr_adx, sma))
        return Signal("HOLD", "No Heikin-Ashi/StochRSI setup.")

    @staticmethod
    def _sma(values: list[Decimal], period: int) -> list[Decimal | None]:
        output: list[Decimal | None] = [None] * len(values)
        rolling = Decimal("0")
        for index, value in enumerate(values):
            rolling += value
            if index >= period:
                rolling -= values[index - period]
            if index >= period - 1:
                output[index] = rolling / Decimal(period)
        return output

    @staticmethod
    def _heikin_ashi(candles: list[Candle]) -> list[HeikinAshiPoint]:
        points: list[HeikinAshiPoint] = []
        prev_ha_open: Decimal | None = None
        prev_ha_close: Decimal | None = None
        for candle in candles:
            ha_close = (candle.open + candle.high + candle.low + candle.close) / Decimal("4")
            if prev_ha_open is None or prev_ha_close is None:
                ha_open = (candle.open + candle.close) / Decimal("2")
            else:
                ha_open = (prev_ha_open + prev_ha_close) / Decimal("2")
            ha_high = max(candle.high, ha_open, ha_close)
            ha_low = min(candle.low, ha_open, ha_close)
            points.append(HeikinAshiPoint(ha_open, ha_high, ha_low, ha_close))
            prev_ha_open = ha_open
            prev_ha_close = ha_close
        return points

    @staticmethod
    def _rsi(values: list[Decimal], period: int = 14) -> list[Decimal | None]:
        output: list[Decimal | None] = [None] * len(values)
        if len(values) <= period:
            return output
        gains: list[Decimal] = []
        losses: list[Decimal] = []
        for index in range(1, period + 1):
            change = values[index] - values[index - 1]
            gains.append(max(change, Decimal("0")))
            losses.append(max(-change, Decimal("0")))
        avg_gain = sum(gains, Decimal("0")) / Decimal(period)
        avg_loss = sum(losses, Decimal("0")) / Decimal(period)
        output[period] = HeikinAshiStochStrategy._rsi_value(avg_gain, avg_loss)
        for index in range(period + 1, len(values)):
            change = values[index] - values[index - 1]
            gain = max(change, Decimal("0"))
            loss = max(-change, Decimal("0"))
            avg_gain = ((avg_gain * Decimal(period - 1)) + gain) / Decimal(period)
            avg_loss = ((avg_loss * Decimal(period - 1)) + loss) / Decimal(period)
            output[index] = HeikinAshiStochStrategy._rsi_value(avg_gain, avg_loss)
        return output

    @staticmethod
    def _rsi_value(avg_gain: Decimal, avg_loss: Decimal) -> Decimal:
        if avg_loss == 0:
            return Decimal("100")
        rs = avg_gain / avg_loss
        return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    @staticmethod
    def _stoch_rsi(
        values: list[Decimal],
        period: int = 14,
        k_period: int = 3,
        d_period: int = 3,
    ) -> tuple[list[Decimal | None], list[Decimal | None]]:
        rsi_values = HeikinAshiStochStrategy._rsi(values, period)
        stoch: list[Decimal | None] = [None] * len(values)
        k_values: list[Decimal | None] = [None] * len(values)
        d_values: list[Decimal | None] = [None] * len(values)
        for index in range(len(values)):
            window = rsi_values[index - period + 1 : index + 1]
            if len(window) < period or any(value is None for value in window):
                continue
            typed_window = [value for value in window if value is not None]
            low = min(typed_window)
            high = max(typed_window)
            if high == low:
                continue
            current_rsi = rsi_values[index]
            if current_rsi is not None:
                stoch[index] = Decimal("100") * (current_rsi - low) / (high - low)

            k_window = stoch[index - k_period + 1 : index + 1]
            if len(k_window) == k_period and all(value is not None for value in k_window):
                k_values[index] = sum((value for value in k_window if value is not None), Decimal("0")) / Decimal(k_period)

            d_window = k_values[index - d_period + 1 : index + 1]
            if len(d_window) == d_period and all(value is not None for value in d_window):
                d_values[index] = sum((value for value in d_window if value is not None), Decimal("0")) / Decimal(d_period)
        return k_values, d_values

    @staticmethod
    def _adx(candles: list[Candle], period: int = 14) -> list[Decimal | None]:
        tr_values: list[Decimal | None] = [None] * len(candles)
        plus_dm: list[Decimal | None] = [None] * len(candles)
        minus_dm: list[Decimal | None] = [None] * len(candles)
        for index in range(1, len(candles)):
            curr = candles[index]
            prev = candles[index - 1]
            tr_values[index] = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
            up_move = curr.high - prev.high
            down_move = prev.low - curr.low
            plus_dm[index] = up_move if up_move > down_move and up_move > 0 else Decimal("0")
            minus_dm[index] = down_move if down_move > up_move and down_move > 0 else Decimal("0")

        adx_values: list[Decimal | None] = [None] * len(candles)
        if len(candles) <= period * 2:
            return adx_values

        atr = sum((value for value in tr_values[1 : period + 1] if value is not None), Decimal("0"))
        plus = sum((value for value in plus_dm[1 : period + 1] if value is not None), Decimal("0"))
        minus = sum((value for value in minus_dm[1 : period + 1] if value is not None), Decimal("0"))
        dx_values: list[Decimal | None] = [None] * len(candles)

        for index in range(period + 1, len(candles)):
            if index > period + 1:
                atr = atr - (atr / Decimal(period)) + (tr_values[index] or Decimal("0"))
                plus = plus - (plus / Decimal(period)) + (plus_dm[index] or Decimal("0"))
                minus = minus - (minus / Decimal(period)) + (minus_dm[index] or Decimal("0"))
            if atr == 0:
                continue
            plus_di = Decimal("100") * plus / atr
            minus_di = Decimal("100") * minus / atr
            if plus_di + minus_di == 0:
                continue
            dx_values[index] = Decimal("100") * abs(plus_di - minus_di) / (plus_di + minus_di)

        first_adx_index = period * 2
        first_dx = [value for value in dx_values[period + 1 : first_adx_index + 1] if value is not None]
        if len(first_dx) < period:
            return adx_values
        adx = sum(first_dx, Decimal("0")) / Decimal(period)
        adx_values[first_adx_index] = adx
        for index in range(first_adx_index + 1, len(candles)):
            dx = dx_values[index]
            if dx is None:
                continue
            adx = ((adx * Decimal(period - 1)) + dx) / Decimal(period)
            adx_values[index] = adx
        return adx_values

    @staticmethod
    def _reason(side: str, curr: Candle, prev: Candle, stoch_k: Decimal, stoch_d: Decimal, adx: Decimal, sma: Decimal) -> str:
        return (
            f"HA/Stoch {side}: close={curr.close}, prev_close={prev.close}, "
            f"StochK={stoch_k:.2f}, StochD={stoch_d:.2f}, ADX={adx:.2f}, SMA={sma:.2f}"
        )


def build_strategy(settings: Settings) -> Strategy:
    if settings.strategy == "ema_cross":
        return EmaCrossStrategy(settings.fast_ema, settings.slow_ema)
    return HeikinAshiStochStrategy(
        sma_period=settings.sma_period,
        stoch_threshold_long=Decimal(str(settings.stoch_threshold_long)),
        stoch_threshold_short=Decimal(str(settings.stoch_threshold_short)),
        wick_tolerance=Decimal(str(settings.wick_tolerance)),
        adx_threshold=Decimal(str(settings.adx_threshold)),
    )
