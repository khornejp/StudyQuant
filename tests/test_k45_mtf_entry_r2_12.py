import pandas as pd

from out import run_k45_mtf_entry_r2_12 as run


def _minutes(n=61):
    time = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    return pd.DataFrame({
        "open_time": time, "open": range(n), "high": range(1, n + 1),
        "low": range(n), "close": range(1, n + 1), "volume": 1.0,
    })


def test_upper_bars_include_only_closed_utc_bars():
    bars = run.aggregate_closed_ohlcv(_minutes(), 60)
    assert len(bars) == 1
    assert bars.iloc[0].decision_time == pd.Timestamp("2026-01-01 01:00", tz="UTC")
    assert bars.iloc[0].close == 60
    assert bars.iloc[0].volume == 60


def test_limit_fills_only_on_touch_and_at_limit():
    lower = pd.DataFrame({
        "decision_time": pd.to_datetime(["2026-01-01 00:15Z", "2026-01-01 00:30Z"]),
        "open": [100.0, 100.0], "high": [101.0, 102.0], "low": [99.5, 98.0],
        "close": [100.0, 101.0], "atr": [4.0, 4.0],
    })
    miss = run.find_entry(lower.assign(low=[99.5, 99.1]), lower.decision_time.iloc[0] - pd.Timedelta("15min"),
                          1, "E1", 1.0, 100.0, 30)
    fill = run.find_entry(lower, lower.decision_time.iloc[0] - pd.Timedelta("15min"),
                          1, "E1", .5, 100.0, 30)
    assert miss is None
    assert fill[0] == lower.decision_time.iloc[1]
    assert fill[1] == 98.0


def test_confirmation_does_not_use_data_after_entry():
    lower = pd.DataFrame({
        "decision_time": pd.to_datetime(["2026-01-01 00:15Z", "2026-01-01 00:30Z", "2026-01-01 00:45Z"]),
        "open": [99.0, 100.0, 1.0], "high": [100.0, 103.0, 999.0],
        "low": [98.0, 99.0, 0.0], "close": [99.0, 102.0, 999.0], "atr": [1.0] * 3,
    })
    args = (pd.Timestamp("2026-01-01 00:00Z"), 1, "E2", None, 99.0, 60)
    before = run.find_entry(lower, *args)
    after = run.find_entry(lower.assign(open=[99.0, 100.0, -999.0], close=[99.0, 102.0, -999.0]), *args)
    assert before == after == (pd.Timestamp("2026-01-01 00:30Z"), 102.0)


def test_single_book_never_overlaps():
    candidates = pd.DataFrame({
        "signal_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z", "2026-01-01 01:00Z"]),
        "entry_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 01:30Z", "2026-01-01 01:00Z"]),
        "exit_time": pd.to_datetime(["2026-01-01 01:00Z", "2026-01-01 02:30Z", "2026-01-01 02:00Z"]),
    })
    accepted, dropped = run.admit_single_positions(candidates)
    assert accepted.index.tolist() == [0, 2]
    assert dropped.index.tolist() == [1]
    assert run.max_concurrent(accepted) == 1
