# CodexProject(2) 소스 분석 요약

> 대상: `CodexProject(2).zip`  
> 참고 문서: `CODE_REVIEW_FIXES.md`, `PIPELINE_INTEGRATION(1).md`  
> 범위: BTCUSDT rule-based regime-aware CatBoost 파이프라인, Kelly sizing, multi-horizon 파일럿, PowerShell/Bash 통합  
> 목적: 현재 소스 검토 결과와 재학습/백테스트 전 남은 이슈 정리

---

# 1. 전체 결론

`CodexProject(2).zip`은 이전 소스 리뷰에서 지적했던 핵심 문제들을 대부분 반영한 상태다.

정상 반영된 주요 항목:

```text
1. Kelly edge 계산에 round-trip cost 반영
2. Kelly sizing 적용 시 Sharpe/profit factor가 position size를 반영
3. 단일모델 SELL을 Kelly가 거부하도록 수정
4. multi-horizon 파일럿을 regime-aware 구조에 맞춤
5. train-multi-horizon label alignment look-ahead 수정
6. run_full_pipeline.sh도 ps1과 동기화
7. v12 feature registry 180개 상태 유지
8. metrics train/backtest parity 유지
```

따라서 이전 버전보다 훨씬 안정적이다.

다만 아직 중요한 구조적 한계가 하나 남아 있다.

```text
multi-horizon 파일럿의 threshold selection horizon과
실제 backtest execution horizon이 어긋날 수 있음
```

즉 현재 상태에서도 실행은 가능하지만, Phase 4와 Phase 4.5를 완전히 동일 조건의 challenger 비교라고 보기에는 아직 주의가 필요하다.

---

# 2. 정상 반영된 핵심 수정

## 2.1 Kelly edge에 비용 반영

이전 문제:

```text
Kelly가 gross TP/SL 기준으로 edge 계산
실제 백테스트는 fee/slippage 차감 후 net PnL 평가
```

현재 수정:

```python
net_win = tp_pct - round_trip_cost
net_loss = sl_pct + round_trip_cost

if net_win <= 0.0:
    return -net_loss

edge = probability * net_win - (1.0 - probability) * net_loss
```

이제 Kelly는 다음 비용을 반영한다.

```text
round_trip_cost = 2 * (fee_rate_per_side + slippage_rate_per_side)
```

의미:

```text
비용 전에는 양수 edge처럼 보이지만
비용 후에는 음수 기대값인 거래를 걸러낼 수 있음
```

이 수정은 매우 중요하다.

기존에는 예를 들어 TP=0.003, SL=0.0015, round_trip_cost=0.0008인 경우:

```text
gross 손익분기 확률:
  약 33.3%

net 손익분기 확률:
  약 51.1%
```

이 차이를 Kelly가 반영하지 못했다.

현재는 net 기준으로 계산하므로 정상이다.

---

## 2.2 Kelly metrics가 position size를 반영

이전 문제:

```text
total_return / max_drawdown은 position size 반영
sharpe / profit_factor는 price return 기준이라 position size 미반영
```

현재 수정:

`BacktestTrade`에 다음 필드가 추가되었다.

```python
trade_return_pct: float = 0.0
gross_trade_return_pct: float = 0.0
```

거래 종료 시 실제 사용한 position size를 반영한다.

```python
trade.trade_return_pct = net_pnl_pct * position_size
trade.gross_trade_return_pct = gross_pnl_pct * position_size
```

metrics 계산도 이제 다음 기준이다.

```python
sharpe = _per_trade_sharpe([t.trade_return_pct for t in trades])
gross_sharpe = _per_trade_sharpe([t.gross_trade_return_pct for t in trades])
```

profit factor도 size-weighted return 기준으로 계산된다.

의미:

```text
Kelly sizing처럼 거래마다 포지션 크기가 달라지는 경우에도
Sharpe/profit_factor가 실제 equity return을 반영함
```

고정 position size에서는 기존과 거의 동일하게 유지된다.

---

## 2.3 단일모델 SELL을 Kelly가 거부

이전 문제:

```text
낮은 P(long_success)를 1 - P(long_success)로 뒤집어
P(short_success)처럼 사용
```

하지만 `label=0`은 반드시 short 성공이 아니다.

`label=0`에는 다음이 섞일 수 있다.

```text
1. long SL first
2. timeout
3. 약한 상승
4. 횡보
5. short TP 성공
```

