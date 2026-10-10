"""Batch-2 new-model screen (2026-10-10): families V/E/F/G/H/I/J/K, 354 variants (177 offset2 + 177 offset5 twins).

Spec: scratchpad codex_batch2_spec.md (Codex Batch-1 review + Batch-2 spec). Parent run NM-B1-20261010.
Engine fixes vs Batch-1 (out/run_new_model_batch1_20261010.py):
  * one continuous simulation 2020-01-01..2026-10-08; DEV-FULL/DEV-A/DEV-B/TEST are MTM cuts of one P&L stream
    (positions and orders persist across splits; no forced exit/re-entry/cost at a split);
  * no stale flip: after an exit fill the engine waits for the next regular decision and re-reads the latest target;
  * open positions are never counted as closed trades / wins (closed_trades, entries, open_n, open_mtm separate);
  * fill-model sensitivity: penetration {0.5,1,2} bp x offset {2,5} bps for the picks;
  * entry weight is entry_weight_frozen (weight fixed at the entry decision while held);
  * DEV score uses net per calendar day of the window (not per exposure day);
  * closed side < 10 -> LOW_N, separate from the profit verdict;
  * stationary bootstrap, mean block 60d main, 20/120d reported;
  * MDD on 1m MTM equity; active months = months with exposure > 0;
  * write-once run folder NM-B2-<UTC>-<codehash8>, registry rows keyed (idempotent).
Causality: decision on closed bar i (T = open_time[i] + 1m); orders fill from bar i+1; every as-of input asserts
available_time <= T; trailing quantiles / robust z / z-score stats exclude the current observation.
Interpretations (spec silent; recorded in the manifest):
  * V/K weight sigma = 1h-bar sigma over the previous 30d (720 bars, current excluded), annualised; K-B1 base keeps
    the Batch-1 1d sigma (current bar included, Batch-1 feature code reused unchanged). V/G z-score sigma excludes the
    current bar. V/K decide hourly; G decides on closed 4h bars; H on closed 4h bars with trend TTL 60m.
  * K: V base = balanced/db0.25/binary with no short gate; action 'veto' blocks new entries while adverse,
    'flat30' adds a decision at settle-30m that flattens an adverse held side and blocks entries at that point.
  * I: history window caps at {104,208} weeks; at least 52 weeks of history required before any signal.
  * J: p480 = mean of the available premium minutes in the last 480; fail-closed if the newest premium is older
    than 2m at T. E/J/K slots = UTC 00/08/16 settlement events.
  * F/H (OI/LS) simulate and score from 2021-01-01; their DEV-FULL/DEV-A windows start there.
  * H: train [R-910d, R-180d) with label end < R-180d (purge), calibration [R-180d, R-h]; refit at each month start R;
    min 500 train / 200 calibration rows; features with all-NaN train get median 0; missing flags for every feature.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, subprocess, sys, time, warnings
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.funding_source import load_funding_dir  # noqa: E402
from btcusdt_quant.sim import data, provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402

_spec = importlib.util.spec_from_file_location("nm_b1", ROOT / "out/run_new_model_batch1_20261010.py")
b1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b1)

OUT_BASE = ROOT / "out/new_model_batch2_20261010"
SNAP = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot"
DEV_MARKET = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
DEV_METRICS = ROOT / "artifacts/metrics"
DEV_PREMIUM = ROOT / "artifacts/premium_index_2020_2026h1"
DEV_FUNDING = ROOT / "artifacts/funding_2020_2026h1"
REGISTRY = ROOT / "out/sim_registry.jsonl"
TS = lambda x: pd.Timestamp(x, tz="UTC")  # noqa: E731
START, DEVB, SPLIT, END, OI_START = TS("2020-01-01"), TS("2024-01-01"), TS("2026-01-01"), TS("2026-10-08"), TS("2021-01-01")
WINDOWS = {"DEV-FULL": (START, SPLIT), "DEV-A": (START, DEVB), "DEV-B": (DEVB, SPLIT), "TEST": (SPLIT, END)}
MIN = 60_000_000_000
HOUR, DAY = 60 * MIN, 1440 * MIN
TICK, EXIT_QUOTE_BPS, REQUOTE_MIN, PEN_BPS = 0.1, 2.0, 60, 0.5
TTL_TREND, TTL_EVENT = 60, 15
THR = 4e-4                      # 4 bps edge threshold (H, I)
SEED, NBOOT, BLOCKS, MAIN_BLOCK = 20261010, 10_000, (20, 60, 120), 60
PARENT = "NM-B1-20261010"
FAMILIES = ("V", "E", "F", "G", "H", "I", "J", "K")
SIDES = ("long", "short")


# ---------------- fill model ----------------
def limit_price(close: float, side: int, offset_bps: float) -> float:
    if side > 0:
        return np.floor(close * (1 - offset_bps / 1e4) / TICK + 1e-9) * TICK
    return np.ceil(close * (1 + offset_bps / 1e4) / TICK - 1e-9) * TICK


def first_fill(o, h, l, start: int, stop: int, limit: float, buy: bool, pen: float = PEN_BPS) -> int:
    """First bar in [start, stop) where a resting limit fills; needs `pen` bp trade-through, gap-through rejects."""
    if stop <= start:
        return -1
    if buy:
        ok = (o[start:stop] >= limit) & (l[start:stop] <= limit * (1 - pen / 1e4))
    else:
        ok = (o[start:stop] <= limit) & (h[start:stop] >= limit * (1 + pen / 1e4))
    k = np.flatnonzero(ok)
    return int(start + k[0]) if len(k) else -1


def exit_fill(m, dec: int, side: int, hi: int, pen: float) -> tuple[int, float]:
    """Passive exit 2 bps favourable from close[dec], re-quoted at the new close every 60m until filled (< hi)."""
    while dec < hi - 1:
        lim = limit_price(m.c[dec], -side, EXIT_QUOTE_BPS)
        j = first_fill(m.o, m.h, m.l, dec + 1, min(dec + 1 + REQUOTE_MIN, hi), lim, side < 0, pen)
        if j >= 0:
            return j, lim
        dec += REQUOTE_MIN
    return -1, np.nan


class Market:
    def __init__(self, t, o, h, l, c, v, tb, ft, fr):
        self.t, self.o, self.h, self.l, self.c, self.v, self.tb = t, o, h, l, c, v, tb
        self.ft, self.fr = ft, fr
        self.N = len(t)

    @classmethod
    def from_frames(cls, frame: pd.DataFrame, funding: pd.DataFrame) -> "Market":
        g = lambda k: frame[k].to_numpy(float)  # noqa: E731
        return cls(frame.open_time.array.asi8.copy(), g("open"), g("high"), g("low"), g("close"), g("volume"),
                   g("taker_buy_base_volume"), funding.time.array.asi8.copy(), funding.rate.to_numpy(float))

    def idx(self, ts) -> int:
        return int(np.searchsorted(self.t, pd.Timestamp(ts).value))


# ---------------- engine ----------------
def simulate(m: Market, kind: str, dec, side, weight, offset: float, ttl: int, pen: float, lo: int, hi: int,
             hold: int = 0, entry_ok=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One continuous run over [lo, hi). kind 'state': side = target side per decision (exit when target != held);
    'event': side = event side, fixed hold (minutes) from the entry fill. Decisions arriving while an order or an
    exit is pending are skipped; after a fill the next decision considered is the first one at or after the fill bar
    (its close is after the fill), and its latest target is re-read (no stale re-entry)."""
    dec, side, weight = np.asarray(dec), np.asarray(side), np.asarray(weight, float)
    sel = (dec >= lo) & (dec < hi - 1)
    D, S, W = dec[sel], side[sel], weight[sel]
    E = np.ones(len(D), bool) if entry_ok is None else np.asarray(entry_ok)[sel]
    assert np.all(np.diff(D) > 0), "decisions must be strictly increasing"
    trades, orders, pos, busy, k = [], [], None, lo, 0

    def rec(p, xdec, j1, xpx):
        trades.append({"side": p[0], "entry_weight_frozen": p[1], "decision_idx": p[2], "entry_idx": p[3],
                       "entry_px": p[4], "exit_decision_idx": xdec, "exit_idx": j1, "exit_px": xpx,
                       "open_at_end": j1 < 0})

    while k < len(D):
        if D[k] < busy:
            k += int(np.searchsorted(D[k:], busy))
            continue
        i, s, w, ok = int(D[k]), int(S[k]), float(W[k]), bool(E[k])
        k += 1
        if pos is not None:
            if s == pos[0]:
                continue
            j1, xpx = exit_fill(m, i, pos[0], hi, pen)
            rec(pos, i, j1, xpx)
            pos = None
            if j1 < 0:
                break
            busy = j1
            continue
        if s == 0 or not w > 0 or not ok:
            continue
        lim = limit_price(m.c[i], s, offset)
        j0 = first_fill(m.o, m.h, m.l, i + 1, min(i + 1 + ttl, hi), lim, s > 0, pen)
        orders.append((i, s, w, j0 >= 0))
        if j0 < 0:
            busy = i + ttl
            continue
        p = (s, w, i, j0, lim)
        if kind == "state":
            pos, busy = p, j0
            continue
        xdec = j0 + hold
        if xdec >= hi - 1:
            rec(p, -1, -1, np.nan)
            break
        j1, xpx = exit_fill(m, xdec, s, hi, pen)
        rec(p, xdec, j1, xpx)
        if j1 < 0:
            break
        busy = j1
    if pos is not None:
        rec(pos, -1, -1, np.nan)
    tr = pd.DataFrame(trades, columns=["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px",
                                       "exit_decision_idx", "exit_idx", "exit_px", "open_at_end"])
    if len(tr):
        assert (tr.entry_idx > tr.decision_idx).all(), "fill on/before decision bar"
        c = ~tr.open_at_end
        assert (tr.exit_idx[c] > tr.exit_decision_idx[c]).all() and (tr.exit_decision_idx[c] >= tr.entry_idx[c]).all()
        assert (tr.entry_idx < hi).all() and (tr.decision_idx >= lo).all()
        if kind == "state":   # no overlap, no stale re-entry: next entry decision at/after previous exit fill
            prev_exit = tr.exit_idx.to_numpy()[:-1]
            assert np.all(tr.decision_idx.to_numpy()[1:] >= prev_exit)
    return tr, pd.DataFrame(orders, columns=["decision_idx", "side", "weight", "filled"])


