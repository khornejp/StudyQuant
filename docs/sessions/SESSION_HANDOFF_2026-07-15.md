# 세션 핸드오프 — 2026-07-15

계측 계층(metric/JSON/배리어)을 전부 고친 뒤, 재학습된 모델을 캘리브레이션으로
진단한 세션. **결론: 시스템은 이제 정직하고, 모델에는 실거래 가능한 alpha가 없다.**

이전 세션(2026-07-14) 핸드오프의 §7 미해결 과제를 대부분 처리했다. 다음 세션은
**feature 예측력 조사**(근본 문제)부터 시작하면 된다.

---

## 0. 한 줄 요약

지난 세션까지는 계측이 깨져서 "모델이 거짓말하는가 vs edge가 없는가"를 구분조차
못 했다. 이번에 계측을 전부 고쳐(유효 JSON · 배리어 parity · 정직한 확률 · 무의미한
비교 거부) 이제 명확히 판정된다 — **edge가 없다.** 문제의 성격이 "실행/계측"에서
"진짜 신호"로 이동했다.

---

## 1. 이번 세션에 한 일 (커밋 6개, 전부 로컬 · 미푸시)

브랜치 `fix/barrier-parity-and-metric-guards`, `origin`보다 **6 커밋 앞섬**.

| 커밋 | 내용 | 이전 §참조 |
|---|---|---|
| `c8d6133` | 유효 JSON 요약: 비유한 metric을 `null`로 직렬화(`backtest.json_safe`), `compare_backtests` 빈 슬라이스 NaN, 중복 상수/공식 제거 | §7.2 |
| `08c62f1` | 캘리브레이션 리포트: `calibration.py` + `verify_calibration.py`, `risk.breakeven_probability`, 파이프라인 Phase 4.3 | §7.1 |
| `fdc0b65` | 무의미한 strategy_comparison 거부: 프로파일 지문이 겹치면 1개만 실행하고 이유 기록 | §7.4 |
| `740a4a8` | 코드 리뷰 수정: 캘리브레이션이 틀린 horizon·틀린 봉을 채점하던 2건 + 부수 정리 | (리뷰) |
| `ac8cc2f` | **배리어 기록 버그**: `run_regime_aware_training`이 `regime_run_summary.json`에 tp_pct/sl_pct/threshold_horizon을 안 씀 | §7 신규 |
| `8c43687` | 같은 버그가 multi-horizon regime 경로(`cli.py`)에도 있어 수정 | (리뷰) |

### 1.1 계측 수정의 핵심 (§7.2, §7.4)

- `backtest.json_safe()`: NaN/inf → `null`. **undefined metric은 오류가 아니라
  "답 없음"이라는 진짜 결과**(거래<20, 분산 0, 손실 거래 없음)이므로 0.0으로
  접으면 성과처럼 읽힌다. `backtest_summary` · `multi_horizon_summary` ·
  `regime_run_summary` 세 곳 모두 적용. 소비자(ps1/sh 요약, compare_backtests)도
  `null` → "n/a" 출력으로 수정(sh는 원래 `f"{None:.3f}"`로 크래시했음).
- `compare_backtests`: 빈 슬라이스 profit_factor/win_rate가 0.0(=최악값)으로
  읽히던 것 → NaN. per-trade Sharpe는 `backtest.per_trade_sharpe`를 import(중복 제거).
- `strategy_comparison`: aggressive/balanced/conservative가 regime-aware+exec
  배리어 실행에서 배리어(exec flag)·임계값(학습값)·min_reward_risk(백테스트 미사용)
  전부 덮여 **구분 불가**. 이제 지문이 겹치면 1개만 돌리고 `best_strategy=null`,
  `indistinguishable_profiles=true`, 이유를 기록.

### 1.2 캘리브레이션 도구 (§7.1)

`btcusdt_quant/calibration.py`(순수 지표) + `verify_calibration.py`(아티팩트 구동).
핵심은 **decision band** — 학습된 임계값 위, 즉 실제 진입 가능 봉에서만 실현 승률이
배리어의 손익분기(`risk.breakeven_probability`)를 넘는지 판정.

리뷰가 잡은 2가지 실버그를 고침(커밋 `740a4a8`):
- `--horizon`을 검증 안 하던 것 → 아티팩트의 `threshold_horizon`과 불일치 시 거부.
- decision band가 direction policy·range mean-reversion 게이트를 무시하고 **모든**
  봉을 세던 것 → **진입 가능 봉만** 세도록 게이트. (range/long: 21,777 priced →
  5,514 enterable → band n 2,862→397. 7배 과다 계측이었음.)

`reliability_curve`는 등폭(equal-width) bin — 등질량이면 0.52 근처에 압축된 확률
밴드를 모든 버킷에 퍼뜨려 병리를 숨긴다. ECE는 `MIN_BIN_SAMPLES`(20) 미만 bin 제외.

