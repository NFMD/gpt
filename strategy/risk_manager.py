"""
리스크 관리 모듈 (v2.0)
StopLossEngine 및 MacroFilter를 구현합니다.
"""
import logging
from datetime import datetime, time
from typing import Dict, Optional
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    DANGER = "DANGER"

class StopLossEngine:
    """기계적 손절 자동화 엔진 (v2.0)"""
    
    def __init__(self, total_asset: float):
        self.total_asset = total_asset
        self.max_loss_pct = 0.03  # 단일 거래 최대 손실 3% (총자산 기준)

    def evaluate(self, data: Dict) -> Dict:
        """
        모든 손절 조건 종합 평가 (우선순위 순)
        1. 비상 청산 (코스피 -2%↓)
        2. 가격 손절 (-3%↓)
        3. 20일선 손절 (종가 < 20MA)
        4. 시간 손절 (09:03 시초가 미돌파)
        5. 타임아웃 (10:00 강제청산)
        """
        now = datetime.now().time()
        
        # 1. 비상 청산
        if data.get('kospi_change', 0) <= -2.0:
            return {"trigger": True, "type": "EMERGENCY", "reason": "코스피 -2% 이상 급락"}
            
        # 2. 가격 손절
        entry_price = data.get('entry_price', 0)
        current_price = data.get('current_price', 0)
        if entry_price > 0:
            pnl_pct = (current_price - entry_price) / entry_price
            if pnl_pct <= -0.03:
                return {"trigger": True, "type": "PRICE_STOP", "reason": f"손절선(-3%) 도달: {pnl_pct*100:.1f}%"}
                
        # 3. 20일선 손절 (익일 시가 매도 조건이나 여기서는 즉시 판단)
        ma20 = data.get('ma20', 0)
        if current_price < ma20 and ma20 > 0:
            return {"trigger": True, "type": "MA20_STOP", "reason": "20일 이동평균선 하회"}
            
        # 4. 시간 손절 (09:03:00 이후)
        open_price = data.get('open_price', 0)
        if time(9, 3) <= now < time(10, 0):
            if current_price <= open_price:
                return {"trigger": True, "type": "TIME_STOP_3MIN", "reason": "09:03 시초가 돌파 실패"}
                
        # 5. 타임아웃 (10:00:00)
        if now >= time(10, 0):
            return {"trigger": True, "type": "TIMEOUT_10AM", "reason": "10시 강제 청산 시간 도달"}
            
        return {"trigger": False, "type": None, "reason": "정상 유지"}

class MacroFilter:
    """거시 환경 필터링 (v2.0)"""
    
    def check_market_regime(self, data: Dict) -> Dict:
        """
        시장 레짐 판단
        - DANGER: 코스피 -2%↓ / 미국선물 -2%↓ / VIX >= 30 -> 진입 금지, 전량 청산
        - CAUTION: 코스피 -1%↓ / 미국선물 -1%↓ / VIX >= 25 -> 비중 50% 축소
        - NORMAL: 정상
        """
        kospi = data.get('kospi_change', 0)
        us_futures = data.get('us_futures_change', 0)
        vix = data.get('vix', 0)
        
        if kospi <= -2.0 or us_futures <= -2.0 or vix >= 30:
            return {"level": RiskLevel.DANGER, "multiplier": 0.0, "reason": "시장 급락 위험 (DANGER)"}
            
        if kospi <= -1.0 or us_futures <= -1.0 or vix >= 25:
            return {"level": RiskLevel.CAUTION, "multiplier": 0.5, "reason": "시장 불안정 (CAUTION)"}
            
        return {"level": RiskLevel.NORMAL, "multiplier": 1.0, "reason": "시장 정상 (NORMAL)"}

class AfterMarketManager:
    """장후 대응 매니저 (v2.0)"""
    
    def check_359_rule(self, sell_qty: int, buy_qty: int) -> float:
        """
        3시 59분의 법칙
        매도잔량:매수잔량 비율에 따른 종가 정리 비중 반환
        """
        if buy_qty == 0: return 1.0
        ratio = sell_qty / buy_qty
        
        if ratio >= 2.0:
            return 0.5  # 50% 정리
        if ratio >= 1.5:
            return 0.3  # 30% 정리
            
        return 0.0  # 홀딩

    def check_overnight_exit(self, change_pct: float) -> float:
        """시간외 단일가 대응"""
        if change_pct >= 4.0:
            return 0.5  # 50% 익절
        if change_pct <= -2.0:
            return 0.3  # 30% 리스크 축소
        return 0.0
