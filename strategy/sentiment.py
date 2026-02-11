"""
심리적 검증 모듈 (v2.0)
PHASE 3: 심리적 검증 (점수제 + VETO)를 구현합니다.

~10개 → ~5개로 축소 (심리적 모멘텀 확인)
"시장의 관심이 충분한가? 악재는 없는가?"

v2.0 신규:
- SentimentData 데이터클래스
- phase3_score: SHOULD 2개 + BONUS 4개 + VETO 1개
- VETO_KEYWORDS 확장 (6개 카테고리 30개 키워드)
- POWER_KEYWORDS (16개 파급력 키워드)
- 최대 50점 (보편적 관심 보너스 포함)
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# VETO 키워드 (Part 2 명세)
# ═══════════════════════════════════════════════════════

VETO_KEYWORDS = {
    # 재무·회계 리스크
    "감사의견": "회계 리스크",
    "한정의견": "회계 리스크",
    "부적정의견": "회계 리스크",
    "의견거절": "회계 리스크",
    "분식회계": "회계 리스크",
    "허위공시": "회계 리스크",

    # 법적 리스크
    "횡령": "법적 리스크",
    "배임": "법적 리스크",
    "검찰": "법적 리스크",
    "고발": "법적 리스크",
    "수사": "법적 리스크",
    "기소": "법적 리스크",

    # 상장 리스크
    "상장폐지": "상장 리스크",
    "관리종목": "상장 리스크",
    "거래정지": "상장 리스크",

    # 수급 리스크
    "공매도": "수급 리스크",
    "대량매도": "수급 리스크",
    "블록딜": "수급 리스크",

    # 희석 리스크
    "유상증자": "희석 리스크",
    "CB": "희석 리스크",
    "BW": "희석 리스크",
    "전환사채": "희석 리스크",
    "신주인수권": "희석 리스크",

    # 경영 리스크
    "대표이사 사임": "경영 리스크",
    "대표이사 사퇴": "경영 리스크",
    "경영권 분쟁": "경영 리스크",
}

# 파급력 키워드 (BONUS 가점용)
POWER_KEYWORDS = [
    "세계 최초", "단독", "정부 정책", "국책과제",
    "수주", "흑자전환", "FDA 승인", "특허",
    "M&A", "인수합병", "실적 서프라이즈", "사상최대",
    "기술이전", "라이선스", "대규모 투자", "공장 증설",
]


# ═══════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════

@dataclass
class SentimentData:
    """심리 분석 데이터"""
    symbol: str

    # 뉴스 데이터
    google_article_count: int = 0       # 구글 뉴스 기사 수
    positive_ratio: float = 0.5         # 긍정 비율 (0~1)
    negative_ratio: float = 0.1         # 부정 비율 (0~1)
    headlines: List[str] = field(default_factory=list)  # 뉴스 헤드라인
    naver_top_10: bool = False          # 네이버 금융 상위 10개 노출

    # 커뮤니티 데이터
    forum_post_count: int = 0           # 종토방 게시글 수

    # 테마 데이터
    theme_expected_days: int = 0        # 테마 예상 지속일
    power_keywords_found: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════
# PHASE 3 점수 산출
# ═══════════════════════════════════════════════════════

def phase3_score(data: SentimentData) -> Tuple[bool, int, dict]:
    """
    PHASE 3: 심리적 검증

    VETO: 악재 키워드 발견 시 즉시 제외
    SHOULD:
      S1: 뉴스 확산성 구글뉴스>=20 (15점, 30개↑ 시 +5점)
      S2: 뉴스 감정 긍정률>=60% (10점)
    BONUS:
      B1: 종토방 활성화 게시글>=50 (5점)
      B2: 파급력 키워드 포함 (5점)
      B3: 네이버 금융 상위 (5점)
      B4: 테마 지속성>=3일 (5점)

    통과 기준: VETO 미발동 (점수와 무관하게 통과)
    최소 15점↑ 권장, 최대 50점

    Returns:
        (통과 여부, 총점, 상세 결과)
    """
    details = {}

    # ═══ VETO 체크 (발견 즉시 제외) ═══
    all_text = " ".join(data.headlines)
    for keyword, risk_type in VETO_KEYWORDS.items():
        if keyword in all_text:
            details["VETO"] = {
                "triggered": True,
                "keyword": keyword,
                "risk_type": risk_type,
            }
            logger.warning(
                f"[PHASE3] {data.symbol} VETO 발동: '{keyword}' ({risk_type})"
            )
            return False, 0, details

    details["VETO"] = {"triggered": False}

    score = 0

    # ═══ SHOULD 조건 ═══

    # S1: 뉴스 확산성
    s1 = data.google_article_count >= 20
    s1_score = 0
    if s1:
        s1_score = 15
        if data.google_article_count >= 30:
            s1_score += 5  # 보편적 관심 보너스
    score += s1_score
    details["S1_news_spread"] = {
        "pass": s1,
        "count": data.google_article_count,
        "score": s1_score,
    }

    # S2: 뉴스 감정
    s2 = data.positive_ratio >= 0.60
    s2_score = 10 if s2 else 0
    score += s2_score
    details["S2_news_sentiment"] = {
        "pass": s2,
        "positive_ratio": data.positive_ratio,
        "score": s2_score,
    }

    # ═══ BONUS 조건 ═══

    # B1: 종토방 활성화
    b1 = data.forum_post_count >= 50
    if b1:
        score += 5
    details["B1_forum_active"] = {"pass": b1, "score": 5 if b1 else 0}

    # B2: 파급력 키워드
    b2 = len(data.power_keywords_found) > 0
    if b2:
        score += 5
    details["B2_power_keywords"] = {
        "pass": b2,
        "keywords": data.power_keywords_found,
        "score": 5 if b2 else 0,
    }

    # B3: 네이버 금융 상위
    b3 = data.naver_top_10
    if b3:
        score += 5
    details["B3_naver_top"] = {"pass": b3, "score": 5 if b3 else 0}

    # B4: 테마 지속성
    b4 = data.theme_expected_days >= 3
    if b4:
        score += 5
    details["B4_theme_duration"] = {
        "pass": b4,
        "expected_days": data.theme_expected_days,
        "score": 5 if b4 else 0,
    }

    logger.info(
        f"[PHASE3] {data.symbol} | 점수={score} | "
        f"뉴스={data.google_article_count}건 | "
        f"감정=+{data.positive_ratio:.0%} | "
        f"파급력={data.power_keywords_found}"
    )

    # VETO 미발동이면 통과 (점수는 참고용)
    return True, score, details


def find_power_keywords(headlines: List[str]) -> List[str]:
    """헤드라인에서 파급력 키워드 탐지"""
    combined = " ".join(headlines)
    found = []
    for kw in POWER_KEYWORDS:
        if kw in combined:
            found.append(kw)
    return found
