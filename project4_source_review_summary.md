# CodexProject(4) 소스 검토 요약

> 대상: `CodexProject(4).zip`  
> 참고 문서: `CODE_REVIEW_FIXES(1).md`  
> 범위: multi-horizon 최종 refit, 비교 도구 보완, run_config provenance, horizon weight 매핑, 남은 live 이슈  
> 핵심 결론: **문서 기반 수정은 대부분 정상 반영되었고, 현재 상태로 재학습과 백테스트를 진행할 수 있다. 다만 비교 안전성과 final refit 실패 처리에는 보완이 필요하다.**

---

# 1. 전체 결론

`CodexProject(4).zip`은 이전 검토 문서의 핵심 수정사항을 대부분 반영했다.

정상 반영된 주요 항목:

```text
1. multi-horizon 배포 모델을 레짐 전체 데이터로 최종 refit
2. diagnostic ensemble의 horizon weight를 최종 refit에 재사용
3. horizon weight를 위치가 아닌 horizon key로 매핑
4. 각 horizon 모델이 자신의 전체 label row를 학습
5. NaN/inf blend weight 방어
6. 실제 final_refit 성공 여부 기록
7. compare_backtests의 단순 return 합계 문제 수정
8. trade_count winner 판정 제거
9. backtest run_config provenance 추가
10. effective threshold 비교 리포트 추가
11. horizon-only A/B 표현 대부분 수정
```

현재 확인된 재학습 차단 수준의 치명적 버그는 없다.

다만 남은 주요 보완점:

```text
1. final refit 실패 시 pipeline이 성공한 것처럼 계속 진행
2. compare_backtests가 전체 strategy config를 비교하지 않음
3. 전체 compounded return과 net_total_return reconciliation 검사 없음
4. 일부 like-for-like 문구가 아직 남아 있음
5. ZIP에 tests/ 디렉터리가 없어 신규 테스트를 재현하기 어려움
6. live entry_quantity=0.001 하드코딩은 미수정
```

---

# 2. Multi-Horizon 최종 refit 확인

## 2.1 기존 문제

이전 multi-horizon 학습은 배포 모델이 레짐 전체 데이터를 사용하지 않았다.

구조:

```text
레짐 데이터 100%
→ threshold/diagnostic prefix 약 80%
→ 내부 validation tail 제거
→ 실제 배포 모델 약 64% 데이터 사용
```

반면 Phase 3 기존 regime 모델은 최종 배포 모델을 레짐 전체 데이터로 재학습한다.

따라서 Phase 4와 Phase 4.5 사이에 학습 데이터 양 차이가 있었다.

---

## 2.2 현재 수정

현재 구조:

```text
1. prefix 데이터로 diagnostic ensemble 학습
2. diagnostic validation으로 horizon blend weight 결정
3. 별도 threshold holdout에서 threshold 선택
4. 결정된 weight를 유지
5. 레짐 전체 데이터로 배포용 horizon 모델 최종 refit
```

코드 개념:

```python
diagnostic = fit_multi_horizon_ensemble(
    fit_rows,
    candles,
    target_key=target_key,
)

adapter = fit_multi_horizon_ensemble(
    regime_rows,
    candles,
    target_key=target_key,
    weights=dict(zip(diagnostic.horizons, diagnostic.weights)),
)
```

이제 최종 배포 모델은 레짐 전체 데이터를 사용한다.

---

## 2.3 최종 refit 상태 기록

사이드별 artifact:

```json
{
  "final_refit": true,
  "threshold_fit_input_rows": 3548,
  "deployed_fit_input_rows": 4436
}
```

상위 summary:

```json
{
  "final_refit_requested": true,
  "final_refit_all_sides": true
}
```

요청값만 기록하는 것이 아니라 실제 refit 성공 여부를 기록한다.

이 부분은 적절하다.

---

# 3. Horizon weight 매핑 안전성

## 3.1 기존 문제

기존에는 weight를 sequence로 받았다.

예:

```python
horizons = [90, 30, 60]
weights = [0.7, 0.1, 0.2]
```

내부에서 horizon을 정렬하면 weight가 잘못된 horizon에 붙을 수 있었다.

---

## 3.2 현재 수정

