# TODO — Rule-based regime: 리뷰 반영 현황 및 남은 작업

외부 리뷰(2026-07 rule-based regime review)를 코드에 대고 검증한 결과와 처리 상태.
Live는 아직 테스트 시기상조라 **보류(TODO)**, 나머지는 검토·반영했습니다.

---

## 🔴 보류 (Live 관련 — 실전 테스트 시점에 반드시 처리)

### [ ] #1 Live warmup / backfill 확대 (최우선, 미착수)

**문제 (검증됨):** `live.py`의 `WebSocketClient` 기본 버퍼가
`buffer_size = 500` (약 8시간 20분치 1분봉)이고, feature engine의
`max_candles = 12`. 그런데 rule 디텍터는 1h/4h/24h 및 24h-rolling F17 피처를
쓰므로 warmup이 크게 부족하다:

- `trend_slope_24h` → 최소 24h(1440봉) 히스토리
- `bb_width_4h` / `adx_4h` → 최대 20개 4h bar ≈ 80h
- `trend_slope_4h` → 4h bar 여러 개

warmup이 부족하면 live의 F17이 학습/백테스트와 **다르게(0 또는 불완전)** 계산되어
regime이 어긋난다 → train/serve skew. (`backfill_missing`는 gap 보정용이지
시작 시 warmup 채우기가 아님.)

**수정 방향:**
1. live 시작 시 REST로 과거 1분봉 backfill (최소 ~6,000, 권장 10,080 = 7일).
2. 그 위에서 feature_rows 생성 → 이후 websocket 캔들 append.
3. rule 디텍터 `detect_one` 호출 전에 warmup 확보 보장(부족하면 진입 보류/경고).
4. `max_candles`도 24h+ 커버하도록 상향(또는 rule 라우팅용 별도 롤링 버퍼).

**주의:** 이 수정 없이는 rule 디텍터가 backtest에서 좋아 보여도 live에서 다른
regime을 낼 수 있음. 실전 배포 전 필수.

---

## 🟢 반영 완료 (이번 커밋)

### [x] #2 학습 test-period 평가에 rule 라우팅 적용
`training.py`의 test-period 진단 평가가 `regime_source == "multi_feature_rule"`일 때
`row.user_regime`(rule 모드엔 없음 → 대개 None)으로 빠져 regime별 평가가 비던 문제.
→ 이제 저장된 **동일 rule 디텍터로 전체 eval 구간을 라우팅**(정확한 hysteresis/
min-hold 상태)한 뒤 test 구간을 시간으로 slice. 라우팅 계산을 per-regime 루프
**밖으로 hoist**(detect_all 1회). 실제 backtest 라우팅과 진단이 일관됨.

### [x] #3 up↔down 직접 전환 완화 (config 토글)
`_stay_decision`에서 up이 장기 trend만으로 바로 down(및 반대)으로 뒤집히던 경로에
`allow_direct_reversal` 토글 추가. **기본 True(기존 동작 유지)**, False로 두면
up→range→down / down→range→up으로 range를 경유(강한 breakout은 예외로 즉시 전환).
1분봉 스캘핑에서 hard flip을 줄이고 싶으면 False 권장. as_dict/from_dict 저장됨.

### [x] #4 fast rule 테스트 강화
기존 테스트가 "유효 클래스 여부" 정도만 보던 것을 보강:
- `test_fast_trend_early_exits_up_to_range`: 장기 up 유지 + 단기 급락 시
  fast rule ON은 range로 조기 이탈, OFF는 up 유지를 **고정 검증**.
- `test_no_direct_reversal_forces_through_range`: 토글 ON은 직접 up→down,
  OFF는 up→range→down 경유를 검증.
- 진입 차단 테스트도 유지. (총 12개 통과)

### [x] #5 파이프라인 로그 정리
`run_full_pipeline.sh` / `.ps1`의 Phase 4에서 **무조건** "regime-classifier
routing"을 먼저 찍고 그 뒤 조건부 메시지를 찍던 중복/오출력 제거. `.ps1` Phase 3의
"Regimes are detected in real time (RegimeDetector...)" 고정 문구를 mode-aware로
분기(rule → MultiFeatureRegimeDetector, classifier → learned classifier).

---

## 🟡 데이터 기반 후속 튜닝 (학습 후)

### [ ] rule 임계값 튜닝
첫 학습/백테스트 로그에서 regime 분포(up/down/range 행 수)와 전환 빈도 확인 후:
- 전환이 잦으면: `fast_conflict_max ↑`, `fast_exit ↑`, `min_hold_bars ↑`,
  필요시 `allow_direct_reversal=False`.
