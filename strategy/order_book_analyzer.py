"""
호가창 역설 지표 분석 모듈

매도 잔량이 매수 잔량보다 압도적으로 많은 상태에서
주가가 밀리지 않고 위로 올라가는 '역설적 신호'를 포착합니다.

이는 강력한 매수세가 상단 물량을 소화하며
올라가려는 의지를 나타냅니다.
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from api import KISApi


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderBookAnalyzer:
    """호가창 역설 지표 분석기"""

    def __init__(self, api: KISApi):
        self.api = api
        self.price_history = {}  # 가격 이력

    def check_paradox_signal(
        self,
        stock_code: str,
        stock_name: str = "",
        min_ratio: float = 2.0
    ) -> Optional[Dict]:
        """
        호가창 역설 신호 체크

        매도 잔량 > 매수 잔량 * 2.0 상태에서
        주가가 밀리지 않으면 강력한 매수세로 판단

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            min_ratio: 최소 매도/매수 비율 (기본: 2.0)

        Returns:
            호가창 역설 분석 결과
        """
        try:
            # 호가창 데이터 조회
            order_book = self.api.get_order_book(stock_code)

            if order_book is None:
                logger.warning(f"⚠️  호가창 조회 실패: {stock_name} ({stock_code})")
                return None

            # 현재가 조회
            price_info = self.api.get_stock_price(stock_code)

            if price_info is None:
                logger.warning(f"⚠️  현재가 조회 실패: {stock_name} ({stock_code})")
                return None

            current_price = price_info["current_price"]

            # 가격 이력 저장
            if stock_code not in self.price_history:
                self.price_history[stock_code] = []

            self.price_history[stock_code].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "price": current_price
            })

            # 최근 5개만 유지
            if len(self.price_history[stock_code]) > 5:
                self.price_history[stock_code] = self.price_history[stock_code][-5:]

            # 가격 추세 분석
            price_rising = False
            price_stable = False

            if len(self.price_history[stock_code]) >= 2:
                recent_price = self.price_history[stock_code][-1]["price"]
                previous_price = self.price_history[stock_code][-2]["price"]

                # 상승 중
                if recent_price > previous_price:
                    price_rising = True

                # 안정적 (±0.5% 이내)
                price_change_rate = ((recent_price - previous_price) / previous_price) * 100
                if abs(price_change_rate) <= 0.5:
                    price_stable = True

            # 호가창 분석
            sell_buy_ratio = order_book["sell_buy_ratio"]
            total_sell_quantity = order_book["total_sell_quantity"]
            total_buy_quantity = order_book["total_buy_quantity"]

            # 역설 조건 체크
            paradox_detected = False
            signal_strength = 0

            # 조건 1: 매도 잔량이 매수 잔량의 2배 이상
            if sell_buy_ratio >= min_ratio:
                paradox_detected = True

                # 조건 2: 가격이 상승 중이거나 안정적
                if price_rising:
                    signal_strength = 80  # 강력한 신호
                    logger.info(
                        f"🔥 호가창 역설 + 가격 상승: {stock_name}\n"
                        f"   매도/매수 비율: {sell_buy_ratio:.2f}:1\n"
                        f"   매도 잔량: {total_sell_quantity:,}주\n"
                        f"   매수 잔량: {total_buy_quantity:,}주\n"
                        f"   현재가: {current_price:,}원 (상승 중)"
                    )
                elif price_stable:
                    signal_strength = 60  # 중간 신호
                    logger.info(
                        f"⚠️  호가창 역설 + 가격 안정: {stock_name}\n"
                        f"   매도/매수 비율: {sell_buy_ratio:.2f}:1\n"
                        f"   현재가: {current_price:,}원 (안정)"
                    )
                else:
                    signal_strength = 20  # 약한 신호 (가격 하락 중)
                    logger.debug(
                        f"📊 호가창 역설 감지 (가격 하락 중): {stock_name}\n"
                        f"   매도/매수 비율: {sell_buy_ratio:.2f}:1"
                    )

            # 상위 호가 분석 (매도 1호가 vs 매수 1호가)
            best_sell_price = order_book["best_sell_price"]
            best_buy_price = order_book["best_buy_price"]
            spread = best_sell_price - best_buy_price
            spread_rate = (spread / best_buy_price) * 100 if best_buy_price > 0 else 0

            # 스프레드가 좁으면 (+) 신호
            if spread_rate <= 0.5:  # 0.5% 이내
                signal_strength += 10
                logger.debug(f"✅ 좁은 호가 스프레드: {spread_rate:.2f}%")

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "check_time": datetime.now().strftime("%H:%M:%S"),
                "current_price": current_price,
                "sell_buy_ratio": sell_buy_ratio,
                "total_sell_quantity": total_sell_quantity,
                "total_buy_quantity": total_buy_quantity,
                "paradox_detected": paradox_detected,
                "price_rising": price_rising,
                "price_stable": price_stable,
                "signal_strength": signal_strength,
                "best_sell_price": best_sell_price,
                "best_buy_price": best_buy_price,
                "spread_rate": spread_rate,
                "order_book": order_book,
            }

        except Exception as e:
            logger.error(f"❌ 호가창 역설 분석 오류 ({stock_code}): {e}")
            return None

    def analyze_order_imbalance(
        self,
        stock_code: str,
        stock_name: str = ""
    ) -> Optional[Dict]:
        """
        호가 불균형 분석

        상위 5단계 호가의 매수/매도 물량 불균형을 분석하여
        단기 방향성을 예측합니다.

        Args:
            stock_code: 종목코드
            stock_name: 종목명

        Returns:
            호가 불균형 분석 결과
        """
        try:
            order_book = self.api.get_order_book(stock_code)

            if order_book is None:
                return None

            sell_orders = order_book["sell_orders"][:5]  # 상위 5단계
            buy_orders = order_book["buy_orders"][:5]

            # 상위 5단계 물량 합계
            top5_sell_qty = sum(order["quantity"] for order in sell_orders)
            top5_buy_qty = sum(order["quantity"] for order in buy_orders)

            # 불균형 비율 계산
            if top5_buy_qty > 0:
                imbalance_ratio = top5_sell_qty / top5_buy_qty
            else:
                imbalance_ratio = 0

            # 불균형 방향
            imbalance_direction = "매도 우세" if imbalance_ratio > 1.5 else \
                                  "매수 우세" if imbalance_ratio < 0.7 else \
                                  "균형"

            # 신호 강도
            signal_strength = 0

            # 매수 우세 시 긍정 신호
            if imbalance_ratio < 0.7:
                signal_strength = 30
                logger.info(f"📊 호가 불균형 (매수 우세): {stock_name}")

            # 매도 우세하지만 역설 조건이면 긍정 신호
            elif imbalance_ratio > 2.0:
                paradox_result = self.check_paradox_signal(stock_code, stock_name, min_ratio=2.0)
                if paradox_result and paradox_result["price_rising"]:
                    signal_strength = 40
                    logger.info(f"🔥 호가 불균형 + 역설: {stock_name}")

            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "top5_sell_qty": top5_sell_qty,
                "top5_buy_qty": top5_buy_qty,
                "imbalance_ratio": imbalance_ratio,
                "imbalance_direction": imbalance_direction,
                "signal_strength": signal_strength,
            }

        except Exception as e:
            logger.error(f"❌ 호가 불균형 분석 오류 ({stock_code}): {e}")
            return None

    def clear_history(self):
        """이력 초기화"""
        self.price_history = {}
        logger.info("✅ 호가창 분석 이력 초기화")
