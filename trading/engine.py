"""
매매 엔진 모듈
종가 베팅 전략을 실행하고 포트폴리오를 관리합니다.
"""
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from api import KISApi
from strategy import StockScreener, TechnicalAnalyzer, SectorAnalyzer
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진"""

    def __init__(self, api: KISApi):
        self.api = api
        self.screener = StockScreener(api)
        self.technical_analyzer = TechnicalAnalyzer(api)
        self.sector_analyzer = SectorAnalyzer()

        self.portfolio_file = Path(__file__).parent.parent / "data" / "portfolio.json"
        self.trade_log_file = Path(__file__).parent.parent / "logs" / "trades.log"

        # 포트폴리오 로드
        self.portfolio = self._load_portfolio()

    def _load_portfolio(self) -> Dict:
        """포트폴리오 로드"""
        if self.portfolio_file.exists():
            with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"holdings": [], "buy_date": None}

    def _save_portfolio(self):
        """포트폴리오 저장"""
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.portfolio, f, ensure_ascii=False, indent=2)

    def _log_trade(self, message: str):
        """거래 로그 기록"""
        self.trade_log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.trade_log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
        logger.info(message)

    def scan_market(self) -> List[Dict]:
        """
        시장 스캔 및 매수 후보 선정

        Returns:
            최종 매수 후보 종목 리스트
        """
        logger.info("\n" + "🔍" * 30)
        logger.info("시장 스캔 시작")
        logger.info("🔍" * 30 + "\n")

        # 1. 종목 스크리닝 (거래대금 + 등락률)
        candidates = self.screener.get_top_candidates()

        if not candidates:
            logger.warning("⚠️  매수 후보를 찾을 수 없습니다.")
            return []

        # 2. 섹터 분석
        self.sector_analyzer.print_sector_analysis(candidates)

        # 3. 기술적 분석
        logger.info("\n" + "=" * 60)
        logger.info("🔬 기술적 분석 시작")
        logger.info("=" * 60)

        analyzed_candidates = self.technical_analyzer.filter_by_technical(candidates)

        # 4. 최종 결과
        logger.info("\n" + "=" * 60)
        logger.info("🎯 최종 매수 후보 (점수 순)")
        logger.info("=" * 60)

        for idx, stock in enumerate(analyzed_candidates[:Config.MAX_STOCKS], 1):
            value_in_billions = stock['trading_value'] / 100000000
            logger.info(
                f"\n{idx}. {stock['stock_name']} ({stock['stock_code']}) - 점수: {stock['score']}/100\n"
                f"   현재가: {stock['current_price']:,}원 | "
                f"등락률: {stock['change_rate']:+.2f}%\n"
                f"   거래대금: {value_in_billions:,.0f}억원\n"
                f"   신고가: {'✅' if stock['is_new_high'] else '❌'} | "
                f"정배열: {'✅' if stock['is_aligned'] else '❌'} | "
                f"외국인+기관: {'✅' if stock['investor_buying']['both_buying'] else '❌'}"
            )

        return analyzed_candidates[:Config.MAX_STOCKS]

    def execute_closing_bet(self) -> bool:
        """
        종가 베팅 실행 (15:00-15:20)

        Returns:
            실행 성공 여부
        """
        logger.info("\n" + "💰" * 30)
        logger.info("종가 베팅 전략 실행")
        logger.info("💰" * 30 + "\n")

        # 현재 시간 확인
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if current_time < Config.BUY_TIME_START or current_time > Config.BUY_TIME_END:
            logger.warning(
                f"⚠️  종가 베팅 시간이 아닙니다. "
                f"(현재: {current_time}, 허용: {Config.BUY_TIME_START}-{Config.BUY_TIME_END})"
            )
            return False

        # 이미 보유 중인 종목이 있는지 확인
        if self.portfolio['holdings']:
            logger.info("⚠️  이미 보유 중인 종목이 있습니다. 매수를 건너뜁니다.")
            return False

        # 시장 스캔
        candidates = self.scan_market()

        if not candidates:
            return False

        # 계좌 잔고 확인
        balance = self.api.get_balance()
        available_cash = balance['cash']

        logger.info(f"\n💵 사용 가능 현금: {available_cash:,}원")

        # 종목당 투자 금액 계산
        num_stocks = min(len(candidates), Config.MAX_STOCKS)
        investment_per_stock = min(
            available_cash // num_stocks,
            Config.MAX_INVESTMENT_PER_STOCK
        )

        logger.info(f"📊 종목당 투자 금액: {investment_per_stock:,}원 ({num_stocks}개 종목)")

        # 매수 실행
        successful_purchases = []

        for stock in candidates[:num_stocks]:
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            current_price = stock['current_price']

            # 매수 수량 계산
            quantity = investment_per_stock // current_price

            if quantity == 0:
                logger.warning(f"⚠️  {stock_name}: 매수 수량 부족 (현재가 {current_price:,}원)")
                continue

            # 주문 실행
            logger.info(f"\n🛒 매수 시도: {stock_name} ({stock_code}) {quantity}주 @ {current_price:,}원")

            success = self.api.place_order(
                stock_code=stock_code,
                quantity=quantity,
                price=current_price,
                order_type="buy"
            )

            if success:
                purchase_info = {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "quantity": quantity,
                    "buy_price": current_price,
                    "buy_date": now.strftime("%Y-%m-%d"),
                    "buy_time": now.strftime("%H:%M:%S"),
                    "score": stock['score'],
                }
                successful_purchases.append(purchase_info)

                self._log_trade(
                    f"✅ 매수 완료: {stock_name} ({stock_code}) {quantity}주 @ {current_price:,}원"
                )

        # 포트폴리오 업데이트
        if successful_purchases:
            self.portfolio['holdings'] = successful_purchases
            self.portfolio['buy_date'] = now.strftime("%Y-%m-%d")
            self._save_portfolio()

            logger.info(f"\n✅ 총 {len(successful_purchases)}개 종목 매수 완료")
            return True
        else:
            logger.warning("⚠️  매수된 종목이 없습니다.")
            return False

    def execute_morning_sell(self) -> bool:
        """
        익일 오전 매도 실행 (09:00-10:00)

        Returns:
            실행 성공 여부
        """
        logger.info("\n" + "💸" * 30)
        logger.info("익일 오전 매도 전략 실행")
        logger.info("💸" * 30 + "\n")

        # 현재 시간 확인
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if current_time < Config.SELL_TIME_START or current_time > Config.SELL_TIME_END:
            logger.warning(
                f"⚠️  매도 시간이 아닙니다. "
                f"(현재: {current_time}, 허용: {Config.SELL_TIME_START}-{Config.SELL_TIME_END})"
            )
            return False

        # 보유 종목 확인
        if not self.portfolio['holdings']:
            logger.info("ℹ️  보유 중인 종목이 없습니다.")
            return False

        # 매도 실행
        total_profit = 0
        successful_sales = []

        for holding in self.portfolio['holdings']:
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            quantity = holding['quantity']
            buy_price = holding['buy_price']

            # 현재가 조회
            price_info = self.api.get_stock_price(stock_code)

            if not price_info:
                logger.warning(f"⚠️  {stock_name}: 현재가 조회 실패")
                continue

            current_price = price_info['current_price']
            profit = (current_price - buy_price) * quantity
            profit_rate = ((current_price - buy_price) / buy_price) * 100

            logger.info(
                f"\n📊 {stock_name} ({stock_code})\n"
                f"   매수가: {buy_price:,}원 → 현재가: {current_price:,}원\n"
                f"   수익: {profit:,}원 ({profit_rate:+.2f}%)"
            )

            # 매도 조건 체크
            should_sell = (
                    profit_rate >= Config.TARGET_PROFIT_RATE * 100 or  # 목표 수익률 달성
                    profit_rate <= Config.STOP_LOSS_RATE * 100 or  # 손절 라인 도달
                    current_time >= "09:50"  # 시간 마감 임박
            )

            if should_sell:
                logger.info(f"🔔 매도 조건 충족")

                # 주문 실행
                success = self.api.place_order(
                    stock_code=stock_code,
                    quantity=quantity,
                    price=current_price,
                    order_type="sell"
                )

                if success:
                    total_profit += profit
                    successful_sales.append(stock_code)

                    self._log_trade(
                        f"✅ 매도 완료: {stock_name} ({stock_code}) {quantity}주 @ {current_price:,}원 "
                        f"(수익: {profit:,}원, {profit_rate:+.2f}%)"
                    )

        # 포트폴리오 업데이트
        if successful_sales:
            self.portfolio['holdings'] = [
                h for h in self.portfolio['holdings']
                if h['stock_code'] not in successful_sales
            ]
            self._save_portfolio()

            logger.info(f"\n✅ 총 {len(successful_sales)}개 종목 매도 완료")
            logger.info(f"💰 총 수익: {total_profit:,}원")
            return True
        else:
            logger.info("ℹ️  매도 조건을 만족하는 종목이 없습니다.")
            return False

    def check_portfolio(self):
        """현재 포트폴리오 상태 확인"""
        logger.info("\n" + "=" * 60)
        logger.info("📂 포트폴리오 현황")
        logger.info("=" * 60)

        if not self.portfolio['holdings']:
            logger.info("ℹ️  보유 중인 종목이 없습니다.")
            return

        logger.info(f"매수일: {self.portfolio['buy_date']}\n")

        total_investment = 0
        total_value = 0

        for holding in self.portfolio['holdings']:
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            quantity = holding['quantity']
            buy_price = holding['buy_price']

            # 현재가 조회
            price_info = self.api.get_stock_price(stock_code)

            if price_info:
                current_price = price_info['current_price']
                investment = buy_price * quantity
                current_value = current_price * quantity
                profit = current_value - investment
                profit_rate = (profit / investment) * 100

                total_investment += investment
                total_value += current_value

                logger.info(
                    f"{stock_name} ({stock_code})\n"
                    f"   수량: {quantity}주 | 매수가: {buy_price:,}원 | 현재가: {current_price:,}원\n"
                    f"   평가액: {current_value:,}원 | 수익: {profit:,}원 ({profit_rate:+.2f}%)\n"
                )

        if total_investment > 0:
            total_profit_rate = ((total_value - total_investment) / total_investment) * 100
            logger.info("=" * 60)
            logger.info(
                f"💰 총 투자금: {total_investment:,}원\n"
                f"💵 현재 평가액: {total_value:,}원\n"
                f"📈 총 수익: {total_value - total_investment:,}원 ({total_profit_rate:+.2f}%)"
            )
