Repo: D:\StudyQuant. R2-40 (재시작): 전략 개선 방안 찾기 — 특히 숏. Codex와 논의(설계·진단 단계, 실행 아님).

# 사용자 지적 (최우선 규칙)
"내가 개선할 방법을 찾으라고 했지 이미 실패한 실험을 답습하라고 하지 않았다."
→ 이미 시험한 아이디어를 이름만 바꿔 다시 제안하지 마라. 모든 제안마다 "기존 시험과 무엇이 실제로 다른가"를 표로 증명하라. 차이가 파라미터 미세 조정뿐이면 제안하지 마라.

# 1. 먼저 할 일: 시험 이력 대장 만들기
docs/results/*/ (REPORT.md, BRIEF.md, manifest.json), docs/audit/2026-10-02_k45_experiment_audit.md, out/k45_*/REPORT.md 를 읽어 지금까지 시험한 모든 아이디어를 한 표로: 실험 번호, 아이디어 한 줄, 방향(롱/숏/양방향), 입력 데이터, 결과(통과/실패/채택), 실패 이유. 최소 포함: R2-6~R2-13 gate/direction/mtf 계열, R2-14 고전 규칙 그리드(A~H 계열, L/S/LS), R2-15 메타라벨, R2-16 학습창, R2-17 역추세 강건성, R2-18 리스크 스탑, R2-19 검증, R2-20/21 꼬리·PatchTST updown, R2-23~25 조합, R2-37 판단주기, R2-39 숏 S1–S6·router. 이 대장을 out/k45_short_discovery_r2_40_20261006/tested_ideas.parquet 와 REPORT 맨 앞 표로.

# 2. 진단 (DEV 기술통계, 숫자로)
- 왜 숏이 어려운가: DEV 드리프트(bp/일)×보유시간이 숏에 주는 불리함, 하락 국면 표본 수.
- 현재 수익원 분해: C1 수익이 어떤 조건(LS 수준, 변동성, 시간대, 보유 중 경로)에서 나오고 어디서 잃는가. 손실 거래의 공통점. 진입 후 경로(MAE/MFE)로 본 청산 개선 여지(단, R2-18 스탑 실험과의 차이 명시).
- F3 숏 전용 단일 포지션 장부(롱 신호 무시) 성과: DEV/HOLD_B, 알파·베타·PW·상위 의존. C1 안 숏과 차이.

# 3. 새 개선안 제안 (최대 6개, 숏 우선, C1 개선도 허용)
각 안: 시장 논리(왜 돈이 될 수 있는가), 정확한 사전 등록 정의(입력·임계값·보유·청산), 대장에서 가장 가까운 기존 시험과의 실질 차이, 예상 표본 수(DEV), 실패 시 배울 점. 데이터로 불가능하면 제외. 대장에 있는 것과 실질이 같으면 제외.

# 4. 시험 설계
누적 시험 수 계상(대장 기준), 통과 기준, 국면 편향 보정(상승/하락 분리 보고, 시장 중립 알파), 하락 표본 부족에 대한 정직한 평가.

# 5. 의견
F3 숏 전용 관찰 장부를 모의에 바로 추가할지, 그리고 어떤 안을 먼저 실행할지 우선순위.

# 사실 (참고)
- C1 롱/숏(+5분, 4bps PESS): DEV 숏 364건 +12,830, HOLD_B 23건 +1,919, HOLD_A 7건 −452. F3 숏: DEV 368 +12,687, HOLD_B 24 +2,046.
- R2-39 결과: out/k45_short_router_r2_39_20261006/REPORT.md (S1–S6 전부 실패, router 실패, C1_X DEV 870건 +34,028).
- 데이터: 로컬 1m klines(OHLCV, 체결수, taker buy), metrics 5분(OI, global/top LS account·position, taker LS), funding, premium. 2020-01..2026-09. bookTicker·spot·m_* 금지.
- 구간: DEV_COMMON 선택, HOLD_B 확인, HOLD_A 사후만.

# 출력
out/k45_short_discovery_r2_40_20261006/REPORT.md — 1 대장 표, 2 진단 표, 3 제안 표(기존과의 차이 열 필수), 4 설계, 5 의견, "Claude에게 반박할 점". 코드는 out/run_k45_short_discovery_r2_40.py만. 모의 시스템·라이브 DB·docs 수정 금지. git commit·다운로드·주문 금지. Python venv_btcusdt\Scripts\python.exe, CPU 워커 최대 6.
