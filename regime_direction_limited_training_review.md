# Regime별 방향 제한 학습 구조 검토 보고서

## 1. 개요

현재 설계는 다음과 같다.

```text
상승장:
    Long만 학습

하락장:
    Short만 학습

횡보장:
    NoTrade로 학습
```

전략 철학 자체는 타당하다.

```text
상승장에서는 Long 위주로 매매한다.
하락장에서는 Short 위주로 매매한다.
횡보장에서는 거래하지 않는다.
```

다만 학습 라벨을 어떻게 구성하느냐에 따라 모델이 유효한 매매 타이밍을 학습할 수도 있고, 단순히 regime과 action을 외우는 잘못된 모델이 될 수도 있다.

---

## 2. 현재 구조의 핵심 위험

만약 현재 학습 데이터가 아래처럼 구성되어 있다면 위험하다.

```text
상승장 데이터 전체 → Long 라벨
하락장 데이터 전체 → Short 라벨
횡보장 데이터 전체 → NoTrade 라벨
```

이 구조에서는 모델이 실제 진입 타이밍을 학습하지 않는다.

모델이 배우는 것은 다음과 같다.

```text
상승장이다 → 무조건 Long
하락장이다 → 무조건 Short
횡보장이다 → 무조건 NoTrade
```

이 경우 CatBoost 모델을 학습시킬 필요가 거의 없다. 단순 룰과 동일해진다.

```python
if regime == "up":
    signal = "LONG"
elif regime == "down":
    signal = "SHORT"
else:
    signal = "NO_TRADE"
```

실전에서는 상승장 안에서도 들어가면 안 되는 구간이 많고, 하락장 안에서도 Short를 치면 안 되는 구간이 많다.

따라서 모델은 다음을 배워야 한다.

```text
상승장에서 언제 Long을 해야 하는가?
하락장에서 언제 Short를 해야 하는가?
횡보장에서 정말 매매를 하지 않을 것인가?
```

---

## 3. 올바른 학습 구조

## 3.1 상승장 모델

상승장에서는 Long만 노리는 방향은 맞다.

하지만 라벨은 단순히 전부 Long이면 안 된다. 상승장 안에서도 Long 성공 여부를 학습해야 한다.

```text
상승장 데이터만 사용

label = 1:
    현재 시점에서 Long 진입 시 TP가 SL보다 먼저 도달

label = 0:
    Long 진입 실패
    TP 미도달
    SL 먼저 도달
    수수료 / 슬리피지 / 안전마진 기준 미달
```

즉 모델은 다음과 같이 정의한다.

```text
up_long_model:
    1 = Long 성공
    0 = Long 실패 / 진입 금지
```

이렇게 해야 상승장 안에서도 매수 타이밍을 학습할 수 있다.

---

## 3.2 하락장 모델

하락장에서는 Short만 노리는 방향은 맞다.

하지만 하락장 데이터 전체를 Short로 라벨링하면 안 된다. 하락장 안에서도 Short 성공 여부를 학습해야 한다.

```text
하락장 데이터만 사용

label = 1:
    현재 시점에서 Short 진입 시 TP가 SL보다 먼저 도달

label = 0:
    Short 진입 실패
    TP 미도달
    SL 먼저 도달
    수수료 / 슬리피지 / 안전마진 기준 미달
```

즉 모델은 다음과 같이 정의한다.

```text
down_short_model:
    1 = Short 성공
    0 = Short 실패 / 진입 금지
```

이렇게 해야 하락장 안에서도 매도 타이밍을 학습할 수 있다.

---

## 3.3 횡보장 처리

횡보장을 전부 NoTrade로만 학습시키는 것은 모델 관점에서 큰 의미가 없다.

횡보장에서 아예 매매하지 않을 계획이라면 모델을 만들 필요 없이 룰로 처리하는 것이 더 낫다.

```python
if regime == "range":
    signal = "NO_TRADE"
```

즉 횡보장은 다음처럼 처리한다.

```text
range:
    학습 대상에서 제외
    실전 추론 시 NoTrade rule 적용
```