# ---------------- accounting ----------------
class Book:
    """Per-trade arrays, PESS funding cashflows, 1m net4 P&L for one simulated stream over [lo, hi)."""

    def __init__(self, m: Market, tr: pd.DataFrame, orders: pd.DataFrame, lo: int, hi: int):
        self.m, self.tr, self.orders, self.lo, self.hi = m, tr, orders, lo, hi
        n = len(tr)
        self.s = tr.side.to_numpy(int)
        self.w = tr.entry_weight_frozen.to_numpy(float)
        self.j0 = tr.entry_idx.to_numpy(int)
        self.px0 = tr.entry_px.to_numpy(float)
        self.closed = ~tr.open_at_end.to_numpy(bool)
        self.j1 = np.where(self.closed, tr.exit_idx.to_numpy(), hi).astype(np.int64)   # hi = never within run
        self.px1 = tr.exit_px.to_numpy(float)
        self.jx = np.where(self.closed, self.j1, hi - 1)                             # exit-fee / terminal minute
        self.gross_full = np.where(self.closed, self.s * self.w * (self.px1 / self.px0 - 1) * 1e4,
                                   self.s * self.w * (m.c[hi - 1] / self.px0 - 1) * 1e4) if n else np.zeros(0)
        # funding (PESS): adverse within [entry bar open, exit bar end); favourable within [entry bar end, exit open)
        tid, fmin, fcf = [], [], []
        end_ns = m.t[hi - 1] + MIN
        for k in range(n):
            t0 = m.t[self.j0[k]]
            adv_hi = m.t[self.j1[k]] + MIN if self.closed[k] else end_ns
            fav_hi = m.t[self.j1[k]] if self.closed[k] else end_ns
            a, b = np.searchsorted(m.ft, t0), np.searchsorted(m.ft, adv_hi)
            if b <= a:
                continue
            ft = m.ft[a:b]
            cf = -self.s[k] * m.fr[a:b] * 1e4 * self.w[k]
            keep = (cf < 0) | ((ft >= t0 + MIN) & (ft < fav_hi))
            tid.append(np.full(keep.sum(), k)); fmin.append(np.searchsorted(m.t, ft[keep], "right") - 1)
            fcf.append(cf[keep])
        cat = lambda x, d: np.concatenate(x) if x else np.zeros(0, d)  # noqa: E731
        self.f_tid, self.f_min, self.f_cf = cat(tid, int), cat(fmin, int), cat(fcf, float)
        self.fund_full = np.bincount(self.f_tid, self.f_cf, minlength=n) if n else np.zeros(0)
        self.net4_full = self.gross_full + self.fund_full - 4 * self.w
        # 1m net4 P&L
        N = m.N
        pnl = np.zeros(N)
        if n:
            a = self.s * self.w / self.px0 * 1e4
            dif = np.zeros(N + 1)
            np.add.at(dif, self.j0 + 1, a)
            np.add.at(dif, self.j1, -a)
            coef = np.cumsum(dif)[:N]
            dc = np.diff(m.c, prepend=m.c[0])
            pnl = coef * dc
            np.add.at(pnl, self.j0, a * (m.c[self.j0] - self.px0) - 2 * self.w)
            cj = self.closed
            np.add.at(pnl, self.j1[cj], a[cj] * (self.px1[cj] - m.c[self.j1[cj] - 1]))
            np.add.at(pnl, self.jx, -2 * self.w)
            np.add.at(pnl, self.f_min, self.f_cf)
            held = np.zeros(N + 1, int)
            np.add.at(held, self.j0, 1)
            np.add.at(held, np.where(cj, self.j1 + 1, hi), -1)
            self.held_day = (np.cumsum(held)[:N] > 0).reshape(-1, 1440).any(1)
        else:
            self.held_day = np.zeros(N // 1440, bool)
        self.pnl = pnl
        assert abs(pnl[lo:hi].sum() - self.net4_full.sum()) < 1e-6 * max(1.0, np.abs(self.net4_full).sum())

    def gross_upto(self, x: int) -> np.ndarray:
        """Cumulative gross (bps) of each trade after minutes < x are marked."""
        k = x - 1
        mark = self.s * self.w * (self.m.c[min(max(k, 0), self.m.N - 1)] / self.px0 - 1) * 1e4
        return np.where(k < self.j0, 0.0, np.where(self.closed & (k >= self.j1), self.gross_full, mark))

    def window(self, a: int, b: int) -> dict:
        m, n = self.m, len(self.s)
        nd = (b - a) // 1440
        out = {"days": nd}
        if n:
            gross = self.gross_upto(b) - self.gross_upto(a)
            legs = ((self.j0 >= a) & (self.j0 < b)).astype(float) + ((self.jx >= a) & (self.jx < b))
            fm = (self.f_min >= a) & (self.f_min < b)
            fund = np.bincount(self.f_tid[fm], self.f_cf[fm], minlength=n)
            part4 = gross + fund - 2 * self.w * legs
            part8 = gross + fund - 4 * self.w * legs
            exp_days = self.w * np.clip(np.minimum(np.where(self.closed, self.j1 + 1, self.hi), b)
                                        - np.maximum(self.j0, a), 0, None) / 1440
            closed_in = self.closed & (self.j1 >= a) & (self.j1 < b)
            open_end = (self.j0 < b) & (~self.closed | (self.j1 >= b))
            lat = (self.j1 - self.tr.exit_decision_idx.to_numpy())[closed_in]
        else:
            gross = fund = part4 = part8 = exp_days = legs = np.zeros(0)
            closed_in = open_end = np.zeros(0, bool)
            lat = np.zeros(0)
        assert abs(part4.sum() - self.pnl[a:b].sum()) < 1e-6 * max(1.0, np.abs(part4).sum()), "window partition"
        for tag, mk in (("all", np.ones(n, bool)), ("long", self.s > 0), ("short", self.s < 0)):
            p = "" if tag == "all" else tag + "_"
            out[p + "net4"] = float(part4[mk].sum())
            out[p + "net8"] = float(part8[mk].sum())
            out[p + "gross"] = float(gross[mk].sum())
            out[p + "funding"] = float(fund[mk].sum())
            out[p + "closed"] = int((closed_in & mk).sum())
            out[p + "entries"] = int((mk & (self.j0 >= a) & (self.j0 < b)).sum()) if n else 0
            out[p + "open_n"] = int((open_end & mk).sum())
            out[p + "open_mtm"] = float(part4[open_end & mk].sum())
            out[p + "win"] = float((self.net4_full[closed_in & mk] > 0).mean()) if (closed_in & mk).any() else np.nan
            out[p + "exp_days"] = float(exp_days[mk].sum())
            out[p + "per_day"] = out[p + "net4"] / nd
        out["turnover"] = float((self.w * legs).sum()) if n else 0.0
        od = self.orders
        om = (od.decision_idx >= a) & (od.decision_idx < b)
        out["orders"] = int(om.sum())
        out["order_notional"] = float(od.weight[om].sum())
        out["fill_notional_rate"] = (float(od.weight[om & od.filled].sum()) / out["order_notional"]
                                     if out["order_notional"] > 0 else np.nan)
        out["exit_latency_p50"] = float(np.median(lat)) if len(lat) else np.nan
        out["exit_latency_p95"] = float(np.quantile(lat, 0.95)) if len(lat) else np.nan
        eq = np.concatenate([[0.0], np.cumsum(self.pnl[a:b])])
        out["mdd_1m"] = float((np.maximum.accumulate(eq) - eq).max())
        daily = self.pnl[a:b].reshape(-1, 1440).sum(1)
        sd = daily.std(ddof=1)
        out["sharpe"] = float(daily.mean() / sd * np.sqrt(365)) if sd > 0 else np.nan
        days = pd.date_range(pd.Timestamp(m.t[a], tz="UTC"), periods=nd, freq="D")
        mon = pd.Series(daily, index=days).groupby(days.strftime("%Y-%m")).sum()
        act = pd.Series(self.held_day[a // 1440:b // 1440], index=days).groupby(days.strftime("%Y-%m")).any()
        out["active_months"] = int(act.sum())
        out["pos_month_ratio"] = float((mon[act] > 0).mean()) if act.any() else np.nan
        return out

    def daily(self, a: int, b: int) -> np.ndarray:
        return self.pnl[a:b].reshape(-1, 1440).sum(1)


def stationary_boot_p05(x: np.ndarray, block: int, n_boot: int = NBOOT, seed: int = SEED) -> float:
    """Politis-Romano stationary bootstrap (circular, geometric blocks, mean `block`), p05 of the mean."""
    n = len(x)
    rng = np.random.default_rng(seed)
    means = []
    for c in range(0, n_boot, 1000):       # chunked: bounded memory on the 2192-day DEV series
        k = min(1000, n_boot - c)
        new = rng.random((k, n)) < 1.0 / block
        new[:, 0] = True
        starts = rng.integers(0, n, size=(k, n))
        pos = np.broadcast_to(np.arange(n), (k, n))
        last = np.maximum.accumulate(np.where(new, pos, 0), axis=1)
        idx = (np.take_along_axis(starts, last, axis=1) + pos - last) % n
        means.append(x[idx].mean(axis=1))
    return float(np.quantile(np.concatenate(means), 0.05))


# ---------------- feature helpers ----------------
def shift(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:-k] if k else x
    return out


def roll(x: np.ndarray, n: int, fn: str, min_periods: int | None = None) -> np.ndarray:
    return getattr(pd.Series(x).rolling(n, min_periods=min_periods or n), fn)().to_numpy()


def z_prev(x: np.ndarray, n: int) -> np.ndarray:
    """z of x_t vs the previous n values (current excluded)."""
    mu, sd = shift(roll(x, n, "mean"), 1), shift(roll(x, n, "std"), 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sd > 0, (x - mu) / sd, np.nan)


def tsmom_score(c: np.ndarray, lookbacks, sigma_bars: int) -> tuple[np.ndarray, np.ndarray]:
    """Mean clipped z over lookbacks; sigma = std of the previous sigma_bars log returns (current excluded)."""
    lr = np.diff(np.log(c), prepend=np.nan)
    sig = shift(roll(lr, sigma_bars, "std"), 1)
    zs = [np.clip(np.log(c / shift(c, L)) / (sig * np.sqrt(L)), -3, 3) for L in lookbacks]
    return np.mean(zs, axis=0), sig


def asof_bars(src_dec: np.ndarray, dst_dec: np.ndarray) -> np.ndarray:
    """Position of the latest source bar whose decision bar <= dst decision bar (-1 if none)."""
    p = np.searchsorted(src_dec, dst_dec, "right") - 1
    assert np.all(src_dec[p[p >= 0]] <= dst_dec[p >= 0])
    return p


def take(x: np.ndarray, p: np.ndarray) -> np.ndarray:
    return np.where(p >= 0, x[np.maximum(p, 0)], np.nan)


def asof_values(avail_ns: np.ndarray, values: np.ndarray, T: np.ndarray, ttl_ns: int | None) -> np.ndarray:
    """Latest value with available_time <= T (and age <= ttl); NaN otherwise."""
    p = np.searchsorted(avail_ns, T, "right") - 1
    ok = p >= 0
    out = np.full(len(T), np.nan)
    out[ok] = values[p[ok]]
    assert np.all(avail_ns[p[ok]] <= T[ok]), "as-of value available after decision"
    if ttl_ns is not None:
        out[ok & (T - avail_ns[np.maximum(p, 0)] > ttl_ns)] = np.nan
    return out


# ---------------- data ----------------
def load_all():
    dev = data.load_minutes(DEV_MARKET, end=SPLIT)
    test = pd.read_parquet(SNAP / "market_1m.parquet", columns=data.MINUTE_COLUMNS)
    test["open_time"] = pd.to_datetime(test.open_time, utc=True).astype("datetime64[ns, UTC]")
    minutes = data.validate_minutes(pd.concat([dev, test], ignore_index=True))
    assert minutes.open_time.iloc[0] == START and minutes.open_time.iloc[-1] == END - pd.Timedelta(minutes=1)
    met = pd.concat([data.load_metrics(DEV_METRICS, end=SPLIT), pd.read_parquet(SNAP / "technique_metrics.parquet")],
                    ignore_index=True)
    met["available_time"] = pd.to_datetime(met.available_time, utc=True).astype("datetime64[ns, UTC]")
    met = met.loc[met.available_time <= END].drop_duplicates("available_time", keep="last").sort_values(
        "available_time").reset_index(drop=True)
    prem = pd.concat([data.load_premium(DEV_PREMIUM, end=SPLIT), pd.read_parquet(SNAP / "technique_premium.parquet")],
                     ignore_index=True)
    prem["available_time"] = pd.to_datetime(prem.available_time, utc=True).astype("datetime64[ns, UTC]")
    prem = prem.loc[prem.available_time <= END].drop_duplicates("available_time", keep="last").sort_values(
        "available_time").reset_index(drop=True)
    fr = load_funding_dir(DEV_FUNDING)
    f_dev = pd.DataFrame({"time": [r.funding_time for r in fr], "rate": [r.funding_rate for r in fr]})
    f_dev["time"] = pd.to_datetime(f_dev.time, utc=True)
    f_dev = f_dev.loc[f_dev.time < SPLIT]
    fmi = pd.read_parquet(SNAP / "funding_model_input.parquet")
    f_test = pd.DataFrame({"time": pd.to_datetime(fmi.publish_time, utc=True), "rate": fmi.rate.to_numpy(float)})
    funding = pd.concat([f_dev, f_test], ignore_index=True).sort_values("time").reset_index(drop=True)
    funding["time"] = funding.time.astype("datetime64[ns, UTC]")
    return minutes, met, prem, funding


def premium_minutes(m: Market, prem: pd.DataFrame) -> np.ndarray:
    """prem[k] = premium of minute bar k (available at t[k] + 1m); NaN if missing."""
    out = np.full(m.N, np.nan)
    at = prem.available_time.array.asi8
    k = np.searchsorted(m.t, at - MIN)
    ok = (k < m.N) & (m.t[np.minimum(k, m.N - 1)] == at - MIN)
    out[k[ok]] = prem.premium.to_numpy(float)[ok]
    return out


def funding_slots(m: Market) -> tuple[np.ndarray, np.ndarray]:
    """Settlement slot (0/8/16 UTC hour, else -1) and the 1m decision bar containing each publish."""
    tod = (m.ft % DAY) / HOUR
    slot = np.round(tod).astype(int)
    slot = np.where((np.abs(tod - slot) < 1 / 60) & np.isin(slot % 24, (0, 8, 16)), slot % 24, -1)
    dec = np.searchsorted(m.t, m.ft, "right") - 1
    ok = dec >= 0
    assert np.all(m.t[dec[ok]] + MIN > m.ft[ok]), "funding decision bar closes after publish"
    return slot, dec


# ---------------- features / signals per family ----------------
class Features:
    def __init__(self, m: Market, met: pd.DataFrame, prem: pd.DataFrame):
        self.m, self.met, self.prem_df = m, met, prem
        N = m.N
        self.h1 = np.arange(59, N, 60)
        self.h4 = np.arange(239, N, 240)
        self.d1 = np.arange(1439, N, 1440)
        self.prem = premium_minutes(m, prem)
        self.fslot, self.fdec = funding_slots(m)
        self.fz90 = b1.trailing_robust_z(m.fr, 90, 30)          # all events, current excluded
        self.met_at = met.available_time.array.asi8
        t0 = time.time()
        self._v()
        print(f"[feat] V {time.time()-t0:.0f}s", flush=True)

    # V / K-V
    def _v(self):
        m = self.m
        sets = {"1h": (60, self.h1, (6, 24, 72, 168), 720), "4h": (240, self.h4, (6, 18, 42, 168), 180),
                "1d": (1440, self.d1, (30, 90, 180, 360), 30)}
        self.S = {}
        for k, (res, dec, L, sb) in sets.items():
            sc, sig = tsmom_score(m.c[dec], L, sb)
            p = asof_bars(dec, self.h1)
            self.S[k] = take(sc, p)
            if k == "1h":
                self.sig1h_ann = sig * np.sqrt(8760)
        # K-B1 base: Batch-1 feature code unchanged (daily bars, sigma incl. current closed bar)
        fb = b1.tsmom_features(m, 1440, (30, 90, 180, 360), 30)
        p = asof_bars(fb.dec_idx.to_numpy(), self.h1)
        self.B1_score, self.B1_sig = take(fb.score.to_numpy(), p), take(fb.sigma_ann.to_numpy(), p)

    def v_score(self, blend):
        w = {"fast": (0.5, 0.5, 0), "balanced": (0.25, 0.5, 0.25), "slow": (0, 0.5, 0.5)}[blend]
        return w[0] * self.S["1h"] + w[1] * self.S["4h"] + w[2] * self.S["1d"]

    # E
    def e_events(self, thr):
        m, out_d, out_s = self.m, [], []
        for sl in (0, 8, 16):
            ix = np.flatnonzero(self.fslot == sl)
            z = b1.trailing_robust_z(m.fr[ix], 90, 30)
            ok = np.abs(z) >= thr
            out_d.append(self.fdec[ix][ok]); out_s.append(-np.sign(z[ok]).astype(int))
        d, s = np.concatenate(out_d), np.concatenate(out_s)
        o = np.argsort(d, kind="stable")
        d, s = d[o], s[o]
        keep = np.concatenate([[True], np.diff(d) > 0])
        return d[keep], s[keep]

    # F
    def f_prep(self):
        m = self.m
        dec5 = np.arange(4, m.N, 5)
        T = m.t[dec5] + MIN
        oi_vals = self.met.oi.to_numpy(float)
        oi_vals = np.where(oi_vals > 0, oi_vals, np.nan)
        oi = asof_values(self.met_at, oi_vals, T, 10 * MIN)
        oi_prev = asof_values(self.met_at, oi_vals, T - HOUR, 10 * MIN)
        cs = lambda x: np.concatenate([[0.0], np.cumsum(x)])  # noqa: E731
        cv, ci = cs(m.v), cs(2 * m.tb - m.v)
        a = np.maximum(dec5 - 59, 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            I = (ci[dec5 + 1] - ci[a]) / (cv[dec5 + 1] - cv[a])
            r = np.log(m.c[dec5] / shift(m.c[dec5], 12))
            doi = np.log(oi / oi_prev)
            lr5 = np.diff(np.log(m.c[dec5]), prepend=np.nan)
            rv = np.sqrt(roll(lr5 ** 2, 12, "sum"))
            resp = np.sign(I) * r / rv
        I[dec5 < 59] = np.nan
        W, MP = 180 * 288, 90 * 288
        absI = pd.Series(np.abs(I))
        dS = pd.Series(doi)
        self.F = {"dec": dec5, "I": I, "doi": doi, "resp": resp,
                  "qI": {q: b1.trailing_quantile(absI, q, W, MP).to_numpy() for q in (0.80, 0.90)},
                  "qO": {q: b1.trailing_quantile(dS, q, W, MP).to_numpy() for q in (0.60, 0.80)}}
        self.F["gaps"] = {"oi_nan_5m": int(np.isnan(oi).sum()), "I_nan": int(np.isnan(I).sum())}

    def f_events(self, qi, qo, rmax):
        F = self.F
        with np.errstate(invalid="ignore"):
            cond = ((np.abs(F["I"]) >= F["qI"][qi]) & (F["doi"] >= F["qO"][qo]) & (F["resp"] <= rmax)
                    & (F["I"] != 0))
        first = cond & ~np.concatenate([[False], cond[:-1]])
        return F["dec"][first], -np.sign(F["I"][first]).astype(int)

    # G
    def g_prep(self):
        c4 = self.m.c[self.h4]
        lr = np.diff(np.log(c4), prepend=np.nan)
        self.G = {"svi": {}, "score": {}}
        r2 = lr ** 2
        for W in (42, 180):
            pos, neg, tot = (roll(np.where(lr > 0, r2, 0.0), W, "sum"), roll(np.where(lr < 0, r2, 0.0), W, "sum"),
                             roll(r2, W, "sum"))
            self.G["svi"][W] = (pos - neg) / (tot + 1e-12)
        for ts in ((6, 18, 42), (42, 168, 504)):
            sc, sig = tsmom_score(c4, ts, 180)
            self.G["score"][ts] = sc
        self.G["sig_ann"] = sig * np.sqrt(6 * 365)

    # H
    def h_prep(self):
        m, dec = self.m, self.h4
        n4 = len(dec)
        T = m.t[dec] + MIN
        H = m.h[: n4 * 240].reshape(n4, 240).max(1)
        L = m.l[: n4 * 240].reshape(n4, 240).min(1)
        V = m.v[: n4 * 240].reshape(n4, 240).sum(1)
        TB = m.tb[: n4 * 240].reshape(n4, 240).sum(1)
        C = m.c[dec]
        lr = np.diff(np.log(C), prepend=np.nan)
        f = {}
        for k in (1, 3, 6, 18, 42):
            f[f"ret{k}"] = np.log(C / shift(C, k))
        for k in (6, 42):
            f[f"rv{k}"] = np.sqrt(roll(lr ** 2, k, "sum"))
        f["range_z42"] = z_prev((H - L) / C, 42)
        f["volume_z42"] = z_prev(np.log(V), 42)
        for k in (1, 6):
            f[f"timb{k}"] = roll(2 * TB - V, k, "sum") / roll(V, k, "sum")
        ttl = 10 * MIN
        for col in ("oi", "global_ls", "top_ls", "taker_lsr"):
            v = self.met[col].to_numpy(float)
            v = np.where(v > 0, v, np.nan)
            lv = np.log(asof_values(self.met_at, v, T, ttl))
            if col == "oi":
                for k in (1, 3, 6):
                    f[f"doi{k}"] = lv - shift(lv, k)
            else:
                f[f"{col}_log"], f[f"{col}_chg1"] = lv, lv - shift(lv, 1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            pm = np.nanmean(self.prem[: n4 * 240].reshape(n4, 240), axis=1)   # every minute in bar ends <= T
        f["prem_mean6"] = roll(pm, 6, "mean", 1)
        f["prem_z180"] = z_prev(pm, 180)
        f["funding_last"] = asof_values(self.m.ft, self.m.fr, T, None)
        f["funding_z90"] = asof_values(self.m.ft, self.fz90, T, None)
        hr = (T % DAY) / HOUR
        dow = ((T // DAY) + 3) % 7          # 1970-01-01 was a Thursday -> Monday = 0
        f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)
        f["dow_sin"], f["dow_cos"] = np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7)
        X = np.column_stack(list(f.values()))
        X[~np.isfinite(X)] = np.nan
        self.H = {"names": list(f), "X": X, "T": T, "C": C}

    def h_fit(self, h: int, lam: float):
        """Monthly refit ridge + split-conformal |residual| quantiles. Returns pred, q80, q90 per 4h decision and
        coefficient rows."""
        X, T, C, names = self.H["X"], self.H["T"], self.H["C"], self.H["names"]
        n4 = len(T)
        y = np.log(shift(C[::-1], h)[::-1] / C)                       # y_t = log(C_{t+h}/C_t)
        yend = np.concatenate([T[h:], np.full(h, np.iinfo(np.int64).max)])
        pred, q80, q90 = (np.full(n4, np.nan) for _ in range(3))
        rows = []
        months = pd.date_range(OI_START, END, freq="MS", tz="UTC")
        for R, R2 in zip(months, list(months[1:]) + [END]):
            R, R2 = R.value, R2.value
            tr = (T >= R - 910 * DAY) & (yend < R - 180 * DAY) & np.isfinite(y)
            ca = (T >= R - 180 * DAY) & (yend <= R) & np.isfinite(y)
            assert not np.any(tr & ca) and np.all(yend[tr | ca] <= R), "label leak into refit"
            if tr.sum() < 500 or ca.sum() < 200:
                continue
            Xt = X[tr]
            with warnings.catch_warnings():     # all-NaN train column (e.g. metrics before 2020-09) -> median 0
                warnings.simplefilter("ignore", RuntimeWarning)
                med = np.nanmedian(Xt, axis=0)
            med = np.where(np.isfinite(med), med, 0.0)

            def design(Z):
                miss = np.isnan(Z)
                return np.column_stack([np.where(miss, med, Z), miss.astype(float)])

            Dt = design(Xt)
            mu, sd = Dt.mean(0), Dt.std(0)
            sd = np.where(sd > 0, sd, 1.0)
            Zt = (Dt - mu) / sd
            ybar = y[tr].mean()
            beta = np.linalg.solve(Zt.T @ Zt + lam * np.eye(Zt.shape[1]), Zt.T @ (y[tr] - ybar))
            f = lambda Z: ((design(Z) - mu) / sd) @ beta + ybar  # noqa: E731
            res = np.abs(y[ca] - f(X[ca]))
            qa, qb = np.quantile(res, 0.80), np.quantile(res, 0.90)
            mk = (T >= R) & (T < R2)
            pred[mk], q80[mk], q90[mk] = f(X[mk]), qa, qb
            rows.append({"h": h, "lam": lam, "refit": pd.Timestamp(R, tz="UTC"), "n_train": int(tr.sum()),
                         "n_cal": int(ca.sum()), "intercept": ybar, "q80": qa, "q90": qb,
                         **{n: b for n, b in zip(names + [f"miss_{x}" for x in names], beta)}})
        return pred, {0.80: q80, 0.90: q90}, rows

    # I
    def i_events(self, weeks, tail, hold):
        m, d = self.m, self.h1
        T = m.t[d] + MIN
        y = np.full(len(d), np.nan)
        ok = d + hold < m.N
        y[ok] = np.log(m.c[d[ok] + hold] / m.c[d[ok]])
        yend = T + hold * MIN
        cell = (((T // DAY) + 3) % 7) * 24 + (T % DAY) // HOUR
        side = np.zeros(len(d), int)
        k = int(round(tail * 168))
        mondays = T[(cell == 0)]
        for U in mondays:
            if U - START.value < 52 * 7 * DAY:
                continue
            mk = (T >= U - weeks * 7 * DAY) & (yend <= U) & np.isfinite(y)
            assert np.all(yend[mk] <= U)
            n = np.bincount(cell[mk], minlength=168)
            s = np.bincount(cell[mk], y[mk], minlength=168)
            gm = y[mk].mean()
            shr = (s + 26 * gm) / (n + 26)
            o = np.argsort(shr, kind="stable")
            lng = [c for c in o[-k:] if shr[c] > THR]
            sht = [c for c in o[:k] if shr[c] < -THR]
            cs = np.zeros(168, int)
            cs[lng], cs[sht] = 1, -1
            wk = (T >= U) & (T < U + 7 * DAY)
            side[wk] = cs[cell[wk]]
        ev = side != 0
        return d[ev], side[ev]

    # J
    def j_events(self, lead, thr):
        m = self.m
        days = np.arange(START.value // DAY, END.value // DAY + 1) * DAY
        settles = (days[:, None] + np.array([0, 8, 16]) * HOUR).ravel()
        T = settles - lead * MIN
        dec = np.searchsorted(m.t, T) - 1                    # bar ending exactly at T
        ok = (dec >= 480) & (dec < m.N) & (T <= m.t[-1] + MIN)
        dec, T, slot = dec[ok], T[ok], ((settles[ok] % DAY) // HOUR)
        assert np.all(m.t[dec] + MIN == T)
        pr = self.prem
        cnt = np.concatenate([[0], np.cumsum(np.isfinite(pr))])
        sm = np.concatenate([[0.0], np.cumsum(np.nan_to_num(pr))])
        n = cnt[dec + 1] - cnt[dec - 479]
        with np.errstate(invalid="ignore", divide="ignore"):
            p480 = (sm[dec + 1] - sm[dec - 479]) / n
        fresh = np.isfinite(pr[dec]) | np.isfinite(pr[dec - 1])     # newest premium age <= 2m else fail-closed
        rate = asof_values(m.ft, m.fr, T, None)
        wedge = np.where(fresh & (n > 0), p480 - rate, np.nan)
        out_d, out_s = [], []
        for sl in (0, 8, 16):
            ix = np.flatnonzero(slot == sl)
            z = b1.trailing_robust_z(wedge[ix], 90, 30)
            e = np.abs(z) >= thr
            out_d.append(dec[ix][e]); out_s.append(-np.sign(z[e]).astype(int))
        d, s = np.concatenate(out_d), np.concatenate(out_s)
        o = np.argsort(d)
        return d[o], s[o]


# ---------------- grids ----------------
def grid():
    V = [dict(family="V", blend=b, db=db, tv=tv, gate=g, sizing=sz, offset=o)
         for b in ("fast", "balanced", "slow") for db in (0.25, 0.50) for tv in (0.20, 0.40)
         for g in (0.0, -0.25) for sz in ("binary", "conviction") for o in (2, 5)]
    E = [dict(family="E", zthr=z, hold=h, offset=o) for z in (1.5, 2.0, 2.5) for h in (30, 120, 480) for o in (2, 5)]
    F = [dict(family="F", qI=a, qOI=b, resp=r, hold=h, offset=o) for a in (0.80, 0.90) for b in (0.60, 0.80)
         for r in (0.0, 0.25) for h in (60, 240, 720) for o in (2, 5)]
    G = [dict(family="G", svi_w=w, g=g, trend=str(ts), db=db, tv=tv, offset=o) for w in (42, 180) for g in (0.0, 0.10)
         for ts in ((6, 18, 42), (42, 168, 504)) for db in (0.25, 0.50) for tv in (0.20, 0.40) for o in (2, 5)]
    H = [dict(family="H", h=h, lam=lam, q=q, offset=o) for h in (2, 6, 18) for lam in (0.1, 1.0, 10.0)
         for q in (0.80, 0.90) for o in (2, 5)]
    I = [dict(family="I", weeks=w, tail=t, hold=h, offset=o) for w in (104, 208) for t in (0.10, 0.20)
         for h in (60, 240, 480) for o in (2, 5)]
    J = [dict(family="J", lead=ld, zthr=z, hold=h, offset=o) for ld in (30, 60) for z in (1.0, 1.5, 2.0)
         for h in (60, 240, 480) for o in (2, 5)]
    K = [dict(family="K", base=b, g=g, action=a, tv=tv, offset=o) for b in ("B1", "V") for g in (0.0, 1.0)
         for a in ("veto", "flat30") for tv in (0.20, 0.40) for o in (2, 5)]
    out = V + E + F + G + H + I + J + K
    assert len(out) == 354 and sum(p["offset"] == 2 for p in out) == 177
    return out


def vid(p: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in p.items())


class Runner:
    """Builds the signal for a variant and runs the continuous simulation."""

    def __init__(self, m: Market, fe: Features):
        self.m, self.fe = m, fe
        self.hcache, self.coef_rows, self.scache = {}, [], {}
        self.kdec = None

    def lo(self, fam: str) -> int:
        return self.m.idx(OI_START) if fam in ("F", "H") else 0

    def signal(self, p: dict):
        key = vid({k: v for k, v in p.items() if k != "offset"})
        if key not in self.scache:          # signals do not depend on the entry offset
            self.scache[key] = self._signal(p)
        return self.scache[key]

    def _signal(self, p: dict):
        fe, fam = self.fe, p["family"]
        if fam == "V":
            sc = fe.v_score(p["blend"])
            with np.errstate(invalid="ignore"):
                des = np.where(np.abs(sc) >= p["db"], np.sign(sc), 0)
                des = np.where((des < 0) & ~(fe.S["1d"] <= p["gate"]), 0, des)
                conv = np.clip(np.abs(sc) - p["db"], 0, 1) if p["sizing"] == "conviction" else 1.0
                w = np.minimum(1.0, p["tv"] / fe.sig1h_ann) * conv
            return dict(kind="state", dec=fe.h1, side=np.nan_to_num(des).astype(int), weight=np.nan_to_num(w),
                        ttl=TTL_TREND)
        if fam == "E":
            d, s = fe.e_events(p["zthr"])
            return dict(kind="event", dec=d, side=s, weight=np.ones(len(d)), ttl=TTL_EVENT, hold=p["hold"])
        if fam == "F":
            d, s = fe.f_events(p["qI"], p["qOI"], p["resp"])
            return dict(kind="event", dec=d, side=s, weight=np.ones(len(d)), ttl=TTL_EVENT, hold=p["hold"])
        if fam == "G":
            G = fe.G
            sc, svi = G["score"][eval(p["trend"])], G["svi"][p["svi_w"]]
            with np.errstate(invalid="ignore"):
                des = np.where((sc >= p["db"]) & (svi >= p["g"]), 1, np.where((sc <= -p["db"]) & (svi <= -p["g"]), -1, 0))
                w = np.minimum(1.0, p["tv"] / G["sig_ann"])
            return dict(kind="state", dec=fe.h4, side=des, weight=np.nan_to_num(w), ttl=TTL_TREND)
        if fam == "H":
            key = (p["h"], p["lam"])
            if key not in self.hcache:
                pred, qs, rows = fe.h_fit(*key)
                self.hcache[key] = (pred, qs)
                self.coef_rows += rows
            pred, qs = self.hcache[key]
            qa = qs[p["q"]]
            with np.errstate(invalid="ignore"):
                s = np.where(pred - qa > THR, 1, np.where(pred + qa < -THR, -1, 0))
            ev = s != 0
            return dict(kind="event", dec=fe.h4[ev], side=s[ev], weight=np.ones(ev.sum()), ttl=TTL_TREND,
                        hold=p["h"] * 240)
        if fam == "I":
            d, s = fe.i_events(p["weeks"], p["tail"], p["hold"])
            return dict(kind="event", dec=d, side=s, weight=np.ones(len(d)), ttl=TTL_EVENT, hold=p["hold"])
        if fam == "J":
            d, s = fe.j_events(p["lead"], p["zthr"])
            return dict(kind="event", dec=d, side=s, weight=np.ones(len(d)), ttl=TTL_EVENT, hold=p["hold"])
        if fam == "K":
            return self.k_signal(p)
        raise ValueError(fam)

    def k_signal(self, p):
        fe, m = self.fe, self.m
        if self.kdec is None:      # hourly decisions + settle-30m points
            days = np.arange(START.value // DAY, END.value // DAY + 1) * DAY
            pre = np.searchsorted(m.t, (days[:, None] + np.array([0, 8, 16]) * HOUR).ravel() - 30 * MIN) - 1
            pre = pre[(pre > 0) & (pre < m.N)]
            allp = np.union1d(fe.h1, pre)
            self.kdec, self.kpre = allp, np.isin(allp, pre)
            self.kpos = asof_bars(fe.h1, allp)           # hourly feature row as-of each decision
            self.kz = asof_values(m.ft, fe.fz90, m.t[allp] + MIN, None)
        p_h = self.kpos
        if p["base"] == "B1":
            sc, sig = take(fe.B1_score, p_h), take(fe.B1_sig, p_h)
        else:
            sc, sig = take(fe.v_score("balanced"), p_h), take(fe.sig1h_ann, p_h)
        with np.errstate(invalid="ignore"):
            des = np.nan_to_num(np.where(np.abs(sc) >= 0.25, np.sign(sc), 0)).astype(int)
            w = np.nan_to_num(np.minimum(1.0, p["tv"] / sig))
            adverse = ((des > 0) & (self.kz > p["g"])) | ((des < 0) & (self.kz < -p["g"]))
        if p["action"] == "veto":
            ok = ~adverse
            dec, ok = self.kdec[~self.kpre], ok[~self.kpre]
            return dict(kind="state", dec=dec, side=des[~self.kpre], weight=w[~self.kpre], ttl=TTL_TREND, entry_ok=ok)
        des = np.where(self.kpre & adverse, 0, des)
        return dict(kind="state", dec=self.kdec, side=des, weight=w, ttl=TTL_TREND, entry_ok=~self.kpre)

    def run(self, p: dict, pen: float = PEN_BPS, offset: float | None = None, sig: dict | None = None):
        sig = sig or self.signal(p)
        lo = self.lo(p["family"])
        tr, od = simulate(self.m, sig["kind"], sig["dec"], sig["side"], sig["weight"],
                          p["offset"] if offset is None else offset, sig["ttl"], pen, lo, self.m.N,
                          hold=sig.get("hold", 0), entry_ok=sig.get("entry_ok"))
        return Book(self.m, tr, od, lo, self.m.N)


def window_bounds(m: Market, fam: str) -> dict:
    s0 = OI_START if fam in ("F", "H") else START
    return {k: (m.idx(max(a, s0)), m.idx(b)) for k, (a, b) in WINDOWS.items()}


def evaluate(book: Book, wb: dict) -> dict:
    return {w: book.window(a, b) for w, (a, b) in wb.items()}


# ---------------- selection ----------------
def eligible(r: dict, twin: dict) -> bool:
    ok = all(r[f"{w}_{s}net4"] > 0 for w in ("DEV-FULL", "DEV-B") for s in ("", "long_", "short_"))
    ok &= all(r[f"DEV-FULL_{s}_closed"] >= 20 or r[f"DEV-FULL_{s}_exp_days"] >= 180 for s in SIDES)
    ok &= (r["DEV-FULL_fill_notional_rate"] or 0) >= 0.10
    ok &= all(twin[f"{w}_{s}_net4"] > 0 for w in ("DEV-FULL", "DEV-B") for s in SIDES)
    return bool(ok)


def dev_score(r: dict) -> float:
    return min(r[f"{w}_{s}_per_day"] for w in ("DEV-A", "DEV-B") for s in SIDES)


def adaptive_score(r: dict, twin: dict) -> float:
    return min(r["TEST_long_per_day"], r["TEST_short_per_day"], twin["TEST_long_per_day"], twin["TEST_short_per_day"])


def verdict(r: dict, twin: dict, boot60: float, elig: bool) -> dict:
    profit = (elig and all(r[f"{w}_{s}_net4"] > 0 for w in ("DEV-FULL", "DEV-B", "TEST") for s in SIDES)
              and all(twin[f"{w}_{s}_net4"] > 0 for w in ("DEV-FULL", "DEV-B", "TEST") for s in SIDES))
    low_n = any(r[f"TEST_{s}_closed"] < 10 for s in SIDES)
    strong = profit and not low_n and boot60 > 0
    kill = any(r[f"{w}_{s}_net4"] <= 0 for w in ("DEV-B", "TEST") for s in SIDES)
    tags = (["STRONG"] if strong else ["PROFIT_PASS"] if profit else []) + (["LOW_N"] if low_n else []) + \
        (["KILL"] if kill else [])
    return {"PROFIT_PASS": profit, "LOW_N": low_n, "STRONG": strong, "KILL": kill,
            "verdict": "+".join(tags) if tags else "FAIL"}


# ---------------- provenance ----------------
def input_hashes() -> dict:
    h = {"dev_market": provenance.file_sha256(DEV_MARKET),
         "dev_metrics_tree": provenance.tree_sha256(DEV_METRICS, "*.zip")["sha256"],
         "dev_premium_tree": provenance.tree_sha256(DEV_PREMIUM, "*.zip")["sha256"],
         "dev_funding_tree": provenance.tree_sha256(DEV_FUNDING, "*.zip")["sha256"],
         "batch1_code": provenance.file_sha256(ROOT / "out/run_new_model_batch1_20261010.py"),
         "code": provenance.file_sha256(Path(__file__))}
    for f in ("market_1m.parquet", "technique_metrics.parquet", "technique_premium.parquet",
              "funding_model_input.parquet", "manifest.json"):
        h["snap_" + f] = provenance.file_sha256(SNAP / f)
    return h


def git_state() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"head": g("rev-parse", "HEAD"), "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_files": len(g("status", "--porcelain").splitlines())}


def registry_keys(path: Path) -> set:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if '"idempotency_key"' in line:
            keys.add(json.loads(line).get("idempotency_key"))
    return keys


def write_registry(grid_df: pd.DataFrame, sel: dict, hashes: dict, run_id: str, fam_counts: dict) -> dict:
    have = registry_keys(REGISTRY)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    for r in grid_df.to_dict("records"):
        key = hashlib.sha256(canonical({"batch": "NM-B2", "variant_id": r["variant_id"], "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            continue
        registry.record(REGISTRY, {
            "experiment": f"NM-B2 new-model batch-2 {r['family']} {r['variant_id']}", "idempotency_key": key,
            "config": {"variant_id": r["variant_id"], "run_id": run_id, "parent_run_id": PARENT,
                       "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
                       "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only"},
            "input_hashes": hashes, "n_trials": 1,
            "result_summary": {f"{w}_{k}": r[f"{w}_{k}"] for w in WINDOWS
                               for k in ("net4", "net8", "long_net4", "short_net4", "closed", "fill_notional_rate")}})
        added += 1
    key = hashlib.sha256(canonical({"batch": "NM-B2", "selection": True, "inputs": ih}).encode()).hexdigest()
    if key not in have:
        registry.record(REGISTRY, {"experiment": "NM-B2 new-model batch-2 selection (DEV_PICK + RESELECTED_ADAPTIVE)",
                                   "idempotency_key": key, "config": {"run_id": run_id, "parent_run_id": PARENT},
                                   "input_hashes": hashes, "n_trials": 0,
                                   "result_summary": {"batch_trials": 354, "family_counts": fam_counts,
                                                      "picks": {f: {k: v["variant_id"] for k, v in d.items()}
                                                                for f, d in sel.items()}}})
        added += 1
    else:
        skipped += 1
    return {"added": added, "skipped": skipped}


# ---------------- report ----------------
RK = ("net4", "net8", "gross", "funding", "closed", "long_net4", "long_closed", "short_net4", "short_closed",
      "open_n", "open_mtm", "win", "mdd_1m", "sharpe", "fill_notional_rate", "pos_month_ratio")


def fmt(x):
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    try:
        return "nan" if not np.isfinite(x) else f"{x:.4g}" if abs(x) < 10 else f"{x:.0f}"
    except TypeError:
        return str(x)


def write_report(run_dir: Path, run_id: str, grid_df, sel, control, manifest):
    L = [f"# {run_id} new-model batch-2", "", f"parent {PARENT}; cutoff {END}; costs maker 4 bps rt (8 report-only);"
         f" runtime {manifest['runtime_sec']}s", ""]
    for fam, d in sel.items():
        for lab, s in d.items():
            L += [f"## {fam} {lab}: {s['variant_id']}", f"eligible {s['dev_eligible']} (n_eligible {s['n_eligible']});"
                  f" verdict {s['verdict']}; DEV score {fmt(s['dev_score'])}; adaptive score {fmt(s['adaptive_score'])}",
                  f"boot p05 mean/day TEST 20/60/120 {[fmt(x) for x in s['boot_TEST']]}; DEV-FULL "
                  f"{[fmt(x) for x in s['boot_DEV-FULL']]}", "",
                  "| metric | " + " | ".join(WINDOWS) + " |", "|---" * (len(WINDOWS) + 1) + "|"]
            L += [f"| {k} | " + " | ".join(fmt(s["metrics"][w][k]) for w in WINDOWS) + " |" for k in RK]
            L += ["", "stress (offset, pen) -> net4 / long / short per window:"]
            for key, v in s["stress"].items():
                L.append(f"- {key}: " + "; ".join(f"{w} {fmt(v[w]['net4'])}/{fmt(v[w]['long_net4'])}/"
                                                   f"{fmt(v[w]['short_net4'])}" for w in WINDOWS))
            L.append("")
        g = grid_df[(grid_df.family == fam) & (grid_df.offset == 2)].sort_values("TEST_worst", ascending=False).head(5)
        cols = ["variant_id", "DEV_eligible", "DEV_score", "DEV-FULL_net4", "DEV-B_worst", "TEST_net4", "TEST_worst",
                "TEST_long_closed", "TEST_short_closed"]
        L += [f"### {fam} top5 by TEST worst-side (offset2)", "", "| " + " | ".join(cols) + " |",
              "|---" * len(cols) + "|"] + ["| " + " | ".join(fmt(x) for x in row) + " |" for row in g[cols].itertuples(
                  index=False)] + [""]
    L += ["## Control: Batch-1 A picks under fixed engine", ""]
    for v, d in control.items():
        L += [f"### {v}", "| metric | old DEV | new DEV-FULL | old TEST | new TEST |", "|---|---|---|---|---|"]
        for k in d["keys"]:
            L.append(f"| {k} | {fmt(d['old']['DEV'][k])} | {fmt(d['new']['DEV-FULL'][k])} | "
                     f"{fmt(d['old']['TEST'][k])} | {fmt(d['new']['TEST'][k])} |")
        L.append("")
    L += ["## Data gaps", "```", json.dumps(manifest["data_gaps"], indent=1, default=str), "```"]
    (run_dir / "report.md").write_text("\n".join(L), encoding="utf-8")


# ---------------- main ----------------
CONTROL = {"model=vt_tsmom|lookback_set=1d_4|deadband=0.25|target_vol=0.6|offset=2": (1440, (30, 90, 180, 360), 0.25, 0.6),
           "model=vt_tsmom|lookback_set=4h_3|deadband=0.5|target_vol=0.4|offset=2": (240, (42, 168, 504), 0.5, 0.4)}
CONTROL_MAP = {"all_net4_bps": "net4", "all_net8_bps": "net8", "all_gross_bps": "gross", "all_funding_bps": "funding",
               "all_trades": "closed", "long_net4_bps": "long_net4", "long_trades": "long_closed",
               "short_net4_bps": "short_net4", "short_trades": "short_closed", "open_positions": "open_n",
               "all_win": "win", "mdd_bps": "mdd_1m", "sharpe_daily_ann": "sharpe", "fill_rate": "fill_notional_rate",
               "positive_month_ratio": "pos_month_ratio"}


def run_control(m: Market) -> dict:
    old = pd.read_parquet(ROOT / "out/new_model_batch1_20261010/grid.parquet").set_index("variant_id")
    out = {}
    wb = window_bounds(m, "V")
    for v, (res, L, db, tv) in CONTROL.items():
        f = b1.tsmom_features(m, res, L, 30 * 1440 // res)
        sc = f.score.to_numpy()
        des = np.where(np.isnan(sc), 0, np.where(np.abs(sc) >= db, np.sign(sc), 0)).astype(int)
        w = np.minimum(1.0, tv / f.sigma_ann.to_numpy())
        w = np.where(np.isfinite(w), w, 0.0)
        tr, od = simulate(m, "state", f.dec_idx.to_numpy(), des, w, 2, TTL_TREND, PEN_BPS, 0, m.N)
        new = evaluate(Book(m, tr, od, 0, m.N), wb)
        o = old.loc[v]
        out[v] = {"keys": list(CONTROL_MAP.values()),
                  "old": {w_: {nk: float(o[f"{w_}_{ok}"]) for ok, nk in CONTROL_MAP.items()} for w_ in ("DEV", "TEST")},
                  "new": {w_: {k: new[w_][k] for k in CONTROL_MAP.values()} for w_ in WINDOWS},
                  "note": "old: Batch-1 separate DEV/TEST runs, trades incl. open, day-end MDD, exit-month ratio; "
                          "new: continuous run, closed only, 1m MDD, exposure months"}
    return out


def data_gaps(m: Market, met: pd.DataFrame, fe: Features) -> dict:
    out = {}
    T5 = m.t[np.arange(4, m.N, 5)] + MIN
    at = met.available_time.array.asi8
    have = np.isin(T5, at)
    for w, (a, b) in WINDOWS.items():
        s0 = max(a, TS("2020-09-01"))
        mk = (T5 >= s0.value) & (T5 < b.value)
        ia, ib = m.idx(a), m.idx(b)
        fk = (m.ft >= a.value) & (m.ft < b.value)
        gaps = np.diff(m.ft[fk]) / HOUR
        out[w] = {"metrics_5m_missing_from_2020-09-01": int((mk & ~have).sum()), "metrics_5m_rows": int(mk.sum()),
                  "premium_missing_min": int(np.isnan(fe.prem[ia:ib]).sum()), "minutes": ib - ia,
                  "funding_events": int(fk.sum()), "funding_gaps_gt_8h05": int((gaps > 8.1).sum())}
        for col in ("oi", "global_ls", "top_ls", "taker_lsr"):
            v = met[col].to_numpy(float)
            okv = (v > 0) & np.isfinite(v)
            out[w][f"{col}_bad_in_present"] = int(np.isin(T5[mk], at[~okv]).sum())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    ap.add_argument("--registry-from", type=Path, help="write registry rows from an existing run folder")
    args = ap.parse_args(argv)
    if args.registry_from:
        man = json.loads((args.registry_from / "manifest.json").read_text(encoding="utf-8"))
        assert man["code_sha256"] == provenance.file_sha256(Path(__file__)), "code changed since run"
        sel = {f: {k: v for k, v in (("DEV_PICK", d), ("RESELECTED_ADAPTIVE", r.get(f))) if v}
               for (f, d), r in [((f, d), json.loads((args.registry_from / "reselected_adaptive.json").read_text()))
                                 for f, d in json.loads((args.registry_from / "selected_dev.json").read_text()).items()]}
        print(write_registry(pd.read_parquet(args.registry_from / "grid.parquet"), sel, man["input_sha256"],
                             man["run_id"], man["variant_counts"]["families"]))
        return args.registry_from
    t_start = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"NM-B2-{stamp}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = load_all()
    m = Market.from_frames(minutes, funding)
    del minutes
    print(f"[load] N={m.N} metrics={len(met)} premium={len(prem)} funding={len(funding)} {time.time()-t_start:.0f}s",
          flush=True)
    fe = Features(m, met, prem)
    fe.f_prep(); fe.g_prep(); fe.h_prep()
    print(f"[feat] all {time.time()-t_start:.0f}s", flush=True)
    gaps = data_gaps(m, met, fe) | {"F": fe.F["gaps"]}
    rn = Runner(m, fe)
    params = grid()
    rows, fold = [], []
    for n_, p in enumerate(params):
        book = rn.run(p)
        ev = evaluate(book, window_bounds(m, p["family"]))
        row = {"variant_id": vid(p), **{k: v for k, v in p.items()}}
        for w, d in ev.items():
            row.update({f"{w}_{k}": v for k, v in d.items()})
            fold.append({"variant_id": row["variant_id"], "family": p["family"], "offset": p["offset"], "window": w, **d})
        rows.append(row)
        if n_ % 20 == 0:
            print(f"[grid] {n_+1}/{len(params)} {p['family']} {time.time()-t_start:.0f}s", flush=True)
    g = pd.DataFrame(rows)
    for w in WINDOWS:
        g[f"{w}_worst"] = g[[f"{w}_long_net4", f"{w}_short_net4"]].min(axis=1)
    twin_of = {r["variant_id"]: r["variant_id"].replace("offset=2", "offset=5") for r in rows if r["offset"] == 2}
    rec = {r["variant_id"]: r for r in g.to_dict("records")}
    g["DEV_eligible"] = [eligible(r, rec[twin_of[r["variant_id"]]]) if r["offset"] == 2 else np.nan
                         for r in g.to_dict("records")]
    g["DEV_score"] = [dev_score(r) for r in g.to_dict("records")]
    g["ADAPT_score"] = [adaptive_score(r, rec[twin_of[r["variant_id"]]]) if r["offset"] == 2 else np.nan
                        for r in g.to_dict("records")]
    print(f"[grid] done {time.time()-t_start:.0f}s", flush=True)

    sel, fam_counts = {}, {}
    trade_dir, daily_dir = run_dir / "trades", run_dir / "daily"
    boot_rows, fill_rows = [], []
    for fam in FAMILIES:
        gf = g[(g.family == fam) & (g.offset == 2)]
        el = gf[gf.DEV_eligible == True]  # noqa: E712
        fam_counts[fam] = {"variants": int((g.family == fam).sum()), "offset2": int(len(gf)), "dev_eligible": int(len(el))}
        sel[fam] = {}
        picks = {"DEV_PICK": (el if len(el) else gf).sort_values(["DEV_score", "DEV-FULL_mdd_1m", "DEV-FULL_turnover"],
                                                                 ascending=[False, True, True]).iloc[0]}
        if len(el):
            picks["RESELECTED_ADAPTIVE"] = el.sort_values(["ADAPT_score", "DEV_score"], ascending=False).iloc[0]
        for lab, best in picks.items():
            keys = next(q for q in params if q["family"] == fam)
            p = {k: type(v)(best[k]) for k, v in keys.items()}     # parquet mixes NaN -> floats; restore types
            assert vid(p) == best.variant_id
            wb = window_bounds(m, fam)
            sig = rn.signal(p)
            book = rn.run(p, sig=sig)
            twin = rec[twin_of[best.variant_id]]
            r = rec[best.variant_id]
            boots = {}
            for w in ("TEST", "DEV-FULL"):
                dly = book.daily(*wb[w])
                boots[w] = [stationary_boot_p05(dly, bl) for bl in BLOCKS]
                for bl, v in zip(BLOCKS, boots[w]):
                    boot_rows.append({"family": fam, "pick": lab, "variant_id": best.variant_id, "window": w,
                                      "block_days": bl, "p05_mean_day": v, "n_days": len(dly), "n_boot": NBOOT,
                                      "seed": SEED})
            stress = {}
            for off in (2, 5):
                for pen in (0.5, 1.0, 2.0):
                    sb = rn.run(p, pen=pen, offset=off, sig=sig)
                    ev = evaluate(sb, wb)
                    stress[f"o{off}_p{pen}"] = {w: {k: ev[w][k] for k in ("net4", "long_net4", "short_net4",
                                                                       "closed", "fill_notional_rate")} for w in WINDOWS}
                    for w in WINDOWS:
                        fill_rows.append({"family": fam, "pick": lab, "variant_id": best.variant_id, "offset": off,
                                          "pen_bps": pen, "window": w, **ev[w]})
            vd = verdict(r, twin, boots["TEST"][1], bool(best.DEV_eligible))
            sel[fam][lab] = {"variant_id": best.variant_id, "params": p, "dev_eligible": bool(best.DEV_eligible),
                             "n_eligible": int(len(el)), "dev_score": float(best.DEV_score),
                             "adaptive_score": float(best.ADAPT_score), **vd,
                             "boot_TEST": boots["TEST"], "boot_DEV-FULL": boots["DEV-FULL"],
                             "metrics": evaluate(book, wb), "stress": stress,
                             "twin_o5": {w: {k: twin[f"{w}_{k}"] for k in ("net4", "long_net4", "short_net4", "closed")}
                                         for w in WINDOWS}}
            if lab == "RESELECTED_ADAPTIVE":
                sel[fam][lab]["label"] = "RESELECTED_ADAPTIVE (chosen on TEST; not independent OOS)"
            (trade_dir / fam).mkdir(parents=True, exist_ok=True)
            (daily_dir / fam).mkdir(parents=True, exist_ok=True)
            tr = book.tr.copy()
            if len(tr):
                tr["net4_full"], tr["gross_full"], tr["funding_full"] = book.net4_full, book.gross_full, book.fund_full
                for c in ("decision_idx", "entry_idx", "exit_idx", "exit_decision_idx"):
                    ix = tr[c].to_numpy().astype(int)
                    tr[c.replace("idx", "time")] = pd.Series(pd.to_datetime(m.t[np.maximum(ix, 0)], utc=True)).where(ix >= 0)
            tr.to_parquet(trade_dir / fam / f"{lab}.parquet", index=False)
            a0 = window_bounds(m, fam)["DEV-FULL"][0]
            dly = book.daily(a0, m.N)
            pd.DataFrame({"day": pd.date_range(pd.Timestamp(m.t[a0], tz="UTC"), periods=len(dly), freq="D"),
                          "net4_bps": dly, "held": book.held_day[a0 // 1440:]}).to_parquet(
                daily_dir / fam / f"{lab}.parquet", index=False)
        print(f"[select] {fam} {time.time()-t_start:.0f}s", flush=True)

    control = run_control(m)
    print(f"[control] {time.time()-t_start:.0f}s", flush=True)
    hashes = input_hashes()
    g.to_parquet(run_dir / "grid.parquet", index=False)
    pd.DataFrame(fold).to_parquet(run_dir / "fold_metrics.parquet", index=False)
    diag_cols = ["variant_id", "family", "offset"] + [c for c in g.columns if c.endswith(
        ("orders", "order_notional", "fill_notional_rate", "exit_latency_p50", "exit_latency_p95", "open_n", "turnover"))]
    pd.concat([g[diag_cols].assign(kind="grid"), pd.DataFrame(fill_rows).assign(kind="pick_stress")],
              ignore_index=True).to_parquet(run_dir / "fill_diagnostics.parquet", index=False)
    pd.DataFrame(boot_rows).to_parquet(run_dir / "bootstrap.parquet", index=False)
    pd.DataFrame(rn.coef_rows).to_parquet(run_dir / "conformal_coefficients.parquet", index=False)
    dump = lambda o, f: (run_dir / f).write_text(json.dumps(o, indent=2, default=float), encoding="utf-8")  # noqa: E731
    dump({f: d["DEV_PICK"] for f, d in sel.items()}, "selected_dev.json")
    dump({f: d.get("RESELECTED_ADAPTIVE") for f, d in sel.items()}, "reselected_adaptive.json")
    dump(control, "control_rerun.json")
    manifest = {
        "run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec": "scratchpad codex_batch2_spec.md (Codex Batch-1 review + Batch-2 spec, 2026-10-10)",
        "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "oi_ls_score_start": str(OI_START),
        "data_cutoff": str(END),
        "sources": {"dev_market": str(DEV_MARKET), "test_market": str(SNAP / "market_1m.parquet"),
                    "dev_metrics": str(DEV_METRICS), "test_metrics": str(SNAP / "technique_metrics.parquet"),
                    "dev_premium": str(DEV_PREMIUM), "test_premium": str(SNAP / "technique_premium.parquet"),
                    "dev_funding": str(DEV_FUNDING), "test_funding": str(SNAP / "funding_model_input.parquet")},
        "input_sha256": hashes, "code_sha256": code_hash, "git": git_state(), "data_gaps": gaps,
        "frozen_hypotheses": {
            "V": "multi-horizon (1h/4h/1d) vol-scaled momentum with a slow daily short gate nets >4 bps in DEV and TEST",
            "E": "funding-rate surprise vs same-slot history mean-reverts (side -sign(z)) over 30m-8h",
            "F": "strong taker flow + rising OI with weak price response = absorption; fade the flow",
            "G": "4h trend gated by semivariance imbalance (upside/downside variance) improves VT",
            "H": "rolling ridge on 4h microstructure/positioning features with conformal |residual| margin > 4 bps",
            "I": "hour-of-week shrunk mean return persists out of sample",
            "J": "premium-funding wedge before settlement mean-reverts (side -sign(z))",
            "K": "carry-aware VT: vetoing / flattening funding-adverse sides before settlement improves VT"},
        "execution": {"tick": TICK, "entry_offsets_bps": [2, 5], "penetration_bps": PEN_BPS,
                      "penetration_stress_bps": [1.0, 2.0], "ttl_min": {"trend": TTL_TREND, "event": TTL_EVENT},
                      "exit_quote_bps": EXIT_QUOTE_BPS, "requote_min": REQUOTE_MIN, "cost_bps_rt": 4,
                      "report_only_bps_rt": 8, "slippage": 0, "terminal_open": "MTM at last close + reserved exit fee",
                      "funding": "actual events, -side*rate*1e4*weight, PESS minute timing"},
        "variant_counts": {"total": len(g), "offset2": int((g.offset == 2).sum()), "offset5": int((g.offset == 5).sum()),
                           "families": fam_counts},
        "adaptive_lineage": "RESELECTED_ADAPTIVE picks are chosen on TEST among DEV-eligible variants "
                            "(max min(TEST long/day, short/day, offset5 long/day, short/day)); not independent OOS",
        "interpretations": __doc__,
        "bootstrap": {"type": "stationary", "mean_block_days": list(BLOCKS), "main": MAIN_BLOCK, "n": NBOOT,
                      "seed": SEED, "stat": "mean daily 1m-MTM net4 (bps/day)"},
        "runtime_sec": round(time.time() - t_start, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    picked = {d[k]["variant_id"] for d in sel.values() for k in d}
    with (run_dir / "runs.jsonl").open("x", encoding="utf-8") as fh:      # write-once
        for r in g.to_dict("records"):
            fh.write(canonical({"run_id": run_id, "parent_run_id": PARENT, "variant_id": r["variant_id"],
                                "family": r["family"], "selected": r["variant_id"] in picked,
                                **{k: v for k, v in r.items() if k.endswith(("net4", "net8", "_closed"))}}) + "\n")
    write_report(run_dir, run_id, g, sel, control, manifest)
    if not args.no_registry:
        reg = write_registry(g, sel, hashes, run_id, fam_counts)
        print(f"[registry] {reg}", flush=True)
    print(f"[done] {run_id} {time.time()-t_start:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
