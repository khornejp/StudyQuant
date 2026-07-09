# V5 분석 잔여 이슈 수정 보고 (2026-07-08)

기준 문서: `rulebased_regime_v5_analysis_summary.md`
이전 세션: `SESSION_SUMMARY_2026-07-03.md`

v5 분석의 우선순위 1~6을 전부 반영했다. 각 항목을 소스에서 재검증한 뒤 수정했으며,
전 항목이 실제 코드에 존재하는 문제였음을 확인했다.

---

## 1순위: 병렬 feature 계산에서 weekly feature 소멸 — 수정 완료 (핵심)

### 확인된 실체
- `dataset.build_feature_rows`는 5만 캔들 초과 시 자동으로 병렬 chunk 모드
  (`MAX_CHUNK=250,000` + `overlap=6,000`)로 진입.
- 각 chunk 내부에서 `weekly_features.compute_weekly_features(chunk_candles)`를
  재계산 → chunk는 최대 ~25.6만 봉(≈25주) → `len(weekly) < 50` 가드에 걸려
  **weekly 7종 feature가 병렬 실행 시 항상 전부 0**이었음.

### 수정 (dataset.py)
1. `_build_feature_rows_parallel`이 **전체 candles 기준으로 weekly feature를
   부모 프로세스에서 1회 선계산** (float32 ndarray로 변환해 pickle 비용 최소화,
   chunk당 ~7MB).
2. 각 work item에 `[start:end)` 정렬 슬라이스를 동봉.
3. `_process_feature_chunk` → `_build_feature_rows_chunk` →
   `build_feature_rows(_precomputed_weekly=...)`로 관통. 주입 시 chunk 내부
   재계산을 건너뜀. 직렬 경로는 기존과 동일(전체 기준 계산).
4. overlap 주석에서 "weekly는 series-start 한정 커버"라는 낡은 설명 교체.

### 검증 (`verify_weekly_parallel_fix.py`)
- 부모 프로세스에서 `compute_weekly_features`를 "global index 반환" 함수로
  패치 → 워커는 이 함수를 절대 호출하지 않으므로(슬라이스만 수신), 산출 row의
  weekly 값이 global index와 일치하면 주입 경로가 증명됨.
- 60,000캔들 / 6 chunks (cpu_count 패치로 chunk_size=10,000 강제)에서
  **506개 샘플 전부 global-index 정렬 확인 (chunk 1~5의 심부 index 포함)**.
- 기존 코드였다면: (a) 실데이터에서 chunk 내 재계산 → 전부 0,
  (b) 패치 하에서도 chunk-local index → chunk>0에서 불일치.

### 부수 효과
- `build_dataset`의 50주 warmup row 필터(504,000 bars)는 그대로 유효 —
  이제 병렬 실행에서도 warmup 이후 row들이 **실제 weekly 값**을 갖게 됨.
