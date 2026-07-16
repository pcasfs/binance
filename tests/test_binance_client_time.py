from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs

import requests

from trader.binance_client import BinanceFuturesClient, DEFAULT_RECV_WINDOW_MS


class FakeResponse:
    def __init__(self, status_code: int, payload: object, reason: str = "OK") -> None:
        self.status_code = status_code
        self._payload = payload
        self.reason = reason
        self.text = str(payload)

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, params: object = None, timeout: int = 10) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


class BinanceClientTimeTest(TestCase):
    def test_signed_request_uses_binance_server_time_offset(self) -> None:
        session = FakeSession(
            [
                FakeResponse(200, {"serverTime": 1001005}),
                FakeResponse(200, {"ok": True}),
            ]
        )
        client = BinanceFuturesClient("key", "secret", testnet=True)
        client.session = session

        with patch("trader.binance_client.time.time", side_effect=[1000.000, 1000.010, 1000.020]):
            result = client._signed_request("GET", "/fapi/v2/positionRisk", {"symbol": "BTCUSDT"})

        signed_params = parse_qs(str(session.calls[1]["params"]))
        self.assertEqual(result, {"ok": True})
        self.assertEqual(signed_params["timestamp"], ["1001020"])
        self.assertEqual(signed_params["recvWindow"], [str(DEFAULT_RECV_WINDOW_MS)])

    def test_timestamp_error_resyncs_and_retries_once(self) -> None:
        session = FakeSession(
            [
                FakeResponse(400, {"code": -1021, "msg": "Timestamp for this request is outside of the recvWindow."}, "Bad Request"),
                FakeResponse(200, {"serverTime": 1005150}),
                FakeResponse(200, {"ok": True}),
            ]
        )
        client = BinanceFuturesClient("key", "secret", testnet=True)
        client.session = session
        client._server_time_synced = True

        with patch("trader.binance_client.time.time", side_effect=[1000.000, 1000.100, 1000.200, 1000.300]):
            result = client._signed_request("GET", "/fapi/v2/positionRisk", {"symbol": "BTCUSDT"})

        first_signed_params = parse_qs(str(session.calls[0]["params"]))
        retry_signed_params = parse_qs(str(session.calls[2]["params"]))
        self.assertEqual(result, {"ok": True})
        self.assertEqual(first_signed_params["timestamp"], ["1000000"])
        self.assertEqual(retry_signed_params["timestamp"], ["1005300"])
        self.assertEqual(len(session.calls), 3)

    def test_get_order_uses_signed_order_endpoint(self) -> None:
        session = FakeSession([FakeResponse(200, {"orderId": 123, "status": "FILLED"})])
        client = BinanceFuturesClient("key", "secret", testnet=True)
        client.session = session
        client._server_time_synced = True

        with patch("trader.binance_client.time.time", return_value=1000.000):
            result = client.get_order("SOLUSDT", 123)

        params = parse_qs(str(session.calls[0]["params"]))
        self.assertEqual(result, {"orderId": 123, "status": "FILLED"})
        self.assertTrue(str(session.calls[0]["url"]).endswith("/fapi/v1/order"))
        self.assertEqual(params["symbol"], ["SOLUSDT"])
        self.assertEqual(params["orderId"], ["123"])
