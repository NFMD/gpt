"""
시간외 거래 리스크 관리 모듈

15:50-15:59 구간의 매도 잔량 급증을 감지하여
익일 갭 하락 리스크를 사전 차단합니다.

16:00-18:00 시간외 단일가에서 급등/급락 시
적절한 대응을 제안합니다.
"""
import logging
from datetime import datetime
from typing import Dict, Optional, List
from api import KISApi
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AfterHoursMonitor:
    """시간외 거래 모니터"""

    def __init__(self, api: KISApi):
        self.api = api
        self.monitored_stocks = {}  # 모니터링 중인 종목

    def add_monitored_stock(
        self,
        stock_code: str,
        stock_name: str,
        buy_price: int,
        buy_quantity: int
    ):
        """
        모니터링 대상 종목 추가

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            buy_price: 매수가
            buy_quantity: 매수 수량
        """
        self.monitored_stocks[stock_code] = {
            "stock_name": stock_name,
            "buy_price": buy_price,
            "buy_quantity": buy_quantity,
            "added_time": datetime.now().strftime("%H:%M:%S"),
        }
        logger.info(f"✅ 시간외 모니터링 추가: {stock_name} ({buy_quantity}주 @ {buy_price:,}원)")

    def check_closing_risk(
        self,
        stock_code: str,
        stock_name: str = ""
    ) -> Optional[Dict]:
        """
        장 마감 직후 리스크 체크 (15:50-15:59)

        매도 잔량이 매수 잔량의 2배 이상이면
        시간외 단일가 하락 위험 신호

        Args:
            stock_code: 종목코드
            stock_name: 종목명

        Returns:
            리스크 분석 결과
        """
        current_time = datetime.now().strftime("%H:%M")

        # 시간 체크
        if current_time < "15:50" or current_time > "15:59":
            logger.debug(f"⏰ 장 마감 리스크 체크 시간 아님 (현재: {current_time})")
            return None

        logger.info("=" * 60)
        logger.info(f"⚠️  장 마감 직후 리스크 체크: {stock_name} ({stock_code})")
        logger.info(f"⏰ 현재 시각: {current_time}")
        logger.info("=" * 60)

        try:
            # 호가창 조회
            order_book = self.api.get_order_book(stock_code)

            if order_book is None:
                logger.warning(f"⚠️  호가창 조회 실패: {stock_name}")
                return None

            sell_buy_ratio = order_book["sell_buy_ratio"]
            total_sell_quantity = order_book["total_sell_quantity"]
            total_buy_quantity = order_book["total_buy_quantity"]

            # 리스크 판단
            risk_level = "안전"
            action_required = None

            # 위험 신호: 매도 잔량 >> 매수 잔량
            if sell_buy_ratio >= 2.0:
                risk_level = "높음"
                action_required = "부분_매도"
                logger.warning(
                    f"🚨 높은 리스크 감지!\n"
                    f"   매도/매수 비율: {sell_buy_ratio:.2f}:1\n"
                    f"   매도 잔량: {total_sell_quantity:,}주\n"
                    f"   매수 잔량: {total_buy_quantity:,}주\n"
                    f"   ⚠️  권장 조치: 보유 물량 50% 긴급 매도"
                )
            elif sell_buy_ratio >= 1.5:
                risk_level = "중간"
                action_required = "관찰"
                logger.info(
                    f"⚠️  중간 리스크\n"
                    f"   매도/매수 비율: {sell_buy_ratio:.2f}:1\n"
                    f"   권장 조치: 시간외 단일가 주의 관찰"
                )
            else:
                logger.info(
                    f"✅ 안전 수준\n"
                    f"   매도/매수 비율: {sell_buy_ratio:.2f}:1"
                )

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "check_time": current_time,
                "sell_buy_ratio": sell_buy_ratio,
                "total_sell_quantity": total_sell_quantity,
                "total_buy_quantity": total_buy_quantity,
                "risk_level": risk_level,
                "action_required": action_required,
            }

        except Exception as e:
            logger.error(f"❌ 장 마감 리스크 체크 오류 ({stock_code}): {e}")
            return None

    def check_after_hours_price(
        self,
        stock_code: str,
        stock_name: str = "",
        buy_price: int = 0
    ) -> Optional[Dict]:
        """
        시간외 단일가 모니터링 (16:00-18:00)

        4% 이상 급등 시 분할 익절
        손실 발생 시 손절 권고

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            buy_price: 매수가

        Returns:
            시간외 가격 분석 결과
        """
        current_time = datetime.now().strftime("%H:%M")

        # 시간 체크
        if current_time < "16:00" or current_time > "18:00":
            logger.debug(f"⏰ 시간외 거래 시간 아님 (현재: {current_time})")
            return None

        try:
            # 현재가 조회
            price_info = self.api.get_stock_price(stock_code)

            if price_info is None:
                logger.warning(f"⚠️  시세 조회 실패: {stock_name}")
                return None

            current_price = price_info["current_price"]

            # 수익률 계산
            if buy_price > 0:
                profit_rate = ((current_price - buy_price) / buy_price) * 100
            else:
                profit_rate = 0

            # 액션 판단
            action_required = None
            action_reason = ""

            # 4% 이상 급등 시 익절
            if profit_rate >= 4.0:
                action_required = "부분_익절"
                action_reason = f"시간외 {profit_rate:.2f}% 급등, 70% 익절 권장"
                logger.info(
                    f"🎯 시간외 급등 감지: {stock_name}\n"
                    f"   매수가: {buy_price:,}원\n"
                    f"   현재가: {current_price:,}원\n"
                    f"   수익률: +{profit_rate:.2f}%\n"
                    f"   💰 권장 조치: 보유 물량 70% 익절"
                )

            # 2% 이상 손실 시 손절
            elif profit_rate <= -2.0:
                action_required = "손절"
                action_reason = f"시간외 {profit_rate:.2f}% 하락, 손절 권장"
                logger.warning(
                    f"⚠️  시간외 하락: {stock_name}\n"
                    f"   매수가: {buy_price:,}원\n"
                    f"   현재가: {current_price:,}원\n"
                    f"   수익률: {profit_rate:.2f}%\n"
                    f"   🛑 권장 조치: 전량 손절"
                )

            # 정상 범위
            else:
                logger.info(
                    f"📊 시간외 정상 범위: {stock_name}\n"
                    f"   현재가: {current_price:,}원\n"
                    f"   수익률: {profit_rate:+.2f}%"
                )

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "check_time": current_time,
                "buy_price": buy_price,
                "current_price": current_price,
                "profit_rate": profit_rate,
                "action_required": action_required,
                "action_reason": action_reason,
            }

        except Exception as e:
            logger.error(f"❌ 시간외 가격 체크 오류 ({stock_code}): {e}")
            return None

    def monitor_all_holdings(self) -> List[Dict]:
        """
        모든 보유 종목 시간외 모니터링

        Returns:
            모니터링 결과 리스트
        """
        current_time = datetime.now().strftime("%H:%M")

        results = []

        if not self.monitored_stocks:
            logger.info("⏰ 모니터링 대상 종목 없음")
            return results

        logger.info("=" * 60)
        logger.info(f"🔍 시간외 전체 종목 모니터링 ({current_time})")
        logger.info(f"📊 모니터링 종목 수: {len(self.monitored_stocks)}개")
        logger.info("=" * 60)

        for stock_code, info in self.monitored_stocks.items():
            stock_name = info["stock_name"]
            buy_price = info["buy_price"]
            buy_quantity = info["buy_quantity"]

            # 15:50-15:59: 리스크 체크
            if "15:50" <= current_time <= "15:59":
                result = self.check_closing_risk(stock_code, stock_name)

            # 16:00-18:00: 시간외 단일가 체크
            elif "16:00" <= current_time <= "18:00":
                result = self.check_after_hours_price(stock_code, stock_name, buy_price)

            else:
                logger.debug(f"⏰ 시간외 모니터링 시간 아님 (현재: {current_time})")
                continue

            if result:
                result["buy_quantity"] = buy_quantity
                results.append(result)

        logger.info("=" * 60)
        logger.info(f"✅ 모니터링 완료 ({len(results)}개 종목 분석)")
        logger.info("=" * 60)

        return results

    def execute_risk_action(
        self,
        stock_code: str,
        action: str,
        quantity: int
    ) -> bool:
        """
        리스크 대응 액션 실행

        Args:
            stock_code: 종목코드
            action: 액션 종류 (부분_매도, 부분_익절, 손절)
            quantity: 보유 수량

        Returns:
            실행 성공 여부
        """
        try:
            if action == "부분_매도":
                # 50% 매도
                sell_quantity = int(quantity * 0.5)
                logger.info(f"🔄 긴급 부분 매도 실행: {sell_quantity}주 (50%)")
                return self.api.place_order(stock_code, sell_quantity, 0, "sell")

            elif action == "부분_익절":
                # 70% 익절
                sell_quantity = int(quantity * 0.7)
                logger.info(f"💰 시간외 익절 실행: {sell_quantity}주 (70%)")
                return self.api.place_order(stock_code, sell_quantity, 0, "sell")

            elif action == "손절":
                # 전량 손절
                logger.info(f"🛑 시간외 손절 실행: {quantity}주 (100%)")
                return self.api.place_order(stock_code, quantity, 0, "sell")

            return False

        except Exception as e:
            logger.error(f"❌ 리스크 액션 실행 오류: {e}")
            return False

    def clear_monitored_stocks(self):
        """모니터링 종목 초기화"""
        self.monitored_stocks = {}
        logger.info("✅ 시간외 모니터링 종목 초기화")
