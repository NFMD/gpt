"""
Tug of War 분석 모듈 (v2.0) — LOGIC 1
투자자 이질성(기관 vs 개인)의 매매 시간대 차이에서 발생하는 가격 괴리를 분석합니다.

수익원천: 기관은 장 마감 MOC에 유동성을 활용해 거래,
          개인은 장 초반 심리적 매매 집중
          → 장중 가격 억눌림이 있었으나 모멘텀이 살아있는 종목을
          장 마감 직전 매수 → 익일 시초가 매도

통계적 근거: 모멘텀 수익의 거의 100%가 밤사이 축적 (S&P 500 30년 데이터)
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TugOfWarResult:
    """LOGIC 1 Tug of War 점수 결과"""
    symbol: str
    name: str
    score: float                      # 0~100
    intraday_return: float = 0.0      # 장중 수익률 (%)
    overnight_return_5d: float = 0.0  # 5일 평균 오버나이트 수익률
    foreign_net_buy: int = 0          # 외국인 순매수
    institution_net_buy: int = 0      # 기관 순매수
    individual_ratio: float = 0.0    # 개인 투자자 비중 (RTP)
    momentum_alive: bool = False      # 모멘텀 생존 여부
    is_negative_intraday: bool = False  # 장중 음수 수익률 여부
    details: Dict = field(default_factory=dict)


class TugOfWarAnalyzer:
    """Tug of War 분석기 (v2.0) — LOGIC 1"""

    def __init__(self):
        logger.info("[LOGIC1] TugOfWarAnalyzer (v2.0) 초기화 완료")

    def calculate_score(
        self,
        symbol: str,
        name: str,
        open_price: float,
        current_price: float,
        close_price_yesterday: float,
        high_price: float,
        foreign_net_buy: int,
        institution_net_buy: int,
        individual_net_buy: int,
        is_new_high_20d: bool = False,
        is_ma_aligned: bool = False,
        overnight_returns_5d: Optional[List[float]] = None,
        trading_value: float = 0,
    ) -> TugOfWarResult:
        """
        LOGIC 1 Tug of War 점수 산출

        점수 구성 (0~100):
        - 장중 수익률 패턴 (Negative Intraday Return): 0~25
        - 모멘텀 생존 확인 (신고가/정배열): 0~25
        - 수급 줄다리기 (외국인+기관 vs 개인): 0~25
        - 과거 오버나이트 수익률 패턴: 0~25
        """
        score = 0.0

        # 장중 수익률 계산
        intraday_return = ((current_price - open_price) / open_price * 100
                           if open_price > 0 else 0)
        is_negative_intraday = intraday_return < 0

        # 오버나이트 평균
        overnight_5d = overnight_returns_5d or []
        avg_overnight = sum(overnight_5d) / len(overnight_5d) if overnight_5d else 0

        # 개인 투자자 비중 추정
        total_abs = abs(foreign_net_buy) + abs(institution_net_buy) + abs(individual_net_buy)
        individual_ratio = (abs(individual_net_buy) / total_abs * 100
                            if total_abs > 0 else 0)

        # 모멘텀 생존
        momentum_alive = is_new_high_20d or is_ma_aligned

        # ── 1. 장중 수익률 패턴 (0~25) ──
        # Negative Intraday Return + 전체 등락률 양수 = 이상적
        day_return = ((current_price - close_price_yesterday) / close_price_yesterday * 100
                      if close_price_yesterday > 0 else 0)

        if is_negative_intraday and day_return > 0:
            # 장중 음수이지만 전일대비 양수 → 갭 상승 후 눌림 = 이상적
            score += 25.0
        elif is_negative_intraday and day_return > -1:
            score += 18.0
        elif day_return > 2:
            # 장중 양수이더라도 강한 상승 모멘텀
            score += 12.0
        elif day_return > 0:
            score += 6.0

        # ── 2. 모멘텀 생존 확인 (0~25) ──
        if is_new_high_20d and is_ma_aligned:
            score += 25.0
        elif is_new_high_20d:
            score += 18.0
        elif is_ma_aligned:
            score += 12.0

        # 고가 근접 여부 (현재가 >= 고가 * 97%)
        if high_price > 0 and current_price >= high_price * 0.97:
            score += 5.0  # 보너스

        # ── 3. 수급 줄다리기 (0~25) ──
        fi_net = foreign_net_buy + institution_net_buy  # 외국인+기관 합산

        if fi_net > 0 and individual_net_buy < 0:
            # 외국인+기관 매수 vs 개인 매도 → 이상적 수급 패턴
            score += 25.0
        elif fi_net > 0:
            # 외국인+기관 순매수
            score += 15.0
        elif foreign_net_buy > 0 or institution_net_buy > 0:
            # 둘 중 하나만 순매수
            score += 8.0

        # 개인 비중 높으면 오버나이트 프리미엄 가능성 ↑
        if individual_ratio >= 60:
            score += 3.0  # 보너스

        # ── 4. 과거 오버나이트 수익률 패턴 (0~25) ──
        if avg_overnight >= 1.0:
            score += 25.0
        elif avg_overnight >= 0.5:
            score += 18.0
        elif avg_overnight >= 0.2:
            score += 10.0
        elif avg_overnight > 0:
            score += 5.0

        score = max(0.0, min(100.0, score))

        result = TugOfWarResult(
            symbol=symbol,
            name=name,
            score=round(score, 1),
            intraday_return=round(intraday_return, 2),
            overnight_return_5d=round(avg_overnight, 2),
            foreign_net_buy=foreign_net_buy,
            institution_net_buy=institution_net_buy,
            individual_ratio=round(individual_ratio, 1),
            momentum_alive=momentum_alive,
            is_negative_intraday=is_negative_intraday,
            details={
                "day_return": round(day_return, 2),
                "fi_net": fi_net,
                "individual_net": individual_net_buy,
            },
        )

        logger.info(
            f"[LOGIC1] {name}({symbol}) | "
            f"점수={score:.1f} | "
            f"장중={intraday_return:+.2f}% | "
            f"5일ON={avg_overnight:+.2f}% | "
            f"외기순매수={fi_net:+,} | "
            f"모멘텀={'O' if momentum_alive else 'X'}"
        )

        return result
