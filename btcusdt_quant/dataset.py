from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sin
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

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


FEATURE_FORMULAS: tuple[dict[str, object], ...] = (
    {"feature_name": "return_1", "formula": "close_t / close_t-1 - 1", "lookback": 2, "min_samples": 2, "warmup_rule": "strict"},
    {"feature_name": "return_3", "formula": "close_t / close_t-3 - 1", "lookback": 4, "min_samples": 4, "warmup_rule": "strict"},
    {"feature_name": "close_sma_5_ratio", "formula": "close_t / SMA(close,5) - 1", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
    {"feature_name": "close_sma_10_ratio", "formula": "close_t / SMA(close,10) - 1", "lookback": 10, "min_samples": 10, "warmup_rule": "strict"},
    {"feature_name": "volume_sma_5_ratio", "formula": "volume_t / max(SMA(volume,5), 1e-12) - 1", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
    {"feature_name": "high_low_range", "formula": "(high_t - low_t) / close_t", "lookback": 1, "min_samples": 1, "warmup_rule": "strict"},
    {"feature_name": "gap_ratio_20", "formula": "rolling repaired candle ratio over last 20 canonical rows", "lookback": 20, "min_samples": 1, "warmup_rule": "state"},
    {"feature_name": "max_gap_run_120", "formula": "maximum contiguous repaired candle run over last 120 canonical rows", "lookback": 120, "min_samples": 1, "warmup_rule": "state"},
)

FEATURE_NAMES: tuple[str, ...] = tuple(str(row["feature_name"]) for row in FEATURE_FORMULAS)


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
    target_return: float
    gap_flag: int
    repaired: bool


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


def load_csv_candles(path: Path) -> list[data.Candle]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"open_time", "open", "high", "low", "close", "volume"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        candles: list[data.Candle] = []
        for row in reader:
            candles.append(
                data.Candle(
                    open_time=parse_open_time(row["open_time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    quote_volume=float(row.get("quote_volume") or 0.0),
                    number_of_trades=int(float(row.get("number_of_trades") or 0)),
                    taker_buy_base_volume=float(row.get("taker_buy_base_volume") or 0.0),
                    taker_buy_quote_volume=float(row.get("taker_buy_quote_volume") or 0.0),
                )
            )
    return candles


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


def build_dataset(input_path: Path | None = None, horizon: int = 3, label_threshold: float = 0.0002) -> DatasetBuild:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if input_path is None:
        raw = expanded_fixture()
        source = "offline_expanded_fixture"
    else:
        raw = load_csv_candles(input_path)
        source = input_path.as_posix()
    canonical = data.CanonicalTimelineBuilder().build(raw)
    gap_report = summarize_gaps(len(raw), canonical)
    feature_rows = build_feature_rows(canonical)
    labeled_rows = attach_labels(feature_rows, canonical, horizon, label_threshold)
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
    for index, candle in enumerate(candles):
        warmup_invalid = index < 10
        values = {
            "return_1": _return(closes, index, 1),
            "return_3": _return(closes, index, 3),
            "close_sma_5_ratio": _ratio_to_mean(closes, index, 5),
            "close_sma_10_ratio": _ratio_to_mean(closes, index, 10),
            "volume_sma_5_ratio": _ratio_to_mean(volumes, index, 5),
            "high_low_range": (candle.high - candle.low) / candle.close if candle.close else 0.0,
            "gap_ratio_20": candle.gap_ratio_20,
            "max_gap_run_120": float(candle.max_gap_run_120),
        }
        rows.append(FeatureRow(index, candle.open_time, values, candle.gap_flag, candle.repaired, warmup_invalid))
    return rows


def attach_labels(feature_rows: Sequence[FeatureRow], candles: Sequence[data.Candle], horizon: int, label_threshold: float) -> list[LabeledRow]:
    labeled: list[LabeledRow] = []
    for row in feature_rows:
        future_index = row.index + horizon
        if row.warmup_invalid or future_index >= len(candles):
            continue
        close = candles[row.index].close
        if close == 0.0:
            continue
        target_return = (candles[future_index].close - close) / close
        labeled.append(
            LabeledRow(
                index=row.index,
                open_time=row.open_time,
                features=dict(row.features),
                label=1 if target_return > label_threshold else 0,
                target_return=target_return,
                gap_flag=row.gap_flag,
                repaired=row.repaired,
            )
        )
    return labeled


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


def labeled_row_dict(row: LabeledRow, feature_names: Sequence[str]) -> dict[str, object]:
    output: dict[str, object] = {
        "index": row.index,
        "open_time": row.open_time.isoformat(),
        "label": row.label,
        "target_return": row.target_return,
        "gap_flag": row.gap_flag,
        "repaired": row.repaired,
    }
    for name in feature_names:
        output[name] = row.features[name]
    return output


def rows_from_mapping(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]
