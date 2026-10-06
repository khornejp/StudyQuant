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
next_funding_rate,float64,float64,0.0,0,abs<=1e-9
oi_change_rate_15m,float64,float64,0.0,0,abs<=1e-9
oi_change_rate_30m,float64,float64,0.0,0,abs<=1e-9
oi_change_rate_45m,float64,float64,0.0,0,abs<=1e-9
oi_change_rate_5m,float64,float64,0.0,0,abs<=1e-9
oi_change_rate_60m,float64,float64,0.0,0,abs<=1e-9
oi_value_zscore_1d,float64,float64,0.0,0,abs<=1e-9
oi_zscore_1d,float64,float64,0.0,0,abs<=1e-9
outside_bar_flag,float64,float64,0.0,0,abs<=1e-9
parkinson_vol_20,float64,float64,0.0,0,abs<=1e-9
premium_index,float64,float64,0.0,0,abs<=1e-9
prev_horizon_trend,float64,float64,0.0,0,abs<=1e-9
price_vs_rolling_vwap_20,float64,float64,0.0,0,abs<=1e-9
price_vs_rolling_vwap_60,float64,float64,0.0,0,abs<=1e-9
quote_volume_sma_20_ratio,float64,float64,0.0,0,abs<=1e-9
range_position_20,float64,float64,0.0,0,abs<=1e-9
range_sma_20_ratio,float64,float64,0.0,0,abs<=1e-9
range_vol_20,float64,float64,0.0,0,abs<=1e-9
range_zscore_20,float64,float64,0.0,0,abs<=1e-9
regime_prob_down,float64,float64,0.0,0,abs<=1e-9
regime_prob_range,float64,float64,0.0,0,abs<=1e-9
regime_prob_up,float64,float64,0.0,0,abs<=1e-9
repaired_flag,float64,float64,0.0,0,abs<=1e-9
return_1,float64,float64,0.0,0,abs<=1e-9
return_10,float64,float64,0.0,0,abs<=1e-9
return_10_vol_adj,float64,float64,0.0,0,abs<=1e-9
return_15,float64,float64,0.0,0,abs<=1e-9
return_15m,float64,float64,0.0,0,abs<=1e-9
return_1_vol_adj,float64,float64,0.0,0,abs<=1e-9
return_1h,float64,float64,0.0,0,abs<=1e-9
return_24h,float64,float64,0.0,0,abs<=1e-9
return_3,float64,float64,0.0,0,abs<=1e-9
return_30,float64,float64,0.0,0,abs<=1e-9
return_30_vol_adj,float64,float64,0.0,0,abs<=1e-9
return_45,float64,float64,0.0,0,abs<=1e-9
return_45m,float64,float64,0.0,0,abs<=1e-9
return_4h,float64,float64,0.0,0,abs<=1e-9
return_5,float64,float64,0.0,0,abs<=1e-9
return_5_vol_adj,float64,float64,0.0,0,abs<=1e-9
return_60,float64,float64,0.0,0,abs<=1e-9
rolling_high_breakout_24h,float64,float64,0.0,0,abs<=1e-9
rolling_low_breakdown_24h,float64,float64,0.0,0,abs<=1e-9
rolling_return_max_20,float64,float64,0.0,0,abs<=1e-9
rolling_return_min_20,float64,float64,0.0,0,abs<=1e-9
rsi_14,float64,float64,0.0,0,abs<=1e-9
rsi_15m,float64,float64,0.0,0,abs<=1e-9
rsi_1h,float64,float64,0.0,0,abs<=1e-9
rsi_45m,float64,float64,0.0,0,abs<=1e-9
rsi_4h,float64,float64,0.0,0,abs<=1e-9
rsi_7,float64,float64,0.0,0,abs<=1e-9
rv_120,float64,float64,0.0,0,abs<=1e-9
rv_15,float64,float64,0.0,0,abs<=1e-9
rv_30,float64,float64,0.0,0,abs<=1e-9
rv_45,float64,float64,0.0,0,abs<=1e-9
rv_5,float64,float64,0.0,0,abs<=1e-9
rv_60,float64,float64,0.0,0,abs<=1e-9
rv_zscore_60,float64,float64,0.0,0,abs<=1e-9
session_asia,float64,float64,0.0,0,abs<=1e-9
session_europe,float64,float64,0.0,0,abs<=1e-9
session_overlap,float64,float64,0.0,0,abs<=1e-9
session_us,float64,float64,0.0,0,abs<=1e-9
sma_20_60_spread,float64,float64,0.0,0,abs<=1e-9
sma_5_20_spread,float64,float64,0.0,0,abs<=1e-9
sma_spread_vol_adj,float64,float64,0.0,0,abs<=1e-9
taker_imbalance,float64,float64,0.0,0,abs<=1e-9
taker_imbalance_vol_adj,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio_change_15m,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio_change_30m,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio_change_45m,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio_change_5m,float64,float64,0.0,0,abs<=1e-9
taker_ls_ratio_change_60m,float64,float64,0.0,0,abs<=1e-9
taker_quote_ratio,float64,float64,0.0,0,abs<=1e-9
taker_ratio,float64,float64,0.0,0,abs<=1e-9
trade_count_ratio,float64,float64,0.0,0,abs<=1e-9
trade_count_zscore_20,float64,float64,0.0,0,abs<=1e-9
trade_count_zscore_20_vol_adj,float64,float64,0.0,0,abs<=1e-9
trend_slope_10,float64,float64,0.0,0,abs<=1e-9
trend_slope_15m,float64,float64,0.0,0,abs<=1e-9
trend_slope_1h,float64,float64,0.0,0,abs<=1e-9
trend_slope_24h,float64,float64,0.0,0,abs<=1e-9
trend_slope_30,float64,float64,0.0,0,abs<=1e-9
trend_slope_45m,float64,float64,0.0,0,abs<=1e-9
trend_slope_4h,float64,float64,0.0,0,abs<=1e-9
upper_shadow,float64,float64,0.0,0,abs<=1e-9
volatility_regime_60,float64,float64,0.0,0,abs<=1e-9
volume_per_trade,float64,float64,0.0,0,abs<=1e-9
volume_regime_60,float64,float64,0.0,0,abs<=1e-9
volume_shock_20,float64,float64,0.0,0,abs<=1e-9
volume_sma_20_ratio,float64,float64,0.0,0,abs<=1e-9
volume_sma_5_ratio,float64,float64,0.0,0,abs<=1e-9
volume_sma_60_ratio,float64,float64,0.0,0,abs<=1e-9
volume_z_15m,float64,float64,0.0,0,abs<=1e-9
volume_z_1h,float64,float64,0.0,0,abs<=1e-9
volume_z_45m,float64,float64,0.0,0,abs<=1e-9
volume_z_4h,float64,float64,0.0,0,abs<=1e-9
volume_zscore_20,float64,float64,0.0,0,abs<=1e-9
volume_zscore_20_vol_adj,float64,float64,0.0,0,abs<=1e-9
volume_zscore_5,float64,float64,0.0,0,abs<=1e-9
vwap_deviation_zscore,float64,float64,0.0,0,abs<=1e-9
weekend_flag,float64,float64,0.0,0,abs<=1e-9
weekly_drawdown,float64,float64,0.0,0,abs<=1e-9
weekly_ma20_above_ma50,float64,float64,0.0,0,abs<=1e-9
weekly_ma20_slope_closed,float64,float64,0.0,0,abs<=1e-9
weekly_ma50_slope_closed,float64,float64,0.0,0,abs<=1e-9
weekly_vol_contraction,float64,float64,0.0,0,abs<=1e-9
wick_imbalance,float64,float64,0.0,0,abs<=1e-9
