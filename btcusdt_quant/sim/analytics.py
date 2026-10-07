"""Inference helpers (spec D3). Every function returns a dict with a `reason`; none raises on degenerate input."""
from __future__ import annotations
from itertools import combinations
import math
import numpy as np, pandas as pd
from scipy import stats

EULER_GAMMA = 0.5772156649015329


def _clean(x) -> np.ndarray:
    x = np.asarray(x, float)
    return x[np.isfinite(x)] if x.ndim == 1 else x


def _flat_top(t: np.ndarray) -> np.ndarray:
    t = np.abs(t)
    return np.where(t <= .5, 1.0, np.where(t <= 1, 2 * (1 - t), 0.0))


def pw_block_length(x) -> float:
    """Politis-White (2004) automatic mean block length for the stationary bootstrap, with the
    Patton-Politis-White (2009) correction."""
    x = _clean(x); n = len(x)
    if n < 8 or x.std() == 0:
        return 1.0
    x = x - x.mean()
    kn = max(5, int(math.ceil(math.sqrt(math.log10(n)))))
    m_max = int(math.ceil(math.sqrt(n))) + kn
    b_max = math.ceil(min(3 * math.sqrt(n), n / 3))
    gamma0 = x @ x / n
    acov = np.array([x[k:] @ x[:-k] / n for k in range(1, m_max + 1)])
    rho = acov / gamma0
    bound = 2 * math.sqrt(math.log10(n) / n)
    m_hat = m_max
    for m in range(1, m_max - kn + 1):
        if np.all(np.abs(rho[m:m + kn]) < bound):
            m_hat = m
            break
    big_m = min(2 * m_hat, m_max)
    k = np.arange(1, big_m + 1)
    weights = _flat_top(k / big_m)
    g = 2 * np.sum(weights * k * acov[:big_m])
    g0 = gamma0 + 2 * np.sum(weights * acov[:big_m])
    d_sb = 2 * g0 ** 2
    if d_sb <= 0 or g == 0:
        return 1.0
    b = (2 * g ** 2 / d_sb) ** (1 / 3) * n ** (1 / 3)
    return float(min(max(b, 1.0), b_max))


