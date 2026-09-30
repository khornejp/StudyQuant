# run_full_pipeline.ps1 신기능 통합 내역

> 작성일: 2026-07-10
> 관련 문서: `APPLICATION_REVIEW_PLAN.md`(적용 계획), `CODE_REVIEW_FIXES.md`(구현·리뷰·수정 내역)
> 목적: 2026-07-09~10에 구현한 기능(리키지 진단, fold IC, OU 반감기, Half-Kelly 사이징, multi-horizon 앙상블, gross/net 샤프 병기)을 전체 파이프라인에서 실제 사용하도록 배선

---

## 1. 파이프라인 흐름 변경 요약

```
Phase 1    아카이브 다운로드 (변경 없음)
Phase 1.5  선물 메트릭 다운로드 (변경 없음)
Phase 2    Parquet 결합 (변경 없음)
Phase 2.3  [신설] 데이터 진단 — IC/리키지 리포트 + range 반감기
Phase 2.5  레짐 분류기 학습 (classifier 모드만, 변경 없음)
Phase 3    레짐 인식 모델 학습 (변경 없음)
Phase 3.5  [신설] multi-horizon 앙상블 파일럿 학습
Phase 4    [수정] 레짐 모델 백테스트 + Half-Kelly 사이징
Phase 4.5  [신설] multi-horizon 파일럿 백테스트 (동일 조건)
최종 요약   [수정] gross/net 샤프·켈리 진단·두 모델 비교 출력
```

## 2. 신규 설정 변수 (스크립트 상단 Configuration 블록)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `$KellySizing` | `$true` | Phase 4/4.5 백테스트에 fractional-Kelly 사이징 적용. `position_size`는 캡으로 재해석, edge≤0 진입은 스킵 |
| `$KellyMultiplier` | `"0.5"` | Half-Kelly 기본 (성장률 ~18.5% 양보로 MDD ~43% 축소) |
| `$KellyLookbackBars` | `"1440"` | 분산 추정 창 (1분봉 1일). 보유기간 스케일링은 `--horizon`(60)에 자동 정렬 |
| `$RunDiagnostics` | `$true` | Phase 2.3 진단 실행 여부. 전체 6년 parquet 기준 수 분 소요 |
| `$MultiHorizonPilot` | `$true` | Phase 3.5/4.5 파일럿 실행 여부. Optuna 없는 CatBoost 학습 ×horizon 수 |
| `$MhHorizons` | `"30,60,90"` | 파일럿 horizon 목록 (바 단위) |

주의: 불리언 변수는 `$null -eq` 검사를 사용하므로, 실행 전 `$KellySizing = $false`처럼 미리 설정하면 기본값이 덮어쓰지 않습니다.

## 3. Phase별 상세

### Phase 2.3 — 데이터 진단 (정보성, 파이프라인 중단 없음)

- **`ic_diagnostic.py`**: 피처×horizon Spearman IC + **fold별 평균±표준편차**(시간 안정성/IC drift) + **리키지 휴리스틱** 2종:
  - `fwd>past`: 미래 수익률과의 |IC|가 0.10을 넘으면서 같은 길이의 과거 수익률 |IC|보다 큰 경우 (인과적 피처에서 비정상)
  - `lag1-collapse`: 피처를 1바 늦게 써도 살아남아야 할 신호가 절반 이상 붕괴하는 경우 (off-by-one 룩어헤드 시그니처)
  - 결과: `artifacts/ic_report/ic_report.csv`. `regimes.json`이 있으면 레짐별 IC도 포함
  - **휴리스틱 트리아지용**이므로 플래그된 피처는 truncation-invariance 테스트(verify_weekly_causality.py 패턴)로 확정 후 조치
- **`verify_range_halflife.py`**: range 레짐 구간의 OU 반감기를 실측해 고정 20바 창(`range_position_20`, 평균회귀 게이트)과 비교, 창 재보정 권고 출력. `regimes.json` 없으면 전체 시계열만

### Phase 3.5 — multi-horizon 앙상블 파일럿 (레짐 인식)

- 신설 CLI: `python -m btcusdt_quant train-multi-horizon --regime-aware`
  - 피처는 **전체 시계열에서 1회 계산** 후 학습 창(`--training-start/end`)을 슬라이스하고, 라벨 forward window가 창을 넘지 않도록 tail을 `max(max(horizons), --threshold-horizon)`만큼 트림
  - 룰 디텍터로 버켓팅 후 **Phase 3와 동일한 direction policy**(up→long, down→short, range→both)를 따라 (레짐×사이드)마다 horizon 앙상블 학습
  - 각 사이드는 **전용 타깃**(`long_success` / `short_success`)으로 학습 — `1 - P(long_success)`는 숏 승률이 아니다(타임아웃된 롱은 숏 승리가 아님). 롱 타깃만 쓰면 숏 가격 산정이 불가능해 켈리가 SELL을 거부한다
  - 레짐/사이드별로 purge gap을 둔 별도 홀드아웃에서 `select_threshold`로 임계값 선택. 파이프라인은 **`--threshold-horizon $Horizon`**(=백테스트 `--horizon`)을 넘겨, 임계값이 실행이 강제하는 것과 **같은 시간 배리어**로 선택되게 한다. 지정하지 않으면 `max(horizons)` 라벨로 선택되며 경고를 출력한다
  - 산출물: `train --regime-aware`와 **동일한 레이아웃** — `regime_run_summary.json`(룰 디텍터 payload + 레짐별 `selected_thresholds` + `default_regime` + `threshold_horizon`) + `regime_{up,down,range}/{long,short}_model.json`
