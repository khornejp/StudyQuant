# Binance Futures Long/Short Metrics 정리

## 1. 개요

바이낸스 선물 차트 하단에서 확인할 수 있는 **Long/Short 비율 계열 데이터**는 일반적인 1분봉 OHLCV 데이터에 포함되어 있지 않다.

BTCUSDT USD-M Futures 기준으로 Binance Vision의 별도 `metrics` 데이터에 포함되어 있다.

대표적인 아카이브 경로는 다음과 같다.

```text
data/futures/um/daily/metrics/BTCUSDT/
```

파일 예시:

```text
BTCUSDT-metrics-2026-07-08.zip
```

이 데이터는 일반적으로 **5분 단위**로 제공된다.

---

## 2. 주요 컬럼

`metrics` 데이터에는 대표적으로 다음 컬럼들이 포함된다.

```text
create_time
symbol
sum_open_interest
sum_open_interest_value
count_toptrader_long_short_ratio
sum_toptrader_long_short_ratio
count_long_short_ratio
sum_taker_long_short_vol_ratio
```

각 컬럼의 의미는 다음과 같다.

| 컬럼 | 의미 | 해석 |
|---|---|---|
| `count_long_short_ratio` | 전체 계정 Long/Short 비율 | 일반 사용자 포함 |
| `count_toptrader_long_short_ratio` | 상위 트레이더 계정 수 기준 Long/Short 비율 | 상위 트레이더 계정 방향 |
| `sum_toptrader_long_short_ratio` | 상위 트레이더 포지션 규모 기준 Long/Short 비율 | 실제 포지션 규모 기준 |
| `sum_taker_long_short_vol_ratio` | 시장가 Buy/Sell 체결량 비율 | 공격적 매수/매도 압력 |
| `sum_open_interest` | 미결제약정 | BTC 단위 Open Interest |
| `sum_open_interest_value` | 미결제약정 가치 | USDT 기준 Open Interest |

---

## 3. 차트에서 보이는 Long 우세 / Short 우세와 가장 가까운 값

차트에서 보이는 "Long이 우세한지, Short이 우세한지"에 가장 직접적으로 대응하는 값은 보통 다음이다.

```text
count_long_short_ratio
```

예를 들어:

```text
count_long_short_ratio = 1.25
```

이면

```text
Long 계정 수 / Short 계정 수 = 1.25
```

이므로 Long 계정이 더 많다는 뜻이다.

반대로:

```text
count_long_short_ratio = 0.80
```

이면 Short 계정이 더 많다는 의미다.

---

## 4. 주의점: 계정 수와 포지션 규모는 다르다

`count_long_short_ratio`는 **계정 수 비율**이다.

따라서 다음처럼 해석하면 안 된다.

> count_long_short_ratio = 2.0  
> → Long 자금이 Short 자금보다 2배 많다.

실제로는 예를 들어:

```text
Long 계정: 100명
Short 계정: 50명

count_long_short_ratio = 2.0
```

이어도,

```text
Long 100명 × 0.01 BTC = 1 BTC
Short 50명 × 1 BTC = 50 BTC
```

라면 실제 포지션 규모는 오히려 Short이 압도적일 수 있다.

그래서 전체 계정 비율뿐 아니라 **Top Trader Position Ratio**를 같이 보는 것이 중요하다.

---

## 5. 퀀트 시스템에서 같이 사용할 핵심 지표

단순히 `count_long_short_ratio` 하나만 넣기보다 다음 4개를 함께 사용하는 것이 좋다.

```text
count_long_short_ratio
count_toptrader_long_short_ratio
sum_toptrader_long_short_ratio
sum_taker_long_short_vol_ratio
```

여기에 Open Interest도 같이 활용한다.

```text
sum_open_interest
sum_open_interest_value
```

---

## 6. 각 지표의 역할

### 6.1 전체 계정 Long/Short Ratio

```text
count_long_short_ratio
```

일반 시장 참여자들이 Long과 Short 중 어느 방향에 더 많이 몰려 있는지 나타낸다.

예:

```text
1.8
```

이면 Long 계정이 Short 계정보다 많다는 의미다.

---

### 6.2 Top Trader 계정 기준 Ratio

```text
count_toptrader_long_short_ratio
```

상위 트레이더들의 계정 방향을 보여준다.

일반 투자자와 상위 트레이더의 방향이 다를 때 유용하다.

---

### 6.3 Top Trader 포지션 규모 Ratio

```text
sum_toptrader_long_short_ratio
```

단순 계정 수가 아니라 **포지션 크기 기준**으로 Long과 Short의 비율을 나타낸다.

