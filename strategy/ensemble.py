"""
앙상블 프레임워크 모듈 (v2.0)
4가지 독립적 수익원천 로직을 결합하여 최종 신호를 생성합니다.
"""
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnsembleEngine:
    """4가지 수익원천 로직 앙상블 엔진"""
    
    WEIGHTS = {
        "tug_of_war": 0.30,      # 로직 1: 투자자 이질성
        "v_pattern": 0.35,       # 로직 2: 실시간 수급 (V자)
        "moc_imbalance": 0.15,   # 로직 3: 체결 왜곡
        "news_temporal": 0.20,   # 로직 4: 정보 전파
    }

    @staticmethod
    def calculate_logic1_tug_of_war(data: Dict) -> float:
        """
        LOGIC 1: Tug of War (30%)
        장중 가격 억눌림 + 모멘텀 유지 확인
        """
        score = 0
        # 장중 수익률이 음수이나 전일 대비는 양수인 경우 (억눌림)
        intraday_ret = (data.get('current_price', 0) - data.get('open_price', 0)) / data.get('open_price', 1)
        daily_ret = data.get('change_rate', 0) / 100
        
        if intraday_ret < 0 and daily_ret > 0.02:
            score += 60
        
        # 개인 투자자 비중(RTP)이 높은 경우 가점 (간이 구현)
        if data.get('individual_buy_ratio', 0) > 0.6:
            score += 40
            
        return min(score, 100)

    @staticmethod
    def calculate_logic2_v_pattern(v_score: float) -> float:
        """
        LOGIC 2: V자 수급전환 (35%)
        Phase 3에서 계산된 V자 점수 활용
        """
        # v_score는 보통 0~100 사이로 들어옴
        return min(v_score, 100)

    @staticmethod
    def calculate_logic3_moc_imbalance(data: Dict) -> float:
        """
        LOGIC 3: MOC Imbalance (15%)
        동시호가 불균형 및 역설적 호가창
        """
        score = 0
        sell_qty = data.get('sell_order_qty', 0)
        buy_qty = data.get('buy_order_qty', 0)
        
        # 역설적 호가창: 매도잔량 >= 매수잔량 * 2
        if buy_qty > 0 and sell_qty >= buy_qty * 2:
            score += 70
            
        # 예상체결가 상승 중
        if data.get('expected_price_rising', False):
            score += 30
            
        return min(score, 100)

    @staticmethod
    def calculate_logic4_news_temporal(data: Dict) -> float:
        """
        LOGIC 4: 뉴스 Temporal Anomaly (20%)
        정보 전파 속도 및 키워드 파급력
        """
        score = 0
        news_count = data.get('news_count', 0)
        sentiment = data.get('sentiment_score', 0) # 0~100
        
        # 뉴스 확산성 (20개 이상)
        if news_count >= 20:
            score += 40
        elif news_count >= 10:
            score += 20
            
        # 감정 분석 결과 반영
        score += (sentiment * 0.6)
        
        return min(score, 100)

    def get_ensemble_score(self, stock_data: Dict) -> Dict:
        """종합 앙상블 점수 산출"""
        l1 = self.calculate_logic1_tug_of_war(stock_data)
        l2 = self.calculate_logic2_v_pattern(stock_data.get('v_score', 0))
        l3 = self.calculate_logic3_moc_imbalance(stock_data)
        l4 = self.calculate_logic4_news_temporal(stock_data)
        
        total_score = (
            l1 * self.WEIGHTS["tug_of_war"] +
            l2 * self.WEIGHTS["v_pattern"] +
            l3 * self.WEIGHTS["moc_imbalance"] +
            l4 * self.WEIGHTS["news_temporal"]
        )
        
        # 진입 등급 결정
        entry_grade = "SKIP"
        if total_score >= 70:
            entry_grade = "TOP_PRIORITY"
        elif total_score >= 55:
            entry_grade = "STANDARD"
        elif total_score >= 40:
            entry_grade = "SMALL"
            
        return {
            "total_score": round(total_score, 1),
            "logic_scores": {
                "l1_tug": l1,
                "l2_v": l2,
                "l3_moc": l3,
                "l4_news": l4
            },
            "entry_grade": entry_grade
        }
