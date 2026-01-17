"""
장중 분봉 분석 모듈
15:00-15:20 구간에서 V자 반등 패턴을 포착하고 최적 진입 타점을 찾습니다.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from api import KISApi


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntradayAnalyzer:
    """장중 실시간 분봉 분석기"""

    def __init__(self, api: KISApi):
        self.api = api

    def get_closing_period_data(
        self,
        stock_code: str,
        interval: int = 1
    ) -> List[Dict]:
        """
        종가 베팅 구간(15:00-15:20) 분봉 데이터 조회

        Args:
            stock_code: 종목코드
            interval: 분봉 간격 (1분 권장)

        Returns:
            분봉 데이터 리스트
        """
        # 최근 30개 분봉 조회 (15:00 이전 포함)
        minute_data = self.api.get_minute_price_history(
            stock_code=stock_code,
            interval=interval,
            count=30
        )

        if not minute_data:
            logger.warning(f"⚠️  {stock_code}: 분봉 데이터 조회 실패")
            return []

        # 15:00 이후 데이터만 필터링
        today = datetime.now().strftime("%Y%m%d")
        closing_period_start = today + "150000"

        filtered_data = [
            candle for candle in minute_data
            if candle['time'] >= closing_period_start
        ]

        logger.info(f"📊 {stock_code}: 종가 구간 {len(filtered_data)}개 분봉 확보")

        return filtered_data

    def detect_v_reversal(
        self,
        minute_data: List[Dict],
        min_drop_percent: float = 1.0,
        min_rebound_percent: float = 0.5
    ) -> Optional[Dict]:
        """
        V자 반등 패턴 감지

        패턴 정의:
        1. 고점에서 급격한 하락 (투매)
        2. 저점 형성
        3. 저점에서 빠른 반등 (매수세 유입)

        Args:
            minute_data: 분봉 데이터 (시간순 정렬)
            min_drop_percent: 최소 하락률 (%)
            min_rebound_percent: 최소 반등률 (%)

        Returns:
            V자 반등 정보 또는 None
        """
        if len(minute_data) < 5:
            return None

        # 최근 데이터가 앞에 오도록 정렬되어 있다고 가정
        # 역순으로 분석 (과거 → 현재)
        candles = list(reversed(minute_data))

        # 1. 고점 찾기 (최근 10분봉 내)
        recent_candles = candles[-10:] if len(candles) >= 10 else candles
        high_point = max(recent_candles, key=lambda x: x['high'])
        high_price = high_point['high']
        high_idx = candles.index(high_point)

        # 2. 저점 찾기 (고점 이후)
        if high_idx >= len(candles) - 2:  # 고점이 너무 최근이면 패턴 미형성
            return None

        candles_after_high = candles[high_idx + 1:]
        if not candles_after_high:
            return None

        low_point = min(candles_after_high, key=lambda x: x['low'])
        low_price = low_point['low']
        low_idx = candles.index(low_point)

        # 3. 현재가 (최신 봉)
        current_candle = candles[-1]
        current_price = current_candle['close']

        # 4. 하락률 계산
        drop_percent = ((high_price - low_price) / high_price) * 100

        # 5. 반등률 계산
        rebound_percent = ((current_price - low_price) / low_price) * 100

        # 6. V자 패턴 조건 체크
        is_v_pattern = (
            drop_percent >= min_drop_percent and
            rebound_percent >= min_rebound_percent and
            low_idx < len(candles) - 1  # 저점이 최신봉이 아님 (이미 반등 시작)
        )

        if is_v_pattern:
            logger.info(
                f"✅ V자 반등 감지!\n"
                f"   고점: {high_price:,}원 → 저점: {low_price:,}원 → 현재: {current_price:,}원\n"
                f"   하락: {drop_percent:.2f}% | 반등: {rebound_percent:.2f}%\n"
                f"   저점 시각: {low_point['time']}"
            )

            return {
                "high_price": high_price,
                "low_price": low_price,
                "current_price": current_price,
                "drop_percent": drop_percent,
                "rebound_percent": rebound_percent,
                "low_time": low_point['time'],
                "pattern_strength": min(drop_percent, rebound_percent),  # 약한 쪽 기준
            }
        else:
            logger.debug(
                f"❌ V자 패턴 미감지 (하락: {drop_percent:.2f}%, 반등: {rebound_percent:.2f}%)"
            )
            return None

    def calculate_momentum(self, minute_data: List[Dict]) -> float:
        """
        모멘텀 계산 (체결강도 대용)

        최근 N개 봉의 거래량 가중 가격 변화율

        Args:
            minute_data: 분봉 데이터

        Returns:
            모멘텀 점수 (-100 ~ 100)
        """
        if len(minute_data) < 3:
            return 0.0

        # 최근 5개 봉 사용
        recent_candles = minute_data[:5]

        total_volume = sum(c['volume'] for c in recent_candles)
        if total_volume == 0:
            return 0.0

        # 거래량 가중 평균 가격 변화
        weighted_change = 0.0
        for candle in recent_candles:
            price_change = ((candle['close'] - candle['open']) / candle['open']) * 100
            weight = candle['volume'] / total_volume
            weighted_change += price_change * weight

        # -100 ~ 100 범위로 클리핑
        momentum = max(min(weighted_change * 10, 100), -100)

        return momentum

    def analyze_buying_pressure(self, minute_data: List[Dict]) -> Dict:
        """
        매수세 분석

        Args:
            minute_data: 분봉 데이터

        Returns:
            매수세 분석 결과
        """
        if len(minute_data) < 5:
            return {
                "buying_pressure": 0.0,
                "volume_surge": False,
                "price_support": False,
            }

        recent_5 = minute_data[:5]
        previous_5 = minute_data[5:10] if len(minute_data) >= 10 else recent_5

        # 1. 거래량 증가 체크
        recent_avg_volume = np.mean([c['volume'] for c in recent_5])
        previous_avg_volume = np.mean([c['volume'] for c in previous_5])

        volume_surge = recent_avg_volume > previous_avg_volume * 1.5

        # 2. 가격 지지 체크 (저점 상승)
        recent_lows = [c['low'] for c in recent_5]
        price_support = all(recent_lows[i] <= recent_lows[i + 1] for i in range(len(recent_lows) - 1))

        # 3. 매수세 점수 (양봉 비율)
        bullish_count = sum(1 for c in recent_5 if c['close'] >= c['open'])
        buying_pressure = (bullish_count / len(recent_5)) * 100

        logger.info(
            f"매수세 분석: {buying_pressure:.0f}% | "
            f"거래량 급증: {'✅' if volume_surge else '❌'} | "
            f"저점 지지: {'✅' if price_support else '❌'}"
        )

        return {
            "buying_pressure": buying_pressure,
            "volume_surge": volume_surge,
            "price_support": price_support,
        }

    def get_entry_signal(
        self,
        stock_code: str,
        stock_name: str = ""
    ) -> Optional[Dict]:
        """
        최적 진입 신호 생성

        15:00-15:20 구간에서 V자 반등 + 매수세 확인 시 진입 신호

        Args:
            stock_code: 종목코드
            stock_name: 종목명

        Returns:
            진입 신호 정보 또는 None
        """
        logger.info(f"🔍 {stock_name} ({stock_code}) 장중 분석 중...")

        # 1. 분봉 데이터 조회
        minute_data = self.get_closing_period_data(stock_code, interval=1)

        if not minute_data:
            return None

        # 2. V자 반등 감지
        v_pattern = self.detect_v_reversal(minute_data)

        # 3. 모멘텀 계산
        momentum = self.calculate_momentum(minute_data)

        # 4. 매수세 분석
        buying_analysis = self.analyze_buying_pressure(minute_data)

        # 5. 종합 판단
        signal_strength = 0

        if v_pattern:
            signal_strength += 50  # V자 반등 확인
            signal_strength += min(v_pattern['pattern_strength'], 30)  # 패턴 강도

        if buying_analysis['buying_pressure'] >= 60:
            signal_strength += 20  # 매수세 강함

        if buying_analysis['volume_surge']:
            signal_strength += 10  # 거래량 급증

        if buying_analysis['price_support']:
            signal_strength += 10  # 저점 지지

        if momentum > 20:
            signal_strength += 10  # 양의 모멘텀

        # 6. 진입 신호 생성 (70점 이상)
        if signal_strength >= 70:
            current_price = minute_data[0]['close']

            logger.info("=" * 60)
            logger.info(f"🎯 진입 신호 발생! ({stock_name})")
            logger.info("=" * 60)
            logger.info(f"신호 강도: {signal_strength}/100")
            logger.info(f"현재가: {current_price:,}원")
            if v_pattern:
                logger.info(
                    f"V자 반등: {v_pattern['low_price']:,}원 → {current_price:,}원 "
                    f"(+{v_pattern['rebound_percent']:.2f}%)"
                )
            logger.info(f"모멘텀: {momentum:.1f}")
            logger.info(f"매수세: {buying_analysis['buying_pressure']:.0f}%")
            logger.info("=" * 60)

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "signal_strength": signal_strength,
                "entry_price": current_price,
                "v_pattern": v_pattern,
                "momentum": momentum,
                "buying_analysis": buying_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            logger.info(
                f"⏸️  {stock_name}: 진입 조건 미달 (신호 강도: {signal_strength}/100)"
            )
            return None
