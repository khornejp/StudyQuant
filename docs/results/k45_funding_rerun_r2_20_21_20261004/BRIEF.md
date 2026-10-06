Repo: D:\StudyQuant. R2-20, R2-21을 새 펀딩 모듈(out/k45_funding.py)로 다시 실행. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고. 판정보다 숫자를 먼저.

# 배경
- R2-22(out/k45_funding_fix_20261004/REPORT.md)에서 공통 펀딩 모듈을 만들었다: 아카이브 정산을 예정 정각(UTC 00/08/16)으로 정규화, cashflow = −side × rate × 1e4, 경계 정산(진입·청산 시각 == T)은 PESS(음수만)·OPT(양수만) 두 값.
- R2-20, R2-21은 r26 loader(아카이브 raw ms 시각)로 펀딩을 계산했다. R2-22 확인에서 칸별 펀딩 합 차이: R2-20 중앙 PESS −8.0 / OPT +1.2 bps, R2-21 중앙 PESS −66.8 / OPT +66.7 bps.

# 할 일
1. out/run_k45_mtf_tail_r2_20.py, out/run_k45_patchtst_updown_r2_21.py 의 손익 펀딩 경로를 out/k45_funding.py 로 바꾼다(호출부 시그니처 유지, 복제 금지). 출력 폴더 인자(환경변수) 추가.
2. 재학습 금지. R2-21은 기존 체크포인트·예측(out/k45_patchtst_updown_r2_21_20261003/ 의 ensemble_predictions, evaluated_predictions, thresholds 등)을 그대로 쓰고 평가(거래·기준선·무작위·가설)만 다시 한다. R2-20은 원래 학습이 없다.
3. 각 실험을 PESS, OPT 두 번 실행. 출력:
   out/k45_funding_rerun_r2_20_21_20261004/r2_20_{PESS,OPT}/, r2_21_{PESS,OPT}/
   기존 결과 폴더는 덮어쓰지 마라.
4. 동결 가설·격자·선택 규칙은 원 BRIEF.md(out/k45_mtf_tail_r2_20_20261003/BRIEF.md, out/k45_patchtst_updown_r2_21_20261003/BRIEF.md) 그대로. R2-20의 R2-12 재현 확인은 "원 R2-12 값(구 펀딩)"과 비교하면 펀딩 차이만큼 다를 수 있으니, 거래 수 일치 + 펀딩 제외 gross 일치로 확인하고 그 방식을 보고.
5. 테스트: 기존 tests/test_k45_mtf_tail_r2_20.py, tests/test_k45_patchtst_updown_r2_21.py 가 새 경로로 통과해야 한다. 펀딩 정의를 고정한 테스트가 있으면 새 정의로 고치고 무엇을 바꿨는지 보고. 필요하면 테스트 추가(경계 PESS/OPT 부호).

# 보고 (out/k45_funding_rerun_r2_20_21_20261004/REPORT.md, 숫자만, 5,000줄 이하)
- 실험별 구 펀딩 / PESS / OPT 비교: 칸 수, 칸별 net 차이 분포, 부호 바뀐 칸 수·목록, 경계 정산 거래 수와 그 펀딩 합(PESS/OPT).
- R2-20: 가설 판정(구/PESS/OPT), 두 구간 양수 칸 수, DEV CI 하한 > 0 칸 수, 사건 상위 5개 제외 후 양수 칸 수, 항상 롱 초과 칸 수, SPA p.
- R2-21: 가설 판정(구/PESS/OPT), 방향 거래 칸 DEV net 범위, fade 대비 차이, 게이트별 요약.
- "확정"(PESS·OPT 결론 같음) / "경계 의존" 목록.
- manifest.json: 입력·출력·소스 SHA256, 시각.

# 제약
- 로컬 데이터만. 다운로드 금지. live 0. git commit 금지. HOLD_A·2026-07 이후 금지. cutoff 2026-06-30 23:59 UTC.
- CPU 워커 최대 12. GPU 불필요.
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: 테스트 결과, 실험별 구/PESS/OPT 요약, 확정/경계 의존 목록, 소요 시간.
