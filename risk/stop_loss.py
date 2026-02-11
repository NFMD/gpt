"""
기계적 손절 자동화 엔진 (v2.0)
리스크 관리 영역 1: 감정을 배제한 기계적 손절매 원칙

손절 우선순위 (높은 번호일수록 먼저 적용):
  1. 비상 청산 — 코스피 -2% 이상 하락 → 전 포지션 즉시 시장가 청산
  2. 가격 손절 — 진입가 대비 -3% 이상 손실 (총자산 기준) → 전량 매도
  3. 20일선 손절 — 종가가 20일 이동평균선 하회 → 익일 시가 매도
  4. 시간 손절 (3분) — 09:03까지 시초가 돌파 양봉 미출현 → 전량 매도
  5. 강제 청산 (10시) — 10:00 도달 → 전량 매도 (예외 없음)
"""
import logging
from typing import Dict
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 손절 우선순위 체계
# ═══════════════════════════════════════════════════════

STOP_LOSS_PRIORITY = {
    1: {
        "name": "비상 청산",
        "condition": "코스피 -2% 이상 하락",
        "action": "전 포지션 즉시 시장가 청산",
        "automated": True,
    },
    2: {
        "name": "가격 손절",
        "condition": "진입가 대비 -3% 이상 손실 (총자산 기준)",
        "action": "해당 종목 전량 시장가 매도",
        "automated": True,
    },
    3: {
        "name": "20일선 손절",
        "condition": "종가가 20일 이동평균선 하회",
        "action": "익일 시가 매도",
        "automated": True,
    },
    4: {
        "name": "시간 손절 (3분)",
        "condition": "09:03까지 시초가 돌파 양봉 미출현",
        "action": "전량 시장가 매도",
        "automated": True,
    },
    5: {
        "name": "강제 청산 (10시)",
        "condition": "10:00 도달",
        "action": "전량 시장가 매도 — 예외 없음",
        "automated": True,
    },
}


