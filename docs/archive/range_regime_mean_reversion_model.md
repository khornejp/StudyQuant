# 횡보장 평균회귀 모델 설계 보고서

## 1. 개요

기존 설계에서는 레짐별 모델을 다음과 같이 구성했다.

```text
상승장(up):
    up_long_model

하락장(down):
    down_short_model

횡보장(range):
    NoTrade
```

하지만 횡보장에서도 가격은 계속 위아래로 움직인다.

```text
range low 근처 → 반등 가능성
range high 근처 → 하락 가능성
VWAP 아래 과도 이탈 → VWAP 회귀 가능성
VWAP 위 과도 이탈 → VWAP 회귀 가능성
Bollinger 하단 이탈 → 중심선 회귀 가능성
Bollinger 상단 이탈 → 중심선 회귀 가능성
```

따라서 횡보장을 무조건 NoTrade로만 처리하면 거래 기회가 너무 줄어들 수 있다.

최종적으로는 횡보장 전용 평균회귀 모델을 추가하는 것이 좋다.

---

## 2. 최종 추천 레짐별 모델 구조

추천 구조는 다음과 같다.

```text
RegimeDetector
    ├─ up
    │    └─ up_long_model
    │
    ├─ down
    │    └─ down_short_model
    │
    └─ range
         ├─ range_long_model
         └─ range_short_model
```

즉 최종 모델은 총 4개다.

```text
1. up_long_model
2. down_short_model
3. range_long_model
4. range_short_model
```

각 모델의 역할은 다음과 같다.

```text
up_long_model:
    상승장 안에서 Long 성공 타이밍 학습

down_short_model:
    하락장 안에서 Short 성공 타이밍 학습

range_long_model:
    횡보장 하단 / 과매도 / 평균 하방 이탈 구간에서 Long 성공 타이밍 학습

range_short_model:
    횡보장 상단 / 과매수 / 평균 상방 이탈 구간에서 Short 성공 타이밍 학습
```

---

## 3. 횡보장은 추세추종이 아니라 평균회귀

횡보장에서는 가격이 특정 방향으로 길게 추세를 만들기보다, 일정 범위 안에서 위아래로 흔들리는 경우가 많다.

따라서 횡보장 모델은 돌파 추종이 아니라 평균회귀 성격이어야 한다.

```text
상승장:
    눌림 후 재상승 Long

하락장:
    반등 후 재하락 Short

횡보장:
    과도 이탈 후 평균 복귀
```

횡보장에서 돌파를 무작정 따라가면 fake breakout에 걸릴 가능성이 높다.

따라서 횡보장 모델은 다음을 목표로 한다.

```text
range_long_model:
    박스 하단, VWAP 하방 이탈, Bollinger 하단, z-score 과매도 구간에서 Long 성공 확률 예측

range_short_model:
    박스 상단, VWAP 상방 이탈, Bollinger 상단, z-score 과매수 구간에서 Short 성공 확률 예측
```

---

## 4. 평균회귀 모델 종류

## 4.1 Range High / Range Low 회귀 모델

가장 직접적인 횡보장 평균회귀 모델이다.

최근 N봉 기준 박스권 상단과 하단을 계산한다.

```text
range_high = 최근 N봉 고점
range_low = 최근 N봉 저점
range_mid = (range_high + range_low) / 2
```

핵심 피처는 `range_position`이다.

```text
range_position = (close - range_low) / (range_high - range_low)
```

해석은 다음과 같다.

```text
range_position < 0.2:
    박스 하단
    Long 후보

range_position > 0.8:
    박스 상단
    Short 후보

0.2 <= range_position <= 0.8:
    박스 중간
    NoTrade 우선
```

모델 구조:

```text
range_long_model:
    가격이 range_low 근처일 때 Long 성공 여부 학습

range_short_model:
    가격이 range_high 근처일 때 Short 성공 여부 학습
```

---

## 4.2 VWAP 회귀 모델

가격이 rolling VWAP에서 과도하게 벗어났다가 다시 VWAP 방향으로 돌아오는지를 학습한다.

```text
range_long_model:
    가격이 VWAP 아래로 과도하게 이탈
    → VWAP 방향 반등 가능성 예측

range_short_model:
    가격이 VWAP 위로 과도하게 이탈
    → VWAP 방향 하락 가능성 예측
```

