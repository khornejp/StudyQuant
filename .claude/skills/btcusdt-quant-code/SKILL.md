---
name: btcusdt-quant-code
description: >-
  btcusdt_quant / StudyQuant 프로젝트(비트코인 1분봉 퀀트 트레이딩 시스템, 2020~2025 데이터,
  regime별 CatBoost 중심 모델)에서 코드를 작성·수정·리뷰·디버깅하고, 후보 엣지가 실제로 반복 가능하고
  거래 가능한지 검증할 때 따르는 코드베이스 규율. feature 계산·registry, label, 모델 어댑터,
  training/CV, regime 탐지·라우팅, calibration, threshold, backtest, live 실행,
  governance/lineage/experiment 코드를 새로 짜거나 고칠 때 반드시 사용한다. 백테스트가 비현실적으로 좋거나,
  validation 개선이 거래수익으로 이어지지 않거나, live와 괴리가 있거나, 스택 트레이스를 고칠 때도 사용한다.
  핵심은 causality, train/serve parity, feature governance, label/execution alignment,
  비용 차감 후 out-of-sample 검증, 그리고 이 레포의 house style을 깨지 않는 것이다.
---

# btcusdt_quant 코드·연구 지침

이 스킬은 **btcusdt_quant** 패키지 / StudyQuant 레포에서 코드를 쓸 때, 이미 이 코드베이스에 자리잡은 규율을
유지하면서 **실제로 거래 가능한 out-of-sample edge가 있는지 검증**하기 위한 것이다.

목표는 학습 점수나 단일 백테스트를 가장 좋게 만드는 것이 아니다. 목표는 다음 질문에 답하는 것이다.

> 동일한 정보 시점과 실행 조건에서, 수수료·슬리피지·펀딩을 차감한 뒤에도 반복 가능한 기대수익이 남는가?

이 시스템은 실제 자금이 걸릴 수 있는 트레이딩 파이프라인이다. 가장 위험한 오류는 예외를 던지는 오류가 아니라,
에러 없이 성능을 부풀리거나 특정 기간에만 맞고 live에서 조용히 무너지는 오류다.

따라서 다음 여섯 원칙이 다른 무엇보다 우선한다.

1. **Causality** — 미래 정보가 feature·regime·label 선택·threshold에 새지 않는다.
2. **Train/serve parity** — 학습, backtest, live가 같은 데이터 가용성과 계산 경로를 사용한다.
3. **Label/execution alignment** — 예측 시점, 실제 진입 가능 시점, 라벨 시작점이 정확히 일치한다.
4. **Feature governance** — 값, 결측, clipping, lineage, availability가 명시된다.
5. **Out-of-sample edge validation** — 단일 metric이 아니라 기준모델·비용·기간·seed·regime 안정성으로 판정한다.
6. **Repository discipline** — 실제 실행되는 코드 경로를 찾아 최소 범위로 수정하고 테스트한다.

---

## 스택과 구조를 먼저 파악한다

- Python 3.10, numpy 1.26.4 고정(LightGBM/CatBoost 호환), pandas, pyarrow, scikit-learn, scipy,
  lightgbm, catboost, optuna, imbalanced-learn. 신경망은 `multitask_nn.py`에서만 torch를 쓴다.
- 재사용 코드는 **패키지 `btcusdt_quant/` 안**에 둔다. 레포 루트의 `verify_*.py`,
  `test_backtest_*.py`, `debug_*.py`, 임시 실험 러너에 핵심 로직을 중복 구현하지 않는다.
- 테스트는 `tests/`에 pytest로 둔다. 새 로직에는 회귀 테스트와 최소 smoke test를 추가한다.
- 코드를 짜기 전에 관련 기존 모듈, CLI 진입점, config 분기, artifact 로드 경로를 읽고
  **실제로 호출되는 코드 경로**를 확인한다.
- 새 구현이 기존 경로에서 호출되지 않는 평행 구현(dead/unused path)이 되지 않게 한다.
- 스킬의 일반 권장보다 레포에 이미 있는 명확한 계약이 우선한다. 단, 누수·시점 오류·test 오염은 예외 없이 고친다.

세부 규율은 필요할 때 다음 참고 파일을 읽는다.

