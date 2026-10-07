from __future__ import annotations
import numpy as np, pandas as pd

def _bridge(o, c, steps, rng):
    w = np.cumsum(rng.normal(0, 1, steps)); w -= np.linspace(0, 1, steps) * w[-1]
    scale = max(abs(c - o), 1e-12)
    return o + (c - o) * np.linspace(0, 1, steps) + w / np.sqrt(steps) * scale

def first_touch_probability(o, h, l, c, stop, take, side, n_paths=200, seed=0) -> float:
    rng = np.random.default_rng(seed); stop_first = accepted = 0
    for _ in range(n_paths * 20):
        if accepted >= n_paths:
            break
        p = _bridge(o, c, 60, rng)
        p = l + (p - p.min()) / max(p.max() - p.min(), 1e-12) * (h - l)   # map to observed range
        hit_stop = np.argmax(p <= stop) if side == 1 and (p <= stop).any() else (
            np.argmax(p >= stop) if side == -1 and (p >= stop).any() else None)
        hit_take = np.argmax(p >= take) if side == 1 and (p >= take).any() else (
            np.argmax(p <= take) if side == -1 and (p <= take).any() else None)
        if hit_stop is None or hit_take is None:
            continue
        accepted += 1; stop_first += hit_stop <= hit_take
    return stop_first / accepted if accepted else 1.0

def resimulate_ambiguous(trades: pd.DataFrame, minutes: pd.DataFrame, seed: int) -> pd.DataFrame:
    """`trades` needs a `take_bps` column (the signal's take level); SimResult.trades lacks it, so merge it in."""
    if "take_bps" not in trades:
        raise ValueError("trades need a take_bps column; without it no stop can be re-drawn")
    rng = np.random.default_rng(seed); out = trades.copy()
    bar = minutes.set_index("open_time")
    for i, t in out.loc[out.exit_reason.eq("stop")].iterrows():
        row = bar.loc[t.exit_time]
        take = t.entry_price * (1 + t.side * t.take_bps / 1e4)
        if np.isnan(take) or not ((t.side == 1 and row.high >= take) or (t.side == -1 and row.low <= take)):
            continue
        p = first_touch_probability(row.open, row.high, row.low, row.close, t.exit_price, take, t.side)
        if rng.random() > p:
            gross = t.side * np.log(take / t.entry_price) * 1e4 * t.units
            out.loc[i, ["exit_price", "exit_reason", "gross_bps"]] = [take, "take_resampled", gross]
            out.loc[i, "net_bps"] = gross - t.fee_bps + t.funding_bps
    return out
