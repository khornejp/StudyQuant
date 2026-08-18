"""Block-permutation null control for persisted OOS ranking measurements.

Only the persisted probability score is reassigned.  Outcomes, gates, folds,
and the fold-local bucket definitions are held fixed; no model is loaded.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .ranking_skill import ArmSpec, DECILES, TAIL_PCTS, _ranked_masks, _sha256


BLOCK_ROWS = 45
PERMUTATIONS = 10_000
SEED = 20260818


@dataclass(frozen=True)
class FoldData:
    fold_index: int
    tp: np.ndarray
    probability: np.ndarray
    descending_rank: np.ndarray


def _load_gated_folds(spec: ArmSpec) -> tuple[list[FoldData], dict[str, Any]]:
    """Load exactly the gated test populations used by the original measure."""
    prediction_path = spec.path / "fold_test_predictions.csv"
    selection_path = spec.path / "threshold_selection_inputs.npz"
    predictions = pd.read_csv(prediction_path)
    with np.load(selection_path, allow_pickle=False) as stored:
        selection_metadata = json.loads(str(stored["metadata"].item()))
    expected_ids = [f"fold_{index}" for index in sorted(predictions["fold_index"].unique())]
    if [item["selection_id"] for item in selection_metadata["selections"]] != expected_ids:
        raise ValueError(f"{spec.name}: threshold-input folds do not match test-prediction folds")
    summary = json.loads((spec.path / "run_summary.json").read_text(encoding="utf-8"))
    provenance = json.loads((spec.path / "provenance.json").read_text(encoding="utf-8"))
    config = provenance["invocation"]["resolved_config"]
    gate = summary["oos_trading"]["gated"]["gate"]
    gate_feature, minima = str(gate["feature"]), gate["minimum_by_fold"]
    gate_column = f"sigma__{gate_feature}"
    if gate_column not in predictions:
        raise ValueError(f"{spec.name}: missing persisted gate feature {gate_column}")
    folds: list[FoldData] = []
    for fold_index in sorted(predictions["fold_index"].unique()):
        full = predictions[predictions["fold_index"] == fold_index].reset_index(drop=True)
        eligible = np.isfinite(full[gate_column].to_numpy(dtype=float)) & (
            full[gate_column].to_numpy(dtype=float) >= float(minima[int(fold_index)])
        )
        fold = full.loc[eligible].reset_index(drop=True)
        if fold.empty:
            raise ValueError(f"{spec.name}: fold {fold_index} has no gated rows")
        tp = np.isclose(fold["payoff"].to_numpy(dtype=float), float(config["tp_pct"]), rtol=0.0, atol=1e-12)
        probability = fold["probability"].to_numpy(dtype=float)
        order = np.argsort(-probability, kind="mergesort")
        rank = np.empty(len(probability), dtype=np.int32)
        rank[order] = np.arange(len(probability), dtype=np.int32)
        folds.append(FoldData(int(fold_index), tp, probability, rank))
    source = {
        "arm": spec.name,
        "artifact_directory": str(spec.path),
        "fold_test_predictions_sha256": _sha256(prediction_path),
        "threshold_selection_inputs_sha256": _sha256(selection_path),
        "threshold_selection_inputs_role": "Validation-only provenance check; not used in the control calculation.",
        "fold_test_predictions_rows": int(len(predictions)),
        "gate_feature": gate_feature,
        "gate_minima_by_fold": minima,
        "tp_pct": float(config["tp_pct"]),
        "sl_pct": float(config["sl_pct"]),
    }
    return folds, source


def _bucket_lifts(tp: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    base = float(tp.mean())
    return {name: float(tp[mask].mean() - base) * 100.0 for name, mask in _ranked_masks(probability).items()}


def _block_permuted_values(values: np.ndarray, rng: np.random.Generator, block_rows: int) -> np.ndarray:
    """Permute contiguous values blocks, retaining each block's internal order."""
    blocks = [values[start : start + block_rows] for start in range(0, len(values), block_rows)]
    return np.concatenate([blocks[index] for index in rng.permutation(len(blocks))])


def _summary(values: np.ndarray, observed: float) -> dict[str, float | int]:
    exceedances = int(np.count_nonzero(values >= observed))
    return {
        "observed_lift_pp": observed,
        "null_mean_lift_pp": float(values.mean()),
        "null_sd_lift_pp": float(values.std(ddof=1)),
        "null_q025_lift_pp": float(np.quantile(values, 0.025)),
        "null_q50_lift_pp": float(np.quantile(values, 0.50)),
        "null_q975_lift_pp": float(np.quantile(values, 0.975)),
        "null_min_lift_pp": float(values.min()),
        "null_max_lift_pp": float(values.max()),
        "null_exceedances_ge_observed": exceedances,
        "empirical_p_one_sided_ge": float((exceedances + 1) / (len(values) + 1)),
    }


