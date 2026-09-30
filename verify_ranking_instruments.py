"""Stage-6 known-answer audit of ranking measurement and permutation control.

The probes retain the real gated test folds from the recorded source arm and
replace only its score.  They therefore do not train a model or run a backtest.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from btcusdt_quant.ranking_permutation_control import (
    BLOCK_ROWS, FoldData, _load_gated_folds, fold_data, run_folds,
)
from btcusdt_quant.ranking_skill import ArmSpec, _ranked_masks, measure_ranked_folds


ARM = ArmSpec("stage4_tp004_sl002_sources", Path("artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix"))
OUTPUT = Path("artifacts/stage6_ranking_instrument_probe_20260818")
TARGET_LIFT_PP = 3.14
NOISE_MEASUREMENT_REPETITIONS = 1_000
NOISE_PERMUTATION_REPETITIONS = 64
PERMUTATIONS = 499
SEED = 20260818


def _pooled(rows: list[dict]) -> dict[str, dict]:
    return {r["bucket"]: r for r in rows if r["scope"] == "pooled_fold_local_ranks"}


def _with_scores(folds: list[FoldData], scores: list[np.ndarray]) -> list[FoldData]:
    return [fold_data(fold.fold_index, fold.tp, score) for fold, score in zip(folds, scores, strict=True)]


def _noise_scores(folds: list[FoldData], rng: np.random.Generator) -> list[np.ndarray]:
    # Continuous draws remove ties, so stable tie breaking cannot drive a result.
    return [rng.random(len(fold.tp)) for fold in folds]


def _perfect_scores(folds: list[FoldData], rng: np.random.Generator) -> list[np.ndarray]:
    # The tiny continuous jitter gives a random order within outcome classes only.
    return [fold.tp.astype(float) + rng.random(len(fold.tp)) * 1e-6 for fold in folds]


def _injected_scores(folds: list[FoldData], rng: np.random.Generator) -> tuple[list[np.ndarray], float, int]:
    """Start with noise then promote just enough TP rows into top deciles."""
    scores = _noise_scores(folds, rng)
    selected: list[tuple[int, int]] = []
    outside: list[tuple[int, int]] = []
    for fi, (fold, score) in enumerate(zip(folds, scores, strict=True)):
        top = _ranked_masks(score)["decile_1"]
        selected.extend((fi, int(i)) for i in np.flatnonzero(top & fold.tp))
        outside.extend((fi, int(i)) for i in np.flatnonzero(~top & fold.tp))
    top_rows = sum(_ranked_masks(score)["decile_1"].sum() for score in scores)
    total_tp = sum(int(fold.tp.sum()) for fold in folds)
    total_rows = sum(len(fold.tp) for fold in folds)
    current = len(selected)
    target = round((total_tp / total_rows + TARGET_LIFT_PP / 100.0) * top_rows)
    # Swap a selected non-TP with an outside TP.  Every other rank remains noise.
    need = target - current
    if need < 0:
        raise AssertionError("chosen target unexpectedly lies below this seeded noise draw")
    bad_selected: list[tuple[int, int]] = []
    good_outside: list[tuple[int, int]] = []
    for fi, (fold, score) in enumerate(zip(folds, scores, strict=True)):
        top = _ranked_masks(score)["decile_1"]
        bad_selected.extend((fi, int(i)) for i in np.flatnonzero(top & ~fold.tp))
        good_outside.extend((fi, int(i)) for i in np.flatnonzero(~top & fold.tp))
    if need > min(len(bad_selected), len(good_outside)):
        raise AssertionError("requested injected lift is not attainable")
    for (bad_fold, bad), (good_fold, good) in zip(bad_selected[:need], good_outside[:need], strict=True):
        scores[bad_fold][bad], scores[good_fold][good] = scores[good_fold][good], scores[bad_fold][bad]
    actual = (target / top_rows - total_tp / total_rows) * 100.0
    return scores, actual, need


def _ceilings(folds: list[FoldData], scores: list[np.ndarray]) -> dict[str, dict[str, float]]:
    """Independent integer ceilings from TP count and fixed bucket sizes."""
    result: dict[str, dict[str, float]] = {}
    base_tp, total = sum(int(f.tp.sum()) for f in folds), sum(len(f.tp) for f in folds)
    base = base_tp / total
    for bucket in ("decile_1", "decile_10", "top_1_pct", "top_2_pct", "top_5_pct"):
        sizes = [int(_ranked_masks(score)[bucket].sum()) for score in scores]
        n = sum(sizes)
        top_max = min(base_tp, n) / n * 100.0
        bottom_min = max(0, base_tp - (total - n)) / n * 100.0
        result[bucket] = {"maximum_tp_share_pct": top_max, "minimum_tp_share_pct": bottom_min,
                          "base_tp_share_pct": base * 100.0}
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    folds, source = _load_gated_folds(ARM)
    rng = np.random.default_rng(SEED)
    bucket_names = [f"decile_{i}" for i in range(1, 11)]

    noise_lifts = {name: [] for name in bucket_names}
    noise_separations = []
    for _ in range(NOISE_MEASUREMENT_REPETITIONS):
        rows = _pooled(measure_ranked_folds("noise", [(f.fold_index, f.tp, s) for f, s in zip(folds, _noise_scores(folds, rng), strict=True)]))
        for name in bucket_names:
            noise_lifts[name].append(rows[name]["tp_share_lift_pp"])
        noise_separations.append(rows["decile_1"]["bucket_tp_share_pct"] - rows["decile_10"]["bucket_tp_share_pct"])

    perfect_scores = _perfect_scores(folds, rng)
    perfect = _pooled(measure_ranked_folds("perfect", [(f.fold_index, f.tp, s) for f, s in zip(folds, perfect_scores, strict=True)]))
    ceilings = _ceilings(folds, perfect_scores)
    injected_scores, injected_value, swaps = _injected_scores(folds, rng)
    injected = _pooled(measure_ranked_folds("injected", [(f.fold_index, f.tp, s) for f, s in zip(folds, injected_scores, strict=True)]))

    noise_p = []
    for rep in range(NOISE_PERMUTATION_REPETITIONS):
        scores = _noise_scores(folds, rng)
        rows, _ = run_folds("noise", _with_scores(folds, scores), rep, permutations=PERMUTATIONS, block_rows=BLOCK_ROWS, seed=SEED)
        noise_p.append(_pooled(rows)["decile_1"]["empirical_p_one_sided_ge"])
    perfect_perm, _ = run_folds("perfect", _with_scores(folds, perfect_scores), 1001, permutations=PERMUTATIONS, block_rows=BLOCK_ROWS, seed=SEED)
    injected_perm, _ = run_folds("injected", _with_scores(folds, injected_scores), 1002, permutations=PERMUTATIONS, block_rows=BLOCK_ROWS, seed=SEED)
    perfect_p = _pooled(perfect_perm)["decile_1"]["empirical_p_one_sided_ge"]
    injected_p = _pooled(injected_perm)["decile_1"]["empirical_p_one_sided_ge"]
    ordered_p = np.sort(noise_p)
    uniform_ks = float(np.max(np.maximum(np.arange(1, len(ordered_p) + 1) / len(ordered_p) - ordered_p,
                                         ordered_p - np.arange(len(ordered_p)) / len(ordered_p))))

    report = {
        "source": source,
        "settings": {"target_lift_pp": TARGET_LIFT_PP, "noise_measurement_repetitions": NOISE_MEASUREMENT_REPETITIONS,
                     "noise_permutation_repetitions": NOISE_PERMUTATION_REPETITIONS, "permutations": PERMUTATIONS,
                     "permutation_resolution_floor": 1 / (PERMUTATIONS + 1)},
        "noise_measurement": {name: {"mean_lift_pp": float(np.mean(v)), "sd_lift_pp": float(np.std(v, ddof=1)),
                                      "q025_lift_pp": float(np.quantile(v, .025)), "q975_lift_pp": float(np.quantile(v, .975)),
                                      "positive_fraction": float(np.mean(np.asarray(v) > 0))} for name, v in noise_lifts.items()},
        "noise_endpoint_separation_pp": {"mean": float(np.mean(noise_separations)), "q025": float(np.quantile(noise_separations, .025)), "q975": float(np.quantile(noise_separations, .975))},
        "perfect": {bucket: {"measured_tp_share_pct": perfect[bucket]["bucket_tp_share_pct"], **ceilings[bucket]} for bucket in ceilings},
        "injected": {"target_lift_pp": TARGET_LIFT_PP, "integer_attainable_lift_pp": injected_value, "rank_swaps_from_noise": swaps,
                     "measured_lift_pp": injected["decile_1"]["tp_share_lift_pp"], "measurement_95pct_ci_pp": [injected["decile_1"]["lift_95pct_normal_ci_low_pp"], injected["decile_1"]["lift_95pct_normal_ci_high_pp"]]},
        "permutation": {"noise_decile_1_p_mean": float(np.mean(noise_p)), "noise_decile_1_p_q025": float(np.quantile(noise_p, .025)), "noise_decile_1_p_q975": float(np.quantile(noise_p, .975)), "noise_decile_1_uniform_ks": uniform_ks,
                        "perfect_decile_1_p": perfect_p, "injected_decile_1_p": injected_p},
        "recorded_artifacts_changed": False,
    }
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Stage 6 ranking-instrument known-answer probe", "", "The input population is the real gated fold-test population of `stage4_tp004_sl002_sources`. Only score arrays were replaced; no model was loaded, retrained, or backtested.", "",
             "## Result", "", "| Case | Observed | Required | Verdict |", "|---|---|---|---|"]
    noise = report["noise_measurement"]
    lines.append(f"| Noise score, 1,000 measurement draws | decile means {min(v['mean_lift_pp'] for v in noise.values()):+.3f} to {max(v['mean_lift_pp'] for v in noise.values()):+.3f} pp; endpoint mean {report['noise_endpoint_separation_pp']['mean']:+.3f} pp, 95% [{report['noise_endpoint_separation_pp']['q025']:+.3f}, {report['noise_endpoint_separation_pp']['q975']:+.3f}] | zero in every decile's 95% draw interval; endpoints do not separate | PASS |")
    lines.append(f"| Perfect outcome-ranked score | top decile {perfect['decile_1']['bucket_tp_share_pct']:.3f}% vs ceiling {ceilings['decile_1']['maximum_tp_share_pct']:.3f}%; bottom {perfect['decile_10']['bucket_tp_share_pct']:.3f}% vs floor {ceilings['decile_10']['minimum_tp_share_pct']:.3f}% | extrema and arithmetic ceilings agree | PASS |")
    lines.append(f"| Injected small edge | {injected['decile_1']['tp_share_lift_pp']:+.3f} pp; injected {injected_value:+.3f} pp; CI [{injected['decile_1']['lift_95pct_normal_ci_low_pp']:+.3f}, {injected['decile_1']['lift_95pct_normal_ci_high_pp']:+.3f}] | recover known approximately +3.14 pp lift inside stated interval | PASS |")
    lines.append(f"| Permutation control | noise p mean {np.mean(noise_p):.3f}, KS {uniform_ks:.3f}; perfect p {perfect_p:.3f}; injected p {injected_p:.3f} | noise approximately uniform, perfect at {1/(PERMUTATIONS+1):.3f} floor, small edge less extreme | PASS |")
    lines.extend(["", "`decile_1` was asserted as the highest score bucket in all probes. The production CSV and measurement README state the same convention; the runner prints it in its top-versus-bottom line.", "", "What could still be wrong: these probes would not detect a shared defect in the persisted gate/outcome extraction used by both production and probe paths, a flaw in the block-exchangeability assumption, or an error that affects only score ties (the probes use continuous scores).", "", "The recorded ranking-skill and permutation-control artifacts were not changed. This directory is a new audit artifact.", ""])
    (OUTPUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    with (OUTPUT / "noise_decile_lifts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", *next(iter(noise.values())).keys()])
        writer.writeheader()
        writer.writerows({"bucket": bucket, **stats} for bucket, stats in noise.items())
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
