# k45_gate_direction_20261001 — parquet 표 전체

원본 폴더: out/k45_gate_direction_20261001/

## backtest.parquet

행 8 × 열 26

| segment | margin | n | net_mean_bps | trimmed_top2_mean_bps | long_n | long_net_mean_bps | short_n | short_net_mean_bps | monthly_positive_share | positive_months | months | year_net_mean_bps | trend_30d_net_mean_bps | pw_selector_status | pw_selector_error | pw_bootstrap_reps | pw_bootstrap_seed | pw_block_length_stationary | pw_p_one_sided | pw_ci95_lower_bps | pw_ci95_upper_bps | random_direction_n | random_direction_net_mean_bps | random_bar_matched_n | random_bar_matched_net_mean_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 0 | 10688 | -4.09225 | -4.33884 | 6528 | -3.4684 | 4160 | -5.07123 | 0.224138 | 13 | 58 | {"2021": 0.32037075953832084, "2022": -9.31549063825997, "2023": -4.359033855973619, "2024": -2.2373093066933847, "2025": -4.0805254801716275} | {"-1": -5.098103783584186, "1": -3.0901625166086353} | MEASURABLE |  | 20000 | 20260930 | 3.06494 | 1 | -5.75061 | -2.44518 | 10688 | -3.7642 | 10688 | -4.14189 |
| DEV | 0.05 | 8765 | -4.02862 | -4.3293 | 5555 | -3.20523 | 3210 | -5.45352 | 0.224138 | 13 | 58 | {"2021": 1.0104084498023187, "2022": -8.202324870951289, "2023": -4.47948619937048, "2024": -3.2588039996646336, "2025": -4.87671102291527} | {"-1": -3.643976851019455, "1": -4.408462864322625} | MEASURABLE |  | 20000 | 20260930 | 1.63917 | 1 | -5.72518 | -2.33679 | 10688 | -3.7642 | 8765 | -3.20641 |
| DEV | 0.1 | 6159 | -3.63285 | -3.87814 | 4073 | -2.29454 | 2086 | -6.24596 | 0.293103 | 17 | 58 | {"2021": 1.3823686532694877, "2022": -6.639703001919388, "2023": -4.850633461751298, "2024": -5.071207900996557, "2025": -3.332185539511524} | {"-1": -2.570893670711485, "1": -4.671955278652568} | UNMEASURABLE | invalid Politis-White block length | 0 | 20260930 |  |  |  |  | 10688 | -3.7642 | 6159 | -4.81461 |
| DEV | 0.2 | 2147 | -1.47433 | -2.34132 | 1600 | -1.20013 | 547 | -2.27636 | 0.482759 | 28 | 58 | {"2021": 0.6140399433130627, "2022": -4.475492203318828, "2023": -11.462698727430842, "2024": 1.0943224570426033, "2025": 4.085597711766135} | {"-1": 0.5463846324034323, "1": -3.796424849103457} | MEASURABLE |  | 20000 | 20260930 | 2.31253 | 0.758062 | -5.72266 | 2.75544 | 10688 | -3.7642 | 2147 | -6.52729 |
| HOLD_B | 0 | 1124 | -3.46135 | -4.08215 | 658 | -2.74702 | 466 | -4.46999 | 0.333333 | 2 | 6 | {"2026": -3.461350228056324} | {"-1": -0.9040198077140057, "1": -6.317276667346333} | MEASURABLE |  | 20000 | 20260930 | 1.62664 | 0.963202 | -7.11261 | 0.32845 | 1124 | -5.55987 | 1124 | -6.04513 |
| HOLD_B | 0.05 | 886 | 0.00567648 | -1.27368 | 528 | 0.0938555 | 358 | -0.124375 | 0.5 | 3 | 6 | {"2026": 0.005676484781384262} | {"-1": 0.9207343896238397, "1": -0.9824142105884034} | MEASURABLE |  | 20000 | 20260930 | 1.79965 | 0.493425 | -4.98434 | 4.76191 | 1124 | -5.55987 | 886 | -6.37703 |
| HOLD_B | 0.1 | 524 | -4.74031 | -5.90207 | 325 | -1.73124 | 199 | -9.65462 | 0.166667 | 1 | 6 | {"2026": -4.74030986585246} | {"-1": -4.896035571192493, "1": -4.560231992599172} | MEASURABLE |  | 20000 | 20260930 | 1.59963 | 0.921804 | -11.0661 | 1.91426 | 1124 | -5.55987 | 524 | -5.4584 |
| HOLD_B | 0.2 | 65 | -5.03376 | -16.341 | 50 | -4.95861 | 15 | -5.28427 | 0.5 | 3 | 6 | {"2026": -5.033759850142287} | {"-1": 2.8588086420585572, "1": -21.57057002427739} | MEASURABLE |  | 20000 | 20260930 | 3.82087 | 0.665517 | -27.8572 | 16.683 | 1124 | -5.55987 | 65 | -4.76563 |

## book_trades.parquet

행 107,964 × 열 21

2,000행 초과라 인라인하지 않음. 열: pilot_fold, signal_index, open_time, r45_bps, cls, p_short, p_none, p_long, n_train, selection_mode, n_selected, trend_30d, segment, side, exit_index, net_bps, strategy, margin, entry_day, month, year

## calibration.parquet

행 27 × 열 6

| segment | side | bin | n | p_mean | hit_rate |
|---|---|---|---|---|---|
| DEV | LONG | 1 | 7 | 0.191138 | 0.285714 |
| DEV | LONG | 2 | 93 | 0.264614 | 0.397849 |
| DEV | LONG | 3 | 2120 | 0.375759 | 0.432547 |
| DEV | LONG | 4 | 12838 | 0.455514 | 0.460352 |
| DEV | LONG | 5 | 8383 | 0.53675 | 0.504354 |
| DEV | LONG | 6 | 1098 | 0.633487 | 0.523679 |
| DEV | LONG | 7 | 275 | 0.741629 | 0.501818 |
| DEV | LONG | 8 | 31 | 0.820548 | 0.677419 |
| DEV | LONG | 9 | 1 | 0.90607 | 0 |
| DEV | SHORT | 0 | 1 | 0.0778137 | 0 |
| DEV | SHORT | 1 | 76 | 0.171883 | 0.407895 |
| DEV | SHORT | 2 | 435 | 0.259173 | 0.422989 |
| DEV | SHORT | 3 | 4484 | 0.37078 | 0.433988 |
| DEV | SHORT | 4 | 15405 | 0.448669 | 0.453035 |
| DEV | SHORT | 5 | 4087 | 0.530301 | 0.484463 |
| DEV | SHORT | 6 | 312 | 0.632713 | 0.516026 |
| DEV | SHORT | 7 | 46 | 0.738213 | 0.652174 |
| HOLD_B | LONG | 3 | 174 | 0.385039 | 0.5 |
| HOLD_B | LONG | 4 | 1699 | 0.455523 | 0.457916 |
| HOLD_B | LONG | 5 | 762 | 0.528658 | 0.496063 |
| HOLD_B | LONG | 6 | 19 | 0.623071 | 0.473684 |
| HOLD_B | LONG | 7 | 2 | 0.73507 | 0.5 |
| HOLD_B | SHORT | 2 | 3 | 0.256912 | 0.666667 |
| HOLD_B | SHORT | 3 | 279 | 0.381566 | 0.426523 |
| HOLD_B | SHORT | 4 | 1916 | 0.449394 | 0.462944 |
| HOLD_B | SHORT | 5 | 457 | 0.523303 | 0.490153 |
| HOLD_B | SHORT | 6 | 1 | 0.611053 | 1 |

