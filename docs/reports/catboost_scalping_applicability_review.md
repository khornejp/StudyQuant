# CatBoost Bitcoin Scalping 전략 적용성 분석 검토 보고서

## 1. 개요

본 문서는 `STRATEGY_APPLICABILITY_ANALYSIS.md`에서 정리한 **CatBoost 기반 비트코인 스캘핑 전략의 현재 프로젝트 반영 가능성**을 검토하고, 실제 구현 전에 보완해야 할 사항을 정리한 보고서이다.

검토 대상은 현재 프로젝트가 보유한 다음 구조를 기준으로 한다.

```text
- BTCUSDT 1m Quant Trading System v7.18
- 115개 F01~F13 피처 체계
- Regime-aware ensemble 구조
- CatBoost / LightGBM 기반 모델
- Triple-barrier 라벨링
- Walk-forward validation
- CPCV / purged CV / embargo 구조
```

전체적으로 원본 보고서의 방향은 타당하다.  
특히 다음 결론은 현재 프로젝트에 매우 적합하다.

```text
다음 가격 예측
→ TP가 SL보다 먼저 맞을 확률 예측

단일 모델
→ LONG / SHORT 분리 모델

비용 무시
→ 비용 반영 EV 게이트
```

다만 일부 항목은 그대로 구현하면 성능이 왜곡될 가능성이 있다.  
따라서 본 문서에서는 원본 분석의 타당한 부분과 수정해야 할 부분을 구분하여 정리한다.

---

## 2. 전체 판단

현재 프로젝트는 CatBoost 기반 스캘핑 전략을 적용하기 위한 기초 인프라가 충분하다.

이미 다음 요소가 존재하기 때문이다.

```text
1. 1분봉 OHLCV 기반 학습 데이터 파이프라인
2. 다수의 가격 / 추세 / 변동성 / 거래량 / 미시구조 / 펀딩 관련 피처
3. Triple-barrier 라벨링 구조
4. Regime-aware ensemble 구조
5. Walk-forward validation
6. CPCV / purged CV / embargo 기반 검증
7. CatBoost GPU 학습 지원
8. 실전 추론 및 TP/SL 브라켓 주문 구조
```

따라서 완전히 새로운 시스템을 만드는 것이 아니라, 기존 구조를 다음 방향으로 바꾸는 것이 핵심이다.

```text
기존:
미래 방향성 또는 수익성 예측 중심

변경:
현재 시점에서 LONG 또는 SHORT에 진입했을 때
TP가 SL보다 먼저 도달할 확률을 예측하는 구조
```

---

## 3. 원본 보고서에서 타당한 부분

### 3.1 전략 적용 우선순위는 적절함

현재 프로젝트가 1분봉 OHLCV 중심이라면, 아래 3개 전략을 우선 적용하는 판단은 적절하다.

```text
1. 변동성 압축 후 확장 돌파
2. 마이크로 추세 눌림목
3. 가짜 돌파 / 유동성 스윕 탐지
```

이 전략들은 현재 보유 중인 1분봉 OHLCV, 거래량, 변동성, 추세 피처만으로도 어느 정도 구현이 가능하다.

반면 다음 전략들은 데이터 소스가 추가되어야 하므로 후순위가 맞다.

```text
- 호가창 불균형 스캘핑
- 체결강도 기반 스캘핑
- CVD 기반 스캘핑
- 청산 데이터 기반 스캘핑
- 실시간 order book depth 기반 전략
```

### 3.2 Phase 1-2 중심 로드맵은 적절함

원본 보고서에서 제안한 다음 순서는 타당하다.

```text
Phase 1:
파라미터 조정 + 피처 추가

Phase 2:
LONG / SHORT 분리 모델
Short-side triple-barrier 라벨
비용 반영 라벨
expected_net_return 구조
```

즉시 적용 가능한 항목은 다음이다.

```text
- 시간 / 세션 피처 추가
- RSI 추가
- MACD 추가
- Bollinger Band width 추가
- rolling VWAP 추가
- EMA slope 추가
- TP / SL / horizon 실험 구조 추가
```

이후 구조적으로 반영해야 할 항목은 다음이다.

```text
- label_long_success
- label_short_success
- long_success_model
- short_success_model
- long_ev / short_ev 계산
- 비용 반영 의사결정 게이트
```

### 3.3 현재 코드베이스 기반 평가도 타당함

현재 프로젝트는 이미 다음 구조를 갖고 있다.

```text
- CatBoost 기반 학습 구조
- Regime-aware ensemble
- Triple-barrier 라벨링
- Walk-forward 검증
- Per-regime 모델 구조
```

