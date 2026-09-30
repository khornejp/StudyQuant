"""Controlled H15 short-return ablation with next-bar executable entry."""
from __future__ import annotations

import argparse
import gc
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .gru import SEQUENCE_LENGTH
from .short_direction import (
    FUNDING_DIRECTION_FEATURES,
    FUNDING_FEATURE_NAMES,
    SIGNED_FEATURE_NAMES,
    add_funding_direction_features,
    add_signed_direction_features,
)
from .short_fast_regime import (
    QUANTILES,
    REGIME_NAMES,
    _enhanced_metrics,
    _prediction,
    _quantile_key,
    _safe_ic,
    add_fast_regime_features,
    assign_regimes,
    fit_regime_thresholds,
    fold_signal_masks,
    tune_fold,
)
from .short_sequence import COST, _indices, _status, _write_json, build_features, walk_forward_folds


RUN_ROOT = Path("artifacts/short_executable_ablation_20260904")
HORIZON = 15
FEATURE_SETS: Mapping[str, tuple[str, ...]] = {
    "direction_10": tuple(SIGNED_FEATURE_NAMES),
    "funding_6": tuple(FUNDING_FEATURE_NAMES),
    "direction_funding_16": (*SIGNED_FEATURE_NAMES, *FUNDING_FEATURE_NAMES),
    "all_47": tuple(FUNDING_DIRECTION_FEATURES),
}


def next_open_short_return(frame: pd.DataFrame, horizon: int = HORIZON) -> np.ndarray:
    """Short gross return: signal after bar t, enter t+1 open, exit t+h close."""
    if horizon < 1:
        raise ValueError("horizon must be positive")
    opens = frame["open"].to_numpy(float)
    closes = frame["close"].to_numpy(float)
    gross = np.full(len(frame), np.nan, dtype=float)
    if len(frame) > horizon:
        gross[:-horizon] = 1.0 - closes[horizon:] / opens[1:len(frame) - horizon + 1]
    return gross


def _run_model(
    frame: pd.DataFrame,
    feature_set: str,
    feature_names: Sequence[str],
    family: str,
    gross: np.ndarray,
    valid: np.ndarray,
    trials: int,
    output: Path,
    gate_specs: Mapping[str, tuple[str, float]] | None = None,
) -> dict[str, object]:
    values = frame.loc[:, list(feature_names)].to_numpy(np.float32)
    target_bps = (gross - COST) * 1e4
    folds = walk_forward_folds(purge_bars=HORIZON)
    gate_specs = gate_specs or {}
    selections = {
        _quantile_key(q): {
            name: [] for name in ("regime_unfiltered", "regime_filtered", *gate_specs, *REGIME_NAMES)
        }
        for q in QUANTILES
    }
    all_times: list[pd.Timestamp] = []
    all_gross: list[float] = []
    all_targets: list[float] = []
    all_predictions: list[float] = []
    fold_reports: list[dict[str, object]] = []
    stage = f"{feature_set}_{family}"
    for fold in folds:
        train_all = _indices(frame.open_time, fold.train_start, fold.train_end, valid)
        validation_all = _indices(frame.open_time, fold.validation_start, fold.validation_end, valid)
        test = _indices(frame.open_time, fold.test_start, fold.test_end, valid)
        train, validation_tune = train_all[::HORIZON], validation_all[::HORIZON]
        if min(len(train), len(validation_tune), len(validation_all), len(test)) == 0:
            continue
        thresholds = fit_regime_thresholds(frame, train_all)
        regimes = assign_regimes(frame, thresholds)
        gate_thresholds = {
            name: float(np.quantile(frame.iloc[train_all][column].dropna(), quantile))
            for name, (column, quantile) in gate_specs.items()
        }
        validation_gates = {
            name: frame.iloc[validation_all][column].to_numpy(float) >= gate_thresholds[name]
            for name, (column, _) in gate_specs.items()
        }
        test_gates = {
            name: frame.iloc[test][column].to_numpy(float) >= gate_thresholds[name]
            for name, (column, _) in gate_specs.items()
        }
        model, _, tuning = tune_fold(family, values, target_bps, train, validation_tune, trials)
        validation_scores = _prediction(model, family, values, validation_all)
        test_scores = _prediction(model, family, values, test)
        masks, threshold_audit = fold_signal_masks(
            frame.iloc[validation_all].open_time.tolist(), validation_scores, gross[validation_all],
            regimes[validation_all], test_scores, regimes[test], HORIZON,
            validation_gates, test_gates,
        )
        all_times.extend(frame.iloc[test].open_time.tolist())
        all_gross.extend(gross[test].tolist())
        all_targets.extend(target_bps[test].tolist())
        all_predictions.extend(test_scores.tolist())
        for quantile, modes in masks.items():
            for mode, mask in modes.items():
                selections[quantile][mode].extend(mask.tolist())
        fold_reports.append({
            "fold": fold.index,
            "test_start": fold.test_start.isoformat(),
            "test_end": fold.test_end.isoformat(),
            "train_rows": len(train),
            "validation_rows": len(validation_all),
            "test_rows": len(test),
            "regime_thresholds_from_train_only": thresholds,
            "external_gate_thresholds_from_train_only": gate_thresholds,
            "tuning": tuning,
            "thresholds_and_validation_gates": threshold_audit,
        })
        del model
        gc.collect()
        _status(output, "running", stage, f"completed fold {fold.index + 1}/{len(folds)}")
    gross_oof = np.asarray(all_gross, dtype=float)
    quantile_results = {
        quantile: {
            mode: _enhanced_metrics(all_times, np.asarray(mask, dtype=bool), gross_oof, HORIZON)
            for mode, mask in modes.items()
        }
        for quantile, modes in selections.items()
    }
    return {
        "model_family": "pytorch_gru" if family == "gru" else family,
        "feature_set": feature_set,
        "feature_names": list(feature_names),
        "sequence_length": SEQUENCE_LENGTH if family == "gru" else None,
        "selection_validation_ic": float(np.mean([
            fold["tuning"]["best_validation_ic"] for fold in fold_reports
        ])),
        "oof_spearman_ic": _safe_ic(np.asarray(all_predictions), np.asarray(all_targets)),
        "folds": fold_reports,
        "quantiles": quantile_results,
    }