## dataset.parquet

행 28,518 × 열 234

2,000행 초과라 인라인하지 않음. 열: pilot_fold, signal_index, open_time, test_end_index, r45_bps, cls, trend_30d, trend_7d, ret_30d_bps, ret_7d_bps, f_return_1, f_return_3, f_return_5, f_return_10, f_return_15, f_return_30, f_return_45, f_return_60, f_log_return_1, f_log_return_5, f_momentum_10, f_momentum_30, f_rolling_return_max_20, f_rolling_return_min_20, f_close_sma_5_ratio, f_close_sma_10_ratio, f_close_sma_20_ratio, f_close_sma_60_ratio, f_close_ema_12_ratio, f_close_ema_26_ratio, f_ema_12_26_spread, f_sma_5_20_spread, f_sma_20_60_spread, f_trend_slope_10, f_trend_slope_30, f_distance_to_high_20, f_distance_to_low_20, f_prev_horizon_trend, f_rv_5, f_rv_15, f_rv_30, f_rv_45, f_rv_60, f_rv_120, f_atr_pct, f_atr_pct_30, f_atr_pct_45, f_parkinson_vol_20, f_garman_klass_vol_20, f_range_vol_20, f_har_rv_short, f_har_rv_medium, f_har_rv_long, f_volume_sma_5_ratio, f_volume_sma_20_ratio, f_volume_sma_60_ratio, f_quote_volume_sma_20_ratio, f_taker_ratio, f_taker_imbalance, f_taker_quote_ratio, f_trade_count_ratio, f_trade_count_zscore_20, f_volume_per_trade, f_volume_shock_20, f_high_low_range, f_body_pct, f_upper_shadow, f_lower_shadow, f_close_location_value, f_wick_imbalance, f_body_to_range, f_range_sma_20_ratio, f_inside_bar_flag, f_outside_bar_flag, f_gap_flag, f_gap_ratio_20, f_gap_ratio_60, f_gap_ratio_120, f_max_gap_run_120, f_repaired_flag, f_gap_length, f_canonical_gap_pressure, f_close_zscore_20, f_close_zscore_60, f_volume_zscore_5, f_volume_zscore_20, f_rv_zscore_60, f_range_zscore_20, f_volatility_regime_60, f_volume_regime_60, f_return_1_vol_adj, f_return_5_vol_adj, f_return_10_vol_adj, f_return_30_vol_adj, f_momentum_10_vol_adj, f_momentum_30_vol_adj, f_close_zscore_20_vol_adj, f_close_zscore_60_vol_adj, f_ema_spread_vol_adj, f_sma_spread_vol_adj, f_candle_range_vol_adj, f_body_pct_vol_adj, f_volume_zscore_20_vol_adj, f_trade_count_zscore_20_vol_adj, f_taker_imbalance_vol_adj, f_adl_indicator, f_funding_rate, f_next_funding_rate, f_minutes_to_next_funding, f_funding_blackout_active, f_mark_price_basis, f_premium_index, f_leverage_bracket_utilization, f_weekly_ma20_slope_closed, f_weekly_ma50_slope_closed, f_weekly_ma20_above_ma50, f_weekly_drawdown, f_weekly_vol_contraction, f_close_vs_weekly_ma20, f_close_vs_weekly_ma50, f_hour, f_minute, f_day_of_week, f_session_asia, f_session_europe, f_session_us, f_session_overlap, f_weekend_flag, f_rsi_7, f_rsi_14, f_bb_width_20, f_bb_percent_b, f_ema_5_slope, f_ema_20_slope, f_ema_60_slope, f_price_vs_rolling_vwap_20, f_price_vs_rolling_vwap_60, f_range_position_20, f_distance_to_range_high, f_distance_to_range_low, f_fake_break_low, f_fake_break_high, f_close_back_inside_range, f_vwap_deviation_zscore, f_bb_zscore, f_oi_change_rate_5m, f_oi_change_rate_15m, f_oi_change_rate_30m, f_oi_change_rate_45m, f_oi_change_rate_60m, f_oi_zscore_1d, f_oi_value_zscore_1d, f_global_ls_account, f_taker_ls_ratio, f_global_ls_account_change_5m, f_global_ls_account_change_15m, f_global_ls_account_change_30m, f_global_ls_account_change_45m, f_global_ls_account_change_60m, f_taker_ls_ratio_change_5m, f_taker_ls_ratio_change_15m, f_taker_ls_ratio_change_30m, f_taker_ls_ratio_change_45m, f_taker_ls_ratio_change_60m, f_global_ls_account_taker_ls_ratio_gap, f_trend_slope_15m, f_return_15m, f_ema_gap_15m, f_ma_slope_15m, f_rsi_15m, f_atr_pct_15m, f_bb_width_15m, f_adx_15m, f_volume_z_15m, f_trend_slope_45m, f_return_45m, f_ema_gap_45m, f_ma_slope_45m, f_rsi_45m, f_atr_pct_45m, f_bb_width_45m, f_adx_45m, f_volume_z_45m, f_trend_slope_1h, f_return_1h, f_ema_gap_1h, f_ma_slope_1h, f_rsi_1h, f_atr_pct_1h, f_bb_width_1h, f_adx_1h, f_volume_z_1h, f_trend_slope_4h, f_return_4h, f_ema_gap_4h, f_ma_slope_4h, f_rsi_4h, f_atr_pct_4h, f_bb_width_4h, f_adx_4h, f_volume_z_4h, f_trend_slope_24h, f_return_24h, f_drawdown_from_24h_high, f_distance_from_24h_high, f_distance_from_24h_low, f_rolling_high_breakout_24h, f_rolling_low_breakdown_24h, f_regime_prob_up, f_regime_prob_range, f_regime_prob_down, m_book_valid, m_book_imbalance_1pct, m_book_imbalance_5pct, m_book_depth_total, m_book_slope_1_5, m_book_depth_change_5m, m_liquidity_valid, m_amihud_illiquidity, m_amihud_surge, m_kyle_lambda, m_kyle_lambda_surge, m_spread_valid, m_spread_bps_mean, m_spread_bps_max, m_spread_bps_std, m_top_imbalance_mean, m_quote_update_count, m_trade_valid, m_trade_count, m_mean_trade_size, m_taker_buy_share, m_trade_count_surge, m_big_trade_share

## deciles.parquet

행 20 × 열 7

