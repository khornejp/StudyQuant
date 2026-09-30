# Kaggle G-Research Crypto Forecasting 발표 내용 추출 요약

> 원본: `Kaggle_G-Research Crypto Forecasting 발표.pdf`  
> 형태: 이미지 기반 PDF 7페이지  
> 주제: G-Research Crypto Forecasting 문제 정의, 데이터 전처리, 타겟 정의, 평가 지표, 주요 접근법 비교

---

# 1. 문제 정의 및 데이터 개요

## 1.1 Mission & Constraints

G-Research 가상자산 수익률 예측 문제의 목표는 다음과 같다.

```text
14개 주요 가상자산(BTC, ETH, DOGE 등)의 미래 수익률 예측
```

핵심 목표는 단순히 시장 전체 흐름을 맞추는 것이 아니라, 개별 자산의 고유 움직임을 예측하는 것이다.

```text
시장 전체 흐름 = Beta
개별 자산 고유 움직임 = Alpha
```

즉 이 문제는 다음에 집중한다.

```text
시장 공통 방향성을 제거하고,
개별 자산의 독립적인 초과 움직임을 예측
```

제약 조건:

```text
Runtime: 9 hours
Memory: 16GB RAM
```

따라서 모델 복잡성과 효율성 사이의 trade-off가 중요하다.

---

## 1.2 Data Schema: train.csv

학습 데이터는 분 단위 가상자산 OHLCV 데이터로 구성된다.

| Column | 의미 |
|---|---|
| timestamp | 분 단위 타임스탬프 |
| Asset_ID | 가상자산 식별 코드 |
| Count | 해당 구간 거래 수 |
| Open | 시가 |
| High | 고가 |
| Low | 저가 |
| Close | 종가 |
| Volume | 거래량 |
| VWAP | 거래량 가중 평균 가격 |
| Target | 예측 대상 수익률 |

`Target`은 단순 미래 수익률이 아니라, 시장 요인을 제거한 residualized return이다.

```text
예측 대상:
15분 잔차 수익률
Residualized Return
```

---

# 2. 데이터 전처리 전략 및 주요 난관

## 2.1 Missing Data 처리: Gap Filling

가상자산 데이터에는 특정 시간 구간의 row가 비어 있는 문제가 발생할 수 있다.

발표에서는 이를 NaN 값이 아니라 **row 자체의 부재**로 설명한다.

처리 방식:

```text
1. 전체 시간축으로 reindex
2. 비어 있는 timestamp 생성
3. 이전 유효 값으로 forward fill
```

개념:

```text
Data → Data → Empty/Gap → Data
                 ↓
          Forward Fill
```

즉 결측 구간은 이전 유효 값으로 복원한다.

---

## 2.2 가격 스케일링: Log Return

자산마다 가격 단위가 다르기 때문에 raw price를 그대로 비교하기 어렵다.

따라서 log return으로 변환한다.

```math
Log Return = log(Price_t / Price_{t-1})
```

의미:

```text
자산별 가격 단위 차이를 제거
수익률을 서로 비교 가능하게 변환
비정상성 완화
```

---

## 2.3 Market Challenges

발표에서 강조하는 시장 데이터의 핵심 난관은 세 가지다.

## A. Non-stationarity

```text
시간에 따라 통계적 특성, 평균, 분산이 변함
```

따라서 고정된 분포를 가정하는 모델은 취약할 수 있다.

필요한 접근:

```text
stationarity test
rolling feature
local standardization
walk-forward validation
```

---

## B. High Correlation

```text
자산 간 높은 동조화 현상
개별 자산의 고유 움직임 포착 어려움
```

가상자산 시장은 전체 시장 방향으로 함께 움직이는 경향이 강하다.

따라서 단순히 BTC나 전체 시장 흐름을 맞추는 것이 아니라, 각 자산의 alpha를 분리해야 한다.

---

## C. Volatility & Manipulation

```text
급격한 변동성
Meme coin 등에서 발생 가능한 시세 조작
```

이로 인해 outlier와 regime shift에 강한 모델링이 필요하다.

---

# 3. Target 정의: 시장 중립적 수익률

발표의 핵심은 target이 단순 미래 수익률이 아니라는 점이다.

```text
Target = 시장 전체 흐름을 제거한 개별 자산의 Alpha
```

이를 만들기 위한 4단계 프로세스가 제시된다.

---

## 3.1 Step 1: Log Return

