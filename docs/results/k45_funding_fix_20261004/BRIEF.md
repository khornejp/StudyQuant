Repo: D:\StudyQuant. R2-22: 펀딩 손익 오류 교정 + 영향 실험 재실행. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고. 판정보다 숫자를 먼저.

# 근거 (먼저 읽어라)
- out/k45_funding_review_20261004/REPORT.md — R2-14 settlement_events가 정산 T에 아카이브 T−8h 요율을 적용(분 floor 기준 7,118/7,118). 아카이브 calc_time=T 행이 T 정산 요율(프리미엄 공식 상관 0.997).
- out/k45_funding_plan_review_20261004/REPORT.md — 후속 계획 검토와 Codex 권고 순서(아래 1~7은 그 권고를 따른다).

# 1. 공통 펀딩 모듈 (근본 원인 한 곳)
새 파일 out/k45_funding.py:
- load_settlements() -> DataFrame[time (scheduled T, UTC 00/08/16 정각), rate, raw_calc_time]:
  아카이브(artifacts/funding_2020_2026h1/BTCUSDT-fundingRate-*.zip, 열 calc_time|funding_interval_hours|last_funding_rate)를 읽어 calc_time을 가장 가까운 예정 정각으로 정규화. |raw − T| > 60초인 행이 있으면 예외. 7,119행 검증.
- cashflow_bps(side, rate) = −side × rate × 1e4  (양수 = 수취). 이 부호 규약 하나만 쓴다. 기존 R2-6 계열(비용 양수 후 차감)과 R2-14 계열(cashflow 가산)을 이 모듈에서 변환하는 함수도 둔다.
- trade_funding(side, entry_time, exit_time, settlements, boundary) -> (내부 합, 경계 합):
  - 내부 정산: entry_time < T < exit_time — 항상 포함.
  - 경계 정산: T == entry_time 또는 T == exit_time (분 시가 체결이 정산 정각과 같은 분).
  - boundary ∈ {"PESS", "OPT", "INCL"}: PESS = 경계 cashflow 중 음수만 포함, OPT = 양수만 포함, INCL = 기존 규칙(entry < T ≤ exit 전부 포함, 비교용).
- 테스트 tests/test_k45_funding.py (TDD):
  (i) 2021-01-08 00:00 → 0.00213517, 08:00 → 0.00092044 (아카이브 T 요율),
  (ii) 7,119행, 정규화 오차 ≤ 60초,
  (iii) 롱 24h 내부 정산 3회 합 = −Σrate×1e4,
  (iv) 경계 거래: rate>0 롱 exit=T → PESS 포함(−), OPT 제외; rate<0 롱 exit=T → PESS 제외, OPT 포함(+),
  (v) R2-6 규약 변환 왕복이 같은 값.

# 2. R2-14 재실행
- out/run_k45_classic_rules_r2_14.py 의 settlement_events / _funding_bps 가 out/k45_funding.py 를 쓰도록 바꾼다(호출부 시그니처 유지). 기존 테스트 중 "직전 분 요율"을 고정한 것은 새 정의로 고치고 무엇을 바꿨는지 보고.
- 출력 폴더 인자(환경변수 K45_OUT_ROOT 등)를 추가해 out/k45_funding_fix_20261004/r2_14_{PESS,OPT}/ 에 쓴다. 기존 out/k45_classic_rules_r2_14_20261002 는 덮어쓰지 마라.
- PESS와 OPT 두 번 전체 실행. INCL은 칸별 펀딩 합만 계산(전체 재실행 불필요).

# 3. R2-15 재학습
- 새 R2-14(PESS) 결과로 대상 칸을 원 규칙대로 다시 고른다. 원래 대상과 다르면 둘 다 보고.
- 라벨(net>0)·피처를 새 펀딩으로 다시 만든다. 학습 2벌: (a) 원 피처, (b) next_funding_rate 제거(funding_rate와 완전 중복). 
- G2 signal strength가 next_funding_rate를 쓰면 funding_rate로 바꾸고 그 사실을 기록(값 동일).
- 출력 out/k45_funding_fix_20261004/r2_15_{full,no_next}/. OPT는 대상·라벨이 PESS와 같으면 생략하고 같음을 보고, 다르면 실행.

# 4. R2-17, R2-18 재실행
- 새 모듈로 PESS/OPT 각각. 출력 r2_17_{PESS,OPT}/, r2_18_{PESS,OPT}/. R2-18 selected_cells는 원 규칙으로 다시 고르고 원래와 다르면 둘 다 보고.

# 5. R2-19 재실행
- 후보 목록을 원 계획서(docs/superpowers/plans/2026-10-03-validation-integrity-r2-19.md Task 6) 동결 목록 그대로 유지. 새 펀딩(PESS/OPT)으로 다시 계산. 출력 r2_19_{PESS,OPT}/.
- R2-14 계열 대표가 바뀐 계열(D1 등)은 표에 표시.

# 6. 초기 실험 손익 재계산 (모델·신호 고정)
- out/k45_gate_direction_20261001, out/k45_gate_direction_r2_20261001, out/k45_trend_side_20261001, out/k45_trend_side_tp_20261001 의 거래(또는 out/k45_funding_plan_review_20261004 에서 재구성한 원장)에 새 펀딩을 붙여 결과 표를 다시 만든다. 출력 early_reprice/.
- 칸별 전/후 net, 부호·순위 변화.

# 7. R2-20, R2-21 확인만
- 입력 SHA와 펀딩 경로(r26 archive raw ms) 확인. 새 모듈(scheduled T, PESS/OPT)로 칸별 펀딩 합을 다시 계산해 차이만 표로. 재실행 안 함.

# 판정 규칙
- 모든 비교는 PESS와 OPT를 나란히. 두 값의 결론(부호, 가설 통과 여부, 대표 칸)이 같을 때만 "확정", 다르면 "경계 의존"으로 표기.
- 동결 가설·선택 규칙·격자는 각 원 실험 BRIEF.md 그대로.

# 보고
out/k45_funding_fix_20261004/REPORT.md (숫자만, 해석 형용사 금지, 5,000줄 이하) — 맨 앞:
(a) 모듈 테스트 결과, (b) 실험별 수정 전 / PESS / OPT 요약(칸 수, net 차이 분포, 부호 바뀐 칸 수·목록, 대표·선택 칸 변화, 가설 판정), (c) R2-15 full vs no_next, (d) 초기 실험 재계산, (e) R2-20/21 차이, (f) "확정" vs "경계 의존" 목록.
manifest.json: 입력·출력·소스 SHA256, 시각, 각 단계 소요 시간.

# 제약
- 로컬 데이터만. 다운로드 금지. live 0. git commit 금지. HOLD_A·2026-07 이후 금지. cutoff 2026-06-30 23:59 UTC.
- 기존 결과 폴더 덮어쓰기 금지. 기존 모델 산출물(PatchTST·CatBoost 예측) 재사용, 재학습은 R2-15만.
- CPU 워커 최대 12. 단계마다 run.log 기록, 체크포인트로 재개 가능.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 단계별 테스트·재실행 결과 요약, 확정/경계 의존 목록, 소요 시간.
