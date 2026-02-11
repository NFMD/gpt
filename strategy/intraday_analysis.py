"""
장중 분봉 분석 모듈 (v2.0)
PHASE 4: V자 반등 패턴 감지 (MUST 5조건 + BONUS 5조건)를 구현합니다.

핵심 시간대: 15:16~15:19:30 (수급 역전 포착 구간)

v2.0 변경사항:
- RealtimeData 데이터클래스 도입
- detect_v_pattern: MUST 5조건 + BONUS 5조건 완전 구현
  B4: 480분 이평선 지지 후 양봉
  B5: 직전 5분 거래량 증가
- calculate_logic_scores: 4가지 로직 개별 점수 산출
- determine_entry_weight: 앙상블+레짐+켈리 기반 진입 비중
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════

@dataclass
class RealtimeData:
    """V자 반등 감지에 필요한 실시간 데이터"""
    symbol: str
    current_price: float
    low_since_1500: float          # 15:00 이후 최저가

    # 1분봉 이동평균선
    ma5_1min: float                # 1분봉 5이평선
    ma20_1min: float               # 1분봉 20이평선
    ma480_1min: Optional[float] = None  # 1분봉 480이평선 (장기)

    # 체결강도
    execution_strength: float = 0.0       # 현재 체결강도
    prev_execution_strength: float = 0.0  # 직전 체결강도

    # 프로그램 매매
    program_net_buy_3min: float = 0.0     # 최근 3분간 프로그램 순매수 변화

    # 호가창
    sell_order_qty: int = 0               # 매도 잔량 합계
    buy_order_qty: int = 0                # 매수 잔량 합계

    # 거래량
    volume_last_5min: int = 0             # 직전 5분 거래량
    volume_prev_5min: int = 0             # 그 전 5분 거래량


# ═══════════════════════════════════════════════════════
# V자 반등 감지 함수
# ═══════════════════════════════════════════════════════

def detect_v_pattern(data: RealtimeData) -> Tuple[bool, int, dict]:
    """
    V자 반등 패턴 감지

    MUST (ALL AND — 기본 50점):
      M1: 시간 15:16:00~15:19:30
      M2: 저점 대비 반등 >=0.5%
      M3: 1분봉 5MA 돌파
      M4: 체결강도 >=100% AND 직전 대비 상승
      M5: 프로그램 순매수 3분간 증가

    BONUS:
      B1: 체결강도 150%↑ (+10)
      B2: 역설적 호가창 매도잔량>=매수*1.5 (+10)
      B3: 1분봉 20MA 돌파 (+5)
      B4: 480분 이평선 지지 후 양봉 (+5)
      B5: 직전 5분 거래량 증가 >=1.5배 (+5)

    최대 점수: 85점 (50 기본 + 35 보너스)

    Returns:
        (신호 발생 여부, 점수, 상세 결과)
    """
    now = datetime.now().strftime('%H:%M:%S')
    details = {}

    # ═══ MUST 조건 (하나라도 실패 시 False) ═══

    # M1: 시간 조건
    if not (Config.V_TIME_START <= now <= Config.V_TIME_END):
        return False, 0, {"reason": f"시간 범위 밖 ({now})"}

    price = data.current_price

    # M2: 저점 대비 0.5%↑ 반등
    m2 = price > data.low_since_1500 * 1.005 if data.low_since_1500 > 0 else False
    rebound_pct = (
        (price - data.low_since_1500) / data.low_since_1500 * 100
        if data.low_since_1500 > 0 else 0
    )
    details["M2_rebound"] = {
        "pass": m2,
        "rebound_pct": round(rebound_pct, 2),
        "low_since_1500": data.low_since_1500,
    }
    if not m2:
        return False, 0, details

    # M3: 1분봉 5MA 돌파
    m3 = price > data.ma5_1min if data.ma5_1min > 0 else False
    details["M3_ma5_break"] = {
        "pass": m3,
        "price": price,
        "ma5_1min": data.ma5_1min,
    }
    if not m3:
        return False, 0, details

    # M4: 체결강도 100%↑ + 상승세
    m4 = (
        data.execution_strength >= 100
        and data.execution_strength > data.prev_execution_strength
    )
    details["M4_exec_strength"] = {
        "pass": m4,
        "current": data.execution_strength,
        "prev": data.prev_execution_strength,
    }
    if not m4:
        return False, 0, details

    # M5: 프로그램 순매수 전환
    m5 = data.program_net_buy_3min > 0
    details["M5_program_net"] = {
        "pass": m5,
        "net_buy_3min": data.program_net_buy_3min,
    }
    if not m5:
        return False, 0, details

    # ═══ 기본 점수 50점 (MUST 모두 충족) ═══
    score = 50

    # ═══ BONUS 조건 ═══

    # B1: 체결강도 150%↑
    b1 = data.execution_strength >= 150
    if b1:
        score += 10
    details["B1_exec_150"] = {"pass": b1, "score": 10 if b1 else 0}

    # B2: 역설적 호가창 (매도잔량 >= 매수잔량 * 1.5)
    b2 = (
        data.buy_order_qty > 0
        and data.sell_order_qty >= data.buy_order_qty * 1.5
    )
    if b2:
        score += 10
    ratio = data.sell_order_qty / data.buy_order_qty if data.buy_order_qty > 0 else 0
    details["B2_paradox_book"] = {
        "pass": b2,
        "sell_buy_ratio": round(ratio, 2),
        "score": 10 if b2 else 0,
    }

    # B3: 1분봉 20MA 돌파
    b3 = data.ma20_1min > 0 and price > data.ma20_1min
    if b3:
        score += 5
    details["B3_ma20_break"] = {"pass": b3, "score": 5 if b3 else 0}

    # B4: 480분 이평선 지지 후 양봉
    b4 = False
    if data.ma480_1min and data.ma480_1min > 0:
        b4 = (
            data.low_since_1500 <= data.ma480_1min * 1.005
            and price > data.ma480_1min
        )
    if b4:
        score += 5
    details["B4_ma480_support"] = {"pass": b4, "score": 5 if b4 else 0}

    # B5: 직전 5분 거래량 증가
    b5 = (
        data.volume_prev_5min > 0
        and data.volume_last_5min >= data.volume_prev_5min * 1.5
    )
    if b5:
        score += 5
    details["B5_volume_surge"] = {"pass": b5, "score": 5 if b5 else 0}

    logger.info(
        f"[PHASE4] {data.symbol} V자 감지! 점수={score} | "
        f"반등={rebound_pct:.2f}% | 체결강도={data.execution_strength:.0f}%"
    )

    return True, score, details


# ═══════════════════════════════════════════════════════
# 4가지 로직 개별 점수 산출
# ═══════════════════════════════════════════════════════

def calculate_logic_scores(
    change_pct: float,
    phase2_score_val: int,
    v_score: int,
    program_net_buy_3min: float,
    intraday_return_negative: bool,
    moc_buy_imbalance: bool,
    sell_order_qty: int,
    buy_order_qty: int,
    execution_strength: float,
    google_article_count: int,
    positive_ratio: float,
    power_keywords_found: List[str],
    theme_expected_days: int,
) -> dict:
    """
    4가지 로직의 개별 점수 산출 (Part 2 명세)

    Returns:
        logic1_tow, logic2_v, logic3_moc, logic4_news (각 0~100)
        + ensemble_score, dominant_logic
    """
    # ── LOGIC 1: Tug of War (투자자 이질성) ──
    logic1 = 0
    if intraday_return_negative:
        logic1 += 30                                    # 장중 억눌림
    if program_net_buy_3min > 0:
        logic1 += 35                                    # 기관 매수 전환
    if phase2_score_val >= 35:
        logic1 += 20                                    # 기술적 모멘텀 유지
    if change_pct >= 0.02:
        logic1 += 15                                    # 당일 여전히 양봉
    logic1 = min(logic1, 100)

    # ── LOGIC 2: V자 수급전환 ──
    logic2 = min(int(v_score / 75 * 100), 100)

    # ── LOGIC 3: MOC Imbalance ──
    logic3 = 0
    if moc_buy_imbalance:
        logic3 += 40                                    # MOC 매수 우위
    if buy_order_qty > 0 and sell_order_qty >= buy_order_qty * 1.5:
        logic3 += 35                                    # 역설적 호가창
    if execution_strength >= 150:
        logic3 += 25                                    # 체결강도 극강
    logic3 = min(logic3, 100)

    # ── LOGIC 4: 뉴스 Temporal Anomaly ──
    logic4 = 0
    if google_article_count >= 30:
        logic4 += 35                                    # 보편적 관심
    elif google_article_count >= 20:
        logic4 += 20                                    # 관심 확산 중
    if positive_ratio >= 0.6:
        logic4 += 20                                    # 긍정적 감정
    if len(power_keywords_found) > 0:
        logic4 += 25                                    # 파급력 키워드
    if theme_expected_days >= 3:
        logic4 += 20                                    # 테마 지속성
    logic4 = min(logic4, 100)

    # ── 앙상블 종합 점수 ──
    weights = Config.ENSEMBLE_WEIGHTS
    ensemble = (
        logic1 * weights["tug_of_war"]
        + logic2 * weights["v_pattern"]
        + logic3 * weights["moc_imbalance"]
        + logic4 * weights["news_temporal"]
    )

    dominant = max(
        [("LOGIC_1_TOW", logic1), ("LOGIC_2_V", logic2),
         ("LOGIC_3_MOC", logic3), ("LOGIC_4_NEWS", logic4)],
        key=lambda x: x[1]
    )[0]

    return {
        "logic1_tow": logic1,
        "logic2_v": logic2,
        "logic3_moc": logic3,
        "logic4_news": logic4,
        "ensemble_score": round(ensemble, 1),
        "dominant_logic": dominant,
    }


# ═══════════════════════════════════════════════════════
# 진입 비중 결정
# ═══════════════════════════════════════════════════════

def determine_entry_weight(
    ensemble_score: float,
    regime: str,               # "NORMAL" / "CAUTION" / "DANGER"
    kelly_pct: float,          # 켈리 공식 기반 비율
    current_cash_ratio: float, # 현재 현금 비율
    position_count: int,       # 현재 보유 종목 수
) -> float:
    """
    앙상블 점수 + 레짐 + 켈리 기반 진입 비중 결정

    Returns:
        포트폴리오 내 비중 (0~30%)
    """
    # DANGER: 신규 진입 금지
    if regime == "DANGER":
        return 0.0

    # 앙상블 점수별 기본 비중
    if ensemble_score >= Config.ENSEMBLE_PRIORITY_THRESHOLD:  # 70
        base_weight = min(kelly_pct * 1.2, Config.MAX_INVESTMENT_PER_STOCK_PCT)
    elif ensemble_score >= Config.ENSEMBLE_STANDARD_THRESHOLD:  # 55
        base_weight = kelly_pct
    elif ensemble_score >= Config.ENSEMBLE_SMALL_THRESHOLD:  # 40
        base_weight = kelly_pct * 0.5
    else:
        return 0.0  # SKIP

    # CAUTION: 50% 축소
    if regime == "CAUTION":
        base_weight *= 0.5

    # 현금 비율 20% 유지 제약
    max_allowed = current_cash_ratio - Config.MIN_CASH_PCT
    base_weight = min(base_weight, max(0, max_allowed))

    # 보유 종목 수 제한
    if position_count >= Config.MAX_STOCKS:
        return 0.0

    # 최대 30% 캡
    return min(base_weight, Config.MAX_INVESTMENT_PER_STOCK_PCT)


# ═══════════════════════════════════════════════════════
# IntradayAnalyzer 클래스 (API 연동)
# ═══════════════════════════════════════════════════════

class IntradayAnalyzer:
    """장중 실시간 분봉 분석기 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api
        logger.info("[PHASE4] IntradayAnalyzer (v2.0) 초기화 완료")

    def get_realtime_data(self, stock_code: str) -> Dict:
        """실시간 분석을 위한 데이터 수집 (KIS API 활용)"""
        return self.api.get_realtime_analysis_data(stock_code)

    def build_realtime_data(self, stock_code: str, raw: Dict) -> RealtimeData:
        """API 응답 → RealtimeData 변환"""
        return RealtimeData(
            symbol=stock_code,
            current_price=raw.get('current_price', 0),
            low_since_1500=raw.get('low_since_1500', 0),
            ma5_1min=raw.get('ma5_1min', 0),
            ma20_1min=raw.get('ma20_1min', 0),
            ma480_1min=raw.get('ma480_1min'),
            execution_strength=raw.get('execution_strength', 0),
            prev_execution_strength=raw.get('prev_execution_strength', 0),
            program_net_buy_3min=raw.get('program_net_buy_3min', 0),
            sell_order_qty=raw.get('sell_order_qty', 0),
            buy_order_qty=raw.get('buy_order_qty', 0),
            volume_last_5min=raw.get('volume_last_5min', 0),
            volume_prev_5min=raw.get('volume_prev_5min', 0),
        )

    def phase4_v_pattern(self, stock_code: str, raw_data: Dict) -> Tuple[bool, int, dict]:
        """PHASE 4 V자 반등 감지 (API 연동 래퍼)"""
        rt = self.build_realtime_data(stock_code, raw_data)
        return detect_v_pattern(rt)
