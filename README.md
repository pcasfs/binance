# Binance Long/Short Auto Trader

Binance USD-M Futures에서 롱/숏 자동매매를 개발하기 위한 Python 프로젝트입니다.

기본 흐름은 다음과 같습니다.

1. REST API로 과거 캔들 다운로드
2. CSV로 저장한 데이터로 백테스트
3. 같은 전략 코드를 테스트넷 드라이런 봇에서 사용
4. 충분히 검증한 뒤 테스트넷 주문, 마지막에만 실거래 검토

## 설치

```powershell
cd C:\binance
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env`의 기본값은 테스트넷과 드라이런입니다.

```env
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true
DRY_RUN=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

전략 옵션, 심볼별 최적값, 진입금액, 손실 제한 같은 운용 설정은 `.env`가 아니라 `config\live.yaml`에서 수정합니다. `.env`는 API 키와 실행 환경값만 보관합니다.

## 과거 데이터 다운로드

```powershell
python main.py download --symbol BTCUSDT --interval 1m --days 30
```

결과는 `data\BTCUSDT_1m.csv`에 저장됩니다.

## 전략

기본 전략은 `STRATEGY=heikin_ashi_stoch`입니다.

이 전략은 기존 Upbit 폴더의 Heikin-Ashi + StochRSI 로직을 Binance Futures용 롱/숏 전략으로 옮긴 것입니다.

- 롱: 종가가 SMA200 위, StochRSI 골든크로스, StochK 32 미만, Heikin-Ashi 양봉, 아래꼬리 거의 없음, ADX 20 초과
- 숏: 종가가 SMA200 아래, StochRSI 데드크로스, StochK 68 초과, Heikin-Ashi 음봉, 위꼬리 거의 없음, ADX 20 초과
- 기본 손절: 1.5%
- 기본 익절: 3.75%

기존 EMA 전략으로 돌리고 싶으면 `config\live.yaml`에서 `settings.strategy: ema_cross`로 바꾸면 됩니다.

## 백테스트

```powershell
python main.py backtest --symbol BTCUSDT --interval 1m
```

백테스트는 웹소켓이 아니라 REST로 받은 과거 캔들 CSV를 사용합니다. 수수료와 슬리피지를 반영합니다.

최적화된 롱/숏 후보값으로 바로 돌리려면:

```powershell
python main.py backtest --symbol BTCUSDT --interval 30m --preset optimized
```

롱 전용 최적 후보값으로 돌리려면:

```powershell
python main.py backtest --symbol BTCUSDT --interval 30m --side long --preset optimized-long
```

## 파라미터 최적화

```powershell
python main.py optimize --symbol BTCUSDT --interval 30m --side both --start 2026-03-30 --end 2026-07-05T12:00 --folds 3 --top 10 --grid focused
```

최적화는 원시 수익률만 보지 않고, 시간 구간을 나눈 fold별 안정성과 최대 낙폭을 함께 봅니다. 결과 요약은 `optimization_results.md`에 정리되어 있습니다.

## 여러 심볼 테스트

여러 심볼 데이터를 한 번에 받으려면:

```powershell
python main.py download-many --symbols BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT --interval 1h --days 365
```

같은 전략을 여러 심볼에 적용해 성과를 비교하려면:

```powershell
python main.py portfolio --symbols BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT --interval 1h --preset optimized --side both
```

심볼을 늘리면 거래 기회는 늘지만, 모든 심볼이 같은 전략에 잘 맞지는 않습니다. 심볼별 성과를 보고 제외할 대상을 정해야 합니다.

심볼별 1시간봉 최적값으로 BTC/ETH/SOL/DOGE를 테스트하려면:

```powershell
python main.py portfolio --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized --side both
```

## 실시간 드라이런

```powershell
python main.py live --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized
```

실시간 봇은 처음에는 REST 폴링으로 동작합니다. 웹소켓은 실시간 캔들 수신용으로 `trader/streams.py`에 분리해 두었고, 백테스트에는 사용하지 않습니다.

실거래 전 점검은 아래 명령으로 합니다. 이 명령은 주문을 넣지 않습니다.

```powershell
python main.py preflight --symbols BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT --interval 1h --preset symbol-optimized
```

## 운영 로그와 알림

텔레그램 알림을 쓰려면 `.env`에 아래 값을 넣습니다.

```env
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=텔레그램_채팅_ID
```

알림은 `HOLD`마다 보내지 않고, 봇 시작/종료, 실제 주문 진입, 청산, 주문 에러, tick 에러만 보냅니다.

분석용 이벤트 로그는 아래 파일에 누적됩니다.

```text
logs/events.csv
```

이 파일에는 신호 확인, 진입 차단, 포지션 점검, 손절/익절 트리거, 주문 성공/실패, tick 에러가 한 줄씩 저장됩니다. 진입 당시 StochRSI, ADX, Heikin-Ashi, SMA200 값과 포지션 보유 중 pnl, 손절가/익절가, 손절가까지 거리도 함께 남깁니다.

최근 로그를 확인하려면:

```bash
tail -n 100 logs/events.csv
```

### S3로 분석 로그 업로드

반복 다운로드를 위해 8000번 포트를 열지 않고 비공개 S3 버킷을 사용합니다. EC2에는 S3 버킷의 지정 경로에만 `s3:PutObject`를 허용하는 IAM 역할을 연결하고, AWS 액세스 키는 `.env`나 설정 파일에 저장하지 않습니다.

1. 서울 리전에 비공개 S3 버킷을 만들고 `모든 퍼블릭 액세스 차단`을 유지합니다.
2. 아래 정책에서 `BUCKET_NAME`을 실제 버킷 이름으로 바꿔 EC2용 IAM 역할에 연결합니다.
3. EC2 인스턴스의 `보안 > IAM 역할 수정`에서 이 역할을 연결합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:AbortMultipartUpload"
      ],
      "Resource": "arn:aws:s3:::BUCKET_NAME/binance-bot/logs/analysis_pack_full.txt"
    }
  ]
}
```

