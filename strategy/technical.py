"""
기술적 분석 모듈 (v1.1)
PHASE 2: 기술적 검증 (점수제)를 구현합니다.
"""
import logging
from typing import Dict, List, Tuple
import numpy as np
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """기술적 분석기 (v1.1)"""

    def __init__(self, api: KISApi):
        self.api = api

    def phase2_score(self, stock: Dict) -> Tuple[bool, int]:
        """
        PHASE 2: 기술적 검증 (점수제)
        
        SHOULD (3개 중 2개 이상 필수, 각 점수 부여):
        1. 20일 신고가 (20점)
        2. 이평선 정배열 (15점)
        3. 당일 고가 근접 (15점)
        
        BONUS:
        1. 거래량 폭증 (10점)
        2. 섹터 동반 상승 (10점)
        
        통과 기준: 최소 35점 이상
        """
        score = 0
        should_count = 0
        stock_code = stock['stock_code']

        # 1. 20일 신고가 (SHOULD)
        price_history = self.api.get_daily_price_history(stock_code, 20)
        if price_history and len(price_history) >= 20:
            current_high = stock.get('high_price', 0)
            past_high = max([p['high'] for p in price_history[1:]])
            if current_high >= past_high:
                score += 20
                should_count += 1

        # 2. 이평선 정배열 (SHOULD)
        # 5MA > 20MA > 60MA
        if price_history and len(price_history) >= 60:
            closes = [p['close'] for p in price_history]
            ma5 = np.mean(closes[:5])
            ma20 = np.mean(closes[:20])
            ma60 = np.mean(closes[:60])
            if ma5 > ma20 > ma60:
                score += 15
                should_count += 1

        # 3. 당일 고가 근접 (SHOULD)
        # 현재가 >= 고가 * 0.97
        current_price = stock.get('current_price', 0)
        high_price = stock.get('high_price', 0)
        if high_price > 0 and current_price >= high_price * 0.97:
            score += 15
            should_count += 1

        # 4. 거래량 폭증 (BONUS)
        # 당일 거래량 >= 20일 평균 * 3
        if price_history and len(price_history) >= 20:
            volumes = [p['volume'] for p in price_history]
            avg_vol = np.mean(volumes[1:21])
            current_vol = stock.get('volume', 0)
            if current_vol >= avg_vol * 3:
                score += 10

        # 5. 섹터 동반 상승 (BONUS)
        # 동일 테마 4종목 이상 +3% (이 데이터는 외부에서 주입받거나 별도 조회 필요)
        # 여기서는 간단히 stock 데이터에 포함되어 있다고 가정하거나 생략
        if stock.get('sector_strength', False):
            score += 10

        is_passed = (should_count >= 2) and (score >= Config.PHASE2_MIN_SCORE)
        return is_passed, score

    def analyze_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """후보 종목들에 대해 PHASE 2 분석 수행"""
        logger.info("=" * 60)
        logger.info("🎯 PHASE 2: 기술적 검증 시작")
        logger.info("=" * 60)
        
        passed_stocks = []
        for stock in candidates:
            is_passed, score = self.phase2_score(stock)
            if is_passed:
                stock['phase2_score'] = score
                passed_stocks.append(stock)
                logger.info(f"✅ {stock['stock_name']} 통과 | 점수: {score}")
            else:
                logger.info(f"❌ {stock['stock_name']} 탈락 | 점수: {score}")
                
        return sorted(passed_stocks, key=lambda x: x['phase2_score'], reverse=True)
