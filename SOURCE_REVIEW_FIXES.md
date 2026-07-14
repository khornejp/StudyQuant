# 소스 전체 리뷰 수정 내역

> 작성일: 2026-07-10
> 대상 문서: `project_pipeline_source_review_summary.md` (round-1 리뷰 문서) 재검증 + 누적 워킹트리 diff(3,272줄) 전체 코드리뷰
> 관련 문서: `CODE_REVIEW_FIXES.md`(1~7차 라운드 이력), `PIPELINE_INTEGRATION.md`(사용법), `THRESHOLD_HORIZON_FIX.md`
> 변경 파일: `btcusdt_quant/models.py`, `btcusdt_quant/training.py`, `btcusdt_quant/cli.py`, `btcusdt_quant/ensemble.py`, `btcusdt_quant/live.py`, `backtest_100usd_unified.py`, `test_backtest_fast_features.py`, `tests/test_review_items.py`

---

## 1. 요약

두 가지를 했다.

1. **round-1 리뷰 문서의 지적 5건을 현재 코드로 재검증** → 전부 반영되어 있고 **회귀 없음**.
2. **누적 diff 전체(3,272줄)에 8개 앵글 코드리뷰** → 실제 결함 5건 발견·수정, 오탐 2건은 실증으로 기각.

| 구분 | 건수 |
|---|---|
| round-1 문서 지적 재검증 | 5건 전부 OK, 회귀 0 |
| 신규 수정 | 9건 (CRITICAL 1, HIGH 1, MEDIUM 3, 강화 4) |
| 실증으로 기각한 후보 | 2건 |
| 의도적으로 보류한 정리 항목 | 3건 |
| 회귀 검증 | `test_review_items.py` **86 passed**, 전체 스위트 **245 passed** |

---

## 2. round-1 문서 재검증 (회귀 없음)

| 원 지적 | 현재 구현 | 상태 |
|---|---|---|
| Kelly edge에 비용 미반영 | `risk.expected_edge(p, tp, sl, round_trip_cost)`, `run_backtest`가 `2*(fee+slippage)`를 전달 | ✅ |
| Sharpe/profit_factor가 position size 미반영 | `trade_return_pct`(equity 수익률) 기준으로 계산 | ✅ |
| multi-horizon SELL 해석 위험 | 단일모델 SELL은 켈리가 거부(`shorts_skipped_no_short_model`), 레짐 경로는 전용 `short_success` 모델 | ✅ |
| `run_full_pipeline.sh` 미동기화 | Phase 2.3 / train-multi-horizon / kelly / compare_backtests 전부 존재 | ✅ |
| OU half-life가 raw close 기준 | `--series {close,vwap_deviation,log_zscore}`, 파이프라인은 `log_zscore` | ✅ |

문서가 남긴 미해결 항목 중 **live `entry_quantity = 0.001`** 만 그대로다 (`kelly_notional` 정의 1회 / 호출 0회).

---

## 3. 수정 내역

### F1 — [CRITICAL] 존재하지 않는 심볼을 임포트하는 죽은 경로

**문제.** `backtest_100usd_unified.py:120`과 `test_backtest_fast_features.py:61`이
`from btcusdt_quant.training import Standardizer, LinearClassifier`를 실행하는데, `training.py`에 두 클래스가 **없다**(grep 0건). 함수 내부 임포트라 모듈 로드는 통과하고, 인라인 학습 분기에 진입하는 순간 `ImportError`로 죽는다. `ensemble._load_submodel`이 참조하던 `deterministic_centroid_linear` 죽은 분기도 같은 뿌리였다.

**수정.** 두 스크립트가 원하던 "밀리초 단위 결정론적 분류기"를 `btcusdt_quant/models.py`에 제대로 구현했다.

```python
class CentroidLinearClassifier:
    model_family_name = "deterministic_centroid_linear"
    # 표준화 -> 두 클래스 centroid의 차이를 가중치로,
    # 경계는 두 centroid의 중점, ||diff||로 정규화한 부호거리를 로지스틱에 통과
```

- `ModelAdapter` 프로토콜 준수: `fit` / `probability` / `predict_proba` / `as_dict` / `from_dict`
- 상수 피처의 `std=0` 나눗셈을 **스케일 상대 하한**으로 방어(F9), `z`를 `±60`으로 클램프해 `exp` 오버플로 차단
- 빈 행렬 / 단일 클래스 / 폭 불일치 / NaN·inf / 겹친 centroid는 명시적 `ValueError`(F7, F8)
- `ensemble._load_submodel`과 **`live.load_model_artifact`** 양쪽에 분기 추가 → 저장한 모델을 다시 로드할 수 있다