현재 입력:

```python
weights: Mapping[int, float]
```

예:

```python
horizons = [60, 30]

weights = {
    60: 0.9,
    30: 0.1,
}
```

정렬 후:

```text
adapter.horizons = (30, 60)
adapter.weights = (0.1, 0.9)
```

weight가 horizon key에 정확히 유지된다.

누락 또는 초과 key도 명시적으로 거부한다.

---

# 4. Horizon별 전체 label row 사용

기존에는 horizon별 label 길이 중 최소값으로 모두 잘랐다.

예:

```text
horizon 30 label rows = 1200
horizon 60 label rows = 1170
horizon 90 label rows = 1140
```

기존 방식:

```text
모든 horizon이 1140 rows만 학습
```

현재 방식:

```text
horizon 30 → 1200 rows
horizon 60 → 1170 rows
horizon 90 → 1140 rows
```

각 horizon이 자신이 사용할 수 있는 전체 label row를 학습한다.

최종 full-data refit 취지와 맞는다.

---

# 5. NaN/inf weight 방어

다음 두 경로 모두 finite validation이 추가됐다.

```text
fit_multi_horizon_ensemble()
MultiHorizonEnsembleAdapter.__post_init__()
```

거부 대상:

```text
NaN
+inf
-inf
음수 weight
모든 weight 합계가 0
```

따라서 학습 입력과 JSON 역직렬화 양쪽에서 잘못된 blend probability가 조용히 생성되지 않는다.

---

# 6. compare_backtests.py 개선 확인

## 6.1 Return 분리

이전:

```python
total_return = sum(trade_return_pct)
```

문제:

```text
단순 합계를 실제 계좌 수익률처럼 표시
```

현재:

```text
sum_trade_returns
compounded_subset_return
```

의미:

```text
sum_trade_returns:
  bucket의 additive contribution

compounded_subset_return:
  해당 bucket만 독립적으로 거래했다고 가정한 복리 결과

net_total_return:
  실제 전체 계좌 수익률
```

구분이 명확해졌다.

---

## 6.2 Trade count winner 제거

현재 trade_count는 참고용으로만 표시된다.

```text
trade_count:
  A 값
  B 값
  차이
  winner 없음
```

거래 수가 많다고 좋은 전략이 아니므로 적절한 수정이다.

---

## 6.3 Effective threshold 비교

현재 비교 도구는 다음을 출력한다.

```text
learned_long
effective_long
learned_short
effective_short
```

그리고 모든 learned threshold가 floor/override에 덮인 경우 다음 의미의 경고를 낸다.

```text
이 실행은 학습 threshold 변경 효과를 실제 backtest에서 보여줄 수 없음
```

threshold horizon 수정 효과가 실제 체결 조건에 반영됐는지 확인하는 데 유용하다.

---

# 7. Backtest run_config provenance

`backtest_summary.json`에 실행 조건이 저장된다.

현재 포함된 주요 값:

```text
backtest_start
backtest_end
execution_horizon
exec_tp_pct
exec_sl_pct
position_size
initial_equity
tp_sl_method
strategy
strategy_tp_pct
strategy_sl_pct
long_threshold_override
short_threshold_override
Kelly enabled
Kelly multiplier
Kelly lookback
Kelly holding period
```

이전보다 Phase 4와 Phase 4.5 비교 안전성이 크게 좋아졌다.

---

# 8. 직접 확인한 테스트

## 8.1 문법 검사

```text
python -m py_compile
→ OK
```

```text
bash -n run_full_pipeline.sh
→ OK
```

---

## 8.2 기존 테스트 연결 실행

최신 ZIP에는 `tests/` 디렉터리가 없었다.

따라서 이전 `CodexProject(3)`의 테스트를 최신 소스에 연결해 실행했다.

결과:

```text
93 tests
OK
```

포함:

```text
Kelly 비용 반영
Kelly size-weighted metrics
multi-horizon alignment
threshold horizon guard
feature registry 180개
Optuna best_iteration
regime detector
```

---

## 8.3 별도 스모크 검증

확인:

```text
horizon-keyed weight mapping
각 horizon 전체 label row 사용
NaN/inf weight 거부
```

