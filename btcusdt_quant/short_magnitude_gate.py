"""Test magnitude inputs versus train-only volatility gates for the H15 short GRU."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .gru import SEQUENCE_LENGTH
from .short_direction import (
    SHORT_ORIENTED_FEATURE_NAMES,
    SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES,
    add_short_horizon_funding_features,
    add_short_oriented_features,
    add_signed_direction_features,
)
from .short_executable_ablation import HORIZON, _run_model, next_open_short_return
from .short_fast_regime import QUANTILES, add_fast_regime_features
from .short_sequence import COST, _status, _write_json, build_features


RUN_ROOT = Path("artifacts/short_magnitude_gate_20260907")
FEATURE_SETS = {
    "signed_30": tuple(SHORT_ORIENTED_FEATURE_NAMES),
    "signed_magnitude_35": tuple(SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES),
}
GATE_SPECS = {
    "rv15_train_q50": ("rv_15", 0.50),
    "rv15_train_q75": ("rv_15", 0.75),
    "atr14_train_q75": ("atr_pct", 0.75),
}


def run_experiment(
    input_path: Path,
    metrics_dir: Path,
    funding_dir: Path,
    premium_dir: Path,
    output: Path = RUN_ROOT,
    trials: int = 8,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing magnitude-gate directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding signed inputs and magnitude contexts")
        frame = add_short_oriented_features(add_short_horizon_funding_features(add_signed_direction_features(
            add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        )))
        gross = next_open_short_return(frame)
        common_names = tuple(dict.fromkeys((*FEATURE_SETS["signed_magnitude_35"], *(
            column for column, _ in GATE_SPECS.values()
        ))))
        common_finite = np.isfinite(frame.loc[:, list(common_names)]).all(axis=1) & np.isfinite(gross)
        valid = pd.Series(common_finite).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        results: dict[str, object] = {
            "designation": "posthoc_h15_signed_magnitude_and_gate_ablation",
            "live_approval_eligible": False,
            "target": {
                "name": "next_bar_open_to_h15_close_short_return_minus_4bps",
                "entry": "t_plus_1_open",
                "exit": "t_plus_15_close",
                "cost_bps": COST * 1e4,
            },
            "horizon": HORIZON,
            "sequence_length": SEQUENCE_LENGTH,
            "trials_per_fold": trials,
            "quantiles": list(QUANTILES),
            "trade_count_filter": None,
            "common_sample_across_feature_sets": True,
            "regime_direction_inputs": ["ema_gap_15m", "return_24h"],
            "regime_volatility_input": "rv_60",
            "external_gate_specs": {
                name: {"feature": feature, "train_quantile": quantile}
                for name, (feature, quantile) in GATE_SPECS.items()
            },
            "feature_sets": {name: list(features) for name, features in FEATURE_SETS.items()},
            "models": {},
        }
        for name, features in FEATURE_SETS.items():
            _status(output, "running", name, f"tuning H15 GRU with {name} and train-only gates")
            model_result = _run_model(
                frame, name, features, "gru", gross, valid, trials, output,
                gate_specs=GATE_SPECS,
            )
            results["models"][name] = model_result  # type: ignore[index]
            _write_json(output / f"{name}_gru.json", model_result)
        _write_json(output / "short_magnitude_gate_results.json", results)
        _status(output, "complete", "complete", "H15 magnitude and gate ablation completed")
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
    parser.add_argument("--trials", type=int, default=8)
    args = parser.parse_args(argv)
    run_experiment(
        args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir,
        output=args.output, trials=args.trials,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
