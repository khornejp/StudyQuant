# CodexProject(3) Threshold Horizon 수정 검토 요약

> 대상: `CodexProject(3).zip`  
> 참고 문서: `THRESHOLD_HORIZON_FIX.md`  
> 범위: multi-horizon threshold horizon 정합성, 누수 방지, 파이프라인 전달, 비교 도구, 남은 보완점  
> 핵심 결론: **threshold horizon 정합성 문제는 정상적으로 수정되었으며, 재학습/백테스트 진행이 가능한 상태다. 다만 비교 도구와 실험 해석 문구에는 보완점이 남아 있다.**

---

# 1. 전체 결론

이번 수정은 이전 분석에서 지적했던 핵심 문제를 제대로 해결했다.

정상 반영된 항목:

```text
1. train-multi-horizon에 --threshold-horizon 추가
2. threshold selection horizon과 execution horizon 정렬
3. threshold_horizon > max(horizons)일 때 발생할 수 있는 look-ahead 방지
4. label_reach 기준 training tail trim
5. threshold holdout purge gap 확장
6. 잘못된 horizon 입력 조기 검증
7. artifact에 threshold_horizon / label_reach 기록
8. backtest 실행 horizon과 artifact threshold horizon 불일치 경고
9. PowerShell/Bash 파이프라인에 threshold horizon 전달
10. stale 단일모델 SELL 문서 수정
11. compare_backtests.py 신설
12. 관련 테스트 통과
```

따라서 threshold horizon 문제 자체는 해결된 것으로 판단한다.

현재 상태로 전체 재학습과 백테스트를 진행해도 된다.

다만 다음 보완점은 남아 있다.

```text
1. compare_backtests의 total_return이 단순 trade return 합계
2. trade_count가 winner 판정 대상
3. 두 백테스트의 비교 조건 provenance가 충분히 저장되지 않음
4. Phase 4와 Phase 4.5 차이가 horizon blend 하나뿐이라는 설명은 부정확
5. live 주문 수량은 여전히 0.001 BTC 하드코딩
```

---

# 2. Threshold horizon 수정 확인

## 2.1 CLI 옵션 추가

`train-multi-horizon` 명령에 다음 옵션이 추가되었다.

```text
--threshold-horizon
```

기본 동작:

```python
threshold_horizon = args.threshold_horizon or max_horizon
```

파이프라인에서는 명시적으로 실행 horizon을 전달한다.

PowerShell:

```powershell
--threshold-horizon $Horizon
```

Bash:

```bash
--threshold-horizon "$HORIZON"
```

기본 파이프라인에서는 다음이 일치한다.

```text
threshold selection horizon = backtest execution horizon = 60
```

---

## 2.2 label_reach 누수 방지

단순히 threshold label horizon만 변경하지 않고, 가장 긴 미래 도달거리를 기준으로 학습 구간을 자른다.

```python
label_reach = max(max_horizon, threshold_horizon)
train_end = i1 - label_reach
```

예시:

```text
model horizons = 30, 60, 90
threshold horizon = 60
label reach = 90
```

```text
model horizons = 30, 60, 90
threshold horizon = 120
label reach = 120
```

따라서 `threshold_horizon > max(horizons)`인 경우에도 threshold label이 OOS 백테스트 구간의 candle을 읽지 않는다.

이 수정은 중요하다.

단순 권장안처럼 다음만 적용하면 위험할 수 있다.

```python
threshold_horizon = args.threshold_horizon or max_horizon
```

왜냐하면 training tail을 여전히 `max_horizon`만큼만 자르면, 더 긴 threshold horizon이 학습 종료 이후 데이터를 읽을 수 있기 때문이다.

현재 코드는 이 문제까지 방지한다.

---

## 2.3 Threshold holdout purge 확장

threshold 선택용 holdout에서도 다음이 적용된다.

```python
holdout_start = min(
    len(regime_rows),
    holdout_split + label_reach,
)
```

이는 fit 영역의 label forward window가 threshold holdout 구간과 겹치는 것을 막는다.

