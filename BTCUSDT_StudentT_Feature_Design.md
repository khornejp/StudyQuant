# BTCUSDT Student-t Feature 설계안

## 1. 결론

현재 BTCUSDT Rule-based Regime + CatBoost + Multi-Horizon 구조에는 다음 방식이 가장 적합하다.

```text
1분 로그수익률
→ EWMA 변동성으로 표준화
→ 과거 1일/7일 구간에 대칭 Student-t 적합
→ 매 60분 파라미터 갱신
→ df, scale, surprise, signed_surprise 생성
→ CatBoost feature로 추가
→ 2025 OOS ablation 검증
```

첫 구현은 **대칭 Student-t**로 시작하고, 효과가 확인된 뒤 **Hansen skewed Student-t**를 challenger로 추가하는 것이 좋다.

원시 수익률에 바로 Student-t를 적합하는 것은 권장하지 않는다. 금융 수익률은 변동성이 시간에 따라 달라지므로, 먼저 변동성으로 표준화한 잔차를 대상으로 꼬리 두께와 이상도를 계산해야 한다.

---

# 2. 1단계: 로그수익률 계산

기본 수익률은 1분 로그수익률을 사용한다.

\[
r_t = \log\left(rac{C_t}{C_{t-1}}ight)
\]

초기 후보 시간축:

```text
1분 수익률
60분 수익률
```

처음부터 1분, 5분, 15분, 30분, 60분을 모두 넣으면 중복 feature가 많아질 수 있으므로, 우선 1분과 60분 두 축만 권장한다.

---

# 3. 2단계: 변동성 표준화

원시 수익률 대신 다음 표준화 잔차를 사용한다.

\[
z_t = rac{r_t}{\sigma_{t-1}}
\]

여기서 \(\sigma_{t-1}\)은 현재 시점 이전 데이터만 사용해 계산한 변동성이다.

권장 순서:

```text
1순위: EWMA volatility
2순위: rolling robust volatility
3순위: GARCH volatility
```

초기 버전에는 EWMA가 가장 적합하다.

\[
\sigma_t^2 = \lambda \sigma_{t-1}^2 + (1-\lambda)r_t^2
\]

구현 시 현재 수익률이 자기 자신의 분모에 들어가지 않도록 shift를 사용해야 한다.

```python
vol = returns.ewm(span=1440, adjust=False).std()
standardized_return = returns / vol.shift(1)
```

---

# 4. 어떤 Student-t 계열을 사용할 것인가

## 4.1 Symmetric Student-t

첫 구현으로 가장 권장한다.

파라미터:

```text
df 또는 ν:
  꼬리 두께

loc:
  중심 위치

scale:
  분포 크기
```

표준화 잔차를 사용하므로 다음처럼 제한하는 것이 좋다.

```text
loc = 0 고정
df와 scale만 추정
```

이유:

```text
방향성:
  CatBoost 담당

Student-t:
  꼬리 위험과 이상도 담당
```

### df 해석

```text
df가 낮음:
  꼬리가 두꺼움
  극단 변동 위험 증가

df가 높음:
  정규분포에 가까움
  상대적으로 안정적
```

CatBoost 입력에는 `df` 대신 다음 변환도 사용할 수 있다.

```python
tail_thickness = 1.0 / df
```

`df`와 `1/df`를 동시에 넣기보다는 우선 하나만 넣는 것이 좋다.

---

## 4.2 Hansen Skewed Student-t

대칭 Student-t에 왜도 파라미터를 추가한 형태다.

```text
df:
  전체적인 꼬리 두께

skew parameter:
  상승 또는 하락 방향 비대칭
```

BTC에서는 급락과 숏 스퀴즈의 빈도 및 크기가 다를 수 있으므로, 대칭 Student-t의 효과가 확인된 뒤 challenger로 비교할 가치가 있다.

장점:

```text
상승·하락 tail risk 분리 가능
레짐별 비대칭 변화 표현 가능
BUY/SELL 위험을 다르게 평가 가능
```

단점:

```text
파라미터 증가
짧은 window에서 불안정
수렴 실패 가능
계산량 증가
```

