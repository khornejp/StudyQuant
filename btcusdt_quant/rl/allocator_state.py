"""RL allocator causal state store (Codex design 2026-10-10 section 2, step 3).

One row per decision time T (1h grid; 4h = the subset at 4h boundaries) and execution cell. Every input is read
through its availability rule, so a store built on inputs truncated or tampered after T equals the full store up to T:
  minute market rows      minute_time + 1m <= T  (the minute-T row itself is excluded; C zero-latency contract)
  sleeve grid / ledger    available_time <= T    (columns restricted to sleeve_precompute.OBS_COLUMNS)
  signal snapshots        available_time <= T    (decision-time source features)
  metrics / premium       available_time <= T
  funding                 funding_time < T (strict)
The 32-step 1h history is a sliding window over the hourly sequence channels (`history`). Normalizers are fit on a
fold's train rows only (`fit_normalizer`). Private outcome tables never enter (sleeve_precompute.read_observation).
"""
from __future__ import annotations
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from . import sleeve_precompute as sp

MIN = sp.MIN
HOUR = 60 * MIN
SEQ_LEN = 32
SEQ_MARKET = ("ret_1h", "range_1h", "logvol_1h", "taker_share_1h")
METRIC_Z_ROWS, METRIC_Z_MIN = 8640, 1440          # 30 d of 5 m rows, previous rows only
PREMIUM_Z_ROWS, PREMIUM_Z_MIN = 43200, 7200       # 30 d of 1 m rows
FUND_N, FUND_MIN = 90, 30
CLOSED_N = 20
_NO_SCALE = ("_sin", "_cos", "_available", "_signal_active", "_pending", "_open", "_exit_pending", "_trail_armed",
             "_base_side", "lbr_armed", "__nan")


def hour_grid(start: pd.Timestamp, end: pd.Timestamp, step_h: int = 1) -> np.ndarray:
    """Decision times T in (start, end] on UTC hour (step_h) boundaries."""
    a = (start.value // (step_h * HOUR) + 1) * step_h * HOUR
    n = (end.value - a) // (step_h * HOUR) + 1            # integer count: float arange drops the endpoint at ~1e18
    return a + step_h * HOUR * np.arange(max(n, 0), dtype=np.int64)


def last_minute(t: np.ndarray, T: np.ndarray) -> np.ndarray:
    """Index of the last minute bar closed by T (minute_time + 1m <= T); -1 if none."""
    return np.searchsorted(t, np.asarray(T, np.int64) - MIN, "right") - 1


def _asof(av: np.ndarray, T: np.ndarray, side: str = "right") -> np.ndarray:
    return np.searchsorted(av, T, side) - 1


def _take(x: np.ndarray, k: np.ndarray, fill=np.nan) -> np.ndarray:
    out = np.full(len(k), fill, dtype=float)
    ok = k >= 0
    out[ok] = np.asarray(x, float)[k[ok]]
    return out


def _cum(x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.nan_to_num(np.asarray(x, float)))])


def _window_sum(cs: np.ndarray, i: np.ndarray, w: int) -> np.ndarray:
    """Sum of x[i-w+1 .. i] from a leading-zero cumulative sum; NaN when i < 0."""
    hi, lo = i + 1, np.maximum(i + 1 - w, 0)
    return np.where(i >= 0, cs[np.maximum(hi, 0)] - cs[lo], np.nan)


def _prior_z(x: np.ndarray, rows: int, min_rows: int) -> np.ndarray:
    """(x_k - mean(prev rows)) / std(prev rows): previous `rows` values only, current excluded."""
    s = pd.Series(np.asarray(x, float)).shift(1).rolling(rows, min_periods=min_rows)
    return ((x - s.mean()) / s.std(ddof=0)).to_numpy(float)


