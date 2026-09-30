# threshold horizon 정합성 수정 및 비교 도구 신설

> 작성일: 2026-07-10
> 대상 검토 문서: `project2_source_analysis_summary.md`
> 관련 문서: `CODE_REVIEW_FIXES.md`(전체 이력, 5차 라운드), `PIPELINE_INTEGRATION.md`(사용법)
> 변경 파일: `btcusdt_quant/cli.py`, `run_full_pipeline.ps1`, `run_full_pipeline.sh`, `tests/test_review_items.py`, `PIPELINE_INTEGRATION.md`, **신설** `compare_backtests.py`

---

## 1. 요약

외부 검토 문서의 지적 3건을 코드와 대조해 **전부 사실로 확인**했다. 다만 문서가 제시한 권장 코드에는 **새로운 look-ahead 리키지를 만드는 함정**이 있어, 가드를 함께 넣어 수정했다. 또한 문서가 "비교하라"고만 하고 도구가 없던 항목(레짐별/사이드별 PnL 분해)을 위해 `compare_backtests.py`를 신설했다.

| 구분 | 내용 |
|---|---|
| 검증된 지적 | 3건 (threshold horizon 불일치 / stale 문서 문구 / live 하드코딩) |
| 수정 | 7건 (T1~T7) |
| 신설 | `compare_backtests.py` |
| 회귀 검증 | 전체 스위트 **223개 통과** (기존 parquet float32 실패 1건 제외) |

---

## 2. 문제: threshold selection horizon ≠ execution horizon

### 2.1 무엇이 어긋났나

`train-multi-horizon --regime-aware`는 레짐/사이드별 진입 임계값을 홀드아웃에서 고르는데, 그 홀드아웃 라벨을 **`max(horizons)`** 기준으로 붙이고 있었다.

```python
# 수정 전
holdout_labeled = dataset.attach_labels(holdout_rows, candles, horizon=max_horizon, ...)
```

반면 Phase 4.5 백테스트는 단일 실행 배리어 `--horizon`(기본 60)으로 타임아웃한다. 즉:

```
모델 학습    : horizon 30/60/90 블렌드
임계값 선택  : horizon 90 라벨 기준     <- 어긋남
백테스트 실행: horizon 60 타임아웃
```

Phase 4(레짐 모델)는 `label_horizon = --horizon`으로 임계값을 고르므로, Phase 4 vs 4.5 비교에 **horizon 블렌드 외의 축이 하나 더** 생긴다.

### 2.2 실제로 거래 결정이 바뀐다 (동일 horizon A/B 실측)

`horizons=30,60,90` 고정, `--threshold-horizon`만 90 → 60으로 변경:

| 레짐/사이드 | th_h=90 | th_h=60 |
|---|---|---|
| range/long | 0.7685 | **0.2516** |
| range/short | 0.9536 | **0.55** |
| up/long | 0.9231 | 0.9231 |
| down/short | 0.8072 | 0.8072 |

`range` 레짐 임계값이 크게 달라진다. 무해한 정리가 아니라 **진입 결정을 바꾸는 정합성 수정**이다.

---

## 3. 검토 문서 권장안의 함정 (문서가 놓친 부분)

문서가 제시한 코드는 다음과 같다.

```python
threshold_horizon = args.threshold_horizon or max_horizon
holdout_labeled = dataset.attach_labels(holdout_rows, candles, horizon=threshold_horizon, ...)
```

**이대로 두면 `threshold_horizon > max_horizon`일 때 백테스트 구간을 리키지한다.**

이유: 호출부가 학습 창 tail을 `train_end = i1 - max_horizon`으로만 트림한다. 홀드아웃 라벨이 `threshold_horizon` 바 앞을 보는데 그 값이 `max_horizon`보다 크면, 라벨이 **학습 창 밖(= out-of-sample 백테스트 구간)의 캔들**을 읽는다. `attach_labels`는 전체 candles를 받으므로 행을 버리지도 않고 조용히 통과한다.

```
horizons=30,60,90 (max=90) 기준
  --threshold-horizon  30 → 안전 (-60바)
  --threshold-horizon  60 → 안전 (-30바)   <- 파이프라인이 쓰는 값
  --threshold-horizon  90 → 안전 (경계)
  --threshold-horizon 120 → LEAK (+30바, 백테스트 구간 침범)
```

