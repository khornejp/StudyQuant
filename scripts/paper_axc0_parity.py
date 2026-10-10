"""B3_AXC0 / K04_AXC0 paper-vs-sim parity on the R2-54 FINAL snapshot, 2026-10-01 .. 2026-10-08 (flat start; both
R2-56 ledgers are flat at 2026-10-01 00:00).

  sim    scripts/sim_r2_56_replay.py path: r2_55 AXC0 table, SimConfig(causal_guard=True), W10 k, PESS funding.
  paper  catalog.run_book (raw_table -> ax_table -> core.simulate with paper E binding, k, config, funding repricing)
         with every opening signal decided at its signal time T. live_table is the identity then (a moved row at T
         would only collide with its own state copy), so it is bypassed for this check.
  live   diagnostic, not a gate: the same run with the real live_table and every signal decided at T + 1 min (the
         earliest a live cycle can decide; live entries are at least 1 min later than the sim's).
  ref    out/k45_rl_r2_48_20261007/r2_56/{id}_AXC0_positions_2026.parquet, positions entered in the window.

Gates (every one must hold, else match=false):
  sim_vs_ref    the full sim position list == the full R2-56 list in the window (count, times, sides, net < 1e-6 bps)
  paper_vs_ref  paper closed positions == R2-56 positions not closed by data_end (count, times, sides, net)
  open_suffix   R2-56 positions closed by data_end (exit B - 1 min) == the paper open position (count 0 or 1, entry
                time, side) == EXPECTED_OPEN
  x3            paper_catalog._x3 on the paper source (leverage.simulate_book) == an independent 3x compounding of the
                sim legs ($100, notional 3 x balance, 4 bps round trip on notional, PESS funding on notional); no
                liquidation; open x3 position entry / side / notional
Writes r2_56/paper_axc0_parity.json.

Usage: venv_btcusdt\\Scripts\\python.exe scripts\\paper_axc0_parity.py
"""
from __future__ import annotations
import json, sys
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant.paper import catalog  # noqa: E402
import paper_catalog  # noqa: E402
import sim_adaptive_exit as ax  # noqa: E402
import sim_r2_55 as r255  # noqa: E402
import sim_strategy_rolling as plan2  # noqa: E402

