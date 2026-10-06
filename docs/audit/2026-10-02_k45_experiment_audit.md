# K45 실험 전수 점검 (기계적 추출)

- 생성 UTC: 2026-10-05T16:18:02.130918+00:00
- git HEAD: 0f358d7023795f25ab5f251a57a46be44975a6b9
- 생성 스크립트: scripts/audit_k45_experiments.py
- 방식: 각 out/k45_* 폴더의 manifest.json 필드를 그대로 옮기고, manifest에 기록된 출력 파일 SHA256을 지금 디스크 파일과 비교하고, 대응 테스트를 다시 실행하고, REPORT.md 앞부분을 그대로 붙인다. 해석 문장은 쓰지 않는다.
- 마지막 절: 대화에서 내가 인용한 숫자와 디스크 값을 나란히 둔다.

## 폴더 목록

| 폴더 | manifest | REPORT.md 줄 수 | 대응 테스트 | 테스트 커밋 |
|---|---|---|---|---|
| k45_candidate_compare_r2_23_20261004 | 있음 | 1890 | tests/test_k45_candidate_compare_r2_23.py | b272801 test: candidate comparison on one ledger with frozen DEV-only selections (R2-23) |
| k45_classic_rules_r2_14_20261002 | 있음 | 107 | tests/test_k45_classic_rules_r2_14.py | 34ec960 fix(test): settle funding at archive rate of the settlement time, with PESS/OPT boundary bounds (R2-22) |
| k45_combo_robust_r2_25_20261004 | 있음 | 669 | tests/test_k45_combo_robust_r2_25.py | 0f358d7 test: combo robustness grid and HOLD-A data parity checks (R2-25, R2-26) |
| k45_contrarian_robust_r2_17_20261002 | 있음 | 4112 | tests/test_k45_contrarian_robust_r2_17.py | 34ec960 fix(test): settle funding at archive rate of the settlement time, with PESS/OPT boundary bounds (R2-22) |
| k45_defect_audit_20260930 | 있음 | 100 |  |  |
| k45_funding_fix_20261004 | 있음 | 216 | tests/test_k45_funding.py | 34ec960 fix(test): settle funding at archive rate of the settlement time, with PESS/OPT boundary bounds (R2-22) |
| k45_funding_plan_review_20261004 | 있음 | 174 |  |  |
| k45_funding_rerun_r2_20_21_20261004 | 있음 | 500 | tests/test_k45_mtf_tail_r2_20.py | bb544fd test: R2-20 and R2-21 funding through the shared archive module with PESS/OPT boundaries |
| k45_funding_review_20261004 | 있음 | 179 |  |  |
| k45_gate_direction_20261001 | 있음 | 976 | tests/test_k45_gate_direction.py | 426f993 test: probability quality deciles and side choice (gate-direction Tasks 4-5) |
| k45_gate_direction_audit_20261001 | 있음 | 없음 | tests/test_k45_gate_direction.py | 426f993 test: probability quality deciles and side choice (gate-direction Tasks 4-5) |
| k45_gate_direction_r2_10_20261001 | 있음 | 6423 | tests/test_k45_gate_direction_r2_10.py | 5714ce0 test: allow the 180-minute horizon in the matched grid (gate-direction R2-10b) |
| k45_gate_direction_r2_10b_20261001 | 있음 | 7636 | tests/test_k45_gate_direction_r2_10.py | 5714ce0 test: allow the 180-minute horizon in the matched grid (gate-direction R2-10b) |
| k45_gate_direction_r2_11_20261001 | 있음 | 98064 | tests/test_k45_gate_direction_r2_11.py | cd6c17f test: per-fold STOP-segment CatBoost tuning never touches TEST (gate-direction R2-11) |
| k45_gate_direction_r2_20261001 | 있음 | 416 | tests/test_k45_gate_direction_r2.py | b1ff8a2 test: side models, book capacity, fade orthogonalisation, tail curves, CI fallbacks (gate-direction round 2) |
| k45_gate_direction_r2_6_20261001 | 있음 | 1099 | tests/test_k45_gate_direction_r2_6.py | 78ed758 test: hold-time sweep with funding and pure-effect baseline (gate-direction R2-6) |
| k45_gate_direction_r2_7_20261001 | 있음 | 7194 | tests/test_k45_gate_direction_r2_7.py | 1059c6a test: causal expanding tail cutoffs never read current or future folds (gate-direction R2-7) |
| k45_gate_direction_r2_8_20261001 | 있음 | 2752 | tests/test_k45_gate_direction_r2_8.py | fd07563 test: single-position higher-probability side with per-side holds (gate-direction R2-8) |
| k45_gate_direction_r2_9_20261001 | 있음 | 149 | tests/test_k45_gate_direction_r2_9.py | 47c381a test: causal tail cutoffs including horizon-matched models, single-position grid (gate-direction R2-9) |
| k45_gate_direction_r2_9b_20261002 | 있음 | 661 | tests/test_k45_gate_direction_r2_9b.py | 3bf9450 test: seed and parameter perturbation keeps fixed artifacts and frozen robust rule (R2-9b) |
| k45_hold_a_data_r2_26_20261004 | 있음 | 257 | tests/test_k45_hold_a_data_r2_26.py | 0f358d7 test: combo robustness grid and HOLD-A data parity checks (R2-25, R2-26) |
| k45_hold_a_eval_build_r2_27_20261005 | 있음 | 71 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_hold_a_exclude_bookticker_r2_32_20261005 | 있음 | 2489 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_hold_a_final_review_r2_31_20261005 | 없음 | 없음 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_hold_a_freeze_review_20261005 | 없음 | 213 |  |  |
| k45_hold_a_interpret_r2_33_20261006 | 있음 | 200 |  |  |
| k45_hold_a_report_complete_r2_30_20261005 | 있음 | 60 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_hold_a_runner_complete_r2_29_20261005 | 있음 | 47 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_hold_a_unblock_r2_28_20261005 | 있음 | 38 | tests/test_k45_hold_a_eval_r2_27.py | not committed |
| k45_holdout_a_2026q3 | 없음 | 없음 | tests/test_k45_holdout_a_2026q3.py | not committed |
| k45_meta_label_r2_15_20261002 | 있음 | 554 | tests/test_k45_meta_label_r2_15.py | f221e9b test: meta-label walk-forward and contrarian neighbourhood robustness (R2-15, R2-17) |
| k45_mtf_entry_r2_12_20261001 | 있음 | 8364 | tests/test_k45_mtf_entry_r2_12.py | 6f7b0f2 test: multi-timeframe signal with lower-timeframe limit entry uses closed bars only (R2-12) |
| k45_mtf_persistence_r2_13_20261002 | 있음 | 1774 | tests/test_k45_mtf_persistence_r2_13.py | 67b7b30 test: persistence labels stop before STOP and trailing exits use closed bars only (R2-13) |
| k45_mtf_tail_r2_20_20261003 | 있음 | 2438 | tests/test_k45_mtf_tail_r2_20.py | bb544fd test: R2-20 and R2-21 funding through the shared archive module with PESS/OPT boundaries |
| k45_patchtst_updown_r2_21_20261003 | 있음 | 3267 | tests/test_k45_patchtst_updown_r2_21.py | bb544fd test: R2-20 and R2-21 funding through the shared archive module with PESS/OPT boundaries |
| k45_risk_stop_r2_18_20261002 | 있음 | 2554 | tests/test_k45_risk_stop_r2_18.py | 34ec960 fix(test): settle funding at archive rate of the settlement time, with PESS/OPT boundary bounds (R2-22) |
| k45_single_book_combo_r2_24_20261004 | 있음 | 2255 | tests/test_k45_single_book_combo_r2_24.py | bc077b6 test: single-position combination of candidates with FIRST/PRIORITY/SWITCH conflict rules (R2-24) |
| k45_train_window_r2_16_20261002 | 있음 | 41 | tests/test_k45_train_window_r2_16.py | 61327ce test: train-window comparison, MTM ledger validation and PatchTST up/down split (R2-16, R2-19, R2-21) |
| k45_trend_side_20261001 | 있음 | 37 | tests/test_k45_trend_side.py | eba6185 test: limit TP exit and stage 2 grid runner (Tasks 5-6) |
| k45_trend_side_tp_20261001 | 있음 | 38 | tests/test_k45_trend_side.py | eba6185 test: limit TP exit and stage 2 grid runner (Tasks 5-6) |
| k45_validation_r2_19_20261003 | 있음 | 708 | tests/test_k45_validation_r2_19.py | 34ec960 fix(test): settle funding at archive rate of the settlement time, with PESS/OPT boundary bounds (R2-22) |

## k45_candidate_compare_r2_23_20261004

- 테스트 재실행 `tests/test_k45_candidate_compare_r2_23.py`: `5 passed in 2.07s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-23 |
| status | COMPLETE |
| started_utc | 2026-10-04T10:44:15.483985+00:00 |
| finished_utc | 2026-10-04T10:45:55.087465+00:00 |
| elapsed_seconds | 99.60182749992236 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| frozen_manifest_sha256 | 0916b0b31db63d55ce9c5c5e3920246a77e708afbb4e9b26ba4f1ff6f0f3d5ec |
| frozen_candidates | ["F3/1h/10/24/signal/LS", "F3/1h/5/24/signal/LS", "F3_global_ls_account/1h/w30/q20/h12/LS", "E1/1h/3/signal/L", "E1/1h/2/signal/L", "E1/1h/3/signal/L+R2-15/catboost/base", "A3/4h/720/signal/LS", "F1/1h/5/24/signal/LS", "SIDE/ROLLING_180D/q=0.01/L=120/S=60/V0", "4h_h480/SIDE/ROLLING_180D/q02/g1", "COMBO_SINGLE/STOP", "BUY_HOLD"] |
| selections | {"candidate_3": "F3_global_ls_account/1h/w30/q20/h12/LS", "candidate_10": "4h_h480/SIDE/ROLLING_180D/q02/g1", "selection_input_segment": "DEV_ONLY", "hold_b_used": false} |
| segments | {"DEV_COMMON": ["2021-03-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"], "HOLD_B": ["2026-01-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00"]} |
| funding_boundaries | ["PESS", "OPT"] |
| cost_bps | [0.0, 4.0, 8.0, 12.0] |
| trial_counts | [813, 4971] |
| random_repetitions | 1000 |
| workers_max | 12 |
| live_orders | 0 |
| downloads | 0 |
| retraining | 0 |
| hold_a_read | 0 |
| post_cutoff_read | 0 |
| meta_boundary_specific_trade_sets | True |
| reproduction_match_rows | 20 |
| reproduction_total_rows | 48 |

- 출력 해시 확인: 12/12 일치

### REPORT.md 앞 150줄 (전체 1890줄, 원문)

# R2-23

## reproduction

| candidate | boundary | segment | source_type | source_n | engine_n | source_net_bps | engine_net_bps | n_difference | net_difference_bps | match | cause_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | PESS | DEV | R2-22_R2-14 | 873 | 874 | 34886.268943 | 34883.279885 | 1 | -2.989058 | 0 | N_MISMATCH |
| F3\|1h\|10/24\|signal\|LS | PESS | HOLD_B | R2-22_R2-14 | 76 | 76 | 1176.121494 | 1176.121494 | 0 | -0.000000 | 1 | MATCH |
| F3\|1h\|10/24\|signal\|LS | OPT | DEV | R2-22_R2-14 | 873 | 874 | 35725.985043 | 35723.995985 | 1 | -1.989058 | 0 | N_MISMATCH |
| F3\|1h\|10/24\|signal\|LS | OPT | HOLD_B | R2-22_R2-14 | 76 | 76 | 1187.491794 | 1187.491794 | 0 | -0.000000 | 1 | MATCH |
| F3\|1h\|5/24\|signal\|LS | PESS | DEV | R2-22_R2-14 | 612 | 613 | 28088.202849 | 28085.213791 | 1 | -2.989058 | 0 | N_MISMATCH |
| F3\|1h\|5/24\|signal\|LS | PESS | HOLD_B | R2-22_R2-14 | 43 | 43 | 1035.804593 | 1035.804593 | 0 | 0.000000 | 1 | MATCH |
| F3\|1h\|5/24\|signal\|LS | OPT | DEV | R2-22_R2-14 | 612 | 613 | 28470.606449 | 28468.617391 | 1 | -1.989058 | 0 | N_MISMATCH |
| F3\|1h\|5/24\|signal\|LS | OPT | HOLD_B | R2-22_R2-14 | 43 | 43 | 1039.763093 | 1039.763093 | 0 | 0.000000 | 1 | MATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | PESS | DEV | R2-22_R2-17 | 2250 | 2251 | 45269.712450 | 45275.311127 | 1 | 5.598677 | 0 | N_MISMATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | PESS | HOLD_B | R2-22_R2-17 | 216 | 217 | 3978.160386 | 3969.572652 | 1 | -8.587734 | 0 | N_MISMATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | OPT | DEV | R2-22_R2-17 | 2250 | 2251 | 46255.114650 | 46261.713327 | 1 | 6.598677 | 0 | N_MISMATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | OPT | HOLD_B | R2-22_R2-17 | 216 | 217 | 3999.233386 | 3990.645652 | 1 | -8.587734 | 0 | N_MISMATCH |
| E1\|1h\|3\|signal\|L | PESS | DEV | R2-22_R2-14 | 375 | 375 | 14420.583556 | 14420.583556 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | PESS | HOLD_B | R2-22_R2-14 | 30 | 30 | 1445.512546 | 1445.512546 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | OPT | DEV | R2-22_R2-14 | 375 | 375 | 14509.211356 | 14509.211356 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | OPT | HOLD_B | R2-22_R2-14 | 30 | 30 | 1447.276546 | 1447.276546 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | PESS | DEV | R2-22_R2-14 | 583 | 583 | 15240.159242 | 15240.159242 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | PESS | HOLD_B | R2-22_R2-14 | 49 | 49 | 1915.549648 | 1915.549648 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | OPT | DEV | R2-22_R2-14 | 583 | 583 | 15374.830242 | 15374.830242 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | OPT | HOLD_B | R2-22_R2-14 | 49 | 49 | 1918.134848 | 1918.134848 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | PESS | DEV | R2-22_R2-15 | 204 | 204 | 12579.569201 | 12579.569201 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | PESS | HOLD_B | R2-22_R2-15 | 10 | 10 | 39.868088 | 39.868088 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | OPT | DEV | R2-22_R2-15 | 202 | 202 | 14661.715973 | 14661.715973 | 0 | -0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | OPT | HOLD_B | R2-22_R2-15 | 10 | 10 | 385.191454 | 385.191454 | 0 | 0.000000 | 1 | MATCH |
| A3\|4h\|720\|signal\|LS | PESS | DEV | R2-22_R2-14 | 339 | 340 | 31066.703900 | 30964.655727 | 1 | -102.048173 | 0 | N_MISMATCH |
| A3\|4h\|720\|signal\|LS | PESS | HOLD_B | R2-22_R2-14 | 45 | 46 | 3045.268844 | 3084.219768 | 1 | 38.950924 | 0 | N_MISMATCH |
| A3\|4h\|720\|signal\|LS | OPT | DEV | R2-22_R2-14 | 339 | 340 | 31466.599600 | 31364.380327 | 1 | -102.219273 | 0 | N_MISMATCH |
| A3\|4h\|720\|signal\|LS | OPT | HOLD_B | R2-22_R2-14 | 45 | 46 | 3061.741744 | 3100.863768 | 1 | 39.122024 | 0 | N_MISMATCH |
| F1\|1h\|5/24\|signal\|LS | PESS | DEV | R2-22_R2-14 | 818 | 818 | 15528.031794 | 15528.031794 | 0 | -0.000000 | 1 | MATCH |
| F1\|1h\|5/24\|signal\|LS | PESS | HOLD_B | R2-22_R2-14 | 48 | 48 | 910.275634 | 910.275634 | 0 | 0.000000 | 1 | MATCH |
| F1\|1h\|5/24\|signal\|LS | OPT | DEV | R2-22_R2-14 | 818 | 818 | 15528.031794 | 15528.031794 | 0 | -0.000000 | 1 | MATCH |
| F1\|1h\|5/24\|signal\|LS | OPT | HOLD_B | R2-22_R2-14 | 48 | 48 | 910.275634 | 910.275634 | 0 | 0.000000 | 1 | MATCH |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | PESS | DEV | R2-9_ORIGIN_REPRICED | 292 | 292 | 4909.905710 | 4913.723836 | 0 | 3.818126 | 0 | GROSS_RETURN_DEFINITION |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | PESS | HOLD_B | R2-9_ORIGIN_REPRICED | 32 | 32 | 1410.061806 | 1414.909623 | 0 | 4.847816 | 0 | GROSS_RETURN_DEFINITION |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | OPT | DEV | R2-9_ORIGIN_REPRICED | 292 | 292 | 4928.668810 | 4932.486936 | 0 | 3.818126 | 0 | GROSS_RETURN_DEFINITION |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | OPT | HOLD_B | R2-9_ORIGIN_REPRICED | 32 | 32 | 1412.081106 | 1416.928923 | 0 | 4.847816 | 0 | GROSS_RETURN_DEFINITION |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | PESS | DEV | R2-22_R2-20 | 80 | 80 | 5161.730680 | 5075.087862 | 0 | -86.642818 | 0 | GROSS_RETURN_DEFINITION |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | PESS | HOLD_B | R2-22_R2-20 | 12 | 12 | -387.181212 | -418.659043 | 0 | -31.477832 | 0 | GROSS_RETURN_DEFINITION |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | OPT | DEV | R2-22_R2-20 | 80 | 80 | 5271.958980 | 5185.316162 | 0 | -86.642818 | 0 | GROSS_RETURN_DEFINITION |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | OPT | HOLD_B | R2-22_R2-20 | 12 | 12 | -384.563212 | -416.041043 | 0 | -31.477832 | 0 | GROSS_RETURN_DEFINITION |
| COMBO_SINGLE\|STOP | PESS | DEV | R2-22_R2-18 | 2307 | 2307 | 10447.845244 | 10409.688282 | 0 | -38.156962 | 0 | GROSS_RETURN_DEFINITION |
| COMBO_SINGLE\|STOP | PESS | HOLD_B | R2-22_R2-18 | 120 | 120 | 554.333006 | 530.096942 | 0 | -24.236064 | 0 | GROSS_RETURN_DEFINITION |
| COMBO_SINGLE\|STOP | OPT | DEV | R2-22_R2-18 | 2307 | 2307 | 11572.272044 | 11534.115082 | 0 | -38.156962 | 0 | GROSS_RETURN_DEFINITION |
| COMBO_SINGLE\|STOP | OPT | HOLD_B | R2-22_R2-18 | 120 | 120 | 561.206306 | 536.970242 | 0 | -24.236064 | 0 | GROSS_RETURN_DEFINITION |
| BUY_HOLD | PESS | DEV | R2-22_R2-14 | 1 | 1 | 15661.382812 | 15664.382812 | 0 | 3.000000 | 0 | BOUNDARY_SPLIT_OR_LEDGER |
| BUY_HOLD | PESS | HOLD_B | R2-22_R2-14 | 1 | 1 | -4080.381298 | -4078.369884 | 0 | 2.011414 | 0 | BOUNDARY_SPLIT_OR_LEDGER |
| BUY_HOLD | OPT | DEV | R2-22_R2-14 | 1 | 1 | 15663.382812 | 15665.382812 | 0 | 2.000000 | 0 | BOUNDARY_SPLIT_OR_LEDGER |
| BUY_HOLD | OPT | HOLD_B | R2-22_R2-14 | 1 | 1 | -4079.381298 | -4078.369884 | 0 | 1.011414 | 0 | BOUNDARY_SPLIT_OR_LEDGER |

## trade_set_parity

| candidate | pess_n | opt_n | common_n | symmetric_difference_n | same_trade_set | r2_15_boundary_specific_exception |
| --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | 1101 | 1101 | 1101 | 0 | 1 | 0 |
| F3\|1h\|5/24\|signal\|LS | 807 | 807 | 807 | 0 | 1 | 0 |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 2770 | 2770 | 2770 | 0 | 1 | 0 |
| E1\|1h\|3\|signal\|L | 441 | 441 | 441 | 0 | 1 | 0 |
| E1\|1h\|2\|signal\|L | 682 | 682 | 682 | 0 | 1 | 0 |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | 214 | 212 | 194 | 38 | 0 | 1 |
| A3\|4h\|720\|signal\|LS | 400 | 400 | 400 | 0 | 1 | 0 |
| F1\|1h\|5/24\|signal\|LS | 892 | 892 | 892 | 0 | 1 | 0 |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 324 | 324 | 324 | 0 | 1 | 0 |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 92 | 92 | 92 | 0 | 1 | 0 |
| COMBO_SINGLE\|STOP | 2427 | 2427 | 2427 | 0 | 1 | 0 |
| BUY_HOLD | 1 | 1 | 1 | 0 | 1 | 0 |

## DEV_COMMON_PESS

| candidate | n | exposure_ratio | net_total_bps | net_per_trade_bps | mtm_daily_sharpe | mtm_max_drawdown_bps | pw_ci95_lower_daily_bps | pw_ci95_upper_daily_bps | pw_p_greater_zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | 717 | 0.405655 | 30361.807133 | 42.345617 | 1.547682 | 3715.524393 | 7.557677 | 27.048894 | 0.001499 |
| F3\|1h\|5/24\|signal\|LS | 489 | 0.276646 | 22789.316838 | 46.603920 | 1.372530 | 3561.673242 | 4.574415 | 21.375364 | 0.001499 |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 1900 | 0.534687 | 31928.282665 | 16.804359 | 1.518511 | 4612.152574 | 7.587250 | 28.765859 | 0.001000 |
| E1\|1h\|3\|signal\|L | 322 | 0.151858 | 8614.395584 | 26.752781 | 0.833185 | 3968.542221 | -0.087021 | 10.189811 | 0.028486 |
| E1\|1h\|2\|signal\|L | 509 | 0.240049 | 9290.913223 | 18.253268 | 0.725365 | 5523.751138 | -1.242126 | 11.781498 | 0.052974 |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | 151 | 0.071213 | 6773.381230 | 44.856829 | 0.902489 | 2310.869893 | -0.007867 | 7.624693 | 0.026487 |
| A3\|4h\|720\|signal\|LS | 321 | 1.000000 | 20642.717839 | 64.307532 | 0.754822 | 7796.206063 | -1.418941 | 25.452059 | 0.038981 |
| F1\|1h\|5/24\|signal\|LS | 761 | 0.424283 | 13400.815813 | 17.609482 | 0.697479 | 6690.540641 | -1.633381 | 16.486442 | 0.051474 |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 292 | 0.009692 | 4913.723836 | 16.827821 | 1.029018 | 1656.977506 | 0.402322 | 5.120835 | 0.011494 |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 80 | 0.015091 | 5075.087862 | 63.438598 | 1.200347 | 1217.915851 | 0.676925 | 4.935370 | 0.005497 |
| COMBO_SINGLE\|STOP | 1896 | 0.160090 | 8416.961768 | 4.439326 | 0.717836 | 2851.900709 | -0.990432 | 10.220896 | 0.046977 |
| BUY_HOLD | 1 | 1.000000 | 1969.029422 | 1969.029422 | 0.071823 | 15849.542995 | -12.379959 | 15.650719 | 0.430785 |

## DEV_COMMON_OPT

| candidate | n | exposure_ratio | net_total_bps | net_per_trade_bps | mtm_daily_sharpe | mtm_max_drawdown_bps | pw_ci95_lower_daily_bps | pw_ci95_upper_daily_bps | pw_p_greater_zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | 717 | 0.405655 | 30663.775233 | 42.766772 | 1.562873 | 3712.388993 | 7.834050 | 27.068155 | 0.001499 |
| F3\|1h\|5/24\|signal\|LS | 489 | 0.276646 | 22874.502938 | 46.778125 | 1.377509 | 3548.409842 | 4.623793 | 21.427875 | 0.001499 |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 1900 | 0.534687 | 32453.286365 | 17.080677 | 1.542493 | 4558.378974 | 7.849371 | 29.060327 | 0.001000 |
| E1\|1h\|3\|signal\|L | 322 | 0.151858 | 8683.247284 | 26.966606 | 0.839507 | 3957.166621 | -0.065805 | 10.241158 | 0.028986 |
| E1\|1h\|2\|signal\|L | 509 | 0.240049 | 9397.395023 | 18.462466 | 0.733474 | 5512.113038 | -1.182609 | 11.846962 | 0.051974 |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | 149 | 0.070270 | 8835.751902 | 59.300348 | 1.167468 | 2195.554762 | 1.301076 | 8.688356 | 0.004498 |
| A3\|4h\|720\|signal\|LS | 321 | 1.000000 | 20925.429839 | 65.188255 | 0.765227 | 7752.552863 | -1.388403 | 25.364774 | 0.037981 |
| F1\|1h\|5/24\|signal\|LS | 761 | 0.424283 | 13400.815813 | 17.609482 | 0.697479 | 6690.540641 | -1.633381 | 16.486442 | 0.051474 |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 292 | 0.009692 | 4932.486936 | 16.892079 | 1.033098 | 1656.803206 | 0.414262 | 5.132781 | 0.011494 |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 80 | 0.015091 | 5185.316162 | 64.816452 | 1.228156 | 1217.618708 | 0.728016 | 4.999889 | 0.005497 |
| COMBO_SINGLE\|STOP | 1896 | 0.160090 | 8978.428168 | 4.735458 | 0.764273 | 2822.026209 | -0.571628 | 10.693714 | 0.039980 |
| BUY_HOLD | 1 | 1.000000 | 1969.029422 | 1969.029422 | 0.071823 | 15849.542995 | -12.379959 | 15.650719 | 0.430785 |

## rankings

| metric | boundary | candidate | value | rank | opt_rank_changed |
| --- | --- | --- | --- | --- | --- |
| pw_ci95_lower_daily_bps | PESS | F3\|1h\|10/24\|signal\|LS | 7.557677 | 2 | 0 |
| pw_ci95_lower_daily_bps | PESS | F3\|1h\|5/24\|signal\|LS | 4.574415 | 3 | 0 |
| pw_ci95_lower_daily_bps | PESS | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 7.587250 | 1 | 0 |
| pw_ci95_lower_daily_bps | PESS | E1\|1h\|3\|signal\|L | -0.087021 | 7 | 0 |
| pw_ci95_lower_daily_bps | PESS | E1\|1h\|2\|signal\|L | -1.242126 | 9 | 0 |
| pw_ci95_lower_daily_bps | PESS | E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | -0.007867 | 6 | 1 |
| pw_ci95_lower_daily_bps | PESS | A3\|4h\|720\|signal\|LS | -1.418941 | 10 | 0 |
| pw_ci95_lower_daily_bps | PESS | F1\|1h\|5/24\|signal\|LS | -1.633381 | 11 | 0 |
| pw_ci95_lower_daily_bps | PESS | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 0.402322 | 5 | 1 |
| pw_ci95_lower_daily_bps | PESS | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 0.676925 | 4 | 1 |
| pw_ci95_lower_daily_bps | PESS | COMBO_SINGLE\|STOP | -0.990432 | 8 | 0 |
| pw_ci95_lower_daily_bps | PESS | BUY_HOLD | -12.379959 | 12 | 0 |
| pw_ci95_lower_daily_bps | OPT | F3\|1h\|10/24\|signal\|LS | 7.834050 | 2 | 0 |
| pw_ci95_lower_daily_bps | OPT | F3\|1h\|5/24\|signal\|LS | 4.623793 | 3 | 0 |
| pw_ci95_lower_daily_bps | OPT | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 7.849371 | 1 | 0 |
| pw_ci95_lower_daily_bps | OPT | E1\|1h\|3\|signal\|L | -0.065805 | 7 | 0 |
| pw_ci95_lower_daily_bps | OPT | E1\|1h\|2\|signal\|L | -1.182609 | 9 | 0 |
| pw_ci95_lower_daily_bps | OPT | E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | 1.301076 | 4 | 1 |
| pw_ci95_lower_daily_bps | OPT | A3\|4h\|720\|signal\|LS | -1.388403 | 10 | 0 |
| pw_ci95_lower_daily_bps | OPT | F1\|1h\|5/24\|signal\|LS | -1.633381 | 11 | 0 |
| pw_ci95_lower_daily_bps | OPT | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 0.414262 | 6 | 1 |
| pw_ci95_lower_daily_bps | OPT | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 0.728016 | 5 | 1 |
| pw_ci95_lower_daily_bps | OPT | COMBO_SINGLE\|STOP | -0.571628 | 8 | 0 |
| pw_ci95_lower_daily_bps | OPT | BUY_HOLD | -12.379959 | 12 | 0 |
| mtm_daily_sharpe | PESS | F3\|1h\|10/24\|signal\|LS | 1.547682 | 1 | 0 |
| mtm_daily_sharpe | PESS | F3\|1h\|5/24\|signal\|LS | 1.372530 | 3 | 0 |
| mtm_daily_sharpe | PESS | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 1.518511 | 2 | 0 |
| mtm_daily_sharpe | PESS | E1\|1h\|3\|signal\|L | 0.833185 | 7 | 0 |
| mtm_daily_sharpe | PESS | E1\|1h\|2\|signal\|L | 0.725365 | 9 | 1 |
| mtm_daily_sharpe | PESS | E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | 0.902489 | 6 | 1 |
| mtm_daily_sharpe | PESS | A3\|4h\|720\|signal\|LS | 0.754822 | 8 | 0 |
| mtm_daily_sharpe | PESS | F1\|1h\|5/24\|signal\|LS | 0.697479 | 11 | 0 |
| mtm_daily_sharpe | PESS | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 1.029018 | 5 | 1 |
| mtm_daily_sharpe | PESS | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 1.200347 | 4 | 0 |
| mtm_daily_sharpe | PESS | COMBO_SINGLE\|STOP | 0.717836 | 10 | 1 |
| mtm_daily_sharpe | PESS | BUY_HOLD | 0.071823 | 12 | 0 |
| mtm_daily_sharpe | OPT | F3\|1h\|10/24\|signal\|LS | 1.562873 | 1 | 0 |
| mtm_daily_sharpe | OPT | F3\|1h\|5/24\|signal\|LS | 1.377509 | 3 | 0 |
| mtm_daily_sharpe | OPT | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 1.542493 | 2 | 0 |
| mtm_daily_sharpe | OPT | E1\|1h\|3\|signal\|L | 0.839507 | 7 | 0 |

## k45_classic_rules_r2_14_20261002

- 테스트 재실행 `tests/test_k45_classic_rules_r2_14.py`: `9 passed, 4 warnings in 1.33s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-14 |
| created_utc | 2026-10-02T07:30:14.427810+00:00 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| hypothesis_frozen | 현재 로컬 데이터의 규칙 기반 기법 중 적어도 하나의 계열 대표 칸(DEV Sharpe 최대)이 DEV에서 SPA p < 0.05로 0과 바이앤홀드를 넘고, HOLD_B에서도 net > 0 이다. |
| cell_count | 813 |
| workers | 1 |
| numeric_threads | 4 |
| model_training | False |
| selection_rule | 각 계열 DEV daily_sharpe 최대 1칸; HOLD_B 미사용 |
| oos_result | {"hypothesis_pass": false, "passing_families": []} |
| funding_events | {"definition": "UTC 00:00/08:00/16:00; prior-minute funding_rate", "count": 7118, "expected": 7119, "scheduled": 7119, "missing_previous_minute": 1, "nonstandard": 0} |
| unavailable_data | ["order_book", "liquidations"] |
| assumptions | {"daily_return": "exit-day realized net bps; boundary-crossing trade clipped to entry segment final day", "pw_block": "circular moving-block bootstrap; block=round(n_days^(1/3)); 1000 repetitions", "fixed_block": "circular moving-block bootstrap; block=20 days; 1000 repetitions", "random": "1000 circular schedule shifts; same trade count, sides, durations, nominal exposure", "unspecified_event_exit": "C2/C3/C5/D1/D2/E1=20 bars; C4=12 bars; E2=flow window", "F2_oi": "sign of available oi_change_rate_60m at each 4h decision", "E3_profile": "50 price bins; rolling 24 one-hour bars; 70% adjacent-b |

- 출력 해시 확인: 10/10 일치

### REPORT.md 앞 107줄 (전체 107줄, 원문)

# R2-14

## 칸 수

813

## 계열 대표 칸

| family | cell_id | dev_n | dev_net_bps | dev_sharpe | dev_spa_p_zero | dev_spa_p_buy_hold | hold_n | hold_net_bps | hold_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | A1\|4h\|50/200\|trail2\|L | 27 | 10304.142669 | 0.944275 | 0.026973 | 0.653347 | 3 | -519.856183 | -2.122772 |
| A2 | A2\|4h\|55/10\|signal\|L | 96 | 18038.414122 | 0.906944 | 0.027972 | 0.419580 | 9 | -851.987712 | -1.965496 |
| A3 | A3\|4h\|720\|signal\|LS | 339 | 31309.380610 | 0.800353 | 0.032967 | 0.212787 | 45 | 3055.937445 | 1.065194 |
| A4 | A4\|4h\|10/3\|signal\|L | 130 | 17515.271415 | 0.602044 | 0.092907 | 0.436563 | 14 | -2251.052293 | -2.612842 |
| A5 | A5\|4h\|25\|trail2\|L | 180 | 18183.324390 | 0.783048 | 0.054945 | 0.408591 | 17 | -947.173409 | -1.435336 |
| A6 | A6\|1h\|40/60\|signal\|L | 228 | 5795.269532 | 0.363393 | 0.192807 | 0.743257 | 20 | 624.468656 | 1.260208 |
| B1 | B1\|15m\|2.5/12\|signal\|L | 2466 | -3325.616534 | -0.275373 | 0.773227 | 0.923077 | 236 | -358.132676 | -0.361616 |
| B2 | B2\|1h\|20/80/4\|signal\|L | 124 | 3587.571583 | 0.670647 | 0.087912 | 0.783217 | 21 | 138.473313 | 0.341580 |
| B3 | B3\|1h\|3\|signal\|L | 286 | 313.625440 | 0.028304 | 0.496503 | 0.866134 | 29 | -1947.668168 | -2.137952 |
| B4 | B4\|1h\|20/5\|signal\|L | 298 | -3766.881808 | -0.432174 | 0.844156 | 0.932068 | 27 | -485.966326 | -0.727271 |
| C1 | C1\|1h\|20/12\|limit\|L | 809 | 16131.127431 | 0.837606 | 0.017982 | 0.470529 | 64 | 417.047032 | 0.441376 |
| C2 | C2\|4h\|20\|signal\|L | 260 | 8298.172535 | 0.385202 | 0.163836 | 0.714286 | 28 | 205.671764 | 0.110461 |
| C3 | C3\|4h\|inside\|signal\|L | 241 | 16903.820752 | 0.875279 | 0.024975 | 0.462537 | 23 | 1218.696610 | 0.950586 |
| C4 | C4\|4h\|pin/trend4h\|signal\|S | 312 | 4885.758569 | 0.276383 | 0.211788 | 0.718282 | 31 | 1797.620240 | 1.626458 |
| C5 | C5\|4h\|3\|signal\|L | 223 | 5061.372678 | 0.270780 | 0.276723 | 0.810190 | 20 | -957.015465 | -0.762728 |
| D1 | D1\|1h\|20\|signal\|L | 501 | -2119.575289 | -0.142290 | 0.613387 | 0.929071 | 46 | -445.083229 | -0.645561 |
| D2 | D2\|4h\|NR4\|signal\|L | 377 | 14046.353681 | 0.553030 | 0.110889 | 0.562438 | 30 | -1413.273212 | -0.679045 |
| E1 | E1\|1h\|3\|signal\|L | 375 | 14636.433664 | 1.148240 | 0.007992 | 0.529471 | 30 | 1447.343046 | 2.146867 |
| E2 | E2\|1h\|4h/follow/5\|signal\|L | 989 | 5346.597406 | 0.441069 | 0.196803 | 0.793207 | 108 | -274.989094 | -0.359267 |
| E3 | E3\|1h\|revert\|signal\|L | 831 | 1436.976051 | 0.137393 | 0.361638 | 0.863137 | 70 | -4477.095511 | -4.515554 |
| F1 | F1\|1h\|5/24\|signal\|LS | 818 | 16024.495580 | 0.749494 | 0.027972 | 0.463536 | 48 | 928.108334 | 0.762049 |
| F2 | F2\|4h\|--/fade/24\|signal\|L | 1307 | 7913.644060 | 0.305203 | 0.209790 | 0.774226 | 128 | -4210.083039 | -2.148457 |
| F3 | F3\|1h\|10/24\|signal\|LS | 873 | 35384.229653 | 1.485597 | 0.001998 | 0.147852 | 76 | 1182.394594 | 0.682082 |
| F4 | F4\|1h\|5/4\|signal\|L | 1812 | 8056.289799 | 0.598889 | 0.034965 | 0.708292 | 186 | 1122.396624 | 0.771955 |
| G1 | G1\|1m\|us/60\|signal\|L | 1011 | 9224.191527 | 0.647023 | 0.065934 | 0.701299 | 78 | -985.645471 | -0.805300 |
| G2 | G2\|1m\|before/60/60\|signal\|L | 713 | 5553.163853 | 0.791497 | 0.046953 | 0.769231 | 207 | 680.485058 | 0.959230 |
| G3 | G3\|1d\|1\|signal\|L | 288 | 10274.205055 | 0.739098 | 0.043956 | 0.665335 | 25 | -813.112803 | -0.902232 |
| H1 | H1\|4h\|55/20/squeeze10\|signal\|L | 25 | 2365.839905 | 0.149235 | 0.336663 | 0.809191 | 1 | -116.192822 | -1.420061 |
| H2 | H2\|1h\|40/60/funding5\|signal\|L | 186 | 7840.365732 | 0.506216 | 0.111888 | 0.686314 | 19 | 640.050249 | 1.292113 |
| H3 | H3\|1h\|4h20/60/C2\|signal\|S | 445 | -1258.288932 | -0.087344 | 0.563437 | 0.844156 | 47 | -493.601248 | -0.715704 |

## 추세추종 대표 칸

| family | cell_id | dev_n | dev_net_bps | dev_sharpe | dev_spa_p_zero | dev_spa_p_buy_hold | hold_n | hold_net_bps | hold_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | A1\|4h\|50/200\|trail2\|L | 27 | 10304.142669 | 0.944275 | 0.026973 | 0.653347 | 3 | -519.856183 | -2.122772 |
| A2 | A2\|4h\|55/10\|signal\|L | 96 | 18038.414122 | 0.906944 | 0.027972 | 0.419580 | 9 | -851.987712 | -1.965496 |
| A3 | A3\|4h\|720\|signal\|LS | 339 | 31309.380610 | 0.800353 | 0.032967 | 0.212787 | 45 | 3055.937445 | 1.065194 |
| A4 | A4\|4h\|10/3\|signal\|L | 130 | 17515.271415 | 0.602044 | 0.092907 | 0.436563 | 14 | -2251.052293 | -2.612842 |
| A5 | A5\|4h\|25\|trail2\|L | 180 | 18183.324390 | 0.783048 | 0.054945 | 0.408591 | 17 | -947.173409 | -1.435336 |
| A6 | A6\|1h\|40/60\|signal\|L | 228 | 5795.269532 | 0.363393 | 0.192807 | 0.743257 | 20 | 624.468656 | 1.260208 |

## 다중검정

| benchmark | n_cells | rc_stat | rc_p | spa_stat | spa_p | bootstrap_repetitions |
| --- | --- | --- | --- | --- | --- | --- |
| zero | 813 | 17.604094 | 0.341658 | 3.486203 | 0.143856 | 1000 |
| buy_hold | 813 | 9.812175 | 0.780220 | 1.140831 | 0.734266 | 1000 |

## 추세추종 연도별

| cell_id | family | segment | year | n | net_bps |
| --- | --- | --- | --- | --- | --- |
| A1\|4h\|50/200\|trail2\|L | A1 | DEV | 2021 | 3 | 1290.171039 |
| A1\|4h\|50/200\|trail2\|L | A1 | DEV | 2022 | 7 | -2003.354388 |
| A1\|4h\|50/200\|trail2\|L | A1 | DEV | 2023 | 4 | 4155.158585 |
| A1\|4h\|50/200\|trail2\|L | A1 | DEV | 2024 | 5 | 2182.837206 |
| A1\|4h\|50/200\|trail2\|L | A1 | DEV | 2025 | 6 | 1366.244854 |
| A1\|4h\|50/200\|trail2\|L | A1 | HOLD_B | 2026 | 3 | -519.856183 |
| A2\|4h\|55/10\|signal\|L | A2 | DEV | 2021 | 17 | 2640.480499 |
| A2\|4h\|55/10\|signal\|L | A2 | DEV | 2022 | 14 | -247.010758 |
| A2\|4h\|55/10\|signal\|L | A2 | DEV | 2023 | 15 | 4626.883333 |
| A2\|4h\|55/10\|signal\|L | A2 | DEV | 2024 | 22 | 2304.202445 |
| A2\|4h\|55/10\|signal\|L | A2 | DEV | 2025 | 17 | 293.796281 |
| A2\|4h\|55/10\|signal\|L | A2 | HOLD_B | 2026 | 9 | -851.987712 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 2021 | 57 | 7065.481337 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 2022 | 68 | 5716.403728 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 2023 | 41 | 10497.160184 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 2024 | 85 | -2477.627142 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 2025 | 75 | -214.227688 |
| A3\|4h\|720\|signal\|LS | A3 | HOLD_B | 2026 | 45 | 3055.937445 |
| A4\|4h\|10/3\|signal\|L | A4 | DEV | 2021 | 21 | 434.043390 |
| A4\|4h\|10/3\|signal\|L | A4 | DEV | 2022 | 26 | -3293.207081 |
| A4\|4h\|10/3\|signal\|L | A4 | DEV | 2023 | 24 | 5732.019792 |
| A4\|4h\|10/3\|signal\|L | A4 | DEV | 2024 | 25 | 4964.920427 |
| A4\|4h\|10/3\|signal\|L | A4 | DEV | 2025 | 24 | -447.672334 |
| A4\|4h\|10/3\|signal\|L | A4 | HOLD_B | 2026 | 14 | -2251.052293 |
| A5\|4h\|25\|trail2\|L | A5 | DEV | 2021 | 25 | 4162.639084 |
| A5\|4h\|25\|trail2\|L | A5 | DEV | 2022 | 40 | -5393.141270 |
| A5\|4h\|25\|trail2\|L | A5 | DEV | 2023 | 33 | 8229.857186 |
| A5\|4h\|25\|trail2\|L | A5 | DEV | 2024 | 33 | 4088.615960 |
| A5\|4h\|25\|trail2\|L | A5 | DEV | 2025 | 36 | -961.843000 |
| A5\|4h\|25\|trail2\|L | A5 | HOLD_B | 2026 | 17 | -947.173409 |
| A6\|1h\|40/60\|signal\|L | A6 | DEV | 2021 | 41 | 367.149707 |
| A6\|1h\|40/60\|signal\|L | A6 | DEV | 2022 | 43 | -3224.431784 |
| A6\|1h\|40/60\|signal\|L | A6 | DEV | 2023 | 38 | 2002.402724 |
| A6\|1h\|40/60\|signal\|L | A6 | DEV | 2024 | 45 | 651.310630 |
| A6\|1h\|40/60\|signal\|L | A6 | DEV | 2025 | 48 | -736.876098 |
| A6\|1h\|40/60\|signal\|L | A6 | HOLD_B | 2026 | 20 | 624.468656 |

## 동결 가설

0

## 소요 시간(초)

2194.194784

## k45_combo_robust_r2_25_20261004

- 테스트 재실행 `tests/test_k45_combo_robust_r2_25.py`: `5 passed in 2.06s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-25 |
| status | COMPLETE |
| started_utc | 2026-10-04T13:32:27.854939+00:00 |
| finished_utc | 2026-10-04T13:38:54.096402+00:00 |
| elapsed_seconds | 386.23502269992605 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | C1형 81개 이웃 조합 중 70% 이상에서 조합 Sharpe가 해당 F3 단독보다 높고 최대 낙폭이 같거나 작다(DEV_COMMON, PESS·OPT 각각). |
| segments | {"DEV_COMMON": ["2021-03-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"], "HOLD_B": ["2026-01-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00"]} |
| hold_b_used_for_decision | False |
| funding_boundaries | ["PESS", "OPT"] |
| collision_rule | FIRST |
| position_limit | 1 |
| cost_bps | [0.0, 4.0, 8.0, 12.0] |
| dsr_trials | [813, 5078] |
| pw | automatic Politis-White block |
| workers_max | 10 |
| numeric_threads | 1 |
| live_orders | 0 |
| downloads | 0 |
| retraining | 0 |
| hold_a_read | 0 |
| post_cutoff_read | 0 |
| r2_24_reproduction_matches | 16 |
| r2_24_reproduction_rows | 16 |
| neighbor_cells | 81 |
| model_r29_cells | 7 |
| model_r20_cells | 3 |
| hypothesis | [{"boundary": "OPT", "cell_n": 81, "both_frozen_n": 15, "both_frozen_ratio": 0.18518518518518517, "threshold": 0.7, "pass": false}, {"boundary": "PESS", "cell_n": 81, "both_frozen_n": 17, "both_frozen_ratio": 0.20987654320987653, "threshold": 0.7, "pass": false}] |
| max_concurrent | 1 |

- 출력 해시 확인: 19/19 일치

### REPORT.md 앞 150줄 (전체 669줄, 원문)

# R2-25

## 0

| live | download | retraining | workers_max | cutoff_yyyymmddhhmm | elapsed_seconds |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 10 | 202606302359 | 386.220666 |

## reproduction

| combo | boundary | segment | n_difference | net_total_bps_difference | mtm_daily_sharpe_difference | mtm_max_drawdown_bps_difference | pw_ci95_lower_daily_bps_difference | pw_ci95_upper_daily_bps_difference | max_abs_difference | match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | PESS | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C1 | PESS | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C1 | OPT | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C1 | OPT | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C3 | PESS | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C3 | PESS | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C3 | OPT | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C3 | OPT | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C4 | PESS | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C4 | PESS | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C4 | OPT | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C4 | OPT | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C5 | PESS | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C5 | PESS | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C5 | OPT | DEV_COMMON | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |
| C5 | OPT | HOLD_B | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 |

## neighbor_summary

| boundary | segment | cell_n | sharpe_difference_min | sharpe_difference_median | sharpe_difference_max | drawdown_difference_min_bps | drawdown_difference_median_bps | drawdown_difference_max_bps | pw_lower_min_bps | pw_lower_median_bps | pw_lower_max_bps | sharpe_up_n | drawdown_not_worse_n | both_frozen_n | both_strict_n | sharpe_up_ratio | drawdown_not_worse_ratio | both_frozen_ratio | both_strict_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPT | DEV_COMMON | 81 | -0.164355 | 0.087867 | 0.340133 | -762.711206 | 424.500633 | 2998.170619 | 3.499590 | 7.374884 | 11.897183 | 61 | 17 | 15 | 14 | 0.753086 | 0.209877 | 0.185185 | 0.172840 |
| OPT | HOLD_B | 81 | -0.303914 | 0.630304 | 1.927068 | -1151.365770 | -296.054965 | 636.556398 | -24.334227 | -9.294007 | 1.842648 | 71 | 57 | 57 | 57 | 0.876543 | 0.703704 | 0.703704 | 0.703704 |
| PESS | DEV_COMMON | 81 | -0.165763 | 0.087187 | 0.338219 | -764.812206 | 424.150433 | 3012.923719 | 3.332471 | 7.292326 | 11.821971 | 60 | 19 | 17 | 16 | 0.740741 | 0.234568 | 0.209877 | 0.197531 |
| PESS | HOLD_B | 81 | -0.304511 | 0.630092 | 1.926950 | -1153.237370 | -295.778765 | 636.180798 | -24.363791 | -9.338033 | 1.790570 | 71 | 57 | 57 | 57 | 0.876543 | 0.703704 | 0.703704 | 0.703704 |

## hypothesis

| boundary | cell_n | both_frozen_n | both_frozen_ratio | threshold | pass |
| --- | --- | --- | --- | --- | --- |
| OPT | 81 | 15 | 0.185185 | 0.700000 | 0 |
| PESS | 81 | 17 | 0.209877 | 0.700000 | 0 |

## neighbor_detail

| label | axis | boundary | neighbor_id | window_days | tail_pct | hold_hours | e1_z | segment | n | net_total_bps_combo | mtm_daily_sharpe_combo | mtm_max_drawdown_bps_combo | pw_status | pw_block | pw_ci95_lower_daily_bps_combo | pw_ci95_upper_daily_bps | pw_p_greater_zero | dsr_813 | dsr_813_sr0 | dsr_5078 | dsr_5078_sr0 | net_total_bps_f3 | mtm_daily_sharpe_f3 | mtm_max_drawdown_bps_f3 | pw_ci95_lower_daily_bps_f3 | sharpe_difference | drawdown_difference_bps | pw_lower_difference_bps | sharpe_up | drawdown_not_worse | drawdown_down | both_frozen | both_strict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| N01 | neighbor_combo | PESS | 1 | 60 | 5 | 12 | 2.000000 | DEV_COMMON | 1166 | 27320.586295 | 1.476723 | 5518.350226 | MEASURABLE | 1.512808 | 6.393184 | 24.737793 | 0.000500 | 0.029678 | 0.120277 | 0.003423 | 0.138939 | 23712.954319 | 1.529555 | 3122.627166 | 5.818948 | -0.052832 | 2395.723059 | 0.574236 | 0 | 0 | 0 | 0 | 0 |
| N01 | neighbor_combo | PESS | 1 | 60 | 5 | 12 | 2.000000 | HOLD_B | 115 | 3309.355689 | 2.395406 | 1204.860002 | MEASURABLE | 1.063159 | -4.307323 | 38.659081 | 0.046477 | 0.531474 | 0.120277 | 0.416923 | 0.138939 | 1609.348334 | 1.301242 | 1202.527764 | -11.705057 | 1.094164 | 2.332238 | 7.397735 | 1 | 0 | 0 | 0 | 0 |
| N01 | neighbor_combo | OPT | 1 | 60 | 5 | 12 | 2.000000 | DEV_COMMON | 1166 | 27629.743095 | 1.493016 | 5515.047426 | MEASURABLE | 1.505847 | 6.585787 | 24.947953 | 0.000500 | 0.032231 | 0.120277 | 0.003815 | 0.138939 | 23966.975419 | 1.545328 | 3120.461966 | 5.977376 | -0.052312 | 2394.585459 | 0.608411 | 0 | 0 | 0 | 0 | 0 |
| N01 | neighbor_combo | OPT | 1 | 60 | 5 | 12 | 2.000000 | HOLD_B | 115 | 3316.228689 | 2.400537 | 1203.724502 | MEASURABLE | 1.062867 | -4.272061 | 38.708388 | 0.045977 | 0.533135 | 0.120277 | 0.418523 | 0.138939 | 1614.262634 | 1.305328 | 1201.718964 | -11.680983 | 1.095209 | 2.005538 | 7.408922 | 1 | 0 | 0 | 0 | 0 |
| N02 | neighbor_combo | PESS | 2 | 60 | 5 | 12 | 2.500000 | DEV_COMMON | 1119 | 29963.963868 | 1.647249 | 4717.250288 | MEASURABLE | 1.315034 | 8.104321 | 26.141123 | 0.000500 | 0.066185 | 0.120277 | 0.009917 | 0.138939 | 23712.954319 | 1.529555 | 3122.627166 | 5.818948 | 0.117694 | 1594.623122 | 2.285373 | 1 | 0 | 0 | 0 | 0 |
| N02 | neighbor_combo | PESS | 2 | 60 | 5 | 12 | 2.500000 | HOLD_B | 112 | 2746.607341 | 1.993714 | 1204.860002 | MEASURABLE_BLOCK1 | 1.000000 | -6.551283 | 35.467942 | 0.083958 | 0.404602 | 0.120277 | 0.299971 | 0.138939 | 1609.348334 | 1.301242 | 1202.527764 | -11.705057 | 0.692473 | 2.332238 | 5.153774 | 1 | 0 | 0 | 0 | 0 |
| N02 | neighbor_combo | OPT | 2 | 60 | 5 | 12 | 2.500000 | DEV_COMMON | 1119 | 30266.654368 | 1.663442 | 4715.612988 | MEASURABLE | 1.308007 | 8.229774 | 26.408135 | 0.000500 | 0.071043 | 0.120277 | 0.010921 | 0.138939 | 23966.975419 | 1.545328 | 3120.461966 | 5.977376 | 0.118115 | 1595.151022 | 2.252397 | 1 | 0 | 0 | 0 | 0 |
| N02 | neighbor_combo | OPT | 2 | 60 | 5 | 12 | 2.500000 | HOLD_B | 112 | 2753.630141 | 1.998967 | 1203.724502 | MEASURABLE_BLOCK1 | 1.000000 | -6.502352 | 35.516234 | 0.083958 | 0.406190 | 0.120277 | 0.301367 | 0.138939 | 1614.262634 | 1.305328 | 1201.718964 | -11.680983 | 0.693639 | 2.005538 | 5.178631 | 1 | 0 | 0 | 0 | 0 |
| N03 | neighbor_combo | PESS | 3 | 60 | 5 | 12 | 3.000000 | DEV_COMMON | 1063 | 30187.410547 | 1.726627 | 3728.096174 | MEASURABLE_BLOCK1 | 1.000000 | 9.086953 | 26.024997 | 0.000500 | 0.090886 | 0.120277 | 0.015051 | 0.138939 | 23712.954319 | 1.529555 | 3122.627166 | 5.818948 | 0.197072 | 605.469007 | 3.268006 | 1 | 0 | 0 | 0 | 0 |
| N03 | neighbor_combo | PESS | 3 | 60 | 5 | 12 | 3.000000 | HOLD_B | 109 | 3052.486490 | 2.259327 | 1247.565762 | MEASURABLE_BLOCK1 | 1.000000 | -4.225574 | 36.629440 | 0.057971 | 0.487553 | 0.120277 | 0.374583 | 0.138939 | 1609.348334 | 1.301242 | 1202.527764 | -11.705057 | 0.958085 | 45.037998 | 7.479484 | 1 | 0 | 0 | 0 | 0 |
| N03 | neighbor_combo | OPT | 3 | 60 | 5 | 12 | 3.000000 | DEV_COMMON | 1063 | 30480.897047 | 1.742873 | 3726.806874 | MEASURABLE_BLOCK1 | 1.000000 | 9.232588 | 26.197259 | 0.000500 | 0.097132 | 0.120277 | 0.016505 | 0.138939 | 23966.975419 | 1.545328 | 3120.461966 | 5.977376 | 0.197545 | 606.344907 | 3.255212 | 1 | 0 | 0 | 0 | 0 |
| N03 | neighbor_combo | OPT | 3 | 60 | 5 | 12 | 3.000000 | HOLD_B | 109 | 3059.164790 | 2.264501 | 1246.025762 | MEASURABLE_BLOCK1 | 1.000000 | -4.180729 | 36.669293 | 0.057471 | 0.489220 | 0.120277 | 0.376134 | 0.138939 | 1614.262634 | 1.305328 | 1201.718964 | -11.680983 | 0.959173 | 44.306798 | 7.500254 | 1 | 0 | 0 | 0 | 0 |
| N04 | neighbor_combo | PESS | 4 | 60 | 5 | 24 | 2.000000 | DEV_COMMON | 824 | 27764.908482 | 1.440486 | 6195.640886 | MEASURABLE | 1.218691 | 5.806767 | 25.602711 | 0.001999 | 0.023141 | 0.120277 | 0.002390 | 0.138939 | 26127.724419 | 1.562976 | 3182.717167 | 6.723072 | -0.122490 | 3012.923719 | -0.916305 | 0 | 0 | 0 | 0 | 0 |
| N04 | neighbor_combo | PESS | 4 | 60 | 5 | 24 | 2.000000 | HOLD_B | 80 | 4491.332197 | 3.093542 | 946.292188 | MEASURABLE | 1.341148 | 1.790570 | 45.729649 | 0.016992 | 0.739822 | 0.120277 | 0.638611 | 0.138939 | 2424.626816 | 1.841079 | 1395.274806 | -8.811665 | 1.252463 | -448.982618 | 10.602235 | 1 | 1 | 1 | 1 | 1 |
| N04 | neighbor_combo | OPT | 4 | 60 | 5 | 24 | 2.000000 | DEV_COMMON | 824 | 28018.176682 | 1.453347 | 6175.556486 | MEASURABLE | 1.214494 | 5.947887 | 25.826593 | 0.001499 | 0.024782 | 0.120277 | 0.002613 | 0.138939 | 26319.620819 | 1.574076 | 3177.385867 | 6.808105 | -0.120729 | 2998.170619 | -0.860218 | 0 | 0 | 0 | 0 | 0 |
| N04 | neighbor_combo | OPT | 4 | 60 | 5 | 24 | 2.000000 | HOLD_B | 80 | 4497.998197 | 3.098110 | 946.292188 | MEASURABLE | 1.340885 | 1.842648 | 45.687345 | 0.016992 | 0.741053 | 0.120277 | 0.640015 | 0.138939 | 2429.141516 | 1.844442 | 1394.098006 | -8.814123 | 1.253668 | -447.805818 | 10.656771 | 1 | 1 | 1 | 1 | 1 |
| N05 | neighbor_combo | PESS | 5 | 60 | 5 | 24 | 2.500000 | DEV_COMMON | 774 | 29976.475680 | 1.582711 | 5485.030499 | MEASURABLE_BLOCK1 | 1.000000 | 7.732187 | 26.481465 | 0.001000 | 0.047028 | 0.120277 | 0.006051 | 0.138939 | 26127.724419 | 1.562976 | 3182.717167 | 6.723072 | 0.019735 | 2302.313333 | 1.009115 | 1 | 0 | 0 | 0 | 0 |
| N05 | neighbor_combo | PESS | 5 | 60 | 5 | 24 | 2.500000 | HOLD_B | 74 | 3593.357514 | 2.480608 | 1341.644897 | MEASURABLE | 1.899866 | -3.041360 | 41.497124 | 0.042979 | 0.557313 | 0.120277 | 0.445459 | 0.138939 | 2424.626816 | 1.841079 | 1395.274806 | -8.811665 | 0.639529 | -53.629909 | 5.770305 | 1 | 1 | 1 | 1 | 1 |
| N05 | neighbor_combo | OPT | 5 | 60 | 5 | 24 | 2.500000 | DEV_COMMON | 774 | 30219.300080 | 1.595239 | 5465.611599 | MEASURABLE_BLOCK1 | 1.000000 | 7.848850 | 26.621639 | 0.001000 | 0.049913 | 0.120277 | 0.006555 | 0.138939 | 26319.620819 | 1.574076 | 3177.385867 | 6.808105 | 0.021163 | 2288.225733 | 1.040745 | 1 | 0 | 0 | 0 | 0 |
| N05 | neighbor_combo | OPT | 5 | 60 | 5 | 24 | 2.500000 | HOLD_B | 74 | 3599.980714 | 2.485123 | 1341.644897 | MEASURABLE | 1.899534 | -3.002701 | 41.535175 | 0.041979 | 0.558730 | 0.120277 | 0.446858 | 0.138939 | 2429.141516 | 1.844442 | 1394.098006 | -8.814123 | 0.640681 | -52.453109 | 5.811422 | 1 | 1 | 1 | 1 | 1 |
| N06 | neighbor_combo | PESS | 6 | 60 | 5 | 24 | 3.000000 | DEV_COMMON | 711 | 31990.384572 | 1.746884 | 3924.079237 | MEASURABLE_BLOCK1 | 1.000000 | 9.167510 | 27.457548 | 0.000500 | 0.095602 | 0.120277 | 0.015668 | 0.138939 | 26127.724419 | 1.562976 | 3182.717167 | 6.723072 | 0.183908 | 741.362070 | 2.444437 | 1 | 0 | 0 | 0 | 0 |
| N06 | neighbor_combo | PESS | 6 | 60 | 5 | 24 | 3.000000 | HOLD_B | 70 | 3968.228976 | 2.784029 | 1405.167900 | MEASURABLE | 1.792458 | -0.864024 | 43.022986 | 0.027486 | 0.651232 | 0.120277 | 0.541259 | 0.138939 | 2424.626816 | 1.841079 | 1395.274806 | -8.811665 | 0.942950 | 9.893095 | 7.947641 | 1 | 0 | 0 | 0 | 0 |
| N06 | neighbor_combo | OPT | 6 | 60 | 5 | 24 | 3.000000 | DEV_COMMON | 711 | 32222.538372 | 1.759209 | 3923.079237 | MEASURABLE_BLOCK1 | 1.000000 | 9.275786 | 27.573594 | 0.000500 | 0.100569 | 0.120277 | 0.016817 | 0.138939 | 26319.620819 | 1.574076 | 3177.385867 | 6.808105 | 0.185133 | 745.693370 | 2.467680 | 1 | 0 | 0 | 0 | 0 |
| N06 | neighbor_combo | OPT | 6 | 60 | 5 | 24 | 3.000000 | HOLD_B | 70 | 3974.507676 | 2.788415 | 1403.259900 | MEASURABLE | 1.792154 | -0.829190 | 43.051341 | 0.027486 | 0.652552 | 0.120277 | 0.542657 | 0.138939 | 2429.141516 | 1.844442 | 1394.098006 | -8.814123 | 0.943973 | 9.161895 | 7.984933 | 1 | 0 | 0 | 0 | 0 |
| N07 | neighbor_combo | PESS | 7 | 60 | 5 | 48 | 2.000000 | DEV_COMMON | 619 | 26296.408156 | 1.307036 | 7414.187986 | MEASURABLE | 1.324162 | 4.578958 | 25.074313 | 0.002499 | 0.011105 | 0.120277 | 0.000937 | 0.138939 | 23714.848714 | 1.296406 | 6557.374296 | 4.404724 | 0.010630 | 856.813690 | 0.174234 | 1 | 0 | 0 | 0 | 0 |
| N07 | neighbor_combo | PESS | 7 | 60 | 5 | 48 | 2.000000 | HOLD_B | 62 | 4476.461461 | 3.069466 | 1045.907976 | MEASURABLE | 1.848772 | 1.240069 | 46.658498 | 0.020990 | 0.731712 | 0.120277 | 0.630215 | 0.138939 | 2743.014327 | 1.869677 | 1624.138752 | -6.486538 | 1.199789 | -578.230776 | 7.726607 | 1 | 1 | 1 | 1 | 1 |
| N07 | neighbor_combo | OPT | 7 | 60 | 5 | 48 | 2.000000 | DEV_COMMON | 619 | 26504.707556 | 1.317260 | 7389.649186 | MEASURABLE | 1.310808 | 4.490688 | 25.197606 | 0.001000 | 0.011791 | 0.120277 | 0.001011 | 0.138939 | 23859.488914 | 1.304194 | 6555.374296 | 4.482488 | 0.013065 | 834.274890 | 0.008200 | 1 | 0 | 0 | 0 | 0 |
| N07 | neighbor_combo | OPT | 7 | 60 | 5 | 48 | 2.000000 | HOLD_B | 62 | 4482.860461 | 3.073856 | 1045.687676 | MEASURABLE | 1.848772 | 1.263717 | 46.684900 | 0.020990 | 0.732904 | 0.120277 | 0.631562 | 0.138939 | 2747.082327 | 1.872429 | 1623.299952 | -6.460443 | 1.201427 | -577.612276 | 7.724160 | 1 | 1 | 1 | 1 | 1 |
| N08 | neighbor_combo | PESS | 8 | 60 | 5 | 48 | 2.500000 | DEV_COMMON | 573 | 27079.583557 | 1.363840 | 6980.880644 | MEASURABLE_BLOCK1 | 1.000000 | 5.476391 | 25.712146 | 0.001999 | 0.015284 | 0.120277 | 0.001403 | 0.138939 | 23714.848714 | 1.296406 | 6557.374296 | 4.404724 | 0.067434 | 423.506347 | 1.071667 | 1 | 0 | 0 | 0 | 0 |
| N08 | neighbor_combo | PESS | 8 | 60 | 5 | 48 | 2.500000 | HOLD_B | 57 | 3043.356312 | 2.000189 | 1935.288196 | MEASURABLE | 2.249728 | -7.170882 | 40.869201 | 0.087456 | 0.410724 | 0.120277 | 0.309954 | 0.138939 | 2743.014327 | 1.869677 | 1624.138752 | -6.486538 | 0.130512 | 311.149445 | -0.684344 | 1 | 0 | 0 | 0 | 0 |
| N08 | neighbor_combo | OPT | 8 | 60 | 5 | 48 | 2.500000 | DEV_COMMON | 573 | 27278.200057 | 1.373725 | 6957.007344 | MEASURABLE_BLOCK1 | 1.000000 | 5.571960 | 25.817200 | 0.001999 | 0.016161 | 0.120277 | 0.001508 | 0.138939 | 23859.488914 | 1.304194 | 6555.374296 | 4.482488 | 0.069531 | 401.633047 | 1.089472 | 1 | 0 | 0 | 0 | 0 |
| N08 | neighbor_combo | OPT | 8 | 60 | 5 | 48 | 2.500000 | HOLD_B | 57 | 3049.532812 | 2.004225 | 1935.288196 | MEASURABLE | 2.249855 | -7.139979 | 40.905077 | 0.086457 | 0.411902 | 0.120277 | 0.311011 | 0.138939 | 2747.082327 | 1.872429 | 1623.299952 | -6.460443 | 0.131796 | 311.988245 | -0.679535 | 1 | 0 | 0 | 0 | 0 |
| N09 | neighbor_combo | PESS | 9 | 60 | 5 | 48 | 3.000000 | DEV_COMMON | 510 | 29133.740869 | 1.486480 | 6766.414003 | MEASURABLE_BLOCK1 | 1.000000 | 7.199046 | 26.724953 | 0.001499 | 0.029652 | 0.120277 | 0.003317 | 0.138939 | 23714.848714 | 1.296406 | 6557.374296 | 4.404724 | 0.190074 | 209.039706 | 2.794322 | 1 | 0 | 0 | 0 | 0 |
| N09 | neighbor_combo | PESS | 9 | 60 | 5 | 48 | 3.000000 | HOLD_B | 53 | 3333.622421 | 2.219886 | 1794.529143 | MEASURABLE | 2.207851 | -5.079575 | 40.897382 | 0.062469 | 0.476255 | 0.120277 | 0.370028 | 0.138939 | 2743.014327 | 1.869677 | 1624.138752 | -6.486538 | 0.350209 | 170.390391 | 1.406963 | 1 | 0 | 0 | 0 | 0 |
| N09 | neighbor_combo | OPT | 9 | 60 | 5 | 48 | 3.000000 | DEV_COMMON | 510 | 29316.313269 | 1.495664 | 6759.302503 | MEASURABLE_BLOCK1 | 1.000000 | 7.283085 | 26.821673 | 0.001499 | 0.031084 | 0.120277 | 0.003530 | 0.138939 | 23859.488914 | 1.304194 | 6555.374296 | 4.482488 | 0.191470 | 203.928206 | 2.800597 | 1 | 0 | 0 | 0 | 0 |
| N09 | neighbor_combo | OPT | 9 | 60 | 5 | 48 | 3.000000 | HOLD_B | 53 | 3339.454421 | 2.223779 | 1794.529143 | MEASURABLE | 2.208029 | -5.074354 | 40.917655 | 0.062469 | 0.477436 | 0.120277 | 0.371134 | 0.138939 | 2747.082327 | 1.872429 | 1623.299952 | -6.460443 | 0.351350 | 171.229191 | 1.386089 | 1 | 0 | 0 | 0 | 0 |
| N10 | neighbor_combo | PESS | 10 | 60 | 10 | 12 | 2.000000 | DEV_COMMON | 1543 | 30873.200822 | 1.565763 | 4870.748652 | MEASURABLE | 2.136542 | 7.856798 | 26.807334 | 0.000500 | 0.046931 | 0.120277 | 0.006364 | 0.138939 | 25762.976943 | 1.442582 | 3092.807713 | 6.139879 | 0.123181 | 1777.940938 | 1.716919 | 1 | 0 | 0 | 0 | 0 |
| N10 | neighbor_combo | PESS | 10 | 60 | 10 | 12 | 2.000000 | HOLD_B | 158 | 4687.921677 | 2.716275 | 1259.856638 | MEASURABLE_BLOCK1 | 1.000000 | -2.217305 | 50.382344 | 0.034983 | 0.638642 | 0.120277 | 0.520914 | 0.138939 | 3115.030913 | 1.932021 | 2189.285150 | -8.388209 | 0.784254 | -929.428512 | 6.170904 | 1 | 1 | 1 | 1 | 1 |
| N10 | neighbor_combo | OPT | 10 | 60 | 10 | 12 | 2.000000 | DEV_COMMON | 1543 | 31229.783622 | 1.583531 | 4867.735152 | MEASURABLE | 2.125188 | 8.136834 | 27.162039 | 0.000500 | 0.050966 | 0.120277 | 0.007105 | 0.138939 | 26087.639343 | 1.460354 | 3092.807713 | 5.816280 | 0.123177 | 1774.927438 | 2.320554 | 1 | 0 | 0 | 0 | 0 |
| N10 | neighbor_combo | OPT | 10 | 60 | 10 | 12 | 2.000000 | HOLD_B | 158 | 4705.481877 | 2.726690 | 1259.631538 | MEASURABLE_BLOCK1 | 1.000000 | -2.158060 | 50.495515 | 0.033983 | 0.642022 | 0.120277 | 0.524445 | 0.138939 | 3134.773713 | 1.944446 | 2183.665850 | -8.292399 | 0.782244 | -924.034312 | 6.134339 | 1 | 1 | 1 | 1 | 1 |
| N11 | neighbor_combo | PESS | 11 | 60 | 10 | 12 | 2.500000 | DEV_COMMON | 1508 | 31552.133919 | 1.619966 | 4238.531924 | MEASURABLE | 1.889715 | 8.302624 | 27.088462 | 0.000500 | 0.060069 | 0.120277 | 0.008855 | 0.138939 | 25762.976943 | 1.442582 | 3092.807713 | 6.139879 | 0.177385 | 1145.724211 | 2.162745 | 1 | 0 | 0 | 0 | 0 |
| N11 | neighbor_combo | PESS | 11 | 60 | 10 | 12 | 2.500000 | HOLD_B | 156 | 4424.497070 | 2.574056 | 1440.281106 | MEASURABLE_BLOCK1 | 1.000000 | -3.802636 | 48.366107 | 0.037981 | 0.592297 | 0.120277 | 0.472914 | 0.138939 | 3115.030913 | 1.932021 | 2189.285150 | -8.388209 | 0.642035 | -749.004044 | 4.585572 | 1 | 1 | 1 | 1 | 1 |
| N11 | neighbor_combo | OPT | 11 | 60 | 10 | 12 | 2.500000 | DEV_COMMON | 1508 | 31905.209619 | 1.637785 | 4237.183924 | MEASURABLE | 1.878922 | 8.519123 | 27.180686 | 0.000500 | 0.064994 | 0.120277 | 0.009850 | 0.138939 | 26087.639343 | 1.460354 | 3092.807713 | 5.816280 | 0.177431 | 1144.376211 | 2.702843 | 1 | 0 | 0 | 0 | 0 |
| N11 | neighbor_combo | OPT | 11 | 60 | 10 | 12 | 2.500000 | HOLD_B | 156 | 4442.790070 | 2.584953 | 1438.189206 | MEASURABLE_BLOCK1 | 1.000000 | -3.734382 | 48.479638 | 0.037481 | 0.595929 | 0.120277 | 0.476566 | 0.138939 | 3134.773713 | 1.944446 | 2183.665850 | -8.292399 | 0.640507 | -745.476644 | 4.558017 | 1 | 1 | 1 | 1 | 1 |
| N12 | neighbor_combo | PESS | 12 | 60 | 10 | 12 | 3.000000 | DEV_COMMON | 1474 | 33147.156770 | 1.733902 | 3249.377810 | MEASURABLE | 1.544920 | 9.796993 | 28.421740 | 0.000500 | 0.096034 | 0.120277 | 0.016620 | 0.138939 | 25762.976943 | 1.442582 | 3092.807713 | 6.139879 | 0.291320 | 156.570096 | 3.657114 | 1 | 0 | 0 | 0 | 0 |
| N12 | neighbor_combo | PESS | 12 | 60 | 10 | 12 | 3.000000 | HOLD_B | 154 | 4399.312346 | 2.585794 | 1567.407722 | MEASURABLE_BLOCK1 | 1.000000 | -3.147114 | 48.115988 | 0.038481 | 0.596664 | 0.120277 | 0.476737 | 0.138939 | 3115.030913 | 1.932021 | 2189.285150 | -8.388209 | 0.653773 | -621.877429 | 5.241095 | 1 | 1 | 1 | 1 | 1 |
| N12 | neighbor_combo | OPT | 12 | 60 | 10 | 12 | 3.000000 | DEV_COMMON | 1474 | 33499.510970 | 1.751950 | 3248.377810 | MEASURABLE | 1.533253 | 10.201225 | 28.696158 | 0.000500 | 0.103203 | 0.120277 | 0.018367 | 0.138939 | 26087.639343 | 1.460354 | 3092.807713 | 5.816280 | 0.291596 | 155.570096 | 4.384946 | 1 | 0 | 0 | 0 | 0 |
| N12 | neighbor_combo | OPT | 12 | 60 | 10 | 12 | 3.000000 | HOLD_B | 154 | 4418.865146 | 2.597514 | 1562.128922 | MEASURABLE_BLOCK1 | 1.000000 | -3.018129 | 48.216591 | 0.037981 | 0.600583 | 0.120277 | 0.480693 | 0.138939 | 3134.773713 | 1.944446 | 2183.665850 | -8.292399 | 0.653069 | -621.536929 | 5.274270 | 1 | 1 | 1 | 1 | 1 |
| N13 | neighbor_combo | PESS | 13 | 60 | 10 | 24 | 2.000000 | DEV_COMMON | 1000 | 30430.807477 | 1.419739 | 5802.538483 | MEASURABLE | 1.945946 | 6.306942 | 27.596447 | 0.001000 | 0.021845 | 0.120277 | 0.002284 | 0.138939 | 28289.541821 | 1.423110 | 3883.302993 | 6.660637 | -0.003371 | 1919.235490 | -0.353695 | 0 | 0 | 0 | 0 | 0 |
| N13 | neighbor_combo | PESS | 13 | 60 | 10 | 24 | 2.000000 | HOLD_B | 100 | 4656.527355 | 2.415868 | 1864.272226 | MEASURABLE | 2.931611 | -0.669762 | 50.406340 | 0.027486 | 0.534450 | 0.120277 | 0.430608 | 0.138939 | 2927.087016 | 1.589870 | 2705.822170 | -9.504390 | 0.825998 | -841.549945 | 8.834628 | 1 | 1 | 1 | 1 | 1 |
| N13 | neighbor_combo | OPT | 13 | 60 | 10 | 24 | 2.000000 | DEV_COMMON | 1000 | 30665.188477 | 1.430486 | 5799.524983 | MEASURABLE | 1.936728 | 6.622684 | 27.719224 | 0.000500 | 0.023128 | 0.120277 | 0.002459 | 0.138939 | 28499.505421 | 1.433437 | 3883.302993 | 6.541966 | -0.002951 | 1916.221990 | 0.080718 | 0 | 0 | 0 | 0 | 0 |
| N13 | neighbor_combo | OPT | 13 | 60 | 10 | 24 | 2.000000 | HOLD_B | 100 | 4667.050755 | 2.421249 | 1864.272226 | MEASURABLE | 2.931150 | -0.602072 | 50.475314 | 0.027486 | 0.536018 | 0.120277 | 0.432155 | 0.138939 | 2937.986316 | 1.595750 | 2700.487670 | -9.435438 | 0.825499 | -836.215445 | 8.833367 | 1 | 1 | 1 | 1 | 1 |
| N14 | neighbor_combo | PESS | 14 | 60 | 10 | 24 | 2.500000 | DEV_COMMON | 962 | 31802.249018 | 1.498982 | 5170.321756 | MEASURABLE | 1.614383 | 7.581351 | 28.998545 | 0.000500 | 0.032890 | 0.120277 | 0.003895 | 0.138939 | 28289.541821 | 1.423110 | 3883.302993 | 6.660637 | 0.075872 | 1287.018762 | 0.920714 | 1 | 0 | 0 | 0 | 0 |
| N14 | neighbor_combo | PESS | 14 | 60 | 10 | 24 | 2.500000 | HOLD_B | 96 | 4401.145048 | 2.291020 | 1909.444899 | MEASURABLE | 2.879600 | -1.133047 | 47.967601 | 0.031484 | 0.497989 | 0.120277 | 0.394830 | 0.138939 | 2927.087016 | 1.589870 | 2705.822170 | -9.504390 | 0.701149 | -796.377272 | 8.371344 | 1 | 1 | 1 | 1 | 1 |
| N14 | neighbor_combo | OPT | 14 | 60 | 10 | 24 | 2.500000 | DEV_COMMON | 962 | 32034.837618 | 1.509772 | 5168.973756 | MEASURABLE | 1.605678 | 7.707243 | 29.260152 | 0.000500 | 0.034709 | 0.120277 | 0.004181 | 0.138939 | 28499.505421 | 1.433437 | 3883.302993 | 6.541966 | 0.076335 | 1285.670762 | 1.165277 | 1 | 0 | 0 | 0 | 0 |
| N14 | neighbor_combo | OPT | 14 | 60 | 10 | 24 | 2.500000 | HOLD_B | 96 | 4412.316648 | 2.296778 | 1909.444899 | MEASURABLE | 2.879452 | -1.049875 | 48.027999 | 0.030485 | 0.499675 | 0.120277 | 0.396454 | 0.138939 | 2937.986316 | 1.595750 | 2700.487670 | -9.435438 | 0.701028 | -791.042772 | 8.385563 | 1 | 1 | 1 | 1 | 1 |
| N15 | neighbor_combo | PESS | 15 | 60 | 10 | 24 | 3.000000 | DEV_COMMON | 919 | 35671.061598 | 1.710607 | 4181.167641 | MEASURABLE | 1.213259 | 10.038777 | 30.914958 | 0.000500 | 0.085795 | 0.120277 | 0.014006 | 0.138939 | 28289.541821 | 1.423110 | 3883.302993 | 6.660637 | 0.287497 | 297.864648 | 3.378141 | 1 | 0 | 0 | 0 | 0 |
| N15 | neighbor_combo | PESS | 15 | 60 | 10 | 24 | 3.000000 | HOLD_B | 93 | 4567.923777 | 2.392320 | 1934.042438 | MEASURABLE | 2.925704 | -0.636881 | 48.794190 | 0.029985 | 0.527607 | 0.120277 | 0.423782 | 0.138939 | 2927.087016 | 1.589870 | 2705.822170 | -9.504390 | 0.802450 | -771.779732 | 8.867509 | 1 | 1 | 1 | 1 | 1 |
| N15 | neighbor_combo | OPT | 15 | 60 | 10 | 24 | 3.000000 | DEV_COMMON | 919 | 35902.424298 | 1.721469 | 4180.167641 | MEASURABLE | 1.204142 | 10.486777 | 31.083061 | 0.000500 | 0.089744 | 0.120277 | 0.014904 | 0.138939 | 28499.505421 | 1.433437 | 3883.302993 | 6.541966 | 0.288032 | 296.864648 | 3.944811 | 1 | 0 | 0 | 0 | 0 |
| N15 | neighbor_combo | OPT | 15 | 60 | 10 | 24 | 3.000000 | HOLD_B | 93 | 4579.095377 | 2.398114 | 1934.042438 | MEASURABLE | 2.925619 | -0.574326 | 48.851094 | 0.029985 | 0.529298 | 0.120277 | 0.425445 | 0.138939 | 2937.986316 | 1.595750 | 2700.487670 | -9.435438 | 0.802365 | -766.445232 | 8.861113 | 1 | 1 | 1 | 1 | 1 |
| N16 | neighbor_combo | PESS | 16 | 60 | 10 | 48 | 2.000000 | DEV_COMMON | 678 | 30041.695550 | 1.387039 | 5962.413459 | MEASURABLE | 3.140001 | 6.975728 | 27.206360 | 0.001499 | 0.019930 | 0.120277 | 0.002120 | 0.138939 | 29935.543815 | 1.436530 | 4843.543026 | 7.364581 | -0.049491 | 1118.870433 | -0.388853 | 0 | 0 | 0 | 0 | 0 |
| N16 | neighbor_combo | PESS | 16 | 60 | 10 | 48 | 2.000000 | HOLD_B | 69 | 3647.607833 | 1.910689 | 1818.523792 | MEASURABLE | 3.004752 | -6.543127 | 44.593017 | 0.061969 | 0.387543 | 0.120277 | 0.291558 | 0.138939 | 3783.548336 | 1.902448 | 2406.291271 | -5.988646 | 0.008241 | -587.767479 | -0.554480 | 1 | 1 | 1 | 1 | 1 |
| N16 | neighbor_combo | OPT | 16 | 60 | 10 | 48 | 2.000000 | DEV_COMMON | 678 | 30218.443450 | 1.395000 | 5959.399959 | MEASURABLE | 3.132023 | 7.211400 | 27.382601 | 0.001499 | 0.020794 | 0.120277 | 0.002240 | 0.138939 | 30078.649815 | 1.443169 | 4843.543026 | 7.308140 | -0.048169 | 1115.856933 | -0.096740 | 0 | 0 | 0 | 0 | 0 |
| N16 | neighbor_combo | OPT | 16 | 60 | 10 | 48 | 2.000000 | HOLD_B | 69 | 3654.231033 | 1.914011 | 1818.523792 | MEASURABLE | 3.003852 | -6.496717 | 44.632850 | 0.061969 | 0.388475 | 0.120277 | 0.292388 | 0.138939 | 3790.265136 | 1.905577 | 2403.514771 | -5.950109 | 0.008434 | -584.990979 | -0.546608 | 1 | 1 | 1 | 1 | 1 |
| N17 | neighbor_combo | PESS | 17 | 60 | 10 | 48 | 2.500000 | DEV_COMMON | 640 | 31561.284501 | 1.470083 | 5131.225880 | MEASURABLE | 2.764828 | 7.828172 | 28.169355 | 0.000500 | 0.030759 | 0.120277 | 0.003736 | 0.138939 | 29935.543815 | 1.436530 | 4843.543026 | 7.364581 | 0.033554 | 287.682854 | 0.463591 | 1 | 0 | 0 | 0 | 0 |
| N17 | neighbor_combo | PESS | 17 | 60 | 10 | 48 | 2.500000 | HOLD_B | 65 | 3163.181520 | 1.597936 | 2825.647757 | MEASURABLE | 2.670281 | -10.416750 | 44.114945 | 0.110945 | 0.303781 | 0.120277 | 0.219123 | 0.138939 | 3783.548336 | 1.902448 | 2406.291271 | -5.988646 | -0.304511 | 419.356486 | -4.428104 | 0 | 0 | 0 | 0 | 0 |
| N17 | neighbor_combo | OPT | 17 | 60 | 10 | 48 | 2.500000 | DEV_COMMON | 640 | 31732.288601 | 1.477863 | 5129.877880 | MEASURABLE | 2.757642 | 7.795848 | 28.219215 | 0.000500 | 0.031975 | 0.120277 | 0.003930 | 0.138939 | 30078.649815 | 1.443169 | 4843.543026 | 7.308140 | 0.034694 | 286.334854 | 0.487708 | 1 | 0 | 0 | 0 | 0 |
| N17 | neighbor_combo | OPT | 17 | 60 | 10 | 48 | 2.500000 | HOLD_B | 65 | 3170.731720 | 1.601662 | 2822.915257 | MEASURABLE | 2.670229 | -10.390235 | 44.168703 | 0.110945 | 0.304723 | 0.120277 | 0.219913 | 0.138939 | 3790.265136 | 1.905577 | 2403.514771 | -5.950109 | -0.303914 | 419.400486 | -4.440126 | 0 | 0 | 0 | 0 | 0 |
| N18 | neighbor_combo | PESS | 18 | 60 | 10 | 48 | 3.000000 | DEV_COMMON | 595 | 33398.450266 | 1.560384 | 4142.071766 | MEASURABLE | 2.341465 | 8.469747 | 29.387114 | 0.000500 | 0.048158 | 0.120277 | 0.006813 | 0.138939 | 29935.543815 | 1.436530 | 4843.543026 | 7.364581 | 0.123854 | -701.471261 | 1.105167 | 1 | 1 | 1 | 1 | 1 |
| N18 | neighbor_combo | PESS | 18 | 60 | 10 | 48 | 3.000000 | HOLD_B | 61 | 3411.615766 | 1.732058 | 2850.245297 | MEASURABLE | 2.821649 | -9.255237 | 45.311348 | 0.087956 | 0.338760 | 0.120277 | 0.248921 | 0.138939 | 3783.548336 | 1.902448 | 2406.291271 | -5.988646 | -0.170390 | 443.954026 | -3.266591 | 0 | 0 | 0 | 0 | 0 |
| N18 | neighbor_combo | OPT | 18 | 60 | 10 | 48 | 3.000000 | DEV_COMMON | 595 | 33555.884066 | 1.567506 | 4141.071766 | MEASURABLE | 2.336672 | 8.634001 | 29.485794 | 0.000500 | 0.049759 | 0.120277 | 0.007117 | 0.138939 | 30078.649815 | 1.443169 | 4843.543026 | 7.308140 | 0.124337 | -702.471261 | 1.325861 | 1 | 1 | 1 | 1 | 1 |
| N18 | neighbor_combo | OPT | 18 | 60 | 10 | 48 | 3.000000 | HOLD_B | 61 | 3419.165966 | 1.735797 | 2847.512797 | MEASURABLE | 2.821638 | -9.201383 | 45.343818 | 0.086957 | 0.339755 | 0.120277 | 0.249777 | 0.138939 | 3790.265136 | 1.905577 | 2403.514771 | -5.950109 | -0.169779 | 443.998026 | -3.251274 | 0 | 0 | 0 | 0 | 0 |
| N19 | neighbor_combo | PESS | 19 | 60 | 15 | 12 | 2.000000 | DEV_COMMON | 1822 | 28496.992831 | 1.331264 | 4816.503795 | MEASURABLE | 1.724377 | 5.521048 | 26.537735 | 0.001999 | 0.014562 | 0.120277 | 0.001411 | 0.138939 | 27208.083939 | 1.356839 | 3786.271122 | 5.238112 | -0.025575 | 1030.232673 | 0.282936 | 0 | 0 | 0 | 0 | 0 |
| N19 | neighbor_combo | PESS | 19 | 60 | 15 | 12 | 2.000000 | HOLD_B | 193 | 4972.154743 | 2.617016 | 1435.519523 | MEASURABLE_BLOCK1 | 1.000000 | -3.247408 | 55.214311 | 0.037481 | 0.603322 | 0.120277 | 0.487749 | 0.138939 | 3408.658790 | 1.877275 | 2252.641992 | -10.014392 | 0.739741 | -817.122469 | 6.766984 | 1 | 1 | 1 | 1 | 1 |
| N19 | neighbor_combo | OPT | 19 | 60 | 15 | 12 | 2.000000 | DEV_COMMON | 1822 | 28928.522331 | 1.351390 | 4810.490295 | MEASURABLE | 1.722288 | 5.947286 | 26.766818 | 0.001999 | 0.016291 | 0.120277 | 0.001629 | 0.138939 | 27614.927639 | 1.377081 | 3779.686322 | 5.487054 | -0.025691 | 1030.803973 | 0.460232 | 0 | 0 | 0 | 0 | 0 |
| N19 | neighbor_combo | OPT | 19 | 60 | 15 | 12 | 2.000000 | HOLD_B | 193 | 4989.987343 | 2.626806 | 1435.519523 | MEASURABLE_BLOCK1 | 1.000000 | -3.151087 | 55.329885 | 0.037481 | 0.606478 | 0.120277 | 0.490948 | 0.138939 | 3428.486590 | 1.888371 | 2238.457792 | -9.879823 | 0.738435 | -802.938269 | 6.728736 | 1 | 1 | 1 | 1 | 1 |
| N20 | neighbor_combo | PESS | 20 | 60 | 15 | 12 | 2.500000 | DEV_COMMON | 1801 | 29187.498542 | 1.371513 | 3945.072705 | MEASURABLE | 1.383359 | 6.366902 | 27.369042 | 0.001999 | 0.018256 | 0.120277 | 0.001889 | 0.138939 | 27208.083939 | 1.356839 | 3786.271122 | 5.238112 | 0.014674 | 158.801583 | 1.128790 | 1 | 0 | 0 | 0 | 0 |
| N20 | neighbor_combo | PESS | 20 | 60 | 15 | 12 | 2.500000 | HOLD_B | 191 | 4854.530885 | 2.576407 | 1480.692196 | MEASURABLE | 1.008643 | -3.383873 | 53.722436 | 0.037481 | 0.590661 | 0.120277 | 0.474397 | 0.138939 | 3408.658790 | 1.877275 | 2252.641992 | -10.014392 | 0.699132 | -771.949796 | 6.630519 | 1 | 1 | 1 | 1 | 1 |
| N20 | neighbor_combo | OPT | 20 | 60 | 15 | 12 | 2.500000 | DEV_COMMON | 1801 | 29623.527242 | 1.391979 | 3938.487905 | MEASURABLE | 1.382116 | 6.614749 | 27.579290 | 0.001999 | 0.020390 | 0.120277 | 0.002180 | 0.138939 | 27614.927639 | 1.377081 | 3779.686322 | 5.487054 | 0.014898 | 158.801583 | 1.127696 | 1 | 0 | 0 | 0 | 0 |
| N20 | neighbor_combo | OPT | 20 | 60 | 15 | 12 | 2.500000 | HOLD_B | 191 | 4872.602885 | 2.586380 | 1480.692196 | MEASURABLE | 1.007847 | -3.605128 | 53.871013 | 0.037481 | 0.593905 | 0.120277 | 0.477651 | 0.138939 | 3428.486590 | 1.888371 | 2238.457792 | -9.879823 | 0.698009 | -757.765596 | 6.274695 | 1 | 1 | 1 | 1 | 1 |
| N21 | neighbor_combo | PESS | 21 | 60 | 15 | 12 | 3.000000 | DEV_COMMON | 1785 | 32151.942396 | 1.533748 | 3602.599397 | MEASURABLE | 1.078927 | 8.121664 | 28.694028 | 0.001499 | 0.041430 | 0.120277 | 0.005486 | 0.138939 | 27208.083939 | 1.356839 | 3786.271122 | 5.238112 | 0.176909 | -183.671725 | 2.883552 | 1 | 1 | 1 | 1 | 1 |
| N21 | neighbor_combo | PESS | 21 | 60 | 15 | 12 | 3.000000 | HOLD_B | 188 | 4726.796339 | 2.523517 | 1505.289736 | MEASURABLE_BLOCK1 | 1.000000 | -4.204474 | 53.318948 | 0.041479 | 0.573725 | 0.120277 | 0.457060 | 0.138939 | 3408.658790 | 1.877275 | 2252.641992 | -10.014392 | 0.646242 | -747.352256 | 5.809918 | 1 | 1 | 1 | 1 | 1 |
| N21 | neighbor_combo | OPT | 21 | 60 | 15 | 12 | 3.000000 | DEV_COMMON | 1785 | 32581.755696 | 1.554185 | 3593.525797 | MEASURABLE | 1.075686 | 8.232687 | 28.889954 | 0.001000 | 0.045645 | 0.120277 | 0.006241 | 0.138939 | 27614.927639 | 1.377081 | 3779.686322 | 5.487054 | 0.177104 | -186.160525 | 2.745633 | 1 | 1 | 1 | 1 | 1 |
| N21 | neighbor_combo | OPT | 21 | 60 | 15 | 12 | 3.000000 | HOLD_B | 188 | 4744.868339 | 2.533539 | 1505.289736 | MEASURABLE_BLOCK1 | 1.000000 | -4.104752 | 53.408192 | 0.040980 | 0.577008 | 0.120277 | 0.460310 | 0.138939 | 3428.486590 | 1.888371 | 2238.457792 | -9.879823 | 0.645168 | -733.168056 | 5.775071 | 1 | 1 | 1 | 1 | 1 |
| N22 | neighbor_combo | PESS | 22 | 60 | 15 | 24 | 2.000000 | DEV_COMMON | 1113 | 34198.827627 | 1.549016 | 5178.881783 | MEASURABLE | 1.486469 | 8.609520 | 30.181931 | 0.000500 | 0.044891 | 0.120277 | 0.006135 | 0.138939 | 31621.626239 | 1.500683 | 3809.184253 | 7.533611 | 0.048333 | 1369.697530 | 1.075909 | 1 | 0 | 0 | 0 | 0 |
| N22 | neighbor_combo | PESS | 22 | 60 | 15 | 24 | 2.000000 | HOLD_B | 114 | 4038.815359 | 1.961493 | 2271.169054 | MEASURABLE | 1.952399 | -7.531578 | 51.513129 | 0.063468 | 0.401071 | 0.120277 | 0.302869 | 0.138939 | 3404.660838 | 1.687146 | 2482.014332 | -12.138344 | 0.274346 | -210.845279 | 4.606766 | 1 | 1 | 1 | 1 | 1 |
| N22 | neighbor_combo | OPT | 22 | 60 | 15 | 24 | 2.000000 | DEV_COMMON | 1113 | 34583.654927 | 1.566186 | 5175.868283 | MEASURABLE | 1.483228 | 8.889900 | 30.523214 | 0.000500 | 0.048643 | 0.120277 | 0.006829 | 0.138939 | 31985.906539 | 1.517678 | 3798.014653 | 7.737925 | 0.048507 | 1377.853630 | 1.151975 | 1 | 0 | 0 | 0 | 0 |
| N22 | neighbor_combo | OPT | 22 | 60 | 15 | 24 | 2.000000 | HOLD_B | 114 | 4056.724759 | 1.970092 | 2265.867954 | MEASURABLE | 1.954131 | -7.426098 | 51.755923 | 0.062969 | 0.403530 | 0.120277 | 0.305073 | 0.138939 | 3427.189838 | 1.698120 | 2471.435032 | -11.927514 | 0.271971 | -205.567079 | 4.501416 | 1 | 1 | 1 | 1 | 1 |
| N23 | neighbor_combo | PESS | 23 | 60 | 15 | 24 | 2.500000 | DEV_COMMON | 1082 | 35260.080055 | 1.596028 | 4457.393053 | MEASURABLE | 1.065528 | 9.199836 | 31.277223 | 0.001000 | 0.056108 | 0.120277 | 0.008306 | 0.138939 | 31621.626239 | 1.500683 | 3809.184253 | 7.533611 | 0.095345 | 648.208800 | 1.666225 | 1 | 0 | 0 | 0 | 0 |
| N23 | neighbor_combo | PESS | 23 | 60 | 15 | 24 | 2.500000 | HOLD_B | 112 | 4045.161530 | 1.973216 | 2202.468685 | MEASURABLE | 1.960306 | -7.721483 | 51.088333 | 0.058971 | 0.404463 | 0.120277 | 0.305950 | 0.138939 | 3404.660838 | 1.687146 | 2482.014332 | -12.138344 | 0.286070 | -279.545647 | 4.416861 | 1 | 1 | 1 | 1 | 1 |
| N23 | neighbor_combo | OPT | 23 | 60 | 15 | 24 | 2.500000 | DEV_COMMON | 1082 | 35646.008255 | 1.613237 | 4454.045053 | MEASURABLE | 1.063965 | 9.527354 | 31.330052 | 0.001000 | 0.060594 | 0.120277 | 0.009214 | 0.138939 | 31985.906539 | 1.517678 | 3798.014653 | 7.737925 | 0.095559 | 656.030400 | 1.789429 | 1 | 0 | 0 | 0 | 0 |
| N23 | neighbor_combo | OPT | 23 | 60 | 15 | 24 | 2.500000 | HOLD_B | 112 | 4066.300930 | 1.983407 | 2193.937585 | MEASURABLE | 1.960796 | -7.588704 | 51.186922 | 0.056972 | 0.407387 | 0.120277 | 0.308579 | 0.138939 | 3427.189838 | 1.698120 | 2471.435032 | -11.927514 | 0.285286 | -277.497447 | 4.338810 | 1 | 1 | 1 | 1 | 1 |
| N24 | neighbor_combo | PESS | 24 | 60 | 15 | 24 | 3.000000 | DEV_COMMON | 1053 | 37969.366627 | 1.740448 | 3699.106043 | MEASURABLE_BLOCK1 | 1.000000 | 10.617150 | 32.433276 | 0.000500 | 0.102472 | 0.120277 | 0.018838 | 0.138939 | 31621.626239 | 1.500683 | 3809.184253 | 7.533611 | 0.239765 | -110.078210 | 3.083539 | 1 | 1 | 1 | 1 | 1 |
| N24 | neighbor_combo | PESS | 24 | 60 | 15 | 24 | 3.000000 | HOLD_B | 109 | 4252.359035 | 2.083262 | 2227.066225 | MEASURABLE | 2.079516 | -4.424936 | 52.118418 | 0.051974 | 0.436391 | 0.120277 | 0.335005 | 0.138939 | 3404.660838 | 1.687146 | 2482.014332 | -12.138344 | 0.396115 | -254.948107 | 7.713408 | 1 | 1 | 1 | 1 | 1 |
| N24 | neighbor_combo | OPT | 24 | 60 | 15 | 24 | 3.000000 | DEV_COMMON | 1053 | 38352.444127 | 1.757683 | 3696.106043 | MEASURABLE_BLOCK1 | 1.000000 | 10.854412 | 32.652067 | 0.000500 | 0.109579 | 0.120277 | 0.020686 | 0.138939 | 31985.906539 | 1.517678 | 3798.014653 | 7.737925 | 0.240005 | -101.908610 | 3.116487 | 1 | 1 | 1 | 1 | 1 |
| N24 | neighbor_combo | OPT | 24 | 60 | 15 | 24 | 3.000000 | HOLD_B | 109 | 4273.498435 | 2.093495 | 2218.535125 | MEASURABLE | 2.080109 | -4.329421 | 52.226394 | 0.050975 | 0.439388 | 0.120277 | 0.337761 | 0.138939 | 3427.189838 | 1.698120 | 2471.435032 | -11.927514 | 0.395375 | -252.899907 | 7.598093 | 1 | 1 | 1 | 1 | 1 |
| N25 | neighbor_combo | PESS | 25 | 60 | 15 | 48 | 2.000000 | DEV_COMMON | 713 | 26219.464741 | 1.174432 | 5187.170063 | MEASURABLE | 2.095588 | 4.456789 | 25.813024 | 0.003998 | 0.005889 | 0.120277 | 0.000453 | 0.138939 | 29443.516762 | 1.317928 | 4447.005672 | 5.728525 | -0.143496 | 740.164391 | -1.271736 | 0 | 0 | 0 | 0 | 0 |
| N25 | neighbor_combo | PESS | 25 | 60 | 15 | 48 | 2.000000 | HOLD_B | 70 | 3000.217334 | 1.469003 | 2325.986888 | MEASURABLE | 1.751476 | -13.287541 | 45.307554 | 0.123938 | 0.273330 | 0.120277 | 0.194327 | 0.138939 | 2786.011355 | 1.310046 | 2702.186368 | -16.846151 | 0.158957 | -376.199480 | 3.558609 | 1 | 1 | 1 | 1 | 1 |
| N25 | neighbor_combo | OPT | 25 | 60 | 15 | 48 | 2.000000 | DEV_COMMON | 713 | 26419.627241 | 1.183296 | 5182.156563 | MEASURABLE | 2.091985 | 4.562792 | 25.874826 | 0.003998 | 0.006224 | 0.120277 | 0.000486 | 0.138939 | 29617.397362 | 1.325632 | 4437.846372 | 5.828970 | -0.142336 | 744.310191 | -1.266178 | 0 | 0 | 0 | 0 | 0 |
| N25 | neighbor_combo | OPT | 25 | 60 | 15 | 48 | 2.000000 | HOLD_B | 70 | 3010.454434 | 1.474021 | 2321.266688 | MEASURABLE | 1.751203 | -13.191402 | 45.379475 | 0.123438 | 0.274524 | 0.120277 | 0.195309 | 0.138939 | 2797.000455 | 1.315142 | 2697.169368 | -16.792246 | 0.158879 | -375.902680 | 3.600844 | 1 | 1 | 1 | 1 | 1 |
| N26 | neighbor_combo | PESS | 26 | 60 | 15 | 48 | 2.500000 | DEV_COMMON | 676 | 29811.514668 | 1.325232 | 4644.975273 | MEASURABLE_BLOCK1 | 1.000000 | 5.847213 | 28.172103 | 0.003498 | 0.014437 | 0.120277 | 0.001412 | 0.138939 | 29443.516762 | 1.317928 | 4447.005672 | 5.728525 | 0.007304 | 197.969600 | 0.118688 | 1 | 0 | 0 | 0 | 0 |

## k45_contrarian_robust_r2_17_20261002

- 테스트 재실행 `tests/test_k45_contrarian_robust_r2_17.py`: `5 passed in 11.42s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-17 |
| created_utc | 2026-10-02T09:30:45.863923+00:00 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| hypothesis_frozen | F3의 DEV 양수는 특정 파라미터 한 점이 아니라 넓은 영역에서 나타난다: F3 global_ls_account LS 칸의 70% 이상이 DEV·DEV_EX2020 모두 양수이고, 그 칸들의 HOLD_B 양수 비율이 50% 이상이다. |
| oos_result | {"cell_count": 360, "dev_and_dev_ex2020_positive_count": 359, "dev_and_dev_ex2020_positive_ratio": 0.9972222222222222, "qualified_hold_b_positive_count": 334, "qualified_hold_b_positive_ratio": 0.9303621169916435, "threshold_dev_and_dev_ex2020": 0.7, "threshold_hold_b": 0.5, "pass": true} |
| cell_count | 2682 |
| metric_row_count | 8046 |
| workers | 4 |
| model_training | False |
| live_orders | 0 |
| segments | {"DEV": ["2020-07-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"], "DEV_EX2020": ["2021-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"], "HOLD_B": ["2026-01-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00"]} |
| methods | {"funding": "R2-14 settlement_events: UTC 00/08/16, prior-minute rate", "execution": "R2-14 simulate: next minute open, one position", "pw_ci": "R2-14 circular moving-block bootstrap, 1000", "fixed_ci": "R2-14 circular 20-day block bootstrap, 1000", "random": "R2-14 random_baseline, 1000 circular shifts, same n/sides/durations/exposure"} |

- 출력 해시 확인: 12/12 일치

### REPORT.md 앞 150줄 (전체 4112줄, 원문)

# R2-17

## cells

2682

## reproduction

| reference_cell_id | cell_id | segment | n_reference | n_r217 | net_reference_bps | net_r217_bps | sharpe_reference | sharpe_r217 | max_abs_diff | match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | F3_global_ls_account\|1h\|w90\|q10\|h24\|LS | DEV | 873 | 873 | 35384.229653 | 35384.229653 | 1.485597 | 1.485597 | 0.000000 | 1 |
| F3\|1h\|10/24\|signal\|LS | F3_global_ls_account\|1h\|w90\|q10\|h24\|LS | HOLD_B | 76 | 76 | 1182.394594 | 1182.394594 | 0.682082 | 0.682082 | 0.000000 | 1 |
| F3\|1h\|5/24\|signal\|LS | F3_global_ls_account\|1h\|w90\|q5\|h24\|LS | DEV | 612 | 612 | 28370.304859 | 28370.304859 | 1.358640 | 1.358640 | 0.000000 | 1 |
| F3\|1h\|5/24\|signal\|LS | F3_global_ls_account\|1h\|w90\|q5\|h24\|LS | HOLD_B | 43 | 43 | 1036.993393 | 1036.993393 | 1.069112 | 1.069112 | 0.000000 | 1 |
| F1\|1h\|5/24\|signal\|LS | F1\|1h\|w90\|q5\|h24\|LS | DEV | 818 | 818 | 16024.495580 | 16024.495580 | 0.749494 | 0.749494 | 0.000000 | 1 |
| F1\|1h\|5/24\|signal\|LS | F1\|1h\|w90\|q5\|h24\|LS | HOLD_B | 48 | 48 | 928.108334 | 928.108334 | 0.762049 | 0.762049 | 0.000000 | 1 |
| A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | DEV | 339 | 339 | 31309.380610 | 31309.380610 | 0.800353 | 0.800353 | 0.000000 | 1 |
| A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | HOLD_B | 45 | 45 | 3055.937445 | 3055.937445 | 1.065194 | 1.065194 | 0.000000 | 1 |

## stability

| family | cell_count | dev_positive_ratio | dev_ex2020_positive_ratio | hold_b_positive_ratio | all_three_positive_count |
| --- | --- | --- | --- | --- | --- |
| F3_global_ls_account | 1080 | 0.975000 | 0.994444 | 0.767593 | 806 |
| F3_taker_ls_ratio | 1080 | 0.150926 | 0.125000 | 0.273148 | 10 |
| F1 | 360 | 0.847222 | 0.938889 | 0.605556 | 164 |
| A3 | 162 | 0.864198 | 0.790123 | 0.623457 | 76 |

## hypothesis

| cell_count | dev_and_dev_ex2020_positive_count | dev_and_dev_ex2020_positive_ratio | qualified_hold_b_positive_count | qualified_hold_b_positive_ratio | threshold_dev_and_dev_ex2020 | threshold_hold_b | pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 360 | 359 | 0.997222 | 334 | 0.930362 | 0.700000 | 0.500000 | 1 |

## axis_median

| family | axis | value | cell_count | dev_sharpe_median |
| --- | --- | --- | --- | --- |
| F3_global_ls_account | window_days | 30.0 | 270 | 1.112016 |
| F3_global_ls_account | window_days | 60.0 | 270 | 1.155524 |
| F3_global_ls_account | window_days | 90.0 | 270 | 1.076469 |
| F3_global_ls_account | window_days | 180.0 | 270 | 0.918071 |
| F3_global_ls_account | tail_pct | 2.5 | 216 | 1.133082 |
| F3_global_ls_account | tail_pct | 5.0 | 216 | 1.056003 |
| F3_global_ls_account | tail_pct | 10.0 | 216 | 1.125783 |
| F3_global_ls_account | tail_pct | 15.0 | 216 | 0.999153 |
| F3_global_ls_account | tail_pct | 20.0 | 216 | 0.960193 |
| F3_global_ls_account | hold | h12 | 180 | 1.185926 |
| F3_global_ls_account | hold | h24 | 180 | 1.202833 |
| F3_global_ls_account | hold | h4 | 180 | 0.984150 |
| F3_global_ls_account | hold | h48 | 180 | 1.022167 |
| F3_global_ls_account | hold | h8 | 180 | 1.253573 |
| F3_global_ls_account | hold | median48 | 180 | 0.788628 |
| F3_global_ls_account | tf | 15m | 360 | 1.039547 |
| F3_global_ls_account | tf | 1h | 360 | 1.094976 |
| F3_global_ls_account | tf | 4h | 360 | 1.051135 |
| F3_taker_ls_ratio | window_days | 30.0 | 270 | -0.658796 |
| F3_taker_ls_ratio | window_days | 60.0 | 270 | -0.552082 |
| F3_taker_ls_ratio | window_days | 90.0 | 270 | -0.575774 |
| F3_taker_ls_ratio | window_days | 180.0 | 270 | -0.732173 |
| F3_taker_ls_ratio | tail_pct | 2.5 | 216 | -0.470520 |
| F3_taker_ls_ratio | tail_pct | 5.0 | 216 | -0.427393 |
| F3_taker_ls_ratio | tail_pct | 10.0 | 216 | -0.717344 |
| F3_taker_ls_ratio | tail_pct | 15.0 | 216 | -0.692278 |
| F3_taker_ls_ratio | tail_pct | 20.0 | 216 | -0.806447 |
| F3_taker_ls_ratio | hold | h12 | 180 | -0.423203 |
| F3_taker_ls_ratio | hold | h24 | 180 | -0.338108 |
| F3_taker_ls_ratio | hold | h4 | 180 | -0.885369 |
| F3_taker_ls_ratio | hold | h48 | 180 | -0.227268 |
| F3_taker_ls_ratio | hold | h8 | 180 | -0.703141 |
| F3_taker_ls_ratio | hold | median48 | 180 | -1.358054 |
| F3_taker_ls_ratio | tf | 15m | 360 | -0.878627 |
| F3_taker_ls_ratio | tf | 1h | 360 | -0.685836 |
| F3_taker_ls_ratio | tf | 4h | 360 | -0.445026 |
| F1 | window_days | 30.0 | 90 | 0.692957 |
| F1 | window_days | 60.0 | 90 | 0.548028 |
| F1 | window_days | 90.0 | 90 | 0.486317 |
| F1 | window_days | 180.0 | 90 | 0.466167 |
| F1 | tail_pct | 2.5 | 72 | 0.678174 |
| F1 | tail_pct | 5.0 | 72 | 0.699885 |
| F1 | tail_pct | 10.0 | 72 | 0.481778 |
| F1 | tail_pct | 15.0 | 72 | 0.410941 |
| F1 | tail_pct | 20.0 | 72 | 0.400257 |
| F1 | hold_hours | 8.0 | 120 | 0.401868 |
| F1 | hold_hours | 24.0 | 120 | 0.538212 |
| F1 | hold_hours | 48.0 | 120 | 0.707824 |
| F1 | tf | 1h | 180 | 0.547782 |
| F1 | tf | 4h | 180 | 0.511841 |
| A3 | lookback_hours | 240.0 | 27 | 0.214924 |
| A3 | lookback_hours | 360.0 | 27 | 0.170074 |
| A3 | lookback_hours | 480.0 | 27 | 0.471394 |
| A3 | lookback_hours | 720.0 | 27 | 0.388360 |
| A3 | lookback_hours | 1080.0 | 27 | 0.358777 |
| A3 | lookback_hours | 1440.0 | 27 | 0.606134 |
| A3 | exit_mode | signal | 54 | 0.457280 |
| A3 | exit_mode | trail2 | 54 | 0.343452 |
| A3 | exit_mode | trail3 | 54 | 0.372103 |
| A3 | tf | 1d | 54 | 0.380424 |
| A3 | tf | 1h | 54 | 0.308133 |
| A3 | tf | 4h | 54 | 0.476605 |

## concentration_cells

| cell_id | family | daily_sharpe | top5 | reference_cell_id | original |
| --- | --- | --- | --- | --- | --- |
| A3\|4h\|1440\|trail2\|LS | A3 | 1.214375 | 1 | nan | 0 |
| A3\|4h\|1440\|trail3\|LS | A3 | 1.110367 | 1 | nan | 0 |
| A3\|1h\|1440\|trail3\|LS | A3 | 0.875146 | 1 | nan | 0 |
| A3\|4h\|480\|trail2\|LS | A3 | 0.832959 | 1 | nan | 0 |
| A3\|4h\|1440\|signal\|LS | A3 | 0.814415 | 1 | nan | 0 |
| A3\|4h\|720\|signal\|LS | A3 | 0.800353 | 0 | A3\|4h\|720\|signal\|LS | 1 |
| F1\|4h\|w30\|q5\|h24\|L | F1 | 1.387425 | 1 | nan | 0 |
| F1\|4h\|w30\|q10\|h24\|L | F1 | 1.322392 | 1 | nan | 0 |
| F1\|4h\|w30\|q15\|h48\|LS | F1 | 1.283136 | 1 | nan | 0 |
| F1\|4h\|w30\|q10\|h48\|L | F1 | 1.264350 | 1 | nan | 0 |
| F1\|1h\|w180\|q20\|h48\|L | F1 | 1.239538 | 1 | nan | 0 |
| F1\|1h\|w90\|q5\|h24\|LS | F1 | 0.749494 | 0 | F1\|1h\|5/24\|signal\|LS | 1 |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | F3_global_ls_account | 1.818554 | 1 | nan | 0 |
| F3_global_ls_account\|15m\|w180\|q2.5\|h8\|LS | F3_global_ls_account | 1.784644 | 1 | nan | 0 |
| F3_global_ls_account\|1h\|w30\|q5\|h8\|LS | F3_global_ls_account | 1.753650 | 1 | nan | 0 |
| F3_global_ls_account\|15m\|w60\|q10\|h8\|LS | F3_global_ls_account | 1.751769 | 1 | nan | 0 |
| F3_global_ls_account\|15m\|w90\|q10\|h8\|LS | F3_global_ls_account | 1.745062 | 1 | nan | 0 |
| F3_global_ls_account\|1h\|w90\|q10\|h24\|LS | F3_global_ls_account | 1.485597 | 0 | F3\|1h\|10/24\|signal\|LS | 1 |
| F3_global_ls_account\|1h\|w90\|q5\|h24\|LS | F3_global_ls_account | 1.358640 | 0 | F3\|1h\|5/24\|signal\|LS | 1 |
| F3_taker_ls_ratio\|1h\|w30\|q20\|h48\|L | F3_taker_ls_ratio | 0.906319 | 1 | nan | 0 |
| F3_taker_ls_ratio\|4h\|w60\|q20\|h48\|L | F3_taker_ls_ratio | 0.881146 | 1 | nan | 0 |
| F3_taker_ls_ratio\|15m\|w30\|q5\|h48\|L | F3_taker_ls_ratio | 0.866249 | 1 | nan | 0 |
| F3_taker_ls_ratio\|15m\|w30\|q10\|h24\|L | F3_taker_ls_ratio | 0.834709 | 1 | nan | 0 |
| F3_taker_ls_ratio\|15m\|w30\|q10\|h48\|L | F3_taker_ls_ratio | 0.825114 | 1 | nan | 0 |

## concentration

| cell_id | family | segment | n | net_total_bps | top10_day_net_bps | top10_day_share | event_count | event_net_mean_bps | trades_per_event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A3\|4h\|1440\|trail2\|LS | A3 | DEV | 187 | 22501.363289 | 20181.244310 | 0.896890 | 187 | 120.328146 | 1.000000 |
| A3\|4h\|1440\|trail2\|LS | A3 | DEV_EX2020 | 179 | 20082.559568 | 19397.778639 | 0.965902 | 179 | 112.193070 | 1.000000 |
| A3\|4h\|1440\|trail2\|LS | A3 | HOLD_B | 14 | -951.632959 | -951.632959 | 1.000000 | 14 | -67.973783 | 1.000000 |
| A3\|4h\|1440\|trail3\|LS | A3 | DEV | 187 | 23321.755654 | 23930.926474 | 1.026120 | 187 | 124.715271 | 1.000000 |
| A3\|4h\|1440\|trail3\|LS | A3 | DEV_EX2020 | 179 | 21041.395399 | 23219.894780 | 1.103534 | 179 | 117.549695 | 1.000000 |
| A3\|4h\|1440\|trail3\|LS | A3 | HOLD_B | 14 | -1336.067071 | -1336.067071 | 1.000000 | 14 | -95.433362 | 1.000000 |
| A3\|1h\|1440\|trail3\|LS | A3 | DEV | 331 | 9937.604952 | 11200.246236 | 1.127057 | 331 | 30.022976 | 1.000000 |
| A3\|1h\|1440\|trail3\|LS | A3 | DEV_EX2020 | 313 | 9562.235058 | 11181.699927 | 1.169360 | 313 | 30.550272 | 1.000000 |
| A3\|1h\|1440\|trail3\|LS | A3 | HOLD_B | 26 | -1147.241339 | -294.308043 | 0.256535 | 26 | -44.124667 | 1.000000 |
| A3\|4h\|480\|trail2\|LS | A3 | DEV | 492 | 19716.070701 | 24154.816807 | 1.225133 | 492 | 40.073314 | 1.000000 |
| A3\|4h\|480\|trail2\|LS | A3 | DEV_EX2020 | 459 | 11995.994047 | 20290.912414 | 1.691474 | 459 | 26.135063 | 1.000000 |
| A3\|4h\|480\|trail2\|LS | A3 | HOLD_B | 36 | -341.221157 | 2365.711139 | -6.933073 | 36 | -9.478365 | 1.000000 |
| A3\|4h\|1440\|signal\|LS | A3 | DEV | 187 | 31974.661764 | 39798.857609 | 1.244700 | 187 | 170.987496 | 1.000000 |
| A3\|4h\|1440\|signal\|LS | A3 | DEV_EX2020 | 179 | 19135.633132 | 27977.963975 | 1.462087 | 179 | 106.902978 | 1.000000 |
| A3\|4h\|1440\|signal\|LS | A3 | HOLD_B | 14 | 697.821107 | 697.821107 | 1.000000 | 14 | 49.844365 | 1.000000 |
| A3\|4h\|720\|signal\|LS | A3 | DEV | 339 | 31309.380610 | 40621.479338 | 1.297422 | 339 | 92.358055 | 1.000000 |

## k45_defect_audit_20260930

### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | K45 six-defect adversarial audit |
| audit_type | post_hoc_no_winner_selection |
| created_at_utc | 2026-09-30T14:57:57.994980+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| new_model_fits | 0 |
| new_orders | 0 |
| external_data_added | 0 |
| live_orders | 0 |

- 출력 해시: manifest에 outputs 해시 항목 없음.

### REPORT.md 앞 100줄 (전체 100줄, 원문)

# K=45 결함 공격 감사

감사 결과: 결함 1·2·3·6은 **CONFIRMED**, 결함 4는 **WRONG**, 결함 5는 **MISLEADING**이다. 이 감사는 사후 분석이다. 승자 선택이나 신규 판정이 아니다.

제약: `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, `live_orders: 0`. 데이터 cutoff는 2026-06-30 23:59 UTC다. 외부 데이터는 쓰지 않았다.

## 재현 경로

**올바르다.** `causal_candidates.parquet`에서 `arm == 'DOWN_BREAKOUT_LONG' & first_come_executed == True`를 적용하고, `1e4*(close[scheduled_exit_index]/close[entry_index]-1)-4`를 계산했다. `n=3,066`, 평균 `0.4550` bps, 합계 `1395.1` bps다. 저장된 `none_net_lin_bps`와 최대 차이는 `0.000e+00` bps다. 이 값은 frozen **linear close→close** endpoint 재현이다. maker 체결 재현은 아니다. 근거: `out/run_patchtst_k45_stop_grid_audit_fix.py:166-182`, `out/run_patchtst_k45_causal_admission_ordering.py:177-201`.

## 결함 1 — CONFIRMED

필터 D1: 위 재현 표본. 절사값은 D1에서 `none_net_lin_bps` 상·하위 k개를 직접 제거했다. 결과는 `trimmed_means.parquet`다.

- 중앙값 `5.9749`, 표준편차 `114.22`, 왜도 `-1.11`, 최솟값 `-1173.3`, 최댓값 `807.9` bps다.
- 상위 2건 제거 후 평균은 `-0.0171` bps다. 부호 반전이 맞다.
- iid bootstrap 20,000회, seed `20260930` 재현값은 95% CI `[-3.566, 4.409]`, `P(mean<=0)=0.407`다.
- iid는 최종 추론으로 부적절하다. 단일 book은 거래 겹침을 없애지만 시장 regime, fold gate, 시간 군집 의존은 남는다. 일별 influence stationary bootstrap의 원 평균 net CI는 `[-3.045, 4.163]`, one-sided p=`0.402`다. 결론은 같다.
- 양수 거래 비율은 `54.01%`, 양수 평균 `69.97`, 비양수 평균 `-81.18` bps다. “조금 자주 벌고 왼쪽 꼬리에서 더 크게 잃는다”가 더 정확하다. 단순한 고승률 전략은 아니다.

상위 2건은 같은 사건이 아니다. `top_trades.parquet`의 정확한 두 행:

- 2021-05-19 14:36 UTC 진입, net `807.931` bps. 그 UTC 일봉은 고가 `43615.93`, 저가 `28688.00`, 일중 범위 `3481.1` bps였다.
- 2021-02-23 12:34 UTC 진입, net `639.559` bps. 일중 범위 `1730.5` bps였다.

85일 떨어진 별도 급락·반등 구간이다. 로컬 OHLC만으로 사건 원인은 말할 수 없다. `LONG_ONLY +0.4550`을 강건한 “실행 가능한 최선”이라 부를 근거는 없다. 철회가 맞다.

## 결함 2 — CONFIRMED

사용자 기준선의 숨은 정확한 필터를 복원했다: `i = arange(min(causal.entry_index), max(causal.entry_index)-45)`. 이때 `n=2,879,368`, net `-3.7834` bps다. 같은 구간에서 `UTC minute % 15 == 0`이면 `n=191,957`, net `-3.7834` bps다. 둘은 4자리 반올림에서 같다. 전체 실제 fold TEST 구간과 `entry+45<test_end`를 쓰면 `n=2,848,545`, net `-3.7728` bps다. 사용자 기준선의 결론은 유지된다.

분해 필터:

- A: 사용자 전 분 기준선. gross `0.2166` bps.
- B: 세 prediction parquet을 합치고 `passes_q90 & signal_index+45<test_end`; signal close long; first-come 45m book. `n=12,217`, gross `0.9406` bps.
- C: D1 전략. gross `4.4550` bps.

따라서 gate 기여 B−A는 `0.7240` bps, trigger·방향·진입시점 기여 C−B는 `3.5145` bps, 합계는 `4.2385` bps다. gate 통과 후 15분 안에 절대 50 bps trigger가 전혀 없었던 stricter book은 `n=9,954`, gross `0.9946` bps다.

시간분포를 맞춰야 한다. 다만 맞추면 우위가 사라지지 않는다. `matched_baselines.parquet`에서 year×weekday×hour 기준 full 우위는 `4.8797` bps, top2 제거 후 `4.4127` bps다. year-month×weekday×hour에서도 각각 `9.3871`, `8.9664` bps다.

상위 2건 제거 후 사용자 random-long 대비 gross 우위는 `3.7663` bps다. 일별 PW stationary bootstrap은 95% CI `[0.240, 7.501]`, one-sided p=`0.0180`다. 고정 7·14·30·60·90·180일 block에서도 하한은 모두 양수다. equal-month 차이는 `4.5730` bps, CI `[1.262, 7.884]`, 양수 월 `42/66`다. stricter no-trigger book 대비 top2 제거 우위는 `2.9883` bps, PW CI `[-0.691, 6.760]`, p=`0.0576`다.

해석: 결함 1과 2는 같은 사실이 아니다. 상위 2건은 전체 gross excess에서 `0.4721` bps만 설명한다. 그러나 top2 제거 전략 net은 `-0.0171` bps다. gross signal excess가 통계적으로 양수여도 4 bps 비용을 넘지 못한다.

## 결함 3 — CONFIRMED

`first_crossing()`은 `close[t+tau]`를 본다(`out/run_patchtst_fixed_trigger_hold_sweep.py:137-153`). frozen entry도 같은 close다(`out/run_patchtst_k45_stop_grid_audit_fix.py:166-181`). 시점 위반이 맞다.

- close→close `0.4550` bps.
- 다음 open→다음 open `0.4587` bps. paired 차이 `0.0037`, SD `0.94`, t=`0.22`다.
- 진입만 다음 open, 기존 exit close는 `0.4585` bps. 차이 `0.0035`, t=`0.29`다.

고정 45분 latency 비교에는 양쪽 이동이 주 비교다. 원래 청산 시각을 고정하는 44분 노출 진단에는 진입만 이동이 맞다. 둘 다 수익 결론은 바꾸지 않는다.

maker-only 시점에는 다음 open 체결도 아니다. trigger close 뒤 그 가격에 resting limit를 내고 후속 bar가 touch해야 한다. `--maker-fill-window` 계약은 `btcusdt_quant/cli.py:1839`다. 5-bar local OHLC touch는 `3,041/3,066` (`99.18%`), 미touch `25`건이다. frozen ledger는 전부 trigger close 즉시 체결한다. 성과 차이는 작아 보여도 체결 시점 계약은 불일치한다. pending order가 book 점유를 바꾸므로 정확한 maker book PnL은 이 감사에서 새 backtest로 만들지 않았다.

## 결함 4 — WRONG

calendar 문자열만 보면 경계 간격은 0이다(`out/run_short_patchtst_3day_cadence_pilot.py:35-50`). 그러나 실제 학습 runner는 각 phase에서 `last=t+15`의 마지막 bar close가 phase end 이하일 때만 origin을 남긴다(`out/run_patchtst_excursion_range.py:205-216`; backward `out/run_patchtst_backward_k45_validation.py:70-82`; confirmation `out/run_patchtst_down_breakout_long_confirmation.py:89-100`). 라벨 정의는 `t+1..t+15`다(`out/run_patchtst_excursion_range.py:101-119`).

15분 grid에서 phase 끝 15분 전 raw origin 1개가 매 fold·phase마다 경계를 넘지만 이미 제거된다. 실제 admitted crossing은 TRAIN/STOP `0`건, STOP/TEST `0`건이다. 제거할 admitted origin이 없으므로 Spearman 변화와 q90 threshold 변화는 정확히 0이다. `boundary_audit.parquet`, `boundary_quality.parquet`에 fold별 근거가 있다.

명시적 post-boundary embargo는 0이다. 하지만 이 walk-forward에서 label overlap purge는 이미 작동한다. 추가 serial-correlation embargo의 재학습 효과는 zero-fit 제약 아래 측정 불가이며, 현재 수치에서 누수 결함으로 부를 근거는 없다.

## 결함 5 — MISLEADING

fold 606..666은 다른 runner다. 그러나 calendar 공식은 같은 3일 continuation이다(`out/run_patchtst_down_breakout_long_confirmation.py:74-86`). 차이는 edge 두 개다: fold 606은 시작 clip으로 TEST 2일과 1일 gap, fold 666은 종료 clip으로 TEST 2일이다. folds 607..665는 기존과 같은 180d/3d/3d다. `calendar_geometry.parquet`에 정확한 기하가 있다.

source 분리 LONG_ONLY net 평균은 다음과 같다. 정확한 필터는 D1에 `pilot_fold` 범위를 추가했다.

- 0..405: `n=2,021`, `-1.0247` bps.
- 406..605: `n=789`, `2.1407` bps.
- 606..666: `n=256`, `6.9416` bps.

따라서 source heterogeneity는 크다. 한 pooled 평균은 안정된 공통 효과로 읽으면 안 된다. 다만 chronology 전체의 거래가중 estimand로 합치는 것 자체가 통계 오류는 아니다.

F-1 45m coefficient를 같은 controls·month FE·PW로 source 분리하면:

- 0..405: beta `6.3524`, p=`0.128`.
- 406..605: beta `-2.4411`, p=`0.656`.
- 606..666: beta `8.4701`, p=`0.171`.

어느 source도 유의하지 않고 중간 source는 부호가 반대다. 기존 `FLOW_REGRESSION_GATE_FAILED`는 바뀌지 않는다.

## 결함 6 — CONFIRMED

필터 D6: `causal_candidates.parquet.groupby('pilot_fold').size()`의 nonempty folds. `n=592`, 평균 `15.3936`, 중앙값 `8`, 최대 `203`(fold 15)다. Kish 유효 fold 수는 `191.5`다. 상위 1% folds가 후보 `10.05%`, 상위 10%가 `44.27%`를 가진다.

HAC가 틀린 것은 아니다. `hac_mean()`은 fold별 score 합을 만들어 거래가중 평균의 SE를 계산한다(`out/run_patchtst_k45_stop_grid_audit_fix.py:413-450`). 하지만 fold 밀도 편중을 제거하지는 않는다.

- all-candidate 평균은 거래가중 `-0.9963` bps, nonempty-fold 동일가중 `1.0757` bps로 부호가 바뀐다.
- executed long은 `0.4550` 대 `2.8462` bps다.
- F-1 beta는 거래가중 `4.5155`에서 fold 동일가중 `1.3188` bps로 줄어든다.

월 block은 일부만 해결한다. 월 안 최대 fold share 중앙값은 `32.18%`, 최대는 `74.47%` (2022-11)다. fold 동일가중 시 66개월 중 `18`개월 coefficient 부호가 바뀐다. 양수 월 수는 `31`→`31`로 같아 최종 F-1 실패는 유지된다. E의 월 block은 calendar dependence를 다루지만 월내 fold 편중까지 없애지는 않는다.

## 최종 한 줄

**예, 명목상 남는다: top2 제거 후 random-long 대비 gross +3.7663 bps, 일별 stationary-bootstrap 95% CI [0.240, 7.501], one-sided p=0.0180. 다만 사후 감사라 확증 결과는 아니며, net은 -0.0171 bps다.**

## k45_funding_fix_20261004

- 테스트 재실행 `tests/test_k45_funding.py`: `7 passed in 0.60s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-22 |
| created_utc | 2026-10-04T05:23:10.872155+00:00 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| downloads | 0 |
| live_orders | 0 |
| hold_a_read | 0 |
| workers_max | 12 |
| stage_durations_seconds | {"early_reprice": 5.17298260005191, "r2_14_OPT": 1406.500125, "r2_14_PESS": 1411.481917, "r2_15_audit": 48.808, "r2_15_full": 4456.30127, "r2_15_no_next": 4435.10992, "r2_15_OPT_full": 4455.221061, "r2_15_OPT_no_next": 4387.08586, "r2_17_OPT": 2236.228007, "r2_17_PESS": 2233.431854, "r2_18_OPT": 330.5120926001109, "r2_18_PESS": 330.80567610030994, "r2_19_OPT": 96.14471719972789, "r2_19_PESS": 96.14511199994013, "r2_20_21_verify": 7.909154500346631} |
| tests | {"test_files": 7, "last_line": "53 passed, 5 warnings in 18.61s", "returncode": 0} |

- 출력 해시 확인: 205/205 일치

### REPORT.md 앞 150줄 (전체 216줄, 원문)

# R2-22

## (a) module_tests

| test_files | last_line | returncode |
| --- | --- | --- |
| 7 | 53 passed, 5 warnings in 18.61s | 0 |

## funding_module

| settlement_rows | max_normalization_error_seconds | rate_2021_01_08_00 | rate_2021_01_08_08 |
| --- | --- | --- | --- |
| 7119 | 0.04700000 | 0.00213517 | 0.00092044 |

## definition_changes

| item | before | after | rows | max_abs_difference |
| --- | --- | --- | --- | --- |
| settlement_rate_offset_hours | -8 | 0 | 7119 | nan |
| r2_15_g2_funding_feature | next_funding_rate | funding_rate | 3417120 | 0.00000000 |

## (b) experiment_summary

| experiment | boundary | cell_count | row_count | old_net_min_bps | old_net_median_bps | old_net_max_bps | new_net_min_bps | new_net_median_bps | new_net_max_bps | delta_min_bps | delta_q05_bps | delta_q25_bps | delta_median_bps | delta_q75_bps | delta_q95_bps | delta_max_bps | sign_changed_n | sign_changed_row_n | sign_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-14 | PESS | 813 | 1626 | -68699.16562346 | -140.39001034 | 35384.22965313 | -69251.56922493 | -193.19146456 | 34886.26894251 | -2368.11100120 | -720.42772303 | -167.98003580 | -10.91465414 | -1.56942509 | 4.23949229 | 488.27450190 | 15 | 15 | A3\|1d\|168\|trail2\|LS;A3\|1d\|24\|signal\|L;A3\|1h\|168\|trail2\|L;A4\|1h\|10/2\|trail2\|LS;A4\|1h\|10/3\|trail2\|LS;A4\|1h\|10/4\|trail2\|LS;A4\|1h\|10/4\|trail3\|L;A5\|1h\|25\|signal\|LS;A5\|1h\|25\|trail2\|LS;C4\|4h\|engulf/trend4h\|signal\|S;D2\|1d\|NR7\|signal\|S;F1\|1h\|10/24\|signal\|LS;G1\|1m\|us/30\|signal\|LS;G3\|1d\|weekday\|signal\|L;G3\|1d\|weekday\|signal\|LS |
| R2-14 | OPT | 813 | 1626 | -68699.16562346 | -140.39001034 | 35384.22965313 | -68086.28292493 | -119.32488954 | 35725.98504251 | -703.91118656 | -126.81025916 | 0.00000000 | 5.61025004 | 56.17531320 | 624.77059720 | 2249.73551279 | 6 | 6 | B2\|15m\|30/70/12\|signal\|L;F1\|1h\|10/24\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|S;F2\|4h\|--/fade/4\|signal\|L;F2\|4h\|--/fade/4\|signal\|LS |
| R2-17 | PESS | 2682 | 8046 | -207724.77051324 | 1405.30101402 | 45977.44555885 | -209710.37231324 | 1330.94648884 | 45428.31955706 | -5050.61071080 | -1168.99572181 | -431.51383113 | -142.29205152 | -16.85449997 | -0.66042501 | 27.99756237 | 42 | 42 | A3\|1h\|1080\|trail2\|LS;A3\|1h\|360\|trail2\|S;A3\|1h\|360\|trail3\|L;A3\|1h\|480\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F1\|4h\|w90\|q15\|h8\|L;F3_global_ls_account\|15m\|w180\|q10\|median48\|LS;F3_global_ls_account\|15m\|w180\|q15\|median48\|LS;F3_global_ls_account\|15m\|w60\|q15\|h8\|L;F3_global_ls_account\|1h\|w180\|q15\|h4\|LS;F3_global_ls_account\|4h\|w180\|q15\|h4\|S;F3_global_ls_account\|4h\|w180\|q15\|h8\|L;F3_global_ls_account\|4h\|w180\|q15\|h8\|S;F3_global_ls_account\|4h\|w180\|q2.5\|h4\|LS;F3_global_ls_account\|4h\|w180\|q20\|h4\|LS;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h8\|L;F3_global_ls_account\|4h\|w90\|q5\|h4\|S;F3_taker_ls_ratio\|15m\|w30\|q5\|h48\|LS;F3_taker_ls_ratio\|1h\|w180\|q2.5\|h4\|LS;F3_taker_ls_ratio\|1h\|w180\|q5\|h12\|LS;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|1h\|w60\|q20\|h12\|L;F3_taker_ls_ratio\|1h\|w90\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h48\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|median48\|S;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|S;F3_taker_ls_ratio\|4h\|w30\|q5\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q5\|h12\|S;F3_taker_ls_ratio\|4h\|w60\|q5\|h4\|S;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h12\|L;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w90\|q5\|h4\|S |
| R2-17 | OPT | 2682 | 8046 | -207724.77051324 | 1405.30101402 | 45977.44555885 | -205690.88341324 | 1426.18824740 | 46255.11465041 | -1024.18489606 | -268.17237675 | 0.53576347 | 29.22665509 | 316.18731219 | 1222.10485091 | 4767.10878920 | 33 | 34 | A3\|1d\|480\|signal\|S;A3\|1h\|360\|trail3\|L;A3\|4h\|240\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F3_global_ls_account\|15m\|w30\|q15\|median48\|L;F3_global_ls_account\|15m\|w60\|q15\|median48\|L;F3_global_ls_account\|15m\|w90\|q10\|median48\|L;F3_global_ls_account\|1h\|w180\|q20\|h4\|S;F3_global_ls_account\|1h\|w180\|q20\|h8\|S;F3_global_ls_account\|4h\|w30\|q15\|h24\|L;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h24\|L;F3_global_ls_account\|4h\|w60\|q5\|h4\|L;F3_taker_ls_ratio\|15m\|w180\|q15\|h24\|L;F3_taker_ls_ratio\|15m\|w30\|q5\|h24\|LS;F3_taker_ls_ratio\|1h\|w180\|q15\|h48\|L;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w60\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h12\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|h24\|S;F3_taker_ls_ratio\|4h\|w30\|q2.5\|h48\|LS;F3_taker_ls_ratio\|4h\|w30\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w60\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w90\|q10\|h48\|LS;F3_taker_ls_ratio\|4h\|w90\|q2.5\|median48\|S;F3_taker_ls_ratio\|4h\|w90\|q5\|median48\|S |
| R2-18 | PESS | 48 | 960 | -16068.05844630 | 166.00739408 | 27082.24716574 | -16412.55629662 | 134.80101429 | 25870.26505871 | -1211.98210702 | -599.94734062 | -174.94169995 | -30.85734700 | -1.60019997 | 2.04300499 | 52.87729978 | 4 | 6 | R-F3\|tail=5\|direction=LS;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-18 | OPT | 48 | 960 | -16068.05844630 | 166.00739408 | 27082.24716574 | -16390.22679662 | 170.60089632 | 28117.91295871 | -663.62525063 | -322.23291532 | -35.42604997 | 1.49589915 | 35.46069939 | 575.94680837 | 1229.66889743 | 5 | 6 | R-E1\|z=2\|direction=LS;R-F4\|tail=5\|direction=L;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-19 | PESS | 6 | 18 | 1038.65349264 | 11223.60277858 | 35293.52228478 | 1035.80459264 | 11166.54862858 | 34883.27988478 | -410.24240000 | -283.36477000 | -184.56552500 | -59.99985000 | -9.46122500 | -1.89592000 | -1.19790000 | 0 | 0 |  |
| R2-19 | OPT | 6 | 18 | 1038.65349264 | 11223.60277858 | 35293.52228478 | 1039.76309264 | 11264.62197858 | 35723.99598478 | 0.56610000 | 0.56610000 | 8.05800000 | 48.13505000 | 170.71840000 | 299.63643000 | 430.47370000 | 0 | 0 |  |

## r2_14_INCL

| rows | cells | funding_min_bps | funding_median_bps | funding_max_bps | event_count_sum |
| --- | --- | --- | --- | --- | --- |
| 1626 | 813 | -6774.69420000 | 0.00000000 | 7061.99980000 | 2000613 |

## sign_changes

| experiment | boundary | sign_changed_n | sign_changed_cells |
| --- | --- | --- | --- |
| R2-14 | PESS | 15 | A3\|1d\|168\|trail2\|LS;A3\|1d\|24\|signal\|L;A3\|1h\|168\|trail2\|L;A4\|1h\|10/2\|trail2\|LS;A4\|1h\|10/3\|trail2\|LS;A4\|1h\|10/4\|trail2\|LS;A4\|1h\|10/4\|trail3\|L;A5\|1h\|25\|signal\|LS;A5\|1h\|25\|trail2\|LS;C4\|4h\|engulf/trend4h\|signal\|S;D2\|1d\|NR7\|signal\|S;F1\|1h\|10/24\|signal\|LS;G1\|1m\|us/30\|signal\|LS;G3\|1d\|weekday\|signal\|L;G3\|1d\|weekday\|signal\|LS |
| R2-14 | OPT | 6 | B2\|15m\|30/70/12\|signal\|L;F1\|1h\|10/24\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|S;F2\|4h\|--/fade/4\|signal\|L;F2\|4h\|--/fade/4\|signal\|LS |
| R2-17 | PESS | 42 | A3\|1h\|1080\|trail2\|LS;A3\|1h\|360\|trail2\|S;A3\|1h\|360\|trail3\|L;A3\|1h\|480\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F1\|4h\|w90\|q15\|h8\|L;F3_global_ls_account\|15m\|w180\|q10\|median48\|LS;F3_global_ls_account\|15m\|w180\|q15\|median48\|LS;F3_global_ls_account\|15m\|w60\|q15\|h8\|L;F3_global_ls_account\|1h\|w180\|q15\|h4\|LS;F3_global_ls_account\|4h\|w180\|q15\|h4\|S;F3_global_ls_account\|4h\|w180\|q15\|h8\|L;F3_global_ls_account\|4h\|w180\|q15\|h8\|S;F3_global_ls_account\|4h\|w180\|q2.5\|h4\|LS;F3_global_ls_account\|4h\|w180\|q20\|h4\|LS;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h8\|L;F3_global_ls_account\|4h\|w90\|q5\|h4\|S;F3_taker_ls_ratio\|15m\|w30\|q5\|h48\|LS;F3_taker_ls_ratio\|1h\|w180\|q2.5\|h4\|LS;F3_taker_ls_ratio\|1h\|w180\|q5\|h12\|LS;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|1h\|w60\|q20\|h12\|L;F3_taker_ls_ratio\|1h\|w90\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h48\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|median48\|S;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|S;F3_taker_ls_ratio\|4h\|w30\|q5\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q5\|h12\|S;F3_taker_ls_ratio\|4h\|w60\|q5\|h4\|S;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h12\|L;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w90\|q5\|h4\|S |
| R2-17 | OPT | 33 | A3\|1d\|480\|signal\|S;A3\|1h\|360\|trail3\|L;A3\|4h\|240\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F3_global_ls_account\|15m\|w30\|q15\|median48\|L;F3_global_ls_account\|15m\|w60\|q15\|median48\|L;F3_global_ls_account\|15m\|w90\|q10\|median48\|L;F3_global_ls_account\|1h\|w180\|q20\|h4\|S;F3_global_ls_account\|1h\|w180\|q20\|h8\|S;F3_global_ls_account\|4h\|w30\|q15\|h24\|L;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h24\|L;F3_global_ls_account\|4h\|w60\|q5\|h4\|L;F3_taker_ls_ratio\|15m\|w180\|q15\|h24\|L;F3_taker_ls_ratio\|15m\|w30\|q5\|h24\|LS;F3_taker_ls_ratio\|1h\|w180\|q15\|h48\|L;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w60\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h12\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|h24\|S;F3_taker_ls_ratio\|4h\|w30\|q2.5\|h48\|LS;F3_taker_ls_ratio\|4h\|w30\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w60\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w90\|q10\|h48\|LS;F3_taker_ls_ratio\|4h\|w90\|q2.5\|median48\|S;F3_taker_ls_ratio\|4h\|w90\|q5\|median48\|S |
| R2-18 | PESS | 4 | R-F3\|tail=5\|direction=LS;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-18 | OPT | 5 | R-E1\|z=2\|direction=LS;R-F4\|tail=5\|direction=L;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-19 | PESS | 0 |  |
| R2-19 | OPT | 0 |  |

## selection_changes

| experiment | selection | old | pess | opt | old_pess_changed | old_opt_changed | boundary_equal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R2-14 | A1 | A1\|4h\|50/200\|trail2\|L | A1\|4h\|50/200\|trail2\|L | A1\|4h\|50/200\|trail2\|L | 0 | 0 | 1 |
| R2-14 | A2 | A2\|4h\|55/10\|signal\|L | A2\|4h\|55/10\|signal\|L | A2\|4h\|55/10\|signal\|L | 0 | 0 | 1 |
| R2-14 | A3 | A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | 0 | 0 | 1 |
| R2-14 | A4 | A4\|4h\|10/3\|signal\|L | A4\|4h\|10/3\|signal\|L | A4\|4h\|10/3\|signal\|L | 0 | 0 | 1 |
| R2-14 | A5 | A5\|4h\|25\|trail2\|L | A5\|4h\|25\|trail2\|L | A5\|4h\|25\|trail2\|L | 0 | 0 | 1 |
| R2-14 | A6 | A6\|1h\|40/60\|signal\|L | A6\|1h\|40/60\|signal\|L | A6\|1h\|40/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | B1 | B1\|15m\|2.5/12\|signal\|L | B1\|15m\|2.5/12\|signal\|L | B1\|15m\|2.5/12\|signal\|L | 0 | 0 | 1 |
| R2-14 | B2 | B2\|1h\|20/80/4\|signal\|L | B2\|1h\|20/80/4\|signal\|L | B2\|1h\|20/80/4\|signal\|L | 0 | 0 | 1 |
| R2-14 | B3 | B3\|1h\|3\|signal\|L | B3\|1h\|3\|signal\|L | B3\|1h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | B4 | B4\|1h\|20/5\|signal\|L | B4\|1h\|20/5\|signal\|L | B4\|1h\|20/5\|signal\|L | 0 | 0 | 1 |
| R2-14 | C1 | C1\|1h\|20/12\|limit\|L | C1\|1h\|20/12\|limit\|L | C1\|1h\|20/12\|limit\|L | 0 | 0 | 1 |
| R2-14 | C2 | C2\|4h\|20\|signal\|L | C2\|4h\|20\|signal\|L | C2\|4h\|20\|signal\|L | 0 | 0 | 1 |
| R2-14 | C3 | C3\|4h\|inside\|signal\|L | C3\|4h\|inside\|signal\|L | C3\|4h\|inside\|signal\|L | 0 | 0 | 1 |
| R2-14 | C4 | C4\|4h\|pin/trend4h\|signal\|S | C4\|4h\|pin/trend4h\|signal\|S | C4\|4h\|pin/trend4h\|signal\|S | 0 | 0 | 1 |
| R2-14 | C5 | C5\|4h\|3\|signal\|L | C5\|4h\|3\|signal\|L | C5\|4h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | D1 | D1\|1h\|20\|signal\|L | D1\|4h\|20\|signal\|S | D1\|1h\|20\|signal\|L | 1 | 0 | 0 |
| R2-14 | D2 | D2\|4h\|NR4\|signal\|L | D2\|4h\|NR4\|signal\|L | D2\|4h\|NR4\|signal\|L | 0 | 0 | 1 |
| R2-14 | E1 | E1\|1h\|3\|signal\|L | E1\|1h\|3\|signal\|L | E1\|1h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | E2 | E2\|1h\|4h/follow/5\|signal\|L | E2\|1h\|4h/follow/5\|signal\|L | E2\|1h\|4h/follow/5\|signal\|L | 0 | 0 | 1 |
| R2-14 | E3 | E3\|1h\|revert\|signal\|L | E3\|1h\|revert\|signal\|L | E3\|1h\|revert\|signal\|L | 0 | 0 | 1 |
| R2-14 | F1 | F1\|1h\|5/24\|signal\|LS | F1\|1h\|5/24\|signal\|LS | F1\|1h\|5/24\|signal\|LS | 0 | 0 | 1 |
| R2-14 | F2 | F2\|4h\|--/fade/24\|signal\|L | F2\|4h\|--/fade/24\|signal\|L | F2\|4h\|--/fade/24\|signal\|L | 0 | 0 | 1 |
| R2-14 | F3 | F3\|1h\|10/24\|signal\|LS | F3\|1h\|10/24\|signal\|LS | F3\|1h\|10/24\|signal\|LS | 0 | 0 | 1 |
| R2-14 | F4 | F4\|1h\|5/4\|signal\|L | F4\|1h\|5/4\|signal\|L | F4\|1h\|5/4\|signal\|L | 0 | 0 | 1 |
| R2-14 | G1 | G1\|1m\|us/60\|signal\|L | G1\|1m\|us/60\|signal\|L | G1\|1m\|us/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | G2 | G2\|1m\|before/60/60\|signal\|L | G2\|1m\|before/60/60\|signal\|L | G2\|1m\|before/60/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | G3 | G3\|1d\|1\|signal\|L | G3\|1d\|1\|signal\|L | G3\|1d\|1\|signal\|L | 0 | 0 | 1 |
| R2-14 | H1 | H1\|4h\|55/20/squeeze10\|signal\|L | H1\|4h\|55/20/squeeze10\|signal\|L | H1\|4h\|55/20/squeeze10\|signal\|L | 0 | 0 | 1 |
| R2-14 | H2 | H2\|1h\|40/60/funding5\|signal\|L | H2\|1h\|40/60/funding5\|signal\|L | H2\|1h\|40/60/funding5\|signal\|L | 0 | 0 | 1 |
| R2-14 | H3 | H3\|1h\|4h20/60/C2\|signal\|S | H3\|1h\|4h20/60/C2\|signal\|S | H3\|1h\|4h20/60/C2\|signal\|S | 0 | 0 | 1 |
| R2-15 | T | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | 0 | 0 | 1 |
| R2-15 | G | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/4\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/4\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/12\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | 0 | 1 | 0 |
| R2-18 | long | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | 0 | 0 | 1 |
| R2-18 | short | R-F3\|tail=10\|direction=S | R-F3\|tail=10\|direction=S | R-F3\|tail=10\|direction=S | 0 | 0 | 1 |
| R2-19 | frozen_candidates | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | 0 | 0 | 1 |

## hypothesis

| experiment | variant | PESS | OPT | status |
| --- | --- | --- | --- | --- |
| R2-14 | primary | 0 | 0 | 확정 |
| R2-17 | primary | 1 | 1 | 확정 |
| R2-18 | primary | 0 | 1 | 경계 의존 |
| R2-19 | primary | 0 | 0 | 확정 |
| R2-15 | full_primary | 1 | 1 | 확정 |
| R2-15 | full_trend | 0 | 0 | 확정 |
| R2-15 | no_next_primary | 1 | 1 | 확정 |
| R2-15 | no_next_trend | 0 | 1 | 경계 의존 |

## (c) r2_15_full_no_next

| rows | full_feature_count | no_next_feature_count | net_difference_min_bps | net_difference_median_bps | net_difference_max_bps | sharpe_difference_min | sharpe_difference_median | sharpe_difference_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240 | 216 | 215 | -8666.20920937 | 0.00000000 | 6207.13775074 | -3.12903310 | 0.00000000 | 2.73373923 |

## r2_15_variants

| boundary | variant | feature_count | hypothesis_pass | trend_hypothesis_pass | passing_cells |
| --- | --- | --- | --- | --- | --- |
| PESS | full | 216 | 1 | 0 | 12 |
| OPT | full | 216 | 1 | 0 | 11 |
| PESS | no_next | 215 | 1 | 0 | 13 |
| OPT | no_next | 215 | 1 | 1 | 12 |

## r2_15_target_label_audit

| pess_targets | opt_targets | target_sets_equal | pess_candidates | opt_candidates | candidate_sets_equal | label_changed_n | labels_equal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 20 | 0 | 25729 | 24422 | 0 | 24 | 0 |

## (d) early_reprice

| experiment | table | cells | trade_instances | crossing_instances | crossing_rate_weighted | signed_difference_mean_bps_weighted | absolute_difference_mean_bps_weighted | sign_changed_cells | rank_changed_cells | boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | 8 | 30358 | 3234 | 0.10652876 | -0.07611311 | 0.12392715 | 1 | 0 | PESS |
| gate_direction_r2 | r21_arm | 12 | 40285 | 3866 | 0.09596624 | -0.08655660 | 0.11701346 | 0 | 2 | PESS |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1773 | 0.10506044 | -0.05487579 | 0.11852717 | 0 | 0 | PESS |
| gate_direction_r2 | r22_books | 18 | 76219 | 8396 | 0.11015626 | -0.08936598 | 0.13981746 | 2 | 0 | PESS |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 4053 | 0.10917466 | -0.09551233 | 0.13835139 | 0 | 0 | PESS |
| gate_direction_r2 | r24_tail | 160 | 84696 | 7774 | 0.09178710 | -0.04446242 | 0.13268834 | 1 | 0 | PESS |
| trend_side | 30d | 4 | 3036 | 280 | 0.09222661 | -0.09121943 | 0.14839572 | 0 | 0 | PESS |
| trend_side | 7d_report_only | 4 | 3047 | 287 | 0.09419101 | -0.06214506 | 0.14507653 | 0 | 0 | PESS |
| trend_side_tp | tp_grid | 9 | 16764 | 1210 | 0.07217848 | -0.06643505 | 0.11253856 | 0 | 9 | PESS |
| gate_direction_1 | backtest | 8 | 30358 | 2622 | 0.08636933 | 0.00722946 | 0.09034534 | 0 | 0 | OPT |
| gate_direction_r2 | r21_arm | 12 | 40285 | 2916 | 0.07238426 | -0.00028115 | 0.08658399 | 0 | 2 | OPT |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1563 | 0.09261673 | 0.02585233 | 0.10271297 | 0 | 0 | OPT |
| gate_direction_r2 | r22_books | 18 | 76219 | 6625 | 0.08692058 | 0.00253540 | 0.10197935 | 0 | 0 | OPT |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 3214 | 0.08657472 | -0.00602671 | 0.09780968 | 0 | 0 | OPT |
| gate_direction_r2 | r24_tail | 160 | 84696 | 8117 | 0.09583688 | 0.05812121 | 0.14166181 | 1 | 0 | OPT |
| trend_side | 30d | 4 | 3036 | 276 | 0.09090909 | -0.08132790 | 0.14008172 | 0 | 0 | OPT |
| trend_side | 7d_report_only | 4 | 3047 | 288 | 0.09451920 | -0.05147457 | 0.13796862 | 0 | 0 | OPT |
| trend_side_tp | tp_grid | 9 | 16764 | 1178 | 0.07026963 | -0.05427707 | 0.10102651 | 0 | 9 | OPT |


## k45_funding_plan_review_20261004

### manifest 필드

| 필드 | 값 |
|---|---|
| created_utc | 2026-10-04T01:55:39.065926+00:00 |
| created_local | 2026-10-04T10:55:39.065935+09:00 |
| run_started_utc | 2026-10-04T01:42:09.953762+00:00 |
| elapsed_seconds | 809.0986950998195 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | Claude plan items 1-6 may be false; test each before acceptance |
| local_only | True |
| downloads | 0 |
| workers | 1 |
| cpu_workers_max | 8 |

### out_of_sample_result (원문)

```text
{
 "retrained": false,
 "repriced_only": true,
 "hold_b_used_for_verdict": false
}
```

- 출력 해시 확인: 9/9 일치

### REPORT.md 앞 150줄 (전체 174줄, 원문)

# K45 펀딩 오류 후속 계획 적대적 검토

| item | verdict | basis |
| --- | --- | --- |
| 1 | PARTIAL | central error holds; 100% is minute-floor/tolerance result, formula exact-match 34.05% |
| 2 | PARTIAL | 6 candidates include >1% changes; family proxy/exact changes=1/1; R2-19 omitted |
| 3 | DISAGREE | direct repricing sign changes=4; memory 0.1156 not reproduced |
| 4 | DISAGREE | boundary rule is sign-dependent; raw-ms and floor differ |
| 5 | DISAGREE | R2-15 fit audits using next feature=1197; G2 pre signal age 7.0-7.5h |
| 6 | PARTIAL | self-critique valid but misses boundary sign, initial sign flip, G2 long selection, duplicate feature |

## 1. 오류 판정

PARTIAL. 중심 결론은 유지된다. 다만 표현은 과장됐다.

- 공식 근사식 대 archive T: Pearson 0.99683330, MAE 0.04525121 bps, 1e-9 exact 0.34054510.
- R2-14 대 archive T-8h: 7,118/7,118 일치. 단, 분 floor와 1e-9 허용 결과다. 최대 오차 0.00000102 bps.
- raw `calc_time` 비정각 3,190/7,119, 최대 47 ms. raw timestamp 기준 100% 시각 일치는 아니다.
- registry `funding_rate`와 `next_funding_rate`는 last-settled와 3,417,120/3,417,120 일치. 미래값이 실제로 달랐던 2,513,756분 중 미래값 일치 0.
- 근거: `out/k45_funding_review_20261004/premium_formula_alignment.parquet`, `r214_archive_shift.parquet`, `archive_time_properties.parquet`, `registry_future_summary.parquet`; `btcusdt_quant/funding_source.py:290-337`.

## 2. 재실행 범위와 후보 영향

### 2a. 지정 6칸

| cell_id | segment | n | net_difference_bps | difference_per_trade_bps | difference_pct_abs_old_net | old_net_bps | archive_net_bps | net_sign_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1\|1h\|3\|signal\|L | DEV | 375 | -163.77640861 | -0.43673709 | -1.11896390 | 14636.43366430 | 14472.65725569 | False |
| E1\|1h\|3\|signal\|L | HOLD_B | 30 | -0.63259995 | -0.02108666 | -0.04370767 | 1447.34304576 | 1446.71044581 | False |
| E1\|1h\|2\|signal\|L | DEV | 583 | -200.35151382 | -0.34365611 | -1.29106107 | 15518.36075588 | 15318.00924206 | False |
| E1\|1h\|2\|signal\|L | HOLD_B | 49 | -0.23930006 | -0.00488367 | -0.01247779 | 1917.80804788 | 1917.56874782 | False |
| F3\|1h\|10/24\|signal\|LS | DEV | 873 | -87.71831062 | -0.10047916 | -0.24790228 | 35384.22965313 | 35296.51134251 | False |
| F3\|1h\|10/24\|signal\|LS | HOLD_B | 76 | -0.60010016 | -0.00789605 | -0.05075295 | 1182.39459428 | 1181.79449412 | False |
| F3\|1h\|5/24\|signal\|LS | DEV | 612 | -92.31741018 | -0.15084544 | -0.32540154 | 28370.30485868 | 28277.98744850 | False |
| F3\|1h\|5/24\|signal\|LS | HOLD_B | 43 | 1.66009987 | 0.03860697 | 0.16008780 | 1036.99339277 | 1038.65349264 | False |
| A3\|4h\|720\|signal\|LS | DEV | 339 | -39.18471045 | -0.11558912 | -0.12515326 | 31309.38061028 | 31270.19589983 | False |
| A3\|4h\|720\|signal\|LS | HOLD_B | 45 | -1.63580030 | -0.03635112 | -0.05352859 | 3055.93744477 | 3054.30164447 | False |
| F4\|1h\|5/4\|signal\|L | DEV | 1812 | 166.31399388 | 0.09178476 | 2.06439935 | 8056.28979850 | 8222.60379239 | False |
| F4\|1h\|5/4\|signal\|L | HOLD_B | 186 | 13.59439981 | 0.07308817 | 1.21119393 | 1122.39662435 | 1135.99102416 | False |

`difference_pct_abs_old_net = 100 * 차이 / abs(old net)`. F4 DEV +2.064399%, HOLD_B +1.211194%. E1 z2 DEV -1.291061%, z3 DEV -1.118964%. 12행 중 1% 초과 4행, 0.1% 미만 4행, 0.1~1% 4행.

### 2b. 계열 대표

| family | old_cell_id | old_daily_sharpe | proxy_cell_id | proxy_archive_sharpe | exact_cell_id | exact_archive_sharpe | proxy_changed | exact_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | A1\|4h\|50/200\|trail2\|L | 0.94427472 | A1\|4h\|50/200\|trail2\|L | 0.94367766 | A1\|4h\|50/200\|trail2\|L | 0.94393375 | False | False |
| A2 | A2\|4h\|55/10\|signal\|L | 0.90694420 | A2\|4h\|55/10\|signal\|L | 0.90505850 | A2\|4h\|55/10\|signal\|L | 0.90589118 | False | False |
| A3 | A3\|4h\|720\|signal\|LS | 0.80035349 | A3\|4h\|720\|signal\|LS | 0.79935182 | A3\|4h\|720\|signal\|LS | 0.79964198 | False | False |
| A4 | A4\|4h\|10/3\|signal\|L | 0.60204447 | A4\|4h\|10/3\|signal\|L | 0.59989241 | A4\|4h\|10/3\|signal\|L | 0.60044277 | False | False |
| A5 | A5\|4h\|25\|trail2\|L | 0.78304764 | A5\|4h\|25\|trail2\|L | 0.78002389 | A5\|4h\|25\|trail2\|L | 0.78115823 | False | False |
| A6 | A6\|1h\|40/60\|signal\|L | 0.36339307 | A6\|1h\|40/60\|signal\|L | 0.36431538 | A6\|1h\|40/60\|signal\|L | 0.36418839 | False | False |
| B1 | B1\|15m\|2.5/12\|signal\|L | -0.27537316 | B1\|15m\|2.5/12\|signal\|L | -0.27752706 | B1\|15m\|2.5/12\|signal\|L | -0.27750740 | False | False |
| B2 | B2\|1h\|20/80/4\|signal\|L | 0.67064712 | B2\|1h\|20/80/4\|signal\|L | 0.67910185 | B2\|1h\|20/80/4\|signal\|L | 0.67640083 | False | False |
| B3 | B3\|1h\|3\|signal\|L | 0.02830351 | B3\|1h\|3\|signal\|L | 0.04007746 | B3\|1h\|3\|signal\|L | 0.04008697 | False | False |
| B4 | B4\|1h\|20/5\|signal\|L | -0.43217380 | B4\|1h\|20/5\|signal\|L | -0.42176555 | B4\|1h\|20/5\|signal\|L | -0.42213975 | False | False |
| C1 | C1\|1h\|20/12\|limit\|L | 0.83760607 | C1\|1h\|20/12\|limit\|L | 0.83255342 | C1\|1h\|20/12\|limit\|L | 0.83342027 | False | False |
| C2 | C2\|4h\|20\|signal\|L | 0.38520187 | C2\|4h\|20\|signal\|L | 0.38695856 | C2\|4h\|20\|signal\|L | 0.38700087 | False | False |
| C3 | C3\|4h\|inside\|signal\|L | 0.87527881 | C3\|4h\|inside\|signal\|L | 0.87358651 | C3\|4h\|inside\|signal\|L | 0.87447138 | False | False |
| C4 | C4\|4h\|pin/trend4h\|signal\|S | 0.27638284 | C4\|4h\|pin/trend4h\|signal\|S | 0.27779400 | C4\|4h\|pin/trend4h\|signal\|S | 0.27795851 | False | False |
| C5 | C5\|4h\|3\|signal\|L | 0.27078014 | C5\|4h\|3\|signal\|L | 0.26953051 | C5\|4h\|3\|signal\|L | 0.26978303 | False | False |
| D1 | D1\|1h\|20\|signal\|L | -0.14229020 | D1\|4h\|20\|signal\|S | -0.14659601 | D1\|4h\|20\|signal\|S | -0.14674368 | True | True |
| D2 | D2\|4h\|NR4\|signal\|L | 0.55303006 | D2\|4h\|NR4\|signal\|L | 0.54871097 | D2\|4h\|NR4\|signal\|L | 0.54939252 | False | False |
| E1 | E1\|1h\|3\|signal\|L | 1.14823991 | E1\|1h\|3\|signal\|L | 1.13539152 | E1\|1h\|3\|signal\|L | 1.13769962 | False | False |
| E2 | E2\|1h\|4h/follow/5\|signal\|L | 0.44106873 | E2\|1h\|4h/follow/5\|signal\|L | 0.43046447 | E2\|1h\|4h/follow/5\|signal\|L | 0.43048965 | False | False |
| E3 | E3\|1h\|revert\|signal\|L | 0.13739256 | E3\|1h\|revert\|signal\|L | 0.14622040 | E3\|1h\|revert\|signal\|L | 0.14610064 | False | False |
| F1 | F1\|1h\|5/24\|signal\|LS | 0.74949435 | F1\|1h\|5/24\|signal\|LS | 0.72627385 | F1\|1h\|5/24\|signal\|LS | 0.72708712 | False | False |
| F2 | F2\|4h\|--/fade/24\|signal\|L | 0.30520342 | F2\|4h\|--/fade/24\|signal\|L | 0.30972449 | F2\|4h\|--/fade/24\|signal\|L | 0.31017044 | False | False |
| F3 | F3\|1h\|10/24\|signal\|LS | 1.48559729 | F3\|1h\|10/24\|signal\|LS | 1.48191446 | F3\|1h\|10/24\|signal\|LS | 1.48365989 | False | False |
| F4 | F4\|1h\|5/4\|signal\|L | 0.59888866 | F4\|1h\|5/4\|signal\|L | 0.61125211 | F4\|1h\|5/4\|signal\|L | 0.61097858 | False | False |
| G1 | G1\|1m\|us/60\|signal\|L | 0.64702321 | G1\|1m\|us/60\|signal\|L | 0.65156700 | G1\|1m\|us/60\|signal\|L | 0.65239166 | False | False |
| G2 | G2\|1m\|before/60/60\|signal\|L | 0.79149743 | G2\|1m\|before/60/60\|signal\|L | 0.74563965 | G2\|1m\|before/60/60\|signal\|L | 0.74517534 | False | False |
| G3 | G3\|1d\|1\|signal\|L | 0.73909840 | G3\|1d\|1\|signal\|L | 0.74110921 | G3\|1d\|1\|signal\|L | 0.74194310 | False | False |
| H1 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14923506 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14944378 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14958840 | False | False |
| H2 | H2\|1h\|40/60/funding5\|signal\|L | 0.50621585 | H2\|1h\|40/60/funding5\|signal\|L | 0.50504098 | H2\|1h\|40/60/funding5\|signal\|L | 0.50507701 | False | False |
| H3 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08734380 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08510006 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08513719 | False | False |

근사: `old Sharpe * archive net / old net`; 일별 표준편차 고정. 변경 1/30계열. 정확 재계산은 exit-day 일별 archive 손익 사용. 변경 1/30계열.

### 2c. 누락

R2-19 누락. R2-19는 6개 후보, R2-14 all_cells/cost/buy-hold, archive floor를 읽는다(`out/run_k45_validation_r2_19.py:27-36,48-65,592-631`). R2-14 대표 변경 시 후보 목록부터 바뀐다.

## 3. 초기 실험 직접 재계산

| experiment | table | cells | trade_instances | crossing_instances | crossing_rate_weighted | signed_difference_mean_bps_weighted | absolute_difference_mean_bps_weighted | sign_changed_cells | rank_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | 8 | 30358 | 2928 | 0.09644904 | -0.03341098 | 0.10766595 | 1 | 0 |
| gate_direction_r2 | r21_arm | 12 | 40285 | 3403 | 0.08447313 | -0.04274554 | 0.10225749 | 0 | 2 |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1672 | 0.09907561 | -0.01611581 | 0.11362491 | 0 | 0 |
| gate_direction_r2 | r22_books | 18 | 76219 | 7497 | 0.09836130 | -0.04080053 | 0.12164810 | 2 | 0 |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 3573 | 0.09624502 | -0.05212651 | 0.11869375 | 0 | 0 |
| gate_direction_r2 | r24_tail | 160 | 84696 | 7850 | 0.09268442 | 0.01584908 | 0.13573816 | 1 | 0 |
| trend_side | 30d | 4 | 3036 | 279 | 0.09189723 | -0.08604246 | 0.14463752 | 0 | 0 |
| trend_side | 7d_report_only | 4 | 3047 | 289 | 0.09484739 | -0.05648569 | 0.14214358 | 0 | 0 |

원장 범위: gate-direction 1차 `book_trades.parquet`; R2는 prediction 원장으로 R2-1~R2-4 실행 규칙 재구성; trend-side는 30d/7d book 원장. raw archive ms, `entry < T <= exit` 적용.

메모리 9.30%/0.1156 bps와 동일하지 않다. gate-direction 1차 공식 8칸의 가중 통과율과 절대 차이는 위 표 값이다. HOLD_B margin=0.05는 +0.00567648 -> -0.00344394 bps로 부호 변경.

### 부호·순위 변경 칸

| experiment | table | cell_id | segment | n | crossing_rate | signed_difference_mean_bps | old_net_mean_bps | new_net_mean_bps | sign_changed | old_rank | new_rank | rank_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | margin=0.05 | HOLD_B | 886 | 0.11738149 | -0.00912043 | 0.00567648 | -0.00344394 | True | 1.00000000 | 1.00000000 | False |
| gate_direction_r2 | r21_arm | LONG\|h=45 | DEV | 9217 | 0.09883910 | -0.10785094 | -2.46856452 | -2.57641546 | False | 2.00000000 | 1.00000000 | True |
| gate_direction_r2 | r21_arm | LONG\|h=60 | DEV | 8899 | 0.13911675 | -0.13502755 | -2.45886641 | -2.59389397 | False | 1.00000000 | 2.00000000 | True |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|ALL | DEV | 2967 | 0.08897877 | -0.06314456 | 0.05195392 | -0.01119063 | True | 1.00000000 | 1.00000000 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|CAP3 | DEV | 2967 | 0.08897877 | -0.06314456 | 0.05195392 | -0.01119063 | True | 2.00000000 | 2.00000000 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|SINGLE | DEV | 319 | 0.07523511 | -0.10562539 | 0.01412412 | -0.09150127 | True | 2.00000000 | 2.00000000 | False |

순위 정의: gate1=segment 내 margin; R2-1 arm=segment·arm 내 horizon; R2-2=segment·signal 내 book; R2-3=segment 내 variant·book; R2-4=segment·score·tail·book 내 share; trend-side=lookback·segment 내 arm.

## 4. 정산 경계

| scope | boundary | trade_instances | boundary_trade_n | boundary_nonzero_offset_n | boundary_cashflow_sum_bps | nonzero_offset_cashflow_sum_bps | floor_minus_raw_boundary_bps | floor_minus_raw_all_events_bps | floor_event_count_minus_raw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-19 six candidate trade-instances | entry | 5522 | 1312 | 538 | -719.04160000 | -145.70680000 | 145.70680000 | 37.75900000 | -45 |
| R2-19 six candidate trade-instances | exit | 5522 | 1216 | 493 | -665.60210000 | -107.94780000 | -107.94780000 | 37.75900000 | -45 |
| R2-6 model metric trade-instances | entry | 745590 | 24372 | 10947 | -12600.40750000 | -4831.59840000 | 4831.59840000 | 1908.37720000 | -1527 |
| R2-6 model metric trade-instances | exit | 745590 | 20409 | 9420 | -6409.02020000 | -2923.22120000 | -2923.22120000 | 1908.37720000 | -1527 |

`entry < T <= exit`는 보수적이지 않다. cashflow=`-side*rate*10000`. 경계 cashflow가 양수면 포함은 낙관적이다. 음수면 포함은 보수적이다.

R2-6은 loader가 raw ms를 보존한다(`out/run_k45_gate_direction_r2_6.py:128-136`; `btcusdt_quant/funding_source.py:131-157,255-280`). R2-19는 분 floor다(`out/run_k45_validation_r2_19.py:48-65`). 동일 거래가 다른 event set을 받는다.

더 나은 규칙: scheduled T로 정규화하고 체결 규약을 고정한다. T 경계는 두 값도 병기한다. pessimistic은 경계 cashflow `min(cashflow,0)`만 포함. optimistic은 `max(cashflow,0)`만 포함. 1차 판정은 두 값 모두 같은 결론일 때만 확정한다.

## 5. `next_funding_rate` 전수

| consumer | direct | count | detail |
| --- | --- | --- | --- |
| R2-14 G2 before | True | 12 | 12 grid cells call attached.next_funding_rate for direction |
| R2-15 model feature | True | 1197 | fit audits using feature / all fit audits = 1197/2170 |
| R2-15 G2 ctx_signal_strength | True | 1030 | G2 candidate rows; selected G2 rules=1 |
| R2-18 G2 rule candidates | False | 4 | 4 before/pre/post rules call R2-14 _g2_signals |
| generic feature registry | True | 1 | metadata says announced next rate; loader supplies last-settled alias |
| gate-direction dataset | False | 28518 | f_next range=0.0..0.0; selected feature rows=0 |

G2 문서 정정만으로 부족하다. G2 before는 다음 정산 60/30분 전 진입한다. last-settled 요율 나이는 약 7.0/7.5시간이다. `8시간 이상`도 틀렸다(`out/run_k45_classic_rules_r2_14.py:188-189,690-700`).

R2-15는 registry feature로 직접 학습하고 G2 signal strength에도 쓴다(`out/run_k45_meta_label_r2_15.py:287-329,380-428,793-803`). R2-18도 4개 G2 before 규칙을 만든다(`out/run_k45_risk_stop_r2_18.py:231-250`). feature registry 설명은 `announced next funding rate`지만 loader는 last-settled 복제다(`btcusdt_quant/feature_registry.py:190`; `btcusdt_quant/funding_source.py:297-307`).

## 6. 추가 실수·위험

- G2 숏만 언급했다. R2-15 selected_rules에는 `G2|1m|before/60/60|signal|L` 1칸이 있다: DEV +5,553.163853 bps, Sharpe 0.791497, HOLD_B +680.485058 bps.
- R2-6 `funding_bps`는 비용 양수 후 차감이다(`run_k45_gate_direction_r2_6.py:90-98`). R2-14 `funding_bps`는 cashflow 후 가산이다(`run_k45_classic_rules_r2_14.py:250-268`). 재가격 코드에서 부호 혼용 위험.
- 초기 PnL 누락은 모델 라벨 오류가 아니어도 결과표 오류다. `문서만`은 재현 가능한 수치 교정이 아니다.
- R2-15 `funding_rate`와 `next_funding_rate`는 완전 중복이다. CatBoost에 중복 열을 넣으면 의미 없는 자유도와 중요도 분산이 생긴다. alias 제거 ablation 필요.
- archive raw ms를 실제 snapshot 시각으로 볼 근거가 로컬 자료에 없다. floor와 raw 중 하나를 진실로 단정하면 안 된다.

## k45_funding_rerun_r2_20_21_20261004

- 테스트 재실행 `tests/test_k45_mtf_tail_r2_20.py`: `5 passed in 5.44s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-04T06:33:41.673779+00:00 |
| run_finished_utc | 2026-10-04T06:33:42.712957+00:00 |
| workflow_started_utc | 2026-10-04T06:20:34.361372+00:00 |
| workflow_elapsed_seconds | 788.351585 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| local_data_only | True |
| downloads | 0 |
| live_orders | 0 |
| model_training | 0 |
| cpu_worker_limit | 12 |
| cpu_processes_used | 4 |
| funding_boundaries | ["PESS", "OPT"] |
| tests | [{"attempt": 1, "passed": 20, "failed": 0, "error": 1, "seconds": 8.32, "status": "DEFAULT_TEMP_PERMISSION_ERROR"}, {"attempt": 2, "passed": 21, "failed": 0, "error": 0, "seconds": 7.97, "status": "PASS"}] |

- 출력 해시 확인: 73/73 일치

### REPORT.md 앞 150줄 (전체 500줄, 원문)

# R2-20 R2-21 FUNDING RERUN

## TEST

| attempt | passed | failed | error | seconds | status |
| --- | --- | --- | --- | --- | --- |
| 1 | 20 | 0 | 1 | 8.32000000 | DEFAULT_TEMP_PERMISSION_ERROR |
| 2 | 21 | 0 | 0 | 7.97000000 | PASS |

## SOURCE_INTEGRITY

| path | recorded_sha256 | current_sha256 | match |
| --- | --- | --- | --- |
| out/k45_patchtst_updown_r2_21_20261003/ensemble_predictions.parquet | 265d1b21bcbc1f3e1db5b9b8688bd3d749defe42804e1af5b7e60662495eadb5 | 265d1b21bcbc1f3e1db5b9b8688bd3d749defe42804e1af5b7e60662495eadb5 | True |
| out/k45_patchtst_updown_r2_21_20261003/evaluated_predictions.parquet | 80c4cd695d3fd52defe1b1a257dbd35f4f27243fe3d831674a73755706cc5c3b | 80c4cd695d3fd52defe1b1a257dbd35f4f27243fe3d831674a73755706cc5c3b | True |
| out/k45_patchtst_updown_r2_21_20261003/thresholds.parquet | 7c8f9e1257f1c181559a59aa9265f2c8b79bf2c711f1fb0ded11a5ba13661680 | 7c8f9e1257f1c181559a59aa9265f2c8b79bf2c711f1fb0ded11a5ba13661680 | True |

## OLD_PESS_OPT_TOTAL

| experiment | variant | configured_cell_n | metric_cell_n | nonempty_cell_n | trade_instances | gross_total_bps | funding_cashflow_total_bps | net_total_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-20 | OLD | 120 | 240 | 219 | 43920 | 331959.08122786 | 3.74470000 | 156282.82592786 |
| R2-21 | OLD | 144 | 144 | 144 | 722420 | 315073.79245768 | -10476.94700000 | -2585083.15454232 |
| R2-20 | PESS | 120 | 240 | 219 | 43920 | 331959.08122786 | -7869.84520000 | 148409.23602786 |
| R2-21 | PESS | 144 | 144 | 144 | 722420 | 315073.79245768 | -45975.31050000 | -2620581.51804232 |
| R2-20 | OPT | 120 | 240 | 219 | 43920 | 331959.08122786 | 7714.28050000 | 163993.36172786 |
| R2-21 | OPT | 144 | 144 | 144 | 722420 | 315073.79245768 | 23603.76150000 | -2551002.44604232 |

## CELL_NET_DIFFERENCE

| experiment | from | to | cell_n | min_bps | p05_bps | median_bps | mean_bps | p95_bps | max_bps | sum_bps | sign_changed_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-20 | OLD | PESS | 240 | -450.11180000 | -148.18281500 | -4.54350000 | -32.80662458 | 0.00000000 | 0.00000000 | -7873.58990000 | 1 |
| R2-20 | OLD | OPT | 240 | 0.00000000 | 0.00000000 | 4.04590000 | 32.12723250 | 147.15539500 | 464.33780000 | 7710.53580000 | 0 |
| R2-20 | PESS | OPT | 240 | 0.00000000 | 0.00000000 | 8.01415000 | 64.93385708 | 300.65229500 | 914.44960000 | 15584.12570000 | 1 |
| R2-21 | OLD | PESS | 144 | -1341.88870000 | -1008.29435500 | -66.83360000 | -246.51641319 | -5.98538500 | -4.64500000 | -35498.36350000 | 0 |
| R2-21 | OLD | OPT | 144 | 4.26520000 | 5.71488500 | 66.73850000 | 236.67158681 | 921.72023500 | 1264.27420000 | 34080.70850000 | 0 |
| R2-21 | PESS | OPT | 144 | 10.58280000 | 10.65645500 | 145.18365000 | 483.18800000 | 2003.04194000 | 2456.86720000 | 69579.07200000 | 0 |

## SIGN_CHANGES

| experiment | from | to | cell | from_net_bps | to_net_bps | from_sign | to_sign |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R2-20 | OLD | PESS | 1h_h60|SIDE|ROLLING_180D|q05|g0|HOLD_B | 15.55602053 | -4.45847947 | 1 | -1 |
| R2-20 | PESS | OPT | 1h_h60|SIDE|ROLLING_180D|q05|g0|HOLD_B | -4.45847947 | 34.53252053 | -1 | 1 |

## BOUNDARY_SETTLEMENT

| experiment | variant | trade_instances | entry_boundary_trade_n | exit_boundary_trade_n | any_boundary_trade_n | included_boundary_trade_n | boundary_cashflow_sum_bps | interior_cashflow_sum_bps | funding_event_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-20 | PESS | 43920 | 8356 | 7658 | 14594 | 8122 | -8261.00780000 | 391.16260000 | 14747 |
| R2-20 | OPT | 43920 | 8356 | 7658 | 14594 | 6689 | 7323.11790000 | 391.16260000 | 13217 |
| R2-21 | PESS | 722420 | 24352 | 25204 | 49556 | 29085 | -41739.76170000 | -4235.54880000 | 44489 |
| R2-21 | OPT | 722420 | 24352 | 25204 | 49556 | 20470 | 27839.31030000 | -4235.54880000 | 35874 |

## R2_20

| variant | cell_n | positive_both_segments_n | dev_positive_n | hold_b_positive_n | dev_ci95_lower_gt_0_n | dev_top5_signal_events_removed_positive_n | dev_net_mean_gt_always_long_n | hypothesis_eligible_n | hypothesis_pass_n | hypothesis_all_pass | spa_p | rc_p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OLD | 120 | 42 | 92 | 51 | 11 | 35 | 47 | 48 | 45 | False | 0.16983017 | 0.20179820 |
| PESS | 120 | 42 | 92 | 50 | 10 | 34 | 47 | 48 | 45 | False | 0.17882118 | 0.23776224 |
| OPT | 120 | 42 | 92 | 51 | 11 | 36 | 47 | 48 | 45 | False | 0.16083916 | 0.18381618 |

## R2_21

| variant | direction_dev_cell_n | direction_dev_net_min_bps | direction_dev_net_max_bps | direction_gt_fade_cell_n | direction_minus_fade_min_bps | direction_minus_fade_max_bps | primary_direction_net_bps | primary_fade_net_bps | primary_difference_bps | dev_spearman_gt_0 | dev_net_gt_fade | hypothesis_result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OLD | 18 | -5.51104945 | -3.91141070 | 0 | -5.23998393 | -0.39365321 | -4.06265861 | -3.02564657 | -1.03701204 | True | False | FAIL |
| PESS | 18 | -5.55806633 | -3.95538210 | 0 | -5.22344654 | -0.38717000 | -4.11123076 | -3.07757725 | -1.03365352 | True | False | FAIL |
| OPT | 18 | -5.44369476 | -3.85890648 | 0 | -5.22344654 | -0.38717000 | -4.01615076 | -2.98251410 | -1.03363666 | True | False | FAIL |

## R2_21_GATE

| gate | folds | available_folds | no_gate_folds | mean_pass_rate | zero_percent_folds | over_25_percent_folds |
| --- | --- | --- | --- | --- | --- | --- |
| OLD | 667 | 667 | 0 | 0.14980546 | 31 | 129 |
| G_STOP | 667 | 667 | 0 | 0.14880511 | 33 | 127 |
| G_ROLL | 667 | 660 | 7 | 0.09639741 | 123 | 69 |
| G_EXP | 667 | 666 | 1 | 0.02843707 | 426 | 18 |

## R2_21_GATE_TRADES

| variant | segment | gate | cell_n | net_min_bps | net_max_bps | h15_m0_n | h15_m0_net_bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OLD | DEV | G_STOP | 6 | -5.21859803 | -3.91525381 | 25840 | -4.06265861 |
| OLD | HOLD_B | G_STOP | 6 | -8.35252297 | -4.77203632 | 2624 | -4.83254593 |
| OLD | DEV | G_ROLL | 6 | -4.76983294 | -3.91141070 | 16263 | -3.93613664 |
| OLD | HOLD_B | G_ROLL | 6 | -6.89503311 | -4.36772064 | 1978 | -4.47289816 |
| OLD | DEV | G_EXP | 6 | -5.51104945 | -4.10570714 | 4759 | -4.54967716 |
| OLD | HOLD_B | G_EXP | 6 | -5.71032394 | -3.57573350 | 673 | -5.12913134 |
| PESS | DEV | G_STOP | 6 | -5.28340929 | -3.97111524 | 25840 | -4.11123076 |
| PESS | HOLD_B | G_STOP | 6 | -8.36709503 | -4.78735523 | 2624 | -4.84835282 |
| PESS | DEV | G_ROLL | 6 | -4.81242203 | -3.95538210 | 16263 | -3.97796445 |
| PESS | HOLD_B | G_ROLL | 6 | -6.91142784 | -4.38321599 | 1978 | -4.48755660 |
| PESS | DEV | G_EXP | 6 | -5.55806633 | -4.17191150 | 4759 | -4.61405993 |
| PESS | HOLD_B | G_EXP | 6 | -5.73056232 | -3.59732520 | 673 | -5.14563298 |
| OPT | DEV | G_STOP | 6 | -5.16027348 | -3.85890648 | 25840 | -4.01615076 |
| OPT | HOLD_B | G_STOP | 6 | -8.33818281 | -4.75777820 | 2624 | -4.81805564 |
| OPT | DEV | G_ROLL | 6 | -4.72166985 | -3.86417230 | 16263 | -3.89077573 |
| OPT | HOLD_B | G_ROLL | 6 | -6.88314893 | -4.35406366 | 1978 | -4.46038537 |
| OPT | DEV | G_EXP | 6 | -5.44369476 | -4.03056703 | 4759 | -4.47590515 |
| OPT | HOLD_B | G_EXP | 6 | -5.69409902 | -3.55896455 | 673 | -5.10980980 |

## CONFIRMED

| experiment | item_type | item | pess | opt | status |
| --- | --- | --- | --- | --- | --- |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|EXPANDING_OOS|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|EXPANDING_OOS|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q01|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|MAX|ROLLING_180D|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q01|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q01|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q02|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |

## k45_funding_review_20261004

### manifest 필드

| 필드 | 값 |
|---|---|
| created_utc | 2026-10-04T00:03:03.984293+00:00 |
| source_timestamp_local | 2026-10-04T09:03:03.984303+09:00 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| hypothesis_frozen | R2-14 applies archive T-8h funding at settlement T |
| oos_result | {"retrained": false, "cells": 813, "segments": ["DEV", "HOLD_B"]} |
| local_only | True |
| downloads | 0 |
| workers | 1 |
| numeric_threads_max | 8 |
| elapsed_seconds_this_process | 6.887678700033575 |
| resumed_from_completed_parquets | True |

- 출력 해시 확인: 16/16 일치

### REPORT.md 앞 150줄 (전체 179줄, 원문)

# K45 funding-rate adversarial review

| claim | verdict | basis |
| --- | --- | --- |
| A | SUPPORTED | R2-14(T)=archive(T-8h), premium formula(T)=archive(T) |
| B | REFUTED | 전략 계열 목록은 맞지만 R2-19도 R2-14 source를 소비; 일부 gate-direction은 archive가 아니라 funding 미반영 |
| C | REFUTED | R2-15 CatBoost y=R2-14 net_bps>0; 나머지 조사 모델 타깃은 가격 경로 |
| D | REFUTED | E1 예시는 맞지만 6칸 net 부호 변화, DEV 최대 \|Δ\| 703.9bps |

- 범위: 로컬 데이터만. 다운로드 0. 원본 코드 수정 0. 재학습 0.
- 데이터 cutoff: 2026-06-30 23:59 UTC.
- 동결 가설: `R2-14는 T에 T-8h 정산 요율을 적용한다`; 반대 가설부터 검사.
- OOS 결과: 회계 요율만 교체한 813칸 DEV/HOLD_B 재계산. 신호·거래·모델 고정.

## 1. 아카이브 시각 규약 — A SUPPORTED

- 실제 열: `calc_time|funding_interval_hours|last_funding_rate`. 78 ZIP 모두 동일.
- 행: 7119. `funding_interval_hours!=8`: 0.
- `calc_time` 분 경계 비정수 ms 행: 3190; 최대 offset 47 ms.
- 공식 근사: 1m premium close의 480분 선형가중 TWAP + clamp(0.01%-TWAP, ±0.05%), 최종 ±0.30% cap. Binance 정산은 5초 관측이라 exact match는 기대하지 않는다.

### 프리미엄 공식 결과

| comparison | n | pearson | spearman | mae_bps | median_ae_bps | p95_ae_bps | match_1e9_rate | within_0_01bps_rate | within_0_05bps_rate | within_0_10bps_rate | sign_match_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| archive_T_minus_8h | 7118 | 0.79491388 | 0.80873880 | 0.57285627 | 0.23154777 | 2.37109783 | 0.26425962 | 0.27507727 | 0.31834785 | 0.37046923 | 0.85951110 |
| archive_T | 7118 | 0.99683330 | 0.98034785 | 0.04525121 | 0.01267814 | 0.14339818 | 0.34054510 | 0.47400955 | 0.76144985 | 0.90207924 | 0.98468671 |
| archive_T_plus_8h | 7117 | 0.80573913 | 0.81092729 | 0.56130855 | 0.23389789 | 2.27044176 | 0.26513981 | 0.27638050 | 0.32190530 | 0.37515807 | 0.86398764 |

`archive_T`가 상관·MAE 모두 최상이다. 따라서 `calc_time=T`는 `(T-8h,T]`에서 계산되어 T에 정산된 요율이다.

### R2-14 event와 archive shift

| comparison | n | match_count | match_rate | pearson | spearman | mae_bps | max_ae_bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| archive_T_minus_8h | 7118 | 7118 | 1.00000000 | 1.00000000 | 1.00000000 | 0.00000003 | 0.00000102 |
| archive_T | 7118 | 1881 | 0.26425962 | 0.79893641 | 0.81949518 | 0.56511942 | 28.39270007 |
| archive_T_plus_8h | 7117 | 1758 | 0.24701419 | 0.73919778 | 0.76807597 | 0.67523988 | 28.48509993 |

근거 코드: `out/run_k45_classic_rules_r2_14.py:204-221`은 T 직전 행을 shift하고, `btcusdt_quant/funding_source.py:290-337`은 registry current/next를 마지막 정산 완료 요율로 정의한다.

### registry 전수

| rows | funding_nonnull | current_vs_last_settled_matches | current_vs_last_settled_match_rate | next_named_vs_last_settled_matches | next_named_vs_last_settled_match_rate | next_named_equals_current_count | current_equals_strict_future_count | strict_future_comparable | current_equals_strict_future_rate | past_future_same_count | future_differs_count | current_equals_future_when_future_differs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3417120 | 3417120 | 3417120 | 1.00000000 | 3417120 | 1.00000000 | 3417120 | 902885 | 3416641 | 0.26426101 | 902885 | 2513756 | 0 |

미래 요율이 과거와 실제로 다른 2513756분 중 registry current가 미래와 일치한 분: 0.
미래 일치 사례는 다음 정산 요율이 직전 정산 요율과 같은 반복값이다. 미래정보 증거가 아니다.

| registry_minute_relative_T | comparison | n | match_count | match_rate |
| --- | --- | --- | --- | --- |
| -1 | archive_T_minus_8h | 7118 | 7118 | 1.00000000 |
| -1 | archive_T | 7118 | 1881 | 0.26425962 |
| -1 | archive_T_plus_8h | 7117 | 1758 | 0.24701419 |
| 0 | archive_T_minus_8h | 7118 | 4276 | 0.60073054 |
| 0 | archive_T | 7119 | 4724 | 0.66357634 |
| 0 | archive_T_plus_8h | 7118 | 1831 | 0.25723518 |
| 1 | archive_T_minus_8h | 7118 | 1881 | 0.26425962 |
| 1 | archive_T | 7119 | 7119 | 1.00000000 |
| 1 | archive_T_plus_8h | 7118 | 1881 | 0.26425962 |

| registry_change_count | offset_0_minutes | offset_1_minutes | other_offset_minutes |
| --- | --- | --- | --- |
| 5237 | 2842 | 2395 | 0 |

| minutes_after_scheduled_T | change_count |
| --- | --- |
| 0 | 2842 |
| 1 | 2395 |

## 2. 실험별 손익 펀딩 경로 — B REFUTED

| file | pnl_funding_source | affected_by_r214_shift | import_chain | evidence | note |
| --- | --- | --- | --- | --- | --- |
| out/k45_gate_direction.py | none | False | out.run_patchtst_k45_flow_inference | out/k45_gate_direction.py:16-27 | price label helpers; no PnL funding |
| out/k45_ledger.py | caller | True | out.run_patchtst_k45_flow_inference.optimal_block_length -> out.run_patchtst_k45_flow_inference.stationary_bootstrap_errors | out/k45_ledger.py:13-39 | funding DataFrame supplied by caller |
| out/k45_trend_side.py | none | False |  | out/k45_trend_side.py:32-40 | price return minus fixed cost |
| out/run_k45_classic_rules_r2_14.py | registry_prior_minute | True |  | out/run_k45_classic_rules_r2_14.py:204-257 | settlement_events then _funding_bps |
| out/run_k45_contrarian_robust_r2_17.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 -> run_k45_classic_rules_r2_14 | out/run_k45_contrarian_robust_r2_17.py:144-187 | r214.load_inputs -> r214.simulate |
| out/run_k45_gate_direction_backtest.py | none | False | out.k45_trend_side -> out.run_patchtst_k45_flow_inference -> out.run_k45_gate_direction_dataset.sha256 -> out.run_k45_gate_direction_dataset.write_json -> out.run_k45_gate_direction_dataset.write_parquet | out/run_k45_gate_direction_backtest.py:35-44 | price PnL through k45_trend_side |
| out/run_k45_gate_direction_dataset.py | none | False | out.k45_gate_direction -> out.k45_trend_side -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_dataset.py:1-40 | dataset construction; no realized funding PnL |
| out/run_k45_gate_direction_precheck.py | none | False | out.k45_gate_direction | out/run_k45_gate_direction_precheck.py:1-40 | precheck only |
| out/run_k45_gate_direction_quality.py | none | False | out.k45_gate_direction -> out.run_k45_gate_direction_dataset.sha256 -> out.run_k45_gate_direction_dataset.write_json -> out.run_k45_gate_direction_dataset.write_parquet | out/run_k45_gate_direction_quality.py:1-40 | quality audit only |
| out/run_k45_gate_direction_r2.py | none | False | out.k45_gate_direction -> out.k45_trend_side -> out.run_k45_gate_direction_walkforward -> out.run_patchtst_k45_flow_inference -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_r2.py:281-325 | gross minus 4 bps |
| out/run_k45_gate_direction_r2_10.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_walkforward | out/run_k45_gate_direction_r2_10.py:459-459 | r26.funding_events |
| out/run_k45_gate_direction_r2_11.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_10 -> out.run_k45_gate_direction_walkforward -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_r2_11.py:929-929 | r26.funding_events |
| out/run_k45_gate_direction_r2_6.py | archive_direct | False | btcusdt_quant.funding_source.load_funding_dir -> out.k45_trend_side -> out.run_k45_gate_direction_r2 | out/run_k45_gate_direction_r2_6.py:128-135 | load_funding_dir |
| out/run_k45_gate_direction_r2_7.py | archive_r26 | False | out.k45_trend_side -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 | out/run_k45_gate_direction_r2_7.py:399-399 | r26.funding_events |
| out/run_k45_gate_direction_r2_8.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 | out/run_k45_gate_direction_r2_8.py:147-147 | r26.funding_events via load_inputs |
| out/run_k45_gate_direction_r2_9.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_7 -> out.run_k45_gate_direction_r2_8 | out/run_k45_gate_direction_r2_9.py:184-184 | r26.funding_events |
| out/run_k45_gate_direction_r2_9b.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_11 | out/run_k45_gate_direction_r2_9b.py:256-256 | r26.funding_events |
| out/run_k45_gate_direction_walkforward.py | none | False | out.k45_gate_direction -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_walkforward.py:1-50 | training split helper; no PnL funding |
| out/run_k45_holdout_a_2026q3.py | none | False | out.run_patchtst_k45_causal_admission_ordering | out/run_k45_holdout_a_2026q3.py:486-486 | manifest states funding input unnecessary |
| out/run_k45_meta_label_r2_15.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 | out/run_k45_meta_label_r2_15.py:214-233 | r214.load_inputs -> make_trades |
| out/run_k45_mtf_entry_r2_12.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.k45_defect_audit_20260930.run_audit | out/run_k45_mtf_entry_r2_12.py:379-381,499 | r26.funding_events |
| out/run_k45_mtf_persistence_r2_13.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_mtf_entry_r2_12 -> out.run_patchtst_k45_flow_inference -> out.k45_defect_audit_20260930.run_audit | out/run_k45_mtf_persistence_r2_13.py:390-392,588 | r26.funding_events |
| out/run_k45_mtf_tail_r2_20.py | archive_r26 | False | out.run_k45_classic_rules_r2_14 -> out.run_k45_mtf_entry_r2_12 -> out.run_patchtst_k45_flow_inference.optimal_block_length -> out.run_patchtst_k45_flow_inference.stationary_bootstrap_errors | out/run_k45_mtf_tail_r2_20.py:154-161 | r212.r26.funding_events |
| out/run_k45_patchtst_updown_r2_21.py | archive_direct | False | btcusdt_quant.funding_source.load_funding_dir | out/run_k45_patchtst_updown_r2_21.py:442-447,511-519 | load_funding_dir |
| out/run_k45_risk_stop_r2_18.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 -> out.run_k45_gate_direction_r2_7 -> out.run_k45_mtf_entry_r2_12 | out/run_k45_risk_stop_r2_18.py:164-170,749-795 | final simulation uses r214 funding; source reproduction also reads archive |
| out/run_k45_train_window_r2_16.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_10 -> out.run_k45_gate_direction_walkforward -> out.run_k45_mtf_entry_r2_12 -> out.k45_defect_audit_20260930.run_audit | out/run_k45_train_window_r2_16.py:512-512,567-567 | r26.funding_events |
| out/run_k45_trend_side.py | none | False | out.k45_trend_side -> out.run_patchtst_k45_flow_inference | out/run_k45_trend_side.py:29-30 | price PnL through k45_trend_side |
| out/run_k45_trend_side_tp.py | none | False | out.k45_trend_side -> out.run_k45_trend_side -> out.run_patchtst_k45_flow_inference | out/run_k45_trend_side_tp.py:57-60 | inherits no-funding trend-side PnL |
| out/run_k45_validation_r2_19.py | mixed_r214_and_archive | True | out.run_k45_classic_rules_r2_14 -> out.k45_ledger | out/run_k45_validation_r2_19.py:592-628 | loads r214 and archive comparison sets |

R2-14 오류를 전략 손익에 직접 전파하는 기본 계열은 R2-14/15/17/18이다. 그러나 literal 주장에는 R2-19가 누락됐다. 또 초기 gate-direction/R2는 archive를 쓰는 것이 아니라 정산 펀딩을 아예 빼고 4bps만 쓴다.

## 3. 학습 라벨·미래정보 — C REFUTED

| experiment | model | label | settlement_funding_in_label | evidence |
| --- | --- | --- | --- | --- |
| gate-direction R2 | CatBoost | forward price return > 4bps | False | out/run_k45_gate_direction_r2.py:99-102,281-292 |
| R2-10/R2-11 | CatBoost | directional price return/class | False | out/run_k45_gate_direction_r2_10.py:179-192; out/run_k45_gate_direction_r2_11.py:278-302 |
| R2-12 | CatBoost | directional price return > 4bps | False | out/run_k45_mtf_entry_r2_12.py:289-298; funding attached 379-381 |
| R2-13 | CatBoost | price-path capture/duration/MFE | False | out/run_k45_mtf_persistence_r2_13.py:101-180,224-230; funding attached 390-392 |
| R2-15 | CatBoost/logistic meta | R2-14 net_bps > 0 | True | out/run_k45_meta_label_r2_15.py:214-233,367-419 |
| R2-16 | CatBoost | price return direction | False | out/run_k45_train_window_r2_16.py:167-172,237-245; funding attached 512 |
| R2-21 | PatchTST | up/down/range price excursion | False | out/run_k45_patchtst_updown_r2_21.py:122-158,272-274; funding attached 511-519 |

- R2-15는 예외가 아니라 실제 CatBoost 학습 경로다: `run_k45_meta_label_r2_15.py:214-233,367-419`.
- R2-13 라벨은 가격 path capture/duration/MFE(`:101-180`); 펀딩은 거래 평가 때 `:390-392`.
- R2-16 CatBoost 라벨은 가격 방향(`:167-172,237-245`); archive 펀딩은 평가 때 `:512`.
- R2-20 손익은 `r212.r26.funding_events()` archive(`run_k45_mtf_tail_r2_20.py:154-161`).
- R2-21 PatchTST 타깃은 up/down/range 가격 excursion(`:122-158`); archive 펀딩은 `:511-519`.
- registry `funding_rate`와 `next_funding_rate`는 둘 다 last-settled다. 이름 `next_`는 예상 요율이 아니다.

## 4. R2-14 813칸 재계산 — D REFUTED

| segment | cells | mean | std | min | q05 | q25 | median | q75 | q95 | max | abs_mean | abs_max | net_sign_changed_cells | funding_sign_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV | 813 | -60.52484745 | 173.92901605 | -703.91118656 | -360.27123803 | -128.54390298 | -19.17793032 | 11.59558020 | 180.81352986 | 607.22520022 | 117.04489875 | 703.91118656 | 4 | 13 |
| HOLD_B | 813 | -1.11572878 | 7.78903487 | -77.50250008 | -7.27380010 | -1.86570009 | -0.06270000 | 1.12780005 | 4.23085990 | 36.21389988 | 3.15444390 | 77.50250008 | 2 | 40 |

### net 부호 변화 6칸

| cell_id | segment | old_net_bps | archive_net_bps | net_difference_bps |
| --- | --- | --- | --- | --- |
| A3\|1h\|168\|trail2\|L | HOLD_B | 0.66860761 | -0.04489241 | -0.71350002 |
| A4\|1h\|10/2\|trail2\|LS | DEV | 461.64413610 | -165.23076265 | -626.87489875 |
| A4\|1h\|10/4\|trail2\|LS | DEV | 317.06184675 | -20.70225065 | -337.76409740 |
| A5\|1h\|25\|signal\|LS | DEV | 291.59969493 | -197.05190038 | -488.65159532 |
| A5\|1h\|25\|trail2\|LS | DEV | 340.02797220 | -168.72212128 | -508.75009348 |
| F1\|1h\|10/24\|signal\|LS | HOLD_B | 5.05553545 | -23.01276460 | -28.06830005 |

### E1 z3

| segment | n | old_funding_bps | archive_funding_bps | funding_difference_bps | old_net_bps | archive_net_bps | net_difference_bps | net_sign_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV | 375 | -1238.06279139 | -1401.83920000 | -163.77640861 | 14636.43366430 | 14472.65725569 | -163.77640861 | False |
| HOLD_B | 30 | -2.48790005 | -3.12050000 | -0.63259995 | 1447.34304576 | 1446.71044581 | -0.63259995 | False |

## k45_gate_direction_20261001

- 테스트 재실행 `tests/test_k45_gate_direction.py`: `12 passed in 1.73s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T01:59:38.649120+00:00 |
| run_finished_utc | 2026-10-01T01:59:52.506439+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | On PatchTST-gated bars, CatBoost-chosen direction has positive net results for both LONG and SHORT after 4 bps round-trip cost. |
| primary_margin | 0.1 |
| report_only_margins | [0.0, 0.05, 0.2] |
| entry_exit_rule | close[t] to close[t+45] |
| round_trip_cost_bps | 4.0 |
| pw_date_range_rule | full prediction-row date range within segment |
| random_seed | 20261001 |
| random_direction_rule | all gated prediction rows; independent +/-1 side; same single-position book |
| random_bar_matched_rule | seeded random prefix of gated rows; same book; exact model trade count; independent +/-1 side |
| new_model_fits | 0 |
| local_data_only | True |
| live_orders | 0 |

### out_of_sample_result (원문)

```text
{
 "TASK4_DEV_ORDERING": "PASS",
 "TASK4_HOLD_B_ORDERING": "FAIL",
 "TASK5_DEV": {
  "label": "DEV",
  "status": "FAIL"
 },
 "TASK5_HOLD_B": {
  "label": "HOLD_B exploratory",
  "status": "FAIL"
 }
}
```

- 출력 해시 확인: 7/7 일치

### REPORT.md 앞 150줄 (전체 976줄, 원문)

# K45 gate direction Tasks 1-5

## Task 1

```json
{
  "run_started_utc": "2026-10-01T01:16:52.584437+00:00",
  "run_finished_utc": "2026-10-01T01:19:59.547266+00:00",
  "runtime_seconds": 186.962829,
  "data_cutoff_utc": "2026-06-30T23:59:00+00:00",
  "frozen_hypothesis": "PatchTST 게이트 바에서 CatBoost가 고른 더 높은 확률 방향으로 거래하면, 롱과 숏 모두 net이 0보다 크다.",
  "out_of_sample_result": "not_evaluated_dataset_only",
  "local_data_only": true,
  "feature_cache_used": false,
  "pnl_or_backtest_computed": false,
  "gate_definition": "run_audit filter B sources; passes_q90 before strict in-fold H=45 cut",
  "gate_sources": {
    "backward_0_405": "out\\patchtst_backward_k45_validation_20260929\\ensemble_predictions.parquet",
    "excursion_406_605": "out\\patchtst_post_trigger_markout_20260929\\exploration_origins.parquet:patchtst_q90_gate",
    "confirmation_606_666": "out\\patchtst_down_breakout_long_confirmation_20260929\\ensemble_predictions.parquet"
  },
  "gate_counts_by_source_before_boundary": {
    "backward_0_405": 17447,
    "excursion_406_605": 8541,
    "confirmation_606_666": 2668
  },
  "filter_b_gate_count_before_boundary": 28656,
  "filter_b_gate_count_after_boundary": 28518,
  "segment_counts": {
    "DEV": 25862,
    "HOLD_B": 2656
  },
  "class_shares": {
    "DEV": {
      "SHORT": 0.45514654705745883,
      "NONE": 0.06712551233469956,
      "LONG": 0.47772794060784163
    },
    "HOLD_B": {
      "SHORT": 0.4642319277108434,
      "NONE": 0.06400602409638555,
      "LONG": 0.47176204819277107
    }
  },
  "feature_counts": {
    "f_": 201,
    "m_": 23,
    "trend_": 2,
    "ret_": 2
  },
  "registry_feature_names": [
    "return_1",
    "return_3",
    "return_5",
    "return_10",
    "return_15",
    "return_30",
    "return_45",
    "return_60",
    "log_return_1",
    "log_return_5",
    "momentum_10",
    "momentum_30",
    "rolling_return_max_20",
    "rolling_return_min_20",
    "close_sma_5_ratio",
    "close_sma_10_ratio",
    "close_sma_20_ratio",
    "close_sma_60_ratio",
    "close_ema_12_ratio",
    "close_ema_26_ratio",
    "ema_12_26_spread",
    "sma_5_20_spread",
    "sma_20_60_spread",
    "trend_slope_10",
    "trend_slope_30",
    "distance_to_high_20",
    "distance_to_low_20",
    "prev_horizon_trend",
    "rv_5",
    "rv_15",
    "rv_30",
    "rv_45",
    "rv_60",
    "rv_120",
    "atr_pct",
    "atr_pct_30",
    "atr_pct_45",
    "parkinson_vol_20",
    "garman_klass_vol_20",
    "range_vol_20",
    "har_rv_short",
    "har_rv_medium",
    "har_rv_long",
    "volume_sma_5_ratio",
    "volume_sma_20_ratio",
    "volume_sma_60_ratio",
    "quote_volume_sma_20_ratio",
    "taker_ratio",
    "taker_imbalance",
    "taker_quote_ratio",
    "trade_count_ratio",
    "trade_count_zscore_20",
    "volume_per_trade",
    "volume_shock_20",
    "high_low_range",
    "body_pct",
    "upper_shadow",
    "lower_shadow",
    "close_location_value",
    "wick_imbalance",
    "body_to_range",
    "range_sma_20_ratio",
    "inside_bar_flag",
    "outside_bar_flag",
    "gap_flag",
    "gap_ratio_20",
    "gap_ratio_60",
    "gap_ratio_120",
    "max_gap_run_120",
    "repaired_flag",
    "gap_length",
    "canonical_gap_pressure",
    "close_zscore_20",
    "close_zscore_60",
    "volume_zscore_5",
    "volume_zscore_20",
    "rv_zscore_60",
    "range_zscore_20",
    "volatility_regime_60",
    "volume_regime_60",
    "return_1_vol_adj",
    "return_5_vol_adj",
    "return_10_vol_adj",
    "return_30_vol_adj",
    "momentum_10_vol_adj",
    "momentum_30_vol_adj",
    "close_zscore_20_vol_adj",
    "close_zscore_60_vol_adj",
    "ema_spread_vol_adj",
    "sma_spread_vol_adj",
    "candle_range_vol_adj",
    "body_pct_vol_adj",
    "volume_zscore_20_vol_adj",
    "trade_count_zscore_20_vol_adj",
    "taker_imbalance_vol_adj",
    "adl_indicator",
    "funding_rate",
    "next_funding_rate",
    "minutes_to_next_funding",

## k45_gate_direction_audit_20261001

- 테스트 재실행 `tests/test_k45_gate_direction.py`: `12 passed in 1.73s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T02:16:05.271128+00:00 |
| run_finished_utc | 2026-10-01T02:39:14.832753+00:00 |
| runtime_seconds | 1389.561625 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | Audit whether the frozen PatchTST gate selects realized volatility and whether CatBoost long/short direction and label design explain economic results. |
| local_data_only | True |
| downloads | 0 |
| feature_cache_used | False |
| patchtst_new_fits | 0 |
| catboost_new_fits | 1242 |
| catboost_training_scope | C-4 regression RMSE and abs(r45)-weighted MultiClass only |
| catboost_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": -1, "verbose": false, "allow_writing_files": false} |
| walk_forward_folds | 621 |
| live_orders | 0 |
| source_inputs_unchanged | True |
| report_utf8_repaired_utc | 2026-10-01T02:43:27.501325+00:00 |

### out_of_sample_result (원문)

```text
"numbers_only_no_audit_verdict"
```

- 출력 해시 확인: 25/25 일치

## k45_gate_direction_r2_10_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_10.py`: `4 passed in 1.91s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T06:26:48.001743+00:00 |
| run_finished_utc | 2026-10-01T10:19:59.470917+00:00 |
| runtime_seconds | 13991.469174 |
| aggregation_runtime_seconds | 182.6386430999264 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 보유 시간에 맞춰 학습한 모델로 단일 포지션 한 방향 규칙을 쓰면 DEV와 HOLD_B net이 모두 0보다 크다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| catboost_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": -1, "verbose": false} |
| purge_rule | signal_index + h < stop_start_index |
| test_valid_rule | signal_index + h < test_end_index and signal_index + h < market_rows |
| residual_causal_margin | role/h target rate = DEV score > 0.20; fold k quantile uses pilot_fold < k; min_history=2000 |
| cost_bps | 4.0 |
| seed | 20261001 |
| random_repetitions | 1000 |
| local_data_only | True |
| downloads | 0 |
| patchtst_fits | 0 |
| live_orders | 0 |

### out_of_sample_result (원문)

```text
{
 "matched_cells": 91,
 "both_positive_cells": 8,
 "all_matched_cells_both_positive": false
}
```

- 출력 해시 확인: 85/85 일치

### REPORT.md 앞 150줄 (전체 6423줄, 원문)

# R2-10

## model_inventory

| model | arm | horizon | source | label_h | hold_h |
|---|---|---|---|---|---|
| R2-1 | LONG | 5 | trained | 5 | 5 |
| R2-1 | LONG | 15 | reused | 15 | 15 |
| R2-1 | LONG | 30 | trained | 30 | 30 |
| R2-1 | LONG | 45 | reused | 45 | 45 |
| R2-1 | LONG | 60 | reused | 60 | 60 |
| R2-1 | LONG | 90 | trained | 90 | 90 |
| R2-1 | LONG | 120 | trained | 120 | 120 |
| R2-1 | LONG | 240 | trained | 240 | 240 |
| R2-1 | SHORT | 5 | reused | 5 | 5 |
| R2-1 | SHORT | 15 | reused | 15 | 15 |
| R2-1 | SHORT | 30 | trained | 30 | 30 |
| R2-1 | SHORT | 45 | reused | 45 | 45 |
| R2-1 | SHORT | 60 | trained | 60 | 60 |
| R2-1 | SHORT | 90 | trained | 90 | 90 |
| R2-1 | SHORT | 120 | trained | 120 | 120 |
| R2-1 | SHORT | 240 | trained | 240 | 240 |
| RESIDUAL | BOTH | 5 | trained | 5 | 5 |
| RESIDUAL | BOTH | 15 | trained | 15 | 15 |
| RESIDUAL | BOTH | 45 | reused | 45 | 45 |
| RESIDUAL | BOTH | 60 | trained | 60 | 60 |
| RESIDUAL | BOTH | 120 | trained | 120 | 120 |
| RESIDUAL | BOTH | 240 | trained | 240 | 240 |

## model_fold_summary

| model | arm | horizon | source | folds | fitted_folds | train_min | train_max | test_total | test_valid | test_excluded |
|---|---|---|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27502 | 0 |
| R2-1 | LONG | 15 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 30 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27502 | 0 |
| R2-1 | LONG | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 60 | reused | 636 | 621 | 0 | 28474 | 28518 | 28455 | 63 |
| R2-1 | LONG | 90 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27306 | 196 |
| R2-1 | LONG | 120 | trained | 621 | 621 | 1016 | 28472 | 27502 | 27165 | 337 |
| R2-1 | LONG | 240 | trained | 621 | 621 | 1016 | 28469 | 27502 | 26304 | 1198 |
| R2-1 | SHORT | 5 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 15 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 30 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27502 | 0 |
| R2-1 | SHORT | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 60 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27440 | 62 |
| R2-1 | SHORT | 90 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27306 | 196 |
| R2-1 | SHORT | 120 | trained | 621 | 621 | 1016 | 28472 | 27502 | 27165 | 337 |
| R2-1 | SHORT | 240 | trained | 621 | 621 | 1016 | 28469 | 27502 | 26304 | 1198 |
| RESIDUAL | BOTH | 5 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27502 | 0 |
| RESIDUAL | BOTH | 15 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27502 | 0 |
| RESIDUAL | BOTH | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| RESIDUAL | BOTH | 60 | trained | 621 | 621 | 1016 | 28474 | 27502 | 27440 | 62 |
| RESIDUAL | BOTH | 120 | trained | 621 | 621 | 1016 | 28472 | 27502 | 27165 | 337 |
| RESIDUAL | BOTH | 240 | trained | 621 | 621 | 1016 | 28469 | 27502 | 26304 | 1198 |

## model_quality

| model | arm | horizon | segment | n | pooled_spearman | n_months | agree_months | p_one_sided |
|---|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | DEV | 24846 | 0.067642 | 58 | 55 | 0.000000 |
| R2-1 | LONG | 5 | HOLD_B | 2656 | 0.042441 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 15 | DEV | 24846 | 0.059606 | 58 | 51 | 0.000000 |
| R2-1 | LONG | 15 | HOLD_B | 2656 | 0.051786 | 6 | 6 | 0.015625 |
| R2-1 | LONG | 30 | DEV | 24846 | 0.048588 | 58 | 50 | 0.000000 |
| R2-1 | LONG | 30 | HOLD_B | 2656 | 0.019950 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 45 | DEV | 24846 | 0.034642 | 58 | 46 | 0.000004 |
| R2-1 | LONG | 45 | HOLD_B | 2656 | 0.031756 | 6 | 4 | 0.343750 |
| R2-1 | LONG | 60 | DEV | 24792 | 0.028213 | 58 | 42 | 0.000431 |
| R2-1 | LONG | 60 | HOLD_B | 2648 | 0.042121 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 90 | DEV | 24670 | 0.027477 | 58 | 41 | 0.001116 |
| R2-1 | LONG | 90 | HOLD_B | 2636 | 0.005840 | 6 | 4 | 0.343750 |
| R2-1 | LONG | 120 | DEV | 24538 | 0.005647 | 58 | 35 | 0.074003 |
| R2-1 | LONG | 120 | HOLD_B | 2627 | -0.034778 | 6 | 3 | 0.656250 |
| R2-1 | LONG | 240 | DEV | 23730 | -0.008102 | 58 | 23 | 0.956526 |
| R2-1 | LONG | 240 | HOLD_B | 2574 | -0.053852 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 5 | DEV | 24846 | 0.062716 | 58 | 51 | 0.000000 |
| R2-1 | SHORT | 5 | HOLD_B | 2656 | 0.049365 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 15 | DEV | 24846 | 0.049336 | 58 | 47 | 0.000001 |
| R2-1 | SHORT | 15 | HOLD_B | 2656 | 0.039137 | 6 | 4 | 0.343750 |
| R2-1 | SHORT | 30 | DEV | 24846 | 0.035400 | 58 | 49 | 0.000000 |
| R2-1 | SHORT | 30 | HOLD_B | 2656 | 0.029605 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 45 | DEV | 24846 | 0.027230 | 58 | 44 | 0.000050 |
| R2-1 | SHORT | 45 | HOLD_B | 2656 | 0.014872 | 6 | 4 | 0.343750 |
| R2-1 | SHORT | 60 | DEV | 24792 | 0.029647 | 58 | 44 | 0.000050 |
| R2-1 | SHORT | 60 | HOLD_B | 2648 | 0.026649 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 90 | DEV | 24670 | 0.022696 | 58 | 37 | 0.023970 |
| R2-1 | SHORT | 90 | HOLD_B | 2636 | -0.017836 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 120 | DEV | 24538 | 0.006320 | 58 | 35 | 0.074003 |
| R2-1 | SHORT | 120 | HOLD_B | 2627 | -0.022227 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 240 | DEV | 23730 | -0.011324 | 58 | 24 | 0.925997 |
| R2-1 | SHORT | 240 | HOLD_B | 2574 | -0.032582 | 6 | 3 | 0.656250 |
| RESIDUAL | BOTH | 5 | DEV | 24846 | 0.073532 | 58 | 52 | 0.000000 |
| RESIDUAL | BOTH | 5 | HOLD_B | 2656 | 0.042153 | 6 | 5 | 0.109375 |
| RESIDUAL | BOTH | 15 | DEV | 24846 | 0.067962 | 58 | 49 | 0.000000 |
| RESIDUAL | BOTH | 15 | HOLD_B | 2656 | 0.041055 | 6 | 6 | 0.015625 |
| RESIDUAL | BOTH | 45 | DEV | 24846 | 0.045526 | 58 | 47 | 0.000001 |
| RESIDUAL | BOTH | 45 | HOLD_B | 2656 | 0.013597 | 6 | 4 | 0.343750 |
| RESIDUAL | BOTH | 60 | DEV | 24792 | 0.041046 | 58 | 44 | 0.000050 |
| RESIDUAL | BOTH | 60 | HOLD_B | 2648 | 0.015553 | 6 | 5 | 0.109375 |
| RESIDUAL | BOTH | 120 | DEV | 24538 | 0.028945 | 58 | 39 | 0.005964 |
| RESIDUAL | BOTH | 120 | HOLD_B | 2627 | -0.032065 | 6 | 3 | 0.656250 |
| RESIDUAL | BOTH | 240 | DEV | 23730 | -0.014211 | 58 | 31 | 0.347002 |
| RESIDUAL | BOTH | 240 | HOLD_B | 2574 | -0.086179 | 6 | 4 | 0.343750 |

## model_deciles

| model | arm | horizon | segment | decile | n | score_mean | r_h_mean_bps |
|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | DEV | 1 | 2485 | 0.260524 | -2.075899 |
| R2-1 | LONG | 5 | DEV | 2 | 2485 | 0.320621 | -1.321544 |
| R2-1 | LONG | 5 | DEV | 3 | 2484 | 0.349838 | -0.735389 |
| R2-1 | LONG | 5 | DEV | 4 | 2485 | 0.372794 | -0.505408 |
| R2-1 | LONG | 5 | DEV | 5 | 2484 | 0.394401 | -1.242060 |
| R2-1 | LONG | 5 | DEV | 6 | 2485 | 0.416591 | -0.591643 |
| R2-1 | LONG | 5 | DEV | 7 | 2484 | 0.441833 | -1.272045 |
| R2-1 | LONG | 5 | DEV | 8 | 2485 | 0.471102 | 0.414680 |
| R2-1 | LONG | 5 | DEV | 9 | 2484 | 0.510284 | 0.257434 |
| R2-1 | LONG | 5 | DEV | 10 | 2485 | 0.601104 | 3.029294 |
| R2-1 | LONG | 5 | HOLD_B | 1 | 266 | 0.308551 | -0.478404 |
| R2-1 | LONG | 5 | HOLD_B | 2 | 266 | 0.347101 | -0.920011 |
| R2-1 | LONG | 5 | HOLD_B | 3 | 265 | 0.366826 | -1.792918 |
| R2-1 | LONG | 5 | HOLD_B | 4 | 266 | 0.382073 | 0.715731 |
| R2-1 | LONG | 5 | HOLD_B | 5 | 265 | 0.397564 | -0.427450 |
| R2-1 | LONG | 5 | HOLD_B | 6 | 266 | 0.412913 | 1.353568 |
| R2-1 | LONG | 5 | HOLD_B | 7 | 265 | 0.430607 | -1.379807 |
| R2-1 | LONG | 5 | HOLD_B | 8 | 266 | 0.452845 | 1.430377 |
| R2-1 | LONG | 5 | HOLD_B | 9 | 265 | 0.481994 | 1.197381 |
| R2-1 | LONG | 5 | HOLD_B | 10 | 266 | 0.540670 | 1.148733 |
| R2-1 | LONG | 15 | DEV | 1 | 2485 | 0.314118 | -2.119282 |
| R2-1 | LONG | 15 | DEV | 2 | 2485 | 0.377223 | 0.118518 |
| R2-1 | LONG | 15 | DEV | 3 | 2484 | 0.404682 | -1.115467 |
| R2-1 | LONG | 15 | DEV | 4 | 2485 | 0.426294 | -0.659447 |
| R2-1 | LONG | 15 | DEV | 5 | 2484 | 0.445679 | 1.854512 |
| R2-1 | LONG | 15 | DEV | 6 | 2485 | 0.465873 | 1.730609 |
| R2-1 | LONG | 15 | DEV | 7 | 2484 | 0.486484 | -0.453538 |
| R2-1 | LONG | 15 | DEV | 8 | 2485 | 0.510818 | 1.739808 |
| R2-1 | LONG | 15 | DEV | 9 | 2484 | 0.542631 | -0.854017 |
| R2-1 | LONG | 15 | DEV | 10 | 2485 | 0.621141 | 4.049154 |
| R2-1 | LONG | 15 | HOLD_B | 1 | 266 | 0.355480 | 0.237186 |
| R2-1 | LONG | 15 | HOLD_B | 2 | 266 | 0.390931 | 0.548546 |
| R2-1 | LONG | 15 | HOLD_B | 3 | 265 | 0.409752 | 0.315465 |
| R2-1 | LONG | 15 | HOLD_B | 4 | 266 | 0.426026 | -2.651268 |
| R2-1 | LONG | 15 | HOLD_B | 5 | 265 | 0.441799 | 3.531368 |
| R2-1 | LONG | 15 | HOLD_B | 6 | 266 | 0.457112 | -4.161772 |
| R2-1 | LONG | 15 | HOLD_B | 7 | 265 | 0.474376 | -1.964663 |
| R2-1 | LONG | 15 | HOLD_B | 8 | 266 | 0.495037 | 3.742503 |
| R2-1 | LONG | 15 | HOLD_B | 9 | 265 | 0.519102 | 4.368997 |
| R2-1 | LONG | 15 | HOLD_B | 10 | 266 | 0.566894 | 1.284972 |
| R2-1 | LONG | 30 | DEV | 1 | 2485 | 0.330747 | 0.457331 |

## k45_gate_direction_r2_10b_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_10.py`: `4 passed in 1.91s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T10:23:56.839896+00:00 |
| run_finished_utc | 2026-10-01T11:19:53.169840+00:00 |
| runtime_seconds | 3356.329944 |
| aggregation_runtime_seconds | 246.7790576997213 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 보유 시간에 맞춰 학습한 모델로 단일 포지션 한 방향 규칙을 쓰면 DEV와 HOLD_B net이 모두 0보다 크다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| catboost_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": -1, "verbose": false} |
| purge_rule | signal_index + h < stop_start_index |
| test_valid_rule | signal_index + h < test_end_index and signal_index + h < market_rows |
| residual_causal_margin | role/h target rate = DEV score > 0.20; fold k quantile uses pilot_fold < k; min_history=2000 |
| cost_bps | 4.0 |
| seed | 20261001 |
| random_repetitions | 1000 |
| local_data_only | True |
| downloads | 0 |
| patchtst_fits | 0 |
| live_orders | 0 |

### out_of_sample_result (원문)

```text
{
 "matched_cells": 117,
 "both_positive_cells": 11,
 "all_matched_cells_both_positive": false
}
```

- 출력 해시 확인: 81/81 일치

### REPORT.md 앞 150줄 (전체 7636줄, 원문)

# R2-10b

## model_inventory

| model | arm | horizon | source | label_h | hold_h |
|---|---|---|---|---|---|
| R2-1 | LONG | 5 | reused | 5 | 5 |
| R2-1 | LONG | 15 | reused | 15 | 15 |
| R2-1 | LONG | 30 | reused | 30 | 30 |
| R2-1 | LONG | 45 | reused | 45 | 45 |
| R2-1 | LONG | 60 | reused | 60 | 60 |
| R2-1 | LONG | 90 | reused | 90 | 90 |
| R2-1 | LONG | 120 | reused | 120 | 120 |
| R2-1 | LONG | 180 | trained | 180 | 180 |
| R2-1 | LONG | 240 | reused | 240 | 240 |
| R2-1 | SHORT | 5 | reused | 5 | 5 |
| R2-1 | SHORT | 15 | reused | 15 | 15 |
| R2-1 | SHORT | 30 | reused | 30 | 30 |
| R2-1 | SHORT | 45 | reused | 45 | 45 |
| R2-1 | SHORT | 60 | reused | 60 | 60 |
| R2-1 | SHORT | 90 | reused | 90 | 90 |
| R2-1 | SHORT | 120 | reused | 120 | 120 |
| R2-1 | SHORT | 180 | trained | 180 | 180 |
| R2-1 | SHORT | 240 | reused | 240 | 240 |
| RESIDUAL | BOTH | 5 | reused | 5 | 5 |
| RESIDUAL | BOTH | 15 | reused | 15 | 15 |
| RESIDUAL | BOTH | 45 | reused | 45 | 45 |
| RESIDUAL | BOTH | 60 | reused | 60 | 60 |
| RESIDUAL | BOTH | 120 | reused | 120 | 120 |
| RESIDUAL | BOTH | 180 | trained | 180 | 180 |
| RESIDUAL | BOTH | 240 | reused | 240 | 240 |

## model_fold_summary

| model | arm | horizon | source | folds | fitted_folds | train_min | train_max | test_total | test_valid | test_excluded |
|---|---|---|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 15 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 30 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | LONG | 60 | reused | 636 | 621 | 0 | 28474 | 28518 | 28455 | 63 |
| R2-1 | LONG | 90 | reused | 636 | 621 | 0 | 28474 | 28518 | 28319 | 199 |
| R2-1 | LONG | 120 | reused | 636 | 621 | 0 | 28472 | 28518 | 28174 | 344 |
| R2-1 | LONG | 180 | trained | 621 | 621 | 1016 | 28472 | 27502 | 26789 | 713 |
| R2-1 | LONG | 240 | reused | 636 | 621 | 0 | 28469 | 28518 | 27295 | 1223 |
| R2-1 | SHORT | 5 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 15 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 30 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| R2-1 | SHORT | 60 | reused | 636 | 621 | 0 | 28474 | 28518 | 28455 | 63 |
| R2-1 | SHORT | 90 | reused | 636 | 621 | 0 | 28474 | 28518 | 28319 | 199 |
| R2-1 | SHORT | 120 | reused | 636 | 621 | 0 | 28472 | 28518 | 28174 | 344 |
| R2-1 | SHORT | 180 | trained | 621 | 621 | 1016 | 28472 | 27502 | 26789 | 713 |
| R2-1 | SHORT | 240 | reused | 636 | 621 | 0 | 28469 | 28518 | 27295 | 1223 |
| RESIDUAL | BOTH | 5 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| RESIDUAL | BOTH | 15 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| RESIDUAL | BOTH | 45 | reused | 636 | 621 | 0 | 28474 | 28518 | 28518 | 0 |
| RESIDUAL | BOTH | 60 | reused | 636 | 621 | 0 | 28474 | 28518 | 28455 | 63 |
| RESIDUAL | BOTH | 120 | reused | 636 | 621 | 0 | 28472 | 28518 | 28174 | 344 |
| RESIDUAL | BOTH | 180 | trained | 621 | 621 | 1016 | 28472 | 27502 | 26789 | 713 |
| RESIDUAL | BOTH | 240 | reused | 636 | 621 | 0 | 28469 | 28518 | 27295 | 1223 |

## model_quality

| model | arm | horizon | segment | n | pooled_spearman | n_months | agree_months | p_one_sided |
|---|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | DEV | 24846 | 0.067642 | 58 | 55 | 0.000000 |
| R2-1 | LONG | 5 | HOLD_B | 2656 | 0.042441 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 15 | DEV | 24846 | 0.059606 | 58 | 51 | 0.000000 |
| R2-1 | LONG | 15 | HOLD_B | 2656 | 0.051786 | 6 | 6 | 0.015625 |
| R2-1 | LONG | 30 | DEV | 24846 | 0.048588 | 58 | 50 | 0.000000 |
| R2-1 | LONG | 30 | HOLD_B | 2656 | 0.019950 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 45 | DEV | 24846 | 0.034642 | 58 | 46 | 0.000004 |
| R2-1 | LONG | 45 | HOLD_B | 2656 | 0.031756 | 6 | 4 | 0.343750 |
| R2-1 | LONG | 60 | DEV | 24792 | 0.028213 | 58 | 42 | 0.000431 |
| R2-1 | LONG | 60 | HOLD_B | 2648 | 0.042121 | 6 | 5 | 0.109375 |
| R2-1 | LONG | 90 | DEV | 24670 | 0.027477 | 58 | 41 | 0.001116 |
| R2-1 | LONG | 90 | HOLD_B | 2636 | 0.005840 | 6 | 4 | 0.343750 |
| R2-1 | LONG | 120 | DEV | 24538 | 0.005647 | 58 | 35 | 0.074003 |
| R2-1 | LONG | 120 | HOLD_B | 2627 | -0.034778 | 6 | 3 | 0.656250 |
| R2-1 | LONG | 180 | DEV | 24182 | 0.022656 | 58 | 34 | 0.118524 |
| R2-1 | LONG | 180 | HOLD_B | 2607 | -0.002641 | 6 | 2 | 0.890625 |
| R2-1 | LONG | 240 | DEV | 23730 | -0.008102 | 58 | 23 | 0.956526 |
| R2-1 | LONG | 240 | HOLD_B | 2574 | -0.053852 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 5 | DEV | 24846 | 0.062716 | 58 | 51 | 0.000000 |
| R2-1 | SHORT | 5 | HOLD_B | 2656 | 0.049365 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 15 | DEV | 24846 | 0.049336 | 58 | 47 | 0.000001 |
| R2-1 | SHORT | 15 | HOLD_B | 2656 | 0.039137 | 6 | 4 | 0.343750 |
| R2-1 | SHORT | 30 | DEV | 24846 | 0.035400 | 58 | 49 | 0.000000 |
| R2-1 | SHORT | 30 | HOLD_B | 2656 | 0.029605 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 45 | DEV | 24846 | 0.027230 | 58 | 44 | 0.000050 |
| R2-1 | SHORT | 45 | HOLD_B | 2656 | 0.014872 | 6 | 4 | 0.343750 |
| R2-1 | SHORT | 60 | DEV | 24792 | 0.029647 | 58 | 44 | 0.000050 |
| R2-1 | SHORT | 60 | HOLD_B | 2648 | 0.026649 | 6 | 5 | 0.109375 |
| R2-1 | SHORT | 90 | DEV | 24670 | 0.022696 | 58 | 37 | 0.023970 |
| R2-1 | SHORT | 90 | HOLD_B | 2636 | -0.017836 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 120 | DEV | 24538 | 0.006320 | 58 | 35 | 0.074003 |
| R2-1 | SHORT | 120 | HOLD_B | 2627 | -0.022227 | 6 | 3 | 0.656250 |
| R2-1 | SHORT | 180 | DEV | 24182 | 0.023076 | 58 | 35 | 0.074003 |
| R2-1 | SHORT | 180 | HOLD_B | 2607 | -0.012014 | 6 | 2 | 0.890625 |
| R2-1 | SHORT | 240 | DEV | 23730 | -0.011324 | 58 | 24 | 0.925997 |
| R2-1 | SHORT | 240 | HOLD_B | 2574 | -0.032582 | 6 | 3 | 0.656250 |
| RESIDUAL | BOTH | 5 | DEV | 24846 | 0.073532 | 58 | 52 | 0.000000 |
| RESIDUAL | BOTH | 5 | HOLD_B | 2656 | 0.042153 | 6 | 5 | 0.109375 |
| RESIDUAL | BOTH | 15 | DEV | 24846 | 0.067962 | 58 | 49 | 0.000000 |
| RESIDUAL | BOTH | 15 | HOLD_B | 2656 | 0.041055 | 6 | 6 | 0.015625 |
| RESIDUAL | BOTH | 45 | DEV | 24846 | 0.045526 | 58 | 47 | 0.000001 |
| RESIDUAL | BOTH | 45 | HOLD_B | 2656 | 0.013597 | 6 | 4 | 0.343750 |
| RESIDUAL | BOTH | 60 | DEV | 24792 | 0.041046 | 58 | 44 | 0.000050 |
| RESIDUAL | BOTH | 60 | HOLD_B | 2648 | 0.015553 | 6 | 5 | 0.109375 |
| RESIDUAL | BOTH | 120 | DEV | 24538 | 0.028945 | 58 | 39 | 0.005964 |
| RESIDUAL | BOTH | 120 | HOLD_B | 2627 | -0.032065 | 6 | 3 | 0.656250 |
| RESIDUAL | BOTH | 180 | DEV | 24182 | 0.030313 | 58 | 38 | 0.012373 |
| RESIDUAL | BOTH | 180 | HOLD_B | 2607 | -0.034998 | 6 | 2 | 0.890625 |
| RESIDUAL | BOTH | 240 | DEV | 23730 | -0.014211 | 58 | 31 | 0.347002 |
| RESIDUAL | BOTH | 240 | HOLD_B | 2574 | -0.086179 | 6 | 4 | 0.343750 |

## model_deciles

| model | arm | horizon | segment | decile | n | score_mean | r_h_mean_bps |
|---|---|---|---|---|---|---|---|
| R2-1 | LONG | 5 | DEV | 1 | 2485 | 0.260524 | -2.075899 |
| R2-1 | LONG | 5 | DEV | 2 | 2485 | 0.320621 | -1.321544 |
| R2-1 | LONG | 5 | DEV | 3 | 2484 | 0.349838 | -0.735389 |
| R2-1 | LONG | 5 | DEV | 4 | 2485 | 0.372794 | -0.505408 |
| R2-1 | LONG | 5 | DEV | 5 | 2484 | 0.394401 | -1.242060 |
| R2-1 | LONG | 5 | DEV | 6 | 2485 | 0.416591 | -0.591643 |
| R2-1 | LONG | 5 | DEV | 7 | 2484 | 0.441833 | -1.272045 |
| R2-1 | LONG | 5 | DEV | 8 | 2485 | 0.471102 | 0.414680 |
| R2-1 | LONG | 5 | DEV | 9 | 2484 | 0.510284 | 0.257434 |
| R2-1 | LONG | 5 | DEV | 10 | 2485 | 0.601104 | 3.029294 |
| R2-1 | LONG | 5 | HOLD_B | 1 | 266 | 0.308551 | -0.478404 |
| R2-1 | LONG | 5 | HOLD_B | 2 | 266 | 0.347101 | -0.920011 |
| R2-1 | LONG | 5 | HOLD_B | 3 | 265 | 0.366826 | -1.792918 |
| R2-1 | LONG | 5 | HOLD_B | 4 | 266 | 0.382073 | 0.715731 |
| R2-1 | LONG | 5 | HOLD_B | 5 | 265 | 0.397564 | -0.427450 |
| R2-1 | LONG | 5 | HOLD_B | 6 | 266 | 0.412913 | 1.353568 |
| R2-1 | LONG | 5 | HOLD_B | 7 | 265 | 0.430607 | -1.379807 |
| R2-1 | LONG | 5 | HOLD_B | 8 | 266 | 0.452845 | 1.430377 |
| R2-1 | LONG | 5 | HOLD_B | 9 | 265 | 0.481994 | 1.197381 |
| R2-1 | LONG | 5 | HOLD_B | 10 | 266 | 0.540670 | 1.148733 |
| R2-1 | LONG | 15 | DEV | 1 | 2485 | 0.314118 | -2.119282 |
| R2-1 | LONG | 15 | DEV | 2 | 2485 | 0.377223 | 0.118518 |
| R2-1 | LONG | 15 | DEV | 3 | 2484 | 0.404682 | -1.115467 |
| R2-1 | LONG | 15 | DEV | 4 | 2485 | 0.426294 | -0.659447 |
| R2-1 | LONG | 15 | DEV | 5 | 2484 | 0.445679 | 1.854512 |
| R2-1 | LONG | 15 | DEV | 6 | 2485 | 0.465873 | 1.730609 |
| R2-1 | LONG | 15 | DEV | 7 | 2484 | 0.486484 | -0.453538 |
| R2-1 | LONG | 15 | DEV | 8 | 2485 | 0.510818 | 1.739808 |
| R2-1 | LONG | 15 | DEV | 9 | 2484 | 0.542631 | -0.854017 |

## k45_gate_direction_r2_11_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_11.py`: `4 passed in 1.87s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T14:19:23.737801+00:00 |
| run_finished_utc | 2026-10-01T22:06:02.530736+00:00 |
| runtime_seconds | 27998.792935 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | STOP 구간으로 fold마다 튜닝하면 고정 파라미터보다 확률 품질과 단일 포지션 net이 모두 높다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| train_rule | signal_index + h < stop_start_index |
| validation_rule | stop_start_index <= signal_index and signal_index + h < test_start_index |
| validation_min_rows | 30 |
| grid | {"depth": [4, 6], "learning_rate": [0.03, 0.1], "l2_leaf_reg": [3, 10]} |
| iterations_max | 2000 |
| early_stopping_rounds | 100 |
| fallback | {"depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "iterations": 500} |
| seed | 20261001 |
| device | CPU |
| model_refit_after_selection | False |
| tail_cell_count_per_version | 516 |
| single_position_max_positions | 1 |
| random_repetitions | 1000 |
| cost_bps | 4.0 |
| local_data_only | True |
| downloads | 0 |
| patchtst_fits | 0 |
| live_orders | 0 |

### out_of_sample_result (원문)

```text
{
 "quality_mean_spearman_delta_DEV": -0.0023298950942198583,
 "quality_mean_spearman_delta_HOLD_B": -0.0028756384717150262,
 "single_grid_mean_net_delta_DEV": -0.3062224355502492,
 "single_grid_mean_net_delta_HOLD_B": -1.7831141482887234,
 "hypothesis_all_four_positive": false
}
```

- 출력 해시 확인: 156/156 일치

### REPORT.md 앞 150줄 (전체 98064줄, 원문)

# R2-11

## UTC

| started | finished | cutoff | seed | cost_bps |
|---|---|---|---|---|
| 2026-10-01T14:19:23.737801+00:00 | 2026-10-01T22:06:02.530736+00:00 | 2026-06-30T23:59:00+00:00 | 20261001 | 4.000000 |

## SINGLE_POSITION_FIXED_TUNED_DEV_HOLD_B

| rule | h_long | h_short | segment | n_fixed | n_tuned | net_mean_bps_fixed | net_mean_bps_tuned | net_sum_bps_fixed | net_sum_bps_tuned | trim_top1_net_mean_bps_fixed | trim_top1_net_mean_bps_tuned | trim_top2_net_mean_bps_fixed | trim_top2_net_mean_bps_tuned | trim_top5_net_mean_bps_fixed | trim_top5_net_mean_bps_tuned | direction_hit_rate_fixed | direction_hit_rate_tuned | pw_ci95_lower_fixed | pw_ci95_lower_tuned | pw_ci95_upper_fixed | pw_ci95_upper_tuned | monthly_positive_share_fixed | monthly_positive_share_tuned | funding_total_bps_fixed | funding_total_bps_tuned | n_delta | net_mean_bps_delta | net_sum_bps_delta | trim_top1_net_mean_bps_delta | trim_top2_net_mean_bps_delta | trim_top5_net_mean_bps_delta | direction_hit_rate_delta | pw_ci95_lower_delta | pw_ci95_upper_delta | monthly_positive_share_delta | funding_total_bps_delta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2_1_MATCHED | 5 | 5 | DEV | 7162.000000 | 6947.000000 | -1.612556 | -1.491151 | -11549.124036 | -10359.023964 | -1.682811 | -1.563563 | -1.744183 | -1.626818 | -1.887634 | -1.774661 | 0.553756 | 0.556499 | -2.592457 | -2.441249 | -0.658739 | -0.550390 | 0.327586 | 0.275862 | 5.320200 | -12.309900 | -215.000000 | 0.121405 | 1190.100072 | 0.119248 | 0.117365 | 0.112973 | 0.002743 | 0.151208 | 0.108349 | -0.051724 | -17.630100 |
| R2_1_MATCHED | 5 | 5 | HOLD_B | 302.000000 | 259.000000 | -0.658211 | 0.277598 | -198.779837 | 71.897799 | -1.048922 | -0.092467 | -1.406047 | -0.360147 | -2.335285 | -1.150899 | 0.559603 | 0.590734 | -3.159315 | -2.137385 | 1.836967 | 2.839264 | 0.333333 | 0.500000 | 0.127200 | 0.555100 | -43.000000 | 0.935809 | 270.677636 | 0.956455 | 1.045900 | 1.184386 | 0.031131 | 1.021930 | 1.002297 | 0.166667 | 0.427900 |
| R2_1_MATCHED | 5 | 15 | DEV | 7681.000000 | 7542.000000 | -3.039368 | -2.937244 | -23345.382434 | -22152.696244 | -3.124402 | -3.023833 | -3.181814 | -3.082290 | -3.325345 | -3.230852 | 0.544200 | 0.545081 | -4.149067 | -4.066471 | -1.952753 | -1.772320 | 0.172414 | 0.189655 | -56.635500 | -77.514000 | -139.000000 | 0.102123 | 1192.686190 | 0.100569 | 0.099524 | 0.094493 | 0.000881 | 0.082597 | 0.180433 | 0.017241 | -20.878500 |
| R2_1_MATCHED | 5 | 15 | HOLD_B | 454.000000 | 382.000000 | -0.863962 | -2.014274 | -392.238953 | -769.452507 | -1.264525 | -2.302992 | -1.607162 | -2.561038 | -2.475865 | -3.241505 | 0.528634 | 0.547120 | -3.819665 | -5.006141 | 2.174408 | 1.011407 | 0.666667 | 0.333333 | 1.925900 | 0.414500 | -72.000000 | -1.150311 | -377.213553 | -1.038467 | -0.953876 | -0.765640 | 0.018486 | -1.186477 | -1.163001 | -0.333333 | -1.511400 |
| R2_1_MATCHED | 5 | 30 | DEV | 6964.000000 | 6901.000000 | -3.274881 | -3.288397 | -22806.270734 | -22693.225967 | -3.415880 | -3.430686 | -3.550390 | -3.566426 | -3.753887 | -3.807894 | 0.538914 | 0.536009 | -4.821976 | nan | -1.744736 | nan | 0.241379 | 0.258621 | -152.460400 | -178.797100 | -63.000000 | -0.013516 | 113.044767 | -0.014805 | -0.016036 | -0.054007 | -0.002905 | nan | nan | 0.017241 | -26.336700 |
| R2_1_MATCHED | 5 | 30 | HOLD_B | 454.000000 | 385.000000 | -4.319115 | 0.438364 | -1960.878338 | 168.770101 | -4.753272 | -0.146631 | -5.113625 | -0.668965 | -6.086652 | -1.933590 | 0.513216 | 0.548052 | -8.620243 | nan | 0.270975 | nan | 0.000000 | 0.500000 | -3.787000 | -0.312500 | -69.000000 | 4.757479 | 2129.648439 | 4.606641 | 4.444660 | 4.153061 | 0.034836 | nan | nan | 0.500000 | 3.474500 |
| R2_1_MATCHED | 5 | 45 | DEV | 6588.000000 | 6537.000000 | -2.716710 | -3.303993 | -17897.687112 | -21598.201740 | -2.955209 | -3.544442 | -3.038614 | -3.650694 | -3.257497 | -3.888195 | 0.540225 | 0.532201 | -4.329873 | nan | -1.145419 | nan | 0.293103 | 0.275862 | -276.067200 | -248.358300 | -51.000000 | -0.587283 | -3700.514628 | -0.589234 | -0.612080 | -0.630698 | -0.008023 | nan | nan | -0.017241 | 27.708900 |
| R2_1_MATCHED | 5 | 45 | HOLD_B | 473.000000 | 423.000000 | -2.711543 | -4.210297 | -1282.559661 | -1780.955453 | -3.251079 | -4.683041 | -3.717555 | -5.096010 | -4.979798 | -6.203397 | 0.530655 | 0.534279 | -6.930195 | -9.458162 | 1.648780 | 1.217270 | 0.166667 | 0.000000 | -3.859700 | -2.242800 | -50.000000 | -1.498754 | -498.395792 | -1.431962 | -1.378455 | -1.223598 | 0.003624 | -2.527966 | -0.431509 | -0.166667 | 1.616900 |
| R2_1_MATCHED | 5 | 60 | DEV | 6233.000000 | 6134.000000 | -3.385973 | -2.742200 | -21104.768696 | -16820.656325 | -3.530967 | -2.872793 | -3.659632 | -2.963636 | -3.901378 | -3.207432 | 0.532649 | 0.533583 | -5.163448 | -4.480797 | -1.614706 | -1.028953 | 0.344828 | 0.310345 | -398.249500 | -424.462100 | -99.000000 | 0.643773 | 4284.112371 | 0.658174 | 0.695996 | 0.693946 | 0.000935 | 0.682652 | 0.585753 | -0.034483 | -26.212600 |
| R2_1_MATCHED | 5 | 60 | HOLD_B | 458.000000 | 425.000000 | -3.757399 | -1.760060 | -1720.888543 | -748.025547 | -4.751024 | -2.826309 | -5.156450 | -3.446141 | -6.309986 | -4.719999 | 0.521834 | 0.536471 | -9.102279 | -7.791639 | 1.344006 | 4.535111 | 0.166667 | 0.333333 | -2.369400 | 3.240500 | -33.000000 | 1.997338 | 972.862996 | 1.924715 | 1.710309 | 1.589987 | 0.014637 | 1.310639 | 3.191105 | 0.166667 | 5.609900 |
| R2_1_MATCHED | 5 | 90 | DEV | 5403.000000 | 5431.000000 | -3.449131 | -4.881350 | -18635.653504 | -26510.610215 | -3.676008 | -5.107321 | -3.814633 | -5.215902 | -4.133373 | -5.504196 | 0.534703 | 0.528448 | -5.888815 | -7.148205 | -1.072203 | -2.551513 | 0.275862 | 0.293103 | -427.049600 | -420.970100 | 28.000000 | -1.432219 | -7874.956711 | -1.431313 | -1.401270 | -1.370823 | -0.006255 | -1.259390 | -1.479310 | 0.017241 | 6.079500 |
| R2_1_MATCHED | 5 | 90 | HOLD_B | 373.000000 | 321.000000 | -2.506955 | -1.257008 | -935.094106 | -403.499532 | -3.763197 | -2.713484 | -4.756739 | -3.747275 | -6.861976 | -5.957545 | 0.509383 | 0.554517 | -8.954822 | -10.013083 | 3.884766 | 7.722121 | 0.500000 | 0.500000 | -8.901200 | -4.694300 | -52.000000 | 1.249947 | 531.594574 | 1.049713 | 1.009464 | 0.904431 | 0.045134 | -1.058261 | 3.837355 | 0.000000 | 4.206900 |
| R2_1_MATCHED | 5 | 120 | DEV | 4966.000000 | 4937.000000 | -4.445687 | -4.623364 | -22077.283192 | -22825.547847 | -4.582585 | -4.761102 | -4.716142 | -4.895480 | -5.091613 | -5.278412 | 0.528594 | 0.519546 | -7.065613 | -7.303764 | -1.821281 | -1.921275 | 0.310345 | 0.310345 | -526.562500 | -537.090900 | -29.000000 | -0.177677 | -748.264655 | -0.178517 | -0.179338 | -0.186799 | -0.009048 | -0.238151 | -0.099994 | 0.000000 | -10.528400 |
| R2_1_MATCHED | 5 | 120 | HOLD_B | 368.000000 | 333.000000 | -3.719801 | -4.912285 | -1368.886790 | -1635.790782 | -4.697570 | -5.773749 | -5.432010 | -6.512411 | -7.469340 | -8.433965 | 0.540761 | 0.552553 | -11.198707 | -13.022557 | 3.729678 | 3.331596 | 0.333333 | 0.166667 | -6.570500 | -4.687600 | -35.000000 | -1.192484 | -266.903992 | -1.076179 | -1.080401 | -0.964625 | 0.011792 | -1.823850 | -0.398082 | -0.166667 | 1.882900 |
| R2_1_MATCHED | 5 | 180 | DEV | 4186.000000 | 4201.000000 | -4.304307 | -3.601275 | -18017.827908 | -15128.954668 | -4.521661 | -3.817685 | -4.717116 | -3.997161 | -5.191025 | -4.447157 | 0.525800 | 0.524161 | nan | -6.387387 | nan | -0.709708 | 0.275862 | 0.344828 | -491.057900 | -505.199600 | 15.000000 | 0.703032 | 2888.873239 | 0.703976 | 0.719955 | 0.743868 | -0.001639 | nan | nan | 0.068966 | -14.141700 |
| R2_1_MATCHED | 5 | 180 | HOLD_B | 307.000000 | 272.000000 | -4.348480 | -1.113000 | -1334.983340 | -302.736079 | -5.839292 | -2.860904 | -7.050486 | -4.544982 | -10.027653 | -8.285819 | 0.534202 | 0.536765 | -16.700773 | -15.452231 | 6.449922 | 10.908689 | 0.166667 | 0.166667 | -5.321400 | -0.680200 | -35.000000 | 3.235480 | 1032.247261 | 2.978388 | 2.505505 | 1.741834 | 0.002563 | 1.248542 | 4.458768 | 0.000000 | 4.641200 |
| R2_1_MATCHED | 5 | 240 | DEV | 3856.000000 | 3861.000000 | -5.463184 | -5.004892 | -21066.038960 | -19323.888300 | -5.671195 | -5.212515 | -5.856322 | -5.397283 | -6.377313 | -5.892053 | 0.524378 | 0.527325 | nan | -8.458218 | nan | -1.543540 | 0.344828 | 0.362069 | -705.769600 | -694.040000 | 5.000000 | 0.458292 | 1742.150659 | 0.458680 | 0.459039 | 0.485260 | 0.002947 | nan | nan | 0.017241 | 11.729600 |
| R2_1_MATCHED | 5 | 240 | HOLD_B | 255.000000 | 239.000000 | -8.193150 | -7.174111 | -2089.253144 | -1714.612581 | -9.644850 | -10.026197 | -11.000621 | -11.307317 | -13.863873 | -14.158028 | 0.494118 | 0.506276 | -18.952309 | -18.904235 | 2.734290 | 4.558394 | 0.166667 | 0.166667 | -5.666800 | -1.406400 | -16.000000 | 1.019038 | 374.640563 | -0.381346 | -0.306695 | -0.294156 | 0.012159 | 0.048074 | 1.824104 | 0.000000 | 4.260400 |
| R2_1_MATCHED | 15 | 5 | DEV | 9591.000000 | 9080.000000 | -1.768261 | -1.365507 | -16959.395374 | -12398.804432 | -1.845751 | -1.420893 | -1.898242 | -1.475636 | -2.036344 | -1.618943 | 0.550099 | 0.554626 | -2.726703 | nan | -0.787249 | nan | 0.344828 | 0.293103 | 169.096600 | 153.331900 | -511.000000 | 0.402754 | 4560.590942 | 0.424858 | 0.422605 | 0.417401 | 0.004526 | nan | nan | -0.051724 | -15.764700 |
| R2_1_MATCHED | 15 | 5 | HOLD_B | 626.000000 | 606.000000 | -1.378414 | -3.246629 | -862.886938 | -1967.456871 | -1.589294 | -3.729039 | -1.785605 | -4.046713 | -2.303396 | -4.829600 | 0.579872 | 0.569307 | -3.890118 | -6.596937 | 1.245596 | 0.402620 | 0.333333 | 0.333333 | -0.265800 | 2.208600 | -20.000000 | -1.868215 | -1104.569934 | -2.139744 | -2.261108 | -2.526204 | -0.010565 | -2.706819 | -0.842976 | 0.000000 | 2.474400 |
| R2_1_MATCHED | 15 | 15 | DEV | 10607.000000 | 10078.000000 | -3.137680 | -2.858974 | -33281.372767 | -28812.743201 | -3.207876 | -2.923764 | -3.269473 | -2.973234 | -3.395412 | -3.103508 | 0.541246 | 0.542766 | -4.242851 | -3.906634 | -1.987016 | -1.788868 | 0.241379 | 0.224138 | 100.269800 | 79.009400 | -529.000000 | 0.278706 | 4468.629566 | 0.284112 | 0.296238 | 0.291904 | 0.001520 | 0.336218 | 0.198148 | -0.017241 | -21.260400 |
| R2_1_MATCHED | 15 | 15 | HOLD_B | 787.000000 | 738.000000 | -1.193100 | -3.934749 | -938.969366 | -2903.844798 | -1.424377 | -4.331691 | -1.621870 | -4.593210 | -2.137941 | -5.237350 | 0.556544 | 0.547425 | -3.742046 | -6.581832 | 1.431561 | -1.039397 | 0.500000 | 0.166667 | 1.532900 | 2.068000 | -49.000000 | -2.741649 | -1964.875432 | -2.907314 | -2.971341 | -3.099408 | -0.009118 | -2.839786 | -2.470958 | -0.333333 | 0.535100 |
| R2_1_MATCHED | 15 | 30 | DEV | 9358.000000 | 8973.000000 | -3.117849 | -2.981131 | -29176.828733 | -26749.687489 | -3.222757 | -3.090525 | -3.302340 | -3.162070 | -3.459850 | -3.331646 | 0.537615 | 0.539173 | -4.485796 | -4.328757 | -1.753846 | -1.641560 | 0.155172 | 0.258621 | -0.899000 | -5.994000 | -385.000000 | 0.136718 | 2427.141243 | 0.132231 | 0.140269 | 0.128204 | 0.001558 | 0.157038 | 0.112287 | 0.103448 | -5.095000 |
| R2_1_MATCHED | 15 | 30 | HOLD_B | 773.000000 | 727.000000 | -3.467131 | -2.800460 | -2680.092216 | -2035.934538 | -3.720785 | -3.201854 | -3.930703 | -3.482004 | -4.495224 | -4.243880 | 0.545925 | 0.547455 | -6.237816 | -5.821586 | -0.472349 | 0.447871 | 0.000000 | 0.333333 | -4.180000 | 1.341000 | -46.000000 | 0.666671 | 644.157678 | 0.518931 | 0.448699 | 0.251343 | 0.001530 | 0.416230 | 0.920220 | 0.333333 | 5.521000 |
| R2_1_MATCHED | 15 | 45 | DEV | 8763.000000 | 8442.000000 | -2.961346 | -2.869089 | -25950.271524 | -24220.847010 | -3.140669 | -3.055221 | -3.225648 | -3.120317 | -3.407549 | -3.300462 | 0.538058 | 0.536840 | -4.608853 | -4.438555 | -1.350062 | -1.385573 | 0.258621 | 0.224138 | -107.981700 | -63.052300 | -321.000000 | 0.092257 | 1729.424514 | 0.085448 | 0.105331 | 0.107087 | -0.001218 | 0.170298 | -0.035512 | -0.034483 | 44.929400 |
| R2_1_MATCHED | 15 | 45 | HOLD_B | 760.000000 | 741.000000 | -2.954763 | -4.915258 | -2245.619517 | -3642.206065 | -3.290605 | -5.311916 | -3.580512 | -5.583363 | -4.362391 | -6.314806 | 0.557895 | 0.546559 | -6.437647 | -8.579577 | 0.633925 | -1.072178 | 0.333333 | 0.166667 | -2.575000 | -0.662100 | -19.000000 | -1.960495 | -1396.586548 | -2.021311 | -2.002851 | -1.952415 | -0.011336 | -2.141930 | -1.706103 | -0.166667 | 1.912900 |
| R2_1_MATCHED | 15 | 60 | DEV | 8186.000000 | 7858.000000 | -3.412216 | -2.914406 | -27932.398998 | -22901.401716 | -3.522617 | -3.016365 | -3.620577 | -3.087291 | -3.841295 | -3.277613 | 0.536404 | 0.539068 | -4.899626 | -4.500391 | -1.896983 | -1.342303 | 0.275862 | 0.275862 | -244.116800 | -302.004600 | -328.000000 | 0.497810 | 5030.997282 | 0.506251 | 0.533285 | 0.563682 | 0.002665 | 0.399235 | 0.554680 | 0.000000 | -57.887800 |
| R2_1_MATCHED | 15 | 60 | HOLD_B | 728.000000 | 708.000000 | -1.985815 | -2.320637 | -1445.673419 | -1643.011208 | -2.887196 | -2.960878 | -3.511461 | -3.373870 | -4.253622 | -4.281058 | 0.557692 | 0.549435 | -5.379346 | -5.733818 | 1.383949 | 1.203170 | 0.333333 | 0.166667 | -2.916600 | 4.333400 | -20.000000 | -0.334822 | -197.337788 | -0.073682 | 0.137591 | -0.027437 | -0.008257 | -0.354472 | -0.180780 | -0.166667 | 7.250000 |
| R2_1_MATCHED | 15 | 90 | DEV | 7180.000000 | 7008.000000 | -4.035258 | -4.627583 | -28973.148861 | -32430.100370 | -4.139599 | -4.734571 | -4.243458 | -4.818658 | -4.483437 | -5.041861 | 0.530919 | 0.530108 | -5.977187 | -6.558310 | -2.120692 | -2.709216 | 0.258621 | 0.258621 | -362.788000 | -384.836500 | -172.000000 | -0.592325 | -3456.951509 | -0.594971 | -0.575200 | -0.558424 | -0.000811 | -0.581123 | -0.588524 | 0.000000 | -22.048500 |
| R2_1_MATCHED | 15 | 90 | HOLD_B | 649.000000 | 623.000000 | -3.643887 | -2.663118 | -2364.882815 | -1659.122497 | -4.366818 | -3.414691 | -4.937463 | -3.946866 | -6.141298 | -5.194044 | 0.528505 | 0.550562 | -7.163769 | -7.482037 | 0.094106 | 2.354655 | 0.166667 | 0.333333 | -9.622100 | -2.017700 | -26.000000 | 0.980769 | 705.760317 | 0.952127 | 0.990597 | 0.947254 | 0.022056 | -0.318269 | 2.260549 | 0.166667 | 7.604400 |
| R2_1_MATCHED | 15 | 120 | DEV | 6575.000000 | 6361.000000 | -3.530182 | -3.788917 | -23210.945202 | -24101.302485 | -3.699560 | -3.964036 | -3.812912 | -4.070848 | -4.114460 | -4.363606 | 0.531711 | 0.531677 | -5.712217 | nan | -1.339856 | nan | 0.275862 | 0.275862 | -437.486800 | -436.014800 | -214.000000 | -0.258735 | -890.357283 | -0.264475 | -0.257936 | -0.249146 | -0.000034 | nan | nan | 0.000000 | 1.472000 |
| R2_1_MATCHED | 15 | 120 | HOLD_B | 602.000000 | 608.000000 | -4.752110 | -5.834570 | -2860.769980 | -3547.418294 | -5.350901 | -6.319654 | -5.799998 | -6.793934 | -7.011595 | -7.929334 | 0.551495 | 0.541118 | -9.695504 | nan | 0.410249 | nan | 0.333333 | 0.333333 | -4.378600 | -3.633600 | 6.000000 | -1.082460 | -686.648314 | -0.968753 | -0.993935 | -0.917739 | -0.010377 | nan | nan | 0.000000 | 0.745000 |
| R2_1_MATCHED | 15 | 180 | DEV | 5724.000000 | 5587.000000 | -3.602901 | -2.482943 | -20623.006426 | -13872.205206 | -3.745635 | -2.617617 | -3.875853 | -2.741911 | -4.221872 | -3.057207 | 0.537212 | 0.535529 | -5.846377 | -4.701094 | -1.282511 | -0.187025 | 0.241379 | 0.327586 | -414.868900 | -389.812900 | -137.000000 | 1.119958 | 6750.801221 | 1.128018 | 1.133942 | 1.164665 | -0.001683 | 1.145282 | 1.095486 | 0.086207 | 25.056000 |
| R2_1_MATCHED | 15 | 180 | HOLD_B | 540.000000 | 524.000000 | -4.595677 | -1.448517 | -2481.665488 | -759.022708 | -5.123520 | -2.315225 | -5.646158 | -3.164251 | -7.097074 | -4.971063 | 0.555556 | 0.562977 | -10.140147 | -10.621023 | 1.014904 | 6.463201 | 0.166667 | 0.166667 | -5.717200 | 2.490100 | -16.000000 | 3.147160 | 1722.642780 | 2.808295 | 2.481907 | 2.126011 | 0.007422 | -0.480876 | 5.448297 | 0.000000 | 8.207300 |
| R2_1_MATCHED | 15 | 240 | DEV | 5343.000000 | 5155.000000 | -4.591299 | -4.459526 | -24531.309254 | -22988.855075 | -4.741244 | -4.614915 | -4.880937 | -4.753169 | -5.243462 | -5.092902 | 0.533408 | 0.534433 | nan | -7.124998 | nan | -1.762712 | 0.241379 | 0.362069 | -620.869700 | -608.900200 | -188.000000 | 0.131773 | 1542.454179 | 0.126329 | 0.127768 | 0.150560 | 0.001024 | nan | nan | 0.120690 | 11.969500 |
| R2_1_MATCHED | 15 | 240 | HOLD_B | 483.000000 | 499.000000 | -6.029359 | -6.787360 | -2912.180189 | -3386.892634 | -6.789874 | -8.149628 | -7.497057 | -8.756769 | -8.982489 | -10.091617 | 0.554865 | 0.533066 | nan | -13.803203 | nan | 0.267763 | 0.166667 | 0.000000 | -5.131200 | -0.512100 | 16.000000 | -0.758001 | -474.712445 | -1.359755 | -1.259712 | -1.109128 | -0.021799 | nan | nan | -0.166667 | 4.619100 |
| R2_1_MATCHED | 30 | 5 | DEV | 8257.000000 | 8072.000000 | -1.593047 | -1.633015 | -13153.785257 | -13181.697902 | -1.669534 | -1.711261 | -1.737451 | -1.780740 | -1.929438 | -1.972463 | 0.544992 | 0.546209 | -2.887218 | -2.926389 | -0.324988 | -0.333722 | 0.396552 | 0.396552 | 270.034200 | 275.278900 | -185.000000 | -0.039969 | -27.912644 | -0.041727 | -0.043289 | -0.043025 | 0.001217 | -0.039171 | -0.008734 | 0.000000 | 5.244700 |
| R2_1_MATCHED | 30 | 5 | HOLD_B | 581.000000 | 561.000000 | -2.491378 | -5.871961 | -1447.490367 | -3294.170205 | -3.072327 | -6.479696 | -3.503298 | -6.932181 | -4.615323 | -7.941095 | 0.549053 | 0.545455 | -6.707283 | -10.621679 | 1.909670 | -0.809304 | 0.166667 | 0.166667 | 3.461600 | 5.049500 | -20.000000 | -3.380584 | -1846.679838 | -3.407369 | -3.428883 | -3.325772 | -0.003599 | -3.914396 | -2.718974 | 0.000000 | 1.587900 |
| R2_1_MATCHED | 30 | 15 | DEV | 8999.000000 | 8826.000000 | -3.201268 | -3.292858 | -28808.208766 | -29062.763001 | -3.271627 | -3.364607 | -3.334121 | -3.428336 | -3.506464 | -3.604092 | 0.538060 | 0.537276 | -4.488726 | -4.622086 | -1.881536 | -1.946465 | 0.241379 | 0.206897 | 223.296300 | 217.217300 | -173.000000 | -0.091590 | -254.554235 | -0.092980 | -0.094215 | -0.097628 | -0.000784 | -0.133360 | -0.064930 | -0.034483 | -6.079000 |
| R2_1_MATCHED | 30 | 15 | HOLD_B | 735.000000 | 696.000000 | -2.070833 | -5.658028 | -1522.062576 | -3937.987812 | -2.529322 | -6.147406 | -2.869007 | -6.511393 | -3.743833 | -7.321369 | 0.533333 | 0.530172 | nan | -9.779687 | nan | -1.373577 | 0.166667 | 0.166667 | 4.044700 | 5.455600 | -39.000000 | -3.587195 | -2415.925236 | -3.618085 | -3.642387 | -3.577536 | -0.003161 | nan | nan | 0.000000 | 1.410900 |
| R2_1_MATCHED | 30 | 30 | DEV | 8614.000000 | 8444.000000 | -3.310523 | -2.981797 | -28516.842723 | -25178.297373 | -3.424515 | -3.098046 | -3.498054 | -3.174075 | -3.689228 | -3.379726 | 0.530532 | 0.529370 | -4.989327 | -4.494953 | -1.700303 | -1.467904 | 0.206897 | 0.362069 | 122.192800 | 117.706200 | -170.000000 | 0.328725 | 3338.545350 | 0.326469 | 0.323978 | 0.309502 | -0.001162 | 0.494374 | 0.232399 | 0.155172 | -4.486600 |
| R2_1_MATCHED | 30 | 30 | HOLD_B | 752.000000 | 698.000000 | -4.380915 | -5.028385 | -3294.448046 | -3509.812758 | -4.832101 | -5.515455 | -5.167156 | -5.877488 | -5.978204 | -6.747392 | 0.525266 | 0.531519 | nan | -8.733225 | nan | -1.105371 | 0.166667 | 0.166667 | 0.675500 | 4.560000 | -54.000000 | -0.647470 | -215.364711 | -0.683355 | -0.710332 | -0.769188 | 0.006253 | nan | nan | 0.000000 | 3.884500 |
| R2_1_MATCHED | 30 | 45 | DEV | 8155.000000 | 8027.000000 | -2.667994 | -3.082099 | -21757.492484 | -24740.011972 | -2.860653 | -3.277882 | -2.938262 | -3.364374 | -3.142429 | -3.583632 | 0.536971 | 0.533076 | -4.696408 | -5.025037 | -0.777968 | -1.254985 | 0.293103 | 0.258621 | 21.601900 | 67.657700 | -128.000000 | -0.414105 | -2982.519488 | -0.417229 | -0.426111 | -0.441204 | -0.003895 | -0.328628 | -0.477018 | -0.034483 | 46.055800 |
| R2_1_MATCHED | 30 | 45 | HOLD_B | 756.000000 | 710.000000 | -3.665279 | -6.032297 | -2770.950803 | -4282.931174 | -4.113126 | -6.512540 | -4.452732 | -6.869845 | -5.351931 | -7.740618 | 0.533069 | 0.523944 | -7.464871 | nan | 0.200814 | nan | 0.166667 | 0.333333 | -0.751600 | -0.275700 | -46.000000 | -2.367019 | -1511.980370 | -2.399414 | -2.417113 | -2.388687 | -0.009125 | nan | nan | 0.166667 | 0.475900 |
| R2_1_MATCHED | 30 | 60 | DEV | 7674.000000 | 7536.000000 | -2.162876 | -2.228627 | -16597.908698 | -16794.936347 | -2.267182 | -2.334853 | -2.343299 | -2.409358 | -2.560419 | -2.627575 | 0.537529 | 0.536890 | -3.863124 | -4.036165 | -0.450487 | -0.457994 | 0.344828 | 0.275862 | -118.003100 | -119.528200 | -138.000000 | -0.065752 | -197.027649 | -0.067671 | -0.066058 | -0.067156 | -0.000640 | -0.173041 | -0.007507 | -0.068966 | -1.525100 |
| R2_1_MATCHED | 30 | 60 | HOLD_B | 728.000000 | 687.000000 | -3.065309 | -3.187509 | -2231.545091 | -2189.818973 | -3.968175 | -4.144514 | -4.643586 | -4.860609 | -5.963690 | -6.225159 | 0.521978 | 0.529840 | nan | -7.678056 | nan | 1.430413 | 0.333333 | 0.333333 | 0.800100 | 6.272600 | -41.000000 | -0.122200 | 41.726118 | -0.176340 | -0.217023 | -0.261468 | 0.007862 | nan | nan | 0.000000 | 5.472500 |
| R2_1_MATCHED | 30 | 90 | DEV | 6812.000000 | 6722.000000 | -3.659334 | -4.468925 | -24927.380964 | -30040.113875 | -3.769258 | -4.580442 | -3.855624 | -4.668085 | -4.104674 | -4.909705 | 0.532002 | 0.530794 | nan | -6.739803 | nan | -2.239885 | 0.362069 | 0.241379 | -246.661400 | -216.661200 | -90.000000 | -0.809591 | -5112.732911 | -0.811184 | -0.812461 | -0.805031 | -0.001208 | nan | nan | -0.120690 | 30.000200 |
| R2_1_MATCHED | 30 | 90 | HOLD_B | 629.000000 | 607.000000 | -2.063194 | -3.777737 | -1297.748939 | -2293.086515 | -2.806631 | -4.550993 | -3.435776 | -5.111341 | -4.967935 | -6.491139 | 0.532591 | 0.537068 | -7.693432 | -9.299873 | 3.592131 | 1.894292 | 0.666667 | 0.500000 | -4.380700 | 0.169500 | -22.000000 | -1.714543 | -995.337575 | -1.744362 | -1.675565 | -1.523204 | 0.004476 | -1.606441 | -1.697839 | -0.166667 | 4.550200 |
| R2_1_MATCHED | 30 | 120 | DEV | 6244.000000 | 6134.000000 | -4.279599 | -4.130286 | -26721.815004 | -25335.176707 | -4.388446 | -4.241061 | -4.491053 | -4.349123 | -4.788511 | -4.662559 | 0.527867 | 0.525595 | nan | -6.439294 | nan | -1.785319 | 0.258621 | 0.310345 | -288.134800 | -295.642700 | -110.000000 | 0.149312 | 1386.638297 | 0.147385 | 0.141930 | 0.125952 | -0.002272 | nan | nan | 0.051724 | -7.507900 |
| R2_1_MATCHED | 30 | 120 | HOLD_B | 604.000000 | 591.000000 | -3.451654 | -5.341170 | -2084.798834 | -3156.631569 | -4.196142 | -5.917103 | -4.745214 | -6.404389 | -5.980881 | -7.645280 | 0.552980 | 0.558376 | -8.634443 | -11.037323 | 2.157678 | 0.667611 | 0.333333 | 0.333333 | 0.290600 | -1.825300 | -13.000000 | -1.889516 | -1071.832735 | -1.720962 | -1.659175 | -1.664399 | 0.005396 | -2.402881 | -1.490068 | 0.000000 | -2.115900 |
| R2_1_MATCHED | 30 | 180 | DEV | 5407.000000 | 5411.000000 | -3.119175 | -2.964171 | -16865.380348 | -16039.129840 | -3.270189 | -3.103315 | -3.398744 | -3.231743 | -3.752477 | -3.548940 | 0.529499 | 0.530771 | -5.873610 | -5.664194 | -0.384451 | -0.246750 | 0.327586 | 0.362069 | -315.180900 | -332.155900 | 4.000000 | 0.155004 | 826.250508 | 0.166875 | 0.167001 | 0.203536 | 0.001272 | 0.209415 | 0.137701 | 0.034483 | -16.975000 |
| R2_1_MATCHED | 30 | 180 | HOLD_B | 529.000000 | 505.000000 | -4.237760 | -7.200682 | -2241.775182 | -3636.344359 | -5.101544 | -8.094521 | -5.801120 | -8.987107 | -7.621272 | -10.570560 | 0.534972 | 0.524752 | -11.198708 | nan | 2.355393 | nan | 0.166667 | 0.166667 | -2.313700 | 3.086800 | -24.000000 | -2.962922 | -1394.569178 | -2.992977 | -3.185987 | -2.949288 | -0.010219 | nan | nan | 0.000000 | 5.400500 |
| R2_1_MATCHED | 30 | 240 | DEV | 5020.000000 | 5027.000000 | -4.219011 | -4.277988 | -21179.432752 | -21505.445333 | -4.378532 | -4.437299 | -4.520458 | -4.579039 | -4.898283 | -4.956372 | 0.530876 | 0.529342 | -7.053256 | -7.219001 | -1.361765 | -1.305115 | 0.327586 | 0.310345 | -518.087500 | -497.376300 | 7.000000 | -0.058977 | -326.012581 | -0.058767 | -0.058581 | -0.058089 | -0.001535 | -0.165745 | 0.056649 | -0.017241 | 20.711200 |
| R2_1_MATCHED | 30 | 240 | HOLD_B | 465.000000 | 489.000000 | -5.183261 | -9.520510 | -2410.216499 | -4655.529241 | -6.414336 | -10.916294 | -7.206891 | -11.541583 | -8.819528 | -13.101122 | 0.529032 | 0.501022 | nan | -16.572165 | nan | -2.004610 | 0.333333 | 0.166667 | -3.448500 | -1.103200 | 24.000000 | -4.337248 | -2245.312743 | -4.501958 | -4.334691 | -4.281594 | -0.028010 | nan | nan | -0.166667 | 2.345300 |
| R2_1_MATCHED | 45 | 5 | DEV | 7342.000000 | 7137.000000 | -1.748278 | -1.616929 | -12835.854787 | -11540.022257 | -1.857243 | -1.729006 | -1.953522 | -1.828034 | -2.178891 | -2.066312 | 0.539771 | 0.539302 | -3.327227 | -3.226063 | -0.149135 | -0.004702 | 0.379310 | 0.327586 | 476.197700 | 430.847900 | -205.000000 | 0.131349 | 1295.832531 | 0.128237 | 0.125489 | 0.112579 | -0.000469 | 0.101165 | 0.144433 | -0.051724 | -45.349800 |
| R2_1_MATCHED | 45 | 5 | HOLD_B | 540.000000 | 531.000000 | -0.887793 | -0.256896 | -479.407962 | -136.411726 | -1.558148 | -0.937445 | -2.000685 | -1.407160 | -3.212841 | -2.495090 | 0.544444 | 0.553672 | -6.106551 | -5.210646 | 4.416983 | 4.652945 | 0.333333 | 0.500000 | 3.574700 | 8.958000 | -9.000000 | 0.630897 | 342.996236 | 0.620704 | 0.593525 | 0.717751 | 0.009228 | 0.895904 | 0.235962 | 0.166667 | 5.383300 |
| R2_1_MATCHED | 45 | 15 | DEV | 7939.000000 | 7756.000000 | -3.351863 | -3.302999 | -26610.443285 | -25618.058193 | -3.485642 | -3.439928 | -3.574884 | -3.531270 | -3.800341 | -3.766182 | 0.533946 | 0.532878 | -5.022151 | -4.978998 | -1.589076 | -1.588506 | 0.344828 | 0.275862 | 467.331700 | 419.060700 | -183.000000 | 0.048865 | 992.385092 | 0.045714 | 0.043614 | 0.034159 | -0.001069 | 0.043153 | 0.000570 | -0.068966 | -48.271000 |
| R2_1_MATCHED | 45 | 15 | HOLD_B | 668.000000 | 644.000000 | -0.082859 | -0.694582 | -55.349644 | -447.310840 | -0.623364 | -1.256213 | -0.979445 | -1.643749 | -1.952959 | -2.533593 | 0.532934 | 0.543478 | -4.907588 | -4.904455 | 4.523364 | 3.379332 | 0.333333 | 0.500000 | 4.591100 | 8.195600 | -24.000000 | -0.611723 | -391.961196 | -0.632849 | -0.664304 | -0.580634 | 0.010544 | 0.003134 | -1.144032 | 0.166667 | 3.604500 |
| R2_1_MATCHED | 45 | 30 | DEV | 7570.000000 | 7410.000000 | -3.861538 | -3.106871 | -29231.843654 | -23021.916645 | -3.967500 | -3.215020 | -4.061158 | -3.310599 | -4.280570 | -3.534448 | 0.525363 | 0.529285 | nan | nan | nan | nan | 0.293103 | 0.275862 | 379.030400 | 336.188300 | -160.000000 | 0.754667 | 6209.927009 | 0.752480 | 0.750559 | 0.746122 | 0.003921 | nan | nan | -0.017241 | -42.842100 |
| R2_1_MATCHED | 45 | 30 | HOLD_B | 680.000000 | 642.000000 | -3.159178 | -1.579448 | -2148.240962 | -1014.005313 | -3.694661 | -2.144211 | -4.048970 | -2.534346 | -4.988851 | -3.431178 | 0.516176 | 0.532710 | -7.780876 | -5.481097 | 1.678327 | 2.277508 | 0.333333 | 0.166667 | 2.458400 | 6.378400 | -38.000000 | 1.579730 | 1134.235649 | 1.550450 | 1.514624 | 1.557672 | 0.016534 | 2.299779 | 0.599181 | -0.166667 | 3.920000 |
| R2_1_MATCHED | 45 | 45 | DEV | 7732.000000 | 7533.000000 | -2.981887 | -2.983290 | -23055.953990 | -22473.121903 | -3.185128 | -3.191900 | -3.322485 | -3.332887 | -3.589226 | -3.606684 | 0.529359 | 0.526882 | -5.194731 | -5.162366 | -0.833534 | -0.892660 | 0.275862 | 0.293103 | 232.073100 | 227.907000 | -199.000000 | -0.001402 | 582.832088 | -0.006772 | -0.010403 | -0.017458 | -0.002477 | 0.032365 | -0.059126 | 0.017241 | -4.166100 |
| R2_1_MATCHED | 45 | 45 | HOLD_B | 706.000000 | 685.000000 | -2.624247 | -1.223984 | -1852.718207 | -838.429105 | -3.139223 | -1.752724 | -3.479657 | -2.117723 | -4.338018 | -2.984403 | 0.531161 | 0.550365 | -7.631961 | -5.783429 | 2.515152 | 3.291274 | 0.166667 | 0.500000 | 5.637700 | 10.504400 | -21.000000 | 1.400263 | 1014.289102 | 1.386499 | 1.361934 | 1.353615 | 0.019203 | 1.848532 | 0.776122 | 0.333333 | 4.866700 |
| R2_1_MATCHED | 45 | 60 | DEV | 7231.000000 | 7008.000000 | -2.651286 | -3.550496 | -19171.451569 | -24881.875701 | -2.762050 | -3.664913 | -2.839092 | -3.766040 | -3.063557 | -3.999374 | 0.533398 | 0.530251 | nan | -5.678867 | nan | -1.473847 | 0.362069 | 0.258621 | 139.842200 | 114.982600 | -223.000000 | -0.899210 | -5710.424132 | -0.902863 | -0.926947 | -0.935817 | -0.003147 | nan | nan | -0.103448 | -24.859600 |
| R2_1_MATCHED | 45 | 60 | HOLD_B | 678.000000 | 662.000000 | -1.813261 | -1.305801 | -1229.391045 | -864.440190 | -2.481124 | -1.989062 | -2.834685 | -2.307198 | -3.828813 | -3.182001 | 0.529499 | 0.543807 | -8.268245 | -5.534941 | 4.330819 | 3.155964 | 0.333333 | 0.500000 | 2.356800 | 12.943500 | -16.000000 | 0.507460 | 364.950856 | 0.492062 | 0.527488 | 0.646812 | 0.014308 | 2.733303 | -1.174856 | 0.166667 | 10.586700 |
| R2_1_MATCHED | 45 | 90 | DEV | 6425.000000 | 6297.000000 | -5.401533 | -5.115764 | -34704.847146 | -32213.967780 | -5.567159 | -5.284712 | -5.692293 | -5.412346 | -5.985715 | -5.706799 | 0.521712 | 0.523265 | nan | nan | nan | nan | 0.241379 | 0.241379 | -5.454300 | -40.229000 | -128.000000 | 0.285768 | 2490.879366 | 0.282446 | 0.279947 | 0.278916 | 0.001553 | nan | nan | 0.000000 | -34.774700 |
| R2_1_MATCHED | 45 | 90 | HOLD_B | 601.000000 | 585.000000 | -0.068499 | 0.803232 | -41.168126 | 469.890665 | -0.843306 | 0.008691 | -1.595933 | -0.609535 | -3.449903 | -1.896850 | 0.527454 | 0.547009 | -5.682042 | nan | 5.560012 | nan | 0.666667 | 0.500000 | -1.063900 | 5.407400 | -16.000000 | 0.871731 | 511.058792 | 0.851996 | 0.986399 | 1.553053 | 0.019554 | nan | nan | -0.166667 | 6.471300 |
| R2_1_MATCHED | 45 | 120 | DEV | 5909.000000 | 5745.000000 | -4.976578 | -4.810543 | -29406.600296 | -27636.567013 | -5.156598 | -4.995674 | -5.292593 | -5.135524 | -5.640553 | -5.484647 | 0.519716 | 0.519060 | -7.367898 | nan | -2.542137 | nan | 0.224138 | 0.224138 | -98.224500 | -107.975300 | -164.000000 | 0.166036 | 1770.033283 | 0.160925 | 0.157069 | 0.155907 | -0.000656 | nan | nan | 0.000000 | -9.750800 |
| R2_1_MATCHED | 45 | 120 | HOLD_B | 579.000000 | 563.000000 | -3.748856 | -0.586253 | -2170.587845 | -330.060503 | -4.378931 | -1.228638 | -4.844245 | -1.731887 | -6.129589 | -2.976037 | 0.538860 | 0.561279 | nan | -6.411565 | nan | 5.466079 | 0.333333 | 0.500000 | 0.437300 | 5.086800 | -16.000000 | 3.162603 | 1840.527342 | 3.150293 | 3.112358 | 3.153552 | 0.022419 | nan | nan | 0.166667 | 4.649500 |
| R2_1_MATCHED | 45 | 180 | DEV | 5116.000000 | 5036.000000 | -3.867371 | -3.162289 | -19785.469362 | -15925.286937 | -4.075083 | -3.373162 | -4.231955 | -3.532387 | -4.618616 | -3.961088 | 0.520524 | 0.520850 | nan | -6.102394 | nan | -0.221667 | 0.344828 | 0.258621 | -86.415700 | -116.205600 | -80.000000 | 0.705082 | 3860.182425 | 0.701922 | 0.699568 | 0.657529 | 0.000326 | nan | nan | -0.086207 | -29.789900 |
| R2_1_MATCHED | 45 | 180 | HOLD_B | 519.000000 | 495.000000 | -4.084606 | -2.922299 | -2119.910517 | -1446.537883 | -4.948271 | -3.869970 | -5.655007 | -4.772092 | -7.380879 | -6.589497 | 0.520231 | 0.539394 | -11.289726 | nan | 2.953005 | nan | 0.333333 | 0.500000 | -1.633200 | 8.424000 | -24.000000 | 1.162307 | 673.372634 | 1.078302 | 0.882915 | 0.791382 | 0.019163 | nan | nan | 0.166667 | 10.057200 |
| R2_1_MATCHED | 45 | 240 | DEV | 4767.000000 | 4697.000000 | -3.797784 | -4.011037 | -18104.037464 | -18839.838785 | -4.020692 | -4.237313 | -4.189042 | -4.408219 | -4.650061 | -4.881851 | 0.523390 | 0.527571 | -7.105454 | nan | -0.491437 | nan | 0.310345 | 0.362069 | -328.436100 | -357.867800 | -70.000000 | -0.213252 | -735.801321 | -0.216620 | -0.219177 | -0.231790 | 0.004181 | nan | nan | 0.051724 | -29.431700 |
| R2_1_MATCHED | 45 | 240 | HOLD_B | 464.000000 | 465.000000 | -4.856307 | -3.230191 | -2253.326491 | -1502.038900 | -5.645498 | -4.684615 | -6.437877 | -5.473208 | -8.247639 | -7.195354 | 0.530172 | 0.526882 | -11.936547 | -10.494898 | 2.676643 | 4.160146 | 0.333333 | 0.333333 | -3.138000 | 2.914600 | 1.000000 | 1.626116 | 751.287591 | 0.960883 | 0.964670 | 1.052285 | -0.003291 | 1.441649 | 1.483503 | 0.000000 | 6.052600 |
| R2_1_MATCHED | 60 | 5 | DEV | 6311.000000 | 6023.000000 | -1.926519 | -2.295117 | -12158.260128 | -13823.489856 | -2.027483 | -2.408662 | -2.116435 | -2.514552 | -2.344121 | -2.776960 | 0.540168 | 0.537274 | -3.813570 | nan | 0.010488 | nan | 0.413793 | 0.413793 | 461.908700 | 452.034100 | -288.000000 | -0.368598 | -1665.229728 | -0.381179 | -0.398117 | -0.432839 | -0.002894 | nan | nan | 0.000000 | -9.874600 |
| R2_1_MATCHED | 60 | 5 | HOLD_B | 471.000000 | 446.000000 | -4.008051 | -4.097685 | -1887.792155 | -1827.567476 | -4.944120 | -5.086543 | -5.425136 | -6.016365 | -6.778840 | -7.693322 | 0.530786 | 0.542601 | -10.591269 | -11.460034 | 2.642726 | 3.388771 | 0.333333 | 0.333333 | 4.004300 | 4.121500 | -25.000000 | -0.089634 | 60.224679 | -0.142423 | -0.591229 | -0.914482 | 0.011815 | -0.868765 | 0.746044 | 0.000000 | 0.117200 |
| R2_1_MATCHED | 60 | 15 | DEV | 6898.000000 | 6570.000000 | -3.312184 | -3.683171 | -22847.441959 | -24198.431055 | -3.422562 | -3.799117 | -3.515164 | -3.903452 | -3.731887 | -4.140835 | 0.539577 | 0.534855 | -5.040207 | -5.556723 | -1.553369 | -1.768293 | 0.275862 | 0.275862 | 445.211000 | 431.327400 | -328.000000 | -0.370987 | -1350.989096 | -0.376555 | -0.388288 | -0.408948 | -0.004721 | -0.516516 | -0.214924 | 0.000000 | -13.883600 |
| R2_1_MATCHED | 60 | 15 | HOLD_B | 596.000000 | 565.000000 | -3.833605 | -3.901742 | -2284.828847 | -2204.484164 | -4.572728 | -4.681611 | -4.951895 | -5.414179 | -6.016880 | -6.731557 | 0.513423 | 0.532743 | -9.412647 | -10.296832 | 1.662787 | 2.505108 | 0.500000 | 0.166667 | 3.622600 | 4.153100 | -31.000000 | -0.068136 | 80.344683 | -0.108883 | -0.462284 | -0.714677 | 0.019321 | -0.884185 | 0.842321 | -0.333333 | 0.530500 |
| R2_1_MATCHED | 60 | 30 | DEV | 6639.000000 | 6401.000000 | -3.849639 | -3.367800 | -25557.750617 | -21557.287584 | -3.945904 | -3.487733 | -4.040412 | -3.594774 | -4.279200 | -3.876943 | 0.526133 | 0.527730 | -5.804074 | -5.508587 | -1.886409 | -1.191024 | 0.293103 | 0.344828 | 363.251000 | 334.557900 | -238.000000 | 0.481839 | 4000.463033 | 0.458171 | 0.445638 | 0.402257 | 0.001597 | 0.295488 | 0.695385 | 0.051724 | -28.693100 |
| R2_1_MATCHED | 60 | 30 | HOLD_B | 612.000000 | 564.000000 | -5.873109 | -4.007335 | -3594.342585 | -2260.137199 | -6.388266 | -4.738706 | -6.760464 | -5.296761 | -7.806316 | -6.508178 | 0.508170 | 0.537234 | nan | -9.842267 | nan | 2.038863 | 0.166667 | 0.333333 | -0.700100 | 3.614300 | -48.000000 | 1.865773 | 1334.205386 | 1.649560 | 1.463703 | 1.298138 | 0.029064 | nan | nan | 0.166667 | 4.314400 |
| R2_1_MATCHED | 60 | 45 | DEV | 6583.000000 | 6378.000000 | -4.758664 | -4.186366 | -31326.284479 | -26700.640425 | -4.874544 | -4.305882 | -4.967210 | -4.413438 | -5.206678 | -4.668190 | 0.526660 | 0.524302 | -6.790857 | -6.200409 | -2.741219 | -2.120282 | 0.206897 | 0.241379 | 312.391100 | 295.107000 | -205.000000 | 0.572298 | 4625.644054 | 0.568663 | 0.553773 | 0.538488 | -0.002357 | 0.590448 | 0.620937 | 0.034483 | -17.284100 |
| R2_1_MATCHED | 60 | 45 | HOLD_B | 624.000000 | 599.000000 | -4.668772 | -4.526693 | -2913.313885 | -2711.488853 | -5.376016 | -5.263266 | -5.789723 | -5.955088 | -6.850088 | -7.200248 | 0.528846 | 0.527546 | -10.245675 | -10.922530 | 0.785668 | 1.976570 | 0.333333 | 0.500000 | 1.219300 | 4.997200 | -25.000000 | 0.142080 | 201.825032 | 0.112750 | -0.165365 | -0.350160 | -0.001300 | -0.676855 | 1.190903 | 0.166667 | 3.777900 |
| R2_1_MATCHED | 60 | 60 | DEV | 6690.000000 | 6362.000000 | -3.759702 | -3.368677 | -25152.409663 | -21431.525903 | -3.891451 | -3.507158 | -4.011378 | -3.633209 | -4.314117 | -3.980840 | 0.530493 | 0.524678 | -5.771180 | nan | -1.727379 | nan | 0.293103 | 0.327586 | 149.573500 | 73.675600 | -328.000000 | 0.391025 | 3720.883760 | 0.384293 | 0.378169 | 0.333277 | -0.005815 | nan | nan | 0.034483 | -75.897900 |
| R2_1_MATCHED | 60 | 60 | HOLD_B | 625.000000 | 591.000000 | -4.439818 | -5.769548 | -2774.886169 | -3409.802602 | -5.168615 | -6.542597 | -5.531089 | -6.971125 | -6.576623 | -8.056476 | 0.515200 | 0.521151 | nan | -11.081339 | nan | -0.204193 | 0.333333 | 0.166667 | 3.323700 | 5.855000 | -34.000000 | -1.329730 | -634.916433 | -1.373982 | -1.440036 | -1.479852 | 0.005951 | nan | nan | -0.166667 | 2.531300 |
| R2_1_MATCHED | 60 | 90 | DEV | 5812.000000 | 5646.000000 | -4.510607 | -5.685585 | -26215.645034 | -32100.811843 | -4.721698 | -5.903092 | -4.852169 | -6.037609 | -5.189758 | -6.340283 | 0.525465 | 0.521785 | -7.190523 | -8.367381 | -1.844963 | -3.054874 | 0.241379 | 0.224138 | 16.729000 | -44.179500 | -166.000000 | -1.174978 | -5885.166809 | -1.181394 | -1.185441 | -1.150525 | -0.003679 | -1.176858 | -1.209910 | -0.017241 | -60.908500 |
| R2_1_MATCHED | 60 | 90 | HOLD_B | 542.000000 | 512.000000 | -0.689798 | -4.273368 | -373.870510 | -2187.964365 | -1.550251 | -5.191350 | -2.360426 | -6.056321 | -4.510482 | -7.708866 | 0.518450 | 0.535156 | -8.636043 | -12.391451 | 7.017158 | 4.210657 | 0.500000 | 0.333333 | -8.306300 | 0.475600 | -30.000000 | -3.583570 | -1814.093855 | -3.641099 | -3.695895 | -3.198384 | 0.016706 | -3.755408 | -2.806501 | -0.166667 | 8.781900 |
| R2_1_MATCHED | 60 | 120 | DEV | 5393.000000 | 5145.000000 | -4.991457 | -5.328522 | -26918.927382 | -27415.243613 | -5.132092 | -5.476003 | -5.258300 | -5.609572 | -5.607727 | -5.986170 | 0.517894 | 0.512536 | nan | -8.153972 | nan | -2.457428 | 0.258621 | 0.258621 | -111.202300 | -138.185500 | -248.000000 | -0.337065 | -496.316231 | -0.343910 | -0.351272 | -0.378443 | -0.005357 | nan | nan | 0.000000 | -26.983200 |
| R2_1_MATCHED | 60 | 120 | HOLD_B | 524.000000 | 507.000000 | -2.987483 | -4.758364 | -1565.440916 | -2412.490547 | -3.826740 | -5.629318 | -4.358792 | -6.447899 | -5.816698 | -8.010726 | 0.541985 | 0.540434 | -10.193541 | -12.389526 | 4.171899 | 3.128913 | 0.333333 | 0.333333 | -3.648700 | -1.018200 | -17.000000 | -1.770881 | -847.049631 | -1.802577 | -2.089107 | -2.194028 | -0.001551 | -2.195985 | -1.042986 | 0.000000 | 2.630500 |
| R2_1_MATCHED | 60 | 180 | DEV | 4601.000000 | 4417.000000 | -4.420335 | -4.722148 | -20337.960126 | -20857.728139 | -4.618105 | -4.928227 | -4.782909 | -5.099969 | -5.209432 | -5.584588 | 0.524886 | 0.517319 | -7.639662 | -8.014355 | -1.224922 | -1.406042 | 0.224138 | 0.293103 | -52.114600 | -85.829900 | -184.000000 | -0.301813 | -519.768013 | -0.310122 | -0.317061 | -0.375156 | -0.007566 | -0.374693 | -0.181120 | 0.068966 | -33.715300 |
| R2_1_MATCHED | 60 | 180 | HOLD_B | 457.000000 | 432.000000 | -5.400934 | -5.120888 | -2468.226872 | -2212.223656 | -6.368796 | -6.155685 | -7.090453 | -7.183824 | -9.003256 | -9.147991 | 0.505470 | 0.511574 | nan | -10.728157 | nan | 0.419560 | 0.333333 | 0.166667 | -4.790100 | 5.134800 | -25.000000 | 0.280046 | 256.003216 | 0.213112 | -0.093371 | -0.144735 | 0.006104 | nan | nan | -0.166667 | 9.924900 |
| R2_1_MATCHED | 60 | 240 | DEV | 4276.000000 | 4078.000000 | -7.120503 | -7.588411 | -30447.269041 | -30945.540380 | -7.308465 | -7.785616 | -7.486430 | -7.972343 | -7.962232 | -8.485914 | 0.514967 | 0.511280 | -10.586876 | -11.329174 | -3.532387 | -3.772259 | 0.241379 | 0.241379 | -289.110000 | -318.453000 | -198.000000 | -0.467908 | -498.271339 | -0.477152 | -0.485914 | -0.523682 | -0.003687 | -0.742297 | -0.239872 | 0.000000 | -29.343000 |
| R2_1_MATCHED | 60 | 240 | HOLD_B | 411.000000 | 402.000000 | -7.866063 | -7.657880 | -3232.952068 | -3078.467739 | -8.948528 | -8.764120 | -9.851920 | -9.630115 | -11.859857 | -11.953056 | 0.503650 | 0.492537 | nan | nan | nan | nan | 0.166667 | 0.333333 | -7.390500 | 1.757600 | -9.000000 | 0.208183 | 154.484329 | 0.184408 | 0.221804 | -0.093199 | -0.011112 | nan | nan | 0.166667 | 9.148100 |
| R2_1_MATCHED | 90 | 5 | DEV | 5493.000000 | 5213.000000 | -1.701325 | -2.170514 | -9345.380907 | -11314.890541 | -1.877958 | -2.356725 | -2.016218 | -2.502507 | -2.385499 | -2.894991 | 0.543055 | 0.546710 | -3.971437 | -4.362827 | 0.599412 | 0.086893 | 0.396552 | 0.344828 | 711.237600 | 686.008300 | -280.000000 | -0.469189 | -1969.509634 | -0.478768 | -0.486289 | -0.509492 | 0.003655 | -0.391390 | -0.512519 | -0.051724 | -25.229300 |
| R2_1_MATCHED | 90 | 5 | HOLD_B | 437.000000 | 421.000000 | -4.514831 | -3.009268 | -1972.981362 | -1266.901619 | -5.559921 | -4.090585 | -6.362557 | -4.851101 | -8.111993 | -6.897210 | 0.535469 | 0.527316 | nan | -11.701075 | nan | 5.573046 | 0.333333 | 0.166667 | 6.644400 | 5.633300 | -16.000000 | 1.505564 | 706.079743 | 1.469336 | 1.511456 | 1.214783 | -0.008153 | nan | nan | -0.166667 | -1.011100 |
| R2_1_MATCHED | 90 | 15 | DEV | 5917.000000 | 5728.000000 | -2.798801 | -3.191632 | -16560.506569 | -18281.669413 | -2.933155 | -3.330488 | -3.064264 | -3.465995 | -3.410287 | -3.823655 | 0.540139 | 0.538233 | -4.941535 | -5.399175 | -0.633926 | -0.954971 | 0.396552 | 0.327586 | 692.898700 | 689.805600 | -189.000000 | -0.392831 | -1721.162844 | -0.397334 | -0.401730 | -0.413368 | -0.001905 | -0.457640 | -0.321045 | -0.068966 | -3.093100 |
| R2_1_MATCHED | 90 | 15 | HOLD_B | 540.000000 | 521.000000 | -4.200363 | -4.545248 | -2268.195879 | -2368.074104 | -4.881195 | -5.421574 | -5.528905 | -6.038119 | -7.189988 | -7.694597 | 0.524074 | 0.514395 | -10.802307 | -11.615105 | 2.660016 | 2.438115 | 0.166667 | 0.166667 | 6.007000 | 4.458600 | -19.000000 | -0.344885 | -99.878225 | -0.540379 | -0.509214 | -0.504609 | -0.009679 | -0.812797 | -0.221901 | 0.000000 | -1.548400 |
| R2_1_MATCHED | 90 | 30 | DEV | 5754.000000 | 5552.000000 | -3.242895 | -3.765601 | -18659.618008 | -20906.616580 | -3.372652 | -3.900174 | -3.496829 | -4.028966 | -3.827348 | -4.387562 | 0.534237 | 0.530620 | -5.615712 | -6.143951 | -0.818392 | -1.347758 | 0.293103 | 0.327586 | 654.148900 | 605.957700 | -202.000000 | -0.522706 | -2246.998572 | -0.527522 | -0.532137 | -0.560214 | -0.003617 | -0.528239 | -0.529367 | 0.034483 | -48.191200 |
| R2_1_MATCHED | 90 | 30 | HOLD_B | 547.000000 | 510.000000 | -4.585518 | -2.965509 | -2508.278205 | -1512.409658 | -5.258326 | -3.684043 | -5.898410 | -4.316139 | -7.471289 | -6.035991 | 0.521024 | 0.513725 | -11.728575 | -9.675536 | 2.724931 | 3.737786 | 0.333333 | 0.333333 | 0.412800 | 4.771000 | -37.000000 | 1.620009 | 995.868547 | 1.574284 | 1.582270 | 1.435298 | -0.007298 | 2.053039 | 1.012854 | 0.000000 | 4.358200 |
| R2_1_MATCHED | 90 | 45 | DEV | 5821.000000 | 5659.000000 | -2.682481 | -2.828808 | -15614.720534 | -16008.222348 | -2.896689 | -3.049175 | -3.033079 | -3.189497 | -3.384768 | -3.547952 | 0.537021 | 0.537728 | -5.113016 | nan | -0.203830 | nan | 0.327586 | 0.344828 | 485.743500 | 454.490100 | -162.000000 | -0.146327 | -393.501814 | -0.152486 | -0.156419 | -0.163184 | 0.000706 | nan | nan | 0.017241 | -31.253400 |
| R2_1_MATCHED | 90 | 45 | HOLD_B | 571.000000 | 549.000000 | -4.244504 | -3.534610 | -2423.611501 | -1940.500717 | -5.043431 | -4.813501 | -5.656138 | -5.647061 | -6.987652 | -7.284797 | 0.523643 | 0.522769 | nan | -9.925525 | nan | 2.744507 | 0.166667 | 0.166667 | 1.679100 | 1.439600 | -22.000000 | 0.709894 | 483.110783 | 0.229930 | 0.009077 | -0.297144 | -0.000874 | nan | nan | 0.000000 | -0.239500 |
| R2_1_MATCHED | 90 | 60 | DEV | 5795.000000 | 5552.000000 | -3.703726 | -3.499449 | -21463.089531 | -19428.939879 | -3.919071 | -3.724185 | -4.045324 | -3.855931 | -4.399118 | -4.220386 | 0.531838 | 0.526837 | -6.197379 | -6.152221 | -1.204499 | -0.907894 | 0.327586 | 0.293103 | 401.401400 | 391.005800 | -243.000000 | 0.204277 | 2034.149652 | 0.194887 | 0.189394 | 0.178732 | -0.005001 | 0.045158 | 0.296605 | -0.034483 | -10.395600 |
| R2_1_MATCHED | 90 | 60 | HOLD_B | 556.000000 | 541.000000 | -4.981277 | -7.793030 | -2769.590055 | -4216.029070 | -5.801657 | -8.641405 | -6.432322 | -9.241047 | -7.678417 | -10.690934 | 0.525180 | 0.491682 | nan | nan | nan | nan | 0.333333 | 0.166667 | 7.767800 | 8.821500 | -15.000000 | -2.811753 | -1446.439015 | -2.839748 | -2.808724 | -3.012517 | -0.033498 | nan | nan | -0.166667 | 1.053700 |
| R2_1_MATCHED | 90 | 90 | DEV | 5566.000000 | 5384.000000 | -4.438254 | -4.116531 | -24703.324443 | -22163.404710 | -4.662594 | -4.348396 | -4.883083 | -4.576283 | -5.274855 | -4.972417 | 0.522637 | 0.526746 | nan | -6.927405 | nan | -1.322884 | 0.241379 | 0.344828 | 208.813700 | 209.865400 | -182.000000 | 0.321723 | 2539.919733 | 0.314198 | 0.306800 | 0.302438 | 0.004108 | nan | nan | 0.103448 | 1.051700 |
| R2_1_MATCHED | 90 | 90 | HOLD_B | 508.000000 | 487.000000 | -3.018472 | -5.554899 | -1533.383764 | -2705.235820 | -3.941221 | -6.522739 | -4.840599 | -7.466382 | -6.756141 | -9.353910 | 0.509843 | 0.496920 | nan | nan | nan | nan | 0.500000 | 0.166667 | 1.637100 | 3.617000 | -21.000000 | -2.536427 | -1171.852056 | -2.581518 | -2.625783 | -2.597768 | -0.012923 | nan | nan | -0.333333 | 1.979900 |
| R2_1_MATCHED | 90 | 120 | DEV | 5041.000000 | 4803.000000 | -4.247766 | -5.364186 | -21412.988834 | -25764.186921 | -4.495436 | -5.624364 | -4.653255 | -5.790242 | -5.077484 | -6.211030 | 0.521722 | 0.517593 | -7.334075 | nan | -1.181782 | nan | 0.258621 | 0.327586 | 145.766500 | 140.672000 | -238.000000 | -1.116420 | -4351.198087 | -1.128928 | -1.136987 | -1.133546 | -0.004129 | nan | nan | 0.068966 | -5.094500 |
| R2_1_MATCHED | 90 | 120 | HOLD_B | 488.000000 | 482.000000 | -2.635169 | -7.268364 | -1285.962438 | -3503.351279 | -3.566954 | -8.221404 | -4.304996 | -8.893877 | -6.330802 | -10.728184 | 0.518443 | 0.514523 | nan | -15.544918 | nan | 1.344698 | 0.500000 | 0.166667 | 9.901300 | 5.384600 | -6.000000 | -4.633195 | -2217.388841 | -4.654450 | -4.588881 | -4.397382 | -0.003920 | nan | nan | -0.333333 | -4.516700 |
| R2_1_MATCHED | 90 | 180 | DEV | 4368.000000 | 4209.000000 | -2.950459 | -2.918999 | -12887.605887 | -12286.066988 | -3.236001 | -3.215322 | -3.444099 | -3.431281 | -3.976842 | -3.944089 | 0.528159 | 0.530530 | nan | -6.211082 | nan | 0.416448 | 0.344828 | 0.362069 | 118.218500 | 114.138000 | -159.000000 | 0.031460 | 601.538899 | 0.020678 | 0.012818 | 0.032753 | 0.002370 | nan | nan | 0.017241 | -4.080500 |
| R2_1_MATCHED | 90 | 180 | HOLD_B | 436.000000 | 415.000000 | -7.553688 | -3.289090 | -3293.407861 | -1364.972445 | -8.608166 | -4.420772 | -9.369901 | -5.523834 | -11.282509 | -8.127811 | 0.511468 | 0.503614 | -18.041353 | -14.548997 | 3.195076 | 7.156828 | 0.500000 | 0.500000 | 6.798700 | 5.837500 | -21.000000 | 4.264598 | 1928.435415 | 4.187394 | 3.846067 | 3.154698 | -0.007853 | 3.492356 | 3.961752 | 0.000000 | -0.961200 |
| R2_1_MATCHED | 90 | 240 | DEV | 4062.000000 | 3897.000000 | -6.744989 | -6.072168 | -27398.143452 | -23663.237755 | -7.052980 | -6.393031 | -7.250880 | -6.599144 | -7.785021 | -7.126874 | 0.521910 | 0.525019 | -10.579529 | nan | -2.860407 | nan | 0.293103 | 0.310345 | -69.102100 | -119.091500 | -165.000000 | 0.672821 | 3734.905696 | 0.659950 | 0.651736 | 0.658147 | 0.003109 | nan | nan | 0.017241 | -49.989400 |
| R2_1_MATCHED | 90 | 240 | HOLD_B | 395.000000 | 391.000000 | -4.486307 | -5.053759 | -1772.091184 | -1976.019612 | -6.202318 | -6.788825 | -7.366050 | -7.966031 | -9.718255 | -10.369346 | 0.513924 | 0.483376 | nan | nan | nan | nan | 0.333333 | 0.333333 | -3.293400 | 2.893300 | -4.000000 | -0.567452 | -203.928428 | -0.586507 | -0.599981 | -0.651091 | -0.030548 | nan | nan | 0.000000 | 6.186700 |
| R2_1_MATCHED | 120 | 5 | DEV | 4796.000000 | 4642.000000 | -1.847272 | -2.315956 | -8859.517435 | -10750.669815 | -2.033504 | -2.508469 | -2.211196 | -2.693729 | -2.660981 | -3.200922 | 0.537114 | 0.549548 | -4.766176 | -5.224070 | 1.027627 | 0.600803 | 0.413793 | 0.362069 | 834.014000 | 797.195800 | -154.000000 | -0.468684 | -1891.152381 | -0.474965 | -0.482533 | -0.539941 | 0.012433 | -0.457895 | -0.426823 | -0.051724 | -36.818200 |
| R2_1_MATCHED | 120 | 5 | HOLD_B | 388.000000 | 380.000000 | -5.510573 | -3.177133 | -2138.102414 | -1207.310532 | -6.865208 | -4.146235 | -7.985333 | -5.119358 | -10.775199 | -7.095258 | 0.479381 | 0.505263 | -15.265012 | -13.707224 | 4.177349 | 7.934021 | 0.333333 | 0.500000 | 13.331000 | 11.914300 | -8.000000 | 2.333440 | 930.791881 | 2.718973 | 2.865975 | 3.679941 | 0.025882 | 1.557789 | 3.756672 | 0.166667 | -1.416700 |
| R2_1_MATCHED | 120 | 15 | DEV | 5217.000000 | 5092.000000 | -4.146951 | -3.966428 | -21634.645582 | -20197.049521 | -4.341458 | -4.165674 | -4.513170 | -4.341568 | -4.907565 | -4.808145 | 0.528848 | 0.535546 | -6.836785 | -6.688980 | -1.408047 | -1.227391 | 0.344828 | 0.362069 | 790.039300 | 743.463000 | -125.000000 | 0.180524 | 1437.596061 | 0.175784 | 0.171601 | 0.099419 | 0.006698 | 0.147805 | 0.180656 | 0.017241 | -46.576300 |
| R2_1_MATCHED | 120 | 15 | HOLD_B | 477.000000 | 467.000000 | -4.542626 | -3.710210 | -2166.832689 | -1732.668049 | -5.641945 | -4.499529 | -6.670593 | -5.291344 | -8.926047 | -6.896276 | 0.482180 | 0.496788 | -12.619938 | -12.691257 | 3.538963 | 5.583950 | 0.333333 | 0.500000 | 13.253900 | 12.322600 | -10.000000 | 0.832416 | 434.164640 | 1.142416 | 1.379249 | 2.029772 | 0.014608 | -0.071318 | 2.044987 | 0.166667 | -0.931300 |
| R2_1_MATCHED | 120 | 30 | DEV | 5073.000000 | 4970.000000 | -4.519170 | -4.391414 | -22925.748935 | -21825.328535 | -4.719272 | -4.595638 | -4.895934 | -4.775938 | -5.303477 | -5.254243 | 0.524147 | 0.533400 | -7.438177 | -7.358459 | -1.648044 | -1.402379 | 0.327586 | 0.293103 | 739.724800 | 708.588700 | -103.000000 | 0.127756 | 1100.420400 | 0.123634 | 0.119996 | 0.049235 | 0.009253 | 0.079718 | 0.245665 | -0.034483 | -31.136100 |
| R2_1_MATCHED | 120 | 30 | HOLD_B | 493.000000 | 466.000000 | -7.288282 | -4.356015 | -3593.122880 | -2029.902841 | -8.284733 | -5.148420 | -9.155408 | -5.943340 | -11.239271 | -7.645679 | 0.472617 | 0.497854 | -15.053496 | -12.036512 | 1.059661 | 3.947751 | 0.166667 | 0.333333 | 9.482100 | 11.714200 | -27.000000 | 2.932267 | 1563.220039 | 3.136313 | 3.212068 | 3.593592 | 0.025237 | 3.016983 | 2.888090 | 0.166667 | 2.232100 |
| R2_1_MATCHED | 120 | 45 | DEV | 5143.000000 | 5038.000000 | -4.314641 | -4.521178 | -22190.200802 | -22777.693842 | -4.495415 | -4.705761 | -4.669629 | -4.883649 | -5.112672 | -5.376349 | 0.524985 | 0.529178 | -7.160339 | -7.561738 | -1.404556 | -1.436220 | 0.275862 | 0.293103 | 630.866400 | 571.965600 | -105.000000 | -0.206536 | -587.493040 | -0.210346 | -0.214020 | -0.263677 | 0.004193 | -0.401399 | -0.031663 | 0.017241 | -58.900800 |
| R2_1_MATCHED | 120 | 45 | HOLD_B | 509.000000 | 484.000000 | -2.950867 | -6.821220 | -1501.991260 | -3301.470275 | -4.338823 | -7.589198 | -5.526270 | -8.119308 | -7.912088 | -9.476027 | 0.489194 | 0.495868 | -13.619331 | nan | 6.541510 | nan | 0.333333 | 0.333333 | 8.292600 | 7.978700 | -25.000000 | -3.870353 | -1799.479015 | -3.250375 | -2.593038 | -1.563939 | 0.006673 | nan | nan | 0.000000 | -0.313900 |
| R2_1_MATCHED | 120 | 60 | DEV | 5128.000000 | 4960.000000 | -3.750004 | -5.106387 | -19230.018007 | -25327.680154 | -3.947809 | -5.311167 | -4.122425 | -5.491975 | -4.563022 | -5.933134 | 0.533346 | 0.537500 | -6.603783 | -7.995197 | -0.941933 | -2.231358 | 0.275862 | 0.327586 | 536.767500 | 494.990300 | -168.000000 | -1.356384 | -6097.662147 | -1.363358 | -1.369550 | -1.370112 | 0.004154 | -1.391414 | -1.289426 | 0.051724 | -41.777200 |
| R2_1_MATCHED | 120 | 60 | HOLD_B | 515.000000 | 484.000000 | -7.335446 | -8.665324 | -3777.754656 | -4194.016713 | -8.177544 | -9.564223 | -9.010671 | -10.098431 | -10.405221 | -11.484596 | 0.481553 | 0.479339 | -15.280384 | -16.761265 | 0.477924 | 0.198619 | 0.333333 | 0.333333 | 15.231400 | 15.586700 | -31.000000 | -1.329878 | -416.262056 | -1.386679 | -1.087760 | -1.079375 | -0.002215 | -1.480881 | -0.279306 | 0.000000 | 0.355300 |
| R2_1_MATCHED | 120 | 90 | DEV | 4848.000000 | 4725.000000 | -3.712176 | -5.374512 | -17996.630304 | -25394.567135 | -3.921401 | -5.589536 | -4.106101 | -5.779399 | -4.597371 | -6.240210 | 0.527640 | 0.527196 | -6.784011 | -8.517566 | -0.607720 | -2.211708 | 0.310345 | 0.275862 | 379.070200 | 343.779600 | -123.000000 | -1.662335 | -7397.936831 | -1.668135 | -1.673298 | -1.642839 | -0.000444 | -1.733556 | -1.603989 | -0.034483 | -35.290600 |
| R2_1_MATCHED | 120 | 90 | HOLD_B | 457.000000 | 448.000000 | -3.742892 | -6.617202 | -1710.501496 | -2964.506293 | -4.888672 | -7.446574 | -5.960880 | -8.278729 | -7.992022 | -9.890060 | 0.481400 | 0.486607 | -13.323751 | -16.900511 | 5.792343 | 4.103107 | 0.500000 | 0.333333 | 3.614000 | 14.471900 | -9.000000 | -2.874310 | -1254.004797 | -2.557902 | -2.317849 | -1.898038 | 0.005207 | -3.576760 | -1.689236 | -0.166667 | 10.857900 |
| R2_1_MATCHED | 120 | 120 | DEV | 4779.000000 | 4563.000000 | -5.041095 | -5.006090 | -24091.394998 | -22842.786936 | -5.253619 | -5.228668 | -5.441266 | -5.425196 | -5.894155 | -5.887704 | 0.517891 | 0.523340 | nan | -8.434031 | nan | -1.605084 | 0.206897 | 0.258621 | 316.605400 | 231.954400 | -216.000000 | 0.035006 | 1248.608063 | 0.024951 | 0.016070 | 0.006451 | 0.005449 | nan | nan | 0.051724 | -84.651000 |
| R2_1_MATCHED | 120 | 120 | HOLD_B | 461.000000 | 453.000000 | -2.282122 | -3.553683 | -1052.058447 | -1609.818607 | -3.414764 | -4.367104 | -4.335529 | -5.183205 | -6.021544 | -6.991929 | 0.520607 | 0.516556 | nan | -14.032657 | nan | 7.303262 | 0.500000 | 0.500000 | 9.890300 | 10.162700 | -8.000000 | -1.271561 | -557.760159 | -0.952340 | -0.847676 | -0.970385 | -0.004051 | nan | nan | 0.000000 | 0.272400 |
| R2_1_MATCHED | 120 | 180 | DEV | 4046.000000 | 3899.000000 | -5.344510 | -3.446480 | -21623.888489 | -13437.825366 | -5.595621 | -3.706574 | -5.817365 | -3.936197 | -6.373687 | -4.427171 | 0.514829 | 0.531675 | -9.205129 | -7.221163 | -1.469453 | 0.294590 | 0.362069 | 0.379310 | 190.035800 | 204.148400 | -147.000000 | 1.898030 | 8186.063123 | 1.889047 | 1.881168 | 1.946515 | 0.016845 | 1.983966 | 1.764043 | 0.017241 | 14.112600 |
| R2_1_MATCHED | 120 | 180 | HOLD_B | 400.000000 | 384.000000 | -7.975012 | -3.872098 | -3190.004643 | -1486.885620 | -9.295082 | -4.832893 | -10.371743 | -5.612705 | -12.547594 | -7.687952 | 0.472500 | 0.502604 | nan | nan | nan | nan | 0.333333 | 0.500000 | 11.407400 | 17.015500 | -16.000000 | 4.102914 | 1703.119023 | 4.462189 | 4.759038 | 4.859641 | 0.030104 | nan | nan | 0.166667 | 5.608100 |
| R2_1_MATCHED | 120 | 240 | DEV | 3728.000000 | 3588.000000 | -7.844934 | -6.929549 | -29245.912342 | -24863.222452 | -8.118141 | -7.213165 | -8.334066 | -7.454189 | -8.925881 | -8.091860 | 0.515826 | 0.532887 | -12.054926 | -11.248888 | -3.516613 | -2.513702 | 0.293103 | 0.327586 | 39.827800 | -49.717500 | -140.000000 | 0.915384 | 4382.689890 | 0.904976 | 0.879877 | 0.834021 | 0.017061 | 0.806037 | 1.002911 | 0.034483 | -89.545300 |
| R2_1_MATCHED | 120 | 240 | HOLD_B | 371.000000 | 359.000000 | -6.431464 | -8.069376 | -2386.073104 | -2896.906128 | -7.978671 | -9.108990 | -9.406074 | -9.956912 | -11.947017 | -12.182899 | 0.493261 | 0.467967 | -18.346238 | -19.472466 | 5.819593 | 4.365553 | 0.500000 | 0.500000 | 10.001800 | 8.205000 | -12.000000 | -1.637913 | -510.833024 | -1.130319 | -0.550838 | -0.235882 | -0.025295 | -1.126228 | -1.454040 | 0.000000 | -1.796800 |
| R2_1_MATCHED | 180 | 5 | DEV | 3986.000000 | 3879.000000 | -0.796050 | -0.400063 | -3173.055772 | -1551.844805 | -1.171920 | -0.786202 | -1.373745 | -1.024994 | -1.929580 | -1.617564 | 0.542900 | 0.550657 | nan | -4.023585 | nan | 3.178782 | 0.413793 | 0.534483 | 1108.447200 | 1048.996300 | -107.000000 | 0.395987 | 1621.210967 | 0.385718 | 0.348751 | 0.312016 | 0.007757 | nan | nan | 0.120690 | -59.450900 |
| R2_1_MATCHED | 180 | 5 | HOLD_B | 310.000000 | 313.000000 | -2.978584 | -7.430524 | -923.360942 | -2325.753929 | -4.203826 | -8.658254 | -5.312812 | -9.589117 | -8.147628 | -12.225694 | 0.532258 | 0.507987 | -14.322776 | -17.760939 | 8.876075 | 3.462744 | 0.333333 | 0.333333 | 3.409800 | 8.401600 | 3.000000 | -4.451940 | -1402.392988 | -4.454428 | -4.276304 | -4.078066 | -0.024271 | -3.438163 | -5.413331 | 0.000000 | 4.991800 |
| R2_1_MATCHED | 180 | 15 | DEV | 4238.000000 | 4177.000000 | -2.585055 | -2.641648 | -10955.462338 | -11034.163871 | -2.938992 | -3.000769 | -3.145035 | -3.223047 | -3.669035 | -3.768844 | 0.530911 | 0.531961 | -6.067005 | -6.035848 | 0.861347 | 0.738373 | 0.431034 | 0.431034 | 1080.021400 | 1024.863200 | -61.000000 | -0.056593 | -78.701533 | -0.061777 | -0.078011 | -0.099809 | 0.001050 | 0.031157 | -0.122973 | 0.000000 | -55.158200 |
| R2_1_MATCHED | 180 | 15 | HOLD_B | 379.000000 | 387.000000 | -3.744452 | -7.827850 | -1419.147168 | -3029.377849 | -4.748065 | -8.821242 | -5.655524 | -9.573608 | -7.901524 | -11.699313 | 0.522427 | 0.488372 | -13.305524 | -16.662133 | 6.171267 | 1.235339 | 0.166667 | 0.166667 | 3.087000 | 7.419000 | 8.000000 | -4.083398 | -1610.230681 | -4.073177 | -3.918085 | -3.797789 | -0.034055 | -3.356610 | -4.935928 | 0.000000 | 4.332000 |
| R2_1_MATCHED | 180 | 30 | DEV | 4158.000000 | 4108.000000 | -2.936375 | -3.157469 | -12209.447751 | -12970.881591 | -3.297208 | -3.522749 | -3.491192 | -3.748889 | -4.025982 | -4.310377 | 0.528139 | 0.526290 | -6.674748 | nan | 0.749491 | nan | 0.344828 | 0.396552 | 1025.213800 | 979.369800 | -50.000000 | -0.221094 | -761.433840 | -0.225540 | -0.257697 | -0.284395 | -0.001848 | nan | nan | 0.051724 | -45.844000 |
| R2_1_MATCHED | 180 | 30 | HOLD_B | 393.000000 | 384.000000 | -8.254718 | -7.700398 | -3244.104009 | -2956.952914 | -9.233993 | -8.701238 | -10.120433 | -9.443508 | -12.319915 | -11.450098 | 0.501272 | 0.484375 | -17.383300 | -16.324054 | 1.740184 | 1.409216 | 0.166667 | 0.166667 | 1.642400 | 8.575700 | -9.000000 | 0.554319 | 287.151095 | 0.532755 | 0.676925 | 0.869817 | -0.016897 | 1.059246 | -0.330968 | 0.000000 | 6.933300 |
| R2_1_MATCHED | 180 | 45 | DEV | 4241.000000 | 4216.000000 | -2.532640 | -3.232339 | -10740.924306 | -13627.540655 | -2.836684 | -3.538352 | -3.073480 | -3.776720 | -3.597058 | -4.333160 | 0.534072 | 0.525854 | nan | -6.571464 | nan | 0.067709 | 0.362069 | 0.379310 | 951.776400 | 871.013600 | -25.000000 | -0.699699 | -2886.616348 | -0.701669 | -0.703240 | -0.736103 | -0.008218 | nan | nan | 0.017241 | -80.762800 |
| R2_1_MATCHED | 180 | 45 | HOLD_B | 416.000000 | 396.000000 | -7.296483 | -9.881394 | -3035.337000 | -3913.031977 | -8.219177 | -10.857350 | -9.053919 | -11.582485 | -11.243558 | -13.540524 | 0.497596 | 0.464646 | -15.938002 | -19.358211 | 1.188171 | -0.422271 | 0.166667 | 0.000000 | 0.648000 | 5.491100 | -20.000000 | -2.584911 | -877.694977 | -2.638173 | -2.528566 | -2.296967 | -0.032950 | -3.420209 | -1.610441 | -0.166667 | 4.843100 |
| R2_1_MATCHED | 180 | 60 | DEV | 4241.000000 | 4183.000000 | -2.683121 | -2.881579 | -11379.116224 | -12053.646865 | -3.036831 | -3.240242 | -3.212967 | -3.412273 | -3.711269 | -3.895586 | 0.534780 | 0.527851 | -6.348238 | -6.547226 | 0.920643 | 0.782358 | 0.431034 | 0.396552 | 806.660000 | 751.981600 | -58.000000 | -0.198458 | -674.530641 | -0.203411 | -0.199306 | -0.184317 | -0.006929 | -0.198988 | -0.138285 | -0.034483 | -54.678400 |
| R2_1_MATCHED | 180 | 60 | HOLD_B | 423.000000 | 402.000000 | -9.605011 | -7.460172 | -4062.919787 | -2998.988995 | -10.517870 | -8.415487 | -11.344193 | -9.123640 | -13.150343 | -11.115734 | 0.513002 | 0.502488 | -16.611354 | nan | -2.085643 | nan | 0.166667 | 0.166667 | 3.855800 | 10.447800 | -21.000000 | 2.144840 | 1063.930791 | 2.102383 | 2.220553 | 2.034610 | -0.010515 | nan | nan | 0.000000 | 6.592000 |
| R2_1_MATCHED | 180 | 90 | DEV | 4072.000000 | 4038.000000 | -3.526323 | -5.286667 | -14359.187566 | -21347.559953 | -3.894924 | -5.658808 | -4.141812 | -5.908213 | -4.661233 | -6.400915 | 0.533890 | 0.527737 | -6.663128 | -8.814252 | -0.328830 | -1.705683 | 0.344828 | 0.310345 | 684.409200 | 650.816600 | -34.000000 | -1.760344 | -6988.372388 | -1.763884 | -1.766401 | -1.739682 | -0.006153 | -2.151124 | -1.376853 | -0.034483 | -33.592600 |
| R2_1_MATCHED | 180 | 90 | HOLD_B | 375.000000 | 366.000000 | -4.439788 | -3.488579 | -1664.920535 | -1276.819801 | -5.694481 | -4.771603 | -6.716776 | -5.816639 | -9.259364 | -8.280268 | 0.517333 | 0.513661 | -15.062370 | -13.549190 | 6.528234 | 6.448746 | 0.500000 | 0.166667 | -5.154900 | 6.677700 | -9.000000 | 0.951209 | 388.100734 | 0.922878 | 0.900137 | 0.979096 | -0.003672 | 1.513180 | -0.079488 | -0.333333 | 11.832600 |

## k45_gate_direction_r2_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2.py`: `7 passed in 1.89s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T02:54:04.679176+00:00 |
| run_finished_utc | 2026-10-01T05:21:56.324353+00:00 |
| runtime_seconds | 8871.645177 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| cost_bps | 4.0 |
| entry | close[t] |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| catboost_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": -1, "verbose": false} |
| pw_bootstrap_reps | 20000 |
| fixed_bootstrap_reps | 999 |
| frozen_hypotheses | {"R2-1": "Separate binary long and short models with train-only payoff thresholds improve directional net at h=45.", "R2-2": "Allowing up to three or all overlapping R2-1 and multiclass signals changes trade and daily-unit net.", "R2-3": "Removing or residualizing fade-named features changes the three-class score ordering and net.", "R2-4": "Directional gross and net vary monotonically into the extreme score tails.", "R2-5": "Fixed daily and event-time block bootstrap intervals remain available when PW selection is unmeasurable."} |
| local_data_only | True |
| feature_cache_used | False |
| live_orders | 0 |
| patchtst_new_fits | 0 |
| manifest_verified_utc | 2026-10-01T05:24:15.006371+00:00 |
| aggregation_runtime_seconds | 423.70152240013704 |
| model_runtime_seconds | {"R2-1_LONG_h45": 2518.3, "R2-1_SHORT_h45": 3165.4, "R2-1_SHORT_h5": 3544.0, "R2-1_SHORT_h15": 3592.9, "R2-1_LONG_h60": 3793.7, "R2-1_LONG_h15": 4267.2, "R2-3_EXCLUDE": 1160.7, "R2-3_RESIDUAL": 1429.5} |

### out_of_sample_result (원문)

```text
{
 "R2-1": [
  {
   "segment": "DEV",
   "strategy": "MODEL",
   "book": "SINGLE",
   "net_mean_bps": -2.951872851797247,
   "pw_status": "MEASURABLE",
   "pw_error": "",
   "pw_block": 2.276945138966366,
   "pw_ci95_lower": -5.159057102271536,
   "pw_ci95_upper": -0.8122241733111433,
   "calendar_days": 1758,
   "trade_days": 1294,
   "zero_day_share": 0.26393629124004553,
   "pw_bootstrap_reps": 20000,
   "fixed_bootstrap_reps": 999,
   "daily_fixed_blocks": "{\"7\":[-5.188327780567539,-0.7875781604041006],\"14\":[-5.140372558976334,-0.8374715545953295],\"30\":[-5.305269214876751,-0.9521436383168704]}",
   "event_fixed_blocks": "{\"20\":[-5.23490450653769,-0.9048922504074377],\"50\":[-5.264206877486213,-0.8442624045776541]}",
   "daily_pnl_pw_status": "MEASURABLE",
   "daily_pnl_pw_error": "",
   "daily_pnl_pw_block": 2.276945138966376,
   "daily_pnl_pw_ci95_lower": -22.690460474837437,
   "daily_pnl_pw_ci95_upper": -3.572307911286435,
   "daily_pnl_calendar_days": 1758,
   "daily_pnl_trade_days": 1294,
   "daily_pnl_zero_day_share": 0.26393629124004553,
   "daily_pnl_pw_bootstrap_reps": 20000,
   "daily_pnl_fixed_bootstrap_reps": 999,
   "daily_pnl_daily_fixed_blocks": "{\"7\":[-22.819198179378937,-3.463910316407576],\"14\":[-22.60828249488345,-3.6833504323839854],\"30\":[-23.333527627660544,-4.187698868865752]}",
   "daily_pnl_event_fixed_blocks": "{\"20\":[-23.024050992348926,-3.9798787714165957],\"50\":[-23.152928086873295,-3.713217811259643]}",
   "daily_pnl_mean_bps": -12.982867400509848,
   "n": 7732,
   "direction_hit_rate": 0.5293585100879462,
   "break_even_hit_rate": 0.5562401030852293,
   "correct_net_mean_bps": 48.72935887956662,
   "wrong_net_mean_bps": -61.08083176261679,
   "gross_mean_bps": 1.0481271482027534,
   "trimmed_top2_net_mean_bps": -3.292462366582974,
   "monthly_positive_share": 0.27586206896551724,
   "positive_months": 16,
   "months": 58
  },
  {
   "segment": "DEV",
   "strategy": "RANDOM_DIRECTION",
   "book": "SAME_ENTRIES",
   "net_mean_bps": -4.816446320643781,
   "pw_status": "MEASURABLE",
   "pw_error": "",
   "pw_block": 1.4337103806952616,
   "pw_ci95_lower": -6.613171289856601,
   "pw_ci95_upper": -3.015689378770234,
   "calendar_days": 1758,
   "trade_days": 1294,
   "zero_day_share": 0.26393629124004553,
   "pw_bootstrap_reps": 20000,
   "fixed_bootstrap_reps": 999,
   "daily_fixed_blocks": "{\"7\":[-6.638430691245052,-3.0248118677352145],\"14\":[-6.630012237502406,-3.0172386039496626],\"30\":[-6.8028696827550075,-2.837580329347654]}",
   "event_fixed_blocks": "{\"20\":[-6.520988473639828,-2.9752310326575433],\"50\":[-6.486780674145261,-3.1536418058814535]}",
   "daily_pnl_pw_status": "MEASURABLE",
   "daily_pnl_pw_error": "",
   "daily_pnl_pw_block": 1.4337103806952358,
   "daily_pnl_pw_ci95_lower": -29.08591604844756,
   "daily_pnl_pw_ci95_upper": -13.263543957139488,
   "daily_pnl_calendar_days": 1758,
   "daily_pnl_trade_days": 1294,
   "daily_pnl_zero_day_share": 0.26393629124004553,
   "daily_pnl_pw_bootstrap_reps": 20000,
   "daily_pnl_fixed_bootstrap_reps": 999,
   "daily_pnl_daily_fixed_blocks": "{\"7\":[-29.19701143612427,-13.303666303372149],\"14\":[-29.1599855633496,-13.270357727951446],\"30\":[-29.92024367864701,-12.480188342728113]}",
   "daily_pnl_event_fixed_blocks": "{\"20\":[-28.680479452891444,-13.085600878559816],\"50\":[-28.530027401872086,-13.870283528484304]}",
   "daily_pnl_mean_bps": -21.18359667304762,
   "n": 7732,
   "direction_hit_rate": 0.4997413347128815,
   "break_even_hit_rate": 0.5437055172106461,
   "correct_net_mean_bps": 49.98882631043102,
   "wrong_net_mean_bps": -59.56504338539896,
   "gross_mean_bps": -0.8164463206437809,
   "trimmed_top2_net_mean_bps": -5.025548104184622,
   "monthly_positive_share": 0.1896551724137931,
   "positive_months": 11,
   "months": 58
  },
  {
   "segment": "HOLD_B",
   "strategy": "MODEL",
   "book": "SINGLE",
   "net_mean_bps": -2.6162613410091535,
   "pw_status": "MEASURABLE",
   "pw_error": "",
   "pw_block": 2.3256769954128753,
   "pw_ci95_lower": -7.60988398639595,
   "pw_ci95_upper": 2.490029195034675,
   "calendar_days": 180,
   "trade_days": 139,
   "zero_day_share": 0.22777777777777777,
   "pw_bootstrap_reps": 20000,
   "fixed_bootstrap_reps": 999,
   "daily_fixed_blocks": "{\"7\":[-7.642498270683861,2.084208485008929],\"14\":[-7.3443368774790425,1.7689922184240428],\"30\":[-6.675430680009564,1.0662968147288665]}",
   "event_fixed_blocks": "{\"20\":[-7.977706285603711,2.5619015720103113],\"50\":[-7.58312256525342,1.931608443898749]}",
   "daily_pnl_pw_status": "MEASURABLE",
   "daily_pnl_pw_error": "",
   "daily_pnl_pw_block": 2.325676995412875,
   "daily_pnl_pw_ci95_lower": -29.84765607997523,
   "daily_pnl_pw_ci95_upper": 9.766447842747104,
   "daily_pnl_calendar_days": 180,
   "daily_pnl_trade_days": 139,
   "daily_pnl_zero_day_share": 0.22777777777777777,
   "daily_pnl_pw_bootstrap_reps": 20000,
   "daily_pnl_fixed_bootstrap_reps": 999,
   "daily_pnl_daily_fixed_blocks": "{\"7\":[-29.975576550571155,8.17472883564612],\"14\":[-28.806121308334497,6.938380590040948],\"30\":[-26.182522556037508,4.182253062214333]}",
   "daily_pnl_event_fixed_blocks": "{\"20\":[-31.290336875756743,10.04834727688492],\"50\":[-29.74269183927168,7.576197563291787]}",
   "daily_pnl_mean_bps": -10.26155837084701,
   "n": 706,
   "direction_hit_rate": 0.5311614730878187,
   "break_even_hit_rate": 0.5580313070231623,
   "correct_net_mean_bps": 43.03359701269604,
   "wrong_net_mean_bps": -54.334378811218954,
   "gross_mean_bps": 1.3837386589908471,
   "trimmed_top2_net_mean_bps": -3.4716492033794255,
   "monthly_positive_share": 0.16666666666666666,
   "positive_months": 1,
   "months": 6
  },
  {
   "segment": "HOLD_B",
   "strategy": "RANDOM_DIRECTION",
   "book": "SAME_ENTRIES",
   "net_mean_bps": -7.040304709802453,
   "pw_status": "MEASURABLE",
   "pw_error": "",
   "pw_block": 4.679882068693194,
   "pw_ci95_lower": -11.404968199893872,
   "pw_ci95_upper": -2.4659883068830597,
   "calend
```

- 출력 해시 확인: 30/30 일치

### REPORT.md 앞 150줄 (전체 416줄, 원문)

# K45 gate direction R2

## Run

```json
{
  "run_started_utc": "2026-10-01T02:54:04.679176+00:00",
  "run_finished_utc": "2026-10-01T05:21:56.324353+00:00",
  "runtime_seconds": 8871.645177,
  "aggregation_runtime_seconds": 423.70152240013704,
  "data_cutoff_utc": "2026-06-30T23:59:00+00:00",
  "cost_bps": 4.0,
  "entry": "close[t]",
  "segments": {
    "DEV": "pilot_fold <= 605",
    "HOLD_B": "pilot_fold >= 606; exploratory"
  },
  "catboost_params": {
    "iterations": 500,
    "depth": 4,
    "learning_rate": 0.05,
    "l2_leaf_reg": 3,
    "random_seed": 20261001,
    "thread_count": -1,
    "verbose": false
  },
  "pw_bootstrap_reps": 20000,
  "fixed_bootstrap_reps": 999,
  "frozen_hypotheses": {
    "R2-1": "Separate binary long and short models with train-only payoff thresholds improve directional net at h=45.",
    "R2-2": "Allowing up to three or all overlapping R2-1 and multiclass signals changes trade and daily-unit net.",
    "R2-3": "Removing or residualizing fade-named features changes the three-class score ordering and net.",
    "R2-4": "Directional gross and net vary monotonically into the extreme score tails.",
    "R2-5": "Fixed daily and event-time block bootstrap intervals remain available when PW selection is unmeasurable."
  },
  "local_data_only": true,
  "feature_cache_used": false,
  "live_orders": 0,
  "patchtst_new_fits": 0
}
```

## R2-1 arm metrics

| segment | arm | horizon | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | daily_pnl_pw_status | daily_pnl_pw_error | daily_pnl_pw_block | daily_pnl_pw_ci95_lower | daily_pnl_pw_ci95_upper | daily_pnl_calendar_days | daily_pnl_trade_days | daily_pnl_zero_day_share | daily_pnl_pw_bootstrap_reps | daily_pnl_fixed_bootstrap_reps | daily_pnl_daily_fixed_blocks | daily_pnl_event_fixed_blocks | daily_pnl_mean_bps | n | direction_hit_rate | break_even_hit_rate | correct_net_mean_bps | wrong_net_mean_bps | gross_mean_bps | trimmed_top2_net_mean_bps | monthly_positive_share | positive_months | months |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | LONG | 15 | -2.6054479196948748 | MEASURABLE |  | 2.411233206505147 | -3.9024544620766557 | -1.2995222552264192 | 1758 | 1160 | 0.34015927189988626 | 20000 | 999 | {"7":[-3.8674150207923628,-1.3123817541544356],"14":[-3.896900622816854,-1.122576263718192],"30":[-3.9636055296255677,-1.2207547936303944]} | {"20":[-3.9802370459517937,-1.243346330117269],"50":[-3.8348316387209254,-1.253960182357927]} | MEASURABLE |  | 2.411233206505147 | -14.87061572323742 | -4.951933781434371 | 1758 | 1160 | 0.34015927189988626 | 20000 | 999 | {"7":[-14.737095121892954,-5.000935933492873],"14":[-14.849452373293452,-4.277666888878154],"30":[-15.103636770740392,-4.651784051495947]} | {"20":[-15.167012497628608,-4.737870913228452],"50":[-14.61293353116693,-4.778315848473123]} | -9.928268267369718 | 6699 | 0.5430661292730258 | 0.5762416304766856 | 33.27999042275248 | -45.25530897484792 | 1.3945520803051252 | -2.790920215002432 | 0.3103448275862069 | 18 | 58 |
| DEV | LONG | 45 | -2.4685645169134274 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 1160 | 0.34015927189988626 | 0 | 999 | {"7":[-4.566720835189197,-0.08466080948711907],"14":[-4.901720286379657,-0.17671501642092657],"30":[-4.6827795476133804,0.04692760895314363]} | {"20":[-4.792509290345888,-0.10624837189753134],"50":[-4.778018380069821,-0.24136996816983025]} | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 1160 | 0.34015927189988626 | 0 | 999 | {"7":[-23.942813389043685,-0.4438672815939597],"14":[-25.699178543550147,-0.926497330120327],"30":[-24.551296410894487,0.24603627515437765]} | {"20":[-25.126597343070515,-0.5570484890668936],"50":[-25.050623099603904,-1.265476107293166]} | -12.942411349482969 | 9217 | 0.5326027991754367 | 0.5538584244964603 | 51.8135432938114 | -64.323454777556 | 1.5314354830865722 | -2.6705923305452823 | 0.43103448275862066 | 25 | 58 |
| DEV | LONG | 60 | -2.4588664125046527 | MEASURABLE |  | 3.5624988833815774 | -5.046594655681403 | 0.21781983367371094 | 1758 | 1157 | 0.34186575654152446 | 20000 | 999 | {"7":[-4.928616670930098,0.3913185243829824],"14":[-4.902778647566931,-0.11055403830120802],"30":[-4.835296542674758,-0.27416022391766726]} | {"20":[-5.195492714554069,0.17691197471351128],"50":[-4.77972036819788,0.205739783666123]} | MEASURABLE |  | 3.5624988833816063 | -25.545873629641218 | 1.1026044936645896 | 1758 | 1157 | 0.34186575654152446 | 20000 | 999 | {"7":[-24.94866880239315,1.9808552607986467],"14":[-24.817876669339235,-0.5596247934259608],"30":[-24.47628210083188,-1.387799677271639]} | {"20":[-26.29959594244405,0.8955288185298329],"50":[-24.19495537917692,1.0414552530402705]} | -12.446787374788912 | 8899 | 0.5341049556129902 | 0.5526457075956854 | 59.32793044798873 | -73.29163184374562 | 1.5411335874953471 | -2.645937687474979 | 0.46551724137931033 | 27 | 58 |
| DEV | SHORT | 5 | -1.1334503229566057 | MEASURABLE |  | 2.3863684856174308 | -2.418574874263499 | 0.17277749838111545 | 1758 | 901 | 0.48748577929465303 | 20000 | 999 | {"7":[-2.4053710916881164,0.16871463010201215],"14":[-2.459314013291788,0.14887507844123937],"30":[-2.499614977511224,0.19265803646116475]} | {"20":[-2.6185389580631746,0.31190291809906956],"50":[-2.5586573239670116,0.23960462589681097]} | MEASURABLE |  | 2.3863684856174934 | -4.537235458089334 | 0.3241298007172291 | 1758 | 901 | 0.48748577929465303 | 20000 | 999 | {"7":[-4.512465222063378,0.31650787831427163],"14":[-4.613661897517785,0.2792889696810006],"30":[-4.689266322998813,0.36142559968652854]} | {"20":[-4.912367169335798,0.5851284550004032],"50":[-4.800029496270312,0.44949718783144066]} | -2.126347647958411 | 3298 | 0.5563978168587023 | 0.5764297770053189 | 23.966491673018297 | -32.61560586814728 | 2.8665496770433943 | -1.407993265647195 | 0.3793103448275862 | 22 | 58 |
| DEV | SHORT | 15 | -3.9117935810553988 | MEASURABLE |  | 2.756788369133222 | -5.787274400587297 | -2.017118999540412 | 1758 | 983 | 0.44084186575654155 | 20000 | 999 | {"7":[-5.77827238494055,-1.9998968956949785],"14":[-5.763160261681555,-1.9644310048161069],"30":[-5.614196599155332,-2.201069067147068]} | {"20":[-5.857429280400162,-1.925770296557522],"50":[-5.647797573324159,-2.0459901813356]} | MEASURABLE |  | 2.756788369133147 | -13.273202720800883 | -4.626293405089187 | 1758 | 983 | 0.44084186575654155 | 20000 | 999 | {"7":[-13.252556459658855,-4.586794245416445],"14":[-13.217896572866884,-4.505452679987726],"30":[-12.876246125025153,-5.048185710316801]} | {"20":[-13.434104015115736,-4.416783751831575],"50":[-12.953310475337322,-4.692509903950608]} | -8.971758656891565 | 4032 | 0.5372023809523809 | 0.5866964712851287 | 32.665679473750295 | -46.36988931348259 | 0.08820641894460146 | -4.1781745209390335 | 0.29310344827586204 | 17 | 58 |
| DEV | SHORT | 45 | -4.622085984008961 | MEASURABLE |  | 2.2338567917510055 | -7.538905019702595 | -1.7272870814397843 | 1758 | 1067 | 0.3930602957906712 | 20000 | 999 | {"7":[-7.187602422785515,-1.878487332020239],"14":[-7.352074640384885,-2.026561840466118],"30":[-7.114187713664901,-2.3523336534508243]} | {"20":[-7.483108841858769,-1.8392384671285784],"50":[-7.001754255732548,-1.8924995799122644]} | MEASURABLE |  | 2.233856791751065 | -22.367991230243902 | -5.124874526046598 | 1758 | 1067 | 0.3930602957906712 | 20000 | 999 | {"7":[-21.325673627559325,-5.573486873616433],"14":[-21.81366400696682,-6.012825119380701],"30":[-21.107851600953467,-6.979392682821079]} | {"20":[-22.202443526243115,-5.45703517892075],"50":[-20.774260635893654,-5.615061324699923]} | -13.71376592297539 | 5216 | 0.5164877300613497 | 0.5568757489651512 | 50.71202909855669 | -63.729978938977986 | -0.6220859840089602 | -5.030087084911829 | 0.27586206896551724 | 16 | 58 |
| HOLD_B | LONG | 15 | -1.12097250420667 | MEASURABLE |  | 4.342290079200206 | -4.064116225747996 | 1.920409544390364 | 180 | 122 | 0.32222222222222224 | 20000 | 999 | {"7":[-4.134915594813705,1.8210381436638399],"14":[-3.8083461115898727,1.6555521444299781],"30":[-3.5410089583044133,1.3100989764363693]} | {"20":[-4.256187343821621,1.997378564305852],"50":[-4.228616590204109,1.4541848629794971]} | MEASURABLE |  | 4.3422900792002235 | -11.808515478145592 | 5.5798566206453355 | 180 | 122 | 0.32222222222222224 | 20000 | 999 | {"7":[-12.014226978264283,5.291127495201033],"14":[-11.065361202008363,4.8102987307604295],"30":[-10.28859825107338,3.8065653593123376]} | {"20":[-12.366588782326163,5.803494384066438],"50":[-12.286480425981933,4.225214907434859]} | -3.2570478872227127 | 523 | 0.5793499043977055 | 0.5954314911085501 | 28.200586340736137 | -41.50475582246881 | 2.8790274957933297 | -1.6075101653835866 | 0.6666666666666666 | 4 | 6 |
| HOLD_B | LONG | 45 | -0.374512240175395 | MEASURABLE |  | 3.777750265740438 | -6.862091465211436 | 6.558255818605229 | 180 | 126 | 0.3 | 20000 | 999 | {"7":[-6.43938725296,5.562250478707595],"14":[-5.727313092207918,5.649481496138714],"30":[-5.667723422215685,5.465509383301589]} | {"20":[-7.1258136666032215,6.135784352194133],"50":[-6.520123158833987,6.102393539019269]} | MEASURABLE |  | 3.7777502657404463 | -28.89702961461259 | 27.61754394723761 | 180 | 126 | 0.3 | 20000 | 999 | {"7":[-27.116975209687116,23.423254793668654],"14":[-24.11835179940892,23.790594300406365],"30":[-23.86741307799719,23.015867291903366]} | {"20":[-30.007593107140245,25.8384696609064],"50":[-27.456963079978696,25.69785723653667]} | -1.5771126558497157 | 758 | 0.5303430079155673 | 0.5338358278932194 | 49.98373506285756 | -57.239724082364305 | 3.6254877598246047 | -1.675886453059729 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 60 | 0.9161983483884844 | MEASURABLE |  | 2.694487205605237 | -8.388196096832093 | 9.432199877296622 | 180 | 117 | 0.35 | 20000 | 999 | {"7":[-7.088320856328899,7.865187424705198],"14":[-5.19615312520269,7.598192068037495],"30":[-4.472050442968461,6.820121214537336]} | {"20":[-8.286636421783015,9.484647524759499],"50":[-7.058267071533226,8.663510780554411]} | MEASURABLE |  | 2.6944872056052396 | -38.25949441943965 | 43.021311662558546 | 180 | 117 | 0.35 | 20000 | 999 | {"7":[-32.330619016922284,35.873993753794394],"14":[-23.700231754396626,34.65619826588221],"30":[-20.397518964872766,31.10733065075086]} | {"20":[-37.79626945713257,43.26053121015302],"50":[-32.19354036515986,39.51523528241765]} | 4.178882466816365 | 821 | 0.5310596833130329 | 0.5230430261334023 | 54.50990131139431 | -59.7769302019246 | 4.916198348388485 | -0.4085414555285554 | 0.5 | 3 | 6 |
| HOLD_B | SHORT | 5 | -3.8017101818339047 | MEASURABLE |  | 21.12426407746893 | -6.894820748668222 | -0.6102012381541719 | 180 | 59 | 0.6722222222222223 | 20000 | 999 | {"7":[-8.180919219391315,0.5420949958679118],"14":[-7.217925879178079,-0.25692029915458026],"30":[-6.699917347400807,-0.7921302561145889]} | {"20":[-7.331159830788401,-0.20751430905923263],"50":[-6.787604454062984,-1.039219381231407]} | MEASURABLE |  | 21.124264077469185 | -4.251806128345397 | -0.3762907635284034 | 180 | 59 | 0.6722222222222223 | 20000 | 999 | {"7":[-5.044900185291315,0.3342919141185403],"14":[-4.45105429215981,-0.1584341844786561],"30":[-4.131615697563825,-0.48848032460399127]} | {"20":[-4.520881895652847,-0.12796715725319352],"50":[-4.18568941333884,-0.6408519517593663]} | -2.3443879454642413 | 111 | 0.5675675675675675 | 0.6344404332032727 | 20.781994519700785 | -36.06782260259819 | 0.19828981816609478 | -5.4862459952805205 | 0.3333333333333333 | 2 | 6 |
| HOLD_B | SHORT | 15 | -1.8621163845086697 | MEASURABLE |  | 15.264689753721706 | -5.8729447799349765 | 2.1612817768475656 | 180 | 95 | 0.4722222222222222 | 20000 | 999 | {"7":[-6.212673743640581,2.313395364478618],"14":[-5.942042741697589,2.2147565323453016],"30":[-5.3119583084249555,1.9562805494997608]} | {"20":[-6.771610072828271,2.704241022185289],"50":[-5.999679931779394,2.4341592468051347]} | MEASURABLE |  | 15.264689753721765 | -8.646279814904267 | 3.1818870603589335 | 180 | 95 | 0.4722222222222222 | 20000 | 999 | {"7":[-9.146436344804169,3.4058320643713085],"14":[-8.748007369721435,3.2606137837305944],"30":[-7.820383065181165,2.8800796978746677]} | {"20":[-9.969314829441615,3.981243727106129],"50":[-8.832862121786338,3.5836233355742255]} | -2.741449121637763 | 265 | 0.5094339622641509 | 0.5347423468677739 | 34.23228753966183 | -39.344766613454965 | 2.1378836154913308 | -3.14699253663908 | 0.3333333333333333 | 2 | 6 |
| HOLD_B | SHORT | 45 | -3.0023577559744172 | MEASURABLE |  | 14.781985151545355 | -9.56025595443164 | 3.1935089447103078 | 180 | 108 | 0.4 | 20000 | 999 | {"7":[-9.275805084446478,3.3984677345861716],"14":[-9.504391680209375,3.404263534032661],"30":[-9.326626142235218,2.775502939459609]} | {"20":[-10.122948977997112,3.5567524090894462],"50":[-9.338176997447661,4.2506702338276785]} | MEASURABLE |  | 14.781985151545497 | -23.688189753758408 | 7.912805496337755 | 180 | 108 | 0.4 | 20000 | 999 | {"7":[-22.983383709239618,8.420647831252381],"14":[-23.549770496518782,8.435008534325368],"30":[-23.109306996871773,6.877079505549906]} | {"20":[-25.082418023259528,8.81284208029941],"50":[-23.137927449231455,10.532216246039694]} | -7.439175328692167 | 446 | 0.531390134529148 | 0.5594061343975264 | 47.21660536268779 | -59.94922023981624 | 0.9976422440255833 | -4.930219333029814 | 0.3333333333333333 | 2 | 6 |

## R2-1 year and 30d trend

| segment | arm | horizon | dimension | value | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | daily_pnl_pw_status | daily_pnl_pw_error | daily_pnl_pw_block | daily_pnl_pw_ci95_lower | daily_pnl_pw_ci95_upper | daily_pnl_calendar_days | daily_pnl_trade_days | daily_pnl_zero_day_share | daily_pnl_pw_bootstrap_reps | daily_pnl_fixed_bootstrap_reps | daily_pnl_daily_fixed_blocks | daily_pnl_event_fixed_blocks | daily_pnl_mean_bps | n | direction_hit_rate | break_even_hit_rate | correct_net_mean_bps | wrong_net_mean_bps | gross_mean_bps | trimmed_top2_net_mean_bps | monthly_positive_share | positive_months | months |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | LONG | 15 | year | 2021 | -0.5677439436058018 | MEASURABLE |  | 13.013782692983945 | -3.1441290103119757 | 2.001560589163871 | 1758 | 204 | 0.8839590443686007 | 20000 | 999 | {"7":[-3.190539198775963,1.7431991777223634],"14":[-3.16100921842569,2.0632490631619866],"30":[-2.8135777714139705,1.76626434983393]} | {"20":[-3.140057614619738,2.323559559062632],"50":[-3.6316725348146006,2.1611666027425613]} | MEASURABLE |  | 13.013782692983902 | -3.1083596245291574 | 1.9787897064656796 | 1758 | 204 | 0.8839590443686007 | 20000 | 999 | {"7":[-3.1542418245009984,1.723367560228315],"14":[-3.125047793870259,2.0397763775742126],"30":[-2.7815689230475766,1.7461703299267706]} | {"20":[-3.104334547331684,2.2971254343861487],"50":[-3.590356578787133,2.136579951971883]} | -0.5612849681381592 | 1738 | 0.5483314154200231 | 0.5545614818665497 | 40.59266832699635 | -50.53700877657886 | 3.4322560563941984 | -1.0838798951006554 | 0.4 | 4 | 10 |
| DEV | LONG | 15 | year | 2022 | -3.924868110776813 | MEASURABLE |  | 2.8705256551687746 | -7.13741173424682 | -0.19838025076995258 | 1758 | 237 | 0.8651877133105802 | 20000 | 999 | {"7":[-7.098918068629774,-0.009587076709523856],"14":[-7.425020591294844,0.7952931187690102],"30":[-7.505746246954658,0.8554181068476452]} | {"20":[-6.677233681148969,-0.7555505910469029],"50":[-7.016682026600627,-0.8573939507900077]} | MEASURABLE |  | 2.87052565516878 | -5.627106179559801 | -0.15640217722821959 | 1758 | 237 | 0.8651877133105802 | 20000 | 999 | {"7":[-5.596757931240601,-0.007558412013290106],"14":[-5.853855824536195,0.6270058376643468],"30":[-5.9174996008414045,0.6744081320197854]} | {"20":[-5.264303687185717,-0.5956729915762304],"50":[-5.53192337250766,-0.6759658792917849]} | -3.0943499439912756 | 1386 | 0.5216450216450217 | 0.5693119773847967 | 35.46258953234153 | -46.87680155870224 | 0.07513188922318739 | -4.765478218906501 | 0.25 | 3 | 12 |
| DEV | LONG | 15 | year | 2023 | -2.4984721017711933 | MEASURABLE |  | 2.6393046603745787 | -5.303143046305399 | 0.5074574494001762 | 1758 | 252 | 0.856655290102389 | 20000 | 999 | {"7":[-5.448472070211125,0.6951199136770412],"14":[-5.449658924016056,1.0883142062661841],"30":[-5.600155072027571,1.4469648049094292]} | {"20":[-5.234623104066771,0.37973282575927314],"50":[-5.778858622021246,0.5307322903148832]} | MEASURABLE |  | 2.639304660374531 | -3.1764559884866763 | 0.3039548886338934 | 1758 | 252 | 0.856655290102389 | 20000 | 999 | {"7":[-3.263504601781771,0.4163602213321833],"14":[-3.2642154988560406,0.6518742088726941],"30":[-3.354359096043838,0.8666973490156171]} | {"20":[-3.1354141800809483,0.22745089051450673],"50":[-3.4613982531219403,0.31789596228758077]} | -1.4965250985011753 | 1053 | 0.5745489078822412 | 0.6164046229235953 | 22.897765503393778 | -36.794730474817634 | 1.5015278982288067 | -2.940694401789969 | 0.4166666666666667 | 5 | 12 |
| DEV | LONG | 15 | year | 2024 | -2.7937382878652524 | MEASURABLE |  | 1.9096942039626128 | -5.395725772837152 | -0.17362221888915208 | 1758 | 244 | 0.8612059158134243 | 20000 | 999 | {"7":[-5.240941567663128,0.08829671037787756],"14":[-5.583626817802904,0.3047698396858327],"30":[-5.606280778985628,0.9721637386087703]} | {"20":[-5.530124782927192,-0.13462699098064856],"50":[-5.16743687237142,-0.39626370285453705]} | MEASURABLE |  | 1.90969420396257 | -4.705146535699203 | -0.1514009451403937 | 1758 | 244 | 0.8612059158134243 | 20000 | 999 | {"7":[-4.57017259569257,0.07699593686553596],"14":[-4.868998812111242,0.26576346088659974],"30":[-4.888753375531669,0.8477400519267495]} | {"20":[-4.822344307296586,-0.11739657404628012],"50":[-4.506075497921154,-0.34554735863254127]} | -2.4361779267903487 | 1533 | 0.5420743639921722 | 0.5769945613727288 | 33.84191896138144 | -46.16158896325556 | 1.2062617121347472 | -3.0828574542290377 | 0.25 | 3 | 12 |
| DEV | LONG | 15 | year | 2025 | -4.159350374165744 | MEASURABLE |  | 9.019427390252314 | -7.472795451406149 | -0.31988898869532045 | 1758 | 223 | 0.873151308304892 | 20000 | 999 | {"7":[-7.417990877485062,-0.45041592252599383],"14":[-7.556812443096243,0.38637439475653856],"30":[-7.997611861927605,0.3317277153693503]} | {"20":[-7.149514274687917,-1.4388417319841351],"50":[-7.340430542742797,-0.9773047639668451]} | MEASURABLE |  | 9.01942739025231 | -4.203978783527197 | -0.17996030137637087 | 1758 | 223 | 0.873151308304892 | 20000 | 999 | {"7":[-4.173147313898108,-0.25339098258144377],"14":[-4.251244315257241,0.21736306963264873],"30":[-4.499225330743143,0.18662042690576408]} | {"20":[-4.022110135191323,-0.8094507809626306],"50":[-4.129514110792166,-0.5498034195467609]} | -2.3399303299487597 | 989 | 0.531850353892821 | 0.5922397220493266 | 28.084709551334388 | -40.79083098067345 | -0.15935037416574355 | -4.784565079049758 | 0.25 | 3 | 12 |
| DEV | LONG | 15 | trend_30d | -1 | -2.918574983666375 | MEASURABLE |  | 2.946116897564934 | -4.836615855989081 | -0.9120906412038114 | 1758 | 600 | 0.658703071672355 | 20000 | 999 | {"7":[-4.881089646766049,-0.8745417931349575],"14":[-4.771179962606933,-0.5318719497278614],"30":[-4.945800308720429,-0.8388109997345228]} | {"20":[-4.799896288358791,-0.9717137867241423],"50":[-4.891592520613758,-1.1001568634378183]} | MEASURABLE |  | 2.946116897564784 | -9.80804068634872 | -1.8496036040338923 | 1758 | 600 | 0.658703071672355 | 20000 | 999 | {"7":[-9.898227867304316,-1.7734593245313324],"14":[-9.675345032248998,-1.0785685442433453],"30":[-10.02945284447568,-1.701001828244343]} | {"20":[-9.733578081910723,-1.9705117461157693],"50":[-9.919526357217315,-2.2309779397928278]} | -5.91849818928932 | 3565 | 0.5304347826086957 | 0.5645540528519468 | 37.24820721617282 | -48.292162283484735 | 1.0814250163336256 | -3.267363705474572 | 0.3877551020408163 | 19 | 49 |
| DEV | LONG | 15 | trend_30d | 1 | -2.249258390958947 | MEASURABLE |  | 1.3561079584773341 | -3.981287603312332 | -0.4637719153040305 | 1758 | 624 | 0.6450511945392492 | 20000 | 999 | {"7":[-3.9494071005247227,-0.3916322839889108],"14":[-4.11243940210671,-0.29787570149876963],"30":[-3.9725642570286723,-0.33410119621665024]} | {"20":[-4.020043518647146,-0.5912966071038177],"50":[-4.0233662780617045,-0.6170121680246146]} | MEASURABLE |  | 1.3561079584772933 | -7.0974717569857795 | -0.826769728420381 | 1758 | 624 | 0.6450511945392492 | 20000 | 999 | {"7":[-7.040638141663567,-0.6981658578052388],"14":[-7.331277068374553,-0.5310252835593006],"30":[-7.081920581073893,-0.5956047491144845]} | {"20":[-7.166562222662214,-1.054108968522962],"50":[-7.172485731197606,-1.09995229498813]} | -4.009770078080399 | 3134 | 0.5574345883854499 | 0.5893051703962676 | 28.98468535328605 | -41.59006568814425 | 1.7507416090410526 | -2.4601907028359586 | 0.28846153846153844 | 15 | 52 |
| DEV | LONG | 45 | year | 2021 | 0.049434012346210386 | MEASURABLE |  | 1.8378738638540488 | -4.76608532423256 | 5.247900214193167 | 1758 | 209 | 0.8811149032992036 | 20000 | 999 | {"7":[-4.58253899818719,4.935364611566604],"14":[-5.122129137197022,5.336737922423656],"30":[-5.2343769547923005,4.974860557611586]} | {"20":[-6.560744230536937,5.923185653212318],"50":[-6.325886056716523,5.659400474699751]} | MEASURABLE |  | 1.837873863854225 | -5.945406778180775 | 6.546442076067022 | 1758 | 209 | 0.8811149032992036 | 20000 | 999 | {"7":[-5.716443699103718,6.156572578592729],"14":[-6.389550169438335,6.657261811078077],"30":[-6.5295726176671005,6.205841412310807]} | {"20":[-8.184136574270482,7.388820328495238],"50":[-7.891165029794839,7.059764073388263]} | 0.0616659778584982 | 2193 | 0.540811673506612 | 0.5404555845298653 | 63.79620204909667 | -75.02868603888123 | 4.049434012346211 | -0.7979645753119436 | 0.5 | 5 | 10 |
| DEV | LONG | 45 | year | 2022 | -10.268636368597445 | MEASURABLE |  | 4.637552245985175 | -17.589543031231926 | -1.6996784589947538 | 1758 | 237 | 0.8651877133105802 | 20000 | 999 | {"7":[-17.497682381250197,-1.7783482432518305],"14":[-17.374646701562114,-1.7580800578090212],"30":[-17.855421960727938,-1.3418814491084525]} | {"20":[-16.495726835476134,-4.217287495280058],"50":[-16.12447255065851,-4.2375089471193395]} | MEASURABLE |  | 4.637552245986025 | -17.089271613961827 | -1.651337205895306 | 1758 | 237 | 0.8651877133105802 | 20000 | 999 | {"7":[-17.000023610452946,-1.7277695105092494],"14":[-16.88048723906094,-1.7080777808523244],"30":[-17.347588571628997,-1.3037164477121532]} | {"20":[-16.0265650938528,-4.097341889612256],"50":[-15.665869804621586,-4.116988214834944]} | -9.976581864371125 | 1708 | 0.4853629976580796 | 0.5575137033847657 | 62.975556957700306 | -79.34649332821158 | -6.268636368597445 | -11.06449906034667 | 0.16666666666666666 | 2 | 12 |
| DEV | LONG | 45 | year | 2023 | -1.1980604162362858 | MEASURABLE |  | 17.2842475527752 | -4.8763075920708125 | 2.703638636005825 | 1758 | 239 | 0.8640500568828214 | 20000 | 999 | {"7":[-4.843253981634066,2.7019721856145336],"14":[-4.764137557038431,2.429349678906281],"30":[-4.709124823282329,2.835045821175696]} | {"20":[-5.8183708879859175,2.802997689452851],"50":[-5.143552181954553,2.8618499594429667]} | MEASURABLE |  | 17.28424755277398 | -4.648857522361007 | 2.577530349229689 | 1758 | 239 | 0.8640500568828214 | 20000 | 999 | {"7":[-4.617345661671595,2.5759416286063583],"14":[-4.541919536744237,2.3160353025295537],"30":[-4.489472812184952,2.70280818901621]} | {"20":[-5.546979299354045,2.6722549075784974],"50":[-4.9036367787007,2.7283620773756665]} | -1.1421781897679264 | 1676 | 0.5542959427207638 | 0.5695514655456976 | 33.804370802274 | -44.72852708557505 | 2.801939583763714 | -1.7404809898847644 | 0.5833333333333334 | 7 | 12 |
| DEV | LONG | 45 | year | 2024 | -0.8104195504478123 | MEASURABLE |  | 19.529293904033203 | -4.493954538716165 | 3.006832773617562 | 1758 | 252 | 0.856655290102389 | 20000 | 999 | {"7":[-4.307934526822428,2.9201037188967875],"14":[-4.428212995952804,2.649810295465154],"30":[-4.630085324372009,3.262004189772516]} | {"20":[-4.944984517087416,3.7423151920156146],"50":[-4.457302947954499,3.3512469345732887]} | MEASURABLE |  | 19.52929390403277 | -5.5113572158544635 | 3.6875605574057415 | 1758 | 252 | 0.856655290102389 | 20000 | 999 | {"7":[-5.2832234583783615,3.58119659723633],"14":[-5.4307322066407,3.2497104647457054],"30":[-5.6783071441103665,4.000501156512939]} | {"20":[-6.064497507872851,4.589551509661923],"50":[-5.466407938447044,4.109947890182045]} | -0.9938933735867364 | 2156 | 0.5463821892393321 | 0.5533427355062125 | 52.004507349900535 | -64.42594499892465 | 3.189580449552188 | -1.3626164762047352 | 0.5 | 6 | 12 |
| DEV | LONG | 45 | year | 2025 | -1.0560129484665524 | MEASURABLE |  | 32.7204866625194 | -4.497505531296104 | 2.9299393657342123 | 1758 | 223 | 0.873151308304892 | 20000 | 999 | {"7":[-4.604180758303862,2.590663739408065],"14":[-4.765599479420418,2.8348546807886943],"30":[-4.400527127526789,2.8106908258365233]} | {"20":[-4.827455620839615,2.8994551903860506],"50":[-4.775699018070439,2.5134138732248554]} | MEASURABLE |  | 32.7204866625194 | -3.7965291288074727 | 2.4732821494593167 | 1758 | 223 | 0.873151308304892 | 20000 | 999 | {"7":[-3.8865780690119465,2.1868856594320114],"14":[-4.022838240875963,2.393017261826145],"30":[-3.7146656753411498,2.3726195594660435]} | {"20":[-4.075053550242315,2.4475492050812893],"50":[-4.031363676232389,2.1216758747813844]} | -0.891423899615679 | 1484 | 0.5303234501347709 | 0.5415889403732124 | 42.970878713675475 | -50.76786910069867 | 2.943987051533448 | -1.5554229254130443 | 0.4166666666666667 | 5 | 12 |
| DEV | LONG | 45 | trend_30d | -1 | -4.346094869749872 | MEASURABLE |  | 2.733835422556484 | -7.735334811327348 | -0.7784128619218986 | 1758 | 592 | 0.6632536973833902 | 20000 | 999 | {"7":[-7.467871791779675,-1.0060873679689304],"14":[-7.561019587398827,-0.8356401817157648],"30":[-7.603825774149266,-0.7489986331124814]} | {"20":[-7.868559539917219,-0.7906826187307869],"50":[-7.73363672786602,-1.122225720862048]} | MEASURABLE |  | 2.7338354225564183 | -20.4559565061778 | -2.058499087073251 | 1758 | 592 | 0.6632536973833902 | 20000 | 999 | {"7":[-19.748655267340013,-2.660580303576248],"14":[-19.994982970316997,-2.20983572514022],"30":[-20.10818317634809,-1.9807136776675645]} | {"20":[-20.80826695169239,-2.090946242593578],"50":[-20.451465954407958,-2.9677061298564666]} | -11.493171245430688 | 4649 | 0.5179608517960852 | 0.5508338799390367 | 59.38359440369857 | -72.8249399257355 | -0.3460948697498708 | -4.747524041973508 | 0.42857142857142855 | 21 | 49 |
| DEV | LONG | 45 | trend_30d | 1 | -0.5577417037924495 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 635 | 0.6387940841865757 | 0 | 999 | {"7":[-3.465437931288416,2.6145213396716844],"14":[-3.760677824540049,2.461971921250548],"30":[-3.3124812765571896,2.136999434961095]} | {"20":[-3.5671374873273605,2.4824664905935965],"50":[-3.306919677044018,2.1647056450129583]} | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 635 | 0.6387940841865757 | 0 | 999 | {"7":[-9.004619152517286,6.7935912853357685],"14":[-9.771772640784377,6.397205765797866],"30":[-8.607175467186147,5.552794891298328]} | {"20":[-9.268876019403526,6.450459003999777],"50":[-8.592724166517103,5.624786909225946]} | -1.4492401040522807 | 4568 | 0.5475043782837128 | 0.5531024353387266 | 44.52498548789047 | -55.10631485638024 | 3.4422582962075503 | -0.7905626306184154 | 0.4807692307692308 | 25 | 52 |
| DEV | LONG | 60 | year | 2021 | -1.854886659193407 | MEASURABLE |  | 4.1458900827467495 | -7.6521010816322805 | 4.703690071839192 | 1758 | 204 | 0.8839590443686007 | 20000 | 999 | {"7":[-7.795829627853406,4.711965880519882],"14":[-7.538072723718125,4.8155416596299405],"30":[-7.6143807025156995,4.5054345813323025]} | {"20":[-8.407060951265455,4.445257120007098],"50":[-8.16877403151467,4.918321535996411]} | MEASURABLE |  | 4.145890082746768 | -8.722872905341813 | 5.361885610902125 | 1758 | 204 | 0.8839590443686007 | 20000 | 999 | {"7":[-8.8867136372116,5.371319467896463],"14":[-8.592888360825345,5.48938878606299],"30":[-8.679874247918857,5.1358878845223375]} | {"20":[-9.583475623626853,5.067289686287957],"50":[-9.311844800429697,5.606550829429327]} | -2.114444178056649 | 2004 | 0.5354291417165669 | 0.5471031073007825 | 71.96118561406314 | -86.92969390860725 | 2.1451133408065917 | -2.671334298422698 | 0.7 | 7 | 10 |
| DEV | LONG | 60 | year | 2022 | -6.544082252015804 | MEASURABLE |  | 3.6367645888520133 | -13.96731577757194 | 1.6458429593604889 | 1758 | 224 | 0.8725824800910125 | 20000 | 999 | {"7":[-13.800104683231996,1.592056501926698],"14":[-12.894661116673019,1.258321139895938],"30":[-12.872526067145625,0.535632511295475]} | {"20":[-14.27492329945354,0.9238786501516465],"50":[-13.556447158624078,0.1877220493413123]} | MEASURABLE |  | 3.636764588852019 | -13.315825508083307 | 1.569074402666815 | 1758 | 224 | 0.8725824800910125 | 20000 | 999 | {"7":[-13.156413793570389,1.5177967561030972],"14":[-12.293203658443598,1.199628117443523],"30":[-12.272101074252518,0.5106485147504749]} | {"20":[-13.609085011310675,0.8807853342742682],"50":[-12.924121409473248,0.17896595830263973]} | -6.238840645266488 | 1676 | 0.4958233890214797 | 0.5371179453129157 | 73.35442031332754 | -85.1188226446789 | -2.544082252015803 | -7.380758847481408 | 0.3333333333333333 | 4 | 12 |
| DEV | LONG | 60 | year | 2023 | -1.515840398940819 | MEASURABLE |  | 10.417824049004953 | -6.202868065531189 | 3.4235735341524567 | 1758 | 262 | 0.850967007963595 | 20000 | 999 | {"7":[-6.064560946028211,3.2562151898888283],"14":[-6.163875795103193,3.296001758830508],"30":[-5.791117422820063,3.8931101146304448]} | {"20":[-7.078581237563735,4.0091962517310655],"50":[-6.107036387070612,3.1926362550803837]} | MEASURABLE |  | 10.417824049004585 | -5.920598756519415 | 3.2677795166712116 | 1758 | 262 | 0.850967007963595 | 20000 | 999 | {"7":[-5.788585476356742,3.108037024251157],"14":[-5.8833808783748704,3.146013055356958],"30":[-5.527585344421037,3.7159492447950253]} | {"20":[-6.756461499790641,3.8267527362939315],"50":[-5.829128019058288,3.0473513287968563]} | -1.446860176008359 | 1678 | 0.5441001191895113 | 0.5599140429122332 | 42.18434870794643 | -53.6704451761801 | 2.4841596010591815 | -2.0968409595429884 | 0.5 | 6 | 12 |
| DEV | LONG | 60 | year | 2024 | -0.4314470355038844 | MEASURABLE |  | 3.2704386528000686 | -5.161525901566785 | 4.356556274564384 | 1758 | 247 | 0.8594994311717861 | 20000 | 999 | {"7":[-4.929253546261366,4.465806150178994],"14":[-4.509643386202812,4.100622074434675],"30":[-4.024630387114965,3.6509200021445984]} | {"20":[-6.420550311540265,5.372021508827183],"50":[-5.826022333745489,4.828210375880532]} | MEASURABLE |  | 3.270438652800227 | -5.851490968044775 | 4.93891732378087 | 1758 | 247 | 0.8594994311717861 | 20000 | 999 | {"7":[-5.588169691523852,5.062771136124481],"14":[-5.11246829846548,4.648771214077593],"30":[-4.562621366052419,4.13895538354614]} | {"20":[-7.27881500051182,6.09012449777734],"50":[-6.604813715105091,5.473619612701859]} | -0.489120558452356 | 1993 | 0.5579528349222278 | 0.5612672916155181 | 57.11039362628124 | -73.0608758844313 | 3.5685529644961154 | -1.1284705225425944 | 0.4166666666666667 | 5 | 12 |
| DEV | LONG | 60 | year | 2025 | -2.4502088852034207 | MEASURABLE |  | 27.071892423509485 | -6.983003357104859 | 2.6966089365653545 | 1758 | 220 | 0.8748577929465301 | 20000 | 999 | {"7":[-7.092713874379076,3.249761117692369],"14":[-7.286497936434446,2.3518182954616655],"30":[-7.0358285905923506,2.251454831330255]} | {"20":[-7.637101449225151,3.005237207029836],"50":[-7.75022702460751,2.545449519175418]} | MEASURABLE |  | 27.071892423509507 | -6.1488561984062775 | 2.3744884151331216 | 1758 | 220 | 0.8748577929465301 | 20000 | 999 | {"7":[-6.245461363787689,2.861564397149055],"14":[-6.416097159044515,2.0708843693829384],"30":[-6.1953712504189635,1.9825097149597233]} | {"20":[-6.72481970614364,2.6462498273505104],"50":[-6.8244319875383574,2.2413855834377405]} | -2.1575218170050596 | 1548 | 0.5322997416020672 | 0.5538527553070945 | 50.71930812165738 | -62.96358183223837 | 1.54979111479658 | -2.9725590229009358 | 0.4166666666666667 | 5 | 12 |
| DEV | LONG | 60 | trend_30d | -1 | -3.380263798957203 | MEASURABLE |  | 7.71768278585719 | -7.0484302820365725 | 0.5106066711610051 | 1758 | 589 | 0.6649601820250285 | 20000 | 999 | {"7":[-7.197032953835549,0.7164055444147461],"14":[-6.842712548766855,0.25847990173150226],"30":[-6.970434700648948,-0.16875882967314348]} | {"20":[-7.522656563003801,0.684134925842157],"50":[-7.218006650623037,0.7166046725904156]} | MEASURABLE |  | 7.717682785857337 | -18.695580435231285 | 1.3543566027439748 | 1758 | 589 | 0.6649601820250285 | 20000 | 999 | {"7":[-19.0897409918856,1.9002269929502251],"14":[-18.14992526444786,0.6856039714301936],"30":[-18.48870137037847,-0.44762367620308297]} | {"20":[-19.95344001893435,1.8146309210477476],"50":[-19.145372589223683,1.9007551696752518]} | -8.965967061739155 | 4663 | 0.5219815569375938 | 0.5450835707786629 | 66.56292164945737 | -79.75608855509944 | 0.6197362010427971 | -3.737744152568851 | 0.46938775510204084 | 23 | 49 |
| DEV | LONG | 60 | trend_30d | 1 | -1.4445897333195166 | MEASURABLE |  | 2.0539203075196597 | -4.971361912870808 | 2.2756820532757542 | 1758 | 634 | 0.6393629124004551 | 20000 | 999 | {"7":[-5.127931390037414,2.090673351951726],"14":[-4.995873356819693,2.224632384692293],"30":[-4.592969547731426,1.733235981815498]} | {"20":[-5.108592101104392,2.208745349164845],"50":[-4.881867665234619,2.170359682185846]} | MEASURABLE |  | 2.0539203075197054 | -11.97877648630317 | 5.483384060111566 | 1758 | 634 | 0.6393629124004551 | 20000 | 999 | {"7":[-12.356039458588523,5.0375951756925055],"14":[-12.03783819083518,5.360377008849024],"30":[-11.067018773714777,4.176329703623704]} | {"20":[-12.30944035283177,5.3220963020832155],"50":[-11.763135056845185,5.2296038758471415]} | -3.4808203130497564 | 4236 | 0.5474504249291785 | 0.5597438419860555 | 51.73415356813764 | -65.77505698218711 | 2.5554102666804837 | -1.7197451051211152 | 0.47058823529411764 | 24 | 51 |
| DEV | SHORT | 5 | year | 2021 | -0.391063253092485 | MEASURABLE |  | 1.6401311727112506 | -2.7054901440808172 | 1.8938988075226084 | 1758 | 205 | 0.8833902161547212 | 20000 | 999 | {"7":[-2.699074880039206,1.9194462054007966],"14":[-2.9458843790054314,1.961840039665442],"30":[-2.9563094118995026,2.265842686656606]} | {"20":[-3.360071566734443,2.45311225751244],"50":[-3.446228356572606,2.4061829926338634]} | MEASURABLE |  | 1.640131172711415 | -1.6620758564319054 | 1.163487322027555 | 1758 | 205 | 0.8833902161547212 | 20000 | 999 | {"7":[-1.6581347385906793,1.179181969188199],"14":[-1.809758321573262,1.2052259629343713],"30":[-1.8161627786412855,1.3919852682531868]} | {"20":[-2.0642077884375447,1.5070314209974056],"50":[-2.117136874344949,1.4782011558842851]} | -0.24024363671210683 | 1080 | 0.5740740740740741 | 0.5800909586239338 | 27.29169794811814 | -37.702610959072025 | 3.608936746907515 | -1.2291047790372371 | 0.3 | 3 | 10 |
| DEV | SHORT | 5 | year | 2022 | -0.46356108283229946 | MEASURABLE |  | 2.962046052749835 | -3.2058071392726615 | 2.1359663571933836 | 1758 | 217 | 0.8765642775881684 | 20000 | 999 | {"7":[-3.4410134499107072,2.0646497236347323],"14":[-3.0391404064836625,1.943230623554089],"30":[-2.7242559518694733,1.802384809172104]} | {"20":[-3.095771055169272,2.0763492671028936],"50":[-2.89705428278378,1.794956437093985]} | MEASURABLE |  | 2.9620460527496038 | -1.7943766922890823 | 1.1955579610229736 | 1758 | 217 | 0.8765642775881684 | 20000 | 999 | {"7":[-1.9260280060933455,1.1556401183484728],"14":[-1.7010888282023107,1.0876785742760446],"30":[-1.5248395088962174,1.008843374417153]} | {"20":[-1.7327865291732427,1.162188668276022],"50":[-1.6215593937765873,1.0046855142778595]} | -0.2594676368071575 | 984 | 0.5619918699186992 | 0.5704085391042976 | 23.660414636358876 | -31.416133177293368 | 3.5364389171677004 | -0.9048581746154203 | 0.5 | 6 | 12 |
| DEV | SHORT | 5 | year | 2023 | -3.2023643863793025 | MEASURABLE |  | 2.9004140261143054 | -5.515269749991546 | -0.5606360166997004 | 1758 | 196 | 0.888509670079636 | 20000 | 999 | {"7":[-5.519992283477171,-0.12864665653825025],"14":[-5.881781152621656,0.16066426389547983],"30":[-6.171284888225808,1.0573524063093083]} | {"20":[-5.389479299293722,-0.5670581167457915],"50":[-5.625702904898365,-0.5111015541225186]} | MEASURABLE |  | 2.900414026114595 | -1.6501887875401087 | -0.16774433719225723 | 1758 | 196 | 0.888509670079636 | 20000 | 999 | {"7":[-1.6516017867513761,-0.038491547974428664],"14":[-1.7598503334919957,0.04807133265589669],"30":[-1.8464709051232426,0.31636368925983216]} | {"20":[-1.6125518267511363,-0.16966585290573666],"50":[-1.6832307895202159,-0.152923445658956]} | -0.9581590826140575 | 526 | 0.5570342205323194 | 0.6271063195007043 | 17.04161085392375 | -28.65938046109516 | 0.7976356136206976 | -3.7296650846767014 | 0.4166666666666667 | 5 | 12 |
| DEV | SHORT | 5 | year | 2024 | 0.36953128791203116 | MEASURABLE |  | 1.500968014045135 | -2.3021574612704923 | 3.1263676107405924 | 1758 | 179 | 0.8981797497155859 | 20000 | 999 | {"7":[-2.332936207434453,2.9908505053360113],"14":[-2.047500470920469,2.830313414415823],"30":[-1.9231848618799818,2.3613025700194914]} | {"20":[-2.1943010653245834,2.702813704928814],"50":[-1.9687941866030017,2.578432398794739]} | MEASURABLE |  | 1.5009680140451958 | -0.6626232510823968 | 0.8998532485977369 | 1758 | 179 | 0.8981797497155859 | 20000 | 999 | {"7":[-0.671482207600589,0.8608477563708896],"14":[-0.589326074110192,0.8146408348659924],"30":[-0.5535446758311943,0.6796468148065121]} | {"20":[-0.6315792599853476,0.7779429662650619],"50":[-0.5666722744147444,0.7421426585836957]} | 0.10636111017263236 | 506 | 0.541501976284585 | 0.5348355615147462 | 25.784896376690927 | -29.646891273835458 | 4.3695312879120305 | -0.17829432159353184 | 0.5833333333333334 | 7 | 12 |
| DEV | SHORT | 5 | year | 2025 | -6.743395597584131 | MEASURABLE |  | 37.54297420583238 | -12.585384344320039 | 1.9372550162103757 | 1758 | 104 | 0.9408418657565415 | 20000 | 999 | {"7":[-12.226466627988678,-0.3065417732952307],"14":[-12.095020374031943,-0.3435601461755313],"30":[-12.41631572121281,0.9061749677942919]} | {"20":[-11.681058843467381,-1.2264086256369415],"50":[-11.362078271571532,-1.7924549019171732]} | MEASURABLE |  | 37.542974205832486 | -1.4461021829081941 | 0.22259699276137757 | 1758 | 104 | 0.9408418657565415 | 20000 | 999 | {"7":[-1.4048613531591143,-0.03522266109526928],"14":[-1.389757744911516,-0.03947619427040705],"30":[-1.4266756403213776,0.1041224934553453]} | {"20":[-1.3421921993062633,-0.14091839725748823],"50":[-1.3055402792135664,-0.2059589819040213]} | -0.7748384019977216 | 202 | 0.47029702970297027 | 0.6030684265939718 | 20.159964324588383 | -30.629556276148517 | -2.74339559758413 | -7.633570818875841 | 0.08333333333333333 | 1 | 12 |
| DEV | SHORT | 5 | trend_30d | -1 | -0.37190054174769654 | MEASURABLE |  | 2.6231458879311256 | -2.2739205627621635 | 1.4977284562713067 | 1758 | 462 | 0.7372013651877133 | 20000 | 999 | {"7":[-2.226027989645839,1.4128361179709779],"14":[-2.2583344795733256,1.3747382523191802],"30":[-2.1866703696879344,1.2660424937247021]} | {"20":[-2.554837512782928,1.7408223700729129],"50":[-2.3457025197387598,1.4807260964395597]} | MEASURABLE |  | 2.6231458879309066 | -2.314018138100767 | 1.5241389125537614 | 1758 | 462 | 0.7372013651877133 | 20000 | 999 | {"7":[-2.265281042933001,1.4377496103812266],"14":[-2.2981572149923624,1.3989799393624185],"30":[-2.225229403510636,1.2883674751271394]} | {"20":[-2.5998886862165276,1.7715194653358632],"50":[-2.3870658747512206,1.5068367386407138]} | -0.3784585148956933 | 1789 | 0.5623253214086081 | 0.5683270307764643 | 26.74894788672776 | -35.21682202201118 | 3.6280994582523043 | -0.8774240109954592 | 0.4375 | 21 | 48 |
| DEV | SHORT | 5 | trend_30d | 1 | -2.036308214661536 | MEASURABLE |  | 1.4301553498511597 | -3.7182034747334063 | -0.2802345344082291 | 1758 | 472 | 0.7315130830489193 | 20000 | 999 | {"7":[-3.607098460353681,-0.26064235105462763],"14":[-3.54373663057434,-0.12306589063063655],"30":[-3.7285657066440887,-0.2612744432850991]} | {"20":[-3.7974745760928617,-0.17167682071700296],"50":[-3.6938882594490448,-0.1697048359164537]} | MEASURABLE |  | 1.4301553498511705 | -3.1915637334315887 | -0.24054261229925755 | 1758 | 472 | 0.7315130830489193 | 20000 | 999 | {"7":[-3.0961954361056785,-0.22372543102474385],"14":[-3.041808063445255,-0.10563505629223946],"30":[-3.200458277204749,-0.22426799483348314]} | {"20":[-3.2596070166803877,-0.1473608205130592],"50":[-3.1706924820868085,-0.14566814413989038]} | -1.7478891330627178 | 1509 | 0.5493704440026508 | 0.5899260036274607 | 20.589952528275578 | -29.620381973330453 | 1.9636917853384643 | -2.2195822543178134 | 0.38461538461538464 | 20 | 52 |
| DEV | SHORT | 15 | year | 2021 | -2.501067922851261 | MEASURABLE |  | 2.675921602274863 | -6.423748380883227 | 1.7422165982240045 | 1758 | 203 | 0.8845278725824801 | 20000 | 999 | {"7":[-6.548813506845813,1.6239111112374234],"14":[-6.2131708301636,1.8528492870046405],"30":[-5.931495369082782,2.0439172697818586]} | {"20":[-6.65517640272589,1.7297514788096517],"50":[-6.603868672295207,2.140180741297545]} | MEASURABLE |  | 2.6759216022749275 | -4.238650808773837 | 1.1495854686802955 | 1758 | 203 | 0.8845278725824801 | 20000 | 999 | {"7":[-4.321173872548947,1.0715226900087242],"14":[-4.0997031643854065,1.2225854225966883],"30":[-3.9138422230579666,1.3486598594693193]} | {"20":[-4.391356443209344,1.141360475210011],"50":[-4.357501513004806,1.4121784186036117]} | -1.650306479242016 | 1160 | 0.5431034482758621 | 0.571163229869471 | 38.22374334363651 | -50.90980584339332 | 1.4989320771487389 | -3.3689723513316383 | 0.5 | 5 | 10 |
| DEV | SHORT | 15 | year | 2022 | -3.4778278499193496 | MEASURABLE |  | 4.242294848046093 | -7.01011173518563 | 0.16777346964995887 | 1758 | 232 | 0.8680318543799772 | 20000 | 999 | {"7":[-7.001118361839911,0.22433459646509446],"14":[-6.91794904748042,0.5884479334109942],"30":[-7.279491947094386,0.45344862081378245]} | {"20":[-6.718634311636929,-0.3080845479570007],"50":[-6.520518943434878,-0.6434565417786731]} | MEASURABLE |  | 4.242294848046066 | -4.414217116524618 | 0.10564575136664622 | 1758 | 232 | 0.8680318543799772 | 20000 | 999 | {"7":[-4.4085540537865455,0.14126188753521518],"14":[-4.356182932628448,0.37054144612405526],"30":[-4.583843905252229,0.2855333465534855]} | {"20":[-4.230675872003454,-0.19399863173401632],"50":[-4.105924044586125,-0.4051799725534657]} | -2.1899632706830032 | 1107 | 0.5266485998193315 | 0.5696496752835334 | 34.805742143978264 | -46.07195248053444 | 0.5221721500806502 | -4.088946420191397 | 0.16666666666666666 | 2 | 12 |
| DEV | SHORT | 15 | year | 2023 | -6.615960822269603 | MEASURABLE |  | 1.5019238902343552 | -10.576385347708205 | -2.037033112399328 | 1758 | 207 | 0.8822525597269625 | 20000 | 999 | {"7":[-10.514811019810448,-2.039755351296529],"14":[-11.061124659845747,-1.1880364991498906],"30":[-11.582027490240288,-0.2898904968768825]} | {"20":[-9.935304500169698,-2.841983216393247],"50":[-9.548849485434634,-3.0909848826727897]} | MEASURABLE |  | 1.5019238902345748 | -4.451948326111516 | -0.8574542111350822 | 1758 | 207 | 0.8822525597269625 | 20000 | 999 | {"7":[-4.426029667041926,-0.8586000909894205],"14":[-4.6559910399805595,-0.5000836230778676],"30":[-4.875256167677923,-0.12202444123371547]} | {"20":[-4.1820963197528895,-1.1962841752736086],"50":[-4.019424698078292,-1.3010971633548736]} | -2.784875431444543 | 740 | 0.5459459459459459 | 0.6398440319561477 | 25.37621239932224 | -45.0827405291836 | -2.615960822269604 | -7.381788728466619 | 0.16666666666666666 | 2 | 12 |
| DEV | SHORT | 15 | year | 2024 | -3.9771107367566465 | MEASURABLE |  | 4.627083558914994 | -7.590992362974276 | -0.029607035913870927 | 1758 | 201 | 0.8856655290102389 | 20000 | 999 | {"7":[-7.578957611165967,0.447310554533515],"14":[-7.728474678148087,0.5899193238431666],"30":[-7.913819644556626,1.1826973937146796]} | {"20":[-7.862842867452524,-0.5144923736034812],"50":[-7.49706373862958,-0.07331128888905791]} | MEASURABLE |  | 4.627083558914422 | -2.918948144124367 | -0.011384730533470222 | 1758 | 201 | 0.8856655290102389 | 20000 | 999 | {"7":[-2.9143204466144583,0.1720033759184889],"14":[-2.9718139262958507,0.2268404225927041],"30":[-3.043084231922765,0.4547801127137616]} | {"20":[-3.0234822402718446,-0.19783665788165994],"50":[-2.882829970030486,-0.028190233952790855]} | -1.5293099306299733 | 676 | 0.5340236686390533 | 0.5891872524492592 | 29.618231380722314 | -42.47843932218491 | 0.022889263243353098 | -5.012153724710005 | 0.25 | 3 | 12 |
| DEV | SHORT | 15 | year | 2025 | -4.116961696046375 | MEASURABLE |  | 8.536020788246187 | -9.224296553241505 | 1.5460895000294625 | 1758 | 140 | 0.9203640500568828 | 20000 | 999 | {"7":[-9.688950680550048,1.6832448683404353],"14":[-8.94263745713161,1.0762157378017054],"30":[-8.66609252848939,1.6767195948474942]} | {"20":[-8.591628327478452,0.522490796944715],"50":[-7.796611220708565,0.057332914915595445]} | MEASURABLE |  | 8.53602078824613 | -1.8312170063033588 | 0.30693130575105465 | 1758 | 140 | 0.9203640500568828 | 20000 | 999 | {"7":[-1.9234606299840125,0.33415953302095336],"14":[-1.7753017477468291,0.21365147468303836],"30":[-1.72040175906872,0.3328641288974744]} | {"20":[-1.705619047946518,0.10372541987127792],"50":[-1.547791419810745,0.011381790276190684]} | -0.8173035448920277 | 349 | 0.5386819484240688 | 0.5961697191335497 | 28.92012992524404 | -42.69443514202524 | -0.11696169604637463 | -5.7355490646037985 | 0.4166666666666667 | 5 | 12 |
| DEV | SHORT | 15 | trend_30d | -1 | -2.6063201922611694 | MEASURABLE |  | 2.6997852416978048 | -5.274626158292662 | 0.17996832359303605 | 1758 | 504 | 0.7133105802047781 | 20000 | 999 | {"7":[-5.320253883082893,0.3411339437019736],"14":[-5.09090712692413,0.20768921501057092],"30":[-5.099179730320859,0.36013797730481123]} | {"20":[-5.059727578207887,-0.05240616739243009],"50":[-4.989230227270208,-0.07067498116503446]} | MEASURABLE |  | 2.699785241697918 | -6.192735148302609 | 0.21129386797272076 | 1758 | 504 | 0.7133105802047781 | 20000 | 999 | {"7":[-6.246304900274707,0.4005122069401943],"14":[-5.977037718982676,0.2438398974867737],"30":[-5.9867502635849466,0.4228241098731931]} | {"20":[-5.940431013322579,-0.06152806001022082],"50":[-5.857662792426448,-0.0829767696954713]} | -3.0599800209482684 | 2064 | 0.5416666666666666 | 0.5728239203392761 | 35.7334973669221 | -47.917013671295955 | 1.39367980773883 | -3.1016586890016806 | 0.3958333333333333 | 19 | 48 |
| DEV | SHORT | 15 | trend_30d | 1 | -5.280948598571298 | MEASURABLE |  | 1.7843616581352186 | -7.75233942190979 | -2.7430422020903706 | 1758 | 523 | 0.7025028441410694 | 20000 | 999 | {"7":[-7.569010469507004,-2.602148841363965],"14":[-7.8583408468683285,-2.5904694758390177],"30":[-7.947541402062286,-2.7769732189605687]} | {"20":[-7.595045813612014,-3.0747311201638765],"50":[-7.5599450670346915,-3.027030364005757]} | MEASURABLE |  | 1.7843616581352542 | -8.6783867931277 | -3.070709359336647 | 1758 | 523 | 0.7025028441410694 | 20000 | 999 | {"7":[-8.473158477809937,-2.9129857336769627],"14":[-8.797050504344021,-2.899911222099624],"30":[-8.896906415960508,-3.1086935693483135]} | {"20":[-8.502303845954735,-3.442019820524739],"50":[-8.463010177431327,-3.388621021822138]} | -5.911778635943295 | 1968 | 0.532520325203252 | 0.6037190143485954 | 29.392950080080375 | -44.7790418759919 | -1.280948598571297 | -5.654378991145804 | 0.32075471698113206 | 17 | 53 |
| DEV | SHORT | 45 | year | 2021 | -0.9578065721069369 | MEASURABLE |  | 21.352232136500074 | -6.586994867040001 | 4.8672988496394645 | 1758 | 197 | 0.8879408418657565 | 20000 | 999 | {"7":[-8.144754697746823,5.798258973919272],"14":[-7.464276799059751,5.321258351535653],"30":[-6.119270655351232,4.48263400130656]} | {"20":[-8.488238317908538,6.96572825715325],"50":[-7.969299888510978,5.740249070305986]} | MEASURABLE |  | 21.352232136498195 | -4.0541117441051 | 2.9956867777646856 | 1758 | 197 | 0.8879408418657565 | 20000 | 999 | {"7":[-5.0128695011156985,3.5686667859959984],"14":[-4.594054321150249,3.275086198158107],"30":[-3.7662405284925375,2.7589362852183887]} | {"20":[-5.224274095550083,4.28721158944245],"50":[-4.904881956410068,3.532963307207666]} | -0.5895032485891392 | 1082 | 0.488909426987061 | 0.4953657907406386 | 74.86287647141587 | -73.48789939312604 | 3.042193427893063 | -2.920759517740037 | 0.4 | 4 | 10 |
| DEV | SHORT | 45 | year | 2022 | -5.211942826933717 | MEASURABLE |  | 2.795076887650284 | -11.0201161428571 | 0.7700643994583878 | 1758 | 228 | 0.8703071672354948 | 20000 | 999 | {"7":[-10.997515511152029,0.743948161507249],"14":[-11.32247052110886,1.1017494379149273],"30":[-10.686255353135595,1.193332142487094]} | {"20":[-11.086312111730548,0.6818650583198593],"50":[-10.92317802211214,0.052321952141394235]} | MEASURABLE |  | 2.7950768876502208 | -7.929719522590437 | 0.5541134614989249 | 1758 | 228 | 0.8703071672354948 | 20000 | 999 | {"7":[-7.913456838229189,0.5353210604705683],"14":[-8.147283964278914,0.7927832986135477],"30":[-7.6894840851628725,0.858683253837571]} | {"20":[-7.977352003037046,0.49064806528705907],"50":[-7.859965982919144,0.037649186267848744]} | -3.7503456632941696 | 1265 | 0.4972332015810277 | 0.5418188820902764 | 53.5601063760975 | -63.33712985320202 | -1.2119428269337165 | -5.7397295204435395 | 0.25 | 3 | 12 |
| DEV | SHORT | 45 | year | 2023 | -9.018217260039682 | MEASURABLE |  | 7.340346306484372 | -15.561637669630013 | -1.4030516220678457 | 1758 | 219 | 0.8754266211604096 | 20000 | 999 | {"7":[-15.330955750483966,-1.307126743489742],"14":[-15.17302048314356,-2.0240150449758465],"30":[-15.62850724526452,-0.6750564273130113]} | {"20":[-14.191746989396053,-3.060577326862621],"50":[-13.674963558001366,-4.367643075410226]} | MEASURABLE |  | 7.340346306484369 | -9.144011213155789 | -0.8244324946508774 | 1758 | 219 | 0.8754266211604096 | 20000 | 999 | {"7":[-9.008462622440224,-0.7680670796501747],"14":[-8.915659931221455,-1.1893103193744041],"30":[-9.183303745368715,-0.3966628494963471]} | {"20":[-8.339064072836244,-1.798393844510287],"50":[-8.035402363717528,-2.566425083560155]} | -5.299100358146184 | 1033 | 0.5411423039690223 | 0.630750304149861 | 37.161570101552 | -63.479190118963196 | -5.01821726003968 | -9.729908700807057 | 0.16666666666666666 | 2 | 12 |
| DEV | SHORT | 45 | year | 2024 | -3.7626763624001347 | MEASURABLE |  | 2.8411972268318864 | -8.696125226450405 | 1.5236108882722634 | 1758 | 220 | 0.8748577929465301 | 20000 | 999 | {"7":[-8.245807497359579,1.133657436800596],"14":[-8.195967371061222,1.9928384164828374],"30":[-7.954595404364023,1.851611671946471]} | {"20":[-8.459945355383741,0.8362598757701187],"50":[-8.195750332833654,0.839580589087003]} | MEASURABLE |  | 2.8411972268322785 | -5.287916875469573 | 0.9264732875783435 | 1758 | 220 | 0.8748577929465301 | 20000 | 999 | {"7":[-5.014088859315915,0.6893514220361943],"14":[-4.983782206862573,1.2117999244711162],"30":[-4.837009378421544,1.1259231384018396]} | {"20":[-5.144301242835737,0.508510698064986],"50":[-4.983650230830024,0.5105299486541539]} | -2.287998311379832 | 1069 | 0.5322731524789522 | 0.567434576380282 | 46.289470506453576 | -60.722019499155664 | 0.23732363759986488 | -4.466443516691671 | 0.3333333333333333 | 4 | 12 |
| DEV | SHORT | 45 | year | 2025 | -4.095471505180109 | MEASURABLE |  | 3.707600335666501 | -9.67257026714017 | 1.6948942942320864 | 1758 | 203 | 0.8845278725824801 | 20000 | 999 | {"7":[-10.233808307733037,1.770558408806389],"14":[-9.536058122161199,1.471770098570575],"30":[-9.342692395095431,1.4686975944935696]} | {"20":[-9.49735336698112,1.2935552567283635],"50":[-9.4023154610543,1.0382164027007565]} | MEASURABLE |  | 3.7076003356664597 | -4.220057676277961 | 0.7394675333765384 | 1758 | 203 | 0.8845278725824801 | 20000 | 999 | {"7":[-4.4649209169689925,0.77247912375105],"14":[-4.16049862326374,0.6421204013672535],"30":[-4.076134850419942,0.6407798947534133]} | {"20":[-4.143612077630557,0.564366827025403],"50":[-4.102147871802419,0.45296472176989644]} | -1.7868183415660663 | 767 | 0.5319426336375489 | 0.5756712139690905 | 39.74120446722487 | -53.915426370754574 | -0.09547150518010968 | -4.82326032820938 | 0.25 | 3 | 12 |
| DEV | SHORT | 45 | trend_30d | -1 | -3.4446552439896 | MEASURABLE |  | 7.120058352939574 | -7.265734276460202 | 0.4509155305506467 | 1758 | 551 | 0.6865756541524459 | 20000 | 999 | {"7":[-7.177290319066847,0.12810587924977712],"14":[-7.282798996335519,0.28667908709435563],"30":[-6.669880790163036,0.008818218363840558]} | {"20":[-7.318254412800013,0.588316069327484],"50":[-7.109439097557168,0.3109236293241442]} | MEASURABLE |  | 7.1200583529397745 | -11.440018473971655 | 0.709973941162569 | 1758 | 551 | 0.6865756541524459 | 20000 | 999 | {"7":[-11.30076200408271,0.20170482011547541],"14":[-11.46688715691527,0.45138095169334136],"30":[-10.501837330586834,0.013884430279130555]} | {"20":[-11.52271229501164,0.9263133560287224],"50":[-11.19392913654052,0.4895543833727336]} | -5.423666504757231 | 2768 | 0.5155346820809249 | 0.5445236052008383 | 54.122712505337695 | -64.70388997798665 | 0.5553447560104002 | -4.1878700116152 | 0.3958333333333333 | 19 | 48 |
| DEV | SHORT | 45 | trend_30d | 1 | -5.953429239063531 | MEASURABLE |  | 2.942658533133656 | -9.884849576720585 | -1.7128417951322845 | 1758 | 565 | 0.6786120591581343 | 20000 | 999 | {"7":[-9.6107039398777,-1.892431498553897],"14":[-9.96769731248856,-1.9868243096707623],"30":[-9.956668124753815,-1.6778937983855808]} | {"20":[-9.583895108445043,-1.9655706379837743],"50":[-9.481201166406583,-2.3024406756992573]} | MEASURABLE |  | 2.942658533133613 | -13.764568693863499 | -2.3851175850306383 | 1758 | 565 | 0.6786120591581343 | 20000 | 999 | {"7":[-13.382823233686384,-2.635194714709886],"14":[-13.879933459028472,-2.7666358987907147],"30":[-13.86457540921353,-2.336452797751952]} | {"20":[-13.345492164660662,-2.737040342311875],"50":[-13.202491726600304,-3.2061289955129766]} | -8.290099418218158 | 2448 | 0.5175653594771242 | 0.5719371782482549 | 46.87063586929349 | -62.624123982745445 | -1.9534292390635306 | -6.40644022029763 | 0.32075471698113206 | 17 | 53 |
| HOLD_B | LONG | 15 | year | 2026 | -1.12097250420667 | MEASURABLE |  | 4.342290079200206 | -4.064116225747996 | 1.920409544390364 | 180 | 122 | 0.32222222222222224 | 20000 | 999 | {"7":[-4.134915594813705,1.8210381436638399],"14":[-3.8083461115898727,1.6555521444299781],"30":[-3.5410089583044133,1.3100989764363693]} | {"20":[-4.256187343821621,1.997378564305852],"50":[-4.228616590204109,1.4541848629794971]} | MEASURABLE |  | 4.3422900792002235 | -11.808515478145592 | 5.5798566206453355 | 180 | 122 | 0.32222222222222224 | 20000 | 999 | {"7":[-12.014226978264283,5.291127495201033],"14":[-11.065361202008363,4.8102987307604295],"30":[-10.28859825107338,3.8065653593123376]} | {"20":[-12.366588782326163,5.803494384066438],"50":[-12.286480425981933,4.225214907434859]} | -3.2570478872227127 | 523 | 0.5793499043977055 | 0.5954314911085501 | 28.200586340736137 | -41.50475582246881 | 2.8790274957933297 | -1.6075101653835866 | 0.6666666666666666 | 4 | 6 |
| HOLD_B | LONG | 15 | trend_30d | -1 | -1.4078808134964997 | MEASURABLE |  | 4.500788890743222 | -5.093738193050592 | 2.546856005006984 | 180 | 71 | 0.6055555555555555 | 20000 | 999 | {"7":[-5.282164868540625,2.3489792760221855],"14":[-5.157866528527738,2.4008939023924096],"30":[-5.309768735633325,2.388302032808605]} | {"20":[-5.855384746288714,2.5923326157416007],"50":[-5.572401401306684,2.1144466276681557]} | MEASURABLE |  | 4.500788890743203 | -10.215774931618117 | 5.107861210041793 | 180 | 71 | 0.6055555555555555 | 20000 | 999 | {"7":[-10.593675097462029,4.711008436911164],"14":[-10.344387871102853,4.815126104242568],"30":[-10.649036186464599,4.789872410243941]} | {"20":[-11.743299407834584,5.199067079348422],"50":[-11.175760588176164,4.240640181045568]} | -2.82358318706798 | 361 | 0.5761772853185596 | 0.5944735734101613 | 31.20484726209003 | -45.74413858945727 | 2.5921191865035 | -2.1155686633342574 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 15 | trend_30d | 1 | -0.4816274446163704 | MEASURABLE |  | 5.501164143902091 | -5.78445075368151 | 5.730502441816867 | 180 | 58 | 0.6777777777777778 | 20000 | 999 | {"7":[-5.525956694699522,6.265370293012278],"14":[-5.792120261554537,5.263179334623638],"30":[-4.96049584602649,4.921453315984442]} | {"20":[-5.878865478577138,5.553364842574403],"50":[-4.911483400761462,4.761569237330663]} | MEASURABLE |  | 5.501164143902121 | -5.206005678313362 | 5.15745219763517 | 180 | 58 | 0.6777777777777778 | 20000 | 999 | {"7":[-4.97336102522958,5.638833263711047],"14":[-5.212908235399092,4.736861401161264],"30":[-4.464446261423857,4.429307984385989]} | {"20":[-5.290978930719419,4.998028358316964],"50":[-4.420335060685313,4.2854123135976]} | -0.4334647001547331 | 162 | 0.5864197530864198 | 0.5954311275061711 | 21.622836112929694 | -31.823777265017508 | 3.5183725553836305 | -1.5840762744746626 | 0.75 | 3 | 4 |
| HOLD_B | LONG | 45 | year | 2026 | -0.374512240175395 | MEASURABLE |  | 3.777750265740438 | -6.862091465211436 | 6.558255818605229 | 180 | 126 | 0.3 | 20000 | 999 | {"7":[-6.43938725296,5.562250478707595],"14":[-5.727313092207918,5.649481496138714],"30":[-5.667723422215685,5.465509383301589]} | {"20":[-7.1258136666032215,6.135784352194133],"50":[-6.520123158833987,6.102393539019269]} | MEASURABLE |  | 3.7777502657404463 | -28.89702961461259 | 27.61754394723761 | 180 | 126 | 0.3 | 20000 | 999 | {"7":[-27.116975209687116,23.423254793668654],"14":[-24.11835179940892,23.790594300406365],"30":[-23.86741307799719,23.015867291903366]} | {"20":[-30.007593107140245,25.8384696609064],"50":[-27.456963079978696,25.69785723653667]} | -1.5771126558497157 | 758 | 0.5303430079155673 | 0.5338358278932194 | 49.98373506285756 | -57.239724082364305 | 3.6254877598246047 | -1.675886453059729 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 45 | trend_30d | -1 | -0.7350054163036405 | MEASURABLE |  | 3.8540650292740204 | -10.533696690051519 | 9.998505886601164 | 180 | 70 | 0.6111111111111112 | 20000 | 999 | {"7":[-9.783039770009193,8.257030682584816],"14":[-9.35792927443557,8.343251521959706],"30":[-8.304771000009728,7.599645456364542]} | {"20":[-11.562205823068258,8.891630799202558],"50":[-10.014634624024048,7.713785665388538]} | MEASURABLE |  | 3.8540650292740155 | -26.977967633965225 | 25.60728452068404 | 180 | 70 | 0.6111111111111112 | 20000 | 999 | {"7":[-25.055451855412368,21.147173025953368],"14":[-23.966696641748797,21.367994175685883],"30":[-21.269441283358084,19.463536418800405]} | {"20":[-29.612093802413742,22.772454435735455],"50":[-25.64859200930603,19.755862176356207]} | -1.8824305384221 | 461 | 0.5119305856832972 | 0.517602887625428 | 62.50804241766845 | -67.06993558882546 | 3.264994583696359 | -2.880016072715004 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 45 | trend_30d | 1 | 0.18504114095295873 | MEASURABLE |  | 3.271217448381013 | -6.3147003599584774 | 6.685978992927017 | 180 | 64 | 0.6444444444444445 | 20000 | 999 | {"7":[-6.36759369322031,6.339845366537113],"14":[-6.695646660410809,6.120601080768126],"30":[-5.913264380870184,5.875953949778105]} | {"20":[-5.459120510557219,6.244136843405687],"50":[-5.4392348783454345,5.854888234659362]} | MEASURABLE |  | 3.271217448380989 | -10.419255593931524 | 11.031865338329533 | 180 | 64 | 0.6444444444444445 | 20000 | 999 | {"7":[-10.506529593813534,10.460744854786212],"14":[-11.047816989677862,10.0989917832674],"30":[-9.756886228435826,9.695324017133853]} | {"20":[-9.00754884241941,10.302825791619375],"50":[-8.974737549269966,9.660565587187943]} | 0.3053178825723825 | 297 | 0.5589225589225589 | 0.5563714589966283 | 32.17809328131921 | -40.35577302164854 | 4.1850411409529595 | -0.5443188077331057 | 0.5 | 2 | 4 |
| HOLD_B | LONG | 60 | year | 2026 | 0.9161983483884844 | MEASURABLE |  | 2.694487205605237 | -8.388196096832093 | 9.432199877296622 | 180 | 117 | 0.35 | 20000 | 999 | {"7":[-7.088320856328899,7.865187424705198],"14":[-5.19615312520269,7.598192068037495],"30":[-4.472050442968461,6.820121214537336]} | {"20":[-8.286636421783015,9.484647524759499],"50":[-7.058267071533226,8.663510780554411]} | MEASURABLE |  | 2.6944872056052396 | -38.25949441943965 | 43.021311662558546 | 180 | 117 | 0.35 | 20000 | 999 | {"7":[-32.330619016922284,35.873993753794394],"14":[-23.700231754396626,34.65619826588221],"30":[-20.397518964872766,31.10733065075086]} | {"20":[-37.79626945713257,43.26053121015302],"50":[-32.19354036515986,39.51523528241765]} | 4.178882466816365 | 821 | 0.5310596833130329 | 0.5230430261334023 | 54.50990131139431 | -59.7769302019246 | 4.916198348388485 | -0.4085414555285554 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 60 | trend_30d | -1 | 1.9352170559985362 | MEASURABLE |  | 2.691313905075075 | -11.67622015322354 | 14.058634241697597 | 180 | 70 | 0.6111111111111112 | 20000 | 999 | {"7":[-10.05102150471711,11.604079701482178],"14":[-7.554873085907526,11.235635134998411],"30":[-6.476151846266483,10.600499821884384]} | {"20":[-10.928041713176349,13.733786727292689],"50":[-9.666905123526458,11.950708191618169]} | MEASURABLE |  | 2.6913139050750723 | -34.89892468019041 | 42.0196956779628 | 180 | 70 | 0.6111111111111112 | 20000 | 999 | {"7":[-30.041386497432264,34.68330488554111],"14":[-22.58067622343479,33.58206501460633],"30":[-19.356498296063197,31.683716134298813]} | {"20":[-32.66270245382711,41.04876255157484],"50":[-28.89330531365131,35.71933892828101]} | 5.784148756262291 | 538 | 0.5278810408921933 | 0.5136871939202892 | 66.304845947604 | -70.03712390941858 | 5.935217055998536 | -0.08516328354033846 | 0.5 | 3 | 6 |
| HOLD_B | LONG | 60 | trend_30d | 1 | -1.0210174279161373 | MEASURABLE |  | 2.5537960354928586 | -8.530434994462114 | 7.435626674002032 | 180 | 57 | 0.6833333333333333 | 20000 | 999 | {"7":[-9.76332926765816,6.999715870560333],"14":[-10.423243876877963,7.468758590023034],"30":[-9.583178640439899,6.902727866216253]} | {"20":[-8.405321814255158,7.341501921004566],"50":[-9.34664958790162,7.622361293806172]} | MEASURABLE |  | 2.5537960354928573 | -13.41173946351542 | 11.69045749301432 | 180 | 57 | 0.6833333333333333 | 20000 | 999 | {"7":[-15.350123237484766,11.005108840936542],"14":[-16.387655650869256,11.742548227647374],"30":[-15.066886418024978,10.852622145217786]} | {"20":[-13.215033741301156,11.542472464690514],"50":[-14.695010185423092,11.984045811928581]} | -1.6052662894459255 | 283 | 0.5371024734982333 | 0.5512136758458207 | 32.47197843847621 | -39.883119501898086 | 2.9789825720838627 | -1.8815376545751803 | 0.25 | 1 | 4 |
| HOLD_B | SHORT | 5 | year | 2026 | -3.8017101818339047 | MEASURABLE |  | 21.12426407746893 | -6.894820748668222 | -0.6102012381541719 | 180 | 59 | 0.6722222222222223 | 20000 | 999 | {"7":[-8.180919219391315,0.5420949958679118],"14":[-7.217925879178079,-0.25692029915458026],"30":[-6.699917347400807,-0.7921302561145889]} | {"20":[-7.331159830788401,-0.20751430905923263],"50":[-6.787604454062984,-1.039219381231407]} | MEASURABLE |  | 21.124264077469185 | -4.251806128345397 | -0.3762907635284034 | 180 | 59 | 0.6722222222222223 | 20000 | 999 | {"7":[-5.044900185291315,0.3342919141185403],"14":[-4.45105429215981,-0.1584341844786561],"30":[-4.131615697563825,-0.48848032460399127]} | {"20":[-4.520881895652847,-0.12796715725319352],"50":[-4.18568941333884,-0.6408519517593663]} | -2.3443879454642413 | 111 | 0.5675675675675675 | 0.6344404332032727 | 20.781994519700785 | -36.06782260259819 | 0.19828981816609478 | -5.4862459952805205 | 0.3333333333333333 | 2 | 6 |
| HOLD_B | SHORT | 5 | trend_30d | -1 | -4.249317142103692 | MEASURABLE |  | 36.66282144987078 | -7.644135370745113 | -0.5628383054329018 | 180 | 36 | 0.8 | 20000 | 999 | {"7":[-9.703806220192966,1.756392722040113],"14":[-8.462988256676148,0.6588128375607782],"30":[-8.090825151373096,-0.06906615978693686]} | {"20":[-9.285873994176523,0.3905193014130095],"50":[-8.09387523878185,-0.29248578673139347]} | MEASURABLE |  | 36.66282144986939 | -3.1425889857507743 | -0.23138908112241063 | 180 | 36 | 0.8 | 20000 | 999 | {"7":[-3.989342557190436,0.722072563505376],"14":[-3.4792285055224177,0.2708452776638781],"30":[-3.326228117786722,-0.028393865690192532]} | {"20":[-3.817525975383683,0.16054682391423647],"50":[-3.327482042610317,-0.12024415676735156]} | -1.7469414917537405 | 74 | 0.5540540540540541 | 0.6185639130350419 | 25.125506838184897 | -40.74531057215921 | -0.24931714210369324 | -6.81195071969009 | 0.4 | 2 | 5 |
| HOLD_B | SHORT | 5 | trend_30d | 1 | -2.906496261294328 | MEASURABLE |  | 3.0886988739655 | -10.374411685352236 | 5.350398608732308 | 180 | 24 | 0.8666666666666667 | 20000 | 999 | {"7":[-10.232562954975894,5.4701429872841905],"14":[-10.329360768713244,5.0607782800688055],"30":[-9.938323790043857,5.109536129559385]} | {"20":[-8.350311298263998,3.448385698925132],"50":[-7.875253083849412,1.6929318753634632]} | MEASURABLE |  | 3.088698873965526 | -2.1325179575446223 | 1.0998041584616456 | 180 | 24 | 0.8666666666666667 | 20000 | 999 | {"7":[-2.1033601629672685,1.1244182807195136],"14":[-2.123257491346612,1.0402710909030317],"30":[-2.0428776679534564,1.0502935377427598]} | {"20":[-1.7164528779764885,0.7088348381123872],"50":[-1.618802022791268,0.34799155215804445]} | -0.5974464537105009 | 37 | 0.5945945945945946 | 0.6701574509805239 | 12.68726701707131 | -25.77734906956393 | 1.093503738705672 | -4.782195926013728 | 0.5 | 2 | 4 |
| HOLD_B | SHORT | 15 | year | 2026 | -1.8621163845086697 | MEASURABLE |  | 15.264689753721706 | -5.8729447799349765 | 2.1612817768475656 | 180 | 95 | 0.4722222222222222 | 20000 | 999 | {"7":[-6.212673743640581,2.313395364478618],"14":[-5.942042741697589,2.2147565323453016],"30":[-5.3119583084249555,1.9562805494997608]} | {"20":[-6.771610072828271,2.704241022185289],"50":[-5.999679931779394,2.4341592468051347]} | MEASURABLE |  | 15.264689753721765 | -8.646279814904267 | 3.1818870603589335 | 180 | 95 | 0.4722222222222222 | 20000 | 999 | {"7":[-9.146436344804169,3.4058320643713085],"14":[-8.748007369721435,3.2606137837305944],"30":[-7.820383065181165,2.8800796978746677]} | {"20":[-9.969314829441615,3.981243727106129],"50":[-8.832862121786338,3.5836233355742255]} | -2.741449121637763 | 265 | 0.5094339622641509 | 0.5347423468677739 | 34.23228753966183 | -39.344766613454965 | 2.1378836154913308 | -3.14699253663908 | 0.3333333333333333 | 2 | 6 |
| HOLD_B | SHORT | 15 | trend_30d | -1 | -1.4176886704078147 | MEASURABLE |  | 23.974632895468858 | -5.834404680756482 | 3.4823349491219666 | 180 | 46 | 0.7444444444444445 | 20000 | 999 | {"7":[-7.283802623211769,4.253854237517104],"14":[-6.223790952033998,4.3110076144315785],"30":[-5.611311376097745,3.4789575502091514]} | {"20":[-8.015282423964113,4.068724966783483],"50":[-6.069636219837535,3.088533816948087]} | MEASURABLE |  | 23.97463289546932 | -5.12131077533068 | 3.0567162331182 | 180 | 46 | 0.7444444444444445 | 20000 | 999 | {"7":[-6.393560080374735,3.7339387195983607],"14":[-5.463105391229805,3.7841066837788455],"30":[-4.925484430130195,3.0537516274058456]} | {"20":[-7.035636794368496,3.5714363597321714],"50":[-5.327791792968507,2.7110463504322126]} | -1.2444156106913031 | 158 | 0.5126582278481012 | 0.5291633127522126 | 40.442072306896215 | -45.451982685493874 | 2.5823113295921862 | -3.5781602895238174 | 0.6666666666666666 | 4 | 6 |
| HOLD_B | SHORT | 15 | trend_30d | 1 | -2.5183741305641383 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 51 | 0.7166666666666667 | 0 | 999 | {"7":[-9.332316780611537,5.309102134633562],"14":[-9.384820854500694,5.6596399030863775],"30":[-8.774402320640359,5.579639898806173]} | {"20":[-9.750463865666482,4.97000571508295],"50":[-9.156798574830388,4.1947567555326515]} | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 51 | 0.7166666666666667 | 0 | 999 | {"7":[-5.547543864030202,3.1559662689210377],"14":[-5.578754619064304,3.36434149794578],"30":[-5.21589471282512,3.3167859398458805]} | {"20":[-5.796109075701744,2.9543922861881953],"50":[-5.44320804170473,2.493549849122185]} | -1.497033510946461 | 107 | 0.5046728971962616 | 0.5501394253242147 | 24.917610388810274 | -30.472018735209762 | 1.4816258694358615 | -4.27009139246323 | 0.5 | 2 | 4 |
| HOLD_B | SHORT | 45 | year | 2026 | -3.0023577559744172 | MEASURABLE |  | 14.781985151545355 | -9.56025595443164 | 3.1935089447103078 | 180 | 108 | 0.4 | 20000 | 999 | {"7":[-9.275805084446478,3.3984677345861716],"14":[-9.504391680209375,3.404263534032661],"30":[-9.326626142235218,2.775502939459609]} | {"20":[-10.122948977997112,3.5567524090894462],"50":[-9.338176997447661,4.2506702338276785]} | MEASURABLE |  | 14.781985151545497 | -23.688189753758408 | 7.912805496337755 | 180 | 108 | 0.4 | 20000 | 999 | {"7":[-22.983383709239618,8.420647831252381],"14":[-23.549770496518782,8.435008534325368],"30":[-23.109306996871773,6.877079505549906]} | {"20":[-25.082418023259528,8.81284208029941],"50":[-23.137927449231455,10.532216246039694]} | -7.439175328692167 | 446 | 0.531390134529148 | 0.5594061343975264 | 47.21660536268779 | -59.94922023981624 | 0.9976422440255833 | -4.930219333029814 | 0.3333333333333333 | 2 | 6 |
| HOLD_B | SHORT | 45 | trend_30d | -1 | -1.34981307650709 | MEASURABLE |  | 41.0 | -7.612651956836326 | 5.331175290182501 | 180 | 55 | 0.6944444444444444 | 20000 | 999 | {"7":[-8.963346708639515,5.903226622865596],"14":[-8.135735378181552,6.314027624443],"30":[-7.639769752135695,5.714794007162921]} | {"20":[-10.890599266261273,7.515695601512997],"50":[-9.214731383365717,6.593961262527227]} | MEASURABLE |  | 41.0 | -11.376685424383158 | 7.967145294772768 | 180 | 55 | 0.6944444444444444 | 20000 | 999 | {"7":[-13.39522369235568,8.822044230838053],"14":[-12.158404537393533,9.435963505417623],"30":[-11.417211462913855,8.540442155149071]} | {"20":[-16.275395570134915,11.231789537816674],"50":[-13.770904122918765,9.854308775665688]} | -2.017220653224482 | 269 | 0.5464684014869888 | 0.5576356053033014 | 53.46989760055412 | -67.4030710234579 | 2.6501869234929103 | -4.543316637756767 | 0.5 | 3 | 6 |
| HOLD_B | SHORT | 45 | trend_30d | 1 | -5.5138522123400175 | MEASURABLE |  | 1.0888526157532799 | -14.891015423164296 | 4.879677913967479 | 180 | 56 | 0.6888888888888889 | 20000 | 999 | {"7":[-16.254417276547365,6.820909653099708],"14":[-16.294478096887488,6.34571680755081],"30":[-15.281192782257047,5.4216888740969225]} | {"20":[-17.75915635153749,6.301201656251136],"50":[-15.790603963719825,4.859415942312143]} | MEASURABLE |  | 1.0888526157532799 | -14.642831832778246 | 4.798349948734667 | 180 | 56 | 0.6888888888888889 | 20000 | 999 | {"7":[-15.983510321938283,6.707227825548098],"14":[-16.02290346193939,6.239954860758343],"30":[-15.02650623588611,5.3313273928619624]} | {"20":[-17.463170412345203,6.196181628646962],"50":[-15.527427230991162,4.778425676606951]} | -5.421954675467684 | 177 | 0.5084745762711864 | 0.5722188356840205 | 37.00289470750607 | -49.49669385356012 | -1.513852212340018 | -7.542110548558628 | 0.25 | 1 | 4 |

## R2-1 h45 decision and random baseline

| segment | strategy | book | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | daily_pnl_pw_status | daily_pnl_pw_error | daily_pnl_pw_block | daily_pnl_pw_ci95_lower | daily_pnl_pw_ci95_upper | daily_pnl_calendar_days | daily_pnl_trade_days | daily_pnl_zero_day_share | daily_pnl_pw_bootstrap_reps | daily_pnl_fixed_bootstrap_reps | daily_pnl_daily_fixed_blocks | daily_pnl_event_fixed_blocks | daily_pnl_mean_bps | n | direction_hit_rate | break_even_hit_rate | correct_net_mean_bps | wrong_net_mean_bps | gross_mean_bps | trimmed_top2_net_mean_bps | monthly_positive_share | positive_months | months |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | MODEL | SINGLE | -2.951872851797247 | MEASURABLE |  | 2.276945138966366 | -5.159057102271536 | -0.8122241733111433 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-5.188327780567539,-0.7875781604041006],"14":[-5.140372558976334,-0.8374715545953295],"30":[-5.305269214876751,-0.9521436383168704]} | {"20":[-5.23490450653769,-0.9048922504074377],"50":[-5.264206877486213,-0.8442624045776541]} | MEASURABLE |  | 2.276945138966376 | -22.690460474837437 | -3.572307911286435 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-22.819198179378937,-3.463910316407576],"14":[-22.60828249488345,-3.6833504323839854],"30":[-23.333527627660544,-4.187698868865752]} | {"20":[-23.024050992348926,-3.9798787714165957],"50":[-23.152928086873295,-3.713217811259643]} | -12.982867400509848 | 7732 | 0.5293585100879462 | 0.5562401030852293 | 48.72935887956662 | -61.08083176261679 | 1.0481271482027534 | -3.292462366582974 | 0.27586206896551724 | 16 | 58 |
| DEV | RANDOM_DIRECTION | SAME_ENTRIES | -4.816446320643781 | MEASURABLE |  | 1.4337103806952616 | -6.613171289856601 | -3.015689378770234 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-6.638430691245052,-3.0248118677352145],"14":[-6.630012237502406,-3.0172386039496626],"30":[-6.8028696827550075,-2.837580329347654]} | {"20":[-6.520988473639828,-2.9752310326575433],"50":[-6.486780674145261,-3.1536418058814535]} | MEASURABLE |  | 1.4337103806952358 | -29.08591604844756 | -13.263543957139488 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-29.19701143612427,-13.303666303372149],"14":[-29.1599855633496,-13.270357727951446],"30":[-29.92024367864701,-12.480188342728113]} | {"20":[-28.680479452891444,-13.085600878559816],"50":[-28.530027401872086,-13.870283528484304]} | -21.18359667304762 | 7732 | 0.4997413347128815 | 0.5437055172106461 | 49.98882631043102 | -59.56504338539896 | -0.8164463206437809 | -5.025548104184622 | 0.1896551724137931 | 11 | 58 |
| HOLD_B | MODEL | SINGLE | -2.6162613410091535 | MEASURABLE |  | 2.3256769954128753 | -7.60988398639595 | 2.490029195034675 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-7.642498270683861,2.084208485008929],"14":[-7.3443368774790425,1.7689922184240428],"30":[-6.675430680009564,1.0662968147288665]} | {"20":[-7.977706285603711,2.5619015720103113],"50":[-7.58312256525342,1.931608443898749]} | MEASURABLE |  | 2.325676995412875 | -29.84765607997523 | 9.766447842747104 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-29.975576550571155,8.17472883564612],"14":[-28.806121308334497,6.938380590040948],"30":[-26.182522556037508,4.182253062214333]} | {"20":[-31.290336875756743,10.04834727688492],"50":[-29.74269183927168,7.576197563291787]} | -10.26155837084701 | 706 | 0.5311614730878187 | 0.5580313070231623 | 43.03359701269604 | -54.334378811218954 | 1.3837386589908471 | -3.4716492033794255 | 0.16666666666666666 | 1 | 6 |
| HOLD_B | RANDOM_DIRECTION | SAME_ENTRIES | -7.040304709802453 | MEASURABLE |  | 4.679882068693194 | -11.404968199893872 | -2.4659883068830597 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-11.344968616562955,-2.672441638618535],"14":[-11.690560659812025,-2.706374028917547],"30":[-12.10223243488322,-2.334725121780071]} | {"20":[-11.440139038457477,-2.374278551181135],"50":[-11.378724883322551,-2.605195086656267]} | MEASURABLE |  | 4.679882068693202 | -44.73281971736158 | -9.672154136996909 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-44.49748801829694,-10.481909982581616],"14":[-45.85297681015166,-10.615000357865526],"30":[-47.46764499459756,-9.157310755426316]} | {"20":[-44.87076756194991,-9.312448095188284],"50":[-44.62988759792069,-10.218154062107352]} | -27.61363958400296 | 706 | 0.4801699716713881 | 0.5526952585114345 | 43.42156805479935 | -53.65222532887605 | -3.040304709802454 | -7.837257080167024 | 0.16666666666666666 | 1 | 6 |

## R2-2 book comparison

| signal | segment | book | max_concurrent | mean_concurrent | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | daily_pnl_pw_status | daily_pnl_pw_error | daily_pnl_pw_block | daily_pnl_pw_ci95_lower | daily_pnl_pw_ci95_upper | daily_pnl_calendar_days | daily_pnl_trade_days | daily_pnl_zero_day_share | daily_pnl_pw_bootstrap_reps | daily_pnl_fixed_bootstrap_reps | daily_pnl_daily_fixed_blocks | daily_pnl_event_fixed_blocks | daily_pnl_mean_bps | n | direction_hit_rate | break_even_hit_rate | correct_net_mean_bps | wrong_net_mean_bps | gross_mean_bps | trimmed_top2_net_mean_bps | monthly_positive_share | positive_months | months |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2-1 | DEV | SINGLE | 1 | 0.1374626110310644 | -2.951872851797247 | MEASURABLE |  | 2.276945138966366 | -5.159057102271536 | -0.8122241733111433 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-5.188327780567539,-0.7875781604041006],"14":[-5.140372558976334,-0.8374715545953295],"30":[-5.305269214876751,-0.9521436383168704]} | {"20":[-5.23490450653769,-0.9048922504074377],"50":[-5.264206877486213,-0.8442624045776541]} | MEASURABLE |  | 2.276945138966376 | -22.690460474837437 | -3.572307911286435 | 1758 | 1294 | 0.26393629124004553 | 20000 | 999 | {"7":[-22.819198179378937,-3.463910316407576],"14":[-22.60828249488345,-3.6833504323839854],"30":[-23.333527627660544,-4.187698868865752]} | {"20":[-23.024050992348926,-3.9798787714165957],"50":[-23.152928086873295,-3.713217811259643]} | -12.982867400509848 | 7732 | 0.5293585100879462 | 0.5562401030852293 | 48.72935887956662 | -61.08083176261679 | 1.0481271482027534 | -3.292462366582974 | 0.27586206896551724 | 16 | 58 |
| R2-1 | DEV | CAP3 | 3 | 0.2526311048566251 | -3.492991660594181 | MEASURABLE |  | 1.65115872686665 | -5.150805184013739 | -1.7802293497716049 | 1758 | 1295 | 0.2633674630261661 | 20000 | 999 | {"7":[-5.147869806583265,-1.7684135299620427],"14":[-5.250178926010544,-1.7212758756621869],"30":[-5.373951346104449,-1.685338574899644]} | {"20":[-5.121161910604114,-1.7397162020775212],"50":[-5.267467380417564,-1.7047511093927872]} | MEASURABLE |  | 1.65115872686664 | -41.63421027578801 | -14.389680921646482 | 1758 | 1295 | 0.2633674630261661 | 20000 | 999 | {"7":[-41.610483476421045,-14.294173072105043],"14":[-42.43745309363473,-13.913157106461753],"30":[-43.4379116201048,-13.622674146373123]} | {"20":[-41.394602246691825,-14.062211166963284],"50":[-42.57719651634444,-13.779586612327444]} | -28.234022467032602 | 14210 | 0.526460239268121 | 0.5568640621681415 | 50.910378620683844 | -63.97621547902796 | 0.5070083394058186 | -3.678368855618898 | 0.25862068965517243 | 15 | 58 |
| R2-1 | DEV | ALL | 3 | 0.2526311048566251 | -3.492991660594181 | MEASURABLE |  | 1.65115872686665 | -5.150805184013739 | -1.7802293497716049 | 1758 | 1295 | 0.2633674630261661 | 20000 | 999 | {"7":[-5.147869806583265,-1.7684135299620427],"14":[-5.250178926010544,-1.7212758756621869],"30":[-5.373951346104449,-1.685338574899644]} | {"20":[-5.121161910604114,-1.7397162020775212],"50":[-5.267467380417564,-1.7047511093927872]} | MEASURABLE |  | 1.65115872686664 | -41.63421027578801 | -14.389680921646482 | 1758 | 1295 | 0.2633674630261661 | 20000 | 999 | {"7":[-41.610483476421045,-14.294173072105043],"14":[-42.43745309363473,-13.913157106461753],"30":[-43.4379116201048,-13.622674146373123]} | {"20":[-41.394602246691825,-14.062211166963284],"50":[-42.57719651634444,-13.779586612327444]} | -28.234022467032602 | 14210 | 0.526460239268121 | 0.5568640621681415 | 50.910378620683844 | -63.97621547902796 | 0.5070083394058186 | -3.678368855618898 | 0.25862068965517243 | 15 | 58 |
| R2-1 | HOLD_B | SINGLE | 1 | 0.1230543671772276 | -2.6162613410091535 | MEASURABLE |  | 2.3256769954128753 | -7.60988398639595 | 2.490029195034675 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-7.642498270683861,2.084208485008929],"14":[-7.3443368774790425,1.7689922184240428],"30":[-6.675430680009564,1.0662968147288665]} | {"20":[-7.977706285603711,2.5619015720103113],"50":[-7.58312256525342,1.931608443898749]} | MEASURABLE |  | 2.325676995412875 | -29.84765607997523 | 9.766447842747104 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-29.975576550571155,8.17472883564612],"14":[-28.806121308334497,6.938380590040948],"30":[-26.182522556037508,4.182253062214333]} | {"20":[-31.290336875756743,10.04834727688492],"50":[-29.74269183927168,7.576197563291787]} | -10.26155837084701 | 706 | 0.5311614730878187 | 0.5580313070231623 | 43.03359701269604 | -54.334378811218954 | 1.3837386589908471 | -3.4716492033794255 | 0.16666666666666666 | 1 | 6 |
| R2-1 | HOLD_B | CAP3 | 3 | 0.2093972174493156 | -1.4475084803062135 | MEASURABLE |  | 3.203977888788384 | -5.4552079284001005 | 2.683033277363988 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-5.197275836316385,2.2019399934356287],"14":[-5.19884709145647,2.20548220510038],"30":[-5.024314277982256,2.0382401571606876]} | {"20":[-6.185682935512505,3.3365043811181057],"50":[-5.932810593591772,2.7046016486135507]} | MEASURABLE |  | 3.2039778887883834 | -36.39835956671403 | 17.90179425618973 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-34.677379330088776,14.691832956201067],"14":[-34.68786309355121,14.715467379586427],"30":[-33.5233413769816,13.599591270833288]} | {"20":[-41.27225114194731,22.261898676238047],"50":[-39.585030682798404,18.045703222138215]} | -9.658098249154234 | 1201 | 0.5303913405495421 | 0.543943659002639 | 48.71088466344673 | -58.09803406997045 | 2.5524915196937865 | -2.3931804695255186 | 0.5 | 3 | 6 |
| R2-1 | HOLD_B | ALL | 3 | 0.2093972174493156 | -1.4475084803062135 | MEASURABLE |  | 3.203977888788384 | -5.4552079284001005 | 2.683033277363988 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-5.197275836316385,2.2019399934356287],"14":[-5.19884709145647,2.20548220510038],"30":[-5.024314277982256,2.0382401571606876]} | {"20":[-6.185682935512505,3.3365043811181057],"50":[-5.932810593591772,2.7046016486135507]} | MEASURABLE |  | 3.2039778887883834 | -36.39835956671403 | 17.90179425618973 | 180 | 139 | 0.22777777777777777 | 20000 | 999 | {"7":[-34.677379330088776,14.691832956201067],"14":[-34.68786309355121,14.715467379586427],"30":[-33.5233413769816,13.599591270833288]} | {"20":[-41.27225114194731,22.261898676238047],"50":[-39.585030682798404,18.045703222138215]} | -9.658098249154234 | 1201 | 0.5303913405495421 | 0.543943659002639 | 48.71088466344673 | -58.09803406997045 | 2.5524915196937865 | -2.3931804695255186 | 0.5 | 3 | 6 |
| MULTICLASS_0.10 | DEV | SINGLE | 1 | 0.10949718330837113 | -3.632852557790652 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 1232 | 0.2992036405005688 | 0 | 999 | {"7":[-5.565733402392931,-1.6668997489459911],"14":[-5.65465765300594,-1.735064287591583],"30":[-5.614353637749668,-1.5838014974527703]} | {"20":[-5.555315327112545,-1.6244742834692123],"50":[-5.65894308756805,-1.78397150226502]} | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 1232 | 0.2992036405005688 | 0 | 999 | {"7":[-19.49906258551654,-5.839838198952461],"14":[-19.810600958398002,-6.0786467276886516],"30":[-19.66939934863496,-5.548710706946338]} | {"20":[-19.462563765464257,-5.691204272973187],"50":[-19.825614605421855,-6.249988897867078]} | -12.727382766457696 | 6159 | 0.5294690696541646 | 0.5625645259918443 | 48.01682032737658 | -61.75210144617241 | 0.36714744220934736 | -3.8781445875320752 | 0.29310344827586204 | 17 | 58 |
| MULTICLASS_0.10 | DEV | CAP3 | 3 | 0.18180194780181902 | -2.958275487871708 | MEASURABLE |  | 1.8896951904458796 | -5.059175639102893 | -0.8592730388424656 | 1758 | 1232 | 0.2992036405005688 | 20000 | 999 | {"7":[-4.922936575276728,-0.7317341109239197],"14":[-5.293573163534818,-0.8721239200986983],"30":[-5.270049958356889,-0.928308521410067]} | {"20":[-5.122150668883081,-0.9222915502945837],"50":[-4.8631943696780136,-0.9559854651280117]} | MEASURABLE |  | 1.8896951904458716 | -29.428401641334595 | -4.998251476224841 | 1758 | 1232 | 0.2992036405005688 | 20000 | 999 | {"7":[-28.63592117109211,-4.25637828117644],"14":[-30.791853908024418,-5.073002961848257],"30":[-30.65502325037407,-5.3998196472921265]} | {"20":[-29.794717144481442,-5.3648199051834045],"50":[-28.288410480277257,-5.560811926279296]} | -17.20780724628901 | 10226 | 0.5304126735771563 | 0.5562627174163304 | 50.781234039253754 | -63.65862943937701 | 1.0417245121282919 | -3.2157842666829155 | 0.25862068965517243 | 15 | 58 |
| MULTICLASS_0.10 | DEV | ALL | 3 | 0.18180194780181902 | -2.958275487871708 | MEASURABLE |  | 1.8896951904458796 | -5.059175639102893 | -0.8592730388424656 | 1758 | 1232 | 0.2992036405005688 | 20000 | 999 | {"7":[-4.922936575276728,-0.7317341109239197],"14":[-5.293573163534818,-0.8721239200986983],"30":[-5.270049958356889,-0.928308521410067]} | {"20":[-5.122150668883081,-0.9222915502945837],"50":[-4.8631943696780136,-0.9559854651280117]} | MEASURABLE |  | 1.8896951904458716 | -29.428401641334595 | -4.998251476224841 | 1758 | 1232 | 0.2992036405005688 | 20000 | 999 | {"7":[-28.63592117109211,-4.25637828117644],"14":[-30.791853908024418,-5.073002961848257],"30":[-30.65502325037407,-5.3998196472921265]} | {"20":[-29.794717144481442,-5.3648199051834045],"50":[-28.288410480277257,-5.560811926279296]} | -17.20780724628901 | 10226 | 0.5304126735771563 | 0.5562627174163304 | 50.781234039253754 | -63.65862943937701 | 1.0417245121282919 | -3.2157842666829155 | 0.25862068965517243 | 15 | 58 |
| MULTICLASS_0.10 | HOLD_B | SINGLE | 1 | 0.09145880281280423 | -4.74030986585246 | MEASURABLE |  | 1.5996314549364359 | -11.066061637091853 | 1.914261836574922 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-11.268848559945594,2.495001684470794],"14":[-11.271269796819773,2.6536997042448958],"30":[-10.587118369510616,2.278817412464667]} | {"20":[-10.365106852835432,1.852238709505901],"50":[-10.575339356032295,2.3470203849601576]} | MEASURABLE |  | 1.5996314549364377 | -32.21453498797848 | 5.572628902029223 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-32.80487025228605,7.2632271259038745],"14":[-32.8119187418531,7.725214694579584],"30":[-30.820277920130867,6.633890689619346]} | {"20":[-30.17397772714317,5.392072687672748],"50":[-30.78598790311623,6.832437120661794]} | -13.799568720592717 | 524 | 0.5419847328244275 | 0.5905892759427984 | 39.92905950597478 | -57.59906362251469 | -0.7403098658524602 | -5.90207452515966 | 0.16666666666666666 | 1 | 6 |
| MULTICLASS_0.10 | HOLD_B | CAP3 | 3 | 0.13381764867873447 | -2.002236018062689 | MEASURABLE |  | 4.32723924275985 | -7.251083948789212 | 3.426063966111453 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-7.215585148203658,3.0917842375219493],"14":[-6.551914675883922,2.880106075477939],"30":[-5.8068957678659885,2.44214368097591]} | {"20":[-7.552812357336201,3.7115048005148568],"50":[-6.520971413296583,2.7141270455687403]} | MEASURABLE |  | 4.327239242759857 | -30.897674381785126 | 14.598839233374921 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-30.74641004817892,13.17443616766295],"14":[-27.918436424460936,12.27245199939765],"30":[-24.743828077517847,10.406245573936246]} | {"20":[-32.18337265598266,15.815134344416077],"50":[-27.786583744435998,11.565196910840122]} | -8.53175014363379 | 767 | 0.5371577574967406 | 0.556574508668817 | 45.725594472635336 | -57.39340830585869 | 1.9977639819373114 | -3.29255543309057 | 0.5 | 3 | 6 |
| MULTICLASS_0.10 | HOLD_B | ALL | 3 | 0.13381764867873447 | -2.002236018062689 | MEASURABLE |  | 4.32723924275985 | -7.251083948789212 | 3.426063966111453 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-7.215585148203658,3.0917842375219493],"14":[-6.551914675883922,2.880106075477939],"30":[-5.8068957678659885,2.44214368097591]} | {"20":[-7.552812357336201,3.7115048005148568],"50":[-6.520971413296583,2.7141270455687403]} | MEASURABLE |  | 4.327239242759857 | -30.897674381785126 | 14.598839233374921 | 180 | 134 | 0.25555555555555554 | 20000 | 999 | {"7":[-30.74641004817892,13.17443616766295],"14":[-27.918436424460936,12.27245199939765],"30":[-24.743828077517847,10.406245573936246]} | {"20":[-32.18337265598266,15.815134344416077],"50":[-27.786583744435998,11.565196910840122]} | -8.53175014363379 | 767 | 0.5371577574967406 | 0.556574508668817 | 45.725594472635336 | -57.39340830585869 | 1.9977639819373114 | -3.29255543309057 | 0.5 | 3 | 6 |
| MULTICLASS_0.20 | DEV | SINGLE | 1 | 0.038170230973059396 | -1.4743264398021483 | MEASURABLE |  | 2.312534300193522 | -5.722659782464767 | 2.75543605855439 | 1758 | 763 | 0.5659840728100114 | 20000 | 999 | {"7":[-5.712027220967461,2.608229418660512],"14":[-5.744991931771719,2.909198812272911],"30":[-5.872182317398124,2.9163650415374933]} | {"20":[-5.698144742373417,2.4364051101772954],"50":[-5.887914886438468,2.416134979452651]} | MEASURABLE |  | 2.312534300193569 | -6.98893660577478 | 3.36514289972473 | 1758 | 763 | 0.5659840728100114 | 20000 | 999 | {"7":[-6.975951333001891,3.185363232004505],"14":[-7.016210283000062,3.5529293799486616],"30":[-7.171544616299211,3.5616813106830714]} | {"20":[-6.958997020407101,2.975518641382629],"50":[-7.190758396577572,2.9507632542006883]} | -1.8005568067435798 | 2147 | 0.5407545412203074 | 0.5515149543315376 | 61.44869661136028 | -75.56522883574495 | 2.5256735601978515 | -2.341318433491338 | 0.4827586206896552 | 28 | 58 |

## k45_gate_direction_r2_6_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_6.py`: `7 passed in 1.90s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T05:38:36.949836+00:00 |
| run_finished_utc | 2026-10-01T05:48:18.666044+00:00 |
| runtime_seconds | 581.716208 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 보유 시간을 늘리면 롱 net이 오르고 숏은 짧을수록 낫다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| entry | close[t] |
| exit | close[t+h] time-only |
| cost_bps | 4.0 |
| horizons | {"LONG": [5, 15, 30, 45, 60, 90, 120, 180, 240], "SHORT": [5, 15, 30, 45, 60, 90, 120, 180, 240]} |
| books | ["SINGLE", "ALL"] |
| source_rules | {"THREE_CLASS_M010": "p_long-p_short > 0.10 LONG; < -0.10 SHORT", "THREE_CLASS_M020": "p_long-p_short > 0.20 LONG; < -0.20 SHORT", "REGRESSION_ABS4": "yhat > 4 LONG; yhat < -4 SHORT", "WEIGHTED_M010": "weighted p_long-p_short > 0.10 LONG; < -0.10 SHORT", "R2_1_PSTAR": "arm p>p*; both eligible selects larger p-p*"} |
| funding_interval | entry_time < funding_time <= exit_time |
| funding_cost_bps | side * sum(actual funding rate) * 10000 |
| random_seed | 20261001 |
| random_direction_match | same entry bars, horizon, and n |
| long_pure_effect_random_match | pilot_fold+horizon+n |
| pw_bootstrap_reps | 20000 |
| pw_bootstrap_seed | 20260930 |
| fixed_bootstrap_reps | 999 |
| fixed_daily_blocks | [7, 14, 30] |
| fixed_event_blocks | [20, 50] |
| local_data_only | True |
| new_model_fits | 0 |
| live_orders | 0 |
| winner_selection | 0 |
| row_counts | {"model_metrics.parquet": 360, "random_direction_metrics.parquet": 360, "long_signal_pure_effect.parquet": 90, "core_net.parquet": 180, "extended_horizon_net.parquet": 60} |

### out_of_sample_result (원문)

```text
[
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 5,
  "ALL_net_bps": -4.0571555394776,
  "SINGLE_net_bps": -4.0571555394776
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 15,
  "ALL_net_bps": -2.6279970770983314,
  "SINGLE_net_bps": -2.6279970770983314
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 30,
  "ALL_net_bps": -2.4026857411113713,
  "SINGLE_net_bps": -2.911012863475147
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 45,
  "ALL_net_bps": -2.794583759606359,
  "SINGLE_net_bps": -2.6532985307328
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 60,
  "ALL_net_bps": -2.141388464856215,
  "SINGLE_net_bps": -1.9422031772533759
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 90,
  "ALL_net_bps": -1.7851638606953213,
  "SINGLE_net_bps": -1.2101957760039717
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 120,
  "ALL_net_bps": -1.6472938837659765,
  "SINGLE_net_bps": -2.0561575712918825
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 180,
  "ALL_net_bps": -0.47176105038871713,
  "SINGLE_net_bps": 0.05273939580406886
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "LONG",
  "horizon": 240,
  "ALL_net_bps": 0.9845125907199761,
  "SINGLE_net_bps": 0.18075458199020594
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 5,
  "ALL_net_bps": -3.2519979520864433,
  "SINGLE_net_bps": -3.2519979520864433
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 15,
  "ALL_net_bps": -4.256621977416879,
  "SINGLE_net_bps": -4.256621977416879
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 30,
  "ALL_net_bps": -4.644824686279453,
  "SINGLE_net_bps": -4.343906076152929
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 45,
  "ALL_net_bps": -4.843931787347693,
  "SINGLE_net_bps": -4.190149473893564
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 60,
  "ALL_net_bps": -4.893955132096311,
  "SINGLE_net_bps": -4.467041944140661
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 90,
  "ALL_net_bps": -7.060791754386459,
  "SINGLE_net_bps": -5.874186538849543
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 120,
  "ALL_net_bps": -9.311983363284561,
  "SINGLE_net_bps": -6.286543860912384
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 180,
  "ALL_net_bps": -12.101231555925931,
  "SINGLE_net_bps": -10.06033523464202
 },
 {
  "segment": "DEV",
  "source": "R2_1_PSTAR",
  "arm": "SHORT",
  "horizon": 240,
  "ALL_net_bps": -14.52225904636348,
  "SINGLE_net_bps": -9.47443381729157
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 5,
  "ALL_net_bps": -3.4267976747170557,
  "SINGLE_net_bps": -3.4267976747170557
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 15,
  "ALL_net_bps": -1.7477652677470734,
  "SINGLE_net_bps": -1.7477652677470734
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 30,
  "ALL_net_bps": -0.7194459341693169,
  "SINGLE_net_bps": -1.4073427226781865
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 45,
  "ALL_net_bps": 0.035454110351418405,
  "SINGLE_net_bps": -0.5238036581339258
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 60,
  "ALL_net_bps": -0.3434387712067836,
  "SINGLE_net_bps": -0.3339020314640311
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 90,
  "ALL_net_bps": 0.23095769035043975,
  "SINGLE_net_bps": -0.484254910299789
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 120,
  "ALL_net_bps": 1.1873847444893368,
  "SINGLE_net_bps": -0.053783787643492696
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 180,
  "ALL_net_bps": 2.504193608322144,
  "SINGLE_net_bps": 1.5570273050293673
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "LONG",
  "horizon": 240,
  "ALL_net_bps": 4.090594192133004,
  "SINGLE_net_bps": 1.3340836773591689
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 5,
  "ALL_net_bps": -2.698112157264879,
  "SINGLE_net_bps": -2.698112157264879
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 15,
  "ALL_net_bps": -3.788234526221254,
  "SINGLE_net_bps": -3.788234526221254
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 30,
  "ALL_net_bps": -3.815824905331575,
  "SINGLE_net_bps": -3.6237080086586473
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 45,
  "ALL_net_bps": -4.623747402007808,
  "SINGLE_net_bps": -4.229232309173488
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 60,
  "ALL_net_bps": -5.4165723810998,
  "SINGLE_net_bps": -4.263274823484096
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 90,
  "ALL_net_bps": -8.938160817243539,
  "SINGLE_net_bps": -4.732265001724322
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 120,
  "ALL_net_bps": -11.251584607692601,
  "SINGLE_net_bps": -4.552537926330045
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 180,
  "ALL_net_bps": -12.634628334911799,
  "SINGLE_net_bps": -8.081070829195832
 },
 {
  "segment": "DEV",
  "source": "REGRESSION_ABS4",
  "arm": "SHORT",
  "horizon": 240,
  "ALL_net_bps": -14.599224600829498,
  "SINGLE_net_bps": -11.6645818523
```

- 출력 해시 확인: 6/6 일치

### REPORT.md 앞 150줄 (전체 1099줄, 원문)

# R2-6 보유 시간 sweep

- 실행 UTC: `2026-10-01T05:38:36.949836+00:00` ~ `2026-10-01T05:48:18.666044+00:00`
- cutoff: `2026-06-30T23:59:00+00:00`
- 동결 가설: `보유 시간을 늘리면 롱 net이 오르고 숏은 짧을수록 낫다`
- 재학습: `0`; live: `0`; 비용: `4 bps`
- DEV: `fold <=605`; HOLD_B: `fold >=606 (탐색)`
- entry/exit: `close[t] / close[t+h]`; fold/data 끝은 `t+h < end_index`
- funding: `entry_time < funding_time <= exit_time`; `funding_bps=side*sum(rate)*10000`
- PW: `mean_influence`, `pw_inference`; 고정 블록 일 `7/14/30`, 거래 `20/50`

## 진입 규칙

| source | rule |
|---|---|
| THREE_CLASS_M010 | p_long-p_short > 0.10 LONG; < -0.10 SHORT |
| THREE_CLASS_M020 | p_long-p_short > 0.20 LONG; < -0.20 SHORT |
| REGRESSION_ABS4 | yhat > 4 LONG; yhat < -4 SHORT |
| WEIGHTED_M010 | weighted p_long-p_short > 0.10 LONG; < -0.10 SHORT |
| R2_1_PSTAR | arm p>p*; both eligible selects larger p-p* |

## 핵심 net

| segment | source | arm | horizon | ALL_net_bps | SINGLE_net_bps |
|---|---|---|---|---|---|
| DEV | R2_1_PSTAR | LONG | 5 | -4.057156 | -4.057156 |
| DEV | R2_1_PSTAR | LONG | 15 | -2.627997 | -2.627997 |
| DEV | R2_1_PSTAR | LONG | 30 | -2.402686 | -2.911013 |
| DEV | R2_1_PSTAR | LONG | 45 | -2.794584 | -2.653299 |
| DEV | R2_1_PSTAR | LONG | 60 | -2.141388 | -1.942203 |
| DEV | R2_1_PSTAR | LONG | 90 | -1.785164 | -1.210196 |
| DEV | R2_1_PSTAR | LONG | 120 | -1.647294 | -2.056158 |
| DEV | R2_1_PSTAR | LONG | 180 | -0.471761 | 0.052739 |
| DEV | R2_1_PSTAR | LONG | 240 | 0.984513 | 0.180755 |
| DEV | R2_1_PSTAR | SHORT | 5 | -3.251998 | -3.251998 |
| DEV | R2_1_PSTAR | SHORT | 15 | -4.256622 | -4.256622 |
| DEV | R2_1_PSTAR | SHORT | 30 | -4.644825 | -4.343906 |
| DEV | R2_1_PSTAR | SHORT | 45 | -4.843932 | -4.190149 |
| DEV | R2_1_PSTAR | SHORT | 60 | -4.893955 | -4.467042 |
| DEV | R2_1_PSTAR | SHORT | 90 | -7.060792 | -5.874187 |
| DEV | R2_1_PSTAR | SHORT | 120 | -9.311983 | -6.286544 |
| DEV | R2_1_PSTAR | SHORT | 180 | -12.101232 | -10.060335 |
| DEV | R2_1_PSTAR | SHORT | 240 | -14.522259 | -9.474434 |
| DEV | REGRESSION_ABS4 | LONG | 5 | -3.426798 | -3.426798 |
| DEV | REGRESSION_ABS4 | LONG | 15 | -1.747765 | -1.747765 |
| DEV | REGRESSION_ABS4 | LONG | 30 | -0.719446 | -1.407343 |
| DEV | REGRESSION_ABS4 | LONG | 45 | 0.035454 | -0.523804 |
| DEV | REGRESSION_ABS4 | LONG | 60 | -0.343439 | -0.333902 |
| DEV | REGRESSION_ABS4 | LONG | 90 | 0.230958 | -0.484255 |
| DEV | REGRESSION_ABS4 | LONG | 120 | 1.187385 | -0.053784 |
| DEV | REGRESSION_ABS4 | LONG | 180 | 2.504194 | 1.557027 |
| DEV | REGRESSION_ABS4 | LONG | 240 | 4.090594 | 1.334084 |
| DEV | REGRESSION_ABS4 | SHORT | 5 | -2.698112 | -2.698112 |
| DEV | REGRESSION_ABS4 | SHORT | 15 | -3.788235 | -3.788235 |
| DEV | REGRESSION_ABS4 | SHORT | 30 | -3.815825 | -3.623708 |
| DEV | REGRESSION_ABS4 | SHORT | 45 | -4.623747 | -4.229232 |
| DEV | REGRESSION_ABS4 | SHORT | 60 | -5.416572 | -4.263275 |
| DEV | REGRESSION_ABS4 | SHORT | 90 | -8.938161 | -4.732265 |
| DEV | REGRESSION_ABS4 | SHORT | 120 | -11.251585 | -4.552538 |
| DEV | REGRESSION_ABS4 | SHORT | 180 | -12.634628 | -8.081071 |
| DEV | REGRESSION_ABS4 | SHORT | 240 | -14.599225 | -11.664582 |
| DEV | THREE_CLASS_M010 | LONG | 5 | -3.759210 | -3.759210 |
| DEV | THREE_CLASS_M010 | LONG | 15 | -2.609522 | -2.609522 |
| DEV | THREE_CLASS_M010 | LONG | 30 | -1.991013 | -2.592706 |
| DEV | THREE_CLASS_M010 | LONG | 45 | -1.706223 | -2.332317 |
| DEV | THREE_CLASS_M010 | LONG | 60 | -1.411853 | -1.855551 |
| DEV | THREE_CLASS_M010 | LONG | 90 | -1.198189 | -1.398586 |
| DEV | THREE_CLASS_M010 | LONG | 120 | -0.625129 | -1.446616 |
| DEV | THREE_CLASS_M010 | LONG | 180 | 0.389015 | 0.756081 |
| DEV | THREE_CLASS_M010 | LONG | 240 | 1.463609 | -0.163055 |
| DEV | THREE_CLASS_M010 | SHORT | 5 | -3.317685 | -3.317685 |
| DEV | THREE_CLASS_M010 | SHORT | 15 | -4.758471 | -4.758471 |
| DEV | THREE_CLASS_M010 | SHORT | 30 | -5.936127 | -4.945899 |
| DEV | THREE_CLASS_M010 | SHORT | 45 | -6.012138 | -4.940653 |
| DEV | THREE_CLASS_M010 | SHORT | 60 | -6.166167 | -4.361465 |
| DEV | THREE_CLASS_M010 | SHORT | 90 | -9.461932 | -6.338287 |
| DEV | THREE_CLASS_M010 | SHORT | 120 | -11.619705 | -5.766607 |
| DEV | THREE_CLASS_M010 | SHORT | 180 | -14.837013 | -9.882812 |
| DEV | THREE_CLASS_M010 | SHORT | 240 | -18.607380 | -11.418609 |
| DEV | THREE_CLASS_M020 | LONG | 5 | -2.415572 | -2.415572 |
| DEV | THREE_CLASS_M020 | LONG | 15 | -0.151464 | -0.151464 |
| DEV | THREE_CLASS_M020 | LONG | 30 | 0.467651 | -0.270263 |
| DEV | THREE_CLASS_M020 | LONG | 45 | 0.159541 | -1.819630 |
| DEV | THREE_CLASS_M020 | LONG | 60 | 1.052757 | -0.238965 |
| DEV | THREE_CLASS_M020 | LONG | 90 | 1.767687 | -0.379767 |
| DEV | THREE_CLASS_M020 | LONG | 120 | 3.464642 | -1.262846 |
| DEV | THREE_CLASS_M020 | LONG | 180 | 7.414628 | 3.011135 |
| DEV | THREE_CLASS_M020 | LONG | 240 | 11.391687 | 5.290002 |
| DEV | THREE_CLASS_M020 | SHORT | 5 | 0.497458 | 0.497458 |
| DEV | THREE_CLASS_M020 | SHORT | 15 | -0.785060 | -0.785060 |
| DEV | THREE_CLASS_M020 | SHORT | 30 | -2.280092 | -1.659963 |
| DEV | THREE_CLASS_M020 | SHORT | 45 | -0.629495 | -0.782425 |
| DEV | THREE_CLASS_M020 | SHORT | 60 | 0.377624 | 1.703445 |
| DEV | THREE_CLASS_M020 | SHORT | 90 | -2.170787 | -0.714994 |
| DEV | THREE_CLASS_M020 | SHORT | 120 | -3.675091 | -2.812100 |
| DEV | THREE_CLASS_M020 | SHORT | 180 | -8.273863 | -8.700818 |
| DEV | THREE_CLASS_M020 | SHORT | 240 | -10.376039 | -10.895094 |
| DEV | WEIGHTED_M010 | LONG | 5 | -3.549243 | -3.549243 |
| DEV | WEIGHTED_M010 | LONG | 15 | -2.314377 | -2.314377 |
| DEV | WEIGHTED_M010 | LONG | 30 | -0.944893 | -2.206058 |
| DEV | WEIGHTED_M010 | LONG | 45 | -0.764763 | -2.422585 |
| DEV | WEIGHTED_M010 | LONG | 60 | -0.265296 | -1.732040 |
| DEV | WEIGHTED_M010 | LONG | 90 | 0.928430 | -1.329053 |
| DEV | WEIGHTED_M010 | LONG | 120 | 2.113573 | -0.910425 |
| DEV | WEIGHTED_M010 | LONG | 180 | 2.823191 | -2.071682 |
| DEV | WEIGHTED_M010 | LONG | 240 | 6.284609 | -1.593506 |
| DEV | WEIGHTED_M010 | SHORT | 5 | -1.610252 | -1.610252 |
| DEV | WEIGHTED_M010 | SHORT | 15 | -2.061833 | -2.061833 |
| DEV | WEIGHTED_M010 | SHORT | 30 | -1.897691 | -1.323285 |
| DEV | WEIGHTED_M010 | SHORT | 45 | -1.991542 | -1.725306 |
| DEV | WEIGHTED_M010 | SHORT | 60 | -1.932360 | -0.818482 |
| DEV | WEIGHTED_M010 | SHORT | 90 | -5.952792 | -3.506738 |
| DEV | WEIGHTED_M010 | SHORT | 120 | -7.390296 | -4.153444 |
| DEV | WEIGHTED_M010 | SHORT | 180 | -7.273145 | -4.440774 |
| DEV | WEIGHTED_M010 | SHORT | 240 | -10.635864 | -5.575820 |
| HOLD_B | R2_1_PSTAR | LONG | 5 | -2.696475 | -2.696475 |
| HOLD_B | R2_1_PSTAR | LONG | 15 | -0.893123 | -0.893123 |
| HOLD_B | R2_1_PSTAR | LONG | 30 | -0.013357 | 1.679840 |
| HOLD_B | R2_1_PSTAR | LONG | 45 | -0.383494 | -0.086374 |
| HOLD_B | R2_1_PSTAR | LONG | 60 | 3.008816 | -0.388547 |
| HOLD_B | R2_1_PSTAR | LONG | 90 | 3.642044 | 1.997020 |
| HOLD_B | R2_1_PSTAR | LONG | 120 | 4.237247 | 4.161386 |
| HOLD_B | R2_1_PSTAR | LONG | 180 | 1.818396 | -0.067903 |
| HOLD_B | R2_1_PSTAR | LONG | 240 | 0.713366 | 4.304527 |
| HOLD_B | R2_1_PSTAR | SHORT | 5 | -3.051688 | -3.051688 |
| HOLD_B | R2_1_PSTAR | SHORT | 15 | -1.425233 | -1.425233 |
| HOLD_B | R2_1_PSTAR | SHORT | 30 | -3.050847 | -2.992793 |
| HOLD_B | R2_1_PSTAR | SHORT | 45 | -3.272443 | -5.327432 |
| HOLD_B | R2_1_PSTAR | SHORT | 60 | -2.835192 | -4.890222 |
| HOLD_B | R2_1_PSTAR | SHORT | 90 | -2.458133 | -6.391714 |
| HOLD_B | R2_1_PSTAR | SHORT | 120 | -2.042202 | -9.139610 |
| HOLD_B | R2_1_PSTAR | SHORT | 180 | -4.835069 | -10.008087 |
| HOLD_B | R2_1_PSTAR | SHORT | 240 | -11.286372 | -15.218356 |
| HOLD_B | REGRESSION_ABS4 | LONG | 5 | -4.340408 | -4.340408 |
| HOLD_B | REGRESSION_ABS4 | LONG | 15 | -2.656112 | -2.656112 |
| HOLD_B | REGRESSION_ABS4 | LONG | 30 | -3.302032 | -4.630765 |
| HOLD_B | REGRESSION_ABS4 | LONG | 45 | -0.692805 | -6.080223 |
| HOLD_B | REGRESSION_ABS4 | LONG | 60 | 3.073483 | -9.399970 |
| HOLD_B | REGRESSION_ABS4 | LONG | 90 | 10.771147 | -4.798198 |
| HOLD_B | REGRESSION_ABS4 | LONG | 120 | 10.264912 | -3.100808 |
| HOLD_B | REGRESSION_ABS4 | LONG | 180 | -0.802509 | -9.838264 |
| HOLD_B | REGRESSION_ABS4 | LONG | 240 | -1.778075 | -17.088141 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 5 | -4.207788 | -4.207788 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 15 | -4.006978 | -4.006978 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 30 | -6.831092 | -9.357981 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 45 | -9.485168 | -13.827912 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 60 | -5.954525 | -10.082756 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 90 | -4.355477 | -12.088563 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 120 | -6.407173 | -14.571436 |
| HOLD_B | REGRESSION_ABS4 | SHORT | 180 | -8.750482 | 2.194518 |

## k45_gate_direction_r2_7_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_7.py`: `3 passed in 1.89s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T05:56:20.883761+00:00 |
| run_finished_utc | 2026-10-01T06:04:15.539300+00:00 |
| runtime_seconds | 474.655539 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 크기 반영 모델의 극단 점수 바는 인과적 기준에서도 net이 0보다 크다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| variants | ["regression_rmse", "weighted_multiclass", "MULTICLASS", "RESIDUAL"] |
| q | [0.01, 0.02, 0.05] |
| methods | ["EXPANDING_OOS", "FULL_SEGMENT", "ROLLING_180D"] |
| minimum_prior_oos_scores | 2000 |
| rolling_days | 180 |
| entry | close[t] |
| exit | close[t+45] |
| cost_bps | 4.0 |
| funding_interval | entry_time < funding_time <= exit_time |
| funding_cost_bps | side * sum(actual funding rate) * 10000 |
| books | ["SINGLE", "ALL"] |
| random_seed | 20261001 |
| random_repetitions | 1000 |
| random_match | same variant+segment+fold gate count; random bars without replacement; random +/-1 |
| pw_bootstrap_reps | 20000 |
| pw_bootstrap_seed | 20260930 |
| fixed_bootstrap_reps | 999 |
| fixed_daily_blocks | [7, 14, 30] |
| fixed_event_blocks | [20, 50] |
| local_data_only | True |
| new_model_fits | 0 |
| live_orders | 0 |
| winner_selection | 0 |
| row_counts | {"thresholds.parquet": 22356, "skipped_folds.parquet": 1032, "core_metrics.parquet": 288, "trim_sensitivity.parquet": 1440, "concentration.parquet": 288, "yearly.parquet": 864, "top_events.parquet": 2657, "random_baseline.parquet": 288, "random_repetitions.parquet": 288000, "size_direction.parquet": 288, "gate_candidates.parquet": 38814} |

### out_of_sample_result (원문)

```text
[
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 34,
  "net_mean_bps": 60.34327777170726
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 43,
  "net_mean_bps": 18.822028246784235
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 46,
  "net_mean_bps": 76.58836493474745
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 44,
  "net_mean_bps": 19.211572218154156
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 2,
  "net_mean_bps": 18.05495981416006
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 3,
  "net_mean_bps": 48.42378166197991
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 4,
  "net_mean_bps": 254.79995002213136
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 6,
  "net_mean_bps": 129.8532977612276
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 79,
  "net_mean_bps": 32.86049244729122
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 77,
  "net_mean_bps": 18.35781592521354
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 135,
  "net_mean_bps": 42.52661171677713
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 84,
  "net_mean_bps": 8.24927163919573
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 3,
  "net_mean_bps": 19.490399154090976
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 11,
  "net_mean_bps": -10.499140831646558
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 6,
  "net_mean_bps": 176.32058772829077
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 15,
  "net_mean_bps": 45.83567013489053
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 233,
  "net_mean_bps": 9.33890588300835
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 232,
  "net_mean_bps": 8.301056895044972
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 376,
  "net_mean_bps": 10.240646623943222
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "DEV",
  "n": 280,
  "net_mean_bps": 1.022351330883879
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 26,
  "net_mean_bps": 23.016505091720887
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 30,
  "net_mean_bps": 14.175776555227143
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "LONG",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 35,
  "net_mean_bps": 32.69159091006624
 },
 {
  "variant": "regression_rmse",
  "q": 0.05,
  "arm": "SHORT",
  "book": "ALL",
  "method": "EXPANDING_OOS",
  "segment": "HOLD_B",
  "n": 43,
  "net_mean_bps": 9.707243453168692
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "FULL_SEGMENT",
  "segment": "DEV",
  "n": 165,
  "net_mean_bps": 23.36974152289155
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "FULL_SEGMENT",
  "segment": "DEV",
  "n": 218,
  "net_mean_bps": 12.094935150701696
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "ALL",
  "method": "FULL_SEGMENT",
  "segment": "DEV",
  "n": 249,
  "net_mean_bps": 31.13592370374843
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "ALL",
  "method": "FULL_SEGMENT",
  "segment": "DEV",
  "n": 249,
  "net_mean_bps": 4.8866724928664755
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "SINGLE",
  "method": "FULL_SEGMENT",
  "segment": "HOLD_B",
  "n": 22,
  "net_mean_bps": 41.700329918536866
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "SINGLE",
  "method": "FULL_SEGMENT",
  "segment": "HOLD_B",
  "n": 19,
  "net_mean_bps": 28.804735517602634
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "LONG",
  "book": "ALL",
  "method": "FULL_SEGMENT",
  "segment": "HOLD_B",
  "n": 27,
  "net_mean_bps": 54.74843578753176
 },
 {
  "variant": "regression_rmse",
  "q": 0.01,
  "arm": "SHORT",
  "book": "ALL",
  "method": "FULL_SEGMENT",
  "segment": "HOLD_B",
  "n": 27,
  "net_mean_bps": 12.973704173810212
 },
 {
  "variant": "regression_rmse",
  "q": 0.02,
  "arm
```

- 출력 해시 확인: 12/12 일치

### REPORT.md 앞 150줄 (전체 7194줄, 원문)

# R2-7 꼬리 신호 인과 검증

- 실행 UTC: `2026-10-01T05:56:20.883761+00:00` ~ `2026-10-01T06:04:15.539300+00:00`
- cutoff: `2026-06-30T23:59:00+00:00`
- 동결 가설: `크기 반영 모델의 극단 점수 바는 인과적 기준에서도 net이 0보다 크다`
- 재학습: `0`; live: `0`; 비용: `4 bps`; 보유: `45분`
- 펀딩: `entry_time < funding_time <= exit_time`
- 기준: `EXPANDING_OOS`, `FULL_SEGMENT`, `ROLLING_180D`; 최소 과거 OOS: `2000`
- q: `0.01, 0.02, 0.05`; seed: `20261001`; 무작위 반복: `1000`

## 핵심

| variant | q | arm | book | method | segment | candidate_n | n | gross_mean_bps | funding_mean_bps | net_mean_bps | direction_hit_rate | pw_status | pw_error | pw_ci95_lower | pw_ci95_upper | daily_fixed_blocks | event_fixed_blocks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| regression_rmse | 0.010000 | LONG | SINGLE | EXPANDING_OOS | DEV | 90 | 34 | 64.267392 | -0.075885 | 60.343278 | 0.735294 | MEASURABLE |  | -17.843710 | 135.411229 | {"7":[-19.37782747853101,139.85593934888547],"14":[-17.671956025310145,136.86769152084452],"30":[-17.31162301645127,138.03751098864757]} | {"20":[20.891429648723566,105.47512387297427],"50":[22.405373070746435,95.73935462532418]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 90 | 43 | 22.742947 | -0.079081 | 18.822028 | 0.511628 | MEASURABLE |  | -48.542125 | 74.412021 | {"7":[-46.81297843073457,75.40862517280064],"14":[-42.716355221937704,69.95991316354798],"30":[-36.985933952561076,67.17188587988666]} | {"20":[-23.855711327010738,61.186661770858464],"50":[-13.446670090201138,52.75734861558806]} |
| regression_rmse | 0.010000 | LONG | ALL | EXPANDING_OOS | DEV | 90 | 46 | 80.482328 | -0.106037 | 76.588365 | 0.739130 | MEASURABLE |  | -8.511482 | 144.283452 | {"7":[-7.521404869866188,148.08164173324008],"14":[-6.765565500184877,145.37545097453895],"30":[0.7846943685538434,145.92207604817787]} | {"20":[18.736327129720898,130.85690293007528],"50":[30.712497671076534,126.45116811215686]} |
| regression_rmse | 0.010000 | SHORT | ALL | EXPANDING_OOS | DEV | 90 | 44 | 23.134288 | -0.077284 | 19.211572 | 0.522727 | MEASURABLE |  | -47.092407 | 74.016001 | {"7":[-45.00190199971634,74.87703090742014],"14":[-40.259861048307414,69.05836363268648],"30":[-35.26394962418114,66.48925347921086]} | {"20":[-20.558666120060554,58.65850950452314],"50":[-14.176057485937061,52.01204882394131]} |
| regression_rmse | 0.010000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 10 | 2 | 22.054960 | 0.000000 | 18.054960 | 0.500000 | MEASURABLE |  | -27.131360 | 45.186320 | {"7":[-27.13136013534923,45.186319949509354],"14":[-18.5968365756158,36.109919628320185],"30":[-18.05495981416014,36.109919628320185]} | {"20":[18.05495981416006,18.05495981416006],"50":[18.05495981416006,18.05495981416006]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 10 | 3 | 52.477015 | 0.053233 | 48.423782 | 0.333333 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-48.42378166198018,96.84756332395978],"14":[-48.423781661980065,96.84756332395978],"30":[-48.42378166197988,96.84756332395978]} | {"20":[-40.991237772063066,137.83880109602288],"50":[48.42378166197991,48.42378166197991]} |
| regression_rmse | 0.010000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 10 | 4 | 258.799950 | 0.000000 | 254.799950 | 0.750000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-259.338150182724,514.1381002048579],"14":[-255.02686003016046,509.5999000442632],"30":[-254.79995002213,509.5999000442632]} | {"20":[137.7665709603605,371.96724068812364],"50":[254.79995002213133,254.79995002213136]} |
| regression_rmse | 0.010000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 10 | 6 | 133.906531 | 0.053233 | 129.853298 | 0.500000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-129.85329776122845,259.7065955224546],"14":[-129.85329776122845,259.7065955224546],"30":[-129.85329776122828,259.7065955224546]} | {"20":[43.59837383868077,244.53323323712726],"50":[72.22875745872543,186.93715019108026]} |
| regression_rmse | 0.020000 | LONG | SINGLE | EXPANDING_OOS | DEV | 219 | 79 | 36.842214 | -0.018278 | 32.860492 | 0.645570 | MEASURABLE |  | -4.631114 | 70.103567 | {"7":[-4.204400245722979,73.49939979163699],"14":[-6.304619733245914,72.48242318778179],"30":[-7.516906059351399,80.13581810115198]} | {"20":[2.242328976469551,63.57263507029854],"50":[7.981759009684843,57.142457766350454]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 219 | 77 | 22.195542 | -0.162274 | 18.357816 | 0.545455 | MEASURABLE |  | -22.813750 | 53.469539 | {"7":[-25.736927547253114,55.01195354119673],"14":[-19.686217916637556,52.24271750111869],"30":[-20.614986227883964,49.179415889456024]} | {"20":[-8.87355434187576,42.17651581935871],"50":[-3.0645803874155426,38.823676377253115]} |
| regression_rmse | 0.020000 | LONG | ALL | EXPANDING_OOS | DEV | 219 | 135 | 46.509526 | -0.017086 | 42.526612 | 0.629630 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[3.491631608349671,76.76079018462795],"14":[4.949510699586156,73.05418487239476],"30":[5.834647197843779,77.76230216408771]} | {"20":[1.3668043166718107,77.7416471022462],"50":[15.164858213563399,69.26821272885222]} |
| regression_rmse | 0.020000 | SHORT | ALL | EXPANDING_OOS | DEV | 219 | 84 | 12.100520 | -0.148751 | 8.249272 | 0.535714 | MEASURABLE |  | -30.384887 | 40.687201 | {"7":[-29.646639808442846,42.02285150894774],"14":[-27.63799686963969,39.10503668354325],"30":[-25.966655886609875,35.88066146236852]} | {"20":[-17.63905792725985,33.46235967230997],"50":[-13.420040923537922,29.072778604992802]} |
| regression_rmse | 0.020000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 21 | 3 | 23.490399 | 0.000000 | 19.490399 | 0.666667 | MEASURABLE |  | -25.541333 | 45.031732 | {"7":[-25.54133270155049,45.031731855641496],"14":[-19.792945831463722,38.98079830818192],"30":[-19.490399154090834,38.98079830818192]} | {"20":[8.85658500850902,30.267757233666014],"50":[19.490399154090976,19.490399154090976]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 21 | 11 | -6.484623 | 0.014518 | -10.499141 | 0.454545 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-72.08351072577605,51.07289712021035],"14":[-76.42673361824524,59.10831984452983],"30":[-73.62769697863065,58.47328704850722]} | {"20":[-70.55910985340861,45.63924221014357],"50":[-51.83146767304315,24.277582735379447]} |
| regression_rmse | 0.020000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 21 | 6 | 180.320588 | 0.000000 | 176.320588 | 0.833333 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-176.61897976081065,352.9395674890994],"14":[-176.33550732991836,352.64117545658064],"30":[-176.32058772829197,352.64117545658064]} | {"20":[90.19613499358509,273.51448905072823],"50":[162.2000008328522,243.27339184840622]} |
| regression_rmse | 0.020000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 21 | 15 | 49.856963 | 0.021293 | 45.835670 | 0.533333 | MEASURABLE |  | -104.487239 | 139.808278 | {"7":[-103.71859426948339,141.32116623379414],"14":[-107.4204880596574,150.382943974329],"30":[-99.1220365601203,147.035709793427]} | {"20":[-39.59616418035285,133.9166943826368],"50":[-16.518783387506815,104.95898975544259]} |
| regression_rmse | 0.050000 | LONG | SINGLE | EXPANDING_OOS | DEV | 656 | 233 | 13.392468 | 0.053562 | 9.338906 | 0.557940 | MEASURABLE |  | -7.974625 | 27.113720 | {"7":[-7.680136275326506,25.263719901375836],"14":[-5.2537480570080515,24.453637021930174],"30":[-5.2471773461815,22.705826277227267]} | {"20":[-3.6934518088641006,21.917976673024732],"50":[-1.7193883682892057,21.67676519897139]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 656 | 232 | 12.216282 | -0.084775 | 8.301057 | 0.500000 | MEASURABLE |  | -12.036952 | 27.959516 | {"7":[-12.64792240259981,27.411384874246757],"14":[-11.996316292571379,27.611733894980745],"30":[-11.550765811523132,26.471221973027582]} | {"20":[-9.965131960541495,23.745445281114655],"50":[-8.367724641512833,23.302158005632965]} |
| regression_rmse | 0.050000 | LONG | ALL | EXPANDING_OOS | DEV | 656 | 376 | 14.283015 | 0.042368 | 10.240647 | 0.545213 | MEASURABLE |  | -12.795283 | 32.520558 | {"7":[-15.387017431086553,31.878083762142857],"14":[-13.368038938738136,30.136002297875734],"30":[-11.675740721942718,30.939383957961603]} | {"20":[-12.193976271007207,30.99689583040275],"50":[-9.802038793778111,30.224744351033884]} |
| regression_rmse | 0.050000 | SHORT | ALL | EXPANDING_OOS | DEV | 656 | 280 | 4.946296 | -0.076055 | 1.022351 | 0.489286 | MEASURABLE |  | -16.427139 | 19.677635 | {"7":[-16.651094900932517,18.93031221385587],"14":[-16.499664241444236,20.237918696955933],"30":[-15.805081131067844,17.828339361054088]} | {"20":[-15.463870832332915,16.871395221944454],"50":[-14.63854604685288,15.263893201349463]} |
| regression_rmse | 0.050000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 78 | 26 | 27.003470 | -0.013035 | 23.016505 | 0.615385 | MEASURABLE |  | -40.506431 | 69.395057 | {"7":[-36.07950803815276,65.52257246359298],"14":[-31.515642802887022,62.231008339728206],"30":[-20.07602760544519,57.830859315960936]} | {"20":[-22.9067399709217,64.5743550421918],"50":[-11.013940844204797,55.0138785720231]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 78 | 30 | 18.186940 | 0.011163 | 14.175777 | 0.500000 | MEASURABLE |  | -58.401506 | 67.380687 | {"7":[-55.63997829713169,70.27021627848384],"14":[-60.24713852081001,77.02303795679701],"30":[-52.03354743383228,72.1907188422031]} | {"20":[-36.05309034340502,61.360018206224616],"50":[-26.95478878923599,55.762971777121784]} |
| regression_rmse | 0.050000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 78 | 35 | 36.675719 | -0.015871 | 32.691591 | 0.657143 | MEASURABLE |  | -43.932825 | 82.604425 | {"7":[-37.25057653260072,78.88645769184865],"14":[-31.695648056005112,76.90606862216828],"30":[-22.02690503054273,74.63719988018363]} | {"20":[-18.733553899888605,85.25215677360598],"50":[-13.5972771538326,71.53917753252333]} |
| regression_rmse | 0.050000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 78 | 43 | 13.733988 | 0.026744 | 9.707243 | 0.488372 | MEASURABLE |  | -60.799300 | 60.361815 | {"7":[-57.091406519997186,61.78196062556858],"14":[-58.9359669012733,68.28014855474336],"30":[-53.66005865282266,66.39578277434333]} | {"20":[-40.625104330505195,60.17204037554974],"50":[-34.60167955457502,53.65296967094784]} |
| regression_rmse | 0.010000 | LONG | SINGLE | FULL_SEGMENT | DEV | 498 | 165 | 27.307117 | -0.062625 | 23.369742 | 0.618182 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[0.8929604216324023,45.9891187509497],"14":[0.0026461841332263702,43.942408698235056],"30":[3.2988030417476644,44.011104369214365]} | {"20":[6.893169872349265,40.2054466222219],"50":[10.957555220527349,36.152045981017025]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 498 | 218 | 15.902229 | -0.192706 | 12.094935 | 0.541284 | MEASURABLE |  | -4.664969 | 26.901608 | {"7":[-6.079878011317115,28.586974592036107],"14":[-4.407750467654703,26.25823844837633],"30":[-2.722531201475018,25.55917062964475]} | {"20":[-4.701256117786615,27.343545825007688],"50":[-3.0149505585163503,25.616697547350938]} |
| regression_rmse | 0.010000 | LONG | ALL | FULL_SEGMENT | DEV | 498 | 249 | 35.090961 | -0.044963 | 31.135924 | 0.622490 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[4.340304089561268,54.339752670054665],"14":[3.5828630516353392,53.430414415573935],"30":[5.12060655062637,53.76306723347393]} | {"20":[6.320069825794178,54.794001572303635],"50":[11.971834453523854,49.73958465003403]} |
| regression_rmse | 0.010000 | SHORT | ALL | FULL_SEGMENT | DEV | 498 | 249 | 8.696246 | -0.190427 | 4.886672 | 0.518072 | MEASURABLE |  | -12.318186 | 20.863726 | {"7":[-14.311717284522635,22.948810420475624],"14":[-12.806454079720242,20.709088580705227],"30":[-10.53612835304099,19.336391438638103]} | {"20":[-11.953104183900814,20.687986470589635],"50":[-7.819937583935804,17.791885569735655]} |
| regression_rmse | 0.010000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 54 | 22 | 45.662484 | -0.037845 | 41.700330 | 0.636364 | MEASURABLE |  | -38.956931 | 90.813313 | {"7":[-35.51387580311764,87.97442945931701],"14":[-37.89220813407381,91.93336896586356],"30":[-31.417201733276798,93.75723448819897]} | {"20":[-12.576049448667149,97.39845052000052],"50":[2.3616916176487592,81.16707701528786]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 54 | 19 | 32.839230 | 0.034495 | 28.804736 | 0.473684 | MEASURABLE |  | -69.114668 | 102.633918 | {"7":[-75.36692300458132,105.34309857890263],"14":[-75.72007177040996,114.32413759014737],"30":[-63.53793539982233,107.93200833755489]} | {"20":[-38.25572629710419,91.48742221375751],"50":[-14.890694253000117,86.38727545814508]} |
| regression_rmse | 0.010000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 54 | 27 | 58.717599 | -0.030837 | 54.748436 | 0.666667 | MEASURABLE |  | -51.228795 | 115.033320 | {"7":[-48.604973587077424,112.69066531371146],"14":[-51.68705188561165,116.15622598363203],"30":[-45.76753741550422,117.59071608790939]} | {"20":[-2.4472588272624094,118.75191898224593],"50":[2.0003776118976475,108.57537972615063]} |
| regression_rmse | 0.010000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 54 | 27 | 17.022252 | 0.048548 | 12.973704 | 0.444444 | MEASURABLE |  | -68.003220 | 78.547115 | {"7":[-71.16591146979593,82.65090478095891],"14":[-74.41550925500209,89.97155614603847],"30":[-65.85549879798668,87.32178119691201]} | {"20":[-54.4828343787672,78.58510090073554],"50":[-42.858717139832294,70.21656023323965]} |
| regression_rmse | 0.020000 | LONG | SINGLE | FULL_SEGMENT | DEV | 994 | 308 | 25.972619 | 0.044718 | 21.927901 | 0.571429 | MEASURABLE |  | -1.029653 | 40.532899 | {"7":[-0.7535841630247582,41.90837685638196],"14":[-1.2522005045484903,39.79436422911396],"30":[1.0005149183533248,39.098310329835115]} | {"20":[3.559239496079538,38.939640486406105],"50":[6.852603039764718,35.90255153134162]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 994 | 399 | 12.454537 | -0.150073 | 8.604609 | 0.513784 | MEASURABLE |  | -6.551276 | 22.025538 | {"7":[-6.529780773040436,22.23464883161175],"14":[-5.212585215868261,20.199639998657126],"30":[-3.176105724050375,19.37102634819771]} | {"20":[-4.141122157083164,20.597441059696333],"50":[-3.148675426299855,18.749471694761503]} |
| regression_rmse | 0.020000 | LONG | ALL | FULL_SEGMENT | DEV | 994 | 497 | 22.208999 | 0.018922 | 18.190077 | 0.569416 | MEASURABLE |  | -2.638767 | 37.859537 | {"7":[-4.9269269143082965,37.872898840340376],"14":[-4.397531708372487,36.49487003197268],"30":[-2.840617044367743,37.365270351832585]} | {"20":[-2.0975913612978836,36.197397538511034],"50":[0.8448712835604688,35.952778544602594]} |
| regression_rmse | 0.020000 | SHORT | ALL | FULL_SEGMENT | DEV | 994 | 497 | 7.220548 | -0.155467 | 3.376015 | 0.501006 | MEASURABLE |  | -11.222705 | 16.348479 | {"7":[-11.676870838257265,16.208750638577676],"14":[-9.522642952488473,15.30618968215029],"30":[-7.759763735261659,12.848624635898801]} | {"20":[-8.952288906823915,15.113253275126167],"50":[-6.889080732034602,12.961625419288202]} |
| regression_rmse | 0.020000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 108 | 37 | 4.187650 | -0.014557 | 0.202206 | 0.486486 | MEASURABLE |  | -28.601783 | 26.403752 | {"7":[-34.718649510602965,30.52475064071925],"14":[-25.47835035043621,24.243488980962734],"30":[-20.5237491503777,20.491879708096086]} | {"20":[-32.67822628592254,31.890314115187223],"50":[-26.927681903285613,23.019742956390193]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 108 | 38 | 8.278579 | 0.008813 | 4.269765 | 0.421053 | MEASURABLE |  | -52.930026 | 43.576189 | {"7":[-52.17579808688772,43.84866154969209],"14":[-53.31284331921691,46.72956932564787],"30":[-46.80986545784673,43.89235788930386]} | {"20":[-34.970806068103215,42.482645851728535],"50":[-32.73736759679697,38.23253453946216]} |
| regression_rmse | 0.020000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 108 | 54 | 12.906973 | -0.002837 | 8.909810 | 0.518519 | MEASURABLE |  | -27.903190 | 37.707434 | {"7":[-34.401884446037364,40.29359345317311],"14":[-23.871774386814288,33.20474249516792],"30":[-12.509841997557606,30.281029224861783]} | {"20":[-38.20082391035829,50.952616255355274],"50":[-28.412609563093092,44.233043837577874]} |
| regression_rmse | 0.020000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 108 | 54 | 6.030923 | 0.021296 | 2.009627 | 0.425926 | MEASURABLE |  | -55.527097 | 44.960831 | {"7":[-53.866531539632916,45.2681614748089],"14":[-55.200294056741654,49.669090166415295],"30":[-49.23396215078469,47.69353463674672]} | {"20":[-44.78639117705858,45.7146873814285],"50":[-38.90561745518533,40.6847944135978]} |
| regression_rmse | 0.050000 | LONG | SINGLE | FULL_SEGMENT | DEV | 2486 | 758 | 6.568888 | 0.089992 | 2.478896 | 0.522427 | MEASURABLE |  | -4.795022 | 9.574815 | {"7":[-4.235947448342911,9.66326492134942],"14":[-4.678357868416503,9.620906919058765],"30":[-4.9668349342214615,8.59091869579344]} | {"20":[-5.720158470468116,9.615620888864663],"50":[-4.37041095065501,8.61450872162543]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 2486 | 916 | 7.667842 | -0.144148 | 3.811990 | 0.518559 | MEASURABLE |  | -5.476481 | 12.472116 | {"7":[-5.3017235139378105,12.46960705425592],"14":[-6.2454282817340125,12.465769761001889],"30":[-4.65274650004028,12.308684977738594]} | {"20":[-4.1528911191256626,11.44864074477235],"50":[-3.703713316373364,11.908907598268694]} |
| regression_rmse | 0.050000 | LONG | ALL | FULL_SEGMENT | DEV | 2486 | 1243 | 9.993349 | 0.084645 | 5.908704 | 0.534191 | MEASURABLE |  | -2.762030 | 14.880404 | {"7":[-3.2367039415419843,15.088467213876712],"14":[-3.1678467500595477,14.250019103764554],"30":[-3.9074815899604634,14.572725721429688]} | {"20":[-3.622875973891297,14.670838739673203],"50":[-2.9323956222295493,14.455159656303165]} |
| regression_rmse | 0.050000 | SHORT | ALL | FULL_SEGMENT | DEV | 2486 | 1243 | 6.446280 | -0.139528 | 2.585808 | 0.505229 | MEASURABLE |  | -6.038455 | 10.872251 | {"7":[-5.858738560142348,10.594823428760918],"14":[-6.240174506612607,10.409784052473336],"30":[-4.71340845013831,10.117451917580098]} | {"20":[-5.496098232544575,10.204953346209798],"50":[-5.317231095230809,9.912146145150857]} |
| regression_rmse | 0.050000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 266 | 81 | 3.257439 | -0.005189 | -0.737372 | 0.506173 | MEASURABLE |  | -23.040372 | 20.030115 | {"7":[-23.19468803558034,18.70834874245884],"14":[-20.843846743118633,16.551999193502226],"30":[-15.930577615889412,15.041335280271596]} | {"20":[-24.444221084589067,23.43437923981776],"50":[-20.98517257017719,20.498981640419032]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 266 | 85 | 1.548358 | -0.001379 | -2.450263 | 0.435294 | MEASURABLE |  | -28.913951 | 18.829091 | {"7":[-30.553104494652825,17.867974747700675],"14":[-29.665320687143282,19.38172489506658],"30":[-26.29513813720529,17.616402080771348]} | {"20":[-27.937296341979785,20.535737021880827],"50":[-25.30741728338534,18.24847770245166]} |
| regression_rmse | 0.050000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 266 | 133 | 10.171311 | -0.007166 | 6.178477 | 0.548872 | MEASURABLE |  | -17.256768 | 26.021064 | {"7":[-16.57942039270161,24.0211281439456],"14":[-12.79035875397895,22.744080061979293],"30":[-9.05584091458681,20.62610765033928]} | {"20":[-22.476919445468635,32.169147215557956],"50":[-19.900466903936632,29.199752347146443]} |
| regression_rmse | 0.050000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 266 | 133 | 3.099224 | 0.012053 | -0.912829 | 0.458647 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-30.777093774731128,21.380496658822267],"14":[-28.431663134960115,22.06274360129143],"30":[-25.082881917636467,19.675886067469214]} | {"20":[-30.74914971840222,26.916412225220586],"50":[-29.279026886560306,25.380709961652585]} |
| regression_rmse | 0.010000 | LONG | SINGLE | ROLLING_180D | DEV | 457 | 151 | 15.244020 | 0.010960 | 11.233061 | 0.569536 | MEASURABLE |  | -8.835275 | 31.994923 | {"7":[-7.17719637388811,31.53669858561878],"14":[-8.141803046680666,29.221095264449637],"30":[-6.954256914870827,29.979534600175825]} | {"20":[-8.40375992665295,29.375388888996376],"50":[-3.970837997045109,26.134653834395834]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | ROLLING_180D | DEV | 457 | 174 | 14.693382 | -0.157984 | 10.851367 | 0.505747 | MEASURABLE |  | -10.246954 | 30.403423 | {"7":[-11.58476716553738,28.871202830703005],"14":[-8.809661715474563,27.74395985973279],"30":[-7.4782634352020505,27.488194669723953]} | {"20":[-5.060657269426718,24.483647894858766],"50":[-0.6668248092003459,21.824861029945147]} |
| regression_rmse | 0.010000 | LONG | ALL | ROLLING_180D | DEV | 457 | 240 | 13.285748 | 0.013589 | 9.272159 | 0.550000 | MEASURABLE |  | -9.234616 | 28.865387 | {"7":[-8.38861739331457,29.521090238111796],"14":[-10.392594115236447,27.095548730633055],"30":[-7.175319226486627,27.61116538456485]} | {"20":[-13.710639274357357,30.048777512919777],"50":[-10.413461026133772,25.59629662226324]} |
| regression_rmse | 0.010000 | SHORT | ALL | ROLLING_180D | DEV | 457 | 217 | 4.259039 | -0.136095 | 0.395133 | 0.493088 | MEASURABLE |  | -16.631453 | 17.033356 | {"7":[-16.74717607325597,16.325452921153733],"14":[-15.141990560586954,16.089570787651898],"30":[-13.492403469413848,14.370008702215548]} | {"20":[-12.232441270972522,12.074144467565908],"50":[-10.230550904410302,10.589729869077866]} |
| regression_rmse | 0.010000 | LONG | SINGLE | ROLLING_180D | HOLD_B | 78 | 27 | 19.167278 | -0.015937 | 15.183215 | 0.481481 | MEASURABLE |  | -22.843830 | 45.807364 | {"7":[-34.9366096877411,49.621904059729744],"14":[-27.655165620601267,47.47309497615231],"30":[-18.647968642358784,46.30813588661762]} | {"20":[-34.974040971404804,67.2637999038053],"50":[-27.272400225986623,55.195374567825816]} |
| regression_rmse | 0.010000 | SHORT | SINGLE | ROLLING_180D | HOLD_B | 78 | 27 | 25.249178 | 0.018622 | 21.230556 | 0.518519 | MEASURABLE |  | -52.048511 | 75.910934 | {"7":[-64.19846834973096,82.53037332513289],"14":[-67.63933557562075,91.74511103447489],"30":[-55.517332949701654,87.50660211279259]} | {"20":[-32.3334512980157,74.49901336960447],"50":[-19.85436289831051,69.79579599054468]} |
| regression_rmse | 0.010000 | LONG | ALL | ROLLING_180D | HOLD_B | 78 | 38 | 26.307971 | -0.011324 | 22.319295 | 0.500000 | MEASURABLE |  | -43.337190 | 66.977205 | {"7":[-43.93611302737423,65.0839256597207],"14":[-34.987991677185114,61.38184409131806],"30":[-23.166416117578116,59.49443242483516]} | {"20":[-43.52226012511625,84.69512670526368],"50":[-32.18187742431087,77.36777009691286]} |
| regression_rmse | 0.010000 | SHORT | ALL | ROLLING_180D | HOLD_B | 78 | 40 | 17.675964 | 0.032948 | 13.643017 | 0.475000 | MEASURABLE |  | -61.062955 | 67.180809 | {"7":[-61.284279747367066,68.3385124561492],"14":[-63.15661536128994,77.74654698495132],"30":[-56.34062197178841,75.03437890715219]} | {"20":[-39.617968819621936,66.52551143731456],"50":[-32.59721897390405,62.30474954377739]} |
| regression_rmse | 0.020000 | LONG | SINGLE | ROLLING_180D | DEV | 843 | 273 | 5.995823 | 0.043114 | 1.952709 | 0.534799 | MEASURABLE |  | -11.840214 | 16.747493 | {"7":[-10.707454894745664,16.250261350672886],"14":[-10.37624974242423,14.556665992108508],"30":[-9.249576509573782,13.768581043791166]} | {"20":[-8.197801001666477,13.801213716399461],"50":[-7.060372758021755,10.988421889566501]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | ROLLING_180D | DEV | 843 | 307 | 7.458663 | -0.107338 | 3.566002 | 0.514658 | MEASURABLE |  | -11.353796 | 18.147647 | {"7":[-11.796584241090557,17.381365474993643],"14":[-11.506514833212535,16.84923864159931],"30":[-10.618755352797855,17.68851372078174]} | {"20":[-13.09942172289308,17.555991555723626],"50":[-12.891154208722092,17.539128075320654]} |
| regression_rmse | 0.020000 | LONG | ALL | ROLLING_180D | DEV | 843 | 454 | 11.077651 | 0.046081 | 7.031570 | 0.541850 | MEASURABLE |  | -7.627870 | 23.438330 | {"7":[-7.318622136239952,22.04912953572402],"14":[-7.103727640703751,21.135949615801124],"30":[-6.935736318922864,21.697282583071498]} | {"20":[-7.885826813703881,22.10609049486048],"50":[-6.674650206218368,20.696168892734015]} |
| regression_rmse | 0.020000 | SHORT | ALL | ROLLING_180D | DEV | 843 | 389 | 5.689973 | -0.115538 | 1.805511 | 0.516710 | MEASURABLE |  | -10.759497 | 15.172067 | {"7":[-11.243248570559802,14.219685052147389],"14":[-10.63078974737997,14.523294127996467],"30":[-9.856010392905429,14.3082149525486]} | {"20":[-10.580897245476747,13.504841605355193],"50":[-11.245386030155284,13.442645960153826]} |
| regression_rmse | 0.020000 | LONG | SINGLE | ROLLING_180D | HOLD_B | 122 | 37 | 9.901904 | -0.014557 | 5.916460 | 0.486486 | MEASURABLE |  | -24.241616 | 33.317530 | {"7":[-31.699634936019347,33.310832936470774],"14":[-19.81063079837365,30.208014213908367],"30":[-14.385627388070322,28.042864967549473]} | {"20":[-27.070518359058948,39.1340180429694],"50":[-23.3255251142206,35.092622103662734]} |
| regression_rmse | 0.020000 | SHORT | SINGLE | ROLLING_180D | HOLD_B | 122 | 46 | 10.642238 | 0.044139 | 6.598099 | 0.456522 | MEASURABLE |  | -48.450620 | 44.532502 | {"7":[-46.44790248920379,43.012269741831695],"14":[-45.270501243007836,43.98004169962861],"30":[-37.16077040838658,42.92196102507029]} | {"20":[-31.76218382436911,43.304025820285],"50":[-28.896432487893307,41.78687232229367]} |
| regression_rmse | 0.020000 | LONG | ALL | ROLLING_180D | HOLD_B | 122 | 56 | 14.431950 | 0.004448 | 10.427502 | 0.500000 | MEASURABLE |  | -21.191692 | 37.336728 | {"7":[-31.173866886021376,38.48162334773643],"14":[-18.839404892489025,34.23969365612377],"30":[-9.949700904753232,33.03279183369058]} | {"20":[-32.76772842526533,57.585528090707214],"50":[-30.335358636058384,46.19629195352505]} |
| regression_rmse | 0.020000 | SHORT | ALL | ROLLING_180D | HOLD_B | 122 | 66 | 7.761490 | 0.048732 | 3.712759 | 0.454545 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-48.4702215112009,41.2751701671288],"14":[-47.4589235067054,45.71925961489233],"30":[-42.37284767851393,43.396027251409386]} | {"20":[-39.888766899329255,45.46534732289607],"50":[-32.31995329079373,41.43764177714336]} |
| regression_rmse | 0.050000 | LONG | SINGLE | ROLLING_180D | DEV | 2102 | 676 | 8.143873 | 0.072271 | 4.071602 | 0.528107 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-2.9782214260402435,11.384080478481978],"14":[-2.242161121482635,10.883847469417379],"30":[-1.861898301101247,10.437101638450454]} | {"20":[-1.7852929513343456,10.324356257754069],"50":[-0.8966236292134955,9.025260248284074]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | ROLLING_180D | DEV | 2102 | 730 | 4.554379 | -0.088363 | 0.642741 | 0.487671 | MEASURABLE |  | -6.612114 | 7.576146 | {"7":[-7.0430444163052695,7.675553820753295],"14":[-7.360221304154886,7.193105798644772],"30":[-7.070328630422852,8.303857270574023]} | {"20":[-6.615009647190919,8.29207524996847],"50":[-8.38949757185656,9.39242287888456]} |
| regression_rmse | 0.050000 | LONG | ALL | ROLLING_180D | DEV | 2102 | 1141 | 9.523310 | 0.082389 | 5.440921 | 0.540754 | MEASURABLE |  | -3.740647 | 14.239565 | {"7":[-4.042734193631043,14.555615886564063],"14":[-3.2634013524324743,13.251197540215083],"30":[-2.851574961497562,13.999955681383618]} | {"20":[-3.116816646681265,14.066443962775997],"50":[-2.36130621623764,13.123747950786473]} |
| regression_rmse | 0.050000 | SHORT | ALL | ROLLING_180D | DEV | 2102 | 961 | 3.677629 | -0.078192 | -0.244179 | 0.489074 | MEASURABLE |  | -7.433385 | 6.612201 | {"7":[-7.6755575267894915,6.536039891954891],"14":[-8.241413188928876,6.648767231205114],"30":[-7.464513777276042,7.218808180664818]} | {"20":[-8.153011772549828,7.179839680491207],"50":[-8.70917087373202,7.811800203172886]} |
| regression_rmse | 0.050000 | LONG | SINGLE | ROLLING_180D | HOLD_B | 291 | 62 | -5.813009 | 0.004589 | -9.817598 | 0.419355 | MEASURABLE |  | -37.328738 | 17.323565 | {"7":[-35.43192953364178,12.482346010879345],"14":[-30.262922921146995,10.318462574099042],"30":[-27.72325783339909,8.133270338326819]} | {"20":[-40.60538582260547,16.137804709710196],"50":[-34.32066290615909,14.711830078987363]} |
| regression_rmse | 0.050000 | SHORT | SINGLE | ROLLING_180D | HOLD_B | 291 | 118 | -5.978139 | -0.015097 | -9.963042 | 0.432203 | MEASURABLE |  | -19.936754 | 0.491101 | {"7":[-23.007159406696637,1.818230658762511],"14":[-19.91141259993799,1.1676568933456792],"30":[-18.61059790353542,0.3324295585556918]} | {"20":[-26.707293798786267,4.082197608535401],"50":[-23.574898016957114,2.6520285177564666]} |
| regression_rmse | 0.050000 | LONG | ALL | ROLLING_180D | HOLD_B | 291 | 100 | 5.945636 | 0.003894 | 1.941742 | 0.480000 | MEASURABLE |  | -25.172717 | 26.506118 | {"7":[-26.908038884984883,25.792506607663434],"14":[-19.841675579380738,21.014941834474094],"30":[-14.848881043889843,19.286543114870888]} | {"20":[-32.706963442286124,34.15218663821743],"50":[-27.72920300677591,32.31470512004173]} |
| regression_rmse | 0.050000 | SHORT | ALL | ROLLING_180D | HOLD_B | 291 | 191 | -2.069545 | 0.010118 | -6.079664 | 0.445026 | MEASURABLE |  | -16.181799 | 3.758602 | {"7":[-19.832063313239253,6.242626348243849],"14":[-17.23801052499141,4.630509616819753],"30":[-15.883144148208952,3.574541995961315]} | {"20":[-25.159931375698356,10.299443058407723],"50":[-22.266836600456976,9.304695165549337]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | EXPANDING_OOS | DEV | 89 | 41 | 46.479432 | -0.082993 | 42.562425 | 0.634146 | MEASURABLE |  | -7.929662 | 83.859644 | {"7":[-7.562455127802551,84.1102880957178],"14":[-6.935424923156091,83.94753211791567],"30":[-4.2783284069631335,84.50648951303124]} | {"20":[5.640050786313452,78.93460037671699],"50":[13.312243312215791,71.27176735331552]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 89 | 34 | 14.327056 | -0.381262 | 10.708318 | 0.529412 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-16.66873486282298,37.23632454581519],"14":[-16.76037729558424,38.24649955046054],"30":[-17.431429630165766,38.868033807219796]} | {"20":[-11.014125344868537,32.23923247798354],"50":[-8.04819077518591,28.762376156047246]} |
| weighted_multiclass | 0.010000 | LONG | ALL | EXPANDING_OOS | DEV | 89 | 55 | 62.681647 | -0.108778 | 58.790425 | 0.690909 | MEASURABLE |  | -1.332125 | 103.291932 | {"7":[-2.2466450823299624,106.97976243316315],"14":[-7.933434475301638,106.22058157620292],"30":[-1.9866373432032276,108.28969380161368]} | {"20":[12.288731537861196,98.87956033592184],"50":[22.197175810987602,93.37783722569266]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | EXPANDING_OOS | DEV | 89 | 34 | 14.327056 | -0.381262 | 10.708318 | 0.529412 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-16.66873486282298,37.23632454581519],"14":[-16.76037729558424,38.24649955046054],"30":[-17.431429630165766,38.868033807219796]} | {"20":[-11.014125344868537,32.23923247798354],"50":[-8.04819077518591,28.762376156047246]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 3 | 2 | 219.913957 | 0.000000 | 215.913957 | 0.500000 | MEASURABLE |  | -243.143158 | 449.980716 | {"7":[-224.9903578023547,440.90431528351576],"14":[-216.36777749722808,431.82791496232653],"30":[-215.91395748116395,431.82791496232653]} | {"20":[215.91395748116315,215.91395748116315],"50":[215.91395748116315,215.91395748116315]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 3 | 1 | 256.109291 | 0.159700 | 251.949591 | 1.000000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-251.9495914428211,503.8991828856362],"14":[-251.94959144281972,503.8991828856362],"30":[-251.94959144281847,503.8991828856362]} | {"20":[251.9495914428178,251.9495914428178],"50":[251.9495914428178,251.9495914428178]} |
| weighted_multiclass | 0.010000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 3 | 2 | 219.913957 | 0.000000 | 215.913957 | 0.500000 | MEASURABLE |  | -243.143158 | 449.980716 | {"7":[-224.9903578023547,440.90431528351576],"14":[-216.36777749722808,431.82791496232653],"30":[-215.91395748116395,431.82791496232653]} | {"20":[215.91395748116315,215.91395748116315],"50":[215.91395748116315,215.91395748116315]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 3 | 1 | 256.109291 | 0.159700 | 251.949591 | 1.000000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-251.9495914428211,503.8991828856362],"14":[-251.94959144281972,503.8991828856362],"30":[-251.94959144281847,503.8991828856362]} | {"20":[251.9495914428178,251.9495914428178],"50":[251.9495914428178,251.9495914428178]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | EXPANDING_OOS | DEV | 229 | 92 | 21.284050 | 0.005707 | 17.278344 | 0.586957 | MEASURABLE |  | -8.381531 | 44.502501 | {"7":[-10.035105950382789,43.10292978477662],"14":[-8.380680898478314,42.71428067677125],"30":[-9.377192077370399,47.80288952805273]} | {"20":[-8.014673711236007,46.69703017494224],"50":[-3.3533514583051662,37.799083204628836]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 229 | 85 | 4.078499 | -0.044538 | 0.123036 | 0.482353 | MEASURABLE |  | -17.161769 | 17.789208 | {"7":[-18.246609151075607,17.70088183698958],"14":[-15.80165316825452,16.151187205990105],"30":[-15.96077169382138,15.96164239969061]} | {"20":[-12.880774035424007,12.589172174455607],"50":[-10.172191859433063,9.778657136997529]} |
| weighted_multiclass | 0.020000 | LONG | ALL | EXPANDING_OOS | DEV | 229 | 138 | 35.584259 | -0.009693 | 31.593952 | 0.623188 | MEASURABLE |  | 2.321576 | 55.542464 | {"7":[1.9388584127018085,56.49569768754584],"14":[0.7059579845218025,55.60393277150365],"30":[4.212014787330869,57.385206624255154]} | {"20":[1.882912605935502,59.487691075631616],"50":[8.156319276795962,54.79563295712341]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | EXPANDING_OOS | DEV | 229 | 91 | 6.168562 | -0.041601 | 2.210163 | 0.505495 | MEASURABLE |  | -13.375543 | 18.078129 | {"7":[-14.368975353162373,17.61303700798613],"14":[-12.629228342452802,16.880215428120938],"30":[-13.06250724967844,17.052934067970696]} | {"20":[-8.896751994121084,13.840370821376927],"50":[-7.014791949625035,11.44559108253316]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 9 | 4 | 48.928827 | 0.000000 | 44.928827 | 0.250000 | MEASURABLE |  | -88.348465 | 126.164200 | {"7":[-140.39038194027222,171.09302706365284],"14":[-95.461555364098,133.27729121387532],"30":[-66.26809875537046,126.16420048747703]} | {"20":[-93.01540932658368,185.3192085164494],"50":[44.92882657617615,44.92882657617616]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 9 | 4 | 47.229083 | 0.039925 | 43.189158 | 0.500000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-115.98090125959683,166.6357874872567],"14":[-110.24813151733346,163.71935524244455],"30":[-83.34603914728396,155.12914132941108]} | {"20":[-28.38845389611142,92.14174346870647],"50":[43.18915787762651,43.18915787762651]} |
| weighted_multiclass | 0.020000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 9 | 5 | 129.939204 | 0.000000 | 125.939204 | 0.400000 | MEASURABLE |  | -202.308449 | 322.557180 | {"7":[-202.3084486731605,316.86670789280424],"14":[-145.69098982357633,268.94982650711916],"30":[-137.32014954411966,268.9498265071191]} | {"20":[-25.41467773962397,293.91877635354695],"50":[123.15100305936393,181.70946642396044]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 9 | 4 | 47.229083 | 0.039925 | 43.189158 | 0.500000 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-115.98090125959683,166.6357874872567],"14":[-110.24813151733346,163.71935524244455],"30":[-83.34603914728396,155.12914132941108]} | {"20":[-28.38845389611142,92.14174346870647],"50":[43.18915787762651,43.18915787762651]} |
| weighted_multiclass | 0.050000 | LONG | SINGLE | EXPANDING_OOS | DEV | 834 | 337 | 11.941395 | 0.078521 | 7.862873 | 0.543027 | MEASURABLE |  | -5.322283 | 20.882110 | {"7":[-5.642266109834464,19.82584302039507],"14":[-5.201965401666223,19.538530300308473],"30":[-4.6231155696763455,21.83829580729875]} | {"20":[-4.338008171769641,19.644688054404057],"50":[-2.7748792105296367,19.612843405640575]} |
| weighted_multiclass | 0.050000 | SHORT | SINGLE | EXPANDING_OOS | DEV | 834 | 306 | 8.831243 | -0.052619 | 4.883862 | 0.509804 | MEASURABLE |  | -5.185292 | 14.797844 | {"7":[-5.541435876329706,15.02103473635305],"14":[-4.660136242164143,13.954268507302444],"30":[-4.362633583326009,13.41518759155265]} | {"20":[-3.2640497160881026,12.722031283758481],"50":[-1.8224437172785617,11.562894822515688]} |
| weighted_multiclass | 0.050000 | LONG | ALL | EXPANDING_OOS | DEV | 834 | 500 | 12.825799 | 0.070298 | 8.755502 | 0.548000 | MEASURABLE |  | -2.249596 | 19.230121 | {"7":[-2.5722408091213786,19.411854557146388],"14":[-1.2375499684022149,18.379645821693344],"30":[-1.1021676408608556,18.686216887209987]} | {"20":[-3.2884196918458777,20.556022396404252],"50":[-2.6845058279485468,19.625914746051173]} |
| weighted_multiclass | 0.050000 | SHORT | ALL | EXPANDING_OOS | DEV | 834 | 334 | 6.412562 | -0.054196 | 2.466757 | 0.500000 | MEASURABLE |  | -7.735549 | 12.928715 | {"7":[-7.959815771363809,13.016777054714227],"14":[-7.311494495919744,11.397883906930472],"30":[-6.684788958617391,10.942867903940728]} | {"20":[-6.24626038548311,11.599269239423464],"50":[-5.481501622936051,10.438365348466677]} |
| weighted_multiclass | 0.050000 | LONG | SINGLE | EXPANDING_OOS | HOLD_B | 50 | 19 | 27.398750 | -0.012137 | 23.410887 | 0.526316 | MEASURABLE |  | -21.536502 | 54.583937 | {"7":[-27.595024705846765,58.7981336530119],"14":[-25.347932392158395,56.13201022583182],"30":[-20.24594614845068,55.23384640806482]} | {"20":[-12.446621735742116,59.73054003205145],"50":[-1.2945303176330292,51.46507640122452]} |
| weighted_multiclass | 0.050000 | SHORT | SINGLE | EXPANDING_OOS | HOLD_B | 50 | 25 | 13.359215 | 0.006388 | 9.352827 | 0.560000 | MEASURABLE |  | -47.007288 | 52.985952 | {"7":[-53.52234117263859,57.22481314212228],"14":[-58.241913378977536,60.24723164894249],"30":[-57.32747966137412,60.08616242116644]} | {"20":[-32.156096205878754,44.41300832279097],"50":[-20.68896432586952,39.956391336566604]} |
| weighted_multiclass | 0.050000 | LONG | ALL | EXPANDING_OOS | HOLD_B | 50 | 24 | 51.770531 | -0.044300 | 47.814831 | 0.625000 | MEASURABLE |  | -48.404621 | 104.255547 | {"7":[-42.82704384602733,101.28976104682225],"14":[-42.97818940953632,102.06874786771064],"30":[-35.199248407122504,101.15825834966247]} | {"20":[-11.567324877461083,98.39843423654168],"50":[0.2598713755710449,90.34315471036018]} |
| weighted_multiclass | 0.050000 | SHORT | ALL | EXPANDING_OOS | HOLD_B | 50 | 26 | 22.695757 | 0.012285 | 18.683472 | 0.576923 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-60.25616757737316,74.22449224839778],"14":[-66.4477954330912,77.31076823496906],"30":[-64.81294549912238,77.15589397749196]} | {"20":[-30.04738414541967,58.53529273170402],"50":[-21.08402116535857,55.46308530437784]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | FULL_SEGMENT | DEV | 498 | 177 | 32.973335 | -0.020472 | 28.993806 | 0.576271 | MEASURABLE |  | -17.299393 | 60.223940 | {"7":[-17.902331381109764,59.834416079528424],"14":[-18.395819418863976,59.27025413743222],"30":[-16.00950103352061,58.76651798747751]} | {"20":[-6.085860997361426,57.844860747844855],"50":[2.29098810118375,53.77862089105123]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 498 | 235 | 14.076771 | -0.104197 | 10.180968 | 0.514894 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-5.095393122933011,24.949458693327962],"14":[-9.071520302143387,24.516466300385858],"30":[-9.77947174077152,25.381773695474504]} | {"20":[-6.84416352133935,24.93004533282503],"50":[-7.063265130669819,23.54309712214741]} |
| weighted_multiclass | 0.010000 | LONG | ALL | FULL_SEGMENT | DEV | 498 | 249 | 37.248056 | -0.015347 | 33.263403 | 0.598394 | MEASURABLE |  | -5.624046 | 62.289164 | {"7":[-4.580898960837175,61.78620747326961],"14":[-6.99491455879356,60.51387208581268],"30":[-2.2436351219315753,58.555147378518136]} | {"20":[1.5400045382019272,58.83811097979248],"50":[8.577862393368829,57.922541060565514]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | FULL_SEGMENT | DEV | 498 | 249 | 14.752099 | -0.120283 | 10.872382 | 0.522088 | MEASURABLE |  | -4.118771 | 24.690248 | {"7":[-3.2595698283581473,25.427703924999165],"14":[-8.081802978607064,25.197873745195096],"30":[-8.304463462356887,25.999732112383022]} | {"20":[-4.975968430969745,26.198048392926133],"50":[-5.4067817511396985,25.777560021427696]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 54 | 22 | 38.382065 | -0.010482 | 34.392547 | 0.500000 | MEASURABLE |  | -17.808797 | 74.162636 | {"7":[-18.535078806457463,72.60296115189053],"14":[-20.080636553684087,75.02083278968504],"30":[-8.230697134403016,75.3390834043561]} | {"20":[-8.145184781983545,77.81607871216539],"50":[2.232892096722857,70.14309167697147]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 54 | 26 | 19.818943 | 0.021688 | 15.797255 | 0.576923 | MEASURABLE |  | -36.416980 | 54.607499 | {"7":[-45.513870199869665,57.84476403511988],"14":[-50.62723498024759,61.87209077494186],"30":[-46.36326668526118,61.20516197960439]} | {"20":[-22.320538325794374,49.098392014629844],"50":[-11.468379577280407,47.468980569921]} |
| weighted_multiclass | 0.010000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 54 | 27 | 58.011923 | -0.039378 | 54.051301 | 0.592593 | MEASURABLE |  | -32.039464 | 111.107308 | {"7":[-27.05401047122681,108.21876696877578],"14":[-28.767989017966208,111.33505454694172],"30":[-18.866091127737242,112.41631850922268]} | {"20":[4.252757138557072,106.75197804557375],"50":[13.162415776831345,94.44522275021924]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 54 | 27 | 28.570438 | 0.026800 | 24.543638 | 0.592593 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-52.11641583030172,74.36529806662043],"14":[-59.83363728152932,78.24346455681933],"30":[-53.977575009614725,77.60123682797584]} | {"20":[-21.212944473865665,65.5623747470274],"50":[-9.813086839326065,58.86493843500011]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | FULL_SEGMENT | DEV | 994 | 347 | 22.077148 | 0.042324 | 18.034824 | 0.544669 | MEASURABLE |  | -8.716526 | 36.946359 | {"7":[-7.7104857779361105,36.803845233588085],"14":[-9.007264774939,36.24151149244318],"30":[-8.681180524379833,36.05584530459963]} | {"20":[-3.5120041156511803,37.03315234559328],"50":[-2.44986644273342,35.17016437340183]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 994 | 429 | 8.111503 | -0.114780 | 4.226283 | 0.512821 | MEASURABLE |  | -6.431753 | 14.407334 | {"7":[-6.23465566658393,14.372934637962992],"14":[-7.695202730948812,14.568946884877995],"30":[-6.950039418931147,13.680677288906072]} | {"20":[-5.983341735157144,13.41625319154096],"50":[-4.300089408098807,12.771475611895795]} |
| weighted_multiclass | 0.020000 | LONG | ALL | FULL_SEGMENT | DEV | 994 | 497 | 21.992744 | 0.035334 | 17.957410 | 0.569416 | MEASURABLE |  | -2.932422 | 33.491669 | {"7":[-3.2386267935998525,33.41447562118688],"14":[-2.9833178572254297,33.23038007770499],"30":[-3.024938634326766,33.102205726728506]} | {"20":[-1.965636684129482,34.02605279071583],"50":[0.2572669978829829,34.59426141417337]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | FULL_SEGMENT | DEV | 994 | 497 | 4.334330 | -0.119289 | 0.453619 | 0.494970 | MEASURABLE |  | -8.941354 | 10.051023 | {"7":[-8.249112164647913,10.108055232248049],"14":[-8.82640408878371,9.207775925479202],"30":[-8.53231458520762,8.556959060941248]} | {"20":[-8.2689750951539,8.842112999388352],"50":[-7.523475062000575,7.588632470993123]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 108 | 37 | 19.369577 | -0.008849 | 15.378426 | 0.540541 | MEASURABLE |  | -18.619754 | 42.878309 | {"7":[-20.281177534072636,44.280296181799486],"14":[-15.168834314839973,40.517557781749645],"30":[-8.529808661144344,37.81295835666407]} | {"20":[-5.279304601005407,36.19545598680226],"50":[-1.790847160898263,31.383420188765964]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 108 | 45 | 5.398279 | 0.009300 | 1.388979 | 0.511111 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-36.60802785910404,31.371040424202768],"14":[-41.76369807277364,35.67715058461681],"30":[-38.642291737176414,35.82048490347259]} | {"20":[-36.27898870658137,36.23725747602849],"50":[-29.737285745043476,32.840254239641624]} |
| weighted_multiclass | 0.020000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 108 | 54 | 30.362134 | -0.022143 | 26.384277 | 0.611111 | MEASURABLE |  | -23.800118 | 63.012052 | {"7":[-19.017274612562563,60.633771144598896],"14":[-19.808407049807055,60.9131812908372],"30":[-11.096893850140976,61.13078532315109]} | {"20":[-3.3824409286266715,53.960380546546105],"50":[0.19600931237064145,50.38547316208839]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 108 | 54 | 13.557821 | 0.013665 | 9.544156 | 0.481481 | MEASURABLE |  | -50.222900 | 51.206067 | {"7":[-48.18975678504039,49.46461963150442],"14":[-54.20388023860874,55.782899212115986],"30":[-49.90897279811877,55.43777363806624]} | {"20":[-35.34382253868143,53.78577259326222],"50":[-30.245966301155164,50.90685445185817]} |
| weighted_multiclass | 0.050000 | LONG | SINGLE | FULL_SEGMENT | DEV | 2486 | 806 | 8.591267 | 0.096882 | 4.494386 | 0.523573 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-5.514979689265299,13.593229835836727],"14":[-6.238038144968366,13.98774980748542],"30":[-6.386465173884524,13.464322904270823]} | {"20":[-5.181865003479521,12.976294139924425],"50":[-4.896731360289005,12.504299115332339]} |
| weighted_multiclass | 0.050000 | SHORT | SINGLE | FULL_SEGMENT | DEV | 2486 | 1021 | 8.197582 | -0.118457 | 4.316040 | 0.512243 | MEASURABLE |  | -2.015721 | 10.495945 | {"7":[-2.270351605199073,10.235864564847704],"14":[-2.6150779493814724,10.214620063256335],"30":[-1.7894224022108016,9.658938008067366]} | {"20":[-1.590072354690962,9.76551770164397],"50":[-1.489191028289393,9.299973016294011]} |
| weighted_multiclass | 0.050000 | LONG | ALL | FULL_SEGMENT | DEV | 2486 | 1243 | 10.089247 | 0.085445 | 6.003802 | 0.536605 | MEASURABLE |  | -3.238256 | 14.769046 | {"7":[-3.823212586926166,15.189133146029045],"14":[-4.504698333188827,14.81761830397323],"30":[-4.219668605977041,15.07394372656673]} | {"20":[-2.578851037650235,14.374633554699676],"50":[-3.418897073806802,14.463020425795438]} |
| weighted_multiclass | 0.050000 | SHORT | ALL | FULL_SEGMENT | DEV | 2486 | 1243 | 5.526161 | -0.118409 | 1.644570 | 0.502011 | MEASURABLE |  | -4.326016 | 7.626406 | {"7":[-4.724692505656792,7.656055302441754],"14":[-4.979712036639738,7.006853396670895],"30":[-3.887080953725959,6.569932055005506]} | {"20":[-4.092866590057481,7.344572518679261],"50":[-3.91899131692591,6.545570647436509]} |
| weighted_multiclass | 0.050000 | LONG | SINGLE | FULL_SEGMENT | HOLD_B | 266 | 80 | -2.127229 | -0.023035 | -6.104194 | 0.475000 | MEASURABLE |  | -27.290252 | 14.926953 | {"7":[-25.35861613849177,10.825037457673064],"14":[-23.299416264027784,8.52901450399227],"30":[-18.589930649408586,7.183449813107593]} | {"20":[-24.42912269783428,11.7759451104223],"50":[-21.57961187442239,8.737081800817247]} |
| weighted_multiclass | 0.050000 | SHORT | SINGLE | FULL_SEGMENT | HOLD_B | 266 | 108 | -9.899455 | 0.000084 | -13.899539 | 0.444444 | MEASURABLE |  | -28.600090 | 1.475901 | {"7":[-27.855725264574815,0.6275565242248557],"14":[-25.84635264230411,-0.46468633778298596],"30":[-24.549031978167392,-2.1392043110473065]} | {"20":[-26.63521378092501,-1.0992624285639856],"50":[-24.986180796816363,-3.4388233521610623]} |
| weighted_multiclass | 0.050000 | LONG | ALL | FULL_SEGMENT | HOLD_B | 266 | 133 | 8.910399 | -0.006912 | 4.917311 | 0.541353 | MEASURABLE |  | -18.217974 | 25.249107 | {"7":[-15.58997630203505,20.901921513235788],"14":[-12.273392569433897,19.528952956167995],"30":[-8.347142833893596,18.589631552105715]} | {"20":[-15.883770256215128,22.417800799750296],"50":[-12.677321574105848,19.26116127934557]} |
| weighted_multiclass | 0.050000 | SHORT | ALL | FULL_SEGMENT | HOLD_B | 266 | 133 | -1.043528 | 0.002707 | -5.046235 | 0.466165 | MEASURABLE |  | -26.500284 | 11.768191 | {"7":[-25.626287029631918,10.368454776639204],"14":[-23.846455286855704,10.697614433365004],"30":[-21.907232011392576,9.339987204506404]} | {"20":[-25.293603656339204,11.120989627547097],"50":[-22.9561896389885,8.98864453423376]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | ROLLING_180D | DEV | 465 | 198 | 14.742091 | 0.073312 | 10.668780 | 0.580808 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-6.144528429788723,27.2872966073436],"14":[-4.357205136642207,27.130095410972224],"30":[-3.1915889402645696,27.883123716285866]} | {"20":[-6.022942151666493,26.627502373671447],"50":[-2.629486249832839,23.82717858425635]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | ROLLING_180D | DEV | 465 | 166 | 11.799019 | -0.055865 | 7.854884 | 0.518072 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-6.531524714461208,21.20014893845485],"14":[-5.513085514199217,20.645503106875594],"30":[-5.837382807068032,19.74295621349775]} | {"20":[-1.1297366711691126,17.203439714512932],"50":[0.8583935951784136,13.976541667509913]} |
| weighted_multiclass | 0.010000 | LONG | ALL | ROLLING_180D | DEV | 465 | 286 | 15.751364 | 0.058942 | 11.692422 | 0.566434 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-2.2904760687850487,24.873741970755013],"14":[-1.7548084873508287,24.950466489053213],"30":[-0.40842002122685805,25.075027505707787]} | {"20":[-8.110382458866583,28.455054166473133],"50":[-4.25235755699603,26.613463592628232]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | ROLLING_180D | DEV | 465 | 179 | 10.583922 | -0.051808 | 6.635730 | 0.519553 | MEASURABLE |  | -7.366815 | 21.176909 | {"7":[-8.024452374000028,20.59902152059923],"14":[-6.914704833732232,19.808586489589594],"30":[-6.371363175850581,18.442401887494356]} | {"20":[-2.917749458662204,16.367841723843338],"50":[-0.38448584837311817,14.179926010605202]} |
| weighted_multiclass | 0.010000 | LONG | SINGLE | ROLLING_180D | HOLD_B | 48 | 15 | 22.369835 | -0.015373 | 18.385208 | 0.400000 | MEASURABLE |  | -33.511099 | 53.307294 | {"7":[-44.687938825257405,61.690136231719464],"14":[-42.208278177822685,56.134284587459575],"30":[-31.461943763694265,53.969903661600014]} | {"20":[-29.972892298514864,65.63332133879582],"50":[-15.889085416998313,52.338910376708704]} |
| weighted_multiclass | 0.010000 | SHORT | SINGLE | ROLLING_180D | HOLD_B | 48 | 27 | 20.387913 | 0.019719 | 16.368194 | 0.555556 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-40.66285949317172,56.956270571400076],"14":[-44.43651032153797,61.71658917595124],"30":[-38.9704571324663,60.425517437215206]} | {"20":[-22.175345076250473,48.895440336752785],"50":[-12.051632905413097,44.15472172444114]} |
| weighted_multiclass | 0.010000 | LONG | ALL | ROLLING_180D | HOLD_B | 48 | 17 | 54.759965 | -0.013565 | 50.773530 | 0.470588 | MEASURABLE |  | -81.984383 | 126.764911 | {"7":[-73.98182161794452,121.68787916035674],"14":[-71.79388575256088,118.49931350765807],"30":[-62.311825975388814,116.31403784448536]} | {"20":[-23.37024108944216,130.37831789052905],"50":[-11.127483052324308,111.15746299550253]} |
| weighted_multiclass | 0.010000 | SHORT | ALL | ROLLING_180D | HOLD_B | 48 | 31 | 37.853546 | 0.027477 | 33.826069 | 0.548387 | MEASURABLE |  | -62.549022 | 92.036542 | {"7":[-61.12770233678373,90.19020618021511],"14":[-60.60640361207312,93.95042082628714],"30":[-56.70862245194665,92.47988241220582]} | {"20":[-22.489027932511156,86.73985685319178],"50":[-10.273957584877785,82.50640689684728]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | ROLLING_180D | DEV | 891 | 328 | 11.793042 | 0.055452 | 7.737590 | 0.545732 | UNMEASURABLE | invalid Politis-White block length | nan | nan | {"7":[-4.669099692158125,18.785551214173573],"14":[-3.220041008111605,19.217752114552635],"30":[-3.985055501316496,20.80632416335064]} | {"20":[-5.660342392136001,22.6869766162975],"50":[-5.565075711275507,21.9790173908107]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | ROLLING_180D | DEV | 891 | 346 | 4.288362 | -0.086338 | 0.374699 | 0.473988 | MEASURABLE |  | -9.248480 | 9.971867 | {"7":[-9.182445244310916,9.483421656289853],"14":[-8.882324309504728,9.505096340226384],"30":[-8.322823313644676,8.799483061075888]} | {"20":[-7.323815578201241,8.498165682162465],"50":[-7.063472926378593,7.495459772894674]} |
| weighted_multiclass | 0.020000 | LONG | ALL | ROLLING_180D | DEV | 891 | 502 | 12.236736 | 0.054487 | 8.182249 | 0.545817 | MEASURABLE |  | -1.492705 | 17.900671 | {"7":[-0.7214918962470644,17.674689382034796],"14":[-0.2852181099933784,16.912341020157246],"30":[-0.35459744461051024,17.43349519252059]} | {"20":[-4.461589713225749,20.55685217811545],"50":[-4.320496014766016,19.682936622842618]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | ROLLING_180D | DEV | 891 | 389 | 3.301764 | -0.088891 | -0.609345 | 0.478149 | MEASURABLE |  | -10.335582 | 9.129547 | {"7":[-10.1212459973604,8.701645263331029],"14":[-9.894452564054863,8.42162526596521],"30":[-9.37646689873122,7.3373852439270415]} | {"20":[-7.99927053539819,6.357403640244274],"50":[-7.515902729957521,5.61609477958604]} |
| weighted_multiclass | 0.020000 | LONG | SINGLE | ROLLING_180D | HOLD_B | 97 | 27 | 29.081957 | -0.034422 | 25.116379 | 0.518519 | MEASURABLE |  | -15.517495 | 58.987048 | {"7":[-20.70310819850227,63.194585813517975],"14":[-10.962446457413328,56.86666337604077],"30":[-5.341493029429053,52.44298604084545]} | {"20":[-4.467319504908936,57.46383650352458],"50":[0.5309583304452232,52.11035773381025]} |
| weighted_multiclass | 0.020000 | SHORT | SINGLE | ROLLING_180D | HOLD_B | 97 | 51 | 3.416089 | 0.008206 | -0.592117 | 0.490196 | MEASURABLE |  | -30.376739 | 24.968359 | {"7":[-29.399363150472233,23.393344167959082],"14":[-32.001601790875654,24.745814285884947],"30":[-28.819643946536825,24.46989558064833]} | {"20":[-30.027849032495812,26.504111283711687],"50":[-25.800622349099683,23.720322998597165]} |
| weighted_multiclass | 0.020000 | LONG | ALL | ROLLING_180D | HOLD_B | 97 | 37 | 41.992919 | -0.031351 | 38.024270 | 0.594595 | MEASURABLE |  | -23.807396 | 81.550551 | {"7":[-20.176434055434996,77.8874200089092],"14":[-14.695530047068956,76.4843250038897],"30":[-5.604912530389306,76.10302068558859]} | {"20":[0.7388661645819568,73.01154513441108],"50":[7.606898932555225,66.12911605568002]} |
| weighted_multiclass | 0.020000 | SHORT | ALL | ROLLING_180D | HOLD_B | 97 | 60 | 11.057005 | 0.012298 | 7.044707 | 0.466667 | MEASURABLE |  | -44.557320 | 43.464094 | {"7":[-42.643067499447056,40.419590466057144],"14":[-43.333543825972875,43.32896754007218],"30":[-39.17988462018451,42.471270087766946]} | {"20":[-31.79063627824427,44.082535756388744],"50":[-30.39143957696828,39.63345245734646]} |

## k45_gate_direction_r2_8_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_8.py`: `3 passed in 1.85s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T06:13:27.011471+00:00 |
| run_finished_utc | 2026-10-01T06:15:12.508281+00:00 |
| runtime_seconds | 105.51189309963956 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 단일 포지션에서 더 높은 확률 쪽만 거래하면(3분류 m=0.20, 롱 240분/숏 60분) HOLD_B net이 0보다 크다 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| book | SINGLE_ONLY_FIRST_COME |
| max_positions | 1 |
| decision | one higher side per gate bar; ties abstain; occupied signals dropped |
| causal_margin | fold k uses abs(score) from pilot_fold < k; minimum 2000; quantile level matches fixed m=0.20 DEV rate |
| r21_model_horizon_map | {"LONG": {"45": 45, "120": 60, "240": 60}, "SHORT": {"5": 5, "15": 15, "60": 45}} |
| r21_mapping_reason | largest available prediction horizon not exceeding requested hold |
| baseline | same admitted bars; side-specific configured holds; common valid bars; random +/-1 x1000 |
| entry_exit | close[t] / close[t+h] |
| cost_bps | 4.0 |
| funding_interval | entry_time < funding_time <= exit_time |
| funding_cost_bps | side * sum(actual funding rate) * 10000 |
| seed | 20261001 |
| random_repetitions | 1000 |
| pw_bootstrap_reps | 20000 |
| fixed_bootstrap_reps | 999 |
| fixed_daily_blocks | [7, 14, 30] |
| fixed_event_blocks | [20, 50] |
| local_data_only | True |
| downloads | 0 |
| model_fits | 0 |
| live_orders | 0 |
| primary_result | [{"segment": "DEV", "n": 1324, "net_mean_bps": 3.0970742348222413}, {"segment": "HOLD_B", "n": 55, "net_mean_bps": -29.218270033197825}] |
| hypothesis_hold_b_net_gt_zero | False |

- 출력 해시 확인: 13/13 일치

### REPORT.md 앞 150줄 (전체 2752줄, 원문)

# R2-8

- UTC: `2026-10-01T06:13:27.011471+00:00` / `2026-10-01T06:15:12.508281+00:00`
- cutoff: `2026-06-30T23:59:00+00:00`
- fit: `0`
- live: `0`
- cost_bps: `4`
- seed: `20261001`
- HOLD_B: `exploratory=1`

## PRIMARY

| segment | n | net_mean_bps | net_sum_bps | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | pw_ci95_lower | pw_ci95_upper | monthly_positive_share | funding_total_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 1324 | 3.097074 | 4100.526287 | 2.297274 | 1.714500 | 0.088334 | 0.565710 | nan | nan | 0.551724 | 550.853000 |
| HOLD_B | 55 | -29.218270 | -1607.004852 | -41.957733 | -48.181242 | -62.415728 | 0.436364 | -60.730629 | 11.757019 | 0.333333 | 1.481900 |

## 9x7

| rule | h_long | h_short | label | n_DEV | n_HOLD_B | net_mean_bps_DEV | net_mean_bps_HOLD_B |
|---|---|---|---|---|---|---|---|
| ORIGINAL_CAUSAL_M020_RATE | 45 | 5 |  | 982.000000 | 74.000000 | 1.063753 | -12.335889 |
| ORIGINAL_CAUSAL_M020_RATE | 45 | 15 |  | 982.000000 | 74.000000 | 0.477972 | -10.035345 |
| ORIGINAL_CAUSAL_M020_RATE | 45 | 60 |  | 944.000000 | 74.000000 | 1.459807 | -13.567609 |
| ORIGINAL_CAUSAL_M020_RATE | 120 | 5 |  | 804.000000 | 70.000000 | 3.408037 | -11.966520 |
| ORIGINAL_CAUSAL_M020_RATE | 120 | 15 |  | 804.000000 | 70.000000 | 2.857984 | -10.674027 |
| ORIGINAL_CAUSAL_M020_RATE | 120 | 60 |  | 769.000000 | 70.000000 | 4.126300 | -15.444110 |
| ORIGINAL_CAUSAL_M020_RATE | 240 | 5 |  | 710.000000 | 63.000000 | 8.708437 | -25.723197 |
| ORIGINAL_CAUSAL_M020_RATE | 240 | 15 |  | 710.000000 | 63.000000 | 8.341858 | -24.287094 |
| ORIGINAL_CAUSAL_M020_RATE | 240 | 60 |  | 676.000000 | 63.000000 | 9.917779 | -29.587187 |
| ORIGINAL_M010 | 45 | 5 |  | 7054.000000 | 599.000000 | -2.610739 | -2.708942 |
| ORIGINAL_M010 | 45 | 15 |  | 7054.000000 | 599.000000 | -3.189226 | -1.578744 |
| ORIGINAL_M010 | 45 | 60 |  | 5918.000000 | 511.000000 | -3.029643 | -5.812561 |
| ORIGINAL_M010 | 120 | 5 |  | 4957.000000 | 448.000000 | -2.230379 | -2.232679 |
| ORIGINAL_M010 | 120 | 15 |  | 4957.000000 | 448.000000 | -2.779187 | -0.875212 |
| ORIGINAL_M010 | 120 | 60 |  | 4181.000000 | 388.000000 | -2.963117 | -4.353945 |
| ORIGINAL_M010 | 240 | 5 |  | 3837.000000 | 350.000000 | -1.684373 | -1.099079 |
| ORIGINAL_M010 | 240 | 15 |  | 3837.000000 | 350.000000 | -2.671103 | 0.497044 |
| ORIGINAL_M010 | 240 | 60 |  | 3248.000000 | 313.000000 | -2.326880 | -5.130207 |
| ORIGINAL_M020 | 45 | 5 |  | 2239.000000 | 65.000000 | -1.365175 | -4.930786 |
| ORIGINAL_M020 | 45 | 15 |  | 2239.000000 | 65.000000 | -1.946162 | -3.236642 |
| ORIGINAL_M020 | 45 | 60 |  | 2109.000000 | 65.000000 | 0.073422 | -4.495448 |
| ORIGINAL_M020 | 120 | 5 |  | 1701.000000 | 62.000000 | -0.733929 | 1.335116 |
| ORIGINAL_M020 | 120 | 15 |  | 1701.000000 | 62.000000 | -1.394161 | 1.824690 |
| ORIGINAL_M020 | 120 | 60 |  | 1605.000000 | 62.000000 | -0.132254 | -0.664677 |
| ORIGINAL_M020 | 240 | 5 |  | 1396.000000 | 55.000000 | 3.508142 | -26.963959 |
| ORIGINAL_M020 | 240 | 15 |  | 1396.000000 | 55.000000 | 2.942682 | -26.412075 |
| ORIGINAL_M020 | 240 | 60 | PRIMARY | 1324.000000 | 55.000000 | 3.097074 | -29.218270 |
| R2_1_PSTAR | 45 | 5 |  | 7342.000000 | 540.000000 | -1.748278 | -0.887793 |
| R2_1_PSTAR | 45 | 15 |  | 7939.000000 | 668.000000 | -3.351863 | -0.082859 |
| R2_1_PSTAR | 45 | 60 |  | 7239.000000 | 674.000000 | -3.701090 | -1.475269 |
| R2_1_PSTAR | 120 | 5 |  | 4707.000000 | 353.000000 | -2.472081 | 2.982296 |
| R2_1_PSTAR | 120 | 15 |  | 5160.000000 | 455.000000 | -3.781957 | 1.886915 |
| R2_1_PSTAR | 120 | 60 |  | 4860.000000 | 467.000000 | -4.865682 | 3.605792 |
| R2_1_PSTAR | 240 | 5 |  | 3512.000000 | 274.000000 | -0.941878 | 2.971590 |
| R2_1_PSTAR | 240 | 15 |  | 3830.000000 | 348.000000 | -3.356115 | 0.081737 |
| R2_1_PSTAR | 240 | 60 |  | 3736.000000 | 366.000000 | -3.804910 | 5.364071 |
| RESIDUAL_CAUSAL_M020_RATE | 45 | 5 |  | 1301.000000 | 81.000000 | 2.807996 | 0.147922 |
| RESIDUAL_CAUSAL_M020_RATE | 45 | 15 |  | 1301.000000 | 81.000000 | 2.899919 | 2.431323 |
| RESIDUAL_CAUSAL_M020_RATE | 45 | 60 |  | 1251.000000 | 74.000000 | 3.636482 | -2.076794 |
| RESIDUAL_CAUSAL_M020_RATE | 120 | 5 |  | 1074.000000 | 71.000000 | 0.917508 | 15.230884 |
| RESIDUAL_CAUSAL_M020_RATE | 120 | 15 |  | 1074.000000 | 71.000000 | 0.873181 | 16.870832 |
| RESIDUAL_CAUSAL_M020_RATE | 120 | 60 |  | 1035.000000 | 64.000000 | 2.285322 | 11.915655 |
| RESIDUAL_CAUSAL_M020_RATE | 240 | 5 |  | 927.000000 | 64.000000 | 2.188822 | 3.499868 |
| RESIDUAL_CAUSAL_M020_RATE | 240 | 15 |  | 927.000000 | 64.000000 | 2.199087 | 6.579342 |
| RESIDUAL_CAUSAL_M020_RATE | 240 | 60 |  | 892.000000 | 57.000000 | 3.406747 | 2.392383 |
| RESIDUAL_M010 | 45 | 5 |  | 7799.000000 | 572.000000 | -1.881391 | -3.907966 |
| RESIDUAL_M010 | 45 | 15 |  | 7799.000000 | 572.000000 | -2.397654 | -2.910043 |
| RESIDUAL_M010 | 45 | 60 |  | 6339.000000 | 482.000000 | -1.609419 | -7.838745 |
| RESIDUAL_M010 | 120 | 5 |  | 5262.000000 | 431.000000 | -1.057753 | -0.457800 |
| RESIDUAL_M010 | 120 | 15 |  | 5262.000000 | 431.000000 | -1.845636 | 1.551197 |
| RESIDUAL_M010 | 120 | 60 |  | 4450.000000 | 362.000000 | -1.615084 | -1.345692 |
| RESIDUAL_M010 | 240 | 5 |  | 3966.000000 | 346.000000 | -0.528553 | -0.118624 |
| RESIDUAL_M010 | 240 | 15 |  | 3966.000000 | 346.000000 | -1.554854 | 2.341041 |
| RESIDUAL_M010 | 240 | 60 |  | 3393.000000 | 290.000000 | -1.357016 | -1.849639 |
| RESIDUAL_M020 | 45 | 5 |  | 2984.000000 | 75.000000 | 1.231092 | 1.234276 |
| RESIDUAL_M020 | 45 | 15 |  | 2984.000000 | 75.000000 | 0.847642 | 3.700350 |
| RESIDUAL_M020 | 45 | 60 |  | 2737.000000 | 68.000000 | 1.406137 | -1.074907 |
| RESIDUAL_M020 | 120 | 5 |  | 2264.000000 | 67.000000 | 0.172248 | 18.985756 |
| RESIDUAL_M020 | 120 | 15 |  | 2264.000000 | 67.000000 | -0.348829 | 20.723611 |
| RESIDUAL_M020 | 120 | 60 |  | 2091.000000 | 60.000000 | 0.441302 | 15.887580 |
| RESIDUAL_M020 | 240 | 5 |  | 1842.000000 | 61.000000 | -0.070818 | 16.164302 |
| RESIDUAL_M020 | 240 | 15 |  | 1842.000000 | 61.000000 | -0.390612 | 19.395226 |
| RESIDUAL_M020 | 240 | 60 |  | 1702.000000 | 54.000000 | 1.160354 | 16.636976 |

## core

| rule | segment | h_long | h_short | label | candidate_n | invalid_exit_n | dropped_n | max_concurrent | n | net_sum_bps | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps | funding_mean_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ORIGINAL_M010 | DEV | 45 | 5 |  | 10226 | 0 | 3172 | 1 | 7054 | -18416.155105 | -2.610739 | MEASURABLE |  | 9.595468 | -4.031733 | -1.191308 | 1758 | 1232 | 0.299204 | 20000 | 999 | {"7":[-3.9663427040616064,-1.2277397185084071],"14":[-4.085350012342695,-1.1355566366353766],"30":[-4.0570199992681655,-1.2592816694720634]} | {"20":[-4.225724246330477,-1.128797284306016],"50":[-4.071786967005679,-1.1970793845035472]} | -2.724277 | -2.824610 | -3.064119 | 0.536150 | 0.275862 | 16 | 58 | 430.338500 | 0.061006 |
| ORIGINAL_M010 | HOLD_B | 45 | 5 |  | 767 | 0 | 168 | 1 | 599 | -1622.656185 | -2.708942 | MEASURABLE |  | 1.510953 | -7.563415 | 2.484724 | 180 | 134 | 0.255556 | 20000 | 999 | {"7":[-8.145271446118315,3.0195080782067083],"14":[-8.014044640734866,3.0511514670932702],"30":[-7.61968048321803,3.2033294255708396]} | {"20":[-7.775599010263175,2.4184557139890743],"50":[-8.030199397853274,2.6857164488751697]} | -3.316204 | -3.717951 | -4.777302 | 0.539232 | 0.333333 | 2 | 6 | 3.121400 | 0.005211 |
| ORIGINAL_M020 | DEV | 45 | 5 |  | 2967 | 0 | 728 | 1 | 2239 | -3056.625890 | -1.365175 | MEASURABLE |  | 2.568037 | -4.714609 | 2.006191 | 1758 | 763 | 0.565984 | 20000 | 999 | {"7":[-4.782267967795327,1.9429953214216213],"14":[-4.783451761841488,2.0688066021419234],"30":[-4.671384498641314,1.7807588505728067]} | {"20":[-4.84479820124795,1.8972126524131652],"50":[-4.314298844021998,1.8386944587117318]} | -1.838788 | -2.196413 | -2.866941 | 0.547119 | 0.482759 | 28 | 58 | 198.605700 | 0.088703 |
| ORIGINAL_M020 | HOLD_B | 45 | 5 |  | 72 | 0 | 7 | 1 | 65 | -320.501060 | -4.930786 | MEASURABLE |  | 6.209837 | -23.405177 | 13.463636 | 180 | 43 | 0.761111 | 20000 | 999 | {"7":[-23.12834827062316,12.79688027111678],"14":[-21.31509643283976,10.358170413156422],"30":[-17.560406456675594,8.347541388619721]} | {"20":[-20.933868477877336,8.10392009125821],"50":[-16.381519887903654,6.282826112104152]} | -13.337660 | -16.214583 | -21.980654 | 0.553846 | 0.500000 | 3 | 6 | -0.411000 | -0.006323 |
| ORIGINAL_CAUSAL_M020_RATE | DEV | 45 | 5 |  | 1253 | 0 | 271 | 1 | 982 | 1044.605422 | 1.063753 | MEASURABLE |  | 2.281228 | -4.747276 | 6.931974 | 1758 | 475 | 0.729807 | 20000 | 999 | {"7":[-5.578609276514928,6.884619296191241],"14":[-5.223731470645081,6.486430094954862],"30":[-4.923691623913241,6.621058195075436]} | {"20":[-4.339698348280022,6.103462916003249],"50":[-3.871189384539836,5.904615798943167]} | 0.300639 | -0.130960 | -1.182337 | 0.542770 | 0.518519 | 28 | 54 | 48.631800 | 0.049523 |
| ORIGINAL_CAUSAL_M020_RATE | HOLD_B | 45 | 5 |  | 83 | 0 | 9 | 1 | 74 | -912.855781 | -12.335889 | MEASURABLE |  | 6.198787 | -27.971435 | 4.747828 | 180 | 46 | 0.744444 | 20000 | 999 | {"7":[-27.825374173168548,3.7129629104023696],"14":[-25.449192013312146,3.3713402759548625],"30":[-23.427686409230816,2.86850747977895]} | {"20":[-27.47589414068862,5.881057401873276],"50":[-26.8888836010376,1.4420585125562368]} | -19.807739 | -21.799398 | -26.221649 | 0.513514 | 0.166667 | 1 | 6 | -0.411000 | -0.005554 |
| RESIDUAL_M010 | DEV | 45 | 5 |  | 11307 | 0 | 3508 | 1 | 7799 | -14672.965070 | -1.881391 | MEASURABLE |  | 2.897666 | -3.250493 | -0.519714 | 1758 | 1257 | 0.284983 | 20000 | 999 | {"7":[-3.246717856140711,-0.510558119238756],"14":[-3.345682549714116,-0.4712543399678575],"30":[-3.206493907087748,-0.558646635192811]} | {"20":[-3.2728847084520805,-0.3480856454943839],"50":[-3.4221590095604064,-0.4172521434814289]} | -2.017382 | -2.113791 | -2.321857 | 0.536992 | 0.327586 | 19 | 58 | 494.032400 | 0.063346 |
| RESIDUAL_M010 | HOLD_B | 45 | 5 |  | 726 | 0 | 154 | 1 | 572 | -2235.356700 | -3.907966 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 127 | 0.294444 | 0 | 999 | {"7":[-9.773218742634072,1.911434716624393],"14":[-9.337557808524812,2.3492775179054735],"30":[-9.0702172663236,1.3437859343892167]} | {"20":[-8.348668311118308,0.7358866732950928],"50":[-8.353236635752571,1.024172614297735]} | -4.279447 | -4.614766 | -5.557575 | 0.524476 | 0.333333 | 2 | 6 | 2.311200 | 0.004041 |
| RESIDUAL_M020 | DEV | 45 | 5 |  | 3985 | 0 | 1001 | 1 | 2984 | 3673.578632 | 1.231092 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 877 | 0.501138 | 0 | 999 | {"7":[-1.7308325049000879,3.9321926464674073],"14":[-1.8493296100780663,4.045672659537058],"30":[-2.1141721676585488,4.090247391211735]} | {"20":[-1.797856586474727,4.170618952437254],"50":[-1.5525570673068811,4.153840763880137]} | 0.876633 | 0.625526 | 0.022139 | 0.556971 | 0.551724 | 32 | 58 | 260.786900 | 0.087395 |
| RESIDUAL_M020 | HOLD_B | 45 | 5 |  | 80 | 0 | 5 | 1 | 75 | 92.570737 | 1.234276 | MEASURABLE |  | 26.121703 | -8.931125 | 11.053425 | 180 | 35 | 0.805556 | 20000 | 999 | {"7":[-11.619673907975121,13.057849476962437],"14":[-10.744937580686342,13.002284980534395],"30":[-8.556899310489703,10.436552750699448]} | {"20":[-11.791876108535218,13.411266917001207],"50":[-7.9475170146887875,10.741512046937695]} | -5.953222 | -8.334889 | -13.796863 | 0.546667 | 0.500000 | 3 | 6 | 0.711800 | 0.009491 |
| RESIDUAL_CAUSAL_M020_RATE | DEV | 45 | 5 |  | 1619 | 0 | 318 | 1 | 1301 | 3653.202545 | 2.807996 | MEASURABLE |  | 1.188848 | -1.022083 | 6.624919 | 1758 | 595 | 0.661547 | 20000 | 999 | {"7":[-1.26478609744508,6.3797936284151895],"14":[-0.9635823657459519,6.324283546007383],"30":[-0.8399784791164349,6.200829408146403]} | {"20":[-0.8317936611131977,6.946153221644138],"50":[-0.6541637438235886,6.252794640961153]} | 2.233480 | 1.692605 | 0.722745 | 0.555726 | 0.592593 | 32 | 54 | 91.789400 | 0.070553 |
| RESIDUAL_CAUSAL_M020_RATE | HOLD_B | 45 | 5 |  | 89 | 0 | 8 | 1 | 81 | 11.981665 | 0.147922 | MEASURABLE |  | 20.450837 | -10.843174 | 11.052511 | 180 | 37 | 0.794444 | 20000 | 999 | {"7":[-12.60046319501288,11.830276928171255],"14":[-11.77195276846159,12.311546813113832],"30":[-9.38451441822627,10.17284952193171]} | {"20":[-12.88846250347299,12.335508061468563],"50":[-8.951577796666811,9.263651853155904]} | -6.514094 | -8.721974 | -13.768019 | 0.543210 | 0.500000 | 3 | 6 | 0.690800 | 0.008528 |
| R2_1_PSTAR | DEV | 45 | 5 |  | 11514 | 0 | 4172 | 1 | 7342 | -12835.854787 | -1.748278 | MEASURABLE |  | 1.231450 | -3.327227 | -0.149135 | 1758 | 1242 | 0.293515 | 20000 | 999 | {"7":[-3.1691901268345726,-0.2888336025314917],"14":[-3.347288872640651,-0.23912711224331984],"30":[-3.3402754528628655,-0.21946106807479615]} | {"20":[-3.411295346123044,-0.12195795341139237],"50":[-3.2964521619995857,-0.18239005024290833]} | -1.857243 | -1.953522 | -2.178891 | 0.539771 | 0.379310 | 22 | 58 | 476.197700 | 0.064859 |
| R2_1_PSTAR | HOLD_B | 45 | 5 |  | 847 | 0 | 307 | 1 | 540 | -479.407962 | -0.887793 | MEASURABLE |  | 3.938260 | -6.106551 | 4.416983 | 180 | 129 | 0.283333 | 20000 | 999 | {"7":[-5.926026724964838,3.9591075574453147],"14":[-5.765496786337983,4.326525311838663],"30":[-5.664927551023998,3.86290236158932]} | {"20":[-5.756309147987643,4.561556758817078],"50":[-6.131807360034112,4.388278151328881]} | -1.558148 | -2.000685 | -3.212841 | 0.544444 | 0.333333 | 2 | 6 | 3.574700 | 0.006620 |
| ORIGINAL_M010 | DEV | 45 | 15 |  | 10226 | 0 | 3172 | 1 | 7054 | -22496.796682 | -3.189226 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 1232 | 0.299204 | 0 | 999 | {"7":[-4.6202733800515166,-1.6101673162351842],"14":[-4.70175459054258,-1.7180584032310995],"30":[-4.779619124140219,-1.608922454170995]} | {"20":[-4.888911503547122,-1.5920741750221246],"50":[-4.8192315981823866,-1.7403246565212047]} | -3.302845 | -3.403261 | -3.643016 | 0.532039 | 0.258621 | 15 | 58 | 397.673500 | 0.056376 |
| ORIGINAL_M010 | HOLD_B | 45 | 15 |  | 767 | 0 | 168 | 1 | 599 | -945.667642 | -1.578744 | MEASURABLE |  | 2.246891 | -6.722018 | 3.562491 | 180 | 134 | 0.255556 | 20000 | 999 | {"7":[-6.820327996292244,3.317790420295757],"14":[-6.3072260194309715,3.3135377421928895],"30":[-5.957840449324213,3.065627557709244]} | {"20":[-6.382341764569804,3.0959074150164483],"50":[-6.278222468401387,3.0329700308081184]} | -2.184117 | -2.583967 | -3.637591 | 0.549249 | 0.333333 | 2 | 6 | 3.248900 | 0.005424 |
| ORIGINAL_M020 | DEV | 45 | 15 |  | 2967 | 0 | 728 | 1 | 2239 | -4357.456501 | -1.946162 | MEASURABLE |  | 2.394202 | -5.508658 | 1.637280 | 1758 | 763 | 0.565984 | 20000 | 999 | {"7":[-5.506566361786482,1.3376908816447355],"14":[-5.520093504886554,1.739964280871612],"30":[-5.8347407114657655,1.8275406072557565]} | {"20":[-5.727411807022742,1.4435019086648786],"50":[-5.347399906227771,1.6863036344413815]} | -2.420035 | -2.777919 | -3.449228 | 0.546226 | 0.500000 | 29 | 58 | 188.939100 | 0.084385 |
| ORIGINAL_M020 | HOLD_B | 45 | 15 |  | 72 | 0 | 7 | 1 | 65 | -210.381738 | -3.236642 | MEASURABLE |  | 3.321348 | -24.990579 | 17.061363 | 180 | 43 | 0.761111 | 20000 | 999 | {"7":[-23.095420069729098,15.159019493167882],"14":[-21.394726394783383,12.447458572081404],"30":[-16.482147084975267,10.346288107245597]} | {"20":[-20.86060031650382,10.929240903235337],"50":[-16.526771083428123,9.099103059145301]} | -11.617045 | -14.466657 | -20.383803 | 0.584615 | 0.333333 | 2 | 6 | -0.411000 | -0.006323 |
| ORIGINAL_CAUSAL_M020_RATE | DEV | 45 | 15 |  | 1253 | 0 | 271 | 1 | 982 | 469.368376 | 0.477972 | MEASURABLE |  | 2.455505 | -5.758414 | 6.649172 | 1758 | 475 | 0.729807 | 20000 | 999 | {"7":[-6.31483746195487,6.380499445283252],"14":[-6.1434707066170615,6.362382460891212],"30":[-5.623167424002755,6.429209841981932]} | {"20":[-5.191175655610412,6.338625650422666],"50":[-5.104617133277377,5.629112952362315]} | -0.285739 | -0.717937 | -1.891180 | 0.546843 | 0.518519 | 28 | 54 | 41.965200 | 0.042734 |
| ORIGINAL_CAUSAL_M020_RATE | HOLD_B | 45 | 15 |  | 83 | 0 | 9 | 1 | 74 | -742.615552 | -10.035345 | MEASURABLE |  | 6.293082 | -26.054804 | 6.735490 | 180 | 46 | 0.744444 | 20000 | 999 | {"7":[-25.90202112071077,6.244864416220345],"14":[-23.606365401111248,4.774302359079583],"30":[-21.06444778366967,4.779267996975953]} | {"20":[-25.814006450318843,8.872098691903389],"50":[-24.846207469004664,3.9779966904589568]} | -17.475681 | -19.434951 | -24.118614 | 0.554054 | 0.166667 | 1 | 6 | -0.411000 | -0.005554 |
| RESIDUAL_M010 | DEV | 45 | 15 |  | 11307 | 0 | 3508 | 1 | 7799 | -18699.300713 | -2.397654 | MEASURABLE |  | 3.743017 | -3.836807 | -0.966263 | 1758 | 1257 | 0.284983 | 20000 | 999 | {"7":[-3.764680575461531,-1.0204917279718149],"14":[-3.9910879323007205,-1.0187889787496625],"30":[-3.7656898344385166,-1.0488386533927156]} | {"20":[-4.053713458401797,-0.7956641689203958],"50":[-4.0287295222757145,-0.9564403037614309]} | -2.533712 | -2.630186 | -2.852136 | 0.538018 | 0.293103 | 17 | 58 | 441.318500 | 0.056587 |
| RESIDUAL_M010 | HOLD_B | 45 | 15 |  | 726 | 0 | 154 | 1 | 572 | -1664.544400 | -2.910043 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 127 | 0.294444 | 0 | 999 | {"7":[-8.443169925951901,2.578444099148898],"14":[-7.568667335779844,2.590973855280838],"30":[-6.955508427837846,1.4813681282519742]} | {"20":[-7.26114078926952,1.7727260376091714],"50":[-7.028835146312797,1.3828571656468158]} | -3.279775 | -3.613340 | -4.550851 | 0.543706 | 0.500000 | 3 | 6 | 2.044800 | 0.003575 |
| RESIDUAL_M020 | DEV | 45 | 15 |  | 3985 | 0 | 1001 | 1 | 2984 | 2529.362858 | 0.847642 | MEASURABLE |  | 1.263227 | -1.857918 | 3.577270 | 1758 | 877 | 0.501138 | 20000 | 999 | {"7":[-2.098038495431516,3.734752552194796],"14":[-2.208345908067285,3.77245068896029],"30":[-2.3562233266769788,3.896593688937693]} | {"20":[-2.3323398664315906,3.9941902951845094],"50":[-2.0715749243277406,4.052818410115932]} | 0.493054 | 0.241819 | -0.398195 | 0.546247 | 0.500000 | 29 | 58 | 252.612000 | 0.084655 |
| RESIDUAL_M020 | HOLD_B | 45 | 15 |  | 80 | 0 | 5 | 1 | 75 | 277.526224 | 3.700350 | MEASURABLE |  | 32.853414 | -5.183414 | 12.383349 | 180 | 35 | 0.805556 | 20000 | 999 | {"7":[-8.490139011653536,15.416735988890569],"14":[-7.784871990376899,13.928894739913122],"30":[-5.337110265027088,12.4534441555118]} | {"20":[-7.5308143648566945,15.40557084669453],"50":[-4.5801303479382165,11.648944994354611]} | -3.453824 | -5.801252 | -11.154641 | 0.573333 | 0.500000 | 3 | 6 | 0.711800 | 0.009491 |
| RESIDUAL_CAUSAL_M020_RATE | DEV | 45 | 15 |  | 1619 | 0 | 318 | 1 | 1301 | 3772.794511 | 2.899919 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 595 | 0.661547 | 0 | 999 | {"7":[-1.409021615250853,6.899901309941729],"14":[-1.169557558903814,6.821113506821754],"30":[-1.0770085969224135,6.664355545642678]} | {"20":[-1.01609112783578,7.177481485935477],"50":[-0.809620096817274,6.626297286858275]} | 2.325474 | 1.784670 | 0.704790 | 0.555726 | 0.555556 | 30 | 54 | 86.594100 | 0.066560 |
| RESIDUAL_CAUSAL_M020_RATE | HOLD_B | 45 | 15 |  | 89 | 0 | 8 | 1 | 81 | 196.937152 | 2.431323 | MEASURABLE |  | 28.000101 | -7.379439 | 12.258060 | 180 | 37 | 0.794444 | 20000 | 999 | {"7":[-9.322393854525734,12.880498639944278],"14":[-8.280325032125122,12.874392770950973],"30":[-6.545054089693137,12.374506092471533]} | {"20":[-9.608865567192119,14.192954583720299],"50":[-5.893417434638273,11.407343758185268]} | -4.202150 | -6.380766 | -11.334394 | 0.567901 | 0.500000 | 3 | 6 | 0.690800 | 0.008528 |
| R2_1_PSTAR | DEV | 45 | 15 |  | 12287 | 0 | 4348 | 1 | 7939 | -26610.443285 | -3.351863 | MEASURABLE |  | 2.143618 | -5.022151 | -1.589076 | 1758 | 1251 | 0.288396 | 20000 | 999 | {"7":[-5.02136732502203,-1.4798655897833466],"14":[-5.175534026195529,-1.4173127657038758],"30":[-5.221920998688287,-1.422694620540971]} | {"20":[-4.95392793599048,-1.6623414278604633],"50":[-5.213758755854621,-1.615337378236015]} | -3.485642 | -3.574884 | -3.800341 | 0.533946 | 0.344828 | 20 | 58 | 467.331700 | 0.058865 |
| R2_1_PSTAR | HOLD_B | 45 | 15 |  | 997 | 0 | 329 | 1 | 668 | -55.349644 | -0.082859 | MEASURABLE |  | 2.740148 | -4.907588 | 4.523364 | 180 | 136 | 0.244444 | 20000 | 999 | {"7":[-4.443315488965822,3.845783791369341],"14":[-4.145784300695598,3.6075692038519818],"30":[-3.90654048698925,3.5552791411387865]} | {"20":[-4.9129917847677325,4.6269689096450595],"50":[-4.412737464834666,3.974143711137702]} | -0.623364 | -0.979445 | -1.952959 | 0.532934 | 0.333333 | 2 | 6 | 4.591100 | 0.006873 |
| ORIGINAL_M010 | DEV | 45 | 60 |  | 10226 | 12 | 4296 | 1 | 5918 | -17929.424638 | -3.029643 | MEASURABLE |  | 2.065123 | -5.168879 | -0.848557 | 1758 | 1231 | 0.299772 | 20000 | 999 | {"7":[-5.189948258100166,-0.5654696394171066],"14":[-5.511643187975434,-0.7201803107351066],"30":[-5.567531822443483,-0.614409968632573]} | {"20":[-5.172576818265798,-0.7664073500707169],"50":[-5.362407969475895,-0.8778202211435078]} | -3.165049 | -3.284723 | -3.573883 | 0.534133 | 0.344828 | 20 | 58 | 201.938500 | 0.034123 |
| ORIGINAL_M010 | HOLD_B | 45 | 60 |  | 767 | 0 | 256 | 1 | 511 | -2970.218626 | -5.812561 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 134 | 0.255556 | 0 | 999 | {"7":[-12.647582052453881,2.7897700473412206],"14":[-12.25435934757947,2.6342325976720398],"30":[-12.274063640072477,2.225631548296003]} | {"20":[-11.935795849072598,1.4412666000992758],"50":[-12.388329971705112,1.8497842891236864]} | -6.530691 | -7.008211 | -8.235149 | 0.528376 | 0.333333 | 2 | 6 | 4.059500 | 0.007944 |
| ORIGINAL_M020 | DEV | 45 | 60 |  | 2967 | 4 | 854 | 1 | 2109 | 154.846464 | 0.073422 | MEASURABLE |  | 1.662089 | -4.589309 | 4.693204 | 1758 | 763 | 0.565984 | 20000 | 999 | {"7":[-4.729319816099382,4.4613347265588255],"14":[-4.830500674817218,5.087388348984087],"30":[-5.289855448513184,4.980861116629258]} | {"20":[-4.722325991639359,4.712594305009552],"50":[-5.028309946542546,4.904268182822249]} | -0.428717 | -0.807737 | -1.584910 | 0.545756 | 0.465517 | 27 | 58 | 116.120200 | 0.055059 |
| ORIGINAL_M020 | HOLD_B | 45 | 60 |  | 72 | 0 | 7 | 1 | 65 | -292.204152 | -4.495448 | MEASURABLE |  | 3.482461 | -25.884256 | 16.773797 | 180 | 43 | 0.761111 | 20000 | 999 | {"7":[-24.63235125964122,15.73980440553225],"14":[-22.010450293166485,12.431844669495888],"30":[-18.771660839063905,11.07056636791409]} | {"20":[-19.954071768695435,10.146281515138185],"50":[-17.064503779998475,8.04322325724429]} | -12.895521 | -15.765425 | -23.909730 | 0.538462 | 0.666667 | 4 | 6 | 0.058800 | 0.000905 |
| ORIGINAL_CAUSAL_M020_RATE | DEV | 45 | 60 |  | 1253 | 3 | 306 | 1 | 944 | 1378.057418 | 1.459807 | MEASURABLE |  | 2.933407 | -5.675479 | 8.417637 | 1758 | 474 | 0.730375 | 20000 | 999 | {"7":[-5.865694359933797,8.383880475275525],"14":[-6.092314458694176,8.508443819778948],"30":[-5.804057130794131,8.342489417709686]} | {"20":[-5.184000746221173,7.972300299451294],"50":[-5.0370369563027735,7.384137290775448]} | 0.666362 | 0.089517 | -1.315646 | 0.536017 | 0.500000 | 27 | 54 | 6.099300 | 0.006461 |
| ORIGINAL_CAUSAL_M020_RATE | HOLD_B | 45 | 60 |  | 83 | 0 | 9 | 1 | 74 | -1004.003080 | -13.567609 | MEASURABLE |  | 4.281112 | -31.999239 | 5.673281 | 180 | 46 | 0.744444 | 20000 | 999 | {"7":[-30.971527788025448,4.7160888359600595],"14":[-29.519604605479305,2.9151278963940985],"30":[-27.193530268125148,2.7363721640301133]} | {"20":[-30.427477132184116,6.475697093868002],"50":[-29.281679806131216,1.6681643480626214]} | -21.056332 | -23.621801 | -30.464724 | 0.500000 | 0.333333 | 2 | 6 | 0.257400 | 0.003478 |
| RESIDUAL_M010 | DEV | 45 | 60 |  | 11307 | 9 | 4959 | 1 | 6339 | -10202.107198 | -1.609419 | MEASURABLE |  | 1.027223 | -3.600768 | 0.342545 | 1758 | 1256 | 0.285552 | 20000 | 999 | {"7":[-3.6234557029068224,0.30048496607035124],"14":[-3.850683611727174,0.5265039687563242],"30":[-3.799108862961744,0.3207953438493567]} | {"20":[-3.7425063837514783,0.3940254965767356],"50":[-3.9131631182747766,0.18366774144681397]} | -1.776694 | -1.895277 | -2.181802 | 0.536678 | 0.431034 | 25 | 58 | 229.770400 | 0.036247 |
| RESIDUAL_M010 | HOLD_B | 45 | 60 |  | 726 | 0 | 244 | 1 | 482 | -3778.275270 | -7.838745 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 127 | 0.294444 | 0 | 999 | {"7":[-14.41640009174602,-0.49653550556968007],"14":[-14.033730401579126,-0.02572470257852011],"30":[-13.898560941678145,-0.8116081595247575]} | {"20":[-13.614787046577387,-1.624869360226871],"50":[-13.147381294859713,-1.6517190370714498]} | -8.243508 | -8.629104 | -9.758524 | 0.524896 | 0.000000 | 0 | 6 | 1.808000 | 0.003751 |
| RESIDUAL_M020 | DEV | 45 | 60 |  | 3985 | 3 | 1245 | 1 | 2737 | 3848.596227 | 1.406137 | MEASURABLE |  | 2.786495 | -1.919842 | 4.632272 | 1758 | 877 | 0.501138 | 20000 | 999 | {"7":[-2.16650599996653,4.641673038213696],"14":[-2.3236994433217486,4.784508309151845],"30":[-2.3396756979906934,5.333249365587492]} | {"20":[-2.0322658328901744,4.916575816309178],"50":[-2.6038588500869704,5.308499006083958]} | 1.019742 | 0.746010 | 0.046534 | 0.544757 | 0.534483 | 31 | 58 | 185.289200 | 0.067698 |
| RESIDUAL_M020 | HOLD_B | 45 | 60 |  | 80 | 0 | 12 | 1 | 68 | -73.093701 | -1.074907 | MEASURABLE |  | 28.487338 | -9.494746 | 7.469913 | 180 | 35 | 0.805556 | 20000 | 999 | {"7":[-13.110265506948874,10.523877389793311],"14":[-11.033234826802587,8.917189663010074],"30":[-9.09978075297963,7.402557497153264]} | {"20":[-11.471233269153531,9.173852090433881],"50":[-9.252359212926367,6.341995825237285]} | -9.047804 | -12.398599 | -20.507161 | 0.500000 | 0.500000 | 3 | 6 | 1.237100 | 0.018193 |
| RESIDUAL_CAUSAL_M020_RATE | DEV | 45 | 60 |  | 1619 | 2 | 366 | 1 | 1251 | 4549.238377 | 3.636482 | MEASURABLE |  | 1.946178 | -1.070520 | 8.240062 | 1758 | 595 | 0.661547 | 20000 | 999 | {"7":[-1.4526579103088029,8.389238878684681],"14":[-1.5889466237898429,8.945525799061276],"30":[-1.3904235358240458,8.811888640437635]} | {"20":[-1.3357012649342561,8.46214714219299],"50":[-1.113425695696301,9.293866119298407]} | 3.039648 | 2.477766 | 1.351503 | 0.552358 | 0.611111 | 33 | 54 | 57.223800 | 0.045742 |
| RESIDUAL_CAUSAL_M020_RATE | HOLD_B | 45 | 60 |  | 89 | 0 | 15 | 1 | 74 | -153.682773 | -2.076794 | MEASURABLE |  | 23.997044 | -11.263237 | 7.539055 | 180 | 37 | 0.794444 | 20000 | 999 | {"7":[-13.744003482434852,9.046606546387526],"14":[-11.672786681503382,8.586261669600773],"30":[-10.445924799196298,7.363334843413765]} | {"20":[-12.525058161550504,8.323320667758338],"50":[-10.251039850664018,5.830782826832888]} | -9.408109 | -12.484675 | -19.891887 | 0.500000 | 0.500000 | 3 | 6 | 1.216100 | 0.016434 |
| R2_1_PSTAR | DEV | 45 | 60 |  | 14210 | 15 | 6956 | 1 | 7239 | -26792.187602 | -3.701090 | MEASURABLE |  | 2.647533 | -5.765929 | -1.653413 | 1758 | 1293 | 0.264505 | 20000 | 999 | {"7":[-5.880679229382459,-1.4520585172296832],"14":[-5.891585352134266,-1.5644916533205908],"30":[-5.909077104145817,-1.7513180153516448]} | {"20":[-5.775787760915559,-1.7623785110500614],"50":[-5.687735955953285,-1.6686245971377844]} | -3.811876 | -3.909795 | -4.137622 | 0.530184 | 0.224138 | 13 | 58 | 105.356600 | 0.014554 |
| R2_1_PSTAR | HOLD_B | 45 | 60 |  | 1201 | 1 | 526 | 1 | 674 | -994.331258 | -1.475269 | MEASURABLE |  | 2.164857 | -6.352770 | 3.333989 | 180 | 139 | 0.227778 | 20000 | 999 | {"7":[-5.579894484226116,2.3165985879269417],"14":[-5.2861414034169485,2.0307754455517637],"30":[-4.731743333238122,1.5981476748038557]} | {"20":[-6.512940959346983,3.033945146840315],"50":[-5.563679648896609,2.559509443425476]} | -2.448216 | -3.245176 | -4.626975 | 0.532641 | 0.166667 | 1 | 6 | 6.626900 | 0.009832 |
| ORIGINAL_M010 | DEV | 120 | 5 |  | 10226 | 102 | 5167 | 1 | 4957 | -11055.986598 | -2.230379 | MEASURABLE |  | 1.730999 | -4.761399 | 0.335942 | 1758 | 1225 | 0.303185 | 20000 | 999 | {"7":[-4.601492444708021,0.06314936125073745],"14":[-4.663326901911156,0.10603971196981643],"30":[-4.500245677831009,-0.108383058497584]} | {"20":[-4.777290649575518,0.3335250309692981],"50":[-4.666162483230511,0.02629987292606817]} | -2.393320 | -2.529714 | -2.903450 | 0.546298 | 0.379310 | 22 | 58 | 799.187400 | 0.161224 |
| ORIGINAL_M010 | HOLD_B | 120 | 5 |  | 767 | 5 | 314 | 1 | 448 | -1000.239985 | -2.232679 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 134 | 0.255556 | 0 | 999 | {"7":[-9.72378639618902,4.476606876662056],"14":[-8.859719676242955,3.713504974020923],"30":[-7.891915154101751,3.2552709833445297]} | {"20":[-9.70090479154543,4.318044827870293],"50":[-8.369340328793882,4.279642023334058]} | -3.189582 | -4.013129 | -5.665147 | 0.513393 | 0.166667 | 1 | 6 | 8.643000 | 0.019292 |
| ORIGINAL_M020 | DEV | 120 | 5 |  | 2967 | 38 | 1228 | 1 | 1701 | -1248.412479 | -0.733929 | MEASURABLE |  | 2.965153 | -5.862877 | 4.432542 | 1758 | 758 | 0.568828 | 20000 | 999 | {"7":[-6.011727268702385,4.199054189843309],"14":[-5.4834023183774185,4.0345054853207785],"30":[-4.8680700166241095,3.715848646893692]} | {"20":[-5.2121188146032775,4.016628504673388],"50":[-4.953994138368024,3.191362510067904]} | -1.208071 | -1.572374 | -2.532330 | 0.561434 | 0.448276 | 26 | 58 | 435.349300 | 0.255937 |
| ORIGINAL_M020 | HOLD_B | 120 | 5 |  | 72 | 0 | 10 | 1 | 62 | 82.777170 | 1.335116 | MEASURABLE |  | 3.635376 | -28.207941 | 27.820587 | 180 | 43 | 0.761111 | 20000 | 999 | {"7":[-25.260091238853615,25.613211133588077],"14":[-22.38306025388469,22.725728912061147],"30":[-19.032514147965657,20.966588577244725]} | {"20":[-17.41477458537858,19.494330015298132],"50":[-12.808052156851808,14.427410194456934]} | -10.153342 | -16.595640 | -27.654245 | 0.516129 | 0.500000 | 3 | 6 | 0.586600 | 0.009461 |
| ORIGINAL_CAUSAL_M020_RATE | DEV | 120 | 5 |  | 1253 | 11 | 438 | 1 | 804 | 2740.061347 | 3.408037 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 471 | 0.732082 | 0 | 999 | {"7":[-5.226052541526677,10.764226116010475],"14":[-4.451740858451368,10.79418360277646],"30":[-4.03138680960906,10.302689512328714]} | {"20":[-3.951059051448859,10.84909259969548],"50":[-3.1437895296948004,9.338699121553677]} | 2.525195 | 1.758089 | 0.131231 | 0.555970 | 0.518519 | 28 | 54 | 133.469200 | 0.166006 |
| ORIGINAL_CAUSAL_M020_RATE | HOLD_B | 120 | 5 |  | 83 | 0 | 13 | 1 | 70 | -837.656372 | -11.966520 | MEASURABLE |  | 7.942734 | -30.416872 | 6.187613 | 180 | 46 | 0.744444 | 20000 | 999 | {"7":[-31.084068822735148,4.65859583648229],"14":[-26.96406092543218,3.6809899089587326],"30":[-23.180268992710428,1.6412068006402283]} | {"20":[-25.120598049522602,-0.5869131145557169],"50":[-21.023956218116098,-3.1853022588410767]} | -22.315760 | -29.153793 | -37.420471 | 0.471429 | 0.166667 | 1 | 6 | 0.555900 | 0.007941 |
| RESIDUAL_M010 | DEV | 120 | 5 |  | 11307 | 123 | 5922 | 1 | 5262 | -5565.893753 | -1.057753 | MEASURABLE |  | 2.761692 | -3.417761 | 1.266621 | 1758 | 1251 | 0.288396 | 20000 | 999 | {"7":[-3.216501540342821,1.0442971942667636],"14":[-3.2976532814443766,1.1751101179466292],"30":[-3.320364490562894,0.921552291020064]} | {"20":[-3.460861767031309,1.3734197818970804],"50":[-3.320081234292968,1.3643622897560068]} | -1.211025 | -1.355397 | -1.734658 | 0.545040 | 0.413793 | 24 | 58 | 814.362100 | 0.154763 |
| RESIDUAL_M010 | HOLD_B | 120 | 5 |  | 726 | 5 | 290 | 1 | 431 | -197.311853 | -0.457800 | MEASURABLE |  | 1.837107 | -7.600179 | 6.874317 | 180 | 127 | 0.294444 | 20000 | 999 | {"7":[-7.112824423651924,6.2057121359615905],"14":[-6.510461198056079,6.069664868533046],"30":[-5.844608350583489,5.379062081090883]} | {"20":[-7.402858052708855,6.177680480139078],"50":[-6.901554453263804,5.683358657170538]} | -1.448407 | -2.029694 | -3.611391 | 0.526682 | 0.333333 | 2 | 6 | 10.793300 | 0.025042 |
| RESIDUAL_M020 | DEV | 120 | 5 |  | 3985 | 58 | 1663 | 1 | 2264 | 389.968856 | 0.172248 | MEASURABLE |  | 3.869349 | -3.678095 | 3.933783 | 1758 | 870 | 0.505119 | 20000 | 999 | {"7":[-3.640275040522287,4.002654398361565],"14":[-3.741731959194393,3.872663291295694],"30":[-3.4583272788034702,4.137010751547157]} | {"20":[-3.662751427889072,4.08646373727667],"50":[-3.988084771266806,3.932554986977245]} | -0.162712 | -0.491007 | -1.347242 | 0.568463 | 0.431034 | 25 | 58 | 490.369900 | 0.216594 |
| RESIDUAL_M020 | HOLD_B | 120 | 5 |  | 80 | 1 | 12 | 1 | 67 | 1272.045619 | 18.985756 | MEASURABLE |  | 5.401609 | -15.658282 | 46.101487 | 180 | 35 | 0.805556 | 20000 | 999 | {"7":[-15.393480629313828,45.70946293126482],"14":[-16.29429333943542,44.19385090912586],"30":[-8.929399429663455,45.7923582911324]} | {"20":[-9.732820812687223,47.382752399265385],"50":[-1.6724021689647834,41.06050952313234]} | 8.635069 | 2.746054 | -9.512246 | 0.597015 | 0.666667 | 4 | 6 | 0.131700 | 0.001966 |
| RESIDUAL_CAUSAL_M020_RATE | DEV | 120 | 5 |  | 1619 | 24 | 521 | 1 | 1074 | 985.403883 | 0.917508 | MEASURABLE |  | 3.413863 | -4.724642 | 6.338804 | 1758 | 590 | 0.664391 | 20000 | 999 | {"7":[-4.454926346730451,6.102979952347093],"14":[-4.545175305264381,5.631989612014948],"30":[-4.2431316105563965,6.322275853396219]} | {"20":[-4.766393795526031,6.808422684562345],"50":[-4.291959361342559,6.5468723446167525]} | 0.342646 | -0.075785 | -1.251525 | 0.560521 | 0.462963 | 25 | 54 | 218.079800 | 0.203054 |
| RESIDUAL_CAUSAL_M020_RATE | HOLD_B | 120 | 5 |  | 89 | 1 | 17 | 1 | 71 | 1081.392745 | 15.230884 | MEASURABLE |  | 7.096317 | -16.108990 | 41.304789 | 180 | 37 | 0.794444 | 20000 | 999 | {"7":[-16.53167213181056,41.27199113801764],"14":[-16.883020947399842,39.88195744924139],"30":[-10.871249846284206,40.15875324322711]} | {"20":[-10.378234796549917,40.21668543528732],"50":[-6.330014550303327,36.043615259109075]} | 5.418024 | -0.176223 | -11.824426 | 0.591549 | 0.666667 | 4 | 6 | 0.312300 | 0.004399 |
| R2_1_PSTAR | DEV | 120 | 5 |  | 11215 | 94 | 6414 | 1 | 4707 | -11636.084256 | -2.472081 | MEASURABLE |  | 2.799577 | -5.181972 | 0.196964 | 1758 | 1246 | 0.291240 | 20000 | 999 | {"7":[-5.014252734306201,0.1493508294712238],"14":[-5.141812857812454,0.12245454563381886],"30":[-5.1220216375419465,0.01931483822432245]} | {"20":[-5.200830703248747,0.35307965255725415],"50":[-5.098455778383645,0.021336113038731508]} | -2.655722 | -2.817505 | -3.255288 | 0.540684 | 0.362069 | 21 | 58 | 800.365000 | 0.170037 |
| R2_1_PSTAR | HOLD_B | 120 | 5 |  | 904 | 6 | 545 | 1 | 353 | 1052.750503 | 2.982296 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 126 | 0.300000 | 0 | 999 | {"7":[-7.202701222541755,12.350674964833962],"14":[-6.178231264613366,12.441869172297594],"30":[-4.386860297632063,10.992912379432674]} | {"20":[-6.801958370305066,12.98109057260406],"50":[-5.471147113872858,11.920425919895305]} | 1.517095 | 0.327069 | -2.103838 | 0.541076 | 0.666667 | 4 | 6 | 7.414700 | 0.021005 |
| ORIGINAL_M010 | DEV | 120 | 15 |  | 10226 | 102 | 5167 | 1 | 4957 | -13776.428430 | -2.779187 | MEASURABLE |  | 1.538188 | -5.473547 | -0.076578 | 1758 | 1225 | 0.303185 | 20000 | 999 | {"7":[-5.131047411917176,-0.25718874311470774],"14":[-5.31637151280087,-0.1758288596978872],"30":[-5.1335022703667486,-0.5070779366456408]} | {"20":[-5.516748155575117,-0.13166391769388186],"50":[-5.3052483720781325,-0.38970289732430086]} | -2.942239 | -3.078743 | -3.452812 | 0.542062 | 0.379310 | 22 | 58 | 773.600300 | 0.156062 |
| ORIGINAL_M010 | HOLD_B | 120 | 15 |  | 767 | 5 | 314 | 1 | 448 | -392.094813 | -0.875212 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 134 | 0.255556 | 0 | 999 | {"7":[-7.962843442717397,5.278981448686842],"14":[-6.709010486425416,3.9882810955114683],"30":[-5.926044887534113,3.424945860954668]} | {"20":[-7.750254578217366,5.220576378838201],"50":[-6.725174111624788,4.915381946930936]} | -1.829078 | -2.649575 | -4.292359 | 0.526786 | 0.333333 | 2 | 6 | 8.695600 | 0.019410 |
| ORIGINAL_M020 | DEV | 120 | 15 |  | 2967 | 38 | 1228 | 1 | 1701 | -2371.467071 | -1.394161 | MEASURABLE |  | 2.553836 | -6.769246 | 4.026245 | 1758 | 758 | 0.568828 | 20000 | 999 | {"7":[-6.8124157175211995,3.6371044947586513],"14":[-6.224526545909326,3.63115224082441],"30":[-6.149107149346593,3.247663365075907]} | {"20":[-6.245994280367164,3.509148324377763],"50":[-5.81924345862528,2.8937446936057145]} | -1.868691 | -2.233384 | -3.194509 | 0.561434 | 0.517241 | 30 | 58 | 426.535700 | 0.250756 |
| ORIGINAL_M020 | HOLD_B | 120 | 15 |  | 72 | 0 | 10 | 1 | 62 | 113.130752 | 1.824690 | MEASURABLE |  | 3.742483 | -27.856693 | 27.937505 | 180 | 43 | 0.761111 | 20000 | 999 | {"7":[-25.078317759120985,26.12335623086294],"14":[-21.834812039924543,23.307612945556663],"30":[-18.45261196198885,21.367514491789372]} | {"20":[-17.5178639146177,20.21753873878093],"50":[-12.139180473216783,14.84505459761513]} | -9.655742 | -16.089747 | -27.121726 | 0.548387 | 0.500000 | 3 | 6 | 0.586600 | 0.009461 |
| ORIGINAL_CAUSAL_M020_RATE | DEV | 120 | 15 |  | 1253 | 11 | 438 | 1 | 804 | 2297.819431 | 2.857984 | MEASURABLE |  | 1.057843 | -5.676776 | 11.623273 | 1758 | 471 | 0.732082 | 20000 | 999 | {"7":[-6.286725171472412,10.81323601718956],"14":[-5.4616354939355425,11.168223346642728],"30":[-5.3341481167296525,10.785040730273053]} | {"20":[-4.553254045843418,10.45971268741435],"50":[-4.345146028994985,9.26006656692488]} | 1.974458 | 1.206665 | -0.452831 | 0.564677 | 0.555556 | 30 | 54 | 126.655600 | 0.157532 |

## k45_gate_direction_r2_9_20261001

- 테스트 재실행 `tests/test_k45_gate_direction_r2_9.py`: `4 passed in 1.88s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-01T11:34:31.384590+00:00 |
| run_finished_utc | 2026-10-01T11:46:44.110935+00:00 |
| runtime_seconds | 732.7224880000576 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | DEV 자동 선정 PRIMARY의 HOLD_B 단일 포지션 net_mean_bps > 0 |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| primary_selection | {"rule": "maximum DEV single-position net_mean_bps", "cell_count": 504, "cell_id": "AGREE/EXPANDING_OOS/q=0.01/L=120/S=60", "bonferroni_cells": 504, "dev_pw_p_one_sided": 0.034098295085245735, "dev_pw_p_bonferroni": 1.0, "dev_pw_ci95_lower": -5.4215039859002445, "dev_pw_ci95_upper": 133.09270239179028, "pw_bootstrap_reps": 20000, "pw_status": "MEASURABLE"} |
| thresholds | {"methods": ["EXPANDING_OOS", "ROLLING_180D"], "q": [0.01, 0.02], "minimum_history": 2000, "rolling_days": 180, "existing_scores": "R2-7 thresholds.parquet exact rows", "new_scores": "R2-7 causal_thresholds definition"} |
| book | single position; first come; occupied signals dropped |
| max_positions | 1 |
| same_bar | one direction; competing SIDE/RESIDUAL margins choose larger; ties abstain |
| baseline | same admitted entry bars and same realized hold; opposite, random +/-1 x1000, always long |
| entry_exit | close[t] / close[t+h] |
| cost_bps | 4.0 |
| funding_interval | entry_time < funding_time <= exit_time |
| funding_cost_bps | side * sum(actual funding rate) * 10000 |
| seed | 20261001 |
| random_repetitions | 1000 |
| pw_bootstrap_reps | 20000 |
| fixed_bootstrap_reps | 999 |
| fixed_daily_blocks | [7, 14, 30] |
| fixed_event_blocks | [20, 50] |
| local_data_only | True |
| downloads | 0 |
| model_fits | 0 |
| live_orders | 0 |
| r2_10b_manifest_finished_utc | 2026-10-01T11:19:53.169840+00:00 |

### out_of_sample_result (원문)

```text
{
 "hold_b_exploratory": true,
 "primary_hold_b_net_mean_bps": 315.1690446055081,
 "hypothesis_hold_b_net_gt_zero": true
}
```

- 출력 해시 확인: 17/17 일치

### REPORT.md 앞 149줄 (전체 149줄, 원문)

# R2-9

- run_started_utc: `2026-10-01T11:34:31.384590+00:00`
- run_finished_utc: `2026-10-01T11:46:44.110935+00:00`
- cutoff_utc: `2026-06-30T23:59:00+00:00`
- model_fits: `0`
- downloads: `0`
- live_orders: `0`
- cost_bps: `4`
- seed: `20261001`
- primary_cell_count: `504`
- hold_b_exploratory: `1`

## PRIMARY_SELECTION_TOP20

| rank | cell_id | combination | method | q | h_long | h_short | segment | candidate_n | invalid_exit_n | dropped_n | max_concurrent | n | long_n | short_n | long_net_mean_bps | long_net_sum_bps | short_net_mean_bps | short_net_sum_bps | net_mean_bps | net_sum_bps | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps | funding_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_block7_ci95_lower | daily_block7_ci95_upper | daily_block14_ci95_lower | daily_block14_ci95_upper | daily_block30_ci95_lower | daily_block30_ci95_upper | event_block20_ci95_lower | event_block20_ci95_upper | event_block50_ci95_lower | event_block50_ci95_upper | is_primary | bonferroni_cells |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 60 | DEV | 31 | 0 | 7 | 1 | 24 | 16 | 8 | 85.703966 | 1371.263454 | 33.376289 | 267.010311 | 68.261407 | 1638.273765 | 52.249831 | 38.827948 | 8.146456 | 0.708333 | 0.812500 | 13 | 16 | -3.707800 | -0.154492 | MEASURABLE |  | 2.211805 | -5.421504 | 133.092702 | 1758 | 21 | 0.988055 | 20000 | 999 | -0.073871 | 140.041317 | -3.111256 | 133.534486 | -3.099855 | 132.720778 | 18.930145 | 125.126855 | 28.570037 | 109.591637 | True | 504 |
| 2 | AGREE|EXPANDING_OOS|q=0.01|L=45|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 45 | 60 | DEV | 31 | 0 | 4 | 1 | 27 | 19 | 8 | 74.069316 | 1407.317010 | 33.376289 | 267.010311 | 62.012123 | 1674.327321 | 53.392847 | 44.276472 | 20.537510 | 0.740741 | 0.687500 | 11 | 16 | -7.448400 | -0.275867 | MEASURABLE |  | 2.363228 | 4.021467 | 113.215905 | 1758 | 21 | 0.988055 | 20000 | 999 | 7.673535 | 115.354543 | 6.096402 | 112.112855 | 8.473731 | 109.298877 | 33.051124 | 95.444255 | 36.961700 | 84.787346 | False | 504 |
| 3 | AGREE|EXPANDING_OOS|q=0.01|L=120|S=45 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 45 | DEV | 31 | 0 | 7 | 1 | 24 | 16 | 8 | 85.703966 | 1371.263454 | 14.571600 | 116.572799 | 61.993177 | 1487.836253 | 45.709069 | 31.989880 | 1.804586 | 0.666667 | 0.687500 | 11 | 16 | -2.707800 | -0.112825 | MEASURABLE |  | 2.378866 | -7.906992 | 122.700684 | 1758 | 21 | 0.988055 | 20000 | 999 | -3.644288 | 127.430923 | -1.792319 | 119.264982 | -5.702594 | 122.364231 | 14.051998 | 117.143798 | 23.417488 | 103.634157 | False | 504 |
| 4 | AGREE|EXPANDING_OOS|q=0.02|L=240|S=60 | AGREE | EXPANDING_OOS | 0.020000 | 240 | 60 | DEV | 108 | 5 | 48 | 1 | 55 | 33 | 22 | 79.330442 | 2617.904587 | 32.122578 | 706.696726 | 60.447297 | 3324.601312 | 44.554532 | 34.299233 | 9.123300 | 0.636364 | 0.655172 | 19 | 29 | -12.294400 | -0.223535 | MEASURABLE |  | 3.989694 | 0.811117 | 115.909974 | 1758 | 49 | 0.972127 | 20000 | 999 | 1.060787 | 116.262491 | 2.346264 | 110.130548 | 8.205128 | 108.467357 | 19.273040 | 97.693543 | 28.699071 | 90.651360 | False | 504 |
| 5 | AGREE|EXPANDING_OOS|q=0.02|L=120|S=60 | AGREE | EXPANDING_OOS | 0.020000 | 120 | 60 | DEV | 108 | 1 | 46 | 1 | 61 | 39 | 22 | 74.051334 | 2888.002016 | 32.122578 | 706.696726 | 58.929488 | 3594.698742 | 44.695455 | 38.821765 | 24.418782 | 0.721311 | 0.724138 | 21 | 29 | -12.213600 | -0.200223 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 51 | 0.970990 | 0 | 999 | 5.523687 | 106.777687 | 3.346838 | 103.177088 | 5.059225 | 104.896226 | 14.931544 | 98.620677 | 26.064816 | 93.681892 | False | 504 |
| 6 | AGREE|EXPANDING_OOS|q=0.01|L=45|S=45 | AGREE | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 31 | 0 | 4 | 1 | 27 | 19 | 8 | 74.069316 | 1407.317010 | 14.571600 | 116.572799 | 56.440363 | 1523.889809 | 47.606789 | 38.258972 | 14.101372 | 0.703704 | 0.687500 | 11 | 16 | -6.448400 | -0.238830 | MEASURABLE |  | 2.588718 | 1.417020 | 104.155856 | 1758 | 21 | 0.988055 | 20000 | 999 | 4.026995 | 107.027979 | 4.560815 | 101.567713 | 5.213629 | 98.950538 | 28.081255 | 87.853380 | 32.642919 | 78.531070 | False | 504 |
| 7 | AGREE|EXPANDING_OOS|q=0.01|L=120|S=15 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 15 | DEV | 31 | 0 | 7 | 1 | 24 | 16 | 8 | 85.703966 | 1371.263454 | -3.054657 | -24.437255 | 56.117758 | 1346.826199 | 39.578197 | 25.580332 | -5.616996 | 0.708333 | 0.750000 | 12 | 16 | 1.160500 | 0.048354 | MEASURABLE |  | 2.494716 | -11.976047 | 114.115207 | 1758 | 21 | 0.988055 | 20000 | 999 | -11.199734 | 121.677826 | -7.856371 | 114.162878 | -10.311353 | 114.500033 | 4.930590 | 111.123500 | 16.091686 | 100.231117 | False | 504 |
| 8 | SIDE|EXPANDING_OOS|q=0.01|L=60|S=90 | SIDE | EXPANDING_OOS | 0.010000 | 60 | 90 | DEV | 53 | 0 | 9 | 1 | 44 | 38 | 6 | 60.816486 | 2311.026454 | 23.037037 | 138.222223 | 55.664743 | 2449.248677 | 42.890428 | 34.515523 | 12.056471 | 0.681818 | 0.681818 | 15 | 22 | 6.060700 | 0.137743 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 35 | 0.980091 | 0 | 999 | 4.199500 | 97.813835 | -0.766712 | 98.679008 | 1.328295 | 98.762575 | 14.740068 | 92.602814 | 22.529956 | 89.285291 | False | 504 |
| 9 | AGREE|EXPANDING_OOS|q=0.02|L=240|S=45 | AGREE | EXPANDING_OOS | 0.020000 | 240 | 45 | DEV | 108 | 5 | 48 | 1 | 55 | 33 | 22 | 79.330442 | 2617.904587 | 10.343549 | 227.558087 | 51.735685 | 2845.462673 | 35.681594 | 25.258881 | -0.459473 | 0.581818 | 0.517241 | 15 | 29 | -11.294400 | -0.205353 | MEASURABLE |  | 4.192922 | -7.080469 | 105.910474 | 1758 | 49 | 0.972127 | 20000 | 999 | -3.567950 | 107.414914 | -2.649872 | 99.768323 | -0.291114 | 97.099122 | 13.022695 | 88.134995 | 22.685565 | 81.258147 | False | 504 |
| 10 | AGREE|EXPANDING_OOS|q=0.01|L=45|S=15 | AGREE | EXPANDING_OOS | 0.010000 | 45 | 15 | DEV | 31 | 0 | 4 | 1 | 27 | 19 | 8 | 74.069316 | 1407.317010 | -3.054657 | -24.437255 | 51.217769 | 1382.879755 | 42.183325 | 32.618569 | 7.691824 | 0.740741 | 0.687500 | 11 | 16 | -2.580100 | -0.095559 | MEASURABLE |  | 2.750412 | -1.286315 | 96.452404 | 1758 | 21 | 0.988055 | 20000 | 999 | -2.669843 | 99.598802 | 0.730640 | 93.868780 | 0.347543 | 90.826070 | 20.213850 | 82.250403 | 24.757455 | 75.318890 | False | 504 |
| 11 | AGREE|EXPANDING_OOS|q=0.02|L=120|S=45 | AGREE | EXPANDING_OOS | 0.020000 | 120 | 45 | DEV | 108 | 1 | 46 | 1 | 61 | 39 | 22 | 74.051334 | 2888.002016 | 10.343549 | 227.558087 | 51.074756 | 3115.560102 | 36.709811 | 30.700771 | 15.862735 | 0.672131 | 0.586207 | 17 | 29 | -11.213600 | -0.183830 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 51 | 0.970990 | 0 | 999 | 0.034446 | 97.193956 | -3.085973 | 94.014763 | -2.568949 | 94.346687 | 8.620300 | 89.446903 | 18.350977 | 84.337804 | False | 504 |
| 12 | SIDE|EXPANDING_OOS|q=0.01|L=60|S=60 | SIDE | EXPANDING_OOS | 0.010000 | 60 | 60 | DEV | 83 | 0 | 8 | 1 | 75 | 39 | 36 | 59.400561 | 2316.621890 | 34.103895 | 1227.740211 | 47.258161 | 3544.362101 | 39.721647 | 32.812981 | 17.700196 | 0.680000 | 0.703704 | 19 | 27 | -7.954900 | -0.106065 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 59 | 0.966439 | 0 | 999 | 7.734799 | 80.962996 | 6.370919 | 82.013726 | 9.983511 | 78.272014 | 18.803787 | 73.845245 | 24.277809 | 69.261392 | False | 504 |
| 13 | SIDE|EXPANDING_OOS|q=0.01|L=60|S=120 | SIDE | EXPANDING_OOS | 0.010000 | 60 | 120 | DEV | 54 | 0 | 8 | 1 | 46 | 37 | 9 | 62.641365 | 2317.730508 | -23.997347 | -215.976126 | 45.690313 | 2101.754382 | 33.262092 | 25.049038 | 2.992880 | 0.673913 | 0.619048 | 13 | 21 | 2.835200 | 0.061635 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 36 | 0.979522 | 0 | 999 | -2.296162 | 85.397186 | -8.683761 | 86.311448 | -8.749491 | 87.053635 | -3.361815 | 91.108898 | 11.216003 | 81.338737 | False | 504 |
| 14 | AGREE|EXPANDING_OOS|q=0.02|L=45|S=60 | AGREE | EXPANDING_OOS | 0.020000 | 45 | 60 | DEV | 108 | 0 | 35 | 1 | 73 | 51 | 22 | 49.976482 | 2548.800603 | 32.122578 | 706.696726 | 44.595854 | 3255.497329 | 35.425938 | 31.755747 | 22.213223 | 0.712329 | 0.733333 | 22 | 30 | -16.543000 | -0.226616 | MEASURABLE |  | 2.184075 | 13.363464 | 73.290681 | 1758 | 52 | 0.970421 | 20000 | 999 | 13.363678 | 75.286615 | 13.799821 | 73.407767 | 13.826768 | 74.811033 | 22.766821 | 63.711271 | 28.403874 | 60.264950 | False | 504 |
| 15 | REG|EXPANDING_OOS|q=0.02|L=240|S=15 | REG | EXPANDING_OOS | 0.020000 | 240 | 15 | DEV | 219 | 5 | 82 | 1 | 132 | 55 | 77 | 100.093416 | 5505.137907 | 1.655280 | 127.456584 | 42.671170 | 5632.594492 | 35.984259 | 31.737327 | 21.129521 | 0.568182 | 0.641026 | 25 | 39 | 5.655400 | 0.042844 | MEASURABLE |  | 2.776564 | 3.881123 | 78.945272 | 1758 | 101 | 0.942548 | 20000 | 999 | 4.782239 | 78.554963 | 5.632616 | 76.113403 | 4.939151 | 76.450112 | 14.270909 | 72.581861 | 20.136983 | 66.150802 | False | 504 |
| 16 | SIDE|EXPANDING_OOS|q=0.01|L=60|S=5 | SIDE | EXPANDING_OOS | 0.010000 | 60 | 5 | DEV | 62 | 0 | 7 | 1 | 55 | 39 | 16 | 59.400561 | 2316.621890 | 1.290815 | 20.653047 | 42.495908 | 2337.274936 | 32.079902 | 25.239212 | 5.087141 | 0.654545 | 0.680000 | 17 | 25 | 6.060700 | 0.110195 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 43 | 0.975540 | 0 | 999 | -1.026949 | 79.866024 | -6.956293 | 79.070525 | -1.990184 | 80.806528 | 4.359837 | 79.005591 | 9.573470 | 74.221572 | False | 504 |
| 17 | AGREE|EXPANDING_OOS|q=0.02|L=120|S=15 | AGREE | EXPANDING_OOS | 0.020000 | 120 | 15 | DEV | 108 | 1 | 43 | 1 | 64 | 39 | 25 | 74.051334 | 2888.002016 | -7.995415 | -199.885383 | 42.001822 | 2688.116633 | 28.176908 | 22.321001 | 7.811350 | 0.625000 | 0.620690 | 18 | 29 | -0.436300 | -0.006817 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 51 | 0.970990 | 0 | 999 | -5.308210 | 85.363268 | -7.586665 | 82.080350 | -9.224412 | 80.899816 | -0.656628 | 80.977794 | 8.468096 | 74.914937 | False | 504 |
| 18 | AGREE|EXPANDING_OOS|q=0.02|L=240|S=15 | AGREE | EXPANDING_OOS | 0.020000 | 240 | 15 | DEV | 108 | 5 | 45 | 1 | 58 | 33 | 25 | 79.330442 | 2617.904587 | -7.995415 | -199.885383 | 41.689986 | 2418.019204 | 26.304607 | 16.272808 | -8.498436 | 0.534483 | 0.586207 | 17 | 29 | -0.517100 | -0.008916 | MEASURABLE |  | 3.887578 | -12.232551 | 92.210625 | 1758 | 49 | 0.972127 | 20000 | 999 | -9.327341 | 91.799454 | -7.933913 | 86.973621 | -10.397516 | 85.409529 | 1.837545 | 75.882055 | 8.197769 | 74.147683 | False | 504 |
| 19 | REG|EXPANDING_OOS|q=0.02|L=240|S=60 | REG | EXPANDING_OOS | 0.020000 | 240 | 60 | DEV | 219 | 5 | 91 | 1 | 123 | 53 | 70 | 72.560655 | 3845.714702 | 15.598737 | 1091.911576 | 40.143303 | 4937.626278 | 32.942375 | 28.354416 | 15.499156 | 0.577236 | 0.538462 | 21 | 39 | -13.254200 | -0.107758 | MEASURABLE |  | 2.171703 | -0.918953 | 79.831780 | 1758 | 101 | 0.942548 | 20000 | 999 | -3.585224 | 79.601495 | 0.353188 | 78.413343 | 0.866643 | 79.715160 | 4.954635 | 71.191703 | 12.519193 | 68.376525 | False | 504 |
| 20 | REG|EXPANDING_OOS|q=0.02|L=240|S=45 | REG | EXPANDING_OOS | 0.020000 | 240 | 45 | DEV | 219 | 5 | 88 | 1 | 126 | 54 | 72 | 74.429354 | 4019.185119 | 12.837296 | 924.285332 | 39.233892 | 4943.470451 | 32.198511 | 26.259679 | 12.832488 | 0.563492 | 0.538462 | 21 | 39 | -5.654100 | -0.044874 | MEASURABLE |  | 2.107962 | -1.781451 | 78.036260 | 1758 | 101 | 0.942548 | 20000 | 999 | -1.905515 | 77.755950 | -1.338223 | 75.374241 | 0.619336 | 76.939063 | 8.451706 | 70.018756 | 15.533701 | 63.782978 | False | 504 |

## PRIMARY_DEV_HOLD_B

| cell_id | combination | method | q | h_long | h_short | segment | candidate_n | invalid_exit_n | dropped_n | max_concurrent | n | long_n | short_n | long_net_mean_bps | long_net_sum_bps | short_net_mean_bps | short_net_sum_bps | net_mean_bps | net_sum_bps | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps | funding_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_block7_ci95_lower | daily_block7_ci95_upper | daily_block14_ci95_lower | daily_block14_ci95_upper | daily_block30_ci95_lower | daily_block30_ci95_upper | event_block20_ci95_lower | event_block20_ci95_upper | event_block50_ci95_lower | event_block50_ci95_upper | is_primary | dev_pw_p_one_sided | dev_pw_p_bonferroni |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 60 | DEV | 31 | 0 | 7 | 1 | 24 | 16 | 8 | 85.703966 | 1371.263454 | 33.376289 | 267.010311 | 68.261407 | 1638.273765 | 52.249831 | 38.827948 | 8.146456 | 0.708333 | 0.812500 | 13 | 16 | -3.707800 | -0.154492 | MEASURABLE |  | 2.211805 | -5.421504 | 133.092702 | 1758 | 21 | 0.988055 | 20000 | 999 | -0.073871 | 140.041317 | -3.111256 | 133.534486 | -3.099855 | 132.720778 | 18.930145 | 125.126855 | 28.570037 | 109.591637 | True | 0.034098 | 1.000000 |
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 60 | HOLD_B | 3 | 0 | 0 | 1 | 3 | 2 | 1 | 146.094617 | 292.189234 | 653.317900 | 653.317900 | 315.169045 | 945.507134 | 146.094617 | -190.776665 | nan | 0.666667 | 1.000000 | 1 | 1 | 0.159700 | 0.053233 | MEASURABLE |  | 3.387947 | -315.169045 | 630.338089 | 180 | 2 | 0.988889 | 20000 | 999 | -315.169045 | 630.338089 | -315.169045 | 630.338089 | -315.169045 | 630.338089 | 258.385044 | 380.342887 | 315.169045 | 315.169045 | True | 0.034098 | 1.000000 |

## PRIMARY_PW_BONFERRONI

| cell_id | bonferroni_cells | dev_pw_p_one_sided | dev_pw_p_bonferroni | dev_pw_ci95_lower | dev_pw_ci95_upper | pw_bootstrap_reps | pw_status |
|---|---|---|---|---|---|---|---|
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | 504 | 0.034098 | 1.000000 | -5.421504 | 133.092702 | 20000 | MEASURABLE |

## H45_H45

| cell_id | combination | method | q | h_long | h_short | segment | candidate_n | invalid_exit_n | dropped_n | max_concurrent | n | long_n | short_n | long_net_mean_bps | long_net_sum_bps | short_net_mean_bps | short_net_sum_bps | net_mean_bps | net_sum_bps | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps | funding_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_block7_ci95_lower | daily_block7_ci95_upper | daily_block14_ci95_lower | daily_block14_ci95_upper | daily_block30_ci95_lower | daily_block30_ci95_upper | event_block20_ci95_lower | event_block20_ci95_upper | event_block50_ci95_lower | event_block50_ci95_upper | is_primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| REG|EXPANDING_OOS|q=0.01|L=45|S=45 | REG | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 90 | 0 | 13 | 1 | 77 | 34 | 43 | 60.343278 | 2051.671444 | 18.822028 | 809.347215 | 37.156086 | 2861.018659 | 27.531644 | 18.501001 | -0.272786 | 0.610390 | 0.566667 | 17 | 30 | -5.980600 | -0.077670 | MEASURABLE |  | 1.165708 | -16.312771 | 84.347671 | 1758 | 57 | 0.967577 | 20000 | 999 | -19.081903 | 86.965036 | -14.951200 | 82.255786 | -15.447614 | 81.469801 | 2.413593 | 70.907294 | 10.076828 | 66.006387 | False |
| REG|EXPANDING_OOS|q=0.01|L=45|S=45 | REG | EXPANDING_OOS | 0.010000 | 45 | 45 | HOLD_B | 10 | 0 | 5 | 1 | 5 | 2 | 3 | 18.054960 | 36.109920 | 48.423782 | 145.271345 | 36.276253 | 181.381265 | -17.642082 | -41.610349 | nan | 0.400000 | 1.000000 | 1 | 1 | 0.159700 | 0.031940 | MEASURABLE |  | 2.970336 | -36.276253 | 72.552506 | 180 | 2 | 0.988889 | 20000 | 999 | -36.276253 | 72.552506 | -36.276253 | 72.552506 | -36.276253 | 72.552506 | -17.372759 | 89.925265 | 21.793149 | 50.759357 | False |
| WGT|EXPANDING_OOS|q=0.01|L=45|S=45 | WGT | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 89 | 0 | 14 | 1 | 75 | 41 | 34 | 42.562425 | 1745.059419 | 10.708318 | 364.082821 | 28.121897 | 2109.142240 | 23.135083 | 19.532641 | 9.176913 | 0.586667 | 0.588235 | 20 | 34 | -16.365600 | -0.218208 | MEASURABLE |  | 8.902755 | -0.969580 | 52.977899 | 1758 | 57 | 0.967577 | 20000 | 999 | -2.097808 | 53.794686 | 1.179524 | 54.474082 | 1.757179 | 52.907876 | 7.664004 | 50.250817 | 10.484225 | 45.534117 | False |
| WGT|EXPANDING_OOS|q=0.01|L=45|S=45 | WGT | EXPANDING_OOS | 0.010000 | 45 | 45 | HOLD_B | 3 | 0 | 0 | 1 | 3 | 2 | 1 | 215.913957 | 431.827915 | 251.949591 | 251.949591 | 227.925835 | 683.777506 | 116.898395 | -18.152801 | nan | 0.666667 | 1.000000 | 1 | 1 | 0.159700 | 0.053233 | MEASURABLE |  | 3.132949 | -227.925835 | 455.851671 | 180 | 2 | 0.988889 | 20000 | 999 | -227.925835 | 455.851671 | -227.925835 | 455.851671 | -227.925835 | 455.851671 | 161.915461 | 295.137398 | 227.925835 | 227.925835 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=45|S=45 | AGREE | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 31 | 0 | 4 | 1 | 27 | 19 | 8 | 74.069316 | 1407.317010 | 14.571600 | 116.572799 | 56.440363 | 1523.889809 | 47.606789 | 38.258972 | 14.101372 | 0.703704 | 0.687500 | 11 | 16 | -6.448400 | -0.238830 | MEASURABLE |  | 2.588718 | 1.417020 | 104.155856 | 1758 | 21 | 0.988055 | 20000 | 999 | 4.026995 | 107.027979 | 4.560815 | 101.567713 | 5.213629 | 98.950538 | 28.081255 | 87.853380 | 32.642919 | 78.531070 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=45|S=45 | AGREE | EXPANDING_OOS | 0.010000 | 45 | 45 | HOLD_B | 3 | 0 | 0 | 1 | 3 | 2 | 1 | 215.913957 | 431.827915 | 251.949591 | 251.949591 | 227.925835 | 683.777506 | 116.898395 | -18.152801 | nan | 0.666667 | 1.000000 | 1 | 1 | 0.159700 | 0.053233 | MEASURABLE |  | 3.132949 | -227.925835 | 455.851671 | 180 | 2 | 0.988889 | 20000 | 999 | -227.925835 | 455.851671 | -227.925835 | 455.851671 | -227.925835 | 455.851671 | 161.915461 | 295.137398 | 227.925835 | 227.925835 | False |
| EITHER|EXPANDING_OOS|q=0.01|L=45|S=45 | EITHER | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 148 | 0 | 26 | 1 | 122 | 54 | 68 | 34.329473 | 1853.791528 | 18.258145 | 1241.553833 | 25.371683 | 3095.345361 | 19.229187 | 14.171896 | 4.464699 | 0.581967 | 0.552632 | 21 | 38 | -15.897800 | -0.130310 | MEASURABLE |  | 1.368659 | -10.161824 | 56.295610 | 1758 | 89 | 0.949374 | 20000 | 999 | -11.236732 | 57.915209 | -8.832694 | 55.088377 | -10.213117 | 57.378245 | -7.941824 | 56.115145 | -3.171538 | 52.275003 | False |
| EITHER|EXPANDING_OOS|q=0.01|L=45|S=45 | EITHER | EXPANDING_OOS | 0.010000 | 45 | 45 | HOLD_B | 10 | 0 | 5 | 1 | 5 | 2 | 3 | 18.054960 | 36.109920 | 48.423782 | 145.271345 | 36.276253 | 181.381265 | -17.642082 | -41.610349 | nan | 0.400000 | 1.000000 | 1 | 1 | 0.159700 | 0.031940 | MEASURABLE |  | 2.970336 | -36.276253 | 72.552506 | 180 | 2 | 0.988889 | 20000 | 999 | -36.276253 | 72.552506 | -36.276253 | 72.552506 | -36.276253 | 72.552506 | -17.372759 | 89.925265 | 21.793149 | 50.759357 | False |
| SIDE|EXPANDING_OOS|q=0.01|L=45|S=45 | SIDE | EXPANDING_OOS | 0.010000 | 45 | 45 | DEV | 167 | 0 | 64 | 1 | 103 | 55 | 48 | -16.315396 | -897.346787 | 0.829650 | 39.823222 | -8.325471 | -857.523564 | -11.164959 | -13.551520 | -18.935513 | 0.553398 | 0.555556 | 15 | 27 | -10.964800 | -0.106454 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 55 | 0.968714 | 0 | 999 | -29.060956 | 15.660345 | -28.953193 | 16.086134 | -29.670200 | 21.024452 | -28.277845 | 15.278490 | -27.485387 | 10.128578 | False |
| SIDE|EXPANDING_OOS|q=0.01|L=45|S=45 | SIDE | EXPANDING_OOS | 0.010000 | 45 | 45 | HOLD_B | 3 | 0 | 1 | 1 | 2 | 2 | 0 | 257.478182 | 514.956364 | nan | 0.000000 | 257.478182 | 514.956364 | -18.152801 | nan | nan | 0.500000 | 1.000000 | 1 | 1 | 0.000000 | 0.000000 | MEASURABLE |  | 1.096597 | -284.707383 | 533.109165 | 180 | 2 | 0.988889 | 20000 | 999 | -266.554582 | 524.032765 | -257.932002 | 514.956364 | -257.478182 | 514.956364 | 257.478182 | 257.478182 | 257.478182 | 257.478182 | False |
| REG|EXPANDING_OOS|q=0.02|L=45|S=45 | REG | EXPANDING_OOS | 0.020000 | 45 | 45 | DEV | 219 | 0 | 63 | 1 | 156 | 79 | 77 | 32.860492 | 2595.978903 | 18.357816 | 1413.551826 | 25.702120 | 4009.530730 | 20.909142 | 16.468099 | 7.242309 | 0.596154 | 0.538462 | 21 | 39 | -13.939100 | -0.089353 | MEASURABLE |  | 2.653396 | -6.646723 | 55.182102 | 1758 | 103 | 0.941411 | 20000 | 999 | -6.532203 | 54.665079 | -4.794838 | 54.851714 | -6.827389 | 57.387543 | 0.308290 | 48.980736 | 4.103072 | 44.994079 | False |
| REG|EXPANDING_OOS|q=0.02|L=45|S=45 | REG | EXPANDING_OOS | 0.020000 | 45 | 45 | HOLD_B | 21 | 0 | 7 | 1 | 14 | 3 | 11 | 19.490399 | 58.471197 | -10.499141 | -115.490549 | -4.072811 | -57.019352 | -23.766842 | -42.021390 | -72.929978 | 0.500000 | 0.750000 | 3 | 4 | 0.159700 | 0.011407 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 8 | 0.955556 | 0 | 999 | -59.317352 | 48.275131 | -63.278025 | 54.795280 | -58.457220 | 54.296325 | -53.567823 | 44.166433 | -42.833483 | 29.178071 | False |
| WGT|EXPANDING_OOS|q=0.02|L=45|S=45 | WGT | EXPANDING_OOS | 0.020000 | 45 | 45 | DEV | 229 | 0 | 52 | 1 | 177 | 92 | 85 | 17.278344 | 1589.607623 | 0.123036 | 10.458075 | 9.039919 | 1600.065697 | 6.347069 | 4.691856 | 0.653108 | 0.536723 | 0.525000 | 21 | 40 | -3.260700 | -0.018422 | MEASURABLE |  | 1.076070 | -7.055578 | 26.928070 | 1758 | 121 | 0.931172 | 20000 | 999 | -5.837354 | 25.154210 | -5.750732 | 24.540629 | -6.089748 | 25.633923 | -5.698478 | 25.271484 | -3.551832 | 23.794704 | False |
| WGT|EXPANDING_OOS|q=0.02|L=45|S=45 | WGT | EXPANDING_OOS | 0.020000 | 45 | 45 | HOLD_B | 9 | 0 | 1 | 1 | 8 | 4 | 4 | 44.928827 | 179.715306 | 43.189158 | 172.756632 | 44.058992 | 352.471938 | -25.805318 | -72.097803 | -153.823591 | 0.375000 | 0.500000 | 1 | 2 | 0.159700 | 0.019962 | MEASURABLE |  | 2.759856 | -101.976505 | 137.222313 | 180 | 6 | 0.966667 | 20000 | 999 | -88.306124 | 131.653956 | -84.489605 | 128.498760 | -76.849917 | 126.049943 | -86.815785 | 161.526597 | -2.791194 | 90.655388 | False |
| AGREE|EXPANDING_OOS|q=0.02|L=45|S=45 | AGREE | EXPANDING_OOS | 0.020000 | 45 | 45 | DEV | 108 | 0 | 35 | 1 | 73 | 51 | 22 | 49.976482 | 2548.800603 | 10.343549 | 227.558087 | 38.032311 | 2776.358690 | 28.771234 | 25.007316 | 15.167066 | 0.671233 | 0.633333 | 19 | 30 | -15.543000 | -0.212918 | MEASURABLE |  | 1.497226 | 7.939290 | 65.605356 | 1758 | 52 | 0.970421 | 20000 | 999 | 8.373744 | 67.582503 | 8.587509 | 64.551725 | 7.984534 | 66.014080 | 17.881443 | 56.805365 | 23.478387 | 52.431876 | False |
| AGREE|EXPANDING_OOS|q=0.02|L=45|S=45 | AGREE | EXPANDING_OOS | 0.020000 | 45 | 45 | HOLD_B | 5 | 0 | 1 | 1 | 4 | 2 | 2 | 257.478182 | 514.956364 | 163.719355 | 327.438710 | 210.598769 | 842.395075 | 103.095303 | 28.668159 | nan | 0.750000 | 1.000000 | 2 | 2 | 0.159700 | 0.039925 | MEASURABLE |  | 2.932797 | -191.726489 | 421.197537 | 180 | 3 | 0.983333 | 20000 | 999 | -172.854209 | 421.197537 | -172.854209 | 421.197537 | -172.854209 | 421.197537 | 139.138351 | 305.334374 | 210.598769 | 210.598769 | False |
| EITHER|EXPANDING_OOS|q=0.02|L=45|S=45 | EITHER | EXPANDING_OOS | 0.020000 | 45 | 45 | DEV | 338 | 0 | 79 | 1 | 259 | 120 | 139 | 20.971827 | 2516.619296 | 2.143070 | 297.886681 | 10.866818 | 2814.505977 | 8.482178 | 6.627625 | 2.334710 | 0.540541 | 0.522727 | 23 | 44 | -1.761900 | -0.006803 | MEASURABLE |  | 2.127490 | -7.183751 | 27.471659 | 1758 | 167 | 0.905006 | 20000 | 999 | -7.484804 | 27.473131 | -6.673065 | 27.395735 | -8.445513 | 28.496244 | -8.972923 | 28.599436 | -7.217355 | 27.542450 | False |
| EITHER|EXPANDING_OOS|q=0.02|L=45|S=45 | EITHER | EXPANDING_OOS | 0.020000 | 45 | 45 | HOLD_B | 25 | 0 | 7 | 1 | 18 | 5 | 13 | -55.353972 | -276.769860 | -20.782510 | -270.172628 | -30.385694 | -546.942489 | -46.993652 | -62.136239 | -88.176380 | 0.388889 | 0.250000 | 1 | 4 | 0.159700 | 0.008872 | MEASURABLE |  | 9.781356 | -63.030264 | 6.306003 | 180 | 11 | 0.938889 | 20000 | 999 | -64.631024 | 2.909139 | -59.417298 | 2.487991 | -55.169579 | 0.592833 | -82.630534 | 27.629631 | -70.963562 | 10.962051 | False |
| SIDE|EXPANDING_OOS|q=0.02|L=45|S=45 | SIDE | EXPANDING_OOS | 0.020000 | 45 | 45 | DEV | 315 | 0 | 97 | 1 | 218 | 105 | 113 | -3.797091 | -398.694566 | 0.178030 | 20.117393 | -1.736593 | -378.577173 | -4.262365 | -6.248092 | -10.853198 | 0.545872 | 0.414634 | 17 | 41 | -20.917900 | -0.095954 | MEASURABLE |  | 4.211768 | -19.262048 | 17.553790 | 1758 | 120 | 0.931741 | 20000 | 999 | -19.219683 | 18.198908 | -19.982228 | 16.398518 | -20.319818 | 18.566526 | -18.715255 | 14.011991 | -18.925707 | 12.568955 | False |
| SIDE|EXPANDING_OOS|q=0.02|L=45|S=45 | SIDE | EXPANDING_OOS | 0.020000 | 45 | 45 | HOLD_B | 13 | 0 | 4 | 1 | 9 | 4 | 5 | 35.238553 | 140.954213 | -59.041963 | -295.209816 | -17.139511 | -154.255603 | -85.920596 | -98.978513 | -140.866913 | 0.222222 | 0.333333 | 1 | 3 | 0.000000 | 0.000000 | MEASURABLE |  | 41.000000 | -53.036126 | 18.152945 | 180 | 4 | 0.977778 | 20000 | 999 | -78.169704 | 49.103300 | -73.596982 | 30.744939 | -48.082615 | 27.360595 | -110.277596 | 70.462787 | -78.016869 | 17.510345 | False |
| REG|ROLLING_180D|q=0.01|L=45|S=45 | REG | ROLLING_180D | 0.010000 | 45 | 45 | DEV | 457 | 0 | 132 | 1 | 325 | 151 | 174 | 11.233061 | 1696.192174 | 10.851367 | 1888.137780 | 11.028708 | 3584.329955 | 8.690482 | 6.778985 | 2.758466 | 0.535385 | 0.560000 | 28 | 50 | -25.834400 | -0.079490 | MEASURABLE |  | 2.434232 | -5.841320 | 26.449576 | 1758 | 191 | 0.891354 | 20000 | 999 | -5.384148 | 25.999151 | -4.901192 | 24.687740 | -4.070258 | 24.576600 | -4.913110 | 25.035756 | -1.431191 | 22.978551 | False |
| REG|ROLLING_180D|q=0.01|L=45|S=45 | REG | ROLLING_180D | 0.010000 | 45 | 45 | HOLD_B | 78 | 0 | 24 | 1 | 54 | 27 | 27 | 15.183215 | 409.946796 | 21.230556 | 573.225008 | 18.206885 | 983.171805 | 7.273113 | -2.839119 | -15.112386 | 0.500000 | 0.400000 | 2 | 5 | 0.072500 | 0.001343 | MEASURABLE |  | 4.784775 | -39.296421 | 57.758005 | 180 | 28 | 0.844444 | 20000 | 999 | -38.567167 | 57.722015 | -39.625032 | 62.847928 | -33.383287 | 62.992987 | -36.858410 | 66.025444 | -27.054879 | 56.233444 | False |
| WGT|ROLLING_180D|q=0.01|L=45|S=45 | WGT | ROLLING_180D | 0.010000 | 45 | 45 | DEV | 465 | 0 | 101 | 1 | 364 | 198 | 166 | 10.668780 | 2112.418379 | 7.854884 | 1303.910726 | 9.385520 | 3416.329105 | 8.241527 | 7.167205 | 4.437122 | 0.552198 | 0.660377 | 35 | 53 | 5.242100 | 0.014401 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 226 | 0.871445 | 0 | 999 | -1.622535 | 21.074478 | -1.302484 | 19.336219 | -0.117327 | 19.390944 | 0.007835 | 18.913924 | 1.146038 | 18.192691 | False |
| WGT|ROLLING_180D|q=0.01|L=45|S=45 | WGT | ROLLING_180D | 0.010000 | 45 | 45 | HOLD_B | 48 | 0 | 6 | 1 | 42 | 15 | 27 | 18.385208 | 275.778120 | 16.368194 | 441.941247 | 17.088556 | 717.719368 | 6.530211 | -0.383809 | -13.634361 | 0.500000 | 0.333333 | 2 | 6 | 0.301800 | 0.007186 | MEASURABLE |  | 6.871544 | -35.102714 | 52.907688 | 180 | 27 | 0.850000 | 20000 | 999 | -34.634524 | 51.542226 | -37.447500 | 56.175883 | -33.270788 | 55.129951 | -21.824548 | 55.966039 | -19.378594 | 49.159779 | False |
| AGREE|ROLLING_180D|q=0.01|L=45|S=45 | AGREE | ROLLING_180D | 0.010000 | 45 | 45 | DEV | 214 | 0 | 60 | 1 | 154 | 90 | 64 | 18.035918 | 1623.232604 | 17.020318 | 1089.300338 | 17.613850 | 2712.532942 | 14.953453 | 12.439027 | 5.564799 | 0.571429 | 0.585366 | 24 | 41 | -14.220300 | -0.092340 | MEASURABLE |  | 1.133971 | -0.920437 | 36.984786 | 1758 | 95 | 0.945961 | 20000 | 999 | -0.350804 | 37.344581 | 0.413980 | 35.270570 | 0.310799 | 36.250486 | 1.033983 | 38.564327 | 3.782281 | 33.603681 | False |
| AGREE|ROLLING_180D|q=0.01|L=45|S=45 | AGREE | ROLLING_180D | 0.010000 | 45 | 45 | HOLD_B | 23 | 0 | 4 | 1 | 19 | 9 | 10 | 23.648988 | 212.840896 | 28.085191 | 280.851907 | 25.983832 | 493.692803 | 2.428449 | -14.081113 | -41.658514 | 0.526316 | 0.600000 | 3 | 5 | -0.672900 | -0.035416 | MEASURABLE |  | 2.608277 | -58.016433 | 79.315489 | 180 | 13 | 0.927778 | 20000 | 999 | -56.346361 | 80.718929 | -59.924364 | 84.941303 | -51.800851 | 82.809953 | -41.123108 | 97.310010 | -22.051577 | 84.745441 | False |
| EITHER|ROLLING_180D|q=0.01|L=45|S=45 | EITHER | ROLLING_180D | 0.010000 | 45 | 45 | DEV | 706 | 0 | 178 | 1 | 528 | 255 | 273 | 13.506190 | 3444.078474 | 4.729241 | 1291.082657 | 8.968108 | 4735.161131 | 7.797072 | 6.889648 | 4.641661 | 0.537879 | 0.622642 | 33 | 53 | -6.372000 | -0.012068 | MEASURABLE |  | 2.310309 | -1.175862 | 18.734723 | 1758 | 306 | 0.825939 | 20000 | 999 | -0.981968 | 19.120369 | -0.498491 | 17.831525 | -0.584014 | 17.587586 | -0.524638 | 17.887397 | -0.089641 | 18.144067 | False |
| EITHER|ROLLING_180D|q=0.01|L=45|S=45 | EITHER | ROLLING_180D | 0.010000 | 45 | 45 | HOLD_B | 103 | 0 | 27 | 1 | 76 | 33 | 43 | 6.819219 | 225.034228 | 15.930778 | 685.023474 | 11.974443 | 910.057702 | 4.164812 | -2.983085 | -10.835189 | 0.473684 | 0.500000 | 3 | 6 | 1.047200 | 0.013779 | MEASURABLE |  | 4.840304 | -29.535965 | 42.475237 | 180 | 41 | 0.772222 | 20000 | 999 | -30.210593 | 42.161231 | -31.396477 | 46.651699 | -26.575488 | 47.506728 | -36.347322 | 50.450633 | -26.120958 | 48.937349 | False |
| SIDE|ROLLING_180D|q=0.01|L=45|S=45 | SIDE | ROLLING_180D | 0.010000 | 45 | 45 | DEV | 569 | 0 | 152 | 1 | 417 | 229 | 188 | -2.253375 | -516.022920 | 0.683771 | 128.548998 | -0.929194 | -387.473923 | -2.244783 | -3.273457 | -5.604969 | 0.544365 | 0.479167 | 23 | 48 | -12.874100 | -0.030873 | MEASURABLE |  | 4.316163 | -11.774444 | 10.497691 | 1758 | 241 | 0.862912 | 20000 | 999 | -12.257853 | 10.565686 | -12.219775 | 10.343948 | -12.774000 | 11.105896 | -10.503546 | 8.785206 | -10.436462 | 9.870803 | False |
| SIDE|ROLLING_180D|q=0.01|L=45|S=45 | SIDE | ROLLING_180D | 0.010000 | 45 | 45 | HOLD_B | 59 | 0 | 11 | 1 | 48 | 25 | 23 | -4.648259 | -116.206464 | -26.157572 | -601.624147 | -14.954804 | -717.830611 | -26.615740 | -32.671508 | -44.012936 | 0.395833 | 0.166667 | 1 | 6 | 0.887000 | 0.018479 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 180 | 31 | 0.827778 | 0 | 999 | -36.731316 | 7.599615 | -34.125667 | 7.623806 | -30.424707 | 4.291785 | -46.056328 | 13.576235 | -39.212251 | 7.430650 | False |
| REG|ROLLING_180D|q=0.02|L=45|S=45 | REG | ROLLING_180D | 0.020000 | 45 | 45 | DEV | 843 | 0 | 263 | 1 | 580 | 273 | 307 | 1.952709 | 533.089513 | 3.566002 | 1094.762498 | 2.806641 | 1627.852011 | 1.484004 | 0.403346 | -1.780312 | 0.524138 | 0.490566 | 26 | 53 | -21.182700 | -0.036522 | MEASURABLE |  | 1.066969 | -7.975835 | 13.445984 | 1758 | 321 | 0.817406 | 20000 | 999 | -6.924503 | 12.076369 | -7.002510 | 12.115343 | -6.158199 | 11.626312 | -6.065576 | 11.677830 | -5.308502 | 10.033570 | False |
| REG|ROLLING_180D|q=0.02|L=45|S=45 | REG | ROLLING_180D | 0.020000 | 45 | 45 | HOLD_B | 122 | 0 | 39 | 1 | 83 | 37 | 46 | 5.916460 | 218.909036 | 6.598099 | 303.512555 | 6.294236 | 522.421591 | -0.917991 | -7.510919 | -15.400732 | 0.469880 | 0.500000 | 3 | 6 | 1.491800 | 0.017973 | MEASURABLE |  | 41.000000 | -21.947808 | 30.509272 | 180 | 45 | 0.750000 | 20000 | 999 | -30.490592 | 33.384864 | -27.749248 | 31.810075 | -21.667537 | 30.776693 | -31.082328 | 39.288229 | -24.849205 | 35.947273 | False |
| WGT|ROLLING_180D|q=0.02|L=45|S=45 | WGT | ROLLING_180D | 0.020000 | 45 | 45 | DEV | 891 | 0 | 217 | 1 | 674 | 328 | 346 | 7.737590 | 2537.929489 | 0.374699 | 129.645970 | 3.957827 | 2667.575459 | 3.201422 | 2.484308 | 0.590629 | 0.508902 | 0.528302 | 28 | 53 | -11.684600 | -0.017336 | MEASURABLE |  | 1.519381 | -3.500802 | 11.672700 | 1758 | 386 | 0.780432 | 20000 | 999 | -3.709868 | 11.213892 | -3.680362 | 10.880794 | -3.310076 | 11.469370 | -3.821957 | 12.403398 | -3.226023 | 12.367448 | False |
| WGT|ROLLING_180D|q=0.02|L=45|S=45 | WGT | ROLLING_180D | 0.020000 | 45 | 45 | HOLD_B | 97 | 0 | 19 | 1 | 78 | 27 | 51 | 25.116379 | 678.142229 | -0.592117 | -30.197959 | 8.306978 | 647.944270 | 2.570955 | -2.137769 | -10.721193 | 0.500000 | 0.333333 | 2 | 6 | -0.510900 | -0.006550 | MEASURABLE |  | 1.936484 | -17.783715 | 30.520470 | 180 | 50 | 0.722222 | 20000 | 999 | -18.191821 | 29.832831 | -17.021580 | 30.496118 | -14.696987 | 30.218834 | -20.490275 | 31.916043 | -15.315033 | 30.373025 | False |
| AGREE|ROLLING_180D|q=0.02|L=45|S=45 | AGREE | ROLLING_180D | 0.020000 | 45 | 45 | DEV | 428 | 0 | 117 | 1 | 311 | 178 | 133 | 13.623223 | 2424.933679 | 1.493070 | 198.578316 | 8.435730 | 2623.511995 | 6.898096 | 5.546133 | 2.251430 | 0.527331 | 0.500000 | 26 | 52 | -8.786400 | -0.028252 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1758 | 194 | 0.889647 | 0 | 999 | -5.592915 | 21.494432 | -4.011205 | 21.016668 | -3.931356 | 21.178186 | -2.310059 | 19.492696 | -1.717875 | 18.951515 | False |
| AGREE|ROLLING_180D|q=0.02|L=45|S=45 | AGREE | ROLLING_180D | 0.020000 | 45 | 45 | HOLD_B | 42 | 0 | 8 | 1 | 34 | 15 | 19 | -1.757868 | -26.368020 | 7.320839 | 139.095949 | 3.315527 | 112.727929 | -10.219781 | -19.385744 | -34.938446 | 0.470588 | 0.333333 | 2 | 6 | -0.672900 | -0.019791 | MEASURABLE |  | 31.668680 | -27.910524 | 28.306728 | 180 | 25 | 0.861111 | 20000 | 999 | -37.970777 | 34.280367 | -33.286933 | 31.847742 | -25.977843 | 29.616032 | -38.213030 | 40.146641 | -30.059855 | 33.907214 | False |
| EITHER|ROLLING_180D|q=0.02|L=45|S=45 | EITHER | ROLLING_180D | 0.020000 | 45 | 45 | DEV | 1302 | 0 | 374 | 1 | 928 | 419 | 509 | 6.477278 | 2713.979645 | 0.547156 | 278.502268 | 3.224657 | 2992.481913 | 2.552727 | 2.001468 | 0.561850 | 0.517241 | 0.528302 | 28 | 53 | -23.138100 | -0.024933 | MEASURABLE |  | 2.565637 | -3.407266 | 9.975819 | 1758 | 486 | 0.723549 | 20000 | 999 | -3.093683 | 9.134528 | -3.266013 | 8.819693 | -2.172606 | 8.768609 | -2.593122 | 9.635923 | -2.242204 | 8.687305 | False |
| EITHER|ROLLING_180D|q=0.02|L=45|S=45 | EITHER | ROLLING_180D | 0.020000 | 45 | 45 | HOLD_B | 175 | 0 | 52 | 1 | 123 | 48 | 75 | 8.957090 | 429.940330 | 3.254023 | 244.051719 | 5.479610 | 673.992049 | 0.625371 | -3.775322 | -10.140855 | 0.479675 | 0.500000 | 3 | 6 | 1.653800 | 0.013446 | MEASURABLE |  | 2.017095 | -22.643575 | 27.870580 | 180 | 64 | 0.644444 | 20000 | 999 | -22.121433 | 27.168816 | -19.972373 | 27.553197 | -17.658184 | 27.982854 | -25.475401 | 35.453452 | -23.385877 | 31.063580 | False |
| SIDE|ROLLING_180D|q=0.02|L=45|S=45 | SIDE | ROLLING_180D | 0.020000 | 45 | 45 | DEV | 995 | 0 | 247 | 1 | 748 | 378 | 370 | -2.466423 | -932.307752 | -3.948737 | -1461.032586 | -3.199653 | -2393.340338 | -3.935336 | -4.509854 | -6.033158 | 0.516043 | 0.519231 | 27 | 52 | -17.877400 | -0.023900 | MEASURABLE |  | 2.987349 | -10.442842 | 4.391906 | 1758 | 387 | 0.779863 | 20000 | 999 | -10.809434 | 3.942937 | -10.587375 | 4.771108 | -10.396805 | 4.893014 | -10.784713 | 4.928852 | -11.521144 | 4.482400 | False |
| SIDE|ROLLING_180D|q=0.02|L=45|S=45 | SIDE | ROLLING_180D | 0.020000 | 45 | 45 | HOLD_B | 116 | 0 | 29 | 1 | 87 | 41 | 46 | 3.200541 | 131.222181 | -17.365204 | -798.799392 | -7.673301 | -667.577211 | -10.245081 | -12.728542 | -19.146130 | 0.482759 | 0.333333 | 2 | 6 | 1.634700 | 0.018790 | MEASURABLE |  | 4.390654 | -21.857171 | 9.993113 | 180 | 42 | 0.766667 | 20000 | 999 | -22.245685 | 10.127022 | -21.954459 | 11.544811 | -19.595543 | 8.150287 | -19.377215 | 4.063071 | -16.170332 | 1.287722 | False |

## PRIMARY_BASELINES

| cell_id | combination | method | q | h_long | h_short | segment | n | actual_net_mean_bps | opposite_net_mean_bps | always_long_net_mean_bps | random_q025_net_mean_bps | random_q500_net_mean_bps | random_q975_net_mean_bps | actual_random_percentile | random_seed | random_repetitions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 60 | DEV | 24 | 68.261407 | -76.261407 | 43.343881 | -78.000895 | -3.504125 | 68.263602 | 97.400000 | 20261001 | 1000 |
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | AGREE | EXPANDING_OOS | 0.010000 | 120 | 60 | HOLD_B | 3 | 315.169045 | -323.169045 | -123.042888 | -447.686821 | 1.474888 | 439.686821 | 86.000000 | 20261001 | 1000 |

## PRIMARY_YEAR

| segment | year | n | net_mean_bps | net_sum_bps |
|---|---|---|---|---|
| DEV | 2021 | 3 | 281.874920 | 845.624759 |
| DEV | 2022 | 10 | -26.153907 | -261.539071 |
| DEV | 2023 | 2 | 137.971715 | 275.943431 |
| DEV | 2024 | 6 | 47.943702 | 287.662211 |
| DEV | 2025 | 3 | 163.527479 | 490.582436 |
| HOLD_B | 2026 | 3 | 315.169045 | 945.507134 |

## PRIMARY_CONCENTRATION

| segment | trade_days | top5_day_pnl_bps | total_pnl_bps | top5_day_pnl_share |
|---|---|---|---|---|
| DEV | 21 | 1392.248836 | 1638.273765 | 0.849827 |
| HOLD_B | 2 | 945.507134 | 945.507134 | 1.000000 |

## PRIMARY_TOP10

| segment | rank | open_time | side | hold | abs_r_h_bps | net_bps | intraday_range_bps |
|---|---|---|---|---|---|---|---|
| DEV | 1 | 2021-09-07 15:15:00+00:00 | 1 | 120 | 442.825359 | 436.527659 | 2580.783121 |
| DEV | 2 | 2021-12-04 05:30:00+00:00 | 1 | 120 | 351.531242 | 347.531242 | 3179.543392 |
| DEV | 3 | 2024-08-05 06:15:00+00:00 | 1 | 120 | 269.814831 | 265.371931 | 1922.537228 |
| DEV | 4 | 2024-07-04 02:00:00+00:00 | 1 | 120 | 233.988633 | 229.988633 | 696.605375 |
| DEV | 5 | 2025-03-02 17:45:00+00:00 | -1 | 60 | 208.071645 | 204.071645 | 1171.087455 |
| DEV | 6 | 2025-10-10 21:15:00+00:00 | 1 | 120 | 178.129657 | 174.129657 | 2066.708368 |
| DEV | 7 | 2023-08-17 22:00:00+00:00 | 1 | 120 | 144.413285 | 139.413285 | 1706.561979 |
| DEV | 8 | 2023-03-14 13:00:00+00:00 | -1 | 60 | 140.530145 | 136.530145 | 1060.039247 |
| DEV | 9 | 2022-07-20 21:45:00+00:00 | -1 | 60 | 130.646440 | 126.646440 | 595.572703 |
| DEV | 10 | 2025-03-04 01:45:00+00:00 | 1 | 120 | 116.381134 | 112.381134 | 952.093596 |
| HOLD_B | 1 | 2026-02-05 23:15:00+00:00 | -1 | 60 | 657.477600 | 653.317900 | 1780.879368 |
| HOLD_B | 2 | 2026-02-06 00:30:00+00:00 | 1 | 120 | 486.965899 | 482.965899 | 1992.374582 |
| HOLD_B | 3 | 2026-02-05 20:15:00+00:00 | 1 | 120 | 186.776665 | -190.776665 | 1780.879368 |

## PRIMARY_HOLD_B_MONTH

| month | n | long_n | short_n | net_mean_bps | net_sum_bps |
|---|---|---|---|---|---|
| 2026-01 | 0 | 0 | 0 | nan | 0.000000 |
| 2026-02 | 3 | 2 | 1 | 315.169045 | 945.507134 |
| 2026-03 | 0 | 0 | 0 | nan | 0.000000 |
| 2026-04 | 0 | 0 | 0 | nan | 0.000000 |
| 2026-05 | 0 | 0 | 0 | nan | 0.000000 |
| 2026-06 | 0 | 0 | 0 | nan | 0.000000 |

## k45_gate_direction_r2_9b_20261002

- 테스트 재실행 `tests/test_k45_gate_direction_r2_9b.py`: `5 passed in 2.08s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-02T02:25:58.036355+00:00 |
| run_finished_utc | 2026-10-02T15:13:34.192809+00:00 |
| runtime_seconds | 46056.156454 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | R2-9 고정 6필터 통과 64칸 중 일부는 교란 7개 변형에서 부호가 유지된다. |
| frozen_robust_rule | DEV net > 0 이 7/7, HOLD_B net > 0 이 ≥ 6/7, HOLD_B n 중앙값 ≥ 30, DEV 변형 간 최소 net > 0. |
| frozen_selection_rule | 강건 칸 중 DEV CI 하한의 변형 간 중앙값이 가장 큰 칸. 동률이면 DEV n 큰 칸. |
| frozen_six_filter_rule | V0 DEV net>0; DEV top5 제거 net>0; DEV 무작위 백분위>=95; HOLD_B net>0; HOLD_B net>항상 롱; HOLD_B n>=30 |
| variants | {"V0": "reused fixed artifacts", "V1": {"random_seed": 20261002, "depth": 4, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3}, "V2": {"random_seed": 20261003, "depth": 4, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3}, "V3": {"random_seed": 20261004, "depth": 4, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3}, "V4": {"random_seed": 20261001, "depth": 6, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3}, "V5": {"random_seed": 20261001, "depth": 4, "learning_rate": 0.03, "iterations": 833, "l2_leaf_reg": 3}, "V6": "reused R2-11 tuned artifacts"} |
| cell_count | 516 |
| screen_cell_count | 64 |
| max_positions | 1 |
| random_repetitions | 1000 |
| bonferroni_cells | 516 |
| cost_bps | 4.0 |
| device | CPU |
| stop_tuning | False |
| local_data_only | True |
| downloads | 0 |
| patchtst_fits | 0 |
| live_orders | 0 |
| train_rule | signal_index + h < stop_start_index |

### out_of_sample_result (원문)

```text
{
 "robust_cell_count": 28,
 "robust_cells": [
  "AGREE|ROLLING_180D|q=0.02|L=120|S=45",
  "EITHER|ROLLING_180D|q=0.01|L=120|S=60",
  "EITHER|ROLLING_180D|q=0.02|L=120|S=60",
  "REG|ROLLING_180D|q=0.01|L=45|S=45",
  "SIDE|ROLLING_180D|q=0.01|L=120|S=15",
  "SIDE|ROLLING_180D|q=0.01|L=120|S=5",
  "SIDE|ROLLING_180D|q=0.01|L=120|S=60",
  "SIDE|ROLLING_180D|q=0.01|L=180|S=15",
  "SIDE|ROLLING_180D|q=0.01|L=180|S=60",
  "SIDE|ROLLING_180D|q=0.01|L=240|S=15",
  "SIDE|ROLLING_180D|q=0.01|L=240|S=5",
  "SIDE|ROLLING_180D|q=0.01|L=240|S=60",
  "SIDE|ROLLING_180D|q=0.01|L=30|S=60",
  "SIDE|ROLLING_180D|q=0.01|L=60|S=15",
  "SIDE|ROLLING_180D|q=0.01|L=60|S=5",
  "SIDE|ROLLING_180D|q=0.02|L=180|S=15",
  "SIDE|ROLLING_180D|q=0.02|L=180|S=5",
  "SIDE|ROLLING_180D|q=0.02|L=180|S=60",
  "SIDE|ROLLING_180D|q=0.02|L=30|S=15",
  "SIDE|ROLLING_180D|q=0.02|L=30|S=60",
  "SIDE|ROLLING_180D|q=0.02|L=60|S=15",
  "SIDE|ROLLING_180D|q=0.02|L=60|S=5",
  "SIDE|ROLLING_180D|q=0.02|L=60|S=60",
  "SIDE|ROLLING_180D|q=0.02|L=90|S=60",
  "WGT|ROLLING_180D|q=0.01|L=120|S=45",
  "WGT|ROLLING_180D|q=0.01|L=120|S=60",
  "WGT|ROLLING_180D|q=0.01|L=45|S=60",
  "WGT|ROLLING_180D|q=0.02|L=120|S=60"
 ],
 "selected_cell": "SIDE|ROLLING_180D|q=0.01|L=120|S=60",
 "hypothesis_some_robust": true
}
```

- 출력 해시 확인: 673/673 일치

### REPORT.md 앞 150줄 (전체 661줄, 원문)

# R2-9b

## ROBUST_CELLS

| cell_id | dev_net_median | dev_net_min | dev_net_max | dev_long_net_median | dev_long_net_min | dev_long_net_max | dev_short_net_median | dev_short_net_min | dev_short_net_max | dev_n_median | dev_positive_variants | dev_pw_ci95_lower_median | hold_b_net_median | hold_b_net_min | hold_b_net_max | hold_b_long_net_median | hold_b_long_net_min | hold_b_long_net_max | hold_b_short_net_median | hold_b_short_net_min | hold_b_short_net_max | hold_b_n_median | hold_b_positive_variants | hold_b_pw_ci95_lower_median | jaccard_v0_median | is_robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREE|ROLLING_180D|q=0.02|L=120|S=45 | 10.152283 | 5.306317 | 16.880676 | 19.018913 | 12.207569 | 25.687366 | -1.414295 | -11.677626 | 16.590399 | 275.000000 | 7 | -6.342312 | 15.838483 | 4.837120 | 25.215063 | 22.140133 | 11.124993 | 79.464037 | 5.054851 | -25.994898 | 17.193125 | 31.000000 | 7 | -29.362324 | 0.450704 | True |
| EITHER|ROLLING_180D|q=0.01|L=120|S=60 | 8.920729 | 0.998401 | 15.141741 | 12.829240 | 7.072937 | 21.756500 | 5.882472 | -7.302449 | 11.051107 | 462.000000 | 7 | -4.330530 | 15.221564 | 10.261165 | 35.210654 | 31.049597 | 12.462343 | 51.712910 | 15.626970 | -8.299935 | 25.212373 | 63.000000 | 7 | -22.722783 | 0.430362 | True |
| EITHER|ROLLING_180D|q=0.02|L=120|S=60 | 5.820981 | 2.809681 | 7.951852 | 11.251110 | 5.604129 | 14.583051 | 3.064841 | -3.865370 | 5.383090 | 789.000000 | 7 | -3.991290 | 12.164627 | 6.066723 | 13.100578 | 26.437139 | 10.659860 | 38.394796 | 3.328999 | -5.461752 | 8.577858 | 105.000000 | 7 | -16.435170 | 0.462428 | True |
| REG|ROLLING_180D|q=0.01|L=45|S=45 | 13.780779 | 8.556432 | 18.717612 | 18.357916 | 4.623605 | 30.433208 | 9.944451 | 1.521546 | 16.194818 | 318.000000 | 7 | -4.516665 | 18.206885 | -20.566502 | 34.089363 | 15.183215 | -34.367012 | 38.995341 | 21.230556 | -8.020584 | 38.775803 | 54.000000 | 6 | -50.890445 | 0.451429 | True |
| SIDE|ROLLING_180D|q=0.01|L=120|S=15 | 10.022622 | 4.281368 | 14.107589 | 17.651338 | 7.609752 | 28.742628 | 4.094141 | 0.223316 | 8.108942 | 304.000000 | 7 | -1.378244 | 15.493175 | 4.437945 | 23.749953 | 43.310036 | -4.022533 | 77.071705 | 1.685050 | -6.631521 | 9.373225 | 38.000000 | 7 | -14.164553 | 0.387629 | True |
| SIDE|ROLLING_180D|q=0.01|L=120|S=5 | 7.658029 | 1.947510 | 11.768788 | 17.651338 | 7.436966 | 29.454628 | -1.961456 | -3.693403 | 3.662963 | 277.000000 | 7 | -5.252805 | 13.923174 | -2.976779 | 21.892779 | 43.310036 | -4.022533 | 77.071705 | -2.366756 | -5.870449 | -0.558362 | 41.000000 | 6 | -25.941510 | 0.408482 | True |
| SIDE|ROLLING_180D|q=0.01|L=120|S=60 | 16.651305 | 6.938793 | 20.112477 | 20.889905 | 10.682792 | 32.001301 | 12.268305 | 4.623955 | 14.371693 | 301.000000 | 7 | 2.328764 | 29.666579 | -11.194486 | 44.112900 | 53.005298 | -4.022533 | 77.071705 | 11.266992 | -18.930781 | 35.458990 | 33.000000 | 6 | -42.215847 | 0.398734 | True |
| SIDE|ROLLING_180D|q=0.01|L=180|S=15 | 12.250504 | 6.853547 | 13.232461 | 28.885723 | 14.635688 | 33.509102 | 2.990688 | -1.919868 | 6.477387 | 274.000000 | 7 | -2.388626 | 32.004435 | 1.021867 | 45.071213 | 62.984544 | 8.986507 | 100.628947 | 0.689296 | -4.068208 | 9.373225 | 42.000000 | 7 | -20.775629 | 0.397291 | True |
| SIDE|ROLLING_180D|q=0.01|L=180|S=60 | 16.461809 | 14.821757 | 20.512902 | 32.510568 | 23.506789 | 36.562301 | 11.128075 | 5.695413 | 14.471775 | 263.000000 | 7 | 1.145897 | 35.109415 | 7.866741 | 57.154101 | 59.676147 | 8.986507 | 100.628947 | 6.956932 | -25.508646 | 36.131335 | 36.000000 | 7 | -33.492796 | 0.419811 | True |
| SIDE|ROLLING_180D|q=0.01|L=240|S=15 | 15.007044 | 11.564752 | 18.950211 | 37.933390 | 31.816802 | 41.602298 | 3.738841 | -2.731497 | 6.898138 | 256.000000 | 7 | -0.899232 | 20.176430 | -6.682237 | 35.136289 | 43.426685 | -10.561310 | 85.832581 | 2.705416 | -5.889283 | 16.195668 | 42.000000 | 6 | -43.282891 | 0.408313 | True |
| SIDE|ROLLING_180D|q=0.01|L=240|S=5 | 12.980153 | 11.473031 | 17.716670 | 38.419165 | 31.860287 | 41.602298 | -0.059116 | -1.500606 | 4.137853 | 246.000000 | 7 | -2.591738 | 10.011806 | -6.542319 | 33.854993 | 43.426685 | -10.561310 | 85.832581 | -2.487213 | -4.607249 | 0.379832 | 43.000000 | 6 | -42.730596 | 0.419023 | True |
| SIDE|ROLLING_180D|q=0.01|L=240|S=60 | 19.297439 | 14.351355 | 21.847660 | 37.777438 | 28.238099 | 43.178048 | 10.919129 | 4.834856 | 12.491215 | 257.000000 | 7 | 1.873150 | 4.161664 | -9.475087 | 63.802472 | 43.426685 | -10.561310 | 85.832581 | 11.713544 | -37.689315 | 55.029176 | 32.000000 | 6 | -63.401027 | 0.433249 | True |
| SIDE|ROLLING_180D|q=0.01|L=30|S=60 | 9.518770 | 8.613064 | 14.112857 | 10.945965 | 5.424512 | 14.896201 | 12.270997 | 5.453470 | 13.698569 | 406.000000 | 7 | 0.855997 | 4.085504 | -7.236039 | 31.845361 | 21.144552 | -2.183044 | 46.743533 | 8.460059 | -21.194899 | 18.978757 | 39.000000 | 6 | -22.828047 | 0.414791 | True |
| SIDE|ROLLING_180D|q=0.01|L=60|S=15 | 7.174007 | 3.692746 | 11.851593 | 11.345777 | 2.599674 | 19.949978 | 3.080100 | 1.083203 | 7.430400 | 383.000000 | 7 | -3.592361 | 10.128917 | -3.391891 | 23.964410 | 25.366813 | -3.478174 | 41.030119 | 1.952718 | -11.394110 | 9.364627 | 52.000000 | 6 | -25.780368 | 0.411570 | True |
| SIDE|ROLLING_180D|q=0.01|L=60|S=5 | 6.522040 | 1.875107 | 10.134183 | 11.856828 | 2.599674 | 19.949978 | 0.177228 | -2.927373 | 2.557211 | 359.000000 | 7 | -6.089434 | 9.769075 | -3.526396 | 18.812393 | 25.366813 | -3.478174 | 41.030119 | -1.446708 | -5.559452 | -0.140555 | 54.000000 | 6 | -28.329570 | 0.414336 | True |
| SIDE|ROLLING_180D|q=0.02|L=180|S=15 | 8.504082 | 4.892337 | 10.135354 | 20.164174 | 15.362818 | 29.076422 | 1.677722 | 0.400668 | 3.904293 | 505.000000 | 7 | -1.687748 | 15.317479 | -3.555235 | 23.882432 | 32.135868 | -13.305889 | 56.599246 | 5.570198 | -3.344108 | 6.579447 | 84.000000 | 6 | -9.915369 | 0.416768 | True |
| SIDE|ROLLING_180D|q=0.02|L=180|S=5 | 5.631905 | 4.101615 | 9.224699 | 20.137228 | 13.177903 | 28.013115 | -0.375429 | -2.982360 | 0.860284 | 467.000000 | 7 | -4.208478 | 9.904621 | -9.667514 | 21.130379 | 32.135868 | -13.305889 | 56.599246 | -2.438742 | -7.294661 | -0.065047 | 77.000000 | 6 | -13.679144 | 0.441710 | True |
| SIDE|ROLLING_180D|q=0.02|L=180|S=60 | 10.453494 | 6.126966 | 11.764783 | 22.543054 | 18.477508 | 31.087022 | 3.389966 | 0.166577 | 6.989978 | 485.000000 | 7 | -1.839186 | 31.605726 | -4.282531 | 37.975492 | 45.172250 | -18.700800 | 61.902385 | 15.508996 | -14.057577 | 25.749169 | 67.000000 | 6 | -22.244046 | 0.439633 | True |
| SIDE|ROLLING_180D|q=0.02|L=30|S=15 | 4.598463 | 1.424441 | 6.687796 | 5.906885 | 2.575473 | 11.681403 | 1.387413 | 0.129903 | 3.407657 | 806.000000 | 7 | -0.780733 | 9.343080 | -0.048770 | 15.214949 | 17.457970 | 2.715999 | 30.424578 | 5.158840 | -1.389265 | 5.858782 | 98.000000 | 6 | -6.286734 | 0.479741 | True |
| SIDE|ROLLING_180D|q=0.02|L=30|S=60 | 5.218040 | 2.715133 | 6.354264 | 5.419389 | 2.366400 | 12.013164 | 2.238803 | -0.171598 | 6.053121 | 773.000000 | 7 | -1.289952 | 14.656097 | -10.386386 | 30.089367 | 17.370577 | 4.399218 | 30.424578 | 12.428161 | -22.059231 | 29.744578 | 77.000000 | 6 | -19.217295 | 0.475820 | True |
| SIDE|ROLLING_180D|q=0.02|L=60|S=15 | 2.874312 | 1.427839 | 5.964747 | 4.606476 | 1.209732 | 10.599466 | 1.647138 | -1.680603 | 3.967795 | 721.000000 | 7 | -3.612812 | 9.027274 | -3.284893 | 13.020851 | 18.624773 | -6.371215 | 29.742885 | 1.543407 | -1.066600 | 5.840215 | 108.000000 | 6 | -10.681126 | 0.456311 | True |
| SIDE|ROLLING_180D|q=0.02|L=60|S=5 | 3.891787 | 0.227778 | 6.061700 | 7.104007 | 1.607852 | 10.571684 | 0.679566 | -1.617364 | 2.135153 | 680.000000 | 7 | -3.966355 | 6.842818 | -7.233940 | 10.312407 | 17.702739 | -6.371215 | 30.155336 | -1.357498 | -9.082112 | 1.947783 | 97.000000 | 6 | -16.031335 | 0.471751 | True |
| SIDE|ROLLING_180D|q=0.02|L=60|S=60 | 4.844541 | 1.616910 | 7.493548 | 7.795223 | 3.446002 | 9.909591 | 1.728587 | -0.191687 | 6.653144 | 695.000000 | 7 | -3.275135 | 15.619028 | -13.136035 | 19.125690 | 18.273115 | -5.600892 | 30.487098 | 6.960011 | -22.059231 | 27.647917 | 86.000000 | 6 | -22.420042 | 0.459510 | True |
| SIDE|ROLLING_180D|q=0.02|L=90|S=60 | 7.949742 | 4.094242 | 11.594425 | 14.981449 | 2.040310 | 19.300526 | 2.723996 | -0.368652 | 6.439468 | 637.000000 | 7 | -1.450017 | 10.210859 | -6.213732 | 24.072198 | 15.651583 | 0.179754 | 37.171033 | 4.262783 | -13.814719 | 19.746057 | 71.000000 | 6 | -22.324463 | 0.426396 | True |
| WGT|ROLLING_180D|q=0.01|L=120|S=45 | 10.242606 | 5.423818 | 16.147920 | 15.353239 | 9.755446 | 24.170104 | 5.607638 | 1.548151 | 11.622194 | 325.000000 | 7 | -3.077320 | 23.447474 | -1.492783 | 37.576808 | 35.109510 | 6.935561 | 55.914954 | 12.487956 | -13.164721 | 47.342708 | 38.000000 | 6 | -33.335244 | 0.375000 | True |
| WGT|ROLLING_180D|q=0.01|L=120|S=60 | 11.904248 | 5.327311 | 16.259065 | 15.763873 | 9.755446 | 24.170104 | 7.312966 | 1.221222 | 11.752849 | 320.000000 | 7 | -3.315310 | 26.201551 | 5.198803 | 42.680706 | 35.860916 | -2.779614 | 69.028029 | 11.436239 | 8.925302 | 23.572071 | 37.000000 | 7 | -22.033066 | 0.379576 | True |
| WGT|ROLLING_180D|q=0.01|L=45|S=60 | 9.820768 | 9.243312 | 16.695281 | 14.630173 | 10.668780 | 22.955755 | 6.891825 | 1.022715 | 10.000554 | 360.000000 | 7 | -1.819382 | 7.234948 | -0.729100 | 23.270485 | -6.956573 | -21.562084 | 36.359037 | 14.876537 | 6.943474 | 25.738079 | 38.000000 | 6 | -25.261304 | 0.383562 | True |
| WGT|ROLLING_180D|q=0.02|L=120|S=60 | 5.739820 | 4.474009 | 14.108909 | 12.429287 | 4.859546 | 19.442642 | 4.547393 | -0.918935 | 9.933942 | 580.000000 | 7 | -5.132680 | 15.571002 | 7.064473 | 22.553726 | 32.175031 | 10.928786 | 70.699625 | 3.691549 | -8.750987 | 10.959133 | 70.000000 | 7 | -9.845836 | 0.441143 | True |

## SELECTED_CELL

| cell_id | dev_net_median | dev_net_min | dev_net_max | dev_long_net_median | dev_long_net_min | dev_long_net_max | dev_short_net_median | dev_short_net_min | dev_short_net_max | dev_n_median | dev_positive_variants | dev_pw_ci95_lower_median | hold_b_net_median | hold_b_net_min | hold_b_net_max | hold_b_long_net_median | hold_b_long_net_min | hold_b_long_net_max | hold_b_short_net_median | hold_b_short_net_min | hold_b_short_net_max | hold_b_n_median | hold_b_positive_variants | hold_b_pw_ci95_lower_median | jaccard_v0_median | is_robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIDE|ROLLING_180D|q=0.01|L=120|S=60 | 16.651305 | 6.938793 | 20.112477 | 20.889905 | 10.682792 | 32.001301 | 12.268305 | 4.623955 | 14.371693 | 301.000000 | 7 | 2.328764 | 29.666579 | -11.194486 | 44.112900 | 53.005298 | -4.022533 | 77.071705 | 11.266992 | -18.930781 | 35.458990 | 33.000000 | 6 | -42.215847 | 0.398734 | True |

## SCREEN_64_VARIANT_NET

| cell_id | V0_DEV_net | V0_HOLD_B_net | V1_DEV_net | V1_HOLD_B_net | V2_DEV_net | V2_HOLD_B_net | V3_DEV_net | V3_HOLD_B_net | V4_DEV_net | V4_HOLD_B_net | V5_DEV_net | V5_HOLD_B_net | V6_DEV_net | V6_HOLD_B_net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREE|ROLLING_180D|q=0.02|L=120|S=45 | 10.956607 | 5.898939 | 7.379021 | 4.837120 | 5.306317 | 25.215063 | 5.589855 | 17.006744 | 10.152283 | 22.968179 | 15.122918 | 7.992016 | 16.880676 | 15.838483 |
| AGREE|ROLLING_180D|q=0.02|L=120|S=60 | 13.134547 | 4.490667 | 7.413608 | 13.456605 | 5.372127 | 10.459110 | 4.575612 | 31.068670 | 9.927197 | 27.144121 | 15.975302 | 11.296854 | 19.742787 | 23.943268 |
| AGREE|ROLLING_180D|q=0.02|L=45|S=45 | 8.435730 | 3.315527 | 8.521364 | -10.548018 | 5.218386 | 15.118254 | 6.497944 | 3.737226 | 7.763167 | 9.156162 | 10.752340 | 1.999567 | 19.878137 | -2.664600 |
| EITHER|ROLLING_180D|q=0.01|L=120|S=45 | 8.007548 | 15.686933 | 14.829017 | -0.460585 | 6.300155 | 6.428936 | 10.885090 | 22.131942 | 2.078506 | -4.274443 | 13.008619 | 6.465535 | 5.249209 | 5.682181 |
| EITHER|ROLLING_180D|q=0.01|L=120|S=60 | 8.920729 | 35.210654 | 15.141741 | 15.221564 | 6.569727 | 15.708421 | 11.823168 | 10.261165 | 0.998401 | 13.739021 | 13.715619 | 11.009228 | 7.302023 | 28.752870 |
| EITHER|ROLLING_180D|q=0.01|L=240|S=45 | 9.716834 | 4.179180 | 15.115965 | -9.059714 | 8.894651 | -7.089585 | 9.392490 | 3.394317 | 5.635805 | 3.395644 | 13.882907 | 4.874233 | 2.199865 | 3.140525 |
| EITHER|ROLLING_180D|q=0.01|L=240|S=60 | 11.484198 | 13.945550 | 14.309193 | -5.183022 | 8.089145 | 2.763635 | 10.432718 | 7.896267 | 3.727921 | -4.585227 | 14.696666 | 8.982065 | 2.593981 | 30.463184 |
| EITHER|ROLLING_180D|q=0.01|L=45|S=45 | 8.968108 | 11.974443 | 15.374346 | 4.471238 | 11.265073 | 16.406311 | 12.653306 | 13.198134 | 4.749164 | -2.693560 | 12.274880 | 20.917109 | 4.329350 | -13.242780 |
| EITHER|ROLLING_180D|q=0.02|L=120|S=60 | 4.396903 | 13.100578 | 7.568202 | 6.066723 | 7.514019 | 8.289027 | 4.894986 | 12.164627 | 2.809681 | 10.460033 | 5.820981 | 12.940153 | 7.951852 | 12.858072 |
| EITHER|ROLLING_180D|q=0.02|L=45|S=45 | 3.224657 | 5.479610 | 4.650643 | -3.981687 | 7.842320 | 3.581948 | 3.067958 | 6.974827 | 4.151842 | -2.733032 | 4.538102 | 0.932885 | 2.950757 | -18.448778 |
| REG|ROLLING_180D|q=0.01|L=45|S=45 | 11.028708 | 18.206885 | 14.341315 | 16.140096 | 13.780779 | 34.089363 | 18.717612 | 25.027053 | 10.190043 | 4.604235 | 15.543851 | 30.923054 | 8.556432 | -20.566502 |
| RESIDUAL|ROLLING_180D|q=0.01|L=45|S=5 | 9.517562 | 4.725012 | 3.458834 | 1.490970 | 4.707817 | -2.222373 | 5.671238 | 0.880186 | -0.727402 | 13.390100 | 6.859201 | 7.104049 | -0.230860 | -1.534674 |
| RESIDUAL|ROLLING_180D|q=0.01|L=45|S=60 | 11.136609 | 9.767221 | 5.270582 | 15.368716 | 5.824932 | -13.886421 | 10.509750 | 19.117146 | 5.853898 | 29.535340 | 12.369206 | 28.364883 | -1.907929 | 7.140784 |
| RESIDUAL|ROLLING_180D|q=0.02|L=120|S=5 | 4.912903 | 7.045718 | 4.921098 | 4.226289 | 4.542350 | 0.005696 | 3.811119 | 2.449983 | 3.451996 | 3.981718 | 2.804321 | 1.374803 | -0.253290 | 7.791419 |
| RESIDUAL|ROLLING_180D|q=0.02|L=45|S=60 | 6.316417 | 3.655716 | 1.680626 | 2.217860 | 6.387307 | -6.374281 | 7.520778 | -6.270286 | 4.918574 | 16.601532 | 5.049987 | 8.395255 | 1.474977 | 10.243409 |
| SIDE|ROLLING_180D|q=0.01|L=120|S=15 | 13.695581 | 11.174371 | 11.936592 | 17.424335 | 4.281368 | 23.749953 | 8.135629 | 4.437945 | 9.161672 | 15.493175 | 10.022622 | 19.577545 | 14.107589 | 13.102974 |
| SIDE|ROLLING_180D|q=0.01|L=120|S=5 | 11.768788 | 7.310959 | 10.787648 | 11.080193 | 1.947510 | 20.013906 | 4.802353 | -2.976779 | 7.658029 | 14.356925 | 5.954981 | 21.892779 | 11.597915 | 13.923174 |
| SIDE|ROLLING_180D|q=0.01|L=120|S=60 | 16.838722 | 44.112900 | 20.077158 | 9.407674 | 6.938793 | 32.467427 | 9.760222 | -11.194486 | 16.651305 | 29.666579 | 12.909649 | 36.227400 | 20.112477 | 17.225837 |
| SIDE|ROLLING_180D|q=0.01|L=15|S=15 | 6.628808 | 0.037517 | 2.766546 | 1.968054 | 3.426063 | 4.649216 | 3.904744 | 6.108806 | 2.180306 | -12.032174 | 7.898151 | -0.651338 | 2.496189 | -2.064705 |
| SIDE|ROLLING_180D|q=0.01|L=15|S=60 | 9.190345 | 8.611777 | 9.433362 | -6.842887 | 5.264282 | -0.968961 | 4.887124 | -0.273882 | 5.570619 | -4.742669 | 9.527947 | 7.691241 | 6.640909 | -6.144399 |
| SIDE|ROLLING_180D|q=0.01|L=180|S=15 | 12.250504 | 32.004435 | 8.285359 | 45.071213 | 12.872048 | 34.551750 | 9.103095 | 41.390444 | 6.853547 | 1.021867 | 12.542455 | 16.427775 | 13.232461 | 13.549488 |
| SIDE|ROLLING_180D|q=0.01|L=180|S=60 | 16.461809 | 57.154101 | 20.512902 | 40.189933 | 15.780412 | 35.307790 | 14.821757 | 35.109415 | 16.693601 | 7.866741 | 16.433125 | 26.280291 | 19.694463 | 9.565447 |
| SIDE|ROLLING_180D|q=0.01|L=240|S=15 | 18.950211 | 28.076890 | 11.564752 | 20.176430 | 15.355736 | 35.136289 | 15.007044 | 14.255696 | 14.859284 | -6.682237 | 15.241611 | 31.236233 | 13.430723 | 3.373939 |
| SIDE|ROLLING_180D|q=0.01|L=240|S=5 | 17.716670 | 23.422568 | 12.980153 | 10.011806 | 12.698162 | 25.876069 | 12.867368 | 4.782864 | 16.740840 | -6.542319 | 15.134261 | 33.854993 | 11.473031 | 6.658608 |
| SIDE|ROLLING_180D|q=0.01|L=240|S=60 | 21.847660 | 63.802472 | 21.026837 | 4.161664 | 14.351355 | 42.152804 | 17.216942 | 1.358248 | 21.630259 | 2.237108 | 19.297439 | 53.840671 | 17.570855 | -9.475087 |
| SIDE|ROLLING_180D|q=0.01|L=30|S=15 | 6.530450 | 18.403115 | 4.097962 | 19.414510 | 7.873200 | 22.716856 | 9.050564 | 14.754796 | 9.162817 | -6.698272 | 7.940016 | 2.755650 | 3.892279 | -2.828025 |
| SIDE|ROLLING_180D|q=0.01|L=30|S=60 | 9.090331 | 31.845361 | 10.228991 | 4.085504 | 9.478009 | 24.075841 | 10.523705 | 3.807096 | 14.112857 | 2.170953 | 9.518770 | 12.062056 | 8.613064 | -7.236039 |
| SIDE|ROLLING_180D|q=0.01|L=5|S=60 | 6.556626 | 13.587834 | 4.708355 | -9.526279 | 3.368924 | -0.518236 | 2.840074 | 0.979696 | 6.887887 | -1.797329 | 1.686827 | 10.592755 | 4.871973 | -6.734810 |
| SIDE|ROLLING_180D|q=0.01|L=60|S=15 | 11.851593 | 12.308952 | 6.102932 | 10.128917 | 7.174007 | 17.606725 | 11.423355 | 23.964410 | 3.692746 | 8.147374 | 8.054088 | 5.532592 | 6.456167 | -3.391891 |
| SIDE|ROLLING_180D|q=0.01|L=60|S=5 | 10.134183 | 9.769075 | 4.387420 | 3.419571 | 7.084717 | 11.848216 | 9.736126 | 18.812393 | 1.875107 | 10.242293 | 5.929212 | 6.760074 | 6.522040 | -3.526396 |
| SIDE|ROLLING_180D|q=0.01|L=60|S=60 | 14.667501 | 24.284864 | 12.921423 | -3.099700 | 9.225407 | 19.124655 | 13.654297 | 14.529009 | 9.577908 | 20.501510 | 10.219033 | 12.995122 | 14.221839 | -7.403832 |
| SIDE|ROLLING_180D|q=0.01|L=90|S=15 | 18.114208 | 0.118213 | 15.385816 | -4.038410 | 18.082580 | 5.907580 | 15.605453 | 14.546516 | 16.361546 | -18.841402 | 15.213472 | 4.746093 | 7.491221 | -4.688255 |
| SIDE|ROLLING_180D|q=0.01|L=90|S=60 | 20.796395 | 29.261163 | 21.222901 | -18.743311 | 18.881681 | 8.560226 | 17.869909 | 1.898672 | 20.610260 | -5.917153 | 17.089190 | 11.588224 | 12.792908 | -9.768447 |
| SIDE|ROLLING_180D|q=0.02|L=120|S=15 | 8.396173 | 7.073747 | 6.171814 | 7.052922 | 1.507249 | 7.073301 | 9.868229 | -3.294356 | 3.725287 | 3.084122 | 6.973835 | 2.376630 | 7.436167 | -1.603045 |
| SIDE|ROLLING_180D|q=0.02|L=120|S=5 | 6.963785 | 2.339330 | 4.422693 | 4.850456 | 1.413715 | 5.970382 | 6.361761 | -3.859649 | 1.747503 | -3.378352 | 6.439875 | -0.862846 | 6.964926 | -2.880881 |
| SIDE|ROLLING_180D|q=0.02|L=120|S=60 | 10.670085 | 18.324434 | 9.362932 | 8.606326 | 3.007550 | 32.812850 | 9.560564 | 10.139434 | 4.846228 | -0.033788 | 7.614632 | 17.364298 | 11.376606 | -5.422750 |
| SIDE|ROLLING_180D|q=0.02|L=15|S=60 | 3.333907 | 1.141616 | -0.945574 | -3.757645 | 1.483086 | 9.768577 | 2.708396 | 8.393408 | 0.903904 | -3.401187 | 0.906261 | 1.950363 | 3.204974 | -9.202581 |
| SIDE|ROLLING_180D|q=0.02|L=180|S=15 | 8.504082 | 23.882432 | 9.194818 | 12.329220 | 5.742602 | 15.317479 | 10.135354 | 21.255458 | 9.282319 | -3.555235 | 4.892337 | 20.637255 | 5.988945 | 7.020829 |
| SIDE|ROLLING_180D|q=0.02|L=180|S=5 | 6.408261 | 21.130379 | 9.224699 | 9.904621 | 4.101615 | 9.615911 | 4.985738 | 17.908944 | 6.772903 | -9.667514 | 5.288184 | 15.707783 | 5.631905 | 6.885098 |
| SIDE|ROLLING_180D|q=0.02|L=180|S=60 | 10.453494 | 32.651118 | 10.916812 | 20.031823 | 7.998295 | 34.983093 | 8.823433 | 31.605726 | 10.848223 | -4.282531 | 6.126966 | 37.975492 | 11.764783 | 6.298856 |
| SIDE|ROLLING_180D|q=0.02|L=240|S=15 | 14.476535 | 4.792062 | 11.467326 | 9.130973 | 10.416262 | 3.153887 | 9.423617 | 9.505757 | 12.813973 | -8.435363 | 10.137986 | 11.395120 | 3.719222 | -14.555461 |
| SIDE|ROLLING_180D|q=0.02|L=240|S=5 | 14.378698 | 0.230857 | 12.102309 | 4.801506 | 10.444069 | 0.456726 | 7.100771 | 4.183335 | 10.618992 | -12.934561 | 11.183335 | 8.280640 | 3.490638 | -20.570061 |
| SIDE|ROLLING_180D|q=0.02|L=240|S=60 | 18.483029 | 6.989274 | 11.804596 | 9.693858 | 11.419792 | 19.363942 | 9.779407 | 18.757376 | 12.725169 | -15.193061 | 10.349877 | 35.299720 | 7.179392 | -43.118227 |
| SIDE|ROLLING_180D|q=0.02|L=30|S=15 | 4.598463 | 11.755818 | 2.333830 | 9.343080 | 3.605147 | 15.214949 | 6.687796 | 12.915770 | 4.762383 | 3.630999 | 6.619472 | 6.229476 | 1.424441 | -0.048770 |
| SIDE|ROLLING_180D|q=0.02|L=30|S=5 | 3.799421 | 8.835243 | 2.208905 | 1.685609 | 3.407977 | 12.255029 | 4.671615 | 6.507589 | 2.981667 | -2.402527 | 6.049446 | 2.614681 | 1.970040 | -1.096505 |
| SIDE|ROLLING_180D|q=0.02|L=30|S=60 | 5.381770 | 20.159911 | 2.715133 | 8.535930 | 3.943431 | 30.089367 | 5.870279 | 18.387815 | 5.218040 | 5.729693 | 6.354264 | 14.656097 | 3.770797 | -10.386386 |
| SIDE|ROLLING_180D|q=0.02|L=5|S=15 | 2.809378 | 2.809709 | -1.409867 | 2.432445 | -0.572152 | 2.123584 | 0.669202 | 3.965469 | 0.115747 | 0.421993 | -0.254067 | 0.947500 | 0.674897 | -0.499592 |
| SIDE|ROLLING_180D|q=0.02|L=5|S=60 | 4.197050 | 7.221977 | -1.867579 | -1.781314 | 0.344200 | 9.231800 | -0.330954 | 3.844093 | 0.522637 | 0.756476 | -0.711920 | 6.747234 | 3.430999 | -10.041644 |
| SIDE|ROLLING_180D|q=0.02|L=60|S=15 | 4.249170 | 5.370524 | 2.874312 | 9.027274 | 5.964747 | 7.344690 | 4.946446 | 13.020851 | 2.762075 | 12.804780 | 1.427839 | 9.660804 | 1.462936 | -3.284893 |
| SIDE|ROLLING_180D|q=0.02|L=60|S=5 | 5.472749 | 4.521023 | 3.891787 | 7.549155 | 6.061700 | 6.842818 | 2.050223 | 10.312407 | 0.227778 | 8.830636 | 1.161247 | 6.839117 | 4.790618 | -7.233940 |
| SIDE|ROLLING_180D|q=0.02|L=60|S=60 | 6.421426 | 12.909829 | 3.649850 | 10.594556 | 5.771936 | 19.125690 | 4.539657 | 15.619028 | 4.844541 | 16.664644 | 1.616910 | 16.735815 | 7.493548 | -13.136035 |
| SIDE|ROLLING_180D|q=0.02|L=90|S=15 | 9.743418 | 2.094981 | 7.036539 | 5.997667 | 6.061030 | 5.044602 | 9.779841 | 9.503668 | 7.248072 | -5.219792 | 8.260842 | 8.576164 | -0.182893 | -1.584916 |
| SIDE|ROLLING_180D|q=0.02|L=90|S=60 | 11.594425 | 18.063396 | 6.529434 | 11.133577 | 8.172098 | 10.210859 | 10.021840 | 24.072198 | 6.308114 | 0.015118 | 7.949742 | 7.626192 | 4.094242 | -6.213732 |
| WGT|ROLLING_180D|q=0.01|L=120|S=45 | 10.242606 | 27.109473 | 16.147920 | -1.492783 | 5.423818 | 17.960809 | 13.076382 | 23.737155 | 9.437872 | 9.816418 | 12.533504 | 23.447474 | 9.393697 | 37.576808 |
| WGT|ROLLING_180D|q=0.01|L=120|S=60 | 10.892288 | 26.201551 | 16.259065 | 8.277435 | 5.327311 | 17.350395 | 14.964682 | 28.993620 | 10.943229 | 5.198803 | 12.212464 | 31.479859 | 11.904248 | 42.680706 |
| WGT|ROLLING_180D|q=0.01|L=240|S=45 | 13.087999 | 9.098983 | 18.392481 | -9.760100 | 10.551646 | -1.805765 | 9.636984 | 30.573930 | 14.631965 | -10.117743 | 15.914300 | 11.262794 | 8.673546 | 16.476067 |
| WGT|ROLLING_180D|q=0.01|L=240|S=60 | 13.784821 | 14.073178 | 18.662262 | -1.390060 | 10.025807 | -3.905995 | 11.689070 | 34.548317 | 16.381638 | -1.661877 | 15.285911 | 17.930319 | 9.870617 | 28.999526 |
| WGT|ROLLING_180D|q=0.01|L=45|S=45 | 9.385520 | 17.088556 | 16.431997 | -9.430124 | 9.266980 | 5.510636 | 11.727905 | 14.784681 | 8.932177 | -2.182898 | 9.769347 | 19.388289 | 7.786736 | 18.443711 |
| WGT|ROLLING_180D|q=0.01|L=45|S=60 | 10.219052 | 7.234948 | 16.695281 | -0.729100 | 9.243312 | 4.596560 | 13.504909 | 19.243594 | 9.820768 | 1.039693 | 9.451264 | 23.270485 | 9.593066 | 19.388520 |
| WGT|ROLLING_180D|q=0.02|L=120|S=60 | 5.297470 | 22.553726 | 9.364783 | 17.008365 | 5.438854 | 7.064473 | 4.474009 | 15.571002 | 5.739820 | 8.152116 | 7.347488 | 14.614637 | 14.108909 | 18.501884 |
| WGT|ROLLING_180D|q=0.02|L=240|S=45 | 6.312201 | 12.996157 | 8.068880 | 7.641255 | 10.451673 | -5.738106 | 8.592260 | 8.361510 | 8.737684 | -6.215110 | 9.702931 | -0.728707 | 10.941046 | 0.052532 |
| WGT|ROLLING_180D|q=0.02|L=240|S=60 | 8.307350 | 10.052738 | 7.924964 | 19.937486 | 9.753778 | -3.543716 | 7.650557 | 13.375775 | 9.189464 | -3.430555 | 9.880587 | 21.742296 | 13.391509 | -2.732180 |
| WGT|ROLLING_180D|q=0.02|L=45|S=45 | 3.957827 | 8.306978 | 7.469821 | -6.497753 | 6.343133 | 4.117993 | 3.244132 | 1.069214 | 6.107035 | 4.069277 | 5.994709 | -5.185888 | 6.745464 | 6.584530 |
| WGT|ROLLING_180D|q=0.02|L=45|S=60 | 5.585303 | 6.109046 | 7.560404 | 1.138446 | 6.132570 | -3.359909 | 2.788162 | 7.025292 | 6.132803 | 4.888821 | 6.468884 | 1.265907 | 9.581917 | -0.841398 |

## COUNTS

| cells | variants | screen_cells | robust_cells | selected_cells |
|---|---|---|---|---|
| 516 | 7 | 64 | 28 | 1 |

## BONFERRONI_516

| variant | segment | finite_p | p_bonferroni_lt_005 | p_bonferroni_min |
|---|---|---|---|---|
| V0 | DEV | 403 | 0 | 0.619169 |
| V0 | HOLD_B | 361 | 0 | 1.000000 |
| V1 | DEV | 396 | 0 | 0.283786 |
| V1 | HOLD_B | 320 | 0 | 1.000000 |
| V2 | DEV | 402 | 0 | 0.619169 |
| V2 | HOLD_B | 347 | 0 | 1.000000 |
| V3 | DEV | 403 | 0 | 1.000000 |
| V3 | HOLD_B | 335 | 0 | 1.000000 |
| V4 | DEV | 419 | 0 | 0.386981 |
| V4 | HOLD_B | 288 | 0 | 1.000000 |
| V5 | DEV | 411 | 0 | 1.000000 |
| V5 | HOLD_B | 337 | 0 | 1.000000 |
| V6 | DEV | 403 | 0 | 1.000000 |
| V6 | HOLD_B | 330 | 0 | 1.000000 |

## UTC

| started | finished | cutoff |
|---|---|---|
| 2026-10-02T02:25:58.036355+00:00 | 2026-10-02T15:13:34.192809+00:00 | 2026-06-30T23:59:00+00:00 |

## ALL_CELL_SUMMARY

| cell_id | dev_net_median | dev_net_min | dev_net_max | dev_long_net_median | dev_long_net_min | dev_long_net_max | dev_short_net_median | dev_short_net_min | dev_short_net_max | dev_n_median | dev_positive_variants | dev_pw_ci95_lower_median | hold_b_net_median | hold_b_net_min | hold_b_net_max | hold_b_long_net_median | hold_b_long_net_min | hold_b_long_net_max | hold_b_short_net_median | hold_b_short_net_min | hold_b_short_net_max | hold_b_n_median | hold_b_positive_variants | hold_b_pw_ci95_lower_median | jaccard_v0_median | is_robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=15 | 80.525298 | 56.117758 | 117.133550 | 120.106822 | 85.703966 | 192.661173 | 3.842116 | -9.432710 | 38.235952 | 22.000000 | 7 | -11.137659 | 115.790757 | -190.776665 | 255.677186 | 255.677186 | -190.776665 | 255.677186 | 26.467474 | -2.248088 | 55.183036 | 2.000000 | 5 | -351.065518 | 0.484848 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=45 | 87.814850 | 61.993177 | 124.870106 | 120.106822 | 85.703966 | 192.661173 | 14.571600 | -7.030814 | 79.941947 | 22.000000 | 7 | -4.429442 | 181.379609 | -190.776665 | 255.677186 | 255.677186 | -190.776665 | 255.677186 | 134.465954 | 16.982316 | 251.949591 | 2.000000 | 5 | -351.065518 | 0.500000 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=120|S=60 | 93.228603 | 68.261407 | 128.975905 | 120.106822 | 85.703966 | 192.661173 | 43.892765 | -1.409859 | 108.516910 | 22.000000 | 7 | -0.241567 | 255.677186 | -190.776665 | 315.169045 | 255.677186 | -190.776665 | 255.677186 | 346.650242 | 39.982585 | 653.317900 | 2.000000 | 5 | -351.065518 | 0.500000 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=240|S=15 | 65.455143 | -0.925765 | 90.402382 | 87.661467 | 0.384322 | 159.650594 | 3.842116 | -9.432710 | 38.235952 | 20.000000 | 6 | -63.559339 | 9.819774 | -639.073178 | 14.329960 | 9.819774 | -639.073178 | 9.819774 | 17.336751 | 17.336751 | 17.336751 | 2.000000 | 4 | -309.716815 | 0.433333 | False |
| AGREE|EXPANDING_OOS|q=0.01|L=240|S=45 | 65.893537 | 5.788999 | 97.476699 | 87.661467 | 0.384322 | 159.650594 | 14.571600 | -7.030814 | 79.941947 | 20.000000 | 7 | -39.309194 | 1.480304 | -639.073178 | 9.819774 | 9.819774 | -639.073178 | 9.819774 | -4.079342 | -4.079342 | -4.079342 | 2.000000 | 4 | -309.716815 | 0.448276 | False |

## k45_hold_a_data_r2_26_20261004

- 테스트 재실행 `tests/test_k45_hold_a_data_r2_26.py`: `4 passed in 0.58s`
### manifest 필드

| 필드 | 값 |
|---|---|
| generated_at_utc | 2026-10-04T13:46:14.846527+00:00 |
| data_cutoff_utc | 2026-09-30T23:59:00+00:00 |
| hold_start_utc | 2026-07-01T00:00:00+00:00 |
| hold_end_utc | 2026-09-30T23:59:00+00:00 |
| warmup_start_utc | 2020-01-01T00:00:00+00:00 |
| warmup_source | artifacts/btcusdt_2020_2026h1.parquet |
| reference_features | artifacts/short_quantile_sweep_20260826/feature_cache/0fc9086b7d4b4c43c8b84f6f/feature_rows.parquet |
| reference_feature_created_at_utc | 2026-08-26T04:15:25.776688+00:00 |
| reference_code_commit_candidate | e246ca62311535c8831c1fed94a1876ecccbae7a |
| code_commit | bc077b685d8e27743fe86d8ec8a21a2a24b43db4 |
| code_sha256 | {"btcusdt_quant/dataset.py": "382eb06a96731ff9d7557821987ba0b8dee3948a0ebf3c89f5eaff4ce5cdcec7", "btcusdt_quant/data.py": "ccabb236cf0e483afb7ae35bfef01d90186fa21de8fbca7f37d6c5d6aeb9ae34", "btcusdt_quant/features.py": "60117957382bb34f3e69d4234b76e241760eb28dfc6cb04151e35300a64cad35", "btcusdt_quant/feature_registry.py": "19098a70fab952e45442b38955fac0b35c922b68418c8ba5ada16ff22c30aff6", "btcusdt_quant/mtf_features.py": "58dc49890f77126216410323db83c7bc5f53e2c7499ab6566cdba16ae198d08f", "btcusdt_quant/weekly_features.py": "01ff1549a681a701f2e435d497f33746a573fb055b6f85af38595e94821d99be", "bt |
| downloads | [{"kind": "klines", "file": "artifacts/hold_a_2026q3/klines/BTCUSDT-1m-2026-07.zip", "url": "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-07.zip", "checksum_url": "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-07.zip.CHECKSUM", "downloaded_at_utc": "2026-10-01T00:00:38.240481+00:00", "checksum_downloaded_at_utc": "2026-10-01T00:00:37.959652+00:00", "sha256": "f18440bb58f0c7e1ff63cbb906132002877c4914540c8aebab920da6937cff73", "checksum_expected_sha256": "f18440bb58f0c7e1ff63cbb906132002877c4914540c8aebab920da6937cf |
| stats | {"market_rows": 132480, "feature_rows": 132480, "funding_settlements": 276, "metrics_observations": 26496, "missing": {"klines_minutes": 0, "premium_source_minutes": 0, "premium_output_minutes": 0, "metrics_aligned_minutes": 0, "funding_feature_minutes": 0}, "parity_mismatch_columns": 0, "parity_mismatch_rows_sum": 0, "feature_columns": 211, "feature_dtypes_match": true, "feature_column_order_match": true, "warmup_rows": 3417120, "boundary_finite_columns": 201, "boundary_total_feature_columns": 201, "boundary_warmup_invalid": 0, "boundary_gap_flag": 0, "unavailable_sources": ["mark_price_1m",  |
| evaluation_performed | False |
| strategy_or_model_results_computed | False |
| live_orders | 0 |
| new_orders | 0 |
| cpu_worker_cap | 6 |
| feature_cache_used | False |
| elapsed_seconds | 347.867 |

- 출력 해시 확인: 0/3 일치
  - MISSING: features_2026q3.parquet
  - MISSING: market_2026q3.parquet
  - MISSING: funding_2026q3.parquet

### REPORT.md 앞 150줄 (전체 257줄, 원문)

# R2-26 HOLD_A data

- downloads_total: 219
- checksum_verified: 219
- klines_files: 32
- metrics_files: 92
- funding_files: 3
- premium_index_files: 92
- expected_minutes: 132480
- market_rows: 132480
- feature_rows: 132480
- funding_settlements_expected: 276
- funding_settlements_actual: 276
- metrics_observations_expected: 26496
- metrics_observations_actual: 26496
- missing_klines_minutes: 0
- missing_premium_source_minutes: 0
- missing_premium_output_minutes: 0
- missing_metrics_aligned_minutes: 0
- missing_funding_feature_minutes: 0
- feature_columns: 211
- feature_dtypes_match: 1
- feature_column_order_match: 1
- warmup_rows: 3417120
- parity_tolerance: 1e-9
- parity_mismatch_columns: 0
- parity_mismatch_rows_sum: 0
- boundary_finite_columns: 201
- boundary_total_feature_columns: 201
- boundary_warmup_invalid: 0
- boundary_gap_flag: 0
- boundary_nonfinite_feature_columns: 0
- boundary_single_pass_build: 1
- unavailable_sources: 8
- fallback_features: 6
- evaluation_performed: 0
- strategy_or_model_results_computed: 0
- live_orders: 0
- new_orders: 0
- cpu_worker_cap: 6
- feature_cache_used: 0
- elapsed_seconds: 347.868

## parity_columns

column,dtype_actual,dtype_expected,max_abs_diff,mismatch_rows,rule
index,int64,int64,0.0,0,exact
open_time,"datetime64[us, UTC]","datetime64[us, UTC]",0.0,0,exact
gap_flag,int64,int64,0.0,0,exact
repaired,bool,bool,0.0,0,exact
warmup_invalid,bool,bool,0.0,0,exact
user_regime,object,object,0.0,0,exact
source_availability_status_json,object,object,0.0,0,exact
feature_availability_status_json,object,object,0.0,0,exact
unavailable_sources_json,object,object,0.0,0,exact
fallback_features_json,object,object,0.0,0,exact
adl_indicator,float64,float64,0.0,0,abs<=1e-9
adx_15m,float64,float64,0.0,0,abs<=1e-9
adx_1h,float64,float64,0.0,0,abs<=1e-9
adx_45m,float64,float64,0.0,0,abs<=1e-9
adx_4h,float64,float64,0.0,0,abs<=1e-9
atr_pct,float64,float64,0.0,0,abs<=1e-9
atr_pct_15m,float64,float64,0.0,0,abs<=1e-9
atr_pct_1h,float64,float64,0.0,0,abs<=1e-9
atr_pct_30,float64,float64,0.0,0,abs<=1e-9
atr_pct_45,float64,float64,0.0,0,abs<=1e-9
atr_pct_45m,float64,float64,0.0,0,abs<=1e-9
atr_pct_4h,float64,float64,0.0,0,abs<=1e-9
bb_percent_b,float64,float64,0.0,0,abs<=1e-9
bb_width_15m,float64,float64,0.0,0,abs<=1e-9
bb_width_1h,float64,float64,0.0,0,abs<=1e-9
bb_width_20,float64,float64,0.0,0,abs<=1e-9
bb_width_45m,float64,float64,0.0,0,abs<=1e-9
bb_width_4h,float64,float64,0.0,0,abs<=1e-9
bb_zscore,float64,float64,0.0,0,abs<=1e-9
body_pct,float64,float64,0.0,0,abs<=1e-9
body_pct_vol_adj,float64,float64,0.0,0,abs<=1e-9
body_to_range,float64,float64,0.0,0,abs<=1e-9
candle_range_vol_adj,float64,float64,0.0,0,abs<=1e-9
canonical_gap_pressure,float64,float64,0.0,0,abs<=1e-9
close_back_inside_range,float64,float64,0.0,0,abs<=1e-9
close_ema_12_ratio,float64,float64,0.0,0,abs<=1e-9
close_ema_26_ratio,float64,float64,0.0,0,abs<=1e-9
close_location_value,float64,float64,0.0,0,abs<=1e-9
close_sma_10_ratio,float64,float64,0.0,0,abs<=1e-9
close_sma_20_ratio,float64,float64,0.0,0,abs<=1e-9
close_sma_5_ratio,float64,float64,0.0,0,abs<=1e-9
close_sma_60_ratio,float64,float64,0.0,0,abs<=1e-9
close_vs_weekly_ma20,float64,float64,0.0,0,abs<=1e-9
close_vs_weekly_ma50,float64,float64,0.0,0,abs<=1e-9
close_zscore_20,float64,float64,0.0,0,abs<=1e-9
close_zscore_20_vol_adj,float64,float64,0.0,0,abs<=1e-9
close_zscore_60,float64,float64,0.0,0,abs<=1e-9
close_zscore_60_vol_adj,float64,float64,0.0,0,abs<=1e-9
day_of_week,float64,float64,0.0,0,abs<=1e-9
distance_from_24h_high,float64,float64,0.0,0,abs<=1e-9
distance_from_24h_low,float64,float64,0.0,0,abs<=1e-9
distance_to_high_20,float64,float64,0.0,0,abs<=1e-9
distance_to_low_20,float64,float64,0.0,0,abs<=1e-9
distance_to_range_high,float64,float64,0.0,0,abs<=1e-9
distance_to_range_low,float64,float64,0.0,0,abs<=1e-9
drawdown_from_24h_high,float64,float64,0.0,0,abs<=1e-9
ema_12_26_spread,float64,float64,0.0,0,abs<=1e-9
ema_20_slope,float64,float64,0.0,0,abs<=1e-9
ema_5_slope,float64,float64,0.0,0,abs<=1e-9
ema_60_slope,float64,float64,0.0,0,abs<=1e-9
ema_gap_15m,float64,float64,0.0,0,abs<=1e-9
ema_gap_1h,float64,float64,0.0,0,abs<=1e-9
ema_gap_45m,float64,float64,0.0,0,abs<=1e-9
ema_gap_4h,float64,float64,0.0,0,abs<=1e-9
ema_spread_vol_adj,float64,float64,0.0,0,abs<=1e-9
fake_break_high,float64,float64,0.0,0,abs<=1e-9
fake_break_low,float64,float64,0.0,0,abs<=1e-9
funding_blackout_active,float64,float64,0.0,0,abs<=1e-9
funding_rate,float64,float64,0.0,0,abs<=1e-9
feature__gap_flag,float64,float64,0.0,0,abs<=1e-9
gap_length,float64,float64,0.0,0,abs<=1e-9
gap_ratio_120,float64,float64,0.0,0,abs<=1e-9
gap_ratio_20,float64,float64,0.0,0,abs<=1e-9
gap_ratio_60,float64,float64,0.0,0,abs<=1e-9
garman_klass_vol_20,float64,float64,0.0,0,abs<=1e-9
global_ls_account,float64,float64,0.0,0,abs<=1e-9
global_ls_account_change_15m,float64,float64,0.0,0,abs<=1e-9
global_ls_account_change_30m,float64,float64,0.0,0,abs<=1e-9
global_ls_account_change_45m,float64,float64,0.0,0,abs<=1e-9
global_ls_account_change_5m,float64,float64,0.0,0,abs<=1e-9
global_ls_account_change_60m,float64,float64,0.0,0,abs<=1e-9
global_ls_account_taker_ls_ratio_gap,float64,float64,0.0,0,abs<=1e-9
har_rv_long,float64,float64,0.0,0,abs<=1e-9
har_rv_medium,float64,float64,0.0,0,abs<=1e-9
har_rv_short,float64,float64,0.0,0,abs<=1e-9
high_low_range,float64,float64,0.0,0,abs<=1e-9
hour,float64,float64,0.0,0,abs<=1e-9
inside_bar_flag,float64,float64,0.0,0,abs<=1e-9
leverage_bracket_utilization,float64,float64,0.0,0,abs<=1e-9
log_return_1,float64,float64,0.0,0,abs<=1e-9
log_return_5,float64,float64,0.0,0,abs<=1e-9
lower_shadow,float64,float64,0.0,0,abs<=1e-9
ma_slope_15m,float64,float64,0.0,0,abs<=1e-9
ma_slope_1h,float64,float64,0.0,0,abs<=1e-9
ma_slope_45m,float64,float64,0.0,0,abs<=1e-9
ma_slope_4h,float64,float64,0.0,0,abs<=1e-9
mark_price_basis,float64,float64,0.0,0,abs<=1e-9
max_gap_run_120,float64,float64,0.0,0,abs<=1e-9
minute,float64,float64,0.0,0,abs<=1e-9
minutes_to_next_funding,float64,float64,0.0,0,abs<=1e-9
momentum_10,float64,float64,0.0,0,abs<=1e-9
momentum_10_vol_adj,float64,float64,0.0,0,abs<=1e-9
momentum_30,float64,float64,0.0,0,abs<=1e-9
momentum_30_vol_adj,float64,float64,0.0,0,abs<=1e-9

## k45_hold_a_eval_build_r2_27_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp_utc | 2026-10-05T02:50:00+00:00 |
| data_cutoff | 2026-06-30T23:59Z |
| frozen_hypothesis | H-A1: at round-trip cost 4 bps, H3(C1 FIRST) total_net_bps > 0 under both PESS and OPT |
| status | BLOCKED_PRE_HOLD_A |
| hold_a_values_computed | 0 |
| downloads | 0 |
| live_orders | 0 |
| commits | 0 |
| selfcheck | {"status": "FAIL", "passed": ["A", "B", "D-R2-20", "E"], "failed": ["C", "D-R2-9b"], "sha256": "c5363a1ca305c37b42631b66d8b94cfe309baf3592da97315d644947c366ed81"} |
| tests | {"command": "venv_btcusdt\\Scripts\\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_27", "result": "14 passed in 4.19s"} |

### out_of_sample_result (원문)

```text
"NO_VERDICT_NOT_EXECUTED"
```

- 출력 해시 확인: 2/5 일치
  - CHANGED: out/run_k45_hold_a_eval_r2_27.py
  - CHANGED: tests/test_k45_hold_a_eval_r2_27.py
  - CHANGED: out/k45_hold_a_eval_build_r2_27_20261005/selfcheck.json

### REPORT.md 앞 71줄 (전체 71줄, 원문)

# R2-27 HOLD_A 평가 러너 제작 보고서

| 재현 검사 | 기준 | exact | 일치 행 수 | 최대 절대 차이 | 판정 |
|---|---|---:|---:|---:|---|
| A | H1/H2/F3-w30 거래, R2-23, PESS/OPT | 예 | 8,624 | 0 | PASS |
| B | C1/C3/C4 FIRST accepted trades + DEV_COMMON, R2-24, PESS/OPT | 예 | 11,162 | 0 | PASS |
| C | 실제 게이트 출처 PatchTST fold 666, CPU | 아니오 | 764 | 0.003284454345703125 | FAIL |
| D-1 | R2-9b V0 LONG120/SHORT60 fold 666 | 아니오 | 50 | 0.03203921459891157 | FAIL |
| D-2 | R2-20 4h_h480 fold 666 | 예 | 10 | 0 | PASS |
| E | 원 모델 점수 2026 H1 존재 여부 | 예 | 81,674 | 0 | PASS |

**최종 상태: `NO_VERDICT`, `execution_ready=false`.** C와 D-1이 exact가 아니므로 고정 문서 7절에 따라 HOLD_A 예측·평가는 시작할 수 없다. 이번 작업에서 HOLD_A 예측·신호·성과·라벨·수익률은 계산하지 않았다(`hold_a_values_computed=0`).

## 재현 근거

- C seed 예측 최대 차이 `0.003284454345703125`, 실제 게이트 ensemble 최대 차이 `0.001636505126953125`. R2-9b/R2-20이 사용한 실제 후기 게이트는 `out/k45_defect_audit_20260930/run_audit.py:29`의 `ensemble_predictions.parquet`다. 사용자 지시의 `predictions.parquet`는 seed별 파일이라 실제 게이트 출처가 아니다.
- D-1은 계약상 8스레드로 재학습했다. 원 R2-9b V0 출력은 `out/run_k45_gate_direction_r2_9b.py:159-175`에서 R2-10b를 재사용하고, 그 학습 파라미터는 `out/run_k45_gate_direction_r2.py:42-50`의 `thread_count=-1`이다.
- D-2는 원 설정 `thread_count=6`(`out/run_k45_mtf_entry_r2_12.py:40-42`)으로 재계산해 exact였다.
- E 점수 범위는 PatchTST `2026-01-01 00:00`–`2026-06-30 23:30`, R2-9b LONG/SHORT `2021-03-09 00:00`–`2026-06-30 15:45`, R2-20 `2021-06-28 00:00`–`2026-06-30 12:00` UTC다. 따라서 HOLD_B 점수 생성은 필요 없고 실행하지 않았다.
- 전체 기계 판독 결과: `selfcheck.json` SHA256 `c5363a1ca305c37b42631b66d8b94cfe309baf3592da97315d644947c366ed81`.

## 고정 문서 v2와 소스/입력 불일치

1. `freeze.md:39`는 PatchTST CPU와 fold 666 exact를 요구한다. 원 소스는 `out/run_patchtst_excursion_range.py:36`에서 `cuda if available else cpu`를 선택한다. 원 manifest는 실제 해소 장치를 기록하지 않았다. 현재 장비에서 CUDA가 사용 가능하지만 새 러너를 CPU로 강제하면 C가 exact가 아니다.
2. `freeze.md:39`는 총 thread/worker 상한 8이다. R2-9b V0의 실제 재사용 출력은 `thread_count=-1`로 만들어졌다(`out/run_k45_gate_direction_r2.py:42-50`, 재사용 경로 `out/run_k45_gate_direction_r2_9b.py:159-175`). 8스레드 재학습은 D-1과 exact가 아니다.
3. `freeze.md:33`은 원 feature universe에서 fold별 TRAIN-only 선택을 요구한다. 원 dataset 작성기는 book/liquidity/spread/trade 1분 파일을 결합한다(`out/run_k45_gate_direction_dataset.py:25-27,186-199`). Q3 feature parquet에는 `f_*` 201개는 모두 있지만 아래 `m_*` 23개가 없다. 누락 열을 제거·대체·직전값 고정하면 후보 정의가 바뀐다.
4. `freeze.md:3,43-45`는 아직 `DRAFT`이고 세 SHA256이 `[필수 기입]`이다. 이는 소스 불일치가 아니라 정상 실행 가드가 거부해야 할 미완료 상태다.

누락된 23개 열은 `input_environment_manifest.json`에 전부 기록했다.

## 결정 필요

1. **PatchTST 기준 출력**
   - 권고: HOLD_A 이전 fold 666을 CPU·현재 결정론 설정으로 새 기준 출력으로 만들고, 그 exact 결과와 새 hash를 v3에 고정한다.
   - 대안: 기존 동적 장치 출력을 기준으로 유지한다. 실제 생성 장치가 manifest에 없어 CPU 계약과 재현 증명이 성립하지 않는다.
   - 영향: 선택 전에는 C 실패로 Section 7 가드가 계속 닫힌다.
2. **R2-9b 스레드 기준**
   - 권고: `thread_count<=8`로 HOLD_A 이전 기준 출력을 다시 만들고 새 모델 정체성·hash를 고정한다.
   - 대안: selfcheck에만 `thread_count=-1` 예외를 둔다. 전역 8스레드 계약을 위반하므로 현 v2와 양립하지 않는다.
   - 영향: CatBoost 확률과 tail 통과가 달라질 수 있다.
3. **Q3 미시구조 23개 입력**
   - 권고: 원 작성식과 동일한 Q3 book/liquidity/spread/trade 1분 입력을 별도 사전 작업으로 준비한다. 이번 작업의 새 다운로드 금지 때문에 생성하지 않았다.
   - 대안: `m_*`를 feature universe에서 제거하고 과거 기준 출력부터 다시 만든다. 이는 R2-9b V0가 아닌 새 후보이므로 새 freeze가 필요하다.
   - 영향: 현 입력만으로는 fold별 TRAIN-only 선택을 source-exact하게 수행할 수 없다.
4. 위 세 항목을 해결한 뒤 러너의 차단 manifest를 새 증거로 교체하고 `predict/evaluate` 운영 경로를 다시 검토·해시해야 한다. 현재 파일은 fail-closed 제작본이며 실행 승인본이 아니다.

## 제작물과 안전장치

- 러너: `out/run_k45_hold_a_eval_r2_27.py`
  - SHA256 `1d59c1463999fe4c44225d91af218d919a64863c76551fe87bc6e68176b3d8dd`
  - `selfcheck/predict/evaluate` 하위명령, DRAFT·문서 hash·닫힌 예측 manifest hash·실행준비 manifest 가드.
  - fold 667–697 일정, strict purge, CPU 결정론/최대 8스레드, 예측 schema whitelist, FIRST, carry-in/강제청산, 모델 fold 경계, funding 결합, 가설 판정 함수.
  - 우선순위는 `manifest_frozen.json`을 문자 그대로 읽으며 재순위화하지 않는다.
  - `predict/evaluate`는 `execution_ready=false`에서 HOLD_A parquet 값을 열기 전에 종료한다.
- 테스트: `tests/test_k45_hold_a_eval_r2_27.py`
  - SHA256 `a233b68cd4eb2362a540f25da304b3b13706888a57f05466f21c11445efa7745`
  - 명령: `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_27`
  - 결과: `14 passed in 4.19s`.
- 입력/환경 manifest: `out/k45_hold_a_eval_build_r2_27_20261005/input_environment_manifest.json`
  - SHA256 `40f6f4edd8c429b77e1c96325af9fbfa4970f66ebffeeef8a08f97b851ac0f1d`
  - Python 3.14.3, numpy 1.26.4, pandas 2.3.3, pyarrow 24.0.0, torch 2.13.0+cu126, CatBoost 1.2.10, 장치 CPU, torch 8/interop 1, worker 1.

## HOLD_A 파일 메타데이터만 확인

| 파일 | 행 | 열 | SHA256 |
|---|---:|---:|---|
| market_2026q3.parquet | 132,480 | 11 | `e61830c177e54073c8d6e7ea18bff2a3f25db0b8c6057e1db01fa240eecd1bb5` |
| features_2026q3.parquet | 132,480 | 211 | `d68c25520c8a8396e0b03a79c8d2708b4ea358cf8ba1e9b79a9e9c91a56d4d98` |
| funding_2026q3.parquet | 276 | 2 | `a28f30fd367847fba25a45db3b284567bc2b4b6e418ba8be7479233c491d65b7` |

펀딩 wrapper는 기존 7,119행과 Q3 276행을 합쳐 7,395행을 만들고, PESS/OPT 경계 현금흐름 의미를 합성 테스트로 확인했다. 문서 파일은 수정하지 않았고, commit·다운로드·실주문·인증 작업은 하지 않았다.

## k45_hold_a_exclude_bookticker_r2_32_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp | 2026-10-05T10:45:12.856082+00:00 |
| data_cutoff | 2026-06-30T23:59Z |
| frozen_hypothesis | docs/hold_a/2026-10-05_hold_a_freeze.md section 4 (DRAFT, unfrozen) |
| freeze_status | DRAFT |
| freeze_guard_bypassed | True |
| freeze_guard_bypass_reason | user decision 2026-10-05 |
| hold_a_values_computed | 1 |
| bookticker_excluded_features | ["m_quote_update_count", "m_spread_bps_max", "m_spread_bps_mean", "m_spread_bps_std", "m_spread_valid", "m_top_imbalance_mean"] |
| cpu_workers_max | 8 |
| r2_9b_catboost_thread_count | -1 |
| tests | {"result": "35 passed in 5.41s"} |

### out_of_sample_result (원문)

```text
[
 {
  "hypothesis": "H-A1",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 },
 {
  "hypothesis": "H-A2",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 },
 {
  "hypothesis": "H-A3",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 },
 {
  "hypothesis": "H-A4",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 },
 {
  "hypothesis": "H-A5a",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 },
 {
  "hypothesis": "H-A5b",
  "PESS": true,
  "OPT": true,
  "verdict": "CONFIRMED"
 }
]
```

- 출력 해시 확인: 6/6 일치

### REPORT.md 앞 150줄 (전체 2489줄, 원문)

# R2-32

## (a) fold 비교

| arm | horizon | selection_exact_folds | score_exact_folds | total_folds | changed_first_fold | changed_last_fold | max_abs_score_difference | folds_347_plus_exact | folds_347_plus_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LONG | 120 | 581 | 581 | 621 | 288.000000 | 346.000000 | 0.324262 | 310 | 310 |
| SHORT | 60 | 621 | 621 | 621 | nan | nan | 0.000000 | 310 | 310 |

- LONG changed folds: `288-293, 295-325, 344-346` (40/621). SHORT changed folds: none (0/621).

- selection source: `select_features`는 `alpha=0.05/len(columns)`를 사용하므로 후보 집합 크기가 gate 통과 여부에 직접 들어간다.

## (b) R2-9b 단독·C3 원 vs 새

| series | boundary | segment | cost_bps | trade_n | exposure_ratio | total_net_bps | mtm_daily_sharpe | mtm_max_drawdown_bps | pw_status | pw_ci95_lower_daily_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-9b OLD | PESS | DEV_COMMON | 4.000000 | 292 | 0.009692 | 4913.723836 | 1.029018 | 1656.977506 | MEASURABLE | 0.402322 |
| R2-9b OLD | PESS | DEV_COMMON | 8.000000 | 292 | 0.009692 | 3745.723836 | 0.790703 | 1760.977506 | MEASURABLE | -0.214580 |
| R2-9b OLD | PESS | DEV_COMMON | 12.000000 | 292 | 0.009692 | 2577.723836 | 0.547477 | 1864.977506 | MEASURABLE | -0.721719 |
| R2-9b OLD | PESS | HOLD_B | 4.000000 | 32 | 0.009899 | 1414.909623 | 1.397614 | 709.290277 | MEASURABLE | -13.138903 |
| R2-9b OLD | PESS | HOLD_B | 8.000000 | 32 | 0.009899 | 1286.909623 | 1.297923 | 789.290277 | MEASURABLE | -13.754713 |
| R2-9b OLD | PESS | HOLD_B | 12.000000 | 32 | 0.009899 | 1158.909623 | 1.193545 | 869.290277 | MEASURABLE | -14.080043 |
| R2-9b OLD | OPT | DEV_COMMON | 4.000000 | 292 | 0.009692 | 4932.486936 | 1.033098 | 1656.803206 | MEASURABLE | 0.414262 |
| R2-9b OLD | OPT | DEV_COMMON | 8.000000 | 292 | 0.009692 | 3764.486936 | 0.794802 | 1760.803206 | MEASURABLE | -0.207119 |
| R2-9b OLD | OPT | DEV_COMMON | 12.000000 | 292 | 0.009692 | 2596.486936 | 0.551573 | 1864.803206 | MEASURABLE | -0.711465 |
| R2-9b OLD | OPT | HOLD_B | 4.000000 | 32 | 0.009899 | 1416.928923 | 1.399703 | 707.987477 | MEASURABLE | -13.119327 |
| R2-9b OLD | OPT | HOLD_B | 8.000000 | 32 | 0.009899 | 1288.928923 | 1.300061 | 787.987477 | MEASURABLE | -13.743471 |
| R2-9b OLD | OPT | HOLD_B | 12.000000 | 32 | 0.009899 | 1160.928923 | 1.195731 | 867.987477 | MEASURABLE | -14.070829 |
| R2-9b NEW | PESS | DEV_COMMON | 4.000000 | 293 | 0.009739 | 4966.040404 | 1.029857 | 1656.977506 | MEASURABLE | 0.386773 |
| R2-9b NEW | PESS | DEV_COMMON | 8.000000 | 293 | 0.009739 | 3794.040404 | 0.792889 | 1760.977506 | MEASURABLE | -0.233021 |
| R2-9b NEW | PESS | DEV_COMMON | 12.000000 | 293 | 0.009739 | 2622.040404 | 0.551175 | 1864.977506 | MEASURABLE | -0.883191 |
| R2-9b NEW | PESS | HOLD_B | 4.000000 | 32 | 0.009899 | 1414.909623 | 1.397614 | 709.290277 | MEASURABLE | -13.138903 |
| R2-9b NEW | PESS | HOLD_B | 8.000000 | 32 | 0.009899 | 1286.909623 | 1.297923 | 789.290277 | MEASURABLE | -13.754713 |
| R2-9b NEW | PESS | HOLD_B | 12.000000 | 32 | 0.009899 | 1158.909623 | 1.193545 | 869.290277 | MEASURABLE | -14.080043 |
| R2-9b NEW | OPT | DEV_COMMON | 4.000000 | 293 | 0.009739 | 4984.733704 | 1.033883 | 1656.803206 | MEASURABLE | 0.395216 |
| R2-9b NEW | OPT | DEV_COMMON | 8.000000 | 293 | 0.009739 | 3812.733704 | 0.796931 | 1760.803206 | MEASURABLE | -0.229837 |
| R2-9b NEW | OPT | DEV_COMMON | 12.000000 | 293 | 0.009739 | 2640.733704 | 0.555214 | 1864.803206 | MEASURABLE | -0.876025 |
| R2-9b NEW | OPT | HOLD_B | 4.000000 | 32 | 0.009899 | 1416.928923 | 1.399703 | 707.987477 | MEASURABLE | -13.119327 |
| R2-9b NEW | OPT | HOLD_B | 8.000000 | 32 | 0.009899 | 1288.928923 | 1.300061 | 787.987477 | MEASURABLE | -13.743471 |
| R2-9b NEW | OPT | HOLD_B | 12.000000 | 32 | 0.009899 | 1160.928923 | 1.195731 | 867.987477 | MEASURABLE | -14.070829 |
| C3 OLD | PESS | DEV_COMMON | 4.000000 | 1008 | 0.470477 | 38418.164214 | 1.815886 | 3878.594398 | MEASURABLE | 11.529307 |
| C3 OLD | PESS | DEV_COMMON | 8.000000 | 1008 | 0.470477 | 34386.164214 | 1.627021 | 4370.594398 | MEASURABLE | 8.932960 |
| C3 OLD | PESS | DEV_COMMON | 12.000000 | 1008 | 0.470477 | 30354.164214 | 1.437644 | 4862.594398 | MEASURABLE | 6.775386 |
| C3 OLD | PESS | HOLD_B | 4.000000 | 105 | 0.464779 | 3789.994498 | 1.952331 | 1338.476009 | MEASURABLE | -17.803391 |
| C3 OLD | PESS | HOLD_B | 8.000000 | 105 | 0.464779 | 3369.994498 | 1.745723 | 1450.706511 | MEASURABLE | -20.655037 |
| C3 OLD | PESS | HOLD_B | 12.000000 | 105 | 0.464779 | 2949.994498 | 1.536543 | 1627.656069 | MEASURABLE | -21.499920 |
| C3 OLD | OPT | DEV_COMMON | 4.000000 | 1008 | 0.470477 | 38811.289114 | 1.834245 | 3851.047498 | MEASURABLE | 11.772280 |
| C3 OLD | OPT | DEV_COMMON | 8.000000 | 1008 | 0.470477 | 34779.289114 | 1.645434 | 4343.047498 | MEASURABLE | 9.139449 |
| C3 OLD | OPT | DEV_COMMON | 12.000000 | 1008 | 0.470477 | 30747.289114 | 1.456108 | 4835.047498 | MEASURABLE | 6.957803 |
| C3 OLD | OPT | HOLD_B | 4.000000 | 105 | 0.464779 | 3802.369698 | 1.958736 | 1337.630809 | MEASURABLE | -17.761913 |
| C3 OLD | OPT | HOLD_B | 8.000000 | 105 | 0.464779 | 3382.369698 | 1.752164 | 1448.019454 | MEASURABLE | -20.553007 |
| C3 OLD | OPT | HOLD_B | 12.000000 | 105 | 0.464779 | 2962.369698 | 1.543019 | 1623.623969 | MEASURABLE | -21.457841 |
| C3 NEW | PESS | DEV_COMMON | 4.000000 | 1008 | 0.470477 | 38418.164214 | 1.815886 | 3878.594398 | MEASURABLE | 11.529307 |
| C3 NEW | PESS | DEV_COMMON | 8.000000 | 1008 | 0.470477 | 34386.164214 | 1.627021 | 4370.594398 | MEASURABLE | 8.932960 |
| C3 NEW | PESS | DEV_COMMON | 12.000000 | 1008 | 0.470477 | 30354.164214 | 1.437644 | 4862.594398 | MEASURABLE | 6.775386 |
| C3 NEW | PESS | HOLD_B | 4.000000 | 105 | 0.464779 | 3789.994498 | 1.952331 | 1338.476009 | MEASURABLE | -17.803391 |
| C3 NEW | PESS | HOLD_B | 8.000000 | 105 | 0.464779 | 3369.994498 | 1.745723 | 1450.706511 | MEASURABLE | -20.655037 |
| C3 NEW | PESS | HOLD_B | 12.000000 | 105 | 0.464779 | 2949.994498 | 1.536543 | 1627.656069 | MEASURABLE | -21.499920 |
| C3 NEW | OPT | DEV_COMMON | 4.000000 | 1008 | 0.470477 | 38811.289114 | 1.834245 | 3851.047498 | MEASURABLE | 11.772280 |
| C3 NEW | OPT | DEV_COMMON | 8.000000 | 1008 | 0.470477 | 34779.289114 | 1.645434 | 4343.047498 | MEASURABLE | 9.139449 |
| C3 NEW | OPT | DEV_COMMON | 12.000000 | 1008 | 0.470477 | 30747.289114 | 1.456108 | 4835.047498 | MEASURABLE | 6.957803 |
| C3 NEW | OPT | HOLD_B | 4.000000 | 105 | 0.464779 | 3802.369698 | 1.958736 | 1337.630809 | MEASURABLE | -17.761913 |
| C3 NEW | OPT | HOLD_B | 8.000000 | 105 | 0.464779 | 3382.369698 | 1.752164 | 1448.019454 | MEASURABLE | -20.553007 |
| C3 NEW | OPT | HOLD_B | 12.000000 | 105 | 0.464779 | 2962.369698 | 1.543019 | 1623.623969 | MEASURABLE | -21.457841 |

## C3 92일 rolling

| series | boundary | window_n | net_positive_ratio | trade_n_mean | trade_n_p05 | trade_n_p50 | trade_n_p95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C3 OLD | PESS | 1676 | 0.789976 | 52.625895 | 36.000000 | 53.000000 | 65.000000 |
| C3 OLD | OPT | 1676 | 0.792959 | 52.625895 | 36.000000 | 53.000000 | 65.000000 |
| C3 NEW | PESS | 1676 | 0.789976 | 52.625895 | 36.000000 | 53.000000 | 65.000000 |
| C3 NEW | OPT | 1676 | 0.792959 | 52.625895 | 36.000000 | 53.000000 | 65.000000 |

## (d) 리허설 exact

| item | generated_rows | source_rows | exact | max_abs_difference | note |
| --- | --- | --- | --- | --- | --- |
| PatchTST gate | 8801 | 8801 | 1 | 0.000000 |  |
| R2-9b LONG120 score | 1356 | 1356 | 1 | 0.000000 |  |
| R2-9b SHORT60 score | 1364 | 1364 | 1 | 0.000000 |  |
| R2-20 4h_h480 score | 490 | 490 | 1 | 0.000000 |  |
| R2-9b tail accepted | 11 | 11 | 1 | 0.000000 |  |
| R2-20 tail accepted | 8 | 8 | 1 | 0.000000 |  |
| classic F3\|1h\|10/24\|signal\|LS | 46 | 46 | 1 | 0.000000 |  |
| classic E1\|1h\|3\|signal\|L | 18 | 18 | 1 | 0.000000 |  |
| classic F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 109 | 109 | 1 | 0.000000 |  |
| FIRST H3/C1 | 51 | 51 | 1 | 0.000000 |  |
| FIRST H4/C3 | 53 | 53 | 1 | 0.000000 |  |
| FIRST H5/C4 | 115 | 115 | 1 | 0.000000 |  |

## (e) HOLD_A H1-H5·B0 × PESS/OPT × 4/8/12

| book | boundary | cost_bps | total_net_bps | trade_n | mtm_daily_sharpe | mtm_max_drawdown_bps | pw_status | pw_ci95_lower_daily_bps | gross_bps | cost_total_bps | funding_bps | long_n | short_n | carry_in_n | forced_exit_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | OPT | 4.000000 | 3382.291136 | 1 | 3.522855 | 736.592041 | MEASURABLE_BLOCK1 | -6.842681 | 3549.403236 | 4.000000 | -163.112100 | 1 | 0 | 0 | 1 |
| B0 | OPT | 8.000000 | 3378.291136 | 1 | 3.518976 | 736.592041 | MEASURABLE_BLOCK1 | -6.908359 | 3549.403236 | 8.000000 | -163.112100 | 1 | 0 | 0 | 1 |
| B0 | OPT | 12.000000 | 3374.291136 | 1 | 3.515089 | 736.592041 | MEASURABLE_BLOCK1 | -6.973033 | 3549.403236 | 12.000000 | -163.112100 | 1 | 0 | 0 | 1 |
| B0 | PESS | 4.000000 | 3381.737936 | 1 | 3.522384 | 736.592041 | MEASURABLE_BLOCK1 | -6.854708 | 3549.403236 | 4.000000 | -163.665300 | 1 | 0 | 0 | 1 |
| B0 | PESS | 8.000000 | 3377.737936 | 1 | 3.518503 | 736.592041 | MEASURABLE_BLOCK1 | -6.920235 | 3549.403236 | 8.000000 | -163.665300 | 1 | 0 | 0 | 1 |
| B0 | PESS | 12.000000 | 3373.737936 | 1 | 3.514615 | 736.592041 | MEASURABLE_BLOCK1 | -6.984909 | 3549.403236 | 12.000000 | -163.665300 | 1 | 0 | 0 | 1 |
| H1 | OPT | 4.000000 | 366.432146 | 28 | 0.561030 | 837.637879 | MEASURABLE | -27.628540 | 511.972846 | 110.000000 | -35.540700 | 21 | 7 | 1 | 0 |
| H1 | OPT | 8.000000 | 256.432146 | 28 | 0.393453 | 871.637879 | MEASURABLE | -26.980990 | 511.972846 | 220.000000 | -35.540700 | 21 | 7 | 1 | 0 |
| H1 | OPT | 12.000000 | 146.432146 | 28 | 0.225129 | 905.637879 | MEASURABLE | -28.781665 | 511.972846 | 330.000000 | -35.540700 | 21 | 7 | 1 | 0 |
| H1 | PESS | 4.000000 | 365.221046 | 28 | 0.559145 | 838.848979 | MEASURABLE | -27.644150 | 511.972846 | 110.000000 | -36.751800 | 21 | 7 | 1 | 0 |
| H1 | PESS | 8.000000 | 255.221046 | 28 | 0.391572 | 872.848979 | MEASURABLE | -26.999843 | 511.972846 | 220.000000 | -36.751800 | 21 | 7 | 1 | 0 |
| H1 | PESS | 12.000000 | 145.221046 | 28 | 0.223254 | 906.848979 | MEASURABLE | -28.920160 | 511.972846 | 330.000000 | -36.751800 | 21 | 7 | 1 | 0 |
| H2 | OPT | 4.000000 | 1506.100994 | 22 | 3.087325 | 340.959596 | MEASURABLE_BLOCK1 | -6.949435 | 1632.421694 | 88.000000 | -38.320700 | 22 | 0 | 0 | 0 |
| H2 | OPT | 8.000000 | 1418.100994 | 22 | 2.914851 | 346.959596 | MEASURABLE_BLOCK1 | -7.866503 | 1632.421694 | 176.000000 | -38.320700 | 22 | 0 | 0 | 0 |
| H2 | OPT | 12.000000 | 1330.100994 | 22 | 2.741088 | 352.959596 | MEASURABLE_BLOCK1 | -8.741680 | 1632.421694 | 264.000000 | -38.320700 | 22 | 0 | 0 | 0 |
| H2 | PESS | 4.000000 | 1503.528994 | 22 | 3.082534 | 340.959596 | MEASURABLE_BLOCK1 | -6.971601 | 1632.421694 | 88.000000 | -40.892700 | 22 | 0 | 0 | 0 |
| H2 | PESS | 8.000000 | 1415.528994 | 22 | 2.910007 | 346.959596 | MEASURABLE_BLOCK1 | -7.904902 | 1632.421694 | 176.000000 | -40.892700 | 22 | 0 | 0 | 0 |
| H2 | PESS | 12.000000 | 1327.528994 | 22 | 2.736193 | 352.959596 | MEASURABLE_BLOCK1 | -8.780445 | 1632.421694 | 264.000000 | -40.892700 | 22 | 0 | 0 | 0 |
| H3 | OPT | 4.000000 | 1377.068386 | 37 | 1.910328 | 575.311820 | MEASURABLE | -20.574761 | 1573.800686 | 146.000000 | -50.732300 | 30 | 7 | 1 | 0 |
| H3 | OPT | 8.000000 | 1231.068386 | 37 | 1.711738 | 585.311820 | MEASURABLE | -21.535324 | 1573.800686 | 292.000000 | -50.732300 | 30 | 7 | 1 | 0 |
| H3 | OPT | 12.000000 | 1085.068386 | 37 | 1.512077 | 595.311820 | MEASURABLE | -23.432871 | 1573.800686 | 438.000000 | -50.732300 | 30 | 7 | 1 | 0 |
| H3 | PESS | 4.000000 | 1376.416586 | 37 | 1.909381 | 575.311820 | MEASURABLE | -20.581669 | 1573.800686 | 146.000000 | -51.384100 | 30 | 7 | 1 | 0 |
| H3 | PESS | 8.000000 | 1230.416586 | 37 | 1.710793 | 585.311820 | MEASURABLE | -21.494852 | 1573.800686 | 292.000000 | -51.384100 | 30 | 7 | 1 | 0 |
| H3 | PESS | 12.000000 | 1084.416586 | 37 | 1.511134 | 595.311820 | MEASURABLE | -23.446863 | 1573.800686 | 438.000000 | -51.384100 | 30 | 7 | 1 | 0 |
| H4 | OPT | 4.000000 | 1398.334066 | 40 | 1.930291 | 575.311820 | MEASURABLE | -21.079125 | 1606.124166 | 158.000000 | -49.790100 | 32 | 8 | 1 | 0 |
| H4 | OPT | 8.000000 | 1240.334066 | 40 | 1.717237 | 585.311820 | MEASURABLE | -21.175051 | 1606.124166 | 316.000000 | -49.790100 | 32 | 8 | 1 | 0 |
| H4 | OPT | 12.000000 | 1082.334066 | 40 | 1.502737 | 599.850409 | MEASURABLE | -24.007895 | 1606.124166 | 474.000000 | -49.790100 | 32 | 8 | 1 | 0 |
| H4 | PESS | 4.000000 | 1397.682266 | 40 | 1.929348 | 575.311820 | MEASURABLE | -21.093295 | 1606.124166 | 158.000000 | -50.441900 | 32 | 8 | 1 | 0 |
| H4 | PESS | 8.000000 | 1239.682266 | 40 | 1.716296 | 585.311820 | MEASURABLE | -21.182313 | 1606.124166 | 316.000000 | -50.441900 | 32 | 8 | 1 | 0 |
| H4 | PESS | 12.000000 | 1081.682266 | 40 | 1.501797 | 599.850409 | MEASURABLE | -24.022240 | 1606.124166 | 474.000000 | -50.441900 | 32 | 8 | 1 | 0 |
| H5 | OPT | 4.000000 | 409.348928 | 105 | 0.532576 | 1252.783029 | MEASURABLE | -32.718040 | 876.280628 | 418.000000 | -48.931700 | 73 | 32 | 1 | 0 |
| H5 | OPT | 8.000000 | -8.651072 | 105 | -0.011255 | 1496.783029 | MEASURABLE | -35.615674 | 876.280628 | 836.000000 | -48.931700 | 73 | 32 | 1 | 0 |
| H5 | OPT | 12.000000 | -426.651072 | 105 | -0.554822 | 1740.783029 | MEASURABLE | -40.531112 | 876.280628 | 1254.000000 | -48.931700 | 73 | 32 | 1 | 0 |
| H5 | PESS | 4.000000 | 400.702128 | 105 | 0.521376 | 1257.142629 | MEASURABLE | -32.063972 | 876.280628 | 418.000000 | -57.578500 | 73 | 32 | 1 | 0 |
| H5 | PESS | 8.000000 | -17.297872 | 105 | -0.022506 | 1501.142629 | MEASURABLE | -35.672873 | 876.280628 | 836.000000 | -57.578500 | 73 | 32 | 1 | 0 |
| H5 | PESS | 12.000000 | -435.297872 | 105 | -0.566112 | 1745.142629 | MEASURABLE | -40.937696 | 876.280628 | 1254.000000 | -57.578500 | 73 | 32 | 1 | 0 |

## 문서 4절 가설 기계 판정

| hypothesis | PESS | OPT | verdict |
| --- | --- | --- | --- |
| H-A1 | 1 | 1 | CONFIRMED |
| H-A2 | 1 | 1 | CONFIRMED |
| H-A3 | 1 | 1 | CONFIRMED |
| H-A4 | 1 | 1 | CONFIRMED |
| H-A5a | 1 | 1 | CONFIRMED |
| H-A5b | 1 | 1 | CONFIRMED |

## DEV_COMMON·HOLD_B

| series | boundary | segment | cost_bps | trade_n | exposure_ratio | total_net_bps | mtm_daily_sharpe | mtm_max_drawdown_bps | pw_status | pw_ci95_lower_daily_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-9b OLD | PESS | DEV_COMMON | 4.000000 | 292 | 0.009692 | 4913.723836 | 1.029018 | 1656.977506 | MEASURABLE | 0.402322 |
| R2-9b OLD | PESS | DEV_COMMON | 8.000000 | 292 | 0.009692 | 3745.723836 | 0.790703 | 1760.977506 | MEASURABLE | -0.214580 |

## k45_hold_a_final_review_r2_31_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
- manifest 없음 (미완료 또는 실행 전).
- 파일: BRIEF.md, codex.log

## k45_hold_a_freeze_review_20261005

- manifest 없음 (미완료 또는 실행 전).
- 파일: BRIEF.md, REPORT.md, codex.log

## k45_hold_a_interpret_r2_33_20261006

### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp_utc | 2026-10-05T16:17:54.183460+00:00 |
| data_cutoff | {"DEV_COMMON": "2025-12-31T23:59:59Z", "HOLD_B": "2026-06-30T23:59:59Z", "HOLD_A": "2026-09-30T23:59:59Z"} |
| frozen_hypothesis | DRAFT v3; evaluated without FROZEN by user decision |
| hold_a_usage | post_hoc_description_and_system_nonselection_only; no tuning, candidate selection, or OOS claim |
| boundary | PESS |
| round_trip_cost_bps | 4.0 |
| downloads | 0 |
| live_orders | 0 |
| cpu_workers_max | 8 |
| tests | {"target": "32 passed in 5.71s", "full": "1133 passed, 35 subtests passed, 20 warnings in 728.07s", "basetemp": ".pytest_tmp_r2_33"} |

- 출력 해시 확인: 37/37 일치

### REPORT.md 앞 150줄 (전체 200줄, 원문)

# R2-33 HOLD_A 적대적 해석과 시스템 결정

> 기준: PESS·왕복 4bps. HOLD_A는 이미 본 구간이며 아래 해석은 전부 사후 서술이다. 새 데이터·새 검증 구간·후보 재선택 없음.

## 1–6 숫자 먼저

| 항목 | 주장 | 근거 수치 | 반대 근거 | 남는 불확실성 | 근거 |
| --- | --- | --- | --- | --- | --- |
| 1 | HOLD_A 후보 수익은 B0와 같은 방향 노출만으로 설명되지 않지만 B0를 모두 하회 | H1: β=0.42, α=-11.5bp/d, short=-672bp; H2: β=0.30, α=5.2bp/d, short=0bp; H3: β=0.54, α=-4.8bp/d, short=-672bp; H4: β=0.54, α=-4.6bp/d, short=-650bp; H5: β=0.54, α=-15.5bp/d, short=-584bp | HOLD_A β의 HAC CI가 넓고 H2는 long-only | 92일 회귀; 구조 변화·비선형 노출 미식별 | beta_hac.csv[segment=HOLD_A]; direction_exposure.csv[segment=HOLD_A] |
| 2 | C1 HOLD_A는 E1 기여에 의존; DEV에서도 E1은 양수지만 지배적이지 않음 | DEV_COMMON:E1 +4688bp; DEV_COMMON:F3 +31030bp; HOLD_B:E1 +873bp; HOLD_B:F3 +1016bp; HOLD_A:E1 +1311bp; HOLD_A:F3 +65bp | E1 단독 HOLD_A는 +1,504bp이고 국면별 DEV 성과는 이질적 | 국면 9셀 표본 작음; 30일 경계·중첩 | c1_components.csv; e1_dev_regime.csv; regime_summary.csv |
| 3 | F3 거래당 성과 약화는 관찰되나 단조 decay 단정은 금지 | DEV 42.35→HOLD_B 15.48→HOLD_A 13.04; 6m 기울기 -15.61 [-22.43,-8.79] bp/trade/year | 연도·반기 성과가 비단조 | 중첩 183일 창; HAC도 완전 독립 표본을 만들지 못함 | f3_yearly.csv; f3_halfyear.csv; f3_trend.csv |
| 4 | HOLD_A 상위 2건 제거 후 F3/C1/C3/C4 모두 음수 | H1 -863bp, DEV 양수율 49.5%, HA pctl 28.8; H3 -226bp, DEV 양수율 53.1%, HA pctl 42.6; H4 -204bp, DEV 양수율 55.5%, HA pctl 40.9; H5 -1117bp, DEV 양수율 48.9%, HA pctl 26.2 | 상위 1건만 제거하면 C1 +389bp, C3 +410bp; DEV 92일 실패 창도 흔함 | 1,676개 창 중첩; 극단 거래 정의는 사후 진단 | concentration_summary.csv |
| 5 | HOLD_A net/Sharpe 백분위는 혼재하며 5개 모두 DEV [p5,p95] 안 | H1:net p28.3, Sharpe p28.3; H2:net p81.8, Sharpe p84.7; H3:net p43.8, Sharpe p50.9; H4:net p42.4, Sharpe p50.2; H5:net p36.3, Sharpe p38.2 | 모든 HOLD_A PW 하한 음수; H1-H4 22~40건 | 중첩 창은 유효 표본 1,676개가 아님 | window_summary.csv; R2-32 hold_a/REPORT.md: numeric/PW tables |
| 6 | C4 8bps 음수와 F3-w30 손실의 DEV 이례성은 백분위로 제한 평가 | C4 8bps total net: -17bp, p36.2, DEV≤0 36.5%; C4 F3-w30 contribution 4bps: -934bp, p11.2, DEV≤0 28.2% | DEV에도 비양수 92일 창 존재 | 비용·구성요소 진단은 HOLD_A 확인 후 수행된 사후 해석 | c4_unusual.csv |

## 7. 실제 시스템 선택지

| 선택지 | DEV_n | DEV_net_bps | DEV_Sharpe | DEV_PW하한_daily_bps | HOLD_B_n | HOLD_B_net_bps | HOLD_A사후_n | HOLD_A사후_net_bps | HOLD_A사후_Sharpe | HOLD_A사후_PW하한_daily_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 859 | 35717.6832 | 1.7279 | 9.9866 | 85 | 1889.1963 | 37 | 1376.4166 | 1.9094 | -20.5817 |
| E1 단독 | 322 | 8614.3956 | 0.8332 | -0.0870 | 30 | 1445.5125 | 22 | 1503.5290 | 3.0825 | -6.9716 |
| C3 | 1008 | 38418.1642 | 1.8159 | 11.5293 | 105 | 3789.9945 | 40 | 1397.6823 | 1.9293 | -21.0933 |
| 없음 | 0 | 0.0000 | nan | nan | 0 | 0.0000 | 0 | 0.0000 | nan | nan |

| 선택지 | 근거 | 위험 |
|---|---|---|
| C1 | DEV +35,718bp, Sharpe 1.73; HOLD_A 사후 +1,376bp | HOLD_A 수익 대부분 E1; top2 제거 음수; PW 하한 음수 |
| E1 단독 | DEV +8,614bp, HOLD_A 사후 +1,504bp로 세 후보 중 HOLD_A 최고 | long-only·저빈도; DEV PW 하한 -0.09; 국면 의존 |
| C3 | DEV +38,418bp, Sharpe 1.82 | 복잡도 증가 대비 HOLD_A 사후 C1과 유사; top2 제거 음수 |
| 없음 | 추가 OOS 없음; 모든 HOLD_A 후보가 B0 +3,381.7bp 하회 | 기회비용; 연구 신호를 실거래에 반영하지 않음 |

**Codex 의견: `없음`을 실제 퀀트 시스템에 넣는다(후보는 shadow 기록만).** 이유는 추가 검증 구간이 없고, HOLD_A를 본 뒤 E1/C1/C3 중 하나를 고르면 그 선택 자체가 HOLD_A 사후 선택이 되기 때문이다. 최종 채택은 사용자 결정 사항이다.

## 상세 계산

### 1. 베타·방향

| book | segment | alpha_daily_bps | alpha_hac_se | alpha_ci95_low | alpha_ci95_high | beta | beta_hac_se | beta_ci95_low | beta_ci95_high | r2 | n_days | hac_maxlags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | DEV_COMMON | 17.1888 | 5.0822 | 7.2211 | 27.1565 | -0.0055 | 0.0545 | -0.1124 | 0.1014 | 0.0001 | 1767 | 7 |
| H2 | DEV_COMMON | 4.6939 | 2.4132 | -0.0391 | 9.4269 | 0.1627 | 0.0177 | 0.1280 | 0.1973 | 0.1860 | 1767 | 7 |
| H3 | DEV_COMMON | 20.1403 | 5.3661 | 9.6157 | 30.6649 | 0.0659 | 0.0560 | -0.0440 | 0.1758 | 0.0076 | 1767 | 7 |
| H4 | DEV_COMMON | 21.6771 | 5.6089 | 10.6763 | 32.6778 | 0.0583 | 0.0566 | -0.0527 | 0.1693 | 0.0057 | 1767 | 7 |
| H5 | DEV_COMMON | 20.8014 | 5.8883 | 9.2527 | 32.3501 | 0.0117 | 0.0528 | -0.0919 | 0.1153 | 0.0002 | 1767 | 7 |
| H1 | HOLD_B | 3.6948 | 10.6000 | -17.2221 | 24.6118 | -0.1244 | 0.1428 | -0.4063 | 0.1575 | 0.0387 | 181 | 4 |
| H2 | HOLD_B | 10.1680 | 4.8690 | 0.5600 | 19.7760 | 0.0968 | 0.0425 | 0.0130 | 0.1807 | 0.1154 | 181 | 4 |
| H3 | HOLD_B | 8.2856 | 10.7599 | -12.9470 | 29.5182 | -0.0955 | 0.1519 | -0.3953 | 0.2043 | 0.0217 | 181 | 4 |
| H4 | HOLD_B | 21.1978 | 17.5694 | -13.4720 | 55.8677 | 0.0115 | 0.1428 | -0.2702 | 0.2932 | 0.0002 | 181 | 4 |
| H5 | HOLD_B | 22.3643 | 12.0967 | -1.5061 | 46.2347 | -0.2403 | 0.1859 | -0.6072 | 0.1265 | 0.0910 | 181 | 4 |
| H1 | HOLD_A | -11.4948 | 8.3841 | -28.1513 | 5.1617 | 0.4207 | 0.1366 | 0.1493 | 0.6922 | 0.3824 | 92 | 3 |
| H2 | HOLD_A | 5.2259 | 5.4596 | -5.6205 | 16.0724 | 0.3024 | 0.0857 | 0.1321 | 0.4728 | 0.3544 | 92 | 3 |
| H3 | HOLD_A | -4.7744 | 9.3766 | -23.4026 | 13.8539 | 0.5369 | 0.1287 | 0.2812 | 0.7926 | 0.5113 | 92 | 3 |
| H4 | HOLD_A | -4.5718 | 9.4910 | -23.4274 | 14.2838 | 0.5377 | 0.1316 | 0.2762 | 0.7992 | 0.5078 | 92 | 3 |
| H5 | HOLD_A | -15.5224 | 10.5668 | -36.5153 | 5.4705 | 0.5408 | 0.1397 | 0.2633 | 0.8182 | 0.4564 | 92 | 3 |

| book | segment | long_exposure_ratio | short_exposure_ratio | long_net_bps | short_net_bps | total_net_bps | b0_total_net_bps | net_minus_b0_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | DEV_COMMON | 0.1975 | 0.2081 | 17032.1383 | 13329.6689 | 30361.8071 | 1969.0294 | 28392.7777 |
| H2 | DEV_COMMON | 0.1519 | 0.0000 | 8614.3956 | 0.0000 | 8614.3956 | 1969.0294 | 6645.3662 |
| H3 | DEV_COMMON | 0.2626 | 0.2059 | 22255.8903 | 13461.7929 | 35717.6832 | 1969.0294 | 33748.6538 |
| H4 | DEV_COMMON | 0.2639 | 0.2066 | 23797.8158 | 14620.3485 | 38418.1642 | 1969.0294 | 36449.1348 |
| H5 | DEV_COMMON | 0.2932 | 0.2876 | 21673.4445 | 15105.7571 | 36779.2016 | 1969.0294 | 34810.1721 |
| H1 | HOLD_B | 0.2818 | 0.1377 | -492.6680 | 1668.7895 | 1176.1215 | -4078.3699 | 5254.4914 |
| H2 | HOLD_B | 0.1381 | 0.0000 | 1445.5125 | 0.0000 | 1445.5125 | -4078.3699 | 5523.8824 |
| H3 | HOLD_B | 0.3204 | 0.1321 | 347.7432 | 1541.4531 | 1889.1963 | -4078.3699 | 5967.5662 |
| H4 | HOLD_B | 0.3264 | 0.1384 | 1370.4983 | 2419.4962 | 3789.9945 | -4078.3699 | 7868.3644 |
| H5 | HOLD_B | 0.3471 | 0.3041 | 2006.6859 | 3021.3285 | 5028.0144 | -4078.3699 | 9106.3843 |
| H1 | HOLD_A | 0.2283 | 0.0661 | 1037.6298 | -672.4088 | 365.2210 | 3381.7379 | -3016.5169 |
| H2 | HOLD_A | 0.1952 | 0.0000 | 1503.5290 | 0.0000 | 1503.5290 | 3381.7379 | -1878.2089 |
| H3 | HOLD_A | 0.2966 | 0.0661 | 2048.8254 | -672.4088 | 1376.4166 | 3381.7379 | -2005.3213 |
| H4 | HOLD_A | 0.2985 | 0.0666 | 2047.2880 | -649.6057 | 1397.6823 | 3381.7379 | -1984.0557 |
| H5 | HOLD_A | 0.4325 | 0.1707 | 984.3263 | -583.6242 | 400.7021 | 3381.7379 | -2981.0358 |

회귀는 일별 MTM net `후보 = α + β·B0 + ε`; Newey–West Bartlett HAC, lag=`floor(4(n/100)^(2/9))`, 유한표본 보정. α는 일 bp. 근거: `beta_hac.csv`, `direction_exposure.csv`.

### 2. C1 구성과 E1 국면

| segment | candidate | trade_n | net_bps | share_of_c1_net |
| --- | --- | --- | --- | --- |
| DEV_COMMON | E1\|1h\|3\|signal\|L | 186 | 4688.0927 | 0.1313 |
| DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 673 | 31029.5905 | 0.8687 |
| HOLD_B | E1\|1h\|3\|signal\|L | 18 | 873.0793 | 0.4621 |
| HOLD_B | F3\|1h\|10/24\|signal\|LS | 67 | 1016.1170 | 0.5379 |
| HOLD_A | E1\|1h\|3\|signal\|L | 14 | 1311.3180 | 0.9527 |
| HOLD_A | F3\|1h\|10/24\|signal\|LS | 23 | 65.0986 | 0.0473 |

| dev_return_tertile_cut1_bps | dev_return_tertile_cut2_bps | dev_vol_tertile_cut1_bps | dev_vol_tertile_cut2_bps | hold_a_return_30d_median_bps | hold_a_return_median_dev_percentile | hold_a_vol_30d_median_bps | hold_a_vol_median_dev_percentile |
| --- | --- | --- | --- | --- | --- | --- | --- |
| -592.2061 | 577.0716 | 226.1464 | 310.4539 | 544.5074 | 65.6502 | 186.8181 | 17.8366 |

| return_tertile | vol_tertile | trade_n | net_bps | net_per_trade_bps |
| --- | --- | --- | --- | --- |
| 상 | 상 | 38 | 1814.2503 | 47.7434 |
| 상 | 중 | 47 | 3109.3739 | 66.1569 |
| 상 | 하 | 56 | 1713.2241 | 30.5933 |
| 중 | 상 | 22 | 1912.2552 | 86.9207 |
| 중 | 중 | 32 | 1629.7292 | 50.9290 |
| 중 | 하 | 51 | 1252.3691 | 24.5563 |
| 초기30일미분류 | 초기30일미분류 | 4 | 178.6859 | 44.6715 |
| 하 | 상 | 37 | -1601.9011 | -43.2946 |
| 하 | 중 | 18 | -981.6786 | -54.5377 |
| 하 | 하 | 17 | -411.9124 | -24.2301 |

| return_tertile | vol_tertile | day_n | return_30d_mean_bps | vol_30d_mean_bps | day_ratio |
| --- | --- | --- | --- | --- | --- |
| 상 | 중 | 23 | 1829.1277 | 241.4642 | 0.2500 |
| 상 | 하 | 19 | 1240.3428 | 206.4871 | 0.2065 |
| 중 | 하 | 48 | 112.7402 | 162.9704 | 0.5217 |
| 하 | 중 | 1 | -1762.1472 | 233.2989 | 0.0109 |
| 하 | 하 | 1 | -832.7296 | 208.6859 | 0.0109 |

국면은 DEV의 B0 30일 MTM net 합과 일별 변동성의 각 3분위 경계로 고정했다. HOLD_A 30일 값은 HOLD_B 마지막 29일을 이어 계산했다. 근거: `c1_components.csv`, `e1_dev_regime.csv`, `hold_a_regime_days.csv`.

### 3. F3 약화

| year | trade_n | net_bps | net_per_trade_bps |
| --- | --- | --- | --- |
| 2021 | 154 | 13696.5718 | 88.9388 |
| 2022 | 138 | 4725.5375 | 34.2430 |
| 2023 | 136 | 5503.9445 | 40.4702 |
| 2024 | 135 | 5044.6052 | 37.3674 |
| 2025 | 154 | 1391.1480 | 9.0334 |

| half | trade_n | net_bps | net_per_trade_bps |
| --- | --- | --- | --- |
| 2021H1 | 73 | 7590.6269 | 103.9812 |
| 2021H2 | 81 | 6105.9450 | 75.3820 |
| 2022H1 | 65 | 5254.6894 | 80.8414 |
| 2022H2 | 73 | -529.1519 | -7.2487 |
| 2023H1 | 69 | 4502.0683 | 65.2474 |
| 2023H2 | 67 | 1001.8762 | 14.9534 |
| 2024H1 | 65 | 1632.5185 | 25.1157 |
| 2024H2 | 70 | 3412.0868 | 48.7441 |
| 2025H1 | 79 | -674.2068 | -8.5343 |
| 2025H2 | 75 | 2065.3548 | 27.5381 |

| slope_bps_per_trade_per_year | slope_hac_se | slope_ci95_low | slope_ci95_high | n_overlapping_windows | hac_maxlags |
| --- | --- | --- | --- | --- | --- |
| -15.6124 | 3.4776 | -22.4336 | -8.7912 | 1585 | 183 |

6개월은 183일 rolling, 거래는 entry-day 귀속. 기울기는 중첩을 감안해 HAC lag 183을 썼다. 근거: `f3_rolling_6m.parquet`.

### 4. 집중도

| book | hold_a_net_bps | hold_a_top1_bps | hold_a_top2_bps | hold_a_exclude_top1_net_bps | hold_a_exclude_top2_net_bps | dev_window_n | dev_exclude_top2_positive_ratio | dev_exclude_top2_p05_bps | dev_exclude_top2_p50_bps | dev_exclude_top2_p95_bps | hold_a_percentile |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | 365.2210 | 614.2279 | 613.8522 | -249.0069 | -862.8591 | 1676 | 0.4946 | -2546.9969 | -33.9229 | 2325.3848 | 28.7589 |
| H3 | 1376.4166 | 987.8343 | 614.2279 | 388.5823 | -225.6456 | 1676 | 0.5310 | -2767.8542 | 145.2915 | 2884.4854 | 42.6014 |
| H4 | 1397.6823 | 987.8343 | 614.2279 | 409.8480 | -204.3800 | 1676 | 0.5555 | -2490.3833 | 346.8820 | 3075.3026 | 40.8711 |
| H5 | 400.7021 | 987.8343 | 529.4512 | -587.1322 | -1116.5834 | 1676 | 0.4893 | -2288.8753 | -65.3853 | 5423.1100 | 26.1933 |

## k45_hold_a_report_complete_r2_30_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp | 2026-10-05T04:24:00.815939+00:00 |
| data_cutoff | 2026-06-30T23:59Z |
| frozen_hypothesis | HOLD_A frozen hypotheses unchanged; rehearsal validates execution only |
| hold_a_values_computed | 0 |
| rehearsal_values | HOLD_B_EXECUTION_VALIDATION_ONLY |
| rehearsal_exact | [{"item": "PatchTST gate", "generated_rows": 8801, "source_rows": 8801, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b LONG120 score", "generated_rows": 1356, "source_rows": 1356, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b SHORT60 score", "generated_rows": 1364, "source_rows": 1364, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-20 4h_h480 score", "generated_rows": 490, "source_rows": 490, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b tail accepted", "generated_rows": 11, "source_rows": 11, "exact |
| report_checklist | [{"section_6_item": "후보×경계×비용/거래당 net/노출/월별/상위거래/PW/무작위/B0 차이", "status": "있음"}, {"section_6_item": "signal→gate→tail→fold 경계→FIRST/carry-in/강제청산/max concurrent", "status": "있음"}, {"section_6_item": "PESS-OPT 경계 정산 사건", "status": "있음"}, {"section_6_item": "일별-거래 원장 parity", "status": "있음"}, {"section_6_item": "fold net/long-short/보유시간", "status": "있음"}, {"section_6_item": "DEV_COMMON·HOLD_B 병렬", "status": "있음"}, {"section_6_item": "기술 실패·재실행 이력", "status": "있음"}] |
| tests | {"command": "venv_btcusdt\\Scripts\\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_30", "result": "23 passed in 4.37s", "full_suite": "NOT_RUN_NOT_REQUESTED"} |
| selfcheck | {"path": "out/k45_hold_a_eval_build_r2_27_20261005/selfcheck.json", "sha256": "14c8aa1703444f8993f2252e2b261494ee49c651dec91239db21c71918402d50", "status": "PASS"} |

### out_of_sample_result (원문)

```text
"NOT_RUN_HOLD_A"
```

- 출력 해시: manifest에 outputs 해시 항목 없음.

### REPORT.md 앞 60줄 (전체 60줄, 원문)

# R2-30 HOLD_A report completion

## defects 1-3 fixed

- defect 1: runner:371, runner:1705 comparator None/비유한 → truth=None → UNMEASURABLE.
- defect 2: runner:1259 fold carry_in_n/forced_exit_n 실제 경계 집계.
- defect 3: runner:1681 6절 필수 항목 숫자 표 생성.

## rehearsal exact 12/12

| item | generated_rows | source_rows | exact | max_abs_difference | note |
| --- | --- | --- | --- | --- | --- |
| PatchTST gate | 8801 | 8801 | 1 | 0.000000 |  |
| R2-9b LONG120 score | 1356 | 1356 | 1 | 0.000000 |  |
| R2-9b SHORT60 score | 1364 | 1364 | 1 | 0.000000 |  |
| R2-20 4h_h480 score | 490 | 490 | 1 | 0.000000 |  |
| R2-9b tail accepted | 11 | 11 | 1 | 0.000000 |  |
| R2-20 tail accepted | 8 | 8 | 1 | 0.000000 |  |
| classic F3\|1h\|10/24\|signal\|LS | 46 | 46 | 1 | 0.000000 |  |
| classic E1\|1h\|3\|signal\|L | 18 | 18 | 1 | 0.000000 |  |
| classic F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 109 | 109 | 1 | 0.000000 |  |
| FIRST H3/C1 | 51 | 51 | 1 | 0.000000 |  |
| FIRST H4/C3 | 53 | 53 | 1 | 0.000000 |  |
| FIRST H5/C4 | 115 | 115 | 1 | 0.000000 |  |

| value_scope | decision_use |
| --- | --- |
| HOLD_B rehearsal | 실행 검증용; HOLD_A 판정 아님 |

## rehearsal report checklist

| section_6_item | status |
| --- | --- |
| 후보×경계×비용/거래당 net/노출/월별/상위거래/PW/무작위/B0 차이 | 있음 |
| signal→gate→tail→fold 경계→FIRST/carry-in/강제청산/max concurrent | 있음 |
| PESS-OPT 경계 정산 사건 | 있음 |
| 일별-거래 원장 parity | 있음 |
| fold net/long-short/보유시간 | 있음 |
| DEV_COMMON·HOLD_B 병렬 | 있음 |
| 기술 실패·재실행 이력 | 있음 |

## hashes

- runner SHA256: `3d0c971617982fdd890533690eabf9e62c9a221a3156b809ee0e479f704b6bc0`
- test SHA256: `aea40f8acbd85dd4d0372300b168dbd0f1174ef148f7a05361d81f639e051c2a`
- manifest SHA256: `831494e2a60e01382efad14787e821a022a55470f6c136afc66dfd885ad12f3d`

## tests

- command: `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_30`
- result: `23 passed in 4.37s`

- full suite: `NOT_RUN_NOT_REQUESTED`

- selfcheck: `PASS`, SHA256 `14c8aa1703444f8993f2252e2b261494ee49c651dec91239db21c71918402d50`

## HOLD_A guard

- HOLD_A predict/evaluate: NOT_RUN
- hold_a_values_computed: 0

## k45_hold_a_runner_complete_r2_29_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp | 2026-10-05T03:59:00.632418+00:00 |
| data_cutoff | 2026-06-30T23:59Z |
| frozen_hypothesis | HOLD_A frozen hypotheses unchanged; rehearsal validates execution only |
| hold_a_values_computed | 0 |
| rehearsal_exact | [{"item": "PatchTST gate", "generated_rows": 8801, "source_rows": 8801, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b LONG120 score", "generated_rows": 1356, "source_rows": 1356, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b SHORT60 score", "generated_rows": 1364, "source_rows": 1364, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-20 4h_h480 score", "generated_rows": 490, "source_rows": 490, "exact": true, "max_abs_difference": 0.0, "note": ""}, {"item": "R2-9b tail accepted", "generated_rows": 11, "source_rows": 11, "exact |
| tests | {"command": "venv_btcusdt\\Scripts\\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_29", "result": "20 passed in 4.24s", "full_suite": "COLLECTION_FAIL: 4 missing pre-existing patchtst_pure_direction_h60 results.json dependencies"} |
| selfcheck | {"path": "out/k45_hold_a_eval_build_r2_27_20261005/selfcheck.json", "sha256": "b7462c54393a8869bb5d6863d3827f0b7aab74c46dec327fcc393f1d11492c1b", "status": "PASS"} |

### out_of_sample_result (원문)

```text
"NOT_RUN_HOLD_A"
```

- 출력 해시: manifest에 outputs 해시 항목 없음.

### REPORT.md 앞 47줄 (전체 47줄, 원문)

# R2-29 HOLD_A runner completion

| item | generated_rows | source_rows | exact | max_abs_difference | note |
| --- | --- | --- | --- | --- | --- |
| PatchTST gate | 8801 | 8801 | 1 | 0.000000 |  |
| R2-9b LONG120 score | 1356 | 1356 | 1 | 0.000000 |  |
| R2-9b SHORT60 score | 1364 | 1364 | 1 | 0.000000 |  |
| R2-20 4h_h480 score | 490 | 490 | 1 | 0.000000 |  |
| R2-9b tail accepted | 11 | 11 | 1 | 0.000000 |  |
| R2-20 tail accepted | 8 | 8 | 1 | 0.000000 |  |
| classic F3\|1h\|10/24\|signal\|LS | 46 | 46 | 1 | 0.000000 |  |
| classic E1\|1h\|3\|signal\|L | 18 | 18 | 1 | 0.000000 |  |
| classic F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 109 | 109 | 1 | 0.000000 |  |
| FIRST H3/C1 | 51 | 51 | 1 | 0.000000 |  |
| FIRST H4/C3 | 53 | 53 | 1 | 0.000000 |  |
| FIRST H5/C4 | 115 | 115 | 1 | 0.000000 |  |

리허설 exact 표다. 이 구간 성과 숫자는 HOLD_B 값이며 판정용이 아니라 실행 검증용이다.

## defects 1-3 fixed

- defect 1: runner:1069 preflight completes before value load; all folds stage, publish, then CLOSED seal.
- defect 2: runner:220 missing CUDA raises ContractError; manifests record device/CUDA/cuDNN.
- defect 3: runner:1343 evaluate writes REPORT.md, metrics.parquet, trades.parquet, daily_pnl.parquet, manifest.json.

## remaining block

- freeze document is still DRAFT v2 and immutable in this task. HOLD_A predict/evaluate remains fail-closed.

## hashes

- runner SHA256: `90d4ebb88106e85bfc02ea3c53348c6b8b58441a41212f2c923a63e1ba8f20af`
- test SHA256: `edff785207553b8c26546d9a59d65dcb77dd926b8d62a1f122f6da7a3b855b5c`
- manifest SHA256: `3f447994fac014e685750865a9f4d4f94d85bcbd718669950d770c272600cebb`

## tests

- command: `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_29`
- result: `20 passed in 4.24s`

- full suite: `COLLECTION_FAIL: 4 missing pre-existing patchtst_pure_direction_h60 results.json dependencies`

- selfcheck: `PASS`, SHA256 `b7462c54393a8869bb5d6863d3827f0b7aab74c46dec327fcc393f1d11492c1b`

## rehearsal evaluation

- evaluate report generated without error: `rehearsal/REPORT.md`

## k45_hold_a_unblock_r2_28_20261005

- 테스트 재실행 `tests/test_k45_hold_a_eval_r2_27.py`: `32 passed in 5.09s`
### manifest 필드

| 필드 | 값 |
|---|---|
| timestamp | 2026-10-05T03:14:41.478923+00:00 |
| data_cutoff | 2026-06-30T23:59Z |
| frozen_hypothesis | 후보를 바꾸지 않고 원 출처 설정을 exact 재현하며 HOLD_A 입력만 생성한다. |
| hold_a_values_computed | 0 |
| downloads | [{"feed": "bookDepth", "date": "2026-07-01", "url": "https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2026-07-01.zip", "checksum_url": "https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2026-07-01.zip.CHECKSUM", "path": "artifacts/hold_a_2026q3/source_micro/bookDepth/BTCUSDT-bookDepth-2026-07-01.zip", "status": "downloaded", "bytes": 568918, "sha256": "5c6593d89225bdc41711e84391584b3df5677ddfe7c41e1fbff10bb0f030ac8a", "checksum_expected_sha256": "5c6593d89225bdc41711e84391584b3df5677ddfe7c41e1fbff10bb0f030ac8a", "checksum |
| reproduction | {"patchtst": {"device": "cuda", "gpu": "NVIDIA GeForce RTX 3090", "source_has_cudnn_deterministic": false, "source_has_use_deterministic_algorithms": false, "source_has_cublas_workspace_config": false, "runtime_cudnn_deterministic": false, "runtime_deterministic_algorithms": false, "runtime_cublas_workspace_config": null, "seed_vs_source": {"exact": true, "rows": 573, "max_abs_difference": 0.0}, "ensemble_vs_gate_source": {"exact": true, "rows": 191, "max_abs_difference": 0.0}, "run1_vs_run2_seed": {"exact": true, "rows": 573, "max_abs_difference": 0.0}, "run1_vs_run2_ensemble": {"exact": true |
| micro_build | {"timestamp": "2026-10-05T03:10:27.217522+00:00", "data_cutoff": "2026-06-30T23:59Z", "hold_a_values_computed": 0, "outputs": [{"path": "artifacts/hold_a_2026q3/micro_book_2026q3.parquet", "rows": 132480, "missing": {"open_time": 0, "book_valid": 0, "book_imbalance_1pct": 0, "book_imbalance_5pct": 0, "book_depth_total": 0, "book_slope_1_5": 0, "book_depth_change_5m": 0}, "sha256": "284ed38e31b88f624c43bea13f5bfcd2920ad2613a6f8c96dd749e9ec10e489b"}, {"path": "artifacts/hold_a_2026q3/micro_liquidity_2026q3.parquet", "rows": 132480, "missing": {"open_time": 0, "amihud_illiquidity": 0, "kyle_lambd |
| tests | {"command": "venv_btcusdt\\Scripts\\python.exe -m pytest tests/test_k45_hold_a_eval_r2_27.py -q --basetemp=.pytest_tmp_r2_28", "result": "16 passed in 4.63s"} |
| selfcheck | {"path": "out/k45_hold_a_eval_build_r2_27_20261005/selfcheck.json", "sha256": "b722ce95780a04a93702d250deee1117db5e72afb416fd58245eca3959daa5c5", "status": "PASS", "hold_a_values_computed": 0} |

### out_of_sample_result (원문)

```text
"NOT_RUN"
```

- 출력 해시: manifest에 outputs 해시 항목 없음.

### REPORT.md 앞 38줄 (전체 38줄, 원문)

# R2-28 R2-27 차단 해소 보고

| 과제 | exact | 원 출력 최대 차이 | 2회 실행 최대 차이 | 아카이브/CHECKSUM | 2026-06 패리티 불일치 |
|---|---:|---:|---:|---:|---:|
| 1 PatchTST fold 666 CUDA seed/ensemble | YES | 0 / 0 | 0 / 0 | N/A | N/A |
| 2 R2-9b V0 fold 666 `thread_count=-1` | YES | 0 | 0 | N/A | N/A |
| 3 m_* 23개 입력 | YES | N/A | N/A | bookDepth 92/92, aggTrades 92/92 검증; bookTicker 0/92(92개 없음) | 0 |

HOLD_A 예측·신호·성과·라벨·수익률은 계산하지 않았다. `hold_a_values_computed=0`이다. 과제 3 입력 피처만 생성했다.

## 고정 문서 v3 수정 문구 제안

1. **PatchTST 장치.** `out/run_patchtst_excursion_range.py` 원 계약인 `cuda if available else cpu`를 사용한다. R2-28 원 장치 재현은 NVIDIA GeForce RTX 3090/CUDA에서 seed 573행과 실제 게이트 출처 ensemble 191행이 exact였다. 원 소스에 `cudnn.deterministic`, `torch.use_deterministic_algorithms`, `CUBLAS_WORKSPACE_CONFIG` 설정은 없었으므로 추가하지 않는다. 장치·Torch/CUDA 버전과 게이트 파일 SHA256을 실행 manifest에 고정한다.
2. **CatBoost 스레드.** R2-9b V0만 원 설정 `thread_count=-1`을 사용한다. R2-28 머신은 논리 코어 32개이며 LONG120/SHORT60 50행이 원 출력과 exact, 2회 exact였다. 이 재현 학습만 CPU 워커 8 상한의 명시적 예외이고 다른 CPU 워커는 최대 8이다.
3. **미시구조 입력.** USD-M BTCUSDT 공개 일별 아카이브 `data.binance.vision`, 수집시각 `2026-10-05T03:02:14.953718+00:00`를 사용한다. bookDepth는 bar close `t+59s` 이하 마지막 snapshot, aggTrades는 exchange `transact_time`의 해당 minute만 사용한다. rolling/surge와 전일 big-trade threshold는 2026 H1 말 이력에서 연속 계산하며 Q3에서 reset하지 않는다. bookTicker는 2026-07-01~09-30 전 날짜가 공식 아카이브에 없으므로 `m_spread_valid=false`, spread 값은 NaN으로 두고 대체하지 않는다. 원 H1 2026-06도 `spread_valid=false` 43,200/43,200행이다. 네 출력 SHA256을 manifest에 고정한다.

## 재현 근거

- PatchTST: device `cuda`, seed 최대 차이 `0.0`, ensemble 최대 차이 `0.0`, 두 실행 최대 차이 `0.0`.
- CatBoost: `thread_count=-1`, 논리 코어 `32`, 원 출력/두 실행 최대 차이 모두 0.
- 다운로드: bookDepth 92개와 aggTrades 92개는 ZIP SHA256이 공식 CHECKSUM과 전부 일치한다. bookTicker CHECKSUM URL은 92개 모두 404다.
- 패리티: book/liquidity/spread/trade 각각 43,200행, exact, 최대 차이 0, 불일치 0.
- Q3 출력: 각 132,480행. 값 분포는 보고하지 않는다. SHA256: `{"micro_book_2026q3.parquet": "284ed38e31b88f624c43bea13f5bfcd2920ad2613a6f8c96dd749e9ec10e489b", "micro_liquidity_2026q3.parquet": "e89c0c823ece2f68687c846417e4a0b2cffe97f2d24ff43e4404870d6ef4f36c", "micro_spread_2026q3.parquet": "1da647968a8ef8bab15ad6d0f33611ede0875d55194f34103a62841e857527a2", "micro_trade_2026q3.parquet": "bc3db7c3c0091336da32799169076e84f9b3d0b62db4d01227f273552283e205"}`.
- 테스트: `16 passed in 4.63s`. selfcheck: `PASS`, SHA256 `b722ce95780a04a93702d250deee1117db5e72afb416fd58245eca3959daa5c5`.

## 갱신 파일 SHA256

- 러너 `out/run_k45_hold_a_eval_r2_27.py`: `31ad9227e7d9fb9339380d5cac2c24ec59922c2f8aa2ece6de841efe94c84dfb`
- 테스트 `tests/test_k45_hold_a_eval_r2_27.py`: `498daf40d951dc41c0c0e22ce1a9a5d56da09793c09b55c714a10b8649b5f123`
- R2-28 도구 `out/run_k45_hold_a_unblock_r2_28.py`: `4a4c84adac86da06690c47255be33b1776647a81a5710087a3101d4ae9e14f1e`
- manifest `out/k45_hold_a_unblock_r2_28_20261005/manifest.json`: `77ddbd89fffee76095ad120d4e819c447d8ebfeca872f2c760b364a698ba1f1f`

## 남은 차단

1. `docs/hold_a/`는 금지 조건대로 수정하지 않았다. v3가 위 문구와 새 러너·테스트·manifest 해시를 FROZEN으로 채택하기 전 `guard_frozen_contract()`는 계속 닫힌다.
2. 기존 `input_environment_manifest.json`은 R2-27의 `execution_ready=false` 상태다. v3 채택 후 R2-28 증거 manifest로 교체해야 한다.
3. 러너의 HOLD_A R2-9b/R2-20 fold writer와 closed prediction manifest 생성은 아직 구현되지 않았다. 이번 과제 범위는 원 설정 재현, m_* 입력 결합, selfcheck까지다.
4. 위 외부 절차가 끝나도 별도 승인 전에는 `predict/evaluate`를 실행하지 않는다.

## k45_holdout_a_2026q3

- 테스트 재실행 `tests/test_k45_holdout_a_2026q3.py`: `3 passed in 3.50s`
- manifest 없음 (미완료 또는 실행 전).
- 파일: BRIEF.md, codex.log, status.json

## k45_meta_label_r2_15_20261002

- 테스트 재실행 `tests/test_k45_meta_label_r2_15.py`: `6 passed in 1.92s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-15 |
| created_utc | 2026-10-02T09:30:38.405394+00:00 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| hypothesis_frozen | 메타 라벨 필터는 같은 받은 비율의 무작위 필터보다 DEV net·Sharpe가 높고(백분위 ≥ 95), HOLD_B에서도 원 규칙보다 거래당 net이 높다. 특히 추세추종 집합 T에서. |
| workers | 4 |
| numeric_threads_per_worker | 1 |
| live_orders | 0 |
| selection_rule | {"T": "A1-A6 family representative with maximum DEV Sharpe; all included", "G": "non-A family; DEV gross mean > 0, random percentile >= 0.90, n >= 300; maximum DEV Sharpe per family"} |
| selected_targets | [{"family": "A1", "cell_id": "A1/4h/50/200/trail2/L", "target_set": "T", "r2_dev_n": 27, "r2_dev_net_bps": 10304.142668901208, "r2_dev_sharpe": 0.9442747201121011, "r2_hold_n": 3, "r2_hold_net_bps": -519.8561831036806, "r2_hold_sharpe": -2.1227720800478256, "gross_mean_bps": null, "selection_random_percentile": null}, {"family": "A2", "cell_id": "A2/4h/55/10/signal/L", "target_set": "T", "r2_dev_n": 96, "r2_dev_net_bps": 18038.414121842296, "r2_dev_sharpe": 0.9069441991052166, "r2_hold_n": 9, "r2_hold_net_bps": -851.9877123931761, "r2_hold_sharpe": -1.9654961739469088, "gross_mean_bps": null,  |
| models | {"logistic": {"penalty": "L2", "C": 1.0, "standardized": true, "training_only_spearman_top": 20}, "catboost": {"depth": 4, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3, "seed": 20261001}, "thresholds": ["p > training base win rate", "p >= training p q50", "p >= training p q70"]} |
| feature_count | 216 |
| feature_names | ["return_1", "return_3", "return_5", "return_10", "return_15", "return_30", "return_45", "return_60", "log_return_1", "log_return_5", "momentum_10", "momentum_30", "rolling_return_max_20", "rolling_return_min_20", "close_sma_5_ratio", "close_sma_10_ratio", "close_sma_20_ratio", "close_sma_60_ratio", "close_ema_12_ratio", "close_ema_26_ratio", "ema_12_26_spread", "sma_5_20_spread", "sma_20_60_spread", "trend_slope_10", "trend_slope_30", "distance_to_high_20", "distance_to_low_20", "prev_horizon_trend", "rv_5", "rv_15", "rv_30", "rv_45", "rv_60", "rv_120", "atr_pct", "atr_pct_30", "atr_pct_45",  |
| oos_result | {"hypothesis_pass": true, "trend_hypothesis_pass": false, "passing_cells": [{"cell_id": "B1/15m/2.5/4/signal/L", "family": "B1", "target_set": "G", "model": "catboost", "threshold": "base"}, {"cell_id": "B1/15m/2.5/4/signal/L", "family": "B1", "target_set": "G", "model": "catboost", "threshold": "q50"}, {"cell_id": "B1/15m/2.5/4/signal/L", "family": "B1", "target_set": "G", "model": "logistic", "threshold": "base"}, {"cell_id": "B1/15m/2.5/4/signal/L", "family": "B1", "target_set": "G", "model": "logistic", "threshold": "q50"}, {"cell_id": "B1/15m/2.5/4/signal/L", "family": "B1", "target_set": |
| causal_contract | {"training": "exit_time < UTC month start", "prediction": "candidate entry month", "feature_time": "entry_time - 1 minute", "past_performance": "same-rule exits strictly before entry_time", "under_100": "all candidates accepted"} |

- 출력 해시 확인: 15/15 일치

### REPORT.md 앞 150줄 (전체 554줄, 원문)

# R2-15

## 대상

| family | cell_id | target_set | r2_dev_n | r2_dev_net_bps | r2_dev_sharpe | r2_hold_n | r2_hold_net_bps | r2_hold_sharpe | gross_mean_bps | selection_random_percentile |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | A1\|4h\|50/200\|trail2\|L | T | 27 | 10304.142669 | 0.944275 | 3 | -519.856183 | -2.122772 | nan | nan |
| A2 | A2\|4h\|55/10\|signal\|L | T | 96 | 18038.414122 | 0.906944 | 9 | -851.987712 | -1.965496 | nan | nan |
| A3 | A3\|4h\|720\|signal\|LS | T | 339 | 31309.380610 | 0.800353 | 45 | 3055.937445 | 1.065194 | nan | nan |
| A4 | A4\|4h\|10/3\|signal\|L | T | 130 | 17515.271415 | 0.602044 | 14 | -2251.052293 | -2.612842 | nan | nan |
| A5 | A5\|4h\|25\|trail2\|L | T | 180 | 18183.324390 | 0.783048 | 17 | -947.173409 | -1.435336 | nan | nan |
| A6 | A6\|1h\|40/60\|signal\|L | T | 228 | 5795.269532 | 0.363393 | 20 | 624.468656 | 1.260208 | nan | nan |
| B1 | B1\|15m\|2.5/4\|signal\|L | G | 2710 | -4022.828444 | -0.477105 | 259 | -433.660704 | -0.699539 | 2.515561 | 0.976000 |
| B2 | B2\|15m\|30/70/4\|signal\|L | G | 2848 | -1148.231981 | -0.111806 | 303 | -1332.323611 | -1.440401 | 3.596829 | 0.999000 |
| C1 | C1\|1h\|20/12\|limit\|L | G | 809 | 16131.127431 | 0.837606 | 64 | 417.047032 | 0.441376 | 23.939589 | 0.974000 |
| C2 | C2\|15m\|20\|signal\|L | G | 4233 | 3671.719278 | 0.164826 | 400 | -3692.830001 | -2.073876 | 4.867404 | 0.972000 |
| C3 | C3\|4h\|inside\|signal\|LS | G | 477 | 20260.841479 | 0.808160 | 49 | -503.669817 | -0.315420 | 46.475559 | 0.974000 |
| C4 | C4\|4h\|pin/trend4h\|signal\|S | G | 312 | 4885.758569 | 0.276383 | 31 | 1797.620240 | 1.626458 | 19.659483 | 0.954000 |
| E1 | E1\|1h\|3\|signal\|L | G | 375 | 14636.433664 | 1.148240 | 30 | 1447.343046 | 2.146867 | 43.030490 | 0.997000 |
| E2 | E2\|1h\|4h/follow/5\|signal\|L | G | 989 | 5346.597406 | 0.441069 | 108 | -274.989094 | -0.359267 | 9.406064 | 0.976000 |
| F1 | F1\|1h\|5/24\|signal\|LS | G | 818 | 16024.495580 | 0.749494 | 48 | 928.108334 | 0.762049 | 23.589848 | 0.986000 |
| F2 | F2\|4h\|-+/fade/4\|signal\|L | G | 2858 | 2176.121719 | 0.121377 | 254 | -3988.656886 | -3.538883 | 4.761414 | 0.950000 |
| F3 | F3\|1h\|10/24\|signal\|LS | G | 873 | 35384.229653 | 1.485597 | 76 | 1182.394594 | 0.682082 | 44.531764 | 0.999000 |
| F4 | F4\|1h\|5/4\|signal\|L | G | 1812 | 8056.289799 | 0.598889 | 186 | 1122.396624 | 0.771955 | 8.446076 | 0.998000 |
| G1 | G1\|1m\|us/60\|signal\|L | G | 1011 | 9224.191527 | 0.647023 | 78 | -985.645471 | -0.805300 | 13.123829 | 0.985000 |
| G2 | G2\|1m\|before/60/60\|signal\|L | G | 713 | 5553.163853 | 0.791497 | 207 | 680.485058 | 0.959230 | 11.788449 | 0.999000 |

## 원규칙_필터

| cell_id | model | threshold | segment | raw_n | raw_net_mean_bps | raw_net_total_bps | raw_daily_sharpe | filtered_n | received_ratio | filtered_net_mean_bps | filtered_net_total_bps | filtered_daily_sharpe | filtered_max_drawdown_bps | filtered_win_rate | filtered_profit_loss_ratio | random_net_percentile | random_sharpe_percentile |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1\|4h\|50/200\|trail2\|L | catboost | base | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | catboost | base | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | catboost | q50 | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | catboost | q50 | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | catboost | q70 | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | catboost | q70 | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | base | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | base | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | q50 | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | q50 | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | q70 | DEV | 27 | 381.634914 | 10304.142669 | 0.944275 | 27 | 1.000000 | 381.634914 | 10304.142669 | 0.944275 | 2003.354388 | 0.592593 | 3.006492 | 1.000000 | 1.000000 |
| A1\|4h\|50/200\|trail2\|L | logistic | q70 | HOLD_B | 3 | -173.285394 | -519.856183 | -2.122772 | 3 | 1.000000 | -173.285394 | -519.856183 | -2.122772 | 519.856183 | 0.000000 | nan | 1.000000 | 1.000000 |
| A2\|4h\|55/10\|signal\|L | catboost | base | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 94 | 0.979167 | 192.544811 | 18099.212253 | 0.910216 | 2518.690217 | 0.436170 | 2.664450 | 0.534000 | 0.520000 |
| A2\|4h\|55/10\|signal\|L | catboost | base | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 4 | 0.444444 | -173.815100 | -695.260401 | -1.981000 | 747.860071 | 0.250000 | 0.211001 | 0.134000 | 0.177000 |
| A2\|4h\|55/10\|signal\|L | catboost | q50 | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 96 | 1.000000 | 187.900147 | 18038.414122 | 0.906944 | 2518.690217 | 0.437500 | 2.633268 | 1.000000 | 1.000000 |
| A2\|4h\|55/10\|signal\|L | catboost | q50 | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 9 | 1.000000 | -94.665301 | -851.987712 | -1.965496 | 904.587382 | 0.333333 | 0.573673 | 1.000000 | 1.000000 |
| A2\|4h\|55/10\|signal\|L | catboost | q70 | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 92 | 0.958333 | 192.812014 | 17738.705243 | 0.893067 | 2518.690217 | 0.434783 | 2.655407 | 0.538000 | 0.499000 |
| A2\|4h\|55/10\|signal\|L | catboost | q70 | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 0 | 0.000000 | nan | 0.000000 | nan | 0.000000 | nan | nan | 1.000000 | 0.000000 |
| A2\|4h\|55/10\|signal\|L | logistic | base | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 93 | 0.968750 | 195.068991 | 18141.416167 | 0.912355 | 2518.690217 | 0.440860 | 2.620662 | 0.596000 | 0.572000 |
| A2\|4h\|55/10\|signal\|L | logistic | base | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 5 | 0.555556 | -135.887310 | -679.436551 | -1.976893 | 740.373407 | 0.200000 | 0.569816 | 0.259000 | 0.279000 |
| A2\|4h\|55/10\|signal\|L | logistic | q50 | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 93 | 0.968750 | 195.068991 | 18141.416167 | 0.912355 | 2518.690217 | 0.440860 | 2.620662 | 0.616000 | 0.602000 |
| A2\|4h\|55/10\|signal\|L | logistic | q50 | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 5 | 0.555556 | -135.887310 | -679.436551 | -1.976893 | 740.373407 | 0.200000 | 0.569816 | 0.253000 | 0.272000 |
| A2\|4h\|55/10\|signal\|L | logistic | q70 | DEV | 96 | 187.900147 | 18038.414122 | 0.906944 | 93 | 0.968750 | 195.068991 | 18141.416167 | 0.912355 | 2518.690217 | 0.440860 | 2.620662 | 0.621000 | 0.598000 |
| A2\|4h\|55/10\|signal\|L | logistic | q70 | HOLD_B | 9 | -94.665301 | -851.987712 | -1.965496 | 3 | 0.333333 | -175.565567 | -526.696700 | -1.896856 | 526.696700 | 0.000000 | nan | 0.205000 | 0.237000 |
| A3\|4h\|720\|signal\|LS | catboost | base | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 167 | 0.492625 | 89.825360 | 15000.835085 | 0.453295 | 5706.254332 | 0.377246 | 2.596546 | 0.483000 | 0.303000 |
| A3\|4h\|720\|signal\|LS | catboost | base | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 14 | 0.311111 | -55.091718 | -771.284051 | -1.641156 | 1123.245613 | 0.285714 | 1.150713 | 0.228000 | 0.203000 |
| A3\|4h\|720\|signal\|LS | catboost | q50 | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 326 | 0.961652 | 94.915285 | 30942.382887 | 0.791047 | 6449.542322 | 0.346626 | 3.273955 | 0.489000 | 0.467000 |
| A3\|4h\|720\|signal\|LS | catboost | q50 | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 44 | 0.977778 | 70.090571 | 3083.985116 | 1.075027 | 2093.396135 | 0.295455 | 4.057286 | 0.429000 | 0.429000 |
| A3\|4h\|720\|signal\|LS | catboost | q70 | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 89 | 0.262537 | 191.951798 | 17083.710039 | 0.555475 | 2515.267207 | 0.426966 | 2.943259 | 0.875000 | 0.716000 |
| A3\|4h\|720\|signal\|LS | catboost | q70 | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 0 | 0.000000 | nan | 0.000000 | nan | 0.000000 | nan | nan | 1.000000 | 0.000000 |
| A3\|4h\|720\|signal\|LS | logistic | base | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 208 | 0.613569 | 105.160789 | 21873.444197 | 0.613333 | 6026.803420 | 0.360577 | 2.994593 | 0.593000 | 0.453000 |
| A3\|4h\|720\|signal\|LS | logistic | base | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 22 | 0.488889 | 66.317628 | 1458.987808 | 0.757264 | 961.320296 | 0.318182 | 3.510686 | 0.462000 | 0.483000 |
| A3\|4h\|720\|signal\|LS | logistic | q50 | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 220 | 0.648968 | 116.386117 | 25604.945785 | 0.690148 | 6489.491163 | 0.359091 | 3.186251 | 0.717000 | 0.588000 |
| A3\|4h\|720\|signal\|LS | logistic | q50 | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 24 | 0.533333 | 41.618688 | 998.848510 | 0.512079 | 1399.235489 | 0.291667 | 3.312018 | 0.340000 | 0.353000 |
| A3\|4h\|720\|signal\|LS | logistic | q70 | DEV | 339 | 92.358055 | 31309.380610 | 0.800353 | 168 | 0.495575 | 111.939792 | 18805.885043 | 0.543733 | 4008.678429 | 0.357143 | 3.003914 | 0.643000 | 0.478000 |
| A3\|4h\|720\|signal\|LS | logistic | q70 | HOLD_B | 45 | 67.909721 | 3055.937445 | 1.065194 | 19 | 0.422222 | 86.320382 | 1640.087259 | 0.860037 | 881.036999 | 0.315789 | 3.956194 | 0.535000 | 0.556000 |
| A4\|4h\|10/3\|signal\|L | catboost | base | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 97 | 0.746154 | 140.438667 | 13622.550684 | 0.488886 | 5577.009479 | 0.309278 | 3.317114 | 0.521000 | 0.416000 |
| A4\|4h\|10/3\|signal\|L | catboost | base | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 8 | 0.571429 | -193.563382 | -1548.507055 | -2.474076 | 1548.507055 | 0.250000 | 0.377931 | 0.344000 | 0.221000 |
| A4\|4h\|10/3\|signal\|L | catboost | q50 | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 129 | 0.992308 | 132.254358 | 17060.812238 | 0.586803 | 5577.009479 | 0.348837 | 2.828904 | 0.214000 | 0.214000 |
| A4\|4h\|10/3\|signal\|L | catboost | q50 | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 14 | 1.000000 | -160.789449 | -2251.052293 | -2.612842 | 2398.004014 | 0.357143 | 0.430685 | 1.000000 | 1.000000 |
| A4\|4h\|10/3\|signal\|L | catboost | q70 | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 88 | 0.676923 | 167.002523 | 14696.222054 | 0.531681 | 5577.009479 | 0.295455 | 3.750413 | 0.701000 | 0.574000 |
| A4\|4h\|10/3\|signal\|L | catboost | q70 | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 0 | 0.000000 | nan | 0.000000 | nan | 0.000000 | nan | nan | 1.000000 | 0.000000 |
| A4\|4h\|10/3\|signal\|L | logistic | base | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 106 | 0.815385 | 97.980766 | 10385.961245 | 0.371136 | 5577.009479 | 0.283019 | 3.378856 | 0.220000 | 0.149000 |
| A4\|4h\|10/3\|signal\|L | logistic | base | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 10 | 0.714286 | -108.231526 | -1082.315262 | -1.650743 | 1448.654349 | 0.400000 | 0.509414 | 0.856000 | 0.848000 |
| A4\|4h\|10/3\|signal\|L | logistic | q50 | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 106 | 0.815385 | 97.980766 | 10385.961245 | 0.371136 | 5577.009479 | 0.283019 | 3.378856 | 0.250000 | 0.167000 |
| A4\|4h\|10/3\|signal\|L | logistic | q50 | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 10 | 0.714286 | -108.231526 | -1082.315262 | -1.650743 | 1448.654349 | 0.400000 | 0.509414 | 0.824000 | 0.827000 |
| A4\|4h\|10/3\|signal\|L | logistic | q70 | DEV | 130 | 134.732857 | 17515.271415 | 0.602044 | 98 | 0.753846 | 110.752747 | 10853.769225 | 0.389389 | 5577.009479 | 0.275510 | 3.595634 | 0.290000 | 0.211000 |
| A4\|4h\|10/3\|signal\|L | logistic | q70 | HOLD_B | 14 | -160.789449 | -2251.052293 | -2.612842 | 6 | 0.428571 | -129.621670 | -777.730023 | -1.748248 | 924.681744 | 0.333333 | 0.438995 | 0.642000 | 0.508000 |
| A5\|4h\|25\|trail2\|L | catboost | base | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 124 | 0.688889 | 141.733355 | 17574.936000 | 0.796210 | 6149.835051 | 0.387097 | 2.835131 | 0.862000 | 0.779000 |
| A5\|4h\|25\|trail2\|L | catboost | base | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 9 | 0.529412 | -75.934615 | -683.411536 | -1.692538 | 718.262644 | 0.333333 | 0.770804 | 0.364000 | 0.327000 |
| A5\|4h\|25\|trail2\|L | catboost | q50 | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 179 | 0.994444 | 100.843150 | 18050.923926 | 0.777406 | 6149.835051 | 0.385475 | 2.514748 | 0.326000 | 0.326000 |
| A5\|4h\|25\|trail2\|L | catboost | q50 | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 17 | 1.000000 | -55.716083 | -947.173409 | -1.435336 | 1145.688886 | 0.352941 | 0.979599 | 1.000000 | 1.000000 |
| A5\|4h\|25\|trail2\|L | catboost | q70 | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 83 | 0.461111 | 124.068590 | 10297.693009 | 0.523532 | 6149.835051 | 0.373494 | 2.675211 | 0.642000 | 0.496000 |
| A5\|4h\|25\|trail2\|L | catboost | q70 | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 0 | 0.000000 | nan | 0.000000 | nan | 0.000000 | nan | nan | 1.000000 | 0.000000 |
| A5\|4h\|25\|trail2\|L | logistic | base | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 127 | 0.705556 | 116.517078 | 14797.668881 | 0.677531 | 6149.835051 | 0.377953 | 2.670875 | 0.680000 | 0.548000 |
| A5\|4h\|25\|trail2\|L | logistic | base | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 7 | 0.411765 | -116.969565 | -818.786955 | -2.184890 | 818.786955 | 0.142857 | 1.439803 | 0.196000 | 0.226000 |
| A5\|4h\|25\|trail2\|L | logistic | q50 | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 130 | 0.722222 | 123.274387 | 16025.670374 | 0.729242 | 6149.835051 | 0.384615 | 2.670546 | 0.745000 | 0.630000 |
| A5\|4h\|25\|trail2\|L | logistic | q50 | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 8 | 0.470588 | -115.470362 | -923.762895 | -2.422343 | 923.762895 | 0.125000 | 1.530622 | 0.167000 | 0.176000 |
| A5\|4h\|25\|trail2\|L | logistic | q70 | DEV | 180 | 101.018469 | 18183.324390 | 0.783048 | 113 | 0.627778 | 111.142899 | 12559.147627 | 0.592555 | 6149.835051 | 0.362832 | 2.769230 | 0.611000 | 0.469000 |
| A5\|4h\|25\|trail2\|L | logistic | q70 | HOLD_B | 17 | -55.716083 | -947.173409 | -1.435336 | 5 | 0.294118 | -107.218237 | -536.091186 | -1.555328 | 629.757062 | 0.200000 | 1.301359 | 0.314000 | 0.411000 |
| A6\|1h\|40/60\|signal\|L | catboost | base | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 118 | 0.517544 | 37.192903 | 4388.762543 | 0.318849 | 4977.368753 | 0.347458 | 2.567395 | 0.653000 | 0.585000 |
| A6\|1h\|40/60\|signal\|L | catboost | base | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 4 | 0.200000 | -34.732490 | -138.929961 | -1.057689 | 178.603904 | 0.500000 | 0.306696 | 0.213000 | 0.286000 |
| A6\|1h\|40/60\|signal\|L | catboost | q50 | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 224 | 0.982456 | 26.367545 | 5906.330057 | 0.372192 | 5257.121630 | 0.343750 | 2.461921 | 0.454000 | 0.473000 |
| A6\|1h\|40/60\|signal\|L | catboost | q50 | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 19 | 0.950000 | 31.874317 | 605.612030 | 1.222436 | 424.678552 | 0.473684 | 2.008809 | 0.360000 | 0.360000 |
| A6\|1h\|40/60\|signal\|L | catboost | q70 | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 81 | 0.355263 | 57.080973 | 4623.558812 | 0.343699 | 4574.986428 | 0.358025 | 2.675602 | 0.782000 | 0.686000 |
| A6\|1h\|40/60\|signal\|L | catboost | q70 | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 0 | 0.000000 | nan | 0.000000 | nan | 0.000000 | nan | nan | 1.000000 | 0.000000 |
| A6\|1h\|40/60\|signal\|L | logistic | base | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 130 | 0.570175 | 32.903792 | 4277.492995 | 0.301068 | 4970.198059 | 0.346154 | 2.468490 | 0.653000 | 0.572000 |
| A6\|1h\|40/60\|signal\|L | logistic | base | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 8 | 0.400000 | 76.155558 | 609.244465 | 1.532660 | 178.603904 | 0.375000 | 4.986410 | 0.856000 | 0.785000 |
| A6\|1h\|40/60\|signal\|L | logistic | q50 | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 140 | 0.614035 | 23.987449 | 3358.242859 | 0.234894 | 5918.217916 | 0.342857 | 2.339483 | 0.470000 | 0.403000 |
| A6\|1h\|40/60\|signal\|L | logistic | q50 | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 9 | 0.450000 | 58.453282 | 526.079541 | 1.308180 | 261.768828 | 0.333333 | 4.704542 | 0.748000 | 0.687000 |
| A6\|1h\|40/60\|signal\|L | logistic | q70 | DEV | 228 | 25.417849 | 5795.269532 | 0.363393 | 117 | 0.513158 | 33.680848 | 3940.659168 | 0.280362 | 5181.964890 | 0.333333 | 2.606768 | 0.589000 | 0.510000 |
| A6\|1h\|40/60\|signal\|L | logistic | q70 | HOLD_B | 20 | 31.223433 | 624.468656 | 1.260208 | 5 | 0.250000 | 18.952893 | 94.764467 | 0.352621 | 178.603904 | 0.200000 | 5.583195 | 0.410000 | 0.388000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | base | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 1459 | 0.538376 | 1.900092 | 2772.234909 | 0.431955 | 2005.102836 | 0.555175 | 0.864461 | 0.993000 | 0.993000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | base | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 142 | 0.548263 | 3.594083 | 510.359809 | 0.983421 | 374.042508 | 0.492958 | 1.229767 | 0.948000 | 0.937000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | q50 | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 1057 | 0.390037 | 3.151278 | 3330.901156 | 0.615397 | 1051.039553 | 0.554399 | 0.915555 | 0.995000 | 0.995000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | q50 | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 136 | 0.525097 | 3.982520 | 541.622661 | 1.047214 | 349.228573 | 0.500000 | 1.211462 | 0.953000 | 0.948000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | q70 | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 216 | 0.079705 | -0.873491 | -188.674030 | -0.063255 | 2181.090161 | 0.587963 | 0.677981 | 0.560000 | 0.569000 |
| B1\|15m\|2.5/4\|signal\|L | catboost | q70 | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 29 | 0.111969 | 9.240523 | 267.975156 | 0.807903 | 253.684804 | 0.586207 | 1.017160 | 0.865000 | 0.791000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | base | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 1239 | 0.457196 | 1.518875 | 1881.885816 | 0.275954 | 2825.291902 | 0.553672 | 0.852103 | 0.974000 | 0.962000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | base | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 102 | 0.393822 | -0.944772 | -96.366740 | -0.199758 | 455.469755 | 0.480392 | 1.034053 | 0.566000 | 0.578000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | q50 | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 1350 | 0.498155 | 1.230438 | 1661.090851 | 0.240209 | 3196.914451 | 0.553333 | 0.845087 | 0.965000 | 0.960000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | q50 | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 127 | 0.490347 | -0.757354 | -96.183966 | -0.182968 | 733.033293 | 0.488189 | 1.011716 | 0.604000 | 0.620000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | q70 | DEV | 2710 | -1.484439 | -4022.828444 | -0.477105 | 837 | 0.308856 | 3.690750 | 3089.157722 | 0.530907 | 2245.435897 | 0.577061 | 0.829738 | 0.994000 | 0.984000 |
| B1\|15m\|2.5/4\|signal\|L | logistic | q70 | HOLD_B | 259 | -1.674366 | -433.660704 | -0.699539 | 71 | 0.274131 | 2.323054 | 164.936804 | 0.364675 | 423.266113 | 0.507042 | 1.076001 | 0.747000 | 0.717000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | base | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 1422 | 0.499298 | 4.787008 | 6807.124698 | 0.840547 | 2085.618223 | 0.563291 | 0.898733 | 0.999000 | 0.999000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | base | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 118 | 0.389439 | 5.789939 | 683.212857 | 0.992196 | 517.997818 | 0.559322 | 0.972293 | 0.969000 | 0.958000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | q50 | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 644 | 0.226124 | 6.217552 | 4004.103734 | 0.756659 | 1206.096643 | 0.554348 | 0.979081 | 0.982000 | 0.982000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | q50 | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 104 | 0.343234 | 5.238456 | 544.799387 | 0.804371 | 567.065475 | 0.557692 | 0.948862 | 0.951000 | 0.939000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | q70 | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 202 | 0.070927 | 23.642421 | 4775.768972 | 1.214623 | 859.264988 | 0.618812 | 1.128602 | 1.000000 | 0.998000 |
| B2\|15m\|30/70/4\|signal\|L | catboost | q70 | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 26 | 0.085809 | 15.940882 | 414.462922 | 0.757145 | 426.445511 | 0.538462 | 1.408092 | 0.929000 | 0.809000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | base | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 1235 | 0.433638 | 7.643667 | 9439.928135 | 1.268036 | 2117.066931 | 0.561943 | 0.976827 | 1.000000 | 1.000000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | base | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 97 | 0.320132 | -4.686992 | -454.638181 | -0.638472 | 870.268809 | 0.474227 | 0.948976 | 0.492000 | 0.577000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | q50 | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 1198 | 0.420646 | 8.154786 | 9769.433182 | 1.311262 | 1864.555551 | 0.567613 | 0.964871 | 1.000000 | 1.000000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | q50 | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 99 | 0.326733 | -3.756220 | -371.865769 | -0.527728 | 787.496396 | 0.484848 | 0.937303 | 0.515000 | 0.574000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | q70 | DEV | 2848 | -0.403171 | -1148.231981 | -0.111806 | 673 | 0.236306 | 12.075853 | 8127.049061 | 1.239479 | 2197.246084 | 0.585438 | 0.974817 | 1.000000 | 1.000000 |
| B2\|15m\|30/70/4\|signal\|L | logistic | q70 | HOLD_B | 303 | -4.397108 | -1332.323611 | -1.440401 | 34 | 0.112211 | 10.132980 | 344.521314 | 0.555060 | 468.419764 | 0.500000 | 1.267053 | 0.873000 | 0.771000 |
| C1\|1h\|20/12\|limit\|L | catboost | base | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 416 | 0.514215 | 24.990472 | 10396.036155 | 0.706219 | 4966.260688 | 0.521635 | 1.163384 | 0.684000 | 0.621000 |
| C1\|1h\|20/12\|limit\|L | catboost | base | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 32 | 0.500000 | -29.076671 | -930.453469 | -1.246255 | 1541.252503 | 0.375000 | 1.138798 | 0.041000 | 0.060000 |
| C1\|1h\|20/12\|limit\|L | catboost | q50 | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 280 | 0.346106 | 39.822526 | 11150.307310 | 1.048165 | 1803.117788 | 0.546429 | 1.264461 | 0.910000 | 0.936000 |
| C1\|1h\|20/12\|limit\|L | catboost | q50 | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 18 | 0.281250 | -26.840452 | -483.128133 | -0.858903 | 1034.954400 | 0.444444 | 0.902739 | 0.172000 | 0.194000 |
| C1\|1h\|20/12\|limit\|L | catboost | q70 | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 52 | 0.064277 | 6.435944 | 334.669099 | 0.080402 | 1862.388758 | 0.423077 | 1.481717 | 0.387000 | 0.397000 |
| C1\|1h\|20/12\|limit\|L | catboost | q70 | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 3 | 0.046875 | 76.623824 | 229.871471 | 0.810561 | 227.793652 | 0.666667 | 1.004561 | 0.757000 | 0.634000 |
| C1\|1h\|20/12\|limit\|L | logistic | base | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 411 | 0.508035 | 28.486633 | 11708.006283 | 0.803622 | 4811.032602 | 0.510949 | 1.257027 | 0.783000 | 0.732000 |
| C1\|1h\|20/12\|limit\|L | logistic | base | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 31 | 0.484375 | -7.229112 | -224.102478 | -0.364351 | 1431.093096 | 0.451613 | 1.081403 | 0.275000 | 0.267000 |
| C1\|1h\|20/12\|limit\|L | logistic | q50 | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 409 | 0.505562 | 28.773376 | 11768.310793 | 0.813182 | 4894.424719 | 0.513447 | 1.251541 | 0.812000 | 0.769000 |
| C1\|1h\|20/12\|limit\|L | logistic | q50 | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 34 | 0.531250 | 2.040203 | 69.366907 | 0.110542 | 1431.093096 | 0.500000 | 1.033873 | 0.404000 | 0.408000 |
| C1\|1h\|20/12\|limit\|L | logistic | q70 | DEV | 809 | 19.939589 | 16131.127431 | 0.837606 | 274 | 0.338690 | 36.960980 | 10127.308554 | 0.818472 | 3279.196887 | 0.514599 | 1.336688 | 0.888000 | 0.838000 |
| C1\|1h\|20/12\|limit\|L | logistic | q70 | HOLD_B | 64 | 6.516360 | 417.047032 | 0.441376 | 21 | 0.328125 | -55.401996 | -1163.441914 | -2.159143 | 1643.545330 | 0.285714 | 1.014156 | 0.023000 | 0.025000 |
| C2\|15m\|20\|signal\|L | catboost | base | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 2097 | 0.495393 | 5.306857 | 11128.479535 | 0.694461 | 5555.026711 | 0.550310 | 0.907529 | 0.972000 | 0.968000 |
| C2\|15m\|20\|signal\|L | catboost | base | HOLD_B | 400 | -9.232075 | -3692.830001 | -2.073876 | 162 | 0.405000 | -8.518626 | -1380.017458 | -1.010440 | 1964.549970 | 0.481481 | 0.899764 | 0.537000 | 0.645000 |
| C2\|15m\|20\|signal\|L | catboost | q50 | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 1385 | 0.327191 | 9.108599 | 12615.409118 | 1.049864 | 2244.409793 | 0.562455 | 0.943230 | 0.993000 | 0.996000 |
| C2\|15m\|20\|signal\|L | catboost | q50 | HOLD_B | 400 | -9.232075 | -3692.830001 | -2.073876 | 147 | 0.367500 | -8.880891 | -1305.490929 | -1.001480 | 1653.617223 | 0.482993 | 0.888851 | 0.505000 | 0.581000 |
| C2\|15m\|20\|signal\|L | catboost | q70 | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 406 | 0.095913 | 4.303370 | 1747.168074 | 0.251125 | 1794.149975 | 0.556650 | 0.869035 | 0.709000 | 0.706000 |
| C2\|15m\|20\|signal\|L | catboost | q70 | HOLD_B | 400 | -9.232075 | -3692.830001 | -2.073876 | 35 | 0.087500 | 24.556960 | 859.493617 | 1.204558 | 421.260617 | 0.542857 | 1.328259 | 0.969000 | 0.930000 |
| C2\|15m\|20\|signal\|L | logistic | base | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 1763 | 0.416489 | 9.454778 | 16668.772868 | 1.007348 | 3812.765770 | 0.557572 | 0.943960 | 1.000000 | 0.998000 |
| C2\|15m\|20\|signal\|L | logistic | base | HOLD_B | 400 | -9.232075 | -3692.830001 | -2.073876 | 153 | 0.382500 | -2.341390 | -358.232653 | -0.268054 | 1776.850203 | 0.516340 | 0.888363 | 0.829000 | 0.838000 |
| C2\|15m\|20\|signal\|L | logistic | q50 | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 1946 | 0.459721 | 7.752870 | 15087.084574 | 0.891966 | 3973.761202 | 0.549846 | 0.948258 | 0.998000 | 0.995000 |
| C2\|15m\|20\|signal\|L | logistic | q50 | HOLD_B | 400 | -9.232075 | -3692.830001 | -2.073876 | 194 | 0.485000 | -1.642950 | -318.732205 | -0.234605 | 1710.272496 | 0.525773 | 0.869289 | 0.890000 | 0.892000 |
| C2\|15m\|20\|signal\|L | logistic | q70 | DEV | 4233 | 0.867404 | 3671.719278 | 0.164826 | 1130 | 0.266950 | 14.006530 | 15827.379109 | 1.141783 | 3320.627451 | 0.575221 | 0.939106 | 1.000000 | 0.999000 |

## k45_mtf_entry_r2_12_20261001

- 테스트 재실행 `tests/test_k45_mtf_entry_r2_12.py`: `4 passed in 1.86s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-02T00:08:43.302962+00:00 |
| run_finished_utc | 2026-10-02T02:13:11.595028+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 상위봉 신호 + 하위봉 정밀 진입이 즉시 진입보다 단일 포지션 net을 높인다 |
| local_data_only | True |
| downloads | 0 |
| patchtst_refits | 0 |
| live_orders | 0 |
| cost_bps | 4.0 |
| funding_included | True |
| hold_b_exploratory | True |
| seed | 20261001 |
| model_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": 6, "verbose": false, "allow_writing_files": false} |
| single_position_first | True |

### out_of_sample_result (원문)

```text
"reported_without_result_filter"
```

- 출력 해시 확인: 27/27 일치

### REPORT.md 앞 150줄 (전체 8364줄, 원문)

# R2-12

## 0

| cost_bps | seed | live | hold_b_exploratory |
|---|---|---|---|
| 4 | 20261001 | 0 | 1 |

## 1

| tf | horizon | entry_tf | rule | k | gate_used | segment | signal_n | filled_n | fill_rate | dropped_overlap_n | max_concurrent | n | long_n | short_n | long_net_mean_bps | short_net_mean_bps | long_net_sum_bps | short_net_sum_bps | net_sum_bps | net_mean_bps | pw_status | pw_error | pw_block | pw_ci95_lower | pw_ci95_upper | calendar_days | trade_days | zero_day_share | pw_bootstrap_reps | fixed_bootstrap_reps | daily_fixed_blocks | event_fixed_blocks | trim_top1_net_mean_bps | trim_top2_net_mean_bps | trim_top5_net_mean_bps | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1h | 60 | 15 | E0 | nan | False | DEV | 22763 | 22763 | 1.000000 | 0 | 1 | 22763 | 12206 | 10557 | -2.625609 | -3.319259 | -32048.184641 | -35041.416468 | -67089.601109 | -2.947309 | MEASURABLE |  | 3.543584 | -3.773935 | -2.100358 | 1819 | 1768 | 0.028037 | 20000 | 999 | {"7":[-3.790010895440181,-2.1267384367337607],"14":[-3.7757268163910047,-2.1016970612464227],"30":[-3.8200025645511495,-2.0699207571067832]} | {"20":[-3.7803723277592876,-2.0786160509575278],"50":[-3.7296812329060955,-2.131813890878185]} | -2.976118 | -3.003947 | -3.076281 | 0.558670 | 0.169492 | 10 | 59 | 262.707000 |
| 1h | 60 | 15 | E0 | nan | False | HOLD_B | 1835 | 1835 | 1.000000 | 0 | 1 | 1835 | 1158 | 677 | -2.731349 | -0.937683 | -3162.901747 | -634.811441 | -3797.713188 | -2.069598 | MEASURABLE |  | 1.850364 | -4.559552 | 0.422845 | 181 | 180 | 0.011050 | 20000 | 999 | {"7":[-3.947422394376468,-0.13514048656733535],"14":[-3.515608352714322,-0.5695232697265113],"30":[-3.357115489853136,-1.032369509491076]} | {"20":[-4.452236321118452,0.3264182350300988],"50":[-4.159330522957781,-0.02065155951053388]} | -2.258053 | -2.418946 | -2.857451 | 0.555313 | 0.142857 | 1 | 7 | 3.868300 |
| 1h | 60 | 15 | E0 | nan | True | DEV | 4383 | 4383 | 1.000000 | 0 | 1 | 4383 | 2688 | 1695 | -1.468140 | -4.617338 | -3946.359421 | -7826.388566 | -11772.747987 | -2.686002 | MEASURABLE |  | 3.891734 | -5.044154 | -0.297529 | 1819 | 1074 | 0.409566 | 20000 | 999 | {"7":[-4.82004260770797,-0.5933163253612057],"14":[-4.917243138208896,-0.3712075758541622],"30":[-4.656585255172497,-0.5834990685766379]} | {"20":[-5.200439725513374,-0.4411981397813989],"50":[-4.853533690770042,-0.4975007710731889]} | -2.835585 | -2.980140 | -3.344947 | 0.547570 | 0.389831 | 23 | 59 | 137.948200 |
| 1h | 60 | 15 | E0 | nan | True | HOLD_B | 418 | 418 | 1.000000 | 0 | 1 | 418 | 289 | 129 | -1.302737 | -0.736942 | -376.490868 | -95.065573 | -471.556441 | -1.128125 | MEASURABLE |  | 1.491974 | -8.415154 | 6.110545 | 181 | 116 | 0.359116 | 20000 | 999 | {"7":[-6.779187204740755,4.498440279104958],"14":[-5.803697788618327,3.5943967963994607],"30":[-4.879235931336621,2.615145407231966]} | {"20":[-7.26043134599714,4.6591797023976085],"50":[-5.667728689201552,3.1459950869783118]} | -1.954704 | -2.662913 | -4.488498 | 0.521531 | 0.166667 | 1 | 6 | 11.097200 |
| 1h | 60 | 15 | E1 | 0.250000 | False | DEV | 22763 | 18718 | 0.822299 | 6329 | 1 | 12389 | 6584 | 5805 | -0.082154 | -3.235103 | -540.902237 | -18779.771907 | -19320.674144 | -1.559502 | MEASURABLE |  | 3.632921 | -2.776076 | -0.334317 | 1819 | 1761 | 0.031886 | 20000 | 999 | {"7":[-2.6330250294842132,-0.40418663671357313],"14":[-2.691705561671247,-0.44727753042972984],"30":[-2.562673570102021,-0.5131675091326329]} | {"20":[-2.8237362956741174,-0.23239751033832978],"50":[-2.70858715601623,-0.508643464793197]} | -1.633244 | -1.681355 | -1.819082 | 0.570264 | 0.338983 | 20 | 59 | 87.204700 |
| 1h | 60 | 15 | E1 | 0.250000 | False | HOLD_B | 1835 | 1469 | 0.800545 | 453 | 1 | 1016 | 628 | 388 | -1.143160 | -1.134958 | -717.904394 | -440.363830 | -1158.268225 | -1.140028 | MEASURABLE |  | 1.763679 | -4.733023 | 2.403849 | 181 | 179 | 0.016575 | 20000 | 999 | {"7":[-4.059179871021892,1.4611816687645227],"14":[-3.8307438459974104,1.29179084733246],"30":[-3.3023740842681883,0.7261257101881122]} | {"20":[-4.569311639673124,2.1127105076959087],"50":[-3.8863244229528062,1.4802628130872932]} | -1.516587 | -1.865176 | -2.702992 | 0.550197 | 0.428571 | 3 | 7 | 3.508300 |
| 1h | 60 | 15 | E1 | 0.250000 | True | DEV | 4383 | 3640 | 0.830481 | 982 | 1 | 2658 | 1625 | 1033 | 5.110862 | -4.119732 | 8305.150555 | -4255.682956 | 4049.467599 | 1.523502 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1020 | 0.439252 | 0 | 999 | {"7":[-1.9202701245410077,5.329564842812404],"14":[-2.01746397566696,5.004332480956166],"30":[-1.8333747120540878,5.006660021949608]} | {"20":[-2.218725545728744,5.3343630382108405],"50":[-2.0231646536189842,4.743176518620572]} | 1.180849 | 0.957528 | 0.317615 | 0.558315 | 0.559322 | 33 | 59 | 76.154500 |
| 1h | 60 | 15 | E1 | 0.250000 | True | HOLD_B | 418 | 348 | 0.832536 | 90 | 1 | 258 | 176 | 82 | 7.223366 | -0.631098 | 1271.312448 | -51.750059 | 1219.562389 | 4.726986 | MEASURABLE |  | 1.364011 | -6.307915 | 15.387364 | 181 | 111 | 0.386740 | 20000 | 999 | {"7":[-7.115308908220265,14.629056336813338],"14":[-7.762714683555553,14.880399496268826],"30":[-6.899864117485683,14.344075587417645]} | {"20":[-8.82897207294591,15.160314308933447],"50":[-7.6944544428031305,14.499835825716776]} | 3.262626 | 1.900554 | -1.402743 | 0.550388 | 0.333333 | 2 | 6 | 10.770900 |
| 1h | 60 | 15 | E1 | 0.500000 | False | DEV | 22763 | 14814 | 0.650793 | 4398 | 1 | 10416 | 5524 | 4892 | -0.690994 | -2.706317 | -3817.052106 | -13239.301829 | -17056.353935 | -1.637515 | MEASURABLE |  | 3.538364 | -2.994809 | -0.261185 | 1819 | 1752 | 0.036833 | 20000 | 999 | {"7":[-2.922716594645662,-0.31024626724230875],"14":[-2.938225412594609,-0.3585244304553854],"30":[-2.7442189349153225,-0.4575699567456317]} | {"20":[-3.0274609027699153,-0.28893759023197685],"50":[-2.9991604497272384,-0.400204785770536]} | -1.709266 | -1.769109 | -1.926344 | 0.574789 | 0.322034 | 19 | 59 | 46.767400 |
| 1h | 60 | 15 | E1 | 0.500000 | False | HOLD_B | 1835 | 1198 | 0.652861 | 328 | 1 | 870 | 547 | 323 | 0.859298 | 1.649481 | 470.035844 | 532.782211 | 1002.818054 | 1.152664 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 175 | 0.038674 | 0 | 999 | {"7":[-2.0725288163141786,4.320051020683634],"14":[-1.4795136908048185,3.6919369266775806],"30":[-0.9074197964556094,3.13492574043143]} | {"20":[-2.463934846236095,4.624602217026184],"50":[-1.4366687468807475,3.894655375726694]} | 0.698824 | 0.322365 | -0.679565 | 0.567816 | 0.571429 | 4 | 7 | 5.929900 |
| 1h | 60 | 15 | E1 | 0.500000 | True | DEV | 4383 | 2882 | 0.657540 | 686 | 1 | 2196 | 1343 | 853 | 5.182790 | -4.167315 | 6960.486727 | -3554.719319 | 3405.767409 | 1.550896 | MEASURABLE |  | 1.744216 | -2.564968 | 5.742644 | 1819 | 947 | 0.479384 | 20000 | 999 | {"7":[-2.1478598932685795,5.415272723535571],"14":[-2.2250694201305343,5.036903542167017],"30":[-1.935068710458584,5.33730764277436]} | {"20":[-2.491738663119012,5.440559431114982],"50":[-2.2703646676314877,5.158242880689986]} | 1.211898 | 0.929180 | 0.185741 | 0.563752 | 0.525424 | 31 | 59 | 66.080700 |
| 1h | 60 | 15 | E1 | 0.500000 | True | HOLD_B | 418 | 283 | 0.677033 | 69 | 1 | 214 | 150 | 64 | 11.394381 | 3.547302 | 1709.157112 | 227.027349 | 1936.184460 | 9.047591 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 103 | 0.430939 | 0 | 999 | {"7":[-1.0118385466929993,18.389842084797724],"14":[-0.02233031582695233,17.55298338813615],"30":[1.005699971286944,16.187501295159624]} | {"20":[-1.3029934430707897,18.960140446941267],"50":[0.2816935041028721,17.26412947670375]} | 7.233074 | 5.722542 | 1.834405 | 0.574766 | 0.833333 | 5 | 6 | 9.167000 |
| 1h | 60 | 15 | E1 | 1.000000 | False | DEV | 22763 | 9050 | 0.397575 | 2053 | 1 | 6997 | 3730 | 3267 | -1.099539 | -2.678729 | -4101.279954 | -8751.408580 | -12852.688535 | -1.836886 | MEASURABLE |  | 1.745286 | -3.682116 | 0.051650 | 1819 | 1727 | 0.050577 | 20000 | 999 | {"7":[-3.5444427895507573,0.024696509804799316],"14":[-3.488964452312733,0.008505050664058711],"30":[-3.5963676328227177,-0.0847550442235443]} | {"20":[-3.7453428391077415,-0.022130769952391827],"50":[-3.511792049949737,-0.13012371224100838]} | -1.999842 | -2.088981 | -2.306034 | 0.587109 | 0.372881 | 22 | 59 | 90.991500 |
| 1h | 60 | 15 | E1 | 1.000000 | False | HOLD_B | 1835 | 748 | 0.407629 | 170 | 1 | 578 | 364 | 214 | -1.559966 | 2.720214 | -567.827669 | 582.125788 | 14.298118 | 0.024737 | MEASURABLE |  | 1.043817 | -5.592406 | 5.688685 | 181 | 172 | 0.055249 | 20000 | 999 | {"7":[-4.612618701575932,4.95676135024787],"14":[-4.2276933804106624,4.988493107859976],"30":[-3.8738649572712878,4.485800350422023]} | {"20":[-4.605499530747559,4.95473855166944],"50":[-4.175016685767435,5.288378087083888]} | -0.678532 | -1.324028 | -2.554444 | 0.557093 | 0.571429 | 4 | 7 | 4.478400 |
| 1h | 60 | 15 | E1 | 1.000000 | True | DEV | 4383 | 1735 | 0.395848 | 307 | 1 | 1428 | 879 | 549 | 8.098788 | -3.188494 | 7118.834409 | -1750.483148 | 5368.351262 | 3.759350 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 768 | 0.577790 | 0 | 999 | {"7":[-1.1381201351762158,9.400905337450457],"14":[-1.5406054060295427,9.117890308247645],"30":[-1.4163544085854936,9.028393028288644]} | {"20":[-1.1621432101757865,9.299610837367847],"50":[-1.362396546465101,8.264308279535765]} | 2.964363 | 2.579667 | 1.682991 | 0.568627 | 0.542373 | 32 | 59 | 64.615100 |
| 1h | 60 | 15 | E1 | 1.000000 | True | HOLD_B | 418 | 184 | 0.440191 | 34 | 1 | 150 | 103 | 47 | 15.441698 | 11.188456 | 1590.494915 | 525.857450 | 2116.352365 | 14.109016 | MEASURABLE |  | 1.074221 | -1.876544 | 29.513870 | 181 | 89 | 0.508287 | 20000 | 999 | {"7":[-2.5865504484866317,27.84714669496363],"14":[0.34532546372592954,27.187291230767123],"30":[1.6505876286291308,26.221653573817846]} | {"20":[2.707298447340257,25.29795488836505],"50":[5.296964450169105,23.265682867712144]} | 11.480142 | 9.050095 | 4.525025 | 0.593333 | 0.833333 | 5 | 6 | 6.414900 |
| 1h | 60 | 15 | E2 | nan | False | DEV | 22763 | 14418 | 0.633396 | 3666 | 1 | 10752 | 5744 | 5008 | -5.314300 | -5.968501 | -30525.340409 | -29890.255350 | -60415.595759 | -5.619010 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1760 | 0.032435 | 0 | 999 | {"7":[-6.9201347787858225,-4.284069779492161],"14":[-7.007126544857874,-4.121424278768524],"30":[-6.999075254345058,-4.0883814771721605]} | {"20":[-6.793385637974922,-4.406225009084922],"50":[-6.901312652173934,-4.275889706223921]} | -5.676499 | -5.727418 | -5.861551 | 0.502511 | 0.067797 | 4 | 59 | -56.364300 |
| 1h | 60 | 15 | E2 | nan | False | HOLD_B | 1835 | 1170 | 0.637602 | 246 | 1 | 924 | 555 | 369 | -4.969824 | -2.151454 | -2758.252220 | -793.886503 | -3552.138723 | -3.844306 | MEASURABLE |  | 1.095595 | -7.749029 | 0.101873 | 181 | 178 | 0.022099 | 20000 | 999 | {"7":[-7.4097846180644735,-0.4031929006165309],"14":[-7.232975156938393,-0.8677929232408581],"30":[-6.628127647532561,-1.3414539295839472]} | {"20":[-7.4320574231658565,-0.14089935778683316],"50":[-7.081493737245706,-0.7101312970163214]} | -4.314718 | -4.620567 | -5.415765 | 0.516234 | 0.285714 | 2 | 7 | 3.079000 |
| 1h | 60 | 15 | E2 | nan | True | DEV | 4383 | 2713 | 0.618982 | 541 | 1 | 2172 | 1369 | 803 | -5.645259 | -5.655245 | -7728.360140 | -4541.161510 | -12269.521650 | -5.648951 | MEASURABLE |  | 2.813016 | -9.402445 | -1.845012 | 1819 | 936 | 0.485432 | 20000 | 999 | {"7":[-9.39892821960984,-1.659634884783154],"14":[-9.893778386111757,-1.4373455530916033],"30":[-10.158121270778672,-0.7643997628586536]} | {"20":[-10.117210457960798,-1.503803524958765],"50":[-10.535015247446132,-0.8910420516755115]} | -5.933656 | -6.186025 | -6.784958 | 0.491252 | 0.389831 | 23 | 59 | 19.491700 |
| 1h | 60 | 15 | E2 | nan | True | HOLD_B | 418 | 256 | 0.612440 | 46 | 1 | 210 | 146 | 64 | -5.049727 | 13.748843 | -737.260179 | 879.925976 | 142.665798 | 0.679361 | MEASURABLE |  | 1.163251 | -10.629681 | 11.562466 | 181 | 100 | 0.447514 | 20000 | 999 | {"7":[-9.437338591906082,10.391720855266122],"14":[-8.770875917499351,10.365163579464456],"30":[-7.71655331589384,8.043600885797549]} | {"20":[-7.905983628977964,9.575182933506659],"50":[-7.288414611195782,7.608558782706034]} | -0.645992 | -1.929750 | -5.053370 | 0.509524 | 0.500000 | 3 | 6 | 5.624100 |
| 1h | 60 | 30 | E0 | nan | False | DEV | 22763 | 22763 | 1.000000 | 0 | 1 | 22763 | 12206 | 10557 | -2.625609 | -3.319259 | -32048.184641 | -35041.416468 | -67089.601109 | -2.947309 | MEASURABLE |  | 3.543584 | -3.773935 | -2.100358 | 1819 | 1768 | 0.028037 | 20000 | 999 | {"7":[-3.790010895440181,-2.1267384367337607],"14":[-3.7757268163910047,-2.1016970612464227],"30":[-3.8200025645511495,-2.0699207571067832]} | {"20":[-3.7803723277592876,-2.0786160509575278],"50":[-3.7296812329060955,-2.131813890878185]} | -2.976118 | -3.003947 | -3.076281 | 0.558670 | 0.169492 | 10 | 59 | 262.707000 |
| 1h | 60 | 30 | E0 | nan | False | HOLD_B | 1835 | 1835 | 1.000000 | 0 | 1 | 1835 | 1158 | 677 | -2.731349 | -0.937683 | -3162.901747 | -634.811441 | -3797.713188 | -2.069598 | MEASURABLE |  | 1.850364 | -4.559552 | 0.422845 | 181 | 180 | 0.011050 | 20000 | 999 | {"7":[-3.947422394376468,-0.13514048656733535],"14":[-3.515608352714322,-0.5695232697265113],"30":[-3.357115489853136,-1.032369509491076]} | {"20":[-4.452236321118452,0.3264182350300988],"50":[-4.159330522957781,-0.02065155951053388]} | -2.258053 | -2.418946 | -2.857451 | 0.555313 | 0.142857 | 1 | 7 | 3.868300 |
| 1h | 60 | 30 | E0 | nan | True | DEV | 4383 | 4383 | 1.000000 | 0 | 1 | 4383 | 2688 | 1695 | -1.468140 | -4.617338 | -3946.359421 | -7826.388566 | -11772.747987 | -2.686002 | MEASURABLE |  | 3.891734 | -5.044154 | -0.297529 | 1819 | 1074 | 0.409566 | 20000 | 999 | {"7":[-4.82004260770797,-0.5933163253612057],"14":[-4.917243138208896,-0.3712075758541622],"30":[-4.656585255172497,-0.5834990685766379]} | {"20":[-5.200439725513374,-0.4411981397813989],"50":[-4.853533690770042,-0.4975007710731889]} | -2.835585 | -2.980140 | -3.344947 | 0.547570 | 0.389831 | 23 | 59 | 137.948200 |
| 1h | 60 | 30 | E0 | nan | True | HOLD_B | 418 | 418 | 1.000000 | 0 | 1 | 418 | 289 | 129 | -1.302737 | -0.736942 | -376.490868 | -95.065573 | -471.556441 | -1.128125 | MEASURABLE |  | 1.491974 | -8.415154 | 6.110545 | 181 | 116 | 0.359116 | 20000 | 999 | {"7":[-6.779187204740755,4.498440279104958],"14":[-5.803697788618327,3.5943967963994607],"30":[-4.879235931336621,2.615145407231966]} | {"20":[-7.26043134599714,4.6591797023976085],"50":[-5.667728689201552,3.1459950869783118]} | -1.954704 | -2.662913 | -4.488498 | 0.521531 | 0.166667 | 1 | 6 | 11.097200 |
| 1h | 60 | 30 | E1 | 0.250000 | False | DEV | 22763 | 16950 | 0.744629 | 5473 | 1 | 11477 | 6103 | 5374 | -0.267107 | -3.282347 | -1630.156550 | -17639.330145 | -19269.486694 | -1.678965 | MEASURABLE |  | 3.145026 | -3.021246 | -0.329146 | 1819 | 1758 | 0.033535 | 20000 | 999 | {"7":[-2.9616207919916953,-0.4121417894659889],"14":[-2.8978344666271356,-0.41416927530580394],"30":[-2.7388623351835175,-0.49881323285889545]} | {"20":[-3.059349712969946,-0.31637925942225764],"50":[-3.0398297216279824,-0.38342082239319586]} | -1.758291 | -1.822556 | -1.987495 | 0.571665 | 0.355932 | 21 | 59 | 96.949700 |
| 1h | 60 | 30 | E1 | 0.250000 | False | HOLD_B | 1835 | 1341 | 0.730790 | 399 | 1 | 942 | 591 | 351 | -3.139609 | -0.106019 | -1855.508835 | -37.212757 | -1892.721592 | -2.009259 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 176 | 0.033149 | 0 | 999 | {"7":[-4.836272282683291,0.9726180215930662],"14":[-4.422416891911737,0.339742155510967],"30":[-3.9099399215341464,-0.10641978470617963]} | {"20":[-5.310888744279477,1.4539732770706055],"50":[-4.642131187540054,0.6436697861915874]} | -2.400807 | -2.770194 | -3.707542 | 0.543524 | 0.285714 | 2 | 7 | 4.732800 |
| 1h | 60 | 30 | E1 | 0.250000 | True | DEV | 4383 | 3412 | 0.778462 | 897 | 1 | 2515 | 1533 | 982 | 5.660470 | -2.809160 | 8677.500863 | -2758.595481 | 5918.905381 | 2.353442 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1005 | 0.447499 | 0 | 999 | {"7":[-1.4696552817251267,6.5111199970975715],"14":[-1.5741863764231092,6.032408611483595],"30":[-1.2747664366719706,6.185179898280477]} | {"20":[-1.4760407677296445,6.1546238257602734],"50":[-1.6291708911577474,5.907631587155413]} | 1.992937 | 1.721025 | 1.042820 | 0.560636 | 0.508475 | 30 | 59 | 82.068300 |
| 1h | 60 | 30 | E1 | 0.250000 | True | HOLD_B | 418 | 325 | 0.777512 | 85 | 1 | 240 | 166 | 74 | 4.474473 | 0.785594 | 742.762467 | 58.133949 | 800.896415 | 3.337068 | MEASURABLE |  | 1.237726 | -7.781890 | 14.330546 | 181 | 110 | 0.392265 | 20000 | 999 | {"7":[-6.495987829165388,12.338351098907518],"14":[-7.284039762893558,12.270156001576936],"30":[-5.902684487848964,11.341860169305967]} | {"20":[-7.065450963382009,12.71075560452383],"50":[-6.440308378314587,12.542477442994958]} | 1.817817 | 0.376622 | -3.242855 | 0.554167 | 0.333333 | 2 | 6 | 9.761300 |
| 1h | 60 | 30 | E1 | 0.500000 | False | DEV | 22763 | 12029 | 0.528445 | 3239 | 1 | 8790 | 4697 | 4093 | -1.615695 | -2.512694 | -7588.917402 | -10284.455569 | -17873.372971 | -2.033376 | MEASURABLE |  | 1.416363 | -3.737066 | -0.315895 | 1819 | 1741 | 0.042881 | 20000 | 999 | {"7":[-3.6782307961293603,-0.37826422423417605],"14":[-3.488949845518969,-0.46441936411202733],"30":[-3.3719180221510743,-0.6107950726733153]} | {"20":[-3.7503355550984905,-0.4895355128964982],"50":[-3.714330873253195,-0.4990436674068328]} | -2.107299 | -2.174750 | -2.352173 | 0.578953 | 0.372881 | 22 | 59 | 117.759200 |
| 1h | 60 | 30 | E1 | 0.500000 | False | HOLD_B | 1835 | 963 | 0.524796 | 243 | 1 | 720 | 454 | 266 | -1.416498 | 2.013072 | -643.089883 | 535.477156 | -107.612726 | -0.149462 | MEASURABLE |  | 1.877568 | -4.766325 | 4.487755 | 181 | 173 | 0.049724 | 20000 | 999 | {"7":[-4.020187795933035,3.7958063924762],"14":[-3.790333950368721,3.7438867037655315],"30":[-3.1298670949723166,3.2631931565790624]} | {"20":[-4.082569886417199,4.158980675767411],"50":[-3.5849561957684886,3.173354208100516]} | -0.619098 | -1.045106 | -2.084104 | 0.568056 | 0.571429 | 4 | 7 | 7.079700 |
| 1h | 60 | 30 | E1 | 0.500000 | True | DEV | 4383 | 2515 | 0.573808 | 566 | 1 | 1949 | 1192 | 757 | 5.077618 | -1.841557 | 6052.520302 | -1394.058287 | 4658.462016 | 2.390181 | MEASURABLE |  | 2.028496 | -2.228360 | 7.014473 | 1819 | 914 | 0.497526 | 20000 | 999 | {"7":[-1.5867006589735215,7.251177452544842],"14":[-1.7598909178539053,6.595111682935775],"30":[-1.5512081949743286,6.591674129263258]} | {"20":[-1.9015918650470258,6.821901065942066],"50":[-1.692352631587954,6.503113204764042]} | 2.058922 | 1.819802 | 1.134358 | 0.562853 | 0.542373 | 32 | 59 | 69.320700 |
| 1h | 60 | 30 | E1 | 0.500000 | True | HOLD_B | 418 | 250 | 0.598086 | 59 | 1 | 191 | 132 | 59 | 3.169917 | 4.906041 | 418.429101 | 289.456410 | 707.885512 | 3.706207 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 101 | 0.441989 | 0 | 999 | {"7":[-5.682208834535826,12.432941324223117],"14":[-4.766942695789288,11.59166185326684],"30":[-3.526814829509646,11.072414098744636]} | {"20":[-3.7375270990257277,10.720941826611458],"50":[-2.1884547199785422,9.385582180366427]} | 1.949299 | 0.344510 | -3.170023 | 0.570681 | 0.666667 | 4 | 6 | 7.208100 |
| 1h | 60 | 30 | E1 | 1.000000 | False | DEV | 22763 | 5914 | 0.259808 | 1112 | 1 | 4802 | 2602 | 2200 | -2.574859 | -4.552520 | -6699.784341 | -10015.543601 | -16715.327943 | -3.480910 | MEASURABLE |  | 1.312380 | -6.234610 | -0.808399 | 1819 | 1670 | 0.081913 | 20000 | 999 | {"7":[-5.787150206406101,-0.9275954819660992],"14":[-5.829432779535471,-1.1675152817177237],"30":[-5.700360891504857,-1.2263030035241886]} | {"20":[-6.053246494081122,-0.9139290483256932],"50":[-5.81121781294881,-1.1904149063361293]} | -3.686699 | -3.860775 | -4.261729 | 0.579967 | 0.389831 | 23 | 59 | 124.990300 |
| 1h | 60 | 30 | E1 | 1.000000 | False | HOLD_B | 1835 | 537 | 0.292643 | 108 | 1 | 429 | 270 | 159 | 1.272442 | -0.431676 | 343.559472 | -68.636560 | 274.922912 | 0.640846 | MEASURABLE |  | 1.075447 | -7.123775 | 8.316461 | 181 | 169 | 0.071823 | 20000 | 999 | {"7":[-5.9149621823145155,7.154309536554197],"14":[-5.005062006792727,6.986225308287444],"30":[-4.479179473301424,5.954322274283801]} | {"20":[-5.5747255912096945,7.634456568868348],"50":[-4.539817249868115,6.905164078024171]} | -0.357226 | -1.290155 | -3.094945 | 0.552448 | 0.857143 | 6 | 7 | -0.174700 |
| 1h | 60 | 30 | E1 | 1.000000 | True | DEV | 4383 | 1278 | 0.291581 | 204 | 1 | 1074 | 670 | 404 | 7.845451 | -7.562521 | 5256.451999 | -3055.258417 | 2201.193581 | 2.049528 | MEASURABLE |  | 2.359130 | -5.296177 | 9.278184 | 1819 | 672 | 0.630566 | 20000 | 999 | {"7":[-4.109041722539757,9.17307571340287],"14":[-5.181696463300945,8.592379309442961],"30":[-4.675052541981556,8.254379281042356]} | {"20":[-5.040965299211052,8.392617333353492],"50":[-4.026000109263393,8.234397054732822]} | 1.133907 | 0.546977 | -0.702562 | 0.581937 | 0.542373 | 32 | 59 | 61.629300 |
| 1h | 60 | 30 | E1 | 1.000000 | True | HOLD_B | 418 | 153 | 0.366029 | 26 | 1 | 127 | 87 | 40 | 10.070989 | 12.810511 | 876.176047 | 512.420460 | 1388.596507 | 10.933831 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 86 | 0.524862 | 0 | 999 | {"7":[-5.2365488718715785,25.578907303105765],"14":[-1.690709015183689,23.495065225245376],"30":[-1.680857246107898,22.740964417528197]} | {"20":[0.17659393743924312,21.765096749980486],"50":[2.6893978527314832,19.586352358268428]} | 7.625246 | 4.502220 | -0.956397 | 0.566929 | 0.666667 | 4 | 6 | 3.112500 |
| 1h | 60 | 30 | E2 | nan | False | DEV | 22763 | 8276 | 0.363572 | 1239 | 1 | 7037 | 3844 | 3193 | -5.329529 | -5.164534 | -20486.709994 | -16490.358126 | -36977.068120 | -5.254664 | MEASURABLE |  | 2.771839 | -6.810118 | -3.684309 | 1819 | 1735 | 0.046179 | 20000 | 999 | {"7":[-6.770144440277889,-3.6276201300982223],"14":[-7.066980715341053,-3.453641932632104],"30":[-6.974793014332098,-3.5503510450486724]} | {"20":[-6.763373310156272,-3.6441678430343893],"50":[-6.832235382471286,-3.7568498823923004]} | -5.365115 | -5.435062 | -5.622493 | 0.486997 | 0.152542 | 9 | 59 | -26.667100 |
| 1h | 60 | 30 | E2 | nan | False | HOLD_B | 1835 | 651 | 0.354768 | 73 | 1 | 578 | 362 | 216 | -0.619004 | 0.999297 | -224.079493 | 215.848257 | -8.231237 | -0.014241 | MEASURABLE |  | 1.078804 | -4.185203 | 3.911987 | 181 | 173 | 0.049724 | 20000 | 999 | {"7":[-3.607954460430093,3.258269761069528],"14":[-3.2317571905440707,3.0989530558291505],"30":[-2.6357281496909426,2.7539347245575656]} | {"20":[-3.3868580780661817,3.165854687740786],"50":[-3.0114612646095993,2.8926957324360014]} | -0.609682 | -1.110991 | -2.329787 | 0.536332 | 0.571429 | 4 | 7 | 5.203000 |
| 1h | 60 | 30 | E2 | nan | True | DEV | 4383 | 1450 | 0.330824 | 163 | 1 | 1287 | 827 | 460 | -6.918623 | -4.478738 | -5721.700836 | -2060.219370 | -7781.920206 | -6.046558 | MEASURABLE |  | 1.722775 | -10.940101 | -1.024359 | 1819 | 718 | 0.605278 | 20000 | 999 | {"7":[-10.823498820508696,-1.3565890434185706],"14":[-11.37297295129345,-1.0333989084041253],"30":[-11.058534822600645,-0.7543243792023553]} | {"20":[-10.440127883424022,-0.848751757283841],"50":[-11.09252154928731,0.31468979072093717]} | -6.429728 | -6.769624 | -7.612368 | 0.470085 | 0.322034 | 19 | 59 | -11.513500 |
| 1h | 60 | 30 | E2 | nan | True | HOLD_B | 418 | 123 | 0.294258 | 13 | 1 | 110 | 75 | 35 | 1.840850 | 24.501555 | 138.063749 | 857.554428 | 995.618177 | 9.051074 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 66 | 0.635359 | 0 | 999 | {"7":[-3.8806562525597847,22.02067444314882],"14":[-3.083515301333657,20.70246598616623],"30":[-1.5126487855644797,18.80063811828598]} | {"20":[-3.910006281464325,20.769623260536857],"50":[-0.7609476029059703,19.13811032046506]} | 5.982228 | 3.964840 | -1.826127 | 0.563636 | 0.666667 | 4 | 6 | 4.253100 |
| 1h | 120 | 15 | E0 | nan | False | DEV | 27412 | 27412 | 1.000000 | 11329 | 1 | 16083 | 8641 | 7442 | -2.367093 | -3.175026 | -20454.052570 | -23628.546951 | -44082.599521 | -2.740944 | MEASURABLE |  | 2.817427 | -4.017651 | -1.461539 | 1819 | 1772 | 0.025838 | 20000 | 999 | {"7":[-3.8738885668489296,-1.5291916739949503],"14":[-3.876987813927239,-1.6035937356697472],"30":[-3.909568618360754,-1.6310554417300493]} | {"20":[-3.94722979168888,-1.3414068900707574],"50":[-3.980289139540608,-1.5536855489729489]} | -2.790406 | -2.838187 | -2.966276 | 0.546105 | 0.220339 | 13 | 59 | 105.425100 |
| 1h | 120 | 15 | E0 | nan | False | HOLD_B | 2447 | 2447 | 1.000000 | 950 | 1 | 1497 | 896 | 601 | -4.195022 | -0.012029 | -3758.739674 | -7.229234 | -3765.968908 | -2.515677 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-5.33159510931745,0.9338430447493291],"14":[-5.4525827325519405,0.6735496926273914],"30":[-5.047425947895931,0.16328818016185132]} | {"20":[-5.839581121592829,1.1052947544594338],"50":[-5.501000171283485,0.8739422040477662]} | -2.818246 | -3.068057 | -3.696492 | 0.545758 | 0.285714 | 2 | 7 | 1.398700 |
| 1h | 120 | 15 | E0 | nan | True | DEV | 4808 | 4808 | 1.000000 | 1499 | 1 | 3309 | 2003 | 1306 | 2.456012 | -4.397901 | 4919.391754 | -5743.659122 | -824.267368 | -0.249099 | MEASURABLE |  | 1.399347 | -4.809959 | 4.151471 | 1819 | 1109 | 0.390324 | 20000 | 999 | {"7":[-5.1135930907272265,3.922778290531875],"14":[-5.062248100558337,4.128465441726188],"30":[-4.918088191775221,3.8119339517028497]} | {"20":[-4.6382394196225265,4.259714898609134],"50":[-4.923874410926642,3.6795007238114703]} | -0.585298 | -0.825179 | -1.467139 | 0.546389 | 0.474576 | 28 | 59 | 86.325400 |
| 1h | 120 | 15 | E0 | nan | True | HOLD_B | 489 | 489 | 1.000000 | 158 | 1 | 331 | 220 | 111 | -2.455548 | 3.560760 | -540.220525 | 395.244368 | -144.976157 | -0.437994 | MEASURABLE |  | 2.910420 | -9.983581 | 9.533118 | 181 | 124 | 0.314917 | 20000 | 999 | {"7":[-9.86454890606661,8.97579005431007],"14":[-11.156070062505576,8.802604978752674],"30":[-10.62681285897505,9.407712862934833]} | {"20":[-10.008765597295989,9.235012104786696],"50":[-9.690634163349426,8.107901068710248]} | -1.803343 | -2.935418 | -5.681107 | 0.537764 | 0.333333 | 2 | 6 | 12.130100 |
| 1h | 120 | 15 | E1 | 0.250000 | False | DEV | 27412 | 22552 | 0.822705 | 12112 | 1 | 10440 | 5667 | 4773 | 0.256292 | -2.031444 | 1452.408848 | -9696.084141 | -8243.675293 | -0.789624 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1771 | 0.026388 | 0 | 999 | {"7":[-2.5664631826424826,0.9580561794075837],"14":[-2.5145462684169795,0.8161658154017859],"30":[-2.5404086602440894,0.8196426648400421]} | {"20":[-2.5770814721035276,0.8893917683298114],"50":[-2.5364097886476387,0.8588477649041468]} | -0.874862 | -0.939351 | -1.125900 | 0.561111 | 0.372881 | 22 | 59 | 12.188700 |
| 1h | 120 | 15 | E1 | 0.250000 | False | HOLD_B | 2447 | 1985 | 0.811197 | 1010 | 1 | 975 | 581 | 394 | -2.704794 | 2.518683 | -1571.485094 | 992.360972 | -579.124122 | -0.593973 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-4.689657629008167,3.020642363622331],"14":[-4.562348664053765,3.080866766393162],"30":[-4.284194382254574,2.741582491286982]} | {"20":[-5.298823027102389,3.7217532048392226],"50":[-4.712330980344539,3.420900123775221]} | -1.045266 | -1.466630 | -2.501966 | 0.550769 | 0.571429 | 4 | 7 | 13.619400 |
| 1h | 120 | 15 | E1 | 0.250000 | True | DEV | 4808 | 4023 | 0.836730 | 1646 | 1 | 2377 | 1431 | 946 | 4.453018 | -3.798527 | 6372.269172 | -3593.406447 | 2778.862726 | 1.169063 | MEASURABLE |  | 1.518076 | -3.580237 | 5.928675 | 1819 | 1053 | 0.421111 | 20000 | 999 | {"7":[-3.3796330110535577,5.928220654371488],"14":[-3.1641748645774634,5.7652534011135845],"30":[-3.6193399659277072,5.59245740523836]} | {"20":[-3.4612312342004103,5.849599725753235],"50":[-3.8657291204037603,5.9889970654455205]} | 0.709431 | 0.335410 | -0.509128 | 0.551956 | 0.525424 | 31 | 59 | -13.316500 |
| 1h | 120 | 15 | E1 | 0.250000 | True | HOLD_B | 489 | 412 | 0.842536 | 170 | 1 | 242 | 154 | 88 | 2.679240 | 11.672710 | 412.602982 | 1027.198507 | 1439.801489 | 5.949593 | MEASURABLE |  | 1.360415 | -8.820268 | 20.139103 | 181 | 118 | 0.348066 | 20000 | 999 | {"7":[-7.427798453502274,19.469450053839733],"14":[-7.590287367128606,18.395984369006868],"30":[-6.7956287405739575,17.21041906914494]} | {"20":[-7.451152463067348,18.46672981674541],"50":[-6.853932140735149,16.63276638118982]} | 3.827623 | 1.730597 | -2.967762 | 0.590909 | 0.500000 | 3 | 6 | 13.748300 |
| 1h | 120 | 15 | E1 | 0.500000 | False | DEV | 27412 | 17830 | 0.650445 | 8673 | 1 | 9157 | 4966 | 4191 | -1.278340 | -2.451747 | -6348.238375 | -10275.272471 | -16623.510846 | -1.815388 | MEASURABLE |  | 1.112310 | -3.846352 | 0.215247 | 1819 | 1767 | 0.028587 | 20000 | 999 | {"7":[-3.6603195800836894,0.0979258057094381],"14":[-3.679799212495272,-0.12267083567623249],"30":[-3.629538352063707,-0.3016339699880666]} | {"20":[-3.7742951857773654,-0.02028634944966856],"50":[-3.59758872466474,-0.019246827107840536]} | -1.883622 | -1.950827 | -2.128129 | 0.560336 | 0.338983 | 20 | 59 | 69.762700 |
| 1h | 120 | 15 | E1 | 0.500000 | False | HOLD_B | 2447 | 1611 | 0.658357 | 756 | 1 | 855 | 522 | 333 | -0.070585 | 0.425266 | -36.845511 | 141.613589 | 104.768077 | 0.122536 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-4.03551269890245,3.8764090211074573],"14":[-3.95094816488465,3.8639366805308626],"30":[-3.4270731037307463,3.4005675924700722]} | {"20":[-3.9611034505138183,4.697907503136639],"50":[-3.753750564510555,4.236149994817872]} | -0.515430 | -0.997447 | -2.064865 | 0.563743 | 0.714286 | 5 | 7 | 12.995400 |
| 1h | 120 | 15 | E1 | 0.500000 | True | DEV | 4808 | 3175 | 0.660358 | 1151 | 1 | 2024 | 1221 | 803 | 4.610385 | -6.008186 | 5629.279892 | -4824.573353 | 804.706539 | 0.397582 | MEASURABLE |  | 8.874389 | -4.376654 | 4.988068 | 1819 | 981 | 0.460693 | 20000 | 999 | {"7":[-4.352899085628905,5.166688314944218],"14":[-3.826313624085257,4.97945346179476],"30":[-4.150008932615521,4.6473372524249115]} | {"20":[-4.26235519700045,5.096721948332721],"50":[-3.610894067734378,4.513238492432083]} | 0.057825 | -0.208321 | -0.927948 | 0.555336 | 0.389831 | 23 | 59 | 18.940300 |
| 1h | 120 | 15 | E1 | 0.500000 | True | HOLD_B | 489 | 340 | 0.695297 | 127 | 1 | 213 | 144 | 69 | 2.244804 | 15.569474 | 323.251825 | 1074.293702 | 1397.545527 | 6.561247 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 113 | 0.375691 | 0 | 999 | {"7":[-6.151476822910295,21.680529376177944],"14":[-6.990092510240407,20.030786645478074],"30":[-4.942753578633273,18.02901896277854]} | {"20":[-5.588325543008601,19.861079528077802],"50":[-3.6368212329735723,17.197907069895862]} | 4.021697 | 1.977859 | -1.469723 | 0.605634 | 0.833333 | 5 | 6 | 14.300200 |
| 1h | 120 | 15 | E1 | 1.000000 | False | DEV | 27412 | 10856 | 0.396031 | 4164 | 1 | 6692 | 3628 | 3064 | -1.218620 | -4.922729 | -4421.151656 | -15083.242768 | -19504.394423 | -2.914584 | MEASURABLE |  | 2.113802 | -5.246749 | -0.591908 | 1819 | 1758 | 0.033535 | 20000 | 999 | {"7":[-4.941287183352529,-0.717897167462374],"14":[-4.82405262115452,-0.9802897187091271],"30":[-4.821642299867703,-1.0758886100666412]} | {"20":[-5.130573617823506,-0.7175078123363807],"50":[-4.920273929284756,-0.8390149291143834]} | -3.027076 | -3.123098 | -3.371873 | 0.568440 | 0.338983 | 20 | 59 | 104.672600 |
| 1h | 120 | 15 | E1 | 1.000000 | False | HOLD_B | 2447 | 1003 | 0.409890 | 368 | 1 | 635 | 381 | 254 | 1.894663 | 4.437295 | 721.866442 | 1127.072811 | 1848.939253 | 2.911715 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 179 | 0.016575 | 0 | 999 | {"7":[-2.8293538495942134,8.322293271579822],"14":[-2.384189255914317,8.399709851041822],"30":[-1.3042223783799467,7.079829606391767]} | {"20":[-2.632376142395263,8.493293914850463],"50":[-2.205325681039556,8.469684690608018]} | 2.016279 | 1.262137 | -0.450095 | 0.560630 | 0.714286 | 5 | 7 | 5.801800 |
| 1h | 120 | 15 | E1 | 1.000000 | True | DEV | 4808 | 1881 | 0.391223 | 523 | 1 | 1358 | 829 | 529 | 11.851530 | -9.196811 | 9824.918405 | -4865.113047 | 4959.805358 | 3.652287 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 802 | 0.559098 | 0 | 999 | {"7":[-3.015234034645863,10.892436201360276],"14":[-2.49644674142824,9.978697045363715],"30":[-1.9386599181292188,9.780071511649982]} | {"20":[-2.5220536610558537,9.97747030946479],"50":[-1.7700164795025661,8.928121728646438]} | 3.125499 | 2.656298 | 1.452397 | 0.565538 | 0.542373 | 32 | 59 | 78.404600 |
| 1h | 120 | 15 | E1 | 1.000000 | True | HOLD_B | 489 | 216 | 0.441718 | 62 | 1 | 154 | 98 | 56 | 1.422696 | 26.598129 | 139.424252 | 1489.495206 | 1628.919458 | 10.577399 | MEASURABLE |  | 1.772948 | -8.522232 | 29.744098 | 181 | 101 | 0.441989 | 20000 | 999 | {"7":[-8.445427685270882,28.87403993410332],"14":[-7.618809461710548,28.50275421114558],"30":[-2.829935010390267,24.61875146432766]} | {"20":[-3.8046595004259274,25.300773606046036],"50":[-0.2858042121436757,22.22395635729785]} | 7.513275 | 4.629920 | -0.914389 | 0.603896 | 0.833333 | 5 | 6 | 8.676100 |
| 1h | 120 | 15 | E2 | nan | False | DEV | 27412 | 17644 | 0.643660 | 8112 | 1 | 9532 | 5145 | 4387 | -5.436549 | -4.041748 | -27971.042350 | -17731.148503 | -45702.190853 | -4.794607 | MEASURABLE |  | 4.837362 | -6.732357 | -2.864216 | 1819 | 1771 | 0.026388 | 20000 | 999 | {"7":[-6.615049633058221,-2.904676453278438],"14":[-6.85988604062608,-2.8221590368666343],"30":[-6.775969695441378,-2.7984247087133567]} | {"20":[-6.684872396173986,-2.908388628830382],"50":[-6.733681373512143,-2.8615528013076483]} | -4.884819 | -4.961076 | -5.168130 | 0.512274 | 0.203390 | 12 | 59 | 61.508700 |
| 1h | 120 | 15 | E2 | nan | False | HOLD_B | 2447 | 1561 | 0.637924 | 677 | 1 | 884 | 506 | 378 | -2.941047 | -3.064510 | -1488.169539 | -1158.384640 | -2646.554179 | -2.993840 | MEASURABLE |  | 1.470340 | -7.228421 | 1.329177 | 181 | 181 | 0.005525 | 20000 | 999 | {"7":[-7.123457149675415,1.5113085811574503],"14":[-7.293258739392842,1.4035949736301965],"30":[-6.900279068974909,1.3748450437509274]} | {"20":[-7.401510267612922,1.4572253150162626],"50":[-7.266309492977884,1.4077845786104324]} | -3.544509 | -3.895661 | -4.786932 | 0.511312 | 0.285714 | 2 | 7 | 4.305600 |
| 1h | 120 | 15 | E2 | nan | True | DEV | 4808 | 3060 | 0.636439 | 1008 | 1 | 2052 | 1248 | 804 | -5.879786 | -8.790469 | -7337.972926 | -7067.536914 | -14405.509841 | -7.020229 | MEASURABLE |  | 3.440053 | -12.760859 | -1.487496 | 1819 | 975 | 0.463991 | 20000 | 999 | {"7":[-12.470323554423242,-1.9611168103146408],"14":[-12.565768464676127,-1.713686595415843],"30":[-12.252780497316117,-1.8697803308031329]} | {"20":[-11.93342845526759,-2.065566112693519],"50":[-11.6299781731169,-2.559266529537255]} | -7.649141 | -8.069957 | -8.880418 | 0.489766 | 0.305085 | 18 | 59 | 16.236800 |
| 1h | 120 | 15 | E2 | nan | True | HOLD_B | 489 | 300 | 0.613497 | 105 | 1 | 195 | 127 | 68 | -1.568005 | 17.947949 | -199.136626 | 1220.460553 | 1021.323927 | 5.237559 | MEASURABLE |  | 1.657469 | -8.190586 | 18.742281 | 181 | 105 | 0.419890 | 20000 | 999 | {"7":[-7.469764567935413,18.83248050461017],"14":[-6.404896981451681,18.982746408409533],"30":[-5.84699260751625,16.182352670481265]} | {"20":[-7.562635792042248,16.80597325309993],"50":[-4.39093206702423,15.344818080053155]} | 3.747711 | 2.289708 | -1.248635 | 0.487179 | 0.666667 | 4 | 6 | 6.345000 |
| 1h | 120 | 30 | E0 | nan | False | DEV | 27412 | 27412 | 1.000000 | 11329 | 1 | 16083 | 8641 | 7442 | -2.367093 | -3.175026 | -20454.052570 | -23628.546951 | -44082.599521 | -2.740944 | MEASURABLE |  | 2.817427 | -4.017651 | -1.461539 | 1819 | 1772 | 0.025838 | 20000 | 999 | {"7":[-3.8738885668489296,-1.5291916739949503],"14":[-3.876987813927239,-1.6035937356697472],"30":[-3.909568618360754,-1.6310554417300493]} | {"20":[-3.94722979168888,-1.3414068900707574],"50":[-3.980289139540608,-1.5536855489729489]} | -2.790406 | -2.838187 | -2.966276 | 0.546105 | 0.220339 | 13 | 59 | 105.425100 |
| 1h | 120 | 30 | E0 | nan | False | HOLD_B | 2447 | 2447 | 1.000000 | 950 | 1 | 1497 | 896 | 601 | -4.195022 | -0.012029 | -3758.739674 | -7.229234 | -3765.968908 | -2.515677 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-5.33159510931745,0.9338430447493291],"14":[-5.4525827325519405,0.6735496926273914],"30":[-5.047425947895931,0.16328818016185132]} | {"20":[-5.839581121592829,1.1052947544594338],"50":[-5.501000171283485,0.8739422040477662]} | -2.818246 | -3.068057 | -3.696492 | 0.545758 | 0.285714 | 2 | 7 | 1.398700 |
| 1h | 120 | 30 | E0 | nan | True | DEV | 4808 | 4808 | 1.000000 | 1499 | 1 | 3309 | 2003 | 1306 | 2.456012 | -4.397901 | 4919.391754 | -5743.659122 | -824.267368 | -0.249099 | MEASURABLE |  | 1.399347 | -4.809959 | 4.151471 | 1819 | 1109 | 0.390324 | 20000 | 999 | {"7":[-5.1135930907272265,3.922778290531875],"14":[-5.062248100558337,4.128465441726188],"30":[-4.918088191775221,3.8119339517028497]} | {"20":[-4.6382394196225265,4.259714898609134],"50":[-4.923874410926642,3.6795007238114703]} | -0.585298 | -0.825179 | -1.467139 | 0.546389 | 0.474576 | 28 | 59 | 86.325400 |
| 1h | 120 | 30 | E0 | nan | True | HOLD_B | 489 | 489 | 1.000000 | 158 | 1 | 331 | 220 | 111 | -2.455548 | 3.560760 | -540.220525 | 395.244368 | -144.976157 | -0.437994 | MEASURABLE |  | 2.910420 | -9.983581 | 9.533118 | 181 | 124 | 0.314917 | 20000 | 999 | {"7":[-9.86454890606661,8.97579005431007],"14":[-11.156070062505576,8.802604978752674],"30":[-10.62681285897505,9.407712862934833]} | {"20":[-10.008765597295989,9.235012104786696],"50":[-9.690634163349426,8.107901068710248]} | -1.803343 | -2.935418 | -5.681107 | 0.537764 | 0.333333 | 2 | 6 | 12.130100 |
| 1h | 120 | 30 | E1 | 0.250000 | False | DEV | 27412 | 20392 | 0.743908 | 10558 | 1 | 9834 | 5345 | 4489 | 0.566528 | -1.939144 | 3028.090354 | -8704.819293 | -5676.728939 | -0.577255 | MEASURABLE |  | 1.766199 | -2.616049 | 1.391809 | 1819 | 1769 | 0.027488 | 20000 | 999 | {"7":[-2.6812879984235463,1.401132318722056],"14":[-2.895109847767961,1.3705553291135475],"30":[-2.855403173297032,1.336068961147845]} | {"20":[-2.58833196449607,1.254702305931421],"50":[-2.689550943147552,1.2656949036328893]} | -0.688898 | -0.777599 | -0.992793 | 0.559487 | 0.372881 | 22 | 59 | 28.409500 |
| 1h | 120 | 30 | E1 | 0.250000 | False | HOLD_B | 2447 | 1809 | 0.739273 | 892 | 1 | 917 | 553 | 364 | -1.173511 | 1.508562 | -648.951630 | 549.116519 | -99.835111 | -0.108871 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-4.770514652695661,4.298187298857003],"14":[-4.531333904591297,4.087911115151555],"30":[-4.270860103363932,4.189559666792459]} | {"20":[-5.066604036936834,4.605414699380435],"50":[-4.631976443789574,4.370201461529493]} | -0.552514 | -0.996697 | -2.133678 | 0.545256 | 0.571429 | 4 | 7 | 14.366000 |
| 1h | 120 | 30 | E1 | 0.250000 | True | DEV | 4808 | 3735 | 0.776830 | 1480 | 1 | 2255 | 1354 | 901 | 4.081003 | -5.519132 | 5525.677656 | -4972.738175 | 552.939480 | 0.245206 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1037 | 0.429907 | 0 | 999 | {"7":[-4.713033943803321,5.635955224149842],"14":[-5.16457390468025,5.552249768779262],"30":[-5.650814500483959,5.477605541071909]} | {"20":[-4.933544722102975,5.483480048912476],"50":[-5.464209867052183,5.651144369413592]} | -0.241466 | -0.628354 | -1.497223 | 0.548115 | 0.457627 | 27 | 59 | -15.662600 |
| 1h | 120 | 30 | E1 | 0.250000 | True | HOLD_B | 489 | 387 | 0.791411 | 156 | 1 | 231 | 151 | 80 | -2.433118 | 12.918216 | -367.400806 | 1033.457282 | 666.056476 | 2.883361 | MEASURABLE |  | 1.317062 | -13.169299 | 19.132999 | 181 | 117 | 0.353591 | 20000 | 999 | {"7":[-11.959608817341463,17.947091475525152],"14":[-13.227890023102622,17.77062844410627],"30":[-12.204492048647394,16.951291843388578]} | {"20":[-13.43169211295419,16.672731202023567],"50":[-11.588619921449709,15.265013935491286]} | 0.798283 | -0.996903 | -5.598147 | 0.571429 | 0.333333 | 2 | 6 | 13.742300 |
| 1h | 120 | 30 | E1 | 0.500000 | False | DEV | 27412 | 14344 | 0.523274 | 6409 | 1 | 7935 | 4342 | 3593 | -0.274774 | -4.489365 | -1193.069435 | -16130.286963 | -17323.356398 | -2.183158 | MEASURABLE |  | 2.175156 | -4.338470 | 0.007099 | 1819 | 1760 | 0.032435 | 20000 | 999 | {"7":[-4.087462282825304,-0.15880808496427035],"14":[-3.969607096157943,-0.297335928099703],"30":[-4.131520721223862,-0.16021132215340383]} | {"20":[-4.236449554533435,-0.24190300580685764],"50":[-4.038569153464423,-0.24302152932835663]} | -2.280180 | -2.360701 | -2.574830 | 0.569628 | 0.338983 | 20 | 59 | 33.393700 |
| 1h | 120 | 30 | E1 | 0.500000 | False | HOLD_B | 2447 | 1305 | 0.533306 | 551 | 1 | 754 | 453 | 301 | -1.715267 | 2.262180 | -777.015825 | 680.916147 | -96.099678 | -0.127453 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-4.914169616279402,4.898861546538623],"14":[-5.004504342998435,4.591575627697868],"30":[-4.072923224859758,4.349828877470624]} | {"20":[-5.040165639981607,4.8565196480136255],"50":[-4.534088283870012,4.856214086350985]} | -0.688837 | -1.235018 | -2.354821 | 0.567639 | 0.428571 | 3 | 7 | 6.051300 |
| 1h | 120 | 30 | E1 | 0.500000 | True | DEV | 4808 | 2717 | 0.565100 | 919 | 1 | 1798 | 1092 | 706 | 5.921543 | -8.177870 | 6466.325145 | -5773.576467 | 692.748678 | 0.385288 | MEASURABLE |  | 1.809658 | -5.542304 | 6.476114 | 1819 | 935 | 0.485981 | 20000 | 999 | {"7":[-5.360478121479261,6.30159116084648],"14":[-5.003665767600312,6.021451592536778],"30":[-4.6229173254300315,5.465098677869722]} | {"20":[-4.928942854906494,6.110465076546245],"50":[-4.203054365114218,5.172153580078207]} | 0.011937 | -0.299919 | -1.096161 | 0.558398 | 0.423729 | 25 | 59 | 28.566900 |
| 1h | 120 | 30 | E1 | 0.500000 | True | HOLD_B | 489 | 300 | 0.613497 | 111 | 1 | 189 | 123 | 66 | -4.206705 | 19.816941 | -517.424696 | 1307.918087 | 790.493391 | 4.182505 | MEASURABLE |  | 2.780447 | -12.562270 | 20.655957 | 181 | 112 | 0.381215 | 20000 | 999 | {"7":[-12.246072103680898,21.20277687635579],"14":[-13.656413369212157,21.040463255452586],"30":[-10.984136354305988,18.939514056235154]} | {"20":[-12.724607690174096,19.475880987377206],"50":[-9.669348794646208,16.498302651770526]} | 1.852738 | -0.330080 | -4.707605 | 0.619048 | 0.666667 | 4 | 6 | 13.215000 |
| 1h | 120 | 30 | E1 | 1.000000 | False | DEV | 27412 | 7036 | 0.256676 | 2223 | 1 | 4813 | 2631 | 2182 | 4.003094 | -4.606700 | 10532.140709 | -10051.819427 | 480.321281 | 0.099797 | MEASURABLE |  | 3.473739 | -2.929931 | 3.112006 | 1819 | 1722 | 0.053326 | 20000 | 999 | {"7":[-2.803140724443338,3.049455641820746],"14":[-2.6673923751909063,3.115575371920919],"30":[-2.894179482871833,2.89939871500265]} | {"20":[-2.891724616214541,2.9901761417962334],"50":[-2.8354556515300318,2.954362917213915]} | -0.078480 | -0.236307 | -0.628387 | 0.576148 | 0.491525 | 29 | 59 | 69.142500 |
| 1h | 120 | 30 | E1 | 1.000000 | False | HOLD_B | 2447 | 699 | 0.285656 | 226 | 1 | 473 | 290 | 183 | 2.583809 | 7.420553 | 749.304604 | 1357.961194 | 2107.265797 | 4.455107 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 174 | 0.044199 | 0 | 999 | {"7":[-2.9431858282702335,12.12899672243615],"14":[-2.787183299881784,12.882524537342835],"30":[-1.7179413781092698,11.210481671302954]} | {"20":[-3.4146608516777555,12.607494890749965],"50":[-2.089304382827317,11.537830693963803]} | 3.317158 | 2.255676 | 0.490085 | 0.560254 | 0.571429 | 4 | 7 | 3.246500 |
| 1h | 120 | 30 | E1 | 1.000000 | True | DEV | 4808 | 1382 | 0.287438 | 344 | 1 | 1038 | 620 | 418 | 14.785052 | -4.856548 | 9166.732382 | -2030.036986 | 7136.695396 | 6.875429 | MEASURABLE |  | 2.228938 | -1.201822 | 15.130942 | 1819 | 693 | 0.619021 | 20000 | 999 | {"7":[-0.710545662493284,15.068175016539055],"14":[-1.4637665463050595,14.81275441338893],"30":[-0.6620558518463362,14.412899264021696]} | {"20":[-1.0015290244051611,15.40757175317111],"50":[-0.628183644061167,14.061182295481284]} | 6.149925 | 5.534042 | 4.075826 | 0.554913 | 0.559322 | 33 | 59 | 44.094400 |
| 1h | 120 | 30 | E1 | 1.000000 | True | HOLD_B | 489 | 177 | 0.361963 | 51 | 1 | 126 | 81 | 45 | -1.563126 | 28.871032 | -126.613173 | 1299.196450 | 1172.583278 | 9.306216 | MEASURABLE |  | 5.529670 | -14.114880 | 33.357600 | 181 | 96 | 0.469613 | 20000 | 999 | {"7":[-12.770694521152604,33.47941044476593],"14":[-12.624542981418548,32.94663916888935],"30":[-9.277903842799455,28.79570417396382]} | {"20":[-9.696554074043432,29.218184662422544],"50":[-4.067559545167683,24.273299864505418]} | 5.354462 | 2.800124 | -3.349514 | 0.634921 | 0.666667 | 4 | 6 | 8.300400 |
| 1h | 120 | 30 | E2 | nan | False | DEV | 27412 | 10344 | 0.377353 | 3282 | 1 | 7062 | 3838 | 3224 | -6.444272 | -3.368458 | -24733.117714 | -10859.907191 | -35593.024905 | -5.040077 | MEASURABLE |  | 1.588690 | -7.033042 | -3.013770 | 1819 | 1763 | 0.030786 | 20000 | 999 | {"7":[-6.848366198268199,-3.3594461875669435],"14":[-6.90658487781988,-3.1649039558622016],"30":[-6.945207594009533,-3.2077776626348147]} | {"20":[-7.105798217887042,-3.1041790125954902],"50":[-6.862566340762806,-3.2707193269511166]} | -5.143020 | -5.245836 | -5.521332 | 0.504673 | 0.305085 | 18 | 59 | -50.329100 |
| 1h | 120 | 30 | E2 | nan | False | HOLD_B | 2447 | 890 | 0.363711 | 251 | 1 | 639 | 377 | 262 | -5.526053 | -2.488870 | -2083.321999 | -652.083890 | -2735.405889 | -4.280760 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 179 | 0.016575 | 0 | 999 | {"7":[-9.732935827073419,1.1814159139092428],"14":[-9.029618521842725,1.1640082739087765],"30":[-8.615566996658314,0.14828082365191975]} | {"20":[-9.64850935288825,1.1760637647809276],"50":[-8.98375871273548,0.8237064162457495]} | -4.819863 | -5.351453 | -6.564038 | 0.478873 | 0.285714 | 2 | 7 | 7.669500 |
| 1h | 120 | 30 | E2 | nan | True | DEV | 4808 | 1672 | 0.347754 | 361 | 1 | 1311 | 813 | 498 | -5.064320 | -3.882055 | -4117.292475 | -1933.263462 | -6050.555937 | -4.615222 | MEASURABLE |  | 1.666356 | -11.934050 | 2.457030 | 1819 | 765 | 0.579439 | 20000 | 999 | {"7":[-12.396056218776007,2.2345035856029973],"14":[-11.775674809962341,1.86098711765211],"30":[-11.46042235900535,2.1621246948233495]} | {"20":[-11.118782383154073,1.9880711996105465],"50":[-11.129870667518105,1.4415785327244217]} | -5.598041 | -6.097635 | -7.484551 | 0.479024 | 0.440678 | 26 | 59 | -23.339000 |
| 1h | 120 | 30 | E2 | nan | True | HOLD_B | 489 | 147 | 0.300613 | 29 | 1 | 118 | 77 | 41 | -0.738069 | -0.459071 | -56.831299 | -18.821899 | -75.653198 | -0.641129 | MEASURABLE |  | 2.162334 | -19.223374 | 21.948779 | 181 | 75 | 0.585635 | 20000 | 999 | {"7":[-18.426873779973597,22.746491625873777],"14":[-17.703100496119525,21.414988090300657],"30":[-16.29218153036318,15.837442745016894]} | {"20":[-18.081096839944077,16.357806490819257],"50":[-13.875632758437458,13.703018251122057]} | -2.557872 | -4.443114 | -9.469423 | 0.542373 | 0.666667 | 4 | 6 | 4.191900 |
| 1h | 240 | 15 | E0 | nan | False | DEV | 30126 | 30126 | 1.000000 | 20855 | 1 | 9271 | 4730 | 4541 | -1.535272 | -2.262378 | -7261.834891 | -10273.457801 | -17535.292692 | -1.891413 | MEASURABLE |  | 3.536131 | -4.255196 | 0.449242 | 1819 | 1773 | 0.025289 | 20000 | 999 | {"7":[-4.096344610509066,0.29360329130853513],"14":[-4.185987335954575,0.3281645051500912],"30":[-4.334754050728488,0.4869820129255462]} | {"20":[-4.088468271506991,0.46518180307855994],"50":[-4.435728948586192,0.3045661448255652]} | -1.988523 | -2.080094 | -2.317598 | 0.542876 | 0.389831 | 23 | 59 | 189.597400 |
| 1h | 240 | 15 | E0 | nan | False | HOLD_B | 2802 | 2802 | 1.000000 | 1897 | 1 | 905 | 559 | 346 | -10.858196 | -3.921396 | -6069.731767 | -1356.802961 | -7426.534727 | -8.206116 | MEASURABLE |  | 2.186200 | -15.252226 | -0.323217 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-15.095439228620972,0.02004279936643094],"14":[-14.7910112789552,0.4570215438741325],"30":[-14.291589875294438,0.08590466332958968]} | {"20":[-15.469120195919544,0.3286381902274478],"50":[-15.041802257758365,0.49874059837150675]} | -8.720099 | -9.204142 | -10.483724 | 0.509392 | 0.285714 | 2 | 7 | 14.940700 |
| 1h | 240 | 15 | E0 | nan | True | DEV | 5018 | 5018 | 1.000000 | 2665 | 1 | 2353 | 1387 | 966 | -1.463124 | -4.892906 | -2029.353245 | -4726.547422 | -6755.900667 | -2.871186 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1110 | 0.389775 | 0 | 999 | {"7":[-9.114694404263076,3.980832167875323],"14":[-9.418882712128593,2.46539166505465],"30":[-9.126740736625864,3.0576523314686703]} | {"20":[-9.960823014962504,3.5547027787110093],"50":[-8.893933745213936,3.2629401550360555]} | -3.440951 | -3.999910 | -4.966996 | 0.533362 | 0.355932 | 21 | 59 | 259.942000 |
| 1h | 240 | 15 | E0 | nan | True | HOLD_B | 512 | 512 | 1.000000 | 279 | 1 | 233 | 156 | 77 | -13.417623 | -3.806054 | -2093.149146 | -293.066176 | -2386.215323 | -10.241267 | MEASURABLE |  | 1.775892 | -27.777367 | 8.249666 | 181 | 120 | 0.337017 | 20000 | 999 | {"7":[-27.954032650781528,9.508568331624586],"14":[-28.653234271166873,9.525480144419197],"30":[-28.579959462104334,9.76741179773049]} | {"20":[-29.63194888210741,7.565586810130023],"50":[-30.18049257624162,6.20904487735393]} | -11.777905 | -13.241568 | -17.406111 | 0.510730 | 0.333333 | 2 | 6 | 7.840700 |
| 1h | 240 | 15 | E1 | 0.250000 | False | DEV | 30126 | 24905 | 0.826695 | 17750 | 1 | 7155 | 3739 | 3416 | 1.196188 | -1.323334 | 4472.546114 | -4520.510603 | -47.964489 | -0.006704 | MEASURABLE |  | 1.134155 | -2.873931 | 2.800422 | 1819 | 1773 | 0.025289 | 20000 | 999 | {"7":[-2.7793161233073906,2.4376007220520046],"14":[-2.824854176826009,2.5591762602316104],"30":[-2.691854942365727,2.773282291978901]} | {"20":[-2.6185598782497266,2.2950159893068776],"50":[-2.6729858400819664,2.521678891008563]} | -0.129337 | -0.247026 | -0.562777 | 0.551782 | 0.474576 | 28 | 59 | 187.337300 |
| 1h | 240 | 15 | E1 | 0.250000 | False | HOLD_B | 2802 | 2272 | 0.810849 | 1580 | 1 | 692 | 405 | 287 | -7.502649 | -1.377149 | -3038.572655 | -395.241861 | -3433.814515 | -4.962160 | MEASURABLE |  | 1.698876 | -12.642747 | 2.759874 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-12.932420435556473,2.9184224255565656],"14":[-11.773531632889036,1.6457760701880355],"30":[-10.752578637177603,1.2842893299819353]} | {"20":[-13.002912804925383,3.248737940008179],"50":[-12.04651649660191,2.5587756305314837]} | -5.696076 | -6.423803 | -7.934746 | 0.530347 | 0.428571 | 3 | 7 | 11.861200 |
| 1h | 240 | 15 | E1 | 0.250000 | True | DEV | 5018 | 4190 | 0.834994 | 2288 | 1 | 1902 | 1140 | 762 | 2.505788 | -3.530067 | 2856.597990 | -2689.911375 | 166.686614 | 0.087638 | MEASURABLE |  | 1.897708 | -6.688726 | 6.809397 | 1819 | 1054 | 0.420561 | 20000 | 999 | {"7":[-6.004385742922331,6.722010274182395],"14":[-5.916818899747282,6.039402741372887],"30":[-6.709306975739345,6.718679068121884]} | {"20":[-7.054153051268534,7.094031954331031],"50":[-6.299814791455155,6.208410664766422]} | -0.336915 | -0.755809 | -1.884398 | 0.542587 | 0.423729 | 25 | 59 | 274.350500 |
| 1h | 240 | 15 | E1 | 0.250000 | True | HOLD_B | 512 | 428 | 0.835938 | 241 | 1 | 187 | 130 | 57 | 0.932565 | 0.522092 | 121.233479 | 29.759266 | 150.992745 | 0.807448 | MEASURABLE |  | 1.273078 | -20.047015 | 21.184860 | 181 | 114 | 0.370166 | 20000 | 999 | {"7":[-19.154940597518678,22.66471041897905],"14":[-20.765069234363843,22.193473617074343],"30":[-21.262094608634456,22.04640765311464]} | {"20":[-21.463768538485922,20.623502870042625],"50":[-20.290836169140867,19.651384634127265]} | -1.670260 | -3.434691 | -8.429836 | 0.502674 | 0.500000 | 3 | 6 | 16.219400 |
| 1h | 240 | 15 | E1 | 0.500000 | False | DEV | 30126 | 19746 | 0.655447 | 13163 | 1 | 6583 | 3417 | 3166 | -1.331845 | -4.211055 | -4550.914158 | -13332.199683 | -17883.113841 | -2.716560 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1773 | 0.025289 | 0 | 999 | {"7":[-5.768266330517855,-0.0494255990014798],"14":[-5.721523934562164,-0.07120908606294174],"30":[-5.6052098538955875,-0.002140386999931465]} | {"20":[-5.618685578557422,0.12745734030001543],"50":[-5.41715534302635,0.04568331715839857]} | -2.880767 | -3.010065 | -3.377676 | 0.548686 | 0.423729 | 25 | 59 | 165.312100 |
| 1h | 240 | 15 | E1 | 0.500000 | False | HOLD_B | 2802 | 1855 | 0.662027 | 1215 | 1 | 640 | 391 | 249 | -6.701893 | -7.032812 | -2620.440150 | -1751.170073 | -4371.610223 | -6.830641 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-12.78504600906856,-0.3815064488256965],"14":[-12.01155419604138,-1.2297645756257465],"30":[-11.000932590020334,-2.1056437620742896]} | {"20":[-13.623105416004503,-0.5288023963965562],"50":[-11.93577787513292,-1.2706855528434966]} | -7.578984 | -8.214195 | -9.740319 | 0.515625 | 0.142857 | 1 | 7 | 9.029400 |
| 1h | 240 | 15 | E1 | 0.500000 | True | DEV | 5018 | 3293 | 0.656238 | 1610 | 1 | 1683 | 1018 | 665 | 6.443385 | -4.449933 | 6559.365626 | -2959.205638 | 3600.159987 | 2.139132 | MEASURABLE |  | 1.280272 | -5.360994 | 9.537667 | 1819 | 985 | 0.458494 | 20000 | 999 | {"7":[-4.292527592417532,9.35267701866062],"14":[-4.697543329896865,8.911238157426723],"30":[-4.847056950998999,9.057621604927524]} | {"20":[-5.452527628026077,9.209411636508458],"50":[-4.067893902325725,8.70682606690373]} | 1.636224 | 1.145463 | -0.312387 | 0.550802 | 0.525424 | 31 | 59 | 212.677100 |
| 1h | 240 | 15 | E1 | 0.500000 | True | HOLD_B | 512 | 356 | 0.695312 | 188 | 1 | 168 | 119 | 49 | 6.031899 | -11.891362 | 717.795973 | -582.676720 | 135.119253 | 0.804281 | MEASURABLE |  | 1.108129 | -20.498572 | 21.619091 | 181 | 111 | 0.386740 | 20000 | 999 | {"7":[-18.289896860669266,19.852434157857644],"14":[-18.55716738978941,19.317672612819663],"30":[-18.547788580736608,19.218452703251444]} | {"20":[-21.05233009272398,18.555898240474562],"50":[-18.329257475655094,17.471771359480908]} | -2.017996 | -4.052081 | -9.442910 | 0.523810 | 0.500000 | 3 | 6 | 13.021500 |
| 1h | 240 | 15 | E1 | 1.000000 | False | DEV | 30126 | 12001 | 0.398360 | 6652 | 1 | 5349 | 2734 | 2615 | -2.687367 | -4.060772 | -7347.261203 | -10618.919081 | -17966.180283 | -3.358792 | MEASURABLE |  | 1.212864 | -6.783151 | 0.029780 | 1819 | 1770 | 0.026938 | 20000 | 999 | {"7":[-6.858305968374427,0.022922652722094483],"14":[-6.674570620496755,0.004730408313669887],"30":[-6.508161434564631,-0.09336434013216177]} | {"20":[-6.769970305398233,0.00660150524715597],"50":[-6.499020626734364,-0.2905488758812904]} | -3.544528 | -3.699005 | -4.101955 | 0.569452 | 0.389831 | 23 | 59 | 132.408500 |
| 1h | 240 | 15 | E1 | 1.000000 | False | HOLD_B | 2802 | 1139 | 0.406495 | 627 | 1 | 512 | 303 | 209 | -7.034687 | -3.838771 | -2131.510312 | -802.303049 | -2933.813361 | -5.730104 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 181 | 0.005525 | 0 | 999 | {"7":[-13.5944567495118,2.844476433677822],"14":[-12.915803259128566,3.348591710706404],"30":[-12.109924906623228,2.0235570183497202]} | {"20":[-14.006499025255664,3.6709132705168885],"50":[-13.19802162864826,2.482926618014667]} | -6.705468 | -7.571640 | -9.694440 | 0.541016 | 0.428571 | 3 | 7 | 13.356000 |
| 1h | 240 | 15 | E1 | 1.000000 | True | DEV | 5018 | 1951 | 0.388800 | 745 | 1 | 1206 | 728 | 478 | 10.878795 | -9.293680 | 7919.762490 | -4442.378873 | 3477.383617 | 2.883403 | MEASURABLE |  | 1.910493 | -6.315756 | 12.081606 | 1819 | 820 | 0.549203 | 20000 | 999 | {"7":[-6.170936434244984,12.619054418096752],"14":[-5.8933297848802155,11.443402609581842],"30":[-6.386923180846427,11.936587943785069]} | {"20":[-6.672184973162663,12.971171097155864],"50":[-5.939820906139971,11.592888167643828]} | 2.064258 | 1.359941 | -0.676646 | 0.553897 | 0.610169 | 36 | 59 | 202.882300 |
| 1h | 240 | 15 | E1 | 1.000000 | True | HOLD_B | 512 | 230 | 0.449219 | 93 | 1 | 137 | 91 | 46 | -4.812311 | -2.249171 | -437.920340 | -103.461858 | -541.382198 | -3.951695 | MEASURABLE |  | 1.146370 | -29.683057 | 22.562791 | 181 | 99 | 0.453039 | 20000 | 999 | {"7":[-27.635580493937614,20.252507339752036],"14":[-26.50804272953,21.9580170898175],"30":[-24.069231436980147,19.875352996651287]} | {"20":[-20.60964763353471,14.807292007949847],"50":[-20.246565110000173,13.796303343831362]} | -7.606594 | -10.141011 | -16.403566 | 0.554745 | 0.500000 | 3 | 6 | 12.289100 |
| 1h | 240 | 15 | E2 | nan | False | DEV | 30126 | 19323 | 0.641406 | 12602 | 1 | 6721 | 3384 | 3337 | -1.990269 | -4.140473 | -6735.069537 | -13816.756862 | -20551.826399 | -3.057852 | MEASURABLE |  | 1.260624 | -5.847439 | -0.262568 | 1819 | 1773 | 0.025289 | 20000 | 999 | {"7":[-5.693715920402366,-0.3720123714024899],"14":[-5.515252264551743,-0.6557569724347112],"30":[-5.69169564757909,-0.6393525193585483]} | {"20":[-5.881677806914199,-0.24787273333228654],"50":[-5.730462366536216,-0.6217792916392129]} | -3.226982 | -3.343838 | -3.657413 | 0.519566 | 0.406780 | 24 | 59 | 18.013200 |
| 1h | 240 | 15 | E2 | nan | False | HOLD_B | 2802 | 1798 | 0.641685 | 1132 | 1 | 666 | 407 | 259 | -5.133373 | -1.812457 | -2089.282959 | -469.426447 | -2558.709405 | -3.841906 | MEASURABLE |  | 1.440373 | -11.614883 | 4.072009 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-11.08091489116264,3.6134898593615765],"14":[-10.525424011047297,2.584351869179191],"30":[-9.091576939405408,1.7126132663250142]} | {"20":[-10.827372583759495,3.324990108897462],"50":[-10.174930264194249,2.5775681699776034]} | -4.409993 | -4.928473 | -6.411098 | 0.507508 | 0.285714 | 2 | 7 | 10.373800 |
| 1h | 240 | 15 | E2 | nan | True | DEV | 5018 | 3158 | 0.629334 | 1482 | 1 | 1676 | 1010 | 666 | -6.072348 | -10.471420 | -6133.071296 | -6973.965959 | -13107.037255 | -7.820428 | MEASURABLE |  | 1.141956 | -14.765192 | -0.835779 | 1819 | 986 | 0.457944 | 20000 | 999 | {"7":[-14.453732751602017,-0.6758054772735758],"14":[-14.264735073122965,-1.5269712941668976],"30":[-14.696018698925815,-1.1924622568072856]} | {"20":[-14.240436997572214,-0.9881700313555815],"50":[-13.546756515221553,-1.9191244012645674]} | -8.237457 | -8.631131 | -9.721606 | 0.501790 | 0.338983 | 20 | 59 | 170.634400 |
| 1h | 240 | 15 | E2 | nan | True | HOLD_B | 512 | 316 | 0.617188 | 156 | 1 | 160 | 111 | 49 | -12.982393 | -14.041189 | -1441.045593 | -688.018255 | -2129.063847 | -13.306649 | MEASURABLE |  | 1.596419 | -36.487217 | 12.460575 | 181 | 106 | 0.414365 | 20000 | 999 | {"7":[-37.4941841984126,12.58871181384087],"14":[-37.425019913196806,13.931386889297272],"30":[-35.28464475030776,11.154434308369058]} | {"20":[-35.540419214852975,9.709030653849322],"50":[-33.43690863674256,4.965480243366102]} | -15.527827 | -17.461948 | -22.943676 | 0.493750 | 0.166667 | 1 | 6 | 5.828200 |
| 1h | 240 | 30 | E0 | nan | False | DEV | 30126 | 30126 | 1.000000 | 20855 | 1 | 9271 | 4730 | 4541 | -1.535272 | -2.262378 | -7261.834891 | -10273.457801 | -17535.292692 | -1.891413 | MEASURABLE |  | 3.536131 | -4.255196 | 0.449242 | 1819 | 1773 | 0.025289 | 20000 | 999 | {"7":[-4.096344610509066,0.29360329130853513],"14":[-4.185987335954575,0.3281645051500912],"30":[-4.334754050728488,0.4869820129255462]} | {"20":[-4.088468271506991,0.46518180307855994],"50":[-4.435728948586192,0.3045661448255652]} | -1.988523 | -2.080094 | -2.317598 | 0.542876 | 0.389831 | 23 | 59 | 189.597400 |
| 1h | 240 | 30 | E0 | nan | False | HOLD_B | 2802 | 2802 | 1.000000 | 1897 | 1 | 905 | 559 | 346 | -10.858196 | -3.921396 | -6069.731767 | -1356.802961 | -7426.534727 | -8.206116 | MEASURABLE |  | 2.186200 | -15.252226 | -0.323217 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-15.095439228620972,0.02004279936643094],"14":[-14.7910112789552,0.4570215438741325],"30":[-14.291589875294438,0.08590466332958968]} | {"20":[-15.469120195919544,0.3286381902274478],"50":[-15.041802257758365,0.49874059837150675]} | -8.720099 | -9.204142 | -10.483724 | 0.509392 | 0.285714 | 2 | 7 | 14.940700 |
| 1h | 240 | 30 | E0 | nan | True | DEV | 5018 | 5018 | 1.000000 | 2665 | 1 | 2353 | 1387 | 966 | -1.463124 | -4.892906 | -2029.353245 | -4726.547422 | -6755.900667 | -2.871186 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1110 | 0.389775 | 0 | 999 | {"7":[-9.114694404263076,3.980832167875323],"14":[-9.418882712128593,2.46539166505465],"30":[-9.126740736625864,3.0576523314686703]} | {"20":[-9.960823014962504,3.5547027787110093],"50":[-8.893933745213936,3.2629401550360555]} | -3.440951 | -3.999910 | -4.966996 | 0.533362 | 0.355932 | 21 | 59 | 259.942000 |
| 1h | 240 | 30 | E0 | nan | True | HOLD_B | 512 | 512 | 1.000000 | 279 | 1 | 233 | 156 | 77 | -13.417623 | -3.806054 | -2093.149146 | -293.066176 | -2386.215323 | -10.241267 | MEASURABLE |  | 1.775892 | -27.777367 | 8.249666 | 181 | 120 | 0.337017 | 20000 | 999 | {"7":[-27.954032650781528,9.508568331624586],"14":[-28.653234271166873,9.525480144419197],"30":[-28.579959462104334,9.76741179773049]} | {"20":[-29.63194888210741,7.565586810130023],"50":[-30.18049257624162,6.20904487735393]} | -11.777905 | -13.241568 | -17.406111 | 0.510730 | 0.333333 | 2 | 6 | 7.840700 |
| 1h | 240 | 30 | E1 | 0.250000 | False | DEV | 30126 | 22582 | 0.749585 | 15697 | 1 | 6885 | 3581 | 3304 | 0.238230 | -2.753012 | 853.100082 | -9095.952453 | -8242.852371 | -1.197219 | MEASURABLE |  | 1.346762 | -4.222869 | 1.772760 | 1819 | 1773 | 0.025289 | 20000 | 999 | {"7":[-4.095509189145767,1.621884846496124],"14":[-3.973819154908082,1.665498507522336],"30":[-3.930101258699528,1.444568610400117]} | {"20":[-3.8242820918822007,1.7302099242443654],"50":[-3.920007414958777,1.4539920918609557]} | -1.351744 | -1.476388 | -1.826883 | 0.555265 | 0.440678 | 26 | 59 | 149.279400 |
| 1h | 240 | 30 | E1 | 0.250000 | False | HOLD_B | 2802 | 2068 | 0.738044 | 1404 | 1 | 664 | 404 | 260 | -10.656384 | -7.515721 | -4305.178947 | -1954.087546 | -6259.266492 | -9.426606 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 182 | 0.000000 | 0 | 999 | {"7":[-16.47661112478708,-2.5009775050986685],"14":[-14.84721101954182,-3.7801774956371545],"30":[-13.521449452044717,-4.52634867149203]} | {"20":[-16.09253593155468,-2.6340573478280387],"50":[-15.500358342709871,-3.360895502425697]} | -10.247711 | -10.968284 | -12.539861 | 0.518072 | 0.285714 | 2 | 7 | 7.111000 |
| 1h | 240 | 30 | E1 | 0.250000 | True | DEV | 5018 | 3910 | 0.779195 | 2085 | 1 | 1825 | 1101 | 724 | 4.300954 | -5.923558 | 4735.350630 | -4288.656064 | 446.694566 | 0.244764 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1036 | 0.430456 | 0 | 999 | {"7":[-6.709754681871006,7.606867747102081],"14":[-6.683206467000616,6.695637120247254],"30":[-6.707053531956684,6.964729937796768]} | {"20":[-6.793269359609861,6.923478554056177],"50":[-6.563832771187582,6.729062790361967]} | -0.215488 | -0.653576 | -1.923584 | 0.547945 | 0.440678 | 26 | 59 | 249.807100 |
| 1h | 240 | 30 | E1 | 0.250000 | True | HOLD_B | 512 | 403 | 0.787109 | 224 | 1 | 179 | 129 | 50 | 0.442316 | -23.853493 | 57.058721 | -1192.674636 | -1135.615915 | -6.344223 | MEASURABLE |  | 1.272122 | -27.910547 | 14.934961 | 181 | 114 | 0.370166 | 20000 | 999 | {"7":[-26.33496236329111,13.953265053982282],"14":[-26.498939266716903,12.137086973257265],"30":[-26.323995468391274,12.251438850222836]} | {"20":[-26.719511604509847,11.986107573620853],"50":[-24.927606713294356,10.21063349019515]} | -8.788848 | -10.574630 | -15.312322 | 0.469274 | 0.333333 | 2 | 6 | 13.839300 |
| 1h | 240 | 30 | E1 | 0.500000 | False | DEV | 30126 | 15844 | 0.525924 | 9869 | 1 | 5975 | 3103 | 2872 | -1.564559 | -3.959877 | -4854.825028 | -11372.766599 | -16227.591627 | -2.715915 | MEASURABLE |  | 1.935333 | -5.936926 | 0.483507 | 1819 | 1772 | 0.025838 | 20000 | 999 | {"7":[-5.763618708338498,0.24773542170396778],"14":[-5.53145081860899,0.2599042327082497],"30":[-5.536869503904584,0.2250013426433375]} | {"20":[-5.713438816599794,0.3207932789030892],"50":[-5.567934325910324,0.17139685058873377]} | -2.873726 | -3.015352 | -3.409688 | 0.556485 | 0.355932 | 21 | 59 | 98.344900 |
| 1h | 240 | 30 | E1 | 0.500000 | False | HOLD_B | 2802 | 1491 | 0.532120 | 907 | 1 | 584 | 347 | 237 | -7.201921 | -8.358709 | -2499.066717 | -1981.013916 | -4480.080633 | -7.671371 | MEASURABLE |  | 1.523549 | -16.008161 | 1.110824 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-15.00053178246171,-0.3914105413983675],"14":[-14.728889072002184,0.9117847946052073],"30":[-13.701746211430919,0.39375607507063215]} | {"20":[-15.19670232769537,0.5305223589348067],"50":[-14.469114152852969,1.271230678675149]} | -8.513807 | -9.167556 | -10.783341 | 0.529110 | 0.428571 | 3 | 7 | 13.938000 |
| 1h | 240 | 30 | E1 | 0.500000 | True | DEV | 5018 | 2850 | 0.567955 | 1321 | 1 | 1529 | 926 | 603 | 6.319796 | -7.552252 | 5852.131020 | -4554.007820 | 1298.123201 | 0.849001 | MEASURABLE |  | 2.040643 | -7.421998 | 9.012964 | 1819 | 952 | 0.476636 | 20000 | 999 | {"7":[-7.184801986561387,8.89574651633604],"14":[-6.973885603811455,8.572983702544546],"30":[-6.9582414762467035,8.362269824707655]} | {"20":[-6.79745208498148,8.563165461661168],"50":[-7.184581943432817,7.944803438563747]} | 0.208659 | -0.406822 | -2.031040 | 0.551995 | 0.542373 | 32 | 59 | 183.338900 |
| 1h | 240 | 30 | E1 | 0.500000 | True | HOLD_B | 512 | 316 | 0.617188 | 161 | 1 | 155 | 108 | 47 | -10.526578 | -15.342142 | -1136.870429 | -721.080671 | -1857.951100 | -11.986781 | MEASURABLE |  | 1.798145 | -35.625474 | 14.469075 | 181 | 108 | 0.403315 | 20000 | 999 | {"7":[-33.784286032672284,13.236387912811075],"14":[-34.20834385661675,14.632359989631887],"30":[-35.15475420102974,14.603588909369769]} | {"20":[-31.719856716650888,9.72997379639849],"50":[-30.85341628367942,7.524159957962905]} | -14.950587 | -17.147357 | -22.682862 | 0.529032 | 0.333333 | 2 | 6 | 8.770000 |
| 1h | 240 | 30 | E1 | 1.000000 | False | DEV | 30126 | 7710 | 0.255925 | 3604 | 1 | 4106 | 2126 | 1980 | 2.455258 | -1.857513 | 5219.878566 | -3677.875878 | 1542.002688 | 0.375549 | MEASURABLE |  | 2.364248 | -4.292064 | 4.886857 | 1819 | 1745 | 0.040682 | 20000 | 999 | {"7":[-4.3313991917169306,5.02132352506437],"14":[-4.356433271902014,4.649732553744748],"30":[-4.706551465163294,5.025663467964235]} | {"20":[-4.4562443397373785,4.999927871711635],"50":[-4.47584284943509,4.846960555391718]} | 0.096388 | -0.133275 | -0.753546 | 0.572820 | 0.440678 | 26 | 59 | 50.343300 |
| 1h | 240 | 30 | E1 | 1.000000 | False | HOLD_B | 2802 | 802 | 0.286224 | 393 | 1 | 409 | 247 | 162 | -7.035661 | -8.330087 | -1737.808314 | -1349.474121 | -3087.282435 | -7.548368 | MEASURABLE |  | 1.582767 | -19.736348 | 5.365108 | 181 | 178 | 0.022099 | 20000 | 999 | {"7":[-19.26081366219055,5.505553809997689],"14":[-18.70359527102501,5.584406381045069],"30":[-18.273524872449805,4.645075340645674]} | {"20":[-18.948330804522897,5.421134340231541],"50":[-18.143225844011322,4.980047514091465]} | -8.938612 | -10.251108 | -12.893166 | 0.533007 | 0.428571 | 3 | 7 | 12.483300 |
| 1h | 240 | 30 | E1 | 1.000000 | True | DEV | 5018 | 1449 | 0.288760 | 500 | 1 | 949 | 567 | 382 | 8.476016 | -11.172800 | 4805.901062 | -4268.009491 | 537.891571 | 0.566798 | MEASURABLE |  | 1.516189 | -11.102019 | 12.161710 | 1819 | 723 | 0.602529 | 20000 | 999 | {"7":[-10.36957052492412,12.577665717298897],"14":[-10.965504663050176,11.032675714870141],"30":[-10.165102652806297,11.532466311661638]} | {"20":[-9.731212469159725,10.928672969594468],"50":[-9.709356322047457,10.627271706323022]} | -0.641811 | -1.521025 | -4.064069 | 0.546891 | 0.542373 | 32 | 59 | 136.063100 |
| 1h | 240 | 30 | E1 | 1.000000 | True | HOLD_B | 512 | 194 | 0.378906 | 71 | 1 | 123 | 79 | 44 | -17.556045 | -3.171065 | -1386.927527 | -139.526860 | -1526.454388 | -12.410198 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 97 | 0.464088 | 0 | 999 | {"7":[-36.45058570324839,12.991076718114044],"14":[-35.70005743728289,17.35436258882158],"30":[-35.149850741220575,15.502481941860069]} | {"20":[-32.76959354383504,12.692214138698006],"50":[-31.879470244383448,9.571636055494455]} | -15.370592 | -17.698633 | -23.552486 | 0.577236 | 0.500000 | 3 | 6 | 12.426600 |
| 1h | 240 | 30 | E2 | nan | False | DEV | 30126 | 11387 | 0.377979 | 5865 | 1 | 5522 | 2833 | 2689 | -2.267901 | -2.678513 | -6424.964588 | -7202.521386 | -13627.485974 | -2.467853 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1769 | 0.027488 | 0 | 999 | {"7":[-5.353584794278577,0.4547351258518044],"14":[-5.077108339971144,-0.06294368951049778],"30":[-5.020600991150014,-0.13414735793261068]} | {"20":[-5.4062091891653274,0.5709049576444798],"50":[-5.189148110996158,0.11377091716192655]} | -2.647736 | -2.788371 | -3.136884 | 0.513039 | 0.355932 | 21 | 59 | -18.416000 |
| 1h | 240 | 30 | E2 | nan | False | HOLD_B | 2802 | 1052 | 0.375446 | 513 | 1 | 539 | 340 | 199 | -3.348441 | 1.435165 | -1138.469864 | 285.597820 | -852.872044 | -1.582323 | MEASURABLE |  | 1.135982 | -9.849739 | 6.756207 | 181 | 182 | 0.000000 | 20000 | 999 | {"7":[-9.745028210036631,5.708184739778522],"14":[-8.548948909596268,4.620569147087826],"30":[-6.97496234381098,3.80796280643939]} | {"20":[-9.28679069246954,5.7040239490563565],"50":[-8.07337254694167,5.0984422476128275]} | -2.360850 | -2.953962 | -4.609872 | 0.532468 | 0.428571 | 3 | 7 | 6.176500 |
| 1h | 240 | 30 | E2 | nan | True | DEV | 5018 | 1777 | 0.354125 | 598 | 1 | 1179 | 728 | 451 | -10.361178 | -2.848423 | -7542.937401 | -1284.638984 | -8827.576385 | -7.487342 | MEASURABLE |  | 1.434986 | -16.552949 | 1.772209 | 1819 | 787 | 0.567345 | 20000 | 999 | {"7":[-15.85260287765893,1.6493493410981426],"14":[-15.863845774342582,1.463486265449557],"30":[-15.859368631366909,1.6501851420277713]} | {"20":[-15.015236490980898,0.6368611947496117],"50":[-16.18541340587217,0.5444557451331349]} | -8.019007 | -8.545724 | -10.099722 | 0.497880 | 0.338983 | 20 | 59 | 78.001600 |
| 1h | 240 | 30 | E2 | nan | True | HOLD_B | 512 | 161 | 0.314453 | 50 | 1 | 111 | 78 | 33 | -15.662075 | 4.548497 | -1221.641873 | 150.100415 | -1071.541458 | -9.653527 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 81 | 0.552486 | 0 | 999 | {"7":[-35.08023009011821,14.67282488079903],"14":[-33.11128391028002,14.945872681550057],"30":[-30.814325471695707,14.552813050704277]} | {"20":[-31.92279002082769,11.148912614358938],"50":[-27.494612778415725,7.689974282235777]} | -12.091583 | -14.541009 | -20.296199 | 0.603604 | 0.333333 | 2 | 6 | 1.519700 |
| 4h | 240 | 15 | E0 | nan | False | DEV | 7279 | 7279 | 1.000000 | 0 | 1 | 7279 | 3632 | 3647 | -0.070763 | -3.248055 | -257.010119 | -11845.654948 | -12102.665066 | -1.662682 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1642 | 0.097306 | 0 | 999 | {"7":[-4.104665454036185,0.868008583423608],"14":[-4.225908317221898,0.7925279398123537],"30":[-4.008579412928777,0.6141722524419209]} | {"20":[-4.234547985213587,0.8347747322726786],"50":[-4.24116317182544,0.9560040358081865]} | -1.766669 | -1.869788 | -2.163535 | 0.548702 | 0.436364 | 24 | 55 | -48.932800 |
| 4h | 240 | 15 | E0 | nan | False | HOLD_B | 759 | 759 | 1.000000 | 0 | 1 | 759 | 451 | 308 | -7.781207 | -3.652973 | -3509.324550 | -1125.115767 | -4634.440317 | -6.105982 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 181 | 181 | 0.005525 | 0 | 999 | {"7":[-13.392909411152022,1.7024274244150464],"14":[-13.650226863741073,2.207354675380718],"30":[-13.436431713928807,2.26207933566283]} | {"20":[-13.38582887378407,1.9040029220663817],"50":[-13.661068673944389,1.7279798904153756]} | -6.661070 | -7.192095 | -8.375827 | 0.519104 | 0.428571 | 3 | 7 | 0.881100 |
| 4h | 240 | 15 | E0 | nan | True | DEV | 1148 | 1148 | 1.000000 | 0 | 1 | 1148 | 689 | 459 | -4.082548 | -12.516479 | -2812.875735 | -5745.063662 | -8557.939398 | -7.454651 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 673 | 0.630016 | 0 | 999 | {"7":[-16.046418411039323,1.0482562647235811],"14":[-15.139627721060727,1.2325028066326622],"30":[-14.737214044551092,0.39376330161145656]} | {"20":[-15.038941539216806,-0.06203989184730219],"50":[-13.703894499459148,-0.19462374584928188]} | -8.023448 | -8.576146 | -10.009043 | 0.530488 | 0.444444 | 24 | 54 | 65.615700 |
| 4h | 240 | 15 | E0 | nan | True | HOLD_B | 125 | 125 | 1.000000 | 0 | 1 | 125 | 85 | 40 | 5.960221 | -32.071825 | 506.618797 | -1282.873005 | -776.254209 | -6.210034 | MEASURABLE |  | 3.829104 | -26.386682 | 13.834060 | 181 | 84 | 0.535912 | 20000 | 999 | {"7":[-24.773999909691135,11.913225327128353],"14":[-23.97975314091118,10.890692896674581],"30":[-21.585911827863022,12.251153529120758]} | {"20":[-25.857377975766695,13.078158721437516],"50":[-22.272226938851418,9.45708649910444]} | -8.695044 | -10.970823 | -17.080178 | 0.472000 | 0.333333 | 2 | 6 | 1.518600 |
| 4h | 240 | 15 | E1 | 0.250000 | False | DEV | 7279 | 6722 | 0.923478 | 2741 | 1 | 3981 | 1992 | 1989 | -0.475047 | -2.360075 | -946.293379 | -4694.188355 | -5640.481734 | -1.416850 | UNMEASURABLE | invalid Politis-White block length | nan | nan | nan | 1819 | 1638 | 0.099505 | 0 | 999 | {"7":[-5.178970985892782,2.218970587301211],"14":[-5.122970094580504,2.03526670952302],"30":[-5.10861257204321,2.0537267782387003]} | {"20":[-5.2745281896319876,2.276977426420995],"50":[-5.10205788407133,2.2587309524033437]} | -1.608383 | -1.793454 | -2.296730 | 0.561919 | 0.472727 | 26 | 55 | -28.707200 |
| 4h | 240 | 15 | E1 | 0.250000 | False | HOLD_B | 759 | 688 | 0.906456 | 266 | 1 | 422 | 248 | 174 | -21.470186 | -14.410191 | -5324.606092 | -2507.373270 | -7831.979362 | -18.559193 | MEASURABLE |  | 1.573541 | -29.533174 | -6.389907 | 181 | 178 | 0.022099 | 20000 | 999 | {"7":[-30.5879508932057,-4.8499338709938264],"14":[-31.181331099037195,-4.308741397537606],"30":[-30.765211466131547,-3.9086335785473096]} | {"20":[-30.98716963575111,-5.752543559503346],"50":[-31.95737271807821,-2.9668952149876304]} | -19.302429 | -20.034572 | -21.945723 | 0.490521 | 0.142857 | 1 | 7 | 4.635500 |
| 4h | 240 | 15 | E1 | 0.250000 | True | DEV | 1148 | 1044 | 0.909408 | 229 | 1 | 815 | 500 | 315 | -1.674837 | -9.142961 | -837.418562 | -2880.032729 | -3717.451292 | -4.561290 | MEASURABLE |  | 1.946791 | -14.483668 | 5.501758 | 1819 | 626 | 0.655855 | 20000 | 999 | {"7":[-14.12616276546066,5.858323258289729],"14":[-13.760531486869517,6.303629903236529],"30":[-14.305987364033498,5.894152098995462]} | {"20":[-14.363813606508877,5.462883853323375],"50":[-13.056948422357294,4.290050877832839]} | -5.484827 | -6.365339 | -8.624923 | 0.541104 | 0.481481 | 26 | 54 | 48.140500 |
| 4h | 240 | 15 | E1 | 0.250000 | True | HOLD_B | 125 | 118 | 0.944000 | 18 | 1 | 100 | 67 | 33 | 2.672680 | -21.067308 | 179.069550 | -695.221173 | -516.151623 | -5.161516 | MEASURABLE |  | 2.272071 | -32.249556 | 24.090096 | 181 | 82 | 0.546961 | 20000 | 999 | {"7":[-30.533965403286782,20.99260002460122],"14":[-27.5260215358024,19.469850916698473],"30":[-24.06480702177284,16.797145511935774]} | {"20":[-25.906501318387903,16.015534994413855],"50":[-22.422879085465972,10.485291464371969]} | -8.863789 | -11.957736 | -19.984454 | 0.520000 | 0.333333 | 2 | 6 | -1.151500 |
| 4h | 240 | 15 | E1 | 0.500000 | False | DEV | 7279 | 6063 | 0.832944 | 2318 | 1 | 3745 | 1858 | 1887 | 3.830687 | -0.635923 | 7117.416197 | -1199.986779 | 5917.429417 | 1.580088 | MEASURABLE |  | 1.649264 | -2.345860 | 5.470308 | 1819 | 1628 | 0.105003 | 20000 | 999 | {"7":[-2.280662798493073,5.5080495672684915],"14":[-2.0684636438341117,5.118057485706066],"30":[-1.9733785708747977,5.2533706269631315]} | {"20":[-1.9786818541148905,5.238734985617796],"50":[-1.9655453982260174,5.4421822334633525]} | 1.387143 | 1.203986 | 0.730603 | 0.570360 | 0.527273 | 29 | 55 | -41.421600 |
| 4h | 240 | 15 | E1 | 0.500000 | False | HOLD_B | 759 | 625 | 0.823452 | 225 | 1 | 400 | 239 | 161 | -19.697333 | -10.893616 | -4707.662658 | -1753.872170 | -6461.534828 | -16.153837 | MEASURABLE |  | 2.337602 | -26.764075 | -4.575097 | 181 | 178 | 0.022099 | 20000 | 999 | {"7":[-26.311778474532105,-4.2619667785006445],"14":[-26.708802700314344,-3.944861438290882],"30":[-26.54006014179749,-4.336680395918526]} | {"20":[-26.473523400408098,-5.207928901368774],"50":[-26.63787531238902,-4.171273012630429]} | -17.205059 | -18.247497 | -20.358420 | 0.480000 | 0.142857 | 1 | 7 | 9.709700 |
| 4h | 240 | 15 | E1 | 0.500000 | True | DEV | 1148 | 943 | 0.821429 | 192 | 1 | 751 | 458 | 293 | 3.621816 | -7.291507 | 1658.791853 | -2136.411654 | -477.619801 | -0.635978 | MEASURABLE |  | 1.834986 | -10.578534 | 9.515919 | 1819 | 586 | 0.677845 | 20000 | 999 | {"7":[-10.763732841504162,9.503686650063457],"14":[-10.197364018948974,9.135085971298704],"30":[-9.76315546161793,9.161619950255712]} | {"20":[-9.915326086152424,8.565370192746393],"50":[-8.638883842855373,7.580889455849506]} | -1.715105 | -2.683973 | -5.233591 | 0.557923 | 0.500000 | 27 | 54 | 36.972800 |
| 4h | 240 | 15 | E1 | 0.500000 | True | HOLD_B | 125 | 107 | 0.856000 | 14 | 1 | 93 | 63 | 30 | 13.319022 | -9.869899 | 839.098393 | -296.096956 | 543.001438 | 5.838725 | MEASURABLE |  | 2.446113 | -18.718762 | 32.492581 | 181 | 77 | 0.574586 | 20000 | 999 | {"7":[-18.193309452711915,30.597435635926765],"14":[-15.720428717613617,29.781845937563588],"30":[-14.796678411530847,28.543570305014725]} | {"20":[-15.696145961664024,28.24944655982909],"50":[-13.864290864296555,25.43823103764266]} | 1.725695 | -1.390093 | -9.138470 | 0.516129 | 0.500000 | 3 | 6 | 0.149000 |
| 4h | 240 | 15 | E1 | 1.000000 | False | DEV | 7279 | 4903 | 0.673582 | 1635 | 1 | 3268 | 1641 | 1627 | 5.170149 | 0.388926 | 8484.215112 | 632.781914 | 9116.997026 | 2.789779 | MEASURABLE |  | 1.640558 | -1.572290 | 7.181664 | 1819 | 1605 | 0.117647 | 20000 | 999 | {"7":[-1.2337564857492263,7.147983853349216],"14":[-1.3934974374957783,6.512582743002756],"30":[-1.1942217660254966,6.615562428118182]} | {"20":[-1.1297864264860071,6.8639238605193755],"50":[-1.3280453137884045,6.355260319412783]} | 2.553348 | 2.329305 | 1.753593 | 0.590575 | 0.600000 | 33 | 55 | -55.580400 |
| 4h | 240 | 15 | E1 | 1.000000 | False | HOLD_B | 759 | 506 | 0.666667 | 164 | 1 | 342 | 208 | 134 | -25.417849 | -5.852508 | -5286.912547 | -784.236054 | -6071.148601 | -17.751896 | MEASURABLE |  | 1.366158 | -31.561176 | -2.844936 | 181 | 176 | 0.033149 | 20000 | 999 | {"7":[-31.01760550033668,-2.491684824011065],"14":[-31.437263021386983,-2.0779731703436575],"30":[-30.786451774922888,-1.886628761180214]} | {"20":[-30.694217086676474,-1.9995731287148537],"50":[-32.356640094130874,-1.7071151867501335]} | -19.042554 | -20.338138 | -22.974433 | 0.511696 | 0.142857 | 1 | 7 | 6.838800 |
| 4h | 240 | 15 | E1 | 1.000000 | True | DEV | 1148 | 724 | 0.630662 | 135 | 1 | 589 | 360 | 229 | 4.974181 | -3.930928 | 1790.705172 | -900.182440 | 890.522732 | 1.511923 | MEASURABLE |  | 2.165846 | -11.393619 | 14.732676 | 1819 | 483 | 0.734469 | 20000 | 999 | {"7":[-11.89926308584217,15.592464037831544],"14":[-11.264691251120716,14.773483051833816],"30":[-10.489521645087208,14.398894664406187]} | {"20":[-8.86571628606969,12.446039271756034],"50":[-6.915425022182817,10.690157962796471]} | 0.090628 | -0.590541 | -2.604550 | 0.587436 | 0.555556 | 30 | 54 | 22.244700 |
| 4h | 240 | 15 | E1 | 1.000000 | True | HOLD_B | 125 | 85 | 0.680000 | 10 | 1 | 75 | 49 | 26 | 13.893041 | -0.366951 | 680.759033 | -9.540717 | 671.218317 | 8.949578 | MEASURABLE |  | 1.146194 | -21.709515 | 40.191799 | 181 | 63 | 0.651934 | 20000 | 999 | {"7":[-22.911175901160266,40.738022910815985],"14":[-18.5924812556213,42.739281246720395],"30":[-16.064230936271738,39.38335529978681]} | {"20":[-16.626820722541677,39.07287210604882],"50":[-14.24693889439007,33.24725242635756]} | 2.724689 | -0.798276 | -8.649298 | 0.693333 | 0.500000 | 3 | 6 | -1.435300 |
| 4h | 240 | 15 | E2 | nan | False | DEV | 7279 | 7172 | 0.985300 | 3035 | 1 | 4137 | 2078 | 2059 | -6.070079 | -3.883720 | -12613.623892 | -7996.579688 | -20610.203580 | -4.981920 | MEASURABLE |  | 2.325208 | -8.606744 | -1.354796 | 1819 | 1642 | 0.097306 | 20000 | 999 | {"7":[-8.590366400907923,-1.5322613588732774],"14":[-8.214602148015652,-1.354383905171666],"30":[-8.060026239083793,-1.982481670105368]} | {"20":[-8.467368497870659,-1.2930638813855202],"50":[-8.139337877592624,-1.7708285190340365]} | -5.159169 | -5.326857 | -5.788546 | 0.512207 | 0.363636 | 20 | 55 | -35.204900 |
| 4h | 240 | 15 | E2 | nan | False | HOLD_B | 759 | 744 | 0.980237 | 305 | 1 | 439 | 261 | 178 | -12.704894 | -15.376029 | -3315.977368 | -2736.933185 | -6052.910553 | -13.787951 | MEASURABLE |  | 2.504203 | -22.038076 | -5.352971 | 181 | 181 | 0.005525 | 20000 | 999 | {"7":[-21.386944953780098,-5.248662597397349],"14":[-21.382892939873543,-5.300024237477832],"30":[-21.26408078645724,-5.575101338814548]} | {"20":[-21.94968030898568,-5.194693370556221],"50":[-21.45843237823852,-5.083444565032856]} | -14.547022 | -15.308033 | -17.150249 | 0.455581 | 0.000000 | 0 | 7 | -4.379000 |

## k45_mtf_persistence_r2_13_20261002

- 테스트 재실행 `tests/test_k45_mtf_persistence_r2_13.py`: `5 passed in 1.87s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-02T15:27:32.881287+00:00 |
| run_finished_utc | 2026-10-02T17:06:48.550623+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 1h/4h에서 예측 포착 수익이 큰 쪽만 거래하면 방향만으로 고른 R_DIR보다 SINGLE net이 높고, 같은 진입·청산의 항상 롱을 DEV와 HOLD_B 모두에서 이긴다. |
| local_data_only | True |
| downloads | 0 |
| patchtst_refits | 0 |
| live_orders | 0 |
| cost_bps | 4.0 |
| funding_included | True |
| hold_b_exploratory | True |
| seed | 20261001 |
| model_params | {"iterations": 500, "depth": 4, "learning_rate": 0.05, "l2_leaf_reg": 3, "random_seed": 20261001, "thread_count": 6, "verbose": false, "allow_writing_files": false} |
| single_position_first | True |
| ci_reps | 999 |
| random_baseline_reps | 1000 |

### out_of_sample_result (원문)

```text
{
 "matched_parameter_cells": 60,
 "dev_and_hold_b_supporting_cells": 9,
 "hypothesis_supported_by_any_cell": true
}
```

- 출력 해시 확인: 33/34 일치
  - CHANGED: out\k45_mtf_persistence_r2_13_20261002\queue.log

### REPORT.md 앞 150줄 (전체 1774줄, 원문)

## 0

| cost_bps | seed | live | hold_b_exploratory | ci_reps | random_reps |
|---|---|---|---|---|---|
| 4.000000 | 20261001 | 0 | 1 | 999 | 1000 |

## 1

| tf | k | segment | arm | model | decile | n | predicted_c_mean_bps | realized_c_mean_bps | realized_net_mean_bps |
|---|---|---|---|---|---|---|---|---|---|
| 1h | 1.000000 | DEV | LONG | M_C | 1 | 3776 | -54.882356 | -4.958749 | -8.958749 |
| 1h | 1.000000 | DEV | LONG | M_C | 2 | 3776 | -13.134432 | -4.349653 | -8.349653 |
| 1h | 1.000000 | DEV | LONG | M_C | 3 | 3776 | -5.631887 | 1.542770 | -2.457230 |
| 1h | 1.000000 | DEV | LONG | M_C | 4 | 3776 | -2.048072 | 1.372417 | -2.627583 |
| 1h | 1.000000 | DEV | LONG | M_C | 5 | 3776 | 0.675920 | 1.601949 | -2.398051 |
| 1h | 1.000000 | DEV | LONG | M_C | 6 | 3776 | 3.534899 | 3.893119 | -0.106881 |
| 1h | 1.000000 | DEV | LONG | M_C | 7 | 3776 | 7.027922 | 1.356143 | -2.643857 |
| 1h | 1.000000 | DEV | LONG | M_C | 8 | 3776 | 12.284047 | -0.329468 | -4.329468 |
| 1h | 1.000000 | DEV | LONG | M_C | 9 | 3776 | 24.420552 | 0.688635 | -3.311365 |
| 1h | 1.000000 | DEV | LONG | M_C | 10 | 3776 | 135.014539 | 7.528703 | 3.528703 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 1 | 3776 | -172.050086 | -5.188979 | -9.188979 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 2 | 3776 | -115.451259 | 7.321101 | 3.321101 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 3 | 3776 | -99.615630 | -0.449213 | -4.449213 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 4 | 3776 | -89.249961 | -2.276056 | -6.276056 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 5 | 3776 | -79.908691 | -4.468379 | -8.468379 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 6 | 3776 | -71.293802 | 0.429988 | -3.570012 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 7 | 3776 | -62.814345 | 0.136299 | -3.863701 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 8 | 3776 | -53.751708 | 0.743194 | -3.256806 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 9 | 3776 | -43.054554 | 6.293985 | 2.293985 |
| 1h | 1.000000 | DEV | LONG | M_Cq | 10 | 3776 | -1.620038 | 5.803926 | 1.803926 |
| 1h | 1.000000 | DEV | SHORT | M_C | 1 | 3776 | -74.803530 | -12.434824 | -16.434824 |
| 1h | 1.000000 | DEV | SHORT | M_C | 2 | 3776 | -14.050886 | 1.499412 | -2.500588 |
| 1h | 1.000000 | DEV | SHORT | M_C | 3 | 3776 | -5.949554 | -1.644648 | -5.644648 |
| 1h | 1.000000 | DEV | SHORT | M_C | 4 | 3776 | -2.845089 | -4.854816 | -8.854816 |
| 1h | 1.000000 | DEV | SHORT | M_C | 5 | 3776 | -0.812099 | -5.235938 | -9.235938 |
| 1h | 1.000000 | DEV | SHORT | M_C | 6 | 3776 | 0.895844 | 3.400165 | -0.599835 |
| 1h | 1.000000 | DEV | SHORT | M_C | 7 | 3776 | 2.759388 | 0.366681 | -3.633319 |
| 1h | 1.000000 | DEV | SHORT | M_C | 8 | 3776 | 5.720207 | -0.300446 | -4.300446 |
| 1h | 1.000000 | DEV | SHORT | M_C | 9 | 3776 | 12.859551 | -2.651072 | -6.651072 |
| 1h | 1.000000 | DEV | SHORT | M_C | 10 | 3776 | 67.937493 | 5.657932 | 1.657932 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 1 | 3776 | -195.591768 | -23.327827 | -27.327827 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 2 | 3776 | -125.511585 | -0.503947 | -4.503947 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 3 | 3776 | -106.278285 | 1.336726 | -2.663274 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 4 | 3776 | -92.384030 | 2.248896 | -1.751104 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 5 | 3776 | -81.081343 | 2.993462 | -1.006538 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 6 | 3776 | -71.384681 | 1.076626 | -2.923374 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 7 | 3776 | -62.971310 | 0.678873 | -3.321127 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 8 | 3776 | -54.507047 | 0.673334 | -3.326666 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 9 | 3776 | -44.223055 | -0.872155 | -4.872155 |
| 1h | 1.000000 | DEV | SHORT | M_Cq | 10 | 3776 | -26.391034 | -0.501540 | -4.501540 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 1 | 388 | -18.915194 | 7.330716 | 3.330716 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 2 | 388 | -9.281924 | -0.752128 | -4.752128 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 3 | 388 | -5.680122 | -13.018859 | -17.018859 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 4 | 388 | -3.180270 | -6.632046 | -10.632046 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 5 | 388 | -1.163342 | -7.817844 | -11.817844 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 6 | 388 | 0.803581 | -11.284509 | -15.284509 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 7 | 388 | 2.971622 | -5.644064 | -9.644064 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 8 | 388 | 5.695120 | -16.168525 | -20.168525 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 9 | 388 | 9.990933 | -3.960104 | -7.960104 |
| 1h | 1.000000 | HOLD_B | LONG | M_C | 10 | 388 | 21.477198 | -8.327070 | -12.327070 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 1 | 388 | -131.887383 | 10.905570 | 6.905570 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 2 | 388 | -103.388127 | -15.096443 | -19.096443 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 3 | 388 | -93.466956 | -5.635360 | -9.635360 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 4 | 388 | -85.535739 | -4.959211 | -8.959211 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 5 | 388 | -78.959319 | -7.090067 | -11.090067 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 6 | 388 | -72.802896 | -5.142312 | -9.142312 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 7 | 388 | -66.182536 | -14.497144 | -18.497144 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 8 | 388 | -59.088963 | -10.614388 | -14.614388 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 9 | 388 | -49.531981 | -12.973257 | -16.973257 |
| 1h | 1.000000 | HOLD_B | LONG | M_Cq | 10 | 388 | -33.645646 | -1.171820 | -5.171820 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 1 | 388 | -19.747677 | 18.502224 | 14.502224 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 2 | 388 | -3.774898 | 7.493977 | 3.493977 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 3 | 388 | -1.958767 | 4.528381 | 0.528381 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 4 | 388 | -0.967370 | -1.882987 | -5.882987 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 5 | 388 | -0.117984 | 3.413935 | -0.586065 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 6 | 388 | 0.779021 | 10.673482 | 6.673482 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 7 | 388 | 1.773092 | 6.890240 | 2.890240 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 8 | 388 | 2.843300 | 5.969145 | 1.969145 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 9 | 388 | 4.341587 | 14.664415 | 10.664415 |
| 1h | 1.000000 | HOLD_B | SHORT | M_C | 10 | 388 | 11.890703 | -13.462669 | -17.462669 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 1 | 388 | -143.555360 | -2.766660 | -6.766660 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 2 | 388 | -101.847799 | -11.016738 | -15.016738 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 3 | 388 | -86.283615 | 7.833188 | 3.833188 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 4 | 388 | -76.874279 | 11.080032 | 7.080032 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 5 | 388 | -70.245137 | 12.878124 | 8.878124 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 6 | 388 | -64.503006 | 10.418521 | 6.418521 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 7 | 388 | -58.553220 | 16.946102 | 12.946102 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 8 | 388 | -52.227862 | 9.562752 | 5.562752 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 9 | 388 | -43.373947 | -0.002544 | -4.002544 |
| 1h | 1.000000 | HOLD_B | SHORT | M_Cq | 10 | 388 | -29.534767 | 1.857366 | -2.142634 |
| 1h | 2.000000 | DEV | LONG | M_C | 1 | 3776 | -85.044545 | -6.371422 | -10.371422 |
| 1h | 2.000000 | DEV | LONG | M_C | 2 | 3776 | -27.127093 | 0.684382 | -3.315618 |
| 1h | 2.000000 | DEV | LONG | M_C | 3 | 3776 | -14.391188 | 1.094332 | -2.905668 |
| 1h | 2.000000 | DEV | LONG | M_C | 4 | 3776 | -7.695903 | 1.253422 | -2.746578 |
| 1h | 2.000000 | DEV | LONG | M_C | 5 | 3776 | -3.048180 | 3.324925 | -0.675075 |
| 1h | 2.000000 | DEV | LONG | M_C | 6 | 3776 | 1.364305 | 3.218946 | -0.781054 |
| 1h | 2.000000 | DEV | LONG | M_C | 7 | 3776 | 6.254757 | 1.161204 | -2.838796 |
| 1h | 2.000000 | DEV | LONG | M_C | 8 | 3776 | 13.571629 | 5.621588 | 1.621588 |
| 1h | 2.000000 | DEV | LONG | M_C | 9 | 3776 | 28.638283 | 3.782357 | -0.217643 |
| 1h | 2.000000 | DEV | LONG | M_C | 10 | 3776 | 149.542692 | 15.381109 | 11.381109 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 1 | 3776 | -212.194441 | -0.688509 | -4.688509 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 2 | 3776 | -139.023145 | 3.540852 | -0.459148 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 3 | 3776 | -116.136067 | 3.640113 | -0.359887 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 4 | 3776 | -101.418027 | -3.177771 | -7.177771 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 5 | 3776 | -89.666012 | 3.647543 | -0.352457 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 6 | 3776 | -78.703341 | 0.821746 | -3.178254 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 7 | 3776 | -68.332337 | 4.338071 | 0.338071 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 8 | 3776 | -57.707855 | 6.691979 | 2.691979 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 9 | 3776 | -44.814500 | 3.081702 | -0.918298 |
| 1h | 2.000000 | DEV | LONG | M_Cq | 10 | 3776 | 6.788462 | 7.255118 | 3.255118 |
| 1h | 2.000000 | DEV | SHORT | M_C | 1 | 3776 | -133.989028 | -4.530508 | -8.530508 |
| 1h | 2.000000 | DEV | SHORT | M_C | 2 | 3776 | -18.665047 | -10.589551 | -14.589551 |
| 1h | 2.000000 | DEV | SHORT | M_C | 3 | 3776 | -8.273116 | -7.072852 | -11.072852 |
| 1h | 2.000000 | DEV | SHORT | M_C | 4 | 3776 | -3.757672 | 0.861223 | -3.138777 |
| 1h | 2.000000 | DEV | SHORT | M_C | 5 | 3776 | -0.430637 | -5.750287 | -9.750287 |
| 1h | 2.000000 | DEV | SHORT | M_C | 6 | 3776 | 2.524282 | -3.892194 | -7.892194 |
| 1h | 2.000000 | DEV | SHORT | M_C | 7 | 3776 | 5.630454 | -2.007415 | -6.007415 |
| 1h | 2.000000 | DEV | SHORT | M_C | 8 | 3776 | 9.660205 | 4.741815 | 0.741815 |
| 1h | 2.000000 | DEV | SHORT | M_C | 9 | 3776 | 17.561296 | 7.029122 | 3.029122 |
| 1h | 2.000000 | DEV | SHORT | M_C | 10 | 3776 | 94.799402 | 0.980447 | -3.019553 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 1 | 3776 | -249.205654 | -17.543779 | -21.543779 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 2 | 3776 | -140.426985 | -5.927743 | -9.927743 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 3 | 3776 | -114.774207 | -6.944038 | -10.944038 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 4 | 3776 | -98.356710 | -1.008728 | -5.008728 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 5 | 3776 | -85.577389 | 2.498019 | -1.501981 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 6 | 3776 | -74.455818 | 3.533999 | -0.466001 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 7 | 3776 | -64.024885 | 1.338938 | -2.661062 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 8 | 3776 | -53.901052 | 1.860951 | -2.139049 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 9 | 3776 | -43.153001 | 0.086965 | -3.913035 |
| 1h | 2.000000 | DEV | SHORT | M_Cq | 10 | 3776 | -19.717848 | 1.875214 | -2.124786 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 1 | 388 | -13.731920 | -20.123427 | -24.123427 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 2 | 388 | -3.595737 | -3.395427 | -7.395427 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 3 | 388 | -1.190054 | -10.382204 | -14.382204 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 4 | 388 | 0.585677 | -10.002646 | -14.002646 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 5 | 388 | 2.369982 | -9.670578 | -13.670578 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 6 | 388 | 4.224017 | -9.108118 | -13.108118 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 7 | 388 | 6.552829 | -0.989879 | -4.989879 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 8 | 388 | 9.776694 | -1.763383 | -5.763383 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 9 | 388 | 15.245781 | -3.209701 | -7.209701 |
| 1h | 2.000000 | HOLD_B | LONG | M_C | 10 | 388 | 34.387058 | 3.551200 | -0.448800 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 1 | 388 | -120.769324 | -7.611859 | -11.611859 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 2 | 388 | -94.696989 | 4.615394 | 0.615394 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 3 | 388 | -84.417089 | -17.461840 | -21.461840 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 4 | 388 | -76.938076 | -3.408330 | -7.408330 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 5 | 388 | -70.931808 | -14.449088 | -18.449088 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 6 | 388 | -65.564961 | 4.246004 | 0.246004 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 7 | 388 | -60.441214 | -5.695559 | -9.695559 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 8 | 388 | -55.245970 | -6.299482 | -10.299482 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 9 | 388 | -49.634863 | -12.558518 | -16.558518 |
| 1h | 2.000000 | HOLD_B | LONG | M_Cq | 10 | 388 | -40.337648 | -6.470885 | -10.470885 |

## k45_mtf_tail_r2_20_20261003

- 테스트 재실행 `tests/test_k45_mtf_tail_r2_20.py`: `5 passed in 5.44s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-03T00:31:42.824232+00:00 |
| run_finished_utc | 2026-10-03T00:43:41.707564+00:00 |
| elapsed_seconds | 444.8088370002806 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 1h 모델 점수 상위 꼬리(q <= 2%, 인과 기준)만 거래하면 같은 tf·h·게이트의 R2-12 E0 전체 거래보다 DEV 거래당 net이 높고, DEV net > 0 이다. |
| hold_b_seen_excluded_from_verdict | True |
| local_data_only | True |
| downloads | 0 |
| model_training | 0 |
| live_orders | 0 |
| cpu_worker_limit | 4 |
| cpu_workers_used | 1 |
| cost_bps_primary | 4.0 |
| funding_included | True |
| single_position | True |
| tail_cell_count | 120 |
| tail_metric_row_count | 240 |
| threshold_methods | ["EXPANDING_OOS", "ROLLING_180D"] |
| tail_modes | ["MAX", "SIDE"] |
| quantiles | [0.01, 0.02, 0.05] |
| seed | 20261003 |

### out_of_sample_result (원문)

```text
{
 "eligible_cell_count": 48,
 "pass_cell_count": 45,
 "all_cells_pass": false
}
```

- 출력 해시 확인: 15/15 일치

### REPORT.md 앞 150줄 (전체 2438줄, 원문)

# R2-20

## 0

| cell_count | metric_rows | cost_bps | hold_b_seen | live |
|---|---|---|---|---|
| 120 | 240 | 4.000000 | 1 | 0 |

## 1

| tf | horizon | gate_used | segment | source_n | actual_n | n_diff | source_net_sum_bps | actual_net_sum_bps | net_sum_bps_diff | source_net_mean_bps | actual_net_mean_bps | net_mean_bps_diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1h | 60 | False | DEV | 22763 | 22763 | 0 | -67089.601109 | -67089.601109 | 0.000000 | -2.947309 | -2.947309 | 0.000000 |
| 1h | 60 | False | HOLD_B | 1835 | 1835 | 0 | -3797.713188 | -3797.713188 | 0.000000 | -2.069598 | -2.069598 | 0.000000 |
| 1h | 60 | True | DEV | 4383 | 4383 | 0 | -11772.747987 | -11772.747987 | 0.000000 | -2.686002 | -2.686002 | 0.000000 |
| 1h | 60 | True | HOLD_B | 418 | 418 | 0 | -471.556441 | -471.556441 | 0.000000 | -1.128125 | -1.128125 | 0.000000 |
| 4h | 240 | False | DEV | 7279 | 7279 | 0 | -12102.665066 | -12102.665066 | 0.000000 | -1.662682 | -1.662682 | 0.000000 |
| 4h | 240 | False | HOLD_B | 759 | 759 | 0 | -4634.440317 | -4634.440317 | 0.000000 | -6.105982 | -6.105982 | 0.000000 |
| 4h | 240 | True | DEV | 1148 | 1148 | 0 | -8557.939398 | -8557.939398 | 0.000000 | -7.454651 | -7.454651 | 0.000000 |
| 4h | 240 | True | HOLD_B | 125 | 125 | 0 | -776.254209 | -776.254209 | 0.000000 | -6.210034 | -6.210034 | 0.000000 |

## 2

| cell_id | tf | horizon | tail_mode | threshold_method | q | gate_used | segment | signal_n | dropped_overlap_n | n | long_n | short_n | long_net_mean_bps | short_net_mean_bps | long_net_sum_bps | short_net_sum_bps | net_mean_bps | net_sum_bps | top1_removed_net_sum_bps | top2_removed_net_sum_bps | top5_removed_net_sum_bps | top5_days_removed_net_sum_bps | top5_signal_events_removed_net_sum_bps | signal_event_n | direction_hit_rate | monthly_positive_share | positive_months | months | funding_total_bps | max_concurrent | pw_status | pw_error | pw_block_raw | pw_block | pw_ci95_lower | pw_ci95_upper | pw_p_one_sided | pw_reps | bonferroni_cells | bonferroni_p_zero |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1h_h60\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.010000 | False | DEV | 48 | 0 | 48 | 41 | 7 | 22.054371 | 47.087155 | 904.229200 | 329.610083 | 25.704985 | 1233.839283 | 581.052463 | 232.018621 | -549.109745 | -665.000215 | -399.421287 | 47 | 0.666667 | 0.607143 | 17 | 28 | 0.918000 | 1 | MEASURABLE |  | 1.293008 | 1.293008 | -30.197157 | 77.075583 | 0.175824 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.010000 | False | HOLD_B | 3 | 0 | 3 | 3 | 0 | 139.545841 | nan | 418.637524 | 0.000000 | 139.545841 | 418.637524 | 178.887207 | -23.178539 | 0.000000 | 0.000000 | 0.000000 | 3 | 0.666667 | 1.000000 | 2 | 2 | 0.000000 | 1 | MEASURABLE |  | 1.456862 | 1.456862 | -87.642952 | 286.817862 | 0.096903 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.010000 | True | DEV | 30 | 0 | 30 | 27 | 3 | 38.891685 | 84.602836 | 1050.075508 | 253.808507 | 43.462800 | 1303.884015 | 651.097195 | 302.063353 | -479.065013 | -958.993388 | -479.065013 | 30 | 0.700000 | 0.666667 | 12 | 18 | 0.995200 | 1 | MEASURABLE |  | 2.115700 | 2.115700 | -62.489579 | 122.770841 | 0.188811 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.010000 | True | HOLD_B | 3 | 0 | 3 | 3 | 0 | 139.545841 | nan | 418.637524 | 0.000000 | 139.545841 | 418.637524 | 178.887207 | -23.178539 | 0.000000 | 0.000000 | 0.000000 | 3 | 0.666667 | 1.000000 | 2 | 2 | 0.000000 | 1 | MEASURABLE |  | 1.456862 | 1.456862 | -87.642952 | 286.817862 | 0.096903 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.020000 | False | DEV | 132 | 0 | 132 | 113 | 19 | 18.188999 | -29.504854 | 2055.356919 | -560.592217 | 11.323975 | 1494.764702 | 841.977882 | 492.944041 | -288.184326 | -714.444549 | -215.249043 | 124 | 0.621212 | 0.622222 | 28 | 45 | 7.214400 | 1 | MEASURABLE |  | 3.937159 | 3.937159 | -18.936774 | 35.014191 | 0.205794 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.020000 | False | HOLD_B | 13 | 0 | 13 | 13 | 0 | 15.680941 | nan | 203.852238 | 0.000000 | 15.680941 | 203.852238 | -35.898079 | -237.963825 | -442.314646 | -442.314646 | -442.314646 | 13 | 0.615385 | 0.666667 | 2 | 3 | 0.461800 | 1 | MEASURABLE |  | 1.388292 | 1.388292 | -50.905868 | 96.477064 | 0.334665 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.020000 | True | DEV | 74 | 0 | 74 | 67 | 7 | 25.296451 | 20.544942 | 1694.862187 | 143.814591 | 24.846983 | 1838.676779 | 1185.889959 | 836.856117 | 55.727750 | -774.283459 | 14.799131 | 68 | 0.648649 | 0.620690 | 18 | 29 | 6.006400 | 1 | MEASURABLE |  | 1.337639 | 1.337639 | -22.759131 | 68.877413 | 0.136863 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.020000 | True | HOLD_B | 7 | 0 | 7 | 7 | 0 | 78.960114 | nan | 552.720798 | 0.000000 | 78.960114 | 552.720798 | 312.970482 | 110.904736 | -57.494137 | -57.494137 | -57.494137 | 7 | 0.714286 | 1.000000 | 3 | 3 | 0.105100 | 1 | MEASURABLE |  | 2.855616 | 2.855616 | -20.096344 | 144.362582 | 0.050949 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.050000 | False | DEV | 627 | 0 | 627 | 493 | 134 | 1.982207 | -12.325826 | 977.227983 | -1651.660714 | -1.075650 | -674.432732 | -1327.219551 | -1733.993824 | -2775.421773 | -3123.863398 | -2658.773823 | 578 | 0.617225 | 0.553571 | 31 | 56 | 35.666000 | 1 | MEASURABLE |  | 4.504493 | 4.504493 | -9.377656 | 7.517683 | 0.629371 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 60 | MAX | EXPANDING_OOS | 0.050000 | False | HOLD_B | 39 | 0 | 39 | 37 | 2 | -7.610315 | 62.907354 | -281.581657 | 125.814707 | -3.994024 | -155.766949 | -395.517266 | -597.583012 | -986.644161 | -802.558374 | -851.985710 | 36 | 0.615385 | 0.200000 | 1 | 5 | 0.117800 | 1 | MEASURABLE |  | 2.273006 | 2.273006 | -29.750402 | 26.282649 | 0.618382 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.050000 | True | DEV | 225 | 0 | 225 | 187 | 38 | 10.350073 | 0.095345 | 1935.463582 | 3.623112 | 8.618163 | 1939.086694 | 1286.299874 | 923.627875 | 7.432795 | -785.883985 | 31.797767 | 200 | 0.617778 | 0.632653 | 31 | 49 | 18.157300 | 1 | MEASURABLE |  | 1.366594 | 1.366594 | -9.101591 | 27.325785 | 0.153846 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 60 | MAX | EXPANDING_OOS | 0.050000 | True | HOLD_B | 16 | 0 | 16 | 15 | 1 | 35.517557 | 1.626312 | 532.763359 | 1.626312 | 33.399354 | 534.389672 | 294.639355 | 92.573609 | -206.567838 | -236.550296 | -217.128410 | 15 | 0.750000 | 0.750000 | 3 | 4 | 0.665400 | 1 | MEASURABLE |  | 41.000000 | 41.000000 | 7.412200 | 58.464163 | 0.006993 | 1000 | 120 | 0.839161 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.010000 | False | DEV | 116 | 0 | 116 | 65 | 51 | 30.140759 | -2.615807 | 1959.149327 | -133.406132 | 15.739165 | 1825.743196 | 1172.956376 | 823.922534 | 40.973262 | -452.129139 | 154.837164 | 113 | 0.672414 | 0.630435 | 29 | 46 | 4.235200 | 1 | MEASURABLE |  | 3.315195 | 3.315195 | -14.141658 | 44.729821 | 0.131868 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.010000 | False | HOLD_B | 5 | 0 | 5 | 5 | 0 | 100.556202 | nan | 502.781008 | 0.000000 | 100.556202 | 502.781008 | 263.030692 | 60.964946 | 0.000000 | 0.000000 | 0.000000 | 5 | 0.600000 | 0.666667 | 2 | 3 | -0.016000 | 1 | MEASURABLE |  | 1.446711 | 1.446711 | -32.132605 | 205.748111 | 0.064935 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.010000 | True | DEV | 51 | 0 | 51 | 37 | 14 | 38.414179 | 24.828339 | 1421.324637 | 347.596740 | 34.684733 | 1768.921377 | 1116.134557 | 767.100715 | -14.027651 | -861.117659 | -14.027651 | 50 | 0.705882 | 0.678571 | 19 | 28 | 6.372100 | 1 | MEASURABLE |  | 2.674879 | 2.674879 | -37.499023 | 89.105152 | 0.152847 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.010000 | True | HOLD_B | 4 | 0 | 4 | 4 | 0 | 128.074348 | nan | 512.297390 | 0.000000 | 128.074348 | 512.297390 | 272.547074 | 70.481328 | 0.000000 | 0.000000 | 0.000000 | 4 | 0.750000 | 1.000000 | 2 | 2 | -0.372700 | 1 | MEASURABLE |  | 1.457795 | 1.457795 | -38.690739 | 256.148695 | 0.058941 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.020000 | False | DEV | 378 | 0 | 378 | 201 | 177 | 11.389864 | -11.408135 | 2289.362674 | -2019.239894 | 0.714611 | 270.122780 | -382.664039 | -731.697881 | -1514.647153 | -2023.613628 | -1373.205955 | 354 | 0.608466 | 0.517857 | 29 | 56 | 0.221500 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -11.641868 | 12.573144 | 0.453546 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.020000 | False | HOLD_B | 23 | 0 | 23 | 19 | 4 | -17.221511 | 18.889133 | -327.208714 | 75.556531 | -10.941399 | -251.652183 | -491.402499 | -693.468245 | -968.259940 | -783.883457 | -782.257145 | 21 | 0.565217 | 0.500000 | 3 | 6 | 0.905200 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -51.943766 | 42.166675 | 0.715285 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.020000 | True | DEV | 145 | 0 | 145 | 100 | 45 | 18.049959 | -0.541237 | 1804.995898 | -24.355662 | 12.280277 | 1780.640236 | 1127.853416 | 778.819574 | -2.308792 | -933.605680 | 25.268504 | 134 | 0.634483 | 0.630435 | 29 | 46 | 11.064600 | 1 | MEASURABLE |  | 2.008437 | 2.008437 | -14.354263 | 38.925816 | 0.169830 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.020000 | True | HOLD_B | 10 | 0 | 10 | 9 | 1 | 39.773262 | 1.626312 | 357.959361 | 1.626312 | 35.958567 | 359.585673 | 119.835357 | -82.230389 | -281.694039 | -283.320351 | -281.694039 | 10 | 0.700000 | 0.750000 | 3 | 4 | 0.507400 | 1 | MEASURABLE |  | 34.023601 | 34.023601 | -6.319015 | 75.757721 | 0.046953 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.050000 | False | DEV | 1904 | 0 | 1904 | 1024 | 880 | -0.103875 | -7.342286 | -106.367721 | -6461.211321 | -3.449359 | -6567.579042 | -7220.365862 | -7627.140134 | -8668.568083 | -8979.447573 | -8675.682877 | 1701 | 0.595588 | 0.446429 | 25 | 56 | 15.402400 | 1 | MEASURABLE |  | 2.268855 | 2.268855 | -7.129144 | 0.174980 | 0.968032 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 60 | SIDE | EXPANDING_OOS | 0.050000 | False | HOLD_B | 101 | 0 | 101 | 65 | 36 | 1.509439 | -14.863169 | 98.113526 | -535.074092 | -4.326342 | -436.960566 | -780.515892 | -1020.266209 | -1519.465696 | -1492.930906 | -1416.930156 | 96 | 0.603960 | 0.428571 | 3 | 7 | 0.367200 | 1 | MEASURABLE |  | 2.825938 | 2.825938 | -18.324644 | 11.546490 | 0.737263 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.050000 | True | DEV | 517 | 0 | 517 | 331 | 186 | 2.896422 | -8.745038 | 958.715789 | -1626.577159 | -1.291801 | -667.861370 | -1320.648190 | -1683.320189 | -2650.556837 | -2980.352507 | -2698.913040 | 448 | 0.580271 | 0.535714 | 30 | 56 | 9.617500 | 1 | MEASURABLE |  | 2.410546 | 2.410546 | -10.989201 | 8.358105 | 0.592408 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 60 | SIDE | EXPANDING_OOS | 0.050000 | True | HOLD_B | 36 | 0 | 36 | 25 | 11 | 31.725649 | -26.781423 | 793.141237 | -294.595653 | 13.848488 | 498.545584 | 154.990259 | -84.760058 | -529.023817 | -509.876587 | -539.584390 | 34 | 0.638889 | 0.500000 | 2 | 4 | 0.001300 | 1 | MEASURABLE |  | 1.801159 | 1.801159 | -17.633091 | 40.359626 | 0.168831 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.010000 | False | DEV | 340 | 0 | 340 | 270 | 70 | 4.759308 | -17.717226 | 1285.013205 | -1240.205853 | 0.131786 | 44.807353 | -607.979467 | -957.013309 | -1738.141675 | -2289.633670 | -1665.206392 | 316 | 0.632353 | 0.543860 | 31 | 57 | 23.077100 | 1 | MEASURABLE |  | 1.019106 | 1.019106 | -13.328017 | 13.254495 | 0.479520 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.010000 | False | HOLD_B | 35 | 0 | 35 | 34 | 1 | -5.223603 | 1.626312 | -177.602512 | 1.626312 | -5.027891 | -175.976199 | -415.726516 | -617.792262 | -977.196309 | -792.239096 | -841.666432 | 32 | 0.628571 | 0.200000 | 1 | 5 | 0.950400 | 1 | MEASURABLE |  | 2.273571 | 2.273571 | -30.461749 | 27.427564 | 0.660340 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.010000 | True | DEV | 142 | 0 | 142 | 122 | 20 | 8.867872 | 7.604937 | 1081.880355 | 152.098744 | 8.689994 | 1233.979099 | 581.192280 | 232.158438 | -548.969929 | -1520.971431 | -589.898548 | 128 | 0.633803 | 0.658537 | 27 | 41 | 11.801500 | 1 | MEASURABLE |  | 2.942110 | 2.942110 | -19.060352 | 36.647457 | 0.276723 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.010000 | True | HOLD_B | 15 | 0 | 15 | 14 | 1 | 35.568831 | 1.626312 | 497.963635 | 1.626312 | 33.305997 | 499.589948 | 259.839631 | 57.773885 | -241.367562 | -271.350020 | -251.928134 | 14 | 0.733333 | 0.750000 | 3 | 4 | 0.665400 | 1 | MEASURABLE |  | 41.000000 | 41.000000 | 6.456267 | 60.037823 | 0.011988 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q02\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.020000 | False | DEV | 698 | 0 | 698 | 542 | 156 | 3.948804 | -11.210844 | 2140.251891 | -1748.891638 | 0.560688 | 391.360253 | -261.426566 | -668.200839 | -1709.628788 | -2025.752857 | -1592.980838 | 637 | 0.621777 | 0.465517 | 27 | 58 | 49.843000 | 1 | MEASURABLE |  | 3.575274 | 3.575274 | -7.361585 | 8.512523 | 0.451548 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q02\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.020000 | False | HOLD_B | 64 | 0 | 64 | 57 | 7 | 0.084608 | 18.122012 | 4.822684 | 126.854081 | 2.057449 | 131.676765 | -211.878561 | -451.628877 | -926.421166 | -812.999043 | -813.566029 | 61 | 0.640625 | 0.571429 | 4 | 7 | 1.644100 | 1 | MEASURABLE |  | 3.119575 | 3.119575 | -16.332992 | 21.730066 | 0.429570 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q02\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.020000 | True | DEV | 248 | 0 | 248 | 203 | 45 | 10.847312 | 1.371463 | 2202.004295 | 61.715821 | 9.127904 | 2263.720116 | 1610.933296 | 1248.261297 | 332.066217 | -498.363398 | 356.431189 | 220 | 0.625000 | 0.615385 | 32 | 52 | 30.939300 | 1 | MEASURABLE |  | 1.866413 | 1.866413 | -9.324442 | 24.304966 | 0.147852 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q02\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.020000 | True | HOLD_B | 26 | 0 | 26 | 23 | 3 | 36.695479 | 15.942530 | 843.996028 | 47.827591 | 34.300908 | 891.823620 | 548.268294 | 308.517978 | -135.745782 | -212.962277 | -146.306355 | 25 | 0.730769 | 0.500000 | 2 | 4 | 0.752600 | 1 | MEASURABLE |  | 18.588006 | 18.588006 | -1.970385 | 68.674975 | 0.035964 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q05\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.050000 | False | DEV | 1782 | 0 | 1782 | 1237 | 545 | 0.458760 | -7.528874 | 567.486271 | -4103.236122 | -1.984147 | -3535.749851 | -4188.536671 | -4595.310943 | -5636.738892 | -5758.270367 | -5666.679014 | 1585 | 0.602132 | 0.491525 | 29 | 59 | 76.580300 | 1 | MEASURABLE |  | 1.769397 | 1.769397 | -5.737308 | 2.153240 | 0.841159 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q05\|g0 | 1h | 60 | MAX | ROLLING_180D | 0.050000 | False | HOLD_B | 168 | 0 | 168 | 133 | 35 | 5.450671 | -10.992804 | 724.939273 | -384.748131 | 2.024947 | 340.191142 | -3.364183 | -252.029210 | -884.564781 | -1238.278447 | -876.987199 | 155 | 0.619048 | 0.571429 | 4 | 7 | -0.227800 | 1 | MEASURABLE |  | 1.377167 | 1.377167 | -11.633389 | 14.850124 | 0.415584 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q05\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.050000 | True | DEV | 532 | 0 | 532 | 404 | 128 | 3.738701 | -10.268751 | 1510.435142 | -1314.400171 | 0.368487 | 196.034971 | -456.751849 | -819.423848 | -1800.700602 | -1907.728836 | -1828.116074 | 454 | 0.578947 | 0.586207 | 34 | 58 | 41.016800 | 1 | MEASURABLE |  | 4.624541 | 4.624541 | -7.452301 | 8.503934 | 0.455544 | 1000 | 120 | 1.000000 |
| 1h_h60\|MAX\|ROLLING_180D\|q05\|g1 | 1h | 60 | MAX | ROLLING_180D | 0.050000 | True | HOLD_B | 57 | 0 | 57 | 46 | 11 | 27.513714 | -26.781423 | 1265.630825 | -294.595653 | 17.035705 | 971.035172 | 627.479847 | 387.729530 | -159.633303 | -631.738111 | -260.406998 | 52 | 0.631579 | 0.500000 | 3 | 6 | -0.128800 | 1 | MEASURABLE |  | 2.207557 | 2.207557 | -13.623294 | 44.359399 | 0.124875 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q01\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.010000 | False | DEV | 681 | 0 | 681 | 363 | 318 | 2.730146 | -5.345318 | 991.042916 | -1699.810990 | -1.040775 | -708.768074 | -1361.554894 | -1724.226893 | -2672.071890 | -3115.844911 | -2627.745781 | 629 | 0.604993 | 0.500000 | 29 | 58 | 13.448800 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -9.076313 | 7.942301 | 0.585415 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q01\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.010000 | False | HOLD_B | 69 | 0 | 69 | 36 | 33 | -8.788372 | -8.576396 | -316.381381 | -283.021072 | -8.686992 | -599.402452 | -839.152769 | -1041.218515 | -1462.540651 | -1420.964005 | -1352.151323 | 64 | 0.594203 | 0.166667 | 1 | 6 | -0.885500 | 1 | MEASURABLE |  | 2.625511 | 2.625511 | -26.715383 | 10.822127 | 0.822178 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q01\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.010000 | True | DEV | 232 | 0 | 232 | 150 | 82 | 9.393513 | 6.715738 | 1409.027022 | 550.690533 | 8.447058 | 1959.717555 | 1306.930736 | 944.258736 | -3.586261 | -885.059220 | -16.077286 | 206 | 0.629310 | 0.634615 | 33 | 52 | 13.553800 | 1 | MEASURABLE |  | 1.782870 | 1.782870 | -11.327707 | 27.735105 | 0.188811 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q01\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.010000 | True | HOLD_B | 24 | 0 | 24 | 14 | 10 | 35.568831 | -17.452320 | 497.963635 | -174.523203 | 13.476685 | 323.440433 | 83.690117 | -118.375629 | -417.517077 | -461.498863 | -428.077649 | 22 | 0.666667 | 0.500000 | 2 | 4 | -0.085900 | 1 | MEASURABLE |  | 26.608756 | 26.608756 | -11.585963 | 35.885645 | 0.128871 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q02\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.020000 | False | DEV | 1438 | 0 | 1438 | 751 | 687 | 1.833916 | -5.906004 | 1377.271279 | -4057.424530 | -1.863806 | -2680.153251 | -3332.940070 | -3739.714343 | -4781.142292 | -5048.794204 | -4664.494342 | 1307 | 0.602225 | 0.440678 | 26 | 59 | 19.178700 | 1 | MEASURABLE |  | 3.360039 | 3.360039 | -6.041002 | 2.452144 | 0.807193 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q02\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.020000 | False | HOLD_B | 133 | 0 | 133 | 67 | 66 | 1.259495 | -10.434735 | 84.386143 | -688.692500 | -4.543657 | -604.306356 | -947.861682 | -1187.611999 | -1686.811486 | -1623.389258 | -1584.275946 | 123 | 0.609023 | 0.428571 | 3 | 7 | 0.050300 | 1 | MEASURABLE |  | 2.815150 | 2.815150 | -15.216834 | 6.652889 | 0.804196 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q02\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.020000 | True | DEV | 428 | 0 | 428 | 265 | 163 | 6.233083 | -9.525158 | 1651.766991 | -1552.600756 | 0.231697 | 99.166235 | -553.620584 | -916.292584 | -1864.137581 | -2545.663119 | -1808.122692 | 379 | 0.577103 | 0.517241 | 30 | 58 | 21.843800 | 1 | MEASURABLE |  | 2.779119 | 2.779119 | -11.217899 | 10.810289 | 0.488511 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q02\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.020000 | True | HOLD_B | 42 | 0 | 42 | 26 | 16 | 32.220887 | -18.166642 | 837.743062 | -290.666274 | 13.025638 | 547.076788 | 203.521462 | -36.228854 | -480.492614 | -461.345384 | -491.053186 | 38 | 0.619048 | 0.333333 | 2 | 6 | 0.076200 | 1 | MEASURABLE |  | 2.168458 | 2.168458 | -14.147280 | 38.723909 | 0.138861 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q05\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.050000 | False | DEV | 3700 | 0 | 3700 | 1896 | 1804 | -0.590504 | -3.695257 | -1119.595646 | -6666.244060 | -2.104281 | -7785.839706 | -8438.626526 | -8845.400798 | -9953.517225 | -10855.972730 | -9915.789409 | 3096 | 0.593243 | 0.423729 | 25 | 59 | 16.639400 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -4.754886 | 0.559239 | 0.944056 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q05\|g0 | 1h | 60 | SIDE | ROLLING_180D | 0.050000 | False | HOLD_B | 379 | 0 | 379 | 184 | 195 | 1.039693 | -0.901269 | 191.303478 | -175.747457 | 0.041045 | 15.556021 | -327.999305 | -576.664332 | -1209.199903 | -1566.599346 | -1261.451905 | 319 | 0.614776 | 0.428571 | 3 | 7 | -0.516400 | 1 | MEASURABLE |  | 1.433790 | 1.433790 | -6.697193 | 6.877687 | 0.463536 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q05\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.050000 | True | DEV | 974 | 0 | 974 | 591 | 383 | 1.306564 | -6.410358 | 772.179234 | -2455.167214 | -1.727914 | -1682.987981 | -2335.774800 | -2732.185386 | -3773.613335 | -4438.972739 | -3728.906027 | 807 | 0.568789 | 0.500000 | 29 | 58 | 30.229900 | 1 | MEASURABLE |  | 1.793202 | 1.793202 | -8.896184 | 4.746590 | 0.735265 | 1000 | 120 | 1.000000 |
| 1h_h60\|SIDE\|ROLLING_180D\|q05\|g1 | 1h | 60 | SIDE | ROLLING_180D | 0.050000 | True | HOLD_B | 104 | 0 | 104 | 62 | 42 | 17.988136 | 1.389682 | 1115.264463 | 58.366629 | 11.284914 | 1173.631092 | 830.075767 | 590.325450 | 42.962617 | -312.473903 | -117.640662 | 87 | 0.625000 | 0.500000 | 3 | 6 | 3.175000 | 1 | MEASURABLE |  | 2.189592 | 2.189592 | -5.498303 | 25.888643 | 0.075924 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.010000 | False | DEV | 12 | 2 | 10 | 10 | 0 | 82.110210 | nan | 821.102101 | 0.000000 | 82.110210 | 821.102101 | 214.678144 | -184.658027 | -443.159271 | -249.405955 | -443.159271 | 10 | 0.500000 | 0.500000 | 2 | 4 | 1.412200 | 1 | MEASURABLE |  | 3.698783 | 3.698783 | -58.862458 | 186.472463 | 0.124875 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.010000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.010000 | True | DEV | 11 | 2 | 9 | 9 | 0 | 46.862881 | nan | 421.765929 | 0.000000 | 46.862881 | 421.765929 | -184.658027 | -347.622165 | -412.370093 | -173.036063 | -412.370093 | 9 | 0.444444 | 0.500000 | 2 | 4 | 1.412200 | 1 | MEASURABLE |  | 12.560924 | 12.560924 | -70.502173 | 114.117869 | 0.174825 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.010000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.020000 | False | DEV | 56 | 15 | 41 | 39 | 2 | 72.904942 | -124.944297 | 2843.292720 | -249.888595 | 63.253759 | 2593.404125 | 1986.980169 | 1569.708407 | 377.708579 | 524.112488 | 385.604489 | 31 | 0.585366 | 0.700000 | 7 | 10 | -10.699200 | 1 | MEASURABLE |  | 8.081190 | 8.081190 | -16.380702 | 120.777868 | 0.056943 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.020000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.020000 | True | DEV | 42 | 12 | 30 | 29 | 1 | 46.604922 | -245.164482 | 1351.542742 | -245.164482 | 36.879275 | 1106.378260 | 499.954304 | 94.456952 | -853.882756 | -116.376059 | -636.501657 | 21 | 0.533333 | 0.875000 | 7 | 8 | -9.402200 | 1 | MEASURABLE |  | 3.604829 | 3.604829 | -9.568583 | 77.425732 | 0.044955 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.020000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.050000 | False | DEV | 212 | 42 | 170 | 132 | 38 | 23.570768 | 21.029274 | 3111.341342 | 799.112396 | 23.002669 | 3910.453738 | 3255.054770 | 2648.630814 | 1643.086067 | 1600.134726 | 1989.060689 | 144 | 0.588235 | 0.634146 | 26 | 41 | -17.892600 | 1 | MEASURABLE |  | 28.133013 | 28.133013 | 8.877694 | 36.013888 | 0.003996 | 1000 | 120 | 0.479520 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 120 | MAX | EXPANDING_OOS | 0.050000 | False | HOLD_B | 11 | 0 | 11 | 10 | 1 | 12.431708 | -449.042875 | 124.317080 | -449.042875 | -29.520527 | -324.725795 | -541.655413 | -582.942577 | -652.040741 | -652.040741 | -652.040741 | 11 | 0.636364 | 0.600000 | 3 | 5 | 1.954600 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -109.004923 | 71.950923 | 0.777223 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.050000 | True | DEV | 94 | 23 | 71 | 66 | 5 | 21.662750 | 23.832002 | 1429.741483 | 119.160008 | 21.815514 | 1548.901491 | 942.477534 | 572.618889 | -288.151950 | 45.324230 | -615.628453 | 54 | 0.577465 | 0.590909 | 13 | 22 | -19.952700 | 1 | MEASURABLE |  | 19.492828 | 19.492828 | -3.098700 | 45.380909 | 0.046953 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 120 | MAX | EXPANDING_OOS | 0.050000 | True | HOLD_B | 7 | 0 | 7 | 6 | 1 | 3.988708 | -449.042875 | 23.932249 | -449.042875 | -60.730089 | -425.110626 | -642.040244 | -663.053982 | -597.348563 | -597.348563 | -597.348563 | 7 | 0.428571 | 0.333333 | 1 | 3 | 0.972700 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -183.510489 | 131.951960 | 0.791209 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.010000 | False | DEV | 55 | 6 | 49 | 10 | 39 | 82.110210 | 11.337038 | 821.102101 | 442.144482 | 25.780542 | 1263.246582 | 656.822626 | 257.486455 | -493.247078 | -526.994398 | -493.247078 | 47 | 0.571429 | 0.650000 | 13 | 20 | -6.293200 | 1 | MEASURABLE |  | 7.902636 | 7.902636 | -10.119751 | 55.997232 | 0.062937 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.010000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.010000 | True | DEV | 19 | 2 | 17 | 9 | 8 | 46.862881 | -13.149028 | 421.765929 | -105.192223 | 18.621983 | 316.573706 | -289.850250 | -502.497220 | -955.915572 | -659.451608 | -955.915572 | 17 | 0.470588 | 0.428571 | 3 | 7 | -4.941600 | 1 | MEASURABLE |  | 10.701165 | 10.701165 | -54.202133 | 79.588574 | 0.262737 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.010000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.020000 | False | DEV | 205 | 42 | 163 | 43 | 120 | 52.517805 | 0.398096 | 2258.265598 | 47.771491 | 14.147467 | 2306.037089 | 1699.613133 | 1282.341371 | 194.140747 | 343.986143 | 89.328678 | 145 | 0.595092 | 0.574468 | 27 | 47 | -42.734800 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -4.516213 | 31.224452 | 0.072927 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.020000 | False | HOLD_B | 2 | 0 | 2 | 1 | 1 | -44.876062 | -449.042875 | -44.876062 | -449.042875 | -246.959469 | -493.918938 | -449.042875 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 | 0 | 2 | 0.565200 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -493.918938 | 246.959469 | 0.882118 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.020000 | True | DEV | 78 | 16 | 62 | 32 | 30 | 35.761704 | -3.937506 | 1144.374532 | -118.125186 | 16.552409 | 1026.249346 | 419.825390 | 14.328038 | -934.011670 | -346.341077 | -936.759264 | 52 | 0.580645 | 0.666667 | 16 | 24 | -24.985900 | 1 | MEASURABLE |  | 7.384531 | 7.384531 | -11.495003 | 41.315500 | 0.108891 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.020000 | True | HOLD_B | 2 | 0 | 2 | 1 | 1 | -44.876062 | -449.042875 | -44.876062 | -449.042875 | -246.959469 | -493.918938 | -449.042875 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 | 0 | 2 | 0.565200 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -493.918938 | 246.959469 | 0.882118 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.050000 | False | DEV | 979 | 165 | 814 | 256 | 558 | 18.110152 | -1.231557 | 4636.198882 | -687.208883 | 4.851339 | 3948.989999 | 3293.591032 | 2687.167075 | 1527.095885 | 795.644832 | 1417.776886 | 742 | 0.577396 | 0.625000 | 35 | 56 | -118.558500 | 1 | MEASURABLE |  | 3.551385 | 3.551385 | -2.354188 | 11.969718 | 0.096903 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 120 | SIDE | EXPANDING_OOS | 0.050000 | False | HOLD_B | 60 | 3 | 57 | 27 | 30 | -1.787490 | -4.133189 | -48.262229 | -123.995679 | -3.022069 | -172.257909 | -389.187526 | -580.525916 | -973.596577 | -925.357675 | -973.596577 | 57 | 0.561404 | 0.500000 | 3 | 6 | 1.756500 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -25.937824 | 20.604874 | 0.605395 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.050000 | True | DEV | 268 | 48 | 220 | 104 | 116 | 18.483479 | -4.672049 | 1922.281846 | -541.957708 | 6.274201 | 1380.324137 | 773.900181 | 404.041536 | -616.382249 | -479.932399 | -987.506365 | 197 | 0.577273 | 0.563636 | 31 | 55 | -42.557600 | 1 | MEASURABLE |  | 8.803957 | 8.803957 | -8.630613 | 21.868800 | 0.186813 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 120 | SIDE | EXPANDING_OOS | 0.050000 | True | HOLD_B | 17 | 0 | 17 | 10 | 7 | -4.884063 | -34.471315 | -48.840634 | -241.299208 | -17.067050 | -290.139842 | -507.069460 | -579.846423 | -731.478474 | -764.329120 | -731.478474 | 17 | 0.588235 | 0.500000 | 3 | 6 | 1.124200 | 1 | MEASURABLE |  | 1.773562 | 1.773562 | -72.959620 | 49.645796 | 0.744256 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.010000 | False | DEV | 331 | 40 | 291 | 215 | 76 | 19.103133 | -4.293795 | 4107.173527 | -326.328420 | 12.992595 | 3780.845107 | 3174.421151 | 2775.084980 | 1779.497955 | 1805.258189 | 1709.366414 | 273 | 0.628866 | 0.640000 | 32 | 50 | -5.883600 | 1 | MEASURABLE |  | 4.405770 | 4.405770 | 1.677628 | 24.491942 | 0.011988 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.010000 | False | HOLD_B | 33 | 2 | 31 | 29 | 2 | -9.453783 | -216.110272 | -274.159693 | -432.220544 | -22.786459 | -706.380237 | -923.309855 | -1017.122285 | -1208.543852 | -1230.164377 | -1208.543852 | 31 | 0.612903 | 0.166667 | 1 | 6 | 1.524200 | 1 | MEASURABLE |  | 1.245802 | 1.245802 | -63.627287 | 26.317268 | 0.843157 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.010000 | True | DEV | 140 | 23 | 117 | 99 | 18 | 20.878366 | 1.369625 | 2066.958248 | 24.653253 | 17.877021 | 2091.611501 | 1485.187545 | 1098.021241 | 223.964085 | 471.894057 | 123.932012 | 102 | 0.623932 | 0.628571 | 22 | 35 | -14.640500 | 1 | MEASURABLE |  | 11.281602 | 11.281602 | -0.757024 | 38.639862 | 0.033966 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.010000 | True | HOLD_B | 13 | 0 | 13 | 12 | 1 | -22.308357 | -449.042875 | -267.700284 | -449.042875 | -55.134089 | -716.743160 | -933.672777 | -1027.485208 | -1137.322685 | -1137.322685 | -1137.322685 | 13 | 0.384615 | 0.000000 | 0 | 5 | 1.493600 | 1 | MEASURABLE |  | 2.612047 | 2.612047 | -139.779435 | 52.186746 | 0.859141 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q02\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.020000 | False | DEV | 680 | 95 | 585 | 418 | 167 | 16.816766 | 1.291231 | 7029.408164 | 215.635590 | 12.384690 | 7245.043753 | 6571.509932 | 5916.110965 | 4479.518806 | 4514.356980 | 4575.633341 | 551 | 0.641026 | 0.618182 | 34 | 55 | 29.929700 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | 3.676785 | 21.170988 | 0.002997 | 1000 | 120 | 0.359640 |
| 1h_h120\|MAX\|ROLLING_180D\|q02\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.020000 | False | HOLD_B | 74 | 2 | 72 | 61 | 11 | -9.815060 | -46.101329 | -598.718686 | -507.114623 | -15.358796 | -1105.833309 | -1341.766724 | -1558.696341 | -1914.646256 | -2049.027015 | -1914.646256 | 72 | 0.541667 | 0.285714 | 2 | 7 | 2.768300 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -39.896066 | 12.309288 | 0.889111 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q02\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.020000 | True | DEV | 242 | 41 | 201 | 160 | 41 | 14.733528 | -5.709927 | 2357.364409 | -234.107000 | 10.563470 | 2123.257409 | 1449.723588 | 843.299632 | -121.693416 | 493.399962 | -476.203318 | 180 | 0.626866 | 0.531915 | 25 | 47 | 11.643800 | 1 | MEASURABLE |  | 9.243785 | 9.243785 | -4.525786 | 25.632524 | 0.085914 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q02\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.020000 | True | HOLD_B | 25 | 0 | 25 | 23 | 2 | -6.299768 | -196.641945 | -144.894674 | -393.283889 | -21.527143 | -538.178563 | -774.111978 | -991.041596 | -1217.612583 | -1273.371570 | -1217.612583 | 25 | 0.480000 | 0.333333 | 2 | 6 | 2.398200 | 1 | MEASURABLE |  | 3.975354 | 3.975354 | -76.670623 | 48.671145 | 0.744256 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q05\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.050000 | False | DEV | 1700 | 262 | 1438 | 966 | 472 | 7.918889 | -4.013108 | 7649.647002 | -1894.187201 | 4.002406 | 5755.459801 | 5081.925980 | 4426.527012 | 3021.444536 | 2795.459725 | 2984.157656 | 1343 | 0.611266 | 0.603448 | 35 | 58 | 33.392700 | 1 | MEASURABLE |  | 7.073441 | 7.073441 | -0.916002 | 9.051862 | 0.060939 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q05\|g0 | 1h | 120 | MAX | ROLLING_180D | 0.050000 | False | HOLD_B | 203 | 23 | 180 | 145 | 35 | -6.328452 | -2.485838 | -917.625600 | -87.004322 | -5.581277 | -1004.629922 | -1240.563337 | -1457.492955 | -2003.216264 | -2086.290172 | -2003.216264 | 173 | 0.538889 | 0.285714 | 2 | 7 | 4.350300 | 1 | MEASURABLE |  | 1.985037 | 1.985037 | -16.539033 | 7.181864 | 0.821179 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q05\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.050000 | True | DEV | 488 | 79 | 409 | 307 | 102 | 14.275253 | -6.481942 | 4382.502551 | -661.158105 | 9.098642 | 3721.344445 | 3047.810624 | 2441.386668 | 1353.449241 | 1634.056465 | 935.339949 | 380 | 0.616137 | 0.622642 | 33 | 53 | 14.034200 | 1 | MEASURABLE |  | 7.321871 | 7.321871 | -2.502981 | 20.100670 | 0.059940 | 1000 | 120 | 1.000000 |
| 1h_h120\|MAX\|ROLLING_180D\|q05\|g1 | 1h | 120 | MAX | ROLLING_180D | 0.050000 | True | HOLD_B | 55 | 5 | 50 | 43 | 7 | -4.197182 | -34.471315 | -180.478842 | -241.299208 | -8.435561 | -421.778050 | -657.711465 | -874.641083 | -1181.750096 | -1275.624199 | -1181.750096 | 48 | 0.540000 | 0.333333 | 2 | 6 | 2.507500 | 1 | MEASURABLE |  | 2.381111 | 2.381111 | -37.094685 | 31.721258 | 0.676324 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q01\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.010000 | False | DEV | 691 | 87 | 604 | 293 | 311 | 13.177266 | 1.303319 | 3860.938924 | 405.332207 | 7.063363 | 4266.271131 | 3659.847175 | 3260.511004 | 2187.520164 | 2033.621240 | 2134.735408 | 572 | 0.599338 | 0.607143 | 34 | 56 | -38.815900 | 1 | MEASURABLE |  | 4.155184 | 4.155184 | -0.602011 | 14.751836 | 0.033966 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q01\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.010000 | False | HOLD_B | 72 | 4 | 68 | 36 | 32 | -5.277266 | -4.986092 | -189.981560 | -159.554949 | -5.140243 | -349.536509 | -566.466126 | -757.804516 | -1150.875177 | -1194.303163 | -1150.875177 | 67 | 0.573529 | 0.571429 | 4 | 7 | 1.491800 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -25.197483 | 18.538003 | 0.670330 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q01\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.010000 | True | DEV | 232 | 38 | 194 | 125 | 69 | 16.346183 | -0.474118 | 2043.272862 | -32.714169 | 10.363705 | 2010.558693 | 1404.134737 | 1016.968433 | 142.911276 | 379.535823 | 42.879204 | 176 | 0.608247 | 0.612245 | 30 | 49 | -15.167900 | 1 | MEASURABLE |  | 3.062367 | 3.062367 | -5.949667 | 25.939878 | 0.105894 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q01\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.010000 | True | HOLD_B | 21 | 0 | 21 | 14 | 7 | -14.893599 | -34.471315 | -208.510382 | -241.299208 | -21.419504 | -449.809590 | -666.739208 | -760.551638 | -951.154855 | -989.269972 | -951.154855 | 21 | 0.619048 | 0.333333 | 2 | 6 | 1.090400 | 1 | MEASURABLE |  | 2.423290 | 2.423290 | -80.995816 | 43.190454 | 0.781219 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q02\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.020000 | False | DEV | 1407 | 209 | 1198 | 584 | 614 | 13.380265 | -1.794912 | 7814.074548 | -1102.075791 | 5.602670 | 6711.998757 | 6038.464936 | 5383.065968 | 3946.473809 | 3606.809565 | 3943.051286 | 1129 | 0.606010 | 0.610169 | 36 | 59 | -61.684300 | 1 | MEASURABLE |  | 5.097126 | 5.097126 | -0.035156 | 11.022372 | 0.026973 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q02\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.020000 | False | HOLD_B | 148 | 11 | 137 | 75 | 62 | -3.512243 | -1.139400 | -263.418214 | -70.642803 | -2.438402 | -334.061017 | -569.994432 | -800.168014 | -1384.843075 | -1448.734887 | -1384.843075 | 133 | 0.576642 | 0.428571 | 3 | 7 | 2.864800 | 1 | MEASURABLE |  | 1.159152 | 1.159152 | -16.548517 | 13.105102 | 0.599401 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q02\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.020000 | True | DEV | 387 | 61 | 326 | 205 | 121 | 13.620953 | -7.766793 | 2792.295441 | -939.781963 | 5.682557 | 1852.513478 | 1178.979657 | 572.555701 | -453.142543 | -139.092958 | -824.266659 | 302 | 0.588957 | 0.545455 | 30 | 55 | 0.459000 | 1 | MEASURABLE |  | 6.831036 | 6.831036 | -5.418187 | 17.044928 | 0.169830 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q02\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.020000 | True | HOLD_B | 36 | 0 | 36 | 25 | 11 | -4.373634 | -54.995371 | -109.340862 | -604.949080 | -19.841387 | -714.289942 | -950.223357 | -1167.152975 | -1487.412910 | -1543.171896 | -1487.412910 | 36 | 0.555556 | 0.333333 | 2 | 6 | 4.113100 | 1 | MEASURABLE |  | 2.296434 | 2.296434 | -67.970893 | 36.414282 | 0.770230 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q05\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.050000 | False | DEV | 3607 | 649 | 2958 | 1443 | 1515 | 5.714069 | -1.455664 | 8245.401043 | -2205.330933 | 2.041944 | 6040.070109 | 5360.627302 | 4687.093481 | 2831.993125 | 2261.991274 | 2827.649267 | 2727 | 0.592968 | 0.610169 | 36 | 59 | -138.877900 | 1 | MEASURABLE |  | 3.024277 | 3.024277 | -1.332987 | 5.375504 | 0.107892 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q05\|g0 | 1h | 120 | SIDE | ROLLING_180D | 0.050000 | False | HOLD_B | 409 | 62 | 347 | 182 | 165 | -2.912262 | -4.970103 | -530.031664 | -820.067043 | -3.890774 | -1350.098707 | -1586.032122 | -1816.205704 | -2439.115316 | -2459.011513 | -2439.115316 | 329 | 0.538905 | 0.428571 | 3 | 7 | 2.937600 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -12.514093 | 4.816986 | 0.802198 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q05\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.050000 | True | DEV | 891 | 145 | 746 | 442 | 304 | 11.990074 | -0.990106 | 5299.612603 | -300.992341 | 6.700563 | 4998.620263 | 4319.177455 | 3645.643634 | 1977.863599 | 1927.581925 | 1502.436616 | 696 | 0.576408 | 0.568966 | 33 | 58 | -15.168600 | 1 | MEASURABLE |  | 3.947889 | 3.947889 | -2.544883 | 15.453695 | 0.081918 | 1000 | 120 | 1.000000 |
| 1h_h120\|SIDE\|ROLLING_180D\|q05\|g1 | 1h | 120 | SIDE | ROLLING_180D | 0.050000 | True | HOLD_B | 98 | 9 | 89 | 55 | 34 | -1.191798 | -5.272000 | -65.548914 | -179.248001 | -2.750527 | -244.796914 | -480.730329 | -697.659947 | -1266.450011 | -1448.505437 | -1266.450011 | 85 | 0.561798 | 0.500000 | 3 | 6 | 4.726000 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -25.454786 | 22.061182 | 0.581419 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.010000 | False | DEV | 11 | 7 | 4 | 4 | 0 | 120.486446 | nan | 481.945786 | 0.000000 | 120.486446 | 481.945786 | -428.202246 | -374.773512 | 0.000000 | 0.000000 | 0.000000 | 2 | 0.250000 | 1.000000 | 1 | 1 | -0.058000 | 1 | MEASURABLE |  | 27.448909 | 27.448909 | -227.537008 | 240.972893 | 0.101898 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q01\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.010000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.010000 | True | DEV | 11 | 7 | 4 | 4 | 0 | 120.486446 | nan | 481.945786 | 0.000000 | 120.486446 | 481.945786 | -428.202246 | -374.773512 | 0.000000 | 0.000000 | 0.000000 | 2 | 0.250000 | 1.000000 | 1 | 1 | -0.058000 | 1 | MEASURABLE |  | 27.448909 | 27.448909 | -227.537008 | 240.972893 | 0.101898 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q01\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.010000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.020000 | False | DEV | 22 | 12 | 10 | 10 | 0 | 52.903456 | nan | 529.034564 | 0.000000 | 52.903456 | 529.034564 | -381.113468 | -728.210555 | -981.705960 | 0.000000 | -664.688811 | 7 | 0.500000 | 0.750000 | 3 | 4 | -3.849000 | 1 | MEASURABLE |  | 22.050417 | 22.050417 | -61.763105 | 134.792805 | 0.168831 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q02\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.020000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.020000 | True | DEV | 22 | 12 | 10 | 10 | 0 | 52.903456 | nan | 529.034564 | 0.000000 | 52.903456 | 529.034564 | -381.113468 | -728.210555 | -981.705960 | 0.000000 | -664.688811 | 7 | 0.500000 | 0.750000 | 3 | 4 | -3.849000 | 1 | MEASURABLE |  | 22.050417 | 22.050417 | -61.763105 | 134.792805 | 0.168831 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q02\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.020000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.050000 | False | DEV | 61 | 25 | 36 | 29 | 7 | 4.625223 | -44.244813 | 134.131479 | -309.713693 | -4.877284 | -175.582214 | -565.455558 | -912.552646 | -1870.551133 | -1719.883087 | -1749.055653 | 33 | 0.472222 | 0.437500 | 7 | 16 | 4.811800 | 1 | MEASURABLE |  | 3.701859 | 3.701859 | -56.286271 | 63.249513 | 0.558442 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q05\|g0 | 1h | 240 | MAX | EXPANDING_OOS | 0.050000 | False | HOLD_B | 5 | 2 | 3 | 3 | 0 | 35.115812 | nan | 105.347435 | 0.000000 | 35.115812 | 105.347435 | 48.330150 | 4.104532 | 0.000000 | 0.000000 | 0.000000 | 3 | 1.000000 | 1.000000 | 2 | 2 | 0.000000 | 1 | MEASURABLE |  | 3.337532 | 3.337532 | -33.747634 | 70.231623 | 0.135864 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.050000 | True | DEV | 37 | 17 | 20 | 18 | 2 | -3.507590 | -129.642968 | -63.136625 | -259.285937 | -16.121128 | -322.422562 | -669.519649 | -1007.817164 | -1579.010031 | -1288.571808 | -1579.010031 | 18 | 0.400000 | 0.400000 | 4 | 10 | 4.502300 | 1 | MEASURABLE |  | 6.327590 | 6.327590 | -79.441707 | 46.666430 | 0.706294 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|EXPANDING_OOS\|q05\|g1 | 1h | 240 | MAX | EXPANDING_OOS | 0.050000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.010000 | False | DEV | 77 | 44 | 33 | 4 | 29 | 120.486446 | -14.283602 | 481.945786 | -414.224463 | 2.052161 | 67.721323 | -842.426709 | -1046.590151 | -1348.294861 | -1458.541891 | -1348.294861 | 28 | 0.515152 | 0.222222 | 2 | 9 | -5.102000 | 1 | MEASURABLE |  | 15.715524 | 15.715524 | -46.216454 | 47.858689 | 0.431568 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q01\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.010000 | False | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.010000 | True | DEV | 23 | 10 | 13 | 4 | 9 | 120.486446 | -25.064169 | 481.945786 | -225.577524 | 19.720636 | 256.368262 | -653.779770 | -857.943212 | -1029.804835 | -1013.279621 | -1029.804835 | 11 | 0.384615 | 0.285714 | 2 | 7 | -0.579200 | 1 | MEASURABLE |  | 18.966143 | 18.966143 | -95.119088 | 101.631154 | 0.317682 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q01\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.010000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.020000 | False | DEV | 140 | 71 | 69 | 10 | 59 | 52.903456 | 15.138545 | 529.034564 | 893.174128 | 20.611720 | 1422.208692 | 512.060660 | -225.361648 | -1122.520511 | -664.224310 | -922.244611 | 58 | 0.536232 | 0.772727 | 17 | 22 | -29.229800 | 1 | MEASURABLE |  | 7.887572 | 7.887572 | -8.519817 | 49.236395 | 0.076923 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q02\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.020000 | False | HOLD_B | 1 | 0 | 1 | 0 | 1 | nan | 37.264384 | 0.000000 | 37.264384 | 37.264384 | 37.264384 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 | 1.000000 | 1.000000 | 1 | 1 | 0.000000 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -37.264384 | 74.528767 | 0.249750 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.020000 | True | DEV | 40 | 16 | 24 | 10 | 14 | 52.903456 | 10.623763 | 529.034564 | 148.732679 | 28.240302 | 677.767243 | -232.380789 | -579.477876 | -1198.252834 | -908.048247 | -997.976934 | 21 | 0.583333 | 0.666667 | 8 | 12 | -5.450200 | 1 | MEASURABLE |  | 14.049153 | 14.049153 | -33.173283 | 89.004197 | 0.161838 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q02\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.020000 | True | HOLD_B | 0 | 0 | 0 | 0 | 0 | nan | nan | 0.000000 | 0.000000 | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | nan | nan | 0 | 0 | 0.000000 | 0 | UNMEASURABLE | zero trades | nan | nan | nan | nan | nan | 0 | 120 | nan |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.050000 | False | DEV | 609 | 215 | 394 | 59 | 335 | 13.925490 | -4.574823 | 821.603929 | -1532.565723 | -1.804472 | -710.961795 | -1448.384103 | -2094.028736 | -3577.422086 | -3309.181856 | -3577.422086 | 376 | 0.565990 | 0.490566 | 26 | 53 | -140.735300 | 1 | MEASURABLE |  | 2.250555 | 2.250555 | -14.916197 | 12.626398 | 0.609391 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q05\|g0 | 1h | 240 | SIDE | EXPANDING_OOS | 0.050000 | False | HOLD_B | 44 | 14 | 30 | 14 | 16 | 77.905896 | -4.316742 | 1090.682550 | -69.067865 | 34.053823 | 1021.614685 | 626.289852 | 260.627002 | -163.008961 | -167.959183 | -163.008961 | 30 | 0.666667 | 0.833333 | 5 | 6 | 0.646200 | 1 | MEASURABLE |  | 2.424951 | 2.424951 | -9.107022 | 72.062184 | 0.064935 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.050000 | True | DEV | 164 | 47 | 117 | 31 | 86 | 6.722960 | -5.410357 | 208.411773 | -465.290701 | -2.195546 | -256.878928 | -866.506148 | -1213.603236 | -2047.903370 | -2117.111557 | -2047.903370 | 115 | 0.555556 | 0.500000 | 23 | 46 | -37.882600 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -30.915231 | 34.918737 | 0.548452 | 1000 | 120 | 1.000000 |
| 1h_h240\|SIDE\|EXPANDING_OOS\|q05\|g1 | 1h | 240 | SIDE | EXPANDING_OOS | 0.050000 | True | HOLD_B | 12 | 1 | 11 | 6 | 5 | 87.710138 | -50.594495 | 526.260831 | -252.972475 | 24.844396 | 273.288356 | -92.374493 | -203.839995 | -370.995526 | -370.995526 | -370.995526 | 11 | 0.636364 | 0.400000 | 2 | 5 | 0.889500 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -59.322228 | 95.336192 | 0.244755 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 240 | MAX | ROLLING_180D | 0.010000 | False | DEV | 346 | 96 | 250 | 172 | 78 | 16.001193 | -14.676266 | 2752.205218 | -1144.748775 | 6.429826 | 1607.456443 | 296.785352 | -547.402845 | -1834.932874 | -1451.389549 | -1834.932874 | 243 | 0.564000 | 0.521739 | 24 | 46 | 32.292300 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -14.696989 | 25.628686 | 0.260739 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|ROLLING_180D\|q01\|g0 | 1h | 240 | MAX | ROLLING_180D | 0.010000 | False | HOLD_B | 44 | 12 | 32 | 29 | 3 | 39.944051 | 116.782811 | 1158.377491 | 350.348433 | 47.147685 | 1508.725924 | 1143.063074 | 826.922717 | 310.748906 | 169.955265 | 310.748906 | 32 | 0.656250 | 1.000000 | 6 | 6 | 2.973300 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | 3.232927 | 88.531140 | 0.022977 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 240 | MAX | ROLLING_180D | 0.010000 | True | DEV | 149 | 40 | 109 | 87 | 22 | 11.814895 | -15.125321 | 1027.895899 | -332.757060 | 6.377421 | 695.138839 | -615.532252 | -1459.720449 | -2599.098702 | -2019.795983 | -2599.098702 | 107 | 0.532110 | 0.538462 | 21 | 39 | 23.734700 | 1 | MEASURABLE_BLOCK1 | invalid Politis-White block length | nan | 1.000000 | -31.589539 | 38.773696 | 0.362637 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|ROLLING_180D\|q01\|g1 | 1h | 240 | MAX | ROLLING_180D | 0.010000 | True | HOLD_B | 11 | 1 | 10 | 9 | 1 | 61.654126 | -3.056308 | 554.887138 | -3.056308 | 55.183083 | 551.830830 | 186.167980 | 74.702478 | -102.510333 | -102.510333 | -102.510333 | 10 | 0.700000 | 0.750000 | 3 | 4 | 1.219100 | 1 | MEASURABLE |  | 1.215516 | 1.215516 | -30.253772 | 119.846678 | 0.079920 | 1000 | 120 | 1.000000 |
| 1h_h240\|MAX\|ROLLING_180D\|q02\|g0 | 1h | 240 | MAX | ROLLING_180D | 0.020000 | False | DEV | 673 | 215 | 458 | 318 | 140 | 15.290510 | -1.438117 | 4862.382272 | -201.336334 | 10.176956 | 4661.045939 | 3350.374848 | 2343.446435 | 409.940571 | 931.343973 | 409.940571 | 449 | 0.572052 | 0.580000 | 29 | 50 | 24.868200 | 1 | MEASURABLE |  | 4.080522 | 4.080522 | -5.291131 | 23.622306 | 0.070929 | 1000 | 120 | 1.000000 |

## k45_patchtst_updown_r2_21_20261003

- 테스트 재실행 `tests/test_k45_patchtst_updown_r2_21.py`: `9 passed in 3.67s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-03T11:44:30.041013+00:00 |
| run_finished_utc | 2026-10-03T11:45:02.265755+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 상승·하락 분리 PatchTST의 d = up_pred − down_pred 는 게이트 통과 바에서 15분 부호 수익과 DEV Spearman > 0 이고, 그 방향 규칙의 DEV net이 같은 바의 fade 규칙보다 높다. |
| folds | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, |
| seeds | [42, 43, 44] |
| params | {"learning_rate": 0.001, "weight_decay": 1e-05, "batch_size": 1024, "max_epochs": 15, "patience": 3} |
| sequence_inputs | ["abs_close_log_return_bps", "high_low_log_range_bps", "abs_body_log_bps", "upper_wick_log_bps", "lower_wick_log_bps", "log1p_quote_volume", "log1p_trade_count"] |
| static_inputs | ["range_240_bps", "range_1440_bps", "rv_240_bps", "rv_1440_bps", "log1p_quote_volume_sum_240", "log1p_quote_volume_sum_1440", "log1p_trade_count_sum_240", "log1p_trade_count_sum_1440", "minute_of_week_sin01", "minute_of_week_cos01"] |
| lookback | 60 |
| span | 15 |
| loss | mean(MAE(up),MAE(down),MAE(range)) |
| device | cuda |
| local_data_only | True |
| downloads | 0 |
| live_orders | 0 |
| seed_fit_seconds | 13881.92813519435 |
| elapsed_wall_seconds | 15337.031409 |

### out_of_sample_result (원문)

```text
{
 "primary_gate": "G_STOP",
 "dev_spearman_gt_0": true,
 "dev_net_gt_fade": false,
 "direction_net_mean_bps": -4.062658609665129,
 "fade_net_mean_bps": -3.0256465688888223,
 "result": "FAIL"
}
```

- 출력 해시 확인: 4026/4027 일치
  - CHANGED: out\k45_patchtst_updown_r2_21_20261003\queue.log

### REPORT.md 앞 150줄 (전체 3267줄, 원문)

# R2-21

## SOURCE

- k45_manifest: `out/k45_gate_direction_20261001/manifest.json`
- k45_script: `out/k45_gate_direction.py`
- old_fold_0_405: `out\patchtst_backward_k45_validation_20260929\ensemble_predictions.parquet`
- old_fold_406_605: `out\patchtst_post_trigger_markout_20260929\exploration_origins.parquet`
- old_fold_606_666: `out\patchtst_down_breakout_long_confirmation_20260929\ensemble_predictions.parquet`
- old_checkpoints_0_405: `out\patchtst_backward_k45_validation_20260929`
- old_checkpoints_406_605: `out\patchtst_excursion_range_20260928`
- old_checkpoints_606_666: `out\patchtst_down_breakout_long_confirmation_20260929`
- folds: 0..666
- seeds: [42, 43, 44]
- span: 15
- lookback: 60
- params: `{"learning_rate": 0.001, "weight_decay": 1e-05, "batch_size": 1024, "max_epochs": 15, "patience": 3}`
- checkpoint: `out\k45_patchtst_updown_r2_21_20261003\checkpoints`

## TIME

| pilot_folds | pilot_fold_mean_seconds | pilot_full_estimate_seconds | checkpoint_count | seed_fit_seconds | seed_fit_mean_seconds | first_full_start_utc | full_complete_utc | elapsed_wall_seconds | full_process_runs | final_pass_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 25.275205 | 16858.561913 | 2001 | 13881.928135 | 6.937495 | 2026-10-03T07:21:33.293462+00:00 | 2026-10-03T11:37:10.324871+00:00 | 15337.031409 | 2 | 1944.362649 |

## PARITY

| segment | n | spearman_new_max_vs_old_excursion |
| --- | --- | --- |
| DEV | 173922 | 0.994180 |
| HOLD_B | 17315 | 0.998078 |

## HEAD

| segment | head | n | spearman | mae_bps | months | months_same_sign |
| --- | --- | --- | --- | --- | --- | --- |
| DEV | up | 173922 | 0.472540 | 13.519728 | 60 | 60 |
| DEV | down | 173922 | 0.481309 | 13.841265 | 60 | 60 |
| DEV | range | 173922 | 0.798853 | 14.685249 | 60 | 60 |
| HOLD_B | up | 17315 | 0.436045 | 10.937247 | 6 | 6 |
| HOLD_B | down | 17315 | 0.435399 | 11.151791 | 6 | 6 |
| HOLD_B | range | 17315 | 0.760486 | 11.572906 | 6 | 6 |

## HEAD_MONTHLY

| segment | head | month | n | spearman |
| --- | --- | --- | --- | --- |
| DEV | up | 2021-01 | 2296 | 0.298342 |
| DEV | up | 2021-02 | 2679 | 0.272273 |
| DEV | up | 2021-03 | 2966 | 0.243424 |
| DEV | up | 2021-04 | 2870 | 0.297928 |
| DEV | up | 2021-05 | 2965 | 0.393257 |
| DEV | up | 2021-06 | 2870 | 0.227345 |
| DEV | up | 2021-07 | 2966 | 0.242218 |
| DEV | up | 2021-08 | 2966 | 0.252470 |
| DEV | up | 2021-09 | 2870 | 0.293586 |
| DEV | up | 2021-10 | 2965 | 0.240963 |
| DEV | up | 2021-11 | 2870 | 0.264819 |
| DEV | up | 2021-12 | 2966 | 0.278181 |
| DEV | up | 2022-01 | 2966 | 0.340442 |
| DEV | up | 2022-02 | 2678 | 0.348114 |
| DEV | up | 2022-03 | 2966 | 0.334759 |
| DEV | up | 2022-04 | 2870 | 0.322882 |
| DEV | up | 2022-05 | 2966 | 0.432447 |
| DEV | up | 2022-06 | 2870 | 0.439304 |
| DEV | up | 2022-07 | 2965 | 0.312739 |
| DEV | up | 2022-08 | 2966 | 0.254466 |
| DEV | up | 2022-09 | 2870 | 0.341433 |
| DEV | up | 2022-10 | 2966 | 0.405326 |
| DEV | up | 2022-11 | 2870 | 0.468425 |
| DEV | up | 2022-12 | 2965 | 0.376359 |
| DEV | up | 2023-01 | 2966 | 0.526553 |
| DEV | up | 2023-02 | 2679 | 0.409032 |
| DEV | up | 2023-03 | 2965 | 0.466386 |
| DEV | up | 2023-04 | 2870 | 0.393859 |
| DEV | up | 2023-05 | 2966 | 0.334014 |
| DEV | up | 2023-06 | 2870 | 0.354652 |
| DEV | up | 2023-07 | 2966 | 0.383545 |
| DEV | up | 2023-08 | 2965 | 0.466845 |
| DEV | up | 2023-09 | 2870 | 0.447642 |
| DEV | up | 2023-10 | 2966 | 0.456922 |
| DEV | up | 2023-11 | 2870 | 0.412823 |
| DEV | up | 2023-12 | 2966 | 0.330589 |
| DEV | up | 2024-01 | 2965 | 0.381501 |
| DEV | up | 2024-02 | 2775 | 0.403488 |
| DEV | up | 2024-03 | 2965 | 0.395152 |
| DEV | up | 2024-04 | 2870 | 0.370452 |
| DEV | up | 2024-05 | 2966 | 0.357085 |
| DEV | up | 2024-06 | 2870 | 0.428052 |
| DEV | up | 2024-07 | 2966 | 0.328467 |
| DEV | up | 2024-08 | 2965 | 0.425373 |
| DEV | up | 2024-09 | 2870 | 0.397758 |
| DEV | up | 2024-10 | 2966 | 0.384787 |
| DEV | up | 2024-11 | 2870 | 0.409803 |
| DEV | up | 2024-12 | 2966 | 0.345602 |
| DEV | up | 2025-01 | 2965 | 0.448109 |
| DEV | up | 2025-02 | 2679 | 0.473729 |
| DEV | up | 2025-03 | 2966 | 0.446436 |
| DEV | up | 2025-04 | 2870 | 0.421723 |
| DEV | up | 2025-05 | 2965 | 0.365614 |
| DEV | up | 2025-06 | 2870 | 0.361425 |
| DEV | up | 2025-07 | 2966 | 0.349780 |
| DEV | up | 2025-08 | 2966 | 0.349686 |
| DEV | up | 2025-09 | 2870 | 0.366990 |
| DEV | up | 2025-10 | 2965 | 0.348200 |
| DEV | up | 2025-11 | 2870 | 0.361226 |
| DEV | up | 2025-12 | 2870 | 0.462714 |
| DEV | down | 2021-01 | 2296 | 0.274769 |
| DEV | down | 2021-02 | 2679 | 0.276544 |
| DEV | down | 2021-03 | 2966 | 0.218919 |
| DEV | down | 2021-04 | 2870 | 0.255573 |
| DEV | down | 2021-05 | 2965 | 0.403766 |
| DEV | down | 2021-06 | 2870 | 0.253992 |
| DEV | down | 2021-07 | 2966 | 0.248251 |
| DEV | down | 2021-08 | 2966 | 0.251692 |
| DEV | down | 2021-09 | 2870 | 0.266794 |
| DEV | down | 2021-10 | 2965 | 0.225446 |
| DEV | down | 2021-11 | 2870 | 0.312125 |
| DEV | down | 2021-12 | 2966 | 0.269076 |
| DEV | down | 2022-01 | 2966 | 0.360560 |
| DEV | down | 2022-02 | 2678 | 0.320905 |
| DEV | down | 2022-03 | 2966 | 0.326203 |
| DEV | down | 2022-04 | 2870 | 0.358159 |
| DEV | down | 2022-05 | 2966 | 0.466894 |
| DEV | down | 2022-06 | 2870 | 0.468336 |
| DEV | down | 2022-07 | 2965 | 0.277648 |
| DEV | down | 2022-08 | 2966 | 0.286879 |
| DEV | down | 2022-09 | 2870 | 0.324486 |
| DEV | down | 2022-10 | 2966 | 0.382960 |
| DEV | down | 2022-11 | 2870 | 0.480335 |
| DEV | down | 2022-12 | 2965 | 0.381618 |
| DEV | down | 2023-01 | 2966 | 0.500838 |
| DEV | down | 2023-02 | 2679 | 0.395378 |
| DEV | down | 2023-03 | 2965 | 0.448832 |
| DEV | down | 2023-04 | 2870 | 0.361562 |
| DEV | down | 2023-05 | 2966 | 0.357802 |
| DEV | down | 2023-06 | 2870 | 0.370674 |
| DEV | down | 2023-07 | 2966 | 0.424033 |
| DEV | down | 2023-08 | 2965 | 0.506289 |
| DEV | down | 2023-09 | 2870 | 0.414854 |
| DEV | down | 2023-10 | 2966 | 0.416911 |
| DEV | down | 2023-11 | 2870 | 0.400636 |
| DEV | down | 2023-12 | 2966 | 0.364300 |
| DEV | down | 2024-01 | 2965 | 0.391594 |
| DEV | down | 2024-02 | 2775 | 0.372046 |
| DEV | down | 2024-03 | 2965 | 0.444857 |
| DEV | down | 2024-04 | 2870 | 0.351802 |
| DEV | down | 2024-05 | 2966 | 0.349328 |
| DEV | down | 2024-06 | 2870 | 0.446969 |
| DEV | down | 2024-07 | 2966 | 0.351720 |

## k45_risk_stop_r2_18_20261002

- 테스트 재실행 `tests/test_k45_risk_stop_r2_18.py`: `8 passed in 1.97s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-18 |
| created_utc | 2026-10-02T10:16:43.070711+00:00 |
| started_utc | 2026-10-02T09:56:37.842161+00:00 |
| elapsed_seconds | 1205.124937 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| hypothesis_frozen | 최대 240분 보유 + ATR(14, 1h) × 1.5 손절 규칙에서, DEV로만 고른 롱 칸 1개 + 숏 칸 1개의 COMBO_SINGLE이 (a) DEV와 DEV_EX2020 모두 net > 0, (b) DEV 상위 5건 제거 후 net > 0, (c) DEV에서 롱 부분과 숏 부분이 각각 net > 0, (d) DEV 최대 낙폭이 BASE 조합보다 작다. |
| oos_result | {"a_dev_and_dev_ex2020_net_positive": true, "b_dev_top5_removed_net_positive": true, "c_dev_long_and_short_net_positive": true, "d_dev_drawdown_less_than_base": false, "pass": false, "hold_b_seen_net_positive": true, "hold_b_seen_net_bps": 559.3811064844739} |
| cell_count | 48 |
| base_stop_cell_count | 96 |
| multiple_testing_cell_count | 48 |
| workers | 1 |
| numeric_threads | 4 |
| model_training | False |
| live_orders | 0 |
| selected_at_utc | 2026-10-02T09:59:36.580968+00:00 |
| selection_input_segment | DEV |
| selected_cells | {"long": "R-TAIL/q=0.01/method=EXPANDING_OOS/direction=L", "short": "R-F3/tail=10/direction=S"} |
| selected_cells_sha256 | c603564b2b4f57d958f20b9fd425082a2c1435c01727a6d25e96cf6ae26183d0 |
| hold_b_metrics_computed_after_selection | True |
| pytest_last_line | 8 passed in 8.46s |
| unavailable_data | ["order_book", "liquidations", "artifacts/btcusdt_2026q3_source (excluded by instruction)"] |
| assumptions | {"entry_minute_stop": "STOP excludes it; STOP_CONS assumes adverse touch after fill", "atr": "Wilder ATR(14), last closed 1h bar, fixed at entry", "funding": "R2-14 UTC 00/08/16 prior-minute rate; entry < funding <= exit", "random": "1000 circular schedule shifts; same count/sides/nominal exposure; stop and cap recomputed", "hold_b": "already seen; excluded from hypothesis and selection", "hold_a": "2026 Q3 excluded and unread"} |

- 출력 해시 확인: 17/17 일치

### REPORT.md 앞 150줄 (전체 2554줄, 원문)

# R2-18

## reproduction

| source | cell | segment | n_expected | n_actual | net_expected_bps | net_actual_bps | max_abs_diff | match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-14 | F4\|1h\|5/4\|signal\|LS | DEV | 3329 | 3329 | 8837.356672 | 8837.356672 | 0.000000 | 1 |
| R2-14 | F4\|1h\|5/4\|signal\|LS | HOLD_B | 348 | 348 | 4364.242485 | 4364.242485 | 0.000000 | 1 |
| R2-14 | F3\|1h\|10/4\|signal\|S | DEV | 2140 | 2140 | 9333.247578 | 9333.247578 | 0.000000 | 1 |
| R2-14 | F3\|1h\|10/4\|signal\|S | HOLD_B | 108 | 108 | 260.352285 | 260.352285 | 0.000000 | 1 |
| R2-14 | G2\|1m\|before/60/60\|signal\|L | DEV | 713 | 713 | 5553.163853 | 5553.163853 | 0.000000 | 1 |
| R2-14 | G2\|1m\|before/60/60\|signal\|L | HOLD_B | 207 | 207 | 680.485058 | 680.485058 | 0.000000 | 1 |
| R2-14 | E1\|1h\|2\|signal\|L | DEV | 583 | 583 | 15518.360756 | 15518.360756 | 0.000000 | 1 |
| R2-14 | E1\|1h\|2\|signal\|L | HOLD_B | 49 | 49 | 1917.808048 | 1917.808048 | 0.000000 | 1 |
| R2-12 | 1h\|h=60\|15m\|E1\|k=1\|gate=1 | DEV | 1428 | 1428 | 5368.351262 | 5368.351262 | 0.000000 | 1 |
| R2-12 | 1h\|h=60\|15m\|E1\|k=1\|gate=1 | HOLD_B | 150 | 150 | 2116.352365 | 2116.352365 | 0.000000 | 1 |
| R2-7 | regression_rmse\|q=.05\|EXPANDING_OOS\|SINGLE\|LONG | DEV | 233 | 233 | 2175.965071 | 2175.965071 | 0.000000 | 1 |
| R2-7 | regression_rmse\|q=.05\|EXPANDING_OOS\|SINGLE\|SHORT | DEV | 232 | 232 | 1925.845200 | 1925.845200 | 0.000000 | 1 |
| R2-7 | regression_rmse\|q=.05\|EXPANDING_OOS\|SINGLE\|LONG | HOLD_B | 26 | 26 | 598.429132 | 598.429132 | 0.000000 | 1 |
| R2-7 | regression_rmse\|q=.05\|EXPANDING_OOS\|SINGLE\|SHORT | HOLD_B | 30 | 30 | 425.273297 | 425.273297 | 0.000000 | 1 |

## selected_cells

| long_cell | short_cell |
| --- | --- |
| R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | R-F3\|tail=10\|direction=S |

## combo_DEV_DEV_EX2020_HOLD_B

| cell_id | version | segment | n | net_mean_bps | net_total_bps | daily_sharpe | max_drawdown_bps | long_net_bps | short_net_bps | dropped_signal_n | overlap_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMBO_SINGLE | BASE | DEV | 2163 | 4.654230 | 10067.098689 | 0.647231 | 2953.133248 | 1135.639541 | 8931.459148 | 5768.000000 | 0.000000 |
| COMBO_SINGLE | BASE | DEV_EX2020 | 1929 | 4.484850 | 8651.275590 | 0.616504 | 2953.133248 | 1135.639541 | 7515.636049 | 5170.000000 | 0.000000 |
| COMBO_SINGLE | BASE | HOLD_B | 110 | 1.090918 | 120.000965 | 0.137901 | 1111.732363 | -140.351320 | 260.352285 | 270.000000 | 0.000000 |
| COMBO_SINGLE | STOP | DEV | 2307 | 4.787474 | 11044.702339 | 0.722312 | 3060.759196 | 1552.742165 | 9491.960174 | 5624.000000 | 0.000000 |
| COMBO_SINGLE | STOP | DEV_EX2020 | 2063 | 5.079471 | 10478.948540 | 0.752736 | 2325.655545 | 1552.742165 | 8926.206375 | 5036.000000 | 0.000000 |
| COMBO_SINGLE | STOP | HOLD_B | 120 | 4.661509 | 559.381106 | 0.667235 | 732.310116 | -186.277172 | 745.658279 | 260.000000 | 0.000000 |
| COMBO_SINGLE | STOP_1.0 | DEV | 2529 | 2.720892 | 6881.136504 | 0.480851 | 3380.109527 | 1466.326655 | 5414.809850 | 5402.000000 | 0.000000 |
| COMBO_SINGLE | STOP_1.0 | DEV_EX2020 | 2264 | 2.769405 | 6269.932134 | 0.489960 | 3380.109527 | 1466.326655 | 4803.605479 | 4835.000000 | 0.000000 |
| COMBO_SINGLE | STOP_1.0 | HOLD_B | 134 | 3.873031 | 518.986187 | 0.599746 | 1044.860957 | 246.832107 | 272.154080 | 246.000000 | 0.000000 |
| COMBO_SINGLE | STOP_2.0 | DEV | 2230 | 4.966695 | 11075.730387 | 0.720890 | 2727.340461 | 1375.602348 | 9700.128038 | 5701.000000 | 0.000000 |
| COMBO_SINGLE | STOP_2.0 | DEV_EX2020 | 1993 | 5.002345 | 9969.673565 | 0.721859 | 2727.340461 | 1375.602348 | 8594.071217 | 5106.000000 | 0.000000 |
| COMBO_SINGLE | STOP_2.0 | HOLD_B | 118 | 2.426244 | 286.296777 | 0.323063 | 901.926441 | -189.513447 | 475.810224 | 262.000000 | 0.000000 |
| COMBO_SINGLE | STOP_CONS | DEV | 2308 | 4.218608 | 9736.547160 | 0.630788 | 3060.759196 | 221.865550 | 9514.681610 | 5623.000000 | 0.000000 |
| COMBO_SINGLE | STOP_CONS | DEV_EX2020 | 2064 | 4.443214 | 9170.793361 | 0.652000 | 2523.667280 | 221.865550 | 8948.927811 | 5035.000000 | 0.000000 |
| COMBO_SINGLE | STOP_CONS | HOLD_B | 120 | 4.661509 | 559.381106 | 0.667235 | 732.310116 | -186.277172 | 745.658279 | 260.000000 | 0.000000 |
| COMBO_HEDGE | BASE | DEV | 2176 | 5.121130 | 11143.577884 | 0.702030 | 2909.974775 | 1810.330306 | 9333.247578 | 5755.000000 | 0.000202 |
| COMBO_HEDGE | BASE | DEV_EX2020 | 1942 | 5.009143 | 9727.754786 | 0.677702 | 2909.974775 | 1810.330306 | 7917.424480 | 5157.000000 | 0.000222 |
| COMBO_HEDGE | BASE | HOLD_B | 110 | 1.090918 | 120.000965 | 0.137901 | 1111.732363 | -140.351320 | 260.352285 | 270.000000 | 0.000000 |
| COMBO_HEDGE | STOP | DEV | 2323 | 4.958498 | 11518.591341 | 0.747839 | 3060.759196 | 1848.945834 | 9669.645507 | 5608.000000 | 0.000215 |
| COMBO_HEDGE | STOP | DEV_EX2020 | 2079 | 5.268320 | 10952.837543 | 0.780530 | 2325.655545 | 1848.945834 | 9103.891708 | 5020.000000 | 0.000237 |
| COMBO_HEDGE | STOP | HOLD_B | 120 | 4.661509 | 559.381106 | 0.667235 | 732.310116 | -186.277172 | 745.658279 | 260.000000 | 0.000000 |
| COMBO_HEDGE | STOP_1.0 | DEV | 2540 | 3.293631 | 8365.823873 | 0.564435 | 3484.868431 | 1999.537788 | 6366.286085 | 5391.000000 | 0.000178 |
| COMBO_HEDGE | STOP_1.0 | DEV_EX2020 | 2275 | 3.408624 | 7754.619502 | 0.582398 | 3484.868431 | 1999.537788 | 5755.081714 | 4824.000000 | 0.000196 |
| COMBO_HEDGE | STOP_1.0 | HOLD_B | 135 | 2.312241 | 312.152489 | 0.373046 | 1044.860957 | 39.998409 | 272.154080 | 245.000000 | 0.000081 |
| COMBO_HEDGE | STOP_2.0 | DEV | 2244 | 5.302270 | 11898.293167 | 0.765261 | 2676.667874 | 1796.376698 | 10101.916469 | 5687.000000 | 0.000200 |
| COMBO_HEDGE | STOP_2.0 | DEV_EX2020 | 2007 | 5.377298 | 10792.236346 | 0.771040 | 2676.667874 | 1796.376698 | 8995.859648 | 5092.000000 | 0.000220 |
| COMBO_HEDGE | STOP_2.0 | HOLD_B | 118 | 2.426244 | 286.296777 | 0.323063 | 901.926441 | -189.513447 | 475.810224 | 262.000000 | 0.000000 |
| COMBO_HEDGE | STOP_CONS | DEV | 2324 | 4.393475 | 10210.436162 | 0.656955 | 3060.759196 | 518.069219 | 9692.366943 | 5607.000000 | 0.000215 |
| COMBO_HEDGE | STOP_CONS | DEV_EX2020 | 2080 | 4.636867 | 9644.682364 | 0.680555 | 2309.288025 | 518.069219 | 9126.613144 | 5019.000000 | 0.000237 |
| COMBO_HEDGE | STOP_CONS | HOLD_B | 120 | 4.661509 | 559.381106 | 0.667235 | 732.310116 | -186.277172 | 745.658279 | 260.000000 | 0.000000 |
| LS_DEV_BEST\|R-F3\|tail=10\|direction=LS | STOP | DEV | 4406 | 4.824664 | 21257.469372 | 1.049077 | 3157.884363 | 11587.823865 | 9669.645507 | nan | nan |
| LS_DEV_BEST\|R-F3\|tail=10\|direction=LS | STOP | DEV_EX2020 | 3746 | 5.610314 | 21016.237219 | 1.145522 | 3157.884363 | 11912.345511 | 9103.891708 | nan | nan |
| LS_DEV_BEST\|R-F3\|tail=10\|direction=LS | STOP | HOLD_B | 391 | -2.910208 | -1137.891177 | -0.872714 | 2541.501192 | -1883.549456 | 745.658279 | nan | nan |

## combo_BASE_vs_STOP

| cell_id | direction | segment | base_net_mean_bps | stop_net_mean_bps | delta_net_mean_bps | base_max_drawdown_bps | stop_max_drawdown_bps | delta_max_drawdown_bps | base_worst_day_bps | stop_worst_day_bps | delta_worst_day_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMBO_SINGLE | LS | WARMUP | nan | nan | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| COMBO_SINGLE | LS | DEV | 4.654230 | 4.787474 | 0.133244 | 2953.133248 | 3060.759196 | 107.625948 | -933.659745 | -1335.256254 | -401.596509 |
| COMBO_SINGLE | LS | DEV_EX2020 | 4.484850 | 5.079471 | 0.594621 | 2953.133248 | 2325.655545 | -627.477703 | -933.659745 | -1335.256254 | -401.596509 |
| COMBO_SINGLE | LS | HOLD_B | 1.090918 | 4.661509 | 3.570591 | 1111.732363 | 732.310116 | -379.422247 | -325.486871 | -295.149994 | 30.336877 |
| COMBO_HEDGE | LS | WARMUP | nan | nan | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| COMBO_HEDGE | LS | DEV | 5.121130 | 4.958498 | -0.162631 | 2909.974775 | 3060.759196 | 150.784421 | -933.659745 | -1335.256254 | -401.596509 |
| COMBO_HEDGE | LS | DEV_EX2020 | 5.009143 | 5.268320 | 0.259178 | 2909.974775 | 2325.655545 | -584.319230 | -933.659745 | -1335.256254 | -401.596509 |
| COMBO_HEDGE | LS | HOLD_B | 1.090918 | 4.661509 | 3.570591 | 1111.732363 | 732.310116 | -379.422247 | -325.486871 | -295.149994 | 30.336877 |

## combo_STOP_vs_STOP_CONS

| cell_id | direction | segment | stop_net_mean_bps | cons_net_mean_bps | stop_net_total_bps | cons_net_total_bps | stop_ratio | cons_stop_ratio | stop_max_drawdown_bps | cons_max_drawdown_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMBO_SINGLE | LS | WARMUP | nan | nan | 0.000000 | 0.000000 | nan | nan | 0.000000 | 0.000000 |
| COMBO_SINGLE | LS | DEV | 4.787474 | 4.218608 | 11044.702339 | 9736.547160 | 0.181188 | 0.181976 | 3060.759196 | 3060.759196 |
| COMBO_SINGLE | LS | DEV_EX2020 | 5.079471 | 4.443214 | 10478.948540 | 9170.793361 | 0.186621 | 0.187500 | 2325.655545 | 2523.667280 |
| COMBO_SINGLE | LS | HOLD_B | 4.661509 | 4.661509 | 559.381106 | 559.381106 | 0.183333 | 0.183333 | 732.310116 | 732.310116 |
| COMBO_HEDGE | LS | WARMUP | nan | nan | 0.000000 | 0.000000 | nan | nan | 0.000000 | 0.000000 |
| COMBO_HEDGE | LS | DEV | 4.958498 | 4.393475 | 11518.591341 | 10210.436162 | 0.180801 | 0.181583 | 3060.759196 | 3060.759196 |
| COMBO_HEDGE | LS | DEV_EX2020 | 5.268320 | 4.636867 | 10952.837543 | 9644.682364 | 0.186147 | 0.187019 | 2325.655545 | 2309.288025 |
| COMBO_HEDGE | LS | HOLD_B | 4.661509 | 4.661509 | 559.381106 | 559.381106 | 0.183333 | 0.183333 | 732.310116 | 732.310116 |

## multiple_testing

| benchmark | n_cells | rc_stat | rc_p | spa_stat | spa_p | bootstrap_repetitions | bonferroni_cells | min_bonferroni_p_zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| zero | 48 | 10.575855 | 0.011988 | 2.461834 | 0.162837 | 1000 | 48 | 0.331748 |

## cell_count

| primary_cells | base_stop_versions | multiple_testing_cells |
| --- | --- | --- |
| 48 | 96 | 48 |

## hypothesis

| a_dev_and_dev_ex2020_net_positive | b_dev_top5_removed_net_positive | c_dev_long_and_short_net_positive | d_dev_drawdown_less_than_base | pass | hold_b_seen_net_positive | hold_b_seen_net_bps |
| --- | --- | --- | --- | --- | --- | --- |
| True | True | True | False | False | True | 559.381106 |

## BASE_vs_STOP_all

| cell_id | direction | segment | base_net_mean_bps | stop_net_mean_bps | delta_net_mean_bps | base_max_drawdown_bps | stop_max_drawdown_bps | delta_max_drawdown_bps | base_worst_day_bps | stop_worst_day_bps | delta_worst_day_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-F4\|tail=5\|direction=LS | LS | WARMUP | 20.823127 | 23.373828 | 2.550701 | 2389.785270 | 2237.867133 | -151.918137 | -1166.086336 | -1998.668175 | -832.581839 |
| R-F4\|tail=5\|direction=LS | LS | DEV | 4.523233 | 2.464336 | -2.058897 | 6410.894337 | 5539.718986 | -871.175350 | -1631.695730 | -1552.529035 | 79.166695 |
| R-F4\|tail=5\|direction=LS | LS | DEV_EX2020 | 3.736846 | 1.708853 | -2.027993 | 6141.842865 | 5386.195535 | -755.647330 | -1631.695730 | -1552.529035 | 79.166695 |
| R-F4\|tail=5\|direction=LS | LS | HOLD_B | 3.330638 | 4.067123 | 0.736485 | 2368.340075 | 1680.924592 | -687.415483 | -1078.286556 | -340.257486 | 738.029070 |
| R-F4\|tail=5\|direction=L | L | WARMUP | 34.379928 | 45.205728 | 10.825800 | 2023.248355 | 1357.985196 | -665.263159 | -1166.086336 | -1357.985196 | -191.898860 |
| R-F4\|tail=5\|direction=L | L | DEV | 4.446076 | 1.633498 | -2.812578 | 3503.450604 | 3862.578041 | 359.127437 | -1022.503856 | -1454.092571 | -431.588715 |
| R-F4\|tail=5\|direction=L | L | DEV_EX2020 | 4.706417 | 1.761069 | -2.945347 | 3503.450604 | 3862.578041 | 359.127437 | -1022.503856 | -1454.092571 | -431.588715 |
| R-F4\|tail=5\|direction=L | L | HOLD_B | 6.034390 | 0.295017 | -5.739373 | 1475.463508 | 1933.383914 | 457.920407 | -1168.402117 | -571.575951 | 596.826166 |
| R-F4\|tail=5\|direction=S | S | WARMUP | 1.366457 | -16.940954 | -18.307410 | 458.147008 | 1406.428095 | 948.281087 | -191.230988 | -640.682979 | -449.451991 |
| R-F4\|tail=5\|direction=S | S | DEV | 1.819564 | 2.163608 | 0.344044 | 4834.095304 | 4111.682491 | -722.412813 | -1367.274039 | -1173.336066 | 193.937973 |
| R-F4\|tail=5\|direction=S | S | DEV_EX2020 | -0.637583 | 0.164494 | 0.802077 | 4565.043832 | 4111.682491 | -453.361342 | -1367.274039 | -1040.839625 | 326.434414 |
| R-F4\|tail=5\|direction=S | S | HOLD_B | 6.798128 | 8.320489 | 1.522362 | 1399.001425 | 1235.631093 | -163.370331 | -624.956829 | -386.128290 | 238.828539 |
| R-F4\|tail=10\|direction=LS | LS | WARMUP | 30.030646 | 22.826924 | -7.203722 | 1225.985836 | 2148.555615 | 922.569779 | -729.027465 | -2039.884400 | -1310.856935 |
| R-F4\|tail=10\|direction=LS | LS | DEV | 1.725653 | 0.248048 | -1.477605 | 5651.542936 | 8060.059240 | 2408.516303 | -1631.695730 | -1630.577581 | 1.118149 |
| R-F4\|tail=10\|direction=LS | LS | DEV_EX2020 | 1.741250 | 0.366406 | -1.374844 | 5651.542936 | 8060.059240 | 2408.516303 | -1631.695730 | -1630.577581 | 1.118149 |
| R-F4\|tail=10\|direction=LS | LS | HOLD_B | -1.556520 | 1.393182 | 2.949702 | 3591.742054 | 1880.111913 | -1711.630140 | -845.804439 | -430.238128 | 415.566310 |
| R-F4\|tail=10\|direction=L | L | WARMUP | 22.556005 | 32.949525 | 10.393520 | 2344.210038 | 1399.201421 | -945.008617 | -1166.086336 | -1399.201421 | -233.115085 |
| R-F4\|tail=10\|direction=L | L | DEV | 2.651553 | 1.758075 | -0.893477 | 4574.331908 | 5273.720702 | 699.388794 | -1386.822881 | -1532.141118 | -145.318237 |
| R-F4\|tail=10\|direction=L | L | DEV_EX2020 | 2.560741 | 1.515893 | -1.044848 | 4574.331908 | 5273.720702 | 699.388794 | -1386.822881 | -1532.141118 | -145.318237 |
| R-F4\|tail=10\|direction=L | L | HOLD_B | 0.407747 | -3.973688 | -4.381435 | 2133.217960 | 2397.870717 | 264.652758 | -895.145215 | -666.144596 | 229.000619 |
| R-F4\|tail=10\|direction=S | S | WARMUP | 28.012013 | 14.920295 | -13.091718 | 1048.243278 | 1168.145823 | 119.902545 | -376.697204 | -640.682979 | -263.985775 |
| R-F4\|tail=10\|direction=S | S | DEV | -1.740159 | -2.950782 | -1.210623 | 10555.575277 | 13168.007621 | 2612.432345 | -1405.019449 | -1388.797289 | 16.222160 |
| R-F4\|tail=10\|direction=S | S | DEV_EX2020 | -1.972763 | -2.705502 | -0.732740 | 10555.575277 | 13168.007621 | 2612.432345 | -1405.019449 | -1388.797289 | 16.222160 |
| R-F4\|tail=10\|direction=S | S | HOLD_B | 1.729891 | 4.759725 | 3.029833 | 2842.390715 | 2360.129239 | -482.261475 | -700.959398 | -481.918633 | 219.040765 |
| R-F3\|tail=5\|direction=LS | LS | WARMUP | -5.106181 | -3.467624 | 1.638557 | 8419.623520 | 6382.499441 | -2037.124079 | -2640.693268 | -2415.021388 | 225.671880 |
| R-F3\|tail=5\|direction=LS | LS | DEV | 6.247065 | 4.482969 | -1.764095 | 2934.677950 | 2851.473497 | -83.204452 | -1265.875162 | -1492.510194 | -226.635033 |
| R-F3\|tail=5\|direction=LS | LS | DEV_EX2020 | 6.029078 | 4.633395 | -1.395682 | 2934.677950 | 2851.473497 | -83.204452 | -1265.875162 | -1492.510194 | -226.635033 |
| R-F3\|tail=5\|direction=LS | LS | HOLD_B | 1.138961 | 0.032211 | -1.106750 | 1225.770075 | 1120.260280 | -105.509794 | -433.402489 | -396.575754 | 36.826735 |
| R-F3\|tail=5\|direction=L | L | WARMUP | -5.106181 | -3.467624 | 1.638557 | 8419.623520 | 6382.499441 | -2037.124079 | -2640.693268 | -2415.021388 | 225.671880 |
| R-F3\|tail=5\|direction=L | L | DEV | 8.061710 | 5.232498 | -2.829212 | 2327.116528 | 3181.533131 | 854.416603 | -1265.875162 | -1406.200684 | -140.325522 |
| R-F3\|tail=5\|direction=L | L | DEV_EX2020 | 9.713754 | 7.415080 | -2.298674 | 2327.116528 | 2874.903566 | 547.787038 | -1265.875162 | -1406.200684 | -140.325522 |
| R-F3\|tail=5\|direction=L | L | HOLD_B | -5.045368 | -5.179484 | -0.134116 | 1512.604345 | 1373.514490 | -139.089855 | -433.402489 | -396.575754 | 36.826735 |
| R-F3\|tail=5\|direction=S | S | WARMUP | nan | nan | nan | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| R-F3\|tail=5\|direction=S | S | DEV | 4.401410 | 3.717705 | -0.683705 | 2370.463501 | 3529.401231 | 1158.937730 | -1035.508384 | -1492.510194 | -457.001811 |
| R-F3\|tail=5\|direction=S | S | DEV_EX2020 | 2.987075 | 2.397431 | -0.589644 | 2370.463501 | 3529.401231 | 1158.937730 | -1035.508384 | -1492.510194 | -457.001811 |
| R-F3\|tail=5\|direction=S | S | HOLD_B | 25.876275 | 19.931407 | -5.944867 | 746.046397 | 815.158686 | 69.112289 | -411.390636 | -381.090315 | 30.300322 |
| R-F3\|tail=10\|direction=LS | LS | WARMUP | -5.106181 | -3.467624 | 1.638557 | 8419.623520 | 6382.499441 | -2037.124079 | -2640.693268 | -2415.021388 | 225.671880 |

## k45_single_book_combo_r2_24_20261004

- 테스트 재실행 `tests/test_k45_single_book_combo_r2_24.py`: `6 passed in 1.92s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-24 |
| status | COMPLETE |
| started_utc | 2026-10-04T12:25:10.139540+00:00 |
| finished_utc | 2026-10-04T12:30:08.639095+00:00 |
| elapsed_seconds | 298.4945829999633 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| frozen_manifest_sha256 | 39580fb4c8c63f083ad402b2c6ecb7ee5c345329cdfa4d9680e0fddc4ee04386 |
| priority | [{"rank": 1, "candidate": "F3_global_ls_account/1h/w30/q20/h12/LS", "dev_common_pess_pw_ci95_lower_daily_bps": 7.587250003948462}, {"rank": 2, "candidate": "F3/1h/10/24/signal/LS", "dev_common_pess_pw_ci95_lower_daily_bps": 7.5576768263355465}, {"rank": 3, "candidate": "4h_h480/SIDE/ROLLING_180D/q02/g1", "dev_common_pess_pw_ci95_lower_daily_bps": 0.6769252982442766}, {"rank": 4, "candidate": "SIDE/ROLLING_180D/q=0.01/L=120/S=60/V0", "dev_common_pess_pw_ci95_lower_daily_bps": 0.40232179342804164}, {"rank": 5, "candidate": "E1/1h/3/signal/L+R2-15/catboost/base", "dev_common_pess_pw_ci95_lower_da |
| combinations | {"C1": ["F3/1h/10/24/signal/LS", "E1/1h/3/signal/L"], "C2": ["F3/1h/10/24/signal/LS", "E1/1h/2/signal/L"], "C3": ["F3/1h/10/24/signal/LS", "E1/1h/3/signal/L", "SIDE/ROLLING_180D/q=0.01/L=120/S=60/V0", "4h_h480/SIDE/ROLLING_180D/q02/g1"], "C4": ["F3_global_ls_account/1h/w30/q20/h12/LS", "E1/1h/3/signal/L"], "C5": ["F3/1h/10/24/signal/LS", "E1/1h/3/signal/L+R2-15/catboost/base"], "C6": ["F3/1h/10/24/signal/LS", "E1/1h/3/signal/L", "A3/4h/720/signal/LS"]} |
| collision_rules | ["FIRST", "PRIORITY", "SWITCH"] |
| segments | {"DEV_COMMON": ["2021-03-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"], "HOLD_B": ["2026-01-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00"]} |
| funding_boundaries | ["PESS", "OPT"] |
| cost_bps | [0.0, 4.0, 8.0, 12.0] |
| hypothesis | C1 FIRST DEV_COMMON: F3/1h/10/24/signal/LS보다 mtm_daily_sharpe 증가 및 mtm_max_drawdown_bps 감소 |
| hypothesis_result_code | 1 |
| hold_b_used_for_decision | False |
| trial_counts | [813, 5007] |
| combo_cell_count | 36 |
| random_repetitions | 1000 |
| workers_max | 12 |
| live_orders | 0 |
| downloads | 0 |
| retraining | 0 |
| hold_a_read | 0 |
| post_cutoff_read | 0 |
| standalone_reproduction_matches | 36 |
| standalone_reproduction_rows | 36 |
| max_concurrent | 1 |
| opposite_overlap | False |

- 출력 해시 확인: 15/15 일치

### REPORT.md 앞 150줄 (전체 2255줄, 원문)

# R2-24

## standalone_reproduction

| candidate | boundary | segment | source_n | source_net_bps | source_sharpe | source_drawdown_bps | engine_n | engine_net_bps | engine_sharpe | engine_drawdown_bps | sharpe_difference | drawdown_difference_bps | n_difference | net_difference_bps | match | cause_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F3\|1h\|10/24\|signal\|LS | PESS | DEV_COMMON | 717 | 30361.807133 | 1.547682 | 3715.524393 | 717 | 30361.807133 | 1.547682 | 3715.524393 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3\|1h\|10/24\|signal\|LS | PESS | HOLD_B | 76 | 1176.121494 | 0.760563 | 1807.016446 | 76 | 1176.121494 | 0.760563 | 1807.016446 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3\|1h\|10/24\|signal\|LS | OPT | DEV_COMMON | 717 | 30663.775233 | 1.562873 | 3712.388993 | 717 | 30663.775233 | 1.562873 | 3712.388993 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3\|1h\|10/24\|signal\|LS | OPT | HOLD_B | 76 | 1187.491794 | 0.767917 | 1802.956446 | 76 | 1187.491794 | 0.767917 | 1802.956446 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | PESS | DEV_COMMON | 322 | 8614.395584 | 0.833185 | 3968.542221 | 322 | 8614.395584 | 0.833185 | 3968.542221 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | PESS | HOLD_B | 30 | 1445.512546 | 2.073947 | 664.465959 | 30 | 1445.512546 | 2.073947 | 664.465959 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | OPT | DEV_COMMON | 322 | 8683.247284 | 0.839507 | 3957.166621 | 322 | 8683.247284 | 0.839507 | 3957.166621 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L | OPT | HOLD_B | 30 | 1447.276546 | 2.076488 | 664.267359 | 30 | 1447.276546 | 2.076488 | 664.267359 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | PESS | DEV_COMMON | 509 | 9290.913223 | 0.725365 | 5523.751138 | 509 | 9290.913223 | 0.725365 | 5523.751138 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | PESS | HOLD_B | 49 | 1915.549648 | 2.310954 | 846.554635 | 49 | 1915.549648 | 2.310954 | 846.554635 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | OPT | DEV_COMMON | 509 | 9397.395023 | 0.733474 | 5512.113038 | 509 | 9397.395023 | 0.733474 | 5512.113038 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|2\|signal\|L | OPT | HOLD_B | 49 | 1918.134848 | 2.314068 | 845.724035 | 49 | 1918.134848 | 2.314068 | 845.724035 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | PESS | DEV_COMMON | 292 | 4913.723836 | 1.029018 | 1656.977506 | 292 | 4913.723836 | 1.029018 | 1656.977506 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | PESS | HOLD_B | 32 | 1414.909623 | 1.397614 | 709.290277 | 32 | 1414.909623 | 1.397614 | 709.290277 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | OPT | DEV_COMMON | 292 | 4932.486936 | 1.033098 | 1656.803206 | 292 | 4932.486936 | 1.033098 | 1656.803206 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | OPT | HOLD_B | 32 | 1416.928923 | 1.399703 | 707.987477 | 32 | 1416.928923 | 1.399703 | 707.987477 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | PESS | DEV_COMMON | 80 | 5075.087862 | 1.200347 | 1217.915851 | 80 | 5075.087862 | 1.200347 | 1217.915851 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | PESS | HOLD_B | 12 | -418.659043 | -0.787445 | 1245.498552 | 12 | -418.659043 | -0.787445 | 1245.498552 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | OPT | DEV_COMMON | 80 | 5185.316162 | 1.228156 | 1217.618708 | 80 | 5185.316162 | 1.228156 | 1217.618708 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | OPT | HOLD_B | 12 | -416.041043 | -0.783067 | 1243.997452 | 12 | -416.041043 | -0.783067 | 1243.997452 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | PESS | DEV_COMMON | 1900 | 31928.282665 | 1.518511 | 4612.152574 | 1900 | 31928.282665 | 1.518511 | 4612.152574 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | PESS | HOLD_B | 217 | 3969.572652 | 2.097912 | 1753.337632 | 217 | 3969.572652 | 2.097912 | 1753.337632 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | OPT | DEV_COMMON | 1900 | 32453.286365 | 1.542493 | 4558.378974 | 1900 | 32453.286365 | 1.542493 | 4558.378974 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | OPT | HOLD_B | 217 | 3990.645652 | 2.109438 | 1753.337632 | 217 | 3990.645652 | 2.109438 | 1753.337632 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | PESS | DEV_COMMON | 151 | 6773.381230 | 0.902489 | 2310.869893 | 151 | 6773.381230 | 0.902489 | 2310.869893 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | PESS | HOLD_B | 10 | 39.868088 | 0.115376 | 758.774304 | 10 | 39.868088 | 0.115376 | 758.774304 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | OPT | DEV_COMMON | 149 | 8835.751902 | 1.167468 | 2195.554762 | 149 | 8835.751902 | 1.167468 | 2195.554762 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| E1\|1h\|3\|signal\|L+R2-15\|catboost\|base | OPT | HOLD_B | 10 | 385.191454 | 0.870595 | 664.267359 | 10 | 385.191454 | 0.870595 | 664.267359 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| A3\|4h\|720\|signal\|LS | PESS | DEV_COMMON | 321 | 20642.717839 | 0.754822 | 7796.206063 | 321 | 20642.717839 | 0.754822 | 7796.206063 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| A3\|4h\|720\|signal\|LS | PESS | HOLD_B | 46 | 3084.219768 | 1.246582 | 2865.429872 | 46 | 3084.219768 | 1.246582 | 2865.429872 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| A3\|4h\|720\|signal\|LS | OPT | DEV_COMMON | 321 | 20925.429839 | 0.765227 | 7752.552863 | 321 | 20925.429839 | 0.765227 | 7752.552863 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| A3\|4h\|720\|signal\|LS | OPT | HOLD_B | 46 | 3100.863768 | 1.253537 | 2858.866672 | 46 | 3100.863768 | 1.253537 | 2858.866672 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| BUY_HOLD | PESS | DEV_COMMON | 1 | 1969.029422 | 0.071823 | 15849.542995 | 1 | 1969.029422 | 0.071823 | 15849.542995 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| BUY_HOLD | PESS | HOLD_B | 1 | -4078.369884 | -1.667515 | 5226.876599 | 1 | -4078.369884 | -1.667515 | 5226.876599 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| BUY_HOLD | OPT | DEV_COMMON | 1 | 1969.029422 | 0.071823 | 15849.542995 | 1 | 1969.029422 | 0.071823 | 15849.542995 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |
| BUY_HOLD | OPT | HOLD_B | 1 | -4078.369884 | -1.667515 | 5226.876599 | 1 | -4078.369884 | -1.667515 | 5226.876599 | 0.000000 | 0.000000 | 0 | 0.000000 | 1 | MATCH |

## combo_summary_DEV_COMMON_PESS

| combo | rule | n | switch_n | switch_cost_bps | net_total_bps | net_per_trade_bps | exposure_ratio | mtm_daily_sharpe | mtm_max_drawdown_bps | worst_day_bps | longest_no_profit_days | pw_block | pw_ci95_lower_daily_bps | pw_ci95_upper_daily_bps | dsr_813 | dsr_5007 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | FIRST | 859 | 0 | 0.000000 | 35717.683175 | 41.580539 | 0.468473 | 1.727874 | 3673.828761 | -1012.646877 | 255 | 1.184650 | 9.986611 | 30.895780 | 0.089969 | 0.014866 |
| C1 | PRIORITY | 859 | 0 | 0.000000 | 35717.683175 | 41.580539 | 0.468473 | 1.727874 | 3673.828761 | -1012.646877 | 255 | 1.184650 | 9.986611 | 30.895780 | 0.089969 | 0.014866 |
| C1 | SWITCH | 898 | 41 | 164.000000 | 34884.929840 | 38.847361 | 0.478188 | 1.667187 | 3740.060118 | -1012.646877 | 255 | 1.230192 | 9.277608 | 30.403984 | 0.069668 | 0.010502 |
| C2 | FIRST | 957 | 0 | 0.000000 | 31678.222461 | 33.101591 | 0.511012 | 1.489365 | 5222.584895 | -1012.646877 | 252 | 1.027645 | 7.369424 | 29.084052 | 0.030191 | 0.003465 |
| C2 | PRIORITY | 957 | 0 | 0.000000 | 31678.222461 | 33.101591 | 0.511012 | 1.489365 | 5222.584895 | -1012.646877 | 252 | 1.027645 | 7.369424 | 29.084052 | 0.030191 | 0.003465 |
| C2 | SWITCH | 1020 | 68 | 272.000000 | 29836.101181 | 29.251080 | 0.526976 | 1.369138 | 5288.816252 | -1012.646877 | 252 | 1.000000 | 6.088969 | 28.019655 | 0.016187 | 0.001562 |
| C3 | FIRST | 1008 | 0 | 0.000000 | 38418.164214 | 38.113258 | 0.470477 | 1.815886 | 3878.594398 | -1012.646877 | 261 | 1.638317 | 11.529307 | 32.324652 | 0.126726 | 0.023815 |
| C3 | PRIORITY | 1008 | 0 | 0.000000 | 38418.164214 | 38.113258 | 0.470477 | 1.815886 | 3878.594398 | -1012.646877 | 261 | 1.638317 | 11.529307 | 32.324652 | 0.126726 | 0.023815 |
| C3 | SWITCH | 1075 | 67 | 268.000000 | 38440.428478 | 35.758538 | 0.479821 | 1.798915 | 4010.162631 | -1012.646877 | 296 | 1.576965 | 11.229615 | 32.702077 | 0.118843 | 0.021773 |
| C4 | FIRST | 1959 | 0 | 0.000000 | 36779.201566 | 18.774478 | 0.580739 | 1.702868 | 3138.584832 | -1057.109700 | 296 | 1.535537 | 10.131695 | 31.215768 | 0.084403 | 0.014095 |
| C4 | PRIORITY | 1959 | 0 | 0.000000 | 36779.201566 | 18.774478 | 0.580739 | 1.702868 | 3138.584832 | -1057.109700 | 296 | 1.535537 | 10.131695 | 31.215768 | 0.084403 | 0.014095 |
| C4 | SWITCH | 2051 | 62 | 248.000000 | 36385.352650 | 17.740299 | 0.586705 | 1.664804 | 4353.781515 | -1214.261062 | 400 | 1.867443 | 9.492573 | 31.381855 | 0.072627 | 0.011578 |
| C5 | FIRST | 783 | 0 | 0.000000 | 35175.580600 | 44.924113 | 0.434706 | 1.751114 | 3656.323441 | -1012.646877 | 254 | 1.144863 | 10.013713 | 30.194574 | 0.097700 | 0.016463 |
| C5 | PRIORITY | 783 | 0 | 0.000000 | 35175.580600 | 44.924113 | 0.434706 | 1.751114 | 3656.323441 | -1012.646877 | 254 | 1.144863 | 10.013713 | 30.194574 | 0.097700 | 0.016463 |
| C5 | SWITCH | 804 | 21 | 84.000000 | 34588.410356 | 43.020411 | 0.439516 | 1.709328 | 3656.323441 | -1012.646877 | 252 | 1.104870 | 9.912341 | 30.064484 | 0.082345 | 0.013036 |
| C6 | FIRST | 384 | 0 | 0.000000 | 22351.805050 | 58.207826 | 0.943124 | 0.833943 | 5737.802876 | -1180.209350 | 387 | 2.581084 | 0.428094 | 25.461199 | 0.000587 | 0.000028 |
| C6 | PRIORITY | 384 | 0 | 0.000000 | 22351.805050 | 58.207826 | 0.943124 | 0.833943 | 5737.802876 | -1180.209350 | 387 | 2.581084 | 0.428094 | 25.461199 | 0.000587 | 0.000028 |
| C6 | SWITCH | 1070 | 111 | 444.000000 | 38273.417379 | 35.769549 | 0.571897 | 1.691351 | 3436.804224 | -1034.092666 | 261 | 1.974907 | 10.548077 | 32.467735 | 0.077862 | 0.012286 |

## combo_summary_DEV_COMMON_OPT

| combo | rule | n | switch_n | switch_cost_bps | net_total_bps | net_per_trade_bps | exposure_ratio | mtm_daily_sharpe | mtm_max_drawdown_bps | worst_day_bps | longest_no_profit_days | pw_block | pw_ci95_lower_daily_bps | pw_ci95_upper_daily_bps | dsr_813 | dsr_5007 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | FIRST | 859 | 0 | 0.000000 | 36043.534275 | 41.959877 | 0.468473 | 1.743456 | 3672.828761 | -1012.646877 | 255 | 1.190981 | 10.336310 | 31.236674 | 0.095944 | 0.016251 |
| C1 | PRIORITY | 859 | 0 | 0.000000 | 36043.534275 | 41.959877 | 0.468473 | 1.743456 | 3672.828761 | -1012.646877 | 255 | 1.190981 | 10.336310 | 31.236674 | 0.095944 | 0.016251 |
| C1 | SWITCH | 898 | 41 | 164.000000 | 35233.385140 | 39.235395 | 0.478188 | 1.683603 | 3739.060118 | -1012.646877 | 255 | 1.240071 | 9.558530 | 30.696045 | 0.074846 | 0.011581 |
| C2 | FIRST | 957 | 0 | 0.000000 | 32017.848961 | 33.456477 | 0.511012 | 1.505199 | 5219.571395 | -1012.646877 | 252 | 1.019187 | 7.486548 | 29.149709 | 0.032721 | 0.003851 |
| C2 | PRIORITY | 957 | 0 | 0.000000 | 32017.848961 | 33.456477 | 0.511012 | 1.505199 | 5219.571395 | -1012.646877 | 252 | 1.019187 | 7.486548 | 29.149709 | 0.032721 | 0.003851 |
| C2 | SWITCH | 1020 | 68 | 272.000000 | 30206.980581 | 29.614687 | 0.526976 | 1.385961 | 5285.802752 | -1012.646877 | 252 | 1.000000 | 6.297431 | 28.245471 | 0.017772 | 0.001761 |
| C3 | FIRST | 1008 | 0 | 0.000000 | 38811.289114 | 38.503263 | 0.470477 | 1.834245 | 3851.047498 | -1012.646877 | 256 | 1.647251 | 11.772280 | 32.525493 | 0.135831 | 0.026283 |
| C3 | PRIORITY | 1008 | 0 | 0.000000 | 38811.289114 | 38.503263 | 0.470477 | 1.834245 | 3851.047498 | -1012.646877 | 256 | 1.647251 | 11.772280 | 32.525493 | 0.135831 | 0.026283 |
| C3 | SWITCH | 1075 | 67 | 268.000000 | 38850.222678 | 36.139742 | 0.479821 | 1.817755 | 3982.615731 | -1012.646877 | 296 | 1.588049 | 11.370102 | 33.146322 | 0.127776 | 0.024124 |
| C4 | FIRST | 1959 | 0 | 0.000000 | 37312.935966 | 19.046930 | 0.580739 | 1.726613 | 3134.017632 | -1057.109700 | 296 | 1.564835 | 10.399176 | 31.874024 | 0.093054 | 0.016120 |
| C4 | PRIORITY | 1959 | 0 | 0.000000 | 37312.935966 | 19.046930 | 0.580739 | 1.726613 | 3134.017632 | -1057.109700 | 296 | 1.564835 | 10.399176 | 31.874024 | 0.093054 | 0.016120 |
| C4 | SWITCH | 2051 | 62 | 248.000000 | 36954.432250 | 18.017763 | 0.586705 | 1.689811 | 4291.982315 | -1213.237662 | 400 | 1.892882 | 9.764433 | 31.515413 | 0.080753 | 0.013380 |
| C5 | FIRST | 780 | 0 | 0.000000 | 36781.010070 | 47.155141 | 0.433480 | 1.828574 | 3712.388993 | -1012.646877 | 255 | 1.218399 | 10.907583 | 31.216823 | 0.132571 | 0.025305 |
| C5 | PRIORITY | 780 | 0 | 0.000000 | 36781.010070 | 47.155141 | 0.433480 | 1.828574 | 3712.388993 | -1012.646877 | 255 | 1.218399 | 10.907583 | 31.216823 | 0.132571 | 0.025305 |
| C5 | SWITCH | 800 | 20 | 80.000000 | 35897.799108 | 44.872249 | 0.438337 | 1.771077 | 3712.388993 | -1012.646877 | 255 | 1.191445 | 10.212644 | 30.938350 | 0.106336 | 0.018597 |
| C6 | FIRST | 384 | 0 | 0.000000 | 22656.545850 | 59.001421 | 0.943124 | 0.845352 | 5720.570076 | -1180.209350 | 387 | 2.601657 | 0.318777 | 25.703149 | 0.000640 | 0.000031 |
| C6 | PRIORITY | 384 | 0 | 0.000000 | 22656.545850 | 59.001421 | 0.943124 | 0.845352 | 5720.570076 | -1180.209350 | 387 | 2.601657 | 0.318777 | 25.703149 | 0.000640 | 0.000031 |
| C6 | SWITCH | 1070 | 111 | 444.000000 | 38717.826179 | 36.184884 | 0.571897 | 1.710771 | 3408.694624 | -1034.092666 | 256 | 1.977680 | 10.899262 | 32.716424 | 0.084559 | 0.013760 |

## blocking_loss_DEV_COMMON

| combo | rule | boundary | segment | candidate | accepted_contribution_bps | standalone_net_bps | blocked_loss_bps | dropped_standalone_net_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | FIRST | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 31029.590520 | 30361.807133 | -667.783387 | -667.783387 |
| C1 | FIRST | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 4688.092654 | 8614.395584 | 3926.302930 | 3926.302930 |
| C1 | FIRST | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 31314.528020 | 30663.775233 | -650.752787 | -650.752787 |
| C1 | FIRST | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 4729.006254 | 8683.247284 | 3954.241030 | 3954.241030 |
| C1 | PRIORITY | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 31029.590520 | 30361.807133 | -667.783387 | -667.783387 |
| C1 | PRIORITY | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 4688.092654 | 8614.395584 | 3926.302930 | 3926.302930 |
| C1 | PRIORITY | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 31314.528020 | 30663.775233 | -650.752787 | -650.752787 |
| C1 | PRIORITY | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 4729.006254 | 8683.247284 | 3954.241030 | 3954.241030 |
| C1 | SWITCH | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30361.807133 | 30361.807133 | -0.000000 | 0.000000 |
| C1 | SWITCH | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 4523.122706 | 8614.395584 | 4091.272878 | 3241.442566 |
| C1 | SWITCH | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30663.775233 | 30663.775233 | -0.000000 | 0.000000 |
| C1 | SWITCH | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 4569.609906 | 8683.247284 | 4113.637378 | 3270.703266 |
| C2 | FIRST | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30654.707158 | 30361.807133 | -292.900024 | -292.900024 |
| C2 | FIRST | PESS | DEV_COMMON | E1\|1h\|2\|signal\|L | 1023.515303 | 9290.913223 | 8267.397920 | 8267.397920 |
| C2 | FIRST | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30928.240558 | 30663.775233 | -264.465324 | -264.465324 |
| C2 | FIRST | OPT | DEV_COMMON | E1\|1h\|2\|signal\|L | 1089.608403 | 9397.395023 | 8307.786620 | 8307.786620 |
| C2 | PRIORITY | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30654.707158 | 30361.807133 | -292.900024 | -292.900024 |
| C2 | PRIORITY | PESS | DEV_COMMON | E1\|1h\|2\|signal\|L | 1023.515303 | 9290.913223 | 8267.397920 | 8267.397920 |
| C2 | PRIORITY | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30928.240558 | 30663.775233 | -264.465324 | -264.465324 |
| C2 | PRIORITY | OPT | DEV_COMMON | E1\|1h\|2\|signal\|L | 1089.608403 | 9397.395023 | 8307.786620 | 8307.786620 |
| C2 | SWITCH | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30361.807133 | 30361.807133 | -0.000000 | 0.000000 |
| C2 | SWITCH | PESS | DEV_COMMON | E1\|1h\|2\|signal\|L | -525.705952 | 9290.913223 | 9816.619175 | 6176.642010 |
| C2 | SWITCH | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30663.775233 | 30663.775233 | -0.000000 | 0.000000 |
| C2 | SWITCH | OPT | DEV_COMMON | E1\|1h\|2\|signal\|L | -456.794652 | 9397.395023 | 9854.189675 | 6221.064410 |
| C3 | FIRST | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 29719.896830 | 30361.807133 | 641.910303 | 641.910303 |
| C3 | FIRST | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 4249.732774 | 8614.395584 | 4364.662810 | 4364.662810 |
| C3 | FIRST | PESS | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 2435.294651 | 4913.723836 | 2478.429184 | 2478.429184 |
| C3 | FIRST | PESS | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2013.239959 | 5075.087862 | 3061.847902 | 3061.847902 |
| C3 | FIRST | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30007.283030 | 30663.775233 | 656.492203 | 656.492203 |
| C3 | FIRST | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 4277.935274 | 8683.247284 | 4405.312010 | 4405.312010 |
| C3 | FIRST | OPT | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 2444.918251 | 4932.486936 | 2487.568684 | 2487.568684 |
| C3 | FIRST | OPT | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2081.152559 | 5185.316162 | 3104.163602 | 3104.163602 |
| C3 | PRIORITY | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 29719.896830 | 30361.807133 | 641.910303 | 641.910303 |
| C3 | PRIORITY | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 4249.732774 | 8614.395584 | 4364.662810 | 4364.662810 |
| C3 | PRIORITY | PESS | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 2435.294651 | 4913.723836 | 2478.429184 | 2478.429184 |
| C3 | PRIORITY | PESS | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2013.239959 | 5075.087862 | 3061.847902 | 3061.847902 |
| C3 | PRIORITY | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30007.283030 | 30663.775233 | 656.492203 | 656.492203 |
| C3 | PRIORITY | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 4277.935274 | 8683.247284 | 4405.312010 | 4405.312010 |
| C3 | PRIORITY | OPT | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 2444.918251 | 4932.486936 | 2487.568684 | 2487.568684 |
| C3 | PRIORITY | OPT | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2081.152559 | 5185.316162 | 3104.163602 | 3104.163602 |
| C3 | SWITCH | PESS | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30361.807133 | 30361.807133 | -0.000000 | 0.000000 |
| C3 | SWITCH | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 3746.537866 | 8614.395584 | 4867.857718 | 4160.729426 |
| C3 | SWITCH | PESS | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 1581.334783 | 4913.723836 | 3332.389052 | 3125.220709 |
| C3 | SWITCH | PESS | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2750.748696 | 5075.087862 | 2324.339166 | 2876.431974 |
| C3 | SWITCH | OPT | DEV_COMMON | F3\|1h\|10/24\|signal\|LS | 30663.775233 | 30663.775233 | -0.000000 | 0.000000 |
| C3 | SWITCH | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 3778.690066 | 8683.247284 | 4904.557218 | 4202.701226 |
| C3 | SWITCH | OPT | DEV_COMMON | SIDE\|ROLLING_180D\|q=0.01\|L=120\|S=60\|V0 | 1590.667883 | 4932.486936 | 3341.819052 | 3135.194709 |
| C3 | SWITCH | OPT | DEV_COMMON | 4h_h480\|SIDE\|ROLLING_180D\|q02\|g1 | 2817.089496 | 5185.316162 | 2368.226666 | 2915.581374 |
| C4 | FIRST | PESS | DEV_COMMON | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 30056.580183 | 31928.282665 | 1871.702482 | 1871.702482 |
| C4 | FIRST | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 6722.621383 | 8614.395584 | 1891.774201 | 1891.774201 |
| C4 | FIRST | OPT | DEV_COMMON | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 30548.586783 | 32453.286365 | 1904.699582 | 1904.699582 |
| C4 | FIRST | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 6764.349183 | 8683.247284 | 1918.898101 | 1918.898101 |
| C4 | PRIORITY | PESS | DEV_COMMON | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 30056.580183 | 31928.282665 | 1871.702482 | 1871.702482 |
| C4 | PRIORITY | PESS | DEV_COMMON | E1\|1h\|3\|signal\|L | 6722.621383 | 8614.395584 | 1891.774201 | 1891.774201 |
| C4 | PRIORITY | OPT | DEV_COMMON | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 30548.586783 | 32453.286365 | 1904.699582 | 1904.699582 |
| C4 | PRIORITY | OPT | DEV_COMMON | E1\|1h\|3\|signal\|L | 6764.349183 | 8683.247284 | 1918.898101 | 1918.898101 |
| C4 | SWITCH | PESS | DEV_COMMON | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS | 31928.282665 | 31928.282665 | -0.000000 | 0.000000 |

## k45_train_window_r2_16_20261002

- 테스트 재실행 `tests/test_k45_train_window_r2_16.py`: `5 passed in 1.91s`
### manifest 필드

| 필드 | 값 |
|---|---|
| run_started_utc | 2026-10-02T17:23:58.092200+00:00 |
| run_finished_utc | 2026-10-03T06:22:28.276185+00:00 |
| runtime_seconds | 46710.183985 |
| data_cutoff_utc | 2026-06-30T23:59:00+00:00 |
| frozen_hypothesis | 짧은 창(30·90일) 또는 시간가중이 누적보다 DEV·HOLD_B 모두에서 Spearman이 높고, 3시드 부호가 일치하는 양 구간 양수 칸이 더 많다. |
| segments | {"DEV": "pilot_fold <= 605", "HOLD_B": "pilot_fold >= 606; exploratory"} |
| windows | {"30d": 30, "90d": 90, "180d": 180, "365d": 365, "expanding": null, "weighted_90d": null} |
| seeds | [20261001, 20261002, 20261003] |
| min_train_rows | 500 |
| model_params | {"depth": 4, "learning_rate": 0.05, "iterations": 500, "l2_leaf_reg": 3} |
| execution | {"initial_process_workers": 16, "initial_model_threads": 1, "resume_process_workers": 2, "resume_model_threads": 8, "thread_1_vs_8_prediction_exact": true, "cpu_worker_upper_bound": 16} |
| weighted_half_life_days | 90 |
| cost_bps | 4.0 |
| single_position_first | True |
| local_data_only | True |
| downloads | 0 |
| patchtst_refits | 0 |
| live_orders | 0 |
| hold_b_exploratory | True |
| result_filtering | False |

### out_of_sample_result (원문)

```text
{
 "hypothesis_supported": false,
 "supporting_window_count": 0,
 "supporting_windows": []
}
```

- 출력 해시 확인: 220/220 일치

### REPORT.md 앞 41줄 (전체 41줄, 원문)

# R2-16

## 0

| cutoff | seed_n | window_n | cost_bps | live | hold_b_exploratory | parity_exact | parity_total |
|---|---|---|---|---|---|---|---|
| 2026-06-30T23:59:00+00:00 | 3 | 6 | 4.00000000 | 0 | 1 | 11 | 11 |

## 1

| window | spearman_mean | spearman_DEV_mean | spearman_HOLD_B_mean | B_C_cell_seed_both_positive | B_C_cells | all_3seed_both_positive_cells | same_sign_both_segments_cells |
|---|---|---|---|---|---|---|---|
| 30d | 0.00118865 | 0.01392753 | -0.01155022 | 0 | 58 | 0 | 23 |
| 90d | 0.00617791 | 0.02079251 | -0.00843668 | 15 | 58 | 0 | 24 |
| 180d | 0.01168116 | 0.03510040 | -0.01173807 | 15 | 58 | 2 | 33 |
| 365d | 0.00896711 | 0.04066823 | -0.02273401 | 14 | 58 | 1 | 31 |
| expanding | 0.03491571 | 0.04558629 | 0.02424514 | 42 | 58 | 8 | 31 |
| weighted_90d | 0.01406128 | 0.04122119 | -0.01309863 | 9 | 58 | 0 | 22 |

## 2

| window | family | cells | all_3seed_both_positive_cells | same_sign_both_segments_cells |
|---|---|---|---|---|
| 180d | B | 40 | 2 | 27 |
| 180d | C | 18 | 0 | 6 |
| 30d | B | 40 | 0 | 23 |
| 30d | C | 18 | 0 | 0 |
| 365d | B | 40 | 1 | 25 |
| 365d | C | 18 | 0 | 6 |
| 90d | B | 40 | 0 | 22 |
| 90d | C | 18 | 0 | 2 |
| expanding | B | 40 | 3 | 22 |
| expanding | C | 18 | 5 | 9 |
| weighted_90d | B | 40 | 0 | 18 |
| weighted_90d | C | 18 | 0 | 4 |
| 180d | TOTAL | 58 | 2 | 33 |
| 30d | TOTAL | 58 | 0 | 23 |
| 365d | TOTAL | 58 | 1 | 31 |
| 90d | TOTAL | 58 | 0 | 24 |
| expanding | TOTAL | 58 | 8 | 31 |
| weighted_90d | TOTAL | 58 | 0 | 22 |

## k45_trend_side_20261001

- 테스트 재실행 `tests/test_k45_trend_side.py`: `23 passed in 1.39s`
### manifest 필드

| 필드 | 값 |
|---|---|
| hypothesis | 느린 추세 방향으로만 fade하면, 두 팔 모두 net이 0보다 크다. |
| run_utc | 2026-10-01T00:19:19.769259+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00Z |
| new_model_fits | 0 |
| live_orders | 0 |

- 출력 해시: manifest에 outputs 해시 항목 없음.

### REPORT.md 앞 37줄 (전체 37줄, 원문)

# Stage 1: trend-conditioned side — result

Run 2026-10-01. Inputs: `causal_candidates.parquet` (frozen), `artifacts/btcusdt_2020_2026h1.parquet` (cutoff 2026-06-30). New model fits 0. Frozen hypothesis: "느린 추세 방향으로만 fade하면, 두 팔 모두 net이 0보다 크다."

## Verdict

**DEV gate: FAIL** (frozen criteria; not lowered). HOLD-B: FAIL (exploratory).

| segment | n book | net mean | trim top-2 | PW 95% CI | p | monthly + share |
|---|---|---|---|---|---|---|
| DEV 30d | 2,794 | −0.682 | −1.295 | [−4.191, 2.985] | 0.645 | 0.52 |
| HOLD-B 30d | 242 | −7.819 | −10.227 | [−18.518, 4.173] | 0.910 | 0.17 |
| DEV 7d (report) | 2,805 | −4.928 | −5.385 | [−8.491, −1.268] | 0.996 | 0.40 |

Reference: long-only book +0.455, shared book −0.521.

## Arm × trend, all candidates (net bps)

| arm | trend | DEV n | DEV net | HOLD-B n | HOLD-B net |
|---|---|---|---|---|---|
| LONG | up | 2,072 | **+3.19** | 95 | +10.44 |
| LONG | down | 2,246 | +0.44 | 279 | +1.66 |
| SHORT | down | 2,082 | −1.47 | 242 | −12.74 |
| SHORT | up | 2,001 | −6.26 | 96 | +5.89 |

Random 45-min trade in the trend direction (DEV): up-trend long −3.34, down-trend short −3.90.

## Reading

- The trend split moves both arms in the predicted direction on DEV: long +2.75, short +4.79.
- The short arm stays below cost even in down-trends (gross +2.53 against 4 bps). The short loses the book.
- HOLD-B reverses the short ordering (short in up-trend +5.89, in down-trend −12.74). The short-side trend effect is unstable.
- Long in up-trend is the only cell above cost on both segments. It is a post-hoc cell, not the frozen rule. Any test of it is a new hypothesis and exploratory.

## Next per plan

DEV failed for the frozen rule, so stage 2 (TP) does not run. Next candidate: 3-class target (spec §9).

## k45_trend_side_tp_20261001

- 테스트 재실행 `tests/test_k45_trend_side.py`: `23 passed in 1.39s`
### manifest 필드

| 필드 | 값 |
|---|---|
| label | EXPLORATORY_AFTER_DEV_FAIL |
| data_source | Binance USD-M BTCUSDT futures; frozen local parquet only |
| run_utc | 2026-10-01T01:04:21.178918+00:00 |
| data_cutoff_utc | 2026-06-30T23:59:00Z |
| hypothesis | 고정 TP가 30일 추세 방향 두 팔의 거래당 net을 높인다. |
| segment_results | {"DEV": {"tested_tp_bps": [50.0, 100.0, 150.0], "book_results": {"50.0": {"net": -0.8335272510354486, "p": 0.7212139393030349}, "100.0": {"net": 0.19857044448930186, "p": 0.45807709614519276}, "150.0": {"net": 0.7255919973417979, "p": 0.3513324333783311}}}, "HOLD_B": {"tested_tp_bps": [], "gate": null, "book_results": {}}} |
| new_model_fits | 0 |
| live_orders | 0 |

- 출력 해시 확인: 4/4 일치

### REPORT.md 앞 38줄 (전체 38줄, 원문)

# Stage 2: trend-conditioned side TP — exploratory result

Label: `EXPLORATORY_AFTER_DEV_FAIL`. Stage 1 DEV failed; this run proceeds only by explicit user decision.

DEV selection: None; Bonferroni alpha = 0.01666667.
HOLD-B gate: NOT_RUN_NO_DEV_SELECTION.

Book occupancy remains fixed through `entry + 45` regardless of an earlier TP fill. TP never creates a new admission opportunity.

## Net grid

| segment | TP bps | arm | n | net mean bps | one-sided p |
|---|---:|---|---:|---:|---:|
| DEV | 50 | BOOK | 2794 | -0.833527 | 0.721214 |
| DEV | 50 | DOWN_BREAKOUT_LONG | 1392 | 0.325617 | 0.449378 |
| DEV | 50 | UP_BREAKOUT_SHORT | 1402 | -1.984403 | 0.848108 |
| DEV | 100 | BOOK | 2794 | 0.198570 | 0.458077 |
| DEV | 100 | DOWN_BREAKOUT_LONG | 1392 | 1.463301 | 0.278036 |
| DEV | 100 | UP_BREAKOUT_SHORT | 1402 | -1.057139 | 0.684066 |
| DEV | 150 | BOOK | 2794 | 0.725592 | 0.351332 |
| DEV | 150 | DOWN_BREAKOUT_LONG | 1392 | 1.307686 | 0.304185 |
| DEV | 150 | UP_BREAKOUT_SHORT | 1402 | 0.147649 | 0.479176 |

## Paired TP minus no-TP

Same admitted trades; daily Politis-White inference is two-sided.

| segment | TP bps | arm | n | paired mean bps | two-sided p |
|---|---:|---|---:|---:|---:|
| DEV | 50 | BOOK | 2794 | -0.151111 | 0.924154 |
| DEV | 50 | DOWN_BREAKOUT_LONG | 1392 | -1.645686 | 0.377981 |
| DEV | 50 | UP_BREAKOUT_SHORT | 1402 | 1.332804 | 0.584721 |
| DEV | 100 | BOOK | 2794 | 0.880987 | 0.568772 |
| DEV | 100 | DOWN_BREAKOUT_LONG | 1392 | -0.508002 | 0.664167 |
| DEV | 100 | UP_BREAKOUT_SHORT | 1402 | 2.260068 | 0.40863 |
| DEV | 150 | BOOK | 2794 | 1.408008 | 0.322334 |
| DEV | 150 | DOWN_BREAKOUT_LONG | 1392 | -0.663616 | nan |
| DEV | 150 | UP_BREAKOUT_SHORT | 1402 | 3.464857 | 0.20074 |

## k45_validation_r2_19_20261003

- 테스트 재실행 `tests/test_k45_validation_r2_19.py`: `6 passed in 7.76s`
### manifest 필드

| 필드 | 값 |
|---|---|
| experiment | R2-19 |
| status | COMPLETE |
| started_utc | 2026-10-03T07:03:33.788797+00:00 |
| finished_utc | 2026-10-03T07:05:29.381244+00:00 |
| elapsed_seconds | 115.58895429968834 |
| data_cutoff | 2026-06-30T23:59:00+00:00 |
| frozen_candidates | ["E1/1h/3/signal/L", "E1/1h/2/signal/L", "F3/1h/10/24/signal/LS", "F3/1h/5/24/signal/LS", "A3/4h/720/signal/LS", "F4/1h/5/4/signal/L", "BUY_HOLD"] |
| hypothesis_frozen | 검토 1순위 E1/1h/3/signal/L은 평가손익 원장·경계 분할·PW 자동 블록·DSR(813 시도)을 적용해도 (a) DEV 총 net > 0, (b) DEV PW CI 하한 > 0, (c) DSR > 0.95, (d) 사건 단위 상위 5개 제외 후 DEV 총 net > 0 을 모두 만족한다. |
| oos_result | {"r214": false, "archive": false} |
| reproduction_pass | True |
| trial_counts | {"R2-14": 813, "R2-15": 120, "R2-16-entry": 720, "R2-16-tail": 324, "R2-17": 2682, "R2-18": 48, "total": 4707} |
| workers | 1 |
| numeric_threads | 4 |
| live_orders | 0 |
| downloads | 0 |
| hold_a_read | 0 |
| funding_archive_columns | {"time": "calc_time", "interval": "funding_interval_hours", "rate": "last_funding_rate"} |
| funding_audit | {"r214_count": 7118.0, "archive_count": 7119.0, "both_count": 7118.0, "match_count": 1881.0, "mismatch_count": 5237.0, "r214_only_count": 0.0, "archive_only_count": 1.0, "max_abs_difference": 0.002839270007214509} |
| long_short_audit | {"metrics_rows": 612516, "registry_rows": 3417120, "create_time_minute_remainders": "{\"0\": 51048, \"1\": 1, \"10\": 51042, \"11\": 1, \"14\": 1, \"15\": 51049, \"20\": 51040, \"25\": 51037, \"30\": 51034, \"31\": 1, \"35\": 51041, \"36\": 1, \"40\": 51040, \"41\": 1, \"45\": 51044, \"49\": 1, \"5\": 51028, \"50\": 51047, \"51\": 1, \"52\": 1, \"53\": 1, \"55\": 51053, \"56\": 1, \"57\": 1, \"6\": 1}", "asof_violations": 0, "unmatched_registry_rows": 351360, "value_comparisons": 3036795, "value_tolerance": 1e-06, "stale_fallback_rows": 1585, "value_matches": 3036795, "value_mismatches": 0, "m |

- 출력 해시 확인: 10/10 일치

### REPORT.md 앞 150줄 (전체 708줄, 원문)

# R2-19

## reproduction

| cell_id | segment | n_new | n_r214 | n_difference | net_new | net_r214 | net_difference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1\|1h\|3\|signal\|L | DEV | 375 | 375 | 0 | 14636.4336642977 | 14636.4336642977 | -0.0000000000 |
| E1\|1h\|3\|signal\|L | HOLD_B | 30 | 30 | 0 | 1447.3430457597 | 1447.3430457597 | 0.0000000000 |
| E1\|1h\|2\|signal\|L | DEV | 583 | 583 | 0 | 15518.3607558782 | 15518.3607558782 | 0.0000000000 |
| E1\|1h\|2\|signal\|L | HOLD_B | 49 | 49 | 0 | 1917.8080478771 | 1917.8080478771 | 0.0000000000 |
| F3\|1h\|10/24\|signal\|LS | DEV | 873 | 873 | 0 | 35384.2296531329 | 35384.2296531329 | -0.0000000000 |
| F3\|1h\|10/24\|signal\|LS | HOLD_B | 76 | 76 | 0 | 1182.3945942850 | 1182.3945942850 | 0.0000000000 |
| F3\|1h\|5/24\|signal\|LS | DEV | 612 | 612 | 0 | 28370.3048586813 | 28370.3048586813 | -0.0000000000 |
| F3\|1h\|5/24\|signal\|LS | HOLD_B | 43 | 43 | 0 | 1036.9933927703 | 1036.9933927703 | 0.0000000000 |
| A3\|4h\|720\|signal\|LS | DEV | 339 | 339 | 0 | 31309.3806102778 | 31309.3806102777 | 0.0000000000 |
| A3\|4h\|720\|signal\|LS | HOLD_B | 45 | 45 | 0 | 3055.9374447653 | 3055.9374447653 | 0.0000000000 |
| F4\|1h\|5/4\|signal\|L | DEV | 1812 | 1812 | 0 | 8056.2897985018 | 8056.2897985018 | 0.0000000000 |
| F4\|1h\|5/4\|signal\|L | HOLD_B | 186 | 186 | 0 | 1122.3966243537 | 1122.3966243537 | -0.0000000000 |

## funding_audit

| r214_count | archive_count | both_count | match_count | mismatch_count | r214_only_count | archive_only_count | max_abs_difference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7118 | 7119 | 7118 | 1881 | 5237 | 0 | 1 | 0.0028392700 |

| time | rate_r214 | rate_archive | only_in | difference | match | abs_difference |
| --- | --- | --- | --- | --- | --- | --- |
| 2020-03-13 08:00:00+00:00 | -0.0001607300 | -0.0030000000 | both | 0.0028392700 | 0 | 0.0028392700 |
| 2020-02-12 00:00:00+00:00 | 0.0005012000 | 0.0030000000 | both | -0.0024988000 | 0 | 0.0024988000 |
| 2020-03-13 16:00:00+00:00 | -0.0030000000 | -0.0006537800 | both | -0.0023462200 | 0 | 0.0023462200 |
| 2020-02-12 08:00:00+00:00 | 0.0030000000 | 0.0010805500 | both | 0.0019194500 | 0 | 0.0019194500 |
| 2021-02-08 16:00:00+00:00 | 0.0005788700 | 0.0024899300 | both | -0.0019110600 | 0 | 0.0019110600 |
| 2021-01-04 16:00:00+00:00 | 0.0023648201 | 0.0005613700 | both | 0.0018034501 | 0 | 0.0018034501 |
| 2021-04-10 08:00:00+00:00 | 0.0001295900 | 0.0014862400 | both | -0.0013566500 | 0 | 0.0013566500 |
| 2021-01-30 00:00:00+00:00 | 0.0016678900 | 0.0003920800 | both | 0.0012758100 | 0 | 0.0012758100 |
| 2021-05-19 16:00:00+00:00 | 0.0003581300 | -0.0008969700 | both | 0.0012551000 | 0 | 0.0012551000 |
| 2020-08-10 08:00:00+00:00 | 0.0001000000 | 0.0013189800 | both | -0.0012189800 | 0 | 0.0012189800 |
| 2021-01-08 08:00:00+00:00 | 0.0021351699 | 0.0009204400 | both | 0.0012147299 | 0 | 0.0012147299 |
| 2021-02-09 00:00:00+00:00 | 0.0024899300 | 0.0013112500 | both | 0.0011786800 | 0 | 0.0011786800 |
| 2021-01-08 00:00:00+00:00 | 0.0009984100 | 0.0021351700 | both | -0.0011367600 | 0 | 0.0011367600 |
| 2020-02-06 00:00:00+00:00 | 0.0005263100 | 0.0016402100 | both | -0.0011139000 | 0 | 0.0011139000 |
| 2021-01-16 00:00:00+00:00 | 0.0011818500 | 0.0001000000 | both | 0.0010818500 | 0 | 0.0010818500 |
| 2021-01-29 16:00:00+00:00 | 0.0006480300 | 0.0016678900 | both | -0.0010198600 | 0 | 0.0010198600 |
| 2020-08-10 16:00:00+00:00 | 0.0013189800 | 0.0003021800 | both | 0.0010168000 | 0 | 0.0010168000 |
| 2021-05-20 00:00:00+00:00 | -0.0008969700 | 0.0001000000 | both | -0.0009969700 | 0 | 0.0009969700 |
| 2021-01-02 16:00:00+00:00 | 0.0002015100 | 0.0011547100 | both | -0.0009532000 | 0 | 0.0009532000 |
| 2021-02-11 16:00:00+00:00 | 0.0008307000 | 0.0017411000 | both | -0.0009104000 | 0 | 0.0009104000 |
| 2021-02-07 08:00:00+00:00 | 0.0015554600 | 0.0006512100 | both | 0.0009042500 | 0 | 0.0009042500 |
| 2021-03-15 16:00:00+00:00 | 0.0010521000 | 0.0001577600 | both | 0.0008943400 | 0 | 0.0008943400 |
| 2020-02-04 00:00:00+00:00 | 0.0001000000 | 0.0009928200 | both | -0.0008928200 | 0 | 0.0008928200 |
| 2022-11-10 16:00:00+00:00 | -0.0011195299 | -0.0002383300 | both | -0.0008811999 | 0 | 0.0008811999 |
| 2020-07-28 00:00:00+00:00 | 0.0005188800 | 0.0013948400 | both | -0.0008759600 | 0 | 0.0008759600 |
| 2020-04-30 16:00:00+00:00 | 0.0009751700 | 0.0001000000 | both | 0.0008751700 | 0 | 0.0008751700 |
| 2022-11-10 00:00:00+00:00 | -0.0003297600 | -0.0011917200 | both | 0.0008619600 | 0 | 0.0008619600 |
| 2020-02-06 08:00:00+00:00 | 0.0016402100 | 0.0007829900 | both | 0.0008572200 | 0 | 0.0008572200 |
| 2020-04-30 08:00:00+00:00 | 0.0001320800 | 0.0009751700 | both | -0.0008430900 | 0 | 0.0008430900 |
| 2021-01-06 08:00:00+00:00 | 0.0012719301 | 0.0021000800 | both | -0.0008281499 | 0 | 0.0008281499 |
| 2021-01-09 16:00:00+00:00 | 0.0006691800 | 0.0014694200 | both | -0.0008002400 | 0 | 0.0008002400 |
| 2021-01-19 08:00:00+00:00 | 0.0006167000 | 0.0014009000 | both | -0.0007842000 | 0 | 0.0007842000 |
| 2021-02-02 16:00:00+00:00 | 0.0004427800 | 0.0012218100 | both | -0.0007790300 | 0 | 0.0007790300 |
| 2021-02-15 08:00:00+00:00 | 0.0011786000 | 0.0004061700 | both | 0.0007724300 | 0 | 0.0007724300 |
| 2021-01-04 08:00:00+00:00 | 0.0016412600 | 0.0023648200 | both | -0.0007235600 | 0 | 0.0007235600 |
| 2020-03-14 08:00:00+00:00 | -0.0007642100 | -0.0000494600 | both | -0.0007147500 | 0 | 0.0007147500 |
| 2021-01-20 00:00:00+00:00 | 0.0015846700 | 0.0008817800 | both | 0.0007028900 | 0 | 0.0007028900 |
| 2021-01-20 08:00:00+00:00 | 0.0008817800 | 0.0001796700 | both | 0.0007021100 | 0 | 0.0007021100 |
| 2021-01-09 00:00:00+00:00 | 0.0013189201 | 0.0006295400 | both | 0.0006893801 | 0 | 0.0006893801 |
| 2020-06-02 16:00:00+00:00 | 0.0007831000 | 0.0001000000 | both | 0.0006831000 | 0 | 0.0006831000 |
| 2021-01-10 16:00:00+00:00 | 0.0012063200 | 0.0005298800 | both | 0.0006764400 | 0 | 0.0006764400 |
| 2020-03-17 00:00:00+00:00 | -0.0009035800 | -0.0002383000 | both | -0.0006652800 | 0 | 0.0006652800 |
| 2021-02-13 16:00:00+00:00 | 0.0014160899 | 0.0007594600 | both | 0.0006566299 | 0 | 0.0006566299 |
| 2021-07-26 08:00:00+00:00 | -0.0005484100 | 0.0001000000 | both | -0.0006484100 | 0 | 0.0006484100 |
| 2021-05-06 00:00:00+00:00 | 0.0001173400 | 0.0007612100 | both | -0.0006438700 | 0 | 0.0006438700 |
| 2021-02-06 00:00:00+00:00 | 0.0009915400 | 0.0003478200 | both | 0.0006437200 | 0 | 0.0006437200 |
| 2021-01-06 00:00:00+00:00 | 0.0006290400 | 0.0012719300 | both | -0.0006428900 | 0 | 0.0006428900 |
| 2020-02-18 00:00:00+00:00 | 0.0009107600 | 0.0002696700 | both | 0.0006410900 | 0 | 0.0006410900 |
| 2021-02-10 16:00:00+00:00 | 0.0017535000 | 0.0011239700 | both | 0.0006295300 | 0 | 0.0006295300 |
| 2020-01-20 00:00:00+00:00 | 0.0009246700 | 0.0002970200 | both | 0.0006276500 | 0 | 0.0006276500 |

## long_short_audit

| metrics_rows | registry_rows | create_time_minute_remainders | asof_violations | unmatched_registry_rows | value_comparisons | value_tolerance | stale_fallback_rows | value_matches | value_mismatches | max_abs_value_difference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 612516 | 3417120 | {"0": 51048, "1": 1, "10": 51042, "11": 1, "14": 1, "15": 51049, "20": 51040, "25": 51037, "30": 51034, "31": 1, "35": 51041, "36": 1, "40": 51040, "41": 1, "45": 51044, "49": 1, "5": 51028, "50": 51047, "51": 1, "52": 1, "53": 1, "55": 51053, "56": 1, "57": 1, "6": 1} | 0 | 351360 | 3036795 | 0.0000010000 | 1585 | 3036795 | 0 | 0.0000002383 |

## boundary

| cell_id | funding_source | crossing_n | original_all_dev_bps | dev_share_bps | hold_b_share_bps | dev_difference_bps |
| --- | --- | --- | --- | --- | --- | --- |
| A3\|4h\|720\|signal\|LS | archive | 1 | -54.8551952716 | -93.8061188685 | 38.9509235969 | -38.9509235969 |
| A3\|4h\|720\|signal\|LS | r214 | 1 | -54.9762952414 | -93.7233188711 | 38.7470236296 | -38.7470236296 |
| BUY_HOLD | archive | 1 | 11587.0129284366 | 15665.3828120298 | -4078.3698835934 | 4078.3698835932 |
| BUY_HOLD | r214 | 1 | 11586.3456797125 | 15664.7578632413 | -4078.4121835288 | 4078.4121835288 |

## risk

| cell_id | funding_source | segment | cost_bps | n | net_total_bps | mtm_daily_sharpe | mtm_max_drawdown_bps | worst_day_bps | realized_net_total_bps | realized_daily_sharpe | realized_max_drawdown_bps | r214_reported_net_bps | r214_reported_sharpe | r214_reported_mdd_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1\|1h\|3\|signal\|L | r214 | DEV | 4.0000000000 | 375 | 14636.4336642976 | 1.2043926921 | 3937.3477194219 | -701.6451380802 | 14636.4336642977 | 1.1482399091 | 3646.9403075508 | 14636.4336642977 | 1.1482399091 | 3646.9403075508 |
| E1\|1h\|3\|signal\|L | r214 | DEV_EX2020 | 4.0000000000 | 332 | 11374.6635168459 | 1.0289245052 | 3937.3477194217 | -701.6451380802 | 11374.6635168459 | 0.9910127164 | 3646.9403075508 | nan | nan | nan |
| E1\|1h\|3\|signal\|L | r214 | HOLD_B | 4.0000000000 | 30 | 1447.3430457597 | 2.0774473116 | 664.0495593996 | -320.4654041805 | 1447.3430457597 | 2.1468674736 | 557.2562686126 | 1447.3430457597 | 2.1468674736 | 557.2562686126 |
| E1\|1h\|3\|signal\|L | r214 | DEV | 8.0000000000 | 375 | 13136.4336642976 | 1.0819998296 | 4145.3477194218 | -703.6451380802 | 13136.4336642977 | 1.0321181344 | 3830.9403075508 | 13136.4336642977 | 1.0321181344 | nan |
| E1\|1h\|3\|signal\|L | r214 | DEV_EX2020 | 8.0000000000 | 332 | 10046.6635168459 | 0.9096262249 | 4145.3477194217 | -703.6451380802 | 10046.6635168459 | 0.8764526303 | 3830.9403075508 | nan | nan | nan |
| E1\|1h\|3\|signal\|L | r214 | HOLD_B | 8.0000000000 | 30 | 1327.3430457597 | 1.9122803996 | 676.0495593996 | -322.4654041805 | 1327.3430457597 | 1.9789467905 | 577.2562686126 | 1327.3430457597 | 1.9789467905 | nan |
| E1\|1h\|3\|signal\|L | r214 | DEV | 12.0000000000 | 375 | 11636.4336642976 | 0.9592834367 | 4353.3477194219 | -705.6451380802 | 11636.4336642977 | 0.9154942072 | 4014.9403075508 | nan | nan | nan |
| E1\|1h\|3\|signal\|L | r214 | DEV_EX2020 | 12.0000000000 | 332 | 8718.6635168459 | 0.7900388821 | 4353.3477194217 | -705.6451380802 | 8718.6635168459 | 0.7614673729 | 4014.9403075508 | nan | nan | nan |
| E1\|1h\|3\|signal\|L | r214 | HOLD_B | 12.0000000000 | 30 | 1207.3430457597 | 1.7454834007 | 694.6100076972 | -324.4654041805 | 1207.3430457597 | 1.8085353610 | 597.2562686126 | nan | nan | nan |
| E1\|1h\|2\|signal\|L | r214 | DEV | 4.0000000000 | 583 | 15518.3607558780 | 1.0327265695 | 5501.1204363544 | -910.3558957905 | 15518.3607558782 | 1.0116016114 | 4575.3729870331 | 15518.3607558782 | 1.0116016114 | 4575.3729870331 |
| E1\|1h\|2\|signal\|L | r214 | DEV_EX2020 | 4.0000000000 | 525 | 11390.4089592193 | 0.8312059973 | 5501.1204363543 | -910.3558957905 | 11390.4089592195 | 0.8235617904 | 4575.3729870331 | nan | nan | nan |
| E1\|1h\|2\|signal\|L | r214 | HOLD_B | 4.0000000000 | 49 | 1917.8080478771 | 2.3140095321 | 846.5296347123 | -320.4654041805 | 1917.8080478771 | 2.2822798471 | 645.9299779885 | 1917.8080478771 | 2.2822798471 | 645.9299779885 |
| E1\|1h\|2\|signal\|L | r214 | DEV | 8.0000000000 | 583 | 13186.3607558780 | 0.8781346365 | 5625.1204363544 | -912.3558957905 | 13186.3607558782 | 0.8604258549 | 4691.3729870331 | 13186.3607558782 | 0.8604258549 | nan |
| E1\|1h\|2\|signal\|L | r214 | DEV_EX2020 | 8.0000000000 | 525 | 9290.4089592193 | 0.6783845062 | 5625.1204363543 | -912.3558957905 | 9290.4089592195 | 0.6722612078 | 4691.3729870331 | nan | nan | nan |
| E1\|1h\|2\|signal\|L | r214 | HOLD_B | 8.0000000000 | 49 | 1721.8080478771 | 2.0840796279 | 870.5296347123 | -322.4654041805 | 1721.8080478771 | 2.0567558407 | 685.9299779885 | 1721.8080478771 | 2.0567558407 | nan |
| E1\|1h\|2\|signal\|L | r214 | DEV | 12.0000000000 | 583 | 10854.3607558780 | 0.7232719221 | 5749.1204363543 | -914.3558957905 | 10854.3607558782 | 0.7088431889 | 4807.3729870331 | nan | nan | nan |
| E1\|1h\|2\|signal\|L | r214 | DEV_EX2020 | 12.0000000000 | 525 | 7190.4089592193 | 0.5253287781 | 5749.1204363544 | -914.3558957905 | 7190.4089592195 | 0.5206366802 | 4807.3729870331 | nan | nan | nan |
| E1\|1h\|2\|signal\|L | r214 | HOLD_B | 12.0000000000 | 49 | 1525.8080478771 | 1.8522595162 | 894.5296347123 | -324.4654041805 | 1525.8080478771 | 1.8288016153 | 725.9299779885 | nan | nan | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV | 4.0000000000 | 873 | 35381.2405954240 | 1.4913106451 | 4027.3116379702 | -1768.8251089036 | 35384.2296531329 | 1.4855972942 | 3216.1466958471 | 35384.2296531329 | 1.4855972942 | 3216.1466958471 |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV_EX2020 | 4.0000000000 | 753 | 31001.6117676537 | 1.4464714168 | 4027.3116379702 | -1768.8251089036 | 31102.9067211207 | 1.4320792242 | 3216.1466958471 | nan | nan | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | HOLD_B | 4.0000000000 | 76 | 1182.3945942849 | 0.7643251676 | 1807.5251456025 | -445.5344038092 | 1182.3945942850 | 0.6820820183 | 1618.8186251421 | 1182.3945942850 | 0.6820820183 | 1618.8186251421 |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV | 8.0000000000 | 873 | 31887.2405954240 | 1.3451818770 | 4131.3116379702 | -1772.8251089036 | 31892.2296531329 | 1.3399743535 | 3272.6576600457 | 31892.2296531329 | 1.3399743535 | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV_EX2020 | 8.0000000000 | 753 | 27987.6117676537 | 1.3070166566 | 4131.3116379702 | -1772.8251089036 | 28090.9067211207 | 1.2943715219 | 3272.6576600457 | nan | nan | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | HOLD_B | 8.0000000000 | 76 | 878.3945942849 | 0.5682630034 | 1983.5251456025 | -447.5344038092 | 878.3945942850 | 0.5069594125 | 1796.7624676828 | 878.3945942850 | 0.5069594125 | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV | 12.0000000000 | 873 | 28393.2405954240 | 1.1987325974 | 4250.5523179346 | -1776.8251089036 | 28400.2296531329 | 1.1940436786 | 3508.6576600457 | nan | nan | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | DEV_EX2020 | 12.0000000000 | 753 | 24973.6117676537 | 1.1672437492 | 4250.5523179347 | -1776.8251089036 | 25078.9067211207 | 1.1563692639 | 3508.6576600457 | nan | nan | nan |
| F3\|1h\|10/24\|signal\|LS | r214 | HOLD_B | 12.0000000000 | 76 | 574.3945942849 | 0.3718495778 | 2159.5251456025 | -449.5344038092 | 574.3945942850 | 0.3316272550 | 1980.7624676828 | nan | nan | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV | 4.0000000000 | 612 | 28367.3158009725 | 1.4159584927 | 3846.3629589600 | -1321.8571916822 | 28370.3048586813 | 1.3586399481 | 3266.7930804600 | 28370.3048586813 | 1.3586399481 | 3266.7930804600 |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV_EX2020 | 4.0000000000 | 515 | 23525.6660872629 | 1.3153415450 | 3846.3629589600 | -1321.8571916822 | 23707.1974746519 | 1.2578624651 | 3266.7930804600 | nan | nan | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | HOLD_B | 4.0000000000 | 43 | 1036.9933927704 | 1.1516896263 | 1265.2737972123 | -370.7931259318 | 1036.9933927703 | 1.0691123435 | 991.2723173917 | 1036.9933927703 | 1.0691123435 | 991.2723173917 |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV | 8.0000000000 | 612 | 25917.3158009725 | 1.2950635729 | 3866.3629589600 | -1323.8571916822 | 25922.3048586813 | 1.2425597712 | 3513.5036806568 | 25922.3048586813 | 1.2425597712 | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV_EX2020 | 8.0000000000 | 515 | 21463.6660872629 | 1.2013338776 | 3866.3629589600 | -1323.8571916822 | 21647.1974746519 | 1.1496114112 | 3513.5036806569 | nan | nan | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | HOLD_B | 8.0000000000 | 43 | 864.9933927704 | 0.9621738795 | 1319.1773492871 | -374.7931259318 | 864.9933927703 | 0.8931589641 | 1043.2723173917 | 864.9933927703 | 0.8931589641 | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV | 12.0000000000 | 612 | 23467.3158009725 | 1.1738246902 | 4150.8488437172 | -1325.8571916822 | 23474.3048586813 | 1.1261660357 | 3851.6604395221 | nan | nan | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | DEV_EX2020 | 12.0000000000 | 515 | 19401.6660872629 | 1.0870104237 | 4150.8488437176 | -1325.8571916822 | 19587.1974746519 | 1.0410757481 | 3851.6604395221 | nan | nan | nan |
| F3\|1h\|5/24\|signal\|LS | r214 | HOLD_B | 12.0000000000 | 43 | 692.9933927704 | 0.7718784234 | 1376.0794127489 | -378.7931259318 | 692.9933927703 | 0.7164638650 | 1100.6631066735 | nan | nan | nan |
| A3\|4h\|720\|signal\|LS | r214 | DEV | 4.0000000000 | 339 | 31207.5363366018 | 0.9845279413 | 7770.1570593800 | -1404.9411284326 | 31309.3806102777 | 0.8003534925 | 6064.4939083931 | 31309.3806102777 | 0.8003534925 | 6064.4939083931 |
| A3\|4h\|720\|signal\|LS | r214 | DEV_EX2020 | 4.0000000000 | 326 | 21620.2767883834 | 0.7449776145 | 7770.1570593811 | -1404.9411284326 | 20587.1904200779 | 0.7205234415 | 6064.4939083931 | nan | nan | nan |
| A3\|4h\|720\|signal\|LS | r214 | HOLD_B | 4.0000000000 | 45 | 3094.6844683949 | 1.2508659375 | 2862.0152716551 | -1154.0725551859 | 3055.9374447653 | 1.0651936827 | 2093.3961345878 | 3055.9374447653 | 1.0651936827 | 2093.3961345878 |
| A3\|4h\|720\|signal\|LS | r214 | DEV | 8.0000000000 | 339 | 29851.5363366018 | 0.9408219261 | 8070.1570593811 | -1404.9411284326 | 29953.3806102777 | 0.7663444161 | 6556.4939083931 | 29953.3806102777 | 0.7663444161 | nan |
| A3\|4h\|720\|signal\|LS | r214 | DEV_EX2020 | 8.0000000000 | 326 | 20316.2767883834 | 0.6993462187 | 8070.1570593811 | -1404.9411284326 | 19283.1904200779 | 0.6755007773 | 6556.4939083931 | nan | nan | nan |
| A3\|4h\|720\|signal\|LS | r214 | HOLD_B | 8.0000000000 | 45 | 2912.6844683949 | 1.1754058733 | 2934.0152716551 | -1154.0725551859 | 2875.9374447653 | 1.0019522832 | 2149.3961345878 | 2875.9374447653 | 1.0019522832 | nan |
| A3\|4h\|720\|signal\|LS | r214 | DEV | 12.0000000000 | 339 | 28495.5363366018 | 0.8971505593 | 8370.1570593813 | -1404.9411284326 | 28597.3806102777 | 0.7322495486 | 7048.4939083931 | nan | nan | nan |
| A3\|4h\|720\|signal\|LS | r214 | DEV_EX2020 | 12.0000000000 | 326 | 19012.2767883834 | 0.6537667714 | 8370.1570593811 | -1404.9411284326 | 17979.1904200779 | 0.6303566038 | 7048.4939083932 | nan | nan | nan |
| A3\|4h\|720\|signal\|LS | r214 | HOLD_B | 12.0000000000 | 45 | 2730.6844683949 | 1.1000662132 | 3006.0152716551 | -1154.0725551859 | 2695.9374447653 | 0.9386943881 | 2205.3961345878 | nan | nan | nan |
| F4\|1h\|5/4\|signal\|L | r214 | DEV | 4.0000000000 | 1812 | 8056.2897985020 | 0.5824112986 | 4221.6620026268 | -1494.1079083222 | 8056.2897985018 | 0.5988886609 | 3503.4506044796 | 8056.2897985018 | 0.5988886609 | 3503.4506044796 |
| F4\|1h\|5/4\|signal\|L | r214 | DEV_EX2020 | 4.0000000000 | 1691 | 7958.5504042646 | 0.6118306560 | 4221.6620026268 | -1494.1079083222 | 7958.5504042646 | 0.6281578155 | 3503.4506044796 | nan | nan | nan |
| F4\|1h\|5/4\|signal\|L | r214 | HOLD_B | 4.0000000000 | 186 | 1122.3966243537 | 0.7572873845 | 2044.2568992177 | -1221.2840110773 | 1122.3966243537 | 0.7719550497 | 1475.4635076560 | 1122.3966243537 | 0.7719550497 | 1475.4635076560 |
| F4\|1h\|5/4\|signal\|L | r214 | DEV | 8.0000000000 | 1812 | 808.2897985020 | 0.0584946103 | 5699.9385128032 | -1510.1079083222 | 808.2897985018 | 0.0601207399 | 4805.0107996109 | 808.2897985018 | 0.0601207399 | nan |
| F4\|1h\|5/4\|signal\|L | r214 | DEV_EX2020 | 8.0000000000 | 1691 | 1194.5504042646 | 0.0919503173 | 5699.9385128032 | -1510.1079083222 | 1194.5504042646 | 0.0943621636 | 4805.0107996109 | nan | nan | nan |
| F4\|1h\|5/4\|signal\|L | r214 | HOLD_B | 8.0000000000 | 186 | 378.3966243537 | 0.2557591670 | 2164.2568992177 | -1235.2840110773 | 378.3966243537 | 0.2608526125 | 1591.4635076560 | 378.3966243537 | 0.2608526125 | nan |
| F4\|1h\|5/4\|signal\|L | r214 | DEV | 12.0000000000 | 1812 | -6439.7102014980 | -0.4658175513 | 7875.0501270925 | -1526.1079083222 | -6439.7102014982 | -0.4784743015 | 7662.6594512204 | nan | nan | nan |
| F4\|1h\|5/4\|signal\|L | r214 | DEV_EX2020 | 12.0000000000 | 1691 | -5569.4495957354 | -0.4286680716 | 7875.0501270927 | -1526.1079083222 | -5569.4495957354 | -0.4396639204 | 7662.6594512204 | nan | nan | nan |

## 대화에서 인용한 숫자 vs 디스크 값

| 실험 | 항목 | 대화에서 말한 값 | 디스크 값 | 같음 |
|---|---|---|---|---|
| R2-9 | SIDE ROLLING_180D q=0.01 L90/S60 DEV n / net_mean | n 335 / +20.80 | n 335 / +20.80 | 같음 |
| R2-9 | SIDE ROLLING_180D q=0.01 L90/S60 HOLD_B n / net_mean | n 40 / +29.26 | n 40 / +29.26 | 같음 |
| R2-9 | SIDE ROLLING_180D q=0.01 L240/S60 DEV n / net_mean | n 245 / +21.85 | n 245 / +21.85 | 같음 |
| R2-9 | SIDE ROLLING_180D q=0.01 L240/S60 HOLD_B n / net_mean | n 32 / +63.80 | n 32 / +63.80 | 같음 |
| R2-9 | SIDE ROLLING_180D q=0.01 L90/S60 DEV pw_ci95 | [+7.35, +33.72] | [+7.35, +33.72] | 같음 |
| R2-9 | DEV cells with pw_ci95_lower > 0 | 43 | 43 | 같음 |
| R2-10 | RESIDUAL_MATCHED_CAUSAL_M020_RATE L45/S60 DEV | n 678 / +6.44 | n 678 / +6.44 | 같음 |
| R2-10 | RESIDUAL_MATCHED_CAUSAL_M020_RATE L45/S60 HOLD_B | +1.61 | n 30 / +1.61 | 같음 |
| R2-11 | manifest out_of_sample_result | -0.0023 / -0.0029 / -0.31 / -1.78 / false | {"quality_mean_spearman_delta_DEV": -0.0023298950942198583, "quality_mean_spearman_delta_HOLD_B": -0.0028756384717150262, "single_grid_mean_net_delta_DEV": -0.3062224355502492, "single_grid_mean_net_delta_HOLD_B": -1.7831141482887234, "hypothesis_all_four_positive": false} | 같음 |
| R2-11 | DEV tuned-version fallback share | 54.8% | 54.769% | 같음 |
| R2-11 | RESIDUAL causal L45/S60 DEV fixed -> tuned | +6.44 -> -0.30 | +6.44 -> -0.30 | 같음 |
| R2-12 | DEV cells with pw_ci95_lower > 0 (of 100) | 0 | 0 | 같음 |
| R2-12 | 1h h60 15m gate E1 k1.0 DEV / HOLD_B | n 1428 +3.76 / n 150 +14.11 | n 1428 +3.76 / n 150 +14.11 | 같음 |
| R2-14 | F3\|1h\|10/24\|signal\|LS | DEV 873 +35,384 Sharpe 1.49 / HB 76 +1,182 | DEV 873 +35,384 Sharpe 1.49 / HOLD_B 76 +1,182 Sharpe 0.68 | 같음 |
| R2-14 | A3\|4h\|720\|signal\|LS | DEV 339 +31,309 Sharpe 0.80 / HB 45 +3,056 | DEV 339 +31,309 Sharpe 0.80 / HOLD_B 45 +3,056 Sharpe 1.07 | 같음 |
| R2-14 | F1\|1h\|5/24\|signal\|LS | DEV 818 +16,024 Sharpe 0.75 / HB 48 +928 | DEV 818 +16,024 Sharpe 0.75 / HOLD_B 48 +928 Sharpe 0.76 | 같음 |
| R2-14 | SPA p (zero / buy_hold) | 0.144 / 0.734 | zero 0.144 / buy_hold 0.734 | 같음 |
| R2-14 | F3 10/24 LS yearly net_bps | +4,281 / +14,319 / +4,765 / +5,540 / +5,070 / +1,410 / +1,182 | 2020 +4,281 / 2021 +14,319 / 2022 +4,765 / 2023 +5,540 / 2024 +5,070 / 2025 +1,410 / 2026 +1,182 | 같음 |
| R2-23 | F3\|1h\|10/24\|signal\|LS DEV_COMMON PESS net / Sharpe / PW lower | +30,362 / 1.55 / +7.56 | +30,362 / 1.55 / +7.56 | 같음 |
| R2-23 | E1\|1h\|3\|signal\|L DEV_COMMON PESS net / Sharpe / PW lower | +8,614 / 0.83 / -0.09 | +8,614 / 0.83 / -0.09 | 같음 |
| R2-24 | C1 FIRST DEV_COMMON PESS net / Sharpe / MDD | +35,718 / 1.73 / 3,674 | +35,718 / 1.73 / 3,674 | 같음 |
| R2-25 | neighbour combos both-better count (PESS / OPT) | 17 / 15 | 17 / 15 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net H1 | 365.221046 | 365.221046 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net H2 | 1503.528994 | 1503.528994 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net H3 | 1376.416586 | 1376.416586 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net H4 | 1397.682266 | 1397.682266 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net H5 | 400.702128 | 400.702128 | 같음 |
| R2-32 | HOLD_A PESS 4bps total_net B0 | 3381.737936 | 3381.737936 | 같음 |
| R2-32 | frozen hypotheses CONFIRMED | 6 | 6 | 같음 |
| R2-32 | LONG exact folds | 581 / 621 | 581 / 621 | 같음 |
| R2-32 | SHORT exact folds | 621 / 621 | 621 / 621 | 같음 |
