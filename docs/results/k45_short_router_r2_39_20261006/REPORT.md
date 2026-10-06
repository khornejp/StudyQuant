# R2-39 숏 강화 + 전략 선택 router

## C1_X 기준선

| segment | role | c1_x_trade_n | c1_x_net_bps | old_t_open_net_bps | entry_delay_delta_bps | c1_x_sharpe | c1_x_pw_low | c1_x_mdd_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV_COMMON | baseline | 870 | 34028.0281 | 35085.6149 | -1057.5868 | 1.6268 | 8.7155 | 4206.5331 |
| HOLD_B | baseline | 88 | 2717.5092 | 2670.1360 | 47.3732 | 1.7194 | -10.7701 | 1248.1578 |
| HOLD_A_POSTHOC | 사후 | 37 | 1377.7010 | 1374.0542 | 3.6468 | 1.8508 | -21.9104 | 705.6327 |

## 1단계 결과

| candidate | stand_n | stand_net | stand_pw_low | stand_top2 | stand_dsr12 | stand_dsr5050 | overlay_delta | overlay_pw_low | delta_dsr12 | delta_dsr5050 | overlay_8bps | dev_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 274 | 9597.1551 | -0.9072 | 5467.7103 | 0.0854 | 0.0000 | 0.0000 |  |  |  | 30548.0281 | False |
| S2 | 184 | -817.2898 | -5.2404 | -3290.3970 | 0.0009 | 0.0000 | -2742.2870 | -4.8061 | 0.0403 | 0.0023 | 27477.7411 | False |
| S3 | 178 | 1610.0822 | -1.0122 | 568.4992 | 0.0130 | 0.0000 | -417.0258 | -2.0528 | 0.1393 | 0.0146 | 29591.0023 | False |
| S4 | 4 | 1164.1369 | -0.4482 | -63.7146 | 0.0022 | 0.0000 | -381.8123 | -0.4299 | 0.0000 | 0.0000 | 30162.2158 | False |
| S5 | 337 | -2976.2681 | -6.1956 | -5279.3441 | 0.0001 | 0.0000 | -4839.7616 | -6.2669 | 0.0053 | 0.0001 | 25130.2665 | False |
| S6 | 16 | -732.5056 | -0.9896 | -1361.3853 | 0.0000 | 0.0000 | -1140.5418 | -1.6036 | 0.0001 | 0.0000 | 29375.4864 | False |

## decision

`{"decision": "SHORT_STAGE_FAIL", "winner": null, "hold_b_result": null, "final_decision": "SHORT_STAGE_FAIL"}`

HOLD_B/HOLD_A는 DEV winner를 바꾸거나 실패 후보를 구제하지 않았다.

## 2단계 결과

| model | trade_n | net_bps | absolute_pw_low | paired_net_bps | paired_pw_low | paired_dsr_m2 | paired_dsr_m5050 | hac_alpha | hac_alpha_low | top2_removed | net_8bps | random_percentile | dev_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ridge | 850 | 9259.4263 | -2.2778 | -7831.4774 | -14.3253 | 0.0271 | 0.0038 | 8.5282 | -1.9393 | 7108.8208 | 5859.4263 | 0.0000 | False |
| small_boosting | 656 | 10257.0336 | -0.6159 | -6833.8701 | -14.6579 | 0.0564 | 0.0100 | 8.8164 | -0.7916 | 8056.8598 | 7633.0336 | 0.0000 | False |

`{"decision": "ROUTER_DEV_FAIL", "winner": null, "hold_b_result": null, "final_decision": "ROUTER_DEV_FAIL"}`

## HOLD_B 확인 결과

(없음)

DEV winner가 없으면 해당 단계 HOLD_B는 열지 않았다.

## HOLD_A 사후 표

