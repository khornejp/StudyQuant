"""Live R2-44 w730_raw PatchTST: same weekly 730-day retrain procedure, predictions every 15 minutes.

Training reuses out/run_k45_vol_detector_r2_44_window.py (fit_fold) unchanged; only the inputs are extended past
2026-06-30 with the paper collector's tables (and the frozen Q3 premium archive). Research artefacts are read only.
"""
from __future__ import annotations
import importlib.util, logging, sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger(__name__)
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
MINUTE_TABLE = "detector_predictions_1m"
VERSIONED_TABLE = "detector_prediction_versions"
REVISION_TABLE = "detector_prediction_revisions"
FRESH_HEADS = ("30m", "1h", "4h")      # refreshed every minute (detector_refresh_check: better); 12h/24h held from 15 m


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
    # R2-54: the stored, causally available interval (no 8 h constant); unknown -> interval_missing=1 and
    # interval_hours=0, which attach_exogenous treats as an expired event (funding_missing=1, rate 0).
    has_events = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='funding_events'").fetchone() is not None
    funding = frame("SELECT f.rate, f.raw_calc_time, " + (
        "(SELECT MAX(e.interval_hours) FROM funding_events e WHERE e.funding_time=f.raw_calc_time)"
        if has_events else "NULL") + " AS interval_hours FROM funding f")
    interval = pd.to_numeric(funding.interval_hours, errors="coerce")
    funding = pd.DataFrame({"publish_time": pd.to_datetime(funding.raw_calc_time, utc=True, format="mixed"),
                            "rate": funding.rate.astype(float), "interval_hours": interval.fillna(0.0),
                            "interval_missing": interval.isna().astype(int)})
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


def recent_data(connection, now: pd.Timestamp, every_minute: bool = False):
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
    origins = pd.DatetimeIndex((bars[0] if every_minute else r.aggregate(_complete(market, "15min"), "15min")).decision_time)
    return SimpleNamespace(bars=bars, arrays=arrays, origins=origins)


def ensure_table(connection) -> None:
    """Legacy TABLE: one immutable row per origin (timestamp = prediction_ts), read by all current readers; the
    versioned (model_id, prediction_ts, version) history is VERSIONED_TABLE. R2-54 availability split, additive:
    logical_available_at = causal availability (the origin: its data cutoff, served by a checkpoint retrained <= it);
    written_at = physical write time; available_at = the live-usable time max(logical, written) = written_at, kept
    with its pre-R2-54 meaning for running readers. Research replay reads logical_available_at only."""
    columns = ", ".join(f"prediction_{t} REAL" for t in target_names())
    for table in (TABLE, MINUTE_TABLE):
        connection.execute(f"CREATE TABLE IF NOT EXISTS {table} (timestamp TEXT PRIMARY KEY, retrain_time TEXT, "
                           f"{columns}, created_at TEXT)")
        have = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for name in ("available_at", "model_id", "source", "logical_available_at", "written_at"):
            if name not in have:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} TEXT")
    # rows written before these columns existed were the 2026-07-01.. backfill
    connection.execute(f"UPDATE {TABLE} SET available_at=created_at, model_id=retrain_time, source='backfill' "
                       "WHERE available_at IS NULL")
    for table in (TABLE, MINUTE_TABLE):     # rows of pre-split writers: created_at was their write time
        connection.execute(f"UPDATE {table} SET logical_available_at=timestamp, written_at=created_at "
                           "WHERE written_at IS NULL")
    # grid rows: no DELETE, and a stored (non-NULL) value never changes; corrections = new model_id/version elsewhere
    stored = " OR ".join(f"(OLD.{c} IS NOT NULL AND OLD.{c} IS NOT NEW.{c})" for c in
                         ("timestamp", "retrain_time", *(f"prediction_{t}" for t in target_names()), "created_at",
                          "available_at", "model_id", "source", "logical_available_at", "written_at"))
    connection.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_update BEFORE UPDATE ON {TABLE} WHEN {stored} "
                       "BEGIN SELECT RAISE(ABORT, 'detector predictions are immutable'); END")
    connection.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_delete BEFORE DELETE ON {TABLE} "
                       "BEGIN SELECT RAISE(ABORT, 'detector predictions are immutable'); END")
    _ensure_versions(connection, columns)


