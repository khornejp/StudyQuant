Repo: D:\StudyQuant. R2-39: 숏 강화(1단계) + 전략 선택 router(2단계) 실행. 사용자 승인(2026-10-06): "1단계 2단계 진행".

명세(계약): out/k45_short_router_plan_review_r2_38_20261006/REPORT.md 의 "# 고정 실행 명세 제안" 1단계·2단계를 그대로 따른다. 거기 적힌 데이터·구간·후보(S1–S6)·장부(standalone/overlay, FIRST, 우선순위)·시간 계약(정시 T 판단, T+1분 open 진입, metrics create_time+5분 < T)·피처(15개 이하 고정)·모델(ridge, depth-2 boosting만)·학습(월 1회 확장 walk-forward, 24h purge/embargo)·지표·통과 기준·시험 수·산출물·실패 처리(SHORT_STAGE_FAIL, HOLD_B/HOLD_A로 구제 금지)를 변경 없이 적용. 명세에 모호한 곳이 있으면 결과를 보기 전에 REPORT의 "실행 전 해석" 절에 해석을 기록하고 그대로 진행. 결과를 본 뒤 정의·임계값·피처를 바꾸지 마라.

# 순서
1. 실행 전: 명세 해석 기록, 후보·피처·모델 정의 parquet와 manifest(frozen hypothesis, cutoff, 입력 hash, 시험 수) 먼저 작성.
2. 기준선 C1_X: 현행 C1을 T+1분 open 진입 계약으로 재계산(DEV/HOLD_B/HOLD_A 사후). 기존 T open C1과 차이도 표로.
3. 1단계 실행 → decision.json(통과 후보 또는 SHORT_STAGE_FAIL). 통과 후보 1개만 HOLD_B 확인.
4. 2단계 실행(1단계 winner 미포함, action = F3, F3-w30, E1) → DEV walk-forward 정책 2개 판정, winner 1개만 HOLD_B 확인.
5. HOLD_A는 모든 단계 숫자 표시만, "사후" 라벨.

# 금지
- 모의 시스템 코드·설정·라이브 DB 수정 금지. 새 코드는 out/run_k45_short_router_r2_39.py(필요시 out/ 하위 모듈)만. git commit 금지. 다운로드·주문·인증 금지(로컬 데이터만; OI/taker LS 등 metrics는 기존 archive 사용). bookTicker·spot·m_* 미사용.
- 결론 단정 금지. 숫자 먼저.

# 출력
out/k45_short_router_r2_39_20261006/REPORT.md — 맨 앞: C1_X 기준선 표, 1단계 결과표(후보별 standalone/overlay 지표·통과 여부), decision, 2단계 결과표(정책별 vs C1_X paired 지표·통과 여부), HOLD_B 확인 결과, HOLD_A 사후 표, 다중검정 표. 마지막 "Codex 의견"과 사용자 결정 사항. 명세의 산출물 전부. Python venv_btcusdt\Scripts\python.exe, CPU 워커·스레드 합 최대 8. 진행 로그 남기기.
