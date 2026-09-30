# 코드리뷰 결과 및 수정 내역 (2026-07-09)

> 대상: `APPLICATION_REVIEW_PLAN.md` 1~6번 항목 구현분
> (`btcusdt_quant/risk.py`, `ensemble.py`, `backtest.py`, `live.py`, `ic_diagnostic.py`, `verify_range_halflife.py`, `tests/test_review_items.py`)
> 방법: `/code-review` high effort — 8개 파인더 앵글(정확성 3 + 정리 3 + 설계 깊이 1 + 컨벤션 1) → 후보 27건 → 중복 제거 후 11건 → 후보별 1-검증자 → **7건 생존 (CONFIRMED 6, PLAUSIBLE 1), 4건 기각(REFUTED)**
> 상태: **생존 7건 전부 수정 완료, 회귀 검증 통과**

---

## 1. 발견 및 수정 내역

### F1. [CONFIRMED · 심각] Kelly 공식 기간 단위 불일치 — `risk.py`

- **문제**: `kelly_leverage_for_signal`이 **트레이드 단위** 기대수익(edge)을 **1분봉 단위** 분산으로 나눔. Kelly f\*=m/s²는 m과 s²가 같은 기간이어야 함. BTCUSDT 1분봉 σ≈0.0008 기준 f≈703이 나와 어떤 현실적 캡에도 항상 포화 → "동적" 사이징이 사실상 상수로 붕괴.
- **수정**: `KellySizingConfig`에 `holding_period_bars`(기본 60, label_horizon과 일치) 추가. 분봉 분산 × 보유기간으로 트레이드 단위 분산으로 스케일링(i.i.d. 근사 하 분산은 기간에 선형) 후 나눔. docstring도 단위 요건 명시.
- **검증**: `test_kelly_scales_bar_variance_to_trade_horizon` — 결정적 입력으로 f = 0.5×0.002/(1e-4×60) = 1/6 정확 일치 확인. 엔드투엔드 테스트에서 산출값이 캡 미만(동적)임을 단언.

### F2. [CONFIRMED] live 모델 로더에 multi_horizon_ensemble 분기 부재 — `live.py:1492`

- **문제**: `load_model_artifact()` 디스패치에 신규 패밀리 분기가 없어 저장된 `MultiHorizonEnsembleAdapter`를 로드 불가 (non-strict는 조용히 None → 모델 없는 백테스트, strict는 ValueError).
- **수정**: `"multi_horizon_ensemble"` 분기 추가 (`ensemble.MultiHorizonEnsembleAdapter.from_dict`).

### F3. [CONFIRMED] `_load_submodel`이 fallback 패밀리를 역직렬화 불가 — `ensemble.py`

- **문제**: `ModelFactory.fit(fallback_allowed=True)`는 catboost 부재 시 pytorch_multitask로 대체 학습할 수 있는데 `_load_submodel`은 lightgbm/catboost만 로드 → **학습·저장은 성공하고 from_dict에서만 실패**하는 save/load 비대칭. 부수: 존재하지 않는 `training.LinearClassifier`를 참조하는 죽은 분기(도달 시 AttributeError).
- **수정**: `pytorch_multitask`, `stacking_ensemble`, `multi_horizon_ensemble`(중첩 앙상블) 분기 추가, 죽은 `deterministic_centroid_linear` 분기 제거 (해당 패밀리를 생산하는 클래스가 패키지에 없음을 grep으로 확인).
- **검증**: 스모크 데이터로 학습→as_dict→JSON 저장→`live.load_model_artifact(strict=True)`→predict 라운드트립에서 확률 완전 일치 확인.

### F4. [CONFIRMED] IC 진단 상수 배열 반복 정렬 (~2.4배 감속) — `ic_diagnostic.py`

- **문제**: fold IC와 리키지 검사가 피처마다(≈180회) 피처와 무관하게 동일한 y측 배열(forward/past return, fold 슬라이스, 레짐 부분집합)을 재정렬. 기본 설정 기준 전체 실행 ~2.4배.
- **수정**: `_make_y_cache`(전량 유한할 때만 rank/평균/분산합 사전 계산; 아니면 None) + `_spearman_ic_cached`(x에 비유한값 있으면 정확 경로로 폴백) 도입. forward 캐시, fold 캐시, 레짐 인덱스·캐시를 피처 루프 밖으로 호이스팅. lag-1 검사는 n-원소 복사 배열 생성 대신 `feature_values[:-1]` vs `fwd[1:]` 페어링으로 대체(수학적으로 동일).
- **검증**: 최적화 전/후 `ic_report.csv` **완전 동일**(diff). `_spearman_ic_cached` vs `_spearman_ic` 일치 단위 테스트(NaN 폴백 포함) 추가.

### F5. [CONFIRMED] 검증 가중 루프의 행 단위 추론 — `ensemble.py`

- **문제**: `weighting="validation"` 루프가 행마다 dict 생성 + `adapter.probability()` 단건 호출 — CatBoost/LightGBM의 배치 추론 무력화 (60만 행 × 3 horizon ≈ 180만 단건 호출).
- **수정**: `training.feature_matrix()` 1회 + `adapter.predict_proba(matrix)` 배치 호출로 교체.
- **검증**: 라운드트립 테스트가 validation 가중 경로로 학습해 정상 가중치 산출 확인.

### F6. [CONFIRMED] `--window-bars 0` 지연 크래시 — `verify_range_halflife.py`

- **문제**: 양수 검증이 없어 0 입력 시 수 분짜리 로드/계산을 모두 끝낸 뒤 마지막 나눗셈에서 ZeroDivisionError, 음수는 엉터리 판정 출력.
- **수정**: 파싱 직후 `window_bars <= 0`이면 즉시 에러 종료(exit 1).
- **검증**: `--window-bars 0` 실행 시 즉시 거부 확인.

### F7. [PLAUSIBLE] `return_variance` lookback이 바 수가 아닌 유효 샘플 수로 동작 — `risk.py`

- **문제**: NaN 필터링 후 슬라이스해서, 갭 구간에서 분산 윈도우가 의도한 시간 창보다 과거로 확장 (`variance_lookback_bars`라는 설정명과 불일치).
- **수정**: 슬라이스를 먼저(바 단위 창 고정), NaN 제거는 창 내부에서만. 전량 NaN 창은 0.0 반환(→ no bet)으로 과거 데이터 재사용 방지.
- **검증**: `test_return_variance_lookback_counts_bars_not_finite_samples` — 창 밖 고변동 구간이 새어들지 않음을 단언.

