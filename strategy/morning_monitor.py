"""
장 시작 모니터링 모듈 (v2.0)
PHASE 5: 청산 로직 (익일 08:30~10:00)을 구현합니다.

핵심 원칙:
- "10시 전 전량 청산" — 예외 없음
- "3분 내 시초가 돌파 양봉 없으면 즉시 매도" — 시간 손절
- "수확의 골든타임은 09:00~09:10" — 여기서 판다

v2.0 변경사항:
- ExitScenario 확장: FLAT_UP, FLAT_DOWN, MA20_STOP 추가
- determine_exit_scenario: ma20, high_since_open 파라미터 추가
- execute_exit: 매도비율(sell_ratio) 기반 분할매도 지원
- after_hours_risk_check: 장후 리스크 관리 (3시59분의 법칙)
- 손절 규칙 5단계 우선순위 (비상>가격>20일선>시간>강제)
"""
import logging
from datetime import datetime, time
from enum import Enum
from typing import Dict, Tuple
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 청산 시나리오
# ═══════════════════════════════════════════════════════

class ExitScenario(Enum):
    GAP_UP_SUCCESS = "A"        # 갭상승 성공
    GAP_UP_STRONG = "A-1"       # 갭상승 + 강세 지속
    GAP_UP_WEAK = "A-2"         # 갭상승 후 약세
    FLAT_OPEN = "B"             # 보합 출발
    FLAT_UP = "B-1"             # 보합 → 상승
    FLAT_DOWN = "B-2"           # 보합 → 하락
    GAP_DOWN = "C"              # 갭하락
    TIMEOUT = "D"               # 타임아웃 (10시)
    STOP_LOSS = "STOP"          # 가격 손절 (-3%)
    MA20_STOP = "MA20"          # 20일선 이탈 손절
    EMERGENCY = "EMERGENCY"     # 비상 청산 (코스피 -2%)


# ═══════════════════════════════════════════════════════
# 청산 시나리오 판단
# ═══════════════════════════════════════════════════════

def determine_exit_scenario(
    entry_price: float,
    open_price: float,
    current_price: float,
    current_time: datetime,
    kospi_change: float,
    ma20: float = 0.0,
    high_since_open: float = 0.0,
) -> Tuple[ExitScenario, str, float]:
    """
    청산 시나리오 판단 (v2.0)

    손절 우선순위:
    1. 비상 청산: 코스피 -2%↓
    2. 가격 손절: 손실 -3%↓
    3. 타임아웃: 10:00 도달
    4. 시나리오별 판단 (A/B/C)

    Returns:
        (시나리오, 사유, 매도비율 0.0~1.0)
    """
    now = current_time.time()
    pnl_pct = (current_price - entry_price) / entry_price * 100
    gap_pct = (open_price - entry_price) / entry_price * 100

    # ══ 우선순위 1: 비상 청산 ══
    if kospi_change <= Config.EMERGENCY_KOSPI_DROP:
        return ExitScenario.EMERGENCY, "코스피 급락 비상청산", 1.0

    # ══ 우선순위 2: 가격 손절 ══
    if pnl_pct <= Config.STOP_LOSS_RATE * 100:
        return ExitScenario.STOP_LOSS, f"손절선 도달 ({pnl_pct:.1f}%)", 1.0

    # ══ 우선순위 3: 타임아웃 ══
    if now >= time(10, 0):
        return ExitScenario.TIMEOUT, "10시 강제청산", 1.0

    # ══ 시나리오별 판단 ══

    # --- 갭상승 (+2%↑) ---
    if gap_pct >= 2.0:
        if now <= time(9, 3):
            return ExitScenario.GAP_UP_SUCCESS, "갭상승, 3분 관찰", 0.0

        if current_price > open_price:
            if now <= time(9, 10):
                return ExitScenario.GAP_UP_STRONG, "강세 지속, 분할매도 준비", 0.5
            else:
                return ExitScenario.GAP_UP_STRONG, "강세 지속, 분할매도", 0.5
        else:
            # 3분 내 시초가 이탈 → 시간 손절
            return ExitScenario.GAP_UP_WEAK, "갭상승 후 약세→시간손절", 1.0

    # --- 갭하락 (-1%↓) ---
    if gap_pct <= -1.0:
        return ExitScenario.GAP_DOWN, "갭하락→즉시 청산", 1.0

    # --- 보합 (-1% ~ +2%) ---
    if now <= time(9, 10):
        return ExitScenario.FLAT_OPEN, "보합, 방향성 관찰", 0.0

    if current_price > open_price:
        return ExitScenario.FLAT_UP, "보합→상승, 분할매도", 0.5
    else:
        return ExitScenario.FLAT_DOWN, "보합→하락, 전량 청산", 1.0


