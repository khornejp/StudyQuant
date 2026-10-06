from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "out/run_k45_vol_detector_r2_43.py"
SPEC = importlib.util.spec_from_file_location("r243", SCRIPT)
r243 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = r243
SPEC.loader.exec_module(r243)


def minute_frame(rows=1600):
    times = pd.date_range("2024-01-01", periods=rows, freq="1min", tz="UTC")
    close = 100 + np.arange(rows) * .01
    return pd.DataFrame({"open_time": times, "open": close - .005,
                         "high": close + .02, "low": close - .02, "close": close,
                         "volume": 1., "quote_volume": 100., "number_of_trades": 2,
                         "taker_buy_base_volume": .5})


def test_labels_use_t_onward_and_only_t_minus_one_anchor():
    frame = minute_frame()
    origin = pd.DatetimeIndex([frame.open_time.iloc[100]])
    baseline = r243.future_targets(frame, origin)
    old = frame.copy()
    old.loc[50, ["high", "low", "close"]] = [999, .1, 800]
    assert np.allclose(baseline, r243.future_targets(old, origin), equal_nan=True)
    future = frame.copy()
    future.loc[100, "high"] *= 2
    assert not np.isclose(baseline[0, 0], r243.future_targets(future, origin)[0, 0])
    anchor = frame.copy()
    anchor.loc[99, "close"] *= .5
    changed = r243.future_targets(anchor, origin)
    assert np.isclose(baseline[0, 0], changed[0, 0])
    assert not np.isclose(baseline[0, 5], changed[0, 5])


def test_completed_bars_and_missing_minutes_are_not_interpolated():
    frame = minute_frame(120)
    bars = r243.aggregate(frame, "5min")
    assert (bars.decision_time == bars.open_time + pd.Timedelta(minutes=5)).all()
    with pytest.raises(ValueError, match="never interpolated"):
        r243.aggregate(frame.drop(index=17), "5min")


def test_ls_plus_five_minutes_is_strictly_available():
    available = pd.DatetimeIndex([pd.Timestamp("2024-01-01 00:05", tz="UTC") +
                                  pd.Timedelta(minutes=5)])
    decisions = pd.DatetimeIndex([pd.Timestamp("2024-01-01 00:10", tz="UTC"),
                                  pd.Timestamp("2024-01-01 00:10:00.001", tz="UTC")])
    values, _, missing, _ = r243.asof_strict(np.array([1.2]), available, decisions,
                                             pd.Timedelta(minutes=15))
    assert missing.tolist() == [1, 0]
    assert values.tolist() == [0, pytest.approx(1.2)]
    values, _, missing, _ = r243.asof_strict(np.array([np.nan]), available, decisions)
    assert missing.tolist() == [1, 1]
    assert values.tolist() == [0, 0]


def test_funding_requires_actual_publish_time():
    publication = pd.DatetimeIndex([pd.Timestamp("2024-01-01 08:00:00.002", tz="UTC")])
    decisions = pd.DatetimeIndex([pd.Timestamp("2024-01-01 08:00:00", tz="UTC"),
                                  pd.Timestamp("2024-01-01 08:15:00", tz="UTC")])
    values, _, missing, _ = r243.asof_strict(np.array([.0001]), publication, decisions)
    assert missing.tolist() == [1, 0]
    assert values[1] == pytest.approx(.0001)


def test_purge_is_strict_label_end_before_retrain_minus_24h():
    retrain = pd.Timestamp("2024-01-01", tz="UTC")
    origins = pd.date_range(pd.Timestamp("2021-01-01", tz="UTC"), retrain,
                            freq="1h", inclusive="left")
    train, stop = r243.purge_indices(origins, retrain)
    label_end = origins + pd.Timedelta(hours=24)
    cutoff = retrain - pd.Timedelta(hours=24)
    assert (label_end[train] < cutoff - pd.Timedelta(days=60)).all()
    assert (label_end[stop] < cutoff).all()
    assert label_end[stop].max() < cutoff
    assert label_end[stop].min() >= cutoff - pd.Timedelta(days=60)


def test_forbidden_result_paths_are_rejected_and_source_has_no_result_imports(tmp_path):
    for word in ("trade", "position", "pnl", "backtest", "c1_x"):
        with pytest.raises(PermissionError):
            r243.guard_path(tmp_path / word / "x.parquet")
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "run_k45_short" not in source
    assert "k45_ledger" not in source


def test_resume_requires_manifest_and_artifact_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(r243, "OUT", tmp_path)
    checkpoint, prediction, metadata = r243.fold_paths("compact_3d", "DEV_FRONT", 0)
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"model")
    prediction.write_bytes(b"prediction")
    record = {"freeze_manifest_hash": "frozen",
              "checkpoint_sha256": r243.sha256_file(checkpoint),
              "predictions_sha256": r243.sha256_file(prediction)}
    r243.write_json(metadata, record)
    assert r243.valid_completed_fold("compact_3d", "DEV_FRONT", 0, "frozen")
    prediction.write_bytes(b"changed")
    assert not r243.valid_completed_fold("compact_3d", "DEV_FRONT", 0, "frozen")


def test_selection_tie_rule_prefers_seven_day_then_compact():
    scores = {item["name"]: .1 for item in r243.CANDIDATES}
    scores["base_3d"] = .109
    assert r243.choose_candidate(scores) == "compact_7d"
    scores = {item["name"]: .05 for item in r243.CANDIDATES}
    scores["base_3d"] = .2
    assert r243.choose_candidate(scores) == "base_3d"


def synthetic_predictions(rows=28 * 96):
    rng = np.random.default_rng(7)
    times = pd.date_range("2024-01-01", periods=rows, freq="15min", tz="UTC")
    frame = pd.DataFrame({"timestamp": times})
    for name in r243.TARGETS:
        actual = rng.lognormal(3, .5, rows)
        prediction = actual * rng.lognormal(0, .05, rows)
        naive = actual * rng.lognormal(0, .4, rows)
        q33, q67, q80 = np.quantile(actual, (1 / 3, 2 / 3, .8))
        frame[f"actual_{name}"] = actual
        frame[f"prediction_{name}"] = prediction
        frame[f"naive_{name}"] = naive
        frame[f"actual_class_{name}"] = np.digitize(actual, (q33, q67))
        frame[f"prediction_class_{name}"] = np.digitize(prediction, (q33, q67))
        frame[f"actual_high_{name}"] = actual > q80
        frame[f"prediction_high_{name}"] = prediction > q80
    return frame


def test_fixed_predictive_criteria_calculation():
    metrics = r243.predictive_metrics(synthetic_predictions())
    assert metrics["monthly_mean_rank_ic"] > .9
    assert metrics["block_bootstrap_95_lower"] > 0
    assert metrics["average_mae_skill"] > 0
    assert metrics["macro_q80_precision"] > .2
    assert metrics["macro_balanced_accuracy"] > 1 / 3
    assert metrics["rank_ic"]["rv_30m"] > 0
    assert metrics["passed"]
