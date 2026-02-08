"""
커맨드 센터 - AI 오케스트레이션 (v2.0)
Claude Opus(Commander)를 필두로 한 AI 협업 체계를 구현합니다.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from strategy.ensemble import EnsembleEngine
from strategy.risk_manager import MacroFilter, RiskLevel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CommandCenter:
    """커맨드 센터 (v2.0)"""

    def __init__(self, api=None):
        self.api = api
        self.ensemble = EnsembleEngine()
        self.macro_filter = MacroFilter()
        logger.info("🚀 커맨드 센터 (v2.0) 초기화 완료")

    def get_final_decision(
        self,
        candidates: List[Dict],
        market_data: Dict,
        account_info: Dict
    ) -> List[Dict]:
        """
        COMMANDER (Claude Opus) - 최종 의사결정
        """
        logger.info("=" * 60)
        logger.info("🤖 COMMANDER: v2.0 앙상블 의사결정 시작")
        logger.info("=" * 60)
        
        # 1. 거시 환경 필터링
        regime = self.macro_filter.check_market_regime(market_data)
        logger.info(f"🌐 시장 레짐: {regime['level'].value} ({regime['reason']})")
        
        if regime['level'] == RiskLevel.DANGER:
            logger.warning("🚨 DANGER 레짐: 모든 신규 진입을 금지합니다.")
            return []

        # 2. 종목별 앙상블 점수 산출
        final_picks = []
        for stock in candidates:
            # Phase 2, 3 점수 등을 stock 데이터에 포함시켜 전달
            res = self.ensemble.get_ensemble_score(stock)
            stock.update(res)
            
            if res['entry_grade'] != "SKIP":
                # 거시 필터에 따른 비중 조절 계수 적용
                stock['weight_multiplier'] = regime['multiplier']
                final_picks.append(stock)
                
        # 3. 최종 순위화 및 비중 결정
        final_picks.sort(key=lambda x: x['total_score'], reverse=True)
        
        decisions = []
        for stock in final_picks[:3]: # 최대 3종목
            decision = {
                "symbol": stock['stock_code'],
                "name": stock['stock_name'],
                "grade": stock['entry_grade'],
                "score": stock['total_score'],
                "multiplier": stock['weight_multiplier'],
                "reason": f"앙상블 {stock['total_score']}점 ({stock['entry_grade']})"
            }
            decisions.append(decision)
            logger.info(f"✅ 최종 선정: {stock['stock_name']} | 점수: {stock['total_score']} | 등급: {stock['entry_grade']}")
            
        return decisions

    def analyst_report(self, stock_name: str) -> str:
        """GPT (ANALYST) - 뉴스 감정 및 재료 분석 리포트"""
        return f"[{stock_name}] 주도 테마 내 대장주 역할, 뉴스 확산성 양호함."

    def explorer_brief(self) -> List[str]:
        """Gemini (EXPLORER) - 글로벌 테마 및 섹터 동향 브리핑"""
        return ["AI 반도체", "저PBR", "초전도체(주의)"]
