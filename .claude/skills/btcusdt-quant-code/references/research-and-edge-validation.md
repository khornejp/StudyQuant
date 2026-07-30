# Research · Edge validation · 실험 governance

이 문서는 “모델 metric이 개선됐는가”가 아니라 “반복 가능하고 거래 가능한 OOS edge인가”를 판단하는 규칙이다.

## Edge로 인정하지 않는 증거

다음은 단독으로 충분하지 않다.

- train 또는 validation loss 감소
- accuracy 상승
- Optuna best value 개선
- SHAP/gain importance
- 한 기간에서만 높은 Sharpe 또는 profit factor
- 반복 threshold search 후 선택된 최고 결과
- 거래 수가 매우 적은 고수익 결과

## 필수 기준모델

모든 실험은 가능한 한 같은 데이터, split, label, 비용으로 다음과 비교한다.

1. constant probability = train positive rate
2. always no-trade
3. simple momentum
4. simple mean reversion
5. previous accepted candidate
6. shuffled-label/permutation negative control

복잡한 CatBoost 모델이 단순 기준을 비용 후 이기지 못하면 채택하지 않는다.

## 예측 지표

최소 보고:

- logloss
- constant baseline logloss
- logloss improvement
- Brier score
- PR-AUC
- ROC-AUC
- calibration error 또는 reliability table
- positive rate
- prediction quantiles/distribution
- sample count

imbalanced label에서 accuracy를 주 지표로 사용하지 않는다.

## 거래 지표

최소 보고:

- trade count
- gross expectancy per trade
- net expectancy per trade
- total and per-trade fee/slippage/funding
- win rate
- average win / average loss
- payoff ratio
- profit factor
- maximum drawdown
- turnover
- exposure
- long/short 분리 결과
- cost stress 결과

Sharpe만 보고하지 않는다. 거래 수와 수익 집중도도 같이 본다.

## 안정성 분해

다음 축으로 결과를 나눈다.

- walk-forward fold
- calendar year/month 또는 half-year
- regime
- prediction horizon
- volatility bucket
- long / short
- random seed

전체 수익의 대부분이 한 달, 한 regime, 한 seed에 집중되면 edge를 확정하지 않는다.

## Feature 연구 절차

각 feature 또는 feature group은 다음 순서로 평가한다.

1. 경제적/미시구조 가설
2. earliest availability와 timestamp contract
3. missing/warmup/coverage 감사
4. 단변량 진단은 참고만 수행
5. 기존 모델에 최소 변경으로 추가
6. 동일한 walk-forward OOS 비교
7. grouped ablation
8. 여러 seed
9. 비용 stress
10. 기간/regime 안정성

SHAP importance만으로 feature를 남기지 않는다. 제거했을 때 OOS 성능이 안정적으로 악화되는지가 더 중요하다.

## Regime 연구 절차

항상 다음 네 결과를 같은 조건으로 비교한다.

1. detector metrics
2. oracle routing
3. predicted causal routing
4. unified model

oracle만 좋으면 detector 문제다. oracle도 나쁘면 entry model, label, feature 또는 regime 정의 문제다.
unified가 predicted보다 좋으면 regime 분리가 현재 데이터에서 해롭다.

## Seed와 HPO

- stochastic model은 여러 seed를 사용한다.
- 평균뿐 아니라 최악/최선과 분산을 보고한다.
- Optuna trial 수, search space, early stop, sampler 설정을 기록한다.
- HPO 중 본 validation을 threshold/calibration에도 반복 사용하지 않는다.
- best trial 하나만 보고 결론 내리지 않는다.

## Multiple testing

시도한 feature, label, regime, horizon, threshold, HPO 조합 수를 기록한다. 실험을 많이 할수록 우연한 최고값이
나올 확률이 커진다.

최소한 다음을 기록한다.

- experiment id
- parent/baseline experiment
- git commit
- data fingerprint 또는 artifact hash
- config hash
- train/validation/test range
- seed
- feature groups
- label definition
- cost assumptions
- HPO trial count
- final test used 여부

가능하면 deflated Sharpe, probability of backtest overfitting, bootstrap confidence interval처럼 선택 편향을 점검하는
통계를 추가한다. 구현하지 못했다면 실험 수와 선택 과정을 투명하게 보고한다.

## Final test 보호

final test는 마지막 증거다. feature, label, hyperparameter, calibration, threshold, regime rule, 비용 가정을 고르는 데
사용하지 않는다.

이미 여러 번 봤다면:

- untouched라고 부르지 않는다.
- 오염 시점과 어떤 결정에 영향을 줬는지 기록한다.
- 가능하면 이후의 새로운 기간을 holdout으로 확보한다.

## 기본 acceptance gate

아래는 절대 법칙이 아니라 기본 증거 요구사항이다.

후보는 보통 다음을 만족해야 한다.

- 대부분의 walk-forward fold에서 positive net expectancy
- baseline보다 일관된 predictive/trading 개선
- 1.5x 비용에서도 대체로 양수, 2x 비용에서 급격히 붕괴하지 않음
- 한 기간 또는 한 regime에 수익이 과도하게 집중되지 않음
- 여러 seed에서 방향성이 유지됨
- grouped ablation에서 핵심 feature 가설이 재현됨
- shuffled label에서는 성능이 사라짐
- 충분한 거래 수와 합리적인 confidence interval
- final test가 선택 과정에 사용되지 않음

## Verdict

- `ACCEPT`: 비용 후 OOS 개선과 안정성이 충분히 재현됨
- `PROMISING BUT UNPROVEN`: 개선은 있으나 기간, 거래 수, seed, 비용 stress 중 일부가 부족함
- `REJECT`: baseline을 안정적으로 이기지 못하거나 비용 후 음수
- `INVALID DUE TO LEAKAGE`: 시점, split, fit, test contamination 문제
- `INCONCLUSIVE DUE TO SAMPLE SIZE`: 거래 또는 독립 사건 수가 부족함

## 한 번의 실험은 하나의 질문만

feature, label, model family, threshold, cost를 동시에 바꾸면 무엇이 개선을 만들었는지 알 수 없다. 변경 surface를
최소화하고, 가장 정보가치가 높은 다음 실험 하나를 제안한다.
