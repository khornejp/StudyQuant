# PatchTST direction seed/checkpoint ensemble report

Date: 2026-09-19 (Asia/Seoul)

## Result

`ENSEMBLE_VARIANCE_FAIL`. Independent verification: `PASS`.

Simple probability averaging measurably reduced some stochastic variance, but
did not improve directional decisions enough to pass the frozen gate. No
ensemble becomes a broader replication candidate. This test made no new model
fit and used no TP/SL, cost, backtest, spot data, or order path.

## Fixed test

The verified 25,305 saved rows from the preceding objective/checkpoint test
were the only input. Seven unweighted probability means were fixed before
calculation: five three-seed means and two six-path seed+checkpoint means.
There was no logit averaging, threshold change, learned weight, arm selection,
or OOS tuning. Each ensemble had the same 1,687 origins over six folds.

## Ensemble results

| Ensemble | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
|reference seed mean|**0.533480**|**0.542855**|**0.551387**|51.859%|**0.691576**|**0.249214**|
|BCE/BCE seed mean|0.519843|0.535840|0.543232|51.801%|0.693193|0.250020|
|BCE/AUC seed mean|0.506529|0.540486|0.551263|50.669%|0.697004|0.251910|
|rank/BCE seed mean|0.511393|0.533024|0.546205|51.732%|0.701887|0.254200|
|rank/AUC seed mean|0.507160|0.537611|0.546989|51.082%|0.708738|0.257229|
|BCE dual mean|0.512422|0.540868|0.549924|50.434%|0.694543|0.250695|
|rank dual mean|0.509262|0.536467|0.547534|**51.968%**|0.703440|0.254926|

The reference seed mean is the clear overall result: best pooled/local AUC and
best proper probability scores. The rank dual mean has balanced accuracy only
0.11 percentage points above it, while losing 2.42 AUC points and materially
worsening log loss/Brier. It is not a better model.

## Gains over constituent-path means

| Ensemble | Pooled AUC gain | Mean-fold gain | Daily gain | BA gain | Fold wins | Log-loss change |
|---|---:|---:|---:|---:|---:|---:|
|reference seed mean|+0.003870|+0.014364|+0.019590|+0.001115|5/6|-0.001134|
|BCE/BCE seed mean|-0.000557|+0.009008|+0.012691|+0.002671|4/6|-0.001964|
|BCE/AUC seed mean|-0.003428|+0.003670|+0.006159|+0.002090|3/6|-0.004016|
|rank/BCE seed mean|+0.000353|+0.002025|+0.003056|+0.003138|3/6|-0.004186|
|rank/AUC seed mean|+0.002098|+0.003021|+0.005174|+0.002587|5/6|-0.007537|
|BCE dual mean|-0.002756|+0.009043|+0.012102|-0.005632|4/6|-0.003546|
|rank dual mean|+0.001211|+0.003673|+0.005051|+0.008475|4/6|-0.007734|

The reference average passed every material variance condition except the
pre-registered +0.005 balanced-accuracy gain: actual gain was +0.001115.
Therefore it is wrong to say averaging did nothing. It improved ranking and
calibration, but not the hard 0.5 direction decision enough to solve the
project's current problem.

Rank dual averaging did exceed the balanced-accuracy gain threshold, but its
mean-fold gain was below +0.005 and it was much weaker than the reference
ensemble. Other arms lost pooled AUC or missed multiple direction gates.

## Diversity

The reference paths had mean pairwise probability correlation 0.4585, mean
per-origin probability standard deviation 0.0200, and mixed 0.5 votes on
55.1% of origins. The model therefore has meaningful seed variation. Averaging
uses that diversity productively for AUC/log loss, but most corrected scores do
not cross the hard decision boundary in a reliably correct direction.

Checkpoint mixing increased disagreement further: BCE dual mixed votes on
67.8% of origins and rank dual on 53.8%, without producing a better overall
direction model. More diversity alone is not the missing information.

## Supported conclusion

Seed variance is a secondary issue, not the primary bottleneck. The best
research representation currently is the three-seed probability mean of the
prior joint reference, but it remains research-only and fails the frozen
improvement gate. Do not tune ensemble weights or decision thresholds on these
inspected OOS dates.

Per the frozen stopping rule, stop further loss/head/checkpoint/ensemble
iterations. The next work should move back to information structure: a causal
regime-conditioning audit that asks whether H60 feature-direction relations
are stable inside predefined volatility/trend/crowding states. Only if such
conditional stability exists should a regime-conditioned direction model be
trained. Genuinely future untouched data remains required for adoption.

## Verification

The verifier pinned the prior output index and prediction hash, rebuilt all
seven ensembles from source rows, and independently recomputed metrics,
diversity and gates. All hashes and 11,809 saved ensemble rows matched. No
neural fit, backtest, or order was created.
