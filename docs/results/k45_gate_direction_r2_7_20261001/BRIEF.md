Repo: D:\StudyQuant. R2-7: 꼬리 신호 인과 검증. 재학습 없이 기존 예측으로 계산한다. 설계·구현·실행·보고를 끝까지 하고, 결과로 거르지 마라.

# 배경
out/k45_gate_direction_r2_20261001/r24_tail_curves.parquet 에서 회귀(regression_rmse)·크기가중(weighted_multiclass) 점수의 상위 1% 바가
DEV net +31.1 / +33.2 bps(n 249, ALL book)로 나왔다. 그러나 꼬리 기준(1/2/5/10%)을 **DEV 전체 점수 분포**로 정했다. 이건 미래 정보다.
이 검증의 목적은 그 숫자가 인과적 기준에서도 남는지 공격하는 것이다.

# 입력(불변)
- out/k45_gate_direction_audit_20261001/c4_predictions.parquet (regression_rmse: score=ŷ, weighted_multiclass: score=p_long−p_short)
- out/k45_gate_direction_20261001/predictions.parquet (3분류, 비교용)
- out/k45_gate_direction_r2_20261001/ 의 R2-3 RESIDUAL 예측(비교용; 파일은 manifest 확인)
- artifacts/btcusdt_2020_2026h1.parquet, 펀딩 artifacts/funding_2020_2026h1 (기존 처리 재사용)
재사용: out/k45_trend_side.py (admit, trim_top), out/run_patchtst_k45_flow_inference.py (mean_influence, pw_inference), R2-5의 대체 CI(고정 블록 7/14/30일, event-time 20/50).

# 인과 기준 (주 규칙)
- 각 fold k의 기준값: 그 fold 이전에 **이미 TEST로 나온** 예측 점수(같은 모델 variant)의 분포에서 상위 q, 하위 q 분위수.
  즉 fold k 기준 = fold < k 의 out-of-sample 점수 전체(확장형). 최소 2,000개 미만이면 그 fold는 거래 없음(기록).
- q ∈ {1%, 2%, 5%}. 상위 꼬리 → 롱, 하위 꼬리 → 숏. 둘 다 보고, 팔별로도 분리.
- 진입 close[t], 청산 close[t+45], 비용 4 bps, 펀딩 반영. book: SINGLE과 ALL.
- 보조 규칙(보고만): 최근 180일 rolling 분위수.

# 공격 항목 (모두 보고)
1. 인과 기준 결과 vs 원래(전체 분포) 기준 결과를 같은 표에 나란히.
2. 상위 1, 2, 5, 10건 제거 후 net.
3. 날짜 집중도: 거래가 있는 UTC 날짜 수, 상위 5일이 차지하는 PnL 비율, 연도별 n과 net, 월별 양수 비율.
4. 사건 확인: 수익 상위 10건의 시각, |r45|, 그날 일중 범위(bps).
5. 무작위 기준선: 같은 fold에서 같은 수의 게이트 바를 무작위로 뽑아 같은 방향 규칙(무작위 ±1, seed 20261001) — 1,000회 반복 분포에서 실제 net의 백분위.
6. 크기 효과 분리: 꼬리 바의 |r45| 평균 vs 전체 게이트 바 |r45| 평균, 그리고 방향 적중률. "크기가 큰 바를 고른 것"인지 "방향을 맞힌 것"인지.
7. CI: PW(가능 시) + 대체 CI 전부.
8. DEV / HOLD_B(탐색 표기) 분리.

# 제약
- 로컬 데이터만. 다운로드 금지. 재학습 금지. live 0. git commit 금지.
- 출력: out/k45_gate_direction_r2_7_20261001/ (REPORT.md, 표별 parquet, manifest.json에 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설 "크기 반영 모델의 극단 점수 바는 인과적 기준에서도 net이 0보다 크다").
- 해석 형용사 금지. 숫자만. 승자 선택 금지.
- 테스트: tests/test_k45_gate_direction_r2_7.py (TDD). 특히 "fold k 기준이 fold ≥ k 점수를 쓰지 않는다"를 테스트로 고정.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 핵심 표(variant × q × 팔 × book × 기준방식, DEV/HOLD_B), 공격 항목 요약, 테스트 마지막 줄.
