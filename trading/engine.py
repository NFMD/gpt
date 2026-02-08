"""
매매 엔진 모듈 (v2.0)
5단계 전략 파이프라인 및 리스크 관리 엔진을 통합합니다.
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from api import KISApi
from strategy.screener import StockScreener
from strategy.technical import TechnicalAnalyzer
from strategy.sentiment import SentimentAnalyzer
from strategy.intraday_analysis import IntradayAnalyzer
from strategy.risk_manager import StopLossEngine, MacroFilter, AfterMarketManager
from strategy.kelly_criterion import KellyCriterion
from command_center.command_center import CommandCenter
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingEngine:
    """매매 엔진 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api
        self.screener = StockScreener(api)
        self.technical = TechnicalAnalyzer(api)
        self.sentiment = SentimentAnalyzer(api)
        self.intraday = IntradayAnalyzer(api)
        self.risk_manager = StopLossEngine(total_asset=100000000) # 예시 자산
        self.macro_filter = MacroFilter()
        self.after_market = AfterMarketManager()
        self.kelly = KellyCriterion()
        self.command_center = CommandCenter(api)

        self.portfolio_file = Path("/home/ubuntu/gpt/data/portfolio.json")
        self.portfolio = self._load_portfolio()

    def _load_portfolio(self):
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r') as f:
                return json.load(f)
        return {"holdings": []}

    def run_full_pipeline(self):
        """v2.0 5단계 전략 파이프라인 실행"""
        logger.info("🚀 v2.0 종가베팅 파이프라인 가동")
        
        # 1. PHASE 1: 유니버스 필터 (Tier 분류)
        candidates = self.screener.get_candidates()
        if not candidates: return

        # 2. PHASE 2: 기술적 검증 (SHOULD/BONUS)
        tech_passed = self.technical.analyze_candidates(candidates)
        if not tech_passed: return

        # 3. PHASE 3: 심리적 검증 (뉴스/감정)
        psych_passed = self.sentiment.analyze_psychology(tech_passed)
        if not psych_passed: return

        # 4. PHASE 4: V자 반등 및 앙상블 최종 결정
        final_candidates = []
        for stock in psych_passed:
            realtime_data = self.intraday.get_realtime_data(stock['stock_code'])
            is_v_passed, v_score = self.intraday.phase3_v_pattern(stock['stock_code'], realtime_data)
            if is_v_passed:
                stock['v_score'] = v_score
                stock.update(realtime_data) # 실시간 데이터(호가 등) 업데이트
                final_candidates.append(stock)

        if not final_candidates:
            logger.info("⚠️ 최종 진입 조건 충족 종목 없음")
            return

        # 거시 데이터 수집 (예시)
        market_data = {
            "kospi_change": 0.5,
            "us_futures_change": 0.2,
            "vix": 18.0
        }

        # Commander 최종 결정
        decisions = self.command_center.get_final_decision(
            final_candidates,
            market_data,
            self.api.get_balance()
        )

        # 5. 주문 실행 및 포지션 사이징
        for d in decisions:
            balance = self.api.get_balance()['cash']
            # 켈리 공식 + 거시 필터 가중치 적용
            pos = self.kelly.get_position_size(balance, d.get('price', 10000))
            qty = int(pos['quantity'] * d['multiplier'])
            
            if qty > 0:
                self.api.place_order(d['symbol'], qty, 0, "buy")
                logger.info(f"🛒 [v2.0] {d['name']} 매수 완료: {qty}주")

    def monitor_and_exit(self):
        """리스크 관리 및 청산 로직 실행"""
        if not self.portfolio['holdings']: return
        
        for holding in self.portfolio['holdings']:
            # 실시간 데이터 수집
            data = self.api.get_realtime_analysis_data(holding['stock_code'])
            data.update({
                "entry_price": holding['buy_price'],
                "kospi_change": 0.0, # 실제 데이터 필요
                "ma20": holding.get('ma20', 0)
            })
            
            # StopLossEngine 평가
            res = self.risk_manager.evaluate(data)
            if res['trigger']:
                logger.warning(f"🔔 {holding['stock_name']} 청산 트리거: {res['type']} ({res['reason']})")
                self.api.place_order(holding['stock_code'], holding['quantity'], 0, "sell")
