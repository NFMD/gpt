"""
VETO 키워드 시스템 모듈 (v2.0)
악재성 키워드를 감지하여 즉시 제외 처리합니다.

VETO 발동 시 COMMANDER 재검토 불가 — 즉시 제외.
"""
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── VETO 키워드 DB ──
VETO_KEYWORDS = {
    # 기업 리스크
    "corporate_risk": [
        "감사의견", "감사의견거절", "한정의견",
        "횡령", "배임", "분식회계",
        "상장폐지", "상폐", "관리종목",
        "거래정지", "매매정지",
    ],
    # 자금 조달 리스크 (희석)
    "dilution_risk": [
        "유상증자", "유증",
        "전환사채", "CB발행", "CB 발행",
        "신주인수권부사채", "BW발행", "BW 발행",
        "무상감자",
    ],
    # 공매도/숏
    "short_risk": [
        "공매도", "대차잔고 급증", "공매도 급증",
    ],
    # 실적 악화
    "earnings_risk": [
        "적자전환", "적자확대", "매출급감",
        "실적쇼크", "어닝쇼크",
    ],
    # 규제/법적 리스크
    "regulatory_risk": [
        "검찰수사", "압수수색", "과징금",
        "제재", "FDA 반려", "임상실패", "임상 실패",
    ],
    # 대주주 리스크
    "insider_risk": [
        "대주주 매도", "최대주주 변경", "최대주주 매도",
        "지분매각", "블록딜",
    ],
}

# 모든 VETO 키워드를 평면화한 리스트
ALL_VETO_KEYWORDS: List[str] = []
for category_keywords in VETO_KEYWORDS.values():
    ALL_VETO_KEYWORDS.extend(category_keywords)


@dataclass
class VetoResult:
    """VETO 판정 결과"""
    symbol: str
    name: str
    is_vetoed: bool
    matched_keywords: List[str]
    matched_categories: List[str]
    source_texts: List[str]   # VETO 발견된 원문


class VetoScanner:
    """VETO 키워드 스캐너 (v2.0)"""

    def __init__(self):
        self.keywords = VETO_KEYWORDS
        self.all_keywords = ALL_VETO_KEYWORDS
        logger.info(f"[VETO] VetoScanner 초기화 | "
                     f"{len(self.all_keywords)}개 키워드, "
                     f"{len(self.keywords)}개 카테고리")

    def scan_text(self, text: str) -> Tuple[bool, List[str], List[str]]:
        """
        단일 텍스트에서 VETO 키워드 스캔

        Args:
            text: 검사할 텍스트

        Returns:
            (VETO 여부, 매칭된 키워드 리스트, 매칭된 카테고리 리스트)
        """
        matched_keywords = []
        matched_categories = set()

        for category, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in text:
                    matched_keywords.append(keyword)
                    matched_categories.add(category)

        is_vetoed = len(matched_keywords) > 0
        return is_vetoed, matched_keywords, list(matched_categories)

    def scan_news_list(
        self,
        symbol: str,
        name: str,
        news_items: List[Dict],
    ) -> VetoResult:
        """
        뉴스 리스트에서 VETO 키워드 종합 스캔

        Args:
            symbol: 종목코드
            name: 종목명
            news_items: 뉴스 항목 리스트 (각각 {"title": ..., "content": ...})

        Returns:
            VetoResult
        """
        all_matched_keywords = []
        all_matched_categories = set()
        source_texts = []

        for item in news_items:
            title = item.get("title", "")
            content = item.get("content", "")
            combined = f"{title} {content}"

            vetoed, keywords, categories = self.scan_text(combined)
            if vetoed:
                all_matched_keywords.extend(keywords)
                all_matched_categories.update(categories)
                source_texts.append(title)

        is_vetoed = len(all_matched_keywords) > 0

        result = VetoResult(
            symbol=symbol,
            name=name,
            is_vetoed=is_vetoed,
            matched_keywords=list(set(all_matched_keywords)),
            matched_categories=list(all_matched_categories),
            source_texts=source_texts[:5],  # 최대 5개
        )

        if is_vetoed:
            logger.warning(
                f"[VETO] {name}({symbol}) VETO 발동! "
                f"키워드: {result.matched_keywords} | "
                f"카테고리: {result.matched_categories}"
            )
        else:
            logger.info(f"[VETO] {name}({symbol}) 통과")

        return result

    def scan_community_posts(
        self,
        symbol: str,
        name: str,
        posts: List[Dict],
    ) -> VetoResult:
        """
        종목토론방 게시글에서 VETO 키워드 스캔

        Args:
            symbol: 종목코드
            name: 종목명
            posts: 게시글 리스트 (각각 {"title": ..., "content": ...})

        Returns:
            VetoResult
        """
        return self.scan_news_list(symbol, name, posts)

    def quick_check(self, symbol: str, name: str, text: str) -> bool:
        """
        단일 텍스트 빠른 VETO 체크

        Returns:
            True면 VETO (제외해야 함)
        """
        vetoed, _, _ = self.scan_text(text)
        if vetoed:
            logger.warning(f"[VETO] {name}({symbol}) 빠른체크 VETO")
        return vetoed
