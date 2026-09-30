# Pure-direction nonlinear fusion head pilot result

Complete: `FUSION_PILOT_FAIL`; saved-model verification PASS.

Plan: `PATCHTST_DIRECTION_FUSION_HEAD_PLAN_2026-09-18.md`.
Runner: `out/run_patchtst_direction_fusion_head.py` (`--self-check`, `--verify`).
Output: `out/patchtst_direction_fusion_head_20260918`.

## Outcome

Nonlinear joint fusion improved pooled balanced accuracy, pooled AUC, log
loss and Brier versus the existing linear model in all three seeds. All
joint seeds now beat the pre-OOS stop prior on probability errors in this
six-fold pilot. This is a real measured improvement, not "nothing worked."

However, within-fold ranking is seed-sensitive, and joint fusion does not
consistently beat the capacity-matched additive control. No seed meets the
full preregistered adoption/expansion gate. Do not promote it or claim a
robust directional solution. The additive constraint exists, but this
experiment has not established it as the principal failure cause.

## What changed, and what did not

Only the experimental classification head changed. Same35 futures features,
60 one-minute bars, strict close[t+60]<close[t] target/excluded ties, BCE,
180d/stop3d/OOS3d calendar,15-minute origin grid. Common encoder architecture
and initial weights per seed; encoder remains trainable end to end.
No new inputs, loss switch, TP/SL/cost gate, trading backtest or live orders.
Production/legacy code and all previous frozen runners/outputs were preserved.

| Arm | Head | Head parameters | Total |
|---|---|---:|---:|
| linear | Existing linear joint score | 1,681 | 21,361 |
| joint |1680→32→1 GELU MLP | 53,825 | 73,505 |
| additive | Per-channel48→31→1 GELU, sum/sqrt(35) | 54,285 | 73,965 |

The additive control uses grouped1x1 convolutions, with no nonlinear
cross-channel fusion. Total capacity differs by0.63% between new arms;
layout, activation count, head initialization and selected optimizer still
differ. This is an approximately matched architectural comparison, not a
perfect causal interaction intervention.

## Causal tuning

Same four lr/wd candidates and three chronological inner validation blocks
inside first-fold TRAIN for every arm. Linear's verified records were reused;
new heads each made12 tuning fits with seed42. Parameters were locked before
new outer OOS predictions. Width/dropout/activation/window were not tuned.

| Arm | Selected lr | Selected wd | Mean inner validation BCE |
|---|---:|---:|---:|
| linear | 0.0003 | 0.001 | 0.686049 |
| joint | 0.001 | 0.00001 | 0.687848 |
| additive | 0.0003 | 0.00001 | 0.687681 |

This is limited supervised tuning, not globally optimal hyperparameters.
New outer fits retain15-epoch cap/patience3 and best stop-BCE checkpoint.
Joint/additive selected epoch1 in8/18 fits each (linear2/18). This records
short-window selection behavior, not proof of a broken optimizer or no
benefit from any different regularization/training protocol.

## Same OOS origins, all three seeds

Six fixed folds15/140/244/348/453/598,1,687 origins per arm/seed,15,183
prediction rows total. These repeated copies are not independent samples;
H60 labels at15-minute spacing overlap. Dates were already inspected
project-wide: retrospective pilot, not pristine confirmation.

| Seed | Arm | Pooled AUC | Mean-fold AUC | Pooled balanced accuracy | Log loss | Brier |
|---|---|---:|---:|---:|---:|---:|
|42|linear|0.523870|0.534347|51.260%|0.696803|0.251691|
|42|joint|0.531769|0.504040|51.667%|0.692521|0.249684|
|42|additive|0.521992|0.534599|51.091%|0.693500|0.250173|
|43|linear|0.519878|0.525937|49.954%|0.697042|0.251880|
|43|joint|0.529681|0.545723|51.674%|0.693103|0.249951|
|43|additive|0.519426|0.543441|51.444%|0.693790|0.250315|
|44|linear|0.512110|0.532869|51.498%|0.698949|0.252786|
|44|joint|0.527381|0.535710|51.903%|0.692506|0.249671|
|44|additive|0.521337|0.529968|52.138%|0.693468|0.250155|