def _robust_prior_z(x: np.ndarray, n: int, min_obs: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for j in range(len(x)):
        s = x[max(0, j - n):j]
        s = s[np.isfinite(s)]
        if len(s) >= min_obs:
            med = np.median(s)
            mad = np.median(np.abs(s - med))
            if mad > 0:
                out[j] = (x[j] - med) / (1.4826 * mad)
    return out


# ---------------------------------------------------------------- common channels
def common_channels(mk: dict, metrics: pd.DataFrame, premium: pd.DataFrame, f_time: np.ndarray, f_rate: np.ndarray,
                    T: np.ndarray) -> pd.DataFrame:
    t, c, h, l = mk["t"], mk["c"], mk["h"], mk["l"]
    v, tb = mk["v"], mk["tb"]
    i = last_minute(t, T)
    lc = np.log(c)
    r = np.r_[0.0, np.diff(lc)]
    cr2 = _cum(r ** 2)
    out = {"T": T}
    for nm, w in (("1h", 60), ("4h", 240), ("24h", 1440), ("7d", 10080)):
        out[f"rv_{nm}"] = np.sqrt(_window_sum(cr2, i, w)) * 1e4
        out[f"ret_{nm}"] = np.where(i - w >= 0, (lc[np.maximum(i, 0)] - lc[np.maximum(i - w, 0)]) * 1e4, np.nan)
    hh = pd.Series(h).rolling(60, min_periods=60).max().to_numpy()
    ll = pd.Series(l).rolling(60, min_periods=60).min().to_numpy()
    out["range_1h"] = _take(np.log(hh / ll) * 1e4, i)
    cv, ctb = _cum(v), _cum(tb)
    vol1h = _window_sum(cv, i, 60)
    out["logvol_1h"] = np.log1p(vol1h)
    out["taker_share_1h"] = np.where(vol1h > 0, _window_sum(ctb, i, 60) / np.where(vol1h > 0, vol1h, 1), np.nan)
    out["ret_1h_seq"] = out["ret_1h"]
    # funding: strictly before T
    j = np.searchsorted(f_time, T, "left") - 1
    fz = _robust_prior_z(np.asarray(f_rate, float), FUND_N, FUND_MIN)
    out["funding_rate_last"] = _take(f_rate, j) * 1e4
    out["funding_z90"] = _take(fz, j)
    out["funding_age_h"] = np.where(j >= 0, (T - np.asarray(f_time)[np.maximum(j, 0)]) / HOUR, np.nan)
    # metrics: available_time <= T
    av = metrics.available_time.to_numpy(np.int64)
    k = _asof(av, T)
    oi = np.where(metrics.oi.to_numpy(float) > 0, metrics.oi.to_numpy(float), np.nan)
    loi = np.log(oi)
    for nm, lag in (("1h", HOUR), ("4h", 4 * HOUR), ("24h", 24 * HOUR)):
        out[f"oi_chg_{nm}"] = (_take(loi, k) - _take(loi, _asof(av, T - lag))) * 1e4
    out["oi_z"] = _take(_prior_z(loi, METRIC_Z_ROWS, METRIC_Z_MIN), k)
    for col in ("global_ls", "top_ls", "taker_lsr"):
        x = metrics[col].to_numpy(float)
        x = np.log(np.where(x > 0, x, np.nan))
        out[f"{col}_log"] = _take(x, k)
        out[f"{col}_z"] = _take(_prior_z(x, METRIC_Z_ROWS, METRIC_Z_MIN), k)
    out["metrics_age_min"] = np.where(k >= 0, (T - av[np.maximum(k, 0)]) / MIN, np.nan)
    pav = premium.available_time.to_numpy(np.int64)
    p = premium.premium.to_numpy(float)
    kp = _asof(pav, T)
    out["premium_last"] = _take(p, kp) * 1e4
    out["premium_z"] = _take(_prior_z(p, PREMIUM_Z_ROWS, PREMIUM_Z_MIN), kp)
    cp = _cum(p)
    out["premium_mean_1h"] = np.where(kp >= 59, _window_sum(cp, kp, 60) / 60 * 1e4, np.nan)
    tt = pd.to_datetime(T, utc=True)
    hod, dow = tt.hour.to_numpy() + tt.minute.to_numpy() / 60, tt.dayofweek.to_numpy()
    out["hour_sin"], out["hour_cos"] = np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24)
    out["dow_sin"], out["dow_cos"] = np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7)
    return pd.DataFrame(out).drop(columns="ret_1h_seq")


