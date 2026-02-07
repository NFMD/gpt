"""
종목 스크리닝 모듈 (v1.1)
PHASE 1: 유니버스 필터 (MUST 조건)를 구현합니다.
"""
import logging
from typing import List, Dict
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockScreener:
    """종목 스크리너 (v1.1)"""

    def __init__(self, api: KISApi):
        self.api = api

    def phase1_filter(self, stock: Dict) -> bool:
        """
        PHASE 1: 유니버스 필터 (MUST 조건)
        
        1. 시가총액 >= 3,000억
        2. 거래대금 >= 1,000억
        3. 등락률 +2% ~ +15%
        4. 관리종목 제외
        5. 상한가 제외
        """
        try:
            # 필수 데이터 존재 확인
            market_cap = stock.get('market_cap', 0)
            trading_value = stock.get('trading_value', 0)
            change_pct = stock.get('change_rate', 0)
            is_managed = stock.get('is_managed', False)
            is_limit_up = stock.get('is_limit_up', False)

            must_conditions = [
                market_cap >= Config.MIN_MARKET_CAP,
                trading_value >= Config.MIN_TRADING_VALUE,
                Config.MIN_CHANGE_RATE <= change_pct <= Config.MAX_CHANGE_RATE,
                not is_managed,
                not is_limit_up
            ]

            return all(must_conditions)
        except Exception as e:
            logger.error(f"Error in phase1_filter for {stock.get('stock_code')}: {e}")
            return False

    def get_candidates(self) -> List[Dict]:
        """
        PHASE 1 필터를 통과한 후보 종목 리스트 반환
        """
        logger.info("=" * 60)
        logger.info("🎯 PHASE 1: 유니버스 필터링 시작")
        logger.info("=" * 60)

        # 1. 전 종목 또는 상위 거래대금 종목 조회 (API 제약에 따라 구현)
        # 여기서는 편의상 거래대금 상위 100개 종목을 가져와서 필터링하는 것으로 가정
        all_stocks = self.api.get_top_trading_value(100)
        
        if not all_stocks:
            logger.warning("⚠️ 종목 정보를 가져올 수 없습니다.")
            return []

        candidates = [s for s in all_stocks if self.phase1_filter(s)]
        
        logger.info(f"✅ PHASE 1 통과 종목: {len(candidates)}개")
        for idx, s in enumerate(candidates, 1):
            logger.info(f"{idx}. {s['stock_name']} ({s['stock_code']}) | "
                        f"시총: {s['market_cap']/1e8:,.0f}억 | "
                        f"거래대금: {s['trading_value']/1e8:,.0f}억 | "
                        f"등락률: {s['change_rate']:+.2f}%")
            
        return candidates
