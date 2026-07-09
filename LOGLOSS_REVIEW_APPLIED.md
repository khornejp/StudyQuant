# Logloss 0.6대 정체 리뷰 반영 (A~E) + 검증 구조 재설계

업로드된 리뷰 문서의 16개 주장을 실제 코드와 하나씩 대조 검증 후, 확인된 5개
(A~E)를 적용. 검증 구조도 사용자 지시대로 재설계.

## 검증 결과 요약
| # | 주장 | 검증 | 조치 |
|---|---|---|---|
| A | class_weights 자동적용이 logloss 왜곡 | 사실 (models.py 199-208) | 옵션화, 기본 OFF |
| B | baseline logloss 미출력 | 사실 | 추가 |
| C | regime별 validation이 전체 test row에 섞임 | 사실 (training.py 632, up/long 모델이 down+range 섞인 2025H1 전체로 평가되던 중) | 재설계 (아래) |
| D | 날짜 end가 inclusive라 마지막날 대부분 누락 | 사실 (`<=` + 00:00 파싱) | exclusive 파싱으로 수정 |
| E | regimes.json에 4개 gap | 사실 (2022-12-31, 2023-12-31, 2024-10-29~11-05 7일, 2024-12-31) | 전부 메움 |
| - | up/down 양방향 학습 필요 | 설계 판단, 버그 아님 | 미적용 (별도 논의 필요) |
| - | TP/SL/EV 기준 통일 | 이전 세션에 --fixed-tp-sl로 이미 해결 | 확인만 |
| - | ensemble/cv-mode가 user-regime 경로 미적용 | 사실이나 기존에 알던 것 | 미적용 (구조적 재작업 필요) |

## A. class_weights 옵션화 (models.py)
- `CatBoostAdapter.DEFAULT_PARAMS`에 `auto_class_weights_enabled: False` 추가.
- `fit()`에서 이 플래그를 pop해 조건부 적용. 기본 OFF → 예측 확률이 실제
  base rate에 가깝게 유지됨 (logloss 최적화 목적에 부합).
- GPU fallback 경로(cpu_params)도 동일 처리.
- 필요시 `model_params={"auto_class_weights_enabled": True}`로 켤 수 있음
  (F1/recall 최적화가 목적일 때).

## B. baseline logloss 출력 (training.py)
- `_baseline_logloss(labels)`: 상수(positive rate) 예측의 logloss. 검증:
  50/50→0.6931(ln2), 30/70→0.6109 (문서 예시값과 일치).
- Optuna 튜닝 로그에 `baseline=`, `improvement=`, `pos_rate=`, 개선폭 등급
  (no/weak/meaningful/strong) 출력.
- `_tune_catboost_with_optuna`의 report에 `baseline_logloss`,
  `improvement_over_baseline`, `positive_rate` 필드 추가.

## C. regime별 validation 재설계 (사용자 지시 반영)
기존 문제: `_run_user_regime_training`이 2025 H1을 "held-out validation"으로
쓰면서, 그 전체(2025 H1 up+down+range 섞인 것)로 up/long 모델도, down/short
모델도 다 평가 → 왜곡된 F1.

**재설계**: 옛 cross-regime test_period 평가를 완전히 제거. 대신:
- `_train_single_regime`이 각 regime의 최종 모델을 **그 regime 자신의 학습
  데이터 중 시간순 뒤 20%(holdout)**로, **그 regime의 target(long_success/
  short_success)에 대해서만** 평가. 다른 regime 데이터 섞임 없음.
- purge gap(label_horizon)을 학습부와 holdout 사이에 둠 (라벨 누설 방지).
- `run_summary["mean_test_f1"]`이 이제 진짜 값 (이전엔 0.0 하드코딩 — 지난
  세션에 발견했던 "Test F1: 0.0000" 표시 버그의 근본 원인이었음, 자동 해결됨).
- `regime_holdout_metrics`를 run_summary에 기록 (side별 F1/Acc/baseline_logloss
  /positive_rate/n_holdout).

**날짜 재구성** (사용자 지시): 2025 H1을 "held-out validation"으로 쓰던 것을
제거하고, 검증은 학습 데이터 내부 split으로 대체했으므로 2025년 전체를
진짜 out-of-sample 백테스트로 사용. `run_full_pipeline.ps1/.sh`:
- `TRAINING_END=2024-12-31` (불변)
- ~~`VALIDATION_START/END`~~ 제거
- `BACKTEST_START=2025-01-01` (기존 07-01에서 변경), `BACKTEST_END=2025-12-31`
- train 명령에서 `--test-start/--test-end` 제거

## D. 날짜 end-exclusive 파싱 (cli.py)
- `_parse_end_date_exclusive()`: 날짜만 입력("2024-12-31", len==10)이면
  그날 23:59:59.999999까지로 확장. 시각까지 명시된 입력은 그대로 둠.
