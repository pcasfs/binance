from __future__ import annotations

from decimal import Decimal

from trader.backtest import Backtester
from trader.config import Settings
from trader.data_loader import csv_path, download_to_csv
from trader.presets import apply_symbol_preset


DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]


def parse_symbols(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_SYMBOLS
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def download_many(settings: Settings, symbols: list[str], interval: str, days: int) -> None:
    for symbol in symbols:
        download_to_csv(settings, symbol, interval, days)


def portfolio_backtest(
    settings: Settings,
    symbols: list[str],
    interval: str,
    side: str,
    start: str | None,
    end: str | None,
    preset: str = "default",
) -> None:
    rows: list[dict[str, object]] = []
    total_pnl = Decimal("0")
    total_trades = 0
    weighted_return = Decimal("0")

    for symbol in symbols:
        path = csv_path(symbol, interval)
        if not path.exists():
            print(f"SKIP {symbol}: missing {path}. Run download-many first.")
            continue
        symbol_settings = apply_symbol_preset(settings, preset, symbol, interval)
        result = Backtester(symbol_settings, symbol, interval, side=side, start=start, end=end).run(print_summary=False)
        metrics = result["metrics"]
        rows.append(
            {
                "symbol": symbol,
                "sl_pct": symbol_settings.stop_loss_pct * 100,
                "tp_pct": symbol_settings.take_profit_pct * 100,
                **metrics,
            }
        )
        total_pnl += Decimal(str(metrics["final_balance"])) - Decimal(str(symbol_settings.starting_balance))
        total_trades += int(metrics["trades"])
        weighted_return += Decimal(str(metrics["total_return"]))

    print_portfolio_report(rows, total_pnl, total_trades, weighted_return)


def print_portfolio_report(
    rows: list[dict[str, object]],
    total_pnl: Decimal,
    total_trades: int,
    weighted_return: Decimal,
) -> None:
    if not rows:
        print("No portfolio results.")
        return

    header = (
        f"{'Symbol':<10} {'Return':>8} {'MDD':>8} {'Trades':>7} {'Win%':>8} "
        f"{'LongPnL':>10} {'ShortPnL':>10} {'AvgRet':>8} {'SL%':>6} {'TP%':>6}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['symbol']:<10} {row['total_return']:>7.2f}% {row['max_drawdown']:>7.2f}% "
            f"{row['trades']:>7} {row['win_rate']:>7.2f}% {row['long_pnl']:>10.4f} "
            f"{row['short_pnl']:>10.4f} {row['avg_return']:>7.2f}% "
            f"{row['sl_pct']:>5.2f}% {row['tp_pct']:>5.2f}%"
        )

    avg_return = weighted_return / Decimal(len(rows))
    print("-" * len(header))
    print(f"Symbols: {len(rows)}")
    print(f"Total trades: {total_trades}")
    print(f"Average symbol return: {avg_return:.2f}%")
    print(f"Total PnL across symbols: {total_pnl:.4f}")
