"""
커맨드 센터 - AI 오케스트레이션 및 최종 의사결정 (v1.1)
Claude Opus(Commander) 역할을 수행하며 다른 AI들의 분석을 종합합니다.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommandCenter:
    """커맨드 센터 - AI 오케스트레이션 (v1.1)"""

    def __init__(self, api=None, trade_history=None):
        self.api = api
        self.trade_history = trade_history
        logger.info("🚀 커맨드 센터 (v1.1) 초기화 완료")

    def get_commander_decision(
        self,
        candidates: List[Dict],
        market_condition: Dict,
        account_info: Dict
    ) -> List[Dict]:
        """
        Claude Opus (COMMANDER) - 최종 의사결정
        
        다른 AI들의 분석 결과(Phase 1~3)를 종합하여 최종 매수 종목과 비중 결정
        """
        logger.info("=" * 60)
        logger.info("🤖 COMMANDER: 최종 의사결정 시작")
        logger.info("=" * 60)
        
        decisions = []
        
        # 1. 후보 종목 순위화 (Phase 2 + Phase 3 점수 합산)
        for stock in candidates:
            total_score = stock.get('phase2_score', 0) + stock.get('phase3_score', 0)
            stock['total_score'] = total_score
            
        sorted_candidates = sorted(candidates, key=lambda x: x['total_score'], reverse=True)
        
        # 2. 상위 종목 선정 (최대 3~5종목)
        top_picks = sorted_candidates[:Config.MAX_STOCKS]
        
        # 3. 포지션 사이징 및 결정
        for stock in top_picks:
            # AI 신뢰도 계산 (간이 로직: 점수 기반)
            confidence = min(int(stock['total_score'] / 1.5), 100)
            
            decision = {
                "action": "BUY" if confidence >= 70 else "SKIP",
                "symbol": stock['stock_code'],
                "name": stock['stock_name'],
                "price_type": "MARKET",
                "confidence": confidence,
                "reasoning": f"PHASE 2/3 종합 점수 {stock['total_score']}점, AI 신뢰도 {confidence}%",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if decision['action'] == "BUY":
                decisions.append(decision)
                logger.info(f"✅ {stock['stock_name']} 매수 결정 | 신뢰도: {confidence}%")
            else:
                logger.info(f"⏸️ {stock['stock_name']} 보류 | 신뢰도: {confidence}%")
                
        return decisions

    def analyze_market_sentiment(self) -> Dict:
        """
        GPT (ANALYST) - 비정량 데이터 분석 (간이 구현)
        """
        # 실제 구현에서는 뉴스/종토방 크롤링 데이터를 GPT API로 분석
        return {
            "sentiment_score": 65,
            "risk_level": "LOW",
            "top_themes": ["반도체", "AI"]
        }

    def explore_themes(self) -> List[str]:
        """
        Gemini (EXPLORER) - 테마 및 재료 탐색 (간이 구현)
        """
        # 실제 구현에서는 검색 API를 통해 주도 테마 탐색
        return ["AI 온디바이스", "CXL", "HBM"]
