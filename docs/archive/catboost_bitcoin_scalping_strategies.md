# CatBoost 기반 비트코인 스캘핑 매매 전략 정리

## 1. 개요

현재 딥러닝을 사용하지 않고 **CatBoost**를 학습시키는 방향이라면, 전략 설계 방식이 달라져야 한다.

딥러닝은 호가창 원본 시퀀스, tick sequence, multi-timeframe sequence 같은 데이터를 그대로 입력받아 패턴을 학습하는 데 강점이 있다.  
반면 CatBoost는 원본 시계열을 그대로 넣기보다는, 일정 구간의 가격·거래량·변동성·추세·체결 정보를 **요약 피처(feature)** 로 만들어 학습시키는 방식이 더 적합하다.

따라서 CatBoost 기반 스캘핑 모델은 다음과 같은 문제로 설계하는 것이 좋다.

```text
1. 방향 분류
2. LONG 진입 성공 확률 예측
3. SHORT 진입 성공 확률 예측
4. 기대수익률 회귀
5. 진입 후보 랭킹
```

핵심은 다음이다.

```text
CatBoost에서는 다음 가격을 맞히는 모델보다,
지금 진입했을 때 TP가 SL보다 먼저 맞을 확률을 예측하는 모델이 더 현실적이다.
```

---

## 2. CatBoost에 적합한 스캘핑 전략 우선순위

| 우선순위 | 전략 | CatBoost 적합도 | 이유 |
|---:|---|---:|---|
| 1 | 변동성 압축 후 확장 돌파 | 매우 높음 | 피처화가 쉽고 라벨링이 명확함 |
| 2 | 마이크로 추세 눌림목 | 매우 높음 | 추세/되돌림 조건 조합에 적합함 |
| 3 | 가짜 돌파 / 유동성 스윕 탐지 | 높음 | 돌파 후 복귀 여부를 분류하기 좋음 |
| 4 | 체결강도 기반 스캘핑 | 높음 | tick 데이터가 있으면 강력함 |
| 5 | 호가창 불균형 스캘핑 | 높음 | order book 데이터가 있으면 강력함 |
| 6 | 평균회귀 스캘핑 | 중간 | 수익폭이 작아 비용 영향이 큼 |
| 7 | 청산 / OI 기반 필터 | 중간 | 단독 전략보다 보조 피처로 적합함 |

---

## 3. 변동성 압축 후 확장 돌파

CatBoost에 가장 잘 맞는 전략 중 하나다.

변동성이 낮아진 구간 이후 거래량, 캔들 range, 돌파 강도, 체결강도 등이 동시에 커질 때 진입 후보로 보는 방식이다.

### 3.1 전략 개념

```text
1. 일정 시간 동안 변동성 감소
2. 가격 범위 압축
3. 거래량 감소 또는 정체
4. 특정 방향으로 돌파 발생
5. 거래량과 변동성 동반 증가
6. 돌파 방향으로 진입
```

### 3.2 입력 피처 예시

```text
bb_width_20
bb_width_zscore
atr_14
atr_ratio_5_20
realized_vol_10
realized_vol_30
range_compression_ratio
volume_zscore_20
candle_body_ratio
upper_wick_ratio
lower_wick_ratio
breakout_distance_high_20
breakout_distance_low_20
```

### 3.3 라벨 설계 예시

```text
진입 시점 t 기준

TP: +0.15%
SL: -0.10%
Timeout: 5분

TP 먼저 도달 → LONG_SUCCESS
SL 먼저 도달 → FAIL
둘 다 미도달 → NO_TRADE 또는 제외
```

### 3.4 적합 모델

```text
CatBoostClassifier
loss_function = Logloss 또는 MultiClass
```

### 3.5 장점

```text
- 피처화가 쉽다.
- 라벨 기준이 명확하다.
- 변동성 기반 전략이라 스캘핑과 잘 맞는다.
- 2-stage 구조와 결합하기 좋다.
```

---

## 4. 마이크로 추세 눌림목 스캘핑

상위 프레임에서는 추세를 판단하고, 하위 프레임에서는 짧은 눌림 후 재상승 또는 재하락을 잡는 방식이다.

### 4.1 전략 예시

```text
5분봉 상승 추세
1분봉에서 VWAP 근처 눌림
RSI 단기 과매도
거래량 감소 후 다시 증가
최근 저점 이탈 없음
=> LONG 후보
```

반대의 경우는 SHORT 후보가 된다.

```text
5분봉 하락 추세
1분봉에서 VWAP 또는 EMA 근처 반등
RSI 단기 과매수
거래량 감소 후 다시 매도세 증가
최근 고점 돌파 실패
=> SHORT 후보
```