**검증.**
```
train accuracy: 0.823   (분리 가능한 피처 기준, 0.5를 크게 상회)
prob range: 0.0586 .. 0.9528   (포화되지 않음)
as_dict/from_dict 왕복 확률 차: 0.00e+00
numpy 2D 배열 입력 그대로 수용
live.load_model_artifact -> CentroidLinearClassifier, 확률 보존
```

> **참고 — 의도적 동작 변경**: 옛 스크립트 수식은 경계를 음성 centroid에 두었다(`intercept = dot(neg_centroid, diff)`). 새 클래스는 **중점**에 둔다. 옛 코드는 애초에 실행된 적이 없으므로(클래스 부재) 보존할 "기존 동작"이 없고, 중점이 nearest-centroid의 표준 정의다.

---

### F2 — [HIGH] direction policy의 두 진실 원천

**문제.** `cli.MH_REGIME_SIDES`가 `training.py:1062-1063`의
`train_long = regime in ("up","range")` / `train_short = regime in ("down","range")`를 **손으로 복제**하고 있었다. 주석 스스로 "mirrors training.py"라고 자인. 누군가 한쪽만 바꾸면 Phase 3와 Phase 3.5가 서로 다른 사이드 집합을 학습하는데, 코드·주석·파이프라인은 계속 "regime-aligned, 비교 가능"이라 주장한다 → Phase 4 vs 4.5 비교가 조용히 apples-to-oranges가 된다.

**수정.** `training.py`에 단일 원천을 만들고 양쪽이 **같은 객체**를 읽게 했다.

```python
# training.py
REGIME_SIDES: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType({
    "up":    (("long",  "long_success"),),
    "down":  (("short", "short_success"),),
    "range": (("long",  "long_success"), ("short", "short_success")),
})
def sides_for_regime(regime_name: str) -> tuple[tuple[str, str], ...]: ...

# cli.py
MH_REGIME_SIDES = training.REGIME_SIDES        # 복사가 아니라 별칭
```

`_train_single_regime`의 두 정책 지점(사이드 선택, 홀드아웃 루프) 모두 `sides_for_regime()`을 읽는다. 별칭이므로 **`MappingProxyType`으로 읽기 전용화** — 그러지 않으면 한 소비자가 모두의 정책을 다시 쓸 수 있다.

**동작 동일성 확인.**
- `_train_single_regime`에 도달하는 `regime_name`은 `dataset.USER_REGIME_NAMES = ("up","down","range")` 루프에서만 온다 → 세 이름 모두 정책이 있으므로 동작 변화 없음 (unknown 이름은 F6에서 `ValueError`로 처리)
- 홀드아웃 루프의 새 스킵 조건 `resolved_params is None`은 옛 `not is_trained`와 동치 (`_resolve_model_params`는 항상 non-empty dict를 반환)
- `long_params if train_long else None`의 지연 평가 덕에 미학습 사이드의 `NameError` 없음

---

### F3 — [MEDIUM] `attach_labels`가 side 루프 안에서 중복 실행

**문제.** regime-aware multi-horizon 학습에서 홀드아웃 라벨링이 `for side, target_key in sides:` **안**에 있었다. 인자 중 어느 것도 side에 의존하지 않고, `attach_labels`는 `target_key`와 무관하게 `long_success`/`short_success`/`profitability`를 **항상 전부** 계산한다. 따라서 양방향 레짐(`range`)은 동일 라벨을 두 번 만든다.

6년 데이터 기준 range 홀드아웃 ~20만 행 × 3회 배리어 스캔 × 최대 60바 ≈ **3,600만 캔들 비교**가 매 실행마다 통째로 낭비.

**수정.** `holdout_labeled`와 `holdout_matrix`를 레짐 루프 레벨로 hoist. side별로는 타깃 컬럼 추출만 남긴다.

**검증(스텁 모델로 계측).**
```
attach_labels 총 호출: 12 -> 11
  (3 레짐 × 홀드아웃 1회) + (4 사이드 × 진단/refit 2회 × horizon 1)
결과 아티팩트·임계값 동일, rc=0
```

---

### F4 — [MEDIUM] 저장한 centroid 모델을 다시 로드할 수 없음

`live.load_model_artifact`의 `model_family` 디스패치에 분기가 없어, `as_dict()`로 저장은 되는데 로드는 `strict=True`면 `ValueError`, 아니면 조용히 `None`을 반환했다. **저장은 되는데 못 읽는 모델**은 서빙 시점에야 드러나는 함정이다. 분기를 추가하고 라운드트립 테스트로 고정했다.

