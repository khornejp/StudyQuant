Repo: D:\StudyQuant. R2-23: 후보 최종 비교 — 같은 엔진·같은 기간·같은 지표로 한 표에. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고. 판정 문구보다 숫자를 먼저.

# 목적
지금까지 후보들은 실험마다 계산 방식(일별 수익 정의, 펀딩, 신뢰구간, 기간)이 달라 나란히 비교할 수 없다. 같은 엔진으로 다시 계산해 한 표에 놓는다. 승자 선택이 아니라 비교표가 산출물이다.

# 엔진 (재사용, 복제 금지)
- 펀딩: out/k45_funding.py (아카이브, 예정 정각, cashflow 부호, 경계 PESS/OPT). 모든 표를 PESS와 OPT 두 값으로.
- 평가손익 원장·구간 경계 분할·사건 묶음·DSR: out/k45_ledger.py.
- PW 자동 블록 CI: out/k45_ledger.pw_mean_ci (블록 < 1이면 MEASURABLE_BLOCK1).
- 거래 생성은 각 후보의 원 실험 코드를 import (R2-14/R2-17 규칙 함수, R2-9 꼬리, R2-12/R2-20 예측, R2-15 메타 필터, R2-18 조합). 재학습 금지 — 단, R2-15 메타 필터는 R2-22에서 새 펀딩으로 재학습된 산출물(out/k45_funding_fix_20261004/r2_15_full, r2_15_OPT_full)을 쓴다.
- 먼저 재현 확인: 각 후보의 "원 실험(R2-22 재실행본이 있으면 그것)" 거래 수·net 합과 이 엔진 결과가 같은지(펀딩 동일 조건). 불일치면 그 후보는 표에 남기되 불일치 표시하고 원인 보고.

# 동결 후보 목록 (실행 전에 manifest에 기록. 결과 보고 바꾸지 마라)
1. F3|1h|10/24|signal|LS (R2-14 대표)
2. F3|1h|5/24|signal|LS (R2-14 인접)
3. R2-17 F3_global_ls_account 계열에서 DEV 일별 Sharpe 최대 LS 칸 (R2-22 PESS 재실행본 기준, DEV만으로 선택)
4. E1|1h|3|signal|L
5. E1|1h|2|signal|L
6. E1|1h|3|signal|L + R2-15 메타 필터 catboost base (R2-22 재학습본; PESS 기준 산출물로 PESS 표, OPT 산출물로 OPT 표)
7. A3|4h|720|signal|LS
8. F1|1h|5/24|signal|LS
9. R2-9b 선택 칸 SIDE|ROLLING_180D|q=0.01|L=120|S=60 (V0 고정 모델 예측)
10. R2-20 칸 중 q ≤ 2%에서 DEV PW CI 하한 최대 칸 (R2-22 이후 재실행본 out/k45_funding_rerun_r2_20_21_20261004/r2_20_PESS 기준, DEV만으로 선택)
11. R2-18 COMBO_SINGLE STOP (롱 R-TAIL q=0.01 EXPANDING_OOS L + 숏 R-F3 tail=10 S)
12. 바이앤홀드
선택 규칙이 있는 3, 10은 선택 결과를 manifest에 먼저 쓰고 SHA256을 남긴 뒤 나머지를 계산.

# 기간
- DEV_COMMON: 2021-03-01 ~ 2025-12-31 (모델 기반 후보의 예측이 2021-02부터라 공통 구간). 1차 비교 구간.
- DEV_FULL: 각 후보의 원 DEV(규칙 기반은 2020-07-01부터).
- HOLD_B: 2026-01-01 ~ 2026-06-30 — 모든 후보 선택에 이미 쓰인 구간이라 "이미 본 구간"으로 표기, 비교에는 넣되 판정에 쓰지 않음.
- 구간 경계를 넘는 거래는 원장에서 평가가격으로 분할.

# 지표 (후보 × 구간 × PESS/OPT, 비용 4 bps 기본)
- 거래 수, 노출 비율, 평균·중앙 보유시간, 롱/숏 분리 n·net.
- 총 net, 거래당 net, 평가손익 일별 Sharpe, 평가손익 최대 낙폭, 최악 1일, 최장 무수익 기간, 연도별 net.
- PW 자동 블록 평균 CI(일별), p.
- DSR: 시도 수 2가지 — 813(R2-14), 누적(out/k45_validation_r2_19_20261003 trial_counts의 4,707에 R2-20 120, R2-21 144, R2-22·R2-23 재실행은 새 시도로 세지 않음 → 4,971). trial Sharpe 분산은 R2-14 all_cells DEV 기준.
- 집중도: 상위 1/2/5 거래, 사건(24h 간격 묶음), 날짜, 주 단위 제외 후 총 net.
- 비용 0/4/8/12 bps 재계산.
- 같은 거래 수·보유시간 분포·방향 비율의 무작위 진입 1,000회 백분위.
- 후보 간 일별 평가손익 상관 행렬(DEV_COMMON, PESS) — 다음 단계(단일 계좌 결합) 준비용.

# 순위표 (사전 고정)
DEV_COMMON, PESS 기준으로 아래 각 지표별 순위를 나란히 보고(합산 점수 만들지 마라): PW CI 하한, 평가손익 Sharpe, 사건 상위 5개 제외 총 net, 비용 12 bps 총 net, 최대 낙폭(작을수록 위). OPT에서 순위가 달라지는 곳 표시.

# 제약
- 로컬 데이터만. 다운로드 금지. live 0. git commit 금지. HOLD_A·2026-07 이후 금지. cutoff 2026-06-30 23:59 UTC. 재학습 금지(R2-15 재학습본 사용).
- CPU 워커 최대 12.
- 출력: out/k45_candidate_compare_r2_23_20261004/ (REPORT.md 숫자만, 해석 형용사 금지, 5,000줄 이하; parquet; manifest.json 입력·출력·소스 SHA256, 시각, cutoff, 동결 후보·선택 결과).
- REPORT 앞부분: 재현 확인 → 후보 × DEV_COMMON 요약표(PESS, OPT) → 순위표 → HOLD_B(이미 본 구간) 표 → 상관 행렬.
- 테스트: tests/test_k45_candidate_compare_r2_23.py (TDD). (i) 선택 규칙 3·10이 DEV만 읽음(HOLD_B 미사용), (ii) DEV_COMMON 경계 분할, (iii) 동시 보유 ≤1(조합 포함), (iv) PESS/OPT가 같은 거래 집합에서 펀딩만 다름, (v) 재현 확인 로직.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 재현 확인, 후보 요약표(DEV_COMMON PESS/OPT), 순위표, 테스트 마지막 줄, 소요 시간.
