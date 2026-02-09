"""
뉴스 Temporal Anomaly 분석 모듈 (v2.0) — LOGIC 4
장 마감 후 쏟아지는 뉴스의 시간차 반영을 분석합니다.

수익원천: 호재는 갭 상승 후에도 추가 Price Drift 발생
핵심: 구글뉴스 기사 수 + 파급력 키워드 + 뉴스 확산성 수치화
"""
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── 뉴스 확산성 기준 ──
NEWS_SPREAD_CRITERIA = {
    "google_news_articles": 20,      # 구글뉴스 기사 수 최소 기준
    "high_confidence_threshold": 30,  # 보편적 관심 확인 기준
    "naver_finance_top": True,        # 네이버 금융 뉴스 상위 노출
}

# ── 파급력 키워드 ──
POWER_KEYWORDS = [
    "세계 최초", "단독", "정부 정책",
    "국책과제", "수주", "흑자전환",
    "FDA 승인", "특허", "M&A",
    "대규모 투자", "신규 수주", "독점 공급",
    "전략적 제휴", "기술이전", "라이센스",
]

# ── 일봉 패턴 (보조) ──
BULLISH_PATTERNS = [
    "4음1양",         # 4일 음봉 후 양봉
    "5일선_이탈_20일선_지지",
    "망치형",
    "상승장악형",
]


@dataclass
class NewsTemporalResult:
    """LOGIC 4 뉴스 Temporal Anomaly 점수 결과"""
    symbol: str
    name: str
    score: float                     # 0~100
    google_news_count: int = 0
    naver_news_count: int = 0
    power_keywords_found: List[str] = field(default_factory=list)
    sentiment_positive: float = 0.0  # 0~1
    sentiment_negative: float = 0.0
    sentiment_neutral: float = 0.0
    news_spread_level: str = "LOW"   # LOW / MEDIUM / HIGH
    daily_pattern_match: bool = False
    details: Dict = field(default_factory=dict)


class NewsTemporalAnalyzer:
    """뉴스 Temporal Anomaly 분석기 (v2.0) — LOGIC 4"""

    def __init__(self):
        self.power_keywords = POWER_KEYWORDS
        self.spread_criteria = NEWS_SPREAD_CRITERIA
        logger.info("[LOGIC4] NewsTemporalAnalyzer (v2.0) 초기화 완료")

    def calculate_score(
        self,
        symbol: str,
        name: str,
        google_news_count: int = 0,
        naver_news_count: int = 0,
        news_headlines: List[str] = None,
        sentiment_positive: float = 0.5,
        sentiment_negative: float = 0.1,
        naver_top_exposure: bool = False,
        daily_pattern_match: bool = False,
    ) -> NewsTemporalResult:
        """
        LOGIC 4 점수 산출

        점수 구성 (0~100):
        - 구글 뉴스 기사 수 기반: 0~30
        - 파급력 키워드 매칭: 0~25
        - 감정 분석 점수: 0~20
        - 네이버 상위 노출: 0~10
        - 일봉 패턴 보조: 0~15
        """
        headlines = news_headlines or []
        score = 0.0
        power_found = []

        # ── 1. 구글 뉴스 기사 수 (0~30) ──
        if google_news_count >= self.spread_criteria["high_confidence_threshold"]:
            score += 30.0
        elif google_news_count >= self.spread_criteria["google_news_articles"]:
            score += 20.0
        elif google_news_count >= 10:
            score += 10.0

        # ── 2. 파급력 키워드 매칭 (0~25) ──
        combined_text = " ".join(headlines)
        for keyword in self.power_keywords:
            if keyword in combined_text:
                power_found.append(keyword)
        keyword_score = min(len(power_found) * 8, 25)
        score += keyword_score

        # ── 3. 감정 분석 (0~20) ──
        if sentiment_positive >= 0.7:
            score += 20.0
        elif sentiment_positive >= 0.5:
            score += 12.0
        elif sentiment_positive >= 0.3:
            score += 5.0

        # 부정 감정 패널티
        if sentiment_negative >= 0.3:
            score -= 10.0

        # ── 4. 네이버 금융 상위 노출 (0~10) ──
        if naver_top_exposure:
            score += 10.0

        # ── 5. 일봉 패턴 보조 (0~15) ──
        if daily_pattern_match:
            score += 15.0

        score = max(0.0, min(100.0, score))

        # 뉴스 확산 레벨
        if google_news_count >= self.spread_criteria["high_confidence_threshold"]:
            spread_level = "HIGH"
        elif google_news_count >= self.spread_criteria["google_news_articles"]:
            spread_level = "MEDIUM"
        else:
            spread_level = "LOW"

        result = NewsTemporalResult(
            symbol=symbol,
            name=name,
            score=round(score, 1),
            google_news_count=google_news_count,
            naver_news_count=naver_news_count,
            power_keywords_found=power_found,
            sentiment_positive=sentiment_positive,
            sentiment_negative=sentiment_negative,
            sentiment_neutral=1.0 - sentiment_positive - sentiment_negative,
            news_spread_level=spread_level,
            daily_pattern_match=daily_pattern_match,
            details={
                "google_score": min(30, google_news_count),
                "keyword_score": keyword_score,
                "sentiment_score": score - keyword_score,
            },
        )

        logger.info(
            f"[LOGIC4] {name}({symbol}) | "
            f"점수={score:.1f} | 구글={google_news_count}건 | "
            f"파급키워드={power_found} | "
            f"감정=+{sentiment_positive:.0%}/-{sentiment_negative:.0%} | "
            f"확산={spread_level}"
        )

        return result

    def analyze_headlines_sentiment(
        self,
        headlines: List[str],
    ) -> Dict:
        """
        뉴스 헤드라인의 간이 감정 분석 (키워드 기반)

        실제 운영에서는 GPT ANALYST가 수행.
        여기서는 키워드 기반 간이 분석.
        """
        positive_keywords = [
            "수주", "흑자", "상향", "최대", "신고가", "돌파",
            "호실적", "성장", "확대", "개선", "급등", "강세",
            "기대", "전망", "승인", "계약",
        ]
        negative_keywords = [
            "적자", "하락", "급락", "부진", "악재", "하향",
            "위기", "우려", "리스크", "폭락", "감소", "철회",
            "실패", "손실",
        ]

        pos_count = 0
        neg_count = 0
        total = len(headlines) if headlines else 1

        for headline in headlines:
            for kw in positive_keywords:
                if kw in headline:
                    pos_count += 1
                    break
            for kw in negative_keywords:
                if kw in headline:
                    neg_count += 1
                    break

        pos_ratio = pos_count / total
        neg_ratio = neg_count / total
        neu_ratio = 1.0 - pos_ratio - neg_ratio

        return {
            "positive": round(max(0, pos_ratio), 2),
            "negative": round(max(0, neg_ratio), 2),
            "neutral": round(max(0, neu_ratio), 2),
            "article_count": len(headlines),
        }
