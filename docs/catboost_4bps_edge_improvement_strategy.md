# CatBoost 기반 퀀트 모델의 4bps 거래비용 극복 전략

## 1. 문제 정의

현재 CatBoost 기반으로 퀀트 모델을 학습하고 있는데, 실제 거래에서 모델이 만들어내는 평균적인 가격 우위가 약해서 거래비용 약 4bps를 넘지 못하고 손실이 발생하는 상황을 가정한다.

예를 들어 모델이 방향 자체는 맞추더라도:

```text
예상 수익: +2.5bps
거래비용:  -4.0bps
--------------------
Net:      -1.5bps
```

라면 예측 방향이 맞았음에도 실제 매매에서는 손실이 난다.

이 경우 바로 모델을 더 복잡한 모델로 바꾸는 방법도 가능하지만, 우선 다음을 확인해야 한다.

```text
1. Target이 거래비용을 반영하고 있는가?
2. Prediction confidence가 실제 수익폭과 연결되는가?
3. 약한 신호까지 너무 많이 거래하고 있지 않은가?
4. 모델 입력 Feature에 충분한 Alpha 정보가 있는가?
5. 현재 CatBoost의 모델 용량이 실제로 부족한가?
```

---

# 2. 핵심 결론

단순히:

```text
4bps를 못 넘긴다
→ CatBoost가 약하다
→ 더 강한 모델로 교체
```

라고 바로 판단하기보다는 다음 순서가 더 합리적이다.

```text
현재 CatBoost 분석
        ↓
Cost-aware Target
        ↓
Threshold 최적화
        ↓
Expected Return 모델 추가
        ↓
새로운 Feature 추가
        ↓
LightGBM / XGBoost 비교
        ↓
Ensemble
        ↓
Temporal Neural Network
```

즉 **모델 교체보다 Target, Threshold, Feature를 먼저 점검하는 것이 중요하다.**

---

# 3. 4-fold와 미세 패턴 탐지의 관계

현재 4 folds로 학습하고 있다고 해서 모델이 미세한 패턴을 덜 잡는 것은 아니다.

Fold 수는 주로:

```text
검증 안정성
일반화 성능 평가
과적합 확인
```

과 관련된다.

반면 미세한 패턴을 잡는 능력은 주로 다음 요소에 의해 결정된다.

```text
Feature
Target
Model Capacity
Hyperparameter
Prediction Horizon
Sampling 방식
Regularization
```

따라서:

```text
4 folds → 8 folds
```

로 바꾼다고 해서 자동으로 더 세밀한 패턴을 잡는 것은 아니다.

---

# 4. Time Series에서 4-fold는 충분히 합리적일 수 있다

예를 들어 다음처럼 시간 순서를 지키는 Walk-forward 또는 Purged CV라면 4 folds도 충분히 의미가 있다.

```text
Fold 1
TRAIN ───────────────
                  VALID

Fold 2
TRAIN ─────────────────────
                        VALID

Fold 3
TRAIN ───────────────────────────
                              VALID

Fold 4
TRAIN ─────────────────────────────────
                                    VALID
```

특히 금융 시계열에서는 일반 Random K-Fold보다:

```text
Walk-forward
Purged K-Fold
Embargo
Temporal split
```

이 더 중요하다.

Fold 개수 자체보다는 **미래 데이터 누수 없이 검증되고 있는가**가 더 중요하다.

---

# 5. 현재 Target이 문제일 가능성

예를 들어 현재 Target이 단순히:

```python
future_price > current_price
```

라면 모델은 다음 두 상황을 모두 같은 정답으로 본다.

```text
+1bps 상승
+20bps 상승
```

둘 다:

```text
LONG = 1
```

이 된다.

하지만 실제 거래에서는 완전히 다르다.

```text
+1bps
→ 거래비용 4bps를 못 넘음

+20bps
→ 충분한 순수익 가능
```

즉 Direction Classification 자체는 맞지만 **경제적으로 의미 없는 작은 움직임까지 정답으로 취급하는 문제**가 발생한다.

---

# 6. Cost-aware Target으로 변경

