"""R2-54 Task 4: Stage-B runner (freeze out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json, amendments A1-A3).

  run           features + labels (pre-2026 only) -> 40 structures x 10 validation folds -> every structure x k x side
                through the full R2-52A minute ledger -> per-side ranking and validation gates -> V6 bias controls and
                the 7 robustness removals -> registry (+127) -> final refit of each gate-passing side on all pre-test
                data -> manifest. Reads no 2026 market, label or outcome data (only snapshot file hashes).
  dry-run       the final-test replay code on an already-seen validation-era window (code check only, unregistered).
  unlock-test   final test (amendment A4: repeatable; every run is appended to stageb/test_runs.jsonl and the
                manifest with UTC, code hash, inputs and result, and counted). Refuses unless the freeze, snapshot,
                selection-trace, code and final checkpoint hashes verify; needs --confirm R2-54-STAGEB-ONE-SHOT.

Usage: venv_btcusdt\\Scripts\\python.exe out\\run_r2_54_stageb.py run [--workers 4]
       venv_btcusdt\\Scripts\\python.exe out\\run_r2_54_stageb.py dry-run
       venv_btcusdt\\Scripts\\python.exe out\\run_r2_54_stageb.py unlock-test --confirm R2-54-STAGEB-ONE-SHOT
"""
from __future__ import annotations
import argparse, getpass, hashlib, json, os, platform, socket, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant import stageb as sb  # noqa: E402
from btcusdt_quant.sim import costs, data, provenance, registry  # noqa: E402
from btcusdt_quant.sim.regime import load_regime  # noqa: E402
from btcusdt_quant.sim.strategies import Context  # noqa: E402

BASE = ROOT / "out/k45_rl_r2_48_20261007/r2_54"
OUT = BASE / "stageb"
SNAPSHOT = BASE / "stageb_snapshot"
SNAPSHOT_SHA = "b748d3640249a675a6a9047419bff8b0e7d8cef59e41fe2d1d85f8adbd167069"     # Task 3 FINAL snapshot
FREEZE_SHA = "e1f848ee8091e295dbc75861ffd9135a00236b45121c3b0054467e34ce4845a3"       # on-disk freeze incl. A4
SNAPSHOT_FREEZE_SHA = "710cb08b8f60c3c3c142ed5fd398122751eb891918df3aa8b2f8f930fad034a6"  # freeze (A3) the snapshot used
REGISTRY = ROOT / "out/sim_registry.jsonl"
CONFIRM = "R2-54-STAGEB-ONE-SHOT"
KNOWN_PREDICTION_GAPS = {"2023-12-31", "2025-12-31"}     # last day of each R2-44 stage-1 segment
PERMUTATION_SEED = 42
SPARSE_EVENTS = 100
CODE = [Path(__file__).resolve(), ROOT / "btcusdt_quant/stageb.py", ROOT / "btcusdt_quant/rl/state.py",
        ROOT / "scripts/sim_adaptive_exit.py", ROOT / "btcusdt_quant/sim/core.py", ROOT / "btcusdt_quant/sim/reference.py",
        ROOT / "btcusdt_quant/sim/regime.py", ROOT / "btcusdt_quant/sim/costs.py"]
_G: dict = {}


# ---------------------------------------------------------------- io helpers
def sha(path: Path) -> str:
    return provenance.file_sha256(path)


def rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump(path: Path, value) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return {"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size}


def parquet(path: Path, frame: pd.DataFrame) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return {"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size, "rows": len(frame)}


def git() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True).stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    return {"commit": head, "dirty_diff_sha256": hashlib.sha256(diff).hexdigest(), "dirty_diff_bytes": len(diff),
            "untracked_or_modified": len(status.splitlines())}


def code_hashes() -> dict:
    out = {rel(p): sha(p) for p in CODE}
    out["btcusdt_quant/sim/strategies"] = provenance.tree_sha256(ROOT / "btcusdt_quant/sim/strategies", "*.py")["sha256"]
    return out


def freeze_record() -> dict:
    sb.check_freeze()
    digest = sha(sb.FREEZE_PATH)
    if digest != FREEZE_SHA:
        raise SystemExit(f"freeze sha256 {digest} != recorded {FREEZE_SHA}; the freeze must not change")
    f = sb.freeze()
    return {"path": rel(sb.FREEZE_PATH), "sha256": digest, "created_utc": f["created_utc"],
            "frozen_utc": f["status"]["frozen_utc"], "amendments": [a["id"] for a in f["amendments"]]}


def verify_snapshot(read_frames: bool = False) -> dict:
    """Snapshot manifest hash and every artifact's file hash (bytes only). read_frames (unlock only): also the taker
    archive-only assertion (amendment A3), which opens the taker table."""
    path = SNAPSHOT / "manifest.json"
    digest = sha(path)
    if digest != SNAPSHOT_SHA:
        raise SystemExit(f"snapshot manifest sha256 {digest} != {SNAPSHOT_SHA}")
    m = json.loads(path.read_text(encoding="utf-8"))
    if m["status"] != "FINAL" or not m["parity"]["passed"] or not m["prediction_parity"]["passed"]:
        raise SystemExit("snapshot is not FINAL with passed parity")
    if m["freeze"]["sha256"] != SNAPSHOT_FREEZE_SHA or sb.amendment("A4")["freeze_sha256_before"] != SNAPSHOT_FREEZE_SHA:
        raise SystemExit("snapshot freeze hash does not chain to the current freeze (A4 freeze_sha256_before)")
    checked = {}
    for name, record in m["artifacts"].items():
        actual = sha(ROOT / record["path"])
        if actual != record["sha256"]:
            raise SystemExit(f"snapshot artifact {name} sha256 changed")
        checked[name] = actual
    if "source=archive only" not in m["artifacts"]["futures_taker_lsr_5m"]["source"]:
        raise SystemExit("snapshot taker table is not archive-only")
    if read_frames:
        taker = pd.read_parquet(ROOT / m["artifacts"]["futures_taker_lsr_5m"]["path"])
        if set(taker.source) != {"archive"}:
            raise SystemExit("snapshot taker rows are not all archive (amendment A3)")
    return {"manifest_path": rel(path), "manifest_sha256": digest, "artifacts_verified": checked,
            "parity_report": m["parity"]["report"], "prediction_parity": m["prediction_parity"]["report"],
            "stage_a_2026_folds": m["stage_a"]["folds"], "pre_2026_hashes": m["pre_2026_train_validation"],
            "gates_data": m["gates_data"], "taker_archive_only_asserted_on_rows": bool(read_frames)}


def features_frame_sha256(frame: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes()).hexdigest()


ARCHIVE_URLS = {"market": "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/",
                "metrics": "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/",
                "premium": "https://data.binance.vision/data/futures/um/daily/premiumIndexKlines/BTCUSDT/1m/",
                "funding": "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/"}


def _mtimes(paths) -> dict:
    stamps = sorted(datetime.fromtimestamp(Path(p).stat().st_mtime, timezone.utc) for p in paths)
    return {"files": len(stamps), "retrieved_first_utc": stamps[0].isoformat() if stamps else None,
            "retrieved_last_utc": stamps[-1].isoformat() if stamps else None}


def source_provenance() -> dict:
    """manifest.required_records: pre-2026 source URLs, local copies, retrieval timestamps (file mtime: the download
    time of each archive; no separate retrieval log exists) and the data cutoff."""
    funding_dir = ROOT / "artifacts/funding_2020_2026h1"
    out = {"data_cutoff_exclusive": str(sb.TEST_START),
           "retrieval_timestamp_rule": "local file modification time (UTC) of the downloaded archive"}
    for name, local in (("market", data.MARKET_PATH), ("metrics", data.METRICS_DIR), ("premium", data.PREMIUM_DIR),
                        ("funding", funding_dir)):
        files = [local] if Path(local).is_file() else sorted(Path(local).glob("*.zip"))
        daily = name in ("metrics", "premium")             # loaders read only daily files dated before the cutoff
        used = [f for f in files if not daily or data._file_day(f) < sb.TEST_START]
        out[name] = {"source_url": ARCHIVE_URLS[name], "source": "data.binance.vision (Binance public archive)",
                     "local": rel(local), **_mtimes(used),
                     "first_file": Path(used[0]).name if used else None, "last_file": Path(used[-1]).name if used else None}
    out["market"]["note"] = "single parquet built from the monthly kline archives; rows >= 2026-01-01 not read"
    folds = sorted(data.PREDICTIONS_DIR.glob("DEV_*/fold_*_predictions.parquet"))
    out["stage_a"] = {"source": "R2-44 w730_raw walk-forward folds (local generation, no URL)",
                      "local": rel(data.PREDICTIONS_DIR), **_mtimes(folds)}
    return out


def stage_a_pre2026() -> list:
    out = []
    for segment in ("DEV_FRONT", "DEV_BACK"):
        for f in sorted((data.PREDICTIONS_DIR / segment).glob("fold_*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            out.append({"segment": segment, "fold": f.stem, "model_id": f"r2_44_w730_raw_{segment}_{f.stem}",
                        "retrain_time": r["retrain_time"], "prediction_end": r["prediction_end"],
                        "checkpoint_sha256": r["checkpoint_sha256"], "predictions_sha256": r["predictions_sha256"],
                        "train_cutoff_rule": "R2-44 730-day rolling window; labels end before retrain-24h"})
    return out


# ---------------------------------------------------------------- pre-2026 context, features, labels
def pre2026_context() -> tuple[Context, pd.DataFrame]:
    ctx = Context.load(end=sb.TEST_START)
    settle = costs._settlements()
    return ctx, sb.funding_frame(settle.loc[settle.time < sb.TEST_START])


def data_gates(ctx: Context, feats: sb.Features, labels: pd.DataFrame) -> dict:
    preds = data.load_predictions(end=sb.TEST_START)
    coverage = data.prediction_coverage(preds, sb.DEV_START, sb.TEST_START)
    t = ctx.minutes.open_time
    times = pd.DatetimeIndex(feats.frame.decision_time)
    crossing = {}
    for h, m in sb.HORIZONS.items():
        exit_ = sb.ns(labels[f"exit_{h}"])
        for i, (a, b) in enumerate(sb.folds()):
            tr, va = sb.train_mask(times, m, a), sb.block_mask(times, m, a, b)
            crossing[f"{h}_fold{i}"] = int((exit_[tr] >= a.value).sum() + (exit_[va] >= b.value).sum()
                                           + (sb.ns(times)[va] < a.value).sum())
    metric_grid = pd.date_range(sb.DEV_START, sb.TEST_START, freq="5min", inclusive="left") + pd.Timedelta(minutes=5)
    present = pd.DatetimeIndex(ctx.metrics.available_time)
    gates = {"no_missing_or_duplicate_1m_bars": bool((np.diff(sb.ns(t)) == 60_000_000_000).all()),
             "minutes": {"first": str(t.iloc[0]), "last": str(t.iloc[-1]), "rows": len(t)},
             "no_feature_row_available_after_t": int((feats.avail > sb.ns(times)).sum()) == 0,
             "stage_a_coverage": coverage,
             "stage_a_missing_days_known": set(coverage["missing_days"]) <= KNOWN_PREDICTION_GAPS,
             "stage_a_retrain_after_timestamp": coverage["retrain_after_timestamp"],
             "split_crossing_labels": int(sum(crossing.values())), "split_crossing_by_fold": crossing,
             "metrics_5m_missing_periods": int((~metric_grid.isin(present)).sum()),
             "metrics_5m_duplicates": int(present.duplicated().sum()),
             "premium_rows": len(ctx.premium), "funding_settlements": len(ctx.funding)}
    gates["pass"] = bool(gates["no_missing_or_duplicate_1m_bars"] and gates["no_feature_row_available_after_t"]
                         and gates["stage_a_missing_days_known"] and gates["stage_a_retrain_after_timestamp"] == 0
                         and gates["split_crossing_labels"] == 0)
    return gates


CAUSALITY_CUTS = (pd.Timestamp("2023-09-01 13:15", tz="UTC"), pd.Timestamp("2025-06-17 07:45", tz="UTC"))


def real_causality(ctx: Context, funding: pd.DataFrame, feats: sb.Features) -> dict:
    """Real-data check: features rebuilt on Context.truncate(cut) equal the full build for every row T < cut."""
    out = {}
    times = feats.frame.decision_time
    for cut in CAUSALITY_CUTS:
        start = cut - pd.Timedelta(days=3)
        part = sb.build_features(ctx.truncate(cut), start, cut, funding.loc[funding.available_time < cut])
        full = feats.frame.loc[(times >= start) & (times < cut)].reset_index(drop=True)
        out[str(cut)] = {"rows": len(full), "identical": bool(part.frame.equals(full))}
    out["pass"] = all(v["identical"] for v in out.values())
    return out


def build_inputs(ctx: Context, funding: pd.DataFrame) -> tuple[sb.Features, pd.DataFrame, dict]:
    t0 = time.time()
    feats = sb.build_features(ctx, sb.DEV_START, sb.TEST_START, funding)
    sb.assert_causal(feats)
    labels = sb.make_labels(ctx.minutes, pd.DatetimeIndex(feats.frame.decision_time))
    sb.assert_isolated(feats.frame, labels)
    folder = OUT / "features"
    records = {"features": parquet(folder / "features_pre2026.parquet", feats.frame),
               "labels": parquet(OUT / "labels/labels_pre2026.parquet", labels),
               "availability": parquet(folder / "features_avail_pre2026.parquet",
                                       pd.DataFrame({"decision_time": feats.frame.decision_time,
                                                     "max_logical_available_at_ns": feats.avail}))}
    meta = {"schema_version": "r2_54_stageb_features_v1", "groups": feats.groups, "tech": feats.tech,
            "views": {v: len(sb.view_columns(feats, v)) for v in sb.VIEWS},
            "group_counts": pd.Series(feats.groups).value_counts().to_dict(),
            "availability_rules": {
                "grid": "15-minute decision T = close of the bar [T-15m, T); entry/label start open(T+1m)",
                "market": "complete bars with decision_time <= T; 1-minute rows with open_time + 1m <= T",
                "metrics": "archive rows with logical_available_at = create_time + 5m <= T (taker = archive, A3); "
                           "value only within 1 h, else missing mask; age since create_time",
                "premium": "minute closed at <= T (available_time = close_time + 1 ms); 15 min TTL",
                "funding": "latest event with actual calc time <= T, 24 h TTL; interval_hours observed (8 h asserted "
                           "by the archive loader pre-2026; snapshot interval_missing -> NaN + mask)",
                "stage_a": "latest prediction with prediction_ts <= T and logical_available_at <= T, age <= 24 h",
                "techniques": "NONE/NATIVE signal rows with decision_time <= T (rl.state.side_channels/oco_channels); "
                              "K10 proposal = grid_plan row at T"},
            "missingness": "no backward fill, no future-derived imputation; Ridge imputes NaN at the train mean "
                           "(z = 0) after train-only standardization; CatBoost native NaN",
            "max_logical_available_minus_t_ns": int((feats.avail - sb.ns(feats.frame.decision_time)).max()),
            "seconds": round(time.time() - t0, 1)}
    records["meta"] = dump(folder / "feature_meta.json", meta)
    return feats, labels, records


def load_inputs() -> tuple[sb.Features, pd.DataFrame]:
    meta = json.loads((OUT / "features/feature_meta.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(OUT / "features/features_pre2026.parquet")
    avail = pd.read_parquet(OUT / "features/features_avail_pre2026.parquet").max_logical_available_at_ns.to_numpy()
    labels = pd.read_parquet(OUT / "labels/labels_pre2026.parquet")
    return sb.Features(frame, meta["groups"], meta["tech"], avail), labels


# ---------------------------------------------------------------- validation fits (worker processes)
def _init_worker() -> None:
    feats, labels = load_inputs()
    _G.update(feats=feats, labels=labels, times=pd.DatetimeIndex(feats.frame.decision_time))


def fit_fold(view: str, horizon: str, i: int, drop_ids: tuple = (), tag: str = "", models=sb.MODELS) -> dict:
    """Train on the purged/embargoed expanding window before fold i, predict every decision inside fold i."""
    feats, labels, times = _G["feats"], _G["labels"], _G["times"]
    a, b = sb.folds()[i]
    cols = sb.view_columns(feats, view, drop_ids)
    x = feats.frame[cols].to_numpy(np.float32)
    h = sb.HORIZONS[horizon]
    tr = sb.train_mask(times, h, a)
    y = labels[f"g_{horizon}"].to_numpy(float)[tr]
    rows = (times >= a) & (times < b)
    out = {"decision_time": times[rows]}
    record = {"view": view, "horizon": horizon, "fold": i, "fold_start": str(a), "fold_end": str(b), "tag": tag,
              "drop_ids": list(drop_ids), "train_rows": int(tr.sum()), "columns": len(cols),
              "train_first": str(times[tr].min()), "train_last": str(times[tr].max()),
              "train_label_exit_max": str(labels[f"exit_{horizon}"][tr].max()),
              "n_eff_train": sb.n_eff(times, tr, h), "checkpoints": {}}
    folder = OUT / "checkpoints" / ("folds" if not tag else f"robustness/{tag}")
    folder.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for name in models:
        model = sb.fit_model(name, x[tr], y, cols)
        out[f"yhat_{name}"] = sb.predict(model, x[rows])
        blob = sb.checkpoint_bytes(model)
        path = folder / f"{view}__{horizon}__f{i:02d}__{name}.bin"
        path.write_bytes(blob)
        record["checkpoints"][name] = {"path": rel(path), "sha256": sb.sha256_bytes(blob)}
    record["seconds"] = round(time.time() - t0, 1)
    return {"record": record, "pred": pd.DataFrame(out)}


def _fit_task(args):
    return fit_fold(*args)


def run_fits(tasks: list, workers: int, cache: Path) -> dict:
    """tasks: (view, horizon, fold, drop_ids, tag, models). Cached per task (resumable); returns {key: result}."""
    cache.mkdir(parents=True, exist_ok=True)
    key = lambda t: f"{t[0]}__{t[1]}__f{t[2]:02d}" + (f"__{t[4]}" if t[4] else "")
    todo = [t for t in tasks if not (cache / f"{key(t)}.json").exists()]
    if todo:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
            for t, res in zip(todo, pool.map(_fit_task, todo)):
                res["pred"].to_parquet(cache / f"{key(t)}.parquet", index=False)
                dump(cache / f"{key(t)}.json", res["record"])
                print(f"fit {key(t)} {res['record']['seconds']}s", flush=True)
    return {key(t): {"record": json.loads((cache / f"{key(t)}.json").read_text(encoding="utf-8")),
                     "pred": pd.read_parquet(cache / f"{key(t)}.parquet")} for t in tasks}


# ---------------------------------------------------------------- ledgers and metrics
class Ledger:
    """Per-fold minute slices of the market and of E (per head) for the R2-52A runs."""

    def __init__(self, ctx: Context):
        ax = sb.ax_runner()
        self.ctx, self.minutes = ctx, ctx.minutes
        self.settle = sb.actual_settlements(costs._settlements())      # actual fundingTime events
        mt = pd.DatetimeIndex(self.minutes.open_time)
        self.e = {h: ax.e_series(ctx.regime, mt, h) for h in sb.HORIZONS}
        self.slices = {}
        for i, (a, b) in enumerate(sb.folds()):
            s = (mt >= a + sb.EMBARGO) & (mt < b)
            self.slices[i] = (self.minutes.loc[s].reset_index(drop=True), np.flatnonzero(s))

    def run(self, i: int, horizon: str, times, yhat, side: int, k: float) -> dict:
        a, b = sb.folds()[i]
        start = a + sb.EMBARGO
        minutes, idx = self.slices[i]
        e, e_min = (x[idx] for x in self.e[horizon])
        rows = (times >= start) & (times < b)
        t = pd.DatetimeIndex(times[rows])
        e0 = sb.ax_runner().e_at(self.ctx.regime, t, horizon)
        table = sb.signal_table(t, np.asarray(yhat)[rows], side, e0, k)
        with sb.ledger_settlements(self.settle):
            r4 = sb.fold_ledger(table, minutes, e, e_min, start, b, sb.FEE_NOMINAL, k)
            r8 = sb.fold_ledger(table, minutes, e, e_min, start, b, sb.FEE_STRESS, k)
        wants = table.side != 0
        return {"net4": r4["pnl"], "net8": r8["pnl"], "completed": r4["completed"], "valid": r4["valid"] and r8["valid"],
                "open_at_end": r4["open_at_end"], "exit_reasons": r4["exit_reasons"],
                "entry_signals": int(wants.sum()),
                "no_entry_e_rows": int((wants & ~(np.isfinite(e0) & (e0 > 0))).sum()), "trades": r4["trades"]}


def fold_ic(times, yhat, g, h_min: int, i: int) -> float:
    a, b = sb.folds()[i]
    keep = sb.block_mask(times, h_min, a, b)
    return sb.spearman(np.asarray(yhat)[keep], np.asarray(g)[keep])


def validation_frame(preds: dict, labels: pd.DataFrame, view: str, horizon: str, model: str, tag: str = "") -> pd.DataFrame:
    """Pooled eligible validation rows of one structure: fold, decision_time, yhat, g."""
    lab = labels.set_index("decision_time")
    h = sb.HORIZONS[horizon]
    parts = []
    for i, (a, b) in enumerate(sb.folds()):
        p = preds[f"{view}__{horizon}__f{i:02d}" + (f"__{tag}" if tag else "")]["pred"]
        t = pd.DatetimeIndex(p.decision_time)
        keep = sb.block_mask(t, h, a, b)
        parts.append(pd.DataFrame({"fold": i, "decision_time": t[keep], "yhat": p[f"yhat_{model}"].to_numpy()[keep],
                                   "g": lab[f"g_{horizon}"].reindex(t[keep]).to_numpy()}))
    return pd.concat(parts, ignore_index=True)


def bucket_ics(preds, labels, feats, view, horizon, model) -> dict:
    """gates.validation_stability: per-fold train-frozen terciles of causal M and L, pooled bucket Spearman IC."""
    times = pd.DatetimeIndex(feats.frame.decision_time)
    v = validation_frame(preds, labels, view, horizon, model)
    f = feats.frame.set_index("decision_time")
    out, cuts = {}, {}
    for name in ("M", "L"):
        col = f[f"v3_{name}"]
        labels_ = np.full(len(v), -1)
        for i, (a, _) in enumerate(sb.folds()):
            tr = sb.train_mask(times, sb.HORIZONS[horizon], a)
            q = np.nanquantile(col.to_numpy()[tr], [1 / 3, 2 / 3])
            cuts.setdefault(name, []).append([float(q[0]), float(q[1])])
            rows = v.fold.to_numpy() == i
            x = col.reindex(v.decision_time[rows]).to_numpy()
            lab = np.where(np.isfinite(x), np.digitize(x, q), -1)
            labels_[rows] = lab
        out[name] = [sb.spearman(v.yhat[labels_ == j], v.g[labels_ == j]) for j in range(3)]
        out[f"{name}_n"] = [int((labels_ == j).sum()) for j in range(3)]
    out["cuts"] = cuts
    return out


# ---------------------------------------------------------------- validation selection
def candidate_rows(preds, labels, ledger: Ledger, trades_out: Path) -> tuple[list, pd.DataFrame]:
    rows, fold_rows, trade_parts = [], [], []
    times_lab = labels.set_index("decision_time")
    for view in sb.VIEWS:
        for horizon, h in sb.HORIZONS.items():
            for model in sb.MODELS:
                fics = []
                per_fold = {}
                for i in range(10):
                    p = preds[f"{view}__{horizon}__f{i:02d}"]["pred"]
                    t = pd.DatetimeIndex(p.decision_time)
                    yhat = p[f"yhat_{model}"].to_numpy()
                    g = times_lab[f"g_{horizon}"].reindex(t).to_numpy()
                    fics.append(fold_ic(t, yhat, g, h, i))
                    for side_name, side in sb.SIDES.items():
                        for k in sb.K_VALUES:
                            r = ledger.run(i, horizon, t, yhat, side, k)
                            per_fold[(side_name, k, i)] = r
                            fold_rows.append({"view": view, "horizon": horizon, "model": model, "side": side_name,
                                              "k": k, "fold": i, "ic": fics[-1],
                                              **{x: r[x] for x in ("net4", "net8", "completed", "valid", "open_at_end",
                                                                   "entry_signals", "no_entry_e_rows")},
                                              "exit_reasons": json.dumps(r["exit_reasons"])})
                            if len(r["trades"]):
                                trade_parts.append(r["trades"].assign(view=view, horizon=horizon, model=model,
                                                                      side_policy=side_name, k=k, fold=i))
                for side_name in sb.SIDES:
                    for k in sb.K_VALUES:
                        fr = [per_fold[(side_name, k, i)] for i in range(10)]
                        rows.append({"side": side_name, "view": view, "horizon": horizon, "model": model, "k": k,
                                     "net4": float(sum(r["net4"] for r in fr)), "net8": float(sum(r["net8"] for r in fr)),
                                     "median_ic": float(np.nanmedian(fics)) if np.isfinite(fics).any() else float("nan"),
                                     "completed": int(sum(r["completed"] for r in fr)),
                                     "folds_valid": int(sum(r["valid"] for r in fr)),
                                     "fold_ic": [float(x) for x in fics], "fold_net4": [float(r["net4"]) for r in fr],
                                     "fold_net8": [float(r["net8"]) for r in fr]})
            print(f"ledger {view} {horizon} done", flush=True)
    trades = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()
    parquet(trades_out, trades)
    return rows, pd.DataFrame(fold_rows)


def v6_finalist(trace: list) -> dict | None:
    """selection.robustness_role: the side's top-ranked eligible V6 pair (else top-ranked V6)."""
    v6 = [r for r in trace if r["view"] == "V6_full"]
    return next((r for r in v6 if r["eligible"]), v6[0] if v6 else None)


def permutation(preds, labels, feats, cfg) -> dict:
    """bias_controls.grouped_permutation on each validation fold: top-level groups and per technique id (all columns of
    a group permuted with one shared row permutation), delta-IC = IC_full - IC_permuted."""
    horizon, model = cfg["horizon"], cfg["model"]
    times = pd.DatetimeIndex(feats.frame.decision_time)
    cols = sb.view_columns(feats, "V6_full")
    x_all = feats.frame[cols].to_numpy(np.float32)
    index = {c: j for j, c in enumerate(cols)}
    groups = {g: [index[c] for c in cols if feats.groups[c] == g] for g in ("V1", "V2", "V3", "V4")}
    ids = sorted(set(feats.tech.values()))
    by_id = {i: [index[c] for c in cols if feats.tech.get(c) == i] for i in ids}
    lab = labels.set_index("decision_time")
    h = sb.HORIZONS[horizon]
    folds = []
    for i, (a, b) in enumerate(sb.folds()):
        rec = preds[f"V6_full__{horizon}__f{i:02d}"]["record"]["checkpoints"][model]
        m = sb.load_checkpoint((ROOT / rec["path"]).read_bytes())
        if sb.sha256_bytes((ROOT / rec["path"]).read_bytes()) != rec["sha256"]:
            raise RuntimeError("fold checkpoint changed")
        keep = sb.block_mask(times, h, a, b)
        x = x_all[keep]
        g = lab[f"g_{horizon}"].reindex(times[keep]).to_numpy()
        full = sb.spearman(sb.predict(m, x), g)
        rng = np.random.default_rng(PERMUTATION_SEED + i)
        delta = {}
        for name, j in [*groups.items(), *by_id.items()]:
            xp = x.copy()
            xp[:, j] = x[rng.permutation(len(x))][:, j]
            delta[name] = full - sb.spearman(sb.predict(m, xp), g)
        pos = {k: max(delta[k], 0.0) for k in ids}
        total = sum(pos.values())
        folds.append({"fold": i, "ic": full, "delta": delta,
                      "id_share": {k: (v / total if total > 0 else 0.0) for k, v in pos.items()}})
    mean = {k: float(np.mean([f["delta"][k] for f in folds])) for k in [*groups, *ids]}
    top = sorted(ids, key=lambda k: (-mean[k], k))[0]
    claims = {k: int(sum(f["delta"][k] > 0 for f in folds)) for k in [*groups, *ids]}
    return {"seed": f"{PERMUTATION_SEED} + fold", "folds": folds, "mean_delta_ic": mean, "top_id": top,
            "positive_delta_folds": claims, "important": {k: v >= 7 for k, v in claims.items()}}


def event_disclosure(preds, labels, feats, cfg) -> dict:
    v = validation_frame(preds, labels, "V6_full", cfg["horizon"], cfg["model"])
    f = feats.frame.set_index("decision_time").reindex(v.decision_time)
    out = {}
    for ident in sorted(set(feats.tech.values())):
        name = next(c for c in (f"v4_{ident}_event_side", f"v4_{ident}_proposal_active") if c in f)
        ev = f[name].to_numpy()
        event = np.nan_to_num(ev) != 0
        out[ident] = {"channel": name, "events": int(event.sum()), "long_events": int((ev == 1).sum()),
                      "short_events": int((ev == -1).sum()),
                      "event_ic": sb.spearman(v.yhat[event], v.g[event]),
                      "no_event_ic": sb.spearman(v.yhat[~event], v.g[~event]),
                      "sparse_no_claim": bool(event.sum() < SPARSE_EVENTS)}
    return out


def robustness(preds_rm, labels, ledger: Ledger, cfg, tag: str) -> dict:
    v = validation_frame(preds_rm, labels, "V6_full", cfg["horizon"], cfg["model"], tag)
    fics = [sb.spearman(v.yhat[v.fold == i], v.g[v.fold == i]) for i in range(10)]
    side = sb.SIDES[cfg["side"]]
    net4 = net8 = 0.0
    completed = 0
    for i in range(10):
        p = preds_rm[f"V6_full__{cfg['horizon']}__f{i:02d}__{tag}"]["pred"]
        r = ledger.run(i, cfg["horizon"], pd.DatetimeIndex(p.decision_time), p[f"yhat_{cfg['model']}"].to_numpy(),
                       side, cfg["k"])
        net4 += r["net4"]; net8 += r["net8"]; completed += r["completed"]
    return {"pooled_ic": sb.spearman(v.yhat, v.g), "fold_ic": fics, "net4": net4, "net8": net8, "completed": completed}


def struct_key(cfg) -> tuple:
    return (cfg["view"], cfg["horizon"], cfg["model"])


def final_fit(feats, labels, cfg: dict, cutoff: pd.Timestamp, folder: Path, name: str) -> dict:
    times = pd.DatetimeIndex(feats.frame.decision_time)
    cols = sb.view_columns(feats, cfg["view"])
    h = sb.HORIZONS[cfg["horizon"]]
    tr = sb.train_mask(times, h, cutoff)
    x = feats.frame[cols].to_numpy(np.float32)[tr]
    y = labels[f"g_{cfg['horizon']}"].to_numpy(float)[tr]
    t0 = time.time()
    model = sb.fit_model(cfg["model"], x, y, cols)
    blob = sb.checkpoint_bytes(model)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.bin"
    path.write_bytes(blob)
    return {"structure": {k: cfg[k] for k in ("view", "horizon", "model", "k")}, "retrain_time": str(cutoff),
            "publication_time_logical": str(cutoff), "written_at": now(), "train_rows": int(tr.sum()),
            "train_first": str(times[tr].min()), "train_last": str(times[tr].max()),
            "train_cutoff_label_exit_max": str(labels[f"exit_{cfg['horizon']}"][tr].max()),
            "n_eff_train": sb.n_eff(times, tr, h), "columns": len(cols),
            "feature_sha256": hashlib.sha256(json.dumps(cols).encode()).hexdigest(),
            "checkpoint": {"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size},
            "seconds": round(time.time() - t0, 1)}


def run(args) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"kind": "R2-54 Stage-B validation selection", "created_utc": now(), "freeze": freeze_record(),
                "git": git(), "code_sha256": code_hashes(), "frozen_hypothesis": sb.freeze()["frozen_hypothesis"],
                "side_hypotheses": {
                    "long": "Long policy (yhat_H - 4 > 0 entry, yhat_H <= 0 exit, R2-52A safety) earns positive "
                            "cost-adjusted net with IC lower bound > 0 on 2026-01-01..2026-10-07.",
                    "short": "Short policy (-yhat_H - 4 > 0 entry, -yhat_H <= 0 exit, R2-52A safety) earns positive "
                             "cost-adjusted net with IC lower bound > 0 on 2026-01-01..2026-10-07."},
                "registry": {**sb.n_trials(), "note": "amendment A2 supersedes the body 5413/5540"},
                "intervals": {"development": sb.freeze()["time_structure"]["development"],
                              "validation_folds": sb.freeze()["time_structure"]["validation_folds"],
                              "validation_training": sb.freeze()["time_structure"]["validation_training"],
                              "embargo_boundaries": [str(b) for b in sb.boundaries()],
                              "final_test_nominal": sb.freeze()["time_structure"]["final_test_nominal"],
                              "final_test_evaluable": sb.freeze()["time_structure"]["final_test_evaluable"]},
                "contamination_note": sb.freeze()["time_structure"]["exposure_note"] + " 2026H1 and 2026Q3 were "
                                      "viewed by earlier discounted experiments; the final-test interval is not a "
                                      "pristine holdout.",
                "snapshot": verify_snapshot(read_frames=False),
                "sources": {"pre_2026": source_provenance(),
                            "final_test": "Task 3 FINAL snapshot (sources, retrieval timestamps and cutoffs in its "
                                          "manifest)"},
                "input_sha256_pre_2026": sb.ax_runner().plan2.input_hashes(sb.TEST_START),
                "stage_a": {"pre_2026": stage_a_pre2026(), "2026": "snapshot.stage_a_2026_folds"},
                "test_status": "LOCKED"}
    ctx, funding = pre2026_context()
    if not (OUT / "features/feature_meta.json").exists():
        feats, labels, records = build_inputs(ctx, funding)
    else:
        feats, labels = load_inputs()
        records = {n: {"path": rel(p), "sha256": sha(p)} for n, p in (
            ("features", OUT / "features/features_pre2026.parquet"), ("labels", OUT / "labels/labels_pre2026.parquet"),
            ("availability", OUT / "features/features_avail_pre2026.parquet"),
            ("meta", OUT / "features/feature_meta.json"))}
    manifest["artifacts"] = records
    digest = features_frame_sha256(feats.frame)
    marker = OUT / "folds/_features_frame_sha256.txt"
    if marker.exists() and marker.read_text().strip() != digest:
        raise SystemExit("fold cache was fit on a different feature frame; delete stageb/folds and robustness_folds")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(digest)
    manifest["artifacts"]["features"]["frame_sha256"] = digest
    rounds = sorted(OUT.glob("manifest_round*.json"))
    if rounds:
        reasons = {"manifest_round0.json": "fix round 1: ledgers book actual fundingTime events (minute bucketing only "
                                           "inside the simulator); V4 availability in the causality gate; code changed",
                   "manifest_round1.json": "amendment A4: 8 bps report-only in the validation economic gate and removed "
                                           "from the rank keys; repeatable logged final test; code changed"}
        manifest["validation_rerun"] = {
            "previous_manifests": [{"path": rel(r), "sha256": sha(r), "superseded_because": reasons.get(r.name)}
                                   for r in rounds],
            "fold_fits": "reused: feature frame sha256 identical to round 0 (marker folds/_features_frame_sha256.txt)",
            "registry": "no new rows: same 127 trials (5417 -> 5544 recorded once in round 0)"}
    gates = data_gates(ctx, feats, labels)
    gates["real_data_truncation_causality"] = real_causality(ctx, funding, feats)
    gates["pass"] = gates["pass"] and gates["real_data_truncation_causality"]["pass"]
    manifest["data_gates"] = gates
    if not gates["pass"]:
        dump(OUT / "manifest.json", manifest)
        raise SystemExit(f"data gates failed: {gates}")
    print(f"features {feats.frame.shape} {round(time.time() - started)}s", flush=True)

    tasks = [(v, h, i, (), "", sb.MODELS) for v in sb.VIEWS for h in sb.HORIZONS for i in range(10)]
    preds = run_fits(tasks, args.workers, OUT / "folds")
    print(f"fits done {round(time.time() - started)}s", flush=True)
    pred_frame = pd.concat([p["pred"].assign(key=k) for k, p in preds.items()], ignore_index=True)
    manifest["artifacts"]["validation_predictions"] = parquet(OUT / "validation/predictions.parquet", pred_frame)
    manifest["fold_checkpoints"] = {k: p["record"]["checkpoints"] for k, p in preds.items()}

    ledger = Ledger(ctx)
    rows, fold_rows = candidate_rows(preds, labels, ledger, OUT / "validation/trades_4bps.parquet")
    manifest["artifacts"]["validation_trades"] = {"path": rel(OUT / "validation/trades_4bps.parquet"),
                                                  "sha256": sha(OUT / "validation/trades_4bps.parquet")}
    manifest["artifacts"]["fold_rows"] = parquet(OUT / "validation/fold_rows.parquet", fold_rows)
    candidates = pd.DataFrame([{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()} for r in rows])
    manifest["artifacts"]["candidates"] = parquet(OUT / "validation/candidates.parquet", candidates)
    candidates.to_csv(OUT / "validation/candidates.csv", index=False)
    print(f"ledgers done {round(time.time() - started)}s", flush=True)

    selection, trace = {}, {}
    for side in sb.SIDES:
        side_rows = [r for r in rows if r["side"] == side]
        if len(side_rows) != 120:
            raise RuntimeError("expected 120 candidate-k rows per side")
        s = sb.select_side(side_rows)
        trace[side] = s["trace"]
        chosen = s["selected"]
        if chosen is None:
            selection[side] = {"selected": None, "eligible": 0, "pass": False, "reason": "no eligible pair"}
            continue
        buckets = bucket_ics(preds, labels, feats, chosen["view"], chosen["horizon"], chosen["model"])
        gates_v = sb.validation_gates(chosen["fold_ic"], chosen["fold_net4"], chosen["net8"],
                                      {"M": buckets["M"], "L": buckets["L"]})
        v = validation_frame(preds, labels, chosen["view"], chosen["horizon"], chosen["model"])
        selection[side] = {"selected": {k: chosen[k] for k in ("view", "horizon", "model", "k", "net4", "net8",
                                                                "median_ic", "completed", "folds_valid", "fold_ic",
                                                                "fold_net4", "fold_net8")},
                           "eligible": s["eligible"], "validation_gates": gates_v, "bucket_detail": buckets,
                           "pooled_ic": sb.spearman(v.yhat, v.g),
                           "n_eff_validation": int(sum(sb.n_eff(pd.DatetimeIndex(v.decision_time[v.fold == i]),
                                                                np.ones(int((v.fold == i).sum()), bool),
                                                                sb.HORIZONS[chosen["horizon"]]) for i in range(10)))}
    manifest["artifacts"]["ranking_trace"] = dump(OUT / "validation/ranking_trace.json",
                                                  {"rank_keys": sb.freeze()["selection"]["rank_per_side"],
                                                   "tie_tolerance": sb.TIE, "trace": trace})

    # V6 bias controls and the seven robustness removals (non-selectable registry trials)
    finalists = {side: v6_finalist(trace[side]) for side in sb.SIDES}
    bias, robust = {}, {}
    rm_tasks, configs = [], {}
    for side, cfg in finalists.items():
        if cfg is None:
            continue
        cfg = {**cfg, "side": side}
        configs[side] = cfg
        bias[side] = {"config": {k: cfg[k] for k in ("view", "horizon", "model", "k")},
                      "role": "primary" if selection[side].get("selected") and
                      selection[side]["selected"]["view"] == "V6_full" else "diagnostic V6 finalist",
                      "permutation": permutation(preds, labels, feats, cfg),
                      "events": event_disclosure(preds, labels, feats, cfg)}
    removals = {**{f"remove_{g}": tuple(ids) for g, ids in sb.REMOVAL_GROUPS.items()}}
    struct_tags = {}
    for side, cfg in configs.items():
        side_removals = {**removals, f"remove_top_id_{bias[side]['permutation']['top_id']}":
                         (bias[side]["permutation"]["top_id"],)}
        for tag, ids in side_removals.items():
            full_tag = f"{tag}"
            struct_tags.setdefault((struct_key(cfg), full_tag), ids)
        bias[side]["removals"] = list(side_removals)
    for ((view, horizon, model), tag), ids in struct_tags.items():
        for i in range(10):
            rm_tasks.append((view, horizon, i, ids, f"{tag}__{model}", (model,)))
    preds_rm = run_fits(rm_tasks, args.workers, OUT / "robustness_folds")
    for side, cfg in configs.items():
        base = selection[side]
        full = validation_frame(preds, labels, "V6_full", cfg["horizon"], cfg["model"])
        full_ic = sb.spearman(full.yhat, full.g)
        res = {tag: robustness(preds_rm, labels, ledger, cfg, f"{tag}__{cfg['model']}") for tag in bias[side]["removals"]}
        fam = [res[f"remove_{g}"]["pooled_ic"] for g in sb.REMOVAL_GROUPS]
        top = res[f"remove_top_id_{bias[side]['permutation']['top_id']}"]["pooled_ic"]
        shares = [f["id_share"] for f in bias[side]["permutation"]["folds"]]
        robust[side] = {"config": bias[side]["config"], "full_pooled_ic": full_ic, "removals": res,
                        "v6_gates": sb.v6_gates(full_ic, fam, top, shares)}
        if base.get("selected") and base["selected"]["view"] == "V6_full":
            base["v6_gates"] = robust[side]["v6_gates"]
    for side in sb.SIDES:
        s = selection[side]
        if s.get("selected"):
            s["pass"] = bool(s["validation_gates"]["pass"] and (s["selected"]["view"] != "V6_full"
                                                                 or s["v6_gates"]["pass"]))
    manifest["artifacts"]["bias_controls"] = dump(OUT / "validation/bias_controls.json", bias)
    manifest["artifacts"]["robustness"] = dump(OUT / "validation/robustness.json", robust)
    manifest["selection"] = {"per_side": selection, "trace_sha256": manifest["artifacts"]["ranking_trace"]["sha256"],
                             "trace_path": manifest["artifacts"]["ranking_trace"]["path"],
                             "rule": sb.freeze()["selection"]["gate_order"]}
    manifest["robustness_summary"] = {side: {"config": r["config"], "full_pooled_ic": r["full_pooled_ic"],
                                             **{t: {k: v for k, v in x.items() if k != "fold_ic"}
                                                for t, x in r["removals"].items()}, "v6_gates": r["v6_gates"]}
                                      for side, r in robust.items()}

    # registry: 120 selectable + 7 robustness, once
    prior = registry.cumulative_trials(REGISTRY)
    lines = REGISTRY.read_text(encoding="utf-8").splitlines() if REGISTRY.exists() else []
    done = any('"R2-54 Stage-B validation' in line for line in lines)
    t = sb.n_trials()
    if not done:
        if prior != t["registry_base"]:
            raise SystemExit(f"registry {prior} != frozen base {t['registry_base']}; not registering")
        registry.record(REGISTRY, {"experiment": "R2-54 Stage-B validation selection (120 view x H x model x k)",
                                   "n_trials": t["selectable"], "config": {"freeze_sha256": FREEZE_SHA},
                                   "input_hashes": {"features": records["features"]["sha256"]},
                                   "result_summary": {s: selection[s].get("pass") for s in sb.SIDES}})
        registry.record(REGISTRY, {"experiment": "R2-54 Stage-B validation V6 robustness removals (6 family + top id)",
                                   "n_trials": t["robustness"], "config": {"freeze_sha256": FREEZE_SHA},
                                   "result_summary": {s: robust.get(s, {}).get("v6_gates", {}).get("pass")
                                                      for s in sb.SIDES}})
    after = registry.cumulative_trials(REGISTRY)
    manifest["registry"].update({"prior_cumulative": prior if not done else t["registry_base"],
                                 "cumulative_after": after, "registered_now": not done,
                                 "registered_ok": after == t["registry_after"]})

    # final refit of each gate-passing side on all causally eligible pre-test data (test stays LOCKED)
    manifest["final_fit"] = {}
    for side in sb.SIDES:
        s = selection[side]
        if s.get("pass"):
            manifest["final_fit"][side] = final_fit(feats, labels, {**s["selected"]}, sb.TEST_START,
                                                    OUT / "final", f"final_{side}_{s['selected']['view']}_"
                                                                   f"{s['selected']['horizon']}_{s['selected']['model']}")
        else:
            manifest["final_fit"][side] = {"opened": False, "reason": "validation selection or gates failed; no test"}
    manifest["opened_sides"] = [s for s in sb.SIDES if selection[s].get("pass")]
    manifest["bootstrap_plan"] = {**sb.freeze()["bootstrap"], "implementation": "stageb.bootstrap_ic + stageb.holm"}
    manifest["test_runs"] = []
    manifest["runtime_seconds"] = round(time.time() - started, 1)
    dump(OUT / "manifest.json", manifest)
    print(json.dumps({"selection": {s: (selection[s].get("selected") or {}) and
                                    {k: selection[s]["selected"][k] for k in ("view", "horizon", "model", "k", "net4",
                                                                              "net8", "median_ic", "completed")}
                                    for s in sb.SIDES},
                      "pass": {s: selection[s].get("pass") for s in sb.SIDES},
                      "gates": {s: selection[s].get("validation_gates") for s in sb.SIDES},
                      "v6": {s: robust.get(s, {}).get("v6_gates") for s in sb.SIDES},
                      "registry": manifest["registry"], "runtime_seconds": manifest["runtime_seconds"]},
                     indent=1, default=str))


# ---------------------------------------------------------------- final-test replay (shared by dry-run and unlock)
def replay(ctx: Context, feats: sb.Features, labels: pd.DataFrame, cfg: dict, side: str, first: pd.Timestamp,
           end: pd.Timestamp, folder: Path, first_checkpoint: dict | None = None, settle: pd.DataFrame | None = None,
           reuse: list | None = None, tag: str = "") -> dict:
    """final_test_mode: one causal continuous replay from flat at first + 24 h with weekly Thursday retraining
    (stageb.weekly_predictions); positions are never reset at retrain boundaries. first_checkpoint: the committed,
    hash-verified final fit serves the first week (its refit check ran before the unlock). reuse: the checkpoint
    events of an earlier replay, loaded and hash-verified instead of retraining (A3 diagnostic)."""
    times = pd.DatetimeIndex(feats.frame.decision_time)
    cols = sb.view_columns(feats, cfg["view"])
    x = feats.frame[cols].to_numpy(np.float32)
    horizon, h = cfg["horizon"], sb.HORIZONS[cfg["horizon"]]
    g_all = labels[f"g_{horizon}"].to_numpy(float) if labels is not None else np.full(len(times), np.nan)
    schedule = sorted({first, *sb.thursdays(first, end)})
    folder.mkdir(parents=True, exist_ok=True)
    code = hashlib.sha256(json.dumps(code_hashes(), sort_keys=True).encode()).hexdigest()
    fsha = hashlib.sha256(json.dumps(cols).encode()).hexdigest()
    previous = {e["retrain_time"]: e for e in (reuse or [])}

    def load(path: str, digest: str):
        blob = (ROOT / path).read_bytes()
        if sb.sha256_bytes(blob) != digest:
            raise RuntimeError(f"checkpoint {path} hash changed")
        return sb.load_checkpoint(blob)

    def fit(r):
        info = {"code_sha256": code, "feature_sha256": fsha, "publication_time_logical": str(r)}
        if reuse is not None:
            e = previous[str(r)]
            if e.get("checkpoint_path") is None:
                raise RuntimeError(f"no checkpoint in the reused replay ({e.get('fallback')})")
            return load(e["checkpoint_path"], e["checkpoint_sha256"]), {**info, "source": "reused",
                                                                         "checkpoint_sha256": e["checkpoint_sha256"]}
        tr = sb.train_mask(times, h, r)
        if not np.isfinite(g_all[tr]).all() or labels[f"exit_{horizon}"][tr].max() >= r:
            raise RuntimeError("training label crosses the retrain time")
        model = sb.fit_model(cfg["model"], x[tr], g_all[tr], cols)
        blob = sb.checkpoint_bytes(model)
        path = folder / f"{side}_{r:%Y%m%d}.bin"
        path.write_bytes(blob)
        return model, {**info, "source": "weekly retrain", "train_rows": int(tr.sum()),
                       "train_cutoff": str(labels[f"exit_{horizon}"][tr].max()), "checkpoint_path": rel(path),
                       "checkpoint_sha256": sb.sha256_bytes(blob), "written_at": now()}

    first_model = None
    if first_checkpoint is not None and reuse is None:
        ck = first_checkpoint["checkpoint"]
        first_model = (load(ck["path"], ck["sha256"]),
                       {"source": "committed final fit", "checkpoint_path": ck["path"], "checkpoint_sha256": ck["sha256"],
                        "train_rows": first_checkpoint["train_rows"], "code_sha256": code, "feature_sha256": fsha,
                        "train_cutoff": first_checkpoint["train_cutoff_label_exit_max"],
                        "publication_time_logical": str(first)})
    yhat, events = sb.weekly_predictions(times, schedule, end, fit,
                                         lambda model, mask: sb.predict(model, x[mask]), first_model)
    ax = sb.ax_runner()
    start = first + sb.EMBARGO
    mt = pd.DatetimeIndex(ctx.minutes.open_time)
    inside = (mt >= start) & (mt < end)
    minutes = ctx.minutes.loc[inside].reset_index(drop=True)
    e, e_min = (z[inside] for z in ax.e_series(ctx.regime, mt, horizon))
    rows = (times >= start) & (times < end)
    t = times[rows]
    e0 = ax.e_at(ctx.regime, t, horizon)
    table = sb.signal_table(t, yhat[rows], sb.SIDES[side], e0, cfg["k"])
    out = {"checkpoints": events, "k_entry": cfg["k"]}
    settle = settle if settle is not None else sb.actual_settlements(costs._settlements())
    with sb.ledger_settlements(settle):
        for fee, name in ((sb.FEE_NOMINAL, "4bps"), (sb.FEE_STRESS, "8bps")):
            config = replace(sb.CONFIG, fee_per_side=fee, close_at_end=True)
            res = ax.run_ax(table, minutes, e, e_min, start, end, config, np.full(len(minutes), cfg["k"]))
            tr = res.trades.assign(k_entry=cfg["k"])
            parquet(folder / f"{side}{tag}_trades_{name}.parquet", tr)
            parquet(folder / f"{side}{tag}_minute_ledger_{name}.parquet",
                    pd.DataFrame({"open_time": res.minute_pnl.index, "pnl_bps": res.minute_pnl.to_numpy()}))
            admin = tr.exit_reason == "data_end"
            out[name] = {"net_bps": float(res.minute_pnl.sum()),
                         "completed_positions": int(tr.loc[~admin].position_id.nunique()),
                         "data_end_close": {"n": int(admin.sum()), "net_bps": float(tr.loc[admin, "net_bps"].sum())},
                         "fee_bps": float(tr.fee_bps.sum()), "funding_bps": float(tr.funding_bps.sum()),
                         "exit_reasons": tr.exit_reason.value_counts().to_dict()}
            out[f"_trades_{name}"] = tr
    keep = sb.block_mask(times, h, first, end)
    wants = table.side != 0
    out.update(ic=sb.spearman(yhat[keep], g_all[keep]), n_eval=int(keep.sum()), n_eff=sb.n_eff(times, keep, h),
               entry_signals=int(wants.sum()), no_entry_e_rows=int((wants & ~(np.isfinite(e0) & (e0 > 0))).sum()),
               _ic_rows=(yhat[keep], g_all[keep]), _yhat=yhat[rows])
    parquet(folder / f"{side}{tag}_predictions.parquet", pd.DataFrame({"decision_time": t, "yhat": yhat[rows]}))
    return out


def strip(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def dry_run(args) -> None:
    """Replay machinery on [2025-09-01, 2025-12-01): validation-era data already used by fold 10. Code check only."""
    m = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    ctx, _ = pre2026_context()
    feats, labels = load_inputs()
    first, end = sb.folds()[-1]
    out = {"kind": "DRY RUN of the final-test replay code on validation-era data (already seen; not a test result, "
                   "not registered)", "window": [str(first), str(end)], "created_utc": now()}
    for side in sb.SIDES:
        sel = m["selection"]["per_side"][side].get("selected") or \
            next(r for r in json.loads((OUT / "validation/ranking_trace.json").read_text(encoding="utf-8"))["trace"][side])
        cfg = {k: sel[k] for k in ("view", "horizon", "model", "k")}
        r = strip(replay(ctx, feats, labels, cfg, side, first, end, OUT / "dry_run"))
        out[side] = {"config": cfg, "checkpoints": len(r["checkpoints"]),
                     "fallbacks": [c["fallback"] for c in r["checkpoints"] if c.get("fallback")],
                     "train_cutoff_before_retrain": all(pd.Timestamp(c["train_cutoff"]) < pd.Timestamp(c["retrain_time"])
                                                        for c in r["checkpoints"] if "train_cutoff" in c),
                     "blocked_decisions": sum(c["blocked_decisions"] for c in r["checkpoints"]),
                     "completed_positions_4bps": r["4bps"]["completed_positions"], "n_eval": r["n_eval"],
                     "n_eff": r["n_eff"], "no_entry_e_rows": r["no_entry_e_rows"]}
    print(json.dumps(out, indent=1, default=str))
    dump(OUT / "dry_run/dry_run.json", out)


# ---------------------------------------------------------------- one-shot final test
SNAPSHOT_FRAMES = ("market_1m", "technique_metrics", "technique_premium", "funding_events", "funding_live_table",
                   "funding_model_input", "stage_a_2026")


def combine_context(pre_minutes, pre_metrics, pre_premium, pre_settle, pre_predictions, snap: dict,
                    end: pd.Timestamp = sb.TEST_END) -> tuple[Context, pd.DataFrame, pd.DataFrame]:
    """Pre-2026 inputs + snapshot frames (2026) -> (context, feature funding, ledger settlements). Snapshot rows win
    on a shared availability time; the market must be gap-free through end - 1 m."""
    minutes = pd.concat([pre_minutes[data.MINUTE_COLUMNS], snap["market_1m"][data.MINUTE_COLUMNS]], ignore_index=True)
    minutes["open_time"] = pd.to_datetime(minutes.open_time, utc=True).astype("datetime64[ns, UTC]")
    if minutes.open_time.duplicated().any():
        raise RuntimeError("duplicate 1-minute bars across the 2026 boundary")
    minutes = data.validate_minutes(minutes.sort_values("open_time").reset_index(drop=True))
    if minutes.open_time.iloc[-1] != end - sb.MINUTE:
        raise RuntimeError("combined market does not reach the data end")
    metrics = pd.concat([pre_metrics, snap["technique_metrics"]], ignore_index=True).drop_duplicates(
        "available_time", keep="last").sort_values("available_time").reset_index(drop=True)
    premium = pd.concat([pre_premium, snap["technique_premium"]], ignore_index=True).drop_duplicates(
        "available_time", keep="last").sort_values("available_time").reset_index(drop=True)
    events, live = snap["funding_events"], snap["funding_live_table"]
    ev = pd.DataFrame({"time": pd.to_datetime(events.funding_time, utc=True, format="ISO8601"),
                       "rate": events.funding_rate.to_numpy(float)})
    late = pd.DataFrame({"time": pd.to_datetime(live.time, utc=True, format="ISO8601"), "rate": live.rate.to_numpy(float)})
    late = late.loc[late.time > ev.time.max()]           # October: live REST events absent from funding_events
    base = pre_settle.loc[pre_settle.time < sb.TEST_START]
    events_2026 = sb.settlements(pd.concat([ev, late], ignore_index=True))
    settle = sb.settlements(pd.concat([sb.actual_settlements(base), events_2026], ignore_index=True))  # actual times
    t2026, r2026 = sb.simulator_minutes(events_2026)
    technique_funding = pd.concat([base[["time", "rate"]], pd.DataFrame(
        {"time": pd.to_datetime(t2026, utc=True), "rate": r2026})], ignore_index=True)   # sim minute buckets
    fmi = snap["funding_model_input"]
    funding = pd.concat([sb.funding_frame(base),
                         pd.DataFrame({"available_time": pd.to_datetime(fmi.publish_time, utc=True),
                                       "rate": fmi.rate.to_numpy(float), "interval_hours": fmi.interval_hours.to_numpy(float),
                                       "interval_missing": fmi.interval_missing.to_numpy(int)})], ignore_index=True)
    pre_p = pre_predictions.drop(columns=[c for c in ("segment",) if c in pre_predictions]).copy()
    pre_p["logical_available_at"] = pre_p.timestamp
    sa = snap["stage_a_2026"].rename(columns={"prediction_ts": "timestamp"})
    preds = pd.concat([pre_p, sa[list(pre_p.columns)]], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    regime_frame = load_regime(data.validate_predictions(preds))
    ctx = Context(minutes=minutes, metrics=metrics, premium=premium, funding=technique_funding,
                  regime=regime_frame, end=end)
    return ctx, funding, settle


def test_context() -> tuple[Context, pd.DataFrame, pd.DataFrame]:
    snap = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))["artifacts"]
    frames = {name: pd.read_parquet(ROOT / snap[name]["path"]) for name in SNAPSHOT_FRAMES}
    pre = Context.load(end=sb.TEST_START)
    # metrics untruncated: the 2025-12-31 23:55 row (available 2026-01-01 00:00) is needed at T >= 2026-01-01
    return combine_context(pre.minutes, data.load_metrics(end=sb.TEST_START), pre.premium, costs._settlements(),
                           data.load_predictions(end=sb.TEST_START), frames)


def unlock_preconditions(m: dict, confirm: str | None) -> list:
    """Every reason to refuse a final-test run (empty list = allowed). A4: earlier runs do not block."""
    problems = []
    if (m.get("freeze") or {}).get("sha256") != FREEZE_SHA or sha(sb.FREEZE_PATH) != FREEZE_SHA:
        problems.append("freeze hash missing or changed")
    if (m.get("snapshot") or {}).get("manifest_sha256") != SNAPSHOT_SHA or sha(SNAPSHOT / "manifest.json") != SNAPSHOT_SHA:
        problems.append("snapshot hash missing or changed")
    sel = m.get("selection") or {}
    trace = ROOT / sel.get("trace_path", "missing")
    if not sel.get("trace_sha256") or not trace.exists() or sha(trace) != sel["trace_sha256"]:
        problems.append("selection trace hash missing or changed")
    opened = m.get("opened_sides") or []
    if not opened:
        problems.append("no side passed validation; nothing to open")
    for side in opened:
        ck = ((m.get("final_fit") or {}).get(side) or {}).get("checkpoint") or {}
        if not ck.get("sha256") or not (ROOT / ck.get("path", "missing")).exists() or sha(ROOT / ck["path"]) != ck["sha256"]:
            problems.append(f"{side} final checkpoint hash missing or changed")
    if not (m.get("registry") or {}).get("registered_ok"):
        problems.append("registry 127 trials not recorded")
    if m.get("code_sha256") != code_hashes():
        problems.append("code hashes differ from the frozen manifest code_sha256")
    if confirm != CONFIRM:
        problems.append(f"explicit confirmation missing (--confirm {CONFIRM})")
    return problems


TEST_RUNS = OUT / "test_runs.jsonl"


def append_run(log: Path, record: dict, run_id: int | None = None) -> dict:
    """A4 run log: append-only JSON lines; a new run gets the next run_id."""
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] if log.exists() else []
    if run_id is None:
        run_id = 1 + max((r["run_id"] for r in rows), default=0)
    row = {"run_id": run_id, "utc": now(), **record}
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def refit_check(m: dict) -> dict:
    """Before any 2026 access: refit each opened side on the pre-2026 artifacts; the hash must equal the committed
    final checkpoint."""
    feats, labels = load_inputs()
    out = {}
    scratch = OUT / "unlock_refit_check"
    for side in m["opened_sides"]:
        ff = m["final_fit"][side]
        refit = final_fit(feats, labels, {**m["selection"]["per_side"][side]["selected"]}, sb.TEST_START, scratch,
                          f"refit_{side}")
        out[side] = {"committed": ff["checkpoint"]["sha256"], "refit": refit["checkpoint"]["sha256"],
                     "equal": refit["checkpoint"]["sha256"] == ff["checkpoint"]["sha256"]}
    return out


def unlock(args) -> None:
    path = OUT / "manifest.json"
    if not path.exists():
        raise SystemExit("refused: no Stage-B manifest")
    m = json.loads(path.read_text(encoding="utf-8"))
    problems = unlock_preconditions(m, args.confirm)
    if problems:
        raise SystemExit("refused: " + "; ".join(problems))
    snapshot = verify_snapshot(read_frames=False)          # file hashes only; SystemExit refuses before the flag
    refit = refit_check(m)                                  # pre-2026 artifacts only
    if not all(r["equal"] for r in refit.values()):
        raise SystemExit(f"refused: final checkpoint refit hash differs {refit}")
    inputs = {"freeze_sha256": FREEZE_SHA, "snapshot_manifest_sha256": SNAPSHOT_SHA,
              "trace_sha256": m["selection"]["trace_sha256"],
              "final_checkpoints": {s: m["final_fit"][s]["checkpoint"]["sha256"] for s in m["opened_sides"]}}
    start = append_run(TEST_RUNS, {"status": "STARTED", "pid": os.getpid(), "host": socket.gethostname(),
                                   "user": getpass.getuser(), "python": sys.version, "platform": platform.platform(),
                                   "argv": sys.argv, "git": git(), "code_sha256": code_hashes(), "inputs": inputs,
                                   "snapshot_verified": snapshot, "refit_check": refit})
    run_id = start["run_id"]
    m.setdefault("test_runs", []).append({"run_id": run_id, "started_utc": start["utc"], "status": "STARTED",
                                          "inputs": inputs})
    m["test_status"] = f"TEST RUN {run_id} (A4: repeatable, logged, counted)"
    dump(path, m)                                      # recorded before any 2026 frame is read
    test = {"snapshot": verify_snapshot(read_frames=True)}
    ctx, funding, settle = test_context()
    feats = sb.build_features(ctx, sb.DEV_START, sb.TEST_END, funding)
    sb.assert_causal(feats)
    old, _ = load_inputs()
    n = len(old.frame)
    same = old.frame.columns.equals(feats.frame.columns) and old.frame.equals(feats.frame.iloc[:n].reset_index(drop=True))
    test["pre_2026_feature_parity"] = {"rows": n, "identical": bool(same)}
    if not same:
        status = "ABORTED: pre-2026 feature rows differ between validation and test builds"
        m["test_runs"][-1].update(status=status, test=test)
        dump(path, m)
        append_run(TEST_RUNS, {"status": status, "test": test}, run_id)
        raise SystemExit(status)
    labels = sb.make_labels(ctx.minutes, pd.DatetimeIndex(feats.frame.decision_time))   # test labels opened here
    sb.assert_isolated(feats.frame, labels)
    folder = OUT / f"test/run_{run_id:02d}"
    parquet(folder / "features_full.parquet", feats.frame)
    parquet(folder / "labels_full.parquet", labels)
    results, pvals, raw = {}, {}, {}
    for side in sb.SIDES:
        if side not in m["opened_sides"]:
            results[side] = {"opened": False, "reason": m["final_fit"][side].get("reason")}
            pvals[side] = None
            continue
        cfg = {**m["selection"]["per_side"][side]["selected"]}
        r = replay(ctx, feats, labels, cfg, side, sb.TEST_START, sb.TEST_END, folder, m["final_fit"][side], settle)
        raw[side] = r
        x, y = r["_ic_rows"]
        plan = sb.freeze()["bootstrap"]
        boot = sb.bootstrap_ic(x, y, block=plan["block_rows"], reps=plan["replicates"], seed=plan["seed"])
        results[side] = {"opened": True, "config": cfg, **strip(r), "bootstrap": boot}
        pvals[side] = boot["p"]
    h = sb.holm(pvals)
    for side, r in results.items():
        if not r["opened"]:
            r["gates"] = {"pass": False, "reason": "not opened"}
            continue
        r["gates"] = sb.final_gates(r, h[side])
    record = {**test, "status": "PRIMARY_FROZEN", "results": results, "holm": h, "written_utc": now(),
              "claim_rule": sb.freeze()["manifest"]["result_claim"], "folder": rel(folder)}
    m["test_runs"][-1].update(record)
    dump(path, m)                                      # primary result frozen before any oracle or diagnostic
    append_run(TEST_RUNS, {"status": "PRIMARY_FROZEN", "results": results, "holm": h}, run_id)
    extra = {"oracles_non_selectable": oracles(ctx, feats, labels, m, settle, folder),
             "a3_taker_source_diagnostic": taker_diagnostic(ctx, funding, labels, m, settle, folder, raw)}
    m["test_runs"][-1].update(extra, status="COMPLETED")
    dump(path, m)
    append_run(TEST_RUNS, {"status": "COMPLETED", **extra}, run_id)
    print(json.dumps({s: results[s].get("gates") for s in sb.SIDES}, indent=1, default=str))


def oracles(ctx, feats, labels, m, settle, folder) -> dict:
    """NON_SELECTABLE_ORACLE outputs through the same rule and safety (after the primary result is frozen)."""
    ax = sb.ax_runner()
    times = pd.DatetimeIndex(feats.frame.decision_time)
    start = sb.TEST_START + sb.EMBARGO
    mt = pd.DatetimeIndex(ctx.minutes.open_time)
    inside = (mt >= start) & (mt < sb.TEST_END)
    minutes = ctx.minutes.loc[inside].reset_index(drop=True)
    rows = (times >= start) & (times < sb.TEST_END)
    out = {}
    for side in m["opened_sides"]:
        cfg = m["selection"]["per_side"][side]["selected"]
        s = sb.SIDES[side]
        horizon = cfg["horizon"]
        g = labels[f"g_{horizon}"].to_numpy(float)
        tr = sb.train_mask(times, sb.HORIZONS[horizon], sb.TEST_START)
        all_g = np.column_stack([labels[f"g_{x}"].to_numpy(float) for x in sb.HORIZONS])
        with np.errstate(invalid="ignore"):
            best = s * np.nanmax(s * all_g, axis=1)
        forecasts = {"perfect_return": g, "hindsight_best_horizon": best,
                     "sign_only_train_median": np.sign(g) * np.nanmedian(np.abs(g[tr]))}
        e, e_min = (z[inside] for z in ax.e_series(ctx.regime, mt, horizon))
        e0 = ax.e_at(ctx.regime, times[rows], horizon)
        out[side] = {}
        for name, f in forecasts.items():
            table = sb.signal_table(times[rows], f[rows], s, e0, cfg["k"])
            with sb.ledger_settlements(settle):
                res = ax.run_ax(table, minutes, e, e_min, start, sb.TEST_END, replace(sb.CONFIG, close_at_end=True),
                                np.full(len(minutes), cfg["k"]))
            out[side][name] = {"label": "NON_SELECTABLE_ORACLE", "net4_bps": float(res.minute_pnl.sum()),
                               "positions": int(res.trades.position_id.nunique())}
    return out


def rest_taker_metrics(metrics: pd.DataFrame, rest: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    """Archive metrics with taker_lsr replaced by REST buy_sell_ratio for rows available in (a, b] (period end);
    a period without a REST row becomes missing (never filled from the archive, amendment A3)."""
    when = pd.to_datetime(rest.create_time, utc=True, format="ISO8601") + pd.Timedelta(minutes=5)
    values = pd.Series(rest.buy_sell_ratio.to_numpy(float), index=pd.DatetimeIndex(when)).groupby(level=0).last()
    out = metrics.copy()
    swap = ((out.available_time > a) & (out.available_time <= b)).to_numpy()
    out.loc[swap, "taker_lsr"] = values.reindex(pd.DatetimeIndex(out.available_time[swap])).to_numpy()
    return out


def compare_trades(archive: pd.DataFrame, rest: pd.DataFrame) -> dict:
    """Position-level comparison of two continuous replays: matched and unmatched entry times, exit differences."""
    a = archive.drop_duplicates("position_id").set_index("entry_time")
    r = rest.drop_duplicates("position_id").set_index("entry_time")
    both = a.index.intersection(r.index)
    exit_diff = [{"entry_time": str(t), "exit_archive": str(a.exit_time[t]), "exit_rest": str(r.exit_time[t])}
                 for t in both if a.exit_time[t] != r.exit_time[t]]
    return {"positions_archive": len(a), "positions_rest": len(r), "matched_entry_times": len(both),
            "only_archive_entry_times": [str(t) for t in a.index.difference(r.index)],
            "only_rest_entry_times": [str(t) for t in r.index.difference(a.index)],
            "matched_with_different_exit": exit_diff,
            "net4_archive": float(archive.net_bps.sum()), "net4_rest": float(rest.net_bps.sum())}


def taker_diagnostic(ctx, funding, labels, m, settle, folder, primary: dict) -> dict:
    """Amendment A3 (report only): the identical continuous replay (same checkpoints, rule, k and ledger) with REST
    instead of archive taker on 2026-10-01..10-07; records the actual entry/exit time differences."""
    import sqlite3
    db = BASE / "parity/rest_staging.sqlite"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        rest = pd.read_sql_query("SELECT create_time, buy_sell_ratio FROM futures_taker_lsr_5m WHERE source='rest'", c)
    a, b = pd.Timestamp("2026-10-01", tz="UTC"), sb.TEST_END
    alt = replace(ctx, metrics=rest_taker_metrics(ctx.metrics, rest, a, b))
    alt_f = sb.build_features(alt, sb.DEV_START, sb.TEST_END, funding)
    out = {"rest_rows": len(rest), "window": [str(a), str(b)],
           "note": "REST rows placed at period end (logical); staging received_at is after the window, so this is "
                   "the as-if-real-time comparison; report only, no reselection"}
    for side in m["opened_sides"]:
        cfg = m["selection"]["per_side"][side]["selected"]
        r = replay(alt, alt_f, labels, cfg, side, sb.TEST_START, sb.TEST_END, folder, m["final_fit"][side], settle,
                   reuse=primary[side]["checkpoints"], tag="_rest_taker")
        diff = np.abs(r["_yhat"] - primary[side]["_yhat"])
        out[side] = {"max_abs_yhat_diff": float(np.nanmax(diff)) if np.isfinite(diff).any() else 0.0,
                     "decisions_with_yhat_diff": int((diff > 0).sum()),
                     **compare_trades(primary[side]["_trades_4bps"], r["_trades_4bps"])}
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--workers", type=int, default=4)
    sub.add_parser("dry-run")
    u = sub.add_parser("unlock-test"); u.add_argument("--confirm", default=None)
    args = p.parse_args()
    {"run": run, "dry-run": dry_run, "unlock-test": unlock}[args.cmd](args)


if __name__ == "__main__":
    main()
