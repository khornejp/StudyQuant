"""Live R2-44 w730_raw PatchTST: same weekly 730-day retrain procedure, predictions every 15 minutes.

Training reuses out/run_k45_vol_detector_r2_44_window.py (fit_fold) unchanged; only the inputs are extended past
2026-06-30 with the paper collector's tables (and the frozen Q3 premium archive). Research artefacts are read only.
"""
from __future__ import annotations
import importlib.util, sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
R44_PATH = ROOT / "out/run_k45_vol_detector_r2_44_window.py"
RESEARCH_CHECKPOINT = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw/HOLD_B/fold_0025.pt"
Q3_PREMIUM = ROOT / "artifacts/hold_a_2026q3/premium_index"
LIVE_DIR = ROOT / "artifacts/live/detector"
FIRST_RETRAIN = pd.Timestamp("2026-06-25", tz="UTC")       # last research fold (HOLD_B fold 25)
CADENCE = pd.Timedelta(days=7)
LABEL_LAG = pd.Timedelta(hours=25)       # fit_fold needs >= 1 labelled prediction row after retrain_time
ARCHIVE_END = pd.Timestamp("2026-07-01", tz="UTC")
PREDICT_DAYS = 20                        # > 14-day 1 h lookback
TABLE = "detector_predictions"


