# Feature governance · 모델 어댑터 (btcusdt_quant)

feature와 모델이 이 레포의 계약을 지키게 하는 규율. 관련 모듈: `feature_registry.py`, `features.py`,
`feature_vector.py`, `models.py`, `ensemble.py`, `parity.py`.

## Feature registry (`feature_registry.py`)

feature는 임의로 추가하지 않고 **registry에 등록**한다. `FeatureDefinition`(frozen dataclass)의 필드가
곧 각 feature가 반드시 밝혀야 하는 계약이다:

- `feature_name`, `category`, `feature_group`, `formula`
- `lookback`, `min_samples`, `warmup_rule` — 얼마나 과거가 필요한지, 초반 warmup을 어떻게 처리하는지
- `dependencies` — 어떤 다른 feature/소스에 의존하는지
- `source` — 데이터 출처
- `required_for_training`, `required_for_live` — train/live parity 판정에 쓰인다
- `leakage_risk` — 이 feature의 누수 위험 등급. 새 feature를 만들 때 **정직하게** 매긴다
- `scaffold_status`

새 feature를 추가할 때:
1. 과거만 참조하는지(causal) 확인하고 `leakage_risk`를 정직하게 기입한다.
2. `lookback`/`warmup_rule`을 CV의 `label_horizon`/purge와 어긋나지 않게 맞춘다.
3. train과 live 양쪽에서 동일 공식으로 계산되는지(parity) 확인한다. live 전용 소스가 있으면 offline
   fallback 기본값이 train 분포와 어긋나지 않게 한다.

## 값 governance: finite + clipping

feature 값은 항상 유한하고 정해진 경계 안에 있어야 한다. 이 레포의 clipping 경계(예):

- z-score 계열: ±10
- ratio 계열: ±100
- return 계열: ±0.20
- vol-adjusted 계열: ±10

새 feature도 성격에 맞는 경계로 clip하고, 나눗셈·정규화에는 std/eps floor를 둔다. 경계·floor는 이름 있는
상수로 노출한다.

## NaN은 원인별로 분류한다

결측을 조용히 0으로 채우지 않는다. NaN 소스를 분류한다:

- **outage** — 소스 장애
- **warmup** — 초반 통계 미충족
- **structural** — 구조적으로 값이 없음
- **isolated** — 산발적 결측

분류에 따라 처리(대체/제외/게이트)를 다르게 하고, live에서는 parity 게이트가 이를 검사한다.

## Train/live parity gate (`parity.py`)

- feature가 train과 live에서 동일하게 계산되는지 게이트가 검증한다. parity가 깨지면 진입을 차단한다.
- 새 feature나 소스를 추가할 때 이 게이트에 걸리지 않는지(양쪽 계산이 일치하는지) 확인한다.

## 모델 어댑터 인터페이스 (`models.py`, `ensemble.py`)

모든 모델은 공통 계약을 지킨다 — 새 모델도 마찬가지:

- **`probability(values: Mapping[str, float]) -> float`** — feature 딕셔너리를 받아 확률을 낸다.
- **`to_dict()` / `from_dict(payload)`** — 학습된 상태를 직렬화·복원(train/serve parity).
- **Fallback 체인.** 요청한 family(lightgbm/catboost 등)가 불가하면 후보 체인을 따라 stdlib
  `CentroidLinearClassifier`까지 우아하게 내려간다. optional 의존성은 함수 안에서 `try/except ImportError`로
  감싼다. fallback이 일어나면 `fallback_used`/`fallback_reason`으로 사실과 이유를 기록한다.
- 앙상블(`EnsembleAdapter`)도 같은 인터페이스로 감싸 하위 모델을 `from_dict`로 복원한다.

새 모델을 붙일 때 별도의 예측·저장 포맷을 만들지 말고 이 인터페이스에 맞춘다. 그래야 training/backtest/live가
모델 종류를 몰라도 동일하게 다룰 수 있다.

## 캘리브레이션

확률은 Platt/Beta/Isotonic으로 캘리브레이션되고, sample 게이트와 ECE/Brier drift 모니터링이 붙는다. 새
확률 출력도 캘리브레이션·드리프트 경로에 태워 raw score를 그대로 신뢰하지 않는다.

## Feature 가설과 availability

registry의 source와 lookback만으로는 실제 사용 가능 시각이 충분히 표현되지 않을 수 있다. 새 feature에는 다음을
추가로 문서화한다.

- 경제적 또는 시장 미시구조 가설
- source event time과 ingestion/availability time
- earliest decision timestamp
- incomplete candle 사용 여부
- publication lag 또는 exchange API 지연

OHLCV 파생 feature 여러 개가 같은 return/trend/volatility 정보를 다른 형태로 반복할 수 있다. feature 수가 늘어난
것을 정보량 증가로 해석하지 않는다.

## Feature 채택 규칙

- SHAP, gain, permutation importance는 진단 도구이지 채택 증거가 아니다.
- 기존 accepted 모델에 feature 또는 group 하나만 추가해 동일 OOS split에서 비교한다.
- grouped ablation으로 제거 시 성능이 안정적으로 악화되는지 확인한다.
- fold, 기간, regime, horizon, seed별 일관성을 본다.
- 비용 후 trading 결과가 개선되지 않으면 predictive metric만의 미세 개선으로 채택하지 않는다.
- feature selection 자체도 fold train에서만 수행하고 선택 결과를 artifact에 기록한다.
