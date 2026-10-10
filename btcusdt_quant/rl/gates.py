"""Admission gates (Codex 2026-10-11, consistent for every book): one continuous 2022-01-01..2025-12-31 daily net4
series per execution cell (same boundaries for candidate and baseline), stationary bootstrap (Politis-Romano, seed
20261010, 10,000 draws, chunked exactly as out/run_new_model_batch2_20261010.stationary_boot_p05), maker 4 bps.

  absolute    : year x cell net4 > 0 (24/24), year x cell closed >= 30 (24/24), pooled daily boot60 p05 > 0 (6/6)
  replacement : paired daily excess (candidate - baseline, same day, same cell) pooled boot60 p05 > 0 (6/6)
  diagnostics : per-year boot p05 at 20/60/120 d (72), MDD, top-2 month share (reported, never gating)."""
from __future__ import annotations
import numpy as np, pandas as pd

SEED, NBOOT, BLOCKS, MAIN_BLOCK = 20261010, 10_000, (20, 60, 120), 60
YEARS = (2022, 2023, 2024, 2025)
START, END = pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC")
N_DAYS = (END - START).days


def boot_p05(x: np.ndarray, block: int, n_boot: int = NBOOT, seed: int = SEED) -> float:
    """p05 of the stationary-bootstrap mean (same RNG stream as Batch-2 stationary_boot_p05)."""
    x = np.asarray(x, float)
    n = len(x)
    rng = np.random.default_rng(seed)
    means = []
    for c in range(0, n_boot, 1000):
        k = min(1000, n_boot - c)
        new = rng.random((k, n)) < 1.0 / block
        new[:, 0] = True
        starts = rng.integers(0, n, size=(k, n))
        pos = np.broadcast_to(np.arange(n), (k, n))
        last = np.maximum.accumulate(np.where(new, pos, 0), axis=1)
        idx = (np.take_along_axis(starts, last, axis=1) + pos - last) % n
        means.append(x[idx].mean(axis=1))
    return float(np.quantile(np.concatenate(means), 0.05))


def year_slices() -> dict:
    out = {}
    for y in YEARS:
        a = (pd.Timestamp(f"{y}-01-01", tz="UTC") - START).days
        b = (pd.Timestamp(f"{y + 1}-01-01", tz="UTC") - START).days
        out[y] = slice(a, b)
    return out


def mdd(daily: np.ndarray) -> float:
    eq = np.r_[0.0, np.cumsum(daily)]
    return float((np.maximum.accumulate(eq) - eq).max())


def top2_share(daily: np.ndarray) -> float | None:
    days = pd.date_range(START, periods=len(daily), freq="D")
    mon = pd.Series(daily, index=days).groupby(days.strftime("%Y-%m")).sum()
    tot = float(daily.sum())
    return float(mon.sort_values(ascending=False).iloc[:2].sum() / tot) if tot > 0 else None


def evaluate(cells: dict, baseline: dict | None = None) -> dict:
    """cells: {cell: {"daily": [N_DAYS] net4, "closed": {year: n}}}; baseline: {cell: [N_DAYS] daily} or None."""
    ys = year_slices()
    out = {"cells": {}}
    net_ok, cl_ok, pool_ok, rep_ok, diag_pos = [], [], [], [], 0
    for c, v in cells.items():
        d = np.asarray(v["daily"], float)
        if len(d) != N_DAYS:
            raise ValueError(f"{c}: daily series must cover 2022-01-01..2025-12-31 ({N_DAYS} days), got {len(d)}")
        r = {"pooled_net4": float(d.sum()), "pooled_boot_p05": {str(b): boot_p05(d, b) for b in BLOCKS},
             "mdd": mdd(d), "top2_month_share": top2_share(d), "years": {}}
        for y, sl in ys.items():
            yy = {"net4": float(d[sl].sum()), "closed": int(v["closed"][y]),
                  "boot_p05": {str(b): boot_p05(d[sl], b) for b in BLOCKS}}
            r["years"][str(y)] = yy
            net_ok.append(yy["net4"] > 0)
            cl_ok.append(yy["closed"] >= 30)
            diag_pos += sum(p > 0 for p in yy["boot_p05"].values())
        pool_ok.append(r["pooled_boot_p05"][str(MAIN_BLOCK)] > 0)
        if baseline is not None:
            ex = d - np.asarray(baseline[c], float)
            r["paired_excess"] = {"net4": float(ex.sum()), "boot_p05": {str(b): boot_p05(ex, b) for b in BLOCKS}}
            rep_ok.append(r["paired_excess"]["boot_p05"][str(MAIN_BLOCK)] > 0)
        out["cells"][c] = r
    out["absolute"] = {"year_cell_net4>0": f"{sum(net_ok)}/{len(net_ok)}",
                       "year_cell_closed>=30": f"{sum(cl_ok)}/{len(cl_ok)}",
                       "pooled_boot60_p05>0": f"{sum(pool_ok)}/{len(pool_ok)}",
                       "pass": bool(all(net_ok) and all(cl_ok) and all(pool_ok))}
    if baseline is not None:
        out["replacement"] = {"paired_excess_boot60_p05>0": f"{sum(rep_ok)}/{len(rep_ok)}", "pass": bool(all(rep_ok))}
    out["diagnostics"] = {"year_cell_block_boot_p05>0": f"{diag_pos}/{len(cells) * len(YEARS) * len(BLOCKS)}"}
    return out
