# V6 분석 잔여 이슈 수정 보고 (2026-07-08)

기준 문서: `rulebased_regime_v6_analysis_summary.md`
이전 보고: `FIX_REPORT_V5_REMEDIATION.md`

v6 분석의 우선순위 1~5를 전부 반영했다. 신규 지적 2건(Sunday look-ahead,
external_sources 복제)은 수정 전 소스에서 실증한 뒤 고쳤다.

---

## 1순위: weekly feature Sunday look-ahead — 실증 후 수정 완료 (데이터 누수)

### 실증
pandas 3.0.2에서 직접 확인: `resample("W")`의 label은 일요일 00:00인데,
해당 행의 `last` close는 **일요일 23:59 봉의 close**다 (label − 실제 데이터
시각 = −23:59). 기존 매핑 `weekly_index <= ts`는 따라서:
- **매주 일요일 00:00~23:58 전 구간에서 그 주의 최종 close(및 그것으로 만든
  MA20/50, slope, drawdown, vol_contraction)를 최대 약 24시간 미리 노출**,
- 시리즈 끝이 주중이면 **부분 주(partial week)의 close도 일요일부터 노출**
  (truncation invariance 위반).

### 수정 (`weekly_features.py`)
- 주봉 행의 **가용 시점(available_at) = label + 1일 = 월요일 00:00**으로 이동.
  완결된 주의 close는 주가 끝난 다음 첫 봉부터만 선택 가능.
- 월~토 값은 수정 전과 동일(선택되는 행이 같음) — 일요일만 달라짐.
- 겸사겸사 per-minute 불리언 마스크 루프(O(분×주))를 `np.searchsorted`
  벡터화로 교체. NaN/기본값 의미는 스칼라 루프와 동일하게 보존
  (첫 가용 주 이전 0.0/vol_contraction 1.0, MA 윈도우 미충족 시 NaN 전파 —
  해당 행들은 기존 50주 warmup 필터가 어차피 제거).

### 검증 (`verify_weekly_causality.py`, 56주 합성 1분봉)
1. **Truncation invariance(누수 표준 검정)**: 일요일 정오에서 자른 prefix와
   전체 시리즈의 피처가 7종 전부 완전 일치 (NaN 포함) — 통과.
2. **일요일 동작**: 일요일 00:00~23:59 내내 이전 주 값 유지, 새 주 값은
   월요일 00:00부터 등장 — 통과.
3. **월~토 무변경**: 기존(label≤ts) 선택과 행 인덱스 동일 — 통과.

수정 전 코드로 같은 테스트를 돌리려 했으나 기존 루프가 56주 데이터에서
20분 내 완료 불가(v6 분석의 verify timeout 보고와 일치) — leak 메커니즘은
resample label 실증으로 증명됨.

### 성능 부수효과
6년 스케일(3,144,960봉)에서 `compute_weekly_features` **3.4초** (기존 루프는
동일 스케일에서 사실상 실행 불가 수준). 병렬 부모의 전체-시리즈 1회
선계산(v6 수정)과 결합해도 부담 없음.

### 영향
- 일요일 봉(전체의 1/7)의 weekly 7종이 미래 정보를 포함하고 있었으므로,
  **이전 백테스트/학습 결과는 일요일 구간에서 낙관 편향 가능**. 기존 feature
  캐시·모델은 폐기 후 재계산/재학습 필요.
- train/backtest/live 모두 같은 함수를 쓰므로 세 경로 일관 수정.

---

## 2순위: external_sources 전체 dict worker 복제 — 수정 완료 (메모리)

### 실증
`--metrics-dir` 사용 시 `external_sources[minute]["metrics"]`가 전 분(minute)
키로 생성(2020~2025 기준 ~315만 entry)되고, `_build_feature_rows_parallel`의
work item 13개 각각에 **전체 dict가 그대로 담겨 태스크마다 통째로 pickle**
되고 있었음. 워커의 소비는 `per_candle_external_sources.get(candle.open_time)`
— 자기 chunk 시각 외에는 절대 조회하지 않음을 확인.

### 수정 (`dataset.py`)
- datetime 키(per-candle) 형태일 때만: 부모에서 키를 1회 정렬 후, chunk의
  `[첫 봉, 마지막 봉]` 시각 범위로 `bisect` 슬라이스한 dict를 work item에 전달.
