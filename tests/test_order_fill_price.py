from __future__ import annotations

from decimal import Decimal
from unittest import TestCase

from trader.bot import TradingBot


class FakeOrderClient:
    def __init__(self, order_details: dict[str, object]) -> None:
        self.order_details = order_details
        self.calls: list[tuple[str, object]] = []

    def get_order(self, symbol: str, order_id: object) -> dict[str, object]:
        self.calls.append((symbol, order_id))
        return self.order_details


class OrderFillPriceTest(TestCase):
    def test_filled_price_uses_cum_quote_when_avg_price_is_zero(self) -> None:
        response = {"avgPrice": "0.00", "executedQty": "0.84", "cumQuote": "62.656440"}

        self.assertEqual(TradingBot._filled_price(response), Decimal("74.591"))

    def test_order_details_are_loaded_after_market_order(self) -> None:
        bot = TradingBot.__new__(TradingBot)
        bot.client = FakeOrderClient(
            {
                "orderId": 123,
                "status": "FILLED",
                "avgPrice": "74.5900",
                "executedQty": "0.84",
                "cumQuote": "62.6556",
            }
        )

        details = bot._order_details_after_market_order("SOLUSDT", {"orderId": 123, "status": "NEW", "avgPrice": "0.00"})

        self.assertEqual(details["status"], "FILLED")
        self.assertEqual(details["avgPrice"], "74.5900")
        self.assertEqual(bot.client.calls, [("SOLUSDT", 123)])
