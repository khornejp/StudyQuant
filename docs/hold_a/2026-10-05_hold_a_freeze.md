# HOLD_A 최종 검증 — 후보·가설 고정 문서 (초안 v3, 사용자 확인 전)

작성: 2026-10-05. 개정: 2026-10-05 v2 (Codex 적대적 검토 `out/k45_hold_a_freeze_review_20261005/REPORT.md` 수정안 반영), v3 (R2-27~R2-30 전용 러너 제작·재현 결과로 장치·스레드·미시구조 입력·hash 확정). 상태: **DRAFT**. 사용자 확인 후 상태를 FROZEN으로 바꾸고 커밋한다. 커밋 이후에는 이 문서의 어떤 항목도 바꾸지 않는다. 바꿔야 하면 HOLD_A 결과를 보기 전에 새 버전으로 다시 커밋한다.

## 1. 구간과 데이터

- HOLD_A: 2026-07-01 00:00 ~ 2026-09-30 23:59 UTC (92일, 132,480분).
- 데이터: `artifacts/hold_a_2026q3/` (R2-26 수집, 아카이브 체크섬 219/219, 6월 재계산 패리티 불일치 0). 이 문서 커밋 전까지 HOLD_A 데이터로 어떤 성과·신호 통계도 계산하지 않았다.
- 평가는 **1회**. 같은 후보·규칙으로 다시 돌리는 것은 재현 확인뿐이다. HOLD_A 결과를 보고 후보·파라미터·규칙을 바꾸지 않는다.

## 2. 후보와 실행 정의

후보는 H1–H5와 B0 여섯 개로 고정한다. 평가구간은 반개구간 `[2026-07-01T00:00:00Z, 2026-10-01T00:00:00Z)`다. 모든 전략은 1단위 비복리 단일 포지션 book이다. 신호 결정 뒤 다음 이용 가능한 1분 open에서 체결한다.

- H1: `F3|1h|10/24|signal|LS`. `out/run_k45_classic_rules_r2_14.py`의 `_attach_minute_features`, `_rolling_quantile`, `_base_signals`, `simulate` 의미를 그대로 쓴다. 1h 결정시각보다 엄격히 이전인 `global_ls_account`를 사용한다. rolling 2,160 bar, min_periods 720, 현재 붙은 관측 포함, q=.10/.90, contrarian LS, 최대 24개 1h bar다. HOLD_A 시작에서 reset하지 않는다.
- H2: `E1|1h|3|signal|L`. 완전히 닫힌 현재 1h bar 거래량을 포함한 20-bar mean/std(ddof=0) z-score가 3보다 크고, close가 `high_20.shift(1)`보다 클 때 long 진입한다. 최대 보유 20개 1h bar다.
- H3: C1 FIRST = H1+H2. 동일시각 우선순위 H1>H2. 포지션 보유 중 모든 신규 신호는 폐기하며 switching하지 않는다. 기존 `exit_time <= new entry_time`이면 먼저 청산된 것으로 본다.
- H4: C3 FIRST = H1 + `SIDE|ROLLING_180D|q=.01|L=120|S=60|V0` + `4h_h480|SIDE|ROLLING_180D|q02|g1` + H2. 동일시각 우선순위는 H1>4h_h480>R2-9b SIDE>H2다. 보유 중 신규 신호는 폐기한다.
- H5: C4 FIRST = `F3_global_ls_account|1h|w30|q20|h12|LS` + H2. F3는 rolling 720 bar, min_periods 720, 현재 관측 포함, q=.20/.80, contrarian LS, 최대 12개 1h bar다. 동일시각 우선순위 F3-w30>H2다.
- B0: 2026-07-01 00:00의 1m open에서 long 1단위 진입, 2026-09-30 23:59 1m close에서 청산한다. 같은 비용·funding 원장을 쓴다.

비용 4bps는 왕복 총액이며 entry/exit에 2bps씩 부과한다. 8/12bps는 민감도일 뿐 가설 판정에 쓰지 않는다. gross는 분당 log-return bps, total net은 HOLD_A 92일 분당 MTM gross-cost+funding의 합이다. 내부 정산은 포함한다. entry/exit 정산 동시시각에서 PESS는 음수 cashflow만, OPT는 양수 cashflow만 포함한다.

고전 규칙 H1/H2/H5와 그 조합은 HOLD_A 이전부터 연속 실행해 7월 1일 carry-in 상태를 보존한다. 10월 1일에 열린 고전 규칙 포지션은 마지막 1m close로 강제청산하고 exit 비용을 낸다. R2-9b/R2-20은 원 출처대로 fold TEST 끝을 넘는 fixed-horizon 신호를 폐기하며 horizon을 줄이거나 강제청산하지 않는다.

`global_ls_account` 등 metrics archive의 `create_time`을 availability time으로 간주하며 추가 publication lag는 두지 않는다. `next_funding_rate`는 미래 정산률이 아니라 마지막 settled rate 반복값이다. 이 가정은 결과 후 바꾸지 않는다.

## 3. 모델 walk-forward 고정

