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
  October (unknown interval -> missing mask, never 8 h). The live DB is opened read-only.
Never mixes HOLD_B / live / minute-refresh / backfill rows. Written once: an existing fold is reused only when its
hashes and code hash verify; anything else refuses (corrections = a new --out version + record).

Usage:
  python out/run_r2_54_stage_a_2026.py run [--retrains 2026-01-01,2026-01-08] [--out DIR]
  python out/run_r2_54_stage_a_2026.py check-definitions
  python out/run_r2_54_stage_a_2026.py compare-hold-b --out DIR
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
    market = market.loc[market.open_time < data_end].reset_index(drop=True)
    if market.open_time.duplicated().any() or not np.all(np.diff(market.open_time.array.asi8) == 60_000_000_000):
        raise ValueError("market has missing or duplicate minutes; interpolation is forbidden")
    if market.open_time.iloc[-1] != data_end - pd.Timedelta(minutes=1):
        raise ValueError(f"market ends {market.open_time.iloc[-1]}, before data_end {data_end}")
    metrics = pd.concat([r.load_metrics(), _swap("METRICS", Q3_METRICS, r.load_metrics),
                         _swap("METRICS", Q4_METRICS, r.load_metrics)], ignore_index=True)
    metrics = metrics.loc[metrics.create_time + pd.Timedelta(minutes=5) <= data_end]
    metrics = metrics.drop_duplicates("create_time", keep="last").sort_values("create_time").reset_index(drop=True)
    premium = pd.concat([r.load_premium(), detector._load_premium(detector.Q3_PREMIUM),
                         l_premium.loc[l_premium.open_time >= Q3_END]], ignore_index=True)
    premium = premium.loc[premium.open_time < data_end]
    premium = premium.drop_duplicates("open_time", keep="last").sort_values("open_time").reset_index(drop=True)
    a_funding = pd.concat([r.load_funding(), _swap("FUNDING", Q3_FUNDING, r.load_funding)], ignore_index=True)
    a_funding["interval_missing"] = 0
    funding = pd.concat([a_funding, l_funding.loc[l_funding.publish_time >= Q3_END]], ignore_index=True)
    funding = funding.loc[funding.publish_time < data_end]
    funding = funding.drop_duplicates("publish_time", keep="first").sort_values("publish_time").reset_index(drop=True)
    frames = {"market": market, "metrics": metrics, "premium": premium, "funding": funding}
    provenance = {"data_end_exclusive": str(data_end), "db": str(db), "db_mode": "read-only",
                  "frames": {k: {"rows": len(v), "sha256": frame_sha256(v),
                                 "min": str(v.iloc[0, 0]), "max": str(v.iloc[-1, 0])} for k, v in frames.items()},
                  "october_funding_interval_missing": int(funding.interval_missing.fillna(0).sum())}
    return (market, metrics, premium, funding), provenance


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


def completed(out: Path, retrain: pd.Timestamp, digest: str) -> bool:
    r = detector.r44().r
    paths = fold_paths(out, retrain)
    if not any(p.exists() for p in paths):
        return False
    if not all(p.exists() for p in paths):
        raise RuntimeError(f"partial fold {retrain.date()} in {out}; write-once artifact, use a new --out")
    record = json.loads(paths[2].read_text(encoding="utf-8"))
    if (record["code_sha256"] != digest or record["checkpoint_sha256"] != r.sha256_file(paths[0])
            or record["predictions_sha256"] != r.sha256_file(paths[1])):
        raise RuntimeError(f"fold {retrain.date()} in {out} does not verify; write-once artifact, use a new --out")
    return True


