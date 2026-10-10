"""G3_COMBINED paper-vs-research parity (Codex B5 review "필수 parity").

  research  out/run_new_model_batch5_20261010.py data path (batch-2 load_all: DEV archive + R2-54 FINAL snapshot
            market / funding_model_input), build_state, core_signal, batch-2 simulate / Book.
  sleeves   independent re-simulation per sleeve (long-only S180-c0-W180-P65, short-only F180-c0-V-ENS), 2 sides x
            6 cells (offset 2/5 x pen 0.5/1/2) x 4 windows = 48 side net4 == combined_book.json cells_net4 (derived
            from the two-sided runs); combined primary == 28783.9741 / 20146.5468 / 8637.4274 / 3299.0488.
  paper     btcusdt_quant.paper.g3 on paper-table inputs: snapshot market_1m as klines_1m (live path from 2026-01-01)
            and the snapshot copy of the live funding table, DEV archive warm-up; full replay from 2020-01-01 (same
            state as research) and a flat start at 2026-01-01.

Gates: market/funding arrays equal; decision side exact, weight atol 1e-12; trades (decision/entry/exit minute,
order/fill prices, side, frozen weight) exact; 1m P&L exact; window net4 atol 1e-6; paper decision_time ==
stored research decision_time + 1m; gross <= 2. Writes out/new_model_batch5_20261010/g3_paper/paper_g3_parity.json.

Usage: venv_btcusdt\\Scripts\\python.exe scripts\\paper_g3_parity.py
"""
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.paper import g3  # noqa: E402

RUN = ROOT / "out/new_model_batch5_20261010/NM-B5-20261010T080025Z-c55285f2"
OUT = ROOT / "out/new_model_batch5_20261010/g3_paper/paper_g3_parity.json"
LIVE_DB = ROOT / "artifacts/live/live.sqlite"
PRIMARY_REF = {"DEV-FULL": 28783.9741, "DEV-A": 20146.5468, "DEV-B": 8637.4274, "TEST": 3299.0488}
TOL, W_TOL = 1e-6, 1e-12
TRADE_COLS = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_decision_idx", "exit_idx",
              "exit_px", "open_at_end"]


def research_sleeves(m, st, dec4, lo: int = 0) -> dict:
    """Independent sleeve runs on the research data for every execution cell."""
    b5 = g3.engine()
    b2 = b5.b2
    out = {}
    for sleeve in g3.SLEEVES:
        side, w = g3.sleeve_signal(st, sleeve)
        for off in b5.OFFSETS:
            for pen in b5.PENS:
                tr, od = b2.simulate(m, "state", dec4, side, w, off, b2.TTL_TREND, pen, lo, m.N)
                out[(sleeve, off, pen)] = (tr, od, b2.Book(m, tr, od, lo, m.N), side, w)
    return out


def sleeve_vs_combined(m, runs: dict) -> dict:
    b5 = g3.engine()
    comb = json.loads((RUN / "combined_book.json").read_text(encoding="utf-8"))
    wb = b5.b3.window_bounds(m)
    diffs, n = {}, 0
    primary = {k: 0.0 for k in wb}
    for (sleeve, off, pen), (_, _, book, _, _) in runs.items():
        for k, (a, b) in wb.items():
            got = book.window(a, b)[f"{sleeve}_net4"]
            ref = comb["cells_net4"][k][f"o{off}_p{pen}"][sleeve]
            n += 1
            diffs[f"{sleeve}|o{off}_p{pen}|{k}"] = got - ref
            if (off, pen) == b5.PRIMARY:
                primary[k] += got
    worst = max(abs(v) for v in diffs.values())
    prim = {k: {"got": v, "ref_4dp": PRIMARY_REF[k], "json": comb["windows_primary"][k]["net4"],
                "diff_vs_json": v - comb["windows_primary"][k]["net4"]} for k, v in primary.items()}
    ok = n == 48 and worst <= TOL and all(abs(p["diff_vs_json"]) <= TOL and abs(p["got"] - p["ref_4dp"]) <= 5e-5
                                          for p in prim.values())
    return {"n_compared": n, "max_abs_diff": worst, "n_diff_gt_1e-6": sum(abs(v) > TOL for v in diffs.values()),
            "combined_primary": prim, "match": bool(ok)}


def same_trades(x: pd.DataFrame, y: pd.DataFrame) -> bool:
    return len(x) == len(y) and x[TRADE_COLS].reset_index(drop=True).equals(y[TRADE_COLS].reset_index(drop=True))