def run_arm(spec: ArmSpec, arm_number: int, *, permutations: int = PERMUTATIONS,
            block_rows: int = BLOCK_ROWS, seed: int = SEED) -> tuple[list[dict[str, Any]], dict[str, np.ndarray], dict[str, Any]]:
    """Return observed-v-null summaries for fold and pooled fold-local buckets."""
    if permutations < 1 or block_rows < 1:
        raise ValueError("permutations and block_rows must be positive")
    folds, source = _load_gated_folds(spec)
    bucket_names = tuple([f"decile_{d}" for d in DECILES] + [f"top_{p}_pct" for p in TAIL_PCTS])
    scopes = [f"fold_{fold.fold_index}" for fold in folds] + ["pooled_fold_local_ranks"]
    observed: dict[str, dict[str, float]] = {f"fold_{fold.fold_index}": _bucket_lifts(fold.tp, fold.probability) for fold in folds}
    pooled_tp = np.concatenate([fold.tp for fold in folds])
    # The pooled statistic is calculated after local ranking, exactly as in the
    # original measurement (not by ranking scores across folds).
    pooled_observed = {bucket: 0.0 for bucket in bucket_names}
    for bucket in bucket_names:
        selected_tp = []
        for fold in folds:
            selected_tp.append(fold.tp[_ranked_masks(fold.probability)[bucket]])
        pooled_observed[bucket] = (float(np.concatenate(selected_tp).mean()) - float(pooled_tp.mean())) * 100.0
    observed["pooled_fold_local_ranks"] = pooled_observed
    null = {scope: np.empty((permutations, len(bucket_names)), dtype=np.float64) for scope in scopes}
    rng = np.random.default_rng(np.random.SeedSequence([seed, arm_number]))
    for draw in range(permutations):
        pooled_selected_tp = {bucket: 0 for bucket in bucket_names}
        pooled_selected_rows = {bucket: 0 for bucket in bucket_names}
        for fold in folds:
            # Ranks are a lossless representation of score ordering.  Shuffling
            # them blockwise is exactly equivalent to shuffling scores then
            # re-ranking, while avoiding an unnecessary sort on every draw.
            rank = _block_permuted_values(fold.descending_rank, rng, block_rows)
            base = float(fold.tp.mean())
            # Match _ranked_masks exactly: its decile boundaries use floor,
            # so the first few deciles can be empty for very small folds.
            decile_stops = np.array([math.floor(d * len(rank) / 10) for d in range(1, 10)] + [len(rank)])
            decile = np.searchsorted(decile_stops, rank, side="right")
            decile_tp = np.bincount(decile, weights=fold.tp, minlength=10)
            decile_rows = np.bincount(decile, minlength=10)
            for index in range(10):
                bucket = bucket_names[index]
                selected_tp, selected_rows = decile_tp[index], decile_rows[index]
                null[f"fold_{fold.fold_index}"][draw, index] = (selected_tp / selected_rows - base) * 100.0
                pooled_selected_tp[bucket] += int(selected_tp)
                pooled_selected_rows[bucket] += int(selected_rows)
            for offset, pct in enumerate(TAIL_PCTS, start=10):
                bucket = bucket_names[offset]
                selected = fold.tp[rank < max(1, math.ceil(len(rank) * pct / 100.0))]
                null[f"fold_{fold.fold_index}"][draw, offset] = (float(selected.mean()) - base) * 100.0
                pooled_selected_tp[bucket] += int(selected.sum())
                pooled_selected_rows[bucket] += len(selected)
        for column, bucket in enumerate(bucket_names):
            pooled_lift = (pooled_selected_tp[bucket] / pooled_selected_rows[bucket] - float(pooled_tp.mean())) * 100.0
            null["pooled_fold_local_ranks"][draw, column] = pooled_lift
    rows: list[dict[str, Any]] = []
    for scope in scopes:
        for column, bucket in enumerate(bucket_names):
            row: dict[str, Any] = {"arm": spec.name, "scope": scope, "bucket": bucket,
                                   "permutations": permutations, "block_rows": block_rows}
            row.update(_summary(null[scope][:, column], observed[scope][bucket]))
            rows.append(row)
    source.update({"permutations": permutations, "block_rows": block_rows, "seed": seed})
    return rows, null, source