---

## 2. 기각된 후보 (REFUTED, 수정 불필요)

| 후보 | 기각 사유 |
|---|---|
| `fit_multi_horizon_ensemble` 수동 purge 분할이 리키지 | 마지막 train 라벨 창이 `validation_start - 1`에서 끝남을 수식으로 확인 — 겹침 없음. `PurgedWalkForwardSplit`은 다중 fold·3분할 구조라 드롭인 대체가 오히려 복잡도 증가 |
| `_per_trade_sharpe`가 `training._sharpe` 중복 | `training._sharpe`는 √n 스케일링을 하는 **다른 통계량** — 재사용하면 오히려 버그. backtest→training 의존은 무거운 결합 |
| `models._clip_probability` 재사용 | 형제 어댑터(StackingEnsemble)도 인라인 클리핑(np.clip) 사용 — "canonical helper" 전제가 거짓 |
| ic_report.csv 스키마 불안정 | 저장소 내 소비자 없음 + DictWriter 헤더 자기기술적 + 기존에도 horizon 의존 컬럼명이었음 |

## 3. 회귀 검증 요약

- `tests/test_review_items.py` (29→36개로 확장) + `tests/test_stacking_ensemble.py`: **전부 통과**
- ic_diagnostic 최적화 전/후 CSV **바이트 단위 동일** (스모크 4,000캔들, regime 파일 포함)
- multi-horizon 앙상블 저장/로드 라운드트립: 확률 오차 < 1e-9
- 참고: `tests/test_v718.py`의 6건 실패는 **HEAD 기준 깨끗한 worktree에서도 동일하게 실패**함을 확인 — 이번 작업과 무관한 기존 실패 (feature_registry warmup 무효화, regime detector 관련; 별도 조사 필요)

## 4. 남은 권고 (수정 범위 외)

- ~~Kelly 사이징을 실제 live/backtest에 배선~~ → **5절에서 완료 (2026-07-09 2차 라운드)**
- `tests/test_v718.py` 기존 실패 5건 + `test_core.py` parquet round-trip 1건(float32 정밀도)의 원인 조사 — 둘 다 HEAD 기준 clean worktree에서 재현되는 기존 실패로 확인됨.

---

# 2차 라운드: Kelly 사이징 배선 + 코드리뷰 (2026-07-09)

## 5. 배선 구현 내역

| 위치 | 내용 |
|---|---|
| `backtest.py` | `run_backtest(kelly_config=...)` opt-in. 진입 시 `kelly_fraction_for_entry()` — 진입 확률 + **실제 실행 TP/SL 배리어** + 최근 분봉 분산(보유기간 스케일링)으로 트레이드별 equity 비율 산출. 기존 `position_size`는 캡으로 재해석. edge≤0이면 진입 스킵. 트레이드별 `position_size_used` 기록, `kelly_sizing` 진단 블록(평균/최소/최대 비율, 스킵 수) 추가 |
| `live.py` | `PositionSizer.kelly_notional()` — 공용 파이프라인으로 동적 비율 산출 후 `fixed_notional` 위임. edge 없으면 `kelly_no_edge_or_variance`로 거부 |
| `cli.py` | `--kelly-sizing`, `--kelly-multiplier`(기본 0.5), `--kelly-lookback-bars`(기본 1440). `holding_period_bars`는 `--horizon` 자동 일치 |

## 6. 2차 코드리뷰 발견 및 수정 (8앵글 → 후보 26건 → 검증 → 확정 7건)

### 수정 완료

| # | 판정 | 발견 | 수정 |
|---|---|---|---|
| K1 | CONFIRMED·심각 | **단일모델 경로(3곳)에서 SELL 진입 확률이 P(long)** — Kelly가 음수 edge로 계산해 숏을 전부 스킵, `--kelly-sizing`이 롱온리로 변질. 번들 경로(전용 숏 모델)는 정상 | `_ctx_two_sided` 컨텍스트 추가, 단일모델 SELL은 `1 - prob`로 반전. 회귀 테스트 `test_kelly_sizes_shorts_on_single_model_path` |
| K2 | CONFIRMED | `kelly_notional`: Kelly 비율이 `max_notional_fraction` 초과 시 `fixed_notional`이 클램프가 아닌 **하드 거부** — 양의 edge 진입이 통째로 거절되는 잠재 케이스 | 캡을 `min(static ratio, max_notional_fraction)`으로 사전 클램프. 테스트 추가 |
| K3 | CONFIRMED | **Kelly 파이프라인 3중 복제** (risk/backtest/live) — `risk.kelly_leverage_for_signal`이 정확한 공용 구현인데 테스트만 호출, 양산 경로 2곳이 인라인 복제 → backtest≠live 사이징 드리프트 위험 | `kelly_leverage_for_signal`에 `cap` 파라미터 추가, backtest·live 모두 위임. 단일 구현 확립 |
| K4 | CONFIRMED·저심각 | Kelly 백테스트와 고정 사이즈 strategy_comparison이 한 JSON에 동일 필드명으로 병기, 비교 블록엔 사이징 표기 없음 | `compare_strategies` 반환에 `"sizing": "fixed_position_size"` 마커 추가, CLI help 명시 |
| K5 | PLAUSIBLE | `KELLY_SKIP`을 `signal_counts`에 넣어 per-bar 신호 히스토그램과 per-entry 사이징 결과가 혼합(같은 바 이중 집계) | 전용 카운터로 분리, `kelly_sizing["entries_skipped_no_edge"]`로만 보고 |

### 확정됐으나 별도 작업 권고 (live 엔진 기존 구조)

| # | 판정 | 발견 |
|---|---|---|
| K6 | CONFIRMED | **live 엔진 진입 경로가 `entry_quantity = 0.001` 하드코딩** (`_handle_signal_event`, live.py:2380) — `PositionSizer`가 엔진에서 아예 인스턴스화되지 않아 `fixed_notional`/`kelly_notional` 모두 미호출. 백테스트는 Kelly 곡선, live는 고정 0.001 BTC → train/serve 사이징 스큐. 배선에 필요한 입력(balance, `model_inference["probability"]`, `optimized_tp_sl`, canonical closes)은 전부 스코프 내 존재하나, **엔진 경로별 확률 의미론(K1과 동일 함정)을 먼저 정리해야 안전** — 별도 작업으로 권고 |
| K7 | CONFIRMED | `DrawdownProtocol`의 `reduce_factor`가 로깅용으로만 소비되고 수량에 곱해지지 않음 — 다만 현재 reduce_size 티어는 주문 자체를 미제출(더 보수적)이라 즉각 위험은 아님. K6 배선 시 함께 구성 권고 |

