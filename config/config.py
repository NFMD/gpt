"""
설정 관리 모듈
환경 변수와 설정값을 로드하고 관리합니다.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 로드
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """설정 클래스 (v1.1)"""

    # API 설정
    KIS_APP_KEY = os.getenv('KIS_APP_KEY', '')
    KIS_APP_SECRET = os.getenv('KIS_APP_SECRET', '')
    KIS_ACCOUNT_NO = os.getenv('KIS_ACCOUNT_NO', '')
    KIS_ACCOUNT_CODE = os.getenv('KIS_ACCOUNT_CODE', '01')

    # AI 모델 설정
    COMMANDER_MODEL = "gpt-4o"  # Claude Opus 대신 GPT-4o 사용 (환경 제약 고려)
    CRAWLER_MODEL = "gpt-4o-mini"
    EXPLORER_MODEL = "gemini-1.5-flash"
    ANALYST_MODEL = "gpt-4o-mini"

    # 운영 모드
    TRADING_ENABLED = os.getenv('TRADING_ENABLED', 'false').lower() == 'true'

    # 매매 설정
    MAX_STOCKS = int(os.getenv('MAX_STOCKS', 5))
    MAX_INVESTMENT_PER_STOCK_PCT = 0.30  # 단일 종목 최대 비중 30%
    MIN_CASH_PCT = 0.20  # 현금 보유 최소 20%

    # PHASE 1: 유니버스 필터 (MUST)
    MIN_MARKET_CAP = 300000000000  # 3,000억
    MIN_TRADING_VALUE = 100000000000  # 1,000억
    MIN_CHANGE_RATE = 2.0
    MAX_CHANGE_RATE = 15.0

    # PHASE 2: 기술적 검증 (SHOULD/BONUS)
    NEW_HIGH_DAYS = 20
    PHASE2_MIN_SCORE = 35

    # PHASE 3: 심리적 검증
    NEWS_COUNT_THRESHOLD = 20
    SENTIMENT_THRESHOLD = 60

    # PHASE 4: V자 반등 (MUST)
    V_REBOUND_THRESHOLD = 0.005  # 0.5%
    V_TIME_START = "15:16:00"
    V_TIME_END = "15:19:30"

    # 시간 설정
    BUY_TIME_START = "14:30"
    BUY_TIME_END = "15:20"
    SELL_TIME_START = "09:00"
    SELL_TIME_END = "10:00"

    # 수익률 및 리스크 설정
    TARGET_PROFIT_RATE = 0.02  # 평균 수익 목표
    STOP_LOSS_RATE = -0.03  # -3% 절대 손절
    EMERGENCY_KOSPI_DROP = -2.0  # 코스피 -2% 시 비상 청산

    # API URL
    KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
    KIS_BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"
    KIS_BASE_URL_VIRTUAL = "https://openapivts.koreainvestment.com:9443"

    @classmethod
    def validate(cls):
        """설정 검증"""
        if cls.TRADING_ENABLED:
            if not all([cls.KIS_APP_KEY, cls.KIS_APP_SECRET, cls.KIS_ACCOUNT_NO]):
                raise ValueError("실거래 모드에서는 API 키와 계좌번호가 필요합니다.")
        return True


# 설정 검증
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️  설정 오류: {e}")
