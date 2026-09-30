from __future__ import annotations

import argparse
from dataclasses import replace

from trader.backtest import Backtester
from trader.bot import TradingBot
from trader.config import Settings
from trader.data_loader import download_to_csv
from trader.log_archive import LogArchiveConfig, upload_analysis_pack
from trader.optimize import Optimizer
from trader.portfolio import download_many, parse_symbols, portfolio_backtest
from trader.preflight import PreflightChecker
from trader.presets import apply_symbol_preset, preset_names
from trader.runtime_config import load_runtime_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance long/short trading toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    dl = sub.add_parser("download", help="Download historical candles to CSV")
    dl.add_argument("--symbol", default=None)
    dl.add_argument("--interval", default=None)
    dl.add_argument("--days", type=int, default=30)

    dl_many = sub.add_parser("download-many", help="Download historical candles for several symbols")
    dl_many.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to major USDT futures symbols.")
    dl_many.add_argument("--interval", default=None)
    dl_many.add_argument("--days", type=int, default=365)

    bt = sub.add_parser("backtest", help="Run CSV-based backtest")
    bt.add_argument("--symbol", default=None)
    bt.add_argument("--interval", default=None)
    bt.add_argument("--side", choices=["both", "long", "short"], default="both")
    bt.add_argument("--start", default=None, help="UTC start time, for example 2026-03-30 or 2026-03-30T00:00")
    bt.add_argument("--end", default=None, help="UTC end time, for example 2026-07-05 or 2026-07-05T12:00")
    bt.add_argument("--log-trades", action="store_true", help="Print each entry and exit like the Upbit backtest")
    bt.add_argument(
        "--preset",
        choices=preset_names(),
        default="default",
        help="Use saved parameter presets without typing environment variables",
    )

    opt = sub.add_parser("optimize", help="Search robust HA/Stoch parameters without fitting one period too tightly")
    opt.add_argument("--symbol", default=None)
    opt.add_argument("--interval", default=None)
    opt.add_argument("--side", choices=["both", "long", "short"], default="long")
    opt.add_argument("--start", default=None, help="UTC start time, for example 2026-03-30 or 2026-03-30T00:00")
    opt.add_argument("--end", default=None, help="UTC end time, for example 2026-07-05 or 2026-07-05T12:00")
    opt.add_argument("--folds", type=int, default=3)
    opt.add_argument("--top", type=int, default=10)
    opt.add_argument("--grid", choices=["focused", "wide"], default="focused")

    pf = sub.add_parser("portfolio", help="Backtest the same strategy across multiple symbols")
    pf.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to major USDT futures symbols.")
    pf.add_argument("--interval", default=None)
    pf.add_argument("--side", choices=["both", "long", "short"], default="both")
    pf.add_argument("--start", default=None)
    pf.add_argument("--end", default=None)
    pf.add_argument("--preset", choices=preset_names(), default="default")

    live = sub.add_parser("live", help="Run live REST polling bot")
    live.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to SYMBOL from .env.")
    live.add_argument("--interval", default=None)
    live.add_argument("--preset", choices=preset_names(), default="default")

    preflight = sub.add_parser("preflight", help="Check live-trading readiness without placing orders")
    preflight.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to SYMBOL from .env.")
    preflight.add_argument("--interval", default=None)
    preflight.add_argument("--preset", choices=preset_names(), default="default")

    upload_logs = sub.add_parser("upload-logs", help="Build the analysis log pack and upload it to private S3")
    upload_logs.add_argument("--bucket", default=None, help="Override log_archive.bucket from config/live.yaml")
    upload_logs.add_argument("--prefix", default=None, help="Override the S3 object prefix")

    args = parser.parse_args()

    if args.command == "upload-logs":
        try:
            runtime_config = load_runtime_config()
            archive_config = LogArchiveConfig.from_runtime_config(runtime_config)
            if args.bucket is not None:
                archive_config = replace(archive_config, bucket=args.bucket.strip())
            if args.prefix is not None:
                archive_config = replace(archive_config, prefix=args.prefix.strip("/"))
            settings_config = runtime_config["settings"]
            pack_path, object_key = upload_analysis_pack(
                archive_config,
                live_order_path=str(settings_config["live_order_log_path"]),
                event_path=str(settings_config["event_log_path"]),
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        size_mb = pack_path.stat().st_size / (1024 * 1024)
        print(f"Analysis pack: {pack_path} ({size_mb:.2f} MiB)")
        print(f"Uploaded: s3://{archive_config.bucket}/{object_key}")
        return

    settings = Settings.from_env()

    if args.command == "download":
        download_to_csv(settings, args.symbol or settings.symbol, args.interval or settings.interval, args.days)
    elif args.command == "download-many":
        download_many(settings, parse_symbols(args.symbols), args.interval or settings.interval, args.days)
    elif args.command == "backtest":
        symbol = args.symbol or settings.symbol
        interval = args.interval or settings.interval
        settings = apply_symbol_preset(settings, args.preset, symbol, interval)
        Backtester(
            settings,
            symbol,
            interval,
            side=args.side,
            start=args.start,
            end=args.end,
            log_trades=args.log_trades,
        ).run()
    elif args.command == "optimize":
        Optimizer(
            settings,
            args.symbol or settings.symbol,
            args.interval or settings.interval,
            side=args.side,
            start=args.start,
            end=args.end,
            folds=args.folds,
            top=args.top,
            grid=args.grid,
        ).run()
    elif args.command == "portfolio":
        portfolio_backtest(
            settings,
            parse_symbols(args.symbols),
            args.interval or settings.interval,
            side=args.side,
            start=args.start,
            end=args.end,
            preset=args.preset,
        )
    elif args.command == "live":
        symbols = parse_symbols(args.symbols) if args.symbols else [settings.symbol]
        TradingBot(settings, symbols=symbols, interval=args.interval or settings.interval, preset=args.preset).run_forever()
    elif args.command == "preflight":
        symbols = parse_symbols(args.symbols) if args.symbols else [settings.symbol]
        ok = PreflightChecker(settings, symbols=symbols, interval=args.interval or settings.interval, preset=args.preset).run()
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
