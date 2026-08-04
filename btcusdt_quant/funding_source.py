"""Binance USDT-M funding-rate archive: download, parse and align to 1m bars.

Funding is the one input this project has that does NOT come from the price
series. Every other feature is a transform of OHLCV, so a model built on them
can only rearrange the same information -- which is why barrier, direction,
label and horizon variants all failed the same way on the first unseen window.
Funding measures positioning: a persistently positive rate means longs are
paying shorts to stay in, i.e. the crowd is on one side.

Measured on 2020-2026H1, its correlation with the forward return is NEGATIVE in
every window and at every horizon tested -- crowded longs precede weaker
returns. Small (|IC| 0.010-0.049) but sign-stable across 6.5 years, and
strongest exactly where the OHLCV features collapsed.

Two properties of the data that matter more than the IC:

  * The distribution SHIFTS. 2020-2024 funding spans +/-0.30%; 2026 H1 spans
    +/-0.015%, twenty times narrower. A model reading the raw level will place
    2026 bars in the middle of the training distribution no matter how extreme
    they are for their own regime.
  * 43% of 2020-2025 bars sit at exactly 0.0100% (the base rate), so the raw
    series is a spike at the default with information only in the tails.

Mirrors metrics_source.py: same downloader shape, same "load -> features ->
forward-fill onto the 1m clock" contract, so both external sources reach
dataset.build_feature_rows through the identical path.
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
    "FUNDING_BASE_URL",
    "FundingRow",
    "FundingDownloadError",
    "BinanceFundingDownloader",
    "parse_funding_csv_text",
    "dedup_funding_rows",
    "load_funding_dir",
    "funding_features_to_minutes",
]

FUNDING_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT"

# Settlement cadence used only to bound "minutes to next" when the archive has
# no later settlement to point at (i.e. at the very end of the data). The
# SCHEDULE is public and known in advance, so counting down to it is causal --
# what is not knowable at time t is the RATE that settlement will print.
DEFAULT_FUNDING_INTERVAL_MINUTES = 480


class FundingDownloadError(RuntimeError):
    """A funding archive file could not be fetched."""


@dataclass(frozen=True)
class FundingRow:
    funding_time: datetime
    funding_rate: float


def _parse_funding_time(raw: str) -> datetime:
    value = raw.strip()
    if value.isdigit():  # epoch milliseconds, the archive's usual form
        return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_funding_csv_text(csv_text: str) -> list[FundingRow]:
    """Parse a fundingRate CSV, with or without a header line.

    Columns are (calc_time, funding_interval_hours, last_funding_rate). Some
    monthly files carry a header and some do not, so the first line is treated
    as data when its first field parses as a timestamp.
    """
    rows: list[FundingRow] = []
    reader = csv.reader(io.StringIO(csv_text))
    for record in reader:
        if not record or len(record) < 3:
            continue
        try:
            when = _parse_funding_time(record[0])
            rate = float(record[2])
        except (ValueError, TypeError):
            continue  # header line, or a malformed row
        rows.append(FundingRow(funding_time=when, funding_rate=rate))
    return rows


def dedup_funding_rows(rows: Iterable[FundingRow]) -> list[FundingRow]:
    """One row per settlement timestamp, chronologically.

    Monthly files overlap at boundaries when a range is re-downloaded; keeping
    both would double-count a settlement in any windowed statistic.
    """
    by_time: dict[datetime, FundingRow] = {}
    for row in rows:
        by_time[row.funding_time] = row
    return [by_time[key] for key in sorted(by_time)]


def _funding_csv_text_from_zip(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        if not names:
            raise FundingDownloadError("funding archive is empty")
        return archive.read(names[0]).decode("utf-8")


class BinanceFundingDownloader:
    """Fetch monthly fundingRate archives, reusing anything already on disk."""

    def __init__(
        self,
        base_url: str = FUNDING_BASE_URL,
        symbol: str = "BTCUSDT",
        timeout_seconds: int = 30,
        max_retries: int = 5,
        urlopen: Callable[..., object] | None = None,
        sleep: Callable[[float], None] | None = None,
        request_interval_seconds: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.symbol = symbol
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.urlopen = urlopen or urllib.request.urlopen
        self.sleep = sleep or time.sleep
        self.request_interval_seconds = request_interval_seconds

    def _month_url(self, year: int, month: int) -> tuple[str, str]:
        name = f"{self.symbol}-fundingRate-{year:04d}-{month:02d}.zip"
        return f"{self.base_url}/{name}", name

    def download_month(self, year: int, month: int, output_dir: Path, force: bool = False) -> list[FundingRow]:
        url, name = self._month_url(year, month)
        cached = output_dir / name
        if cached.exists() and not force:
            try:
                return parse_funding_csv_text(_funding_csv_text_from_zip(cached.read_bytes()))
            except (zipfile.BadZipFile, FundingDownloadError):
                cached.unlink(missing_ok=True)  # truncated download; refetch
        output_dir.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.urlopen(url, timeout=self.timeout_seconds)  # type: ignore[call-arg]
                payload = response.read()
                cached.write_bytes(payload)
                self.sleep(self.request_interval_seconds)
                return parse_funding_csv_text(_funding_csv_text_from_zip(payload))
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return []  # month not published yet -- not an error
                last_error = error
            except Exception as error:  # network hiccup; retry with backoff
                last_error = error
            self.sleep(self.request_interval_seconds * (attempt + 1))
        raise FundingDownloadError(f"failed to download {url}: {last_error}")

    def download_range(self, start: str | date, end: str | date, output_dir: Path, force: bool = False) -> list[FundingRow]:
        first, last = _as_date(start), _as_date(end)
        rows: list[FundingRow] = []
        year, month = first.year, first.month
        while (year, month) <= (last.year, last.month):
            rows.extend(self.download_month(year, month, Path(output_dir), force=force))
            month += 1
            if month > 12:
                year, month = year + 1, 1
        return dedup_funding_rows(rows)


def load_funding_dir(funding_dir: Path) -> list[FundingRow]:
    rows: list[FundingRow] = []
    for path in sorted(Path(funding_dir).glob("*.zip")):
        try:
            rows.extend(parse_funding_csv_text(_funding_csv_text_from_zip(path.read_bytes())))
        except (zipfile.BadZipFile, FundingDownloadError):
            continue
    return dedup_funding_rows(rows)


def funding_features_to_minutes(
    rows: Sequence[FundingRow],
    minute_times: Sequence[datetime],
) -> dict[datetime, dict[str, float]]:
    """Per-minute funding snapshot, carrying only information available at that minute.

    For a bar at time t:

      current_rate     the last SETTLED rate, i.e. the most recent settlement
                       at or before t. Settlements after t do not exist yet.
      minutes_to_next  minutes until the next scheduled settlement. The
                       schedule is public in advance, so counting down to it is
                       causal; the rate that settlement will print is not.

    ``next_rate`` is deliberately NOT produced. The archive stores realised
    rates, and the next realised rate is future information -- filling it would
    put tomorrow's number in today's feature vector. The feature therefore stays
    at its fallback and is excluded from training by drop_fallback_features,
    which is the honest outcome rather than a fabricated one.

    Bars before the first settlement get nothing: with no settled rate there is
    no causal value to carry, and emitting 0.0 would be indistinguishable from a
    genuine zero rate.
    """
    if not rows or not minute_times:
        return {}
    ordered = dedup_funding_rows(rows)
    times = [row.funding_time for row in ordered]
    rates = [row.funding_rate for row in ordered]

    out: dict[datetime, dict[str, float]] = {}
    cursor = 0
    horizon = timedelta(minutes=DEFAULT_FUNDING_INTERVAL_MINUTES)
    for minute in sorted(minute_times):
        while cursor + 1 < len(times) and times[cursor + 1] <= minute:
            cursor += 1
        if times[cursor] > minute:
            continue  # before the first settlement: nothing is known yet
        following = times[cursor + 1] if cursor + 1 < len(times) else times[cursor] + horizon
        minutes_to_next = max(0.0, (following - minute).total_seconds() / 60.0)
        out[minute] = {
            "current_rate": float(rates[cursor]),
            "minutes_to_next": float(minutes_to_next),
        }
    return out


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
