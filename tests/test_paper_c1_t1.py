from __future__ import annotations

from pathlib import Path

import pandas as pd

from btcusdt_quant.paper import book, rules
from btcusdt_quant.paper.config import PaperConfig, load_config
from btcusdt_quant.paper.dashboard.server import BOOK_LABELS, CONDITION_BOOKS
from btcusdt_quant.paper.engine import BOOKS, EXECUTION_DELAYS, PaperEngine
from btcusdt_quant.paper.notify import format_message
from btcusdt_quant.paper.store import PaperStore


def _combo(market: pd.DataFrame, features: pd.DataFrame,
           decision_start: object | None = None) -> pd.DataFrame:
    return rules.make_first_trades(
        market, features, (rules.F3, rules.E1), decision_start=decision_start,
        execution_delay_minutes=1)


def _core(frame: pd.DataFrame, candidate: str = "candidate") -> pd.DataFrame:
    columns = [candidate, "entry_time", "exit_time", "side", "entry_price",
               "exit_price", "hold_minutes"]
    return frame[columns].rename(columns={candidate: "candidate"}).reset_index(drop=True)


def test_config_dashboard_and_notifications_expose_comparison_book() -> None:
    config = load_config("config/paper.toml")
    assert "C1_T1" in config.books
    assert config.book_start_times["C1_T1"] == "2026-10-06T05:00:00Z"
    assert "C1_T1" in config.comparison_books
    assert "C1_T1" not in config.leverage_books
    assert BOOKS["C1_T1"] == (rules.F3, rules.E1)
    assert EXECUTION_DELAYS["C1_T1"] == 1
    assert CONDITION_BOOKS["C1_T1"] == (rules.F3, rules.E1)
    assert BOOK_LABELS["C1_T1"] == "C1 T+1분 진입 (비교)"
    message = format_message("entry", {"book": "C1_T1", "side": -1, "price": 100,
                                        "candidate": "F3", "exit_time": "later"})
    assert message.startswith("🟢 [모의 진입 체결] BTCUSDT · C1_T1") and "방향 : SHORT" in message and "later" in message


def test_r2_39_c1_x_exact_and_q3_restart(tmp_path) -> None:
    from out import run_k45_decision_cadence_r2_37 as r237
    from out import run_k45_short_router_r2_39 as r239

    reference_path = Path("out/k45_short_router_r2_39_20261006/baseline_trades.parquet")
    assert reference_path.exists(), "R2-39 C1_X 산출물이 필요합니다"
    reference = pd.read_parquet(reference_path, filters=[("policy", "==", "C1_X")])
    reference = reference.rename(columns={"component": "candidate"})
    reference["candidate"] = reference.candidate.replace(
        {"F3": rules.F3, "E1": rules.E1})

    all_market = r239.load_market()
    all_features = r239.load_metrics().rename(
        columns={"create_time": "open_time", "global_ls": "global_ls_account"})
    all_features["source"] = "archive"
    all_funding = r239.load_funding()
    actual_all = _combo(all_market, all_features)
    pd.testing.assert_frame_equal(_core(actual_all), _core(reference),
                                  check_exact=True, check_dtype=False)
    priced = book.reprice(actual_all, all_funding, "PESS", cost_first=True)
    value_columns = ["gross_bps", "cost_bps", "funding_bps", "net_bps"]
    pd.testing.assert_frame_equal(priced[value_columns].reset_index(drop=True),
                                  reference[value_columns].reset_index(drop=True),
                                  check_exact=True, check_dtype=False)

    q3 = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet")
    q3_funding = pd.read_parquet("artifacts/hold_a_2026q3/funding_2026q3.parquet")
    start, end = r237.SEGMENTS["HOLD_A"]
    hist_market = all_market.loc[all_market.open_time.lt(start)]
    hist_funding = all_funding.loc[all_funding.time.lt(start)]
    path = tmp_path / "restart.sqlite"
    config = PaperConfig(
        books=("C1_T1",), primary_book="C1_T1", start_time=start.isoformat(),
        book_start_times={"C1_T1": start.isoformat()}, comparison_books=(),
        leverage_books=(), sqlite_path=str(path))
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

    expected_raw = r237.force_window(
        _combo(all_market, all_features, decision_start=start), all_market, start, end)
    expected = pd.concat([
        book.reprice(expected_raw, all_funding, boundary, cost_first=True).assign(
            book="C1_T1", boundary=boundary)
        for boundary in ("PESS", "OPT")], ignore_index=True)
    columns = ["book", "boundary", "candidate", "entry_time", "exit_time", "side",
               "entry_price", "exit_price", "gross_bps", "cost_bps", "funding_bps",
               "net_bps", "hold_minutes"]
    pd.testing.assert_frame_equal(replayed[columns].reset_index(drop=True),
                                  expected[columns].reset_index(drop=True),
                                  check_exact=True, check_dtype=False)
