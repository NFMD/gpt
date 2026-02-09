"""
매매 엔진 모듈 (v2.0)
종가 베팅 전략을 실행하고 포트폴리오를 관리합니다.

v2.0 변경사항:
- 4가지 수익원천 앙상블 프레임워크 통합
- 거시 환경 필터(MarketRegime) 통합
- VETO 시스템 통합
- SQLite DB 기반 매매 기록
- 포지션 사이징에 레짐 배수 반영
- 장후 잔량 모니터링 지원
"""
import logging
import json
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path
from api import KISApi
from strategy.screener import StockScreener
from strategy.technical import TechnicalAnalyzer
from strategy.intraday_analysis import IntradayAnalyzer
from strategy.morning_monitor import MorningMonitor, ExitScenario
from strategy.kelly_criterion import KellyCriterion
from strategy.macro_filter import MacroFilter, MarketRegime
from command_center.command_center import CommandCenter
from data.database import TradingDatabase
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api
        self.screener = StockScreener(api)
        self.technical_analyzer = TechnicalAnalyzer(api)
        self.intraday_analyzer = IntradayAnalyzer(api)
        self.morning_monitor = MorningMonitor(api)
        self.kelly = KellyCriterion()
        self.command_center = CommandCenter(api)
        self.macro_filter = self.command_center.macro_filter
        self.db = TradingDatabase()

        self.portfolio_file = Path(__file__).parent.parent / "data" / "portfolio.json"
        self.portfolio = self._load_portfolio()

        logger.info("TradingEngine (v2.0) 초기화 완료")

    def _load_portfolio(self) -> Dict:
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"holdings": [], "buy_date": None}

    def _save_portfolio(self):
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.portfolio, f, ensure_ascii=False, indent=2)

    def run_closing_strategy(self, market_condition: Optional[Dict] = None):
        """
        종가 베팅 전략 실행 (14:30 ~ 15:20) -- v2.0

        1. 거시 환경 필터 체크
        2. PHASE 1: 유니버스 필터
        3. PHASE 2: 기술적 검증
        4. PHASE 3/4: V자 반등 감지
        5. COMMANDER 앙상블 의사결정
        6. 주문 실행 + DB 기록
        """
        logger.info("=" * 60)
        logger.info("[ENGINE] 종가 베팅 전략 실행 시작 (v2.0)")
        logger.info("=" * 60)

        mc = market_condition or {}

        # 1. 거시 환경 필터
        regime = self.macro_filter.update(
            kospi_change=mc.get("kospi_change", 0),
            kosdaq_change=mc.get("kosdaq_change", 0),
            us_futures_change=mc.get("us_futures", 0),
            vix=mc.get("vix", 15),
        )

        if regime == MarketRegime.DANGER:
            logger.warning("[ENGINE] DANGER 레짐 - 종가 베팅 전면 중단")
            return

        # 2. PHASE 1: 유니버스 필터
        candidates = self.screener.get_candidates()
        if not candidates:
            logger.info("[ENGINE] PHASE 1 통과 종목 없음")
            return

        # 3. PHASE 2: 기술적 검증
        tech_passed = self.technical_analyzer.analyze_candidates(candidates)
        if not tech_passed:
            logger.info("[ENGINE] PHASE 2 통과 종목 없음")
            return

        # 4. PHASE 3/4: V자 반등 감지
        final_candidates = []
        for stock in tech_passed:
            realtime_data = self.intraday_analyzer.get_realtime_data(stock['stock_code'])
            is_v_passed, v_score = self.intraday_analyzer.phase3_v_pattern(
                stock['stock_code'], realtime_data
            )

            if is_v_passed:
                stock['phase3_score'] = v_score
                # V자 반등에서 수집한 실시간 데이터 병합
                stock.update({
                    'sell_order_qty': realtime_data.get('sell_order_qty', 0),
                    'buy_order_qty': realtime_data.get('buy_order_qty', 0),
                    'expected_close_price': realtime_data.get('expected_close_price', 0),
                    'price_at_1520': realtime_data.get('current_price', 0),
                    'buy_order_surge': realtime_data.get('buy_order_surge', False),
                    'expected_price_rising': realtime_data.get('expected_price_rising', False),
                    'open_price': realtime_data.get('open_price', 0),
                    'close_price_yesterday': realtime_data.get('close_price_yesterday', 0),
                    'current_price': realtime_data.get('current_price', stock.get('current_price', 0)),
                })
                final_candidates.append(stock)

        if not final_candidates:
            logger.info("[ENGINE] V자 반등 조건 충족 종목 없음")
            return

        # 5. COMMANDER 앙상블 의사결정
        account = self.api.get_balance()
        decisions = self.command_center.get_commander_decision(
            final_candidates,
            market_condition=mc,
            account_info=account,
        )

        # 6. 주문 실행 + DB 기록
        for decision in decisions:
            if decision['action'] != "BUY":
                continue

            symbol = decision['symbol']
            balance = account.get('cash', 0)

            # 포지션 사이징 (앙상블 배수 반영)
            kelly_fraction = self.kelly.calculate_kelly_fraction()
            adjusted_fraction = kelly_fraction * decision.get('position_multiplier', 1.0)
            adjusted_fraction = min(adjusted_fraction, Config.MAX_INVESTMENT_PER_STOCK_PCT)

            # 현재가 조회
            current_price = 0
            for s in final_candidates:
                if s.get('stock_code') == symbol:
                    current_price = s.get('current_price', 0)
                    break

            if current_price <= 0:
                continue

            investment = int(balance * adjusted_fraction)
            quantity = investment // current_price

            if quantity <= 0:
                continue

            # 주문 실행
            success = self.api.place_order(symbol, quantity, 0, "buy")

            if success:
                logger.info(
                    f"[ENGINE] 매수 완료: {decision['name']} "
                    f"{quantity}주 @ {current_price:,}원 | "
                    f"앙상블={decision['ensemble_score']:.1f}"
                )

                # 포트폴리오 업데이트
                self.portfolio['holdings'].append({
                    "stock_code": symbol,
                    "stock_name": decision['name'],
                    "quantity": quantity,
                    "entry_price": current_price,
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "ensemble_score": decision['ensemble_score'],
                    "entry_tier": decision['entry_tier'],
                    "dominant_logic": decision['dominant_logic'],
                })
                self.portfolio['buy_date'] = date.today().isoformat()
                self._save_portfolio()

                # DB 기록
                self.db.insert_trade({
                    "symbol": symbol,
                    "name": decision['name'],
                    "theme": "",
                    "entry_date": date.today().isoformat(),
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "entry_price": current_price,
                    "quantity": quantity,
                    "weight_pct": decision.get('weight_pct', 0),
                    "exit_date": None,
                    "exit_time": None,
                    "exit_price": None,
                    "exit_scenario": None,
                    "exit_reason": None,
                    "pnl": None,
                    "pnl_percent": None,
                    "phase2_score": None,
                    "phase3_score": None,
                    "v_pattern_score": None,
                    "ensemble_score": decision['ensemble_score'],
                    "logic1_tow_score": decision['logic_scores'].get('tug_of_war', 0),
                    "logic2_v_score": decision['logic_scores'].get('v_pattern', 0),
                    "logic3_moc_score": decision['logic_scores'].get('moc_imbalance', 0),
                    "logic4_news_score": decision['logic_scores'].get('news_temporal', 0),
                    "ai_confidence": decision['confidence'],
                    "notes": decision.get('reasoning', ''),
                })

    def run_morning_strategy(self):
        """
        익일 오전 청산 전략 실행 (09:00 ~ 10:00) -- v2.0

        시나리오 A~D + STOP + EMERGENCY 판단 후 청산
        """
        if not self.portfolio['holdings']:
            logger.info("[ENGINE] 보유 종목 없음 - 청산 불필요")
            return

        logger.info("=" * 60)
        logger.info("[ENGINE] 오전 청산 전략 실행 시작 (v2.0)")
        logger.info("=" * 60)

        holdings_to_remove = []

        for i, holding in enumerate(self.portfolio['holdings']):
            symbol = holding['stock_code']
            name = holding['stock_name']
            entry_price = holding['entry_price']
            quantity = holding['quantity']

            # 현재 시세 조회
            price_info = self.api.get_stock_price(symbol)
            if not price_info:
                continue

            current_price = price_info['current_price']
            open_price = price_info.get('open_price', current_price)

            # 시나리오 판단
            scenario, reason = self.morning_monitor.determine_exit_scenario(
                entry_price=entry_price,
                open_price=open_price,
                current_price=current_price,
                current_time=datetime.now(),
                kospi_change=0,
            )

            # 청산 실행
            exit_action = self.morning_monitor.execute_exit(scenario, quantity)

            if exit_action['action'] == 'SELL' and exit_action['qty'] > 0:
                sell_qty = exit_action['qty']
                success = self.api.place_order(symbol, sell_qty, 0, "sell")

                if success:
                    pnl = (current_price - entry_price) * sell_qty
                    pnl_pct = (current_price - entry_price) / entry_price * 100

                    logger.info(
                        f"[ENGINE] 청산: {name} {sell_qty}주 | "
                        f"시나리오={scenario.value} | "
                        f"수익={pnl:+,.0f}원({pnl_pct:+.2f}%) | "
                        f"사유={reason}"
                    )

                    if sell_qty >= quantity:
                        holdings_to_remove.append(i)

        # 청산된 종목 제거
        for idx in sorted(holdings_to_remove, reverse=True):
            self.portfolio['holdings'].pop(idx)
        self._save_portfolio()

    def scan_market(self):
        """시장 스캔 (정보 수집용)"""
        logger.info("[ENGINE] 시장 스캔 시작")
        candidates = self.screener.get_candidates()
        if candidates:
            self.technical_analyzer.analyze_candidates(candidates)

    def check_portfolio(self):
        """포트폴리오 상태 확인"""
        logger.info("=" * 60)
        logger.info("[ENGINE] 포트폴리오 상태")
        logger.info("=" * 60)

        if not self.portfolio['holdings']:
            logger.info("보유 종목 없음")
            return

        for h in self.portfolio['holdings']:
            logger.info(
                f"  {h['stock_name']}({h['stock_code']}) | "
                f"{h['quantity']}주 @ {h['entry_price']:,}원 | "
                f"앙상블={h.get('ensemble_score', 'N/A')}"
            )

        # 거시 상태 출력
        macro = self.command_center.get_macro_status()
        logger.info(f"  레짐={macro.get('regime', 'N/A')} | "
                     f"진입가능={macro.get('entry_allowed', 'N/A')}")
        logger.info("=" * 60)

    def execute_closing_bet(self):
        """종가 베팅 실행 (run_closing_strategy 래퍼)"""
        self.run_closing_strategy()

    def execute_morning_sell(self):
        """오전 매도 실행 (run_morning_strategy 래퍼)"""
        self.run_morning_strategy()
