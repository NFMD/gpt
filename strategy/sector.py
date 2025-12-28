"""
섹터 분석 모듈
섹터별 주도성을 분석하고 대장주를 선정합니다.
"""
import logging
from typing import List, Dict
from collections import defaultdict


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SectorAnalyzer:
    """섹터 분석기"""

    def __init__(self):
        # 업종별 종목 그룹핑을 위한 키워드 매핑
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
        """
        종목명으로 섹터 분류

        Args:
            stock_name: 종목명

        Returns:
            섹터명
        """
        for sector, keywords in self.sector_keywords.items():
            for keyword in keywords:
                if keyword in stock_name:
                    return sector
        return "기타"

    def analyze_sectors(self, stocks: List[Dict]) -> Dict:
        """
        섹터별 분석

        Args:
            stocks: 종목 리스트

        Returns:
            섹터별 분석 결과
        """
        sector_data = defaultdict(lambda: {
            "stocks": [],
            "total_change_rate": 0.0,
            "total_trading_value": 0,
            "count": 0,
        })

        # 섹터별 그룹핑
        for stock in stocks:
            sector = self.classify_sector(stock['stock_name'])
            sector_data[sector]["stocks"].append(stock)
            sector_data[sector]["total_change_rate"] += stock['change_rate']
            sector_data[sector]["total_trading_value"] += stock['trading_value']
            sector_data[sector]["count"] += 1

        # 섹터별 평균 계산
        sector_analysis = {}
        for sector, data in sector_data.items():
            avg_change_rate = data["total_change_rate"] / data["count"] if data["count"] > 0 else 0

            sector_analysis[sector] = {
                "stocks": data["stocks"],
                "count": data["count"],
                "total_change_rate": data["total_change_rate"],
                "avg_change_rate": avg_change_rate,
                "total_trading_value": data["total_trading_value"],
            }

        return sector_analysis

    def find_dominant_sectors(self, stocks: List[Dict], min_stocks: int = 2) -> List[Dict]:
        """
        주도 섹터 찾기

        기준:
        - 동일 섹터 내 2개 이상의 종목이 동시 상승
        - 합산 등락률이 높은 순서

        Args:
            stocks: 종목 리스트
            min_stocks: 최소 종목 수

        Returns:
            주도 섹터 리스트
        """
        sector_analysis = self.analyze_sectors(stocks)

        # 최소 종목 수 이상인 섹터만 필터링
        dominant_sectors = [
            {
                "sector": sector,
                **data
            }
            for sector, data in sector_analysis.items()
            if data["count"] >= min_stocks and sector != "기타"
        ]

        # 합산 등락률 순으로 정렬
        dominant_sectors = sorted(
            dominant_sectors,
            key=lambda x: x["total_change_rate"],
            reverse=True
        )

        return dominant_sectors

    def find_sector_leaders(self, stocks: List[Dict]) -> List[Dict]:
        """
        섹터별 대장주 찾기

        각 섹터에서 거래대금이 가장 많은 종목을 대장주로 선정

        Args:
            stocks: 종목 리스트

        Returns:
            섹터별 대장주 리스트
        """
        sector_analysis = self.analyze_sectors(stocks)
        sector_leaders = []

        for sector, data in sector_analysis.items():
            if data["count"] == 0:
                continue

            # 거래대금 기준 최강 종목
            leader = max(data["stocks"], key=lambda x: x['trading_value'])

            sector_leaders.append({
                "sector": sector,
                "leader": leader,
                "sector_count": data["count"],
                "sector_total_change_rate": data["total_change_rate"],
            })

        # 섹터 합산 등락률 순으로 정렬
        sector_leaders = sorted(
            sector_leaders,
            key=lambda x: x["sector_total_change_rate"],
            reverse=True
        )

        return sector_leaders

    def print_sector_analysis(self, stocks: List[Dict]):
        """
        섹터 분석 결과 출력

        Args:
            stocks: 종목 리스트
        """
        logger.info("=" * 60)
        logger.info("📊 섹터 분석 결과")
        logger.info("=" * 60)

        dominant_sectors = self.find_dominant_sectors(stocks)

        if not dominant_sectors:
            logger.info("⚠️  주도 섹터가 확인되지 않았습니다.")
            return

        for idx, sector_data in enumerate(dominant_sectors, 1):
            logger.info(
                f"\n{idx}. {sector_data['sector']} 섹터\n"
                f"   종목 수: {sector_data['count']}개 | "
                f"합산 등락률: {sector_data['total_change_rate']:.2f}% | "
                f"평균 등락률: {sector_data['avg_change_rate']:.2f}%"
            )

            # 섹터 내 종목 출력
            for stock in sector_data['stocks']:
                value_in_billions = stock['trading_value'] / 100000000
                logger.info(
                    f"   ➤ {stock['stock_name']} ({stock['stock_code']}): "
                    f"{stock['change_rate']:+.2f}% | {value_in_billions:,.0f}억원"
                )

        # 섹터별 대장주 출력
        logger.info("\n" + "=" * 60)
        logger.info("🏆 섹터별 대장주 (거래대금 기준)")
        logger.info("=" * 60)

        sector_leaders = self.find_sector_leaders(stocks)

        for leader_data in sector_leaders[:5]:  # 상위 5개 섹터만
            leader = leader_data['leader']
            value_in_billions = leader['trading_value'] / 100000000
            logger.info(
                f"\n{leader_data['sector']} 섹터 대장주:\n"
                f"   {leader['stock_name']} ({leader['stock_code']})\n"
                f"   등락률: {leader['change_rate']:+.2f}% | "
                f"거래대금: {value_in_billions:,.0f}억원"
            )
