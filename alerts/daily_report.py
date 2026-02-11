"""
일일 리포트 생성기 (v2.0)
매일 장 마감 후 트레이딩 성과를 요약합니다.

섹션 10: 성과 측정 — 핵심 KPI 및 백테스팅 설정
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Optional
from data.database import TradingDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 핵심 KPI 목표값
# ═══════════════════════════════════════════════════════

KPI_TARGETS = {
    "win_rate": 0.55,
    "win_loss_ratio": 1.5,
    "daily_avg_return": 0.003,
    "max_mdd": -15.0,
    "sharpe_ratio": 1.5,
    "trade_freq_min": 1,
    "trade_freq_max": 3,
    "ensemble_hit_rate": 0.60,
}


# ═══════════════════════════════════════════════════════
# 백테스팅 설정
# ═══════════════════════════════════════════════════════

BACKTEST_CONFIG = {
    "train_period": ("2022-01-01", "2023-12-31"),
    "validate_period": ("2024-01-01", "2024-06-30"),
    "paper_period": ("2024-07-01", "2024-09-30"),
    "live_test_period": ("2024-10-01", None),
    "slippage": 0.001,
    "commission": 0.0025,
    "entry_delay_sec": 60,
    "exit_type": "market",
    "strategies": {
        "A": "기본 (V자 반등 단독)",
        "B": "기본 + 감정분석 필터",
        "C": "기본 + 테마 지속성 필터",
        "D": "B + C 통합",
        "E": "4가지 앙상블 통합 (v2.0)",
    },
    "market_conditions": [
        "상승장 (코스피 +10%↑)",
        "하락장 (코스피 -10%↓)",
        "횡보장 (코스피 ±5% 이내)",
        "급등락장 (일중 변동 ±2%↑)",
    ],
    "min_samples": 100,
}


class DailyReportGenerator:
    """일일 트레이딩 리포트 생성기"""

    def __init__(self, db: TradingDatabase = None):
        self.db = db or TradingDatabase()

    def generate(
        self,
        today_trades: List[Dict] = None,
        market_data: Dict = None,
        ai_cost: float = 3.02,
        watchlist: List[str] = None,
    ) -> str:
        """
        일일 리포트 생성

        Args:
            today_trades: 오늘 체결된 거래 리스트
            market_data: 시장 데이터 {kospi_change, kosdaq_change}
            ai_cost: AI 호출 비용 (USD)
            watchlist: 내일 관심 종목 리스트

        Returns:
            포매팅된 리포트 문자열
        """
        today = date.today().isoformat()
        trades = today_trades or []
        market = market_data or {}

        # 오늘 거래 통계
        wins = [t for t in trades if (t.get('pnl_percent') or 0) > 0]
        losses = [t for t in trades if (t.get('pnl_percent') or 0) <= 0]
        total_pnl = sum(t.get('pnl', 0) or 0 for t in trades)
        total_pnl_pct = sum(t.get('pnl_percent', 0) or 0 for t in trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        # 누적 통계
        stats = self.db.get_trade_statistics()
        mdd = self.db.calculate_mdd()

        # 샤프 비율 (일별 성과에서 가져옴)
        perf_history = self.db.get_daily_performance_history(days=30)
        sharpe = perf_history[0].get('sharpe_ratio', 0) if perf_history else 0

        # 거래 상세
        trade_details = self._format_trade_details(trades)

        # 관심 종목
        watchlist_str = "\n".join(f"  - {w}" for w in (watchlist or [])) or "  없음"

        # 앙상블 적중률 (70점↑ 종목 중 수익 비율)
        ensemble_hit = self._calc_ensemble_hit_rate(trades)

        report = (
            f"**일일 트레이딩 리포트**\n"
            f"{'━' * 32}\n"
            f"날짜: {today}\n"
            f"시장: 코스피 {market.get('kospi_change', 0):+.1f}% / "
            f"코스닥 {market.get('kosdaq_change', 0):+.1f}%\n\n"
            f"오늘 성과:\n"
            f"  총 거래: {len(trades)}건\n"
            f"  승/패: {len(wins)}/{len(losses)}\n"
            f"  승률: {win_rate:.1f}%\n"
            f"  총 손익: {total_pnl:+,.0f}원 ({total_pnl_pct:+.2f}%)\n\n"
            f"누적 성과:\n"
            f"  누적 손익: {stats.get('total_pnl', 0):+,.0f}원\n"
            f"  누적 승률: {stats.get('win_rate', 0) * 100:.1f}%\n"
            f"  MDD: {mdd:.2f}%\n"
            f"  샤프비율: {sharpe:.2f}\n\n"
            f"앙상블 적중률: {ensemble_hit:.1f}% (70점↑ 종목)\n\n"
            f"거래 상세:\n{trade_details}\n\n"
            f"내일 관심:\n{watchlist_str}\n\n"
            f"AI 비용: ${ai_cost:.2f}\n"
            f"{'━' * 32}"
        )

        return report

    def _format_trade_details(self, trades: List[Dict]) -> str:
        """거래 상세 포매팅"""
        if not trades:
            return "  거래 없음"

        lines = []
        for t in trades:
            name = t.get('name', t.get('stock_name', ''))
            pnl = t.get('pnl', 0) or 0
            pnl_pct = t.get('pnl_percent', 0) or 0
            scenario = t.get('exit_scenario', '')
            ensemble = t.get('ensemble_score', 0) or 0

            icon = "+" if pnl >= 0 else "-"
            lines.append(
                f"  {icon} {name} | {pnl_pct:+.2f}% ({pnl:+,.0f}원) | "
                f"시나리오={scenario} | 앙상블={ensemble:.0f}"
            )

        return "\n".join(lines)

    def _calc_ensemble_hit_rate(self, trades: List[Dict]) -> float:
        """앙상블 70점↑ 종목의 승률 계산"""
        high_ensemble = [
            t for t in trades
            if (t.get('ensemble_score') or 0) >= 70
        ]
        if not high_ensemble:
            return 0.0

        wins = [t for t in high_ensemble if (t.get('pnl_percent') or 0) > 0]
        return len(wins) / len(high_ensemble) * 100

    def generate_kpi_check(self) -> str:
        """KPI 달성 현황 체크 리포트"""
        stats = self.db.get_trade_statistics()
        mdd = self.db.calculate_mdd()

        checks = []
        win_rate = stats.get('win_rate', 0)
        checks.append(
            f"  승률: {win_rate * 100:.1f}% "
            f"({'OK' if win_rate >= KPI_TARGETS['win_rate'] else 'MISS'} "
            f"목표 {KPI_TARGETS['win_rate'] * 100}%)"
        )

        avg_win = abs(stats.get('avg_win_pct', 0))
        avg_loss = abs(stats.get('avg_loss_pct', 0))
        wl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        checks.append(
            f"  손익비: {wl_ratio:.2f}:1 "
            f"({'OK' if wl_ratio >= KPI_TARGETS['win_loss_ratio'] else 'MISS'} "
            f"목표 {KPI_TARGETS['win_loss_ratio']}:1)"
        )

        checks.append(
            f"  MDD: {mdd:.2f}% "
            f"({'OK' if mdd >= KPI_TARGETS['max_mdd'] else 'MISS'} "
            f"목표 {KPI_TARGETS['max_mdd']}%)"
        )

        return (
            f"**KPI 달성 현황**\n"
            f"{'━' * 24}\n"
            + "\n".join(checks)
        )

    def save_daily_performance(
        self,
        total_asset: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        trades: List[Dict],
        market_data: Dict = None,
        regime: str = "NORMAL",
    ):
        """일별 성과를 DB에 저장"""
        market = market_data or {}
        wins = [t for t in trades if (t.get('pnl_percent') or 0) > 0]
        losses = [t for t in trades if (t.get('pnl_percent') or 0) <= 0]

        # 누적 수익 계산
        perf_history = self.db.get_daily_performance_history(days=1)
        prev_cum = perf_history[0].get('cumulative_pnl', 0) if perf_history else 0

        mdd = self.db.calculate_mdd()

        self.db.insert_daily_performance({
            "date": date.today().isoformat(),
            "total_asset": total_asset,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "cumulative_pnl": prev_cum + daily_pnl,
            "cumulative_return": 0,  # 별도 계산 필요
            "trade_count": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": len(wins) / len(trades) if trades else 0,
            "avg_win_pct": (
                sum(t.get('pnl_percent', 0) or 0 for t in wins) / len(wins)
                if wins else 0
            ),
            "avg_loss_pct": (
                sum(t.get('pnl_percent', 0) or 0 for t in losses) / len(losses)
                if losses else 0
            ),
            "mdd": mdd,
            "sharpe_ratio": 0,  # 별도 계산 필요
            "kospi_change": market.get('kospi_change', 0),
            "kosdaq_change": market.get('kosdaq_change', 0),
            "market_regime": regime,
        })
        logger.info("[REPORT] 일별 성과 DB 저장 완료")
