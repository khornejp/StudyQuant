"""Out-of-sample ranking-skill measurement for persisted training artifacts.

This module deliberately does not load a model or apply an entry threshold. It
uses only the fold-test predictions written by the training artifact writer.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


DECILES = tuple(range(1, 11))
TAIL_PCTS = (1, 2, 5)


@dataclass(frozen=True)
class ArmSpec:
    name: str
    path: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _share_and_se(values: np.ndarray, selected: np.ndarray) -> tuple[float, float, float]:
    """Selected share, selected-minus-base pp, and conditional iid paired SE."""
    n_all, n_selected = len(values), int(selected.sum())
    if not n_selected:
        return math.nan, math.nan, math.nan
    base = float(values.mean())
    share = float(values[selected].mean())
    # The selected set is contained in the base population, so their estimates
    # are paired: Var(p_selected - p_all) = p(1-p)(1/n_selected - 1/n_all).
    variance = base * (1.0 - base) * (1.0 / n_selected - 1.0 / n_all)
    return share, (share - base) * 100.0, math.sqrt(max(variance, 0.0)) * 100.0


def _ranked_masks(probability: np.ndarray) -> dict[str, np.ndarray]:
    """Fold-local buckets; input order resolves equal probabilities stably."""
    n = len(probability)
    order = np.argsort(-probability, kind="mergesort")
    masks: dict[str, np.ndarray] = {}
    for decile in DECILES:
        start = math.floor((decile - 1) * n / 10)
        stop = math.floor(decile * n / 10) if decile < 10 else n
        mask = np.zeros(n, dtype=bool)
        mask[order[start:stop]] = True
        masks[f"decile_{decile}"] = mask
    for pct in TAIL_PCTS:
        mask = np.zeros(n, dtype=bool)
        mask[order[:max(1, math.ceil(n * pct / 100.0))]] = True
        masks[f"top_{pct}_pct"] = mask
    return masks


def _result_row(arm: str, scope: str, bucket: str, tp: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    share, lift_pp, se_pp = _share_and_se(tp, mask)
    return {
        "arm": arm, "scope": scope, "bucket": bucket,
        "gated_rows": int(len(tp)), "bucket_rows": int(mask.sum()),
        "base_tp_share_pct": float(tp.mean() * 100.0),
        "bucket_tp_share_pct": share * 100.0, "tp_share_lift_pp": lift_pp,
        "lift_se_pp_conditional_iid": se_pp,
        "lift_95pct_normal_ci_low_pp": lift_pp - 1.96 * se_pp,
        "lift_95pct_normal_ci_high_pp": lift_pp + 1.96 * se_pp,
    }


def measure_ranked_folds(
    arm: str, folds: Iterable[tuple[int, np.ndarray, np.ndarray]],
) -> list[dict[str, Any]]:
    """Measure the production ranking statistic for supplied gated folds.

    ``folds`` contains ``(fold_index, strict_tp, score)`` triples.  This is
    deliberately the calculation core used by :func:`measure_arm`, and gives
    validation probes a way to replace only the score while preserving the
    real, gated outcome population and fold-local ranking convention.
    """
    rows: list[dict[str, Any]] = []
    pooled_tp: list[np.ndarray] = []
    pooled_masks: dict[str, list[np.ndarray]] = {}
    for fold_index, is_tp, probability in folds:
        is_tp = np.asarray(is_tp, dtype=bool)
        probability = np.asarray(probability, dtype=float)
        if len(is_tp) == 0 or len(is_tp) != len(probability):
            raise ValueError("each ranked fold needs equally sized, non-empty outcome and score arrays")
        masks = _ranked_masks(probability)
        scope = f"fold_{int(fold_index)}"
        for bucket, mask in masks.items():
            rows.append(_result_row(arm, scope, bucket, is_tp, mask))
            pooled_masks.setdefault(bucket, []).append(mask)
        pooled_tp.append(is_tp)
    if not pooled_tp:
        raise ValueError("at least one ranked fold is required")
    pooled_values = np.concatenate(pooled_tp)
    for bucket, masks in pooled_masks.items():
        rows.append(_result_row(arm, "pooled_fold_local_ranks", bucket, pooled_values, np.concatenate(masks)))
    return rows


def measure_arm(spec: ArmSpec) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Measure strict realised TP-share ranking lift from one corrected arm."""
    prediction_path = spec.path / "fold_test_predictions.csv"
    selection_path = spec.path / "threshold_selection_inputs.npz"
    predictions = pd.read_csv(prediction_path)
    with np.load(selection_path, allow_pickle=False) as stored:
        selection_metadata = json.loads(str(stored["metadata"].item()))
    # The NPZ stores validation inputs used to select each threshold, whereas
    # the CSV stores the test predictions.  They must not be joined or used as
    # a substitute for the test rows in this measurement.
    selection_ids = [item["selection_id"] for item in selection_metadata["selections"]]
    expected_ids = [f"fold_{index}" for index in sorted(predictions["fold_index"].unique())]
    if selection_ids != expected_ids:
        raise ValueError(f"{spec.name}: threshold-input folds do not match test-prediction folds")
    summary = json.loads((spec.path / "run_summary.json").read_text(encoding="utf-8"))
    provenance = json.loads((spec.path / "provenance.json").read_text(encoding="utf-8"))
    config = provenance["invocation"]["resolved_config"]
    tp_pct, sl_pct = float(config["tp_pct"]), float(config["sl_pct"])
    gate = summary["oos_trading"]["gated"]["gate"]
    gate_feature, minima = str(gate["feature"]), gate["minimum_by_fold"]
    gate_column = f"sigma__{gate_feature}"
    if gate_column not in predictions:
        raise ValueError(f"{spec.name}: missing persisted gate feature {gate_column}")

    ranked_folds: list[tuple[int, np.ndarray, np.ndarray]] = []
    populations: list[dict[str, Any]] = []
    for fold_index in sorted(predictions["fold_index"].unique()):
        full_fold = predictions[predictions["fold_index"] == fold_index].reset_index(drop=True)
        minimum = float(minima[int(fold_index)])
        gate_values = full_fold[gate_column].to_numpy(dtype=float)
        eligible = np.isfinite(gate_values) & (gate_values >= minimum)
        fold = full_fold.loc[eligible].reset_index(drop=True)
        if fold.empty:
            raise ValueError(f"{spec.name}: fold {fold_index} has no gated rows")
        payoff = fold["payoff"].to_numpy(dtype=float)
        # Strict TP, rather than the profitability label: all remaining rows
        # after TP/SL classification are realised horizon-close timeouts.
        is_tp = np.isclose(payoff, tp_pct, rtol=0.0, atol=1e-12)
        is_sl = np.isclose(payoff, -sl_pct, rtol=0.0, atol=1e-12)
        is_timeout = ~(is_tp | is_sl)
        probability = fold["probability"].to_numpy(dtype=float)
        scope = f"fold_{int(fold_index)}"
        ranked_folds.append((int(fold_index), is_tp, probability))
        populations.append({
            "arm": spec.name, "scope": scope, "gate_feature": gate_feature, "gate_minimum": minimum,
            "gated_rows": int(len(fold)), "tp_rows": int(is_tp.sum()), "sl_rows": int(is_sl.sum()),
            "timeout_rows": int(is_timeout.sum()), "tp_share_pct": float(is_tp.mean() * 100.0),
            "timeout_share_pct": float(is_timeout.mean() * 100.0),
            "timeout_mean_payoff_bps": float(payoff[is_timeout].mean() * 10_000.0) if is_timeout.any() else math.nan,
            "unresolved_rows": 0,
        })
    rows = measure_ranked_folds(spec.name, ranked_folds)
    pooled_values = np.concatenate([tp for _, tp, _ in ranked_folds])
    populations.append({
        "arm": spec.name, "scope": "pooled_fold_local_ranks", "gate_feature": gate_feature,
        "gate_minimum": float(minima[0]), "gated_rows": int(len(pooled_values)),
        "tp_rows": int(pooled_values.sum()), "sl_rows": int(sum(row["sl_rows"] for row in populations)),
        "timeout_rows": int(sum(row["timeout_rows"] for row in populations)),
        "tp_share_pct": float(pooled_values.mean() * 100.0),
        "timeout_share_pct": float(sum(row["timeout_rows"] for row in populations) / len(pooled_values) * 100.0),
        "timeout_mean_payoff_bps": math.nan, "unresolved_rows": 0,
    })
    source = {
        "arm": spec.name, "artifact_directory": str(spec.path),
        "fold_test_predictions_sha256": _sha256(prediction_path),
        "threshold_selection_inputs_sha256": _sha256(selection_path),
        "train_target": config["train_target"], "tp_pct": tp_pct, "sl_pct": sl_pct,
        "round_trip_cost": float(config["round_trip_cost"]), "gate_feature": gate_feature,
        "gate_minima_by_fold": minima, "short_side_available": False,
        "threshold_inputs_role": "Validation-only threshold-selection inputs. They were checked for matching fold IDs but not used in the test-row calculation.",
        "short_side_note": "Only one long-side profitability probability and payoff are stored; no short probability or short realised payoff is present.",
    }
    return rows, populations, source


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialised = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialised[0]))
        writer.writeheader()
        writer.writerows(materialised)
