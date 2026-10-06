Repo: D:\StudyQuant. R2-9: 크기 반영 모델(회귀·크기가중)의 극단 꼬리를 단일 포지션 + "더 높은 확률(점수) 쪽" 규칙으로 묶은 전략. 재학습 없이 기존 예측으로 계산. 설계·구현·실행·보고 끝까지, 결과로 거르지 마라.

# 사용자 확정 조건
- book은 단일 포지션만. 동시 보유 ≤ 1. 한 바에서 한 방향만.
- 보유 중 들어온 신호는 버림(선착순). 버린 신호 수·사후 r_h 평균 보고.

# 입력(불변)
- out/k45_gate_direction_audit_20261001/c4_predictions.parquet (regression_rmse score=ŷ, weighted_multiclass score=p_long−p_short)
- out/k45_gate_direction_r2_7_20261001/ 의 인과 기준 코드·thresholds.parquet (확장형, 최근 180일) — 재사용, 기준 정의를 바꾸지 마라
- artifacts/btcusdt_2020_2026h1.parquet, 펀딩 artifacts/funding_2020_2026h1
재사용: R2-6/R2-7/R2-8 코드(펀딩, 대체 CI, 무작위 기준선, 단일 book).

# 신호 규칙
- 기준 방식 M ∈ {EXPANDING_OOS, ROLLING_180D} (R2-7 정의 그대로, 과거 점수만), q ∈ {1%, 2%}.
- 모델 조합 S:
  REG: 회귀 점수만. score ≥ 상단 기준 → 롱, ≤ 하단 기준 → 숏.
  WGT: 크기가중 점수만. 같은 규칙.
  AGREE: 두 모델이 같은 방향 꼬리에 동시에 있을 때만 그 방향.
  EITHER: 둘 중 하나라도 꼬리면 거래. 두 모델이 반대 방향이면 거래 안 함. 같은 바에서 둘 다 같은 방향이면 1건.
- 보유: 롱 h_L ∈ {45, 120, 240}, 숏 h_S ∈ {15, 45, 60}. 점유 시간 = 그 거래의 h.

# PRIMARY 선정 (기계적, DEV만 사용)
- h_L = h_S = 45 인 칸들(S × M × q = 16칸) 중 **DEV 단일 포지션 net이 가장 큰 칸** 하나를 PRIMARY로 자동 선정.
  선정 근거 표를 남겨라. HOLD_B는 이 선정에 쓰지 않는다.
- PRIMARY 동결 가설: "선정된 칸의 HOLD_B 단일 포지션 net이 0보다 크다". HOLD_B는 이미 일부 열람됐으므로 탐색(exploratory) 표기.

# 보고 (DEV / HOLD_B 분리)
1. 전 칸(S × M × q × h_L × h_S): n, 롱 n·net, 숏 n·net, 전체 net, 상위 1/2/5건 제거 net, 적중률, PW + 대체 CI, 월별 양수 비율.
2. PRIMARY 상세: 연도별 n·net, 거래일 수, 상위 5일 PnL 비중, 수익 상위 10건(시각, 방향, |r_h|, 그날 일중 범위), HOLD_B 월별 표.
3. 기준선(같은 진입 바·같은 보유): 방향 반대, 무작위 ±1 1,000회 분포 백분위(seed 20261001), 항상 롱.
4. 크기 효과 vs 방향 효과: 신호 바 |r_h| 배율, 적중률.
5. 펀딩 합계.

# 제약
- 로컬 데이터만. 다운로드·재학습 금지. live 0. git commit 금지.
- 출력: out/k45_gate_direction_r2_9_20261001/ (REPORT.md 숫자만, 해석 형용사 금지; 표별 parquet; manifest.json 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설).
- 테스트: tests/test_k45_gate_direction_r2_9.py (TDD). (i) 동시 보유 ≤1, (ii) 한 바 한 방향, (iii) 기준이 미래 점수를 안 씀, (iv) PRIMARY 선정이 HOLD_B 값을 읽지 않음.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: PRIMARY 선정 표와 결과(DEV/HOLD_B), 전 칸 요약(h=45/45), 기준선 비교, 테스트 마지막 줄.

# 추가 (사용자 지시 2026-10-01): R2-10 재학습 모델 포함
R2-9는 R2-10이 끝난 뒤 실행한다. 입력에 R2-10 산출물(out/k45_gate_direction_r2_10b_20261001/ (180분 포함; R2-10b가 R2-10 산출물을 모두 포함), manifest 확인)을 추가한다.
- 추가 신호원(모두 같은 꼬리·단일 포지션·한 방향 규칙, 같은 인과 기준 M × q):
  SIDE_h: R2-1/R2-10 팔별 모델. 롱 점수 = p_long(h) − p*_long(h), 숏 점수 = p_short(h) − p*_short(h), h ∈ {5,15,30,45,60,90,120,180,240}.
    롱 꼬리 = 롱 점수 상위 q, 숏 꼬리 = 숏 점수 상위 q (각 점수의 과거 분포 기준). 같은 바에서 둘 다 꼬리면 (점수 − 기준)이 큰 쪽 하나.
  RESIDUAL_h: R2-3/R2-10 잔차 3분류, score = p_long − p_short, h ∈ {5,15,45,60,120,180,240}.
- 보유 시간 = 그 모델의 라벨 h (롱 h_L, 숏 h_S 각각). SIDE는 롱 h_L × 숏 h_S 81조합, RESIDUAL은 롱 {45,120,240} × 숏 {5,15,60}.
- 기존 REG/WGT/AGREE/EITHER(45분 라벨)는 그대로 유지.
- PRIMARY 자동 선정 범위를 모든 신호원 × 조합으로 넓힌다(DEV 단일 포지션 net 최대, HOLD_B 미사용). 칸 수를 보고하고, 선정값의 다중검정 보정(Bonferroni 칸 수, DEV PW p)을 함께 보고.
- 이전 실행이 중단됐다. out/run_k45_gate_direction_r2_9.py·tests가 미완성으로 남아 있으면 검토 후 재사용.