def run(out: Path, retrains: list[pd.Timestamp] | None, db: Path, device_name: str,
        data_end: pd.Timestamp = DATA_END) -> dict:
    import torch
    r = detector.r44().r
    device = torch.device(device_name)
    torch.set_num_threads(4)
    digest = code_hash()
    folds = [f for f in schedule(data_end) if retrains is None or f[0] in retrains]
    if retrains is not None and len(folds) != len(retrains):
        raise ValueError("retrain not on the Thursday schedule")
    started = time.perf_counter()
    inputs, provenance = canonical_inputs(db, data_end)
    data = detector.build_data(*inputs)
    load_seconds = time.perf_counter() - started
    records = []
    for retrain, end in folds:
        if completed(out, retrain, digest):
            records.append(json.loads(fold_paths(out, retrain)[2].read_text(encoding="utf-8"))); continue
        checkpoint, frame, record = run_fold(data, retrain, end, device)
        ckpt, preds, meta = fold_paths(out, retrain)
        r.atomic_torch_save(ckpt, checkpoint)
        r.write_parquet(preds, frame)
        record = {"model_id": model_id(retrain), "retrain_time": str(retrain), "prediction_start": str(retrain),
                  "prediction_end_exclusive": str(end), "rows": len(frame), **record,
                  "best_stop_mae": checkpoint["best_stop_mae"], "epochs": len(checkpoint["history"]),
                  "checkpoint_sha256": r.sha256_file(ckpt), "predictions_sha256": r.sha256_file(preds),
                  "code_sha256": digest, "inputs": provenance, "written_at": r.utc_now()}
        r.write_json(meta, record)
        records.append(record)
        print(json.dumps({"fold": str(retrain.date()), "rows": len(frame),
                          "seconds": round(record["elapsed_seconds"], 1)}), flush=True)
    summary = {"load_seconds": load_seconds, "folds": len(records)}
    if retrains is None and data_end == DATA_END:      # full schedule: one combined artifact + manifest
        combined = pd.concat([pd.read_parquet(fold_paths(out, t)[1]) for t, _ in folds], ignore_index=True)
        if combined.prediction_ts.duplicated().any():
            raise RuntimeError("duplicate prediction_ts")
        expected = pd.date_range(FIRST_RETRAIN, DATA_END, freq="15min", inclusive="left").as_unit("ns")
        if not pd.DatetimeIndex(combined.prediction_ts).as_unit("ns").equals(expected):
            raise RuntimeError("combined grid is not the complete 2026 15-minute grid")
        path = out / "stage_a_2026.parquet"
        r.write_parquet(path, combined)
        r.write_json(out / "manifest.json", {
            "experiment": "R2-54 Stage-A 2026 single lineage", "freeze": r.file_record(FREEZE),
            "generator": "R2-44 w730_raw (detector.train = fit_fold unchanged)", "source": SOURCE,
            "schedule": "Thursday 00:00 UTC weekly from 2026-01-01; T uses latest retrain_time <= T",
            "availability": "research: prediction_ts<=T and logical_available_at<=T; written_at is physical",
            "data_end_exclusive": str(DATA_END), "code_sha256": digest, "code": [r.file_record(p) for p in CODE],
            "inputs": provenance, "input_records": input_records(),
            "folds": records, "artifact": {**r.file_record(path), "rows": len(combined)},
            "written_at": r.utc_now()})
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


def compare_hold_b(out: Path, db: Path, device_name: str) -> dict:
    """Overlap check vs frozen R2-44 HOLD_B: (a) frozen checkpoint through this generator's inputs; (b) this
    generator's retrained checkpoint. Max abs diff in restored bps on the frozen fold's rows."""
    import torch
    r = detector.r44().r
    device = torch.device(device_name)
    inputs, _ = canonical_inputs(db)
    data = detector.build_data(*inputs, with_targets=False)
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
        mine = pd.read_parquet(ours).set_index("prediction_ts")
        regen = mine.reindex(origins)[names].to_numpy(float)
        expected = frozen[names].to_numpy(float)
        result[str(retrain.date())] = {
            "rows": len(frozen), "regenerated_rows": len(mine),
            "frozen_checkpoint_max_abs_bps": float(np.abs(same_ckpt - expected).max()),
            "frozen_checkpoint_max_rel": float((np.abs(same_ckpt - expected) / expected).max()),
            "regenerated_max_abs_bps": float(np.nanmax(np.abs(regen - expected))),
            "regenerated_max_rel": float(np.nanmax(np.abs(regen - expected) / expected)),
            "regenerated_missing_rows": int(np.isnan(regen).any(1).sum())}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("run", "check-definitions", "compare-hold-b"))
    parser.add_argument("--retrains", help="comma-separated Thursday dates (smoke); default: full schedule")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--data-end", default=str(DATA_END), help="exclusive input cutoff (causality checks only)")
    args = parser.parse_args()
    if args.command == "check-definitions":
        print(json.dumps(check_definitions(args.db), indent=2)); return
    if args.command == "compare-hold-b":
        print(json.dumps(compare_hold_b(args.out, args.db, args.device), indent=2)); return
    retrains = None if args.retrains is None else [pd.Timestamp(x, tz="UTC") for x in args.retrains.split(",")]
    print(json.dumps(run(args.out, retrains, args.db, args.device, pd.to_datetime(args.data_end, utc=True)), indent=2))


if __name__ == "__main__":
    main()