추천 피처:

```text
rolling_vwap_20
rolling_vwap_60
rolling_vwap_240
price_vs_vwap_20
price_vs_vwap_60
price_vs_vwap_240
vwap_deviation_zscore
distance_to_vwap_atr
```

암호화폐는 24시간 시장이므로 장 시작 기준 VWAP보다 rolling VWAP이 더 적합하다.

---

## 4.3 Bollinger Band 평균회귀 모델

횡보장에서 가장 전형적인 평균회귀 방식이다.

```text
가격이 Bollinger 하단 근처:
    Long 반등 후보

가격이 Bollinger 상단 근처:
    Short 하락 후보
```

추천 피처:

```text
bb_mid_20
bb_upper_20
bb_lower_20
bb_width_20
bb_percent_b
bb_zscore
price_vs_bb_mid
price_vs_bb_upper
price_vs_bb_lower
```

진입 후보 예시:

```text
range_long_candidate:
    bb_percent_b < 0.1
    또는 close < bb_lower

range_short_candidate:
    bb_percent_b > 0.9
    또는 close > bb_upper
```

Bollinger Band는 단독 진입 신호가 아니라 CatBoost 입력 피처로 사용하는 것이 좋다.

---

## 4.4 Z-score 평균회귀 모델

현재 가격이 최근 평균에서 몇 표준편차 떨어져 있는지를 이용한다.

```text
zscore = (price - rolling_mean) / rolling_std
```

활용 방식:

```text
zscore < -2:
    과도한 하락
    Long 회귀 후보

zscore > +2:
    과도한 상승
    Short 회귀 후보
```

추천 피처:

```text
price_zscore_20
price_zscore_60
return_zscore_20
return_zscore_60
volume_zscore_20
rv_zscore_20
```

CatBoost에서는 z-score 자체만으로 진입하지 않고, 거래량, 변동성, 캔들 구조와 함께 판단하도록 하는 것이 좋다.

---

## 4.5 RSI 과매수 / 과매도 회귀 모델

RSI는 단독으로 쓰면 약하지만, 횡보장에서는 보조 피처로 쓸 수 있다.

```text
RSI 낮음:
    과매도
    Long 후보

RSI 높음:
    과매수
    Short 후보
```

추천 피처:

```text
rsi_7
rsi_14
rsi_21
rsi_slope
rsi_divergence
```

추천 사용 방식:

```text
RSI 단독 진입 금지

RSI
+ VWAP 이탈
+ Bollinger 하단/상단
+ range 위치
+ 캔들 꼬리
+ 거래량 감소/반전
```

---

## 4.6 EMA / MA 이격 회귀 모델

가격이 EMA 또는 이동평균에서 과하게 멀어졌을 때 다시 돌아오는지를 본다.

추천 피처:

```text
price_vs_ema20
price_vs_ema60
price_vs_sma20
price_vs_sma60
ema_gap_zscore
ma_deviation_atr
```

주의할 점은 추세장에서는 EMA 이격이 계속 벌어질 수 있다는 것이다.  
따라서 이 모델은 반드시 `regime == range`일 때만 사용하는 것이 좋다.

---

## 4.7 캔들 꼬리 / Fakeout 회귀 모델

횡보장에서는 박스 상단/하단을 살짝 이탈한 뒤 다시 박스 안으로 들어오는 패턴이 자주 발생한다.

Long 후보:

```text
아래꼬리 길다
저점 갱신 후 종가는 위로 복귀
range_low 아래로 살짝 이탈 후 회복
close_back_inside_range 발생
```

Short 후보:

```text
위꼬리 길다
고점 갱신 후 종가는 아래로 복귀
range_high 위로 살짝 이탈 후 회복
close_back_inside_range 발생
```

추천 피처:

```text
upper_wick_ratio
lower_wick_ratio
close_location
body_ratio
wick_to_body_ratio
fake_break_low
fake_break_high
close_back_inside_range
```

이 방식은 liquidity sweep 또는 fakeout 탐지와 연결된다.

---

## 5. CatBoost 기준 추천 구현

평균회귀 모델들을 각각 별도의 모델로 나누기보다는, 주요 평균회귀 개념을 피처로 만들어 CatBoost 이진 분류 모델에 넣는 구조가 좋다.

