# 전체 시스템 디버깅 Plan v2.0

## 현재 상태 요약

| 구분 | 파일 수 | 상태 |
|------|---------|------|
| Part 1 (앙상블 프레임워크) | 13개 | 구현 완료 |
| Part 2 (5단계 전략 로직) | 9개 변경/신규 | 구현 완료 |
| Part 3 (리스크 관리·알림) | 9개 변경/신규 | 구현 완료 |
| **전체** | **약 30개 .py** | **통합 검증 필요** |

---

## 1단계: API 인터페이스 보완 (Critical)

### 1.1 KISApi 누락 메서드 추가
**파일**: `api/kis_api.py`

현재 KISApi에 존재하는 메서드:
- `get_stock_price(stock_code)` — `current_price`, `change_rate`, `trading_volume` 등
- `get_top_gainers(count)` — 상위 상승 종목
- `get_minute_price_history(stock_code, interval, count)` — 분봉
- `get_daily_price_history(stock_code, days)` — 일봉
- `get_investor_trading(stock_code)` — 투자자별 매매
- `get_balance()` — 잔고 (holdings + cash)
- `place_order(stock_code, quantity, price, order_type)` — 주문

**누락된 메서드 (구현 필요)**:

| 메서드 | 호출처 | 필요 반환 필드 |
|--------|--------|---------------|
| `get_realtime_analysis_data(stock_code)` | `IntradayAnalyzer.get_realtime_data()`, `engine.run_after_hours_check()` | `current_price`, `open_price`, `execution_strength`, `program_net_buy_3min`, `sell_order_qty`, `buy_order_qty`, `moc_buy_imbalance`, `after_hours_change` |
| `get_market_overview()` | `engine.run_morning_strategy()` | `kospi_change`, `kosdaq_change`, `us_close_change`, `vix`, `expected_gap_pct` |

### 1.2 get_stock_price 반환값 확장
**현재 반환**: `stock_code`, `stock_name`, `current_price`, `change_rate`, `trading_volume`, `trading_value`, `high_price`, `low_price`

**추가 필요**:
- `open_price` — 시가 (morning_monitor, engine에서 사용)
- `ma20` — 20일 이동평균선 (StopLossEngine, exit scenario)
- `high_since_open` — 장중 고가 (exit scenario B-2)
- `kospi_change` — 코스피 등락률 (StopLossEngine emergency)

### 1.3 get_balance 반환값 확장
**현재 반환**: `{"holdings": [...], "cash": int}`

**추가 필요**:
- `total_asset` — 총자산 (= cash + sum(holdings.current_price * quantity))
  → 또는 engine에서 직접 계산하는 로직 추가

---

## 2단계: Strategy 모듈 메서드 시그니처 검증

### 2.1 StockScreener.get_candidates()
**파일**: `strategy/screener.py:162`
- 현재: `get_top_gainers()` → `StockData` 변환 → `phase1_filter` → `run_phase1`
- 검증: `get_top_gainers` 반환 딕셔너리에서 `market_cap`, `change_rank` 등 추출 가능한지 확인
- **이슈**: `get_top_gainers()` 반환에 `market_cap` 없음 → `get_stock_price()`로 보완하거나 API 확장 필요

### 2.2 TechnicalAnalyzer.analyze_candidates()
**파일**: `strategy/technical.py:247`
- 검증: 반환값에 `phase2_score` 키가 포함되는지 확인
- 검증: `get_daily_price_history()` 20일 데이터로 MA 계산 정확성

### 2.3 IntradayAnalyzer.build_realtime_data()
**파일**: `strategy/intraday_analysis.py`
- `get_realtime_analysis_data()`의 raw dict → `RealtimeData` dataclass 변환 검증
- 특히 `minute_prices` (1분봉) → 5MA, 20MA 계산 경로

### 2.4 VetoScanner.scan_news_list()
**파일**: `strategy/veto.py:101`
- 반환값 `VetoResult`에 `triggered_keyword`, `risk_type` 속성 존재 확인
- engine.py에서 `hasattr` 가드를 사용 중이나 실제 존재하는지 확인

---

## 3단계: TradingEngine 통합 흐름 검증

### 3.1 run_closing_strategy() 흐름
```
market_condition dict → macro_filter.update() → regime
                      → check_us_market_correlation() → us_check
                      → guard.can_enter() → 허용/차단
screener.get_candidates() → candidates (List[Dict])
technical_analyzer.analyze_candidates(candidates) → tech_passed (List[Dict])
  → 각 stock에 대해:
    veto_scanner.scan_news_list() → VetoResult
    phase3_score(SentimentData) → (passed, score, details)
  → 상위 5개 선별
  → 각 final_candidate에 대해:
    guard.can_enter() 재체크
    intraday_analyzer.get_realtime_data() → raw dict  ← ★ API 필요
    intraday_analyzer.phase4_v_pattern() → (is_v, v_score, v_details)
    calculate_logic_scores() → logic_scores dict
    ensemble_scorer.score_with_logic_dict() → EnsembleResult
    determine_entry_weight() → float
    api.place_order() → bool
    guard.record_entry()
    discord.send_buy_signal()
```

**검증 포인트**:
- [ ] candidates dict 키 구조 일관성 (`stock_code` vs `symbol`)
- [ ] tech_passed에 `phase2_score` 키 포함 확인
- [ ] `news_items` 키가 candidates/tech_passed에 포함되는 경로
- [ ] `google_news_count`, `positive_ratio`, `forum_post_count` 등 데이터 소스

