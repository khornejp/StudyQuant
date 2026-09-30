import numpy as np
import pandas as pd

from btcusdt_quant.short_regime_payoff import (
    add_policy_state, eligible_events, nonoverlap, period, policy_payoffs, trade_summary,
)


def test_regime_payoff_design_keeps_causality_costs_and_position_boundaries() -> None:
    frame = pd.DataFrame({name: np.full(100, 100.0) for name in ("open", "high", "low", "close")})
    frame["open_time"] = pd.date_range("2022-01-01", periods=100, freq="min", tz="UTC")
    frame.loc[1, ["high", "low"]] = [102, 98]  # Both barriers: SL first, not candle-direction inference.
    labels = policy_payoffs(frame, np.array([0]), 15, np.array([0.01]))
    assert labels.exit_reason.iloc[0] == "SL"
    np.testing.assert_allclose(labels.net_bps, [-104])
    frame.loc[1, ["open", "high", "low", "close"]] = [103, 104, 102, 103]
    gap = policy_payoffs(frame, np.array([0]), 15, np.array([0.01]))
    # Entry occurs at 103, not signal close 100; high 104 stays below this stop.
    assert gap.entry_price.iloc[0] == 103
    frame.loc[2, ["open", "high", "low", "close"]] = [106, 107, 105, 106]
    gap = policy_payoffs(frame, np.array([0]), 15, np.array([0.01]))
    np.testing.assert_allclose(gap.net_bps, [(1 - 106 / 103) * 1e4 - 4])

    flat = frame.copy()
    flat[["open", "high", "low", "close"]] = 100.0
    flat.loc[15, ["close", "low"]] = 99.5
    timeout = policy_payoffs(flat, np.array([0]), 15, np.array([0.01]))
    assert timeout.exit_reason.iloc[0] == "TIMEOUT"
    np.testing.assert_allclose(timeout.net_bps, [46])
    changed = flat.copy()
    changed.loc[16:, "close"] = 1000
    pd.testing.assert_frame_equal(timeout, policy_payoffs(changed, np.array([0]), 15, np.array([0.01])))
    flat.close = 100 + np.sin(np.arange(100) / 5)
    changed = flat.copy()
    changed.loc[80:, "close"] = 1000
    np.testing.assert_allclose(add_policy_state(flat).efficiency_60[:80],
                               add_policy_state(changed).efficiency_60[:80], equal_nan=True)
    day = pd.DataFrame({"close": np.arange(100.0, 1600.0)})
    state = add_policy_state(day)
    assert np.isnan(state.return_24h.iloc[1439])
    np.testing.assert_allclose(state.return_24h.iloc[1440], 1540 / 100 - 1)

    events = pd.DataFrame({
        "policy": ["trend_pullback", "trend_pullback", "range_rejection", "range_rejection"],
        "ema_gap_15m": [-0.01, 0.01, 0.0001, 0.0001], "return_24h": [-0.02, 0.02, 0.0, 0.0],
        "efficiency_60": [0.8, 0.8, 0.1, 0.1], "rv_60": [0.001, 0.001, 0.001, 0.001],
        "sigma_h": [0.005, 0.005, 0.005, 0.0001],
    })
    thresholds = {"abs_ema_median": 0.001, "efficiency_q33": 0.2, "efficiency_q67": 0.6, "rv60_q99": 0.01}
    assert eligible_events(events, thresholds).tolist() == [True, False, True, False]
    positions = pd.DataFrame({"signal_index": [0, 1, 15, 16], "exit_index": [15, 2, 60, 17]})
    assert nonoverlap(positions).signal_index.tolist() == [0, 15]
    # A lucky early exit must not admit a signal whose maximum window crosses a split.
    assert period(timeout, flat.open_time.iloc[0], flat.open_time.iloc[10]).empty
    timeout["policy"] = "range_rejection"
    assert trade_summary(timeout)["mean_net_ci95"] is None
    assert trade_summary(timeout.iloc[:0])["trades"] == 0
