"""
시장 상태 분석 모듈
현재 시장 상황을 정량화하여 상태 벡터로 변환합니다.
"""
import logging
from typing import Dict, List
import numpy as np
from api import KISApi
from strategy import TradeHistory


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketState:
    """시장 상태 분석기"""

    def __init__(self, api: KISApi, trade_history: TradeHistory):
        self.api = api
        self.trade_history = trade_history

    def get_state_vector(self, candidates: List[Dict]) -> np.ndarray:
        """
        현재 시장 상황을 상태 벡터로 변환

        상태 벡터 구성 (10차원):
        0. 평균 거래대금 (정규화)
        1. 평균 등락률 (정규화)
        2. 평균 분석 점수 (0-110)
        3. 주도주 비율 (1조 이상 비율)
        4. 신고가 종목 비율
        5. 정배열 종목 비율
        6. 200일선 상승 종목 비율
        7. 외국인+기관 매수 비율
        8. 최근 승률 (20거래 기준)
        9. 평균 수익률 (20거래 기준)

        Args:
            candidates: 매수 후보 종목 리스트

        Returns:
            상태 벡터 (10차원 numpy array)
        """
        if not candidates:
            return np.zeros(10)

        # 거래 통계
        stats = self.trade_history.get_statistics(recent_trades=20)

        # 후보 종목 특성 계산
        avg_trading_value = np.mean([c['trading_value'] for c in candidates])
        avg_change_rate = np.mean([c['change_rate'] for c in candidates])
        avg_score = np.mean([c.get('score', 0) for c in candidates])

        # 주도주 비율 (1조 이상)
        dominant_ratio = sum(1 for c in candidates if c['trading_value'] >= 1000000000000) / len(candidates)

        # 신고가 비율
        new_high_ratio = sum(1 for c in candidates if c.get('is_new_high', False)) / len(candidates)

        # 정배열 비율
        aligned_ratio = sum(1 for c in candidates if c.get('is_aligned', False)) / len(candidates)

        # 200일선 상승 비율
        ma200_uptrend_ratio = sum(1 for c in candidates if c.get('ma200_uptrend', False)) / len(candidates)

        # 외국인+기관 동반 매수 비율
        both_buying_ratio = sum(
            1 for c in candidates
            if c.get('investor_buying', {}).get('both_buying', False)
        ) / len(candidates)

        # 거래 실적
        win_rate = stats['win_rate']
        avg_profit_rate = stats['avg_profit_rate'] / 100  # % -> 비율

        # 상태 벡터 생성
        state = np.array([
            min(avg_trading_value / 1000000000000, 1.0),  # 0. 평균 거래대금 (1조 기준 정규화)
            min(max(avg_change_rate / 20, 0), 1.0),  # 1. 평균 등락률 (20% 기준 정규화)
            avg_score / 110,  # 2. 평균 점수 (110점 만점)
            dominant_ratio,  # 3. 주도주 비율
            new_high_ratio,  # 4. 신고가 비율
            aligned_ratio,  # 5. 정배열 비율
            ma200_uptrend_ratio,  # 6. 200일선 상승 비율
            both_buying_ratio,  # 7. 외국인+기관 매수 비율
            win_rate,  # 8. 최근 승률
            min(max(avg_profit_rate, -0.1), 0.1),  # 9. 평균 수익률 (-10% ~ 10% 클리핑)
        ])

        return state

    def get_state_description(self, state: np.ndarray) -> Dict:
        """
        상태 벡터를 해석 가능한 설명으로 변환

        Args:
            state: 상태 벡터

        Returns:
            상태 설명 딕셔너리
        """
        return {
            "avg_trading_value_score": f"{state[0] * 100:.1f}%",
            "avg_change_rate_score": f"{state[1] * 100:.1f}%",
            "avg_analysis_score": f"{state[2] * 100:.1f}%",
            "dominant_stock_ratio": f"{state[3] * 100:.1f}%",
            "new_high_ratio": f"{state[4] * 100:.1f}%",
            "aligned_ratio": f"{state[5] * 100:.1f}%",
            "ma200_uptrend_ratio": f"{state[6] * 100:.1f}%",
            "both_buying_ratio": f"{state[7] * 100:.1f}%",
            "win_rate": f"{state[8] * 100:.1f}%",
            "avg_profit_rate": f"{state[9] * 100:+.1f}%",
        }

    def classify_market_condition(self, state: np.ndarray) -> str:
        """
        시장 상황 분류

        Args:
            state: 상태 벡터

        Returns:
            시장 상황 (STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR)
        """
        # 종합 점수 계산 (가중 평균)
        weights = np.array([0.15, 0.15, 0.2, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05])
        composite_score = np.dot(state, weights)

        if composite_score >= 0.7:
            return "STRONG_BULL"  # 강력한 상승장
        elif composite_score >= 0.5:
            return "BULL"  # 상승장
        elif composite_score >= 0.3:
            return "NEUTRAL"  # 중립
        elif composite_score >= 0.15:
            return "BEAR"  # 하락장
        else:
            return "STRONG_BEAR"  # 강력한 하락장

    def print_market_analysis(self, state: np.ndarray):
        """
        시장 분석 결과 출력

        Args:
            state: 상태 벡터
        """
        description = self.get_state_description(state)
        condition = self.classify_market_condition(state)

        logger.info("=" * 60)
        logger.info("📊 시장 상태 분석")
        logger.info("=" * 60)
        logger.info(f"거래대금 점수: {description['avg_trading_value_score']}")
        logger.info(f"등락률 점수: {description['avg_change_rate_score']}")
        logger.info(f"종합 분석 점수: {description['avg_analysis_score']}")
        logger.info(f"주도주 비율: {description['dominant_stock_ratio']}")
        logger.info(f"신고가 비율: {description['new_high_ratio']}")
        logger.info(f"정배열 비율: {description['aligned_ratio']}")
        logger.info(f"200일선 상승 비율: {description['ma200_uptrend_ratio']}")
        logger.info(f"동반 매수 비율: {description['both_buying_ratio']}")
        logger.info(f"최근 승률: {description['win_rate']}")
        logger.info(f"평균 수익률: {description['avg_profit_rate']}")
        logger.info("=" * 60)
        logger.info(f"🎯 시장 상황: {condition}")
        logger.info("=" * 60)
