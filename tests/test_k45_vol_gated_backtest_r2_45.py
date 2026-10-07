from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from out import run_k45_vol_gated_backtest_r2_45 as r


def empty_funding() -> pd.DataFrame:
    frame = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns, UTC]"), "rate": pd.Series([], dtype=float)})
    frame.attrs["_time_ns"] = np.array([], dtype=np.int64)
    frame.attrs["_rates"] = np.array([], dtype=float)
    return frame


def tiny_market() -> pd.DataFrame:
    times = pd.date_range("2024-01-01", periods=61, freq="min", tz="UTC")
    price = np.linspace(100, 103, len(times))
    return pd.DataFrame({"open_time": times, "open": price, "high": price + .1, "low": price - .1, "close": price})


def tiny_signals(a2_first: int = 1) -> pd.DataFrame:
    return pd.DataFrame({
        "decision_time": pd.to_datetime(["2024-01-01 00:15Z", "2024-01-01 00:30Z"]),
        "E1-15": [0, 0], "A2-30": [a2_first, 0], "a2_exit_long": [False, True],
        "a2_exit_short": [False, False], "F3-30": [0, 0], "F3W-30": [0, 0],
    })


def test_causal_percentile_excludes_current_and_future():
    times = pd.date_range("2024-01-01", periods=5, freq="15min", tz="UTC")
    base = pd.Series([1., 2., 3., 4., 5.])
    got = r.causal_percentile(base, times, days=30, minimum_days=0)
    changed_current = r.causal_percentile(pd.Series([1., 2., 300., 4., 5.]), times, days=30, minimum_days=0)
    changed_future = r.causal_percentile(pd.Series([1., 2., 3., 400., 500.]), times, days=30, minimum_days=0)
    assert got[2] == changed_current[2]
    assert np.array_equal(got[:3], changed_future[:3], equal_nan=True)


def test_causal_percentile_requires_seven_day_warmup():
    times = pd.date_range("2024-01-01", periods=7 * 96 + 2, freq="15min", tz="UTC")
    got = r.causal_percentile(pd.Series(np.arange(len(times), dtype=float)), times)
    assert np.isnan(got[7 * 96 - 1])
    assert np.isfinite(got[7 * 96])


def test_gate_blocks_entry_but_not_exit_and_fill_is_t_plus_one():
    regimes = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:15Z", "2024-01-01 00:30Z"]), "M": [.9, np.nan], "L": [.5, np.nan]})
    trades = r.simulate_fast("B2_HIGH_ONLY", tiny_signals(), regimes, tiny_market(), empty_funding())
    assert len(trades) == 1
    assert trades.entry_time.iloc[0] == pd.Timestamp("2024-01-01 00:16Z")
    assert trades.exit_time.iloc[0] == pd.Timestamp("2024-01-01 00:31Z")
    assert trades.exit_reason.iloc[0] == "signal_exit"


def test_missing_detector_is_fail_closed():
    regimes = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:15Z", "2024-01-01 00:30Z"]), "M": [np.nan, np.nan], "L": [np.nan, np.nan]})
    trades = r.simulate_fast("B2_HIGH_ONLY", tiny_signals(), regimes, tiny_market(), empty_funding())
    assert trades.empty


def test_round_trip_cost_is_one_configured_bps_amount():
    raw = pd.DataFrame({"book": ["x"], "component": ["x"], "decision_time": [pd.Timestamp("2024-01-01T00:00Z")],
                        "entry_time": [pd.Timestamp("2024-01-01T00:01Z")], "exit_time": [pd.Timestamp("2024-01-01T00:02Z")],
                        "side": [1], "entry_price": [100.], "exit_price": [100.], "exit_reason": ["x"]})
    got = r.attach_funding(raw, empty_funding(), cost=4)
    assert got.net_bps.iloc[0] == -4
    assert got.cost_bps.iloc[0] == 4


def test_loading_regimes_does_not_write_detector_files():
    before = r.tree_record(r.PRED_ROOT, "fold_*_predictions.parquet")["tree_sha256"]
    frame = r.load_regimes()
    after = r.tree_record(r.PRED_ROOT, "fold_*_predictions.parquet")["tree_sha256"]
    assert len(frame) > 0
    assert before == after


def test_manifest_hash_freezes_configuration_but_allows_oos_field():
    value = {"rules": {"threshold": 2 / 3}, "OOS_result": None}
    digest = r.frozen_manifest_hash(value)
    value["manifest_sha256"] = digest
    value["OOS_result"] = {"winner": "B2"}
    assert r.frozen_manifest_hash(value) == digest
    value["rules"]["threshold"] = .75
    assert r.frozen_manifest_hash(value) != digest


def test_c1_x_reproduces_r2_39_dev_exactly():
    result = r.precheck_c1_x(write=False)
    assert result["passed"], json.dumps(result, ensure_ascii=False)
    assert result["dev_trade_n_actual"] == result["dev_trade_n_reference"]
    assert result["max_numeric_abs_diff"] <= 1e-10