### 기각 (REFUTED)

- CLI ValueError 원시 traceback 주장 — backtest 핸들러 전체가 `except (OSError, RuntimeError, ValueError)`로 감싸져 있어 이미 깔끔히 처리됨.
- 효율 앵글 후보들 — 진입이 희소(쿨다운)해서 per-entry O(lookback) 분산 계산은 현실 실행에서 1초 미만, rolling variance 전환은 복잡도 대비 무가치로 자체 결론.
- 크로스파일 앵글 — 시그니처/스키마/순환임포트/argparse 전 항목 안전 확인, 발견 0건.

## 7. 2차 회귀 검증

- `tests/test_review_items.py` 36→**50개**로 확장, `test_stacking_ensemble.py` 포함 전부 통과
- `tests/test_core.py` 130 통과 / 1 실패(parquet float32 — HEAD에서도 재현되는 기존 실패)
- CLI `--kelly-sizing` 플래그 파싱 스모크 통과

---

# 3차 라운드: `project_pipeline_source_review_summary.md` 검토 및 수정 (2026-07-10)

외부 검토 문서의 지적 5건을 코드와 대조해 **전부 사실로 확인**했고, 문서가 놓친 심각한 버그 1건을 포함해 5건을 추가로 발견해 수정했다.

## 8. 외부 검토 문서 주장의 검증 결과

| 문서 주장 | 판정 | 근거 |
|---|---|---|
| Kelly edge에 비용 미반영 | CONFIRMED | 손익분기 확률 실측: gross `p=0.3333`, net `p=0.5111` — 문서 수치와 정확히 일치 |
| Sharpe/profit_factor가 size 미반영 | CONFIRMED | `returns.append(pnl_pct)`가 가격 기준 수익률. `total_return`/`max_drawdown`은 equity 기반이라 size 반영 → 한 결과 안에 두 기준이 혼재 |
| multi-horizon SELL 해석 위험 | CONFIRMED (실증) | 실측: `P(long_success)=0.488`, `P(short_success)=0.000`, 합계 ≠ 1. 롱 실패의 **86%가 timeout**(1,738/2,017)이지 숏 성공이 아님 |
| `run_full_pipeline.sh` 미동기화 | CONFIRMED | 318줄에 kelly/multi-horizon/diagnostics 0건 |
| OU half-life가 raw close 기준 | CONFIRMED | drift·heteroskedasticity로 추정 불안정 |

### 문서에 대한 정정 2건

1. **우선순위 정정** — size-weighted 지표는 *현재 수치를 전혀 바꾸지 않는다*. 현실적 변동성 전 구간에서 Kelly 비율이 캡(0.1)을 초과해 **모든 거래가 캡에 고정**되기 때문이다(캡 미만이 되는 확률 구간 폭은 0.0007~0.024에 불과). 즉 Kelly는 지금 **사이저가 아니라 이진 진입 필터**로 동작한다. 잠재 버그로서 수정할 가치는 있으나, 문서가 말한 "모델 비교 왜곡"의 실제 원인은 size가 아니라 **Kelly 스킵으로 인한 거래 모집단 변화**다. 또한 자동화 게이트(`select_threshold`, champion-challenger, `run_experiments`)는 `BacktestResult.sharpe`를 소비하지 않고 `training.py`의 독립 `_trading_pnl` 시뮬레이터를 쓰므로 **오염되지 않았다**.
2. **선택지 B 재평가** — `attach_labels`가 이미 `long_success`/`short_success` 타깃을 생산하고(`dataset.py`), `training.py`가 이미 그 방식으로 레짐별 양방향 모델을 학습한다. 따라서 horizon별 long/short 분리는 문서 평가와 달리 **타깃 키 교체 수준**이며, 장기 방향으로 권장한다.

## 9. 수정 내역 (우선순위 순)

| # | 심각도 | 문제 | 수정 |
|---|---|---|---|
| P1 | **CRITICAL** | `train-multi-horizon`이 `candles[i0:i1]`을 슬라이스해 넘기지만 `FeatureRow.index`는 전체 시계열 인덱스 → `--training-start`가 첫 캔들 이후면 **라벨이 미래 캔들에서 계산됨**(조용한 look-ahead). 재현: i0=1000일 때 close 55,255 대신 60,061(1,000바 미래)을 읽고 라벨 행 2,940→1,940 유실 | 전체 candles를 넘기고 `feature_rows[i0:i1-max(horizons)]`로 tail 트림 → 라벨 forward window가 학습 창을 넘지 않음. 회귀 테스트 `MultiHorizonSliceAlignmentTests` |
| P2 | **HIGH** | 2차 라운드에서 넣은 `1 - prob` 반전이 단일모델 SELL의 숏 승률을 조작 — 실측상 실제 0%를 51%로 오판 | 반전 제거. 단일모델 SELL은 Kelly가 **거부**하고 `shorts_skipped_no_short_model`로 별도 보고(no-edge 스킵과 구분). 스모크: 이전 98건 체결 → 3,881건 거부 |
| P3 | **HIGH** | Kelly edge가 gross TP/SL 기준 → net 기준 음수 기대값 거래에 진입 | `expected_edge(p, tp, sl, round_trip_cost)`: `net_win = tp-rt`, `net_loss = sl+rt`. `net_win<=0`이면 무조건 no-bet. `risk`/`backtest`/`live` 단일 파이프라인 전체에 전달 |
| P4 | **HIGH** | `$ErrorActionPreference="Stop"`은 PS 5.1에서 python의 비정상 종료를 잡지 못하고, ps1에 `$LASTEXITCODE` 검사 0건 → 학습 실패가 조용히 백테스트로 진행 | `Assert-PhaseSucceeded`(아티팩트 생성 단계 게이팅) / `Warn-IfPhaseFailed`(진단 단계는 비게이팅) 도입, 9개 python 호출에 적용 |
| P5 | MEDIUM | Sharpe/gross_sharpe/profit_factor가 size 미반영 | `BacktestTrade.trade_return_pct` / `gross_trade_return_pct` 추가, 지표를 equity 수익률 기준으로 계산. 고정 사이즈에서는 상수가 약분되어 **기존 값 불변**(테스트로 고정) |
| P6 | MEDIUM | `.sh` 미동기화 | Phase 2.3 / 3.5 / 4.5 + Kelly 플래그 + gross/net sharpe 요약 이식. `set -euo pipefail`이 이미 게이팅하므로 진단 단계만 `|| true`. 마지막 요약의 `python3` → `python`(다른 모든 단계와 일치) |
| P7 | MEDIUM | OU half-life가 raw close 기준 | `--series {close,vwap_deviation,log_zscore}` 추가. 파이프라인은 `log_zscore` 사용. `--detrend-window`(기본 60)를 분리하고 **`--window-bars` 이하면 거부** — 검증 대상 창으로 detrend하면 반감기가 그 창의 인공물이 되어 순환 논리 |
| P8 | LOW | `multi_horizon_summary.json`의 `training_rows`가 warmup/purge 제거분 미반영 | `window_candles` / `rows_after_label_trim` / `rows_past_warmup`로 분해 기록 |
| P9 | LOW | `log_zscore`가 바마다 창 전체 재계산(O(n·window)), `vwap_deviation`은 0/음수 close 미방어 | 둘 다 O(n) 롤링 누적으로 통일, 비유효 close는 양쪽 모두 결측 처리. 리팩터 후 값 동일(12.5 / 8.8)로 검증 |