- 코드 스타일(dataclass, 타입, import, 수치 안전) → `references/house-style.md`
- 누수 방지·CV(purged walk-forward, CPCV, embargo, uniqueness, parity) → `references/leakage-and-cv.md`
- label, 예측 시점, 체결, 거래비용 → `references/labels-execution-and-costs.md`
- regime 탐지·라우팅·oracle 비교 → `references/regime.md`
- feature registry·governance·모델 어댑터 → `references/feature-governance.md`
- 엣지 판정·기준모델·실험 기록·다중검정 → `references/research-and-edge-validation.md`

---

## 원칙 1: Causality — 아무것도 미래를 보지 않는다

이 레포의 1순위 계약이다.

- 모든 per-row feature, regime 점수, 시그널은 그 시점까지 실제로 이용 가능한 정보로만 계산한다.
- `shift(-k)`, `center=True` rolling, 미래 봉을 포함한 resample, 전체 구간 통계, 미래 구간을 사용한 threshold는
  대표적인 누수 경로다.
- 정규화·스케일·quantile·feature selection·regime 통계는 각 train fold에서만 fit한다.
- `bfill`은 미래 관측치를 과거로 전파하므로 시계열 feature 처리에서 기본 금지한다.
- hindsight regime 라벨은 oracle 진단용 상한선일 뿐 forward 성능으로 보고하지 않는다.
- calibration, probability threshold, cost assumption, label 정의를 final test 결과를 보고 다시 고르지 않는다.
- 새 feature·label·split·resample을 리뷰할 때 causality를 가장 먼저 점검한다.

---

## 원칙 2: Train/serve parity — 학습과 운용이 같은 계산을 한다

- fit 상태는 `to_dict` / `from_dict`로 저장·복원한다. scaler, regime detector, calibrator,
  model adapter의 통계를 backtest/live에서 재-fit하지 않는다.
- feature parity gate와 `required_for_training` / `required_for_live` 계약을 존중한다.
- offline에만 존재하는 source를 사용한다면 live 대체값을 임의로 넣지 말고 availability 차이를 명시한다.
- 라우터를 바꾸면 새 bucketing으로 regime별 모델을 재학습한다.
- candle 완료 여부, resample boundary, timezone, timestamp rounding이 학습과 serve에서 같은지 확인한다.
- train에서 사용한 feature가 decision timestamp에 실제로 존재하지 않으면 parity 실패다.

---

## 원칙 3: Label/execution alignment — 예측한 기회와 거래한 기회가 같아야 한다

feature나 label을 변경하기 전에 아래 다섯 시점을 명시한다.

1. feature cutoff timestamp
2. prediction/decision timestamp
3. earliest executable timestamp
4. label start timestamp
5. label end timestamp

기본 안전 계약은 다음과 같다. 레포 config가 다르면 그 계약을 문서화하고 테스트한다.

- candle `t`의 close까지 계산된 feature를 사용한다.
- 예측은 candle `t`가 닫힌 뒤 생성한다.
- 가장 빠른 체결은 candle `t+1` open 또는 그 이후다.
- 미래 수익률 label은 실제 체결 가능 시점부터 시작한다.
- 불완전한 상위 timeframe candle을 완료된 봉처럼 사용하지 않는다.

현재 봉의 종가를 feature에 사용하고 같은 종가에 체결하는 백테스트는, 현실적인 주문·지연 모델이 명시되지 않으면
허용하지 않는다. 자세한 규칙은 `references/labels-execution-and-costs.md`를 따른다.

---

## 원칙 4: Feature governance — 값뿐 아니라 정보 가용성도 관리한다

- feature는 registry에 등록하고 formula, lookback, warmup, dependencies, source, leakage risk,
  train/live requirement를 명시한다.
- 값은 finite여야 하고 성격에 맞는 경계로 clip한다.
- NaN은 outage, warmup, structural, isolated로 분류한다. 조용히 0으로 채우지 않는다.
- feature마다 경제적 또는 시장 미시구조 가설과 earliest availability를 적는다.
- SHAP importance나 split gain만으로 feature를 채택하지 않는다.
- 새 feature는 기존 모델에 최소 변경으로 추가하고 grouped ablation, fold 안정성, cost sensitivity를 통과해야 한다.
- OHLCV에서 파생된 비슷한 수십 개 feature는 새 정보가 아니라 중복 표현일 수 있음을 항상 경계한다.