따라서 전략 문서의 Phase 1-2를 구현하기에 충분한 기반이 있다.

중요한 것은 다음 세 가지 전환이다.

```text
1. 라벨링 전환
2. 모델 출력 구조 전환
3. 실전 진입 조건 전환
```

---

## 4. 수정해야 할 핵심 사항

### 4.1 Horizon 5분 고정은 위험함

원본 보고서에서는 스캘핑 목적에 맞춰 horizon을 기존 60분에서 5분으로 줄이는 것을 제안했다.

방향 자체는 맞다.  
그러나 1분봉 기반에서 horizon을 5분으로 고정하는 것은 위험하다.

#### 문제점

```text
1. 5분 horizon은 캔들 5개만 사용하므로 라벨이 매우 noisy해질 수 있음
2. TP와 SL이 같은 1분봉 안에서 동시에 터질 가능성이 커짐
3. high/low 순서 판정 문제가 커짐
4. 수수료와 슬리피지 영향이 상대적으로 커짐
5. 거래 횟수는 늘지만 거래 품질은 떨어질 수 있음
```

#### 권장 방식

5분 하나로 고정하지 말고, 다음 후보를 모두 실험해야 한다.

```text
horizon 후보:
5분
10분
15분
30분
```

TP/SL도 하나로 고정하지 말고 grid 실험이 필요하다.

```text
TP / SL 후보:
+0.12% / -0.08%
+0.15% / -0.10%
+0.20% / -0.12%
+0.30% / -0.15%
```

#### 결론

```text
60분 → 5분 단순 변경 금지

대신:
horizon / TP / SL grid 실험 구조로 구현
```

---

### 4.2 expected_return 단일 모델은 위험함

원본 보고서의 의사코드에서는 다음과 같은 구조가 제안되었다.

```python
long_success_prob = long_model.predict_proba(features)
short_success_prob = short_model.predict_proba(features)
expected_return = return_model.predict(features)

if long_success_prob > threshold and expected_return > cost + margin:
    enter_long()
elif short_success_prob > threshold and expected_return > cost + margin:
    enter_short()
else:
    no_trade()
```

이 구조에는 문제가 있다.

`expected_return`이 다음 중 무엇인지 불명확하기 때문이다.

```text
- signed return인가?
- long 기준 expected return인가?
- short 기준 expected return인가?
- 특정 후보 전략 기준 return인가?
```

#### 권장 구조

LONG과 SHORT의 기대값을 반드시 분리해야 한다.

```python
long_prob = long_model.predict_proba(X)[:, 1]
short_prob = short_model.predict_proba(X)[:, 1]

long_ev = long_ev_model.predict(X)
short_ev = short_ev_model.predict(X)

if long_prob > long_threshold and long_ev > min_ev:
    enter_long()
elif short_prob > short_threshold and short_ev > min_ev:
    enter_short()
else:
    no_trade()
```

초기에는 EV 회귀 모델 없이 확률 기반 계산식만 사용해도 된다.

```python
long_ev = long_prob * net_long_tp - (1.0 - long_prob) * abs(net_long_sl)
short_ev = short_prob * net_short_tp - (1.0 - short_prob) * abs(net_short_sl)
```

#### 결론

```text
expected_return 단일 모델 금지

대신:
long_ev / short_ev 분리
```

---

### 4.3 전체 timestamp 학습보다 전략 후보 필터가 필요함

스캘핑 모델에서 모든 1분봉 시점을 학습 대상으로 삼으면 대부분은 진입할 필요가 없는 구간이다.

이 경우 모델은 다음을 과도하게 학습할 수 있다.

```text
NO_TRADE
```

결국 모델이 진입하지 않는 쪽으로만 최적화될 가능성이 있다.

#### 권장 구조

전략별 후보를 먼저 생성한 뒤, 후보에 대해서만 라벨을 붙이는 것이 좋다.

```text
전체 1분봉 데이터
    ↓
전략별 후보 생성
    ↓
후보별 triple-barrier 라벨 생성
    ↓
CatBoost 학습
```

#### 예시: 변동성 압축 돌파 후보

```text
조건 예시:
- bb_width_20이 최근 분위수 하위권
- range_compression_ratio 발생
- volume_zscore 상승
- 가격이 최근 high/low 근처 접근
- ATR 대비 돌파 거리가 의미 있음
```

#### 예시: 눌림목 후보

```text
조건 예시:
- 상위 프레임 EMA 정렬이 상승 또는 하락
- 가격이 rolling VWAP 또는 EMA 근처로 되돌림
- pullback_depth가 일정 범위 안에 있음
- 거래량 감소 후 반등 거래량 증가
```