def stationary_indices(n: int, block: float, reps: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.empty((reps, n), np.int64)
    idx[:, 0] = rng.integers(0, n, reps)
    restart = rng.random((reps, n)) < 1 / block
    starts = rng.integers(0, n, (reps, n))
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def pw_mean_ci(x, reps: int = 2000, seed: int = 0) -> dict:
    x = _clean(x)
    if not len(x):
        return {"mean": math.nan, "lower": math.nan, "upper": math.nan, "block": math.nan, "reason": "empty"}
    if x.std() == 0:
        return {"mean": float(x.mean()), "lower": float(x.mean()), "upper": float(x.mean()), "block": 1.0,
                "reason": "zero_variance"}
    block = pw_block_length(x)
    means = x[stationary_indices(len(x), block, reps, np.random.default_rng(seed))].mean(axis=1)
    lower, upper = np.quantile(means, [.025, .975])
    return {"mean": float(x.mean()), "lower": float(lower), "upper": float(upper), "block": block, "reason": "ok"}


def _long_run_variance(x: np.ndarray, lag: int) -> float:
    x = x - x.mean(); n = len(x)
    value = x @ x / n
    for k in range(1, min(lag, n - 1) + 1):
        value += 2 * (1 - k / (lag + 1)) * (x[k:] @ x[:-k] / n)
    return float(value)


def hac_mean_ci(x, lag: int = 7) -> dict:
    x = _clean(x)
    if not len(x):
        return {"mean": math.nan, "lower": math.nan, "upper": math.nan, "reason": "empty"}
    mean = float(x.mean())
    if x.std() == 0:
        return {"mean": mean, "lower": mean, "upper": mean, "reason": "zero_variance"}
    se = math.sqrt(max(_long_run_variance(x, lag), 0.0) / len(x))
    return {"mean": mean, "lower": mean - 1.96 * se, "upper": mean + 1.96 * se, "reason": "ok"}


def hac_alpha(y, x, lag: int = 7) -> dict:
    """Intercept of OLS y = alpha + beta x with a Newey-West (Bartlett, `lag`) 95% CI (plan 3 C19)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    nan = {"alpha": math.nan, "lower": math.nan, "upper": math.nan, "beta": math.nan}
    if len(y) < 3:
        return {**nan, "reason": "too_short"}
    if x.std() == 0:
        return {**nan, "reason": "x_constant"}
    X = np.column_stack([np.ones(len(y)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    u = X * (y - X @ beta)[:, None]
    s = u.T @ u
    for k in range(1, min(lag, len(y) - 1) + 1):
        g = u[k:].T @ u[:-k]
        s += (1 - k / (lag + 1)) * (g + g.T)
    inv = np.linalg.inv(X.T @ X)
    se = math.sqrt(max((inv @ s @ inv)[0, 0], 0.0))
    alpha = float(beta[0])
    return {"alpha": alpha, "lower": alpha - 1.96 * se, "upper": alpha + 1.96 * se, "beta": float(beta[1]), "se": se,
            "reason": "ok" if se > 0 else "zero_variance"}


def deflated_sharpe(x, trial_sharpes, n_trials: int) -> dict:
    x = _clean(x)
    if len(x) < 30:
        return {"sr": math.nan, "dsr": math.nan, "reason": "too_short"}
    if x.std(ddof=1) == 0:
        return {"sr": math.nan, "dsr": math.nan, "reason": "zero_variance"}
    sr = float(x.mean() / x.std(ddof=1))
    v = float(np.var(_clean(trial_sharpes), ddof=1)) if len(_clean(trial_sharpes)) > 1 else 0.0
    n = max(int(n_trials), 1)
    sr0 = 0.0 if n == 1 else math.sqrt(v) * ((1 - EULER_GAMMA) * stats.norm.ppf(1 - 1 / n)
                                              + EULER_GAMMA * stats.norm.ppf(1 - 1 / (n * math.e)))
    skew = float(stats.skew(x)); kurt = float(stats.kurtosis(x, fisher=False))
    denominator = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denominator <= 0:
        return {"sr": sr, "dsr": math.nan, "sr0": sr0, "reason": "bad_moments"}
    dsr = float(stats.norm.cdf((sr - sr0) * math.sqrt(len(x) - 1) / math.sqrt(denominator)))
    return {"sr": sr, "dsr": dsr, "sr0": sr0, "reason": "ok"}


def cscv_pbo(matrix: pd.DataFrame, splits: int = 16) -> dict:
    m = pd.DataFrame(matrix).dropna()
    m = m.T.drop_duplicates().T
    n_strategies = m.shape[1]
    if n_strategies < 2 or len(m) < splits:
        return {"pbo": math.nan, "n_strategies": n_strategies, "reason": "too_small"}
    blocks = np.array_split(np.arange(len(m)), splits)
    values = m.to_numpy(float)
    logits = []
    for chosen in combinations(range(splits), splits // 2):
        ins = np.concatenate([blocks[k] for k in chosen])
        outs = np.concatenate([blocks[k] for k in range(splits) if k not in chosen])
        def sharpe(rows):
            s = values[rows].std(axis=0, ddof=1)
            return np.where(s > 0, values[rows].mean(axis=0) / np.where(s > 0, s, 1), 0.0)
        best = int(np.argmax(sharpe(ins)))
        rank = stats.rankdata(sharpe(outs))[best]
        omega = rank / (n_strategies + 1)
        logits.append(math.log(omega / (1 - omega)))
    logits = np.array(logits)
    return {"pbo": float(np.mean(logits <= 0)), "n_strategies": n_strategies, "n_combinations": len(logits),
            "reason": "ok"}


def _bootstrap_means(d: np.ndarray, reps: int, seed: int) -> np.ndarray:
    block = float(np.mean([pw_block_length(d[:, k]) for k in range(d.shape[1])]))
    idx = stationary_indices(len(d), block, reps, np.random.default_rng(seed))
    return np.stack([d[:, k][idx].mean(axis=1) for k in range(d.shape[1])], axis=1)


def white_rc(diff, reps: int = 2000, seed: int = 0) -> dict:
    d = np.asarray(diff, float)
    d = d.reshape(len(d), -1) if d.size else d.reshape(0, 1)
    if not len(d):
        return {"p": math.nan, "reason": "empty"}
    if np.all(d.std(axis=0) == 0):
        return {"p": 1.0, "reason": "constant"}
    t = len(d); mean = d.mean(axis=0)
    observed = np.max(math.sqrt(t) * mean)
    boot = math.sqrt(t) * (_bootstrap_means(d, reps, seed) - mean)
    return {"p": float(np.mean(boot.max(axis=1) >= observed)), "statistic": float(observed), "reason": "ok"}


def hansen_spa(diff, reps: int = 2000, seed: int = 0, lag: int = 7) -> dict:
    d = np.asarray(diff, float)
    d = d.reshape(len(d), -1) if d.size else d.reshape(0, 1)
    if not len(d):
        return {"p": math.nan, "reason": "empty"}
    if np.all(d.std(axis=0) == 0):
        return {"p": 1.0, "reason": "constant"}
    t = len(d); mean = d.mean(axis=0)
    omega = np.sqrt([max(_long_run_variance(d[:, k], lag), 1e-300) for k in range(d.shape[1])])
    observed = max(0.0, float(np.max(math.sqrt(t) * mean / omega)))
    threshold = -math.sqrt(2 * math.log(math.log(t)))
    centre = mean * (math.sqrt(t) * mean / omega >= threshold)       # consistent SPA: keep bad models' mean
    boot = math.sqrt(t) * (_bootstrap_means(d, reps, seed) - centre) / omega
    stat = np.maximum(boot.max(axis=1), 0.0)
    return {"p": float(np.mean(stat >= observed)), "statistic": observed, "reason": "ok"}


def trade_monte_carlo(net, reps: int = 10000, seed: int = 0) -> dict:
    net = _clean(net)
    if not len(net):
        return {"final_q05": math.nan, "final_median": math.nan, "final_q95": math.nan, "dd_median": math.nan,
                "dd_q95": math.nan, "loss_prob": math.nan, "reason": "empty"}
    rng = np.random.default_rng(seed)
    paths = np.cumsum(net[rng.integers(0, len(net), (reps, len(net)))], axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((reps, 1)), paths], axis=1), axis=1)[:, 1:]
    drawdown = (peak - paths).max(axis=1)
    final = paths[:, -1]
    q05, median, q95 = np.quantile(final, [.05, .5, .95])
    return {"final_q05": float(q05), "final_median": float(median), "final_q95": float(q95),
            "dd_median": float(np.median(drawdown)), "dd_q95": float(np.quantile(drawdown, .95)),
            "loss_prob": float(np.mean(final < 0)), "reason": "ok"}
