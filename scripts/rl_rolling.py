"""Plan 3 Task 8, R2-51 (net-P&L reward): rolling evaluation of the trained PPO policies. Stages, each resumable:
  test        per window and state: select (encoder, lr) by the best median validation net over 5 seeds (manifests,
              validation only), then test-window actions of the 5-seed C13 ensemble, each seed (criterion 6), the 4
              hparam ensembles (PBO/White/SPA candidates) and permutation input importance. Windows with unfinished
              trainings are skipped and listed.
  supervised  C14 per window and state (training), then its test actions.
  shuffled    C16: 20 seeds of the window-selected config on the shuffled store (training), then test actions.
  report      C17/C18 comparators, C15 relocation, pass_report per state (n_trials 5297), diagnostics, guard.check,
              registry (n_trials 12, only when complete), report_net.json and REPORT.md (every result).
Usage: python scripts/rl_rolling.py --stage test|supervised|shuffled|report [--windows W01 ..] [--states S1 S3 S4]
Evaluation runs on CPU (batch 1); the two training stages use the GPU if one is visible."""
from __future__ import annotations
import argparse, json, math, sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.rl import baselines as B, evaluation as E, state  # noqa: E402
from btcusdt_quant.rl.train import HYPOTHESIS, NOMINAL, REWARDS, check_minutes, run_config  # noqa: E402
from btcusdt_quant.sim import costs, guard, registry  # noqa: E402
from btcusdt_quant.sim.rolling import END, TRAIN_START, WINDOWS  # noqa: E402
from btcusdt_quant.sim.strategies import Context  # noqa: E402

OUT = ROOT / "out/k45_rl_r2_48_20261007/rl"
CATALOG = [ROOT / "out/k45_rl_r2_48_20261007" / p for p in ("strategies", "levels_r2_49", "levels_r2_50")]
DOC = ROOT / "docs/results/k45_rl_r2_48_20261007/REPORT.md"
REGISTRY = ROOT / "out/sim_registry.jsonl"
EXPERIMENT = "R2-51 RL net-P&L reward rolling evaluation"
STATES = ("S1", "S3", "S4")
HPARAMS = [("conv", 1e-4), ("conv", 3e-4), ("gru", 1e-4), ("gru", 3e-4)]
SEEDS, SHUFFLE_SEEDS = range(5), range(20)
N_CANDIDATES = 12            # registry: S1, S3, S4 x 4 hparams (freeze addendum 2026-10-08)
load_model = B.load_supervised   # same checkpoint layout (model_args + model) as ppo best.pt


def run_dir(root, w: str, st: str, enc: str, lr: float, seed: int, kind: str = "net") -> Path:
    return Path(root) / w / kind / f"{st}_{enc}_lr{lr:g}_s{seed}"      # as scripts/rl_train_window.py


def eval_path(root, w: str, st: str, what: str) -> Path:
    return Path(root) / "eval_net" / w / f"{st}_{what}.{'json' if what == 'selection' else 'parquet'}"


def cand_names() -> list[str]:
    return [f"cand_{e}_{lr:g}" for e, lr in HPARAMS]


def missing_runs(root, w: str, st: str, kind: str = "net") -> list[str]:
    return [str(run_dir(root, w, st, e, lr, s, kind)) for e, lr in HPARAMS for s in SEEDS
            if not (run_dir(root, w, st, e, lr, s, kind) / "manifest.json").exists()]


def select(root, w: str, st: str) -> dict | None:
    """Best median validation net over the 5 seeds (ties: first in HPARAMS order). None if a run is unfinished."""
    if missing_runs(root, w, st):
        return None
    rows = []
    for e, lr in HPARAMS:
        mans = [json.loads((run_dir(root, w, st, e, lr, s) / "manifest.json").read_text(encoding="utf-8"))
                for s in SEEDS]
        if any(m["reward"] != "net" or m["smoke"] for m in mans):
            raise ValueError(f"{w} {st} {e} {lr}: manifest is not a full net-reward run")
        vals = [m["val_net_bps"] for m in mans]
        rows.append({"encoder": e, "lr": lr, "val_nets": vals, "median": float(np.median(vals))})
    best = max(rows, key=lambda r: r["median"])                    # max keeps the first of equal medians
    return {"window": w, "state": st, "encoder": best["encoder"], "lr": best["lr"], "median": best["median"],
            "candidates": rows}


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.astype(np.int8).to_parquet(tmp)
    tmp.replace(path)                                                # the parquet marks the stage done


