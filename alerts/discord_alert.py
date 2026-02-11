"""
Discord 알림 시스템 (v2.0)
6개 채널로 구분된 웹훅 기반 알림

채널 구조:
  #trading-signals     : 매수/매도 신호
  #v-pattern-alerts    : V자 반등 감지 알림
  #daily-report        : 일일 리포트
  #risk-alert          : 리스크 경고 (VETO, CAUTION, DANGER)
  #after-hours         : 장후 잔량/시간외 거래 알림
  #system-status       : 시스템 상태
"""
import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# Discord 웹훅 설정
# ═══════════════════════════════════════════════════════

WEBHOOK_URLS = {
    "trading_signals": os.getenv("DISCORD_WEBHOOK_TRADING", ""),
    "v_pattern_alerts": os.getenv("DISCORD_WEBHOOK_V_PATTERN", ""),
    "daily_report": os.getenv("DISCORD_WEBHOOK_DAILY_REPORT", ""),
    "risk_alert": os.getenv("DISCORD_WEBHOOK_RISK", ""),
    "after_hours": os.getenv("DISCORD_WEBHOOK_AFTER_HOURS", ""),
    "system_status": os.getenv("DISCORD_WEBHOOK_SYSTEM", ""),
}


class DiscordAlert:
    """Discord 웹훅 알림 발송기"""

    def __init__(self, webhooks: Dict[str, str] = None):
        self.webhooks = webhooks or WEBHOOK_URLS
        self.enabled = any(url for url in self.webhooks.values())
        if not self.enabled:
            logger.warning("[DISCORD] 웹훅 URL 미설정 — 알림 비활성화")
        else:
            active = sum(1 for url in self.webhooks.values() if url)
            logger.info(f"[DISCORD] 알림 시스템 초기화 ({active}개 채널)")

    def _send(self, channel: str, content: str) -> bool:
        """웹훅으로 메시지 전송"""
        url = self.webhooks.get(channel, "")
        if not url:
            logger.debug(f"[DISCORD] {channel} 웹훅 미설정 — 스킵")
            return False

        payload = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    logger.info(f"[DISCORD] {channel} 전송 성공")
                    return True
        except urllib.error.URLError as e:
            logger.error(f"[DISCORD] {channel} 전송 실패: {e}")
        except Exception as e:
            logger.error(f"[DISCORD] {channel} 전송 오류: {e}")

        return False

    # ═══════════════════════════════════════════════════
    # V자 반등 감지 알림
    # ═══════════════════════════════════════════════════

    def send_v_pattern_alert(self, data: Dict) -> bool:
        """V자 반등 감지 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**V자 반등 감지**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"현재가: {data.get('price', 0):,}원 ({data.get('change_pct', 0):+.1f}%)\n"
            f"V자 점수: {data.get('v_score', 0)}점 / 75점\n\n"
            f"MUST 조건 (전부 충족):\n"
            f"  저점 대비 반등: {data.get('rebound_pct', 0):.2f}%\n"
            f"  체결강도: {data.get('exec_str', 0):.0f}%\n"
            f"  프로그램 순매수: {data.get('prog_net', 0):+,}주\n\n"
            f"시간: {timestamp}"
        )
        return self._send("v_pattern_alerts", msg)

    # ═══════════════════════════════════════════════════
    # 매수 신호
    # ═══════════════════════════════════════════════════

    def send_buy_signal(self, data: Dict) -> bool:
        """매수 신호 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**매수 신호**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"매수가: {data.get('price', 0):,}원\n"
            f"수량: {data.get('quantity', 0):,}주\n"
            f"금액: {data.get('amount', 0):,}원\n"
            f"비중: {data.get('weight', 0):.1f}%\n\n"
            f"앙상블 점수: {data.get('ensemble', 0):.1f}점\n"
            f"  L1 Tug of War: {data.get('logic1', 0):.0f}점\n"
            f"  L2 V자 수급전환: {data.get('logic2', 0):.0f}점\n"
            f"  L3 MOC Imbalance: {data.get('logic3', 0):.0f}점\n"
            f"  L4 뉴스 Temporal: {data.get('logic4', 0):.0f}점\n"
            f"  지배 로직: {data.get('dominant_logic', '')}\n\n"
            f"PHASE 점수:\n"
            f"  PHASE 2 (기술적): {data.get('phase2_score', 0)}점\n"
            f"  PHASE 3 (심리적): {data.get('phase3_score', 0)}점\n"
            f"  PHASE 4 (V자): {data.get('v_score', 0)}점\n\n"
            f"거시 레짐: {data.get('regime', 'N/A')}\n"
            f"AI 신뢰도: {data.get('confidence', 0)}%\n\n"
            f"시간: {timestamp}"
        )
        return self._send("trading_signals", msg)

    # ═══════════════════════════════════════════════════
    # 청산 알림
    # ═══════════════════════════════════════════════════

    def send_exit_alert(self, data: Dict) -> bool:
        """청산 완료 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        pnl = data.get('pnl', 0)
        emoji = "수익" if pnl >= 0 else "손실"

        msg = (
            f"**청산 완료**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"매수가: {data.get('entry_price', 0):,}원 -> 매도가: {data.get('exit_price', 0):,}원\n"
            f"수익률: {data.get('pnl_pct', 0):+.2f}%\n"
            f"{emoji}: {pnl:+,}원\n\n"
            f"청산 시나리오: {data.get('scenario', '')}\n"
            f"청산 사유: {data.get('exit_reason', '')}\n\n"
            f"시간: {timestamp}"
        )
        return self._send("trading_signals", msg)

    # ═══════════════════════════════════════════════════
    # 장후 리스크 알림
    # ═══════════════════════════════════════════════════

    def send_after_hours_alert(self, data: Dict) -> bool:
        """장후 리스크 경고 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**장후 리스크 경고**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"매도잔량:매수잔량 = {data.get('sell_buy_ratio', 0):.1f}:1\n\n"
            f"조치: {data.get('action', '')}\n"
            f"  정리 수량: {data.get('sell_qty', 0):,}주 ({data.get('sell_pct', 0):.0f}%)\n"
            f"  사유: {data.get('reason', '')}\n\n"
            f"시간: {timestamp}"
        )
        return self._send("after_hours", msg)

    # ═══════════════════════════════════════════════════
    # 거시 레짐 변경 알림
    # ═══════════════════════════════════════════════════

    def send_regime_change_alert(self, data: Dict) -> bool:
        """시장 레짐 변경 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        policy = {
            "NORMAL": ("정상 운영", "정상 운영"),
            "CAUTION": ("비중 50% 축소", "기존 포지션 유지"),
            "DANGER": ("신규 진입 전면 금지", "전 포지션 청산"),
        }
        new_regime = data.get('new_regime', 'NORMAL')
        entry_policy, position_policy = policy.get(new_regime, ("N/A", "N/A"))

        msg = (
            f"**시장 레짐 변경**\n"
            f"{'━' * 24}\n"
            f"레짐: {data.get('prev_regime', '')} -> {new_regime}\n\n"
            f"트리거:\n"
            f"  코스피: {data.get('kospi_change', 0):+.1f}%\n"
            f"  미국선물: {data.get('us_futures', 0):+.1f}%\n"
            f"  VIX: {data.get('vix', 0):.1f}\n\n"
            f"정책 변경:\n"
            f"  신규 진입: {entry_policy}\n"
            f"  보유 포지션: {position_policy}\n\n"
            f"시간: {timestamp}"
        )
        return self._send("risk_alert", msg)

    # ═══════════════════════════════════════════════════
    # VETO 발동 알림
    # ═══════════════════════════════════════════════════

    def send_veto_alert(self, data: Dict) -> bool:
        """VETO 키워드 감지 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**VETO 발동**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"키워드: {data.get('keyword', '')}\n"
            f"카테고리: {data.get('category', '')}\n"
            f"출처: {data.get('source', '')}\n\n"
            f"조치: 즉시 제외 (재검토 불가)\n\n"
            f"시간: {timestamp}"
        )
        return self._send("risk_alert", msg)

    # ═══════════════════════════════════════════════════
    # 손절 알림
    # ═══════════════════════════════════════════════════

    def send_stop_loss_alert(self, data: Dict) -> bool:
        """손절 발동 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**손절 발동**\n"
            f"{'━' * 24}\n"
            f"종목: {data.get('symbol', '')} {data.get('name', '')}\n"
            f"유형: {data.get('type', '')}\n"
            f"우선순위: {data.get('priority', 'N/A')}\n"
            f"사유: {data.get('reason', '')}\n\n"
            f"조치: {data.get('action', '')}\n"
            f"수량: {data.get('quantity', 0):,}주\n\n"
            f"시간: {timestamp}"
        )
        return self._send("risk_alert", msg)

    # ═══════════════════════════════════════════════════
    # 일일 리포트
    # ═══════════════════════════════════════════════════

    def send_daily_report(self, report: str) -> bool:
        """일일 리포트 전송"""
        return self._send("daily_report", report)

    # ═══════════════════════════════════════════════════
    # 시스템 상태
    # ═══════════════════════════════════════════════════

    def send_system_status(self, message: str) -> bool:
        """시스템 상태 메시지 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"**시스템** [{timestamp}]\n{message}"
        return self._send("system_status", msg)

    def send_guard_alert(self, data: Dict) -> bool:
        """뇌동매매 가드 알림 전송"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"**뇌동매매 가드 발동**\n"
            f"{'━' * 24}\n"
            f"사유: {data.get('reason', '')}\n"
            f"상태: {data.get('status', '')}\n\n"
            f"시간: {timestamp}"
        )
        return self._send("risk_alert", msg)
