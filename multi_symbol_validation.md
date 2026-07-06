# Multi-Symbol Validation

검증 목적: BTC 단일 자동매매의 낮은 거래 빈도를 보완하기 위해 BTC/ETH/SOL/DOGE를 30m와 1h로 나누어 같은 하이키나시 + StochRSI + 200MA/ADX 구조에서 객관적으로 비교했다.

## Data

- 기준일: 2026-07-06
- 거래 방향: long/short both
- 최적화 방식: focused grid, 3 chronological folds, top 10
- 점수 방식: 단순 수익률 순위가 아니라 fold 안정성, MDD 페널티를 반영한 anti-overfit score
- BTC 데이터: 2025-07-05 UTC ~ 2026-07-05 UTC
- ETH/SOL/DOGE 데이터: 2025-07-06 UTC ~ 2026-07-06 UTC

## Commands Run

```powershell
python main.py optimize --symbol BTCUSDT --interval 30m --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol ETHUSDT --interval 30m --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol SOLUSDT --interval 30m --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol DOGEUSDT --interval 30m --side both --folds 3 --top 10 --grid focused

python main.py optimize --symbol BTCUSDT --interval 1h --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol ETHUSDT --interval 1h --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol SOLUSDT --interval 1h --side both --folds 3 --top 10 --grid focused
python main.py optimize --symbol DOGEUSDT --interval 1h --side both --folds 3 --top 10 --grid focused
```

## Summary Table

| Symbol | Interval | Rank | Return | MDD | Trades | Win% | PF | Stoch | Wick | ADX | SL% | TP% | RR | FoldReturns | 판단 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| BTCUSDT | 30m | 1 | 5.36% | 1.95% | 93 | 40.9% | 1.55 | 20 | 0.0020 | 20 | 2.00% | 4.50% | 2.25 | 3.22%, -0.81%, 3.15% | 보류 |
| ETHUSDT | 30m | 3 | 2.35% | 1.04% | 97 | 27.8% | 1.45 | 20 | 0.0018 | 25 | 1.00% | 3.75% | 3.75 | 1.51%, 0.17%, 0.78% | 보류 |
| SOLUSDT | 30m | 1 | 5.80% | 1.99% | 91 | 47.3% | 1.68 | 32 | 0.0005 | 20 | 2.00% | 3.75% | 1.88 | 2.27%, 0.50%, 2.65% | 후보 |
| DOGEUSDT | 30m | 1 | 5.31% | 1.70% | 87 | 41.4% | 1.59 | 20 | 0.0018 | 20 | 2.00% | 4.50% | 2.25 | 1.95%, 1.61%, 1.30% | 후보 |
| BTCUSDT | 1h | 1 | 5.23% | 0.98% | 89 | 30.3% | 1.96 | 32 | 0.0020 | 20 | 1.00% | 4.50% | 4.50 | 2.81%, 0.26%, 2.16% | 후보 |
| ETHUSDT | 1h | 2 | 2.26% | 0.99% | 54 | 44.4% | 1.60 | 32 | 0.0018 | 25 | 1.50% | 3.00% | 2.00 | 0.89%, 0.15%, 1.23% | 후보 |
| SOLUSDT | 1h | 1 | 7.48% | 0.63% | 65 | 64.6% | 2.74 | 35 | 0.0018 | 20 | 2.00% | 3.00% | 1.50 | 3.30%, 2.26%, 1.92% | 후보 |
| DOGEUSDT | 1h | 1 | 4.72% | 1.58% | 63 | 49.2% | 1.82 | 32 | 0.0020 | 20 | 2.00% | 3.75% | 1.88 | 1.33%, 2.26%, 1.12% | 후보 |

## Interpretation

### 유지 후보

- SOLUSDT 1h: 가장 강한 후보. 수익률, MDD, 승률, PF, 폴드 안정성이 모두 좋다.
- BTCUSDT 1h: 기존 BTC 단일 운용 후보로 계속 유지할 만하다. 거래 수가 충분하고 세 폴드가 모두 플러스다.
- DOGEUSDT 30m/1h: DOGE 추가는 객관적으로 괜찮다. 두 시간축 모두 세 폴드가 플러스이고 거래 수도 충분하다.
- SOLUSDT 30m: 1h보다는 거칠지만 거래 수 보완용 후보로 쓸 만하다.
- ETHUSDT 1h: 강한 후보는 아니지만 30m보다 구조가 낫다. 소액 또는 보조 후보로만 보는 편이 낫다.

### 보류

- BTCUSDT 30m: 전체 수익과 거래 수는 좋지만 두 번째 폴드가 -0.81%다. 30m BTC는 최근 1년 전체에서는 흔들림이 있어 바로 실전 후보로 올리기보다 추가 기간 검증이 필요하다.
- ETHUSDT 30m: 세 폴드는 플러스인 조합이 있지만 PF가 1.45로 약하고 승률도 낮다. 지금 단계에서는 ETH는 1h만 우선 검토하는 편이 낫다.

### 제외

- 이번 8개 대표 후보 중 즉시 완전 제외할 조합은 없다. 다만 실제 운용 후보에서는 BTC 30m, ETH 30m는 보류로 두고 시작하지 않는 편이 낫다.

## Practical Direction

1. 1차 운용 후보는 SOLUSDT 1h, BTCUSDT 1h, DOGEUSDT 1h로 잡는 것이 가장 객관적이다.
2. 거래 수가 부족하면 DOGEUSDT 30m와 SOLUSDT 30m를 보조로 추가한다.
3. ETHUSDT는 1h만 약한 후보로 유지하고, 30m는 당장 실전 후보에서 제외한다.
4. 심볼을 늘리는 방향은 타당하다. 필터를 억지로 완화해서 BTC 거래 수를 늘리는 것보다, 서로 다른 심볼에서 같은 전략이 통하는지 보는 쪽이 과적합 위험이 낮다.

## Next Risk-Management Features

- 심볼별 최대 동시 포지션 수 제한
- 전체 계좌 기준 총 노출 한도
- 하루 손실 한도 도달 시 신규 진입 중단
- 연속 손실 후 쿨다운
- 펀딩비가 불리할 때 신규 진입 제한
- 실전 전용 dry-run 로그와 실제 주문 로그 분리
- 30m/1h 동시 신호가 같은 방향일 때만 진입하는 상위 시간축 필터 테스트