def stage_test(root, windows, states, store_fn, minutes, funding) -> dict:
    out = {"done": [], "missing": {}}
    for w in windows:
        for st in states:
            key = f"{w.name}/{st}"
            if eval_path(root, w.name, st, "actions").exists():
                out["done"].append(key); continue
            sel = select(root, w.name, st)
            if sel is None:
                out["missing"][key] = missing_runs(root, w.name, st); continue
            store, cols = store_fn(st, w), {}
            run = lambda models: E.ensemble_actions(models, store, minutes, funding, w.test_start, w.test_end)
            for (e, lr), name in zip(HPARAMS, cand_names()):
                models = [load_model(run_dir(root, w.name, st, e, lr, s) / "best.pt") for s in SEEDS]
                cols[name] = run(models)
                if (e, lr) == (sel["encoder"], sel["lr"]):
                    cols["ensemble"] = cols[name]
                    cols.update({f"seed{s}": run([m]) for s, m in enumerate(models)})
                    sel["importance"] = E.input_importance(models, store, minutes, funding, [w])
            path = eval_path(root, w.name, st, "selection")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sel, indent=1, default=float), encoding="utf-8")
            _write(pd.DataFrame(cols), eval_path(root, w.name, st, "actions"))
            out["done"].append(key)
    return out


def stage_supervised(root, windows, states, store_fn) -> dict:
    out = {"done": []}
    for w in windows:
        for st in states:
            path = eval_path(root, w.name, st, "supervised")
            if not path.exists():
                d = Path(root) / w.name / "supervised" / st
                if not (d / "manifest.json").exists():
                    B.train_supervised(w, d, st)
                acts = B.supervised_actions(load_model(d / "best.pt"), store_fn(st, w), w.test_start, w.test_end)
                _write(pd.DataFrame({"supervised": acts}), path)
            out["done"].append(f"{w.name}/{st}")
    return out


def stage_shuffled(root, windows, states, store_fn, minutes, funding) -> dict:
    out = {"done": [], "missing": {}}
    for w in windows:
        for st in states:
            key, path = f"{w.name}/{st}", eval_path(root, w.name, st, "shuffled")
            if path.exists():
                out["done"].append(key); continue
            sel = select(root, w.name, st)
            if sel is None:
                out["missing"][key] = missing_runs(root, w.name, st); continue
            e, lr = sel["encoder"], sel["lr"]
            dirs = [run_dir(root, w.name, st, e, lr, s, "net_shuffled") for s in SHUFFLE_SEEDS]
            for s, d in zip(SHUFFLE_SEEDS, dirs):
                if not (d / "manifest.json").exists():   # ponytail: an interrupted run restarts from scratch
                    run_config(w, st, e, lr, s, d, reward="net", shuffle_seed=s)
            store = store_fn(st, w)
            _write(pd.DataFrame({f"seed{s}": E.ensemble_actions([load_model(d / "best.pt")], store, minutes, funding,
                                                               w.test_start, w.test_end)
                                 for s, d in zip(SHUFFLE_SEEDS, dirs)}), path)
            out["done"].append(key)
    return out


# ---------------------------------------------------------------- report
def _sharpe(d: pd.Series) -> float:
    sd = float(d.std(ddof=1)) if len(d) > 1 else 0.0
    return float(d.mean()) / sd if sd > 0 else math.nan


def _sum_importance(parts: list[dict]) -> dict:
    out = {"base_net": float(sum(p["base_net"] for p in parts)), "reason": "summed over test windows"}
    for g in (k for k in parts[0] if k != "base_net"):
        out[g] = {k: float(sum(p[g][k] for p in parts)) for k in ("net", "drop")}
    return out


