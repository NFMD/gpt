"""
매매 엔진 모듈 (v2.0 — Part 3 통합)
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

Part 3 통합:
- StopLossEngine: 5단계 우선순위 손절 자동화
- BrainTradeGuard: 뇌동매매 방지 (시간/횟수/연패/손실한도)
- DiscordAlert: 6채널 알림 시스템
- DailyReportGenerator: 일일 리포트 + KPI 추적
- US Market Correlation: 미국 증시 상관관계 체크
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
from risk.stop_loss import StopLossEngine
from risk.brain_trade_guard import BrainTradeGuard, is_action_allowed
from risk.us_market import check_us_market_correlation, assess_overnight_risk
from alerts.discord_alert import DiscordAlert
from alerts.daily_report import DailyReportGenerator
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진 (v2.0 — Part 3 통합) — 5단계 전략 파이프라인 + 리스크 관리 5대 영역"""

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

        # Part 3: 리스크 관리 모듈
        self.stop_loss_engine = None  # 총자산 확인 후 초기화
        self.guard = BrainTradeGuard()
        self.discord = DiscordAlert()
        self.report_generator = DailyReportGenerator(self.db)

        # 포트폴리오
        self.portfolio_file = Path(__file__).parent.parent / "data" / "portfolio.json"
        self.portfolio = self._load_portfolio()

        # 일일 거래 기록 (리포트용)
        self.today_trades: List[Dict] = []

        logger.info("TradingEngine (v2.0 Part 3) 초기화 완료 — 5단계 파이프라인 + 리스크 5대 영역")

    def _load_portfolio(self) -> Dict:
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"holdings": [], "buy_date": None}

    def _save_portfolio(self):
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.portfolio, f, ensure_ascii=False, indent=2)

    def _init_stop_loss_engine(self, total_asset: float):
        """StopLossEngine 초기화 (총자산 기반)"""
        self.stop_loss_engine = StopLossEngine(total_asset)

    # ═══════════════════════════════════════════════════════
    # 종가 베팅 전략 (PHASE 1~4)
    # ═══════════════════════════════════════════════════════

    def run_closing_strategy(self, market_condition: Optional[Dict] = None):
        """
        종가 베팅 5단계 전략 실행 (14:00~15:20)

        0. 거시 환경 필터 (DANGER = 전면 중단)
        0.5 뇌동매매 가드 체크
        1. PHASE 1: 유니버스 필터 → ~50개
        2. PHASE 2: 기술적 검증 → ~10개
        3. PHASE 3: 심리적 검증 + VETO → ~5개
        4. PHASE 4: V자 반등 감지 + 앙상블 진입
        """
        logger.info("=" * 60)
        logger.info("[ENGINE] 종가 베팅 5단계 파이프라인 시작 (v2.0 Part 3)")
        logger.info("=" * 60)

        mc = market_condition or {}
        current_time = datetime.now().strftime("%H:%M")

        # ═══ 0. 거시 환경 필터 ═══
        regime = self.macro_filter.update(
            kospi_change=mc.get("kospi_change", 0),
            kosdaq_change=mc.get("kosdaq_change", 0),
            us_futures_change=mc.get("us_futures", 0),
            vix=mc.get("vix", 15),
        )

        # 미국 증시 상관관계 체크
        us_check = check_us_market_correlation(
            us_futures_change=mc.get("us_futures", 0),
            us_close_change=mc.get("us_close_change", 0),
            vix=mc.get("vix", 15),
        )

        if regime == MarketRegime.DANGER:
            logger.warning("[ENGINE] DANGER 레짐 — 종가 베팅 전면 중단")
            self.discord.send_regime_change_alert({
                "prev_regime": "N/A", "new_regime": "DANGER",
                "kospi_change": mc.get("kospi_change", 0),
                "us_futures": mc.get("us_futures", 0),
                "vix": mc.get("vix", 0),
            })
            return

        # ═══ 0.5 뇌동매매 가드 체크 ═══
        can_enter, guard_reason = self.guard.can_enter(current_time)
        if not can_enter:
            logger.warning(f"[ENGINE] 가드 차단: {guard_reason}")
            self.discord.send_guard_alert({
                "reason": guard_reason,
                "status": str(self.guard.get_status()),
            })
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
                self.discord.send_veto_alert({
                    "symbol": symbol, "name": name,
                    "keyword": veto_result.triggered_keyword if hasattr(veto_result, 'triggered_keyword') else "",
                    "category": veto_result.risk_type if hasattr(veto_result, 'risk_type') else "",
                    "source": "PHASE 3 VETO 스캔",
                })
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

        # StopLossEngine 초기화
        self._init_stop_loss_engine(total_asset)

        buy_orders = []

        for stock in final_candidates:
            symbol = stock.get('stock_code', '')
            name = stock.get('stock_name', '')

            # 가드 재체크 (진입 횟수 초과 가능)
            can_enter, guard_reason = self.guard.can_enter(
                datetime.now().strftime("%H:%M")
            )
            if not can_enter:
                logger.info(f"  [GUARD] {name} 진입 차단: {guard_reason}")
                break

            # V자 반등 감지
            realtime_data = self.intraday_analyzer.get_realtime_data(symbol)
            is_v, v_score, v_details = self.intraday_analyzer.phase4_v_pattern(
                symbol, realtime_data
            )

            if not is_v:
                logger.info(f"  [SKIP] {name} — V자 미충족")
                continue

            # V자 감지 Discord 알림
            self.discord.send_v_pattern_alert({
                "symbol": symbol, "name": name,
                "price": realtime_data.get('current_price', 0),
                "change_pct": stock.get('change_rate', 0),
                "v_score": v_score,
                "rebound_pct": v_details.get('rebound_pct', 0),
                "exec_str": realtime_data.get('execution_strength', 0),
                "prog_net": realtime_data.get('program_net_buy_3min', 0),
            })

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

            # 진입 비중 결정 (켈리 × 레짐 × US시장 보정)
            kelly_pct = self.kelly.calculate_kelly_fraction()
            entry_weight = determine_entry_weight(
                ensemble_score=logic_scores['ensemble_score'],
                regime=regime.value,
                kelly_pct=kelly_pct,
                current_cash_ratio=current_cash_ratio,
                position_count=position_count,
            )

            # US 시장 보정 적용
            entry_weight *= us_check['weight_multiplier']

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

                # 가드에 진입 기록
                self.guard.record_entry()

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

                # Discord 매수 알림
                self.discord.send_buy_signal({
                    "symbol": symbol, "name": name,
                    "price": current_price,
                    "quantity": quantity,
                    "amount": current_price * quantity,
                    "weight": entry_weight * 100,
                    "ensemble": logic_scores['ensemble_score'],
                    "logic1": logic_scores['logic1_tow'],
                    "logic2": logic_scores['logic2_v'],
                    "logic3": logic_scores['logic3_moc'],
                    "logic4": logic_scores['logic4_news'],
                    "dominant_logic": logic_scores['dominant_logic'],
                    "phase2_score": stock.get('phase2_score', 0),
                    "phase3_score": stock.get('phase3_score', 0),
                    "v_score": v_score,
                    "regime": regime.value,
                    "confidence": min(int(logic_scores['ensemble_score']), 100),
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

                # Discord 장후 알림
                sell_qty = after_data.get('sell_order_qty', 0)
                buy_qty = after_data.get('buy_order_qty', 0)
                ratio = sell_qty / buy_qty if buy_qty > 0 else 0
                self.discord.send_after_hours_alert({
                    "symbol": symbol, "name": name,
                    "sell_buy_ratio": ratio,
                    "action": result['action'],
                    "sell_qty": result['sell_qty'],
                    "sell_pct": result['sell_qty'] / qty * 100 if qty > 0 else 0,
                    "reason": result['reason'],
                })

    # ═══════════════════════════════════════════════════════
    # 익일 오전 청산 (PHASE 5) + StopLossEngine
    # ═══════════════════════════════════════════════════════

    def run_morning_strategy(self):
        """
        익일 오전 청산 전략 실행 (08:30~10:00)

        통합 흐름:
        1. 야간 돌발 악재 체크 (08:30)
        2. StopLossEngine: 5단계 우선순위 손절 평가
        3. 시나리오 A~D + STOP + EMERGENCY 판단 후 분할/전량 청산
        4. 10:00 = 무조건 전량 강제 청산
        """
        if not self.portfolio['holdings']:
            logger.info("[ENGINE] 보유 종목 없음 — 청산 불필요")
            return

        logger.info("=" * 60)
        logger.info("[ENGINE] PHASE 5: 오전 청산 전략 시작 (v2.0 Part 3)")
        logger.info("=" * 60)

        # 총자산 조회 및 StopLossEngine 초기화
        account = self.api.get_balance()
        total_asset = account.get('total_asset', account.get('cash', 0))
        self._init_stop_loss_engine(total_asset)

        # 거시 레짐 재확인 (08:30)
        market_data = self.api.get_market_overview() if hasattr(self.api, 'get_market_overview') else {}
        kospi_change = market_data.get('kospi_change', 0)

        # 야간 돌발 악재 체크
        overnight = assess_overnight_risk(
            expected_gap_pct=market_data.get('expected_gap_pct', 0),
            us_close_change=market_data.get('us_close_change', 0),
            vix=market_data.get('vix', 15),
        )
        if overnight['urgency'] == 'HIGH':
            logger.warning(f"[ENGINE] 야간 악재 감지: {overnight['reason']}")
            self.discord.send_system_status(f"야간 악재: {overnight['reason']} → {overnight['action']}")

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
            ma20 = price_info.get('ma20', 0)
            high_since_open = price_info.get('high_since_open', current_price)
            current_time_str = datetime.now().strftime("%H:%M:%S")

            # ── StopLossEngine 우선순위 평가 ──
            stop_result = self.stop_loss_engine.evaluate(
                entry_price=entry_price,
                current_price=current_price,
                quantity=quantity,
                current_time=current_time_str,
                open_price=open_price,
                kospi_change=kospi_change,
                ma20=ma20,
            )

            if stop_result['trigger']:
                # 손절 발동 → 전량 매도
                sell_qty = quantity
                success = self.api.place_order(symbol, sell_qty, 0, "sell")

                if success:
                    pnl = (current_price - entry_price) * sell_qty
                    pnl_pct = (current_price - entry_price) / entry_price * 100

                    logger.warning(
                        f"[ENGINE] 손절: {name} {sell_qty}주 | "
                        f"유형={stop_result['type']} | "
                        f"수익={pnl:+,.0f}원({pnl_pct:+.2f}%) | "
                        f"사유={stop_result['reason']}"
                    )

                    # 가드에 결과 기록
                    self.guard.record_trade_result(pnl_pct, symbol)

                    # 일일 거래 기록
                    self.today_trades.append({
                        "name": name, "symbol": symbol,
                        "pnl": pnl, "pnl_percent": pnl_pct,
                        "exit_scenario": stop_result['type'],
                        "ensemble_score": holding.get('ensemble_score', 0),
                    })

                    # Discord 손절 알림
                    self.discord.send_stop_loss_alert({
                        "symbol": symbol, "name": name,
                        "type": stop_result['type'],
                        "priority": stop_result['priority'],
                        "reason": stop_result['reason'],
                        "action": stop_result['action'],
                        "quantity": sell_qty,
                    })

                    # Discord 청산 알림
                    self.discord.send_exit_alert({
                        "symbol": symbol, "name": name,
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "pnl": pnl, "pnl_pct": pnl_pct,
                        "scenario": stop_result['type'],
                        "exit_reason": stop_result['reason'],
                    })

                    holdings_to_remove.append(i)
                continue

            # ── 시나리오 기반 청산 판단 ──
            scenario, reason, sell_ratio = determine_exit_scenario(
                entry_price=entry_price,
                open_price=open_price,
                current_price=current_price,
                current_time=datetime.now(),
                kospi_change=kospi_change,
                ma20=ma20,
                high_since_open=high_since_open,
            )

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

                    # 가드에 결과 기록
                    self.guard.record_trade_result(pnl_pct, symbol)

                    # 일일 거래 기록
                    self.today_trades.append({
                        "name": name, "symbol": symbol,
                        "pnl": pnl, "pnl_percent": pnl_pct,
                        "exit_scenario": scenario.value,
                        "ensemble_score": holding.get('ensemble_score', 0),
                    })

                    # Discord 청산 알림
                    self.discord.send_exit_alert({
                        "symbol": symbol, "name": name,
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "pnl": pnl, "pnl_pct": pnl_pct,
                        "scenario": scenario.value,
                        "exit_reason": reason,
                    })

                    remaining = exit_result['remaining_qty']
                    if remaining <= 0:
                        holdings_to_remove.append(i)
                    else:
                        holding['quantity'] = remaining

        for idx in sorted(holdings_to_remove, reverse=True):
            self.portfolio['holdings'].pop(idx)
        self._save_portfolio()

    # ═══════════════════════════════════════════════════════
    # 일일 리포트 생성 및 전송
    # ═══════════════════════════════════════════════════════

    def run_daily_report(self, market_data: Dict = None, watchlist: List[str] = None):
        """장 마감 후 일일 리포트 생성 및 Discord 전송"""
        logger.info("[ENGINE] 일일 리포트 생성 시작")

        report = self.report_generator.generate(
            today_trades=self.today_trades,
            market_data=market_data,
            ai_cost=Config.DAILY_AI_COST_ESTIMATE,
            watchlist=watchlist,
        )

        # Discord 전송
        self.discord.send_daily_report(report)

        # DB 저장
        total_pnl = sum(t.get('pnl', 0) or 0 for t in self.today_trades)
        account = self.api.get_balance()
        total_asset = account.get('total_asset', 0)
        total_pnl_pct = total_pnl / total_asset * 100 if total_asset > 0 else 0

        self.report_generator.save_daily_performance(
            total_asset=total_asset,
            daily_pnl=total_pnl,
            daily_pnl_pct=total_pnl_pct,
            trades=self.today_trades,
            market_data=market_data,
            regime=self.macro_filter.current_regime.value,
        )

        # KPI 체크
        kpi_report = self.report_generator.generate_kpi_check()
        logger.info(f"\n{kpi_report}")

        logger.info("[ENGINE] 일일 리포트 완료")
        return report

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
        guard_status = self.guard.get_status()
        logger.info(f"  레짐={macro.get('regime', 'N/A')} | "
                     f"진입가능={macro.get('entry_allowed', 'N/A')}")
        logger.info(f"  가드: {guard_status}")
        logger.info("=" * 60)

    def execute_closing_bet(self):
        """종가 베팅 실행 (래퍼)"""
        self.run_closing_strategy()

    def execute_morning_sell(self):
        """오전 매도 실행 (래퍼)"""
        self.run_morning_strategy()

    def reset_daily(self):
        """일일 초기화"""
        self.today_trades.clear()
        self.guard.reset_daily()
        self.discord.send_system_status("일일 초기화 완료")
        logger.info("[ENGINE] 일일 초기화 완료")
