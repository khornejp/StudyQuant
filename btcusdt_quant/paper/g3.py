"""G3_COMBINED paper book: NM-B5 G3-NORM-ADAPT long sleeve + short sleeve (two independent state machines).

Frozen paper spec: Codex B5 review "Frozen paper spec" (addendum out/new_model_batch5_20261010/g3_paper/
g3_combined_paper_addendum.json). Long sleeve = LONG_DEV_PICK G5-S180-c+0.0-W180-P65 long side only, short sleeve =
SHORT_DEV_PICK G5-F180-c+0.0-V-ENS short side only; each sleeve <= 1x of the common NAV, gross <= 2, no x3 overlay.
Decisions, fills and accounting are the research engine itself (out/run_new_model_batch5_20261010.py build_state /
core_signal, batch-2 simulate / Book): train/serve parity by construction; scripts/paper_g3_parity.py checks the data
path. Order time T = closed 4h bar open + 1m (dec4 = 239 + 240k from 2020-01-01); funding strictly before T.
"""
from __future__ import annotations
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.funding_source import load_funding_dir
from btcusdt_quant.sim import data
from .store import utc_text

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "out/run_new_model_batch5_20261010.py"
BOOKS = ("G3_COMBINED",)
NAMES = {"G3_COMBINED": "4시간 추세·변동 비대칭 롱 + 펀딩 관문 숏 (각 1배, 합산 최대 2배)"}
SLEEVES = {"long": (1, dict(struct="S180", c=0.0, vol="W180-P65")),
           "short": (-1, dict(struct="F180", c=0.0, vol="V-ENS"))}
OFFSET_BPS, PEN_BPS = 2, 0.5
STATE_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_g3_state (book TEXT NOT NULL, sleeve TEXT NOT NULL, "
               "status TEXT NOT NULL, side INTEGER, weight REAL, decision_time TEXT, entry_time TEXT, entry_price REAL, "
               "exit_decision_time TEXT, unrealized_bps REAL, last_decision_time TEXT, target_side INTEGER, "
               "target_weight REAL, updated_at TEXT NOT NULL, PRIMARY KEY(book, sleeve))")


@lru_cache(maxsize=1)
def engine():
    """Batch-5 research module (imports batch-4/3/2/1 unchanged)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("nm_b5", ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sleeve_id(sleeve: str) -> str:
    return engine().cid(SLEEVES[sleeve][1])


@lru_cache(maxsize=2)
def _archive(live_from: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Research history before `live_from`: DEV market (< 2026-01-01) + R2-54 FINAL snapshot (2026-01-01 ..
    live_from), DEV funding archive (< 2026-01-01); as batch-2 load_all."""
    b2 = engine().b2
    dev = data.load_minutes(b2.DEV_MARKET, end=b2.SPLIT)
    parts = [dev]
    if live_from > b2.SPLIT:
        snap = pd.read_parquet(b2.SNAP / "market_1m.parquet", columns=data.MINUTE_COLUMNS)
        snap["open_time"] = pd.to_datetime(snap.open_time, utc=True).astype("datetime64[ns, UTC]")
        parts.append(snap.loc[snap.open_time < live_from])
    minutes = pd.concat(parts, ignore_index=True)
    fr = load_funding_dir(b2.DEV_FUNDING)
    funding = pd.DataFrame({"time": pd.to_datetime([r.funding_time for r in fr], utc=True),
                            "rate": [r.funding_rate for r in fr]})
    funding = funding.loc[funding.time < b2.SPLIT]
    funding["time"] = funding.time.astype("datetime64[ns, UTC]")
    return minutes, funding.reset_index(drop=True)


