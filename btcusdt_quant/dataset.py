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
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import isfinite, sqrt, sin
from pathlib import Path
from statistics import mean
from typing import Callable, Mapping, Sequence

from . import data


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


FEATURE_FORMULAS: tuple[dict[str, object], ...] = (
    {"feature_name": "return_1", "category": "F01", "formula": "close_t / close_t-1 - 1", "lookback": 2, "min_samples": 2, "warmup_rule": "strict"},
    {"feature_name": "return_3", "category": "F01", "formula": "close_t / close_t-3 - 1", "lookback": 4, "min_samples": 4, "warmup_rule": "strict"},
    {"feature_name": "return_5", "category": "F01", "formula": "close_t / close_t-5 - 1", "lookback": 6, "min_samples": 6, "warmup_rule": "strict"},
    {"feature_name": "return_10", "category": "F01", "formula": "close_t / close_t-10 - 1", "lookback": 11, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "close_sma_5_ratio", "category": "F02", "formula": "close_t / SMA(close,5) - 1", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
    {"feature_name": "close_sma_10_ratio", "category": "F02", "formula": "close_t / SMA(close,10) - 1", "lookback": 10, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "close_sma_20_ratio", "category": "F02", "formula": "close_t / SMA(close,20) - 1", "lookback": 20, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "close_sma_60_ratio", "category": "F02", "formula": "close_t / SMA(close,60) - 1", "lookback": 60, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "rv_15", "category": "F03", "formula": "stddev(1m returns over 15 bars)", "lookback": 16, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "rv_60", "category": "F03", "formula": "stddev(1m returns over 60 bars)", "lookback": 61, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "rv_120", "category": "F03", "formula": "stddev(1m returns over 120 bars)", "lookback": 121, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "atr_pct", "category": "F03", "formula": "SMA(true_range,14) / close_t", "lookback": 15, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "volume_sma_5_ratio", "category": "F04", "formula": "volume_t / max(SMA(volume,5), 1e-12) - 1", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
    {"feature_name": "volume_sma_20_ratio", "category": "F04", "formula": "volume_t / max(SMA(volume,20), 1e-12) - 1", "lookback": 20, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "taker_ratio", "category": "F04", "formula": "taker_buy_base_volume_t / max(volume_t, 1e-12)", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "trade_count_ratio", "category": "F04", "formula": "number_of_trades_t / max(SMA(number_of_trades,20), 1e-12) - 1", "lookback": 20, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "high_low_range", "category": "F05", "formula": "(high_t - low_t) / close_t", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "body_pct", "category": "F05", "formula": "abs(close_t - open_t) / close_t", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "upper_shadow", "category": "F05", "formula": "high_t - max(open_t, close_t) over close_t", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "lower_shadow", "category": "F05", "formula": "min(open_t, close_t) - low_t over close_t", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "gap_ratio_20", "category": "F06", "formula": "rolling repaired candle ratio over last 20 canonical rows", "lookback": 20, "min_samples": 1, "warmup_rule": "state"},
    {"feature_name": "gap_ratio_60", "category": "F06", "formula": "rolling repaired candle ratio over last 60 canonical rows", "lookback": 60, "min_samples": 1, "warmup_rule": "state"},
    {"feature_name": "gap_ratio_120", "category": "F06", "formula": "rolling repaired candle ratio over last 120 canonical rows", "lookback": 120, "min_samples": 1, "warmup_rule": "state"},
    {"feature_name": "max_gap_run_120", "category": "F06", "formula": "maximum contiguous repaired candle run over last 120 canonical rows", "lookback": 120, "min_samples": 1, "warmup_rule": "state"},
    {"feature_name": "close_zscore_20", "category": "F07", "formula": "(close_t - SMA(close,20)) / stddev(close,20)", "lookback": 20, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "close_zscore_60", "category": "F07", "formula": "(close_t - SMA(close,60)) / stddev(close,60)", "lookback": 60, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "volume_zscore_5", "category": "F07", "formula": "(volume_t - SMA(volume,5)) / stddev(volume,5)", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
    {"feature_name": "volume_zscore_20", "category": "F07", "formula": "(volume_t - SMA(volume,20)) / stddev(volume,20)", "lookback": 20, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "return_5_vol_adj", "category": "F08", "formula": "return_5 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", "lookback": 121, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "return_10_vol_adj", "category": "F08", "formula": "return_10 / max(rv_15, rv_60, rv_120, atr_pct, 1e-12)", "lookback": 121, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "close_zscore_20_vol_adj", "category": "F09", "formula": "close_zscore_20 / max(rv_60, 1e-12)", "lookback": 61, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "volume_zscore_20_vol_adj", "category": "F09", "formula": "volume_zscore_20 / max(rv_60, 1e-12)", "lookback": 61, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "candle_range_vol_adj", "category": "F10", "formula": "high_low_range / max(rv_60, 1e-12)", "lookback": 61, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "body_pct_vol_adj", "category": "F10", "formula": "body_pct / max(rv_60, 1e-12)", "lookback": 61, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "spread", "category": "F11", "formula": "best_ask - best_bid over mid price", "lookback": 1, "min_samples": 1, "warmup_rule": "strict", "scaffold_status": "pending_data_source"},
    {"feature_name": "bid_ask_imbalance", "category": "F11", "formula": "(bid_qty - ask_qty) / max(bid_qty + ask_qty, 1e-12)", "lookback": 1, "min_samples": 1, "warmup_rule": "strict", "scaffold_status": "pending_data_source"},
    {"feature_name": "adl_indicator", "category": "F12", "formula": "exchange ADL quantile indicator", "lookback": 1, "min_samples": 1, "warmup_rule": "state", "scaffold_status": "pending_data_source"},
    {"feature_name": "funding_rate", "category": "F12", "formula": "current and next funding rate state", "lookback": 1, "min_samples": 1, "warmup_rule": "state", "scaffold_status": "pending_data_source"},
)

FEATURE_NAMES: tuple[str, ...] = tuple(str(row["feature_name"]) for row in FEATURE_FORMULAS if row.get("scaffold_status") != "pending_data_source")

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


@dataclass(frozen=True)
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

    def __init__(self, allow_network: bool = False, base_url: str = "https://fapi.binance.com", timeout_seconds: int = 10) -> None:
        self.allow_network = allow_network
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch_klines(self, symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500) -> list[data.Candle]:
        if not self.allow_network:
            raise RuntimeError("public kline download requires explicit allow_network=True")
        if limit <= 0 or limit > 1500:
            raise ValueError("limit must be between 1 and 1500")
        query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
        url = f"{self.base_url}/fapi/v1/klines?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-offline-research/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("unexpected kline response payload")
        return [candle_from_kline_row(row) for row in payload]


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
        zip_name = f"{day.isoformat()}_{self.symbol}-{self.interval}.zip"
        csv_name = f"{day.isoformat()}_{self.symbol}-{self.interval}.csv"
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
    downloaded_days = sum(1 for filename in downloaded_files if filename[:10] in requested_dates)
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


def collect_candles(
    output_path: Path,
    rows: int = 240,
    allow_public_network: bool = False,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
) -> CollectionResult:
    if rows <= 0:
        raise ValueError("rows must be positive")
    if allow_public_network:
        candles = PublicKlineDownloader(allow_network=True).fetch_klines(symbol=symbol, interval=interval, limit=rows)
        source = "binance_public_klines"
        network_used = True
    else:
        candles = expanded_fixture(rows)
        source = "offline_expanded_fixture"
        network_used = False
    write_candles_csv(output_path, candles)
    return CollectionResult(output_path, source, symbol, interval, len(candles), network_used)


def expanded_fixture(rows: int = 240) -> list[data.Candle]:
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
    horizon: int = 3,
    label_threshold: float = 0.0002,
    tp_pct: float = 0.001,
    sl_pct: float = 0.0005,
    external_events: Mapping[object, object] | None = None,
    archive_dir: Path | None = None,
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
        raw = load_csv_candles(input_path)
        source = input_path.as_posix()
    canonical = data.CanonicalTimelineBuilder().build(raw)
    gap_report = summarize_gaps(len(raw), canonical)
    feature_rows = build_feature_rows(canonical)
    labeled_rows = attach_labels(feature_rows, canonical, horizon, label_threshold, tp_pct=tp_pct, sl_pct=sl_pct, external_events=external_events)
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


def build_feature_rows(candles: Sequence[data.Candle]) -> list[FeatureRow]:
    rows: list[FeatureRow] = []
    closes = [candle.close for candle in candles]
    volumes = [candle.volume for candle in candles]
    trades = [float(candle.number_of_trades) for candle in candles]
    warmup_cutoff = max_feature_min_samples() - 1
    for index, candle in enumerate(candles):
        warmup_invalid = index < warmup_cutoff
        return_5 = _return(closes, index, 5)
        return_10 = _return(closes, index, 10)
        rv_15 = _rolling_return_std(closes, index, 15)
        rv_60 = _rolling_return_std(closes, index, 60)
        rv_120 = _rolling_return_std(closes, index, 120)
        atr_pct = _atr_pct(candles, index, 14)
        volatility_denominator = max(rv_15, rv_60, rv_120, atr_pct, 1e-12)
        rv_60_denominator = max(rv_60, 1e-12)
        close_zscore_20 = _zscore(closes, index, 20)
        volume_zscore_20 = _zscore(volumes, index, 20)
        high_low_range = (candle.high - candle.low) / candle.close if candle.close else 0.0
        body_pct = abs(candle.close - candle.open) / candle.close if candle.close else 0.0
        values = {
            "return_1": _return(closes, index, 1),
            "return_3": _return(closes, index, 3),
            "return_5": return_5,
            "return_10": return_10,
            "close_sma_5_ratio": _ratio_to_mean(closes, index, 5),
            "close_sma_10_ratio": _ratio_to_mean(closes, index, 10),
            "close_sma_20_ratio": _ratio_to_mean(closes, index, 20),
            "close_sma_60_ratio": _ratio_to_mean(closes, index, 60),
            "rv_15": rv_15,
            "rv_60": rv_60,
            "rv_120": rv_120,
            "atr_pct": atr_pct,
            "volume_sma_5_ratio": _ratio_to_mean(volumes, index, 5),
            "volume_sma_20_ratio": _ratio_to_mean(volumes, index, 20),
            "taker_ratio": candle.taker_buy_base_volume / candle.volume if candle.volume else 0.0,
            "trade_count_ratio": _ratio_to_mean(trades, index, 20),
            "high_low_range": high_low_range,
            "body_pct": body_pct,
            "upper_shadow": (candle.high - max(candle.open, candle.close)) / candle.close if candle.close else 0.0,
            "lower_shadow": (min(candle.open, candle.close) - candle.low) / candle.close if candle.close else 0.0,
            "gap_ratio_20": candle.gap_ratio_20,
            "gap_ratio_60": candle.gap_ratio_60,
            "gap_ratio_120": candle.gap_ratio_120,
            "max_gap_run_120": float(candle.max_gap_run_120),
            "close_zscore_20": close_zscore_20,
            "close_zscore_60": _zscore(closes, index, 60),
            "volume_zscore_5": _zscore(volumes, index, 5),
            "volume_zscore_20": volume_zscore_20,
            "return_5_vol_adj": return_5 / volatility_denominator,
            "return_10_vol_adj": return_10 / volatility_denominator,
            "close_zscore_20_vol_adj": close_zscore_20 / rv_60_denominator,
            "volume_zscore_20_vol_adj": volume_zscore_20 / rv_60_denominator,
            "candle_range_vol_adj": high_low_range / rv_60_denominator,
            "body_pct_vol_adj": body_pct / rv_60_denominator,
        }
        rows.append(FeatureRow(index, candle.open_time, values, candle.gap_flag, candle.repaired, warmup_invalid))
    return rows


def attach_labels(
    feature_rows: Sequence[FeatureRow],
    candles: Sequence[data.Candle],
    horizon: int,
    label_threshold: float,
    tp_pct: float = 0.001,
    sl_pct: float = 0.0005,
    external_events: Mapping[object, object] | None = None,
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
        if row.warmup_invalid or future_index >= len(candles):
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
        "offline_only": True,
        "network_required": False,
    }


def feature_matrix(build: DatasetBuild) -> tuple[list[list[float]], list[int]]:
    matrix = [[row.features[name] for name in build.feature_names] for row in build.labeled_rows]
    labels = [row.label for row in build.labeled_rows]
    return matrix, labels


def feature_formula_registry() -> dict[str, object]:
    return {"features": [dict(row) for row in FEATURE_FORMULAS]}


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


def _ratio_to_mean(values: Sequence[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    average = mean(values[index + 1 - window:index + 1])
    if average == 0.0:
        return 0.0
    return values[index] / average - 1.0


def _rolling_return_std(values: Sequence[float], index: int, window: int) -> float:
    if index < window:
        return 0.0
    returns = [_return(values, position, 1) for position in range(index + 1 - window, index + 1)]
    return _stddev(returns)


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
