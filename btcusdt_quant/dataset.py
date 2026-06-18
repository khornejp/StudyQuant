from __future__ import annotations

import csv
import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from math import isfinite, log, sqrt, sin
from pathlib import Path
from statistics import mean
from typing import Callable, Mapping, Sequence

from . import data, feature_registry, features, parity, sources


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
class FeatureRow:
    index: int
    open_time: datetime
    features: dict[str, float]
    gap_flag: int
    repaired: bool
    warmup_invalid: bool
    source_availability_status: dict[str, str] = field(default_factory=dict)
    feature_availability_status: dict[str, str] = field(default_factory=dict)
    unavailable_sources: tuple[str, ...] = ()
    fallback_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class LabeledRow:
    index: int
    open_time: datetime
    features: dict[str, float]
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
    ) -> None:
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        self.base_url = base_url.rstrip("/")
        self.symbol = symbol
        self.interval = interval
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.urlopen = urlopen or urllib.request.urlopen
        self.sleep = sleep or time.sleep

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
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    missing = set(ARCHIVE_CSV_FIELDS) - set(fieldnames)
    if missing:
        raise ArchiveValidationError(f"archive CSV missing required columns: {', '.join(sorted(missing))}")
    candles: list[data.Candle] = []
    seen_open_times: set[datetime] = set()
    previous_open_time: datetime | None = None
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
            reader = csv.reader(handle)
            next(reader, None)  # skip header
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


def expanded_fixture(rows: int = 300) -> list[data.Candle]:
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