다만 횡보장에서 평균회귀 전략을 사용할 계획이라면 별도 모델을 만들 수 있다.

```text
range_long_model:
    range low 근처 Long 성공 여부

range_short_model:
    range high 근처 Short 성공 여부
```

하지만 현재 설계가 “횡보장은 거래하지 않는다”라면, range 모델은 만들지 않고 NoTrade rule로 처리하는 것이 더 깔끔하다.

---

## 4. 추천 최종 구조

현재 전략 의도에 가장 적합한 구조는 다음이다.

```text
RegimeDetector
    ├─ 상승장 up
    │    └─ up_long_model
    │         1 = Long 성공
    │         0 = Long 실패 / 진입 금지
    │
    ├─ 하락장 down
    │    └─ down_short_model
    │         1 = Short 성공
    │         0 = Short 실패 / 진입 금지
    │
    └─ 횡보장 range
         └─ NoTrade rule
```

즉 최종 모델은 최소 다음 2개면 된다.

```text
up_long_model
down_short_model
```

횡보장은 모델이 아니라 룰로 처리한다.

```text
range_no_trade_rule
```

---

## 5. 실전 추론 흐름

실전에서는 다음 순서로 동작해야 한다.

```text
1. 현재 시점의 과거 데이터만으로 regime 판단
2. regime이 상승장이면 up_long_model 호출
3. regime이 하락장이면 down_short_model 호출
4. regime이 횡보장이면 바로 NoTrade
5. 모델 확률과 EV를 계산
6. EV가 양수이고 threshold를 넘을 때만 진입
```

예시 의사코드는 다음과 같다.

```python
regime = regime_detector.predict(X)

if regime == "up":
    long_prob = up_long_model.predict_proba(X)[:, 1]
    long_ev = long_prob * net_tp - (1.0 - long_prob) * abs(net_sl)

    if long_prob > long_threshold and long_ev > min_ev:
        signal = "LONG"
    else:
        signal = "NO_TRADE"

elif regime == "down":
    short_prob = down_short_model.predict_proba(X)[:, 1]
    short_ev = short_prob * net_tp - (1.0 - short_prob) * abs(net_sl)

    if short_prob > short_threshold and short_ev > min_ev:
        signal = "SHORT"
    else:
        signal = "NO_TRADE"

else:
    signal = "NO_TRADE"
```

---

## 6. 라벨링 방식

## 6.1 상승장 Long 라벨

```text
대상 데이터:
    regime == up

진입 가정:
    현재 시점에서 Long 진입

TP:
    +0.12% ~ +0.30%

SL:
    -0.08% ~ -0.15%

Horizon:
    5 / 10 / 15 / 30분 후보 실험

label = 1:
    TP가 SL보다 먼저 도달
    비용 차감 후 기대수익이 양수

label = 0:
    SL이 먼저 도달
    Timeout
    비용 차감 후 수익 부족
```

## 6.2 하락장 Short 라벨

```text
대상 데이터:
    regime == down

진입 가정:
    현재 시점에서 Short 진입

TP:
    -0.12% ~ -0.30%

SL:
    +0.08% ~ +0.15%

Horizon:
    5 / 10 / 15 / 30분 후보 실험

label = 1:
    TP가 SL보다 먼저 도달
    비용 차감 후 기대수익이 양수

label = 0:
    SL이 먼저 도달
    Timeout
    비용 차감 후 수익 부족
```

---

## 7. 비용 반영 EV 계산

단순히 성공 확률만 보고 진입하면 안 된다. 스캘핑에서는 수수료, 슬리피지, 스프레드, 안전마진을 반드시 반영해야 한다.

```text
비용 요소:
    fee_entry
    fee_exit
    slippage
    spread_cost
    safety_margin
```

Long 기준:

```text
net_long_tp = gross_long_tp - fee_entry - fee_exit - slippage - spread_cost
net_long_sl = gross_long_sl - fee_entry - fee_exit - slippage - spread_cost
```

Short 기준:

```text
net_short_tp = gross_short_tp - fee_entry - fee_exit - slippage - spread_cost
net_short_sl = gross_short_sl - fee_entry - fee_exit - slippage - spread_cost
```