레짐별 row는 원본 candle에서 비연속적일 수 있으므로, `label_reach`개의 regime row를 건너뛰는 방식은 시간 기준으로는 필요 이상 보수적일 수 있다.

하지만 이는 leakage가 아니라 데이터 손실 문제다.

안전성 측면에서는 문제가 없다.

---

## 2.4 입력값 조기 검증

다음 검증이 candle load와 feature 계산 전에 수행된다.

```python
if not horizons or any(h <= 0 for h in horizons):
    raise ValueError(...)

if args.threshold_horizon is not None and args.threshold_horizon <= 0:
    raise ValueError(...)
```

장점:

```text
잘못된 설정을 장시간 feature 계산 후 발견하지 않음
0 또는 음수 horizon을 즉시 거부
명확한 오류 메시지 제공
```

---

# 3. Artifact provenance 확인

`regime_run_summary.json`에 다음 정보가 저장된다.

```json
{
  "horizons": [30, 60, 90],
  "threshold_horizon": 60,
  "label_reach": 90
}
```

이제 모델 artifact를 확인하면 다음을 알 수 있다.

```text
어떤 horizon 모델을 blend했는지
threshold를 어떤 horizon label 기준으로 선택했는지
학습 tail/purge가 몇 bar 기준이었는지
```

이전처럼 계산하지 않은 `mean_test_f1: 0.0` 값도 제거되었다.

이 방향은 좋다.

---

# 4. Backtest mismatch 경고 확인

백테스트는 artifact의 `threshold_horizon`과 실행 `--horizon`을 비교한다.

불일치 예:

```text
artifact threshold horizon = 90
backtest horizon = 60
```

경고:

```text
WARNING: artifact thresholds were selected on 90-bar labels
but --horizon is 60.
```

일치하면 경고하지 않는다.

장점:

```text
오래된 artifact를 다른 horizon으로 실행해도 조용히 넘어가지 않음
threshold 재학습이 필요한 상황을 즉시 알 수 있음
실험 provenance 오류를 줄임
```

---

# 5. 파이프라인 정합성

PowerShell과 Bash 모두 다음 조건을 전달한다.

Phase 3.5:

```text
--threshold-horizon $Horizon
```

Phase 4.5:

```text
--horizon $Horizon
```

또한 Phase 4와 Phase 4.5는 다음 조건을 동일하게 사용한다.

```text
backtest 기간
fee
slippage
TP
SL
threshold floor
Kelly 설정
metrics directory
execution horizon
```

따라서 이전의 명확한 threshold horizon mismatch는 해결되었다.

---

# 6. 문서 수정 확인

이전 문서의 잘못된 설명:

```text
단일모델 SELL은 1 - P(long)으로 자동 반전
```

현재 설명:

```text
단일모델은 P(short_success)가 없으므로
Kelly sizing에서 SELL을 거부한다.

레짐 번들은 전용 short model의
P(short_success)를 사용한다.
```

현재 코드 동작과 일치한다.

---

# 7. 테스트 결과

확인된 테스트:

```text
py_compile:
  btcusdt_quant/*.py
  compare_backtests.py
  ic_diagnostic.py
  verify_range_halflife.py

결과:
  OK
```

```text
관련 테스트:
  test_review_items
  test_stacking_ensemble
  test_feature_deactivation
  test_optuna_best_iteration
  test_regime_rules

결과:
  Ran 93 tests
  OK
```

주요 검증 항목:

```text
threshold horizon label reach
holdout label boundary
backtest mismatch warning
multi-horizon label alignment
Kelly net edge
Kelly size-weighted metrics
single-model short rejection
feature registry 180개
Optuna best_iteration
regime detector
```

Bash 구문 검사:

```text
bash -n run_full_pipeline.sh
→ OK
```

첨부 보고서 기준 전체 스위트:

```text
223 passed
기존 parquet float32 실패 1건 제외
```

---

# 8. compare_backtests.py 평가

새 비교 도구 추가 방향은 좋다.

지원하는 분해:

```text
전체
regime별
side별
regime × side별
월별
```