### 1.3 배리어 기록 버그 (신규, 가장 중요)

`run_regime_aware_training`이 live가 읽는 `regime_run_summary.json`에 **모델이
라벨링된 배리어를 안 적었다.** 그래서 `load_regime_aware_models`가
`label_tp_pct=None`을 읽었고, 지난 세션이 추가한 배리어 parity 가드가
**구조적으로 발동 불가**("pre-parity artifact" 경고만)했다. 재학습된 모델이
`tp_pct: null`로 나온 게 정확히 이 이유. multi-horizon regime 경로에도 같은 버그.

수정: `tp_pct`/`sl_pct` ← `training_config`, `threshold_horizon` ← `build.label_horizon`.
전부 live가 이미 읽던 키 — 쓰는 쪽만 빠져 있었다.

---

## 2. 파이프라인 재학습 결과 (2025 OOS, 525,600봉)

`run_full_pipeline.ps1`이 세션 시작 시(어제 코드 `b6eceb8`) 이미 돌고 있었고
정상 완료. 산출물: `artifacts/regime_stacking_model`, `artifacts/backtest_results`,
`artifacts/multi_horizon_model`, `artifacts/backtest_results_multi_horizon`.

### 2.1 백테스트 헤드라인 (regime model)

| 지표 | 값 |
|---|---|
| 거래 수 | 26 |
| 승률 | 38.46% (손익분기 38.67% → **0.21%p 미달**) |
| Net 수익률 | −0.12% |
| Net Sharpe | −0.07 |
| Profit factor | 0.86 |
| 거래 분포 | **26건 전부 range** (up/down 0건) |

배리어는 정확히 실행됨(TP 8 / SL 16 / TIMEOUT 2, net +0.92% / −0.58%).
멀티호라이즌(Phase 4.5)은 더 나빴음(11거래, 승률 18.2%, net −0.29%).

**주의: 26건은 통계적으로 무의미.** 흑자 월은 2월(2건)·11월(2건)뿐, 5~10·12월 0거래.

---

## 3. 캘리브레이션 진단 (이 세션의 핵심 결과)

배리어 백필(아래 §4) 후 실제 모델에 `verify_calibration.py`를 돌린 결과.
리포트: `artifacts/backtest_results/calibration_report.json`.

### 3.1 캘리브레이션은 이제 정직하다 (이전 세션과 정반대)

지난 세션 병리("P=0.52인데 실현 16.7%")가 사라짐. ECE 전부 0.03 미만:

| regime/side | ECE | 평균 예측확률 | 진입구간 승률 | break-even 대비 |
|---|---|---|---|---|
| up/long | 0.027 | 0.064 | 7.1% | **−31.6%** |
| range/long | 0.011 | 0.046 | 19.8% | −18.9% |
| range/short | 0.005 | 0.035 | 25.0% | −13.7% |
| down/short | 0.014 | 0.141 | 28.9% | −9.8% |

모델이 "5% 확률"이라 하면 실제 ~5% 발생. **확률이 정직하다.**

### 3.2 확률 분포가 극도로 낮게 압축됨 → up/down 침묵의 원인

- up/long: 봉의 84%가 P<0.1, **P≥0.3인 봉이 1년간 0개.**
- 학습 임계값이 0.12~0.30으로 낮은 이유 = 확률이 이렇게 낮으니 그 아래로 안 내리면
  거래가 아예 없음.
- **up/down 0건 메커니즘**: up/long은 P가 너무 낮아 Kelly expected_edge가 전부
  음수→진입 0. down/short은 P≥0.3이 640봉 있으나 실현 28%로 break-even 미달→Kelly
  거부→0. range만 봉이 압도적(47.8만)이라 극소수가 게이트 통과해 26건(그것도 손실).

### 3.3 "고확신만 진입" 시나리오도 실패

임계값을 높여 확신 높은 봉만 잡아도(bin 데이터로 계산):

| regime/side | P≥0.4 | P≥0.5 |
|---|---|---|
| up/long | 0봉 | 0봉 |
| down/short | 0봉 | 0봉 |
| range/long | 549봉 33% (미달) | **72봉 44% (넘지만 표본 무의미)** |
| range/short | 23봉 48% | 0봉 |

배리어(1%/0.5%, break-even 38.67%)를 넘기려면 P>0.4를 자신 있게 매기는 봉이 충분히
많아야 하는데, 그런 봉이 연간 수십 개 수준으로 극히 희소하다.

### 3.4 결론

**모델에 실거래 가능한 alpha가 없다.** 계측·실행 버그가 아니라 **예측력 부족.**
확률이 정직하게 "대부분의 봉에서 이 배리어에 도달할 확률은 낮다"고 말하고 그게 사실.
threshold 튜닝·배리어 재조정으로 해결 안 됨 → **더 나은 feature/신호가 필요.**

---

## 4. 아티팩트 배리어 백필 (재학습 없이)