### 해결

트림과 홀드아웃 purge gap을 모두 **가장 긴 라벨 도달거리**로 확장했다.

```python
label_reach = max(max(horizons), threshold_horizon)
train_end   = i1 - label_reach
holdout_start = holdout_split + label_reach   # purge gap
```

이로써 더 긴 임계값 horizon도 **거부하지 않고 안전하게 허용**된다.

---

## 4. 수정 내역

| # | 파일 | 내용 |
|---|---|---|
| **T1** | `cli.py` | `train-multi-horizon --threshold-horizon` 추가. 트림·purge gap을 `label_reach = max(max(horizons), threshold_horizon)`로 확장 |
| **T2** | `cli.py` | 미지정 시 `max(horizons)` 폴백 + **경고 출력** (하위호환 유지, 조용한 불일치 방지) |
| **T3** | `cli.py` | `--horizons` / `--threshold-horizon` 유효성 검증을 **캔들 로드·피처 계산 전으로 이동** (0.6초 만에 명확한 메시지로 실패) |
| **T4** | `cli.py` | `regime_run_summary.json`에 `threshold_horizon` / `label_reach` 기록. 계산하지 않은 값을 하드코딩하던 `mean_test_f1: 0.0` 제거 |
| **T5** | `cli.py` | **백테스트가 아티팩트의 `threshold_horizon`과 자기 `--horizon`을 비교해 경고.** 일치하면 조용. 같은 불일치의 재발 방지 |
| **T6** | `run_full_pipeline.{ps1,sh}` | Phase 3.5에 `--threshold-horizon $Horizon` 전달 |
| **T7** | `PIPELINE_INTEGRATION.md` | stale 문구 2곳 수정 + threshold horizon·플로어 주의사항 추가 (§6 참고) |

### 검증 결과 (실행 로그)

```
--threshold-horizon 120  →  "23,880 rows after 120-bar label trim"   (90 → 120 확장)
--threshold-horizon 미지정 → "WARNING: --threshold-horizon not set; ... 90-bar labels"
--threshold-horizon 0    →  "multi-horizon training failed: --threshold-horizon must be
                             a positive number of bars"   (0.6초, 피처 계산 전)

아티팩트 provenance:
  {'model_kind': 'multi_horizon_ensemble', 'horizons': [30,60,90],
   'threshold_horizon': 60, 'label_reach': 90, 'default_regime': 'range'}
  mean_test_f1 present? False

백테스트 경고:
  불일치(th_h=90, --horizon 60):
    WARNING: artifact thresholds were selected on 90-bar labels but --horizon is 60.
    Entry cutoffs were optimized for a different time barrier than the one this
    backtest enforces; retrain with --threshold-horizon 60 for a like-for-like result.
  일치(th_h=60, --horizon 60):
    (경고 없음)
```

---

## 5. 신설: `compare_backtests.py`

검토 문서의 7순위 비교 항목(레짐별 PnL, 사이드별 PnL, 월별 성과)에 **저장소 어디에도 도구가 없었다.** 데이터는 이미 `backtest_summary.json`의 `trades[]`에 다 있다(`entry_regime`, `model_side`, `entry_time`, `trade_return_pct`).

```bash
python compare_backtests.py \
    artifacts/backtest_results/backtest_summary.json \
    artifacts/backtest_results_multi_horizon/backtest_summary.json
```

기능:

- **레짐별 / 사이드별 / 레짐×사이드 / 월별** 수익·승률·per-trade 샤프·profit factor 분해
- `trade_return_pct`(가격 수익률이 아닌 **equity 수익률**)를 읽으므로 켈리 런도 계정이 실제로 번 값으로 요약된다. 구버전 아티팩트는 `net_pnl_pct`로 폴백
- **비교 불가 경고**: 두 런의 비용 기준·min_hold·cooldown이 다르거나 켈리 on/off가 다르면 명시
- `shorts_skipped_no_short_model > 0`이면 **"이 런은 LONG-ONLY"** 경고 (스모크에서 flat 모델을 바로 잡아냄)
- head-to-head 표에 per-trade 샤프/PF는 거래 수가 크게 다르면 비교 불가라는 주석 병기

