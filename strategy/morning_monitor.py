"""
장 시작 모니터링 모듈
3분의 법칙과 1분봉 20분 이평선 추적으로 매도 타이밍을 결정합니다.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, time
import numpy as np
from api import KISApi


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MorningMonitor:
    """장 시작 모니터링 시스템"""

    def __init__(self, api: KISApi):
        self.api = api

    def check_three_minute_rule(
        self,
        stock_code: str,
        stock_name: str,
        opening_price: int
    ) -> Dict:
        """
        3분의 법칙 체크

        장 시작 후 3분 이내에 시초가를 돌파하는지 확인
        돌파하지 못하면 시간 손절 신호

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            opening_price: 시초가

        Returns:
            체크 결과
        """
        logger.info(f"⏰ {stock_name} 3분의 법칙 체크 중... (시초가: {opening_price:,}원)")

        # 1분봉 데이터 조회 (최근 5개)
        minute_data = self.api.get_minute_price_history(
            stock_code=stock_code,
            interval=1,
            count=5
        )

        if not minute_data or len(minute_data) < 3:
            logger.warning(f"⚠️  {stock_name}: 분봉 데이터 부족")
            return {
                "passed": False,
                "reason": "데이터 부족",
                "action": "hold",
            }

        # 장 시작 후 3분 이내 데이터 확인
        # 최근 3개 봉(0,1,2번 인덱스)이 09:00~09:03 구간
        first_three_candles = minute_data[:3]

        # 시초가 돌파 여부 확인
        breakthrough = False
        max_price = 0

        for candle in first_three_candles:
            if candle['high'] > opening_price:
                breakthrough = True
                max_price = max(max_price, candle['high'])

        if breakthrough:
            breakthrough_rate = ((max_price - opening_price) / opening_price) * 100
            logger.info(
                f"✅ {stock_name}: 3분의 법칙 통과!\n"
                f"   시초가: {opening_price:,}원 → 고점: {max_price:,}원 "
                f"(+{breakthrough_rate:.2f}%)"
            )
            return {
                "passed": True,
                "reason": "시초가 돌파",
                "action": "hold",  # 보유 유지
                "max_price": max_price,
                "breakthrough_rate": breakthrough_rate,
            }
        else:
            # 최고가
            max_price = max(candle['high'] for candle in first_three_candles)

            logger.warning(
                f"❌ {stock_name}: 3분의 법칙 실패!\n"
                f"   시초가: {opening_price:,}원 | 3분 내 최고가: {max_price:,}원\n"
                f"   → 시간 손절 신호"
            )
            return {
                "passed": False,
                "reason": "시초가 미돌파",
                "action": "sell",  # 즉시 매도
                "max_price": max_price,
            }

    def calculate_ema_20(self, prices: List[float]) -> float:
        """
        20분 지수이동평균(EMA) 계산

        Args:
            prices: 가격 리스트 (최신 → 과거 순)

        Returns:
            EMA 20 값
        """
        if len(prices) < 20:
            # 데이터 부족 시 단순 이동평균
            return np.mean(prices)

        # EMA 계산
        # EMA = (현재가 × (2 / (기간 + 1))) + (전일 EMA × (1 - (2 / (기간 + 1))))
        multiplier = 2 / (20 + 1)

        # 초기 EMA는 SMA
        ema = np.mean(prices[-20:])

        # 역순으로 계산 (과거 → 현재)
        for price in reversed(prices[-20:]):
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def check_ema_support(
        self,
        stock_code: str,
        stock_name: str,
        current_price: int
    ) -> Dict:
        """
        1분봉 20분 이평선 지지 확인

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            current_price: 현재가

        Returns:
            지지 확인 결과
        """
        # 1분봉 데이터 조회 (30개 - 여유있게)
        minute_data = self.api.get_minute_price_history(
            stock_code=stock_code,
            interval=1,
            count=30
        )

        if not minute_data or len(minute_data) < 20:
            logger.warning(f"⚠️  {stock_name}: 이평선 계산 데이터 부족")
            return {
                "supported": True,  # 데이터 부족 시 안전하게 보유
                "reason": "데이터 부족",
                "action": "hold",
            }

        # 종가 리스트 추출
        closes = [candle['close'] for candle in minute_data]

        # 20분 EMA 계산
        ema_20 = self.calculate_ema_20(closes)

        # 현재가와 EMA 비교
        distance_from_ema = ((current_price - ema_20) / ema_20) * 100

        # 이탈 기준: -1.5% 이하
        if distance_from_ema < -1.5:
            logger.warning(
                f"❌ {stock_name}: 1분봉 20분 이평선 이탈!\n"
                f"   현재가: {current_price:,}원 | EMA20: {ema_20:,.0f}원\n"
                f"   이격도: {distance_from_ema:.2f}% → 매도 신호"
            )
            return {
                "supported": False,
                "reason": "이평선 이탈",
                "action": "sell",
                "ema_20": ema_20,
                "distance": distance_from_ema,
            }
        else:
            logger.info(
                f"✅ {stock_name}: 1분봉 20분 이평선 지지 중\n"
                f"   현재가: {current_price:,}원 | EMA20: {ema_20:,.0f}원\n"
                f"   이격도: {distance_from_ema:+.2f}%"
            )
            return {
                "supported": True,
                "reason": "이평선 지지",
                "action": "hold",
                "ema_20": ema_20,
                "distance": distance_from_ema,
            }

    def get_sell_signal(
        self,
        stock_code: str,
        stock_name: str,
        buy_price: int,
        current_price: int,
        current_time: str = None
    ) -> Dict:
        """
        종합 매도 신호 판단

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            buy_price: 매수가
            current_price: 현재가
            current_time: 현재 시각 (HH:MM)

        Returns:
            매도 신호 정보
        """
        if current_time is None:
            current_time = datetime.now().strftime("%H:%M")

        profit_rate = ((current_price - buy_price) / buy_price) * 100

        logger.info("=" * 60)
        logger.info(f"📊 {stock_name} 매도 신호 분석")
        logger.info("=" * 60)
        logger.info(f"매수가: {buy_price:,}원 | 현재가: {current_price:,}원")
        logger.info(f"수익률: {profit_rate:+.2f}%")
        logger.info(f"현재 시각: {current_time}")

        # 1. 09:03 이전이면 3분의 법칙 체크
        if current_time <= "09:03":
            # 시초가 조회
            price_info = self.api.get_stock_price(stock_code)
            if price_info:
                opening_price = price_info.get('opening_price', buy_price)
                three_min_result = self.check_three_minute_rule(
                    stock_code, stock_name, opening_price
                )

                if three_min_result['action'] == 'sell':
                    logger.info("🔔 매도 신호: 3분의 법칙 실패 (시간 손절)")
                    return {
                        "should_sell": True,
                        "reason": "3분의 법칙 실패",
                        "signal_type": "time_stop",
                        "details": three_min_result,
                    }

        # 2. 1분봉 20분 이평선 체크
        ema_result = self.check_ema_support(stock_code, stock_name, current_price)

        if ema_result['action'] == 'sell':
            logger.info("🔔 매도 신호: 1분봉 20분 이평선 이탈")
            return {
                "should_sell": True,
                "reason": "이평선 이탈",
                "signal_type": "technical_stop",
                "details": ema_result,
            }

        # 3. 매도 신호 없음 - 보유
        logger.info("✅ 보유 유지 (매도 조건 미충족)")
        logger.info("=" * 60)

        return {
            "should_sell": False,
            "reason": "보유 조건 유지",
            "signal_type": "hold",
            "details": {
                "ema_result": ema_result,
            },
        }
