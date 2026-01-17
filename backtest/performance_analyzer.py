"""
성과 분석 모듈
거래 실적을 분석하고 상세 리포트를 생성합니다.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import json

from strategy import TradeHistory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """성과 분석기"""

    def __init__(self, trade_history: TradeHistory):
        """
        Args:
            trade_history: 거래 실적 관리 객체
        """
        self.trade_history = trade_history
        self.reports_dir = Path(__file__).parent.parent / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self, date: Optional[str] = None) -> Dict:
        """
        일일 성과 리포트 생성

        Args:
            date: 대상 날짜 (YYYY-MM-DD), None이면 오늘

        Returns:
            일일 리포트
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logger.info("\n" + "=" * 80)
        logger.info(f"📊 일일 성과 리포트: {date}")
        logger.info("=" * 80 + "\n")

        # 해당 날짜의 거래 조회
        all_trades = self.trade_history.get_all_trades()
        daily_trades = [t for t in all_trades if t.get('sell_date') == date]

        if not daily_trades:
            logger.info(f"ℹ️  {date}에 체결된 거래가 없습니다.")
            return {"date": date, "trades": [], "summary": {}}

        # 통계 계산
        total_trades = len(daily_trades)
        total_profit = sum(t['profit'] for t in daily_trades)
        winning_trades = [t for t in daily_trades if t['profit'] > 0]
        losing_trades = [t for t in daily_trades if t['profit'] < 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_profit_rate = sum(t['profit_rate'] for t in daily_trades) / total_trades

        report = {
            "date": date,
            "total_trades": total_trades,
            "total_profit": total_profit,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_profit_rate": avg_profit_rate,
            "trades": daily_trades
        }

        # 출력
        logger.info(f"📈 총 거래: {total_trades}건")
        logger.info(f"💰 총 수익: {total_profit:,}원")
        logger.info(f"✅ 수익 거래: {len(winning_trades)}건")
        logger.info(f"❌ 손실 거래: {len(losing_trades)}건")
        logger.info(f"🎲 승률: {win_rate:.2f}%")
        logger.info(f"📊 평균 수익률: {avg_profit_rate:+.2f}%\n")

        # 거래 상세
        for idx, trade in enumerate(daily_trades, 1):
            logger.info(
                f"{idx}. {trade['stock_name']} ({trade['stock_code']})\n"
                f"   매수: {trade['buy_price']:,}원 → 매도: {trade['sell_price']:,}원\n"
                f"   수익: {trade['profit']:,}원 ({trade['profit_rate']:+.2f}%)"
            )

        logger.info("\n" + "=" * 80)

        return report

    def generate_weekly_report(self, weeks_back: int = 1) -> Dict:
        """
        주간 성과 리포트 생성

        Args:
            weeks_back: 몇 주 전 (1 = 지난주, 2 = 2주 전, ...)

        Returns:
            주간 리포트
        """
        # 지난주 월요일~일요일 계산
        today = datetime.now()
        days_to_monday = today.weekday()  # 0 = 월요일
        last_sunday = today - timedelta(days=days_to_monday + (weeks_back - 1) * 7)
        last_monday = last_sunday - timedelta(days=6)

        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = last_sunday.strftime("%Y-%m-%d")

        logger.info("\n" + "=" * 80)
        logger.info(f"📊 주간 성과 리포트: {start_date} ~ {end_date}")
        logger.info("=" * 80 + "\n")

        # 해당 주간의 거래 조회
        all_trades = self.trade_history.get_all_trades()
        weekly_trades = [
            t for t in all_trades
            if start_date <= t.get('sell_date', '') <= end_date
        ]

        if not weekly_trades:
            logger.info(f"ℹ️  해당 기간에 체결된 거래가 없습니다.")
            return {"start_date": start_date, "end_date": end_date, "trades": []}

        # 통계 계산
        total_trades = len(weekly_trades)
        total_profit = sum(t['profit'] for t in weekly_trades)
        winning_trades = [t for t in weekly_trades if t['profit'] > 0]
        losing_trades = [t for t in weekly_trades if t['profit'] < 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_profit_rate = sum(t['profit_rate'] for t in weekly_trades) / total_trades

        # 일별 수익 분석
        daily_profits = {}
        for trade in weekly_trades:
            sell_date = trade['sell_date']
            if sell_date not in daily_profits:
                daily_profits[sell_date] = 0
            daily_profits[sell_date] += trade['profit']

        report = {
            "start_date": start_date,
            "end_date": end_date,
            "total_trades": total_trades,
            "total_profit": total_profit,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_profit_rate": avg_profit_rate,
            "daily_profits": daily_profits,
            "trades": weekly_trades
        }

        # 출력
        logger.info(f"📈 총 거래: {total_trades}건")
        logger.info(f"💰 총 수익: {total_profit:,}원")
        logger.info(f"✅ 수익 거래: {len(winning_trades)}건")
        logger.info(f"❌ 손실 거래: {len(losing_trades)}건")
        logger.info(f"🎲 승률: {win_rate:.2f}%")
        logger.info(f"📊 평균 수익률: {avg_profit_rate:+.2f}%\n")

        # 일별 수익
        logger.info("📅 일별 수익:")
        for date in sorted(daily_profits.keys()):
            profit = daily_profits[date]
            logger.info(f"  {date}: {profit:,}원")

        logger.info("\n" + "=" * 80)

        return report

    def generate_monthly_report(self, month: Optional[str] = None) -> Dict:
        """
        월간 성과 리포트 생성

        Args:
            month: 대상 월 (YYYY-MM), None이면 이번 달

        Returns:
            월간 리포트
        """
        if month is None:
            month = datetime.now().strftime("%Y-%m")

        logger.info("\n" + "=" * 80)
        logger.info(f"📊 월간 성과 리포트: {month}")
        logger.info("=" * 80 + "\n")

        # 해당 월의 거래 조회
        all_trades = self.trade_history.get_all_trades()
        monthly_trades = [
            t for t in all_trades
            if t.get('sell_date', '').startswith(month)
        ]

        if not monthly_trades:
            logger.info(f"ℹ️  {month}에 체결된 거래가 없습니다.")
            return {"month": month, "trades": []}

        # 통계 계산
        total_trades = len(monthly_trades)
        total_profit = sum(t['profit'] for t in monthly_trades)
        winning_trades = [t for t in monthly_trades if t['profit'] > 0]
        losing_trades = [t for t in monthly_trades if t['profit'] < 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_profit_rate = sum(t['profit_rate'] for t in monthly_trades) / total_trades

        # 최대 수익/손실 거래
        best_trade = max(monthly_trades, key=lambda t: t['profit_rate'])
        worst_trade = min(monthly_trades, key=lambda t: t['profit_rate'])

        # 종목별 통계
        stock_stats = {}
        for trade in monthly_trades:
            stock_name = trade['stock_name']
            if stock_name not in stock_stats:
                stock_stats[stock_name] = {
                    'count': 0,
                    'total_profit': 0,
                    'wins': 0,
                    'losses': 0
                }

            stock_stats[stock_name]['count'] += 1
            stock_stats[stock_name]['total_profit'] += trade['profit']
            if trade['profit'] > 0:
                stock_stats[stock_name]['wins'] += 1
            else:
                stock_stats[stock_name]['losses'] += 1

        report = {
            "month": month,
            "total_trades": total_trades,
            "total_profit": total_profit,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_profit_rate": avg_profit_rate,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "stock_stats": stock_stats,
            "trades": monthly_trades
        }

        # 출력
        logger.info(f"📈 총 거래: {total_trades}건")
        logger.info(f"💰 총 수익: {total_profit:,}원")
        logger.info(f"✅ 수익 거래: {len(winning_trades)}건")
        logger.info(f"❌ 손실 거래: {len(losing_trades)}건")
        logger.info(f"🎲 승률: {win_rate:.2f}%")
        logger.info(f"📊 평균 수익률: {avg_profit_rate:+.2f}%\n")

        logger.info("🏆 최고 수익 거래:")
        logger.info(
            f"  {best_trade['stock_name']}: "
            f"{best_trade['profit']:,}원 ({best_trade['profit_rate']:+.2f}%)"
        )

        logger.info("📉 최대 손실 거래:")
        logger.info(
            f"  {worst_trade['stock_name']}: "
            f"{worst_trade['profit']:,}원 ({worst_trade['profit_rate']:+.2f}%)\n"
        )

        logger.info("📊 종목별 통계:")
        for stock_name, stats in sorted(
            stock_stats.items(),
            key=lambda x: x[1]['total_profit'],
            reverse=True
        ):
            logger.info(
                f"  {stock_name}: {stats['count']}건 | "
                f"수익 {stats['total_profit']:,}원 | "
                f"승 {stats['wins']}회 패 {stats['losses']}회"
            )

        logger.info("\n" + "=" * 80)

        # 리포트 저장
        self._save_report(report, f"monthly_{month.replace('-', '')}")

        return report

    def generate_custom_report(
        self,
        start_date: str,
        end_date: str,
        save: bool = True
    ) -> Dict:
        """
        사용자 정의 기간 리포트 생성

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            save: 리포트 파일 저장 여부

        Returns:
            기간별 리포트
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"📊 기간별 성과 리포트: {start_date} ~ {end_date}")
        logger.info("=" * 80 + "\n")

        # 해당 기간의 거래 조회
        all_trades = self.trade_history.get_all_trades()
        period_trades = [
            t for t in all_trades
            if start_date <= t.get('sell_date', '') <= end_date
        ]

        if not period_trades:
            logger.info(f"ℹ️  해당 기간에 체결된 거래가 없습니다.")
            return {
                "start_date": start_date,
                "end_date": end_date,
                "trades": []
            }

        # 통계 계산
        total_trades = len(period_trades)
        total_profit = sum(t['profit'] for t in period_trades)
        total_investment = sum(t['buy_price'] * t['quantity'] for t in period_trades)

        winning_trades = [t for t in period_trades if t['profit'] > 0]
        losing_trades = [t for t in period_trades if t['profit'] < 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        profit_rates = [t['profit_rate'] for t in period_trades]
        avg_profit_rate = sum(profit_rates) / len(profit_rates) if profit_rates else 0

        # 연속 승/패 분석
        max_consecutive_wins = self._calculate_max_consecutive(period_trades, win=True)
        max_consecutive_losses = self._calculate_max_consecutive(period_trades, win=False)

        report = {
            "start_date": start_date,
            "end_date": end_date,
            "total_trades": total_trades,
            "total_profit": total_profit,
            "total_investment": total_investment,
            "roi": (total_profit / total_investment * 100) if total_investment > 0 else 0,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_profit_rate": avg_profit_rate,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "trades": period_trades
        }

        # 출력
        logger.info(f"📈 총 거래: {total_trades}건")
        logger.info(f"💰 총 수익: {total_profit:,}원")
        logger.info(f"💵 총 투자금: {total_investment:,}원")
        logger.info(f"📊 ROI: {report['roi']:+.2f}%")
        logger.info(f"✅ 수익 거래: {len(winning_trades)}건")
        logger.info(f"❌ 손실 거래: {len(losing_trades)}건")
        logger.info(f"🎲 승률: {win_rate:.2f}%")
        logger.info(f"📊 평균 수익률: {avg_profit_rate:+.2f}%")
        logger.info(f"🔥 최대 연속 승: {max_consecutive_wins}회")
        logger.info(f"❄️  최대 연속 패: {max_consecutive_losses}회")
        logger.info("\n" + "=" * 80)

        if save:
            self._save_report(
                report,
                f"custom_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
            )

        return report

    def _calculate_max_consecutive(self, trades: List[Dict], win: bool = True) -> int:
        """연속 승/패 계산"""
        max_consecutive = 0
        current_consecutive = 0

        for trade in trades:
            if win and trade['profit'] > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            elif not win and trade['profit'] < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _save_report(self, report: Dict, filename: str):
        """리포트 파일 저장"""
        report_file = self.reports_dir / f"{filename}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 리포트 저장: {report_file}")

    def compare_strategies(
        self,
        strategy_results: Dict[str, Dict]
    ) -> Dict:
        """
        여러 전략 성과 비교

        Args:
            strategy_results: {전략명: 백테스트 결과} 딕셔너리

        Returns:
            비교 분석 결과
        """
        logger.info("\n" + "=" * 80)
        logger.info("🔬 전략 비교 분석")
        logger.info("=" * 80 + "\n")

        comparison = {}

        for strategy_name, result in strategy_results.items():
            comparison[strategy_name] = {
                "total_return": result.get('total_return', 0),
                "win_rate": result.get('win_rate', 0),
                "sharpe_ratio": result.get('sharpe_ratio', 0),
                "max_drawdown": result.get('max_drawdown', 0),
                "total_trades": result.get('total_trades', 0)
            }

            logger.info(f"📊 {strategy_name}:")
            logger.info(f"   수익률: {comparison[strategy_name]['total_return']:+.2f}%")
            logger.info(f"   승률: {comparison[strategy_name]['win_rate']:.2f}%")
            logger.info(f"   샤프: {comparison[strategy_name]['sharpe_ratio']:.2f}")
            logger.info(f"   MDD: {comparison[strategy_name]['max_drawdown']:.2f}%")
            logger.info(f"   거래수: {comparison[strategy_name]['total_trades']}건\n")

        # 최고 성과 전략 찾기
        best_return = max(comparison.items(), key=lambda x: x[1]['total_return'])
        best_sharpe = max(comparison.items(), key=lambda x: x[1]['sharpe_ratio'])
        lowest_mdd = min(comparison.items(), key=lambda x: x[1]['max_drawdown'])

        logger.info("🏆 최고 성과:")
        logger.info(f"   수익률: {best_return[0]} ({best_return[1]['total_return']:+.2f}%)")
        logger.info(f"   샤프 비율: {best_sharpe[0]} ({best_sharpe[1]['sharpe_ratio']:.2f})")
        logger.info(f"   리스크 관리: {lowest_mdd[0]} (MDD {lowest_mdd[1]['max_drawdown']:.2f}%)")

        logger.info("\n" + "=" * 80)

        return comparison
