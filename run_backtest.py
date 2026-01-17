#!/usr/bin/env python3
"""
백테스트 실행 스크립트

사용법:
    python run_backtest.py --mode backtest --start 20240101 --end 20241231
    python run_backtest.py --mode optimize --start 20240101 --end 20241231
    python run_backtest.py --mode report --type monthly --month 2024-01
"""
import argparse
import logging
from datetime import datetime

from api import KISApi
from backtest import Backtester, PerformanceAnalyzer, StrategyOptimizer
from strategy import TradeHistory
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_backtest(args):
    """백테스트 실행"""
    logger.info("=" * 80)
    logger.info("🔬 백테스트 모드")
    logger.info("=" * 80)

    # API 초기화
    api = KISApi()

    # 백테스터 생성
    backtester = Backtester(
        api=api,
        initial_capital=args.initial_capital
    )

    # 백테스트 실행
    result = backtester.run_backtest(
        start_date=args.start,
        end_date=args.end,
        min_trading_value=args.min_trading_value,
        max_stocks_per_day=args.max_stocks,
        v_reversal_threshold=args.v_threshold
    )

    # 결과 출력
    if result:
        backtester.print_result(result)
    else:
        logger.error("백테스트 실패")


def run_optimization(args):
    """파라미터 최적화 실행"""
    logger.info("=" * 80)
    logger.info("🎯 파라미터 최적화 모드")
    logger.info("=" * 80)

    # API 초기화
    api = KISApi()

    # 최적화기 생성
    optimizer = StrategyOptimizer(
        api=api,
        initial_capital=args.initial_capital
    )

    # 파라미터 그리드 정의
    param_grid = {
        'min_trading_value': [200000000000, 300000000000, 500000000000],
        'max_stocks_per_day': [2, 3, 5],
        'v_reversal_threshold': [60, 70, 80]
    }

    # 최적화 방법 선택
    if args.optimization_method == "grid":
        best_params, best_result = optimizer.grid_search(
            start_date=args.start,
            end_date=args.end,
            param_grid=param_grid,
            optimization_metric=args.metric
        )
    elif args.optimization_method == "random":
        best_params, best_result = optimizer.random_search(
            start_date=args.start,
            end_date=args.end,
            param_distributions=param_grid,
            n_iterations=args.n_iterations,
            optimization_metric=args.metric
        )
    else:
        logger.error(f"지원하지 않는 최적화 방법: {args.optimization_method}")
        return

    logger.info("\n✅ 최적화 완료!")


def run_report(args):
    """성과 리포트 생성"""
    logger.info("=" * 80)
    logger.info("📊 성과 리포트 모드")
    logger.info("=" * 80)

    # TradeHistory 초기화
    trade_history = TradeHistory()

    # 성과 분석기 생성
    analyzer = PerformanceAnalyzer(trade_history)

    # 리포트 타입별 처리
    if args.report_type == "daily":
        analyzer.generate_daily_report(date=args.date)

    elif args.report_type == "weekly":
        analyzer.generate_weekly_report(weeks_back=args.weeks_back)

    elif args.report_type == "monthly":
        analyzer.generate_monthly_report(month=args.month)

    elif args.report_type == "custom":
        if not args.start or not args.end:
            logger.error("커스텀 리포트는 --start와 --end가 필요합니다.")
            return

        analyzer.generate_custom_report(
            start_date=args.start,
            end_date=args.end
        )

    else:
        logger.error(f"지원하지 않는 리포트 타입: {args.report_type}")


def main():
    parser = argparse.ArgumentParser(
        description="한국 주식 자동매매 백테스팅 및 성과 분석"
    )

    # 공통 인자
    parser.add_argument(
        '--mode',
        type=str,
        choices=['backtest', 'optimize', 'report'],
        required=True,
        help='실행 모드 (backtest/optimize/report)'
    )

    parser.add_argument(
        '--initial-capital',
        type=int,
        default=10000000,
        help='초기 자본금 (기본: 1000만원)'
    )

    # 백테스트 관련 인자
    parser.add_argument(
        '--start',
        type=str,
        help='시작일 (YYYYMMDD or YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='종료일 (YYYYMMDD or YYYY-MM-DD)'
    )

    parser.add_argument(
        '--min-trading-value',
        type=int,
        default=200000000000,
        help='최소 거래대금 (기본: 2000억)'
    )

    parser.add_argument(
        '--max-stocks',
        type=int,
        default=3,
        help='일일 최대 매수 종목 수 (기본: 3)'
    )

    parser.add_argument(
        '--v-threshold',
        type=int,
        default=70,
        help='V자 반등 신호 강도 임계값 (기본: 70)'
    )

    # 최적화 관련 인자
    parser.add_argument(
        '--optimization-method',
        type=str,
        choices=['grid', 'random'],
        default='grid',
        help='최적화 방법 (grid/random, 기본: grid)'
    )

    parser.add_argument(
        '--metric',
        type=str,
        choices=['total_return', 'sharpe_ratio', 'win_rate'],
        default='total_return',
        help='최적화 메트릭 (기본: total_return)'
    )

    parser.add_argument(
        '--n-iterations',
        type=int,
        default=20,
        help='Random Search 반복 횟수 (기본: 20)'
    )

    # 리포트 관련 인자
    parser.add_argument(
        '--report-type',
        type=str,
        choices=['daily', 'weekly', 'monthly', 'custom'],
        help='리포트 타입 (daily/weekly/monthly/custom)'
    )

    parser.add_argument(
        '--date',
        type=str,
        help='일일 리포트 날짜 (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--weeks-back',
        type=int,
        default=1,
        help='주간 리포트: 몇 주 전 (기본: 1 = 지난주)'
    )

    parser.add_argument(
        '--month',
        type=str,
        help='월간 리포트 월 (YYYY-MM)'
    )

    args = parser.parse_args()

    # 모드별 실행
    if args.mode == 'backtest':
        if not args.start or not args.end:
            logger.error("백테스트 모드는 --start와 --end가 필요합니다.")
            return
        run_backtest(args)

    elif args.mode == 'optimize':
        if not args.start or not args.end:
            logger.error("최적화 모드는 --start와 --end가 필요합니다.")
            return
        run_optimization(args)

    elif args.mode == 'report':
        if not args.report_type:
            logger.error("리포트 모드는 --report-type이 필요합니다.")
            return
        run_report(args)


if __name__ == "__main__":
    main()
