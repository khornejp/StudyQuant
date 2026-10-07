"""Dump every completed detector fold's predictive metrics, unfiltered, to CSV + markdown.

Read-only on fold prediction files; does not touch training or selection.  "High" flags
use the R2-44 rank method (model's own previous 30 days of predictions); the stored
level-method flags are reported next to them for reference.
    venv_btcusdt\\Scripts\\python.exe scripts\\report_vol_detector_progress.py [run_dir]
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / (sys.argv[1] if len(sys.argv) > 1 else "out/k45_vol_detector_r2_44_window_20261006")
_spec = importlib.util.spec_from_file_location("r244", REPO / "out/run_k45_vol_detector_r2_44_window.py")
r244 = importlib.util.module_from_spec(_spec)
sys.modules["r244"] = r244
_spec.loader.exec_module(r244)
TARGETS = list(r244.r.TARGETS)


def _rate(flag: pd.Series, truth: pd.Series) -> tuple[float, float]:
    flag, truth = flag.astype(bool), truth.astype(bool)
    return (float(truth[flag].mean()) if flag.any() else np.nan,
            float(flag[truth].mean()) if truth.any() else np.nan)


def candidate_rows(paths: list[Path]) -> list[dict[str, object]]:
    frame = r244.rank_flags(pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))
    level = f"level_high_{TARGETS[0]}" in frame
    rows = []
    for (segment, fold), part in frame.groupby(["segment", "fold"], sort=True):
        for target in TARGETS:
            p, a, n = (part[f"{k}_{target}"].astype(float) for k in ("prediction", "actual", "naive"))
            ok = np.isfinite(p) & np.isfinite(a) & np.isfinite(n)
            mae_model, mae_naive = float((p[ok] - a[ok]).abs().mean()), float((n[ok] - a[ok]).abs().mean())
            truth = part[f"actual_high_{target}"]
            ready = part[f"rank_ready_{target}"].astype(bool)
            flag = part.loc[ready, f"prediction_high_{target}"]
            precision, recall = _rate(flag, truth[ready])
            row = {"candidate": part.candidate.iloc[0], "segment": segment, "fold": int(fold),
                   "start": part.timestamp.min(), "target": target, "n": int(ok.sum()),
                   "rank_ic": float(p[ok].rank().corr(a[ok].rank())),
                   "naive_rank_ic": float(n[ok].rank().corr(a[ok].rank())),
                   "mae_model": mae_model, "mae_naive": mae_naive,
                   "mae_skill": (mae_naive - mae_model) / mae_naive if mae_naive else np.nan,
                   "base_rate": float(truth.astype(bool).mean()),
                   "rank_flag_rate": float(flag.mean()) if ready.any() else np.nan,
                   "rank_precision": precision, "rank_recall": recall}
            if level:
                row["level_precision"], row["level_recall"] = _rate(part[f"level_high_{target}"], truth)
            rows.append(row)
    return rows


def _md(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in frame.itertuples(index=False)]
    return "\n".join(lines)


def main() -> None:
    groups: dict[str, list[Path]] = {}
    for path in sorted(ROOT.glob("folds/*/*/fold_*_predictions.parquet")):
        groups.setdefault(path.parts[-3], []).append(path)
    table = pd.DataFrame([row for paths in groups.values() for row in candidate_rows(paths)])
    out = ROOT / "progress_metrics"
    out.mkdir(exist_ok=True)
    table.to_csv(out / "fold_metrics_all.csv", index=False)
    metric_cols = [c for c in table.columns if c not in ("candidate", "segment", "fold", "start",
                                                         "target", "n", "mae_model", "mae_naive")]
    summary = table.groupby(["candidate", "segment", "target"])[metric_cols].mean().round(4).reset_index()
    folds = table.groupby(["candidate", "segment"]).fold.nunique().rename("folds_done")
    with open(out / "summary.md", "w", encoding="utf-8") as handle:
        handle.write(f"# 탐지기 진행 중 예측 품질 (완료 fold 전부, 거르지 않음)\n\n"
                     f"생성: {pd.Timestamp.now(tz='Asia/Seoul'):%Y-%m-%d %H:%M} KST. "
                     "중간 관찰이며 선택에 쓰지 않는다.\n\n")
        handle.write(_md(folds.reset_index()) + "\n\n")
        handle.write(_md(summary) + "\n")
    print(out / "summary.md")


if __name__ == "__main__":
    main()