def market(live_minutes: pd.DataFrame, live_funding: pd.DataFrame, end: pd.Timestamp,
           live_from: pd.Timestamp | None = None):
    """batch-2 Market over archive + paper tables (klines_1m >= live_from, funding >= 2026-01-01), minutes < end.
    Fails closed on any missing minute (data.validate_minutes)."""
    b2 = engine().b2
    live_from = b2.END if live_from is None else pd.Timestamp(live_from)
    archive, fund0 = _archive(live_from)
    live = live_minutes[data.MINUTE_COLUMNS].copy()
    live["open_time"] = pd.to_datetime(live.open_time, utc=True, format="mixed").astype("datetime64[ns, UTC]")
    live = live.loc[(live.open_time >= live_from) & (live.open_time < end)]
    minutes = data.validate_minutes(pd.concat([archive, live], ignore_index=True).sort_values("open_time",
                                                                                              ignore_index=True))
    fund = live_funding[["time", "rate"]].copy()
    fund["time"] = pd.to_datetime(fund.time, utc=True, format="mixed").astype("datetime64[ns, UTC]")
    fund = fund.loc[(fund.time >= b2.SPLIT) & (fund.time < end)]
    funding = pd.concat([fund0, fund], ignore_index=True).sort_values("time", ignore_index=True)
    return b2.Market.from_frames(minutes, funding)


def sleeve_signal(st: dict, sleeve: str) -> tuple[np.ndarray, np.ndarray]:
    """Research core_signal restricted to the sleeve's side: the other side's target is flat (exit, no entry)."""
    side, p = SLEEVES[sleeve]
    sig = engine().core_signal(st, p)
    s = np.where(sig["side"] == side, side, 0)
    return s, np.where(s != 0, sig["w"], 0.0)


def _whole_days(m):
    """Book reshapes its 1m arrays by day: pad the open day with flat bars at the last close. Book(..., hi=m.N) keeps
    every mark, fee and funding cut at the real data end; the padded minutes carry zero P&L."""
    pad = -m.N % 1440
    if not pad:
        return m
    b2 = engine().b2
    t = np.r_[m.t, m.t[-1] + b2.MIN * np.arange(1, pad + 1)]
    flat = lambda x, v: np.r_[x, np.full(pad, v)]  # noqa: E731
    c = m.c[-1]
    return b2.Market(t, flat(m.o, c), flat(m.h, c), flat(m.l, c), flat(m.c, c), flat(m.v, 0.0), flat(m.tb, 0.0),
                     m.ft, m.fr)


def simulate(m, book_start: pd.Timestamp) -> dict:
    """Both sleeves from a flat start: decisions with order time T >= book_start. Returns per sleeve the research
    trades / orders / Book plus the decision frame, and the combined 1m P&L."""
    b5 = engine()
    b2 = b5.b2
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    lo = max(m.idx(book_start) - 1, 0)                  # decision bar lo-1 closes at book_start: T = book_start
    out = {"m": m, "dec4": dec4, "T": st["T"], "lo": lo, "sleeves": {}}
    mb = _whole_days(m)
    for sleeve in SLEEVES:
        side, w = sleeve_signal(st, sleeve)
        tr, od = b2.simulate(m, "state", dec4, side, w, OFFSET_BPS, b2.TTL_TREND, PEN_BPS, lo, m.N)
        out["sleeves"][sleeve] = {"side": side, "w": w, "tr": tr, "od": od, "book": b2.Book(mb, tr, od, lo, m.N)}
    held = sum(b5.held_weight(s["book"]) for s in out["sleeves"].values())[:m.N]
    assert held.max(initial=0.0) <= 2 + 1e-12, "gross > 2"
    out["gross"] = held
    out["pnl"] = sum(s["book"].pnl for s in out["sleeves"].values())[:m.N]
    return out


def _time(m, idx) -> pd.Series:
    ix = np.asarray(idx, dtype=np.int64)
    return pd.Series(pd.to_datetime(m.t[np.maximum(ix, 0)], utc=True)).where(ix >= 0)