현재 수정:

```text
single-model 경로 + Kelly SELL:
  short_success 확률이 없으므로 거부
  shorts_skipped_no_short_model 증가

regime-aware bundle 경로:
  전용 short_model의 P(short_success)를 사용
```

이 방향은 맞다.

특히 Kelly에서는 확률 의미가 매우 중요하므로, `1 - P(long)`을 short 확률로 쓰지 않는 것이 안전하다.

---

## 2.4 multi-horizon 파일럿이 regime-aware 구조로 정렬됨

현재 `train-multi-horizon --regime-aware`는 기존 regime-aware 학습과 같은 방향 정책을 사용한다.

```python
MH_REGIME_SIDES = {
    "up":    (("long", "long_success"),),
    "down":  (("short", "short_success"),),
    "range": (("long", "long_success"), ("short", "short_success")),
}
```

즉:

```text
up    → long only
down  → short only
range → long/short both
```

기존 Phase 3 regime-aware 학습 구조와 같다.

생성되는 artifact 구조도 기존 regime-aware 모델과 맞다.

```text
artifacts/multi_horizon_model/
  regime_run_summary.json
  regime_up/
    long_model.json
  regime_down/
    short_model.json
  regime_range/
    long_model.json
    short_model.json
```

이제 Phase 4.5 backtest는 `model.json` 단일 파일이 아니라 디렉터리 artifact를 넘기며, 기존 `load_regime_aware_models` 경로를 재사용한다.

의미:

```text
Phase 4:
  기존 regime-aware 단일 horizon 모델

Phase 4.5:
  regime-aware multi-horizon blended 모델
```

두 모델이 같은 regime bucket / side policy / target semantics를 공유하게 되었다.

---

## 2.5 train-multi-horizon label alignment look-ahead 수정

이전 치명적 문제:

```text
feature_rows는 전체 candles 기준 index를 가짐
그런데 candles[i0:i1] 슬라이스를 넘김
row.index가 sliced candles에 적용되며 미래 candle을 읽을 수 있음
```

즉 training-start가 첫 캔들 이후일 때 조용한 look-ahead가 생길 수 있었다.

현재 수정:

```python
train_rows = feature_rows[i0:train_end]
fit_multi_horizon_ensemble(train_rows, candles, ...)
```

전체 candles를 그대로 넘기고, row만 training window로 자른다.

또한 label forward window가 학습 창을 넘지 않도록 tail을 `max(horizons)`만큼 자른다.

```python
train_end = i1 - max_horizon
```

의미:

```text
feature row index와 candles index 정렬 유지
label forward window가 training window 밖으로 넘어가지 않음
```

이 수정은 중요하다.

---

## 2.6 run_full_pipeline.sh 동기화

이전에는 PowerShell 버전만 새 기능이 들어가고 Bash 버전은 구버전이었다.

현재는 `run_full_pipeline.sh`에도 다음이 들어가 있다.

```text
Phase 2.3 diagnostics
Phase 3.5 train-multi-horizon
Phase 4 Kelly flags
Phase 4.5 multi-horizon backtest
gross/net sharpe summary
```

따라서 Windows PowerShell과 Linux/macOS Bash의 파이프라인 차이가 줄었다.

---

# 3. 직접 확인한 테스트 상태

확인된 테스트:

```text
python -m py_compile btcusdt_quant/*.py ic_diagnostic.py verify_range_halflife.py
→ OK
```

```text
python -m unittest tests.test_review_items tests.test_stacking_ensemble -v
→ Ran 61 tests OK
```

주요 검증 항목:

```text
Kelly cost-aware edge
Kelly size-weighted metrics
single-model short rejection
short_model 존재 시 Kelly short sizing
multi-horizon target_key 검증
multi-horizon label alignment
gross/net sharpe
IC diagnostic cache
OU half-life
```

빠른 핵심 테스트 기준으로는 정상이다.

---

# 4. 남은 핵심 문제

# 4.1 multi-horizon threshold selection horizon과 execution horizon 불일치

현재 `train-multi-horizon --regime-aware`에서 regime/side별 threshold를 고를 때 다음처럼 label을 붙인다.

```python
holdout_labeled = dataset.attach_labels(
    holdout_rows,
    candles,
    horizon=max_horizon,
    label_threshold=args.label_threshold,
    tp_pct=args.tp_pct,
    sl_pct=args.sl_pct,
)
```

