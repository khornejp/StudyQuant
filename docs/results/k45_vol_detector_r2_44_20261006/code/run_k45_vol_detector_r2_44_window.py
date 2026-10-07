"""R2-44 volatility-only detector: training-window and target-normalisation grid.

User decision 2026-10-06 (option B): stop R2-43-exc and compare training windows
before running every architecture.  Data, inputs, model, labels, naive baseline and
predictive metrics are reused from out/run_k45_vol_detector_r2_43.py.  Only these
pre-registered items change:

- training window: 730/365/180/90 days hard, or expanding with recency-weighted sampling
- target: raw log1p(bps) or log ratio to the trailing 30-day realised volatility scale
- actual "high"/tertile: causal trailing 90-day quantiles of realised actuals
  (labels whose end is at or before the decision time), applied to every candidate
- predicted "high"/tertile (user decision 2026-10-06, rank method): the prediction's
  rank against the model's own predictions from the previous 30 days (strictly earlier
  rows, minimum 7 days).  Evaluation of a segment uses the preceding segment as warm-up.

No return, trade or backtest artefact is read or written.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
R243_PATH = ROOT / "out/run_k45_vol_detector_r2_43.py"
_spec = importlib.util.spec_from_file_location("r243", R243_PATH)
r = importlib.util.module_from_spec(_spec)
sys.modules["r243"] = r
_spec.loader.exec_module(r)

OUT = ROOT / "out/k45_vol_detector_r2_44_window_20261006"
r.OUT = OUT  # fold_paths / valid_completed_fold / collect_predictions write here
TEST_FILE = ROOT / "tests/test_k45_vol_detector_r2_44.py"

CONFIG = r.CONFIGS["compact"]
CADENCE_DAYS = 7
SCALE_DAYS = 30
THRESHOLD_DAYS = 90
SCALE_FLOOR_BPS = 1.0
DATA_START = pd.Timestamp("2020-01-01", tz="UTC")
EARLIEST_ORIGIN = DATA_START + pd.Timedelta(days=SCALE_DAYS + 1)
EXPANDING_BUDGET_DAYS = 305  # samples per epoch = a 365-day hard window's training part
MAX_EPOCHS, PATIENCE = 6, 2
RANK_DAYS, RANK_MIN_DAYS = 30, 7
SEGMENT_ORDER = ("DEV_FRONT", "DEV_BACK", "HOLD_B")
FROZEN_HYPOTHESIS = (
    "동일 compact PatchTST에서 학습 창 길이·최근 가중·30일 변동성 정규화를 바꾸면 "
    "15개 unsigned 변동성 타겟의 OOS 예측 품질이 730일 원값보다 좋아진다."
)
# Tuple order is also the tie order (within .01 of the best score, first wins).
CANDIDATES = (
    {"name": "w365_raw", "window_days": 365, "normalized": False, "half_life_days": None},
    {"name": "w365_norm", "window_days": 365, "normalized": True, "half_life_days": None},
    {"name": "w730_raw", "window_days": 730, "normalized": False, "half_life_days": None},
    {"name": "w180_raw", "window_days": 180, "normalized": False, "half_life_days": None},
    {"name": "w180_norm", "window_days": 180, "normalized": True, "half_life_days": None},
    {"name": "exp_hl180_norm", "window_days": None, "normalized": True, "half_life_days": 180},
    {"name": "exp_hl90_norm", "window_days": None, "normalized": True, "half_life_days": 90},
    {"name": "w90_raw", "window_days": 90, "normalized": False, "half_life_days": None},
)
TARGET_HORIZONS = tuple(r.HORIZONS_MINUTES[j % len(r.HORIZONS_MINUTES)]
                        for j in range(len(r.TARGETS)))


def stop_days(candidate: dict) -> int:
    window = candidate["window_days"]
    return 60 if window is None or window >= 365 else window // 6


def split_indices(origins: pd.DatetimeIndex, retrain_time: pd.Timestamp,
                  candidate: dict) -> tuple[np.ndarray, np.ndarray]:
    label_end = origins + pd.Timedelta(hours=24)
    cutoff = retrain_time - pd.Timedelta(hours=24)
    split = cutoff - pd.Timedelta(days=stop_days(candidate))
    window = candidate["window_days"]
    start = DATA_START if window is None else cutoff - pd.Timedelta(days=window)
    usable = origins >= EARLIEST_ORIGIN
    train = np.flatnonzero(usable & (label_end >= start) & (label_end < split))
    stop = np.flatnonzero(usable & (label_end >= split) & (label_end < cutoff))
    return train, stop


def scale_bps(minutes: pd.DataFrame, origins: pd.DatetimeIndex) -> np.ndarray:
    """Trailing 30-day realised volatility scaled to each target horizon (bps)."""
    close = minutes.close.to_numpy(float)
    returns = np.r_[np.nan, np.diff(np.log(close))]
    prefix = np.r_[0.0, np.cumsum(np.nan_to_num(returns, nan=0.0) ** 2)]
    starts = np.searchsorted(minutes.open_time.array.asi8, origins.asi8)
    span = SCALE_DAYS * 1440
    valid = starts >= span + 1
    variance = np.full(len(origins), np.nan)
    variance[valid] = (prefix[starts[valid]] - prefix[starts[valid] - span]) / span
    return np.column_stack([np.sqrt(variance * horizon) * 1e4 for horizon in TARGET_HORIZONS])


def to_z(value: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.log((value + SCALE_FLOOR_BPS) / (scale + SCALE_FLOOR_BPS))


def from_z(z: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.maximum(np.exp(z) * (scale + SCALE_FLOOR_BPS) - SCALE_FLOOR_BPS, 0.0)


def causal_thresholds(origins: pd.DatetimeIndex, actual: np.ndarray) -> np.ndarray:
    """[3, N, targets] trailing-90-day q33/q67/q80 of labels already ended at each origin."""
    result = np.full((3, len(origins), actual.shape[1]), np.nan)
    for column, horizon in enumerate(TARGET_HORIZONS):
        series = pd.Series(actual[:, column], index=origins + pd.Timedelta(minutes=horizon)).dropna()
        for row, quantile in enumerate((1 / 3, 2 / 3, .8)):
            rolled = series.rolling(f"{THRESHOLD_DAYS}D",
                                    min_periods=THRESHOLD_DAYS * 96 // 2).quantile(quantile)
            positions = np.searchsorted(rolled.index.asi8, origins.asi8, side="right") - 1
            valid = positions >= 0
            result[row, valid, column] = rolled.to_numpy()[positions[valid]]
    return result


def epoch_order(rng: np.random.Generator, label_end: pd.DatetimeIndex, cutoff: pd.Timestamp,
                candidate: dict) -> np.ndarray:
    if candidate["half_life_days"] is None:
        return rng.permutation(len(label_end))
    age = (cutoff - label_end) / pd.Timedelta(days=1)
    weight = 0.5 ** (np.asarray(age, float) / candidate["half_life_days"])
    budget = min(len(label_end), EXPANDING_BUDGET_DAYS * 96)
    return rng.choice(len(label_end), size=budget, replace=False, p=weight / weight.sum())


class Data:
    def __init__(self):
        base = r.load_dataset()
        self.minutes, self.bars, self.arrays = base.minutes, base.bars, base.arrays
        self.origins, self.naive = base.origins, base.naive
        self.actual = np.expm1(base.targets_log.astype(float))
        self.raw_target = base.targets_log
        self.scale = scale_bps(self.minutes, self.origins)
        self.norm_target = to_z(self.actual, self.scale).astype(np.float32)
        self.thresholds = causal_thresholds(self.origins, self.actual)


def fit_fold(data: Data, candidate: dict, retrain_time: pd.Timestamp,
             prediction_end: pd.Timestamp, device: torch.device) -> tuple[dict, pd.DataFrame]:
    config = CONFIG
    target = data.norm_target if candidate["normalized"] else data.raw_target
    train, stop = split_indices(data.origins, retrain_time, candidate)
    finite = np.isfinite(target).all(1)
    train, stop = train[finite[train]], stop[finite[stop]]
    predict = np.flatnonzero((data.origins >= retrain_time) & (data.origins < prediction_end) &
                             finite & np.isfinite(data.thresholds).all((0, 2)))
    if min(len(train), len(stop), len(predict)) == 0:
        raise ValueError("empty frozen fold")
    endpoint_sets = [r.endpoint_indices(data.bars, data.origins[index])
                     for index in (train, stop, predict)]
    for endpoints in endpoint_sets:
        for end, lookback in zip(endpoints, config.lookbacks):
            if end.min() < lookback - 1:
                raise ValueError("insufficient causal lookback")

    first, scaler_end = data.origins[train[0]], data.origins[train[-1]]
    means, stds = [], []
    for frame, values, lookback, step in zip(data.bars, data.arrays, config.lookbacks,
                                             ("1min", "5min", "1h")):
        allowed = ((frame.decision_time >= first - pd.Timedelta(step) * lookback) &
                   (frame.decision_time <= scaler_end)).to_numpy()
        mean, std = np.nanmean(values[allowed], 0), np.nanstd(values[allowed], 0)
        mean[~np.isfinite(mean)] = 0
        std[(~np.isfinite(std)) | (std == 0)] = 1
        means.append(mean.astype(np.float32)); stds.append(std.astype(np.float32))

    r.seed_all()
    model = r.MultiResolutionPatchTST(config, tuple(a.shape[1] for a in data.arrays))
    if candidate["normalized"]:
        model.head[-1] = nn.Identity()  # log-ratio targets can be negative
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-5)
    rng = np.random.default_rng(r.SEED)
    cutoff = retrain_time - pd.Timedelta(hours=24)
    label_end = data.origins[train] + pd.Timedelta(hours=24)
    best, best_state, stale, history = float("inf"), None, 0, []
    started = time.perf_counter()
    for epoch in range(MAX_EPOCHS):
        model.train()
        losses = []
        order = epoch_order(rng, label_end, cutoff, candidate)
        for start in range(0, len(order), config.batch_size):
            chosen = order[start:start + config.batch_size]
            x = r.batch(data.arrays, endpoint_sets[0], chosen, config.lookbacks, means, stds, device)
            y = torch.from_numpy(target[train[chosen]]).to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.smooth_l1_loss(model(x), y)
            if not torch.isfinite(loss):
                raise ValueError("non-finite loss")
            loss.backward(); optimizer.step()
            losses.append(float(loss.detach()))
        stop_prediction = r._predict(model, data, stop, endpoint_sets[1], config, means, stds, device)
        stop_loss = float(np.abs(stop_prediction - target[stop]).mean())
        history.append({"epoch": epoch + 1, "train_loss": float(np.mean(losses)),
                        "stop_mae": stop_loss, "samples": len(order)})
        if stop_loss < best - 1e-6:
            best, stale = stop_loss, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    model.load_state_dict(best_state)
    raw = r._predict(model, data, predict, endpoint_sets[2], config, means, stds, device)
    prediction = (from_z(raw, data.scale[predict]) if candidate["normalized"] else np.expm1(raw))
    actual = data.actual[predict]
    q33, q67, q80 = (data.thresholds[k][predict] for k in range(3))
    columns = {"timestamp": data.origins[predict], "retrain_time": retrain_time}
    for column, name in enumerate(r.TARGETS):
        columns[f"prediction_{name}"] = prediction[:, column]
        columns[f"actual_{name}"] = actual[:, column]
        columns[f"naive_{name}"] = data.naive[predict, column]
        columns[f"scale_{name}"] = data.scale[predict, column]
        columns[f"threshold_q80_{name}"] = q80[:, column]
        columns[f"actual_class_{name}"] = ((actual[:, column] > q33[:, column]).astype(int) +
                                           (actual[:, column] > q67[:, column]))
        columns[f"level_class_{name}"] = ((prediction[:, column] > q33[:, column]).astype(int) +
                                          (prediction[:, column] > q67[:, column]))
        columns[f"actual_high_{name}"] = actual[:, column] > q80[:, column]
        columns[f"level_high_{name}"] = prediction[:, column] > q80[:, column]
    checkpoint = {"model_state": best_state, "candidate": candidate, "seed": r.SEED,
                  "retrain_time": str(retrain_time), "prediction_end": str(prediction_end),
                  "means": means, "stds": stds, "train_rows": len(train), "stop_rows": len(stop),
                  "prediction_rows": len(predict), "history": history, "best_stop_mae": best,
                  "elapsed_seconds": time.perf_counter() - started}
    return checkpoint, pd.DataFrame(columns)


def rank_flags(frame: pd.DataFrame) -> pd.DataFrame:
    """Add prediction_high/prediction_class from the model's own trailing prediction ranks."""
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    index = pd.DatetimeIndex(frame.timestamp)
    added = {}
    for name in r.TARGETS:
        past = pd.Series(frame[f"prediction_{name}"].to_numpy(float), index=index).shift(1)
        rolling = past.rolling(f"{RANK_DAYS}D", min_periods=RANK_MIN_DAYS * 96)
        q33, q67, q80 = (rolling.quantile(q).to_numpy() for q in (1 / 3, 2 / 3, .8))
        value = frame[f"prediction_{name}"].to_numpy(float)
        added[f"rank_ready_{name}"] = np.isfinite(q80)
        added[f"prediction_high_{name}"] = value > q80
        added[f"prediction_class_{name}"] = (value > q33).astype(int) + (value > q67)
    frame = frame.drop(columns=[c for c in added if c in frame], errors="ignore")
    return pd.concat([frame, pd.DataFrame(added)], axis=1)


