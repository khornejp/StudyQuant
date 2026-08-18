"""Run a score-only, block-permutation control beside the ranking measurement."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from btcusdt_quant.ranking_permutation_control import BLOCK_ROWS, PERMUTATIONS, SEED, run_arm
from btcusdt_quant.ranking_skill import ArmSpec


INPUT = Path("artifacts/ranking_skill_h45_tp004_timeoutfix_20260818")
OUTPUT = Path("artifacts/ranking_score_permutation_control_h45_tp004_timeoutfix_20260818")
ARMS = (
    ArmSpec("stage3_tp004_sl002", Path("artifacts/stage3_h45_tp004_sl002_q80_timeoutfix")),
    ArmSpec("stage3_tp004_sl004", Path("artifacts/stage3_h45_tp004_sl004_q80_timeoutfix")),
    ArmSpec("stage4_tp004_sl002_sources", Path("artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix")),
    ArmSpec("stage4_tp004_sl004_sources", Path("artifacts/stage4_h45_tp004_sl004_q80_sources_timeoutfix")),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_rows, sources, arrays = [], [], {}
    for number, arm in enumerate(ARMS):
        rows, null, source = run_arm(arm, number)
        all_rows.extend(rows)
        sources.append(source)
        for scope, values in null.items():
            arrays[f"{arm.name}__{scope}"] = values
    _write_csv(OUTPUT / "permutation_null_summary.csv", all_rows)
    np.savez_compressed(OUTPUT / "permutation_null_draws.npz", **arrays)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Score-only block-permutation control for the persisted OOS ranking measurement; no refit, backtest, threshold selection, or trading-default change.",
        "input_measurement": str(INPUT / "ranking_skill_by_bucket.csv"),
        "input_measurement_sha256": _sha256(INPUT / "ranking_skill_by_bucket.csv"),
        "null_hypothesis": "Conditional on each persisted gated test fold's fixed TP outcomes, the probability-score time blocks have no association with those outcomes.",
        "permutation_unit": "Contiguous 45-row (45 one-minute-bar) blocks of probability scores, permuted independently within each arm and fold; internal score order within blocks is unchanged.",
        "why_blocked": "A global row shuffle would erase score serial structure while outcomes retain overlapping 45-bar dependence. Block reassignment keeps the score's local time structure and evaluates the same fold-local ranks against the fixed dependent outcome sequence.",
        "assumptions": "Exchangeability of score blocks within a fold under the null; 45 rows is the realised barrier horizon. Dependence extending beyond 45 rows is not fully preserved by this control.",
        "permutations": PERMUTATIONS,
        "tail_resolution": "The add-one empirical one-sided p-value has minimum resolution 1/(10000+1) ~= 0.00010. At the 2.5% and 97.5% null quantiles, binomial Monte Carlo CDF SE is about 0.00156, adequate for the reported 95% null interval.",
        "scope": "Both fold-level and pooled fold-local-rank statistics are reported. Pooled is the primary like-for-like comparison to the existing pooled measurement; fold-level results retain each arm's differing inverting-fold placement rather than averaging it away.",
        "selection_limits": "This control prices the specified tail/decile ranking rule conditional on fixed folds, gates, geometry, horizon, and persisted scores. It does not price the prior search or selection of geometry, gate, horizon, model, or arm, nor any decision to run or emphasize this measurement.",
        "sources": sources,
        "outputs": ["README.md", "permutation_null_summary.csv", "permutation_null_draws.npz", "provenance.json"],
    }
    (OUTPUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    tails = [r for r in all_rows if r["scope"] == "pooled_fold_local_ranks" and r["bucket"].startswith("top_")]
    lines = ["# Score-only block-permutation control", "", "This control preserves the original persisted OOS measurement's gates, folds, outcomes, fold-local ranking rule, top 1%/2%/5% tails, and deciles. It changes only the probability-score assignment.", "", "Scores are reassigned as contiguous 45-row blocks independently within each fold. This retains within-block score serial structure while leaving the fixed, overlapping-horizon outcome sequence intact. The one-sided empirical p-value is `(exceedances >= observed + 1) / 10001`.", "", "The null is conditional: it does **not** correct for the prior selection/search of geometry, gate, horizon, model, or arm. It only evaluates the tail/decile rule for those fixed choices.", "", "## Pooled fold-local tails", "", "| Arm | Tail | Observed lift pp | Null mean pp | Null SD pp | 95% null interval pp | p (null >= observed) |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in tails:
        lines.append(f"| {row['arm']} | {row['bucket']} | {row['observed_lift_pp']:.3f} | {row['null_mean_lift_pp']:.3f} | {row['null_sd_lift_pp']:.3f} | [{row['null_q025_lift_pp']:.3f}, {row['null_q975_lift_pp']:.3f}] | {row['empirical_p_one_sided_ge']:.5f} |")
    lines.extend(["", "Fold-level and decile results are in `permutation_null_summary.csv`; all reproducible null draws are in `permutation_null_draws.npz`.", ""])
    (OUTPUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
