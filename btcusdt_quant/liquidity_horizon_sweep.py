"""Zero-fit raw-arm markout-horizon sweep on frozen target-equivalence shards."""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from btcusdt_quant.target_equivalence import RssGuard, json_ready, save_json, sha256


PLAN = Path("ZERO_FIT_LIQUIDITY_HORIZON_SWEEP_2026-09-28.md")
PLAN_SHA256 = "b3e6419859b10344dc5918e2efc4041ce93ddb2f801234cac90af203e7e840bd"
BASE = Path("out/zero_fit_target_equivalence_20260925_r1")
OUTPUT = Path("out/zero_fit_liquidity_horizon_sweep_20260928")
HORIZONS = (5, 10, 30, 60)
OFFSETS = (1.0, 2.0, 5.0, 10.0)
MAX_AGE_MS = 1_000
MIN_CELL_N = 500
STRONGLY_NEGATIVE = -0.8
RSS_LIMIT = 3 * 1024**3
CONTROL = {
    1.0: (-1.0950, .288, .572, 2.0158),
    2.0: (-.8117, .157, .565, 3.9872),
    5.0: (-.3245, .034, .343, 9.9824),
    10.0: (-.0857, .006, .128, 20.0524),
}


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    frame.to_parquet(partial, index=False, compression="zstd")
    if pq.ParquetFile(partial).metadata.num_rows != len(frame):
        raise ValueError(f"Parquet footer row mismatch: {partial}")
    os.replace(partial, path)


def _record(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256(path)}


