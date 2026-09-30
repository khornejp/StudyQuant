# PatchTST direction objective/checkpoint-selection report

Date: 2026-09-19 (Asia/Seoul)

## Result

`OBJECTIVE_SELECTION_FAIL`. Independent replay verification passed.

Changing BCE checkpoint selection to mean daily AUC, or adding same-day
pairwise ranking loss, did not produce a seed-stable direction improvement.
The result rejects these changes at this tested scope. It does **not** show
that every ranking loss is useless, nor that the H60 direction target is
intrinsically unpredictable.

No TP/SL, fees, slippage, magnitude threshold, backtest, spot data, or order
path was used. This remained a futures-only, pure H60 direction experiment.

## Frozen comparison

- Same 35 futures features, preceding 60 one-minute bars, strict
  `close[t+60] < close[t]` label and 15-minute origins.
- Same joint nonlinear FusionPatchTST, 180-day TRAIN / 3-day stop / 3-day OOS.
- Six folds 15/140/244/348/453/598 and seeds 42/43/44.
- Fixed AdamW `lr=0.001`, `weight_decay=0.00001`, batch 1024.
- Exactly 15 epochs, with all states saved.
- Objectives: BCE, and BCE + weight-1 same-UTC-day pairwise logistic ranking.
- Selectors: minimum stop BCE, and maximum mean eligible-day stop AUC.
- 36 new fits; 18 prior joint reference models reused; 1,687 distinct OOS
  origins per arm/seed; 25,305 prediction rows.

The Plan was motivated by direct ranking methods, while retaining the caveat
that proper logistic losses can themselves be AUC-consistent under assumptions:
[Agarwal 2013](https://proceedings.mlr.press/v30/Agarwal13.html),
[Gao and Zhou 2013](https://proceedings.mlr.press/v28/gao13.html), and
[Liu and Bellet 2018](https://proceedings.mlr.press/v80/liu18g.html).

## OOS metrics

`reference` is the prior joint model. `bce_bce` trains all 15 epochs and then
selects the minimum-BCE epoch, so it is not byte-identical to the prior
patience-3 training path.

| Seed | Arm | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---:|---|---:|---:|---:|---:|---:|---:|
|42|reference|0.531769|0.504040|0.502012|51.667%|0.692521|0.249684|
|42|bce_bce|0.515805|0.509482|0.508296|50.610%|0.694856|0.250838|
|42|bce_auc|0.498691|0.535233|0.541289|48.144%|0.698107|0.252459|
|42|rank_bce|0.526696|0.526834|0.535119|53.165%|0.699527|0.252847|
|42|rank_auc|0.513476|0.541984|0.546940|51.319%|0.715473|0.259792|
|43|reference|0.529681|0.545723|0.550547|51.674%|0.693103|0.249951|
|43|bce_bce|0.517321|0.528944|0.534106|51.910%|0.697156|0.251936|
|43|bce_auc|0.503997|0.535127|0.546056|50.784%|0.710330|0.258027|
|43|rank_bce|0.497127|0.528700|0.541660|50.480%|0.710624|0.258272|
|43|rank_auc|0.509691|0.538663|0.547433|51.607%|0.708262|0.257028|
|44|reference|0.527381|0.535710|0.542834|51.903%|0.692506|0.249671|
|44|bce_bce|0.528072|0.542072|0.549222|52.082%|0.693459|0.250099|
|44|bce_auc|0.527181|0.540090|0.547967|52.452%|0.694622|0.250664|
|44|rank_bce|0.509297|0.537462|0.552669|50.609%|0.708069|0.256966|
|44|rank_auc|0.492018|0.523125|0.531073|49.543%|0.725089|0.264150|

Across-seed arithmetic means:

| Arm | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
|reference|0.529610|0.528491|0.531798|51.748%|0.692710|0.249769|
|bce_bce|0.520399|0.526833|0.530541|51.534%|0.695157|0.250957|
|bce_auc|0.509957|0.536817|0.545104|50.460%|0.701020|0.253717|
|rank_bce|0.511040|0.530999|0.543149|51.418%|0.706073|0.256028|
|rank_auc|0.505062|0.534591|0.541815|50.823%|0.716275|0.260324|

## What the split metrics mean

The daily-AUC selector did change the fitted solution. On seed 42 it raised
mean-fold AUC by 2.58 percentage points for BCE and 1.52 points for ranking,
relative to the corresponding BCE selector. But pooled AUC fell by 1.71 and
1.32 points, balanced accuracy fell, and probability errors worsened. Seed 43
showed smaller local-ranking gains; seed 44 reversed them. This is not a
stable direction solution.

The pooled/within-fold disagreement is important. Pooled AUC can benefit from
between-calendar score offsets, whereas mean-fold and daily AUC measure more
local ordering. Optimizing a three-day stop window for local AUC can improve
that local statistic yet transfer poorly to the next three days and disturb
the 0.5 decision boundary. The result therefore does not justify optimizing
only pooled AUC or only daily AUC.

Pairwise ranking weight 1 was too costly to probability quality here. Against
`bce_bce`, `rank_bce` changed mean-fold AUC by +1.74/-0.02/-0.46 points for
seeds 42/43/44, while log loss worsened by 0.0047/0.0135/0.0146. Direction and
calibration did not trade off consistently enough to adopt it.

## Checkpoint behavior

Mean selected epoch was 6.56 for BCE-selection and 9.33 for AUC-selection on
the BCE trajectory; 6.17 and 8.94 on the ranking trajectory. Selectors agreed
in only 4/18 and 5/18 fits. BCE selected epoch 1 in 5/18 BCE fits and 4/18
ranking fits; AUC never selected epoch 1 on ranking.

This disproves the narrow claim that the previous result existed only because
all useful direction training was stopped at epoch 1. Later checkpoints exist
and local-AUC selection finds them, but their improvement is not stable OOS.

## Gate and interpretation

No treatment passed in any all-seed sense. Seed 42 produced promising local
ranking numbers, but failed pooled AUC, balanced-accuracy, probability-error,
or fold-win conditions depending on arm. Seed 43 did not beat the reference;
seed 44 reversed several ranking effects. No arm is promoted.

The supported conclusion is narrower than “the model cannot learn”:

1. Earlier fit diagnostics showed the implementation can memorize controlled
   signals.
2. Nonlinear fusion gave a small genuine pooled/probability improvement.
3. This test shows that BCE checkpoint selection is not the sole bottleneck.
4. Weight-1 same-day pairwise loss is not a robust remedy.
5. Remaining weakness is unstable out-of-period feature-to-direction
   relationship and model variance, not a missing TP/SL or cost gate.

## Verification and next boundary

Verification rebuilt the target and independent causal splits/scalers, replayed
all 540 saved stop states and both selected OOS checkpoints per trajectory,
recomputed metrics/gates, and verified source/output hashes: `PASS`.

Do not tune ranking weight or selector on these six OOS outcomes. The next
lowest-cost diagnostic should use only the already saved predictions to test
whether seed/checkpoint ensembling reduces variance. If it does not, stop
loss/head iteration and return to information design (feature/target horizon or
regime conditioning) under a new frozen Plan. Any broader confirmation still
requires genuinely future untouched data.
