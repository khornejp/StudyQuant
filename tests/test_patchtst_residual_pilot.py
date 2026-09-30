"""Contract tests for the retrospective R0/R1 residual pilot."""
from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_residual_pilot as pilot


def rows(classes, accepted, forward=(10.0, -20.0, 5.0)):
    return pd.DataFrame({
        "pilot_fold": [406] * 3,
        "signal_index": [100, 115, 130],
        "open_time": pd.date_range("2024-01-01", periods=3, freq="15min", tz="UTC"),
        "predicted_class": classes,
        "accepted": accepted,
        "forward_bps": forward,
    })


def test_side_convention_includes_not_accepted_zero():
    side = pilot.decision_side(
        np.array([pilot.UP, pilot.DOWN, pilot.SMALL, pilot.UP]),
        np.array([True, True, True, False]),
    )
    np.testing.assert_array_equal(side, [1.0, -1.0, 0.0, 0.0])


def test_pairing_arithmetic_uses_every_origin():
    r0 = rows([pilot.UP, pilot.DOWN, pilot.UP], [True, False, True])
    r1 = rows([pilot.DOWN, pilot.DOWN, pilot.UP], [True, True, False])
    paired = pilot.paired_utility_rows(r0, r1)
    np.testing.assert_array_equal(paired.r0_u, [10.0, 0.0, 5.0])
    np.testing.assert_array_equal(paired.r1_u, [-10.0, 20.0, 0.0])
    assert (paired.r1_u - paired.r0_u).mean() == pytest.approx(-5.0 / 3.0)


def test_pairing_fails_when_origin_populations_differ():
    r0 = rows([pilot.UP] * 3, [True] * 3)
    r1 = r0.iloc[1:].copy()
    with pytest.raises(AssertionError):
        pilot.paired_utility_rows(r0, r1)


def test_c6_selects_only_accepted_fade_to_continuation_flips():
    selected = pilot.c6_selection(
        r0_side=np.array([-1.0, 1.0, 0.0, 1.0]),
        r1_side=np.array([1.0, -1.0, 1.0, -1.0]),
        prior_move=np.array([0.01, -0.02, 0.03, 0.0]),
    )
    np.testing.assert_array_equal(selected, [True, True, False, False])


def test_two_mask_origin_counts_record_each_split(monkeypatch):
    frame = pd.DataFrame({"open_time": pd.date_range("2024-01-01", periods=5, freq="min")})
    plan = [None, {
        "train_start": "train", "train_end": "train",
        "stop_start": "stop", "stop_end": "stop",
        "test_start": "test", "test_end": "test",
    }]

    def fake_endpoints(_frame, mask, _binary, _span, _start, _end):
        return np.flatnonzero(mask)

    monkeypatch.setattr(pilot, "horizon", types.SimpleNamespace(endpoints=fake_endpoints))
    monkeypatch.setattr(pilot.old, "calendar", types.SimpleNamespace(fold_plan=lambda: plan))
    base = np.array([True, True, False, True, True])
    liquidity = np.array([True, False, True, True, True])
    counts = pilot.mask_origin_counts(frame, np.zeros(5), base, liquidity, folds=(1,))
    for split in ("train", "stop", "test"):
        assert counts["by_fold"]["1"][split] == {
            "valid_and_fresh": 4,
            "with_liquidity_valid": 3,
            "different": 1,
        }
    assert counts["different_origin_occurrences"] == 3
    assert counts["different_unique_signal_indices"] == 1


def test_r0_loads_c0_checkpoint_and_never_fits(monkeypatch):
    calls = []
    sentinel = object()

    def fake_ladder_model(arm, number, seed, values, returns, train, stop, fit_missing):
        calls.append((arm, number, seed, fit_missing))
        return sentinel

    monkeypatch.setattr(pilot.ladder, "model", fake_ladder_model)
    monkeypatch.setattr(
        pilot.rungs,
        "fit_pnl",
        lambda *_args, **_kwargs: pytest.fail("R0 entered fit path"),
    )
    out = pilot.model(
        "R0",
        406,
        42,
        np.zeros((4, 40), np.float32),
        np.zeros(4),
        np.array([0, 1]),
        np.array([2, 3]),
        True,
    )
    assert out is sentinel
    assert calls == [("C0", 406, 42, False)]


def test_folds_and_single_appended_channel_are_frozen():
    assert pilot.PILOT_FOLDS == (406, 424, 442, 460, 478, 496, 514, 532, 550, 568, 586, 604)
    assert pilot.CHANNEL == "kyle_lambda_surge"
    assert pilot.CONDITIONING == "sign(x)*log1p(abs(x))"