권장 순서:

```text
대칭 Student-t
→ 유효성 확인
→ skewed-t 추가
→ OOS 비교
```

---

## 4.3 Non-central t

현재 목적에는 권장하지 않는다.

이유:

```text
금융 왜도 표현에 가장 자연스러운 선택이 아님
Hansen skewed-t가 해석하기 쉬움
방향성은 기존 CatBoost가 담당
```

---

## 4.4 Multivariate Student-t

현재 BTCUSDT 단일 종목 구조에는 불필요하다.

다음과 같은 다변량 공동 꼬리를 모델링할 때 의미가 있다.

```text
BTC + ETH 공동 급락
BTC return + funding + basis 공동 이상
```

현재 프로젝트에는 복잡도 대비 이득이 적다.

---

# 5. 권장 Student-t Feature

## 5.1 분포 상태 Feature

### `student_t_df`

현재 rolling window의 자유도.

```text
낮음:
  fat-tail 상태

높음:
  정규분포에 가까운 상태
```

### `student_t_tail_thickness`

```python
student_t_tail_thickness = 1.0 / student_t_df
```

### `student_t_scale`

표준화 이후에도 남아 있는 잔차 크기.

```text
scale 증가:
  EWMA가 변동성을 충분히 따라가지 못함
  또는 잔차 분포가 더 넓어진 상태
```

---

## 5.2 현재 움직임 이상도 Feature

과거 window로 Student-t를 적합하고 현재 \(z_t\)를 평가한다.

### `student_t_neg_logpdf`

\[
-\log f_t(z_t)
\]

해석:

```text
낮음:
  평범한 움직임

높음:
  현재 분포에서 드문 움직임
```

예시:

```python
student_t_surprise = -t.logpdf(
    current_z,
    df=fitted_df,
    loc=0.0,
    scale=fitted_scale,
)
```

### `student_t_left_tail_prob`

현재 움직임 이하의 하락이 발생할 확률.

```python
left_tail_prob = t.cdf(
    current_z,
    df=fitted_df,
    loc=0.0,
    scale=fitted_scale,
)
```

급락일수록 0에 가까워진다.

### `student_t_right_tail_prob`

```python
right_tail_prob = t.sf(
    current_z,
    df=fitted_df,
    loc=0.0,
    scale=fitted_scale,
)
```

급등일수록 0에 가까워진다.

### `student_t_signed_surprise`

현재 움직임의 방향을 보존한다.

```python
signed_surprise = np.sign(current_z) * student_t_surprise
```

해석:

```text
큰 음수:
  이례적인 급락

큰 양수:
  이례적인 급등
```

---

## 5.3 정규분포 대비 Feature

### `student_t_vs_normal_llr`

\[
\log f_t(z_t) - \log f_N(z_t)
\]

해석:

```text
양수:
  Student-t가 현재 움직임을 정규분포보다 잘 설명

큰 양수:
  fat-tail 상태일 가능성
```

Rolling window 전체에 대해서도 Student-t와 Normal의 평균 OOS log-likelihood 차이를 계산할 수 있다.

이 값이 계속 0에 가깝다면 Student-t feature의 추가 가치가 적다는 의미다.

---

## 5.4 Skewed-t 추가 Feature

Skewed-t를 사용할 경우 다음을 추가할 수 있다.

```text
skew_t_lambda
skew_t_left_tail_prob
skew_t_right_tail_prob
skew_t_downside_surprise
skew_t_upside_surprise
```

특히 다음 두 feature가 유용할 가능성이 높다.

```text
downside_tail_risk
upside_tail_risk
```

---

# 6. 권장 Rolling Window

1분봉 전체에서 매분 MLE를 다시 수행하면 계산량이 크다.

초기 설정:

```text
Short window:
  1,440 bars
  약 1일

Long window:
  10,080 bars
  약 1주
```

파라미터는 매 바 다시 적합하지 않고 다음과 같이 갱신한다.

```text
매 60분마다 재적합
그 사이에는 이전 파라미터 forward-fill
```

