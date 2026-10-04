from __future__ import annotations

import numpy as np
import pandas as pd

from out import k45_funding
from out import run_k45_candidate_compare_r2_23 as R


UTC = "UTC"


def test_selection_rules_read_dev_only():
    r17 = pd.DataFrame({
        "family": ["F3_global_ls_account"] * 4,
        "direction": ["LS"] * 4,
        "segment": ["DEV", "DEV", "HOLD_B", "HOLD_B"],
        "cell_id": ["a", "b", "a", "b"],
        "daily_sharpe": [1.0, 2.0, 999.0, -999.0],
    })
    assert R.select_candidate_3(r17).cell_id == "b"

    r20 = pd.DataFrame({
        "segment": ["DEV", "DEV", "HOLD_B", "HOLD_B"],
        "cell_id": ["a", "b", "a", "b"],
        "q": [.01, .02, .01, .02],
        "pw_ci95_lower": [1.0, 2.0, 999.0, -999.0],
    })
    assert R.select_candidate_10(r20).cell_id == "b"


def test_dev_common_boundary_split_uses_valuation_price():
    index = pd.date_range("2021-02-28 23:59", periods=4, freq="min", tz=UTC)
    closes = pd.Series([100.0, 110.0, 121.0, 121.0], index=index)
    trades = pd.DataFrame({
        "entry_time": [index[0]], "exit_time": [index[2]], "side": [1],
        "entry_price": [100.0], "exit_price": [121.0],
        "gross_bps": [np.log(1.21) * 1e4], "hold_minutes": [2.0],
    })
    empty_funding = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns, UTC]"),
                                  "rate": pd.Series([], dtype=float)})
    out = R.trade_segment_contributions(
        trades, closes, empty_funding,
        (pd.Timestamp("2021-03-01", tz=UTC), pd.Timestamp("2021-03-02", tz=UTC)),
        "PESS", 0.0,
    )
    # 00:00 minute P&L starts from the 23:59 valuation close.
    assert np.isclose(out.iloc[0], np.log(121 / 100) * 1e4)


def test_single_position_including_combo():
    ok = pd.DataFrame({
        "entry_time": pd.to_datetime(["2021-01-01 00:00Z", "2021-01-01 01:00Z"]),
        "exit_time": pd.to_datetime(["2021-01-01 01:00Z", "2021-01-01 02:00Z"]),
    })
    assert R.max_concurrent(ok) == 1
    bad = ok.copy()
    bad.loc[1, "entry_time"] = pd.Timestamp("2021-01-01 00:30Z")
    assert R.max_concurrent(bad) == 2


def test_pess_opt_same_trade_set_and_only_funding_differs():
    funding = pd.DataFrame({"time": pd.to_datetime(["2021-01-01 08:00Z"]),
                            "rate": [0.001]})
    base = pd.DataFrame({
        "entry_time": pd.to_datetime(["2021-01-01 08:00Z"]),
        "exit_time": pd.to_datetime(["2021-01-01 09:00Z"]),
        "side": [1], "entry_price": [100.0], "exit_price": [101.0],
    })
    pess = R.reprice_trades(base, funding, "PESS")
    opt = R.reprice_trades(base, funding, "OPT")
    R.verify_trade_set_parity(pess, opt)
    assert pess.funding_bps.iloc[0] == k45_funding.cashflow_bps(1, .001)
    assert opt.funding_bps.iloc[0] == 0.0


def test_reproduction_check_logic():
    assert R.reproduction_check(3, 10.0, 3, 10.0 + 1e-8)["match"]
    mismatch = R.reproduction_check(3, 10.0, 2, 10.0)
    assert not mismatch["match"]
    assert mismatch["cause_code"] == "N_MISMATCH"
