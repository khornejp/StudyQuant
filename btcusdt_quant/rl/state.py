"""Causal 15-minute RL observations (plan 3 Task 2, contract C7-C9): every row T reads only what Context.truncate(T)
keeps, so a store built on a truncated context equals the full store up to T. Account channels (C6) come from the env."""
from __future__ import annotations
import dataclasses, warnings
from dataclasses import dataclass
from pathlib import Path
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from ..sim import data, indicators, provenance, regime, store as feature_store
from ..sim.rolling import TRAIN_START
from ..sim.strategies import CATALOG, Context, build_variant

COMPOSITES = ("B1", "B2", "B3")
OCO_FAMILIES = ("K06", "K07", "K14")          # entry="oco": no raw side, proposal channels instead (C8)
_ATOMIC = [k for k, s in CATALOG.items() if s.simulator == "core" and k not in COMPOSITES]
OCO_IDS = tuple(k for k in _ATOMIC if k.split("_")[0] in OCO_FAMILIES)
SIGNAL_IDS = tuple(k for k in _ATOMIC if k not in OCO_IDS)
SEQ_LEN = 32
SEQ_NAMES = ("ret_bps", "range_bps", "log_volume", "taker_share")
AGE_CAP = np.log1p(10080)
PREDICTION_AGE = pd.Timedelta(minutes=14)     # C7
METRIC_TTL = pd.Timedelta(hours=1)
SETTLEMENT_MIN = 480                          # BTCUSDT funding every 8 h at 00/08/16 UTC (all 2020-2026 settlements)
_UNSCALED_SUFFIX = ("_side", "_never_seen", "_proposal_active", "__nan", "_sin", "_cos")
_UNMASKED = ("_age", "min_to_settlement")     # continuous but never NaN
CACHE_ROOT = data.ROOT / "artifacts/rl_state"
S4_WINDOWS = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}
# ponytail: 30-day windows are row counts (5 m metrics, 1 m premium, 8 h funding), exact only without data gaps
DAY30 = {"metrics": 30 * 288, "premium": 30 * 1440, "funding": 30 * 3}


@dataclass(frozen=True)
class StateStore:
    times: np.ndarray            # int64 ns, 15-minute grid T
    seq: np.ndarray              # float32 [n, SEQ_LEN, len(SEQ_NAMES)], oldest first, last row = bar closing at T
    static: np.ndarray           # float32 [n, len(feature_names)]
    mask_missing: np.ndarray     # bool [n], C7 detector missing
    feature_names: list[str]     # static channel names
    variant: str


def is_scaled(name: str) -> bool:
    """C9: continuous channels are standardized; sides, flags, masks and sin/cos are not."""
    return name not in ("missing", "seq__nan") and not name.endswith(_UNSCALED_SUFFIX)


def _pick(values, position: np.ndarray, default: float) -> np.ndarray:
    out = np.full(len(position), default, dtype=float)
    ok = position >= 0
    out[ok] = np.asarray(values, float)[position[ok]]
    return out


def _ns(times) -> np.ndarray:
    return pd.DatetimeIndex(times).as_unit("ns").asi8


def side_channels(table: pd.DataFrame, times: pd.DatetimeIndex, five_minute: bool):
    """C8 event_side, last_side, scaled age, never_seen. 5-minute ids: latest nonzero event in (T-15m, T];
    others: the row with the latest decision_time <= T. A row with allow_entry False counts as side 0."""
    t, now = _ns(table.decision_time), _ns(times)
    side = np.where(np.asarray(table.allow_entry, bool), np.asarray(table.side, int), 0)
    nonzero = side != 0
    t_nz = t[nonzero]
    p = np.searchsorted(t_nz, now, side="right") - 1
    last = _pick(side[nonzero], p, 0)
    age_min = (now - _pick(t_nz, p, 0).astype(np.int64)) / 60e9
    never = (p < 0).astype(float)
    age = np.where(p >= 0, np.clip(np.log1p(np.maximum(age_min, 0)), 0, AGE_CAP) / AGE_CAP, 1.0)
    if five_minute:
        event = np.where((p >= 0) & (age_min < 15), last, 0)
    else:
        event = _pick(side, np.searchsorted(t, now, side="right") - 1, 0)
    return event, last, age, never


def oco_channels(table: pd.DataFrame, times: pd.DatetimeIndex, close: np.ndarray):
    """proposal_active and the upper/lower entry distance from close_T in bps (NaN when no live proposal)."""
    t, now = _ns(table.decision_time), _ns(times)
    q = np.searchsorted(t, now, side="right") - 1
    expiry = _pick(table.expiry_min, q, 0) * 60e9
    live = (_pick(table.allow_entry, q, 0) > 0) & (now - _pick(t, q, 0) < expiry)
    with np.errstate(invalid="ignore", divide="ignore"):
        upper = np.where(live, np.log(_pick(table.upper, q, np.nan) / close) * 1e4, np.nan)
        lower = np.where(live, np.log(_pick(table.lower, q, np.nan) / close) * 1e4, np.nan)
    return live.astype(float), upper, lower