일반적으로 `count_toptrader_long_short_ratio`보다 자금 흐름 관점에서 더 의미가 있을 수 있다.

---

### 6.4 Taker Buy/Sell Ratio

```text
sum_taker_long_short_vol_ratio
```

시장가 주문 기준으로 실제 매수와 매도 중 어느 쪽의 공격성이 높은지 나타낸다.

- 1보다 큼 → 공격적 매수 우세
- 1보다 작음 → 공격적 매도 우세

즉, 단순 포지션 보유 방향이 아니라 **현재 실제 체결 압력**에 가깝다.

---

### 6.5 Open Interest

```text
sum_open_interest
sum_open_interest_value
```

현재 시장에 열려 있는 선물 포지션 규모를 나타낸다.

가격과 Open Interest를 함께 보면 다음과 같은 상황을 구분할 수 있다.

```text
가격 상승 + OI 상승
→ 신규 Long/Short 포지션 유입 가능성

가격 상승 + OI 감소
→ Short Covering 가능성

가격 하락 + OI 상승
→ 신규 Short 유입 가능성

가격 하락 + OI 감소
→ Long 청산 가능성
```

---

## 7. 예시: 일반 투자자와 큰손의 방향이 반대인 경우

예를 들어 다음과 같은 상태가 있다고 가정한다.

```text
count_long_short_ratio = 1.80
sum_toptrader_long_short_ratio = 0.75
sum_taker_long_short_vol_ratio = 0.70
```

의미는 다음과 같다.

```text
전체 계정:
Long 우세

Top Trader 포지션:
Short 우세

시장가 체결:
Sell 우세
```

즉:

```text
일반 투자자 → Long
큰 포지션 → Short
실제 공격적 체결 → Sell
```

이와 같은 구조는 단순 가격 지표만으로는 얻기 어려운 **포지셔닝 정보**다.

따라서 Contrarian Feature 또는 시장 심리 Feature로 활용할 수 있다.

---

# 8. 추천 Raw Feature

BTCUSDT 퀀트 모델에 다음과 같은 Raw Feature를 추가할 수 있다.

```text
ls_all
ls_top_account
ls_top_position
taker_buy_sell_ratio
open_interest
open_interest_value
```

실제 매핑 예시는 다음과 같다.

```text
ls_all
= count_long_short_ratio

ls_top_account
= count_toptrader_long_short_ratio

ls_top_position
= sum_toptrader_long_short_ratio

taker_buy_sell_ratio
= sum_taker_long_short_vol_ratio

open_interest
= sum_open_interest

open_interest_value
= sum_open_interest_value
```

---

# 9. 변화율 Feature

절대적인 Ratio 값보다 **변화 방향**도 중요하다.

예를 들어 다음과 같이 구성할 수 있다.

```text
ls_all_change_5m
ls_all_change_15m
ls_all_change_30m

ls_top_position_change_5m
ls_top_position_change_15m
ls_top_position_change_30m

taker_ratio_change_5m
taker_ratio_change_15m
taker_ratio_change_30m

open_interest_change_5m
open_interest_change_15m
open_interest_change_30m
```

예:

```python
df["ls_all_change_5m"] = df["ls_all"].pct_change(1)
df["ls_all_change_15m"] = df["ls_all"].pct_change(3)
df["ls_all_change_30m"] = df["ls_all"].pct_change(6)
```

metrics가 5분 단위라고 가정하면:

```text
1 step = 5분
3 step = 15분
6 step = 30분
```

이 된다.

---

# 10. Retail vs Top Trader Gap

특히 유용하게 사용할 수 있는 파생 Feature는 일반 계정과 Top Trader의 차이다.

예:

```text
retail_vs_top_gap
```

계산 방법 예시:

```python
import numpy as np

df["retail_vs_top_gap"] = (
    np.log(df["count_long_short_ratio"])
    - np.log(df["sum_toptrader_long_short_ratio"])
)
```

또는 단순 비율로:

```python
df["retail_vs_top_ratio"] = (
    df["count_long_short_ratio"]
    / df["sum_toptrader_long_short_ratio"]
)
```

---

## 11. retail_vs_top_gap 해석

값이 크게 양수이면:

```text
전체 투자자 → Long 쏠림
Top Trader → 상대적으로 Short
```

값이 크게 음수이면:

```text
전체 투자자 → 상대적으로 Short
Top Trader → Long
```

즉 일반 시장 참여자와 큰 포지션 보유자의 방향 괴리를 Feature로 만들 수 있다.

---

# 12. Taker + Long/Short Ratio 조합

Long/Short Ratio와 Taker Ratio를 같이 보면 더 다양한 상황을 구분할 수 있다.

예:

### Case 1