최종적으로는 다음 2개 모델을 만든다.

```text
range_long_model
range_short_model
```

## 5.1 range_long_model

목적:

```text
횡보장 안에서 Long 평균회귀 성공 확률 예측
```

학습 대상:

```text
regime == range
```

후보 조건:

```text
price near range_low
또는
bb_percent_b 낮음
또는
price_vs_vwap 음수로 과도
또는
zscore < -1.5
또는
lower_wick_ratio 큼
```

라벨:

```text
현재 시점 Long 진입 가정

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0
비용 차감 후 수익 부족 → 0
```

---

## 5.2 range_short_model

목적:

```text
횡보장 안에서 Short 평균회귀 성공 확률 예측
```

학습 대상:

```text
regime == range
```

후보 조건:

```text
price near range_high
또는
bb_percent_b 높음
또는
price_vs_vwap 양수로 과도
또는
zscore > +1.5
또는
upper_wick_ratio 큼
```

라벨:

```text
현재 시점 Short 진입 가정

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0
비용 차감 후 수익 부족 → 0
```

---

## 6. 추천 피처 세트

## 6.1 Range 위치 피처

```text
range_high_20
range_low_20
range_mid_20
range_width_20
range_position_20
distance_to_range_high
distance_to_range_low
distance_to_range_mid
```

## 6.2 VWAP 이격 피처

```text
rolling_vwap_20
rolling_vwap_60
rolling_vwap_240
price_vs_vwap_20
price_vs_vwap_60
price_vs_vwap_240
vwap_deviation_zscore
```

## 6.3 Bollinger 피처

```text
bb_width_20
bb_percent_b
bb_mid_20
bb_upper_20
bb_lower_20
price_vs_bb_mid
price_vs_bb_upper
price_vs_bb_lower
```

## 6.4 Z-score 피처

```text
price_zscore_20
price_zscore_60
return_zscore_20
return_zscore_60
volume_zscore_20
rv_zscore_20
```

## 6.5 RSI 피처

```text
rsi_7
rsi_14
rsi_21
rsi_slope
rsi_divergence
```

## 6.6 캔들 구조 피처

```text
upper_wick_ratio
lower_wick_ratio
close_location
body_ratio
wick_to_body_ratio
fake_break_low
fake_break_high
close_back_inside_range
```

## 6.7 거래량 피처

```text
volume_zscore_20
volume_decline_ratio
rebound_volume_ratio
trade_count_ratio
volume_per_trade
```

---

## 7. 횡보장 진입 로직

횡보장에서는 박스권 중간에서 진입하면 애매해질 가능성이 높다.

따라서 range_long_model과 range_short_model은 활성화 조건을 다르게 두는 것이 좋다.

```python
if regime == "range":
    if range_position < 0.25:
        check_range_long_model()

    elif range_position > 0.75:
        check_range_short_model()

    else:
        signal = "NO_TRADE"
```

전체 의사결정은 다음과 같다.

```python
if regime == "range":
    long_prob = range_long_model.predict_proba(X)[:, 1]
    short_prob = range_short_model.predict_proba(X)[:, 1]

    long_ev = long_prob * net_long_tp - (1.0 - long_prob) * abs(net_long_sl)
    short_ev = short_prob * net_short_tp - (1.0 - short_prob) * abs(net_short_sl)

    if range_position < 0.25 and long_ev > min_ev:
        signal = "LONG"

    elif range_position > 0.75 and short_ev > min_ev:
        signal = "SHORT"

    else:
        signal = "NO_TRADE"
```

---

## 8. 비용 반영 EV 계산

횡보장 평균회귀는 수익폭이 작을 수 있으므로 비용 반영이 매우 중요하다.

비용 요소:

```text
fee_entry
fee_exit
slippage
spread_cost
safety_margin
```

EV 계산:

```text
EV = p_success * net_tp - (1 - p_success) * abs(net_sl)
```

진입 조건:

```text
EV > min_expected_value
```

수수료와 슬리피지를 반영하지 않으면 백테스트에서는 좋아 보이지만 실전에서는 수익이 사라질 수 있다.

---

## 9. 라벨링 예시

## 9.1 range_long_model 라벨