def build_report(root, windows, states, minutes, raw_stores: dict, common: dict, catalog_sharpes,
                 reps: int = 1000) -> dict:
    """common: stitched daily nets of C1_X, baseline2, flat, buy_hold (C18). Needs the test and supervised stages
    for every window; the shuffled control may be incomplete (criterion 7 then fails with a reason, final False)."""
    need = [str(eval_path(root, w.name, st, k)) for w in windows for st in states for k in ("actions", "supervised")
            if not eval_path(root, w.name, st, k).exists()]
    if need:
        raise ValueError(f"missing stage outputs: {need}")
    cat = lambda parts: pd.concat(parts) if parts else pd.Series(dtype=float)
    data, cands = {}, {}
    for st in states:
        acts = [pd.read_parquet(eval_path(root, w.name, st, "actions")) for w in windows]
        ens = [E.window_result(a.ensemble, w, minutes=minutes) for a, w in zip(acts, windows)]
        replay = lambda col, frames=acts: cat([E.replay_window(a[col], w, minutes=minutes)
                                               for a, w in zip(frames, windows)])
        for name in cand_names():
            cands[f"{st}_{name[5:]}"] = replay(name)
        sup = [pd.read_parquet(eval_path(root, w.name, st, "supervised")) for w in windows]
        sh_ok = all(eval_path(root, w.name, st, "shuffled").exists() for w in windows)
        sh = [pd.read_parquet(eval_path(root, w.name, st, "shuffled")) for w in windows] if sh_ok else []
        data[st] = {"acts": acts, "ens": ens, "seeds": [replay(f"seed{s}") for s in SEEDS],
                    "supervised": replay("supervised", sup), "shuffled_complete": sh_ok,
                    "null": np.array([float(replay(f"seed{s}", sh).sum()) for s in SHUFFLE_SEEDS]) if sh_ok
                    else np.zeros(0)}
    cand_df = pd.DataFrame(cands).fillna(0.0)
    trial_sharpes = np.r_[np.asarray(catalog_sharpes, float), [_sharpe(cand_df[c]) for c in cand_df]]
    trial_sharpes = trial_sharpes[np.isfinite(trial_sharpes)]
    out_states = {}
    for st in states:
        dd = data[st]
        minute_pnl = cat([r.minute_pnl for r in dd["ens"]])
        daily = E._daily(minute_pnl)
        trades = pd.concat([r.trades for r in dd["ens"]], ignore_index=True)
        comps = {**common, "supervised": dd["supervised"]}
        rep = E.pass_report(daily, dd["seeds"], comps, dd["null"], E.N_TRIALS["net"], trial_sharpes, trades,
                            experiment="net")
        mc = sum(B.relocation_mc(r.trades, w, reps=reps, seed=0, minutes=minutes) for r, w in zip(dd["ens"], windows))
        net4 = float(daily.sum())
        sels = [json.loads(eval_path(root, w.name, st, "selection").read_text(encoding="utf-8")) for w in windows]
        diag = E.diagnostics(pd.concat([a.ensemble for a in dd["acts"]]),
                             [pd.concat([a[f"seed{s}"] for a in dd["acts"]]) for s in SEEDS], minute_pnl, trades,
                             raw_stores[st], list(windows), cand_df, common["C1_X"], minutes=minutes,
                             importance=_sum_importance([s["importance"] for s in sels]))
        guard.check({**rep, "diagnostics": diag})
        inside = lambda s, w: float(s[(s.index >= w.test_start) & (s.index < w.test_end)].sum())
        out_states[st] = {
            "pass": rep["pass"], "pass_report": rep, "diagnostics": diag,
            "selection": [{k: v for k, v in s.items() if k != "importance"} for s in sels],
            "per_window": [{"window": w.name, "encoder": s["encoder"], "lr": s["lr"], "median_val": s["median"],
                            "ensemble": float(r.minute_pnl.sum()), "trades": int(len(r.trades)),
                            "seeds": [inside(x, w) for x in dd["seeds"]],
                            **{k: inside(v, w) for k, v in comps.items()}}
                           for w, s, r in zip(windows, sels, dd["ens"])],
            "random": {"reps": int(reps), "mean": float(np.mean(mc)), "q05": float(np.quantile(mc, .05)),
                       "q50": float(np.quantile(mc, .5)), "q95": float(np.quantile(mc, .95)),
                       "share_ge_rl": float(np.mean(mc >= net4))},
            "shuffled_null": {"complete": dd["shuffled_complete"], "nets": [float(x) for x in dd["null"]]},
        }
    first = next(iter(out_states.values()))["selection"][0]
    man = run_dir(root, windows[0].name, states[0], first["encoder"], first["lr"], 0) / "manifest.json"
    return {"experiment": EXPERIMENT, "reward": "net", "freeze_file": REWARDS["net"][2], "hypothesis": HYPOTHESIS,
            "data_cutoff": "2026-01-01", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source": "scripts/rl_rolling.py", "windows": [w.name for w in windows], "states": out_states,
            "final": all(d["shuffled_complete"] for d in data.values()), "n_trials": E.N_TRIALS["net"],
            "n_trials_registered": N_CANDIDATES, "nominal": NOMINAL,
            "input_hashes": json.loads(man.read_text(encoding="utf-8")).get("input_hashes", {}),
            "trial_sharpes": {"n": int(len(trial_sharpes)), "sources": "catalog values_daily (Plan 2, R2-49, R2-50) "
                              "+ the 12 R2-51 candidate configs' stitched test dailies"},
            "candidates_net_4bps": {k: float(v.sum()) for k, v in cand_df.items()},
            "strategies": [{**s, "id": f"{st}_{s['id']}"} for st, v in out_states.items()
                           for s in v["pass_report"]["strategies"]]}


