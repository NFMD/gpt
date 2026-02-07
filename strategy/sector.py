"""
섹터 분석 모듈 (v1.1)
섹터별 주도성을 분석하고 대장주를 선정합니다.
"""
import logging
from typing import List, Dict
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SectorAnalyzer:
    """섹터 분석기 (v1.1)"""

    def __init__(self):
        self.sector_keywords = {
            "2차전지": ["2차전지", "배터리", "LG에너지", "삼성SDI", "SK온", "에코프로"],
            "반도체": ["반도체", "SK하이닉스", "삼성전자", "메모리", "파운드리"],
            "바이오": ["바이오", "제약", "셀트리온", "삼성바이오", "헬스케어"],
            "자동차": ["자동차", "현대차", "기아", "모빌리티"],
            "조선": ["조선", "HD현대", "삼성중공업", "한화오션"],
            "엔터": ["엔터", "카카오", "네이버", "하이브", "SM", "YG", "JYP"],
            "게임": ["게임", "넥슨", "엔씨", "크래프톤", "넷마블"],
            "은행": ["은행", "KB금융", "신한", "하나", "우리"],
            "증권": ["증권", "미래에셋", "삼성증권", "NH투자", "키움"],
            "화학": ["화학", "LG화학", "SK케미칼", "롯데케미칼"],
            "건설": ["건설", "삼성물산", "현대건설", "대우건설"],
            "유통": ["유통", "신세계", "롯데쇼핑", "현대백화점"],
            "인터넷": ["인터넷", "카카오", "네이버", "쿠팡"],
            "항공": ["항공", "대한항공", "아시아나"],
            "원전": ["원전", "두산에너빌리티", "한전", "한국전력"],
        }

    def classify_sector(self, stock_name: str) -> str:
        for sector, keywords in self.sector_keywords.items():
            for keyword in keywords:
                if keyword in stock_name:
                    return sector
        return "기타"

    def check_sector_strength(self, stocks: List[Dict]) -> Dict[str, bool]:
        """
        섹터 동반 상승 여부 확인 (BONUS 조건)
        동일 테마 4종목 이상 +3% 시 해당 섹터 강세로 판단
        """
        sector_counts = defaultdict(int)
        for stock in stocks:
            if stock.get('change_rate', 0) >= 3.0:
                sector = self.classify_sector(stock['stock_name'])
                if sector != "기타":
                    sector_counts[sector] += 1
        
        return {sector: count >= 4 for sector, count in sector_counts.items()}
