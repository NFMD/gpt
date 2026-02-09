"""
커맨드 센터 - AI 오케스트레이션 및 최종 의사결정 (v2.0)
Claude Opus(Commander) 역할을 수행하며 다른 AI들의 분석을 종합합니다.

v2.0 변경사항:
- 4가지 수익원천 로직 앙상블 점수 기반 의사결정
- 거시 환경 필터(MarketRegime) 통합
- VETO 시스템 통합
- COMMANDER 입출력 포맷 표준화
- 포지션 사이징에 레짐 배수 반영
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from config import Config
from strategy.ensemble import EnsembleScorer, EnsembleResult
from strategy.macro_filter import MacroFilter, MarketRegime
from strategy.veto import VetoScanner
from strategy.tug_of_war import TugOfWarAnalyzer
from strategy.moc_imbalance import MOCImbalanceAnalyzer
from strategy.news_analyzer import NewsTemporalAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommandCenter:
    """커맨드 센터 - AI 오케스트레이션 (v2.0)"""

    def __init__(self, api=None, trade_history=None):
        self.api = api
        self.trade_history = trade_history

        # v2.0 하위 모듈
        self.ensemble_scorer = EnsembleScorer()
        self.macro_filter = MacroFilter()
        self.veto_scanner = VetoScanner()
        self.tow_analyzer = TugOfWarAnalyzer()
        self.moc_analyzer = MOCImbalanceAnalyzer()
        self.news_analyzer = NewsTemporalAnalyzer()

        logger.info("CommandCenter (v2.0) 초기화 완료")

    def get_commander_decision(
        self,
        candidates: List[Dict],
        market_condition: Dict,
        account_info: Dict,
    ) -> List[Dict]:
        """
        COMMANDER -- 최종 의사결정 (v2.0)

        1. 거시 환경 필터 적용
        2. VETO 스캔
        3. 4가지 로직별 점수 산출
        4. 앙상블 종합 점수 기반 순위화
        5. 포지션 사이징 (레짐 배수 반영)
        """
        logger.info("=" * 60)
        logger.info("[COMMANDER] 최종 의사결정 시작 (v2.0 앙상블)")
        logger.info("=" * 60)

        # 1. 거시 환경 필터
        regime = self.macro_filter.update(
            kospi_change=market_condition.get("kospi_change", 0),
            kosdaq_change=market_condition.get("kosdaq_change", 0),
            us_futures_change=market_condition.get("us_futures", 0),
            vix=market_condition.get("vix", 15),
        )

        if regime == MarketRegime.DANGER:
            logger.warning("[COMMANDER] DANGER 레짐 -- 신규 진입 전면 금지")
            return []

        regime_multiplier = self.macro_filter.get_position_multiplier()

        # 2. VETO 스캔 + 3. 로직별 점수 산출 + 4. 앙상블
        ensemble_results: List[EnsembleResult] = []

        for stock in candidates:
            symbol = stock.get("stock_code", "")
            name = stock.get("stock_name", "")

            # VETO 체크
            news_items = stock.get("news_items", [])
            veto_result = self.veto_scanner.scan_news_list(symbol, name, news_items)
            if veto_result.is_vetoed:
                logger.warning(f"[COMMANDER] {name} VETO 발동 -- 즉시 제외")
                continue

            # LOGIC 1: Tug of War
            tow_result = self.tow_analyzer.calculate_score(
                symbol=symbol,
                name=name,
                open_price=stock.get("open_price", 0),
                current_price=stock.get("current_price", 0),
                close_price_yesterday=stock.get("close_price_yesterday", 0),
                high_price=stock.get("high_price", 0),
                foreign_net_buy=stock.get("foreign_net_buy", 0),
                institution_net_buy=stock.get("institution_net_buy", 0),
                individual_net_buy=stock.get("individual_net_buy", 0),
                is_new_high_20d=stock.get("is_new_high", False),
                is_ma_aligned=stock.get("is_aligned", False),
                overnight_returns_5d=stock.get("overnight_returns_5d", []),
                trading_value=stock.get("trading_value", 0),
            )

            # LOGIC 2: V자 수급전환 (기존 phase3_score 활용 -> 100점 스케일링)
            raw_v_score = stock.get("phase3_score", 0)
            logic2_score = min(100, raw_v_score * 100 / 75) if raw_v_score > 0 else 0

            # LOGIC 3: MOC Imbalance
            moc_result = self.moc_analyzer.calculate_score(
                symbol=symbol,
                name=name,
                sell_order_qty=stock.get("sell_order_qty", 0),
                buy_order_qty=stock.get("buy_order_qty", 0),
                current_price=stock.get("current_price", 0),
                expected_close_price=stock.get("expected_close_price", 0),
                price_at_1520=stock.get("price_at_1520", stock.get("current_price", 0)),
                buy_order_surge=stock.get("buy_order_surge", False),
                expected_price_rising=stock.get("expected_price_rising", False),
            )

            # LOGIC 4: 뉴스 Temporal Anomaly
            headlines = [item.get("title", "") for item in news_items]
            sentiment = self.news_analyzer.analyze_headlines_sentiment(headlines)
            news_result = self.news_analyzer.calculate_score(
                symbol=symbol,
                name=name,
                google_news_count=stock.get("google_news_count", 0),
                naver_news_count=stock.get("naver_news_count", 0),
                news_headlines=headlines,
                sentiment_positive=sentiment["positive"],
                sentiment_negative=sentiment["negative"],
                naver_top_exposure=stock.get("naver_top_exposure", False),
                daily_pattern_match=stock.get("daily_pattern_match", False),
            )

            # 앙상블 점수 산출
            ensemble = self.ensemble_scorer.score_candidate(
                symbol=symbol,
                name=name,
                logic1_score=tow_result.score,
                logic2_score=logic2_score,
                logic3_score=moc_result.score,
                logic4_score=news_result.score,
                logic_details={
                    "tug_of_war": tow_result.details,
                    "moc_imbalance": moc_result.details if moc_result.details else {},
                    "news_temporal": news_result.details,
                },
            )
            ensemble_results.append(ensemble)

        # 4. 순위화 (SKIP 제외)
        ranked = self.ensemble_scorer.rank_candidates(ensemble_results)

        # 5. 최종 의사결정
        decisions = []
        for result in ranked[:Config.MAX_STOCKS]:
            adjusted_multiplier = result.position_multiplier * regime_multiplier

            if adjusted_multiplier <= 0:
                continue

            confidence = min(int(result.ensemble_score), 100)

            decision = {
                "action": "BUY",
                "symbol": result.symbol,
                "name": result.name,
                "price_type": "MARKET",
                "weight_pct": round(adjusted_multiplier * Config.MAX_INVESTMENT_PER_STOCK_PCT * 100, 1),
                "stop_loss_pct": Config.STOP_LOSS_RATE * 100,
                "ensemble_score": result.ensemble_score,
                "confidence": confidence,
                "dominant_logic": result.dominant_logic,
                "entry_tier": result.entry_tier,
                "position_multiplier": adjusted_multiplier,
                "logic_scores": {
                    "tug_of_war": result.logic_scores[0].score if len(result.logic_scores) > 0 else 0,
                    "v_pattern": result.logic_scores[1].score if len(result.logic_scores) > 1 else 0,
                    "moc_imbalance": result.logic_scores[2].score if len(result.logic_scores) > 2 else 0,
                    "news_temporal": result.logic_scores[3].score if len(result.logic_scores) > 3 else 0,
                },
                "market_regime": regime.value,
                "reasoning": self._build_reasoning(result, regime),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            decisions.append(decision)
            logger.info(
                f"[COMMANDER] BUY {result.name} | "
                f"앙상블={result.ensemble_score:.1f} | "
                f"등급={result.entry_tier} | "
                f"비중={decision['weight_pct']:.1f}% | "
                f"레짐={regime.value}"
            )

        if not decisions:
            logger.info("[COMMANDER] 진입 조건 충족 종목 없음")

        return decisions

    def _build_reasoning(self, result: EnsembleResult, regime: MarketRegime) -> str:
        """의사결정 근거 문자열 생성"""
        parts = [f"앙상블 {result.ensemble_score:.1f}점({result.entry_tier})"]

        for ls in result.logic_scores:
            if ls.score > 0:
                parts.append(f"{ls.logic_name} {ls.score:.0f}")

        parts.append(f"주도로직={result.dominant_logic}")
        parts.append(f"레짐={regime.value}")

        return " | ".join(parts)

    def get_macro_status(self) -> Dict:
        """현재 거시 환경 상태 조회"""
        return self.macro_filter.get_regime_summary()

    def analyze_market_sentiment(self) -> Dict:
        """GPT (ANALYST) - 비정량 데이터 분석"""
        return {
            "sentiment_score": 65,
            "risk_level": "LOW",
            "top_themes": ["반도체", "AI"],
        }

    def explore_themes(self) -> List[str]:
        """Gemini (EXPLORER) - 테마 및 재료 탐색"""
        return ["AI 온디바이스", "CXL", "HBM"]
