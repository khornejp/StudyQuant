# CodexProject 소스 검토 요약

> 대상: `CodexProject(1).zip`  
> 참고 문서: `PIPELINE_INTEGRATION.md`  
> 범위: BTCUSDT rule-based regime-aware CatBoost 파이프라인, PowerShell 통합 기능, Kelly sizing, multi-horizon 파일럿, diagnostics  
> 목적: 소스 검토 결과와 재학습/백테스트 전 수정 필요 항목 정리

---

# 1. 전체 결론

이번 소스는 v12 기준 기능 위에 `run_full_pipeline.ps1` 통합 기능이 추가된 버전으로 보인다.

큰 방향은 좋다.

정상 반영된 주요 항목:

```text
1. v12 feature registry 상태 유지
2. scale-dependent 9개 feature 제외 유지
3. train/backtest metrics parity 유지
4. Optuna best_iteration 구조 유지
5. PowerShell pipeline에 diagnostics / multi-horizon / Kelly sizing 통합
6. 기본 단위 테스트 통과
```

다만 최종 백테스트 결과를 신뢰하기 전에 반드시 고쳐야 할 핵심 문제가 있다.

가장 중요한 문제:

```text
1. Kelly edge 계산에 비용이 반영되지 않음
2. Kelly sizing 적용 시 Sharpe / profit factor가 position size를 반영하지 않음
3. multi-horizon single-model의 SELL 해석이 label 의미와 맞지 않을 수 있음
4. run_full_pipeline.sh는 PowerShell 버전과 아직 동기화되지 않음
```

특히 Kelly 관련 1~2번은 백테스트 결과 해석에 직접 영향을 주므로, 재학습/최종 백테스트 전에 수정하는 것이 좋다.

---

# 2. 정상 반영된 부분

## 2.1 v12 feature registry 상태 유지

직접 확인 결과:

```text
dataset.FEATURE_NAMES = 180
feature_formula_registry()["active_feature_names"] = 180
tuple equality = True
```

즉 v12에서 수정했던 registry metadata 불일치 문제는 이번 소스에서도 정상이다.

모델 입력에서 제외된 scale-dependent 9개 feature:

```text
quote_volume_per_trade

macd_line
macd_signal
macd_hist

rolling_vwap_20
rolling_vwap_60

range_high_20
range_low_20
range_mid_20
```

이 9개는 모델 입력에 들어가지 않는다.

상대 대체 feature들은 유지된다.

```text
price_vs_rolling_vwap_20
price_vs_rolling_vwap_60
vwap_deviation_zscore

range_position_20
distance_to_range_high
distance_to_range_low
distance_to_high_20
distance_to_low_20

ema_12_26_spread
volume_per_trade
```

---

## 2.2 run_full_pipeline.ps1 신규 phase 반영

PowerShell 기준으로는 `PIPELINE_INTEGRATION.md`의 내용과 실제 코드가 대체로 일치한다.

추가된 흐름:

```text
Phase 2.3:
  IC/leakage diagnostic + range half-life

Phase 3.5:
  train-multi-horizon

Phase 4:
  regime model backtest + Kelly sizing

Phase 4.5:
  multi-horizon backtest

최종 출력:
  gross/net sharpe
  cost impact
  Kelly diagnostics
```

의도:

```text
1. 학습 전 feature IC와 leakage heuristic 확인
2. range regime 평균회귀 half-life 확인
3. horizon 30/60/90 파일럿 모델 학습
4. Kelly sizing 적용 백테스트
5. regime model과 multi-horizon 파일럿을 net sharpe/MDD 기준으로 비교
```

---

## 2.3 train/backtest metrics parity 유지

현재 구조에서는 다음 경로들이 metrics feature를 받을 수 있다.

```text
train
backtest
train-multi-horizon
```

기본 PowerShell 파이프라인에서는 각 단계에 다음이 전달된다.

```powershell
--metrics-dir $MetricsDir
```

따라서 이전 문제였던 아래 skew는 유지 보수된 상태로 보인다.

```text
train:
  F16 metrics 실값

backtest:
  F16 metrics 0.0
```

현재는 train/backtest 모두 metrics를 사용할 수 있는 구조다.

---

## 2.4 테스트 상태

확인한 테스트:

```text
python -m py_compile btcusdt_quant/*.py ic_diagnostic.py verify_range_halflife.py
→ OK
```

```text
python -m unittest tests.test_review_items -v
→ Ran 45 tests OK
```

```text
python -m unittest tests.test_stacking_ensemble -v
→ Ran 5 tests OK
```

기본 문법/단위 테스트 수준에서는 깨진 부분이 보이지 않는다.

---