```text
Long/Short Ratio 상승
Taker Buy/Sell Ratio 상승
```

→ Long 포지셔닝 증가 + 실제 매수 체결 증가

---

### Case 2

```text
Long/Short Ratio 상승
Taker Buy/Sell Ratio 하락
```

→ Long 계정은 증가하지만 실제 체결은 Sell 우세

Potential Long Trap 가능성

---

### Case 3

```text
Long/Short Ratio 하락
Taker Buy/Sell Ratio 상승
```

→ Short 계정은 많아지지만 실제 체결은 Buy 우세

Potential Short Squeeze 가능성

---

# 13. Open Interest와 결합

다음과 같이 조합 Feature를 만들 수도 있다.

```text
price_return
open_interest_change
long_short_ratio_change
taker_ratio
```

예를 들어:

```text
Price ↑
OI ↑
Taker Buy ↑
Top Trader Long ↑
```

라면 비교적 강한 Long Momentum 상태일 수 있다.

반대로:

```text
Price ↑
OI ↓
Taker Buy ↑
```

라면 신규 Long 진입보다는 Short Covering일 가능성도 있다.

---

# 14. 현재 1분봉 데이터와 병합하는 방법

현재 BTCUSDT 학습 데이터가 **1분봉**이고 `metrics`가 **5분 단위**라면 그대로 inner join하면 안 된다.

가장 안전한 방법은 `merge_asof`를 사용하는 것이다.

예:

```python
merged = pd.merge_asof(
    candles.sort_values("timestamp"),
    metrics.sort_values("timestamp"),
    on="timestamp",
    direction="backward",
)
```

핵심은:

```text
direction = "backward"
```

이다.

즉 해당 1분 시점에서 **이미 공개되어 있는 가장 최근 metrics 값만 사용한다.**

---

# 15. 시간 정렬 예시

예를 들어 metrics 데이터가 다음과 같이 있다.

```text
10:00
10:05
10:10
```

1분봉 데이터에는 다음처럼 매칭한다.

```text
10:00 → 10:00 metrics
10:01 → 10:00 metrics
10:02 → 10:00 metrics
10:03 → 10:00 metrics
10:04 → 10:00 metrics

10:05 → 10:05 metrics
10:06 → 10:05 metrics
10:07 → 10:05 metrics
...
```

이 방식이면 1분봉 모델에서도 metrics를 사용할 수 있다.

---

# 16. Future Leakage 주의

다음 방식은 위험하다.

```text
10:01 candle
→ 10:05 metrics 사용
```

10:05에 생성된 값을 10:01 모델 입력에 넣으면 모델이 미래 정보를 보게 된다.

즉:

```text
Future Leakage
```

가 발생한다.

백테스트 성능은 매우 좋아질 수 있지만 실제 매매에서는 재현되지 않는다.

따라서 반드시:

```text
현재 시점 이하의 가장 최근 metrics만 사용
```

해야 한다.

---

# 17. Metrics Timestamp 자체의 의미 확인 필요

추가로 실제 파이프라인에 넣기 전에는 `create_time`이 정확히 어떤 시간 기준으로 생성된 값인지 확인하는 것이 좋다.

예를 들어:

```text
10:05 timestamp
```

가

```text
10:00 ~ 10:05 구간 결과
```

인지,

혹은

```text
10:05 ~ 10:10 구간 시작값
```

인지에 따라 데이터 정렬 방식이 달라질 수 있다.

보수적으로는 실제 API/Archive Timestamp 정의를 확인하고 필요하면 한 구간 지연시켜 사용하는 방법도 고려할 수 있다.

---

# 18. 데이터 품질 검사

Binance archive 데이터를 받을 때는 다음을 검사하는 것이 좋다.

```text
timestamp duplicate
timestamp missing
5분 grid 누락
NaN
비정상적인 0 값
급격한 spike
```

예:

```python
metrics = metrics.drop_duplicates(subset=["timestamp"])

metrics = metrics.sort_values("timestamp")
```

5분 간격 검사:

```python
diff = metrics["timestamp"].diff()

print(diff.value_counts())
```

---

# 19. Missing 값 처리

metrics 값이 특정 시점에 누락되었을 경우 무조건 무제한 forward fill을 하는 것은 좋지 않다.

예를 들어:

```python
metrics = metrics.set_index("timestamp")

metrics = metrics.asfreq("5min")
```

후 제한된 구간만 채우는 방법을 사용할 수 있다.

예:

```python
metrics = metrics.ffill(limit=2)
```

그러면 최대 10분 정도까지만 이전 값을 유지하고 그 이상은 missing으로 남길 수 있다.

---

# 20. Feature 예시