자산 a의 미래 수익률을 계산한다.

```math
R^a(t) = log(P^a(t+16) / P^a(t+1))
```

의미:

```text
15분간 가격 변화
1분 지연 체결 가정
```

---

## 3.2 Step 2: Market Return

전체 시장 수익률을 계산한다.

```text
모든 자산의 수익률을 asset weight를 반영해 평균
```

개념:

```text
M(t) = weighted average return of all assets
```

즉 특정 자산만의 움직임이 아니라 시장 전체 흐름을 구한다.

---

## 3.3 Step 3: Beta 계산

각 자산의 시장 민감도 beta를 계산한다.

```math
β^a = <M · R^a> / <M^2>
```

발표에서는 rolling window를 사용한다.

```text
Rolling Window: 3,750분
약 2.6일
```

의미:

```text
해당 자산이 시장 전체 움직임에 얼마나 민감한지 측정
```

---

## 3.4 Step 4: Linear Residualization

최종 target은 다음과 같다.

```math
Target^a(t) = R^a(t) - β^a M(t)
```

의미:

```text
전체 수익률 - 시장 흐름 기여분 = 순수 Alpha
```

즉 모델은 시장 전체 상승/하락을 맞추는 것이 아니라, 시장 효과를 제거한 개별 자산의 residual return을 예측한다.

---

# 4. 평가 지표: Weighted Pearson Correlation

평가 지표는 weighted Pearson correlation이다.

## 4.1 개념

예측값과 실제 target 간의 상관계수를 계산하되, 자산별 weight를 반영한다.

```text
Weight가 높은 자산을 잘 맞추는 것이 점수에 더 중요
```

즉 모든 자산을 동일하게 보는 것이 아니라, 중요도가 높은 자산의 예측 성능이 평가 점수에 더 크게 반영된다.

---

## 4.2 계산 흐름

발표의 코드 개념은 다음과 같다.

```python
def weighted_pearson(a, b):
    w = corrdf.Weight.values
    sumw = w.sum()

    # Weighted Mean
    ma = (w * a).sum() / sumw
    mb = (w * b).sum() / sumw

    # Covariance and Variance
    covab = (a * b * w).sum() / sumw - ma * mb
    covaa = (w * (a - ma) * (a - ma)).sum() / sumw
    covbb = (w * (b - mb) * (b - mb)).sum() / sumw

    return covab / np.sqrt(covaa * covbb)
```

핵심:

```text
예측값과 실제값의 방향성이 얼마나 일치하는지 평가
자산 weight가 점수에 반영됨
```

---

# 5. 접근법 1: LightGBM & 정교한 Feature Engineering

발표에서는 3위 솔루션으로 LightGBM 기반 수동 feature engineering 접근법을 소개한다.

---

## 5.1 The Engineer's Approach

핵심 철학:

```text
복잡한 모델보다 잘 설계된 feature와 검증 구조를 중시
```

주요 구성:

```text
1. Data Lightweighting
2. Lag Features
3. Market Neutrality
4. Embargo CV
```

---

## 5.2 Data Lightweighting

메모리와 속도 제약 때문에 모든 OHLCV를 다 쓰지 않고, 주로 Close 가격만 사용한다.

```text
Close 가격만 사용
메모리 효율 극대화
```

의미:

```text
복잡한 raw feature를 줄이고,
핵심 가격 흐름에 집중
```

---

## 5.3 Lag Features

과거 시점의 가격/수익률 정보를 feature로 사용한다.

발표에 제시된 lag 예:

```text
60분 전
300분 전
900분 전
```

의미:

```text
단기/중기/장기 momentum 또는 reversal 정보 활용
```

---

## 5.4 Market Neutrality Feature

입력 feature 단계에서도 시장 효과를 제거한다.

```text
Feature_Neutral = Feature_Raw - Market_Avg_Feature
```

의미:

```text
전체 시장 공통 움직임을 제거하고
개별 자산의 상대적 움직임에 집중
```

---

## 5.5 Validation: Embargo CV

시계열 데이터에서는 leakage를 막기 위해 train/test 사이에 물리적 시간 간격을 둔다.

발표에서는 다음 embargo period를 사용한다.

```text
Embargo Period: 3,750 minutes
```

이유:

```text
시계열 자기상관성 방지
target leakage 방지
train/test 사이에 충분한 시간 gap 확보
```

발표에 나온 결과 예:

```text
Litecoin: 0.0945
Ethereum: 0.0891
```

