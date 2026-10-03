import numpy as np
import pandas as pd
import pytest

from out import k45_ledger as L

UTC = "UTC"


def _closes(start, prices):
    idx = pd.date_range(start, periods=len(prices), freq="min", tz=UTC)
    return pd.Series(prices, index=idx, dtype=float)


def _trade(side, entry, entry_px, exit_, exit_px):
    return pd.DataFrame({"side": [side], "entry_time": [pd.Timestamp(entry, tz=UTC)],
                         "entry_price": [entry_px], "exit_time": [pd.Timestamp(exit_, tz=UTC)],
                         "exit_price": [exit_px]})


NO_FUNDING = pd.DataFrame({"time": pd.to_datetime([], utc=True), "rate": []})


def test_minute_pnl_sums_to_realized_trade():
    closes = _closes("2024-01-01 00:00", [100, 101, 99, 102, 103])
    t = _trade(1, "2024-01-01 00:00", 100.0, "2024-01-01 00:04", 103.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    realized = np.log(103 / 100) * 1e4 - 4.0
    assert pnl.sum() == pytest.approx(realized)
    # 보유 중 최저점이 원장에 보여야 한다 (99에서 평가손실)
    equity = pnl.cumsum()
    assert equity.min() < 0


def test_boundary_split_sums_to_trade():
    # 23:57 100, 23:58 100, 23:59 90 | 00:00 110, 00:01 110, 00:02 110, 00:03 110
    closes = _closes("2025-12-31 23:57", [100.0, 100.0, 90.0, 110.0, 110.0, 110.0, 110.0])
    t = _trade(1, "2025-12-31 23:57", 100.0, "2026-01-01 00:03", 110.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    seg = L.segment_pnl(pnl, {"DEV": (pd.Timestamp("2020-07-01", tz=UTC), pd.Timestamp("2026-01-01", tz=UTC)),
                              "HOLD_B": (pd.Timestamp("2026-01-01", tz=UTC), pd.Timestamp("2026-07-01", tz=UTC))})
    total = np.log(110 / 100) * 1e4 - 4.0
    assert seg["DEV"].sum() + seg["HOLD_B"].sum() == pytest.approx(total)
    # DEV 몫은 2025-12-31 23:59 종가(90)까지의 평가손익 + 진입 비용
    assert seg["DEV"].sum() == pytest.approx(np.log(90 / 100) * 1e4 - 2.0)


def test_no_trade_days_are_zero():
    closes = _closes("2024-01-01 00:00", [100, 101])
    t = _trade(1, "2024-01-01 00:00", 100.0, "2024-01-01 00:01", 101.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    daily = L.daily_from_minutes(pnl, pd.Timestamp("2024-01-01", tz=UTC), pd.Timestamp("2024-01-08", tz=UTC))
    assert len(daily) == 7
    assert (daily.iloc[1:] == 0).all()


def test_funding_booked_at_settlement_minute():
    closes = _closes("2024-01-01 07:58", [100.0] * 5)
    t = _trade(1, "2024-01-01 07:58", 100.0, "2024-01-01 08:02", 100.0)
    funding = pd.DataFrame({"time": [pd.Timestamp("2024-01-01 08:00", tz=UTC)], "rate": [0.001]})
    pnl = L.mtm_minute_pnl(t, closes, funding, cost_bps=0.0)
    assert pnl.loc[pd.Timestamp("2024-01-01 08:00", tz=UTC)] == pytest.approx(-10.0)
    assert pnl.sum() == pytest.approx(-10.0)


def _ar(phi, n=1500, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return x


def test_pw_block_grows_with_autocorrelation():
    assert L.pw_mean_ci(_ar(0.8))["block"] > L.pw_mean_ci(_ar(0.2))["block"]


def test_pw_iid_falls_back_to_block_one():
    # 2026-10-03 확인: 기존 optimal_block_length는 iid 시계열에서
    # "invalid Politis-White block length"(추정 블록 < 1)로 예외를 낸다.
    out = L.pw_mean_ci(np.random.default_rng(0).normal(size=1500))  # seed 0: 추정 블록 < 1 확인됨
    assert out["status"] == "MEASURABLE_BLOCK1"
    assert out["block"] == 1.0
    assert np.isfinite(out["ci95_lower"])


def test_pw_unmeasurable_is_reported():
    out = L.pw_mean_ci(np.zeros(181))
    assert out["status"] == "UNMEASURABLE"
    assert np.isnan(out["ci95_lower"])


def test_pw_is_seeded():
    x = np.random.default_rng(1).normal(size=400)
    assert L.pw_mean_ci(x) == L.pw_mean_ci(x)


def _tr(entries, exits, nets):
    return pd.DataFrame({"entry_time": pd.to_datetime(entries, utc=True),
                         "exit_time": pd.to_datetime(exits, utc=True)}), pd.Series(nets, dtype=float)


def test_event_exclusion_removes_whole_event():
    trades, net = _tr(["2024-01-01 00:00", "2024-01-01 05:00", "2024-02-01 00:00"],
                      ["2024-01-01 04:00", "2024-01-01 09:00", "2024-02-01 04:00"],
                      [50.0, 40.0, 60.0])
    ev = L.assign_events(trades)
    assert ev.iloc[0] == ev.iloc[1] != ev.iloc[2]
    by_trade = L.exclude_top(trades, net, pd.Series(range(3)), k=1)
    by_event = L.exclude_top(trades, net, ev, k=1)
    assert by_trade == pytest.approx(90.0)
    assert by_event == pytest.approx(60.0)
    assert by_event <= by_trade


def test_week_grouping_uses_entry_week():
    trades, net = _tr(["2024-01-01", "2024-01-03", "2024-01-10"],
                      ["2024-01-02", "2024-01-04", "2024-01-11"], [10.0, 20.0, 5.0])
    week = trades.entry_time.dt.to_period("W")
    assert L.exclude_top(trades, net, week, k=1) == pytest.approx(5.0)


def test_dsr_falls_with_more_trials():
    x = np.random.default_rng(2).normal(0.05, 1.0, size=1500)
    few = L.deflated_sharpe(x, n_trials=2, trial_sharpe_var=0.001)
    many = L.deflated_sharpe(x, n_trials=813, trial_sharpe_var=0.001)
    assert many["dsr"] < few["dsr"]
    assert 0.0 <= many["dsr"] <= 1.0


def test_dsr_single_trial_matches_psr_against_zero():
    x = np.random.default_rng(3).normal(0.02, 1.0, size=1000)
    out = L.deflated_sharpe(x, n_trials=1, trial_sharpe_var=0.0)
    assert out["sr0"] == 0.0
