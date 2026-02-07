"""
켈리 공식 기반 베팅 사이즈 결정 모듈 (v1.1)
거래 실적을 바탕으로 최적의 투자 비율을 계산합니다.
"""
import logging
from typing import Dict, Optional
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KellyCriterion:
    """켈리 공식 계산기 (v1.1)"""

    def __init__(self, trade_history=None):
        self.trade_history = trade_history

    def calculate_kelly_fraction(
        self,
        win_rate: float = 0.55,
        avg_win: float = 0.02,
        avg_loss: float = 0.015,
        kelly_fraction: float = 0.5
    ) -> float:
        """
        켈리 공식 기반 포지션 사이징
        
        Args:
            win_rate: 승률 (0~1)
            avg_win: 평균 수익률
            avg_loss: 평균 손실률 (양수)
            kelly_fraction: 켈리 비율 (보수적으로 0.5 적용)
        
        Returns:
            최적 베팅 비율 (0~1)
        """
        if avg_loss == 0:
            return 0
        
        # 손익비
        win_loss_ratio = avg_win / avg_loss
        
        # 풀 켈리 계산
        full_kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Half Kelly 적용 (보수적)
        position_size = max(0, full_kelly * kelly_fraction)
        
        # 최대 30% 제한 (Config 반영)
        return min(position_size, Config.MAX_INVESTMENT_PER_STOCK_PCT)

    def get_position_size(self, total_balance: int, stock_price: int, **kwargs) -> Dict:
        """포지션 사이즈 계산 결과 반환"""
        fraction = self.calculate_kelly_fraction(**kwargs)
        investment_amount = int(total_balance * fraction)
        quantity = investment_amount // stock_price
        
        return {
            "fraction": fraction,
            "investment_amount": investment_amount,
            "quantity": quantity
        }