### 4.2 입력 피처 예시

```text
ema_5_slope
ema_20_slope
ema_60_slope
price_vs_vwap
price_vs_ema20
rsi_7
rsi_14
macd_hist
pullback_depth
pullback_duration
volume_decline_ratio
rebound_volume_ratio
higher_high_count
higher_low_count
lower_high_count
lower_low_count
```

### 4.3 라벨 설계 예시

```text
현재 시점에서 LONG 진입한다고 가정

5분 안에 +0.12% TP 도달 → 1
먼저 -0.08% SL 도달 → 0
둘 다 미도달 → 0 또는 제외
```

SHORT 모델은 반대로 설계한다.

```text
현재 시점에서 SHORT 진입한다고 가정

5분 안에 -0.12% TP 도달 → 1
먼저 +0.08% SL 도달 → 0
둘 다 미도달 → 0 또는 제외
```

### 4.4 적합 모델

```text
CatBoostClassifier
```

### 4.5 장점

```text
- CatBoost가 조건 조합형 패턴을 잘 잡을 수 있다.
- 추세장과 눌림목을 분리해서 학습시키기 좋다.
- LONG 모델과 SHORT 모델을 따로 만들기 좋다.
```

---

## 5. 가짜 돌파 / 유동성 스윕 탐지

직전 고점이나 저점을 살짝 깨고 다시 반대로 돌아가는 패턴을 탐지하는 전략이다.

### 5.1 분류 대상

```text
A. 진짜 돌파
B. 유동성만 먹고 반전
```

### 5.2 입력 피처 예시

```text
break_high_20
break_low_20
breakout_size_pct
volume_on_breakout
wick_after_breakout
close_back_inside_range
time_to_return_inside
range_position
atr_normalized_breakout
```

### 5.3 라벨 설계 예시

```text
고점 돌파 후 3분 안에 range 내부로 복귀 → FAKEOUT
고점 돌파 후 추가 상승 지속 → BREAKOUT
```

이진 분류로 표현하면 다음과 같다.

```text
0 = FAKEOUT
1 = BREAKOUT
```

### 5.4 적합 모델

```text
CatBoostClassifier
```

### 5.5 활용 방식

이 전략은 단독 진입 모델로도 쓸 수 있지만, 처음에는 필터로 쓰는 것이 더 안전하다.

```text
돌파 전략이 LONG 신호 발생
+
fakeout_model이 FAKEOUT 확률 높음
= 진입 금지
```

또는

```text
돌파 전략이 LONG 신호 발생
+
real_breakout 확률 높음
= LONG 진입 후보
```

---

## 6. 호가창 불균형 스캘핑

호가창 데이터가 있다면 매우 강력한 전략이다.  
다만 CatBoost에서는 호가창 10단계 raw matrix를 그대로 넣기보다는, 요약 피처를 만들어 넣는 것이 좋다.

### 6.1 입력 피처 예시

```text
bid_ask_spread
mid_price_return_1s
book_imbalance_1
book_imbalance_5
book_imbalance_10
bid_depth_5
ask_depth_5
bid_depth_10
ask_depth_10
depth_ratio_5
depth_ratio_10
bid_depth_change_1s
ask_depth_change_1s
spread_change
```

### 6.2 라벨 설계 예시

```text
5초 뒤 mid_price 상승폭 > 비용 + 안전마진 → LONG
5초 뒤 mid_price 하락폭 < -비용 - 안전마진 → SHORT
그 외 → NO_TRADE
```

3-class 분류로 만들 수 있다.

```text
0 = SHORT
1 = NO_TRADE
2 = LONG
```

### 6.3 주의점

```text
- 호가창 데이터가 없으면 우선순위를 낮춰야 한다.
- snapshot 간격이 너무 느리면 효과가 줄어든다.
- 스프레드와 체결비용을 반드시 라벨에 반영해야 한다.
```

---

## 7. 체결강도 기반 스캘핑

trade tick 데이터가 있다면 CatBoost에 잘 맞는 전략이다.  
시장가 매수와 시장가 매도 중 어느 쪽이 더 공격적인지를 피처화한다.

### 7.1 입력 피처 예시

```text
buy_volume_1s
sell_volume_1s
buy_volume_5s
sell_volume_5s
buy_sell_ratio_5s
trade_count_5s
avg_trade_size_5s
large_trade_count
cvd_5s
cvd_30s
cvd_slope
volume_delta_zscore
```

### 7.2 라벨 설계 예시

