"""G3 (G3_LONG + G3_SHORT) paper-vs-research parity (Codex B5 review "필수 parity" + fix round 1).

  research  out/run_new_model_batch5_20261010.py data path (batch-2 load_all: DEV archive + R2-54 FINAL snapshot
            market / funding_model_input), build_state, core_signal, batch-2 simulate / Book. Verification only.
  sleeves   independent re-simulation per sleeve (long-only S180-c0-W180-P65, short-only F180-c0-V-ENS), 2 sides x
            6 cells (offset 2/5 x pen 0.5/1/2) x 4 windows = 48 side net4 == combined_book.json cells_net4 (derived
            from the two-sided runs); combined primary == 28783.9741 / 20146.5468 / 8637.4274 / 3299.0488.
  paper     the live incremental engine (g3.run_cycle) on a temp paper DB, flat start 2026-01-01 00:00 (a T_ADD-like
            start), fed the snapshot as klines_1m / the snapshot copy of the live funding table in cycles of 7 days
            plus 180 one-minute cycles (every cycle resumes from the stored state) to 2026-10-08.
  ref       research flat start: simulate(lo = decision bar of T = 2026-01-01) per sleeve, primary cell.

Gates: decision side exact, weight atol 1e-12; orders (time, side, weight, price, filled) and trades (decision /
entry / exit minute, prices, side, frozen weight) exact; paper decision_time == research bar + 1m; 1m P&L of the
stored ledger == research P&L (atol 1e-9); window net4 atol 1e-6; trades table rows == research net4_full.
Writes out/new_model_batch5_20261010/g3_paper/paper_g3_parity.json.

Usage: venv_btcusdt\\Scripts\\python.exe scripts\\paper_g3_parity.py
"""
from __future__ import annotations
import json, sqlite3, sys, tempfile
from contextlib import closing
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.paper import g3  # noqa: E402
from btcusdt_quant.paper.store import PaperStore  # noqa: E402

RUN = ROOT / "out/new_model_batch5_20261010/NM-B5-20261010T080025Z-c55285f2"
OUT = ROOT / "out/new_model_batch5_20261010/g3_paper/paper_g3_parity.json"
LIVE_DB = ROOT / "artifacts/live/live.sqlite"
PRIMARY_REF = {"DEV-FULL": 28783.9741, "DEV-A": 20146.5468, "DEV-B": 8637.4274, "TEST": 3299.0488}
TOL, W_TOL, PNL_TOL = 1e-6, 1e-12, 1e-9
SIDE_OF = {"G3_LONG": "long", "G3_SHORT": "short"}
MIN = pd.Timedelta(minutes=1)


def research_runs(m, st, dec4, lo: int, cells) -> dict:
    b2 = g3.engine().b2
    out = {}
    for book in g3.SLEEVES:
        side, w = g3.sleeve_signal(st, book)
        for off, pen in cells:
            tr, od = b2.simulate(m, "state", dec4, side, w, off, b2.TTL_TREND, pen, lo, m.N)
            out[(book, off, pen)] = (tr, od, b2.Book(m, tr, od, lo, m.N), side, w)
    return out


def sleeve_vs_combined(m, runs: dict) -> dict:
    b5 = g3.engine()
    comb = json.loads((RUN / "combined_book.json").read_text(encoding="utf-8"))
    wb = b5.b3.window_bounds(m)
    diffs, primary = {}, {k: 0.0 for k in wb}
    for (book, off, pen), (_, _, bk, _, _) in runs.items():
        side = SIDE_OF[book]
        for k, (a, b) in wb.items():
            got = bk.window(a, b)[f"{side}_net4"]
            diffs[f"{side}|o{off}_p{pen}|{k}"] = got - comb["cells_net4"][k][f"o{off}_p{pen}"][side]
            if (off, pen) == b5.PRIMARY:
                primary[k] += got
    prim = {k: {"got": v, "ref_4dp": PRIMARY_REF[k], "diff_vs_json": v - comb["windows_primary"][k]["net4"]}
            for k, v in primary.items()}
    worst = max(abs(v) for v in diffs.values())
    ok = len(diffs) == 48 and worst <= TOL and all(abs(p["diff_vs_json"]) <= TOL and abs(p["got"] - p["ref_4dp"])
                                                   <= 5e-5 for p in prim.values())
    return {"n_compared": len(diffs), "max_abs_diff": worst, "n_diff_gt_1e-6": sum(abs(v) > TOL for v in diffs.values()),
            "combined_primary": prim, "match": bool(ok)}


