# 조용한 단방향(one-directional) 결함 수정

> 작성일: 2026-07-11
> 대상 문서: `Project6_review_summary.md` (확인성 리뷰) 재검증
> 관련 문서: `CODE_REVIEW_FIXES.md`, `SOURCE_REVIEW_FIXES.md`, `PIPELINE_INTEGRATION.md`
> 변경 파일: `btcusdt_quant/backtest.py`, `btcusdt_quant/live.py`, `btcusdt_quant/cli.py`, `btcusdt_quant/training.py`, `tests/test_review_items.py`

---

## 1. 요약

`Project6_review_summary.md`의 개선 주장 5건은 **전부 사실**로 재확인했다. 그러나 문서의 **재학습 전 체크리스트가 통과하면서도 모델이 조용히 단방향으로 도는** 경로를 발견해, 그 체크리스트를 **코드로 강제**하도록 고쳤다.

| 구분 | 건수 |
|---|---|
| 문서 개선 주장 재검증 | 5건 전부 사실 |
| 핵심 수정 | 4건 |
| 코드리뷰가 새 코드에서 잡은 결함 | 4건 (그중 2건은 CRITICAL — 최악 케이스 미탐지) |
| 회귀 검증 | 전체 스위트 **251 passed** (제외 1건은 기존 parquet float32) |

---

## 2. 핵심 발견 — 체크리스트가 통과하면서 모델이 틀림

문서는 재학습 후 `default_fallback = 0`과 `shorts_skipped_no_short_model = 0`을 확인하라고 한다. 그런데 **둘 다 0이면서** `range` 레짐이 롱 전용인 아티팩트를 실제로 만들어 재현했다.

```
regime_range/short_model.json 을 제거한 뒤 백테스트:
  default_fallback                    = 0     ✅ (체크리스트 통과)
  shorts_skipped_no_short_model       = 0     ✅ (체크리스트 통과)
  실제 체결: down/SELL 48, range/BUY 23, up/BUY 31
  range 레짐 23건 전부 BUY  ← short 모델이 없어 SELL이 원천 차단
```

**원인.** 사이드 모델이 없으면 그 방향의 신호가 애초에 생성되지 않는다. 그러면:
- `shorts_skipped_no_short_model`은 "제안된 SELL을 켈리가 거부"할 때만 증가하므로 0을 유지
- `default_fallback`은 "레짐 매칭 실패"만 세므로, 매칭은 됐고 모델만 반쪽인 경우엔 0

즉 두 체크리스트 항목이 **구조적으로 이 실패를 볼 수 없다.**

---

## 3. 수정 내역

### D1 — capability를 확률 생산 지점(번들)으로 이동

기존 `_ctx_two_sided`(bool)는 "번들 경로인가"를 뜻했지 "이 사이드 확률이 진짜인가"가 아니었다. 한쪽 모델만 있는 번들에서도 True가 되고, 없는 쪽은 `0.0`으로 날조됐다.

`RegimeModelBundle`에 3개 메서드를 추가했다.

```python
def has_side_probability(self, regime, side) -> bool          # 이 사이드를 가격 매길 수 있는가
def probability_for(self, regime, side, features) -> float|None # None = "가격 불가"(0.0과 다름)
def missing_side_models(self, policy) -> dict[str, list[str]]   # 정책 대비 빠진 사이드
```

`run_backtest`는 `_ctx_two_sided`(bool)를 `_ctx_genuine_sides`(set)로 바꿨다. 번들 경로는 `has_side_probability`로 사이드를 선언하고, 단일모델 경로는 `"long"`만 선언한다(P(long)만 산출하므로). 켈리 가드는 `entered_side not in _ctx_genuine_sides`이면 거부하고, **롱/숏 각각 별도 카운터**(`shorts_skipped_no_short_model` / `longs_skipped_no_long_model`)로 보고한다.

- 기본값 `set()`은 **fail-closed**: 새 라우팅 경로가 사이드 선언을 잊으면 그 방향이 자동 차단된다(예전 bool 기본 False는 fail-open이었다)
- `None` vs `0.0` 구분: "가격 불가"를 "제로 확률"로 사이징하던 함정 제거

### D2 — 백테스트가 로드한 정책을 `REGIME_SIDES`와 대조

`cli.py`가 번들 로드 직후 `regime_bundle.missing_side_models(training.REGIME_SIDES)`를 계산해, 빠진 사이드마다 경고를 찍고 `BacktestResult.missing_side_models`로 아티팩트에 기록한다. 그러면 카운터가 0이어도 진실이 드러난다.

```
WARNING: regime 'range' has no model for side(s) ['short'] that the direction
policy requires. Those entries can never fire, so this run is one-directional
in 'range' -- retrain that side before comparing results.

backtest_summary.json: missing_side_models = {"range": ["short"]}
```

