"""
SQLite 데이터베이스 모듈 (v2.0)
매매 기록, 일별 스냅샷, 테마 성과, 일별 성과, 거시 레짐 로그를 관리합니다.

v2.0 변경사항:
- 앙상블 점수 + 로직별 점수 + 청산사유 추가 (trade_history)
- daily_snapshot 테이블 신규
- theme_performance 테이블 신규
- daily_performance 테이블 신규
- macro_regime_log 테이블 신규
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "trading.db"


class TradingDatabase:
    """매매 데이터베이스 (v2.0)"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()
        logger.info(f"[DB] TradingDatabase (v2.0) 초기화 | {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """데이터베이스 및 테이블 초기화"""
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
            logger.info("[DB] 스키마 초기화 완료")
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # trade_history
    # ═══════════════════════════════════════════════════
    def insert_trade(self, trade: Dict) -> int:
        """매매 기록 삽입"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO trade_history (
                    symbol, name, theme,
                    entry_date, entry_time, entry_price, quantity, weight_pct,
                    exit_date, exit_time, exit_price, exit_scenario, exit_reason,
                    pnl, pnl_percent,
                    phase2_score, phase3_score, v_pattern_score,
                    ensemble_score, logic1_tow_score, logic2_v_score,
                    logic3_moc_score, logic4_news_score,
                    ai_confidence, notes
                ) VALUES (
                    :symbol, :name, :theme,
                    :entry_date, :entry_time, :entry_price, :quantity, :weight_pct,
                    :exit_date, :exit_time, :exit_price, :exit_scenario, :exit_reason,
                    :pnl, :pnl_percent,
                    :phase2_score, :phase3_score, :v_pattern_score,
                    :ensemble_score, :logic1_tow_score, :logic2_v_score,
                    :logic3_moc_score, :logic4_news_score,
                    :ai_confidence, :notes
                )
            """, trade)
            conn.commit()
            trade_id = cursor.lastrowid
            logger.info(f"[DB] 매매 기록 삽입: ID={trade_id}, {trade.get('name')}")
            return trade_id
        finally:
            conn.close()

    def update_trade_exit(self, trade_id: int, exit_info: Dict):
        """매매 청산 정보 업데이트"""
        conn = self._get_conn()
        try:
            conn.execute("""
                UPDATE trade_history SET
                    exit_date = :exit_date,
                    exit_time = :exit_time,
                    exit_price = :exit_price,
                    exit_scenario = :exit_scenario,
                    exit_reason = :exit_reason,
                    pnl = :pnl,
                    pnl_percent = :pnl_percent
                WHERE id = :trade_id
            """, {**exit_info, "trade_id": trade_id})
            conn.commit()
            logger.info(f"[DB] 청산 정보 업데이트: ID={trade_id}")
        finally:
            conn.close()

    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """최근 매매 기록 조회"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trade_history ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trade_statistics(self, recent_n: Optional[int] = None) -> Dict:
        """매매 통계 산출"""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM trade_history WHERE pnl IS NOT NULL ORDER BY id DESC"
            if recent_n:
                query += f" LIMIT {recent_n}"
            rows = conn.execute(query).fetchall()
            trades = [dict(r) for r in rows]

            if not trades:
                return {
                    "total": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "avg_pnl_pct": 0.0,
                    "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
                    "total_pnl": 0.0,
                }

            wins = [t for t in trades if (t.get("pnl_percent") or 0) > 0]
            losses = [t for t in trades if (t.get("pnl_percent") or 0) <= 0]

            return {
                "total": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) if trades else 0,
                "avg_pnl_pct": sum(t.get("pnl_percent", 0) or 0 for t in trades) / len(trades),
                "avg_win_pct": (sum(t.get("pnl_percent", 0) or 0 for t in wins) / len(wins)
                                if wins else 0),
                "avg_loss_pct": (sum(t.get("pnl_percent", 0) or 0 for t in losses) / len(losses)
                                 if losses else 0),
                "total_pnl": sum(t.get("pnl", 0) or 0 for t in trades),
            }
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # daily_snapshot
    # ═══════════════════════════════════════════════════
    def insert_daily_snapshot(self, snapshot: Dict):
        """일별 종목 스냅샷 삽입 (UPSERT)"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO daily_snapshot (
                    date, symbol, name,
                    close_price, change_pct, high_price, low_price,
                    volume, trading_value,
                    program_net_buy, foreign_net_buy, institution_net_buy,
                    news_count, google_news_count, sentiment_score, forum_post_count,
                    is_new_high_20d, is_new_high_all, ma5, ma20, ma60, is_aligned,
                    phase1_pass, phase2_score, phase3_score
                ) VALUES (
                    :date, :symbol, :name,
                    :close_price, :change_pct, :high_price, :low_price,
                    :volume, :trading_value,
                    :program_net_buy, :foreign_net_buy, :institution_net_buy,
                    :news_count, :google_news_count, :sentiment_score, :forum_post_count,
                    :is_new_high_20d, :is_new_high_all, :ma5, :ma20, :ma60, :is_aligned,
                    :phase1_pass, :phase2_score, :phase3_score
                )
            """, snapshot)
            conn.commit()
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # daily_performance
    # ═══════════════════════════════════════════════════
    def insert_daily_performance(self, perf: Dict):
        """일별 성과 기록 삽입 (UPSERT)"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO daily_performance (
                    date, total_asset, daily_pnl, daily_pnl_pct,
                    cumulative_pnl, cumulative_return,
                    trade_count, win_count, loss_count, win_rate,
                    avg_win_pct, avg_loss_pct,
                    mdd, sharpe_ratio,
                    kospi_change, kosdaq_change, market_regime
                ) VALUES (
                    :date, :total_asset, :daily_pnl, :daily_pnl_pct,
                    :cumulative_pnl, :cumulative_return,
                    :trade_count, :win_count, :loss_count, :win_rate,
                    :avg_win_pct, :avg_loss_pct,
                    :mdd, :sharpe_ratio,
                    :kospi_change, :kosdaq_change, :market_regime
                )
            """, perf)
            conn.commit()
        finally:
            conn.close()

    def get_daily_performance_history(self, days: int = 30) -> List[Dict]:
        """최근 N일 성과 조회"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM daily_performance ORDER BY date DESC LIMIT ?",
                (days,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # macro_regime_log
    # ═══════════════════════════════════════════════════
    def insert_macro_regime_log(self, log: Dict):
        """거시 레짐 로그 삽입"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO macro_regime_log (
                    timestamp, regime,
                    us_futures_change, vix, kospi_change,
                    trigger_reason
                ) VALUES (
                    :timestamp, :regime,
                    :us_futures_change, :vix, :kospi_change,
                    :trigger_reason
                )
            """, log)
            conn.commit()
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # theme_performance
    # ═══════════════════════════════════════════════════
    def insert_theme_performance(self, theme: Dict):
        """테마 성과 기록 삽입"""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO theme_performance (
                    theme_name, start_date, duration_days,
                    avg_return, max_return, success_rate, sample_count
                ) VALUES (
                    :theme_name, :start_date, :duration_days,
                    :avg_return, :max_return, :success_rate, :sample_count
                )
            """, theme)
            conn.commit()
        finally:
            conn.close()

    def get_theme_performance(self, theme_name: str = None) -> List[Dict]:
        """테마 성과 조회"""
        conn = self._get_conn()
        try:
            if theme_name:
                rows = conn.execute(
                    "SELECT * FROM theme_performance WHERE theme_name = ? ORDER BY start_date DESC",
                    (theme_name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM theme_performance ORDER BY start_date DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════
    # MDD 계산
    # ═══════════════════════════════════════════════════
    def calculate_mdd(self) -> float:
        """전체 기간 MDD 계산"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT total_asset FROM daily_performance ORDER BY date ASC"
            ).fetchall()
            if not rows:
                return 0.0

            assets = [r["total_asset"] for r in rows]
            peak = assets[0]
            max_drawdown = 0.0

            for asset in assets:
                if asset > peak:
                    peak = asset
                drawdown = (asset - peak) / peak * 100
                if drawdown < max_drawdown:
                    max_drawdown = drawdown

            return round(max_drawdown, 2)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════
# SQL 스키마 정의
# ═══════════════════════════════════════════════════════════
SCHEMA_SQL = """
-- 매매 기록 (v2.0: 앙상블 점수 + 로직별 점수 + 청산사유 추가)
CREATE TABLE IF NOT EXISTS trade_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              VARCHAR(10) NOT NULL,
    name                VARCHAR(50),
    theme               VARCHAR(100),

    -- 진입 정보
    entry_date          DATE NOT NULL,
    entry_time          TIME NOT NULL,
    entry_price         DECIMAL(10,2) NOT NULL,
    quantity            INTEGER NOT NULL,
    weight_pct          DECIMAL(5,2),

    -- 청산 정보
    exit_date           DATE,
    exit_time           TIME,
    exit_price          DECIMAL(10,2),
    exit_scenario       VARCHAR(20),
    exit_reason         VARCHAR(100),

    -- 손익
    pnl                 DECIMAL(10,2),
    pnl_percent         DECIMAL(5,2),

    -- 점수 기록
    phase2_score        INTEGER,
    phase3_score        INTEGER,
    v_pattern_score     INTEGER,
    ensemble_score      DECIMAL(5,1),
    logic1_tow_score    DECIMAL(5,1),
    logic2_v_score      DECIMAL(5,1),
    logic3_moc_score    DECIMAL(5,1),
    logic4_news_score   DECIMAL(5,1),
    ai_confidence       INTEGER,

    -- 메타
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 일별 종목 스냅샷
CREATE TABLE IF NOT EXISTS daily_snapshot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                DATE NOT NULL,
    symbol              VARCHAR(10) NOT NULL,
    name                VARCHAR(50),

    -- 가격 데이터
    close_price         DECIMAL(10,2),
    change_pct          DECIMAL(5,2),
    high_price          DECIMAL(10,2),
    low_price           DECIMAL(10,2),

    -- 거래 데이터
    volume              BIGINT,
    trading_value       BIGINT,

    -- 수급 데이터
    program_net_buy     BIGINT,
    foreign_net_buy     BIGINT,
    institution_net_buy BIGINT,

    -- 심리 데이터
    news_count          INTEGER,
    google_news_count   INTEGER,
    sentiment_score     DECIMAL(3,2),
    forum_post_count    INTEGER,

    -- 기술적 데이터
    is_new_high_20d     BOOLEAN,
    is_new_high_all     BOOLEAN,
    ma5                 DECIMAL(10,2),
    ma20                DECIMAL(10,2),
    ma60                DECIMAL(10,2),
    is_aligned          BOOLEAN,

    -- PHASE 결과
    phase1_pass         BOOLEAN,
    phase2_score        INTEGER,
    phase3_score        INTEGER,

    UNIQUE(date, symbol)
);

-- 테마/재료별 성과 백데이터
CREATE TABLE IF NOT EXISTS theme_performance (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_name          VARCHAR(100) NOT NULL,
    start_date          DATE,
    duration_days       INTEGER,
    avg_return          DECIMAL(5,2),
    max_return          DECIMAL(5,2),
    success_rate        DECIMAL(3,2),
    sample_count        INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 일별 계좌 성과
CREATE TABLE IF NOT EXISTS daily_performance (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                DATE NOT NULL UNIQUE,

    -- 성과
    total_asset         DECIMAL(15,2),
    daily_pnl           DECIMAL(10,2),
    daily_pnl_pct       DECIMAL(5,2),
    cumulative_pnl      DECIMAL(15,2),
    cumulative_return   DECIMAL(5,2),

    -- 거래 통계
    trade_count         INTEGER,
    win_count           INTEGER,
    loss_count          INTEGER,
    win_rate            DECIMAL(3,2),
    avg_win_pct         DECIMAL(5,2),
    avg_loss_pct        DECIMAL(5,2),

    -- 리스크 지표
    mdd                 DECIMAL(5,2),
    sharpe_ratio        DECIMAL(5,2),

    -- 시장 상태
    kospi_change        DECIMAL(5,2),
    kosdaq_change       DECIMAL(5,2),
    market_regime       VARCHAR(20),

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 거시 레짐 로그
CREATE TABLE IF NOT EXISTS macro_regime_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TIMESTAMP NOT NULL,
    regime              VARCHAR(20) NOT NULL,
    us_futures_change   DECIMAL(5,2),
    vix                 DECIMAL(5,2),
    kospi_change        DECIMAL(5,2),
    trigger_reason      VARCHAR(200),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
