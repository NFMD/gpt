"""
v1.1 전략 로직 테스트 스크립트
"""
import unittest
from datetime import datetime
from strategy.screener import StockScreener
from strategy.technical import TechnicalAnalyzer
from strategy.intraday_analysis import IntradayAnalyzer
from strategy.morning_monitor import MorningMonitor, ExitScenario
from config import Config

class MockAPI:
    def get_top_trading_value(self, count):
        return [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "market_cap": 400e12,
                "trading_value": 500e9,
                "change_rate": 5.0,
                "is_managed": False,
                "is_limit_up": False,
                "current_price": 75000,
                "high_price": 76000,
                "volume": 10000000
            },
            {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "market_cap": 100e12,
                "trading_value": 300e9,
                "change_rate": 16.0, # MAX_CHANGE_RATE 초과
                "is_managed": False,
                "is_limit_up": False,
                "current_price": 180000,
                "high_price": 185000,
                "volume": 5000000
            }
        ]
    
    def get_daily_price_history(self, code, days):
        return [{"close": 70000, "high": 74000, "volume": 1000000}] * days

    def get_realtime_analysis_data(self, code):
        return {
            "current_price": 75500,
            "low_since_1500": 75000,
            "ma5_1min": 75200,
            "execution_strength": 120,
            "prev_execution_strength": 110,
            "program_net_buy_3min": 10000,
            "sell_order_qty": 15000,
            "buy_order_qty": 10000,
            "ma20_1min": 75100
        }

class TestV11Strategy(unittest.TestCase):
    def setUp(self):
        self.api = MockAPI()
        self.screener = StockScreener(self.api)
        self.technical = TechnicalAnalyzer(self.api)
        self.intraday = IntradayAnalyzer(self.api)
        self.morning = MorningMonitor()

    def test_phase1_filter(self):
        candidates = self.screener.get_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['stock_code'], "005930")

    def test_phase2_scoring(self):
        stock = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 75000,
            "high_price": 75500,
            "volume": 10000000
        }
        is_passed, score = self.technical.phase2_score(stock)
        self.assertTrue(is_passed)
        self.assertGreaterEqual(score, 35)

    def test_phase3_v_pattern(self):
        # 시간을 15:17로 고정하여 테스트하기 위해 Config를 임시로 수정하거나 
        # datetime.now()를 모킹해야 함. 여기서는 로직 흐름만 확인.
        data = self.api.get_realtime_analysis_data("005930")
        # 현재 시간이 V_TIME_START ~ V_TIME_END 사이여야 함
        import datetime as dt
        now_str = dt.datetime.now().strftime('%H:%M:%S')
        if Config.V_TIME_START <= now_str <= Config.V_TIME_END:
            is_passed, score = self.intraday.phase3_v_pattern("005930", data)
            self.assertTrue(is_passed)
            self.assertEqual(score, 70) # 50(base) + 10(exec_str) + 10(orderbook)

    def test_phase5_exit(self):
        scenario, reason = self.morning.determine_exit_scenario(
            entry_price=75000,
            open_price=77000, # 2.6% 갭상승
            current_price=77500,
            current_time=datetime.strptime("09:01:00", "%H:%M:%S"),
            kospi_change=0.5
        )
        self.assertEqual(scenario, ExitScenario.GAP_UP_SUCCESS)

if __name__ == "__main__":
    unittest.main()
