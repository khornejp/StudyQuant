"""Zero-fit BBO, bounce-corrected trade, and raw-trade target comparison."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import shutil
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import psutil


PLAN = Path("ZERO_FIT_TARGET_EQUIVALENCE_2026-09-25.md")
PLAN_SHA256 = "97de0c5fa481a64a84d80d6d432e6643b63b25d5bf5aab23d1b75df749fee15b"
BOOK_ROOT = Path("artifacts/bookticker")
TRADE_ROOT = Path("artifacts/aggtrades")
SPREAD_ARTIFACT = Path("artifacts/spread_features_1m.parquet")
OUTPUT = Path("out/zero_fit_target_equivalence_20260925_r1")
START = pd.Timestamp("2023-05-16 11:49:00", tz="UTC")
STOP = pd.Timestamp("2024-04-01 06:46:00", tz="UTC")
TICK = 0.1
OFFSETS = np.array([1.0, 2.0, 5.0, 10.0])
ARMS = ("bbo", "bounce", "raw")
PAIRS = (("bbo", "bounce"), ("bbo", "raw"), ("bounce", "raw"))
MAX_AGE_MS = 1_000
FILL_WINDOW_MS = 60_000
MARKOUT_MS = 60_000
BOUNCE_WINDOW_MS = 60_000
BOUNCE_MAX_GAP_MS = 100
BOUNCE_MIN_PAIRS = 20
CSV_CHUNK = 500_000
MAX_PART_ROWS = 5_000_000
RSS_LIMIT = 3 * 1024 ** 3
MIN_FREE_DISK = 100 * 1024 ** 3
BBO_BEFORE_MS = 1_000
BBO_AFTER_MS = 60_000
TRADE_BEFORE_MS = 60_100
TRADE_AFTER_MS = 61_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path: Path, value: object) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                                  allow_nan=False) + "\n", encoding="utf-8")
    os.replace(partial, path)


def completed_parquet(path: Path) -> bool:
    if (not path.is_file() or path.with_suffix(path.suffix + ".partial").exists()
            or not (path.parent / "_SUCCESS").is_file()):
        return False
    try:
        pq.ParquetFile(path).metadata
    except Exception:
        return False
    return True


def _atomic_marker(path: Path, text: str = "ok\n") -> None:
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="ascii")
    os.replace(partial, path)


def _write_parquet_parts(frame: pd.DataFrame, directory: Path, stem: str) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    starts = range(0, len(frame), MAX_PART_ROWS) if len(frame) else [0]
    for number, left in enumerate(starts):
        part = frame.iloc[left:left + MAX_PART_ROWS]
        path = directory / f"{stem}-{number:05d}.parquet"
        partial = path.with_suffix(path.suffix + ".partial")
        part.to_parquet(partial, index=False, compression="zstd")
        metadata = pq.ParquetFile(partial).metadata
        if metadata.num_rows != len(part):
            raise ValueError(f"Parquet footer row mismatch: {partial}")
        os.replace(partial, path)
        records.append({"path": path.name, "rows": len(part), "bytes": path.stat().st_size,
                        "sha256": sha256(path)})
    return records


class RssGuard:
    def __init__(self, limit: int = RSS_LIMIT):
        self.limit = limit
        self.process = psutil.Process()
        self.maximum = 0
        self.block_peak = 0
        self.exceeded = False
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._monitor, daemon=True)

    def _monitor(self):
        while not self.stop_event.wait(.1):
            rss = self.process.memory_info().rss
            self.maximum = max(self.maximum, rss)
            self.block_peak = max(self.block_peak, rss)
            self.exceeded |= rss > self.limit

    def __enter__(self):
        self.thread.start()
        return self

    def begin_block(self):
        self.block_peak = self.process.memory_info().rss

    def end_block(self, label: str):
        rss = self.process.memory_info().rss
        self.maximum = max(self.maximum, self.block_peak, rss)
        print(f"RSS {label}: peak={self.block_peak / 1024**3:.3f} GiB "
              f"running_max={self.maximum / 1024**3:.3f} GiB", flush=True)
        if self.exceeded or self.block_peak > self.limit or rss > self.limit:
            raise MemoryError(f"RSS ceiling exceeded: {self.maximum / 1024**3:.3f} GiB > 3 GiB")

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join()


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def ceil_tick(value):
    scaled = np.asarray(value, dtype=float) / TICK
    return np.round(np.ceil(np.nextafter(scaled, -np.inf)) * TICK, 1)


def floor_tick(value):
    scaled = np.asarray(value, dtype=float) / TICK
    return np.round(np.floor(np.nextafter(scaled, np.inf)) * TICK, 1)


def epoch_ms(index: pd.DatetimeIndex) -> np.ndarray:
    return index.to_numpy(dtype="datetime64[ms]").astype(np.int64)


@dataclass
class Trades:
    times: np.ndarray
    ids: np.ndarray
    prices: np.ndarray
    signs: np.ndarray
    pair_times: np.ndarray
    pair_values: np.ndarray


def pair_events(times: np.ndarray, prices: np.ndarray, signs: np.ndarray):
    gap = times[1:] - times[:-1]
    keep = (signs[1:] != signs[:-1]) & (gap >= 0) & (gap <= BOUNCE_MAX_GAP_MS)
    values = signs[1:] * 10_000.0 * (prices[1:] / prices[:-1] - 1.0)
    return times[1:][keep], values[keep]


def bounce_estimate(pair_times: np.ndarray, pair_values: np.ndarray, query_ms: int):
    left = np.searchsorted(pair_times, query_ms - BOUNCE_WINDOW_MS, side="left")
    right = np.searchsorted(pair_times, query_ms, side="left")
    count = int(right - left)
    if count < BOUNCE_MIN_PAIRS:
        return math.nan, count
    return float(np.median(pair_values[left:right])), count


def trade_origin_reference(trades: Trades, query_ms: int, corrected: bool):
    index = int(np.searchsorted(trades.times, query_ms, side="left") - 1)
    if index < 0 or query_ms - int(trades.times[index]) > MAX_AGE_MS:
        return math.nan, 0
    if not corrected:
        return float(trades.prices[index]), 0
    spread, count = bounce_estimate(trades.pair_times, trades.pair_values, query_ms)
    if not np.isfinite(spread):
        return math.nan, count
    denominator = 1.0 + float(trades.signs[index]) * spread / 20_000.0
    if denominator <= 0:
        return math.nan, count
    return float(trades.prices[index] / denominator), count


def trade_endpoint_reference(trades: Trades, target_ms: int, corrected: bool):
    index = int(np.searchsorted(trades.times, target_ms, side="left"))
    if index >= len(trades.times) or int(trades.times[index]) - target_ms > MAX_AGE_MS:
        return math.nan
    if not corrected:
        return float(trades.prices[index])
    event_ms = int(trades.times[index])
    spread, _ = bounce_estimate(trades.pair_times, trades.pair_values, event_ms)
    if not np.isfinite(spread):
        return math.nan
    denominator = 1.0 + float(trades.signs[index]) * spread / 20_000.0
    return math.nan if denominator <= 0 else float(trades.prices[index] / denominator)


def bbo_reference(times: np.ndarray, mids: np.ndarray, query_ms: int,
                  inclusive: bool = True):
    index = int(np.searchsorted(times, query_ms,
                                side="right" if inclusive else "left") - 1)
    if index < 0 or query_ms - int(times[index]) > MAX_AGE_MS:
        return math.nan
    return float(mids[index])


def first_fill(times: np.ndarray, prices: np.ndarray, signs: np.ndarray,
               origin_ms: int, quote: float, side: str):
    left = int(np.searchsorted(times, origin_ms, side="right"))
    right = int(np.searchsorted(times, origin_ms + FILL_WINDOW_MS, side="right"))
    if side == "short":
        matches = np.flatnonzero((signs[left:right] == 1)
                                 & (prices[left:right] >= quote + TICK - 1e-12))
    elif side == "long":
        matches = np.flatnonzero((signs[left:right] == -1)
                                 & (prices[left:right] <= quote - TICK + 1e-12))
    else:
        raise ValueError(f"unknown side: {side}")
    return -1 if not len(matches) else int(times[left + int(matches[0])])


def required_trade_paths(start: pd.Timestamp, stop: pd.Timestamp):
    days = pd.date_range(start.floor("D"), stop.floor("D"), freq="D", tz="UTC")
    paths = [TRADE_ROOT / f"BTCUSDT-aggTrades-{day:%Y-%m-%d}.zip" for day in days]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing aggTrades inputs: {missing[:3]}")
    return paths


def _owned_remove(path: Path, output: Path) -> None:
    resolved = path.resolve()
    root = output.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"refusing to remove path outside run output: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def _hour_parts(root: Path, hour: pd.Timestamp) -> Path:
    return root / f"date={hour:%Y-%m-%d}" / f"hour={hour:%H}"


def _required_hours(kind: str) -> pd.DatetimeIndex:
    if kind == "bbo":
        lower = START - pd.Timedelta(milliseconds=BBO_BEFORE_MS)
        upper = STOP + pd.Timedelta(milliseconds=FILL_WINDOW_MS + BBO_AFTER_MS)
    else:
        lower = START - pd.Timedelta(milliseconds=TRADE_BEFORE_MS)
        upper = STOP + pd.Timedelta(milliseconds=FILL_WINDOW_MS + TRADE_AFTER_MS)
    return pd.date_range(lower.floor("h"), upper.floor("h"), freq="h", tz="UTC")


def _stage_block_complete(directory: Path) -> bool:
    metadata_path = directory / "block.json"
    if not (directory / "_SUCCESS").is_file() or not metadata_path.is_file():
        return False
    if list(directory.glob("*.partial")):
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return bool(metadata["files"]) and all(
            completed_parquet(directory / row["path"])
            and pq.ParquetFile(directory / row["path"]).metadata.num_rows == row["rows"]
            for row in metadata["files"])
    except Exception:
        return False


def _finalize_stage_hour(work: Path, destination: Path, kind: str, output: Path) -> None:
    frames = [pd.read_parquet(path) for path in sorted(work.glob("*.parquet"))]
    if frames:
        frame = pd.concat(frames, ignore_index=True)
    elif kind == "bbo":
        frame = pd.DataFrame({"transaction_time": pd.Series(dtype="int64"),
                              "update_id": pd.Series(dtype="int64"),
                              "mid": pd.Series(dtype="float64")})
    else:
        frame = pd.DataFrame({"transact_time": pd.Series(dtype="int64"),
                              "agg_trade_id": pd.Series(dtype="int64"),
                              "price": pd.Series(dtype="float64"),
                              "sign": pd.Series(dtype="int8")})
    if kind == "bbo":
        frame.sort_values(["transaction_time", "update_id"], inplace=True,
                          kind="mergesort", ignore_index=True)
        if frame.duplicated(["transaction_time", "update_id"]).any():
            raise ValueError(f"duplicate BBO key in {destination}")
        frame.drop(columns="update_id", inplace=True)
    else:
        frame.sort_values(["transact_time", "agg_trade_id"], inplace=True,
                          kind="mergesort", ignore_index=True)
        if frame.agg_trade_id.duplicated().any():
            raise ValueError(f"duplicate aggTrade ID in {destination}")
        if (frame.transact_time.to_numpy()[1:] < frame.transact_time.to_numpy()[:-1]).any():
            raise ValueError(f"reversed aggTrade time in {destination}")
    _owned_remove(destination, output) if destination.exists() else None
    files = _write_parquet_parts(frame, destination, "part")
    save_json(destination / "block.json", {
        "kind": kind,
        "rows": len(frame),
        "min_time_ms": (int(frame.iloc[0]["transaction_time" if kind == "bbo" else "transact_time"])
                        if len(frame) else None),
        "max_time_ms": (int(frame.iloc[-1]["transaction_time" if kind == "bbo" else "transact_time"])
                        if len(frame) else None),
        "files": files,
    })
    _atomic_marker(destination / "_SUCCESS")


def _write_work_chunk(frame: pd.DataFrame, directory: Path, number: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"chunk-{number:06d}.parquet"
    partial = path.with_suffix(path.suffix + ".partial")
    frame.to_parquet(partial, index=False, compression="zstd")
    pq.ParquetFile(partial).metadata
    os.replace(partial, path)


def stage_bbo(output: Path, guard: RssGuard) -> None:
    root = output / "staging" / "bbo"
    required = _required_hours("bbo")
    for month, month_hours in pd.Series(required, index=required).groupby(required.strftime("%Y-%m")):
        month_hours = pd.DatetimeIndex(month_hours.to_numpy())
        incomplete = [hour for hour in month_hours if not _stage_block_complete(_hour_parts(root, hour))]
        if not incomplete:
            print(f"stage bbo {month}: resume skip", flush=True)
            continue
        work_month = output / "staging" / "_work" / "bbo" / month
        _owned_remove(work_month, output) if work_month.exists() else None
        path = BOOK_ROOT / f"BTCUSDT-bookTicker-{month}.zip"
        wanted = {int(hour.timestamp() // 3600): hour for hour in incomplete}
        print(f"stage bbo {month}: one ZIP pass, {len(incomplete)} hourly blocks", flush=True)
        with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as handle:
            reader = pd.read_csv(handle, usecols=["update_id", "best_bid_price",
                                                  "best_ask_price", "transaction_time"],
                                 chunksize=CSV_CHUNK)
            for chunk_number, frame in enumerate(reader):
                guard.begin_block()
                times = frame.transaction_time.to_numpy(np.int64, copy=False)
                bids = frame.best_bid_price.to_numpy(float, copy=False)
                asks = frame.best_ask_price.to_numpy(float, copy=False)
                if (not np.isfinite(bids).all() or not np.isfinite(asks).all()
                        or (bids <= 0).any() or (asks <= bids).any()):
                    raise ValueError(f"invalid/crossed BBO in {path.name}")
                frame = pd.DataFrame({"transaction_time": times,
                                      "update_id": frame.update_id.to_numpy(np.int64, copy=False),
                                      "mid": (bids + asks) / 2.0})
                frame["hour_key"] = frame.transaction_time // 3_600_000
                for hour_key, part in frame.groupby("hour_key", sort=False):
                    hour = wanted.get(int(hour_key))
                    if hour is not None:
                        _write_work_chunk(part.drop(columns="hour_key"),
                                          _hour_parts(work_month, hour), chunk_number)
                del frame
                guard.end_block(f"stage-bbo {month} chunk={chunk_number + 1}")
        for hour in incomplete:
            guard.begin_block()
            _finalize_stage_hour(_hour_parts(work_month, hour), _hour_parts(root, hour),
                                 "bbo", output)
            gc.collect()
            guard.end_block(f"stage-bbo-finalize {hour:%Y-%m-%dT%H}")
        _owned_remove(work_month, output)


def _maker_sign(values: pd.Series) -> np.ndarray:
    if values.dtype == bool:
        makers = values.to_numpy(bool, copy=False)
    else:
        mapped = values.astype(str).str.lower().map({"true": True, "false": False})
        if mapped.isna().any():
            raise ValueError("invalid is_buyer_maker value")
        makers = mapped.to_numpy(bool, copy=False)
    return np.where(makers, -1, 1).astype(np.int8)


def stage_trades(output: Path, guard: RssGuard) -> None:
    root = output / "staging" / "aggtrades"
    required = _required_hours("trade")
    days = pd.DatetimeIndex(required.floor("D").unique())
    previous_id = previous_time = None
    for day in days:
        day_hours = required[required.floor("D") == day]
        incomplete = [hour for hour in day_hours if not _stage_block_complete(_hour_parts(root, hour))]
        day_metadata = root / f"date={day:%Y-%m-%d}" / "day.json"
        if not incomplete and day_metadata.is_file():
            metadata = json.loads(day_metadata.read_text(encoding="utf-8"))
            if previous_id is not None and metadata["first_id"] != previous_id + 1:
                raise ValueError(f"aggTrade ID gap before {day:%Y-%m-%d}")
            previous_id, previous_time = metadata["last_id"], metadata["last_time_ms"]
            print(f"stage trades {day:%Y-%m-%d}: resume skip", flush=True)
            continue
        work_day = output / "staging" / "_work" / "aggtrades" / f"{day:%Y-%m-%d}"
        _owned_remove(work_day, output) if work_day.exists() else None
        path = TRADE_ROOT / f"BTCUSDT-aggTrades-{day:%Y-%m-%d}.zip"
        wanted = {int(hour.timestamp() // 3600): hour for hour in incomplete}
        first_id = first_time = last_id = last_time = None
        with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as handle:
            reader = pd.read_csv(handle, usecols=["agg_trade_id", "price", "transact_time",
                                                  "is_buyer_maker"], chunksize=CSV_CHUNK)
            for chunk_number, frame in enumerate(reader):
                guard.begin_block()
                ids = frame.agg_trade_id.to_numpy(np.int64, copy=False)
                times = frame.transact_time.to_numpy(np.int64, copy=False)
                if not len(ids) or (ids[1:] != ids[:-1] + 1).any():
                    raise ValueError(f"non-consecutive aggTrade IDs in {path.name}")
                if last_id is not None and ids[0] != last_id + 1:
                    raise ValueError(f"aggTrade ID gap in {path.name}")
                if (times[1:] < times[:-1]).any() or (last_time is not None and times[0] < last_time):
                    raise ValueError(f"reversed aggTrade timestamps in {path.name}")
                if first_id is None:
                    first_id = int(ids[0])
                    first_time = int(times[0])
                last_id, last_time = int(ids[-1]), int(times[-1])
                prices = frame.price.to_numpy(float, copy=False)
                if not np.isfinite(prices).all() or (prices <= 0).any():
                    raise ValueError(f"invalid aggTrade price in {path.name}")
                staged = pd.DataFrame({"transact_time": times, "agg_trade_id": ids,
                                       "price": prices, "sign": _maker_sign(frame.is_buyer_maker)})
                staged["hour_key"] = staged.transact_time // 3_600_000
                for hour_key, part in staged.groupby("hour_key", sort=False):
                    hour = wanted.get(int(hour_key))
                    if hour is not None:
                        _write_work_chunk(part.drop(columns="hour_key"),
                                          _hour_parts(work_day, hour), chunk_number)
                del frame, staged
                guard.end_block(f"stage-trades {day:%Y-%m-%d} chunk={chunk_number + 1}")
        if previous_id is not None and first_id != previous_id + 1:
            raise ValueError(f"aggTrade ID gap before {path.name}")
        if previous_time is not None and first_time < previous_time:
            raise ValueError(f"aggTrade time reversal before {path.name}")
        previous_id, previous_time = last_id, last_time
        for hour in incomplete:
            guard.begin_block()
            _finalize_stage_hour(_hour_parts(work_day, hour), _hour_parts(root, hour),
                                 "trade", output)
            gc.collect()
            guard.end_block(f"stage-trades-finalize {hour:%Y-%m-%dT%H}")
        save_json(day_metadata, {"first_id": first_id, "last_id": last_id,
                                 "last_time_ms": last_time})
        _owned_remove(work_day, output)


def _load_stage(root: Path, start_ms: int, stop_ms: int, kind: str) -> pd.DataFrame:
    hours = pd.date_range(pd.to_datetime(start_ms, unit="ms", utc=True).floor("h"),
                          pd.to_datetime(stop_ms, unit="ms", utc=True).floor("h"),
                          freq="h", tz="UTC")
    paths = []
    missing = []
    for hour in hours:
        directory = _hour_parts(root, hour)
        if not _stage_block_complete(directory):
            missing.append(str(directory))
        else:
            paths.extend(sorted(directory.glob("part-*.parquet")))
    if missing:
        raise ValueError(f"boundary_context_missing={len(missing)}: {missing[:3]}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    time_column = "transaction_time" if kind == "bbo" else "transact_time"
    frame = frame[(frame[time_column] >= start_ms) & (frame[time_column] <= stop_ms)]
    return frame.sort_values(time_column, kind="mergesort", ignore_index=True)


def _as_trades(frame: pd.DataFrame) -> Trades:
    times = frame.transact_time.to_numpy(np.int64, copy=False)
    ids = frame.agg_trade_id.to_numpy(np.int64, copy=False)
    prices = frame.price.to_numpy(float, copy=False)
    signs = frame.sign.to_numpy(np.int8, copy=False)
    pair_times_, pair_values_ = pair_events(times, prices, signs)
    return Trades(times, ids, prices, signs, pair_times_, pair_values_)


def _quotes(reference: float):
    return (ceil_tick(reference * (1.0 + OFFSETS / 10_000.0)),
            floor_tick(reference * (1.0 - OFFSETS / 10_000.0)))


def process_origins(origin_ms: np.ndarray, bbo_times: np.ndarray, bbo_mids: np.ndarray,
                    trades: Trades, boundary_context_missing: bool = False):
    origin_rows = []
    outcome_rows = []
    for number, origin in enumerate(origin_ms):
        origin = int(origin)
        left = int(np.searchsorted(trades.times, origin - 60_000, side="left"))
        right = int(np.searchsorted(trades.times, origin, side="left"))
        bbo = bbo_reference(bbo_times, bbo_mids, origin, inclusive=False)
        bounce, pair_count = trade_origin_reference(trades, origin, True)
        raw, _ = trade_origin_reference(trades, origin, False)
        if boundary_context_missing:
            drop_reason = "boundary_context_missing"
        elif not np.isfinite(raw):
            drop_reason = "stale_trade"
        elif pair_count < BOUNCE_MIN_PAIRS:
            drop_reason = "pair_count_lt_20"
        else:
            drop_reason = ""
        refs = {"bbo": bbo, "bounce": bounce, "raw": raw}
        stamp = pd.to_datetime(origin, unit="ms", utc=True)
        origin_rows.append({
            "origin": stamp,
            "month": stamp.strftime("%Y-%m"),
            "utc_hour": int(stamp.hour),
            "trade_intensity_60s": int(right - left),
            "bounce_pair_count": pair_count,
            "drop_reason": drop_reason,
            "bbo_origin_valid": bool(np.isfinite(bbo)),
            "bounce_origin_valid": bool(np.isfinite(bounce)),
            "raw_origin_valid": bool(np.isfinite(raw)),
        })
        arm_quotes = {}
        for arm, reference in refs.items():
            if np.isfinite(reference):
                short, long = _quotes(reference)
                arm_quotes[arm] = {"short": short, "long": long}
        endpoint_cache = {}
        for side in ("short", "long"):
            side_sign = 1.0 if side == "long" else -1.0
            for offset_index, offset in enumerate(OFFSETS):
                row = {"origin": stamp, "month": stamp.strftime("%Y-%m"),
                       "side": side, "offset_bps": float(offset)}
                for arm in ARMS:
                    valid = arm in arm_quotes
                    quote = float(arm_quotes[arm][side][offset_index]) if valid else math.nan
                    fill_ms = first_fill(trades.times, trades.prices, trades.signs,
                                         origin, quote, side) if valid else -1
                    filled = fill_ms >= 0
                    endpoint = math.nan
                    markout = math.nan
                    if valid and filled:
                        cache_key = (arm, fill_ms)
                        if cache_key not in endpoint_cache:
                            target = fill_ms + MARKOUT_MS
                            if arm == "bbo":
                                endpoint_cache[cache_key] = bbo_reference(
                                    bbo_times, bbo_mids, target, inclusive=True)
                            else:
                                endpoint_cache[cache_key] = trade_endpoint_reference(
                                    trades, target, arm == "bounce")
                        endpoint = endpoint_cache[cache_key]
                        valid = bool(np.isfinite(endpoint))
                        if valid:
                            markout = side_sign * 10_000.0 * math.log(endpoint / quote)
                    row.update({
                        f"{arm}_valid": valid,
                        f"{arm}_fill": filled,
                        f"{arm}_fill_ms": fill_ms,
                        f"{arm}_quote": quote,
                        f"{arm}_endpoint": endpoint,
                        f"{arm}_markout_bps": markout,
                    })
                outcome_rows.append(row)
        if (number + 1) % 10_000 == 0:
            print(f"  targets: {number + 1:,}/{len(origin_ms):,} origins", flush=True)
    return pd.DataFrame(origin_rows), pd.DataFrame(outcome_rows)


def _stats(frame: pd.DataFrame, reference: str, candidate: str):
    ref = frame[f"{reference}_markout_bps"].to_numpy(float)
    cand = frame[f"{candidate}_markout_bps"].to_numpy(float)
    keep = np.isfinite(ref) & np.isfinite(cand)
    ref, cand = ref[keep], cand[keep]
    if not len(ref):
        return {"count": 0, "mean": None, "mae": None, "p50": None, "p90": None,
                "p99": None, "max": None, "pearson": None, "spearman": None}
    difference = cand - ref
    absolute = np.abs(difference)
    pearson = pd.Series(ref).corr(pd.Series(cand), method="pearson") if len(ref) >= 2 else math.nan
    spearman = pd.Series(ref).corr(pd.Series(cand), method="spearman") if len(ref) >= 2 else math.nan
    return json_ready({
        "count": len(ref),
        "mean": difference.mean(),
        "mae": absolute.mean(),
        "p50": np.quantile(absolute, .50),
        "p90": np.quantile(absolute, .90),
        "p99": np.quantile(absolute, .99),
        "max": absolute.max(),
        "pearson": pearson,
        "spearman": spearman,
    })


def _split_stats(frame: pd.DataFrame, reference: str, candidate: str):
    rows = []
    definitions = [("overall", []) , ("offset", ["offset_bps"]),
                   ("side", ["side"]), ("month", ["month"])]
    for split, columns in definitions:
        groups = [((), frame)] if not columns else frame.groupby(columns, sort=True, observed=True)
        for key, part in groups:
            keys = key if isinstance(key, tuple) else (key,)
            row = {"split": split, "reference": reference, "candidate": candidate}
            row.update({column: value for column, value in zip(columns, keys)})
            row.update(_stats(part, reference, candidate))
            rows.append(row)
    return rows


def _origin_validity(outcomes: pd.DataFrame):
    values = outcomes.groupby("origin", sort=False)[[f"{arm}_valid" for arm in ARMS]].all()
    return values.rename(columns={f"{arm}_valid": arm for arm in ARMS})


def _gate_pair(origins: pd.DataFrame, outcomes: pd.DataFrame,
               validity: pd.DataFrame, reference: str, candidate: str):
    common = validity[reference] & validity[candidate]
    common_origins = common.index[common]
    coverage_rows = [{"split": "overall", "month": None, "common": int(common.sum()),
                      "total": len(common), "rate": float(common.mean())}]
    origin_month = origins.set_index("origin").month
    for month, index in origin_month.groupby(origin_month).groups.items():
        mask = common.reindex(index).fillna(False)
        coverage_rows.append({"split": "month", "month": month, "common": int(mask.sum()),
                              "total": len(mask), "rate": float(mask.mean())})
    paired = outcomes[outcomes.origin.isin(common_origins)].copy()
    paired["fill_equal"] = paired[f"{reference}_fill"] == paired[f"{candidate}_fill"]
    fill_rows = []
    for keys, part in paired.groupby(["side", "offset_bps"], sort=True, observed=True):
        fill_rows.append({"split": "side_offset", "side": keys[0], "offset_bps": keys[1],
                          "month": None, "count": len(part),
                          "agreement": float(part.fill_equal.mean())})
    for keys, part in paired.groupby(["side", "offset_bps", "month"], sort=True, observed=True):
        fill_rows.append({"split": "side_offset_month", "side": keys[0],
                          "offset_bps": keys[1], "month": keys[2], "count": len(part),
                          "agreement": float(part.fill_equal.mean())})
    both = paired[paired[f"{reference}_fill"] & paired[f"{candidate}_fill"]]
    distributions = _split_stats(both, reference, candidate)

    coverage_pass = (coverage_rows[0]["rate"] >= .99
                     and all(row["rate"] >= .98 for row in coverage_rows[1:]))
    fill_pass = bool(fill_rows) and all(row["agreement"] >= .99 for row in fill_rows)
    mean_pass = bool(distributions) and all(row["mean"] is not None
                                            and abs(row["mean"]) <= .02 for row in distributions)
    mae_pass = bool(distributions) and all(row["mae"] is not None
                                           and row["mae"] <= .10 for row in distributions)
    p99_pass = bool(distributions) and all(row["p99"] is not None
                                           and row["p99"] <= .50 for row in distributions)
    correlation_pass = bool(distributions) and all(
        row["pearson"] is not None and row["spearman"] is not None
        and row["pearson"] >= .995 and row["spearman"] >= .995
        for row in distributions)
    criteria = {
        "common_valid_origins": coverage_pass,
        "fill_agreement": fill_pass,
        "markout_mean_difference": mean_pass,
        "markout_mae": mae_pass,
        "markout_absolute_difference_p99": p99_pass,
        "pearson_and_spearman": correlation_pass,
    }
    return {
        "reference": reference,
        "candidate": candidate,
        "pass": all(criteria.values()),
        "criteria": criteria,
        "coverage": coverage_rows,
        "fill_agreement": fill_rows,
        "distributions": distributions,
    }


DROP_REASONS = ("stale_trade", "pair_count_lt_20", "boundary_context_missing")


def _drop_table(frame: pd.DataFrame, columns: list[str]):
    rows = []
    for key, part in frame.groupby(columns, sort=True, observed=True, dropna=False):
        keys = key if isinstance(key, tuple) else (key,)
        base = {column: value for column, value in zip(columns, keys)}
        for reason in DROP_REASONS:
            dropped = int((part.drop_reason == reason).sum())
            rows.append(json_ready({**base, "cause": reason, "origins": len(part),
                                    "dropped": dropped, "drop_rate": dropped / len(part)}))
    return rows


def _population_comparison(origins: pd.DataFrame, outcomes: pd.DataFrame,
                           validity: pd.DataFrame, reference: str, candidate: str,
                           groups: dict[str, pd.Index]):
    rows = []
    for name, index in groups.items():
        common = validity.index.intersection(index)
        common = common[validity.loc[common, reference] & validity.loc[common, candidate]]
        part = outcomes[outcomes.origin.isin(common)].copy()
        if len(part):
            fill = float((part[f"{reference}_fill"] == part[f"{candidate}_fill"]).mean())
            both = part[part[f"{reference}_fill"] & part[f"{candidate}_fill"]]
        else:
            fill, both = math.nan, part
        rows.append({"group": name, "reference": reference, "candidate": candidate,
                     "common_origins": len(common), "fill_agreement": json_ready(fill),
                     "markout": _stats(both, reference, candidate)})
    return rows


def build_report(origins: pd.DataFrame, outcomes: pd.DataFrame):
    origins = origins.sort_values("origin").reset_index(drop=True)
    if "drop_reason" not in origins:
        origins["drop_reason"] = np.where(
            origins.bounce_origin_valid, "",
            np.where(origins.raw_origin_valid, "pair_count_lt_20", "stale_trade"))
    boundary_missing = int((origins.drop_reason == "boundary_context_missing").sum())
    if boundary_missing:
        raise ValueError(f"boundary_context_missing={boundary_missing}; gate not computed")
    origins["bounce_dropped"] = origins.drop_reason != ""
    adjacent = origins.bounce_dropped.shift(1, fill_value=False) | origins.bounce_dropped.shift(-1, fill_value=False)
    origins["drop_adjacent"] = origins.bounce_origin_valid & adjacent
    origins["intensity_bin"] = pd.cut(
        origins.trade_intensity_60s,
        bins=[-1, 49, 99, 199, 499, 999, np.inf],
        labels=["0-49", "50-99", "100-199", "200-499", "500-999", "1000+"])
    validity = _origin_validity(outcomes)
    comparisons = {}
    for reference, candidate in PAIRS:
        key = f"{reference}_vs_{candidate}"
        comparisons[key] = _gate_pair(origins, outcomes, validity, reference, candidate)

    indexed = origins.set_index("origin")
    kept = indexed.index[~indexed.bounce_dropped]
    dropped = indexed.index[indexed.bounce_dropped]
    adjacent_kept = indexed.index[indexed.drop_adjacent]
    nonadjacent_kept = indexed.index[(~indexed.bounce_dropped) & (~indexed.drop_adjacent)]
    population = []
    population += _population_comparison(origins, outcomes, validity, "bbo", "bounce", {
        "kept_drop_adjacent": adjacent_kept,
        "kept_nonadjacent": nonadjacent_kept,
    })
    population += _population_comparison(origins, outcomes, validity, "bbo", "raw", {
        "bounce_kept": kept,
        "bounce_dropped": dropped,
        "kept_drop_adjacent": adjacent_kept,
    })
    drop_rate = float(origins.bounce_dropped.mean())
    by_cause = {}
    for reason in DROP_REASONS:
        count = int((origins.drop_reason == reason).sum())
        by_cause[reason] = {"count": count, "rate": count / len(origins)}
    drop_analysis = {
        "origins": len(origins),
        "dropped": int(origins.bounce_dropped.sum()),
        "drop_rate": drop_rate,
        "large_population_change": drop_rate > .01,
        "by_cause": by_cause,
        "by_utc_hour": _drop_table(origins, ["utc_hour"]),
        "by_month": _drop_table(origins, ["month"]),
        "by_trade_intensity": _drop_table(origins, ["intensity_bin"]),
        "agreement_near_drops": population,
    }
    all_pass = all(value["pass"] for value in comparisons.values())
    bbo_bounce = comparisons["bbo_vs_bounce"]["pass"]
    bbo_raw = comparisons["bbo_vs_raw"]["pass"]
    if all_pass and bbo_raw:
        primary = "raw_last_trade"
        correction = "not justified: raw passes and avoids bounce assumptions and origin drops"
    elif all_pass and bbo_bounce:
        primary = "bounce_corrected_trade"
        correction = "required: raw last trade does not pass"
    else:
        primary = None
        correction = "no trade target is promoted because at least one frozen pairwise gate failed"
    verdict = {
        "trade_target_replaces_bbo": all_pass,
        "full_span_primary": primary,
        "bounce_correction": correction,
        "full_span_change": ("use the selected trade target; remove BBO-only labels and features"
                             if all_pass else
                             "do not start full-span fitting; target equivalence remains failed"),
    }
    return json_ready({
        "status": "PASS" if all_pass else "FAIL",
        "window": {"start": START, "stop": STOP},
        "arms": list(ARMS),
        "offsets_bps": OFFSETS.tolist(),
        "comparisons": comparisons,
        "drop_analysis": drop_analysis,
        "verdict": verdict,
        "new_model_fits": 0,
        "new_orders": 0,
    }), origins


def input_paths():
    books = sorted(BOOK_ROOT.glob("BTCUSDT-bookTicker-*.zip"))
    books = [path for path in books if "2023-05" <= path.stem[-7:] <= "2024-04"]
    trades = required_trade_paths(START, STOP + pd.Timedelta(minutes=2))
    return books + trades + [SPREAD_ARTIFACT]


def make_manifest(paths: list[Path]):
    print(f"hashing {len(paths)} frozen inputs", flush=True)
    records = []
    for number, path in enumerate(paths, 1):
        records.append({"path": path.as_posix(), "bytes": path.stat().st_size,
                        "sha256": sha256(path)})
        if number % 25 == 0 or number == len(paths):
            print(f"  hashes: {number}/{len(paths)}", flush=True)
    source = Path(__file__).resolve()
    return {
        "status": "PREFLIGHT_PASS",
        "plan": {"path": PLAN.as_posix(), "sha256": sha256(PLAN)},
        "sources": [{"path": source.relative_to(Path.cwd()).as_posix(),
                     "sha256": sha256(source)}],
        "inputs": records,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
        "data_cutoff": STOP.isoformat(),
        "new_model_fits": 0,
        "new_orders": 0,
    }


def _write_tables(report: dict, output: Path):
    coverage, fill, distributions = [], [], []
    for pair, value in report["comparisons"].items():
        coverage += [dict(pair=pair, **row) for row in value["coverage"]]
        fill += [dict(pair=pair, **row) for row in value["fill_agreement"]]
        distributions += [dict(pair=pair, **row) for row in value["distributions"]]
    for name, frame in (("coverage.csv", pd.DataFrame(coverage)),
                        ("fill_agreement.csv", pd.DataFrame(fill)),
                        ("markout_distributions.csv", pd.DataFrame(distributions))):
        path = output / name
        partial = path.with_suffix(path.suffix + ".partial")
        frame.to_csv(partial, index=False)
        os.replace(partial, path)


def preflight(output: Path):
    if sha256(PLAN) != PLAN_SHA256:
        raise ValueError("frozen plan SHA-256 mismatch")
    free = shutil.disk_usage(output.parent if output.parent.exists() else Path.cwd()).free
    if free < MIN_FREE_DISK:
        raise OSError(f"preflight free disk {free / 1024**3:.1f} GiB < 100 GiB")
    paths = input_paths()
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing frozen inputs: {missing[:3]}")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    current = make_manifest(paths)
    if manifest_path.is_file():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("plan", "sources", "inputs"):
            if saved.get(key) != current.get(key):
                raise ValueError(f"restart refused: frozen {key} changed")
        print(f"PREFLIGHT PASS (restart): free={free / 1024**3:.1f} GiB", flush=True)
        return saved
    save_json(manifest_path, current)
    print(f"PREFLIGHT PASS: free={free / 1024**3:.1f} GiB, inputs={len(paths)}", flush=True)
    return current


def _day_complete(directory: Path) -> bool:
    metadata_path = directory / "shard.json"
    if not (directory / "_SUCCESS").is_file() or not metadata_path.is_file():
        return False
    if list(directory.glob("*.partial")):
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return all(completed_parquet(directory / row["path"])
                   and sha256(directory / row["path"]) == row["sha256"]
                   for row in metadata["files"])
    except Exception:
        return False


def _write_day_shard(output: Path, day: pd.Timestamp,
                     origins: pd.DataFrame, outcomes: pd.DataFrame) -> None:
    directory = output / "shards" / f"date={day:%Y-%m-%d}"
    _owned_remove(directory, output) if directory.exists() else None
    files = _write_parquet_parts(origins, directory, "origins")
    files += _write_parquet_parts(outcomes, directory, "outcomes")
    save_json(directory / "shard.json", {
        "date": f"{day:%Y-%m-%d}", "origin_rows": len(origins),
        "outcome_rows": len(outcomes), "max_part_rows": MAX_PART_ROWS, "files": files,
    })
    _atomic_marker(directory / "_SUCCESS")


def compute_shards(output: Path, guard: RssGuard) -> None:
    bbo_root = output / "staging" / "bbo"
    trade_root = output / "staging" / "aggtrades"
    for day in pd.date_range(START.floor("D"), STOP.floor("D"), freq="D", tz="UTC"):
        directory = output / "shards" / f"date={day:%Y-%m-%d}"
        if _day_complete(directory):
            print(f"compute {day:%Y-%m-%d}: resume skip", flush=True)
            continue
        day_start, day_stop = max(START, day), min(STOP, day + pd.Timedelta(days=1) - pd.Timedelta(minutes=1))
        grid = pd.date_range(day_start.ceil("min"), day_stop.floor("min"), freq="min", tz="UTC")
        origin_parts, outcome_parts = [], []
        for hour, stamps in pd.Series(grid, index=grid).groupby(grid.floor("h")):
            guard.begin_block()
            origins_ms = epoch_ms(pd.DatetimeIndex(stamps))
            fill_start = int(origins_ms.min())
            fill_stop = int(origins_ms.max()) + FILL_WINDOW_MS
            bbo = _load_stage(bbo_root, fill_start - BBO_BEFORE_MS,
                              fill_stop + BBO_AFTER_MS, "bbo")
            trade_frame = _load_stage(trade_root, fill_start - TRADE_BEFORE_MS,
                                      fill_stop + TRADE_AFTER_MS, "trade")
            trades = _as_trades(trade_frame)
            origins, outcomes = process_origins(
                origins_ms, bbo.transaction_time.to_numpy(np.int64, copy=False),
                bbo.mid.to_numpy(float, copy=False), trades)
            origin_parts.append(origins)
            outcome_parts.append(outcomes)
            del bbo, trade_frame, trades, origins, outcomes
            gc.collect()
            guard.end_block(f"compute {hour:%Y-%m-%dT%H}")
        origins = pd.concat(origin_parts, ignore_index=True)
        outcomes = pd.concat(outcome_parts, ignore_index=True)
        if origins.origin.duplicated().any() or len(outcomes) != 8 * len(origins):
            raise ValueError(f"invalid logical day shard {day:%Y-%m-%d}")
        _write_day_shard(output, day, origins, outcomes)
        del origins, outcomes, origin_parts, outcome_parts
        gc.collect()


def _shard_paths(output: Path, stem: str) -> list[Path]:
    directories = sorted((output / "shards").glob("date=*"))
    invalid = [str(path) for path in directories if not _day_complete(path)]
    if invalid:
        raise ValueError(f"incomplete logical shards: {invalid[:3]}")
    return [path for directory in directories for path in sorted(directory.glob(f"{stem}-*.parquet"))]


def _load_measurement(output: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    origin_paths = _shard_paths(output, "origins")
    outcome_paths = _shard_paths(output, "outcomes")
    origins = pd.concat([pd.read_parquet(path) for path in origin_paths], ignore_index=True)
    outcomes = pd.concat([pd.read_parquet(path) for path in outcome_paths], ignore_index=True)
    return origins, outcomes


def _output_records(output: Path) -> list[dict]:
    paths = [output / name for name in ("results.json", "coverage.csv", "fill_agreement.csv",
                                        "markout_distributions.csv")]
    paths += _shard_paths(output, "origins") + _shard_paths(output, "outcomes")
    return [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size,
             "sha256": sha256(path)} for path in paths]


def run(output: Path):
    started = time.monotonic()
    manifest = preflight(output)
    if manifest.get("status") == "COMPLETE" and (output / "_SUCCESS").is_file():
        print("measurement already complete; verifying", flush=True)
        verify(output)
        return
    manifest["status"] = "RUNNING"
    save_json(output / "manifest.json", manifest)
    with RssGuard() as guard:
        stage_bbo(output, guard)
        stage_trades(output, guard)
        compute_shards(output, guard)
        guard.begin_block()
        origins, outcomes = _load_measurement(output)
        guard.end_block("report-load")
        guard.begin_block()
        report, _ = build_report(origins, outcomes)
        guard.end_block("report-build")
        wall = time.monotonic() - started
        report["execution"] = {"peak_rss_bytes": guard.maximum,
                               "peak_rss_gib": guard.maximum / 1024**3,
                               "wall_clock_seconds": wall}
        save_json(output / "results.json", report)
        _write_tables(report, output)
        del origins, outcomes
        gc.collect()
        guard.end_block("report-write")
        manifest["status"] = "COMPLETE"
        manifest["peak_rss_bytes"] = guard.maximum
        manifest["wall_clock_seconds"] = wall
        manifest["outputs"] = _output_records(output)
        save_json(output / "manifest.json", manifest)
        _atomic_marker(output / "_SUCCESS")
    print(json.dumps({"status": report["status"], "verdict": report["verdict"],
                      "drop_rate": report["drop_analysis"]["drop_rate"],
                      "peak_rss_gib": report["execution"]["peak_rss_gib"],
                      "wall_clock_seconds": report["execution"]["wall_clock_seconds"],
                      "new_model_fits": 0, "new_orders": 0}, indent=2), flush=True)
    verify(output)


def verify(output: Path):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "COMPLETE":
        raise ValueError("run is not complete")
    if manifest["plan"]["sha256"] != PLAN_SHA256 or sha256(PLAN) != PLAN_SHA256:
        raise ValueError("frozen plan SHA-256 mismatch")
    for section in ("sources", "inputs"):
        for row in manifest[section]:
            path = Path(row["path"])
            if not path.is_file() or sha256(path) != row["sha256"]:
                raise ValueError(f"{section[:-1]} hash mismatch: {path}")
    for row in manifest["outputs"]:
        path = output / row["path"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise ValueError(f"output hash mismatch: {path}")
    if not (output / "_SUCCESS").is_file():
        raise ValueError("run success marker missing")
    origins, outcomes = _load_measurement(output)
    reconstructed, _ = build_report(origins, outcomes)
    saved = json.loads((output / "results.json").read_text(encoding="utf-8"))
    saved_core = {key: value for key, value in saved.items() if key != "execution"}
    if reconstructed != saved_core:
        raise ValueError("reconstructed results differ")
    if saved["new_model_fits"] != 0 or saved["new_orders"] != 0:
        raise ValueError("zero-fit/order invariant failed")
    print("VERIFY PASS: frozen hashes and reconstructed zero-fit results match", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.output)
    elif args.preflight:
        preflight(args.output)
    else:
        run(args.output)


if __name__ == "__main__":
    main()
