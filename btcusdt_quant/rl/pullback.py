"""LONG-PULLBACK-GBM-24H-r1 (Codex spec 2026-10-11): long-only entries in G3 pullbacks (G3_LONG target 0, slow G3
score > 0, fast score < 0), LightGBM huber regressor of the 24h long net4 (4 bps + actual funding), entry threshold =
an inner blocked-OOF prediction quantile in {0.50, 0.65, 0.80}. Pure helpers; data and execution in the script."""
from __future__ import annotations
import numpy as np

QUANTILES = (0.50, 0.65, 0.80)
GBM_PARAMS = dict(objective="huber", alpha=0.9, n_estimators=300, learning_rate=0.03, num_leaves=7, max_depth=3,
                  min_child_samples=120, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_alpha=1.0,
                  reg_lambda=10.0, random_state=20261011, n_jobs=1, deterministic=True, force_row_wise=True,
                  verbose=-1)
EXTRA = ("fast_score", "slow_score", "svi42", "svi180", "sigma_ann", "funding_minus_med90", "funding_mad90")


def universe(g3_long_side: np.ndarray, slow: np.ndarray, fast: np.ndarray) -> np.ndarray:
    """Long-term uptrend with a short-term pullback while G3_LONG itself is flat (NaN comparisons -> False)."""
    with np.errstate(invalid="ignore"):
        return (np.asarray(g3_long_side) == 0) & (slow > 0) & (fast < 0)


def fit(X: np.ndarray, y: np.ndarray):
    import lightgbm as lgb
    m = lgb.LGBMRegressor(**GBM_PARAMS)
    m.fit(X, y)
    return m