- entry 모델 학습에 들어가는 20/50주 시장 구조 정보가 설계 의도대로 복원
  (rule detector 라우팅은 F17만 사용하므로 영향 없음 — 아래 "다음 실행 시
  주의" 3항 참조). **기존 병렬 실행으로 만든 feature 캐시가 있다면 반드시
  폐기 후 재계산해야 함.**

---

## 2순위: tp_sl_sweep.ps1 / .sh — rule-based 파이프라인 정렬 완료

기존: `--regime-aware`만으로 학습(=slope 단일 detector 버킷팅),
백테스트는 `--auto-regime` + `--tp/sl-floor --fixed-tp-sl`, end 미지정.
→ 메인 파이프라인과 라우팅/objective/기간이 전부 어긋나 비교 불가.

수정 후 각 sweep cell은 메인 파이프라인과 TP/SL만 다르고 구조는 동일:
- 학습: `--multi-feature-regime` (+ `configs/rule_regime.json` 존재 시
  `--rule-regime-config`), `--threshold-objective trading_pnl`,
  `--round-trip-cost`, `--horizon`.
- 백테스트: `--auto-regime` 제거(아티팩트 내장 rule detector 자동 로드 —
  auto-regime은 legacy slope detector라서 학습 버킷과 skew),
  `--exec-tp-pct/--exec-sl-pct`(라벨 barrier 그대로 실행), `--horizon`,
  `--threshold-floor 0.45`, `--backtest-start/--backtest-end` 고정 윈도우,
  `--fee/slippage-rate-per-side`.
- 낡은 헤더 주석 교체.

---

## 3순위: backtest CLI `--horizon` — 추가 완료

- `backtest_parser`에 `--horizon` (기본 60, train 기본과 동일) 신설.
- `compare_strategies`에 `label_horizon` 파라미터 신설 → 내부 `run_backtest`
  호출로 전달. CLI에서 `compare_strategies`/`run_backtest` 양쪽에
  `label_horizon=args.horizon` 배선.
- 감사 가능성: `backtest_summary.json`에 `label_horizon` 기록.
- `run_full_pipeline.ps1/.sh`의 Phase 4 backtest 호출에 `--horizon` 전달 →
  이후 `$Horizon`/`HORIZON`을 120 등으로 바꿔도 라벨과 실행 TIMEOUT이
  자동으로 함께 움직임.
- 스모크: `--horizon 45` → summary에 45 기록 확인.

## 4순위: 비용 기준 CLI 통일 — 완료

- train: `--round-trip-cost` (기본 0.0008) 신설 → `run_train` →
  `TrainingConfig.round_trip_cost` → `select_threshold`/`metrics`/
  `_trading_pnl` 체인은 기존 배선 그대로 사용.
- backtest: `--fee-rate-per-side` / `--slippage-rate-per-side` override 신설
  → `compare_strategies`/`run_backtest` 양쪽에 전달. override 시 로그 출력.
- 파이프라인/스윕 스크립트: `FeePerSide`/`SlippagePerSide` 단일 소스 노브 →
  `round_trip = 2*(fee+slip)` 파생값을 train에, per-side 값을 backtest에 전달.
  비용 가정을 한 곳에서 바꾸면 threshold 선택과 실행이 함께 움직임.
- 스모크: fee 0.0003/slip 0.0002 override → round_trip 0.001 로그 및
  summary 반영 확인.

## 5순위: `threshold_objective` 기본값 → `trading_pnl` — 완료

- `TrainingConfig.threshold_objective` 기본값, `run_train` 파라미터 기본값,
  CLI `--threshold-objective` default 3곳 모두 `trading_pnl`로 변경
  (+ help 텍스트 갱신). `precision_recall`은 legacy choice로 유지.
- 수동 train 실행 시에도 저확신 threshold(~0.32) 회귀 위험 제거.

## 6순위: 문서/주석 정리 — 완료

- `run_full_pipeline.sh` 헤더의 "validation 2025 H1 / backtest 2025 H2"
  낡은 설명 → 실제 동작(rule 모드 기본, in-training holdout, 2025 전체
  백테스트)으로 교체.
- `run_full_pipeline.ps1` 헤더의 "regimes.json 필수" 기술 → rule 모드에서는
  불필요(classifier 모드 한정)로 수정.
- sweep 스크립트 헤더도 현재 구조 반영.

---

## 테스트 결과 (수정 후 = 원본 zip과 동일; 회귀 0)

| 스위트 | 결과 | 비고 |
|---|---|---|
| tests.test_regime_rules | 15/15 OK | |
| tests.test_core | 131 tests, errors=7 | 전부 pyarrow/catboost 미설치(환경) — 원본 zip 동일 |
| tests.test_v718 | 159 tests, failures=2 errors=14 | 원본 zip과 실패 개수 동일 (기존 stale 기대값 + 환경) |
| tests.test_stacking_ensemble | errors=1 | catboost 미설치 — 원본 동일 |
| verify_weekly_parallel_fix.py | OK | 신규 — 병렬 weekly 주입 정렬 증명 |
| CLI 스모크 (backtest --horizon/--fee...) | OK | |
| py_compile (dataset/backtest/training/cli) | OK | |
| bash -n (모든 .sh) | OK | |

7순위(전체 테스트 기대값 갱신)는 catboost/pyarrow가 있는 로컬 환경에서
수행 필요 — v5 분석대로 F01~F13 시절 기대값이 남은 stale 실패가 다수.

---

## 다음 실행 시 주의

1. **feature 캐시가 있다면 삭제 후 재계산** — 병렬로 생성된 캐시의 weekly
   feature는 전부 0이므로 이번 수정의 효과가 반영되지 않음. (candles
   parquet은 재사용 가능; feature만 해당.)
2. `run_full_pipeline.ps1` 기본 실행이면 추가 플래그 불필요 — horizon/비용이
   자동으로 train↔backtest 정렬됨.
3. 결과 분석 시 이전(-10.98%) 백테스트와의 차이 중 일부는 weekly feature
   복원에서 올 수 있음. 단, 영향 범위는 정확히 구분할 것:
   - **rule regime 라우팅은 불변** — `MultiFeatureRegimeDetector`는 F17
     (trend_slope_1h/4h/24h, bb_width, volume_z 등)만 소비하고 weekly
     feature는 사용하지 않음 (`regime_rules.py`에 weekly 참조 없음 확인).
     따라서 `regime_routing_diagnostics` 분포는 이전 run과 동일해야 하며,
     달라졌다면 다른 원인을 의심할 것.
   - **entry 모델(CatBoost) 입력은 변함** — weekly 7종이 상수 0 → 실값이
     되므로 학습된 모델·threshold·성능이 모두 달라짐. v5 분석의 "rule-based
     regime 판단이 달라질 수 있음"이라는 우려 중 라우팅 부분은 해당 없음.