거래비용이 약 4bps라면 Target 자체를 비용 기준으로 조정하는 것이 좋다.

예를 들어:

```text
future_return > +6bps
→ LONG

future_return < -6bps
→ SHORT

그 사이
→ NOTRADE
```

또는 더 보수적으로:

```text
+8bps 이상
→ LONG

-8bps 이하
→ SHORT

-8bps ~ +8bps
→ NOTRADE
```

로 구성할 수 있다.

---

# 7. 왜 4bps가 아니라 6~10bps인가?

실제 거래에서는 단순 명목 수수료 외에도 여러 비용이 존재한다.

```text
Maker/Taker Fee
Slippage
Spread
체결 지연
시장 충격
Prediction Error
```

따라서 실질적인 거래비용이 4bps라면 모델이 찾아야 할 최소 Gross Edge는 일반적으로 그보다 높아야 한다.

예:

```text
Estimated Cost = 4bps
Safety Margin  = 2~6bps
```

그러면 Target 기준은:

```text
6~10bps 이상
```

을 실험해볼 수 있다.

---

# 8. Threshold가 너무 낮은 문제

현재 모델이 예를 들어:

```text
P(Long) > 0.50
```

이면 거래하도록 되어 있다면 약한 신호까지 너무 많이 포함될 수 있다.

중요한 것은 Prediction Probability와 실제 Return의 관계를 확인하는 것이다.

예를 들어 다음처럼 분석한다.

| Prediction Probability | 실제 평균 Future Return |
|---:|---:|
| 0.50 ~ 0.55 | +0.3bps |
| 0.55 ~ 0.60 | +1.5bps |
| 0.60 ~ 0.65 | +3.1bps |
| 0.65 ~ 0.70 | +4.8bps |
| 0.70 ~ 0.75 | +7.2bps |
| 0.75 이상 | +10.5bps |

이런 결과라면 CatBoost 자체는 이미 강한 신호를 분리하고 있을 가능성이 있다.

문제는 단순히:

```text
P > 0.5
```

에서 너무 많은 거래를 하고 있기 때문일 수 있다.

---

# 9. Threshold 최적화

예를 들어:

```text
P(Long) > 0.70
```

일 때만 Long 진입하도록 하면 거래 횟수는 줄어들 수 있다.

하지만:

```text
평균 Gross Edge
```

는 크게 올라갈 가능성이 있다.

예:

## 기존

```text
1000 trades

Gross Edge = +2.5bps
Cost       = -4.0bps

Net        = -1.5bps/trade
```

## 개선

```text
180 trades

Gross Edge = +11bps
Cost       = -4bps

Net        = +7bps/trade
```

실전 퀀트에서는 거래 횟수보다 **Trade당 Expected Value**가 훨씬 중요하다.

---

# 10. 거래 횟수를 줄이는 것이 나쁜 것은 아니다

흔히 다음과 같이 생각하기 쉽다.

```text
신호가 많다
→ 좋은 모델
```

하지만 실제로는 반드시 그렇지 않다.

더 좋은 구조는:

```text
약한 신호 1000개
```

보다:

```text
강한 신호 150개
```

일 수 있다.

특히 거래비용이 존재할 때는:

```text
NoTrade
```

를 적극적으로 활용해야 한다.

---

# 11. CatBoostClassifier에서 CatBoostRegressor로 확장

현재 모델이 Direction Classification이라면 다음 실험을 추천한다.

```text
CatBoostClassifier
+
CatBoostRegressor
```

Regressor는 단순히:

```text
오를까?
```

가 아니라:

```text
얼마나 오를까?
```

를 학습한다.

---

# 12. Return을 직접 Target으로 학습

예를 들어:

```python
target_bps = (
    future_price / current_price - 1.0
) * 10000.0
```

로 만들 수 있다.

예:

```text
future return = +0.0012
→ +12bps

future return = -0.00035
→ -3.5bps
```

그러면 CatBoostRegressor의 예측값이:

```text
expected_return_bps
```

가 된다.

---

# 13. Live 진입 규칙 예시

예를 들어:

```python
if pred_return_bps > 7:
    LONG
elif pred_return_bps < -7:
    SHORT
else:
    NOTRADE
```

