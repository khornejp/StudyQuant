# 스케일 의존 피처 9종 비활성화 보고 (2026-07-08)

기준: `ohlcv_normalization_catboost_summary.md` 검토에서 실측 발견한
스케일 의존 피처에 대한 사용자 결정("학습에 저하되는 피처는 제거").
이전 보고: `FIX_REPORT_V9_REMEDIATION.md`

---

## 제거 대상과 사유

| 피처 | 문제 | 유지되는 대체재 |
|---|---|---|
| rolling_vwap_20 / rolling_vwap_60 | 달러 원가격(클리퍼 "price" ±1e6 통과) → 연도 프록시 | price_vs_rolling_vwap_20/60, vwap_deviation_zscore |
| range_high_20 / range_low_20 / range_mid_20 | 달러 원가격(동일) | range_position_20, distance_to_range_high/low, distance_to_high/low_20 |
| macd_line / macd_signal / macd_hist | 달러 스케일 EMA 차 → 기본 "ratio" ±100 클립. 같은 %움직임이 고가격 구간에서만 포화 → 정보 소실 + 시대 누출 동시 발생 | ema_12_26_spread ((EMA12−EMA26)/close = 정규화 MACD line) |
| quote_volume_per_trade | 거래당 달러(수백~수만$)가 ±100에 상시 포화 → 사실상 상수 | volume_per_trade (BTC 단위, 포화 없음) |

활성 피처: **189 → 180**.

## 구현 방식 (최소침습)

1. **registry 게이팅 확장** (`feature_registry.py`):
   `INACTIVE_SCAFFOLD_STATUSES = {"pending_data_source",
   "disabled_scale_dependent"}` 신설, `active_feature_names`가 이 집합
   기준으로 필터. F11(depth)의 기존 의미는 그대로 보존.
2. 9종 정의에 `scaffold_status="disabled_scale_dependent"` + 피처별 사유
   주석. 정의 자체는 registry에 남아 provenance/문서 유지.
3. **계산은 유지** (`dataset.py` 무변경 + 의도 주석): rolling_vwap_*,
   range_high/low_20, macd_line/signal은 **활성 상대 피처의 입력**
   (vwap_deviation_zscore, price_vs_rolling_vwap_*, range_position_20,
   distance_to_range_*)이므로 내부 계산은 그대로 두고,
   `FeatureVector.from_mapping`의 "extra names are ignored" 규약으로
   모델/아티팩트/parity 표면에서만 제외. 상대 피처 값은 1비트도 변하지
   않음(아래 테스트로 검증).
4. train/backtest/live가 모두 registry의 `active_feature_names` 단일
   소스를 쓰므로 세 경로 자동 일치 — parity 검증도 같은 목록을 비교.

## 검증

**신규 `tests/test_feature_deactivation.py` — 5/5 OK:**
1. 9종이 active_feature_names에 없음.
2. 8개 상대 대체재는 전부 활성.
3. registry 정의는 9종 모두 `disabled_scale_dependent` 상태로 문서 유지.
4. 빌드된 row에서 9종 접근 시 KeyError·부재, 대체재는 존재하며
   **내부 유지 계산으로부터 정확한 값**(range_position_20=0.5,
   distance_to_range_high=100/110−1) 산출 확인.
5. FeatureVector 폭 == 활성 registry 크기(180).

**기대값 갱신(의도적 변경에 따른 것, 3곳):**
- `tests/test_core.py::test_feature_registry_all_features_active`:
  활성 집합 = 전체 − pending(F11 7종) − scale-disabled(9종)로 갱신,
  9종 상태의 정확성 및 대체재 활성까지 assert 강화.
- `tests/test_v718.py::test_feature_names_matches_active_registry`:
  하드코딩된 `!= "pending_data_source"` 판정을 registry의
  `INACTIVE_SCAFFOLD_STATUSES` 단일 소스로 교체(재발 방지).
- `tests/test_v718.py::TestRangeMeanReversionFeatures`:
  raw range_high/low_20 값 검증 → "모델 표면에서 제외" assert +
  상대 피처(distance_to_range_high/low) 값 검증으로 전환.

