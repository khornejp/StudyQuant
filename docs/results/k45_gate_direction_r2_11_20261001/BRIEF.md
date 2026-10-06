Repo: D:\StudyQuant. R2-11: CatBoost를 fold별 STOP 구간으로 튜닝. 설계·구현·실행·보고 끝까지, 결과로 거르지 마라.
실행 순서: R2-10 → R2-9 → **R2-11**. R2-9가 끝난 뒤 시작한다.

# 배경
각 fold는 TRAIN 180일 / STOP 3일 / TEST 3일. 지금 CatBoost는 TRAIN만 쓰고 STOP을 버린다. 반복 500회·depth 4·lr 0.05·l2 3 고정.
PatchTST는 STOP을 early stopping과 q90 게이트 기준에 쓴다. CatBoost도 STOP을 검증용으로 쓰게 한다. TEST는 어떤 결정에도 쓰지 않는다.

# 튜닝 규칙 (fold마다, 인과)
- train = signal_index + h < stop_start_index (기존과 동일). val = 그 fold STOP 구간의 게이트 통과 바 중 signal_index + h < test_start_index.
  val 행 < 30이면 그 fold는 고정 파라미터로 대체하고 기록.
- 격자: depth {4, 6} × learning_rate {0.03, 0.1} × l2_leaf_reg {3, 10} = 8조합. iterations 최대 2000, early_stopping_rounds 100 (val 손실).
- val 손실(MultiClass/Logloss)이 가장 낮은 조합과 그 best iteration을 고른 뒤, **train만으로** 그 설정으로 다시 학습하지 말고 그 모델 그대로 TEST 예측
  (재학습 시 best iteration 의미가 바뀜). 선택 조합·best iteration·val 손실을 fold별로 저장.
- 피처 선택은 기존처럼 train 행만.
- random_seed 20261001 고정, CPU (기존 결과와 비교 가능하게).

# 대상 모델 (각각 고정 파라미터 버전과 1:1 비교)
1. 잔차 3분류(RESIDUAL) h ∈ {5, 15, 30, 45, 60, 90, 120, 180, 240} (R2-10/R2-10b 산출물 기준)
2. R2-1/R2-10 팔별 모델: 롱·숏 h ∈ {5, 15, 30, 45, 60, 90, 120, 180, 240}
   C(꼬리)에서 R2-9가 빠뜨린 residual long-180 조합도 포함한다.
3. 3분류 원본 h=45, 회귀(RMSE) h=45, 크기가중 h=45
병렬 실행 허용. 진행 로그 run.log(모델, h, fold, 선택 조합, best_iter, val_loss, 경과초).

# 평가 순서 (전부 보고, 판정으로 멈추지 않음)
A. 확률 품질(백테스트 전): score Spearman vs r_h, monthly_sign_test, 십분위, 보정표 — 튜닝 vs 고정, DEV/HOLD_B.
B. 단일 포지션 그리드: R2-8/R2-10과 같은 규칙(RESIDUAL m 고정·인과, R2_1 edge, 팔별 보유)을 튜닝 모델로 재실행. 고정 버전 결과를 같은 표에 나란히.
C. R2-9의 꼬리 규칙(REG/WGT/SIDE/RESIDUAL, 인과 기준 M × q)을 튜닝 모델로 재실행.
D. 기준선: 반대 방향, 무작위 1,000회 백분위, 항상 롱. 상위 1/2/5건 제거, 연도별, 월별, PW + 대체 CI, 펀딩.
E. 튜닝 진단: fold별 선택 조합 분포, best iteration 분포, val 손실 vs TEST 손실 상관.

# 제약
- 로컬 데이터만. 다운로드·PatchTST 재학습 금지. live 0. git commit 금지. 단일 포지션 결과를 먼저 보고.
- 출력: out/k45_gate_direction_r2_11_20261001/ (REPORT.md 숫자만, 해석 형용사 금지; 표별 parquet; manifest.json 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설
  "STOP 구간으로 fold마다 튜닝하면 고정 파라미터보다 확률 품질과 단일 포지션 net이 모두 높다").
- 테스트: tests/test_k45_gate_direction_r2_11.py (TDD). (i) val이 STOP 구간만, (ii) TEST가 튜닝에 안 쓰임, (iii) val 라벨 창이 TEST 시작을 넘지 않음, (iv) 동시 보유 ≤1.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 튜닝 vs 고정 비교 전 표(품질·그리드·꼬리, DEV/HOLD_B), 튜닝 진단, 테스트 마지막 줄, 소요 시간.