| segment | decile | n | score_mean | r_mean | long_share | short_share |
|---|---|---|---|---|---|---|
| DEV | 0 | 2485 | -0.182571 | 2.10811 | 0.451509 | 0.4833 |
| DEV | 1 | 2485 | -0.0873845 | -0.612034 | 0.430181 | 0.498994 |
| DEV | 2 | 2484 | -0.0435881 | 0.304951 | 0.444847 | 0.470209 |
| DEV | 3 | 2485 | -0.00868128 | 0.2755 | 0.47002 | 0.460362 |
| DEV | 4 | 2484 | 0.0221995 | -0.781194 | 0.477456 | 0.456924 |
| DEV | 5 | 2485 | 0.0510224 | 0.378526 | 0.462777 | 0.474447 |
| DEV | 6 | 2484 | 0.080271 | 1.8191 | 0.505233 | 0.419082 |
| DEV | 7 | 2485 | 0.113678 | -0.21275 | 0.486117 | 0.43662 |
| DEV | 8 | 2484 | 0.160296 | 1.98227 | 0.518519 | 0.416667 |
| DEV | 9 | 2485 | 0.296041 | 4.88607 | 0.513883 | 0.435815 |
| HOLD_B | 0 | 266 | -0.138306 | 5.12045 | 0.477444 | 0.488722 |
| HOLD_B | 1 | 266 | -0.0817094 | -5.44755 | 0.424812 | 0.5 |
| HOLD_B | 2 | 265 | -0.0485515 | -4.35572 | 0.441509 | 0.501887 |
| HOLD_B | 3 | 266 | -0.0181945 | 2.74987 | 0.458647 | 0.477444 |
| HOLD_B | 4 | 265 | 0.00828802 | 2.44754 | 0.467925 | 0.475472 |
| HOLD_B | 5 | 266 | 0.0334089 | -3.98079 | 0.469925 | 0.451128 |
| HOLD_B | 6 | 265 | 0.0579675 | 5.6435 | 0.501887 | 0.433962 |
| HOLD_B | 7 | 266 | 0.081705 | -1.32214 | 0.477444 | 0.473684 |
| HOLD_B | 8 | 265 | 0.113946 | 2.84218 | 0.490566 | 0.422642 |
| HOLD_B | 9 | 266 | 0.176337 | 7.11656 | 0.507519 | 0.417293 |

## precheck.parquet

행 684 × 열 8

