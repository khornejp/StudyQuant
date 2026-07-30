# Regime 탐지 · 라우팅 (btcusdt_quant)

이 레포는 시장을 **up / down / range** 세 regime으로 나누고, regime별로 진입 모델을 학습·라우팅한다.
regime은 코드 품질과 누수가 동시에 걸리는 지점이라 특히 규율이 중요하다. 관련 모듈: `regime_rules.py`
(규칙 기반 causal 탐지기), `regime_classifier.py`, `regimes.json`(정적 hindsight 라벨).

## 세 가지 불변식

1. **Causal & deterministic.** 각 시점의 regime은 그 시점까지의 feature와, 학습 구간에서 한 번 fit한
   정규화 통계로만 결정된다. 순차 상태(hysteresis)는 과거 행에만 의존한다. **미래를 보지 않는다.**
2. **Train/serve parity.** 탐지기 `fit()`은 학습 행에서 per-feature `(mean, std)`를 계산하고 `to_dict`로
   저장한다. backtest/live는 `from_dict`로 **같은 통계**를 복원해 점수를 낸다 — live 버퍼에 재-fit하지
   않는다. 그래야 학습 때의 bucketing과 serve 때의 bucketing이 일치한다.
3. **라우터를 바꾸면 재-bucketing.** 탐지기(bucketing)를 바꾸면 regime-aware 진입 모델은 **그 새
   bucketing으로 재학습**해야 한다. 탐지기만 갈아끼우면 train/serve skew가 생긴다. 이 커플링을 잊지 않는다.

## Hindsight 라벨(`regimes.json`)의 용도

`regimes.json`의 고정 regime 구간은 **사후(hindsight)로 매긴 것**이라 look-ahead가 있다. 이 라벨로 낸
백테스트는 "regime 라우팅이 완벽할 때 모델이 얼마나 하는가"를 보는 **진단·상한선**일 뿐, live/forward
성능이 아니다. 이 둘을 혼동한 결론을 내지 않는다. 실거래·forward 평가는 반드시 실시간 탐지기로 한다.
(파일 상단 주석에 이 경고와 gap-fill 방식이 문서화돼 있으니 참고.)

## 규칙 기반 탐지기 패턴 (`regime_rules.py`)

새 regime 로직을 짜거나 고칠 때 이 구조를 따른다:

- 설정은 `MultiFeatureRegimeConfig`(frozen dataclass)에 **모든 가중치·임계값을 필드로 노출**해 튜닝
  가능하게 한다. 상수를 코드에 흩뿌리지 않는다.
- 여러 점수(trend / volatility / range / breakout)를 결합하되, 긴 timeframe(regime anchor)과 짧은
  timeframe(confirmation/timing)의 역할을 섞지 않는다.
- 결정에는 **entry/exit hysteresis와 minimum-hold**를 둬서 regime이 매 봉 튀지 않게 한다.
- 정규화에는 std floor(`_STD_FLOOR = 1e-9`)를 써서 분산이 0에 가까운 feature에서 div-by-zero·runaway
  z-score를 막는다.
- 출력 클래스는 기존 진입 모델 bucket과 동일한 `("up", "down", "range")`를 유지한다.

## 라우팅 · 추론

- "이 시점은 어떤 regime인가 → 어떤 모델로 보낼 것인가"를 한 경로로 모은다. regime 전환 직후·미분류 시의
  처리를 명시적으로 정의한다.
- regime별 표본 수를 로깅한다. 특정 regime(예: 급락 down 구간)은 표본이 적어 과적합되기 쉽다 — 너무 적으면
  모델을 나누는 것이 오히려 해로울 수 있으니 사용자에게 알린다.

## 평가

- regime별 성능과, 실제 운용처럼 시간순으로 이어붙인 통합 성능을 **둘 다** 본다.
- regime별로만 좋고 통합이 나쁘면, 라우팅·전환에서 정보가 새거나(누수) 전환 비용이 숨었을 수 있다.
- hindsight 라우팅 성능과 실시간 탐지 라우팅 성능의 격차가 크면, 그 격차가 곧 "라우터가 실제로 얼마나
  어려운가"를 말해준다 — 이 격차를 성능으로 착각하지 않는다.

## 필수 4-way 비교

regime-aware 결과를 평가할 때 다음 네 경로를 같은 split, label, 비용으로 비교한다.

1. regime detector 자체의 classification/calibration 결과
2. hindsight/true regime을 사용한 oracle routing
3. causal predicted regime을 사용한 실제 routing
4. regime을 사용하지 않는 unified entry model

해석:

- oracle은 좋고 predicted만 나쁘면 detector, transition, hysteresis 또는 routing lag 문제다.
- oracle도 나쁘면 entry model, label, feature 또는 regime 분할 자체 문제다.
- unified가 predicted보다 좋으면 현재 bucketing이 표본을 쪼개고 edge를 약화시킨다.
- detector accuracy가 높아도 중요한 전환 구간에서 틀리면 trading 결과는 나쁠 수 있으므로 confusion뿐 아니라
  transition-window 성능과 비용을 본다.

## Routing diagnostics 범위

라우팅 진단은 해당 OOS 평가 기간에 한정해 계산한다. 전체 2020~2025 분포와 confusion을 특정 2025 test 구간의
성능 근거로 사용하지 않는다. train/validation/test별 regime count, route count, fallback count를 따로 저장한다.