fold는 667–697이다. fold 667 TEST는 `[07-01,07-04)`, 이후 3일씩 전진하고 fold 697만 `[09-29,10-01)` 2일이다. 각 fold STOP은 TEST 직전 3일이다.

- PatchTST: TRAIN은 STOP 직전 rolling 180일, STOP 3일, TEST 3일(마지막 2일). seed 42/43/44, lookback 60, span 15, AdamW lr=1e-3, weight_decay=1e-5, batch=1024, max_epochs=15, patience=3. TRAIN scaler만 사용한다. STOP의 두 head MAE 평균이 1e-6보다 개선될 때만 best epoch를 갱신한다. 세 seed TEST 예측을 산술평균한다. 같은 fold STOP excursion 예측의 q90을 `linear`로 계산하고 TEST 예측 `>=q90`을 통과시킨다. target span이 phase end를 넘는 origin은 폐기한다.
- R2-9b V0: LONG h=120/SHORT h=60 binary CatBoost, iterations=500, depth=4, lr=.05, l2=3, seed=20261001. 모든 과거 행 중 `signal_index+h < STOP_start`인 expanding TRAIN만 사용한다. 피처 선택은 해당 TRAIN에서만 원 규칙대로 매 fold 다시 수행한다. V1–V6 재선택·평균·STOP 튜닝은 금지한다.
- R2-9b tail: fold k는 fold<k OOS score만 사용한다. EXPANDING은 전부, ROLLING_180D는 현재 fold 최초시각 직전 180일만 사용하며 n>=2,000이어야 한다. 현재 fold score는 다음 fold부터 history에 들어간다. 선택 후보는 ROLLING_180D q=.01 SIDE뿐이다.
- R2-20: 4h h=480 binary long/short CatBoost, iterations=500, depth=4, lr=.05, l2=3, seed=20261001. `decision_time+480m < STOP_start`인 모든 과거 행의 expanding TRAIN, TRAIN-only 피처 선택을 쓴다. PatchTST gate는 4h 결정시각보다 엄격히 이전인 마지막 gate만 쓴다. tail은 이전 fold score만 history에 추가하고, 현재 fold 안에서는 180일 밖 행의 aging-out만 허용한다. q=.02 linear 98% SIDE cutoff다.

이전 HOLD_A fold의 완료된 라벨은 현재 fold의 위 purge를 통과할 때만 TRAIN/STOP에 들어간다. 이전 HOLD_A 성과·손익은 어떤 선택·튜닝·중단에도 쓰지 않는다. fold 697에서 10월 1일 이후 target/exit이 필요한 origin은 폐기한다.

PatchTST 장치는 원 출처(`out/run_patchtst_excursion_range.py:36`)대로 CUDA다(NVIDIA GeForce RTX 3090, torch 2.13.0+cu126, CUDA 12.6, cuDNN 91002). 원 소스에 결정론 옵션이 없었으므로 추가하지 않는다. CUDA가 없으면 CPU로 넘어가지 않고 중단한다. torch intra-op thread 8, inter-op 1. R2-9b V0 CatBoost만 원 설정 `thread_count=-1`(논리 코어 32)이며 CPU 8 상한의 명시적 예외다. R2-20 CatBoost는 원 설정 `thread_count=6`이다. 환경 기록이 입력/환경 manifest와 한 항목이라도 다르면 시작하지 않는다.

재현 근거(전부 HOLD_A 이전): R2-28에서 PatchTST fold 666 seed 573행·ensemble 191행, R2-9b V0 fold 666 50행이 원 출력과 exact이고 2회 실행 차이 0. R2-29/R2-30에서 같은 러너 코드를 달력만 바꿔 `[2026-04-01, 2026-07-01)`에 적용한 리허설이 PatchTST gate 8,801, R2-9b score 1,356/1,364, R2-20 score 490, tail 통과 11/8, 고전 규칙 거래 46/18/109, FIRST 조합 51/53/115행 모두 원 출력과 exact(최대 차이 0)였다. 리허설 성과 숫자는 HOLD_B 값이며 판정에 쓰지 않는다.

R2-9b 피처 중 미시구조 `m_*` 23개의 Q3 입력은 `data.binance.vision` USD-M BTCUSDT 일별 아카이브(수집 2026-10-05T03:02Z)에서 기존 빌더(`out/build_{book,liquidity,spread,trade}_features.py`) 계산 그대로 만들었다. bookDepth 92/92, aggTrades 92/92 CHECKSUM 일치. bookTicker는 Q3 92일 전부 아카이브에 없어 `m_spread_valid=false`, spread 값 NaN으로 두고 대체하지 않는다(원 2026-06도 43,200/43,200행 invalid). rolling/surge는 H1 말 이력에서 연속 계산했고 2026-06 재계산 패리티 불일치 0이다. 파일: `artifacts/hold_a_2026q3/micro_{book,liquidity,spread,trade}_2026q3.parquet`.

입력/환경 manifest에는 모든 입력 파일, 환경 기록, 러너가 import하는 프로젝트 모듈(`out/`, `btcusdt_quant/`) 86개의 SHA256이 들어 있다. 하나라도 없거나 다르면 시작하지 않는다.

