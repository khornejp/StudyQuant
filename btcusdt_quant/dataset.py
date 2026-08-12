from __future__ import annotations

import csv
import io
import json
import logging
import os
import pickle
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
import zipfile
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timedelta, timezone
from bisect import bisect_left, bisect_right
from math import isfinite, log, sqrt, sin
from pathlib import Path
from statistics import mean as _statistics_mean

import numpy as np


# Canonical triple-barrier geometry. The SINGLE source for the labeling barrier,
# so training, the backtest's execution barrier and the threshold objective
# cannot drift apart into a train/serve mismatch.
#
# The barrier must clear the round-trip cost (2*(fee+slippage) = 0.0008) by a
# wide margin or the reward:risk the labels advertise is not the one the account
# earns. The previous 0.003/0.0015 lost that argument outright: net of cost a TP
# pays +0.22% and an SL costs -0.23%, so a nominal 2.0:1 executes as 0.96:1 and
# break-even win rate is 51.1% -- above what the model delivers, which is why
# every backtest at that geometry lost money. At 0.010/0.005 the net is
# +0.92%/-0.58% (1.59:1) and break-even falls to 38.7%.
DEFAULT_LABEL_TP_PCT = 0.010
DEFAULT_LABEL_SL_PCT = 0.005


def mean(values):
    """Fast arithmetic mean for sequences of floats.

    Replaces statistics.mean (which uses Fraction-based exact arithmetic and
    dominates the build_feature_rows profile). For our feature pipeline,
    float-precision averaging is sufficient. Falls back to statistics.mean for
    non-numeric inputs to preserve the original contract.
    """
    if not values:
        # statistics.mean raises StatisticsError on empty input; preserve that
        return _statistics_mean(values)
    # Iterate once to compute both sum and length without materializing a list
    total = 0.0
    count = 0
    try:
        for value in values:
            total += value
            count += 1
    except TypeError:
        return _statistics_mean(values)
    return total / count
from typing import Callable, Mapping, Sequence

from . import data, feature_registry, features, mtf_features, parity, sources, weekly_features
from .feature_vector import FeatureVector, bind_canonical as _bind_feature_canonical


COLLECTED_CSV_FIELDS: tuple[str, ...] = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "number_of_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)

ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m"

ARCHIVE_CSV_FIELDS: tuple[str, ...] = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)

ARCHIVE_CHECKPOINT_KEYS: tuple[str, ...] = ("last_completed_date", "downloaded_files", "failed_dates")

LOGGER = logging.getLogger(__name__)


FEATURE_FORMULAS: tuple[dict[str, object], ...] = feature_registry.FEATURE_FORMULAS
FEATURE_NAMES: tuple[str, ...] = feature_registry.active_feature_names()
# NOTE: build_feature_rows still COMPUTES some registry-disabled
# ("disabled_scale_dependent") values -- rolling_vwap_*, range_high/low_20,
# macd_line/signal (dollar-scale, absolute-price-level series) -- because
# active RELATIVE features derive from them (vwap_deviation_zscore,
# price_vs_rolling_vwap_*, range_position_20, distance_to_range_*). They are
# dropped at FeatureVector.from_mapping (extra names ignored), so they never
# reach the model, artifacts, or live parity surfaces.

# Bind the canonical feature order shared by every FeatureVector (columnar
# float32 storage). Must happen before any FeatureVector is built.
_bind_feature_canonical(FEATURE_NAMES)

# Shared immutable-by-convention empty dict for MTF lookups that miss (warmup
# rows). Reused instead of allocating a fresh {} per lookup.
_EMPTY_MTF_ROW: dict[str, float] = {}

LABEL_REASON_BUCKETS: tuple[str, ...] = (
    "tp_first",
    "sl_first",
    "timeout_no_tp",
    "ambiguous_path",
    "no_fill",
    "partial_fill",
    "post_only_blocked",
    "gap_cross_timeout",
    "gap_cross_sl",
    "funding_force_close",
    "funding_cross",
    "liquidation",
)

EVENT_NEGATIVE_REASONS: frozenset[str] = frozenset(
    {
        "no_fill",
        "partial_fill",
        "post_only_blocked",
        "gap_cross_sl",
        "funding_force_close",
        "funding_cross",
        "liquidation",
    }
)


@dataclass(frozen=True)
class GapReport:
    raw_rows: int
    canonical_rows: int
    repaired_rows: int
    gap_ratio_total: float
    max_gap_run: int
    first_open_time: str
    last_open_time: str


@dataclass(frozen=True)
class UserRegimePeriod:
    regime: str
    start: datetime
    end_exclusive: datetime


USER_REGIME_NAMES: tuple[str, ...] = ("up", "down", "range")

# Bumped to 2 on 2026-07-31: feature columns whose name collides with a
# structural column (gap_flag is both a FeatureRow field and a feature) are now
# stored under a "feature__" prefix. Before that the feature silently
# overwrote the field's column and came back as NaN, so a cached matrix was not
# the matrix it replaced.
DATASET_CACHE_SCHEMA_VERSION = 2
# Column names the row schema owns. A feature sharing one of these names cannot
# share its column, so it is written prefixed and mapped back on read.
_RESERVED_ROW_COLUMNS: frozenset[str] = frozenset({
    "index", "open_time", "gap_flag", "repaired", "warmup_invalid", "user_regime",
    "source_availability_status_json", "feature_availability_status_json",
    "unavailable_sources_json", "fallback_features_json",
    "label", "label_reason", "target_return", "targets_json", "target_reasons_json",
})
_FEATURE_COLUMN_PREFIX = "feature__"


def _feature_column_name(feature_name: str) -> str:
    """Parquet column holding this feature's values."""
    return f"{_FEATURE_COLUMN_PREFIX}{feature_name}" if feature_name in _RESERVED_ROW_COLUMNS else feature_name
DATASET_CACHE_METADATA_FILE = "_metadata.json"
DATASET_CACHE_FEATURE_ROWS_FILE = "feature_rows.parquet"
DATASET_CACHE_LABELED_ROWS_FILE = "labeled_rows.parquet"
DATASET_CACHE_CANONICAL_FILE = "canonical.parquet"


@dataclass(frozen=True)
class DatasetCacheValidation:
    feature_count_matches: bool
    missing_features: tuple[str, ...]
    extra_features: tuple[str, ...]
    schema_version: int


@dataclass(frozen=True, slots=True)
class FeatureRow:
    index: int
    open_time: datetime
    features: Mapping[str, float]
    gap_flag: int
    repaired: bool
    warmup_invalid: bool
    source_availability_status: dict[str, str] = field(default_factory=dict)
    feature_availability_status: dict[str, str] = field(default_factory=dict)
    unavailable_sources: tuple[str, ...] = ()
    fallback_features: tuple[str, ...] = ()
    user_regime: str | None = None


@dataclass(frozen=True)
class LabeledRow:
    index: int
    open_time: datetime
    features: Mapping[str, float]
    label: int
    label_reason: str
    target_return: float
    gap_flag: int
    repaired: bool
    warmup_invalid: bool
    source_availability_status: dict[str, str] = field(default_factory=dict)
    feature_availability_status: dict[str, str] = field(default_factory=dict)
    unavailable_sources: tuple[str, ...] = ()
    fallback_features: tuple[str, ...] = ()
    targets: dict[str, int] = field(default_factory=dict)
    target_reasons: dict[str, str] = field(default_factory=dict)
    user_regime: str | None = None


@dataclass
class DatasetBuild:
    source: str
    symbol: str
    interval: str
    raw_rows: int
    canonical: list[data.Candle]
    gap_report: GapReport
    feature_rows: list[FeatureRow]
    labeled_rows: list[LabeledRow]
    feature_names: tuple[str, ...]
    label_horizon: int
    label_threshold: float
    source_bundle: sources.MarketSourceBundle | None = None
    source_availability_report: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.source_availability_report is None:
            self.source_availability_report = {}


@dataclass(frozen=True)
class CollectionResult:
    output_path: Path
    source: str
    symbol: str
    interval: str
    rows: int
    network_used: bool


@dataclass(frozen=True)
class ArchiveDownloadSummary:
    output_dir: Path
    checkpoint_file: Path
    start_date: str
    end_date: str
    total_days: int
    downloaded_days: int
    failed_days: int
    last_completed_date: str | None
    downloaded_files: tuple[str, ...]
    failed_dates: tuple[str, ...]


class ArchiveDownloadError(RuntimeError):
    """Recoverable per-day archive download failure."""


class ArchiveHardBanError(RuntimeError):
    """HTTP 418 hard-ban response; archive crawling must stop immediately."""


class ArchiveValidationError(ValueError):
    """Malformed archive CSV or zip payload."""


class PublicKlineDownloader:
    """Explicit opt-in downloader for unsigned public kline data only."""

    def __init__(self, allow_network: bool = False, base_url: str = "https://fapi.binance.com", timeout_seconds: int = 10, urlopen: Callable[..., object] | None = None) -> None:
        self.allow_network = allow_network
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.urlopen = urlopen or urllib.request.urlopen

    def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        limit: int = 500,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        max_retries: int = 3,
    ) -> list[data.Candle]:
        if not self.allow_network:
            raise RuntimeError("public kline download requires explicit allow_network=True")
        if limit <= 0 or limit > 1500:
            raise ValueError("limit must be between 1 and 1500")
        params: dict[str, object] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/fapi/v1/klines?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-offline-research/0.1"})
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                with self.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, list):
                    raise ValueError("unexpected kline response payload")
                return [candle_from_kline_row(row) for row in payload]
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 418:
                    # Hard ban: do not retry
                    raise RuntimeError(f"public kline hard ban (418) on {url}: {exc}") from exc
                if exc.code == 429 and attempt < max_retries - 1:
                    # Honor Retry-After if present
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            sleep_seconds = float(retry_after)
                        except (ValueError, TypeError):
                            sleep_seconds = 1.0 * (attempt + 1)
                    else:
                        sleep_seconds = 1.0 * (attempt + 1)
                    time.sleep(sleep_seconds)
                    continue
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
            except Exception as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
        raise RuntimeError(f"public kline fetch failed after {max_retries} attempts: {last_error}")

    def fetch_klines_paginated(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        max_rows: int = 10000,
    ) -> list[data.Candle]:
        if not self.allow_network:
            raise RuntimeError("public kline download requires explicit allow_network=True")
        all_candles: list[data.Candle] = []
        current_start = start_time_ms
        while len(all_candles) < max_rows:
            batch = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=1500,
                start_time_ms=current_start,
                end_time_ms=end_time_ms,
            )
            if not batch:
                break
            all_candles.extend(batch)
            if len(batch) < 1500:
                break
            last_open_time_ms = int(batch[-1].open_time.timestamp() * 1000)
            current_start = last_open_time_ms + 1
            if end_time_ms is not None and current_start > end_time_ms:
                break
            # Rate-limit backoff between paginated batches to avoid 429 errors
            time.sleep(0.5)
        return all_candles[:max_rows]


class BinanceArchiveDownloader:
    """Downloader for Binance futures daily 1m kline archives."""

    def __init__(
        self,
        base_url: str = ARCHIVE_BASE_URL,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        timeout_seconds: int = 30,
        max_retries: int = 5,
        urlopen: Callable[..., object] | None = None,
        sleep: Callable[[float], None] | None = None,
        request_interval_seconds: float = 0.2,
    ) -> None:
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if request_interval_seconds < 0.0:
            raise ValueError("request_interval_seconds must be non-negative")
        self.base_url = base_url.rstrip("/")
        self.symbol = symbol
        self.interval = interval
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.urlopen = urlopen or urllib.request.urlopen
        self.sleep = sleep or time.sleep
        # Multi-year archive downloads (e.g. 2020-2025 = ~2,200 daily requests)
        # hit data.binance.vision back-to-back with no delay otherwise, which
        # risks a 418 hard ban. A small fixed delay between successful
        # downloads keeps the request rate conservative without meaningfully
        # slowing down a 2000+ day backfill (a few minutes total).
        self.request_interval_seconds = request_interval_seconds

    def download_range(
        self,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        output_dir: Path | str,
        checkpoint_file: Path | str | None = None,
    ) -> ArchiveDownloadSummary:
        start = _parse_archive_date(start_date)
        end = _parse_archive_date(end_date)
        if start > end:
            raise ValueError("start_date must be on or before end_date")
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        checkpoint_path = Path(checkpoint_file) if checkpoint_file is not None else destination / "checkpoint.json"
        checkpoint = _load_archive_checkpoint(checkpoint_path)

        resume_after = checkpoint.get("last_completed_date")
        first_day = start
        if isinstance(resume_after, str) and resume_after:
            completed_day = _parse_archive_date(resume_after)
            if completed_day >= start:
                first_day = completed_day + timedelta(days=1)

        for current_day in _iter_archive_dates(first_day, end):
            try:
                downloaded_file = self._download_day(current_day, destination)
            except ArchiveHardBanError:
                _write_archive_checkpoint(checkpoint_path, checkpoint)
                LOGGER.error("hard ban while downloading Binance archive; stopping immediately")
                raise
            except (ArchiveDownloadError, ArchiveValidationError, OSError, ValueError) as error:
                failed_dates = _string_list(checkpoint.get("failed_dates"))
                current_iso = current_day.isoformat()
                if current_iso not in failed_dates:
                    failed_dates.append(current_iso)
                checkpoint["failed_dates"] = failed_dates
                _write_archive_checkpoint(checkpoint_path, checkpoint)
                LOGGER.error("failed to download Binance archive %s: %s", current_iso, error)
                continue

            downloaded_files = _string_list(checkpoint.get("downloaded_files"))
            if downloaded_file not in downloaded_files:
                downloaded_files.append(downloaded_file)
            failed_dates = [value for value in _string_list(checkpoint.get("failed_dates")) if value != current_day.isoformat()]
            checkpoint["last_completed_date"] = current_day.isoformat()
            checkpoint["downloaded_files"] = downloaded_files
            checkpoint["failed_dates"] = failed_dates
            _write_archive_checkpoint(checkpoint_path, checkpoint)
            if self.request_interval_seconds > 0.0:
                self.sleep(self.request_interval_seconds)

        return _archive_summary(destination, checkpoint_path, start, end, checkpoint)

    def _download_day(self, day: date, output_dir: Path) -> str:
        zip_name = f"{self.symbol}-{self.interval}-{day.isoformat()}.zip"
        csv_name = f"{self.symbol}-{self.interval}-{day.isoformat()}.csv"
        url = f"{self.base_url}/{zip_name}"
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-archive-crawler/0.1"})
        backoff_seconds = 1.0
        last_error: BaseException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with self.urlopen(request, timeout=self.timeout_seconds) as response:  # type: ignore[attr-defined]
                    payload = response.read()  # type: ignore[attr-defined]
                csv_text = _archive_csv_text_from_zip(bytes(payload))
                parse_archive_csv_text(csv_text)
                (output_dir / zip_name).write_bytes(bytes(payload))
                (output_dir / csv_name).write_text(csv_text, encoding="utf-8")
                return zip_name
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code == 418:
                    LOGGER.error("HTTP 418 hard ban while downloading %s", url)
                    raise ArchiveHardBanError(f"HTTP 418 hard ban while downloading {zip_name}") from error
                if error.code == 429:
                    if attempt >= self.max_retries:
                        break
                    self.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2.0, 60.0)
                    continue
                if error.code == 404:
                    raise ArchiveDownloadError(f"HTTP 404 archive file not found: {zip_name}") from error
                if attempt >= self.max_retries:
                    break
                self.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 60.0)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                self.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 60.0)
            except (zipfile.BadZipFile, UnicodeDecodeError, ArchiveValidationError, ValueError) as error:
                raise ArchiveValidationError(f"invalid archive CSV for {zip_name}: {error}") from error
        raise ArchiveDownloadError(f"failed downloading {zip_name} after {self.max_retries} attempts: {last_error}")


def parse_open_time(value: str) -> datetime:
    stripped = value.strip()
    if stripped.isdigit():
        number = int(stripped)
        seconds = number / 1000.0 if number > 10_000_000_000 else float(number)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_archive_csv_text(csv_text: str) -> list[data.Candle]:
    # Check if first line looks like a header (contains letters)
    first_line = csv_text.lstrip().splitlines()[0] if csv_text else ""
    has_header = any(c.isalpha() for c in first_line.split(",")[0]) if first_line else False

    candles: list[data.Candle] = []
    seen_open_times: set[datetime] = set()
    previous_open_time: datetime | None = None

    if has_header:
        # Standard DictReader for files with headers
        reader = csv.DictReader(io.StringIO(csv_text))
        fieldnames = reader.fieldnames or []
        missing = set(ARCHIVE_CSV_FIELDS) - set(fieldnames)
        if missing:
            raise ArchiveValidationError(f"archive CSV missing required columns: {', '.join(sorted(missing))}")
        for row in reader:
            open_time = parse_open_time(row["open_time"])
            if open_time in seen_open_times:
                raise ArchiveValidationError(f"archive CSV contains duplicate open_time: {open_time.isoformat()}")
            if previous_open_time is not None and open_time <= previous_open_time:
                raise ArchiveValidationError("archive CSV open_time values must be chronological")
            seen_open_times.add(open_time)
            previous_open_time = open_time
            open_price = float(row["open"])
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            volume = float(row["volume"])
            _validate_ohlcv(open_price, high, low, close, volume)
            candles.append(
                data.Candle(
                    open_time=open_time,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    quote_volume=float(row.get("quote_volume") or 0.0),
                    number_of_trades=int(float(row.get("count") or 0)),
                    taker_buy_base_volume=float(row.get("taker_buy_volume") or 0.0),
                    taker_buy_quote_volume=float(row.get("taker_buy_quote_volume") or 0.0),
                )
            )
    else:
        # No header: use standard Binance kline column order
        standard_fields = list(ARCHIVE_CSV_FIELDS)
        reader = csv.reader(io.StringIO(csv_text))
        for raw_row in reader:
            if len(raw_row) < len(standard_fields):
                continue  # Skip malformed rows
            row = {k: v for k, v in zip(standard_fields, raw_row)}
            open_time = parse_open_time(row["open_time"])
            if open_time in seen_open_times:
                raise ArchiveValidationError(f"archive CSV contains duplicate open_time: {open_time.isoformat()}")
            if previous_open_time is not None and open_time <= previous_open_time:
                raise ArchiveValidationError("archive CSV open_time values must be chronological")
            seen_open_times.add(open_time)
            previous_open_time = open_time
            open_price = float(row["open"])
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            volume = float(row["volume"])
            _validate_ohlcv(open_price, high, low, close, volume)
            candles.append(
                data.Candle(
                    open_time=open_time,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    quote_volume=float(row.get("quote_volume") or 0.0),
                    number_of_trades=int(float(row.get("count") or 0)),
                    taker_buy_base_volume=float(row.get("taker_buy_volume") or 0.0),
                    taker_buy_quote_volume=float(row.get("taker_buy_quote_volume") or 0.0),
                )
            )
    return candles