서버에 새 의존성을 설치합니다.

```bash
cd ~/binance
python3 -m pip install -r requirements.txt
```

`config/live.yaml`에 비공개 버킷 이름을 설정합니다.

```yaml
log_archive:
  bucket: my-private-binance-log-bucket
  prefix: binance-bot/logs
  pack_path: logs/analysis_pack_full.txt
  storage_class: STANDARD
```

서버에서 아래 명령을 실행하면 `live_orders.csv`와 `events.csv`를 하나의 분석 파일로 만들고 동일한 S3 객체 키에 덮어씁니다.

```bash
python3 main.py upload-logs
```

설정 파일을 바꾸지 않고 한 번만 실행할 수도 있습니다.

```bash
python3 main.py upload-logs --bucket my-private-binance-log-bucket
```

업로드 위치는 `s3://버킷이름/binance-bot/logs/analysis_pack_full.txt`입니다. 버킷 버전 관리를 켜면 이전 버전도 과금 대상이 될 수 있으므로, 최신 파일 하나만 유지하려면 버전 관리를 끄거나 수명 주기 규칙으로 이전 버전을 삭제합니다.

하루 요약 로그는 `config\live.yaml`의 설정을 따릅니다.

```yaml
settings:
  event_log_path: logs/events.csv
  daily_summary_dir: logs/daily
  daily_summary_retention_days: 90
```

요약 로그는 하루에 하나의 `daily_summary_YYYY-MM-DD.md` 파일로 갱신됩니다. 기본값은 최근 90일만 보관하므로 시간이 지나도 기록이 과하게 쌓이지 않습니다.

## 실거래 전 주의

- 출금 권한이 없는 API 키만 사용하세요.
- 처음에는 반드시 테스트넷과 드라이런으로 검증하세요.
- Hedge Mode에서 `LONG` / `SHORT` 포지션을 분리합니다.
- 포지션 모드 변경은 열린 주문이나 포지션이 있으면 실패할 수 있습니다.

이 코드는 투자 조언이 아니며 손실 가능성이 있습니다.