```text
대상:
    regime == range

진입 가정:
    현재 시점에서 Long 진입

TP:
    +0.10% ~ +0.20%

SL:
    -0.08% ~ -0.15%

Horizon:
    5 / 10 / 15분 후보

label = 1:
    TP가 SL보다 먼저 도달
    비용 차감 후 수익이 양수

label = 0:
    SL 먼저 도달
    Timeout
    비용 차감 후 수익 부족
```

## 9.2 range_short_model 라벨

```text
대상:
    regime == range

진입 가정:
    현재 시점에서 Short 진입

TP:
    -0.10% ~ -0.20%

SL:
    +0.08% ~ +0.15%

Horizon:
    5 / 10 / 15분 후보

label = 1:
    TP가 SL보다 먼저 도달
    비용 차감 후 수익이 양수

label = 0:
    SL 먼저 도달
    Timeout
    비용 차감 후 수익 부족
```

---

## 10. 주의사항

## 10.1 횡보장 판정이 중요함

횡보장이 아닌 추세장에 평균회귀 모델을 적용하면 위험하다.

예를 들어 상승 추세가 강한 구간에서 Bollinger 상단을 찍었다고 Short를 치면 계속 손절이 날 수 있다.  
하락 추세에서도 Bollinger 하단 Long은 위험하다.

따라서 평균회귀 모델은 반드시 `regime == range` 조건 아래에서만 사용한다.

---

## 10.2 박스권 중간 진입 금지

횡보장에서도 박스권 중간은 방향성이 애매하다.

```text
range_position 0.4 ~ 0.6:
    NoTrade 우선
```

추천 활성화 기준:

```text
range_position < 0.25:
    range_long_model 활성화

range_position > 0.75:
    range_short_model 활성화

그 외:
    NoTrade
```

---

## 10.3 Fake breakout에 주의

횡보장에서는 돌파처럼 보였다가 다시 박스 안으로 들어오는 경우가 많다.

따라서 단순 breakout 피처보다 다음 피처를 중요하게 봐야 한다.

```text
fake_break_low
fake_break_high
close_back_inside_range
upper_wick_ratio
lower_wick_ratio
```

---

## 10.4 샘플 수 확인

횡보장 데이터를 다시 range_long, range_short 후보로 나누면 샘플 수가 줄어든다.

반드시 확인해야 한다.

```text
range regime 전체 샘플 수
range_long_candidate 수
range_short_candidate 수
range_long label=1 비율
range_short label=1 비율
실제 백테스트 trade count
```

샘플이 너무 적으면 모델이 과적합될 수 있다.

---

## 11. 추천 적용 순서

1차 적용:

```text
range_position 기반 range_long/range_short 후보 생성
range_long_model / range_short_model 이진 분류 학습
```

2차 적용:

```text
rolling VWAP 피처 추가
Bollinger Band 피처 추가
Z-score 피처 추가
RSI 피처 추가
캔들 꼬리 / fakeout 피처 추가
```

3차 적용:

```text
range_long_model, range_short_model 각각 threshold 튜닝
EV 기반 진입 게이트 적용
2025년 1~6월 validation에서 성능 검증
```

4차 적용:

```text
2025년 7~12월 final backtest
```

---

## 12. 최종 결론

횡보장을 전부 NoTrade로 처리하면 거래 기회가 너무 줄어들 수 있다.

따라서 최종적으로는 횡보장 전용 평균회귀 모델을 추가하는 것이 좋다.

추천 최종 구조:

```text
up:
    up_long_model

down:
    down_short_model

range:
    range_long_model
    range_short_model
```

횡보장 모델은 추세추종이 아니라 평균회귀 모델이어야 한다.

```text
range_long_model:
    박스 하단 / VWAP 하방 이탈 / Bollinger 하단 / z-score 과매도 구간에서 Long 성공 확률 학습

range_short_model:
    박스 상단 / VWAP 상방 이탈 / Bollinger 상단 / z-score 과매수 구간에서 Short 성공 확률 학습
```

한 문장으로 정리하면 다음과 같다.

```text
횡보장 평균회귀 모델은
박스 하단에서 Long 성공 확률,
박스 상단에서 Short 성공 확률을 학습하는 CatBoost 이진 분류 모델이다.
```