def load_archive_csv_candles(path: Path) -> list[data.Candle]:
    return parse_archive_csv_text(path.read_text(encoding="utf-8"))


def load_archive_zip_candles(path: Path) -> list[data.Candle]:
    return parse_archive_csv_text(_archive_csv_text_from_zip(path.read_bytes()))


def load_archive_candles(archive_dir: Path) -> list[data.Candle]:
    if not archive_dir.is_dir():
        raise ValueError(f"archive_dir does not exist or is not a directory: {archive_dir}")
    candles: list[data.Candle] = []
    csv_stems: set[str] = set()
    for csv_path in sorted(archive_dir.glob("*.csv")):
        csv_stems.add(csv_path.stem)
        candles.extend(load_archive_csv_candles(csv_path))
    for zip_path in sorted(archive_dir.glob("*.zip")):
        if zip_path.stem in csv_stems:
            continue
        candles.extend(load_archive_zip_candles(zip_path))
    if not candles:
        raise ValueError(f"archive_dir contains no archive CSV or zip files: {archive_dir}")
    merged_by_time: dict[datetime, data.Candle] = {}
    for candle in sorted(candles, key=lambda row: row.open_time):
        merged_by_time.setdefault(candle.open_time, candle)
    return list(merged_by_time.values())


def archive_row_count(archive_dir: Path) -> int:
    """Count all data rows in CSV files matching BTCUSDT-1m-*.csv in archive_dir."""
    total = 0
    for csv_path in archive_dir.glob("BTCUSDT-1m-*.csv"):
        with csv_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
            has_header = any(c.isalpha() for c in first_line.split(",")[0]) if first_line else False
            reader = csv.reader(handle)
            if not has_header:
                total += 1  # Count the first line we already read
            total += sum(1 for _ in reader)
    return total


def archive_date_coverage(archive_dir: Path) -> dict[str, object]:
    """Return coverage summary for BTCUSDT-1m-*.csv files in archive_dir."""
    files = sorted(archive_dir.glob("BTCUSDT-1m-*.csv"))
    if not files:
        return {
            "start_date": None,
            "end_date": None,
            "raw_rows": 0,
            "canonical_rows": 0,
            "missing_days": [],
            "files_found": 0,
        }
    dates: list[date] = []
    raw_rows = 0
    for csv_path in files:
        date_str = _extract_date_from_archive_filename(csv_path.name)
        dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # skip header
            raw_rows += sum(1 for _ in reader)
    start_date = min(dates)
    end_date = max(dates)
    try:
        canonical = load_archive_candles(archive_dir)
        canonical_rows = len(canonical)
    except ValueError:
        canonical_rows = raw_rows
    all_days = set(_iter_archive_dates(start_date, end_date))
    found_days = set(dates)
    missing_days = sorted([d.isoformat() for d in all_days - found_days])
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "raw_rows": raw_rows,
        "canonical_rows": canonical_rows,
        "missing_days": missing_days,
        "files_found": len(files),
    }


