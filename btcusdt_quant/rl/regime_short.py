"""REGIME-SHORT-24H (Codex spec 2026-10-11): ridge regression of the next-24h short net4 on causal futures regime
features at 4h decisions; short when the prediction is > 0. Pure numpy; data access and execution live in
scripts/precompute_rl_allocator.py (regime-short).

Label (training only): short from the close of the decision bar to the close 24h later, minus the 4 bps maker round
trip, plus the funding a short receives for settlements in (T, T + 24h]. A training row is kept only if its label
ends at least `embargo` before the validation start. Features: train-window median / IQR, NaN -> 0 (median), clip
+-10. Lambda chosen in {1, 10, 100} by train-internal year-block CV (quarter blocks when the train window holds a
single calendar year); CV score = mean held-out block net of the rule (sum of labels where prediction > 0), ties ->
lower held-out MSE, then larger lambda."""
from __future__ import annotations
import numpy as np, pandas as pd

FEATURES = ("ret_1h", "ret_4h", "ret_24h", "ret_7d", "rv_1h", "rv_4h", "rv_24h", "rv_7d", "funding_z90",
            "funding_age_h", "oi_chg_1h", "oi_chg_4h", "oi_chg_24h", "oi_z", "global_ls_z", "top_ls_z", "taker_lsr_z",
            "premium_z")
LAMBDAS = (1.0, 10.0, 100.0)
MIN = 60_000_000_000
HOLD_MIN = 1440
COST_BPS = 4.0


def short_labels(t: np.ndarray, c: np.ndarray, ft: np.ndarray, fr: np.ndarray, d: np.ndarray, hold: int = HOLD_MIN):
    """Decision bar index d (decision time t[d] + 1m). Returns label (bps) and label end time (ns); NaN when the hold
    runs past the data."""
    d = np.asarray(d, np.int64)
    ok = d + hold < len(t)
    e = np.minimum(d + hold, len(t) - 1)
    gross = -(c[e] / c[d] - 1.0) * 1e4
    t0, t1 = t[d] + MIN, t[e] + MIN
    cf = np.concatenate([[0.0], np.cumsum(fr * 1e4)])                    # short receives +rate
    fund = cf[np.searchsorted(ft, t1, "right")] - cf[np.searchsorted(ft, t0, "right")]
    lab = np.where(ok, gross - COST_BPS + fund, np.nan)
    return lab, np.where(ok, t1, np.iinfo(np.int64).max)


def long_labels(t: np.ndarray, c: np.ndarray, ft: np.ndarray, fr: np.ndarray, d: np.ndarray, hold: int = HOLD_MIN):
    """Long label: +24h price return - 4 bps - funding a long pays for settlements in (T, T + 24h]."""
    y_s, lend = short_labels(t, c, ft, fr, d, hold)
    d = np.asarray(d, np.int64)
    e = np.minimum(d + hold, len(t) - 1)
    gross = (c[e] / c[d] - 1.0) * 1e4
    t0, t1 = t[d] + MIN, t[e] + MIN
    cf = np.concatenate([[0.0], np.cumsum(fr * 1e4)])
    fund = cf[np.searchsorted(ft, t1, "right")] - cf[np.searchsorted(ft, t0, "right")]
    return np.where(np.isfinite(y_s), gross - COST_BPS - fund, np.nan), lend


def fit_norm(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(X, axis=0)
    q1, q3 = np.nanpercentile(X, 25, axis=0), np.nanpercentile(X, 75, axis=0)
    sc = np.where(q3 > q1, q3 - q1, 1.0)
    return np.nan_to_num(med), sc


def apply_norm(X: np.ndarray, med, sc) -> np.ndarray:
    return np.clip(np.nan_to_num((X - med) / sc, nan=0.0), -10, 10)


def ridge(X: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, float]:
    """Ridge with an unpenalized intercept."""
    xm, ym = X.mean(0), y.mean()
    Xc = X - xm
    w = np.linalg.solve(Xc.T @ Xc + lam * np.eye(X.shape[1]), Xc.T @ (y - ym))
    return w, float(ym - xm @ w)


def block_ids(T: np.ndarray) -> np.ndarray:
    ts = pd.to_datetime(T, utc=True)
    years = ts.year.to_numpy()
    if len(np.unique(years)) >= 2:
        return years
    return years * 10 + (ts.quarter.to_numpy())


def cv_lambda(X: np.ndarray, y: np.ndarray, T: np.ndarray, lend: np.ndarray, lambdas=LAMBDAS) -> tuple[float, dict]:
    """Block CV inside the train window; a training row is dropped if its label end reaches the held-out block."""
    blk = block_ids(T)
    res = {}
    for lam in lambdas:
        nets, mses = [], []
        for b in np.unique(blk):
            te = blk == b
            start = T[te].min()
            tr = ~te & ((lend < start) | (T > T[te].max() + HOLD_MIN * MIN))
            med, sc = fit_norm(X[tr])
            w, b0 = ridge(apply_norm(X[tr], med, sc), y[tr], lam)
            p = apply_norm(X[te], med, sc) @ w + b0
            nets.append(float(y[te][p > 0].sum()))
            mses.append(float(np.mean((p - y[te]) ** 2)))
        res[lam] = {"cv_net_mean": float(np.mean(nets)), "cv_mse": float(np.mean(mses)), "blocks": len(nets)}
    best = sorted(lambdas, key=lambda l: (-res[l]["cv_net_mean"], res[l]["cv_mse"], -l))[0]
    return best, res
