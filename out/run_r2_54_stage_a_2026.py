"""R2-54 single-lineage Stage-A 2026: one causal R2-44 w730_raw weekly generator for every 2026 origin.

Freeze: out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json (stage_a_provenance, data_plan.predictions, inputs.V3_stageA).
- Schedule: retrain every Thursday 00:00 UTC from 2026-01-01; origin T uses the checkpoint with the latest
  retrain_time <= T (each checkpoint serves [retrain, retrain + 7 d)), 15-minute grid only, T < 2026-10-08.
- Training: btcusdt_quant.paper.detector.train = R2-44 fit_fold unchanged (split_indices: labels end before
  retrain_time - 24 h; 730-day window; 60-day stop set; seed, optimizer, epochs as frozen).
- Outputs: detector.predict = expm1-restored bps, all 15 heads; logical_available_at = prediction_ts.
- Inputs (canonical only, data cutoff DATA_END): market = btcusdt_2020_2026h1.parquet + hold_a_2026q3/market_2026q3
  .parquet + live DB klines_1m for October; global LS = metrics archives (artifacts/metrics, hold_a_2026q3/metrics,
  metrics_2026q4; the same zips the futures_global_ls_5m archive rows were normalized from); premium = premium
  archives + live DB premium_1m for October; funding = funding archives + live DB funding/funding_events for
  October (unknown interval -> missing mask, never 8 h). The live DB is opened read-only, by `snapshot` only.
Never mixes HOLD_B / live / minute-refresh / backfill rows. Written once: an existing fold is reused only when its
hashes and code hash verify; anything else refuses (corrections = a new --out version + record).

The run reads only a write-once input snapshot (built once from the canonical sources and the read-only live DB;
SHA-256, rows, min/max and source per input in its manifest). The snapshot refuses when funding_events lacks an
event inside 2026-01-01..2026-10-08 unless --accept-missing-funding records the accepted missing mask.
The full run passes only if all 26 R2-44 HOLD_B folds are bit-exact (acceptance_hold_b.json).

Usage:
  python out/run_r2_54_stage_a_2026.py snapshot [--snapshot DIR] [--accept-missing-funding]
  python out/run_r2_54_stage_a_2026.py run [--retrains 2026-01-01,2026-01-08] [--out DIR] [--snapshot DIR]
  python out/run_r2_54_stage_a_2026.py causality --retrains 2026-01-08 --data-end 2026-01-16 --out DIR
  python out/run_r2_54_stage_a_2026.py compare-hold-b --out DIR
  python out/run_r2_54_stage_a_2026.py check-definitions
"""
from __future__ import annotations

import argparse, hashlib, json, sqlite3, sys, time
from pathlib import Path

import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.paper import detector  # noqa: E402

FREEZE = ROOT / "out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json"
OUT = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stage_a_2026"
SNAPSHOT = ROOT / "out/k45_rl_r2_48_20261007/r2_54/stage_a_2026_inputs"   # write-once input snapshot
DB = ROOT / "artifacts/live/live.sqlite"
Q3_MARKET = ROOT / "artifacts/hold_a_2026q3/market_2026q3.parquet"
Q3_METRICS = ROOT / "artifacts/hold_a_2026q3/metrics"
Q4_METRICS = ROOT / "artifacts/metrics_2026q4"
Q3_FUNDING = ROOT / "artifacts/hold_a_2026q3/funding"
Q3_END = pd.Timestamp("2026-10-01", tz="UTC")
FIRST_RETRAIN = pd.Timestamp("2026-01-01", tz="UTC")        # a Thursday; = R2-44 HOLD_B fold 0
CADENCE = pd.Timedelta(days=7)
DATA_END = pd.Timestamp("2026-10-08", tz="UTC")             # exclusive; final_test_nominal end
SOURCE = "r2_54_stage_a_2026"
CODE = [Path(__file__).resolve(), ROOT / "out/run_k45_vol_detector_r2_44_window.py",
        ROOT / "out/run_k45_vol_detector_r2_43.py", ROOT / "btcusdt_quant/paper/detector.py"]


