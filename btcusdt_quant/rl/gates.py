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
CELLS = ("o2_p0.5", "o2_p1.0", "o2_p2.0", "o5_p0.5", "o5_p1.0", "o5_p2.0")


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
    """cells: exactly the 6 execution cells, {cell: {"daily": [N_DAYS] net4, "closed": {year: n}, optional "daily8":
    [N_DAYS] net8 (report only)}}; baseline: {cell: [N_DAYS] daily} for the same 6 cells, or None."""
    if set(cells) != set(CELLS) or len(cells) != len(CELLS):
        raise ValueError(f"gate needs exactly the 6 cells {CELLS}, got {sorted(cells)}")
    if baseline is not None and set(baseline) != set(CELLS):
        raise ValueError(f"baseline needs exactly the 6 cells {CELLS}, got {sorted(baseline)}")
    ys = year_slices()
    out = {"cells": {}}
    net_ok, cl_ok, pool_ok, rep_ok, diag_pos = [], [], [], [], 0
    for c, v in cells.items():
        d = np.asarray(v["daily"], float)
        if len(d) != N_DAYS:
            raise ValueError(f"{c}: daily series must cover 2022-01-01..2025-12-31 ({N_DAYS} days), got {len(d)}")
        r = {"pooled_net4": float(d.sum()), "pooled_boot_p05": {str(b): boot_p05(d, b) for b in BLOCKS},
             "mdd": mdd(d), "top2_month_share": top2_share(d), "years": {}}
        if "daily8" in v:
            r["pooled_net8_report_only"] = float(np.asarray(v["daily8"], float).sum())
        for y, sl in ys.items():
            yy = {"net4": float(d[sl].sum()), "closed": int(v["closed"][y]),
                  "boot_p05": {str(b): boot_p05(d[sl], b) for b in BLOCKS}}
            if "daily8" in v:
                yy["net8_report_only"] = float(np.asarray(v["daily8"], float)[sl].sum())
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


def evaluate_period(cells: dict, start_year: int, end_year: int, baseline: dict | None = None,
                    comparators: dict | None = None) -> dict:
    """Generic DEV-period gate used by A8. ``evaluate`` above remains the frozen 2022-2025 implementation.

    ``comparators`` maps a report name to the same ``cell -> daily`` shape as ``baseline``. Optional A8 execution
    fields in each cell are gated when present: max hold, cap violations, identity error, faults, and side RT counts.
    """
    if start_year > end_year or start_year < 2021 or end_year >= 2026:
        raise ValueError("period must be ordered and wholly before TEST/2026")
    if set(cells) != set(CELLS) or len(cells) != len(CELLS):
        raise ValueError(f"gate needs exactly the 6 cells {CELLS}, got {sorted(cells)}")
    all_base = ({"baseline": baseline} if baseline is not None else {}) | (comparators or {})
    for name, base in all_base.items():
        if set(base) != set(CELLS):
            raise ValueError(f"{name} needs exactly the 6 cells {CELLS}, got {sorted(base)}")
    years = tuple(range(start_year, end_year + 1))
    start = pd.Timestamp(f"{start_year}-01-01", tz="UTC")
    end = pd.Timestamp(f"{end_year + 1}-01-01", tz="UTC")
    n_days = (end - start).days
    slices = {y: slice((pd.Timestamp(f"{y}-01-01", tz="UTC") - start).days,
                       (pd.Timestamp(f"{y + 1}-01-01", tz="UTC") - start).days) for y in years}
    out = {"period": [start_year, end_year], "cells": {}}
    net_ok, rt_ok, pool_ok, exec_ok = [], [], [], []
    replacement = {name: [] for name in all_base}
    for cell, value in cells.items():
        daily = np.asarray(value["daily"], float)
        if len(daily) != n_days:
            raise ValueError(f"{cell}: daily series must cover {start.date()}..{(end - pd.Timedelta(days=1)).date()}")
        months = pd.date_range(start, periods=n_days, freq="D").strftime("%Y-%m")
        monthly = pd.Series(daily).groupby(months).sum()
        total = float(daily.sum())
        row = {"pooled_net4": total, "pooled_boot_p05": {str(b): boot_p05(daily, b) for b in BLOCKS},
               "mdd": mdd(daily),
               "top2_month_share": (float(monthly.nlargest(2).sum() / total) if total > 0 else None), "years": {}}
        for year, sl in slices.items():
            closed = int(value["closed"][year])
            net4 = float(daily[sl].sum())
            row["years"][str(year)] = {"net4": net4, "closed": closed,
                                        "boot_p05": {str(b): boot_p05(daily[sl], b) for b in BLOCKS}}
            net_ok.append(net4 > 0)
            rt_ok.append(closed >= 30)
        pool_ok.append(row["pooled_boot_p05"][str(MAIN_BLOCK)] > 0)
        row["paired_excess"] = {}
        for name, base in all_base.items():
            bd = np.asarray(base[cell], float)
            if len(bd) != n_days:
                raise ValueError(f"{name}/{cell}: baseline daily length {len(bd)} != {n_days}")
            excess = daily - bd
            p = {str(b): boot_p05(excess, b) for b in BLOCKS}
            row["paired_excess"][name] = {"net4": float(excess.sum()), "boot_p05": p}
            replacement[name].append(p[str(MAIN_BLOCK)] > 0)
        present = any(k in value for k in ("max_hold_min", "cap_violations", "identity_err", "faults",
                                            "long_round_trips", "short_round_trips"))
        if present:
            checks = {"max_hold<=1440": float(value.get("max_hold_min", np.inf)) <= 1440,
                      "cap_violations=0": int(value.get("cap_violations", 1)) == 0,
                      "identity<=1e-8": float(value.get("identity_err", np.inf)) <= 1e-8,
                      "faults=0": int(value.get("faults", 1)) == 0,
                      "long_rt>=30": int(value.get("long_round_trips", 0)) >= 30,
                      "short_rt>=30": int(value.get("short_round_trips", 0)) >= 30}
            row["execution"] = checks
            exec_ok.append(all(checks.values()))
        out["cells"][cell] = row
    out["absolute"] = {"year_cell_net4>0": f"{sum(net_ok)}/{len(net_ok)}",
                       "year_cell_closed>=30": f"{sum(rt_ok)}/{len(rt_ok)}",
                       "pooled_boot60_p05>0": f"{sum(pool_ok)}/{len(pool_ok)}",
                       "pass": bool(all(net_ok) and all(rt_ok) and all(pool_ok))}
    out["replacement"] = {name: {"paired_excess_boot60_p05>0": f"{sum(v)}/{len(v)}", "pass": bool(all(v))}
                          for name, v in replacement.items()}
    if exec_ok:
        out["execution"] = {"cells_pass": f"{sum(exec_ok)}/{len(exec_ok)}", "pass": bool(all(exec_ok))}
    out["pass"] = bool(out["absolute"]["pass"] and all(v["pass"] for v in out["replacement"].values())
                       and (not exec_ok or all(exec_ok)))
    return out
