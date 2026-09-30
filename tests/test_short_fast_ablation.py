import numpy as np
import pandas as pd

from btcusdt_quant.short_fast_ablation import (
    FAST_DERIVATIVE_FEATURES,
    FAST_PRICE_FLOW_FEATURES,
    FEATURE_SETS,
    path_diagnostics,
)


def test_ablation_feature_sets_remove_slow_raw_context() -> None:
    slow = {"funding_rate", "premium_index", "rv_60", "ema_gap_15m", "rsi_15m", "return_24h"}
    assert len(FAST_PRICE_FLOW_FEATURES) == 27
    assert len(FAST_DERIVATIVE_FEATURES) == 31
    assert slow.isdisjoint(FAST_PRICE_FLOW_FEATURES)
    assert slow.isdisjoint(FAST_DERIVATIVE_FEATURES)
    assert set(FEATURE_SETS) == {"all_34", "fast_price_flow_27", "fast_plus_derivatives_31"}


def test_path_diagnostic_detects_intrawindow_profit_hidden_by_endpoint() -> None:
    times = pd.date_range("2021-01-01", periods=4, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "open_time": times,
        "open": [100.0, 100.0, 99.4, 100.0],
        "high": [100.0, 100.1, 99.8, 100.2],
        "low": [100.0, 99.2, 99.3, 99.9],
        "close": [100.0, 99.4, 99.7, 100.1],
    })
    report = path_diagnostics(frame, [0], [times[0]], np.asarray([True]), horizon=3)
    assert report["trades"] == 1
    assert report["mfe_above_4bps_share"] == 1.0
    assert report["endpoint_positive_after_cost_share"] == 0.0
    assert report["intrawindow_positive_but_endpoint_not_share"] == 1.0
    assert report["tp_0.6_sl_1.2_first_touch_mean_net_bps"] > 0.0