# 3. 핵심 문제 1: Kelly edge 계산에 비용이 반영되지 않음

## 3.1 현재 문제

현재 Kelly sizing은 대략 다음 개념으로 계산된다.

```python
edge = p * tp_pct - (1 - p) * sl_pct
kelly = edge / variance
```

즉 gross TP/SL 기준 edge만 사용한다.

하지만 실제 백테스트 PnL은 trade close 시점에 비용을 차감한다.

```text
net_pnl_pct = gross_pnl_pct - round_trip_cost
```

현재 기본 비용:

```text
fee per side      = 0.0002
slippage per side = 0.0002
round trip cost   = 0.0008
```

문제:

```text
Kelly는 비용 전 gross edge를 보고 진입/사이징
실제 백테스트는 비용 후 net PnL로 평가
```

즉 Kelly가 net으로는 음수 기대값인 거래도 gross 기준 양수라고 판단해 진입할 수 있다.

---

## 3.2 예시

기본 TP/SL:

```text
TP = 0.0030
SL = 0.0015
round_trip_cost = 0.0008
```

gross 기준 edge가 양수이려면:

```text
p * 0.003 - (1 - p) * 0.0015 > 0
p > 0.333
```

즉 승률 33.3% 이상이면 gross edge는 양수다.

하지만 net 기준으로는:

```text
win  = 0.0030 - 0.0008 = 0.0022
loss = 0.0015 + 0.0008 = 0.0023
```

net edge가 양수이려면:

```text
p * 0.0022 - (1 - p) * 0.0023 > 0
p > 약 0.511
```

즉 실제 net 기준에서는 약 51.1% 이상이어야 양수 기대값이다.

현재 Kelly는 이 차이를 반영하지 않는다.

---

## 3.3 영향

이 문제 때문에 다음 지표가 왜곡될 수 있다.

```text
1. entries_skipped_no_edge가 실제보다 적게 나올 수 있음
2. 비용 후 음수 기대값 거래에도 포지션이 생길 수 있음
3. Half-Kelly sizing이 과대평가될 수 있음
4. regime model vs multi-horizon model 비교가 왜곡될 수 있음
```

즉 지금 상태에서 Kelly sizing 결과를 최종 판단에 쓰면 위험하다.

---

## 3.4 권장 수정

`kelly_fraction_for_entry()` 또는 `kelly_leverage_for_signal()`에 비용을 전달해야 한다.

권장 입력:

```python
kelly_fraction_for_entry(
    config,
    entry_probability,
    entry_price,
    tp_price,
    sl_price,
    bar_returns_window,
    cap,
    fee_rate_per_side,
    slippage_rate_per_side,
)
```

edge 계산은 net 기준으로 바꾼다.

```python
round_trip_cost = 2.0 * (fee_rate_per_side + slippage_rate_per_side)

gross_tp_pct = abs(tp_price - entry_price) / entry_price
gross_sl_pct = abs(entry_price - sl_price) / entry_price

net_win = gross_tp_pct - round_trip_cost
net_loss = gross_sl_pct + round_trip_cost

edge = p * net_win - (1 - p) * net_loss
```

예외 처리:

```python
if net_win <= 0:
    return 0.0
```

즉 TP가 비용보다 작으면 진입하지 않는 것이 맞다.

---

# 4. 핵심 문제 2: Kelly sizing 시 Sharpe / profit factor가 position size를 반영하지 않음

## 4.1 현재 문제

현재 `_close_trade()`는 equity 계산에는 position size를 반영한다.

개념:

```text
net_trade_pnl = net_pnl_pct * trade_notional
trade_notional = position_size * equity
```

하지만 metrics 계산용 `returns`에는 다음이 들어간다.

```python
returns.append(pnl_pct)
```

여기서 `pnl_pct`는 position size가 반영되지 않은 가격 기준 net PnL%다.

즉 Kelly sizing으로 어떤 거래는 1%, 어떤 거래는 10% equity fraction으로 들어가도 Sharpe 계산에서는 같은 무게로 취급된다.

---

## 4.2 왜 문제인가

문제되는 지표:

```text
1. sharpe
2. gross_sharpe
3. profit_factor
```

현재 구조에서는:

```text
total_return
max_drawdown
```

은 size를 반영하지만,

```text
sharpe
profit_factor
```

는 size를 제대로 반영하지 않을 수 있다.

이건 특히 `regime model vs multi-horizon model`을 net sharpe/MDD 기준으로 비교하려는 설계에서 중요하다.

---

## 4.3 권장 수정

거래 종료 시 실제 equity return을 저장해야 한다.

개념:

```python
realized_size = active_trade.position_size_used or position_size

trade_equity_return = net_pnl_pct * realized_size
gross_trade_equity_return = gross_pnl_pct * realized_size
```

