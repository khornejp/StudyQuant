"""R2-43 causal volatility-only detector runner.

The frozen R2-42 contract is implemented here.  This module intentionally has
no dependency on execution, strategy, or return-accounting artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS"):
    os.environ[_variable] = "4"

import numpy as np
import pandas as pd
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
DESIGN = ROOT / "out/k45_vol_gated_design_r2_42_20261006/REPORT.md"
PROBE = ROOT / "out/run_k45_vol_gated_probe_r2_42.py"
# User stopped the first run (2026-10-06 15:10 KST) to add excursion targets; it stays in
# out/k45_vol_detector_r2_43_20261006 unchanged.
OUT = ROOT / "out/k45_vol_detector_r2_43_exc_20261006"
HISTORY = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
METRICS = ROOT / "artifacts/metrics"
PREMIUM = ROOT / "artifacts/premium_index_2020_2026h1"
FUNDING = ROOT / "artifacts/funding_2020_2026h1"
TEST_FILE = ROOT / "tests/test_k45_vol_detector_r2_43.py"

SEED = 20261006
HORIZONS_MINUTES = (30, 60, 240, 720, 1_440)
HORIZON_NAMES = ("30m", "1h", "4h", "12h", "24h")
TARGETS = tuple(f"{kind}_{horizon}" for kind in ("range", "rv", "exc")
                for horizon in HORIZON_NAMES)
PRICE_CHANNELS = (
    "log_return_bps", "abs_return_bps", "range_bps", "body_bps",
    "upper_wick_bps", "lower_wick_bps", "log_volume", "log_quote_volume",
    "log_trades", "taker_buy_share_centered",
)
FEATURE_SCHEMA = {
    "1m": list(PRICE_CHANNELS),
    "5m": list(PRICE_CHANNELS) + ["global_ls", "global_ls_change", "global_ls_age_minutes",
                                         "global_ls_missing", "premium_mean_bps",
                                         "premium_age_minutes", "premium_missing"],
    "1h": list(PRICE_CHANNELS) + ["premium_mean_bps", "premium_age_minutes",
                                         "premium_missing", "last_funding_rate_bps",
                                         "funding_age_hours", "hours_to_next_funding",
                                         "funding_missing"],
}
SPLITS = {
    "WARMUP": ("2020-01-01", "2022-03-01"),
    "DEV_FRONT": ("2022-03-01", "2024-01-01"),
    "DEV_BACK": ("2024-01-01", "2026-01-01"),
    "HOLD_B": ("2026-01-01", "2026-07-01"),
}
FROZEN_HYPOTHESIS = (
    "causal PatchTST가 다섯 기간의 unsigned range, realized volatility, "
    "최대 이탈폭(결정 시점 가격 기준)을 "
    "naive보다 OOS에서 더 잘 예측한다."
)
DENIED_PATH_WORDS = ("trade", "position", "pnl", "backtest", "c1_x")


@dataclass(frozen=True)
class Config:
    name: str
    lookbacks: tuple[int, int, int]
    patches: tuple[int, int, int]
    strides: tuple[int, int, int]
    width: int
    layers: int
    heads: int
    batch_size: int


CONFIGS = {
    "compact": Config("compact", (360, 288, 336), (60, 24, 24), (30, 12, 12),
                      32, 1, 4, 256),
    "base": Config("base", (720, 576, 720), (60, 24, 48), (30, 12, 24),
                   48, 2, 4, 128),
}
CANDIDATES = tuple(
    {"name": f"{name}_{cadence}d", "config": name, "cadence_days": cadence}
    for name in ("compact", "base") for cadence in (3, 7, 30)
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def guard_path(path: Path | str) -> Path:
    resolved = Path(path).resolve()
    lowered = "/".join(resolved.parts).lower()
    if any(word in lowered for word in DENIED_PATH_WORDS):
        raise PermissionError(f"R2-43 volatility-only path boundary rejected: {resolved}")
    return resolved


def read_text(path: Path) -> str:
    return guard_path(path).read_text(encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path = guard_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path = guard_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.parquet")
    guard_path(temporary)
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def read_parquet(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_parquet(guard_path(path), **kwargs)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with guard_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_record(path: Path, pattern: str = "*.zip") -> dict[str, object]:
    files = sorted(guard_path(path).glob(pattern))
    digest = hashlib.sha256()
    total = 0
    for item in files:
        item_hash = sha256_file(item)
        size = item.stat().st_size
        digest.update(item.name.encode())
        digest.update(item_hash.encode())
        total += size
    return {"path": str(path.relative_to(ROOT)), "files": len(files), "bytes": total,
            "tree_sha256": digest.hexdigest(),
            "first": files[0].name if files else None, "last": files[-1].name if files else None}


def file_record(path: Path) -> dict[str, object]:
    path = guard_path(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def input_records() -> list[dict[str, object]]:
    return [file_record(HISTORY), tree_record(METRICS), tree_record(PREMIUM), tree_record(FUNDING)]


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seed_all(seed: int = SEED) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def aggregate(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    grouped = frame.set_index("open_time").resample(frequency, origin="epoch",
                                                      label="left", closed="left")
    result = grouped.agg(open=("open", "first"), high=("high", "max"),
                         low=("low", "min"), close=("close", "last"),
                         volume=("volume", "sum"), quote_volume=("quote_volume", "sum"),
                         number_of_trades=("number_of_trades", "sum"),
                         taker_buy_base_volume=("taker_buy_base_volume", "sum"),
                         rows=("close", "size"))
    expected = int(pd.Timedelta(frequency) / pd.Timedelta(minutes=1))
    if not result.rows.eq(expected).all():
        raise ValueError(f"incomplete {frequency} bars; missing minutes are never interpolated")
    result = result.drop(columns="rows").reset_index()
    result["decision_time"] = result.open_time + pd.Timedelta(frequency)
    return result


def price_features(bars: pd.DataFrame) -> np.ndarray:
    open_ = bars.open.to_numpy(float)
    high = bars.high.to_numpy(float)
    low = bars.low.to_numpy(float)
    close = bars.close.to_numpy(float)
    previous = np.r_[np.nan, close[:-1]]
    log_return = np.log(close / previous) * 1e4
    body_high, body_low = np.maximum(open_, close), np.minimum(open_, close)
    share = bars.taker_buy_base_volume.to_numpy(float) / np.maximum(
        bars.volume.to_numpy(float), 1e-12)
    return np.column_stack((
        log_return, np.abs(log_return), np.log(high / low) * 1e4,
        np.abs(np.log(close / open_)) * 1e4, np.log(high / body_high) * 1e4,
        np.log(body_low / low) * 1e4, np.log1p(bars.volume.to_numpy(float)),
        np.log1p(bars.quote_volume.to_numpy(float)),
        np.log1p(bars.number_of_trades.to_numpy(float)), 2 * share - 1,
    )).astype(np.float32)


def future_targets(minutes: pd.DataFrame, origins: pd.DatetimeIndex) -> np.ndarray:
    high, low = minutes.high.to_numpy(float), minutes.low.to_numpy(float)
    close = minutes.close.to_numpy(float)
    starts = np.searchsorted(minutes.open_time.array.asi8, origins.asi8)
    returns = np.r_[np.nan, np.diff(np.log(close))]
    prefix = np.r_[0.0, np.cumsum(np.nan_to_num(returns, nan=0.0) ** 2)]
    result = np.full((len(origins), len(TARGETS)), np.nan, np.float32)
    for column, horizon in enumerate(HORIZONS_MINUTES):
        rolling_high = pd.Series(high).rolling(horizon).max().shift(1 - horizon).to_numpy()
        rolling_low = pd.Series(low).rolling(horizon).min().shift(1 - horizon).to_numpy()
        ends = starts + horizon
        valid = (starts > 0) & (ends <= len(minutes))
        result[valid, column] = np.log(
            rolling_high[starts[valid]] / rolling_low[starts[valid]]) * 1e4
        result[valid, len(HORIZONS_MINUTES) + column] = np.sqrt(
            prefix[ends[valid]] - prefix[starts[valid]]) * 1e4
        anchor = close[starts[valid] - 1]
        result[valid, 2 * len(HORIZONS_MINUTES) + column] = np.maximum(
            np.log(rolling_high[starts[valid]] / anchor),
            np.log(anchor / rolling_low[starts[valid]])) * 1e4
    return np.log1p(result)


def past_targets(minutes: pd.DataFrame, origins: pd.DatetimeIndex) -> np.ndarray:
    high, low = minutes.high.to_numpy(float), minutes.low.to_numpy(float)
    close = minutes.close.to_numpy(float)
    starts = np.searchsorted(minutes.open_time.array.asi8, origins.asi8)
    returns = np.r_[np.nan, np.diff(np.log(close))]
    prefix = np.r_[0.0, np.cumsum(np.nan_to_num(returns, nan=0.0) ** 2)]
    result = np.full((len(origins), len(TARGETS)), np.nan, np.float32)
    for column, horizon in enumerate(HORIZONS_MINUTES):
        rolling_high = pd.Series(high).rolling(horizon).max().to_numpy()
        rolling_low = pd.Series(low).rolling(horizon).min().to_numpy()
        valid = starts >= horizon + 1
        ending = starts[valid] - 1
        result[valid, column] = np.log(
            rolling_high[ending] / rolling_low[ending]) * 1e4
        result[valid, len(HORIZONS_MINUTES) + column] = np.sqrt(
            prefix[starts[valid]] - prefix[starts[valid] - horizon]) * 1e4
        anchor = close[starts[valid] - horizon - 1]
        result[valid, 2 * len(HORIZONS_MINUTES) + column] = np.maximum(
            np.log(rolling_high[ending] / anchor), np.log(anchor / rolling_low[ending])) * 1e4
    return result


def check_targets(minutes: pd.DataFrame, origins: pd.DatetimeIndex,
                  targets: np.ndarray) -> None:
    row = len(origins) // 2
    start = int(np.searchsorted(minutes.open_time.array.asi8, origins[row].value))
    for column, horizon in enumerate(HORIZONS_MINUTES):
        part = minutes.iloc[start:start + horizon]
        expected_range = math.log(part.high.max() / part.low.min()) * 1e4
        prior = float(minutes.close.iloc[start - 1])
        returns = np.diff(np.log(np.r_[prior, part.close.to_numpy(float)]))
        assert np.isclose(np.expm1(targets[row, column]), expected_range, rtol=1e-5)
        assert np.isclose(np.expm1(targets[row, 5 + column]),
                          math.sqrt(float(returns @ returns)) * 1e4, rtol=1e-5)
        expected_excursion = max(math.log(part.high.max() / prior),
                                 math.log(prior / part.low.min())) * 1e4
        assert np.isclose(np.expm1(targets[row, 10 + column]), expected_excursion, rtol=1e-5)


def asof_strict(values: np.ndarray, available_times: pd.DatetimeIndex,
                decisions: pd.DatetimeIndex, ttl: pd.Timedelta | None = None
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    positions = np.searchsorted(available_times.asi8, decisions.asi8, side="left") - 1
    valid = positions >= 0
    output = np.zeros(len(decisions), np.float32)
    source_ns = np.full(len(decisions), np.iinfo(np.int64).min, np.int64)
    output[valid] = values[positions[valid]]
    source_ns[valid] = available_times.asi8[positions[valid]]
    age_ns = np.zeros(len(decisions), np.int64)
    age_ns[valid] = decisions.asi8[valid] - source_ns[valid]
    if ttl is not None:
        valid &= age_ns <= ttl.value
    valid &= np.isfinite(output)
    output[~valid] = 0
    age_minutes = np.zeros(len(decisions), np.float32)
    age_minutes[valid] = age_ns[valid] / pd.Timedelta(minutes=1).value
    return output, age_minutes, (~valid).astype(np.float32), positions


def load_market() -> pd.DataFrame:
    columns = ["open_time", "open", "high", "low", "close", "volume", "quote_volume",
               "number_of_trades", "taker_buy_base_volume"]
    frame = read_parquet(HISTORY, columns=columns)
    frame["open_time"] = pd.to_datetime(frame.open_time, utc=True).astype("datetime64[ns, UTC]")
    if not frame.open_time.is_monotonic_increasing:
        raise ValueError("market timestamps are not ordered")
    if not np.all(np.diff(frame.open_time.array.asi8) == pd.Timedelta(minutes=1).value):
        raise ValueError("market has missing minutes; interpolation is forbidden")
    return frame


def _read_zip_csv(path: Path, **kwargs) -> pd.DataFrame:
    path = guard_path(path)
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one CSV in {path}")
        return pd.read_csv(archive.open(names[0]), **kwargs)


def load_metrics() -> pd.DataFrame:
    frames = []
    for path in sorted(METRICS.glob("*.zip")):
        frame = _read_zip_csv(path, usecols=["create_time", "count_long_short_ratio"])
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    result["create_time"] = pd.to_datetime(result.create_time, utc=True).astype("datetime64[ns, UTC]")
    result["global_ls"] = pd.to_numeric(result.count_long_short_ratio, errors="raise")
    invalid_rows = int((~np.isfinite(result.global_ls)).sum())
    result = result.loc[np.isfinite(result.global_ls), ["create_time", "global_ls"]].drop_duplicates(
        "create_time", keep="last").sort_values("create_time").reset_index(drop=True)
    result.attrs["invalid_rows_masked"] = invalid_rows
    return result


def load_premium() -> pd.DataFrame:
    columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
               "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    frames = []
    for path in sorted(PREMIUM.glob("*.zip")):
        raw = _read_zip_csv(path, header=None)
        if str(raw.iloc[0, 0]).lower() == "open_time":
            raw = raw.iloc[1:].reset_index(drop=True)
        raw.columns = columns
        frames.append(raw[["open_time", "close_time", "close"]])
    result = pd.concat(frames, ignore_index=True)
    result["open_time"] = pd.to_datetime(pd.to_numeric(result.open_time), unit="ms", utc=True)
    result["close_time"] = pd.to_datetime(pd.to_numeric(result.close_time), unit="ms", utc=True)
    result["premium"] = pd.to_numeric(result.close, errors="raise")
    return result[["open_time", "close_time", "premium"]].drop_duplicates(
        "open_time", keep="last").sort_values("open_time").reset_index(drop=True)


def load_funding() -> pd.DataFrame:
    frames = []
    for path in sorted(FUNDING.glob("*.zip")):
        frame = _read_zip_csv(path, usecols=["calc_time", "funding_interval_hours",
                                             "last_funding_rate"])
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    result["publish_time"] = pd.to_datetime(pd.to_numeric(result.calc_time), unit="ms", utc=True)
    result["rate"] = pd.to_numeric(result.last_funding_rate, errors="raise")
    result["interval_hours"] = pd.to_numeric(result.funding_interval_hours, errors="raise")
    return result[["publish_time", "rate", "interval_hours"]].drop_duplicates(
        "publish_time", keep="last").sort_values("publish_time").reset_index(drop=True)


def attach_exogenous(bars: list[pd.DataFrame], metrics: pd.DataFrame,
                     premium: pd.DataFrame, funding: pd.DataFrame) -> list[np.ndarray]:
    arrays = [price_features(frame) for frame in bars]
    five, hourly = bars[1], bars[2]

    metric_available = pd.DatetimeIndex(metrics.create_time + pd.Timedelta(minutes=5))
    metric_values = metrics.global_ls.to_numpy(float)
    ls, ls_age, ls_missing, positions = asof_strict(
        metric_values, metric_available, pd.DatetimeIndex(five.decision_time),
        pd.Timedelta(minutes=15))
    previous = np.r_[np.nan, metric_values[:-1]]
    changes = np.zeros(len(five), np.float32)
    valid = (positions >= 1) & (ls_missing == 0)
    changes[valid] = (metric_values[positions[valid]] - previous[positions[valid]]).astype(np.float32)

    premium_index = premium.set_index("open_time").premium
    premium_parts = []
    for frame, frequency in ((five, "5min"), (hourly, "1h")):
        grouped = premium_index.resample(frequency, origin="epoch", label="left", closed="left")
        mean, count, last_time = grouped.mean(), grouped.count(), grouped.apply(
            lambda x: x.index.max() if len(x) else pd.NaT)
        expected = int(pd.Timedelta(frequency) / pd.Timedelta(minutes=1))
        means = frame.open_time.map(mean).to_numpy(float) * 1e4
        counts = frame.open_time.map(count).fillna(0).to_numpy(int)
        last = pd.DatetimeIndex(frame.open_time.map(last_time))
        age = np.zeros(len(frame), np.float32)
        observed = counts > 0
        age[observed] = ((pd.DatetimeIndex(frame.decision_time[observed]).asi8 -
                          last[observed].asi8) / pd.Timedelta(minutes=1).value).astype(np.float32)
        missing = (~observed) | (age > 15)
        means[missing] = 0
        age[missing] = 0
        premium_parts.append((means.astype(np.float32), age, missing.astype(np.float32),
                              int((counts != expected).sum())))

    five_extra = np.column_stack((ls, changes, ls_age, ls_missing,
                                  premium_parts[0][0], premium_parts[0][1], premium_parts[0][2]))

    funding_times = pd.DatetimeIndex(funding.publish_time)
    decisions = pd.DatetimeIndex(hourly.decision_time)
    rate, age_minutes, missing, funding_positions = asof_strict(
        funding.rate.to_numpy(float), funding_times, decisions, None)
    valid_funding = funding_positions >= 0
    next_hours = np.zeros(len(hourly), np.float32)
    if valid_funding.any():
        chosen = funding_positions[valid_funding]
        expiry = funding_times.asi8[chosen] + (
            funding.interval_hours.to_numpy(float)[chosen] * pd.Timedelta(hours=1).value).astype(np.int64)
        next_hours[valid_funding] = np.maximum(
            0, (expiry - decisions.asi8[valid_funding]) / pd.Timedelta(hours=1).value)
        expired = valid_funding.copy()
        expired[valid_funding] = decisions.asi8[valid_funding] > expiry
        missing[expired] = 1
        rate[expired] = 0
        age_minutes[expired] = 0
        next_hours[expired] = 0
    hourly_extra = np.column_stack((premium_parts[1][0], premium_parts[1][1],
                                    premium_parts[1][2], rate * 1e4,
                                    age_minutes / 60, next_hours, missing))
    arrays[1] = np.column_stack((arrays[1], five_extra)).astype(np.float32)
    arrays[2] = np.column_stack((arrays[2], hourly_extra)).astype(np.float32)
    return arrays


def availability_audit() -> dict[str, object]:
    started = time.perf_counter()
    market = load_market()
    metrics = load_metrics()
    premium = load_premium()
    funding = load_funding()
    required_start = pd.Timestamp("2020-01-01", tz="UTC")
    cutoff = pd.Timestamp("2026-07-01", tz="UTC")
    failures: list[str] = []
    if market.open_time.iloc[0] != required_start or market.open_time.iloc[-1] != cutoff - pd.Timedelta(minutes=1):
        failures.append("market coverage does not match frozen cutoff")
    if not metrics.create_time.is_monotonic_increasing or metrics.create_time.duplicated().any():
        failures.append("global LS timestamps are not unique and ordered")
    if not premium.open_time.is_monotonic_increasing or premium.open_time.duplicated().any():
        failures.append("premium timestamps are not unique and ordered")
    if not funding.publish_time.is_monotonic_increasing or funding.publish_time.duplicated().any():
        failures.append("funding timestamps are not unique and ordered")
    if not metrics.create_time.dt.minute.mod(5).eq(0).all():
        failures.append("global LS archive is not on a five-minute grid")
    if not (premium.close_time >= premium.open_time + pd.Timedelta(seconds=59)).all():
        failures.append("premium completion timestamps precede bar completion")
    if not funding.interval_hours.isin((1, 2, 4, 8)).all():
        failures.append("unexpected funding interval")

    decisions = pd.date_range(SPLITS["DEV_FRONT"][0], SPLITS["HOLD_B"][1],
                              freq="15min", inclusive="left", tz="UTC")
    _, _, ls_missing, ls_positions = asof_strict(
        metrics.global_ls.to_numpy(float),
        pd.DatetimeIndex(metrics.create_time + pd.Timedelta(minutes=5)), decisions,
        pd.Timedelta(minutes=15))
    ls_valid = ls_positions >= 0
    if ls_valid.any():
        selected = (metrics.create_time + pd.Timedelta(minutes=5)).array.asi8[ls_positions[ls_valid]]
        if not np.all(selected < decisions.asi8[ls_valid]):
            failures.append("global LS strict +5 minute availability failed")
    funding_positions = np.searchsorted(funding.publish_time.array.asi8,
                                        decisions.asi8, side="left") - 1
    valid = funding_positions >= 0
    if valid.any() and not np.all(
            funding.publish_time.array.asi8[funding_positions[valid]] < decisions.asi8[valid]):
        failures.append("funding publication availability failed")
    premium_grid = pd.Series(1, index=premium.open_time).reindex(
        pd.date_range(required_start, cutoff, freq="1min", inclusive="left", tz="UTC"))
    premium_missing_runs = premium_grid.isna().astype(int).groupby(
        premium_grid.notna().cumsum()).sum()
    result = {
        "status": "PASS" if not failures else "FAIL", "failures": failures,
        "market": {"rows": len(market), "start": str(market.open_time.iloc[0]),
                   "end": str(market.open_time.iloc[-1]), "missing_minutes": 0},
        "global_ls": {"rows": len(metrics), "start": str(metrics.create_time.iloc[0]),
                      "end": str(metrics.create_time.iloc[-1]),
                      "invalid_rows_masked": metrics.attrs.get("invalid_rows_masked", 0),
                      "masked_origins": int(ls_missing.sum()),
                      "rule": "archive create_time+5m < T; TTL 15m"},
        "premium": {"rows": len(premium), "start": str(premium.open_time.iloc[0]),
                    "end": str(premium.open_time.iloc[-1]),
                    "missing_minutes": int(premium_grid.isna().sum()),
                    "max_missing_run_minutes": int(premium_missing_runs.max()),
                    "rule": "completed bars only; TTL 15m; missing is masked, never interpolated"},
        "funding": {"rows": len(funding), "start": str(funding.publish_time.iloc[0]),
                    "end": str(funding.publish_time.iloc[-1]),
                    "rule": "actual calc/publish time < T; valid until next scheduled settlement"},
        "elapsed_seconds": time.perf_counter() - started,
    }
    return result


class PatchBranch(nn.Module):
    def __init__(self, channels: int, lookback: int, patch: int, stride: int,
                 width: int, layers: int, heads: int):
        super().__init__()
        self.lookback, self.patch, self.stride = lookback, patch, stride
        count = 1 + (lookback - patch) // stride
        self.input = nn.Linear(patch, width)
        position = torch.arange(count, dtype=torch.float32)[:, None]
        frequency = torch.exp(torch.arange(0, width, 2) * (-math.log(10_000.0) / width))
        encoding = torch.zeros(count, width)
        encoding[:, 0::2] = torch.sin(position * frequency)
        encoding[:, 1::2] = torch.cos(position * frequency)
        self.register_buffer("position", encoding[None])
        layer = nn.TransformerEncoderLayer(width, heads, width * 2, 0.1, "gelu",
                                           batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, nn.LayerNorm(width),
                                             enable_nested_tensor=False)
        self.channels, self.width = channels, width

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        patches = values.transpose(1, 2).unfold(-1, self.patch, self.stride)
        tokens = self.input(patches).flatten(0, 1) + self.position
        encoded = self.encoder(tokens).mean(1)
        return encoded.reshape(len(values), self.channels * self.width)


class MultiResolutionPatchTST(nn.Module):
    def __init__(self, config: Config, channels: tuple[int, int, int]):
        super().__init__()
        self.branches = nn.ModuleList([
            PatchBranch(channel, lookback, patch, stride, config.width,
                        config.layers, config.heads)
            for channel, lookback, patch, stride in zip(
                channels, config.lookbacks, config.patches, config.strides)
        ])
        joined = sum(channels) * config.width
        self.head = nn.Sequential(nn.Linear(joined, config.width), nn.GELU(),
                                  nn.Linear(config.width, len(TARGETS)), nn.Softplus())

    def forward(self, values: tuple[torch.Tensor, ...]) -> torch.Tensor:
        return self.head(torch.cat([branch(value) for branch, value in zip(
            self.branches, values)], 1))


def endpoint_indices(bars: list[pd.DataFrame], origins: pd.DatetimeIndex) -> list[np.ndarray]:
    endpoints = []
    for frame in bars:
        positions = np.searchsorted(frame.decision_time.array.asi8,
                                    origins.asi8, side="right") - 1
        if (positions < 0).any():
            raise ValueError("origin precedes completed input")
        endpoints.append(positions)
    return endpoints


def batch(arrays: list[np.ndarray], endpoints: list[np.ndarray], rows: np.ndarray,
          lookbacks: tuple[int, int, int], means: list[np.ndarray],
          stds: list[np.ndarray], device: torch.device) -> tuple[torch.Tensor, ...]:
    tensors = []
    for values, end, lookback, mean, std in zip(arrays, endpoints, lookbacks, means, stds):
        indices = end[rows, None] + np.arange(-lookback + 1, 1)
        selected = (values[indices] - mean) / std
        selected = np.nan_to_num(selected, nan=0.0, posinf=10.0, neginf=-10.0)
        selected = np.clip(selected, -10, 10).astype(np.float32)
        tensors.append(torch.from_numpy(selected).to(device, non_blocking=True))
    return tuple(tensors)


def purge_indices(origins: pd.DatetimeIndex, retrain_time: pd.Timestamp
                  ) -> tuple[np.ndarray, np.ndarray]:
    label_end = origins + pd.Timedelta(hours=24)
    cutoff = retrain_time - pd.Timedelta(hours=24)
    pool_start = cutoff - pd.Timedelta(days=730)
    split = cutoff - pd.Timedelta(days=60)
    train = np.flatnonzero((label_end >= pool_start) & (label_end < split))
    stop = np.flatnonzero((label_end >= split) & (label_end < cutoff))
    return train, stop


def fold_schedule(segment: str, cadence_days: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start, end = (pd.Timestamp(value, tz="UTC") for value in SPLITS[segment])
    prediction_end = end - pd.Timedelta(hours=24)
    result = []
    retrain = start
    while retrain < prediction_end:
        result.append((retrain, min(retrain + pd.Timedelta(days=cadence_days), prediction_end)))
        retrain += pd.Timedelta(days=cadence_days)
    return result


@dataclass
class Dataset:
    minutes: pd.DataFrame
    bars: list[pd.DataFrame]
    arrays: list[np.ndarray]
    origins: pd.DatetimeIndex
    targets_log: np.ndarray
    naive: np.ndarray


def load_dataset() -> Dataset:
    minutes = load_market()
    bars = [aggregate(minutes, frequency) for frequency in ("1min", "5min", "1h")]
    arrays = attach_exogenous(bars, load_metrics(), load_premium(), load_funding())
    origins = pd.DatetimeIndex(aggregate(minutes, "15min").decision_time)
    targets = future_targets(minutes, origins)
    check_targets(minutes, origins, targets)
    return Dataset(minutes, bars, arrays, origins, targets, past_targets(minutes, origins))


def _predict(model: nn.Module, dataset: Dataset, rows: np.ndarray,
             endpoints: list[np.ndarray], config: Config, means: list[np.ndarray],
             stds: list[np.ndarray], device: torch.device) -> np.ndarray:
    parts = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(rows), config.batch_size * 2):
            local = np.arange(start, min(start + config.batch_size * 2, len(rows)))
            x = batch(dataset.arrays, endpoints, local, config.lookbacks, means, stds, device)
            parts.append(model(x).cpu().numpy())
    return np.concatenate(parts) if parts else np.empty((0, len(TARGETS)), np.float32)


def fit_fold(dataset: Dataset, config: Config, retrain_time: pd.Timestamp,
             prediction_end: pd.Timestamp, device: torch.device) -> tuple[dict, pd.DataFrame]:
    train, stop = purge_indices(dataset.origins, retrain_time)
    predict = np.flatnonzero((dataset.origins >= retrain_time) &
                             (dataset.origins < prediction_end) &
                             np.isfinite(dataset.targets_log).all(1))
    if min(len(train), len(stop), len(predict)) == 0:
        raise ValueError("empty frozen fold")
    sets = [dataset.origins[index] for index in (train, stop, predict)]
    endpoint_sets = [endpoint_indices(dataset.bars, origins) for origins in sets]
    for endpoints in endpoint_sets:
        for end, lookback in zip(endpoints, config.lookbacks):
            if end.min() < lookback - 1:
                raise ValueError("insufficient causal lookback")

    scaler_end = dataset.origins[train[-1]]
    means, stds = [], []
    for frame, values, lookback in zip(dataset.bars, dataset.arrays, config.lookbacks):
        allowed = ((frame.decision_time >= dataset.origins[train[0]] -
                    pd.Timedelta(minutes=lookback * int(pd.Timedelta(
                        {0: "1min", 1: "5min", 2: "1h"}[len(means)]) / pd.Timedelta(minutes=1)))) &
                   (frame.decision_time <= scaler_end))
        mean = np.nanmean(values[allowed], axis=0)
        std = np.nanstd(values[allowed], axis=0)
        mean[~np.isfinite(mean)] = 0
        std[(~np.isfinite(std)) | (std == 0)] = 1
        means.append(mean.astype(np.float32)); stds.append(std.astype(np.float32))

    seed_all()
    model = MultiResolutionPatchTST(config, tuple(array.shape[1] for array in dataset.arrays)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-5)
    rng = np.random.default_rng(SEED)
    best, best_state, stale, history = float("inf"), None, 0, []
    started = time.perf_counter()
    for epoch in range(6):
        model.train()
        losses = []
        order = rng.permutation(len(train))
        for start in range(0, len(train), config.batch_size):
            chosen = order[start:start + config.batch_size]
            x = batch(dataset.arrays, endpoint_sets[0], chosen, config.lookbacks,
                      means, stds, device)
            y = torch.from_numpy(dataset.targets_log[train[chosen]]).to(device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(x)
            loss = nn.functional.smooth_l1_loss(prediction, y)
            if not torch.isfinite(loss):
                raise ValueError("non-finite loss")
            loss.backward(); optimizer.step()
            losses.append(float(loss.detach()))
        stop_prediction = _predict(model, dataset, stop, endpoint_sets[1], config,
                                   means, stds, device)
        stop_loss = float(np.abs(stop_prediction - dataset.targets_log[stop]).mean())
        history.append({"epoch": epoch + 1, "train_loss": float(np.mean(losses)),
                        "stop_log_mae": stop_loss})
        if stop_loss < best - 1e-6:
            best, stale = stop_loss, 0
            best_state = {name: value.detach().cpu().clone()
                          for name, value in model.state_dict().items()}
        else:
            stale += 1
            if stale >= 2:
                break
    model.load_state_dict(best_state)
    train_prediction = np.expm1(_predict(model, dataset, train, endpoint_sets[0], config,
                                         means, stds, device))
    prediction = np.expm1(_predict(model, dataset, predict, endpoint_sets[2], config,
                                   means, stds, device))
    actual = np.expm1(dataset.targets_log[predict])
    train_actual = np.expm1(dataset.targets_log[train])
    actual_quantiles = np.quantile(train_actual, (1 / 3, 2 / 3, .8), axis=0)
    prediction_quantiles = np.quantile(train_prediction, (1 / 3, 2 / 3, .8), axis=0)
    frame = pd.DataFrame({"timestamp": dataset.origins[predict],
                          "retrain_time": retrain_time})
    for column, name in enumerate(TARGETS):
        frame[f"prediction_{name}"] = prediction[:, column]
        frame[f"actual_{name}"] = actual[:, column]
        frame[f"naive_{name}"] = dataset.naive[predict, column]
        frame[f"actual_class_{name}"] = np.digitize(actual[:, column], actual_quantiles[:2, column])
        frame[f"prediction_class_{name}"] = np.digitize(
            prediction[:, column], prediction_quantiles[:2, column])
        frame[f"actual_high_{name}"] = actual[:, column] > actual_quantiles[2, column]
        frame[f"prediction_high_{name}"] = prediction[:, column] > prediction_quantiles[2, column]
    checkpoint = {
        "model_state": best_state, "config": asdict(config), "seed": SEED,
        "retrain_time": str(retrain_time), "prediction_end": str(prediction_end),
        "means": means, "stds": stds, "actual_quantiles": actual_quantiles,
        "prediction_quantiles": prediction_quantiles, "feature_schema": FEATURE_SCHEMA,
        "train_rows": len(train), "stop_rows": len(stop), "prediction_rows": len(predict),
        "history": history, "best_stop_log_mae": best,
        "elapsed_seconds": time.perf_counter() - started,
    }
    return checkpoint, frame


def rank_ic(prediction: np.ndarray, actual: np.ndarray) -> float:
    return float(pd.Series(prediction).rank().corr(pd.Series(actual).rank()))


def balanced_accuracy(actual: np.ndarray, prediction: np.ndarray) -> float:
    recalls = [np.mean(prediction[actual == label] == label) for label in range(3)
               if np.any(actual == label)]
    return float(np.mean(recalls)) if recalls else math.nan


def block_scores(frame: pd.DataFrame) -> pd.DataFrame:
    blocks = frame.timestamp.dt.floor("7D")
    rows = []
    for block, part in frame.groupby(blocks, sort=True):
        values = [rank_ic(part[f"prediction_{name}"], part[f"actual_{name}"])
                  for name in TARGETS]
        if np.isfinite(values).all():
            rows.append({"block": block, **{name: value for name, value in zip(TARGETS, values)},
                         "mean": float(np.mean(values))})
    return pd.DataFrame(rows)


def bootstrap_summary(blocks: pd.DataFrame, repetitions: int = 2_000) -> tuple[float, list[float]]:
    values = blocks[["mean", *TARGETS]].to_numpy(float)
    if len(values) < 2:
        return math.nan, [math.nan] * len(TARGETS)
    rng = np.random.default_rng(SEED)
    samples = values[rng.integers(0, len(values), size=(repetitions, len(values)))].mean(1)
    lower = float(np.quantile(samples[:, 0], .025))
    p_values = [float((1 + np.count_nonzero(samples[:, i + 1] <= 0)) /
                      (repetitions + 1)) for i in range(len(TARGETS))]
    return lower, p_values


def holm_adjust(p_values: list[float]) -> list[float]:
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), float)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def predictive_metrics(frame: pd.DataFrame) -> dict[str, object]:
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    months = frame.timestamp.dt.to_period("M")
    head_ic = []
    for name in TARGETS:
        monthly = [rank_ic(part[f"prediction_{name}"], part[f"actual_{name}"])
                   for _, part in frame.groupby(months, sort=True)]
        head_ic.append(float(np.nanmean(monthly)))
    mean_ic = float(np.mean(head_ic))
    model_mae = [float(np.abs(frame[f"prediction_{name}"] - frame[f"actual_{name}"]).mean())
                 for name in TARGETS]
    naive_mae = [float(np.abs(frame[f"naive_{name}"] - frame[f"actual_{name}"]).mean())
                 for name in TARGETS]
    average_model_mae, average_naive_mae = float(np.mean(model_mae)), float(np.mean(naive_mae))
    precision = []
    accuracy = []
    for name in TARGETS:
        predicted = frame[f"prediction_high_{name}"].to_numpy(bool)
        actual = frame[f"actual_high_{name}"].to_numpy(bool)
        precision.append(float(actual[predicted].mean()) if predicted.any() else 0.0)
        accuracy.append(balanced_accuracy(frame[f"actual_class_{name}"].to_numpy(int),
                                          frame[f"prediction_class_{name}"].to_numpy(int)))
    blocks = block_scores(frame)
    lower, p_values = bootstrap_summary(blocks)
    result = {
        "rows": len(frame), "start": str(frame.timestamp.min()), "end": str(frame.timestamp.max()),
        "monthly_mean_rank_ic": mean_ic,
        "rank_ic": dict(zip(TARGETS, head_ic)), "block_bootstrap_95_lower": lower,
        "block_bootstrap_p_one_sided": dict(zip(TARGETS, p_values)),
        "holm_adjusted_p": dict(zip(TARGETS, holm_adjust(p_values))),
        "mae_model": dict(zip(TARGETS, model_mae)), "mae_naive": dict(zip(TARGETS, naive_mae)),
        "average_mae_model": average_model_mae, "average_mae_naive": average_naive_mae,
        "average_mae_skill": ((average_naive_mae - average_model_mae) / average_naive_mae),
        "q80_precision": dict(zip(TARGETS, precision)), "macro_q80_precision": float(np.mean(precision)),
        "balanced_accuracy": dict(zip(TARGETS, accuracy)),
        "macro_balanced_accuracy": float(np.mean(accuracy)),
        "seven_day_blocks": len(blocks),
    }
    result["criteria"] = pass_criteria(result)
    result["passed"] = all(result["criteria"].values())
    return result


def pass_criteria(metrics: dict[str, object]) -> dict[str, bool]:
    rank = metrics["rank_ic"]
    return {
        "mean_rank_ic_gte_0_10": metrics["monthly_mean_rank_ic"] >= .10,
        "block_bootstrap_lower_gt_0": metrics["block_bootstrap_95_lower"] > 0,
        "core_rv_rank_ic_gt_0": all(rank[name] > 0 for name in ("rv_30m", "rv_1h", "rv_4h")),
        "average_mae_below_naive": metrics["average_mae_model"] < metrics["average_mae_naive"],
        "average_mae_skill_gt_0": metrics["average_mae_skill"] > 0,
        "macro_q80_precision_gt_0_20": metrics["macro_q80_precision"] > .20,
        "macro_balanced_accuracy_gt_1_3": metrics["macro_balanced_accuracy"] > 1 / 3,
    }


def choose_candidate(scores: dict[str, float]) -> str:
    best = max(scores.values())
    tied = [candidate for candidate in CANDIDATES
            if scores[candidate["name"]] >= best - .01]
    tied.sort(key=lambda item: (item["cadence_days"] != 7,
                                item["config"] != "compact", item["name"]))
    return tied[0]["name"]


def run_focused_tests() -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(TEST_FILE),
         "--basetemp", str(OUT / ".pytest_tmp")], cwd=ROOT,
        text=True, capture_output=True, check=False)
    summary = (completed.stdout + completed.stderr).strip().splitlines()
    result = {"status": "PASS" if completed.returncode == 0 else "FAIL",
              "returncode": completed.returncode,
              "summary": summary[-1] if summary else "no output",
              "elapsed_seconds": time.perf_counter() - started, "timestamp_utc": utc_now()}
    if completed.returncode:
        raise RuntimeError("focused tests failed: " + result["summary"])
    return result


def frozen_payload(audit: dict, tests: dict, inputs: list[dict]) -> dict[str, object]:
    return {
        "experiment": "R2-43-exc", "source": "local Binance USD-M BTCUSDT public archives",
        "timestamp_utc": utc_now(), "data_cutoff": "2026-06-30T23:59:00Z",
        "frozen_hypothesis_1": FROZEN_HYPOTHESIS, "seed": SEED,
        "cpu_thread_limit": 4, "gpu_limit": 1, "origin_frequency": "15min",
        "targets": list(TARGETS), "splits": SPLITS, "candidates": list(CANDIDATES),
        "training": {"optimizer": "AdamW", "learning_rate": 1e-3, "weight_decay": 1e-5,
                     "dropout": .1, "loss": "SmoothL1", "max_epochs": 6,
                     "patience": 2, "train_days": 670, "stop_days": 60,
                     "purge": "label_end < retrain_time-24h"},
        "selection": {"score": "equal-weight mean of 15 monthly Spearman rank ICs",
                      "tie_range": .01,
                      "tie_order": ["7-day cadence", "compact", "candidate name lexical"]},
        "criteria": {"mean_rank_ic": ">=0.10", "block_bootstrap_95_lower": ">0",
                     "core_rv_rank_ic": ">0 each", "average_mae_skill": ">0",
                     "macro_q80_precision": ">0.20",
                     "macro_balanced_accuracy": ">1/3"},
        "feature_schema": FEATURE_SCHEMA, "availability_audit": audit,
        "focused_tests": tests, "inputs": inputs,
        "sources": [file_record(path) for path in (DESIGN, PROBE, SCRIPT)],
    }


def report_text(manifest: dict, progress: dict | None = None,
                appendix: str = "") -> str:
    frozen = manifest["frozen"]
    audit = frozen["availability_audit"]
    tests = frozen["focused_tests"]
    lines = [
        "# R2-43-exc 1단계 변동성 탐지기 본 실행 (이탈폭 추가 재시작)", "",
        "## 사전 점검", "",
        f"- availability audit: **{audit['status']}**",
        f"- 시장 1분봉: {audit['market']['rows']:,}행, 누락 {audit['market']['missing_minutes']}분",
        f"- global LS: {audit['global_ls']['rows']:,}행, 규칙 `{audit['global_ls']['rule']}`",
        f"- premium: {audit['premium']['rows']:,}행, 누락 {audit['premium']['missing_minutes']:,}분, "
        f"최대 연속 누락 {audit['premium']['max_missing_run_minutes']}분",
        f"- funding: {audit['funding']['rows']:,}행, 규칙 `{audit['funding']['rule']}`",
        f"- 집중 테스트: **{tests['status']}**, `{tests['summary']}`",
        "- 다운로드·주문·인증·실행 시스템 변경: 0", "",
        "## 동결", "",
        f"- freeze manifest hash: `{manifest['freeze_manifest_hash']}`",
        f"- 입력 cutoff: `{frozen['data_cutoff']}`",
        f"- 가설 1: {frozen['frozen_hypothesis_1']}",
        "- 후보: `compact/base × 3/7/30일`, 정확히 6개",
        "- OOS 결과: validate 완료 후 manifest에 기록", "",
        "## 실행", "",
    ]
    if progress and progress.get("started_utc"):
        lines += [
            f"- 학습 시작 UTC: `{progress['started_utc']}`",
            f"- PID: `{progress.get('pid')}`",
            f"- 명령: `{progress.get('command')}`",
            f"- 완료 fold: `{progress.get('completed_folds')}/{progress.get('total_folds')}`",
            f"- 경과: `{progress.get('elapsed_seconds', 0):.1f}초`",
            f"- 예상 남은 시간: `{progress.get('eta_seconds')}`초",
            f"- 예상 완료 UTC: `{progress.get('estimated_completion_utc')}`",
            f"- 마지막 오류: `{progress.get('last_error')}`", "",
            "처음 fold 시간:", "",
        ]
        for item in progress.get("first_fold_times", []):
            lines.append(f"- `{item['candidate']} {item['segment']} {item['fold']}`: "
                         f"{item['seconds']:.1f}초")
        lines += ["", "재시작:", "",
                  "```powershell",
                  r"venv_btcusdt\Scripts\python.exe out\run_k45_vol_detector_r2_43.py train",
                  "```", ""]
    else:
        lines += ["학습 미시작. freeze만 완료됨.", ""]
    if appendix:
        lines += ["## 결과 부록", "", appendix.strip(), ""]
    return "\n".join(lines)


def freeze() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = availability_audit()
    if audit["status"] != "PASS":
        write_json(OUT / "availability_audit.json", audit)
        write_text(OUT / "REPORT.md", "# R2-43 사전 점검 실패\n\n" +
                   "availability audit 실패. 학습을 실행하지 않았다.\n\n" +
                   "```json\n" + json.dumps(audit, ensure_ascii=False, indent=2) + "\n```\n")
        raise RuntimeError("availability audit failed; freeze and training stopped")
    tests = run_focused_tests()
    inputs = input_records()
    frozen = frozen_payload(audit, tests, inputs)
    manifest = {"status": "FROZEN", "frozen": frozen,
                "freeze_manifest_hash": canonical_hash(frozen),
                "out_of_sample_result": None}
    if (OUT / "manifest.json").exists():
        current = read_json(OUT / "manifest.json")
        if current.get("freeze_manifest_hash") != manifest["freeze_manifest_hash"]:
            raise RuntimeError("existing manifest differs; result-dependent refreeze forbidden")
        manifest = current
    else:
        write_json(OUT / "manifest.json", manifest)
    write_json(OUT / "availability_audit.json", audit)
    write_text(OUT / "REPORT.md", report_text(manifest))
    print(json.dumps({"status": "FROZEN", "freeze_manifest_hash": manifest["freeze_manifest_hash"]},
                     ensure_ascii=False))


def verify_manifest() -> dict:
    manifest = read_json(OUT / "manifest.json")
    if canonical_hash(manifest["frozen"]) != manifest["freeze_manifest_hash"]:
        raise RuntimeError("frozen manifest payload hash mismatch")
    expected_inputs = manifest["frozen"]["inputs"]
    if input_records() != expected_inputs:
        raise RuntimeError("input hash mismatch; resume forbidden")
    expected_sources = {item["path"]: item["sha256"] for item in manifest["frozen"]["sources"]}
    for path in (DESIGN, PROBE, SCRIPT):
        if sha256_file(path) != expected_sources[str(path.relative_to(ROOT))]:
            raise RuntimeError(f"source hash mismatch: {path}")
    return manifest


def atomic_torch_save(path: Path, value: object) -> None:
    path = guard_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    guard_path(temporary)
    torch.save(value, temporary)
    temporary.replace(path)


def fold_paths(candidate: str, segment: str, fold: int) -> tuple[Path, Path, Path]:
    directory = OUT / "folds" / candidate / segment
    stem = f"fold_{fold:04d}"
    return directory / f"{stem}.pt", directory / f"{stem}_predictions.parquet", directory / f"{stem}.json"


def valid_completed_fold(candidate: str, segment: str, fold: int,
                         manifest_hash: str) -> bool:
    checkpoint, predictions, metadata = fold_paths(candidate, segment, fold)
    if not all(path.exists() for path in (checkpoint, predictions, metadata)):
        return False
    record = read_json(metadata)
    return (record.get("freeze_manifest_hash") == manifest_hash and
            record.get("checkpoint_sha256") == sha256_file(checkpoint) and
            record.get("predictions_sha256") == sha256_file(predictions))


def initial_progress(manifest_hash: str) -> dict[str, object]:
    total = sum(len(fold_schedule("DEV_FRONT", item["cadence_days"])) for item in CANDIDATES)
    return {"status": "TRAINING", "freeze_manifest_hash": manifest_hash,
            "started_utc": utc_now(), "pid": os.getpid(),
            "command": "venv_btcusdt\\Scripts\\python.exe out\\run_k45_vol_detector_r2_43.py train",
            "candidate_folds": {item["name"]: {"completed": 0,
                                                   "total": len(fold_schedule("DEV_FRONT", item["cadence_days"]))}
                                for item in CANDIDATES},
            "completed_folds": 0, "total_folds": total, "elapsed_seconds": 0.0,
            "eta_seconds": None, "estimated_completion_utc": None,
            "first_fold_times": [], "last_error": None}


def update_progress(progress: dict, started: float, fold_seconds: float | None = None,
                    candidate: str | None = None, segment: str | None = None,
                    fold: int | None = None) -> None:
    progress["elapsed_seconds"] = time.perf_counter() - started
    if fold_seconds is not None and len(progress["first_fold_times"]) < 6:
        progress["first_fold_times"].append(
            {"candidate": candidate, "segment": segment, "fold": fold, "seconds": fold_seconds})
    completed = int(progress["completed_folds"])
    if completed:
        remaining = int(progress["total_folds"]) - completed
        eta = progress["elapsed_seconds"] / completed * remaining
        progress["eta_seconds"] = round(eta, 1)
        progress["estimated_completion_utc"] = datetime.fromtimestamp(
            time.time() + eta, timezone.utc).isoformat()
    write_json(OUT / "progress.json", progress)
    manifest = read_json(OUT / "manifest.json")
    appendix = read_text(OUT / "result_appendix.md") if (OUT / "result_appendix.md").exists() else ""
    write_text(OUT / "REPORT.md", report_text(manifest, progress, appendix))


def run_candidate_segment(dataset: Dataset, candidate: dict, segment: str,
                          device: torch.device, manifest_hash: str,
                          progress: dict, started: float, count_primary: bool = True) -> None:
    name = candidate["name"]
    schedule = fold_schedule(segment, candidate["cadence_days"])
    if not count_primary:
        progress["total_folds"] += sum(
            not valid_completed_fold(name, segment, fold, manifest_hash)
            for fold in range(len(schedule)))
    for fold, (retrain_time, prediction_end) in enumerate(schedule):
        if valid_completed_fold(name, segment, fold, manifest_hash):
            continue
        fold_started = time.perf_counter()
        checkpoint, prediction = fit_fold(dataset, CONFIGS[candidate["config"]],
                                          retrain_time, prediction_end, device)
        checkpoint["freeze_manifest_hash"] = manifest_hash
        checkpoint_path, prediction_path, metadata_path = fold_paths(name, segment, fold)
        atomic_torch_save(checkpoint_path, checkpoint)
        prediction.insert(0, "candidate", name)
        prediction.insert(1, "segment", segment)
        prediction.insert(2, "fold", fold)
        write_parquet(prediction_path, prediction)
        metadata = {"freeze_manifest_hash": manifest_hash,
                    "checkpoint_sha256": sha256_file(checkpoint_path),
                    "predictions_sha256": sha256_file(prediction_path),
                    "retrain_time": str(retrain_time), "prediction_end": str(prediction_end),
                    "elapsed_seconds": time.perf_counter() - fold_started,
                    "completed_utc": utc_now()}
        write_json(metadata_path, metadata)
        if count_primary:
            progress["candidate_folds"][name]["completed"] += 1
        progress["completed_folds"] += 1
        update_progress(progress, started, metadata["elapsed_seconds"], name, segment, fold)


def collect_predictions(candidate: str, segment: str) -> pd.DataFrame:
    paths = sorted((OUT / "folds" / candidate / segment).glob("*_predictions.parquet"))
    if not paths:
        raise RuntimeError(f"no predictions for {candidate} {segment}")
    return pd.concat([read_parquet(path) for path in paths], ignore_index=True)


def select() -> dict:
    manifest = verify_manifest()
    metrics = {}
    block_tables = {}
    for candidate in CANDIDATES:
        name = candidate["name"]
        frame = collect_predictions(name, "DEV_FRONT")
        metrics[name] = predictive_metrics(frame)
        block_tables[name] = block_scores(frame).set_index("block")["mean"]
    scores = {name: value["monthly_mean_rank_ic"] for name, value in metrics.items()}
    selected = choose_candidate(scores)
    aligned = pd.concat(block_tables, axis=1, keys=block_tables).dropna()
    simultaneous = {}
    if len(aligned) >= 2:
        rng = np.random.default_rng(SEED)
        values = aligned.to_numpy(float)
        draws = values[rng.integers(0, len(values), size=(2_000, len(values)))].mean(1)
        centers = values.mean(0)
        width = float(np.quantile(np.max(np.abs(draws - centers), axis=1), .95))
        simultaneous = {name: [float(center - width), float(center + width)]
                        for name, center in zip(aligned.columns, centers)}
    result = {"selected": selected, "scores": scores, "metrics": metrics,
              "simultaneous_95_ci": simultaneous, "tie_rule_applied": True,
              "timestamp_utc": utc_now(), "freeze_manifest_hash": manifest["freeze_manifest_hash"]}
    write_json(OUT / "selection.json", result)
    write_json(OUT / "decision.json", {"status": "SELECTED_PENDING_VALIDATION",
                                        "selected": selected, "DEV_FRONT": metrics[selected]})
    return result


def _candidate(name: str) -> dict:
    return next(item for item in CANDIDATES if item["name"] == name)


def _appendix(selection: dict, dev_back: dict | None = None,
              hold_b: dict | None = None, decision: str = "") -> str:
    lines = [f"- 선택 후보: `{selection['selected']}`",
             f"- DEV_FRONT 점수: `{selection['scores'][selection['selected']]:.6f}`"]
    if dev_back:
        lines += [f"- DEV_BACK 통과: `{dev_back['passed']}`",
                  f"- DEV_BACK mean rank IC: `{dev_back['monthly_mean_rank_ic']:.6f}`"]
    if hold_b:
        lines += [f"- HOLD_B 통과: `{hold_b['passed']}`",
                  f"- HOLD_B mean rank IC: `{hold_b['monthly_mean_rank_ic']:.6f}`"]
    if decision:
        lines.append(f"- 최종 판정: **{decision}**")
    return "\n".join(lines) + "\n"


def seal_outputs() -> None:
    for path in OUT.rglob("*"):
        if path.is_file() and path.name not in ("train.log",):
            path.chmod(0o444)


def validate(dataset: Dataset | None = None, device: torch.device | None = None,
             progress: dict | None = None, started: float | None = None) -> dict:
    manifest = verify_manifest()
    selection = read_json(OUT / "selection.json")
    selected = selection["selected"]
    candidate = _candidate(selected)
    own_dataset = dataset is None
    if dataset is None:
        dataset = load_dataset()
    if device is None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required")
        device = torch.device("cuda:0")
    if progress is None:
        progress = read_json(OUT / "progress.json") if (OUT / "progress.json").exists() else initial_progress(
            manifest["freeze_manifest_hash"])
    if started is None:
        started = time.perf_counter() - float(progress.get("elapsed_seconds", 0))

    run_candidate_segment(dataset, candidate, "DEV_BACK", device,
                          manifest["freeze_manifest_hash"], progress, started, False)
    dev_back = predictive_metrics(collect_predictions(selected, "DEV_BACK"))
    if not dev_back["passed"]:
        decision = {"status": "NO_DETECTOR", "selected": selected,
                    "DEV_FRONT": selection["metrics"][selected], "DEV_BACK": dev_back,
                    "HOLD_B": None, "reason": "DEV_BACK fixed predictive criteria failed"}
        manifest["status"] = "COMPLETE_NO_DETECTOR"
        manifest["out_of_sample_result"] = {"DEV_BACK": dev_back, "HOLD_B": None}
        write_json(OUT / "manifest.json", manifest)
        write_json(OUT / "decision.json", decision)
        write_text(OUT / "result_appendix.md", _appendix(selection, dev_back, None, "탐지기 없음"))
        progress["status"] = "COMPLETE_NO_DETECTOR"
        update_progress(progress, started)
        seal_outputs()
        return decision

    run_candidate_segment(dataset, candidate, "HOLD_B", device,
                          manifest["freeze_manifest_hash"], progress, started, False)
    hold_b = predictive_metrics(collect_predictions(selected, "HOLD_B"))
    status = "DETECTOR_ACCEPTED" if hold_b["passed"] else "NO_DETECTOR"
    decision = {"status": status, "selected": selected,
                "DEV_FRONT": selection["metrics"][selected], "DEV_BACK": dev_back,
                "HOLD_B": hold_b,
                "reason": "fixed predictive criteria applied once without retuning"}
    manifest["status"] = "COMPLETE_" + status
    manifest["out_of_sample_result"] = {"DEV_BACK": dev_back, "HOLD_B": hold_b}
    write_json(OUT / "manifest.json", manifest)
    write_json(OUT / "decision.json", decision)
    write_text(OUT / "result_appendix.md", _appendix(
        selection, dev_back, hold_b, "탐지기 채택" if hold_b["passed"] else "탐지기 없음"))
    progress["status"] = manifest["status"]
    update_progress(progress, started)
    seal_outputs()
    if own_dataset:
        del dataset
    return decision


def train() -> None:
    manifest = verify_manifest()
    if not torch.cuda.is_available():
        raise RuntimeError("R2-43 training requires one CUDA GPU")
    torch.set_num_threads(4)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    device = torch.device("cuda:0")
    started = time.perf_counter()
    progress = initial_progress(manifest["freeze_manifest_hash"])
    for candidate in CANDIDATES:
        for fold in range(len(fold_schedule("DEV_FRONT", candidate["cadence_days"]))):
            if valid_completed_fold(candidate["name"], "DEV_FRONT", fold,
                                    manifest["freeze_manifest_hash"]):
                progress["candidate_folds"][candidate["name"]]["completed"] += 1
                progress["completed_folds"] += 1
    update_progress(progress, started)
    try:
        dataset = load_dataset()
        for candidate in CANDIDATES:
            run_candidate_segment(dataset, candidate, "DEV_FRONT", device,
                                  manifest["freeze_manifest_hash"], progress, started)
        progress["status"] = "SELECTING"
        update_progress(progress, started)
        select()
        progress["status"] = "VALIDATING"
        update_progress(progress, started)
        validate(dataset, device, progress, started)
    except Exception as error:
        progress["status"] = "FAILED"
        progress["last_error"] = f"{type(error).__name__}: {error}"
        update_progress(progress, started)
        raise


def status() -> None:
    path = OUT / "progress.json"
    if not path.exists():
        print(json.dumps({"status": "NOT_STARTED"}, ensure_ascii=False, indent=2))
        return
    print(json.dumps(read_json(path), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "train", "select", "validate", "status"))
    args = parser.parse_args()
    {"freeze": freeze, "train": train, "select": select,
     "validate": validate, "status": status}[args.command]()


if __name__ == "__main__":
    main()
