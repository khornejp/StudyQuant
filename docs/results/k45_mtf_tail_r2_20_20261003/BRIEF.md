Repo: D:\StudyQuant. R2-20: 1h/4h 방향 모델 점수 꼬리(상위 1~5%)만 거래. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고.
동시에 R2-16이 돈다. CPU 워커 최대 4. 모델 학습 없음.

# 배경 (R2-12)
1h 팔별 binary 모델 Spearman DEV 0.054~0.077, HOLD_B 대부분 월 부호 일치. 그러나 매 시간 한쪽을 고르는 즉시 진입(E0) net은 거의 전부 음수(1h h60 DEV −2.95).
질문: 점수가 극단인 소수 시점만 거래하면 거래당 net이 비용을 넘는가.

# 입력 (재사용, 재학습 금지)
out/k45_mtf_entry_r2_12_20261001/predictions_{1h_h60,1h_h120,1h_h240,4h_h240,4h_h480}.parquet
(열: pilot_fold, signal_index, decision_time, segment, close, gate_pass, horizon, p_long, pstar_long, edge_long, p_short, pstar_short, edge_short, side ...)
진입·청산·비용·펀딩 함수는 out/run_k45_mtf_entry_r2_12.py 의 것을 import (복제 금지). 먼저 재현 확인: R2-12 E0 칸(1h h60 15m gate 0/1, 4h h240) n·net이 R2-12 core_metrics와 차이 0인지 보고. 불일치면 멈추고 원인 보고.

# 꼬리 규칙 (전 칸 보고)
- 점수: s = max(edge_long, edge_short), 방향 = 큰 쪽. 동률이면 거래 없음.
- 기준선(인과): q ∈ {1%, 2%, 5%} 상위. 기준 방법 ∈ {EXPANDING_OOS(이전 fold의 OOS 점수 전체, 최소 2,000개), ROLLING_180D(결정 시점 이전 180일 OOS 점수)}. 현재·미래 fold 점수 사용 금지.
- 팔별 분리 버전도: 롱 점수 edge_long 꼬리만 롱, 숏 점수 edge_short 꼬리만 숏, 둘 다 해당하면 큰 쪽(SIDE).
- 게이트 {사용, 미사용}.
- 진입: E0(R2-12와 동일 정의). 보유: 모델 h 그대로 (1h: 60/120/240, 4h: 240/480).
- 단일 포지션, 보유 중 신호 버림, 비용 4 bps, 펀딩 반영.

# 평가 (DEV, HOLD_B — HOLD_B는 이미 본 구간으로 표기)
- 칸별: n, 롱/숏 n·net, 거래당 net, 총 net, 상위 1/2/5건 제거, 같은 날·연속 신호 사건 단위 상위 5개 제거, 적중률, 월별 양수 비율, 연도별, PW CI(out/run_patchtst_k45_flow_inference.py 의 optimal_block_length + stationary_bootstrap_errors import; 추정 블록 < 1 이면 블록 1로 두고 상태 MEASURABLE_BLOCK1 기록), 펀딩 합.
- 기준선: 반대 방향, 무작위 방향 1,000회 백분위, 항상 롱(같은 진입·보유), 같은 거래 수 무작위 시점 1,000회.
- 비용 0/4/8/12 bps 재계산.
- R2-12 같은 tf·h·게이트의 E0 전체 칸과 나란히.
- 다중검정: 칸 수 먼저 보고, DEV 일별 수익으로 SPA(기준 0), Bonferroni.

# 동결 가설
"1h 모델 점수 상위 꼬리(q ≤ 2%, 인과 기준)만 거래하면 같은 tf·h·게이트의 R2-12 E0 전체 거래보다 DEV 거래당 net이 높고, DEV net > 0 이다." HOLD_B는 판정에서 제외, 별도 기록.

# 제약
- 로컬 데이터만. 다운로드·재학습 금지. live 0. git commit 금지. HOLD_A·2026-07 이후 데이터 금지. cutoff 2026-06-30 23:59 UTC.
- 출력: out/k45_mtf_tail_r2_20_20261003/ (REPORT.md 숫자만, 해석 형용사 금지, 5,000줄 이하; parquet; manifest.json SHA256·시각·cutoff·동결 가설·OOS 결과).
- 테스트: tests/test_k45_mtf_tail_r2_20.py (TDD). (i) 기준선이 현재·미래 fold 점수 미사용, (ii) R2-12 E0 재현 일치, (iii) 동시 보유 ≤1, (iv) 동률 시 거래 없음, (v) 블록 < 1 대체 처리.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 재현 확인, 칸 수, 전 칸 요약(DEV/HOLD_B), 가설 판정, 테스트 마지막 줄, 소요 시간.