- `training_end`, `test_end` 파싱에 적용 (`training_start`/`test_start`는
  시작점이라 원래도 문제없어 불변).
- 검증: "2024-12-31" → 2024-12-31 23:59:59.999999 (그날 전체 포함),
  "2024-12-31T12:00:00" → 그대로 12:00:00 (명시적 시각 존중).

## E. regimes.json gap 메우기
- 4개 gap 확인 후 전부 메움: 직전 period의 end_exclusive를 다음 period의
  start까지 연장 (연말 gap을 직전 추세의 연장으로 간주 — 보수적 선택이며
  해당 특정 일자의 정밀 라벨링은 아님, 필요시 재검토).
- 검증: gap 0개, 전체 범위 2020-01-01~2026-01-01 연속.

## 회귀 검증
- test_core: 원본과 동일 (errors=7, 전부 catboost/pyarrow 환경 문제)
- test_v718: 원본(failures=3, errors=15) 대비 새로 생긴 실패 0개.
  오히려 1개 개선(TestRegimeTraining이 이제 실제로 detector 경로를 태우게
  되면서 catboost 필요해짐 → skipUnless로 명시적 처리, 이전엔 조용히
  아무 것도 학습 안 하고 통과하던 것이 정직해짐).
- TestRegimeTraining 테스트들을 방향 기반(up/down/range)으로 갱신 — 이전엔
  detect_all(강도 기반)을 patch했는데 이제 학습 경로가 detect_all_directional을
  쓰므로 patch가 안 먹혀 실제 계산이 돌아 catboost 필요해짐이 드러남
  (이것도 지난 세션 "detector 경로가 원래 학습을 안 하고 있었다" 버그의 증거).

## 미적용 (신중해야 할 것들)
- **up/down 양방향 모델**: 지금은 up→long만, down→short만. 문서는 양방향+
  임계값 차등을 제안하나, 이건 direction_policy 전체 재설계라 별도 논의 필요.
- **--ensemble을 regime-aware 경로에 적용**: 모델 개수 폭증(regime당 3배) +
  신호 존재가 불확실한 상태에서는 효과가 제한적. gross 플러스 확인 후 재검토.
- **--cv-mode를 regime-aware 경로에 적용**: regime 분할과 fold 분할이 겹쳐
  표본이 지나치게 작아짐. 지금 regime holdout(1-fold)을 향후 walk-forward
  다중 fold로 확장하는 절충안이 낫다고 판단, 미적용.
- **--feature-selection**: 사용자 요청으로 보류.
- **probability calibration (Platt/Isotonic)**: 미구현. class_weights를 끈
  지금은 우선순위가 낮아짐.

## G. --threshold-objective를 regime-aware 경로에 적용 (추가 적용)
문서에는 없던 항목. "다른 flag들이 auto-regime에도 적용되는가"라는 질문에서
출발해 ensemble/cv-mode/threshold-objective 셋을 검토, threshold-objective만
현재 구조와 상충 없이 적용 가능하다고 판단해 추가.

### 문제
`_train_single_regime`의 regime holdout 평가가 고정 임계값 0.5로 F1/Acc를
계산하고 있었음. 0.5는 임의의 값 — 실제로 거래해 이득이 나는 확률 지점이
0.5라는 보장이 없음. 기존 비-regime 학습 경로에는 이미 `select_threshold()`
(precision_recall / trading_pnl 두 objective 지원)가 있었지만 regime-aware
경로에는 연결되어 있지 않았음.

### 수정 (training.py `_train_single_regime`)
- regime holdout에서 예측 확률을 얻은 뒤, **그 holdout 위에서**
  `select_threshold(probs, holdout_labels, objective=training_config.threshold_objective, min_trades=training_config.threshold_min_trades)`
  로 임계값을 선정 (학습 데이터가 아니라 holdout으로 골라야 과적합 없음).
- 그 임계값으로 holdout 지표(F1/Acc 등)를 재계산.
- `run_summary["selected_thresholds"]` = `{"long": 0.xx, "short": 0.xx}`,
  `run_summary["threshold_objective"]`를 기록.
- user-regime 경로(_run_user_regime_training)와 detector 경로(auto-regime)가
  둘 다 동일한 `_train_single_regime`을 호출하므로 **자동으로 양쪽 다 적용됨**
  (질문의 답: 그렇다, 동일하게 적용된다).

### CLI (cli.py)
- `--use-user-regime` 사용 시 뜨던 "ignored flags" 경고 목록에서
  `--threshold-objective`를 제거 (이제 무시되지 않고 실제로 쓰이므로).

### 파이프라인 (run_full_pipeline.ps1/.sh)
- `$ThresholdObjective` / `THRESHOLD_OBJECTIVE` 설정 변수 추가 (기본
  `precision_recall`). Phase 3a/3b 둘 다 `--threshold-objective`로 전달.
