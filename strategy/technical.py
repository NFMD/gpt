"""
기술적 분석 모듈 (v2.0)
PHASE 2: 기술적 검증 (점수제)를 구현합니다.

~50개 → ~10개로 축소 (기술적 우위 확인)
"차트의 위치가 맞는가?"

v2.0 변경사항:
- TechnicalData 데이터클래스 도입
- SHOULD 3개 (S1~S3) + BONUS 5개 (B1~B5) 완전 구현
- B3 장대양봉, B4 위꼬리 짧음, B5 눌림목 패턴 추가
- 상세 결과 딕셔너리 반환
- 최대 점수: 85점
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════

@dataclass
class TechnicalData:
    """기술적 분석에 필요한 데이터"""
    symbol: str
    price: float                # 현재가
    high: float                 # 당일 고가
    low: float                  # 당일 저가
    open_price: float           # 시가
    close: float                # (예상) 종가

    high_20d: float             # 20일 최고가
    high_all_time: float = 0.0  # 역사적 최고가

    ma5: float = 0.0            # 5일 이동평균
    ma20: float = 0.0           # 20일 이동평균
    ma60: float = 0.0           # 60일 이동평균

    volume: int = 0             # 당일 거래량
    volume_20d_avg: int = 0     # 20일 평균 거래량

    theme_stocks_rising: int = 0  # 동일 테마 내 +3%↑ 종목 수

    # 눌림목 패턴 관련
    prev_days_declining: int = 0  # 직전 연속 하락(조정) 일수
    above_ma5: bool = False       # 5일선 위 여부
    volume_vs_prev: float = 1.0   # 전일 대비 거래량 비율


# ═══════════════════════════════════════════════════════
# PHASE 2 점수 산출
# ═══════════════════════════════════════════════════════

def phase2_score(data: TechnicalData) -> Tuple[bool, int, dict]:
    """
    PHASE 2: 기술적 검증 (점수제)

    SHOULD (3개 중 2개↑ 필수):
      S1: 20일 신고가 (20점)
      S2: 이평선 정배열 5MA>20MA>60MA (15점)
      S3: 당일 고가 근접 현재가>=고가*0.97 (15점)

    BONUS:
      B1: 거래량 폭증 당일>=20일평균*3 (10점)
      B2: 섹터 동반 상승 테마4종목↑ (10점)
      B3: 장대양봉 몸통>=3% (5점)
      B4: 위꼬리 짧음 위꼬리/몸통<=0.3 (5점)
      B5: 눌림목 패턴 2~3일조정+5일선지지+거래량급감 (5점)

    통과 기준: SHOULD 2개↑ 충족 AND 35점↑
    최대 점수: 85점

    Returns:
        (통과 여부, 총점, 상세 결과)
    """
    score = 0
    should_count = 0
    details = {}

    # ═══ SHOULD 조건 (3개 중 2개↑ 필수) ═══

    # S1: 20일 신고가
    s1 = data.high >= data.high_20d if data.high_20d > 0 else False
    if s1:
        score += 20
        should_count += 1
    details["S1_new_high_20d"] = {"pass": s1, "score": 20 if s1 else 0}

    # S2: 이평선 정배열
    s2 = (data.ma5 > data.ma20 > data.ma60) and data.ma60 > 0
    if s2:
        score += 15
        should_count += 1
    details["S2_ma_aligned"] = {"pass": s2, "score": 15 if s2 else 0}

    # S3: 당일 고가 근접
    s3 = data.price >= data.high * 0.97 if data.high > 0 else False
    if s3:
        score += 15
        should_count += 1
    details["S3_near_high"] = {"pass": s3, "score": 15 if s3 else 0}

    # ── SHOULD 미충족 시 탈락 ──
    if should_count < 2:
        details["should_count"] = should_count
        return False, score, details

    # ═══ BONUS 조건 ═══

    # B1: 거래량 폭증
    b1 = data.volume >= data.volume_20d_avg * 3 if data.volume_20d_avg > 0 else False
    if b1:
        score += 10
    details["B1_volume_surge"] = {"pass": b1, "score": 10 if b1 else 0}

    # B2: 섹터 동반 상승
    b2 = data.theme_stocks_rising >= 4
    if b2:
        score += 10
    details["B2_sector_sync"] = {"pass": b2, "score": 10 if b2 else 0}

    # B3: 장대양봉 (몸통 3%↑)
    body_pct = abs(data.close - data.open_price) / data.open_price if data.open_price > 0 else 0
    b3 = body_pct >= 0.03 and data.close > data.open_price
    if b3:
        score += 5
    details["B3_large_candle"] = {"pass": b3, "score": 5 if b3 else 0, "body_pct": round(body_pct * 100, 2)}

    # B4: 위꼬리 짧음
    body_size = abs(data.close - data.open_price)
    upper_wick = data.high - max(data.close, data.open_price)
    b4 = (upper_wick / body_size <= 0.3) if body_size > 0 else False
    if b4:
        score += 5
    details["B4_clean_candle"] = {"pass": b4, "score": 5 if b4 else 0}

    # B5: 눌림목 패턴 (2~3일 조정 + 5일선 지지 + 거래량 급감)
    b5 = (
        2 <= data.prev_days_declining <= 3
        and data.above_ma5
        and data.volume_vs_prev < 0.5
    )
    if b5:
        score += 5
    details["B5_pullback"] = {"pass": b5, "score": 5 if b5 else 0}

    details["should_count"] = should_count
    passed = score >= Config.PHASE2_MIN_SCORE
    return passed, score, details


# ═══════════════════════════════════════════════════════
# TechnicalAnalyzer 클래스 (API 연동)
# ═══════════════════════════════════════════════════════

class TechnicalAnalyzer:
    """기술적 분석기 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api
        logger.info("[PHASE2] TechnicalAnalyzer (v2.0) 초기화 완료")

    def build_technical_data(self, stock: Dict) -> TechnicalData:
        """API 응답으로부터 TechnicalData 구성"""
        stock_code = stock.get('stock_code', '')
        current_price = stock.get('current_price', 0)
        high_price = stock.get('high_price', 0)
        low_price = stock.get('low_price', 0)
        open_price = stock.get('open_price', 0)
        volume = stock.get('volume', 0)

        # 일봉 데이터 조회
        price_history = self.api.get_daily_price_history(stock_code, 60)

        high_20d = 0.0
        ma5 = ma20 = ma60 = 0.0
        volume_20d_avg = 0
        prev_days_declining = 0
        above_ma5 = False
        volume_vs_prev = 1.0

        if price_history and len(price_history) >= 5:
            closes = [p['close'] for p in price_history]
            highs = [p['high'] for p in price_history]
            volumes = [p['volume'] for p in price_history]

            # 20일 최고가
            if len(highs) >= 20:
                high_20d = max(highs[1:21])  # 전일부터 20일
            else:
                high_20d = max(highs[1:]) if len(highs) > 1 else high_price

            # 이동평균
            ma5 = float(np.mean(closes[:5]))
            if len(closes) >= 20:
                ma20 = float(np.mean(closes[:20]))
            if len(closes) >= 60:
                ma60 = float(np.mean(closes[:60]))

            # 20일 평균 거래량
            if len(volumes) >= 21:
                volume_20d_avg = int(np.mean(volumes[1:21]))
            elif len(volumes) >= 2:
                volume_20d_avg = int(np.mean(volumes[1:]))

            # 눌림목: 직전 연속 하락 일수
            for i in range(1, min(5, len(closes))):
                if i + 1 < len(closes) and closes[i] < closes[i + 1]:
                    prev_days_declining += 1
                else:
                    break

            # 5일선 위 여부
            above_ma5 = current_price > ma5 if ma5 > 0 else False

            # 전일 대비 거래량 비율
            if len(volumes) >= 2 and volumes[1] > 0:
                volume_vs_prev = volume / volumes[1] if volume > 0 else 0

        return TechnicalData(
            symbol=stock_code,
            price=current_price,
            high=high_price,
            low=low_price,
            open_price=open_price,
            close=current_price,  # 장중에는 현재가를 예상 종가로 사용
            high_20d=high_20d,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            volume=volume,
            volume_20d_avg=volume_20d_avg,
            theme_stocks_rising=stock.get('theme_stocks_rising', 0),
            prev_days_declining=prev_days_declining,
            above_ma5=above_ma5,
            volume_vs_prev=volume_vs_prev,
        )

    def analyze_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """후보 종목들에 대해 PHASE 2 분석 수행 (v2.0)"""
        logger.info("=" * 60)
        logger.info("[PHASE2] 기술적 검증 시작 (v2.0)")
        logger.info("=" * 60)

        passed_stocks = []
        for stock in candidates:
            tech_data = self.build_technical_data(stock)
            is_passed, score, details = phase2_score(tech_data)

            stock['phase2_score'] = score
            stock['phase2_details'] = details
            stock['technical_data'] = tech_data

            # MA 정보 주입 (후속 PHASE에서 사용)
            stock['ma5'] = tech_data.ma5
            stock['ma20'] = tech_data.ma20
            stock['ma60'] = tech_data.ma60
            stock['is_new_high'] = details.get('S1_new_high_20d', {}).get('pass', False)
            stock['is_aligned'] = details.get('S2_ma_aligned', {}).get('pass', False)

            if is_passed:
                passed_stocks.append(stock)
                logger.info(
                    f"  [PASS] {stock.get('stock_name', '')} | "
                    f"점수: {score} | SHOULD: {details.get('should_count', 0)}/3"
                )
            else:
                logger.debug(
                    f"  [FAIL] {stock.get('stock_name', '')} | "
                    f"점수: {score} | SHOULD: {details.get('should_count', 0)}/3"
                )

        logger.info(f"[PHASE2] 통과: {len(passed_stocks)}/{len(candidates)}개")
        return sorted(passed_stocks, key=lambda x: x['phase2_score'], reverse=True)
