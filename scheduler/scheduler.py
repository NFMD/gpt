"""
스케줄러 모듈
시간대별 자동 실행을 관리합니다.
"""
import schedule
import time
import logging
from datetime import datetime
from api import KISApi
from trading import TradingEngine
from config import Config


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingScheduler:
    """자동매매 스케줄러"""

    def __init__(self):
        self.api = KISApi()
        self.engine = TradingEngine(self.api)

    def job_morning_check(self):
        """장 시작 전 체크"""
        logger.info("🌅 장 시작 전 시스템 체크")
        try:
            # 포트폴리오 확인
            self.engine.check_portfolio()
        except Exception as e:
            logger.error(f"❌ 오류 발생: {e}")

    def job_morning_sell(self):
        """오전 매도 작업"""
        logger.info("💸 오전 매도 작업 시작")
        try:
            self.engine.execute_morning_sell()
        except Exception as e:
            logger.error(f"❌ 매도 오류: {e}")

    def job_market_scan(self):
        """장중 시장 스캔 (선택적)"""
        logger.info("🔍 시장 스캔")
        try:
            self.engine.scan_market()
        except Exception as e:
            logger.error(f"❌ 스캔 오류: {e}")

    def job_closing_bet(self):
        """종가 베팅 작업"""
        logger.info("💰 종가 베팅 작업 시작")
        try:
            self.engine.execute_closing_bet()
        except Exception as e:
            logger.error(f"❌ 매수 오류: {e}")

    def job_daily_summary(self):
        """일일 마감 요약"""
        logger.info("📊 일일 마감 요약")
        try:
            self.engine.check_portfolio()
        except Exception as e:
            logger.error(f"❌ 요약 오류: {e}")

    def setup_schedule(self):
        """스케줄 설정"""
        logger.info("⏰ 자동매매 스케줄러 설정")
        logger.info("=" * 60)

        # 장 시작 전 체크 (08:50)
        schedule.every().monday.at("08:50").do(self.job_morning_check)
        schedule.every().tuesday.at("08:50").do(self.job_morning_check)
        schedule.every().wednesday.at("08:50").do(self.job_morning_check)
        schedule.every().thursday.at("08:50").do(self.job_morning_check)
        schedule.every().friday.at("08:50").do(self.job_morning_check)
        logger.info("✅ 08:50 - 장 시작 전 체크")

        # 오전 매도 (09:30, 09:50)
        schedule.every().monday.at("09:30").do(self.job_morning_sell)
        schedule.every().tuesday.at("09:30").do(self.job_morning_sell)
        schedule.every().wednesday.at("09:30").do(self.job_morning_sell)
        schedule.every().thursday.at("09:30").do(self.job_morning_sell)
        schedule.every().friday.at("09:30").do(self.job_morning_sell)
        logger.info("✅ 09:30 - 오전 매도 (1차)")

        schedule.every().monday.at("09:50").do(self.job_morning_sell)
        schedule.every().tuesday.at("09:50").do(self.job_morning_sell)
        schedule.every().wednesday.at("09:50").do(self.job_morning_sell)
        schedule.every().thursday.at("09:50").do(self.job_morning_sell)
        schedule.every().friday.at("09:50").do(self.job_morning_sell)
        logger.info("✅ 09:50 - 오전 매도 (2차)")

        # 장중 시장 스캔 (선택적, 14:30)
        schedule.every().monday.at("14:30").do(self.job_market_scan)
        schedule.every().tuesday.at("14:30").do(self.job_market_scan)
        schedule.every().wednesday.at("14:30").do(self.job_market_scan)
        schedule.every().thursday.at("14:30").do(self.job_market_scan)
        schedule.every().friday.at("14:30").do(self.job_market_scan)
        logger.info("✅ 14:30 - 시장 스캔")

        # 종가 베팅 (15:10)
        schedule.every().monday.at("15:10").do(self.job_closing_bet)
        schedule.every().tuesday.at("15:10").do(self.job_closing_bet)
        schedule.every().wednesday.at("15:10").do(self.job_closing_bet)
        schedule.every().thursday.at("15:10").do(self.job_closing_bet)
        schedule.every().friday.at("15:10").do(self.job_closing_bet)
        logger.info("✅ 15:10 - 종가 베팅")

        # 일일 마감 요약 (15:40)
        schedule.every().monday.at("15:40").do(self.job_daily_summary)
        schedule.every().tuesday.at("15:40").do(self.job_daily_summary)
        schedule.every().wednesday.at("15:40").do(self.job_daily_summary)
        schedule.every().thursday.at("15:40").do(self.job_daily_summary)
        schedule.every().friday.at("15:40").do(self.job_daily_summary)
        logger.info("✅ 15:40 - 일일 마감 요약")

        logger.info("=" * 60)
        logger.info("✅ 스케줄러 설정 완료")

    def run(self):
        """스케줄러 실행"""
        self.setup_schedule()

        logger.info("\n🚀 자동매매 시스템 가동")
        logger.info(f"📅 현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"⚙️  거래 모드: {'실거래' if Config.TRADING_ENABLED else '모의거래'}")
        logger.info("\n대기 중... (Ctrl+C로 종료)\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  자동매매 시스템 종료")


def run_scheduler():
    """스케줄러 실행 함수"""
    scheduler = TradingScheduler()
    scheduler.run()