def ledger(sim: dict) -> pd.DataFrame:
    """All sleeve trades (closed and open) with paper times: decision_time / exit_decision_time = bar open + 1m."""
    m, rows = sim["m"], []
    for sleeve, s in sim["sleeves"].items():
        tr, bk = s["tr"], s["book"]
        if not len(tr):
            continue
        rows.append(pd.DataFrame({
            "sleeve": sleeve, "candidate": f"G3_{sleeve.upper()}:{sleeve_id(sleeve)}", "side": tr.side.to_numpy(int),
            "weight": tr.entry_weight_frozen.to_numpy(float),
            "decision_time": _time(m, tr.decision_idx) + pd.Timedelta(minutes=1),
            "entry_time": _time(m, tr.entry_idx), "entry_price": tr.entry_px.to_numpy(float),
            "exit_decision_time": _time(m, tr.exit_decision_idx) + pd.Timedelta(minutes=1),
            "exit_time": _time(m, tr.exit_idx), "exit_price": tr.exit_px.to_numpy(float),
            "open_at_end": tr.open_at_end.to_numpy(bool), "gross_bps": bk.gross_full, "cost_bps": 4.0 * bk.w,
            "funding_bps": bk.fund_full, "net_bps": bk.net4_full}))
    columns = ["sleeve", "candidate", "side", "weight", "decision_time", "entry_time", "entry_price",
               "exit_decision_time", "exit_time", "exit_price", "open_at_end", "gross_bps", "cost_bps",
               "funding_bps", "net_bps"]
    return (pd.concat(rows, ignore_index=True).sort_values(["entry_time", "sleeve"], ignore_index=True)
            if rows else pd.DataFrame(columns=columns))


def decisions(sim: dict) -> pd.DataFrame:
    """Per sleeve and 4h decision since the book start: order time T, target side and weight."""
    keep = sim["dec4"] >= sim["lo"]
    T = pd.to_datetime(sim["T"][keep], utc=True)
    return pd.concat([pd.DataFrame({"sleeve": k, "T": T, "side": s["side"][keep], "weight": s["w"][keep]})
                      for k, s in sim["sleeves"].items()], ignore_index=True)


