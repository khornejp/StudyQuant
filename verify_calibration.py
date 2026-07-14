#!/usr/bin/env python3
"""Reliability check: do the side models' probabilities mean what they say?

The 2025 backtest entered at a mean probability of 0.522 and realized a 32.3%
win rate -- and on the long side, 0.522 stated against 16.7% realized. Every
consumer of that number is then wrong in the same direction: risk.expected_edge
sees an edge that is not there, risk.kelly_leverage_for_signal sizes the bet on
it, and training.select_threshold chose the entry cutoff assuming the number was
a probability. A learned threshold near 0.35 is itself a symptom -- the
probability mass is squashed into a narrow band, so the cutoff has to be dragged
down to find any bars at all.

Accuracy cannot show this (a monotone squash preserves the ranking and the
accuracy while destroying the probabilities), so this script scores the model
OUT OF SAMPLE and compares stated probability against realized frequency:

  - features come from dataset.build_feature_rows -- the same path training and
    live use, so a parity break shows up here rather than in production;
  - regimes come from the fitted detector INSIDE the artifact, so every bar is
    priced by the model that would actually have priced it (routing with a
    different detector would grade the wrong model);
  - labels come from dataset.attach_labels at the artifact's OWN recorded
    barrier (label_tp_pct / label_sl_pct). A side model answers exactly one
    question, "does price reach +tp before -sl within the horizon", so grading
    it against any other barrier grades it on a trade nobody trained it for.
    The script refuses rather than guess.

The verdict line is the decision band: on the bars the deployed threshold would
have entered, does the realized rate clear risk.breakeven_probability for this
barrier? Below it, the strategy cannot pay its costs at ANY threshold, and the
answer is a better model or a better barrier -- not more tuning.

Usage:
    python verify_calibration.py --input artifacts/btcusdt_2020_2025.parquet \\
        --model-dir artifacts/regime_stacking_model \\
        --start 2025-01-01 --end 2025-12-31 --horizon 60

Diagnostic only: exit code 0 with a report, 1 on unusable input. It does not
fail on a miscalibrated model -- read the report and decide.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from btcusdt_quant import backtest, calibration, dataset, live, risk

# Matches backtest.DEFAULT_ROUND_TRIP_COST_PCT (2 x (fee + slippage) per side).
# The break-even win rate is a function of the barrier AND the cost, so a
# report run with the wrong cost grades the model against the wrong hurdle.
DEFAULT_ROUND_TRIP_COST = backtest.DEFAULT_ROUND_TRIP_COST_PCT

# attach_labels needs a label_threshold for its `profitability` target. This
# script reads only long_success / short_success (the targets the side models
# are trained on), which the triple barrier decides without it.
_UNUSED_LABEL_THRESHOLD = 0.001


def _recorded_horizon(model_dir: Path) -> int | None:
    """The label horizon the artifact was trained on, or None if it predates the field.

    RegimeModelBundle carries the tp/sl barrier but not the time barrier, so it
    is read straight from the summary the bundle was loaded from.
    """
    try:
        summary = json.loads((model_dir / "regime_run_summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = summary.get("threshold_horizon")
    return None if value is None else int(value)


def _entered_sides(bundle: live.RegimeModelBundle, regime: str, features: dict[str, float]) -> list[str]:
    """The sides this bar could ACTUALLY be entered on, gated exactly as the backtest gates.

    Scoring every bar that has a side model would grade a population the
    strategy never trades: run_backtest first filters by the bundle's direction
    policy, then (in the range regime) by the mean-reversion gate, which only
    permits LONG near the bottom of the range and SHORT near the top and blocks
    entry entirely in the middle. Range is ~91% of 2025's bars, so ignoring that
    gate would inflate the decision band with bars that were never entered and
    measure its win rate on the wrong sample -- while the band is precisely the
    line the operator reads as the verdict.

    The reliability CURVE still wants every bar the model prices (it grades the
    model, not the policy); only the decision band is gated. See main().
    """
    allowed = (bundle.direction_policy or {}).get(regime, {"LONG", "SHORT"})
    allowed = backtest.apply_range_mean_reversion_gate(regime, features, set(allowed))
    return [
        side for side in ("long", "short")
        if side.upper() in allowed and bundle.has_side_probability(regime, side)
    ]


def _sides_present(bundle: live.RegimeModelBundle, regime: str) -> list[str]:
    return [side for side in ("long", "short") if bundle.has_side_probability(regime, side)]


def _threshold_for(bundle: live.RegimeModelBundle, regime: str, side: str) -> float | None:
    """The cutoff this regime/side would actually enter on, as saved at train time."""
    learned = (bundle.regime_thresholds or {}).get(regime) or {}
    value = learned.get(side)
    return None if value is None else float(value)


def _format_report(report: calibration.CalibrationReport) -> list[str]:
    lines = [
        f"    n={report.count:,}  mean_predicted={report.mean_predicted:.4f}  "
        f"observed={report.observed_rate:.4f}  overall_gap={report.overall_gap:+.4f}",
        f"    brier={report.brier:.4f}  ece={report.ece:.4f}",
        "    bin            n      predicted   observed        gap",
    ]
    for b in report.bins:
        if b.count == 0:
            continue
        flag = "  (thin)" if b.count < calibration.MIN_BIN_SAMPLES else ""
        lines.append(
            f"    [{b.lower:.1f},{b.upper:.1f})  {b.count:>8,}   {b.mean_predicted:>8.4f}   "
            f"{b.observed_rate:>8.4f}   {b.gap:>+8.4f}{flag}"
        )
    band = report.decision
    if band is not None:
        lines.append("")
        if band.count == 0:
            lines.append(
                f"    DECISION BAND (p >= {band.threshold:.4f}): no bars -- this side never enters. "
                f"The threshold is above everything the model outputs on the bars the entry policy allows."
            )
        else:
            verdict = "CLEARS break-even" if band.clears_breakeven else "BELOW break-even"
            lines.append(
                f"    DECISION BAND (p >= {band.threshold:.4f}): n={band.count:,} "
                f"({band.share_of_bars:.2%} of ENTERABLE bars)  predicted={band.mean_predicted:.4f}  "
                f"observed={band.observed_rate:.4f}"
            )
            lines.append(
                f"      break-even={band.breakeven_rate:.4f}  margin={band.margin:+.4f}  -> {verdict}"
            )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="path to candle Parquet or CSV")
    parser.add_argument("--model-dir", required=True, help="regime artifact dir (with regime_run_summary.json)")
    parser.add_argument("--start", default=None, help="scoring window start (YYYY-MM-DD), out of sample")
    parser.add_argument("--end", default=None, help="scoring window end (YYYY-MM-DD, inclusive)")
    parser.add_argument("--horizon", type=int, default=60, help="label time barrier in bars (must match training --horizon)")
    parser.add_argument("--round-trip-cost", type=float, default=DEFAULT_ROUND_TRIP_COST,
                        help="round-trip cost as a fraction; sets the break-even win rate")
    parser.add_argument("--bins", type=int, default=10, help="reliability curve bins over [0, 1]")
    parser.add_argument("--output", default=None, help="optional path for the JSON report")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"input not found: {input_path}")
        return 1

    bundle = live.load_regime_aware_models(Path(args.model_dir), strict=True)
    if bundle is None:
        print(f"no regime artifact at {args.model_dir}")
        return 1

    # The barrier is not a CLI option on purpose: it is a property of the
    # models on disk, and letting the operator pass a different one here is
    # exactly the silent mismatch check_execution_barrier_parity exists to stop.
    tp_pct, sl_pct = bundle.label_tp_pct, bundle.label_sl_pct
    if tp_pct is None or sl_pct is None:
        print(
            "this artifact does not record the barrier it was labeled on "
            "(label_tp_pct/label_sl_pct missing from regime_run_summary.json).\n"
            "Grading it would mean guessing which trade its probabilities describe. Retrain."
        )
        return 1

    # The TIME barrier is the third leg of the same triple barrier, and refusing
    # a tp/sl mismatch while trusting --horizon would leave the identical hole
    # open: labels built on 60 bars grade a model that answers about 90.
    recorded_horizon = _recorded_horizon(Path(args.model_dir))
    if recorded_horizon is None:
        print(
            f"WARNING: this artifact does not record the horizon its labels used; "
            f"grading against --horizon {args.horizon} on trust.",
            file=sys.stderr,
        )
    elif recorded_horizon != args.horizon:
        print(
            f"the models were labeled on a {recorded_horizon}-bar time barrier but --horizon is "
            f"{args.horizon}. Their probabilities answer a question about a different trade, so the\n"
            f"reliability curve would grade them on labels nobody trained them for. "
            f"Re-run with --horizon {recorded_horizon}."
        )
        return 1

    breakeven = risk.breakeven_probability(tp_pct, sl_pct, args.round_trip_cost)
    print(f"[CALIB] artifact={args.model_dir}")
    print(f"[CALIB] barrier: tp={tp_pct:.4%} sl={sl_pct:.4%}  horizon={args.horizon} bars  "
          f"round_trip_cost={args.round_trip_cost:.4%}")
    print(f"[CALIB] break-even win rate for this barrier: {breakeven:.4f}")

    candles = (
        dataset.load_parquet_candles(input_path)
        if input_path.suffix.lower() == ".parquet"
        else dataset.load_csv_candles(input_path)
    )
    print(f"[CALIB] {len(candles):,} candles loaded")

    feature_rows = dataset.build_feature_rows(candles)
    detector = bundle.multi_feature_regime_detector
    if detector is None:
        print(
            "this artifact carries no fitted rule detector, so there is no way to reproduce the\n"
            "bucketing its models were trained under. Routing with a different detector would grade\n"
            "the wrong model on each bar. Retrain with --multi-feature-regime."
        )
        return 1
    feature_rows, routing = backtest.apply_multi_feature_routing(
        feature_rows, detector, start_date=args.start, end_date=args.end
    )
    print(f"[CALIB] regime routing (artifact's own detector): {routing}")

    # The SAME bounds the backtest slices with, so the two reports grade the
    # same bars (an inclusive/exclusive end drift would silently compare
    # different samples).
    start, end = backtest.window_bounds(args.start, args.end)
    # Narrowed BEFORE labeling, not after: the triple barrier scans up to
    # `horizon` candles per row, and labeling all ~3.15M rows to keep 2025's
    # ~525k would spend ~6x the work on rows that are then discarded. row.index
    # still indexes the full candle list, so the labels are identical -- the
    # barrier can still walk forward out of the window, which is what it must do
    # for rows near the end.
    windowed = [
        row for row in feature_rows
        if (start is None or row.open_time >= start) and (end is None or row.open_time < end)
    ]

    # Labels look FORWARD by construction -- that is the target, not a leak.
    # The features behind each probability are strictly causal (build_feature_rows),
    # and attach_labels drops the tail whose barrier window runs past the data.
    scored = dataset.attach_labels(
        windowed, candles, horizon=args.horizon,
        label_threshold=_UNUSED_LABEL_THRESHOLD, tp_pct=tp_pct, sl_pct=sl_pct,
    )
    print(f"[CALIB] {len(scored):,} labeled rows in the scoring window")
    if not scored:
        print("no rows in the scoring window")
        return 1

    # Two streams per regime/side, and they are NOT the same population:
    #
    #   samples  -- every bar the model prices. This grades the MODEL, so it must
    #               not be filtered by the entry policy: a probability is either
    #               honest or it is not, whether or not the strategy acts on it.
    #   entered  -- only the bars run_backtest would actually enter (direction
    #               policy + range mean-reversion gate). This grades the TRADE,
    #               and the decision band must be measured here or it reports a
    #               win rate for bars nobody takes.
    #
    # Per regime/side rather than pooled, because each is a separate model:
    # pooling would average a well-calibrated regime with a broken one and report
    # neither.
    samples: dict[tuple[str, str], tuple[list[float], list[int]]] = {}
    entered: dict[tuple[str, str], tuple[list[float], list[int]]] = {}
    for row in scored:
        regime = row.user_regime
        if regime is None:
            continue
        tradeable = _entered_sides(bundle, regime, row.features)
        for side in _sides_present(bundle, regime):
            probability = bundle.probability_for(regime, side, row.features)
            if probability is None:
                continue
            outcome = int(row.targets[f"{side}_success"])
            probabilities, outcomes = samples.setdefault((regime, side), ([], []))
            probabilities.append(probability)
            outcomes.append(outcome)
            if side in tradeable:
                gated_probabilities, gated_outcomes = entered.setdefault((regime, side), ([], []))
                gated_probabilities.append(probability)
                gated_outcomes.append(outcome)

    payload: dict[str, object] = {
        "model_dir": str(args.model_dir),
        "window": {"start": args.start, "end": args.end},
        "horizon": args.horizon,
        "label_tp_pct": tp_pct,
        "label_sl_pct": sl_pct,
        "round_trip_cost": args.round_trip_cost,
        "breakeven_win_rate": breakeven,
        "regimes": {},
    }
    for (regime, side), (probabilities, outcomes) in sorted(samples.items()):
        threshold = _threshold_for(bundle, regime, side)
        # The curve over every priced bar; the band over the enterable ones only.
        report = calibration.reliability_curve(probabilities, outcomes, bin_count=args.bins)
        band = None
        if threshold is not None:
            gated_probabilities, gated_outcomes = entered.get((regime, side), ([], []))
            band = calibration.decision_band(
                gated_probabilities, gated_outcomes, threshold=threshold,
                tp_pct=tp_pct, sl_pct=sl_pct, round_trip_cost=args.round_trip_cost,
            )
            report = replace(report, decision=band)
        gated_count = 0 if band is None else len(entered.get((regime, side), ([], []))[0])
        print(f"\n  {regime}/{side}  (learned threshold: "
              f"{'none saved' if threshold is None else f'{threshold:.4f}'})")
        for line in _format_report(report):
            print(line)
        payload["regimes"].setdefault(regime, {})[side] = {
            "learned_threshold": threshold,
            # How many of the priced bars the entry policy even allows. When this
            # is far below `count`, the band speaks for a small corner of the
            # curve above it -- in range, the mean-reversion gate blocks the
            # middle of the range entirely.
            "enterable_bars": gated_count,
            **report.as_dict(),
        }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(backtest.json_safe(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\n[CALIB] report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
