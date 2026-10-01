from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from out import k45_trend_side as ts
from out import run_k45_trend_side as run
from out import run_k45_trend_side_tp as tp


CAND = Path("out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet")
MARKET = Path("artifacts/btcusdt_2020_2026h1.parquet")


def test_trend_sign_is_causal_and_zero_without_history():
    close = np.array([100., 101., 99., 99., 102.])
    got = ts.trend_sign(close, np.array([0, 1, 2, 3, 4]), lookback=2)
    assert got.tolist() == [0, 0, -1, -1, 1]


def test_trend_sign_zero_when_flat():
    close = np.array([100., 100., 100.])
    assert ts.trend_sign(close, np.array([2]), lookback=2).tolist() == [0]


def test_side_mask_takes_long_in_uptrend_short_in_downtrend_nothing_flat():
    arm = np.array([ts.LONG, ts.SHORT, ts.LONG, ts.SHORT, ts.LONG])
    trend = np.array([1, 1, -1, -1, 0], dtype=np.int8)
    assert ts.side_mask(arm, trend).tolist() == [True, False, False, True, False]


def test_net_bps_signs_and_cost():
    close = np.array([100., 101., 100.])
    got = ts.net_bps(close, np.array([0, 1]), np.array([1, 2]), np.array([1., -1.]))
    assert got == pytest.approx([96.0, 1e4 * (1 - 100 / 101) - 4])


def test_admit_blocks_overlap_and_frees_at_hold():
    assert ts.admit(np.array([10, 20, 55, 56]), hold=45).tolist() == [True, False, True, False]


@pytest.mark.skipif(not CAND.exists() or not MARKET.exists(), reason="frozen data absent")
def test_reproduces_long_only_0455():
    d = pd.read_parquet(CAND)
    close = pd.read_parquet(MARKET, columns=["close"])["close"].to_numpy(float)
    ex = d[(d.arm == ts.LONG) & d.first_come_executed]
    r = ts.net_bps(close, ex.entry_index, ex.scheduled_exit_index, np.ones(len(ex)))
    assert len(ex) == 3066
    assert r.mean() == pytest.approx(0.4550, abs=5e-5)


def test_dev_gate_requires_all_three():
    ok = ts.dev_gate(1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})
    assert ok == {"status": "PASS", "passing_arms": [ts.LONG, ts.SHORT]}
    assert ts.dev_gate(1.0, -0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})["status"] == "FAIL"
    assert ts.dev_gate(-1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})["status"] == "FAIL"


def test_dev_gate_one_arm():
    got = ts.dev_gate(1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: -0.5})
    assert got == {"status": "ONE_ARM_PASS", "passing_arms": [ts.LONG]}


def test_dev_gate_zero_is_not_positive():
    assert ts.dev_gate(0.0, 0.1, {ts.LONG: 1.0, ts.SHORT: 1.0})["status"] == "FAIL"


def test_dev_gate_nan_ci_fails():
    assert ts.dev_gate(1.0, float("nan"), {ts.LONG: 1.0, ts.SHORT: 1.0})["status"] == "FAIL"


def test_trim_top_removes_largest():
    assert ts.trim_top(np.array([1., 2., 100., 50.]), 2) == pytest.approx(1.5)


def test_hold_gates():
    assert ts.holdb_gate(0.01) == "PASS" and ts.holdb_gate(0.0) == "FAIL"
    assert ts.holda_gate(1.0, 0.1) == "PASS" and ts.holda_gate(1.0, -0.1) == "FAIL"


def test_stage1_on_synthetic_frame():
    n = 200
    close = 100 + np.cumsum(np.full(n, 0.01))
    cands = pd.DataFrame({
        "candidate_id": [0, 1, 2],
        "pilot_fold": [0, 0, 0],
        "arm": [ts.LONG, ts.SHORT, ts.LONG],
        "signal_index": [60, 61, 150],
        "entry_index": [61, 62, 151],
        "scheduled_exit_index": [106, 107, 196],
        "entry_time": pd.to_datetime(["2021-01-10", "2021-01-10", "2021-01-11"], utc=True),
    })
    out = run.stage1(cands, close, lookback=50)
    book = out["book"]
    assert book.candidate_id.tolist() == [0, 2]
    assert set(out["cells"].columns) >= {"arm", "trend", "n", "gross_mean_bps", "net_mean_bps"}


def test_random_baseline_uptrend_long_is_positive():
    close = 100 + np.cumsum(np.full(400, 0.05))
    b = run.random_baseline(close, 100, 400, lookback=50)
    assert b.trend.tolist() == [1.0]
    assert b.net_mean_bps.iloc[0] > -4


def test_stage1_flat_trend_takes_no_trade():
    close = np.full(120, 100.0)
    cands = pd.DataFrame({
        "candidate_id": [0],
        "pilot_fold": [0],
        "arm": [ts.LONG],
        "signal_index": [50],
        "entry_index": [51],
        "scheduled_exit_index": [96],
        "entry_time": pd.to_datetime(["2021-01-10"], utc=True),
    })
    out = run.stage1(cands, close, lookback=50)
    assert out["book"].empty
    assert set(out) >= {"book", "cells", "baseline", "monthly"}