모두 정상이다.

---

# 9. 남은 문제 1: final refit 실패 시 pipeline 지속

## 9.1 현재 동작

최종 refit이 실패하면:

```python
except ValueError as error:
    print("final refit failed ... shipping the prefix model")
```

즉 전체 레짐 데이터 refit에 실패해도 prefix diagnostic 모델을 배포한다.

summary에는 다음이 기록된다.

```text
final_refit_all_sides = false
```

하지만 pipeline은 성공 코드로 종료할 수 있다.

---

## 9.2 위험

Phase 4.5 모델이 전체 레짐 데이터가 아닌 약 64% 데이터만 학습했는데도:

```text
백테스트 진행
compare_backtests 진행
결과 비교
```

가 계속될 수 있다.

이 경우 Phase 4와 Phase 4.5 비교가 불공정하다.

---

## 9.3 권장 수정

기본 정책:

```python
if final_refit_requested and not final_refit_all_sides:
    print(
        "multi-horizon training failed: one or more final refits failed",
        file=sys.stderr,
    )
    return 1
```

빠른 파일럿이 필요하면 별도 옵션:

```text
--allow-partial-final-refit
```

권장 의미:

```text
기본:
  하나라도 final refit 실패 → pipeline 중단

--allow-partial-final-refit:
  prefix model 배포 허용
  명확한 artifact marker와 경고 출력
```

현재 `--skip-final-refit`은 사용자가 의도적으로 생략하는 옵션이므로, 예상치 못한 실패와 분리해야 한다.

---

# 10. 남은 문제 2: comparability 검사 불완전

## 10.1 현재 확인하는 항목

```text
backtest window
execution horizon
exec TP/SL
position size
initial equity
Kelly 설정
fee/cost
min_hold
cooldown
```

---

## 10.2 아직 비교하지 않는 항목

`run_config`에는 다음이 있지만 `COMPARABILITY_KEYS`에 일부 포함되지 않는다.

```text
strategy
strategy_tp_pct
strategy_sl_pct
long_threshold_override
short_threshold_override
```

따라서 다음 두 실행이 달라도 경고가 없을 수 있다.

```text
Run A:
  strategy = balanced
  threshold override 없음

Run B:
  strategy = aggressive
  long threshold override = 0.7
```

---

## 10.3 StrategyConfig 전체 저장 권장

실제 체결에 영향을 주는 값:

```text
atr_multiplier_tp
atr_multiplier_sl
min_reward_risk
min_tp_floor_pct
min_sl_floor_pct
use_atr_pricing
long_threshold
short_threshold
```

권장:

```python
"strategy_config": {
    **strategy.as_dict(),
    "use_atr_pricing": strategy.use_atr_pricing,
}
```

비교:

```python
if cfg_a.get("strategy_config") != cfg_b.get("strategy_config"):
    warnings.append("run_config.strategy_config differs")
```

최소한 `COMPARABILITY_KEYS`에 다음은 추가해야 한다.

```text
strategy
strategy_tp_pct
strategy_sl_pct
long_threshold_override
short_threshold_override
```

---

# 11. 남은 문제 3: compounded return reconciliation

## 11.1 현재 의미

전체 trade의:

```python
product(1 + trade_return_pct) - 1
```

은 원칙적으로:

```text
net_total_return
```

과 일치해야 한다.

이유:

```text
한 번에 active trade 1개
trade_return_pct에 position size 반영
equity_next = equity * (1 + trade_return_pct)
```

Kelly로 거래마다 size가 달라도 `trade_return_pct`에 이미 반영된다.

---

## 11.2 Subset의 의미

다음 subset의 compounded return은 전체 net return과 다르다.

```text
regime별
side별
월별
regime × side별
```

이는 해당 subset만 독립적으로 거래한 가상 복리 결과다.

---

## 11.3 권장 reconciliation 검사

```python
overall_compounded = _compounded(overall)
reported_return = float(backtest.get("net_total_return", 0.0))

if abs(overall_compounded - reported_return) > 1e-8:
    print(
        "WARNING: trade returns do not reconcile with net_total_return"
    )
```

이 검사는 다음 오류를 잡을 수 있다.

