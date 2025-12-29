"""
강화학습 에이전트 모듈
Q-learning 기반으로 매매 의사결정을 학습합니다.
"""
import logging
import json
import numpy as np
from pathlib import Path
from typing import Dict, Tuple


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RLAgent:
    """강화학습 에이전트 (Q-Learning)"""

    # 행동 정의
    ACTION_BUY_AGGRESSIVE = 0  # 적극 매수
    ACTION_BUY_MODERATE = 1  # 보통 매수
    ACTION_BUY_CONSERVATIVE = 2  # 보수적 매수
    ACTION_HOLD = 3  # 대기
    ACTION_SELL = 4  # 매도

    ACTION_NAMES = {
        0: "적극 매수",
        1: "보통 매수",
        2: "보수적 매수",
        3: "대기",
        4: "매도",
    }

    def __init__(
        self,
        state_size: int = 10,
        n_actions: int = 5,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
    ):
        """
        Args:
            state_size: 상태 벡터 차원
            n_actions: 행동 개수
            learning_rate: 학습률 (alpha)
            discount_factor: 할인 계수 (gamma)
            epsilon: 탐험 확률
        """
        self.state_size = state_size
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon

        # Q-테이블 (이산화된 상태 공간 사용)
        self.q_table_file = Path(__file__).parent.parent / "data" / "q_table.json"
        self.q_table = self._load_q_table()

        # 학습 통계
        self.total_updates = 0

    def _load_q_table(self) -> Dict:
        """Q-테이블 로드"""
        if self.q_table_file.exists():
            with open(self.q_table_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_q_table(self):
        """Q-테이블 저장"""
        self.q_table_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.q_table_file, 'w') as f:
            json.dump(self.q_table, f, indent=2)

    def _discretize_state(self, state: np.ndarray, bins: int = 5) -> str:
        """
        연속 상태를 이산 상태로 변환

        Args:
            state: 연속 상태 벡터
            bins: 각 차원을 나눌 구간 수

        Returns:
            이산화된 상태 문자열
        """
        discretized = []
        for value in state:
            # 0~1 범위를 bins개 구간으로 나눔
            bin_idx = min(int(value * bins), bins - 1)
            discretized.append(str(bin_idx))

        return "_".join(discretized)

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """
        주어진 상태에서의 Q값들 조회

        Args:
            state: 상태 벡터

        Returns:
            각 행동에 대한 Q값 배열
        """
        state_key = self._discretize_state(state)

        if state_key not in self.q_table:
            # 초기 Q값: 0으로 설정
            self.q_table[state_key] = [0.0] * self.n_actions

        return np.array(self.q_table[state_key])

    def select_action(self, state: np.ndarray, greedy: bool = False) -> int:
        """
        행동 선택 (ε-greedy 정책)

        Args:
            state: 현재 상태
            greedy: True면 무조건 greedy 선택 (탐험 없음)

        Returns:
            선택된 행동 인덱스
        """
        if not greedy and np.random.random() < self.epsilon:
            # 탐험: 무작위 행동
            action = np.random.randint(self.n_actions)
            logger.debug(f"🎲 탐험: {self.ACTION_NAMES[action]}")
        else:
            # 활용: 최선의 행동
            q_values = self.get_q_values(state)
            action = int(np.argmax(q_values))
            logger.debug(f"🎯 활용: {self.ACTION_NAMES[action]} (Q={q_values[action]:.3f})")

        return action

    def update_q_value(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray
    ):
        """
        Q-learning 업데이트

        Q(s, a) ← Q(s, a) + α[r + γ max Q(s', a') - Q(s, a)]

        Args:
            state: 현재 상태
            action: 실행한 행동
            reward: 받은 보상
            next_state: 다음 상태
        """
        state_key = self._discretize_state(state)

        # 현재 Q값
        current_q = self.get_q_values(state)[action]

        # 다음 상태에서의 최대 Q값
        next_q_values = self.get_q_values(next_state)
        max_next_q = np.max(next_q_values)

        # TD 타겟
        td_target = reward + self.gamma * max_next_q

        # TD 오차
        td_error = td_target - current_q

        # Q값 업데이트
        new_q = current_q + self.lr * td_error

        self.q_table[state_key][action] = new_q
        self.total_updates += 1

        # 주기적으로 저장
        if self.total_updates % 10 == 0:
            self._save_q_table()

        logger.info(
            f"📚 Q-learning 업데이트: {self.ACTION_NAMES[action]}\n"
            f"   보상: {reward:+.3f} | TD 오차: {td_error:+.3f} | "
            f"새 Q값: {new_q:.3f}"
        )

    def calculate_reward(
        self,
        action: int,
        profit_rate: float,
        market_condition: str
    ) -> float:
        """
        보상 계산

        Args:
            action: 실행한 행동
            profit_rate: 수익률
            market_condition: 시장 상황

        Returns:
            보상값
        """
        # 기본 보상: 수익률 기반
        reward = profit_rate

        # 행동별 보너스/페널티
        if action in [self.ACTION_BUY_AGGRESSIVE, self.ACTION_BUY_MODERATE, self.ACTION_BUY_CONSERVATIVE]:
            # 매수 행동
            if profit_rate > 0.03:  # 3% 이상 수익
                reward += 0.5  # 보너스
            elif profit_rate < -0.02:  # 2% 이상 손실
                reward -= 0.5  # 페널티

            # 시장 상황에 따른 조정
            if market_condition in ["STRONG_BULL", "BULL"]:
                reward += 0.2  # 상승장에서 매수는 좋은 선택
            elif market_condition in ["STRONG_BEAR", "BEAR"]:
                reward -= 0.2  # 하락장에서 매수는 나쁜 선택

        elif action == self.ACTION_HOLD:
            # 대기 행동
            if market_condition == "NEUTRAL":
                reward += 0.1  # 중립장에서 대기는 합리적
            else:
                reward -= 0.1  # 기회 비용

        elif action == self.ACTION_SELL:
            # 매도 행동
            if profit_rate > 0:
                reward += 0.3  # 이익 실현 보너스
            else:
                reward -= 0.1  # 손실 매도 페널티

        return reward

    def get_action_recommendation(
        self,
        state: np.ndarray,
        market_condition: str
    ) -> Dict:
        """
        현재 상태에서의 행동 추천

        Args:
            state: 현재 상태
            market_condition: 시장 상황

        Returns:
            추천 정보
        """
        q_values = self.get_q_values(state)
        best_action = int(np.argmax(q_values))
        best_q_value = q_values[best_action]

        # 행동별 Q값 정렬
        sorted_indices = np.argsort(q_values)[::-1]

        recommendations = []
        for idx in sorted_indices[:3]:  # 상위 3개
            recommendations.append({
                "action": self.ACTION_NAMES[idx],
                "q_value": float(q_values[idx]),
            })

        return {
            "best_action": self.ACTION_NAMES[best_action],
            "best_action_id": best_action,
            "best_q_value": float(best_q_value),
            "market_condition": market_condition,
            "all_recommendations": recommendations,
        }

    def print_recommendation(self, recommendation: Dict):
        """추천 정보 출력"""
        logger.info("=" * 60)
        logger.info("🤖 AI 추천 행동")
        logger.info("=" * 60)
        logger.info(f"시장 상황: {recommendation['market_condition']}")
        logger.info(f"➡️  최적 행동: {recommendation['best_action']} (Q={recommendation['best_q_value']:.3f})")
        logger.info("\n상위 추천:")
        for i, rec in enumerate(recommendation['all_recommendations'], 1):
            logger.info(f"  {i}. {rec['action']:20s} (Q={rec['q_value']:.3f})")
        logger.info("=" * 60)
