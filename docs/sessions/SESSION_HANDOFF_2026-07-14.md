# 세션 핸드오프 — 2026-07-14

백테스트 결과 분석 → 근본 원인 수정 → 커밋/푸시까지 완료한 세션의 기록.
다음 세션은 **파이프라인 재학습**부터 시작하면 된다.

---

## 1. 발단: 아티팩트 결과가 전부 가짜였다

`artifacts/backtest_results_multi_horizon/backtest_summary.json` (2025년 1년, 525,600봉):

| 지표 | 값 |
|---|---|
| 거래 수 | 31 |
| 승률 | 32.3% |
| Net 수익률 | **-0.25%** |
| Sharpe | -0.45 |
| Profit factor | 0.39 |
| Kelly "edge 없음" 스킵 | 112 / 143 (78%) |

이전 실행(`artifacts/backtest_results/`)은 더 심각했다. 거래 2건, 승률 100%,
**Sharpe 1.08e14**, PF `Infinity`, MDD 0. 성과가 아니라 계산 붕괴였다.

---

## 2. 근본 원인 (5가지, 전부 수정 완료)

### 2.1 배리어 경제성 — 비용이 손익비를 파괴 (최우선)

TP 0.30% / SL 0.15%, 왕복 비용 0.08%:

- Net TP = **+0.22%**, Net SL = **-0.23%**
- 명목 손익비 2.0:1 → **실효 0.96:1** (사실상 1:1)
- 손익분기 승률: gross 33.3% → **net 51.1%**
- 거래당 기대값: **-8.5bp**

승률 51%를 넘겨야 본전인 구조였다. 모델 실현 승률은 32.3%. **임계값을 어떻게
튜닝해도 수익이 날 수 없었다.**

→ 배리어를 **1.00% / 0.50%** 로 변경. Net +0.92% / -0.58% (1.59:1),
손익분기 승률 **38.7%**.

### 2.2 train/serve 배리어 불일치가 탐지 불가능했다

모델은 "라벨링된 배리어" 하나에만 답한다(`P(TP before SL)`). 그런데 백테스트는
다른 배리어를 태연히 실행했고, 아무 에러도 없이 무의미한 숫자를 냈다.

### 2.3 Sharpe가 float 노이즈로 나눗셈

`_per_trade_sharpe`의 `std > 0` 가드가 부실했다. TP로 똑같이 닫힌 거래 2건은
std가 ~1e-18이라 이 가드를 통과했고, 옛 공식이 아티팩트의
`108220898565759.67`을 **소수점까지 정확히 재현**했다. 원인 확정.

`training._calmar`도 같은 `== 0` 결함. 게다가 calmar는 `select_threshold`
정렬 튜플의 **첫 번째** 키라 sharpe보다 순위가 높다.

### 2.4 NaN이 승급 게이트를 fail-open으로 통과

`features._optional_float`가 NaN을 정상 float로 통과시켰고, 모든 게이트가
`elif value < limit` 형태라 **NaN이면 조건이 False → 거부 사유가 안 붙는다**.
Sharpe·MDD·Calmar·flip-rate 6곳 전부 해당.

### 2.5 `threshold_floor = 0.45`가 range 레짐을 통째로 차단

range의 학습된 임계값 0.348/0.358이 floor 0.45에 덮여, **2025년 봉의 91%
(478,738봉)에서 거래 0건**. 31건 전부 up/down에서만 나왔다.

---

## 3. 적용한 수정 (커밋 `d9591ed`)

