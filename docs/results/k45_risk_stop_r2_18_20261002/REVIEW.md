# R2-18 BRIEF 검토 (2026-10-02)

검토 대상: docs/results/k45_risk_stop_r2_18_20261002/BRIEF.md (7,817 bytes, 18:08)
방식: 브리프가 참조하는 파일·칸이 디스크에 실제로 있는지 확인하고, 규칙 정의에서 빠지거나 겹치는 곳을 적음.

## 1. 참조 확인 (디스크 대조)

| 참조 | 결과 |
|---|---|
| R2-14 F4\|1h\|5/4\|signal\|LS | 있음. DEV n 3,329 / 총 +8,837 / Sharpe 0.48, HOLD_B n 348 / +4,364 / 2.69. 평균 보유 236분 |
| R2-14 F3\|1h\|10/4\|signal\|S | 있음. DEV n 2,140 / +9,333 / 0.61, HOLD_B n 108 / +260 / 0.29. 보유 240분 |
| R2-14 G2\|1m\|before/60/60\|signal\|L | 있음. DEV n 713 / +5,553 / 0.79, HOLD_B n 207 / +680 / 0.96. 보유 120분 |
| R2-14 E1\|1h\|2\|signal\|L | 있음. DEV n 583 / +15,518 / 1.01, HOLD_B n 49 / +1,918 / 2.28. 보유 1,200분 (브리프의 "원래 보유 1,200분"과 일치) |
| R2-12 1h / h=60 / 15m / E1 k=1.0 / gate=True | 있음. DEV n 1,428 / +3.76, HOLD_B n 150 / +14.11 |
| R2-12 1h / h=120 / 30m / E1 k=1.0 / gate=True | 있음. DEV n 1,038 / +6.88, HOLD_B n 126 / +9.31 |
| R2-7 regression_rmse, q 0.01/0.05, EXPANDING_OOS / ROLLING_180D, SINGLE | 이름 모두 manifest에 있음 (variants, methods, q, books) |
| artifacts/btcusdt_2026q3.parquet | **없음** |
| artifacts/btcusdt_2026q3_source/ | 있음. 1분봉 kline zip만 (2026-07, 2026-08, 2026-09-01 ~ 09-29). premium_index, global_ls_account, funding_rate 없음 |

## 2. 수정이 필요한 곳

1. **HOLD_A 데이터 경로가 없음.** btcusdt_2026q3.parquet가 없고, 있는 것은 kline zip뿐이다.
   - F3·F4·G2: premium_index / global_ls_account / funding 없음 → HOLD_A 계산 불가.
   - E1: OHLCV만으로 신호는 가능하지만 펀딩 반영 불가.
   - MTF·TAIL: 2026 Q3 모델 예측이 없고 재학습·추론 금지 → 계산 불가.
   - 이 zip은 HOLD-A 철회(2026-10-01, "있는 데이터로만") 이전에 내려받은 것이다. 쓸지 말지는 사용자 결정 사항. 쓴다면 data_cutoff가 2026-06-30에서 바뀌므로 manifest에 따로 적어야 한다.
2. **후보 목록이 HOLD_B를 본 뒤 정해졌다.** F4 LS(HOLD_B Sharpe 2.69), E1 z2(2.28), MTF 칸(R2-12 6필터에 HOLD_B 포함) 등. 그런데 동결 가설 (a)가 "HOLD_B net > 0"을 요구한다. 브리프에 "이미 본 구간" 표기는 있지만, 가설 판정에 HOLD_B를 넣으면 판정이 독립적이지 않다.
   - 제안: 가설 판정은 DEV / DEV_EX2020만, HOLD_B는 별도 표기.
3. **"BASE 조합" 정의가 없다** (가설 (d)). 제안: 같은 selected_cells의 BASE 버전으로 같은 조합 방식(COMBO_SINGLE)을 돌린 것.
4. **진입 1분봉 손절 미판정은 낙관 쪽 가정이다.** 진입 분 안에서 손절가에 닿은 경우를 놓친다. 제안: 진입 분의 저가(롱)/고가(숏)가 손절가에 닿으면 손절로 치는 보수 버전을 같이 보고(표만).
5. **ATR 기준 봉과 보유 길이 차이.** 1h ATR(14) × 1.5는 대략 수십~150 bps. R-TAIL(45분), R-G2(≤120분)에서는 손절이 거의 안 걸릴 수 있다. 결과에서 청산 사유 비율로 확인하면 되므로 규칙 변경은 불필요, 해석 시 참고.
6. **이전 기록과의 관계.** 이전 세션 메모리 기록(날짜·원본 파일은 이번 점검에서 확인하지 않음): "손절은 롱 팔을 해쳤다(matched −4.11 bps), stop 폭 재탐색 금지". 이번은 사용자 지시로 ATR 1.5 고정이고 {1.0, 2.0}은 표만이라 충돌은 아님. REPORT에서 이전 결과와 나란히 비교 권장.
7. **브리프 위치.** docs/results/ 는 out/ 결과를 내보내는 폴더다. 실행 시 out/k45_risk_stop_r2_18_20261002/BRIEF.md 로 두는 것이 다른 실험과 같은 구조.
8. **CPU.** 지금 R2-9b(16 워커), R2-15, R2-17이 돌고 있다. 4 워커 제한이 있어도 R2-17 종료 후 시작하는 편이 다른 실험 속도에 영향이 적다.

## 3. 문제 없음으로 확인한 곳

- 재현 확인 → 불일치 시 정지 규칙.
- selected_cells를 HOLD_B 계산 전에 manifest에 기록하고 SHA256 남기기, 테스트 (vii).
- 240분 상한, 손절가 고정, 갭 시 시가 체결, 손절 후 다음 신호부터 재진입.
- COMBO_SINGLE / COMBO_HEDGE 정의, 동시 보유 테스트.
- 펀딩 구간 정의(entry < funding ≤ exit)는 R2-6~R2-9과 같은 정의.
