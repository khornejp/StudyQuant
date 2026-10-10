"""Batch-1 new-model screen (2026-10-10): VT-TSMOM, cascade-exhaustion proxy, crowding disagreement.

Spec: scratchpad codex_newmodel.md "Batch-1 spec". DEV [2020-01-01, 2026-01-01), TEST [2026-01-01, 2026-10-08).
Maker-only fills, 4 bps round trip (8 bps report-only), slippage 0, actual funding events (PESS timing).
Causality: decision on the closed bar i (decision time T = open_time[i] + 1m), orders fill from bar i+1;
metrics used only when available_time (= create_time + 5m) <= T; trailing quantiles / robust z exclude the
current observation (strictly past); VT-TSMOM sigma includes the just-closed bar (it is known at T).
Interpretations (spec silent): sigma window 30 days; 'same hour' volume baseline = all 5m vol30 values in the
same UTC hour over the prior 30 days; selection over o=2 variants, stress = o=5 twin; daily equity is MTM.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.funding_source import load_funding_dir  # noqa: E402
from btcusdt_quant.sim import data, provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402

OUT = ROOT / "out/new_model_batch1_20261010"
SNAP = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot"
DEV_MARKET = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
DEV_METRICS = ROOT / "artifacts/metrics"
DEV_FUNDING = ROOT / "artifacts/funding_2020_2026h1"
REGISTRY = ROOT / "out/sim_registry.jsonl"
START, SPLIT, END = (pd.Timestamp(x, tz="UTC") for x in ("2020-01-01", "2026-01-01", "2026-10-08"))
WINDOWS = {"DEV": (START, SPLIT), "TEST": (SPLIT, END)}
MIN = 60_000_000_000
TICK = 0.1
EXIT_QUOTE_BPS, REQUOTE_MIN, TOUCH_BPS = 2.0, 60, 0.5
SEED, NBOOT, BLOCK = 20261010, 10_000, 20
RUN_ID = "NM-B1-20261010"


# ---------------- fill rule ----------------
def limit_price(close: float, side: int, offset_bps: float) -> float:
    """Passive quote: long bids below close (floor to tick), short asks above (ceil to tick)."""
    if side > 0:
        return np.floor(close * (1 - offset_bps / 1e4) / TICK + 1e-9) * TICK
    return np.ceil(close * (1 + offset_bps / 1e4) / TICK - 1e-9) * TICK


def first_fill(o, h, l, start: int, stop: int, limit: float, buy: bool) -> int:
    """First bar in [start, stop) where a resting limit fills: buy needs open>=limit and low<=limit(1-0.5bp);
    sell needs open<=limit and high>=limit(1+0.5bp). Gap-through bars (open beyond limit) never fill. -1 if none."""
    if stop <= start:
        return -1
    if buy:
        ok = (o[start:stop] >= limit) & (l[start:stop] <= limit * (1 - TOUCH_BPS / 1e4))
    else:
        ok = (o[start:stop] <= limit) & (h[start:stop] >= limit * (1 + TOUCH_BPS / 1e4))
    k = np.flatnonzero(ok)
    return int(start + k[0]) if len(k) else -1


def exit_fill(o, h, l, c, dec: int, side: int, hi: int) -> tuple[int, float]:
    """Exit quote at close[dec] 2 bps favourable, re-quoted at the new close every 60m; scan bars < hi."""
    while True:
        lim = limit_price(c[dec], -side, EXIT_QUOTE_BPS)
        j = first_fill(o, h, l, dec + 1, min(dec + 1 + REQUOTE_MIN, hi), lim, buy=side < 0)
        if j >= 0:
            return j, lim
        dec += REQUOTE_MIN
        if dec >= hi - 1:
            return -1, np.nan


# ---------------- engine ----------------
class Market:
    def __init__(self, frame: pd.DataFrame, funding: pd.DataFrame):
        self.t = pd.to_datetime(frame.open_time, utc=True).astype("datetime64[ns, UTC]").array.asi8.copy()
        self.o, self.h, self.l, self.c = (frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.v, self.tb = frame.volume.to_numpy(float), frame.taker_buy_base_volume.to_numpy(float)
        self.ft = pd.to_datetime(funding.time, utc=True).astype("datetime64[ns, UTC]").array.asi8.copy()
        self.fr = funding.rate.to_numpy(float)

    def idx(self, ts: pd.Timestamp) -> int:
        return int(np.searchsorted(self.t, ts.value))

    def funding_bps(self, side: int, w: float, j0: int, j1_end_ns: int, j1_open_ns: int, upto: int | None = None) -> float:
        """PESS: an adverse event counts if within [entry bar open, exit bar end); a favourable one only within
        [entry bar end, exit bar open). upto (ns) caps the window for MTM marks."""
        a, b = self.t[j0], j1_end_ns
        lo, hi = np.searchsorted(self.ft, a), np.searchsorted(self.ft, b)
        if hi <= lo:
            return 0.0
        ft, cf = self.ft[lo:hi], -side * self.fr[lo:hi] * 1e4 * w
        keep = np.where(cf < 0, True, (ft >= self.t[j0] + MIN) & (ft < j1_open_ns))
        if upto is not None:
            keep &= ft < upto
        return float(cf[keep].sum())


def _trade(m: Market, side, w, dec_i, j0, entry, xdec, j1, xpx, hi, offset):
    open_end = j1 < 0
    if open_end:                      # mark at last close, exit fee reserved in the net columns
        j1, xpx = hi - 1, m.c[hi - 1]
    gross = side * (xpx / entry - 1) * 1e4 * w
    fund = m.funding_bps(side, w, j0, m.t[j1] + MIN, m.t[j1] if not open_end else m.t[j1] + MIN)
    return {"side": side, "weight": w, "decision_idx": dec_i, "entry_idx": j0, "entry_px": entry,
            "exit_decision_idx": xdec, "exit_idx": j1, "exit_px": xpx, "open_at_end": open_end,
            "gross_bps": gross, "funding_bps": fund, "net4_bps": gross + fund - 4 * w, "net8_bps": gross + fund - 8 * w,
            "exit_latency_min": (j1 - xdec) if (not open_end and xdec >= 0) else np.nan, "offset_bps": offset}


def run_state(m: Market, dec_idx, desired, weight, offset, ttl, lo, hi) -> tuple[list, dict]:
    """Model A: persistent target side per decision; exit when target != held side; flip = exit fill then entry."""
    trades, orders, misses = [], 0, 0
    pos = None            # (side, w, dec_i, j0, entry)
    busy = lo
    sel = (dec_idx >= lo) & (dec_idx < hi - 1)
    D, S, W = dec_idx[sel], desired[sel], weight[sel]
    for k in range(len(D)):
        i, s, w = int(D[k]), int(S[k]), float(W[k])
        if i < busy:
            continue
        start = i
        if pos is not None and s != pos[0]:
            j1, xpx = exit_fill(m.o, m.h, m.l, m.c, i, pos[0], hi)
            trades.append(_trade(m, pos[0], pos[1], pos[2], pos[3], pos[4], i, j1, xpx, hi, offset))
            pos = None
            if j1 < 0:
                busy = hi
                break
            start, busy = j1, j1 + 1
        if pos is None and s != 0 and start < hi - 1:
            lim = limit_price(m.c[start], s, offset)
            orders += 1
            j0 = first_fill(m.o, m.h, m.l, start + 1, min(start + 1 + ttl, hi), lim, buy=s > 0)
            if j0 < 0:
                misses += 1
                busy = start + ttl + 1
            else:
                pos, busy = (s, w, start, j0, lim), j0 + 1
    if pos is not None:
        trades.append(_trade(m, pos[0], pos[1], pos[2], pos[3], pos[4], -1, -1, np.nan, hi, offset))
    return trades, {"orders": orders, "ttl_miss": misses}


def run_event(m: Market, ev_idx, ev_side, hold, offset, ttl, lo, hi) -> tuple[list, dict]:
    """Models B/C: event -> passive entry (TTL), fixed hold from fill, passive exit; cooldown = hold from event."""
    trades, orders, misses = [], 0, 0
    sel = (ev_idx >= lo) & (ev_idx < hi - 1)
    E, S = ev_idx[sel], ev_side[sel]
    busy = lo
    k = 0
    while k < len(E):
        k += int(np.searchsorted(E[k:], busy))
        if k >= len(E):
            break
        i, s = int(E[k]), int(S[k])
        lim = limit_price(m.c[i], s, offset)
        orders += 1
        j0 = first_fill(m.o, m.h, m.l, i + 1, min(i + 1 + ttl, hi), lim, buy=s > 0)
        cool = i + hold
        if j0 < 0:
            misses += 1
            busy = max(i + ttl + 1, cool)
            continue
        xdec = j0 + hold
        if xdec >= hi - 1:
            trades.append(_trade(m, s, 1.0, i, j0, lim, -1, -1, np.nan, hi, offset))
            break
        j1, xpx = exit_fill(m.o, m.h, m.l, m.c, xdec, s, hi)
        trades.append(_trade(m, s, 1.0, i, j0, lim, xdec, j1, xpx, hi, offset))
        if j1 < 0:
            break
        busy = max(j1 + 1, cool)
    return trades, {"orders": orders, "ttl_miss": misses}


# ---------------- metrics ----------------
def daily_mtm(m: Market, trades: pd.DataFrame, lo: int, hi: int) -> np.ndarray:
    """Daily P&L (bps, 4 bps line) from day-end marks: unrealised gross - entry fee + funding to day end."""
    nd = (hi - lo) // 1440
    pnl = np.zeros(nd)
    for r in trades.itertuples(index=False):
        d0, d1 = (r.entry_idx - lo) // 1440, (r.exit_idx - lo) // 1440
        prev = 0.0
        for d in range(d0, d1):
            end_i = lo + d * 1440 + 1439
            e = (r.side * (m.c[end_i] / r.entry_px - 1) * 1e4 * r.weight - 2 * r.weight
                 + m.funding_bps(r.side, r.weight, r.entry_idx, m.t[r.exit_idx] + MIN, m.t[r.exit_idx],
                                 upto=m.t[end_i] + MIN))
            pnl[d] += e - prev
            prev = e
        pnl[d1] += r.net4_bps - prev
    return pnl


def boot_index(n: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    nb = -(-n // BLOCK)
    starts = rng.integers(0, max(n - BLOCK + 1, 1), size=(NBOOT, nb))
    return (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(NBOOT, -1)[:, :n]


def summarize(m: Market, trades: pd.DataFrame, diag: dict, lo: int, hi: int, bidx: np.ndarray, t0: pd.Timestamp) -> dict:
    nd = (hi - lo) // 1440
    out = {"orders": diag["orders"], "ttl_miss": diag["ttl_miss"], "days": nd}
    n = len(trades)
    out["fill_rate"] = (n / diag["orders"]) if diag["orders"] else np.nan
    if n:
        exp_days = (trades.exit_idx - trades.entry_idx) / 1440.0
    for tag, mask in (("all", slice(None)), ("long", trades.side > 0 if n else slice(0)),
                      ("short", trades.side < 0 if n else slice(0))):
        sub = trades[mask] if n else trades
        out[f"{tag}_trades"] = int(len(sub))
        for col in ("gross_bps", "funding_bps", "net4_bps", "net8_bps"):
            out[f"{tag}_{col}"] = float(sub[col].sum()) if len(sub) else 0.0
        out[f"{tag}_exposure_days"] = float(exp_days[mask].sum()) if n else 0.0
        out[f"{tag}_win"] = float((sub.net4_bps > 0).mean()) if len(sub) else np.nan
        out[f"{tag}_net_per_expday"] = (out[f"{tag}_net4_bps"] / out[f"{tag}_exposure_days"]
                                        if out[f"{tag}_exposure_days"] > 0 else np.nan)
    out["net_per_day"] = out["all_net4_bps"] / nd
    out["turnover"] = float(2 * trades.weight.sum()) if n else 0.0
    out["open_positions"] = int(trades.open_at_end.sum()) if n else 0
    lat = trades.exit_latency_min.dropna() if n else pd.Series(dtype=float)
    out["exit_latency_p50"] = float(lat.quantile(0.5)) if len(lat) else np.nan
    out["exit_latency_p95"] = float(lat.quantile(0.95)) if len(lat) else np.nan
    daily = daily_mtm(m, trades, lo, hi) if n else np.zeros(nd)
    eq = np.cumsum(daily)
    out["mdd_bps"] = float((np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])).max())
    sd = daily.std(ddof=1)
    out["sharpe_daily_ann"] = float(daily.mean() / sd * np.sqrt(365)) if sd > 0 else np.nan
    means = daily[bidx].mean(axis=1)
    out["boot_mean_day_p05"], out["boot_mean_day_p95"] = (float(x) for x in np.quantile(means, [0.05, 0.95]))
    days = pd.date_range(t0, periods=nd, freq="D")
    ser = pd.Series(daily, index=days)
    mon = ser.groupby(ser.index.strftime("%Y-%m")).sum()
    if n:
        active = pd.Series(trades.exit_idx.to_numpy()).map(lambda j: days[(j - lo) // 1440].strftime("%Y-%m")).unique()
        mon_a = mon[mon.index.isin(active)]
    else:
        mon_a = mon.iloc[:0]
    out["positive_month_ratio"] = float((mon_a > 0).mean()) if len(mon_a) else np.nan
    out["monthly_net4"] = {k: float(v) for k, v in mon.items()}
    out["yearly_net4"] = {k: float(v) for k, v in ser.groupby(ser.index.year.astype(str)).sum().items()}
    return out, daily


# ---------------- features ----------------
def trailing_quantile(x: pd.Series, q: float, window: int, min_periods: int) -> pd.Series:
    """Quantile over the previous `window` rows, current row excluded (strictly past)."""
    return x.shift(1).rolling(window, min_periods=min_periods).quantile(q)


def _nanmedian_sorted(blk: np.ndarray, cnt: np.ndarray) -> np.ndarray:
    srt = np.sort(blk, axis=1)              # NaN sorts last
    a, b = (cnt - 1) // 2, cnt // 2
    r = np.arange(len(blk))
    return 0.5 * (srt[r, a] + srt[r, b])


def trailing_robust_z(x: np.ndarray, window: int, min_obs: int, chunk: int = 2_000) -> np.ndarray:
    """(x_t - median(past)) / (1.4826 MAD(past)); past = previous `window` rows, current excluded."""
    n = len(x)
    z = np.full(n, np.nan)
    pad = np.concatenate([np.full(window, np.nan), x])
    view = np.lib.stride_tricks.sliding_window_view(pad, window)[:n]   # row t = x[t-window .. t-1]
    for a in range(0, n, chunk):
        blk = view[a:a + chunk]
        cnt = np.sum(~np.isnan(blk), axis=1)
        clean = cnt == window
        med = np.full(len(blk), np.nan)
        mad = np.full(len(blk), np.nan)
        if clean.any():
            med[clean] = np.median(blk[clean], axis=1)
            mad[clean] = np.median(np.abs(blk[clean] - med[clean, None]), axis=1)
        dirty = (~clean) & (cnt >= min_obs)
        if dirty.any():
            bd, cd = blk[dirty], cnt[dirty]
            med[dirty] = _nanmedian_sorted(bd, cd)
            mad[dirty] = _nanmedian_sorted(np.abs(bd - med[dirty, None]), cd)
        ok = cnt >= min_obs
        with np.errstate(invalid="ignore", divide="ignore"):
            z[a:a + chunk] = np.where(ok & (mad > 0), (x[a:a + chunk] - med) / (1.4826 * mad), np.nan)
    return z


def tsmom_features(m: Market, res_min: int, lookbacks: tuple[int, ...], sigma_bars: int) -> pd.DataFrame:
    """Closed resolution bars: decision index = last 1m bar of each res bar. sigma = std of the last sigma_bars
    bar log returns (current closed bar included, known at T)."""
    dec = np.arange(res_min - 1, len(m.c), res_min)
    c = m.c[dec]
    lr = np.diff(np.log(c), prepend=np.nan)
    sig = pd.Series(lr).rolling(sigma_bars, min_periods=sigma_bars).std().to_numpy()
    ms = []
    for L in lookbacks:
        ret = np.full(len(c), np.nan)
        ret[L:] = np.log(c[L:] / c[:-L])
        ms.append(np.clip(ret / (sig * np.sqrt(L)), -3, 3))
    score = np.mean(ms, axis=0)       # NaN until every horizon is available
    bars_per_year = 365 * 1440 / res_min
    return pd.DataFrame({"dec_idx": dec, "score": score, "sigma_ann": sig * np.sqrt(bars_per_year)})


def metrics_on_grid(m: Market, met: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """5m decision grid (last 1m bar of each 5m bar); metric row with available_time == T exactly (no stale fill)."""
    dec = np.arange(4, len(m.c), 5)
    T = m.t[dec] + MIN
    at = met.available_time.array.asi8
    pos = np.searchsorted(at, T)
    pos_c = np.minimum(pos, len(at) - 1)
    hit = at[pos_c] == T
    g = pd.DataFrame(index=np.arange(len(dec)))
    for col in ("global_ls", "top_ls", "oi", "taker_lsr"):
        v = met[col].to_numpy(float)[pos_c]
        g[col] = np.where(hit & (v > 0), v, np.nan)     # archive has OI==0 / ratio==0 rows: treat as missing
    used = at[pos_c][hit]
    assert np.all(used <= T[hit]), "metric available after decision"
    return dec, g


def cascade_features(m: Market, dec: np.ndarray, grid: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v, tb = m.c, m.h, m.l, m.v, m.tb
    i = dec
    valid = i >= 30
    ip = np.where(valid, i - 30, 0)
    r30 = np.where(valid, np.log(c[i] / c[ip]), np.nan)
    hmax = pd.Series(h).rolling(30).max().to_numpy()[i]
    lmin = pd.Series(l).rolling(30).min().to_numpy()[i]
    range30 = (hmax - lmin) / np.where(valid, c[ip], np.nan)
    vs = pd.Series(v).rolling(30).sum().to_numpy()[i]
    imb = pd.Series(2 * tb - v).rolling(30).sum().to_numpy()[i] / vs
    oi = grid.oi.to_numpy()
    doi30 = np.full(len(i), np.nan)
    doi30[6:] = np.log(oi[6:] / oi[:-6])
    # same-hour baseline: all 5m vol sums in the same UTC hour on the previous 30 days (current day excluded)
    assert len(i) % 288 == 0
    cube = vs.reshape(-1, 24, 12)
    nd = cube.shape[0]
    base = np.full((nd, 24), np.nan)
    for d in range(30, nd):
        base[d] = np.nanmedian(cube[d - 30:d].transpose(1, 0, 2).reshape(24, -1), axis=1)
    vol30 = vs / np.repeat(base.reshape(-1), 12)
    return pd.DataFrame({"r30": r30, "doi30": doi30, "range30": range30, "vol30": vol30, "imb30": imb})


def crowd_features(grid: pd.DataFrame) -> pd.DataFrame:
    W, MINOBS = 30 * 288, 7 * 288
    oi = grid.oi.to_numpy()
    doi60 = np.full(len(oi), np.nan)
    doi60[12:] = np.log(oi[12:] / oi[:-12])
    return pd.DataFrame({"z_taker": trailing_robust_z(grid.taker_lsr.to_numpy(), W, MINOBS),
                         "z_global": trailing_robust_z(grid.global_ls.to_numpy(), W, MINOBS),
                         "z_top": trailing_robust_z(grid.top_ls.to_numpy(), W, MINOBS), "doi60": doi60})


# ---------------- grids ----------------
def grid_a():
    sets = {"1d_3": (1440, (30, 90, 180)), "1d_4": (1440, (30, 90, 180, 360)),
            "4h_3": (240, (42, 168, 504)), "4h_4": (240, (42, 168, 504, 1008))}
    return [dict(model="vt_tsmom", lookback_set=k, res_min=r, lookbacks=L, deadband=db, target_vol=tv, offset=o)
            for k, (r, L) in sets.items() for db in (0.25, 0.50) for tv in (0.20, 0.40, 0.60) for o in (2, 5)]


def grid_b():
    return [dict(model="cascade_proxy", q_ret=a, q_oi=b, q_range=c, vol_mult=d, hold=e, offset=o)
            for a in (0.975, 0.99) for b in (0.05, 0.10) for c in (0.95, 0.975) for d in (2, 3)
            for e in (60, 240, 720) for o in (2, 5)]


def grid_c():
    return [dict(model="crowd_disagreement", gap=a, top_min=b, oi_filter=c, hold=e, offset=o)
            for a in (1.5, 2.0, 2.5) for b in (0.0, 0.5, 1.0) for c in ("none", "doi60>=0")
            for e in (15, 60, 240) for o in (2, 5)]


def vid(p: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in p.items() if k not in ("res_min", "lookbacks"))


# ---------------- main ----------------
def load_all():
    dev = data.load_minutes(DEV_MARKET, end=SPLIT)
    test = pd.read_parquet(SNAP / "market_1m.parquet", columns=data.MINUTE_COLUMNS)
    test["open_time"] = pd.to_datetime(test.open_time, utc=True).astype("datetime64[ns, UTC]")
    minutes = data.validate_minutes(pd.concat([dev, test], ignore_index=True))
    assert minutes.open_time.iloc[0] == START and minutes.open_time.iloc[-1] == END - pd.Timedelta(minutes=1)
    met = pd.concat([data.load_metrics(DEV_METRICS, end=SPLIT),
                     pd.read_parquet(SNAP / "technique_metrics.parquet")], ignore_index=True)
    met["available_time"] = pd.to_datetime(met.available_time, utc=True).astype("datetime64[ns, UTC]")
    met = met.loc[met.available_time <= END].drop_duplicates("available_time", keep="last").sort_values(
        "available_time").reset_index(drop=True)
    fr = load_funding_dir(DEV_FUNDING)
    f_dev = pd.DataFrame({"time": [r.funding_time for r in fr], "rate": [r.funding_rate for r in fr]})
    f_dev["time"] = pd.to_datetime(f_dev.time, utc=True)
    f_dev = f_dev.loc[f_dev.time < SPLIT]
    fmi = pd.read_parquet(SNAP / "funding_model_input.parquet")
    f_test = pd.DataFrame({"time": pd.to_datetime(fmi.publish_time, utc=True), "rate": fmi.rate.to_numpy(float)})
    funding = pd.concat([f_dev, f_test], ignore_index=True).sort_values("time").reset_index(drop=True)
    funding["time"] = funding.time.astype("datetime64[ns, UTC]")
    return minutes, met, funding


def input_hashes() -> dict:
    h = {"dev_market": provenance.file_sha256(DEV_MARKET),
         "dev_metrics_tree": provenance.tree_sha256(DEV_METRICS, "*.zip")["sha256"],
         "dev_funding_tree": provenance.tree_sha256(DEV_FUNDING, "*.zip")["sha256"],
         "code": provenance.file_sha256(Path(__file__))}
    for f in ("market_1m.parquet", "technique_metrics.parquet", "funding_model_input.parquet", "manifest.json"):
        h["snap_" + f] = provenance.file_sha256(SNAP / f)
    return h


def git_state() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"head": g("rev-parse", "HEAD"), "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_files": len(g("status", "--porcelain").splitlines())}


def eligible(r: dict) -> bool:
    return (r["DEV_all_net4_bps"] > 0 and r["DEV_long_net4_bps"] > 0 and r["DEV_short_net4_bps"] > 0
            and all(r[f"DEV_{s}_trades"] >= 20 or r[f"DEV_{s}_exposure_days"] >= 365 for s in ("long", "short"))
            and r["DEV_fill_rate"] >= 0.10)


REPORT_KEYS = ("all_net4_bps", "all_net8_bps", "all_gross_bps", "all_funding_bps", "all_trades", "long_net4_bps",
               "long_trades", "short_net4_bps", "short_trades", "all_win", "mdd_bps", "sharpe_daily_ann", "fill_rate",
               "positive_month_ratio", "boot_mean_day_p05", "open_positions")


def write_report(grid, selected, mets, manifest) -> None:
    lines = [f"# {RUN_ID} new-model batch-1", "", f"cutoff {manifest['data_cutoff']}; costs 4 bps rt (8 report-only)", ""]
    for model, sel in selected.items():
        lines += [f"## {model}: {sel['variant_id']}", f"verdict {sel['verdict']}; eligible {sel['dev_eligible']} "
                  f"(n_eligible {sel['n_eligible']}); kill {sel['kill_sides']}; insufficient {sel['insufficient_sides']}; "
                  f"o5 stress net4 {sel['stress_o5_net4']}", "", "| metric | DEV | TEST |", "|---|---|---|"]
        lines += [f"| {k} | {mets[model]['DEV'][k]:.4g} | {mets[model]['TEST'][k]:.4g} |" for k in REPORT_KEYS]
        lines.append("")
    cols = ["variant_id", "DEV_all_net4_bps", "DEV_worst_side_net4", "TEST_all_net4_bps", "TEST_worst_side_net4",
            "TEST_all_trades"]
    for model in selected:
        g = grid[grid.model == model]
        for key in ("TEST_worst_side_net4", "DEV_score"):
            lines += [f"### {model} top5 by {key}", "", g.sort_values(key, ascending=False).head(5)[cols].to_markdown(
                index=False, floatfmt=".1f"), ""]
    (OUT / "report.md").write_text(chr(10).join(lines), encoding="utf-8")


def write_registry(grid: pd.DataFrame, hashes: dict, windows: dict) -> None:
    for r in grid.to_dict("records"):
        cfg = {"model": r["model"], "variant_id": r["variant_id"], "run_id": RUN_ID, "windows": windows,
               "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only"}
        registry.record(REGISTRY, {
            "experiment": f"NM-B1 new-model batch-1 {r['model']} {r['variant_id']}", "config": cfg,
            "input_hashes": hashes, "n_trials": 1,
            "result_summary": {f"{w}_{k}": r[f"{w}_{k}"] for w in WINDOWS for k in
                               ("all_net4_bps", "all_net8_bps", "long_net4_bps", "short_net4_bps", "all_trades",
                                "fill_rate")}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    ap.add_argument("--registry-only", action="store_true", help="append registry rows from an existing run")
    args = ap.parse_args()
    if args.registry_only:
        man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        assert man["input_sha256"]["code"] == provenance.file_sha256(Path(__file__)), "code changed since run"
        write_registry(pd.read_parquet(OUT / "grid.parquet"), man["input_sha256"], man["windows"])
        return
    t_start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    minutes, met, funding = load_all()
    m = Market(minutes, funding)
    print(f"[load] minutes={len(minutes)} metrics={len(met)} funding={len(funding)} {time.time()-t_start:.0f}s", flush=True)
    win = {k: (m.idx(a), m.idx(b)) for k, (a, b) in WINDOWS.items()}
    bidx = {k: boot_index((hi - lo) // 1440) for k, (lo, hi) in win.items()}

    # gaps report
    dec5, g5 = metrics_on_grid(m, met)
    gaps = {}
    for k, (lo, hi) in win.items():
        s = (dec5 >= lo) & (dec5 < hi) & (m.t[dec5] + MIN >= pd.Timestamp("2020-09-01", tz="UTC").value)
        gaps[k] = {c: int(g5.loc[s, c].isna().sum()) for c in g5.columns} | {"grid_rows": int(s.sum())}
    print("[gaps]", gaps, flush=True)

    # features
    feats_a = {(r, L): tsmom_features(m, r, L, 30 * 1440 // r) for r, L in
               {(p["res_min"], p["lookbacks"]) for p in grid_a()}}
    fb = cascade_features(m, dec5, g5)
    W, MP = 180 * 288, 90 * 288
    qcache = {}
    absr = fb.r30.abs()
    for q in (0.975, 0.99):
        qcache[("ret", q)] = trailing_quantile(absr, q, W, MP).to_numpy()
    for q in (0.05, 0.10):
        qcache[("oi", q)] = trailing_quantile(fb.doi30, q, W, MP).to_numpy()
    for q in (0.95, 0.975):
        qcache[("range", q)] = trailing_quantile(fb.range30, q, W, MP).to_numpy()
    print(f"[features] A,B {time.time()-t_start:.0f}s", flush=True)
    fc = crowd_features(g5)
    print(f"[features] C {time.time()-t_start:.0f}s", flush=True)

    rows, store = [], {}
    for p in grid_a() + grid_b() + grid_c():
        model = p["model"]
        if model == "vt_tsmom":
            f = feats_a[(p["res_min"], p["lookbacks"])]
            sc = f.score.to_numpy()
            des = np.where(np.isnan(sc), 0, np.where(np.abs(sc) >= p["deadband"], np.sign(sc), 0)).astype(int)
            w = np.minimum(1.0, p["target_vol"] / f.sigma_ann.to_numpy())
            w = np.where(np.isfinite(w), w, 0.0)
            assert np.all(m.t[f.dec_idx.to_numpy()] % (p["res_min"] * MIN) == (p["res_min"] - 1) * MIN)
            runner = lambda lo, hi: run_state(m, f.dec_idx.to_numpy(), des, w, p["offset"], 60, lo, hi)
        elif model == "cascade_proxy":
            r30 = fb.r30.to_numpy()
            with np.errstate(invalid="ignore"):
                ev = ((np.abs(r30) >= qcache[("ret", p["q_ret"])]) & (fb.doi30.to_numpy() <= qcache[("oi", p["q_oi"])])
                      & (fb.range30.to_numpy() >= qcache[("range", p["q_range"])])
                      & (fb.vol30.to_numpy() >= p["vol_mult"]) & (np.sign(fb.imb30.to_numpy()) == np.sign(r30))
                      & (r30 != 0))
            idx, side = dec5[ev], -np.sign(r30[ev]).astype(int)
            runner = lambda lo, hi, idx=idx, side=side: run_event(m, idx, side, p["hold"], p["offset"], 15, lo, hi)
        else:
            zt, zg, zp, d60 = (fc[k].to_numpy() for k in ("z_taker", "z_global", "z_top", "doi60"))
            with np.errstate(invalid="ignore"):
                ev = ((np.sign(zt) == -np.sign(zg)) & (zt != 0) & (np.abs(zt - zg) >= p["gap"])
                      & (np.sign(zp - zg) == np.sign(zt)) & (np.abs(zp) >= p["top_min"]))
                if p["oi_filter"] != "none":
                    ev &= d60 >= 0
            idx, side = dec5[ev], np.sign(zt[ev]).astype(int)
            runner = lambda lo, hi, idx=idx, side=side: run_event(m, idx, side, p["hold"], p["offset"], 15, lo, hi)
        row = {"variant_id": vid(p), **{k: (str(v) if isinstance(v, tuple) else v) for k, v in p.items()}}
        for k, (lo, hi) in win.items():
            tr, dg = runner(lo, hi)
            tr = pd.DataFrame(tr)
            if len(tr):
                assert (tr.entry_idx > tr.decision_idx).all(), "same-bar fill"
                assert ((tr.exit_idx > tr.exit_decision_idx) | tr.open_at_end).all()
                assert (tr.exit_idx < hi).all() and (tr.decision_idx >= lo).all()
            s, daily = summarize(m, tr, dg, lo, hi, bidx[k], WINDOWS[k][0])
            store[(row["variant_id"], k)] = (tr, daily, s)
            row.update({f"{k}_{a}": b for a, b in s.items() if not isinstance(b, dict)})
        rows.append(row)
    print(f"[grid] {len(rows)} variants {time.time()-t_start:.0f}s", flush=True)
    grid = pd.DataFrame(rows)
    for k in WINDOWS:
        grid[f"{k}_worst_side_net4"] = grid[[f"{k}_long_net4_bps", f"{k}_short_net4_bps"]].min(axis=1)
    grid["DEV_eligible"] = [eligible(r) for r in grid.to_dict("records")]
    grid["DEV_score"] = grid[["DEV_long_net_per_expday", "DEV_short_net_per_expday"]].min(axis=1)

    selected, mets = {}, {}
    for model in ("vt_tsmom", "cascade_proxy", "crowd_disagreement"):
        g = grid[(grid.model == model) & (grid.offset == 2)]
        el = g[g.DEV_eligible]
        pick_from = el if len(el) else g
        best = pick_from.sort_values(["DEV_score", "DEV_mdd_bps", "DEV_turnover"],
                                     ascending=[False, True, True], na_position="last").iloc[0]
        twin = grid[(grid.variant_id == best.variant_id.replace("offset=2", "offset=5"))].iloc[0]
        r = best.to_dict()
        kill = [f"{w}-{s}" for w in WINDOWS for s in ("long", "short") if r[f"{w}_{s}_net4_bps"] <= 0]
        insuff = [s for s in ("long", "short") if r[f"TEST_{s}_trades"] < 10 and r[f"TEST_{s}_exposure_days"] < 30]
        stress = {w: float(twin[f"{w}_all_net4_bps"]) for w in WINDOWS}
        verdict = ("KILL" if kill else "INSUFFICIENT" if insuff else
                   "STRESS_KILL" if any(v <= 0 for v in stress.values()) else
                   "PASS" if r["TEST_boot_mean_day_p05"] > 0 else "FAIL_BOOT")
        selected[model] = {"variant_id": best.variant_id, "dev_eligible": bool(best.DEV_eligible),
                           "n_eligible": int(len(el)), "kill_sides": kill, "insufficient_sides": insuff,
                           "stress_o5_net4": stress, "verdict": verdict}
        mets[model] = {w: store[(best.variant_id, w)][2] for w in WINDOWS}
        for w in WINDOWS:
            tr, daily, _ = store[(best.variant_id, w)]
            (OUT / "trades" / model).mkdir(parents=True, exist_ok=True)
            (OUT / "daily" / model).mkdir(parents=True, exist_ok=True)
            tr = tr.copy()
            if len(tr):
                for c in ("decision_idx", "entry_idx", "exit_idx"):
                    tr[c.replace("idx", "time")] = pd.to_datetime(m.t[tr[c].to_numpy()], utc=True)
            tr.to_parquet(OUT / "trades" / model / f"{w}.parquet", index=False)
            lo, _ = win[w]
            pd.DataFrame({"day": pd.date_range(WINDOWS[w][0], periods=len(daily), freq="D"), "net4_bps": daily}
                         ).to_parquet(OUT / "daily" / model / f"{w}.parquet", index=False)

    grid.to_parquet(OUT / "grid.parquet", index=False)
    diag_cols = ["variant_id", "model"] + [c for c in grid.columns if any(
        c.endswith(x) for x in ("orders", "ttl_miss", "fill_rate", "exit_latency_p50", "exit_latency_p95",
                                "open_positions"))]
    grid[diag_cols].to_parquet(OUT / "fill_diagnostics.parquet", index=False)
    (OUT / "selected.json").write_text(json.dumps(selected, indent=2, default=str), encoding="utf-8")
    (OUT / "metrics.json").write_text(json.dumps(mets, indent=2, default=float), encoding="utf-8")
    hashes = input_hashes()
    manifest = {"run_id": RUN_ID, "parent_run_id": None, "created_utc": datetime.now(timezone.utc).isoformat(),
                "spec": "codex_newmodel.md Batch-1 spec (Codex session 01a1245a-507e-7cb0-bfaf-0a63c6e2a481)",
                "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "data_cutoff": str(END),
                "sources": {"dev_market": str(DEV_MARKET), "test_market": str(SNAP / "market_1m.parquet"),
                            "dev_metrics": str(DEV_METRICS), "test_metrics": str(SNAP / "technique_metrics.parquet"),
                            "dev_funding": str(DEV_FUNDING), "test_funding": str(SNAP / "funding_model_input.parquet")},
                "input_sha256": hashes, "git": git_state(), "metric_gaps_on_5m_grid": gaps,
                "frozen_hypotheses": {
                    "vt_tsmom": "risk-normalized multi-horizon momentum exceeds 4 bps and persists in 2026",
                    "cascade_proxy": "OI drop + extreme return/range/volume + taker agreement = forced-position proxy; "
                                     "short-term reversal after the shock",
                    "crowd_disagreement": "taker flow opposite to global account crowd (top confirms) wins 15m-4h"},
                "execution": {"tick": TICK, "entry_offsets_bps": [2, 5], "touch_bps": TOUCH_BPS, "ttl_min":
                              {"vt_tsmom": 60, "event": 15}, "exit_quote_bps": EXIT_QUOTE_BPS,
                              "requote_min": REQUOTE_MIN, "cost_bps_rt": 4, "report_only_bps_rt": 8, "slippage": 0,
                              "funding": "actual events, -side*rate*1e4*weight, PESS minute timing"},
                "interpretations": __doc__,
                "bootstrap": {"block_days": BLOCK, "n": NBOOT, "seed": SEED, "stat": "mean daily MTM net4"},
                "grid_sizes": {"vt_tsmom": len(grid_a()), "cascade_proxy": len(grid_b()),
                               "crowd_disagreement": len(grid_c())},
                "runtime_sec": round(time.time() - t_start, 1)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    with (OUT / "runs.jsonl").open("a", encoding="utf-8") as fh:
        for r in grid.to_dict("records"):
            fh.write(canonical({"run_id": RUN_ID, "parent_run_id": None, "variant_id": r["variant_id"],
                                "selected": r["variant_id"] in {v["variant_id"] for v in selected.values()},
                                **{k: v for k, v in r.items() if k.endswith(("net4_bps", "net8_bps", "_trades"))}}) + "\n")
    write_report(grid, selected, mets, manifest)
    if not args.no_registry:
        write_registry(grid, hashes, manifest["windows"])
    print(f"[done] {time.time()-t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
