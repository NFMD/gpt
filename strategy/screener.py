"""
종목 스크리닝 모듈
거래대금과 등락률 기준으로 주도주를 선별합니다.
"""
import logging
from typing import List, Dict
from api import KISApi
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockScreener:
    """종목 스크리너"""

    def __init__(self, api: KISApi):
        self.api = api

    def screen_by_trading_value(self, stocks: List[Dict]) -> List[Dict]:
        """
        거래대금 기준 필터링

        Args:
            stocks: 종목 리스트

        Returns:
            필터링된 종목 리스트
        """
        # 1차 필터: 최소 거래대금 2000억 이상
        filtered = [
            stock for stock in stocks
            if stock['trading_value'] >= Config.MIN_TRADING_VALUE
        ]

        logger.info(f"📊 거래대금 2000억 이상 종목: {len(filtered)}개")

        if not filtered:
            logger.warning("⚠️  거래대금 기준을 만족하는 종목이 없습니다.")
            return []

        # 2차 필터: 거래대금 순으로 정렬하여 상위 종목 선정
        sorted_stocks = sorted(filtered, key=lambda x: x['trading_value'], reverse=True)

        # 주도주 (1조 이상) 표시
        dominant_stocks = [
            stock for stock in sorted_stocks
            if stock['trading_value'] >= Config.MIN_TRADING_VALUE_DOMINANT
        ]

        if dominant_stocks:
            logger.info(f"🔥 주도주 (1조 이상): {len(dominant_stocks)}개")
            for stock in dominant_stocks:
                value_in_billions = stock['trading_value'] / 100000000
                logger.info(
                    f"   ➤ {stock['stock_name']} ({stock['stock_code']}): "
                    f"거래대금 {value_in_billions:,.0f}억원, "
                    f"등락률 {stock['change_rate']:+.2f}%"
                )

        return sorted_stocks[:Config.TOP_VOLUME_COUNT]

    def get_top_candidates(self) -> List[Dict]:
        """
        매수 후보 종목 선정

        프로세스:
        1. 등락률 상위 20개 종목 조회
        2. 거래대금 2000억 이상 필터링
        3. 거래대금 순으로 상위 5개 선정

        Returns:
            최종 후보 종목 리스트
        """
        logger.info("=" * 60)
        logger.info("🎯 종목 스크리닝 시작")
        logger.info("=" * 60)

        # 1. 등락률 상위 종목 조회
        logger.info(f"1️⃣  등락률 상위 {Config.TOP_GAINERS_COUNT}개 종목 조회 중...")
        top_gainers = self.api.get_top_gainers(Config.TOP_GAINERS_COUNT)

        if not top_gainers:
            logger.warning("⚠️  등락률 상위 종목을 조회할 수 없습니다.")
            return []

        logger.info(f"✅ {len(top_gainers)}개 종목 조회 완료")

        # 2. 거래대금 필터링
        logger.info("2️⃣  거래대금 필터링 중...")
        filtered_stocks = self.screen_by_trading_value(top_gainers)

        if not filtered_stocks:
            return []

        # 3. 최종 결과 출력
        logger.info("=" * 60)
        logger.info(f"✅ 최종 후보 종목: {len(filtered_stocks)}개")
        logger.info("=" * 60)

        for idx, stock in enumerate(filtered_stocks, 1):
            value_in_billions = stock['trading_value'] / 100000000
            logger.info(
                f"{idx}. {stock['stock_name']} ({stock['stock_code']})\n"
                f"   현재가: {stock['current_price']:,}원 | "
                f"등락률: {stock['change_rate']:+.2f}% | "
                f"거래대금: {value_in_billions:,.0f}억원"
            )

        return filtered_stocks

    def get_stock_details(self, stock_code: str) -> Dict:
        """
        종목 상세 정보 조회

        Args:
            stock_code: 종목코드

        Returns:
            상세 정보 딕셔너리
        """
        price_info = self.api.get_stock_price(stock_code)
        investor_info = self.api.get_investor_trading(stock_code)

        if price_info and investor_info:
            return {**price_info, **investor_info}
        elif price_info:
            return price_info
        else:
            return {}
