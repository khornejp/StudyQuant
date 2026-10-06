"""Dump every completed R2-43 fold's predictive metrics, unfiltered, to CSV + markdown.

Read-only on fold prediction files; does not touch training or selection.
    venv_btcusdt\\Scripts\\python.exe scripts\\report_vol_detector_progress.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "out/k45_vol_detector_r2_43_20261006"
TARGETS = [f"{kind}_{h}" for kind in ("range", "rv") for h in ("30m", "1h", "4h", "12h", "24h")]


def fold_rows(path: Path) -> list[dict[str, object]]:
    frame = pd.read_parquet(path)
    rows = []
    for target in TARGETS:
        pred, act, naive = (frame[f"{k}_{target}"].astype(float) for k in ("prediction", "actual", "naive"))
        ok = np.isfinite(pred) & np.isfinite(act) & np.isfinite(naive)
        p, a, n = pred[ok], act[ok], naive[ok]
        mae_model, mae_naive = float((p - a).abs().mean()), float((n - a).abs().mean())
        hit = frame.loc[ok, f"prediction_high_{target}"].astype(bool)
        truth = frame.loc[ok, f"actual_high_{target}"].astype(bool)
        rows.append({
            "candidate": frame.candidate.iloc[0], "segment": frame.segment.iloc[0],
            "fold": int(frame.fold.iloc[0]), "start": frame.timestamp.min(), "target": target,
            "n": int(ok.sum()),
            "rank_ic": float(p.rank().corr(a.rank())),
            "naive_rank_ic": float(n.rank().corr(a.rank())),
            "mae_model": mae_model, "mae_naive": mae_naive,
            "mae_skill": (mae_naive - mae_model) / mae_naive if mae_naive else np.nan,
            "q80_precision": float(truth[hit].mean()) if hit.any() else np.nan,
            "q80_recall": float(hit[truth].mean()) if truth.any() else np.nan,
        })
    return rows


def _md(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in frame.itertuples(index=False)]
    return "\n".join(lines)


def main() -> None:
    files = sorted(ROOT.glob("folds/*/*/fold_*_predictions.parquet"))
    table = pd.DataFrame([row for path in files for row in fold_rows(path)])
    out = ROOT / "progress_metrics"
    out.mkdir(exist_ok=True)
    table.to_csv(out / "fold_metrics_all.csv", index=False)
    summary = (table.groupby(["candidate", "target"])
               [["rank_ic", "naive_rank_ic", "mae_skill", "q80_precision", "q80_recall"]]
               .mean().round(4).reset_index())
    folds = table.groupby("candidate").fold.nunique().rename("folds_done")
    with open(out / "summary.md", "w", encoding="utf-8") as handle:
        handle.write(f"# R2-43 진행 중 예측 품질 (완료 fold 전부, 거르지 않음)\n\n"
                     f"생성: {pd.Timestamp.now(tz='Asia/Seoul'):%Y-%m-%d %H:%M} KST. "
                     f"선택은 동결 규칙대로 학습 종료 후에만 한다. 이 표는 중간 관찰이며 선택에 쓰지 않는다.\n\n")
        handle.write(_md(folds.reset_index()) + "\n\n")
        handle.write(_md(summary) + "\n")
    print(out / "summary.md")


if __name__ == "__main__":
    main()