def build_dataset(
    input_path: Path | None = None,
    stream_buffer: Sequence[data.Candle] | None = None,
    horizon: int = 15,
    label_threshold: float = 0.0002,
    tp_pct: float = 0.0005,
    sl_pct: float = 0.0005,
    external_events: Mapping[object, object] | None = None,
    archive_dir: Path | None = None,
    source_bundle: sources.MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
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
    feature_rows = build_feature_rows(canonical, source_bundle=resolved_source_bundle, external_sources=external_sources)
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
) -> list[FeatureRow]:
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
    warmup_cutoff = max_feature_min_samples() - 1
    for index, candle in enumerate(candles):
        warmup_invalid = index < warmup_cutoff
        return_1 = _return(closes, index, 1)
        return_3 = _return(closes, index, 3)
        return_5 = _return(closes, index, 5)
        return_10 = _return(closes, index, 10)
        return_15 = _return(closes, index, 15)
        return_30 = _return(closes, index, 30)
        return_60 = _return(closes, index, 60)
        momentum_10 = return_10
        momentum_30 = return_30
        sma_5 = _rolling_mean_value(closes, index, 5)
        sma_20 = _rolling_mean_value(closes, index, 20)
        sma_60 = _rolling_mean_value(closes, index, 60)
        ema_12 = _ema(closes, index, 12)
        ema_26 = _ema(closes, index, 26)
        ema_12_26_spread = _spread_to_close(ema_12, ema_26, candle.close)
        sma_20_60_spread = _spread_to_close(sma_20, sma_60, candle.close)
        rv_15 = _rolling_return_std(closes, index, 15)
        rv_5 = _rolling_return_std(closes, index, 5)
        rv_30 = _rolling_return_std(closes, index, 30)
        rv_60 = _rolling_return_std(closes, index, 60)
        rv_120 = _rolling_return_std(closes, index, 120)
        atr_pct = _atr_pct(candles, index, 14)
        atr_pct_30 = _atr_pct(candles, index, 30)
        volatility_denominator = _positive_denominator(rv_15, rv_60, rv_120, atr_pct)
        rv_60_denominator = _positive_denominator(rv_60)
        close_zscore_20 = _zscore(closes, index, 20)
        close_zscore_60 = _zscore(closes, index, 60)
        volume_zscore_5 = _zscore(volumes, index, 5)
        volume_zscore_20 = _zscore(volumes, index, 20)
        trade_count_zscore_20 = _zscore(trades, index, 20)
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
        values = {
            "return_1": return_1,
            "return_3": return_3,
            "return_5": return_5,
            "return_10": return_10,
            "return_15": return_15,
            "return_30": return_30,
            "return_60": return_60,
            "log_return_1": _log_return(closes, index, 1),
            "log_return_5": _log_return(closes, index, 5),
            "momentum_10": momentum_10,
            "momentum_30": momentum_30,
            "rolling_return_max_20": _rolling_return_extreme(closes, index, 20, use_max=True),
            "rolling_return_min_20": _rolling_return_extreme(closes, index, 20, use_max=False),
            "close_sma_5_ratio": _ratio_to_mean(closes, index, 5),
            "close_sma_10_ratio": _ratio_to_mean(closes, index, 10),
            "close_sma_20_ratio": _ratio_to_mean(closes, index, 20),
            "close_sma_60_ratio": _ratio_to_mean(closes, index, 60),
            "close_ema_12_ratio": _ratio_to_value(candle.close, ema_12),
            "close_ema_26_ratio": _ratio_to_value(candle.close, ema_26),
            "ema_12_26_spread": ema_12_26_spread,
            "sma_5_20_spread": _spread_to_close(sma_5, sma_20, candle.close),
            "sma_20_60_spread": sma_20_60_spread,
            "trend_slope_10": _trend_slope(closes, index, 10),
            "trend_slope_30": _trend_slope(closes, index, 30),
            "prev_horizon_trend": _prev_horizon_trend(closes, index),
            "distance_to_high_20": _distance_to_extreme(candle.close, _rolling_max(highs, index, 20)),
            "distance_to_low_20": _distance_to_extreme(candle.close, _rolling_min(lows, index, 20)),
            "rv_5": rv_5,
            "rv_15": rv_15,
            "rv_30": rv_30,
            "rv_60": rv_60,
            "rv_120": rv_120,
            "atr_pct": atr_pct,
            "atr_pct_30": atr_pct_30,
            "parkinson_vol_20": _parkinson_vol(candles, index, 20),
            "garman_klass_vol_20": _garman_klass_vol(candles, index, 20),
            "range_vol_20": _rolling_std(range_pcts, index, 20),
            "har_rv_short": rv_5,
            "har_rv_medium": rv_30,
            "har_rv_long": rv_120,
            "volume_sma_5_ratio": _ratio_to_mean(volumes, index, 5),
            "volume_sma_20_ratio": _ratio_to_mean(volumes, index, 20),
            "volume_sma_60_ratio": _ratio_to_mean(volumes, index, 60),
            "quote_volume_sma_20_ratio": _ratio_to_mean(quote_volumes, index, 20),
            "taker_ratio": taker_ratio,
            "taker_imbalance": taker_imbalance,
            "taker_quote_ratio": taker_quote_ratio,
            "trade_count_ratio": _ratio_to_mean(trades, index, 20),
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
            "range_sma_20_ratio": _ratio_to_mean(ranges, index, 20),
            "inside_bar_flag": _inside_bar_flag(candles, index),
            "outside_bar_flag": _outside_bar_flag(candles, index),
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
            "rv_zscore_60": _indicator_zscore(lambda position: _rolling_return_std(closes, position, 5), index, 60),
            "range_zscore_20": _zscore(range_pcts, index, 20),
            "volatility_regime_60": _indicator_ratio_to_mean(lambda position: _rolling_return_std(closes, position, 15), index, 60),
            "volume_regime_60": _ratio_to_mean(volumes, index, 60),
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
        }
        clipper = features.FeatureClipper()
        clipped = clipper.clip({name: values[name] for name in FEATURE_NAMES})
        nan_classifier = features.NaNSourceClassifier(optional_noncritical_features=set(fallback_features))
        row_context = {
            "gap_flag": candle.gap_flag,
            "canonical_candle_repaired": candle.repaired,
            "warmup_invalid": warmup_invalid,
        }
        nan_status: dict[str, str] = {}
        for name, value in clipped.values.items():
            if value is None:
                nan_status[name] = nan_classifier.classify(row_context, name)
        merged_feature_status = dict(feature_availability_status)
        merged_feature_status.update(nan_status)
        rows.append(
            FeatureRow(
                index,
                candle.open_time,
                clipped.values,
                candle.gap_flag,
                candle.repaired,
                warmup_invalid,
                dict(source_availability_status),
                merged_feature_status,
                unavailable_sources,
                fallback_features,
            )
        )
    return rows


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
        external_label, external_reason = _external_label(row, target_return, label_threshold, external_events)
        if external_label is not None and external_reason is not None:
            label = external_label
            label_reason = external_reason
        labeled.append(
            LabeledRow(
                index=row.index,
                open_time=row.open_time,
                features=dict(row.features),
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


def max_feature_min_samples() -> int:
    values: list[int] = []
    for row in FEATURE_FORMULAS:
        value = row.get("min_samples", 1)
        if not isinstance(value, int):
            raise ValueError("feature min_samples must be an integer")
        if value <= 0:
            raise ValueError("feature min_samples must be positive")
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


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    average = mean(values)
    variance = mean([(value - average) ** 2 for value in values])
    return sqrt(variance) if variance > 0.0 else 0.0


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
    mark = external_sources.get("mark_price_1m")
    if isinstance(mark, Mapping):
        return float(mark.get("premium_index", 0.0))
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
                int(row["open_time"]): {"mark_price": row["close"], "premium_index": 0.0}
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
                premium_index = premium_index_by_time.get(candle_time_ms, 0.0)
                sources["mark_price_1m"] = {
                    "mark_price": mark_price,
                    "premium_index": float(premium_index),
                }
            else:
                sources["mark_price_1m"] = {"mark_price": candle.close * 1.0002, "premium_index": 0.0002}
            external_sources[candle.open_time] = sources
        return external_sources