- range가 과다하면: `fast_conflict_max ↓`, `trend_enter ↓`.
- 초기 범위: fast_conflict_max 0.45~0.70, fast_exit 0.70~0.90, min_hold 60~180.

### [ ] (선택) 24h 방향 신호 보강
현재 `trend_slope_24h` 1개. 필요시 `return_24h`(이미 F17에 존재)도 trend_weights에
소량 추가 가능.

---

# 2차 리뷰 (non-live fix plan) 처리 현황

## 🟢 반영 완료

- **[x] #2 `switch_confirm_bars`** — 새 후보 regime이 N바 연속돼야 전환하는
  디바운스 추가. 기본 1(기존 동작 보존), 5~15 권장. 강한 breakout은 우회.
  min_hold_bars(현재 regime 유지)와 별개 게이트로 결합.
- **[x] #3 Rule config JSON 외부화** — `train --rule-regime-config <json>`.
  MultiFeatureRegimeConfig 전 필드(가중치 포함) override. fitted 디텍터에 embed →
  아티팩트 저장 → backtest/live 자동 상속. 예시: `configs/rule_regime.json`.
- **[x] #4 regime 전환 통계 출력** — `diagnostics()`를 확장(전환 by-type,
  direct_reversal_count, 평균 지속 bar, ratio). 학습 로그 + 백테스트 로그에 출력.
- **[x] #6 테스트 보강** — switch_confirm(단발 blip 무시 / 지속 시 전환 /
  breakout 우회) 3개 추가. 총 15개 통과.

## 🟡 판단 — 기본값/보류

- **#1 `allow_direct_reversal` 기본값** — 코드 기본값은 **True(기존 동작)로 유지**.
  대신 권장 보수 프리셋을 `configs/rule_regime.json`(allow_direct_reversal=false,
  switch_confirm_bars=10)으로 제공. 이유: 라우팅 기본값을 조용히 바꾸면 이전
  백테스트와 재현성이 깨짐. 첫 백테스트의 전환 통계를 보고 config로 켜는 것을 권장.
- **[ ] #5 전환 구간 성능 분석 (보류)** — 트레이드를 안정/전환직후/전환직전
  구간으로 나눠 win_rate·PF·PnL·MDD를 따로 보는 분석. 백테스트 트레이드 루프에
  regime-change 경과 bar 추적이 필요한 **별도 분석 기능**이라 범위가 큼. 먼저 #4의
  전환 통계로 "전환이 과한지"를 판단하고, 필요하면 전용 작업으로 진행. (전환 직후
  no-trade/threshold 상향 같은 대응은 이 분석 결과가 나온 뒤에 얹는 게 순서.)

---

# 3차 리뷰 (파이프라인·백테스트 연결부) 처리 현황

## 🟢 반영 완료

- **[x] 3.1 파이프라인이 rule config 미적용** — `run_full_pipeline.sh/.ps1`이
  이제 **기본으로** `configs/rule_regime.json`을 `--rule-regime-config`로 넘김
  (파일 존재 시). 즉 그냥 실행해도 보수 프리셋(switch_confirm_bars=10,
  allow_direct_reversal=false 등)이 적용됨. `RuleRegimeConfig=""`로 끄면 코드 기본값.
- **[x] 3.2 backtest가 selected_thresholds 미사용 (핵심)** — `backtest.py`의 4개
  threshold 결정 지점(regime/default_regime × bundle/legacy)이 이제 live와 동일
  우선순위(**명시적 override > 학습된 per-regime > strategy 기본**)로
  `regime_bundle.regime_thresholds`를 사용. 헬퍼 `_resolve_backtest_thresholds`로
  통일. (비-regime 단일모델 경로는 bundle이 없어 기존대로 strategy 기본 유지.)
- **[x] 3.3 backtest CLI threshold override 없음** — `backtest`에
  `--long-threshold`/`--short-threshold` 추가, `run_backtest`에 전달.
- **[x] 3.5 routing diagnostics 미저장** — `BacktestResult.regime_routing_diagnostics`
  필드 추가, rule 라우팅 시 저장, `as_dict()`에 포함 → `backtest_summary.json`에서
  regime 분포/전환/direct_reversal/평균지속을 확인 가능.
- **[x] 4.2 `__post_init__` 검증 보강** — switch_confirm_bars>=1,
  fast_conflict_max>=0, fast_exit>=0 검증 추가 (+ 테스트).

## 🟡 판단