# ---------------------------------------------------------------- sleeve channels
def _run_start(key: np.ndarray) -> np.ndarray:
    """Index where the current run of equal `key` values started."""
    chg = np.r_[True, key[1:] != key[:-1]]
    return np.maximum.accumulate(np.where(chg, np.arange(len(key)), 0))


def sleeve_channels(name: str, grid: pd.DataFrame, ledger: pd.DataFrame, c: np.ndarray, T: np.ndarray) -> pd.DataFrame:
    """Per-sleeve state at T from its observation-safe grid and ledger (both already cut at available_time <= T is
    not required: only rows with minute_time + 1m <= T are ever indexed)."""
    sp.obs_columns("grid", grid.columns)
    sp.obs_columns("ledger", ledger.columns)
    t = grid.minute_time.to_numpy(np.int64)
    i = last_minute(t, T)
    ok = i >= 0
    ii = np.maximum(i, 0)
    g = lambda col: grid[col].to_numpy()  # noqa: E731
    side, opp, openm, pend = g("base_side").astype(np.int64), g("entry_opportunity_id"), g("open"), g("pending")
    out = {}
    pre = f"{name}_"
    for col in ("available", "signal_active", "pending", "open", "exit_pending", "trail_armed"):
        out[pre + col] = np.where(ok, g(col)[ii], 0).astype(np.float32)
    out[pre + "base_side"] = np.where(ok, side[ii], 0).astype(np.float32)
    out[pre + "base_weight"] = np.where(ok, g("base_weight")[ii], 0).astype(np.float32)
    s_age = ii - _run_start(side)[ii]
    out[pre + "signal_age_h"] = np.where(ok & (side[ii] != 0), (s_age + 1) / 60, 0.0)
    key_p = np.where(pend, opp, -1)
    out[pre + "pending_age_h"] = np.where(ok & pend[ii], (ii - _run_start(key_p)[ii] + 1) / 60, 0.0)
    key_o = np.where(openm, opp, -1)
    out[pre + "hold_age_h"] = np.where(ok & openm[ii], (ii - _run_start(key_o)[ii] + 1) / 60, 0.0)
    mand = g("base_mandatory_exit_time")[ii]
    out[pre + "to_mandatory_exit_h"] = np.where(ok & (mand > 0), (mand - T) / HOUR, np.nan)
    R0, Rt, lvl = g("R0_bps")[ii].astype(float), g("R_t_bps")[ii].astype(float), g("stop_level")[ii].astype(float)
    open_now = ok & openm[ii]
    out[pre + "R0_bps"] = np.where(open_now, R0, np.nan)
    out[pre + "Rt_over_R0"] = np.where(open_now & (R0 > 0), Rt / np.where(R0 > 0, R0, 1), np.nan)
    sd = side[ii] * np.log(np.asarray(c, float)[ii] / lvl) * 1e4
    out[pre + "stop_dist_bps"] = np.where(open_now & np.isfinite(lvl), sd, np.nan)
    # realized canonical P&L (unit allocation) from the grid: minutes < T
    net = g("net4").astype(float)
    cs = _cum(net)
    for nm, w in (("24h", 1440), ("7d", 10080), ("30d", 43200)):
        out[pre + f"mtm_{nm}"] = _window_sum(cs, i, w)
    out[pre + "net4_1h"] = _window_sum(cs, i, 60)
    edges = t[0] + HOUR * np.arange((t[-1] + MIN - t[0]) // HOUR + 1, dtype=np.int64) if len(t) else np.zeros(0, np.int64)
    hourly = np.diff(cs[np.searchsorted(t, edges)]) if len(t) else np.zeros(0)
    hcs, hcs2 = _cum(hourly), _cum(hourly ** 2)
    hi = (i + 1) // 60 - 1                         # last full hour fully closed by T (grid starts on an hour)
    for nm, w in (("24h", 24), ("7d", 168)):
        n_ = np.minimum(hi + 1, w)
        m1 = _window_sum(hcs, hi, w) / np.maximum(n_, 1)
        m2 = _window_sum(hcs2, hi, w) / np.maximum(n_, 1)
        out[pre + f"vol_{nm}"] = np.where(n_ >= 2, np.sqrt(np.maximum(m2 - m1 ** 2, 0)), np.nan)
    eq = cs[1:]
    peak = np.maximum.accumulate(eq)
    out[pre + "drawdown"] = np.where(ok, (peak - eq)[ii], np.nan)
    out[pre + "mdd_to_date"] = np.where(ok, np.maximum.accumulate(peak - eq)[ii], np.nan)
    # open trade unrealized / MAE / MFE and last-20 closed trades from the ledger (minute_time + 1m <= T)
    lm = ledger.minute_idx.to_numpy(np.int64)
    lo = ledger.entry_opportunity_id.to_numpy(np.int64)
    ln = ledger.net4.to_numpy(float)
    order = np.lexsort((lm, lo))
    lm, lo, ln = lm[order], lo[order], ln[order]
    cum = pd.Series(ln).groupby(lo).cumsum().to_numpy()
    cmax = pd.Series(cum).groupby(lo).cummax().to_numpy()
    cmin = pd.Series(cum).groupby(lo).cummin().to_numpy()
    cur = np.where(open_now, opp[ii], -1)
    unr, mfe, mae = (np.full(len(T), np.nan) for _ in range(3))
    starts = np.searchsorted(lo, cur, "left")
    ends = np.searchsorted(lo, cur, "right")
    for q in np.flatnonzero(cur >= 0):
        a, b = starts[q], ends[q]
        k = a + np.searchsorted(lm[a:b], i[q], "right") - 1
        if k >= a:
            unr[q], mfe[q], mae[q] = cum[k], cmax[k], cmin[k]
    out[pre + "unrealized_net4"], out[pre + "mfe"], out[pre + "mae"] = unr, mfe, mae
    # closed trades: exit fill minute (grid closed_opp_id, known at that minute's close) <= i
    cl = g("closed_opp_id").astype(np.int64)
    em = np.flatnonzero(cl >= 0)
    ids = cl[em]
    tot_by = pd.Series(ln).groupby(lo).sum()
    tot = tot_by.reindex(ids).to_numpy(float)
    k_end = np.searchsorted(em, i, "right")
    win = _cum(tot > 0)
    s_tot = _cum(tot)
    n_c = np.minimum(k_end, CLOSED_N)
    out[pre + "closed20_win"] = np.where(n_c > 0, (win[k_end] - win[k_end - n_c]) / np.maximum(n_c, 1), np.nan)
    out[pre + "closed20_mean"] = np.where(n_c > 0, (s_tot[k_end] - s_tot[k_end - n_c]) / np.maximum(n_c, 1), np.nan)
    out[pre + "closed_n"] = k_end.astype(float)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- signal snapshots
def asof_features(frame: pd.DataFrame, T: np.ndarray, cols, prefix: str) -> pd.DataFrame:
    """Latest snapshot row with available_time <= T; age in hours."""
    av = frame.available_time.to_numpy(np.int64)
    if np.any(np.diff(av) < 0):
        raise ValueError("snapshot available_time not sorted")
    k = _asof(av, T)
    out = {f"{prefix}{c}": _take(frame[c].to_numpy(float), k) for c in cols}
    out[f"{prefix}age_h"] = np.where(k >= 0, (T - av[np.maximum(k, 0)]) / HOUR, np.nan)
    return pd.DataFrame(out)


def ax_table_features(tab: pd.DataFrame, T: np.ndarray, prefix: str) -> pd.DataFrame:
    """AXC0 latest decision group (available_time <= T): first enterable row's component/E0, k, group size."""
    tab = tab.sort_values(["available_time", "feature_snapshot_id"], kind="stable").reset_index(drop=True)
    av = tab.available_time.to_numpy(np.int64)
    ok = tab.allow_entry.to_numpy(bool) & (tab.side.to_numpy() != 0) & np.isfinite(tab.e0_bps.to_numpy(float))
    grp_first = np.r_[True, av[1:] != av[:-1]]
    gid = np.cumsum(grp_first) - 1
    g_av = av[grp_first]
    pick = np.full(len(g_av), -1)
    cand = np.flatnonzero(ok)
    first_ok = pd.Series(cand).groupby(gid[cand]).first()
    pick[first_ok.index.to_numpy()] = first_ok.to_numpy()
    row = np.where(pick >= 0, pick, np.flatnonzero(grp_first))
    k = _asof(g_av, T)
    rr = np.where(k >= 0, row[np.maximum(k, 0)], -1)
    return pd.DataFrame({f"{prefix}component": _take(tab.component.to_numpy(float), rr),
                         f"{prefix}e0_bps": _take(np.where(ok, tab.e0_bps.to_numpy(float), np.nan), rr),
                         f"{prefix}k": _take(tab.k.to_numpy(float), rr),
                         f"{prefix}sig_side": _take(np.where(ok, tab.side.to_numpy(float), 0.0), rr)})


# ---------------------------------------------------------------- history / normalizer
def history(frame: pd.DataFrame, cols, n: int = SEQ_LEN) -> np.ndarray:
    """[rows, n, len(cols)] float32 windows over consecutive 1h rows (oldest first, last = row T); NaN-padded."""
    x = frame[list(cols)].to_numpy(np.float32)
    pad = np.vstack([np.full((n - 1, x.shape[1]), np.nan, np.float32), x])
    return sliding_window_view(pad, n, axis=0).transpose(0, 2, 1)


def is_scaled(col: str) -> bool:
    return col not in ("T", "exec_cell") and not col.endswith(_NO_SCALE) and not any(s in col for s in ("lbr_armed",))


def fit_normalizer(frame: pd.DataFrame, train_start, train_end) -> dict:
    """Median / IQR per scaled column from train rows only (T in [train_start, train_end))."""
    T = frame["T"].to_numpy(np.int64)
    ts = lambda x: (pd.Timestamp(x) if pd.Timestamp(x).tzinfo else pd.Timestamp(x, tz="UTC")).value  # noqa: E731
    m = (T >= ts(train_start)) & (T < ts(train_end))
    if not m.any():
        raise ValueError("empty train window")
    out = {}
    for c in frame.columns:
        if not is_scaled(c):
            continue
        x = frame.loc[m, c].to_numpy(float)
        x = x[np.isfinite(x)]
        if not len(x):
            out[c] = (0.0, 1.0)
            continue
        q1, med, q3 = np.quantile(x, [0.25, 0.5, 0.75])
        out[c] = (float(med), float(q3 - q1) if q3 > q1 else (float(np.std(x)) or 1.0))
    return out


def apply_normalizer(frame: pd.DataFrame, norm: dict) -> pd.DataFrame:
    """Scaled copy plus `<col>__nan` masks; NaN -> 0 after masking; clipped to +-10."""
    out = frame.copy()
    for c, (med, sc) in norm.items():
        x = out[c].to_numpy(float)
        nan = ~np.isfinite(x)
        out[c] = np.clip(np.where(nan, 0.0, (x - med) / sc), -10, 10).astype(np.float32)
        if nan.any():
            out[c + "__nan"] = nan.astype(np.float32)
    return out