| 파일 | 내용 |
|---|---|
| `dataset.py` | `DEFAULT_LABEL_TP_PCT = 0.010`, `DEFAULT_LABEL_SL_PCT = 0.005` — 배리어 **단일 출처** |
| `live.py` | `RegimeModelBundle`이 `label_tp_pct/label_sl_pct`를 운반 (`regime_run_summary.json`에서 읽음) |
| `backtest.py` | `check_execution_barrier_parity()` — 배리어 불일치 시 **`ValueError`로 거부**. `_MIN_RETURN_STD`, `MIN_TRADES_FOR_RISK_METRICS = 20` |
| `training.py` | `_sharpe`/`_calmar`에 float-noise 가드 (`_MIN_PNL_STD`, `_MIN_PNL_MDD`). NaN이 아니라 **0.0으로 접음** — `max()` 정렬 키라서 |
| `features.py` | `_optional_float`가 비유한 값 → `None` (게이트 6곳 한 번에 수정) |
| `cli.py` | 배리어 기본값 + `--allow-barrier-mismatch` 탈출구 |
| `run_full_pipeline.{ps1,sh}` | `LabelTpPct=0.010`, `LabelSlPct=0.005`, `ThresholdFloor=0.0` |

### 검증 (실제 아티팩트 대상)

```
label_tp_pct = 0.003  label_sl_pct = 0.0015
GUARD FIRED: execution barrier does not match the barrier the models
were trained on (tp_pct: labeled 0.003, executing 0.01; ...)
```

**즉 지금 상태에서 기존 `artifacts/` 모델로는 백테스트가 실행되지 않는다.
의도한 동작이다.**

---

## 4. 테스트 상태

전체 스위트(깨끗한 환경): **417 통과, 6 실패, 1 스킵** (39분 36초)

6건 실패는 **제 변경을 stash로 되돌려도 동일하게 실패** → 전부 기존 결함.

```
tests/test_core.py::TestDatasetCacheParquet::test_parquet_round_trip_preserves_rows
tests/test_v718.py::FeatureRegistryV718Tests::test_warmup_invalidation_strict_for_all_features
tests/test_v718.py::TestRegimeDetector::test_live_loads_detector_thresholds
tests/test_v718.py::TestRegimeDetector::test_training_persists_detector
tests/test_v718.py::TestRegimeTraining::test_live_fallback_to_default
tests/test_v718.py::E2ECLIV718Tests::test_cli_collect_train_live_pipeline
```

`tests/test_review_items.py`는 신규 8건 포함 **100개 전부 통과**.

### ⚠️ 함정: GPU 데드락

`models.py:169`에 `task_type: "GPU"`가 하드코딩돼 있다. **pytest를 여러 개
동시에 띄우면** 각각 CatBoost로 GPU 메모리를 잡고 서로를 굶겨 `_train` 안에서
데드락에 빠진다. 이번 세션에서 좀비 9개가 쌓여 20시간 hang했다.