```text
10초 뒤 수익률 기준

상승폭 > 비용 + 안전마진 → LONG
하락폭 < -비용 - 안전마진 → SHORT
그 외 → NO_TRADE
```

### 7.3 추천 조합

```text
호가창 불균형
+
체결강도
+
spread 안정
```

이 세 조건이 동시에 맞을 때만 진입 후보로 보는 것이 좋다.

---

## 8. 평균회귀 스캘핑

가격이 VWAP, EMA, Bollinger 중심선, 단기 평균 가격에서 과하게 벌어진 뒤 되돌아오는 움직임을 노리는 방식이다.

### 8.1 입력 피처 예시

```text
price_vs_vwap
price_vs_ema20
price_vs_ema60
bollinger_percent_b
zscore_return_20
zscore_price_vwap
rsi_7
rsi_14
recent_drop_pct
recent_rise_pct
volume_exhaustion
```

### 8.2 라벨 설계 예시

```text
과매도 후 3분 안에 VWAP 방향으로 +0.10% 회귀 → 성공
반대로 -0.08% 추가 이탈 → 실패
```

SHORT 평균회귀는 반대로 설계한다.

```text
과매수 후 3분 안에 VWAP 방향으로 -0.10% 회귀 → 성공
반대로 +0.08% 추가 이탈 → 실패
```

### 8.3 주의점

평균회귀는 수익폭이 작다.  
따라서 반드시 다음 조건을 만족해야 한다.

```text
예상수익 > 수수료 + 스프레드 + 슬리피지
```

---

## 9. 청산 / 미체결약정 기반 필터

선물 시장에서는 강제청산, 미체결약정, 펀딩비 변화가 초단기 방향성에 영향을 줄 수 있다.

단독 전략으로 사용하기보다는 기존 호가창·체결강도·돌파 모델의 신뢰도 보정 피처로 쓰는 것이 좋다.

### 9.1 입력 피처 예시

```text
open_interest_change
funding_rate
long_short_ratio
liquidation_volume
basis
premium_index
```

### 9.2 활용 예시

```text
호가창 모델이 SHORT 신호
+
OI 감소와 롱 청산 증가
+
체결강도 매도 우위
= SHORT 신뢰도 증가
```

또는

```text
돌파 모델이 LONG 신호
+
OI 증가
+
청산이 아닌 신규 포지션 유입
= LONG 신뢰도 증가
```

---

## 10. CatBoost용 추천 모델 구조

## 10.1 구조 1: 단일 3-class 분류 모델

가장 단순한 방식이다.

```text
입력:
캔들 피처 + 거래량 피처 + 변동성 피처 + 추세 피처

출력:
SHORT / NO_TRADE / LONG
```

예시:

```text
CatBoostClassifier
loss_function = MultiClass
target = 0, 1, 2
```

### 장점

```text
- 구현이 단순하다.
- 한 모델에서 방향성을 바로 얻을 수 있다.
```

### 단점

```text
- LONG, SHORT, NO_TRADE 기준이 애매하면 성능이 약해진다.
- NO_TRADE 비중이 너무 커질 수 있다.
- 롱과 숏의 특성이 섞일 수 있다.
```

---

## 10.2 구조 2: Long/Short 분리 모델

가장 추천하는 기본 구조다.

```text
Model A: LONG 진입 성공 확률
Model B: SHORT 진입 성공 확률
```

각각 이진 분류로 학습한다.

```text
long_model:
1 = LONG 진입 시 TP 먼저 도달
0 = 실패

short_model:
1 = SHORT 진입 시 TP 먼저 도달
0 = 실패
```

실전 의사결정은 다음과 같다.

```text
long_prob = long_model.predict_proba(X)
short_prob = short_model.predict_proba(X)

if long_prob > threshold and long_ev > 0:
    LONG
elif short_prob > threshold and short_ev > 0:
    SHORT
else:
    NO_TRADE
```

### 장점

```text
- 롱과 숏을 독립적으로 학습할 수 있다.
- 롱이 잘 맞는 장세와 숏이 잘 맞는 장세를 분리할 수 있다.
- threshold 조정이 쉽다.
```

---

## 10.3 구조 3: 2-stage 구조

기존에 설계했던 2-stage 구조와 가장 잘 맞는다.

### Stage 1: 시장 국면 분류

```text
Model:
CatBoostClassifier

분류:
- ranging
- trending_up
- trending_down
- high_volatility
- squeeze
```

### Stage 2: 진입 성공 확률 예측

```text
Model:
CatBoostClassifier 또는 CatBoostRegressor

출력:
- LONG 성공 확률
- SHORT 성공 확률
- expected_return
```