예측 산출물에는 실현 target·return·PnL 컬럼을 넣지 않는다. 31 folds의 예측을 모두 닫고 SHA256을 기록한 뒤에만 별도 평가 단계에서 라벨/가격/정산을 결합한다. resume은 fold 입력·코드·환경 hash가 모두 같을 때만 허용한다.

전용 평가 러너 SHA256: `out/run_k45_hold_a_eval_r2_27.py` `a87c5cd90acb6f42e90be18e3ec197f0a8ace99ee42f8e3e16e8361ac2697f25`
전용 테스트 SHA256 및 통과 명령: `tests/test_k45_hold_a_eval_r2_27.py` `49bb66462d1f93574b57393d75371b0c03467dfa4446aabb8d88748ac6395f59`, `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q` 결과 28 passed
입력/환경 manifest SHA256: `out/k45_hold_a_runner_complete_r2_29_20261005/input_environment_manifest.json` `bde07617d8989b0909b3b9620c099ac9ebf3ec38a51d431af2f27dd252435484`

실행 명령(FROZEN 커밋 후): `venv_btcusdt\Scripts\python.exe out/run_k45_hold_a_eval_r2_27.py predict` 다음 `... evaluate`. 출력 `out/k45_hold_a_eval_r2_29/`.

## 4. 사전 가설과 판정

비용 4bps에서 H-A1만 주 가설이다.

- H-A1: H3(C1)의 `total_net_bps > 0`.
- H-A2: H1의 `total_net_bps > 0`.
- H-A3: H2의 `total_net_bps > 0`.
- H-A4: H3의 MTM daily Sharpe가 H1보다 엄격히 크다.
- H-A5a: H4의 `total_net_bps > 0`.
- H-A5b: H5의 `total_net_bps > 0`.

PESS·OPT가 둘 다 참이면 CONFIRMED, 둘 다 거짓이면 REJECTED, 하나만 참이면 BOUNDARY_DEPENDENT다. 0은 실패다. daily Sharpe는 92개 UTC calendar day와 무거래일 0을 포함해 `mean/std(ddof=1)*sqrt(365)`로 계산한다. std=0은 UNMEASURABLE이며 확인 실패다. 보조 가설은 다중검정 보정 없는 서술 결과다.

## 5. 사전 기대치(DEV_COMMON, HOLD_A 미사용)

DEV_COMMON의 1,676개 겹치는 92일 창에서 비용 4bps MTM net>0 비율은 H1 78.94/79.00%, H2 64.02/64.02%, H3 78.58/78.70%, H4 79.00/79.30%, H5 72.08/72.26%, B0 52.21/52.21%(PESS/OPT)였다. 92일 예상 거래 수는 H1 37.3, H2 16.8, H3 44.7, H4 52.5, H5 102.0, B0 1이다. 이는 겹치는 선택구간의 경험 빈도이지 p-value나 귀무가설 확률이 아니다.

## 6. 필수 보고

후보×PESS/OPT×비용 4/8/12 기본 항목에 다음을 추가한다: 모든 hash·환경·fold666 parity; fold별 TRAIN/STOP/TEST·행 수·최대 라벨시각·피처·seed·best epoch·STOP loss·q90; tail history n/start/end/cutoff; 신호→gate→tail→boundary→fill→FIRST 단계별 수; carry-in·강제청산·경계폐기; gross/cost/funding 분해와 PESS-OPT 차이 사건; 92일 일별 원장/거래 원장 parity; fold별 net; 기술 실패·재실행 이력.

## 7. 실패 규칙

HOLD_A 값을 열기 전의 동일 binary·동일 입력 재실행만 기술 재현으로 허용한다. hash/parity/schema/fold/seed 하나라도 실패하면 결과를 열지 않고 NO_VERDICT로 종료한다. 장치·batch·seed·학습창·피처·경계규칙을 바꾸는 재실행은 금지한다. 설정 변경이 필요하면 HOLD_A 판정을 포기하고 새 외부 구간을 기다린다.

## 8. 정직성 메모

- 이 후보들은 DEV와 HOLD_B를 본 뒤 정해졌다. HOLD_A만이 선택에 쓰이지 않은 구간이다.
- 92일은 짧다. DEV_COMMON 기준 92일 예상 거래 수는 H2 16.8회, H1 37.3회 수준이다. DEV에서도 92일 창의 약 21%(H1)는 net<=0이었다. 결과 하나로 예측력 입증이라고 확대하지 않는다.
- DSR(813회 보정)은 모든 후보가 0.13 이하였다. HOLD_A 결과와 무관하게 이 사실은 유지된다.
- R2-25 이웃 조합 강건성 가설(>=70%)은 17/81로 실패했다. HOLD_A 결과와 무관하게 유지된다.
- 고전 규칙(기간 끝 강제청산)과 모델 규칙(fold 경계 거래 폐기)의 경계 처리는 비대칭이다. 출처 그대로를 우선해 유지하고 수량을 공개한다.
