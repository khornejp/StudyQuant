"""R2-54 Stage B (freeze out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json, amendments A1-A3): fixed-horizon gross
signed-return labels, causal V5/V6 feature views, Ridge/CatBoost, the deterministic position rule through the R2-52A
core ledger (scripts/sim_adaptive_exit.py), per-side ranking, gates, block bootstrap and Holm.
Pure functions only; orchestration, artifacts and the one-shot test unlock live in out/run_r2_54_stageb.py."""
from __future__ import annotations
import contextlib, functools, hashlib, importlib.util, io, json, math, pickle, sys
from dataclasses import dataclass, replace
from pathlib import Path
import numpy as np, pandas as pd

from .rl import state
from .sim import costs, indicators, regime, schema
from .sim.reference import SimConfig
from .sim.strategies import AX_DEFAULTS, CATALOG, Context, build_variant, make_table
from .sim.strategies import grid as grid_strategy

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json"
MINUTE = pd.Timedelta(minutes=1)
HORIZONS = {"30m": 30, "1h": 60, "4h": 240, "12h": 720, "24h": 1440}
VIEWS = ("V5_continuous", "V6_full")
MODELS = ("ridge_1", "ridge_10", "ridge_100", "catboost")
RIDGE_LAMBDA = {"ridge_1": 1.0, "ridge_10": 10.0, "ridge_100": 100.0}
K_VALUES = (1.0, 1.5, 2.0)
SIDES = {"long": 1, "short": -1}
ENTRY_BPS = 4.0                                   # nominal round-trip fee: enter when side*yhat - 4 > 0
FEE_NOMINAL, FEE_STRESS = 2.0, 4.0                # per side: 4 / 8 bps round trip
EMBARGO = pd.Timedelta(hours=24)
DEV_START = pd.Timestamp("2022-03-01", tz="UTC")
TEST_START, TEST_END = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
TIE = 1e-12
MIN_POSITIONS = 100
CATBOOST_PARAMS = {"loss_function": "RMSE", "depth": 4, "iterations": 500, "learning_rate": 0.03, "l2_leaf_reg": 10,
                   "random_seed": 42}
CATBOOST_THREADS = 8                              # fixed so the CPU fit is reproducible
CONFIG = SimConfig(exit_policy="R2_52A")          # strict, NATIVE rows, PESS funding, delay 1, fee 2 bps/side
E_MAX_AGE = regime.E_MAX_AGE                      # 24 h
METRIC_TTL, PREMIUM_TTL, FUNDING_TTL = pd.Timedelta(hours=1), pd.Timedelta(minutes=15), pd.Timedelta(hours=24)
AGE_CAP_MIN = 10080.0
SEQ15, SEQ1M = 32, 15
# selection.robustness_removals, by technique id number (B1-B3 count with the legacy group)
REMOVAL_GROUPS = {
    "legacy_grid": ("B1", "B2", "B3", "K01", "K02", "K03", "K04", "K05", "K10"),
    "volatility": ("K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0", "K08", "K09"),
    "trend": ("K11_15m", "K11_1h", "K12_30m", "K12_1h", "K13", "K14"),
    "reversion": ("K15", "K16", "K17_N5", "K17_N7"),
    "futures": ("K18", "K19", "K20_A", "K20_B", "K21_A", "K21_B", "K22", "K23", "K24"),
    "levels": ("K25", "K26", "K27", "K28", "K29", "K30")}


