"""G3 paper pair (G3_LONG + G3_SHORT): NM-B5 long S180 / short F180 sleeves, 1x each, no x3, incremental and
append-only (Codex fix round 1)."""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper import catalog, g3
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.store import PaperStore
from tests.test_paper_ax import _fake_run_book, _store_with_minutes

ROOT = Path(__file__).resolve().parents[1]
AXC0_STAGED = ROOT / "config/paper.axc0_staged.toml"
STAGED = ROOT / "config/paper.g3_staged.toml"
T_ADD = "2026-10-10T12:00:00Z"
SNAPSHOT = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot/manifest.json"
needs_engine = pytest.mark.skipif(not g3.ENGINE.exists(), reason="research engine out/run_new_model_batch5 absent")
MIN = pd.Timedelta(minutes=1)
START = pd.Timestamp("2020-12-01T02:00Z")          # off the 4h grid: first decision T = 04:00


def _filled(path: Path, tmp_path) -> Path:
    out = tmp_path / path.name
    out.write_text(path.read_text(encoding="utf-8").replace("__T_ADD__", T_ADD), encoding="utf-8")
    return out


def _frames(days: int = 420, funding=None, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trending synthetic 1m market (10-day up / down regimes) and 8h funding."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    drift = np.where((np.arange(n) // (10 * 1440)) % 2 == 0, 3e-5, -3e-5)
    c = 10_000 * np.exp(np.cumsum(drift + rng.normal(0, 5e-4, n)))
    o = np.r_[c[0], c[:-1]]
    t = pd.date_range("2020-01-01", periods=n, freq="min", tz="UTC")
    minutes = pd.DataFrame({"open_time": t, "open": o, "high": np.maximum(o, c) * 1.0002,
                            "low": np.minimum(o, c) * 0.9998, "close": c, "volume": 1.0, "quote_volume": 1.0,
                            "number_of_trades": 1, "taker_buy_base_volume": 0.5})
    ft = pd.date_range("2020-01-01", periods=days * 3, freq="8h", tz="UTC") + pd.Timedelta(milliseconds=3)
    rate = rng.normal(1e-4, 5e-5, len(ft)) if funding is None else np.full(len(ft), funding)
    return minutes, pd.DataFrame({"time": ft, "rate": rate})


@pytest.fixture(scope="module")
def synthetic():
    minutes, fund = _frames()
    b2 = g3.engine().b2
    m = b2.Market.from_frames(minutes, fund)
    dec4 = np.arange(239, m.N, 240)
    st = g3.engine().build_state(m, dec4)
    sides = {b: g3.sleeve_signal(st, b) for b in g3.SLEEVES}
    sig = {int(T): {b: (int(sides[b][0][k]), float(sides[b][1][k])) for b in g3.SLEEVES} for k, T in enumerate(st["T"])}
    lo = m.idx(START) - 1
    ref = {b: b2.simulate(m, "state", dec4, *sides[b], 2, b2.TTL_TREND, 0.5, lo, m.N)[0] for b in g3.SLEEVES}
    return SimpleNamespace(minutes=minutes, fund=fund, m=m, sig=sig, ref=ref, lo=lo)


def _ledger(events: list, state: dict) -> pd.DataFrame:
    rows = [p for _, kind, p in events if kind == "EXIT_FILL"]
    if state["status"] in ("OPEN", "EXIT_PENDING"):
        rows.append({"side": state["side"], "weight": state["w"], "decision_time": state["dec_time"],
                     "entry_time": state["entry_time"], "entry_px": state["entry_px"],
                     "exit_decision_time": state.get("exit_dec_time"), "exit_time": None, "exit_px": np.nan})
    return pd.DataFrame(rows)


def _expected(m, tr: pd.DataFrame) -> pd.DataFrame:
    t = lambda ix: [None if i < 0 else int(m.t[i]) for i in ix]  # noqa: E731
    return pd.DataFrame({"side": tr.side, "weight": tr.entry_weight_frozen,
                         "decision_time": [x + g3.MIN for x in t(tr.decision_idx)], "entry_time": t(tr.entry_idx),
                         "entry_px": tr.entry_px,
                         "exit_decision_time": [None if x is None else x + g3.MIN for x in t(tr.exit_decision_idx)],
                         "exit_time": t(tr.exit_idx), "exit_px": tr.exit_px})


def _same(got: pd.DataFrame, exp: pd.DataFrame) -> bool:
    if len(got) != len(exp) or not len(exp):
        return len(got) == len(exp)
    for c in exp:
        a, b = got[c].to_numpy(), exp[c].to_numpy()
        if c in ("entry_px", "exit_px", "weight"):
            if not np.array_equal(a.astype(float), b.astype(float), equal_nan=True):
                return False
        elif [None if pd.isna(x) else int(x) for x in a] != [None if pd.isna(x) else int(x) for x in b]:
            return False
    return True


def test_books_are_two_sleeves_with_the_frozen_picks() -> None:
    assert g3.BOOKS == ("G3_LONG", "G3_SHORT") and not set(g3.BOOKS) & set(catalog.BOOKS)
    assert g3.SLEEVES["G3_LONG"] == (1, {"struct": "S180", "c": 0.0, "vol": "W180-P65"})
    assert g3.SLEEVES["G3_SHORT"] == (-1, {"struct": "F180", "c": 0.0, "vol": "V-ENS"})
    assert (g3.OFFSET_BPS, g3.PEN_BPS, g3.TTL_MIN, g3.EXIT_QUOTE_BPS, g3.REQUOTE_MIN) == (2, 0.5, 60, 2.0, 60)


@needs_engine
def test_sleeve_ids_are_the_batch5_dev_picks() -> None:
    assert {b: g3.sleeve_id(b) for b in g3.SLEEVES} == {"G3_LONG": "G5-S180-c+0.0-W180-P65",
                                                        "G3_SHORT": "G5-F180-c+0.0-V-ENS"}


@needs_engine
def test_mad0_threshold_falls_back_to_the_median() -> None:
    minutes, fund = _frames(funding=1e-4)                     # constant rates: MAD90 == 0 everywhere it is ready
    m = g3.engine().b2.Market.from_frames(minutes, fund)
    st = g3.engine().build_state(m, np.arange(239, m.N, 240))
    ready = np.isfinite(st["med"])
    assert ready.any() and (st["mad"][ready] == 0).all() and np.isnan(st["fz"][ready]).all()
    sig = g3.engine().core_signal(st, g3.SLEEVES["G3_SHORT"][1])
    assert np.array_equal(sig["thr"][ready], st["med"][ready]) and sig["gate"][ready].all()
    side, _ = g3.sleeve_signal(st, "G3_SHORT")
    assert (side == -1).any() and np.array_equal(side == -1, (sig["des"] == -1) & sig["gate"])


@needs_engine
@pytest.mark.parametrize("chunk", [10**9, 997, 1])
def test_incremental_step_equals_research_simulate(synthetic, chunk) -> None:
    """The live state machine over closed bars (any cycle size, resumed from its own state) == batch-2 simulate
    from the same flat start: decision / entry / exit minutes, prices, sides, frozen weights."""
    s, m = synthetic, synthetic.m
    a = s.lo
    b = m.N if chunk != 1 else a + 60 * 1440           # 1m cycles: first 60 days only (speed)
    n = 0
    for book in g3.SLEEVES:
        state, events = g3.initial_state(START), []
        for k in range(a, b, chunk):
            j = min(k + chunk, b)
            state, ev = g3.step(state, book, m.t[k:j], m.o[k:j], m.h[k:j], m.l[k:j], m.c[k:j], s.sig)
            events += ev
            state = json.loads(json.dumps(state))       # stored and reloaded every cycle
        tr = s.ref[book]
        if chunk == 1:
            tr = tr.loc[tr.decision_idx < b - 1].copy()
            open_ = (tr.exit_idx >= b) | tr.open_at_end
            tr.loc[open_, ["exit_idx", "exit_px"]] = [-1, np.nan]
            tr.loc[open_ & (tr.exit_decision_idx >= b - 1), "exit_decision_idx"] = -1
        assert _same(_ledger(events, state), _expected(m, tr)), book
        n += len(tr)
        assert {p["target"] for t, kind, p in events if kind == "DECISION"} <= {0, g3.SLEEVES[book][0]}
    assert n >= (2 if chunk == 1 else 9)


def _cycle_inputs(s, days=40):
    n = s.m.idx(START) - 1 + days * 1440
    lo = pd.Timestamp(START).floor("D")
    minutes = s.minutes.iloc[s.minutes.open_time.searchsorted(lo):n].reset_index(drop=True)
    return minutes


@needs_engine
def test_run_cycle_is_append_only_resumes_and_matches_simulate(synthetic, tmp_path, monkeypatch) -> None:
    s = synthetic
    monkeypatch.setattr(g3, "signals", lambda minutes, funding, end, live_from=None: s.sig)
    minutes = _cycle_inputs(s)
    path = tmp_path / "p.sqlite"
    starts = {b: START for b in g3.SLEEVES}
    ends = list(pd.date_range(START + pd.Timedelta(days=3), minutes.open_time.iloc[-1] + MIN, freq="3D")) + \
        [minutes.open_time.iloc[-1] + MIN]
    for e in ends:
        with PaperStore(path) as store:
            assert g3.run_cycle(store, starts, minutes, s.fund, e, "cfg") == 2
    with sqlite3.connect(path) as c:
        before = c.execute("SELECT COUNT(*), MAX(observed_at) FROM g3_events").fetchone()
    with PaperStore(path) as store:                      # same end again: nothing new, nothing rewritten
        g3.run_cycle(store, starts, minutes, s.fund, ends[-1], "cfg2")
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT COUNT(*), MAX(observed_at) FROM g3_events").fetchone() == before
        assert {r[0] for r in c.execute("SELECT DISTINCT config_hash FROM g3_events")} == {"cfg"}
        trades = pd.read_sql_query("SELECT * FROM trades", c)
        health = pd.read_sql_query("SELECT * FROM g3_health", c)
    assert len(trades) and set(trades.book) <= set(g3.BOOKS)
    assert len(health) == 2 and (health.stale == 0).all() and health.last_error.isna().all()
    b = _cycle_inputs(s).shape[0]
    for book in g3.SLEEVES:
        tr = s.ref[book]
        closed = tr.loc[~tr.open_at_end & (tr.exit_idx < s.m.idx(minutes.open_time.iloc[-1]) + 1)]
        mine = trades.loc[trades.book == book].sort_values("entry_time", ignore_index=True)
        assert len(mine) == len(closed) and np.array_equal(mine.entry_price.to_numpy(), closed.entry_px.to_numpy())
    assert b > 0


@needs_engine
def test_gap_stops_the_sleeve_and_flags_health(synthetic, tmp_path, monkeypatch) -> None:
    s = synthetic
    monkeypatch.setattr(g3, "signals", lambda minutes, funding, end, live_from=None: s.sig)
    minutes = _cycle_inputs(s, days=5)
    path = tmp_path / "p.sqlite"
    starts = {b: START for b in g3.SLEEVES}
    with PaperStore(path) as store:
        g3.run_cycle(store, starts, minutes, s.fund, minutes.open_time.iloc[2000], "cfg")
        holed = minutes.drop(minutes.index[3000])
        assert g3.run_cycle(store, starts, holed, s.fund, minutes.open_time.iloc[-1] + MIN, "cfg") == 0
        health = pd.read_sql_query("SELECT * FROM g3_health", store.connection)
        state = store.connection.execute("SELECT last_bar FROM g3_state").fetchall()
    assert (health.stale == 1).all() and health.last_error.notna().all()
    assert {r[0] for r in state} == {pd.Timestamp(minutes.open_time.iloc[1999]).isoformat()}   # not advanced


@needs_engine
def test_both_sleeves_filling_the_same_minute_do_not_collide(tmp_path, monkeypatch) -> None:
    """Separate books per sleeve: the trades UNIQUE(book, boundary, entry_time) key cannot clash."""
    t = pd.date_range("2026-10-10T00:00Z", periods=8 * 60, freq="min")
    c = np.full(len(t), 100.0)
    o, h, l = c.copy(), c * 1.01, c * 0.99            # every bar trades through both sides' limits
    minutes = pd.DataFrame({"open_time": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0,
                            "taker_buy_base_volume": 0.5})
    sig = {int((t[0] + pd.Timedelta(hours=h)).value): {"G3_LONG": (0, 0.0), "G3_SHORT": (0, 0.0)} for h in (8, 12, 16)}
    sig[int((t[0] + pd.Timedelta(hours=4)).value)] = {"G3_LONG": (1, 1.0), "G3_SHORT": (-1, 1.0)}
    monkeypatch.setattr(g3, "signals", lambda *a, **k: sig)
    start = t[0] + pd.Timedelta(hours=4)
    minutes = pd.concat([minutes, minutes.assign(open_time=minutes.open_time + pd.Timedelta(hours=8))],
                        ignore_index=True)
    with PaperStore(tmp_path / "p.sqlite") as store:
        g3.run_cycle(store, {b: start for b in g3.BOOKS}, minutes, pd.DataFrame(columns=["time", "rate"]),
                     minutes.open_time.iloc[-1] + MIN, "cfg")
        trades = store.frame("trades")
    assert len(trades) == 2 and trades.entry_time.nunique() == 1 and set(trades.book) == set(g3.BOOKS)


def test_staged_config_is_the_axc0_staged_config_plus_g3_without_x3(tmp_path) -> None:
    base, staged = load_config(_filled(AXC0_STAGED, tmp_path)), load_config(_filled(STAGED, tmp_path))
    assert staged.books == base.books + g3.BOOKS
    assert (staged.leverage_books, staged.telegram_books, staged.comparison_books) == (
        base.leverage_books, base.telegram_books, base.comparison_books)
    assert staged.book_start_times == {**base.book_start_times, "G3_LONG": T_ADD, "G3_SHORT": T_ADD}
    assert load_config(ROOT / "config/paper.toml").books == base.books[:28]
    with pytest.raises(ValueError):
        load_config(STAGED)                     # the placeholder can never be loaded as a live config


def test_catalog_cycle_runs_g3_once_without_x3_or_signals(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    config = load_config(_filled(STAGED, tmp_path))
    config = replace(config, sqlite_path=str(path), book_start_times={n: "2026-07-01T00:00:00Z" for n in config.books},
                     start_time="2026-07-01T00:00:00Z")
    assert paper_catalog.active_books(config)[-2:] == list(g3.BOOKS)
    seen = {}

    def fake_cycle(store, starts, minutes, funding, end, config_hash, live_from=None):
        seen.update(starts=starts, config_hash=config_hash)
        return len(starts)

    with PaperStore(path) as store:
        ctx = SimpleNamespace(minutes=market.assign(open_time=pd.to_datetime(market.open_time, utc=True)))
        monkeypatch.setattr(catalog, "run_book", _fake_run_book)
        monkeypatch.setattr(g3, "run_cycle", fake_cycle)
        monkeypatch.setattr(catalog, "signal_rows", lambda name, ctx, since: (_ for _ in ()).throw(KeyError(name))
                            if name in g3.BOOKS else pd.DataFrame())
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        assert paper_catalog.recompute_books(store, config, end, ctx, pd.DataFrame(columns=["time", "rate"]),
                                             with_signals=True) == 32
        assert set(store.frame("leverage_state").book) == {f"{n}_x3" for n in config.books if n not in g3.BOOKS}
    assert set(seen["starts"]) == set(g3.BOOKS) and seen["config_hash"] == config.hash


@needs_engine
@pytest.mark.skipif(not SNAPSHOT.exists(), reason="R2-54 FINAL snapshot (untracked out/) absent")
def test_snapshot_parity_incremental_paper_equals_research() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_g3_parity as parity
    report = parity.run_all()
    s = report["sleeve_vs_combined"]
    assert s["match"] and s["n_compared"] == 48 and s["max_abs_diff"] == 0
    assert [round(v["got"], 4) for v in s["combined_primary"].values()] == [28783.9741, 20146.5468, 8637.4274,
                                                                           3299.0488]
    p = report["paper_incremental_flat_start_2026"]
    assert p["match"] and round(p["combined_TEST_net4"], 4) == 3299.0488
    assert p["books"]["G3_LONG"]["trades"] == [15, 15] and p["books"]["G3_LONG"]["closed"] == 14
    assert p["books"]["G3_SHORT"]["trades"] == [21, 21] and p["books"]["G3_SHORT"]["closed"] == 21
    assert report["stored_ledger"]["match"] and report["match"]
