"""
매매 엔진 모듈 (v1.1)
종가 베팅 전략을 실행하고 포트폴리오를 관리합니다.
"""
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from api import KISApi
from strategy.screener import StockScreener
from strategy.technical import TechnicalAnalyzer
from strategy.intraday_analysis import IntradayAnalyzer
from strategy.morning_monitor import MorningMonitor, ExitScenario
from strategy.kelly_criterion import KellyCriterion
from command_center.command_center import CommandCenter
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진 (v1.1)"""

    def __init__(self, api: KISApi):
        self.api = api
        self.screener = StockScreener(api)
        self.technical_analyzer = TechnicalAnalyzer(api)
        self.intraday_analyzer = IntradayAnalyzer(api)
        self.morning_monitor = MorningMonitor(api)
        self.kelly = KellyCriterion()
        self.command_center = CommandCenter(api)

        self.portfolio_file = Path("/home/ubuntu/gpt/data/portfolio.json")
        self.portfolio = self._load_portfolio()

    def _load_portfolio(self) -> Dict:
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"holdings": [], "buy_date": None}

    def _save_portfolio(self):
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.portfolio, f, ensure_ascii=False, indent=2)

    def run_closing_strategy(self):
        """종가 베팅 전략 실행 (14:30 ~ 15:20)"""
        logger.info("🚀 종가 베팅 전략 실행 시작")
        
        # 1. PHASE 1: 유니버스 필터
        candidates = self.screener.get_candidates()
        if not candidates:
            return

        # 2. PHASE 2: 기술적 검증
        tech_passed = self.technical_analyzer.analyze_candidates(candidates)
        if not tech_passed:
            return

        # 3. PHASE 3: 심리적 검증 (Analyst/Explorer 역할 - 여기서는 간소화)
        # 4. PHASE 4: V자 반등 감지 및 최종 결정
        final_candidates = []
        for stock in tech_passed:
            # 실시간 데이터 수집
            realtime_data = self.intraday_analyzer.get_realtime_data(stock['stock_code'])
            is_v_passed, v_score = self.intraday_analyzer.phase3_v_pattern(stock['stock_code'], realtime_data)
            
            if is_v_passed:
                stock['phase3_score'] = v_score
                final_candidates.append(stock)

        if not final_candidates:
            logger.info("⚠️ V자 반등 조건 충족 종목 없음")
            return

        # 5. Commander 최종 의사결정
        decisions = self.command_center.get_commander_decision(
            final_candidates, 
            market_condition={}, 
            account_info=self.api.get_balance()
        )

        # 6. 주문 실행
        for decision in decisions:
            if decision['action'] == "BUY":
                # 포지션 사이징
                balance = self.api.get_balance()['cash']
                pos_size = self.kelly.get_position_size(balance, stock['current_price'])
                
                if pos_size['quantity'] > 0:
                    self.api.place_order(decision['symbol'], pos_size['quantity'], 0, "buy")
                    logger.info(f"🛒 {decision['name']} 매수 주문 완료: {pos_size['quantity']}주")

    def run_morning_strategy(self):
        """익일 오전 청산 전략 실행 (09:00 ~ 10:00)"""
        if not self.portfolio['holdings']:
            return

        logger.info("🚀 오전 청산 전략 실행 시작")
        for holding in self.portfolio['holdings']:
            # 시나리오 판단 및 실행
            # (실제 구현에서는 실시간 시세와 코스피 지수 등을 지속적으로 모니터링)
            pass
