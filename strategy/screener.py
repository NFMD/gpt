"""
종목 스크리닝 모듈 (v2.0)
PHASE 1: 유니버스 필터 (MUST 조건 + Tier 분류)를 구현합니다.

수천 개 종목 → ~50개로 1차 축소
"돈이 몰리는 곳"을 먼저 찾는다

v2.0 변경사항:
- StockData 데이터클래스 도입
- CandidateTier (TIER_1/2/3) 분류
- phase1_filter: MUST 5조건 + Tier 등급 반환
- run_phase1: Tier별 정렬, 최대 50개 반환
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from api import KISApi
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════

class CandidateTier(Enum):
    """PHASE 1 우선순위 Tier"""
    TIER_1 = 1   # 최우선: 거래대금 1조↑ + 등락률 상위 10
    TIER_2 = 2   # 우선:   거래대금 5,000억↑ + 동일 테마 4종목↑
    TIER_3 = 3   # 기본:   거래대금 1,000억↑ + 등락률 상위 20


@dataclass
class StockData:
    """PHASE 1 종목 데이터"""
    symbol: str
    name: str
    market_cap: float               # 시가총액 (원)
    trading_value: float            # 거래대금 (원)
    change_pct: float               # 등락률 (소수: 0.05 = 5%)
    is_managed: bool                # 관리종목 여부
    is_limit_up: bool               # 상한가 여부
    change_rank: int = 0            # 등락률 순위
    trading_value_rank: int = 0     # 거래대금 순위
    theme: str = ""                 # 테마
    theme_stocks_rising: int = 0    # 동일 테마 내 +3% 이상 종목 수

    # 추가 데이터 (PHASE 2~4에서 사용)
    current_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    open_price: float = 0.0
    volume: int = 0
    raw_data: Dict = field(default_factory=dict)  # 원본 API 응답


# ═══════════════════════════════════════════════════════
# PHASE 1 핵심 함수
# ═══════════════════════════════════════════════════════

def phase1_filter(stock: StockData) -> Tuple[bool, Optional[CandidateTier]]:
    """
    PHASE 1: 유니버스 필터 (MUST 조건)

    MUST 5조건 (ALL AND — 하나라도 실패 시 제외):
    1. 시가총액 >= 3,000억
    2. 거래대금 >= 1,000억
    3. 등락률 +2% ~ +15%
    4. 관리종목 아님
    5. 상한가 아님

    Returns:
        (통과 여부, Tier 등급 or None)
    """
    must_conditions = [
        stock.market_cap >= Config.MIN_MARKET_CAP,            # 3,000억↑
        stock.trading_value >= Config.MIN_TRADING_VALUE,       # 1,000억↑
        (Config.MIN_CHANGE_RATE / 100) <= stock.change_pct <= (Config.MAX_CHANGE_RATE / 100),
        not stock.is_managed,
        not stock.is_limit_up,
    ]

    if not all(must_conditions):
        return False, None

    # ═══ 우선순위 Tier 분류 ═══
    # Tier 1: 거래대금 1조↑ + 등락률 상위 10
    if stock.trading_value >= 1e12 and stock.change_rank <= 10:
        return True, CandidateTier.TIER_1

    # Tier 2: 거래대금 5,000억↑ + 동일 테마 4종목↑ 동반상승
    if stock.trading_value >= 5e11 and stock.theme_stocks_rising >= 4:
        return True, CandidateTier.TIER_2

    # Tier 3: 기본 통과
    return True, CandidateTier.TIER_3


def run_phase1(stocks: List[StockData], max_candidates: int = 50) -> List[Tuple[StockData, CandidateTier]]:
    """
    전체 종목에 PHASE 1 적용, Tier별 정렬하여 반환

    Args:
        stocks: 전체 종목 리스트
        max_candidates: 최대 반환 종목 수 (기본 50)

    Returns:
        (StockData, CandidateTier) 리스트 — Tier 순서 → 거래대금 내림차순
    """
    candidates = []
    for stock in stocks:
        passed, tier = phase1_filter(stock)
        if passed and tier is not None:
            candidates.append((stock, tier))

    # Tier 순서(1→2→3) → 같은 Tier 내에서 거래대금 내림차순
    candidates.sort(key=lambda x: (x[1].value, -x[0].trading_value))

    return candidates[:max_candidates]


# ═══════════════════════════════════════════════════════
# StockScreener 클래스 (API 연동)
# ═══════════════════════════════════════════════════════

class StockScreener:
    """종목 스크리너 (v2.0)"""

    def __init__(self, api: KISApi):
        self.api = api
        logger.info("[PHASE1] StockScreener (v2.0) 초기화 완료")

    def _dict_to_stock_data(self, stock: Dict, rank: int = 0) -> StockData:
        """API 응답 딕셔너리 → StockData 변환"""
        change_pct_raw = stock.get('change_rate', 0)
        # change_rate가 % 단위(예: 5.0)면 소수로 변환
        change_pct = change_pct_raw / 100.0 if abs(change_pct_raw) > 1.0 else change_pct_raw

        return StockData(
            symbol=stock.get('stock_code', ''),
            name=stock.get('stock_name', ''),
            market_cap=stock.get('market_cap', 0),
            trading_value=stock.get('trading_value', 0),
            change_pct=change_pct,
            is_managed=stock.get('is_managed', False),
            is_limit_up=stock.get('is_limit_up', False),
            change_rank=rank,
            trading_value_rank=stock.get('trading_value_rank', rank),
            theme=stock.get('theme', ''),
            theme_stocks_rising=stock.get('theme_stocks_rising', 0),
            current_price=stock.get('current_price', 0),
            high_price=stock.get('high_price', 0),
            low_price=stock.get('low_price', 0),
            open_price=stock.get('open_price', 0),
            volume=stock.get('volume', 0),
            raw_data=stock,
        )

    def get_candidates(self) -> List[Dict]:
        """
        PHASE 1 필터를 통과한 후보 종목 리스트 반환 (v2.0)

        Returns:
            원본 Dict에 'tier', 'phase1_passed' 키가 추가된 리스트
        """
        logger.info("=" * 60)
        logger.info("[PHASE1] 유니버스 필터링 시작 (v2.0)")
        logger.info("=" * 60)

        # 거래대금 상위 종목 조회
        all_stocks_raw = self.api.get_top_trading_value(100)
        if not all_stocks_raw:
            logger.warning("[PHASE1] 종목 정보를 가져올 수 없습니다.")
            return []

        # 등락률 순위 부여
        sorted_by_change = sorted(all_stocks_raw, key=lambda s: s.get('change_rate', 0), reverse=True)
        for rank, s in enumerate(sorted_by_change, 1):
            s['change_rank'] = rank

        # StockData 변환 + PHASE 1 실행
        stock_data_list = [
            self._dict_to_stock_data(s, s.get('change_rank', i))
            for i, s in enumerate(all_stocks_raw, 1)
        ]

        phase1_results = run_phase1(stock_data_list)

        # 결과 변환 (원본 Dict에 Tier 정보 추가)
        candidates = []
        for stock_data, tier in phase1_results:
            result = stock_data.raw_data.copy()
            result['tier'] = tier.name
            result['tier_value'] = tier.value
            result['phase1_passed'] = True
            result['stock_data'] = stock_data
            candidates.append(result)

        # 로그 출력
        tier_counts = {}
        for _, tier in phase1_results:
            tier_counts[tier.name] = tier_counts.get(tier.name, 0) + 1

        logger.info(f"[PHASE1] 통과 종목: {len(candidates)}개 | "
                     f"Tier 분포: {tier_counts}")
        for idx, c in enumerate(candidates[:10], 1):
            logger.info(
                f"  {idx}. [{c['tier']}] {c.get('stock_name', '')} ({c.get('stock_code', '')}) | "
                f"시총: {c.get('market_cap', 0)/1e8:,.0f}억 | "
                f"거래대금: {c.get('trading_value', 0)/1e8:,.0f}억 | "
                f"등락률: {c.get('change_rate', 0):+.2f}%"
            )
        if len(candidates) > 10:
            logger.info(f"  ... 외 {len(candidates) - 10}개")

        return candidates