# ---------------------------------------------------------------- freeze
@functools.cache
def freeze() -> dict:
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def parse_interval(text: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    a, b = text.strip("[)").split(",")
    return pd.Timestamp(a.strip()), pd.Timestamp(b.strip())


@functools.cache
def folds() -> tuple[tuple[pd.Timestamp, pd.Timestamp], ...]:
    out = tuple(parse_interval(x) for x in freeze()["time_structure"]["validation_folds"])
    if len(out) != 10:
        raise ValueError("freeze must list ten validation folds")
    return out


def boundaries() -> tuple[pd.Timestamp, ...]:
    """Every validation-fold start/end and the final-test start (labels.embargo)."""
    return tuple(sorted({t for f in folds() for t in f} | {TEST_START}))


def n_trials() -> dict:
    a2 = next(a for a in freeze()["amendments"] if a["id"] == "A2")["new"]       # supersedes the body 5413/5540
    t = freeze()["trials"]
    selectable = len(VIEWS) * len(HORIZONS) * len(MODELS) * len(K_VALUES)
    robustness = len(freeze()["selection"]["robustness_removals"])
    if selectable + robustness != t["new_trials"] or a2["registry_after"] - a2["registry_base"] != t["new_trials"]:
        raise ValueError("trial count does not match the freeze")
    return {"selectable": selectable, "robustness": robustness, "new_trials": t["new_trials"],
            "registry_base": a2["registry_base"], "registry_after": a2["registry_after"]}


def check_freeze() -> None:
    """Module constants against the frozen values (fails closed on any drift)."""
    f = freeze()
    ok = (list(HORIZONS) == f["labels"]["horizons"] and list(VIEWS) == f["inputs"]["selectable_views"]
          and list(K_VALUES) == f["position_rule"]["k_policy"]["candidates"]
          and parse_interval(f["time_structure"]["final_test_nominal"]) == (TEST_START, TEST_END)
          and parse_interval(f["time_structure"]["development"])[0] == DEV_START
          and f["status"]["design"] == "FROZEN" and f["bootstrap"]["block_rows"] == 672
          and f["bootstrap"]["replicates"] == 10000 and f["bootstrap"]["seed"] == 20261008)
    n_trials()
    if not ok:
        raise ValueError("stageb constants differ from the freeze")


# ---------------------------------------------------------------- small helpers
def ns(times) -> np.ndarray:
    return pd.DatetimeIndex(times).as_unit("ns").asi8


def _take(values, k: np.ndarray, default=np.nan) -> np.ndarray:
    values = np.asarray(values)
    out = np.full(len(k), default, dtype=values.dtype if values.dtype.kind in "iu" else float)
    ok = k >= 0
    out[ok] = values[k[ok]]
    return out


def _pos(src_ns: np.ndarray, t_ns: np.ndarray) -> np.ndarray:
    """Latest index with src <= t (src sorted), -1 when none."""
    return np.searchsorted(src_ns, t_ns, side="right") - 1


def _age(age_ns: np.ndarray, ok: np.ndarray) -> np.ndarray:
    minutes = np.where(ok, age_ns / 60e9, AGE_CAP_MIN)
    return np.log1p(np.clip(minutes, 0, AGE_CAP_MIN))


def _ok(x) -> np.ndarray:
    x = np.asarray(x, float)
    return np.isfinite(x) & (x > 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- labels, purge, embargo, N_eff
def make_labels(minutes: pd.DataFrame, times) -> pd.DataFrame:
    """g_H(T) = 1e4 * log(open(T+1m+H) / open(T+1m)). A minute missing inside the data invalidates the run; an exit
    beyond the last minute is unavailable (NaN), never filled."""
    t, o = ns(minutes.open_time), minutes.open.to_numpy(float)
    if len(t) > 1 and not np.all(np.diff(t) == 60_000_000_000):
        raise ValueError("missing 1-minute price inside the market data")
    d = ns(times)
    out = {"decision_time": pd.DatetimeIndex(times)}

    def price(when: np.ndarray) -> np.ndarray:
        k = np.searchsorted(t, when)
        hit = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == when)
        inside = (when >= t[0]) & (when <= t[-1])
        if (inside & ~hit).any():
            raise ValueError("missing 1-minute price inside the market data")
        return np.where(hit, o[np.minimum(k, len(t) - 1)], np.nan)

    entry = d + MINUTE.value
    p0 = price(entry)
    for h, m in HORIZONS.items():
        exit_ = entry + m * MINUTE.value
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"g_{h}"] = 1e4 * np.log(price(exit_) / p0)
        out[f"exit_{h}"] = pd.DatetimeIndex(exit_, tz="UTC")
    return pd.DataFrame(out)


def embargoed(times) -> np.ndarray:
    d = ns(times)
    out = np.zeros(len(d), bool)
    for b in boundaries():
        out |= (d >= b.value) & (d < (b + EMBARGO).value)
    return out


def train_mask(times, h_min: int, cutoff: pd.Timestamp) -> np.ndarray:
    """labels.purge + embargo: T >= development start, T+1m+H < cutoff, not in the first 24 h after a boundary."""
    d = ns(times)
    return (d >= DEV_START.value) & (d + MINUTE.value + h_min * MINUTE.value < cutoff.value) & ~embargoed(times)


def block_mask(times, h_min: int, a: pd.Timestamp, b: pd.Timestamp) -> np.ndarray:
    """labels.block_membership: decision after the 24 h embargo and label exit inside [a, b)."""
    d = ns(times)
    return (d >= (a + EMBARGO).value) & (d + MINUTE.value + h_min * MINUTE.value < b.value)


