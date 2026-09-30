# Direction relationship stability result

Data audit complete; full saved-table verification PASS.

Plan: `PATCHTST_DIRECTION_RELATION_STABILITY_PLAN_2026-09-18.md`.
Runner: `out/audit_patchtst_direction_relations.py` (`--self-check`, `--verify`).
Outputs: `out/patchtst_direction_relations_20260918`.

## Outcome

The audited relationships do not support blindly shortening TRAIN to30 days.
Single-feature directional relationships are weak and variable, but the
long-reference relationships retain their sign more often than shorter ones.
Distribution drift exists descriptively; this does not establish that drift
is the cause of the weak PatchTST OOS result. A separate source inspection
also identifies an additive-logit representation constraint worth testing.

Keep the agreed futures terminal H60 direction label. No TP/SL, cost gate,
model fitting, feature deletion, policy change, backtest or orders occurred.
Hourly sampling is diagnostic only; the model's15-minute origin grid and
60-minute lookback were not changed. Existing outputs remain intact.

## Coverage and causal boundary

- Same28 available historical folds, no replacement. Only each fold's
  TRAIN and following pre-OOS stop3d were analyzed. No OOS rows were used.
- Hourly origins have non-overlapping future return increments, but serial
  dependence remains. Recent3d contains59..71 labels per fold.
- Outer comparisons:84 eligible (28 folds x three reference windows).
- TRAIN-internal comparisons:551 eligible3d blocks x three windows =1,653;
  nine3d blocks lacked support, giving27 excluded window comparisons.
- Fold140 inner blocks0..6 and fold432 blocks15..16 were excluded for recent
  counts0/32/24/5. These are availability gaps, not evidence of direction drift.
- The inner long arm is a growing120..177-day prefix inside outer TRAIN,
  capped at180 days. Do not call it a full180-day inner rolling comparison.

## Feature-direction relationships

For each of35 endpoint features, determine increasing/decreasing orientation
from the reference AUC alone and measure the next3d AUC in that orientation.
These are averages of single-feature diagnostics, **not neural model AUC or
classification accuracy**. Reference orientation inflates its in-sample AUC,
especially with shorter reference samples; report recent results separately.

| Reference days | Outer next3d mean oriented feature AUC | Inner next3d mean oriented feature AUC | Outer sign retention* | Inner sign retention* |
|---|---:|---:|---:|---:|
| 30 | 0.510243 | 0.509872 | 58.35% | 58.84% |
| 60 | 0.515039 | 0.511886 | 62.71% | 62.30% |
| 180 cap | 0.510964 | 0.512077 | 70.40% | 64.48% |

*Subset where reference |AUC-0.5|>=0.02, fixed before execution. Different
windows produce different subsets; percentages are not matched-feature
effect estimates or significance tests. Outer subset counts437/354/277;
inner8,990/7,247/5,642 feature-block rows.

The60-day outer arm is slightly better descriptively, but TRAIN-internal60d
and long-prefix values differ by only0.000191. Neither this nor the30-day
result justifies selecting a neural training window. Window effects require
a new causally selected neural experiment. All features were retained; no
best-feature or OOS-selected feature list was produced.

## Distribution, labels and redundancy

Median outer empirical KS distance across feature/fold pairs:
30d0.12433,60d0.12687,180d0.13217. The respective90th percentiles are
0.24796/0.26293/0.27224. These describe distribution differences, not
independent-sample p-values or proven conditional drift. The mean absolute
TRAIN180-to-recent class-prior change is4.817 percentage points; about70
recent labels and temporal dependence prohibit treating it as proof of drift.
Fold-average down rates are49.39% in TRAIN180 and49.82% in recent3d;
there is no severe overall class imbalance in this audited binary task.
See [SciPy's KS assumptions/statistic](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html).

Recent endpoint clipping under the original full-TRAIN scaler averages
0.0216% across feature/fold pairs; the maximum is2.817% for one pair.
Clipping is not obviously widespread at endpoints. This did not inspect
every token's clipping inside the complete60-bar model input.

Equal-weight fold-average terminal-return profiles:

| Scope | Median absolute H60 return | Within0.01% | Within0.05% | Within0.10% |
|---|---:|---:|---:|---:|
| TRAIN180 | 0.2483% | 2.351% | 12.461% | 24.492% |
| Recent3d | 0.2507% | 2.328% | 12.071% | 24.534% |

Extremely small terminal moves are not most of this hourly label population.
This does not make large moves predictable, establish a correct economic
target, or replace any future path/execution analysis. These magnitude bins
were not used to create a neutral class or include transaction fees.

Among595 feature pairs,9..13 per fold have |TRAIN Spearman|>=0.90, mean10.43.
Examples present in all28 folds: short_return_1 versus short_body (mean
correlation0.999910), short_ema_gap_10 versus short_ema_gap_15 (0.965347),
and taker_sell_imbalance_5m versus signed_sell_volume_intensity_5m (0.972069).
Redundancy is real, but a few redundant pairs do not establish the failure
cause or authorize dropping inputs.

## Separate code finding: additive fusion constraint

Source: `out/run_short_patchtst.py`, `encode_channels` and `forward`;
`out/run_patchtst_pure_direction_h60.py`, `DirectionPatchTST`.
Attention operates on temporal patches **within each feature channel**.
The output head is a single Linear(channels*48,1). At supplied feature-input
level the inference logit therefore has the form:

`logit(X) = bias + sum_channel weight[channel] · Encoder(X[channel])`.

This is additive fusion after nonlinear per-channel sequence encoding, not
a learned nonlinear joint representation across channels. It can combine
additive evidence and encode interactions already provided as engineered
input features (including return x OI terms). It is not unable to use multiple
features at all. However, arbitrary non-additive interactions between
separate channel representations are restricted. The final sigmoid does not
remove that restriction on the logit/decision score.

A read-only trained-fold15 check changed taker_sell_imbalance_1m and
estimated_funding_pressure_uncapped independently and together. The mixed
logit difference z(A+B)-z(A)-z(B)+z(base) was-5.96e-8, consistent with
additivity. This is a structural sanity check on synthetic model inputs,
not a measured causal feature effect or evidence that nonlinear fusion
will improve financial predictions.

## Next boundary

There is no strong data-audit reason to rework the direction label or blindly
shorten TRAIN to30d. Do not repeat TP/SL/loss sweeps or expand606-fold fitting.
The next candidate is a minimal nonlinear joint classification-head comparison
while keeping the encoder, pure-direction target, lookback, calendar and
evaluation origins fixed. It needs a separate frozen Plan with TRAIN-only
internal selection and proper-scoring/directional evaluation. Extra head
capacity must be reported as a confound, or controlled explicitly before
claiming that interactions caused any improvement. No next fit was launched.

Runtime359.1 seconds before separate verification; zero experimental model
fits/backtests/orders and no new dependencies. This remains retrospective
research on previously inspected calendar dates, not pristine confirmation.

Verification record: `out/patchtst_direction_relations_20260918/verification.json`.
All28 folds passed reconstructed source-label/calendar checks, hourly source
snapshot reconciliation, sklearn AUC comparisons for every eligible feature
comparison, empirical-CDF KS reconciliation, independent Spearman computation,
all saved-table reconstruction and summary/hash accounting. No OOS rows used.
