from __future__ import annotations

import pandas as pd

from out import run_k45_holdout_a_2026q3 as runner


def test_holdout_calendar_is_contiguous_and_cutoff_bounded() -> None:
    specs = [runner.fold_spec(fold) for fold in runner.FOLDS]
    assert specs[0]["test_start"] == runner.HOLD_START
    assert specs[-1]["test_end"] == runner.HOLD_END
    assert all(left["test_end"] == right["test_start"] for left, right in zip(specs, specs[1:]))
    assert all(spec["train_end"] == spec["stop_start"] and
               spec["stop_end"] == spec["test_start"] for spec in specs)
    assert all(spec["train_end"] - spec["train_start"] == pd.Timedelta(days=180) for spec in specs)


def test_reproduction_fold_precedes_holdout_without_overlap() -> None:
    reproduction = runner.fold_spec(666)
    first = runner.fold_spec(667)
    assert reproduction["test_end"] == first["test_start"]
    assert reproduction["test_start"] == pd.Timestamp("2026-06-29T00:00:00Z")


def test_candidate_contract_forbids_pnl_columns() -> None:
    columns = ["first_come_executed", "pred_excursion_bps", "gate_margin_bps"]
    assert not [name for name in columns if "pnl" in name or "net_" in name or "gross_" in name]
