from __future__ import annotations

from btcusdt_quant.paper import rules
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.engine import BOOKS


AX_BOOKS = ("C1_AX", "B1_AX", "B2_AX", "B3_AX", "K02_AX", "K03_AX", "K04_AX", "K05_AX", "K06_k0.5_AX",
            "K06_k1.0_AX", "K07_k0.5_AX", "K07_k1.0_AX", "K08_AX", "K09_AX", "K11_15m_AX", "K11_1h_AX", "K12_30m_AX",
            "K12_1h_AX", "K13_AX", "K14_AX", "K15_AX", "K19_AX", "K21_A_AX", "K21_B_AX", "K26_AX", "K29_AX", "K30_AX")


def test_live_config_is_the_committed_r2_52a_ax_switch() -> None:
    # config/paper.toml: the 27 R2-52A AX books (1ca5dd2), then C1_FLIP_AX appended at its own start time
    config = load_config("config/paper.toml")
    books = AX_BOOKS + ("C1_FLIP_AX",)
    assert config.books == books
    assert config.leverage_books == books and config.comparison_books == books[1:]
    assert config.telegram_books[-1] == "C1_FLIP_AX_x3"
    assert set(config.book_start_times) == set(books)
    assert {config.book_start_times[b] for b in AX_BOOKS} == {"2026-10-09T01:24:00Z"}
    assert config.book_start_times["C1_FLIP_AX"] == "2026-10-09T15:08:00Z"
    assert not {"C1", "C1_5m", "C1_T1"} & set(config.books)


def test_config_enables_comparison_book_without_overlay() -> None:
    # pre-switch behaviour (C1_5m comparison book without x3 overlay), kept on the recorded pre-R2-52A config
    config = load_config("config/paper.pre_r2_52a.toml")
    assert config.books[:8] == (
        "C1", "C1_FLIP", "C1_SL200", "C1_5m", "C1_T1", "F3", "E1", "C4")
    assert config.book_start_times.items() >= {
        "C1_5m": "2026-10-06T04:00:00Z", "C1_T1": "2026-10-06T05:00:00Z"}.items()
    assert config.comparison_books[:4] == ("C1_FLIP", "C1_SL200", "C1_5m", "C1_T1")
    assert config.leverage_books == ("C1", "F3", "E1", "C4")
    assert BOOKS["C1_5m"] == (rules.F3_5M, rules.E1)


def test_replay_before_comparison_book_t0_does_not_crash(tmp_path) -> None:
    # Live: C1_5m's own T0 is later than the global start; replays in between saw no trades.
    import pandas as pd
    from btcusdt_quant.paper.config import PaperConfig
    from btcusdt_quant.paper.engine import PaperEngine
    from btcusdt_quant.paper.store import PaperStore

    market = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet").iloc[:6 * 1440]
    config = PaperConfig(sqlite_path=str(tmp_path / "live.sqlite"), books=("C1", "C1_5m"),
                         start_time="2026-07-03T00:00:00Z",
                         book_start_times={"C1_5m": "2026-07-05T23:00:00Z"},
                         comparison_books=("C1_5m",))
    with PaperStore(config.sqlite_path) as store:
        engine = PaperEngine(store, config)
        engine.process_replay_minutes(market)
        engine.replay_books(config.start_time, "2026-07-05T00:00:00Z", publish_open_positions=True)