### F5 — [MEDIUM] 별칭된 정책 매핑이 mutable

`cli.MH_REGIME_SIDES`가 `training.REGIME_SIDES`와 **같은 객체**가 된 순간, 평범한 `dict`라면 어느 소비자든 모두의 정책을 바꿀 수 있다. `MappingProxyType`으로 읽기 전용화하고 테스트로 고정했다.

---

### F6~F9 — [강화] 코드리뷰가 새 코드에서 잡은 4건

이번 라운드에 **내가 새로 쓴 코드**를 리뷰한 결과다.

| # | 발견 | 수정 |
|---|---|---|
| F6 | `sides_for_regime()`의 unknown-regime 폴백이 **양방향**을 반환 — 옛 코드는 아무것도 학습하지 않았다. 오늘은 `USER_REGIME_NAMES` 루프만 호출해 도달 불가하나, 미래의 호출자가 새 버킷 이름을 넘기면 정책 없는 버킷에 롱·숏 모델을 조용히 만든다 | 추측하지 않고 `ValueError`. "양방향"은 정책 없는 버킷에 모델을 배포하고, "무방향"은 모델이 조용히 사라진다 — 둘 다 나쁘다 |
| F7 | 두 클래스 centroid가 겹치면(`norm == 0`) `_scale = 0` → **모든 확률이 정확히 0.5**인 상수 모델을 조용히 배포. 운영자는 "학습됐는데 절대 발동 안 하는" 모델을 이유 없이 보게 된다 | `ValueError("class centroids coincide...")` |
| F8 | `min(60, max(-60, nan))`이 CPython에서 **`-60`으로 귀결** → NaN 피처가 `probability ≈ 0`, 즉 "확신에 찬 숏"이 된다 | fit 시점에 NaN/inf `ValueError`, serve 시점엔 `0.5`(무의견) 반환 |
| F9 | 표준화의 **절대** epsilon(`std + 1e-8`)이 대규모 near-constant 피처(volume ~1e9, 잔차 float 오차 ~1e-7)를 z≈10으로 증폭해 순수 반올림 노이즈에 실질 가중치를 준다 | 스케일 **상대** 하한 `max(raw_std, 1e-9*(|mean|+1))`. 실측: 노이즈 가중치 `1.4431 → 0.000000` |

실증:
```
probability(NaN)                = 0.5                     (확신 0이 아님)
fit(NaN)                        -> ValueError: feature_matrix contains NaN or inf
fit(coincident centroids)       -> ValueError: class centroids coincide...
sides_for_regime("sideways")    -> ValueError: no direction policy for regime 'sideways'
|w_signal|=1.4431  |w_noise1e9|=0.000000
```

리뷰의 제거된-동작 앵글과 크로스파일 앵글은 **각각 발견 0건**. `_train_single_regime`의 새 스킵 조건(`resolved_params is None`)이 옛 `not is_trained`와 동치이고, 삼항식의 지연 평가로 미학습 사이드의 `NameError`가 없으며, 두 스모크 스크립트에 죽은 변수·임포트가 남지 않았음을 확인했다.

---

## 4. 실증으로 기각한 후보 2건

리뷰 에이전트가 제기했으나 **실험으로 반박**한 항목이다. 기록해 두는 이유는, 같은 의심이 다시 제기될 때 재실험 비용을 없애기 위해서다.

### R1 — `log_zscore`의 수치 불안정 → 저변동 구간 선택 편향 (기각)

주장: `var = s2/count - mean²`가 BTC 로그가격(~11)에서 catastrophic cancellation을 일으켜 음수가 되고, `if var > 0.0` 가드가 그 바들을 조용히 버려 **가장 조용한(=가장 빠르게 회귀하는) 구간이 표본에서 빠져** 반감기가 "느린 회귀" 쪽으로 편향된다. 게다가 롤링 합계는 2.6M바 동안 리셋되지 않아 드리프트가 누적된다.

실험: 2.6M바 전 구간(추세/조용한 레인지 교대) 시뮬레이션.

```
bars evaluated: 2,599,941
naive var <= 0 인 바 (조용히 버려짐): 0   (0.0000%)
가장 음수인 var: 0.000e+00
샘플 지점 naive vs two-pass 분산 상대오차: 최대 6.7e-4  (z 오차 ~3e-4)
완전 평탄 윈도우: 분자가 정확히 0 -> z = 0.0 (O(1) 노이즈 아님)
```

→ **버려지는 바 0건**, z 오차 3e-4. 예측된 편향은 발생하지 않는다.

### R2 — 파이프라인 플래그 오타 (기각)

