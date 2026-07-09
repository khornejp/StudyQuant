"""Binance futures ``metrics`` archive: download, dedup, and 1m alignment.

The ``metrics`` archive (https://data.binance.vision/data/futures/um/daily/
metrics/BTCUSDT/) provides derivatives sentiment data that is NOT derivable
from klines:

    create_time, symbol,
    sum_open_interest, sum_open_interest_value,
    count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio,
    count_long_short_ratio, sum_taker_long_short_vol_ratio

These are 5-minute observations (BTCUSDT metrics exist from ~2020-09). This
module downloads the daily CSV zips, de-duplicates rows sharing a create_time,
and forward-fills the 5-minute series onto the 1-minute feature clock WITHOUT
look-ahead: every 1m bar sees only the last metrics observation at or before
its own open_time.

IMPORTANT (train/live parity): this module only builds the TRAINING-side
metrics from the historical archive. To deploy models that use these features
live, a matching real-time source (Binance /futures/data/* REST endpoints)
MUST be wired into the live engine. Until that exists, models trained with
these features are for RESEARCH ONLY and must not drive live orders — the same
train/live gap that made the depth features unusable would otherwise recur.
"""
from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

METRICS_BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT"

# Columns as delivered by the archive. Order is not relied upon — we parse by
# header name — but this documents the expected schema.
METRICS_CSV_FIELDS: tuple[str, ...] = (
    "create_time",
    "symbol",
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
)

# Numeric columns we surface downstream (symbol/create_time handled separately).
METRICS_VALUE_FIELDS: tuple[str, ...] = (
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
)


class MetricsDownloadError(RuntimeError):
    """Raised when a metrics archive file cannot be downloaded."""


class MetricsValidationError(RuntimeError):
    """Raised when a metrics CSV is missing required columns or is malformed."""


@dataclass(frozen=True)
class MetricsRow:
    """One metrics observation at a specific create_time (UTC)."""

    create_time: datetime
    values: Mapping[str, float]


def _parse_metrics_create_time(raw: str) -> datetime:
    """Parse a create_time cell into a UTC datetime.

    The archive uses 'YYYY-MM-DD HH:MM:SS' (sometimes with fractional seconds).
    A pure integer epoch-ms is also accepted defensively.
    """
    text = raw.strip()
    if not text:
        raise MetricsValidationError("empty create_time")
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000.0, tz=timezone.utc)
    normalized = text.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise MetricsValidationError(f"unrecognized create_time format: {raw!r}")


