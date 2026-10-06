Repo: D:\StudyQuant. R2-8: 단일 포지션 · "더 높은 확률 쪽" 결정 · 팔별 보유 시간. 재학습 없이 기존 예측으로 계산. 설계·구현·실행·보고 끝까지, 결과로 거르지 마라.

# 사용자 확정 조건
- **book은 단일 포지션만.** 동시 보유 0 또는 1. ALL/CAP 결과는 내지 마라.
- 매 게이트 바에서 롱과 숏 확률을 비교해 **더 높은 쪽 하나만** 거래한다. 둘 다 거래하는 일은 없다.
- 보유 중에 들어온 신호는 버린다(선착순). 버린 신호 수와 그 신호들의 사후 r_h 평균도 보고.

# 입력(불변)
- 3분류: out/k45_gate_direction_20261001/predictions.parquet (p_long, p_short)
- R2-1 팔별 모델: out/k45_gate_direction_r2_20261001/ 의 롱/숏 예측과 p* (manifest 확인). 팔별 보유분 h에 맞는 예측 파일을 쓴다(롱 h45/h60, 숏 h5/h15/h45 중 해당).
- R2-3 RESIDUAL 3분류 예측(비교용)
- artifacts/btcusdt_2020_2026h1.parquet, 펀딩 artifacts/funding_2020_2026h1
재사용: out/k45_trend_side.py, out/run_patchtst_k45_flow_inference.py, R2-5/R2-6의 대체 CI·펀딩·무작위 기준선 코드, R2-7의 인과 분위수 코드.

# 결정 규칙
A. 3분류 (원본, RESIDUAL 각각)
  - score = p_long − p_short. side = 롱 if score > m, 숏 if score < −m, else 없음.
  - m 고정값: {0.10, 0.20}.
  - m 인과값: fold k 이전 out-of-sample |score| 분포에서, 고정 m=0.20이 DEV 전체에서 낸 신호 비율과 같은 비율이 되는 분위수를
    **과거 점수만으로** 매 fold 계산(R2-7과 같은 확장형 규칙). 2,000개 미만이면 거래 없음.
B. R2-1 팔별: edge_long = p_long − p*_long, edge_short = p_short − p*_short. 둘 다 ≤0이면 없음, 아니면 큰 쪽.

# 팔별 보유 시간
- 롱 h_L ∈ {45, 120, 240}, 숏 h_S ∈ {5, 15, 60}. 9개 조합 전부.
- 포지션 점유 시간 = 그 거래의 h. 즉 롱 4시간 보유 중이면 그동안 숏 신호도 버린다.
- **사전 고정 주 조합**(R2-6 DEV에서 고른 것, 판정은 HOLD-B로만): 3분류 m=0.20, 롱 240 / 숏 60. 이 한 칸만 "PRIMARY"로 표기.
  나머지는 보고용.

# 보고 (구간 DEV / HOLD_B 분리, HOLD_B는 탐색 표기)
1. 조합마다: 전체 n, net, 상위 1/2/5건 제외 net, 적중률, PW CI + 대체 CI, 월별 양수 비율, 연도별 n·net.
2. 팔별 기여: 롱 n·net, 숏 n·net, 롱/숏 거래 비율, 롱이 점유한 시간 비율.
3. "확률 높은 쪽" 효과 분리: 같은 바·같은 보유에서 (a) 실제 결정, (b) 방향 반대, (c) 무작위 ±1 (seed 20261001, 1,000회 분포의 백분위),
   (d) 항상 롱(같은 진입 바, h_L) — 상승장 효과 기준선.
4. 버린 신호: 수, 사후 방향 r_h 평균.
5. HOLD_B 월별 표(6개월): 월별 n, 롱/숏 수, net.
6. 펀딩 합계.

# 제약
- 로컬 데이터만. 다운로드·재학습 금지. live 0. git commit 금지.
- 출력: out/k45_gate_direction_r2_8_20261001/ (REPORT.md 숫자만·해석 형용사 금지, 표별 parquet, manifest.json: 입력/출력/소스 SHA256, 시각, cutoff, 동결 가설
  "단일 포지션에서 더 높은 확률 쪽만 거래하면(3분류 m=0.20, 롱 240분/숏 60분) HOLD_B net이 0보다 크다").
- 테스트: tests/test_k45_gate_direction_r2_8.py (TDD). 특히 (i) 동시 보유가 절대 1을 넘지 않음, (ii) 한 바에서 한 방향만, (iii) 인과 m이 미래 점수를 안 씀.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: PRIMARY 결과(DEV/HOLD_B), 9조합 × 규칙 요약 표(단일 포지션 net), 기준선 비교, 테스트 마지막 줄.
