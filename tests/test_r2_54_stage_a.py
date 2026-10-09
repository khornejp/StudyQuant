"""R2-54 Task 2: single-lineage Stage-A 2026 generator (offline, CPU; no training)."""
import importlib.util, json, sys
from pathlib import Path

import numpy as np, pandas as pd, pytest, torch

from btcusdt_quant.paper import detector

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r2_54_stage_a", ROOT / "out/run_r2_54_stage_a_2026.py")
gen = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = gen; SPEC.loader.exec_module(gen)
FROZEN = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw/HOLD_B/fold_0000.pt"


def test_schedule_is_one_weekly_thursday_lineage_covering_2026():
    folds = gen.schedule()
    assert len(folds) == 40 and folds[0][0] == pd.Timestamp("2026-01-01", tz="UTC")
    assert all(t.dayofweek == 3 and t == t.floor("D") for t, _ in folds)              # Thursday 00:00 UTC
    assert all(a[1] == b[0] for a, b in zip(folds, folds[1:])) and folds[-1][1] == gen.DATA_END
    assert folds[-1][0] == pd.Timestamp("2026-10-01", tz="UTC")


def test_prediction_rows_split_availability_and_never_reuse_other_lineage_ids():
    origins = pd.date_range("2026-01-01", periods=3, freq="15min", tz="UTC")
    retrain = pd.Timestamp("2026-01-01", tz="UTC")
    frame = gen.predictions_frame(retrain, origins, np.ones((3, 15)), "2026-10-09T00:00:00+00:00")
    assert list(frame.columns[:6]) == ["prediction_ts", "retrain_time", "model_id", "logical_available_at",
                                       "written_at", "source"]
    assert (frame.logical_available_at == frame.prediction_ts).all()
    assert (frame.written_at == pd.Timestamp("2026-10-09", tz="UTC")).all()
    assert frame.model_id.iloc[0] == "r2_54_stage_a_2026_w730_raw_20260101" != f"w730_raw_{retrain:%Y%m%d}"
    assert [c[11:] for c in frame.columns[6:]] == list(detector.target_names())


def test_train_record_cutoff_is_before_retrain_and_independent_of_later_rows():
    origins = pd.date_range("2023-12-01", "2026-03-01", freq="15min", tz="UTC")
    target = np.ones((len(origins), 15), np.float32)
    data = type("D", (), {"origins": origins, "raw_target": target})()
    retrain = pd.Timestamp("2026-01-08", tz="UTC")
    record = gen.train_record(data, retrain)
    assert pd.Timestamp(record["train_cutoff"]) < retrain - pd.Timedelta(hours=24)
    target[origins >= retrain - pd.Timedelta(hours=48)] = np.nan     # unmatured labels change nothing
    assert gen.train_record(data, retrain) == record


def _synthetic(days=22, seed=0):
    t = pd.date_range("2026-01-01", periods=days * 1440, freq="1min", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 1e5 * np.exp(np.cumsum(rng.normal(0, 5e-4, len(t))))
    open_ = np.r_[close[0], close[:-1]]
    market = pd.DataFrame({"open_time": t, "open": open_, "high": np.maximum(open_, close) * 1.0003,
                           "low": np.minimum(open_, close) * 0.9997, "close": close, "volume": 10.0,
                           "quote_volume": 1e6, "number_of_trades": 100, "taker_buy_base_volume": 5.0})
    five = t[::5]
    metrics = pd.DataFrame({"create_time": five, "global_ls": 1.5 + rng.normal(0, .01, len(five))})
    premium = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(milliseconds=59_999),
                            "premium": rng.normal(0, 1e-4, len(t))})
    eight = pd.date_range(t[0], t[-1], freq="8h")
    funding = pd.DataFrame({"publish_time": eight, "rate": 1e-4, "interval_hours": 8.0})
    return market, metrics, premium, funding


def test_changing_inputs_after_cutoff_does_not_change_earlier_predictions():
    checkpoint = torch.load(FROZEN, weights_only=False, map_location="cpu")
    frames = _synthetic()
    cutoff = pd.Timestamp("2026-01-20T12:00", tz="UTC")
    changed = [f.copy() for f in frames]
    m = changed[0]; late = m.open_time >= cutoff
    for c in ("open", "high", "low", "close"):
        m.loc[late, c] *= 1.3
    m.loc[late, "volume"] *= 7
    changed[1].loc[changed[1].create_time + pd.Timedelta(minutes=5) > cutoff, "global_ls"] = 9.0
    changed[2].loc[changed[2].open_time >= cutoff, "premium"] = 0.01
    changed[3].loc[changed[3].publish_time >= cutoff, "rate"] = 0.05
    base = detector.build_data(*frames, with_targets=False)
    other = detector.build_data(*changed, with_targets=False)
    origins = pd.date_range(cutoff - pd.Timedelta(days=1), cutoff, freq="15min")
    a = detector.predict(base, checkpoint, origins, torch.device("cpu"))
    b = detector.predict(other, checkpoint, origins, torch.device("cpu"))
    assert np.array_equal(a, b) and (a > 0).all()
    after = pd.date_range(cutoff + pd.Timedelta(minutes=15), periods=8, freq="15min")
    assert not np.allclose(detector.predict(base, checkpoint, after, torch.device("cpu")),
                           detector.predict(other, checkpoint, after, torch.device("cpu")))