# ═══════════════════════════════════════════════════════
# 청산 실행
# ═══════════════════════════════════════════════════════

def execute_exit(
    scenario: ExitScenario,
    sell_ratio: float,
    position_qty: int,
) -> dict:
    """
    시나리오별 청산 실행 (v2.0)

    Returns:
        scenario, action, sell_qty, remaining_qty, price_type
    """
    sell_qty = int(position_qty * sell_ratio)

    return {
        "scenario": scenario.value,
        "action": "SELL" if sell_qty > 0 else "HOLD",
        "sell_qty": sell_qty,
        "remaining_qty": position_qty - sell_qty,
        "price_type": "MARKET",  # 모든 청산은 시장가
    }


# ═══════════════════════════════════════════════════════
# 장후 리스크 관리
# ═══════════════════════════════════════════════════════

def after_hours_risk_check(
    symbol: str,
    sell_order_qty: int,       # 장후 매도 잔량
    buy_order_qty: int,        # 장후 매수 잔량
    after_hours_change: float, # 시간외 등락률
    holding_qty: int,          # 보유 수량
) -> dict:
    """
    장후 리스크 관리 판단

    3시 59분의 법칙: 매도잔량 >> 매수잔량 시 종가 정리
    시간외 익절: +4%↑ 시 일부 매도

    Returns:
        action, sell_qty, reason, sell_buy_ratio, after_hours_change
    """
    action = "HOLD"
    sell_qty = 0
    reason = ""

    # 매도/매수 비율
    if buy_order_qty > 0:
        sell_buy_ratio = sell_order_qty / buy_order_qty
    else:
        sell_buy_ratio = float('inf')

    # ── 3시 59분의 법칙 ──
    if sell_buy_ratio >= 2.0:
        action = "PARTIAL_SELL"
        sell_qty = int(holding_qty * 0.5)
        reason = f"장후 매도잔량 우위 ({sell_buy_ratio:.1f}:1) → 50% 정리"
    elif sell_buy_ratio >= 1.5:
        action = "PARTIAL_SELL"
        sell_qty = int(holding_qty * 0.3)
        reason = f"장후 매도잔량 주의 ({sell_buy_ratio:.1f}:1) → 30% 정리"

    # ── 시간외 단일가 익절 ──
    if after_hours_change >= 4.0:
        action = "PARTIAL_SELL"
        sell_qty = max(sell_qty, int(holding_qty * 0.5))
        reason = f"시간외 +{after_hours_change:.1f}% 급등 → 50% 익절"

    if action != "HOLD":
        logger.info(
            f"[PHASE5] {symbol} 장후 리스크: {reason} | "
            f"매도잔량비={sell_buy_ratio:.1f} | 시간외={after_hours_change:+.1f}%"
        )

    return {
        "action": action,
        "sell_qty": sell_qty,
        "reason": reason,
        "sell_buy_ratio": round(sell_buy_ratio, 2) if sell_buy_ratio != float('inf') else 999.9,
        "after_hours_change": after_hours_change,
    }


# ═══════════════════════════════════════════════════════
# MorningMonitor 클래스
# ═══════════════════════════════════════════════════════

class MorningMonitor:
    """장 시작 모니터링 시스템 (v2.0)"""

    def __init__(self, api=None):
        self.api = api
        logger.info("[PHASE5] MorningMonitor (v2.0) 초기화 완료")

    def determine_exit_scenario(
        self,
        entry_price: float,
        open_price: float,
        current_price: float,
        current_time: datetime,
        kospi_change: float,
        ma20: float = 0.0,
        high_since_open: float = 0.0,
    ) -> Tuple[ExitScenario, str, float]:
        """청산 시나리오 판단 (v2.0 래퍼)"""
        return determine_exit_scenario(
            entry_price, open_price, current_price,
            current_time, kospi_change, ma20, high_since_open,
        )

    def execute_exit(self, scenario: ExitScenario, sell_ratio: float, position_qty: int) -> Dict:
        """시나리오별 청산 실행 (v2.0 래퍼)"""
        return execute_exit(scenario, sell_ratio, position_qty)

    def check_after_hours_risk(
        self, symbol: str, sell_order_qty: int, buy_order_qty: int,
        after_hours_change: float, holding_qty: int,
    ) -> Dict:
        """장후 리스크 체크 래퍼"""
        return after_hours_risk_check(
            symbol, sell_order_qty, buy_order_qty,
            after_hours_change, holding_qty,
        )