def average_precision(score: np.ndarray, truth: np.ndarray) -> float:
    order = np.argsort(-score, kind="stable")
    hits = truth[order].astype(float)
    if not hits.any():
        return float("nan")
    precision = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float((precision * hits).sum() / hits.sum())


def evaluate(name: str, segment: str) -> dict:
    """Predictive metrics for one segment, rank flags warmed up by the previous segment."""
    position = SEGMENT_ORDER.index(segment)
    parts = [r.collect_predictions(name, seg) for seg in SEGMENT_ORDER[max(0, position - 1):position + 1]
             if (OUT / "folds" / name / seg).exists()]
    frame = rank_flags(pd.concat(parts, ignore_index=True))
    frame = frame[frame.segment.eq(segment)]
    ready = np.column_stack([frame[f"rank_ready_{t}"] for t in r.TARGETS]).all(1)
    frame = frame[ready].reset_index(drop=True)
    metrics = r.predictive_metrics(frame)
    extra = {}
    for target in r.TARGETS:
        flag = frame[f"prediction_high_{target}"].to_numpy(bool)
        truth = frame[f"actual_high_{target}"].to_numpy(bool)
        base = float(truth.mean())
        precision = float(truth[flag].mean()) if flag.any() else float("nan")
        extra[target] = {"base_rate": base, "flag_rate": float(flag.mean()), "precision": precision,
                         "recall": float(flag[truth].mean()) if truth.any() else float("nan"),
                         "lift": precision / base if base else float("nan"),
                         "average_precision": average_precision(
                             frame[f"prediction_{target}"].to_numpy(float), truth)}
    metrics["rank_flag_detail"] = extra
    metrics["rank_flag_rows_dropped_for_warmup"] = int((~ready).sum())
    return metrics


