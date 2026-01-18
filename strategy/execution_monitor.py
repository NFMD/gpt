"""
체결 강도 및 프로그램 매매 모니터링 모듈

15:16-15:20 구간의 수급 전환을 실시간 포착합니다.
- 체결 강도 100%/150% 돌파 감지
- 프로그램 매매 순매수 전환 (매도 → 매수)
- 수급 역전 신호 강도 계산
"""
import logging
from datetime import datetime
from typing import Dict, Optional, List
from api import KISApi
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExecutionMonitor:
    """체결 강도 및 프로그램 매매 모니터"""

    def __init__(self, api: KISApi):
        self.api = api
        self.execution_history = {}  # 체결 강도 이력
        self.program_history = {}    # 프로그램 매매 이력

    def check_execution_strength(self, stock_code: str, stock_name: str = "") -> Optional[Dict]:
        """
        체결 강도 체크

        Args:
            stock_code: 종목코드
            stock_name: 종목명 (로깅용)

        Returns:
            체결 강도 분석 결과
        """
        try:
            execution_strength = self.api.get_execution_strength(stock_code)

            if execution_strength is None:
                logger.warning(f"⚠️  체결 강도 조회 실패: {stock_name} ({stock_code})")
                return None

            # 이력 저장
            if stock_code not in self.execution_history:
                self.execution_history[stock_code] = []

            self.execution_history[stock_code].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "strength": execution_strength
            })

            # 최근 5개만 유지
            if len(self.execution_history[stock_code]) > 5:
                self.execution_history[stock_code] = self.execution_history[stock_code][-5:]

            # 추세 분석 (상승 중인지 확인)
            is_rising = False
            if len(self.execution_history[stock_code]) >= 2:
                recent = self.execution_history[stock_code][-1]["strength"]
                previous = self.execution_history[stock_code][-2]["strength"]
                is_rising = recent > previous

            # 신호 강도 계산
            signal_strength = 0

            # 100% 돌파 시 +30점
            if execution_strength >= 100:
                signal_strength += 30
                logger.info(f"✅ 체결 강도 100% 돌파: {stock_name} ({execution_strength:.1f}%)")

            # 150% 이상 시 +50점 (강력한 매수세)
            if execution_strength >= 150:
                signal_strength += 50
                logger.info(f"🔥 체결 강도 150% 돌파: {stock_name} ({execution_strength:.1f}%)")

            # 상승 추세 시 +20점
            if is_rising:
                signal_strength += 20
                logger.info(f"📈 체결 강도 상승 추세: {stock_name}")

            return {
                "stock_code": stock_code,
                "execution_strength": execution_strength,
                "is_rising": is_rising,
                "signal_strength": signal_strength,
                "above_100": execution_strength >= 100,
                "above_150": execution_strength >= 150,
                "history": self.execution_history[stock_code],
            }

        except Exception as e:
            logger.error(f"❌ 체결 강도 체크 오류 ({stock_code}): {e}")
            return None

    def check_program_trading(self, stock_code: str, stock_name: str = "") -> Optional[Dict]:
        """
        프로그램 매매 전환 체크

        Args:
            stock_code: 종목코드
            stock_name: 종목명 (로깅용)

        Returns:
            프로그램 매매 분석 결과
        """
        try:
            program_data = self.api.get_program_trading(stock_code)

            if program_data is None:
                logger.debug(f"⚠️  프로그램 매매 조회 실패: {stock_name} ({stock_code})")
                return None

            # 이력 저장
            if stock_code not in self.program_history:
                self.program_history[stock_code] = []

            self.program_history[stock_code].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "net_buy": program_data["program_net_buy"]
            })

            # 최근 10개만 유지
            if len(self.program_history[stock_code]) > 10:
                self.program_history[stock_code] = self.program_history[stock_code][-10:]

            # 수급 전환 감지 (음수 → 양수)
            supply_reversal = False
            if len(self.program_history[stock_code]) >= 2:
                current = self.program_history[stock_code][-1]["net_buy"]
                previous = self.program_history[stock_code][-2]["net_buy"]

                # 이전에 매도였다가 현재 매수로 전환
                if previous < 0 and current > 0:
                    supply_reversal = True
                    logger.info(f"🔄 프로그램 매매 전환 감지: {stock_name} (매도 → 매수)")

            # 신호 강도 계산
            signal_strength = 0

            # 현재 순매수 중이면 +40점
            if program_data["program_net_buy"] > 0:
                signal_strength += 40

            # 수급 전환 감지 시 +60점 (매우 강력한 신호)
            if supply_reversal:
                signal_strength += 60
                logger.info(f"🚀 강력한 수급 전환: {stock_name}")

            # API의 supply_reversal도 체크
            if program_data.get("supply_reversal", False):
                signal_strength += 40

            return {
                "stock_code": stock_code,
                "program_net_buy": program_data["program_net_buy"],
                "supply_reversal": supply_reversal,
                "signal_strength": signal_strength,
                "is_net_buying": program_data["program_net_buy"] > 0,
                "recent_trend": program_data.get("recent_trend", []),
                "history": self.program_history[stock_code],
            }

        except Exception as e:
            logger.error(f"❌ 프로그램 매매 체크 오류 ({stock_code}): {e}")
            return None

    def get_supply_reversal_signal(
        self,
        stock_code: str,
        stock_name: str = ""
    ) -> Optional[Dict]:
        """
        수급 역전 종합 신호 (체결 강도 + 프로그램 매매)

        15:16-15:20 구간에서 다음 조건을 모두 만족할 때 강력한 진입 신호:
        1. 체결 강도 150% 이상
        2. 프로그램 매매 순매수 전환 (매도 → 매수)
        3. 체결 강도 상승 추세

        Args:
            stock_code: 종목코드
            stock_name: 종목명

        Returns:
            종합 신호 분석 결과
        """
        current_time = datetime.now().strftime("%H:%M")

        # 시간 체크 (15:16-15:20만 유효)
        if current_time < "15:16" or current_time > "15:20":
            logger.debug(f"⏰ 수급 전환 감지 시간 아님 (현재: {current_time})")
            return None

        logger.info("=" * 60)
        logger.info(f"🔍 수급 역전 신호 분석: {stock_name} ({stock_code})")
        logger.info(f"⏰ 현재 시각: {current_time}")
        logger.info("=" * 60)

        # 1. 체결 강도 체크
        execution_result = self.check_execution_strength(stock_code, stock_name)
        if execution_result is None:
            return None

        # 2. 프로그램 매매 체크
        program_result = self.check_program_trading(stock_code, stock_name)
        if program_result is None:
            # 프로그램 매매 데이터가 없어도 체결 강도만으로 판단 가능
            program_result = {
                "signal_strength": 0,
                "supply_reversal": False,
                "is_net_buying": False,
            }

        # 3. 종합 신호 강도 계산
        total_strength = (
            execution_result["signal_strength"] +
            program_result["signal_strength"]
        )

        # 4. 진입 조건 판단
        entry_signal = False
        entry_reason = []

        # 조건 1: 체결 강도 150% 이상 (필수)
        if execution_result["above_150"]:
            entry_reason.append("체결 강도 150% 이상")

        # 조건 2: 프로그램 매매 전환 또는 순매수 중
        if program_result["supply_reversal"]:
            entry_reason.append("프로그램 매매 전환 (매도→매수)")
        elif program_result["is_net_buying"]:
            entry_reason.append("프로그램 순매수 지속")

        # 조건 3: 체결 강도 상승 추세
        if execution_result["is_rising"]:
            entry_reason.append("체결 강도 상승 추세")

        # 최종 진입 판단
        # - 체결 강도 150% 이상 (필수)
        # - 총 신호 강도 80점 이상
        if execution_result["above_150"] and total_strength >= 80:
            entry_signal = True

        # 5. 결과 로깅
        logger.info(f"📊 체결 강도: {execution_result['execution_strength']:.1f}%")
        logger.info(f"📊 프로그램 순매수: {program_result.get('program_net_buy', 0):,}주")
        logger.info(f"📊 총 신호 강도: {total_strength}점")

        if entry_signal:
            logger.info("=" * 60)
            logger.info(f"🚀 강력한 진입 신호 발생!")
            logger.info(f"📋 진입 근거:")
            for idx, reason in enumerate(entry_reason, 1):
                logger.info(f"   {idx}. {reason}")
            logger.info("=" * 60)
        else:
            logger.info(f"⚠️  진입 조건 미달 (신호 강도: {total_strength}점)")

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "check_time": current_time,
            "execution_strength": execution_result["execution_strength"],
            "is_execution_rising": execution_result["is_rising"],
            "program_net_buy": program_result.get("program_net_buy", 0),
            "supply_reversal": program_result["supply_reversal"],
            "total_signal_strength": total_strength,
            "entry_signal": entry_signal,
            "entry_reason": entry_reason,
            "execution_detail": execution_result,
            "program_detail": program_result,
        }

    def clear_history(self):
        """이력 초기화"""
        self.execution_history = {}
        self.program_history = {}
        logger.info("✅ 수급 모니터링 이력 초기화")