## 10. 3차 코드리뷰 (수정분 대상)

수정 직후 diff에 2개 앵글(라인 스캔 / 크로스파일)을 돌린 결과:

- **고·중 심각도 결함 0건.** Kelly 배선, SELL 거부, 카운터 초기화, size-weighted 지표, `train_end` 산술(off-by-one 아님)이 모두 정확함을 확인.
- API 변경(`expected_edge`, `kelly_leverage_for_signal`, `kelly_fraction_for_entry`, `kelly_notional`, `BacktestTrade` 신규 필드)은 **전부 하위호환** — 모든 호출부가 키워드 인자 사용, 신규 dataclass 필드는 기본값과 함께 뒤에 추가되어 위치 인자 파손 없음.
- 발견된 저심각도 4건 중 3건(즉 P7의 `--window-bars` 미전달, P9의 O(n·window)와 입력 위생)을 이 라운드에서 함께 수정했고, 죽은 변수 1건도 정리.
- `expected_edge`가 `net_win<=0`일 때 `-net_loss`를 반환하는 설계는 **유일 소비자가 부호만 검사**함을 grep으로 확인 — 안전.

## 11. 3차 회귀 검증

- `tests/test_review_items.py` 50→**53개**로 확장 (비용 반영 손익분기, 숏 거부/숏모델 존재 시 사이징, size-weighted vs 고정사이즈 불변, 인덱스 정렬 재현 테스트 포함)
- 빠른 스위트 5종 **87개 통과**
- 전체 스위트(`tests/`, `test_v718.py` 제외) **217개 통과 / 1건 deselect**(parquet float32 — HEAD 클린 worktree에서도 재현되는 기존 실패)
- ps1 `ParseFile` 구문검사 통과, `bash -n` 통과
- 엔드투엔드 스모크: `train-multi-horizon`(중간 `--training-start` 포함) → `backtest --kelly-sizing` — `round_trip_cost=0.0008` 반영, 숏 3,881건 거부, `trade_return_pct = pnl_pct × size` 확인

## 12. 남은 권고

- **live 엔진 배선(K6/K7)** — 여전히 `entry_quantity=0.001` 하드코딩. P2에서 드러났듯 **경로별 확률 의미론 정리가 선행 조건**이다. `short_success` 모델을 먼저 붙인 뒤 `kelly_notional`을 배선할 것.
- **multi-horizon 양방향 확장** — 현재 파일럿은 Kelly 하에서 사실상 long-only(`shorts_skipped_no_short_model`로 가시화됨). `long_success`/`short_success` 타깃으로 horizon별 양방향 모델을 학습하면 해소된다.
- **Kelly 캡 재보정** — 현 설정에서 Kelly는 사이저가 아니라 필터다. 동적 사이징을 원하면 `position_size` 캡을 올리거나 `--kelly-multiplier`를 낮출 것.
- **Phase 4.5 horizon 정합** — 30/60/90 블렌드 모델을 단일 `--horizon 60` 실행 배리어로 백테스트하므로, 30/90 성분은 라벨과 실행 배리어가 어긋난다. 파일럿의 구조적 한계로 기록.
- `tests/test_v718.py` 기존 실패 5건 + parquet float32 1건 원인 조사.

---

# 4차 라운드: multi-horizon 파일럿을 레짐 구조에 정렬 (2026-07-10)

## 13. 배경 — 왜 필요했나

프로덕션 학습(`train --regime-aware`)의 실제 구조는:

```
train_long  = regime in ("up", "range")   -> long_success 타깃
train_short = regime in ("down", "range") -> short_success 타깃
저장: regime_{name}/long_model.json, short_model.json
```

즉 **up→롱만, down→숏만, range→양방향**이고 각 사이드가 전용 triple-barrier 타깃으로 학습된다.

- **Phase 4(레짐 모델)는 이미 정상**이었다. 백테스트가 번들 경로로 들어가 `_ctx_two_sided=True`가 되고 `short_prob`가 진짜 `P(short_success)`이므로, 3차 라운드에서 넣은 숏 거부는 이 경로에 걸리지 않는다(`shorts_skipped_no_short_model=0`).
- **Phase 4.5(파일럿)만 어긋나 있었다.** `fit_multi_horizon_ensemble`이 레짐 라우팅 없이 평평한 단일 모델을 `row.label`(롱 측 profitability)로 학습해서, ① SELL 확률 의미론이 없고 ② 켈리 하에서 사실상 long-only가 되며 ③ Phase 4와의 비교가 애초에 성립하지 않았다.

## 14. 수정 내역