- 단일(str 키) 매핑은 소형이므로 그대로 통과. `external_sources=None`도 동일.

### 검증 (`verify_external_slicing.py`)
- 60,000봉 × 6 chunks, 전 분에 funding_rate를 넣은 per-candle external로
  **병렬(슬라이스) vs 직렬(전체 dict) 189개 피처 등가성** 비교.
- external 직결 피처(funding_rate/spread/spread_bps)는 **정확 일치** — chunk
  경계(10k/20k/.../59,999) 명시 프로브 포함 통과.
- 나머지 통계 피처는 허용오차 비교: 진단 과정에서 발견된 미세 차이는
  external 없이도 동일하게 재현되는 **기존(pre-existing) chunk↔직렬 부동소수점
  드리프트**(cumsum 재시작 + near-zero variance 취소오차)로, 이번 수정과 무관.
  극단 케이스(20봉 완전평탄 윈도우에서 zscore 0 vs ±10)는 합성 사인 가격의
  인공물이며 실데이터에서는 발생 조건이 없음. 별도 이슈로 기록만 해 둠.

---

## 3순위: `select_threshold()` 기본 objective → `trading_pnl` — 완료

함수 기본 인자와 docstring 갱신 (precision_recall은 legacy 항목으로 문서
유지). config 경유가 아닌 직접 호출(`select_threshold(probs, labels)`)도
이제 설계 의도와 일치. **v718 스위트의 실패 테스트 집합이 baseline과
이름 단위로 완전 동일**함을 diff로 확인 — 이 기본값 변경으로 결과가 뒤집힌
테스트 없음.

## 4순위: backtest CLI 기본 시작일 → `2025-01-01` — 완료

`--backtest-start` default를 2025-07-01(과거 H1 validation/H2 backtest 분할
시절)에서 2025-01-01(현행 full-year OOS)로 변경, help에 배경 명시.

## 5순위: 주석/requirement 잔여 정리 — 완료

- `run_full_pipeline.sh` Requirements: "regimes.json with your ..." →
  "classifier 모드에서만 필요" 문구로.
- `run_full_pipeline.ps1` Usage: "Edit ... your regimes.json" → rule 모드
  기본임을 반영.

---

## 테스트 결과 (수정 후 = baseline과 동일; 회귀 0)

| 검증 | 결과 |
|---|---|
| verify_weekly_causality.py (신규) | 3/3 OK — truncation invariance / Sunday / Mon–Sat 무변경 |
| verify_external_slicing.py (신규) | OK — 189 피처, external 직결 정확 일치 |
| verify_weekly_parallel_fix.py (v6) | OK — ndarray 반환 변경 후에도 global-index 정렬 유지 |
| tests.test_regime_rules | 15/15 OK |
| tests.test_core | 131, errors=7 (전부 pyarrow 미설치; baseline 동일) |
| tests.test_v718 | 159, failures=2 errors=14 — **실패 집합 baseline과 diff 완전 일치** |
| tests.test_stacking_ensemble | errors=1 (catboost 미설치; baseline 동일) |
| py_compile / bash -n | 전부 OK |
| weekly 6년 스케일 벤치 | 3,144,960봉 3.4s |

## 남은 사항 (코드 외)

- 6~8순위(v6 분석): pyarrow/catboost 환경에서 전체 테스트 재실행 및 stale
  기대값 갱신 → **feature 캐시/기존 모델 폐기** → 2025 full-year 백테스트
  재실행. Sunday leak 수정으로 결과가 이전 대비 보수적으로 나올 수 있음
  (특히 주말 구간 성과 귀속 확인 권장 — trade record의 `entry_regime`/요일
  분해).
- 기록용 별도 이슈: 병렬 chunk와 직렬 경로의 rolling 통계 미세 fp 드리프트
  (기존부터 존재; 학습에 유의미한 크기는 아니나, near-zero variance에서
  zscore 가드가 경로에 따라 0/클립값으로 갈리는 수치 경계 케이스 존재).
  원하면 rolling 통계를 chunk-로컬 재계산 대신 Welford/정확 윈도우 합으로
  통일하는 후속 작업 가능.
