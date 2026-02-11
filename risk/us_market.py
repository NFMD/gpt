"""
미국 증시 상관관계 체크 모듈 (v2.0)
리스크 관리 영역 3: 거시 환경 필터링 보조

미국선물/VIX 기반 리스크 판단 및 야간 돌발 악재 대응
"""
import logging
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_us_market_correlation(
    us_futures_change: float,
    us_close_change: float = 0.0,
    vix: float = 15.0,
) -> Dict:
    """
    미국 증시 상관관계 기반 리스크 판단

    Returns:
        {
            "risk_level": "NORMAL" | "CAUTION" | "DANGER",
            "weight_multiplier": float (0.0~1.0),
            "reason": str,
        }
    """
    risk_level = "NORMAL"
    weight_multiplier = 1.0
    reasons = []

    # 미국 선물 급락
    if us_futures_change <= -2.0:
        risk_level = "DANGER"
        weight_multiplier = 0.0
        reasons.append(f"미국선물 {us_futures_change:.1f}% 급락")
    elif us_futures_change <= -1.0:
        risk_level = "CAUTION"
        weight_multiplier = 0.5
        reasons.append(f"미국선물 {us_futures_change:.1f}% 하락")

    # VIX 급등
    if vix >= 30:
        risk_level = "DANGER"
        weight_multiplier = 0.0
        reasons.append(f"VIX {vix:.1f} (공포)")
    elif vix >= 25:
        if risk_level != "DANGER":
            risk_level = "CAUTION"
            weight_multiplier = min(weight_multiplier, 0.5)
            reasons.append(f"VIX {vix:.1f} (경계)")

    # 전일 미국 종가 연계
    if us_close_change <= -3.0:
        if risk_level != "DANGER":
            risk_level = "DANGER"
            weight_multiplier = 0.0
        reasons.append(f"전일 미국 종가 {us_close_change:.1f}% 급락")
    elif us_close_change <= -1.5:
        if risk_level == "NORMAL":
            risk_level = "CAUTION"
            weight_multiplier = min(weight_multiplier, 0.7)
        reasons.append(f"전일 미국 종가 {us_close_change:.1f}% 하락")

    reason = " / ".join(reasons) if reasons else "미국 시장 정상"

    if risk_level != "NORMAL":
        logger.warning(f"[US] {risk_level}: {reason}")

    return {
        "risk_level": risk_level,
        "weight_multiplier": weight_multiplier,
        "reason": reason,
    }


# ═══════════════════════════════════════════════════════
# 야간 돌발 악재 대응 시나리오
# ═══════════════════════════════════════════════════════

OVERNIGHT_RISK_SCENARIOS = {
    "geopolitical": {
        "name": "지정학적 리스크",
        "trigger": "전쟁, 제재 등",
        "timing": "08:30 동시호가",
        "action": "예상 갭 -3% 이상 시 시가 전량 매도",
    },
    "earnings_shock": {
        "name": "글로벌 기업 어닝쇼크",
        "trigger": "대형 기업 실적 쇼크",
        "timing": "08:30 동시호가",
        "action": "관련 섹터 종목만 매도, 나머지 관찰",
    },
    "rate_hike": {
        "name": "미국 금리 인상",
        "trigger": "FOMC 결정",
        "timing": "08:30 동시호가",
        "action": "레짐 재판단 → CAUTION/DANGER 전환",
    },
    "domestic_policy": {
        "name": "국내 정책 리스크",
        "trigger": "정부 정책 발표",
        "timing": "08:30 동시호가",
        "action": "관련 종목 매도, 비관련 종목 관찰",
    },
}


def assess_overnight_risk(
    expected_gap_pct: float,
    us_close_change: float,
    vix: float,
    has_geopolitical_event: bool = False,
) -> Dict:
    """
    야간 돌발 악재 종합 평가 (08:30 동시호가 시점)

    Returns:
        {
            "action": "SELL_ALL" | "SELL_SECTOR" | "HOLD" | "OBSERVE",
            "urgency": "HIGH" | "MEDIUM" | "LOW",
            "reason": str,
        }
    """
    # 지정학적 리스크 + 대형 갭하락
    if has_geopolitical_event and expected_gap_pct <= -3.0:
        return {
            "action": "SELL_ALL",
            "urgency": "HIGH",
            "reason": f"지정학적 리스크 + 예상갭 {expected_gap_pct:+.1f}%",
        }

    # 대형 갭하락
    if expected_gap_pct <= -3.0:
        return {
            "action": "SELL_ALL",
            "urgency": "HIGH",
            "reason": f"예상 갭하락 {expected_gap_pct:+.1f}% — 전량 매도",
        }

    # 미국 종가 급락 + VIX 급등
    if us_close_change <= -2.0 and vix >= 28:
        return {
            "action": "SELL_ALL",
            "urgency": "HIGH",
            "reason": f"미국 {us_close_change:+.1f}% + VIX {vix:.0f}",
        }

    # 보통 수준 하락
    if expected_gap_pct <= -1.5:
        return {
            "action": "OBSERVE",
            "urgency": "MEDIUM",
            "reason": f"예상갭 {expected_gap_pct:+.1f}% — 시초가 관찰",
        }

    return {
        "action": "HOLD",
        "urgency": "LOW",
        "reason": "야간 특이사항 없음",
    }
