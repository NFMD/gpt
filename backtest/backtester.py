"""
백테스팅 엔진 모듈
과거 데이터를 기반으로 종가 베팅 전략의 성과를 시뮬레이션합니다.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path

from api import KISApi
from strategy import (
    StockScreener,
    TechnicalAnalyzer,
    SectorAnalyzer,
    IntradayAnalyzer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """백테스트 거래 기록"""
    date: str
    stock_code: str
    stock_name: str
    entry_price: int
    exit_price: int
    quantity: int
    profit: int
    profit_rate: float
    hold_days: int
    exit_reason: str


@dataclass
class BacktestResult:
    """백테스트 결과"""
    start_date: str
    end_date: str
    initial_capital: int
    final_capital: int
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit_rate: float
    avg_win_rate: float
    avg_loss_rate: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[BacktestTrade]
    daily_returns: List[float]


class Backtester:
    """백테스팅 엔진"""

    def __init__(self, api: KISApi, initial_capital: int = 10000000):
        """
        Args:
            api: KIS API 클라이언트
            initial_capital: 초기 자본금 (기본 1000만원)
        """
        self.api = api
        self.initial_capital = initial_capital
        self.screener = StockScreener(api)
        self.technical_analyzer = TechnicalAnalyzer(api)
        self.sector_analyzer = SectorAnalyzer()
        self.intraday_analyzer = IntradayAnalyzer(api)

        self.results_dir = Path(__file__).parent.parent / "backtest_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        min_trading_value: int = 200000000000,  # 2000억
        max_stocks_per_day: int = 3,
        v_reversal_threshold: int = 70
    ) -> BacktestResult:
        """
        백테스트 실행

        Args:
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            min_trading_value: 최소 거래대금
            max_stocks_per_day: 일일 최대 매수 종목 수
            v_reversal_threshold: V자 반등 신호 강도 임계값

        Returns:
            백테스트 결과
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"🔬 백테스트 시작: {start_date} ~ {end_date}")
        logger.info(f"💰 초기 자본: {self.initial_capital:,}원")
        logger.info(f"📊 설정: 거래대금 {min_trading_value/100000000:,.0f}억+ | "
                   f"최대 {max_stocks_per_day}종목 | V자 신호 {v_reversal_threshold}+")
        logger.info("=" * 80 + "\n")

        # 거래일 목록 생성
        trading_days = self._get_trading_days(start_date, end_date)

        if not trading_days:
            logger.error("거래일 목록을 가져올 수 없습니다.")
            return None

        logger.info(f"📅 총 거래일 수: {len(trading_days)}일\n")

        # 시뮬레이션 변수
        current_capital = self.initial_capital
        holdings: List[Dict] = []
        trades: List[BacktestTrade] = []
        daily_capitals: List[int] = [self.initial_capital]

        # 각 거래일에 대해 시뮬레이션
        for idx, trade_date in enumerate(trading_days, 1):
            logger.info(f"\n[{idx}/{len(trading_days)}] 📆 {trade_date}")

            # 보유 종목 매도 처리 (익일 오전)
            if holdings:
                current_capital, holdings, completed_trades = self._simulate_sell(
                    holdings=holdings,
                    sell_date=trade_date,
                    current_capital=current_capital
                )
                trades.extend(completed_trades)

            # 신규 매수 처리 (장 마감 전)
            if idx < len(trading_days):  # 마지막 날은 매수 안 함
                new_holdings = self._simulate_buy(
                    trade_date=trade_date,
                    current_capital=current_capital,
                    min_trading_value=min_trading_value,
                    max_stocks=max_stocks_per_day,
                    v_threshold=v_reversal_threshold
                )

                # 매수 집행
                for holding in new_holdings:
                    investment = holding['entry_price'] * holding['quantity']
                    current_capital -= investment
                    holdings.append(holding)
                    logger.info(
                        f"  ✅ 매수: {holding['stock_name']} "
                        f"{holding['quantity']}주 @ {holding['entry_price']:,}원 "
                        f"(투자금: {investment:,}원)"
                    )

            # 일일 자본 기록 (현금 + 보유 종목 평가액)
            holdings_value = sum(h['entry_price'] * h['quantity'] for h in holdings)
            total_capital = current_capital + holdings_value
            daily_capitals.append(total_capital)

            logger.info(f"  💵 현금: {current_capital:,}원 | "
                       f"보유: {holdings_value:,}원 | "
                       f"총 자산: {total_capital:,}원")

        # 최종 결산: 남은 보유 종목 강제 청산
        if holdings:
            logger.info("\n🔔 백테스트 종료: 잔여 보유 종목 청산")
            for holding in holdings:
                # 마지막 거래일 종가로 청산
                exit_price = holding['entry_price']  # 실제로는 마지막 날 종가 조회 필요
                quantity = holding['quantity']
                profit = (exit_price - holding['entry_price']) * quantity
                profit_rate = ((exit_price - holding['entry_price']) / holding['entry_price']) * 100

                current_capital += exit_price * quantity

                trade = BacktestTrade(
                    date=trading_days[-1],
                    stock_code=holding['stock_code'],
                    stock_name=holding['stock_name'],
                    entry_price=holding['entry_price'],
                    exit_price=exit_price,
                    quantity=quantity,
                    profit=profit,
                    profit_rate=profit_rate,
                    hold_days=1,
                    exit_reason="백테스트 종료 (강제 청산)"
                )
                trades.append(trade)

        # 최종 자본
        final_capital = current_capital

        # 성과 분석
        result = self._analyze_performance(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            trades=trades,
            daily_capitals=daily_capitals
        )

        # 결과 저장
        self._save_result(result)

        return result

    def _get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """
        거래일 목록 조회

        Args:
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)

        Returns:
            거래일 리스트
        """
        # 간단한 구현: 주말을 제외한 모든 날짜 (공휴일은 미고려)
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")

        trading_days = []
        current = start

        while current <= end:
            # 주말 제외 (월~금)
            if current.weekday() < 5:
                trading_days.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)

        return trading_days

    def _simulate_buy(
        self,
        trade_date: str,
        current_capital: int,
        min_trading_value: int,
        max_stocks: int,
        v_threshold: int
    ) -> List[Dict]:
        """
        매수 시뮬레이션

        Returns:
            매수 종목 리스트
        """
        # 종목 스크리닝 (실제 API 호출 시뮬레이션)
        # 주의: 백테스트에서는 과거 특정 날짜의 데이터를 조회해야 함
        # 여기서는 간단히 현재 API 사용 (실제로는 날짜별 데이터 필요)

        try:
            # 후보 종목 스크리닝
            candidates = self.screener.get_top_candidates(
                min_trading_value=min_trading_value
            )

            if not candidates:
                return []

            # 기술적 분석 필터링
            analyzed = self.technical_analyzer.filter_by_technical(candidates)

            if not analyzed:
                return []

            # V자 반등 확인
            holdings = []
            investment_per_stock = current_capital // max_stocks

            for stock in analyzed[:max_stocks]:
                # V자 반등 신호 확인
                signal = self.intraday_analyzer.get_entry_signal(
                    stock_code=stock['stock_code'],
                    stock_name=stock['stock_name']
                )

                if signal and signal['signal_strength'] >= v_threshold:
                    entry_price = signal['entry_price']
                    quantity = investment_per_stock // entry_price

                    if quantity > 0:
                        holdings.append({
                            'stock_code': stock['stock_code'],
                            'stock_name': stock['stock_name'],
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'entry_date': trade_date,
                            'score': stock['score'],
                            'signal_strength': signal['signal_strength']
                        })

            return holdings

        except Exception as e:
            logger.warning(f"  ⚠️ 매수 시뮬레이션 오류: {e}")
            return []

    def _simulate_sell(
        self,
        holdings: List[Dict],
        sell_date: str,
        current_capital: int
    ) -> Tuple[int, List[Dict], List[BacktestTrade]]:
        """
        매도 시뮬레이션

        Returns:
            (업데이트된 자본, 남은 보유 종목, 완료된 거래 리스트)
        """
        remaining_holdings = []
        completed_trades = []

        for holding in holdings:
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            entry_price = holding['entry_price']
            quantity = holding['quantity']
            entry_date = holding['entry_date']

            # 익일 종가 조회 (실제로는 sell_date의 실제 가격 조회 필요)
            try:
                price_info = self.api.get_stock_price(stock_code)
                if price_info:
                    exit_price = price_info['current_price']
                else:
                    # 가격 조회 실패 시 진입가로 청산
                    exit_price = entry_price
            except:
                exit_price = entry_price

            # 수익 계산
            profit = (exit_price - entry_price) * quantity
            profit_rate = ((exit_price - entry_price) / entry_price) * 100

            # 보유일 계산
            entry_dt = datetime.strptime(entry_date, "%Y%m%d")
            sell_dt = datetime.strptime(sell_date, "%Y%m%d")
            hold_days = (sell_dt - entry_dt).days

            # 매도 조건 판단 (간단한 로직)
            should_sell = True  # 익일 무조건 매도 (종가 베팅 전략)
            exit_reason = "익일 오전 매도"

            if should_sell:
                # 매도 실행
                current_capital += exit_price * quantity

                trade = BacktestTrade(
                    date=sell_date,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    profit=profit,
                    profit_rate=profit_rate,
                    hold_days=hold_days,
                    exit_reason=exit_reason
                )
                completed_trades.append(trade)

                logger.info(
                    f"  💸 매도: {stock_name} {quantity}주 @ {exit_price:,}원 "
                    f"(수익: {profit:,}원, {profit_rate:+.2f}%)"
                )
            else:
                remaining_holdings.append(holding)

        return current_capital, remaining_holdings, completed_trades

    def _analyze_performance(
        self,
        start_date: str,
        end_date: str,
        initial_capital: int,
        final_capital: int,
        trades: List[BacktestTrade],
        daily_capitals: List[int]
    ) -> BacktestResult:
        """성과 분석"""

        # 기본 통계
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.profit > 0)
        losing_trades = sum(1 for t in trades if t.profit < 0)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # 수익률 통계
        total_return = ((final_capital - initial_capital) / initial_capital) * 100

        profit_rates = [t.profit_rate for t in trades]
        avg_profit_rate = sum(profit_rates) / len(profit_rates) if profit_rates else 0

        win_rates = [t.profit_rate for t in trades if t.profit > 0]
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0

        loss_rates = [t.profit_rate for t in trades if t.profit < 0]
        avg_loss_rate = sum(loss_rates) / len(loss_rates) if loss_rates else 0

        # 최대 낙폭 (MDD)
        max_drawdown = self._calculate_max_drawdown(daily_capitals)

        # 샤프 비율
        sharpe_ratio = self._calculate_sharpe_ratio(daily_capitals)

        # 일일 수익률
        daily_returns = [
            ((daily_capitals[i] - daily_capitals[i-1]) / daily_capitals[i-1]) * 100
            for i in range(1, len(daily_capitals))
        ]

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_profit_rate=avg_profit_rate,
            avg_win_rate=avg_win_rate,
            avg_loss_rate=avg_loss_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            daily_returns=daily_returns
        )

    def _calculate_max_drawdown(self, daily_capitals: List[int]) -> float:
        """최대 낙폭 (MDD) 계산"""
        if not daily_capitals:
            return 0.0

        max_capital = daily_capitals[0]
        max_dd = 0.0

        for capital in daily_capitals:
            if capital > max_capital:
                max_capital = capital

            drawdown = ((max_capital - capital) / max_capital) * 100
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd

    def _calculate_sharpe_ratio(self, daily_capitals: List[int]) -> float:
        """샤프 비율 계산 (연환산)"""
        if len(daily_capitals) < 2:
            return 0.0

        # 일일 수익률 계산
        daily_returns = [
            (daily_capitals[i] - daily_capitals[i-1]) / daily_capitals[i-1]
            for i in range(1, len(daily_capitals))
        ]

        if not daily_returns:
            return 0.0

        # 평균 및 표준편차
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_return = variance ** 0.5

        if std_return == 0:
            return 0.0

        # 샤프 비율 (무위험 수익률 0 가정, 연환산 252 거래일)
        sharpe = (avg_return / std_return) * (252 ** 0.5)

        return sharpe

    def _save_result(self, result: BacktestResult):
        """백테스트 결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.results_dir / f"backtest_{timestamp}.json"

        # 결과를 JSON으로 변환
        result_dict = {
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": result.win_rate,
            "avg_profit_rate": result.avg_profit_rate,
            "avg_win_rate": result.avg_win_rate,
            "avg_loss_rate": result.avg_loss_rate,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "trades": [
                {
                    "date": t.date,
                    "stock_code": t.stock_code,
                    "stock_name": t.stock_name,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "profit": t.profit,
                    "profit_rate": t.profit_rate,
                    "hold_days": t.hold_days,
                    "exit_reason": t.exit_reason
                }
                for t in result.trades
            ],
            "daily_returns": result.daily_returns
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 백테스트 결과 저장: {result_file}")

    def print_result(self, result: BacktestResult):
        """백테스트 결과 출력"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 백테스트 결과 요약")
        logger.info("=" * 80)
        logger.info(f"📅 기간: {result.start_date} ~ {result.end_date}")
        logger.info(f"💰 초기 자본: {result.initial_capital:,}원")
        logger.info(f"💵 최종 자본: {result.final_capital:,}원")
        logger.info(f"📈 총 수익률: {result.total_return:+.2f}%")
        logger.info(f"📉 최대 낙폭 (MDD): {result.max_drawdown:.2f}%")
        logger.info(f"📊 샤프 비율: {result.sharpe_ratio:.2f}")
        logger.info("")
        logger.info(f"🎯 총 거래 횟수: {result.total_trades}회")
        logger.info(f"✅ 수익 거래: {result.winning_trades}회")
        logger.info(f"❌ 손실 거래: {result.losing_trades}회")
        logger.info(f"🎲 승률: {result.win_rate:.2f}%")
        logger.info("")
        logger.info(f"📊 평균 수익률: {result.avg_profit_rate:+.2f}%")
        logger.info(f"📈 평균 수익 (승): {result.avg_win_rate:+.2f}%")
        logger.info(f"📉 평균 손실 (패): {result.avg_loss_rate:+.2f}%")
        logger.info("=" * 80 + "\n")