def _archive_csv_text_from_zip(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        csv_names = [name for name in names if name.lower().endswith(".csv")]
        if not csv_names:
            raise ArchiveValidationError("archive zip contains no CSV file")
        with archive.open(csv_names[0]) as handle:
            return handle.read().decode("utf-8-sig")


def _parse_archive_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo is not None else value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iter_archive_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _default_archive_checkpoint() -> dict[str, object]:
    return {"last_completed_date": None, "downloaded_files": [], "failed_dates": []}


def _load_archive_checkpoint(path: Path) -> dict[str, object]:
    if not path.exists():
        return _default_archive_checkpoint()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("archive checkpoint must be a JSON object")
    checkpoint = _default_archive_checkpoint()
    checkpoint["last_completed_date"] = payload.get("last_completed_date")
    checkpoint["downloaded_files"] = _string_list(payload.get("downloaded_files"))
    checkpoint["failed_dates"] = _string_list(payload.get("failed_dates"))
    return checkpoint


def _write_archive_checkpoint(path: Path, checkpoint: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_completed_date": checkpoint.get("last_completed_date"),
        "downloaded_files": _string_list(checkpoint.get("downloaded_files")),
        "failed_dates": _string_list(checkpoint.get("failed_dates")),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("archive checkpoint list fields must be lists")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("archive checkpoint list values must be strings")
        output.append(item)
    return output


def _archive_summary(output_dir: Path, checkpoint_file: Path, start: date, end: date, checkpoint: Mapping[str, object]) -> ArchiveDownloadSummary:
    total_days = (end - start).days + 1
    requested_dates = {day.isoformat() for day in _iter_archive_dates(start, end)}
    downloaded_files = tuple(_string_list(checkpoint.get("downloaded_files")))
    failed_dates = tuple(_string_list(checkpoint.get("failed_dates")))
    downloaded_days = sum(1 for filename in downloaded_files if _extract_date_from_archive_filename(filename) in requested_dates)
    failed_days = sum(1 for failed_date in failed_dates if failed_date in requested_dates)
    last_completed = checkpoint.get("last_completed_date")
    return ArchiveDownloadSummary(
        output_dir=output_dir,
        checkpoint_file=checkpoint_file,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        total_days=total_days,
        downloaded_days=downloaded_days,
        failed_days=failed_days,
        last_completed_date=last_completed if isinstance(last_completed, str) else None,
        downloaded_files=downloaded_files,
        failed_dates=failed_dates,
    )


def _extract_date_from_archive_filename(filename: str) -> str:
    # Extract date from BTCUSDT-1m-YYYY-MM-DD.zip or YYYY-MM-DD_BTCUSDT-1m.zip
    from re import search
    match = search(r"\d{4}-\d{2}-\d{2}", filename)
    return match.group(0) if match else filename[:10]


def load_csv_candles(path: Path) -> list[data.Candle]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"open_time", "open", "high", "low", "close", "volume"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        candles: list[data.Candle] = []
        seen_open_times: set[datetime] = set()
        for row in reader:
            open_time = parse_open_time(row["open_time"])
            if open_time in seen_open_times:
                raise ValueError(f"CSV contains duplicate open_time: {open_time.isoformat()}")
            seen_open_times.add(open_time)
            open_price = float(row["open"])
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            volume = float(row["volume"])
            _validate_ohlcv(open_price, high, low, close, volume)
            candles.append(
                data.Candle(
                    open_time=open_time,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    quote_volume=float(row.get("quote_volume") or 0.0),
                    number_of_trades=int(float(row.get("number_of_trades") or 0)),
                    taker_buy_base_volume=float(row.get("taker_buy_base_volume") or 0.0),
                    taker_buy_quote_volume=float(row.get("taker_buy_quote_volume") or 0.0),
                )
            )
    if candles and all(candle.volume == 0.0 for candle in candles):
        raise ValueError("CSV volume is zero for all rows")
    return sorted(candles, key=lambda candle: candle.open_time)


def _validate_ohlcv(open_price: float, high: float, low: float, close: float, volume: float) -> None:
    prices = (open_price, high, low, close)
    if any(not isfinite(value) for value in (*prices, volume)):
        raise ValueError("CSV OHLCV values must be finite")
    if any(value <= 0.0 for value in prices):
        raise ValueError("CSV OHLC prices must be positive")
    if volume < 0.0:
        raise ValueError("CSV volume must be non-negative")
    if high < low:
        raise ValueError("CSV high must be greater than or equal to low")
    if not low <= open_price <= high:
        raise ValueError("CSV open must be within high/low range")
    if not low <= close <= high:
        raise ValueError("CSV close must be within high/low range")


def candle_from_kline_row(row: Sequence[object]) -> data.Candle:
    if len(row) < 11:
        raise ValueError("kline row must have at least 11 fields")
    return data.Candle(
        open_time=parse_open_time(str(row[0])),
        open=float(str(row[1])),
        high=float(str(row[2])),
        low=float(str(row[3])),
        close=float(str(row[4])),
        volume=float(str(row[5])),
        quote_volume=float(str(row[7])),
        number_of_trades=int(float(str(row[8]))),
        taker_buy_base_volume=float(str(row[9])),
        taker_buy_quote_volume=float(str(row[10])),
    )


def write_candles_csv(path: Path, candles: Sequence[data.Candle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLLECTED_CSV_FIELDS)
        writer.writeheader()
        for candle in candles:
            writer.writerow(
                {
                    "open_time": candle.open_time.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "quote_volume": candle.quote_volume,
                    "number_of_trades": candle.number_of_trades,
                    "taker_buy_base_volume": candle.taker_buy_base_volume,
                    "taker_buy_quote_volume": candle.taker_buy_quote_volume,
                }
            )


def write_candles_parquet(path: Path, candles: Sequence[data.Candle]) -> None:
    """Write candles to Parquet format for faster I/O and compression."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc
    # Build arrow arrays
    open_times = [candle.open_time for candle in candles]
    opens = [candle.open for candle in candles]
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]
    volumes = [candle.volume for candle in candles]
    quote_volumes = [candle.quote_volume for candle in candles]
    number_of_trades = [candle.number_of_trades for candle in candles]
    taker_buy_base_volumes = [candle.taker_buy_base_volume for candle in candles]
    taker_buy_quote_volumes = [candle.taker_buy_quote_volume for candle in candles]
    table = pa.table(
        {
            "open_time": open_times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "quote_volume": quote_volumes,
            "number_of_trades": number_of_trades,
            "taker_buy_base_volume": taker_buy_base_volumes,
            "taker_buy_quote_volume": taker_buy_quote_volumes,
        }
    )
    pq.write_table(table, path)


def load_parquet_candles(path: Path) -> list[data.Candle]:
    """Read candles from Parquet format."""
    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc
    table = pq.read_table(path)
    columns = {name: table.column(name).to_pylist() for name in table.column_names}
    candles: list[data.Candle] = []
    for i in range(table.num_rows):
        open_time = columns["open_time"][i]
        if isinstance(open_time, str):
            open_time = datetime.fromisoformat(open_time)
        elif isinstance(open_time, int):
            open_time = datetime.fromtimestamp(open_time / 1000.0, tz=timezone.utc)
        candles.append(
            data.Candle(
                open_time=open_time,
                open=float(columns["open"][i]),
                high=float(columns["high"][i]),
                low=float(columns["low"][i]),
                close=float(columns["close"][i]),
                volume=float(columns["volume"][i]),
                quote_volume=float(columns["quote_volume"][i]),
                number_of_trades=int(columns["number_of_trades"][i]),
                taker_buy_base_volume=float(columns["taker_buy_base_volume"][i]),
                taker_buy_quote_volume=float(columns["taker_buy_quote_volume"][i]),
            )
        )
    return candles


def dataset_cache_dir(path: Path) -> Path:
    if path.suffix == ".pkl":
        return path.with_suffix(".parquet_cache")
    return path


def validate_dataset_cache_schema(
    stored_feature_names: Sequence[str],
    expected_feature_names: Sequence[str] | None = None,
    schema_version: int = DATASET_CACHE_SCHEMA_VERSION,
) -> DatasetCacheValidation:
    stored = tuple(str(name) for name in stored_feature_names)
    expected = tuple(str(name) for name in expected_feature_names) if expected_feature_names is not None else stored
    stored_set = set(stored)
    expected_set = set(expected)
    return DatasetCacheValidation(
        feature_count_matches=len(stored) == len(expected),
        missing_features=tuple(name for name in expected if name not in stored_set),
        extra_features=tuple(name for name in stored if name not in expected_set),
        schema_version=int(schema_version),
    )


def save_dataset_cache(path: Path, build: DatasetBuild) -> Path:
    cache_dir = dataset_cache_dir(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": DATASET_CACHE_SCHEMA_VERSION,
        "source": build.source,
        "symbol": build.symbol,
        "interval": build.interval,
        "raw_rows": build.raw_rows,
        "feature_names": list(build.feature_names),
        "label_horizon": build.label_horizon,
        "label_threshold": build.label_threshold,
        "gap_report": asdict(build.gap_report),
        "source_availability_report": build.source_availability_report or {},
    }
    with (cache_dir / DATASET_CACHE_METADATA_FILE).open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, default=_dataset_cache_json_default, indent=2, sort_keys=True)
    _write_feature_rows_parquet(cache_dir / DATASET_CACHE_FEATURE_ROWS_FILE, build.feature_rows, build.feature_names)
    _write_labeled_rows_parquet(cache_dir / DATASET_CACHE_LABELED_ROWS_FILE, build.labeled_rows, build.feature_names)
    write_candles_parquet(cache_dir / DATASET_CACHE_CANONICAL_FILE, build.canonical)
    return cache_dir


def load_dataset_cache(
    path: Path,
    *,
    expected_feature_names: Sequence[str] | None = None,
    allow_missing_features: bool = True,
    allow_pickle_fallback: bool = True,
) -> DatasetBuild:
    cache_dir = dataset_cache_dir(path)
    if cache_dir.exists():
        metadata = _read_dataset_cache_metadata(cache_dir)
        schema_version = int(metadata.get("schema_version", 0))
        if schema_version != DATASET_CACHE_SCHEMA_VERSION:
            raise ValueError(f"unsupported dataset cache schema version: {schema_version}")
        stored_feature_names = tuple(str(name) for name in metadata.get("feature_names", ()))
        _validate_dataset_cache_features(stored_feature_names, expected_feature_names, allow_missing_features, schema_version)
        feature_names = tuple(str(name) for name in expected_feature_names) if expected_feature_names is not None else stored_feature_names
        feature_rows = _load_feature_rows_parquet(
            cache_dir / DATASET_CACHE_FEATURE_ROWS_FILE,
            stored_feature_names=stored_feature_names,
            expected_feature_names=expected_feature_names,
            allow_missing_features=allow_missing_features,
        )
        labeled_rows = _load_labeled_rows_parquet(
            cache_dir / DATASET_CACHE_LABELED_ROWS_FILE,
            stored_feature_names=stored_feature_names,
            expected_feature_names=expected_feature_names,
            allow_missing_features=allow_missing_features,
        )
        canonical = load_parquet_candles(cache_dir / DATASET_CACHE_CANONICAL_FILE)
        return DatasetBuild(
            source=str(metadata.get("source", "")),
            symbol=str(metadata.get("symbol", "BTCUSDT")),
            interval=str(metadata.get("interval", "1m")),
            raw_rows=int(metadata.get("raw_rows", len(canonical))),
            canonical=canonical,
            gap_report=_gap_report_from_metadata(metadata.get("gap_report", {})),
            feature_rows=feature_rows,
            labeled_rows=labeled_rows,
            feature_names=feature_names,
            label_horizon=int(metadata.get("label_horizon", 0)),
            label_threshold=float(metadata.get("label_threshold", 0.0)),
            source_availability_report=_metadata_mapping(metadata.get("source_availability_report", {})),
        )
    if allow_pickle_fallback and path.exists():
        with path.open("rb") as handle:
            build = pickle.load(handle)
        if not isinstance(build, DatasetBuild):
            raise TypeError("pickle dataset cache did not contain a DatasetBuild")
        save_dataset_cache(path, build)
        return load_dataset_cache(
            path,
            expected_feature_names=expected_feature_names,
            allow_missing_features=allow_missing_features,
            allow_pickle_fallback=False,
        )
    raise FileNotFoundError(cache_dir)


def save_feature_rows_cache(path: Path, rows: Sequence[FeatureRow], feature_names: Sequence[str]) -> Path:
    cache_dir = dataset_cache_dir(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / DATASET_CACHE_FEATURE_ROWS_FILE
    _write_feature_rows_parquet(output_path, rows, feature_names)
    return output_path


def load_feature_rows_cache(
    path: Path,
    *,
    expected_feature_names: Sequence[str] | None = None,
    allow_missing_features: bool = True,
) -> list[FeatureRow]:
    cache_dir = dataset_cache_dir(path)
    return _load_feature_rows_parquet(
        cache_dir / DATASET_CACHE_FEATURE_ROWS_FILE,
        stored_feature_names=None,
        expected_feature_names=expected_feature_names,
        allow_missing_features=allow_missing_features,
    )


def _dataset_cache_json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _read_dataset_cache_metadata(cache_dir: Path) -> dict[str, object]:
    with (cache_dir / DATASET_CACHE_METADATA_FILE).open("r", encoding="utf-8") as handle:
        data_loaded = json.load(handle)
    if not isinstance(data_loaded, dict):
        raise ValueError("dataset cache metadata must be a JSON object")
    return data_loaded


def _validate_dataset_cache_features(
    stored_feature_names: Sequence[str],
    expected_feature_names: Sequence[str] | None,
    allow_missing_features: bool,
    schema_version: int = DATASET_CACHE_SCHEMA_VERSION,
) -> DatasetCacheValidation:
    validation = validate_dataset_cache_schema(stored_feature_names, expected_feature_names, schema_version)
    if expected_feature_names is None:
        return validation
    if validation.missing_features:
        message = "dataset cache missing expected features: " + ", ".join(validation.missing_features)
        if allow_missing_features:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        else:
            raise ValueError(message)
    if not allow_missing_features and (validation.extra_features or not validation.feature_count_matches):
        details: list[str] = []
        if validation.extra_features:
            details.append("extra features: " + ", ".join(validation.extra_features))
        if not validation.feature_count_matches:
            details.append("feature count mismatch")
        raise ValueError("dataset cache feature schema mismatch" + (": " + "; ".join(details) if details else ""))
    return validation


def _write_feature_rows_parquet(path: Path, rows: Sequence[FeatureRow], feature_names: Sequence[str]) -> None:
    _write_rows_parquet(path, rows, feature_names, labeled=False)


def _write_labeled_rows_parquet(path: Path, rows: Sequence[LabeledRow], feature_names: Sequence[str]) -> None:
    _write_rows_parquet(path, rows, feature_names, labeled=True)


def _write_rows_parquet(path: Path, rows: Sequence[FeatureRow] | Sequence[LabeledRow], feature_names: Sequence[str], *, labeled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc

    arrays: dict[str, object] = {
        "index": pa.array([row.index for row in rows], type=pa.int64()),
        "open_time": pa.array([_as_utc_datetime(row.open_time) for row in rows], type=pa.timestamp("us", tz="UTC")),
        "gap_flag": pa.array([row.gap_flag for row in rows], type=pa.int64()),
        "repaired": pa.array([row.repaired for row in rows], type=pa.bool_()),
        "warmup_invalid": pa.array([row.warmup_invalid for row in rows], type=pa.bool_()),
        "user_regime": pa.array([row.user_regime for row in rows], type=pa.string()),
        "source_availability_status_json": pa.array([_json_dump(row.source_availability_status) for row in rows], type=pa.string()),
        "feature_availability_status_json": pa.array([_json_dump(row.feature_availability_status) for row in rows], type=pa.string()),
        "unavailable_sources_json": pa.array([_json_dump(list(row.unavailable_sources)) for row in rows], type=pa.string()),
        "fallback_features_json": pa.array([_json_dump(list(row.fallback_features)) for row in rows], type=pa.string()),
    }
    if labeled:
        labeled_rows = rows  # type: ignore[assignment]
        arrays.update(
            {
                "label": pa.array([row.label for row in labeled_rows], type=pa.int64()),
                "label_reason": pa.array([row.label_reason for row in labeled_rows], type=pa.string()),
                "target_return": pa.array([row.target_return for row in labeled_rows], type=pa.float64()),
                "targets_json": pa.array([_json_dump(row.targets) for row in labeled_rows], type=pa.string()),
                "target_reasons_json": pa.array([_json_dump(row.target_reasons) for row in labeled_rows], type=pa.string()),
            }
        )
    for name in feature_names:
        feature_name = str(name)
        arrays[_feature_column_name(feature_name)] = pa.array(
            [_nullable_float(row.features.get(feature_name)) for row in rows], type=pa.float64()
        )
    pq.write_table(pa.table(arrays), path)


def _load_feature_rows_parquet(
    path: Path,
    *,
    stored_feature_names: Sequence[str] | None,
    expected_feature_names: Sequence[str] | None,
    allow_missing_features: bool,
) -> list[FeatureRow]:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc
    table = pq.read_table(path)
    columns = {name: table.column(name).to_pylist() for name in table.column_names}
    stored = tuple(str(name) for name in stored_feature_names) if stored_feature_names is not None else _infer_feature_names(table.column_names, expected_feature_names, labeled=False)
    _validate_dataset_cache_features(stored, expected_feature_names, allow_missing_features)
    feature_names = tuple(str(name) for name in expected_feature_names) if expected_feature_names is not None else stored
    rows: list[FeatureRow] = []
    for index in range(table.num_rows):
        rows.append(
            FeatureRow(
                index=int(columns["index"][index]),
                open_time=_datetime_from_cache_value(columns["open_time"][index]),
                features=_features_from_columns(columns, index, feature_names),
                gap_flag=int(columns["gap_flag"][index]),
                repaired=bool(columns["repaired"][index]),
                warmup_invalid=bool(columns["warmup_invalid"][index]),
                source_availability_status=_json_dict_str(columns.get("source_availability_status_json", [None] * table.num_rows)[index]),
                feature_availability_status=_json_dict_str(columns.get("feature_availability_status_json", [None] * table.num_rows)[index]),
                unavailable_sources=_json_tuple_str(columns.get("unavailable_sources_json", [None] * table.num_rows)[index]),
                fallback_features=_json_tuple_str(columns.get("fallback_features_json", [None] * table.num_rows)[index]),
                user_regime=columns.get("user_regime", [None] * table.num_rows)[index],
            )
        )
    return rows


def _load_labeled_rows_parquet(
    path: Path,
    *,
    stored_feature_names: Sequence[str],
    expected_feature_names: Sequence[str] | None,
    allow_missing_features: bool,
) -> list[LabeledRow]:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc
    table = pq.read_table(path)
    columns = {name: table.column(name).to_pylist() for name in table.column_names}
    _validate_dataset_cache_features(stored_feature_names, expected_feature_names, allow_missing_features)
    feature_names = tuple(str(name) for name in expected_feature_names) if expected_feature_names is not None else tuple(str(name) for name in stored_feature_names)
    rows: list[LabeledRow] = []
    for index in range(table.num_rows):
        rows.append(
            LabeledRow(
                index=int(columns["index"][index]),
                open_time=_datetime_from_cache_value(columns["open_time"][index]),
                features=_features_from_columns(columns, index, feature_names),
                label=int(columns["label"][index]),
                label_reason=str(columns["label_reason"][index]),
                target_return=float(columns["target_return"][index]),
                gap_flag=int(columns["gap_flag"][index]),
                repaired=bool(columns["repaired"][index]),
                warmup_invalid=bool(columns["warmup_invalid"][index]),
                source_availability_status=_json_dict_str(columns.get("source_availability_status_json", [None] * table.num_rows)[index]),
                feature_availability_status=_json_dict_str(columns.get("feature_availability_status_json", [None] * table.num_rows)[index]),
                unavailable_sources=_json_tuple_str(columns.get("unavailable_sources_json", [None] * table.num_rows)[index]),
                fallback_features=_json_tuple_str(columns.get("fallback_features_json", [None] * table.num_rows)[index]),
                targets=_json_dict_int(columns.get("targets_json", [None] * table.num_rows)[index]),
                target_reasons=_json_dict_str(columns.get("target_reasons_json", [None] * table.num_rows)[index]),
                user_regime=columns.get("user_regime", [None] * table.num_rows)[index],
            )
        )
    return rows


def _infer_feature_names(column_names: Sequence[str], expected_feature_names: Sequence[str] | None, *, labeled: bool) -> tuple[str, ...]:
    reserved = {
        "index",
        "open_time",
        "gap_flag",
        "repaired",
        "warmup_invalid",
        "user_regime",
        "source_availability_status_json",
        "feature_availability_status_json",
        "unavailable_sources_json",
        "fallback_features_json",
    }
    if labeled:
        reserved.update({"label", "label_reason", "target_return", "targets_json", "target_reasons_json"})
    inferred = [
        name[len(_FEATURE_COLUMN_PREFIX):] if name.startswith(_FEATURE_COLUMN_PREFIX) else name
        for name in column_names
        if name.startswith(_FEATURE_COLUMN_PREFIX) or name not in reserved
    ]
    if expected_feature_names is not None:
        for name in expected_feature_names:
            if _feature_column_name(str(name)) in column_names and name not in inferred:
                inferred.append(str(name))
    return tuple(inferred)


def _features_from_columns(columns: Mapping[str, Sequence[object]], row_index: int, feature_names: Sequence[str]) -> FeatureVector:
    output: dict[str, float] = {}
    for name in feature_names:
        column = _feature_column_name(str(name))
        if column in columns:
            value = columns[column][row_index]
            output[name] = 0.0 if value is None else float(value)
        else:
            output[name] = 0.0
    return FeatureVector.from_mapping(output)


def _gap_report_from_metadata(value: object) -> GapReport:
    report = _metadata_mapping(value)
    return GapReport(
        raw_rows=int(report.get("raw_rows", 0)),
        canonical_rows=int(report.get("canonical_rows", 0)),
        repaired_rows=int(report.get("repaired_rows", 0)),
        gap_ratio_total=float(report.get("gap_ratio_total", 0.0)),
        max_gap_run=int(report.get("max_gap_run", 0)),
        first_open_time=str(report.get("first_open_time", "")),
        last_open_time=str(report.get("last_open_time", "")),
    )


def _metadata_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_dump(value: object) -> str:
    return json.dumps(value, default=_dataset_cache_json_default, sort_keys=True)


def _json_load(value: object, default: object) -> object:
    if value is None or value == "":
        return default
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        return default
    return json.loads(value)


def _json_dict_str(value: object) -> dict[str, str]:
    loaded = _json_load(value, {})
    if not isinstance(loaded, Mapping):
        return {}
    return {str(key): str(item) for key, item in loaded.items()}


def _json_dict_int(value: object) -> dict[str, int]:
    loaded = _json_load(value, {})
    if not isinstance(loaded, Mapping):
        return {}
    return {str(key): int(item) for key, item in loaded.items()}


def _json_tuple_str(value: object) -> tuple[str, ...]:
    loaded = _json_load(value, [])
    if not isinstance(loaded, Sequence) or isinstance(loaded, (str, bytes)):
        return ()
    return tuple(str(item) for item in loaded)


def _nullable_float(value: object) -> float | None:
    return None if value is None else float(value)


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _datetime_from_cache_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return _as_utc_datetime(value)
    if isinstance(value, str):
        return _as_utc_datetime(datetime.fromisoformat(value))
    if isinstance(value, (int, float)):
        scale = 1000.0 if abs(float(value)) > 10_000_000_000 else 1.0
        return datetime.fromtimestamp(float(value) / scale, tz=timezone.utc)
    raise TypeError(f"unsupported cached datetime value: {value!r}")


def _interval_to_ms(interval: str) -> int:
    mapping = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000, "1M": 2_592_000_000}
    return mapping.get(interval, 60_000)


def collect_candles(
    output_path: Path,
    rows: int = 240,
    allow_public_network: bool = False,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    format: str = "csv",
) -> CollectionResult:
    if rows <= 0:
        raise ValueError("rows must be positive")
    if allow_public_network:
        downloader = PublicKlineDownloader(allow_network=True)
        if rows > 1500:
            # Use pagination for large requests with rate-limit backoff between batches
            # Compute start_time_ms to go back far enough to collect 'rows' candles
            interval_ms = _interval_to_ms(interval)
            end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_time_ms = end_time_ms - (rows * interval_ms)
            candles = downloader.fetch_klines_paginated(
                symbol=symbol, interval=interval, start_time_ms=start_time_ms, end_time_ms=end_time_ms, max_rows=rows
            )
        else:
            candles = downloader.fetch_klines(symbol=symbol, interval=interval, limit=rows)
        source = "binance_public_klines"
        network_used = True
    else:
        candles = expanded_fixture(rows)
        source = "offline_expanded_fixture"
        network_used = False
    if format == "parquet":
        write_candles_parquet(output_path, candles)
    else:
        write_candles_csv(output_path, candles)
    return CollectionResult(output_path, source, symbol, interval, len(candles), network_used)


def expanded_fixture(rows: int = 6000) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 1, 0, 0)
    missing_minutes = {37, 38, 119, 177}
    candles: list[data.Candle] = []
    previous_close = 100000.0
    for index in range(rows):
        if index in missing_minutes:
            continue
        cycle = sin(index / 5.0) * 45.0 + sin(index / 17.0) * 95.0
        drift = (index % 29) * 1.5
        open_price = previous_close
        close = 100000.0 + cycle + drift
        high = max(open_price, close) + 18.0 + (index % 7)
        low = min(open_price, close) - 18.0 - (index % 5)
        volume = 8.0 + (index % 11) + abs(sin(index / 3.0)) * 4.0
        candles.append(
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=round(open_price, 8),
                high=round(high, 8),
                low=round(low, 8),
                close=round(close, 8),
                volume=round(volume, 8),
                quote_volume=round(volume * close, 8),
                number_of_trades=100 + (index % 17),
                taker_buy_base_volume=round(volume * (0.45 + (index % 9) * 0.01), 8),
                taker_buy_quote_volume=round(volume * close * (0.45 + (index % 9) * 0.01), 8),
            )
        )
        previous_close = close
    return candles


def resolve_user_regime(open_time: datetime, periods: Sequence[UserRegimePeriod]) -> str | None:
    """Return user regime for open_time using half-open intervals [start, end_exclusive)."""
    for period in periods:
        if period.start <= open_time < period.end_exclusive:
            return period.regime
    return None


def load_user_regime_periods(path: Path) -> list[UserRegimePeriod]:
    """Load user-specified regime periods from JSON file.

    Expected format:
    {
        "periods": [
            {"regime": "up", "start": "2020-01-01", "end_exclusive": "2020-02-13"},
            ...
        ]
    }
    """
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    periods_data = data.get("periods", []) if isinstance(data, dict) else data
    periods: list[UserRegimePeriod] = []
    for item in periods_data:
        regime = str(item["regime"]).lower()
        if regime not in USER_REGIME_NAMES:
            raise ValueError(f"invalid regime '{regime}'; must be one of {USER_REGIME_NAMES}")
        start = datetime.fromisoformat(str(item["start"])).replace(tzinfo=timezone.utc)
        end_exclusive = datetime.fromisoformat(str(item["end_exclusive"])).replace(tzinfo=timezone.utc)
        periods.append(UserRegimePeriod(regime=regime, start=start, end_exclusive=end_exclusive))
    return periods


def build_dataset(
    input_path: Path | None = None,
    stream_buffer: Sequence[data.Candle] | None = None,
    horizon: int = 60,
    label_threshold: float = 0.001,
    tp_pct: float = DEFAULT_LABEL_TP_PCT,
    sl_pct: float = DEFAULT_LABEL_SL_PCT,
    external_events: Mapping[object, object] | None = None,
    archive_dir: Path | None = None,
    source_bundle: sources.MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
    user_regime_periods: Sequence[UserRegimePeriod] | None = None,
) -> DatasetBuild:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if tp_pct <= 0.0:
        raise ValueError("tp_pct must be positive")
    if sl_pct <= 0.0:
        raise ValueError("sl_pct must be positive")
    supplied_sources = sum(1 for value in (input_path, stream_buffer, archive_dir) if value is not None)
    if supplied_sources > 1:
        raise ValueError("input_path, stream_buffer, and archive_dir are mutually exclusive")
    if archive_dir is not None:
        raw = load_archive_candles(archive_dir)
        source = archive_dir.as_posix()
    elif stream_buffer is not None:
        raw = list(stream_buffer)
        source = "live_stream_buffer"
    elif input_path is None:
        raw = expanded_fixture()
        source = "offline_expanded_fixture"
    else:
        if input_path.suffix.lower() == ".parquet":
            raw = load_parquet_candles(input_path)
        else:
            raw = load_csv_candles(input_path)
        source = input_path.as_posix()
    canonical = data.CanonicalTimelineBuilder().build(raw)
    gap_report = summarize_gaps(len(raw), canonical)
    resolved_source_bundle = source_bundle or sources.bundle_from_candles(canonical, source=source)
    # Handle per-candle external_sources: extract first entry for source report
    source_report_external_sources: Mapping[str, object] | None = None
    if external_sources is not None and any(isinstance(key, datetime) for key in external_sources.keys()):
        first_key = next(iter(external_sources.keys()))
        source_report_external_sources = external_sources[first_key]  # type: ignore[index]
    else:
        source_report_external_sources = external_sources
    feature_rows = build_feature_rows(canonical, source_bundle=resolved_source_bundle, external_sources=external_sources, user_regime_periods=user_regime_periods)
    labeled_rows = attach_labels(
        feature_rows,
        canonical,
        horizon,
        label_threshold,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        external_events=external_events,
        include_warmup=input_path is not None or archive_dir is not None,
    )
    # Exclude warmup rows: first 50 weeks have unreliable weekly MA features
    # Only apply for large datasets where meaningful training data remains
    WEEKLY_WARMUP_BARS = 50 * 7 * 24 * 60  # 504000
    if len(canonical) >= WEEKLY_WARMUP_BARS + 80:
        labeled_rows = [row for row in labeled_rows if row.index >= WEEKLY_WARMUP_BARS]
    source_report = sources.train_live_feature_parity_report(
        FEATURE_NAMES,
        source_bundle=resolved_source_bundle,
        external_sources=source_report_external_sources,
        feature_registry=feature_formula_registry()["features"],
    )
    return DatasetBuild(
        source=source,
        symbol="BTCUSDT",
        interval="1m",
        raw_rows=len(raw),
        canonical=canonical,
        gap_report=gap_report,
        feature_rows=feature_rows,
        labeled_rows=labeled_rows,
        feature_names=FEATURE_NAMES,
        label_horizon=horizon,
        label_threshold=label_threshold,
        source_bundle=resolved_source_bundle,
        source_availability_report=source_report,
    )


def summarize_gaps(raw_rows: int, canonical: Sequence[data.Candle]) -> GapReport:
    if not canonical:
        return GapReport(raw_rows, 0, 0, 0.0, 0, "", "")
    repaired_rows = sum(candle.gap_flag for candle in canonical)
    return GapReport(
        raw_rows=raw_rows,
        canonical_rows=len(canonical),
        repaired_rows=repaired_rows,
        gap_ratio_total=repaired_rows / len(canonical),
        max_gap_run=data.max_gap_run([candle.gap_flag for candle in canonical], len(canonical)),
        first_open_time=canonical[0].open_time.isoformat(),
        last_open_time=canonical[-1].open_time.isoformat(),
    )


def build_feature_rows(
    candles: Sequence[data.Candle],
    source_bundle: sources.MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
    user_regime_periods: Sequence[UserRegimePeriod] | None = None,
    _parallel: bool = True,
    _precomputed_weekly: Mapping[str, Sequence[float]] | None = None,
) -> list[FeatureRow]:
    # Parallel processing for large datasets
    if _parallel and len(candles) > 50000:
        return _build_feature_rows_parallel(
            candles, source_bundle, external_sources, user_regime_periods
        )
    # Support per-candle external_sources: Mapping[datetime, Mapping[str, object]]
    # or single external_sources for all candles: Mapping[str, object]
    per_candle_external_sources: Mapping[datetime, Mapping[str, object]] | None = None
    single_external_sources: Mapping[str, object] | None = None
    if external_sources is not None:
        # Check if it's a per-candle mapping (keys are datetimes)
        if any(isinstance(key, datetime) for key in external_sources.keys()):
            per_candle_external_sources = external_sources  # type: ignore[assignment]
        else:
            single_external_sources = external_sources
    rows: list[FeatureRow] = []
    resolved_source_bundle = source_bundle or sources.bundle_from_candles(candles, source="feature_rows")
    source_report = sources.train_live_feature_parity_report(
        FEATURE_NAMES,
        source_bundle=resolved_source_bundle,
        external_sources=external_sources,
        feature_registry=feature_formula_registry()["features"],
    )
    source_availability_status = _source_availability_status(source_report)
    feature_availability_status = dict(source_report.get("feature_source_status", {}))
    unavailable_sources = tuple(str(value) for value in source_report.get("unavailable_sources", ()))
    fallback_features = tuple(str(value) for value in source_report.get("fallback_features", ()))
    opens = [candle.open for candle in candles]
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]
    volumes = [candle.volume for candle in candles]
    quote_volumes = [candle.quote_volume for candle in candles]
    trades = [float(candle.number_of_trades) for candle in candles]
    ranges = [_range_value(candle) for candle in candles]
    range_pcts = [_range_pct(candle) for candle in candles]

    # ---- NumPy arrays for vectorized rolling reductions ----
    # The list copies above remain for the few helpers still consumed as
    # sequences; we materialize float arrays once and reuse them everywhere.
    opens_np = np.asarray(opens, dtype=float)
    highs_np = np.asarray(highs, dtype=float)
    lows_np = np.asarray(lows, dtype=float)
    closes_np = np.asarray(closes, dtype=float)
    volumes_np = np.asarray(volumes, dtype=float)
    quote_volumes_np = np.asarray(quote_volumes, dtype=float)
    trades_np = np.asarray(trades, dtype=float)
    ranges_np = np.asarray(ranges, dtype=float)
    range_pcts_np = np.asarray(range_pcts, dtype=float)

    # Returns (every lookback used in the per-candle loop)
    return_1_np  = _np_return_series(closes_np, 1)
    return_3_np  = _np_return_series(closes_np, 3)
    return_5_np  = _np_return_series(closes_np, 5)
    return_10_np = _np_return_series(closes_np, 10)
    return_15_np = _np_return_series(closes_np, 15)
    return_30_np = _np_return_series(closes_np, 30)
    return_60_np = _np_return_series(closes_np, 60)
    log_return_1_np = _np_log_return_series(closes_np, 1)
    log_return_5_np = _np_log_return_series(closes_np, 5)

    # SMAs and ratio-to-mean
    sma_5_np  = _np_rolling_mean_strict(closes_np, 5)
    sma_20_np = _np_rolling_mean_strict(closes_np, 20)
    sma_60_np = _np_rolling_mean_strict(closes_np, 60)
    close_sma_5_ratio_np  = _np_ratio_to_mean_series(closes_np, 5)
    close_sma_10_ratio_np = _np_ratio_to_mean_series(closes_np, 10)
    close_sma_20_ratio_np = _np_ratio_to_mean_series(closes_np, 20)
    close_sma_60_ratio_np = _np_ratio_to_mean_series(closes_np, 60)
    volume_sma_5_ratio_np   = _np_ratio_to_mean_series(volumes_np, 5)
    volume_sma_20_ratio_np  = _np_ratio_to_mean_series(volumes_np, 20)
    volume_sma_60_ratio_np  = _np_ratio_to_mean_series(volumes_np, 60)
    quote_vol_sma_20_ratio_np = _np_ratio_to_mean_series(quote_volumes_np, 20)
    trade_count_ratio_np = _np_ratio_to_mean_series(trades_np, 20)
    range_sma_20_ratio_np = _np_ratio_to_mean_series(ranges_np, 20)

    # Zscores
    close_zscore_20_np  = _np_zscore_series(closes_np, 20)
    close_zscore_60_np  = _np_zscore_series(closes_np, 60)
    volume_zscore_5_np  = _np_zscore_series(volumes_np, 5)
    volume_zscore_20_np = _np_zscore_series(volumes_np, 20)
    trade_count_zscore_20_np = _np_zscore_series(trades_np, 20)
    range_zscore_20_np = _np_zscore_series(range_pcts_np, 20)
    # Indicator zscore / ratio-to-mean over rv_5 and rv_15 require rv arrays
    # built below; we'll compute them once those exist.

    # Trend slopes
    trend_slope_10_np = _np_trend_slope_series(closes_np, 10)
    trend_slope_30_np = _np_trend_slope_series(closes_np, 30)

    # Rolling return extremes
    rolling_return_max_20_np = _np_rolling_return_extreme_series(closes_np, 20, True)
    rolling_return_min_20_np = _np_rolling_return_extreme_series(closes_np, 20, False)

    # Rolling extremes on highs/lows for distance-to-extreme features
    rolling_high_20_np = _np_rolling_max_strict(highs_np, 20)
    rolling_low_20_np  = _np_rolling_min_strict(lows_np, 20)

    # Volatility (Parkinson / Garman-Klass)
    parkinson_vol_20_np = _np_parkinson_vol_series(highs_np, lows_np, 20)
    garman_klass_vol_20_np = _np_garman_klass_vol_series(opens_np, highs_np, lows_np, closes_np, 20)
    range_vol_20_np = _np_rolling_std_strict(range_pcts_np, 20)

    # Inside/outside bar flags
    inside_bar_flag_np = _np_inside_bar_flag_series(highs_np, lows_np)
    outside_bar_flag_np = _np_outside_bar_flag_series(highs_np, lows_np)

    # Pre-compute weekly features once for all rows.
    #
    # CRITICAL (parallel correctness): weekly MA20/MA50 features need up to
    # 50 completed weekly closes (~504,000 1m bars) of history. A parallel
    # chunk (<=250k + 6k overlap bars, ~25 weeks) can NEVER satisfy
    # `len(weekly) >= 50` inside weekly_features.compute_weekly_features, so
    # computing weekly features per-chunk silently zeroes out all seven
    # weekly_* / close_vs_weekly_* features on every parallel run. The
    # parallel parent therefore computes them ONCE over the FULL candle
    # series and hands each worker its aligned slice via
    # ``_precomputed_weekly``; only the serial path computes them here.
    if _precomputed_weekly is not None:
        weekly_feature_values: Mapping[str, Sequence[float]] = _precomputed_weekly
    else:
        weekly_feature_values = weekly_features.compute_weekly_features(candles)
    # Pre-compute F17 multi-timeframe (15m/1h/4h/24h-rolling) features once.
    # Pure function of candles already in hand -- no external source needed.
    mtf_feature_values = mtf_features.compute_mtf_features_to_minutes(candles)
    # Pre-compute F15 momentum indicators once for all rows (optimized O(n))
    rsi_7_values = _rsi_series(closes, 7)
    rsi_14_values = _rsi_series(closes, 14)
    ema_12_values = _ema_series(closes, 12)
    ema_26_values = _ema_series(closes, 26)
    macd_line_values = [ema_12_values[i] - ema_26_values[i] for i in range(len(candles))]
    macd_signal_values = _ema_series(macd_line_values, 9)
    bb_width_20_values, bb_percent_b_values = _bb_series(closes, 20)
    ema_5_slope_values = _ema_slope_series(closes, 5, 5)
    ema_20_slope_values = _ema_slope_series(closes, 20, 10)
    ema_60_slope_values = _ema_slope_series(closes, 60, 10)
    rolling_vwap_20_values = _rolling_vwap_series(closes, volumes, 20)
    rolling_vwap_60_values = _rolling_vwap_series(closes, volumes, 60)
    range_high_20_values = _range_high_series(highs, 20)
    range_low_20_values = _range_low_series(lows, 20)
    range_mid_20_values = _range_mid_series(range_high_20_values, range_low_20_values)
    range_position_20_values = _range_position_series(closes, range_low_20_values, range_high_20_values)
    fake_break_low_values = _fake_break_low_series(opens, closes, range_low_20_values)
    fake_break_high_values = _fake_break_high_series(opens, closes, range_high_20_values)
    close_back_inside_range_values = _close_back_inside_range_series(closes, range_low_20_values, range_high_20_values)
    vwap_deviation_zscore_values = _vwap_deviation_zscore_series(closes, rolling_vwap_20_values, 20)
    # Rolling return-std series: precomputed once per window (O(n) total per window)
    # instead of recomputing the full window every candle inside the per-candle loop.
    rv_5_values = _rolling_return_std_series(closes, 5)
    rv_15_values = _rolling_return_std_series(closes, 15)
    rv_30_values = _rolling_return_std_series(closes, 30)
    rv_60_values = _rolling_return_std_series(closes, 60)
    rv_120_values = _rolling_return_std_series(closes, 120)
    atr_pct_14_values = _atr_pct_series(candles, 14)
    atr_pct_30_values = _atr_pct_series(candles, 30)

    # Indicator zscore / ratio-to-mean: rv_5/rv_15 over a 60-bar window.
    # Inline the same prefix-sum recipe as _np_zscore_series / _np_ratio_to_mean_series,
    # operating on the rv arrays.
    rv_5_np  = np.asarray(rv_5_values, dtype=float)
    rv_15_np = np.asarray(rv_15_values, dtype=float)
    rv_zscore_60_np = _np_zscore_series(rv_5_np, 60)
    volatility_regime_60_np = _np_ratio_to_mean_series(rv_15_np, 60)

    # Pass the candle count so features that cannot be computed on this
    # dataset (min_samples > len(candles), e.g. weekly MA50 on a short
    # fixture) do not invalidate every row. On full multi-year data this is
    # unchanged (504,000).
    warmup_cutoff = max_feature_min_samples(len(candles)) - 1
    # Stateless helpers — instantiate once outside the per-candle loop
    clipper = features.FeatureClipper()
    nan_classifier = features.NaNSourceClassifier(optional_noncritical_features=set(fallback_features))
    for index, candle in enumerate(candles):
        warmup_invalid = index < warmup_cutoff
        return_1 = float(return_1_np[index])
        return_3 = float(return_3_np[index])
        return_5 = float(return_5_np[index])
        return_10 = float(return_10_np[index])
        return_15 = float(return_15_np[index])
        return_30 = float(return_30_np[index])
        return_60 = float(return_60_np[index])
        momentum_10 = return_10
        momentum_30 = return_30
        sma_5 = float(sma_5_np[index])
        sma_20 = float(sma_20_np[index])
        sma_60 = float(sma_60_np[index])
        ema_12 = ema_12_values[index]
        ema_26 = ema_26_values[index]
        ema_12_26_spread = _spread_to_close(ema_12, ema_26, candle.close)
        sma_20_60_spread = _spread_to_close(sma_20, sma_60, candle.close)
        rv_15 = rv_15_values[index]
        rv_5 = rv_5_values[index]
        rv_30 = rv_30_values[index]
        rv_60 = rv_60_values[index]
        rv_120 = rv_120_values[index]
        atr_pct = atr_pct_14_values[index]
        atr_pct_30 = atr_pct_30_values[index]
        volatility_denominator = _positive_denominator(rv_15, rv_60, rv_120, atr_pct)
        rv_60_denominator = _positive_denominator(rv_60)
        close_zscore_20 = float(close_zscore_20_np[index])
        close_zscore_60 = float(close_zscore_60_np[index])
        volume_zscore_5 = float(volume_zscore_5_np[index])
        volume_zscore_20 = float(volume_zscore_20_np[index])
        trade_count_zscore_20 = float(trade_count_zscore_20_np[index])
        high_low_range = range_pcts[index]
        body_pct = _body_pct(candle)
        upper_shadow_raw = max(0.0, candle.high - max(candle.open, candle.close))
        lower_shadow_raw = max(0.0, min(candle.open, candle.close) - candle.low)
        upper_shadow = _divide(upper_shadow_raw, candle.close)
        lower_shadow = _divide(lower_shadow_raw, candle.close)
        taker_ratio = _divide(candle.taker_buy_base_volume, candle.volume)
        taker_imbalance = _divide(candle.taker_buy_base_volume - (candle.volume - candle.taker_buy_base_volume), candle.volume)
        taker_quote_ratio = _divide(candle.taker_buy_quote_volume, candle.quote_volume)
        range_value = ranges[index]
        candle_external_sources = per_candle_external_sources.get(candle.open_time) if per_candle_external_sources else single_external_sources
        # One dict lookup per candle for the MTF block instead of one per MTF
        # feature name. pop() (not get()) removes each minute's MTF dict from
        # the intermediate as it is consumed -- the minute is used exactly once
        # and mtf_feature_values is not referenced after this loop -- so the
        # ~2.8M-entry intermediate shrinks as `rows` grows instead of both being
        # held at full size simultaneously (lower peak build memory). The shared
        # empty dict avoids allocating a throwaway {} default on warmup misses.
        mtf_row = mtf_feature_values.pop(candle.open_time, None) or _EMPTY_MTF_ROW
        values = {
            "return_1": return_1,
            "return_3": return_3,
            "return_5": return_5,
            "return_10": return_10,
            "return_15": return_15,
            "return_30": return_30,
            "return_60": return_60,
            "log_return_1": float(log_return_1_np[index]),
            "log_return_5": float(log_return_5_np[index]),
            "momentum_10": momentum_10,
            "momentum_30": momentum_30,
            "rolling_return_max_20": float(rolling_return_max_20_np[index]),
            "rolling_return_min_20": float(rolling_return_min_20_np[index]),
            "close_sma_5_ratio": float(close_sma_5_ratio_np[index]),
            "close_sma_10_ratio": float(close_sma_10_ratio_np[index]),
            "close_sma_20_ratio": float(close_sma_20_ratio_np[index]),
            "close_sma_60_ratio": float(close_sma_60_ratio_np[index]),
            "close_ema_12_ratio": _ratio_to_value(candle.close, ema_12),
            "close_ema_26_ratio": _ratio_to_value(candle.close, ema_26),
            "ema_12_26_spread": ema_12_26_spread,
            "sma_5_20_spread": _spread_to_close(sma_5, sma_20, candle.close),
            "sma_20_60_spread": sma_20_60_spread,
            "trend_slope_10": float(trend_slope_10_np[index]),
            "trend_slope_30": float(trend_slope_30_np[index]),
            "prev_horizon_trend": _prev_horizon_trend(closes, index),
            "distance_to_high_20": _distance_to_extreme(candle.close, float(rolling_high_20_np[index])),
            "distance_to_low_20": _distance_to_extreme(candle.close, float(rolling_low_20_np[index])),
            "rv_5": rv_5,
            "rv_15": rv_15,
            "rv_30": rv_30,
            "rv_60": rv_60,
            "rv_120": rv_120,
            "atr_pct": atr_pct,
            "atr_pct_30": atr_pct_30,
            "parkinson_vol_20": float(parkinson_vol_20_np[index]),
            "garman_klass_vol_20": float(garman_klass_vol_20_np[index]),
            "range_vol_20": float(range_vol_20_np[index]),
            "har_rv_short": rv_5,
            "har_rv_medium": rv_30,
            "har_rv_long": rv_120,
            "volume_sma_5_ratio": float(volume_sma_5_ratio_np[index]),
            "volume_sma_20_ratio": float(volume_sma_20_ratio_np[index]),
            "volume_sma_60_ratio": float(volume_sma_60_ratio_np[index]),
            "quote_volume_sma_20_ratio": float(quote_vol_sma_20_ratio_np[index]),
            "taker_ratio": taker_ratio,
            "taker_imbalance": taker_imbalance,
            "taker_quote_ratio": taker_quote_ratio,
            "trade_count_ratio": float(trade_count_ratio_np[index]),
            "trade_count_zscore_20": trade_count_zscore_20,
            "volume_per_trade": _divide(candle.volume, float(candle.number_of_trades)),
            "quote_volume_per_trade": _divide(candle.quote_volume, float(candle.number_of_trades)),
            "volume_shock_20": volume_zscore_20,
            "high_low_range": high_low_range,
            "body_pct": body_pct,
            "upper_shadow": upper_shadow,
            "lower_shadow": lower_shadow,
            "close_location_value": _divide((candle.close - candle.low) - (candle.high - candle.close), range_value),
            "wick_imbalance": _divide(upper_shadow_raw - lower_shadow_raw, range_value),
            "body_to_range": _divide(abs(candle.close - candle.open), range_value),
            "range_sma_20_ratio": float(range_sma_20_ratio_np[index]),
            "inside_bar_flag": float(inside_bar_flag_np[index]),
            "outside_bar_flag": float(outside_bar_flag_np[index]),
            "gap_flag": float(candle.gap_flag),
            "gap_ratio_20": candle.gap_ratio_20,
            "gap_ratio_60": candle.gap_ratio_60,
            "gap_ratio_120": candle.gap_ratio_120,
            "max_gap_run_120": float(candle.max_gap_run_120),
            "repaired_flag": 1.0 if candle.repaired else 0.0,
            "gap_length": float(candle.gap_length),
            "canonical_gap_pressure": candle.gap_ratio_20 * (1.0 + float(candle.max_gap_run_120)),
            "close_zscore_20": close_zscore_20,
            "close_zscore_60": close_zscore_60,
            "volume_zscore_5": volume_zscore_5,
            "volume_zscore_20": volume_zscore_20,
            "rv_zscore_60": float(rv_zscore_60_np[index]),
            "range_zscore_20": float(range_zscore_20_np[index]),
            "volatility_regime_60": float(volatility_regime_60_np[index]),
            "volume_regime_60": float(volume_sma_60_ratio_np[index]),
            "return_1_vol_adj": return_1 / volatility_denominator,
            "return_5_vol_adj": return_5 / volatility_denominator,
            "return_10_vol_adj": return_10 / volatility_denominator,
            "return_30_vol_adj": return_30 / volatility_denominator,
            "momentum_10_vol_adj": momentum_10 / volatility_denominator,
            "momentum_30_vol_adj": momentum_30 / volatility_denominator,
            "close_zscore_20_vol_adj": close_zscore_20 / rv_60_denominator,
            "close_zscore_60_vol_adj": close_zscore_60 / rv_60_denominator,
            "ema_spread_vol_adj": ema_12_26_spread / rv_60_denominator,
            "sma_spread_vol_adj": sma_20_60_spread / rv_60_denominator,
            "candle_range_vol_adj": high_low_range / rv_60_denominator,
            "body_pct_vol_adj": body_pct / rv_60_denominator,
            "volume_zscore_20_vol_adj": volume_zscore_20 / rv_60_denominator,
            "trade_count_zscore_20_vol_adj": trade_count_zscore_20 / rv_60_denominator,
            "taker_imbalance_vol_adj": taker_imbalance / rv_60_denominator,
            # F11/F12 features — use per-candle external_sources if available, else single or mock defaults
            "spread": _spread_value(candle_external_sources, candle.close),
            "spread_bps": _spread_bps_value(candle_external_sources, candle.close),
            "bid_ask_imbalance": _bid_ask_imbalance_value(candle_external_sources),
            "best_bid_qty_ratio": _best_bid_qty_ratio_value(candle_external_sources),
            "best_ask_qty_ratio": _best_ask_qty_ratio_value(candle_external_sources),
            "microprice_deviation": _microprice_deviation_value(candle_external_sources, candle.close),
            "order_book_pressure": _order_book_pressure_value(candle_external_sources),
            "adl_indicator": _adl_indicator_value(candle_external_sources),
            "funding_rate": _funding_rate_value(candle_external_sources),
            "next_funding_rate": _next_funding_rate_value(candle_external_sources),
            "minutes_to_next_funding": _minutes_to_next_funding_value(candle_external_sources),
            "funding_blackout_active": _funding_blackout_active_value(candle_external_sources),
            "mark_price_basis": _mark_price_basis_value(candle_external_sources, candle.close),
            "premium_index": _premium_index_value(candle_external_sources),
            "leverage_bracket_utilization": _leverage_bracket_utilization_value(candle_external_sources),
            # F16: Derivatives metrics (values pre-computed and forward-filled
            # onto the 1m clock, delivered via external_sources["metrics"] as a
            # flat {feature_name: value} dict; 0.0 when unavailable so training
            # without --metrics-dir degrades to a constant, exactly like the
            # other external features).
            "oi_change_rate_5m": _metrics_feature_value(candle_external_sources, "oi_change_rate_5m"),
            "oi_change_rate_30m": _metrics_feature_value(candle_external_sources, "oi_change_rate_30m"),
            "oi_zscore_1d": _metrics_feature_value(candle_external_sources, "oi_zscore_1d"),
            "oi_value_zscore_1d": _metrics_feature_value(candle_external_sources, "oi_value_zscore_1d"),
            "toptrader_ls_account": _metrics_feature_value(candle_external_sources, "toptrader_ls_account"),
            "toptrader_ls_position": _metrics_feature_value(candle_external_sources, "toptrader_ls_position"),
            "global_ls_account": _metrics_feature_value(candle_external_sources, "global_ls_account"),
            "taker_ls_ratio": _metrics_feature_value(candle_external_sources, "taker_ls_ratio"),
            "toptrader_ls_account_change_5m": _metrics_feature_value(candle_external_sources, "toptrader_ls_account_change_5m"),
            "global_ls_account_change_5m": _metrics_feature_value(candle_external_sources, "global_ls_account_change_5m"),
            "taker_ls_ratio_change_5m": _metrics_feature_value(candle_external_sources, "taker_ls_ratio_change_5m"),
            # F17: Multi-timeframe (15m/1h/4h/24h-rolling) trend/vol/momentum
            # features, pre-computed once for the whole candle series above
            # (mtf_feature_values) and looked up per-candle here by open_time.
            **{name: mtf_row.get(name, 0.0) for name in mtf_features.MTF_FEATURE_NAMES},
            # F18: Regime probabilities (soft up/range/down), delivered via
            # external_sources["regime_classifier"] when the OOF pipeline has
            # been run; 0.0 degrade otherwise (same pattern as F16 metrics).
            "regime_prob_up": _regime_probability_feature_value(candle_external_sources, "regime_prob_up"),
            "regime_prob_range": _regime_probability_feature_value(candle_external_sources, "regime_prob_range"),
            "regime_prob_down": _regime_probability_feature_value(candle_external_sources, "regime_prob_down"),
            # F13: Weekly features
            "weekly_ma20_slope_closed": weekly_feature_values["weekly_ma20_slope_closed"][index],
            "weekly_ma50_slope_closed": weekly_feature_values["weekly_ma50_slope_closed"][index],
            "weekly_ma20_above_ma50": weekly_feature_values["weekly_ma20_above_ma50"][index],
            "weekly_drawdown": weekly_feature_values["weekly_drawdown"][index],
            "weekly_vol_contraction": weekly_feature_values["weekly_vol_contraction"][index],
            "close_vs_weekly_ma20": weekly_feature_values["close_vs_weekly_ma20"][index],
            "close_vs_weekly_ma50": weekly_feature_values["close_vs_weekly_ma50"][index],
            # F14: Time / Session features
            "hour": float(candle.open_time.hour),
            "minute": float(candle.open_time.minute),
            "day_of_week": float(candle.open_time.weekday()),
            "session_asia": 1.0 if 0 <= candle.open_time.hour < 8 else 0.0,
            "session_europe": 1.0 if 8 <= candle.open_time.hour < 16 else 0.0,
            "session_us": 1.0 if 16 <= candle.open_time.hour < 24 else 0.0,
            "session_overlap": 1.0 if 8 <= candle.open_time.hour < 16 else 0.0,
            "weekend_flag": 1.0 if candle.open_time.weekday() >= 5 else 0.0,
            # F15: Momentum indicators (pre-computed)
            "rsi_7": rsi_7_values[index],
            "rsi_14": rsi_14_values[index],
            "macd_line": macd_line_values[index],
            "macd_signal": macd_signal_values[index],
            "macd_hist": macd_line_values[index] - macd_signal_values[index],
            "bb_width_20": bb_width_20_values[index],
            "bb_percent_b": bb_percent_b_values[index],
            "ema_5_slope": ema_5_slope_values[index],
            "ema_20_slope": ema_20_slope_values[index],
            "ema_60_slope": ema_60_slope_values[index],
            "rolling_vwap_20": rolling_vwap_20_values[index],
            "rolling_vwap_60": rolling_vwap_60_values[index],
            "price_vs_rolling_vwap_20": _divide(candle.close, rolling_vwap_20_values[index]) - 1.0 if rolling_vwap_20_values[index] != 0.0 else 0.0,
            "price_vs_rolling_vwap_60": _divide(candle.close, rolling_vwap_60_values[index]) - 1.0 if rolling_vwap_60_values[index] != 0.0 else 0.0,
            "range_high_20": range_high_20_values[index],
            "range_low_20": range_low_20_values[index],
            "range_mid_20": range_mid_20_values[index],
            "range_position_20": range_position_20_values[index],
            "distance_to_range_high": _ratio_to_value(candle.close, range_high_20_values[index]),
            "distance_to_range_low": _ratio_to_value(candle.close, range_low_20_values[index]),
            "fake_break_low": fake_break_low_values[index],
            "fake_break_high": fake_break_high_values[index],
            "close_back_inside_range": close_back_inside_range_values[index],
            "vwap_deviation_zscore": vwap_deviation_zscore_values[index],
            "bb_zscore": close_zscore_20,
        }
        clipped_values = clipper.clip_values_only({name: values[name] for name in FEATURE_NAMES})
        row_context = {
            "gap_flag": candle.gap_flag,
            "canonical_candle_repaired": candle.repaired,
            "warmup_invalid": warmup_invalid,
        }
        nan_status: dict[str, str] = {}
        for name, value in clipped_values.items():
            if value is None:
                nan_status[name] = nan_classifier.classify(row_context, name)
        merged_feature_status = dict(feature_availability_status)
        merged_feature_status.update(nan_status)
        rows.append(
            FeatureRow(
                index,
                candle.open_time,
                FeatureVector.from_mapping(clipped_values),
                candle.gap_flag,
                candle.repaired,
                warmup_invalid,
                dict(source_availability_status),
                merged_feature_status,
                unavailable_sources,
                fallback_features,
                resolve_user_regime(candle.open_time, user_regime_periods) if user_regime_periods else None,
            )
        )
    return rows


def _build_feature_rows_chunk(
    chunk_candles: Sequence[data.Candle],
    source_bundle: sources.MarketSourceBundle | None,
    external_sources: Mapping[str, object] | None,
    user_regime_periods: Sequence[UserRegimePeriod] | None,
    index_offset: int,
    overlap: int,
    is_first_chunk: bool,
    precomputed_weekly: Mapping[str, Sequence[float]] | None = None,
) -> list[FeatureRow]:
    """Process a chunk of candles and return feature rows with corrected indices."""
    chunk_rows = build_feature_rows(
        chunk_candles,
        source_bundle=source_bundle,
        external_sources=external_sources,
        user_regime_periods=user_regime_periods,
        _parallel=False,
        _precomputed_weekly=precomputed_weekly,
    )
    result: list[FeatureRow] = []
    for row in chunk_rows:
        new_index = row.index + index_offset
        # Skip overlap rows (except for first chunk which keeps warmup rows)
        if not is_first_chunk and row.index < overlap:
            continue
        result.append(
            FeatureRow(
                index=new_index,
                open_time=row.open_time,
                features=row.features,
                gap_flag=row.gap_flag,
                repaired=row.repaired,
                warmup_invalid=row.warmup_invalid,
                source_availability_status=row.source_availability_status,
                feature_availability_status=row.feature_availability_status,
                unavailable_sources=row.unavailable_sources,
                fallback_features=row.fallback_features,
                user_regime=row.user_regime,
            )
        )
    return result


def _process_feature_chunk(
    args: tuple[int, int, bool, Sequence[data.Candle], sources.MarketSourceBundle | None, Mapping[str, object] | None, Sequence[UserRegimePeriod] | None, int, Mapping[str, Sequence[float]] | None],
) -> list[FeatureRow]:
    """Top-level worker for parallel feature computation.

    NOTE: ``chunk_candles`` here is ALREADY the sliced sub-range for this
    worker (sliced in the parent before dispatch). Previously each worker
    received the ENTIRE candle list and sliced it locally, which pickled the
    full multi-million-candle list once per worker (N-fold blow-up) and
    caused BrokenProcessPool on large multi-year runs.

    ``weekly_slice`` is the [start:end) slice of the GLOBALLY-computed weekly
    features (see _build_feature_rows_parallel): weekly MA20/MA50 need ~50
    weeks (~504k bars) of history, far more than any chunk contains, so they
    must never be recomputed per-chunk.
    """
    start, end, is_first, chunk_candles, source_bundle, external_sources, user_regime_periods, overlap, weekly_slice = args
    return _build_feature_rows_chunk(
        chunk_candles,
        source_bundle=source_bundle,
        external_sources=external_sources,
        user_regime_periods=user_regime_periods,
        index_offset=start,
        overlap=overlap,
        is_first_chunk=is_first,
        precomputed_weekly=weekly_slice,
    )


def _build_feature_rows_parallel(
    candles: Sequence[data.Candle],
    source_bundle: sources.MarketSourceBundle | None,
    external_sources: Mapping[str, object] | None,
    user_regime_periods: Sequence[UserRegimePeriod] | None,
) -> list[FeatureRow]:
    """Parallel feature computation using chunked ProcessPoolExecutor."""
    n = len(candles)
    num_workers = min(os.cpu_count() or 4, 8)
    # Cap chunk size independently of worker count. build_feature_rows_chunk
    # materializes ~50 full-length float64 NumPy arrays per chunk; with a very
    # large chunk (e.g. a single worker handling 500k+ candles) the peak
    # memory of those arrays plus overlap can exceed the process limit and
    # kill the worker (BrokenProcessPool). Splitting into bounded chunks keeps
    # each task's peak memory low and lets executor.map stream them, even when
    # os.cpu_count() reports 1.
    # Bounded chunk size: caps the peak memory of the ~50 full-length NumPy
    # arrays each chunk materializes, and caps per-task pickle size. 250k is a
    # balance between overhead (too many tiny chunks) and peak memory (one huge
    # chunk). Lower this if workers are memory-constrained.
    MAX_CHUNK = 250_000
    chunk_size = max(min(n // num_workers if num_workers > 0 else n, MAX_CHUNK), 10000)
    # Overlap must cover the largest lookback any per-chunk feature needs,
    # since a chunk boundary's first KEPT row has only seen `overlap` minutes
    # of history within its own chunk. Weekly features (needing up to 504,000
    # minutes -- 50 completed weeks -- vastly more than any chunk) are NOT
    # computed per-chunk at all: they are computed ONCE below over the FULL
    # series and injected into each worker as an aligned slice, so they are
    # exact everywhere regardless of chunk size. F17 multi-timeframe
    # features need up to 4800 minutes (20 closed 4h bars for bb_width_4h/
    # volume_z_4h), so overlap is sized to 6000 (safe margin) to guarantee
    # those are exact at every chunk boundary, not just the series start.
    overlap = 6000
    # Number of chunks now derives from data size, not worker count.
    num_chunks = max(1, (n + chunk_size - 1) // chunk_size)
    print(f"[FEATURE] Parallel feature computation: {n:,} candles, {num_workers} workers, {num_chunks} chunks, chunk_size={chunk_size:,}, overlap={overlap}")

    # Build chunk ranges
    chunks: list[tuple[int, int, bool]] = []
    for i in range(num_chunks):
        start = i * chunk_size
        if start >= n:
            break
        end = min(start + chunk_size + overlap, n)
        if i == num_chunks - 1:
            end = n
        is_first = i == 0
        chunks.append((start, end, is_first))
        if end >= n:
            break

    # Weekly MA20/MA50 features require ~50 completed weeks (~504,000 1m
    # bars) of history. Every chunk (<=256k bars, ~25 weeks) fails the
    # `len(weekly) >= 50` guard inside compute_weekly_features, so per-chunk
    # computation would silently zero ALL weekly_* / close_vs_weekly_*
    # features on parallel runs. Compute them ONCE over the full series here
    # (cheap: one weekly resample of the whole span) and hand each worker
    # its [start:end) slice, aligned 1:1 with its candle slice. float32
    # ndarrays keep the per-task pickle small (~7 MB per 256k-bar chunk).
    weekly_full = weekly_features.compute_weekly_features(candles)
    weekly_full_np = {
        name: np.asarray(values, dtype=np.float32)
        for name, values in weekly_full.items()
    }
    del weekly_full

    # Per-candle external_sources (datetime-keyed, e.g. --metrics-dir merges
    # external_sources[minute]["metrics"] for EVERY minute -- ~3.15M keys on
    # a 2020-2025 run) must NOT be pickled whole into every work item: each
    # of the ~13 chunk tasks would serialize the entire multi-million-entry
    # nested dict (hundreds of MB per task, duplicated in every worker).
    # Workers only ever look up their own candles' open_times
    # (per_candle_external_sources.get(candle.open_time)), so slice by the
    # chunk's [first, last] candle-time range in the parent. A single small
    # non-datetime-keyed mapping (the "same sources for all candles" form)
    # is passed through unchanged.
    external_is_per_candle = external_sources is not None and any(
        isinstance(key, datetime) for key in external_sources.keys()
    )
    # Defensive: a mapping detected as per-candle could in principle carry
    # stray non-datetime keys (e.g. a str key merged in by a future caller);
    # sorting a mixed list raises TypeError, and workers only ever look up
    # candle open_times anyway, so slice over the datetime keys ONLY.
    sorted_external_keys: list[datetime] = (
        sorted(key for key in external_sources.keys() if isinstance(key, datetime))  # type: ignore[union-attr]
        if external_is_per_candle
        else []
    )

    def _external_slice(start: int, end: int) -> Mapping[str, object] | None:
        if external_sources is None:
            return None
        if not external_is_per_candle:
            return external_sources
        lo = bisect_left(sorted_external_keys, candles[start].open_time)
        hi = bisect_right(sorted_external_keys, candles[end - 1].open_time)
        return {key: external_sources[key] for key in sorted_external_keys[lo:hi]}  # type: ignore[index]

    all_rows: list[FeatureRow] = []
    # Slice each chunk's candles HERE (in the parent) so each worker only
    # receives its own sub-range, not the entire candle list. This avoids
    # pickling the full multi-million-candle list once per worker.
    work_items = [
        (
            start,
            end,
            is_first,
            candles[start:end],
            source_bundle,
            _external_slice(start, end),
            user_regime_periods,
            overlap,
            {name: values[start:end] for name, values in weekly_full_np.items()},
        )
        for start, end, is_first in chunks
    ]
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for result in executor.map(_process_feature_chunk, work_items):
            all_rows.extend(result)
    print(f"[FEATURE] Parallel computation complete: {len(all_rows):,} rows")
    return all_rows


def attach_labels(
    feature_rows: Sequence[FeatureRow],
    candles: Sequence[data.Candle],
    horizon: int,
    label_threshold: float,
    tp_pct: float = 0.001,
    sl_pct: float = 0.0005,
    external_events: Mapping[object, object] | None = None,
    include_warmup: bool = False,
) -> list[LabeledRow]:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if tp_pct <= 0.0:
        raise ValueError("tp_pct must be positive")
    if sl_pct <= 0.0:
        raise ValueError("sl_pct must be positive")
    labeled: list[LabeledRow] = []
    for row in feature_rows:
        future_index = row.index + horizon
        if (row.warmup_invalid and not include_warmup) or future_index >= len(candles):
            continue
        close = candles[row.index].close
        if close == 0.0:
            continue
        target_return = (candles[future_index].close - close) / close
        label, label_reason = triple_barrier_label(row.index, candles, horizon, label_threshold, tp_pct, sl_pct, target_return)
        # LONG/SHORT success labels
        long_success, long_reason = triple_barrier_label_long(row.index, candles, horizon, tp_pct, sl_pct)
        short_success, short_reason = triple_barrier_label_short(row.index, candles, horizon, tp_pct, sl_pct)
        short_profit, short_profit_reason = triple_barrier_label_short_profitability(
            row.index, candles, horizon, label_threshold, tp_pct, sl_pct, target_return
        )
        # Direction target: simple future return sign
        direction_label = 1 if target_return > 0.0 else 0
        direction_reason = "future_positive" if target_return > 0.0 else "future_negative"
        external_label, external_reason = _external_label(row, target_return, label_threshold, external_events)
        if external_label is not None and external_reason is not None:
            label = external_label
            label_reason = external_reason
        labeled.append(
            LabeledRow(
                index=row.index,
                open_time=row.open_time,
                features=row.features,
                label=label,
                label_reason=label_reason,
                target_return=target_return,
                gap_flag=row.gap_flag,
                repaired=row.repaired,
                warmup_invalid=row.warmup_invalid,
                source_availability_status=dict(row.source_availability_status),
                feature_availability_status=dict(row.feature_availability_status),
                unavailable_sources=row.unavailable_sources,
                fallback_features=row.fallback_features,
                targets={
                    "direction": direction_label,
                    "profitability": label,
                    "long_success": long_success,
                    "short_success": short_success,
                    "short_profitability": short_profit,
                },
                target_reasons={
                    "direction": direction_reason,
                    "profitability": label_reason,
                    "long_success": long_reason,
                    "short_success": short_reason,
                    "short_profitability": short_profit_reason,
                },
                user_regime=row.user_regime,
            )
        )
    return labeled


def triple_barrier_label(
    entry_index: int,
    candles: Sequence[data.Candle],
    horizon: int,
    label_threshold: float,
    tp_pct: float,
    sl_pct: float,
    target_return: float,
) -> tuple[int, str]:
    entry_price = candles[entry_index].close
    tp_level = entry_price * (1.0 + tp_pct)
    sl_level = entry_price * (1.0 - sl_pct)
    gap_seen = False
    for future_index in range(entry_index + 1, entry_index + horizon + 1):
        candle = candles[future_index]
        if candle.gap_flag == 1:
            gap_seen = True
        tp_touched = candle.high >= tp_level
        sl_touched = candle.low <= sl_level
        if tp_touched and sl_touched:
            if candle.close > candle.open:
                return 1, "tp_first"
            if candle.close < candle.open:
                return 0, "sl_first"
            return 0, "ambiguous_path"
        if tp_touched:
            return 1, "tp_first"
        if sl_touched:
            return 0, "gap_cross_sl" if candle.gap_flag == 1 else "sl_first"
    timeout_reason = "gap_cross_timeout" if gap_seen else "timeout_no_tp"
    return (1 if target_return > label_threshold else 0), timeout_reason


def triple_barrier_label_long(
    entry_index: int,
    candles: Sequence[data.Candle],
    horizon: int,
    tp_pct: float,
    sl_pct: float,
) -> tuple[int, str]:
    """LONG 진입 시 TP가 SL보다 먼저 도달하면 1, 아니면 0."""
    entry_price = candles[entry_index].close
    tp_level = entry_price * (1.0 + tp_pct)
    sl_level = entry_price * (1.0 - sl_pct)
    for future_index in range(entry_index + 1, entry_index + horizon + 1):
        candle = candles[future_index]
        tp_touched = candle.high >= tp_level
        sl_touched = candle.low <= sl_level
        if tp_touched and sl_touched:
            if candle.close > candle.open:
                return 1, "long_tp_first"
            return 0, "long_sl_first"
        if tp_touched:
            return 1, "long_tp_first"
        if sl_touched:
            return 0, "long_sl_first"
    return 0, "long_timeout"


def triple_barrier_label_short(
    entry_index: int,
    candles: Sequence[data.Candle],
    horizon: int,
    tp_pct: float,
    sl_pct: float,
) -> tuple[int, str]:
    """SHORT 진입 시 TP(가격 하락)가 SL(가격 상승)보다 먼저 도달하면 1, 아니면 0."""
    entry_price = candles[entry_index].close
    tp_level = entry_price * (1.0 - tp_pct)  # TP: 가격 하락
    sl_level = entry_price * (1.0 + sl_pct)  # SL: 가격 상승
    for future_index in range(entry_index + 1, entry_index + horizon + 1):
        candle = candles[future_index]
        tp_touched = candle.low <= tp_level  # 하락 TP 체크
        sl_touched = candle.high >= sl_level  # 상승 SL 체크
        if tp_touched and sl_touched:
            if candle.close < candle.open:
                return 1, "short_tp_first"
            return 0, "short_sl_first"
        if tp_touched:
            return 1, "short_tp_first"
        if sl_touched:
            return 0, "short_sl_first"
    return 0, "short_timeout"


def triple_barrier_label_short_profitability(
    entry_index: int,
    candles: Sequence[data.Candle],
    horizon: int,
    label_threshold: float,
    tp_pct: float,
    sl_pct: float,
    target_return: float,
) -> tuple[int, str]:
    """The mirror of ``triple_barrier_label``: is a SHORT worth taking here?

    ``short_success`` alone is unusable once the barriers are set beyond reach
    (the barrier-free horizon-exit design), because it returns 0 on every
    timeout and the label collapses to a constant. ``profitability`` does not
    have that problem on the long side -- it counts a timeout as a win when the
    horizon return clears ``label_threshold`` -- so the short side needs the
    same branch with the sign flipped: a SHORT wins on timeout when price FELL
    by more than the threshold.

    Without it the project can only infer shorts from the bottom of a
    long-trained model's probability, which answers a different question: a low
    P(return > +threshold) covers small POSITIVE returns too, not just falls.
    """
    label, reason = triple_barrier_label_short(entry_index, candles, horizon, tp_pct, sl_pct)
    if reason != "short_timeout":
        return label, reason
    return (1 if -target_return > label_threshold else 0), "short_timeout_return"


def _external_label(row: FeatureRow, target_return: float, label_threshold: float, external_events: Mapping[object, object] | None) -> tuple[int | None, str | None]:
    if not external_events:
        return None, None
    event = _event_for_row(row, external_events)
    if event is None:
        return None, None
    if isinstance(event, str):
        reason = event
        explicit_label: object | None = None
    elif isinstance(event, Mapping):
        reason = event.get("label_reason") or event.get("reason")
        explicit_label = event.get("label")
    else:
        return None, None
    if not isinstance(reason, str) or reason not in LABEL_REASON_BUCKETS:
        raise ValueError(f"unknown label_reason: {reason}")
    if explicit_label is not None:
        label = int(explicit_label)
        if label not in (0, 1):
            raise ValueError("external event label must be 0 or 1")
        return label, reason
    if reason == "tp_first":
        return 1, reason
    if reason in EVENT_NEGATIVE_REASONS or reason in {"sl_first", "ambiguous_path"}:
        return 0, reason
    return (1 if target_return > label_threshold else 0), reason


def _event_for_row(row: FeatureRow, external_events: Mapping[object, object]) -> object | None:
    for key in (row.index, row.open_time, row.open_time.isoformat()):
        if key in external_events:
            return external_events[key]
    return None


def dataset_card(build: DatasetBuild) -> dict[str, object]:
    registry = feature_formula_registry()
    source_report = build.source_availability_report or sources.train_live_feature_parity_report(
        build.feature_names,
        source_bundle=build.source_bundle,
        feature_registry=registry["features"],
    )
    parity_result = parity.compare_training_live_features(
        registry,
        registry,
        source_report=source_report,
        training_feature_names=build.feature_names,
        live_feature_names=build.feature_names,
    )
    parity_metadata = parity_result.as_metadata()
    train_live_feature_parity_passed = bool(source_report.get("train_live_feature_parity_passed", False)) and parity_result.passed
    return {
        "dataset_id": "btcusdt_offline_research_v1",
        "symbol": build.symbol,
        "bar_interval": build.interval,
        "source": build.source,
        "timezone": "UTC",
        "raw_rows": build.raw_rows,
        "canonical_rows": build.gap_report.canonical_rows,
        "labeled_rows": len(build.labeled_rows),
        "label_horizon_minutes": build.label_horizon,
        "label_threshold_return": build.label_threshold,
        "label_reason_buckets": list(LABEL_REASON_BUCKETS),
        "label_reason_counts": label_reason_counts(build.labeled_rows),
        "gap_report": gap_report_dict(build.gap_report),
        "source_hashes": dict(source_report.get("source_hashes", {})),
        "feature_space_parity_passed": bool(source_report.get("feature_space_parity_passed", False)),
        "train_live_feature_parity_passed": train_live_feature_parity_passed,
        "feature_parity_passed": bool(parity_metadata["feature_parity_passed"]),
        "feature_schema_hash": parity_metadata["feature_schema_hash"],
        "training_feature_schema_hash": parity_metadata["training_feature_schema_hash"],
        "live_feature_schema_hash": parity_metadata["live_feature_schema_hash"],
        "source_schema_hash": parity_metadata["source_schema_hash"],
        "training_source_schema_hash": parity_metadata["training_source_schema_hash"],
        "live_source_schema_hash": parity_metadata["live_source_schema_hash"],
        "dependency_graph_hash": parity_metadata["dependency_graph_hash"],
        "training_dependency_graph_hash": parity_metadata["training_dependency_graph_hash"],
        "live_dependency_graph_hash": parity_metadata["live_dependency_graph_hash"],
        "feature_parity_checks": parity_metadata["parity_checks"],
        "feature_parity_reasons": parity_metadata["parity_reasons"],
        "documented_grade_c_fallback": parity_metadata["documented_grade_c_fallback"],
        "unavailable_sources": list(source_report.get("unavailable_sources", ())),
        "grade_c_sources": list(source_report.get("grade_c_sources", ())),
        "fallback_features": list(source_report.get("fallback_features", ())),
        "approval_block_reasons": list(source_report.get("approval_block_reasons", ())),
        "offline_only": True,
        "network_required": False,
    }


def feature_matrix(build: DatasetBuild) -> tuple[list[list[float]], list[int]]:
    matrix = [[row.features[name] for name in build.feature_names] for row in build.labeled_rows]
    labels = [row.label for row in build.labeled_rows]
    return matrix, labels


def feature_formula_registry() -> dict[str, object]:
    return feature_registry.registry_from_feature_rows(FEATURE_FORMULAS)


def _source_availability_status(source_report: Mapping[str, object]) -> dict[str, str]:
    rows = source_report.get("source_rows", ())
    status: dict[str, str] = {}
    if not isinstance(rows, Sequence):
        return status
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source_name = row.get("source_name")
        availability_grade = row.get("availability_grade")
        if isinstance(source_name, str):
            status[source_name] = str(availability_grade)
    return status


def max_feature_min_samples(n_candles: int | None = None) -> int:
    """Largest feature warmup requirement.

    When ``n_candles`` is given, features whose ``min_samples`` exceeds the
    available candle count are excluded from the maximum: such features can
    never be computed on this dataset (e.g. weekly MA50 needs 504,000 1m bars
    = 50 weeks), so gating the whole warmup on them would invalidate every row
    on a short dataset. On a full multi-year dataset all features qualify and
    the result is unchanged (504,000). This keeps real-world behavior intact
    while letting short fixtures/tests produce labeled rows.
    """
    values: list[int] = []
    for row in FEATURE_FORMULAS:
        value = row.get("min_samples", 1)
        if not isinstance(value, int):
            raise ValueError("feature min_samples must be an integer")
        if value <= 0:
            raise ValueError("feature min_samples must be positive")
        if n_candles is not None and value > n_candles:
            # This feature cannot be computed on a dataset this short; do not
            # let its warmup requirement invalidate the entire dataset.
            continue
        values.append(value)
    return max(values, default=1)


def gap_report_dict(report: GapReport) -> dict[str, object]:
    return {
        "raw_rows": report.raw_rows,
        "canonical_rows": report.canonical_rows,
        "repaired_rows": report.repaired_rows,
        "gap_ratio_total": report.gap_ratio_total,
        "max_gap_run": report.max_gap_run,
        "first_open_time": report.first_open_time,
        "last_open_time": report.last_open_time,
    }


def _return(values: Sequence[float], index: int, lookback: int) -> float:
    if index < lookback or values[index - lookback] == 0.0:
        return 0.0
    return values[index] / values[index - lookback] - 1.0


def _log_return(values: Sequence[float], index: int, lookback: int) -> float:
    if index < lookback:
        return 0.0
    current = values[index]
    previous = values[index - lookback]
    if current <= 0.0 or previous <= 0.0:
        return 0.0
    return log(current / previous)


def _divide(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _ratio_to_value(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator - 1.0


def _ratio_to_mean(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    average = mean(values[index + 1 - window:index + 1])
    if average == 0.0:
        return 0.0
    return values[index] / average - 1.0


def _rolling_mean_value(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    return mean(values[index + 1 - window:index + 1])


def _ema(values: Sequence[float], index: int, span: int) -> float:
    if index + 1 < span or not values:
        return 0.0
    alpha = 2.0 / (span + 1.0)
    value = values[0]
    for position in range(1, index + 1):
        value = alpha * values[position] + (1.0 - alpha) * value
    return value


def _ema_series(values: Sequence[float], span: int) -> list[float]:
    """Compute EMA for all indices in O(n) time."""
    if not values or span <= 0:
        return [0.0] * len(values)
    alpha = 2.0 / (span + 1.0)
    result: list[float] = []
    ema = values[0]
    for index, value in enumerate(values):
        if index == 0:
            ema = value
        else:
            ema = alpha * value + (1.0 - alpha) * ema
        if index + 1 >= span:
            result.append(ema)
        else:
            result.append(0.0)
    return result


def _rsi_series(values: Sequence[float], period: int) -> list[float]:
    """Compute RSI for all indices in O(n) time."""
    if len(values) < period + 1 or period <= 0:
        return [50.0] * len(values)
    result: list[float] = []
    # Calculate initial average gain/loss
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    # RSI for index=period
    if avg_loss == 0.0:
        result.extend([50.0] * period)
        result.append(100.0 if avg_gain > 0 else 50.0)
    else:
        rs = avg_gain / avg_loss
        result.extend([50.0] * period)
        result.append(100.0 - (100.0 / (1.0 + rs)))
    # Wilder's smoothing for remaining indices
    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0.0:
            result.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))
    return result


def _bb_series(values: Sequence[float], window: int) -> tuple[list[float], list[float]]:
    """Compute Bollinger Band width and %B for all indices."""
    width_values = []
    percent_b_values = []
    for index in range(len(values)):
        if index + 1 < window:
            width_values.append(0.0)
            percent_b_values.append(0.0)
            continue
        sample = values[index + 1 - window:index + 1]
        mean_value = mean(sample)
        std_value = _stddev(sample)
        if mean_value == 0.0:
            width_values.append(0.0)
        else:
            width_values.append((2.0 * std_value) / mean_value)
        upper = mean_value + 2.0 * std_value
        lower = mean_value - 2.0 * std_value
        if upper == lower:
            percent_b_values.append(0.5)
        else:
            percent_b_values.append((values[index] - lower) / (upper - lower))
    return width_values, percent_b_values


def _ema_slope_series(values: Sequence[float], ema_period: int, slope_window: int) -> list[float]:
    """Compute EMA slope for all indices."""
    ema_values = _ema_series(values, ema_period)
    result = []
    for index in range(len(values)):
        if index + 1 < ema_period + slope_window:
            result.append(0.0)
            continue
        slope_ema_values = ema_values[index + 1 - slope_window:index + 1]
        result.append(_trend_slope(slope_ema_values, slope_window - 1, slope_window))
    return result


def _rolling_vwap_series(closes: Sequence[float], volumes: Sequence[float], window: int) -> list[float]:
    """Compute rolling VWAP for all indices."""
    result = []
    for index in range(len(closes)):
        if index + 1 < window:
            result.append(0.0)
            continue
        total_value = 0.0
        total_volume = 0.0
        for position in range(index + 1 - window, index + 1):
            total_value += closes[position] * volumes[position]
            total_volume += volumes[position]
        result.append(total_value / total_volume if total_volume > 0 else 0.0)
    return result


def _rolling_extreme_series(values: Sequence[float], window: int, use_max: bool) -> list[float]:
    if window <= 0:
        return [0.0] * len(values)
    result = [0.0] * len(values)
    candidates: deque[int] = deque()
    for index, value in enumerate(values):
        while candidates and candidates[0] <= index - window:
            candidates.popleft()
        while candidates and ((values[candidates[-1]] <= value) if use_max else (values[candidates[-1]] >= value)):
            candidates.pop()
        candidates.append(index)
        if index + 1 >= window:
            result[index] = values[candidates[0]]
    return result


def _range_high_series(highs: Sequence[float], window: int) -> list[float]:
    return _rolling_extreme_series(highs, window, use_max=True)


def _range_low_series(lows: Sequence[float], window: int) -> list[float]:
    return _rolling_extreme_series(lows, window, use_max=False)


def _range_mid_series(range_highs: Sequence[float], range_lows: Sequence[float]) -> list[float]:
    return [(high + low) / 2.0 if high != 0.0 or low != 0.0 else 0.0 for high, low in zip(range_highs, range_lows)]


def _range_position_series(closes: Sequence[float], range_lows: Sequence[float], range_highs: Sequence[float]) -> list[float]:
    result: list[float] = []
    for close, range_low, range_high in zip(closes, range_lows, range_highs):
        width = range_high - range_low
        if width <= 0.0:
            result.append(0.0)
            continue
        position = (close - range_low) / width
        result.append(max(0.0, min(1.0, position)))
    return result


def _fake_break_low_series(opens: Sequence[float], closes: Sequence[float], range_lows: Sequence[float]) -> list[float]:
    result = [0.0] * len(closes)
    for index in range(1, len(closes)):
        previous_range_low = range_lows[index - 1]
        if previous_range_low == 0.0 or range_lows[index] == 0.0:
            continue
        if closes[index - 1] >= previous_range_low and closes[index] < previous_range_low and closes[index] > opens[index]:
            result[index] = 1.0
    return result


def _fake_break_high_series(opens: Sequence[float], closes: Sequence[float], range_highs: Sequence[float]) -> list[float]:
    result = [0.0] * len(closes)
    for index in range(1, len(closes)):
        previous_range_high = range_highs[index - 1]
        if previous_range_high == 0.0 or range_highs[index] == 0.0:
            continue
        if closes[index - 1] <= previous_range_high and closes[index] > previous_range_high and closes[index] < opens[index]:
            result[index] = 1.0
    return result


def _close_back_inside_range_series(closes: Sequence[float], range_lows: Sequence[float], range_highs: Sequence[float]) -> list[float]:
    result = [0.0] * len(closes)
    for index in range(1, len(closes)):
        previous_low = range_lows[index - 1]
        previous_high = range_highs[index - 1]
        current_low = range_lows[index]
        current_high = range_highs[index]
        if previous_low == 0.0 or previous_high == 0.0 or current_low == 0.0 or current_high == 0.0:
            continue
        previous_outside = closes[index - 1] < previous_low or closes[index - 1] > previous_high
        current_inside = current_low <= closes[index] <= current_high
        if previous_outside and current_inside:
            result[index] = 1.0
    return result


def _vwap_deviation_zscore_series(closes: Sequence[float], vwaps: Sequence[float], window: int) -> list[float]:
    deviations = [close - vwap if vwap != 0.0 else 0.0 for close, vwap in zip(closes, vwaps)]
    result = [0.0] * len(closes)
    first_valid_index = (window - 1) * 2
    for index in range(first_valid_index, len(closes)):
        sample = deviations[index + 1 - window:index + 1]
        scale = _stddev(sample)
        if scale != 0.0:
            result[index] = deviations[index] / scale
    return result


def _spread_to_close(left: float, right: float, close: float) -> float:
    if close == 0.0:
        return 0.0
    return (left - right) / close


def _rolling_max(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    return max(values[index + 1 - window:index + 1])


def _rolling_min(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    return min(values[index + 1 - window:index + 1])


def _distance_to_extreme(close: float, extreme: float) -> float:
    if extreme == 0.0:
        return 0.0
    return close / extreme - 1.0


def _trend_slope(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    sample = values[index + 1 - window:index + 1]
    x_mean = (window - 1) / 2.0
    y_mean = mean(sample)
    denominator = sum((position - x_mean) ** 2 for position in range(window))
    if denominator == 0.0 or values[index] == 0.0:
        return 0.0
    numerator = sum((position - x_mean) * (value - y_mean) for position, value in enumerate(sample))
    return (numerator / denominator) / values[index]


def _rolling_return_extreme(values: Sequence[float], index: int, window: int, use_max: bool) -> float:
    if index < window:
        return 0.0
    returns = [_return(values, position, 1) for position in range(index + 1 - window, index + 1)]
    return max(returns) if use_max else min(returns)


def _rolling_return_std(values: Sequence[float], index: int, window: int) -> float:
    if index < window:
        return 0.0
    returns = [_return(values, position, 1) for position in range(index + 1 - window, index + 1)]
    return _stddev(returns)


def _rolling_return_std_series(values: Sequence[float], window: int) -> list[float]:
    """Rolling stddev of 1-bar returns for every index. Matches _rolling_return_std.

    Uses prefix sums of returns and squared returns so each index is O(1) amortized.
    Returns 0.0 for index < window (matches the strict warmup of the original).
    """
    n = len(values)
    if n == 0 or window <= 0:
        return [0.0] * n
    # Build the return series first (same semantics as _return(values, i, 1))
    returns = [0.0] * n
    for i in range(1, n):
        prev = values[i - 1]
        if prev != 0.0:
            returns[i] = values[i] / prev - 1.0
    # Prefix sums over the return series; prefix_sum[k] = sum(returns[:k])
    prefix_sum = [0.0] * (n + 1)
    prefix_sum_sq = [0.0] * (n + 1)
    for i in range(n):
        prefix_sum[i + 1] = prefix_sum[i] + returns[i]
        prefix_sum_sq[i + 1] = prefix_sum_sq[i] + returns[i] * returns[i]
    result = [0.0] * n
    for index in range(window, n):
        # _rolling_return_std uses returns at positions [index+1-window .. index]
        # which corresponds to slice indices [index+1-window, index+1)
        lo = index + 1 - window
        hi = index + 1
        window_sum = prefix_sum[hi] - prefix_sum[lo]
        window_sum_sq = prefix_sum_sq[hi] - prefix_sum_sq[lo]
        window_mean = window_sum / window
        # population variance (matches _stddev which uses ddof=0)
        variance = window_sum_sq / window - window_mean * window_mean
        # Clamp tiny negative values from float cancellation before sqrt
        if variance > 0.0:
            result[index] = sqrt(variance)
        else:
            result[index] = 0.0
    return result


def _rolling_std(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    return _stddev(values[index + 1 - window:index + 1])


def _atr_pct(candles: Sequence[data.Candle], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    true_ranges: list[float] = []
    for position in range(index + 1 - window, index + 1):
        candle = candles[position]
        previous_close = candles[position - 1].close if position > 0 else candle.close
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
    close = candles[index].close
    return mean(true_ranges) / close if close else 0.0


def _atr_pct_series(candles: Sequence[data.Candle], window: int) -> list[float]:
    """ATR percentage for every index. Matches _atr_pct.

    Builds the true-range series once and uses a prefix sum to compute the
    rolling mean in O(1) per index.
    """
    n = len(candles)
    if n == 0 or window <= 0:
        return [0.0] * n
    true_ranges = [0.0] * n
    for position in range(n):
        candle = candles[position]
        prev_close = candles[position - 1].close if position > 0 else candle.close
        diff_high_low = candle.high - candle.low
        diff_high_pc = candle.high - prev_close
        if diff_high_pc < 0.0:
            diff_high_pc = -diff_high_pc
        diff_low_pc = candle.low - prev_close
        if diff_low_pc < 0.0:
            diff_low_pc = -diff_low_pc
        tr = diff_high_low
        if diff_high_pc > tr:
            tr = diff_high_pc
        if diff_low_pc > tr:
            tr = diff_low_pc
        true_ranges[position] = tr
    prefix = [0.0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] + true_ranges[i]
    result = [0.0] * n
    for index in range(window - 1, n):
        lo = index + 1 - window
        hi = index + 1
        window_mean = (prefix[hi] - prefix[lo]) / window
        close = candles[index].close
        result[index] = window_mean / close if close else 0.0
    return result


def _parkinson_vol(candles: Sequence[data.Candle], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    terms: list[float] = []
    for candle in candles[index + 1 - window:index + 1]:
        if candle.high <= 0.0 or candle.low <= 0.0:
            terms.append(0.0)
        else:
            high_low_log = log(candle.high / candle.low)
            terms.append(high_low_log * high_low_log)
    variance = mean(terms) / (4.0 * log(2.0))
    return sqrt(variance) if variance > 0.0 else 0.0


def _garman_klass_vol(candles: Sequence[data.Candle], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    terms: list[float] = []
    for candle in candles[index + 1 - window:index + 1]:
        if candle.high <= 0.0 or candle.low <= 0.0 or candle.open <= 0.0 or candle.close <= 0.0:
            terms.append(0.0)
        else:
            high_low_log = log(candle.high / candle.low)
            close_open_log = log(candle.close / candle.open)
            terms.append(0.5 * high_low_log * high_low_log - (2.0 * log(2.0) - 1.0) * close_open_log * close_open_log)
    variance = mean(terms)
    return sqrt(variance) if variance > 0.0 else 0.0


def _range_value(candle: data.Candle) -> float:
    return candle.high - candle.low


def _range_pct(candle: data.Candle) -> float:
    return _divide(candle.high - candle.low, candle.close)


def _body_pct(candle: data.Candle) -> float:
    return _divide(abs(candle.close - candle.open), candle.close)


def _inside_bar_flag(candles: Sequence[data.Candle], index: int) -> float:
    if index == 0:
        return 0.0
    current = candles[index]
    previous = candles[index - 1]
    return 1.0 if current.high <= previous.high and current.low >= previous.low else 0.0


def _outside_bar_flag(candles: Sequence[data.Candle], index: int) -> float:
    if index == 0:
        return 0.0
    current = candles[index]
    previous = candles[index - 1]
    return 1.0 if current.high >= previous.high and current.low <= previous.low else 0.0


PREV_HORIZON_TREND_HORIZON = 15
PREV_HORIZON_TREND_THRESHOLD = 0.001


def _prev_horizon_trend(closes: list[float], index: int, horizon: int = PREV_HORIZON_TREND_HORIZON, threshold: float = PREV_HORIZON_TREND_THRESHOLD) -> float:
    if index < horizon:
        return 0.0
    prev_close = closes[index - 1]
    start_close = closes[index - horizon]
    if start_close == 0.0:
        return 0.0
    change = prev_close / start_close - 1.0
    if change > threshold:
        return 1.0
    if change < -threshold:
        return -1.0
    return 0.0


def _indicator_zscore(value_at: Callable[[int], float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    sample = [value_at(position) for position in range(index + 1 - window, index + 1)]
    scale = _stddev(sample)
    if scale == 0.0:
        return 0.0
    return (sample[-1] - mean(sample)) / scale


def _indicator_ratio_to_mean(value_at: Callable[[int], float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    sample = [value_at(position) for position in range(index + 1 - window, index + 1)]
    average = mean(sample)
    if average == 0.0:
        return 0.0
    return sample[-1] / average - 1.0


def _positive_denominator(*values: float) -> float:
    finite_values = [value for value in values if isfinite(value) and value > 1e-12]
    if finite_values:
        return max(finite_values)
    if any(not isfinite(value) for value in values):
        return float("nan")
    return 1e-12


def _zscore(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    sample = values[index + 1 - window:index + 1]
    scale = _stddev(sample)
    if scale == 0.0:
        return 0.0
    return (values[index] - mean(sample)) / scale


def _rsi(values: Sequence[float], index: int, period: int) -> float:
    if index < period:
        return 50.0
    gains = 0.0
    losses = 0.0
    for position in range(index + 1 - period, index + 1):
        change = values[position] - values[position - 1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _bb_width(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    sample = values[index + 1 - window:index + 1]
    mean_value = mean(sample)
    std_value = _stddev(sample)
    if mean_value == 0.0:
        return 0.0
    return (2.0 * std_value) / mean_value


def _bb_percent_b(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.5
    sample = values[index + 1 - window:index + 1]
    mean_value = mean(sample)
    std_value = _stddev(sample)
    upper = mean_value + 2.0 * std_value
    lower = mean_value - 2.0 * std_value
    if upper == lower:
        return 0.5
    return (values[index] - lower) / (upper - lower)


def _ema_slope(values: Sequence[float], index: int, ema_period: int, slope_window: int) -> float:
    if index + 1 < ema_period + slope_window:
        return 0.0
    ema_values = [_ema(values, position, ema_period) for position in range(index + 1 - slope_window, index + 1)]
    return _trend_slope(ema_values, slope_window - 1, slope_window)


def _rolling_vwap(closes: Sequence[float], volumes: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    total_value = 0.0
    total_volume = 0.0
    for position in range(index + 1 - window, index + 1):
        total_value += closes[position] * volumes[position]
        total_volume += volumes[position]
    return total_value / total_volume if total_volume > 0 else 0.0


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    average = mean(values)
    variance = mean([(value - average) ** 2 for value in values])
    return sqrt(variance) if variance > 0.0 else 0.0


# ---------------------------------------------------------------------------
# Vectorized NumPy series helpers used by build_feature_rows.
#
# Each helper produces the same per-index value as the equivalent scalar
# function above (e.g. _np_return_series matches _return(values, i, lookback)
# for every i). These exist purely so the main per-candle loop in
# build_feature_rows can index into pre-computed arrays instead of recomputing
# rolling reductions for every candle.
# ---------------------------------------------------------------------------


def _np_return_series(values: np.ndarray, lookback: int) -> np.ndarray:
    """Per-index return matching _return(values, i, lookback).

    return[i] = values[i] / values[i - lookback] - 1.0 if i >= lookback and
    values[i - lookback] != 0.0, else 0.0.
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if lookback <= 0 or n <= lookback:
        return result
    prev = values[:-lookback]
    curr = values[lookback:]
    mask = prev != 0.0
    result[lookback:] = np.where(mask, curr / np.where(mask, prev, 1.0) - 1.0, 0.0)
    return result


def _np_log_return_series(values: np.ndarray, lookback: int) -> np.ndarray:
    """Per-index log-return matching _log_return(values, i, lookback)."""
    n = len(values)
    result = np.zeros(n, dtype=float)
    if lookback <= 0 or n <= lookback:
        return result
    prev = values[:-lookback]
    curr = values[lookback:]
    valid = (prev > 0.0) & (curr > 0.0)
    safe_ratio = np.where(valid, curr / np.where(valid, prev, 1.0), 1.0)
    result[lookback:] = np.where(valid, np.log(safe_ratio), 0.0)
    return result


def _np_rolling_mean_strict(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean with strict warmup (returns 0.0 before window is full).

    Matches _rolling_mean_value: 0.0 while index + 1 < window, then the
    plain arithmetic mean of values[index+1-window:index+1].
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    cumsum = np.concatenate(([0.0], np.cumsum(values)))
    result[window - 1:] = (cumsum[window:] - cumsum[:-window]) / window
    return result


def _np_rolling_std_strict(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling population stddev (ddof=0) with strict warmup.

    Matches _rolling_std (which calls _stddev internally on a slice).
    Uses prefix sums of values and squared values for O(n) total time.
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    cumsum = np.concatenate(([0.0], np.cumsum(values)))
    cumsum_sq = np.concatenate(([0.0], np.cumsum(values * values)))
    window_sum = cumsum[window:] - cumsum[:-window]
    window_sum_sq = cumsum_sq[window:] - cumsum_sq[:-window]
    window_mean = window_sum / window
    variance = window_sum_sq / window - window_mean * window_mean
    # Floating-point cancellation can drive variance slightly negative; clamp.
    variance = np.where(variance > 0.0, variance, 0.0)
    result[window - 1:] = np.sqrt(variance)
    return result


def _np_zscore_series(values: np.ndarray, window: int) -> np.ndarray:
    """Per-index zscore matching _zscore: (x - mean) / std with std==0 -> 0."""
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    cumsum = np.concatenate(([0.0], np.cumsum(values)))
    cumsum_sq = np.concatenate(([0.0], np.cumsum(values * values)))
    window_sum = cumsum[window:] - cumsum[:-window]
    window_sum_sq = cumsum_sq[window:] - cumsum_sq[:-window]
    window_mean = window_sum / window
    variance = window_sum_sq / window - window_mean * window_mean
    variance = np.where(variance > 0.0, variance, 0.0)
    scale = np.sqrt(variance)
    current = values[window - 1:]
    z = np.where(scale > 0.0, (current - window_mean) / np.where(scale > 0.0, scale, 1.0), 0.0)
    result[window - 1:] = z
    return result


def _np_rolling_max_strict(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling max with strict warmup. Matches _rolling_max."""
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(values, window_shape=window)
    result[window - 1:] = windows.max(axis=1)
    return result


def _np_rolling_min_strict(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling min with strict warmup. Matches _rolling_min."""
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(values, window_shape=window)
    result[window - 1:] = windows.min(axis=1)
    return result


def _np_trend_slope_series(values: np.ndarray, window: int) -> np.ndarray:
    """Per-index trend slope matching _trend_slope.

    slope = sum((pos - x_mean) * (val - y_mean)) / sum((pos - x_mean)^2),
    then divided by values[index]. Returns 0 where index + 1 < window
    or values[index] == 0.
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    x = np.arange(window, dtype=float)
    x_mean = (window - 1) / 2.0
    denom = float(np.sum((x - x_mean) ** 2))
    if denom == 0.0:
        return result
    # Use convolutions equivalent to the original sums over each window
    sum_y = np.convolve(values, np.ones(window, dtype=float), mode="valid")
    sum_xy = np.convolve(values, x[::-1], mode="valid")
    slopes = (sum_xy - x_mean * sum_y) / denom
    current = values[window - 1:]
    safe = current != 0.0
    result[window - 1:] = np.where(safe, slopes / np.where(safe, current, 1.0), 0.0)
    return result


def _np_ratio_to_mean_series(values: np.ndarray, window: int) -> np.ndarray:
    """Per-index ratio-to-rolling-mean matching _ratio_to_mean.

    result[i] = values[i] / mean(values[i+1-window:i+1]) - 1.0
    Returns 0.0 in warmup or when the rolling mean is exactly 0.
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    sma = _np_rolling_mean_strict(values, window)
    current = values[window - 1:]
    sma_slice = sma[window - 1:]
    safe = sma_slice != 0.0
    result[window - 1:] = np.where(safe, current / np.where(safe, sma_slice, 1.0) - 1.0, 0.0)
    return result


def _np_rolling_return_extreme_series(values: np.ndarray, window: int, use_max: bool) -> np.ndarray:
    """Per-index rolling max/min over the 1-bar return series.

    Matches _rolling_return_extreme: returns 0.0 for index < window
    (note: original uses `index < window`, not `index + 1 < window`).
    """
    n = len(values)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n <= window:
        return result
    one_bar_returns = _np_return_series(values, 1)
    # The original takes positions [index+1-window .. index]; in array terms
    # this is a sliding window of size `window` over `one_bar_returns`.
    # Original sets result for index < window to 0.0 (i.e. starts at index = window).
    windows = np.lib.stride_tricks.sliding_window_view(one_bar_returns, window_shape=window)
    # windows[i] covers one_bar_returns[i:i+window]; we want the window ending
    # at index i, i.e. one_bar_returns[i+1-window:i+1] = windows[i+1-window].
    # The valid window-end index range is [window-1, n-1], but the original
    # condition `index < window` discards index == window-1 too, so we start
    # at index == window.
    agg = windows.max(axis=1) if use_max else windows.min(axis=1)
    # agg[k] corresponds to index = k + window - 1 in the original series.
    # Original wants index >= window, i.e. k >= 1.
    result[window:] = agg[1:]
    return result


def _np_parkinson_vol_series(highs: np.ndarray, lows: np.ndarray, window: int) -> np.ndarray:
    """Matches _parkinson_vol for every index."""
    n = len(highs)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    valid = (highs > 0.0) & (lows > 0.0)
    ratio = np.where(valid, highs / np.where(valid, lows, 1.0), 1.0)
    hl_log = np.where(valid, np.log(ratio), 0.0)
    terms = hl_log * hl_log
    # rolling mean of terms
    cumsum = np.concatenate(([0.0], np.cumsum(terms)))
    window_mean = (cumsum[window:] - cumsum[:-window]) / window
    variance = window_mean / (4.0 * log(2.0))
    variance = np.where(variance > 0.0, variance, 0.0)
    result[window - 1:] = np.sqrt(variance)
    return result


def _np_garman_klass_vol_series(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    window: int,
) -> np.ndarray:
    """Matches _garman_klass_vol for every index."""
    n = len(highs)
    result = np.zeros(n, dtype=float)
    if n == 0 or window <= 0 or n < window:
        return result
    valid = (highs > 0.0) & (lows > 0.0) & (opens > 0.0) & (closes > 0.0)
    hl_ratio = np.where(valid, highs / np.where(valid, lows, 1.0), 1.0)
    co_ratio = np.where(valid, closes / np.where(valid, opens, 1.0), 1.0)
    hl_log = np.where(valid, np.log(hl_ratio), 0.0)
    co_log = np.where(valid, np.log(co_ratio), 0.0)
    terms = np.where(
        valid,
        0.5 * hl_log * hl_log - (2.0 * log(2.0) - 1.0) * co_log * co_log,
        0.0,
    )
    cumsum = np.concatenate(([0.0], np.cumsum(terms)))
    window_mean = (cumsum[window:] - cumsum[:-window]) / window
    variance = np.where(window_mean > 0.0, window_mean, 0.0)
    result[window - 1:] = np.sqrt(variance)
    return result


def _np_inside_bar_flag_series(highs: np.ndarray, lows: np.ndarray) -> np.ndarray:
    """Matches _inside_bar_flag: 1.0 when current bar is fully inside prev bar."""
    n = len(highs)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result
    inside = (highs[1:] <= highs[:-1]) & (lows[1:] >= lows[:-1])
    result[1:] = inside.astype(float)
    return result


def _np_outside_bar_flag_series(highs: np.ndarray, lows: np.ndarray) -> np.ndarray:
    """Matches _outside_bar_flag: 1.0 when current bar engulfs prev bar."""
    n = len(highs)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result
    outside = (highs[1:] >= highs[:-1]) & (lows[1:] <= lows[:-1])
    result[1:] = outside.astype(float)
    return result


def labeled_row_dict(row: LabeledRow, feature_names: Sequence[str]) -> dict[str, object]:
    output: dict[str, object] = {
        "index": row.index,
        "open_time": row.open_time.isoformat(),
        "label": row.label,
        "label_reason": row.label_reason,
        "target_return": row.target_return,
        "gap_flag": row.gap_flag,
        "repaired": row.repaired,
        "warmup_invalid": row.warmup_invalid,
        "user_regime": row.user_regime,
    }
    for name in feature_names:
        output[name] = row.features[name]
    return output


def rows_from_mapping(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]


def label_reason_counts(rows: Sequence[LabeledRow]) -> dict[str, int]:
    counts = {reason: 0 for reason in LABEL_REASON_BUCKETS}
    for row in rows:
        counts[row.label_reason] = counts.get(row.label_reason, 0) + 1
    return counts


def _depth_value(external_sources: Mapping[str, object] | None, key: str) -> float:
    if external_sources is None:
        return 0.0
    depth = external_sources.get("depth_snapshot")
    if not isinstance(depth, Mapping):
        return 0.0
    return float(depth.get(key, 0.0))


def _spread_value(external_sources: Mapping[str, object] | None, close: float) -> float:
    best_bid = _depth_value(external_sources, "best_bid")
    best_ask = _depth_value(external_sources, "best_ask")
    if best_bid > 0 and best_ask > 0:
        mid = (best_bid + best_ask) / 2
        return (best_ask - best_bid) / mid if mid > 0 else 0.0
    return 0.0001


def _spread_bps_value(external_sources: Mapping[str, object] | None, close: float) -> float:
    return _spread_value(external_sources, close) * 10000.0


def _bid_ask_imbalance_value(external_sources: Mapping[str, object] | None) -> float:
    bid_qty = _depth_value(external_sources, "bid_qty")
    ask_qty = _depth_value(external_sources, "ask_qty")
    if bid_qty > 0 or ask_qty > 0:
        return (bid_qty - ask_qty) / max(bid_qty + ask_qty, 1e-12)
    return 0.0


def _best_bid_qty_ratio_value(external_sources: Mapping[str, object] | None) -> float:
    bid_qty = _depth_value(external_sources, "bid_qty")
    ask_qty = _depth_value(external_sources, "ask_qty")
    if bid_qty > 0 or ask_qty > 0:
        return bid_qty / max(bid_qty + ask_qty, 1e-12)
    return 0.5


def _best_ask_qty_ratio_value(external_sources: Mapping[str, object] | None) -> float:
    bid_qty = _depth_value(external_sources, "bid_qty")
    ask_qty = _depth_value(external_sources, "ask_qty")
    if bid_qty > 0 or ask_qty > 0:
        return ask_qty / max(bid_qty + ask_qty, 1e-12)
    return 0.5


def _microprice_deviation_value(external_sources: Mapping[str, object] | None, close: float) -> float:
    best_bid = _depth_value(external_sources, "best_bid")
    best_ask = _depth_value(external_sources, "best_ask")
    microprice = _depth_value(external_sources, "microprice")
    if best_bid > 0 and best_ask > 0 and microprice > 0:
        mid = (best_bid + best_ask) / 2
        return (microprice - mid) / mid if mid > 0 else 0.0
    return 0.0


def _order_book_pressure_value(external_sources: Mapping[str, object] | None) -> float:
    bid_qty = _depth_value(external_sources, "bid_qty")
    ask_qty = _depth_value(external_sources, "ask_qty")
    if bid_qty > 0 or ask_qty > 0:
        return (bid_qty - ask_qty) / max(bid_qty + ask_qty, 1e-12)
    return 0.0


def _adl_indicator_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    adl = external_sources.get("adl_quantile")
    if isinstance(adl, Mapping):
        return float(adl.get("adl_quantile", 0.0))
    return 0.0


def _funding_rate_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    funding = external_sources.get("funding_rate")
    if isinstance(funding, Mapping):
        return float(funding.get("current_rate", 0.0))
    return 0.0


def _regime_probability_feature_value(external_sources: Mapping[str, object] | None, feature_name: str) -> float:
    """Read a pre-computed regime probability from external_sources["regime_classifier"].

    Callers that ran the OOF regime-classifier pipeline (regime_classifier.py)
    pack per-candle results as external_sources[candle_time]["regime_classifier"]
    = {"regime_prob_up": .., "regime_prob_range": .., "regime_prob_down": ..}.
    Returns 0.0 when absent, so the feature degrades to a constant (like F16
    metrics) rather than raising.
    """
    if external_sources is None:
        return 0.0
    snapshot = external_sources.get("regime_classifier")
    if isinstance(snapshot, Mapping):
        try:
            return float(snapshot.get(feature_name, 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _metrics_feature_value(external_sources: Mapping[str, object] | None, feature_name: str) -> float:
    """Read a pre-computed metrics feature from external_sources["metrics"].

    The training pipeline forward-fills the 5m metrics-derived features onto
    the 1m clock (see metrics_source.metrics_features_to_minutes) and packs
    them per-candle as external_sources[candle_time]["metrics"] = {feature: v}.
    Returns 0.0 when metrics are absent (e.g. training run without
    --metrics-dir), so the feature degrades to a constant rather than raising.
    """
    if external_sources is None:
        return 0.0
    metrics = external_sources.get("metrics")
    if isinstance(metrics, Mapping):
        try:
            return float(metrics.get(feature_name, 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _next_funding_rate_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    funding = external_sources.get("funding_rate")
    if isinstance(funding, Mapping):
        return float(funding.get("next_rate", 0.0))
    return 0.0


def _minutes_to_next_funding_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 480.0
    funding = external_sources.get("funding_rate")
    if isinstance(funding, Mapping):
        return float(funding.get("minutes_to_next", 480.0))
    return 480.0


def _funding_blackout_active_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    funding = external_sources.get("funding_rate")
    if isinstance(funding, Mapping):
        minutes = float(funding.get("minutes_to_next", 480.0))
        return 1.0 if minutes <= 60.0 else 0.0
    return 0.0


def _mark_price_basis_value(external_sources: Mapping[str, object] | None, close: float) -> float:
    if external_sources is None:
        return 0.0
    mark = external_sources.get("mark_price_1m")
    if isinstance(mark, Mapping):
        mark_price = float(mark.get("mark_price", 0.0))
        if mark_price > 0 and close > 0:
            return (mark_price - close) / close
    return 0.0


def _premium_index_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    premium = external_sources.get("premium_index_1m")
    if isinstance(premium, Mapping):
        return float(premium.get("premium_index", 0.0))
    return 0.0


def _leverage_bracket_utilization_value(external_sources: Mapping[str, object] | None) -> float:
    if external_sources is None:
        return 0.0
    leverage = external_sources.get("leverage_bracket")
    if isinstance(leverage, Mapping):
        position_notional = float(leverage.get("position_notional", 0.0))
        bracket_cap = float(leverage.get("bracket_cap", 1e-12))
        return position_notional / max(bracket_cap, 1e-12)
    return 0.0


class ExternalSourcesCollector:
    """Collect real F11/F12 external sources (funding rate, mark price) from Binance API."""

    def __init__(self, allow_network: bool = False, base_url: str = "https://fapi.binance.com", timeout_seconds: int = 10) -> None:
        self.allow_network = allow_network
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _fetch_klines(
        self,
        endpoint: str,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> list[list[float]]:
        if not self.allow_network:
            raise RuntimeError("external sources collection requires explicit allow_network=True")
        params: dict[str, object] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{endpoint}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-offline-research/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"unexpected klines response payload from {endpoint}")
        return payload

    def fetch_mark_price_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        rows = self._fetch_klines("/fapi/v1/markPriceKlines", symbol, interval, start_time_ms, end_time_ms, limit)
        return [
            {
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
            }
            for row in rows
        ]

    def fetch_premium_index_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        rows = self._fetch_klines("/fapi/v1/premiumIndexKlines", symbol, interval, start_time_ms, end_time_ms, limit)
        return [
            {
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
            }
            for row in rows
        ]

    def fetch_funding_rate_history(
        self,
        symbol: str = "BTCUSDT",
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        if not self.allow_network:
            raise RuntimeError("external sources collection requires explicit allow_network=True")
        params: dict[str, object] = {"symbol": symbol, "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/fapi/v1/fundingRate?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-offline-research/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("unexpected funding rate response payload")
        return [
            {
                "symbol": row.get("symbol"),
                "fundingTime": row.get("fundingTime"),
                "fundingRate": row.get("fundingRate"),
                "markPrice": row.get("markPrice"),
            }
            for row in payload
        ]

    def build_external_sources_for_candles(
        self,
        candles: Sequence[data.Candle],
        symbol: str = "BTCUSDT",
    ) -> dict[datetime, dict[str, object]]:
        if not candles:
            return {}
        if not self.allow_network:
            return {}
        start_time_ms = int(candles[0].open_time.timestamp() * 1000)
        end_time_ms = int(candles[-1].open_time.timestamp() * 1000)
        funding_history = self.fetch_funding_rate_history(
            symbol=symbol,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            limit=1000,
        )
        # Build funding rate lookup by time
        funding_by_time: dict[int, dict[str, object]] = {}
        for row in funding_history:
            funding_time_ms = int(row.get("fundingTime", 0))
            funding_by_time[funding_time_ms] = {
                "current_rate": float(row.get("fundingRate", 0.0)),
                "next_rate": float(row.get("fundingRate", 0.0)),
                "minutes_to_next": 480.0,
            }
        # Fetch real mark price and premium index klines
        try:
            mark_price_history = self.fetch_mark_price_klines(
                symbol=symbol,
                interval="1m",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                limit=1000,
            )
            mark_price_by_time: dict[int, dict[str, object]] = {
                int(row["open_time"]): {"mark_price": row["close"]}
                for row in mark_price_history
            }
        except (urllib.error.URLError, ValueError) as e:
            print(f"Warning: failed to fetch mark price klines: {e}")
            mark_price_by_time = {}
        try:
            premium_index_history = self.fetch_premium_index_klines(
                symbol=symbol,
                interval="1m",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                limit=1000,
            )
            premium_index_by_time: dict[int, float] = {
                int(row["open_time"]): row["close"]
                for row in premium_index_history
            }
        except (urllib.error.URLError, ValueError) as e:
            print(f"Warning: failed to fetch premium index klines: {e}")
            premium_index_by_time = {}
        # Map each candle to external sources
        external_sources: dict[datetime, dict[str, object]] = {}
        for candle in candles:
            candle_time_ms = int(candle.open_time.timestamp() * 1000)
            # Find closest funding rate (funding happens every 8 hours)
            closest_funding = None
            min_diff = float("inf")
            for funding_time_ms, funding_data in funding_by_time.items():
                diff = abs(candle_time_ms - funding_time_ms)
                if diff < min_diff:
                    min_diff = diff
                    closest_funding = funding_data
            sources: dict[str, object] = {}
            if closest_funding:
                sources["funding_rate"] = closest_funding
            # Use real mark price when available, fallback to approximation
            mark_data = mark_price_by_time.get(candle_time_ms)
            if mark_data:
                mark_price = float(mark_data["mark_price"])
                sources["mark_price_1m"] = {
                    "mark_price": mark_price,
                }
            else:
                sources["mark_price_1m"] = {"mark_price": candle.close * 1.0002}
            premium_index = premium_index_by_time.get(candle_time_ms)
            if premium_index is not None:
                sources["premium_index_1m"] = {"premium_index": float(premium_index)}
            external_sources[candle.open_time] = sources
        return external_sources