def register(rep: dict, path=REGISTRY) -> bool:
    """One registry line for R2-51, only for a complete report; never twice."""
    path = Path(path)
    if not rep["final"] or (path.exists() and any(json.loads(x).get("experiment") == EXPERIMENT
                                                  for x in path.read_text(encoding="utf-8").splitlines() if x.strip())):
        return False
    registry.record(path, {"experiment": EXPERIMENT, "n_trials": N_CANDIDATES, "input_hashes": rep["input_hashes"],
                           "config": {"reward": "net", "freeze_file": rep["freeze_file"], "states": list(rep["states"]),
                                      "hparams": HPARAMS, "seeds": len(SEEDS), "shuffle_seeds": len(SHUFFLE_SEEDS),
                                      "windows": rep["windows"], "nominal": rep["nominal"],
                                      "n_trials_dsr": rep["n_trials"]},
                           "result_summary": {st: {"pass": v["pass"],
                                                   "net_4bps": v["pass_report"]["criteria"]["c1"]["value"],
                                                   "trial_sharpes_sha256": v["pass_report"]["criteria"]["c4"]
                                                   ["detail"]["trial_sharpes_sha256"]}
                                              for st, v in rep["states"].items()}})
    return True


def _f(x) -> str:
    return f"{x:.4g}" if isinstance(x, float) else str(x)


