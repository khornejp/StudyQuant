# PatchTST class-aware selective direction broad replication report

Date: 2026-09-19 (Asia/Seoul)

## Outcome

`CLASSWISE_SELECTIVE_REPLICATION_PASS`. Independent reconstruction: `PASS`.

The exact frozen class-aware reject rule was replicated over all 28 eligible
folds among the fixed 30-fold sparse pilot sample. It used the fixed three-seed H15/H60 PatchTST 50:50
probability blend and each fold's class-specific STOP 90th-percentile
confidence thresholds. No TEST labels selected a threshold. There was no
TP/SL, fee, backtest or order.

## Broad OOS result

- Population: 7,982 H15 origins across 28 folds.
- Accepted: 872 origins; 10.925% coverage.
- Selected AUC: 0.593764.
- Selected accuracy: 58.028%; balanced accuracy: 58.054%.
- Predicted down: 423; precision 59.102%.
- Predicted up: 449; precision 57.016%.
- Forced all-origin BA: 53.162%; accepted-set gain: 4.892 percentage points.
- Mean fold BA: 58.514%; 17/28 folds exceeded 55% BA.

The early 14 folds had 59.466% BA, 59.420% accuracy, 60.793% down precision
and 58.203% up precision. The late 14 folds had 56.293% BA, 56.298% accuracy,
57.143% down precision and 55.440% up precision. Every frozen replication gate
passed.

## Stability boundary

The aggregate result is real but not uniform. Fold BA ranged from 37.879% to
79.487%; folds 494, 515, 536 and 578 were below 46%. The later half is also
weaker than the earlier half. This rule therefore improves the reliability of
a sparse accepted subset; it does not make every three-day regime predictable
and does not prove profitability.

These are not 28 consecutive three-day folds. They span 2021-02-22 through
2025-12-28 with a median 63-day gap; none of the adjacent tested folds is only
three days apart. They cover 28/606 (4.62%) of the available calendar folds.
Accordingly, this pass does not satisfy the previously requested 200+ fold
continuous walk-forward replication.

## Reproducibility

- Plan: `PATCHTST_DIRECTION_CLASSWISE_SELECTIVE_REPLICATION_PLAN_2026-09-19.md`
- Runner: `out/run_patchtst_direction_classwise_selective_replication.py`
- Output: `out/patchtst_direction_classwise_selective_replication_20260919`
- New fits: 132; reused models: 36.
- Independent verification rebuilt every scaler, STOP threshold, TEST
  prediction, metric and gate from the stored checkpoints and passed.

## Next valid step

Keep this direction recipe frozen. Run a diagnostic on the failing folds using
only information available before each TEST interval, then evaluate
limit-order TP/SL economics on accepted signals as a separate layer. Historical
results remain retrospective; untouched future data is still required before
any live use.
