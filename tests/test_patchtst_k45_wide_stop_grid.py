import numpy as np
import pandas as pd

from out import run_patchtst_k45_wide_stop_grid as run


def test_frozen_grid_plan_hash_and_zero_fit_contract():
    assert run.WIDE_LABELS == ("100", "200", "300", "500", "1000", "2000")
    assert len(run.ALL_LABELS) * len(run.audit.ARMS) * len(run.FILL_MODES) == 112
    assert run.FILL_MODES == ("touch", "gap", "late", "adverse_extreme")
    assert run.FIT_CALLS == 0
    assert run.audit.sha256(run.PLAN) == run.PLAN_HASH.read_text().split()[0]


def test_adverse_rows_reconstruct_log_and_linear_returns():
    touch = pd.DataFrame({
        "fill_mode": ["touch", "touch"], "position": [1, -1],
        "adverse_shadow_net_lin_bps": [-104.0, -204.0],
        "net_lin_bps": [0.0, 0.0], "gross_lin_bps": [0.0, 0.0],
        "gross_log_bps": [0.0, 0.0], "net_log_bps": [0.0, 0.0],
        "pnl_usd_100": [0.0, 0.0],
    })
    rows = run._adverse_rows(touch)
    assert rows.fill_mode.eq("adverse_extreme").all()
    assert rows.gross_lin_bps.tolist() == [-100.0, -200.0]
    assert np.allclose(rows.net_log_bps, [1e4 * np.log(.99) - 4, -1e4 * np.log(1.02) - 4])


def test_three_part_identity_reused_for_empty_added_and_dropped_sets():
    result = run.matched._decomposition(-1.0, None, 2.0, None, 4, 0, 0)
    assert result["full_difference_net_lin_bps"] == -3.0
    assert result["matched_contribution_bps"] == -3.0
    assert result["added_contribution_bps"] == 0.0
    assert result["dropped_contribution_bps"] == 0.0
    assert abs(result["reconstruction_residual_bps"]) <= 1e-12