class FrozenInputs:
    def __init__(self, base: Path):
        self.base = base
        self.records: dict[str, dict] = {}
        manifest_path = base / "manifest.json"
        self.base_manifest_sha256 = sha256(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "COMPLETE" or manifest.get("new_model_fits") != 0:
            raise ValueError("base R1 run is not a completed zero-fit artifact")
        self.base_outputs = {row["path"]: row for row in manifest["outputs"]}

    def _accept(self, path: Path, expected: dict, metadata: Path | None = None) -> None:
        relative = path.relative_to(self.base).as_posix()
        if not path.is_file() or path.stat().st_size != expected["bytes"]:
            raise ValueError(f"frozen input size mismatch: {path}")
        if sha256(path) != expected["sha256"]:
            raise ValueError(f"frozen input hash mismatch: {path}")
        self.records[relative] = {"path": relative, "bytes": expected["bytes"],
                                  "sha256": expected["sha256"]}
        if metadata is not None:
            meta_relative = metadata.relative_to(self.base).as_posix()
            self.records[meta_relative] = _record(metadata, self.base)

    def day_frame(self, day: str, stem: str, columns: list[str]) -> pd.DataFrame:
        directory = self.base / "shards" / f"date={day}"
        metadata_path = directory / "shard.json"
        if not (directory / "_SUCCESS").is_file() or not metadata_path.is_file():
            raise ValueError(f"incomplete frozen shard: {day}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        parts = []
        for row in metadata["files"]:
            if row["path"].startswith(stem + "-"):
                path = directory / row["path"]
                manifest_row = self.base_outputs.get(path.relative_to(self.base).as_posix())
                if manifest_row != {"path": path.relative_to(self.base).as_posix(),
                                    "bytes": row["bytes"], "sha256": row["sha256"]}:
                    raise ValueError(f"base manifest/shard metadata mismatch: {path}")
                self._accept(path, row, metadata_path)
                parts.append(pd.read_parquet(path, columns=columns))
        if not parts:
            raise ValueError(f"missing frozen {stem} shard: {day}")
        return pd.concat(parts, ignore_index=True)

    def trades(self, start_ms: int, stop_ms: int) -> pd.DataFrame:
        hours = pd.date_range(pd.to_datetime(start_ms, unit="ms", utc=True).floor("h"),
                              pd.to_datetime(stop_ms, unit="ms", utc=True).floor("h"),
                              freq="h", tz="UTC")
        parts = []
        for hour in hours:
            directory = (self.base / "staging" / "aggtrades" /
                         f"date={hour:%Y-%m-%d}" / f"hour={hour:%H}")
            metadata_path = directory / "block.json"
            if not (directory / "_SUCCESS").is_file() or not metadata_path.is_file():
                raise ValueError(f"missing frozen trade block: {directory}")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for row in metadata["files"]:
                path = directory / row["path"]
                self._accept(path, row, metadata_path)
                parts.append(pd.read_parquet(
                    path, columns=["transact_time", "price"]))
        frame = pd.concat(parts, ignore_index=True)
        frame = frame[(frame.transact_time >= start_ms) & (frame.transact_time <= stop_ms)]
        return frame.sort_values("transact_time", kind="mergesort", ignore_index=True)


def _epoch_ms(values: pd.Series) -> np.ndarray:
    return values.to_numpy(dtype="datetime64[ms]").astype(np.int64)


def _asof_prices(times: np.ndarray, prices: np.ndarray, targets: np.ndarray,
                 before: bool) -> tuple[np.ndarray, np.ndarray]:
    indices = np.searchsorted(times, targets, side="left") - int(before)
    in_bounds = (indices >= 0) & (indices < len(times))
    safe = np.clip(indices, 0, max(len(times) - 1, 0))
    delays = np.full(len(targets), MAX_AGE_MS + 1, dtype=np.int64)
    if len(times):
        delays[in_bounds] = ((targets[in_bounds] - times[safe[in_bounds]]) if before else
                             (times[safe[in_bounds]] - targets[in_bounds]))
    valid = in_bounds & (delays >= 0) & (delays <= MAX_AGE_MS)
    values = np.full(len(targets), np.nan)
    if len(times):
        values[valid] = prices[safe[valid]]
    return values, valid


def causal_features(origins: pd.DataFrame) -> pd.DataFrame:
    origins = origins.sort_values("origin", ignore_index=True)
    stamp = _epoch_ms(origins.origin)
    reference = origins.raw_reference.to_numpy(float)
    consecutive = np.r_[False, np.diff(stamp) == 60_000]
    move = np.full(len(origins), np.nan)
    good = consecutive & np.isfinite(reference) & np.r_[False, np.isfinite(reference[:-1])]
    move[good] = 10_000.0 * np.log(reference[good] / reference[np.flatnonzero(good) - 1])
    score = pd.Series(np.abs(move)).rolling(15, min_periods=15).mean().to_numpy()
    trailing = np.full(len(origins), np.nan)
    if len(origins) > 15:
        good15 = ((stamp[15:] - stamp[:-15] == 900_000)
                  & np.isfinite(reference[15:]) & np.isfinite(reference[:-15]))
        positions = np.flatnonzero(good15) + 15
        trailing[positions] = 10_000.0 * np.log(
            reference[positions] / reference[positions - 15])
    valid = np.isfinite(score) & np.isfinite(trailing)
    decile = np.zeros(len(origins), dtype=np.int8)
    decile[valid] = np.asarray(pd.qcut(score[valid], 10, labels=False), dtype=np.int8) + 1
    direction = np.full(len(origins), "", dtype=object)
    direction[valid & (trailing < 0)] = "down"
    direction[valid & (trailing == 0)] = "flat"
    direction[valid & (trailing > 0)] = "up"
    return pd.DataFrame({"origin": origins.origin, "raw_reference": reference,
                         "volatility_score_bps": score, "vol_decile": decile,
                         "trailing_move_bps": trailing, "direction": direction})


def _markouts(fill_ms: np.ndarray, fills: np.ndarray, quotes: np.ndarray, side: str,
              horizon: int, times: np.ndarray, prices: np.ndarray):
    targets = fill_ms + horizon * 1_000
    endpoints, endpoint_valid = _asof_prices(times, prices, targets, before=False)
    endpoint_valid &= fills
    valid = (~fills) | endpoint_valid
    values = np.zeros(len(fills))
    sign = 1.0 if side == "long" else -1.0
    values[endpoint_valid] = sign * 10_000.0 * np.log(
        endpoints[endpoint_valid] / quotes[endpoint_valid])
    return values, valid, endpoint_valid


def _aggregate(frame: pd.DataFrame, keys: list[str], scope: str) -> pd.DataFrame:
    rows = []
    for key, part in frame.groupby(keys, sort=True, observed=True):
        values = key if isinstance(key, tuple) else (key,)
        both = part.both.to_numpy(bool)
        one = part.one.to_numpy(bool)
        row = {column: value for column, value in zip(keys, values)}
        row.update({"scope": scope, "n": len(part), "both_n": int(both.sum()),
                    "one_n": int(one.sum()), "side_fills": int(part.side_fills.sum()),
                    "y_sum": float(part.y.sum()), "y_both_sum": float(part.y[both].sum()),
                    "y_one_sum": float(part.y[one].sum()),
                    "fade_sum": float(part.fade_bps.sum()) if "fade_bps" in part else 0.0})
        rows.append(row)
    return pd.DataFrame(rows)


def _day_cells(outcomes: pd.DataFrame, features: pd.DataFrame,
               trades: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    columns = ["origin", "offset_bps", "raw_fill", "raw_fill_ms", "raw_quote",
               "raw_valid", "raw_markout_bps"]
    sides = {}
    for side in ("long", "short"):
        part = outcomes.loc[outcomes.side == side, columns].copy()
        if part.duplicated(["origin", "offset_bps"]).any():
            raise ValueError(f"duplicate frozen raw rows: {side}")
        sides[side] = part.rename(columns={column: f"{side}_{column}"
                                           for column in columns[2:]})
    pairs = sides["long"].merge(sides["short"], on=["origin", "offset_bps"],
                                  how="inner", validate="one_to_one")
    pairs = pairs.merge(features, on="origin", how="left", validate="many_to_one")
    times = trades.transact_time.to_numpy(np.int64, copy=False)
    prices = trades.price.to_numpy(float, copy=False)
    origin_ms = _epoch_ms(pairs.origin)
    raw_reference = pairs.raw_reference.to_numpy(float)
    audit = {"compared": 0, "mask_mismatch": 0, "max_abs_diff_bps": 0.0}
    aggregates = []
    for horizon in HORIZONS:
        side_values, side_valid, evaluated_fills = {}, {}, {}
        for side in ("long", "short"):
            fills = pairs[f"{side}_raw_fill"].to_numpy(bool)
            values, valid, endpoint_valid = _markouts(
                pairs[f"{side}_raw_fill_ms"].to_numpy(np.int64), fills,
                pairs[f"{side}_raw_quote"].to_numpy(float), side, horizon, times, prices)
            side_values[side], side_valid[side] = values, valid
            evaluated_fills[side] = endpoint_valid
            if horizon == 60:
                frozen_valid = pairs[f"{side}_raw_valid"].to_numpy(bool)
                audit["mask_mismatch"] += int(np.sum(fills & (endpoint_valid != frozen_valid)))
                compare = fills & endpoint_valid & frozen_valid
                frozen = pairs[f"{side}_raw_markout_bps"].to_numpy(float)
                audit["compared"] += int(compare.sum())
                if compare.any():
                    audit["max_abs_diff_bps"] = max(
                        audit["max_abs_diff_bps"],
                        float(np.max(np.abs(values[compare] - frozen[compare]))))
        long_fill = evaluated_fills["long"]
        short_fill = evaluated_fills["short"]
        side_fills = long_fill.astype(np.int8) + short_fill.astype(np.int8)
        endpoint, fade_valid = _asof_prices(
            times, prices, origin_ms + horizon * 1_000, before=False)
        fade_signal = np.select([pairs.direction == "down", pairs.direction == "up"],
                                [1.0, -1.0], default=0.0)
        fade = np.zeros(len(pairs))
        fade_ok = fade_valid & np.isfinite(raw_reference)
        fade[fade_ok] = fade_signal[fade_ok] * 10_000.0 * np.log(
            endpoint[fade_ok] / raw_reference[fade_ok])
        frame = pd.DataFrame({
            "horizon_s": horizon, "offset_bps": pairs.offset_bps,
            "vol_decile": pairs.vol_decile, "direction": pairs.direction,
            "side_fills": side_fills, "both": side_fills == 2,
            "one": side_fills == 1, "y": side_values["long"] + side_values["short"],
            "fade_bps": fade,
        })
        quote_valid = (np.isfinite(pairs.long_raw_quote.to_numpy(float))
                       & np.isfinite(pairs.short_raw_quote.to_numpy(float))
                       & (side_valid["long"] | side_valid["short"]))
        aggregates.append(_aggregate(frame[quote_valid], ["horizon_s", "offset_bps"],
                                     "overall"))
        primary = quote_valid & (pairs.vol_decile > 0)
        aggregates.append(_aggregate(frame[primary],
                                     ["horizon_s", "offset_bps", "vol_decile"],
                                     "primary"))
        conditional = primary & fade_ok
        aggregates.append(_aggregate(
            frame[conditional], ["horizon_s", "offset_bps", "vol_decile", "direction"],
            "direction"))
    return pd.concat(aggregates, ignore_index=True), audit


def _metrics(row: pd.Series) -> dict:
    n, both_n, one_n = int(row.n), int(row.both_n), int(row.one_n)
    y_both = row.y_both_sum / both_n if both_n else math.nan
    y_one = row.y_one_sum / one_n if one_n else math.nan
    realised = both_n / one_n if one_n else math.nan
    required = -y_one / y_both if y_both > 0 and y_one < 0 else math.nan
    return json_ready({"n": n, "y_both": y_both, "y_one": y_one,
                       "p_both": both_n / n, "p_one": one_n / n,
                       "mean_y": row.y_sum / n, "required_double_to_one": required,
                       "realised_double_to_one": realised,
                       "trade_rate": (both_n + one_n) / n,
                       "fill_rate": row.side_fills / (2 * n)})


def _combine(parts: list[Path]) -> pd.DataFrame:
    frame = pd.concat([pd.read_parquet(path) for path in parts], ignore_index=True)
    keys = ["scope", "horizon_s", "offset_bps", "vol_decile", "direction"]
    for column in keys:
        if column not in frame:
            frame[column] = "" if column == "direction" else 0
    sums = ["n", "both_n", "one_n", "side_fills", "y_sum", "y_both_sum",
            "y_one_sum", "fade_sum"]
    return frame.groupby(keys, sort=True, observed=True, dropna=False)[sums].sum().reset_index()


def _binary_fade_correlation(counts: dict[str, int], selected: str) -> float:
    signals = {"down": 1.0, "flat": 0.0, "up": -1.0}
    total = sum(counts.values())
    if not total:
        return math.nan
    mean_x = counts.get(selected, 0) / total
    mean_z = sum(counts.get(key, 0) * value for key, value in signals.items()) / total
    mean_xz = counts.get(selected, 0) * signals[selected] / total
    var_x = mean_x - mean_x**2
    mean_z2 = sum(counts.get(key, 0) * value**2 for key, value in signals.items()) / total
    var_z = mean_z2 - mean_z**2
    return ((mean_xz - mean_x * mean_z) / math.sqrt(var_x * var_z)
            if var_x > 0 and var_z > 0 else math.nan)


def build_reports(combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame,
                                                           pd.DataFrame, dict]:
    report_frames = {}
    for scope in ("overall", "primary"):
        rows = []
        for _, row in combined[combined.scope == scope].iterrows():
            keys = {"horizon_s": int(row.horizon_s), "offset_bps": float(row.offset_bps)}
            if scope == "primary":
                keys["vol_decile"] = int(row.vol_decile)
            rows.append({**keys, **_metrics(row)})
        report_frames[scope] = pd.DataFrame(rows)

    direction_rows = []
    directions = combined[combined.scope == "direction"]
    group_keys = ["horizon_s", "offset_bps", "vol_decile"]
    for keys, group in directions.groupby(group_keys, sort=True, observed=True):
        counts = {str(row.direction): int(row.n) for _, row in group.iterrows()}
        pooled_y = float(group.y_sum.sum() / group.n.sum())
        for _, row in group.iterrows():
            metrics = _metrics(row)
            direction = str(row.direction)
            direction_rows.append({
                "horizon_s": int(keys[0]), "offset_bps": float(keys[1]),
                "vol_decile": int(keys[2]), "direction": direction, **metrics,
                "fade_mean_bps": float(row.fade_sum / row.n),
                "quote_fade_correlation": json_ready(
                    _binary_fade_correlation(counts, direction)),
                "direction_removed_mean_y": pooled_y,
                "positive_disappears_when_direction_removed": bool(
                    metrics["mean_y"] > 0 and pooled_y <= 0),
            })
    direction_frame = pd.DataFrame(direction_rows)

    correlations, positive = [], []
    primary = report_frames["primary"]
    for horizon, part in primary.groupby("horizon_s", sort=True):
        rho_trade = part.trade_rate.corr(part.mean_y, method="spearman")
        rho_fill = part.fill_rate.corr(part.mean_y, method="spearman")
        candidates = part[(part.n >= MIN_CELL_N) & (part.fill_rate > .2) & (part.mean_y > 0)]
        correlations.append({"horizon_s": int(horizon),
                             "spearman_trade_rate_y": float(rho_trade),
                             "spearman_fill_rate_y": float(rho_fill),
                             "strongly_negative": bool(rho_trade <= STRONGLY_NEGATIVE),
                             "positive_liquid_cells": len(candidates)})
        positive.extend(candidates.to_dict("records"))
    correlation_frame = pd.DataFrame(correlations)
    first_positive = min((row["horizon_s"] for row in positive), default=None)
    fixed = [row for row in correlations
             if row["positive_liquid_cells"] and not row["strongly_negative"]]
    first_fixed = min((row["horizon_s"] for row in fixed), default=None)
    results = json_ready({
        "status": "HORIZON_FIX" if first_fixed is not None else "HORIZON_NOT_FIX",
        "horizons_s": list(HORIZONS), "offsets_bps": list(OFFSETS),
        "cell_min_n": MIN_CELL_N, "strong_negative_threshold": STRONGLY_NEGATIVE,
        "first_positive_liquid_horizon_s": first_positive,
        "first_horizon_fix_s": first_fixed,
        "correlations": correlations, "positive_liquid_cells": positive,
        "fade_disguise": {
            "direction_positive_cells": int((direction_frame.mean_y > 0).sum()),
            "positives_disappearing_when_direction_removed": int(
                direction_frame.positive_disappears_when_direction_removed.sum()),
        },
        "out_of_sample_status": "not independent; confirmatory diagnostic on frozen discovery shards",
        "new_model_fits": 0, "new_orders": 0,
    })
    return report_frames["overall"], primary, direction_frame, correlation_frame, results


def _check_control(overall: pd.DataFrame, audit: dict) -> None:
    if audit["mask_mismatch"] or audit["max_abs_diff_bps"] > 1e-9:
        raise ValueError(f"60s frozen-row control failed: {audit}")
    control = overall[overall.horizon_s == 60].set_index("offset_bps")
    for offset, expected in CONTROL.items():
        row = control.loc[offset]
        actual = (round(row.mean_y, 4), round(row.p_both, 3), round(row.p_one, 3),
                  round(row.y_both, 4))
        if actual != expected:
            raise ValueError(f"60s pooled control mismatch at {offset:g}bp: {actual} != {expected}")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    frame.to_csv(partial, index=False)
    os.replace(partial, path)


def _reports_from_daily(output: Path):
    parts = sorted((output / "daily").glob("date=*/cells.parquet"))
    if not parts:
        raise ValueError("no daily cell shards")
    return (*build_reports(_combine(parts)), parts)


def run(output: Path = OUTPUT) -> None:
    if sha256(PLAN) != PLAN_SHA256:
        raise ValueError("frozen plan SHA-256 mismatch")
    if output.exists():
        if (output / "_SUCCESS").is_file():
            verify(output)
            return
        raise FileExistsError(f"incomplete output exists; preserve or remove explicitly: {output}")
    output.mkdir(parents=True)
    started = time.monotonic()
    frozen = FrozenInputs(BASE)
    source = Path(__file__).resolve()
    save_json(output / "manifest.json", {
        "status": "RUNNING", "plan": {"path": PLAN.as_posix(), "sha256": PLAN_SHA256},
        "source": {"path": source.relative_to(Path.cwd()).as_posix(),
                   "sha256": sha256(source)},
        "base_manifest_sha256": frozen.base_manifest_sha256,
        "data_cutoff": "2024-04-01T06:46:00+00:00",
        "new_model_fits": 0, "new_orders": 0,
    })
    days = [path.name.removeprefix("date=") for path in sorted((BASE / "shards").glob("date=*"))]
    feature_parts = []
    audits = []
    with RssGuard(RSS_LIMIT) as guard:
        for day in days:
            guard.begin_block()
            origins = frozen.day_frame(day, "origins", ["origin", "raw_origin_valid"])
            origin_ms = _epoch_ms(origins.origin)
            trades = frozen.trades(int(origin_ms.min()) - MAX_AGE_MS, int(origin_ms.max()))
            reference, valid = _asof_prices(
                trades.transact_time.to_numpy(np.int64), trades.price.to_numpy(float),
                origin_ms, before=True)
            if not np.array_equal(valid, origins.raw_origin_valid.to_numpy(bool)):
                raise ValueError(f"raw origin validity mismatch: {day}")
            feature_parts.append(pd.DataFrame({"origin": origins.origin,
                                               "raw_reference": reference}))
            del origins, trades, reference
            gc.collect()
            guard.end_block(f"features {day}")
        features = causal_features(pd.concat(feature_parts, ignore_index=True))
        feature_path = output / "origin_features.parquet"
        _atomic_parquet(features, feature_path)
        del feature_parts
        gc.collect()

        for day in days:
            guard.begin_block()
            outcomes = frozen.day_frame(
                day, "outcomes", ["origin", "side", "offset_bps", "raw_fill",
                                  "raw_fill_ms", "raw_quote", "raw_valid",
                                  "raw_markout_bps"])
            day_features = features[features.origin.dt.strftime("%Y-%m-%d") == day]
            origin_ms = _epoch_ms(day_features.origin)
            fill_ms = outcomes.raw_fill_ms.to_numpy(np.int64)
            maximum = max(int(origin_ms.max()) + 60_000,
                          int(fill_ms[fill_ms >= 0].max()) + 60_000)
            trades = frozen.trades(int(origin_ms.min()), maximum + MAX_AGE_MS)
            cells, audit = _day_cells(outcomes, day_features, trades)
            directory = output / "daily" / f"date={day}"
            _atomic_parquet(cells, directory / "cells.parquet")
            save_json(directory / "audit.json", audit)
            audits.append(audit)
            del outcomes, day_features, trades, cells
            gc.collect()
            guard.end_block(f"measure {day}")

        overall, primary, direction, correlations, results, daily_parts = _reports_from_daily(output)
        audit = {"compared": sum(row["compared"] for row in audits),
                 "mask_mismatch": sum(row["mask_mismatch"] for row in audits),
                 "max_abs_diff_bps": max(row["max_abs_diff_bps"] for row in audits)}
        _check_control(overall, audit)
        results["control_60s"] = audit
        results["execution"] = {"peak_rss_bytes": guard.maximum,
                                "peak_rss_gib": guard.maximum / 1024**3,
                                "wall_clock_seconds": time.monotonic() - started}
        for frame, name in ((overall, "overall.csv"), (primary, "cells.csv"),
                            (direction, "direction_cells.csv"),
                            (correlations, "correlations.csv")):
            _write_csv(frame, output / name)
        save_json(output / "results.json", results)
        output_paths = [feature_path, output / "overall.csv", output / "cells.csv",
                        output / "direction_cells.csv", output / "correlations.csv",
                        output / "results.json", *daily_parts,
                        *sorted((output / "daily").glob("date=*/audit.json"))]
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        manifest.update({
            "status": "COMPLETE", "python": platform.python_version(),
            "pandas": pd.__version__, "pyarrow": pa.__version__,
            "inputs": sorted(frozen.records.values(), key=lambda row: row["path"]),
            "outputs": [_record(path, output) for path in output_paths],
            "peak_rss_bytes": guard.maximum, "new_model_fits": 0, "new_orders": 0,
        })
        save_json(output / "manifest.json", manifest)
        marker = output / "_SUCCESS.partial"
        marker.write_text("ok\n", encoding="ascii")
        os.replace(marker, output / "_SUCCESS")
    verify(output)


def verify(output: Path = OUTPUT) -> None:
    if sha256(PLAN) != PLAN_SHA256:
        raise ValueError("frozen plan SHA-256 mismatch")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "COMPLETE" or not (output / "_SUCCESS").is_file():
        raise ValueError("measurement is incomplete")
    if manifest["base_manifest_sha256"] != sha256(BASE / "manifest.json"):
        raise ValueError("base R1 manifest changed")
    source = Path(manifest["source"]["path"])
    if manifest["source"]["sha256"] != sha256(source):
        raise ValueError("measurement source changed")
    for row in manifest["inputs"]:
        path = BASE / row["path"]
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise ValueError(f"frozen input changed: {path}")
    for row in manifest["outputs"]:
        path = output / row["path"]
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise ValueError(f"measurement output changed: {path}")
    overall, primary, direction, correlations, rebuilt, _ = _reports_from_daily(output)
    saved = json.loads((output / "results.json").read_text(encoding="utf-8"))
    for key in ("status", "first_positive_liquid_horizon_s", "first_horizon_fix_s",
                "correlations", "positive_liquid_cells", "fade_disguise",
                "new_model_fits", "new_orders"):
        if saved.get(key) != rebuilt.get(key):
            raise ValueError(f"results reconstruction mismatch: {key}")
    expected = ((overall, "overall.csv"), (primary, "cells.csv"),
                (direction, "direction_cells.csv"), (correlations, "correlations.csv"))
    for frame, name in expected:
        stored = pd.read_csv(output / name)
        pd.testing.assert_frame_equal(stored, frame, check_dtype=False, atol=1e-12, rtol=1e-12)
    if saved["new_model_fits"] != 0 or saved["new_orders"] != 0:
        raise ValueError("zero-fit/order invariant failed")
    print(json.dumps({"status": "VERIFIED", "verdict": saved["status"],
                      "new_model_fits": 0, "new_orders": 0}, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify(args.output) if args.verify else run(args.output)


if __name__ == "__main__":
    main()
