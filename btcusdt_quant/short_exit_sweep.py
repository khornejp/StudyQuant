"""Cost-aware first-touch exit sweep for the H15 31-feature GRU."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .gru import SEQUENCE_LENGTH
from .short_fast_ablation import FAST_DERIVATIVE_FEATURES, REFERENCE, _reference_params, _selected_positions
from .short_fast_regime import (
    QUANTILES,
    _fit_gru,
    _prediction,
    _quantile_key,
    add_fast_regime_features,
    assign_regimes,
    fit_regime_thresholds,
    fold_signal_masks,
)
from .short_sequence import COST, _indices, _status, _write_json, build_features, walk_forward_folds
from .short_target_diagnostic import short_gross_return


RUN_ROOT = Path("artifacts/short_exit_sweep_20260830")
HORIZON = 15
TP_BPS = (8, 12, 20, 40, 60)
SL_BPS = (8, 12, 20, 40, 120)


def first_touch_grid(
    frame: pd.DataFrame, source_indices: Sequence[int], times: Sequence[pd.Timestamp], selected: np.ndarray,
    horizon: int = HORIZON, tp_bps: Sequence[int] = TP_BPS, sl_bps: Sequence[int] = SL_BPS,
) -> list[dict[str, object]]:
    """Evaluate exits on the same conservative non-overlapping entries for every geometry."""
    positions = _selected_positions(times, selected, horizon)
    source = np.asarray(source_indices, dtype=np.int64)[positions]
    valid = source + horizon < len(frame)
    source, positions = source[valid], positions[valid]
    if not len(source):
        return []
    offsets = np.arange(1, horizon + 1, dtype=np.int64)
    future = source[:, None] + offsets[None, :]
    entry = frame.close.to_numpy(float)[source]
    lows = frame.low.to_numpy(float)[future]
    highs = frame.high.to_numpy(float)[future]
    opens = frame.open.to_numpy(float)[future]
    closes = frame.close.to_numpy(float)[future]
    endpoint = -(closes[:, -1] / entry - 1.0)
    years = np.asarray([times[position].year for position in positions], dtype=np.int16)
    results = []
    for tp_value in tp_bps:
        tp = float(tp_value) / 1e4
        hit_tp = lows <= entry[:, None] * (1.0 - tp)
        for sl_value in sl_bps:
            sl = float(sl_value) / 1e4
            hit_sl = highs >= entry[:, None] * (1.0 + sl)
            hit = hit_tp | hit_sl
            has_hit = hit.any(axis=1)
            first = hit.argmax(axis=1)
            row = np.arange(len(source))
            tp_at_first = hit_tp[row, first]
            sl_at_first = hit_sl[row, first]
            tp_first = tp_at_first & (~sl_at_first | (closes[row, first] < opens[row, first]))
            gross = np.where(has_hit, np.where(tp_first, tp, -sl), endpoint)
            net = gross - COST
            holding = np.where(has_hit, first + 1, horizon)
            equity = np.cumsum(net)
            peak = np.maximum.accumulate(np.r_[0.0, equity])[-len(equity):]
            loss = -net[net < 0.0].sum()
            by_year = {}
            for year in range(2021, 2026):
                values = net[years == year]
                by_year[str(year)] = {
                    "trades": int(len(values)),
                    "mean_net_bps": float(values.mean() * 1e4) if len(values) else 0.0,
                    "net_return": float(values.sum()),
                }
            standard_error = float(net.std(ddof=1) / math.sqrt(len(net)) * 1e4) if len(net) > 1 else None
            results.append({
                "tp_bps": int(tp_value), "sl_bps": int(sl_value), "trades": int(len(net)),
                "mean_net_bps": float(net.mean() * 1e4), "net_return": float(net.sum()),
                "win_rate": float(np.mean(net > 0.0)),
                "profit_factor": float(net[net > 0.0].sum() / loss) if loss else None,
                "mdd": float((equity - peak).min()), "mean_holding_minutes": float(holding.mean()),
                "timeout_share": float(np.mean(~has_hit)),
                "positive_years": sum(value["net_return"] > 0.0 for value in by_year.values()),
                "by_year": by_year,
                "mean_net_bps_ci95": (
                    [float(net.mean() * 1e4 - 1.96 * standard_error),
                     float(net.mean() * 1e4 + 1.96 * standard_error)] if standard_error is not None else None
                ),
            })
    return sorted(results, key=lambda row: float(row["mean_net_bps"]), reverse=True)


def run_sweep(
    input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path,
    output: Path = RUN_ROOT, reference: Path = REFERENCE,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing exit sweep directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding 31-feature H15 GRU source data")
        frame = add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        feature_names = FAST_DERIVATIVE_FEATURES
        values = frame.loc[:, list(feature_names)].to_numpy(np.float32)
        gross = short_gross_return(frame, HORIZON)
        target_bps = (gross - COST) * 1e4
        finite = np.isfinite(values).all(axis=1) & np.isfinite(gross)
        valid = pd.Series(finite).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        params_by_fold = _reference_params(reference)
        selections = {
            _quantile_key(q): {"regime_unfiltered": [], "regime_filtered": []} for q in QUANTILES
        }
        all_times: list[pd.Timestamp] = []
        all_source_indices: list[int] = []
        fold_reports = []
        folds = walk_forward_folds(purge_bars=HORIZON)
        _status(output, "running", "oof", "reproducing 31-feature H15 GRU OOF signals")
        for fold in folds:
            train_all = _indices(frame.open_time, fold.train_start, fold.train_end, valid)
            validation_all = _indices(frame.open_time, fold.validation_start, fold.validation_end, valid)
            test = _indices(frame.open_time, fold.test_start, fold.test_end, valid)
            train, validation_train = train_all[::HORIZON], validation_all[::HORIZON]
            thresholds = fit_regime_thresholds(frame, train_all)
            regimes = assign_regimes(frame, thresholds)
            model = _fit_gru(params_by_fold[fold.index], values, target_bps, train, validation_train)
            validation_scores = _prediction(model, "gru", values, validation_all)
            test_scores = _prediction(model, "gru", values, test)
            masks, audit = fold_signal_masks(
                frame.iloc[validation_all].open_time.tolist(), validation_scores, gross[validation_all],
                regimes[validation_all], test_scores, regimes[test], HORIZON,
            )
            for quantile, modes in selections.items():
                for mode in modes:
                    modes[mode].extend(masks[quantile][mode].tolist())
            all_times.extend(frame.iloc[test].open_time.tolist())
            all_source_indices.extend(test.tolist())
            fold_reports.append({
                "fold": fold.index, "params": params_by_fold[fold.index],
                "regime_thresholds_from_train_only": thresholds, "thresholds_and_validation_gates": audit,
            })
            del model
            _status(output, "running", "oof", f"completed fold {fold.index + 1}/{len(folds)}")
        _status(output, "running", "exit_grid", "evaluating cost-aware first-touch TP/SL grid")
        grid = {}
        comparison = []
        for quantile, modes in selections.items():
            grid[quantile] = {}
            for mode, mask in modes.items():
                rows = first_touch_grid(
                    frame, all_source_indices, all_times, np.asarray(mask, dtype=bool), HORIZON,
                )
                grid[quantile][mode] = rows
                for row in rows:
                    comparison.append({"quantile": quantile, "regime_mode": mode, **row})
        comparison.sort(key=lambda row: float(row["mean_net_bps"]), reverse=True)
        result = {
            "designation": "posthoc_exit_geometry_diagnostic", "live_approval_eligible": False,
            "feature_names": list(feature_names), "horizon": HORIZON, "round_trip_cost_bps": COST * 1e4,
            "entry_lockout": "fixed_15_minutes_for_geometry_comparability", "trade_count_filter": None,
            "tp_bps": list(TP_BPS), "sl_bps": list(SL_BPS), "folds": fold_reports,
            "grid": grid, "comparison": comparison,
        }
        _write_json(output / "h15_exit_sweep.json", result)
        _status(output, "complete", "complete", "H15 first-touch exit sweep completed")
        return result
    except BaseException as error:
        _write_json(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        _status(output, "failed", "failed", str(error))
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/btcusdt_2020_2026h1.parquet"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("artifacts/metrics"))
    parser.add_argument("--funding-dir", type=Path, default=Path("artifacts/funding_2020_2026h1"))
    parser.add_argument("--premium-index-dir", type=Path, default=Path("artifacts/premium_index_2020_2026h1"))
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    args = parser.parse_args(argv)
    run_sweep(args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir, reference=args.reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