- **3.4 `allow_direct_reversal` 코드 기본값** — **코드 기본값은 True 유지**
  (라이브러리/테스트 호환). 대신 3.1로 **파이프라인은 config를 통해 False가 기본
  적용**되므로, 실사용(파이프라인) 경로에서는 보수 설정이 기본이 됨. 코드 기본값을
  직접 False로 바꾸는 것은 라이브러리 소비자/기존 테스트에 영향을 줘 보류.
- **4.1 약한 테스트** — `test_fast_trend_blocks_conflicting_entry`의 OFF 단언은
  약하지만, 이미 강한 테스트(early-exit up→range 고정, reversal range 경유,
  switch_confirm 3종)를 추가해 커버리지는 충분. 별도 강화는 후순위.


---

# 4차 (실측 분석 후속) — #3 barrier/horizon 정렬

## 🟢 반영 완료

- **[x] 라벨↔실행 barrier 불일치 수정 (핵심).** 모델은 라벨 tp/sl(0.30%/0.15%,
  horizon 60분)로 학습되는데 백테스트는 ATR barrier(~0.84%/0.42%)로 실행되던
  train/execution 불일치를 수정. `backtest --exec-tp-pct/--exec-sl-pct`로 실행
  barrier를 라벨과 동일한 고정값으로 강제(ATR 무시). run_backtest/compare_strategies
  양쪽 적용.
- **[x] 파이프라인 튜닝 노브.** `HORIZON`/`LABEL_TP_PCT`/`LABEL_SL_PCT` 변수 추가.
  train(--horizon/--tp-pct/--sl-pct)과 backtest(--exec-tp-pct/--exec-sl-pct)에
  동일 값을 넘겨 **라벨과 실행이 항상 일치**. 기본 60분 / 0.30% / 0.15%.

## 🟡 유지 / 다음

- range 거래는 유지(사용자 결정). regime 라우팅 자체는 정상.
- #4 모델 엣지: regime 정보를 모델 **피처**로 넣는 것(연속 regime score 또는
  F18 재도입)은 엣지 개선 후보지만 modest. 라벨 품질/피처/목표 재설계가 본질.

---

# 5차 리뷰 (partial fix review) 처리 현황 — 6개 전부 검증 후 반영

## 🟢 반영 완료 (리뷰 우선순위 순)

- **[x] 1순위: `_trading_pnl` 수정 (근본 원인).** threshold 미만을 반대
  포지션(-1)으로 계산하던 것을 **no-trade(PnL 0)**로 수정. 승리 +tp(0.30%)−비용,
  패배 −sl(0.15%)−비용의 **비대칭 barrier + round-trip cost(0.08%)** 반영.
  검증: 약한 모델에서 선택 threshold가 0.32대 → **0.58**로 상승.
- **[x] 2순위: routing diagnostics 백테스트 기간 slice.** detect_all은 전체
  히스토리로(hysteresis state 유지), diagnostics만 start_date 이후로 slice.
  검증: 600bar 중 window 360bar만 집계됨 확인. (이전 결과의 counts 합
  3,156,480 → 이제 525,600이 나올 것.)
- **[x] 3순위: trade record 확장.** `entry_regime` / `long_probability` /
  `short_probability` / `used_threshold`를 5개 시그널 분기 전부에서 기록,
  backtest_summary.json trades에 직렬화. regime/side/확신도별 손실 귀속 분석 가능.
- **[x] 4순위: threshold floor.** `--threshold-floor`(기본 0=off) 추가.
  learned/strategy 값에만 적용, 명시적 `--long/--short-threshold` override는
  클램프하지 않음. 파이프라인 기본 `THRESHOLD_FLOOR=0.45`.
- **[x] 5순위: feature 2회 계산 제거.** CLI backtest가 feature_rows를 한 번
  빌드해 compare_strategies와 run_backtest에 공유. 모든 라우팅 경로가
  dataclasses.replace(비파괴)임을 확인 후 적용 — 원본 불변이라 공유 안전.
- **[x] 6순위: 기본 objective를 `trading_pnl`로 변경** (sh/ps1). 리뷰 지시대로
  `_trading_pnl` 수정 **후에** 변경.

## 🟡 남김

- warmup drop 로그(리뷰 5절 권장: raw/after-warmup/dropped/first-trainable
  카운트 출력) — 진단 편의 항목, 다음 정리 때.
- trade record의 rule 점수(trend_score/trend_fast 등) 확장 — detector 점수
  노출 API 필요, 최소 필드는 반영 완료.

---