파이프라인 최종 단계(ps1/sh 모두)에서 Phase 4 vs 4.5를 **자동 출력**한다. 정보성이므로 실패해도 파이프라인을 중단하지 않는다.

---

## 6. 문서 수정 (`PIPELINE_INTEGRATION.md`)

| 위치 | 수정 전 | 수정 후 |
|---|---|---|
| Phase 4 | "단일모델 경로의 SELL은 `1 - P(long)`으로 자동 반전" | "단일모델 경로는 `P(short_success)`가 없으므로 켈리가 SELL을 **거부**하고 `shorts_skipped_no_short_model`을 증가시킨다. 레짐 번들 경로는 전용 숏 모델의 `P(short_success)`로 사이징한다" |
| 검증 내역 | 4,000캔들 flat 모델 기준 (구버전 동작) | 24,000캔들 regime-aware 기준으로 갱신 |
| Phase 3.5 | tail 트림 `max(horizons)` | tail 트림 `max(max(horizons), --threshold-horizon)`, threshold horizon 설명 추가 |
| Phase 4.5 | — | 백테스트 경고, 플로어 주의, 남는 차이 2가지 명시 |

---

## 7. 남은 주의사항

1. **`--threshold-floor 0.45`가 학습 임계값을 덮어쓸 수 있다.**
   위 A/B에서 `range/long=0.2516`은 플로어에 막히고, `range/short=0.55` / `up/long=0.9231` / `down/short=0.8072`는 학습값이 살아남는다.
   → 실행 후 `backtest_summary.json`의 `effective_thresholds`에서 `learned_*` vs `effective_*`를 반드시 대조할 것. 학습 임계값이 전부 덮어써졌다면 이번 수정의 효과가 실행에 반영되지 않은 것이다.

2. **임계값 horizon을 맞춰도 완전한 like-for-like는 아니다.**
   Phase 4 대비 남는 차이는 **(a) horizon 블렌드**, **(b) base model 튜닝**(Phase 3은 Optuna 100 trials, Phase 3.5는 기본 파라미터), **(c) 확률 캘리브레이션 의미론**(블렌드 확률은 어느 단일 horizon에도 캘리브레이션되어 있지 않다) 세 가지다.
   따라서 Phase 4.5는 엄밀한 horizon-only A/B가 아니라 **regime-aware multi-horizon challenger 파일럿**으로 해석해야 한다.
   (학습 데이터 비율 차이는 6차 라운드의 최종 refit으로 해소했다 — `CODE_REVIEW_FIXES.md` 참고.)

3. **아티팩트 삭제는 수행하지 않았다.** 되돌릴 수 없는 작업이다.
   지운다면 `artifacts/archive_full`(아카이브)과 `artifacts/metrics`(선물 메트릭)는 **남길 것** — 재다운로드에 수 시간이 걸린다. 모델/백테스트 산출물(`regime_stacking_model`, `multi_horizon_model`, `backtest_results*`)만 지우면 된다.

4. **live 배선은 미착수.** `_handle_signal_event`의 `entry_quantity = 0.001` 하드코딩이 그대로다. `PositionSizer.kelly_notional()` API는 준비돼 있고, 선행 조건이던 사이드별 확률 의미론은 4차 라운드에서 해소됐으므로 착수 가능하다. `DrawdownProtocol.reduce_factor`가 수량에 곱해지지 않는 문제도 함께 정리해야 한다.

---

## 8. 회귀 검증

```
전체 스위트          : 223 passed, 1 deselected (기존 parquet float32 실패)
tests/test_review_items.py : 59 passed
run_full_pipeline.ps1 : ParseFile 구문검사 통과
run_full_pipeline.sh  : bash -n 통과
compare_backtests.py  : ast.parse 통과 + 실제 요약 2개로 스모크 실행 확인
```

신규 테스트 3종 (`ThresholdHorizonGuardTests`):

- `test_label_reach_covers_longer_threshold_horizon` — `label_reach`가 항상 둘 중 큰 값
- `test_holdout_labels_stay_inside_the_training_window` — 홀드아웃 라벨이 학습 창을 넘지 않음
- `test_backtest_warns_on_threshold_horizon_mismatch` — 불일치 시 경고, 일치 시 무음
