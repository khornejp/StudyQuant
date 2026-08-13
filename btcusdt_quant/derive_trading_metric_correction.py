"""Derive an immutable correction report for a historical training artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping

from .training import summarise_fold_trading


_METRIC_KEYS = (
    "fold_count",
    "folds_without_eligible_rows",
    "long_net_bps_trade_weighted_mean",
    "short_net_bps_trade_weighted_mean",
    "long_net_bps_plain_fold_mean",
    "short_net_bps_plain_fold_mean",
    "long_trade_weighted_mean_folds_with_trades",
    "short_trade_weighted_mean_folds_with_trades",
    "long_plain_fold_mean_folds_with_trades",
    "short_plain_fold_mean_folds_with_trades",
    "long_folds_with_no_trades",
    "short_folds_with_no_trades",
    "long_profitable_trade_share",
    "short_profitable_trade_share",
    "long_trades_by_fold",
    "short_trades_by_fold",
    "long_net_bps_by_fold",
    "short_net_bps_by_fold",
)


def corrected_trading_metrics(block: Mapping[str, object]) -> dict[str, object]:
    """Re-aggregate only recorded fold measurements; never run a model."""
    folds = block.get("folds")
    if not isinstance(folds, list):
        raise ValueError("trading block has no recorded folds")
    summary = summarise_fold_trading(folds, label_horizon=block.get("label_horizon"))
    def json_value(value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, list):
            return [json_value(item) for item in value]
        return value

    return {key: json_value(summary[key]) for key in _METRIC_KEYS}


def derive(run_summary_path: Path, output_path: Path) -> dict[str, object]:
    raw = run_summary_path.read_bytes()
    run_summary = json.loads(raw)
    oos = run_summary.get("oos_trading")
    if not isinstance(oos, dict):
        raise ValueError("run summary has no oos_trading block")
    gated = oos.get("gated")
    if not isinstance(gated, dict):
        raise ValueError("run summary has no gated oos_trading block")
    payload = {
        "schema": "trade_weighted_metric_correction/v1",
        "derived_from": {
            "run_summary": str(run_summary_path),
            "run_summary_sha256": hashlib.sha256(raw).hexdigest(),
        },
        "reading_rule": {
            "primary": "*_net_bps_trade_weighted_mean",
            "descriptive_only": "*_net_bps_plain_fold_mean",
            "profitable_vote": "*_profitable_trade_share",
        },
        "ungated": corrected_trading_metrics(oos),
        "gated": corrected_trading_metrics(gated),
    }
    output_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    derive(args.run_summary, args.output)
    print(f"[METRIC-CORRECTION] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