def render(rep: dict) -> str:
    L = [f"# {rep['experiment']}", "",
         f"- Hypothesis (frozen): {rep['hypothesis']}", f"- Reward: net (freeze file `{rep['freeze_file']}`)",
         f"- Data cutoff: {rep['data_cutoff']}; generated {rep['timestamp_utc']} by `{rep['source']}`",
         f"- Windows: {', '.join(rep['windows'])}; nominal test: 4 bps round trip, delay 1, slip 0, PESS funding",
         f"- DSR n_trials {rep['n_trials']}; registry n_trials {rep['n_trials_registered']}; "
         f"trial Sharpes: {rep['trial_sharpes']['n']} ({rep['trial_sharpes']['sources']})",
         f"- Final (shuffled control complete for every state): {rep['final']}",
         "- Every result is listed, pass or fail. Units: bps, 1 unit.", ""]
    for st, v in rep["states"].items():
        L += [f"## {st}: overall pass = {v['pass']}", "", "| criterion | value | threshold | pass | reason |",
              "|---|---|---|---|---|"]
        for k, c in v["pass_report"]["criteria"].items():
            L.append(f"| {k} | {_f(c['value'])} | {_f(c['threshold'])} | {c['pass']} | {c['zero_reason'] or c['reason']} |")
        cols = ["ensemble", "trades", "C1_X", "baseline2", "supervised", "buy_hold", "flat"]
        L += ["", "| window | encoder | lr | median val | " + " | ".join(cols) + " | seeds |",
              "|---|---|---|---|" + "---|" * len(cols) + "---|"]
        for r in v["per_window"]:
            L.append(f"| {r['window']} | {r['encoder']} | {r['lr']:g} | {_f(r['median_val'])} | "
                     + " | ".join(_f(r[c]) for c in cols) + " | " + ", ".join(_f(x) for x in r["seeds"]) + " |")
        L += ["", "| comparator | net 4bps | daily diff mean | lower | upper |", "|---|---|---|---|---|"]
        for k, c in v["pass_report"]["comparators"].items():
            L.append(f"| {k} | {_f(c['net_4bps'])} | {_f(c['diff']['mean'])} | {_f(c['diff']['lower'])} | "
                     f"{_f(c['diff']['upper'])} |")
        L += ["", f"- C15 random relocation: {json.dumps(v['random'])}",
              f"- C16 shuffled null: {json.dumps(v['shuffled_null'])}", "",
              "<details><summary>Selection (validation only), pass report detail and diagnostics</summary>", "",
              "```json", json.dumps({"selection": v["selection"], "pass_report": v["pass_report"],
                                     "diagnostics": v["diagnostics"]}, indent=1, default=str), "```", "</details>", ""]
    L += ["## Candidate configs (stitched test net, diagnostics only)", "", "| candidate | net 4bps |", "|---|---|"]
    L += [f"| {k} | {_f(x)} |" for k, x in rep["candidates_net_4bps"].items()]
    return "\n".join(L) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, choices=("test", "supervised", "shuffled", "report"))
    p.add_argument("--reward", choices=("net",), default="net")
    p.add_argument("--windows", nargs="*", default=[w.name for w in WINDOWS])
    p.add_argument("--states", nargs="*", default=list(STATES), choices=STATES)
    p.add_argument("--root", default=str(OUT))
    p.add_argument("--reps", type=int, default=1000)
    p.add_argument("--no-register", action="store_true")
    a = p.parse_args()
    windows = [w for w in WINDOWS if w.name in a.windows]
    ctx = Context.load(end=END)
    minutes, funding = ctx.minutes, costs._settlement_arrays()
    check_minutes(minutes)
    raw = lru_cache(maxsize=None)(lambda st: state.cached_state_store(ctx, TRAIN_START, END, st))
    store_fn = lambda st, w: state.fit_normalizer(raw(st), w.train_end).apply(raw(st))     # C9 per window
    if a.stage == "test":
        res = stage_test(a.root, windows, a.states, store_fn, minutes, funding)
    elif a.stage == "supervised":
        res = stage_supervised(a.root, windows, a.states, store_fn)
    elif a.stage == "shuffled":
        res = stage_shuffled(a.root, windows, a.states, store_fn, minutes, funding)
    else:
        if len(windows) != len(WINDOWS):
            raise SystemExit("report needs all 10 windows")
        picks = B.baseline2_all(CATALOG).set_index("window")
        grid = lambda w: pd.Series(1, index=pd.date_range(w.test_start, w.test_end, freq="15min", inclusive="left"))
        bh = pd.concat([E.replay_window(grid(w), w, minutes=minutes) for w in windows])
        common = {"C1_X": B.combo_daily("K01__NONE__NATIVE", windows, ctx),
                  "baseline2": pd.concat([B.combo_daily(picks.combo[w.name], [w], ctx) for w in windows]),
                  "buy_hold": bh, "flat": pd.Series(0.0, index=bh.index)}
        sharpes = [x for c in CATALOG for x in json.loads((c / "manifest.json").read_text(encoding="utf-8"))
                   ["trial_sharpes"]["values_daily"]]
        rep = build_report(a.root, windows, a.states, minutes, {st: raw(st) for st in a.states}, common, sharpes,
                           a.reps)
        rep["baseline2_picks"] = picks.reset_index()[["window", "combo", "val_net_4bps"]].to_dict("records")
        guard.check(rep)
        (Path(a.root) / "report_net.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text(render(rep), encoding="utf-8")
        res = {"final": rep["final"], "registered": False if a.no_register else register(rep),
               "written": [str(Path(a.root) / "report_net.json"), str(DOC)]}
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
