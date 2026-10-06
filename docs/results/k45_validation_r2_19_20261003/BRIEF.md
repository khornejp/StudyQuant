Repo: D:\StudyQuant. R2-19: 검증 정합성 복구 + 후보 재평가. 설계·구현·실행·보고 끝까지, 결과로 거르지 말고 있는 그대로 전부 보고.

계획서(이 문서가 기준, 그대로 따를 것): docs/superpowers/plans/2026-10-03-validation-integrity-r2-19.md
검토 근거: scripts/BTCUSDT_RESULTS_LIVE_READINESS_REVIEW_KO.md (외부 검토. 계획서의 "검토 지적 확인 결과" 표에 있는 항목만 반영)

실행 규칙
- 계획서 Task 1 → 6 순서. 각 Task는 테스트 먼저(TDD), 실패 확인, 구현, 통과 확인.
- git commit 금지(검토자가 커밋). out/ 아래에만 코드·결과 작성. tests/ 테스트 파일 작성.
- 계획서의 예시 코드·테스트는 2026-10-03에 통과 확인됨. 그대로 쓰되, 계약(테스트)을 바꾸지 마라.
- Task 2: out/run_patchtst_k45_flow_inference.py 의 optimal_block_length / stationary_bootstrap_errors 를 import (복제 금지).
- Task 5: 펀딩 아카이브 zip CSV의 실제 열 이름을 확인해서 쓰고 manifest에 기록. 추측 금지.
- Task 6: 재현 확인(R2-14 all_cells와 n·net 차이 0)이 실패하면 멈추고 원인 보고.
- 동결 후보·동결 가설은 계획서 Task 6 그대로. 실행 전에 manifest에 기록.
- 로컬 데이터만, 다운로드 금지, HOLD_A·2026-07 이후 데이터 읽기 금지, live 0, cutoff 2026-06-30 23:59 UTC.
- CPU 워커 최대 4.
- 출력: out/k45_validation_r2_19_20261003/ (REPORT.md 숫자만, 해석 형용사 금지, 5,000줄 이하; parquet; manifest.json 입력·출력·소스 SHA256, 시각, cutoff, 동결 가설, OOS 결과).
- Python: venv_btcusdt\Scripts\python.exe
마지막 출력: Task별 테스트 결과, 재현 확인, 펀딩·롱숏 감사 결과, 후보별 평가손익 MDD·Sharpe(기존 대비), PW 자동 블록 CI(기존 대비), DSR, 사건·주 단위 집중도, 무작위 대비, 비용 12 bps, 가설 판정, 소요 시간.