def compare(paper: dict, runs: dict, m_res, lo: int) -> dict:
    """paper g3.simulate output vs the research independent sleeves at the primary cell (same lo)."""
    b5 = g3.engine()
    mp = paper["m"]
    out = {"market_equal": bool(all(np.array_equal(getattr(mp, a), getattr(m_res, a))
                                    for a in ("t", "o", "h", "l", "c", "ft", "fr"))), "sleeves": {}}
    pnl = np.zeros(m_res.N)
    wb = b5.b3.window_bounds(m_res)
    ok = out["market_equal"]
    for sleeve, s in paper["sleeves"].items():
        tr, od, book, side, w = runs[(sleeve, *b5.PRIMARY)]
        keep = paper["dec4"] >= lo
        r = {"decisions": int(keep.sum()),
             "side_equal": bool(np.array_equal(s["side"][keep], side[keep])),
             "weight_max_abs_diff": float(np.max(np.abs(s["w"][keep] - w[keep]), initial=0.0)),
             "nonflat_decisions": int((s["side"][keep] != 0).sum()),
             "trades": [len(s["tr"]), len(tr)], "trades_equal": same_trades(s["tr"], tr),
             "closed": int((~s["tr"].open_at_end).sum()), "orders_equal": bool(s["od"].equals(od)),
             "pnl_1m_equal": bool(np.array_equal(s["book"].pnl, book.pnl)),
             "funding_cashflows_equal": bool(np.array_equal(s["book"].f_cf, book.f_cf)
                                             and np.array_equal(s["book"].f_min, book.f_min))}
        r["window_net4"] = {k: [s["book"].window(a, b)[f"{sleeve}_net4"], book.window(a, b)[f"{sleeve}_net4"]]
                            for k, (a, b) in wb.items() if b > lo}
        r["window_max_abs_diff"] = max(abs(x - y) for x, y in r["window_net4"].values())
        r["match"] = bool(r["side_equal"] and r["weight_max_abs_diff"] <= W_TOL and r["trades_equal"] and
                          r["orders_equal"] and r["pnl_1m_equal"] and r["funding_cashflows_equal"]
                          and r["window_max_abs_diff"] <= TOL)
        ok &= r["match"]
        pnl += book.pnl
        out["sleeves"][sleeve] = r
    out["combined_pnl_1m_equal"] = bool(np.array_equal(paper["pnl"], pnl))
    out["combined_window_net4"] = {k: float(paper["pnl"][a:b].sum()) for k, (a, b) in wb.items() if b > lo}
    out["max_gross"] = float(paper["gross"].max())
    held = {k: b5.held_weight(s["book"]) > 1e-12 for k, s in paper["sleeves"].items()}
    out["overlap_minutes"] = int((held["long"] & held["short"]).sum())
    out["match"] = bool(ok and out["combined_pnl_1m_equal"] and out["max_gross"] <= 2 + 1e-12)
    return out


def stored_ledger(paper: dict) -> dict:
    """Paper ledger (decision_time = bar + 1m) vs the run's stored pick trades (decision_time = bar), sleeve side."""
    led = g3.ledger(paper)
    out, ok = {}, True
    for sleeve, lab in (("long", "LONG_DEV_PICK"), ("short", "SHORT_DEV_PICK")):
        side = g3.SLEEVES[sleeve][0]
        ref = pd.read_parquet(RUN / "trades" / f"{lab}.parquet")
        ref = ref.loc[ref.side == side].reset_index(drop=True)
        got = led.loc[led.sleeve == sleeve].reset_index(drop=True)
        n = len(got) == len(ref)
        checks = n and {
            "decision_time_plus_1m": bool((got.decision_time == ref.decision_time + pd.Timedelta(minutes=1)).all()),
            "exit_decision_time_plus_1m": bool((got.exit_decision_time.isna() == ref.exit_decision_time.isna()).all()
                                               and (got.exit_decision_time.dropna() == (ref.exit_decision_time
                                                    + pd.Timedelta(minutes=1)).dropna()).all()),
            "entry_time": bool((got.entry_time == ref.entry_time).all()),
            "exit_time": bool((got.exit_time.isna() == ref.exit_time.isna()).all()
                              and (got.exit_time.dropna() == ref.exit_time.dropna()).all()),
            "entry_price": bool((got.entry_price.to_numpy() == ref.entry_px.to_numpy()).all()),
            "exit_price": bool(np.array_equal(got.exit_price.to_numpy(), ref.exit_px.to_numpy(), equal_nan=True)),
            "weight": bool((got.weight.to_numpy() == ref.entry_weight_frozen.to_numpy()).all()),
            "net4_full_max_abs_diff": float(np.max(np.abs(got.net_bps.to_numpy() - ref.net4_full.to_numpy()),
                                                   initial=0.0))}
        good = bool(n and all(v for k, v in checks.items() if k != "net4_full_max_abs_diff")
                    and checks["net4_full_max_abs_diff"] <= TOL)
        out[sleeve] = {"n": [len(got), len(ref)], "checks": checks or None, "match": good}
        ok &= good
    daily = g3.daily(paper, "G3_COMBINED", pd.Timestamp("2020-01-01", tz="UTC"))
    ref_l = pd.read_parquet(RUN / "daily/LONG_DEV_PICK.parquet")
    ref_s = pd.read_parquet(RUN / "daily/SHORT_DEV_PICK.parquet")
    ref = ref_l.net4_long.to_numpy() + ref_s.net4_short.to_numpy()
    d = float(np.max(np.abs(daily.net_bps.to_numpy() - ref))) if len(daily) == len(ref) else np.inf
    out["daily"] = {"n": [len(daily), len(ref)], "max_abs_diff": d,
                    "components_sum_ok": bool(np.allclose(daily.gross_bps - daily.cost_bps + daily.funding_bps,
                                                          daily.net_bps, atol=1e-9))}
    out["match"] = bool(ok and d <= TOL and out["daily"]["components_sum_ok"])
    return out


