from __future__ import annotations

import numpy as np
import pandas as pd

from btcusdt_quant.paper import book, rules


def test_first_closes_before_same_minute_entry() -> None:
    times = pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 01:00Z",
                            "2026-01-01 01:00Z"])
    signals = pd.DataFrame({
        "entry_time": [times[0], times[1], times[2]],
        "exit_time": [times[1], times[1] + pd.Timedelta(hours=1),
                      times[2] + pd.Timedelta(hours=1)],
        "candidate": ["low", "low", "high"], "side": [1, 1, -1],
        "entry_price": [1.0] * 3, "exit_price": [1.0] * 3,
    })
    accepted, dropped = book.first_book(signals, ["high", "low"])
    assert accepted.candidate.tolist() == ["low", "high"]
    assert dropped.reason.tolist() == ["simultaneous"]


def test_archive_period_start_matches_rest_end_timestamp_at_strict_boundary() -> None:
    decisions = pd.DataFrame({"decision_time": pd.to_datetime([
        "2026-01-01 00:05Z", "2026-01-01 00:06Z"])})
    archive = pd.DataFrame({
        "open_time": pd.to_datetime(["2026-01-01 00:00Z"]),
        "global_ls_account": [1.25], "source": ["archive"]})
    rest = pd.DataFrame({
        "open_time": pd.to_datetime(["2026-01-01 00:05Z"]),
        "global_ls_account": [1.25], "source": ["rest"]})

    archive_values = rules._strict_prior_feature(decisions, archive, "global_ls_account")
    rest_values = rules._strict_prior_feature(decisions, rest, "global_ls_account")

    pd.testing.assert_series_equal(archive_values, rest_values)
    assert np.isnan(archive_values.iloc[0])
    assert archive_values.iloc[1] == 1.25