### D3 — MH 학습이 불완전 사이드 집합에서 게이트

`train-multi-horizon --regime-aware`가 정책이 요구하는 사이드를 못 만들면 **exit 1**(`--allow-partial-sides`로 명시 허용). `train --regime-aware`는 같은 상황에서 예외로 죽으므로, 이 게이트가 없으면 Phase 4.5가 Phase 4와 비대칭이 된다. partial-refit 게이트와 같은 패턴.

### D4 — 스킵된 레짐과 모든 `default_fallback`을 가시화

- `train`이 레짐을 min-rows 미달로 스킵하면 **경고**(예전엔 `skipped_regimes`에만 조용히 기록)
- 백테스트의 fallback 경고 임계값: auto/rule 라우팅에서는 `fallback > 0`이면 즉시(예전 20%는 15% 차지하는 레짐 하나가 통째로 빠져도 침묵), `--user-regime-file`은 의도적 갭이므로 20% 유지
- `no_model > 0`(자기 레짐도 default도 없는 바)이면 별도 경고

---

## 4. 코드리뷰가 새 코드에서 잡은 결함 4건

내가 D1~D4로 쓴 코드를 두 앵글로 리뷰한 결과다.

| # | 심각도 | 발견 | 수정 |
|---|---|---|---|
| C1 | **CRITICAL** | `missing_side_models`가 `sorted(self.models)`를 순회 → 모델이 **하나도 없는 레짐**(예: `down` 통째 미학습)은 `self.models`에 없어 누락 리스트에서 빠진다. 이게 최악 케이스(전체 단방향)인데 조용히 통과 | `sorted(policy)`를 순회하도록 변경 |
| C2 | **CRITICAL** | MH 게이트의 `missing_sides` 계산이 `if not trained_sides: continue` **뒤**에 있어, 사이드를 통째로 못 만든 레짐은 `skipped_regimes`에만 들어가고 게이트를 우회 → exit 0 | 완전 스킵 레짐도 `missing_sides[regime]=wanted_sides`로 기록 |
| C3 | MEDIUM | `elif fallback > 0`이 `--user-regime-file`의 의도적 갭에도 매번 경고 → 노이즈 | auto 라우팅에서만 즉시 경고, user-file은 20% 유지 |
| C4 | LOW | `has_side_probability`/`probability_for`가 unknown side를 조용히 `short_models`로 처리 | `ValueError`(training.sides_for_regime과 동일 정책) |

C1·C2를 실증으로 재현·확정:

```
[C1] range만 롱 보유, up/down 통째 미학습:
     missing_side_models = {'up':['long'], 'down':['short'], 'range':['short']}
     (수정 전에는 {} — up/down이 self.models에 없어 안 보임)

[C2] down/short가 통째 실패(down은 short 전용):
     multi-horizon training failed: could not fit required side(s): down/short, range/short
     default rc = 1
     (수정 전에는 skipped_regimes에만 기록되고 rc=0)
```

Angle B(제거된 동작)와 Angle C(크로스파일)는 **활성 결함 0건**. 확인 사항:
- `entry_probability=None`이 실제 트레이드에 기록될 수 없음(None 사이드는 임계값을 못 넘어 트레이드 미생성)
- 켈리 가드의 빈 `_ctx_genuine_sides` short-circuit 안전(BUY/SELL 신호는 항상 최소 `"long"`을 선언)
- `direction_policy`를 가진 객체는 실제 `RegimeModelBundle`과 테스트 스텁뿐(둘 다 새 메서드 보유)
- `run_config`·`kelly_sizing` 신규 키를 소비자들이 `.get(default)`로 읽어 스키마 파손 없음
- 고정 사이즈 Sharpe/profit_factor 불변(상수 약분)

---

## 5. 검증

```
tests/test_review_items.py          : SideCapabilityTests 6종 신설, 전체 통과
  - has_side_probability / probability_for(None≠0.0) / missing_side_models(정책 순회)
  - unknown side ValueError / BacktestResult.missing_side_models 직렬화
전체 스위트 (test_v718 제외)         : 251 passed, 1 deselected
게이트 실증                          : 완전 미학습 레짐 rc=1, --allow-partial-sides rc=0
missing-side 탐지                    : 카운터 0이어도 missing_side_models가 진실 보고
```

---

## 6. 남은 항목

- **live Kelly 배선**: 여전히 `entry_quantity = 0.001`. 이제 `has_side_probability`가 준비됐으므로, live 진입부도 같은 capability로 사이드별 사이징을 판단할 수 있다(선행 문제 해소).
- **Phase 4.5는 regime-aligned challenger**: horizon 블렌드 / Optuna 튜닝 / 확률 캘리브레이션 의미론은 Phase 4와 다르다.
- `DrawdownProtocol.reduce_factor` 미배선(K7).