처럼 구성할 수 있다.

이 방식은 거래비용 기준을 모델 출력과 직접 연결하기 쉽다.

---

# 14. Direction Model + Return Model 조합

더 좋은 구조는 두 모델을 같이 사용하는 것이다.

```text
                    Market Data
                         ↓
                   Feature Set
                         ↓
             ┌───────────┴───────────┐
             │                       │
      Direction Model          Return Model
    CatBoostClassifier       CatBoostRegressor
             │                       │
             ↓                       ↓
        P(Long/Short)         Expected Return
             │                       │
             └───────────┬───────────┘
                         ↓
                     Trade Gate
                         ↓
                 Long / Short / NoTrade
```

---

# 15. Long 진입 예시

```python
if (
    p_long > 0.65
    and expected_return_bps > 7
):
    signal = "LONG"
```

---

# 16. Short 진입 예시

```python
if (
    p_short > 0.65
    and expected_return_bps < -7
):
    signal = "SHORT"
```

그 외에는:

```text
NOTRADE
```

로 처리한다.

이렇게 하면 Direction Model과 Return Model이 서로 Filter 역할을 한다.

---

# 17. Expected Return 대신 MFE를 Target으로 사용하는 방법

Terminal Return만 예측하는 대신 일정 시간 동안의 최대 유리한 움직임을 예측할 수도 있다.

예:

```text
MFE
Maximum Favorable Excursion
```

Long 기준:

```text
미래 N분 동안 현재가 대비 최대 상승폭
```

Short 기준:

```text
미래 N분 동안 현재가 대비 최대 하락폭
```

이를 bps로 변환해서 Target으로 사용할 수 있다.

예:

```text
현재 가격 = 100
15분 내 최고가 = 100.12

Long MFE = +12bps
```

이런 Target은 실제 Take Profit 가능성을 평가할 때 유용할 수 있다.

---

# 18. Terminal Return과 MFE의 차이

예를 들어 미래 15분 동안:

```text
현재       100.00
중간 최고  100.15
15분 후    100.02
```

이면:

```text
Terminal Return = +2bps
MFE             = +15bps
```

가 된다.

실제 전략이 중간에 TP를 사용할 수 있다면 MFE Target이 더 적합할 수 있다.

반대로 고정 Horizon 종료가 실제 매매 규칙이라면 Terminal Return이 더 자연스럽다.

---

# 19. 모델을 바꾸는 것도 충분히 가능하다

Target과 Threshold를 조정한 뒤에도 CatBoost가 충분한 Edge를 만들지 못한다면 모델 교체를 실험할 가치가 있다.

후보:

| 모델 | 특징 |
|---|---|
| CatBoost | 안정적인 강력한 baseline |
| LightGBM | 매우 세밀한 Tree split 가능 |
| XGBoost | 비선형 관계와 정교한 split에 강함 |
| CatBoost + LightGBM | 서로 다른 오류를 보완 |
| TCN / 1D CNN | 연속적인 시계열 패턴 포착 |
| Transformer | 긴 시계열 문맥 학습 |
| GRU / LSTM | 전통적인 Sequential Model |

---

# 20. LightGBM이 미세한 패턴에 유리할 수 있는 이유

LightGBM은 다음 Hyperparameter를 통해 매우 세밀한 Decision Boundary를 만들 수 있다.

```text
num_leaves
max_depth
min_data_in_leaf
feature_fraction
bagging_fraction
lambda_l1
lambda_l2
```

특히:

```text
num_leaves 증가
min_data_in_leaf 감소
```

를 통해 더 세부적인 구간을 분리할 수 있다.

다만 그만큼 Overfitting 위험도 커진다.

---

# 21. CatBoost도 Capacity를 늘릴 수 있다

CatBoost를 바로 버리기 전에 모델 Capacity 자체를 점검하는 것도 필요하다.

예:

```text
depth
iterations
learning_rate
l2_leaf_reg
random_strength
min_data_in_leaf
border_count
```

특히 너무 강한 Regularization이 걸려 있으면 작은 Market Pattern이 뭉개질 수 있다.