| 파일 | 변경 |
|---|---|
| `ensemble.py` | `fit_multi_horizon_ensemble(..., target_key=...)` 추가 — `profitability`(기본, 하위호환) / `long_success` / `short_success`. 단일 클래스 타깃이면 명시적 에러. 라벨 부족 에러 메시지에 "warmup 행이 라벨링에서 제거됨"을 명시 |
| `cli.py` | `train-multi-horizon --regime-aware` 신설. 룰 디텍터로 버켓팅 → `MH_REGIME_SIDES`(up→long, down→short, range→both) 정책대로 (레짐×사이드)마다 horizon 앙상블 학습 → **`train --regime-aware`와 동일한 아티팩트 레이아웃** 생성. 부수 플래그: `--rule-regime-config`, `--min-regime-rows`, `--threshold-objective`, `--round-trip-cost` |
| `cli.py` | 레짐/사이드별로 **max(horizons) purge gap을 둔 크로노 홀드아웃**을 따로 떼어 `training.select_threshold`로 임계값 선택 (홀드아웃은 어떤 horizon 모델도, 블렌드 가중치도 본 적 없음) |
| `cli.py` | flat 모드는 유지하되, "롱 측 타깃이라 숏을 가격 매길 수 없고 켈리가 SELL을 거부한다"는 경고를 출력 |
| `run_full_pipeline.{ps1,sh}` | Phase 3.5에 `--regime-aware --threshold-objective --round-trip-cost --rule-regime-config` 전달. Phase 4.5의 `--model-artifact`를 `model.json` → **디렉터리**로 변경(→ `load_regime_aware_models` 경유, 룰 디텍터·direction policy·레짐별 임계값 자동 적용) |

### 생성되는 아티팩트

```
artifacts/multi_horizon_model/
  regime_run_summary.json     # 룰 디텍터 payload + regime_results + selected_thresholds + default_regime
  regime_up/    long_model.json     # MH 앙상블(30/60/90), long_success
  regime_down/  short_model.json    # MH 앙상블(30/60/90), short_success
  regime_range/ long_model.json  short_model.json
```

기존 `live.load_regime_aware_models` / 백테스트 번들 경로를 **그대로 재사용**한다(신규 로더 코드 없음). `_load_submodel`이 3차 라운드에서 `multi_horizon_ensemble`을 지원하도록 확장돼 있었기에 중첩 로딩도 동작한다.

## 15. 검증

합성 24,000봉(상승/하락/횡보 3구간 교대) 엔드투엔드:

```
[MH] rule regime distribution: {'up': 4436, 'down': 5913, 'range': 13641}
[MH] regime down/short : holdout n=1,173 threshold=0.0399
[MH] regime range/long : holdout n=2,719 threshold=0.0171
[MH] regime range/short: holdout n=2,719 threshold=0.0007
  skipped: {'up': 'no side could be fitted'}   # 합성 상승추세라 long_success 단일 클래스
```

이어서 `backtest --model-artifact <dir> --kelly-sizing`:

```
trades: 2  sides: {'SELL': 2}   entry regimes: {'down': 2}
shorts_skipped_no_short_model: 0      <- 양방향 켈리 활성 (핵심)
effective_thresholds: down{learned_short=0.0006}, range{learned_long=0.0111, learned_short=0.0012}
regime_coverage: matched=2925
```

- 파이프라인과 동일한 플래그(`--threshold-floor 0.45` 포함)로 재현 시 진입 0건 — 학습 임계값이 플로어로 상향돼 막힌 것으로, 플로어가 의도대로 동작함을 확인
- 신규 단위 테스트 3종: direction policy가 `training.py`와 일치하는지, `target_key` 검증, **`P(long)+P(short) != 1`이고 롱 실패 대부분이 숏 승리가 아님**을 라벨에서 직접 확인
- `tests/test_review_items.py` 56개 + `test_stacking_ensemble.py` 포함 61개 통과, ps1/sh 구문검사 통과

## 16. 이 변경으로 해소된 것

- Phase 4.5가 Phase 4와 **동일한 레짐 버켓팅·direction policy·사이드별 타깃·임계값 목적함수**를 쓰게 됐다. (※ 6차 라운드 정정: 그렇다고 차이가 horizon 블렌드 "하나"로 귀결되지는 않는다 — Optuna 튜닝 유무가 남으며, 학습 데이터 비율 차이는 6차 라운드의 최종 refit으로 해소했다.)
- 파일럿이 켈리 하에서 long-only로 변질되던 문제 해소 — 숏은 이제 `short_success` 모델의 진짜 확률로 사이징된다.
- 3차 라운드의 `shorts_skipped_no_short_model` 카운터는 이제 **회귀 감지기** 역할을 한다: 파이프라인 출력에서 0이 아니면 어딘가 단방향 모델이 섞였다는 뜻.

## 17. 남은 항목

- live 엔진 배선(K6/K7) — 이제 선행 조건(사이드별 확률 의미론)이 해소됐으므로 착수 가능.
- `up` 레짐이 실데이터에서도 단일 클래스로 스킵되는지 확인 필요(합성 데이터의 인공물일 가능성이 높음).
- Phase 4.5의 실행 배리어는 여전히 단일 `--horizon`이라 30/90 성분과 어긋난다(파일럿의 구조적 한계).

---

# 5차 라운드: `project2_source_analysis_summary.md` 검토 및 수정 (2026-07-10)

## 18. 외부 검토 문서 주장의 검증

| 지적 | 판정 | 근거 |
|---|---|---|
| threshold selection이 `max_horizon`(90) 기준, 실행은 `--horizon`(60) | **CONFIRMED** | `cli.py`의 `attach_labels(holdout_rows, candles, horizon=max_horizon, ...)`. Phase 4는 `label_horizon = --horizon`으로 임계값을 고르므로 축이 하나 더 어긋남 |
| `PIPELINE_INTEGRATION.md`의 `1 - P(long)` 자동 반전 문구가 stale | **CONFIRMED** | 62행. 3차 라운드에서 반전→거부로 바꿨는데 문서만 남음 |
| live `entry_quantity = 0.001` 하드코딩 | **CONFIRMED** | 여전히 유효 (별도 작업) |

### 문서가 놓친 것 — 제안대로만 하면 새 리키지가 생김

문서의 권장 코드(`threshold_horizon = args.threshold_horizon or max_horizon`)는 **가드 없이는 백테스트 구간을 리키지한다.** 호출부가 학습 창 tail을 `train_end = i1 - max_horizon`으로만 트림하기 때문에, `threshold_horizon > max_horizon`이면 홀드아웃 라벨이 학습 창 밖(=out-of-sample) 캔들을 읽는다. `attach_labels`는 전체 candles를 받으므로 행을 버리지도 않고 조용히 통과한다.

```
horizons=30,60,90 (max=90)
  --threshold-horizon  60 → 안전 (-30바)
  --threshold-horizon  90 → 안전 (경계)
  --threshold-horizon 120 → LEAK (+30바, 백테스트 구간 침범)
```

## 19. 수정 내역

