"""
v2.0 시스템 통합 테스트 스크립트
"""
import unittest
from strategy.ensemble import EnsembleEngine
from strategy.risk_manager import StopLossEngine, MacroFilter, RiskLevel
from strategy.screener import StockScreener, CandidateTier
from command_center.command_center import CommandCenter

class MockAPI:
    def get_top_trading_value(self, count):
        return [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "market_cap": 400e12,
                "trading_value": 1.2e12, # Tier 1
                "change_rate": 5.0,
                "is_managed": False,
                "is_limit_up": False
            }
        ]
    def get_balance(self):
        return {"cash": 10000000}

class TestV20System(unittest.TestCase):
    def setUp(self):
        self.api = MockAPI()
        self.ensemble = EnsembleEngine()
        self.risk = StopLossEngine(total_asset=100000000)
        self.macro = MacroFilter()
        self.commander = CommandCenter(self.api)

    def test_ensemble_logic(self):
        data = {
            "current_price": 75000,
            "open_price": 76000, # intraday_ret < 0
            "change_rate": 3.0,  # daily_ret > 0.02
            "v_score": 80,
            "sell_order_qty": 20000,
            "buy_order_qty": 10000, # l3_moc score high
            "news_count": 25,
            "sentiment_score": 70
        }
        res = self.ensemble.get_ensemble_score(data)
        self.assertGreaterEqual(res['total_score'], 70)
        self.assertEqual(res['entry_grade'], "TOP_PRIORITY")

    def test_macro_filter(self):
        data = {"kospi_change": -1.5, "us_futures_change": -0.5, "vix": 20}
        res = self.macro.check_market_regime(data)
        self.assertEqual(res['level'], RiskLevel.CAUTION)
        self.assertEqual(res['multiplier'], 0.5)

    def test_screener_tier(self):
        screener = StockScreener(self.api)
        candidates = screener.get_candidates()
        self.assertEqual(candidates[0]['tier'], CandidateTier.TIER_1)

    def test_commander_decision(self):
        candidates = [{
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 75000,
            "open_price": 76000,
            "change_rate": 3.0,
            "v_score": 80,
            "sell_order_qty": 20000,
            "buy_order_qty": 10000,
            "news_count": 25,
            "sentiment_score": 70
        }]
        market_data = {"kospi_change": 0.0, "us_futures_change": 0.0, "vix": 15}
        decisions = self.commander.get_final_decision(candidates, market_data, {})
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]['grade'], "TOP_PRIORITY")

if __name__ == "__main__":
    unittest.main()