최종적으로 다음과 같은 Feature Set을 구성할 수 있다.

```text
# Raw
ls_all
ls_top_account
ls_top_position
taker_buy_sell_ratio
open_interest
open_interest_value

# Long/Short Change
ls_all_change_5m
ls_all_change_15m
ls_all_change_30m

ls_top_position_change_5m
ls_top_position_change_15m
ls_top_position_change_30m

# Taker
taker_ratio_change_5m
taker_ratio_change_15m
taker_ratio_change_30m

# Open Interest
open_interest_change_5m
open_interest_change_15m
open_interest_change_30m

# Divergence
retail_vs_top_gap
retail_vs_top_ratio
```

---

# 21. 추가로 만들 수 있는 Feature

### Log Ratio

Ratio는 1을 중심으로 비대칭이므로 log transform이 유용할 수 있다.

```python
df["ls_all_log"] = np.log(df["count_long_short_ratio"])
df["ls_top_log"] = np.log(df["sum_toptrader_long_short_ratio"])
df["taker_log"] = np.log(df["sum_taker_long_short_vol_ratio"])
```

그러면:

```text
1.0 → 0
2.0 → +0.693
0.5 → -0.693
```

처럼 Long/Short 방향이 대칭적으로 표현된다.

---

### Retail / Top Divergence

```python
df["retail_top_divergence"] = (
    df["ls_all_log"]
    - df["ls_top_log"]
)
```

---

### OI × Direction

```python
df["oi_long_pressure"] = (
    df["open_interest_change_15m"]
    * df["ls_top_log"]
)
```

---

### Taker × OI

```python
df["taker_oi_pressure"] = (
    df["taker_log"]
    * df["open_interest_change_15m"]
)
```

이를 통해 실제 체결 압력과 신규 포지션 증가를 동시에 표현할 수 있다.

---

# 22. 현재 BTCUSDT 모델에서의 의미

현재 가격 기반 Feature들은 대부분 다음 정보를 표현한다.

```text
가격
수익률
이동평균
Trend
Volatility
ATR
Multi-Timeframe Slope
```

하지만 Binance Futures Metrics는 완전히 다른 종류의 정보를 제공한다.

```text
시장 참여자의 실제 포지셔닝
상위 트레이더 방향
시장가 매수/매도 압력
미결제약정
```

따라서 기존 가격 Feature와 중복되는 정보가 아니라 새로운 정보 축을 추가하게 된다.

구조적으로는:

```text
Price Features
+
Trend Features
+
Volatility Features
+
Positioning Features
+
Order-flow Features
```

형태가 된다.

---

# 23. Regime Detector에도 활용 가능

이 데이터는 Entry Model뿐 아니라 Regime Detector에도 활용 가능하다.

예를 들어:

```text
OI 빠르게 증가
+
Top Trader Long 증가
+
Taker Buy 증가
+
가격 상승
```

이면 Trend Regime 신뢰도를 높일 수 있다.

반대로:

```text
Long/Short Ratio 급변
+
가격 횡보
+
OI 감소
```

같은 패턴은 Position Unwinding 또는 Range 상태일 가능성을 나타낼 수 있다.

따라서 현재의 Trend Slope 기반 Regime Detector에 보조 Feature로 넣는 것도 테스트할 가치가 있다.

---

# 24. 추천 적용 순서

처음부터 Feature를 너무 많이 추가하기보다는 단계적으로 테스트하는 것이 좋다.

## Phase 1

먼저 다음 5개만 추가한다.

```text
count_long_short_ratio
sum_toptrader_long_short_ratio
sum_taker_long_short_vol_ratio
sum_open_interest
sum_open_interest_value
```

---

## Phase 2

변화율 추가:

```text
ls_change_15m
top_position_change_15m
taker_change_15m
oi_change_15m
```

---

## Phase 3

Divergence Feature 추가:

```text
retail_vs_top_gap
retail_vs_top_ratio
```

---

## Phase 4

다중 시간축 Feature 추가:

```text
5m
15m
30m
1h
```

---

# 25. 성능 평가 방법

새로운 metrics Feature를 추가할 때는 반드시 기존 모델과 비교한다.

예:

```text
Baseline
F17

Experiment A
F17 + Metrics Raw

Experiment B
F17 + Metrics Raw + Change

Experiment C
F17 + Metrics Raw + Change + Divergence
```

비교 대상:

```text
LogLoss
AUC
PR-AUC
Precision
Recall
Expected Value
Trade Count
Win Rate
Profit Factor
MDD
Backtest PnL
```

Feature Importance 또는 SHAP을 통해 실제로 Metrics Feature가 모델에 사용되고 있는지도 확인하는 것이 좋다.

