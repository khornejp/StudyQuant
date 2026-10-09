"""C1_FLIP_AX paper book (Codex 2026-10-09): K01_FLIP source + C1_FLIP_AX_x3 overlay, k from r2_52a_flip/."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from btcusdt_quant.paper import catalog
from btcusdt_quant.paper.config import PaperConfig
from btcusdt_quant.paper.store import PaperStore
from tests.test_paper_ax import _ctx, _decisions, _fake_run_book, _store_with_minutes

ROOT = Path(__file__).resolve().parents[1]
CODE = re.compile(r"(?:\b[KBC]\d|F3|E1|_AX|_x3|\(3x\)|×3|x3|FLIP)")
NAME = "롱숏비율 극단 방향 추종 + 거래량 급증 상단 돌파 · 추세추종"
BOOKS = (*catalog.AX_BOOKS, "C1_FLIP_AX")
X3 = tuple(f"{n}_x3" for n in BOOKS)


def _k_file(path: Path, k: float = 1.0) -> Path:
    pd.DataFrame({"id": ["K01_FLIP"] * 2, "window": ["W10", "W11"],
                  "val_start": ["2025-09-01 00:00:00+00:00", "2025-12-01 00:00:00+00:00"],
                  "val_end": ["2025-12-01 00:00:00+00:00", "2026-03-01 00:00:00+00:00"], "k": [k, 2.0]}).to_csv(path, index=False)
    return path


def test_flip_book_maps_to_k01_flip_with_plain_korean_name() -> None:
    assert catalog.BOOKS["C1_FLIP_AX"] == ("K01_FLIP", False, "NATIVE") and catalog.needs_model("C1_FLIP_AX")
    assert catalog.FLIP_BOOKS == ("C1_FLIP_AX",) and catalog.FLIP_X3_BOOKS == ("C1_FLIP_AX_x3",)
    assert "C1_FLIP_AX" not in catalog.AX_BOOKS and len(catalog.AX_BOOKS) == 27     # frozen R2-52A rollout unchanged
    assert "C1_FLIP_AX" not in catalog.NAMES and len(catalog.NAMES) == 27
    assert catalog.label("C1_FLIP_AX") == catalog.label("C1_FLIP_AX_x3") == NAME
    assert not CODE.search(catalog.label("C1_FLIP_AX_x3"))
    assert catalog.FLIP_SELECTED_K == ROOT / "out/k45_rl_r2_48_20261007/r2_52a_flip/selected_k.csv"


def test_flip_k_comes_from_the_flip_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(catalog.K_SOURCES, "K01_FLIP", _k_file(tmp_path / "selected_k.csv", 1.5))
    assert catalog.book_k("K01_FLIP") == 1.5
    if catalog.SELECTED_K.exists():
        assert catalog.book_k("K01") == catalog.paper_k()["K01"]


def _config(path, start="2026-07-01T00:00:00Z"):
    return PaperConfig(books=BOOKS, primary_book="C1_AX", comparison_books=tuple(n for n in BOOKS if n != "C1_AX"),
                       leverage_books=BOOKS, telegram_books=X3, book_start_times={n: start for n in BOOKS},
                       start_time=start, retired_books=("C1", "C1_x3", "K09"), sqlite_path=str(path))


def test_catalog_cycle_with_flip_publishes_28_sources_and_28_x3(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    with PaperStore(path) as store:
        ctx = SimpleNamespace(minutes=market.assign(open_time=pd.to_datetime(market.open_time, utc=True)))
        monkeypatch.setattr(catalog, "run_book", _fake_run_book)
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        config = _config(path)
        assert paper_catalog.active_books(config) == list(BOOKS)
        assert paper_catalog.recompute_books(store, config, end, ctx, pd.DataFrame(columns=["time", "rate"]),
                                             with_signals=False) == 28
        assert set(store.frame("leverage_state").book) == set(X3)
        assert len(store.frame("leverage_trades").loc[lambda f: f.book.isin(X3)]) == 28
        assert set(store.frame("trades").book) == set(BOOKS)


def test_flip_book_never_enters_before_its_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(catalog.K_SOURCES, "K01_FLIP", _k_file(tmp_path / "selected_k.csv"))
    ctx, funding, predictions = _ctx(days=34)
    name = "C1_FLIP_AX"
    start = ctx.minutes.open_time.iloc[32 * 1440]
    end = ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    full = catalog.raw_table(name, ctx)
    assert ((full.side != 0) & (full.decision_time < start)).any()   # signals exist before the start
    decisions = _decisions(name, ctx, predictions, ctx.minutes.open_time.iloc[0], end)
    table = catalog.ax_table(name, ctx, decisions, start)
    assert len(table) and (table.decision_time >= start).all() and (table.k == 1.0).all()
    trades, _, held = catalog.run_book(name, ctx, funding, start, end, decisions)
    legs = trades.attrs["legs"]
    assert legs.empty or (legs.entry_time >= start).all()
    assert held is None or pd.Timestamp(held["entry_time"]) >= start