def schedule(end: pd.Timestamp = DATA_END) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out, t = [], FIRST_RETRAIN
    while t < end:
        out.append((t, min(t + CADENCE, end))); t += CADENCE
    return out


def model_id(retrain: pd.Timestamp) -> str:
    return f"{SOURCE}_w730_raw_{retrain:%Y%m%d}"


def code_hash() -> str:
    digest = hashlib.sha256()
    for path in CODE:
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def frame_sha256(frame: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes()).hexdigest()


def _swap(name: str, path: Path, loader):
    r = detector.r44().r
    saved = getattr(r, name)
    try:
        setattr(r, name, path)
        return loader()
    finally:
        setattr(r, name, saved)


def _ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def canonical_inputs(db: Path = DB, data_end: pd.Timestamp = DATA_END) -> tuple[tuple[pd.DataFrame, ...], dict]:
    """(market, metrics, premium, funding) in the R2-43 formats, all rows < data_end, plus provenance."""
    r = detector.r44().r
    cols = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "number_of_trades",
            "taker_buy_base_volume"]
    q3 = pd.read_parquet(Q3_MARKET, columns=cols)
    q3["open_time"] = pd.to_datetime(q3.open_time, utc=True).astype("datetime64[ns, UTC]")
    with _ro(db) as connection:
        l_market, _, l_premium, l_funding = detector.live_inputs(connection, Q3_END)
    market = pd.concat([r.load_market(), q3, l_market.loc[l_market.open_time >= Q3_END, cols]], ignore_index=True)
    metrics = pd.concat([r.load_metrics(), _swap("METRICS", Q3_METRICS, r.load_metrics),
                         _swap("METRICS", Q4_METRICS, r.load_metrics)], ignore_index=True)
    metrics = metrics.drop_duplicates("create_time", keep="last")
    premium = pd.concat([r.load_premium(), detector._load_premium(detector.Q3_PREMIUM),
                         l_premium.loc[l_premium.open_time >= Q3_END]], ignore_index=True)
    premium = premium.drop_duplicates("open_time", keep="last")
    a_funding = pd.concat([r.load_funding(), _swap("FUNDING", Q3_FUNDING, r.load_funding)], ignore_index=True)
    a_funding["interval_missing"] = 0
    funding = pd.concat([a_funding, l_funding.loc[l_funding.publish_time >= Q3_END]], ignore_index=True)
    funding = funding.drop_duplicates("publish_time", keep="first")
    frames = cut((market, metrics, premium, funding), data_end)
    return frames, provenance(frames, data_end)


def cut(frames: tuple[pd.DataFrame, ...], data_end: pd.Timestamp) -> tuple[pd.DataFrame, ...]:
    """Rows known before data_end (exclusive), sorted; the market must be gap-free up to data_end - 1 min."""
    market, metrics, premium, funding = frames
    market = market.loc[market.open_time < data_end].sort_values("open_time").reset_index(drop=True)
    if market.open_time.duplicated().any() or not np.all(np.diff(market.open_time.array.asi8) == 60_000_000_000):
        raise ValueError("market has missing or duplicate minutes; interpolation is forbidden")
    if market.open_time.iloc[-1] != data_end - pd.Timedelta(minutes=1):
        raise ValueError(f"market ends {market.open_time.iloc[-1]}, before data_end {data_end}")
    metrics = metrics.loc[metrics.create_time + pd.Timedelta(minutes=5) <= data_end]
    premium = premium.loc[premium.open_time < data_end]
    funding = funding.loc[funding.publish_time < data_end]
    return (market, metrics.sort_values("create_time").reset_index(drop=True),
            premium.sort_values("open_time").reset_index(drop=True),
            funding.sort_values("publish_time").reset_index(drop=True))