def parse_metrics_csv_text(csv_text: str) -> list[MetricsRow]:
    """Parse a metrics CSV into rows, tolerant of a header or its absence.

    De-dup is NOT done here (a single daily file is parsed as-is); callers
    combine days and then de-dup, so cross-file duplicates at day boundaries
    are also handled.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows_raw = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows_raw:
        return []
    # Detect header: first cell is non-numeric label 'create_time'.
    header = rows_raw[0]
    has_header = header and header[0].strip().lower() == "create_time"
    if has_header:
        field_index = {name.strip().lower(): idx for idx, name in enumerate(header)}
        data_rows = rows_raw[1:]
    else:
        field_index = {name: idx for idx, name in enumerate(METRICS_CSV_FIELDS)}
        data_rows = rows_raw

    required = ("create_time",) + METRICS_VALUE_FIELDS
    missing = [name for name in required if name not in field_index]
    if missing:
        raise MetricsValidationError(f"metrics CSV missing columns: {', '.join(missing)}")

    parsed: list[MetricsRow] = []
    for row in data_rows:
        try:
            ct = _parse_metrics_create_time(row[field_index["create_time"]])
        except (IndexError, MetricsValidationError):
            continue
        values: dict[str, float] = {}
        ok = True
        for name in METRICS_VALUE_FIELDS:
            idx = field_index[name]
            try:
                values[name] = float(row[idx])
            except (IndexError, ValueError):
                ok = False
                break
        if ok:
            parsed.append(MetricsRow(create_time=ct, values=values))
    return parsed


def dedup_metrics_rows(rows: Iterable[MetricsRow]) -> list[MetricsRow]:
    """Collapse rows that share a create_time, keeping the LAST occurrence.

    The archive sometimes writes two rows with an identical create_time (a
    polling artifact). When the duplicate values are identical this is a no-op;
    when they differ, keeping the last-written row treats it as a correction.
    Because both rows carry the SAME timestamp, keeping either introduces no
    look-ahead. Output is sorted ascending by create_time.
    """
    by_time: dict[datetime, MetricsRow] = {}
    for row in rows:
        by_time[row.create_time] = row  # later write wins for equal create_time
    return [by_time[t] for t in sorted(by_time)]


def align_metrics_to_minutes(
    rows: Sequence[MetricsRow],
    minute_times: Sequence[datetime],
) -> dict[datetime, dict[str, float]]:
    """Forward-fill metrics onto a 1-minute clock without look-ahead.

    For each minute t in ``minute_times`` (assumed UTC, ascending), assign the
    most recent metrics observation whose create_time <= t. Minutes before the
    first observation get no entry (caller decides the fallback). This is a
    causal as-of join: a bar never sees a metrics value stamped after it.
    """
    aligned: dict[datetime, dict[str, float]] = {}
    if not rows:
        return aligned
    ordered = dedup_metrics_rows(rows)
    idx = 0
    n = len(ordered)
    current: dict[str, float] | None = None
    for minute in minute_times:
        while idx < n and ordered[idx].create_time <= minute:
            current = dict(ordered[idx].values)
            idx += 1
        if current is not None:
            aligned[minute] = current
    return aligned


def _metrics_csv_text_from_zip(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise MetricsValidationError("metrics zip contains no CSV")
        with archive.open(names[0]) as handle:
            return handle.read().decode("utf-8")


class BinanceMetricsDownloader:
    """Download daily metrics archives, mirroring BinanceArchiveDownloader.

    Network is only touched when ``download_range`` is called. Callers must opt
    in explicitly (the pipeline passes a dedicated flag), matching the project's
    no-implicit-network policy.
    """

    def __init__(
        self,
        base_url: str = METRICS_BASE_URL,
        symbol: str = "BTCUSDT",
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
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.urlopen = urlopen or urllib.request.urlopen
        self.sleep = sleep or time.sleep
        self.request_interval_seconds = request_interval_seconds

    def _day_url(self, day: date) -> tuple[str, str]:
        # metrics archive layout: BTCUSDT-metrics-YYYY-MM-DD.zip (no interval).
        zip_name = f"{self.symbol}-metrics-{day.isoformat()}.zip"
        return f"{self.base_url}/{zip_name}", zip_name

    def download_day(self, day: date, output_dir: Path, force: bool = False) -> list[MetricsRow]:
        url, zip_name = self._day_url(day)
        cached = output_dir / zip_name
        # Reuse an already-downloaded file instead of re-fetching. Validate it
        # first (parse it); if the cached file is corrupt/partial, fall through
        # to a fresh download. force=True bypasses the cache entirely.
        if not force and cached.exists():
            try:
                csv_text = _metrics_csv_text_from_zip(cached.read_bytes())
                return parse_metrics_csv_text(csv_text)
            except (zipfile.BadZipFile, UnicodeDecodeError, MetricsValidationError, ValueError, OSError):
                pass  # corrupt cache -> re-download below
        request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-metrics-crawler/0.1"})
        backoff = 1.0
        last_error: BaseException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with self.urlopen(request, timeout=self.timeout_seconds) as response:  # type: ignore[attr-defined]
                    payload = bytes(response.read())  # type: ignore[attr-defined]
                csv_text = _metrics_csv_text_from_zip(payload)
                rows = parse_metrics_csv_text(csv_text)
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / zip_name).write_bytes(payload)
                if self.request_interval_seconds > 0.0:
                    self.sleep(self.request_interval_seconds)
                return rows
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code == 404:
                    # Some early days may be missing; treat as empty, not fatal.
                    raise MetricsDownloadError(f"HTTP 404 metrics not found: {zip_name}") from error
                if attempt >= self.max_retries:
                    break
                self.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                self.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
            except (zipfile.BadZipFile, UnicodeDecodeError, MetricsValidationError, ValueError) as error:
                raise MetricsValidationError(f"invalid metrics CSV for {zip_name}: {error}") from error
        raise MetricsDownloadError(f"failed downloading {zip_name} after {self.max_retries} attempts: {last_error}")

    def download_range(
        self,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        output_dir: Path | str,
        force: bool = False,
    ) -> list[MetricsRow]:
        """Download all days in [start, end], returning combined deduped rows.

        Days whose zip already exists on disk are reused (not re-downloaded)
        unless force=True. Missing days (404) are skipped with a note rather
        than aborting, since the metrics archive can have gaps. All rows across
        days are combined and de-duplicated by create_time at the end.
        """
        start = _as_date(start_date)
        end = _as_date(end_date)
        if start > end:
            raise ValueError("start_date must be on or before end_date")
        destination = Path(output_dir)
        all_rows: list[MetricsRow] = []
        cached_days = 0
        downloaded_days = 0
        skipped_days = 0
        day = start
        while day <= end:
            _, zip_name = self._day_url(day)
            was_cached = (destination / zip_name).exists() and not force
            try:
                all_rows.extend(self.download_day(day, destination, force=force))
                if was_cached:
                    cached_days += 1
                else:
                    downloaded_days += 1
            except MetricsDownloadError as error:
                skipped_days += 1
                print(f"[METRICS] skipping {day.isoformat()}: {error}")
            day = day + timedelta(days=1)
        print(f"[METRICS] reused {cached_days} cached, downloaded {downloaded_days} new, skipped {skipped_days} missing")
        return dedup_metrics_rows(all_rows)


# Feature names produced by compute_metrics_features(). Registering these in
# the feature registry (with source "metrics") is the next step; kept here so
# the downloader module is the single source of truth for what it emits.
METRICS_FEATURE_NAMES: tuple[str, ...] = (
    # Open interest: absolute scale drifts over years, so we never expose the
    # raw level. Change-rates and a rolling z-score are scale-stable.
    "oi_change_rate_5m",
    "oi_change_rate_30m",
    "oi_zscore_1d",
    "oi_value_zscore_1d",
    # Long/short ratios are already ratios (scale-stable) -> raw + short change.
    "toptrader_ls_account",
    "toptrader_ls_position",
    "global_ls_account",
    "taker_ls_ratio",
    "toptrader_ls_account_change_5m",
    "global_ls_account_change_5m",
    "taker_ls_ratio_change_5m",
)

# Rolling window lengths expressed in 5-minute metric ticks.
_TICKS_30M = 6      # 30 minutes / 5m
_TICKS_1D = 288     # 24h / 5m


def _causal_change_rate(series: Sequence[float], lag_ticks: int) -> list[float]:
    """(x[t] - x[t-lag]) / |x[t-lag]|, using only past values. 0 before warmup."""
    out = [0.0] * len(series)
    for t in range(len(series)):
        past = t - lag_ticks
        if past < 0:
            continue
        base = series[past]
        if base == 0.0:
            continue
        out[t] = (series[t] - base) / abs(base)
    return out


def _causal_zscore(series: Sequence[float], window_ticks: int) -> list[float]:
    """Rolling z-score over the trailing window (inclusive of t), past-only.

    Uses the window ending at t (values t-window+1 .. t). This is causal: it
    never reads future ticks. Returns 0 until at least 2 samples exist and when
    the trailing std is zero.
    """
    import math

    out = [0.0] * len(series)
    for t in range(len(series)):
        lo = max(0, t - window_ticks + 1)
        window = series[lo : t + 1]
        n = len(window)
        if n < 2:
            continue
        mean = sum(window) / n
        var = sum((v - mean) ** 2 for v in window) / n
        std = math.sqrt(var)
        if std == 0.0:
            continue
        out[t] = (series[t] - mean) / std
    return out


def compute_metrics_features(rows: Sequence[MetricsRow]) -> dict[datetime, dict[str, float]]:
    """Derive causal, scale-stable features from deduped 5m metric rows.

    All derivations look only at past/current ticks (no look-ahead). Returns a
    mapping create_time -> {feature_name: value} at the 5-minute grid; callers
    forward-fill onto the 1m clock with align_metrics_to_minutes-style logic
    (see metrics_features_to_minutes below).
    """
    ordered = dedup_metrics_rows(rows)
    if not ordered:
        return {}
    times = [r.create_time for r in ordered]
    oi = [r.values["sum_open_interest"] for r in ordered]
    oi_val = [r.values["sum_open_interest_value"] for r in ordered]
    tt_acct = [r.values["count_toptrader_long_short_ratio"] for r in ordered]
    tt_pos = [r.values["sum_toptrader_long_short_ratio"] for r in ordered]
    gl_acct = [r.values["count_long_short_ratio"] for r in ordered]
    taker = [r.values["sum_taker_long_short_vol_ratio"] for r in ordered]

    oi_chg_5m = _causal_change_rate(oi, 1)
    oi_chg_30m = _causal_change_rate(oi, _TICKS_30M)
    oi_z = _causal_zscore(oi, _TICKS_1D)
    oi_val_z = _causal_zscore(oi_val, _TICKS_1D)
    tt_acct_chg = _causal_change_rate(tt_acct, 1)
    gl_acct_chg = _causal_change_rate(gl_acct, 1)
    taker_chg = _causal_change_rate(taker, 1)

    features: dict[datetime, dict[str, float]] = {}
    for i, t in enumerate(times):
        features[t] = {
            "oi_change_rate_5m": oi_chg_5m[i],
            "oi_change_rate_30m": oi_chg_30m[i],
            "oi_zscore_1d": oi_z[i],
            "oi_value_zscore_1d": oi_val_z[i],
            "toptrader_ls_account": tt_acct[i],
            "toptrader_ls_position": tt_pos[i],
            "global_ls_account": gl_acct[i],
            "taker_ls_ratio": taker[i],
            "toptrader_ls_account_change_5m": tt_acct_chg[i],
            "global_ls_account_change_5m": gl_acct_chg[i],
            "taker_ls_ratio_change_5m": taker_chg[i],
        }
    return features


def metrics_features_to_minutes(
    rows: Sequence[MetricsRow],
    minute_times: Sequence[datetime],
) -> dict[datetime, dict[str, float]]:
    """Compute 5m features then forward-fill onto the 1m clock, causally.

    Convenience wrapper: compute_metrics_features on the 5m grid, then as-of
    join onto minute_times (each minute sees the last 5m feature vector at or
    before it). Minutes before the first metric observation get no entry.
    """
    feat_5m = compute_metrics_features(rows)
    if not feat_5m:
        return {}
    grid_times = sorted(feat_5m)
    aligned: dict[datetime, dict[str, float]] = {}
    idx = 0
    n = len(grid_times)
    current: dict[str, float] | None = None
    for minute in minute_times:
        while idx < n and grid_times[idx] <= minute:
            current = feat_5m[grid_times[idx]]
            idx += 1
        if current is not None:
            aligned[minute] = current
    return aligned


def load_metrics_dir(metrics_dir: Path) -> list[MetricsRow]:
    """Parse all downloaded metrics zips in a directory, deduped and sorted."""
    rows: list[MetricsRow] = []
    for zip_path in sorted(Path(metrics_dir).glob("*.zip")):
        try:
            payload = zip_path.read_bytes()
            csv_text = _metrics_csv_text_from_zip(payload)
            rows.extend(parse_metrics_csv_text(csv_text))
        except (zipfile.BadZipFile, MetricsValidationError, OSError) as error:
            print(f"[METRICS] skipping {zip_path.name}: {error}")
    return dedup_metrics_rows(rows)


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()
