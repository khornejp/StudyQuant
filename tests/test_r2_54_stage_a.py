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
    assert not gen.completed(tmp_path, retrain, "c")
    for p in (ckpt, preds):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="partial"):
        gen.completed(tmp_path, retrain, "c")
    sha = detector.r44().r.sha256_file(ckpt)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps({"code_sha256": "c", "checkpoint_sha256": sha, "predictions_sha256": sha}))
    assert gen.completed(tmp_path, retrain, "c")
    with pytest.raises(RuntimeError, match="does not verify"):
        gen.completed(tmp_path, retrain, "other code")
