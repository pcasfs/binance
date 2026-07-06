# Optimization Results

Data:
- Symbol: BTCUSDT
- Interval: 30m
- Period: 2026-03-30 00:00 UTC to 2026-07-05 12:00 UTC
- Grid: focused
- Folds: 3 chronological folds
- Score: average fold return + worst-fold stability bonus - drawdown penalty

The optimizer is intentionally not ranked by raw return only. This reduces the chance of selecting a parameter set that only worked in one short period.

## Best Long-Only Candidate

```text
Stoch threshold: 20
Wick tolerance: 0.0018
ADX threshold: 25
Stop loss: 2.00%
Take profit: 4.50%
Risk/reward: 2.25
```

Backtest:

```text
Final balance: 1002.8588
Total return: 0.29%
Max drawdown: 0.15%
Trades: 15
Win rate: 46.67%
Average trade return: 1.03%
```

## Best Long/Short Candidate

```text
Stoch threshold: 20
Wick tolerance: 0.0005
ADX threshold: 20
Stop loss: 2.00%
Take profit: 4.50%
Risk/reward: 2.25
```

Backtest:

```text
Final balance: 1005.0965
Total return: 0.51%
Max drawdown: 0.18%
Trades: 19
Win rate: 52.63%
Average trade return: 1.42%
Long PnL: 2.0112
Short PnL: 3.2373
```

## Commands

Long-only optimization:

```powershell
python main.py optimize --symbol BTCUSDT --interval 30m --side long --start 2026-03-30 --end 2026-07-05T12:00 --folds 3 --top 15 --grid focused
```

Long/short optimization:

```powershell
python main.py optimize --symbol BTCUSDT --interval 30m --side both --start 2026-03-30 --end 2026-07-05T12:00 --folds 3 --top 10 --grid focused
```

Backtest the saved long/short optimized preset:

```powershell
python main.py backtest --symbol BTCUSDT --interval 30m --preset optimized
```

Backtest the saved long-only optimized preset:

```powershell
python main.py backtest --symbol BTCUSDT --interval 30m --side long --preset optimized-long
```

Wide grid, slower:

```powershell
python main.py optimize --symbol BTCUSDT --interval 30m --side both --start 2026-03-30 --end 2026-07-05T12:00 --folds 3 --top 20 --grid wide
```

## Caution

These are candidates, not final live-trading settings. Before using them for live trading, re-run the optimizer on additional periods and at least one other major symbol such as ETHUSDT.
