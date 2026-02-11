"""
뇌동매매 방지 가드 (v2.0)
리스크 관리 영역 5: 매매 시간 및 행동 통제

규칙:
- 10시 이후 수동 매매 비활성화
- 하루 최대 진입 3회
- 연속 3연패 시 익일 매매 금지
- 일일 최대 손실 -5% 도달 시 당일 종료
"""
import logging
from datetime import datetime, date
from typing import Tuple, List
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 매매 허용 시간 윈도우
# ═══════════════════════════════════════════════════════

TRADING_WINDOWS = {
    "exit_mode": {
        "start": "08:30",
        "end": "10:00",
        "actions": ["SELL"],
        "description": "청산 모드: 매도만 가능",
    },
    "data_only": {
        "start": "10:00",
        "end": "14:30",
        "actions": [],
        "description": "데이터 수집 전용: 매매 금지",
    },
    "entry_mode": {
        "start": "14:30",
        "end": "15:20",
        "actions": ["BUY"],
        "description": "진입 모드: 매수만 가능",
    },
    "after_hours_risk": {
        "start": "15:30",
        "end": "18:00",
        "actions": ["SELL"],
        "description": "장후 리스크 관리: 매도만 가능",
    },
    "ats_mode": {
        "start": "19:00",
        "end": "20:00",
        "actions": ["BUY"],
        "description": "(선택) ATS 추가 매수",
    },
}


# ═══════════════════════════════════════════════════════
# 취약 패턴 배제 리스트
# ═══════════════════════════════════════════════════════

EXCLUDED_PATTERNS = [
    "낙주 매매 (하락 중 역매매)",
    "시가 배팅 (장 시작 직후 매수)",
    "상한가 따라잡기",
    "테마 후발주 추격 매수",
    "동시호가 직전 급등주 추격",
    "손절 후 즉시 재진입 (복수 매매)",
]


# ═══════════════════════════════════════════════════════
# 수익금 인출 규칙
# ═══════════════════════════════════════════════════════

WITHDRAWAL_RULES = {
    "frequency": "weekly",
    "percentage": 0.20,
    "min_withdrawal": 100_000,
    "purpose": "실물 현금 확인 → 뇌동매매 방지 + 심리적 안정",
    "trigger": "weekly_pnl > 0",
}


def is_action_allowed(current_time: str, action: str) -> bool:
    """
    현재 시간에 해당 액션이 허용되는지 확인

    Args:
        current_time: "HH:MM" 또는 "HH:MM:SS" 형식
        action: "BUY" 또는 "SELL"

    Returns:
        허용 여부
    """
    time_str = current_time[:5]  # HH:MM
    for window in TRADING_WINDOWS.values():
        if window["start"] <= time_str <= window["end"]:
            return action in window["actions"]
    return False


def get_current_window(current_time: str) -> dict:
    """현재 시간대의 매매 윈도우 정보 반환"""
    time_str = current_time[:5]
    for name, window in TRADING_WINDOWS.items():
        if window["start"] <= time_str <= window["end"]:
            return {"name": name, **window}
    return {"name": "closed", "start": "", "end": "", "actions": [], "description": "매매 불가 시간"}


class BrainTradeGuard:
    """뇌동매매 방지 가드"""

    def __init__(self):
        self.daily_entry_count = 0
        self.max_daily_entries = 3
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        self.daily_loss_pct = 0.0
        self.max_daily_loss_pct = -5.0
        self.last_reset_date = date.today()
        self.trade_log: List[dict] = []
        logger.info("[GUARD] BrainTradeGuard 초기화 완료")

    def _auto_reset(self):
        """날짜 변경 시 자동 초기화"""
        today = date.today()
        if today != self.last_reset_date:
            self.reset_daily()
            self.last_reset_date = today

    def can_enter(self, current_time: str) -> Tuple[bool, str]:
        """
        신규 진입 가능 여부 판단

        Returns:
            (allowed, reason)
        """
        self._auto_reset()

        # 시간 체크
        if not is_action_allowed(current_time, "BUY"):
            window = get_current_window(current_time)
            return False, f"현재 시간({current_time}) 매수 불가 구간 ({window['description']})"

        # 일일 진입 횟수 체크
        if self.daily_entry_count >= self.max_daily_entries:
            return False, f"일일 진입 한도 도달 ({self.daily_entry_count}/{self.max_daily_entries})"

        # 연속 손실 체크
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"연속 {self.consecutive_losses}패 → 익일까지 매매 금지"

        # 일일 최대 손실 체크
        if self.daily_loss_pct <= self.max_daily_loss_pct:
            return False, f"일일 손실 한도 도달 ({self.daily_loss_pct:.1f}%)"

        return True, "진입 가능"

    def can_exit(self, current_time: str) -> Tuple[bool, str]:
        """매도 가능 여부 판단 (청산은 거의 항상 허용)"""
        if is_action_allowed(current_time, "SELL"):
            return True, "매도 가능"
        # 비상 청산은 시간 무관 허용
        return True, "비상 청산 허용"

    def record_entry(self):
        """진입 기록"""
        self._auto_reset()
        self.daily_entry_count += 1
        logger.info(f"[GUARD] 진입 기록 ({self.daily_entry_count}/{self.max_daily_entries})")

    def record_trade_result(self, pnl_pct: float, symbol: str = ""):
        """거래 결과 기록"""
        self._auto_reset()
        self.daily_loss_pct += pnl_pct

        if pnl_pct < 0:
            self.consecutive_losses += 1
            logger.info(f"[GUARD] 손실 기록: {pnl_pct:+.2f}% | 연패={self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
            logger.info(f"[GUARD] 수익 기록: {pnl_pct:+.2f}% | 연패 초기화")

        self.trade_log.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "pnl_pct": pnl_pct,
        })

    def reset_daily(self):
        """일일 초기화"""
        self.daily_entry_count = 0
        self.daily_loss_pct = 0.0
        self.trade_log.clear()
        logger.info("[GUARD] 일일 초기화 완료")

    def get_status(self) -> dict:
        """현재 가드 상태 반환"""
        return {
            "daily_entries": f"{self.daily_entry_count}/{self.max_daily_entries}",
            "consecutive_losses": self.consecutive_losses,
            "daily_loss_pct": round(self.daily_loss_pct, 2),
            "is_locked": (
                self.consecutive_losses >= self.max_consecutive_losses
                or self.daily_loss_pct <= self.max_daily_loss_pct
            ),
        }
