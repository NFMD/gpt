"""
심리적 검증 모듈 (v2.0)
PHASE 3: 뉴스 확산성 및 감정 분석을 수행합니다.
"""
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """심리적 분석기 (v2.0)"""

    def __init__(self, api=None):
        self.api = api

    def phase3_score(self, stock: Dict) -> Tuple[bool, int]:
        """
        PHASE 3: 심리적 검증 (점수제)
        
        SHOULD:
        - S1: 뉴스 확산성 (기사 20개 이상) (15점)
        - S2: 뉴스 감정 (긍정률 60% 이상) (10점)
        
        BONUS:
        - B1: 종토방 활성화 (게시글 50개 이상) (5점)
        - B2: 파급력 키워드 포함 (10점)
        - B3: 네이버 금융 상위 노출 (5점)
        
        VETO (즉시 제외):
        - V1: 유상증자, 배임/횡령, 거래정지 예고 등
        """
        score = 0
        
        # VETO 조건 체크
        if stock.get('has_veto_news', False):
            logger.warning(f"🚨 VETO 발생: {stock['stock_name']} 제외")
            return False, 0
            
        # S1: 뉴스 확산성
        news_count = stock.get('news_count', 0)
        if news_count >= 20:
            score += 15
        elif news_count >= 10:
            score += 7
            
        # S2: 뉴스 감정 (0~100)
        sentiment = stock.get('sentiment_score', 50)
        if sentiment >= 60:
            score += 10
            
        # B1: 종토방 활성화
        board_count = stock.get('board_post_count', 0)
        if board_count >= 50:
            score += 5
            
        # B2: 파급력 키워드 ('세계 최초', '단독', '정부 정책' 등)
        if stock.get('has_power_keywords', False):
            score += 10
            
        # B3: 네이버 금융 상위 노출
        if stock.get('is_naver_top', False):
            score += 5
            
        # 통과 기준: 15점 이상 (뉴스 확산성 또는 감정+보너스)
        is_passed = score >= 15
        return is_passed, score

    def analyze_psychology(self, candidates: List[Dict]) -> List[Dict]:
        """후보 종목들에 대해 심리적 분석 수행"""
        logger.info("=" * 60)
        logger.info("🧠 PHASE 3: 심리적 검증 시작")
        logger.info("=" * 60)
        
        passed_stocks = []
        for stock in candidates:
            # 실제 구현에서는 여기서 뉴스 크롤링 및 GPT 감정 분석 API 호출
            # news_data = self.crawler.get_news(stock['stock_name'])
            # stock.update(self.gpt_analyst.analyze(news_data))
            
            is_passed, score = self.phase3_score(stock)
            if is_passed:
                stock['phase3_score'] = score
                passed_stocks.append(stock)
                logger.info(f"✅ {stock['stock_name']} 심리적 검증 통과 | 점수: {score}")
                
        return passed_stocks
