"""H15 GRU feature ablation plus intrawindow short-path diagnostics."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .gru import GRU_FEATURE_NAMES, SEQUENCE_LENGTH
from .short_fast_regime import (
    ADDED_FAST_FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    QUANTILES,
    REGIME_NAMES,
    _enhanced_metrics,
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


RUN_ROOT = Path("artifacts/short_fast_ablation_20260829")
REFERENCE = Path("artifacts/short_fast_regime_experiment_20260828/h15_gru.json")
HORIZON = 15

FAST_PRICE_FLOW_FEATURES = (
    "return_1", "return_3", "return_5", "log_return_1",
    "high_low_range", "body_pct", "upper_shadow", "lower_shadow", "close_location_value",
    "volume_sma_20_ratio", "volume_zscore_20", "quote_volume_sma_20_ratio",
    "taker_ratio", "taker_imbalance", "taker_quote_ratio",
    "trade_count_ratio", "trade_count_zscore_20", "rv_5", "rv_15", "rv_30", "atr_pct",
    *ADDED_FAST_FEATURE_NAMES,
)
FAST_DERIVATIVE_FEATURES = (
    *FAST_PRICE_FLOW_FEATURES,
    "oi_change_rate_5m", "oi_change_rate_15m",
    "global_ls_account_change_5m", "taker_ls_ratio_change_5m",
)
FEATURE_SETS = {
    "all_34": MODEL_FEATURE_NAMES,
    "fast_price_flow_27": FAST_PRICE_FLOW_FEATURES,
    "fast_plus_derivatives_31": FAST_DERIVATIVE_FEATURES,
}


def _selected_positions(times: Sequence[pd.Timestamp], selected: np.ndarray, horizon: int) -> np.ndarray:
    positions, next_time = [], None
    for position, when in enumerate(times):
        if bool(selected[position]) and (next_time is None or when >= next_time):
            positions.append(position)
            next_time = when + pd.Timedelta(minutes=horizon)
    return np.asarray(positions, dtype=np.int64)


def _first_touch_payoff(frame: pd.DataFrame, entry_index: int, horizon: int, tp: float, sl: float) -> float:
    close = float(frame.iloc[entry_index].close)
    stop = min(len(frame), entry_index + horizon + 1)
    for future_index in range(entry_index + 1, stop):
        row = frame.iloc[future_index]
        hit_tp = float(row.low) <= close * (1.0 - tp)
        hit_sl = float(row.high) >= close * (1.0 + sl)
        if hit_tp or hit_sl:
            tp_first = hit_tp and (not hit_sl or float(row.close) < float(row.open))
            return tp if tp_first else -sl
    if stop <= entry_index + horizon:
        return math.nan
    return -(float(frame.iloc[entry_index + horizon].close) / close - 1.0)


def path_diagnostics(
    frame: pd.DataFrame, source_indices: Sequence[int], times: Sequence[pd.Timestamp],
    selected: np.ndarray, horizon: int = HORIZON,
) -> dict[str, object]:
    positions = _selected_positions(times, selected, horizon)
    source = np.asarray(source_indices, dtype=np.int64)[positions]
    mfe, mae, endpoint, first_touch = [], [], [], []
    for index in source:
        entry = float(frame.iloc[index].close)
        future = frame.iloc[index + 1:index + horizon + 1]
        if len(future) != horizon:
            continue
        mfe.append((entry - float(future.low.min())) / entry)
        mae.append((float(future.high.max()) - entry) / entry)
        endpoint.append(-(float(future.iloc[-1].close) / entry - 1.0))
        first_touch.append(_first_touch_payoff(frame, int(index), horizon, 0.006, 0.012))
    mfe_values = np.asarray(mfe, dtype=float)
    mae_values = np.asarray(mae, dtype=float)
    endpoint_values = np.asarray(endpoint, dtype=float)
    touch_values = np.asarray(first_touch, dtype=float)
    endpoint_profitable = endpoint_values > COST
    intrawindow_profitable = mfe_values > COST
    return {
        "trades": int(len(mfe_values)),
        "mean_mfe_bps": float(mfe_values.mean() * 1e4) if len(mfe_values) else 0.0,
        "mean_mae_bps": float(mae_values.mean() * 1e4) if len(mae_values) else 0.0,
        "mfe_above_4bps_share": float(np.mean(mfe_values > COST)) if len(mfe_values) else 0.0,
        "mfe_above_8bps_share": float(np.mean(mfe_values > 0.0008)) if len(mfe_values) else 0.0,
        "endpoint_positive_after_cost_share": float(endpoint_profitable.mean()) if len(mfe_values) else 0.0,
        "intrawindow_positive_but_endpoint_not_share": (
            float(np.mean(intrawindow_profitable & ~endpoint_profitable)) if len(mfe_values) else 0.0
        ),
        "tp_0.6_sl_1.2_first_touch_mean_net_bps": (
            float((touch_values - COST).mean() * 1e4) if len(touch_values) else 0.0
        ),
        "tp_0.6_sl_1.2_first_touch_positive_share": (
            float(np.mean(touch_values > COST)) if len(touch_values) else 0.0
        ),
    }


def _reference_params(path: Path) -> dict[int, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    folds = payload.get("folds", [])
    params = {int(fold["fold"]): dict(fold["tuning"]["best_params"]) for fold in folds}
    if len(params) != len(walk_forward_folds(purge_bars=HORIZON)):
        raise ValueError("reference H15 GRU artifact does not cover every walk-forward fold")
    return params


def run_ablation(
    input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path,
    output: Path = RUN_ROOT, reference: Path = REFERENCE,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing ablation directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding sources for H15 GRU feature ablation")
        frame = add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        gross = short_gross_return(frame, HORIZON)
        target_bps = (gross - COST) * 1e4
        reference_params = _reference_params(reference)
        all_values = frame.loc[:, list(MODEL_FEATURE_NAMES)].to_numpy(np.float32)
        common_finite = np.isfinite(all_values).all(axis=1) & np.isfinite(gross)
        common_valid = pd.Series(common_finite).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        folds = walk_forward_folds(purge_bars=HORIZON)
        result: dict[str, object] = {
            "designation": "posthoc_h15_gru_feature_ablation", "live_approval_eligible": False,
            "horizon": HORIZON, "cost_bps": COST * 1e4, "trade_count_filter": None,
            "reference_hyperparameters": str(reference),
            "feature_sets": {name: list(features) for name, features in FEATURE_SETS.items()},
            "results": {},
        }
        for set_name, feature_names in FEATURE_SETS.items():
            _status(output, "running", set_name, f"running {set_name} with fixed fold-selected GRU parameters")
            values = frame.loc[:, list(feature_names)].to_numpy(np.float32)
            all_times: list[pd.Timestamp] = []
            all_source_indices: list[int] = []
            all_gross: list[float] = []
            selections = {
                _quantile_key(q): {name: [] for name in ("regime_unfiltered", "regime_filtered", *REGIME_NAMES)}
                for q in QUANTILES
            }
            fold_reports = []
            for fold in folds:
                train_all = _indices(frame.open_time, fold.train_start, fold.train_end, common_valid)
                validation_all = _indices(frame.open_time, fold.validation_start, fold.validation_end, common_valid)
                test = _indices(frame.open_time, fold.test_start, fold.test_end, common_valid)
                train = train_all[::HORIZON]
                validation_train = validation_all[::HORIZON]
                thresholds = fit_regime_thresholds(frame, train_all)
                regimes = assign_regimes(frame, thresholds)
                params = reference_params[fold.index]
                model = _fit_gru(params, values, target_bps, train, validation_train)
                validation_scores = _prediction(model, "gru", values, validation_all)
                test_scores = _prediction(model, "gru", values, test)
                masks, gate_audit = fold_signal_masks(
                    frame.iloc[validation_all].open_time.tolist(), validation_scores, gross[validation_all],
                    regimes[validation_all], test_scores, regimes[test], HORIZON,
                )
                all_times.extend(frame.iloc[test].open_time.tolist())
                all_source_indices.extend(test.tolist())
                all_gross.extend(gross[test].tolist())
                for quantile, modes in masks.items():
                    for mode, mask in modes.items():
                        selections[quantile][mode].extend(mask.tolist())
                fold_reports.append({
                    "fold": fold.index, "feature_count": len(feature_names), "params": params,
                    "regime_thresholds_from_train_only": thresholds,
                    "thresholds_and_validation_gates": gate_audit,
                })
                del model
                _status(output, "running", set_name, f"completed fold {fold.index + 1}/{len(folds)} for {set_name}")
            gross_oof = np.asarray(all_gross, dtype=float)
            summaries = {}
            for quantile, modes in selections.items():
                summaries[quantile] = {}
                for mode, mask_values in modes.items():
                    mask = np.asarray(mask_values, dtype=bool)
                    metrics = _enhanced_metrics(all_times, mask, gross_oof, HORIZON)
                    if mode in {"regime_unfiltered", "regime_filtered"}:
                        metrics["path_diagnostics"] = path_diagnostics(
                            frame, all_source_indices, all_times, mask, HORIZON,
                        )
                    summaries[quantile][mode] = metrics
            set_result = {"feature_names": list(feature_names), "folds": fold_reports, "quantiles": summaries}
            result["results"][set_name] = set_result  # type: ignore[index]
            _write_json(output / f"{set_name}.json", set_result)
        comparison = []
        for set_name, set_result in result["results"].items():  # type: ignore[union-attr]
            for quantile, modes in set_result["quantiles"].items():
                for mode in ("regime_unfiltered", "regime_filtered"):
                    metrics = modes[mode]
                    comparison.append({
                        "feature_set": set_name, "quantile": quantile, "regime_mode": mode,
                        "trades": metrics["trades"], "mean_net_bps": metrics["mean_net_bps"],
                        "positive_years": metrics["positive_years"],
                        "path_diagnostics": metrics["path_diagnostics"],
                    })
        result["comparison"] = sorted(comparison, key=lambda row: float(row["mean_net_bps"]), reverse=True)
        _write_json(output / "h15_fast_ablation.json", result)
        _status(output, "complete", "complete", "H15 GRU fast-feature ablation completed")
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
    run_ablation(args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir, reference=args.reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
