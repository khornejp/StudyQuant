"""Guards for the ternary 10 bps move target.

The failure modes that matter here are silent: a flipped class polarity, a
weight that stops being causal, or a gate that passes an arm which only
rediscovered the fade. Each gets one assertion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_move_target_10bps as move


def test_returns_bps_are_forward_and_leave_the_tail_unknown():
    close = np.array([100.0, 101.0, 99.0, 100.0], float)
    out = move.returns_bps(close, 2)
    assert out[0] == pytest.approx((99.0 / 100.0 - 1) * 10000)
    assert out[1] == pytest.approx((100.0 / 101.0 - 1) * 10000)
    assert np.isnan(out[-2:]).all(), "the last `span` rows have no forward window"


def test_move_target_polarity_and_threshold():
    # +50 bps, -50 bps, +1 bp, then an unknown tail
    close = np.array([100.0, 100.5, 100.0, 100.01, 100.0], float)
    labels = move.move_targets(close, 1, 10.0)
    assert labels[0] == move.UP
    assert labels[1] == move.DOWN
    assert labels[2] == move.SMALL, "a 1 bp move is below the 10 bps threshold"
    assert labels[-1] == -1, "no forward window means the -1 sentinel, never a class"


def test_move_target_boundary_is_inclusive():
    # doubling is exactly +10000 bps and halving exactly -5000 bps, with no float slack
    close = np.array([1.0, 2.0, 1.0], float)
    labels = move.move_targets(close, 1, 10000.0)
    assert labels[0] == move.UP, "a move exactly at the threshold counts"
    assert labels[1] == move.SMALL, "-5000 bps is inside a 10000 bps threshold"


def test_plain_arm_weights_every_sample_equally():
    forward = np.array([1.0, -80.0, 5.0], float)
    weights = move.sample_weights("plain", forward, np.array([0, 1, 2]))
    assert np.array_equal(weights, np.ones(3, np.float32))


def test_weighted_arm_scales_by_magnitude_and_respects_the_cap():
    forward = np.array([10.0, -10.0, 1000.0], float)
    train = np.array([0, 1])  # mean |r| over TRAIN only = 10.0
    weights = move.sample_weights("weighted", forward, train)
    assert weights[0] == pytest.approx(1.0)
    assert weights[1] == pytest.approx(1.0)
    assert weights[2] == pytest.approx(move.WEIGHT_CAP), "100x the mean must clip to the cap"


def test_weight_scale_comes_only_from_train_rows():
    forward = np.array([10.0, 10.0, 1000.0], float)
    quiet = move.sample_weights("weighted", forward, np.array([0, 1]))
    loud = move.sample_weights("weighted", forward, np.array([2]))
    assert quiet[0] > loud[0], "a louder TRAIN split must shrink the same sample's weight"


def test_fade_side_opposes_the_prior_move_and_never_returns_zero():
    close = np.array([100.0, 101.0, 101.0], float)
    idx = np.array([1, 2])
    side = move.fade_side(close, idx, span=1)
    assert side[0] == -1.0, "price rose into the origin, so the fade is short"
    assert side[1] == 1.0, "a flat prior bar must still take a side, not 0"


def test_paired_difference_uses_the_pairing_not_two_independent_means():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([0.5, 1.5, 2.5])
    result = move.paired(a, b)
    assert result["gross_bps"] == pytest.approx(0.5)
    assert result["se"] == pytest.approx(0.0, abs=1e-12), "a constant gap has no paired dispersion"


def _report(gross, t, fade_gap, fade_t, large, coverage=0.05, rows=2000, sides=(1000, 1000)):
    return {
        "coverage": coverage,
        "accepted": {"rows": rows, "gross_bps": gross, "se": 1.0, "t": t, "hit": .55},
        "accepted_minus_fade": {"rows": rows, "gross_bps": fade_gap, "se": 1.0, "t": fade_t, "hit": .5},
        "accepted_long": {"rows": sides[0]}, "accepted_short": {"rows": sides[1]},
        "by_magnitude": {"50_plus": {"gross_bps": large}},
    }


def test_gate_rejects_an_arm_that_only_rediscovered_the_fade():
    a0 = _report(1.0, 3.0, 0.0, 0.0, 0.0)
    arm = _report(8.0, 6.0, fade_gap=0.05, fade_t=0.3, large=2.0)
    checks = move.gate(arm, a0)
    assert checks["gross_positive_t2"], "the arm is profitable in isolation"
    assert not checks["beats_fade_t2"], "but it adds nothing over the fade, so it must fail"
    assert not all(checks.values())


def test_gate_rejects_an_arm_still_inverted_on_large_moves():
    a0 = _report(1.0, 3.0, 0.0, 0.0, 0.0)
    arm = _report(8.0, 6.0, fade_gap=5.0, fade_t=4.0, large=-3.0)
    assert not move.gate(arm, a0)["large_moves_not_negative"]


def test_gate_passes_only_when_every_line_holds():
    a0 = _report(1.157, 3.07, 0.0, 0.0, -12.246)
    arm = _report(8.0, 6.0, fade_gap=5.0, fade_t=4.0, large=2.0)
    assert all(move.gate(arm, a0).values())


def test_gate_requires_a_material_gain_over_the_frozen_baseline():
    a0 = _report(1.157, 3.07, 0.0, 0.0, -12.246)
    arm = _report(1.9, 6.0, fade_gap=5.0, fade_t=4.0, large=2.0)
    assert not move.gate(arm, a0)["beats_a0_by_1bp"]


def test_fade_side_refuses_an_origin_with_no_prior_window():
    close = np.full(30, 100.0)
    with pytest.raises(AssertionError):
        move.fade_side(close, np.array([3]), span=15)


def test_score_reproduces_the_audited_baseline_arithmetic():
    # model goes long into a +20 bps move, then short into a +30 bps move
    close = np.full(40, 100.0)
    rows = pd.DataFrame({
        "signal_index": [20, 20],
        "forward_bps": [20.0, 30.0],
        "predicted_class": [move.UP, move.DOWN],
        "accepted": [True, True],
    })
    report = move.score(rows, close)
    assert report["accepted"]["gross_bps"] == pytest.approx((20.0 - 30.0) / 2)
    assert report["net_at_4bps"] == pytest.approx((20.0 - 30.0) / 2 - 4.0)
    assert report["coverage"] == pytest.approx(1.0)
