# H60 causal regime-conditioning audit report

Date: 2026-09-19 (Asia/Seoul)

## Result

`REGIME_CONDITIONING_AUDIT_FAIL`. Independent verification: `PASS`.

The predefined volatility/trend/crowding states exposed a promising local
effect, but it occurred too rarely to justify fitting a regime-conditioned
PatchTST. Only 12/28 folds qualified inside TRAIN and only 9 retained enough
state support in the following three-day stop block. The paired bootstrap
interval crossed zero.

No neural model was fitted. No TP/SL, fees, slippage, magnitude gate, spot
data, backtest, or order path was used.

## Fixed causal procedure

- Pure terminal H60 direction: `close[t+60] < close[t]`, ties excluded.
- Existing 35 futures features and 15-minute origins.
- 28 available rolling folds, up to 180-day TRAIN and next 3-day stop.
- Eight fixed intersections of:
  - `rv_15` below/above causal reference median;
  - `short_return_15` negative/nonnegative;
  - estimated funding pressure below/above causal reference median.
- Ten consecutive three-day blocks in the last 30 TRAIN days.
- Each block selected one feature and its direction from preceding TRAIN only.
- A state qualified only with at least 7/10 eligible blocks, mean inner AUC
  at least 0.52, and at least +0.01 over the unconditional inner control.
- The stop block never selected a state, feature, sign, or threshold.

The median splits are relative data partitions, not claims that a median
funding observation is economically extreme crowding.

## Aggregate result

| Measurement | Result | Frozen requirement |
|---|---:|---:|
| TRAIN-inner qualified folds | 12/28 | at least 18 |
| Paired eligible stop folds | 9/28 | at least 18 |
| Conditional mean stop AUC | 0.553223 | at least 0.52 |
| Conditional median stop AUC | 0.565769 | above 0.50 |
| Conditional folds above 0.5 | 77.78% | at least 60% |
| Unconditional paired mean AUC | 0.525528 | control |
| Mean conditional gain | +0.027695 | at least +0.01 |
| Conditional win rate | 77.78% | at least 60% |
| Fold bootstrap 95% interval | [-0.026948, 0.076764] | lower bound above 0 |

The effect size among eligible folds is worth recording. It is not enough to
pass because the audit would otherwise select a sparse success subset: nine
folds cannot establish a general regime mechanism, and the uncertainty range
includes harm.

## Coverage failure

The 12 TRAIN-selected states were spread across five definitions:

| Selected state | Folds |
|---|---:|
| high volatility / down trend / high crowding | 4 |
| low volatility / up trend / high crowding | 3 |
| high volatility / up trend / high crowding | 2 |
| low volatility / down trend / low crowding | 2 |
| high volatility / down trend / low crowding | 1 |

Three qualified folds then failed outer support: fold 35 had zero matching
stop rows, fold 181 had 13, and fold 536 had 5. This is not a coding drop; the
causal TRAIN medians and three-way intersection genuinely produced sparse or
absent next-period states.

Among the nine eligible conditional evaluations, the TRAIN-selected feature
also varied: `short_return_10` and 15-minute taker imbalance appeared twice;
funding change, EMA gap, 1/3-minute taker imbalance and ATR appeared once each.
There is no single recurring state-feature mechanism to carry directly into a
new model.

## Individual outer behavior

Conditional oriented AUCs included strong wins at folds 77 (0.6667), 473
(0.6361), 557 (0.5658), 578 (0.5671) and 604 (0.5783). They also included
fold 515 at 0.4239 and fold 223 at 0.4971. This explains both the positive
average and the bootstrap interval crossing zero.

All eight states were frequently measurable inside TRAIN—the eligible inner
counts ranged from 131 to 171 of 280 possible state-blocks—so the failure is
not simply that the audit could never calculate them. The stricter repeatable
gain rule and next-period state availability removed most folds.

## Supported conclusion

Simple three-axis regime conditioning is a plausible source of occasional
edge, but it is not sufficiently available or stable to train a dedicated
model now. Doing so would turn nine favorable retrospective cases into a
general rule without evidence.

The previous stopping rule remains active: do not resume loss/head/checkpoint/
ensemble sweeps. Before another model fit, audit whether the target horizon or
input information is mismatched. The next step should first inventory prior
horizon experiments to avoid repeating them, then freeze a small pure-direction
multi-horizon information comparison only for genuinely untested horizons.
Any future adoption still requires untouched forward data.

## Verification

Verification independently rebuilt H60 labels and causal indices, replayed all
2,520 inner state-block measurements and outer measurements, reconciled every
selected-feature AUC with sklearn, repeated state selection and the seeded
10,000-resample bootstrap, and checked hashes. Result: `PASS`.

Pandas emitted a future-compatibility warning about `None` versus `NaN` during
saved-table comparison; current tables matched and verification passed. The
frozen runner was not modified after execution.
