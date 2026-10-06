from __future__ import annotations

import numpy as np
import pandas as pd

from btcusdt_quant.paper import book, rules


def _exact(left: pd.DataFrame, right: pd.DataFrame, columns: list[str]) -> None:
    pd.testing.assert_frame_equal(left[columns].reset_index(drop=True),
                                  right[columns].reset_index(drop=True),
                                  check_exact=True, check_dtype=False)


def _base_trades(market: pd.DataFrame, features: pd.DataFrame, *, legacy: bool
                 ) -> dict[str, pd.DataFrame]:
    return {candidate: rules.make_trades(
                market, features, candidate,
                legacy_create_time_available=legacy)
            for candidate in (rules.F3, rules.E1, rules.F3_W30)}


def _books(base: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    result = {rules.F3: base[rules.F3], rules.F3_W30: base[rules.F3_W30]}
    for name, priority in {"C1": [rules.F3, rules.E1],
                           "C4": [rules.F3_W30, rules.E1]}.items():
        signals = pd.concat([base[candidate].assign(candidate=candidate)
                             for candidate in priority], ignore_index=True)
        result[name], _ = book.first_book(signals, priority)
    return result


def test_port_parity_uses_r2_35_plus5_exact() -> None:
    from out import run_k45_ls_ratio_timing_r2_35 as research

    historical_market, historical_features, historical_funding, market, features, funding = (
        research.load_inputs())
    historical = _books(_base_trades(historical_market, historical_features, legacy=False))
    end_price = float(market.close.iloc[-1])
    hold_base = {candidate: research.force_hold_a(frame, end_price)
                 for candidate, frame in _base_trades(market, features, legacy=False).items()}
    hold = _books(hold_base)
    expected = pd.read_parquet(
        "out/k45_ls_timing_adopt_r2_36_20261006/r2_35_plus5_trades.parquet")
    trade_columns = ["entry_time", "exit_time", "side", "entry_price", "exit_price",
                     "gross_bps", "cost_bps", "funding_bps", "net_bps", "hold_minutes"]
    for strategy in research.CANDIDATES:
        for segment in research.SEGMENTS:
            raw = hold[strategy] if segment == "HOLD_A" else historical[strategy]
            raw = research.selected_trades(raw, segment)
            segment_funding = funding if segment == "HOLD_A" else historical_funding
            for boundary in ("PESS", "OPT"):
                actual = book.reprice(raw, segment_funding, boundary)
                wanted = expected.loc[(expected.strategy == strategy) &
                                      (expected.segment == segment) &
                                      (expected.boundary == boundary)]
                _exact(actual, wanted, trade_columns)


def test_legacy_port_parity_preserves_r2_23_24_32_exact() -> None:
    from out import run_k45_ls_ratio_timing_r2_35 as research

    market, features, funding, all_market, all_features, all_funding = research.load_inputs()
    generated = _base_trades(market, features, legacy=True)
    expected = pd.read_parquet("out/k45_candidate_compare_r2_23_20261004/trades.parquet")
    trade_columns = ["entry_time", "exit_time", "side", "entry_price", "exit_price",
                     "gross_bps", "cost_bps", "funding_bps", "net_bps", "hold_minutes"]
    for candidate in (rules.F3, rules.E1, rules.F3_W30):
        for boundary in ("PESS", "OPT"):
            actual = book.reprice(generated[candidate], funding, boundary)
            wanted = expected.loc[(expected.candidate == candidate) &
                                  (expected.boundary == boundary)]
            _exact(actual, wanted, trade_columns)

    accepted = pd.read_parquet(
        "out/k45_single_book_combo_r2_24_20261004/accepted_trades.parquet")
    for combo, priority in {"C1": [rules.F3, rules.E1],
                            "C4": [rules.F3_W30, rules.E1]}.items():
        for boundary in ("PESS", "OPT"):
            signals = expected.loc[(expected.candidate.isin(priority)) &
                                   (expected.boundary == boundary)]
            actual, _ = book.first_book(signals, priority)
            wanted = accepted.loc[(accepted.combo == combo) & accepted.rule.eq("FIRST") &
                                  accepted.boundary.eq(boundary)]
            _exact(actual, wanted, ["candidate", "entry_time", "exit_time", "side",
                                    "entry_price", "exit_price"])

    start, end = research.SEGMENTS["HOLD_A"]
    end_price = float(all_market.close.iloc[-1])

    def window(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.loc[(frame.exit_time > start) & (frame.entry_time < end)].copy()
        force = result.exit_time > end
        result.loc[force, "exit_time"] = end
        result.loc[force, "exit_price"] = end_price
        result.loc[force, "gross_bps"] = (result.loc[force, "side"] * np.log(
            result.loc[force, "exit_price"] / result.loc[force, "entry_price"]) * 1e4)
        return result.reset_index(drop=True)

    base = {candidate: window(frame) for candidate, frame in
            _base_trades(all_market, all_features, legacy=True).items()}
    books = {"H1": base[rules.F3], "H2": base[rules.E1]}
    for name, priority in {"H3": [rules.F3, rules.E1],
                           "H5": [rules.F3_W30, rules.E1]}.items():
        signals = pd.concat([base[candidate].assign(candidate=candidate)
                             for candidate in priority], ignore_index=True)
        books[name], _ = book.first_book(signals, priority)
    expected = pd.read_parquet(
        "out/k45_hold_a_exclude_bookticker_r2_32_20261005/hold_a/trades.parquet")
    for name, raw in books.items():
        for boundary in ("PESS", "OPT"):
            actual = book.reprice(raw, all_funding, boundary)
            wanted = expected.loc[expected.book.eq(name) & expected.boundary.eq(boundary)]
            _exact(actual, wanted, trade_columns)


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