| # | 내용 |
|---|---|
| T1 | `train-multi-horizon --threshold-horizon` 추가. **트림과 purge gap을 `label_reach = max(max(horizons), threshold_horizon)`로 확장** — 더 긴 임계값 horizon도 안전하게 허용 |
| T2 | 미지정 시 `max(horizons)` 폴백 + **경고 출력**(하위호환 유지하되 조용한 불일치 방지) |
| T3 | `--horizons` / `--threshold-horizon` 유효성 검증을 **캔들 로드·피처 계산 전으로 이동** (0.6초 만에 명확한 메시지로 실패) |
| T4 | `regime_run_summary.json`에 `threshold_horizon` / `label_reach` 기록. 조작된 `mean_test_f1: 0.0` 제거 |
| T5 | **백테스트가 아티팩트의 `threshold_horizon`과 자기 `--horizon`을 비교해 경고** — 같은 불일치의 재발 방지. 일치할 때는 조용 |
| T6 | `run_full_pipeline.{ps1,sh}` Phase 3.5에 `--threshold-horizon $Horizon` 전달 |
| T7 | `PIPELINE_INTEGRATION.md`의 stale 문구 2곳 수정 (단일모델 SELL 동작, 구버전 검증 노트) + threshold horizon·플로어 주의사항 추가 |

## 20. 효과 실증 (동일 horizon A/B)

`horizons=30,60,90` 고정, `--threshold-horizon`만 90 → 60으로 바꾼 비교:

| 레짐/사이드 | th_h=90 | th_h=60 |
|---|---|---|
| range/long | 0.7685 | **0.2516** |
| range/short | 0.9536 | **0.55** |
| up/long | 0.9231 | 0.9231 |
| down/short | 0.8072 | 0.8072 |

`range` 레짐의 임계값이 크게 바뀐다 — 즉 이 수정은 무해한 정리가 아니라 **실제로 거래 결정을 바꾸는 정합성 수정**이다.

가드 동작:

```
--threshold-horizon 120 → "23,880 rows after 120-bar label trim" (90 → 120으로 확장)
--threshold-horizon 미지정 → "WARNING: --threshold-horizon not set; ... 90-bar labels"
--threshold-horizon 0 → "multi-horizon training failed: ... must be a positive number of bars" (0.6초)
```

백테스트 경고:

```
불일치(th_h=90, --horizon 60):
  WARNING: artifact thresholds were selected on 90-bar labels but --horizon is 60. ...
일치(th_h=60, --horizon 60):
  (경고 없음)
```

## 21. 남은 주의사항

- **`--threshold-floor 0.45`가 학습 임계값을 덮어쓸 수 있다.** 위 A/B에서 `range/long=0.2516`은 플로어에 막히고, `range/short=0.55` / `up/long=0.9231` / `down/short=0.8072`는 학습값이 살아남는다. 실행 후 `effective_thresholds`의 `learned_*` vs `effective_*`를 반드시 대조할 것.
- **임계값 horizon을 맞춰도 완전한 like-for-like는 아니다.** MH 확률은 30/60/90 블렌드라 어느 단일 horizon에도 캘리브레이션되어 있지 않다. Phase 4 대비 차이는 (a) horizon 블렌드 + (b) 확률 캘리브레이션 의미론 두 가지로 남는다 — 파일럿의 본질이지 버그가 아니다.
- ~~레짐별/사이드별 PnL 집계 도구가 없다~~ → **`compare_backtests.py` 신설로 해소.** `backtest_summary.json` 두 개를 받아 레짐별/사이드별/레짐×사이드/월별로 수익·승률·샤프·profit factor를 분해하고, 비용·쿨다운·켈리 설정이 다르면 '비교 불가' 경고를 낸다. 파이프라인 최종 단계에서 Phase 4 vs 4.5를 자동 출력한다(정보성, 비게이팅). `trade_return_pct`(equity 수익률)를 읽으므로 켈리 런도 계정이 실제로 번 값으로 요약된다.
- **아티팩트 삭제는 수행하지 않았다.** `artifacts/archive_full`·`artifacts/metrics`는 재다운로드에 수 시간이 걸리므로, 지운다면 모델/백테스트 산출물만 지울 것.
- live 배선(K6/K7)은 여전히 미착수.

## 22. 5차 회귀 검증

- 전체 스위트 **223개 통과** / 1건 deselect(기존 parquet float32)
- 신규 테스트 3종: `label_reach` 계산, 홀드아웃 라벨이 학습 창을 넘지 않음, 백테스트 불일치 경고
- ps1 `ParseFile` / `bash -n` / `compare_backtests.py` 구문 검사 통과

---

# 6차 라운드: `project3_threshold_horizon_review_summary.md` 검토 및 수정 (2026-07-10)

## 23. 검토 문서 보완점 5건 — 전부 CONFIRMED

| # | 지적 | 판정 | 근거 |
|---|---|---|---|
| 1 | `compare_backtests`의 `total_return`이 단순 합계 | CONFIRMED | 합계 +5.00% vs 복리 -2.50% (부호 반전 가능) |
| 2 | `trade_count`가 winner 판정 대상 | CONFIRMED | 거래 수가 많다고 나은 전략이 아님 |
| 3 | 비교 조건 provenance 부족 | CONFIRMED | `as_dict()`에 `backtest_start/end`, `execution_horizon`, `exec_tp/sl`, `initial_equity`, `position_size` 전무 |
| 4 | "horizon blend 하나만 다르다"는 설명 부정확 | CONFIRMED | Phase 3은 Optuna 100 trials, MH는 0건 |
| 5 | live `entry_quantity=0.001` | CONFIRMED | 미착수 |

### 문서가 놓친 더 큰 비대칭

`training.py:1138`의 배포 모델은 `long_model.fit(f_matrix, ...)` — 레짐 **전체 행**으로 학습한다(80/20 홀드아웃은 임계값용 별도 진단 모델에만 사용). 반면 4차 라운드의 MH는 `fit_rows = regime_rows[:80%]`로만 학습하고 내부에서 검증 tail(20%)까지 뺐다.

```
Phase 3  배포 모델: 레짐 행의 100.0%
Phase 3.5 배포 모델: 레짐 행의  63.9%   <- 파일럿에 대한 데이터 핸디캡
```

즉 실제 차이는 **세 가지**였다: ① horizon 블렌드 ② Optuna 유무 ③ **학습 데이터 64% vs 100%**. ③은 문구 정정이 아니라 코드로 고쳐야 할 문제였다.

## 24. 수정 내역

