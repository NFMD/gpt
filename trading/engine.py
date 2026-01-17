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
from strategy import (
    StockScreener,
    TechnicalAnalyzer,
    SectorAnalyzer,
    TradeHistory,
    KellyCriterion,
    IntradayAnalyzer,
    MorningMonitor
)
from command_center import CommandCenter
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

        # 장중 실시간 분석 (V자 반등 포착)
        self.intraday_analyzer = IntradayAnalyzer(api)

        # 익일 오전 모니터링 (3분의 법칙, 이평선 추적)
        self.morning_monitor = MorningMonitor(api)

        # 거래 실적 추적 및 켈리 공식
        self.trade_history = TradeHistory()
        self.kelly = KellyCriterion(self.trade_history)

        # 커맨드 센터 (AI 의사결정)
        self.command_center = CommandCenter(api, self.trade_history)

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
                f"\n{idx}. {stock['stock_name']} ({stock['stock_code']}) - 점수: {stock['score']}/110\n"
                f"   현재가: {stock['current_price']:,}원 | "
                f"등락률: {stock['change_rate']:+.2f}%\n"
                f"   거래대금: {value_in_billions:,.0f}억원\n"
                f"   신고가: {'✅' if stock['is_new_high'] else '❌'} | "
                f"정배열: {'✅' if stock['is_aligned'] else '❌'} | "
                f"200일선↗: {'✅' if stock.get('ma200_uptrend', False) else '❌'} | "
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

        # 커맨드 센터: AI 상황 분석 및 의사결정
        situation_analysis = self.command_center.analyze_situation(candidates)

        # AI 판단: 거래 실행 여부
        if not self.command_center.should_trade(situation_analysis):
            logger.warning("⚠️  커맨드 센터 판단: 거래 조건 미충족. 매수를 건너뜁니다.")
            return False

        # 계좌 잔고 확인
        balance = self.api.get_balance()
        available_cash = balance['cash']

        logger.info(f"\n💵 사용 가능 현금: {available_cash:,}원")

        # 거래 실적 및 켈리 공식 추천 확인
        recommendation = self.kelly.get_recommendation(recent_trades=20)
        logger.info(f"\n💡 켈리 공식 추천: {recommendation}\n")

        # 종목당 투자 금액 계산 (켈리 공식 + AI 포지션 조절)
        num_stocks = min(len(candidates), Config.MAX_STOCKS)

        # 첫 번째 종목에 대해 켈리 비율 계산
        if len(candidates) > 0:
            kelly_info = self.kelly.calculate_position_size(
                total_capital=available_cash,
                stock_price=candidates[0]['current_price'],
                recent_trades=20,
                use_half_kelly=True
            )

            # AI 포지션 사이즈 조절 계수 적용
            position_factor = self.command_center.get_position_sizing_factor(situation_analysis)

            # 켈리 공식 + AI 조절
            base_investment = kelly_info['investment_amount'] // num_stocks
            adjusted_investment = int(base_investment * position_factor)

            # 설정값 한도 내에서 조절
            investment_per_stock = min(
                adjusted_investment,
                Config.MAX_INVESTMENT_PER_STOCK
            )
        else:
            investment_per_stock = min(
                available_cash // num_stocks,
                Config.MAX_INVESTMENT_PER_STOCK
            )

        logger.info(f"📊 종목당 투자 금액: {investment_per_stock:,}원 ({num_stocks}개 종목)")

        # 장중 실시간 분석: V자 반등 포착
        logger.info("\n" + "🎯" * 30)
        logger.info("장중 실시간 분석: V자 반등 포착")
        logger.info("🎯" * 30 + "\n")

        entry_signals = []
        for stock in candidates[:num_stocks]:
            signal = self.intraday_analyzer.get_entry_signal(
                stock_code=stock['stock_code'],
                stock_name=stock['stock_name']
            )
            if signal:
                # 기존 종목 정보와 진입 신호 병합
                entry_signals.append({**stock, **signal})

        if not entry_signals:
            logger.warning("⚠️  V자 반등 확인된 종목 없음. 매수를 건너뜁니다.")
            return False

        logger.info(f"\n✅ V자 반등 확인 종목: {len(entry_signals)}개")

        # 매수 실행 (V자 반등 확인된 종목만)
        successful_purchases = []

        for stock in entry_signals:
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            entry_price = stock['entry_price']  # V자 반등 분석 시점의 가격

            # 매수 수량 계산
            quantity = investment_per_stock // entry_price

            if quantity == 0:
                logger.warning(f"⚠️  {stock_name}: 매수 수량 부족 (진입가 {entry_price:,}원)")
                continue

            # 주문 실행
            logger.info(
                f"\n🛒 매수 시도: {stock_name} ({stock_code})\n"
                f"   수량: {quantity}주 @ {entry_price:,}원\n"
                f"   신호 강도: {stock['signal_strength']}/100"
            )

            success = self.api.place_order(
                stock_code=stock_code,
                quantity=quantity,
                price=entry_price,
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

        전략:
        - 3분의 법칙: 09:00-09:03 구간에서 시초가 미돌파 시 전량 매도
        - 1분봉 20분 이평선: 이평선 이탈(-1.5%) 시 전량 매도
        - 분할 매도: 33% → 33% → 34% 3단계 매도
        - 09:50 이후 잔량 전량 정리

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
        holdings_to_remove = []

        for holding in self.portfolio['holdings']:
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            total_quantity = holding['quantity']
            buy_price = holding['buy_price']

            # 이미 매도된 수량 추적
            sold_quantity = holding.get('sold_quantity', 0)
            remaining_quantity = total_quantity - sold_quantity

            if remaining_quantity <= 0:
                logger.info(f"ℹ️  {stock_name}: 이미 전량 매도 완료")
                holdings_to_remove.append(stock_code)
                continue

            # 현재가 조회
            price_info = self.api.get_stock_price(stock_code)

            if not price_info:
                logger.warning(f"⚠️  {stock_name}: 현재가 조회 실패")
                continue

            current_price = price_info['current_price']
            profit_rate = ((current_price - buy_price) / buy_price) * 100

            logger.info(
                f"\n📊 {stock_name} ({stock_code})\n"
                f"   매수가: {buy_price:,}원 → 현재가: {current_price:,}원\n"
                f"   잔여 수량: {remaining_quantity}주 / {total_quantity}주\n"
                f"   수익률: {profit_rate:+.2f}%"
            )

            # 매도 신호 판단
            sell_quantity = 0
            sell_reason = ""

            # 1. 긴급 매도 신호: 3분의 법칙 또는 이평선 이탈
            sell_signal = self.morning_monitor.get_sell_signal(
                stock_code=stock_code,
                stock_name=stock_name,
                buy_price=buy_price,
                current_price=current_price,
                current_time=current_time
            )

            if sell_signal['should_sell']:
                # 긴급 신호: 전량 매도
                sell_quantity = remaining_quantity
                sell_reason = f"긴급 매도 ({sell_signal['reason']})"

            # 2. 09:50 이후: 잔량 전량 정리
            elif current_time >= "09:50":
                sell_quantity = remaining_quantity
                sell_reason = "시간 마감 (09:50 이후)"

            # 3. 분할 매도 전략
            else:
                # 매도 단계 계산
                sell_stage = sold_quantity // (total_quantity // 3 + 1)  # 0, 1, 2

                # 각 단계별 수익률 기준
                stage_targets = [
                    (1, 2.0),   # 1단계: +2% 이상
                    (2, 3.0),   # 2단계: +3% 이상
                    (3, 5.0),   # 3단계: +5% 이상
                ]

                for stage, target_profit in stage_targets:
                    if sell_stage < stage and profit_rate >= target_profit:
                        # 해당 단계 매도 실행
                        if stage == 1:
                            sell_quantity = int(total_quantity * 0.33)
                            sell_reason = f"1차 분할 매도 ({target_profit}% 도달)"
                        elif stage == 2:
                            first_sold = int(total_quantity * 0.33)
                            sell_quantity = int(total_quantity * 0.33)
                            sell_reason = f"2차 분할 매도 ({target_profit}% 도달)"
                        else:  # stage == 3
                            sell_quantity = remaining_quantity  # 잔량 전부
                            sell_reason = f"3차 분할 매도 ({target_profit}% 도달)"
                        break

            # 4. 매도 실행
            if sell_quantity > 0:
                logger.info(f"🔔 매도 신호: {sell_reason}")
                logger.info(f"📤 매도 수량: {sell_quantity}주 @ {current_price:,}원")

                # 주문 실행
                success = self.api.place_order(
                    stock_code=stock_code,
                    quantity=sell_quantity,
                    price=current_price,
                    order_type="sell"
                )

                if success:
                    # 수익 계산
                    profit = (current_price - buy_price) * sell_quantity
                    total_profit += profit

                    # 매도 수량 업데이트
                    holding['sold_quantity'] = sold_quantity + sell_quantity

                    self._log_trade(
                        f"✅ 매도 완료: {stock_name} ({stock_code}) {sell_quantity}주 @ {current_price:,}원 "
                        f"(수익: {profit:,}원, {profit_rate:+.2f}%) - {sell_reason}"
                    )

                    # 전량 매도 완료 시 거래 실적 기록
                    if holding['sold_quantity'] >= total_quantity:
                        total_profit_amount = (current_price - buy_price) * total_quantity

                        trade_record = {
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "buy_date": holding['buy_date'],
                            "sell_date": now.strftime("%Y-%m-%d"),
                            "buy_price": buy_price,
                            "sell_price": current_price,
                            "quantity": total_quantity,
                            "profit": total_profit_amount,
                            "profit_rate": profit_rate,
                        }
                        self.trade_history.add_trade(trade_record)

                        # 커맨드 센터: 거래 결과 학습
                        self.command_center.update_from_trade_result(profit_rate / 100)

                        # 포트폴리오에서 제거 표시
                        holdings_to_remove.append(stock_code)
                else:
                    logger.warning(f"⚠️  {stock_name}: 매도 주문 실패")
            else:
                logger.info(f"⏸️  {stock_name}: 매도 조건 미충족 (보유 유지)")

        # 포트폴리오 업데이트
        if holdings_to_remove or total_profit != 0:
            # 전량 매도된 종목 제거
            self.portfolio['holdings'] = [
                h for h in self.portfolio['holdings']
                if h['stock_code'] not in holdings_to_remove
            ]
            self._save_portfolio()

            logger.info(f"\n✅ 매도 실행 완료")
            if holdings_to_remove:
                logger.info(f"🗑️  포트폴리오에서 제거: {len(holdings_to_remove)}개 종목")
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
