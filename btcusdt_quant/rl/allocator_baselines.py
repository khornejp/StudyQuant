"""Static allocation baselines (Codex design section 4, step 6) with an analytic scorer.

Linearity: a static book with weights w (each in [0, 1], sum <= 2) never hits the 2.0 gross cap (each sleeve holds at
most one reserved opportunity at a time; an exit at tau releases its cap before entries at tau), so its step P&L and
turnover are sum_s w_s x (unit P&L / turnover of sleeve s). Unit series come from the env itself (static book with a
unit weight vector, availability-gated, flat start, terminal mark + fee); every candidate is then scored with matrix
products, no per-candidate env replay. The scorer <-> env parity sample checks the linearity claim.

Ranking (per fold, train window only, all 6 exec cells): lexicographic
  1. min over cells of net4 (desc)            2. min over cells of bootstrap p05 of the daily mean (desc)
  3. max over cells of MDD (asc)              4. mean over cells of turnover (asc)
  5. tie-break: smaller total weight, then the weight vector in ascending lexicographic order.
Bootstrap: stationary (Politis-Romano), mean block 60 d, 10,000 resamples, seed 20261010, same resample indices for
all candidates of a (cell, window)."""
from __future__ import annotations
import itertools
import numpy as np, pandas as pd
from . import allocator_contracts as C

LEVEL_Q = (0, 1, 2, 3, 4)                     # quarters
BOOT_N, BOOT_BLOCK, BOOT_SEED = 10_000, 60, 20261010


def candidate_grid() -> np.ndarray:
    """All weight vectors in {0, .25, .5, .75, 1}^7 with sum <= 2 (5,595)."""
    g = np.array([v for v in itertools.product(LEVEL_Q, repeat=len(C.SLEEVES)) if sum(v) <= 8], float) / 4.0
    return g


def named_baselines() -> dict:
    return {"STATIC_EQUAL_2_7": np.full(len(C.SLEEVES), 2 / 7),
            "G3_ONLY": np.array([1.0, 1.0, 0, 0, 0, 0, 0])}


def stationary_indices(n: int, n_boot: int = BOOT_N, block: int = BOOT_BLOCK, seed: int = BOOT_SEED) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (circular, geometric blocks with mean `block`)."""
    rng = np.random.default_rng(seed)
    new = rng.random((n_boot, n)) < 1.0 / block
    new[:, 0] = True
    starts = rng.integers(0, n, size=(n_boot, n))
    pos = np.broadcast_to(np.arange(n), (n_boot, n))
    last = np.maximum.accumulate(np.where(new, pos, 0), axis=1)
    return (np.take_along_axis(starts, last, axis=1) + pos - last) % n


def score(unit_step: np.ndarray, unit_turn: np.ndarray, day_id: np.ndarray, W: np.ndarray,
          boot_idx: np.ndarray, chunk: int = 512) -> pd.DataFrame:
    """unit_step [T, 7] per-step unit net4, unit_turn [T, 7] per-step unit turnover (bps), day_id [T] UTC day index of
    each step (0..D-1). W [n, 7] candidate weights. Returns net4, mdd (step equity incl. the 0 start), turnover,
    boot_p05 (daily mean), n_days."""
    D = int(day_id.max()) + 1
    daily = np.zeros((D, unit_step.shape[1]))
    np.add.at(daily, day_id, unit_step)
    bmeans = np.stack([daily[:, k][boot_idx].mean(axis=1) for k in range(daily.shape[1])], axis=1)  # [n_boot, 7]
    eq = np.cumsum(unit_step, axis=0)                          # [T, 7]
    out = {"net4": W @ unit_step.sum(0), "turnover": W @ unit_turn.sum(0), "n_days": np.full(len(W), D)}
    mdd = np.zeros(len(W))
    p05 = np.zeros(len(W))
    for a in range(0, len(W), chunk):
        w = W[a:a + chunk]
        e = eq @ w.T                                           # [T, c]
        peak = np.maximum(np.maximum.accumulate(e, axis=0), 0.0)
        mdd[a:a + chunk] = (peak - e).max(axis=0)
        p05[a:a + chunk] = np.quantile(bmeans @ w.T, 0.05, axis=0)
    out["mdd"], out["boot_p05"] = mdd, p05
    return pd.DataFrame(out)


def rank(cells: dict, W: np.ndarray) -> pd.DataFrame:
    """cells: {cell: score frame}. Lexicographic ranking (see module docstring); row 0 = selected."""
    f = pd.DataFrame({"cand": np.arange(len(W)),
                      "min_net4": np.min([c.net4.to_numpy() for c in cells.values()], axis=0),
                      "min_boot_p05": np.min([c.boot_p05.to_numpy() for c in cells.values()], axis=0),
                      "max_mdd": np.max([c.mdd.to_numpy() for c in cells.values()], axis=0),
                      "mean_turnover": np.mean([c.turnover.to_numpy() for c in cells.values()], axis=0),
                      "sum_w": W.sum(1)})
    for k, s in enumerate(C.SLEEVES):
        f[f"w_{s}"] = W[:, k]
    keys = ["min_net4", "min_boot_p05", "max_mdd", "mean_turnover", "sum_w"] + [f"w_{s}" for s in C.SLEEVES]
    asc = [False, False, True, True, True] + [True] * len(C.SLEEVES)
    return f.sort_values(keys, ascending=asc, kind="mergesort").reset_index(drop=True)
