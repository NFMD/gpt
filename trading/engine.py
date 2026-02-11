"""
매매 엔진 모듈 (v2.0)
종가 베팅 5단계 전략 파이프라인을 실행하고 포트폴리오를 관리합니다.

v2.0 변경사항:
- 5단계 파이프라인 명시적 구현
  PHASE 1: 유니버스 필터 (수천→~50)
  PHASE 2: 기술적 검증 (~50→~10)
  PHASE 3: 심리적 검증 (~10→~5, VETO 포함)
  PHASE 4: V자 반등 + 앙상블 진입 (~5→매수)
  PHASE 5: 익일 청산 (시나리오별 분할매도)
- 거시 환경 필터(MarketRegime) 통합
- calculate_logic_scores 기반 4로직 앙상블
- determine_entry_weight 기반 포지션 사이징
- 장후 리스크 관리 (after_hours_risk_check)
- SQLite DB 기반 매매 기록
"""
import logging
import json
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path
from api import KISApi
from strategy.screener import StockScreener
from strategy.technical import TechnicalAnalyzer
from strategy.intraday_analysis import (
    IntradayAnalyzer, calculate_logic_scores, determine_entry_weight,
)
from strategy.morning_monitor import (
    MorningMonitor, ExitScenario,
    determine_exit_scenario, execute_exit, after_hours_risk_check,
)
from strategy.sentiment import SentimentData, phase3_score, find_power_keywords
from strategy.kelly_criterion import KellyCriterion
from strategy.macro_filter import MacroFilter, MarketRegime
from strategy.ensemble import EnsembleScorer
from strategy.veto import VetoScanner
from command_center.command_center import CommandCenter
from data.database import TradingDatabase
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진 (v2.0) — 5단계 전략 파이프라인"""

    def __init__(self, api: KISApi):
        self.api = api

        # PHASE별 분석기
        self.screener = StockScreener(api)              # PHASE 1
        self.technical_analyzer = TechnicalAnalyzer(api)  # PHASE 2
        self.veto_scanner = VetoScanner()                # PHASE 3 VETO
        self.intraday_analyzer = IntradayAnalyzer(api)   # PHASE 4
        self.morning_monitor = MorningMonitor(api)       # PHASE 5

        # 공통 모듈
        self.kelly = KellyCriterion()
        self.ensemble_scorer = EnsembleScorer()
        self.macro_filter = MacroFilter()
        self.command_center = CommandCenter(api)
        self.db = TradingDatabase()

        # 포트폴리오
        self.portfolio_file = Path(__file__).parent.parent / "data" / "portfolio.json"
        self.portfolio = self._load_portfolio()

        logger.info("TradingEngine (v2.0) 초기화 완료 — 5단계 파이프라인")

    def _load_portfolio(self) -> Dict:
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"holdings": [], "buy_date": None}

    def _save_portfolio(self):
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.portfolio, f, ensure_ascii=False, indent=2)

    # ═══════════════════════════════════════════════════════
    # 종가 베팅 전략 (PHASE 1~4)
    # ═══════════════════════════════════════════════════════

    def run_closing_strategy(self, market_condition: Optional[Dict] = None):
        """
        종가 베팅 5단계 전략 실행 (14:00~15:20)

        0. 거시 환경 필터 (DANGER = 전면 중단)
        1. PHASE 1: 유니버스 필터 → ~50개
        2. PHASE 2: 기술적 검증 → ~10개
        3. PHASE 3: 심리적 검증 + VETO → ~5개
        4. PHASE 4: V자 반등 감지 + 앙상블 진입
        """
        logger.info("=" * 60)
        logger.info("[ENGINE] 종가 베팅 5단계 파이프라인 시작 (v2.0)")
        logger.info("=" * 60)

        mc = market_condition or {}

        # ═══ 0. 거시 환경 필터 ═══
        regime = self.macro_filter.update(
            kospi_change=mc.get("kospi_change", 0),
            kosdaq_change=mc.get("kosdaq_change", 0),
            us_futures_change=mc.get("us_futures", 0),
            vix=mc.get("vix", 15),
        )

        if regime == MarketRegime.DANGER:
            logger.warning("[ENGINE] DANGER 레짐 — 종가 베팅 전면 중단")
            return

        # ═══ PHASE 1: 유니버스 필터 ═══
        logger.info("[ENGINE] PHASE 1: 유니버스 필터")
        candidates = self.screener.get_candidates()
        if not candidates:
            logger.info("[ENGINE] PHASE 1 통과 종목 없음 — 종료")
            return

        # ═══ PHASE 2: 기술적 검증 ═══
        logger.info("[ENGINE] PHASE 2: 기술적 검증")
        tech_passed = self.technical_analyzer.analyze_candidates(candidates)
        if not tech_passed:
            logger.info("[ENGINE] PHASE 2 통과 종목 없음 — 종료")
            return

        # ═══ PHASE 3: 심리적 검증 + VETO ═══
        logger.info("[ENGINE] PHASE 3: 심리적 검증 + VETO")
        phase3_passed = []
        for stock in tech_passed:
            symbol = stock.get('stock_code', '')
            name = stock.get('stock_name', '')

            # VETO 스캔
            news_items = stock.get("news_items", [])
            veto_result = self.veto_scanner.scan_news_list(symbol, name, news_items)
            if veto_result.is_vetoed:
                logger.warning(f"[ENGINE] {name} VETO 발동 — 제외")
                continue

            # 심리적 점수 산출
            headlines = [item.get("title", "") for item in news_items]
            power_kws = find_power_keywords(headlines)

            sent_data = SentimentData(
                symbol=symbol,
                google_article_count=stock.get("google_news_count", 0),
                positive_ratio=stock.get("positive_ratio", 0.5),
                negative_ratio=stock.get("negative_ratio", 0.1),
                headlines=headlines,
                naver_top_10=stock.get("naver_top_exposure", False),
                forum_post_count=stock.get("forum_post_count", 0),
                theme_expected_days=stock.get("theme_expected_days", 0),
                power_keywords_found=power_kws,
            )

            passed, score, details = phase3_score(sent_data)
            stock['phase3_score'] = score
            stock['phase3_details'] = details
            stock['sentiment_data'] = sent_data

            if passed:
                phase3_passed.append(stock)
                logger.info(f"  [PASS] {name} | 심리점수={score}")

        if not phase3_passed:
            logger.info("[ENGINE] PHASE 3 통과 종목 없음 — 종료")
            return

        # 상위 5개로 축소 (PHASE 2+3 합산 점수 기준)
        phase3_passed.sort(
            key=lambda s: s.get('phase2_score', 0) + s.get('phase3_score', 0),
            reverse=True,
        )
        final_candidates = phase3_passed[:5]
        logger.info(f"[ENGINE] PHASE 3 최종 후보: {len(final_candidates)}개")

        # ═══ PHASE 4: V자 반등 + 앙상블 진입 ═══
        logger.info("[ENGINE] PHASE 4: V자 반등 + 앙상블 진입")
        account = self.api.get_balance()
        total_asset = account.get('total_asset', account.get('cash', 0))
        cash = account.get('cash', 0)
        current_cash_ratio = cash / total_asset if total_asset > 0 else 1.0
        position_count = len(self.portfolio.get('holdings', []))

        buy_orders = []

        for stock in final_candidates:
            symbol = stock.get('stock_code', '')
            name = stock.get('stock_name', '')

            # V자 반등 감지
            realtime_data = self.intraday_analyzer.get_realtime_data(symbol)
            is_v, v_score, v_details = self.intraday_analyzer.phase4_v_pattern(
                symbol, realtime_data
            )

            if not is_v:
                logger.info(f"  [SKIP] {name} — V자 미충족")
                continue

            # 장중 억눌림 여부
            open_price = realtime_data.get('open_price', stock.get('open_price', 0))
            current_price = realtime_data.get('current_price', stock.get('current_price', 0))
            intraday_return_negative = (
                (current_price - open_price) / open_price < 0
                if open_price > 0 else False
            )

            # 4가지 로직 점수 산출
            sent_data = stock.get('sentiment_data')
            logic_scores = calculate_logic_scores(
                change_pct=stock.get('change_rate', 0) / 100.0 if abs(stock.get('change_rate', 0)) > 1 else stock.get('change_rate', 0),
                phase2_score_val=stock.get('phase2_score', 0),
                v_score=v_score,
                program_net_buy_3min=realtime_data.get('program_net_buy_3min', 0),
                intraday_return_negative=intraday_return_negative,
                moc_buy_imbalance=realtime_data.get('moc_buy_imbalance', False),
                sell_order_qty=realtime_data.get('sell_order_qty', 0),
                buy_order_qty=realtime_data.get('buy_order_qty', 0),
                execution_strength=realtime_data.get('execution_strength', 0),
                google_article_count=sent_data.google_article_count if sent_data else 0,
                positive_ratio=sent_data.positive_ratio if sent_data else 0.5,
                power_keywords_found=sent_data.power_keywords_found if sent_data else [],
                theme_expected_days=sent_data.theme_expected_days if sent_data else 0,
            )

            ensemble_result = self.ensemble_scorer.score_with_logic_dict(
                symbol, name, logic_scores
            )

            if ensemble_result.entry_tier == "SKIP":
                logger.info(f"  [SKIP] {name} — 앙상블 {logic_scores['ensemble_score']}점 미달")
                continue

            # 진입 비중 결정
            kelly_pct = self.kelly.calculate_kelly_fraction()
            entry_weight = determine_entry_weight(
                ensemble_score=logic_scores['ensemble_score'],
                regime=regime.value,
                kelly_pct=kelly_pct,
                current_cash_ratio=current_cash_ratio,
                position_count=position_count,
            )

            if entry_weight <= 0:
                continue

            # 주문 수량 계산
            if current_price <= 0:
                continue
            investment = int(cash * entry_weight)
            quantity = investment // current_price
            if quantity <= 0:
                continue

            # 주문 실행
            success = self.api.place_order(symbol, quantity, 0, "buy")

            if success:
                logger.info(
                    f"[ENGINE] 매수: {name} {quantity}주 @ {current_price:,}원 | "
                    f"앙상블={logic_scores['ensemble_score']:.1f} | "
                    f"비중={entry_weight:.1%} | "
                    f"주도={logic_scores['dominant_logic']}"
                )

                # 포트폴리오 업데이트
                self.portfolio['holdings'].append({
                    "stock_code": symbol,
                    "stock_name": name,
                    "quantity": quantity,
                    "entry_price": current_price,
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "ensemble_score": logic_scores['ensemble_score'],
                    "entry_tier": ensemble_result.entry_tier,
                    "dominant_logic": logic_scores['dominant_logic'],
                    "phase2_score": stock.get('phase2_score', 0),
                    "phase3_score": stock.get('phase3_score', 0),
                    "v_score": v_score,
                })
                self.portfolio['buy_date'] = date.today().isoformat()
                self._save_portfolio()

                # DB 기록
                self.db.insert_trade({
                    "symbol": symbol,
                    "name": name,
                    "theme": stock.get('theme', ''),
                    "entry_date": date.today().isoformat(),
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "entry_price": current_price,
                    "quantity": quantity,
                    "weight_pct": round(entry_weight * 100, 1),
                    "exit_date": None, "exit_time": None, "exit_price": None,
                    "exit_scenario": None, "exit_reason": None,
                    "pnl": None, "pnl_percent": None,
                    "phase2_score": stock.get('phase2_score', 0),
                    "phase3_score": stock.get('phase3_score', 0),
                    "v_pattern_score": v_score,
                    "ensemble_score": logic_scores['ensemble_score'],
                    "logic1_tow_score": logic_scores['logic1_tow'],
                    "logic2_v_score": logic_scores['logic2_v'],
                    "logic3_moc_score": logic_scores['logic3_moc'],
                    "logic4_news_score": logic_scores['logic4_news'],
                    "ai_confidence": min(int(logic_scores['ensemble_score']), 100),
                    "notes": f"주도로직={logic_scores['dominant_logic']} 레짐={regime.value}",
                })

                position_count += 1
                cash -= investment
                current_cash_ratio = cash / total_asset if total_asset > 0 else 0

                buy_orders.append({
                    "symbol": symbol, "name": name,
                    "quantity": quantity, "price": current_price,
                    "ensemble": logic_scores['ensemble_score'],
                })

        if not buy_orders:
            logger.info("[ENGINE] PHASE 4 진입 조건 충족 종목 없음")
        else:
            logger.info(f"[ENGINE] 총 {len(buy_orders)}개 종목 매수 완료")

    # ═══════════════════════════════════════════════════════
    # 장후 리스크 관리
    # ═══════════════════════════════════════════════════════

    def run_after_hours_check(self):
        """장후 리스크 관리 (15:30~18:00)"""
        if not self.portfolio['holdings']:
            return

        logger.info("=" * 60)
        logger.info("[ENGINE] 장후 리스크 관리 시작")
        logger.info("=" * 60)

        for holding in self.portfolio['holdings']:
            symbol = holding['stock_code']
            name = holding['stock_name']
            qty = holding['quantity']

            after_data = self.api.get_realtime_analysis_data(symbol)
            result = after_hours_risk_check(
                symbol=symbol,
                sell_order_qty=after_data.get('sell_order_qty', 0),
                buy_order_qty=after_data.get('buy_order_qty', 0),
                after_hours_change=after_data.get('after_hours_change', 0),
                holding_qty=qty,
            )

            if result['action'] == 'PARTIAL_SELL' and result['sell_qty'] > 0:
                logger.info(f"[ENGINE] 장후 정리: {name} {result['sell_qty']}주 | {result['reason']}")

    # ═══════════════════════════════════════════════════════
    # 익일 오전 청산 (PHASE 5)
    # ═══════════════════════════════════════════════════════

    def run_morning_strategy(self):
        """
        익일 오전 청산 전략 실행 (08:30~10:00)

        시나리오 A~D + STOP + EMERGENCY 판단 후 분할/전량 청산
        10:00 = 무조건 전량 강제 청산
        """
        if not self.portfolio['holdings']:
            logger.info("[ENGINE] 보유 종목 없음 — 청산 불필요")
            return

        logger.info("=" * 60)
        logger.info("[ENGINE] PHASE 5: 오전 청산 전략 시작 (v2.0)")
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
            kospi_change = price_info.get('kospi_change', 0)
            ma20 = price_info.get('ma20', 0)
            high_since_open = price_info.get('high_since_open', current_price)

            # 시나리오 판단
            scenario, reason, sell_ratio = determine_exit_scenario(
                entry_price=entry_price,
                open_price=open_price,
                current_price=current_price,
                current_time=datetime.now(),
                kospi_change=kospi_change,
                ma20=ma20,
                high_since_open=high_since_open,
            )

            # 청산 실행
            exit_result = execute_exit(scenario, sell_ratio, quantity)

            if exit_result['action'] == 'SELL' and exit_result['sell_qty'] > 0:
                sell_qty = exit_result['sell_qty']
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

                    remaining = exit_result['remaining_qty']
                    if remaining <= 0:
                        holdings_to_remove.append(i)
                    else:
                        holding['quantity'] = remaining

        for idx in sorted(holdings_to_remove, reverse=True):
            self.portfolio['holdings'].pop(idx)
        self._save_portfolio()

    # ═══════════════════════════════════════════════════════
    # 유틸리티
    # ═══════════════════════════════════════════════════════

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

        macro = self.macro_filter.get_regime_summary()
        logger.info(f"  레짐={macro.get('regime', 'N/A')} | "
                     f"진입가능={macro.get('entry_allowed', 'N/A')}")
        logger.info("=" * 60)

    def execute_closing_bet(self):
        """종가 베팅 실행 (래퍼)"""
        self.run_closing_strategy()

    def execute_morning_sell(self):
        """오전 매도 실행 (래퍼)"""
        self.run_morning_strategy()