---

# 26. 결론

바이낸스 선물 차트의 Long/Short 우세 정보는 일반 OHLCV 데이터가 아니라 **Futures Metrics 데이터**에 존재한다.

가장 직접적인 지표는:

```text
count_long_short_ratio
```

이다.

하지만 퀀트 시스템에서는 이것 하나만 사용하는 것보다 다음을 함께 사용하는 것이 더 유용하다.

```text
count_long_short_ratio
count_toptrader_long_short_ratio
sum_toptrader_long_short_ratio
sum_taker_long_short_vol_ratio
sum_open_interest
sum_open_interest_value
```

특히 다음 세 가지 정보의 괴리를 잡는 것이 중요하다.

```text
전체 시장 참여자 방향
Top Trader 방향
실제 Taker 체결 방향
```

여기에 Open Interest 변화를 추가하면 시장의 포지셔닝 상태를 보다 정교하게 표현할 수 있다.

현재 BTCUSDT 시스템의 기존 F17 가격/추세 기반 Feature와 성격이 다른 데이터이므로, **새로운 정보 축을 추가하는 Feature로서 테스트 가치가 높다.**

가장 중요한 구현 원칙은 다음이다.

```text
1분봉 OHLCV
+
5분 Futures Metrics
↓
merge_asof(direction="backward")
```

즉, 항상 **해당 시점에서 이미 관측 가능한 metrics 값만 사용하여 Future Leakage를 방지해야 한다.**

---

# 27. Live 환경에서 Metrics를 가져오는 방법

학습/백테스트에서는 Binance Archive의 `metrics` ZIP 데이터를 사용할 수 있지만, 실제 Live Trading에서는 **Binance USDⓈ-M Futures REST API**를 통해 거의 동일한 정보를 조회할 수 있다.

전체 구조는 다음과 같이 가져가는 것이 자연스럽다.

```text
TRAIN / BACKTEST
Binance Archive metrics
        ↓
동일 Feature Schema
        ↓
Model

LIVE
Binance Futures REST API
        ↓
동일 Feature Schema
        ↓
Model
```

즉 학습과 Live에서 데이터의 출처만 다르고, 모델에 들어가는 최종 Feature 이름과 의미는 동일하게 맞추는 것이 좋다.

---

# 28. Archive Metrics와 Live REST API 대응

대표적인 대응 관계는 다음과 같다.

| Archive metrics | Live REST API | 주요 응답값 |
|---|---|---|
| `count_long_short_ratio` | `/futures/data/globalLongShortAccountRatio` | `longShortRatio` |
| `count_toptrader_long_short_ratio` | `/futures/data/topLongShortAccountRatio` | `longShortRatio` |
| `sum_toptrader_long_short_ratio` | `/futures/data/topLongShortPositionRatio` | `longShortRatio` |
| `sum_taker_long_short_vol_ratio` | `/futures/data/takerlongshortRatio` | `buySellRatio` |
| `sum_open_interest` | `/futures/data/openInterestHist` | `sumOpenInterest` |
| `sum_open_interest_value` | `/futures/data/openInterestHist` | `sumOpenInterestValue` |
| 현재 Open Interest | `/fapi/v1/openInterest` | `openInterest` |

기본 REST API 주소는 일반적으로 다음을 사용한다.

```text
https://fapi.binance.com
```

---

# 29. 전체 시장 Long/Short Ratio Live 조회

전체 계정 기준 Long/Short Ratio는 다음 API로 조회할 수 있다.

```text
GET /futures/data/globalLongShortAccountRatio
```

예:

```text
GET https://fapi.binance.com/futures/data/globalLongShortAccountRatio
    ?symbol=BTCUSDT
    &period=5m
    &limit=1
```

응답 예시는 다음과 같은 형태다.

```json
[
    {
        "symbol": "BTCUSDT",
        "longShortRatio": "1.9559",
        "longAccount": "0.6617",
        "shortAccount": "0.3382",
        "timestamp": 1591261042378
    }
]
```

Live Feature로는 예를 들어 다음과 같이 매핑한다.

```text
longShortRatio
→ ls_all
```

Python:

```python
ls_all = float(data[-1]["longShortRatio"])
```

---

# 30. Top Trader Long/Short Ratio Live 조회

## 30.1 계정 수 기준

```text
GET /futures/data/topLongShortAccountRatio
```

Archive의 다음 값에 대응한다.

```text
count_toptrader_long_short_ratio
```

내부 Feature 이름 예:

```text
ls_top_account
```

---

## 30.2 포지션 규모 기준

```text
GET /futures/data/topLongShortPositionRatio
```

Archive의 다음 값에 대응한다.

