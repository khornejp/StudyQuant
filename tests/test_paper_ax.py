"""R2-52A Task D: AX paper books (27 hidden 1x sources + 27 visible x3 overlays), retirement, filtering."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper import catalog, leverage
from btcusdt_quant.paper.config import PaperConfig, load_config
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.notify import TelegramNotifier
from btcusdt_quant.paper.store import PaperStore

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json"
OUT_OK = FREEZE_PATH.exists() and catalog.SELECTED_K.exists()
# the untracked research outputs (freeze json, selected_k.csv) are needed by AX replay and the switch: skip, not fail
needs_out = pytest.mark.skipif(not OUT_OK, reason="untracked out/ freeze json or r2_52a/selected_k.csv absent")
ROLLOUT = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))["paper_rollout"] if OUT_OK else {}
NEW_BOOKS = catalog.AX_BOOKS
X3 = tuple(f"{name}_x3" for name in NEW_BOOKS)
CODE = re.compile(r"(?:\b[KBC]\d|F3|E1|_AX|_x3|\(3x\)|×3|x3)")
HEADS = ("30m", "1h", "4h", "12h", "24h")


# ---------------------------------------------------------------- configuration / names
@needs_out
def test_ax_books_are_exactly_the_frozen_27_sources() -> None:
    assert tuple(catalog.BOOKS) == tuple(ROLLOUT["new_books"]) == NEW_BOOKS and len(NEW_BOOKS) == 27
    assert catalog.BOOKS["C1_AX"] == ("K01", False, "NATIVE")
    assert all(catalog.BOOKS[n] == (n[:-3], False, "NATIVE") for n in NEW_BOOKS if n != "C1_AX")
    assert catalog.X3_BOOKS == X3
    assert all(catalog.needs_model(n) for n in NEW_BOOKS)           # AX is always model-dependent (E)


@needs_out
def test_plain_korean_names_without_codes_or_3x_suffix() -> None:
    names = ROLLOUT["presentation_addendum_2026-10-08"]["name_list"]
    assert catalog.NAMES == names                                    # verbatim from the freeze
    for source, x3 in zip(NEW_BOOKS, X3):
        assert catalog.label(x3) == names[source] == catalog.label(source)
        assert not CODE.search(catalog.label(x3)), catalog.label(x3)


@needs_out
def test_paper_k_is_the_last_validation_window_before_cutoff(tmp_path) -> None:
    path = tmp_path / "selected_k.csv"
    pd.DataFrame({"id": ["K02"] * 3, "window": ["W09", "W10", "W11"],
                  "val_start": ["2025-06-01 00:00:00+00:00", "2025-09-01 00:00:00+00:00", "2025-12-01 00:00:00+00:00"],
                  "val_end": ["2025-09-01 00:00:00+00:00", "2025-12-01 00:00:00+00:00", "2026-03-01 00:00:00+00:00"],
                  "k": [1.0, 1.5, 2.0]}).to_csv(path, index=False)
    assert catalog.paper_k(path) == {"K02": 1.5}
    real = catalog.paper_k()
    assert {spec for spec, _, _ in catalog.BOOKS.values()} <= set(real)
    assert real["K01"] == 1.5            # out/k45_rl_r2_48_20261007/r2_52a/selected_k.csv K01 W10


@needs_out
def test_switch_config_matches_the_freeze_configuration(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_ax_switch
    old = PaperConfig(books=("C1", "F3", "K09"), primary_book="C1", comparison_books=("K09",),
                      leverage_books=("C1",), sqlite_path=str(tmp_path / "x.sqlite"))
    switch = pd.Timestamp("2026-10-08T12:01:00Z")
    path = tmp_path / "paper.toml"
    path.write_text(paper_ax_switch.config_toml(old, switch, paper_ax_switch.retired_books(old)), encoding="utf-8")
    config = load_config(path)
    assert config.books == NEW_BOOKS and config.primary_book == "C1_AX"
    assert config.comparison_books == tuple(n for n in NEW_BOOKS if n != "C1_AX")
    assert config.leverage_books == NEW_BOOKS and config.telegram_books == X3
    assert config.book_start_times == {n: "2026-10-08T12:01:00Z" for n in NEW_BOOKS}
    assert config.retired_books == ("C1", "C1_x3", "F3", "K09")
    assert config.sqlite_path == old.sqlite_path


# ---------------------------------------------------------------- synthetic paper inputs
def _inputs(days: int = 6, seed: int = 0, e_bps: float = 60.0):
    t = pd.date_range("2026-07-01", periods=days * 24 * 60, freq="1min", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1.5e-3, len(t))))
    open_ = np.r_[close[0], close[:-1]]
    market = pd.DataFrame({"open_time": t, "open": open_, "high": np.maximum(open_, close) * 1.001,
                           "low": np.minimum(open_, close) * .999, "close": close,
                           "volume": rng.lognormal(0, 1, len(t)), "quote_volume": 1.0, "number_of_trades": 1,
                           "taker_buy_base_volume": rng.uniform(.2, .8, len(t))})
    five = t[::5]
    ls = pd.DataFrame({"open_time": five, "global_ls_account": 1.5 + np.cumsum(rng.normal(0, .02, len(five))),
                       "source": "archive"})
    premium = pd.DataFrame({"open_time": t, "premium_index": rng.normal(0, 1e-4, len(t))})
    funding = pd.DataFrame({"time": pd.date_range(t[0], t[-1], freq="8h"), "rate": 1e-4})
    grid = t[::15]
    predictions = pd.DataFrame({"timestamp": grid, "available_at": grid + pd.Timedelta(minutes=2),
                                "retrain_time": t[0], "model_id": "test", "source": "live"})
    for kind in ("range", "rv", "exc"):
        for head in HEADS:
            predictions[f"prediction_{kind}_{head}"] = e_bps * rng.uniform(.8, 1.2, len(grid))
    return market, ls, premium, funding, predictions


def _ctx(e_bps: float = 60.0, days: int = 6):
    market, ls, premium, funding, predictions = _inputs(days, e_bps=e_bps)
    return catalog.live_context(market, ls, premium, funding, predictions), funding, predictions


def _decisions(name, ctx, predictions, start, end):
    """Live decision events as the minute cycles would have recorded them (decided when first observable)."""
    table = catalog.raw_table(name, ctx)
    signals = pd.DatetimeIndex(table.loc[catalog._opens(table), "decision_time"].drop_duplicates())
    moments = signals.union(pd.DatetimeIndex(predictions.available_at)).sort_values()
    events, known = [], set()
    for now in moments[(moments >= start) & (moments < end)]:
        for event in catalog.decide(name, table, predictions, known, now, start):
            known.add(event["signal_time"].isoformat())
            events.append(event)
    return pd.DataFrame(events, columns=catalog.DECISION_COLUMNS)


# ---------------------------------------------------------------- AX source replay
@needs_out
def test_ax_e0_is_bound_causally_at_the_decision_time() -> None:
    ctx, _, predictions = _ctx()
    t = pd.DatetimeIndex(ctx.regime.timestamp)[200]
    frame = catalog.e_frame(ctx)
    assert (pd.DatetimeIndex(frame.timestamp).minute % 15 == 0).all()
    late = pd.DataFrame({"decision_time": [t, t + pd.Timedelta(minutes=2)]})
    e0 = catalog.row_e0(late, frame, "K02")
    before = frame.loc[frame.timestamp <= t - pd.Timedelta(minutes=15), "prediction_exc_4h"].iloc[-1]
    assert e0[0] == before                       # the prediction at t is not available before t + 2 min
    assert e0[1] == frame.loc[frame.timestamp == t, "prediction_exc_4h"].iloc[0]


@needs_out
def test_ax_book_has_no_max_hold_and_publishes_exit_phases() -> None:
    ctx, funding, predictions = _ctx()
    name = "K11_15m_AX"
    start, end = ctx.minutes.open_time.iloc[1440], ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    decisions = _decisions(name, ctx, predictions, start, end)
    trades, daily, held = catalog.run_book(name, ctx, funding, start, end, decisions)
    legs = trades.attrs["legs"]
    assert len(legs) > 3 and set(legs.exit_reason) <= {"stop", "trail", "state", "flag", "reverse"}
    assert set(trades.exit_reason) <= {"STOP", "TRAIL", "STATE", "FLAG", "REVERSE"}
    source = trades.attrs["source"]
    closed = source.loc[~source._active]
    assert set(closed.exit_phase) <= {"OPEN", "INTRAMINUTE_STOP", "CLOSE"} and closed.exit_reason.notna().all()
    opens = ctx.minutes.set_index("open_time").open
    at_open = closed.exit_phase.eq("OPEN")
    assert np.allclose(closed.loc[at_open, "exit_price"], opens.reindex(closed.loc[at_open, "exit_time"]))
    assert (closed.loc[closed.exit_phase.eq("INTRAMINUTE_STOP"), "exit_reason"].isin(["STOP", "TRAIL"])).all()
    if held is not None:
        assert held["k"] == catalog.paper_k()["K11_15m"] and held["r_bps"] <= held["r0_bps"] <= 300
        assert source._active.sum() == 1 and source._active.iloc[-1]
    pess = trades.loc[trades.boundary.eq("PESS")]
    assert np.isclose(daily.loc[daily.boundary.eq("PESS"), "net_bps"].sum(), pess.net_bps.sum())


@needs_out
def test_ax_book_without_e_never_enters() -> None:
    ctx, funding, predictions = _ctx(e_bps=np.nan)
    name = "K11_15m_AX"
    start, end = ctx.minutes.open_time.iloc[1440], ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    trades, _, held = catalog.run_book(name, ctx, funding, start, end, _decisions(name, ctx, predictions, start, end))
    assert trades.empty and held is None                    # NO_ENTRY_E, no fallback to native exits


# ---------------------------------------------------------------- catalog cycle (source + x3 together)
TABLES = ("trades", "daily_pnl", "positions", "signals", "leverage_state", "leverage_positions", "leverage_trades",
          "leverage_daily", "leverage_skips")


def _hash(store: PaperStore, books) -> dict:
    out = {}
    keep = sorted(books)
    for table in TABLES:
        frame = store.frame(table)
        if frame.empty:
            out[table] = (0, "")
            continue
        frame = frame.loc[frame.book.isin(keep)].drop(columns=[c for c in ("id",) if c in frame])
        if frame.empty:
            out[table] = (0, "")
            continue
        text = frame.sort_values(list(frame.columns)).to_csv(index=False)
        out[table] = (len(frame), hashlib.sha256(text.encode()).hexdigest())
    return out


def _retired_rows(store: PaperStore) -> None:
    store.insert("trades", {"book": "C1", "boundary": "PESS", "candidate": "F3", "side": 1,
                            "entry_time": "2026-07-02T00:00:00+00:00", "exit_time": "2026-07-02T01:00:00+00:00",
                            "entry_price": 100.0, "exit_price": 101.0, "gross_bps": 99.0, "cost_bps": 4.0,
                            "funding_bps": 0.0, "net_bps": 95.0, "hold_minutes": 60.0, "exit_reason": "MAX_HOLD"})
    store.upsert("positions", {"book": "K09", "side": 1, "candidate": "K09", "entry_time": "2026-07-02T00:00:00+00:00",
                               "entry_price": 100.0, "exit_time": "2026-07-02T04:00:00+00:00",
                               "remaining_minutes": 10, "unrealized_bps": 3.0, "updated_at": "2026-07-02T00:10:00+00:00"})
    store.upsert("leverage_state", {"book": "C1_x3", "source_book": "C1", "status": "RUNNING", "balance_usd": 101.0,
                                    "cumulative_pnl_usd": 1.0, "cumulative_return_pct": 1.0, "max_drawdown_usd": 0.0,
                                    "max_drawdown_pct": 0.0, "liquidated_at": None,
                                    "updated_at": "2026-07-02T00:10:00+00:00"})
    store.insert("leverage_trades", {"book": "C1_x3", "source_book": "C1", "candidate": "F3",
                                     "entry_time": "2026-07-02T00:00:00+00:00", "exit_time": "2026-07-02T01:00:00+00:00",
                                     "side": 1, "entry_price": 100.0, "exit_price": 101.0, "notional_usd": 300.0,
                                     "margin_usd": 100.0, "initial_liquidation_price": 67.0, "liquidation_price": 67.0,
                                     "max_adverse_pnl_usd": 0.0, "liquidated": 0, "gross_pnl_usd": 3.0, "cost_usd": .12,
                                     "funding_usd": 0.0, "pnl_usd": 2.88, "balance_before_usd": 100.0,
                                     "balance_after_usd": 102.88, "hold_minutes": 60.0, "exit_reason": "MAX_HOLD"})


def _fake_run_book(name, ctx, funding, start, end, decisions=None):
    entry = pd.Timestamp(start) + pd.Timedelta(minutes=5)
    exit_ = entry + pd.Timedelta(minutes=30)
    trades = pd.DataFrame([{"book": name, "boundary": b, "candidate": catalog.BOOKS[name][0], "entry_time": entry,
                            "exit_time": exit_, "side": 1, "entry_price": 100.0, "exit_price": 101.0,
                            "gross_bps": 99.5, "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": 95.5,
                            "hold_minutes": 30.0, "exit_reason": "TRAIL"} for b in ("PESS", "OPT")])
    trades.attrs["source"] = pd.DataFrame([{"entry_time": entry, "exit_time": exit_, "side": 1, "entry_price": 100.0,
                                            "exit_price": 101.0, "exit_reason": "TRAIL", "exit_phase": "INTRAMINUTE_STOP",
                                            "candidate": catalog.BOOKS[name][0], "_active": False}])
    trades.attrs["fills"] = pd.DataFrame([{"decision_time": entry - pd.Timedelta(minutes=1), "entry_time": entry,
                                           "side": 1, "entry_price": 100.0}])
    trades.attrs["legs"] = pd.DataFrame([{"position_id": 1, "entry_time": entry, "exit_time": exit_, "side": 1,
                                          "entry_price": 100.0, "exit_price": 101.0, "exit_reason": "trail"}])
    daily = pd.DataFrame([{"book": name, "boundary": "PESS", "date": entry.strftime("%Y-%m-%d"), "gross_bps": 99.5,
                           "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": 95.5}])
    return trades, daily, None


def _ax_config(path, start="2026-07-01T00:00:00Z", retired=("C1", "C1_x3", "K09")):
    return PaperConfig(books=NEW_BOOKS, primary_book="C1_AX",
                       comparison_books=tuple(n for n in NEW_BOOKS if n != "C1_AX"), leverage_books=NEW_BOOKS,
                       telegram_books=X3, book_start_times={n: start for n in NEW_BOOKS}, start_time=start,
                       retired_books=retired, sqlite_path=str(path))


def _store_with_minutes(path, days=1):
    market, *_ = _inputs(days)
    with PaperStore(path) as store:
        for row in market.to_dict("records"):
            row["open_time"] = row["open_time"].isoformat()
            store.upsert("klines_1m", {**row, "taker_buy_quote_volume": 0.0, "source": "archive",
                                       "received_at": row["open_time"], "closed": 1})
    return market


def test_catalog_cycle_publishes_27_sources_and_x3_and_preserves_retired_rows(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    with PaperStore(path) as store:
        _retired_rows(store)
        before = _hash(store, ("C1", "C1_x3", "K09"))
        ctx = SimpleNamespace(minutes=market.assign(open_time=pd.to_datetime(market.open_time, utc=True)))
        monkeypatch.setattr(catalog, "run_book", _fake_run_book)
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        config = _ax_config(path)
        for _ in range(2):                                       # a rewrite is idempotent
            assert paper_catalog.recompute_books(store, config, end, ctx, pd.DataFrame(columns=["time", "rate"]),
                                                 with_signals=False) == 27
        assert _hash(store, ("C1", "C1_x3", "K09")) == before
        state = store.frame("leverage_state")
        assert set(state.book) == {"C1_x3", *X3}
        x3 = store.frame("leverage_trades").loc[lambda f: f.book.isin(X3)]
        assert len(x3) == 27 and set(x3.exit_reason) == {"TRAIL"}
        assert set(store.frame("trades").book) == {"C1", *NEW_BOOKS}
        events = pd.read_sql_query("SELECT * FROM catalog_ax_events", store.connection)
        assert len(events) == 27 * 2 and set(events.event_type) == {"ENTRY", "EXIT"}


def test_engine_replay_with_ax_config_touches_no_rows(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    with PaperStore(path) as store:
        _retired_rows(store)
        before = _hash(store, ("C1", "C1_x3", "K09"))
        engine = PaperEngine(store, _ax_config(path))
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        engine.replay_books("2026-07-01T00:00:00Z", end, publish_open_positions=True)
        assert _hash(store, ("C1", "C1_x3", "K09")) == before


@needs_out
def test_all_27_real_ax_sources_create_x3(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    ctx, funding, predictions = _ctx(days=4)
    path = tmp_path / "live.sqlite"
    start = ctx.minutes.open_time.iloc[1440]
    end = ctx.minutes.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    config = _ax_config(path, start=start.isoformat().replace("+00:00", "Z"), retired=())
    with PaperStore(path) as store:
        decisions = pd.concat([_decisions(n, ctx, predictions, start, end) for n in NEW_BOOKS], ignore_index=True)
        store.connection.execute(paper_catalog.DECISION_TABLE)
        for e in decisions.to_dict("records"):
            store.connection.execute("INSERT INTO catalog_decisions VALUES (?,?,?,?,?,?,?,?)", tuple(
                None if pd.isna(e[c]) else (e[c].isoformat() if isinstance(e[c], pd.Timestamp) else e[c])
                for c in catalog.DECISION_COLUMNS))
        assert paper_catalog.recompute_books(store, config, end, ctx, funding, with_signals=False) == 27
        state = store.frame("leverage_state")
        assert set(state.book) == set(X3)
        positions = store.frame("positions")
        assert positions.exit_time.isna().all() and positions.remaining_minutes.isna().all()
        assert set(store.frame("leverage_positions").book) <= set(X3)


# ---------------------------------------------------------------- x3 overlay (leverage.simulate_book)
def _minutes(opens, lows, highs, closes, start="2026-01-01"):
    return pd.DataFrame({"open_time": pd.date_range(start, periods=len(lows), freq="min", tz="UTC"),
                         "open": opens, "low": lows, "high": highs, "close": closes})


def _source(exit_minute, price, reason="STOP", phase="INTRAMINUTE_STOP", side=1, active=False):
    return pd.DataFrame([{"entry_time": pd.Timestamp("2026-01-01T00:00Z"),
                          "exit_time": pd.Timestamp("2026-01-01T00:00Z") + pd.Timedelta(minutes=exit_minute),
                          "side": side, "entry_price": 100.0, "exit_price": price, "candidate": "K02",
                          "exit_reason": reason, "exit_phase": phase, "_active": active}])


NO_FUNDING = pd.DataFrame(columns=["time", "rate"])
T0, T9 = pd.Timestamp("2026-01-01T00:00Z"), pd.Timestamp("2026-01-01T00:09Z")


def test_x3_has_no_max_hold_and_active_source_stays_open() -> None:
    minutes = _minutes([100] * 6, [99] * 6, [101] * 6, [100.5] * 6)
    result = leverage.simulate_book(_source(6, 100.5, "ACTIVE", None, active=True), minutes, NO_FUNDING, "K02_AX",
                                    T0, T0 + pd.Timedelta(minutes=6))
    assert result.trades.empty and result.position is not None and result.state["status"] == "RUNNING"
    assert result.position["book"] == "K02_AX_x3"


def test_x3_preserves_source_exit_reason_and_requires_it() -> None:
    minutes = _minutes([100] * 4, [99] * 4, [101] * 4, [100] * 4)
    result = leverage.simulate_book(_source(2, 99.5, "STATE", "OPEN"), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert result.trades.exit_reason.tolist() == ["STATE"] and result.trades.exit_price.tolist() == [99.5]
    with pytest.raises(ValueError):
        leverage.simulate_book(_source(2, 99.5, None, "OPEN"), minutes, NO_FUNDING, "K02_AX", T0, T9)
    with pytest.raises(ValueError):
        leverage.simulate_book(_source(2, 99.5, "STATE", None), minutes, NO_FUNDING, "K02_AX", T0, T9)


def test_x3_open_gap_through_liquidation_beats_open_source_exit() -> None:
    minutes = _minutes([100, 60], [99, 59], [101, 61], [100, 60])
    result = leverage.simulate_book(_source(1, 60.0, "STOP", "OPEN"), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert result.trades.exit_reason.tolist() == ["LIQUIDATED"] and result.state["status"] == "LIQUIDATED"


def test_x3_intraminute_stop_before_liquidation_and_exact_tie_liquidates() -> None:
    liq = leverage.liquidation_price(100, 1, 100, 300, .004)
    minutes = _minutes([100, 99], [99, liq - 1], [101, 100], [100, 98])
    stop = leverage.simulate_book(_source(1, 97.0), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert stop.trades.exit_reason.tolist() == ["STOP"] and stop.state["status"] == "RUNNING"
    tie = leverage.simulate_book(_source(1, liq), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert tie.trades.exit_reason.tolist() == ["LIQUIDATED"]


def test_x3_funding_moved_liquidation_inside_the_stop_wins() -> None:
    funding = pd.DataFrame({"time": [pd.Timestamp("2026-01-01T00:01Z")], "rate": [.25]})   # long pays 75 USD
    liq = leverage.liquidation_price(100, 1, 100, 300, .004, -75.0)
    assert liq > 90
    minutes = _minutes([100, 99], [99, 89], [101, 100], [100, 90])
    result = leverage.simulate_book(_source(1, 90.0), minutes, funding, "K02_AX", T0, T9)
    assert result.trades.exit_reason.tolist() == ["LIQUIDATED"]


def test_x3_close_phase_tests_the_bar_before_the_close_exit() -> None:
    minutes = _minutes([100, 99], [99, 50], [101, 100], [100, 98])
    result = leverage.simulate_book(_source(1, 98.0, "DATA_END", "CLOSE"), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert result.trades.exit_reason.tolist() == ["LIQUIDATED"]


def test_x3_liquidation_stops_later_source_trades() -> None:
    first = _source(1, 60.0, "STOP", "OPEN")
    later = _source(3, 101.0, "TRAIL", "INTRAMINUTE_STOP").assign(entry_time=pd.Timestamp("2026-01-01T00:02Z"))
    minutes = _minutes([100, 60, 100, 100], [99, 59, 99, 99], [101, 61, 102, 102], [100, 60, 100, 100])
    result = leverage.simulate_book(pd.concat([first, later], ignore_index=True), minutes, NO_FUNDING, "K02_AX", T0, T9)
    assert result.trades.exit_reason.tolist() == ["LIQUIDATED"] and result.skips.reason.tolist() == ["LIQUIDATED"]
    assert result.state["balance_usd"] == 0 and result.position is None


def test_exit_phases_from_minute_open() -> None:
    minutes = _minutes([100, 99, 98], [99] * 3, [101] * 3, [99, 98, 97])
    trades = pd.DataFrame({"exit_time": pd.to_datetime(["2026-01-01T00:01Z", "2026-01-01T00:02Z",
                                                        "2026-01-01T00:03Z"]),
                           "exit_price": [99.0, 98.5, 97.0], "exit_reason": ["STATE", "STOP", "REPLAY_END"]})
    assert leverage.exit_phases(trades, minutes).tolist() == ["OPEN", "INTRAMINUTE_STOP", "CLOSE"]


# ---------------------------------------------------------------- dashboard
def _dashboard_store(path) -> None:
    with PaperStore(path) as store:
        store.set_meta("last_processed_minute", "2026-07-01T03:00:00+00:00")
        _retired_rows(store)
        for book in X3:
            liquidated = book == "K02_AX_x3"
            store.upsert("leverage_state", {"book": book, "source_book": book[:-3],
                                            "status": "LIQUIDATED" if liquidated else "RUNNING",
                                            "balance_usd": 0.0 if liquidated else 100.0,
                                            "cumulative_pnl_usd": -100.0 if liquidated else 0.0,
                                            "cumulative_return_pct": -100.0 if liquidated else 0.0,
                                            "max_drawdown_usd": 0.0, "max_drawdown_pct": 0.0,
                                            "liquidated_at": "2026-07-01T02:00:00+00:00" if liquidated else None,
                                            "updated_at": "2026-07-01T03:00:00+00:00"})
        store.upsert("positions", {"book": "C1_AX", "side": 1, "candidate": "K01",
                                   "entry_time": "2026-07-01T01:00:00+00:00", "entry_price": 100.0, "exit_time": None,
                                   "remaining_minutes": None, "unrealized_bps": 1.0,
                                   "updated_at": "2026-07-01T03:00:00+00:00"})
        store.upsert("leverage_positions", {"book": "C1_AX_x3", "source_book": "C1_AX", "side": 1, "candidate": "K01",
                                            "entry_time": "2026-07-01T01:00:00+00:00", "entry_price": 100.0,
                                            "mark_price": 100.1, "notional_usd": 300.0, "margin_usd": 100.0,
                                            "liquidation_price": 67.0, "liquidation_distance_pct": 33.0,
                                            "unrealized_pnl_usd": .3, "balance_usd": 100.0,
                                            "updated_at": "2026-07-01T03:00:00+00:00"})
        store.insert("trades", {"book": "C1_AX", "boundary": "PESS", "candidate": "K01", "side": 1,
                                "entry_time": "2026-07-01T00:10:00+00:00", "exit_time": "2026-07-01T00:40:00+00:00",
                                "entry_price": 100.0, "exit_price": 101.0, "gross_bps": 99.0, "cost_bps": 4.0,
                                "funding_bps": 0.0, "net_bps": 95.0, "hold_minutes": 30.0, "exit_reason": "TRAIL"})
        store.insert("leverage_trades", {"book": "K02_AX_x3", "source_book": "K02_AX", "candidate": "K02",
                                         "entry_time": "2026-07-01T01:00:00+00:00",
                                         "exit_time": "2026-07-01T02:00:00+00:00", "side": 1, "entry_price": 100.0,
                                         "exit_price": 67.0, "notional_usd": 300.0, "margin_usd": 100.0,
                                         "initial_liquidation_price": 67.0, "liquidation_price": 67.0,
                                         "max_adverse_pnl_usd": -100.0, "liquidated": 1, "gross_pnl_usd": -99.9,
                                         "cost_usd": .06, "funding_usd": 0.0, "pnl_usd": -100.0,
                                         "balance_before_usd": 100.0, "balance_after_usd": 0.0, "hold_minutes": 60.0,
                                         "exit_reason": "LIQUIDATED"})


def _serve(path, tmp_path):
    from btcusdt_quant.paper.dashboard import make_server
    server = make_server(path, tmp_path, port=0, books=NEW_BOOKS, start_time="2026-07-01T00:00:00Z",
                         book_start_times={n: "2026-07-01T00:00:00Z" for n in NEW_BOOKS}, leverage_books=NEW_BOOKS,
                         primary_book="C1_AX")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _get(base, route):
    with urllib.request.urlopen(base + route, timeout=20) as response:
        return json.load(response)


def test_dashboard_exposes_only_the_27_x3_books_with_plain_names(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "live.sqlite"
    _dashboard_store(path)
    server, base = _serve(path, tmp_path)
    try:
        books = _get(base, "/api/books")
        assert [r["book"] for r in books["rows"]] == list(X3) and books["default_book"] == "C1_AX_x3"
        for row in books["rows"]:
            assert row["display_book"] == catalog.NAMES[row["book"][:-3]] and not CODE.search(row["display_book"])
        liquidated = next(r for r in books["rows"] if r["book"] == "K02_AX_x3")
        assert liquidated["status"] == "LIQUIDATED" and liquidated["balance_usd"] == 0 and liquidated["position"] is None
        positions = _get(base, "/api/positions")["rows"]
        assert [r["book"] for r in positions] == ["C1_AX_x3"]               # hidden 1x source and retired rows absent
        trades = _get(base, "/api/trades")["rows"]
        assert [r["book"] for r in trades] == ["K02_AX_x3"]
        assert _get(base, "/api/signals")["rows"] == []
        assert _get(base, "/api/summary")["books"] == ["K02_AX_x3"]
        for hidden in ("C1_AX", "C1", "C1_x3"):
            with pytest.raises(urllib.error.HTTPError):
                _get(base, f"/api/performance?book={hidden}")
        perf = _get(base, "/api/performance?book=K02_AX_x3")
        assert perf["summary"]["status"] == "LIQUIDATED" and perf["summary"]["balance_usd"] == 0
        conditions = _get(base, "/api/conditions?book=K02_AX_x3&tf=1h")
        assert conditions["book"] == "K02_AX_x3" and "내부 원천" in conditions["summary"]["note"]
        html = urllib.request.urlopen(base + "/").read().decode("utf-8")
        assert "<option>C1</option>" not in html and "default_book" in html
    finally:
        server.shutdown(); server.server_close()


# ---------------------------------------------------------------- Telegram
def _secrets(tmp_path):
    path = tmp_path / "telegram-secrets.txt"
    path.write_text("TELEGRAM_BOT_TOKEN=token-abcdefgh-12345678\nTELEGRAM_CHAT_ID=123456\n", encoding="utf-8")
    return path


def _x3_trade(store, book, entry, exit_, pnl=3.0, reason="TRAIL", liquidated=0):
    store.insert("leverage_trades", {"book": book, "source_book": book[:-3], "candidate": "K", "entry_time": entry,
                                     "exit_time": exit_, "side": 1, "entry_price": 100.0, "exit_price": 101.0,
                                     "notional_usd": 300.0, "margin_usd": 100.0, "initial_liquidation_price": 67.0,
                                     "liquidation_price": 67.0, "max_adverse_pnl_usd": 0.0, "liquidated": liquidated,
                                     "gross_pnl_usd": pnl, "cost_usd": .12, "funding_usd": 0.0, "pnl_usd": pnl,
                                     "balance_before_usd": 100.0, "balance_after_usd": 100.0 + pnl,
                                     "hold_minutes": 0.0, "exit_reason": reason})


def test_telegram_sends_only_x3_events_and_same_minute_x3_entries(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    _dashboard_store(path)
    minute = "2026-07-01T03:00:00+00:00"
    with PaperStore(path) as store:
        _x3_trade(store, "K03_AX_x3", minute, minute)                       # entered and closed in the same minute
        _x3_trade(store, "C1_x3", "2026-07-01T03:00:00+00:00", "2026-07-01T03:01:00+00:00", reason="MIGRATION_END")
        store.upsert("positions", {"book": "K04_AX", "side": -1, "candidate": "K04", "entry_time": minute,
                                   "entry_price": 100.0, "exit_time": None, "remaining_minutes": None,
                                   "unrealized_bps": 0.0, "updated_at": minute})
    notifier = TelegramNotifier(path, _ax_config(path), env_path=_secrets(tmp_path))
    notifier.publish_store_events()
    with PaperStore(path) as store:
        rows = store.frame("notifications")
    books = {key.split(":")[1] for key in rows.event_key}
    assert books <= set(X3) and {"K03_AX_x3", "K02_AX_x3", "C1_AX_x3"} <= books
    assert rows.event_key.str.startswith("entry:K03_AX_x3:").sum() == 1
    assert not rows.payload.str.contains("MIGRATION_END|_AX|_x3").any()
    assert rows.payload.str.contains(catalog.NAMES["K03_AX"], regex=False).any()
    # a liquidated book receives no later events
    assert not rows.event_key.str.contains("K02_AX_x3").loc[rows.event_type.eq("distance_warning")].any()


def test_daily_summary_has_only_x3_usd_rows_of_books_that_closed_a_trade(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        _x3_trade(store, "K03_AX_x3", "2026-07-01T03:00:00+00:00", "2026-07-01T04:00:00+00:00", pnl=6.0)
        _x3_trade(store, "C1_x3", "2026-07-01T03:00:00+00:00", "2026-07-01T05:00:00+00:00", reason="MIGRATION_END")
        for book in ("K03_AX_x3", "K05_AX_x3"):
            store.upsert("leverage_daily", {"book": book, "date": "2026-07-01", "balance_usd": 106.0,
                                            "day_pnl_usd": 6.0, "max_drawdown_usd": 0.0, "max_drawdown_pct": 0.0})
        store.upsert("daily_pnl", {"book": "K03_AX", "boundary": "PESS", "date": "2026-07-01", "gross_bps": 5.0,
                                   "cost_bps": 0.0, "funding_bps": 0.0, "net_bps": 5.0})
    notifier = TelegramNotifier(path, _ax_config(path), env_path=_secrets(tmp_path))
    assert notifier.publish_daily_summary("2026-07-01")
    assert notifier.publish_daily_summary("2026-07-02")
    with PaperStore(path) as store:
        payloads = store.frame("notifications").set_index("event_key").payload
    day = payloads["daily:2026-07-01"]
    assert catalog.NAMES["K03_AX"] in day and "+6.00 USD" in day and "bps" not in day
    assert catalog.NAMES["K05_AX"] not in day and "C1" not in day
    assert "2. " not in day
    assert "완료 거래 : 0회" in payloads["daily:2026-07-02"]


def test_telegram_delivery_is_paced_fifo_and_honours_429(tmp_path, monkeypatch) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    notifier = TelegramNotifier(path, env_path=_secrets(tmp_path))
    for k in range(3):
        notifier.enqueue(f"alert:{k}", "alert", {"kind": "x", "detail": str(k)})
    clock = {"now": 0.0}
    sleeps, sent = [], []
    notifier._clock = lambda: clock["now"]
    notifier._sleep = lambda s: (sleeps.append(s), clock.__setitem__("now", clock["now"] + s))

    class Response:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {"ok": False, "error_code": 429, "parameters": {"retry_after": 7}} if self.status_code == 429 \
                else {"ok": True}

    codes = iter([200, 429])
    monkeypatch.setattr("btcusdt_quant.paper.notify.requests.post",
                        lambda *a, **k: (sent.append(k["data"]["text"]), Response(next(codes)))[1])
    now = pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=1)
    assert notifier.deliver_pending(now) == 1
    assert sleeps == [1.0] and len(sent) == 2                    # 1 request per second, FIFO stops at the 429
    with PaperStore(path) as store:
        rows = store.frame("notifications").sort_values("id")
    assert rows.status.tolist() == ["sent", "failed", "pending"]
    assert pd.Timestamp(rows.next_attempt_at.iloc[1]) == now + pd.Timedelta(seconds=7)
    codes = iter([200, 200])
    assert notifier.deliver_pending(now + pd.Timedelta(seconds=1)) == 0     # third waits behind the throttled head
    assert notifier.deliver_pending(now + pd.Timedelta(seconds=8)) == 2


# ---------------------------------------------------------------- retirement (MIGRATION_END)
def _switch_db(tmp_path, x3_entry=100.0):
    """A pre-switch DB: open retired 1x C1 and DETEXIT half K09_D (TAKE already booked) and an open C1_x3."""
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    switch = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    with PaperStore(path) as store:
        store.set_meta("last_processed_minute", market.open_time.iloc[-1].isoformat())
        mark = np.log(market.close.iloc[-1] / 100.0) * 1e4
        for name, units in (("C1", 1.0), ("K09_D", 0.5)):          # a DETEXIT half position
            store.upsert("positions", {"book": name, "side": 1, "candidate": "F3",
                                       "entry_time": "2026-07-01T12:00:00+00:00", "entry_price": 100.0,
                                       "exit_time": "2026-07-02T12:00:00+00:00", "remaining_minutes": 600,
                                       "unrealized_bps": units * mark, "updated_at": switch.isoformat()})
        for boundary in ("PESS", "OPT"):           # its TAKE half is already booked on the same entry row
            store.insert("trades", {"book": "K09_D", "boundary": boundary, "candidate": "K09", "side": 1,
                                    "entry_time": "2026-07-01T12:00:00+00:00", "exit_time": "2026-07-01T13:00:00+00:00",
                                    "entry_price": 100.0, "exit_price": 101.0, "gross_bps": 10.0, "cost_bps": 2.0,
                                    "funding_bps": 0.0, "net_bps": 8.0, "hold_minutes": 60.0, "exit_reason": "TAKE"})
        store.upsert("leverage_positions", {"book": "C1_x3", "source_book": "C1", "side": 1, "candidate": "F3",
                                            "entry_time": "2026-07-01T12:00:00+00:00", "entry_price": x3_entry,
                                            "mark_price": 100.0, "notional_usd": 300.0, "margin_usd": 100.0,
                                            "liquidation_price": 67.0, "liquidation_distance_pct": 33.0,
                                            "unrealized_pnl_usd": 0.0, "balance_usd": 100.0,
                                            "updated_at": switch.isoformat()})
        store.upsert("leverage_state", {"book": "C1_x3", "source_book": "C1", "status": "RUNNING", "balance_usd": 100.0,
                                        "cumulative_pnl_usd": 0.0, "cumulative_return_pct": 0.0, "max_drawdown_usd": 0.0,
                                        "max_drawdown_pct": 0.0, "liquidated_at": None, "updated_at": switch.isoformat()})
    old = PaperConfig(books=("C1", "F3", "K09_D"), primary_book="C1", leverage_books=("C1",), sqlite_path=str(path),
                      start_time="2026-07-01T00:00:00Z")
    return path, switch, old


@needs_out
def test_switch_closes_retired_positions_at_the_switch_open_and_freezes_them(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_ax_switch
    path, switch, old = _switch_db(tmp_path)
    out = tmp_path / "paper_ax.toml"
    manifest = paper_ax_switch.switch(old, out, tmp_path / "manifest.json", price=lambda t: 102.0)
    assert manifest["effective_switch_time"] == switch.isoformat()
    assert manifest["retired_books"] == ["C1", "C1_x3", "F3", "K09_D"]
    with PaperStore(path) as store:
        trades = store.frame("trades").set_index(["book", "boundary"])
        assert set(trades.exit_reason) == {"MIGRATION_END", "TAKE+MIGRATION_END"} and len(trades) == 4
        assert (trades.exit_price == 102.0).all() and (trades.exit_time == switch.isoformat()).all()
        assert np.isclose(trades.loc[("C1", "PESS"), "gross_bps"], np.log(1.02) * 1e4)
        assert np.isclose(trades.loc[("K09_D", "PESS"), "gross_bps"], 10 + .5 * np.log(1.02) * 1e4)
        assert trades.loc[("K09_D", "PESS"), "cost_bps"] == 4.0
        daily = store.frame("daily_pnl").groupby(["book", "boundary"]).net_bps.sum()
        assert np.isclose(daily[("C1", "PESS")], trades.loc[("C1", "PESS"), "net_bps"])
        x3 = store.frame("leverage_trades")
        assert x3.exit_reason.tolist() == ["MIGRATION_END"] and np.isclose(x3.gross_pnl_usd.iloc[0], 6.0)
        assert np.isclose(store.frame("leverage_state").balance_usd.iloc[0], 100 + 6.0 - .12)
        assert store.get_meta("r2_52a_effective_switch_time") == switch.isoformat()
        assert manifest["retired_after"] == paper_ax_switch.retired_hashes(store, manifest["retired_books"])
        assert manifest["retired_before"]["trades"]["rows"] == 2
        assert manifest["retired_after"]["trades"]["rows"] == 4
    assert load_config(out).books == NEW_BOOKS
    with pytest.raises(SystemExit):
        paper_ax_switch.switch(old, out, tmp_path / "manifest.json", price=lambda t: 102.0)


# ---------------------------------------------------------------- fix round 1 (Codex review)
def _switch_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_ax_switch
    return paper_ax_switch


@needs_out
def test_switch_liquidates_a_retired_x3_whose_liquidation_the_switch_open_crossed(tmp_path) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path, x3_entry=160.0)        # long 160: liquidation ~107.3 > open 102
    s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
    liq = leverage.liquidation_price(160.0, 1, 100.0, 300.0, .004)
    with PaperStore(path) as store:
        x3 = store.frame("leverage_trades").iloc[0]
        state = store.frame("leverage_state").iloc[0]
    assert x3.exit_reason == "LIQUIDATED" and x3.liquidated == 1 and np.isclose(x3.exit_price, liq)
    assert x3.pnl_usd == -100.0 and x3.balance_after_usd == 0.0
    assert state.status == "LIQUIDATED" and state.balance_usd == 0.0 and state.liquidated_at == switch.isoformat()


def _untouched(path, tmp_path) -> None:
    with PaperStore(path) as store:
        assert store.get_meta("r2_52a_switch_phase") is None
        assert not store.frame("trades").exit_reason.str.contains("MIGRATION_END").any()
    assert not (tmp_path / "paper_ax.toml").exists() and not (tmp_path / "manifest.json").exists()


@needs_out
def test_switch_validates_every_input_before_any_write(tmp_path, monkeypatch) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    for patch in (("FREEZE", tmp_path / "missing.json"), ("SELECTED_K", tmp_path / "missing.csv")):
        with monkeypatch.context() as m:
            m.setattr(s, *patch)
            with pytest.raises(SystemExit):
                s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
        _untouched(path, tmp_path)

    def no_price(t):
        raise OSError("network down")
    with pytest.raises(OSError):
        s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=no_price)
    _untouched(path, tmp_path)
    assert not s.backup_path(path).exists()


@needs_out
@pytest.mark.parametrize("phase", ["validated", "backed_up", "staged", "committed"])
def test_switch_failure_after_each_phase_is_recoverable(tmp_path, phase) -> None:
    s = _switch_module()
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path, switch, old = _switch_db(tmp_path)
    out, manifest_path = tmp_path / "paper_ax.toml", tmp_path / "manifest.json"
    out.write_text("# old config\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="injected"):
        s.switch(old, out, manifest_path, price=lambda t: 102.0, fail_at=phase)
    assert out.read_text(encoding="utf-8") == "# old config\n" and not manifest_path.exists()
    assert s.backup_path(path).exists() == (phase != "validated")
    with PaperStore(path) as store:
        migrated = store.frame("trades").exit_reason.str.contains("MIGRATION_END").any()
        assert migrated == (phase == "committed")
        assert store.get_meta("r2_52a_switch_phase") == ("committed" if phase == "committed" else None)
        if phase == "committed":       # paper processes refuse to start on a half-applied switch
            with pytest.raises(SystemExit):
                paper_catalog.refuse_pending_switch(store)
    manifest = s.switch(old, out, manifest_path, price=lambda t: 999.0)      # rerun: resume or redo
    assert manifest["switch_open_price"] == 102.0 if phase == "committed" else 999.0
    with PaperStore(path) as store:
        trades = store.frame("trades")
        assert len(trades) == 4 and store.get_meta("r2_52a_switch_phase") == "done"
        assert manifest["retired_after"] == s.retired_hashes(store, manifest["retired_books"])
        paper_catalog.refuse_pending_switch(store)
    assert load_config(out).books == NEW_BOOKS and (tmp_path / "paper_ax.pre_r2_52a.toml").exists()
    assert not list(tmp_path.glob("*.r2_52a.tmp"))


@needs_out
@pytest.mark.parametrize("lock", [".run.lock", ".catalog.lock"])
def test_switch_refuses_while_paper_run_or_catalog_holds_its_lock(tmp_path, lock) -> None:
    from btcusdt_quant.paper.store import exclusive_lock
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    with exclusive_lock(path.with_suffix(lock)):
        with pytest.raises(SystemExit, match="running"):
            s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
    _untouched(path, tmp_path)


def test_switch_lock_is_held_for_the_whole_switch(tmp_path) -> None:
    from btcusdt_quant.paper.store import exclusive_lock
    held = tmp_path / "x.lock"
    with exclusive_lock(held):
        with pytest.raises(RuntimeError):
            with exclusive_lock(held):
                pass
    with exclusive_lock(held):          # released after the block
        pass


@pytest.mark.parametrize("failure", ["http500", "timeout"])
def test_telegram_fifo_head_failure_stops_the_cycle(tmp_path, monkeypatch, failure) -> None:
    import requests as http
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    notifier = TelegramNotifier(path, env_path=_secrets(tmp_path))
    notifier._sleep = lambda s: None
    for k in range(3):
        notifier.enqueue(f"alert:{k}", "alert", {"kind": "x", "detail": str(k)})
    calls = []

    class Response:
        status_code = 500

        @staticmethod
        def json():
            return {"ok": False}

    def post(*a, **k):
        calls.append(k["data"]["text"])
        if failure == "timeout":
            raise http.Timeout()
        return Response()
    monkeypatch.setattr("btcusdt_quant.paper.notify.requests.post", post)
    now = pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=1)
    assert notifier.deliver_pending(now) == 0 and len(calls) == 1
    assert notifier.deliver_pending(now + pd.Timedelta(seconds=1)) == 0 and len(calls) == 1   # head still backing off
    with PaperStore(path) as store:
        assert store.frame("notifications").sort_values("id").status.tolist() == ["failed", "pending", "pending"]


# ---------------------------------------------------------------- fix round 2 (Codex re-review)
def _dump(path) -> list[str]:
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(path)) as connection:
        return sorted(line for line in connection.iterdump())


def _files(path):
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)    # bytes and no write
            for p in path.parent.glob(path.name + "*")}


@needs_out
def test_failed_validation_leaves_the_db_byte_identical(tmp_path, monkeypatch) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    before = _files(path)
    assert set(before) == {"live.sqlite"}
    monkeypatch.setattr(s, "SELECTED_K", tmp_path / "missing.csv")

    def no_store(*a, **k):
        raise AssertionError("a writable PaperStore was opened during validation")
    monkeypatch.setattr(s, "PaperStore", no_store)
    with pytest.raises(SystemExit):
        s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
    assert _files(path) == before and not s.backup_path(path).exists()


@needs_out
def test_switch_refuses_without_twice_the_db_size_free(tmp_path, monkeypatch) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    before = _files(path)
    monkeypatch.setattr(s.shutil, "disk_usage", lambda p: SimpleNamespace(total=10, used=9, free=1))
    with pytest.raises(SystemExit, match="free disk"):
        s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
    assert _files(path) == before and not s.backup_path(path).exists()


@needs_out
def test_failure_inside_the_transaction_rolls_back(tmp_path) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    with pytest.raises(RuntimeError, match="injected"):
        s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0,
                 fail_at="in_transaction")
    _untouched(path, tmp_path)
    with PaperStore(path) as store:
        assert store.get_meta("r2_52a_effective_switch_time") is None
    s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0)
    with PaperStore(path) as store:
        assert len(store.frame("trades")) == 4 and store.get_meta("r2_52a_switch_phase") == "done"


@needs_out
@pytest.mark.parametrize("phase", ["config_replaced", "manifest_replaced"])
def test_failure_during_finalize_resumes(tmp_path, phase) -> None:
    s = _switch_module()
    path, switch, old = _switch_db(tmp_path)
    out, manifest_path = tmp_path / "paper_ax.toml", tmp_path / "manifest.json"
    out.write_text("# old config\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="injected"):
        s.switch(old, out, manifest_path, price=lambda t: 102.0, fail_at=phase)
    assert load_config(out).books == NEW_BOOKS and manifest_path.exists() == (phase == "manifest_replaced")
    with PaperStore(path) as store:
        assert store.get_meta("r2_52a_switch_phase") == "committed"
    manifest = s.switch(old, out, manifest_path, price=lambda t: 999.0)
    assert manifest["switch_open_price"] == 102.0
    assert (tmp_path / "paper_ax.pre_r2_52a.toml").read_text(encoding="utf-8") == "# old config\n"
    with PaperStore(path) as store:
        assert len(store.frame("trades")) == 4 and store.get_meta("r2_52a_switch_phase") == "done"


@needs_out
def test_restore_from_the_backup_returns_the_pre_switch_state(tmp_path) -> None:
    import shutil as sh
    s = _switch_module()
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path, switch, old = _switch_db(tmp_path)
    pre = _dump(path)
    with pytest.raises(RuntimeError, match="injected"):
        s.switch(old, tmp_path / "paper_ax.toml", tmp_path / "manifest.json", price=lambda t: 102.0,
                 fail_at="committed")
    backup = s.backup_path(path)
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(backup)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    for suffix in ("-wal", "-shm"):                      # documented restore: stop, drop -wal/-shm, copy backup
        Path(str(path) + suffix).unlink(missing_ok=True)
    sh.copy2(backup, path)
    assert _dump(path) == pre
    with PaperStore(path) as store:
        paper_catalog.refuse_pending_switch(store)          # processes may start again
        assert store.get_meta("r2_52a_switch_phase") is None


def test_telegram_dead_letters_a_permanently_failing_head_and_continues(tmp_path, monkeypatch, caplog) -> None:
    import logging
    from btcusdt_quant.paper import notify
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    notifier = TelegramNotifier(path, env_path=_secrets(tmp_path))
    notifier._sleep = lambda s: None
    for k in range(2):
        notifier.enqueue(f"alert:{k}", "alert", {"kind": "x", "detail": str(k)})
    sent = []

    class Response:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {"ok": self.status_code == 200}

    def post(*a, **k):
        sent.append(k["data"]["text"])
        return Response(500 if k["data"]["text"].endswith("\n0") else 200)
    monkeypatch.setattr("btcusdt_quant.paper.notify.requests.post", post)
    now = pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=1)
    with caplog.at_level(logging.ERROR):
        for attempt in range(notify.MAX_ATTEMPTS):
            delivered = notifier.deliver_pending(now + pd.Timedelta(days=attempt))
    assert delivered == 1 and len(sent) == notify.MAX_ATTEMPTS + 1         # the next message goes out after it
    with PaperStore(path) as store:
        rows = store.frame("notifications").sort_values("id")
        dead = pd.read_sql_query("SELECT * FROM notifications_dead", store.connection)
    assert rows.status.tolist() == ["dead", "sent"]
    assert dead.event_key.tolist() == ["alert:0"] and dead.attempts.tolist() == [notify.MAX_ATTEMPTS]
    assert dead.last_error.tolist() == ["HTTP_500"] and dead.payload.iloc[0].endswith("\n0")
    assert "dead-letter" in caplog.text
