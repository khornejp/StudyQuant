"""G3_COMBINED paper book (NM-B5 long S180 sleeve + short F180 sleeve, 1x each, no x3)."""
from __future__ import annotations

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


def _filled(path: Path, tmp_path) -> Path:
    out = tmp_path / path.name
    out.write_text(path.read_text(encoding="utf-8").replace("__T_ADD__", T_ADD), encoding="utf-8")
    return out


def _frames(days: int = 420, funding=None, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trending synthetic 1m market (30-day up / down regimes) and 8h funding."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    drift = np.where((np.arange(n) // (30 * 1440)) % 2 == 0, 3e-5, -3e-5)
    c = 10_000 * np.exp(np.cumsum(drift + rng.normal(0, 5e-4, n)))
    o = np.r_[c[0], c[:-1]]
    t = pd.date_range("2020-01-01", periods=n, freq="min", tz="UTC")
    minutes = pd.DataFrame({"open_time": t, "open": o, "high": np.maximum(o, c) * 1.0002,
                            "low": np.minimum(o, c) * 0.9998, "close": c, "volume": 1.0, "quote_volume": 1.0,
                            "number_of_trades": 1, "taker_buy_base_volume": 0.5})
    ft = pd.date_range("2020-01-01", periods=days * 3, freq="8h", tz="UTC") + pd.Timedelta(milliseconds=3)
    rate = rng.normal(1e-4, 5e-5, len(ft)) if funding is None else np.full(len(ft), funding)
    return minutes, pd.DataFrame({"time": ft, "rate": rate})


def _market(days: int = 420, funding=None):
    minutes, fund = _frames(days, funding)
    return g3.engine().b2.Market.from_frames(minutes, fund)


def test_book_is_two_sleeves_with_the_frozen_picks() -> None:
    assert g3.BOOKS == ("G3_COMBINED",) and not set(g3.BOOKS) & set(catalog.BOOKS)
    assert g3.SLEEVES["long"] == (1, {"struct": "S180", "c": 0.0, "vol": "W180-P65"})
    assert g3.SLEEVES["short"] == (-1, {"struct": "F180", "c": 0.0, "vol": "V-ENS"})
    assert (g3.OFFSET_BPS, g3.PEN_BPS) == (2, 0.5)


@needs_engine
def test_sleeve_ids_are_the_batch5_dev_picks() -> None:
    assert {s: g3.sleeve_id(s) for s in g3.SLEEVES} == {"long": "G5-S180-c+0.0-W180-P65",
                                                         "short": "G5-F180-c+0.0-V-ENS"}


@needs_engine
def test_mad0_threshold_falls_back_to_the_median() -> None:
    m = _market(funding=1e-4)                                  # constant rates: MAD90 == 0 everywhere it is ready
    dec4 = np.arange(239, m.N, 240)
    st = g3.engine().build_state(m, dec4)
    ready = np.isfinite(st["med"])
    assert ready.any() and (st["mad"][ready] == 0).all() and np.isnan(st["fz"][ready]).all()
    sig = g3.engine().core_signal(st, g3.SLEEVES["short"][1])
    assert np.array_equal(sig["thr"][ready], st["med"][ready]) and sig["gate"][ready].all()
    side, _ = g3.sleeve_signal(st, "short")
    assert (side == -1).any() and np.array_equal(side == -1, (sig["des"] == -1) & sig["gate"])


@needs_engine
@pytest.mark.parametrize("cut", [0, 777])              # whole days and an open partial day (padded Book)
def test_sleeves_are_one_sided_capped_and_start_flat(cut: int) -> None:
    full = _market()
    m = full if not cut else g3.engine().b2.Market(*(getattr(full, a)[:full.N - cut] for a in
                                                     ("t", "o", "h", "l", "c", "v", "tb")), full.ft, full.fr)
    start = pd.Timestamp("2020-12-01T02:00Z")
    sim = g3.simulate(m, start)
    led = g3.ledger(sim)
    assert set(led.sleeve) == {"long", "short"}
    assert (led.loc[led.sleeve == "long", "side"] == 1).all() and (led.loc[led.sleeve == "short", "side"] == -1).all()
    assert (led.weight > 0).all() and (led.weight <= 1).all() and sim["gross"].max() <= 2
    assert (led.decision_time >= start).all() and (led.entry_time >= led.decision_time).all()
    dt = pd.DatetimeIndex(led.decision_time)
    assert ((dt.hour % 4 == 0) & (dt.minute == 0)).all()          # order time T = 4h bar open + 1m
    closed = led.loc[~led.open_at_end]
    assert (closed.exit_time > closed.exit_decision_time - MIN).all()
    for sleeve in g3.SLEEVES:      # no overlap inside a sleeve; next decision after the previous exit fill
        part = led.loc[led.sleeve == sleeve]
        assert (part.decision_time.iloc[1:].to_numpy() > part.exit_time.iloc[:-1].to_numpy()).all()
    assert len(sim["pnl"]) == m.N and abs(sim["pnl"].sum() - led.net_bps.sum()) < 1e-6
    daily = g3.daily(sim, "G3_COMBINED", start)
    assert daily.date.iloc[0] == "2020-12-01" and abs(daily.net_bps.sum() - led.net_bps.sum()) < 1e-6
    assert np.allclose(daily.gross_bps - daily.cost_bps + daily.funding_bps, daily.net_bps)
    states = {r["sleeve"]: r for r in g3.sleeve_state(sim, "G3_COMBINED", pd.Timestamp(m.t[-1], tz="UTC") + MIN)}
    assert set(states) == {"long", "short"}
    for sleeve, part in led.groupby("sleeve"):
        if part.open_at_end.iloc[-1]:
            assert states[sleeve]["status"] in ("OPEN", "EXIT_PENDING")


@needs_engine
def test_market_joins_archive_and_paper_tables_and_fails_closed(monkeypatch) -> None:
    minutes, fund = _frames(3)
    cut = pd.Timestamp("2020-01-02", tz="UTC")
    monkeypatch.setattr(g3, "_archive", lambda live_from: (minutes.loc[minutes.open_time < live_from],
                                                           fund.loc[fund.time < g3.engine().b2.SPLIT]))
    monkeypatch.setattr(g3.engine().b2, "SPLIT", pd.Timestamp("2020-01-01T12:00Z"))
    live = minutes.loc[minutes.open_time >= cut].assign(open_time=lambda f: f.open_time.map(lambda t: t.isoformat()))
    text_funding = fund.assign(time=fund.time.map(lambda t: t.isoformat()))
    end = pd.Timestamp("2020-01-03T10:00Z")
    m = g3.market(live, text_funding, end, live_from=cut)
    assert m.N == 2 * 1440 + 600 and np.array_equal(m.c, minutes.close.to_numpy()[:m.N])
    assert np.array_equal(m.ft, fund.loc[fund.time < end, "time"].array.asi8)      # nothing at / after the data end
    with pytest.raises(ValueError, match="missing minutes"):
        g3.market(live.drop(live.index[100]), text_funding, end, live_from=cut)


def _fake_g3(name, minutes, funding, start, end):
    t = pd.Timestamp(start)
    trades = pd.DataFrame([{"sleeve": "long", "candidate": "G3_LONG:x", "side": 1, "weight": 0.5,
                            "decision_time": t, "entry_time": t, "entry_price": 100.0, "exit_decision_time": t + MIN,
                            "exit_time": t + 2 * MIN, "exit_price": 101.0, "open_at_end": False, "gross_bps": 50.0,
                            "cost_bps": 2.0, "funding_bps": 0.0, "net_bps": 48.0},
                           {"sleeve": "short", "candidate": "G3_SHORT:y", "side": -1, "weight": 1.0,
                            "decision_time": t, "entry_time": t + MIN, "entry_price": 100.0,
                            "exit_decision_time": pd.NaT, "exit_time": pd.NaT, "exit_price": np.nan,
                            "open_at_end": True, "gross_bps": 1.0, "cost_bps": 4.0, "funding_bps": 0.0,
                            "net_bps": -3.0}])
    daily = pd.DataFrame([{"book": name, "boundary": "PESS", "date": t.strftime("%Y-%m-%d"), "gross_bps": 51.0,
                           "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": 47.0}])
    state = [{"book": name, "sleeve": s, "status": "FLAT", "updated_at": end.isoformat()} for s in g3.SLEEVES]
    return {"trades": trades, "daily": daily, "state": state}


def test_publish_replaces_closed_trades_daily_and_sleeve_state(tmp_path) -> None:
    result = _fake_g3("G3_COMBINED", None, None, pd.Timestamp("2026-10-10T12:00Z"), pd.Timestamp("2026-10-10T13:00Z"))
    with PaperStore(tmp_path / "live.sqlite") as store:
        for _ in range(2):
            with store.transaction() as connection:
                g3.publish(connection, "G3_COMBINED", result)
        trades = store.frame("trades")
        assert len(trades) == 1 and trades.candidate.iloc[0] == "G3_LONG:x" and trades.boundary.iloc[0] == "PESS"
        assert len(store.frame("daily_pnl")) == 1 and store.frame("positions").empty
        assert store.connection.execute("SELECT COUNT(*) FROM catalog_g3_state").fetchone()[0] == 2


def test_staged_config_is_the_axc0_staged_config_plus_g3_without_x3(tmp_path) -> None:
    base, staged = load_config(_filled(AXC0_STAGED, tmp_path)), load_config(_filled(STAGED, tmp_path))
    assert staged.books == base.books + g3.BOOKS
    assert (staged.leverage_books, staged.telegram_books, staged.comparison_books) == (
        base.leverage_books, base.telegram_books, base.comparison_books)
    assert staged.book_start_times == {**base.book_start_times, "G3_COMBINED": T_ADD}
    assert load_config(ROOT / "config/paper.toml").books == base.books[:28]
    with pytest.raises(ValueError):
        load_config(STAGED)                     # the placeholder can never be loaded as a live config


def test_catalog_cycle_publishes_g3_once_without_x3_or_signals(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_catalog
    path = tmp_path / "live.sqlite"
    market = _store_with_minutes(path)
    config = load_config(_filled(STAGED, tmp_path))
    config = replace(config, sqlite_path=str(path), book_start_times={n: "2026-07-01T00:00:00Z" for n in config.books},
                     start_time="2026-07-01T00:00:00Z")
    assert paper_catalog.active_books(config)[-1] == "G3_COMBINED"
    with PaperStore(path) as store:
        ctx = SimpleNamespace(minutes=market.assign(open_time=pd.to_datetime(market.open_time, utc=True)))
        monkeypatch.setattr(catalog, "run_book", _fake_run_book)
        monkeypatch.setattr(g3, "run_book", _fake_g3)
        monkeypatch.setattr(catalog, "signal_rows", lambda name, ctx, since: (_ for _ in ()).throw(KeyError(name))
                            if name in g3.BOOKS else pd.DataFrame())
        end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        assert paper_catalog.recompute_books(store, config, end, ctx, pd.DataFrame(columns=["time", "rate"]),
                                             with_signals=True) == 31
        assert set(store.frame("leverage_state").book) == {f"{n}_x3" for n in config.books if n != "G3_COMBINED"}
        assert set(store.frame("trades").book) == set(config.books)


@needs_engine
@pytest.mark.skipif(not SNAPSHOT.exists(), reason="R2-54 FINAL snapshot (untracked out/) absent")
def test_snapshot_parity_paper_equals_research_sleeves_and_combined_book() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paper_g3_parity as parity
    report = parity.run_all()
    s = report["sleeve_vs_combined"]
    assert s["match"] and s["n_compared"] == 48 and s["max_abs_diff"] == 0
    assert [round(v["got"], 4) for v in s["combined_primary"].values()] == [28783.9741, 20146.5468, 8637.4274,
                                                                           3299.0488]
    full = report["paper_full_replay"]
    assert full["match"] and full["stored_ledger"]["match"] and full["max_gross"] == 2.0
    assert {k: v["trades"] for k, v in full["sleeves"].items()} == {"long": [116, 116], "short": [183, 183]}
    assert report["paper_flat_start_2026"]["match"] and report["match"]
