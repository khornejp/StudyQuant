"""B3_AXC0 / K04_AXC0 paper-vs-sim parity on the R2-54 FINAL snapshot, 2026-10-01 .. 2026-10-08 (flat start; both
R2-56 ledgers are flat at 2026-10-01 00:00).

  sim    scripts/sim_r2_56_replay.py path: r2_55 AXC0 table, SimConfig(causal_guard=True), W10 k, PESS funding.
  paper  catalog.run_book (raw_table -> ax_table -> core.simulate with paper E binding, k, config, funding repricing)
         with every opening signal decided at its signal time T. live_table is the identity then (a moved row at T
         would only collide with its own state copy), so it is bypassed for this check.
  live   diagnostic, not a gate: the same run with the real live_table and every signal decided at T + 1 min (the
         earliest a live cycle can decide; live entries are at least 1 min later than the sim's).
  ref    out/k45_rl_r2_48_20261007/r2_56/{id}_AXC0_positions_2026.parquet, positions entered in the window.

Positions must match exactly (entry/exit time, side) and net within 1e-6 bps; the last R2-56 position closed by
data_end must be the paper's open position. Writes r2_56/paper_axc0_parity.json.

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
import sim_adaptive_exit as ax  # noqa: E402
import sim_r2_55 as r255  # noqa: E402
import sim_strategy_rolling as plan2  # noqa: E402

O = ROOT / "out/k45_rl_r2_48_20261007"
A, B = pd.Timestamp("2026-10-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
TOL = 1e-6


def decided_at_signal(name: str, ctx, lag: pd.Timedelta = pd.Timedelta(0)) -> pd.DataFrame:
    table = catalog.raw_table(name, ctx)
    t = pd.DatetimeIndex(table.loc[catalog._opens(table), "decision_time"].drop_duplicates())
    t = t[(t >= A) & (t < B)]
    return pd.DataFrame({"book": name, "signal_time": t, "decision_time": t + lag, "status": "decided",
                         "prediction_ts": t, "available_at": t, "decided_at": t, "model_id": "parity"},
                        columns=catalog.DECISION_COLUMNS)


def frame(df: pd.DataFrame) -> list[dict]:
    return [{k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in r.items()} for r in df.to_dict("records")]


def main() -> None:
    run = r255.stageb_runner()
    ctx, _, settle = run.test_context()
    sel = pd.read_csv(O / "r2_55/selection/selected_k.csv")
    times = pd.DatetimeIndex(ctx.minutes.open_time)
    report = {"window": [str(A), str(B)], "snapshot_manifest_sha256": run.verify_snapshot(read_frames=False)[
        "manifest_sha256"], "books": {}}
    for name in catalog.AXC0_BOOKS:
        spec_id = catalog.BOOKS[name][0]
        k = float(sel.loc[(sel.id == spec_id) & (sel.window == r255.LAST_WINDOW), "k"].iloc[0])
        assert k == catalog.book_k(spec_id, axc0=True)
        table = r255.ax_table(ctx, spec_id, True)
        e, e_min = ax.e_matrix(ctx.regime, times, ax.heads(spec_id))
        cfg = replace(ax.CONFIG, close_at_end=True, fee_per_side=r255.FEE4, causal_guard=True)
        with run.sb.ledger_settlements(settle):
            sim = plan2.positions(ax.run_ax(table, ctx.minutes, e, e_min, A, B, cfg, np.full(len(times), k)).trades)
        live_table = catalog.live_table
        catalog.live_table = lambda table, decisions: table
        try:
            trades, _, held = catalog.run_book(name, ctx, settle, A, B, decided_at_signal(name, ctx))
        finally:
            catalog.live_table = live_table
        lt, _, lheld = catalog.run_book(name, ctx, settle, A, B, decided_at_signal(name, ctx, pd.Timedelta(minutes=1)))
        live = lt.loc[lt.boundary.eq("PESS"), ["entry_time", "exit_time", "side", "net_bps"]] if len(lt) else lt
        paper = trades.loc[trades.boundary.eq("PESS")] if len(trades) else pd.DataFrame(
            columns=["entry_time", "exit_time", "side", "net_bps"])
        paper = paper[["entry_time", "exit_time", "side", "net_bps"]].sort_values("entry_time").reset_index(drop=True)
        ref = pd.read_parquet(O / f"r2_56/{spec_id}_AXC0_positions_2026.parquet")
        ref = ref.loc[ref.entry_time >= A, ["entry_time", "exit_time", "side", "net_bps"]].reset_index(drop=True)
        last_open = bool(len(ref)) and held is not None and ref.exit_time.iloc[-1] == B - pd.Timedelta(minutes=1)
        closed_ref = ref.iloc[:-1] if last_open else ref
        closed_sim = sim.iloc[:len(closed_ref)][["entry_time", "exit_time", "side", "net_bps"]].reset_index(drop=True)

        def same(x, y) -> dict:
            keys = len(x) == len(y) and (x.entry_time.values == y.entry_time.values).all() and \
                   (x.exit_time.values == y.exit_time.values).all() and (x.side.values == y.side.values).all()
            diff = float(np.abs(x.net_bps.to_numpy(float) - y.net_bps.to_numpy(float)).max()) if keys and len(x) else None
            return {"n": [len(x), len(y)], "times_sides_match": bool(keys), "max_abs_net_diff_bps": diff,
                    "match": bool(keys) and (diff is None or diff < TOL)}

        open_match = (not last_open and held is None) or (last_open and pd.Timestamp(held["entry_time"]) ==
                                                          ref.entry_time.iloc[-1] and int(held["side"]) == int(ref.side.iloc[-1]))
        out = {"k": k, "paper_vs_ref": same(paper, closed_ref), "sim_vs_ref": same(closed_sim, closed_ref),
               "open_position_match": bool(open_match),
               "paper_net_4bps_closed": float(paper.net_bps.sum()), "ref_net_4bps_closed": float(closed_ref.net_bps.sum()),
               "live_plus_1min_diagnostic": {"positions": int(len(live)), "net_4bps_closed": float(live.net_bps.sum()) if len(live) else 0.0,
                                              "open": None if lheld is None else str(lheld["entry_time"]),
                                              "positions_list": frame(live.reset_index(drop=True)) if len(live) else []},
               "paper_open": None if held is None else {"entry_time": str(held["entry_time"]), "side": int(held["side"])},
               "paper_positions": frame(paper), "ref_positions": frame(ref)}
        out["match"] = out["paper_vs_ref"]["match"] and out["sim_vs_ref"]["match"] and out["open_position_match"]
        report["books"][name] = out
    report["match"] = all(b["match"] for b in report["books"].values())
    path = O / "r2_56/paper_axc0_parity.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({n: {k: v for k, v in b.items() if not k.endswith("_positions")} for n, b in report["books"].items()},
                     indent=1, default=str))
    print("MATCH" if report["match"] else "MISMATCH", path)


if __name__ == "__main__":
    main()