Kelly run도 `trade_return_pct`를 사용하므로 실제 equity return 기준으로 분석한다.

다음 조건의 불일치 경고도 지원한다.

```text
비용 조건
min_hold
cooldown
Kelly on/off
short model 부재로 long-only가 된 경우
```

하지만 아래 보완이 필요하다.

---

# 9. compare_backtests 보완점 1: total_return 명칭/계산

현재 breakdown에서 다음처럼 계산한다.

```python
"total_return": sum(returns)
```

이 값은 실제 복리 계좌 수익률이 아니다.

예:

```text
+10%
-10%
```

단순 합:

```text
0%
```

실제 복리:

```text
1.10 × 0.90 - 1 = -1%
```

따라서 현재 `total_return`은 이름이 부정확하다.

## 권장 방법 A

명칭만 명확히 변경:

```python
"sum_trade_returns": sum(returns)
```

표시:

```text
sum_ret
```

이 방식이 가장 단순하다.

## 권장 방법 B

복리 subset return 추가:

```python
compounded_return = math.prod(1.0 + r for r in returns) - 1.0
```

추천 출력:

```text
sum_trade_returns
compounded_subset_return
```

주의:

regime별 subset을 따로 복리 계산하면 실제 전체 trade sequence와는 다른 가상 결과다.

따라서 기여도 성격의 `sum_trade_returns`와 subset standalone 성격의 `compounded_subset_return`을 구분해 표시하는 것이 좋다.

---

# 10. compare_backtests 보완점 2: trade_count winner 제거

현재 head-to-head 비교에서 거래 수가 더 많은 모델을 winner로 표시할 수 있다.

하지만 거래 수가 많다고 더 좋은 전략은 아니다.

예:

```text
Model A:
  1000 trades
  PF 0.8

Model B:
  200 trades
  PF 1.4
```

이 경우 Model B가 더 나을 수 있다.

따라서 trade_count는 winner 판정 없이 참고값으로만 보여야 한다.

권장:

```text
trade_count:
  A = ...
  B = ...
  difference = ...
  winner 없음
```

---

# 11. compare_backtests 보완점 3: 비교 조건 provenance 부족

현재 비교 도구가 확인하는 조건:

```text
round_trip_cost_pct
min_hold_bars
cooldown_bars
Kelly on/off
```

하지만 like-for-like 비교를 위해서는 다음도 같아야 한다.

```text
backtest start/end
execution horizon
execution TP/SL
threshold floor
position size cap
Kelly multiplier
Kelly lookback
initial equity
regime routing config
```

현재 `backtest_summary.json`에 일부 핵심 조건이 저장되지 않기 때문에 비교 도구가 완전한 정합성 검증을 할 수 없다.

## 권장 provenance 추가

```text
backtest_start
backtest_end
execution_horizon
exec_tp_pct
exec_sl_pct
threshold_floor
position_size_cap
initial_equity
kelly_multiplier
kelly_lookback_bars
rule_regime_config hash/path
```

그 후 `compare_backtests.py`에서 차이가 있으면 경고하도록 한다.

---

# 12. Phase 4 vs Phase 4.5 비교 설명 주의

Threshold horizon과 regime/side 구조는 맞춰졌다.

하지만 Phase 4와 Phase 4.5는 학습 방식이 여전히 다르다.

## Phase 3 기존 레짐 모델

```text
Optuna tuning
best_iteration cap
regime/side별 hyperparameter tuning
최종 full-data refit
```

## Phase 3.5 multi-horizon 모델

```text
horizon별 기본 모델 학습
Optuna 없음
validation accuracy edge 기반 blend weight
```

따라서 두 모델의 차이는 다음 두 가지다.

```text
1. single horizon vs multi-horizon blend
2. Optuna-tuned model vs default-parameter horizon models
```

따라서 다음 표현은 부정확하다.

```text
ONLY axis that differs is horizon blend
```

권장 표현:

```text
두 모델은 동일한 regime/side/target/threshold horizon 조건을 공유한다.
다만 multi-horizon 구성과 base model tuning 방식은 다르다.
```

