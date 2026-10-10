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
