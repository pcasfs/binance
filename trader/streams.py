from __future__ import annotations

import json
from typing import Callable

import websocket


def kline_stream_url(symbol: str, interval: str, testnet: bool) -> str:
    host = "wss://stream.binancefuture.com" if testnet else "wss://fstream.binance.com"
    return f"{host}/ws/{symbol.lower()}@kline_{interval}"


class KlineWebSocket:
    """Realtime candle stream. This is for live trading, not backtesting."""

    def __init__(self, symbol: str, interval: str, testnet: bool, on_closed_kline: Callable[[dict], None]) -> None:
        self.url = kline_stream_url(symbol, interval, testnet)
        self.on_closed_kline = on_closed_kline

    def run_forever(self) -> None:
        def on_message(_: websocket.WebSocketApp, message: str) -> None:
            data = json.loads(message)
            kline = data.get("k", {})
            if kline.get("x") is True:
                self.on_closed_kline(kline)

        app = websocket.WebSocketApp(self.url, on_message=on_message)
        app.run_forever()