```text
sum_toptrader_long_short_ratio
```

내부 Feature 이름 예:

```text
ls_top_position
```

퀀트 시스템에서는 단순 계정 수보다 **포지션 규모 기준 Top Trader Ratio**가 더 의미 있는 Feature가 될 가능성이 있다.

---

# 31. Taker Buy/Sell Ratio Live 조회

Taker Buy/Sell Ratio는 다음 API로 조회한다.

```text
GET /futures/data/takerlongshortRatio
```

예:

```text
GET https://fapi.binance.com/futures/data/takerlongshortRatio
    ?symbol=BTCUSDT
    &period=5m
    &limit=1
```

응답 예:

```json
[
    {
        "buySellRatio": "1.5586",
        "buyVol": "387.3300",
        "sellVol": "248.5030",
        "timestamp": 1591261042378
    }
]
```

내부 Feature 매핑:

```text
buySellRatio
→ taker_ratio
```

해석:

```text
taker_ratio > 1
→ Taker Buy 우세

taker_ratio < 1
→ Taker Sell 우세
```

즉 실제 시장가 주문의 공격 방향을 보여주는 Feature로 사용할 수 있다.

---

# 32. Open Interest Live 조회

Open Interest는 두 가지 방식으로 사용할 수 있다.

## 32.1 Archive와 유사한 통계형 OI

```text
GET /futures/data/openInterestHist
```

대표 응답값:

```text
sumOpenInterest
sumOpenInterestValue
timestamp
```

Archive의 다음 컬럼과 대응한다.

```text
sum_open_interest
sum_open_interest_value
```

---

## 32.2 현재 시점 Open Interest

Live 시스템에서는 현재 OI 자체도 조회할 수 있다.

```text
GET /fapi/v1/openInterest
```

예:

```text
GET https://fapi.binance.com/fapi/v1/openInterest
    ?symbol=BTCUSDT
```

응답 예:

```json
{
    "openInterest": "10659.509",
    "symbol": "BTCUSDT",
    "time": 1589437530011
}
```

내부 Feature 예:

```text
open_interest_current
```

Live에서는 이 값을 5분 통계값보다 더 자주 조회하여 보조 Feature로 사용할 수도 있다.

---

# 33. Live 1분봉 시스템에서의 추천 구조

1분마다 매매 판단을 한다고 가정하면 다음처럼 구성할 수 있다.

```text
                    Binance

1m Candle ───────────────→ Price Features

5m Global L/S ───────────→ ls_all
5m Top Account ──────────→ ls_top_account
5m Top Position ─────────→ ls_top_position
5m Taker Ratio ──────────→ taker_ratio

Current OI ──────────────→ open_interest_current

                           ↓

                    Feature Builder

                           ↓

                     CatBoost Model

                           ↓

                Long / Short / NoTrade
```

---

# 34. 5분 Metrics를 1분 Live 판단에 사용하는 방법

Long/Short, Top Trader, Taker 계열은 5분 단위 값이므로 매 1분마다 새 값을 기대할 수 없다.

따라서 다음과 같은 방식으로 가장 최근 확정값을 유지하는 것이 좋다.

```text
14:00 metrics 확정

14:00
14:01
14:02
14:03
14:04
→ 14:00 metrics 사용

14:05 새로운 metrics 확정

14:05
14:06
14:07
14:08
14:09
→ 14:05 metrics 사용
```

즉 학습 시 `merge_asof(direction="backward")`와 동일한 개념을 Live에서도 유지한다.

---

# 35. Live Feature Schema 통일

학습 데이터와 Live 데이터의 Feature 이름을 다르게 두면 관리가 복잡해진다.

예를 들어 학습에서는 Archive 컬럼을 그대로 모델에 넣지 말고 다음처럼 내부 표준 Feature 이름으로 변환한다.

```text
Archive

count_long_short_ratio
→ ls_all

count_toptrader_long_short_ratio
→ ls_top_account

sum_toptrader_long_short_ratio
→ ls_top_position

sum_taker_long_short_vol_ratio
→ taker_ratio

sum_open_interest
→ open_interest

sum_open_interest_value
→ open_interest_value
```

Live에서는 API 응답을 동일하게 변환한다.

```text
Live API

globalLongShortAccountRatio.longShortRatio
→ ls_all

topLongShortAccountRatio.longShortRatio
→ ls_top_account

topLongShortPositionRatio.longShortRatio
→ ls_top_position

takerlongshortRatio.buySellRatio
→ taker_ratio

openInterestHist.sumOpenInterest
→ open_interest

openInterestHist.sumOpenInterestValue
→ open_interest_value
```