반대로 Capacity를 너무 높이면 금융 Noise를 학습하게 된다.

따라서 동일한 Walk-forward CV에서 성능을 비교해야 한다.

---

# 22. 모델을 비교할 때 Accuracy만 보면 안 된다

실제 목적이 Trading이라면 다음 Metric이 더 중요하다.

```text
Average Gross Return / Trade
Average Net Return / Trade
Profit Factor
Win Rate
Trade Count
Expected Value
Maximum Drawdown
Sharpe Ratio
Sortino Ratio
PnL
```

Classification Metric도 함께 본다.

```text
LogLoss
AUC
PR-AUC
Precision
Recall
Calibration
```

하지만 최종 판단은 반드시 Cost-aware Backtest를 통해 해야 한다.

---

# 23. Prediction Probability 구간별 Return 분석

현재 모델을 평가할 때 가장 먼저 추천하는 분석이다.

예:

```text
0.50 ~ 0.55
0.55 ~ 0.60
0.60 ~ 0.65
0.65 ~ 0.70
0.70 ~ 0.75
0.75 ~ 0.80
0.80+
```

각 구간마다 다음을 계산한다.

```text
Sample Count
Average Future Return
Median Future Return
Win Rate
Gross PnL
Net PnL after Cost
```

이를 통해:

```text
모델이 강한 신호를 실제로 구분하고 있는가?
```

를 확인할 수 있다.

---

# 24. Probability Calibration도 확인

CatBoost가 출력한:

```text
0.7
```

이 실제로 70%의 의미를 갖는지 확인할 필요가 있다.

Calibration이 나쁘다면:

```text
P = 0.7
```

이 반드시 강한 Edge를 의미하지 않을 수 있다.

필요하면:

```text
Platt Scaling
Isotonic Regression
```

등을 적용할 수도 있다.

다만 금융에서는 단순 확률 정확도보다:

```text
Probability Bucket별 Expected Return
```

이 더 중요하다.

---

# 25. 새로운 Feature가 모델 교체보다 중요할 수 있다

모델은 입력 Feature에 없는 정보를 새로 만들어낼 수 없다.

예를 들어 현재 입력이 대부분:

```text
OHLCV
Return
Moving Average
ATR
Trend Slope
Volatility
Multi-Timeframe Price Feature
```

라면 CatBoost에서 Transformer로 바꿔도 정보 자체가 부족하면 Edge 개선이 제한적일 수 있다.

---

# 26. Binance Futures Metrics 추가

새롭게 고려할 수 있는 Feature:

```text
Open Interest
Global Long/Short Ratio
Top Trader Account Ratio
Top Trader Position Ratio
Taker Buy/Sell Ratio
```

이들은 기존 Price Feature와 다른 정보 축을 제공한다.

```text
Price Action
+
Trend
+
Volatility
+
Positioning
+
Order Flow
```

형태가 된다.

---

# 27. Metrics가 4bps Edge 문제에 도움이 될 수 있는 이유

예를 들어 가격 Feature만 보면:

```text
상승 확률 56%
```

정도로 애매할 수 있다.

하지만 동시에:

```text
Top Trader Long 증가
OI 증가
Taker Buy 증가
```

가 나타난다면 강한 Long 신호일 가능성이 높아질 수 있다.

반대로:

```text
가격 상승
Retail Long 급증
Top Trader Short 증가
Taker Sell 우세
```

라면 Long Trap 가능성을 Filter할 수 있다.

즉 Metrics는 약한 Trade를 걸러내는 데 도움이 될 수 있다.

---

# 28. 추천 실험 순서

현재 상황에서는 다음 순서를 추천한다.

## Step 1

현재 CatBoost의 Prediction Probability 구간별 실제 Return을 분석한다.

```text
P(Long)
→ Average Future Return
→ Net Return after 4bps
```

---

## Step 2

Threshold를 최적화한다.

예:

```text
0.50
0.55
0.60
0.65
0.70
0.75
```

각 Threshold별로:

```text
Trade Count
Average Gross bps
Average Net bps
Profit Factor
MDD
Total PnL
```

을 비교한다.

---

## Step 3

