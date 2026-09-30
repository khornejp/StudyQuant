import numpy as np
import pandas as pd

from btcusdt_quant.short_target_diagnostic import _select_trading_threshold, add_trend_features


def test_trend_features_are_causal_and_threshold_is_fail_closed() -> None:
    times = pd.date_range("2021-01-01", periods=3_000, freq="min", tz="UTC")
    close = 100.0 + np.sin(np.arange(len(times)) / 20.0)
    frame = pd.DataFrame({"open_time": times, "close": close})
    changed = frame.copy()
    changed.loc[2_000:, "close"] += 1_000.0
    before = add_trend_features(frame)
    after = add_trend_features(changed)
    names = ["return_60", "close_zscore_60", "ema_gap_15m", "rsi_15m", "return_24h"]
    np.testing.assert_allclose(before.loc[:1_999, names], after.loc[:1_999, names], equal_nan=True)

    predictions = np.linspace(-0.01, 0.01, 300)
    threshold, audit = _select_trading_threshold(times[:300], predictions, np.full(300, -0.01), 15)
    assert threshold is None
    assert audit["selected_threshold"] is None