### 장점

```text
- 시장 국면별로 다른 진입 기준을 적용할 수 있다.
- 횡보장과 추세장을 분리할 수 있다.
- high volatility 구간에서 진입 제한 또는 별도 전략 적용이 가능하다.
```

---

## 10.4 구조 4: CatBoostRanker

더 공격적인 방식이다.

매 시점마다 여러 후보를 만든다.

```text
후보 1: LONG breakout
후보 2: LONG pullback
후보 3: SHORT fakeout
후보 4: SHORT momentum
후보 5: NO_TRADE
```

각 후보의 실제 미래 수익률을 점수로 둔다.

```text
score = future_net_return
```

CatBoostRanker가 가장 좋은 후보를 위로 올리도록 학습한다.

### 데이터 구성 예시

```text
group_id = timestamp 또는 trading_session
features = 각 후보 전략의 피처
label = 해당 후보의 미래 실현 수익률
```

### 추천

처음부터 Ranker로 가기보다는 다음 순서를 추천한다.

```text
1. Long/Short 분리 CatBoostClassifier
2. expected_return CatBoostRegressor 추가
3. 후보 전략이 많아지면 CatBoostRanker 적용
```

---

## 11. 지금 바로 추천하는 CatBoost 학습 타겟

## 11.1 1순위 타겟: LONG 진입 성공 여부

```text
현재 시점에서 LONG 진입 가정

TP = +0.15%
SL = -0.10%
Timeout = 5분

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

## 11.2 2순위 타겟: SHORT 진입 성공 여부

```text
현재 시점에서 SHORT 진입 가정

TP = -0.15%
SL = +0.10%
Timeout = 5분

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

## 11.3 3순위 타겟: expected_net_return

```text
future_return - fee - slippage
```

이 타겟은 CatBoostRegressor로 학습한다.

---

## 12. 피처 그룹 설계

## 12.1 가격 / 수익률 피처

```text
return_1
return_3
return_5
return_10
log_return_1
high_low_range
close_open_return
body_size
upper_wick
lower_wick
```

## 12.2 변동성 피처

```text
atr_14
atr_30
realized_vol_10
realized_vol_30
bb_width_20
range_zscore
volatility_regime
```

## 12.3 추세 피처

```text
ema_5
ema_20
ema_60
ema_5_slope
ema_20_slope
ema_alignment
adx_14
trend_strength
```

## 12.4 거래량 피처

```text
volume
volume_zscore_20
volume_ma_ratio
quote_volume
trade_count
volume_spike
```

## 12.5 위치 피처

```text
price_vs_vwap
price_vs_ema20
price_vs_high_20
price_vs_low_20
range_position_20
breakout_high_20
breakout_low_20
```

## 12.6 시간 피처

```text
hour
minute
day_of_week
session_asia
session_europe
session_us
```

## 12.7 호가창 피처

```text
spread
mid_price
book_imbalance_1
book_imbalance_5
book_imbalance_10
bid_depth_5
ask_depth_5
depth_ratio_5
depth_ratio_10
spread_change
depth_change
```

## 12.8 체결강도 피처

```text
buy_volume_1s
sell_volume_1s
buy_volume_5s
sell_volume_5s
buy_sell_ratio
cvd
cvd_slope
trade_count
avg_trade_size
large_trade_count
```

---

## 13. 검증 방식

스캘핑 모델에서 가장 위험한 것은 랜덤 셔플 검증이다.

절대 다음과 같이 하면 안 된다.

```text
train_test_split(shuffle=True)
```

권장 검증 방식은 다음이다.

```text
Walk-forward validation
Purged time series split
월별 train/test split
최근 구간 완전 unseen backtest
```

### 예시

```text
Train: 2024-01 ~ 2024-06
Valid: 2024-07

Train: 2024-01 ~ 2024-07
Valid: 2024-08

Train: 2024-01 ~ 2024-08
Valid: 2024-09
```

---

## 14. 성능 평가 지표

정확도만 보면 안 된다.  
Accuracy가 높아도 실제로는 돈을 못 벌 수 있다.

봐야 할 지표는 다음이다.

```text
net profit
profit factor
expectancy
max drawdown
win rate
avg win / avg loss
trade count
fee-adjusted return
slippage-adjusted return
precision_at_trade
recall_at_trade
```

### 핵심 평가 기준

```text
1. 수수료 차감 후 수익이 나는가?
2. 슬리피지를 반영해도 수익이 나는가?
3. 거래 횟수가 너무 적지는 않은가?
4. 특정 기간에만 과적합된 것은 아닌가?
5. 최대 낙폭이 감당 가능한가?
```

