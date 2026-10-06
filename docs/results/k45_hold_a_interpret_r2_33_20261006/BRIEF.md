Repo: D:\StudyQuant. R2-33: HOLD_A 결과 해석(적대적) + 정리. 사용자 결정: 추가 검증 구간은 없다. 이 해석으로 실제 퀀트 시스템에 무엇을 넣을지 정한다.

입력:
- out/k45_hold_a_exclude_bookticker_r2_32_20261005/REPORT.md, hold_a/REPORT.md, hold_a/{metrics,trades,daily_pnl}.parquet, historical_metrics.parquet, fold_comparison.parquet
- DEV/HOLD_B 원 출력: out/k45_candidate_compare_r2_23_20261004, out/k45_single_book_combo_r2_24_20261004, out/k45_combo_robust_r2_25_20261004
- 고정 문서 docs/hold_a/2026-10-05_hold_a_freeze.md (DRAFT v3; 평가는 FROZEN 없이 사용자 결정으로 수행)

# 절대 금지
- 새 데이터 다운로드, 주문·인증·지갑. git commit 금지.
- HOLD_A 결과를 보고 후보·파라미터를 골라 "HOLD_A 성과"로 재보고하지 마라. HOLD_A는 이미 본 구간이다. 새 변형의 성능은 DEV에서만 계산하고 HOLD_A 값은 참고로만 병기, "HOLD_A 사후" 라벨.
- 결론을 단정하지 말고 숫자 먼저. 각 주장은 근거 파일:행 또는 계산값.

# 해석 과제 (항목별 표: 주장, 근거 수치, 반대 근거, 남는 불확실성)
1. 베타 분해: 모든 후보가 B0(+3,381.7 bps)보다 낮다. 각 후보의 일별 MTM net을 B0 일별 수익에 회귀(알파·베타, HAC 표준오차)하라. DEV_COMMON, HOLD_B, HOLD_A 각각. 롱 노출 비율·숏 기여도 분리.
2. E1 의존: C1 HOLD_A net의 대부분이 E1(+1,311)에서, F3는 +65. DEV에서도 그런가? E1 성과를 시장 국면(B0 30일 수익 상·중·하 3분위, 변동성 3분위)별로 DEV에서 분해. HOLD_A 국면이 DEV 어디에 해당하는지.
3. F3 약화: F3 거래당 net DEV 42.3 → HOLD_B 15.5 → HOLD_A 13.0. 연도별·반기별 DEV 추세로 decay가 있는지(롤링 6개월 거래당 net, 추세 기울기와 CI).
4. 집중도: 상위 1–2건 제외 시 F3/C1/C3/C4가 음수. DEV에서 92일 창 기준 "상위 2건 제외 net>0" 비율은? HOLD_A가 DEV 분포상 어디인지(백분위).
5. 표본: HOLD_A 거래 22–40건, PW 하한 전부 음수. DEV 92일 창 분포 대비 HOLD_A 결과 백분위(net, Sharpe) — 기대치 안/밖.
6. H5(C4) 8bps 음수, F3-w30 기여 −934: DEV 대비 이례적인지.
7. 종합: 시스템에 넣을 후보 선택지 2–3개(예: C1 / E1 단독 / C3 / 없음)별 근거·위험·DEV 지표·HOLD_A 사후 지표 표. 권고는 하나만 하되 "Codex 의견"으로 명시, 사용자 결정 사항으로 남긴다.

# 정리 과제
8. 보고서 라벨 버그: R2-32 hold_a/REPORT.md "DEV_COMMON HOLD_B side by side" 표에서 HOLD_A 값 열 접두사가 `REHEARSAL_`로 잘못 붙음. 러너 out/run_k45_hold_a_eval_r2_27.py 의 해당 라벨 생성만 고치는 패치를 적용하고(값 로직 변경 금지), 기존 산출물은 덮어쓰지 말고 이 폴더에 라벨만 고친 사본 표를 생성. 테스트 추가, 전체 테스트 통과.
9. 감사 스크립트 scripts/audit_k45_experiments.py 의 TESTS/claims에 R2-27~R2-32 추가(출력 hash, 테스트 재실행, REPORT head, 다음 주장 대조: R2-32 HOLD_A 4bps PESS total_net H1 365.221046, H2 1503.528994, H3 1376.416586, H4 1397.682266, H5 400.702128, B0 3381.737936; 가설 6개 CONFIRMED; LONG exact fold 581/621, SHORT 621/621). 실행해 docs/audit/ 갱신.
10. 고정 문서 사실 기록안: docs/hold_a 문서에 덧붙일 "실행 기록" 절 문구를 REPORT에 제안만(파일 수정 금지): FROZEN 없이 평가, bookTicker 제외, 기술 실패 3건, 최종 hash.

# 출력
out/k45_hold_a_interpret_r2_33_20261006/REPORT.md — 맨 앞 숫자 표(1–6), 종합표(7), 정리 결과(8–10). manifest.json(source, timestamp, data cutoff, HOLD_A 사용 = 사후 서술용). 대용량 표는 parquet/csv.
Python: venv_btcusdt\Scripts\python.exe. pytest `--basetemp=.pytest_tmp_r2_33`. CPU 워커 최대 8.