- `--regime-aware` 없이 실행하면 기존 flat 단일 모델(롱 측 타깃)로 학습되며, 켈리 하에서 long-only가 된다는 경고를 출력한다

### Phase 4 — 켈리 사이징 (레짐 모델 백테스트)

- `--kelly-sizing --kelly-multiplier 0.5 --kelly-lookback-bars 1440` 추가
- 트레이드별 사이즈 = Half-Kelly(진입 확률, **실제 실행 TP/SL 배리어**, 최근 분봉 분산 × 보유기간, **라운드트립 비용 차감 후 edge**) — `risk.kelly_leverage_for_signal` 단일 구현 사용 (backtest/live 동일 파이프라인)
- **숏 확률 의미론**: 단일모델 경로는 `P(short_success)`가 없으므로 켈리가 SELL 진입을 **거부**하고 `shorts_skipped_no_short_model`을 증가시킨다(`1 - P(long)`은 숏 승률이 아니다 — 타임아웃된 롱은 숏 승리가 아님). 레짐 번들 경로는 전용 숏 모델의 `P(short_success)`로 사이징한다
- `backtest_summary.json`의 `kelly_sizing` 블록: cap, 평균/최소/최대 비율, `round_trip_cost`, `entries_skipped_no_edge`, `shorts_skipped_no_short_model`
- **주의**: 같은 JSON의 `strategy_comparison` 블록은 고정 사이즈(`"sizing": "fixed_position_size"` 마커) — 켈리 백테스트와 직접 비교 금지

### Phase 4.5 — multi-horizon 파일럿 백테스트

- Phase 4와 동일한 기간·비용·켈리 설정으로 **디렉터리 아티팩트**(`model.json`이 아님)를 백테스트 → `artifacts/backtest_results_multi_horizon`
- 디렉터리를 넘기면 `load_regime_aware_models`가 룰 디텍터·direction policy·레짐별 임계값을 자동 적용하므로, Phase 4와 **레짐 버켓팅/사이드/타깃/임계값 목적함수/임계값 선택 배리어가 모두 동일**해진다
- 백테스트는 아티팩트의 `threshold_horizon`과 자기 `--horizon`이 다르면 **경고**한다 — 임계값이 다른 시간 배리어로 최적화됐다는 뜻이므로 그 결과는 like-for-like가 아니다
- **엄밀한 horizon-only A/B가 아니라 challenger 파일럿이다.** 남는 차이는 세 가지:
  - **(a) horizon 블렌드** — 파일럿의 검증 대상
  - **(b) base model 튜닝** — Phase 3은 Optuna 100 trials, Phase 3.5는 기본 파라미터. Optuna를 파일럿에도 적용하면 학습 비용이 크게 늘어난다
  - **(c) 확률 캘리브레이션 의미론** — 블렌드 확률은 어느 단일 horizon에도 캘리브레이션되어 있지 않다
- 학습 데이터 양은 이제 동일하다: Phase 3.5도 임계값 선택 후 **레짐 전체 행으로 최종 refit**한다(`--skip-final-refit`으로 끌 수 있으나, 그러면 배포 모델이 레짐 행의 약 64%만 학습해 비교가 왜곡된다)
- 레짐 모델 vs 파일럿을 **net 샤프/MDD 기준**으로 비교해 확장 여부 결정
- 요약 출력의 `shorts_skipped_no_short_model`은 회귀 감지기다 — **0이 아니면 어딘가 단방향 모델이 섞였다는 뜻**이고, 그 런은 long-only이므로 Phase 4와 비교 불가
- **주의**: `--threshold-floor 0.45`가 학습된 임계값보다 크면 플로어가 이를 덮어쓴다. 실행 후 `effective_thresholds.learned_*` vs `effective_*`를 확인해, 학습된 임계값이 실제로 쓰였는지 먼저 판단할 것

### 최종 요약 출력

- 두 백테스트 각각: gross/net 수익률, 트레이드 수, 승률, **net/gross 샤프 + cost_impact**(비용 드래그 — gross에서만 양수인 전략은 배포 금지, Chan ch.3), 켈리 진단, 레짐 커버리지

## 4. 검증 내역 (2026-07-10)

- 합성 데이터(24,000캔들, 상승/하락/횡보 교대) 엔드투엔드: `train-multi-horizon --regime-aware` → `regime_{down,range}/{long,short}_model.json` 생성 → `backtest --model-artifact <dir> --kelly-sizing` 로드/실행. `shorts_skipped_no_short_model=0`(양방향 켈리 활성), `entry_regime=down`(레짐 라우팅 동작), 레짐별 학습 임계값 적용 확인
- PowerShell `ParseFile` / `bash -n` 구문 검사 통과
- 전체 테스트 스위트 통과 (기존 parquet float32 실패 1건 제외)

## 5. 미반영/후속 항목

- **`run_full_pipeline.sh`** (bash 버전): 이번 변경 미반영 — ps1과 동기화 필요 시 별도 작업
- **live 엔진 주문 경로**: `_handle_signal_event`의 `entry_quantity=0.001` 하드코딩이 여전히 유효 — `PositionSizer.kelly_notional()` API는 준비됐으나 엔진 경로별 확률 의미론 정리 후 배선 권고 (`CODE_REVIEW_FIXES.md` K6/K7 참고)
- `--backtest-start` 기본값은 2025-01-01 — 파이프라인은 날짜를 명시하므로 영향 없음