```text
trade_return_pct 저장 오류
artifact 일부 손상
equity 계산과 trade list 불일치
구버전 artifact fallback 문제
```

---

# 12. 남은 stale 문구

일부 스크립트에는 아직 다음 표현이 남아 있다.

```text
like-for-like challenger
```

또는:

```text
Phase 4.5 is a like-for-like challenger
```

하지만 실제 차이는 다음과 같다.

```text
1. single horizon vs multi-horizon blend
2. Phase 3 Optuna tuned vs Phase 3.5 기본 base model
3. blend probability calibration 의미론 차이
```

학습 데이터 비율 차이는 final refit으로 해결됐다.

권장 문구:

```text
Phase 4.5 is a regime-aligned multi-horizon challenger.
It shares execution and routing conditions with Phase 4,
but also differs in horizon blending, base-model tuning,
and probability calibration semantics.
```

한국어:

```text
Phase 4.5는 Phase 4와 실행 조건과 레짐 라우팅을 맞춘
multi-horizon challenger다.

다만 horizon blend, base model tuning,
확률 calibration 의미론은 여전히 다르다.
```

---

# 13. ZIP 패키징 문제

`CodexProject(4).zip`에는 다음이 없다.

```text
tests/
```

따라서 보고서의:

```text
230 passed
tests/test_review_items.py 72 passed
```

를 ZIP 단독으로 재현할 수 없다.

다음 ZIP에는 포함하는 것이 좋다.

```text
tests/test_review_items.py
tests/test_stacking_ensemble.py
tests/test_feature_deactivation.py
tests/test_optuna_best_iteration.py
tests/test_regime_rules.py
```

특히 신규 테스트:

```text
CompareBacktests tests
MultiHorizonFinalRefit tests
non-finite weight tests
horizon-keyed weight tests
```

---

# 14. Live 미반영

현재 live 주문 경로:

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

live 전환 전 필요 작업:

```text
1. PositionSizer.kelly_notional 배선
2. DrawdownProtocol.reduce_factor를 실제 수량에 반영
3. short_success 확률이 있는 경로에서만 SELL sizing
4. balance / cap / leverage / min quantity 검증
5. backtest/live sizing parity 테스트
```

---

# 15. 현재 우선순위

## 재학습 전 권장

```text
1. final refit 실패 시 기본 pipeline 중단
2. compare_backtests에 전체 strategy config 비교 추가
3. overall compounded return reconciliation 추가
4. 남은 like-for-like 문구 수정
5. tests/를 ZIP에 포함
```

---

## 재학습 후 반드시 확인

`regime_run_summary.json`:

```text
final_refit_requested = true
final_refit_all_sides = true
```

각 regime/side:

```text
final_refit = true
```

multi-horizon provenance:

```text
horizons = [30,60,90]
threshold_horizon = 60
label_reach = 90
```

backtest:

```text
threshold horizon mismatch warning 없음
shorts_skipped_no_short_model = 0
```

compare_backtests:

```text
NOT LIKE-FOR-LIKE 경고 없음
effective threshold override 확인
overall compounded return과 net_total_return 정합
```

---

# 16. 최종 판단

정상 반영:

```text
multi-horizon 최종 full-regime refit        OK
diagnostic weight 재사용                    OK
horizon-keyed weight 매핑                   OK
각 horizon 전체 label row 사용              OK
NaN/inf weight 방어                         OK
실제 final_refit 상태 기록                  OK
sum return / compounded return 분리          OK
trade_count winner 제거                     OK
run_config provenance 추가                  OK
effective threshold report                  OK
challenger 설명 개선                        대부분 OK
```

현재 확인된 재학습 차단 수준의 치명적 버그:

```text
없음
```

현재 코드로 재학습과 OOS 백테스트를 진행할 수 있다.

다만 다음 조건은 중요하다.

```text
final_refit_all_sides = false인 경우
Phase 4와 Phase 4.5 비교를 중단해야 한다.
```

Phase 4.5는 엄밀한 horizon-only A/B가 아니라 다음 성격이다.

```text
regime-aligned multi-horizon challenger
```

실행 조건과 routing은 Phase 4와 맞지만, horizon blending, base-model tuning, probability calibration 차이는 남아 있다.