| # | 파일 | 내용 |
|---|---|---|
| R1 | `compare_backtests.py` | `total_return` → **`sum_trade_returns`(기여도) + `compounded_subset_return`(단독 복리)** 병기. 둘 다 `net_total_return`과 다르다는 점을 출력에 명시 |
| R2 | `compare_backtests.py` | `trade_count`를 **winner 판정에서 제외**하고 정수 + 차이만 표시. `win_rate`를 채점 항목에 추가 |
| R3 | `backtest.py` | `BacktestResult.run_config` 신설 — window, execution_horizon, exec tp/sl, strategy, position_size, initial_equity, threshold override, kelly 설정 전부 기록 |
| R4 | `compare_backtests.py` | `run_config` + 비용/게이팅 12개 필드를 대조해 **"NOT LIKE-FOR-LIKE"** 경고. `run_config` 없는 구버전 아티팩트도 명시 |
| R5 | `compare_backtests.py` | **`effective_thresholds` 대조 리포트** — 사이드별 `learned` vs `effective`를 찍고, 전부 덮어써졌으면 "이 런은 임계값 변경 효과를 보여줄 수 없다" 경고 |
| R6 | `ensemble.py` + `cli.py` | **최종 refit (Phase 3 parity).** 임계값은 prefix 전용 진단 앙상블에서 선택하고, 배포 모델은 레짐 전체 행으로 재적합. 블렌드 가중치는 진단에서 **그대로 이월**해 검증 tail이 불필요해져 각 horizon 모델이 자기 라벨 행 100%를 학습. `--skip-final-refit`으로 끌 수 있음 |
| R7 | 4개 문서/스크립트 | "ONLY axis" / "horizon 블렌드 축 하나" 과잉 주장을 **challenger 파일럿(blend + Optuna + 캘리브레이션 의미론)** 으로 정정 |

## 25. 코드 리뷰에서 잡은 자체 결함 3건 (수정분 대상)

| # | 심각도 | 발견 | 수정 |
|---|---|---|---|
| C1 | **HIGH** | `weights`를 시퀀스로 받아 내부 정렬된 `horizons`와 **위치로** 대응 — 호출자가 `horizons=[90,30,60]`로 넘기면 가중치가 엉뚱한 모델에 붙음(길이는 맞아 에러 없음) | `Mapping[int, float]`(`{horizon: weight}`)로 변경해 순서 모호성 자체를 제거. 누락/초과 키를 명시적으로 거부 |
| C2 | **MEDIUM** | `final_refit`을 `not args.skip_final_refit`(요청값)으로 기록 — refit이 실패해 prefix 모델을 배포해도 아티팩트는 데이터 parity를 주장 | 사이드별 `refit_done` 실측값 기록. 상위 요약은 `final_refit_requested` / `final_refit_all_sides`로 분리 |
| C3 | **MEDIUM** | `weights` 제공 시에도 `rows[:n]`(n = horizon별 최소 라벨 행)로 잘라, 짧은 horizon의 여분 tail을 버림 — "전체 행 학습"이라는 취지와 모순 | `train_end=None`으로 각 horizon이 **자기 라벨 행 전체**를 학습 |
| C4 | **MEDIUM** | `NaN`/`inf` 가중치가 `w < 0` / `sum <= 0` 검증을 모두 통과(NaN 비교는 항상 False) → 블렌드 확률이 조용히 NaN. **`from_dict` 역직렬화 경로**에도 동일 취약점 | `math.isfinite` 검사를 `fit_multi_horizon_ensemble`과 `MultiHorizonEnsembleAdapter.__post_init__` 양쪽에 추가 |

앵글 B/C(제거된 동작 + 크로스파일)는 **신규 correctness 버그 0건**. 유일한 후보였던 "prefix 진단 모델의 임계값을 refit 모델에 적용"은 `training.py:1201-1224`가 이미 쓰는 동일 패턴으로, 신규 결함이 아닌 기존 설계 트레이드오프로 확인.

## 26. 검증

```
전체 스위트         : 230 passed, 1 deselected (기존 parquet float32)
tests/test_review_items.py : 72 passed (신규 CompareBacktests 4종, MultiHorizonFinalRefit 4종)
ps1 ParseFile / bash -n / compare_backtests ast.parse : 통과
```

가중치 키잉 + 전체 커버리지 실증 (CatBoost 스텁):

```
horizons=(60,30), weights={60:0.9, 30:0.1}
  -> adapter.horizons=(30,60), weights=(0.1, 0.9)      # 0.1이 h30에 정확히 유지
  -> 각 horizon이 자기 라벨 행 1,201개 전부로 학습      # min-clipping 없음
```

엔드투엔드 레짐 인식 학습:

```
final_refit_requested: True | final_refit_all_sides: True
threshold_horizon: 60 | label_reach: 60
  up/long    : thr_fit=3,548  deployed_fit=4,436   refit=True
  down/short : thr_fit=4,690  deployed_fit=5,863   refit=True
  range/long : thr_fit=10,912 deployed_fit=13,641  refit=True
  range/short: thr_fit=10,912 deployed_fit=13,641  refit=True
```

## 27. 남은 항목

- **Phase 4 vs 4.5는 여전히 challenger 비교**다. 남는 차이: (a) horizon 블렌드, (b) Optuna 튜닝 유무, (c) 블렌드 확률의 캘리브레이션 의미론. 학습 데이터 비율(③)은 이번에 해소.
- **`--threshold-floor 0.45`** 가 학습 임계값을 덮어쓸 수 있다. 이제 `compare_backtests`가 자동 판정하므로 실행 후 그 리포트를 볼 것.
- **아티팩트 삭제는 수행하지 않았다.** 지운다면 `archive_full` / `metrics` / `btcusdt_2020_2025.parquet`는 보존하고 `regime_stacking_model`, `multi_horizon_model`, `backtest_results*`만 삭제.
- live 배선(K6/K7) 미착수.

---

# 7차 라운드: `project4_source_review_summary.md` 검토 및 수정 (2026-07-10)

## 28. 검토 문서 보완점 — 검증 결과

| # | 지적 | 판정 | 근거 |
|---|---|---|---|
| 1 | final refit 실패 시 파이프라인이 성공처럼 진행 | **CONFIRMED** | `_run_train_multi_horizon_regime_aware`가 실패와 무관하게 `return 0` |
| 2 | `compare_backtests`가 strategy config 전체를 비교하지 않음 | **CONFIRMED** | `COMPARABILITY_KEYS`에 `strategy`, `strategy_tp/sl_pct`, threshold override 부재 |
| 3 | compounded return reconciliation 검사 없음 | **CONFIRMED (불변식 검증됨)** | `equity_next = equity*(1+trade_return_pct)`이므로 `prod(1+r)-1 == net_total_return`. 켈리 on/off 모두 실측 오차 **1.06e-15** |
| 4 | stale `like-for-like` 문구 잔존 | **CONFIRMED** | ps1 21/398행, sh 19/340행 |
| 5 | ZIP에 `tests/` 미포함 | 패키징 이슈 (코드 아님) | 저장소에는 존재. 배포 ZIP 생성 시 포함 필요 |
| 6 | live `entry_quantity=0.001` | CONFIRMED | 미착수 |

