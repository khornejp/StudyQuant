"""RL allocator sleeve precompute (Codex design 2026-10-10, sections 1/6/8 steps 1-2).

Fixed canonical shadow ledgers per sleeve and execution cell, a fast counterfactual replay (allocation multiplier and
early exit on canonical entry opportunities), and the TEST-access guard. Pure numpy/pandas; the source engines (out/,
scripts/) are driven by scripts/precompute_rl_allocator.py and never imported here.

Ledger kinds (both reproduce their source ledger per minute):
  "lin"  Batch-2 Book (G3_LONG, G3_SHORT, LBR_FUND): arithmetic MTM a = s*w/px0*1e4, 2 bps x w at the entry fill and
         at the exit fill (or the terminal minute), PESS funding: adverse in [t(j0), t(j1)+1m), favourable in
         [t(j0)+1m, t(j1)).
  "log"  sim core (B3_AXC0, K04_AXC0) and R2-37 fast_ledger (C1v2, C4v2): log MTM, `fee` bps x units per side,
         funding at settlement minutes: interior always, entry/exit boundary only if the cashflow is negative (PESS).
Counterfactual rule (design section 6): the canonical opportunity schedule is fixed. An allocation multiplier in
LEVELS scales one canonical opportunity for its whole life; a skipped or early-exited opportunity never re-enters.
Early exit request at minute x (allocator decided on bars closed through x-1):
  "lin": maker exit quote 2 bps from close[x-1], re-quoted every 60 m (Batch-2 exit_fill, cell penetration); the
         position closes at whichever fills first, this order or the canonical exit (tie -> this order).
  "log": native fill at open[x] (R2-37 / core market exit), only for entry minute < x <= canonical exit minute.
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np, pandas as pd

MIN = 60_000_000_000
TEST_START = pd.Timestamp("2026-01-01", tz="UTC")
DATA_END = pd.Timestamp("2026-10-08", tz="UTC")
LEVELS = (0.0, 0.25, 0.50, 0.75, 1.00)
TICK, EXIT_QUOTE_BPS, REQUOTE_MIN = 0.1, 2.0, 60
ROW_COLS = ("minute", "tid", "gross", "fee", "funding")

# Observation contract (Codex review 2026-10-10 P1). Only these columns may reach an allocator observation, and a row
# only once its available_time <= T. Everything in the private outcome tables (fill result, realized exits, reasons,
# trade totals) is future information at decision time and stays replay/accounting-only.
OBS_COLUMNS = {
    "grid": ("minute_time", "available_time", "sleeve_id", "exec_cell", "available", "base_side", "base_weight",
             "signal_active", "pending", "open", "exit_pending", "entry_opportunity_id", "base_mandatory_exit_time",
             "R0_bps", "R_t_bps", "stop_level", "trail_armed", "gross_pnl", "fee", "funding", "net4",
             "feature_snapshot_id", "snapshot_id_aux", "closed_opp_id"),
    "decisions": ("entry_opportunity_id", "decision_time", "available_time", "side", "base_weight",
                  "feature_snapshot_id", "base_mandatory_exit_time", "segment"),
    "ledger": ("minute_time", "available_time", "minute_idx", "entry_opportunity_id", "gross_pnl", "fee", "funding",
               "net4"),
}
PRIVATE_STEMS = ("outcomes",)


# ---------------------------------------------------------------- TEST guard
class TestAccessError(RuntimeError):
    """Raised when TEST rows (time >= 2026-01-01) are read without an explicit unlock."""


def guard_times(times_ns, allow_test: bool = False, what: str = "rows") -> np.ndarray:
    t = np.asarray(times_ns, np.int64)
    if not allow_test and len(t) and int(t.max()) >= TEST_START.value:
        raise TestAccessError(f"{what}: {int((t >= TEST_START.value).sum())} TEST rows (>= {TEST_START.date()}) "
                              "read without allow_test=True")
    return t


def require_unlock(flag: bool, purpose: str) -> None:
    """Fail closed: any code path that reads TEST rows must be given an explicit unlock flag."""
    if not flag:
        raise TestAccessError(f"{purpose} reads TEST rows (>= {TEST_START.date()}); pass the explicit unlock flag")


def obs_columns(kind: str, columns) -> list[str]:
    """Allowlist check: raise on any column that is not observation-safe for `kind`."""
    allowed = OBS_COLUMNS[kind]
    bad = [c for c in columns if c not in allowed]
    if bad:
        raise PermissionError(f"non-observation columns for {kind}: {bad}")
    return list(columns)


def read_observation(directory: Path, kind: str, T_max_ns: int, columns=None, allow_test: bool = False) -> pd.DataFrame:
    """The only reader for observation inputs: allowlisted columns of grid/decisions/ledger partitions, rows with
    available_time <= T_max_ns. Private outcome tables cannot be read through it."""
    if kind in PRIVATE_STEMS or kind not in OBS_COLUMNS:
        raise PermissionError(f"{kind} is not an observation table")
    cols = obs_columns(kind, columns if columns is not None else OBS_COLUMNS[kind])
    tcol = "minute_time" if kind != "decisions" else "decision_time"
    years = set(range(2020, pd.Timestamp(int(T_max_ns), tz="UTC").year + 1))
    f = read_partitioned(directory, kind, allow_test=allow_test, time_col=tcol, years=years)
    if not len(f):
        return f
    keep = f.available_time.to_numpy(np.int64) <= int(T_max_ns)
    return f.loc[keep, [c for c in f.columns if c in cols]].reset_index(drop=True)


def read_partitioned(directory: Path, stem: str, allow_test: bool = False, time_col: str = "minute_time",
                     years=None) -> pd.DataFrame:
    """Read `<stem>_<year>.parquet` partitions. A partition at or after the TEST year is refused before it is opened."""
    files = sorted(Path(directory).glob(f"{stem}_*.parquet"))
    out = []
    for f in files:
        year = int(f.stem.rsplit("_", 1)[1])
        if years is not None and year not in years:
            continue
        if year >= TEST_START.year and not allow_test:
            raise TestAccessError(f"{f.name}: TEST partition read without allow_test=True")
        out.append(pd.read_parquet(f))
    frame = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(frame):
        guard_times(frame[time_col], allow_test, str(directory))
    return frame


# ---------------------------------------------------------------- ledgers
def _empty_rows() -> dict:
    return {"minute": np.zeros(0, np.int64), "tid": np.zeros(0, np.int64), "gross": np.zeros(0),
            "fee": np.zeros(0), "funding": np.zeros(0)}


def _cat(parts: list[dict]) -> dict:
    if not parts:
        return _empty_rows()
    return {k: np.concatenate([p[k] for p in parts]) for k in ROW_COLS}


def _one(tid: int, j0: int, gross: np.ndarray, fee: np.ndarray, fmin: np.ndarray, fcf: np.ndarray) -> dict:
    n = len(gross)
    fund = np.zeros(n)
    np.add.at(fund, fmin - j0, fcf)
    return {"minute": np.arange(j0, j0 + n, dtype=np.int64), "tid": np.full(n, tid, np.int64), "gross": gross,
            "fee": fee, "funding": fund}


def lin_trade(t, c, tid, s, w, j0, px0, closed, j1, px1, hi, ft, fr) -> dict:
    """One Batch-2 Book trade as per-minute rows over [j0, exit or terminal minute]."""
    jx = j1 if closed else hi - 1
    last = j1 if closed else hi                    # MTM coef live on minutes j0+1 .. last-1
    n = jx - j0 + 1
    a = s * w / px0 * 1e4
    gross, fee = np.zeros(n), np.zeros(n)
    gross[1:last - j0] = a * (c[j0 + 1:last] - c[j0:last - 1])
    gross[0] += a * (c[j0] - px0)
    if closed:
        gross[j1 - j0] += a * (px1 - c[j1 - 1])
    fee[0] -= 2 * w
    fee[jx - j0] -= 2 * w
    t0 = t[j0]
    adv_hi = t[j1] + MIN if closed else t[hi - 1] + MIN
    fav_hi = t[j1] if closed else t[hi - 1] + MIN
    lo_, hi_ = np.searchsorted(ft, t0), np.searchsorted(ft, adv_hi)
    f_t = ft[lo_:hi_]
    cf = -s * fr[lo_:hi_] * 1e4 * w
    keep = (cf < 0) | ((f_t >= t0 + MIN) & (f_t < fav_hi))
    fmin = np.searchsorted(t, f_t[keep], "right") - 1
    return _one(tid, j0, gross, fee, fmin, cf[keep])


def lin_rows(t, c, tr: pd.DataFrame, hi: int, ft, fr) -> dict:
    """tr: Batch-2 simulate trades (+ column tid)."""
    parts = []
    for r in tr.itertuples(index=False):
        closed = not bool(r.open_at_end)
        parts.append(lin_trade(t, c, int(r.tid), int(r.side), float(r.entry_weight_frozen), int(r.entry_idx),
                               float(r.entry_px), closed, int(r.exit_idx) if closed else hi,
                               float(r.exit_px), hi, ft, fr))
    return _cat(parts)


def log_funding(t, s, units, entry_ns, exit_ns, ft, fr) -> tuple[np.ndarray, np.ndarray]:
    """Settlement minutes and cashflows (bps) of one holding: interior always, boundary only if negative (PESS).
    Settlements not on a minute open are skipped (sim core rule)."""
    lo_, hi_ = np.searchsorted(ft, entry_ns, "left"), np.searchsorted(ft, exit_ns, "right")
    f_t = ft[lo_:hi_]
    v = -s * fr[lo_:hi_] * 1e4
    edge = (f_t == entry_ns) | (f_t == exit_ns)
    keep = ~edge | (v < 0)
    k = np.searchsorted(t, f_t, "left")
    on = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == f_t)
    keep &= on
    return k[keep].astype(np.int64), v[keep] * units


def log_trade(t, logc, tid, s, units, e, x, px_in, px_out, fee_side, entry_ns, exit_ns, ft, fr) -> dict:
    """One log-ledger holding: entry minute e (fill px_in), exit minute x (fill px_out), marks to close."""
    n = x - e + 1
    gross, fee = np.zeros(n), np.zeros(n)
    k = s * 1e4 * units
    if n == 1:
        gross[0] = k * math.log(px_out / px_in)
        fee[0] = -2 * fee_side * units
    else:
        gross[0] = k * (logc[e] - math.log(px_in))
        gross[1:-1] = k * (logc[e + 1:x] - logc[e:x - 1])
        gross[-1] = k * (math.log(px_out) - logc[x - 1])
        fee[0] = fee[-1] = -fee_side * units
    fmin, fcf = log_funding(t, s, units, entry_ns, exit_ns, ft, fr)
    return _one(tid, e, gross, fee, fmin, fcf)


def log_rows(t, c, tr: pd.DataFrame, fee_side: float, ft, fr) -> dict:
    """tr columns: tid, side, units, e, x, px_in, px_out, entry_ns, exit_ns."""
    logc = np.log(c)
    return _cat([log_trade(t, logc, int(r.tid), int(r.side), float(r.units), int(r.e), int(r.x), float(r.px_in),
                           float(r.px_out), fee_side, int(r.entry_ns), int(r.exit_ns), ft, fr)
                  for r in tr.itertuples(index=False)])


def minute_sum(rows: dict, n: int, weight=None) -> np.ndarray:
    v = rows["gross"] + rows["fee"] + rows["funding"]
    if weight is not None:
        v = v * weight
    return np.bincount(rows["minute"], v, minlength=n)[:n]


# ---------------------------------------------------------------- early exits
def limit_price(close: float, side: int, offset_bps: float) -> float:
    if side > 0:
        return np.floor(close * (1 - offset_bps / 1e4) / TICK + 1e-9) * TICK
    return np.ceil(close * (1 + offset_bps / 1e4) / TICK - 1e-9) * TICK


def first_fill(o, h, l, start: int, stop: int, limit: float, buy: bool, pen: float) -> int:
    if stop <= start:
        return -1
    if buy:
        ok = (o[start:stop] >= limit) & (l[start:stop] <= limit * (1 - pen / 1e4))
    else:
        ok = (o[start:stop] <= limit) & (h[start:stop] >= limit * (1 + pen / 1e4))
    k = np.flatnonzero(ok)
    return int(start + k[0]) if len(k) else -1


def exit_fill(o, h, l, c, dec: int, side: int, hi: int, pen: float) -> tuple[int, float]:
    """Passive exit 2 bps from close[dec], re-quoted every 60 m until filled (< hi); (-1, nan) if never."""
    while dec < hi - 1:
        lim = limit_price(c[dec], -side, EXIT_QUOTE_BPS)
        j = first_fill(o, h, l, dec + 1, min(dec + 1 + REQUOTE_MIN, hi), lim, side < 0, pen)
        if j >= 0:
            return j, lim
        dec += REQUOTE_MIN
    return -1, np.nan


def lin_early(mk: dict, tr: pd.DataFrame, x: int, pen: float, hi: int):
    """Early exit of one lin trade at minute x -> (exit_decision_idx, exit_idx, exit_px) or None (no change)."""
    r = tr
    xc_dec = int(r.exit_decision_idx) if not r.open_at_end else hi
    if not (int(r.entry_idx) <= x - 1 < xc_dec):
        return None
    j, px = exit_fill(mk["o"], mk["h"], mk["l"], mk["c"], x - 1, int(r.side), hi, pen)
    if j < 0 or (not r.open_at_end and j > int(r.exit_idx)):
        return None                                        # canonical exit fills first
    return x - 1, j, px


def log_early(tr, x: int):
    """Early exit of one log trade at the open of minute x -> new exit minute or None."""
    return x if int(tr.e) < x <= int(tr.x) else None


def replay(kind: str, rows: dict, tr: pd.DataFrame, mk: dict, ft, fr, mult, exit_at, *, pen: float = 0.5,
           fee_side: float = 2.0, hi: int | None = None) -> np.ndarray:
    """Fast counterfactual minute net (bps) from precomputed canonical rows.
    mult: per tid multiplier; exit_at: per tid early-exit minute (-1 none). tr indexed so tr.iloc[tid] is trade tid."""
    t, c = mk["t"], mk["c"]
    n = len(t)
    hi = n if hi is None else hi
    mult = np.asarray(mult, float)
    cut = np.full(len(tr), np.iinfo(np.int64).max)
    extra = []
    logc = np.log(c) if kind == "log" else None
    for tid in np.flatnonzero((np.asarray(exit_at) >= 0) & (mult > 0)):
        r = tr.iloc[tid]
        x = int(exit_at[tid])
        if kind == "lin":
            ch = lin_early(mk, r, x, pen, hi)
            if ch is None:
                continue
            xd, j, px = ch
            cut[tid] = j
            one = lin_trade(t, c, tid, int(r.side), float(r.entry_weight_frozen), int(r.entry_idx),
                            float(r.entry_px), True, j, px, hi, ft, fr)
        else:
            xx = log_early(r, x)
            if xx is None:
                continue
            cut[tid] = xx
            one = log_trade(t, logc, tid, int(r.side), float(r.units), int(r.e), xx, float(r.px_in),
                            float(mk["o"][xx]), fee_side, int(r.entry_ns), int(t[xx]), ft, fr)
        keep = one["minute"] >= j if kind == "lin" else one["minute"] >= xx
        extra.append({k: v[keep] for k, v in one.items()})
    keep = rows["minute"] < cut[rows["tid"]]
    base = {k: v[keep] for k, v in rows.items()}
    out = minute_sum(base, n, mult[base["tid"]])
    for e in extra:
        out += minute_sum(e, n, mult[e["tid"]])
    return out


# ---------------------------------------------------------------- adaptive stop state (B3/K04, sim core R2_52A)
def adaptive_path(o, h, l, e_min_col, e: int, x: int, side: int, px: float, k: float, e0: float):
    """Per-minute (e..x) end-of-minute R_t, best, armed and the stop level live at the next open, plus the level used
    inside each minute (after that minute's R update). Mirrors core._adaptive_loop for one open position."""
    n = x - e + 1
    R0 = min(k * e0, 300.0)
    R, best, armed = R0, px, 0.0
    out_R, out_best, out_arm, lvl_in = (np.zeros(n) for _ in range(4))
    for q in range(n):
        i = e + q
        if i > e:
            v = e_min_col[i]
            if np.isfinite(v) and v > 0:
                R = min(R, k * v, 300.0)
        hard = px * math.exp(-side * R / 1e4)
        lvl = hard
        if armed == 1.0:
            trail = best * math.exp(-side * 0.5 * R / 1e4)
            if side * (trail - hard) > 0:
                lvl = trail
        lvl_in[q] = lvl
        best = max(best, h[i]) if side == 1 else min(best, l[i])
        if armed == 1.0 or side * math.log(best / px) * 1e4 >= R0:
            armed = 1.0
        out_R[q], out_best[q], out_arm[q] = R, best, armed
    return R0, out_R, out_best, out_arm, lvl_in


# ---------------------------------------------------------------- per-minute state grid
def interval_mask(n: int, a, b) -> np.ndarray:
    """True on [a_i, b_i] (inclusive) for every interval with b_i >= a_i."""
    a, b = np.asarray(a, np.int64), np.asarray(b, np.int64)
    ok = b >= a
    d = np.zeros(n + 1, np.int64)
    np.add.at(d, np.clip(a[ok], 0, n), 1)
    np.add.at(d, np.clip(b[ok] + 1, 0, n), -1)
    return np.cumsum(d)[:n] > 0


def interval_fill(n: int, a, b, values, fill, dtype) -> np.ndarray:
    """values[i] on [a_i, b_i]; later intervals overwrite earlier ones (same-minute reversal -> the new opportunity)."""
    out = np.full(n, fill, dtype)
    for x, y, v in zip(np.asarray(a, np.int64), np.asarray(b, np.int64), values):
        if y >= x:
            out[x:y + 1] = v
    return out


def event_ffill(t: np.ndarray, ev_t: np.ndarray, values, fill, dtype) -> np.ndarray:
    """Value of the latest event with event time <= t[i] (known at minute open t[i]); `fill` before the first."""
    k = np.searchsorted(np.asarray(ev_t, np.int64), np.asarray(t, np.int64), "right") - 1
    v = np.asarray(values)
    return np.where(k >= 0, v[np.maximum(k, 0)] if len(v) else fill, fill).astype(dtype)


def event_index(t: np.ndarray, ev_t: np.ndarray) -> np.ndarray:
    """Index of the latest event with event time <= t[i], -1 before the first."""
    return np.searchsorted(np.asarray(ev_t, np.int64), np.asarray(t, np.int64), "right") - 1


def year_slices(t: np.ndarray) -> dict[int, slice]:
    years = np.asarray(pd.to_datetime(np.asarray(t, np.int64), utc=True).year)
    out = {}
    for y in np.unique(years):
        idx = np.flatnonzero(years == y)
        out[int(y)] = slice(int(idx[0]), int(idx[-1]) + 1)
    return out
