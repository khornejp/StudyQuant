"""Measure OOS probability-ranking TP share for the four timeout-fixed arms."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from btcusdt_quant.ranking_skill import ArmSpec, measure_arm, write_csv


OUTPUT = Path("artifacts/ranking_skill_h45_tp004_timeoutfix_20260818")
ARMS = (
    ArmSpec("stage3_tp004_sl002", Path("artifacts/stage3_h45_tp004_sl002_q80_timeoutfix")),
    ArmSpec("stage3_tp004_sl004", Path("artifacts/stage3_h45_tp004_sl004_q80_timeoutfix")),
    ArmSpec("stage4_tp004_sl002_sources", Path("artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix")),
    ArmSpec("stage4_tp004_sl004_sources", Path("artifacts/stage4_h45_tp004_sl004_q80_sources_timeoutfix")),
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metrics, populations, sources = [], [], []
    for arm in ARMS:
        arm_metrics, arm_populations, source = measure_arm(arm)
        metrics.extend(arm_metrics)
        populations.extend(arm_populations)
        sources.append(source)
    write_csv(OUTPUT / "ranking_skill_by_bucket.csv", metrics)
    write_csv(OUTPUT / "gated_outcome_population.csv", populations)
    lines = [
        "# OOS ranking-skill measurement", "",
        "Strict realised TP is `payoff == +tp_pct`; timeout rows are the residual non-TP/non-SL rows and settle at their horizon close. No threshold or entry rule is used.", "",
        "`fold_test_predictions.csv` is the calculation input. `threshold_selection_inputs.npz` is validation-only threshold provenance, checked only for matching fold IDs and not joined to these test rows.", "",
        "The lift is bucket TP share minus the all-gated TP share, in percentage points. SE/CI are conditional-iid paired estimates: the selected bucket is contained in the base population. Pooled buckets rank within each fold before pooling.", "",
        "Probability-rank convention: `decile_1` is the highest-probability (top) decile and `decile_10` is the lowest-probability (bottom) decile. The `top_*_pct` buckets are likewise the highest-probability tails.", "",
        "## Top-versus-bottom decile contrast (pooled fold-local ranks)", "",
        "The figures below are each decile's lift versus the all-gated base; the final figure is top-minus-bottom TP-share separation. This is a rank-endpoint contrast, not a claim that every intervening decile is strictly monotone.", "",
    ]
    for arm in ARMS:
        pooled = {item["bucket"]: item for item in metrics if item["arm"] == arm.name and item["scope"] == "pooled_fold_local_ranks"}
        top, bottom = pooled["decile_1"], pooled["decile_10"]
        separation = top["bucket_tp_share_pct"] - bottom["bucket_tp_share_pct"]
        lines.extend([
            f"- `{arm.name}`: top (`decile_1`, highest probability) {top['tp_share_lift_pp']:+.3f} pp; "
            f"bottom (`decile_10`, lowest probability) {bottom['tp_share_lift_pp']:+.3f} pp; "
            f"top-minus-bottom separation {separation:+.3f} pp.", "",
            f"## {arm.name}", "", "| Scope | Bucket (probability rank; `decile_1` highest, `decile_10` lowest) | Base TP % | Bucket TP % | Lift pp | SE pp | 95% CI pp | n |", "|---|---|---:|---:|---:|---:|---:|---:|"])
        for row in (item for item in metrics if item["arm"] == arm.name):
            lines.append(
                f"| {row['scope']} | {row['bucket']} | {row['base_tp_share_pct']:.3f} | {row['bucket_tp_share_pct']:.3f} | "
                f"{row['tp_share_lift_pp']:.3f} | {row['lift_se_pp_conditional_iid']:.3f} | "
                f"[{row['lift_95pct_normal_ci_low_pp']:.3f}, {row['lift_95pct_normal_ci_high_pp']:.3f}] | {row['bucket_rows']:,} |"
            )
        lines.append("")
    lines.extend(["## Gated settlement population", "", "See `gated_outcome_population.csv` for TP, SL, timeout, and timeout horizon-close payoff counts by fold. No unresolved rows are in these fully labelled test artifacts. Short-side probabilities/payoffs are not stored in these four long-profitability artifacts, so no short-side ranking measure is available.", ""])
    (OUTPUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "OOS fold-test ranking measurement; no refit, backtest, threshold, or entry rule.",
        "input_roles": "fold_test_predictions.csv is the sole calculation input. threshold_selection_inputs.npz is validation-only threshold provenance and is not joined to test rows.",
        "outcome": "Strict realised TP: payoff exactly +tp_pct; non-TP/non-SL rows are horizon-close timeouts.",
        "uncertainty": "Conditional iid normal SE for selected TP share minus all-gated TP share; accounts for the selected subset being contained in the base. It does not claim independence across overlapping 45-bar outcomes.",
        "bucket_convention": "Descending probability rank within each fold: decile_1 is the highest-probability (top) decile and decile_10 is the lowest-probability (bottom) decile; top_*_pct are highest-probability tails.",
        "pooled_method": "Each fold is ranked locally before its same-percentile bucket is pooled, avoiding cross-fold probability-scale mixing.",
        "short_side": "Not available in these artifacts; each stores only long-side profitability probabilities and payoffs.",
        "sources": sources,
        "outputs": ["README.md", "ranking_skill_by_bucket.csv", "gated_outcome_population.csv"],
    }
    (OUTPUT / "provenance.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
