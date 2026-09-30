# V7 분석 잔여 이슈 수정 보고 (2026-07-08)

기준 문서: `rulebased_regime_v7_analysis_summary.md`
이전 보고: `FIX_REPORT_V6_REMEDIATION.md`

v7 분석의 우선순위 1~7을 전부 반영했다. 핵심 지적(metrics parity)은 수정 전
소스에서 실증했고, skew의 실재 여부까지 검증 스크립트로 증명했다.

---

## 1~2순위: backtest `--metrics-dir` + feature 생성 배선 — 수정 완료 (핵심)

### 확인된 실체
- `--metrics-dir`는 **train 파서에만** 존재. backtest 디스패치는
  `dataset.build_feature_rows(candles, user_regime_periods=...)`를
  external_sources 없이 호출 → **학습은 F16 metrics 11종 실값, 백테스트는
  전부 0.0**. 메인 파이프라인이 train에 `--metrics-dir $MetricsDir`를 넘기고
  있으므로(Phase 2 metrics 수집 → Phase 3 학습) 현행 기본 실행이 정확히 이
  skew를 밟는다.

### 수정 (`cli.py`)
- **공유 헬퍼 `merge_metrics_external_sources()` 신설**: 기존 train 디스패치의
  인라인 merge 블록(load zips → causal 5m features → 1m forward-fill →
  `external_sources[minute]["metrics"]`)을 함수로 추출. train과 backtest가
  **같은 코드**를 쓰므로 parity가 구조적으로 보장(by construction). 정렬된
  metrics가 0건이면 경고 출력.
- backtest 파서에 `--metrics-dir` 추가(help에 skew 배경 명시).
- backtest 디스패치: `--metrics-dir` 지정 시 헬퍼로 external을 구성해
  `build_feature_rows(..., external_sources=...)`로 전달. 이후
  `compare_strategies`/`run_backtest`는 이 shared feature rows를 그대로 사용.
- v7에서 수정한 병렬 external 슬라이싱이 이 경로에 그대로 적용됨(315만 분
  metrics dict도 chunk 범위만 워커로 감).

## 3순위: run_full_pipeline Phase 4 — 완료
ps1/sh 백테스트 호출에 `--metrics-dir $MetricsDir` / `"$METRICS_DIR"` 추가.
기본 실행에서 train↔backtest metrics 조건이 자동 일치.

## 4순위: tp_sl_sweep — 완료
ps1/sh에 `MetricsDir`(기본 `artifacts/metrics`, 메인 파이프라인과 동일) 노브
추가. **디렉토리에 zip이 있을 때만** train·backtest 양쪽에 동일하게
`--metrics-dir` 전달(조건부 플래그 — metrics 없이 sweep하는 사용도 유지).
어느 한쪽에만 들어가는 조합은 스크립트 구조상 불가능.

## 5순위: parity 검증 스크립트 — `verify_metrics_parity.py` 신설, 4/4 통과
합성 Binance 포맷 metrics zip(5m 그리드, 일별) + 합성 1분봉으로 end-to-end:
1. **NON-ZERO**: metrics 존재 시 F16 11종 전부 warmup 이후 non-zero — 통과.
2. **ZERO-DEGRADE**: metrics 없이 빌드하면 같은 피처가 정확히 0.0 —
   **v7 분석이 경고한 skew가 실재함을 증명**. 통과.
3. **TRAIN==BACKTEST**: 공유 헬퍼 경유 두 경로의 feature 벡터가 이름
   순서·값까지 전 timestamp 동일 — 통과.
4. **PARALLEL==SERIAL**: 60k봉/6 chunks에서 metrics external이 chunk 경계
   포함 정확 일치(v7 슬라이싱과의 상호작용 검증) — 통과.

추가로 실제 CLI end-to-end 스모크: 합성 CSV + metrics zip으로
`backtest --metrics-dir ...` 실행 → "Loaded metrics: 576 rows -> 2880
aligned minutes" 로그와 정상 완료 확인.

## 6순위: ps1 주석 — 완료
`$RegimeFile = "regimes.json"` 주석을 "only used when
$RegimeMode=\"classifier\""로 교체.

## 7순위: mixed-key 방어 — 완료
`_external_slice`의 정렬을 `isinstance(key, datetime)` 필터 후 수행 —
datetime/str 혼합 매핑에서 `sorted()` TypeError 가능성 제거. 워커는 candle
open_time만 조회하므로 non-datetime 키는 슬라이스에 불필요.

---

## 테스트 결과 (회귀 0)

| 검증 | 결과 |
|---|---|
| verify_metrics_parity.py (신규) | 4/4 OK |
| CLI 스모크: backtest --metrics-dir | OK (metrics 로드 로그 + 정상 완료) |
| verify_weekly_causality.py | 3/3 OK |
| verify_external_slicing.py | OK |
| verify_weekly_parallel_fix.py | OK |
| tests.test_regime_rules | 15/15 OK |
| tests.test_core | 131, errors=7 (pyarrow 미설치; baseline 동일) |
| tests.test_v718 | **실패 집합 baseline과 diff 완전 일치** |
| py_compile / bash -n | 전부 OK |

## 재실행 시 주의

1. **기존 모델·feature 캐시 폐기 필수** — 이번(metrics parity) + 직전
   (Sunday leak) 수정이 모두 feature 값을 바꾼다. candles parquet과 metrics
   zip 아카이브는 재사용 가능.
2. metrics parity는 결과를 어느 방향으로도 움직일 수 있음: 학습 때 F16을
   중요하게 쓴 모델이라면 이전 백테스트의 확률 분포 자체가 왜곡돼 있었으므로,
   threshold·trade_count·regime별 귀속을 전부 새 기준으로 다시 읽어야 함.
3. **live parity는 별도 확인 필요(범위 외)**: backtest는 이제 metrics를
   받지만, live 경로가 동일한 F16을 실시간 주입하는지는 v7 분석 범위(live
   제외)에 없었음. 실전 배포 전 live의 metrics 소스 배선(기존
   TODO의 warmup/backfill 항목과 함께) 점검 권장.
