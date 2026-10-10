"""B3_AXC0 / K04_AXC0 paper books (user 2026-10-10): R2-55 AXC0 tables, causal guard, R2-55 W10 k, + x3 overlays."""
from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from btcusdt_quant.paper import catalog
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.store import PaperStore
from tests.test_paper_ax import _ctx, _decisions, _fake_run_book, _store_with_minutes

ROOT = Path(__file__).resolve().parents[1]
CODE = re.compile(r"(?:\b[KBC]\d|F3|E1|_AX|_x3|\(3x\)|×3|x3|AXC0)")
AXC0 = ("B3_AXC0", "K04_AXC0")
STAGED = ROOT / "config/paper.axc0_staged.toml"
T_ADD = "2026-10-10T12:00:00Z"


def _staged(tmp_path) -> Path:
    path = tmp_path / "paper.toml"
    path.write_text(STAGED.read_text(encoding="utf-8").replace("__T_ADD__", T_ADD), encoding="utf-8")
    return path


def test_axc0_books_map_to_b3_k04_with_r2_55_k_and_plain_korean_names() -> None:
    assert catalog.AXC0_BOOKS == AXC0 and catalog.AXC0_X3_BOOKS == ("B3_AXC0_x3", "K04_AXC0_x3")
    assert tuple(catalog.BOOKS)[-2:] == AXC0
    assert catalog.BOOKS["B3_AXC0"] == ("B3", False, "NATIVE") and catalog.BOOKS["K04_AXC0"] == ("K04", False, "NATIVE")
    assert all(catalog.needs_model(n) for n in AXC0)
    assert catalog.book_k("B3", axc0=True) == 1.0 and catalog.book_k("K04", axc0=True) == 2.0   # R2-55 W10
    assert catalog.book_k("B3") == catalog.paper_k()["B3"] and catalog.book_k("K04") == catalog.paper_k()["K04"]
    labels = [catalog.label(n) for n in (*catalog.BOOKS,)]
    assert len(set(labels)) == len(labels)
    for name in AXC0:
        assert catalog.label(name) == catalog.label(f"{name}_x3") and not CODE.search(catalog.label(name))


def test_axc0_table_has_the_fixed_breakout_level_and_its_own_cache() -> None:
    ctx, _, _ = _ctx(days=4)
    ax, c0 = catalog.raw_table("K04_AX", ctx), catalog.raw_table("K04_AXC0", ctx)
    assert ax.ax_exit_long.any() and not c0.ax_exit_long.any() and not c0.ax_exit_short.any()
    assert c0.anchor_upper.notna().any() and c0.anchor_lower.notna().any() and c0.anchor_price.notna().any()
    assert catalog.raw_table("K04_AX", ctx).equals(ax)                 # the AX book is unchanged by the AXC0 one
    b3 = catalog.raw_table("B3_AXC0", ctx)
    e1 = b3.component.eq(2)
    assert b3.loc[e1, "anchor_price"].notna().any() and b3.loc[~e1, "anchor_upper"].isna().all()


def test_axc0_run_book_uses_the_causal_guard_and_r2_55_k(monkeypatch) -> None:
    ctx, funding, predictions = _ctx(days=4)
    start, end = ctx.minutes.open_time.iloc[1440], ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    seen = {}
    simulate = catalog.core.simulate

    def spy(table, *args, **kwargs):
        seen[len(seen)] = (args[3].causal_guard, set(table.k))
        return simulate(table, *args, **kwargs)

    monkeypatch.setattr(catalog.core, "simulate", spy)
    for name in ("K04_AX", "K04_AXC0"):
        catalog.run_book(name, ctx, funding, start, end, _decisions(name, ctx, predictions, start, end))
    assert seen[0] == (False, {catalog.book_k("K04")}) and seen[1] == (True, {2.0})