def n_eff(times, mask: np.ndarray, h_min: int) -> int:
    """labels.overlap: sum over contiguous 15-minute blocks of floor(N_block / q), q = H / 15m."""
    q = h_min // 15
    d = ns(times)[np.asarray(mask, bool)]
    if not len(d):
        return 0
    breaks = np.flatnonzero(np.diff(d) != 15 * MINUTE.value)
    sizes = np.diff(np.r_[0, breaks + 1, len(d)])
    return int((sizes // q).sum())


# ---------------------------------------------------------------- features
@dataclass
class Features:
    frame: pd.DataFrame            # decision_time + float32 feature columns (never a target)
    groups: dict                   # column -> V1 / V2 / V3 / V4
    tech: dict                     # V4 column -> technique id
    avail: np.ndarray              # int64 ns per row: latest logical_available_at of any input used


def technique_ids() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(raw signal ids incl. B1-B3, OCO proposal ids); K10 is its own grid proposal. Post-freeze ids excluded."""
    ids = [k for k, s in CATALOG.items() if not s.post_freeze and k != "K10"]
    oco = tuple(k for k in ids if k.split("_")[0] in state.OCO_FAMILIES)
    return tuple(k for k in ids if k not in oco), oco


def funding_frame(settlements: pd.DataFrame, interval_hours: float = 8.0) -> pd.DataFrame:
    """Research funding inputs from sim settlements (time, rate[, raw_calc_time]): logical_available_at = the actual
    calc time when present. The archive loader (out/k45_funding.py) asserts funding_interval_hours == 8 for every
    pre-2026 row, so the interval is observed there, not imputed."""
    avail = settlements.raw_calc_time if "raw_calc_time" in settlements else settlements.time
    return pd.DataFrame({"available_time": pd.to_datetime(avail, utc=True), "rate": settlements.rate.to_numpy(float),
                         "interval_hours": float(interval_hours), "interval_missing": 0}).sort_values(
        "available_time", kind="stable").reset_index(drop=True)


def _regime_pos(frame: pd.DataFrame, t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """regime._asof row choice: latest timestamp among rows with timestamp <= T and availability <= T."""
    ts = ns(frame.timestamp)
    av = regime.available_ns(frame)
    av = ts if av is None else av
    if not len(ts):
        return np.full(len(t), -1), ts, av
    order = np.argsort(av, kind="stable")
    tso = ts[order]
    best = np.maximum.accumulate(np.where(tso == np.maximum.accumulate(tso), np.arange(len(tso)), 0))
    k = np.searchsorted(av[order], t, side="right") - 1
    return np.where(k >= 0, order[best[np.maximum(k, 0)]], -1), ts, av


def build_features(ctx: Context, start: pd.Timestamp, end: pd.Timestamp, funding: pd.DataFrame) -> Features:
    """inputs.V1-V4 on the 15-minute grid [start, end). Row T reads only inputs with logical availability <= T
    (data_plan.store.asof_rule); missing exogenous values stay NaN with age and missing masks (no backfill)."""
    times = pd.date_range(start, end, freq="15min", inclusive="left")
    t = ns(times)
    cols, groups, tech = {}, {}, {}
    avail = np.full(len(t), np.iinfo(np.int64).min, np.int64)

    def put(name, values, group, ident=None):
        cols[name] = np.asarray(values, float)
        groups[name] = group
        if ident is not None:
            tech[name] = ident

    def seen(when: np.ndarray, ok: np.ndarray):
        nonlocal avail
        avail = np.where(ok, np.maximum(avail, when), avail)

    err = dict(invalid="ignore", divide="ignore")
    # V1 market: S4 multi-window indicators, 15 m and 1 m sequences, UTC time
    for w, minutes in state.S4_WINDOWS.items():
        b = ctx.bars(minutes)
        bt = ns(b.decision_time)
        k = _pos(bt, t)
        with np.errstate(**err):
            frame = state.s4_indicators(b)
        for name, x in frame.items():
            put(f"v1_{w}_{name}", _take(x.to_numpy(float), k), "V1")
        seen(_take(bt, k, 0), k >= 0)
    b = ctx.bars(15)
    bt = ns(b.decision_time)
    k15 = _pos(bt, t)
    o, h, l, c, v, tb = (b[x].to_numpy(float) for x in ("open", "high", "low", "close", "volume", "taker_buy"))
    with np.errstate(**err):
        put("v1_vwap_dev", _take((b.close / indicators.vwap_utc(b) - 1).to_numpy(float), k15), "V1")
        s = pd.Series
        for wn, name in ((4, "h1"), (16, "h4")):
            put(f"v1_{name}_ret", _take(np.log(c / s(o).shift(wn - 1).to_numpy()) * 1e4, k15), "V1")
            put(f"v1_{name}_range", _take(np.log(s(h).rolling(wn).max() / s(l).rolling(wn).min()).to_numpy() * 1e4,
                                          k15), "V1")
            put(f"v1_{name}_log_volume", _take(np.log1p(s(v).rolling(wn).sum()).to_numpy(), k15), "V1")
            put(f"v1_{name}_taker_share", _take((s(tb).rolling(wn).sum() / s(v).rolling(wn).sum()).to_numpy(), k15),
                "V1")
        bar = {"ret_bps": np.log(c / o) * 1e4, "range_bps": np.log(h / l) * 1e4, "log_volume": np.log1p(v),
               "taker_share": tb / v}
    for j in range(SEQ15):                                        # j = 0 oldest ... 31 = bar closing at <= T
        idx = np.where(k15 >= 0, k15 - (SEQ15 - 1 - j), -1)
        for name, x in bar.items():
            put(f"v1_seq15_{j:02d}_{name}", _take(x, idx), "V1")
    seen(_take(bt, k15, 0), k15 >= 0)
    m = ctx.minutes
    mt = ns(m.open_time)
    last = _pos(mt, t - MINUTE.value)                            # minute closed at <= T
    mo, mh, ml, mc, mv, mb = (m[x].to_numpy(float) for x in ("open", "high", "low", "close", "volume",
                                                            "taker_buy_base_volume"))
    with np.errstate(**err):
        one = {"ret_bps": np.log(mc / mo) * 1e4, "range_bps": np.log(mh / ml) * 1e4, "log_volume": np.log1p(mv),
               "taker_share": mb / mv}
    for j in range(SEQ1M):
        idx = np.where(last >= 0, last - (SEQ1M - 1 - j), -1)
        for name, x in one.items():
            put(f"v1_seq1m_{j:02d}_{name}", _take(x, idx), "V1")
    seen(_take(mt, last, 0) + MINUTE.value, last >= 0)
    day = times.hour * 60 + times.minute
    for name, x in (("dow_sin", np.sin(2 * np.pi * (times.dayofweek + day / 1440) / 7)),
                    ("dow_cos", np.cos(2 * np.pi * (times.dayofweek + day / 1440) / 7)),
                    ("hour_sin", np.sin(2 * np.pi * day / 1440)), ("hour_cos", np.cos(2 * np.pi * day / 1440))):
        put(f"v1_{name}", np.asarray(x, float), "V1")

    # V2 futures: five 5-minute metrics (archive taker only, amendment A3), premium, funding
    met = ctx.metrics.sort_values("available_time", kind="stable")
    at = ns(met.available_time)
    for name in ("global_ls", "top_ls", "oi", "oi_value", "taker_lsr"):
        x = met[name].to_numpy(float)
        fin = _ok(x)
        tt, xv = at[fin], np.log(x[fin])
        k = _pos(tt, t)
        age = t - (_take(tt, k, 0) - 5 * MINUTE.value)           # since create_time = available_time - 5 m
        ok = (k >= 0) & (t - _take(tt, k, 0) <= METRIC_TTL.value)
        val = np.where(ok, _take(xv, k), np.nan)
        put(f"v2_{name}", val, "V2")
        put(f"v2_{name}_age", _age(age, k >= 0), "V2")
        put(f"v2_{name}_missing", (~ok).astype(float), "V2")
        for lag in ("1h", "4h", "1d"):
            tl = t - pd.Timedelta(lag).value
            k2 = _pos(tt, tl)
            ok2 = (k2 >= 0) & (tl - _take(tt, k2, 0) <= METRIC_TTL.value)
            put(f"v2_d_{name}_{lag}", np.where(ok & ok2, val - _take(xv, k2), np.nan), "V2")
        seen(_take(tt, k, 0), k >= 0)
    with np.errstate(**err):
        pct = met.global_ls.rolling(30 * 288, min_periods=30 * 288 // 4).rank(pct=True).to_numpy(float)
    k = _pos(at, t)
    put("v2_global_ls_pct30d", np.where((k >= 0) & (t - _take(at, k, 0) <= METRIC_TTL.value), _take(pct, k), np.nan),
        "V2")
    seen(_take(at, k, 0), k >= 0)
    prem = ctx.premium.sort_values("available_time", kind="stable")
    pt, px = ns(prem.available_time), prem.premium.to_numpy(float)
    fin = np.isfinite(px)
    with np.errstate(**err):
        z = indicators.zscore_past(pd.Series(px), 30 * 1440, 30 * 1440 // 4).to_numpy(float)
    ptf, pxf, zf = pt[fin], px[fin], z[fin]
    k = _pos(ptf, t)
    ok = (k >= 0) & (t - _take(ptf, k, 0) <= PREMIUM_TTL.value)
    val = np.where(ok, _take(pxf, k) * 1e4, np.nan)
    put("v2_premium_bps", val, "V2")
    put("v2_premium_age", _age(t - _take(ptf, k, 0), k >= 0), "V2")
    put("v2_premium_missing", (~ok).astype(float), "V2")
    tl = t - pd.Timedelta("1h").value
    k2 = _pos(ptf, tl)
    ok2 = (k2 >= 0) & (tl - _take(ptf, k2, 0) <= PREMIUM_TTL.value)
    put("v2_d_premium_1h", np.where(ok & ok2, val - _take(pxf, k2) * 1e4, np.nan), "V2")
    put("v2_premium_z30d", np.where(ok, _take(zf, k), np.nan), "V2")
    seen(_take(ptf, k, 0), k >= 0)
    fund = funding.sort_values("available_time", kind="stable")
    ft, fr = ns(fund.available_time), fund.rate.to_numpy(float)
    fin = np.isfinite(fr)
    with np.errstate(**err):
        fz = indicators.zscore_past(pd.Series(fr[fin]), 90, 22).to_numpy(float)
    ftf, frf = ft[fin], fr[fin]
    interval = np.where(fund.interval_missing.to_numpy(int)[fin] == 1, np.nan,
                        fund.interval_hours.to_numpy(float)[fin])
    k = _pos(ftf, t)
    ok = (k >= 0) & (t - _take(ftf, k, 0) <= FUNDING_TTL.value)
    put("v2_funding_bps", np.where(ok, _take(frf, k) * 1e4, np.nan), "V2")
    iv = np.where(ok, _take(interval, k), np.nan)
    put("v2_funding_interval_h", iv, "V2")
    put("v2_funding_interval_missing", (ok & ~np.isfinite(iv)).astype(float), "V2")
    put("v2_funding_age", _age(t - _take(ftf, k, 0), k >= 0), "V2")
    put("v2_funding_missing", (~ok).astype(float), "V2")
    put("v2_funding_z30d", np.where(ok, _take(fz, k), np.nan), "V2")
    seen(_take(ftf, k, 0), k >= 0)

    # V3 Stage-A: fifteen expm1-restored bps outputs, causal M/L, age and missing mask (E rule: age <= 24 h)
    pos, ts, av = _regime_pos(ctx.regime, t)
    ok = (pos >= 0) & (t - _take(ts, pos, 0) <= E_MAX_AGE.value)
    from .sim.data import TARGETS
    for target in TARGETS:
        put(f"v3_pred_{target}", np.where(ok, _take(ctx.regime[f"prediction_{target}"].to_numpy(float), pos), np.nan),
            "V3")
    for name in ("M", "L"):
        put(f"v3_{name}", np.where(ok, _take(ctx.regime[name].to_numpy(float), pos), np.nan), "V3")
    put("v3_age", _age(t - _take(ts, pos, 0), pos >= 0), "V3")
    put("v3_missing", (~ok).astype(float), "V3")
    seen(_take(av, pos, 0), pos >= 0)

    # V4 techniques: raw NONE/NATIVE side channels, OCO proposals, K10 grid proposal (no fabricated side)
    sig_ids, oco_ids = technique_ids()
    close15 = _take(c, k15)

    def seen_rows(table):
        """A technique row is available at its decision_time; the channels read the latest row <= T."""
        tt = np.sort(ns(table.decision_time))
        p = _pos(tt, t)
        seen(_take(tt, p, 0), p >= 0)

    for ident in sig_ids:
        table, _ = build_variant(ctx, ident, gated=False, style="NATIVE")
        channels = state.side_channels(table, times, CATALOG[ident].cadence_min == 5)
        for name, x in zip(("event_side", "last_side", "age", "never_seen"), channels):
            put(f"v4_{ident}_{name}", x, "V4", ident)
        seen_rows(table)
    for ident in oco_ids:
        table, _ = build_variant(ctx, ident, gated=False, style="NATIVE")
        for name, x in zip(("proposal_active", "upper_bps", "lower_bps"), state.oco_channels(table, times, close15)):
            put(f"v4_{ident}_{name}", x, "V4", ident)
        seen_rows(table)
    plan = grid_strategy.grid_plan(ctx, gated=False)
    gt = ns(plan.decision_time)
    k = _pos(gt, t)
    active = (k >= 0) & (_take(gt, k, 0) == t)
    put("v4_K10_proposal_active", active.astype(float), "V4", "K10")
    put("v4_K10_step_bps", np.where(active, _take(plan.g.to_numpy(float), k), np.nan), "V4", "K10")
    seen(_take(gt, k, 0), k >= 0)

    data = {name: np.where(np.isfinite(x), x, np.nan).astype(np.float32) for name, x in cols.items()}
    frame = pd.concat([pd.DataFrame({"decision_time": times}), pd.DataFrame(data)], axis=1)
    return Features(frame, groups, tech, avail)


def assert_causal(features: Features) -> None:
    t = ns(features.frame.decision_time)
    late = int((features.avail > t).sum())
    if late:
        raise ValueError(f"{late} feature rows with logical_available_at > T")


def assert_isolated(feature_frame: pd.DataFrame, labels: pd.DataFrame) -> None:
    """labels.isolation: no target name and no column equal to a target inside the feature frame."""
    names = [c for c in feature_frame if c.startswith(("g_", "exit_")) or c in labels.columns and c != "decision_time"]
    if names:
        raise ValueError(f"target column in features: {names}")
    if not (pd.DatetimeIndex(feature_frame.decision_time) == pd.DatetimeIndex(labels.decision_time)).all():
        raise ValueError("feature and label rows are not aligned")
    for g in [c for c in labels if c.startswith("g_")]:
        y = labels[g].to_numpy(float)
        fin = np.isfinite(y)
        if not fin.any():
            continue
        y32 = y[fin].astype(np.float32)
        for c in feature_frame.columns[1:]:
            x = feature_frame[c].to_numpy()[fin].astype(np.float32)
            if np.array_equal(x, y32):
                raise ValueError(f"target column in features: {c} equals {g}")


def view_columns(features: Features, view: str, drop_ids=()) -> list[str]:
    keep = {"V5_continuous": ("V1", "V2", "V3"), "V6_full": ("V1", "V2", "V3", "V4")}[view]
    drop = set(drop_ids)
    return [c for c, g in features.groups.items() if g in keep and features.tech.get(c) not in drop]


# ---------------------------------------------------------------- models
@dataclass
class Model:
    name: str
    columns: list
    state: dict


def fit_model(name: str, x: np.ndarray, y: np.ndarray, columns: list) -> Model:
    """Ridge: train-only standardization, NaN -> train mean (z = 0). CatBoost: frozen RMSE config, native NaN."""
    x = np.asarray(x, np.float64 if name in RIDGE_LAMBDA else np.float32)
    y = np.asarray(y, float)
    if not np.isfinite(y).all():
        raise ValueError("non-finite training target")
    if name in RIDGE_LAMBDA:
        with np.errstate(invalid="ignore"):
            mean, std = np.nanmean(x, axis=0), np.nanstd(x, axis=0)
        mean = np.where(np.isfinite(mean), mean, 0.0)
        std = np.where(np.isfinite(std) & (std > 0), std, 1.0)
        z = np.nan_to_num((x - mean) / std, nan=0.0)
        # min ||y - b - z w||^2 + lambda ||w||^2 (unpenalized intercept; the sklearn Ridge objective), normal equations
        # this venv's numpy has no BLAS (a 120k x 475 Gram takes ~6 min); scipy's bundled BLAS does it in ~1 s
        from scipy.linalg import blas
        zm, ym = z.mean(axis=0), y.mean()
        zc = np.asfortranarray(z - zm)
        gram = blas.dgemm(1.0, zc, zc, trans_a=1)
        rhs = blas.dgemv(1.0, zc, y - ym, trans=1)
        coef = np.linalg.solve(gram + RIDGE_LAMBDA[name] * np.eye(z.shape[1]), rhs)
        return Model(name, list(columns), {"mean": mean, "std": std, "coef": coef.astype(float),
                                           "intercept": float(ym - zm @ coef)})
    if name != "catboost":
        raise ValueError(f"unknown model config {name}")
    from catboost import CatBoostRegressor
    model = CatBoostRegressor(**CATBOOST_PARAMS, thread_count=CATBOOST_THREADS, task_type="CPU", verbose=False,
                              allow_writing_files=False)
    model.fit(x, y)
    # predict through the persisted canonical-JSON checkpoint, so every prediction equals the hashed artifact
    # (the JSON float text differs from the in-memory model by ~1e-15)
    return load_checkpoint(checkpoint_bytes(Model(name, list(columns), {"catboost": model})))


def predict(model: Model, x: np.ndarray) -> np.ndarray:
    if model.name in RIDGE_LAMBDA:
        s = model.state
        z = np.nan_to_num((np.asarray(x, np.float64) - s["mean"]) / s["std"], nan=0.0)
        return z @ s["coef"] + s["intercept"]
    return np.asarray(model.state["catboost"].predict(np.asarray(x, np.float32)), float)


def checkpoint_bytes(model: Model) -> bytes:
    if model.name in RIDGE_LAMBDA:                      # deterministic bytes: JSON header + raw float64 arrays
        s = model.state
        head = json.dumps({"name": model.name, "columns": model.columns, "intercept": s["intercept"].hex()}).encode()
        body = b"".join(np.ascontiguousarray(s[k], "<f8").tobytes() for k in ("mean", "std", "coef"))
        return b"RIDGE" + len(head).to_bytes(8, "little") + head + body
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "m.json")
        model.state["catboost"].save_model(str(path), format="json")
        tree = json.loads(path.read_text(encoding="utf-8"))
    for field in ("model_guid", "train_finish_time"):   # per-fit id and wall clock; the hash covers the model only
        tree["model_info"].pop(field, None)
    blob = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()
    head = json.dumps({"name": model.name, "columns": model.columns}).encode()
    return b"CATB" + len(head).to_bytes(8, "little") + head + blob


def load_checkpoint(blob: bytes) -> Model:
    if blob[:5] == b"RIDGE":
        n = int.from_bytes(blob[5:13], "little")
        head = json.loads(blob[13:13 + n])
        arrays = np.frombuffer(blob[13 + n:], "<f8").reshape(3, len(head["columns"]))
        return Model(head["name"], head["columns"], {"mean": arrays[0].copy(), "std": arrays[1].copy(),
                                                     "coef": arrays[2].copy(),
                                                     "intercept": float.fromhex(head["intercept"])})
    if blob[:4] != b"CATB":
        raise ValueError("unknown checkpoint format")
    n = int.from_bytes(blob[4:12], "little")
    head = json.loads(blob[12:12 + n])
    import tempfile
    from catboost import CatBoostRegressor
    model = CatBoostRegressor()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "m.json")
        path.write_bytes(blob[12 + n:])
        model.load_model(str(path), format="json")
    return Model(head["name"], head["columns"], {"catboost": model})


def checkpoint_sha256(model: Model) -> str:
    return sha256_bytes(checkpoint_bytes(model))


# ---------------------------------------------------------------- position rule and R2-52A ledger
@functools.cache
def ax_runner():
    """scripts/sim_adaptive_exit.py (R2-52A research runner): run_ax / validation_pnl / e_series / e_at."""
    path = ROOT / "scripts/sim_adaptive_exit.py"
    spec = importlib.util.spec_from_file_location("r2_54_ax_runner", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def signal_table(times, yhat, side: int, e0, k: float) -> pd.DataFrame:
    """position_rule: flat -> enter `side` at open(T+1m) when side*yhat - 4 > 0; held -> full close at open(T+1m)
    when side*yhat <= 0. NaN yhat never acts. Market rows, no max hold, R2-52A state columns inert."""
    s = side * np.asarray(yhat, float)
    with np.errstate(invalid="ignore"):
        enter, close = s - ENTRY_BPS > 0, s <= 0
    table = make_table(pd.DatetimeIndex(times), np.where(enter, side, 0), 0, 0,
                       exit_long=close & (side == 1), exit_short=close & (side == -1),
                       e0_bps=np.asarray(e0, float), k=float(k), e_col=0.0, **AX_DEFAULTS)
    return schema.validate(table)


def fold_ledger(table, minutes, e, e_min, a, b, fee_per_side: float, k: float) -> dict:
    """Selection accounting (selection.fold_execution): R2-52A minute ledger on [a, b) from flat, constant k; an open
    position is marked at the fold-end close without an exit fee and pays the settlements it held through (the same
    arithmetic as sim_adaptive_exit.validation_pnl, through the same run_ax)."""
    ax = ax_runner()
    config = replace(CONFIG, fee_per_side=fee_per_side, close_at_end=False)
    result = ax.run_ax(table, minutes, e, e_min, a, b, config, np.full(len(minutes), k))
    pnl = float(result.minute_pnl.sum())
    result_pnl = pnl
    held = result.open_position
    if held is not None and config.include_funding:
        events = costs.funding_events(held["side"], held["entry_time"], b - MINUTE, config.funding_boundary)
        pnl += sum(v for _, v in events) * held["units"]
    trades = result.trades
    inside = minutes.loc[(minutes.open_time >= a) & (minutes.open_time < b)]
    valid = bool(np.isfinite(pnl) and len(inside) == (b - a) // MINUTE)
    return {"pnl": pnl, "result_minute_pnl": result_pnl, "completed": int(trades.position_id.nunique()),
            "trades": trades, "valid": valid, "open_at_end": held is not None,
            "exit_reasons": trades.exit_reason.value_counts().to_dict()}


def settlements(events: pd.DataFrame) -> pd.DataFrame:
    """Funding events (time = actual fundingTime, rate), sorted; no schedule rounding (data_plan.funding)."""
    out = pd.DataFrame({"time": pd.to_datetime(events.time, utc=True), "rate": events.rate.to_numpy(float)})
    out = out.sort_values("time", kind="stable").reset_index(drop=True)
    if out.time.duplicated().any():
        raise ValueError("duplicate funding event time")
    return out


def actual_settlements(sim_settlements: pd.DataFrame) -> pd.DataFrame:
    """Pre-2026 events from costs._settlements: its raw_calc_time is the actual fundingTime."""
    return settlements(pd.DataFrame({"time": sim_settlements.raw_calc_time, "rate": sim_settlements.rate}))


def simulator_minutes(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Minute bucketing, used only inside the simulator: each actual event books at the minute containing it."""
    t = ns(pd.DatetimeIndex(pd.to_datetime(frame.time, utc=True)).floor("min"))
    if len(t) > 1 and not np.all(np.diff(t) > 0):
        raise ValueError("two funding events in one minute")
    return t, frame.rate.to_numpy(float)


@contextlib.contextmanager
def ledger_settlements(frame: pd.DataFrame):
    """Point the sim ledger (costs.funding_events) at the actual events of `frame` for the duration of the block."""
    arrays = simulator_minutes(frame)
    original = costs._settlement_arrays
    costs._settlement_arrays = lambda: arrays
    try:
        yield
    finally:
        costs._settlement_arrays = original


def weekly_predictions(times, schedule: list, end: pd.Timestamp, fit, predict_rows, first_model=None):
    """live_retraining on the 15-minute grid: the checkpoint retrained at r serves [r, next r). On retrain failure the
    previous checkpoint serves only decisions before its retrain_time + 7 d; later decisions (and every decision with
    no valid checkpoint) get NaN, which blocks new entries and model exits (R2-52A stops continue).
    fit(r) -> (model, record); predict_rows(model, mask) -> values. Returns (yhat, events)."""
    times = pd.DatetimeIndex(times)
    yhat = np.full(len(times), np.nan)
    events, active, active_r = [], None, None
    for j, r in enumerate(schedule):
        nxt = schedule[j + 1] if j + 1 < len(schedule) else end
        rec = {"retrain_time": str(r), "serves": [str(r), str(nxt)], "fallback": None}
        try:
            model, info = (first_model if j == 0 and first_model is not None else fit(r))
            rec.update(info)
            active, active_r = model, r
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            if active is not None and fallback_ok(r, active_r):
                rec["fallback"] = (f"retrain failed ({reason}); previous checkpoint {active_r} serves only before "
                                   f"{active_r + pd.Timedelta(days=7)}")
            else:
                rec["fallback"] = f"hard failure ({reason}); new entries blocked"
                active = None
        window = (times >= r) & (times < nxt)
        serve = window & (times < active_r + pd.Timedelta(days=7)) if active is not None and active_r != r else window
        if active is None:
            serve = np.zeros(len(times), bool)
        rec["blocked_decisions"] = int(window.sum() - serve.sum())
        if active is not None and serve.any():
            yhat[serve] = predict_rows(active, serve)
            rec["first_prediction"] = str(times[serve][0])
        events.append(rec)
    return yhat, events


# ---------------------------------------------------------------- statistics
def spearman(x, y) -> float:
    from scipy.stats import rankdata
    x, y = np.asarray(x, float), np.asarray(y, float)
    fin = np.isfinite(x) & np.isfinite(y)
    if fin.sum() < 3:
        return float("nan")
    rx, ry = rankdata(x[fin]), rankdata(y[fin])
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def bootstrap_ic(x, y, block: int = 672, reps: int = 10000, seed: int = 20261008) -> dict:
    """bootstrap: circular moving-block resampling of the ordered rows; one-sided 95% percentile lower bound and
    p = (1 + #{IC_b <= 0}) / (reps + 1)."""
    from scipy.stats import rankdata
    x, y = np.asarray(x, float), np.asarray(y, float)
    fin = np.isfinite(x) & np.isfinite(y)
    x, y = x[fin], y[fin]
    n = len(x)
    rng = np.random.default_rng(seed)
    blocks = -(-n // block)
    ics = np.empty(reps)
    step = 100
    for r0 in range(0, reps, step):
        m = min(step, reps - r0)
        starts = rng.integers(0, n, size=(m, blocks))
        idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(m, -1)[:, :n]
        rx, ry = rankdata(x[idx], axis=1), rankdata(y[idx], axis=1)
        rx -= rx.mean(axis=1, keepdims=True); ry -= ry.mean(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            ics[r0:r0 + m] = (rx * ry).sum(1) / np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))
    ics = np.where(np.isfinite(ics), ics, 0.0)
    return {"ic": spearman(x, y), "lower": float(np.percentile(ics, 5)),
            "p": float((1 + np.count_nonzero(ics <= 0)) / (reps + 1)), "method": "circular moving-block",
            "block_rows": block, "reps": reps, "seed": seed, "n": int(n)}


def holm(pvalues: dict) -> dict:
    """Holm step-down over the side hypotheses; an unopened side (None) enters with p = 1 (the family stays two)."""
    p = {k: (1.0 if v is None else float(v)) for k, v in pvalues.items()}
    order = sorted(p, key=lambda k: (p[k], k))
    m, running, out = len(p), 0.0, {}
    for i, name in enumerate(order):
        running = max(running, min(1.0, (m - i) * p[name]))
        out[name] = {"p": p[name], "p_adj": running, "rank": i + 1, "opened": pvalues[name] is not None}
    return out


# ---------------------------------------------------------------- ranking, eligibility, gates
_K_ORDER = {2.0: 0, 1.5: 1, 1.0: 2}
_VIEW_ORDER = {"V5_continuous": 0, "V6_full": 1}
_H_ORDER = {h: i for i, h in enumerate(HORIZONS)}
_MODEL_ORDER = {"ridge_100": (0, 0), "ridge_10": (0, 1), "ridge_1": (0, 2), "catboost": (1, 0)}


def _num(x) -> float:
    return -math.inf if x is None or not np.isfinite(x) else float(x)


def _compare(a: dict, b: dict) -> int:
    """selection.rank_per_side, tie_tolerance 1e-12 on the numeric keys, then the frozen priorities."""
    for key in ("net4", "median_ic", "net8"):
        x, y = _num(a[key]), _num(b[key])
        if x == y or (math.isfinite(x) and math.isfinite(y) and abs(x - y) <= TIE):
            continue
        return -1 if x > y else 1
    ka = (_K_ORDER[a["k"]], _VIEW_ORDER[a["view"]], _MODEL_ORDER[a["model"]][0], _MODEL_ORDER[a["model"]][1],
          _H_ORDER[a["horizon"]])
    kb = (_K_ORDER[b["k"]], _VIEW_ORDER[b["view"]], _MODEL_ORDER[b["model"]][0], _MODEL_ORDER[b["model"]][1],
          _H_ORDER[b["horizon"]])
    return (ka > kb) - (ka < kb)


def rank_candidates(rows: list) -> list:
    return sorted(rows, key=functools.cmp_to_key(_compare))


def is_eligible(row: dict) -> bool:
    return row["folds_valid"] == 10 and row["completed"] >= MIN_POSITIONS


def select_side(rows: list) -> dict:
    """Rank every pair, select the top eligible one once (gate_order: no runner-up promotion)."""
    ranked = rank_candidates(rows)
    trace = [{**{k: v for k, v in r.items() if not isinstance(v, (list, dict))}, "rank": i + 1,
              "eligible": is_eligible(r)} for i, r in enumerate(ranked)]
    chosen = next((r for r in ranked if is_eligible(r)), None)
    return {"selected": chosen, "trace": trace, "eligible": int(sum(t["eligible"] for t in trace))}


def validation_gates(fold_ic, fold_net4, pooled_net8: float, buckets: dict) -> dict:
    ic = np.asarray(fold_ic, float)
    statistical = bool(np.nanmedian(ic) > 0 and np.sum(ic > 0) >= 7) if np.isfinite(ic).any() else False

    def stable(values):
        v = np.asarray(values, float)
        return bool(np.isfinite(v).all() and np.sum(v > 0) >= 2 and not np.any(v < -0.01))

    stability = all(stable(buckets[name]) for name in ("M", "L"))
    economic = bool(np.sum(np.asarray(fold_net4, float) > 0) >= 7 and pooled_net8 >= 0)
    return {"statistical": statistical, "stability": stability, "economic": economic,
            "pass": statistical and stability and economic, "median_ic": float(np.nanmedian(ic)),
            "positive_ic_folds": int(np.sum(ic > 0)), "positive_net4_folds": int(np.sum(np.asarray(fold_net4) > 0)),
            "pooled_net8": float(pooled_net8), "buckets": buckets}


def v6_gates(full_ic: float, family_ic, top_id_ic: float, id_shares) -> dict:
    """gates.v6_extra plus bias_controls.single_id_gate."""
    fam = np.asarray(family_ic, float)
    family = bool(np.sum(fam > 0) >= 5)
    top = bool(np.isfinite(top_id_ic) and np.isfinite(full_ic) and full_ic > 0 and top_id_ic >= 0.8 * full_ic)
    counts: dict = {}
    for shares in id_shares:
        for ident, share in shares.items():
            if share >= 0.5:
                counts[ident] = counts.get(ident, 0) + 1
    single = not any(n >= 6 for n in counts.values())
    return {"family": family, "top_id": top, "single_id": single, "pass": family and top and single,
            "family_ic_positive": int(np.sum(fam > 0)), "top_id_retained": (float(top_id_ic / full_ic)
                                                                            if full_ic else float("nan")),
            "id_majority_folds": counts}


# ---------------------------------------------------------------- weekly retraining
def thursdays(start: pd.Timestamp, end: pd.Timestamp) -> list:
    """live_retraining.cadence: every Thursday 00:00 UTC in [start, end)."""
    first = start.normalize() + pd.Timedelta(days=(3 - start.dayofweek) % 7)
    if first < start:
        first += pd.Timedelta(days=7)
    return list(pd.date_range(first, end, freq="7D", inclusive="left"))


def fallback_ok(retrain_time: pd.Timestamp, previous: pd.Timestamp) -> bool:
    """live_retraining.fallback: the previous checkpoint only while its scheduled age is <= 7 days."""
    return retrain_time - previous <= pd.Timedelta(days=7)