def test_segment_report_uses_candidate_dates_and_exit_boundary(monkeypatch):
    close = 100 + np.cumsum(np.full(220, 0.01))
    cands = pd.DataFrame({
        "candidate_id": [0, 1, 2],
        "pilot_fold": [606, 607, 666],
        "arm": [ts.SHORT, ts.LONG, ts.SHORT],
        "signal_index": [60, 100, 160],
        "entry_index": [61, 101, 161],
        "scheduled_exit_index": [106, 146, 206],
        "entry_time": pd.to_datetime(
            ["2026-01-02 14:49", "2026-03-01 00:00", "2026-06-30 16:00"], utc=True),
    })
    seen = {}

    def fake_mean(frame, value, start, end):
        seen["mean"] = (value, start, end)
        return 1.0, np.array([1.0]), pd.DatetimeIndex([start])

    def fake_pw(estimate, raw, alternative, label):
        seen["pw"] = (estimate, raw.tolist(), alternative, label)
        return {"bootstrap_ci95_lower": 0.1}

    def fake_baseline(_close, start, stop, lookback):
        seen.setdefault("baseline", []).append((start, stop, lookback))
        return pd.DataFrame({"trend": [1.0], "n": [1], "net_mean_bps": [0.0]})

    monkeypatch.setattr(run.flow, "mean_influence", fake_mean)
    monkeypatch.setattr(run.flow, "pw_inference", fake_pw)
    monkeypatch.setattr(run, "random_baseline", fake_baseline)

    run._segment_report(cands, close, 50, "HOLD_B_30d")

    assert seen["mean"] == (
        "net_bps", pd.Timestamp("2026-01-02", tz="UTC"), pd.Timestamp("2026-06-30", tz="UTC"))
    assert seen["pw"] == (1.0, [1.0], "greater", "HOLD_B_30d_book_net")
    assert seen["baseline"] == [(61, 206, 50)]


def test_tp_long_fills_at_tp_price():
    close = np.array([100., 100., 100., 100.])
    high = np.array([100., 100.4, 101.0, 100.])
    low = close.copy()
    net, ex = ts.tp_exit_net_bps(high, low, close, np.array([0]), np.array([1.]), 50, hold=3)
    assert ex.tolist() == [2] and net == pytest.approx([50 - 4])


def test_tp_not_filled_on_entry_bar():
    close = np.array([100., 100., 100.])
    high = np.array([200., 100., 100.])
    net, ex = ts.tp_exit_net_bps(high, close, close, np.array([0]), np.array([1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([-4])


def test_tp_short_and_same_bar_as_time_exit():
    close = np.array([100., 100., 98.])
    low = np.array([100., 100., 99.4])
    net, ex = ts.tp_exit_net_bps(close, low, close, np.array([0]), np.array([-1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([50 - 4])


def test_tp_untouched_uses_time_exit():
    close = np.array([100., 100., 100.2])
    net, ex = ts.tp_exit_net_bps(close, close, close, np.array([0]), np.array([1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([20 - 4])


def test_tp_raises_if_hold_window_exceeds_market_array():
    close = np.array([100., 100., 100.])
    with pytest.raises(IndexError):
        ts.tp_exit_net_bps(close, close, close, np.array([1]), np.array([1.]), 50, hold=2)


def test_select_tp_bonferroni():
    r = {50.0: {"net": 1.0, "p": 0.01},
         100.0: {"net": 2.0, "p": 0.02},
         150.0: {"net": 0.5, "p": 0.001}}
    assert tp.select_tp(r) == 50.0
    assert tp.select_tp({50.0: {"net": 1.0, "p": 0.02}}) is None


def test_tp_segment_keeps_fixed_book_and_reports_both_arms():
    close = np.r_[100 + np.arange(70) * .1, 107 - np.arange(80) * .1]
    high, low = close.copy(), close.copy()
    high[22] = 200
    low[92] = 0
    cands = pd.DataFrame({
        "candidate_id": [0, 1, 2],
        "pilot_fold": [0, 0, 0],
        "arm": [ts.LONG, ts.LONG, ts.SHORT],
        "signal_index": [20, 29, 90],
        "entry_index": [21, 30, 91],
        "scheduled_exit_index": [66, 75, 136],
        "entry_time": pd.to_datetime(["2021-01-01", "2021-01-01", "2021-01-02"], utc=True),
    })

    grid, paired = tp.evaluate_segment(
        cands, high, low, close, "DEV", lookback=2, grid=(50.0,))

    assert set(grid.arm) == {tp.BOOK, ts.LONG, ts.SHORT}
    assert grid.set_index("arm").loc[tp.BOOK, "n"] == 2
    assert paired.set_index("arm").loc[tp.BOOK, "n"] == 2
    assert grid.label.unique().tolist() == [tp.LABEL]
    assert paired.alternative.unique().tolist() == ["two-sided"]
