Repo: D:\StudyQuant. R2-26: HOLD_A(2026-07-01 00:00 ~ 2026-09-30 23:59 UTC) 데이터 수집 + 피처 생성 + 패리티 검증. 평가 금지 — 이 작업에서는 어떤 전략·모델 결과도 계산하지 마라(HOLD_A 수익률·신호 성과 계산 금지). 데이터만 준비한다.

# 사용자 결정 (2026-10-04)
"로컬 데이터만" 규칙의 예외: HOLD_A 최종 검증용으로 Binance USD-M BTCUSDT 공개 아카이브(data.binance.vision)에서 필요한 데이터만 수집한다. 인증·주문·현물·DEX 금지. 이 범위 밖 다운로드 금지.

# 수집 (기존 프로젝트 다운로더 사용, 새로 만들지 마라)
- klines 1m: 이미 있음(artifacts/btcusdt_2026q3_source/, artifacts/fresh_2026q3_archive/). 2026-07-01~09-30 전 분 커버리지 확인, 빠진 날(예: 09-30)만 daily 아카이브로 보충.
- metrics(롱숏비율·OI·taker): btcusdt_quant/metrics_source.py 다운로더, daily 2026-07-01~09-30.
- fundingRate: btcusdt_quant/funding_source.py 다운로더, monthly 2026-07/08/09 (09가 monthly로 없으면 있는 범위와 함께 보고).
- premiumIndexKlines 1m: btcusdt_quant/premium_index_source.py.
- 그 밖에 feature registry가 요구하는 소스가 있으면 같은 방식으로(기존 2020~2026H1 피처를 만들 때 쓴 소스 목록을 manifest·코드에서 확인해 동일하게). 기존 피처에서 "unavailable"/fallback이던 소스는 그대로 unavailable로 둔다.
- 각 파일: URL, 다운로드 시각, SHA256, CHECKSUM 검증 결과를 sources.json 에 기록. 검증 실패 파일은 쓰지 마라.
- 저장: artifacts/hold_a_2026q3/ (기존 artifacts 폴더 덮어쓰기 금지).

# 피처 생성 (같은 코드 경로)
- 기존 2020-01~2026-06 피처 parquet을 만든 코드 경로·버전(btcusdt_quant/dataset.py 등)을 찾아 그대로 사용. --feature-cache 사용 금지(캐시는 구현 변경을 못 잡는다).
- 지표 워밍업 때문에 2026-07 이전 이력이 필요하면 기존 로컬 데이터(2026-06 이전)를 이어 붙여 계산하고, 출력은 2026-07-01 이후만 저장. 워밍업 구간 사용 사실 기록.
- 출력: artifacts/hold_a_2026q3/features_2026q3.parquet (열 구성·dtype이 기존 피처 parquet과 같아야 함), market_2026q3.parquet(1m OHLCV + premium), funding_2026q3.parquet.

# 패리티 검증 (필수)
- 같은 코드 경로로 2026-06-01~06-30 피처를 원시 아카이브(로컬에 있는 2026H1 원본)에서 다시 계산해 기존 피처 parquet의 같은 구간과 비교: 열별 최대 절대 차이, 불일치 행 수. 허용 오차 1e-9(부동소수)·정수열 완전 일치. 불일치 열이 있으면 원인 보고하고 HOLD_A 피처에도 같은 영향이 있는지 명시.
- 2026-06-30 → 07-01 경계 연속성: 마지막/첫 행 지표 값이 이어지는지(롤링 창 단절 없음).
- 결측: 소스별 결측 분 수, 정산 이벤트 수(기대 276 = 92일 × 3), metrics 5분 관측 수.

# 산출물
out/k45_hold_a_data_r2_26_20261004/REPORT.md (숫자만): 수집 목록·검증, 커버리지, 패리티 결과, 결측, 피처 열 비교. manifest.json(모든 다운로드 URL·SHA256, 코드 SHA256, 시각).
테스트: tests/test_k45_hold_a_data_r2_26.py: (i) 출력 피처 열·dtype = 기존 피처, (ii) 2026-07-01 이전 행 미포함, (iii) 정산 276건, (iv) 패리티 함수가 의도적 변형을 잡아냄.
git commit 금지. live 0. CPU 워커 최대 6(다른 작업과 병행).
Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 수집 요약, 패리티 결과, 결측, 테스트 마지막 줄, 소요 시간.
