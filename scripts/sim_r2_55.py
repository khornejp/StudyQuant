"""R2-55 family state-exit repairs (freeze out/k45_rl_r2_48_20261007/r2_55_k0607_c0_freeze.json, amendments
REBASE_2026-10-10 suspended by REBASE_BACK_2026-10-10, and HISTORICAL_TEST_2026-10-10).

  select   pre-2026 rolling k selection for the 10 changed ids on their AXC0 tables (R2-52A procedure of
           scripts/sim_adaptive_exit.py: k in {1.0, 1.5, 2.0}, 4 bps validation minute-ledger P&L, tie -> 2.0; family
           repair only, no causal guard, as the AX k it is paired with). Registers 30 trials (5694 -> 5724).
  test     HISTORICAL_TEST: [2026-01-01, 2026-10-08) replay on the R2-54 FINAL snapshot (hash-verified) plus pre-2026
           warm-up; both arms (current R2-52A AX and AXC0) with SimConfig(causal_guard=True), flat start, last
           pre-2026 window (W10) k, 1 m MTM ledger with PESS funding at the actual settlement times, 4 bps (8 bps
           report/gate as frozen per pair). Per pair, four family PW stationary-bootstrap tests, Holm.
           Also the guard-only diagnostic (AX with vs without the guard) on all 29 current ids and K01_FLIP.
           Every test run is appended to r2_55/test/test_runs.jsonl and counted.

Usage: venv_btcusdt\\Scripts\\python.exe scripts\\sim_r2_55.py select [--workers 8]
       venv_btcusdt\\Scripts\\python.exe scripts\\sim_r2_55.py test [--workers 4]
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, sys, time, traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant.sim import analytics, costs, data, provenance, registry, rolling  # noqa: E402
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant  # noqa: E402
import sim_adaptive_exit as ax  # noqa: E402
import sim_strategy_rolling as plan2  # noqa: E402

O = ROOT / "out/k45_rl_r2_48_20261007"
FREEZE_PATH = O / "r2_55_k0607_c0_freeze.json"
FREEZE_SHA = "93da69ce3175b9bf6cca59fb2f46b43d06ac0b81d226346b04bc09141696379d"
PARENT_SHA = "d1d56efa3b35465059e24f30380b7f413a029a4384da2ed45056977327a0eced"     # R2-52A (REBASE_BACK)
OUT = O / "r2_55"
REGISTRY = ROOT / "out/sim_registry.jsonl"
REGISTRY_BASE, REGISTRY_AFTER = 5694, 5724                # REBASE_BACK trials
K_VALUES = (1.0, 1.5, 2.0)
A, B = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
FEE4, FEE8 = 2.0, 4.0
MIN_POSITIONS = 30
REPS, SEED, ALPHA = 2000, 0, 0.05
LAST_WINDOW = "W10"
_G: dict = {}


def freeze() -> dict:
    digest = provenance.file_sha256(FREEZE_PATH)
    if digest != FREEZE_SHA:
        raise SystemExit(f"R2-55 freeze sha256 {digest} != {FREEZE_SHA}")
    f = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if f["status"] != "FROZEN" or [a["id"] for a in f["amendments"]] != [
            "REBASE_2026-10-10", "REBASE_BACK_2026-10-10", "HISTORICAL_TEST_2026-10-10"]:
        raise SystemExit("unexpected freeze status or amendments")
    if provenance.file_sha256(O / "r2_52a_exit_freeze.json") != PARENT_SHA:
        raise SystemExit("R2-52A parent freeze changed")
    return f


def changed_ids(f: dict) -> list[str]:
    ids = list(f["scope"]["changed_ids"])
    if len(ids) != f["scope"]["n_changed_ids"] or sorted(ids) != sorted(i for i, s in CATALOG.items() if s.axc0):
        raise SystemExit("changed ids do not match the AXC0 catalog")
    return ids


def families(f: dict) -> dict[str, list[str]]:
    return {k: list(v) for k, v in f["scope"]["families"].items()}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def code_hashes() -> dict:
    files = [Path(__file__).resolve(), ROOT / "scripts/sim_adaptive_exit.py", ROOT / "btcusdt_quant/sim/core.py",
             ROOT / "btcusdt_quant/sim/reference.py", ROOT / "btcusdt_quant/sim/costs.py"]
    out = {str(p.relative_to(ROOT)): provenance.file_sha256(p) for p in files}
    out["btcusdt_quant/sim/strategies"] = provenance.tree_sha256(ROOT / "btcusdt_quant/sim/strategies", "*.py")["sha256"]
    return out


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def ax_table(ctx: Context, spec_id: str, axc0: bool) -> pd.DataFrame:
    table, _ = build_variant(ctx, spec_id, False, "NATIVE", ax=True, axc0=axc0)
    return table.assign(e0_bps=ax.row_e0(table, ctx.regime, spec_id), e_col=ax.e_cols(table, spec_id).astype(float))


# ---------------------------------------------------------------- select
def _init_select() -> None:
    _G["ctx"] = Context.load(end=rolling.END)


def select_id(spec_id: str) -> dict:
    try:
        ctx = _G["ctx"]
        table = ax_table(ctx, spec_id, axc0=True)
        e, e_min = ax.e_matrix(ctx.regime, pd.DatetimeIndex(ctx.minutes.open_time), ax.heads(spec_id))
        rows = []
        for w in rolling.WINDOWS:
            scores = {k: ax.validation_pnl(table, ctx.minutes, e, e_min, w.val_start, w.val_end, ax.CONFIG, k)
                      for k in K_VALUES}
            rows.append({"id": spec_id, "window": w.name, "val_start": w.val_start, "val_end": w.val_end,
                         **{f"val_net_4bps_k{k}": v for k, v in scores.items()}, "k": ax.select_k(scores)})
        return {"id": spec_id, "status": "ok", "rows": rows}
    except Exception as error:
        return {"id": spec_id, "status": "error", "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=5)}


def select(args) -> None:
    f = freeze()
    ids = changed_ids(f)
    out = OUT / "selection"
    if (out / "selected_k.csv").exists():
        raise SystemExit("R2-55 k selection already recorded; never rerun (no reselection)")
    prior = registry.cumulative_trials(REGISTRY)
    if prior != REGISTRY_BASE:
        raise SystemExit(f"registry cumulative_trials {prior} != frozen base {REGISTRY_BASE}")
    end = rolling.END
    predictions = data.load_predictions(end=end)
    coverage = data.prediction_coverage(predictions, rolling.TRAIN_START, end)
    if coverage["retrain_after_timestamp"] or set(coverage["missing_days"]) - plan2.KNOWN_PREDICTION_GAPS:
        raise SystemExit(f"prediction availability check failed: {coverage}")
    started = time.time()
    with ProcessPoolExecutor(max_workers=min(args.workers, 8), initializer=_init_select) as pool:
        results = list(pool.map(select_id, ids))
    failed = [r for r in results if r["status"] != "ok"]
    if failed:
        print(json.dumps(failed, indent=1)); raise SystemExit("selection failed; nothing registered")
    frame = pd.DataFrame([row for r in results for row in r["rows"]])
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "selected_k.csv", index=False)
    config = {"experiment": "R2-55 AXC0 pre-2026 k selection", "exit_policy": "R2_52A", "k_values": str(list(K_VALUES)),
              "selection": "R2-52A rolling: per window 4 bps validation minute-ledger P&L from flat at val_start, "
                           "open position marked at val_end without exit fee; tie -> 2.0",
              "tables": "build_variant(ax=True, axc0=True): frozen family repair only; causal_guard off (as the "
                        "paired AX k)", "freeze_sha256": FREEZE_SHA, "windows": f"{rolling.WINDOWS[0].name}.."
                                                                               f"{rolling.WINDOWS[-1].name}"}
    inputs = plan2.input_hashes(end)
    registry.record(REGISTRY, {"experiment": "R2-55 AXC0 pre-2026 k selection (REBASE_BACK, R2-52A k 1/1.5/2)",
                               "n_trials": len(ids) * len(K_VALUES), "config": config, "input_hashes": inputs,
                               "result_summary": {"selected_k_last_window": {
                                   r["id"]: r["rows"][-1]["k"] for r in results}}})
    after = registry.cumulative_trials(REGISTRY)
    if after != REGISTRY_AFTER:
        raise SystemExit(f"registry after {after} != frozen {REGISTRY_AFTER}")
    dump(out / "manifest.json", {"created_utc": now(), "freeze": str(FREEZE_PATH.relative_to(ROOT)),
                                 "freeze_sha256": FREEZE_SHA, "parent_freeze_sha256": PARENT_SHA, "ids": ids,
                                 "config": config, "input_sha256": inputs, "prediction_coverage": coverage,
                                 "code_sha256": code_hashes(), "registry_before": prior, "registry_after": after,
                                 "selected_k": {r["id"]: {x["window"]: x["k"] for x in r["rows"]} for r in results},
                                 "runtime_seconds": round(time.time() - started, 1)})
    print(json.dumps({"registry": [prior, after], "W10": {r["id"]: r["rows"][-1]["k"] for r in results}}, indent=1))


# ---------------------------------------------------------------- historical test
def stageb_runner():
    spec = importlib.util.spec_from_file_location("r2_54_stageb_runner", ROOT / "out/run_r2_54_stageb.py")
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _init_test() -> None:
    run = stageb_runner()
    ctx, _, settle = run.test_context()
    _G.update(ctx=ctx, settle=settle, sb=run.sb)


def ledger(result, days) -> dict:
    tr = result.trades
    pos = plan2.positions(tr)
    admin = set(tr.loc[tr.exit_reason == "data_end", "position_id"])
    minute = result.minute_pnl
    cum = minute.cumsum()
    dd_min = float((cum.cummax().clip(lower=0) - cum).max()) if len(cum) else 0.0
    hold = (pos.exit_time - pos.entry_time).dt.total_seconds() / 3600.0 if len(pos) else pd.Series(dtype=float)
    exposure_min = float(hold.sum() * 60.0)
    last = minute.index[-1] if len(minute) else B
    open_age = [float((last - p.entry_time).total_seconds() / 3600.0) for p in pos.itertuples() if p.position_id in admin]
    return {"daily": ax.daily(minute, days), "net_bps": float(minute.sum()), "positions": int(len(pos)),
            "completed_positions": int(len(pos) - len(admin)), "data_end_positions": int(len(admin)),
            "worst_position_bps": float(pos.net_bps.min()) if len(pos) else None,
            "max_drawdown_bps": dd_min, "max_drawdown_daily_bps": ax._drawdown(ax.daily(minute, days)),
            "funding_bps": float(tr.funding_bps.sum()), "fee_bps": float(tr.fee_bps.sum()),
            "exit_reasons": tr.exit_reason.value_counts().to_dict(),
            "hold_hours_p50": float(hold.quantile(.5)) if len(hold) else None,
            "hold_hours_p95": float(hold.quantile(.95)) if len(hold) else None,
            "hold_hours_max": float(hold.max()) if len(hold) else None,
            "exposure_share": exposure_min / max(len(minute), 1),
            "open_position_age_hours_at_cutoff": open_age,
            "trades": tr}


def test_id(job: tuple) -> dict:
    spec_id, k_ax, k_c0 = job
    try:
        ctx, sb = _G["ctx"], _G["sb"]
        minutes = ctx.minutes
        times = pd.DatetimeIndex(minutes.open_time)
        e, e_min = ax.e_matrix(ctx.regime, times, ax.heads(spec_id))
        days = pd.date_range(A, B, freq="D", inclusive="left")
        base = replace(ax.CONFIG, close_at_end=True)
        current = ax_table(ctx, spec_id, False)
        arms = {"ax_guard": (current, True, k_ax), "ax_noguard": (current, False, k_ax)}
        if k_c0 is not None:
            arms["axc0_guard"] = (ax_table(ctx, spec_id, True), True, k_c0)
        out = {"id": spec_id, "status": "ok", "k_ax": k_ax, "k_axc0": k_c0}
        with sb.ledger_settlements(_G["settle"]):
            for name, (table, guard, k) in arms.items():
                for fee, tag in ((FEE4, "4bps"), (FEE8, "8bps")):
                    cfg = replace(base, fee_per_side=fee, causal_guard=guard)
                    res = ax.run_ax(table, minutes, e, e_min, A, B, cfg, np.full(len(minutes), k))
                    out[f"{name}_{tag}"] = ledger(res, days)
        return out
    except Exception as error:
        return {"id": spec_id, "status": "error", "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=8)}


def one_sided_test(x: np.ndarray) -> dict:
    """primary_test: centered PW stationary bootstrap, p = (1 + #(centered mean >= observed)) / (REPS + 1); 95%
    percentile interval from uncentered resamples; zero variance and NaN per bootstrap_edge_cases."""
    x = np.asarray(x, float)
    if not len(x) or not np.isfinite(x).all():
        return {"valid": False, "reason": "NaN or empty input", "p": None, "mean": None, "lower": None, "upper": None}
    mean = float(x.mean())
    if x.std() == 0:
        return {"valid": True, "reason": "zero_variance", "mean": mean, "lower": mean, "upper": mean, "block": 1.0,
                "p": 1 / (REPS + 1) if mean > 0 else 1.0}
    block = analytics.pw_block_length(x)
    means = x[analytics.stationary_indices(len(x), block, REPS, np.random.default_rng(SEED))].mean(axis=1)
    if not np.isfinite(means).all():
        return {"valid": False, "reason": "NaN in bootstrap output", "p": None, "mean": mean, "lower": None,
                "upper": None}
    centered = means - mean
    lower, upper = np.quantile(means, [.025, .975])
    return {"valid": True, "reason": "ok", "mean": mean, "lower": float(lower), "upper": float(upper), "block": block,
            "p": float((1 + np.sum(centered >= mean)) / (REPS + 1))}


def holm(pvalues: dict[str, float | None]) -> dict:
    """Holm step-down over exactly the given hypotheses; an invalid family keeps p = 1 in the ordering (cannot pass)."""
    names = sorted(pvalues, key=lambda n: (1.0 if pvalues[n] is None else pvalues[n], n))
    m, running, out = len(names), 0.0, {}
    for rank, name in enumerate(names):
        p = 1.0 if pvalues[name] is None else pvalues[name]
        running = max(running, min(1.0, (m - rank) * p))
        out[name] = {"rank": rank + 1, "raw_p": pvalues[name], "multiplier": m - rank, "adjusted_p": running}
    return out


def pair_result(r: dict) -> dict:
    s4, c4, s8, c8 = r["axc0_guard_4bps"], r["ax_guard_4bps"], r["axc0_guard_8bps"], r["ax_guard_8bps"]
    d4 = s4["daily"] - c4["daily"]
    d8 = s8["daily"] - c8["daily"]
    ws, wc = s4["worst_position_bps"], c4["worst_position_bps"]
    evidence = s4["completed_positions"] >= MIN_POSITIONS and c4["completed_positions"] >= MIN_POSITIONS
    gates = {"delta_4bps_gt_0": float(d4.sum()) > 0, "delta_8bps_ge_0": float(d8.sum()) >= 0,
             "worst_position_ge_current": ws is not None and wc is not None and ws >= wc,
             "max_drawdown_le_current": s4["max_drawdown_bps"] <= c4["max_drawdown_bps"]}
    return {"id": r["id"], "k_axc0": r["k_axc0"], "k_ax": r["k_ax"], "min_evidence_met": evidence,
            "delta_4bps": float(d4.sum()), "delta_8bps": float(d8.sum()), **gates,
            "pair_pass": evidence and all(gates.values()),
            "pw_delta_4bps_unadjusted": analytics.pw_mean_ci(d4.to_numpy()), "_d4": d4}


def arm_view(x: dict) -> dict:
    return {k: v for k, v in x.items() if k not in ("daily", "trades")}


def test(args) -> None:
    f = freeze()
    ids = changed_ids(f)
    fam = families(f)
    sel_path = OUT / "selection" / "selected_k.csv"
    if not sel_path.exists():
        raise SystemExit("run select first")
    if registry.cumulative_trials(REGISTRY) != REGISTRY_AFTER:
        raise SystemExit("registry is not at the frozen R2-55 value")
    run = stageb_runner()
    snapshot = run.verify_snapshot(read_frames=True)
    sel = pd.read_csv(sel_path)
    k_c0 = sel.loc[sel.window == LAST_WINDOW].set_index("id").k.to_dict()
    k52 = pd.read_csv(O / "r2_52a/selected_k.csv")
    k_ax = k52.loc[k52.window == LAST_WINDOW].set_index("id").k.to_dict()
    kf = pd.read_csv(O / "r2_52a_flip/selected_k.csv")
    k_ax["K01_FLIP"] = float(kf.loc[kf.window == LAST_WINDOW, "k"].iloc[0])
    current = list(ax.INCLUDED) + ["K01_FLIP"]
    jobs = [(i, float(k_ax[i]), float(k_c0[i]) if i in ids else None) for i in current]
    out = OUT / "test"
    out.mkdir(parents=True, exist_ok=True)
    log = out / "test_runs.jsonl"
    run_id = 1 + (sum(1 for x in log.read_text(encoding="utf-8").splitlines() if x.strip()) if log.exists() else 0)
    started = time.time()
    with ProcessPoolExecutor(max_workers=min(args.workers, 8), initializer=_init_test) as pool:
        results = {r["id"]: r for r in pool.map(test_id, jobs)}
    failed = [{k: r[k] for k in ("id", "error", "traceback")} for r in results.values() if r["status"] != "ok"]
    folder = out / f"run_{run_id:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    for i, r in results.items():
        if r["status"] != "ok":
            continue
        for key, value in r.items():
            if isinstance(value, dict) and "trades" in value:
                value["trades"].to_parquet(folder / f"{i}_{key}_trades.parquet")
        pd.DataFrame({key: v["daily"] for key, v in r.items() if isinstance(v, dict) and "daily" in v}).to_parquet(
            folder / f"{i}_daily.parquet")
    pairs = {i: pair_result(results[i]) for i in ids if results.get(i, {}).get("status") == "ok"}
    stats, p = {}, {}
    for name, members in fam.items():
        missing = [i for i in members if i not in pairs]
        if missing:
            stats[name] = {"valid": False, "reason": f"missing pairs {missing}", "p": None}
        else:
            series = pd.concat([pairs[i]["_d4"] for i in members], axis=1).mean(axis=1)
            stats[name] = {**one_sided_test(series.to_numpy()), "n_days": int(len(series)),
                           "cum_mean_delta_4bps": float(series.sum())}
        p[name] = stats[name]["p"] if stats[name]["valid"] else None
    adj = holm(p)
    decisions = {}
    for name, members in fam.items():
        s = stats[name]
        stat_gate = bool(s["valid"] and adj[name]["adjusted_p"] <= ALPHA and s["lower"] is not None and s["lower"] > 0)
        member = {i: (pairs[i]["pair_pass"] if i in pairs else False) for i in members}
        evidence = all(pairs[i]["min_evidence_met"] for i in members if i in pairs) and len(member) == len(
            [i for i in members if i in pairs])
        decisions[name] = {"members": members, "statistical_gate": stat_gate, "holm": adj[name],
                           "min_evidence_all_pairs": evidence, "member_pair_pass": member,
                           "family_pass": stat_gate and all(member.values()) and evidence,
                           "decision": "PASS: switch at first flat moment" if stat_gate and all(member.values())
                           and evidence else "FAIL: keep current AX books"}
    k13 = results.get("K13", {})
    guard_only = []
    for i in current:
        r = results.get(i, {})
        if r.get("status") != "ok":
            continue
        g4, n4, g8, n8 = r["ax_guard_4bps"], r["ax_noguard_4bps"], r["ax_guard_8bps"], r["ax_noguard_8bps"]
        d = g4["daily"] - n4["daily"]
        same = g4["trades"].reset_index(drop=True).equals(n4["trades"].reset_index(drop=True))
        guard_only.append({"id": i, "k": r["k_ax"], "identical_trades": bool(same),
                           "net_4bps_guard": g4["net_bps"], "net_4bps_noguard": n4["net_bps"],
                           "delta_4bps": float(d.sum()), "delta_8bps": float((g8["daily"] - n8["daily"]).sum()),
                           "positions_guard": g4["positions"], "positions_noguard": n4["positions"],
                           "worst_guard": g4["worst_position_bps"], "worst_noguard": n4["worst_position_bps"],
                           "mdd_guard": g4["max_drawdown_bps"], "mdd_noguard": n4["max_drawdown_bps"],
                           "exit_reasons_guard": g4["exit_reasons"], "exit_reasons_noguard": n4["exit_reasons"],
                           "pw_delta_4bps_unadjusted": analytics.pw_mean_ci(d.to_numpy())})
    report = {
        "experiment": f["experiment"], "kind": "HISTORICAL_TEST_2026-10-10 decision replay", "run_id": run_id,
        "created_utc": now(), "window": [str(A), str(B)], "freeze_sha256": FREEZE_SHA,
        "parent_freeze_sha256": PARENT_SHA, "snapshot": {"manifest_sha256": snapshot["manifest_sha256"],
                                                         "artifacts_verified": snapshot["artifacts_verified"]},
        "contamination": f["amendments"][2]["contamination"],
        "costs": "4 bps round trip (2/side) + PESS funding at actual settlement times (R2-54 snapshot ledger); 8 bps "
                 "(4/side) same path, per-pair gate delta_8bps >= 0 as frozen",
        "config": "R2_52A, delay 1, strict, NATIVE rows, causal_guard=True both arms, flat at 2026-01-01, close_at_end "
                  "(data_end administrative close; excluded from completed positions)",
        "k": {"axc0_W10": {i: k_c0[i] for i in ids}, "ax_W10": {i: k_ax[i] for i in current}},
        "failed_ids": failed,
        "pairs": {i: {**{k: v for k, v in pr.items() if not k.startswith("_")},
                      "axc0_4bps": arm_view(results[i]["axc0_guard_4bps"]),
                      "ax_4bps": arm_view(results[i]["ax_guard_4bps"]),
                      "axc0_8bps_net": results[i]["axc0_guard_8bps"]["net_bps"],
                      "ax_8bps_net": results[i]["ax_guard_8bps"]["net_bps"]} for i, pr in pairs.items()},
        "families": stats, "holm": adj, "decisions": decisions,
        "k13_risk": {arm: {k: arm_view(k13[f"{arm}_4bps"])[k] for k in (
            "hold_hours_p50", "hold_hours_p95", "hold_hours_max", "funding_bps", "exposure_share",
            "open_position_age_hours_at_cutoff")} for arm in ("axc0_guard", "ax_guard")} if k13.get("status") == "ok"
        else None,
        "guard_only": guard_only,
        "runtime_seconds": round(time.time() - started, 1), "code_sha256": code_hashes()}
    dump(folder / "report.json", report)
    record = {"run_id": run_id, "utc": now(), "code_sha256": code_hashes(),
              "freeze_sha256": FREEZE_SHA, "snapshot_manifest_sha256": snapshot["manifest_sha256"],
              "report": str((folder / "report.json").relative_to(ROOT)),
              "decisions": {n: d["decision"] for n, d in decisions.items()}, "failed_ids": [x["id"] for x in failed]}
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    print(json.dumps({"run_id": run_id, "failed": [x["id"] for x in failed],
                      "decisions": {n: d["decision"] for n, d in decisions.items()},
                      "families": {n: {k: s.get(k) for k in ("mean", "lower", "upper", "p")} for n, s in stats.items()},
                      "holm": {n: a["adjusted_p"] for n, a in adj.items()}}, indent=1, default=str))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("select", "test"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    select(args) if args.command == "select" else test(args)


if __name__ == "__main__":
    main()