FRAMES = ("market", "metrics", "premium", "funding")
SOURCES = {
    "market": "artifacts/btcusdt_2020_2026h1.parquet + artifacts/hold_a_2026q3/market_2026q3.parquet + "
              "live DB klines_1m (open_time >= 2026-10-01)",
    "metrics": "metrics zips artifacts/metrics + artifacts/hold_a_2026q3/metrics + artifacts/metrics_2026q4 "
               "(R2-43 load_metrics: create_time, count_long_short_ratio)",
    "premium": "premium zips artifacts/premium_index_2020_2026h1 + artifacts/hold_a_2026q3/premium_index + "
               "live DB premium_1m (open_time >= 2026-10-01)",
    "funding": "funding zips artifacts/funding_2020_2026h1 + artifacts/hold_a_2026q3/funding + live DB "
               "funding/funding_events via detector.live_inputs (publish_time >= 2026-10-01; unknown interval = missing)"}


def provenance(frames: tuple[pd.DataFrame, ...], data_end: pd.Timestamp) -> dict:
    return {"data_end_exclusive": str(data_end),
            "frames": {k: {"rows": len(v), "sha256": frame_sha256(v), "min": str(v.iloc[0, 0]),
                           "max": str(v.iloc[-1, 0])} for k, v in zip(FRAMES, frames)},
            "funding_interval_missing_events": int(frames[3].interval_missing.fillna(0).sum())}


def funding_coverage(db: Path, start: pd.Timestamp = FIRST_RETRAIN, end: pd.Timestamp = DATA_END) -> dict:
    """Every funding event in [start, end) must be in funding_events with a known interval: walking the stored
    events, the next one must arrive within interval_hours (+1 min for ms offsets) and the last must cover end."""
    with _ro(db) as c:
        events = pd.read_sql_query("SELECT funding_time, interval_hours FROM funding_events", c)
    return coverage_of(events, start, end)


