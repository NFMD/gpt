"""
거래 실적 추적 모듈
모든 거래 기록을 저장하고 분석합니다.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradeHistory:
    """거래 실적 추적기"""

    def __init__(self):
        self.history_file = Path(__file__).parent.parent / "data" / "trade_history.json"
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """거래 기록 로드"""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_history(self):
        """거래 기록 저장"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def add_trade(self, trade: Dict):
        """
        거래 기록 추가

        Args:
            trade: 거래 정보 딕셔너리
                - stock_code: 종목코드
                - stock_name: 종목명
                - buy_date: 매수일
                - sell_date: 매도일
                - buy_price: 매수가
                - sell_price: 매도가
                - quantity: 수량
                - profit: 수익
                - profit_rate: 수익률 (%)
        """
        trade['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.history.append(trade)
        self._save_history()

        logger.info(
            f"📝 거래 기록 추가: {trade['stock_name']} "
            f"수익률 {trade['profit_rate']:+.2f}% (총 {len(self.history)}건)"
        )

    def get_statistics(self, recent_trades: Optional[int] = None) -> Dict:
        """
        거래 통계 계산

        Args:
            recent_trades: 최근 N개 거래만 분석 (None이면 전체)

        Returns:
            통계 딕셔너리
        """
        if not self.history:
            return {
                "total_trades": 0,
                "win_trades": 0,
                "lose_trades": 0,
                "win_rate": 0.0,
                "avg_profit_rate": 0.0,
                "avg_win_rate": 0.0,
                "avg_loss_rate": 0.0,
                "total_profit": 0,
                "max_profit": 0,
                "max_loss": 0,
            }

        # 최근 N개 거래만 분석
        trades = self.history[-recent_trades:] if recent_trades else self.history

        total_trades = len(trades)
        win_trades = [t for t in trades if t['profit_rate'] > 0]
        lose_trades = [t for t in trades if t['profit_rate'] <= 0]

        win_count = len(win_trades)
        lose_count = len(lose_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0

        # 평균 수익률
        avg_profit_rate = sum(t['profit_rate'] for t in trades) / total_trades if total_trades > 0 else 0

        # 평균 수익/손실률
        avg_win_rate = sum(t['profit_rate'] for t in win_trades) / win_count if win_count > 0 else 0
        avg_loss_rate = sum(t['profit_rate'] for t in lose_trades) / lose_count if lose_count > 0 else 0

        # 총 수익
        total_profit = sum(t['profit'] for t in trades)

        # 최대 수익/손실
        max_profit = max((t['profit'] for t in trades), default=0)
        max_loss = min((t['profit'] for t in trades), default=0)

        return {
            "total_trades": total_trades,
            "win_trades": win_count,
            "lose_trades": lose_count,
            "win_rate": win_rate,
            "avg_profit_rate": avg_profit_rate,
            "avg_win_rate": avg_win_rate,
            "avg_loss_rate": avg_loss_rate,
            "total_profit": total_profit,
            "max_profit": max_profit,
            "max_loss": max_loss,
        }

    def print_statistics(self, recent_trades: Optional[int] = None):
        """
        거래 통계 출력

        Args:
            recent_trades: 최근 N개 거래만 분석 (None이면 전체)
        """
        stats = self.get_statistics(recent_trades)

        title = f"최근 {recent_trades}건" if recent_trades else "전체"

        logger.info("=" * 60)
        logger.info(f"📊 거래 통계 ({title})")
        logger.info("=" * 60)
        logger.info(f"총 거래 횟수: {stats['total_trades']}건")
        logger.info(f"승리: {stats['win_trades']}건 | 패배: {stats['lose_trades']}건")
        logger.info(f"승률: {stats['win_rate'] * 100:.2f}%")
        logger.info(f"평균 수익률: {stats['avg_profit_rate']:+.2f}%")
        logger.info(f"평균 승리 수익률: {stats['avg_win_rate']:+.2f}%")
        logger.info(f"평균 손실률: {stats['avg_loss_rate']:+.2f}%")
        logger.info(f"총 수익: {stats['total_profit']:,}원")
        logger.info(f"최대 수익: {stats['max_profit']:,}원")
        logger.info(f"최대 손실: {stats['max_loss']:,}원")
        logger.info("=" * 60)

    def get_recent_trades(self, count: int = 10) -> List[Dict]:
        """
        최근 거래 내역 조회

        Args:
            count: 조회할 거래 수

        Returns:
            최근 거래 리스트
        """
        return self.history[-count:] if self.history else []

    def clear_history(self):
        """모든 거래 기록 삭제"""
        self.history = []
        self._save_history()
        logger.warning("⚠️  모든 거래 기록이 삭제되었습니다.")
