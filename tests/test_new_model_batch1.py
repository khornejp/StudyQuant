import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_P = Path(__file__).resolve().parents[1] / "out/run_new_model_batch1_20261010.py"
_spec = importlib.util.spec_from_file_location("nm1", _P)
nm1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm1)


def test_limit_price_ticks():
    assert nm1.limit_price(100000.0, 1, 2) == np.floor(100000 * (1 - 2e-4) / 0.1 + 1e-9) * 0.1
    assert abs(nm1.limit_price(100000.0, 1, 2) - 99980.0) < 1e-6
    assert abs(nm1.limit_price(100000.0, -1, 2) - 100020.0) < 1e-6
    assert abs(nm1.limit_price(100000.03, 1, 0) - 100000.0) < 1e-6
    assert abs(nm1.limit_price(100000.03, -1, 0) - 100000.1) < 1e-6


def test_first_fill_requires_open_and_penetration():
    lim = 100.0
    o = np.array([101, 99.0, 101, 101])        # bar1 gaps through (open below limit)
    l = np.array([100.0, 98.0, 99.999, 99.99])  # bar0 touch only, bar2 < 0.5bp, bar3 penetrates
    h = o + 1
    assert nm1.first_fill(o, h, l, 0, 4, lim, buy=True) == 3
    assert nm1.first_fill(o, h, l, 0, 3, lim, buy=True) == -1      # TTL ends before fill
    # sell side mirror
    o2 = np.array([99.0, 101.0, 99.0]); h2 = np.array([100.0, 102.0, 100.01]); l2 = o2 - 1
    assert nm1.first_fill(o2, h2, l2, 0, 3, lim, buy=False) == 2


def test_exit_requotes_from_new_close():
    n = 200
    c = np.full(n, 100000.0); o = c.copy(); h = c + 1.0; l = c - 1.0
    # long exit: sell quote 100020.0 never reached in first 60m; close moves to 99000 -> requote 99019.8
    c[60:] = 99000.0; o[60:] = 99000.0; h[60:] = 99000.0; l[60:] = 98990.0
    h[100] = 99030.0
    j, px = nm1.exit_fill(o, h, l, c, 0, 1, n)
    assert j == 100 and abs(px - 99019.8) < 1e-6


def test_event_engine_no_same_bar_fill_and_funding():
    n = 3000
    t = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    c = np.full(n, 100000.0)
    frame = pd.DataFrame({"open_time": t, "open": c, "high": c + 30, "low": c - 30, "close": c,
                          "volume": 1.0, "taker_buy_base_volume": 0.5})
    fund = pd.DataFrame({"time": [t[500] + pd.Timedelta(seconds=1)], "rate": [0.0001]})
    m = nm1.Market(frame, fund)
    tr, dg = nm1.run_event(m, np.array([10]), np.array([1]), 1000, 2, 15, 0, n)
    assert dg["orders"] == 1 and len(tr) == 1
    r = tr[0]
    assert r["entry_idx"] == 11 and r["exit_decision_idx"] == 11 + 1000 and r["exit_idx"] > r["exit_decision_idx"]
    assert abs(r["funding_bps"] - (-1.0)) < 1e-9          # long pays 1 bp
    assert abs(r["net4_bps"] - (r["gross_bps"] + r["funding_bps"] - 4)) < 1e-9


def test_trailing_quantile_and_z_strictly_past():
    x = pd.Series(np.arange(10, dtype=float))
    q = nm1.trailing_quantile(x, 1.0, 3, 3).to_numpy()
    assert np.isnan(q[2]) and q[3] == 2.0 and q[9] == 8.0       # max of x[t-3..t-1], never x[t]
    v = np.array([1.0, 2, 3, 4, 5, 100])
    z = nm1.trailing_robust_z(v, 5, 5)
    med, mad = 3.0, 1.0
    assert np.all(np.isnan(z[:5])) and abs(z[5] - (100 - med) / (1.4826 * mad)) < 1e-9
    v2 = np.array([1.0, np.nan, 3, 4, 5, 100])
    z2 = nm1.trailing_robust_z(v2, 5, 4)
    assert abs(z2[5] - (100 - 3.5) / (1.4826 * 1.0)) < 1e-9


def test_tsmom_score_uses_closed_bars():
    n = 1440 * 40
    t = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    c = 100 * np.exp(np.linspace(0, 0.4, n)) * (1 + 0.001 * np.sin(np.arange(n)))
    frame = pd.DataFrame({"open_time": t, "open": c, "high": c, "low": c, "close": c,
                          "volume": 1.0, "taker_buy_base_volume": 0.5})
    m = nm1.Market(frame, pd.DataFrame({"time": pd.to_datetime([], utc=True), "rate": []}))
    f = nm1.tsmom_features(m, 1440, (5, 10), 5)
    assert (f.dec_idx % 1440 == 1439).all()
    assert np.isnan(f.score.iloc[9]) and f.score.iloc[-1] > 0
