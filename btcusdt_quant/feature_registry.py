from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FeatureDefinition:
    feature_name: str
    category: str
    feature_group: str
    formula: str
    lookback: int
    min_samples: int
    warmup_rule: str
    dependencies: tuple[str, ...]
    source: str
    required_for_training: bool
    required_for_live: bool
    leakage_risk: str
    scaffold_status: str


PRICE_RETURN = "price_return_features"
TREND_MA = "trend_ma_features"
VOLATILITY = "volatility_features"
VOLUME_FLOW = "volume_trade_flow_features"
CANDLE_STRUCTURE = "candle_structure_features"
GAP_QUALITY = "gap_data_quality_features"
REGIME_NORMALIZATION = "regime_normalization_features"
VOL_ADJUSTED_RETURNS = "volatility_adjusted_return_features"
VOL_ADJUSTED_TREND = "volatility_adjusted_trend_features"
VOL_ADJUSTED_FLOW = "volatility_adjusted_candle_flow_features"
MICROSTRUCTURE = "microstructure_features"
EXCHANGE_SAFETY = "exchange_funding_safety_features"
HIGHER_TIMEFRAME = "higher_timeframe_features"
TIME_SESSION = "time_session_features"
MOMENTUM_INDICATORS = "momentum_indicator_features"


def _feature(
    feature_name: str,
    category: str,
    feature_group: str,
    formula: str,
    lookback: int,
    min_samples: int,
    source: str,
    dependencies: tuple[str, ...] = (),
    warmup_rule: str = "strict",
    required_for_training: bool = True,
    required_for_live: bool = True,
    leakage_risk: str = "low_past_only",
    scaffold_status: str = "implemented",
) -> FeatureDefinition:
    return FeatureDefinition(
        feature_name=feature_name,
        category=category,
        feature_group=feature_group,
        formula=formula,
        lookback=lookback,
        min_samples=min_samples,
        warmup_rule=warmup_rule,
        dependencies=dependencies,
        source=source,
        required_for_training=required_for_training,
        required_for_live=required_for_live,
        leakage_risk=leakage_risk,
        scaffold_status=scaffold_status,
    )


