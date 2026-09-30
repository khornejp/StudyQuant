# PatchTST class-aware selective direction report

Date: 2026-09-19 (Asia/Seoul)

## Outcome

`CLASSWISE_SELECTIVE_PASS`. Independent verification: `PASS`.

The underlying fixed H15/H60 cross-horizon PatchTST still has modest accuracy
when forced to classify every origin. The material improvement came from
changing the decision problem to selective classification: predict only when
the model is unusually confident relative to the immediately preceding STOP
period, otherwise abstain.

For each fold, the 90th percentile of `abs(p_down - 0.5)` was computed
separately for STOP-predicted down and STOP-predicted up rows. Those two
label-free thresholds were frozen and applied to TEST rows of the same predicted
class. No threshold grid, TEST tuning, model fit, TP/SL, fee, backtest or order
was used.

This follows the reject-option/risk-coverage framing in selective
classification: https://www.jmlr.org/papers/v11/el-yaniv10a.html and
https://arxiv.org/abs/1705.08500.

## Recent folds 348/453/598

- Accepted: 71/844 origins, 8.41% coverage.
- Pooled AUC: 0.615079.
- Accuracy: 60.563%.
- Balanced accuracy: 60.675%.
- Predicted down: 30; precision 63.333%.
- Predicted up: 41; precision 58.537%.
- Fold BA: 52.778%, 59.524%, 55.556%; two of three exceed 55%.
- Every frozen material-improvement check passed.

Compared with the forced all-origin recent classifier (AUC 0.534956, BA
53.152%), this is a large accepted-set improvement: +8.01 AUC points and +7.52
balanced-accuracy points, at the explicit cost of rejecting 91.59% of origins.
The cohorts differ, so this is a risk-coverage result, not a claim that the
underlying probability model itself improved by those amounts.

## All six folds

- Accepted: 199/1,685 origins, 11.81% coverage.
- AUC: 0.586895; accuracy 56.281%; BA 57.474%.
- Down precision 64.384%; up precision 51.587%.

The older fold 15 is poor and predicts almost entirely up after selection.
Therefore the pass is a recent-period candidate, not broad historical
stationarity evidence. It must be replicated over the broader 3-day
walk-forward sequence before economic testing.

## Search results before the pass

- iTransformer-style variable-token attention: failed; recent BA 53.293%,
  pooled AUC 0.543886, mean-fold AUC 0.544957.
- TSMixer: failed; recent BA 50.990%, pooled AUC 0.524879.
- H60-to-H15 supervised transfer: failed; recent BA 52.426%, pooled AUC
  0.533405.
- Masked PatchTST pretraining: failed; recent BA 50.467%, pooled AUC 0.525424.
- Trend/mean target audit: future-mean H15 selected in development but lost to
  terminal H15 on later folds, 0.534183 versus 0.546261 mean AUC.
- Legacy feature expansion: complete-coverage base+GRU lost by -0.009411 mean
  AUC; 3/14 wins.
- MTF43 expansion: essentially tied and failed, -0.000228 mean AUC; 7/14 wins.
- Global confidence top-10%: pooled recent BA 58.225% but failed up precision
  and fold consistency. Class-conditional calibration fixed that imbalance.

## Boundary and next step

This result improves direction reliability only on the accepted subset. It
does not establish profitability and does not authorize live trading. The next
valid experiment is to freeze the exact recipe—H15/H60 three-seed 50:50 model,
class-specific STOP 90th-percentile confidence thresholds, no tuning—and
replicate it over many consecutive three-day OOS folds. Only if direction
precision/coverage remains stable should TP/SL and limit-order economics be
tested on the accepted signals.

