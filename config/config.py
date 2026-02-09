"""
설정 관리 모듈 (v2.0)
환경 변수와 설정값을 로드하고 관리합니다.

v2.0 변경사항:
- 앙상블 가중치 설정 추가
- 거시 환경 필터 임계값 추가
- VETO 키워드 관련 설정 추가
- 뉴스 확산성 기준 추가
- 장후 데이터 수집 시간 설정 추가
- AI 활성화 시간 설정 추가
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 로드
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """설정 클래스 (v2.0)"""

    # ── API 설정 ──
    KIS_APP_KEY = os.getenv('KIS_APP_KEY', '')
    KIS_APP_SECRET = os.getenv('KIS_APP_SECRET', '')
    KIS_ACCOUNT_NO = os.getenv('KIS_ACCOUNT_NO', '')
    KIS_ACCOUNT_CODE = os.getenv('KIS_ACCOUNT_CODE', '01')

    # ── AI 모델 설정 ──
    COMMANDER_MODEL = "claude-opus-4-6"    # COMMANDER: Claude Opus
    CRAWLER_MODEL = "glm-4"               # CRAWLER: GLM
    EXPLORER_MODEL = "gemini-2.0-flash"    # EXPLORER: Gemini
    ANALYST_MODEL = "gpt-4o"              # ANALYST: GPT

    # ── 운영 모드 ──
    TRADING_ENABLED = os.getenv('TRADING_ENABLED', 'false').lower() == 'true'

    # ── 매매 설정 ──
    MAX_STOCKS = int(os.getenv('MAX_STOCKS', 5))
    MAX_INVESTMENT_PER_STOCK_PCT = 0.30  # 단일 종목 최대 비중 30%
    MIN_CASH_PCT = 0.20  # 현금 보유 최소 20%

    # ── PHASE 1: 유니버스 필터 (MUST) ──
    MIN_MARKET_CAP = 300_000_000_000     # 3,000억
    MIN_TRADING_VALUE = 100_000_000_000  # 1,000억 (조 단위 거래대금)
    MIN_CHANGE_RATE = 2.0
    MAX_CHANGE_RATE = 15.0

    # ── PHASE 2: 기술적 검증 (SHOULD/BONUS) ──
    NEW_HIGH_DAYS = 20
    PHASE2_MIN_SCORE = 35

    # ── PHASE 3: 심리적 검증 ──
    NEWS_COUNT_THRESHOLD = 20
    SENTIMENT_THRESHOLD = 60

    # ── PHASE 4: V자 반등 (MUST) ──
    V_REBOUND_THRESHOLD = 0.005  # 0.5%
    V_TIME_START = "15:16:00"
    V_TIME_END = "15:19:30"

    # ── 시간 설정 ──
    BUY_TIME_START = "14:30"
    BUY_TIME_END = "15:20"
    SELL_TIME_START = "09:00"
    SELL_TIME_END = "10:00"

    # ── 수익률 및 리스크 설정 ──
    TARGET_PROFIT_RATE = 0.02       # 평균 수익 목표
    STOP_LOSS_RATE = -0.03          # -3% 절대 손절
    EMERGENCY_KOSPI_DROP = -2.0     # 코스피 -2% 시 비상 청산
    MAX_MDD = -15.0                 # 최대 허용 MDD (v2.0)
    MAX_SINGLE_LOSS_PCT = -3.0      # 단일 거래 최대 손실 (v2.0)

    # ── 앙상블 가중치 (v2.0) ──
    ENSEMBLE_WEIGHTS = {
        "tug_of_war": 0.30,     # LOGIC 1
        "v_pattern": 0.35,      # LOGIC 2
        "moc_imbalance": 0.15,  # LOGIC 3
        "news_temporal": 0.20,  # LOGIC 4
    }

    # ── 앙상블 진입 기준 (v2.0) ──
    ENSEMBLE_PRIORITY_THRESHOLD = 70   # 최우선 진입 (비중 확대)
    ENSEMBLE_STANDARD_THRESHOLD = 55   # 표준 진입
    ENSEMBLE_SMALL_THRESHOLD = 40      # 소규모 진입 (비중 축소)

    # ── 거시 환경 필터 임계값 (v2.0) ──
    MACRO_DANGER_KOSPI = -2.0          # DANGER: 코스피 하한
    MACRO_DANGER_US_FUTURES = -2.0     # DANGER: 미국선물 하한
    MACRO_DANGER_VIX = 30.0            # DANGER: VIX 상한
    MACRO_CAUTION_KOSPI = -1.0         # CAUTION: 코스피 하한
    MACRO_CAUTION_US_FUTURES = -1.0    # CAUTION: 미국선물 하한
    MACRO_CAUTION_VIX = 25.0           # CAUTION: VIX 상한

    # ── 뉴스 확산성 기준 (v2.0) ──
    NEWS_GOOGLE_MIN = 20               # 구글뉴스 최소 기사 수
    NEWS_GOOGLE_HIGH = 30              # 보편적 관심 확인 기준
    NEWS_POWER_KEYWORDS = [
        "세계 최초", "단독", "정부 정책",
        "국책과제", "수주", "흑자전환",
        "FDA 승인", "특허", "M&A",
    ]

    # ── 장후 데이터 수집 (v2.0) ──
    AFTER_HOURS_START = "15:30"
    AFTER_HOURS_END = "16:00"
    AFTER_SINGLE_START = "16:00"
    AFTER_SINGLE_END = "18:00"

    # ── AI 활성화 시간 (v2.0) ──
    COMMANDER_TIMES = ["08:50", "14:30", "15:00", "15:15", "15:19"]  # 5회
    EXPLORER_TIMES = ["09:00", "13:00", "14:00"]                     # 3회
    ANALYST_TIMES = ["10:00", "14:00", "15:00"]                      # 3회

    # ── 거시 필터 체크 타이밍 (v2.0) ──
    MACRO_CHECK_TIMES = ["08:30", "14:00", "15:15"]

    # ── 시스템 목표 (v2.0) ──
    TARGET_WIN_RATE = 0.55              # 목표 승률
    TARGET_WIN_LOSS_RATIO = 1.5         # 목표 손익비
    TARGET_SHARPE_RATIO = 1.5           # 목표 샤프 비율
    TARGET_DAILY_RETURN = 0.003         # 일평균 수익률 0.3%
    TARGET_TRADE_FREQ = (1, 3)          # 일 거래 빈도 (최소, 최대)

    # ── API URL ──
    KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
    KIS_BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"
    KIS_BASE_URL_VIRTUAL = "https://openapivts.koreainvestment.com:9443"

    @classmethod
    def validate(cls):
        """설정 검증"""
        if cls.TRADING_ENABLED:
            if not all([cls.KIS_APP_KEY, cls.KIS_APP_SECRET, cls.KIS_ACCOUNT_NO]):
                raise ValueError("실거래 모드에서는 API 키와 계좌번호가 필요합니다.")

        # 앙상블 가중치 합이 1.0인지 검증
        weight_sum = sum(cls.ENSEMBLE_WEIGHTS.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(f"앙상블 가중치 합이 1.0이 아닙니다: {weight_sum}")

        return True


# 설정 검증
try:
    Config.validate()
except ValueError as e:
    print(f"설정 오류: {e}")
