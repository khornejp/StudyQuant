from __future__ import annotations
import zipfile
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARKET_PATH = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
METRICS_DIR = ROOT / "artifacts/metrics"
PREMIUM_DIR = ROOT / "artifacts/premium_index_2020_2026h1"
PREDICTIONS_DIR = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw"
TARGETS = tuple(f"{k}_{h}" for k in ("range", "rv", "exc") for h in ("30m", "1h", "4h", "12h", "24h"))
MINUTE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume",
                  "number_of_trades", "taker_buy_base_volume"]

def validate_minutes(frame: pd.DataFrame) -> pd.DataFrame:
    step = np.diff(frame.open_time.array.asi8)
    if len(step) and not np.all(step == 60_000_000_000):
        raise ValueError("market has missing minutes; interpolation is forbidden")
    if not (frame.high >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise ValueError("high below open/close/low")
    return frame

def _file_day(path: Path) -> pd.Timestamp:
    """Archive files end with -YYYY-MM-DD.zip."""
    return pd.Timestamp(Path(path).stem[-10:], tz="UTC")


def archive_files(root: Path, end: pd.Timestamp | None = None) -> list[Path]:
    files = sorted(Path(root).glob("*.zip"))
    return files if end is None else [f for f in files if _file_day(f) < end]


def load_minutes(path: Path = MARKET_PATH, end: pd.Timestamp | None = None) -> pd.DataFrame:
    filters = None if end is None else [("open_time", "<", pd.Timestamp(end).to_pydatetime())]
    frame = pd.read_parquet(path, columns=MINUTE_COLUMNS, filters=filters)
    frame["open_time"] = pd.to_datetime(frame.open_time, utc=True).astype("datetime64[ns, UTC]")
    return validate_minutes(frame.sort_values("open_time").reset_index(drop=True))

def _csv(path: Path, **kwargs) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one csv in {path}")
        return pd.read_csv(archive.open(names[0]), **kwargs)

def load_metrics(root: Path = METRICS_DIR, end: pd.Timestamp | None = None) -> pd.DataFrame:
    frames = [_csv(p) for p in archive_files(root, end)]
    raw = pd.concat(frames, ignore_index=True)
    create = pd.to_datetime(raw.create_time, utc=True).astype("datetime64[ns, UTC]")
    result = pd.DataFrame({
        "available_time": create + pd.Timedelta(minutes=5),
        "global_ls": pd.to_numeric(raw.count_long_short_ratio, errors="coerce"),
        "top_ls": pd.to_numeric(raw.count_toptrader_long_short_ratio, errors="coerce"),
        "oi": pd.to_numeric(raw.sum_open_interest, errors="coerce"),
        "oi_value": pd.to_numeric(raw.sum_open_interest_value, errors="coerce"),
        "taker_lsr": pd.to_numeric(raw.sum_taker_long_short_vol_ratio, errors="coerce")})
    return result.drop_duplicates("available_time", keep="last").sort_values("available_time").reset_index(drop=True)

def load_premium(root: Path = PREMIUM_DIR, end: pd.Timestamp | None = None) -> pd.DataFrame:
    columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
               "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    frames = []
    for path in archive_files(root, end):
        raw = _csv(path, header=None)
        if str(raw.iloc[0, 0]).lower() == "open_time":
            raw = raw.iloc[1:]
        raw.columns = columns
        frames.append(raw[["close_time", "close"]])
    raw = pd.concat(frames, ignore_index=True)
    result = pd.DataFrame({
        "available_time": pd.to_datetime(pd.to_numeric(raw.close_time), unit="ms", utc=True) + pd.Timedelta(milliseconds=1),
        "premium": pd.to_numeric(raw.close, errors="raise")})
    return result.drop_duplicates("available_time", keep="last").sort_values("available_time").reset_index(drop=True)

def validate_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    if (frame.retrain_time > frame.timestamp).any():
        raise ValueError("retrain_time after timestamp: future model used")
    if (frame.timestamp.dt.minute % 15 != 0).any() or (frame.timestamp.dt.second != 0).any():
        raise ValueError("prediction timestamp off the 15-minute grid")
    if frame.timestamp.duplicated().any():
        raise ValueError("duplicate prediction timestamp")
    return frame

SEGMENT_STARTS = {"DEV_FRONT": "2022-03-01", "DEV_BACK": "2024-01-01", "HOLD_B": "2026-01-01"}


def load_predictions(root: Path = PREDICTIONS_DIR, end: pd.Timestamp | None = None) -> pd.DataFrame:
    segments = [s for s, start in SEGMENT_STARTS.items() if end is None or pd.Timestamp(start, tz="UTC") < end]
    paths = sorted(p for s in segments for p in (Path(root) / s).glob("fold_*_predictions.parquet"))
    columns = ["timestamp", "retrain_time", "segment"] + [f"prediction_{t}" for t in TARGETS]
    frame = pd.concat([pd.read_parquet(p, columns=columns) for p in paths], ignore_index=True)
    for c in ("timestamp", "retrain_time"):
        frame[c] = pd.to_datetime(frame[c], utc=True)
    if end is not None:
        frame = frame.loc[frame.timestamp < end]
    return validate_predictions(frame.sort_values("timestamp").reset_index(drop=True))


def prediction_coverage(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Expected 15-minute origins in [start, end) vs present; missing days listed (fail-closed callers check it)."""
    expected = pd.date_range(start, end, freq="15min", tz="UTC", inclusive="left")
    present = pd.DatetimeIndex(frame.timestamp)
    missing = expected.difference(present)
    return {"expected": int(len(expected)), "present": int(expected.isin(present).sum()),
            "missing": int(len(missing)), "missing_days": sorted({str(t.date()) for t in missing}),
            "retrain_after_timestamp": int((frame.retrain_time > frame.timestamp).sum())}

def asof(values_time: pd.DatetimeIndex, values: np.ndarray, decisions: pd.DatetimeIndex,
         ttl: pd.Timedelta | None) -> np.ndarray:
    position = np.searchsorted(values_time.asi8, decisions.asi8, side="left") - 1
    out = np.full(len(decisions), np.nan)
    ok = position >= 0
    out[ok] = np.asarray(values, float)[position[ok]]
    if ttl is not None:
        age = np.full(len(decisions), np.iinfo(np.int64).max)
        age[ok] = decisions.asi8[ok] - values_time.asi8[position[ok]]
        out[age > ttl.value] = np.nan
    return out