#### 결론

```text
전체 timestamp 직접 학습
→ 전략 후보 생성 후 후보별 학습
```

---

### 4.4 RegimeDetector를 바로 CatBoost로 바꾸는 것은 후순위

원본 보고서에서는 Phase 4에서 시장 국면 분류를 CatBoostClassifier로 전환하는 방안을 제안했다.

하지만 현재 프로젝트가 이미 다음 구조를 가지고 있다면, 국면 분류 모델 교체는 후순위가 맞다.

```text
- up / down / range 국면 분류
- per-regime ensemble
- regime-aware training
```

#### 권장 우선순위

```text
1순위:
기존 regime 값을 feature 또는 group 정보로 사용

2순위:
regime별 threshold 최적화

3순위:
regime별 TP / SL / horizon 다르게 적용

4순위:
국면 분류 자체를 CatBoostClassifier로 대체
```

#### 결론

```text
국면 분류 모델 교체보다
라벨링 / LONG-SHORT 분리 / EV 게이트가 먼저다.
```

---

### 4.5 비용 반영은 라벨 보정만으로 부족함

원본 보고서에는 비용 반영 라벨 예시가 들어가 있다.

```python
label = 1 if tp_first and (tp_pct - total_cost) > 0 else 0
```

하지만 실전에서는 라벨뿐 아니라 최종 의사결정에서도 비용을 반영해야 한다.

#### 비용 구성 예시

```text
fee_entry
fee_exit
slippage
spread_cost
safety_margin
```

#### LONG 기준 net TP / SL

```text
gross_tp = +0.15%
gross_sl = -0.10%

net_long_tp = gross_tp - fee_entry - fee_exit - slippage - spread_cost
net_long_sl = gross_sl - fee_entry - fee_exit - slippage - spread_cost
```

#### SHORT 기준 net TP / SL

```text
gross_tp = +0.15% 수익
gross_sl = -0.10% 손실

net_short_tp = gross_tp - fee_entry - fee_exit - slippage - spread_cost
net_short_sl = gross_sl - fee_entry - fee_exit - slippage - spread_cost
```

#### EV 계산

```text
EV = p_success * net_tp - (1 - p_success) * abs(net_sl)
```

#### 진입 조건

```text
EV > min_expected_value
```

#### 결론

```text
비용 반영은 라벨 단계 + 의사결정 단계 둘 다 필요하다.
```

---

### 4.6 CatBoostRanker는 후순위

원본 보고서에서는 CatBoostRanker가 Phase 3에 들어가 있다.

방향은 나쁘지 않지만, 바로 적용하기에는 이르다.

CatBoostRanker를 쓰려면 먼저 다음 구조가 필요하다.

```text
후보 1: LONG breakout
후보 2: SHORT breakdown
후보 3: LONG pullback
후보 4: SHORT pullback
후보 5: FAKEOUT filter
후보 6: NO_TRADE
```

현재 코드가 후보 전략 체계를 갖고 있지 않다면 Ranker는 복잡도만 높일 수 있다.

#### 권장 순서

```text
1. LONG / SHORT 이진 분리 모델
2. long_ev / short_ev 계산
3. 전략별 후보 생성기
4. 후보별 성과 비교
5. 그 다음 CatBoostRanker 적용
```

#### 결론

```text
CatBoostRanker는 후보 체계가 만들어진 뒤 적용한다.
```

---

## 5. 보완된 최종 구현 로드맵

### Phase 0: 현재 구조 검증

구현 전에 먼저 기존 구조의 누수와 라벨 의미를 확인해야 한다.

#### 확인 항목

```text
1. 현재 label=1이 long TP만 의미하는지 확인
2. direction_model과 profitability_model의 타겟 중복 여부 확인
3. meta_model이 OOF prediction으로 학습되는지 확인
4. stacking leakage 여부 확인
5. triple-barrier에서 high/low 동시 터치 처리 방식 확인
6. 현재 봉의 high/low/close 사용 시점 확인
7. 라벨 생성 시 미래 데이터가 feature에 섞이지 않는지 확인
```

#### 목적

```text
기존 구조의 leakage를 먼저 제거해야
LONG / SHORT 분리 구조에서도 같은 문제가 반복되지 않는다.
```

---

### Phase 1: 스캘핑 피처 추가

원본 보고서의 Phase 1은 대부분 바로 적용 가능하다.

#### 시간 / 세션 피처

```text
hour
minute
day_of_week
session_asia
session_europe
session_us
```

암호화폐는 24시간 시장이므로 세션은 다음처럼 나눌 수 있다.

```text
Asia session
Europe session
US session
session_overlap
weekend_flag
```

