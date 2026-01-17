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
    """설정 클래스"""

    # API 설정
    KIS_APP_KEY = os.getenv('KIS_APP_KEY', '')
    KIS_APP_SECRET = os.getenv('KIS_APP_SECRET', '')
    KIS_ACCOUNT_NO = os.getenv('KIS_ACCOUNT_NO', '')
    KIS_ACCOUNT_CODE = os.getenv('KIS_ACCOUNT_CODE', '01')

    # 운영 모드
    TRADING_ENABLED = os.getenv('TRADING_ENABLED', 'false').lower() == 'true'

    # 매매 설정
    MAX_STOCKS = int(os.getenv('MAX_STOCKS', 5))
    MAX_INVESTMENT_PER_STOCK = int(os.getenv('MAX_INVESTMENT_PER_STOCK', 1000000))

    # 필터링 기준
    MIN_TRADING_VALUE = int(os.getenv('MIN_TRADING_VALUE', 200000000000))  # 2000억
    MIN_TRADING_VALUE_DOMINANT = int(os.getenv('MIN_TRADING_VALUE_DOMINANT', 1000000000000))  # 1조
    TOP_GAINERS_COUNT = int(os.getenv('TOP_GAINERS_COUNT', 20))
    TOP_VOLUME_COUNT = int(os.getenv('TOP_VOLUME_COUNT', 5))
    NEW_HIGH_DAYS = int(os.getenv('NEW_HIGH_DAYS', 20))

    # 시간 설정
    BUY_TIME_START = os.getenv('BUY_TIME_START', '15:16')  # V자 반등 확인 시작
    BUY_TIME_END = os.getenv('BUY_TIME_END', '15:20')  # 종가 베팅 마감
    SELL_TIME_START = os.getenv('SELL_TIME_START', '09:00')
    SELL_TIME_END = os.getenv('SELL_TIME_END', '10:00')

    # 수익률 설정
    TARGET_PROFIT_RATE = float(os.getenv('TARGET_PROFIT_RATE', 0.045))  # 4.5%
    STOP_LOSS_RATE = float(os.getenv('STOP_LOSS_RATE', -0.03))  # -3%

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
