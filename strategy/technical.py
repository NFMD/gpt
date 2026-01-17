"""
기술적 분석 모듈
신고가, 이동평균선, 외국인/기관 매수세를 분석합니다.
"""
import logging
from typing import Dict, List, Optional
import numpy as np
from api import KISApi
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """기술적 분석기"""

    def __init__(self, api: KISApi):
        self.api = api

    def is_new_high(self, stock_code: str, days: int = None) -> bool:
        """
        N일 신고가 돌파 확인

        Args:
            stock_code: 종목코드
            days: 기준 일수 (기본값: Config.NEW_HIGH_DAYS)

        Returns:
            신고가 여부
        """
        if days is None:
            days = Config.NEW_HIGH_DAYS

        price_history = self.api.get_daily_price_history(stock_code, days)

        if not price_history or len(price_history) < days:
            return False

        current_price = price_history[0]['close']
        past_high = max([p['high'] for p in price_history[1:]])

        is_high = current_price > past_high

        if is_high:
            logger.info(f"📈 {stock_code}: {days}일 신고가 돌파 (현재가: {current_price:,}원)")

        return is_high

    def calculate_moving_averages(self, stock_code: str, include_ma200: bool = False) -> Optional[Dict]:
        """
        이동평균선 계산 (5일, 20일, 60일, 200일)

        Args:
            stock_code: 종목코드
            include_ma200: 200일 이동평균선 포함 여부

        Returns:
            이동평균선 딕셔너리
        """
        days_needed = 200 if include_ma200 else 60
        price_history = self.api.get_daily_price_history(stock_code, days_needed)

        if not price_history:
            logger.warning(f"⚠️  {stock_code}: 이동평균선 계산에 필요한 데이터 부족")
            return None

        if include_ma200 and len(price_history) < 200:
            logger.warning(f"⚠️  {stock_code}: 200일 이동평균선 계산에 필요한 데이터 부족")
            return None

        if not include_ma200 and len(price_history) < 60:
            logger.warning(f"⚠️  {stock_code}: 이동평균선 계산에 필요한 데이터 부족")
            return None

        closes = [p['close'] for p in price_history]

        result = {
            "ma5": round(np.mean(closes[:5]), 2),
            "ma20": round(np.mean(closes[:20]), 2),
            "ma60": round(np.mean(closes[:60]), 2),
            "current_price": closes[0],
        }

        if include_ma200:
            result["ma200"] = round(np.mean(closes[:200]), 2)

        return result

    def is_ma200_uptrend(self, stock_code: str, lookback_days: int = 20) -> bool:
        """
        200일 이동평균선 상승 추세 확인

        최근 200일 MA와 N일 전의 200일 MA를 비교하여 상승 추세인지 판단합니다.

        Args:
            stock_code: 종목코드
            lookback_days: 비교 기준 일수 (기본: 20일)

        Returns:
            200일선 상승 추세 여부
        """
        # 200일 + lookback_days 만큼의 데이터 필요
        price_history = self.api.get_daily_price_history(stock_code, 200 + lookback_days)

        if not price_history or len(price_history) < 200 + lookback_days:
            logger.warning(f"⚠️  {stock_code}: 200일선 추세 분석에 필요한 데이터 부족")
            return False

        closes = [p['close'] for p in price_history]

        # 현재 200일 이동평균선
        current_ma200 = np.mean(closes[:200])

        # lookback_days 전의 200일 이동평균선
        past_ma200 = np.mean(closes[lookback_days:200 + lookback_days])

        # 상승률 계산
        ma200_change_rate = ((current_ma200 - past_ma200) / past_ma200) * 100

        is_uptrend = current_ma200 > past_ma200

        if is_uptrend:
            logger.info(
                f"📈 {stock_code}: 200일선 상승 추세 확인 "
                f"(현재: {current_ma200:,.0f}원, {lookback_days}일 전: {past_ma200:,.0f}원, "
                f"변화율: {ma200_change_rate:+.2f}%)"
            )
        else:
            logger.info(
                f"📉 {stock_code}: 200일선 하락/횡보 "
                f"(변화율: {ma200_change_rate:+.2f}%)"
            )

        return is_uptrend

    def is_golden_alignment(self, stock_code: str) -> bool:
        """
        정배열 확인 (단기 > 중기 > 장기)

        Args:
            stock_code: 종목코드

        Returns:
            정배열 여부
        """
        mas = self.calculate_moving_averages(stock_code)

        if not mas:
            return False

        is_aligned = mas['ma5'] > mas['ma20'] > mas['ma60']

        if is_aligned:
            logger.info(
                f"✅ {stock_code}: 정배열 확인 "
                f"(5일: {mas['ma5']:,.0f} > 20일: {mas['ma20']:,.0f} > 60일: {mas['ma60']:,.0f})"
            )

        return is_aligned

    def check_investor_buying(self, stock_code: str) -> Dict:
        """
        외국인/기관 매수세 확인

        Args:
            stock_code: 종목코드

        Returns:
            매수세 정보
        """
        investor_info = self.api.get_investor_trading(stock_code)

        if not investor_info:
            return {
                "foreign_buying": False,
                "institution_buying": False,
                "both_buying": False,
            }

        foreign_buying = investor_info['foreign_net_buy'] > 0
        institution_buying = investor_info['institution_net_buy'] > 0
        both_buying = foreign_buying and institution_buying

        if both_buying:
            logger.info(
                f"💰 {stock_code}: 외국인+기관 동반 매수 "
                f"(외국인: {investor_info['foreign_net_buy']:,}주, "
                f"기관: {investor_info['institution_net_buy']:,}주)"
            )
        elif foreign_buying:
            logger.info(f"💰 {stock_code}: 외국인 매수 ({investor_info['foreign_net_buy']:,}주)")
        elif institution_buying:
            logger.info(f"💰 {stock_code}: 기관 매수 ({investor_info['institution_net_buy']:,}주)")

        return {
            "foreign_buying": foreign_buying,
            "institution_buying": institution_buying,
            "both_buying": both_buying,
            "foreign_net_buy": investor_info['foreign_net_buy'],
            "institution_net_buy": investor_info['institution_net_buy'],
        }

    def analyze_stock(self, stock_code: str, stock_name: str = "") -> Dict:
        """
        종목 종합 기술적 분석

        Args:
            stock_code: 종목코드
            stock_name: 종목명

        Returns:
            분석 결과 딕셔너리
        """
        logger.info(f"🔍 {stock_name} ({stock_code}) 기술적 분석 중...")

        # 신고가 확인
        is_new_high = self.is_new_high(stock_code)

        # 정배열 확인
        is_aligned = self.is_golden_alignment(stock_code)

        # 200일선 상승 추세 확인
        ma200_uptrend = self.is_ma200_uptrend(stock_code)

        # 투자자 매수세 확인
        investor_buying = self.check_investor_buying(stock_code)

        # 종합 점수 계산 (0~110)
        score = 0
        if is_new_high:
            score += 40
        if is_aligned:
            score += 30
        if ma200_uptrend:
            score += 10  # 200일선 상승 추세 보너스
        if investor_buying['both_buying']:
            score += 30
        elif investor_buying['foreign_buying'] or investor_buying['institution_buying']:
            score += 15

        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "is_new_high": is_new_high,
            "is_aligned": is_aligned,
            "ma200_uptrend": ma200_uptrend,
            "investor_buying": investor_buying,
            "score": score,
        }

        logger.info(f"📊 {stock_name} 분석 점수: {score}/110")

        return result

    def filter_by_technical(self, stocks: List[Dict]) -> List[Dict]:
        """
        기술적 분석 기준으로 종목 필터링

        Args:
            stocks: 종목 리스트

        Returns:
            필터링된 종목 리스트 (점수 순)
        """
        analyzed_stocks = []

        for stock in stocks:
            analysis = self.analyze_stock(stock['stock_code'], stock['stock_name'])
            analyzed_stocks.append({
                **stock,
                **analysis,
            })

        # 점수 순으로 정렬
        sorted_stocks = sorted(analyzed_stocks, key=lambda x: x['score'], reverse=True)

        return sorted_stocks