---

# 6. 접근법 2: Axial Attention Transformer

발표에서는 7위 솔루션으로 Axial Attention Transformer 접근법을 소개한다.

---

## 6.1 Input: Raw Data & Local Standardization

입력 데이터:

```text
OHLCV + log(volume)
```

전처리:

```text
Local Standardization
```

의미:

```text
시퀀스 내 상대적 위치를 학습
비정상성 극복
```

즉 전체 기간 기준의 고정 scaler보다, 로컬 구간 내 정규화를 통해 현재 위치의 상대적 의미를 학습한다.

---

## 6.2 Architecture: Axial Attention

Axial Attention은 두 방향의 attention을 사용한다.

## A. Time-wise Attention

```text
각 자산의 시간 흐름 학습
Momentum Learning
```

즉 특정 자산 안에서 시간에 따른 패턴을 학습한다.

---

## B. Asset-wise Attention

```text
동시간대 자산 간 상호작용 학습
Correlation Learning
```

즉 같은 시간대에 여러 자산이 어떻게 함께 움직이는지, 어떤 자산이 다른 자산에 영향을 주는지 학습한다.

발표의 설명:

```text
모델 구조적으로 시장 중립성 및 상관관계 학습
```

---

## 6.3 Winning Edge: Multi-window Ensemble

단일 시계열 window만 쓰지 않고 여러 window 길이의 모델을 앙상블한다.

제시된 window:

```text
45 min
60 min
90 min
120 min
```

최종 예측:

```text
각 window 모델의 평균
```

발표의 핵심 메시지:

```text
단일 모델 28위
앙상블 7위
```

즉 서로 다른 시간 가정을 가진 모델을 결합하면 성능이 크게 향상될 수 있다.

---

# 7. Feature Engineering vs Model Architecture 비교

발표의 마지막 페이지는 LightGBM 접근법과 Deep Learning 접근법을 비교한다.

| 항목 | LightGBM 3위 | Deep Learning 7위 |
|---|---|---|
| Philosophy | Manual Feature Engineering | Automated Architecture Learning |
| Data | Close Price Only, Lightweight | Full OHLCV Raw Data |
| Neutrality | Manual, Feature - Market Avg | Structural, Axial Attention |
| Validation | Embargo CV, 7-Fold | Standard CV, 3-Fold |
| Ensemble | Single Model | Multi-window Ensemble |

---

# 8. 핵심 교훈

## 8.1 Validation is Critical

```text
정보 누수 차단을 위한 Embargo 설정은 필수
```

시계열 금융 데이터에서는 무작위 split이 위험하다.

필요한 검증 구조:

```text
time split
purge gap
embargo
walk-forward validation
```

---

## 8.2 Focus on Alpha

```text
시장 전체 Beta가 아니라 자산 고유 Alpha에 집중
```

시장 전체가 같이 오르거나 내리는 구간을 맞추는 것은 상대적으로 쉽다.

중요한 것은 다음이다.

```text
시장 효과를 제거한 후에도 남는 고유 움직임
```

---

## 8.3 The Great Trade-off

```text
정교한 수동 feature engineering
vs
정교한 모델 architecture
```

둘 중 하나만 정답은 아니다.

LightGBM 접근법은 수동 feature 설계와 검증 구조로 성과를 냈고, Deep Learning 접근법은 architecture와 ensemble로 성과를 냈다.

---

## 8.4 Power of Ensemble

```text
서로 다른 시간 window를 가진 모델의 결합은 강력함
```

특히 금융 시계열에서는 하나의 horizon/window만으로는 충분하지 않을 수 있다.

---

# 9. 현재 BTCUSDT Rule-based Regime 프로젝트에 주는 시사점

현재 프로젝트는 단일 BTCUSDT 1분봉 기반 regime-aware CatBoost 구조다.

G-Research는 14개 자산 cross-sectional 문제이므로 완전히 동일하지는 않지만, 다음 교훈은 직접 적용 가능하다.

---

## 9.1 Log Return / Relative Feature 중요성

발표의 log return 변환은 현재 논의한 OHLCV 정규화 방향과 일치한다.

현재 프로젝트에서도 raw OHLCV보다 다음 feature가 더 적합하다.

```text
log_return
close / moving_average - 1
ATR normalized range
volume rolling z-score
volatility adjusted return
```

---

## 9.2 Embargo / Purge Gap 중요성