`BacktestTrade`에 필드 추가:

```python
trade_return_pct: float = 0.0
gross_trade_return_pct: float = 0.0
```

metrics 계산은 다음 기준으로 바꾼다.

```python
returns.append(trade.trade_return_pct)
gross_returns.append(trade.gross_trade_return_pct)
```

profit factor도 size-weighted return 기준으로 계산한다.

```python
gross_profit = sum(
    t.trade_return_pct for t in trades
    if t.trade_return_pct > 0
)

gross_loss = abs(sum(
    t.trade_return_pct for t in trades
    if t.trade_return_pct < 0
))
```

고정 position size에서는 모든 거래가 같은 비율이므로 기존 Sharpe와 차이가 거의 없다.

하지만 Kelly sizing처럼 거래마다 size가 달라지는 경우에는 반드시 size-weighted return으로 계산해야 한다.

---

# 5. 설계 리스크: multi-horizon single-model SELL 해석

## 5.1 현재 구조

`train-multi-horizon`은 horizon별로 triple-barrier label을 학습한다.

기본 label 의미:

```text
long 방향 TP가 먼저 맞았거나
미래 수익률이 label_threshold보다 크면 1
그 외는 0
```

그런데 single-model backtest path는 다음처럼 해석한다.

```text
prob > long_threshold
  → BUY

prob < short_threshold
  → SELL
```

즉 낮은 `P(long_success)`를 short signal로 해석한다.

문제는 `label = 0`이 반드시 short 성공을 의미하지 않는다는 점이다.

---

## 5.2 label = 0에 섞이는 것

`label = 0`에는 다음이 섞일 수 있다.

```text
1. long SL first
2. timeout_no_tp
3. 약한 상승
4. 횡보
5. 실제 short TP 성공
```

따라서 낮은 `P(long_success)`를 곧바로 `P(short_success)`로 해석하는 것은 위험하다.

특히 Kelly sizing에서는 single-model SELL의 확률을 `1 - P(long)`으로 반전할 수 있다.

이 경우 short edge가 과대평가될 수 있다.

---

## 5.3 권장 선택지

## 선택지 A: multi-horizon 파일럿은 long-only로 제한

가장 안전한 파일럿 방식이다.

```text
prob > threshold
  → BUY

그 외
  → HOLD
```

SELL은 사용하지 않는다.

장점:

```text
label 의미와 action 의미가 일치
파일럿 복잡도 낮음
결과 해석이 쉬움
```

---

## 선택지 B: horizon별 long/short 모델 분리

regime-aware 구조처럼 horizon별로 long/short model을 따로 만든다.

예:

```text
horizon 30 long_success model
horizon 30 short_success model

horizon 60 long_success model
horizon 60 short_success model

horizon 90 long_success model
horizon 90 short_success model
```

장점:

```text
BUY/SELL 각각의 확률 의미가 명확함
Kelly edge 계산에도 적합
```

단점:

```text
모델 수 증가
파일럿 복잡도 증가
```

---

## 선택지 C: direction label 사용

`P(up)`과 `P(down)`을 명시적으로 학습하는 direction label로 바꾸는 방법이다.

하지만 현재 triple-barrier profitability label과 목적이 다르다.

따라서 현재 파일럿 단계에서는 추천 우선순위가 낮다.

---

## 추천

현재 파일럿 단계에서는 **선택지 A: long-only**가 가장 안전하다.

multi-horizon 효과가 확인되면 그 다음에 long/short 분리로 확장하는 것이 좋다.

---

# 6. run_full_pipeline.sh 미동기화

## 6.1 현재 상태

`run_full_pipeline.ps1`에는 신규 기능이 들어가 있다.

하지만 `run_full_pipeline.sh`에는 아직 다음이 없다.

```text
Phase 2.3 diagnostics
Phase 3.5 train-multi-horizon
Phase 4 Kelly flags
Phase 4.5 multi-horizon backtest
gross/net sharpe 출력 확장
```

즉 Windows PowerShell 실행과 Linux/macOS bash 실행의 동작이 다르다.

문서에도 bash 버전은 이번 변경 미반영이라고 정리되어 있다.

---

## 6.2 영향

사용자가 `.sh`를 실행하면 기대한 신규 실험이 돌지 않는다.

예:

```text
Kelly sizing 없음
multi-horizon pilot 없음
diagnostics 없음
gross/net sharpe 확장 없음
```

---

## 6.3 권장

둘 중 하나를 선택해야 한다.

```text
1. run_full_pipeline.sh도 ps1과 동일하게 업데이트
```

또는:

```text
2. run_full_pipeline.sh 상단에 신규 기능 미포함 경고 추가
```