# ---------------------------------------------------------------- run control

def frozen_payload(tests: dict) -> dict:
    return {
        "experiment": "R2-44", "source": "local Binance USD-M BTCUSDT public archives",
        "timestamp_utc": r.utc_now(), "data_cutoff": "2026-06-30T23:59:00Z",
        "frozen_hypothesis_1": FROZEN_HYPOTHESIS, "seed": r.SEED, "model": "compact",
        "cadence_days": CADENCE_DAYS, "targets": list(r.TARGETS), "splits": r.SPLITS,
        "candidates": list(CANDIDATES),
        "stop_days": "60 for >=365d and expanding, window/6 otherwise",
        "expanding": f"data start {DATA_START.date()}, weighted sampling without replacement, "
                     f"{EXPANDING_BUDGET_DAYS}d x 96 samples per epoch",
        "normalization": f"log((y+{SCALE_FLOOR_BPS})/(s+{SCALE_FLOOR_BPS})), s = trailing "
                         f"{SCALE_DAYS}d 1m realised vol x sqrt(horizon minutes)",
        "high_reference": f"trailing {THRESHOLD_DAYS}d q33/q67/q80 of actuals with label end <= T",
        "flag_method": f"rank: prediction vs model's own previous {RANK_DAYS}d predictions "
                       f"(strictly earlier, min {RANK_MIN_DAYS}d); previous segment as warm-up; "
                       "level-method flags stored as level_* for reference only",
        "amendment": "2026-10-06 user chose rank flags before any DEV_BACK/HOLD_B; level-flag run "
                     "stopped at 20 DEV_FRONT folds and kept as *_superseded_level_flag",
        "training": {"optimizer": "AdamW", "learning_rate": 1e-3, "weight_decay": 1e-5,
                     "loss": "SmoothL1", "max_epochs": MAX_EPOCHS, "patience": PATIENCE},
        "selection": {"score": "DEV_FRONT equal-weight mean of 15 monthly rank ICs",
                      "tie_range": .01, "tie_order": [c["name"] for c in CANDIDATES]},
        "criteria": "R2-43 pass_criteria unchanged; DEV_BACK once, then HOLD_B once",
        "multiple_testing": "ledger 5,114 + 8 = 5,122",
        "focused_tests": tests, "inputs": r.input_records(),
        "sources": [r.file_record(path) for path in (R243_PATH, SCRIPT, TEST_FILE)],
    }