---

## 15. CatBoost에서 주의할 점

## 15.1 NO_TRADE 비중 문제

스캘핑 라벨은 대부분 NO_TRADE가 된다.  
따라서 다음 중 하나가 필요하다.

```text
class_weights
sample_weights
NO_TRADE 다운샘플링
진입 후보 구간만 학습
```

## 15.2 거래비용 포함 라벨

라벨을 이렇게 만들면 안 된다.

```text
5분 뒤 가격이 오르면 LONG
```

이렇게 만들어야 한다.

```text
5분 안에 수수료 + 슬리피지 + 안전마진을 넘는 TP를 먼저 찍으면 LONG_SUCCESS
```

## 15.3 피처 누수 방지

다음은 데이터 누수다.

```text
현재 봉의 종가가 확정되기 전에 현재 봉 전체 high/low 사용
미래 거래량 포함
미래 ATR 포함
미래 캔들 기준으로 라벨과 피처가 섞임
```

반드시 피처는 현재 시점에서 알 수 있는 과거 데이터만 사용해야 한다.

## 15.4 랜덤 셔플 금지

시계열 데이터에서는 랜덤 셔플을 하면 미래 정보가 학습에 섞이는 것과 비슷한 효과가 생길 수 있다.  
반드시 시간 순서 기반 검증을 해야 한다.

---

## 16. 추천 구현 순서

## 16.1 1단계

```text
데이터:
BTCUSDT 1m OHLCV

전략:
변동성 압축 후 확장 돌파
마이크로 추세 눌림목
가짜 돌파 탐지

모델:
LONG 성공확률 CatBoostClassifier
SHORT 성공확률 CatBoostClassifier
```

## 16.2 2단계

```text
데이터 추가:
trade_count
quote_volume
taker_buy_volume
taker_sell_volume 추정값
volume delta

전략 추가:
체결강도 기반 스캘핑
```

## 16.3 3단계

```text
데이터 추가:
order book snapshot
spread
depth imbalance

전략 추가:
호가창 불균형 스캘핑
```

## 16.4 4단계

```text
데이터 추가:
open interest
funding rate
liquidation
basis
long/short ratio

활용:
시장 국면 보정
신뢰도 보정
진입 필터
```

## 16.5 5단계

```text
모델 추가:
CatBoostRegressor
CatBoostRanker

목표:
expected_net_return 예측
여러 진입 후보 중 최상위 후보 선택
```

---

## 17. 최종 추천 구조

가장 현실적인 구조는 다음이다.

```text
Stage 1:
CatBoostClassifier로 시장 국면 분류

Stage 2:
LONG 성공확률 모델
SHORT 성공확률 모델

Stage 3:
expected_net_return이 양수일 때만 진입

Optional:
CatBoostRanker로 여러 진입 후보 중 최상위 후보 선택
```

### 최종 진입 조건

```text
long_prob > long_threshold
+
long_expected_value > 수수료 + 슬리피지 + 안전마진
+
현재 시장 국면이 LONG 전략에 적합
= LONG 진입
```

```text
short_prob > short_threshold
+
short_expected_value > 수수료 + 슬리피지 + 안전마진
+
현재 시장 국면이 SHORT 전략에 적합
= SHORT 진입
```

그 외에는 진입하지 않는다.

```text
NO_TRADE
```

---

## 18. 결론

딥러닝을 사용하지 않고 CatBoost를 사용한다면, 가장 적합한 전략은 다음 3개다.

```text
1. 변동성 압축 후 확장 돌파
2. 마이크로 추세 눌림목
3. 가짜 돌파 / 유동성 스윕 탐지
```

데이터가 tick 또는 order book까지 있다면 다음을 추가한다.

```text
4. 체결강도 기반 스캘핑
5. 호가창 불균형 스캘핑
```

CatBoost에서는 다음 가격을 단순히 맞히는 모델보다, 다음 구조가 훨씬 현실적이다.

```text
지금 진입했을 때
TP가 SL보다 먼저 맞을 확률을 예측하고,
거래비용을 제외한 expected_net_return이 양수일 때만 진입한다.
```

최종적으로는 다음 구조를 추천한다.

```text
시장 국면 분류
+
LONG/SHORT 성공확률 분리 모델
+
expected_net_return 필터
+
필요 시 CatBoostRanker
```

이 구조가 딥러닝 없이 CatBoost만으로 시작할 수 있는 가장 안정적인 비트코인 스캘핑 모델 구조다.