Stop prior, identical for all arms/seeds: pooled AUC0.525009, balanced
accuracy50.890%, log loss0.693854, Brier0.250353. Do not directly compare
these six-fold numbers to the earlier28-fold cohort's aggregate scores.

| Seed | Joint-minus-linear BA | Joint-minus-additive BA | Fold AUC wins versus linear/additive |
|---|---:|---:|---|
|42|+0.407pp|+0.576pp|2/6,0/6|
|43|+1.720pp|+0.230pp|5/6,4/6|
|44|+0.404pp|-0.235pp|4/6,4/6|

Seed42 fails mean-fold ranking and consistency despite improved pooled
metrics. Seed43 gains against linear but its advantage over additive is
below the required0.005 AUC/0.5pp BA. Seed44 lacks the required linear
mean-fold AUC/BA gains and trails additive BA. All seed gates FAIL.

## Direction versus probability error

Pooled AUC compares scores from different calendar models as well as scores
inside one3d interval. Calibration/regime offsets can improve pooled ranking
while within-fold discrimination worsens; seed42 demonstrates exactly that.
Neither metric is a calculation error, but they answer different stability
questions. Do not use pooled AUC0.532 as proof of local direction accuracy.
Joint down/up recall is72.45%/30.89% for seed42,42.87%/60.47% for43 and
38.48%/65.33% for44: the sign boundary remains initialization-sensitive.

Restored TRAIN mean-fold AUC:

| Seed | linear | joint | additive |
|---|---:|---:|---:|
|42|0.552657|0.533658|0.555856|
|43|0.548825|0.552838|0.549081|
|44|0.555257|0.546753|0.546508|

No consistent higher TRAIN ranking emerges from adding joint capacity.

Post-hoc explanatory accounting, not a new gate or feature/policy selection:
reuse `out/diagnose_short_probability_stability.py`, `decompose`/`aggregate`
on saved probabilities. For fixed labels, within-fold Brier equals
uncertainty + mean-bias-squared + probability-variance - twice-covariance.
This algebra reconciled the reported Brier scores. For seed42, linear→joint:
bias-squared0.006500→0.003666, variance0.002797→0.000584, twice-covariance
0.003142→0.000101. Bias/variance reductions improve proper scores even
though the covariance contribution shrinks. All joint seeds similarly have
lower bias/variance and smaller covariance contribution than linear.
Covariance also depends on probability scale: it alone is not an information
or causal-effect test. These findings explain why probability improvement
must not be conflated with stable directional discrimination.

## Verification and boundary

Pre-fit checks PASS: exact parameter counts, matching initial encoder,
one-output/finite gradients, additive mixed-logit zero versus joint nonzero,
and4096-row grouped-head CUDA inference. Each new checkpoint passed
save/restore probe equality. Full verification PASS rebuilds source-price
labels, causal splits/scalers and tuning selection; replays24 tuning models
and all54 outer models' TRAIN/stop/OOS scores (36 new,18 reused); compares
independent metric formulas and recomputes the frozen gates and output hashes.
Record: `out/patchtst_direction_fusion_head_20260918/verification.json`.

Actual historical fits60 (24 tuning +36 outer),18 linear outer models reused;
657.0 seconds before independent verification. Existing helpers/reference
models were reused; no new dependency or experimental framework.

Retain both new heads as research candidates only. No automatic expansion,
gate relaxation, backtest or live promotion. Do not call the agreed target
incorrect from this result, or claim nonlinear fusion has no possible value.
If continuing, prioritize the objective/checkpoint-selection distinction:
stable within-window direction versus class-prior/probability-error fitting,
with a new causal Plan and internal TRAIN validation. Blindly enlarging the
encoder, adding a hybrid or repeating head sweeps is not supported here.