def _ensure_versions(connection, columns: str) -> None:
    """Frozen R2-54 rule, additive: VERSIONED_TABLE keeps one immutable row per (model_id, prediction_ts, version);
    a differing write is a new version / another model's row plus a REVISION_TABLE record, never dropped. The legacy
    TABLE (one row per origin, read by every current reader) is dual-written; rows of pre-R2-54 / old-code writers
    are mirrored here as version 1 on every call."""
    connection.execute(f"CREATE TABLE IF NOT EXISTS {VERSIONED_TABLE} (model_id TEXT NOT NULL, "
                       "prediction_ts TEXT NOT NULL, version INTEGER NOT NULL, retrain_time TEXT, "
                       f"{columns}, logical_available_at TEXT, written_at TEXT, source TEXT, "
                       "PRIMARY KEY(model_id, prediction_ts, version))")
    connection.execute(f"CREATE TABLE IF NOT EXISTS {REVISION_TABLE} (prediction_ts TEXT NOT NULL, "
                       "model_id TEXT NOT NULL, version INTEGER NOT NULL, kind TEXT NOT NULL, "
                       "kept_model_id TEXT, kept_version INTEGER, detected_at TEXT NOT NULL)")
    for name in (VERSIONED_TABLE, REVISION_TABLE):
        connection.execute(f"CREATE TRIGGER IF NOT EXISTS {name}_no_update BEFORE UPDATE ON {name} "
                           "BEGIN SELECT RAISE(ABORT, 'detector predictions are immutable'); END")
        connection.execute(f"CREATE TRIGGER IF NOT EXISTS {name}_no_delete BEFORE DELETE ON {name} "
                           "BEGIN SELECT RAISE(ABORT, 'detector predictions are immutable'); END")
    names = ", ".join(f"prediction_{t}" for t in target_names())
    connection.execute(f"INSERT OR IGNORE INTO {VERSIONED_TABLE} (model_id, prediction_ts, version, retrain_time, "
                       f"{names}, logical_available_at, written_at, source) SELECT COALESCE(model_id, retrain_time), "
                       f"timestamp, 1, retrain_time, {names}, logical_available_at, written_at, source FROM {TABLE} "
                       f"WHERE NOT EXISTS (SELECT 1 FROM {VERSIONED_TABLE} v WHERE v.prediction_ts={TABLE}.timestamp "
                       f"AND v.model_id=COALESCE({TABLE}.model_id, {TABLE}.retrain_time))")


def _write_versions(connection, rows: list[tuple], now: str) -> None:
    """rows = legacy-column tuples; see _ensure_versions."""
    names = [f"prediction_{t}" for t in target_names()]
    k = len(names)
    for row in rows:
        stamp, retrain, values = row[0], row[1], tuple(None if v != v else v for v in row[2:2 + k])   # NaN = NULL
        model, source, logical, written = row[2 + k + 2], row[2 + k + 3], row[2 + k + 4], row[2 + k + 5]
        kept = connection.execute(f"SELECT model_id, {', '.join(names)} FROM {TABLE} WHERE timestamp=?",
                                  (stamp,)).fetchone()
        last = connection.execute(f"SELECT version, {', '.join(names)} FROM {VERSIONED_TABLE} WHERE model_id=? AND "
                                  "prediction_ts=? ORDER BY version DESC LIMIT 1", (model, stamp)).fetchone()
        if last is not None and tuple(last[1:]) == values:
            continue
        version = 1 if last is None else last[0] + 1
        connection.execute(f"INSERT INTO {VERSIONED_TABLE} (model_id, prediction_ts, version, retrain_time, "
                           f"{', '.join(names)}, logical_available_at, written_at, source) VALUES "
                           f"({', '.join('?' * (k + 7))})", (model, stamp, version, retrain, *values, logical, written,
                                                             source))
        if last is not None:
            connection.execute(f"INSERT INTO {REVISION_TABLE} VALUES (?,?,?,?,?,?,?)",
                               (stamp, model, version, "correction", model, last[0], now))
        if kept is not None and (kept[0] != model or tuple(kept[1:]) != values):
            log.warning("detector prediction %s: legacy row %s kept; %s v%d stored in %s", stamp, kept[0], model,
                        version, VERSIONED_TABLE)
            connection.execute(f"INSERT INTO {REVISION_TABLE} VALUES (?,?,?,?,?,?,?)",
                               (stamp, model, version, "legacy_kept_other_row", kept[0], None, now))


def write_predictions(connection, origins: pd.DatetimeIndex, retrain: pd.Timestamp, values: np.ndarray,
                      source: str = "live", table: str = TABLE) -> int:
    """Legacy table: INSERT OR IGNORE (a later model never overwrites an origin's prediction); the 15 m grid is
    also written to VERSIONED_TABLE, where nothing differing is dropped. Returns legacy rows written."""
    ensure_table(connection)
    names = [f"prediction_{t}" for t in target_names()]
    now = pd.Timestamp.now(tz="UTC").isoformat()
    columns = ["timestamp", "retrain_time", *names, "created_at", "available_at", "model_id", "source",
               "logical_available_at", "written_at"]
    rows = [(o.isoformat(), retrain.isoformat(), *map(float, v), now, now, f"w730_raw_{retrain:%Y%m%d}", source,
             o.isoformat(), now) for o, v in zip(origins, values)]
    if table == TABLE:          # before the legacy insert, so a differing row is compared with the kept one
        _write_versions(connection, rows, now)
    before = connection.total_changes
    connection.executemany(f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                           rows)
    return connection.total_changes - before


def mix_minute(values: np.ndarray, held: np.ndarray) -> np.ndarray:
    """Fresh values for FRESH_HEADS, the held 15-minute values for the longer heads."""
    out = held.copy()
    fresh = [j for j, name in enumerate(target_names()) if name.split("_", 1)[1] in FRESH_HEADS]
    out[:, fresh] = values[:, fresh]
    return out


def read_predictions(connection, table: str = TABLE) -> pd.DataFrame:
    ensure_table(connection)
    frame = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY timestamp", connection)
    for c in ("timestamp", "retrain_time", "available_at", "logical_available_at", "written_at"):
        frame[c] = pd.to_datetime(frame[c], utc=True, format="mixed")
    return frame.drop(columns="created_at")


__all__ = ["build_data", "checkpoint_path", "combined_inputs", "predict", "read_predictions", "recent_data",
           "retrain_times", "train", "write_predictions"]