# 6차 리뷰 (v3 inspection) 처리 현황

## 🟢 반영 완료 (리뷰 우선순위 순)

- **[x] 1순위: `--backtest-end` 추가.** 파이프라인의 `$BacktestEnd`가 로그에만
  쓰이고 backtest에 미전달이던 것 확인. run_backtest/compare_strategies에
  `end_date`(inclusive) 추가, 거래 루프에 end 게이트, CLI `--backtest-end`,
  sh/ps1 전달. 이제 parquet이 2026까지 늘어나도 traded span이 조용히 안 넓어짐.
- **[x] 2순위: diagnostics를 start~end로 slice.** end_date까지 반영.
  검증: 720bar 중 [start,end] 300bar만 집계.
- **[x] 3순위: threshold objective가 학습 tp/sl을 따라감.** `_trading_pnl` →
  `metrics` → `select_threshold` 체인에 tp_pct/sl_pct/round_trip_cost 관통,
  두 호출부가 `training_config.tp_pct/sl_pct` 전달. TP/SL sweep 시 objective가
  라벨 geometry와 자동 동기화. 검증: big-TP에서 선택 threshold ≤ small-TP.
- **[x] 4순위: rule detect_all 중복 제거.** `apply_multi_feature_routing()`
  헬퍼 추가 — CLI가 라우팅을 **1회** 수행해 routed rows + windowed diag를
  compare/run 양쪽에 공유, run_backtest는 `precomputed_routing_diagnostics`로
  저장만. (~3.15M행 detect_all 2회 → 1회.)
- **[x] 5순위: trade record에 `model_side` / `entry_probability`.** 진입 side와
  그 side의 확률을 직접 기록·직렬화.
- **[x] 6순위: summary에 threshold 구분 저장.** `threshold_floor` +
  regime별 `effective_thresholds` {learned_long/short, effective_long/short}.
  artifact selected_threshold(예: 0.38)와 실제 진입 threshold(0.45)의 혼동 제거.

## 🟡 확인/스킵

- **5.1 `best_strategy` 중복 키** — 현재 코드에 1곳만 존재, 해당 없음.
- **5.2 comparison에 diag 포함** — 필수 아님(리뷰도 동의). routed rows 공유
  구조라 전략 간 라우팅이 동일함이 구조적으로 보장됨.

---

# 7차 리뷰 (v4 inspection) 처리 현황 — 5개 전부 검증 후 반영

## 🟢 반영 완료

- **[x] 1순위: backtest_end 날짜 해석.** date-only "2025-12-31"이 00:00
  inclusive로 해석돼 마지막 날 1,439/1,440바가 빠지던 문제. 공용
  `_parse_end_exclusive()` 도입 — date-only는 **다음날 00:00 exclusive**
  (하루 전체 포함), 시각 포함 값은 그대로 exclusive. 거래 루프/diag slice
  2곳/routing 헬퍼 모두 `< end` exclusive로 통일. 검증: end=2025-12-31에서
  정확히 1,440바 거래.
- **[x] 2순위: end 이후 open trade 처리.** end 도달 시 `continue`→**`break`**
  (캔들 시간순 전제), `last_in_window_candle` 추적, 잔여 open trade는 파일
  마지막 캔들(`candles[-1]`)이 아닌 **마지막 in-window 캔들**에서 OPEN_AT_END
  마감. 검증: 파일이 2026-01-01 11:59까지 있어도 마지막 exit=12-31 23:59.
- **[x] 3순위: holdout metrics geometry 일치.** `m = metrics(...)` 호출이
  training_config의 tp/sl/cost를 받도록 수정 — threshold는 sweep geometry로
  뽑는데 summary의 mdd/sharpe/calmar는 기본값으로 계산되던 불일치 제거.
- **[x] 4순위: `TrainingConfig.round_trip_cost` 추가** (기본 0.0008 = 백테스트
  비용 모델과 동일). 두 select_threshold 호출 + holdout metrics에 전달.
  검증: cost 0.02%→0.20%로 올리면 선택 threshold 0.588→0.640으로 상승.
- **[x] 5순위: legacy hard gate 제거.** 3곳의 `and prob >= 0.55` /
  `and prob <= 0.45` 이중 게이트 제거 — resolved lt/st(override>learned>floor)
  가 유일한 게이트. 테스트 의존 없음 확인 후 적용.

검증: 경계 미니백테스트(1,440바/2026 미침범/OPEN_AT_END in-window),
cost→threshold 방향성, test_core 회귀 0, rule 테스트 15개 OK.
