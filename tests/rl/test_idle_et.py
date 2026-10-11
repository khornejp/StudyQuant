"""G3-IDLE-EXTRATREES helpers: strict idle, side modes, median imputation, determinism."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import idle_et as IE


def test_idle_strict():
    f = pd.DataFrame({c: [0, 0, 0] for c in IE.IDLE_COLS})
    f.loc[1, "G3_SHORT_pending"] = 1
    f.loc[2, "G3_LONG_signal_active"] = np.nan
    assert IE.idle(f).tolist() == [True, False, False]


def test_sides():
    p = np.array([2.0, -2.0, 0.5, -0.5])
    assert IE.sides(p, "BOTH", 1.0).tolist() == [1, -1, 0, 0]
    assert IE.sides(p, "LONG", 1.0).tolist() == [1, 0, 0, 0]
    assert IE.sides(p, "SHORT", 1.0).tolist() == [0, -1, 0, 0]


def test_model_impute_and_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, 4))
    y = 5 * X[:, 0] + rng.normal(size=500)
    X[::7, 1] = np.nan
    a, b = IE.Model(X, y), IE.Model(X, y)
    assert np.array_equal(a.predict(X), b.predict(X)) and np.isfinite(a.predict(X)).all()
    assert np.isclose(a.med[1], np.nanmedian(X[:, 1])) and np.corrcoef(a.predict(X), y)[0, 1] > 0.8
