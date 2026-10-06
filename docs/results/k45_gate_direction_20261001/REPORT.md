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
    "funding_blackout_active",
    "mark_price_basis",
    "premium_index",
    "leverage_bracket_utilization",
    "weekly_ma20_slope_closed",
    "weekly_ma50_slope_closed",
    "weekly_ma20_above_ma50",
    "weekly_drawdown",
    "weekly_vol_contraction",
    "close_vs_weekly_ma20",
    "close_vs_weekly_ma50",
    "hour",
    "minute",
    "day_of_week",
    "session_asia",
    "session_europe",
    "session_us",
    "session_overlap",
    "weekend_flag",
    "rsi_7",
    "rsi_14",
    "bb_width_20",
    "bb_percent_b",
    "ema_5_slope",
    "ema_20_slope",
    "ema_60_slope",
    "price_vs_rolling_vwap_20",
    "price_vs_rolling_vwap_60",
    "range_position_20",
    "distance_to_range_high",
    "distance_to_range_low",
    "fake_break_low",
    "fake_break_high",
    "close_back_inside_range",
    "vwap_deviation_zscore",
    "bb_zscore",
    "oi_change_rate_5m",
    "oi_change_rate_15m",
    "oi_change_rate_30m",
    "oi_change_rate_45m",
    "oi_change_rate_60m",
    "oi_zscore_1d",
    "oi_value_zscore_1d",
    "global_ls_account",
    "taker_ls_ratio",
    "global_ls_account_change_5m",
    "global_ls_account_change_15m",
    "global_ls_account_change_30m",
    "global_ls_account_change_45m",
    "global_ls_account_change_60m",
    "taker_ls_ratio_change_5m",
    "taker_ls_ratio_change_15m",
    "taker_ls_ratio_change_30m",
    "taker_ls_ratio_change_45m",
    "taker_ls_ratio_change_60m",
    "global_ls_account_taker_ls_ratio_gap",
    "trend_slope_15m",
    "return_15m",
    "ema_gap_15m",
    "ma_slope_15m",
    "rsi_15m",
    "atr_pct_15m",
    "bb_width_15m",
    "adx_15m",
    "volume_z_15m",
    "trend_slope_45m",
    "return_45m",
    "ema_gap_45m",
    "ma_slope_45m",
    "rsi_45m",
    "atr_pct_45m",
    "bb_width_45m",
    "adx_45m",
    "volume_z_45m",
    "trend_slope_1h",
    "return_1h",
    "ema_gap_1h",
    "ma_slope_1h",
    "rsi_1h",
    "atr_pct_1h",
    "bb_width_1h",
    "adx_1h",
    "volume_z_1h",
    "trend_slope_4h",
    "return_4h",
    "ema_gap_4h",
    "ma_slope_4h",
    "rsi_4h",
    "atr_pct_4h",
    "bb_width_4h",
    "adx_4h",
    "volume_z_4h",
    "trend_slope_24h",
    "return_24h",
    "drawdown_from_24h_high",
    "distance_from_24h_high",
    "distance_from_24h_low",
    "rolling_high_breakout_24h",
    "rolling_low_breakdown_24h",
    "regime_prob_up",
    "regime_prob_range",
    "regime_prob_down"
  ],
  "registry_schema_sha256": "c980ed0878e9be3109c297aa5d709fd734f60b2f83dae57b52ad98ca2d2092ce",
  "missing_share_by_feature": {
    "trend_30d": 0.0,
    "trend_7d": 0.0,
    "ret_30d_bps": 0.0,
    "ret_7d_bps": 0.0,
    "f_return_1": 0.0,
    "f_return_3": 0.0,
    "f_return_5": 0.0,
    "f_return_10": 0.0,
    "f_return_15": 0.0,
    "f_return_30": 0.0,
    "f_return_45": 0.0,
    "f_return_60": 0.0,
    "f_log_return_1": 0.0,
    "f_log_return_5": 0.0,
    "f_momentum_10": 0.0,
    "f_momentum_30": 0.0,
    "f_rolling_return_max_20": 0.0,
    "f_rolling_return_min_20": 0.0,
    "f_close_sma_5_ratio": 0.0,
    "f_close_sma_10_ratio": 0.0,
    "f_close_sma_20_ratio": 0.0,
    "f_close_sma_60_ratio": 0.0,
    "f_close_ema_12_ratio": 0.0,
    "f_close_ema_26_ratio": 0.0,
    "f_ema_12_26_spread": 0.0,
    "f_sma_5_20_spread": 0.0,
    "f_sma_20_60_spread": 0.0,
    "f_trend_slope_10": 0.0,
    "f_trend_slope_30": 0.0,
    "f_distance_to_high_20": 0.0,
    "f_distance_to_low_20": 0.0,
    "f_prev_horizon_trend": 0.0,
    "f_rv_5": 0.0,
    "f_rv_15": 0.0,
    "f_rv_30": 0.0,
    "f_rv_45": 0.0,
    "f_rv_60": 0.0,
    "f_rv_120": 0.0,
    "f_atr_pct": 0.0,
    "f_atr_pct_30": 0.0,
    "f_atr_pct_45": 0.0,
    "f_parkinson_vol_20": 0.0,
    "f_garman_klass_vol_20": 0.0,
    "f_range_vol_20": 0.0,
    "f_har_rv_short": 0.0,
    "f_har_rv_medium": 0.0,
    "f_har_rv_long": 0.0,
    "f_volume_sma_5_ratio": 0.0,
    "f_volume_sma_20_ratio": 0.0,
    "f_volume_sma_60_ratio": 0.0,
    "f_quote_volume_sma_20_ratio": 0.0,
    "f_taker_ratio": 0.0,
    "f_taker_imbalance": 0.0,
    "f_taker_quote_ratio": 0.0,
    "f_trade_count_ratio": 0.0,
    "f_trade_count_zscore_20": 0.0,
    "f_volume_per_trade": 0.0,
    "f_volume_shock_20": 0.0,
    "f_high_low_range": 0.0,
    "f_body_pct": 0.0,
    "f_upper_shadow": 0.0,
    "f_lower_shadow": 0.0,
    "f_close_location_value": 0.0,
    "f_wick_imbalance": 0.0,
    "f_body_to_range": 0.0,
    "f_range_sma_20_ratio": 0.0,
    "f_inside_bar_flag": 0.0,
    "f_outside_bar_flag": 0.0,
    "f_gap_flag": 0.0,
    "f_gap_ratio_20": 0.0,
    "f_gap_ratio_60": 0.0,
    "f_gap_ratio_120": 0.0,
    "f_max_gap_run_120": 0.0,
    "f_repaired_flag": 0.0,
    "f_gap_length": 0.0,
    "f_canonical_gap_pressure": 0.0,
    "f_close_zscore_20": 0.0,
    "f_close_zscore_60": 0.0,
    "f_volume_zscore_5": 0.0,
    "f_volume_zscore_20": 0.0,
    "f_rv_zscore_60": 0.0,
    "f_range_zscore_20": 0.0,
    "f_volatility_regime_60": 0.0,
    "f_volume_regime_60": 0.0,
    "f_return_1_vol_adj": 0.0,
    "f_return_5_vol_adj": 0.0,
    "f_return_10_vol_adj": 0.0,
    "f_return_30_vol_adj": 0.0,
    "f_momentum_10_vol_adj": 0.0,
    "f_momentum_30_vol_adj": 0.0,
    "f_close_zscore_20_vol_adj": 0.0,
    "f_close_zscore_60_vol_adj": 0.0,
    "f_ema_spread_vol_adj": 0.0,
    "f_sma_spread_vol_adj": 0.0,
    "f_candle_range_vol_adj": 0.0,
    "f_body_pct_vol_adj": 0.0,
    "f_volume_zscore_20_vol_adj": 0.0,
    "f_trade_count_zscore_20_vol_adj": 0.0,
    "f_taker_imbalance_vol_adj": 0.0,
    "f_adl_indicator": 0.0,
    "f_funding_rate": 0.0,
    "f_next_funding_rate": 0.0,
    "f_minutes_to_next_funding": 0.0,
    "f_funding_blackout_active": 0.0,
    "f_mark_price_basis": 0.0,
    "f_premium_index": 0.0,
    "f_leverage_bracket_utilization": 0.0,
    "f_weekly_ma20_slope_closed": 0.0,
    "f_weekly_ma50_slope_closed": 0.0,
    "f_weekly_ma20_above_ma50": 0.0,
    "f_weekly_drawdown": 0.0,
    "f_weekly_vol_contraction": 0.0,
    "f_close_vs_weekly_ma20": 0.0,
    "f_close_vs_weekly_ma50": 0.0,
    "f_hour": 0.0,
    "f_minute": 0.0,
    "f_day_of_week": 0.0,
    "f_session_asia": 0.0,
    "f_session_europe": 0.0,
    "f_session_us": 0.0,
    "f_session_overlap": 0.0,
    "f_weekend_flag": 0.0,
    "f_rsi_7": 0.0,
    "f_rsi_14": 0.0,
    "f_bb_width_20": 0.0,
    "f_bb_percent_b": 0.0,
    "f_ema_5_slope": 0.0,
    "f_ema_20_slope": 0.0,
    "f_ema_60_slope": 0.0,
    "f_price_vs_rolling_vwap_20": 0.0,
    "f_price_vs_rolling_vwap_60": 0.0,
    "f_range_position_20": 0.0,
    "f_distance_to_range_high": 0.0,
    "f_distance_to_range_low": 0.0,
    "f_fake_break_low": 0.0,
    "f_fake_break_high": 0.0,
    "f_close_back_inside_range": 0.0,
    "f_vwap_deviation_zscore": 0.0,
    "f_bb_zscore": 0.0,
    "f_oi_change_rate_5m": 0.0,
    "f_oi_change_rate_15m": 0.0,
    "f_oi_change_rate_30m": 0.0,
    "f_oi_change_rate_45m": 0.0,
    "f_oi_change_rate_60m": 0.0,
    "f_oi_zscore_1d": 0.0,
    "f_oi_value_zscore_1d": 0.0,
    "f_global_ls_account": 0.0,
    "f_taker_ls_ratio": 0.0,
    "f_global_ls_account_change_5m": 0.0,
    "f_global_ls_account_change_15m": 0.0,
    "f_global_ls_account_change_30m": 0.0,
    "f_global_ls_account_change_45m": 0.0,
    "f_global_ls_account_change_60m": 0.0,
    "f_taker_ls_ratio_change_5m": 0.0,
    "f_taker_ls_ratio_change_15m": 0.0,
    "f_taker_ls_ratio_change_30m": 0.0,
    "f_taker_ls_ratio_change_45m": 0.0,
    "f_taker_ls_ratio_change_60m": 0.0,
    "f_global_ls_account_taker_ls_ratio_gap": 0.0,
    "f_trend_slope_15m": 0.0,
    "f_return_15m": 0.0,
    "f_ema_gap_15m": 0.0,
    "f_ma_slope_15m": 0.0,
    "f_rsi_15m": 0.0,
    "f_atr_pct_15m": 0.0,
    "f_bb_width_15m": 0.0,
    "f_adx_15m": 0.0,
    "f_volume_z_15m": 0.0,
    "f_trend_slope_45m": 0.0,
    "f_return_45m": 0.0,
    "f_ema_gap_45m": 0.0,
    "f_ma_slope_45m": 0.0,
    "f_rsi_45m": 0.0,
    "f_atr_pct_45m": 0.0,
    "f_bb_width_45m": 0.0,
    "f_adx_45m": 0.0,
    "f_volume_z_45m": 0.0,
    "f_trend_slope_1h": 0.0,
    "f_return_1h": 0.0,
    "f_ema_gap_1h": 0.0,
    "f_ma_slope_1h": 0.0,
    "f_rsi_1h": 0.0,
    "f_atr_pct_1h": 0.0,
    "f_bb_width_1h": 0.0,
    "f_adx_1h": 0.0,
    "f_volume_z_1h": 0.0,
    "f_trend_slope_4h": 0.0,
    "f_return_4h": 0.0,
    "f_ema_gap_4h": 0.0,
    "f_ma_slope_4h": 0.0,
    "f_rsi_4h": 0.0,
    "f_atr_pct_4h": 0.0,
    "f_bb_width_4h": 0.0,
    "f_adx_4h": 0.0,
    "f_volume_z_4h": 0.0,
    "f_trend_slope_24h": 0.0,
    "f_return_24h": 0.0,
    "f_drawdown_from_24h_high": 0.0,
    "f_distance_from_24h_high": 0.0,
    "f_distance_from_24h_low": 0.0,
    "f_rolling_high_breakout_24h": 0.0,
    "f_rolling_low_breakdown_24h": 0.0,
    "f_regime_prob_up": 0.0,
    "f_regime_prob_range": 0.0,
    "f_regime_prob_down": 0.0,
    "m_book_valid": 0.0,
    "m_book_imbalance_1pct": 0.36142085700259485,
    "m_book_imbalance_5pct": 0.36142085700259485,
    "m_book_depth_total": 0.36142085700259485,
    "m_book_slope_1_5": 0.36142085700259485,
    "m_book_depth_change_5m": 0.36142085700259485,
    "m_liquidity_valid": 0.0,
    "m_amihud_illiquidity": 0.3559856932463707,
    "m_amihud_surge": 0.3559856932463707,
    "m_kyle_lambda": 0.3559856932463707,
    "m_kyle_lambda_surge": 0.3559856932463707,
    "m_spread_valid": 0.0,
    "m_spread_bps_mean": 0.8325618907356757,
    "m_spread_bps_max": 0.8325618907356757,
    "m_spread_bps_std": 0.8325618907356757,
    "m_top_imbalance_mean": 0.8325618907356757,
    "m_quote_update_count": 0.8325618907356757,
    "m_trade_valid": 0.0,
    "m_trade_count": 0.3559856932463707,
    "m_mean_trade_size": 0.3559856932463707,
    "m_taker_buy_share": 0.3559856932463707,
    "m_trade_count_surge": 0.3559856932463707,
    "m_big_trade_share": 0.3559856932463707
  },
  "inputs": {
    "artifacts\\btcusdt_2020_2026h1.parquet": {
      "sha256": "6ad4dba7c55550e380426b4397b55dfbea3bcb318e37632971d82cad8cf6ada4",
      "mtime_utc": "2026-07-31T05:10:34.534496+00:00"
    },
    "out\\patchtst_backward_k45_validation_20260929\\ensemble_predictions.parquet": {
      "sha256": "4a892edec8361c1d44bbfa8851bc473539a1c5e200aea0f0e2cc8f41cdca29d8",
      "mtime_utc": "2026-09-29T10:10:37.210265+00:00"
    },
    "out\\patchtst_post_trigger_markout_20260929\\exploration_origins.parquet": {
      "sha256": "bb0172e74bee42d7585638b9f81cce3e2aabe2b4ef1e9e4b1591bf9dc90bf78e",
      "mtime_utc": "2026-09-29T04:57:42.716911+00:00"
    },
    "out\\patchtst_down_breakout_long_confirmation_20260929\\ensemble_predictions.parquet": {
      "sha256": "d5e81e9d7f58f070c173eed0ab62870566272e8d71e93cece4ac92fea53865c6",
      "mtime_utc": "2026-09-29T06:19:33.516301+00:00"
    },
    "artifacts\\book_features_1m.parquet": {
      "sha256": "ac742068deb446bd1f2fc62432e87c7df816040f2dbe65c6feb916cc715603eb",
      "mtime_utc": "2026-09-23T06:17:03.704799+00:00"
    },
    "artifacts\\liquidity_features_1m.parquet": {
      "sha256": "af66ff8dd9c6c02a86d50d84d0807453cc5a15539e04ede3a32eae9476daaa02",
      "mtime_utc": "2026-09-23T08:40:02.717260+00:00"
    },
    "artifacts\\spread_features_1m.parquet": {
      "sha256": "867aa7dce5adfe6930552383f35fc6fed3274024f58932432ccf72599f8877b3",
      "mtime_utc": "2026-09-23T05:08:13.491690+00:00"
    },
    "artifacts\\trade_features_1m.parquet": {
      "sha256": "968e24ef2b00718e55a6141b9b5f84c42c4aef9e0d03d572680155f792bd22a4",
      "mtime_utc": "2026-09-23T06:34:22.012191+00:00"
    }
  },
  "outputs": {
    "out\\k45_gate_direction_20261001\\dataset.parquet": {
      "sha256": "b099a66e6dce89c0c707fce3c3b5e1744248112fcbe3fdf942616ef27e8b260c",
      "rows": 28518
    }
  }
}
```

## Task 2

```json
{
  "run_started_utc": "2026-10-01T01:25:22.179632+00:00",
  "run_finished_utc": "2026-10-01T01:25:51.021007+00:00",
  "runtime_seconds": 28.840890899766237,
  "source": "out\\k45_gate_direction_20261001\\dataset.parquet",
  "source_sha256": "b099a66e6dce89c0c707fce3c3b5e1744248112fcbe3fdf942616ef27e8b260c",
  "data_cutoff_utc": "2026-06-30T23:59:00+00:00",
  "frozen_hypothesis": "On PatchTST-gated bars, CatBoost-chosen direction has positive net results for both LONG and SHORT after 4 bps round-trip cost.",
  "out_of_sample_result": "not_evaluated_dev_diagnostic_only",
  "local_data_only": true,
  "pnl_or_backtest_computed": false,
  "dev_rows": 25862,
  "n_features": 228,
  "bonferroni_alpha": 7.309941520467836e-05,
  "passing_features_by_target": {
    "r45_bps": 51,
    "long": 75,
    "short": 61
  },
  "top10_by_absolute_pooled_spearman": {
    "r45_bps": [
      {
        "feature": "f_distance_to_high_20",
        "pooled_spearman": -0.04845465071691475,
        "agree_months": 46,
        "n_months": 60,
        "p_one_sided": 2.1118522811339885e-05
      },
      {
        "feature": "f_distance_to_range_high",
        "pooled_spearman": -0.04845465071691475,
        "agree_months": 46,
        "n_months": 60,
        "p_one_sided": 2.1118522811339885e-05
      },
      {
        "feature": "f_sma_5_20_spread",
        "pooled_spearman": -0.04650165230433202,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_close_sma_60_ratio",
        "pooled_spearman": -0.04607924952207852,
        "agree_months": 50,
        "n_months": 60,
        "p_one_sided": 8.081907283078588e-08
      },
      {
        "feature": "f_close_zscore_60",
        "pooled_spearman": -0.04600564800857843,
        "agree_months": 51,
        "n_months": 60,
        "p_one_sided": 1.542517804719451e-08
      },
      {
        "feature": "f_return_15",
        "pooled_spearman": -0.04439226022211144,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_close_ema_26_ratio",
        "pooled_spearman": -0.044304219966045805,
        "agree_months": 51,
        "n_months": 60,
        "p_one_sided": 1.542517804719451e-08
      },
      {
        "feature": "f_ema_12_26_spread",
        "pooled_spearman": -0.044044703029205434,
        "agree_months": 49,
        "n_months": 60,
        "p_one_sided": 3.7806404911983754e-07
      },
      {
        "feature": "f_ema_20_slope",
        "pooled_spearman": -0.04372721188440376,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_price_vs_rolling_vwap_60",
        "pooled_spearman": -0.042646833892729094,
        "agree_months": 50,
        "n_months": 60,
        "p_one_sided": 8.081907283078588e-08
      }
    ],
    "long": [
      {
        "feature": "f_close_zscore_60",
        "pooled_spearman": -0.06912394862498344,
        "agree_months": 55,
        "n_months": 60,
        "p_one_sided": 5.191331739484717e-12
      },
      {
        "feature": "f_ema_spread_vol_adj",
        "pooled_spearman": -0.06772470240086191,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_close_sma_60_ratio",
        "pooled_spearman": -0.06504788241018104,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_ema_12_26_spread",
        "pooled_spearman": -0.06371780113802587,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_ema_20_slope",
        "pooled_spearman": -0.06199037263445513,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_ema_60_slope",
        "pooled_spearman": -0.06067000172542477,
        "agree_months": 55,
        "n_months": 60,
        "p_one_sided": 5.191331739484717e-12
      },
      {
        "feature": "f_rsi_14",
        "pooled_spearman": -0.06029244849674966,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_return_60",
        "pooled_spearman": -0.06024682586130884,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_return_45",
        "pooled_spearman": -0.06006332436397729,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_return_30_vol_adj",
        "pooled_spearman": -0.0600382174115193,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      }
    ],
    "short": [
      {
        "feature": "f_close_zscore_60",
        "pooled_spearman": 0.05945383629293952,
        "agree_months": 55,
        "n_months": 60,
        "p_one_sided": 5.191331739484717e-12
      },
      {
        "feature": "f_ema_spread_vol_adj",
        "pooled_spearman": 0.05640222790218387,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_close_sma_60_ratio",
        "pooled_spearman": 0.05555105222935982,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "m_book_imbalance_1pct",
        "pooled_spearman": -0.05441721034318886,
        "agree_months": 30,
        "n_months": 36,
        "p_one_sided": 3.480084706097841e-05
      },
      {
        "feature": "f_rsi_14",
        "pooled_spearman": 0.05342292323991746,
        "agree_months": 53,
        "n_months": 60,
        "p_one_sided": 3.8359591371384116e-10
      },
      {
        "feature": "f_ema_12_26_spread",
        "pooled_spearman": 0.053391019947623526,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_ema_20_slope",
        "pooled_spearman": 0.05285005243831557,
        "agree_months": 55,
        "n_months": 60,
        "p_one_sided": 5.191331739484717e-12
      },
      {
        "feature": "f_close_ema_26_ratio",
        "pooled_spearman": 0.05212113891716361,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_sma_5_20_spread",
        "pooled_spearman": 0.052088075978098544,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      },
      {
        "feature": "f_return_15",
        "pooled_spearman": 0.05144879328719274,
        "agree_months": 54,
        "n_months": 60,
        "p_one_sided": 4.8614808359492834e-11
      }
    ]
  },
  "outputs": {
    "out\\k45_gate_direction_20261001\\precheck.parquet": {
      "sha256": "283f6f9482c76ba36cbda279433529157a8590d28a535917634962a00548ba46",
      "rows": 684
    }
  }
}
```

## Task 3

```json
{
  "run_started_utc": "2026-10-01T01:28:41.690974+00:00",
  "run_finished_utc": "2026-10-01T01:51:09.262792+00:00",
  "runtime_seconds": 1347.5487883999012,
  "source": "out\\k45_gate_direction_20261001\\dataset.parquet",
  "source_sha256": "b099a66e6dce89c0c707fce3c3b5e1744248112fcbe3fdf942616ef27e8b260c",
  "market_source": "artifacts\\btcusdt_2020_2026h1.parquet",
  "market_source_sha256": "6ad4dba7c55550e380426b4397b55dfbea3bcb318e37632971d82cad8cf6ada4",
  "data_cutoff_utc": "2026-06-30T23:59:00+00:00",
  "frozen_hypothesis": "On PatchTST-gated bars, CatBoost-chosen direction has positive net results for both LONG and SHORT after 4 bps round-trip cost.",
  "out_of_sample_result": "not_evaluated_predictions_only",
  "local_data_only": true,
  "pnl_or_backtest_computed": false,
  "folds_total": 667,
  "folds_fitted": 621,
  "folds_skipped": 46,
  "skip_reason_counts": {
    "train_rows_below_1000": 15,
    "zero_test_rows": 31
  },
  "selection_mode_counts": {
    "FALLBACK": 198,
    "GATE": 423
  },
  "feature_candidate_count": 228,
  "catboost_params": {
    "loss_function": "MultiClass",
    "iterations": 500,
    "depth": 4,
    "learning_rate": 0.05,
    "l2_leaf_reg": 3,
    "random_seed": 20261001,
    "thread_count": -1,
    "verbose": false
  },
  "stop_start_rule": "market index of run_audit.test_bounds(fold)[0] minus 3 days",
  "train_rule": "signal_index + 45 < stop_start_index",
  "outputs": {
    "out\\k45_gate_direction_20261001\\predictions.parquet": {
      "sha256": "31b341e49c421aa9e104319505a2ed1cdc426d0f74a702cc91d1c4424a1b6cb8",
      "rows": 27502
    },
    "out\\k45_gate_direction_20261001\\selection.parquet": {
      "sha256": "b9c857f63513c789bdda90eceebe7d163cb8cb232e4576fdfa7fd49192e755b8",
      "rows": 19452
    },
    "out\\k45_gate_direction_20261001\\walkforward.log": {
      "sha256": "5e75144cbe7dc1cb834a400106767673c3789141fd8db66aacf48bb23bae98bd",
      "rows": 667
    }
  }
}
```

## Task 4

```json
{
  "run_started_utc": "2026-10-01T01:59:36.725044+00:00",
  "run_finished_utc": "2026-10-01T01:59:36.968066+00:00",
  "source": "out\\k45_gate_direction_20261001\\predictions.parquet",
  "source_sha256": "31b341e49c421aa9e104319505a2ed1cdc426d0f74a702cc91d1c4424a1b6cb8",
  "data_cutoff_utc": "2026-06-30T23:59:00+00:00",
  "frozen_hypothesis": "On PatchTST-gated bars, CatBoost-chosen direction has positive net results for both LONG and SHORT after 4 bps round-trip cost.",
  "out_of_sample_result": {
    "DEV": "PASS",
    "HOLD_B": "FAIL"
  },
  "local_data_only": true,
  "new_model_fits": 0,
  "score": "p_long - p_short",
  "ordering_gate": "monthly_sign_test p_one_sided < 0.05",
  "segments": {
    "DEV": {
      "rows": 24846,
      "ordering": {
        "pooled_spearman": 0.036287875484230285,
        "n_months": 58,
        "agree_months": 44,
        "p_one_sided": 5.024834963457403e-05,
        "pass": true
      },
      "pooled_spearman_p_long_vs_r45": 0.04075111207764132,
      "pooled_spearman_p_short_vs_negative_r45": 0.02924090403686438
    },
    "HOLD_B": {
      "rows": 2656,
      "ordering": {
        "pooled_spearman": 0.03595627574503214,
        "n_months": 6,
        "agree_months": 5,
        "p_one_sided": 0.109375,
        "pass": false
      },
      "pooled_spearman_p_long_vs_r45": 0.03868947271514949,
      "pooled_spearman_p_short_vs_negative_r45": 0.03175920064225056
    }
  },
  "outputs": {
    "out\\k45_gate_direction_20261001\\deciles.parquet": {
      "sha256": "d18734e7c1725781f02cab4922983261be19b89c00f95be309931f2979a4c0eb",
      "rows": 20
    },
    "out\\k45_gate_direction_20261001\\calibration.parquet": {
      "sha256": "13f2f7afc79075cf37faaeb039cb062ffaaaf87f90bf9bff921bc4ea58aaa418",
      "rows": 27
    }
  }
}
```

## Task 4 deciles

| segment | decile | n | score_mean | r_mean | long_share | short_share |
|---|---|---|---|---|---|---|
| DEV | 0 | 2485 | -0.18257092526674443 | 2.1081094673102743 | 0.4515090543259557 | 0.48329979879275653 |
| DEV | 1 | 2485 | -0.08738447984289538 | -0.6120340194433901 | 0.4301810865191147 | 0.49899396378269617 |
| DEV | 2 | 2484 | -0.04358812955518452 | 0.3049513361855624 | 0.44484702093397743 | 0.47020933977455714 |
| DEV | 3 | 2485 | -0.008681275118172653 | 0.2754995688045972 | 0.47002012072434607 | 0.46036217303822935 |
| DEV | 4 | 2484 | 0.022199489705450753 | -0.7811940168939103 | 0.4774557165861514 | 0.45692431561996777 |
| DEV | 5 | 2485 | 0.05102243444445792 | 0.37852612004534447 | 0.46277665995975853 | 0.4744466800804829 |
| DEV | 6 | 2484 | 0.08027096306038164 | 1.819104854099784 | 0.5052334943639292 | 0.4190821256038647 |
| DEV | 7 | 2485 | 0.11367783368231615 | -0.21274975276062907 | 0.48611670020120723 | 0.43661971830985913 |
| DEV | 8 | 2484 | 0.16029647703245514 | 1.9822730840011245 | 0.5185185185185185 | 0.4166666666666667 |
| DEV | 9 | 2485 | 0.29604125703640116 | 4.88606511936433 | 0.5138832997987928 | 0.4358148893360161 |
| HOLD_B | 0 | 266 | -0.13830556886200754 | 5.1204526761374805 | 0.4774436090225564 | 0.48872180451127817 |
| HOLD_B | 1 | 266 | -0.08170944837775121 | -5.4475479243221825 | 0.424812030075188 | 0.5 |
| HOLD_B | 2 | 265 | -0.0485515130529724 | -4.35572467168445 | 0.44150943396226416 | 0.5018867924528302 |
| HOLD_B | 3 | 266 | -0.01819453992296916 | 2.7498735156181953 | 0.45864661654135336 | 0.4774436090225564 |
| HOLD_B | 4 | 265 | 0.008288018809905644 | 2.447544773275957 | 0.4679245283018868 | 0.47547169811320755 |
| HOLD_B | 5 | 266 | 0.0334089414936793 | -3.9807924219963526 | 0.4699248120300752 | 0.45112781954887216 |
| HOLD_B | 6 | 265 | 0.05796754244866747 | 5.643502940991418 | 0.5018867924528302 | 0.4339622641509434 |
| HOLD_B | 7 | 266 | 0.08170498753667364 | -1.322142691484702 | 0.4774436090225564 | 0.47368421052631576 |
| HOLD_B | 8 | 265 | 0.11394610929659078 | 2.8421789405791955 | 0.49056603773584906 | 0.4226415094339623 |
| HOLD_B | 9 | 266 | 0.17633728153903408 | 7.116562311782185 | 0.5075187969924813 | 0.41729323308270677 |

## Task 4 calibration

| segment | side | bin | n | p_mean | hit_rate |
|---|---|---|---|---|---|
| DEV | LONG | 1 | 7 | 0.1911383974878392 | 0.2857142857142857 |
| DEV | LONG | 2 | 93 | 0.26461407480651744 | 0.3978494623655914 |
| DEV | LONG | 3 | 2120 | 0.37575851845201685 | 0.43254716981132074 |
| DEV | LONG | 4 | 12838 | 0.45551445507210625 | 0.46035207976320297 |
| DEV | LONG | 5 | 8383 | 0.5367498122775198 | 0.5043540498628176 |
| DEV | LONG | 6 | 1098 | 0.6334871846305077 | 0.52367941712204 |
| DEV | LONG | 7 | 275 | 0.7416291195823131 | 0.5018181818181818 |
| DEV | LONG | 8 | 31 | 0.8205481816652257 | 0.6774193548387096 |
| DEV | LONG | 9 | 1 | 0.9060702092874713 | 0.0 |
| DEV | SHORT | 0 | 1 | 0.07781372851646942 | 0.0 |
| DEV | SHORT | 1 | 76 | 0.17188290260018912 | 0.40789473684210525 |
| DEV | SHORT | 2 | 435 | 0.25917259718278557 | 0.42298850574712643 |
| DEV | SHORT | 3 | 4484 | 0.37078023774217084 | 0.43398751115075823 |
| DEV | SHORT | 4 | 15405 | 0.4486693140167476 | 0.4530347289840961 |
| DEV | SHORT | 5 | 4087 | 0.5303005181876591 | 0.4844629312454123 |
| DEV | SHORT | 6 | 312 | 0.6327126482966756 | 0.5160256410256411 |
| DEV | SHORT | 7 | 46 | 0.7382126459105571 | 0.6521739130434783 |
| HOLD_B | LONG | 3 | 174 | 0.3850389619253686 | 0.5 |
| HOLD_B | LONG | 4 | 1699 | 0.4555230845668086 | 0.4579164214243673 |
| HOLD_B | LONG | 5 | 762 | 0.5286581530258435 | 0.49606299212598426 |
| HOLD_B | LONG | 6 | 19 | 0.6230708412792263 | 0.47368421052631576 |
| HOLD_B | LONG | 7 | 2 | 0.735069735859561 | 0.5 |
| HOLD_B | SHORT | 2 | 3 | 0.25691224661603795 | 0.6666666666666666 |
| HOLD_B | SHORT | 3 | 279 | 0.3815662178885616 | 0.4265232974910394 |
| HOLD_B | SHORT | 4 | 1916 | 0.4493939768366448 | 0.4629436325678497 |
| HOLD_B | SHORT | 5 | 457 | 0.5233026315977864 | 0.49015317286652077 |
| HOLD_B | SHORT | 6 | 1 | 0.611052781530358 | 1.0 |

## Task 5

| segment | margin | n | net_mean_bps | trimmed_top2_mean_bps | long_n | long_net_mean_bps | short_n | short_net_mean_bps | monthly_positive_share | positive_months | months | year_net_mean_bps | trend_30d_net_mean_bps | pw_selector_status | pw_selector_error | pw_bootstrap_reps | pw_bootstrap_seed | pw_block_length_stationary | pw_p_one_sided | pw_ci95_lower_bps | pw_ci95_upper_bps | random_direction_n | random_direction_net_mean_bps | random_bar_matched_n | random_bar_matched_net_mean_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 0.0 | 10688 | -4.092254462533747 | -4.338842307612834 | 6528 | -3.4683982386789975 | 4160 | -5.0712288445827385 | 0.22413793103448276 | 13 | 58 | {"2021": 0.32037075953832084, "2022": -9.31549063825997, "2023": -4.359033855973619, "2024": -2.2373093066933847, "2025": -4.0805254801716275} | {"-1": -5.098103783584186, "1": -3.0901625166086353} | MEASURABLE |  | 20000 | 20260930 | 3.064943514567133 | 1.0 | -5.7506076478235295 | -2.445177931754042 | 10688 | -3.764199936653043 | 10688 | -4.1418926129018425 |
| DEV | 0.05 | 8765 | -4.028618416183971 | -4.329304304626565 | 5555 | -3.2052252230825373 | 3210 | -5.453524705180375 | 0.22413793103448276 | 13 | 58 | {"2021": 1.0104084498023187, "2022": -8.202324870951289, "2023": -4.47948619937048, "2024": -3.2588039996646336, "2025": -4.87671102291527} | {"-1": -3.643976851019455, "1": -4.408462864322625} | MEASURABLE |  | 20000 | 20260930 | 1.6391715412650858 | 1.0 | -5.72517644634243 | -2.336787358371785 | 10688 | -3.764199936653043 | 8765 | -3.206405059779087 |
| DEV | 0.1 | 6159 | -3.632852557790652 | -3.8781445875320752 | 4073 | -2.294542116326172 | 2086 | -6.245958228013484 | 0.29310344827586204 | 17 | 58 | {"2021": 1.3823686532694877, "2022": -6.639703001919388, "2023": -4.850633461751298, "2024": -5.071207900996557, "2025": -3.332185539511524} | {"-1": -2.570893670711485, "1": -4.671955278652568} | UNMEASURABLE | invalid Politis-White block length | 0 | 20260930 | nan | nan | nan | nan | 10688 | -3.764199936653043 | 6159 | -4.814610732267972 |
| DEV | 0.2 | 2147 | -1.4743264398021483 | -2.341318433491338 | 1600 | -1.2001324562575828 | 547 | -2.2763563733877157 | 0.4827586206896552 | 28 | 58 | {"2021": 0.6140399433130627, "2022": -4.475492203318828, "2023": -11.462698727430842, "2024": 1.0943224570426033, "2025": 4.085597711766135} | {"-1": 0.5463846324034323, "1": -3.796424849103457} | MEASURABLE |  | 20000 | 20260930 | 2.312534300193522 | 0.7580620968951552 | -5.722659782464767 | 2.75543605855439 | 10688 | -3.764199936653043 | 2147 | -6.527291872934151 |
| HOLD_B | 0.0 | 1124 | -3.461350228056325 | -4.082149458470894 | 658 | -2.747024111686783 | 466 | -4.46999096747941 | 0.3333333333333333 | 2 | 6 | {"2026": -3.461350228056324} | {"-1": -0.9040198077140057, "1": -6.317276667346333} | MEASURABLE |  | 20000 | 20260930 | 1.6266415918995998 | 0.9632018399080046 | -7.112609862656464 | 0.3284503435058439 | 1124 | -5.559870773829503 | 1124 | -6.045129842185367 |
| HOLD_B | 0.05 | 886 | 0.005676484781383909 | -1.2736836341595277 | 528 | 0.093855481244601 | 358 | -0.12437521949956114 | 0.5 | 3 | 6 | {"2026": 0.005676484781384262} | {"-1": 0.9207343896238397, "1": -0.9824142105884034} | MEASURABLE |  | 20000 | 20260930 | 1.7996540910709897 | 0.4934253287335633 | -4.9843372535496995 | 4.7619060689106245 | 1124 | -5.559870773829503 | 886 | -6.377025600601712 |
| HOLD_B | 0.1 | 524 | -4.74030986585246 | -5.90207452515966 | 325 | -1.731241020001016 | 199 | -9.654618282444016 | 0.16666666666666666 | 1 | 6 | {"2026": -4.74030986585246} | {"-1": -4.896035571192493, "1": -4.560231992599172} | MEASURABLE |  | 20000 | 20260930 | 1.5996314549364359 | 0.9218039098045098 | -11.066061637091853 | 1.914261836574922 | 1124 | -5.559870773829503 | 524 | -5.458395955619558 |
| HOLD_B | 0.2 | 65 | -5.033759850142289 | -16.340963725472914 | 50 | -4.958605805311663 | 15 | -5.284273332911034 | 0.5 | 3 | 6 | {"2026": -5.033759850142287} | {"-1": 2.8588086420585572, "1": -21.57057002427739} | MEASURABLE |  | 20000 | 20260930 | 3.8208660717694873 | 0.6655167241637918 | -27.85722329381031 | 16.68297989705271 | 1124 | -5.559870773829503 | 65 | -4.765629783089429 |

## Gates

```json
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