def run_experiment(
    input_path: Path,
    metrics_dir: Path,
    funding_dir: Path,
    premium_dir: Path,
    output: Path = RUN_ROOT,
    trials: int = 4,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing executable ablation directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding common 47-feature source data")
        frame = add_funding_direction_features(add_signed_direction_features(
            add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        ))
        gross = next_open_short_return(frame)
        common_finite = np.isfinite(frame.loc[:, list(FUNDING_DIRECTION_FEATURES)]).all(axis=1) & np.isfinite(gross)
        valid = pd.Series(common_finite).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        results: dict[str, object] = {
            "designation": "posthoc_next_open_h15_feature_ablation",
            "live_approval_eligible": False,
            "target": {
                "name": "next_bar_open_to_h15_close_short_return_minus_4bps",
                "signal_time": "after_t_bar_close",
                "entry": "t_plus_1_open",
                "exit": "t_plus_15_close",
                "cost_bps": COST * 1e4,
            },
            "horizon": HORIZON,
            "trials_per_family_per_fold": trials,
            "quantiles": list(QUANTILES),
            "trade_count_filter": None,
            "common_sample_across_feature_sets": True,
            "feature_sets": {name: list(features) for name, features in FEATURE_SETS.items()},
            "models": {},
        }
        validation_scores: dict[str, list[float]] = {name: [] for name in FEATURE_SETS}
        for feature_set, feature_names in FEATURE_SETS.items():
            set_results: dict[str, object] = {}
            for family in ("catboost", "lightgbm"):
                _status(output, "running", f"{feature_set}_{family}", f"screening {feature_set} with {family}")
                model_result = _run_model(
                    frame, feature_set, feature_names, family, gross, valid, trials, output,
                )
                set_results[family] = model_result
                validation_scores[feature_set].append(float(model_result["selection_validation_ic"]))
                _write_json(output / f"{feature_set}_{family}.json", model_result)
            results["models"][feature_set] = set_results  # type: ignore[index]
        selected = max(validation_scores, key=lambda name: float(np.mean(validation_scores[name])))
        results["gru_selection"] = {
            "criterion": "highest mean fold validation IC across CatBoost and LightGBM; OOF test returns excluded",
            "validation_ic_by_feature_set": {
                name: float(np.mean(scores)) for name, scores in validation_scores.items()
            },
            "selected_feature_set": selected,
        }
        _status(output, "running", f"{selected}_gru", f"tuning GRU on validation-selected {selected}")
        gru_result = _run_model(frame, selected, FEATURE_SETS[selected], "gru", gross, valid, trials, output)
        results["models"][selected]["gru"] = gru_result  # type: ignore[index]
        _write_json(output / f"{selected}_gru.json", gru_result)
        _write_json(output / "executable_ablation_results.json", results)
        _status(output, "complete", "complete", "next-open H15 feature ablation completed")
        return results
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
    parser.add_argument("--output", type=Path, default=RUN_ROOT)
    parser.add_argument("--trials", type=int, default=4)
    args = parser.parse_args(argv)
    run_experiment(
        args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir,
        output=args.output, trials=args.trials,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