자체 스캔이 `--optuna`, `--cv-mode`, `--multi-feature-regime`, `--ensemble`, `--feature-selection`, `--optuna-trials` 6개를 "미정의"로 표시했으나, `cli.py:968-992`에 **전부 정의**되어 있었다. 프로브 스크립트가 `train --help`를 제대로 실행하지 못한 결함이었고, 독립 크로스파일 앵글의 전수 대조도 통과했다.

---

## 5. 의도적으로 보류한 정리 항목

실제 결함은 아니나 유지보수 부채로 기록한다. 이번 라운드에서 손대지 않은 이유는 **리뷰 중인 diff에 미리뷰 코드를 더하지 않기 위해서**다.

| 항목 | 내용 | 판단 |
|---|---|---|
| `compare_backtests._sharpe` / `_profit_factor` | `backtest._per_trade_sharpe`와 공식 중복 | 방어 가능 — `compare_backtests`는 `json+math`만 쓰는 경량 리포터인데 `backtest.py`는 numpy·모델 어댑터를 끌어온다. 공용 stats 헬퍼로 빼는 것이 정답 |
| `load_candles` parquet/csv 삼항식 | `ic_diagnostic.py`, `cli.py`×4, `verify_range_halflife.py` 등 5+곳 복붙 | `dataset.load_candles(path)` 디스패처 추가 권장 |
| `ic_diagnostic`의 리키지 휴리스틱 | `_leak_flags`/`_past_returns`와 0.10/0.05/0.5 임계값이 CLI 스크립트의 private 함수라 `verify_*.py`에서 재사용 불가 | `btcusdt_quant/` 안의 모듈로 이동 권장 |

---

## 6. 남은 아키텍처 항목 (별도 작업)

| # | 내용 |
|---|---|
| K6 | **live 엔진이 `entry_quantity = 0.001` 하드코딩.** `PositionSizer`가 엔진에서 인스턴스화되지 않아 `kelly_notional()`은 호출 0회의 죽은 코드. 필요한 입력(`account.available_balance`, `model_inference["probability"]`, `optimized_tp_sl`, canonical closes)은 모두 스코프에 있으나, 단일모델 경로에 `P(short_success)`가 없다는 backtest와 동일한 선행 문제를 먼저 풀어야 한다 |
| K7 | `DrawdownProtocol.reduce_factor`가 로깅에만 소비되고 주문 수량에 곱해지지 않는다. 현재는 reduce_size 티어가 주문 자체를 미제출해 더 보수적이라 즉각 위험은 아니나, Kelly 배선 시 두 통합이 각각 이를 기억해야 한다 |
| A1 | `_ctx_two_sided`가 기본 `False`인 bool 플래그로 바 루프를 관통한다. "이 경로가 사이드별 확률을 제공하는가"는 확률을 생산하는 지점(번들 추상화)이 답해야 할 질문 — 새 라우팅 경로 추가 시 플래그 설정을 잊으면 **에러 없이 런이 long-only가 된다** |
| A2 | Phase 4.5는 여전히 **regime-aligned challenger**다. 실행 조건·레짐 라우팅·사이드별 타깃·임계값 배리어·학습 데이터 비율은 Phase 4와 같지만, horizon 블렌드 / base-model 튜닝(Optuna vs 기본) / 확률 캘리브레이션 의미론은 다르다 |

---

## 7. 검증

```
tests/test_review_items.py                : 86 passed
전체 스위트 (tests/, test_v718 제외)        : 245 passed, 1 deselected
  신규: CentroidLinearClassifierTests (8종)
        - phantom 심볼 부재, 클래스 분리 성능, 상수 피처 0-나눗셈 방어,
          직렬화 왕복, _load_submodel 로드, live.load_model_artifact 라운드트립,
          퇴화 입력 ValueError(빈/단일클래스/폭불일치/NaN/겹친 centroid),
          NaN 서브 시 0.5 중립, 대규모 노이즈 피처 가중치 무시
  신규: test_regime_side_policy_is_one_shared_object
        - `assertIs`로 동일 객체 확인 + MappingProxy 불변성 + unknown regime ValueError

python -c "import ast" 파싱 : backtest_100usd_unified.py, test_backtest_fast_features.py
attach_labels 계측         : 12 -> 11 호출, 결과 동일
centroid 라운드트립        : 확률 오차 0.00e+00
REGIME_SIDES               : mappingproxy, item assignment -> TypeError
```

전체 회귀 스위트: **`245 passed, 1 deselected`** (제외 1건은 HEAD 클린 worktree에서도 재현되는 기존 parquet float32 실패).