O = ROOT / "out/k45_rl_r2_48_20261007"
A, B = pd.Timestamp("2026-10-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
TOL, USD_TOL = 1e-6, 1e-9
EXPECTED_OPEN = {"B3_AXC0": (pd.Timestamp("2026-10-07T13:31Z"), -1), "K04_AXC0": None}   # R2-56 data_end suffix
COLS = ["entry_time", "exit_time", "side", "net_bps"]
X3_COLS = ["notional_usd", "funding_usd", "pnl_usd", "balance_after_usd"]


def decided_at_signal(name: str, ctx, lag: pd.Timedelta = pd.Timedelta(0)) -> pd.DataFrame:
    table = catalog.raw_table(name, ctx)
    t = pd.DatetimeIndex(table.loc[catalog._opens(table), "decision_time"].drop_duplicates())
    t = t[(t >= A) & (t < B)]
    return pd.DataFrame({"book": name, "signal_time": t, "decision_time": t + lag, "status": "decided",
                         "prediction_ts": t, "available_at": t, "decided_at": t, "model_id": "parity"},
                        columns=catalog.DECISION_COLUMNS)


def frame(df: pd.DataFrame) -> list[dict]:
    return [{k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in r.items()} for r in df.to_dict("records")]


def same(x: pd.DataFrame, y: pd.DataFrame) -> dict:
    keys = len(x) == len(y) and (x.entry_time.values == y.entry_time.values).all() and \
        (x.exit_time.values == y.exit_time.values).all() and (x.side.values == y.side.values).all()
    diff = float(np.abs(x.net_bps.to_numpy(float) - y.net_bps.to_numpy(float)).max()) if keys and len(x) else None
    return {"n": [len(x), len(y)], "times_sides_match": bool(keys), "max_abs_net_diff_bps": diff,
            "match": bool(keys) and (diff is None or diff < TOL)}


def expected_x3(legs: pd.DataFrame, funding: pd.DataFrame) -> dict:
    """Independent 3x compounding of the sim legs; the data_end leg is the open position (not closed)."""
    times = pd.to_datetime(funding.time, utc=True).tolist()
    rates = funding.rate.astype(float).tolist()
    balance, rows, open_ = 100.0, [], None
    for leg in legs.sort_values("entry_time").itertuples(index=False):
        side, entry, exit_ = int(leg.side), pd.Timestamp(leg.entry_time), pd.Timestamp(leg.exit_time)
        notional = 3.0 * balance
        if leg.exit_reason == "data_end":
            open_ = {"entry_time": entry, "side": side, "notional_usd": notional}
            break
        flows = [(t, -side * notional * r) for t, r in zip(times, rates) if entry <= t <= exit_]
        funding_usd = sum(c for t, c in flows if entry < t < exit_ or c < 0)        # PESS at both boundaries
        pnl = notional * side * (leg.exit_price / leg.entry_price - 1.0) + funding_usd - notional * 4.0 / 1e4
        rows.append({"entry_time": entry, "exit_time": exit_, "side": side, "notional_usd": notional,
                     "funding_usd": funding_usd, "pnl_usd": pnl, "balance_after_usd": balance + pnl})
        balance += pnl
    return {"trades": pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", *X3_COLS]), "open": open_,
            "balance": balance}


def x3_parity(name: str, trades: pd.DataFrame, sim_legs: pd.DataFrame, ctx, funding: pd.DataFrame) -> dict:
    x3 = paper_catalog._x3(name, trades, ctx.minutes, funding, A, B)
    want = expected_x3(sim_legs, funding)
    got = x3.trades if len(x3.trades) else pd.DataFrame(columns=["entry_time", "exit_time", "side", "liquidated",
                                                                 *X3_COLS])
    keys = len(got) == len(want["trades"]) and all(
        (got[c].values == want["trades"][c].values).all() for c in ("entry_time", "exit_time", "side"))
    liquidated = bool(got.liquidated.astype(bool).any()) if len(got) else False
    diffs = {c: float(np.abs(got[c].to_numpy(float) - want["trades"][c].to_numpy(float)).max())
             for c in X3_COLS} if keys and len(got) else {}
    held, exp = x3.position, want["open"]
    open_ok = (held is None and exp is None) or (
        held is not None and exp is not None and pd.Timestamp(held["entry_time"]) == exp["entry_time"]
        and int(held["side"]) == exp["side"] and abs(float(held["notional_usd"]) - exp["notional_usd"]) < USD_TOL)
    balance = [float(x3.state["balance_usd"]), float(want["balance"])]
    out = {"n": [len(got), len(want["trades"])], "times_sides_match": bool(keys), "liquidated": liquidated,
           "max_abs_diff_usd": diffs, "balance_usd": balance, "status": x3.state["status"],
           "open_match": bool(open_ok),
           "open": None if held is None else {"entry_time": str(held["entry_time"]), "side": int(held["side"]),
                                              "notional_usd": float(held["notional_usd"])},
           "trades": frame(got[["entry_time", "exit_time", "side", *X3_COLS, "exit_reason"]]) if len(got) else []}
    out["match"] = bool(keys and not liquidated and open_ok and all(v < USD_TOL for v in diffs.values())
                        and abs(balance[0] - balance[1]) < USD_TOL and x3.state["status"] == "RUNNING")
    return out


def book_parity(name: str, ctx, settle: pd.DataFrame, sel: pd.DataFrame, sb) -> dict:
    spec_id = catalog.BOOKS[name][0]
    times = pd.DatetimeIndex(ctx.minutes.open_time)
    k = float(sel.loc[(sel.id == spec_id) & (sel.window == r255.LAST_WINDOW), "k"].iloc[0])
    assert k == catalog.book_k(spec_id, axc0=True)
    table = r255.ax_table(ctx, spec_id, True)
    e, e_min = ax.e_matrix(ctx.regime, times, ax.heads(spec_id))
    cfg = replace(ax.CONFIG, close_at_end=True, fee_per_side=r255.FEE4, causal_guard=True)
    with sb.ledger_settlements(settle):
        sim_legs = ax.run_ax(table, ctx.minutes, e, e_min, A, B, cfg, np.full(len(times), k)).trades
    sim = plan2.positions(sim_legs)[COLS].reset_index(drop=True)
    live_table = catalog.live_table
    catalog.live_table = lambda table, decisions: table
    try:
        trades, _, held = catalog.run_book(name, ctx, settle, A, B, decided_at_signal(name, ctx))
    finally:
        catalog.live_table = live_table
    lt, _, lheld = catalog.run_book(name, ctx, settle, A, B, decided_at_signal(name, ctx, pd.Timedelta(minutes=1)))
    live = lt.loc[lt.boundary.eq("PESS"), COLS] if len(lt) else pd.DataFrame(columns=COLS)
    paper = trades.loc[trades.boundary.eq("PESS"), COLS] if len(trades) else pd.DataFrame(columns=COLS)
    paper = paper.sort_values("entry_time").reset_index(drop=True)
    ref = pd.read_parquet(O / f"r2_56/{spec_id}_AXC0_positions_2026.parquet")
    ref = ref.loc[ref.entry_time >= A, COLS].reset_index(drop=True)
    data_end = ref.exit_time.eq(B - pd.Timedelta(minutes=1))
    suffix, closed_ref = ref.loc[data_end], ref.loc[~data_end].reset_index(drop=True)
    expected = EXPECTED_OPEN[name]
    got = None if held is None else (pd.Timestamp(held["entry_time"]), int(held["side"]))
    ref_open = [(t, int(s)) for t, s in zip(suffix.entry_time, suffix.side)]
    open_suffix = {"ref_data_end_positions": frame(suffix),
                   "paper_open": None if got is None else {"entry_time": str(got[0]), "side": got[1]},
                   "expected": None if expected is None else {"entry_time": str(expected[0]), "side": expected[1]},
                   "match": (got is None and expected is None and not ref_open) or
                            (got is not None and got == expected and ref_open == [got] and bool(data_end.iloc[-1]))}
    out = {"k": k, "sim_vs_ref": same(sim, ref), "paper_vs_ref": same(paper, closed_ref), "open_suffix": open_suffix,
           "x3": x3_parity(name, trades, sim_legs, ctx, settle),
           "paper_net_4bps_closed": float(paper.net_bps.sum()), "ref_net_4bps_closed": float(closed_ref.net_bps.sum()),
           "live_plus_1min_diagnostic": {"positions": int(len(live)),
                                          "net_4bps_closed": float(live.net_bps.sum()) if len(live) else 0.0,
                                          "open": None if lheld is None else str(lheld["entry_time"]),
                                          "positions_list": frame(live.reset_index(drop=True))},
           "paper_positions": frame(paper), "ref_positions": frame(ref)}
    out["match"] = bool(out["sim_vs_ref"]["match"] and out["paper_vs_ref"]["match"] and open_suffix["match"]
                        and out["x3"]["match"])
    return out


def run_all() -> dict:
    run = r255.stageb_runner()
    ctx, _, settle = run.test_context()
    sel = pd.read_csv(O / "r2_55/selection/selected_k.csv")
    report = {"window": [str(A), str(B)], "snapshot_manifest_sha256": run.verify_snapshot(read_frames=False)[
        "manifest_sha256"], "books": {n: book_parity(n, ctx, settle, sel, run.sb) for n in catalog.AXC0_BOOKS}}
    report["match"] = all(b["match"] for b in report["books"].values())
    return report


def main() -> None:
    report = run_all()
    path = O / "r2_56/paper_axc0_parity.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({n: {k: v for k, v in b.items() if not k.endswith("_positions") and k != "x3"} | {
        "x3": {k: v for k, v in b["x3"].items() if k != "trades"}} for n, b in report["books"].items()},
        indent=1, default=str))
    print("MATCH" if report["match"] else "MISMATCH", path)


if __name__ == "__main__":
    main()
