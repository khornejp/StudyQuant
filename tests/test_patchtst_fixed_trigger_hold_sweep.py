from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_fixed_trigger_hold_sweep as sweep


def test_fixed_hold_reads_entry_and_exact_k_exit_only():
    close = np.full(12, np.nan)
    close[5] = 100.0
    close[9] = 101.0
    entry, exit_, available, gross = sweep.fixed_hold_outcomes(
        close, np.array([2]), np.array([3]), np.array([1]), hold=4
    )
    assert entry.tolist() == [5]
    assert exit_.tolist() == [9]
    assert available.tolist() == [True]
    assert gross[0] == pytest.approx(1e4 * np.log(1.01))
    assert np.isnan(close[:5]).all()  # bars before tau were never required or read


def test_fixed_hold_censors_missing_exit_without_using_earlier_bar():
    close = np.full(10, 100.0)
    entry, exit_, available, gross = sweep.fixed_hold_outcomes(
        close, np.array([2]), np.array([3]), np.array([-1]), hold=5
    )
    assert entry.tolist() == [5]
    assert exit_.tolist() == [10]
    assert available.tolist() == [False]
    assert np.isnan(gross[0])


def test_completed_close_first_crossing_keeps_overshoot_side():
    close = np.full(25, 100.0)
    close[7] = 100.0 * np.exp(-0.0051)
    close[8] = 100.0 * np.exp(0.009)
    triggered, tau, side = sweep.first_crossing(close, np.array([5]))
    assert triggered.tolist() == [True]
    assert tau.tolist() == [2]
    assert side.tolist() == [-1]


def test_speed_bins_exactly_invert_old_remaining_groups():
    tau = np.array([1, 5, 6, 9, 10, 12, 13, 14, 15])
    assert sweep.speed_labels(tau).tolist() == [
        "tau=1-5", "tau=1-5", "tau=6-9", "tau=6-9",
        "tau=10-12", "tau=10-12", "tau=13-14", "tau=13-14", "tau=15",
    ]
    remaining = 15 - tau
    assert remaining.tolist() == [14, 10, 9, 6, 5, 3, 2, 1, 0]


def test_old_k0_cost_is_four_bps_and_four_cents_per_trade():
    trades = pd.DataFrame({
        "span": [sweep.EARLY_SPAN] * 3 + [sweep.LATE_SPAN],
        "arm": [sweep.ARMS[0], sweep.ARMS[0], sweep.ARMS[1], sweep.ARMS[1]],
        "tau_50": [15, 2, 15, 15],
    })
    rows = sweep.old_k0_summary(trades)
    pooled = rows.loc[
        rows.span.eq(sweep.POOLED_SPAN) & rows.arm.eq("BOTH_ARMS")
    ].iloc[0]
    assert pooled.old_zero_exposure_count == 3
    assert pooled.pure_cost_bps_total == -12
    assert pooled.pure_cost_usd_100_fixed_total == pytest.approx(-0.12)


def test_frozen_family_and_plan_hash():
    assert sweep.HOLDS == (15, 20, 30, 45, 60, 70)
    assert len(sweep.HOLDS) * len(sweep.ARMS) == 12
    expected = sweep.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert sweep.sha256(sweep.PLAN) == expected