---

## 원칙 5: Edge는 단일 metric이나 단일 백테스트로 인정하지 않는다

다음만으로 edge가 있다고 말하지 않는다.

- train loss 감소
- validation accuracy 상승
- Optuna best trial 개선
- SHAP 상위 feature 등장
- 한 번의 backtest 수익
- 특정 regime 또는 특정 연도에서만 높은 win rate
- threshold를 여러 번 바꾼 뒤 나온 최선 결과

모든 후보는 최소한 다음과 비교한다.

1. train positive rate를 내는 constant-probability baseline
2. always no-trade
3. 단순 momentum baseline
4. 단순 mean-reversion baseline
5. 현재 accepted/production 후보
6. shuffled-label 또는 permutation negative control

예측 평가는 logloss, baseline logloss, Brier, PR-AUC, ROC-AUC, calibration, class rate,
prediction distribution을 포함한다. 거래 평가는 gross/net expectancy, trade count, fee, slippage, funding,
profit factor, drawdown, turnover, exposure, long/short 분리 결과를 포함한다.

결과는 year, fold, regime, horizon, volatility bucket, seed로 나눠 안정성을 확인한다.
기본 비용뿐 아니라 1.5배와 2배 비용 stress에서도 방향성이 유지되는지 본다.

자세한 acceptance gate와 실험 기록 규칙은 `references/research-and-edge-validation.md`를 따른다.

---

## 원칙 6: Regime routing은 detector와 entry model을 분리해서 검증한다

regime-aware 구조는 end-to-end 결과만 보면 원인을 알기 어렵다. 다음 네 가지를 반드시 비교한다.

1. regime detector 자체 품질
2. true/hindsight regime을 사용한 oracle routing
3. predicted causal regime을 사용한 routing
4. regime을 사용하지 않는 unified model

판정 규칙:

- oracle routing은 좋고 predicted routing만 나쁘면 detector 또는 transition/routing 문제다.
- oracle routing도 나쁘면 label, feature, entry model 또는 regime 분할 자체 문제다.
- unified model이 predicted routing보다 좋으면 현재 regime 분리가 오히려 정보를 손상시킨다.
- regime별 결과만 좋고 시간순 통합 결과가 나쁘면 전환 비용, routing lag, leakage를 의심한다.

라우팅 진단은 실제 평가 대상 OOS 기간에 대해 계산한다. 전체 2020~2025 혼합 결과로 특정 test 기간의
라우팅 성능을 설명하지 않는다.

---

## Research split와 final test 보호

날짜는 레포 config와 최신 설계 문서를 먼저 읽는다. 현재 프로젝트의 canonical split이 다음과 같다면 그대로 지킨다.

- train: 2020-01-01 ~ 2024-12-31
- model/threshold validation: 2025-01-01 ~ 2025-06-30
- final untouched test: 2025-07-01 ~ 2025-12-31

final test는 다음에 사용하지 않는다.

- feature 또는 label 선택
- regime threshold 선택
- HPO와 early stopping
- calibration fitting
- probability/EV threshold 선택
- cost 가정 조정
- 전략 후보 선택

이 날짜가 config와 다르면 하드코딩하지 말고 실제 split을 출력하고, final test가 무엇인지 먼저 확정한다.
이미 final test를 반복 조회했다면 그것을 “untouched”라고 부르지 말고 오염 사실을 기록한다.

---

## House style 요약

`references/house-style.md`가 기준이다.

- 모든 모듈 첫 줄 `from __future__ import annotations`
- 모듈 docstring에 목적과 설계 의도
- 값/설정 객체는 `@dataclass(frozen=True)`
- 공개 API 완전한 타입 힌트와 `__all__`
- 이름 있는 상수와 수치 floor
- optional dependency는 지연 import와 명시적 fallback 기록
- 상태 있는 컴포넌트는 `to_dict` / `from_dict`
- 재사용 로직은 패키지 모듈, 테스트는 `tests/`

---

## 작업 절차

주요 변경을 구현하기 전에 다음 순서를 따른다.

