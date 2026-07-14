---
name: btcusdt-quant-code
description: >-
  btcusdt_quant / StudyQuant 프로젝트(비트코인 1분봉 퀀트 트레이딩 시스템, 2020~2025 데이터, regime별 모델)에서
  코드를 작성·수정·리뷰·디버깅할 때 따르는 이 코드베이스의 확립된 규율. feature 계산·registry, 모델 어댑터,
  training/CV, regime 탐지·라우팅, backtest, live 실행, governance/lineage 코드를 새로 짜거나 고칠 때, 그리고
  백테스트/검증 성능이 이상하거나(비현실적으로 좋음, live와 괴리) 스택 트레이스를 고칠 때 반드시 사용한다.
  사용자가 "지침"이나 파일명을 명시하지 않아도, 이 프로젝트의 파이썬 코드를 다루는 작업이면 기본으로 참고한다.
  핵심은 causality(무 look-ahead), train/serve parity, feature governance, 그리고 이 레포의 house style을
  깨지 않는 것이다.
---

# btcusdt_quant 코드 지침

이 스킬은 **btcusdt_quant**(패키지) / StudyQuant 레포에서 코드를 쓸 때, 이미 이 코드베이스에 자리잡은 규율에
새 코드를 맞추기 위한 것이다. 목표는 새로운 규칙을 강요하는 게 아니라, 프로젝트마다 품질이 들쑥날쑥해지는 것을
막고 **이 레포가 원래 지키던 방식**을 일관되게 이어가는 것이다.

이 시스템은 실제 자금이 걸릴 수 있는 트레이딩 파이프라인이므로, 여기서의 실수는 대부분 "에러 없이 조용히 성능을
부풀리거나 live에서만 무너지는" 형태로 나타난다. 그래서 아래 세 가지 원칙이 다른 무엇보다 우선한다.

## 스택 & 구조 (먼저 파악)

- Python 3.10, numpy 1.26.4 고정(LightGBM/CatBoost 호환), pandas, pyarrow, scikit-learn, scipy,
  lightgbm, catboost, optuna, imbalanced-learn. 신경망은 `multitask_nn.py`에서만 torch를 쓴다.
- 재사용 코드는 **패키지 `btcusdt_quant/` 안**에 둔다. 레포 루트에는 일회성 스크립트(`verify_*.py`,
  `test_backtest_*.py`, `debug_*.py`, `*.py` 실험 러너)가 많은데, 이것들이 패키지 규율에서 벗어난 부분이
  코드 품질이 들쑥날쑥해 보이는 주된 원인이다. **새로 만드는 재사용 로직은 루트 스크립트가 아니라 패키지
  모듈에 넣고, 아래 house style을 따른다.** 루트 스크립트를 고칠 때도 가능한 한 패키지 함수를 호출하게 한다.
- 테스트는 `tests/`에 pytest로 둔다(`tests/test_regime_rules.py` 등). 새 로직에는 여기에 테스트를 추가한다.
- 코드를 짜기 전에 관련 기존 모듈을 먼저 읽고 그 관례를 따른다. 스킬의 권장보다 **레포에 이미 있는 방식이
  우선**이다.

프레임워크·영역별 세부는 필요할 때 참고 파일을 읽는다:

- 코드 스타일(dataclass, 타입, import, 수치 안전 등) → `references/house-style.md`
- 누수 방지·CV(purged walk-forward, CPCV, embargo, uniqueness, train/serve parity) → `references/leakage-and-cv.md`
- regime 탐지·라우팅 → `references/regime.md`
- feature registry·governance·모델 어댑터 인터페이스 → `references/feature-governance.md`

---

## 원칙 1: Causality — 아무것도 미래를 보지 않는다

이 레포의 1순위 계약이다. `regime_rules.py`가 "Nothing looks ahead"를 명시하고, `regimes.json`조차
hindsight 라벨에 look-ahead 경고를 달아둔 이유다.

- **모든 per-row 계산은 그 시점까지의 정보로만.** feature, regime 점수, 시그널은 미래 봉을 참조하면 안 된다.
  `shift(-k)`, `center=True` 롤링, 전체 구간 통계 등이 미래를 끌어오는 전형적 경로다.
- **정규화·스케일 통계는 학습 구간에서 한 번만 fit.** 그리고 저장했다가 backtest/live에서 재사용한다
  (전체 데이터나 live 버퍼에 재-fit 금지). 자세한 것은 parity 절 참조.
- **hindsight로 라벨된 것은 진단용일 뿐.** `regimes.json`의 정적 regime 구간은 "라우팅이 완벽할 때
  모델이 얼마나 하는가"를 볼 때만 쓰고, live/forward 성능으로 착각하지 않는다. 실거래 경로는 `RegimeDetector`/
  `regime_rules`로 실시간 탐지한다.
- 코드를 리뷰할 때, 새 feature·라벨·split이 미래를 보는지 **항상** 먼저 점검한다.

## 원칙 2: Train/serve parity — 학습과 실거래가 똑같이 계산한다

