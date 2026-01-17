# 🚀 한국 주식 자동매매 프로그램

**종가 베팅 전략** 기반 자동매매 시스템입니다.

시장의 주도주를 포착하여 종가 베팅(15:00-15:20) 후, 익일 오전(09:00-10:00)에 매도하는 단기 매매 전략을 자동화합니다.

---

## 📋 목차

- [핵심 전략](#-핵심-전략)
- [프로젝트 구조](#-프로젝트-구조)
- [설치 방법](#-설치-방법)
- [설정](#-설정)
- [사용법](#-사용법)
- [백테스팅 및 성과 분석](#-백테스팅-및-성과-분석)
- [매매 원칙](#-매매-원칙)
- [주의사항](#-주의사항)

---

## 🎯 핵심 전략

### 1. 종목 선정 기준
- **거래대금**: 2,000억원 이상 (주도주는 1조원 이상)
- **등락률**: 상위 20개 종목 중 거래대금 TOP 5
- **신고가**: 20일 신고가 돌파
- **정배열**: 5일 > 20일 > 60일 이동평균선
- **수급**: 외국인/기관 동반 매수

### 2. 매매 타이밍
- **매수**: 15:00 ~ 15:20 (종가 베팅)
- **매도**: 익일 09:00 ~ 10:00 (오전 매도)

### 3. 수익률 목표
- **목표 수익률**: 4.5%
- **손절 라인**: -3%

### 4. 고급 기능 (Phase 1-4)

#### Phase 1: V자 반등 실시간 포착
- **15:00-15:20 분봉 분석**: 실시간 V자 패턴 감지
- **신호 강도 계산**: 0-100점 체계로 진입 신호 평가
- **매수 타이밍 최적화**: 15:16-15:20 V자 확인 후 진입

#### Phase 2: 익일 오전 매도 전략 고도화
- **3분의 법칙**: 장 시작 3분 내 시초가 미돌파 시 전량 매도
- **1분봉 20분 이평선**: EMA 이탈(-1.5%) 시 즉시 청산
- **분할 매도**: 33%/33%/34% 3단계 익절 시스템

#### Phase 3: AI 기반 의사결정 시스템
- **200일선 상승 추세 감지**: 장기 추세 필터링
- **켈리 공식 포지션 사이징**: 거래 실적 기반 최적 투자 비율
- **강화학습 커맨드 센터**: Q-learning 기반 매매 의사결정

#### Phase 4: 백테스팅 및 성과 분석
- **백테스팅 엔진**: 과거 데이터 기반 전략 검증
- **성과 분석 리포트**: 일/주/월별 상세 리포트
- **파라미터 최적화**: Grid/Random Search 자동 최적화

---

## 📁 프로젝트 구조

```
/
├── api/
│   ├── kis_api.py          # 한국투자증권 API 클라이언트
│   └── __init__.py
├── config/
│   ├── config.py           # 설정 관리
│   └── __init__.py
├── strategy/
│   ├── screener.py         # 종목 스크리닝 (거래대금, 등락률)
│   ├── technical.py        # 기술적 분석 (신고가, 이평선, 200일선)
│   ├── sector.py           # 섹터 분석
│   ├── intraday_analysis.py # 장중 V자 반등 패턴 감지
│   ├── morning_monitor.py  # 익일 오전 모니터링 (3분 법칙, EMA)
│   ├── trade_history.py    # 거래 실적 추적
│   ├── kelly_criterion.py  # 켈리 공식 포지션 사이징
│   └── __init__.py
├── command_center/
│   ├── market_state.py     # 시장 상태 분석
│   ├── rl_agent.py         # Q-learning 강화학습 에이전트
│   ├── command_center.py   # AI 통합 의사결정
│   └── __init__.py
├── backtest/              # Phase 4: 백테스팅 시스템
│   ├── backtester.py      # 백테스팅 엔진
│   ├── performance_analyzer.py # 성과 분석기
│   ├── optimizer.py       # 파라미터 최적화
│   └── __init__.py
├── trading/
│   ├── engine.py          # 통합 매매 엔진
│   └── __init__.py
├── scheduler/
│   ├── scheduler.py       # 자동 스케줄러
│   └── __init__.py
├── data/                  # 포트폴리오 데이터
├── logs/                  # 거래 로그
├── reports/               # 성과 분석 리포트
├── backtest_results/      # 백테스트 결과
├── optimization_results/  # 최적화 결과
├── main.py                # 메인 실행 파일
├── run_backtest.py        # 백테스트 실행 스크립트
├── requirements.txt       # 필요한 패키지
├── .env.example           # 환경 변수 예시
└── README.md
```

---

## 🔧 설치 방법

### 1. 저장소 클론

```bash
git clone <repository-url>
cd gpt
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 API 키를 입력하세요:

```env
# 한국투자증권 KIS API 정보
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=your_account_number_here
KIS_ACCOUNT_CODE=01

# 매매 설정
TRADING_ENABLED=false  # true로 변경하면 실거래
MAX_STOCKS=5
MAX_INVESTMENT_PER_STOCK=1000000
```

---

## ⚙️ 설정

### API 키 발급

1. [한국투자증권](https://www.koreainvestment.com/) 계좌 개설
2. [KIS Developers](https://apiportal.koreainvestment.com/) 접속
3. 앱 등록 후 **APP KEY**와 **APP SECRET** 발급
4. `.env` 파일에 입력

### 주요 설정값

| 설정 | 기본값 | 설명 |
|-----|-------|------|
| `TRADING_ENABLED` | `false` | 실거래 활성화 (true/false) |
| `MAX_STOCKS` | `5` | 최대 보유 종목 수 |
| `MAX_INVESTMENT_PER_STOCK` | `1,000,000` | 종목당 최대 투자금 |
| `MIN_TRADING_VALUE` | `200,000,000,000` | 최소 거래대금 (2000억) |
| `NEW_HIGH_DAYS` | `20` | 신고가 기준 일수 |
| `TARGET_PROFIT_RATE` | `0.045` | 목표 수익률 (4.5%) |
| `STOP_LOSS_RATE` | `-0.03` | 손절 라인 (-3%) |

---

## 🚀 사용법

### 1. 시장 스캔 (테스트)

```bash
python main.py --mode scan
```

현재 시장에서 주도주를 스캔하고 매수 후보를 출력합니다.

### 2. 종가 베팅 (15:00-15:20)

```bash
python main.py --mode buy
```

매수 후보 종목을 분석하고 종가 베팅을 실행합니다.

### 3. 오전 매도 (09:00-10:00)

```bash
python main.py --mode sell
```

보유 종목을 매도합니다.

### 4. 포트폴리오 확인

```bash
python main.py --mode portfolio
```

현재 보유 종목과 수익률을 확인합니다.

### 5. 자동 스케줄러 (권장)

```bash
python main.py --mode scheduler
```

자동으로 다음 일정에 따라 실행됩니다:

- **08:50**: 장 시작 전 체크
- **09:30**: 오전 매도 (1차)
- **09:50**: 오전 매도 (2차)
- **14:30**: 시장 스캔
- **15:10**: 종가 베팅
- **15:40**: 일일 마감 요약

---

## 🧪 백테스팅 및 성과 분석

### 1. 백테스트 실행

과거 데이터로 전략의 성과를 검증합니다:

```bash
python run_backtest.py --mode backtest \
  --start 20240101 \
  --end 20241231 \
  --initial-capital 10000000 \
  --min-trading-value 200000000000 \
  --max-stocks 3 \
  --v-threshold 70
```

**출력 예시:**
```
📊 백테스트 결과 요약
==========================================
📅 기간: 20240101 ~ 20241231
💰 초기 자본: 10,000,000원
💵 최종 자본: 12,450,000원
📈 총 수익률: +24.50%
📉 최대 낙폭 (MDD): 8.32%
📊 샤프 비율: 1.85

🎯 총 거래 횟수: 156회
✅ 수익 거래: 98회
❌ 손실 거래: 58회
🎲 승률: 62.82%

📊 평균 수익률: +1.87%
📈 평균 수익 (승): +3.24%
📉 평균 손실 (패): -1.52%
```

### 2. 파라미터 최적화

Grid Search로 최적의 파라미터를 찾습니다:

```bash
python run_backtest.py --mode optimize \
  --start 20240101 \
  --end 20241231 \
  --optimization-method grid \
  --metric total_return
```

Random Search 사용 (더 빠름):

```bash
python run_backtest.py --mode optimize \
  --start 20240101 \
  --end 20241231 \
  --optimization-method random \
  --n-iterations 50 \
  --metric sharpe_ratio
```

**최적화 메트릭:**
- `total_return`: 총 수익률 (기본값)
- `sharpe_ratio`: 샤프 비율 (위험 대비 수익)
- `win_rate`: 승률

### 3. 성과 분석 리포트

#### 일일 리포트
```bash
python run_backtest.py --mode report \
  --report-type daily \
  --date 2024-12-01
```

#### 주간 리포트
```bash
python run_backtest.py --mode report \
  --report-type weekly \
  --weeks-back 1  # 1=지난주, 2=2주 전
```

#### 월간 리포트
```bash
python run_backtest.py --mode report \
  --report-type monthly \
  --month 2024-12
```

#### 사용자 정의 기간 리포트
```bash
python run_backtest.py --mode report \
  --report-type custom \
  --start 2024-11-01 \
  --end 2024-12-31
```

**리포트 내용:**
- 총 거래 횟수 및 수익
- 승률 및 평균 수익률
- 최고/최저 수익 거래
- 종목별 통계
- 연속 승/패 분석

### 4. 백테스팅 결과 분석

백테스트 결과는 다음 위치에 저장됩니다:

- **백테스트 결과**: `backtest_results/backtest_YYYYMMDD_HHMMSS.json`
- **최적화 결과**: `optimization_results/grid_search_YYYYMMDD_HHMMSS.json`
- **성과 리포트**: `reports/monthly_YYYYMM.json`

JSON 파일을 열어 상세한 거래 내역과 통계를 확인할 수 있습니다.

---

## 📊 매매 원칙

### 종목 선정 프로세스

```
1. 등락률 상위 20개 종목 조회
   ↓
2. 거래대금 2,000억 이상 필터링
   ↓
3. 거래대금 순으로 TOP 5 선정
   ↓
4. 기술적 분석 (신고가, 정배열, 수급)
   ↓
5. 점수화하여 최종 후보 선정
```

### 점수 산정 기준

| 조건 | 점수 |
|-----|------|
| 20일 신고가 돌파 | 40점 |
| 이동평균선 정배열 | 30점 |
| 외국인+기관 동반 매수 | 30점 |
| 외국인 또는 기관 매수 | 15점 |

**총점 70점 이상** 종목을 우선 매수합니다.

---

## ⚠️ 주의사항

### 1. 실거래 전 충분한 테스트

```bash
# .env 파일에서
TRADING_ENABLED=false  # 모의거래 모드로 테스트
```

모의거래로 충분히 테스트한 후 실거래를 시작하세요.

### 2. 리스크 관리

- 종목당 투자금을 적절히 설정하세요
- 손절 라인을 반드시 설정하세요
- 여유 자금으로만 투자하세요

### 3. 모니터링

- 거래 로그를 정기적으로 확인하세요 (`logs/trades.log`)
- 포트폴리오 상태를 주기적으로 점검하세요

### 4. API 제한

- 한국투자증권 API는 초당 요청 횟수에 제한이 있습니다
- 과도한 요청 시 일시적으로 차단될 수 있습니다

### 5. 법적 책임

- 본 프로그램은 교육 및 연구 목적으로 제공됩니다
- 투자 손실에 대한 책임은 사용자에게 있습니다
- 프로그램 사용으로 인한 어떠한 손해도 개발자가 책임지지 않습니다

---

## 📈 작동 원리

### 종가 베팅 전략

```
100m 달리기에서 90m 지점까지 가장 힘차게 달리는 선수를 찾아,
확실한 우승 후보에게 마지막 순간에 투표하는 것과 같습니다.
```

시장이 **뜨겁게 달아오른 순간(15:00-15:20)**에 진입하여,
그 **열기가 식기 전(익일 09:00-10:00)**에 수익을 실현합니다.

---

## 🛠️ 문제 해결

### API 토큰 발급 실패

```
❌ 토큰 발급 실패: ...
```

→ `.env` 파일의 API 키를 확인하세요.

### 시세 조회 실패

```
⚠️  시세 조회 실패: ...
```

→ API 호출 제한에 걸렸을 수 있습니다. 잠시 후 다시 시도하세요.

### 주문 실패

```
❌ 주문 실패: ...
```

→ 계좌 잔고 또는 주문 가능 시간을 확인하세요.

---

## 📝 라이선스

MIT License

---

## 🤝 기여

이슈 및 풀 리퀘스트를 환영합니다!

---

## 📧 문의

질문이나 제안사항이 있으시면 이슈를 등록해주세요.

---

**⚡ Happy Trading! ⚡**
