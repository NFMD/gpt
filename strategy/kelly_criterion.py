"""
켈리 공식 기반 베팅 사이즈 결정 모듈
거래 실적을 바탕으로 최적의 투자 비율을 계산합니다.
"""
import logging
from typing import Dict, Optional
from .trade_history import TradeHistory


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KellyCriterion:
    """켈리 공식 계산기"""

    def __init__(self, trade_history: TradeHistory):
        self.trade_history = trade_history

    def calculate_kelly_fraction(
        self,
        recent_trades: Optional[int] = 20,
        use_half_kelly: bool = True,
        max_fraction: float = 0.25
    ) -> float:
        """
        켈리 공식으로 베팅 비율 계산

        Kelly Fraction = (p * b - q) / b
        여기서:
        - p = 승률
        - q = 패배율 (1 - p)
        - b = 승리 시 평균 수익률 / 패배 시 평균 손실률의 절댓값

        Args:
            recent_trades: 최근 N개 거래 기반으로 계산 (None이면 전체)
            use_half_kelly: 반켈리(Half Kelly) 사용 여부 (리스크 감소)
            max_fraction: 최대 베팅 비율 (0.25 = 25%)

        Returns:
            베팅 비율 (0.0 ~ max_fraction)
        """
        stats = self.trade_history.get_statistics(recent_trades)

        # 거래 데이터가 부족한 경우
        if stats['total_trades'] < 10:
            logger.warning(
                f"⚠️  거래 데이터 부족 ({stats['total_trades']}건). "
                f"기본 베팅 비율 10% 사용"
            )
            return 0.10

        p = stats['win_rate']  # 승률
        q = 1 - p  # 패배율

        # 승률이 너무 낮으면 베팅하지 않음
        if p < 0.4:
            logger.warning(f"⚠️  승률이 너무 낮음 ({p * 100:.1f}%). 최소 베팅 비율 사용")
            return 0.05

        # 평균 승리 수익률과 평균 손실률
        avg_win = stats['avg_win_rate'] / 100  # % -> 비율
        avg_loss = abs(stats['avg_loss_rate'] / 100)  # % -> 비율 (절댓값)

        # 손실률이 0인 경우 (모든 거래가 이익인 경우)
        if avg_loss == 0:
            logger.info("✅ 모든 거래 이익! 최대 베팅 비율 사용")
            return max_fraction

        # b = 승리 시 수익률 / 손실 시 손실률
        b = avg_win / avg_loss

        # 켈리 공식
        kelly_fraction = (p * b - q) / b

        # 음수인 경우 (기댓값이 마이너스)
        if kelly_fraction <= 0:
            logger.warning(
                f"⚠️  켈리 비율이 음수 ({kelly_fraction:.4f}). "
                f"기댓값이 마이너스이므로 최소 베팅"
            )
            return 0.05

        # Half Kelly 적용
        if use_half_kelly:
            kelly_fraction = kelly_fraction / 2
            logger.info("🔹 Half Kelly 적용 (리스크 감소)")

        # 최대 비율 제한
        kelly_fraction = min(kelly_fraction, max_fraction)

        logger.info("=" * 60)
        logger.info("📐 켈리 공식 계산 결과")
        logger.info("=" * 60)
        logger.info(f"분석 기간: 최근 {recent_trades}건" if recent_trades else "전체 거래")
        logger.info(f"총 거래 횟수: {stats['total_trades']}건")
        logger.info(f"승률 (p): {p * 100:.2f}%")
        logger.info(f"패배율 (q): {q * 100:.2f}%")
        logger.info(f"평균 승리 수익률: {avg_win * 100:+.2f}%")
        logger.info(f"평균 손실률: {avg_loss * 100:.2f}%")
        logger.info(f"리스크/리워드 비율 (b): {b:.2f}")
        logger.info(f"➡️  켈리 비율: {kelly_fraction * 100:.2f}%")
        logger.info("=" * 60)

        return kelly_fraction

    def calculate_position_size(
        self,
        total_capital: int,
        stock_price: int,
        recent_trades: Optional[int] = 20,
        use_half_kelly: bool = True
    ) -> Dict:
        """
        켈리 공식 기반 포지션 사이즈 계산

        Args:
            total_capital: 총 투자 가능 자본
            stock_price: 주식 가격
            recent_trades: 최근 N개 거래 기반
            use_half_kelly: Half Kelly 사용 여부

        Returns:
            포지션 사이즈 정보
        """
        kelly_fraction = self.calculate_kelly_fraction(recent_trades, use_half_kelly)

        # 투자할 금액
        investment_amount = int(total_capital * kelly_fraction)

        # 매수 가능 수량
        quantity = investment_amount // stock_price

        result = {
            "kelly_fraction": kelly_fraction,
            "investment_amount": investment_amount,
            "quantity": quantity,
            "total_cost": quantity * stock_price,
        }

        logger.info(
            f"💰 포지션 사이즈: {quantity}주 "
            f"(투자금: {investment_amount:,}원, 켈리 비율: {kelly_fraction * 100:.2f}%)"
        )

        return result

    def get_recommendation(self, recent_trades: Optional[int] = 20) -> str:
        """
        현재 거래 실적 기반 추천 메시지

        Args:
            recent_trades: 최근 N개 거래 분석

        Returns:
            추천 메시지
        """
        stats = self.trade_history.get_statistics(recent_trades)

        if stats['total_trades'] < 10:
            return "⚠️  거래 데이터 부족. 신중한 매매 필요 (최소 10건 이상 권장)"

        win_rate = stats['win_rate']

        if win_rate >= 0.6:
            return "✅ 우수한 승률! 켈리 공식 기반 적극적 베팅 추천"
        elif win_rate >= 0.5:
            return "👍 양호한 승률. Half Kelly 전략 권장"
        elif win_rate >= 0.4:
            return "⚠️  보통 승률. 보수적 베팅 권장 (Quarter Kelly)"
        else:
            return "❌ 낮은 승률. 전략 재검토 필요. 최소 베팅만 권장"
