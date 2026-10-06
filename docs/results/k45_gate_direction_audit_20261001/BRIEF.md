Repo: D:\StudyQuant. 감사(audit) 작업이다. 확인이 아니라 **공격**해라.

배경: docs/superpowers/plans/2026-10-01-gate-direction-catboost.md 를 끝까지 돌렸다. 결과 out/k45_gate_direction_20261001/REPORT.md.
CatBoost 방향 순서는 DEV에서 유의(score Spearman 0.036, 44/58월)인데 백테스트 net은 전 margin 음수(0.10: −3.63, 0.20: −1.47).
사용자는 "이 데이터로 불가"라는 결론을 거부했다. **PatchTST 게이트가 정말 변동성을 잡는지, CatBoost 롱/숏이 정말 맞는지** 의심하라고 했다.
결론을 내리지 말고, 아래 각 질문에 숫자로 답해라. 숫자마다 file:line 또는 정확한 필터를 달아라.

# 제약
- 로컬 데이터만. 다운로드 금지. `--feature-cache` 금지. live 0.
- PatchTST 재학습 금지. CatBoost는 아래 C-4에서만 추가 학습 허용(plan 고정 파라미터, walk-forward 동일 규칙).
- 기존 산출물 불변. 새 산출물은 `out/k45_gate_direction_audit_20261001/`만. git commit 금지.
- Python: `venv_btcusdt\Scripts\python.exe`.

# A. PatchTST 게이트 감사
A-1. 게이트가 실제로 큰 움직임을 고르는가. 같은 15분 격자의 TEST origin 전체에서, `passes_q90` 참/거짓별로
     실현 excursion, range, |r45|, |r15|의 평균·중앙값. pred_excursion 십분위별 실현 excursion(단조성, Spearman). fold별 Spearman 분포.
A-2. 게이트 임계값 정합성: fold별 `stop_q90_excursion_bps`와 TEST 통과 비율. 설계상 ~10%인데 실제 비율 분포. 통과 비율이 0이거나 매우 큰 fold.
A-3. 게이트의 방향 가치: 게이트 안/밖에서 동일 피처(Task 3 상위 선택 피처 10개)의 r45 Spearman과 월 일치. 방향 예측이 고변동 구간에서 더 쉬운가, 더 어려운가.
A-4. 게이트 통과 바의 비용 대비 기회: |r45| > 4 bps 비율, |r45| 분포 분위수. 완벽한 방향을 알 때의 net 상한(oracle)과 방향 정확도 p일 때 손익분기 p(대칭 가정 대신 실제 분포로).

# C. CatBoost 방향 감사 (out/k45_gate_direction_20261001/predictions.parquet)
C-1. 정확도 vs 크기: 예측 방향 적중률(롱/숏 각각, margin별). 적중 시 평균 이익, 실패 시 평균 손실. 손익분기 적중률 대비 실제. 손실 꼬리(하위 1%, 5%) 거래가 어떤 바인가(시각, 연도, |r45|).
C-2. 시간축: 같은 score로 r_h, h ∈ {5, 10, 15, 30, 45, 60, 90} 분 Spearman과 상위/하위 십분위 평균. 방향 정보가 45분보다 짧게 소멸하는가.
C-3. 보정: p_long, p_short 신뢰도 표. 실제 클래스 빈도 대비 확률이 좁게 몰려 있는가(분포 분위수).
C-4. 라벨 문제: 3분류는 +5와 +500을 같게 취급한다. 같은 피처·같은 walk-forward로 **회귀(r45 예측, RMSE 손실)**와
     **크기가중 3분류(sample_weight=|r45|)** 두 변형을 학습해서 Task 4·5와 같은 지표(score Spearman, 십분위, margin 0.10 동등 규칙 백테스트 — 회귀는 예측값 |ŷ|>4 bps 규칙)를 내라. 파라미터 고정, 튜닝 금지.
C-5. book 손실: 단일 포지션 때문에 버려진 신호와 채택된 신호의 r45(예측 방향 기준) 평균 비교. margin별.
C-6. 누수 역방향 점검: 상위 선택 피처가 t 시점 종가까지만 쓰는지 레지스트리 정의를 인용해 확인. 진입 close[t] vs 다음 봉 open 진입 차이.

# 출력
`AUDIT.md`(질문별 답, 숫자, 근거), 질문별 parquet, `manifest.json`(입력·출력 SHA256, 시각, cutoff).
마지막 출력: 질문별 한 줄 요약. 판정·추천 금지.
