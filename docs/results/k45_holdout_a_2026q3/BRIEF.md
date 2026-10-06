Repo: D:\StudyQuant. Branch research/k45-audit-and-negative-results-20260930.
Spec: docs/superpowers/specs/2026-10-01-trend-conditioned-side-design.md. 이 작업은 spec 7장(HOLD-A 데이터 준비) 1~5단계다.
6단계(판정 실행)는 하지 마라. 판정 규칙은 아직 동결 전이다.

# 목표

2026-07-01 00:00 ~ 2026-09-30 23:59 UTC 구간에 대해, 기존 K=45 파이프라인과 **바이트 단위로 같은 절차**로
PatchTST fold 예측과 후보(candidate) 파일을 만든다. 결과는 봉인한다.

# 단계

1. 데이터 받기
   - 출처: https://data.binance.vision/ USD-M futures (`data/futures/um/monthly/klines/BTCUSDT/1m/`), 2026-07, 08, 09.
     월 파일이 없으면 daily(`data/futures/um/daily/klines/BTCUSDT/1m/`)로 대체하고 그 사실을 기록한다.
   - 각 ZIP의 `.CHECKSUM` 파일로 검증한다. ZIP SHA256과 다운로드 시각(UTC)을 manifest에 기록한다.
   - 현물(spot) 데이터 금지. 인증 요청 금지.
   - funding이 파이프라인에 필요하면 같은 출처의 `fundingRate` 월 파일을 받는다.
2. 변환
   - `artifacts/btcusdt_2020_2026h1.parquet`와 같은 스키마·dtype·시간 기준으로 만든다. 기존 변환 코드가 있으면 그걸 써라
     (`convert_to_parquet.py`, `convertparquet.py`, `combinedata.py` 등 확인).
   - 결과: `artifacts/btcusdt_2026q3.parquet` (새 파일). 기존 parquet은 수정 금지.
   - 검사: 중복 분, 빠진 분, 2026-06-30 23:59와 2026-07-01 00:00 경계 연속성. 모두 보고.
   - walk-forward는 180일 TRAIN 이력이 필요하다. 기존 parquet과 새 parquet을 이어 붙인 뷰를 쓰되 파일은 새로 만들지 마라.
3. 피처
   - 기존 코드 그대로. `--feature-cache` 금지.
4. PatchTST fold 모델
   - 기존 K=45 후보를 만든 러너를 찾아라. 후보 파일은
     `out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet`,
     fold 0–605는 `out/run_short_patchtst_3day_cadence_pilot.py` 계열, 606–666은
     `out/run_patchtst_down_breakout_long_confirmation.py`에서 왔다. 예측·게이트 생성 러너
     (`out/run_patchtst_excursion_range.py` 등)를 추적해 정확한 설정을 복원하라.
   - 3일 cadence를 fold 666 다음부터 이어서, TEST가 2026-07-01 ~ 2026-09-30을 덮도록 fold를 만든다.
     180d TRAIN / 3d STOP / 3d TEST, 경계 origin purge 규칙(`last=t+15 <= phase end`) 동일.
   - 하이퍼파라미터, seed 규칙, q90 게이트 산정 방식 모두 동일. 바꾸면 안 된다.
   - 재현 확인: 새 코드 경로로 **기존 fold 하나(예: 666)** 를 다시 돌려 기존 예측과 일치하는지 먼저 확인하라.
     GPU 비결정성 때문에 완전 일치가 안 되면 차이 크기를 보고하라.
5. 후보 생성
   - 기존 후보와 같은 컬럼 스키마로 `out/k45_holdout_a_2026q3/candidates_sealed.parquet`를 쓴다.
     trigger(15분 내 |50| bps, `first_crossing`), arm, entry/exit index, `first_come_executed`(기존 두 팔 shared 규칙 말고
     컬럼만 채우지 마라 — 이 컬럼은 비워 두고 NaN), `signal_index`, `open_time`.
   - **PnL 컬럼(`none_net_lin_bps` 등)은 계산하지 마라.** 수익 요약 통계도 출력하지 마라. 봉인이다.
   - 파일 SHA256을 `out/k45_holdout_a_2026q3/SEALED.json`에 기록한다.

# 출력

- `out/k45_holdout_a_2026q3/manifest.json`: 출처 URL, 다운로드 시각, ZIP SHA256, 데이터 cutoff, fold 수, 러너 경로와 SHA256
- `out/k45_holdout_a_2026q3/REPORT.md`: 단계별 결과, 재현 확인 결과, 경계 검사. 수익 숫자는 없다.

# 제약

- `live_orders: 0`, `new_orders: 0`. 새 fit은 이 walk-forward 연장 fold에 한해서만 허용.
- 기존 산출물·기존 parquet 불변.
- 장시간 학습은 진행 로그를 파일에 남겨라(fold 번호, 시각).
- 숫자마다 file:line 또는 정확한 필터를 달아라.