def test_written_folds_are_immutable(tmp_path):
    retrain = pd.Timestamp("2026-01-01", tz="UTC")
    ckpt, preds, meta = gen.fold_paths(tmp_path, retrain)
    inputs = {"snapshot_manifest_sha256": "s"}
    assert not gen.completed(tmp_path, retrain, "c", inputs)
    for p in (ckpt, preds):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="partial"):
        gen.completed(tmp_path, retrain, "c", inputs)
    sha = detector.r44().r.sha256_file(ckpt)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps({"code_sha256": "c", "checkpoint_sha256": sha, "predictions_sha256": sha,
                                "inputs": inputs}))
    assert gen.completed(tmp_path, retrain, "c", inputs)
    with pytest.raises(RuntimeError, match="does not verify"):
        gen.completed(tmp_path, retrain, "other code", inputs)
    with pytest.raises(RuntimeError, match="does not verify"):          # other input provenance: never reused
        gen.completed(tmp_path, retrain, "c", {"snapshot_manifest_sha256": "other"})


def test_funding_coverage_guard_finds_missing_and_unknown_interval_events():
    t = pd.date_range("2026-09-30", "2026-09-30T16:00", freq="8h", tz="UTC")
    ok = pd.DataFrame({"funding_time": [x.isoformat() for x in t], "interval_hours": 8.0})
    end = pd.Timestamp("2026-10-01", tz="UTC")
    assert gen.coverage_of(ok, pd.Timestamp("2026-09-30T04:00", tz="UTC"), end)["complete"]
    late = gen.coverage_of(ok, pd.Timestamp("2026-09-30T04:00", tz="UTC"), end + pd.Timedelta(hours=8))
    assert not late["complete"] and late["gaps"] == [{"expected": "2026-10-01 00:00:00+00:00", "next_stored": None}]
    unknown = ok.assign(interval_hours=[8.0, np.nan, 8.0])
    assert gen.coverage_of(unknown, pd.Timestamp("2026-09-30T04:00", tz="UTC"), end)["unknown_interval_events"] == 1
    hole = ok.drop(index=1)
    assert gen.coverage_of(hole, pd.Timestamp("2026-09-30T04:00", tz="UTC"), end)["gaps"][0]["expected"]         == "2026-09-30 08:00:00+00:00"


def _write_snapshot(root, frames, end):
    r = detector.r44().r
    records = {}
    for name, frame in zip(gen.FRAMES, frames):
        r.write_parquet(root / f"{name}.parquet", frame)
        records[name] = {"sha256": gen.frame_sha256(frame), "file": r.file_record(root / f"{name}.parquet")}
    r.write_json(root / "manifest.json", {"data_end_exclusive": str(end), "frames": records,
                                         "funding_coverage": {"complete": True}, "funding_gaps_accepted": False})


def test_run_inputs_come_only_from_a_verified_snapshot(tmp_path):
    market, metrics, premium, funding = _synthetic(days=3)
    frames = (market, metrics, premium, funding.assign(interval_missing=0))
    end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    root = tmp_path / "snap"
    _write_snapshot(root, frames, end)
    loaded, prov = gen.load_snapshot(root, end)
    assert gen.frame_sha256(loaded[0]) == gen.frame_sha256(market)
    cut, prov_cut = gen.load_snapshot(root, end - pd.Timedelta(days=1))
    assert cut[0].open_time.max() < end - pd.Timedelta(days=1) and prov_cut != prov    # cut changes provenance
    with pytest.raises(ValueError):
        gen.load_snapshot(root, end + pd.Timedelta(days=1))
    frame = pd.read_parquet(root / "premium.parquet")
    frame.loc[0, "premium"] = 1.0
    frame.to_parquet(root / "premium.parquet", index=False)
    with pytest.raises(RuntimeError, match="file hash"):
        gen.load_snapshot(root, end)


def test_hold_b_acceptance_needs_all_26_bit_exact_folds():
    good = {"frozen_checkpoint_max_abs_bps": 0.0, "regenerated_max_abs_bps": 0.0, "regenerated_missing_rows": 0}
    folds = {str(k): good for k in range(26)}
    assert gen.hold_b_acceptance(folds)["passed"]
    assert not gen.hold_b_acceptance(dict(list(folds.items())[:25]))["passed"]
    assert not gen.hold_b_acceptance({**folds, "0": {**good, "regenerated_max_abs_bps": 1e-7}})["passed"]