def coverage_of(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    events = events.assign(funding_time=pd.to_datetime(events.funding_time, utc=True, format="mixed"))
    events = events.drop_duplicates("funding_time").sort_values("funding_time")
    before = events.loc[events.funding_time < start].tail(1)
    inside = events.loc[(events.funding_time >= start) & (events.funding_time < end)]
    walk = pd.concat([before, inside], ignore_index=True)
    gaps, unknown = [], int(inside.interval_hours.isna().sum())
    if walk.empty:
        gaps.append({"expected": str(start), "next_stored": None})
    for k, row in walk.iterrows():
        if pd.isna(row.interval_hours):
            continue
        due = row.funding_time + pd.Timedelta(hours=float(row.interval_hours))
        nxt = walk.funding_time.iloc[k + 1] if k + 1 < len(walk) else None
        if due < end and (nxt is None or nxt > due + pd.Timedelta(minutes=1)):
            gaps.append({"expected": str(due), "next_stored": None if nxt is None else str(nxt)})
    return {"window": [str(start), str(end)], "stored_events": int(len(inside)), "unknown_interval_events": unknown,
            "gaps": gaps, "complete": not gaps and not unknown}


def build_snapshot(snapshot: Path, db: Path, allow_funding_gaps: bool = False) -> dict:
    """Immutable input snapshot: the four input frames as parquet (read back and hash-checked) + manifest with
    file SHA-256, frame hash, rows, min/max, source, archive tree hashes and the funding coverage guard."""
    r = detector.r44().r
    if snapshot.exists():
        raise RuntimeError(f"{snapshot} exists; snapshots are write-once, use a new path")
    coverage = funding_coverage(db)
    if not coverage["complete"] and not allow_funding_gaps:
        raise RuntimeError("funding_events lacks events inside the run window: " + json.dumps(coverage)[:600] +
                           " ... rerun with --accept-missing-funding (= --allow-funding-gaps) to record and accept the missing mask")
    frames, prov = canonical_inputs(db)
    records = {}
    for name, frame in zip(FRAMES, frames):
        path = snapshot / f"{name}.parquet"
        r.write_parquet(path, frame)
        if frame_sha256(_read(path)) != prov["frames"][name]["sha256"]:
            raise RuntimeError(f"{name} parquet round trip is not exact")
        records[name] = {**prov["frames"][name], "file": r.file_record(path), "source": SOURCES[name]}
    with _ro(db) as c:
        db_state = {t: c.execute(f"SELECT COUNT(*), MIN({k}), MAX({k}) FROM {t}").fetchone() for t, k in
                    (("klines_1m", "open_time"), ("premium_1m", "open_time"), ("funding", "time"),
                     ("funding_events", "funding_time"))}
    manifest = {"kind": "R2-54 Stage-A 2026 input snapshot", "created_at": r.utc_now(),
                "data_end_exclusive": str(DATA_END), "frames": records, "archive_records": input_records(),
                "live_db": {"path": str(db), "mode": "read-only", "tables_count_min_max": db_state},
                "funding_coverage": coverage,
                "funding_gaps_accepted": bool(allow_funding_gaps and not coverage["complete"]),
                "funding_interval_missing_events": prov["funding_interval_missing_events"],
                "funding_missing_event_times": [str(t) for t in   # masked (rate 0, funding_missing=1) in the features
                                                frames[3].publish_time[frames[3].interval_missing.fillna(0).eq(1)]]}
    r.write_json(snapshot / "manifest.json", manifest)
    return manifest


def _read(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    for c in frame:
        if isinstance(frame[c].dtype, pd.DatetimeTZDtype):
            frame[c] = frame[c].astype("datetime64[ns, UTC]")
    return frame


def load_snapshot(snapshot: Path, data_end: pd.Timestamp = DATA_END) -> tuple[tuple[pd.DataFrame, ...], dict]:
    """Verified snapshot frames cut at data_end, and the provenance every fold record carries."""
    r = detector.r44().r
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data_end > pd.Timestamp(manifest["data_end_exclusive"]):
        raise ValueError("data_end after the snapshot cutoff")
    if not manifest["funding_coverage"]["complete"] and not manifest["funding_gaps_accepted"]:
        raise RuntimeError("snapshot funding coverage incomplete and not accepted")
    frames = []
    for name in FRAMES:
        record = manifest["frames"][name]
        path = snapshot / f"{name}.parquet"
        if r.sha256_file(path) != record["file"]["sha256"]:
            raise RuntimeError(f"snapshot {name} file hash mismatch")
        frame = _read(path)
        if frame_sha256(frame) != record["sha256"]:
            raise RuntimeError(f"snapshot {name} frame hash mismatch")
        frames.append(frame)
    frames = cut(tuple(frames), data_end)
    return frames, {"snapshot_manifest_sha256": r.sha256_file(manifest_path),
                    "funding_gaps_accepted": manifest["funding_gaps_accepted"], **provenance(frames, data_end)}


def input_records() -> list[dict]:
    r = detector.r44().r
    return [*r.input_records(), r.file_record(Q3_MARKET), r.tree_record(Q3_METRICS), r.tree_record(Q4_METRICS),
            r.tree_record(detector.Q3_PREMIUM), r.tree_record(Q3_FUNDING)]


def train_record(data, retrain: pd.Timestamp) -> dict:
    """Cutoffs of the rows fit_fold trains / early-stops on (same split_indices + finite filter)."""
    r44 = detector.r44()
    train, stop = r44.split_indices(data.origins, retrain, detector.candidate())
    finite = np.isfinite(data.raw_target).all(1)
    train, stop = train[finite[train]], stop[finite[stop]]
    label = pd.Timedelta(hours=24)
    record = {"train_rows": int(len(train)), "stop_rows": int(len(stop)),
              "train_first_origin": str(data.origins[train[0]]), "train_last_origin": str(data.origins[train[-1]]),
              "stop_last_origin": str(data.origins[stop[-1]]),
              "train_cutoff": str(data.origins[stop[-1]] + label),     # latest label end any fitted row used
              "label_cutoff_rule": str(retrain - label)}
    if not data.origins[stop[-1]] + label < retrain - label:
        raise RuntimeError("training label crosses retrain_time - 24 h")
    return record


def predictions_frame(retrain: pd.Timestamp, origins: pd.DatetimeIndex, values: np.ndarray, written: str):
    frame = pd.DataFrame({"prediction_ts": origins, "retrain_time": retrain, "model_id": model_id(retrain),
                          "logical_available_at": origins, "written_at": pd.Timestamp(written), "source": SOURCE})
    for j, name in enumerate(detector.target_names()):
        frame[f"prediction_{name}"] = values[:, j].astype(float)
    return frame


def run_fold(data, retrain: pd.Timestamp, end: pd.Timestamp, device):
    import torch
    started = time.perf_counter()
    record = train_record(data, retrain)
    checkpoint, _ = detector.train(data, retrain, device)        # = R2-44 fit_fold, unchanged
    origins = pd.DatetimeIndex(data.origins)
    origins = origins[(origins >= retrain) & (origins < end)]
    with torch.no_grad():
        values = detector.predict(data, checkpoint, origins, device)
    if not np.isfinite(values).all() or (values < 0).any():
        raise RuntimeError("non-finite or negative restored bps")
    frame = predictions_frame(retrain, origins, values, pd.Timestamp.now(tz="UTC").isoformat())
    if not (frame.prediction_ts >= retrain).all() or pd.Timestamp(record["train_cutoff"]) >= frame.prediction_ts.min():
        raise RuntimeError("checkpoint trained past its prediction timestamp")
    return checkpoint, frame, {**record, "elapsed_seconds": time.perf_counter() - started}


def fold_paths(out: Path, retrain: pd.Timestamp) -> tuple[Path, Path, Path]:
    stem = f"w730_raw_{retrain:%Y%m%d}"
    return out / "checkpoints" / f"{stem}.pt", out / "predictions" / f"{stem}.parquet", out / "folds" / f"{stem}.json"


def completed(out: Path, retrain: pd.Timestamp, digest: str, inputs: dict) -> bool:
    """True for a fold whose code hash, input provenance (snapshot manifest + cut-frame hashes) and output hashes
    all verify; a partial or differing fold is never reused or overwritten (write-once: use a new --out)."""
    r = detector.r44().r
    paths = fold_paths(out, retrain)
    if not any(p.exists() for p in paths):
        return False
    if not all(p.exists() for p in paths):
        raise RuntimeError(f"partial fold {retrain.date()} in {out}; write-once artifact, use a new --out")
    record = json.loads(paths[2].read_text(encoding="utf-8"))
    if (record.get("code_sha256") != digest or record.get("inputs") != inputs
            or record.get("checkpoint_sha256") != r.sha256_file(paths[0])
            or record.get("predictions_sha256") != r.sha256_file(paths[1])):
        raise RuntimeError(f"fold {retrain.date()} in {out} does not verify (code, inputs or outputs); "
                           "write-once artifact, use a new --out")
    return True


def run(out: Path, retrains: list[pd.Timestamp] | None, snapshot: Path, device_name: str,
        data_end: pd.Timestamp = DATA_END) -> dict:
    """Train/predict the scheduled folds from the verified input snapshot only (never the live DB)."""
    import torch
    r = detector.r44().r
    device = torch.device(device_name)
    torch.set_num_threads(4)
    digest = code_hash()
    folds = [f for f in schedule(data_end) if retrains is None or f[0] in retrains]
    if retrains is not None and len(folds) != len(retrains):
        raise ValueError("retrain not on the Thursday schedule")
    started = time.perf_counter()
    inputs, prov = load_snapshot(snapshot, data_end)
    data = detector.build_data(*inputs)
    load_seconds = time.perf_counter() - started
    records = []
    for retrain, end in folds:
        if completed(out, retrain, digest, prov):
            records.append(json.loads(fold_paths(out, retrain)[2].read_text(encoding="utf-8"))); continue
        checkpoint, frame, record = run_fold(data, retrain, end, device)
        ckpt, preds, meta = fold_paths(out, retrain)
        r.atomic_torch_save(ckpt, checkpoint)
        r.write_parquet(preds, frame)
        record = {"model_id": model_id(retrain), "retrain_time": str(retrain), "prediction_start": str(retrain),
                  "prediction_end_exclusive": str(end), "rows": len(frame), **record,
                  "best_stop_mae": checkpoint["best_stop_mae"], "epochs": len(checkpoint["history"]),
                  "checkpoint_sha256": r.sha256_file(ckpt), "predictions_sha256": r.sha256_file(preds),
                  "code_sha256": digest, "inputs": prov, "written_at": r.utc_now()}
        r.write_json(meta, record)
        records.append(record)
        print(json.dumps({"fold": str(retrain.date()), "rows": len(frame),
                          "seconds": round(record["elapsed_seconds"], 1)}), flush=True)
    summary = {"load_seconds": load_seconds, "folds": len(records)}
    if retrains is None and data_end == DATA_END:      # full schedule: acceptance, combined artifact, manifest
        combined = pd.concat([pd.read_parquet(fold_paths(out, t)[1]) for t, _ in folds], ignore_index=True)
        if combined.prediction_ts.duplicated().any():
            raise RuntimeError("duplicate prediction_ts")
        expected = pd.date_range(FIRST_RETRAIN, DATA_END, freq="15min", inclusive="left").as_unit("ns")
        if not pd.DatetimeIndex(combined.prediction_ts).as_unit("ns").equals(expected):
            raise RuntimeError("combined grid is not the complete 2026 15-minute grid")
        acceptance = hold_b_acceptance(compare_hold_b(out, data, device))
        r.write_json(out / "acceptance_hold_b.json", acceptance)
        manifest = {
            "experiment": "R2-54 Stage-A 2026 single lineage", "freeze": r.file_record(FREEZE),
            "generator": "R2-44 w730_raw (detector.train = fit_fold unchanged)", "source": SOURCE,
            "schedule": "Thursday 00:00 UTC weekly from 2026-01-01; T uses latest retrain_time <= T",
            "availability": "research: prediction_ts<=T and logical_available_at<=T; written_at is physical",
            "data_end_exclusive": str(DATA_END), "code_sha256": digest, "code": [r.file_record(p) for p in CODE],
            "inputs": prov, "snapshot_manifest": r.file_record(snapshot / "manifest.json"),
            "folds": records, "acceptance_hold_b": acceptance, "written_at": r.utc_now()}
        if not acceptance["passed"]:
            r.write_json(out / "manifest.json", {**manifest, "status": "FAILED_HOLD_B_ACCEPTANCE"})
            raise RuntimeError("HOLD_B overlap is not bit-exact; no combined artifact written")
        path = out / "stage_a_2026.parquet"
        r.write_parquet(path, combined)
        r.write_json(out / "manifest.json", {**manifest, "status": "COMPLETE",
                                             "artifact": {**r.file_record(path), "rows": len(combined)}})
        summary["artifact"] = str(path)
    return summary


def check_definitions(db: Path = DB) -> dict:
    """R2-44 LS/funding inputs vs the canonical R2-54 tables (report only; R2-44 features are not changed)."""
    r = detector.r44().r
    with _ro(db) as c:
        table = pd.read_sql_query("SELECT create_time, long_short_ratio FROM futures_global_ls_5m "
                                  "WHERE source='archive'", c)
        events = pd.read_sql_query("SELECT funding_time, funding_rate, interval_hours, logical_available_at "
                                   "FROM funding_events WHERE source='archive'", c)
    table["create_time"] = pd.to_datetime(table.create_time, utc=True)
    archive = pd.concat([r.load_metrics(), _swap("METRICS", Q3_METRICS, r.load_metrics),
                         _swap("METRICS", Q4_METRICS, r.load_metrics)], ignore_index=True)
    archive = archive.loc[archive.create_time >= table.create_time.min()]
    joined = archive.merge(table, on="create_time", how="outer", indicator=True)
    both = joined._merge.eq("both")
    events["funding_time"] = pd.to_datetime(events.funding_time, utc=True, format="mixed")
    events["logical_available_at"] = pd.to_datetime(events.logical_available_at, utc=True, format="mixed")
    fund = pd.concat([r.load_funding(), _swap("FUNDING", Q3_FUNDING, r.load_funding)], ignore_index=True)
    fund = fund.loc[fund.publish_time >= events.funding_time.min()]
    fj = fund.merge(events, left_on="publish_time", right_on="funding_time", how="outer", indicator=True)
    fb = fj._merge.eq("both")
    return {
        "global_ls": {"archive_rows": int(len(archive)), "table_rows": int(len(table)), "matched": int(both.sum()),
                      "archive_only": int(joined._merge.eq("left_only").sum()),
                      "table_only": int(joined._merge.eq("right_only").sum()),
                      "max_abs_diff": float((joined.global_ls - joined.long_short_ratio)[both].abs().max()),
                      "r2_44_rule": "create_time+5m < T strictly, TTL 15 min (asof_strict side=left)",
                      "canonical_rule": "logical_available_at=create_time+5m <= T"},
        "funding": {"archive_rows": int(len(fund)), "table_rows": int(len(events)), "matched": int(fb.sum()),
                    "archive_only": int(fj._merge.eq("left_only").sum()),
                    "table_only": int(fj._merge.eq("right_only").sum()),
                    "max_abs_rate_diff": float((fj.rate - fj.funding_rate)[fb].abs().max()),
                    "interval_mismatch": int((fj.interval_hours_x != fj.interval_hours_y)[fb].sum()),
                    "availability_mismatch": int((fj.logical_available_at != fj.publish_time)[fb].sum()),
                    "r2_44_rule": "publish_time(calc_time) < T strictly; expires after interval_hours",
                    "canonical_rule": "logical_available_at=funding_time <= T"},
        "unused_by_r2_44": "top LS, OI, OI value, taker LSR (R2-44 features use global LS, premium, funding only)"}




HOLD_B = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw/HOLD_B"
HOLD_B_FOLDS = 26


def compare_hold_b(out: Path, data, device) -> dict:
    """Overlap check vs frozen R2-44 HOLD_B: (a) frozen checkpoint through this generator's inputs; (b) this
    generator's retrained checkpoint. Max abs diff in restored bps on the frozen fold's rows."""
    import torch
    r = detector.r44().r
    names = [f"prediction_{t}" for t in detector.target_names()]
    result = {}
    for fold, (retrain, _) in enumerate(r.fold_schedule("HOLD_B", 7)):
        ours = fold_paths(out, retrain)[1]
        if not ours.exists():
            continue
        frozen = pd.read_parquet(HOLD_B / f"fold_{fold:04d}_predictions.parquet")
        origins = pd.DatetimeIndex(frozen.timestamp).as_unit("ns")
        checkpoint = torch.load(HOLD_B / f"fold_{fold:04d}.pt", weights_only=False, map_location="cpu")
        same_ckpt = detector.predict(data, checkpoint, origins, device)
        mine = _read(ours).set_index("prediction_ts")
        regen = mine.reindex(origins)[names].to_numpy(float)
        expected = frozen[names].to_numpy(float)
        result[str(retrain.date())] = {
            "rows": len(frozen), "regenerated_rows": len(mine),
            "frozen_checkpoint_max_abs_bps": float(np.abs(same_ckpt - expected).max()),
            "regenerated_max_abs_bps": float(np.nanmax(np.abs(regen - expected))),
            "regenerated_missing_rows": int(np.isnan(regen).any(1).sum())}
    return result


def hold_b_acceptance(result: dict) -> dict:
    """Full-run gate: all 26 H1 folds present and bit-exact for both the frozen and the regenerated checkpoint."""
    exact = all(v["frozen_checkpoint_max_abs_bps"] == 0 and v["regenerated_max_abs_bps"] == 0 and
                not v["regenerated_missing_rows"] for v in result.values())
    return {"folds": result, "required_folds": HOLD_B_FOLDS, "passed": len(result) == HOLD_B_FOLDS and exact}


def causality(out: Path, snapshot: Path, retrain: pd.Timestamp, data_end: pd.Timestamp, device_name: str) -> dict:
    """Retrain one fold with every input cut at data_end into out/causality_<retrain>_data_end_<date>/ and compare
    with the same fold in out (full data). Persists causality_<...>.json in out."""
    r = detector.r44().r
    name = f"causality_{retrain:%Y%m%d}_data_end_{data_end:%Y%m%d}"
    run(out / name, [retrain], snapshot, device_name, data_end)
    full = _read(fold_paths(out, retrain)[1])
    cut_run = _read(fold_paths(out / name, retrain)[1])
    full = full.loc[full.prediction_ts < data_end].reset_index(drop=True)
    names = [c for c in full if c.startswith("prediction_") and c != "prediction_ts"]
    same_ts = len(full) == len(cut_run) and bool((full.prediction_ts.values == cut_run.prediction_ts.values).all())
    diff = float(np.abs(full[names].to_numpy() - cut_run[names].to_numpy()).max()) if same_ts else None
    result = {"retrain_time": str(retrain), "data_end_exclusive": str(data_end), "rows": len(cut_run),
              "same_prediction_ts": same_ts, "max_abs_bps": diff, "passed": same_ts and diff == 0,
              "full_fold": json.loads(fold_paths(out, retrain)[2].read_text(encoding="utf-8"))["checkpoint_sha256"],
              "cut_fold": json.loads(fold_paths(out / name, retrain)[2].read_text(encoding="utf-8"))
              ["checkpoint_sha256"], "written_at": r.utc_now()}
    r.write_json(out / f"{name}.json", result)
    return result


def main() -> None:
    import torch
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("snapshot", "run", "check-definitions", "compare-hold-b", "causality"))
    parser.add_argument("--retrains", help="comma-separated Thursday dates (smoke); default: full schedule")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--db", type=Path, default=DB, help="live DB, read-only; used by snapshot/check-definitions")
    parser.add_argument("--allow-funding-gaps", "--accept-missing-funding", action="store_true",
                        help="snapshot: record and accept funding_events gaps (missing mask) instead of refusing")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--data-end", default=str(DATA_END), help="exclusive input cutoff (causality checks only)")
    args = parser.parse_args()
    data_end = pd.to_datetime(args.data_end, utc=True)
    if args.command == "snapshot":
        result = build_snapshot(args.snapshot, args.db, args.allow_funding_gaps)
    elif args.command == "check-definitions":
        result = check_definitions(args.db)
    elif args.command == "compare-hold-b":
        inputs, _ = load_snapshot(args.snapshot)
        result = compare_hold_b(args.out, detector.build_data(*inputs, with_targets=False), torch.device(args.device))
    elif args.command == "causality":
        result = causality(args.out, args.snapshot, pd.Timestamp(args.retrains, tz="UTC"), data_end, args.device)
    else:
        retrains = None if args.retrains is None else [pd.Timestamp(x, tz="UTC") for x in args.retrains.split(",")]
        result = run(args.out, retrains, args.snapshot, args.device, data_end)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