def snapshot_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """klines_1m from the decision bar of T = 2026-01-01 (DEV last minute) + snapshot; snapshot live funding table."""
    b2 = g3.engine().b2
    snap = pd.read_parquet(b2.SNAP / "market_1m.parquet")
    last = pd.read_parquet(b2.DEV_MARKET, filters=[("open_time", ">=", (b2.SPLIT - MIN).to_pydatetime())])
    last = last.loc[pd.to_datetime(last.open_time, utc=True) < b2.SPLIT, snap.columns]
    k = pd.concat([last, snap], ignore_index=True)
    k["open_time"] = pd.to_datetime(k.open_time, utc=True).astype("datetime64[ns, UTC]")
    return k, pd.read_parquet(b2.SNAP / "funding_live_table.parquet")


def cycle_ends(start: pd.Timestamp, end: pd.Timestamp, minute_from: pd.Timestamp, n_minute: int) -> list:
    ends = list(pd.date_range(start + pd.Timedelta(days=7), end, freq="7D"))
    ends += [minute_from + MIN * k for k in range(1, n_minute + 1)]
    return sorted(set(e for e in ends if e <= end) | {end})


def replay(k: pd.DataFrame, f: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, path: Path) -> dict:
    """Incremental paper engine from a flat start, cycle by cycle; every cycle reloads the state from the DB."""
    b2 = g3.engine().b2
    ends = cycle_ends(start, end, pd.Timestamp("2026-04-22T15:00Z"), 180)    # 1m cycles over the first long entry
    starts = {b: start for b in g3.SLEEVES}
    for e in ends:
        with PaperStore(path) as store:
            assert g3.run_cycle(store, starts, k, f, e, "parity", live_from=b2.SPLIT) == 2, e
    with closing(sqlite3.connect(path)) as c:
        events = pd.read_sql_query("SELECT * FROM g3_events", c)
        states = {b: json.loads(s) for b, s in c.execute("SELECT book, state FROM g3_state")}
        trades = pd.read_sql_query("SELECT * FROM trades", c)
        daily = pd.read_sql_query("SELECT * FROM daily_pnl", c)
        health = pd.read_sql_query("SELECT * FROM g3_health", c)
    return {"cycles": len(ends), "events": events, "states": states, "trades": trades, "daily": daily,
            "health": health}


