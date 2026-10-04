from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from out import run_k45_patchtst_updown_r2_21 as r21


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_up_down_targets_and_excursion_identity() -> None:
    close = np.array([100.0, 101.0, 99.0, 102.0, 98.0])
    high = close + np.array([1.0, 2.0, 1.0, 3.0, 1.0])
    low = close - np.array([1.0, 1.0, 2.0, 1.0, 3.0])
    targets = r21.up_down_range_targets(high, low, close, span=2)
    expected_up = (max(high[1:3]) / close[0] - 1) * 1e4
    expected_down = (1 - min(low[1:3]) / close[0]) * 1e4
    assert targets[0, 0] == pytest.approx(expected_up)
    assert targets[0, 1] == pytest.approx(expected_down)
    old = r21.old_excursion_targets(high, low, close, span=2)
    np.testing.assert_allclose(np.maximum(targets[:, 0], targets[:, 1]), old, equal_nan=True)


def test_label_window_stays_inside_every_phase() -> None:
    stamps = pd.date_range("2024-01-01", periods=100, freq="min", tz="UTC")
    valid = np.ones(len(stamps), dtype=bool)
    for start, end in ((10, 40), (40, 70), (70, 100)):
        selected = r21.phase_indices(stamps, valid, stamps[start], stamps[end - 1] + pd.Timedelta(minutes=1),
                                     span=15, grid_minutes=1)
        assert len(selected)
        assert (selected + 15 < end).all()
        assert (stamps[selected + 15] + pd.Timedelta(minutes=1) <= stamps[end - 1] + pd.Timedelta(minutes=1)).all()


def test_confirmation_fold_geometry_is_extended_and_clipped() -> None:
    first = r21.fold_spec(606)
    last = r21.fold_spec(666)
    assert first["test_start"] == pd.Timestamp("2026-01-01T00:00:00Z")
    assert first["test_end"] == pd.Timestamp("2026-01-03T00:00:00Z")
    assert last["test_start"] == pd.Timestamp("2026-06-29T00:00:00Z")
    assert last["test_end"] == pd.Timestamp("2026-07-01T00:00:00Z")


def test_roll_and_exp_use_strictly_prior_oos_folds() -> None:
    frame = pd.DataFrame({
        "pilot_fold": np.repeat([1, 2, 3], 4),
        "open_time": pd.date_range("2024-01-01", periods=12, freq="45D", tz="UTC"),
        "pred_excursion_bps": np.arange(1.0, 13.0),
    })
    first = r21.causal_gate_thresholds(frame, min_roll_rows=2, roll_days=180)
    changed = frame.copy()
    changed.loc[changed.pilot_fold.ge(2), "pred_excursion_bps"] = 1e6
    second = r21.causal_gate_thresholds(changed, min_roll_rows=2, roll_days=180)
    for column in ("g_roll_threshold", "g_exp_threshold"):
        assert first.loc[first.pilot_fold.eq(2), column].equals(second.loc[second.pilot_fold.eq(2), column])
    assert first.loc[first.pilot_fold.eq(1), "g_exp_threshold"].isna().all()
    assert first.loc[first.pilot_fold.eq(2), "g_exp_threshold"].nunique() == 1


def test_single_position_never_exceeds_one() -> None:
    entries = np.array([0, 5, 15, 16, 30, 45])
    keep = r21.admit_single_positions(entries, hold=15)
    admitted = entries[keep]
    assert np.array_equal(admitted, np.array([0, 15, 30, 45]))
    assert np.all(admitted[1:] >= admitted[:-1] + 15)


def test_existing_artifacts_hash_comparison(tmp_path: Path) -> None:
    source = tmp_path / "old.parquet"
    source.write_bytes(b"frozen")
    snapshot = {str(source): digest(source)}
    r21.verify_immutable(snapshot)
    source.write_bytes(b"changed")
    with pytest.raises(AssertionError, match="modified"):
        r21.verify_immutable(snapshot)


def test_backtest_margin_loops_do_not_mutate_gate_columns() -> None:
    rows = pd.DataFrame({
        "signal_index": [20, 80],
        "open_time": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
        "d_bps": [2.0, -3.0], "m_q50": [1.0, 1.0], "m_q80": [2.5, 2.5],
        "fade_side": [-1, 1], "segment": ["DEV", "DEV"],
        "pass_g_stop": [True, True], "pass_g_roll": [True, False],
        "pass_g_exp": [False, True], "valid_h15": [True, True], "valid_h45": [True, True],
    })
    before = rows[["pass_g_stop", "pass_g_roll", "pass_g_exp"]].copy()
    close = np.linspace(100, 101, 140)
    events = pd.DataFrame({"time": pd.DatetimeIndex([], tz="UTC"), "rate": np.array([], float)})
    r21.backtests(rows, close, events)
    pd.testing.assert_frame_equal(before, rows[before.columns])


@pytest.mark.parametrize("boundary,rate,expected", [("PESS", 0.0001, -1.0),
                                                     ("OPT", -0.0001, 1.0)])
def test_attach_funding_boundary_sign(monkeypatch, boundary, rate, expected) -> None:
    monkeypatch.setattr(r21, "FUNDING_BOUNDARY", boundary)
    exit_time = pd.Timestamp("2024-01-01 08:00", tz="UTC")
    trades = pd.DataFrame({"open_time": [exit_time - pd.Timedelta(minutes=15)],
                           "exit_time": [exit_time], "side": [1], "gross_bps": [0.0]})
    events = pd.DataFrame({"time": [exit_time], "rate": [rate]})
    result = r21.attach_funding(trades, events)
    assert result.funding_bps.iat[0] == pytest.approx(expected)
