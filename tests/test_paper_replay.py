from __future__ import annotations

import pandas as pd

from btcusdt_quant.paper.config import PaperConfig
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.store import PaperStore


def test_q3_replay_exact_after_midpoint_restart(tmp_path) -> None:
    from out import k45_funding

    historical = pd.read_parquet("artifacts/btcusdt_2020_2026h1.parquet")
    q3 = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet")
    feature_columns = ["open_time", "global_ls_account"]
    features = pd.concat([
        pd.read_parquet(
            "artifacts/short_quantile_sweep_20260826/feature_cache/"
            "0fc9086b7d4b4c43c8b84f6f/feature_rows.parquet", columns=feature_columns),
        pd.read_parquet("artifacts/hold_a_2026q3/features_2026q3.parquet",
                        columns=feature_columns),
    ], ignore_index=True)
    historical_funding = k45_funding.load_settlements()
    q3_funding = pd.read_parquet("artifacts/hold_a_2026q3/funding_2026q3.parquet")
    path = tmp_path / "replay.sqlite"
    config = PaperConfig(books=("H1", "H2", "H3", "H5"), primary_book="H3",
                         start_time="2026-07-01T00:00:00Z", sqlite_path=str(path))
    midpoint = len(q3) // 2

    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        assert engine.process_replay_minutes(q3.iloc[:midpoint]) == midpoint
    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        # Duplicate proves idempotent resume after a durable midpoint checkpoint.
        assert engine.process_replay_minutes(q3.iloc[midpoint - 1:]) == len(q3) - midpoint
        for row in q3_funding.itertuples(index=False):
            engine.store_funding(row.funding_time, row.funding_rate)
        actual = engine.replay_books(
            "2026-07-01T00:00:00Z", "2026-10-01T00:00:00Z",
            features=features, history=historical, funding_history=historical_funding)

    corrected = pd.read_parquet(
        "out/k45_ls_timing_adopt_r2_36_20261006/r2_35_plus5_trades.parquet")
    corrected = corrected.loc[corrected.segment.eq("HOLD_A") &
                              corrected.strategy.isin(("F3|1h|10/24|signal|LS",
                                                       "C1", "C4"))].copy()
    corrected["book"] = corrected.strategy.map({
        "F3|1h|10/24|signal|LS": "H1", "C1": "H3", "C4": "H5"})
    corrected.loc[corrected.book.eq("H1"), "candidate"] = None
    legacy = pd.read_parquet(
        "out/k45_hold_a_exclude_bookticker_r2_32_20261005/hold_a/trades.parquet")
    expected = pd.concat([corrected, legacy.loc[legacy.book.eq("H2")]], ignore_index=True)
    columns = ["book", "boundary", "candidate", "entry_time", "exit_time", "side",
               "entry_price", "exit_price", "gross_bps", "cost_bps", "funding_bps",
               "net_bps", "hold_minutes"]
    wanted = expected.loc[expected.book.isin(("H1", "H2", "H3", "H5")), columns]
    left = actual[columns].sort_values(columns[:5], kind="stable").reset_index(drop=True)
    right = wanted.sort_values(columns[:5], kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, check_exact=True, check_dtype=False)
