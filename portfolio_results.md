# Portfolio Results

Command:

```powershell
python main.py portfolio --symbols BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT --interval 1h --preset optimized --side both
```

Result:

```text
Symbol       Return      MDD  Trades     Win%    LongPnL   ShortPnL   AvgRet
----------------------------------------------------------------------------
BTCUSDT       3.01%    0.64%      23   52.17%    10.0558    21.0286    1.39%
ETHUSDT       0.13%    0.97%      15   33.33%    -3.6986     5.6024    0.17%
SOLUSDT       0.31%    1.02%      11   36.36%     2.7988     0.7604    0.36%
BNBUSDT      -1.56%    2.03%      20   20.00%    -7.3972    -7.4028   -0.70%
XRPUSDT      -0.78%    0.96%      10   20.00%    -3.6986    -3.7014   -0.70%
----------------------------------------------------------------------------
Symbols: 5
Total trades: 79
Average symbol return: 0.22%
Total PnL across symbols: 11.0674
```

Initial read:

- BTCUSDT works best with the current `optimized` preset.
- ETHUSDT and SOLUSDT are slightly positive, but not strong.
- BNBUSDT and XRPUSDT reduce the portfolio result and should not be included without separate optimization or stronger filters.
- Increasing symbols does increase trade count, but symbol selection matters more than simply adding more markets.
