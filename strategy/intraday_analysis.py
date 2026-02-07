"""
장중 분봉 분석 모듈 (v1.1)
PHASE 3: V자 반등 패턴 감지 (MUST 조건 및 보너스)를 구현합니다.
"""
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntradayAnalyzer:
    """장중 실시간 분봉 분석기 (v1.1)"""

    def __init__(self, api: KISApi):
        self.api = api

    def phase3_v_pattern(self, stock_code: str, data: Dict) -> Tuple[bool, int]:
        """
        PHASE 3: V자 반등 감지 (15:16~15:19:30)
        
        MUST:
        1. 시간 조건 (15:16:00 ~ 15:19:30)
        2. 저점 대비 0.5% 이상 반등
        3. 1분봉 5MA 돌파
        4. 체결강도 100% 이상 + 상승세
        5. 프로그램 순매수 전환 (최근 3분)
        
        BONUS:
        1. 체결강도 150% 돌파 (10점)
        2. 역설적 호가창 (10점)
        3. 1분봉 20MA 돌파 (5점)
        
        통과 기준: MUST 조건 모두 충족 (기본 50점)
        """
        now = datetime.now().strftime('%H:%M:%S')
        
        # MUST 1: 시간 조건
        if not (Config.V_TIME_START <= now <= Config.V_TIME_END):
            return False, 0
            
        current_price = data.get('current_price', 0)
        low_since_1500 = data.get('low_since_1500', 0)
        ma5_1min = data.get('ma5_1min', 0)
        exec_str = data.get('execution_strength', 0)
        prev_exec_str = data.get('prev_execution_strength', 0)
        prog_net_3min = data.get('program_net_buy_3min', 0)
        
        # MUST 2: 저점 대비 0.5% 이상 반등
        if low_since_1500 > 0 and current_price <= low_since_1500 * (1 + Config.V_REBOUND_THRESHOLD):
            return False, 0
            
        # MUST 3: 1분봉 5MA 돌파
        if current_price <= ma5_1min:
            return False, 0
            
        # MUST 4: 체결강도 100% 이상 + 상승세
        if exec_str < 100 or exec_str <= prev_exec_str:
            return False, 0
            
        # MUST 5: 프로그램 순매수 전환
        if prog_net_3min <= 0:
            return False, 0
            
        # MUST 조건 모두 충족 시 기본 50점
        score = 50
        
        # BONUS 1: 체결강도 150% 돌파
        if exec_str >= 150:
            score += 10
            
        # BONUS 2: 역설적 호가창 (매도잔량 >= 매수잔량 * 1.5)
        sell_qty = data.get('sell_order_qty', 0)
        buy_qty = data.get('buy_order_qty', 0)
        if buy_qty > 0 and sell_qty >= buy_qty * 1.5:
            score += 10
            
        # BONUS 3: 1분봉 20MA 돌파
        ma20_1min = data.get('ma20_1min', 0)
        if ma20_1min > 0 and current_price > ma20_1min:
            score += 5
            
        return True, score

    def get_realtime_data(self, stock_code: str) -> Dict:
        """실시간 분석을 위한 데이터 수집 (KIS API 활용)"""
        # 실제 구현에서는 API를 통해 현재가, 호가, 프로그램 매매, 분봉 MA 등을 가져옴
        # 여기서는 구조만 정의
        return self.api.get_realtime_analysis_data(stock_code)
