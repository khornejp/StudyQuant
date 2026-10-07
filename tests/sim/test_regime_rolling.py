import numpy as np, pandas as pd
from btcusdt_quant.sim import regime, rolling

def grid(n, start="2024-01-01"):
    return pd.date_range(start, periods=n, freq="15min", tz="UTC")

def test_causal_percentile_excludes_current_and_needs_7_days():
    t = grid(8 * 96)
    out = regime.causal_percentile(np.ones(len(t)), t)
    first = int(np.flatnonzero(np.isfinite(out))[0])
    assert first == 7 * 96 and out[first] == 1.0
    x = np.r_[np.zeros(7 * 96), 5.0]
    assert regime.causal_percentile(x, grid(len(x)))[-1] == 1.0          # all earlier <= 5
    x = np.r_[np.arange(7 * 96, dtype=float), -1.0]
    assert regime.causal_percentile(x, grid(len(x)))[-1] == 0.0          # current not counted

def test_causal_percentile_30_day_window():
    x = np.r_[np.full(31 * 96, 10.0), np.zeros(96)]
    out = regime.causal_percentile(x, grid(len(x)))
    assert out[-1] < 1.0      # the 10s inside the last 30 days still rank above zero

def test_e_lookup_exact_then_prior_24h():
    t = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:00", "2024-01-02 00:00"], utc=True))
    frame = pd.DataFrame({"timestamp": t, "prediction_exc_4h": [100.0, 200.0]})
    d = pd.DatetimeIndex(pd.to_datetime(["2024-01-02 00:00", "2024-01-02 01:00", "2024-01-03 01:00"], utc=True))
    out = regime.e_bps(frame, d, "4h")
    assert out[0] == 200.0 and out[1] == 200.0 and np.isnan(out[2])

def test_gate_mask_nan_is_false():
    frame = pd.DataFrame({"timestamp": grid(3), "M": [.9, np.nan, .1]})
    assert regime.gate_mask(frame, pd.DatetimeIndex(frame.timestamp), "HIGH").tolist() == [True, False, False]
    assert regime.gate_mask(frame, pd.DatetimeIndex(frame.timestamp), "LOW").tolist() == [False, False, True]

def test_windows_schedule():
    w = rolling.WINDOWS
    assert len(w) == 10
    assert w[0].test_start == pd.Timestamp("2023-09-01", tz="UTC")
    assert w[-1].test_end == pd.Timestamp("2026-01-01", tz="UTC")
    for x in w:
        assert x.train_start == pd.Timestamp("2022-03-01", tz="UTC")
        assert x.train_end == x.val_start - pd.Timedelta(days=1)
        assert x.val_end == x.test_start and x.test_end <= pd.Timestamp("2026-01-01", tz="UTC")
    assert all(a.test_end == b.test_start for a, b in zip(w, w[1:]))

def test_gate_mask_uses_latest_15m_prediction_for_5m_decisions():
    frame = pd.DataFrame({"timestamp": grid(2), "M": [.9, .1]})
    d = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:05", "2024-01-01 00:20", "2024-01-01 00:35"], utc=True))
    assert regime.gate_mask(frame, d, "HIGH").tolist() == [True, False, False]
    assert regime.gate_mask(frame, d, "LOW").tolist() == [False, True, False]   # 00:35: 20 min old -> missing

def test_lookups_with_no_predictions():
    empty = pd.DataFrame({"timestamp": pd.Series(dtype="datetime64[ns, UTC]"), "M": pd.Series(dtype=float),
                          "prediction_exc_4h": pd.Series(dtype=float)})
    d = grid(3)
    assert np.isnan(regime.e_bps(empty, d, "4h")).all() and not regime.gate_mask(empty, d, "HIGH").any()