#### 기술 지표 피처

```text
RSI_7
RSI_14
MACD_line
MACD_signal
MACD_hist
Bollinger_width
Bollinger_percent_b
EMA_5_slope
EMA_20_slope
EMA_60_slope
```

#### VWAP 피처

주식처럼 장 시작 기준 VWAP보다는 rolling VWAP이 적합하다.

```text
rolling_vwap_20
rolling_vwap_60
rolling_vwap_240
price_vs_rolling_vwap_20
price_vs_rolling_vwap_60
price_vs_rolling_vwap_240
```

#### 추가 후보 피처

```text
pullback_depth
pullback_duration
volume_decline_ratio
rebound_volume_ratio
range_compression_ratio
breakout_strength
fakeout_return_inside_speed
```

---

### Phase 2: LONG / SHORT 라벨 분리

가장 중요한 단계다.

#### 생성할 라벨

```text
label_long_success
label_short_success
```

#### LONG 라벨

```text
현재 시점에서 LONG 진입 가정

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

#### SHORT 라벨

```text
현재 시점에서 SHORT 진입 가정

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

#### 파라미터 sweep

```text
horizon:
5 / 10 / 15 / 30

TP / SL:
0.12 / 0.08
0.15 / 0.10
0.20 / 0.12
0.30 / 0.15
```

#### Timeout 처리

Timeout은 처음부터 무조건 실패로 고정하지 말고 세 가지를 비교한다.

```text
방식 A:
Timeout = 0

방식 B:
Timeout sample 제외

방식 C:
Timeout 중 미래 순수익률이 비용 이상이면 성공, 아니면 실패
```

---

### Phase 3: 모델 구조 변경

#### 기본 모델

```text
long_success_model:
CatBoostClassifier

short_success_model:
CatBoostClassifier
```

#### 선택 모델

```text
long_ev_model:
CatBoostRegressor

short_ev_model:
CatBoostRegressor
```

초기에는 EV 회귀 모델 없이 확률 기반 EV 계산으로 시작한다.

#### 의사결정 로직

```python
long_prob = long_model.predict_proba(X)[:, 1]
short_prob = short_model.predict_proba(X)[:, 1]

long_ev = long_prob * net_long_tp - (1.0 - long_prob) * abs(net_long_sl)
short_ev = short_prob * net_short_tp - (1.0 - short_prob) * abs(net_short_sl)

if long_ev > min_ev and long_prob > long_threshold:
    signal = "LONG"
elif short_ev > min_ev and short_prob > short_threshold:
    signal = "SHORT"
else:
    signal = "NO_TRADE"
```

#### 추가 권장사항

CatBoost 확률은 반드시 calibration을 검토해야 한다.

```text
- Platt scaling
- Isotonic calibration
- validation OOF 기반 calibration
```

확률 calibration이 안 되어 있으면 EV 계산이 왜곡될 수 있다.

---

### Phase 4: 전략 후보 기반 학습

기본 LONG / SHORT 모델이 안정화된 뒤에는 전략 후보 기반 구조로 확장한다.

#### 후보 타입 예시

```text
breakout_candidate
breakdown_candidate
pullback_long_candidate
pullback_short_candidate
fakeout_candidate
mean_reversion_candidate
```

#### 후보별 저장 정보

```text
timestamp
candidate_type
candidate_direction
candidate_strength
features
label_success
future_net_return
regime
```

#### 모델 확장 예시

```text
long_breakout_model
short_breakdown_model
long_pullback_model
short_pullback_model
fakeout_filter_model
```

#### 목적

```text
모든 시점에서 진입 여부를 판단하는 모델
→ 의미 있는 후보에서 성공 확률을 판단하는 모델
```

---

### Phase 5: 고급 데이터 추가

호가창, tick, CVD, OI, 청산 데이터는 중기 이후에 추가한다.

#### 우선순위

```text
1순위:
1m OHLCV + taker_buy_volume + trade_count

2순위:
funding / mark price / premium index / open interest

3순위:
order book snapshot

4순위:
tick trade / CVD

5순위:
liquidation stream
```

#### 이유

호가창과 tick 데이터는 단순 피처 추가가 아니다.

다음 문제가 함께 따라온다.

```text
- 수집 주기
- 저장 용량
- timestamp 정렬
- 1분봉과의 동기화
- 백테스트 재현성
- 실시간 추론 latency
- missing data 처리
```

따라서 기존 1분봉 기반 구조가 안정화된 뒤 추가하는 것이 맞다.

---

### Phase 6: CatBoostRanker 검토

전략 후보 체계가 만들어진 뒤 Ranker를 적용한다.

