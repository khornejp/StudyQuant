Repo: D:\StudyQuant. R2-6: 보유 시간 sweep. 재학습 없이 기존 예측으로 계산한다. 설계·구현·실행·보고를 끝까지 하고, 결과로 거르지 마라.

입력(불변):
- out/k45_gate_direction_20261001/predictions.parquet (3분류)
- out/k45_gate_direction_audit_20261001/c4_predictions.parquet (회귀, 크기가중)
- out/k45_gate_direction_r2_20261001/ 의 R2-1 롱/숏 예측과 진입 결정(파일명은 그 폴더 manifest.json / REPORT.md 확인)
- artifacts/btcusdt_2020_2026h1.parquet, 펀딩: artifacts/funding_2020_2026h1 (기존 러너의 펀딩 처리 방식 재사용)
재사용: out/k45_trend_side.py (admit, trim_top), out/run_patchtst_k45_flow_inference.py (mean_influence, pw_inference), R2-5의 대체 CI(고정 블록 7/14/30일, event-time 20/50 거래).

# 규칙
- 진입 결정(어느 바에서 어느 방향)은 각 예측 원본의 규칙 그대로: 3분류 margin 0.10, 0.20; 회귀 |ŷ|>4; 가중 margin 0.10; R2-1 팔별 p* 규칙.
- 바꾸는 것은 청산 시각뿐: 진입 close[t], 청산 close[t+h]. 시간 청산만. stop/TP 금지.
- h: 롱·숏 모두 {5, 15, 30, 45, 60, 90, 120, 180, 240}분 (같은 목록). 롱·숏 모두 120/180/240분(2/3/4시간) 결과를 별도 요약 표로도 낸다. 롱·숏 각각 sweep.
- book: SINGLE(점유 h분, 선착순)과 ALL(제한 없음, 최대/평균 동시 보유 수 보고).
- net = 방향 gross − 4 − 펀딩(보유 중 정산 시각 통과 시 실제 펀딩률, 방향 부호 반영).
- 진입 후 t+h가 그 fold TEST 끝 또는 데이터 끝을 넘으면 그 거래 제외하고, 제외 수를 보고.
- 구간: DEV(fold ≤605), HOLD_B(≥606, 탐색 표기).
- 보고: 예측원 × 팔 × h × book 마다 n, gross, 펀딩, net, 상위 2건 제외, 적중률, 월별 양수 비율, PW CI(가능 시) + 대체 CI. 무작위 방향 기준선(seed 20261001, 같은 바·같은 h·거래 수 일치).
- 추가로 "롱 신호 순수 효과" = 같은 h에서 롱 신호 바의 r_h 평균 − 무작위 바 r_h 평균.
- 해석 형용사 금지. 숫자만. 승자 선택 금지(보고용).

# 제약
- 로컬 데이터만. 다운로드 금지. 재학습 금지. live 0. git commit 금지.
- 출력: out/k45_gate_direction_r2_6_20261001/ (REPORT.md, 표별 parquet, manifest.json에 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설 문장 "보유 시간을 늘리면 롱 net이 오르고 숏은 짧을수록 낫다").
- 테스트: tests/test_k45_gate_direction_r2_6.py (TDD). Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 핵심 표(DEV/HOLD_B, 예측원 × 팔 × h, SINGLE/ALL net), 테스트 마지막 줄.

# 참고
이전 실행이 중간에 중단됐다. `out/run_k45_gate_direction_r2_6.py`, `tests/test_k45_gate_direction_r2_6.py`가 미완성 상태로 남아 있다. 재사용해도 되지만 전부 다시 검토하고, 숏 120/180/240 추가를 반영해라.