1. 실제 CLI/entry point와 config 분기를 추적한다.
2. 현재 실행되는 training, routing, calibration, backtest 경로를 확인한다.
3. 중복 또는 충돌하는 구현이 있는지 찾는다.
4. 변경 가설과 기대 효과를 한 문장으로 명시한다.
5. timestamp contract와 누수 위험을 적는다.
6. 가장 작은 surface만 수정한다.
7. 관련 unit/regression test를 추가한다.
8. smoke test를 실행한다.
9. 가능하면 기존 baseline과 동일 split에서 비교 실험한다.
10. 실패, fallback, 미실행 경로를 숨기지 않고 보고한다.

한 번에 feature, label, model, threshold, cost를 모두 바꾸지 않는다. 한 번의 실험은 가능한 한 하나의 가설만
검증하도록 한다.

---

## 디버깅 순서

### 백테스트/검증이 비현실적으로 좋다

1. timestamp와 execution alignment
2. split, purge, embargo
3. scaler/quantile/regime 통계 fit 범위
4. `shift(-k)`, centered rolling, bfill, resample 경계
5. hindsight regime 사용 여부
6. calibration/threshold/test 오염
7. fee, slippage, funding 누락

### logloss는 개선되지만 수익이 없다

1. label이 실제 거래 가능한 수익을 표현하는가
2. 예측 개선이 비용 이하의 작은 움직임에 집중되는가
3. probability calibration이 fold 밖에서 유지되는가
4. threshold가 validation에 과적합되었는가
5. trade count와 turnover가 비용을 증폭시키는가
6. regime routing에서 edge가 소실되는가
7. long/short 중 한 방향만 손실을 만드는가

### backtest는 좋지만 OOS/live에서 무너진다

1. train/serve feature availability
2. fit artifact 복원
3. incomplete candle/resample 차이
4. router 변경 후 재학습 누락
5. data revision 또는 publication lag
6. 특정 기간·seed 의존성

### 스택 트레이스와 수치 예외

shape, dtype, index alignment, timestamp order, finite 여부부터 확인한다. 문제를 최소 재현으로 좁히고 한 번에
하나의 가설만 검증한다. 수치 문제를 넓은 `try/except`나 무조건적인 `fillna(0)`로 숨기지 않는다.

---

## 결과 보고 형식

연구 또는 성능 변경 작업은 가능한 한 다음 형식으로 보고한다.

### Hypothesis
검증하려는 시장 행동 또는 소프트웨어 가설.

### Exact change
변경한 파일, 함수, config, feature, label.

### Timestamp and leakage assessment
feature cutoff, decision, execution, label interval, purge/embargo, 잠재 누수.

### Experimental design
train/validation/test, fold, seed, 비용, baseline.

### Predictive results
baseline과 모델의 logloss, Brier, PR-AUC, calibration 등.

### Trading results
gross/net, 거래 수, 비용, expectancy, drawdown, long/short 분리.

### Stability
기간, regime, horizon, volatility bucket, seed별 안정성.

### Verdict
다음 중 하나만 사용한다.

- `ACCEPT`
- `PROMISING BUT UNPROVEN`
- `REJECT`
- `INVALID DUE TO LEAKAGE`
- `INCONCLUSIVE DUE TO SAMPLE SIZE`

### Next experiment
가장 정보가치가 높은 다음 실험 하나만 제안한다.

---

## 넘기기 전 체크

- 실제 호출되는 코드 경로를 수정했는가?
- feature, label, split, regime, calibration, threshold가 미래를 보지 않는가?
- feature cutoff → prediction → execution → label start/end 계약이 명시됐는가?
- fold별 train에서만 fit하고 artifact를 동일하게 복원하는가?
- feature가 finite/clip되고 registry와 lineage에 등록됐는가?
- NaN을 원인별로 처리했는가?
- 기준모델과 accepted 후보를 같은 split/비용으로 비교했는가?
- fee, slippage, funding과 1.5x/2x stress를 반영했는가?
- 결과를 period/regime/horizon/seed로 분해했는가?
- oracle routing, predicted routing, unified model을 비교했는가?
- final test를 선택·튜닝에 사용하지 않았는가?
- 시도한 실험 수와 multiple-testing 위험을 기록했는가?
- 새 로직에 테스트와 smoke run이 있는가?
- fallback, 실패, 실행하지 못한 검증을 숨기지 않았는가?