### 3.2 run_morning_strategy() 흐름
```
api.get_balance() → total_asset
StopLossEngine(total_asset)
api.get_market_overview() → market_data  ← ★ API 필요
assess_overnight_risk() → overnight
  → 각 holding에 대해:
    api.get_stock_price() → price_info  ← ★ 필드 부족
    stop_loss_engine.evaluate() → stop_result
    (or) determine_exit_scenario() → (scenario, reason, sell_ratio)
    execute_exit() → exit_result
    api.place_order() → bool
    guard.record_trade_result()
    discord.send_exit_alert()
```

**검증 포인트**:
- [ ] `get_stock_price()` 반환에 `open_price`, `ma20`, `high_since_open` 추가 필요
- [ ] `get_market_overview()` 구현 필요
- [ ] `kospi_change` 데이터 소스 확보

### 3.3 run_after_hours_check() 흐름
```
  → 각 holding에 대해:
    api.get_realtime_analysis_data() → after_data  ← ★ API 필요
    after_hours_risk_check() → result
    discord.send_after_hours_alert()
```

---

## 4단계: Scheduler v2.0 업데이트

**파일**: `scheduler/scheduler.py`

### 현재 (v1.1) 스케줄
| 시간 | 작업 |
|------|------|
| 08:50 | morning_check (portfolio) |
| 09:30, 09:50 | morning_sell |
| 14:30 | market_scan |
| 15:18 | closing_bet |
| 15:40 | daily_summary (portfolio) |

### 필요 (v2.0) 스케줄
| 시간 | 작업 | 신규 |
|------|------|------|
| 00:00 | `engine.reset_daily()` | ★ NEW |
| 08:30 | `engine.run_morning_strategy()` (야간 악재 + 동시호가) | ★ 시간 변경 |
| 09:00 | `engine.run_morning_strategy()` (시나리오 판단) | ★ NEW |
| 09:03 | `engine.run_morning_strategy()` (3분 체크) | ★ NEW |
| 09:30 | `engine.run_morning_strategy()` (분할매도) | 유지 |
| 09:50 | `engine.run_morning_strategy()` (2차) | 유지 |
| 14:00 | `engine.scan_market()` (PHASE 1) | 시간 변경 |
| 15:18 | `engine.execute_closing_bet()` | 유지 |
| 15:40 | `engine.run_after_hours_check()` | ★ NEW |
| 16:30 | `engine.run_after_hours_check()` (시간외 단일가) | ★ NEW |
| 17:00 | `engine.run_daily_report()` | ★ NEW |

---

## 5단계: main.py 모드 확장

**추가 모드**:
- `--mode after-hours` → `engine.run_after_hours_check()`
- `--mode report` → `engine.run_daily_report()`
- `--mode guard-status` → `engine.guard.get_status()` + `engine.check_portfolio()`

---

## 6단계: CommandCenter 동기화

**파일**: `command_center/command_center.py`

- `print_dashboard()` 메서드 존재 확인 및 구현
- Part 3 모듈 연동 (guard 상태, 레짐, 손절 이력 표시)

---

## 7단계: 데이터 흐름 E2E 테스트

### 7.1 Mock 데이터 기반 단위 테스트
| 테스트 | 대상 | 설명 |
|--------|------|------|
| test_phase1 | screener.py | StockData → phase1_filter → CandidateTier |
| test_phase2 | technical.py | TechnicalData → phase2_score → (bool, int, dict) |
| test_phase3 | sentiment.py | SentimentData → phase3_score → VETO/PASS |
| test_phase4 | intraday_analysis.py | RealtimeData → detect_v_pattern → (bool, int, dict) |
| test_phase5 | morning_monitor.py | determine_exit_scenario → (scenario, reason, ratio) |
| test_ensemble | ensemble.py | logic_scores → score_with_logic_dict → EnsembleResult |
| test_stop_loss | stop_loss.py | evaluate → 우선순위별 trigger |
| test_guard | brain_trade_guard.py | can_enter → 시간/횟수/연패/손실 체크 |
| test_us_market | us_market.py | check_us_market_correlation → risk_level |
| test_discord | discord_alert.py | send_* → 웹훅 전송 (모의) |
| test_report | daily_report.py | generate → 리포트 문자열 |

### 7.2 통합 테스트 (Mock API)
| 테스트 | 시나리오 |
|--------|---------|
| test_full_pipeline | PHASE 1→2→3→4 전체 파이프라인 (정상 케이스) |
| test_danger_regime | DANGER 레짐에서 진입 차단 확인 |
| test_guard_block | 3연패 후 매매 차단 확인 |
| test_stop_loss_priority | 비상 > 가격 > 20일선 > 3분 > 10시 순서 |
| test_morning_exit_scenarios | A/B/C/D 시나리오별 매도 비율 |
| test_after_hours | 장후 잔량 비율별 정리 로직 |

---

## 실행 순서 (권장)

```
1단계 → API 보완 (get_realtime_analysis_data, get_market_overview, 반환값 확장)
2단계 → Strategy 메서드 시그니처 검증 및 수정
3단계 → Engine 통합 흐름 dry-run (데이터 키 일관성)
4단계 → Scheduler 업데이트 (v2.0 타임라인)
5단계 → main.py 모드 확장
6단계 → CommandCenter dashboard 구현
7단계 → Mock 기반 E2E 테스트
```

**예상 소요**: 1단계가 가장 critical — API가 완성되어야 나머지 단계 진행 가능
