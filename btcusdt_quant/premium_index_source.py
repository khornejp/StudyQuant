"""Binance USDT-M ``premiumIndexKlines`` archive: download, parse and align.

The funding archive records a rate only after its eight-hour settlement.  This
archive records the premium-index kline each minute: the perp-versus-index
basis state from which funding is calculated, rather than the settlement
outcome.  It is therefore not reconstructible from the funding series, nor
from the metrics archive, whose fields are open interest and long/short/taker
ratios only.

This module deliberately stops at collection and causal alignment.  It does
not register a feature or make a training path available.  That decision
belongs after a training-span-only IC/ranking measurement.

Causality contract
------------------
``PremiumIndexRow.open_time`` names a one-minute interval and its OHLC values
are complete only at ``close_time`` (normally open_time + 59.999 seconds).
``premium_index_to_minutes`` consequently exposes a row only to a feature
clock at or after its close time; a candle whose open_time is 00:01 first sees
the completed 00:00 premium kline.  It never substitutes the still-forming
00:01 bar.  The archive does not publish a revision/version field or a
publication-latency SLA.  Historical alignment therefore treats a finalized
kline as available at its exchange close timestamp; any live implementation
must add its measured transport/publication delay before using the same value.
The earliest usable timestamp is one minute after the first archived open
timestamp (2019-12-24 00:01 UTC for the currently enumerated BTCUSDT archive).
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
from typing import Callable, Iterable, Sequence

__all__ = [
    "PREMIUM_INDEX_BASE_URL",
    "PremiumIndexRow",
    "PremiumIndexDownloadError",
    "PremiumIndexValidationError",
    "BinancePremiumIndexDownloader",
    "parse_premium_index_csv_text",
    "dedup_premium_index_rows",
    "load_premium_index_dir",
    "premium_index_to_minutes",
]

PREMIUM_INDEX_BASE_URL = (
    "https://data.binance.vision/data/futures/um/daily/"
    "premiumIndexKlines/BTCUSDT/1m"
)
_ONE_MINUTE = timedelta(minutes=1)


class PremiumIndexDownloadError(RuntimeError):
    """A premium-index archive file could not be fetched or read."""


class PremiumIndexValidationError(RuntimeError):
    """A premium-index CSV does not have the expected finalized-kline schema."""


@dataclass(frozen=True)
class PremiumIndexDownloadCoverage:
    """Archive availability observed during one requested range."""

    requested: int
    fetched: int
    missing_dates: tuple[str, ...]


@dataclass(frozen=True)
class PremiumIndexRow:
    """One finalized premium-index kline, all timestamps UTC."""

    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float


def _parse_epoch_ms(raw: str, field: str) -> datetime:
    try:
        value = int(raw.strip())
    except (TypeError, ValueError) as error:
        raise PremiumIndexValidationError(f"invalid {field}: {raw!r}") from error
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)


def parse_premium_index_csv_text(csv_text: str) -> list[PremiumIndexRow]:
    """Strictly parse a daily premium-index kline CSV.

    Binance kline archives use the standard 12-column layout, where column 6
    is close_time.  Six-column historical variants have no close_time; for
    those, the only defensible availability bound is the end of their 1m
    interval.  A header is allowed, but malformed data rows are an error rather
    than a reason to silently manufacture a forward-filled gap.
    """
    records = [row for row in csv.reader(io.StringIO(csv_text)) if row and any(x.strip() for x in row)]
    if not records:
        return []
    first_is_header = records[0][0].strip().lower() in {"open_time", "open time"}
    data_rows = records[1:] if first_is_header else records
    parsed: list[PremiumIndexRow] = []
    for line_number, record in enumerate(data_rows, start=2 if first_is_header else 1):
        if len(record) < 6:
            raise PremiumIndexValidationError(f"row {line_number} has {len(record)} columns; need at least 6")
        try:
            open_time = _parse_epoch_ms(record[0], "open_time")
            op, high, low, close = (float(record[i]) for i in range(1, 5))
            close_time = _parse_epoch_ms(record[6], "close_time") if len(record) >= 7 else open_time + _ONE_MINUTE - timedelta(milliseconds=1)
        except (ValueError, OverflowError, PremiumIndexValidationError) as error:
            raise PremiumIndexValidationError(f"invalid premium-index row {line_number}: {error}") from error
        if close_time < open_time:
            raise PremiumIndexValidationError(f"row {line_number} closes before it opens")
        parsed.append(PremiumIndexRow(open_time, close_time, op, high, low, close))
    return parsed


def dedup_premium_index_rows(rows: Iterable[PremiumIndexRow]) -> list[PremiumIndexRow]:
    """One kline per open timestamp, with a later archive correction winning."""
    by_open_time: dict[datetime, PremiumIndexRow] = {}
    for row in rows:
        by_open_time[row.open_time] = row
    return [by_open_time[when] for when in sorted(by_open_time)]


def _premium_csv_text_from_zip(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise PremiumIndexValidationError("premium-index zip contains no CSV")
        with archive.open(names[0]) as handle:
            return handle.read().decode("utf-8")


class BinancePremiumIndexDownloader:
    """Fetch daily 1m premium-index archives, reusing validated local files."""

    def __init__(
        self,
        base_url: str = PREMIUM_INDEX_BASE_URL,
        symbol: str = "BTCUSDT",
        timeout_seconds: int = 30,
        max_retries: int = 5,
        urlopen: Callable[..., object] | None = None,
        sleep: Callable[[float], None] | None = None,
        request_interval_seconds: float = 0.2,
    ) -> None:
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        self.base_url, self.symbol = base_url.rstrip("/"), symbol
        self.timeout_seconds, self.max_retries = timeout_seconds, max_retries
        self.urlopen, self.sleep = urlopen or urllib.request.urlopen, sleep or time.sleep
        self.request_interval_seconds = request_interval_seconds
        self.last_coverage = PremiumIndexDownloadCoverage(0, 0, ())

    def _day_url(self, day: date) -> tuple[str, str]:
        # ``premiumIndexKlines`` is the directory type; the archive name uses
        # the regular SYMBOL-INTERVAL-DATE convention.
        name = f"{self.symbol}-1m-{day.isoformat()}.zip"
        return f"{self.base_url}/{name}", name

    def download_day(self, day: date, output_dir: Path | str, force: bool = False) -> list[PremiumIndexRow]:
        url, name = self._day_url(day)
        destination = Path(output_dir)
        cached = destination / name
        if cached.exists() and not force:
            try:
                return parse_premium_index_csv_text(_premium_csv_text_from_zip(cached.read_bytes()))
            except (zipfile.BadZipFile, UnicodeDecodeError, OSError, PremiumIndexValidationError):
                cached.unlink(missing_ok=True)  # partial cache: refetch, never trust it
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "btcusdt-quant-premium-crawler/0.1"})
                response = self.urlopen(request, timeout=self.timeout_seconds)  # type: ignore[call-arg]
                payload = bytes(response.read())
                rows = parse_premium_index_csv_text(_premium_csv_text_from_zip(payload))
                destination.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(payload)
                self.sleep(self.request_interval_seconds)
                return rows
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return []  # not published yet; caller can decide coverage policy
                last_error = error
            except (OSError, urllib.error.URLError, zipfile.BadZipFile, UnicodeDecodeError, PremiumIndexValidationError) as error:
                last_error = error
            self.sleep(self.request_interval_seconds * (attempt + 1))
        raise PremiumIndexDownloadError(f"failed to download {url}: {last_error}")

    def download_range(self, start: str | date, end: str | date, output_dir: Path | str, force: bool = False) -> list[PremiumIndexRow]:
        first, last = _as_date(start), _as_date(end)
        if first > last:
            raise ValueError("start must be on or before end")
        rows: list[PremiumIndexRow] = []
        fetched = 0
        missing_dates: list[str] = []
        current = first
        while current <= last:
            day_rows = self.download_day(current, output_dir, force)
            if day_rows:
                fetched += 1
                rows.extend(day_rows)
            else:
                missing_dates.append(current.isoformat())
            current += timedelta(days=1)
        self.last_coverage = PremiumIndexDownloadCoverage(
            requested=(last - first).days + 1,
            fetched=fetched,
            missing_dates=tuple(missing_dates),
        )
        return dedup_premium_index_rows(rows)


def load_premium_index_dir(premium_dir: Path | str, strict: bool = True) -> list[PremiumIndexRow]:
    """Load every cached archive, refusing to silently forward-fill a bad file."""
    rows: list[PremiumIndexRow] = []
    broken: list[str] = []
    for path in sorted(Path(premium_dir).glob("*.zip")):
        try:
            rows.extend(parse_premium_index_csv_text(_premium_csv_text_from_zip(path.read_bytes())))
        except (zipfile.BadZipFile, UnicodeDecodeError, OSError, PremiumIndexValidationError) as error:
            broken.append(f"{path.name}: {error}")
    if broken:
        detail = "; ".join(broken)
        if strict:
            raise PremiumIndexDownloadError(
                f"unreadable premium-index archive(s) in {premium_dir}: {detail}. "
                "Delete them and re-run collection; carrying a stale basis across a gap is not valid."
            )
        print(f"WARNING: skipping unreadable premium-index archive(s): {detail}")
    return dedup_premium_index_rows(rows)


def premium_index_to_minutes(rows: Sequence[PremiumIndexRow], minute_times: Sequence[datetime]) -> dict[datetime, dict[str, float]]:
    """As-of join finalized 1m premium-index closes onto candle open times.

    A 00:00 kline cannot be used at 00:00: it is still forming.  At 00:01 its
    close_time (00:00:59.999) has passed, so its close is the latest known
    premium index.  Earlier minutes receive no value instead of an invented
    zero.  This preserves source-level availability if the source is wired in
    a later pass: absent history stays absent rather than becoming a constant.
    """
    if not rows or not minute_times:
        return {}
    ordered = sorted(dedup_premium_index_rows(rows), key=lambda row: row.close_time)
    out: dict[datetime, dict[str, float]] = {}
    cursor, current = 0, None
    for minute in sorted(minute_times):
        while cursor < len(ordered) and ordered[cursor].close_time <= minute:
            current = ordered[cursor]
            cursor += 1
        if current is not None:
            out[minute] = {"premium_index": float(current.close)}
    return out


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