def compare(rep: dict, ref: dict, m, st, lo: int, k: pd.DataFrame, f: pd.DataFrame, start, end) -> dict:
    b5 = g3.engine()
    out, ok = {"cycles": rep["cycles"], "books": {}}, True
    a = m.idx(start)
    wb = b5.b3.window_bounds(m)
    total = 0.0
    for book in g3.SLEEVES:
        tr, od, bk_ref, side, w = ref[(book, *b5.PRIMARY)]
        ev = rep["events"].loc[rep["events"].book == book]
        pay = lambda kind: [json.loads(p) for p in ev.loc[ev.event_type == kind, "payload"]]  # noqa: E731
        times = lambda kind: pd.to_datetime(ev.loc[ev.event_type == kind, "event_time"], utc=True).reset_index(drop=True)  # noqa: E731
        T = pd.to_datetime(st["T"], utc=True)
        keep = np.asarray(T >= start)
        dec = pd.DataFrame(pay("DECISION")).assign(T=times("DECISION")).sort_values("T", ignore_index=True)
        r = {"decisions": [len(dec), int(keep.sum())],
             "decision_T_equal": bool(len(dec) == keep.sum() and (dec["T"].to_numpy() == T[keep].to_numpy()).all())}
        r["side_equal"] = bool(r["decision_T_equal"] and np.array_equal(dec.target.to_numpy(), side[keep]))
        r["weight_max_abs_diff"] = float(np.max(np.abs(dec.weight.to_numpy() - w[keep]), initial=0.0)) \
            if r["decision_T_equal"] else None
        # orders: research od (decision bar, side, weight, filled) vs ENTRY_ORDER + ENTRY_FILL / ENTRY_EXPIRED
        eo = pd.DataFrame(pay("ENTRY_ORDER")).assign(T=times("ENTRY_ORDER"))
        fills = {p["decision_time"] for p in pay("ENTRY_FILL")}
        odt = pd.to_datetime(m.t[od.decision_idx.to_numpy()], utc=True) + MIN
        r["orders"] = [len(eo), len(od)]
        r["orders_equal"] = bool(len(eo) == len(od) and (eo["T"].to_numpy() == odt.to_numpy()).all()
                                 and (eo.side.to_numpy() == od.side.to_numpy()).all()
                                 and (eo.weight.to_numpy() == od.weight.to_numpy()).all()
                                 and np.array_equal([t.value in fills for t in eo["T"]], od.filled.to_numpy())
                                 and np.array_equal(eo.price.to_numpy(), [b5.b2.limit_price(m.c[i], s_, 2) for i, s_ in
                                                                          zip(od.decision_idx, od.side)]))
        # trades: EXIT_FILL ledger + open state vs research trades
        led = pay("EXIT_FILL")
        s = rep["states"][book]
        if s["status"] in ("OPEN", "EXIT_PENDING"):
            led.append({"side": s["side"], "weight": s["w"], "decision_time": s["dec_time"], "entry_time": s["entry_time"],
                        "entry_px": s["entry_px"], "exit_decision_time": s.get("exit_dec_time"), "exit_time": None,
                        "exit_px": np.nan})
        t_ns = lambda idx: np.where(np.asarray(idx) >= 0, m.t[np.maximum(np.asarray(idx), 0)], -1)  # noqa: E731
        got = pd.DataFrame(led)
        r["trades"] = [len(got), len(tr)]
        same = len(got) == len(tr)
        if same:
            exp_xd = np.where(tr.exit_decision_idx >= 0, t_ns(tr.exit_decision_idx) + MIN.value, -1)
            checks = {
                "decision_time_bar_plus_1m": (got.decision_time.to_numpy() == t_ns(tr.decision_idx) + MIN.value).all(),
                "entry_minute": (got.entry_time.to_numpy() == t_ns(tr.entry_idx)).all(),
                "exit_decision_time": (got.exit_decision_time.fillna(-1).astype("int64").to_numpy() == exp_xd).all(),
                "exit_minute": (got.exit_time.fillna(-1).astype("int64").to_numpy() == t_ns(tr.exit_idx)).all(),
                "entry_price": (got.entry_px.to_numpy() == tr.entry_px.to_numpy()).all(),
                "exit_price": np.array_equal(got.exit_px.to_numpy(float), tr.exit_px.to_numpy(float), equal_nan=True),
                "side": (got.side.to_numpy() == tr.side.to_numpy()).all(),
                "frozen_weight": (got.weight.to_numpy() == tr.entry_weight_frozen.to_numpy()).all()}
            r["trade_checks"] = {x: bool(v) for x, v in checks.items()}
            same = all(r["trade_checks"].values())
        r["trades_equal"] = bool(same)
        r["closed"] = int((~tr.open_at_end).sum())
        r["status_at_end"] = s["status"]
        # stored trades table rows == research net4_full of the closed trades
        tt = rep["trades"].loc[rep["trades"].book == book].sort_values("entry_time", ignore_index=True)
        rn = bk_ref.net4_full[~tr.open_at_end.to_numpy()]
        r["trades_table"] = [len(tt), len(rn)]
        r["trades_table_net_max_abs_diff"] = float(np.max(np.abs(tt.net_bps.to_numpy() - rn), initial=0.0)) \
            if len(tt) == len(rn) else None
        # 1m P&L of the stored ledger (Book over klines_1m from the start day) vs research
        with PaperStore(rep["path"]) as store:
            bk, mm, _ = g3.book_of(g3.closed_trades(store.connection, book), s, k, f, start, end)
        p_paper, p_ref = bk.pnl[:mm.N], bk_ref.pnl[a:]
        r["pnl_1m_max_abs_diff"] = float(np.max(np.abs(p_paper - p_ref))) if len(p_paper) == len(p_ref) else None
        a_t, b_t = wb["TEST"]
        r["TEST_net4"] = [float(p_paper.sum()), bk_ref.window(a_t, b_t)[f"{SIDE_OF[book]}_net4"]]
        dd = rep["daily"].loc[rep["daily"].book == book]
        r["daily_sum_vs_TEST"] = float(dd.net_bps.sum() - r["TEST_net4"][1])
        total += r["TEST_net4"][0]
        r["match"] = bool(r["decision_T_equal"] and r["side_equal"] and r["weight_max_abs_diff"] <= W_TOL
                          and r["orders_equal"] and r["trades_equal"]
                          and r["trades_table_net_max_abs_diff"] is not None
                          and r["trades_table_net_max_abs_diff"] <= TOL
                          and r["pnl_1m_max_abs_diff"] is not None and r["pnl_1m_max_abs_diff"] <= PNL_TOL
                          and abs(r["TEST_net4"][0] - r["TEST_net4"][1]) <= TOL and abs(r["daily_sum_vs_TEST"]) <= TOL)
        ok &= r["match"]
        out["books"][book] = r
    out["combined_TEST_net4"] = total
    out["combined_TEST_vs_3299.0488"] = total - PRIMARY_REF["TEST"]
    out["event_counts"] = rep["events"].groupby(["book", "event_type"]).size().to_dict()
    out["event_counts"] = {f"{a_}|{b_}": int(v) for (a_, b_), v in out["event_counts"].items()}
    out["event_hashes"] = all(set(rep["events"].loc[rep["events"].book == b, "code_hash"]) == {g3.behavior_hash(b, start)}
                              for b in g3.SLEEVES)
    out["health"] = rep["health"].to_dict("records")
    out["match"] = bool(ok and abs(out["combined_TEST_vs_3299.0488"]) <= 5e-5 and out["event_hashes"]
                        and (rep["health"].stale == 0).all() and rep["health"].last_error.isna().all())
    return out