즉 `MhHorizons = 30,60,90`이면 threshold selection은 `horizon=90` 기준이다.

하지만 Phase 4.5 backtest는 단일 execution horizon을 사용한다.

```text
--horizon $Horizon
```

기본값:

```text
Horizon = 60
```

따라서 현재 구조는 다음과 같다.

```text
multi-horizon 학습:
  horizon 30/60/90 모델 blend

threshold selection:
  horizon 90 label 기준

backtest execution:
  horizon 60 timeout 기준
```

이건 완전히 같은 목적함수라고 보기 어렵다.

---

## 4.2 왜 중요한가

Phase 4와 Phase 4.5를 비교할 때 의도는 다음이다.

```text
Phase 4:
  single horizon regime-aware model

Phase 4.5:
  multi-horizon blended regime-aware model

비교 차이:
  horizon blend 축 하나
```

하지만 현재는 차이가 하나 더 생긴다.

```text
threshold는 90-bar label 기준
execution은 60-bar timeout 기준
```

따라서 결과 차이가 다음 중 무엇 때문인지 분리하기 어렵다.

```text
1. multi-horizon blend 효과
2. threshold selection horizon mismatch
3. execution horizon mismatch
```

즉 현재 Phase 4.5 결과는 “multi-horizon 구조적 파일럿”으로는 볼 수 있지만, 완전한 like-for-like challenger 비교라고 보기 어렵다.

---

# 5. 권장 수정

## 5.1 threshold horizon 옵션 추가

`train-multi-horizon`에 threshold selection용 horizon을 명시하는 옵션을 추가하는 것이 좋다.

추천 옵션명:

```text
--threshold-horizon
```

또는:

```text
--execution-horizon
```

예:

```text
--threshold-horizon 60
```

기본값은 다음 중 하나로 정할 수 있다.

```text
1. args.threshold_horizon이 있으면 사용
2. 없으면 max(horizons) 사용
```

하지만 파이프라인에서는 명시적으로 `$Horizon`을 넘기는 것이 좋다.

---

## 5.2 코드 수정 방향

현재:

```python
holdout_labeled = dataset.attach_labels(
    holdout_rows,
    candles,
    horizon=max_horizon,
    label_threshold=args.label_threshold,
    tp_pct=args.tp_pct,
    sl_pct=args.sl_pct,
)
```

권장:

```python
threshold_horizon = args.threshold_horizon or max_horizon

holdout_labeled = dataset.attach_labels(
    holdout_rows,
    candles,
    horizon=threshold_horizon,
    label_threshold=args.label_threshold,
    tp_pct=args.tp_pct,
    sl_pct=args.sl_pct,
)
```

그리고 `run_full_pipeline.ps1` / `.sh` Phase 3.5에서 다음을 전달한다.

```powershell
--threshold-horizon $Horizon
```

Bash도 동일하게:

```bash
--threshold-horizon "$Horizon"
```

이렇게 하면:

```text
threshold selection horizon = backtest execution horizon
```

이 되어 Phase 4와 Phase 4.5 비교 해석이 더 깔끔해진다.

---

# 6. 문서 불일치

`PIPELINE_INTEGRATION(1).md`의 Phase 4 설명에는 아직 오래된 문장이 남아 있다.

현재 문서 문구:

```text
단일모델 경로의 SELL은 1 - P(long)으로 자동 반전
```

하지만 현재 실제 코드 동작은 다르다.

현재 실제 동작:

```text
single-model SELL + Kelly:
  short_success 확률이 없으므로 거부
  shorts_skipped_no_short_model 증가

regime bundle SELL + Kelly:
  전용 short_model의 P(short_success)로 사이징
```

권장 문구:

```text
단일모델 경로는 short_success 확률이 없으므로 Kelly sizing에서 SELL을 거부한다.
regime bundle 경로는 전용 short_model의 P(short_success)를 사용한다.
```

문서의 다른 부분에서는 `shorts_skipped_no_short_model`이 0이 아니면 단방향 모델이 섞였다는 뜻이라고 제대로 설명하고 있다.

따라서 Phase 4의 한 줄만 최신 동작에 맞게 수정하면 된다.

---

# 7. live 쪽 남은 작업

live engine에는 여전히 주문 수량 하드코딩이 남아 있다.