def freeze() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", str(TEST_FILE),
                           "--basetemp", str(OUT / ".pytest_tmp")], cwd=ROOT,
                          text=True, capture_output=True, check=False)
    lines = (done.stdout + done.stderr).strip().splitlines()
    if done.returncode:
        raise RuntimeError("focused tests failed: " + (lines[-1] if lines else ""))
    frozen = frozen_payload({"status": "PASS", "summary": lines[-1], "timestamp_utc": r.utc_now()})
    manifest = {"status": "FROZEN", "frozen": frozen,
                "freeze_manifest_hash": r.canonical_hash(frozen), "out_of_sample_result": None}
    if (OUT / "manifest.json").exists():
        raise RuntimeError("manifest exists; result-dependent refreeze forbidden")
    r.write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"status": "FROZEN", "hash": manifest["freeze_manifest_hash"]}))


def verify_manifest() -> dict:
    manifest = r.read_json(OUT / "manifest.json")
    if r.canonical_hash(manifest["frozen"]) != manifest["freeze_manifest_hash"]:
        raise RuntimeError("frozen manifest hash mismatch")
    if r.input_records() != manifest["frozen"]["inputs"]:
        raise RuntimeError("input hash mismatch")
    for record in manifest["frozen"]["sources"]:
        if r.sha256_file(ROOT / record["path"]) != record["sha256"]:
            raise RuntimeError(f"source hash mismatch: {record['path']}")
    return manifest