def snapshot_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Snapshot copies of the paper tables, in the DB's text form."""
    snap = g3.engine().b2.SNAP
    k = pd.read_parquet(snap / "market_1m.parquet")
    k["open_time"] = pd.to_datetime(k.open_time, utc=True).map(lambda t: t.isoformat())
    f = pd.read_parquet(snap / "funding_live_table.parquet")
    return k, f


def live_db_overlap(k: pd.DataFrame, f: pd.DataFrame) -> dict | None:
    """Read-only: live DB klines_1m / funding vs the snapshot on their overlap (live-apply data check)."""
    if not LIVE_DB.exists():
        return None
    with sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True) as c:
        lk = pd.read_sql_query("SELECT open_time,open,high,low,close,volume,taker_buy_base_volume FROM klines_1m "
                               "WHERE open_time < '2026-10-08'", c)
        lf = pd.read_sql_query("SELECT time,rate FROM funding WHERE time < '2026-10-08'", c)
    lk["open_time"] = pd.to_datetime(lk.open_time, utc=True)
    sk = k.assign(open_time=pd.to_datetime(k.open_time, utc=True))
    j = lk.merge(sk, on="open_time", suffixes=("_live", "_snap"))
    cols = ("open", "high", "low", "close", "volume", "taker_buy_base_volume")
    lf["time"] = pd.to_datetime(lf.time, utc=True, format="mixed")
    sf = f.assign(time=pd.to_datetime(f.time, utc=True, format="mixed"))
    jf = lf.merge(sf, on="time", how="outer", suffixes=("_live", "_snap"))
    return {"klines_overlap_rows": len(j), "klines_live_rows": len(lk),
            "klines_rows_differing": int((~np.all([j[f"{c}_live"] == j[f"{c}_snap"] for c in cols], axis=0)).sum()),
            "funding_rows": [len(lf), len(sf)], "funding_rows_differing": int((jf.rate_live != jf.rate_snap).sum())}


def run_all() -> dict:
    b5 = g3.engine()
    b2 = b5.b2
    minutes, _, _, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    runs = research_sleeves(m, st, dec4)
    report = {"run": RUN.name, "engine_sha256": b5.provenance.file_sha256(g3.ENGINE),
              "sleeve_ids": {s: g3.sleeve_id(s) for s in g3.SLEEVES},
              "sleeve_vs_combined": sleeve_vs_combined(m, runs)}
    k, f = snapshot_frames()
    end = b2.END
    paper_full = g3.simulate(g3.market(k, f, end, live_from=b2.SPLIT), pd.Timestamp("2020-01-01", tz="UTC"))
    report["paper_full_replay"] = compare(paper_full, runs, m, 0)
    report["paper_full_replay"]["stored_ledger"] = stored_ledger(paper_full)
    report["paper_full_replay"]["match"] &= report["paper_full_replay"]["stored_ledger"]["match"]
    start = b2.SPLIT
    lo = m.idx(start) - 1
    runs_test = {key: v for key, v in research_sleeves(m, st, dec4, lo).items() if key[1:] == b5.PRIMARY}
    paper_test = g3.simulate(g3.market(k, f, end, live_from=b2.SPLIT), start)
    report["paper_flat_start_2026"] = compare(paper_test, runs_test, m, lo)
    led = g3.ledger(paper_test)
    report["paper_flat_start_2026"]["ledger"] = {
        s: {"trades": int((led.sleeve == s).sum()), "closed": int(((led.sleeve == s) & ~led.open_at_end).sum()),
            "first_entry": str(led.loc[led.sleeve == s, "entry_time"].min())} for s in g3.SLEEVES}
    report["paper_flat_start_2026"]["decision_grid_ok"] = bool(
        (pd.DatetimeIndex(g3.decisions(paper_test)["T"]).hour % 4 == 0).all()
        and (pd.DatetimeIndex(g3.decisions(paper_test)["T"]).minute == 0).all())
    report["live_db_overlap"] = live_db_overlap(k, f)
    report["match"] = bool(report["sleeve_vs_combined"]["match"] and report["paper_full_replay"]["match"]
                           and report["paper_flat_start_2026"]["match"]
                           and report["paper_flat_start_2026"]["decision_grid_ok"])
    return report


def main() -> None:
    report = run_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, default=str))
    print("MATCH" if report["match"] else "MISMATCH", OUT)


if __name__ == "__main__":
    main()