현재 프로젝트에서도 label horizon과 feature window가 있으므로 train/validation split에 gap이 필요하다.

특히 다음 문제를 막아야 한다.

```text
feature leakage
target leakage
overlapping label leakage
```

현재 Optuna validation split에도 purge gap 또는 embargo 개념을 유지하는 것이 좋다.

---

## 9.3 Market Neutrality 개념의 변형 적용

G-Research는 multi-asset 문제라 자산별 market average를 제거한다.

현재 프로젝트는 BTCUSDT 단일 자산이므로 같은 방식은 어렵다.

하지만 대체 개념은 가능하다.

```text
BTC relative to crypto market index
BTC relative to ETH
BTC relative to total market cap proxy
BTC residual return after removing broad market factor
```

추후 multi-asset 데이터를 붙이면 G-Research식 residualized target도 검토할 수 있다.

---

## 9.4 Multi-window Ensemble 적용 가능

발표의 45/60/90/120분 window ensemble은 현재 프로젝트의 horizon 실험과 직접 연결된다.

현재 timeout은 60분이므로, 후속 실험으로 다음을 비교할 수 있다.

```text
30 min
60 min
90 min
120 min
```

또는 모델을 따로 학습해서 ensemble할 수 있다.

```text
horizon 30 model
horizon 60 model
horizon 90 model
horizon 120 model
```

---

## 9.5 Feature Engineering vs Architecture

현재 단계에서는 deep learning architecture보다 CatBoost + 정교한 feature engineering이 더 현실적이다.

이유:

```text
해석 가능성 높음
검증 쉬움
feature importance 확인 가능
regime별 성능 분석 가능
비용 반영 백테스트와 연결 쉬움
```

강화학습이나 Transformer는 이후 execution policy 또는 ensemble 후보로 보는 것이 안전하다.

---

# 10. 현재 프로젝트에 반영하면 좋은 후속 실험

## 10.1 Log Return / Relative OHLCV feature 추가

```text
log_return_1m
log_return_5m
hl_range_pct
oc_return
body_pct
upper_wick_pct
lower_wick_pct
```

---

## 10.2 Local Standardization

```text
rolling_zscore_return_1h
rolling_zscore_return_1d
volume_zscore_1h
volume_zscore_1d
atr_normalized_return
```

전체 데이터 기준 scaler가 아니라 과거 rolling window 기준으로 계산해야 한다.

---

## 10.3 Embargo Validation 강화

Optuna validation split에서 label horizon과 feature horizon을 고려한 purge gap을 명확히 둔다.

예:

```text
purge_gap = max(label_horizon, max_feature_lookback)
```

---

## 10.4 Multi-horizon Ensemble

현재 구조의 다음 확장 후보:

```text
horizon 30 model
horizon 60 model
horizon 90 model
horizon 120 model
```

각 horizon별 확률을 별도 feature로 사용하거나 평균/가중 평균 ensemble을 구성한다.

---

## 10.5 Market-neutral Feature 변형

단일 BTCUSDT에서도 아래를 붙일 수 있다.

```text
BTC return - ETH return
BTC return - crypto index return
BTC volume zscore - market volume zscore
BTC funding - market average funding
```

다만 이를 위해서는 ETH/주요 알트/시장 index 데이터가 필요하다.

---

# 11. 최종 요약

이 발표의 핵심 메시지는 다음이다.

```text
1. 금융 시계열에서는 validation이 가장 중요하다.
2. Embargo / purge gap 없이는 leakage 위험이 크다.
3. raw price보다 log return과 상대 feature가 중요하다.
4. 시장 전체 Beta를 제거하고 Alpha를 예측해야 한다.
5. LightGBM/CatBoost 같은 트리 모델도 정교한 feature engineering으로 강력한 성과를 낼 수 있다.
6. Deep Learning은 architecture와 ensemble로 성능을 낼 수 있지만 복잡도가 크다.
7. 서로 다른 time window 모델의 ensemble은 매우 강력하다.
```

현재 BTCUSDT rule-based regime 프로젝트에 바로 적용할 핵심은 다음이다.

```text
1. raw OHLCV보다 log return / relative feature 강화
2. Optuna validation에 purge/embargo 개념 유지
3. horizon 30/60/90/120 multi-window 실험
4. BTC 단일 자산에서 가능한 market-neutral proxy 검토
5. 우선은 CatBoost + feature engineering 기반을 완성한 뒤, deep learning/RL은 후속으로 검토
```
