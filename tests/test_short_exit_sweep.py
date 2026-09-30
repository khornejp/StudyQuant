import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.short_exit_sweep import first_touch_grid


def test_first_touch_grid_resolves_same_bar_by_candle_direction_and_timeout() -> None:
    times = pd.date_range("2021-01-01", periods=6, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "open_time": times,
        "open": [100.0, 100.2, 100.0, 100.0, 100.0, 100.0],
        "high": [100.0, 100.2, 100.0, 100.0, 100.0, 100.0],
        "low": [100.0, 99.8, 100.0, 100.0, 100.0, 100.0],
        "close": [100.0, 99.9, 100.0, 100.0, 100.0, 100.0],
    })
    result = first_touch_grid(
        frame, [0], [times[0]], np.asarray([True]), horizon=5, tp_bps=(10,), sl_bps=(10,),
    )[0]
    assert result["trades"] == 1
    assert result["mean_net_bps"] == pytest.approx(6.0)
    assert result["mean_holding_minutes"] == 1.0
    assert result["timeout_share"] == 0.0


def test_first_touch_grid_applies_round_trip_cost_on_timeout() -> None:
    times = pd.date_range("2021-01-01", periods=4, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "open_time": times, "open": [100.0] * 4, "high": [100.0] * 4,
        "low": [100.0] * 4, "close": [100.0] * 4,
    })
    result = first_touch_grid(
        frame, [0], [times[0]], np.asarray([True]), horizon=3, tp_bps=(10,), sl_bps=(10,),
    )[0]
    assert result["mean_net_bps"] == -4.0
    assert result["timeout_share"] == 1.0
    assert result["mean_holding_minutes"] == 3.0
