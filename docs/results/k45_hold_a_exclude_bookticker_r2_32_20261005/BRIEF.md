Repo: D:\StudyQuant. R2-32: R2-9b 피처 후보에서 bookTicker 파생 피처 6개 제외 + 리허설 확인 + HOLD_A 계산을 한 번의 실행으로. (R2-31 검토는 사용자 지시로 중단됨, 반영 대상 아님)

# 사용자 결정 (2026-10-05)
- bookTicker는 2024-04 이후 공개 아카이브에 없고 앞으로도 구할 방법이 없다. 구할 수 없는 데이터에 의존하는 모델은 쓰지 않는다. 따라서 R2-9b V0 피처 후보에서 아래 6개를 영구 제외한다:
  `m_spread_valid, m_spread_bps_mean, m_spread_bps_max, m_spread_bps_std, m_top_imbalance_mean, m_quote_update_count`
- bookDepth(m_book_* 6개), aggTrades(m_trade_*, m_liquidity_* 등)는 유지.
- 새 피처(예: bookDepth ±0.2% 대용 불균형) 추가 금지. 다른 설정 변경 금지.
- 영향 후보는 H4(C3) 안의 R2-9b SIDE|ROLLING_180D|q=0.01|L=120|S=60|V0 뿐. H1/H2/H3/H5, R2-20, PatchTST는 바꾸지 마라.

# 사용자 결정 2 (2026-10-05): HOLD_A 계산 포함
- bookTicker 제외로 결측 입력이 없으므로 HOLD_A [2026-07-01, 2026-10-01)도 이번에 계산한다. 고정 문서는 FROZEN으로 만들지 않는다(DRAFT 유지, 사용자 지시).
- 러너의 FROZEN 가드는 이번 실행에 한해 명시적 플래그(예: `--allow-draft-user-2026-10-05`)로만 우회하고, manifest에 `freeze_status=DRAFT`, `freeze_guard_bypassed=true`, 사유 "user decision 2026-10-05"를 기록. 다른 가드(입력 hash, 환경, dependency, 스키마, CUDA, closed prediction manifest)는 그대로 통과해야 한다.
- 순서: 과제 1–6(재학습·비교·리허설 exact) 완료 → 그 뒤 HOLD_A predict(fold 667–697) → evaluate. 리허설 exact가 깨지면 HOLD_A 실행하지 말고 중단·보고.
- HOLD_A 결과를 본 뒤 후보·설정·규칙을 바꾸거나 재실행하지 마라. 기술 실패는 값 열기 전 동일 설정 재실행만.
- 보고: 숫자 먼저, 거르지 말고 전부. 문서 4절 가설은 기계 판정 결과만 표로. 서술적 결론·평가 문장 금지.

# 절대 금지
- docs/hold_a/ 수정 금지(문구 제안은 REPORT에). git commit 금지. 다운로드·주문 금지.
- 기존 원 출력 폴더(out/k45_gate_direction_r2_10b_20261001, out/k45_candidate_compare_r2_23_20261004, out/k45_single_book_combo_r2_24_20261004 등) 덮어쓰기 금지. 새 결과는 이 폴더 아래에.

# 과제
1. R2-9b V0(LONG h=120, SHORT h=60) 를 원 절차·원 파라미터(CatBoost 500/depth4/lr.05/l2 3/seed 20261001/thread_count=-1, expanding TRAIN, `signal_index+h < STOP_start` purge, TRAIN-only 피처 선택)로, 피처 후보에서 6개만 뺀 채 원 fold 전체(DEV+HOLD_B, 원 출력에 있는 모든 fold) 다시 학습·예측. 원 코드 경로를 재사용하고 제외는 피처 후보 목록 필터 한 곳으로만.
2. 비교표: fold별 선택 피처 동일 여부, 점수 exact 여부, 최대 차이. 특히 bookTicker 피처가 원래 선택되지 않은 fold(원 기록상 fold 347 이후 전부)가 exact인지. exact가 아니면 원인(선택 방식이 후보 집합에 의존하는지 등)을 소스로 설명. 기준 완화 금지, 그대로 보고.
3. 새 점수로 R2-9b tail(ROLLING_180D q=.01 SIDE, 원 규칙), 거래, 그리고 C3 FIRST 조합을 다시 계산해 DEV_COMMON·HOLD_B 지표(PESS/OPT, 4/8/12 bps: 총 net, 거래 수, Sharpe, MDD, PW CI 하한, R2-23과 같은 정의)를 원 값과 나란히. R2-9b 단독도. 우선순위 manifest_frozen.json은 그대로(재순위화 금지). 92일 rolling net>0 비율(R2 freeze review 6절과 같은 방법)도 C3 새 값으로.
4. (삭제: R2-31 중단됨)
5. 러너 out/run_k45_hold_a_eval_r2_27.py 를 새 R2-9b 기준 출력(이 폴더의 새 예측 파일)과 제외 목록으로 갱신. selfcheck의 R2-9b 기준(fold 666 재현 등)도 새 기준 출력으로. 입력/환경 manifest 재생성(dependency_sources, environment 포함, execution_ready는 사전검사 통과 시 true) — 새 경로는 이 폴더 아래.
6. 리허설 [2026-04-01, 2026-07-01) 재실행(HOLD_A보다 먼저): PatchTST/R2-20/고전 규칙/C1/C5 계열은 원 출력과 exact, R2-9b·C3는 새 기준 출력과 exact. 테스트 갱신·통과(제외 목록이 피처 후보에 없음을 테스트로 고정), selfcheck PASS.

# 출력
out/k45_hold_a_exclude_bookticker_r2_32_20261005/REPORT.md — 맨 앞: (a) fold 비교표 요약(exact fold 수/전체, 달라진 fold 범위, 최대 차이) (b) R2-9b 단독·C3 원 vs 새 지표 표(숫자 먼저, 서술 결론 금지) (c) (없음) (d) 리허설 exact 표 (e) HOLD_A 결과: 후보 H1–H5·B0 × PESS/OPT × 4/8/12 bps 전체 표, 문서 6절 보고 항목 전부, 4절 가설 기계 판정, DEV_COMMON·HOLD_B와 나란히 (f) 고정 문서 수정 문구 제안 (g) 러너·테스트·입력/환경 manifest SHA256, 테스트 명령·결과. manifest.json(source, timestamp, data cutoff 2026-06-30T23:59Z, frozen hypothesis = docs/hold_a/2026-10-05_hold_a_freeze.md 4절(DRAFT, 미고정), freeze_guard_bypassed=true, hold_a_values_computed=1, out-of-sample result).
Python: venv_btcusdt\Scripts\python.exe. pytest `--basetemp=.pytest_tmp_r2_32`. CPU 워커 최대 8(R2-9b 학습만 thread_count=-1 예외). 진행 로그 남기기.