| feature | target | pooled_spearman | n_months | agree_months | p_one_sided | bonferroni_alpha | passes |
|---|---|---|---|---|---|---|---|
| trend_30d | r45_bps | 0.0199919 | 45 | 15 | 0.991953 | 7.30994e-05 | False |
| trend_30d | long | 0.0162492 | 45 | 17 | 0.963773 | 7.30994e-05 | False |
| trend_30d | short | -0.0164033 | 45 | 18 | 0.932422 | 7.30994e-05 | False |
| trend_7d | r45_bps | 0.00236247 | 60 | 23 | 0.974053 | 7.30994e-05 | False |
| trend_7d | long | 0.000950147 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| trend_7d | short | -0.0142752 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| ret_30d_bps | r45_bps | 0.0121088 | 60 | 9 | 1 | 7.30994e-05 | False |
| ret_30d_bps | long | 0.00985298 | 60 | 10 | 1 | 7.30994e-05 | False |
| ret_30d_bps | short | -0.013234 | 60 | 13 | 0.999998 | 7.30994e-05 | False |
| ret_7d_bps | r45_bps | -0.00335414 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| ret_7d_bps | long | -0.00227076 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| ret_7d_bps | short | -0.0115574 | 60 | 15 | 0.999979 | 7.30994e-05 | False |
| f_return_1 | r45_bps | -0.0284393 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_return_1 | long | -0.0214871 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_return_1 | short | 0.0277964 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_return_3 | r45_bps | -0.0188035 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_return_3 | long | -0.0182551 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_return_3 | short | 0.0185295 | 60 | 41 | 0.0031088 | 7.30994e-05 | False |
| f_return_5 | r45_bps | -0.025546 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_5 | long | -0.02651 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_5 | short | 0.0244688 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_return_10 | r45_bps | -0.0410548 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_return_10 | long | -0.0466184 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_return_10 | short | 0.0439499 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_return_15 | r45_bps | -0.0443923 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_15 | long | -0.0573831 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_return_15 | short | 0.0514488 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_return_30 | r45_bps | -0.0414475 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_return_30 | long | -0.0579932 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_30 | short | 0.048778 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_return_45 | r45_bps | -0.0418687 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_return_45 | long | -0.0600633 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_45 | short | 0.0493839 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_60 | r45_bps | -0.0413815 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_return_60 | long | -0.0602468 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_60 | short | 0.0507778 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_log_return_1 | r45_bps | -0.0284393 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_log_return_1 | long | -0.0214871 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_log_return_1 | short | 0.0277964 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_log_return_5 | r45_bps | -0.025546 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_log_return_5 | long | -0.02651 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_log_return_5 | short | 0.0244688 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_momentum_10 | r45_bps | -0.0410548 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_momentum_10 | long | -0.0466184 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_momentum_10 | short | 0.0439499 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_momentum_30 | r45_bps | -0.0414475 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_momentum_30 | long | -0.0579932 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_momentum_30 | short | 0.048778 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_rolling_return_max_20 | r45_bps | 0.00895474 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_rolling_return_max_20 | long | 0.0139476 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_rolling_return_max_20 | short | 0.0251028 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_rolling_return_min_20 | r45_bps | -0.0332962 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_rolling_return_min_20 | long | -0.052014 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_rolling_return_min_20 | short | 0.0103615 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_close_sma_5_ratio | r45_bps | -0.0199767 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_close_sma_5_ratio | long | -0.0185208 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_close_sma_5_ratio | short | 0.0204805 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_close_sma_10_ratio | r45_bps | -0.0270457 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_close_sma_10_ratio | long | -0.0300783 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_close_sma_10_ratio | short | 0.0299395 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_close_sma_20_ratio | r45_bps | -0.0418078 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_close_sma_20_ratio | long | -0.0513803 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_close_sma_20_ratio | short | 0.0479062 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_close_sma_60_ratio | r45_bps | -0.0460792 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_close_sma_60_ratio | long | -0.0650479 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_close_sma_60_ratio | short | 0.0555511 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_close_ema_12_ratio | r45_bps | -0.0333574 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_close_ema_12_ratio | long | -0.040422 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_close_ema_12_ratio | short | 0.038823 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_close_ema_26_ratio | r45_bps | -0.0443042 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_close_ema_26_ratio | long | -0.0576946 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_close_ema_26_ratio | short | 0.0521211 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_ema_12_26_spread | r45_bps | -0.0440447 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_ema_12_26_spread | long | -0.0637178 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_ema_12_26_spread | short | 0.053391 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_sma_5_20_spread | r45_bps | -0.0465017 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_sma_5_20_spread | long | -0.058936 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_sma_5_20_spread | short | 0.0520881 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_sma_20_60_spread | r45_bps | -0.0325527 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_sma_20_60_spread | long | -0.0524361 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_sma_20_60_spread | short | 0.0408821 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_trend_slope_10 | r45_bps | -0.0331496 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_trend_slope_10 | long | -0.038794 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_trend_slope_10 | short | 0.0363091 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_trend_slope_30 | r45_bps | -0.034513 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_trend_slope_30 | long | -0.052927 | 60 | 55 | 5.19133e-12 | 7.30994e-05 | True |
| f_trend_slope_30 | short | 0.0431177 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_distance_to_high_20 | r45_bps | -0.0484547 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_distance_to_high_20 | long | -0.0593136 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_distance_to_high_20 | short | 0.0306254 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_distance_to_low_20 | r45_bps | -0.0184542 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_distance_to_low_20 | long | -0.018435 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_distance_to_low_20 | short | 0.0410295 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_prev_horizon_trend | r45_bps | -0.0392896 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_prev_horizon_trend | long | -0.0565082 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_prev_horizon_trend | short | 0.0476411 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_rv_5 | r45_bps | 0.0233302 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_rv_5 | long | 0.0372479 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_rv_5 | short | 0.00274613 | 60 | 21 | 0.993255 | 7.30994e-05 | False |
| f_rv_15 | r45_bps | 0.0206178 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_rv_15 | long | 0.0345693 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_rv_15 | short | 0.0119821 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_rv_30 | r45_bps | 0.021998 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_rv_30 | long | 0.036107 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_rv_30 | short | 0.0119803 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_rv_45 | r45_bps | 0.0228647 | 60 | 41 | 0.0031088 | 7.30994e-05 | False |
| f_rv_45 | long | 0.0367157 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_rv_45 | short | 0.0115621 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_rv_60 | r45_bps | 0.0245302 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_rv_60 | long | 0.0373468 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_rv_60 | short | 0.00930563 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_rv_120 | r45_bps | 0.0224955 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_rv_120 | long | 0.0323908 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_rv_120 | short | 0.0118328 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_atr_pct | r45_bps | 0.024967 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_atr_pct | long | 0.0405657 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_atr_pct | short | 0.00969449 | 60 | 26 | 0.87747 | 7.30994e-05 | False |
| f_atr_pct_30 | r45_bps | 0.025159 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_atr_pct_30 | long | 0.0398316 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_atr_pct_30 | short | 0.0100804 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_atr_pct_45 | r45_bps | 0.0256809 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_atr_pct_45 | long | 0.0397071 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_atr_pct_45 | short | 0.00966055 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_parkinson_vol_20 | r45_bps | 0.0259328 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_parkinson_vol_20 | long | 0.0398987 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_parkinson_vol_20 | short | 0.00861455 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_garman_klass_vol_20 | r45_bps | 0.0267627 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_garman_klass_vol_20 | long | 0.0403616 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_garman_klass_vol_20 | short | 0.00783374 | 60 | 25 | 0.922499 | 7.30994e-05 | False |
| f_range_vol_20 | r45_bps | 0.0214053 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_range_vol_20 | long | 0.0314621 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_range_vol_20 | short | 0.00683397 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_har_rv_short | r45_bps | 0.0233302 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_har_rv_short | long | 0.0372479 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_har_rv_short | short | 0.00274613 | 60 | 21 | 0.993255 | 7.30994e-05 | False |
| f_har_rv_medium | r45_bps | 0.021998 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_har_rv_medium | long | 0.036107 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_har_rv_medium | short | 0.0119803 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_har_rv_long | r45_bps | 0.0224955 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_har_rv_long | long | 0.0323908 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_har_rv_long | short | 0.0118328 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_volume_sma_5_ratio | r45_bps | 0.000668406 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_volume_sma_5_ratio | long | 0.00577308 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_volume_sma_5_ratio | short | -0.00420919 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_sma_20_ratio | r45_bps | 0.00378476 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_volume_sma_20_ratio | long | 0.00967598 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_volume_sma_20_ratio | short | -0.00352418 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_volume_sma_60_ratio | r45_bps | 0.0059055 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volume_sma_60_ratio | long | 0.0125924 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_volume_sma_60_ratio | short | -0.00230169 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_quote_volume_sma_20_ratio | r45_bps | 0.00366905 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_quote_volume_sma_20_ratio | long | 0.00954977 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_quote_volume_sma_20_ratio | short | -0.00341136 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_taker_ratio | r45_bps | -0.0139853 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_taker_ratio | long | -0.0105315 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_ratio | short | 0.0150698 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_imbalance | r45_bps | -0.0139853 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_taker_imbalance | long | -0.0105315 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_imbalance | short | 0.0150699 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_quote_ratio | r45_bps | -0.0139764 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_taker_quote_ratio | long | -0.0105214 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_quote_ratio | short | 0.0150681 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_trade_count_ratio | r45_bps | 0.00545081 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_trade_count_ratio | long | 0.00924894 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_trade_count_ratio | short | -0.00342782 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_trade_count_zscore_20 | r45_bps | 0.00835481 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_trade_count_zscore_20 | long | 0.011207 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_trade_count_zscore_20 | short | -0.00684903 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_volume_per_trade | r45_bps | 0.00551721 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_per_trade | long | 0.00461706 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_per_trade | short | -0.00880696 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_shock_20 | r45_bps | 0.00684167 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_shock_20 | long | 0.0117581 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_volume_shock_20 | short | -0.00704526 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_high_low_range | r45_bps | 0.0220812 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_high_low_range | long | 0.0385026 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_high_low_range | short | 0.00641328 | 60 | 25 | 0.922499 | 7.30994e-05 | False |
| f_body_pct | r45_bps | 0.0111147 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_body_pct | long | 0.0255962 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_body_pct | short | 0.00544682 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_upper_shadow | r45_bps | 0.0224751 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_upper_shadow | long | 0.0173629 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_upper_shadow | short | 0.0020147 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_lower_shadow | r45_bps | 0.0126222 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_lower_shadow | long | 0.0235407 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_lower_shadow | short | -0.00155486 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_close_location_value | r45_bps | -0.0244702 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_close_location_value | long | -0.0152556 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_close_location_value | short | 0.0216148 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_wick_imbalance | r45_bps | 0.00822797 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_wick_imbalance | long | -0.00187071 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_wick_imbalance | short | -0.000256189 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_body_to_range | r45_bps | -0.00803697 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_body_to_range | long | -0.00320314 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_body_to_range | short | -0.00022168 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_range_sma_20_ratio | r45_bps | 0.00239877 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_range_sma_20_ratio | long | 0.010409 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_range_sma_20_ratio | short | -0.00355153 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_inside_bar_flag | r45_bps | 0.00545282 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_inside_bar_flag | long | 0.0014692 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_inside_bar_flag | short | -0.00289987 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_outside_bar_flag | r45_bps | -0.00986832 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_outside_bar_flag | long | -0.00821895 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_outside_bar_flag | short | 0.00696582 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_gap_flag | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_flag | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_flag | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_20 | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_20 | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_20 | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_60 | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_60 | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_60 | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_120 | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_120 | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_ratio_120 | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_max_gap_run_120 | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_max_gap_run_120 | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_max_gap_run_120 | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_repaired_flag | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_repaired_flag | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_repaired_flag | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_length | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_length | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_gap_length | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_canonical_gap_pressure | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_canonical_gap_pressure | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_canonical_gap_pressure | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_close_zscore_20 | r45_bps | -0.0400688 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_close_zscore_20 | long | -0.0516291 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_close_zscore_20 | short | 0.0468096 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_close_zscore_60 | r45_bps | -0.0460056 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_close_zscore_60 | long | -0.0691239 | 60 | 55 | 5.19133e-12 | 7.30994e-05 | True |
| f_close_zscore_60 | short | 0.0594538 | 60 | 55 | 5.19133e-12 | 7.30994e-05 | True |
| f_volume_zscore_5 | r45_bps | -0.000618211 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volume_zscore_5 | long | 0.00584528 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_volume_zscore_5 | short | -0.00532682 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_zscore_20 | r45_bps | 0.00684167 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_zscore_20 | long | 0.0117581 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_volume_zscore_20 | short | -0.00704526 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_rv_zscore_60 | r45_bps | 0.00940695 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_rv_zscore_60 | long | 0.0131895 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_rv_zscore_60 | short | -0.00844406 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_range_zscore_20 | r45_bps | 0.00505708 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_range_zscore_20 | long | 0.0118818 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_range_zscore_20 | short | -0.00505246 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volatility_regime_60 | r45_bps | -0.000522865 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volatility_regime_60 | long | 0.00396224 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_volatility_regime_60 | short | 0.00331574 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_volume_regime_60 | r45_bps | 0.00589794 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volume_regime_60 | long | 0.0125854 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_volume_regime_60 | short | -0.00229653 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_return_1_vol_adj | r45_bps | -0.0275967 | 60 | 41 | 0.0031088 | 7.30994e-05 | False |
| f_return_1_vol_adj | long | -0.0221357 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_return_1_vol_adj | short | 0.0297824 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_return_5_vol_adj | r45_bps | -0.0253344 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_5_vol_adj | long | -0.0288309 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_return_5_vol_adj | short | 0.0273743 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_10_vol_adj | r45_bps | -0.0395995 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_return_10_vol_adj | long | -0.0495283 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_return_10_vol_adj | short | 0.0459805 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_return_30_vol_adj | r45_bps | -0.0381087 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_return_30_vol_adj | long | -0.0600382 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_return_30_vol_adj | short | 0.0507585 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_momentum_10_vol_adj | r45_bps | -0.0395995 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_momentum_10_vol_adj | long | -0.0495283 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_momentum_10_vol_adj | short | 0.0459805 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_momentum_30_vol_adj | r45_bps | -0.0381087 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_momentum_30_vol_adj | long | -0.0600382 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_momentum_30_vol_adj | short | 0.0507585 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_close_zscore_20_vol_adj | r45_bps | -0.0334584 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_close_zscore_20_vol_adj | long | -0.0458557 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_close_zscore_20_vol_adj | short | 0.0407202 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_close_zscore_60_vol_adj | r45_bps | -0.0364151 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_close_zscore_60_vol_adj | long | -0.0591399 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_close_zscore_60_vol_adj | short | 0.0510418 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_ema_spread_vol_adj | r45_bps | -0.0418722 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_ema_spread_vol_adj | long | -0.0677247 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_ema_spread_vol_adj | short | 0.0564022 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_sma_spread_vol_adj | r45_bps | -0.0282942 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_sma_spread_vol_adj | long | -0.0546572 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_sma_spread_vol_adj | short | 0.0426998 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_candle_range_vol_adj | r45_bps | 0.00842719 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_candle_range_vol_adj | long | 0.0177313 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_candle_range_vol_adj | short | -0.00292338 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_body_pct_vol_adj | r45_bps | -0.00055253 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_body_pct_vol_adj | long | 0.00875083 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_body_pct_vol_adj | short | -0.00178622 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_volume_zscore_20_vol_adj | r45_bps | 0.00467268 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_zscore_20_vol_adj | long | 0.00770579 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_volume_zscore_20_vol_adj | short | -0.00310197 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_trade_count_zscore_20_vol_adj | r45_bps | 0.000360632 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_trade_count_zscore_20_vol_adj | long | 0.00130111 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_trade_count_zscore_20_vol_adj | short | 0.00119153 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_taker_imbalance_vol_adj | r45_bps | -0.0168801 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_taker_imbalance_vol_adj | long | -0.0135709 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_taker_imbalance_vol_adj | short | 0.0165344 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_adl_indicator | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_adl_indicator | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_adl_indicator | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_rate | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_rate | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_rate | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_next_funding_rate | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_next_funding_rate | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_next_funding_rate | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_minutes_to_next_funding | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_minutes_to_next_funding | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_minutes_to_next_funding | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_blackout_active | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_blackout_active | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_funding_blackout_active | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_mark_price_basis | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_mark_price_basis | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_mark_price_basis | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_premium_index | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_premium_index | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_premium_index | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_leverage_bracket_utilization | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_leverage_bracket_utilization | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_leverage_bracket_utilization | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_weekly_ma20_slope_closed | r45_bps | 0.0115266 | 60 | 23 | 0.974053 | 7.30994e-05 | False |
| f_weekly_ma20_slope_closed | long | 0.0120415 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_weekly_ma20_slope_closed | short | -0.00268678 | 60 | 24 | 0.95377 | 7.30994e-05 | False |
| f_weekly_ma50_slope_closed | r45_bps | 0.0147629 | 60 | 25 | 0.922499 | 7.30994e-05 | False |
| f_weekly_ma50_slope_closed | long | 0.0229842 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_weekly_ma50_slope_closed | short | -2.06607e-05 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_weekly_ma20_above_ma50 | r45_bps | 0.0131223 | 2 | 2 | 0.25 | 7.30994e-05 | False |
| f_weekly_ma20_above_ma50 | long | 0.0143602 | 2 | 2 | 0.25 | 7.30994e-05 | False |
| f_weekly_ma20_above_ma50 | short | -0.00540991 | 2 | 1 | 0.75 | 7.30994e-05 | False |
| f_weekly_drawdown | r45_bps | 0.00342402 | 60 | 25 | 0.922499 | 7.30994e-05 | False |
| f_weekly_drawdown | long | 0.0104773 | 60 | 26 | 0.87747 | 7.30994e-05 | False |
| f_weekly_drawdown | short | 0.00856643 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_weekly_vol_contraction | r45_bps | 0.0213438 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_weekly_vol_contraction | long | 0.0260843 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_weekly_vol_contraction | short | -0.00518441 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_close_vs_weekly_ma20 | r45_bps | 0.00957376 | 60 | 6 | 1 | 7.30994e-05 | False |
| f_close_vs_weekly_ma20 | long | 0.00817588 | 60 | 7 | 1 | 7.30994e-05 | False |
| f_close_vs_weekly_ma20 | short | -0.00776321 | 60 | 8 | 1 | 7.30994e-05 | False |
| f_close_vs_weekly_ma50 | r45_bps | 0.0077725 | 60 | 5 | 1 | 7.30994e-05 | False |
| f_close_vs_weekly_ma50 | long | 0.010562 | 60 | 5 | 1 | 7.30994e-05 | False |
| f_close_vs_weekly_ma50 | short | -0.00146357 | 60 | 9 | 1 | 7.30994e-05 | False |
| f_hour | r45_bps | 0.00843587 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_hour | long | 0.00960322 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_hour | short | -0.00970385 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_minute | r45_bps | -0.00316481 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_minute | long | -0.00268335 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_minute | short | -0.00111061 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_day_of_week | r45_bps | -0.00126076 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_day_of_week | long | -0.00287048 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_day_of_week | short | 0.00623742 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_session_asia | r45_bps | 0.000827673 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_session_asia | long | 0.00195652 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_session_asia | short | -0.0057824 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_session_europe | r45_bps | -0.00730221 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_session_europe | long | -0.00732912 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_session_europe | short | 0.0147031 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_session_us | r45_bps | 0.00659792 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_session_us | long | 0.00570697 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_session_us | short | -0.00993885 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_session_overlap | r45_bps | -0.00730221 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_session_overlap | long | -0.00732912 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_session_overlap | short | 0.0147031 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_weekend_flag | r45_bps | 0.0157594 | 59 | 35 | 0.0962632 | 7.30994e-05 | False |
| f_weekend_flag | long | 0.0150434 | 59 | 32 | 0.301462 | 7.30994e-05 | False |
| f_weekend_flag | short | -0.00784471 | 59 | 30 | 0.5 | 7.30994e-05 | False |
| f_rsi_7 | r45_bps | -0.0342959 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_rsi_7 | long | -0.0451776 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_rsi_7 | short | 0.0424521 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_rsi_14 | r45_bps | -0.0407202 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_rsi_14 | long | -0.0602924 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_rsi_14 | short | 0.0534229 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_bb_width_20 | r45_bps | 0.0212657 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_bb_width_20 | long | 0.0326832 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_bb_width_20 | short | 0.0099228 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_bb_percent_b | r45_bps | -0.0400688 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_bb_percent_b | long | -0.0516291 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_bb_percent_b | short | 0.0468096 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_ema_5_slope | r45_bps | -0.0281037 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_ema_5_slope | long | -0.0329339 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_ema_5_slope | short | 0.0291211 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_ema_20_slope | r45_bps | -0.0437272 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_ema_20_slope | long | -0.0619904 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_ema_20_slope | short | 0.0528501 | 60 | 55 | 5.19133e-12 | 7.30994e-05 | True |
| f_ema_60_slope | r45_bps | -0.0390827 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_ema_60_slope | long | -0.06067 | 60 | 55 | 5.19133e-12 | 7.30994e-05 | True |
| f_ema_60_slope | short | 0.0498434 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_20 | r45_bps | -0.0347644 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_20 | long | -0.0407601 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_20 | short | 0.0382979 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_60 | r45_bps | -0.0426468 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_60 | long | -0.0598785 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_price_vs_rolling_vwap_60 | short | 0.0512289 | 60 | 53 | 3.83596e-10 | 7.30994e-05 | True |
| f_range_position_20 | r45_bps | -0.0393313 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_range_position_20 | long | -0.0474492 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_range_position_20 | short | 0.0431411 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_distance_to_range_high | r45_bps | -0.0484547 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_distance_to_range_high | long | -0.0593136 | 60 | 54 | 4.86148e-11 | 7.30994e-05 | True |
| f_distance_to_range_high | short | 0.0306254 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_distance_to_range_low | r45_bps | -0.0184542 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_distance_to_range_low | long | -0.018435 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_distance_to_range_low | short | 0.0410295 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_fake_break_low | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_fake_break_low | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_fake_break_low | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_fake_break_high | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_fake_break_high | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_fake_break_high | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_close_back_inside_range | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_close_back_inside_range | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_close_back_inside_range | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_vwap_deviation_zscore | r45_bps | -0.0338806 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_vwap_deviation_zscore | long | -0.0448612 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_vwap_deviation_zscore | short | 0.0402182 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_bb_zscore | r45_bps | -0.0400688 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_bb_zscore | long | -0.0516291 | 60 | 52 | 2.60285e-09 | 7.30994e-05 | True |
| f_bb_zscore | short | 0.0468096 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_oi_change_rate_5m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_5m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_5m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_15m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_15m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_15m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_30m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_30m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_30m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_45m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_45m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_45m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_60m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_60m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_change_rate_60m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_zscore_1d | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_zscore_1d | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_zscore_1d | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_value_zscore_1d | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_value_zscore_1d | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_oi_value_zscore_1d | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_5m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_5m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_5m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_15m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_15m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_15m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_30m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_30m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_30m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_45m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_45m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_45m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_60m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_60m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_change_60m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_5m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_5m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_5m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_15m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_15m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_15m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_30m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_30m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_30m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_45m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_45m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_45m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_60m | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_60m | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_taker_ls_ratio_change_60m | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_taker_ls_ratio_gap | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_taker_ls_ratio_gap | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_global_ls_account_taker_ls_ratio_gap | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_trend_slope_15m | r45_bps | -0.0175148 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_trend_slope_15m | long | -0.0313057 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_trend_slope_15m | short | 0.0252202 | 60 | 41 | 0.0031088 | 7.30994e-05 | False |
| f_return_15m | r45_bps | -0.0199527 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_return_15m | long | -0.035276 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_return_15m | short | 0.028899 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_ema_gap_15m | r45_bps | -0.0284617 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_ema_gap_15m | long | -0.0452969 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_ema_gap_15m | short | 0.0352591 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_ma_slope_15m | r45_bps | -0.0199153 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_ma_slope_15m | long | -0.0352474 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_ma_slope_15m | short | 0.0288807 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_rsi_15m | r45_bps | -0.0229831 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_rsi_15m | long | -0.0418865 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_rsi_15m | short | 0.0368491 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_atr_pct_15m | r45_bps | 0.0213649 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_atr_pct_15m | long | 0.0315073 | 60 | 42 | 0.00133522 | 7.30994e-05 | False |
| f_atr_pct_15m | short | 0.0117742 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_bb_width_15m | r45_bps | 0.0180008 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_bb_width_15m | long | 0.0217078 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_bb_width_15m | short | 0.00933447 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_adx_15m | r45_bps | 0.0107684 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_adx_15m | long | 0.00704439 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_adx_15m | short | -0.00353477 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_z_15m | r45_bps | 0.00782586 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_volume_z_15m | long | 0.00848945 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volume_z_15m | short | -0.00126014 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_trend_slope_45m | r45_bps | -0.010594 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_trend_slope_45m | long | -0.0215382 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_trend_slope_45m | short | 0.0115325 | 60 | 41 | 0.0031088 | 7.30994e-05 | False |
| f_return_45m | r45_bps | -0.0106411 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_return_45m | long | -0.0224955 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_45m | short | 0.0116096 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_ema_gap_45m | r45_bps | -0.014089 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_ema_gap_45m | long | -0.0247815 | 60 | 44 | 0.000197022 | 7.30994e-05 | False |
| f_ema_gap_45m | short | 0.0128197 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_ma_slope_45m | r45_bps | -0.0106472 | 60 | 39 | 0.0136701 | 7.30994e-05 | False |
| f_ma_slope_45m | long | -0.022513 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_ma_slope_45m | short | 0.0116283 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_rsi_45m | r45_bps | -0.0126626 | 60 | 40 | 0.00674465 | 7.30994e-05 | False |
| f_rsi_45m | long | -0.0237827 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_rsi_45m | short | 0.0163555 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_atr_pct_45m | r45_bps | 0.0163462 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_atr_pct_45m | long | 0.0285786 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_atr_pct_45m | short | 0.0114873 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_bb_width_45m | r45_bps | 0.0146884 | 60 | 26 | 0.87747 | 7.30994e-05 | False |
| f_bb_width_45m | long | 0.0216798 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_bb_width_45m | short | 0.00769769 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_adx_45m | r45_bps | 0.0182033 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_adx_45m | long | 0.00427057 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_adx_45m | short | -0.0108115 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_volume_z_45m | r45_bps | 0.0127619 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_volume_z_45m | long | 0.00509575 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_volume_z_45m | short | -0.00620902 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_trend_slope_1h | r45_bps | -0.0155448 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_trend_slope_1h | long | -0.0250648 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_trend_slope_1h | short | 0.0139568 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_1h | r45_bps | -0.0182524 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_return_1h | long | -0.027203 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_return_1h | short | 0.0156693 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_ema_gap_1h | r45_bps | -0.0181744 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_ema_gap_1h | long | -0.0265385 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_ema_gap_1h | short | 0.0143114 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_ma_slope_1h | r45_bps | -0.018186 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_ma_slope_1h | long | -0.0271528 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_ma_slope_1h | short | 0.0156315 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_rsi_1h | r45_bps | -0.0123748 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_rsi_1h | long | -0.0206305 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_rsi_1h | short | 0.0138112 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_atr_pct_1h | r45_bps | 0.0144878 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_atr_pct_1h | long | 0.0273268 | 60 | 32 | 0.349442 | 7.30994e-05 | False |
| f_atr_pct_1h | short | 0.0128879 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_bb_width_1h | r45_bps | 0.0110258 | 60 | 27 | 0.816853 | 7.30994e-05 | False |
| f_bb_width_1h | long | 0.0194722 | 60 | 30 | 0.551289 | 7.30994e-05 | False |
| f_bb_width_1h | short | 0.011933 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_adx_1h | r45_bps | 0.00949686 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_adx_1h | long | 0.00666687 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_adx_1h | short | -0.00734274 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_volume_z_1h | r45_bps | 0.00385331 | 60 | 35 | 0.12253 | 7.30994e-05 | False |
| f_volume_z_1h | long | -0.00211082 | 60 | 29 | 0.650558 | 7.30994e-05 | False |
| f_volume_z_1h | short | 0.00436467 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_trend_slope_4h | r45_bps | -0.0101923 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_trend_slope_4h | long | -0.010114 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_trend_slope_4h | short | -0.00600198 | 60 | 21 | 0.993255 | 7.30994e-05 | False |
| f_return_4h | r45_bps | -0.010886 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_return_4h | long | -0.0120853 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_return_4h | short | -0.00645422 | 60 | 18 | 0.999467 | 7.30994e-05 | False |
| f_ema_gap_4h | r45_bps | -0.01359 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_ema_gap_4h | long | -0.0157677 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_ema_gap_4h | short | -0.00188271 | 60 | 17 | 0.999803 | 7.30994e-05 | False |
| f_ma_slope_4h | r45_bps | -0.010921 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_ma_slope_4h | long | -0.0121083 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_ma_slope_4h | short | -0.00643961 | 60 | 19 | 0.998665 | 7.30994e-05 | False |
| f_rsi_4h | r45_bps | -0.00753007 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_rsi_4h | long | -0.0100863 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_rsi_4h | short | -0.00515778 | 60 | 22 | 0.98633 | 7.30994e-05 | False |
| f_atr_pct_4h | r45_bps | 0.0160331 | 60 | 36 | 0.077501 | 7.30994e-05 | False |
| f_atr_pct_4h | long | 0.0311901 | 60 | 38 | 0.0259469 | 7.30994e-05 | False |
| f_atr_pct_4h | short | 0.0138305 | 60 | 28 | 0.740521 | 7.30994e-05 | False |
| f_bb_width_4h | r45_bps | 0.0172415 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_bb_width_4h | long | 0.0277132 | 60 | 37 | 0.0462305 | 7.30994e-05 | False |
| f_bb_width_4h | short | 0.0120139 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_adx_4h | r45_bps | 0.00567962 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_adx_4h | long | 0.00740402 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_adx_4h | short | 0.0017146 | 60 | 26 | 0.87747 | 7.30994e-05 | False |
| f_volume_z_4h | r45_bps | 0.00851486 | 60 | 34 | 0.183147 | 7.30994e-05 | False |
| f_volume_z_4h | long | 0.00417561 | 60 | 31 | 0.448711 | 7.30994e-05 | False |
| f_volume_z_4h | short | -0.00582372 | 60 | 33 | 0.259479 | 7.30994e-05 | False |
| f_trend_slope_24h | r45_bps | -0.0121043 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_trend_slope_24h | long | -0.0152059 | 60 | 47 | 6.07335e-06 | 7.30994e-05 | True |
| f_trend_slope_24h | short | 0.00147673 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_return_24h | r45_bps | -0.0187564 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_return_24h | long | -0.0243915 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_return_24h | short | 0.00975651 | 60 | 46 | 2.11185e-05 | 7.30994e-05 | True |
| f_drawdown_from_24h_high | r45_bps | 0.0247128 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_drawdown_from_24h_high | long | 0.0400063 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_drawdown_from_24h_high | short | -0.0148008 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_distance_from_24h_high | r45_bps | -0.0247128 | 60 | 50 | 8.08191e-08 | 7.30994e-05 | True |
| f_distance_from_24h_high | long | -0.0400063 | 60 | 51 | 1.54252e-08 | 7.30994e-05 | True |
| f_distance_from_24h_high | short | 0.0148008 | 60 | 49 | 3.78064e-07 | 7.30994e-05 | True |
| f_distance_from_24h_low | r45_bps | -0.014844 | 60 | 43 | 0.000532883 | 7.30994e-05 | False |
| f_distance_from_24h_low | long | -0.0147372 | 60 | 45 | 6.7257e-05 | 7.30994e-05 | True |
| f_distance_from_24h_low | short | 0.030365 | 60 | 48 | 1.59181e-06 | 7.30994e-05 | True |
| f_rolling_high_breakout_24h | r45_bps | 0.00618763 | 2 | 1 | 0.75 | 7.30994e-05 | False |
| f_rolling_high_breakout_24h | long | 0.00576205 | 2 | 2 | 0.25 | 7.30994e-05 | False |
| f_rolling_high_breakout_24h | short | -0.00372627 | 2 | 1 | 0.75 | 7.30994e-05 | False |
| f_rolling_low_breakdown_24h | r45_bps | -0.0126456 | 4 | 4 | 0.0625 | 7.30994e-05 | False |
| f_rolling_low_breakdown_24h | long | -0.0133943 | 4 | 4 | 0.0625 | 7.30994e-05 | False |
| f_rolling_low_breakdown_24h | short | 0.0166824 | 4 | 4 | 0.0625 | 7.30994e-05 | False |
| f_regime_prob_up | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_up | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_up | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_range | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_range | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_range | short |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_down | r45_bps |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_down | long |  | 0 | 0 |  | 7.30994e-05 | False |
| f_regime_prob_down | short |  | 0 | 0 |  | 7.30994e-05 | False |
| m_book_valid | r45_bps | 0.00113384 | 11 | 6 | 0.5 | 7.30994e-05 | False |
| m_book_valid | long | -0.00917959 | 11 | 7 | 0.274414 | 7.30994e-05 | False |
| m_book_valid | short | -0.0118635 | 11 | 6 | 0.5 | 7.30994e-05 | False |
| m_book_imbalance_1pct | r45_bps | 0.0387344 | 36 | 30 | 3.48008e-05 | 7.30994e-05 | True |
| m_book_imbalance_1pct | long | 0.0588943 | 36 | 30 | 3.48008e-05 | 7.30994e-05 | True |
| m_book_imbalance_1pct | short | -0.0544172 | 36 | 30 | 3.48008e-05 | 7.30994e-05 | True |
| m_book_imbalance_5pct | r45_bps | 0.0300736 | 36 | 29 | 0.000156276 | 7.30994e-05 | False |
| m_book_imbalance_5pct | long | 0.038755 | 36 | 30 | 3.48008e-05 | 7.30994e-05 | True |
| m_book_imbalance_5pct | short | -0.0281058 | 36 | 27 | 0.00196659 | 7.30994e-05 | False |
| m_book_depth_total | r45_bps | -0.00924959 | 36 | 21 | 0.202516 | 7.30994e-05 | False |
| m_book_depth_total | long | -0.0113145 | 36 | 17 | 0.69114 | 7.30994e-05 | False |
| m_book_depth_total | short | 0.00524311 | 36 | 18 | 0.56603 | 7.30994e-05 | False |
| m_book_slope_1_5 | r45_bps | 0.000457715 | 36 | 21 | 0.202516 | 7.30994e-05 | False |
| m_book_slope_1_5 | long | -0.00432468 | 36 | 16 | 0.797484 | 7.30994e-05 | False |
| m_book_slope_1_5 | short | -0.00890209 | 36 | 17 | 0.69114 | 7.30994e-05 | False |
| m_book_depth_change_5m | r45_bps | -0.00927057 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_book_depth_change_5m | long | -0.00798219 | 36 | 22 | 0.121492 | 7.30994e-05 | False |
| m_book_depth_change_5m | short | 0.00179799 | 36 | 21 | 0.202516 | 7.30994e-05 | False |
| m_liquidity_valid | r45_bps | 0.00156077 | 0 | 0 |  | 7.30994e-05 | False |
| m_liquidity_valid | long | -0.00826009 | 0 | 0 |  | 7.30994e-05 | False |
| m_liquidity_valid | short | -0.0127767 | 0 | 0 |  | 7.30994e-05 | False |
| m_amihud_illiquidity | r45_bps | -0.00904222 | 36 | 18 | 0.56603 | 7.30994e-05 | False |
| m_amihud_illiquidity | long | 0.00110136 | 36 | 18 | 0.56603 | 7.30994e-05 | False |
| m_amihud_illiquidity | short | 0.00586603 | 36 | 17 | 0.69114 | 7.30994e-05 | False |
| m_amihud_surge | r45_bps | -0.00264608 | 36 | 17 | 0.69114 | 7.30994e-05 | False |
| m_amihud_surge | long | 0.0019897 | 36 | 18 | 0.56603 | 7.30994e-05 | False |
| m_amihud_surge | short | -0.00790994 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_kyle_lambda | r45_bps | 0.0224151 | 36 | 23 | 0.0662491 | 7.30994e-05 | False |
| m_kyle_lambda | long | 0.0242884 | 36 | 24 | 0.0326227 | 7.30994e-05 | False |
| m_kyle_lambda | short | -0.00655897 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_kyle_lambda_surge | r45_bps | 0.0132031 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_kyle_lambda_surge | long | 0.0165314 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_kyle_lambda_surge | short | -0.00501324 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_spread_valid | r45_bps | 0.00211966 | 5 | 2 | 0.8125 | 7.30994e-05 | False |
| m_spread_valid | long | -0.00421984 | 5 | 3 | 0.5 | 7.30994e-05 | False |
| m_spread_valid | short | -0.0124724 | 5 | 3 | 0.5 | 7.30994e-05 | False |
| m_spread_bps_mean | r45_bps | -0.0060515 | 11 | 5 | 0.725586 | 7.30994e-05 | False |
| m_spread_bps_mean | long | -0.0134048 | 11 | 4 | 0.886719 | 7.30994e-05 | False |
| m_spread_bps_mean | short | 0.00298607 | 11 | 4 | 0.886719 | 7.30994e-05 | False |
| m_spread_bps_max | r45_bps | 0.0289189 | 11 | 5 | 0.725586 | 7.30994e-05 | False |
| m_spread_bps_max | long | 0.044666 | 11 | 6 | 0.5 | 7.30994e-05 | False |
| m_spread_bps_max | short | -0.00300259 | 11 | 5 | 0.725586 | 7.30994e-05 | False |
| m_spread_bps_std | r45_bps | 0.0289626 | 11 | 4 | 0.886719 | 7.30994e-05 | False |
| m_spread_bps_std | long | 0.044095 | 11 | 6 | 0.5 | 7.30994e-05 | False |
| m_spread_bps_std | short | 0.00264834 | 11 | 8 | 0.113281 | 7.30994e-05 | False |
| m_top_imbalance_mean | r45_bps | 0.00583768 | 11 | 6 | 0.5 | 7.30994e-05 | False |
| m_top_imbalance_mean | long | 0.00872138 | 11 | 7 | 0.274414 | 7.30994e-05 | False |
| m_top_imbalance_mean | short | -0.0132677 | 11 | 7 | 0.274414 | 7.30994e-05 | False |
| m_quote_update_count | r45_bps | 0.0162047 | 11 | 2 | 0.994141 | 7.30994e-05 | False |
| m_quote_update_count | long | 0.0292877 | 11 | 4 | 0.886719 | 7.30994e-05 | False |
| m_quote_update_count | short | 0.00892258 | 11 | 7 | 0.274414 | 7.30994e-05 | False |
| m_trade_valid | r45_bps | 0.00156077 | 0 | 0 |  | 7.30994e-05 | False |
| m_trade_valid | long | -0.00826009 | 0 | 0 |  | 7.30994e-05 | False |
| m_trade_valid | short | -0.0127767 | 0 | 0 |  | 7.30994e-05 | False |
| m_trade_count | r45_bps | 0.0172958 | 36 | 20 | 0.30886 | 7.30994e-05 | False |
| m_trade_count | long | 0.0264289 | 36 | 24 | 0.0326227 | 7.30994e-05 | False |
| m_trade_count | short | 0.0130608 | 36 | 20 | 0.30886 | 7.30994e-05 | False |
| m_mean_trade_size | r45_bps | 0.00638039 | 36 | 16 | 0.797484 | 7.30994e-05 | False |
| m_mean_trade_size | long | -0.00287973 | 36 | 22 | 0.121492 | 7.30994e-05 | False |
| m_mean_trade_size | short | -0.0165083 | 36 | 16 | 0.797484 | 7.30994e-05 | False |
| m_taker_buy_share | r45_bps | -0.00466729 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_taker_buy_share | long | -0.00163703 | 36 | 21 | 0.202516 | 7.30994e-05 | False |
| m_taker_buy_share | short | 0.00865733 | 36 | 20 | 0.30886 | 7.30994e-05 | False |
| m_trade_count_surge | r45_bps | 0.000211532 | 36 | 14 | 0.933751 | 7.30994e-05 | False |
| m_trade_count_surge | long | 0.00456853 | 36 | 17 | 0.69114 | 7.30994e-05 | False |
| m_trade_count_surge | short | 0.00764712 | 36 | 19 | 0.43397 | 7.30994e-05 | False |
| m_big_trade_share | r45_bps | -0.0241909 | 36 | 26 | 0.00566549 | 7.30994e-05 | False |
| m_big_trade_share | long | -0.0180917 | 36 | 25 | 0.0144084 | 7.30994e-05 | False |
| m_big_trade_share | short | 0.0158434 | 36 | 23 | 0.0662491 | 7.30994e-05 | False |

## predictions.parquet

행 27,502 × 열 11

2,000행 초과라 인라인하지 않음. 열: pilot_fold, signal_index, open_time, r45_bps, cls, p_short, p_none, p_long, n_train, selection_mode, n_selected

## selection.parquet

행 19,452 × 열 4

2,000행 초과라 인라인하지 않음. 열: pilot_fold, feature, selection_mode, selection_rank
