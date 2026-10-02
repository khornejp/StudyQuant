import numpy as np
import pandas as pd
import pytest

from out import run_k45_risk_stop_r2_18 as run


def _minutes(n=301, low=None, high=None, open_=None):
    time = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    opens = np.full(n, 100.0) if open_ is None else np.asarray(open_, float)
    lows = opens - 1 if low is None else np.asarray(low, float)
    highs = opens + 1 if high is None else np.asarray(high, float)
    return pd.DataFrame({"open_time": time, "open": opens, "high": highs,
                         "low": lows, "close": opens})


def _candidate(side=1, exit_minute=300, atr=2.0):
    start = pd.Timestamp("2026-01-01", tz="UTC")
    return pd.DataFrame({"signal_time": [start], "entry_time": [start],
                         "entry_price": [100.0], "original_exit_time":
                         [start + pd.Timedelta(minutes=exit_minute)],
                         "side": [side], "entry_atr": [atr]})


def test_stop_is_fixed_from_entry_atr():
    minutes = _minutes(low=np.r_[99.0, np.full(300, 96.9)])
    trade = run.simulate_candidates(_candidate(atr=2.0), minutes, None, 1.5).iloc[0]
    assert trade.stop_price == pytest.approx(97.0)
    assert trade.exit_price == pytest.approx(97.0)
    assert trade.exit_reason == "stop"


def test_stop_only_on_touch_and_gap_executes_at_open():
    untouched = run.simulate_candidates(_candidate(), _minutes(), None, 1.5).iloc[0]
    assert untouched.exit_reason == "max_hold"
    opens = np.full(301, 100.0)
    opens[1] = 95.0
    gap = run.simulate_candidates(_candidate(), _minutes(open_=opens), None, 1.5).iloc[0]
    assert gap.stop_price == pytest.approx(97.0)
    assert gap.exit_price == pytest.approx(95.0)


def test_entry_minute_stop_is_ignored_except_conservative_version():
    lows = np.full(301, 99.0)
    lows[0] = 90.0
    base = run.simulate_candidates(_candidate(), _minutes(low=lows), None, 1.5)
    conservative = run.simulate_candidates(_candidate(), _minutes(low=lows), None, 1.5,
                                            conservative=True)
    assert base.iloc[0].exit_reason == "max_hold"
    assert conservative.iloc[0].exit_reason == "stop"


def test_all_trades_respect_240_minute_cap():
    trades = run.simulate_candidates(_candidate(exit_minute=300), _minutes(), None, None)
    assert trades.hold_minutes.max() <= 240
    assert trades.iloc[0].exit_reason == "max_hold"


def test_future_atr_changes_do_not_change_entry_stop():
    minutes = _minutes(low=np.r_[99.0, np.full(300, 96.9)])
    candidate = _candidate(atr=2.0).assign(future_atr=999.0)
    before = run.simulate_candidates(candidate, minutes, None, 1.5)
    after = run.simulate_candidates(candidate.assign(future_atr=.01), minutes, None, 1.5)
    assert before.iloc[0].stop_price == after.iloc[0].stop_price == pytest.approx(97.0)


def test_combo_position_limits():
    candidates = pd.concat([_candidate(1), _candidate(-1)], ignore_index=True)
    single, dropped = run.combine_single(candidates, _minutes(), None, 1.5)
    hedge, _ = run.combine_hedge(candidates, _minutes(), None, 1.5)
    assert single.empty and dropped == 2
    assert run.max_concurrent(hedge.loc[hedge.side.eq(1)]) <= 1
    assert run.max_concurrent(hedge.loc[hedge.side.eq(-1)]) <= 1


def test_selection_accepts_dev_rows_only():
    metrics = pd.DataFrame({"cell_id": ["L1", "L2", "S1", "S2"],
                            "direction": ["L", "L", "S", "S"],
                            "segment": ["DEV"] * 4,
                            "version": ["STOP"] * 4,
                            "daily_sharpe": [1.0, 2.0, 3.0, 1.0]})
    assert run.select_cells(metrics) == {"long": "L2", "short": "S1"}
    with pytest.raises(ValueError, match="DEV"):
        run.select_cells(pd.concat([metrics, metrics.assign(segment="HOLD_B")]))


def test_round_trip_cost_and_funding_boundary():
    start = pd.Timestamp("2026-01-01", tz="UTC")
    funding = pd.DataFrame({"time": [start, start + pd.Timedelta(minutes=1)],
                            "rate": [.5, .001]})
    trade = run.simulate_candidates(_candidate(exit_minute=2), _minutes(), funding, None).iloc[0]
    assert trade.funding_bps == pytest.approx(-10.0)
    assert trade.net_bps == pytest.approx(trade.gross_bps - 4.0 - 10.0)
