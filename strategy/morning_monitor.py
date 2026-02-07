"""
장 시작 모니터링 모듈 (v1.1)
PHASE 5: 청산 로직 (익일 09:00~10:00)을 구현합니다.
"""
import logging
from typing import Dict, Tuple
from datetime import datetime, time
from enum import Enum
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExitScenario(Enum):
    GAP_UP_SUCCESS = "A"
    GAP_UP_STRONG = "A-1"
    GAP_UP_WEAK = "A-2"
    FLAT_OPEN = "B"
    GAP_DOWN = "C"
    TIMEOUT = "D"
    STOP_LOSS = "STOP"
    EMERGENCY = "EMERGENCY"


class MorningMonitor:
    """장 시작 모니터링 시스템 (v1.1)"""

    def __init__(self, api=None):
        self.api = api

    def determine_exit_scenario(
        self,
        entry_price: float,
        open_price: float,
        current_price: float,
        current_time: datetime,
        kospi_change: float
    ) -> Tuple[ExitScenario, str]:
        """청산 시나리오 판단"""
        
        now = current_time.time()
        pnl_pct = (current_price - entry_price) / entry_price * 100
        gap_pct = (open_price - entry_price) / entry_price * 100
        
        # 비상 청산: 코스피 -2% 이상 하락
        if kospi_change <= Config.EMERGENCY_KOSPI_DROP:
            return ExitScenario.EMERGENCY, "코스피 급락 비상청산"
        
        # 가격 손절: -3% 이상 손실
        if pnl_pct <= Config.STOP_LOSS_RATE * 100:
            return ExitScenario.STOP_LOSS, f"손절선 도달 ({pnl_pct:.1f}%)"
        
        # 타임아웃: 10시 이후
        if now >= time(10, 0):
            return ExitScenario.TIMEOUT, "10시 강제청산"
        
        # 시나리오 A: 갭상승 (+2% 이상)
        if gap_pct >= 2.0:
            if now <= time(9, 3):
                return ExitScenario.GAP_UP_SUCCESS, "갭상승 성공, 3분 관찰"
            elif current_price > open_price:
                return ExitScenario.GAP_UP_STRONG, "강세 지속"
            else:
                return ExitScenario.GAP_UP_WEAK, "갭상승 후 약세, 청산"
        
        # 시나리오 C: 갭하락 (-1% 이상)
        if gap_pct <= -1.0:
            return ExitScenario.GAP_DOWN, "갭하락, 즉시 청산"
        
        # 시나리오 B: 보합
        return ExitScenario.FLAT_OPEN, "보합 출발, 방향성 관찰"

    def execute_exit(self, scenario: ExitScenario, position_qty: int) -> Dict:
        """시나리오별 청산 실행"""
        
        actions = {
            ExitScenario.GAP_UP_SUCCESS: {"action": "HOLD", "qty": 0},
            ExitScenario.GAP_UP_STRONG: {"action": "SELL", "qty": int(position_qty * 0.5)},
            ExitScenario.GAP_UP_WEAK: {"action": "SELL", "qty": position_qty},
            ExitScenario.FLAT_OPEN: {"action": "HOLD", "qty": 0},
            ExitScenario.GAP_DOWN: {"action": "SELL", "qty": position_qty},
            ExitScenario.TIMEOUT: {"action": "SELL", "qty": position_qty},
            ExitScenario.STOP_LOSS: {"action": "SELL", "qty": position_qty},
            ExitScenario.EMERGENCY: {"action": "SELL", "qty": position_qty},
        }
        
        return actions.get(scenario, {"action": "HOLD", "qty": 0})
