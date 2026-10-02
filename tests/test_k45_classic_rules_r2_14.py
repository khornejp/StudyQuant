import numpy as np
import pandas as pd

from out import run_k45_classic_rules_r2_14 as run


def minute_frame(n=12):
    time = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    price = np.arange(100.0, 100.0 + n)
    return pd.DataFrame({"open_time": time, "open": price, "high": price + 1,
                         "low": price - 1, "close": price + .5,
                         "volume": np.ones(n)})


def test_closed_bars_and_next_minute_open_execution():
    minutes = minute_frame(7)
    bars = run.aggregate_closed_ohlcv(minutes, 3)
    assert bars.decision_time.tolist() == [minutes.open_time.iloc[3], minutes.open_time.iloc[6]]
    assert bars.close.tolist() == [minutes.close.iloc[2], minutes.close.iloc[5]]
    trades = run.simulate(minutes, bars, np.array([1, -1]), np.zeros(2, bool),
                          np.zeros(2, bool), close_at_end=True)
    assert trades.entry_time.iloc[0] == minutes.open_time.iloc[3]
    assert trades.entry_price.iloc[0] == minutes.open.iloc[3]


def test_indicator_has_no_future_use():
    minutes = minute_frame(240)
    first = run.add_indicators(run.aggregate_closed_ohlcv(minutes, 15))
    changed = minutes.copy()
    changed.loc[changed.index[-1], ["high", "low", "close"]] = [9999, 1, 7777]
    second = run.add_indicators(run.aggregate_closed_ohlcv(changed, 15))
    pd.testing.assert_series_equal(first.ema_10.iloc[:-1], second.ema_10.iloc[:-1])
    pd.testing.assert_series_equal(first.rsi_14.iloc[:-1], second.rsi_14.iloc[:-1])


def test_single_position_cost_and_funding():
    minutes = minute_frame(10)
    bars = run.aggregate_closed_ohlcv(minutes, 2)
    funding = pd.DataFrame({"time": [minutes.open_time.iloc[4]], "rate": [.001]})
    trades = run.simulate(minutes, bars, np.array([1, 1, -1, -1, 0]),
                          np.zeros(5, bool), np.zeros(5, bool), funding=funding,
                          close_at_end=True)
    assert run.max_concurrent(trades) <= 1
    first = trades.iloc[0]
    expected = np.log(first.exit_price / first.entry_price) * 10_000 - 4 - 10
    assert first.net_bps == pytest.approx(expected)
    assert first.funding_bps == pytest.approx(-10)


def test_settlement_uses_utc_clock_and_previous_minute_rate():
    times = pd.date_range("2026-01-01 07:58", periods=4, freq="min", tz="UTC")
    registry = pd.DataFrame({
        "open_time": times,
        "minutes_to_next_funding": [2.00001, 1.00001, 480.00003, 479.00003],
        "funding_rate": [.001, .002, .003, .004],
    })
    events, stats = run.settlement_events(registry)
    assert events.to_dict("records") == [{"time": times[2], "rate": .002}]
    assert stats == {"scheduled": 1, "missing_previous_minute": 0,
                     "nonstandard": 0}


def test_actual_day_long_24h_applies_three_settlements():
    start = pd.Timestamp("2026-01-01", tz="UTC")
    registry = pd.read_parquet(
        run.REGISTRY,
        columns=["open_time", "minutes_to_next_funding", "funding_rate"],
        filters=[("open_time", ">=", start - pd.Timedelta(minutes=1)),
                 ("open_time", "<=", start + pd.Timedelta(days=1))],
    )
    registry["open_time"] = pd.to_datetime(registry.open_time, utc=True)
    events, _ = run.settlement_events(registry)
    held = events.loc[events.time.between(start + pd.Timedelta(minutes=1),
                                          start + pd.Timedelta(days=1, minutes=1),
                                          inclusive="both")]
    assert len(held) == 3
    assert run._funding_bps(1, start + pd.Timedelta(minutes=1),
                            start + pd.Timedelta(days=1, minutes=1), events) == pytest.approx(
                                -held.rate.sum() * 10_000)


def test_g2_countdown_uses_integer_open_time_minutes():
    times = pd.date_range("2026-01-01 06:59", periods=63, freq="min", tz="UTC")
    bars = pd.DataFrame({"bar_start": times,
                         "decision_time": times + pd.Timedelta(minutes=1),
                         "close": np.arange(len(times), dtype=float)})
    settlement = pd.DatetimeIndex([pd.Timestamp("2026-01-01 08:00", tz="UTC")])
    countdown = run.minutes_to_settlement(bars.bar_start, settlement)
    assert countdown[1] == 60
    assert countdown[-2] == 0
    assert countdown[-1] == -1


def test_limit_fills_only_when_touched():
    minutes = minute_frame(10)
    bars = run.aggregate_closed_ohlcv(minutes, 2)
    no_fill = run.simulate_limit(minutes, bars, np.array([1, 0, 0, 0, 0]),
                                 np.array([50.0] * 5), wait_bars=2, hold_bars=1)
    fill = run.simulate_limit(minutes, bars, np.array([1, 0, 0, 0, 0]),
                              np.array([103.0] * 5), wait_bars=2, hold_bars=1)
    assert no_fill.empty
    assert len(fill) == 1
    assert fill.entry_price.iloc[0] == 103.0


def test_segment_is_entry_time_even_when_trade_crosses_boundary():
    trade = pd.DataFrame({"entry_time": [pd.Timestamp("2025-12-31 23:59", tz="UTC")],
                          "exit_time": [pd.Timestamp("2026-01-01 01:00", tz="UTC")]})
    assert run.assign_segment(trade).iloc[0] == "DEV"


import pytest