- `trading_pnl`은 calmar/sharpe/f1 기반이라 실전 손익에 더 가깝지만, 분류
  균형과는 다른 기준이라 기본값은 안전한 `precision_recall`로 둠. 필요시
  환경변수로 전환 가능.

### 아직 안 한 것 (범위 밖)
- **백테스트/라이브가 이 selected_threshold를 실제로 읽어 쓰지는 않음.**
  지금은 학습 단계에서 "이 regime/side에 최적인 임계값이 얼마인지 찾아서
  기록"하는 것까지. `live.py`의 `StrategyConfig.long_threshold/short_threshold`
  는 여전히 `RegimeStrategyProfile`의 하드코딩된 값(0.45~0.55)을 씀. 이 둘을
  연결하는 건 백테스트/라이브 경로까지 건드리는 별도 작업이라 미룸 — 필요시
  다음 단계로 진행.

### 검증
- `select_threshold` 자체 mock 검증 (precision_recall/trading_pnl 둘 다
  유효 범위 threshold 반환).
- `_train_single_regime` end-to-end mock 검증: trading_pnl → threshold
  0.2129 선정, run_summary에 정확히 기록; precision_recall(기본값) →
  다른 threshold(0.605) 선정, 기본값 정상 동작.
- CLI 파싱 확인 (`--threshold-objective trading_pnl` 정상 인식).
- test_core/test_v718 회귀 없음 (원본과 동일한 실패 패턴).

## F. Optuna 탐색 공간 확장 + eval_set 기반 early stopping (추가 적용)
문서 11번 항목. IC 진단은 일단 보류하고 이것부터 적용.

### CatBoostAdapter.fit()에 eval_set/use_best_model 추가 (models.py)
- 기존엔 `DEFAULT_PARAMS`에 `od_type: Iter, od_wait: 50`이 있었지만 eval_set을
  한 번도 넘긴 적이 없어서 **완전히 무효(silent no-op)**였음. CatBoost의 early
  stopping은 eval_set 없이는 작동하지 않음.
- `fit(feature_matrix, labels, sample_weight=None, eval_set=None, use_best_model=False)`
  로 시그니처 확장. 위치 인자는 그대로라 기존 호출부(eval_set 없이 쓰던 곳)
  전부 하위호환 유지 (mock으로 검증).
- GPU 실패 시 CPU 폴백 경로도 동일하게 eval_set 지원.

### 탐색 공간 확장 (training.py `_tune_catboost_with_optuna`)
| 파라미터 | 기존 | 확장 후 |
|---|---|---|
| iterations | 200~800 | 300~2000 |
| learning_rate | 0.01~0.1 | 0.005~0.08 |
| depth | 4~10 | 3~8 |
| l2_leaf_reg | 1~10 | 1~50 |
| random_strength | (없음) | 0.1~10 (신규) |
| bagging_temperature | (없음) | 0~5 (신규) |
| min_data_in_leaf | (없음) | 20~500 (신규) |
| border_count | (없음) | 64~254 (신규) |

(`rsm`은 GPU에서 지원 문제가 있어 사용자 지시로 탐색 공간에서 제외.)

- `od_wait`을 각 trial의 `iterations`에 비례해 동적 설정
  (`max(30, iterations // 10)`) — 큰 iterations trial엔 널널하게, 작은 trial엔
  타이트하게.
- objective가 `adapter.fit(train_x, train_y, eval_set=(val_x, val_y),
  use_best_model=True)`로 호출 → early stopping 실제 작동, val 성능 기준
  최적 iteration으로 롤백.

### trial 수 증가 (run_full_pipeline.ps1/.sh)
- `--optuna-trials 30` → `100` (Phase 3a, 3b 둘 다).
- **주의**: 탐색 차원이 4개→9개로 늘고 trial도 30→100이 되어, regime×side
  (최대 4)×모델(2, user+auto) = 최대 8곳에서 각각 튜닝 시간이 크게 증가.
  전체 파이프라인 시간이 상당히 늘어날 것으로 예상됨 (체감 3~5배 이상 가능).

### 검증
- optuna 미설치 환경(이 컨테이너)에서 안전 폴백 확인: `optuna_available:
  False`, 기존 기본 파라미터 사용 — 새 코드가 optuna 없을 때도 안 깨짐.
- od_wait 스케일링 계산 검증 (300→30, 800→80, 2000→200).
- mock CatBoost로 eval_set/use_best_model이 실제 `catboost.fit()`에
  정확히 전달됨을 확인.
- eval_set 없이 기존 방식으로 호출하는 하위호환 케이스도 정상 작동 확인.
- test_core/test_v718 회귀 없음 (원본과 동일한 실패 패턴).
