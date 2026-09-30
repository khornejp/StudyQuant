import pandas as pd

from out import run_patchtst_k45_account_target_stop_grid as run


def test_frozen_exact_grid_and_cell_counts():
    assert len(run.MAPPINGS) == 24
    assert run.TARGET_LABELS == (
        "46", "50", "96", "100", "196", "200", "329.333333333333",
        "333.333333333333", "396", "400", "496", "500",
        "662.666666666667", "666.666666666667", "996", "1000", "1996", "2000",
    )
    assert len(run.TARGET_LABELS) * len(run.audit.ARMS) * len(run.FILL_MODES) == 144
    assert len(run.MAPPINGS) * len(run.audit.ARMS) * len(run.FILL_MODES) == 192
    assert run.audit.sha256(run.PLAN) == run.PLAN_HASH.read_text().split()[0]
    assert run.FIT_CALLS == 0


def test_actual_funding_interval_and_arm_sign():
    rows = pd.DataFrame({
        "entry_time": pd.to_datetime(["2026-01-01 07:30Z", "2026-01-01 07:30Z"]),
        "exit_time": pd.to_datetime(["2026-01-01 08:15Z", "2026-01-01 08:15Z"]),
        "exit_time_exact": [True, True],
        "exit_bar_open_time": pd.to_datetime(["2026-01-01 08:14Z", "2026-01-01 08:14Z"]),
        "position": [1, -1], "net_lin_bps": [10.0, 10.0],
    })
    events = pd.DataFrame({
        "funding_time": pd.to_datetime(["2026-01-01 08:00Z"]),
        "funding_rate": [0.0001],
    })
    funded = run.attach_actual_funding(rows, events)
    assert funded.actual_funding_cost_bps.tolist() == [1.0, -1.0]
    assert funded.net_lin_bps_after_actual_funding.tolist() == [9.0, 11.0]


def test_mmr_threshold_formula_is_not_zero_cost():
    leverage, stop_bps, funding_bps = 10, 96, 0.1156
    stop = stop_bps / 1e4
    threshold = (1 / leverage - stop - (4 + funding_bps) / 1e4) / (1 - stop)
    assert round(threshold * 100, 4) == 9.0861
