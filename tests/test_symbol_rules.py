from decimal import Decimal
from unittest import TestCase

from trader.symbol_rules import SymbolRules, format_decimal, parse_symbol_rules, plan_order_quantity


class SymbolRulesTest(TestCase):
    def test_parses_market_lot_size_and_min_notional(self) -> None:
        info = {
            "symbol": "BTCUSDT",
            "filters": [
                {"filterType": "MARKET_LOT_SIZE", "minQty": "0.001", "maxQty": "100", "stepSize": "0.001"},
                {"filterType": "MIN_NOTIONAL", "notional": "5"},
            ],
        }

        rules = parse_symbol_rules(info)

        self.assertEqual(rules.min_qty, Decimal("0.001"))
        self.assertEqual(rules.step_size, Decimal("0.001"))
        self.assertEqual(rules.min_notional, Decimal("5"))

    def test_rounds_quantity_down_to_step_size(self) -> None:
        rules = SymbolRules("BTCUSDT", Decimal("0.001"), Decimal("100"), Decimal("0.001"), Decimal("5"))

        plan = plan_order_quantity(Decimal("20"), Decimal("63123.45"), rules)

        self.assertEqual(plan.quantity, Decimal("0.000"))
        self.assertFalse(plan.is_valid)

    def test_accepts_integer_step_altcoin_quantity(self) -> None:
        rules = SymbolRules("DOGEUSDT", Decimal("1"), Decimal("10000000"), Decimal("1"), Decimal("5"))

        plan = plan_order_quantity(Decimal("20"), Decimal("0.1234"), rules)

        self.assertEqual(plan.quantity, Decimal("162"))
        self.assertTrue(plan.is_valid)
        self.assertEqual(format_decimal(plan.quantity), "162")
