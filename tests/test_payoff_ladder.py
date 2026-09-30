"""Guards for the payoff ladder.

The two things that can go wrong silently here are the barrier payoff reading a
bar it should not resolve on, and CUSUM marking origins from information it does
not yet have.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_payoff_ladder as payoff


def bars(close, high=None, low=None):
    close = np.asarray(close, float)
    return pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=len(close), freq="min", tz="UTC"),
        "close": close,
        "high": close if high is None else np.asarray(high, float),
        "low": close if low is None else np.asarray(low, float),
    })


def test_each_rung_changes_exactly_one_thing():
    for low, high in payoff.CONTRASTS:
        a, b = payoff.ARMS[low], payoff.ARMS[high]
        changed = [k for k in ("extra", "payoff", "geometry", "origins") if a[k] != b[k]]
        if a["payoff"] != b["payoff"]:
            # a terminal payoff has no geometry, so the two move together
            changed = [k for k in changed if k != "geometry"]
        assert len(changed) == 1, f"{low} -> {high} changes {changed}"


def test_no_arm_trains_on_a_barrier_payoff():
    # priced on B4's own signals, every geometry from +/-5 to +/-50 earned less
    # than the endpoint exit, so barriers are scored and never trained on
    for arm, spec in payoff.ARMS.items():
        assert spec["payoff"] == "terminal", f"{arm} trains on a barrier"
        assert spec["geometry"] is None


def test_both_geometries_are_still_available_for_scoring():
    assert set(payoff.GEOMETRY) == {"symmetric", "wide"}
    assert payoff.GEOMETRY["symmetric"] == (10.0, 10.0)
    assert payoff.GEOMETRY["wide"] == (20.0, 10.0)


def test_each_geometry_needs_the_hit_rate_the_plan_states():
    cost = 4.0
    for name, (take, stop), expected in (("symmetric", payoff.GEOMETRY["symmetric"], 0.700),
                                         ("wide", payoff.GEOMETRY["wide"], 0.467)):
        assert (stop + cost) / (take + stop) == pytest.approx(expected, abs=1e-3), name


def test_the_wide_geometry_pays_more_on_an_upside_touch():
    close = np.full(20, 100.0)
    high = close.copy()
    high[3] = 100.3                       # +30 bps, clears both takes
    frame = bars(close, high, close)
    narrow = payoff.barrier_payoff(frame, 15, *payoff.GEOMETRY["symmetric"])
    wide = payoff.barrier_payoff(frame, 15, *payoff.GEOMETRY["wide"])
    assert narrow[0] == pytest.approx(10.0)
    assert wide[0] == pytest.approx(20.0)


def test_the_wide_geometry_still_stops_at_the_same_loss():
    close = np.full(20, 100.0)
    low = close.copy()
    low[2] = 99.7
    frame = bars(close, close, low)
    assert payoff.barrier_payoff(frame, 15, *payoff.GEOMETRY["wide"])[0] == pytest.approx(-10.0)


def test_barrier_pays_the_upper_touch_when_it_comes_first():
    close = np.full(20, 100.0)
    high = close.copy()
    high[3] = 100.2                       # +20 bps on bar 3
    out = payoff.barrier_payoff(bars(close, high, close), 15, 10.0, 10.0)
    assert out[0] == pytest.approx(10.0)


def test_barrier_pays_the_lower_touch_when_it_comes_first():
    close = np.full(20, 100.0)
    low = close.copy()
    low[2] = 99.8                         # -20 bps on bar 2
    out = payoff.barrier_payoff(bars(close, close, low), 15, 10.0, 10.0)
    assert out[0] == pytest.approx(-10.0)


def test_barrier_takes_whichever_is_earlier():
    close = np.full(20, 100.0)
    high, low = close.copy(), close.copy()
    low[2] = 99.8                         # down first, on bar 2
    high[5] = 100.2                       # up later, on bar 5
    assert payoff.barrier_payoff(bars(close, high, low), 15, 10.0, 10.0)[0] \
        == pytest.approx(-10.0)


def test_a_same_bar_touch_of_both_is_resolved_against_the_position():
    close = np.full(20, 100.0)
    high, low = close.copy(), close.copy()
    high[4], low[4] = 100.2, 99.8
    assert payoff.barrier_payoff(bars(close, high, low), 15, 10.0, 10.0)[0] \
        == pytest.approx(-10.0)


def test_barrier_falls_back_to_the_endpoint_when_neither_is_touched():
    close = np.full(20, 100.0)
    close[15] = 100.05                    # +5 bps at the horizon, never touches 10
    out = payoff.barrier_payoff(bars(close), 15, 10.0, 10.0)
    assert out[0] == pytest.approx(5.0, abs=1e-6)


def test_barrier_leaves_the_tail_unknown():
    out = payoff.barrier_payoff(bars(np.full(20, 100.0)), 15, 10.0, 10.0)
    assert np.isnan(out[-15:]).all(), "the last span bars have no window to resolve in"


def test_barrier_reads_no_bar_beyond_the_window():
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0004, 200)))
    frame = bars(close, close * 1.0005, close * 0.9995)
    before = payoff.barrier_payoff(frame, 15, 10.0, 10.0)
    moved = frame.copy()
    moved.loc[100, ["close", "high", "low"]] *= 1.05
    after = payoff.barrier_payoff(moved, 15, 10.0, 10.0)
    np.testing.assert_allclose(before[:85], after[:85], rtol=0, atol=1e-9)


def test_cusum_marks_only_after_the_move_has_happened():
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0005, 400)))
    frame = bars(close)
    valid = np.ones(len(close), bool)
    marks = payoff.cusum_events(frame, valid)
    assert not marks[:60].any(), "no volatility estimate exists before the warmup closes"
    moved = frame.copy()
    moved.loc[350, "close"] *= 1.05
    assert np.array_equal(payoff.cusum_events(moved, valid)[:340], marks[:340])


def test_only_the_cusum_arm_changes_what_is_trained_on():
    assert payoff.ARMS["C3"]["origins"] == "cusum"
    for arm in ("C0", "C1"):
        assert payoff.ARMS[arm]["origins"] == "clock"
    a, b = payoff.ARMS["C1"], payoff.ARMS["C3"]
    assert {k: v for k, v in a.items() if k != "origins"} == \
           {k: v for k, v in b.items() if k != "origins"}, "C3 - C1 must isolate sampling"


def test_cusum_keeps_far_fewer_origins_than_the_clock():
    rng = np.random.default_rng(2)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0005, 5000)))
    valid = np.ones(len(close), bool)
    marks = payoff.cusum_events(bars(close), valid)
    assert 0 < marks.mean() < 0.35, f"CUSUM kept {marks.mean():.3f} of bars"


def test_no_arm_reuses_b4():
    # B4 trained on `valid`; every arm here trains on `valid & fresh`, so reusing
    # it would leave C0 trained one way over half its folds and another over the rest
    for arm in payoff.ORDER:
        assert payoff.ROOT.name in str(payoff.checkpoint(arm, 506, 42)), \
            f"{arm} must train its own weights"
        assert payoff.REUSE.name not in str(payoff.checkpoint(arm, 506, 42))


def test_a_short_barrier_is_not_a_negated_long_one():
    close = np.full(20, 100.0)
    high, low = close.copy(), close.copy()
    low[3] = 99.8                          # price falls 20 bps: good for a short
    frame = bars(close, high, low)
    take, stop = payoff.GEOMETRY["wide"]   # +20 / -10
    long_payoff = payoff.barrier_payoff(frame, 15, take, stop, direction=1)
    short_payoff = payoff.barrier_payoff(frame, 15, take, stop, direction=-1)
    assert long_payoff[0] == pytest.approx(-stop), "a long is stopped out by that fall"
    assert short_payoff[0] == pytest.approx(take), "a short takes profit on it"
    assert short_payoff[0] != pytest.approx(-long_payoff[0]), \
        "negating the long payoff would give the wrong number"


def test_a_same_bar_touch_goes_against_the_short_too():
    close = np.full(20, 100.0)
    high, low = close.copy(), close.copy()
    high[4], low[4] = 100.2, 99.8          # both barriers in one minute
    frame = bars(close, high, low)
    for direction in (1, -1):
        out = payoff.barrier_payoff(frame, 15, 10.0, 10.0, direction=direction)
        assert out[0] == pytest.approx(-10.0), f"direction {direction} must lose the tie"


def test_the_symmetric_shortcut_only_looked_right_by_coincidence():
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0006, 300)))
    frame = bars(close, close * 1.0008, close * 0.9992)
    for name, (take, stop) in payoff.GEOMETRY.items():
        long_payoff = payoff.barrier_payoff(frame, 15, take, stop, 1)[:200]
        short_payoff = payoff.barrier_payoff(frame, 15, take, stop, -1)[:200]
        agrees = np.isclose(short_payoff, -long_payoff, equal_nan=True).mean()
        if take == stop:
            assert agrees > 0.8, f"{name}: symmetric mostly survives negation"
        else:
            assert agrees < 0.5, f"{name}: asymmetric must not survive negation"


def test_preflight_abstains_on_a_fold_whose_stop_is_too_thin():
    # Binance never published bookDepth for 2024-04-18, and a three-day STOP
    # window containing it loses a third of its origins
    import types

    module = payoff
    frame = pd.DataFrame({"open_time": pd.date_range("2024-01-01", periods=200, freq="min",
                                                     tz="UTC")})
    calls = []

    def fake_endpoints(_frame, mask, _binary, _span, start, end):
        calls.append((start, end))
        return np.arange(5 if "thin" in str(start) else 500)

    plan = [{"train_start": "ok", "train_end": "ok", "stop_start": "ok", "stop_end": "ok"}] * 700
    plan[payoff.FOLDS[3]] = {"train_start": "ok", "train_end": "ok",
                             "stop_start": "thin", "stop_end": "thin"}
    saved_h, saved_c = module.horizon, module.old.calendar
    try:
        module.horizon = types.SimpleNamespace(endpoints=fake_endpoints)
        module.old.calendar = types.SimpleNamespace(fold_plan=lambda: plan)
        mask = np.ones(len(frame), bool)
        abstain, reasons = module.preflight(frame, mask, mask, mask)
    finally:
        module.horizon, module.old.calendar = saved_h, saved_c
    assert abstain == [payoff.FOLDS[3]]
    assert reasons[payoff.FOLDS[3]]["stop_origins"] == 5


def test_the_extra_channels_are_ten_and_named_once():
    assert len(payoff.EXTRA_NAMES) == 10
    assert len(set(payoff.EXTRA_NAMES)) == 10
    assert [a for a in payoff.ORDER if payoff.ARMS[a]["extra"]] == ["C1", "C3"]
