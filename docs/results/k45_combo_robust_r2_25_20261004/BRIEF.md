Repo: D:\StudyQuant. R2-25: 단일 포지션 조합(C1·C3·C4·C5) 강건성 검사. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고. 판정보다 숫자를 먼저.
동시에 다른 Codex 작업(데이터 수집, 네트워크 위주)이 돈다. CPU 워커 최대 10.

# 규칙
- 단일 포지션(동시 보유 1개, 롱·숏 동시 금지). 엔진은 R2-24 그대로 import(out/k45_single_book_combo_r2_24_20261004 의 코드), 충돌 규칙 FIRST.
- 펀딩 out/k45_funding.py PESS/OPT, 원장 out/k45_ledger.py, PW 자동 블록, DSR. 구간 DEV_COMMON 2021-03-01~2025-12-31 (1차), HOLD_B(이미 본 구간, 판정 미사용).
- 재학습 금지. 이미 있는 산출물만 쓴다.
- 먼저 재현: C1·C3·C4·C5 FIRST가 R2-24 값과 같은지.

# 교란 축 (전부 보고, 선택하지 마라)
1. 규칙 파라미터 이웃 — F3: R2-17 산출물(out/k45_funding_fix_20261004/r2_17_PESS, r2_17_OPT 의 거래 생성 규칙)에서 global_ls_account, 1h, 분위 창 {60, 90, 180}일 × 극단 {5, 10, 15}% × 보유 {12, 24, 48}h, LS. E1: z ∈ {2, 2.5, 3} (2.5는 R2-14 함수로 새로 계산, 학습 없음), 1h, L.
   → 이웃 F3 27칸 × E1 3칸 = 81개 C1형 조합. 각 조합의 F3 단독 대비 Sharpe 차이·낙폭 차이·PW 하한 분포(최소·중앙·최대), "Sharpe 상승 & 낙폭 감소" 비율.
2. 모델 교란 — C3의 R2-9b 칸: R2-9b 변형 V0~V6 예측(out/k45_gate_direction_r2_9b_20261002)을 각각 넣은 7개 C3. R2-20 칸: R2-16의 expanding 창 3시드 예측(out/k45_train_window_r2_16_20261002)을 쓸 수 있으면 3개 시드로 바꿔 넣는다(없으면 없다고 보고).
3. 비용 0/4/8/12 bps — C1·C3·C4·C5.
4. 기간 분할 — 연도별(2021~2025), 반기별 net·Sharpe, 조합 vs F3 단독 승패 수.
5. 진입 지연 — 모든 진입을 +1분, +5분 늦춰(청산 규칙 동일) C1·C3 재계산(실행 지연 민감도).

# 동결 가설
"C1형 81개 이웃 조합 중 70% 이상에서 조합 Sharpe가 해당 F3 단독보다 높고 최대 낙폭이 같거나 작다(DEV_COMMON, PESS·OPT 각각)."

# 출력
out/k45_combo_robust_r2_25_20261004/ (REPORT.md 숫자만, 5,000줄 이하; parquet; manifest.json SHA256·시각·cutoff·동결 가설).
테스트: tests/test_k45_combo_robust_r2_25.py (TDD): (i) 포지션 ≤1, (ii) R2-24 재현, (iii) 지연 진입이 미래 데이터 미사용, (iv) z=2.5 신호가 R2-14 함수 정의와 같음, (v) 모델 교란 칸이 해당 변형 예측만 사용.
제약: 로컬 데이터만(이 작업은 다운로드 없음), live 0, git commit 금지, HOLD_A·2026-07 이후 금지, cutoff 2026-06-30 23:59 UTC.
Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 재현, 축별 요약, 가설 판정(PESS/OPT), 테스트 마지막 줄, 소요 시간.