결과적으로 모델 입장에서는 Train과 Live 입력 형식이 동일하다.

---

# 36. Live Timestamp 처리의 중요성

Metrics를 Live에 적용할 때 가장 중요한 문제 중 하나는 Timestamp 의미다.

단순히 API가 반환한 `timestamp`를 현재 1분봉에 바로 붙이면 안 된다.

각 API의 Timestamp가:

```text
구간 시작 시각
```

인지

```text
구간 종료 시각
```

인지 확인해야 한다.

특히 Taker Buy/Sell 계열처럼 **5분 동안 누적된 체결량을 나타내는 데이터**는 해당 5분 구간이 완전히 끝나기 전에 학습/매매 Feature로 사용하면 Future Leakage와 동일한 문제가 발생할 수 있다.

---

# 37. Taker Ratio Leakage 예시

예를 들어 API 데이터가 다음과 같다고 가정한다.

```text
timestamp = 14:00
period = 5m
```

그리고 이 값이 실제로:

```text
14:00 ~ 14:05
```

구간 전체의 Taker Buy/Sell Volume을 집계한 결과라면,

이 데이터를:

```text
14:00
14:01
14:02
```

시점의 Feature로 사용하면 안 된다.

왜냐하면 14:05까지의 체결 정보를 과거 시점 모델이 보는 셈이기 때문이다.

안전한 방식은:

```text
14:00 ~ 14:05 구간 데이터
→ 14:05 이후 사용
```

이다.

---

# 38. Live에서도 Train과 동일한 시간 규칙을 사용해야 한다

가장 중요한 원칙은 다음이다.

```text
TRAIN에서 사용 가능한 시점
=
LIVE에서 실제로 사용 가능한 시점
```

예를 들어 학습 데이터에서는 5분 Metrics를 구간 종료 후에만 사용했는데, Live에서는 구간 중간값을 사용한다면 Train/Live Feature Distribution이 달라질 수 있다.

반대로 학습에서 미래 5분 Metrics를 잘못 붙였다면 Backtest 성능만 비정상적으로 높아지고 실제 Live에서는 재현되지 않는다.

따라서 Timestamp 처리 규칙은 반드시 하나의 공통 모듈로 관리하는 것이 좋다.

---

# 39. Python Live API 예제

기본적인 Live 조회 코드는 다음처럼 구성할 수 있다.

```python
import requests

BASE = "https://fapi.binance.com"


def get_global_ls(symbol="BTCUSDT"):
    response = requests.get(
        f"{BASE}/futures/data/globalLongShortAccountRatio",
        params={
            "symbol": symbol,
            "period": "5m",
            "limit": 1,
        },
        timeout=5,
    )

    response.raise_for_status()

    data = response.json()[-1]

    return {
        "ls_all": float(data["longShortRatio"]),
        "long_account": float(data["longAccount"]),
        "short_account": float(data["shortAccount"]),
        "timestamp": int(data["timestamp"]),
    }
```

---

# 40. Taker Ratio 조회 예제

```python
def get_taker_ratio(symbol="BTCUSDT"):
    response = requests.get(
        f"{BASE}/futures/data/takerlongshortRatio",
        params={
            "symbol": symbol,
            "period": "5m",
            "limit": 1,
        },
        timeout=5,
    )

    response.raise_for_status()

    data = response.json()[-1]

    return {
        "taker_ratio": float(data["buySellRatio"]),
        "taker_buy_vol": float(data["buyVol"]),
        "taker_sell_vol": float(data["sellVol"]),
        "timestamp": int(data["timestamp"]),
    }
```

---

# 41. 현재 Open Interest 조회 예제

```python
def get_current_open_interest(symbol="BTCUSDT"):
    response = requests.get(
        f"{BASE}/fapi/v1/openInterest",
        params={
            "symbol": symbol,
        },
        timeout=5,
    )

    response.raise_for_status()

    data = response.json()

    return {
        "open_interest_current": float(data["openInterest"]),
        "timestamp": int(data["time"]),
    }
```

---

# 42. Live Metrics Provider 구조 추천

실제 프로그램에서는 API 호출 코드를 모델 코드에 직접 넣기보다 별도 Provider로 분리하는 것이 좋다.

예:

```text
BinanceMetricsProvider
│
├── get_global_long_short()
├── get_top_account_ratio()
├── get_top_position_ratio()
├── get_taker_ratio()
├── get_open_interest()
│
└── get_feature_snapshot()
```

최종적으로:

```python
features = provider.get_feature_snapshot("BTCUSDT")
```

하면 다음 형태를 반환하도록 한다.

