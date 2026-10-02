import numpy as np
import pandas as pd

from out import run_k45_classic_rules_r2_14 as r214
from out import run_k45_contrarian_robust_r2_17 as run


def test_quantiles_use_only_values_known_at_decision():
    source = pd.Series(np.arange(12.0))
    first = run.rolling_levels(source, bars_per_day=1, window_days=4, tail_pct=25)
    changed = source.copy()
    changed.iloc[8:] = 10_000
    second = run.rolling_levels(changed, bars_per_day=1, window_days=4, tail_pct=25)
    pd.testing.assert_frame_equal(first.iloc[:8], second.iloc[:8])


def test_r214_original_cells_reproduce():
    result = run.reproduce_original_cells()
    assert len(result) == 8
    assert result.match.all(), result.loc[~result.match].to_string(index=False)


def test_single_position_only():
    minutes = pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=20, freq="min", tz="UTC"),
        "open": np.arange(100.0, 120.0),
        "high": np.arange(101.0, 121.0),
        "low": np.arange(99.0, 119.0),
        "close": np.arange(100.5, 120.5),
        "volume": 1.0,
    })
    bars = r214.add_indicators(r214.aggregate_closed_ohlcv(minutes, 2))
    trades = run.execute_signals(minutes, bars, np.ones(len(bars), np.int8),
                                 np.zeros(len(bars), bool), np.zeros(len(bars), bool),
                                 max_hold_bars=2, funding=None)
    assert r214.max_concurrent(trades) <= 1


def test_median_return_exit_does_not_use_future_values():
    source = pd.Series([1, 2, 3, 9, 8, 7, 6, 5, 4, 3, 2, 1], dtype=float)
    first = run.contrarian_signals(source, bars_per_day=1, window_days=4,
                                   tail_pct=25, median_exit=True)
    changed = source.copy()
    changed.iloc[9:] = -99
    second = run.contrarian_signals(changed, bars_per_day=1, window_days=4,
                                    tail_pct=25, median_exit=True)
    for left, right in zip(first, second):
        np.testing.assert_array_equal(left[:9], right[:9])


def test_dev_ex2020_boundary_uses_entry_time():
    boundary = pd.Timestamp("2021-01-01", tz="UTC")
    trades = pd.DataFrame({
        "entry_time": [boundary - pd.Timedelta(minutes=1), boundary,
                       pd.Timestamp("2025-12-31 23:59", tz="UTC"),
                       pd.Timestamp("2026-01-01", tz="UTC")],
    })
    selected = run.segment_mask(trades, "DEV_EX2020")
    assert selected.tolist() == [False, True, True, False]
