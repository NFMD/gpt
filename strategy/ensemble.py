"""
앙상블 점수 산출 모듈 (v2.0)
4가지 수익원천 로직의 앙상블 점수를 산출합니다.

LOGIC 1: Tug of War (투자자 이질성) — 30%
LOGIC 2: V자 수급전환 (실시간 프로그램 매매) — 35%
LOGIC 3: MOC Imbalance (체결 메커니즘 왜곡) — 15%
LOGIC 4: 뉴스 Temporal Anomaly (정보 전파 속도 차이) — 20%
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── 앙상블 가중치 ──
ENSEMBLE_WEIGHTS = {
    "tug_of_war": 0.30,
    "v_pattern": 0.35,
    "moc_imbalance": 0.15,
    "news_temporal": 0.20,
}

# ── 진입 기준 ──
ENTRY_THRESHOLDS = {
    "priority": 70,     # 최우선 진입 (비중 확대)
    "standard": 55,     # 표준 진입
    "small": 40,        # 소규모 진입 (비중 축소)
    "skip": 40,         # 이 미만은 SKIP
}


@dataclass
class LogicScore:
    """개별 로직 점수 결과"""
    logic_name: str
    score: float          # 0~100
    weight: float         # 앙상블 가중치
    weighted_score: float  # score * weight
    details: Dict = field(default_factory=dict)


@dataclass
class EnsembleResult:
    """앙상블 종합 결과"""
    symbol: str
    name: str
    ensemble_score: float          # 0~100
    entry_tier: str                # "PRIORITY" / "STANDARD" / "SMALL" / "SKIP"
    logic_scores: List[LogicScore] = field(default_factory=list)
    dominant_logic: str = ""       # 가장 높은 점수의 로직명
    position_multiplier: float = 1.0  # 포지션 비중 배수


def calculate_ensemble_score(
    logic1_score: float,  # Tug of War (0~100)
    logic2_score: float,  # V자 수급전환 (0~100)
    logic3_score: float,  # MOC Imbalance (0~100)
    logic4_score: float,  # 뉴스 Temporal (0~100)
) -> float:
    """
    4가지 로직의 앙상블 점수 산출

    Args:
        logic1_score: Tug of War 점수 (0~100)
        logic2_score: V자 수급전환 점수 (0~100)
        logic3_score: MOC Imbalance 점수 (0~100)
        logic4_score: 뉴스 Temporal Anomaly 점수 (0~100)

    Returns:
        앙상블 종합 점수 (0~100)
    """
    ensemble = (
        logic1_score * ENSEMBLE_WEIGHTS["tug_of_war"]
        + logic2_score * ENSEMBLE_WEIGHTS["v_pattern"]
        + logic3_score * ENSEMBLE_WEIGHTS["moc_imbalance"]
        + logic4_score * ENSEMBLE_WEIGHTS["news_temporal"]
    )
    return round(ensemble, 1)


def determine_entry_tier(ensemble_score: float) -> Tuple[str, float]:
    """
    앙상블 점수 기반 진입 등급 결정

    Args:
        ensemble_score: 앙상블 종합 점수

    Returns:
        (진입 등급, 포지션 배수)
    """
    if ensemble_score >= ENTRY_THRESHOLDS["priority"]:
        return "PRIORITY", 1.5     # 비중 확대
    elif ensemble_score >= ENTRY_THRESHOLDS["standard"]:
        return "STANDARD", 1.0     # 표준 비중
    elif ensemble_score >= ENTRY_THRESHOLDS["small"]:
        return "SMALL", 0.5        # 비중 축소
    else:
        return "SKIP", 0.0         # 진입 안함


def find_dominant_logic(
    logic1_score: float,
    logic2_score: float,
    logic3_score: float,
    logic4_score: float,
) -> str:
    """가장 높은 점수의 로직명 반환"""
    scores = {
        "LOGIC_1_TOW": logic1_score,
        "LOGIC_2_V": logic2_score,
        "LOGIC_3_MOC": logic3_score,
        "LOGIC_4_NEWS": logic4_score,
    }
    return max(scores, key=scores.get)


class EnsembleScorer:
    """4가지 수익원천 로직 앙상블 점수 산출기 (v2.0)"""

    def __init__(self):
        self.weights = ENSEMBLE_WEIGHTS.copy()
        logger.info("EnsembleScorer (v2.0) 초기화 | "
                     f"가중치: TOW={self.weights['tug_of_war']:.0%}, "
                     f"V={self.weights['v_pattern']:.0%}, "
                     f"MOC={self.weights['moc_imbalance']:.0%}, "
                     f"NEWS={self.weights['news_temporal']:.0%}")

    def score_candidate(
        self,
        symbol: str,
        name: str,
        logic1_score: float,
        logic2_score: float,
        logic3_score: float,
        logic4_score: float,
        logic_details: Optional[Dict] = None,
    ) -> EnsembleResult:
        """
        단일 종목의 앙상블 점수 산출

        Args:
            symbol: 종목코드
            name: 종목명
            logic1_score: Tug of War 점수
            logic2_score: V자 수급전환 점수
            logic3_score: MOC Imbalance 점수
            logic4_score: 뉴스 Temporal Anomaly 점수
            logic_details: 로직별 상세 정보 (선택)

        Returns:
            EnsembleResult
        """
        details = logic_details or {}

        ensemble = calculate_ensemble_score(
            logic1_score, logic2_score, logic3_score, logic4_score
        )
        entry_tier, pos_mult = determine_entry_tier(ensemble)
        dominant = find_dominant_logic(
            logic1_score, logic2_score, logic3_score, logic4_score
        )

        logic_scores = [
            LogicScore("Tug of War", logic1_score, self.weights["tug_of_war"],
                        round(logic1_score * self.weights["tug_of_war"], 1),
                        details.get("tug_of_war", {})),
            LogicScore("V자 수급전환", logic2_score, self.weights["v_pattern"],
                        round(logic2_score * self.weights["v_pattern"], 1),
                        details.get("v_pattern", {})),
            LogicScore("MOC Imbalance", logic3_score, self.weights["moc_imbalance"],
                        round(logic3_score * self.weights["moc_imbalance"], 1),
                        details.get("moc_imbalance", {})),
            LogicScore("뉴스 Temporal", logic4_score, self.weights["news_temporal"],
                        round(logic4_score * self.weights["news_temporal"], 1),
                        details.get("news_temporal", {})),
        ]

        result = EnsembleResult(
            symbol=symbol,
            name=name,
            ensemble_score=ensemble,
            entry_tier=entry_tier,
            logic_scores=logic_scores,
            dominant_logic=dominant,
            position_multiplier=pos_mult,
        )

        logger.info(f"[ENSEMBLE] {name}({symbol}) | "
                     f"종합={ensemble:.1f} | 등급={entry_tier} | "
                     f"TOW={logic1_score:.0f} V={logic2_score:.0f} "
                     f"MOC={logic3_score:.0f} NEWS={logic4_score:.0f} | "
                     f"주도로직={dominant}")

        return result

    def rank_candidates(self, results: List[EnsembleResult]) -> List[EnsembleResult]:
        """
        앙상블 점수 기준 후보 순위화 (SKIP 제외)

        Args:
            results: EnsembleResult 리스트

        Returns:
            앙상블 점수 내림차순 정렬된 리스트 (SKIP 제외)
        """
        filtered = [r for r in results if r.entry_tier != "SKIP"]
        ranked = sorted(filtered, key=lambda r: r.ensemble_score, reverse=True)

        logger.info("=" * 60)
        logger.info(f"[ENSEMBLE] 순위화 완료: {len(ranked)}/{len(results)}개 진입 가능")
        for i, r in enumerate(ranked, 1):
            logger.info(f"  {i}. {r.name} | {r.ensemble_score:.1f}점 | {r.entry_tier}")
        logger.info("=" * 60)

        return ranked