def s4_indicators(b: pd.DataFrame) -> pd.DataFrame:
    """Frozen S4 per-window list (r2_51 freeze, addendum 2026-10-08) on complete bars; row i reads bars <= i only."""
    c, o, h, l, v = b.close, b.open, b.high, b.low, b.volume
    r = np.log(c / c.shift())
    e9, e21 = indicators.ema(c, 9), indicators.ema(c, 21)
    bb = indicators.bollinger(c, 20, 1.0)                    # upper - middle = std20
    hi, lo, rng = h.rolling(20).max(), l.rolling(20).min(), h - l
    return pd.DataFrame({
        "ret1": r, "ret4": np.log(c / c.shift(4)), "ret16": np.log(c / c.shift(16)), "rv20": r.rolling(20).std(ddof=0),
        "close_ema9": c / e9 - 1, "ema9_ema21": e9 / e21 - 1, "boll_z": (c - bb.middle) / (bb.upper - bb.middle),
        "rsi14": indicators.rsi(c, 14), "atr14": indicators.atr(b, 14) / c, "adx14": indicators.adx(b, 14),
        "range_pos20": (c - lo) / (hi - lo), "volume_z": indicators.zscore_past(v, 20, 20),
        "taker_imb4": (b.taker_buy / v - 0.5).rolling(4).mean(),
        "upper_wick": (h - np.maximum(o, c)) / rng, "lower_wick": (np.minimum(o, c) - l) / rng})


