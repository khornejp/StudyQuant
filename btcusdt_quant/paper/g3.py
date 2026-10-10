"""G3_COMBINED paper pair: NM-B5 G3-NORM-ADAPT long sleeve (book G3_LONG) + short sleeve (book G3_SHORT).

Frozen paper spec: Codex B5 review "Frozen paper spec" (addendum out/new_model_batch5_20261010/g3_paper/
g3_combined_paper_addendum.json). G3_LONG = LONG_DEV_PICK G5-S180-c+0.0-W180-P65 long side only, G3_SHORT =
SHORT_DEV_PICK G5-F180-c+0.0-V-ENS short side only; each sleeve <= 1x of the common NAV, gross <= 2, no x3 overlay.

Live engine (Codex fix round 1): each sleeve starts FLAT at its book start and is an incremental state machine over
closed 1m bars (FLAT -> ENTRY_PENDING -> OPEN -> EXIT_PENDING -> FLAT), the minute-by-minute form of batch-2
simulate(kind="state"). Every decision / order / requote / fill / expiry is appended once, as first observed, to
g3_events (INSERT OR IGNORE, code + config hash); g3_state holds the resume point; closed trades are appended to
trades. Signals come from the research build_state / core_signal on the 4h close series since 2020-01-01 (about
16k bars + all funding events: the exact research input, no 1m archive in memory). Order time T = closed 4h bar open
+ 1m; funding strictly before T; MAD90 = 0 -> threshold = median90. A missing minute stops the sleeve at the gap
(fail closed, g3_health stale). Accounting (trades / daily_pnl) = batch-2 Book over the stored ledger.
The full-history research replay is a verification tool only (scripts/paper_g3_parity.py).
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.funding_source import load_funding_dir
from .store import utc_text

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "out/run_new_model_batch5_20261010.py"
SLEEVES = {"G3_LONG": (1, dict(struct="S180", c=0.0, vol="W180-P65")),
           "G3_SHORT": (-1, dict(struct="F180", c=0.0, vol="V-ENS"))}
BOOKS = tuple(SLEEVES)
NAMES = {"G3_LONG": "4시간 추세·변동 비대칭 롱 (1배)", "G3_SHORT": "4시간 하락 추세 + 펀딩 관문 숏 (1배)"}
OFFSET_BPS, PEN_BPS, TTL_MIN, EXIT_QUOTE_BPS, REQUOTE_MIN = 2, 0.5, 60, 2.0, 60
MIN = 60_000_000_000
H4 = 240 * MIN
STALE_MIN = 5
TABLES = (
    "CREATE TABLE IF NOT EXISTS g3_events (book TEXT NOT NULL, event_time TEXT NOT NULL, event_type TEXT NOT NULL, "
    "payload TEXT NOT NULL, code_hash TEXT NOT NULL, config_hash TEXT NOT NULL, observed_at TEXT NOT NULL, "
    "PRIMARY KEY(book, event_time, event_type))",
    "CREATE TABLE IF NOT EXISTS g3_state (book TEXT PRIMARY KEY, state TEXT NOT NULL, last_bar TEXT NOT NULL, "
    "updated_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS g3_health (book TEXT PRIMARY KEY, last_success TEXT, last_error TEXT, "
    "last_error_at TEXT, last_bar TEXT, stale INTEGER NOT NULL, updated_at TEXT NOT NULL)")


@lru_cache(maxsize=1)
def engine():
    """Batch-5 research module (imports batch-4/3/2/1 unchanged)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("nm_b5", ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# every source file the live G3 path executes: g3, its paper / sim helpers and the batch-5 engine with the batch-4/3/2/1
# files it loads dynamically (importlib)
DEPS = (Path(__file__), ROOT / "btcusdt_quant/paper/store.py", ROOT / "btcusdt_quant/funding_source.py",
        *(ROOT / f"btcusdt_quant/sim/{n}.py" for n in ("data", "provenance", "registry", "store")),
        *(ROOT / f"out/run_new_model_batch{i}_20261010.py" for i in range(1, 6)))
MISMATCH = "behavior_hash_mismatch"


def code_hash() -> str:
    """sha256 over the dependency chain (file name + bytes of every DEPS file); read fresh on every call."""
    h = hashlib.sha256()
    for path in DEPS:
        h.update(Path(path).name.encode() + b"\0")
        h.update(Path(path).read_bytes())
    return h.hexdigest()


def behavior_hash(book: str, start: pd.Timestamp, code: str | None = None) -> str:
    """Everything that decides a sleeve's path: code chain, sleeve params, execution params, book start (config)."""
    spec = {"code": code or code_hash(), "book": book, "sleeve": SLEEVES[book],
            "execution": {"offset_bps": OFFSET_BPS, "pen_bps": PEN_BPS, "ttl_min": TTL_MIN,
                          "exit_quote_bps": EXIT_QUOTE_BPS, "requote_min": REQUOTE_MIN},
            "start": utc_text(pd.Timestamp(start))}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def sleeve_id(book: str) -> str:
    return engine().cid(SLEEVES[book][1])


def sleeve_signal(st: dict, book: str) -> tuple[np.ndarray, np.ndarray]:
    """Research core_signal restricted to the sleeve's side: the other side's target is flat (exit, no entry)."""
    side, p = SLEEVES[book]
    sig = engine().core_signal(st, p)
    s = np.where(sig["side"] == side, side, 0)
    return s, np.where(s != 0, sig["w"], 0.0)


# ---------------------------------------------------------------- 4h signal state
def _ns(values) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True, format="mixed")).as_unit("ns").asi8