현재 파일럿 단계에서는 이 문구 수정만으로 충분하다.

정말 horizon 축만 비교하려면 Phase 3.5 horizon별 모델에도 동일한 Optuna 정책을 적용해야 하지만, 학습 비용이 크게 증가한다.

---

# 13. Threshold floor 주의사항

예:

```text
learned range/long threshold = 0.2516
threshold floor = 0.45
effective threshold = 0.45
```

이 경우 threshold horizon 수정으로 learned threshold가 바뀌어도 실제 실행에서는 floor가 덮어쓴다.

재실행 후 반드시 확인할 값:

```text
backtest_summary.json
  effective_thresholds
    learned_long
    learned_short
    effective_long
    effective_short
```

해석:

```text
모든 learned threshold가 effective threshold와 다름
→ threshold floor가 학습 임계값을 대부분 덮어씀

일부 learned threshold가 floor보다 높음
→ threshold horizon 수정 효과가 실제 실행에 반영됨
```

---

# 14. Live 미반영

live engine에는 여전히 다음 하드코딩이 남아 있다.

```python
entry_quantity = 0.001
```

현재 상태:

```text
backtest:
  Kelly sizing

live:
  fixed 0.001 BTC
```

현재 범위가 live 제외라면 재학습을 막는 문제는 아니다.

live 전환 전에는 다음 작업이 필요하다.

```text
PositionSizer.kelly_notional() 배선
DrawdownProtocol.reduce_factor 실제 수량 반영
BUY/SELL별 probability semantics 검증
전용 short_success model이 있는 경로에서만 SELL sizing
```

---

# 15. 현재 우선순위

```text
1순위:
  현재 코드로 전체 재학습/백테스트 실행

2순위:
  effective_thresholds에서 learned vs effective 비교

3순위:
  compare_backtests의 total_return 명칭/복리 계산 보완

4순위:
  trade_count winner 판정 제거

5순위:
  backtest summary provenance 확장

6순위:
  Phase 4 vs 4.5 설명을 horizon-only 비교가 아닌 challenger 파일럿으로 수정

7순위:
  live 전환 시 Kelly sizing 배선
```

---

# 16. 재실행 전 삭제 대상

모델 입력/threshold artifact가 바뀌므로 기존 모델과 결과는 삭제하거나 별도 보관해야 한다.

삭제 대상:

```text
artifacts/regime_stacking_model
artifacts/multi_horizon_model
artifacts/backtest_results
artifacts/backtest_results_multi_horizon
```

보존 대상:

```text
artifacts/archive_full
artifacts/metrics
artifacts/btcusdt_2020_2025.parquet
```

---

# 17. 재실행 후 확인 항목

```text
threshold_horizon = 60
label_reach = 90

artifact vs backtest horizon mismatch warning 없음

effective_thresholds:
  learned_long
  learned_short
  effective_long
  effective_short

shorts_skipped_no_short_model = 0

Phase 4 vs Phase 4.5:
  net_total_return
  net_sharpe
  max_drawdown
  profit_factor
  trade_count
  regime별 PnL
  side별 PnL
  월별 성과
```

---

# 18. 최종 판단

이번 요청 사항은 정상 반영되었다.

```text
--threshold-horizon 추가                OK
execution horizon과 pipeline 정렬       OK
label_reach 누수 방지                   OK
holdout purge 확장                      OK
입력값 조기 검증                        OK
artifact provenance 저장                OK
backtest mismatch 경고                  OK
PowerShell/Bash 전달                    OK
stale SELL 문서 수정                    OK
compare_backtests 추가                  OK
관련 테스트 통과                        OK
```

Threshold horizon 문제는 해결됐다.

현재 상태로 전체 재학습과 백테스트를 진행해도 된다.

다만 Phase 4.5는 엄밀한 horizon-only A/B라기보다 다음 성격으로 보는 것이 정확하다.

```text
regime-aware multi-horizon challenger 파일럿
```

비교 결과를 해석할 때는 horizon blend와 base model tuning 방식이 함께 다르다는 점을 명시해야 한다.