EV 계산:

```text
EV = p_success * net_tp - (1 - p_success) * abs(net_sl)
```

진입 조건:

```text
EV > min_expected_value
```

---

## 8. 하면 안 되는 구조

다음 구조는 피해야 한다.

```text
up 데이터 전체 label = Long
down 데이터 전체 label = Short
range 데이터 전체 label = NoTrade
```

이렇게 하면 모델은 매매 타이밍을 학습하지 못한다.

또한 다음도 피해야 한다.

```text
상승장/하락장/횡보장을 사후 차트 기준으로 나눔
```

regime 판단은 반드시 해당 시점에서 알 수 있는 과거 데이터만으로 해야 한다.

```text
현재 시점에서 알 수 있는 정보:
    직전 완료 주봉 기준 MA20/MA50
    과거 N봉 수익률
    과거 N봉 변동성
    과거 N봉 EMA slope
    과거 N봉 ADX
```

---

## 9. 데이터 분할 권장안

현재 데이터셋 구성은 다음이 적절하다.

```text
Raw Data:
    2020-01-01 ~ 2025-12-31

Warm-up:
    2020-01-01 ~ 50주 MA 완성 전
    학습 제외
    피처 계산용으로만 사용

Train:
    2020년 50주 MA 완성 이후 ~ 2024-12-31

Validation / Tuning:
    2025-01-01 ~ 2025-06-30

Final Backtest:
    2025-07-01 ~ 2025-12-31
```

2025년 1~6월은 다음 용도로만 사용한다.

```text
- threshold 튜닝
- TP / SL / horizon 선택
- confidence threshold 선택
- class weight 조정 확인
- probability calibration 확인
```

2025년 7~12월은 최종 unseen backtest로 봉인한다.

```text
- threshold 변경 금지
- TP / SL 변경 금지
- horizon 변경 금지
- feature selection 변경 금지
- Optuna 재튜닝 금지
```

---

## 10. 체크리스트

구현 전 반드시 다음을 확인해야 한다.

```text
1. 상승장 데이터 전체가 Long 라벨로 고정되어 있지 않은가?
2. 하락장 데이터 전체가 Short 라벨로 고정되어 있지 않은가?
3. 횡보장은 모델 학습이 아니라 NoTrade rule로 처리 가능한가?
4. Long 라벨은 TP가 SL보다 먼저 도달한 경우만 1인가?
5. Short 라벨은 TP가 SL보다 먼저 도달한 경우만 1인가?
6. 비용, 슬리피지, 안전마진이 라벨과 EV에 반영되어 있는가?
7. regime 판단에 미래 정보가 들어가지 않는가?
8. 2025년 1~6월만 튜닝에 사용하는가?
9. 2025년 7~12월은 최종 백테스트로 봉인되어 있는가?
10. 각 regime별 positive sample 수가 충분한가?
```

---

## 11. 최종 결론

현재 전략 철학은 맞다.

```text
상승장에서는 Long만 노린다.
하락장에서는 Short만 노린다.
횡보장에서는 거래하지 않는다.
```

하지만 학습 라벨을 다음처럼 만들면 안 된다.

```text
상승장 = Long
하락장 = Short
횡보장 = NoTrade
```

올바른 구조는 다음이다.

```text
상승장:
    Long 성공 여부 학습

하락장:
    Short 성공 여부 학습

횡보장:
    학습하지 않고 NoTrade rule 처리
```

최종 추천 구조는 다음과 같다.

```text
up_long_model:
    1 = Long 성공
    0 = Long 실패 / 진입 금지

down_short_model:
    1 = Short 성공
    0 = Short 실패 / 진입 금지

range:
    NoTrade rule
```

이 구조가 현재 프로젝트의 의도와 가장 잘 맞는다.

한 문장으로 요약하면 다음과 같다.

```text
Regime은 방향을 제한하는 필터로 쓰고,
모델은 그 regime 안에서 실제 진입 타이밍의 성공 확률을 학습해야 한다.
```
