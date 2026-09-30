# CodexProject(7) 소스 검토 요약

## 전체 평가

`CodexProject(7)`에는 조용한 단방향(one-directional) 결함을 줄이기 위한 구조가 실제로 반영되어 있다.

주요 반영 내용:

```text
RegimeModelBundle.has_side_probability()
RegimeModelBundle.probability_for()
RegimeModelBundle.missing_side_models()
_ctx_genuine_sides
--allow-partial-sides
BacktestResult.missing_side_models
default_fallback / no_model 경고 강화
```

기존 bool 기반의 `_ctx_two_sided`보다 실제 사이드 확률 제공 여부를 확인하는 capability 방식이 더 안전하다.

다만 현재 상태에서도 재학습 전에 보완할 필요가 있는 중요 문제가 남아 있다.

---

# 1. CRITICAL — 이전 실행의 stale 모델 혼입 가능성

## 문제

학습 시 기존 출력 디렉터리를 삭제하지 않고 그대로 사용한다.

```text
artifacts/regime_stacking_model
artifacts/multi_horizon_model
```

현재 학습에서 생성하지 않은 과거 모델 파일이 남아 있으면, 로더가 파일 존재 여부만 보고 다시 로드할 수 있다.

예:

```text
현재 정책:
  up = long only

이전 실행에서 남은 파일:
  regime_up/short_model.json

결과:
  up 레짐에서 long + short 모두 활성화 가능
```

`missing_side_models()`는 필요한 사이드가 없는 경우만 검사하므로, 정책상 금지된 extra side는 탐지하지 못한다.

## 권장

가장 안전한 방식:

```text
임시 디렉터리에서 전체 학습
→ 필수 모델 검증
→ 기존 디렉터리를 atomic replace
```

로더도 파일 존재 여부가 아니라 `regime_run_summary.json`에 선언된 사이드만 로드하는 것이 좋다.

재학습 전 최소 대응:

```powershell
Remove-Item -Recurse -Force artifacts\regime_stacking_model -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force artifacts\multi_horizon_model -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force artifacts\backtest_results -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force artifacts\backtest_results_multi_horizon -ErrorAction SilentlyContinue
```

---

# 2. HIGH — min_regime_rows 미달 레짐이 게이트를 우회

## 문제

레짐 데이터가 `min_regime_rows`보다 적으면 학습 루프에서 바로 `continue`된다.

```text
down 레짐 데이터 부족
→ skipped_regimes에는 기록
→ missing_sides에는 기록되지 않음
→ partial-side 게이트 우회 가능
→ exit code 0 가능
```

즉 필수 레짐 전체가 빠졌는데도 학습 성공으로 종료될 수 있다.

## 권장

`min_regime_rows` 미달도 필수 사이드 누락으로 처리해야 한다.

예:

```text
missing_sides["down"] = ["short"]
```

기본 동작:

```text
필수 사이드 누락 → exit 1
```

명시적으로 허용한 경우에만:

```text
--allow-partial-sides
```

로 진행해야 한다.

---

# 3. HIGH — 자동 레짐에서 모델 누락 시 다른 레짐 모델로 거래

## 문제

Rule-based 또는 auto routing에서 감지된 레짐 모델이 없으면 `default_regime` 모델로 fallback한다.

예:

```text
감지 레짐:
  down

down 모델:
  없음

default_regime:
  range

결과:
  down 구간을 range 모델로 거래
```

현재는 경고만 출력하고 거래는 계속한다.

## 권장

모드를 구분해야 한다.

```text
user regime file의 빈 구간:
  default fallback 허용 가능

auto/rule regime에서 모델 누락:
  HOLD 또는 backtest 실패
```

자동 레짐에서 `default_fallback > 0`은 정상적인 fallback이 아니라 모델 누락일 가능성이 높다.

---

# 4. MEDIUM — _ctx_genuine_sides가 실제로 fail-closed가 아님

## 문제

현재 조건:

```python
if _ctx_genuine_sides and entered_side not in _ctx_genuine_sides:
```

빈 집합이면 조건 자체가 실행되지 않는다.

```text
set() → False
→ 검사 건너뜀
```

따라서 문서와 주석에서 설명한 fail-closed가 아니라 실제로는 fail-open이다.

현재 주요 경로에서는 신호 전에 사이드를 등록하므로 즉시 발생하는 활성 버그는 아닐 수 있지만, 새로운 라우팅 경로에서 사이드 등록을 빼먹으면 자동 차단되지 않는다.

---

# 5. 테스트 보강 필요

현재 capability 메서드 자체는 테스트하지만 실제 위험 경로 테스트가 부족하다.

추가 권장 테스트:

```text
min_regime_rows 미달 레짐이 exit 1인지
--allow-partial-sides에서만 통과하는지
stale 모델 파일이 무시되는지
정책에 없는 extra side를 거부하는지
auto/rule 모델 누락 시 default fallback을 금지하는지
빈 _ctx_genuine_sides가 실제로 거래를 차단하는지
```

---

# 6. 정상 반영 확인 항목

다음은 정상적으로 구현되어 있다.

## Side capability

```text
has_side_probability()
probability_for()
```

다음 두 상태를 구분한다.

```text
None:
  해당 사이드 확률을 계산할 모델이 없음

0.0:
  모델은 존재하며 성공 확률이 실제로 0
```

## 정책 기준 누락 탐지

`missing_side_models()`는 정책 전체를 기준으로 누락된 사이드를 탐지한다.

## Unknown side 처리

잘못된 side 문자열은 조용히 short로 처리하지 않고 `ValueError`를 발생시킨다.

## Backtest 결과 기록

```text
missing_side_models
longs_skipped_no_long_model
shorts_skipped_no_short_model
```

이 `backtest_summary.json`에 기록된다.

## 기존 Project(6) 개선 유지

```text
CentroidLinearClassifier
REGIME_SIDES 단일화
Loader symmetry
attach_labels 중복 제거
MappingProxyType
```

도 유지되고 있다.

---

# 7. 검증 결과

집중 테스트:

```text
tests/test_review_items.py
tests/test_stacking_ensemble.py
tests/test_feature_deactivation.py
tests/test_optuna_best_iteration.py
tests/test_regime_rules.py
```

결과:

```text
121 passed
```

추가 확인:

```text
btcusdt_quant compileall 통과
Python AST parse 통과
run_full_pipeline.sh bash -n 통과
```

전체 테스트 `251 passed`는 현재 검토 환경에서는 완전히 재현하지 못했다. 문서상 보고는 다음과 같다.

```text
251 passed
1 deselected
```

---

# 8. 재학습 전 우선 보완 권장

```text
1. 기존 출력 디렉터리 stale 모델 혼입 방지
2. min_regime_rows 스킵을 missing_sides 게이트에 포함
3. auto/rule 레짐 모델 누락 시 default fallback 대신 HOLD
4. _ctx_genuine_sides의 실제 fail-closed 조건 수정
```

특히 1번과 2번은 재학습 전에 처리하는 것이 안전하다.

---

# 9. 현재 소스로 재학습할 경우 필수 체크

재학습 전:

```text
기존 모델/백테스트 artifact 디렉터리 완전 삭제
```

재학습 후:

```text
skipped_regimes = {}
missing_sides = {}
missing_side_models = {}
default_fallback = 0
no_model = 0
```

파일 구조:

```text
regime_up/
  long_model.json
  short_model.json 없어야 함

regime_down/
  short_model.json
  long_model.json 없어야 함

regime_range/
  long_model.json
  short_model.json
```

이 조건까지 확인해야 Phase 4와 Phase 4.5 비교를 신뢰할 수 있다.
