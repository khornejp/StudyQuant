"""REGIME-SHORT-24H helpers (btcusdt_quant/rl/regime_short.py): label, ridge, normalization, CV embargo."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import regime_short as RS

MIN = RS.MIN


def test_short_label_formula_and_funding_window():
    n = 4000
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * MIN).astype(np.int64)
    c = np.linspace(100, 90, n)
    ft = t[[100, 600, 2000]] + MIN // 2                 # inside (T, T+24h] for d=10 only the first two
    fr = np.array([1e-4, 2e-4, 5e-4])
    y, lend = RS.short_labels(t, c, ft, fr, np.array([10, 3000]))
    want = -(c[1450] / c[10] - 1) * 1e4 - 4 + (1e-4 + 2e-4) * 1e4
    assert np.isclose(y[0], want) and lend[0] == t[1450] + MIN
    assert np.isnan(y[1])                              # hold past the data end


def test_ridge_recovers_and_unpenalized_intercept():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, 3))
    y = X @ np.array([2.0, -1.0, 0.0]) + 5 + rng.normal(0, 0.01, 500)
    w, b = RS.ridge(X, y, 1e-6)
    assert np.allclose(w, [2, -1, 0], atol=0.01) and abs(b - 5) < 0.01
    w2, b2 = RS.ridge(X, y, 1e6)
    assert np.abs(w2).max() < 0.01 and abs(b2 - y.mean()) < 0.05


def test_norm_nan_and_cv_embargo():
    X = np.array([[1.0, np.nan], [2.0, 4.0], [3.0, 6.0], [4.0, np.nan]])
    med, sc = RS.fit_norm(X)
    Z = RS.apply_norm(X, med, sc)
    assert np.isfinite(Z).all() and Z[0, 1] == 0.0
    T = pd.date_range("2021-01-01", "2022-12-31", freq="4h", tz="UTC").as_unit("ns").asi8
    rng = np.random.default_rng(1)
    Xf = rng.normal(size=(len(T), 4))
    y = Xf[:, 0] * 10 + rng.normal(size=len(T))
    lend = T + RS.HOLD_MIN * MIN
    lam, res = RS.cv_lambda(Xf, y, T, lend)
    assert lam in RS.LAMBDAS and all(r["blocks"] == 2 for r in res.values())
    assert set(RS.block_ids(T[:100])) == {20211}         # one year -> quarter blocks


def test_dev_loader_refuses_test_sources(tmp_path):
    import pytest
    from btcusdt_quant.rl import dev_data as DD, sleeve_precompute as sp
    with pytest.raises(sp.TestAccessError):
        DD.assert_dev_path(DD.ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot/market_1m.parquet")
    with pytest.raises(sp.TestAccessError):
        DD.assert_dev_path(tmp_path / "BTCUSDT-fundingRate-2026-01.zip")
    for nm in ("BTCUSDT-fundingRate-2025-12.zip", "BTCUSDT-fundingRate-2026-02.zip"):
        (tmp_path / nm).write_bytes(b"x")
    assert [p.name for p in DD.dev_funding_files(tmp_path)] == ["BTCUSDT-fundingRate-2025-12.zip"]


def test_long_label_is_mirror_minus_costs():
    n = 3000
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * MIN).astype(np.int64)
    c = np.linspace(100, 110, n)
    ft = t[[50]] + MIN // 2
    fr = np.array([2e-4])
    ys, _ = RS.short_labels(t, c, ft, fr, np.array([10]))
    yl, _ = RS.long_labels(t, c, ft, fr, np.array([10]))
    g = (c[1450] / c[10] - 1) * 1e4
    assert np.isclose(yl[0], g - 4 - 2) and np.isclose(ys[0], -g - 4 + 2)


def test_ma100_uses_completed_days_only():
    import importlib.util, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("pra_ma_t", root / "scripts/precompute_rl_allocator.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    days = 105
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(days * 1440) * MIN).astype(np.int64)
    c = np.repeat(np.arange(1, days + 1, dtype=float), 1440)
    m = type("M", (), {"t": t, "c": c})()
    T = np.array([pd.Timestamp("2024-04-10 04:00", tz="UTC").value])   # day index 100 running
    d = np.searchsorted(t, T) - 1
    bear, ma = mod.ma100_bear(m, T, d)
    assert np.isclose(ma[0], np.arange(1, 101).mean())                   # days 0..99, running day excluded
    c2 = c.copy()
    c2[d[0] + 1:] = 1e6                                                  # future tamper
    m2 = type("M", (), {"t": t, "c": c2})()
    assert np.isclose(mod.ma100_bear(m2, T, d)[1][0], ma[0])


def test_dev_market_hash_is_slice_hash():
    from btcusdt_quant.rl import dev_data as DD
    f = pd.DataFrame({"open_time": pd.to_datetime([0, 60_000_000_000], utc=True), "open": [1.0, 2.0]})
    g = f.copy()
    g.loc[1, "open"] = 2.5
    assert DD.frame_sha(f) == DD.frame_sha(f.copy()) and DD.frame_sha(f) != DD.frame_sha(g)
    import inspect
    # the DEV market is now a DEV-only physical file (built from daily archives < 2026); the mixed file is not read
    assert inspect.signature(DD.load_dev).parameters["market"].default == DD.DEV_MARKET != DD.MIXED_MARKET
    assert all(p.name < "BTCUSDT-1m-2026" for p in DD.dev_day_files())