예:

```bash
echo "WARNING: run_full_pipeline.sh is not synchronized with run_full_pipeline.ps1."
echo "Kelly sizing, diagnostics, and multi-horizon pilot are available only in the PowerShell pipeline."
```

가능하면 `.sh`도 동기화하는 것이 좋다.

---

# 7. IC diagnostic 평가

`ic_diagnostic.py`는 다음을 수행한다.

```text
feature × horizon Spearman IC
fold별 IC mean/std
fwd>past heuristic
lag1-collapse heuristic
```

이건 정보성 도구로는 괜찮다.

다만 해석은 조심해야 한다.

```text
IC 높음
  → 무조건 좋은 feature라는 뜻은 아님

leak flag
  → 무조건 제거해야 한다는 뜻은 아님

fold std 큼
  → feature가 불안정할 수도 있지만 regime-dependent signal일 수도 있음
```

따라서 현재처럼 Phase 2.3이 파이프라인을 중단하지 않는 정보성 단계인 것은 적절하다.

leak flag가 뜨면 truncation-invariance 테스트로 확정하는 방식이 맞다.

---

# 8. OU half-life 진단 평가

`verify_range_halflife.py`는 range regime 구간에서 OU half-life를 추정한다.

이 방향은 좋다.

다만 현재는 raw close 기준으로 보는 성격이 강하다.

BTC price는 drift와 heteroskedasticity가 크므로 raw close에 OU를 맞추면 결과가 불안정할 수 있다.

후속으로는 아래 상대/정규화 series에도 적용하는 것이 좋다.

```text
1. close / rolling_vwap - 1
2. range_position_20
3. zscore of log price
4. spread from local mean
```

즉 raw close half-life는 참고용으로 보고, 실제 range gate 조정은 상대/정규화 series 기준도 함께 검증하는 것이 좋다.

---

# 9. 현재 우선순위

지금 바로 고쳐야 할 순서는 다음이다.

```text
1순위:
  Kelly edge 계산에 round-trip cost 반영

2순위:
  Kelly sizing 시 Sharpe / profit_factor를
  position-size-weighted return 기준으로 계산

3순위:
  multi-horizon single-model SELL 해석 정리
  - 우선 long-only pilot 권장
  - 또는 long/short horizon 모델 분리

4순위:
  run_full_pipeline.sh를 ps1과 동기화하거나 경고 추가

5순위:
  OU half-life를 상대/정규화 series에도 적용하는 옵션 추가
```

---

# 10. 다음 수정 요청 예시

다음 작업에서 바로 이어가려면 아래처럼 요청하면 된다.

```text
첨부 ZIP 기준으로 다음을 수정해줘.

1. Kelly sizing edge 계산에 fee/slippage round-trip cost를 반영
   - net_win = tp_pct - round_trip_cost
   - net_loss = sl_pct + round_trip_cost
   - edge = p * net_win - (1-p) * net_loss
   - net_win <= 0이면 no edge 처리

2. Kelly sizing 적용 시 Sharpe / profit factor가 position size를 반영하도록 수정
   - BacktestTrade에 trade_return_pct, gross_trade_return_pct 추가
   - returns/gross_returns/profit_factor를 size-weighted return 기준으로 계산

3. multi-horizon single-model backtest는 우선 long-only로 제한
   - 낮은 P(long)를 SELL로 해석하지 않도록 옵션 추가 또는 기본 변경

4. run_full_pipeline.sh를 ps1과 동기화하거나, 최소한 신규 기능 미포함 경고 추가

5. 관련 단위 테스트 추가
```

---

# 11. 최종 판단

이번 소스는 전체적으로 많이 좋아졌다.

정상 유지/반영된 항목:

```text
v12 feature registry 상태 정상
scale-dependent 9개 feature 제외 유지
metrics parity 유지
Optuna best_iteration 구조 유지
PowerShell pipeline에 diagnostics / multi-horizon / Kelly sizing 통합
기본 테스트 통과
```

하지만 Kelly 관련 문제는 최종 결과 해석에 치명적일 수 있다.

현재 상태에서 다음을 최종 판단에 쓰면 위험하다.

```text
1. net Sharpe 기준 regime model vs multi-horizon model 비교
2. Kelly sizing 적용 후 profit factor 비교
3. entries_skipped_no_edge 해석
```

이유:

```text
1. Kelly edge가 비용을 반영하지 않음
2. Kelly Sharpe/profit factor가 position size를 반영하지 않음
```

따라서 지금은 재학습/최종 백테스트 전에 다음을 먼저 고치는 것이 맞다.

```text
Kelly net edge
Kelly size-weighted metrics
multi-horizon SELL 해석
```