def build_state_store(ctx: Context, start: pd.Timestamp, end: pd.Timestamp, variant: str) -> StateStore:
    if variant not in ("S1", "S3", "S4"):
        raise ValueError(f"bad state variant {variant}")
    times = pd.date_range(start, end, freq="15min", inclusive="left")
    bars = ctx.bars(15).set_index("decision_time")
    first = min(bars.index[0], times[0]) if len(bars) else times[0]
    g = bars.reindex(pd.date_range(first, times[-1], freq="15min"))     # complete 15 m bars, missing -> NaN
    at = g.index.get_indexer(times)
    o, h, l, c, v, tb = (g[k] for k in ("open", "high", "low", "close", "volume", "taker_buy"))
    with np.errstate(invalid="ignore", divide="ignore"):
        bar = np.column_stack([np.log(c / o) * 1e4, np.log(h / l) * 1e4, np.log1p(v), tb / v])
    window = sliding_window_view(np.vstack([np.full((SEQ_LEN - 1, bar.shape[1]), np.nan), bar]), SEQ_LEN, axis=0)
    seq = window[at].transpose(0, 2, 1).astype(np.float32)

    cols: dict[str, np.ndarray] = {}
    for target in data.TARGETS:
        cols[f"pred_{target}"] = np.log(regime._asof(ctx.regime, times, f"prediction_{target}", PREDICTION_AGE))
    m = regime._asof(ctx.regime, times, "M", PREDICTION_AGE)
    lv = regime._asof(ctx.regime, times, "L", PREDICTION_AGE)
    missing = ~(np.isfinite(m) & np.isfinite(lv))
    cols.update(M=m, L=lv, missing=missing.astype(float))

    for spec_id in SIGNAL_IDS if variant != "S4" else ():
        table, _ = build_variant(ctx, spec_id, gated=False, style="NATIVE")
        channels = side_channels(table, times, CATALOG[spec_id].cadence_min == 5)
        for name, values in zip(("event_side", "last_side", "age", "never_seen"), channels):
            cols[f"{spec_id}_{name}"] = values
    close = c.to_numpy(float)[at]
    for spec_id in OCO_IDS if variant != "S4" else ():
        table, _ = build_variant(ctx, spec_id, gated=False, style="NATIVE")
        for name, values in zip(("proposal_active", "upper_bps", "lower_bps"), oco_channels(table, times, close)):
            cols[f"{spec_id}_{name}"] = values

    metric_time = pd.DatetimeIndex(ctx.metrics.available_time).as_unit("ns")

    def metric(column: str, when: pd.DatetimeIndex) -> np.ndarray:      # available strictly before T
        return data.asof(metric_time, ctx.metrics[column].to_numpy(float), when.as_unit("ns"), METRIC_TTL)

    funding = ctx.funding.sort_values("time")
    f_time, f_rate = _ns(funding.time), funding.rate.to_numpy(float)
    rate = data.asof(pd.DatetimeIndex(f_time, tz="UTC"), f_rate, times.as_unit("ns"), None)  # settled strictly before T
    premium = data.asof(pd.DatetimeIndex(ctx.premium.available_time).as_unit("ns"), ctx.premium.premium.to_numpy(float),
                        times.as_unit("ns") + pd.Timedelta(1, "ns"), pd.Timedelta(minutes=15))   # minute closed at <= T
    ls, oi = metric("global_ls", times), metric("oi", times)
    hour = pd.Timedelta(hours=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cols.update(log_global_ls=np.log(ls), d_ls_1h=np.log(ls / metric("global_ls", times - hour)),
                    d_oi_1h=np.log(oi / metric("oi", times - hour)), log_taker_lsr=np.log(metric("taker_lsr", times)),
                    funding_bps=rate * 1e4, premium_bps=premium * 1e4)
    day = times.hour * 60 + times.minute
    cols.update(dow_sin=np.sin(2 * np.pi * (times.dayofweek + day / 1440) / 7),
                dow_cos=np.cos(2 * np.pi * (times.dayofweek + day / 1440) / 7),
                hour_sin=np.sin(2 * np.pi * day / 1440), hour_cos=np.cos(2 * np.pi * day / 1440),
                min_to_settlement=(SETTLEMENT_MIN - day % SETTLEMENT_MIN).to_numpy(float))

    summary: dict[str, pd.Series] = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        for w, name in ((4, "h1"), (16, "h4")):
            summary[f"{name}_ret"] = np.log(c / o.shift(w - 1)) * 1e4
            summary[f"{name}_range"] = np.log(h.rolling(w).max() / l.rolling(w).min()) * 1e4
            summary[f"{name}_log_volume"] = np.log1p(v.rolling(w).sum())
            summary[f"{name}_taker_share"] = tb.rolling(w).sum() / v.rolling(w).sum()
        if variant == "S3":
            r = np.log(c / c.shift()) * 1e4
            for w, name in ((96, "24h"), (672, "7d")):
                hi, lo = h.rolling(w).max(), l.rolling(w).min()
                summary[f"s3_ret_{name}"] = np.log(c / c.shift(w)) * 1e4
                summary[f"s3_rv_{name}"] = np.sqrt((r ** 2).rolling(w).sum())
                summary[f"s3_pos_{name}"] = (c - lo) / (hi - lo)
            v24, v7, v30 = v.rolling(96).sum(), v.rolling(672).sum(), v.rolling(2880).sum()
            summary["s3_volratio_24h"] = v24 / (v7 / 7)
            summary["s3_volratio_7d"] = v7 / (v30 * 7 / 30)
    cols.update({k: s.to_numpy(float)[at] for k, s in summary.items()})
    if variant == "S3":
        now = times.as_unit("ns").asi8
        total = np.r_[0.0, np.cumsum(f_rate)]
        hi_i, lo_i = np.searchsorted(f_time, now, "left"), np.searchsorted(f_time, now - pd.Timedelta(days=7).value, "left")
        with np.errstate(invalid="ignore", divide="ignore"):
            mean7 = np.where(hi_i > lo_i, (total[hi_i] - total[lo_i]) / np.maximum(hi_i - lo_i, 1), np.nan)
            cols["s3_funding_trend"] = (rate - mean7) * 1e4
            cols["s3_oi_trend_24h"] = np.log(oi / metric("oi", times - pd.Timedelta(hours=24)))

    if variant == "S4":
        now = times.as_unit("ns").asi8
        for w, minutes in S4_WINDOWS.items():
            b = ctx.bars(minutes)
            k = np.searchsorted(_ns(b.decision_time), now, side="right") - 1     # last bar closed at or before T
            with np.errstate(invalid="ignore", divide="ignore"):
                frame = s4_indicators(b)
            cols.update({f"{w}_{name}": _pick(x, k, np.nan) for name, x in frame.items()})
        b = ctx.bars(15)
        k = np.searchsorted(_ns(b.decision_time), now, side="right") - 1
        with np.errstate(invalid="ignore", divide="ignore"):
            cols["vwap_dev"] = _pick(b.close / indicators.vwap_utc(b) - 1, k, np.nan)
            pct = ctx.metrics.global_ls.rolling(DAY30["metrics"], min_periods=DAY30["metrics"] // 4).rank(pct=True)
            cols["ls_pct30d"] = data.asof(metric_time, pct.to_numpy(float), times.as_unit("ns"), METRIC_TTL)
            for lag in ("4h", "1d"):
                cols[f"d_ls_{lag}"] = np.log(ls / metric("global_ls", times - pd.Timedelta(lag)))
            z = indicators.zscore_past(ctx.premium.premium.astype(float), DAY30["premium"], DAY30["premium"] // 4)
            cols["premium_z30d"] = data.asof(pd.DatetimeIndex(ctx.premium.available_time).as_unit("ns"), z.to_numpy(float),
                                             times.as_unit("ns") + pd.Timedelta(1, "ns"), pd.Timedelta(minutes=15))
            z = indicators.zscore_past(pd.Series(f_rate), DAY30["funding"], DAY30["funding"] // 4)
            cols["funding_z30d"] = data.asof(pd.DatetimeIndex(f_time, tz="UTC"), z.to_numpy(float), times.as_unit("ns"), None)

    for name in list(cols):
        cols[name] = np.where(np.isfinite(cols[name]), cols[name], np.nan)
    for name in [k for k in cols if is_scaled(k) and not k.endswith(_UNMASKED)]:
        cols[f"{name}__nan"] = np.isnan(cols[name]).astype(float)
    cols["seq__nan"] = np.isnan(seq).any(axis=(1, 2)).astype(float)
    names = list(cols)
    static = np.column_stack([cols[k] for k in names]).astype(np.float32)
    return StateStore(times.as_unit("ns").asi8, seq, static, missing, names, variant)


@dataclass(frozen=True)
class Normalizer:
    static_mean: np.ndarray
    static_std: np.ndarray
    seq_mean: np.ndarray
    seq_std: np.ndarray

    def apply(self, store: StateStore) -> StateStore:
        """Standardize continuous channels, then NaN -> 0 (the __nan channels keep the mask)."""
        static = (store.static.astype(np.float64) - self.static_mean) / self.static_std
        seq = (store.seq.astype(np.float64) - self.seq_mean) / self.seq_std
        return dataclasses.replace(store, static=np.nan_to_num(static, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32),
                                   seq=np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32))


def _moments(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # all-NaN channels
        mean, std = np.nanmean(x, axis=0), np.nanstd(x, axis=0)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    return mean, np.where(np.isfinite(std) & (std > 0), std, 1.0)


def fit_normalizer(store: StateStore, train_end: pd.Timestamp) -> Normalizer:
    """C9: mean/std over rows TRAIN_START <= T <= train_end only (warm-up and later rows never enter)."""
    rows = (store.times >= TRAIN_START.value) & (store.times <= pd.Timestamp(train_end).value)
    mean, std = _moments(store.static[rows].astype(np.float64))
    scaled = np.array([is_scaled(name) for name in store.feature_names])
    seq_mean, seq_std = _moments(store.seq[rows].astype(np.float64).reshape(-1, store.seq.shape[2]))
    return Normalizer(np.where(scaled, mean, 0.0), np.where(scaled, std, 1.0), seq_mean, seq_std)


def _input_hash(ctx: Context) -> dict:
    root = Path(__file__).resolve().parents[1]
    out = {"state_py": provenance.file_sha256(Path(__file__)),
           "sim_py": provenance.tree_sha256(root / "sim", "**/*.py")["sha256"]}
    for name in ("minutes", "metrics", "premium", "funding", "regime"):
        out[name] = str(int(pd.util.hash_pandas_object(getattr(ctx, name), index=False).sum()))
    return out


def cached_state_store(ctx: Context, start: pd.Timestamp, end: pd.Timestamp, variant: str,
                       root: Path = CACHE_ROOT) -> StateStore:
    """build_state_store through the hash-keyed parquet store (key: range, variant, code and input hashes)."""
    def build() -> pd.DataFrame:
        s = build_state_store(ctx, start, end, variant)
        seq = {f"seq{j}_{name}": s.seq[:, j, k] for j in range(SEQ_LEN) for k, name in enumerate(SEQ_NAMES)}
        return pd.DataFrame({"time": s.times, "mask_missing": s.mask_missing,
                             **{name: s.static[:, k] for k, name in enumerate(s.feature_names)}, **seq})
    frame = feature_store.get_or_build(root, f"rl_state_{variant}", {"start": str(start), "end": str(end)},
                                       _input_hash(ctx), build)
    seq_cols = [f"seq{j}_{name}" for j in range(SEQ_LEN) for name in SEQ_NAMES]
    names = [k for k in frame.columns if k not in ("time", "mask_missing") and k not in set(seq_cols)]
    seq = frame[seq_cols].to_numpy(np.float32).reshape(len(frame), SEQ_LEN, len(SEQ_NAMES))
    return StateStore(frame.time.to_numpy(np.int64), seq, frame[names].to_numpy(np.float32),
                      frame.mask_missing.to_numpy(bool), names, variant)