def write_progress(progress: dict, started: float) -> None:
    progress["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    done, total = progress["completed_folds"], progress["total_folds"]
    if progress["run_folds"]:
        eta = progress["elapsed_seconds"] / progress["run_folds"] * (total - done)
        progress["eta_seconds"] = round(eta, 1)
        progress["estimated_completion_utc"] = (pd.Timestamp.now(tz="UTC") +
                                                pd.Timedelta(seconds=eta)).isoformat()
    r.write_json(OUT / "progress.json", progress)


def run_segment(data: Data, candidate: dict, segment: str, device: torch.device,
                manifest_hash: str, progress: dict, started: float) -> None:
    name = candidate["name"]
    for fold, (retrain_time, prediction_end) in enumerate(r.fold_schedule(segment, CADENCE_DAYS)):
        if r.valid_completed_fold(name, segment, fold, manifest_hash):
            continue
        fold_started = time.perf_counter()
        checkpoint, frame = fit_fold(data, candidate, retrain_time, prediction_end, device)
        checkpoint_path, prediction_path, metadata_path = r.fold_paths(name, segment, fold)
        r.atomic_torch_save(checkpoint_path, checkpoint)
        frame.insert(0, "candidate", name); frame.insert(1, "segment", segment)
        frame.insert(2, "fold", fold)
        r.write_parquet(prediction_path, frame)
        r.write_json(metadata_path, {
            "freeze_manifest_hash": manifest_hash,
            "checkpoint_sha256": r.sha256_file(checkpoint_path),
            "predictions_sha256": r.sha256_file(prediction_path),
            "retrain_time": str(retrain_time), "prediction_end": str(prediction_end),
            "elapsed_seconds": time.perf_counter() - fold_started, "completed_utc": r.utc_now()})
        progress["candidate_folds"].setdefault(f"{name}/{segment}", 0)
        progress["candidate_folds"][f"{name}/{segment}"] += 1
        progress["completed_folds"] += 1
        progress["run_folds"] += 1
        write_progress(progress, started)


def choose(scores: dict[str, float]) -> str:
    best = max(scores.values())
    return next(c["name"] for c in CANDIDATES if scores[c["name"]] >= best - .01)


def train() -> None:
    manifest = verify_manifest()
    digest = manifest["freeze_manifest_hash"]
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    torch.set_num_threads(4)
    device = torch.device("cuda:0")
    started = time.perf_counter()
    folds = len(r.fold_schedule("DEV_FRONT", CADENCE_DAYS))
    progress = {"status": "TRAINING", "freeze_manifest_hash": digest, "pid": os.getpid(),
                "started_utc": r.utc_now(), "candidate_folds": {},
                "completed_folds": sum(r.valid_completed_fold(c["name"], "DEV_FRONT", f, digest)
                                       for c in CANDIDATES for f in range(folds)),
                "total_folds": folds * len(CANDIDATES), "run_folds": 0, "last_error": None}
    write_progress(progress, started)
    try:
        data = Data()
        for candidate in CANDIDATES:
            run_segment(data, candidate, "DEV_FRONT", device, digest, progress, started)
        metrics = {c["name"]: evaluate(c["name"], "DEV_FRONT") for c in CANDIDATES}
        scores = {name: value["monthly_mean_rank_ic"] for name, value in metrics.items()}
        selected = choose(scores)
        r.write_json(OUT / "selection.json", {"selected": selected, "scores": scores,
                                              "metrics": metrics, "timestamp_utc": r.utc_now()})
        candidate = next(c for c in CANDIDATES if c["name"] == selected)
        progress["status"] = "VALIDATING"
        progress["total_folds"] += len(r.fold_schedule("DEV_BACK", CADENCE_DAYS))
        write_progress(progress, started)
        run_segment(data, candidate, "DEV_BACK", device, digest, progress, started)
        dev_back = evaluate(selected, "DEV_BACK")
        hold_b = None
        if dev_back["passed"]:
            progress["total_folds"] += len(r.fold_schedule("HOLD_B", CADENCE_DAYS))
            run_segment(data, candidate, "HOLD_B", device, digest, progress, started)
            hold_b = evaluate(selected, "HOLD_B")
        status = "DETECTOR_ACCEPTED" if hold_b and hold_b["passed"] else "NO_DETECTOR"
        manifest["status"] = "COMPLETE_" + status
        manifest["out_of_sample_result"] = {"selected": selected, "DEV_BACK": dev_back,
                                            "HOLD_B": hold_b}
        r.write_json(OUT / "manifest.json", manifest)
        r.write_json(OUT / "decision.json", {"status": status, "selected": selected,
                                             "DEV_FRONT": metrics[selected],
                                             "DEV_BACK": dev_back, "HOLD_B": hold_b})
        progress["status"] = manifest["status"]
        write_progress(progress, started)
    except Exception as error:
        progress["status"] = "FAILED"
        progress["last_error"] = f"{type(error).__name__}: {error}"
        write_progress(progress, started)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "train"))
    {"freeze": freeze, "train": train}[parser.parse_args().command]()


if __name__ == "__main__":
    main()