```python
{
    "ls_all": 1.21,
    "ls_top_account": 0.94,
    "ls_top_position": 0.82,
    "taker_ratio": 0.91,
    "open_interest": 72341.0,
    "open_interest_value": 8240000000.0,
    "open_interest_current": 72412.0,
    "metrics_timestamp": ...
}
```

이 구조면 Live Trading 코드와 Feature 생성 코드를 분리할 수 있다.

---

# 43. API 호출 주기 추천

모든 Metrics API를 1초마다 호출할 필요는 없다.

예를 들어 다음처럼 구성할 수 있다.

```text
1m Candle
→ 매 1분 갱신

Long/Short Ratio
→ 5분 단위 갱신

Top Trader Ratio
→ 5분 단위 갱신

Taker Ratio
→ 5분 단위 갱신

Open Interest Hist
→ 5분 단위 갱신

Current Open Interest
→ 필요하면 10초~1분 단위 갱신
```

실제 호출 주기는 Binance API Rate Limit을 고려하여 조정해야 한다.

---

# 44. Metrics Cache 권장

5분 데이터는 1분마다 동일한 값을 여러 번 요청할 필요가 없다.

따라서 다음과 같은 Cache를 두는 것이 좋다.

```text
MetricsCache

last_global_ls
last_top_account
last_top_position
last_taker
last_oi_hist
last_update_time
```

새로운 5분 구간이 확정되었을 때만 API를 다시 조회한다.

---

# 45. API 실패 시 처리

Live 매매 시스템에서는 API 요청이 실패할 가능성을 반드시 고려해야 한다.

예:

```text
Timeout
HTTP Error
Rate Limit
Network Disconnect
Temporary Binance Failure
```

추천 처리 방식:

```text
API 실패

↓

// 최근 정상값이 충분히 최근인가?

YES
→ 제한적으로 이전 값 사용

NO
→ 해당 Metrics Feature를 invalid 처리
→ 필요하면 NoTrade
```

예를 들어 최근 정상값이 15분 이상 오래되었다면 해당 Metrics를 그대로 계속 사용하는 것보다 매매를 제한하는 것이 안전하다.

---

# 46. Feature Staleness 추가 추천

Live 시스템에서는 단순 Metrics 값뿐 아니라 **얼마나 오래된 데이터인지**도 Feature 또는 Safety 조건으로 사용할 수 있다.

예:

```text
metrics_age_seconds
taker_age_seconds
oi_age_seconds
```

예:

```python
metrics_age_seconds = (
    current_timestamp - metrics_timestamp
) / 1000.0
```

이 값이 비정상적으로 크면 Metrics가 stale 상태라고 판단할 수 있다.

---

# 47. Train / Live 공통 Feature Builder 추천

최종적으로 다음 구조를 추천한다.

```text
                Feature Builder
                     ↑
          ┌──────────┴──────────┐
          │                     │
     Archive Loader       Live Provider
          │                     │
      TRAIN/BACKTEST           LIVE
```

두 입력 소스가 같은 표준 DataFrame 또는 Dictionary를 반환한다.

예:

```text
timestamp
ls_all
ls_top_account
ls_top_position
taker_ratio
open_interest
open_interest_value
```

이후 변화율 및 파생 Feature는 **동일한 Feature Builder**에서 계산한다.

예:

```text
ls_change_15m
top_position_change_15m
taker_change_15m
oi_change_15m
retail_vs_top_gap
```

이렇게 해야 Train과 Live에서 계산식이 달라지는 문제를 막을 수 있다.

---

# 48. 최종 권장 아키텍처

```text
TRAIN
────────────────────────────────────────────

Binance Archive
    │
    ├── 1m OHLCV
    └── 5m Futures Metrics
              │
              ▼
        Timestamp Align
              │
              ▼
       Feature Builder
              │
              ▼
          CatBoost


LIVE
────────────────────────────────────────────

Binance API
    │
    ├── 1m Candle
    ├── Global L/S
    ├── Top Account
    ├── Top Position
    ├── Taker Ratio
    └── Open Interest
              │
              ▼
        Metrics Cache
              │
              ▼
        Timestamp Align
              │
              ▼
       Same Feature Builder
              │
              ▼
        Same CatBoost Model
              │
              ▼
       Long / Short / NoTrade
```

핵심은 다음과 같다.

```text
Archive와 Live API의 원본 형식은 달라도
모델에 들어가는 Feature는 완전히 동일하게 만든다.
```

그리고 반드시:

```text
현재 시점에서 실제로 알 수 있는 데이터만 사용
```

해야 한다.

이 원칙만 지키면 Binance Archive 기반 학습 데이터와 Binance REST API 기반 Live Trading 데이터를 자연스럽게 연결할 수 있다.