class StopLossEngine:
    """기계적 손절 자동화 엔진"""

    def __init__(self, total_asset: float, max_loss_pct: float = None):
        self.total_asset = total_asset
        self.max_loss_pct = max_loss_pct or abs(Config.MAX_SINGLE_LOSS_PCT) / 100.0
        logger.info(
            f"[STOP] StopLossEngine 초기화 | "
            f"총자산={total_asset:,.0f} 최대손실={self.max_loss_pct:.1%}"
        )

    def update_total_asset(self, total_asset: float):
        """총자산 갱신"""
        self.total_asset = total_asset

    # ── 개별 손절 조건 체크 ──

    def check_emergency(self, kospi_change: float) -> bool:
        """비상 청산 체크 (우선순위 1)"""
        return kospi_change <= Config.EMERGENCY_KOSPI_DROP

    def check_price_stop(
        self, entry_price: float, current_price: float, quantity: int
    ) -> bool:
        """가격 기반 손절 체크 (우선순위 2)"""
        if self.total_asset <= 0:
            return False
        loss = (entry_price - current_price) * quantity
        loss_ratio = loss / self.total_asset
        return loss_ratio >= self.max_loss_pct

    def check_ma20_stop(self, current_price: float, ma20: float) -> bool:
        """20일 이평선 이탈 체크 (우선순위 3)"""
        if ma20 <= 0:
            return False
        return current_price < ma20

    def check_time_stop(
        self, current_time: str, open_price: float, current_price: float
    ) -> bool:
        """시간 손절 체크 — 09:03 시초가 미돌파 (우선순위 4)"""
        if current_time >= "09:03:00":
            return current_price <= open_price
        return False

    def check_timeout(self, current_time: str) -> bool:
        """10시 강제 청산 체크 (우선순위 5)"""
        return current_time >= "10:00:00"

    # ── 종합 평가 ──

    def evaluate(
        self,
        entry_price: float,
        current_price: float,
        quantity: int,
        current_time: str,
        open_price: float,
        kospi_change: float,
        ma20: float,
    ) -> Dict:
        """
        모든 손절 조건 종합 평가 (우선순위 순)

        Returns:
            {
                "trigger": bool,
                "type": str | None,    # EMERGENCY / PRICE_STOP / MA20_STOP / TIME_STOP_3MIN / TIMEOUT_10AM
                "action": str,         # SELL_ALL / HOLD
                "priority": int | None,
                "reason": str,
            }
        """
        # 우선순위 1: 비상 청산
        if self.check_emergency(kospi_change):
            reason = f"코스피 {kospi_change:+.1f}% — 비상 청산"
            logger.warning(f"[STOP] 비상 청산 발동: {reason}")
            return {
                "trigger": True, "type": "EMERGENCY",
                "action": "SELL_ALL", "priority": 1, "reason": reason,
            }

        # 우선순위 2: 가격 손절
        if self.check_price_stop(entry_price, current_price, quantity):
            loss_pct = (current_price - entry_price) / entry_price * 100
            reason = f"진입가 대비 {loss_pct:+.2f}% 손실 — 가격 손절"
            logger.warning(f"[STOP] 가격 손절 발동: {reason}")
            return {
                "trigger": True, "type": "PRICE_STOP",
                "action": "SELL_ALL", "priority": 2, "reason": reason,
            }

        # 우선순위 3: 20일선 이탈
        if self.check_ma20_stop(current_price, ma20):
            reason = f"현재가 {current_price:,} < 20MA {ma20:,.0f} — 20일선 이탈"
            logger.warning(f"[STOP] 20일선 손절 발동: {reason}")
            return {
                "trigger": True, "type": "MA20_STOP",
                "action": "SELL_ALL", "priority": 3, "reason": reason,
            }

        # 우선순위 4: 시간 손절 (3분)
        if self.check_time_stop(current_time, open_price, current_price):
            reason = f"{current_time} 시초가 미돌파 — 3분 시간 손절"
            logger.warning(f"[STOP] 시간 손절 발동: {reason}")
            return {
                "trigger": True, "type": "TIME_STOP_3MIN",
                "action": "SELL_ALL", "priority": 4, "reason": reason,
            }

        # 우선순위 5: 10시 강제 청산
        if self.check_timeout(current_time):
            reason = "10:00 도달 — 강제 청산 (예외 없음)"
            logger.warning(f"[STOP] 강제 청산 발동: {reason}")
            return {
                "trigger": True, "type": "TIMEOUT_10AM",
                "action": "SELL_ALL", "priority": 5, "reason": reason,
            }

        return {
            "trigger": False, "type": None,
            "action": "HOLD", "priority": None, "reason": "",
        }

    def evaluate_all_positions(
        self,
        holdings: list,
        current_time: str,
        kospi_change: float,
        price_data: Dict,
    ) -> list:
        """
        전체 포트폴리오 손절 평가

        Args:
            holdings: 보유 종목 리스트
            current_time: 현재 시간 (HH:MM:SS)
            kospi_change: 코스피 등락률
            price_data: {symbol: {current_price, open_price, ma20}} 시세 딕셔너리

        Returns:
            [{symbol, name, stop_result}, ...]  트리거된 종목 리스트
        """
        triggered = []

        for holding in holdings:
            symbol = holding['stock_code']
            name = holding['stock_name']
            entry_price = holding['entry_price']
            quantity = holding['quantity']

            prices = price_data.get(symbol, {})
            current_price = prices.get('current_price', entry_price)
            open_price = prices.get('open_price', current_price)
            ma20 = prices.get('ma20', 0)

            result = self.evaluate(
                entry_price=entry_price,
                current_price=current_price,
                quantity=quantity,
                current_time=current_time,
                open_price=open_price,
                kospi_change=kospi_change,
                ma20=ma20,
            )

            if result['trigger']:
                triggered.append({
                    "symbol": symbol,
                    "name": name,
                    "quantity": quantity,
                    "current_price": current_price,
                    "stop_result": result,
                })

        return triggered
