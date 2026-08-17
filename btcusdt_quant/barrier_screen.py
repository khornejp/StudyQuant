"""Training-only, provenance-captured triple-barrier geometry screen.

This deliberately calls ``dataset.triple_barrier_label_long`` for every
entry.  It does not duplicate the barrier walk: that is the production
long-label resolver, including its candle-direction same-bar tie rule.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import data, dataset, governance

# Exact historical geometry from the barrier root-cause screen.  In particular,
# 0.8% / 0.4% is the configuration whose 45-bar unresolved rate is being
# re-derived; the symmetric pairs distinguish reward:risk from barrier width.
DEFAULT_CANDIDATES = (
    (0.004, 0.002), (0.006, 0.003), (0.008, 0.004), (0.010, 0.005),
    (0.012, 0.006), (0.006, 0.006), (0.008, 0.008), (0.010, 0.010),
    (0.004, 0.004), (0.012, 0.012),
)
# This spans materially shorter and longer holds around the inherited 45 bars,
# while keeping enough spacing that the sweep is interpretable despite the
# increasing overlap between neighbouring labels at long horizons.
DEFAULT_HORIZONS = (15, 30, 45, 60, 90, 120, 180)
ROUND_TRIP_COST = 0.0004  # 4 bps: two 2-bps maker limit legs.
RECONCILIATION_CANDIDATE = (0.008, 0.004)


def parse_candidates(value: str | None) -> tuple[tuple[float, float], ...]:
    if value is None:
        return DEFAULT_CANDIDATES
    pairs = []
    for item in value.split(","):
        try:
            tp, sl = (float(x) for x in item.split(":"))
        except ValueError as exc:
            raise ValueError("--candidates must be comma-separated tp:sl fractions") from exc
        if tp <= 0 or sl <= 0:
            raise ValueError("candidate TP and SL must be positive")
        pairs.append((tp, sl))
    if not pairs:
        raise ValueError("--candidates cannot be empty")
    return tuple(pairs)


def parse_horizons(value: str) -> tuple[int, ...]:
    """Parse an explicit horizon list, or the recommended sweep sentinel."""
    if value == "default":
        return DEFAULT_HORIZONS
    try:
        horizons = tuple(int(item) for item in value.split(","))
    except ValueError as exc:
        raise ValueError("--horizons must be comma-separated positive integers") from exc
    if not horizons or any(horizon <= 0 for horizon in horizons):
        raise ValueError("--horizons must contain at least one positive integer")
    if len(set(horizons)) != len(horizons):
        raise ValueError("--horizons cannot contain duplicates")
    return horizons


def _slice(candles: Sequence[data.Candle], start: datetime | None, end: datetime | None) -> tuple[int, int]:
    lo, hi = 0, len(candles)
    while lo < hi and start is not None and candles[lo].open_time < start:
        lo += 1
    while hi > lo and end is not None and candles[hi - 1].open_time >= end:
        hi -= 1
    return lo, hi


def _gate_input_fingerprint(feature: str, lo: int, label_hi: int, values: Sequence[float]) -> str:
    """Hash the legacy compact JSON payload without building its values string.

    The update sequence is byte-for-byte equivalent to the previous
    ``json.dumps({...}, separators=(",", ":"))`` payload, so existing digest
    semantics remain stable while large gate vectors are streamed to SHA-256.
    """
    digest = hashlib.sha256()
    digest.update(b'{"feature":')
    digest.update(json.dumps(feature).encode("utf-8"))
    digest.update(b',"training_indices":[')
    digest.update(str(lo).encode("ascii"))
    digest.update(b",")
    digest.update(str(label_hi).encode("ascii"))
    digest.update(b'],"finite_values":[')
    for index, value in enumerate(values):
        if index:
            digest.update(b",")
        digest.update(json.dumps(value).encode("utf-8"))
    digest.update(b"]}")
    return digest.hexdigest()


def _outcome_counts(candles: Sequence[data.Candle], indices: Sequence[int], horizon: int,
                    tp: float, sl: float) -> tuple[int, int, int]:
    """Count production-label outcomes for one geometry and set of entry rows."""
    tp_count = sl_count = timeout_count = 0
    for index in indices:
        _, reason = dataset.triple_barrier_label_long(index, candles, horizon, tp, sl)
        if reason == "long_tp_first":
            tp_count += 1
        elif reason == "long_sl_first":
            sl_count += 1
        elif reason == "long_timeout":
            timeout_count += 1
        else:
            raise RuntimeError(f"unexpected production label reason: {reason}")
    return tp_count, sl_count, timeout_count


def screen(
    candles: Sequence[data.Candle], *, training_start: datetime | None,
    training_end: datetime | None, gate_feature: str, gate_quantile: float,
    horizon: int, candidates: Sequence[tuple[float, float]],
    _feature_rows: Sequence[object] | None = None,
) -> dict[str, object]:
    """Screen long barrier geometry without an (n, horizon) window matrix."""
    if not 0.0 <= gate_quantile < 1.0:
        raise ValueError("--gate-quantile must be in [0, 1)")
    if horizon <= 0:
        raise ValueError("--horizon must be positive")
    # Feature construction is one full-series pass so rolling gate values retain
    # pre-training warmup.  No feature cache is accepted or consulted here.
    rows = dataset.build_feature_rows(candles) if _feature_rows is None else _feature_rows
    lo, hi = _slice(candles, training_start, training_end)
    # Tail rows whose label walks beyond training-end are excluded: this is a
    # training-only screen, not a label that peeks into the evaluation period.
    label_hi = hi - horizon
    if label_hi <= lo:
        raise ValueError("training slice is shorter than --horizon")
    values = [float(rows[i].features[gate_feature]) for i in range(lo, label_hi)
              if gate_feature in rows[i].features and math.isfinite(float(rows[i].features[gate_feature]))]
    if not values:
        raise ValueError(f"no finite training values for gate feature {gate_feature!r}; no default is used")
    values.sort()
    cutoff = values[min(len(values) - 1, int(gate_quantile * len(values)))]
    gate_input_fingerprint = _gate_input_fingerprint(gate_feature, lo, label_hi, values)
    eligible = [i for i in range(lo, label_hi)
                if gate_feature in rows[i].features
                and math.isfinite(float(rows[i].features[gate_feature]))
                and float(rows[i].features[gate_feature]) >= cutoff]
    if not eligible:
        raise ValueError("volatility gate selected no training rows")
    results = []
    for tp, sl in candidates:
        tp_count = sl_count = timeout_count = 0
        payoffs: list[float] = []
        for index in eligible:
            # This is intentionally the production function, not an equivalent loop.
            label, reason = dataset.triple_barrier_label_long(index, candles, horizon, tp, sl)
            if reason == "long_tp_first":
                tp_count += 1; payoffs.append(tp - ROUND_TRIP_COST)
            elif reason == "long_sl_first":
                sl_count += 1; payoffs.append(-sl - ROUND_TRIP_COST)
            elif reason == "long_timeout":
                timeout_count += 1
                # A timeout exits at its horizon close, not at TP.  It remains
                # unresolved for resolved/tp_share but has an honest payoff.
                payoffs.append(candles[index + horizon].close / candles[index].close - 1.0 - ROUND_TRIP_COST)
            else:  # Defensive: the labeller's public contract must be exhaustive.
                raise RuntimeError(f"unexpected production label reason: {reason}")
        n = len(eligible)
        mean = sum(payoffs) / n
        std = math.sqrt(sum((p - mean) ** 2 for p in payoffs) / n)
        resolved_rows = tp_count + sl_count
        results.append({"tp_pct": tp, "sl_pct": sl, "screened_rows": n,
                        "resolved_share": resolved_rows / n,
                        "conditional_tp_share": tp_count / resolved_rows if resolved_rows else None,
                        "whole_population_tp_share": tp_count / n,
                        "unresolved_rows": timeout_count, "tp_rows": tp_count, "sl_rows": sl_count,
                        "random_walk_tp_share": sl / (tp + sl),
                        "break_even_tp_share": (sl + ROUND_TRIP_COST) / (tp + sl),
                        "payoff_mean_bps": mean * 10_000, "payoff_std_bps": std * 10_000})
    reconciliation_tp, reconciliation_sl, reconciliation_unresolved = _outcome_counts(
        candles, range(lo, label_hi), horizon, *RECONCILIATION_CANDIDATE,
    )
    reconciliation_total = reconciliation_tp + reconciliation_sl + reconciliation_unresolved
    gated_result = next((result for result in results
                          if (result["tp_pct"], result["sl_pct"]) == RECONCILIATION_CANDIDATE), None)
    return {"screen_type": "training_barrier_geometry", "direction": "long",
            "touch_resolver": "dataset.triple_barrier_label_long",
            "same_bar_tp_sl": "TP only when candle.close > candle.open; otherwise SL (including doji)",
            "round_trip_cost_bps": 4.0, "cost_assumption": "limit-only maker, both legs; no slippage or taker assumptions",
            "resolution_metrics_note": (
                "conditional_tp_share is TP rows divided by TP plus SL rows and is the primary skill comparison to "
                "break_even_tp_share. whole_population_tp_share retains timeouts in its denominator and is reported "
                "separately. Conditioning on resolution favors the nearer barrier under a time limit. In a horizon "
                "sweep that selection bias also changes as the time limit changes, so conditional_tp_share is not "
                "directly comparable across horizons without its resolved share and nearer-barrier geometry."
            ),
            "training_slice": {"start_index": lo, "end_index_exclusive": hi, "label_end_index_exclusive": label_hi,
                               "start": candles[lo].open_time.isoformat(), "end_exclusive": candles[hi - 1].open_time.isoformat()},
            "gate": {"feature": gate_feature, "quantile": gate_quantile, "cutoff": cutoff,
                     "input_fingerprint": gate_input_fingerprint,
                     "boundary_slice": "all finite training rows after horizon tail trim", "eligible_rows": len(eligible)},
            "candidate_source": "historical_default" if tuple(candidates) == DEFAULT_CANDIDATES else "custom",
            "candidate_sets": {
                "historical": [{"tp_pct": tp, "sl_pct": sl} for tp, sl in DEFAULT_CANDIDATES],
                "additions": [],
            },
            "candidates": [{"tp_pct": tp, "sl_pct": sl,
                            "category": "historical" if (tp, sl) in DEFAULT_CANDIDATES else "custom"}
                           for tp, sl in candidates], "results": results,
            "unresolved_reconciliation": {
                "tp_pct": RECONCILIATION_CANDIDATE[0], "sl_pct": RECONCILIATION_CANDIDATE[1],
                "horizon": horizon, "training_rows": reconciliation_total,
                "gate_off_unresolved_rows": reconciliation_unresolved,
                "gate_off_unresolved_share": reconciliation_unresolved / reconciliation_total,
                "gated_unresolved_share": gated_result["unresolved_rows"] / gated_result["screened_rows"]
                if gated_result is not None else None,
                "does_not_reconcile_stated_59pct": reconciliation_unresolved / reconciliation_total != 0.59,
                "comparison_note": (
                    "These are separate measurements on the same training span: the first has no rv_60 filter; "
                    "the second uses this report's volatility gate. They are reported without reconciling or drawing "
                    "a conclusion that any prior root-cause claim is confirmed or refuted."
                ),
            }}


def screen_horizons(
    candles: Sequence[data.Candle], *, training_start: datetime | None,
    training_end: datetime | None, gate_feature: str, gate_quantile: float,
    horizons: Sequence[int], candidates: Sequence[tuple[float, float]],
) -> dict[str, object]:
    """Run the existing training-only screen once per horizon.

    Features are constructed once, but each horizon derives its own tail-trimmed
    training/gate population and calls the production labeller for every entry.
    """
    if not horizons:
        raise ValueError("--horizons cannot be empty")
    rows = dataset.build_feature_rows(candles)
    reports = [screen(
        candles, training_start=training_start, training_end=training_end,
        gate_feature=gate_feature, gate_quantile=gate_quantile, horizon=horizon,
        candidates=candidates, _feature_rows=rows,
    ) for horizon in horizons]
    return {
        "screen_type": "training_barrier_horizon_sweep",
        "direction": "long",
        "touch_resolver": "dataset.triple_barrier_label_long",
        "horizons": list(horizons),
        "horizon_reports": reports,
        "cross_horizon_note": (
            "Every horizon has its own training-end tail trim and consequently its own gate population, cutoff, "
            "fingerprint, and eligible-row count. rv_60 itself is candle-only, but its measured quantile cutoff can "
            "change because the tail-trimmed population changes. Conditional TP share conditions on resolution; the "
            "nearer-barrier selection bias changes with the time limit, so compare it across horizons only alongside "
            "resolved share, whole-population TP share, and the fixed geometry."
        ),
    }


def run(input_path: Path, output: Path, **kwargs: object) -> dict[str, object]:
    candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
    horizons = kwargs.pop("horizons", None)
    if horizons is None:
        report = screen(candles, **kwargs)  # type: ignore[arg-type]
        resolved_config = {"input": str(input_path), **kwargs, "round_trip_cost": ROUND_TRIP_COST,
                           "gate_input_fingerprint": report["gate"]["input_fingerprint"]}
    else:
        report = screen_horizons(candles, horizons=horizons, **kwargs)  # type: ignore[arg-type]
        resolved_config = {
            "input": str(input_path), **kwargs, "horizons": horizons,
            "round_trip_cost": ROUND_TRIP_COST,
            "gate_input_fingerprints": [item["gate"]["input_fingerprint"] for item in report["horizon_reports"]],
        }
    provenance, diff = governance.capture_provenance(resolved_config=resolved_config, input_paths=(input_path,))
    report["provenance"] = provenance
    output.mkdir(parents=True, exist_ok=True)
    (output / "barrier_screen_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if diff is not None:
        (output / "source_diff.patch").write_text(diff, encoding="utf-8")
    return report
