"""Is a per-minute PatchTST refresh better than holding the last 15-minute prediction? (R2-44 w730_raw, HOLD_B)

For every minute origin in HOLD_B (2026-01-01..2026-06-29) with complete inputs:
  B = fresh inference at that minute with the research fold covering it (weights unchanged),
  A = the prediction of the latest 15-minute origin <= that minute (what a 15-minute cadence serves).
Both are scored against the realised targets of the minute origin (log1p MAE and Spearman rank IC), by target and
by minutes since the last 15-minute boundary. Research checkpoints and archives are read only.
Writes out/k45_rl_r2_48_20261007/detector_refresh_check.csv
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pandas as pd, torch
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.paper import detector  # noqa: E402

FOLDS = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw/HOLD_B"
OUT = ROOT / "out/k45_rl_r2_48_20261007/detector_refresh_check.csv"


def main() -> None:
    r = detector.r44().r
    config = detector.r44().CONFIG
    device = torch.device("cuda")
    minutes, metrics, premium, funding = detector._archive_inputs()
    minutes = minutes.loc[minutes.open_time >= pd.Timestamp("2025-12-01", tz="UTC")].reset_index(drop=True)
    bars = [r.aggregate(minutes, f) for f in ("1min", "5min", "1h")]
    arrays = r.attach_exogenous(bars, metrics, premium, funding)
    data = SimpleNamespace(bars=bars, arrays=arrays)
    origins = pd.date_range("2026-01-01", "2026-06-29 00:00", freq="1min", tz="UTC")
    actual = r.future_targets(minutes, origins)                      # log1p bps, NaN where the horizon runs out
    folds = sorted(FOLDS.glob("fold_*.json"))
    pred = np.full((len(origins), len(r.TARGETS)), np.nan, np.float32)
    for k, meta_path in enumerate(folds):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        start, end = pd.Timestamp(meta["retrain_time"]), pd.Timestamp(meta["prediction_end"])
        rows = np.flatnonzero((origins >= start) & (origins < end))
        if not len(rows):
            continue
        checkpoint = torch.load(meta_path.with_suffix(".pt"), weights_only=False, map_location="cpu")
        model = r.MultiResolutionPatchTST(config, tuple(a.shape[1] for a in arrays)).to(device)
        model.load_state_dict(checkpoint["model_state"])
        endpoints = r.endpoint_indices(bars, origins[rows])
        pred[rows] = r._predict(model, data, np.arange(len(rows)), endpoints, config, checkpoint["means"],
                                checkpoint["stds"], device)
        print(f"fold {k} {start.date()} rows {len(rows)}", flush=True)
    fresh = pred                                                      # model output is log1p bps
    grid_index = pd.Series(np.arange(len(origins)), index=origins)
    last_grid = origins.floor("15min")
    held = fresh[grid_index.reindex(last_grid).to_numpy()]
    lag = ((origins - last_grid) / pd.Timedelta(minutes=1)).astype(int)
    ok = np.isfinite(actual).all(1) & np.isfinite(fresh).all(1) & np.isfinite(held).all(1)
    rows = []
    buckets = {"0 (grid)": lag == 0, "1-4": (lag >= 1) & (lag <= 4), "5-9": (lag >= 5) & (lag <= 9),
               "10-14": lag >= 10, "all off-grid": lag > 0}
    for j, name in enumerate(r.TARGETS):
        for label, mask in buckets.items():
            m = ok & mask
            a, b, y = held[m, j], fresh[m, j], actual[m, j]
            rows.append({"target": name, "minutes_since_grid": label, "n": int(m.sum()),
                         "mae_held_15m": float(np.abs(a - y).mean()), "mae_fresh_1m": float(np.abs(b - y).mean()),
                         "ic_held_15m": float(spearmanr(a, y).statistic), "ic_fresh_1m": float(spearmanr(b, y).statistic)})
    frame = pd.DataFrame(rows)
    frame["mae_gain_pct"] = (1 - frame.mae_fresh_1m / frame.mae_held_15m) * 100
    frame["ic_gain"] = frame.ic_fresh_1m - frame.ic_held_15m
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    pd.set_option("display.width", 220)
    print(frame.loc[frame.minutes_since_grid.isin(["1-4", "10-14", "all off-grid"])].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
