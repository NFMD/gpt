"""
거시 환경 필터 모듈 (v2.0)
시장 레짐을 판단하고 포지션 비중을 조정합니다.

NORMAL  → 정상 운영
CAUTION → 비중 50% 축소
DANGER  → 신규 진입 금지
"""
import logging
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    NORMAL = "NORMAL"       # 정상 운영
    CAUTION = "CAUTION"     # 비중 50% 축소
    DANGER = "DANGER"       # 신규 진입 금지


@dataclass
class MacroSnapshot:
    """거시 지표 스냅샷"""
    timestamp: str
    kospi_change: float      # 코스피 등락률 (%)
    kosdaq_change: float     # 코스닥 등락률 (%)
    us_futures_change: float  # 미국선물 등락률 (%)
    vix: float               # VIX 지수
    usd_krw_change: float = 0.0  # 원/달러 등락률 (%)


# ── 거시 필터 임계값 ──
DANGER_THRESHOLDS = {
    "kospi_drop": -2.0,          # 코스피 -2% 이상 하락
    "us_futures_drop": -2.0,     # 미국선물 -2% 이상 급락
    "vix_panic": 30.0,           # VIX 30 이상 (공포)
}

CAUTION_THRESHOLDS = {
    "kospi_drop": -1.0,          # 코스피 -1% 이상 하락
    "us_futures_drop": -1.0,     # 미국선물 -1% 이상 하락
    "vix_alert": 25.0,           # VIX 25 이상 (경계)
}


def assess_market_regime(
    kospi_change: float,
    kosdaq_change: float,
    us_futures_change: float,
    vix: float,
) -> MarketRegime:
    """
    거시 환경 기반 시장 레짐 판단

    Args:
        kospi_change: 코스피 등락률 (%)
        kosdaq_change: 코스닥 등락률 (%)
        us_futures_change: 미국선물 등락률 (%)
        vix: VIX 지수

    Returns:
        MarketRegime: 현재 시장 상태
    """
    # ── DANGER 조건 (하나라도 해당 시 신규 진입 금지) ──
    danger_conditions = [
        kospi_change <= DANGER_THRESHOLDS["kospi_drop"],
        us_futures_change <= DANGER_THRESHOLDS["us_futures_drop"],
        vix >= DANGER_THRESHOLDS["vix_panic"],
    ]
    if any(danger_conditions):
        triggered = []
        if kospi_change <= DANGER_THRESHOLDS["kospi_drop"]:
            triggered.append(f"KOSPI {kospi_change:+.1f}%")
        if us_futures_change <= DANGER_THRESHOLDS["us_futures_drop"]:
            triggered.append(f"US선물 {us_futures_change:+.1f}%")
        if vix >= DANGER_THRESHOLDS["vix_panic"]:
            triggered.append(f"VIX {vix:.1f}")
        logger.warning(f"[MACRO] DANGER 발동: {', '.join(triggered)}")
        return MarketRegime.DANGER

    # ── CAUTION 조건 (하나라도 해당 시 비중 50% 축소) ──
    caution_conditions = [
        kospi_change <= CAUTION_THRESHOLDS["kospi_drop"],
        us_futures_change <= CAUTION_THRESHOLDS["us_futures_drop"],
        vix >= CAUTION_THRESHOLDS["vix_alert"],
        (kospi_change < 0 and kosdaq_change < 0),  # 양시장 동반하락
    ]
    if any(caution_conditions):
        triggered = []
        if kospi_change <= CAUTION_THRESHOLDS["kospi_drop"]:
            triggered.append(f"KOSPI {kospi_change:+.1f}%")
        if us_futures_change <= CAUTION_THRESHOLDS["us_futures_drop"]:
            triggered.append(f"US선물 {us_futures_change:+.1f}%")
        if vix >= CAUTION_THRESHOLDS["vix_alert"]:
            triggered.append(f"VIX {vix:.1f}")
        if kospi_change < 0 and kosdaq_change < 0:
            triggered.append("양시장 동반하락")
        logger.warning(f"[MACRO] CAUTION 발동: {', '.join(triggered)}")
        return MarketRegime.CAUTION

    logger.info("[MACRO] NORMAL: 거시 환경 정상")
    return MarketRegime.NORMAL


def adjust_position_by_regime(
    base_weight: float,
    regime: MarketRegime
) -> float:
    """
    레짐에 따른 포지션 비중 조정

    Args:
        base_weight: 기본 포지션 비중 (0~1)
        regime: 시장 레짐

    Returns:
        조정된 포지션 비중
    """
    multipliers = {
        MarketRegime.NORMAL: 1.0,
        MarketRegime.CAUTION: 0.5,
        MarketRegime.DANGER: 0.0,     # 신규 진입 금지
    }
    adjusted = base_weight * multipliers[regime]
    logger.info(f"[MACRO] 포지션 조정: {base_weight:.1%} → {adjusted:.1%} ({regime.value})")
    return adjusted


class MacroFilter:
    """거시 환경 필터 (v2.0)"""

    def __init__(self):
        self.current_regime = MarketRegime.NORMAL
        self.last_snapshot: Optional[MacroSnapshot] = None
        self.regime_history: list = []
        logger.info("[MACRO] MacroFilter (v2.0) 초기화 완료")

    def update(
        self,
        kospi_change: float = 0.0,
        kosdaq_change: float = 0.0,
        us_futures_change: float = 0.0,
        vix: float = 15.0,
        usd_krw_change: float = 0.0,
    ) -> MarketRegime:
        """
        거시 지표 갱신 및 레짐 재판단

        Returns:
            현재 MarketRegime
        """
        self.last_snapshot = MacroSnapshot(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            kospi_change=kospi_change,
            kosdaq_change=kosdaq_change,
            us_futures_change=us_futures_change,
            vix=vix,
            usd_krw_change=usd_krw_change,
        )

        new_regime = assess_market_regime(
            kospi_change, kosdaq_change, us_futures_change, vix
        )

        if new_regime != self.current_regime:
            logger.warning(
                f"[MACRO] 레짐 전환: {self.current_regime.value} → {new_regime.value}"
            )

        self.current_regime = new_regime
        self.regime_history.append({
            "timestamp": self.last_snapshot.timestamp,
            "regime": new_regime.value,
            "kospi": kospi_change,
            "us_futures": us_futures_change,
            "vix": vix,
        })

        return new_regime

    def get_position_multiplier(self) -> float:
        """현재 레짐 기반 포지션 배수 반환"""
        multipliers = {
            MarketRegime.NORMAL: 1.0,
            MarketRegime.CAUTION: 0.5,
            MarketRegime.DANGER: 0.0,
        }
        return multipliers[self.current_regime]

    def is_entry_allowed(self) -> bool:
        """신규 진입 가능 여부"""
        return self.current_regime != MarketRegime.DANGER

    def should_reduce_existing(self) -> bool:
        """기존 포지션 축소 필요 여부"""
        return self.current_regime == MarketRegime.DANGER

    def get_regime_summary(self) -> Dict:
        """현재 레짐 요약"""
        snapshot = self.last_snapshot
        return {
            "regime": self.current_regime.value,
            "entry_allowed": self.is_entry_allowed(),
            "position_multiplier": self.get_position_multiplier(),
            "snapshot": {
                "kospi_change": snapshot.kospi_change if snapshot else None,
                "kosdaq_change": snapshot.kosdaq_change if snapshot else None,
                "us_futures_change": snapshot.us_futures_change if snapshot else None,
                "vix": snapshot.vix if snapshot else None,
            } if snapshot else None,
        }
