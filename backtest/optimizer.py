"""
파라미터 최적화 모듈
Grid Search와 Random Search를 통해 최적의 전략 파라미터를 탐색합니다.
"""
import logging
from typing import List, Dict, Tuple, Optional
import itertools
import random
from datetime import datetime

from backtest.backtester import Backtester, BacktestResult
from api import KISApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """전략 파라미터 최적화기"""

    def __init__(self, api: KISApi, initial_capital: int = 10000000):
        """
        Args:
            api: KIS API 클라이언트
            initial_capital: 초기 자본금
        """
        self.api = api
        self.initial_capital = initial_capital

    def grid_search(
        self,
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List],
        optimization_metric: str = "total_return"
    ) -> Tuple[Dict, BacktestResult]:
        """
        Grid Search를 통한 파라미터 최적화

        Args:
            start_date: 백테스트 시작일
            end_date: 백테스트 종료일
            param_grid: 파라미터 그리드
                예: {
                    'min_trading_value': [200000000000, 300000000000],
                    'max_stocks_per_day': [2, 3, 5],
                    'v_reversal_threshold': [60, 70, 80]
                }
            optimization_metric: 최적화 기준 메트릭
                - 'total_return': 총 수익률
                - 'sharpe_ratio': 샤프 비율
                - 'win_rate': 승률

        Returns:
            (최적 파라미터, 최적 결과)
        """
        logger.info("\n" + "=" * 80)
        logger.info("🔍 Grid Search 파라미터 최적화 시작")
        logger.info("=" * 80)
        logger.info(f"📅 백테스트 기간: {start_date} ~ {end_date}")
        logger.info(f"🎯 최적화 메트릭: {optimization_metric}")
        logger.info(f"📊 탐색 공간:\n")

        for param, values in param_grid.items():
            logger.info(f"   {param}: {values}")

        # 모든 파라미터 조합 생성
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        all_combinations = list(itertools.product(*param_values))

        total_combinations = len(all_combinations)
        logger.info(f"\n📊 총 {total_combinations}개 조합 탐색\n")
        logger.info("=" * 80 + "\n")

        # 각 조합에 대해 백테스트 실행
        best_score = float('-inf')
        best_params = None
        best_result = None
        results = []

        for idx, combination in enumerate(all_combinations, 1):
            # 파라미터 딕셔너리 생성
            params = dict(zip(param_names, combination))

            logger.info(f"[{idx}/{total_combinations}] 테스트 중...")
            logger.info(f"파라미터: {params}")

            # 백테스트 실행
            backtester = Backtester(self.api, self.initial_capital)
            try:
                result = backtester.run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    min_trading_value=params.get('min_trading_value', 200000000000),
                    max_stocks_per_day=params.get('max_stocks_per_day', 3),
                    v_reversal_threshold=params.get('v_reversal_threshold', 70)
                )

                if result is None:
                    logger.warning("백테스트 실패, 건너뜁니다.\n")
                    continue

                # 메트릭 추출
                if optimization_metric == "total_return":
                    score = result.total_return
                elif optimization_metric == "sharpe_ratio":
                    score = result.sharpe_ratio
                elif optimization_metric == "win_rate":
                    score = result.win_rate
                else:
                    score = result.total_return

                logger.info(f"결과: {optimization_metric} = {score:.2f}\n")

                results.append({
                    'params': params,
                    'result': result,
                    'score': score
                })

                # 최고 성과 업데이트
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result
                    logger.info(f"🏆 새로운 최고 성과! {optimization_metric} = {score:.2f}\n")

            except Exception as e:
                logger.error(f"백테스트 오류: {e}\n")
                continue

        # 최적화 결과 출력
        logger.info("\n" + "=" * 80)
        logger.info("🏆 Grid Search 최적화 완료")
        logger.info("=" * 80)
        logger.info(f"✨ 최적 파라미터:")

        for param, value in best_params.items():
            logger.info(f"   {param}: {value}")

        logger.info(f"\n📊 최적 성과:")
        logger.info(f"   {optimization_metric}: {best_score:.2f}")
        logger.info(f"   총 수익률: {best_result.total_return:+.2f}%")
        logger.info(f"   승률: {best_result.win_rate:.2f}%")
        logger.info(f"   샤프 비율: {best_result.sharpe_ratio:.2f}")
        logger.info(f"   MDD: {best_result.max_drawdown:.2f}%")
        logger.info("=" * 80 + "\n")

        # 결과 저장
        self._save_optimization_result(
            method="grid_search",
            best_params=best_params,
            best_result=best_result,
            all_results=results
        )

        return best_params, best_result

    def random_search(
        self,
        start_date: str,
        end_date: str,
        param_distributions: Dict[str, List],
        n_iterations: int = 20,
        optimization_metric: str = "total_return"
    ) -> Tuple[Dict, BacktestResult]:
        """
        Random Search를 통한 파라미터 최적화

        Args:
            start_date: 백테스트 시작일
            end_date: 백테스트 종료일
            param_distributions: 파라미터 분포
            n_iterations: 탐색 횟수
            optimization_metric: 최적화 기준 메트릭

        Returns:
            (최적 파라미터, 최적 결과)
        """
        logger.info("\n" + "=" * 80)
        logger.info("🎲 Random Search 파라미터 최적화 시작")
        logger.info("=" * 80)
        logger.info(f"📅 백테스트 기간: {start_date} ~ {end_date}")
        logger.info(f"🎯 최적화 메트릭: {optimization_metric}")
        logger.info(f"🔢 탐색 횟수: {n_iterations}회")
        logger.info(f"📊 탐색 공간:\n")

        for param, values in param_distributions.items():
            logger.info(f"   {param}: {values}")

        logger.info("\n" + "=" * 80 + "\n")

        # Random Search 실행
        best_score = float('-inf')
        best_params = None
        best_result = None
        results = []

        for iteration in range(1, n_iterations + 1):
            # 랜덤 파라미터 샘플링
            params = {
                param: random.choice(values)
                for param, values in param_distributions.items()
            }

            logger.info(f"[{iteration}/{n_iterations}] 테스트 중...")
            logger.info(f"파라미터: {params}")

            # 백테스트 실행
            backtester = Backtester(self.api, self.initial_capital)
            try:
                result = backtester.run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    min_trading_value=params.get('min_trading_value', 200000000000),
                    max_stocks_per_day=params.get('max_stocks_per_day', 3),
                    v_reversal_threshold=params.get('v_reversal_threshold', 70)
                )

                if result is None:
                    logger.warning("백테스트 실패, 건너뜁니다.\n")
                    continue

                # 메트릭 추출
                if optimization_metric == "total_return":
                    score = result.total_return
                elif optimization_metric == "sharpe_ratio":
                    score = result.sharpe_ratio
                elif optimization_metric == "win_rate":
                    score = result.win_rate
                else:
                    score = result.total_return

                logger.info(f"결과: {optimization_metric} = {score:.2f}\n")

                results.append({
                    'params': params,
                    'result': result,
                    'score': score
                })

                # 최고 성과 업데이트
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result
                    logger.info(f"🏆 새로운 최고 성과! {optimization_metric} = {score:.2f}\n")

            except Exception as e:
                logger.error(f"백테스트 오류: {e}\n")
                continue

        # 최적화 결과 출력
        logger.info("\n" + "=" * 80)
        logger.info("🏆 Random Search 최적화 완료")
        logger.info("=" * 80)
        logger.info(f"✨ 최적 파라미터:")

        for param, value in best_params.items():
            logger.info(f"   {param}: {value}")

        logger.info(f"\n📊 최적 성과:")
        logger.info(f"   {optimization_metric}: {best_score:.2f}")
        logger.info(f"   총 수익률: {best_result.total_return:+.2f}%")
        logger.info(f"   승률: {best_result.win_rate:.2f}%")
        logger.info(f"   샤프 비율: {best_result.sharpe_ratio:.2f}")
        logger.info(f"   MDD: {best_result.max_drawdown:.2f}%")
        logger.info("=" * 80 + "\n")

        # 결과 저장
        self._save_optimization_result(
            method="random_search",
            best_params=best_params,
            best_result=best_result,
            all_results=results
        )

        return best_params, best_result

    def walk_forward_analysis(
        self,
        start_date: str,
        end_date: str,
        train_period_days: int = 60,
        test_period_days: int = 20,
        param_grid: Dict[str, List] = None
    ) -> List[Dict]:
        """
        Walk-Forward Analysis (전진 분석)

        훈련 기간에서 최적 파라미터를 찾고,
        다음 테스트 기간에서 성과를 검증합니다.

        Args:
            start_date: 분석 시작일
            end_date: 분석 종료일
            train_period_days: 훈련 기간 (일)
            test_period_days: 테스트 기간 (일)
            param_grid: 파라미터 그리드

        Returns:
            각 기간별 결과 리스트
        """
        logger.info("\n" + "=" * 80)
        logger.info("🔄 Walk-Forward Analysis 시작")
        logger.info("=" * 80)
        logger.info(f"📅 전체 기간: {start_date} ~ {end_date}")
        logger.info(f"🔧 훈련 기간: {train_period_days}일")
        logger.info(f"🧪 테스트 기간: {test_period_days}일")
        logger.info("=" * 80 + "\n")

        if param_grid is None:
            param_grid = {
                'min_trading_value': [200000000000, 300000000000],
                'max_stocks_per_day': [2, 3],
                'v_reversal_threshold': [60, 70]
            }

        # TODO: 구현
        # 1. 전체 기간을 train + test 윈도우로 슬라이딩
        # 2. 각 윈도우에서 train 기간으로 최적 파라미터 탐색
        # 3. 찾은 파라미터로 test 기간에서 성과 검증
        # 4. 전체 기간의 평균 성과 계산

        logger.info("ℹ️  Walk-Forward Analysis는 추후 구현 예정입니다.\n")

        return []

    def _save_optimization_result(
        self,
        method: str,
        best_params: Dict,
        best_result: BacktestResult,
        all_results: List[Dict]
    ):
        """최적화 결과 저장"""
        from pathlib import Path
        import json

        results_dir = Path(__file__).parent.parent / "optimization_results"
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = results_dir / f"{method}_{timestamp}.json"

        optimization_data = {
            "method": method,
            "timestamp": timestamp,
            "best_params": best_params,
            "best_result": {
                "total_return": best_result.total_return,
                "win_rate": best_result.win_rate,
                "sharpe_ratio": best_result.sharpe_ratio,
                "max_drawdown": best_result.max_drawdown,
                "total_trades": best_result.total_trades
            },
            "all_results": [
                {
                    "params": r['params'],
                    "score": r['score'],
                    "total_return": r['result'].total_return,
                    "win_rate": r['result'].win_rate
                }
                for r in all_results
            ]
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(optimization_data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 최적화 결과 저장: {result_file}")