#### Ranker 적용 조건

```text
1. 후보 타입이 명확해야 함
2. 같은 timestamp에 여러 후보가 존재해야 함
3. 후보별 미래 net_return이 계산되어야 함
4. group_id를 timestamp 또는 session 단위로 묶을 수 있어야 함
```

#### 데이터 구조 예시

```text
group_id = timestamp

candidate 1:
LONG_BREAKOUT
label = future_net_return

candidate 2:
SHORT_PULLBACK
label = future_net_return

candidate 3:
NO_TRADE
label = 0
```

#### 권장 시점

```text
LONG / SHORT 분리 모델의 백테스트 성능이 안정화된 이후
```

---

## 6. 최종 추천 구현 순서

가장 안전한 구현 순서는 다음이다.

```text
1. 현재 라벨 / stacking / triple-barrier 누수 여부 검증
2. RSI / MACD / Bollinger / rolling VWAP / 시간 피처 추가
3. LONG / SHORT triple-barrier 라벨 분리
4. horizon / TP / SL grid 실험
5. long_model / short_model CatBoostClassifier 학습
6. probability calibration 적용 여부 검토
7. EV 기반 진입 게이트 추가
8. 전략 후보 생성기 추가
9. 후보별 모델 또는 필터 모델 추가
10. 그 다음 Ranker 또는 호가창 / tick 데이터 연동 검토
```

---

## 7. 반영 우선순위 표

| 우선순위 | 항목 | 적용 난이도 | 예상 효과 | 판단 |
|---:|---|---:|---:|---|
| 1 | 기존 라벨 / 누수 검증 | 중간 | 매우 높음 | 필수 |
| 2 | RSI / MACD / Bollinger / VWAP 피처 | 낮음 | 중간~높음 | 즉시 적용 |
| 3 | 시간 / 세션 피처 | 낮음 | 중간 | 즉시 적용 |
| 4 | LONG / SHORT 라벨 분리 | 중간 | 매우 높음 | 핵심 |
| 5 | horizon / TP / SL grid | 중간 | 높음 | 필수 |
| 6 | long / short 모델 분리 | 중간 | 매우 높음 | 핵심 |
| 7 | EV 기반 진입 게이트 | 중간 | 높음 | 필수 |
| 8 | Probability calibration | 중간 | 중간~높음 | 권장 |
| 9 | 전략 후보 생성기 | 중간~높음 | 높음 | 단기 이후 |
| 10 | CatBoostRanker | 높음 | 중간 | 후순위 |
| 11 | 호가창 / tick / CVD | 높음 | 높음 | 중기 이후 |
| 12 | 국면 분류 CatBoost 전환 | 중간 | 중간 | 후순위 |

---

## 8. 최종 결론

원본 `STRATEGY_APPLICABILITY_ANALYSIS.md`의 방향은 전반적으로 타당하다.

특히 다음 판단은 그대로 유지해도 된다.

```text
현재 코드베이스는 Phase 1-2 구현 기반이 충분하다.
핵심은 라벨링과 모델 구조의 방향 전환이다.
LONG / SHORT 분리와 비용 반영이 우선이다.
호가창 / tick / CVD는 데이터 기반이 없으면 후순위다.
```

다만 실제 구현 전에는 다음을 반드시 수정해야 한다.

```text
1. horizon 5분 고정 금지
   → 5 / 10 / 15 / 30분 sweep

2. expected_return 단일 모델 금지
   → long_ev / short_ev 분리

3. 전체 timestamp 학습 지양
   → 전략 후보 필터 선행

4. CatBoostRanker 조기 적용 금지
   → 후보 체계 구축 후 적용

5. 국면 분류 CatBoost 전환은 후순위
   → 기존 regime을 먼저 활용

6. 비용 반영은 라벨뿐 아니라 EV 계산까지 연결
```

따라서 최종 권장 방향은 다음과 같다.

```text
Phase 0:
현재 구조 검증

Phase 1:
스캘핑 피처 추가

Phase 2:
LONG / SHORT 라벨 분리

Phase 3:
LONG / SHORT CatBoostClassifier 분리 학습

Phase 4:
EV 기반 진입 게이트

Phase 5:
전략 후보 생성기

Phase 6:
Ranker 또는 고급 데이터 연동
```

한 문장으로 요약하면 다음과 같다.

```text
현재 프로젝트는 CatBoost 스캘핑 전략을 적용하기에 충분한 기반을 갖추고 있으며,
가장 먼저 해야 할 일은 피처 추가가 아니라
LONG / SHORT 라벨 분리와 비용 반영 EV 의사결정 구조를 만드는 것이다.
```
