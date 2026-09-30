import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_k45_stop_grid_matched_decomposition as run


def test_exact_three_part_identity():
    result = run._decomposition(
        mu_s_m=-2.0, mu_s_a=-7.0, mu_n_m=1.0, mu_n_d=4.0,
        m=3, a=2, d=1,
    )
    assert result["stop_book_mean_net_lin_bps"] == pytest.approx(-4.0)
    assert result["none_book_mean_net_lin_bps"] == pytest.approx(1.75)
    assert result["full_difference_net_lin_bps"] == pytest.approx(-5.75)
    assert sum(result[key] for key in (
        "matched_contribution_bps", "added_contribution_bps",
        "dropped_contribution_bps")) == pytest.approx(-5.75)
    assert abs(result["reconstruction_residual_bps"]) <= 1e-12


def test_hac_is_built_from_paired_trade_differences():
    differences, inference = run.paired_hac(
        np.array([10.0, -4.0, 3.0]), np.array([7.0, -5.0, 8.0]),
        np.array([0, 1, 2]), np.arange(3),
    )
    assert differences.tolist() == [3.0, 1.0, -5.0]
    assert inference["estimate_bps"] == pytest.approx(-1 / 3)


def test_blocker_is_latest_accepted_none_trade():
    none = pd.DataFrame({
        "candidate_id": [1, 2], "entry_index": [10, 60], "exit_index": [55, 105],
    })
    added = pd.DataFrame({"candidate_id": [3, 4], "entry_index": [20, 90]})
    blockers = run._find_blockers(none, added)
    assert blockers.blocker_candidate_id.tolist() == [1, 2]
    assert blockers.blocker_hold_minutes.tolist() == [45, 45]
    assert blockers.blocker_remaining_minutes.tolist() == [35, 15]


def test_main_table_uses_adverse_width_for_status():
    rows = []
    for label in (*run.FINITE_LABELS, "none"):
        for arm in run.audit.ARMS:
            for fill in run.audit.FILL_MODES:
                rows.append({
                    "stop_label": label, "arm": arm, "fill_mode": fill,
                    "executed": True, "net_lin_bps": 0.0,
                    "adverse_shadow_net_lin_bps": -100.0 if label != "none" else 0.0,
                })
    table = run.main_table(pd.DataFrame(rows))
    assert len(table) == 48
    assert table.loc[table.stop_label.ne("none"), "measurement_status"].eq(
        "UNMEASURABLE").all()
    assert table.loc[table.stop_label.eq("none"), "measurement_status"].eq(
        "NOT_APPLICABLE").all()


def test_frozen_zero_fit_contract_and_plan_hash():
    assert run.FIT_CALLS == 0
    assert len(run.audit.STOP_LABELS) * len(run.audit.ARMS) * len(run.audit.FILL_MODES) == 48
    expected = run.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert run.audit.sha256(run.PLAN) == expected
