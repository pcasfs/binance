from __future__ import annotations

from decimal import Decimal

from trader.models import Trade


def summarize(final_balance: Decimal, equity_curve: list[Decimal], trades: list[Trade]) -> dict[str, Decimal | int]:
    start = equity_curve[0]
    total_return = (final_balance - start) / start * Decimal("100")
    wins = [trade for trade in trades if trade.pnl > 0]
    losses = [trade for trade in trades if trade.pnl <= 0]
    win_rate = Decimal(len(wins)) / Decimal(len(trades)) * Decimal("100") if trades else Decimal("0")
    long_pnl = sum((trade.pnl for trade in trades if trade.side == "LONG"), Decimal("0"))
    short_pnl = sum((trade.pnl for trade in trades if trade.side == "SHORT"), Decimal("0"))
    avg_return = sum((trade.pnl_pct for trade in trades), Decimal("0")) / Decimal(len(trades)) if trades else Decimal("0")
    return {
        "final_balance": final_balance,
        "total_return": total_return,
        "max_drawdown": max_drawdown(equity_curve) * Decimal("100"),
        "trades": len(trades),
        "win_rate": win_rate,
        "long_pnl": long_pnl,
        "short_pnl": short_pnl,
        "avg_return": avg_return,
        "average_loss": sum((t.pnl for t in losses), Decimal("0")) / Decimal(len(losses)) if losses else Decimal("0"),
        "average_win": sum((t.pnl for t in wins), Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0"),
    }


def print_report(symbol: str, interval: str, final_balance: Decimal, equity_curve: list[Decimal], trades: list[Trade]) -> None:
    metrics = summarize(final_balance, equity_curve, trades)

    print(f"Backtest {symbol} {interval}")
    print(f"Final balance: {metrics['final_balance']:.4f}")
    print(f"Total return: {metrics['total_return']:.2f}%")
    print(f"Max drawdown: {metrics['max_drawdown']:.2f}%")
    print(f"Trades: {metrics['trades']}")
    print(f"Win rate: {metrics['win_rate']:.2f}%")
    print(f"Long PnL: {metrics['long_pnl']:.4f}")
    print(f"Short PnL: {metrics['short_pnl']:.4f}")
    print(f"Average return: {metrics['avg_return']:.2f}%")
    if metrics["average_loss"]:
        print(f"Average loss: {metrics['average_loss']:.4f}")
    if metrics["average_win"]:
        print(f"Average win: {metrics['average_win']:.4f}")


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