```python
entry_quantity = 0.001 if self.signal in {"BUY", "SELL"} else 0.0
```

즉 `PositionSizer.kelly_notional()` API는 준비되어 있지만, 실제 `_handle_signal_event` 주문 경로에서는 아직 사용하지 않는다.

현재 상태:

```text
backtest:
  Kelly sizing 적용 가능

live:
  고정 0.001 BTC 주문
```

따라서 live로 넘어가면 train/backtest/live sizing skew가 발생한다.

다만 현재 범위는 live 제외 / backtest 중심이므로 당장 백테스트 검증에는 치명적이지 않다.

live 전환 전에는 반드시 다음이 필요하다.

```text
1. _handle_signal_event의 entry_quantity=0.001 제거
2. PositionSizer.kelly_notional() 배선
3. BUY/SELL별 probability semantics 확인
4. short_success 모델이 있는 경로에서만 SELL sizing 허용
5. DrawdownProtocol reduce_factor가 실제 quantity에 반영되도록 정리
```

---

# 8. 현재 판단

`CodexProject(2).zip`은 재학습/백테스트를 돌려볼 수 있는 수준까지 왔다.

정상 반영:

```text
Kelly net edge
Kelly size-weighted metrics
single-model short rejection
regime-aware multi-horizon side-specific target
train-multi-horizon label alignment
PowerShell/Bash pipeline 동기화
v12 feature registry 180개 유지
metrics parity 유지
Optuna best_iteration 유지
```

남은 핵심:

```text
1. multi-horizon threshold selection horizon과 backtest execution horizon 정합성
2. PIPELINE_INTEGRATION 문서의 single-model SELL 설명 수정
3. live entry_quantity 하드코딩 제거는 추후 live 단계에서 처리
```

---

# 9. 우선순위

권장 작업 순서:

```text
1순위:
  train-multi-horizon에 --threshold-horizon 또는 --execution-horizon 추가

2순위:
  Phase 3.5에서 $Horizon을 threshold horizon으로 전달

3순위:
  threshold selection label horizon을 Phase 4.5 execution horizon과 맞춤

4순위:
  PIPELINE_INTEGRATION 문서의 single-model SELL 설명 수정

5순위:
  기존 artifacts 삭제
    - artifacts/regime_stacking_model
    - artifacts/backtest_results
    - artifacts/backtest_results_multi_horizon
    - artifacts/multi_horizon_model

6순위:
  run_full_pipeline.ps1 또는 run_full_pipeline.sh 실행

7순위:
  Phase 4 vs Phase 4.5 비교
    - net_total_return
    - net_sharpe
    - max_drawdown
    - profit_factor
    - trade_count
    - shorts_skipped_no_short_model
    - regime별 PnL
    - side별 PnL
    - 월별/요일별 성과

8순위:
  live 전환 전에 _handle_signal_event의 entry_quantity=0.001 제거 및 PositionSizer 배선
```

---

# 10. 다음 수정 요청 예시

다음 작업에서 바로 이어가려면 아래처럼 요청하면 된다.

```text
첨부 ZIP 기준으로 다음을 수정해줘.

1. train-multi-horizon CLI에 --threshold-horizon 옵션 추가
2. regime-aware multi-horizon threshold selection에서 max_horizon 대신 threshold_horizon 사용
3. run_full_pipeline.ps1 Phase 3.5에 --threshold-horizon $Horizon 전달
4. run_full_pipeline.sh Phase 3.5에도 --threshold-horizon "$Horizon" 전달
5. PIPELINE_INTEGRATION 문서에서 단일모델 SELL 설명을 최신 동작에 맞게 수정
6. 관련 테스트 추가
```

---

# 11. 최종 결론

`CodexProject(2).zip`은 직전 리뷰에서 치명적으로 지적했던 문제들이 대부분 해결된 상태다.

특히 다음 수정은 좋다.

```text
Kelly net edge
Kelly size-weighted metrics
single-model SELL rejection
regime-aware multi-horizon side-specific model
label alignment look-ahead 제거
PowerShell/Bash 동기화
```

하지만 Phase 4.5를 진짜 “like-for-like horizon-blend challenger”로 보려면 다음이 필요하다.

```text
threshold selection horizon = backtest execution horizon
```

따라서 현재 상태에서도 실행은 가능하지만, 최종 비교 결과를 해석하기 전에 이 정합성 수정까지 반영하는 것을 권장한다.
