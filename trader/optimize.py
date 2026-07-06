from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal
from itertools import product

import pandas as pd

from trader.config import Settings
from trader.data_loader import load_candles
from trader.models import Candle
from trader.strategy import HeikinAshiStochStrategy

UTC = timezone.utc


@dataclass(frozen=True)
class Params:
    stoch: float
    wick: float
    adx: float
    stop_loss: float
    take_profit: float

    @property
    def rr(self) -> float:
        return self.take_profit / self.stop_loss


@dataclass(frozen=True)
class Metrics:
    final_balance: float
    total_return: float
    max_drawdown: float
    trades: int
    win_rate: float
    avg_trade_return: float
    profit_factor: float


@dataclass(frozen=True)
class Result:
    params: Params
    full: Metrics
    folds: tuple[Metrics, ...]
    score: float


class Optimizer:
    def __init__(
        self,
        settings: Settings,
        symbol: str,
        interval: str,
        side: str = "long",
        start: str | None = None,
        end: str | None = None,
        folds: int = 3,
        top: int = 10,
        grid: str = "focused",
    ) -> None:
        self.settings = settings
        self.symbol = symbol.upper()
        self.interval = interval
        self.side = side
        self.start_ms = parse_utc_ms(start, is_end=False)
        self.end_ms = parse_utc_ms(end, is_end=True)
        self.folds = max(2, folds)
        self.top = top
        self.grid = grid
        self.candles = load_candles(self.symbol, self.interval)
        base_strategy = HeikinAshiStochStrategy(sma_period=settings.sma_period)
        self.warmup = base_strategy.warmup_candles
        self.df = base_strategy._indicator_frame(self.candles)
        self.df["open_time"] = [candle.open_time for candle in self.candles]
        self.df["close_time"] = [candle.close_time for candle in self.candles]
        self.close = self.df["close"].tolist()
        self.sma = self.df["sma"].tolist()
        self.stoch_k = self.df["stoch_k"].tolist()
        self.stoch_d = self.df["stoch_d"].tolist()
        self.adx = self.df["adx"].tolist()
        self.ha_open = self.df["ha_open"].tolist()
        self.ha_high = self.df["ha_high"].tolist()
        self.ha_low = self.df["ha_low"].tolist()
        self.ha_close = self.df["ha_close"].tolist()

    def run(self) -> list[Result]:
        params_grid = list(self._params_grid())
        periods = self._fold_periods()
        results: list[Result] = []

        print(f"Optimizing {len(params_grid)} parameter sets on {self.symbol} {self.interval}")
        print(f"Side={self.side}, folds={len(periods)}, anti-overfit score uses fold stability")

        for params in params_grid:
            full = self._simulate(params, self.start_ms, self.end_ms)
            fold_metrics = tuple(self._simulate(params, start, end) for start, end in periods)
            score = self._score(full, fold_metrics)
            results.append(Result(params=params, full=full, folds=fold_metrics, score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        self._print_results(results[: self.top])
        return results

    def _params_grid(self) -> list[Params]:
        if self.grid == "wide":
            stoch_values = [20, 25, 28, 32, 35, 40]
            wick_values = [0.0005, 0.0010, 0.0015, 0.0018, 0.0020, 0.0025]
            adx_values = [15, 20, 25, 30]
            stop_values = [0.010, 0.0125, 0.015, 0.020]
            take_values = [0.020, 0.025, 0.030, 0.0375, 0.045, 0.050]
        else:
            stoch_values = [20, 32, 35]
            wick_values = [0.0005, 0.0018, 0.0020]
            adx_values = [20, 25]
            stop_values = [0.010, 0.015, 0.020]
            take_values = [0.020, 0.030, 0.0375, 0.045]
        params: list[Params] = []
        for stoch, wick, adx, stop_loss, take_profit in product(
            stoch_values,
            wick_values,
            adx_values,
            stop_values,
            take_values,
        ):
            if take_profit / stop_loss < 1.4:
                continue
            params.append(Params(stoch, wick, adx, stop_loss, take_profit))
        return params

    def _fold_periods(self) -> list[tuple[int, int]]:
        start = self.start_ms or int(self.df["open_time"].iloc[self.warmup])
        end = self.end_ms or int(self.df["open_time"].iloc[-1])
        span = end - start
        periods: list[tuple[int, int]] = []
        for index in range(self.folds):
            fold_start = start + (span * index // self.folds)
            fold_end = start + (span * (index + 1) // self.folds)
            periods.append((fold_start, fold_end))
        return periods

    def _simulate(self, params: Params, start_ms: int | None, end_ms: int | None) -> Metrics:
        balance = Decimal(str(self.settings.starting_balance))
        equity_curve = [balance]
        trade_returns: list[Decimal] = []
        position: tuple[str, int, Decimal, Decimal] | None = None

        for index in range(self.warmup, len(self.candles)):
            candle = self.candles[index]
            if end_ms is not None and candle.open_time > end_ms:
                break

            in_period = self._in_period(candle.open_time, start_ms, end_ms)
            if in_period and position is not None:
                pos_side, _entry_time, entry_price, quantity = position
                exit_price = self._exit_price(pos_side, entry_price, candle, params)
                if exit_price is not None:
                    direction = Decimal("1") if pos_side == "LONG" else Decimal("-1")
                    gross = (exit_price - entry_price) * quantity * direction
                    fee = exit_price * quantity * Decimal(str(self.settings.fee_rate))
                    balance += gross - fee
                    trade_returns.append((exit_price - entry_price) / entry_price * direction * Decimal("100"))
                    position = None

            if in_period:
                equity_curve.append(self._mark_equity(balance, position, candle.close))

            if position is None and index + 1 < len(self.candles):
                next_candle = self.candles[index + 1]
                if self._in_period(next_candle.open_time, start_ms, end_ms):
                    action = self._signal(index, params)
                    if self._allowed(action):
                        entry_price = next_candle.open
                        quantity = Decimal(str(self.settings.usdt_per_trade)) / entry_price
                        entry_fee = entry_price * quantity * Decimal(str(self.settings.fee_rate))
                        balance -= entry_fee
                        position = (action, next_candle.open_time, entry_price, quantity)

        return self._metrics(balance, equity_curve, trade_returns)

    def _signal(self, index: int, params: Params) -> str:
        sma = self.sma[index]
        stoch_k = self.stoch_k[index]
        stoch_d = self.stoch_d[index]
        prev_k = self.stoch_k[index - 1]
        prev_d = self.stoch_d[index - 1]
        adx = self.adx[index]
        ha_open = self.ha_open[index]
        ha_high = self.ha_high[index]
        ha_low = self.ha_low[index]
        ha_close = self.ha_close[index]
        close = self.close[index]

        values = [sma, stoch_k, stoch_d, prev_k, prev_d, adx, ha_open, ha_high, ha_low, ha_close]
        if any(pd.isna(value) for value in values):
            return "HOLD"

        bullish = ha_close > ha_open
        bearish = ha_close < ha_open
        no_lower_wick = abs(ha_open - ha_low) / ha_open < params.wick
        no_upper_wick = abs(ha_high - ha_open) / ha_open < params.wick
        golden = prev_k <= prev_d and stoch_k > stoch_d and stoch_k < params.stoch
        death = prev_k >= prev_d and stoch_k < stoch_d and stoch_k > (100 - params.stoch)
        strong = adx > params.adx

        if close > sma and golden and bullish and no_lower_wick and strong:
            return "LONG"
        if close < sma and death and bearish and no_upper_wick and strong:
            return "SHORT"
        return "HOLD"

    @staticmethod
    def _exit_price(side: str, entry_price: Decimal, candle: Candle, params: Params) -> Decimal | None:
        stop_loss = Decimal(str(params.stop_loss))
        take_profit = Decimal(str(params.take_profit))
        if side == "LONG":
            stop = entry_price * (Decimal("1") - stop_loss)
            target = entry_price * (Decimal("1") + take_profit)
            if candle.low <= stop:
                return stop
            if candle.high >= target:
                return target
        else:
            stop = entry_price * (Decimal("1") + stop_loss)
            target = entry_price * (Decimal("1") - take_profit)
            if candle.high >= stop:
                return stop
            if candle.low <= target:
                return target
        return None

    def _allowed(self, action: str) -> bool:
        if action == "LONG":
            return self.side in {"both", "long"}
        if action == "SHORT":
            return self.side in {"both", "short"}
        return False

    @staticmethod
    def _in_period(timestamp_ms: int, start_ms: int | None, end_ms: int | None) -> bool:
        if start_ms is not None and timestamp_ms < start_ms:
            return False
        if end_ms is not None and timestamp_ms > end_ms:
            return False
        return True

    @staticmethod
    def _mark_equity(
        balance: Decimal,
        position: tuple[str, int, Decimal, Decimal] | None,
        price: Decimal,
    ) -> Decimal:
        if position is None:
            return balance
        side, _entry_time, entry_price, quantity = position
        direction = Decimal("1") if side == "LONG" else Decimal("-1")
        return balance + ((price - entry_price) * quantity * direction)

    def _metrics(self, balance: Decimal, equity_curve: list[Decimal], trade_returns: list[Decimal]) -> Metrics:
        start = Decimal(str(self.settings.starting_balance))
        total_return = float((balance - start) / start * Decimal("100"))
        max_dd = float(max_drawdown(equity_curve) * Decimal("100"))
        wins = [item for item in trade_returns if item > 0]
        losses = [item for item in trade_returns if item <= 0]
        win_rate = float(Decimal(len(wins)) / Decimal(len(trade_returns)) * Decimal("100")) if trade_returns else 0.0
        avg = float(sum(trade_returns, Decimal("0")) / Decimal(len(trade_returns))) if trade_returns else 0.0
        positive = sum(wins, Decimal("0"))
        negative = abs(sum(losses, Decimal("0")))
        profit_factor = float(positive / negative) if negative else (999.0 if positive else 0.0)
        return Metrics(
            final_balance=float(balance),
            total_return=total_return,
            max_drawdown=max_dd,
            trades=len(trade_returns),
            win_rate=win_rate,
            avg_trade_return=avg,
            profit_factor=profit_factor,
        )

    @staticmethod
    def _score(full: Metrics, folds: tuple[Metrics, ...]) -> float:
        if full.trades < 8:
            return -9999 + full.trades
        fold_returns = [item.total_return for item in folds]
        positive_folds = sum(1 for item in fold_returns if item > 0)
        avg_fold_return = sum(fold_returns) / len(fold_returns)
        worst_fold = min(fold_returns)
        avg_dd = sum(item.max_drawdown for item in folds) / len(folds)
        trade_penalty = 0 if full.trades >= 12 else (12 - full.trades) * 0.05
        return avg_fold_return + (0.35 * worst_fold) + (0.10 * positive_folds) - (0.65 * avg_dd) - trade_penalty

    def _print_results(self, results: list[Result]) -> None:
        print("")
        header = (
            f"{'Rank':>4}  {'Score':>6}  {'Return':>7}  {'MDD':>6}  {'Trades':>6}  {'Win%':>6}  "
            f"{'Avg%':>7}  {'PF':>5}  {'Stoch':>6}  {'Wick':>8}  {'ADX':>5}  "
            f"{'SL%':>6}  {'TP%':>6}  {'RR':>5}  {'F1':>7}  {'F2':>7}  {'F3':>7}"
        )
        print(header)
        print("-" * len(header))
        for rank, result in enumerate(results, start=1):
            p = result.params
            f = result.full
            folds = [item.total_return for item in result.folds]
            while len(folds) < 3:
                folds.append(0.0)
            print(
                f"{rank:>4}  {result.score:>6.2f}  {f.total_return:>6.2f}%  {f.max_drawdown:>5.2f}%  "
                f"{f.trades:>6}  {f.win_rate:>5.1f}%  {f.avg_trade_return:>6.2f}%  {f.profit_factor:>5.2f}  "
                f"{p.stoch:>6.0f}  {p.wick:>8.4f}  {p.adx:>5.0f}  "
                f"{p.stop_loss * 100:>5.2f}%  {p.take_profit * 100:>5.2f}%  {p.rr:>5.2f}  "
                f"{folds[0]:>6.2f}%  {folds[1]:>6.2f}%  {folds[2]:>6.2f}%"
            )


def parse_utc_ms(value: str | None, is_end: bool) -> int | None:
    if not value:
        return None
    if len(value) == 10:
        day = datetime.fromisoformat(value).date()
        parsed = datetime.combine(day, time.max if is_end else time.min, tzinfo=UTC)
    else:
        parsed = datetime.fromisoformat(value.replace(" ", "T"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def max_drawdown(equity_curve: list[Decimal]) -> Decimal:
    peak = equity_curve[0]
    worst = Decimal("0")
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak if peak else Decimal("0")
        if drawdown > worst:
            worst = drawdown
    return worst
