# Symbol-Optimized 1h Portfolio

기준일: 2026-07-06

목표는 BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT 1시간봉을 각 심볼별 최적 옵션으로 운용할 수 있게 만들고, 실거래 전 포트폴리오 백테스트를 다시 확인하는 것이다.

## Implemented

- `symbol-optimized` preset 추가
- `portfolio` 백테스트에서 심볼별 옵션 적용
- `live` 명령에서 여러 심볼을 받을 수 있게 준비
- 같은 심볼에 이미 포지션이 있으면 신규 진입 차단
- 하루 손실 한도 도달 시 신규 진입 차단
- 연속 손실 후 쿨다운
- 펀딩비가 방향에 불리하면 신규 진입 차단
- 실제 주문 시도/성공/실패 CSV 로그 저장

제외한 것:

- 전체 동시 포지션 수 제한
- 30m/1h 동시 방향 필터
- dry-run 전용 로그
- 페이퍼 트레이딩 전용 구조
- 실제 주문 실행
- `DRY_RUN=false` 변경

## Symbol Settings

| Symbol | Interval | Stoch Long | Stoch Short | Wick | ADX | SL | TP |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 1h | 32 | 68 | 0.0020 | 20 | 1.00% | 4.50% |
| ETHUSDT | 1h | 32 | 68 | 0.0018 | 25 | 1.50% | 3.00% |
| SOLUSDT | 1h | 35 | 65 | 0.0018 | 20 | 2.00% | 3.00% |
| DOGEUSDT | 1h | 32 | 68 | 0.0020 | 20 | 2.00% | 3.75% |

## Backtest Command

```powershell
python main.py portfolio --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized --side both
```

## Backtest Result

```text
Symbol       Return      MDD  Trades     Win%    LongPnL   ShortPnL   AvgRet    SL%    TP%
------------------------------------------------------------------------------------------
BTCUSDT       5.23%    0.98%      89   30.34%    24.0898    31.8536    0.67%  1.00%  4.50%
ETHUSDT       2.26%    0.99%      54   44.44%    10.9952    13.8460    0.50%  1.50%  3.00%
SOLUSDT       7.48%    0.63%      65   64.62%    43.5820    33.8140    1.23%  2.00%  3.00%
DOGEUSDT      4.72%    1.58%      63   49.21%     4.4578    45.2887    0.83%  2.00%  3.75%
------------------------------------------------------------------------------------------
Symbols: 4
Total trades: 271
Average symbol return: 4.93%
Total PnL across symbols: 197.0071
```

## Live Command Prepared

실제 실행은 하지 않았다. 구조만 준비되어 있다.

```powershell
python main.py live --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized
```

## Preflight Command

실거래 전에는 먼저 아래 점검 명령을 실행한다. 이 명령은 주문을 넣지 않고, 심볼별 거래 규칙, 캔들 조회, 수량 정밀도, 펀딩비, 가능한 경우 선물 잔고/포지션 모드를 확인한다.

```powershell
python main.py preflight --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized
```

현재 실행 결과:

```text
Public checks: OK
Quantity precision checks: OK
Signed checks: FAIL - Invalid API-key, IP, or permissions for action
```

현재 `.env`가 `BINANCE_TESTNET=true`이므로, signed check를 통과하려면 테스트넷용 Futures API 키가 필요하다. 메인넷 키를 쓸 경우 `BINANCE_TESTNET=false`로 맞춘 뒤 다시 점검해야 한다.

## Risk Settings

아래 값은 `config/live.yaml`에서 조절한다. `0`이면 해당 제한은 비활성이다.

```yaml
risk:
  daily_loss_limit_usdt: 0
  daily_loss_limit_pct: 0
  max_consecutive_losses: 0
  cooldown_minutes: 0
  max_abs_funding_rate: 0

settings:
  live_order_log_path: logs/live_orders.csv
```

펀딩비 필터는 방향별로 판단한다.

- 롱: 펀딩비가 양수이고 설정 임계값보다 크면 불리한 것으로 본다.
- 숏: 펀딩비가 음수이고 절댓값이 설정 임계값보다 크면 불리한 것으로 본다.

## Verification

```text
python -m unittest discover -s tests
Ran 7 tests
OK
```

```text
python main.py live --help
--symbols, --interval, --preset 옵션 확인 완료
```

실제 live 실행, 실제 주문, `DRY_RUN=false` 변경은 하지 않았다.
