from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from trader.binance_client import BinanceFuturesClient
from trader.config import Settings
from trader.presets import apply_symbol_preset
from trader.symbol_rules import format_decimal, plan_order_quantity


class PreflightChecker:
    def __init__(self, settings: Settings, symbols: list[str], interval: str, preset: str) -> None:
        self.base_settings = settings
        self.symbols = [symbol.upper() for symbol in symbols]
        self.interval = interval
        self.preset = preset
        self.client = BinanceFuturesClient(settings.api_key, settings.api_secret, settings.testnet)
        self.signed_checks_ok = False
        self.available_usdt: Decimal | None = None

    def run(self) -> bool:
        print("Preflight check")
        print(f"Testnet: {self.base_settings.testnet}")
        print(f"Dry run: {self.base_settings.dry_run}")
        print(f"Symbols: {','.join(self.symbols)}")
        print(f"Interval: {self.interval}")
        print(f"Preset: {self.preset}")
        print()

        signed_ok = self._signed_checks()
        self.signed_checks_ok = signed_ok
        public_ok = True
        for symbol in self.symbols:
            if not self._symbol_checks(symbol):
                public_ok = False
        ok = signed_ok and public_ok
        print()
        print("PREFLIGHT RESULT: OK" if ok else "PREFLIGHT RESULT: CHECK WARNINGS")
        return ok

    def _signed_checks(self) -> bool:
        if not self.base_settings.api_key or not self.base_settings.api_secret:
            print("[WARN] Signed checks skipped: API key/secret not configured.")
            return False

        ok = True
        try:
            balances = self.client.account_balance()
            usdt = next((item for item in balances if item.get("asset") == "USDT"), None)
            if usdt:
                self.available_usdt = Decimal(str(usdt.get("availableBalance", "0")))
                print(f"[OK] Futures balance reachable. USDT availableBalance={usdt.get('availableBalance')}")
            else:
                print("[WARN] Futures balance reachable, but USDT balance was not found.")
        except Exception as exc:
            print(f"[FAIL] Futures balance check failed: {safe_error(exc)}")
            ok = False

        try:
            mode = self.client.get_position_mode()
            hedge_mode = str(mode.get("dualSidePosition", "")).lower() == "true"
            label = "Hedge Mode" if hedge_mode else "One-way Mode"
            if hedge_mode:
                print(f"[OK] Position mode: {label}")
            else:
                print("[FAIL] Position mode: One-way Mode. Bot sends LONG/SHORT positionSide, so Hedge Mode is required.")
                ok = False
        except Exception as exc:
            print(f"[FAIL] Position mode check failed: {safe_error(exc)}")
            ok = False

        return ok

    def _symbol_checks(self, symbol: str) -> bool:
        ok = True
        print(f"\n[{symbol}]")
        try:
            settings = apply_symbol_preset(self.base_settings, self.preset, symbol, self.interval)
            print(
                "[OK] Settings "
                f"SL={settings.stop_loss_pct * 100:.2f}% TP={settings.take_profit_pct * 100:.2f}% "
                f"Stoch={settings.stoch_threshold_long:.0f}/{settings.stoch_threshold_short:.0f} "
                f"Wick={settings.wick_tolerance} ADX={settings.adx_threshold:.0f}"
            )
        except Exception as exc:
            print(f"[FAIL] Preset/settings check failed: {safe_error(exc)}")
            return False

        try:
            rules = self.client.symbol_rules(symbol)
            print(
                "[OK] Exchange rules "
                f"minQty={format_decimal(rules.min_qty)} stepSize={format_decimal(rules.step_size)} "
                f"minNotional={format_decimal(rules.min_notional)}"
            )
        except Exception as exc:
            print(f"[FAIL] Exchange rules check failed: {safe_error(exc)}")
            return False

        try:
            candles = self.client.get_klines(symbol, self.interval, limit=2)
            if len(candles) >= 2:
                print(f"[OK] Kline reachable for {self.interval}")
            else:
                print(f"[WARN] Kline returned only {len(candles)} rows.")
        except Exception as exc:
            print(f"[FAIL] Kline check failed: {safe_error(exc)}")
            ok = False

        try:
            mark_price = self.client.mark_price(symbol)
            quantity_plan = plan_order_quantity(Decimal(str(settings.usdt_per_trade)), mark_price, rules)
            status = "OK" if quantity_plan.is_valid else "FAIL"
            print(
                f"[{status}] Quantity "
                f"mark={mark_price} raw={format_decimal(quantity_plan.raw_quantity)} "
                f"rounded={format_decimal(quantity_plan.quantity)} notional={format_decimal(quantity_plan.notional)} "
                f"reason={quantity_plan.reason}"
            )
            if not quantity_plan.is_valid:
                ok = False
            elif self.available_usdt is not None and settings.leverage > 0:
                required_margin = quantity_plan.notional / Decimal(str(settings.leverage))
                if self.available_usdt < required_margin:
                    print(
                        "[FAIL] Balance may be insufficient for configured leverage. "
                        f"available={self.available_usdt} required_margin~={format_decimal(required_margin)}"
                    )
                    ok = False
        except Exception as exc:
            print(f"[FAIL] Quantity check failed: {safe_error(exc)}")
            ok = False

        try:
            funding_rate = self.client.funding_rate(symbol)
            threshold = Decimal(str(settings.max_abs_funding_rate))
            if threshold <= 0:
                print(f"[OK] Funding reachable. lastFundingRate={funding_rate} filter=disabled")
            elif abs(funding_rate) <= threshold:
                print(f"[OK] Funding reachable. lastFundingRate={funding_rate} threshold={threshold}")
            else:
                print(f"[WARN] Funding rate outside threshold. lastFundingRate={funding_rate} threshold={threshold}")
        except Exception as exc:
            print(f"[WARN] Funding check failed: {safe_error(exc)}")

        if self.signed_checks_ok:
            if not self._position_checks(symbol, settings):
                ok = False

        return ok

    def _position_checks(self, symbol: str, settings: Settings) -> bool:
        ok = True
        try:
            positions = self.client.positions(symbol)
        except Exception as exc:
            print(f"[FAIL] Position check failed: {safe_error(exc)}")
            return False

        open_positions = [item for item in positions if Decimal(str(item.get("positionAmt", "0"))) != 0]
        if open_positions:
            sides = ",".join(str(item.get("positionSide", "UNKNOWN")) for item in open_positions)
            print(f"[WARN] Existing open position detected: {sides}. Bot will block new entries for this symbol.")
        else:
            print("[OK] No open position detected.")

        if positions:
            if not self._compare_position_setting(positions, "leverage", str(settings.leverage), "leverage"):
                ok = False
            expected_margin = settings.margin_type.lower()
            margin_values = {str(item.get("marginType", "")).lower() for item in positions if item.get("marginType")}
            if margin_values and expected_margin not in margin_values:
                print(f"[FAIL] Margin type differs. expected={expected_margin} current={','.join(sorted(margin_values))}")
                ok = False
            elif margin_values:
                print(f"[OK] Margin type appears to be {expected_margin}")
            else:
                print("[WARN] Margin type could not be read from positionRisk.")

        return ok

    @staticmethod
    def _compare_position_setting(positions: list[dict[str, Any]], key: str, expected: str, label: str) -> bool:
        values = {str(item.get(key, "")) for item in positions if item.get(key) not in (None, "")}
        if not values:
            print(f"[WARN] {label} could not be read from positionRisk.")
            return True
        if expected not in values:
            print(f"[FAIL] {label} differs. expected={expected} current={','.join(sorted(values))}")
            return False
        print(f"[OK] {label} appears to be {expected}")
        return True


def safe_error(exc: Exception) -> str:
    message = str(exc)
    for token in ("signature", "timestamp", "recvWindow"):
        message = _redact_query_param(message, token)
    return message


def _redact_query_param(message: str, key: str) -> str:
    marker = f"{key}="
    if marker not in message:
        return message
    parts = message.split()
    return " ".join(_redact_url_part(part, key) for part in parts)


def _redact_url_part(value: str, key: str) -> str:
    if "://" not in value or f"{key}=" not in value:
        return value
    split = urlsplit(value)
    query = urlencode(
        [
            (param_key, "[redacted]" if param_key == key else param_value)
            for param_key, param_value in parse_qsl(split.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))