def _bars_4h(t: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    keep = (t + MIN) % H4 == 0                       # decision bars 03:59, 07:59, ... UTC
    return t[keep], c[keep]


@lru_cache(maxsize=2)
def _archive(live_from: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """4h decision-bar closes before live_from (DEV market < 2026-01-01 + R2-54 FINAL snapshot) and DEV funding
    (< 2026-01-01): the research batch-2 load_all inputs, reduced to what build_state reads."""
    b2 = engine().b2
    dev = pd.read_parquet(b2.DEV_MARKET, columns=["open_time", "close"],
                          filters=[("open_time", "<", b2.SPLIT.to_pydatetime())])
    t, c = _bars_4h(_ns(dev.open_time), dev.close.to_numpy(float))
    del dev
    if live_from > b2.SPLIT:
        snap = pd.read_parquet(b2.SNAP / "market_1m.parquet", columns=["open_time", "close"])
        st, sc = _bars_4h(_ns(snap.open_time), snap.close.to_numpy(float))
        keep = st < live_from.value
        t, c = np.r_[t, st[keep]], np.r_[c, sc[keep]]
    assert t[0] == b2.START.value + H4 - MIN and np.all(np.diff(t) == H4), "4h archive grid not contiguous"
    fr = load_funding_dir(b2.DEV_FUNDING)
    ft = _ns([r.funding_time for r in fr])
    rate = np.array([r.funding_rate for r in fr], float)
    keep = ft < b2.SPLIT.value
    return t, c, ft[keep], rate[keep]


def signals(minutes: pd.DataFrame, funding: pd.DataFrame, end: pd.Timestamp,
            live_from: pd.Timestamp | None = None) -> dict[int, dict[str, tuple[int, float]]]:
    """{T ns: {book: (target side, weight)}} for every 4h decision with data < end; research build_state on the 4h
    close series since 2020-01-01 (archive + paper klines_1m >= live_from) and funding < end."""
    b2 = engine().b2
    live_from = b2.END if live_from is None else pd.Timestamp(live_from)
    t0, c0, ft0, fr0 = _archive(live_from)
    t = _ns(minutes.open_time)
    keep = (t >= live_from.value) & (t < end.value)
    t1, c1 = _bars_4h(t[keep], minutes.close.to_numpy(float)[keep])
    t4, c4 = np.r_[t0, t1], np.r_[c0, c1]
    if not np.all(np.diff(t4) == H4):
        raise ValueError("missing 4h decision bar in paper klines_1m")
    ft = _ns(funding.time)
    fr = pd.to_numeric(funding.rate).to_numpy(float)
    order = np.argsort(ft, kind="stable")
    ft, fr = ft[order], fr[order]
    fk = (ft >= b2.SPLIT.value) & (ft < end.value)
    # compact market: decision bar + its next minute (T) per 4h bar; build_state reads only t, c at dec4 and funding
    tt = np.repeat(t4, 2) + np.tile([0, MIN], len(t4))
    cc = np.repeat(c4, 2)
    m = b2.Market(tt, cc, cc, cc, cc, np.zeros_like(cc), np.zeros_like(cc), np.r_[ft0, ft[fk]], np.r_[fr0, fr[fk]])
    dec4 = np.arange(0, m.N, 2)
    st = engine().build_state(m, dec4)
    sides = {book: sleeve_signal(st, book) for book in SLEEVES}
    return {int(T): {book: (int(sides[book][0][k]), float(sides[book][1][k])) for book in SLEEVES}
            for k, T in enumerate(st["T"])}


# ---------------------------------------------------------------- sleeve state machine
def initial_state(start: pd.Timestamp, behavior: str | None = None) -> dict:
    """FLAT, nothing inherited; the first bar processed is the decision bar whose T = start (if on the 4h grid)."""
    out = {"status": "FLAT", "last_bar": int(pd.Timestamp(start).value) - 2 * MIN, "start": int(pd.Timestamp(start).value)}
    return out if behavior is None else {**out, "behavior_hash": behavior}


def _limit(close: float, side: int, bps: float) -> float:
    return float(engine().b2.limit_price(close, side, bps))


def _fills(o: float, h: float, l: float, lim: float, buy: bool) -> bool:
    """batch-2 first_fill for one bar: pen bp trade-through, gap-through rejects."""
    return (o >= lim and l <= lim * (1 - PEN_BPS / 1e4)) if buy else (o <= lim and h >= lim * (1 + PEN_BPS / 1e4))


def _flat(s: dict) -> dict:
    return {k: s[k] for k in ("last_bar", "start", "behavior_hash") if k in s} | {"status": "FLAT"}


def step(state: dict, book: str, t, o, h, l, c, sig: dict) -> tuple[dict, list[tuple[int, str, dict]]]:
    """Advance one sleeve over consecutive closed bars (already checked contiguous after state['last_bar']).
    Per bar: resting order fill / expiry / requote first, then the 4h decision of that bar (batch-2 simulate order:
    after an exit fill the decision on the fill bar is considered; decisions are ignored while an order rests)."""
    s = dict(state)
    side_of = SLEEVES[book][0]
    events = []
    for k in range(len(t)):
        tj = int(t[k])
        if s["status"] == "ENTRY_PENDING":
            if _fills(o[k], h[k], l[k], s["lim"], s["side"] > 0):
                s.update(status="OPEN", entry_time=tj, entry_px=s["lim"])
                events.append((tj, "ENTRY_FILL", {"side": s["side"], "weight": s["w"], "price": s["lim"],
                                                  "decision_time": s["dec_time"]}))
            elif tj >= s["deadline"]:
                events.append((tj, "ENTRY_EXPIRED", {"side": s["side"], "price": s["lim"], "decision_time": s["dec_time"]}))
                s = _flat(s)
        elif s["status"] == "EXIT_PENDING":
            if _fills(o[k], h[k], l[k], s["lim"], s["side"] < 0):
                trade = {"side": s["side"], "weight": s["w"], "decision_time": s["dec_time"],
                         "entry_time": s["entry_time"], "entry_px": s["entry_px"],
                         "exit_decision_time": s["exit_dec_time"], "exit_time": tj, "exit_px": s["lim"]}
                events.append((tj, "EXIT_FILL", trade))
                s = _flat(s)
            elif tj >= s["quote_base"] + REQUOTE_MIN * MIN:
                s.update(quote_base=tj, lim=_limit(c[k], -s["side"], EXIT_QUOTE_BPS))
                events.append((tj, "EXIT_REQUOTE", {"price": s["lim"]}))
        T = tj + MIN
        if T % H4 == 0 and T >= s["start"]:
            if T not in sig:
                raise ValueError(f"no signal for {pd.Timestamp(T, tz='UTC')}")
            target, w = sig[T][book]
            events.append((T, "DECISION", {"target": target, "weight": w, "close": float(c[k]),
                                           "status": s["status"]}))
            if s["status"] == "FLAT" and target != 0 and w > 0:
                assert target == side_of
                s.update(status="ENTRY_PENDING", side=target, w=w, dec_time=T, deadline=tj + TTL_MIN * MIN,
                         lim=_limit(c[k], target, OFFSET_BPS))
                events.append((T, "ENTRY_ORDER", {"side": target, "weight": w, "price": s["lim"]}))
            elif s["status"] == "OPEN" and target != s["side"]:
                s.update(status="EXIT_PENDING", exit_dec_time=T, quote_base=tj,
                         lim=_limit(c[k], -s["side"], EXIT_QUOTE_BPS))
                events.append((T, "EXIT_ORDER", {"price": s["lim"]}))
        s["last_bar"] = tj
    return s, events


# ---------------------------------------------------------------- accounting (batch-2 Book over the ledger)
def _whole_days(m):
    """Book reshapes its 1m arrays by day: pad the open day with flat bars at the last close. Book(..., hi=real N)
    keeps every mark, fee and funding cut at the real data end; padded minutes carry zero P&L."""
    pad = -m.N % 1440
    if not pad:
        return m
    b2 = engine().b2
    flat = lambda x, v: np.r_[x, np.full(pad, v)]  # noqa: E731
    c = m.c[-1]
    return b2.Market(np.r_[m.t, m.t[-1] + MIN * np.arange(1, pad + 1)], flat(m.o, c), flat(m.h, c), flat(m.l, c),
                     flat(m.c, c), flat(m.v, 0.0), flat(m.tb, 0.0), m.ft, m.fr)


def book_of(trades: list[dict], state: dict, minutes: pd.DataFrame, funding: pd.DataFrame, start: pd.Timestamp,
            end: pd.Timestamp):
    """batch-2 Book over the sleeve ledger (closed trades + the open position) on the 1m bars from the start's UTC
    day to end. Returns (Book, Market, trade frame)."""
    b2 = engine().b2
    lo = pd.Timestamp(start).floor("D").value
    t = _ns(minutes.open_time)
    keep = (t >= lo) & (t < end.value)
    mm = minutes.loc[keep]
    tt = t[keep]
    if not len(tt) or tt[0] != lo or not np.all(np.diff(tt) == MIN):
        raise ValueError("paper klines_1m not contiguous since the book start day")
    ft, fr = _ns(funding.time), pd.to_numeric(funding.rate).to_numpy(float)
    order = np.argsort(ft, kind="stable")
    fk = order[(ft[order] >= lo) & (ft[order] < end.value)]
    g = lambda k: mm[k].to_numpy(float)  # noqa: E731
    m = b2.Market(tt, g("open"), g("high"), g("low"), g("close"), g("volume"), g("taker_buy_base_volume"),
                  ft[fk], fr[fk])
    rows = list(trades)
    if state["status"] in ("OPEN", "EXIT_PENDING"):
        rows.append({"side": state["side"], "weight": state["w"], "decision_time": state["dec_time"],
                     "entry_time": state["entry_time"], "entry_px": state["entry_px"],
                     "exit_decision_time": state.get("exit_dec_time"), "exit_time": None, "exit_px": np.nan})
    idx = lambda x: int(np.searchsorted(tt, x)) if x is not None else -1  # noqa: E731
    tr = pd.DataFrame({"side": [r["side"] for r in rows], "entry_weight_frozen": [r["weight"] for r in rows],
                       "decision_idx": [idx(r["decision_time"] - MIN) for r in rows],
                       "entry_idx": [idx(r["entry_time"]) for r in rows], "entry_px": [r["entry_px"] for r in rows],
                       "exit_decision_idx": [idx(r["exit_decision_time"] - MIN) if r["exit_decision_time"] else -1
                                             for r in rows],
                       "exit_idx": [idx(r["exit_time"]) for r in rows], "exit_px": [r["exit_px"] for r in rows],
                       "open_at_end": [r["exit_time"] is None for r in rows]},
                      columns=["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px",
                               "exit_decision_idx", "exit_idx", "exit_px", "open_at_end"])
    orders = pd.DataFrame(columns=["decision_idx", "side", "weight", "filled"])
    return b2.Book(_whole_days(m), tr, orders, 0, m.N), m, tr


def daily_rows(book: str, bk, m) -> list[tuple]:
    """daily_pnl rows (PESS, research 1m MTM net4 incl. the open trade and its reserved 2 bps exit fee)."""
    n = m.N
    net = bk.pnl[:n]
    fund, cost = np.zeros(n), np.zeros(n)
    np.add.at(fund, bk.f_min, bk.f_cf)
    np.add.at(cost, bk.j0, 2 * bk.w)
    np.add.at(cost, bk.jx, 2 * bk.w)
    day = (m.t - m.t[0]) // (1440 * MIN)
    frame = pd.DataFrame({"day": day, "net": net, "funding": fund, "cost": cost}).groupby("day").sum()
    dates = pd.to_datetime(m.t[0] + frame.index.to_numpy() * 1440 * MIN, utc=True).strftime("%Y-%m-%d")
    return [(book, "PESS", d, float(n_ - f + c_), float(c_), float(f), float(n_))
            for d, n_, f, c_ in zip(dates, frame.net, frame.funding, frame.cost)]


# ---------------------------------------------------------------- persistence / cycle
def ensure_tables(connection) -> None:
    for sql in TABLES:
        connection.execute(sql)


def load_state(connection, book: str, start: pd.Timestamp, behavior: str) -> dict:
    """Stored resume state; a new book starts FLAT and records its behavior hash."""
    row = connection.execute("SELECT state FROM g3_state WHERE book=?", (book,)).fetchone()
    return json.loads(row[0]) if row else initial_state(start, behavior)


class BehaviorMismatch(RuntimeError):
    """Stored sleeve state was produced by other code / params / start: never continued silently
    (scripts/paper_g3_migrate.py is the explicit path)."""


def closed_trades(connection, book: str) -> list[dict]:
    rows = connection.execute("SELECT payload FROM g3_events WHERE book=? AND event_type='EXIT_FILL' "
                              "ORDER BY event_time", (book,)).fetchall()
    return [json.loads(r[0]) for r in rows]


def _iso(ns: int) -> str:
    return utc_text(pd.Timestamp(int(ns), tz="UTC"))


def advance(connection, book: str, start: pd.Timestamp, minutes: pd.DataFrame, sig_fn, end: pd.Timestamp,
            behavior: str) -> tuple:
    """New bars for one sleeve: contiguous from state['last_bar'] + 1m, cut at the first gap (fail closed)."""
    state = load_state(connection, book, start, behavior)
    if state.get("behavior_hash") != behavior:
        raise BehaviorMismatch(MISMATCH)
    t = _ns(minutes.open_time)
    a = int(np.searchsorted(t, state["last_bar"] + MIN))
    b = int(np.searchsorted(t, end.value))
    gap = None
    if a < b and t[a] != state["last_bar"] + MIN:
        return state, [], f"gap: next bar {_iso(t[a])} after {_iso(state['last_bar'])}"
    if a < b:
        breaks = np.flatnonzero(np.diff(t[a:b]) != MIN)
        if len(breaks):
            b = a + int(breaks[0]) + 1
            gap = f"gap after {_iso(t[b - 1])}"
    if a >= b:
        return state, [], gap
    cols = [minutes[k].to_numpy(float)[a:b] for k in ("open", "high", "low", "close")]
    needs = ((t[a:b] + MIN) % H4 == 0) & (t[a:b] + MIN >= state["start"])
    new, events = step(state, book, t[a:b], *cols, sig_fn() if needs.any() else {})
    return new, events, gap


def write_health(connection, book: str, error: str | None, last: int, end: pd.Timestamp, now: str,
                 stale: bool | None = None) -> None:
    stale = int(end.value - (last + MIN) > STALE_MIN * MIN) if stale is None else int(stale)
    old = connection.execute("SELECT last_success, last_error, last_error_at FROM g3_health WHERE book=?",
                             (book,)).fetchone() or (None, None, None)
    connection.execute("INSERT OR REPLACE INTO g3_health VALUES (?,?,?,?,?,?,?)", (
        book, old[0] if error else now, error or old[1], now if error else old[2], _iso(last), stale, now))


def run_cycle(store, starts: dict[str, pd.Timestamp], minutes: pd.DataFrame, funding: pd.DataFrame,
              end: pd.Timestamp, config_hash: str, live_from: pd.Timestamp | None = None) -> int:
    """One paper cycle for the G3 sleeve books in `starts` (book -> start, start < end). Appends events / trades,
    stores the resume state, refreshes daily_pnl and g3_health. Returns the number of books advanced cleanly."""
    now = utc_text(pd.Timestamp.now(tz="UTC"))
    with store.transaction() as connection:
        ensure_tables(connection)
    cache = {}

    def sig_fn():
        if "sig" not in cache:
            cache["sig"] = signals(minutes, funding, end, live_from)
        return cache["sig"]

    done, code = 0, code_hash()
    for book, start in starts.items():
        behavior = behavior_hash(book, start, code)
        error = None
        try:
            with store.transaction() as connection:
                state, events, error = advance(connection, book, start, minutes, sig_fn, end, behavior)
                trades = closed_trades(connection, book) + [p for _, kind, p in events if kind == "EXIT_FILL"]
                done_to = pd.Timestamp(state["last_bar"] + MIN, tz="UTC")     # accounting only over processed bars
                if done_to > pd.Timestamp(start).floor("D"):
                    bk, m, tr = book_of(trades, state, minutes, funding, start, done_to)
                else:
                    bk = m = None
                    tr = pd.DataFrame({"open_at_end": []})
                for t_, kind, payload in events:
                    connection.execute("INSERT OR IGNORE INTO g3_events VALUES (?,?,?,?,?,?,?)",
                                       (book, _iso(t_), kind, json.dumps(payload), behavior, config_hash, now))
                for k in np.flatnonzero(~tr.open_at_end.to_numpy(bool)):
                    r = trades[k]
                    connection.execute(
                        "INSERT OR IGNORE INTO trades(book,boundary,candidate,entry_time,exit_time,side,entry_price,"
                        "exit_price,gross_bps,cost_bps,funding_bps,net_bps,hold_minutes,exit_reason) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (book, "PESS", sleeve_id(book), _iso(r["entry_time"]), _iso(r["exit_time"]), int(r["side"]),
                         float(r["entry_px"]), float(r["exit_px"]), float(bk.gross_full[k]), float(4 * bk.w[k]),
                         float(bk.fund_full[k]), float(bk.net4_full[k]), (r["exit_time"] - r["entry_time"]) / MIN,
                         "TARGET_CHANGE"))
                if bk is not None:
                    connection.executemany("INSERT OR REPLACE INTO daily_pnl(book,boundary,date,gross_bps,cost_bps,"
                                           "funding_bps,net_bps) VALUES(?,?,?,?,?,?,?)", daily_rows(book, bk, m))
                connection.execute("INSERT OR REPLACE INTO g3_state VALUES (?,?,?,?)",
                                   (book, json.dumps(state), _iso(state["last_bar"]), now))
                write_health(connection, book, error, state["last_bar"], end, now)     # same transaction
        except Exception as exc:     # the stored state stays at the last clean cycle
            error = MISMATCH if isinstance(exc, BehaviorMismatch) else f"{type(exc).__name__}: {exc}"
            with store.transaction() as connection:
                row = connection.execute("SELECT state FROM g3_state WHERE book=?", (book,)).fetchone()
                last = json.loads(row[0])["last_bar"] if row else initial_state(start)["last_bar"]
                write_health(connection, book, error, last, end, now, stale=True if error == MISMATCH else None)
        done += error is None
    return done


__all__ = ["BOOKS", "DEPS", "NAMES", "SLEEVES", "behavior_hash", "book_of", "code_hash", "initial_state", "run_cycle", "signals", "sleeve_signal", "step"]
