from __future__ import annotations

import pandas as pd

from btcusdt_quant.paper import book, rules
from btcusdt_quant.paper.config import PaperConfig, load_config
from btcusdt_quant.paper.engine import BOOKS, PaperEngine
from btcusdt_quant.paper.store import PaperStore


def _combo(market: pd.DataFrame, features: pd.DataFrame,
           decision_start: object | None = None) -> pd.DataFrame:
    parts = []
    for candidate in (rules.F3_5M, rules.E1):
        trades = rules.make_trades(
            market, features, candidate, decision_start=decision_start)
        parts.append(trades.assign(candidate=candidate))
    return book.first_book(pd.concat(parts, ignore_index=True),
                           [rules.F3_5M, rules.E1])[0]


def _reference(group: str) -> pd.DataFrame:
    frame = pd.read_parquet(
        "out/k45_decision_cadence_r2_37_20261006/trades.parquet",
        filters=[("strategy", "==", "C1"), ("variant", "==", "F_V5+E_V0"),
                 ("data_group", "==", group)])
    return frame.replace({"candidate": {"F3/V5": rules.F3_5M, "E1/V0": rules.E1}})


def _core(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["candidate", "entry_time", "exit_time", "side", "entry_price",
               "exit_price", "hold_minutes"]
    return frame[columns].reset_index(drop=True)


def test_config_enables_comparison_book_without_overlay() -> None:
    config = load_config("config/paper.toml")
    assert config.books == ("C1", "C1_5m", "F3", "E1", "C4")
    assert config.book_start_times == {"C1_5m": "2026-10-06T04:00:00Z"}
    assert config.comparison_books == ("C1_5m",)
    assert config.leverage_books == ("C1", "F3", "E1", "C4")
    assert BOOKS["C1_5m"] == (rules.F3_5M, rules.E1)


def test_r2_37_c1_v5_exact_and_q3_restart(tmp_path) -> None:
    from out import run_k45_decision_cadence_r2_37 as r237
    from out import run_k45_ls_ratio_timing_r2_35 as r235

    hist_market, _, hist_funding, all_market, all_features, all_funding = r235.load_inputs()
    for frame in (hist_market, all_market, all_features):
        frame["open_time"] = pd.to_datetime(frame.open_time, utc=True).astype(
            "datetime64[ns, UTC]")

    actual_history = _combo(hist_market, all_features)
    actual_all = _combo(all_market, all_features)
    pd.testing.assert_frame_equal(_core(actual_history), _core(_reference("HISTORY")),
                                  check_exact=True, check_dtype=False)
    pd.testing.assert_frame_equal(_core(actual_all), _core(_reference("THROUGH_HOLD_A")),
                                  check_exact=True, check_dtype=False)

    references = {"DEV_COMMON": (actual_history, hist_market, hist_funding),
                  "HOLD_B": (actual_history, hist_market, hist_funding),
                  "HOLD_A": (actual_all, all_market, all_funding)}
    for segment, (trades, market, funding) in references.items():
        start, end = r237.SEGMENTS[segment]
        expected = r237.force_window(trades, market, start, end)
        for boundary in ("PESS", "OPT"):
            left = book.reprice(expected, funding, boundary)
            right = book.reprice(r237.force_window(
                _reference("THROUGH_HOLD_A" if segment == "HOLD_A" else "HISTORY"),
                market, start, end), funding, boundary)
            columns = ["entry_time", "exit_time", "side", "entry_price", "exit_price",
                       "gross_bps", "cost_bps", "funding_bps", "net_bps", "hold_minutes"]
            pd.testing.assert_frame_equal(left[columns].reset_index(drop=True),
                                          right[columns].reset_index(drop=True),
                                          check_exact=True, check_dtype=False)

    q3 = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet")
    q3_funding = pd.read_parquet("artifacts/hold_a_2026q3/funding_2026q3.parquet")
    path = tmp_path / "restart.sqlite"
    start, end = r237.SEGMENTS["HOLD_A"]
    config = PaperConfig(
        books=("C1_5m",), primary_book="C1_5m", start_time=start.isoformat(),
        book_start_times={"C1_5m": start.isoformat()}, leverage_books=(),
        sqlite_path=str(path))
    midpoint = len(q3) // 2
    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        assert engine.process_replay_minutes(q3.iloc[:midpoint]) == midpoint
    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        assert engine.process_replay_minutes(q3.iloc[midpoint - 1:]) == len(q3) - midpoint
        for row in q3_funding.itertuples(index=False):
            engine.store_funding(row.funding_time, row.funding_rate)
        replayed = engine.replay_books(
            start, end, features=all_features, history=hist_market,
            funding_history=hist_funding)
        assert store.frame("leverage_state").empty
        assert store.frame("leverage_positions").empty
        assert store.frame("leverage_trades").empty

    expected_raw = r237.force_window(actual_all, all_market, start, end)
    expected = pd.concat([
        book.reprice(expected_raw, all_funding, boundary).assign(
            book="C1_5m", boundary=boundary)
        for boundary in ("PESS", "OPT")], ignore_index=True)
    columns = ["book", "boundary", "entry_time", "exit_time", "side", "entry_price",
               "exit_price", "gross_bps", "cost_bps", "funding_bps", "net_bps",
               "hold_minutes"]
    pd.testing.assert_frame_equal(replayed[columns].reset_index(drop=True),
                                  expected[columns].reset_index(drop=True),
                                  check_exact=True, check_dtype=False)
