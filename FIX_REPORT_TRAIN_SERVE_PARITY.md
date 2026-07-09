# 수정 보고서 — train/serve 일관성 4개 이슈 (2026-07-03)

앞선 외부 분석에서 확인된 4개 문제를 실제 코드로 재검증한 뒤 수정. 각 수정은
`python3 -c` 직접 실행으로 단위 검증했고, 전체 회귀(test_core / test_v718)는
수정 전후 결과가 동일함(문서화된 베이스라인 그대로: test_core errors=7,
test_v718 failures=2/errors=14/skipped=6 — 전부 catboost·pyarrow·lightgbm·torch
미설치로 인한 환경 오류이며 제품 코드 결함이 아님).

수정 파일: `btcusdt_quant/live.py`, `btcusdt_quant/backtest.py`,
`btcusdt_quant/training.py`, `btcusdt_quant/cli.py`.

우선순위 순서(#4 → #2 → #3 → #1)로 진행.

---

## #4 EV의 TP/SL 불일치 (가장 급함) — 수정

**문제**: 진입 게이트 `evaluate_entry_signal`의 EV가 하드코딩된
`gross_tp=0.0015 / gross_sl=0.0010`(RR 1.5)로 계산됐는데, 실제 청산 배리어
(`optimized_tp_sl`)와 라벨/백테스트 기본값은 `tp=0.003 / sl=0.0015`(RR 2.0).
백테스트는 이 함수를 호출할 때 tp/sl을 아예 안 넘겨 잘못된 기본값을 썼음. CLI
도움말은 이 값들이 "MUST match"라고 명시 — 코드가 자기 계약을 위반.

**수정**:
- `optimized_tp_sl`의 배리어 계산부를 공용 헬퍼 `resolve_tp_sl_deltas(features,
  strategy)`로 추출. 이제 "실제 청산 배리어"와 "EV 계산 배리어"가 단일
  소스에서 나오므로 구조적으로 어긋날 수 없음.
- `evaluate_entry_signal`에 `strategy`/`features` 인자 추가 — 넘기면 EV가
  그 bar의 실제 배리어(ATR/floor 포함)로 계산됨. 폴백 기본값도 라벨과 일치하는
  0.003/0.0015로 교체(잊고 안 넘겨도 라벨-정합).
- backtest 2개 호출부, live 1개 호출부가 모두 `strategy`+`features`를 넘기도록 수정.

**검증**: ATR 케이스에서 EV가 실제 resolved delta(0.16/0.08)로 계산됨을 확인,
`optimized_tp_sl` 출력 가격은 불변(기존 strategy 테스트 전부 통과).

---

## #2 live 라우팅 train/serve skew — 수정

**문제**: 학습·백테스트는 learned regime classifier(`route_regime_causal` +
`.cbm`)로 라우팅하는데, live는 `regime_classifier_model.cbm`을 로드하지 않고
`trend_slope_30` 룰 detector로만 `active_regime`을 정함. 라우팅 신호가 실전에서
달라지는 명백한 skew. 또한 live 진입 모델이 F18(`regime_prob_*`)를 0/0/0으로 봄.

**수정**:
- `LiveEngine`/`run_live`에 `regime_classifier_model` 파라미터 추가.
- `_compute_signal`의 regime 결정에 Priority 2로 classifier 라우팅 삽입:
  버퍼의 F17 벡터에 `route_regime_causal`을 돌려 `active_regime`을 정하고,
  마지막 bar의 `regime_prob_up/range/down`을 latest row의 features에 in-place
  주입(backtest의 raw_probs 주입과 동일). detector는 classifier가 없을 때만
  쓰는 Priority 3 폴백으로 강등.
- CLI `live`에 `--regime-classifier-dir` 추가. training/backtest와 **동일한**
  디렉터리를 넘기면 같은 `.cbm`으로 라우팅. 미지정 시 기존 detector 폴백.

**검증**: mock classifier로 라우팅 라벨(`up`)과 F18 주입(0.7/0.2/0.1)이 정확히
동작함을 확인. classifier 미지정 dry-run live는 기존과 동일하게 동작.

**한계(정직하게)**: live는 스트리밍이라 smoothing 히스테리시스를 버퍼 위에서
재계산함. 단, per-bar raw 확률은 stateless(그 bar의 F17만 의존)라 마지막 bar의
F18 주입값은 버퍼 길이와 무관하게 정확. 라우팅 라벨(smoothed)만 버퍼가 길수록
학습 smoothing에 근접 — 온라인 히스테리시스의 본질적 특성.

---

## #3 selected_thresholds 미연결 — 수정

**문제**: 각 regime의 holdout에서 out-of-sample로 고른 per-side 임계값
(`selected_thresholds`)이 `regime_run_summary.json`에는 저장되지만
live/backtest 의사결정에서 읽히지 않음. live는 정적 프로파일/CLI 기본(0.55)만 씀.

**수정**:
- `RegimeModelBundle`에 `regime_thresholds: {regime: {long, short}}` 필드 추가.
- `load_regime_aware_models`가 `regime_results[regime]["selected_thresholds"]`를
  파싱해 bundle에 적재.
- regime-aware EV 경로에서 임계값 우선순위 적용:
  **명시적 CLI override > 학습된 per-regime holdout 임계값 > 0.55**.
- live CLI `--long-threshold/--short-threshold` 기본값을 `0.55 → None`으로 변경
  (backtest의 None-센티넬 패턴과 정합). "명시적으로 넘겼는지"를 감지하기 위함.

**부수효과 차단**: CLI 기본이 None이 되면 비-EV 경로(`_apply_strategy_decision`,
단일모델/레거시 아티팩트)의 임계값이 프로파일 값으로 바뀔 수 있어, 그 경로엔
기존 0.55를 그대로 유지하는 파생값(`_nonev_long/short_threshold`)을 써서 **비-EV
경로 동작을 완전히 보존**. 학습 임계값 연결은 regime-aware EV 경로에만 적용.

**검증**: loader가 `{up:{long:.62,short:.58}, down:{long:.70}}`를 정확히 파싱함을
확인. 우선순위 로직(override > learned > 0.55)도 케이스별 확인.

---

## #1 커버리지 갭 가드 (보험) — 수정

**문제**: `regime_probabilities.json`은 hand-label이 있는 시점만 저장하므로,
학습 구간이 라벨 커버리지보다 넓으면 커버리지 밖 row가 F18=0/0/0으로 들어가
smoothing의 sticky/bootstrap을 타고 어떤 regime 버킷을 오염시킬 수 있음. 기존
가드는 "전부 0"일 때만 raise — **부분 갭은 조용히 통과**.

> 참고: 현재 프로젝트의 `regimes.json`은 2020-01-01~2025-01-01을 빈틈없이
> 덮음(학습 1827일 커버리지 갭 0). 따라서 이 수정은 현재 데이터엔 **무영향
> (no-op)**이며, 라벨을 지우거나 `--training-start`를 라벨 시작보다 앞당길 때만
> 발동하는 회귀 방지용 보험임.

**수정**: `run_regime_aware_training`에서 F18=0/0/0 row를 감지해 (a) 개수/비율을
경고 로그로 노출하고 (b) smoothing 이후 해당 row의 regime을 `None`으로 만들어
**모든 버킷에서 제외**(어떤 regime 모델도 오염시키지 않음). 경고는 라벨 확장 또는
`--training-start` 조정을 안내.

**검증**: 커버 3 + 미커버 2(중간) + 커버 3 시퀀스에서, 미커버 row가 (원래는
sticky로 'up'을 상속했을 것이나) 이제 `None`으로 모든 버킷에서 제외됨을 확인.

---

## 검증 요약

```
python3 -m compileall -q btcusdt_quant        # 통과
python3 -m btcusdt_quant --help               # 통과
python3 -m btcusdt_quant live --dry-run ...    # 통과 (classifier 미지정 경로 불변)
python3 -m unittest tests.test_core            # 131 tests: errors=7(pyarrow), failures=0
python3 -m unittest tests.test_v718            # 159 tests: failures=2, errors=14, skipped=6
```

test_v718의 실패/오류는 전부 catboost·lightgbm·torch·pyarrow 미설치 환경 문제로,
**수정 전 베이스라인과 정확히 동일**(회귀 0). catboost가 설치된 환경에서
model-family 의존 테스트를 별도 확인 권장.
