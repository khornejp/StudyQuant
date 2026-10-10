"""LONG-PULLBACK helpers: universe rule, fixed deterministic GBM."""
import numpy as np
from btcusdt_quant.rl import pullback as PB


def test_universe_rule():
    side = np.array([0, 0, 1, 0, 0])
    slow = np.array([1.0, 1.0, 1.0, -1.0, np.nan])
    fast = np.array([-1.0, 1.0, -1.0, -1.0, -1.0])
    assert PB.universe(side, slow, fast).tolist() == [True, False, False, False, False]


def test_gbm_fixed_and_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 5))
    y = X[:, 0] * 10 + rng.normal(size=600)
    a, b = PB.fit(X, y).predict(X), PB.fit(X, y).predict(X)
    assert np.array_equal(a, b) and np.corrcoef(a, y)[0, 1] > 0.8
    assert PB.GBM_PARAMS["objective"] == "huber" and PB.GBM_PARAMS["n_estimators"] == 300
