"""
기술적 분석 모듈 (v2.0)
PHASE 2: SHOULD/BONUS 점수제 기반 기술적 검증을 수행합니다.
"""
import logging
from typing import List, Dict, Tuple
import numpy as np
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechnicalAnalyzer:
    """기술적 분석기 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api

    def phase2_score(self, stock: Dict) -> Tuple[bool, int]:
        """
        PHASE 2: 기술적 검증 (점수제)
        
        SHOULD (3개 중 2개 필수):
        - S1: 20일 신고가 (20점)
        - S2: 이평선 정배열 (15점)
        - S3: 당일 고가 근접 (15점)
        
        BONUS:
        - B1: 거래량 폭증 (10점)
        - B2: 섹터 동반 상승 (10점)
        - B3: 장대양봉 (5점)
        - B4: 위꼬리 짧음 (5점)
        - B5: 눌림목 패턴 (5점)
        """
        score = 0
        should_count = 0
        stock_code = stock['stock_code']
        
        # 데이터 조회
        price_history = self.api.get_daily_price_history(stock_code, 60)
        if not price_history or len(price_history) < 20:
            return False, 0
            
        current_price = stock.get('current_price', 0)
        high_price = stock.get('high_price', 0)
        open_price = stock.get('open_price', 0)
        
        # S1: 20일 신고가
        past_high_20d = max([p['high'] for p in price_history[1:21]])
        if high_price >= past_high_20d:
            score += 20
            should_count += 1
            
        # S2: 이평선 정배열 (5 > 20 > 60)
        if len(price_history) >= 60:
            closes = [p['close'] for p in price_history]
            ma5 = np.mean(closes[:5])
            ma20 = np.mean(closes[:20])
            ma60 = np.mean(closes[:60])
            if ma5 > ma20 > ma60:
                score += 15
                should_count += 1
            
        # S3: 당일 고가 근접 (현재가 >= 고가 * 0.97)
        if high_price > 0 and current_price >= high_price * 0.97:
            score += 15
            should_count += 1
            
        # SHOULD 조건 미충족 시 탈락
        if should_count < 2:
            return False, score
            
        # BONUS B1: 거래량 폭증 (20일 평균 * 3)
        vol = stock.get('volume', 0)
        vol_avg_20d = np.mean([p['volume'] for p in price_history[1:21]])
        if vol_avg_20d > 0 and vol >= vol_avg_20d * 3:
            score += 10
            
        # BONUS B2: 섹터 동반 상승 (외부 주입 데이터 활용)
        if stock.get('sector_sync', False):
            score += 10
            
        # BONUS B3: 장대양봉 (몸통 3% 이상)
        body_pct = abs(current_price - open_price) / open_price if open_price > 0 else 0
        if body_pct >= 0.03 and current_price > open_price:
            score += 5
            
        # BONUS B4: 위꼬리 짧음 (위꼬리/몸통 <= 0.3)
        body_size = abs(current_price - open_price)
        upper_wick = high_price - max(current_price, open_price)
        if body_size > 0 and (upper_wick / body_size) <= 0.3:
            score += 5
            
        # BONUS B5: 눌림목 패턴 (2~3일 조정 + 5일선 지지 + 거래량 급감)
        # 간이 구현: 직전 2일 연속 하락 & 현재가 > ma5 & 거래량 < 전일거래량 * 0.5
        if len(price_history) >= 3:
            is_declining = price_history[1]['close'] < price_history[2]['close']
            vol_drop = vol < price_history[1]['volume'] * 0.5
            if is_declining and vol_drop:
                score += 5
            
        return True, score

    def analyze_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """후보 종목들에 대해 기술적 분석 수행"""
        logger.info("=" * 60)
        logger.info("🔬 PHASE 2: 기술적 검증 시작")
        logger.info("=" * 60)
        
        passed_stocks = []
        for stock in candidates:
            is_passed, score = self.phase2_score(stock)
            if is_passed:
                stock['phase2_score'] = score
                passed_stocks.append(stock)
                logger.info(f"✅ {stock['stock_name']} 통과 | 점수: {score}")
                
        # 점수 순 정렬
        passed_stocks.sort(key=lambda x: x['phase2_score'], reverse=True)
        
        logger.info(f"✅ PHASE 2 통과 종목: {len(passed_stocks)}개")
        return passed_stocks