@lru_cache(maxsize=1)
def r44():
    spec = importlib.util.spec_from_file_location("r44_window", R44_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules["r44_window"] = module
    spec.loader.exec_module(module)
    return module


def candidate() -> dict:
    return next(c for c in r44().CANDIDATES if c["name"] == "w730_raw")


def target_names() -> tuple[str, ...]:
    return tuple(r44().r.TARGETS)


def retrain_times(now: pd.Timestamp) -> list[pd.Timestamp]:
    """Research schedule continued: 2026-06-25 + 7 k days, trainable once labels exist (now >= t + 25 h)."""
    out, t = [], FIRST_RETRAIN
    while t + LABEL_LAG <= now:
        out.append(t); t += CADENCE
    return out


# ---------- inputs in the R2-43 formats ----------

def live_inputs(connection, since: pd.Timestamp | None = None) -> tuple[pd.DataFrame, ...]:
    def frame(sql: str) -> pd.DataFrame:
        return pd.read_sql_query(sql, connection)
    where = "" if since is None else f" WHERE {{col}} >= '{since.isoformat()}'"
    market = frame("SELECT open_time, open, high, low, close, volume, quote_volume, number_of_trades, "
                   "taker_buy_base_volume FROM klines_1m" + where.format(col="open_time") + " ORDER BY open_time")
    market["open_time"] = pd.to_datetime(market.open_time, utc=True).astype("datetime64[ns, UTC]")
    ls = frame("SELECT timestamp, global_ls_account, source FROM ls_ratio" + where.format(col="timestamp"))
    ls_time = pd.to_datetime(ls.timestamp, utc=True).astype("datetime64[ns, UTC]")
    # R2-43 reads create_time and allows use after +5 min; REST rows are stamped at availability already
    create = ls_time - pd.to_timedelta(np.where(ls.source.eq("rest"), 5, 0), unit="min")
    metrics = pd.DataFrame({"create_time": create, "global_ls": ls.global_ls_account.astype(float)})
    premium = frame("SELECT open_time, premium_index FROM premium_1m" + where.format(col="open_time"))
    p_open = pd.to_datetime(premium.open_time, utc=True).astype("datetime64[ns, UTC]")
    premium = pd.DataFrame({"open_time": p_open, "close_time": p_open + pd.Timedelta(milliseconds=59_999),
                            "premium": premium.premium_index.astype(float)})
    funding = frame("SELECT time, rate, raw_calc_time FROM funding")
    funding = pd.DataFrame({"publish_time": pd.to_datetime(funding.raw_calc_time, utc=True, format="mixed"),
                            "rate": funding.rate.astype(float), "interval_hours": 8.0})
    return market, metrics, premium, funding


@lru_cache(maxsize=1)
def _archive_inputs() -> tuple[pd.DataFrame, ...]:
    r = r44().r
    premium_q3 = _load_premium(Q3_PREMIUM)
    return r.load_market(), r.load_metrics(), pd.concat([r.load_premium(), premium_q3], ignore_index=True), r.load_funding()


def _load_premium(root: Path) -> pd.DataFrame:
    r = r44().r
    saved = r.PREMIUM
    try:
        r.PREMIUM = root
        return r.load_premium()
    finally:
        r.PREMIUM = saved


def _merge(archive: pd.DataFrame, live: pd.DataFrame, key: str) -> pd.DataFrame:
    frame = pd.concat([archive, live], ignore_index=True)
    frame[key] = pd.to_datetime(frame[key], utc=True).astype("datetime64[ns, UTC]")
    return frame.drop_duplicates(key, keep="last").sort_values(key).reset_index(drop=True)


def combined_inputs(connection) -> tuple[pd.DataFrame, ...]:
    """Frozen archives up to 2026-06-30 plus the collector's tables afterwards."""
    a_market, a_metrics, a_premium, a_funding = _archive_inputs()
    l_market, l_metrics, l_premium, l_funding = live_inputs(connection)
    market = _merge(a_market, l_market.loc[l_market.open_time >= ARCHIVE_END], "open_time")
    market = _complete(market, "1h")
    if not np.all(np.diff(market.open_time.array.asi8) == pd.Timedelta(minutes=1).value):
        raise ValueError("combined market has missing minutes")
    return (market, _merge(a_metrics, l_metrics.loc[l_metrics.create_time >= ARCHIVE_END - pd.Timedelta(minutes=5)], "create_time"),
            _merge(a_premium, l_premium, "open_time"), _merge(a_funding, l_funding, "publish_time"))


def build_data(market, metrics, premium, funding, with_targets: bool = True):
    """r44.Data built from the given frames (R2-43 load_dataset with injected loaders)."""
    module, r = r44(), r44().r
    saved = (r.load_market, r.load_metrics, r.load_premium, r.load_funding, r.check_targets)
    r.load_market, r.load_metrics = (lambda: market), (lambda: metrics)
    r.load_premium, r.load_funding = (lambda: premium), (lambda: funding)
    r.check_targets = lambda *a, **k: None     # live tail has no complete labels
    try:
        if with_targets:
            return module.Data()
        base = r.load_dataset()
        return base
    finally:
        r.load_market, r.load_metrics, r.load_premium, r.load_funding, r.check_targets = saved


# ---------- train / predict ----------

def checkpoint_path(retrain: pd.Timestamp) -> Path:
    return RESEARCH_CHECKPOINT if retrain == FIRST_RETRAIN else LIVE_DIR / f"w730_raw_{retrain:%Y%m%d}.pt"


def train(data, retrain: pd.Timestamp, device) -> tuple[dict, pd.DataFrame]:
    """One weekly fold exactly as R2-44 fit_fold (prediction rows: the labelled part of the following week)."""
    end = min(retrain + CADENCE, pd.Timestamp(data.origins[-1]) - pd.Timedelta(hours=24))
    return r44().fit_fold(data, candidate(), retrain, end, device)


def predict(data, checkpoint: dict, origins: pd.DatetimeIndex, device) -> np.ndarray:
    """bps predictions [len(origins), 15] from a saved fold; origins must be in data.origins."""
    import torch
    r = r44().r
    config = r44().CONFIG
    model = r.MultiResolutionPatchTST(config, tuple(a.shape[1] for a in data.arrays)).to(device)
    model.load_state_dict(checkpoint["model_state"])
    rows = pd.DatetimeIndex(data.origins).get_indexer(origins)
    if (rows < 0).any():
        raise ValueError("origin not in dataset")
    endpoints = r.endpoint_indices(data.bars, origins)
    raw = r._predict(model, data, rows, endpoints, config, checkpoint["means"], checkpoint["stds"], device)
    return np.expm1(raw)


def _complete(minutes: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Drop the trailing incomplete bar of `frequency` (R2-43 aggregate refuses incomplete bars)."""
    end = (minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)).floor(frequency)
    return minutes.loc[minutes.open_time < end].reset_index(drop=True)


def recent_data(connection, now: pd.Timestamp):
    """Feature-only inputs over the last PREDICT_DAYS of collector data; each resolution keeps its complete bars,
    so an origin sees exactly the bars the research dataset would give it."""
    from types import SimpleNamespace
    r = r44().r
    since = (now - pd.Timedelta(days=PREDICT_DAYS)).floor("D")
    market, metrics, premium, funding = live_inputs(connection, since)
    archive_premium = _archive_inputs()[2]
    premium = _merge(archive_premium.loc[archive_premium.open_time >= since], premium, "open_time")
    metrics = metrics.sort_values("create_time").reset_index(drop=True)
    funding = funding.sort_values("publish_time").reset_index(drop=True)
    bars = [r.aggregate(_complete(market, f), f) for f in ("1min", "5min", "1h")]
    arrays = r.attach_exogenous(bars, metrics, premium, funding)
    origins = pd.DatetimeIndex(r.aggregate(_complete(market, "15min"), "15min").decision_time)
    return SimpleNamespace(bars=bars, arrays=arrays, origins=origins)


def ensure_table(connection) -> None:
    """Predictions are immutable: one row per origin; available_at = commit time (live) or write time (backfill)."""
    columns = ", ".join(f"prediction_{t} REAL" for t in target_names())
    connection.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (timestamp TEXT PRIMARY KEY, retrain_time TEXT, "
                       f"{columns}, created_at TEXT)")
    have = {row[1] for row in connection.execute(f"PRAGMA table_info({TABLE})")}
    for name in ("available_at", "model_id", "source"):
        if name not in have:
            connection.execute(f"ALTER TABLE {TABLE} ADD COLUMN {name} TEXT")
    # rows written before these columns existed were the 2026-07-01.. backfill
    connection.execute(f"UPDATE {TABLE} SET available_at=created_at, model_id=retrain_time, source='backfill' "
                       "WHERE available_at IS NULL")


def write_predictions(connection, origins: pd.DatetimeIndex, retrain: pd.Timestamp, values: np.ndarray,
                      source: str = "live") -> int:
    """INSERT OR IGNORE: a later model never overwrites an origin's prediction."""
    ensure_table(connection)
    names = [f"prediction_{t}" for t in target_names()]
    now = pd.Timestamp.now(tz="UTC").isoformat()
    columns = ["timestamp", "retrain_time", *names, "created_at", "available_at", "model_id", "source"]
    rows = [(o.isoformat(), retrain.isoformat(), *map(float, v), now, now, f"w730_raw_{retrain:%Y%m%d}", source)
            for o, v in zip(origins, values)]
    before = connection.total_changes
    connection.executemany(f"INSERT OR IGNORE INTO {TABLE} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                           rows)
    return connection.total_changes - before


def read_predictions(connection) -> pd.DataFrame:
    ensure_table(connection)
    frame = pd.read_sql_query(f"SELECT * FROM {TABLE} ORDER BY timestamp", connection)
    for c in ("timestamp", "retrain_time", "available_at"):
        frame[c] = pd.to_datetime(frame[c], utc=True, format="mixed")
    return frame.drop(columns="created_at")


__all__ = ["build_data", "checkpoint_path", "combined_inputs", "predict", "read_predictions", "recent_data",
           "retrain_times", "train", "write_predictions"]
