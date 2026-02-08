"""
종목 스크리닝 모듈 (v2.0)
PHASE 1: 유니버스 필터 및 Tier 분류를 수행합니다.
"""
import logging
from typing import List, Dict, Tuple
from enum import Enum
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CandidateTier(Enum):
    TIER_1 = 1   # 최우선 (조 단위 주도주)
    TIER_2 = 2   # 우선 (섹터 리딩)
    TIER_3 = 3   # 기본 (일반 후보)

class StockScreener:
    """종목 스크리너 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api

    def phase1_filter(self, stock: Dict) -> Tuple[bool, CandidateTier]:
        """
        PHASE 1: 유니버스 필터 (MUST 조건) 및 Tier 분류
        """
        # MUST 조건 검증
        market_cap = stock.get('market_cap', 0)
        trading_value = stock.get('trading_value', 0)
        change_pct = stock.get('change_rate', 0)
        is_managed = stock.get('is_managed', False)
        is_limit_up = stock.get('is_limit_up', False)

        # Config 값은 비율(0.02)이 아닌 퍼센트(2.0)로 저장되어 있을 수 있으므로 확인 필요
        # 여기서는 v1.1에서 2.0, 15.0 등으로 설정했으므로 그대로 사용
        must_pass = (
            market_cap >= Config.MIN_MARKET_CAP and
            trading_value >= Config.MIN_TRADING_VALUE and
            Config.MIN_CHANGE_RATE <= change_pct <= Config.MAX_CHANGE_RATE and
            not is_managed and
            not is_limit_up
        )

        if not must_pass:
            return False, CandidateTier.TIER_3

        # Tier 분류
        # Tier 1: 거래대금 1조↑
        if trading_value >= 1e12:
            return True, CandidateTier.TIER_1
        
        # Tier 2: 거래대금 5,000억↑
        if trading_value >= 5e11:
            return True, CandidateTier.TIER_2
            
        return True, CandidateTier.TIER_3

    def get_candidates(self) -> List[Dict]:
        """전체 시장에서 후보 종목 추출 및 Tier 분류"""
        logger.info("=" * 60)
        logger.info("🎯 PHASE 1: 유니버스 필터링 및 Tier 분류 시작")
        logger.info("=" * 60)

        # 거래대금 상위 종목 조회
        raw_stocks = self.api.get_top_trading_value(count=100)
        
        candidates = []
        for stock in raw_stocks:
            passed, tier = self.phase1_filter(stock)
            if passed:
                stock['tier'] = tier
                candidates.append(stock)

        # Tier 순 -> 거래대금 순 정렬
        candidates.sort(key=lambda x: (x['tier'].value, -x['trading_value']))
        
        logger.info(f"✅ PHASE 1 통과 종목: {len(candidates)}개")
        for i, s in enumerate(candidates[:10], 1):
            logger.info(f"{i}. {s['stock_name']} ({s['stock_code']}) | Tier: {s['tier'].name} | 거래대금: {s['trading_value']/1e8:.0f}억")
            
        return candidates[:50]