train에서 계산한 것과 backtest/live에서 계산한 것이 어긋나면(train/serve skew) 백테스트는 좋지만 live는
무너진다. 이 레포는 이를 구조로 막는다.

- **fit 상태는 `to_dict`/`from_dict`로 저장·재로딩한다.** regime 탐지기, 스케일러, 모델 어댑터 모두 학습
  시 통계를 계산해 직렬화하고, serve 시 **같은 통계**로 복원해 점수를 낸다. 새 상태 있는 컴포넌트도 이
  패턴을 따른다.
- **feature parity gate를 존중한다.** feature는 train과 live에서 동일하게 계산돼야 하며, registry의
  `required_for_training`/`required_for_live`와 parity 게이트가 이를 강제한다. live 전용 소스가 없을 때의
  안전한 fallback 기본값도 train과 어긋나지 않게 한다.
- **라우터를 바꾸면 재-bucketing이 필요하다.** regime 탐지기(bucketing)를 바꾸면 regime-aware 모델은
  그 새 bucketing으로 재학습해야 한다. 라우터만 갈아끼우면 train/serve skew가 생긴다.

## 원칙 3: Feature governance — 값은 항상 유한하고 경계 안에 있다

- **finite 강제 + clipping.** feature 값은 유한해야 하고 정해진 경계로 clip된다(예: z-score ±10, ratio
  ±100, return ±0.20, vol_adj ±10). 새 feature도 registry에 등록하고 적절한 경계·warmup·leakage_risk를
  지정한다. 자세한 것은 `references/feature-governance.md`.
- **NaN은 원인별로 분류한다**(outage/warmup/structural/isolated) — 조용히 0으로 채우지 않는다.
- **모델 어댑터는 공통 인터페이스를 지킨다.** `probability(values) -> float` + `to_dict`/`from_dict`,
  그리고 LightGBM/CatBoost가 없으면 stdlib 분류기로 내려가는 fallback 체인. 새 모델도 이 계약을 따른다.

---

## House style (요약)

`references/house-style.md`에 예시와 함께 정리돼 있다. 핵심만:

- 모든 모듈 첫 줄 `from __future__ import annotations`, 모듈 docstring으로 목적·설계 의도를 적는다.
- 값/설정 객체는 `@dataclass(frozen=True)`, 가변 기본값은 `field(default_factory=...)`,
  경계 검증은 `__post_init__`에서 `ValueError`로.
- 완전한 타입 힌트(모던 문법: `int | None`, `Mapping[str, float]`, `tuple[str, ...]`), 공개 API는 `__all__`.
- 매직 넘버는 이름 있는 상수 + 설명 주석(`_STD_FLOOR = 1e-9` 처럼 왜인지). 나눗셈에는 std/eps floor.
- 무거운/optional 의존성(lightgbm, catboost, torch)과 순환 참조 회피용 import는 함수 안에서 지연 import,
  없을 때 우아하게 fallback.
- 주석·docstring 언어는 기존 모듈을 따른다(대부분 영어).

---

## 디버깅

증상별로 접근이 다르다. 자세한 체크리스트는 각 참고 파일에 있다.

### 백테스트/검증 성능이 비현실적으로 좋다 → 십중팔구 look-ahead 누수

이 레포에서 "성능이 너무 좋다"는 버그 신호다. 순서대로 되짚는다: split이 시간순인가(purge/embargo 있는가) →
스케일러·regime 통계를 전체 구간에 fit하지 않았는가 → feature에 `shift(-k)`나 미래 롤링이 없는가 → regime
라벨이 hindsight(`regimes.json`)인가 → CPCV/walk-forward 경계를 넘는 샘플이 없는가.

### backtest는 좋은데 live/out-of-sample에서 무너진다 → train/serve parity 문제

train에서 접근한 정보가 serve 시점에 실제로 존재하는지, fit 통계가 `to_dict`/`from_dict`로 동일하게
복원되는지, feature parity 게이트가 통과하는지 본다.

### 스택 트레이스 / 예외

예외 타입과 관련 값의 shape/dtype/유한성을 먼저 확인한다. 추측으로 여러 곳을 동시에 바꾸지 말고, 문제를
재현하는 가장 작은 예시로 좁혀 한 번에 하나의 가설만 검증한다. 수치 이슈(NaN/Inf)는 clipping·floor·finite
강제가 빠진 지점을 의심한다.

---

## 넘기기 전 체크

- 새 feature/라벨/split/regime 점수가 미래를 보지 않는가? (causality)
- fit 통계를 train에서 한 번만 계산하고 `to_dict`/`from_dict`로 serve에서 재사용하는가? (parity)
- feature가 finite·clip되고 registry에 등록됐는가? NaN을 원인별로 다루는가? (governance)
- 재사용 로직을 루트 스크립트가 아니라 패키지 모듈에 두고 house style(dataclass·타입·__future__·__all__)을
  따랐는가?
- 새 로직에 `tests/` pytest를 추가했는가?
- 의심스러운 결정(하이퍼파라미터, metric, regime 임계값)은 주석/커밋에 근거를 남겼는가?
