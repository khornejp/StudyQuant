from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "out/run_k45_vol_detector_r2_44_window.py"
SPEC = importlib.util.spec_from_file_location("r244", SCRIPT)
r244 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r244
SPEC.loader.exec_module(r244)
CANDIDATES = {c["name"]: c for c in r244.CANDIDATES}


def minutes(days=40):
    times = pd.date_range("2024-01-01", periods=days * 1440, freq="1min", tz="UTC")
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(times))))
    return pd.DataFrame({"open_time": times, "close": close})


def test_threshold_uses_only_labels_ended_before_decision():
    origins = pd.date_range("2024-01-01", periods=120 * 96, freq="15min", tz="UTC")
    actual = np.random.default_rng(2).lognormal(3, .5, (len(origins), 15))
    base = r244.causal_thresholds(origins, actual)
    row = 100 * 96
    changed = actual.copy()
    # Labels of the 24h targets that end after origins[row] must not move its threshold.
    changed[row - 95:, 4] *= 50
    after = r244.causal_thresholds(origins, changed)
    assert np.allclose(base[:, row, 4], after[:, row, 4])
    changed[row - 2000:row - 200, 4] *= 50
    assert not np.allclose(base[:, row + 200, 4], r244.causal_thresholds(origins, changed)[:, row + 200, 4])
    assert np.isnan(base[:, 10, 0]).all()  # under half a 90-day window: no reference yet


def test_scale_is_past_only_and_horizon_scaled():
    frame = minutes()
    origin = pd.DatetimeIndex([frame.open_time.iloc[35 * 1440]])
    base = r244.scale_bps(frame, origin)[0]
    future = frame.copy()
    future.loc[35 * 1440:, "close"] *= 2
    assert np.allclose(base, r244.scale_bps(future, origin)[0])
    past = frame.copy()
    past.loc[35 * 1440 - 2, "close"] *= 1.05
    assert not np.allclose(base, r244.scale_bps(past, origin)[0])
    assert np.isclose(base[1] / base[0], np.sqrt(2)) and np.isclose(base[5], base[0])
    z = r244.to_z(np.array([[3.0, 50.0]]), np.array([[10.0, 20.0]]))
    assert np.allclose(r244.from_z(z, np.array([[10.0, 20.0]])), [[3.0, 50.0]])


def test_windows_purge_and_stop_lengths():
    retrain = pd.Timestamp("2022-06-01", tz="UTC")
    origins = pd.date_range(pd.Timestamp("2020-01-01", tz="UTC"), retrain, freq="15min", inclusive="left")
    cutoff = retrain - pd.Timedelta(hours=24)
    for name, window, stop in (("w365_raw", 365, 60), ("w180_raw", 180, 30), ("w90_raw", 90, 15)):
        train, held = r244.split_indices(origins, retrain, CANDIDATES[name])
        end = origins + pd.Timedelta(hours=24)
        assert end[train].min() >= cutoff - pd.Timedelta(days=window)
        assert end[train].max() < cutoff - pd.Timedelta(days=stop) <= end[held].min()
        assert end[held].max() < cutoff
    train, _ = r244.split_indices(origins, retrain, CANDIDATES["exp_hl90_norm"])
    assert origins[train].min() == r244.EARLIEST_ORIGIN


def test_expanding_sampling_has_fixed_budget_and_prefers_recent():
    cutoff = pd.Timestamp("2024-01-01", tz="UTC")
    label_end = pd.date_range(pd.Timestamp("2021-01-01", tz="UTC"), cutoff, freq="15min", inclusive="left")
    order = r244.epoch_order(np.random.default_rng(0), label_end, cutoff, CANDIDATES["exp_hl90_norm"])
    assert len(order) == r244.EXPANDING_BUDGET_DAYS * 96 == len(set(order.tolist()))
    assert np.median(order) > len(label_end) * .6
    plain = r244.epoch_order(np.random.default_rng(0), label_end, cutoff, CANDIDATES["w365_raw"])
    assert sorted(plain.tolist()) == list(range(len(label_end)))


def test_tie_order_and_boundary():
    scores = {c["name"]: .10 for c in r244.CANDIDATES}
    scores["w90_raw"] = .105
    assert r244.choose(scores) == "w365_raw"
    scores["exp_hl90_norm"] = .2
    assert r244.choose(scores) == "exp_hl90_norm"
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for word in ("run_k45_short", "k45_ledger", "paper", "pnl"):
        assert word not in source


def test_rank_flags_use_only_earlier_predictions():
    times = pd.date_range(pd.Timestamp("2024-01-01", tz="UTC"), periods=40 * 96, freq="15min")
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({"timestamp": times, "segment": "DEV_FRONT"})
    for name in r244.r.TARGETS:
        frame[f"prediction_{name}"] = rng.lognormal(3, .5, len(times))
    base = r244.rank_flags(frame)
    row = 20 * 96
    changed = frame.copy()
    changed.loc[row:, "prediction_range_30m"] *= 100  # the row itself and later rows
    after = r244.rank_flags(changed)
    assert (base.loc[:row - 1, "prediction_high_range_30m"] == after.loc[:row - 1, "prediction_high_range_30m"]).all()
    assert bool(after.loc[row, "prediction_high_range_30m"])
    assert not base.loc[7 * 96 - 2, "rank_ready_range_30m"] and base.loc[7 * 96 + 1, "rank_ready_range_30m"]
    assert .1 < base.loc[8 * 96:, "prediction_high_range_30m"].mean() < .3


def test_average_precision_bounds():
    truth = np.array([1, 1, 0, 0, 0], bool)
    assert r244.average_precision(np.array([5., 4, 3, 2, 1]), truth) == 1.0
    assert r244.average_precision(np.array([1., 2, 3, 4, 5]), truth) < .5
