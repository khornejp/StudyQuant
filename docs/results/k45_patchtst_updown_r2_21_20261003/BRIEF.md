Repo: D:\StudyQuant. R2-21: PatchTST 옵션 A — 변동폭 타깃을 상승·하락으로 분리 + 게이트 기준 수정. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고.

# 배경
- 현재 게이트 PatchTST(out/run_patchtst_excursion_range.py 계열)는 15분 뒤 excursion = max(상승폭, 하락폭)과 range 두 타깃. 방향 정보가 없다.
- 2026-10-01 감사: 게이트 예측-실현 Spearman 0.734. 그러나 fold별 STOP q90 기준이라 통과율이 들쭉날쭉(평균 15%, 0%인 fold 31개, 25% 초과 129개).
- 사용자 승인 "옵션 A": 타깃을 상승폭·하락폭·range 3개로 늘리고 게이트 기준을 고친다.

# 1. 기존 게이트 출처 확인 (먼저)
- out/k45_gate_direction_20261001/manifest.json 의 inputs와 out/k45_gate_direction.py 를 읽어 K45 실험들이 쓴 게이트 예측 파일·fold 범위·seed·체크포인트 위치를 찾아 REPORT에 적는다.
- 같은 fold 집합·seed·하이퍼파라미터(PARAMS)·입력 피처·윈도를 그대로 쓴다. 타깃 열만 바꾼다.
- 기존 체크포인트·예측 파일은 덮어쓰지 마라. 새 출력은 out/k45_patchtst_updown_r2_21_20261003/ 아래에만.

# 2. 타깃 (span = 기존과 동일 15분)
- up = (향후 15분 최고가 / close − 1) × 1e4, down = (1 − 향후 15분 최저가 / close) × 1e4, range = 기존 정의.
- 기존 excursion = max(up, down) 이므로 새 모델의 max(up_pred, down_pred)와 기존 excursion 예측의 상관을 패리티 지표로 보고.
- 손실: 3개 헤드 MAE 평균(기존과 같은 방식), early stopping은 기존처럼 STOP 구간.

# 3. 학습
- GPU(RTX 3090). 먼저 3개 fold로 시험 학습해 fold당 시간을 재고 전체 예상 시간을 run.log에 기록한 뒤 전체를 돌린다(멈추지 말 것).
- 체크포인트로 재개 가능하게. seed는 기존과 같은 집합.

# 4. 게이트 기준 (전부 보고)
- G_STOP: 기존처럼 fold STOP 구간 예측의 q90.
- G_ROLL: 결정 시점 이전 180일의 과거 OOS 예측(range 또는 excursion) q90. 최소 2,000개, 미만이면 게이트 없음 기록. 현재·미래 fold 예측 금지.
- G_EXP: 과거 OOS 전체 q90.
- 각 기준의 fold별 통과율 분포(평균, 0% fold 수, 25% 초과 fold 수)를 기존 게이트와 나란히.

# 5. 평가
- 헤드별 예측 품질: Spearman(up_pred, 실현 up), (down_pred, 실현 down), (range_pred, 실현 range). DEV / HOLD_B, 월 일치.
- 방향 정보: d = up_pred − down_pred. Spearman(d, 실현 15분·45분 부호 수익), 십분위별 실현 수익.
- 단순 거래 규칙(게이트 통과 시): 방향 = sign(d), |d| > m, m ∈ {0, 학습 구간 |d| 분포 q50, q80} (인과), 보유 15분·45분, 단일 포지션, 비용 4 bps, 펀딩. 게이트 3종 × 보유 × m 전 칸.
- 기준선: 같은 게이트 통과 바에서 무작위 방향 1,000회, 항상 롱, 반대 방향, 그리고 기존 fade 규칙(직전 15분 반대 방향).
- 기존 게이트(2헤드) 대비: 같은 바·같은 규칙에서 게이트 통과 바 집합 겹침(Jaccard)과 net 차이.

# 동결 가설
"상승·하락 분리 PatchTST의 d = up_pred − down_pred 는 게이트 통과 바에서 15분 부호 수익과 DEV Spearman > 0 이고, 그 방향 규칙의 DEV net이 같은 바의 fade 규칙보다 높다." HOLD_B는 이미 본 구간, 별도 기록.

# 제약
- 로컬 데이터만. 다운로드 금지. live 0. git commit 금지. HOLD_A·2026-07 이후 데이터 금지. cutoff 2026-06-30 23:59 UTC.
- 출력: out/k45_patchtst_updown_r2_21_20261003/ (REPORT.md 숫자만, 해석 형용사 금지, 5,000줄 이하; parquet; manifest.json SHA256·시각·cutoff·동결 가설·OOS 결과·학습 시간).
- 테스트: tests/test_k45_patchtst_updown_r2_21.py (TDD). (i) up/down 타깃 정의와 max(up,down) = 기존 excursion, (ii) 라벨 창이 STOP·TEST 경계를 넘지 않음, (iii) G_ROLL·G_EXP 기준이 과거 예측만 사용, (iv) 동시 보유 ≤1, (v) 기존 산출물 파일 미변경(해시 비교).
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 게이트 출처, 학습 시간, 패리티, 헤드별 품질, 통과율 분포, 방향 품질, 거래 칸 요약, 가설 판정, 테스트 마지막 줄.