### 문서가 놓친 것

`live.StrategyConfig.as_dict()`가 **`use_atr_pricing`을 빠뜨리고** 있었다. ATR 기반 배리어와 고정 플로어 배리어는 **완전히 다른 TP/SL로 체결**되는데, 두 설정이 아티팩트에서 동일하게 직렬화되고 있었다. `live.py`의 다른 소비처(`live.py:542`, `:2140`)에도 영향.

## 29. 수정 내역

| # | 파일 | 내용 |
|---|---|---|
| P1 | `cli.py` | **partial final-refit 게이트.** 요청한 refit이 일부 사이드에서 실패하면 실패한 `regime/side` 목록과 함께 **exit 1**. `--allow-partial-final-refit`으로 명시적 허용 가능(경고 2줄 출력). `--skip-final-refit`(의도적 생략)과 분리 |
| P2 | `cli.py` | 게이트를 **성공 배너보다 먼저** 실행 — stdout이 "complete"라 해놓고 stderr가 실패를 말하는 모순 제거. 진단용으로 아티팩트는 남기고, 위치를 stderr에 안내 |
| P3 | `cli.py` (backtest) | `final_refit_all_sides=false` 아티팩트를 로드하면 **경고**. 학습 터미널이 사라진 뒤에도 부분 refit 모델임을 알 수 있음 |
| P4 | `live.py` | `StrategyConfig.as_dict()`에 **`use_atr_pricing` 추가** |
| P5 | `backtest.py` | `run_config`에 `strategy`/`strategy_tp_pct`/`strategy_sl_pct` 대신 **`strategy_config = strategy.as_dict()`** 전체 기록 (ATR 배수, TP/SL 플로어, `use_atr_pricing` 포함) |
| P6 | `compare_backtests.py` | `COMPARABILITY_KEYS`에 `strategy_config`, `long/short_threshold_override` 추가. 사람이 읽는 헤더에도 strategy/atr_pricing/thresholds/overrides 출력 |
| P7 | `compare_backtests.py` | **reconciliation 검사** — `prod(1+trade_return_pct)-1` vs `net_total_return`. 불일치 시 "이 리포트의 모든 수치를 의심하라" 경고. 구버전 아티팩트(`trade_return_pct` 없음)는 건너뜀 |
| P8 | ps1/sh | stale `like-for-like challenger` → **regime-aligned multi-horizon challenger**(실행·라우팅은 공유하되 blend/tuning/calibration은 다름) |

## 30. 코드 리뷰에서 잡은 자체 결함

| # | 심각도 | 발견 | 수정 |
|---|---|---|---|
| Q1 | MEDIUM | 게이트가 아티팩트 기록 + "training complete" 배너 **뒤**에서 exit 1 → stdout/stderr 모순 | 게이트를 배너 앞으로 이동 (P2) |
| Q2 | MEDIUM | reconcile 허용오차 `abs_tol=1e-12`가 **손익분기 근처 대규모 런에서 오탐**. equity는 달러 공간, compounded는 단위 공간에서 누적돼 ~n·eps(50k 트레이드 ≈ 1.1e-11) 만큼 드리프트하는데, `net_total_return`이 작으면 `rel_tol`이 무력해지고 `abs_tol`이 드리프트보다 작아짐 | `abs_tol=1e-9`(수익률 1e-7%)로 상향 — 드리프트의 ~100배, 해석에 무의미한 크기. 오탐/진탐 양쪽 테스트 추가 |

Angle B/C(제거된 동작 + 크로스파일)는 **발견 0건**. 제거된 `run_config` 키의 소비자 없음, `as_dict()` 키 추가에 대한 정확 일치 단언 없음, `StrategyConfig`에 `from_dict` 없음(예상치 못한 kwarg 불가), 중첩 dict의 `!=` 비교는 순서 무관하며 `1 == 1.0`이라 JSON 왕복 오탐 없음, 두 스크립트 모두 Phase 3.5를 게이팅함을 확인.

## 31. 검증

```
전체 스위트 : 235 passed, 1 deselected (기존 parquet float32)
test_review_items + test_stacking_ensemble : 77 passed
ps1 ParseFile / bash -n : 통과
```

게이트 실증 (모델 팩토리 스텁, 배포 refit 1회 강제 실패):

```
기본                          -> "multi-horizon training failed: final refit failed for up/long..."  rc=1
                                 (성공 배너 출력되지 않음)
--allow-partial-final-refit   -> WARNING 2줄, rc=0, final_refit_all_sides=false
```

reconciliation 불변식 실측:

```
kelly=off  trades=62  compounded=+0.0054188246  net_total_return=+0.0054188246  |diff|=1.06e-15
kelly=on   trades=62  compounded=+0.0054188246  net_total_return=+0.0054188246  |diff|=1.06e-15
실제 아티팩트: "reconcile     OK (... diff 6.6e-17)"
```

provenance:

```
strategy_config keys: [atr_multiplier_sl, atr_multiplier_tp, long_threshold, min_reward_risk,
                       min_sl_floor_pct, min_tp_floor_pct, name, short_threshold, sl_pct,
                       tp_pct, use_atr_pricing]
```

## 32. 남은 항목

- **배포 ZIP에 `tests/` 포함** — 저장소에는 있으나 ZIP 생성 스크립트가 없어 수동 확인 필요.
- **Phase 4.5는 regime-aligned challenger** — 실행 조건과 레짐 라우팅은 Phase 4와 같지만 horizon 블렌드, base-model 튜닝(Optuna vs 기본), 확률 캘리브레이션 의미론은 여전히 다르다.
- **`--threshold-floor 0.45`** 가 학습 임계값을 덮어썼는지는 `compare_backtests`의 threshold 리포트로 확인.
- **아티팩트 삭제 미수행.** `archive_full` / `metrics` / `btcusdt_2020_2025.parquet` 보존, `regime_stacking_model` / `multi_horizon_model` / `backtest_results*`만 삭제 권장.
- live 배선(K6/K7) 미착수.
