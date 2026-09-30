Repo: D:\StudyQuant. 이번엔 구현 지시가 아니라 **논의**다. 내가 문헌과 오픈소스를 검색해서
후보를 모았다. 네가 공격하고, 무엇을 어떤 순서로 지을지 설계해서 돌려줘라. 설계에 합의되면
바로 실행한다. 새 fit 0회 원칙은 유지한다.

# 지금까지의 벽

- 손절: 0.1%~20% 전부 측정. 어느 폭도 `none`을 못 넘음. matched −4.11 bps, HAC가 0을 안 넘음
- 레버리지: 계좌 기준 비용이 `4L bps`라 레버리지가 올라갈수록 계좌 수익률 단조 악화
- 공유 book: 기존 pooled는 실행 불가능. 실행 가능 최선은 롱 전용 +0.4550 bps, HAC [−2.583, +3.493]
- Task B(자기 특성 10개): `NO_ORDERING`, 20칸 중 0개 통과
- Task D(반대 arm 신호 5개): `NO_ORDERING`. 다만 이진 분할이 +5.6844 대 −4.6214,
  차이 −10.3058 HAC [−16.4337, −4.1778]로 0을 안 넘음. fold 방향 일치 53.55%로 탈락

D의 탈락 이유가 핵심이다. 효과 크기는 큰데 fold 일관성이 없다. 그리고 **방향을 셀 수 있었던
fold가 667개 중 282개뿐**이다. 나머지는 후보가 너무 적어 계산이 안 됐다. B에서도 286/667이
non-finite였다.

즉 우리 일관성 통계는 검정력이 없을 가능성이 있다. 3일 간격 fold에 45분 거래를 얹으면 fold당
거래가 한 자릿수다.

# 갈래 1 — 검정력 수정 (Task E 후보)

## E-1. fold를 달력 블록으로 합친다

3일 fold를 그대로 쓰지 말고 비중첩 달력 블록(예: 월, 분기)으로 묶어 블록당 거래 수를 늘린 뒤
방향 일치와 HAC를 다시 계산한다.

**이건 사후 기준 완화가 아니라 검정력 문제의 수정이다.** 다만 블록 크기를 결과를 보고 고르면
그 순간 사후 선택이 된다. 블록 크기를 어떻게 사전에 고정할지가 네가 답할 문제다.

## E-2. Politis–White 자동 블록 길이

`stationary block bootstrap`의 최적 블록 길이를 flat-top lag-window 스펙트럼 추정으로 자동
선택하는 표준 방법이 있다. 원 논문과 Patton–Politis–White 정정이 있다.

- Politis & White (2004), Automatic Block-Length Selection for the Dependent Bootstrap
  https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf
- Patton, Politis & White (2009) 정정: `D_SB = 2 ĝ²(0)`
  https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf

**공격 지점**: 이 방법은 score 계열의 자기상관에서 블록 길이를 뽑는다. 평균이나 수익성을
보지는 않는다. 그래도 데이터 의존이다. 이게 우리 사전등록 규율에 맞는가, 아니면 룩어헤드인가.
네 판단과 근거를 써라. 맞다고 보면 "알고리즘을 사전등록하고 숫자는 산출물로 둔다"는 형태가
성립하는지도 판단해라.

내 현재 lag 규칙(`L_primary = min(60, G-1)`, `L_auto = min(G-1, floor(4*(G/100)^(2/9)))`)과
비교해라. 어느 쪽이 더 정직한가.

## E-3. CSCV / PBO / Deflated Sharpe

우리는 이미 많이 시험했다. 손절 폭 15개 이상, 특성 25개, arm 2개, fill 규약 4개.
다중검정 위험을 말로만 적어뒀지 수치화한 적이 없다.

- Bailey, Borwein, López de Prado, Zhu — Probability of Backtest Overfitting via
  combinatorially symmetric cross-validation (CSCV). "사내 최고가 out-of-sample에서 하위
  절반에 떨어지는 빈도"를 묻는다
- Bailey & López de Prado (2014) — Deflated Sharpe Ratio. 탐색 규모에 맞춰 하나의 숫자를 깎는다
  https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf
- 구현 참고: https://github.com/esvhd/pypbo , https://github.com/CH4RL3I/fluke

둘 다 **fit 0회로 기존 per-fold 수익 계열에서 계산 가능**하다.

**공격 지점**: 우리 표본이 CSCV 가정을 만족하는가. fold가 겹치고 거래가 fold를 넘는다.
DSR은 Sharpe 기반인데 우리는 거래당 bps를 본다. 변환이 정당한가. 정당하지 않으면 무엇을
써야 하는가.

## E-4. CPCV는 쓸 수 있는가

Combinatorial Purged CV는 하나의 경로 대신 OOS 추정치의 **분포**를 준다. 우리 검정력 문제에
직접 대응한다.

- https://en.wikipedia.org/wiki/Purged_cross-validation
- mlfinlab 구현: https://github.com/hudson-and-thames/mlfinlab/blob/master/mlfinlab/cross_validation/combinatorial.py

**문제**: CPCV는 조합마다 재학습을 요구한다. 우리는 fit 0회다. 기존 fold별 동결 체크포인트
위에서 조합 집계만 하는 것이 정당한 근사인가, 아니면 다른 이름을 붙여야 하는가. 네 판단.

# 갈래 2 — 새 특성군 (Task F 후보)

지금까지 본 것은 (a) 롱 후보 자신의 속성, (b) 반대 arm 신호다. 둘 다 실패했다.
아직 안 본 것이 둘 있다.

