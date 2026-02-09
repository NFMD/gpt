"""
MOC Imbalance 분석 모듈 (v2.0) — LOGIC 3
장 마감 동시호가에서 발생하는 매수/매도 불균형의 일시적 가격 왜곡을 분석합니다.

수익원천: MOC 매도 잔량 >> 매수 잔량인데 주가가 지지되면
          → 밤사이 본래 가치 회복 (Reversal)

역설적 호가창: 매도잔량:매수잔량 >= 2:1 상태에서 주가 지지 시 강한 매수 신호
"""
import logging
from typing import Dict, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MOCImbalanceResult:
    """LOGIC 3 MOC Imbalance 점수 결과"""
    symbol: str
    name: str
    score: float                       # 0~100
    sell_order_qty: int = 0            # 매도 잔량
    buy_order_qty: int = 0             # 매수 잔량
    imbalance_ratio: float = 0.0       # 매도/매수 비율
    is_paradoxical: bool = False       # 역설적 호가창 여부
    expected_price_trend: str = ""     # 예상체결가 추이
    price_holding: bool = False        # 주가 지지 여부
    details: Dict = None


class MOCImbalanceAnalyzer:
    """MOC Imbalance 분석기 (v2.0) — LOGIC 3"""

    def __init__(self):
        # 역설적 호가창 임계값
        self.paradox_ratio = 2.0       # 매도잔량:매수잔량 >= 2:1
        self.strong_paradox_ratio = 3.0  # 강한 역설 기준
        logger.info("[LOGIC3] MOCImbalanceAnalyzer (v2.0) 초기화 완료")

    def calculate_score(
        self,
        symbol: str,
        name: str,
        sell_order_qty: int,
        buy_order_qty: int,
        current_price: float,
        expected_close_price: float,
        price_at_1520: float,
        buy_order_surge: bool = False,
        expected_price_rising: bool = False,
    ) -> MOCImbalanceResult:
        """
        LOGIC 3 MOC Imbalance 점수 산출

        점수 구성 (0~100):
        - 역설적 호가창 감지: 0~35
        - 예상체결가 상승 추이: 0~25
        - 동시호가 매수 주문 급증: 0~20
        - 주가 지지력 확인: 0~20

        Args:
            sell_order_qty: 총 매도 잔량
            buy_order_qty: 총 매수 잔량
            current_price: 현재가
            expected_close_price: 예상체결가
            price_at_1520: 15:20 시점 가격
            buy_order_surge: 동시호가 매수 주문 급증 여부
            expected_price_rising: 예상체결가 상승 추이 여부
        """
        score = 0.0
        is_paradoxical = False
        price_holding = False

        # 매도/매수 불균형 비율
        imbalance_ratio = (sell_order_qty / buy_order_qty) if buy_order_qty > 0 else 0.0

        # ── 1. 역설적 호가창 감지 (0~35) ──
        if imbalance_ratio >= self.strong_paradox_ratio:
            # 매도잔량이 3배 이상인데 주가 지지 → 매우 강한 신호
            if current_price >= price_at_1520 * 0.995:  # 0.5% 이내 지지
                score += 35.0
                is_paradoxical = True
        elif imbalance_ratio >= self.paradox_ratio:
            # 매도잔량이 2배 이상인데 주가 지지 → 강한 신호
            if current_price >= price_at_1520 * 0.995:
                score += 25.0
                is_paradoxical = True
        elif imbalance_ratio >= 1.5:
            if current_price >= price_at_1520 * 0.997:
                score += 15.0

        # ── 2. 예상체결가 상승 추이 (0~25) ──
        if expected_price_rising:
            price_diff_pct = ((expected_close_price - current_price) / current_price * 100
                              if current_price > 0 else 0)
            if price_diff_pct > 0.5:
                score += 25.0
            elif price_diff_pct > 0.2:
                score += 15.0
            elif price_diff_pct > 0:
                score += 8.0

        # ── 3. 동시호가 매수 주문 급증 (0~20) ──
        if buy_order_surge:
            score += 20.0

        # ── 4. 주가 지지력 (0~20) ──
        if price_at_1520 > 0:
            price_change = (current_price - price_at_1520) / price_at_1520 * 100
            if price_change >= 0.3:
                score += 20.0
                price_holding = True
            elif price_change >= 0:
                score += 12.0
                price_holding = True
            elif price_change >= -0.3:
                score += 5.0

        score = max(0.0, min(100.0, score))

        result = MOCImbalanceResult(
            symbol=symbol,
            name=name,
            score=round(score, 1),
            sell_order_qty=sell_order_qty,
            buy_order_qty=buy_order_qty,
            imbalance_ratio=round(imbalance_ratio, 2),
            is_paradoxical=is_paradoxical,
            expected_price_trend="RISING" if expected_price_rising else "FLAT",
            price_holding=price_holding,
            details={
                "paradox_score": min(35, score),
                "imbalance_ratio": round(imbalance_ratio, 2),
                "buy_surge": buy_order_surge,
            },
        )

        logger.info(
            f"[LOGIC3] {name}({symbol}) | "
            f"점수={score:.1f} | "
            f"매도:매수={imbalance_ratio:.1f}:1 | "
            f"역설={is_paradoxical} | "
            f"지지={price_holding} | "
            f"예상추이={'상승' if expected_price_rising else '횡보'}"
        )

        return result
