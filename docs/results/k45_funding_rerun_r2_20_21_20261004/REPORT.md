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
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q02|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q02|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|EXPANDING_OOS|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|EXPANDING_OOS|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q01|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|MAX|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q01|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h120|SIDE|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q02|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q02|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|EXPANDING_OOS|q05|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q02|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|EXPANDING_OOS|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|MAX|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q02|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q02|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 1h_h240|SIDE|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q01|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q01|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q02|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q02|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q02|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q02|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|EXPANDING_OOS|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q01|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q01|g0|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q01|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q01|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q02|g1|HOLD_B | 0 | 0 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|EXPANDING_OOS|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q01|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q02|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q02|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|MAX|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q02|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q05|g0|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q05|g1|DEV | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h240|SIDE|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|EXPANDING_OOS|q05|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q01|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q02|g1|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q05|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|EXPANDING_OOS|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|MAX|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q01|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q01|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q01|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q01|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q02|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q02|g0|HOLD_B | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q02|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q02|g1|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q05|g0|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q05|g0|HOLD_B | -1 | -1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q05|g1|DEV | 1 | 1 | 확정 |
| R2-20 | NET_SIGN | 4h_h480|SIDE|ROLLING_180D|q05|g1|HOLD_B | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|45|MQ50 | 1 | 1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_STOP|45|MQ80 | 1 | 1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_STOP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_ROLL|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|15|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|15|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|15|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|45|M0 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|45|MQ50 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|DEV|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | DIRECTION|HOLD_B|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|DEV|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | ALWAYS_LONG|HOLD_B|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|DEV|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | OPPOSITE|HOLD_B|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|DEV|G_EXP|45|MQ80 | 1 | 1 | 확정 |
| R2-21 | NET_SIGN | FADE_15|HOLD_B|G_EXP|45|MQ80 | -1 | -1 | 확정 |
| R2-20 | HYPOTHESIS | all_cells_pass | False | False | 확정 |
| R2-21 | HYPOTHESIS | dev_spearman_gt_0 | True | True | 확정 |
| R2-21 | HYPOTHESIS | dev_net_gt_fade | False | False | 확정 |
| R2-21 | HYPOTHESIS | result | FAIL | FAIL | 확정 |

## BOUNDARY_DEPENDENT

| experiment | item_type | item | pess | opt | status |
| --- | --- | --- | --- | --- | --- |
| R2-20 | NET_SIGN | 1h_h60|SIDE|ROLLING_180D|q05|g0|HOLD_B | -1 | 1 | 경계 의존 |