def stored_ledger(rep: dict, start: pd.Timestamp) -> dict:
    """Replay EXIT_FILL ledger vs the run's stored pick trades (bar time) entered since the flat start."""
    out, ok = {}, True
    for book, lab in (("G3_LONG", "LONG_DEV_PICK"), ("G3_SHORT", "SHORT_DEV_PICK")):
        ref = pd.read_parquet(RUN / "trades" / f"{lab}.parquet")
        ref = ref.loc[(ref.side == g3.SLEEVES[book][0]) & (ref.decision_time + MIN >= start)
                      & ~ref.open_at_end].reset_index(drop=True)
        ev = rep["events"]
        got = pd.DataFrame([json.loads(p) for p in ev.loc[(ev.book == book) & (ev.event_type == "EXIT_FILL"), "payload"]])
        good = len(got) == len(ref) and bool(
            (pd.to_datetime(got.decision_time, utc=True) == ref.decision_time + MIN).all()
            and (pd.to_datetime(got.exit_decision_time, utc=True) == ref.exit_decision_time + MIN).all()
            and (pd.to_datetime(got.entry_time, utc=True) == ref.entry_time).all()
            and (pd.to_datetime(got.exit_time, utc=True) == ref.exit_time).all()
            and (got.entry_px.to_numpy() == ref.entry_px.to_numpy()).all()
            and (got.exit_px.to_numpy() == ref.exit_px.to_numpy()).all())
        out[book] = {"closed": [len(got), len(ref)], "match": good}
        ok &= good
    out["match"] = bool(ok)
    return out


def live_db_overlap(k: pd.DataFrame, f: pd.DataFrame) -> dict | None:
    """Read-only: live DB klines_1m / funding vs the snapshot on their overlap (live-apply data check)."""
    if not LIVE_DB.exists():
        return None
    with closing(sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)) as c:
        lk = pd.read_sql_query("SELECT open_time,open,high,low,close,volume,taker_buy_base_volume FROM klines_1m "
                               "WHERE open_time < '2026-10-08'", c)
        lf = pd.read_sql_query("SELECT time,rate FROM funding WHERE time < '2026-10-08'", c)
    lk["open_time"] = pd.to_datetime(lk.open_time, utc=True)
    j = lk.merge(k, on="open_time", suffixes=("_live", "_snap"))
    cols = ("open", "high", "low", "close", "volume", "taker_buy_base_volume")
    lf["time"] = pd.to_datetime(lf.time, utc=True, format="mixed")
    jf = lf.merge(f.assign(time=pd.to_datetime(f.time, utc=True, format="mixed")), on="time", how="outer",
                  suffixes=("_live", "_snap"))
    return {"klines_overlap_rows": len(j), "klines_live_rows": len(lk),
            "klines_rows_differing": int((~np.all([j[f"{c}_live"] == j[f"{c}_snap"] for c in cols], axis=0)).sum()),
            "funding_rows": [len(lf), len(f)], "funding_rows_differing": int((jf.rate_live != jf.rate_snap).sum())}


def run_all() -> dict:
    b5 = g3.engine()
    b2 = b5.b2
    minutes, _, _, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    cells = [(o, p) for o in b5.OFFSETS for p in b5.PENS]
    report = {"run": RUN.name, "engine_sha256": b5.provenance.file_sha256(g3.ENGINE), "code_hash": g3.code_hash(),
              "sleeve_ids": {b: g3.sleeve_id(b) for b in g3.SLEEVES},
              "sleeve_vs_combined": sleeve_vs_combined(m, research_runs(m, st, dec4, 0, cells))}
    start, end = b2.SPLIT, b2.END
    lo = m.idx(start) - 1                        # decision bar of T = start
    ref = research_runs(m, st, dec4, lo, [b5.PRIMARY])
    k, f = snapshot_inputs()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "paper.sqlite"
        rep = replay(k, f, start, end, path)
        rep["path"] = path
        report["paper_incremental_flat_start_2026"] = compare(rep, ref, m, st, lo, k, f, start, end)
        report["stored_ledger"] = stored_ledger(rep, start)
    report["live_db_overlap"] = live_db_overlap(k, f)
    report["match"] = bool(report["sleeve_vs_combined"]["match"] and report["paper_incremental_flat_start_2026"]["match"]
                           and report["stored_ledger"]["match"])
    return report


def main() -> None:
    report = run_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, default=str))
    print("MATCH" if report["match"] else "MISMATCH", OUT)


if __name__ == "__main__":
    main()