| stage | book | trade_n | total_net_bps | paired_net_bps | daily_sharpe | top2_removed_net_bps | label |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | C1_X | 37 | 1377.7010 |  | 1.8508 | -277.9264 | 사후 |
| baseline | C1_T_OPEN | 37 | 1374.0542 |  | 1.8432 | -295.0377 | 사후 |
| baseline | F3 | 27 | 405.4801 |  | 0.6189 | -825.5286 | 사후 |
| baseline | F3-w30 | 105 | -39.3249 |  | -0.0560 | -921.6086 | 사후 |
| baseline | E1 | 22 | 1635.5190 |  | 3.3903 | 323.3776 | 사후 |
| short_stage | S1 | 4 | -595.4801 |  | -3.4218 | -390.7434 | 사후 |
| short_stage | overlay_S1 | 37 | 1377.7010 |  | 1.8508 | -277.9264 | 사후 |
| short_stage | S2 | 2 | -56.8303 |  | -0.6487 | 0.0000 | 사후 |
| short_stage | overlay_S2 | 39 | 1352.0126 |  | 1.8091 | -302.0149 | 사후 |
| short_stage | S3 | 19 | -624.8978 |  | -3.8050 | -879.0787 | 사후 |
| short_stage | overlay_S3 | 53 | 546.1867 |  | 0.6991 | -1242.1049 | 사후 |
| short_stage | S4 | 0 | 0.0000 |  |  | 0.0000 | 사후 |
| short_stage | overlay_S4 | 37 | 1377.7010 |  | 1.8508 | -277.9264 | 사후 |
| short_stage | S5 | 20 | 167.2826 |  | 0.6387 | -266.9716 | 사후 |
| short_stage | overlay_S5 | 50 | 1856.5910 |  | 2.4370 | 207.6767 | 사후 |
| short_stage | S6 | 5 | 30.5482 |  | 0.3308 | -137.1972 | 사후 |
| short_stage | overlay_S6 | 41 | 1603.1433 |  | 2.1610 | -48.5630 | 사후 |
| router_stage | ridge | 50 | 765.0067 | -612.6943 | 1.1209 | -366.1728 | 사후 |
| router_stage | small_boosting | 23 | 440.7467 | -936.9544 | 0.7595 | -672.3857 | 사후 |

전 행은 **사후**다. 선택·통과 판정에 미사용했다.

## 다중검정 표

| stage | policy | series | internal_m | cumulative_m | dsr_internal | dsr_cumulative | pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| short_stage | S1 | standalone | 12 | 5050 | 0.0854 | 0.0000 | False |
| short_stage | S1 | overlay_paired_delta | 12 | 5050 |  |  | False |
| short_stage | S2 | standalone | 12 | 5050 | 0.0009 | 0.0000 | False |
| short_stage | S2 | overlay_paired_delta | 12 | 5050 | 0.0403 | 0.0023 | False |
| short_stage | S3 | standalone | 12 | 5050 | 0.0130 | 0.0000 | False |
| short_stage | S3 | overlay_paired_delta | 12 | 5050 | 0.1393 | 0.0146 | False |
| short_stage | S4 | standalone | 12 | 5050 | 0.0022 | 0.0000 | False |
| short_stage | S4 | overlay_paired_delta | 12 | 5050 | 0.0000 | 0.0000 | False |
| short_stage | S5 | standalone | 12 | 5050 | 0.0001 | 0.0000 | False |
| short_stage | S5 | overlay_paired_delta | 12 | 5050 | 0.0053 | 0.0001 | False |
| short_stage | S6 | standalone | 12 | 5050 | 0.0000 | 0.0000 | False |
| short_stage | S6 | overlay_paired_delta | 12 | 5050 | 0.0001 | 0.0000 | False |
| router_stage | ridge | paired_delta | 2 | 5050 | 0.0271 | 0.0038 | False |
| router_stage | small_boosting | paired_delta | 2 | 5050 | 0.0564 | 0.0100 | False |

## 실행 전 해석