FEATURE_DEFINITIONS: list[FeatureDefinition] = [
    _feature("return_1", "F01", PRICE_RETURN, "close_t / close_t-1 - 1", 2, 2, "klines_1m"),
    _feature("return_3", "F01", PRICE_RETURN, "close_t / close_t-3 - 1", 4, 4, "klines_1m"),
    _feature("return_5", "F01", PRICE_RETURN, "close_t / close_t-5 - 1", 6, 6, "klines_1m"),
    _feature("return_10", "F01", PRICE_RETURN, "close_t / close_t-10 - 1", 11, 11, "klines_1m"),
    _feature("return_15", "F01", PRICE_RETURN, "close_t / close_t-15 - 1", 16, 16, "klines_1m"),
    _feature("return_30", "F01", PRICE_RETURN, "close_t / close_t-30 - 1", 31, 31, "klines_1m"),
    _feature("return_60", "F01", PRICE_RETURN, "close_t / close_t-60 - 1", 61, 61, "klines_1m"),
    _feature("log_return_1", "F01", PRICE_RETURN, "ln(close_t / close_t-1)", 2, 2, "klines_1m"),
    _feature("log_return_5", "F01", PRICE_RETURN, "ln(close_t / close_t-5)", 6, 6, "klines_1m"),
    _feature("momentum_10", "F01", PRICE_RETURN, "close_t / close_t-10 - 1", 11, 11, "klines_1m"),
    _feature("momentum_30", "F01", PRICE_RETURN, "close_t / close_t-30 - 1", 31, 31, "klines_1m"),
    _feature("rolling_return_max_20", "F01", PRICE_RETURN, "max(return_1 over last 20 completed bars ending at t)", 21, 21, "klines_1m", ("return_1",)),
    _feature("rolling_return_min_20", "F01", PRICE_RETURN, "min(return_1 over last 20 completed bars ending at t)", 21, 21, "klines_1m", ("return_1",)),
    _feature("close_sma_5_ratio", "F02", TREND_MA, "close_t / SMA(close,5) - 1", 5, 5, "klines_1m"),
    _feature("close_sma_10_ratio", "F02", TREND_MA, "close_t / SMA(close,10) - 1", 10, 10, "klines_1m"),
    _feature("close_sma_20_ratio", "F02", TREND_MA, "close_t / SMA(close,20) - 1", 20, 20, "klines_1m"),
    _feature("close_sma_60_ratio", "F02", TREND_MA, "close_t / SMA(close,60) - 1", 60, 60, "klines_1m"),
    _feature("close_ema_12_ratio", "F02", TREND_MA, "close_t / EMA(close,12) - 1", 12, 12, "klines_1m"),
    _feature("close_ema_26_ratio", "F02", TREND_MA, "close_t / EMA(close,26) - 1", 26, 26, "klines_1m"),
    _feature("ema_12_26_spread", "F02", TREND_MA, "(EMA(close,12) - EMA(close,26)) / close_t", 26, 26, "klines_1m", ("close_ema_12_ratio", "close_ema_26_ratio")),
    _feature("sma_5_20_spread", "F02", TREND_MA, "(SMA(close,5) - SMA(close,20)) / close_t", 20, 20, "klines_1m", ("close_sma_5_ratio", "close_sma_20_ratio")),
    _feature("sma_20_60_spread", "F02", TREND_MA, "(SMA(close,20) - SMA(close,60)) / close_t", 60, 60, "klines_1m", ("close_sma_20_ratio", "close_sma_60_ratio")),
    _feature("trend_slope_10", "F02", TREND_MA, "linear_regression_slope(close,last 10 bars) / close_t", 10, 10, "klines_1m"),
    _feature("trend_slope_30", "F02", TREND_MA, "linear_regression_slope(close,last 30 bars) / close_t", 30, 30, "klines_1m"),
    _feature("distance_to_high_20", "F02", TREND_MA, "close_t / max(high,last 20 bars) - 1", 20, 20, "klines_1m"),
    _feature("distance_to_low_20", "F02", TREND_MA, "close_t / min(low,last 20 bars) - 1", 20, 20, "klines_1m"),
    _feature("prev_horizon_trend", "F02", TREND_MA, "+1 if close_t-1 > close_t-15 * 1.001 else -1 if close_t-1 < close_t-15 * 0.999 else 0", 16, 16, "klines_1m"),
    _feature("rv_5", "F03", VOLATILITY, "stddev(1m returns over 5 bars ending at t)", 6, 6, "klines_1m", ("return_1",)),
    _feature("rv_15", "F03", VOLATILITY, "stddev(1m returns over 15 bars ending at t)", 16, 16, "klines_1m", ("return_1",)),
    _feature("rv_30", "F03", VOLATILITY, "stddev(1m returns over 30 bars ending at t)", 31, 31, "klines_1m", ("return_1",)),
    _feature("rv_60", "F03", VOLATILITY, "stddev(1m returns over 60 bars ending at t)", 61, 61, "klines_1m", ("return_1",)),
    _feature("rv_120", "F03", VOLATILITY, "stddev(1m returns over 120 bars ending at t)", 121, 121, "klines_1m", ("return_1",)),
    _feature("atr_pct", "F03", VOLATILITY, "SMA(true_range,14) / close_t", 15, 15, "klines_1m"),
    _feature("atr_pct_30", "F03", VOLATILITY, "SMA(true_range,30) / close_t", 31, 31, "klines_1m"),
    _feature("parkinson_vol_20", "F03", VOLATILITY, "sqrt(mean(ln(high/low)^2,last 20 bars) / (4*ln(2)))", 20, 20, "klines_1m"),
    _feature("garman_klass_vol_20", "F03", VOLATILITY, "sqrt(mean(0.5*ln(high/low)^2 - (2*ln(2)-1)*ln(close/open)^2,last 20 bars))", 20, 20, "klines_1m"),
    _feature("range_vol_20", "F03", VOLATILITY, "stddev((high-low)/close over last 20 bars)", 20, 20, "klines_1m", ("high_low_range",)),
    _feature("har_rv_short", "F03", VOLATILITY, "rv_5 component for HAR volatility state at t", 6, 6, "klines_1m", ("rv_5",)),
    _feature("har_rv_medium", "F03", VOLATILITY, "rv_30 component for HAR volatility state at t", 31, 31, "klines_1m", ("rv_30",)),
    _feature("har_rv_long", "F03", VOLATILITY, "rv_120 component for HAR volatility state at t", 121, 121, "klines_1m", ("rv_120",)),
    _feature("volume_sma_5_ratio", "F04", VOLUME_FLOW, "volume_t / max(SMA(volume,5), 1e-12) - 1", 5, 5, "klines_1m"),
    _feature("volume_sma_20_ratio", "F04", VOLUME_FLOW, "volume_t / max(SMA(volume,20), 1e-12) - 1", 20, 20, "klines_1m"),
    _feature("volume_sma_60_ratio", "F04", VOLUME_FLOW, "volume_t / max(SMA(volume,60), 1e-12) - 1", 60, 60, "klines_1m"),
    _feature("quote_volume_sma_20_ratio", "F04", VOLUME_FLOW, "quote_volume_t / max(SMA(quote_volume,20), 1e-12) - 1", 20, 20, "klines_1m"),
    _feature("taker_ratio", "F04", VOLUME_FLOW, "taker_buy_base_volume_t / max(volume_t, 1e-12)", 1, 1, "klines_1m"),
    _feature("taker_imbalance", "F04", VOLUME_FLOW, "(taker_buy_base_volume_t - sell_base_volume_t) / max(volume_t, 1e-12)", 1, 1, "klines_1m", ("taker_ratio",)),
    _feature("taker_quote_ratio", "F04", VOLUME_FLOW, "taker_buy_quote_volume_t / max(quote_volume_t, 1e-12)", 1, 1, "klines_1m"),
    _feature("trade_count_ratio", "F04", VOLUME_FLOW, "number_of_trades_t / max(SMA(number_of_trades,20), 1e-12) - 1", 20, 20, "klines_1m"),
    _feature("trade_count_zscore_20", "F04", VOLUME_FLOW, "(number_of_trades_t - SMA(number_of_trades,20)) / stddev(number_of_trades,20)", 20, 20, "klines_1m"),
    _feature("volume_per_trade", "F04", VOLUME_FLOW, "volume_t / max(number_of_trades_t, 1)", 1, 1, "klines_1m"),
    _feature("quote_volume_per_trade", "F04", VOLUME_FLOW, "quote_volume_t / max(number_of_trades_t, 1)", 1, 1, "klines_1m"),
    _feature("volume_shock_20", "F04", VOLUME_FLOW, "(volume_t - SMA(volume,20)) / stddev(volume,20)", 20, 20, "klines_1m", ("volume_zscore_20",)),
    _feature("high_low_range", "F05", CANDLE_STRUCTURE, "(high_t - low_t) / close_t", 1, 1, "klines_1m"),
    _feature("body_pct", "F05", CANDLE_STRUCTURE, "abs(close_t - open_t) / close_t", 1, 1, "klines_1m"),
    _feature("upper_shadow", "F05", CANDLE_STRUCTURE, "max(0, high_t - max(open_t, close_t)) / close_t", 1, 1, "klines_1m"),
    _feature("lower_shadow", "F05", CANDLE_STRUCTURE, "max(0, min(open_t, close_t) - low_t) / close_t", 1, 1, "klines_1m"),
    _feature("close_location_value", "F05", CANDLE_STRUCTURE, "((close_t - low_t) - (high_t - close_t)) / max(high_t - low_t, 1e-12)", 1, 1, "klines_1m"),
    _feature("wick_imbalance", "F05", CANDLE_STRUCTURE, "(upper_shadow_raw_t - lower_shadow_raw_t) / max(high_t - low_t, 1e-12)", 1, 1, "klines_1m", ("upper_shadow", "lower_shadow")),
    _feature("body_to_range", "F05", CANDLE_STRUCTURE, "abs(close_t - open_t) / max(high_t - low_t, 1e-12)", 1, 1, "klines_1m"),
    _feature("range_sma_20_ratio", "F05", CANDLE_STRUCTURE, "(high_t-low_t) / max(SMA(high-low,20), 1e-12) - 1", 20, 20, "klines_1m"),
    _feature("inside_bar_flag", "F05", CANDLE_STRUCTURE, "1 if high_t <= high_t-1 and low_t >= low_t-1 else 0", 2, 2, "klines_1m"),
    _feature("outside_bar_flag", "F05", CANDLE_STRUCTURE, "1 if high_t >= high_t-1 and low_t <= low_t-1 else 0", 2, 2, "klines_1m"),
    _feature("gap_flag", "F06", GAP_QUALITY, "canonical gap flag at t", 1, 1, "klines_1m", warmup_rule="state"),
    _feature("gap_ratio_20", "F06", GAP_QUALITY, "rolling repaired candle ratio over last 20 canonical rows", 20, 1, "klines_1m", warmup_rule="state"),
    _feature("gap_ratio_60", "F06", GAP_QUALITY, "rolling repaired candle ratio over last 60 canonical rows", 60, 1, "klines_1m", warmup_rule="state"),
    _feature("gap_ratio_120", "F06", GAP_QUALITY, "rolling repaired candle ratio over last 120 canonical rows", 120, 1, "klines_1m", warmup_rule="state"),
    _feature("max_gap_run_120", "F06", GAP_QUALITY, "maximum contiguous repaired candle run over last 120 canonical rows", 120, 1, "klines_1m", warmup_rule="state"),
    _feature("repaired_flag", "F06", GAP_QUALITY, "1 if canonical candle at t was repaired else 0", 1, 1, "klines_1m", warmup_rule="state"),
    _feature("gap_length", "F06", GAP_QUALITY, "contiguous repaired candle run length at t", 1, 1, "klines_1m", warmup_rule="state"),
    _feature("canonical_gap_pressure", "F06", GAP_QUALITY, "gap_ratio_20 * (1 + max_gap_run_120) at t", 120, 1, "klines_1m", ("gap_ratio_20", "max_gap_run_120"), warmup_rule="state"),
    _feature("close_zscore_20", "F07", REGIME_NORMALIZATION, "(close_t - SMA(close,20)) / stddev(close,20)", 20, 20, "klines_1m"),
    _feature("close_zscore_60", "F07", REGIME_NORMALIZATION, "(close_t - SMA(close,60)) / stddev(close,60)", 60, 60, "klines_1m"),
    _feature("volume_zscore_5", "F07", REGIME_NORMALIZATION, "(volume_t - SMA(volume,5)) / stddev(volume,5)", 5, 5, "klines_1m"),
    _feature("volume_zscore_20", "F07", REGIME_NORMALIZATION, "(volume_t - SMA(volume,20)) / stddev(volume,20)", 20, 20, "klines_1m"),
    _feature("rv_zscore_60", "F07", REGIME_NORMALIZATION, "(rv_5_t - SMA(rv_5,60)) / stddev(rv_5,60)", 65, 65, "klines_1m", ("rv_5",)),
    _feature("range_zscore_20", "F07", REGIME_NORMALIZATION, "((high-low)/close_t - SMA(range_pct,20)) / stddev(range_pct,20)", 20, 20, "klines_1m", ("high_low_range",)),
    _feature("volatility_regime_60", "F07", REGIME_NORMALIZATION, "rv_15_t / max(SMA(rv_15,60), 1e-12) - 1", 75, 75, "klines_1m", ("rv_15",)),
    _feature("volume_regime_60", "F07", REGIME_NORMALIZATION, "volume_t / max(SMA(volume,60), 1e-12) - 1", 60, 60, "klines_1m"),
    _feature("return_1_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "return_1 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("return_1", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("return_5_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "return_5 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("return_5", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("return_10_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "return_10 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("return_10", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("return_30_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "return_30 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("return_30", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("momentum_10_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "momentum_10 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("momentum_10", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("momentum_30_vol_adj", "F08", VOL_ADJUSTED_RETURNS, "momentum_30 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", 121, 121, "klines_1m", ("momentum_30", "rv_15", "rv_60", "rv_120", "atr_pct")),
    _feature("close_zscore_20_vol_adj", "F09", VOL_ADJUSTED_TREND, "close_zscore_20 / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("close_zscore_20", "rv_60")),
    _feature("close_zscore_60_vol_adj", "F09", VOL_ADJUSTED_TREND, "close_zscore_60 / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("close_zscore_60", "rv_60")),
    _feature("ema_spread_vol_adj", "F09", VOL_ADJUSTED_TREND, "ema_12_26_spread / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("ema_12_26_spread", "rv_60")),
    _feature("sma_spread_vol_adj", "F09", VOL_ADJUSTED_TREND, "sma_20_60_spread / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("sma_20_60_spread", "rv_60")),
    _feature("candle_range_vol_adj", "F10", VOL_ADJUSTED_FLOW, "high_low_range / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("high_low_range", "rv_60")),
    _feature("body_pct_vol_adj", "F10", VOL_ADJUSTED_FLOW, "body_pct / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("body_pct", "rv_60")),
    _feature("volume_zscore_20_vol_adj", "F10", VOL_ADJUSTED_FLOW, "volume_zscore_20 / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("volume_zscore_20", "rv_60")),
    _feature("trade_count_zscore_20_vol_adj", "F10", VOL_ADJUSTED_FLOW, "trade_count_zscore_20 / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("trade_count_zscore_20", "rv_60")),
    _feature("taker_imbalance_vol_adj", "F10", VOL_ADJUSTED_FLOW, "taker_imbalance / max(rv_60, 1e-12)", 61, 61, "klines_1m", ("taker_imbalance", "rv_60")),
    _feature("spread", "F11", MICROSTRUCTURE, "(best_ask_t - best_bid_t) / mid_price_t", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("spread_bps", "F11", MICROSTRUCTURE, "10000 * (best_ask_t - best_bid_t) / mid_price_t", 1, 1, "depth_snapshot", ("spread",), warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("bid_ask_imbalance", "F11", MICROSTRUCTURE, "(best_bid_qty_t - best_ask_qty_t) / max(best_bid_qty_t + best_ask_qty_t, 1e-12)", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("best_bid_qty_ratio", "F11", MICROSTRUCTURE, "best_bid_qty_t / max(best_bid_qty_t + best_ask_qty_t, 1e-12)", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("best_ask_qty_ratio", "F11", MICROSTRUCTURE, "best_ask_qty_t / max(best_bid_qty_t + best_ask_qty_t, 1e-12)", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("microprice_deviation", "F11", MICROSTRUCTURE, "(microprice_t - mid_price_t) / mid_price_t", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("order_book_pressure", "F11", MICROSTRUCTURE, "(bid_qty - ask_qty) / max(bid_qty + ask_qty, 1e-12)", 1, 1, "depth_snapshot", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("adl_indicator", "F12", EXCHANGE_SAFETY, "exchange ADL quantile indicator observed at t", 1, 1, "adl_quantile", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("funding_rate", "F12", EXCHANGE_SAFETY, "current funding rate observed at t", 1, 1, "funding_rate", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("next_funding_rate", "F12", EXCHANGE_SAFETY, "announced next funding rate snapshot observed at t", 1, 1, "funding_rate", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("minutes_to_next_funding", "F12", EXCHANGE_SAFETY, "minutes until scheduled funding timestamp at t", 1, 1, "funding_rate", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("funding_blackout_active", "F12", EXCHANGE_SAFETY, "1 if t is inside configured funding blackout window else 0", 1, 1, "funding_rate", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("mark_price_basis", "F12", EXCHANGE_SAFETY, "(mark_price_t - close_t) / close_t", 1, 1, "mark_price_1m", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("premium_index", "F12", EXCHANGE_SAFETY, "exchange premium index observed at t", 1, 1, "premium_index_1m", warmup_rule="state", leakage_risk="low_state_snapshot"),
    _feature("leverage_bracket_utilization", "F12", EXCHANGE_SAFETY, "position notional_t / max(current leverage bracket cap_t, 1e-12)", 1, 1, "leverage_bracket", warmup_rule="state", leakage_risk="low_state_snapshot"),
    # F13: Higher Timeframe Features (Weekly)
    _feature("weekly_ma20_slope_closed", "F13", HIGHER_TIMEFRAME, "pct_change(SMA(weekly_close, 20))", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("weekly_ma50_slope_closed", "F13", HIGHER_TIMEFRAME, "pct_change(SMA(weekly_close, 50))", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("weekly_ma20_above_ma50", "F13", HIGHER_TIMEFRAME, "1 if SMA(weekly_close, 20) > SMA(weekly_close, 50) else 0", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("weekly_drawdown", "F13", HIGHER_TIMEFRAME, "weekly_close_t / cummax(weekly_close) - 1", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("weekly_vol_contraction", "F13", HIGHER_TIMEFRAME, "std(weekly_close, 20) / std(weekly_close, 50)", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("close_vs_weekly_ma20", "F13", HIGHER_TIMEFRAME, "current_close / SMA(weekly_close, 20) - 1", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("close_vs_weekly_ma50", "F13", HIGHER_TIMEFRAME, "current_close / SMA(weekly_close, 50) - 1", 5040, 5040, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    # F14: Time / Session Features
    _feature("hour", "F14", TIME_SESSION, "hour_of_day(open_time)", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("minute", "F14", TIME_SESSION, "minute_of_hour(open_time)", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("day_of_week", "F14", TIME_SESSION, "day_of_week(open_time)", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("session_asia", "F14", TIME_SESSION, "1 if hour in [0,1,2,3,4,5,6,7] else 0", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("session_europe", "F14", TIME_SESSION, "1 if hour in [8,9,10,11,12,13,14,15] else 0", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("session_us", "F14", TIME_SESSION, "1 if hour in [16,17,18,19,20,21,22,23] else 0", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("session_overlap", "F14", TIME_SESSION, "1 if hour in [8,9,10,11,12,13,14,15] else 0", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    _feature("weekend_flag", "F14", TIME_SESSION, "1 if day_of_week in [5,6] else 0", 1, 1, "klines_1m", warmup_rule="none", leakage_risk="none"),
    # F15: Momentum Indicators (RSI, MACD, Bollinger, VWAP)
    _feature("rsi_7", "F15", MOMENTUM_INDICATORS, "RSI(close, 7)", 8, 8, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("rsi_14", "F15", MOMENTUM_INDICATORS, "RSI(close, 14)", 15, 15, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("macd_line", "F15", MOMENTUM_INDICATORS, "EMA(close,12) - EMA(close,26)", 26, 26, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("macd_signal", "F15", MOMENTUM_INDICATORS, "EMA(macd_line, 9)", 35, 35, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("macd_hist", "F15", MOMENTUM_INDICATORS, "macd_line - macd_signal", 35, 35, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("bb_width_20", "F15", MOMENTUM_INDICATORS, "(BB_upper_20 - BB_lower_20) / BB_middle_20", 20, 20, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("bb_percent_b", "F15", MOMENTUM_INDICATORS, "(close - BB_lower_20) / (BB_upper_20 - BB_lower_20)", 20, 20, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("ema_5_slope", "F15", MOMENTUM_INDICATORS, "linear_regression_slope(EMA(close,5), last 5 bars)", 10, 10, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("ema_20_slope", "F15", MOMENTUM_INDICATORS, "linear_regression_slope(EMA(close,20), last 10 bars)", 30, 30, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("ema_60_slope", "F15", MOMENTUM_INDICATORS, "linear_regression_slope(EMA(close,60), last 10 bars)", 70, 70, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("rolling_vwap_20", "F15", MOMENTUM_INDICATORS, "cumulative(close*volume, 20) / cumulative(volume, 20)", 20, 20, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("rolling_vwap_60", "F15", MOMENTUM_INDICATORS, "cumulative(close*volume, 60) / cumulative(volume, 60)", 60, 60, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("price_vs_rolling_vwap_20", "F15", MOMENTUM_INDICATORS, "close / rolling_vwap_20 - 1", 20, 20, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
    _feature("price_vs_rolling_vwap_60", "F15", MOMENTUM_INDICATORS, "close / rolling_vwap_60 - 1", 60, 60, "klines_1m", warmup_rule="strict", leakage_risk="low_past_only"),
]


def _definition_dict(definition: FeatureDefinition) -> dict[str, object]:
    return {
        "feature_name": definition.feature_name,
        "category": definition.category,
        "feature_group": definition.feature_group,
        "formula": definition.formula,
        "lookback": definition.lookback,
        "min_samples": definition.min_samples,
        "warmup_rule": definition.warmup_rule,
        "dependencies": list(definition.dependencies),
        "source": definition.source,
        "required_for_training": definition.required_for_training,
        "required_for_live": definition.required_for_live,
        "leakage_risk": definition.leakage_risk,
        "scaffold_status": definition.scaffold_status,
    }


FEATURE_FORMULAS: tuple[dict[str, object], ...] = tuple(_definition_dict(definition) for definition in FEATURE_DEFINITIONS)


def active_feature_names(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> tuple[str, ...]:
    return tuple(definition.feature_name for definition in definitions if definition.scaffold_status != "pending_data_source")


def feature_formula_registry(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> dict[str, object]:
    rows = [_definition_dict(definition) for definition in definitions]
    return registry_from_feature_rows(rows)


def max_feature_min_samples(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> int:
    return max((definition.min_samples for definition in definitions), default=1)


def feature_dependency_graph(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> dict[str, object]:
    rows = [_definition_dict(definition) for definition in definitions]
    return dependency_graph_from_feature_rows(rows)


def features_by_source(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for definition in definitions:
        grouped.setdefault(definition.source, []).append(definition.feature_name)
    return grouped


def features_by_group(definitions: Sequence[FeatureDefinition] = FEATURE_DEFINITIONS) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for definition in definitions:
        grouped.setdefault(definition.feature_group, []).append(definition.feature_name)
    return grouped


def registry_from_feature_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    feature_rows = [dict(row) for row in rows]
    return {
        "features": feature_rows,
        "active_feature_names": [str(row["feature_name"]) for row in feature_rows if row.get("scaffold_status") != "pending_data_source"],
        "dependency_graph": dependency_graph_from_feature_rows(feature_rows),
        "features_by_source": _rows_by_key(feature_rows, "source"),
        "features_by_group": _rows_by_key(feature_rows, "feature_group"),
    }


def dependency_graph_from_feature_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    dependencies: dict[str, list[str]] = {}
    known = {str(row.get("feature_name", "")) for row in rows}
    for row in rows:
        name = str(row.get("feature_name", ""))
        raw_dependencies = row.get("dependencies", ())
        if isinstance(raw_dependencies, str):
            dependency_names = [raw_dependencies]
        else:
            dependency_names = [str(dependency) for dependency in raw_dependencies] if isinstance(raw_dependencies, Sequence) else []
        dependencies[name] = [dependency for dependency in dependency_names if dependency in known]
    order: list[str] = []
    temporary: set[str] = set()
    permanent: set[str] = set()
    cycle_found = False

    def visit(name: str) -> None:
        nonlocal cycle_found
        if name in permanent:
            return
        if name in temporary:
            cycle_found = True
            return
        temporary.add(name)
        for dependency in dependencies.get(name, []):
            visit(dependency)
        temporary.remove(name)
        permanent.add(name)
        order.append(name)

    for name in dependencies:
        visit(name)
    return {"acyclic": not cycle_found, "dependencies": dependencies, "calculation_order": order}


def _rows_by_key(rows: Sequence[Mapping[str, object]], key: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        group = str(row.get(key, "unknown"))
        grouped.setdefault(group, []).append(str(row.get("feature_name", "")))
    return grouped