예시:

```text
00:00 적합
01:00 적합
02:00 적합
...
```

초기 feature 후보는 8개 정도가 적당하다.

```text
t_df_1d
t_scale_1d
t_surprise_1d
t_signed_surprise_1d

t_df_7d
t_scale_7d
t_surprise_7d
t_signed_surprise_7d
```

---

# 7. Causal 계산 순서

시점 \(t\)에서 다음 순서를 지켜야 한다.

```text
1. 과거 t-W ~ t-1의 수익률 수집
2. 과거 데이터로 volatility 계산
3. 과거 standardized residual 생성
4. Student-t 파라미터 적합
5. 현재 수익률 r_t 계산
6. sigma_(t-1)로 현재 z_t 계산
7. 현재 z_t의 tail probability와 surprise 계산
8. feature row t에 저장
9. 이후 t+1부터 미래 label 계산
```

금지:

```text
2020~2025 전체 데이터로 Student-t 파라미터를 한 번 적합
→ 해당 파라미터로 과거 feature 생성
```

이렇게 하면 미래 정보가 과거 feature에 들어가는 leakage가 발생한다.

---

# 8. Regime별 별도 적합 여부

첫 버전에서는 권장하지 않는다.

초기 구조:

```text
전체 시장 rolling Student-t
+
현재 rule-based regime feature
```

레짐별로 따로 적합하면 다음 문제가 생길 수 있다.

```text
표본 감소
레짐 전환 시 파라미터 급변
일부 레짐 수렴 불안정
과거 동일 레짐만 선택하는 로직 복잡화
```

첫 실험이 성공한 뒤 다음 challenger로 비교할 수 있다.

```text
전역 rolling Student-t
vs
regime-conditioned rolling Student-t
```

---

# 9. Kelly와의 연결

첫 단계에서는 Kelly에 직접 연결하지 않는 것이 좋다.

초기 단계:

```text
Student-t feature
→ CatBoost 입력
→ 모델 성능 확인
```

곧바로 Kelly에 연결하면 다음 변화가 동시에 발생한다.

```text
CatBoost 신호 변화
Student-t risk filter 변화
Kelly sizing 변화
```

그러면 성능 변화의 원인을 구분하기 어렵다.

권장 단계:

```text
1단계:
  CatBoost feature로만 추가

2단계:
  Feature ablation 수행

3단계:
  downside tail risk가 높을 때
  Kelly fraction 축소 실험
```

예:

```python
if downside_tail_probability < 0.01:
    kelly_fraction *= 0.5
```

단, `0.01`과 `0.5`는 고정값으로 확정하지 말고 OOS sensitivity 테스트로 결정해야 한다.

---

# 10. 검증 기준

## 10.1 모델 성능

```text
Logloss
Brier score
PR-AUC
Calibration error
```

## 10.2 거래 성능

```text
Net return
Net Sharpe
Profit factor
Max drawdown
Trade count
Cost impact
```

## 10.3 분포 Feature 자체

```text
fit 실패율
df 하한/상한 도달 비율
scale 이상치 비율
parameter jump 빈도
Student-t vs Normal OOS log-likelihood
```

다음과 같은 경우 제거를 고려한다.

```text
Logloss 개선 없음
Calibration 악화
df가 대부분 상한에 고정
Student-t와 Normal likelihood 차이가 거의 없음
CatBoost 중요도 거의 0
```

---

# 11. 최종 권장 구현안

```text
1분 로그수익률
→ EWMA volatility 표준화
→ 1일/7일 대칭 Student-t 적합
→ 매 60분 파라미터 갱신
→ df, scale, surprise, signed_surprise 생성
→ CatBoost feature로만 추가
→ 2025 OOS ablation
```

그다음 성능이 확인되면:

```text
대칭 Student-t
→ Hansen skewed Student-t challenger
→ downside/upside tail feature 추가
```

처음부터 복잡한 skewed-t나 multivariate-t를 적용하기보다는, 대칭 Student-t 기반 8개 안팎의 feature로 효과부터 확인하는 것이 가장 안전하다.