→ **테스트는 한 번에 하나만 실행할 것.** hang이 보이면:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId, CommandLine
```
로 확인하고 정리. 정상이면 `run_train`은 130초에 끝난다.

---

## 5. Git 상태

- 브랜치 **`fix/barrier-parity-and-metric-guards`** → `origin` 푸시 완료 (커밋 `d9591ed`, 56파일)
- PR 링크: https://github.com/khornejp/StudyQuant/pull/new/fix/barrier-parity-and-metric-guards
- **`main`에는 머지하지 않음** — 배리어 변경이 기존 아티팩트를 쓸 수 없게 만들기 때문
- 커밋에는 이전 세션들의 미커밋 변경분도 함께 포함됨 (`ensemble.py`, `models.py`, `risk.py`, `ic_diagnostic.py`, 리뷰 문서 다수)
- `.gitignore`에 추가: `*.zip`, `catboost_info/`, `.omo/`, `test_results*.txt`
- `.claude/skills/btcusdt-quant-code/` 커밋됨 → **새 세션에서 자동 로드된다**
- `git stash list`에 이번 세션과 무관한 stash 하나 있음 (`ca3509a` 기반). 건드리지 않았음

---

## 6. 다음 세션에서 할 일

### 6.1 (선택) 기존 아티팩트 백업

```powershell
Copy-Item artifacts\multi_horizon_model artifacts\multi_horizon_model_tp003 -Recurse
Copy-Item artifacts\backtest_results_multi_horizon artifacts\backtest_results_multi_horizon_tp003 -Recurse
```

### 6.2 파이프라인 재학습

```powershell
powershell -ExecutionPolicy Bypass -File run_full_pipeline.ps1
```

- 데이터는 이미 있음 (`artifacts/btcusdt_2020_2025.parquet` 168MB, 아카이브 CSV 2,192개) → Phase 1/2 건너뜀
- Phase 3에서 regime별 long/short마다 **Optuna 100 trial** → **12시간 이상** 예상
- 급하면 `$MultiHorizonPilot = $false` (Phase 3.5 생략) 또는 Optuna trial 축소
- 학습(Phase 3)과 백테스트(Phase 4)가 같은 `$LabelTpPct/$LabelSlPct`를 공유하므로 배리어 가드는 자동 통과

### 6.3 결과에서 볼 것 (이게 핵심)

1. **승률이 38.7%를 넘는가?** — 새 배리어의 손익분기점. 기존 32.3%에서 6.4%p를
   메워야 한다. 못 넘으면 새 배리어에서도 구조적으로 수익이 안 난다.
2. **range 레짐에서 거래가 나오는가?** — `threshold_floor=0`이므로 2025년 봉의
   91%를 차지하는 range에서 거래가 나와야 정상. 이전엔 0건이었다. **이번에도
   0건이면 다른 원인이 있다.**
3. **Sharpe/PF가 NaN인가?** — 거래 20건 미만이면 NaN이 정상 동작(가짜 숫자 방지).

---

## 7. 미해결 과제

### 7.1 모델 캘리브레이션이 깨져 있다

진입 확률 평균이 롱 0.522 / 숏 0.522인데 실현 승률은 32.3%.
특히 **롱은 P=0.522인데 승률 16.7%** (12건 중 2승). 모델이 "52% 확률"이라고
말한 사건이 17%만 발생한다. 학습된 최적 임계값이 0.35 근처인 것도 확률 분포가
낮게 압축돼 있다는 신호다. **실거래 전에 reliability curve 점검 필요.**

### 7.2 코드 리뷰에서 남긴 미수정 항목

- `backtest_summary.json`에 JSON `NaN` 리터럴이 나감 (RFC 8259 위반). PowerShell/Python은 파싱되지만 jq는 실패. `null`로 직렬화하는 게 낫다
- `compare_backtests.py`의 `_profit_factor`는 빈 슬라이스에 0.0을 반환하는데 `_sharpe`는 NaN → 데이터 없는 셀이 "PF 0.00 = 최악"으로 읽힘
- `_MIN_RETURN_STD` 상수가 `backtest.py`와 `compare_backtests.py`에 중복 (import로 묶이지 않음)

### 7.3 기존 테스트 실패 6건

특히 `test_v718.py`의 5건이 regime detector 지속성 · live 폴백 · E2E 파이프라인
같은 핵심 경로를 다룬다. 실거래 시스템 기준으로 방치하기 나쁜 자리.

### 7.4 `strategy_comparison`이 사실상 no-op

aggressive/balanced/conservative 세 프로파일 결과가 **모든 자릿수까지 동일**했다.
프로파일의 knob은 임계값과 TP/SL 둘뿐인데, 임계값은 learned 값이 덮고
(`_resolve_backtest_thresholds`), TP/SL은 `exec_tp_pct/exec_sl_pct`가 덮는다.
비교 자체가 의미를 잃은 상태.

### 7.5 레짐 분포 시프트

학습 구간 vs 2025년: range 78.6% → 91.1%, up 11.0% → 3.6%, down 10.4% → 5.3%.
추세 레짐이 3배 가까이 희소해진 해에 하필 추세 레짐에서만 거래가 나왔다.
31건이라는 표본으로는 아무것도 결론지을 수 없다.