- 반대 신호 청산도 정시 T에 판단하고 T+1분 open에 체결한다. max-hold는 진입시각부터 정확한 시간 뒤 open이다.
- 구간 일별 PnL은 기존 k45_ledger처럼 고정 [start,end) MTM slice를 사용한다. 거래 수·집중도는 decision_time이 구간 안인 거래다.
- archive metrics create_time+5분<T는 정시 T에서 마지막 create_time<=T-10분 행을 뜻한다(5분 격자).
- 과거 분위수는 명세가 prior라고 한 S3~S6·router percentile에서 현재 행을 제외한다. 동결 F3/F3-w30 신호 자체는 기존 정의대로 현재 snapshot을 rolling 표본에 포함한다.
- 24h realized volatility는 최근 24개 1h log return의 ddof=0 표준편차다.
- 60m ratio change는 log(current/prior-hour), prior percentile은 과거값 중 current 이하 비율이다.
- 동일 action·side run은 1시간 연속이며 중간 unavailable 또는 side 변화에서 끊는다. run 안 row weight 합은 1이다.
- F3 계열 signal strength는 진입 tail 경계 초과거리를 prior-window IQR로 나눈 값이다. E1은 명세 식이며 ATR은 14시간 Wilder ATR이다.
- DSR trial Sharpe 분산은 해당 단계 DEV 정책들의 비연율 Sharpe 표본분산이다. 0 또는 비유한 분산은 0으로 둔다.
- HOLD_A 끝에서 미청산 포지션은 숫자 표시를 위해 2026-10-01 직전 마지막 close로 data_cutoff 청산한다. 선택·통과에는 쓰지 않는다.
- funding PESS 경계 현금흐름은 기존 out/k45_funding.py 정의를 그대로 쓴다.
- 필수 source stale은 metric create_time이 T보다 15분 초과 과거이거나 완결 market/premium source가 없을 때다. 정상 결측은 training median+indicator로 처리한다.
- 1단계 winner의 HOLD_B 절대 net·paired net·상위 2거래 제거 조건은 C1_X와 직접 비교되는 overlay 장부에 적용한다.

이 절과 `candidate_definitions.parquet`, `feature_definitions.parquet`, `model_definitions.parquet`, 최초 manifest는 결과 계산 전에 기록했다.

## router 비교 기준

### 고정 baseline

| book | trade_n | total_net_bps | daily_sharpe |
| --- | --- | --- | --- |
| C1_X | 534 | 17090.9037 | 1.7129 |
| F3 | 424 | 11999.4157 | 1.3442 |
| F3-w30 | 1220 | 7563.4497 | 0.7178 |
| E1 | 221 | 7002.9182 | 1.1328 |

### 초기 fit best single

| action | net_bps |
| --- | --- |
| F3 | 18435.1362 |
| F3-w30 | 18661.6227 |
| E1 | -172.0492 |

- 선택: `F3-w30`. 2021-03-01~2022-12-31만 사용했다.

### 균등 random 10,000회

| repetitions | p05_net_bps | median_net_bps | p95_net_bps |
| --- | --- | --- | --- |
| 10000 | 13152.7448 | 14714.0454 | 16344.5320 |

- perfect hindsight oracle DEV net: `92743.9664` bp. 상한 참고값이며 gate가 아니다.

## 계약 준수

- 시장: Binance USD-M BTCUSDT futures 로컬 자료만.
- 정시 T 판단, T+1분 open 체결, metrics `create_time+5분<T`.
- 1단계 12 series. 2단계 ridge/depth-2 boosting 2개만.
- expanding monthly, `label_end < retrain_time-24h`.
- 비용 4 bp + funding PESS 주결과. 8 bp gate, 12 bp 보고.
- bookTicker, spot, DEX, m_* 미사용. 네트워크·주문·인증 0.

## 산출물

명세의 parquet·JSON·REPORT 전부 생성했다. 입력·소스·출력 SHA256과 cutoff는 `manifest.json`에 있다. 진행 기록은 `run.log`다.

## Codex 의견

판정은 위 숫자와 사전 AND gate만 따른다. HOLD_B 실패나 HOLD_A 양수로 DEV 실패를 되살리지 않았다. 이 결과는 새 모의 승격 근거가 아니라 동결 가설의 제한된 OOS 확인값이다.

## 사용자 결정 사항

- 승인: 2026-10-06, “1단계 2단계 진행”.
- 다음 결정: `SHORT_STAGE_FAIL`와 `ROUTER_DEV_FAIL`를 유지할지, 새 가설은 새 R 번호로 등록할지 선택.
