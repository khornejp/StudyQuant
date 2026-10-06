Repo: D:\StudyQuant. 펀딩 요율 "오류" 주장에 대한 적대적 검증. 확인하지 말고 공격하라. 주장이 틀렸을 가능성을 먼저 찾아라.
코드 수정 금지(실험 코드·테스트 모두). 읽기 전용 분석. 결과는 out/k45_funding_review_20261004/ 에만 쓴다. git commit 금지. 로컬 데이터만, 다운로드 금지.

# Claude의 주장 (검증 대상)
A. out/run_k45_classic_rules_r2_14.py:204-221 `settlement_events`는 정산 시각 T(UTC 00/08/16)에 "T 직전 분의 registry funding_rate"를 적용한다. 이 값은 공식 아카이브(artifacts/funding_2020_2026h1/BTCUSDT-fundingRate-*.zip)의 "T−8h 정산 요율"과 99.99% 같고, "T 정산 요율"과는 26%만 같다. 따라서 R2-14는 한 정산 늦은 요율을 손익에 적용했다 = 오류.
   근거 파일: out/k45_validation_r2_19_20261003/funding_audit.parquet, REPORT.md funding_audit 절.
B. 영향 범위는 R2-14, R2-15, R2-17, R2-18 규칙 계열뿐이다. 다른 실험(R2-6~R2-13, R2-16, R2-20, R2-21, gate-direction)은 out/run_k45_gate_direction_r2_6.py `funding_events()`(아카이브)를 쓴다.
C. 모델 학습(CatBoost 라벨, PatchTST 타깃)에는 정산 펀딩이 들어가지 않는다. registry funding_rate/next_funding_rate를 피처·신호로 쓰는 것은 결정 시점에 알 수 있는 값이라 문제없다. R2-15 메타 라벨(펀딩 포함 거래 손익)은 영향을 받는다.
D. 손익 영향은 작다(예: E1 z3 DEV +14,636 → +14,473 bps). F1·G2처럼 정산을 걸쳐 들고 가는 규칙은 더 클 수 있다.

# 공격 과제 (각각 SUPPORTED / REFUTED / UNCERTAIN + 근거 숫자·파일·행번호)
1. 아카이브 시각 규약: 아카이브 CSV의 실제 열 이름과 의미(calc_time, last_funding_rate 등)를 확인하라. "calc_time=T 행의 요율"이 T에 정산된 요율인지, T부터 시작하는 다음 구간의 요율인지 데이터로 판정하라.
   방법 1: 로컬 프리미엄 인덱스(artifacts/premium_index_2020_2026h1)로 Binance 공식 공식(구간 평균 프리미엄 + clamp(0.01% − 프리미엄, ±0.05%), 상하한 캡)으로 각 구간 (T−8h, T]의 계산 요율을 만들어, 아카이브 T 값 / T−8h 값 / T+8h 값 중 어느 것과 가장 잘 맞는지 상관·일치율로 보고. 구간 길이가 8h가 아닌 시기(있으면)는 따로.
   방법 2: registry(feature parquet) funding_rate가 바뀌는 분이 정산 시각과 어떻게 맞물리는지(정산 분에 바뀌는지, 직후에 바뀌는지) 분포로 보고.
   만약 registry 값이 "다음 정산 예상 요율"이라면 R2-14 방식이 맞을 수도 있다 — 이 가능성을 직접 반박하거나 지지하라.
2. 주장 B: out/ 아래 모든 run_k45_*.py, k45_*.py 와 import 체인을 추적해 각 실험이 손익 펀딩을 어디서 읽는지 표로. 누락된 실험이 있으면 지적.
3. 주장 C: (a) CatBoost·PatchTST 학습 라벨에 펀딩이 들어가는 코드 경로가 있는지, (b) registry funding_rate가 결정 시각 t에서 t 이후 정산 시각의 아카이브 요율과 같아지는 경우(미래 정보)가 있는지 전수 확인, (c) R2-13 라벨, R2-15 라벨, R2-16·R2-20 손익 경로 확인.
4. 주장 D: R2-14 813칸 전부를 아카이브 요율로 다시 계산했을 때의 칸별 펀딩 합 차이를 실제 계산해서(재학습 없음, R2-14 함수 재사용, 출력은 이 폴더) 분포·부호 변화 칸 수·F1/G2 별도 표로 보고. 계산만 하고 R2-14 코드는 바꾸지 마라(필요하면 이 폴더에 래퍼 스크립트).
5. 위와 별개로 Claude가 놓친 다른 해석이나 결함이 있으면 적어라.

# 출력
out/k45_funding_review_20261004/REPORT.md — 맨 앞에 주장 A~D 판정 표, 다음에 과제별 근거. 숫자만, 해석 형용사 최소. parquet 표. manifest.json(입력 SHA256, 시각).
Python: venv_btcusdt\Scripts\python.exe. CPU 워커 최대 8.
