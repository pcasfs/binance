from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any
from urllib.parse import urlencode

import requests

from trader.symbol_rules import SymbolRules, format_decimal, parse_symbol_rules

TESTNET_URL = "https://testnet.binancefuture.com"
MAINNET_URL = "https://fapi.binance.com"


class BinanceFuturesClient:
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True, timeout: int = 10) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = TESTNET_URL if testnet else MAINNET_URL
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-MBX-APIKEY": api_key})

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 150,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[list[Any]]:
        params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._request("GET", "/fapi/v1/klines", params)

    def mark_price(self, symbol: str) -> Decimal:
        data = self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})
        return Decimal(data["markPrice"])

    def funding_rate(self, symbol: str) -> Decimal:
        data = self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})
        return Decimal(data.get("lastFundingRate", "0"))

    def exchange_info(self) -> dict[str, Any]:
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def symbol_rules(self, symbol: str) -> SymbolRules:
        data = self.exchange_info()
        symbol = symbol.upper()
        for item in data.get("symbols", []):
            if item.get("symbol") == symbol:
                return parse_symbol_rules(item)
        raise ValueError(f"{symbol} was not found in Binance futures exchangeInfo.")

    def account_balance(self) -> list[dict[str, Any]]:
        return self._signed_request("GET", "/fapi/v2/balance")

    def positions(self, symbol: str) -> list[dict[str, Any]]:
        positions = self._signed_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
        return [item for item in positions if item["symbol"] == symbol]

    def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        return self._signed_request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})

    def set_margin_type(self, symbol: str, margin_type: str) -> dict[str, Any]:
        try:
            return self._signed_request("POST", "/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type})
        except requests.HTTPError as exc:
            if exc.response is not None and "-4046" in exc.response.text:
                return {"msg": "No need to change margin type."}
            raise

    def get_position_mode(self) -> dict[str, Any]:
        return self._signed_request("GET", "/fapi/v1/positionSide/dual")

    def set_position_mode(self, hedge_mode: bool) -> dict[str, Any]:
        return self._signed_request(
            "POST",
            "/fapi/v1/positionSide/dual",
            {"dualSidePosition": "true" if hedge_mode else "false"},
        )

    def market_order(self, symbol: str, side: str, quantity: Decimal, position_side: str) -> dict[str, Any]:
        return self._signed_request(
            "POST",
            "/fapi/v1/order",
            {"symbol": symbol, "side": side, "type": "MARKET", "quantity": format_decimal(quantity), "positionSide": position_side},
        )

    @staticmethod
    def round_down(value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.request(method, self.base_url + path, params=params, timeout=self.timeout)
        self._raise_for_status(response, path)
        return response.json()

    def _signed_request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise ValueError("API key is required for signed Binance requests.")
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload["recvWindow"] = 5000
        query = urlencode(payload)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        response = self.session.request(method, self.base_url + path, params=f"{query}&signature={signature}", timeout=self.timeout)
        self._raise_for_status(response, path)
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response, path: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:300]
            raise requests.HTTPError(f"{response.status_code} {response.reason} for {path}: {detail}") from exc
