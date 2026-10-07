"""Detector regime inputs (R2-45 M/L percentiles, R2-46 E lookup) and fixed gates."""
from __future__ import annotations
from bisect import bisect_left, bisect_right, insort
import numpy as np, pandas as pd

M_TARGETS = tuple(f"{k}_{h}" for k in ("range", "rv", "exc") for h in ("30m", "1h", "4h"))
L_TARGETS = tuple(f"{k}_{h}" for k in ("range", "rv", "exc") for h in ("12h", "24h"))
GATES = {"HIGH": lambda m: m >= 2 / 3, "LOW": lambda m: m <= 1 / 3}
E_MAX_AGE = pd.Timedelta(hours=24)


def causal_percentile(values, times: pd.DatetimeIndex, days: int = 30, minimum_days: int = 7) -> np.ndarray:
    """Share of strictly earlier values within the last `days` that are <= the current value."""
    x = np.asarray(values, float); ns = pd.DatetimeIndex(times).asi8
    result = np.full(len(x), np.nan)
    ordered: list[float] = []
    left = 0
    minimum = minimum_days * 96
    window = pd.Timedelta(days=days).value
    for i, value in enumerate(x):
        while left < i and ns[left] < ns[i] - window:
            if np.isfinite(x[left]):
                ordered.pop(bisect_left(ordered, float(x[left])))
            left += 1
        if np.isfinite(value) and len(ordered) >= max(1, minimum):
            result[i] = bisect_right(ordered, float(value)) / len(ordered)
        if np.isfinite(value):
            insort(ordered, float(value))
    return result


def load_regime(predictions: pd.DataFrame) -> pd.DataFrame:
    frame = predictions.sort_values("timestamp").reset_index(drop=True).copy()
    times = pd.DatetimeIndex(frame.timestamp)
    ranks = {t: causal_percentile(frame[f"prediction_{t}"].to_numpy(float), times) for t in M_TARGETS + L_TARGETS}
    frame["M"] = pd.DataFrame({t: ranks[t] for t in M_TARGETS}).mean(axis=1, skipna=False).to_numpy()
    frame["L"] = pd.DataFrame({t: ranks[t] for t in L_TARGETS}).mean(axis=1, skipna=False).to_numpy()
    return frame


def rank_against(reference: pd.DataFrame, rows: pd.DataFrame, days: int = 30, minimum_days: int = 7) -> pd.DataFrame:
    """M/L for off-grid rows: each value's rank among the strictly earlier 15-minute reference predictions of the
    last `days` (the research distribution), needing `minimum_days` x 96 of them."""
    ref_t = pd.DatetimeIndex(reference.timestamp).as_unit("ns").asi8
    times = pd.DatetimeIndex(rows.timestamp).as_unit("ns").asi8
    lo = np.searchsorted(ref_t, times - pd.Timedelta(days=days).value, side="left")
    hi = np.searchsorted(ref_t, times, side="left")
    out = rows.copy()
    ranks = {}
    for target in M_TARGETS + L_TARGETS:
        ref_v = reference[f"prediction_{target}"].to_numpy(float)
        values = rows[f"prediction_{target}"].to_numpy(float)
        rank = np.full(len(rows), np.nan)
        for k, (a, b, v) in enumerate(zip(lo, hi, values)):
            window = ref_v[a:b]
            window = window[np.isfinite(window)]
            if len(window) >= minimum_days * 96 and np.isfinite(v):
                rank[k] = np.count_nonzero(window <= v) / len(window)
        ranks[target] = rank
    out["M"] = pd.DataFrame({t: ranks[t] for t in M_TARGETS}).mean(axis=1, skipna=False).to_numpy()
    out["L"] = pd.DataFrame({t: ranks[t] for t in L_TARGETS}).mean(axis=1, skipna=False).to_numpy()
    return out


def _asof(frame: pd.DataFrame, decisions: pd.DatetimeIndex, column: str, max_age: pd.Timedelta | None) -> np.ndarray:
    times = pd.DatetimeIndex(frame.timestamp).as_unit("ns").asi8
    d = pd.DatetimeIndex(decisions).as_unit("ns").asi8
    position = np.searchsorted(times, d, side="right") - 1          # exact T counts (prediction made for T)
    out = np.full(len(d), np.nan)
    if not len(times):                  # no predictions at all (e.g. live paper books)
        return out
    ok = position >= 0
    out[ok] = frame[column].to_numpy(float)[position[ok]]
    if max_age is not None:
        age = np.where(ok, d - times[np.maximum(position, 0)], np.iinfo(np.int64).max)
        out[age > max_age.value] = np.nan
    return out


def e_bps(frame: pd.DataFrame, decisions: pd.DatetimeIndex, head: str) -> np.ndarray:
    """prediction_exc_<head> at T, else the latest earlier one at most 24 h old (R2-46 annotate_entries)."""
    return _asof(frame, decisions, f"prediction_exc_{head}", E_MAX_AGE)


def gate_mask(frame: pd.DataFrame, decisions: pd.DatetimeIndex, gate: str) -> np.ndarray:
    m = _asof(frame, decisions, "M", pd.Timedelta(minutes=14))       # latest 15 m prediction at or before T
    with np.errstate(invalid="ignore"):
        return np.isfinite(m) & GATES[gate](m)
