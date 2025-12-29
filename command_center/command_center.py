"""
커맨드 센터 - 전체 시스템 통합 및 의사결정
강화학습 기반 매매 의사결정을 수행합니다.
"""
import logging
from typing import Dict, List, Optional
from api import KISApi
from strategy import TradeHistory
from .market_state import MarketState
from .rl_agent import RLAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommandCenter:
    """커맨드 센터 - AI 기반 매매 의사결정"""

    def __init__(self, api: KISApi, trade_history: TradeHistory):
        self.api = api
        self.trade_history = trade_history

        # 시장 상태 분석기
        self.market_state = MarketState(api, trade_history)

        # 강화학습 에이전트
        self.rl_agent = RLAgent(
            state_size=10,
            n_actions=5,
            learning_rate=0.1,
            discount_factor=0.95,
            epsilon=0.1,
        )

        # 이전 상태 및 행동 (학습용)
        self.prev_state = None
        self.prev_action = None

        logger.info("🚀 커맨드 센터 초기화 완료")

    def analyze_situation(self, candidates: List[Dict]) -> Dict:
        """
        전체 상황 분석

        Args:
            candidates: 매수 후보 종목 리스트

        Returns:
            상황 분석 결과
        """
        logger.info("\n" + "🎯" * 30)
        logger.info("커맨드 센터: 상황 분석 시작")
        logger.info("🎯" * 30 + "\n")

        # 1. 시장 상태 벡터 생성
        state = self.market_state.get_state_vector(candidates)

        # 2. 시장 상황 분류
        market_condition = self.market_state.classify_market_condition(state)

        # 3. 시장 분석 출력
        self.market_state.print_market_analysis(state)

        # 4. AI 추천 행동
        recommendation = self.rl_agent.get_action_recommendation(state, market_condition)
        self.rl_agent.print_recommendation(recommendation)

        # 5. 거래 통계
        self.trade_history.print_statistics(recent_trades=20)

        # 현재 상태 저장 (다음 학습에 사용)
        self.prev_state = state
        self.prev_action = recommendation['best_action_id']

        return {
            "state": state,
            "market_condition": market_condition,
            "recommendation": recommendation,
        }

    def should_trade(self, analysis: Dict) -> bool:
        """
        거래 실행 여부 결정

        Args:
            analysis: 상황 분석 결과

        Returns:
            거래 실행 여부
        """
        best_action = analysis['recommendation']['best_action_id']

        # 매수 행동 (0, 1, 2)이면 거래
        should_trade = best_action in [
            RLAgent.ACTION_BUY_AGGRESSIVE,
            RLAgent.ACTION_BUY_MODERATE,
            RLAgent.ACTION_BUY_CONSERVATIVE,
        ]

        if should_trade:
            logger.info(f"✅ 커맨드 센터 판단: 거래 실행 ({analysis['recommendation']['best_action']})")
        else:
            logger.info(f"⏸️  커맨드 센터 판단: 거래 보류 ({analysis['recommendation']['best_action']})")

        return should_trade

    def get_position_sizing_factor(self, analysis: Dict) -> float:
        """
        포지션 사이즈 조절 계수 계산

        Args:
            analysis: 상황 분석 결과

        Returns:
            조절 계수 (0.5 ~ 1.5)
        """
        best_action = analysis['recommendation']['best_action_id']
        market_condition = analysis['market_condition']

        # 기본 계수
        factor = 1.0

        # 행동에 따른 조절
        if best_action == RLAgent.ACTION_BUY_AGGRESSIVE:
            factor = 1.5  # 공격적 매수: 1.5배
        elif best_action == RLAgent.ACTION_BUY_MODERATE:
            factor = 1.0  # 보통 매수: 1.0배
        elif best_action == RLAgent.ACTION_BUY_CONSERVATIVE:
            factor = 0.5  # 보수적 매수: 0.5배

        # 시장 상황에 따른 추가 조절
        if market_condition == "STRONG_BULL":
            factor *= 1.2  # 강세장: 20% 증가
        elif market_condition == "STRONG_BEAR":
            factor *= 0.7  # 약세장: 30% 감소

        logger.info(f"📊 포지션 사이즈 조절 계수: {factor:.2f}x")

        return factor

    def update_from_trade_result(self, profit_rate: float):
        """
        거래 결과로부터 학습

        Args:
            profit_rate: 수익률
        """
        if self.prev_state is None or self.prev_action is None:
            logger.warning("⚠️  이전 상태/행동 정보 없음. 학습 불가")
            return

        # 현재 상태 (거래 후)
        stats = self.trade_history.get_statistics(recent_trades=5)
        current_state = self.market_state.get_state_vector([])  # 빈 리스트로 현재 통계만 반영

        # 시장 상황
        market_condition = self.market_state.classify_market_condition(current_state)

        # 보상 계산
        reward = self.rl_agent.calculate_reward(
            action=self.prev_action,
            profit_rate=profit_rate,
            market_condition=market_condition
        )

        # Q-learning 업데이트
        self.rl_agent.update_q_value(
            state=self.prev_state,
            action=self.prev_action,
            reward=reward,
            next_state=current_state
        )

        logger.info(f"✅ 거래 결과 학습 완료 (수익률: {profit_rate * 100:+.2f}%, 보상: {reward:+.3f})")

    def print_dashboard(self):
        """실시간 대시보드 출력"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 커맨드 센터 대시보드")
        logger.info("=" * 60)

        # 거래 통계
        stats = self.trade_history.get_statistics()
        logger.info(f"\n[거래 통계]")
        logger.info(f"총 거래: {stats['total_trades']}건")
        logger.info(f"승률: {stats['win_rate'] * 100:.2f}%")
        logger.info(f"평균 수익률: {stats['avg_profit_rate']:+.2f}%")
        logger.info(f"총 수익: {stats['total_profit']:,}원")

        # AI 학습 상태
        logger.info(f"\n[AI 학습 상태]")
        logger.info(f"총 업데이트 횟수: {self.rl_agent.total_updates}회")
        logger.info(f"Q-테이블 크기: {len(self.rl_agent.q_table)}개 상태")
        logger.info(f"탐험 확률 (ε): {self.rl_agent.epsilon * 100:.1f}%")

        # 최근 거래 내역
        recent_trades = self.trade_history.get_recent_trades(count=5)
        if recent_trades:
            logger.info(f"\n[최근 거래 내역]")
            for i, trade in enumerate(recent_trades[-5:], 1):
                logger.info(
                    f"{i}. {trade['stock_name']} | "
                    f"수익률: {trade['profit_rate']:+.2f}% | "
                    f"수익: {trade['profit']:+,}원"
                )

        logger.info("=" * 60 + "\n")