## F-1. Taker flow imbalance — 우리 데이터에 이미 있는데 안 쓰고 있다

`artifacts/btcusdt_2020_2026h1.parquet` 스키마를 확인했다.

```
open_time, open, high, low, close, volume, quote_volume,
number_of_trades, taker_buy_base_volume, taker_buy_quote_volume
```

3,417,120행. **`taker_buy_*`가 있다.** Binance kline은 모든 체결의 공격자 측을 기록하므로
주식시장식 tick-rule 분류 오차가 없다.

그런데 PatchTST excursion/range 모델의 `SEQUENCE_NAMES`는

```
abs_close_log_return_bps, high_low_log_range_bps, abs_body_log_bps,
upper_wick_log_bps, lower_wick_log_bps, log1p_quote_volume, log1p_trade_count
```

**부호 있는 flow가 없다.** 크기 예측 모델이라 부호를 뺀 것은 설계상 맞다. 하지만 백테스트 쪽
조건부 특성으로는 한 번도 안 썼다.

문헌에서 나온 표준 정의:

```
taker_imbalance = (2 * taker_buy_quote_volume - quote_volume) / quote_volume
```

그리고 문헌의 핵심 주장 하나가 우리 전략과 정확히 맞물린다.

> reversal concentrates after moves driven by aggressive taker flow and grows with flow intensity

- Short-horizon mean reversion in cryptocurrency markets: a matched study
  https://arxiv.org/html/2608.21888v1
- Explainable Patterns in Cryptocurrency Microstructure
  https://arxiv.org/html/2602.00776v1
- Bitcoin wild moves: order flow toxicity (VPIN)
  https://www.sciencedirect.com/science/article/pii/S0275531925004192

우리 전략은 **돌파를 fade**한다(하락 돌파 → 롱). 위 주장이 맞다면, **공격적 taker flow가 만든
돌파일수록 fade가 잘 들어야 한다**. 이건 검증 가능한 인과 가설이고, 트리거 시점에 관측 가능하다.

**공격 지점**: 이게 진짜 새 정보인가, 아니면 `|d(tau)|`나 거래량의 재표현인가. B에서
`abs_d_tau_bps`가 ρ +0.0588(p 0.000094)로 가장 강했고 그것도 관문을 못 넘었다. taker imbalance가
`|d(tau)|`와 얼마나 상관되는지 먼저 봐야 하지 않는가. 네 설계에 그 진단을 넣어라.

또 하나. 문헌의 OFI는 호가창 기반이고 1초 단위이며 "충격이 1초 안에 거의 소멸"한다고 한다
(https://arxiv.org/html/2508.06788). 우리는 1분봉이고 홀드가 45분이다. 시간 규모가 두 자릿수
다르다. 이 괴리가 가설을 무력화하는가.

## F-2. 상위 시간프레임 상태

우리 모델은 1분봉 60개만 본다. 45분 홀드인데 그보다 긴 문맥이 없다.

- Quantpedia, 비트코인 멀티 타임프레임 추세 전략
  https://quantpedia.com/how-to-design-a-simple-multi-timeframe-trend-strategy-on-bitcoin/
- HMM 기반 crypto regime 분류 (Strong Trend / Weak Trend / Range / Choppy / Vol Spike / Squeeze)
  https://github.com/akash-kumar5/CryptoMarket_Regime_Classifier
- HMM 일중 모멘텀 + side information https://arxiv.org/pdf/2006.08307

**공격 지점**: 이 레포에는 이미 regime router가 있었고 폐기됐다. 이유는 "30분 기울기 크기를
재는 것이지 시장 방향이 아니었고, 64% 폭락과 강세장에서 down share가 동일했으며, regime이
15분 지속인데 홀드가 45분이었다"는 것이었다. 새 상위 시간프레임 특성이 같은 함정을 어떻게
피하는가. 못 피하면 F-2는 빼라.

# 네가 답할 것

1. E-1~E-4 중 무엇을 짓고 무엇을 버리는가. 순서는. 각각 왜
2. 블록 크기 / 블록 길이를 **결과 보기 전에** 고정하는 구체적 방법. Politis–White가
   그 규율에 맞는가
3. CSCV/DSR이 우리 표본에서 정당한가. 정당하지 않으면 대안
4. CPCV를 fit 0으로 흉내 내는 것이 정당한가. 정당하면 뭐라 불러야 하는가
5. F-1이 `|d(tau)|`·거래량의 재표현이 아님을 어떻게 보일 것인가. 1분/45분 시간 규모 괴리는
6. F-2를 할 것인가 말 것인가. 폐기된 regime router의 함정을 어떻게 피하는가
7. E와 F의 순서. 검정력을 먼저 고치고 특성을 보는 게 맞는가, 반대인가

# 제약

- 새 fit 0회 유지. `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, `live_orders: 0`
- 외부 데이터 추가 금지. 위 URL은 방법론 참고이지 데이터 소스가 아니다. 기존 로컬 parquet과
  funding ZIP만 쓴다
- 예측은 입력이다. 재학습·재튜닝·fold 선택 금지
- 손절 없음, K=45, 롱 전용 book을 기본 무대로 한다. 손절 축은 닫혔다
- 사전등록·해시·SHA-256 manifest·`--verify` 규율 유지
- 지금은 **설계만** 내라. 구현은 합의 후에 한다. 다만 설계 근거로 필요한 0-fit 진단
  (예: taker imbalance와 `|d(tau)|`의 상관)은 계산해도 된다
