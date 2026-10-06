Repo: D:\StudyQuant. CatBoost 2라운드. 설계·구현·실행·보고를 끝까지 한다. 결과로 멈추거나 거르지 마라.

입력(불변): out/k45_gate_direction_20261001/dataset.parquet, predictions.parquet, 그리고 감사 out/k45_gate_direction_audit_20261001/AUDIT.md (c4_predictions.parquet 포함).
재사용: out/k45_gate_direction.py (label_45, monthly_sign_test, select_features, predict_proba3), out/run_k45_gate_direction_walkforward.py (train_mask, prepare_feature_frame, fold/stop 규칙),
out/k45_trend_side.py (admit, net_bps, trim_top), out/run_patchtst_k45_flow_inference.py (mean_influence, pw_inference, stationary_bootstrap_errors).

# 고정 조건
- 로컬 데이터만. 다운로드 금지. `--feature-cache` 금지. live 0. PatchTST 재학습 금지.
- 비용 4 bps, 지정가 전제. 진입 close[t]. DEV = fold ≤605, HOLD_B = fold ≥606(탐색 표기).
- CatBoost 파라미터 plan 고정값(MultiClass 대신 binary는 loss_function="Logloss", 나머지 동일). 튜닝 금지.
- walk-forward 규칙은 기존과 동일: 확장형, train = signal_index + h < stop_start_index (h = 그 모델의 보유분), 피처 선택은 train 행만.
- 출력: out/k45_gate_direction_r2_20261001/ 만. git commit 금지. 테스트는 tests/test_k45_gate_direction_r2.py 새 파일(TDD).
- Python: venv_btcusdt\Scripts\python.exe

# R2-1 롱/숏 분리 모델 (주 실험)
- 롱 모델: y = 1[r_h > +4], 숏 모델: y = 1[r_h < −4]. 각자 binary CatBoost, 각자 select_features(타깃은 롱: r_h, 숏: −r_h).
- 주 보유분 h = 45 (두 팔 동일). 보고용 추가: 숏 h ∈ {5, 15}, 롱 h ∈ {15, 60}. 보고용은 판정에 쓰지 않는다.
- 팔별 진입 기준 p* = L / (W + L). W, L은 그 fold의 train 행에서 그 팔의 "y=1일 때 평균 net", "y=0일 때 평균 |net|" (net = 방향 수익 − 4). test 정보 사용 금지.
- 결정: 롱만 p_long > p*_long → 롱. 숏만 → 숏. 둘 다 → (p − p*)가 큰 쪽. 둘 다 아니면 없음.
- 보고: 팔별 n, 적중률, 손익분기 적중률, 맞을 때/틀릴 때 평균, net, 상위 2건 제외, 월별 양수 비율, 연도별, 30일 추세별. 무작위 방향 기준선(seed 20261001, 거래 수 일치).

# R2-2 book 방식 비교 (R2-1 신호, 그리고 기존 3분류 margin 0.10/0.20 신호 모두)
- SINGLE: 기존 단일 포지션 선착순.
- CAP3: 동시 보유 최대 3개, 각 1단위, 선착순.
- ALL: 모든 신호 거래(동시 보유 제한 없음, 각 1단위). 거래당 net 평균과 함께 최대 동시 보유 수, 평균 동시 보유 수를 보고.
- 거래당 net, 일별 합계 PnL(단위 기준)의 평균, PW CI.

# R2-3 fade 직교화 (진단)
- 기존 3분류 walk-forward를 두 변형으로 재실행: (a) 이름에 zscore, bb_, ema_.*ratio, sma_.*ratio, distance_, range_position, return_, momentum_, drawdown_ 를 포함하는 f_ 피처 제외, (b) 같은 피처를 train 행에서 선형회귀한 잔차로 대체(fold마다 train에서 계수 추정, test에 적용).
- Task 4·5와 같은 지표(score Spearman, 월 일치, 십분위, margin 0.10 SINGLE/ALL net).

# R2-4 꼬리 곡선 (보고용)
- 3분류 score, C-4 회귀 score, C-4 가중 score, R2-1 (p_long − p*_long) / (p_short − p*_short) 각각에 대해 상위/하위 1%, 2%, 5%, 10% 바의 방향 gross·net 평균, n. SINGLE과 ALL 둘 다.

# R2-5 PW 복구
- 기존 pw_inference가 UNMEASURABLE이면 원인(0인 날 비율, 거래일 수)을 기록하고, 대체 추론 두 개를 항상 같이 보고:
  (i) 고정 블록 7/14/30일 stationary bootstrap(일별 영향값), (ii) event-time: 거래 순서열에 대해 블록 20/50 거래 stationary bootstrap.
- 모든 R2 표의 net에 이 CI를 붙인다.

# 출력
REPORT.md (모든 표, 숫자 그대로, 해석 형용사 금지), 표별 parquet, manifest.json(입력/출력/소스 SHA256, 시각, cutoff, 각 실험의 동결 가설 문장).
마지막 출력: 실험별 핵심 표(DEV/HOLD_B), 테스트 마지막 줄, 소요 시간.