재학습(12h)을 피하려고 기존 아티팩트에 배리어를 손으로 추가함. 값은 학습 명령줄에서
확인(`--tp-pct 0.010 --sl-pct 0.005 --horizon 60`).

- `artifacts/regime_stacking_model/regime_run_summary.json`에 tp_pct/sl_pct/
  threshold_horizon 추가. 원본은 `.bak`으로 백업. (`_barrier_backfilled` 마커 남김.)
- 검증: 로드가 `label_tp_pct=0.01`을 읽고 parity 가드가 경고→검증으로 전환.
- `multi_horizon_model`은 이미 배리어가 있어 백필 불필요(provenance 병합으로 들어가
  있었음). 로드도 정상(`label_tp_pct=0.01`).
- **다음 재학습부터는 코드(`ac8cc2f`)가 자동 기록**하므로 백필 불필요.

---

## 5. 다음 세션에서 할 일 (우선순위)

### 5.1 feature 예측력 조사 (근본 문제 — 최우선)

진단이 "edge 없음"으로 나왔으니, 이제 물어야 할 질문: **어떤 feature가 실제로
예측력을 갖는가?** `ic_diagnostic.py`(Spearman IC per feature/horizon, fold-wise
mean/std, leakage 휴리스틱)로 현재 feature set의 IC를 보고, 확률이 0.05 근처에
압축되는 원인이 feature 부재인지 라벨 난이도(1%/0.5% 배리어가 1분봉엔 과한지)인지
판별. 압축이 배리어 탓이면 더 짧은 horizon·작은 배리어로 라벨 재설계 검토.

### 5.2 `mean_test_*: 0.0` 하드코딩 (리뷰 미수정)

`training.py`의 `run_regime_aware_training` run_summary에서
`mean_test_accuracy`/`ece`/`brier`가 **0.0 리터럴**(mean_test_f1만 실제값).
재학습 모델의 검증 지표가 전부 0으로 읽히는 원인. `test_period_evaluation`과
단일 regime holdout(`training.py:1339`)에 실제 값이 있으니 반영하거나 필드 삭제.
(line ~835, 커밋 `ac8cc2f`가 건드린 dict 바로 아래.)

### 5.3 기존 테스트 실패 6건 (§7.3 — 이제 GPU 안전)

학습이 안 도니 pytest를 안전하게 돌릴 수 있음(아래 §6 GPU 주의). 특히
`test_v718.py`의 5건(regime detector 지속성, live 폴백, E2E 파이프라인)이 핵심 경로.
E2E(`test_cli_collect_train_live_pipeline`)는 `training.py:259` split 구성 단계에서
"not enough labeled rows"로 실패 — 데이터/split 문제이지 배리어와 무관.

### 5.4 (선택) 멀티호라이즌 백테스트 재실행

`multi_horizon_model`은 이제 배리어가 있으니, 재백테스트하면 parity 경고가 사라지고
`backtest_results_multi_horizon`이 정상 검증됨. 진단 목적이면 §4처럼 캘리브레이션도
가능.

---

## 6. 주의사항 / 함정

### 6.1 GPU 데드락 (변함없음)

`models.py:169`에 `task_type: "GPU"` 하드코딩. **pytest 여러 개 동시 실행 시**
CatBoost가 GPU를 서로 굶겨 `_train`에서 데드락. **테스트는 한 번에 하나만.**
hang 확인: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`.

### 6.2 병렬 feature 계산 + 학습 병행 위험

`dataset.build_feature_rows`는 5만 봉 초과 시 process pool(8 workers)을 쓴다.
학습이 도는 중에 백테스트/캘리브레이션을 병행하면 메모리 경합으로
`BrokenProcessPool`이 날 수 있다(이 세션에서 45k 픽스처를 만들 때 60k에서 겪음).
학습 완료 후 단독 실행이면 문제없음(캘리브레이션은 3.15M봉을 정상 처리).

### 6.3 파이프라인 스크립트는 실행 중 변경이 반영 안 됨

PowerShell/bash는 스크립트 전체를 파싱해 실행하므로, 도는 중에 파일을 고쳐도
그 인스턴스엔 반영 안 됨. Python 모듈은 각 Phase가 새 프로세스라 반영됨.
→ 이번에 추가한 Phase 4.3(캘리브레이션)은 **다음 파이프라인 실행부터** 자동 실행.

---

## 7. Git 상태

- 브랜치 `fix/barrier-parity-and-metric-guards`, `origin`보다 **6 커밋 앞섬(미푸시)**.
- **`main` 미머지** — 배리어 변경이 기존(구 배리어) 아티팩트를 못 쓰게 만듦.
- 테스트: `test_review_items.py`(139) · `test_calibration.py`(22, 신규) · 배리어
  라운드트립 2건(`test_v718.py`) 통과. 기존 실패 6건은 §5.3.
- `artifacts/`는 `.gitignore` — 재학습 산출물·백필·캘리브레이션 리포트 모두 미커밋.
