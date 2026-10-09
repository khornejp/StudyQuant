"""R2-54 four-table futures metrics: public REST / archive normalization and archive backfill.

Frozen timestamp rules (out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json, data_plan):
global/top/OI REST timestamp = period end (create_time = ts - 5m); taker REST timestamp = period start
(create_time = ts). Archive create_time = period start. logical_available_at: archive = create_time + 5m;
live REST = max(period end, received_at). Public data only; no API key.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from btcusdt_quant import metrics_source
from .store import PaperStore, utc_text

SYMBOL = "BTCUSDT"
PERIOD = pd.Timedelta(minutes=5)
PROBE_INTERVAL = pd.Timedelta(minutes=15)       # re-probe cadence for endpoints that failed closed
MAX_PAGES = 20                                   # 20 x 500 x 5m > 30-day REST history
_LS = {"long_short_ratio": "longShortRatio", "long_account": "longAccount", "short_account": "shortAccount"}
# endpoint -> (table, REST timestamp minus create_time, {column: REST field})
REST_SPECS: dict[str, tuple[str, pd.Timedelta, dict[str, str]]] = {
    "/futures/data/globalLongShortAccountRatio": ("futures_global_ls_5m", PERIOD, _LS),
    "/futures/data/topLongShortAccountRatio": ("futures_top_ls_5m", PERIOD, _LS),
    "/futures/data/openInterestHist": ("futures_oi_5m", PERIOD, {
        "sum_open_interest": "sumOpenInterest", "sum_open_interest_value": "sumOpenInterestValue"}),
    "/futures/data/takerlongshortRatio": ("futures_taker_lsr_5m", pd.Timedelta(0), {
        "buy_sell_ratio": "buySellRatio", "buy_volume": "buyVol", "sell_volume": "sellVol"}),
}
TABLES = tuple(spec[0] for spec in REST_SPECS.values())
# archive metrics CSV field per column (absent columns stay NULL = missing)
ARCHIVE_FIELDS = {
    "futures_global_ls_5m": {"long_short_ratio": "count_long_short_ratio"},
    "futures_top_ls_5m": {"long_short_ratio": "count_toptrader_long_short_ratio"},
    "futures_oi_5m": {"sum_open_interest": "sum_open_interest", "sum_open_interest_value": "sum_open_interest_value"},
    "futures_taker_lsr_5m": {"buy_sell_ratio": "sum_taker_long_short_vol_ratio"},
}
_NULL_COLUMNS = {"futures_global_ls_5m": ("long_account", "short_account"),
                 "futures_top_ls_5m": ("long_account", "short_account"),
                 "futures_oi_5m": (), "futures_taker_lsr_5m": ("buy_volume", "sell_volume")}


class SchemaDrift(ValueError):
    """REST payload no longer has the frozen shape; the endpoint fails closed."""


def _number(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise SchemaDrift(f"non-numeric value {value!r}") from error
    return number if math.isfinite(number) else None


def normalize_rest(endpoint: str, payload: object, received: object) -> tuple[str, list[dict[str, object]]]:
    """Finalized rows only (period end <= received); any shape change raises SchemaDrift for the whole page."""
    table, shift, fields = REST_SPECS[endpoint]
    received = pd.Timestamp(received)
    if not isinstance(payload, list):
        raise SchemaDrift(f"{endpoint}: payload is {type(payload).__name__}")
    rows = []
    for item in payload:
        if (not isinstance(item, Mapping) or "timestamp" not in item or not set(fields.values()) <= set(item)
                or item.get("symbol", SYMBOL) != SYMBOL):
            raise SchemaDrift(f"{endpoint}: unexpected row {item!r}"[:200])
        try:
            stamp = pd.to_datetime(int(item["timestamp"]), unit="ms", utc=True)
        except (TypeError, ValueError, OverflowError, pd.errors.OutOfBoundsDatetime) as error:
            raise SchemaDrift(f"{endpoint}: bad timestamp {item['timestamp']!r}") from error
        create = stamp - shift
        if create != create.floor("5min"):
            raise SchemaDrift(f"{endpoint}: off-grid timestamp {stamp}")
        end = create + PERIOD
        if end > received:
            continue
        rows.append({"symbol": SYMBOL, "create_time": utc_text(create), "source_timestamp": utc_text(stamp),
                     **{column: _number(item[field]) for column, field in fields.items()},
                     "logical_available_at": utc_text(max(end, received)), "received_at": utc_text(received),
                     "source": "rest"})
    return table, rows


def normalize_archive(rows: Iterable[metrics_source.MetricsRow],
                      received: object) -> dict[str, list[dict[str, object]]]:
    received_text = utc_text(pd.Timestamp(received))
    out: dict[str, list[dict[str, object]]] = {table: [] for table in TABLES}
    for row in rows:
        create = pd.Timestamp(row.create_time)
        for table, fields in ARCHIVE_FIELDS.items():
            values = {column: row.values.get(field) for column, field in fields.items()}
            if all(value is None for value in values.values()):
                continue
            out[table].append({"symbol": SYMBOL, "create_time": utc_text(create),
                               "source_timestamp": utc_text(create), **values,
                               **{column: None for column in _NULL_COLUMNS[table]},
                               "logical_available_at": utc_text(create + PERIOD),
                               "received_at": received_text, "source": "archive"})
    return out


def write_rows(store: PaperStore, table: str, rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts = {"inserted": 0, "same": 0, "revised": 0}
    with store.transaction() as connection:
        for row in rows:
            counts[store.put_versioned(table, row, connection)] += 1
    return counts


def backfill_metrics(store: PaperStore, start: object, end: object, search_dirs: Sequence[str | Path],
                     download_dir: str | Path, downloader: metrics_source.BinanceMetricsDownloader | None = None,
                     received: object | None = None) -> dict[str, object]:
    """Daily metrics zips for [start, end] (inclusive days): local zips first, only missing days downloaded
    (metrics_source.download_range), normalized into the four tables with source='archive'."""
    downloader = downloader or metrics_source.BinanceMetricsDownloader()
    received = pd.Timestamp(received or pd.Timestamp.now(tz="UTC"))
    first, last = pd.Timestamp(start).date(), pd.Timestamp(end).date()       # end day inclusive
    dirs = [Path(path) for path in search_dirs]
    rows: list[metrics_source.MetricsRow] = []
    files: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    raw_rows = 0
    day = first
    while day <= last:
        name = f"{downloader.symbol}-metrics-{day.isoformat()}.zip"
        folder = next((path for path in dirs if (path / name).exists()), Path(download_dir))
        local = (folder / name).exists()
        day_rows = downloader.download_range(day, day, folder)
        if downloader.last_coverage.fetched:
            payload = (folder / name).read_bytes()
            raw = metrics_source.parse_metrics_csv_text(metrics_source._metrics_csv_text_from_zip(payload))
            raw_rows += len(raw)
            rows.extend(raw)
            files[name] = {"path": str(folder / name), "sha256": hashlib.sha256(payload).hexdigest(),
                           "bytes": len(payload), "rows": len(raw), "local": local,
                           "deduped_rows": len(day_rows)}
        else:
            missing.append(day.isoformat())
        day += timedelta(days=1)
    lo, hi = pd.Timestamp(first, tz="UTC"), pd.Timestamp(last, tz="UTC") + pd.Timedelta(days=1)
    deduped = [row for row in metrics_source.dedup_metrics_rows(rows) if lo <= pd.Timestamp(row.create_time) < hi]
    in_range_raw = sum(lo <= pd.Timestamp(row.create_time) < hi for row in rows)
    tables = {table: write_rows(store, table, table_rows)
              for table, table_rows in normalize_archive(deduped, received).items()}
    coverage = {"requested_days": (last - first).days + 1, "fetched_days": len(files), "missing_days": missing,
                "raw_rows": raw_rows, "duplicates_dropped": in_range_raw - len(deduped),
                "duplicate_rule": "last occurrence per create_time (metrics_source.dedup_metrics_rows)",
                "files": files, "tables": tables, "received_at": utc_text(received),
                "range": [str(first), str(last)]}
    store.set_meta("futures_metrics_backfill", json.dumps(coverage))
    return coverage


def backfill_funding(engine, start: object, end: object, search_dirs: Sequence[str | Path],
                     received: object | None = None) -> dict[str, object]:
    """Monthly fundingRate archive zips (local only; calc_time, funding_interval_hours, last_funding_rate)."""
    received = pd.Timestamp(received or pd.Timestamp.now(tz="UTC"))
    lo = pd.Timestamp(pd.Timestamp(start).date(), tz="UTC")
    hi = pd.Timestamp(pd.Timestamp(end).date(), tz="UTC") + pd.Timedelta(days=1)      # end day inclusive
    months = pd.period_range(lo.tz_localize(None), (hi - pd.Timedelta(days=1)).tz_localize(None), freq="M")
    files, missing, stored = {}, [], 0
    for month in months:
        name = f"BTCUSDT-fundingRate-{month}.zip"
        path = next((Path(d) / name for d in search_dirs if (Path(d) / name).exists()), None)
        if path is None:
            missing.append(str(month))
            continue
        payload = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            frame = pd.read_csv(archive.open(archive.namelist()[0]))
        files[name] = {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "rows": len(frame)}
        for row in frame.itertuples(index=False):
            stamp = pd.to_datetime(int(row.calc_time), unit="ms", utc=True)
            if lo <= stamp < hi:
                hours = pd.to_numeric(row.funding_interval_hours, errors="coerce")
                engine.store_funding(stamp, float(row.last_funding_rate), source="archive", received_at=received,
                                     interval_hours=None if pd.isna(hours) else float(hours))
                stored += 1
    coverage = {"requested_months": [str(m) for m in months], "missing_months": missing, "files": files,
                "events": stored, "received_at": utc_text(received)}
    engine.store.set_meta("funding_backfill", json.dumps(coverage))
    return coverage


__all__ = ["ARCHIVE_FIELDS", "PROBE_INTERVAL", "REST_SPECS", "SchemaDrift", "TABLES", "backfill_funding",
           "backfill_metrics", "normalize_archive", "normalize_rest", "write_rows"]
