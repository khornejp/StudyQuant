Repo: D:\StudyQuant. R2-10: 보유 시간에 맞춘 재학습 + R2-8 단일 포지션 그리드 재실행. 설계·구현·실행·보고 끝까지, 결과로 거르지 마라.

# 문제
R2-8에서 R2-1 팔별 모델은 보유 시간과 라벨 시간이 안 맞았다(롱 120/240 → h60 모델, 숏 60 → h45 모델).
3분류·잔차(RESIDUAL) 모델은 모두 45분 라벨로만 학습됐는데 롱 120/240, 숏 5/15/60으로 보유했다.

# 재학습 (walk-forward 규칙·CatBoost 고정 파라미터·피처 후보·in-window 선택 모두 기존과 동일, 라벨 시간 h만 바꿈)
재사용: out/run_k45_gate_direction_walkforward.py, out/run_k45_gate_direction_r2.py(또는 R2-1/R2-3 구현 위치, manifest 확인), out/k45_gate_direction.py.
1. R2-1 팔별 binary 모델: 롱·숏 모두 h ∈ {5, 15, 30, 45, 60, 90, 120, 240} (사용자 지정). 타깃 롱 1[r_h > +4], 숏 1[r_h < −4]. p*는 그 fold train에서 같은 h로 계산.
   기존 결과 재사용: 롱 h15/h45/h60, 숏 h5/h15/h45 (out/k45_gate_direction_r2_20261001/). 새로 학습: 롱 h5/30/90/120/240, 숏 h30/60/90/120/240 (10개).
2. RESIDUAL 3분류(R2-3 잔차 버전) 라벨 h ∈ {5, 15, 60, 120, 240}. 라벨: r_h > +4 LONG, < −4 SHORT, else NONE.
   (h=45는 기존 R2-3 결과 재사용.)
- purge: train = signal_index + h < stop_start_index (h에 맞게).
- r_h 가 fold TEST 끝 또는 데이터 끝을 넘는 TEST 바는 평가에서 제외하고 수를 기록.
- 병렬 실행 허용(프로세스 여러 개). 진행 로그: run.log (모델, h, fold, 경과초).

# R2-8 그리드 재실행 (단일 포지션, 한 바 한 방향, 보유 중 신호 버림 — R2-8 코드 재사용)
- 보유 조합: R2_1_MATCHED는 롱 h_L × 숏 h_S 모두 {5, 15, 30, 45, 60, 90, 120, 240} (64조합).
  RESIDUAL_MATCHED는 잔차 모델이 있는 h만: 롱 {45, 120, 240} × 숏 {5, 15, 60} (9조합).
- 규칙:
  RESIDUAL_MATCHED: 롱 방향 판단은 h_L 라벨 잔차 모델의 p_long−p_short, 숏 방향 판단은 h_S 라벨 잔차 모델의 p_short−p_long.
    한 바에서 롱 점수 = p_long(h_L) − p_short(h_L), 숏 점수 = p_short(h_S) − p_long(h_S). margin m을 넘는 쪽 중 큰 쪽 하나. 
    m: 고정 {0.10, 0.20}, 인과(R2-8 RESIDUAL_CAUSAL_M020_RATE와 같은 정의, 각 h 모델 점수의 과거 분포로).
  R2_1_MATCHED: 롱 edge = p_long(h_L) − p*_long(h_L), 숏 edge = p_short(h_S) − p*_short(h_S). 큰 쪽(>0).
  비교용: R2-8의 RESIDUAL_CAUSAL_M020_RATE, R2_1_PSTAR(불일치 버전) 결과를 같은 표에 그대로.
- 보고(DEV/HOLD_B 분리, HOLD_B 탐색 표기): n, 롱 n·net, 숏 n·net, net, 상위 1/2/5건 제거, 적중률, PW+대체 CI, 월별 양수 비율, 연도별,
  기준선(반대 방향, 무작위 1,000회 백분위, 항상 롱), 버린 신호, 펀딩.
- 추가로 각 재학습 모델의 확률 품질: score Spearman vs r_h, 월 일치(monthly_sign_test), 십분위.

# 제약
- 로컬 데이터만. 다운로드 금지. PatchTST 재학습 금지. live 0. git commit 금지.
- 출력: out/k45_gate_direction_r2_10_20261001/ (REPORT.md 숫자만, 해석 형용사 금지; 표별 parquet; manifest.json 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설
  "보유 시간에 맞춰 학습한 모델로 단일 포지션 한 방향 규칙을 쓰면 DEV와 HOLD_B net이 모두 0보다 크다").
- 테스트: tests/test_k45_gate_direction_r2_10.py (TDD). purge가 h를 따른다, 라벨 h가 보유 h와 일치한다, 동시 보유 ≤1.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 재학습 모델 품질 표, 그리드 표(DEV/HOLD_B), 불일치 버전 대비 차이, 테스트 마지막 줄, 소요 시간.

# 참고
이전 실행이 시작 직후 중단됐다. 남은 파일이 있으면 검토 후 재사용 또는 덮어써라. 지금 R2-9 Codex가 동시에 돌고 있으니 R2-9 파일은 건드리지 마라.