**회귀:**
| 스위트 | 결과 |
|---|---|
| test_feature_deactivation (신규) | 5/5 OK |
| test_regime_rules / test_optuna_best_iteration | 21/21 OK |
| test_core | errors=7 (전부 pyarrow 환경; baseline 동일), 갱신 테스트 통과 |
| test_v718 | 실패 16건 — **이름 단위로 baseline과 완전 일치** (클래스별 취합 대조). warmup 테스트의 ERROR는 baseline에서도 동일한 BrokenProcessPool(컨테이너 리소스)임을 원인까지 대조 확인 |

(참고: 이번 세션 후반 컨테이너가 현저히 느려져 v718 전체 1-shot 실행이
불가해 클래스 단위로 분할 실행·취합했다. 클래스별 합산 시간은 이전 전체
실행과 동일 — 코드 성능 회귀 아님.)

## 영향과 재실행

- **모델 입력이 바뀌므로 기존 모델 아티팩트는 무효** — v9 재실행 안내와
  동일하게 `artifacts/regime_stacking_model/`, `artifacts/backtest_results/`
  삭제 후 `run_full_pipeline.ps1` 실행. candles parquet/metrics 재사용.
- ablation 관점: 이번 제거는 문서 §8의 실험 D(raw 제거) 방향을 기본값으로
  채택한 것. 재실행 결과가 이전 대비 악화되면 되돌릴 수 있도록 9종은
  registry에 정의가 남아 있어 `scaffold_status`만 바꾸면 즉시 복원 가능.
- macd_hist의 정규화 버전((line−signal)/close)은 현재 부재 — 재실행 후
  importance에서 ema_12_26_spread가 상위권이면 추가 검토 가치 있음.
- live parity: 세 경로가 registry 단일 소스를 공유하므로 추가 작업 없음.
  (기존 TODO의 live warmup/backfill·F16 실시간 주입 점검은 여전히 별건.)

---

# 추록: v11 분석의 registry metadata 불일치 수정 (같은 날)

기준: `rulebased_regime_v11_feature_deactivation_analysis_summary.md` §6~7, §12.

## 확인된 실체
`dataset.FEATURE_NAMES`는 180이지만
`feature_formula_registry()["active_feature_names"]`는 189 — 재현 확인.
원인: `registry_from_feature_rows()`의 metadata 생성이 여전히
`!= "pending_data_source"` 단일 조건 사용(v11에서 이 경로를 놓침).
낡은 조건은 이 한 곳뿐임을 전수 grep으로 확인.

## 수정 (분석 §7.1의 helper 방식)
- **`_is_active_status(status)` 단일 판정 함수 신설**: 누락/None status는
  "implemented"(활성) 취급 — FeatureDefinition 기본값과 일치.
- `active_feature_names()`(dataclass 경로)와
  `registry_from_feature_rows()`(row-dict/artifact metadata 경로)가 **같은
  판정을 공유** → 두 경로가 다시 어긋날 수 없는 구조.

## 검증 (분석 §12의 2~4)
- `test_registry_metadata_active_names_tuple_equal_feature_names`:
  metadata와 FEATURE_NAMES의 **tuple 비교**(이름+순서) — 통과.
- `test_registry_metadata_excludes_scale_disabled`: 9종 부재 + F11 depth
  (spread_bps) 부재까지 확인 — 통과.
- `test_registry_from_feature_rows_uses_shared_predicate`: row-dict 경로에서
  두 비활성 상태 모두 제외되고, status 누락 row는 활성 취급 — 통과.
- 회귀: test_feature_deactivation 8/8, regime_rules+optuna 21/21,
  v718 FeatureRegistry registry-match·Range 클래스 통과,
  test_core errors=7(전부 pyarrow, baseline 동일). metadata 필드의 코드 내
  소비처는 없음(grep 확인 — 위험 표면은 JSON artifact/외부 해석뿐).

재실행 안내는 본문과 동일: 이 수정은 metadata만 바꾸므로 모델 무효화
사유가 추가되지는 않으나, 어차피 v11 피처 변경으로 재학습이 예정돼 있어
그 한 번에 함께 반영된다.