def daily(sim: dict, book: str, book_start: pd.Timestamp) -> pd.DataFrame:
    """daily_pnl rows (PESS only, research 1m MTM net4 incl. open trades and their reserved 2 bps exit fee)."""
    m = sim["m"]
    net = sim["pnl"]
    fund, cost = np.zeros(m.N), np.zeros(m.N)
    for s in sim["sleeves"].values():
        bk = s["book"]
        np.add.at(fund, bk.f_min, bk.f_cf)
        np.add.at(cost, bk.j0, 2 * bk.w)
        np.add.at(cost, bk.jx, 2 * bk.w)
    day = (m.t - m.t[0]) // (1440 * 60_000_000_000)
    first = max((book_start.value - m.t[0]) // (1440 * 60_000_000_000), 0)
    frame = pd.DataFrame({"day": day, "net": net, "funding": fund, "cost": cost}).groupby("day").sum()
    frame = frame.loc[frame.index >= first]
    dates = pd.to_datetime(m.t[0] + frame.index.to_numpy() * 1440 * 60_000_000_000, utc=True).strftime("%Y-%m-%d")
    return pd.DataFrame({"book": book, "boundary": "PESS", "date": dates,
                         "gross_bps": (frame.net - frame.funding + frame.cost).to_numpy(),
                         "cost_bps": frame.cost.to_numpy(), "funding_bps": frame.funding.to_numpy(),
                         "net_bps": frame.net.to_numpy()})


def sleeve_state(sim: dict, book: str, end: pd.Timestamp) -> list[dict]:
    """One row per sleeve: OPEN / EXIT_PENDING / ENTRY_PENDING / FLAT plus the latest decision."""
    m, rows = sim["m"], []
    tdec = decisions(sim)
    for sleeve, s in sim["sleeves"].items():
        tr, od = s["tr"], s["od"]
        last = tdec.loc[tdec.sleeve == sleeve].iloc[-1] if (tdec.sleeve == sleeve).any() else None
        row = {"book": book, "sleeve": sleeve, "status": "FLAT", "side": None, "weight": None, "decision_time": None,
               "entry_time": None, "entry_price": None, "exit_decision_time": None, "unrealized_bps": None,
               "last_decision_time": None if last is None else utc_text(last["T"]),
               "target_side": None if last is None else int(last["side"]),
               "target_weight": None if last is None else float(last["weight"]), "updated_at": utc_text(end)}
        if len(tr) and tr.open_at_end.iloc[-1]:
            t = tr.iloc[-1]
            px = m.c[m.N - 1]
            row.update(status="EXIT_PENDING" if t.exit_decision_idx >= 0 else "OPEN", side=int(t.side),
                       weight=float(t.entry_weight_frozen), decision_time=utc_text(_time(m, [t.decision_idx])[0]
                                                                                  + pd.Timedelta(minutes=1)),
                       entry_time=utc_text(_time(m, [t.entry_idx])[0]), entry_price=float(t.entry_px),
                       exit_decision_time=(utc_text(_time(m, [t.exit_decision_idx])[0] + pd.Timedelta(minutes=1))
                                           if t.exit_decision_idx >= 0 else None),
                       unrealized_bps=float(t.side * t.entry_weight_frozen * (px / t.entry_px - 1) * 1e4))
        elif len(od) and not od.filled.iloc[-1] and od.decision_idx.iloc[-1] + 1 + engine().b2.TTL_TREND > m.N:
            o = od.iloc[-1]
            row.update(status="ENTRY_PENDING", side=int(o.side), weight=float(o.weight),
                       decision_time=utc_text(_time(m, [o.decision_idx])[0] + pd.Timedelta(minutes=1)),
                       entry_price=float(engine().b2.limit_price(m.c[int(o.decision_idx)], int(o.side), OFFSET_BPS)))
        rows.append(row)
    return rows


def run_book(name: str, live_minutes: pd.DataFrame, live_funding: pd.DataFrame, book_start: pd.Timestamp,
             end: pd.Timestamp) -> dict:
    sim = simulate(market(live_minutes, live_funding, end), pd.Timestamp(book_start))
    return {"sim": sim, "trades": ledger(sim), "daily": daily(sim, name, pd.Timestamp(book_start)),
            "state": sleeve_state(sim, name, end)}


def publish(connection, name: str, result: dict) -> None:
    """Replace this book's trades (closed sleeve trades, PESS), daily_pnl and sleeve state rows."""
    connection.execute(STATE_TABLE)
    for table in ("trades", "daily_pnl", "positions", "catalog_g3_state"):
        connection.execute(f"DELETE FROM {table} WHERE book=?", (name,))
    closed = result["trades"].loc[~result["trades"].open_at_end.astype(bool)]
    for row in closed.itertuples(index=False):
        connection.execute(
            "INSERT INTO trades(book,boundary,candidate,entry_time,exit_time,side,entry_price,exit_price,gross_bps,"
            "cost_bps,funding_bps,net_bps,hold_minutes,exit_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, "PESS", row.candidate, utc_text(row.entry_time), utc_text(row.exit_time), int(row.side),
             float(row.entry_price), float(row.exit_price), float(row.gross_bps), float(row.cost_bps),
             float(row.funding_bps), float(row.net_bps), (row.exit_time - row.entry_time) / pd.Timedelta(minutes=1),
             "TARGET_CHANGE"))
    connection.executemany("INSERT INTO daily_pnl(book,boundary,date,gross_bps,cost_bps,funding_bps,net_bps) "
                           "VALUES(?,?,?,?,?,?,?)", result["daily"].itertuples(index=False, name=None))
    for row in result["state"]:
        connection.execute(f"INSERT INTO catalog_g3_state ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                           tuple(row.values()))


__all__ = ["BOOKS", "NAMES", "SLEEVES", "decisions", "ledger", "market", "publish", "run_book", "simulate"]
