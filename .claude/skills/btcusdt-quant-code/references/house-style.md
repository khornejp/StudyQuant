# House style (btcusdt_quant)

이 레포 패키지(`btcusdt_quant/`)의 실제 코드 컨벤션. 새 코드는 이 방식을 따르고, 기존 모듈을 고칠 때는 그
모듈의 지역 관례를 우선한다. black/flake8/mypy와 `pyrightconfig.json`(Python 3.10)이 설정돼 있으니 그에 맞춘다.

## 모듈 구성

- **첫 줄은 항상** `from __future__ import annotations`.
- 그 아래에 **모듈 docstring**으로 목적과 설계 의도를 적는다. `regime_rules.py`처럼 "왜 이렇게 설계했는가"
  (causal한 이유, parity를 지키는 방법)를 서술하는 것이 이 레포의 스타일이다.
- import 순서: 표준 라이브러리 → 서드파티 → 로컬(`from . import ...`). 무거운/optional 의존성은 최상단이
  아니라 사용하는 함수·메서드 안에서 지연 import.
- 공개 심볼은 파일 끝에 `__all__ = [...]`로 명시(예: `cv.py`).

## 값·설정 객체는 frozen dataclass

```python
@dataclass(frozen=True)
class SampleInterval:
    sample_index: int
    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        if self.end_index < self.start_index:
            raise ValueError("end_index must be greater than or equal to start_index")
```

- 불변 값/설정은 `@dataclass(frozen=True)`.
- 경계·불변식은 `__post_init__`에서 검증하고, 위반 시 **명확한 메시지의 `ValueError`**를 던진다.
- 가변 기본값(dict/list)은 `field(default_factory=lambda: {...})`로. 설정 dataclass의 가중치 맵이 그 예
  (`regime_rules.MultiFeatureRegimeConfig`).

## 타입 힌트 (모던 문법)

- 모든 공개 함수·메서드에 완전한 타입 힌트. 반환 타입도 명시(`-> None` 포함).
- 모던 문법을 쓴다: `int | None`, `dict[int, float]`, `tuple[str, ...]`, `Sequence[...]`, `Mapping[...]`.
  (`from __future__ import annotations` 덕분에 3.10에서 안전.)
- 값 컨테이너 반환은 dataclass로 감싼다(예: `UniquenessWeightResult`) — 튜플 언패킹으로 흘리지 않는다.

## 수치 안전 (금융 데이터라 특히 중요)

- 0 나눗셈·runaway를 막는 floor를 이름 있는 상수로 둔다: `_STD_FLOOR = 1e-9` 처럼, 왜 필요한지 주석과 함께.
- 유한성 검사에 `math.isfinite`를 쓴다. 비유한 값은 조용히 넘기지 말고 clip하거나 분류한다
  (feature governance 참조).
- 매직 넘버(임계값·경계·가중치)는 하드코딩하지 말고 설정 dataclass의 필드로 노출해 튜닝 가능하게 한다
  (`MultiFeatureRegimeConfig`가 모든 상수를 필드로 노출하는 방식).

## 상태 있는 컴포넌트는 직렬화 계약을 갖는다

fit이 필요한 것(스케일러, regime 탐지기, 모델 어댑터)은 `to_dict()` / `from_dict(payload)` 쌍을 제공해
학습 시 통계를 저장하고 serve 시 동일하게 복원한다. train/serve parity의 구현 수단이므로 새 컴포넌트도 이
패턴을 따른다. (`models.py`의 어댑터들, `regime_rules`의 detector 참고.)

## Optional 의존성 · fallback

lightgbm/catboost/torch처럼 없을 수 있는 의존성은 함수 안에서 `try/except ImportError`로 감싸고, 실패 시
graceful하게 대체 경로로 내려간다. `models.py`의 모델 선택은 요청 family가 불가하면 후보 체인을 따라
stdlib `CentroidLinearClassifier`까지 fallback하며, 그 사실을 `fallback_used`/`fallback_reason`으로
기록한다. 새 optional 경로도 "왜 fallback했는지"를 남긴다.

## PyTorch 사용 (multitask_nn.py 한정)

신경망은 `multitask_nn.py`에서만 쓴다. 여기서도 위 스타일을 유지하되:

- 학습 시작에 시드 고정, 학습/평가 모드 전환(`model.train()` / `model.eval()` + `torch.no_grad()`),
  `optimizer.zero_grad()`를 지킨다.
- 모델 상태는 이 레포 관례대로 `to_dict`/`from_dict`(내부적으로 `state_dict`를 직렬화)로 저장해 다른
  어댑터와 인터페이스를 맞춘다. 별도의 저장 포맷을 새로 만들지 않는다.

## 테스트

- `tests/`에 pytest로 둔다(`tests/test_regime_rules.py`, `tests/test_core.py` 등이 참고 예시).
- causal·parity 불변식은 특히 테스트로 못박는다(예: "detector 통계는 train으로만 fit된다", "경계를 넘는
  누수 샘플이 없다"). 이 레포는 이런 계약 위반이 가장 위험하므로 회귀 테스트로 지키는 것이 스타일에 맞는다.