def test_axc0_book_never_enters_before_its_start() -> None:
    ctx, funding, predictions = _ctx(days=34)
    start = ctx.minutes.open_time.iloc[32 * 1440]
    end = ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    for name in AXC0:
        full = catalog.raw_table(name, ctx)
        assert ((full.side != 0) & (full.decision_time < start)).any()
        trades, _, held = catalog.run_book(name, ctx, funding, start, end, _decisions(name, ctx, predictions,
                                                                                      ctx.minutes.open_time.iloc[0], end))
        legs = trades.attrs["legs"]
        assert legs.empty or (legs.entry_time >= start).all()
        assert held is None or pd.Timestamp(held["entry_time"]) >= start


def test_staged_config_is_the_live_config_plus_the_axc0_pair_last(tmp_path) -> None:
    live, staged = load_config(ROOT / "config/paper.toml"), load_config(_staged(tmp_path))
    base = live.books[:28]
    assert staged.books == base + AXC0 and staged.leverage_books == base + AXC0
    assert staged.comparison_books == base[1:] + AXC0
    assert staged.telegram_books == live.telegram_books[:28] + catalog.AXC0_X3_BOOKS
    assert {n: staged.book_start_times[n] for n in base} == {n: live.book_start_times[n] for n in base}
    assert {staged.book_start_times[n] for n in AXC0} == {T_ADD}
    assert (staged.primary_book, staged.start_time, staged.retired_books) == (live.primary_book, live.start_time,
                                                                              live.retired_books)
    with pytest.raises(ValueError):
        load_config(STAGED)                     # the placeholder can never be loaded as a live config


def test_catalog_cycle_with_axc0_publishes_30_sources_and_30_x3(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    config = load_config(_staged(tmp_path))
    config = replace(config, sqlite_path=str(path), book_start_times={n: "2026-07-01T00:00:00Z" for n in config.books},
                     start_time="2026-07-01T00:00:00Z")
    with PaperStore(path) as store:
        ctx = SimpleNamespace(minutes=market.assign(open_time=pd.to_datetime(market.open_time, utc=True)))
        monkeypatch.setattr(catalog, "run_book", _fake_run_book)
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        assert paper_catalog.recompute_books(store, config, end, ctx, pd.DataFrame(columns=["time", "rate"]),
                                             with_signals=False) == 30
        x3 = tuple(f"{n}_x3" for n in config.books)
        assert set(store.frame("leverage_state").book) == set(x3)
        assert set(store.frame("trades").book) == set(config.books)


SNAPSHOT = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot/manifest.json"


def test_parity_gate_rejects_extra_or_missing_positions() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_axc0_parity as parity
    t = pd.date_range("2026-10-01", periods=3, freq="h", tz="UTC")
    ref = pd.DataFrame({"entry_time": t[:2], "exit_time": t[1:], "side": [1, -1], "net_bps": [1.0, 2.0]})
    extra = pd.concat([ref, ref.iloc[[-1]]], ignore_index=True)
    assert parity.same(ref, ref)["match"] and not parity.same(extra, ref)["match"] and not parity.same(ref[:1], ref)["match"]


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="R2-54 FINAL snapshot (untracked out/) absent")
def test_snapshot_parity_source_and_x3_match_the_sim_for_both_books() -> None:
    """2026-10-01..10-08: full sim list == R2-56, paper closed == R2-56 closed, B3 open short 10-07 13:31 == the
    R2-56 data_end suffix, and the x3 overlay (paper_catalog._x3 -> simulate_book) == an independent 3x
    compounding of the sim legs (trades, funding, PnL, balance, open notional)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_axc0_parity as parity
    report = parity.run_all()
    for name in AXC0:
        book = report["books"][name]
        assert book["sim_vs_ref"]["match"] and book["paper_vs_ref"]["match"] and book["open_suffix"]["match"], name
        assert book["x3"]["match"] and book["x3"]["n"][0] == book["paper_vs_ref"]["n"][0] == 6, name
    assert report["books"]["B3_AXC0"]["sim_vs_ref"]["n"] == [7, 7]
    assert report["books"]["B3_AXC0"]["x3"]["open"]["entry_time"] == "2026-10-07 13:31:00+00:00"
    assert report["books"]["K04_AXC0"]["x3"]["open"] is None and report["match"]