Target을 Cost-aware 방식으로 바꾼다.

예:

```text
+8bps 이상 → LONG
-8bps 이하 → SHORT
그 사이 → NOTRADE
```

---

## Step 4

CatBoostRegressor로 Expected Return을 직접 예측한다.

```text
expected_return_bps
```

를 만들어:

```text
expected_return_bps > threshold
```

일 때만 거래한다.

---

## Step 5

Direction Model + Return Model 조합을 테스트한다.

```text
Probability 조건
+
Expected Return 조건
```

둘 다 통과한 경우만 진입한다.

---

## Step 6

Binance Futures Metrics를 추가한다.

```text
Long/Short
Top Trader
Taker
Open Interest
```

---

## Step 7

동일 데이터와 동일 4-fold 환경에서 LightGBM을 비교한다.

중요한 것은:

```text
동일 Target
동일 Feature
동일 CV Split
동일 거래비용
동일 Backtest
```

이다.

---

## Step 8

CatBoost와 LightGBM이 서로 다른 Edge를 보이면 Ensemble을 테스트한다.

예:

```text
CatBoost Probability
+
LightGBM Probability
```

또는:

```text
CatBoost Direction
+
LightGBM Expected Return
```

등의 조합이 가능하다.

---

## Step 9

Tree Model에서 의미 있는 Edge가 확인되었지만 한계가 명확할 경우 Temporal Model을 테스트한다.

후보:

```text
TCN
1D CNN
Transformer
```

---

# 29. 추천 A/B 테스트 구조

다음과 같이 실험하면 원인을 비교하기 쉽다.

```text
A
Current CatBoost

B
CatBoost + Threshold Optimization

C
CatBoost + Cost-aware Target

D
CatBoost Classifier + CatBoost Regressor

E
D + Binance Futures Metrics

F
LightGBM + 동일 Target / Feature

G
CatBoost + LightGBM Ensemble
```

각 실험마다 동일한 4-fold와 동일 Backtest 조건을 사용한다.

---

# 30. 최종 판단 기준

모델 교체 여부는 다음 기준으로 결정하는 것이 좋다.

## CatBoost 유지

다음과 같은 경우:

```text
High-confidence 구간에서는 >4bps Edge 존재
Threshold를 높이면 Net EV가 양수
Metrics 추가 후 개선
Cost-aware Target에서 개선
```

즉 모델 자체가 문제라기보다 Signal Selection 문제일 가능성이 높다.

---

## 모델 교체 또는 병행

다음과 같은 경우:

```text
Prediction Confidence와 실제 Return의 관계가 약함
어떤 Threshold에서도 Net EV가 음수
Feature 추가 후에도 개선 없음
CatBoost Capacity 변경에도 성능 정체
LightGBM이 동일 CV에서 안정적으로 우수
```

이 경우 LightGBM이나 다른 모델을 병행할 가치가 있다.

---

# 31. 핵심 요약

현재 거래비용이 4bps인데 실제 거래 Edge가 이를 넘지 못한다면, 더 미세한 패턴을 잡는 모델을 테스트하는 것은 충분히 가능한 방법이다.

하지만 가장 먼저 확인해야 할 것은 모델 종류보다:

```text
Target
Threshold
Expected Return
Feature
```

이다.

특히:

```text
방향을 맞히는 모델
```

에서:

```text
거래비용을 넘을 정도로 크게 움직이는 구간을 찾는 모델
```

로 목적을 바꾸는 것이 중요하다.

추천 우선순위:

```text
1. Prediction Probability별 실제 bps 분석
2. Threshold 최적화
3. Cost-aware Target
4. CatBoostRegressor
5. Direction + Return Dual Model
6. Binance Futures Metrics 추가
7. LightGBM 비교
8. CatBoost + LightGBM Ensemble
9. 필요 시 TCN / Transformer
```

그리고 현재의 **4-fold 자체가 미세한 패턴을 못 잡는 원인이라고 볼 필요는 없다.**

4-fold는 검증 방법이고, 실질적인 Edge는 주로:

```text
Feature
Target
Model Capacity
Horizon
Trade Gate
```

에서 결정된다.
