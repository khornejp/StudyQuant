# PatchTST move-target ladder plan

Date: 2026-09-23 (Asia/Seoul)

Supersedes `PATCHTST_MOVE_TARGET_10BPS_PLAN_2026-09-22.md`, whose run was
stopped after 62 of 100 folds of its first arm. That plan changed the target and
the loss together against a blended baseline, and measurement during the run
showed its fixed 10 bps threshold fires on 57.7% of origins in folds 506-525 but
only 45.6% in folds 566-585, so accepted coverage collapsed in quiet windows for
a reason that had nothing to do with skill. Its ternary H15 checkpoints are
byte-identical to what B1 needs and are reused; nothing else from it is used.

## Objective

Find which single change, if any, moves the frozen sign classifier off the
one-line fade rule it currently reproduces
(`DIRECTION_CLASSIFIER_ECONOMIC_AUDIT_2026-09-23.md`: +1.157 bps against the
fade's +1.340 on the same bars, paired difference -0.184, t -1.26). Measure in
basis points. Do not tune after seeing results.

## The ladder

Every arm is H15 only. The H60 model and the 50:50 cross-horizon blend are held
out of this experiment. Each arm differs from the one above it by exactly one
change, so each contrast measures one thing.

| Arm | Horizon | Target | Features | Loss | Contrast |
| --- | --- | --- | --- | --- | --- |
| A0 | H60+H15 blend | sign | 35 | BCE | reference, no fits |
| B0 | H15 | sign | 35 | BCE | B0 - A0 = dropping the blend |
| B1 | H15 | ternary, fixed 10 bps | 35 | CE | B1 - B0 = the target |
| B1v | H15 | ternary, 0.5 x trailing vol | 35 | CE | B1v - B1 = the threshold rule |
| B2 | H15 | ternary, fixed 10 bps | 40 | CE | B2 - B1 = the trend features |
| B3 | H15 | ternary, fixed 10 bps | 40 | weighted CE | B3 - B2 = a magnitude-weighted loss |
| B4 | H15 | ternary, fixed 10 bps | 40 | expected bps | B4 - B2 = an objective denominated in money |
| B5 | H15 | ternary, fixed 10 bps | 40 | CE, 2 encoder layers | B5 - B2 = encoder depth |

B3, B4 and B5 are three separate answers to the same question and all hang off
B2, so none of them is a rung beneath another.

B4 replaces cross-entropy with `-(exposure * r - c * |exposure|)`, where
`exposure = p_up - p_down`. It is the only objective in this project denominated
in basis points rather than in class probability: it learns the sign and size of
the conditional mean return, weighted by how large that return is, where
cross-entropy learns a ternary posterior. The rung runs at `c = 0`, so it
measures a **gross-exposure objective** and cost is applied when scoring, which
is what the gate measures.

It does **not** produce voluntary abstention. At `c = 0` the objective is linear
in exposure and `SMALL` earns nothing, so any non-zero conditional mean return
pushes exposure to the rail; abstention can only come from the cost term.
Smoke testing with the real `c = 4.0` drove exposure to exactly zero — 279 of
279 TEST rows on fold 605 came back `SMALL`, STOP net basis points at 0.000 from
epoch 4 on. That is not a failure to be tuned away: told the round trip,
gradient descent returned the economically correct answer that the conditional
edge here is under 4 bps, which is the audit's arithmetic reached by
optimization. It is recorded as a finding and the cost-aware variant is not run
as a rung, because an arm that never trades cannot be scored against a gate
built on trade counts.

Returns are winsorized at the TRAIN 1st and 99th percentiles inside the loss
only, so one 300 bps bar cannot dominate a batch of 1024, and divided by the
winsorized mean `|r|` to keep the objective dimensionless. Scoring uses raw
returns. That is not a train/serve leak — no feature sees it — but it is a
mismatch between what is optimized and what is measured, and a tail outcome
could rank B4 differently from what its own objective preferred.

B5 stacks the frozen encoder block twice and changes nothing else: patch length,
d_model 48, four heads, feed-forward width 96, dropout 0 and the output head are
all unchanged, so the contrast is depth alone. It tests whether one transformer
layer over 48 dimensions is too small to separate signal from noise. The
measurements so far predict it will not help, since the failure is that the
model reproduces a one-line fade rule rather than that it fits that rule badly.
The result that would change that reading is B5's STOP cross-entropy falling
below the class-prior baseline of 0.943 while B2's does not.

B1v is a side branch off B1, not a rung beneath B2. The first draft of this plan
put B2 and B3 on the volatility-scaled threshold, because that rule holds the
label base rate constant across regimes (0.5863 on folds 406-505 against 0.5891
on 506-605, versus 0.5749 / 0.5018 for the fixed rule). Smoke testing on fold 605
before the run showed why that is the wrong base: with a per-row threshold the
target becomes the standardized move `|r| / vol`, which strips out the one
component the model can predict — trailing volatility forecasts `|move|` at
corr .4407 — leaving only the residual. B1v predicted `SMALL` on 273 of 279 TEST
rows and accepted nothing, and B2 on the same base predicted `SMALL` on 277 of
279. The fixed threshold's regime-dependent coverage is the same property that
makes its target learnable. The feature and loss contrasts therefore sit on the
fixed-threshold branch, and the threshold rule is still measured, by B1v - B1.

This is a pre-result design fix found by a smoke test, not a response to a gate.
No arm had been scored when it was made.

## Targets

Per origin `t`, with `forward = (close[t+15] / close[t] - 1) * 10000`:

- sign (B0): `DOWN` when `forward < 0`, else `UP`. Ties are already excluded by
  the frozen origin rule.
- ternary: `UP` when `forward >= threshold`, `DOWN` when `forward <= -threshold`,
  else `SMALL`.
  - B1: `threshold = 10.0` bps, fixed.
  - B1v, B2, B3: `threshold = 0.5 * std(logret[t-59 .. t]) * sqrt(15) * 10000`,
    a 60-bar window ending at the origin's own closed bar, so it uses no
    information later than the feature cutoff. Its median is about 9.7 bps, so
    the 10 bps intent is preserved on average while quiet windows are not
    starved.

Origins come from `horizon.endpoints` on the frozen **binary** labels, never
from the ternary array, so every arm scores exactly the rows A0 scored.

## Features

All arms use the frozen 35. B2 and B3 add five short-horizon trend channels,
computed from closed bars only and appended after the 35:

| Channel | Definition |
| --- | --- |
| `ema_5_slope` | least-squares slope of EMA(close,5) over the last 5 bars, divided by close |
| `ema_20_slope` | least-squares slope of EMA(close,20) over the last 10 bars, divided by close |
| `bb_squeeze_20` | `bb_width_20 / rolling_median(bb_width_20, 60)`, with `bb_width_20 = 4 * std(close,20) / mean(close,20)` |
| `return_sign_run_15` | `sum(sign(close.diff())) / 15` over the last 15 bars |
| `ema_gap_5_minus_15` | `short_ema_gap_5 - short_ema_gap_15`, both `(EMA - close) / close` |

The last one is a linear combination of two channels the model already has,
which would be redundant in a dense network. It is not redundant here: the
encoder is channel-independent, so a cross-channel signal that varies over the
60-bar window can never be formed before the final 32-unit bottleneck.

Nothing longer than 60 bars is added. `ema_60_slope`, `ema_gap_1h` and
`bb_width_1h` are deliberately held out.

## Loss

B0 uses binary cross-entropy. B1, B1v and B2 use unweighted three-class
cross-entropy. B3 weights each sample by `min(|r| / mean|r_train|, 4.0)`, with
the scale taken over that fold's TRAIN split only. The cap is preregistered and
is not to be tuned. B3 weights the STOP objective the same way, so that early
stopping optimizes the objective the arm is trained on.

## Accept rule

B0 keeps the frozen class-wise rule: accept when `|p_down - 0.5|` clears the
STOP-fitted 90th percentile for the predicted class. B1 onward accept when the
predicted class is not `SMALL` and its probability clears the STOP-fitted 90th
percentile of that same predicted class. A fold where STOP never predicts a
class accepts nothing of that class and is reported, not repaired.

## Scope

Folds 506 through 605 inclusive, 100 consecutive folds, 2025-06-29 through
2025-12-31, on the frozen calendar. Seven arms x 100 folds x 3 seeds = 2,100
models, of which 186 already exist for B1 and are reused by SHA.

## Primary metric and frozen gate

Gross basis points per trade on accepted rows,
`side * (close[t+15] / close[t] - 1) * 10000`. Balanced accuracy is reported and
gates nothing. An arm passes only if all hold:

1. coverage at least 2%, at least 1,200 accepted rows, at least 300 per side;
2. gross positive with t at least 2.0;
3. **gross minus the fade benchmark on the same accepted bars positive with t at
   least 2.0**, the benchmark being `-sign(close[t] / close[t-15] - 1)`;
4. gross on rows whose realized absolute move is at least 50 bps not negative;
5. gross at least 1.0 bps above A0 on the same folds.

Net of 4 bps is reported everywhere and gates nothing: this run is about what
the model learns.

**Correction, made while the run was still fitting and before any arm was
scored.** Line 1 is a deployability question — does this trade often enough to
be worth running — inside an experiment whose stated purpose is what the model
learns, and lines 2 to 5 already carry sample size through their t-statistics, so
line 1 adds nothing to significance. It also penalizes exactly the behaviour a
reject option exists for: an arm that inspects 28,389 origins and accepts 967 of
them is being selective, and the audit's own conclusion was that the selection is
where the value sits. Its threshold was never derived either — 1,200 is A0's
6,477 rescaled to 100 folds, not a power calculation.

The gate is therefore **not** relaxed, because changing a threshold after seeing
which arms miss it is the failure mode this project keeps repeating. Instead both
readings are reported for every arm: `outcome` applies the gate exactly as
declared above, and `outcome_without_count` applies lines 2 to 5 alone. Every arm
also carries a 95% interval on its gross and on its difference from the fade, so
a thin arm reads as wide rather than as silent. An arm accepting fewer than 100
rows is reported as having **declined to trade**, which is a result about the
model rather than a shortage of evidence about a strategy.

## How a thin arm is read, fixed before the numbers arrive

Taking the per-trade dispersion from the audit's own accepted set — 30.34 bps on
gross, 11.75 bps on the difference from the fade — the smallest effect each arm
can resolve at t = 2 is:

| Set | n | se | Minimum detectable |
| --- | --- | --- | --- |
| B0, B0d, B3 | ~3,100 | 0.54 | 1.08 bps |
| B1 | 967 | 0.98 | 1.95 bps |
| B2 | 950 | 0.98 | 1.97 bps |
| B1v | 285 | 1.80 | 3.59 bps |
| fade difference, B1 / B2 | 967 / 950 | 0.38 | 0.76 bps |

An arm short on trade count is then read one of three ways, and which one is
decided by its numbers, not by its size:

1. **Clears its own minimum on gross and on the fade difference.** The effect is
   real and the trade count is a deployment fact, not a scientific one. Follow up
   by widening to folds 406-605 as a separate frozen experiment — never by
   moving a threshold.
2. **Negative point estimate, or a 95% upper bound below the 4 bps cost.** A
   small sample does not protect a negative estimate; it only widens the
   interval. If even the optimistic end cannot pay the cost, the arm is
   concluded and no further folds are warranted.
3. **Between zero and its minimum detectable effect.** Genuinely inconclusive.
   Report the interval together with the minimum, say plainly that an effect this
   size cannot be resolved by this many rows, and name fold expansion as the next
   experiment.

B1v is none of these. At 285 accepted rows on 1.00% coverage the model declined
to trade, which answers the mechanism question the arm was built to ask and
would not change with more folds.

**The ladder is underpowered for its own arm-to-arm contrasts**, and this is a
property of the 100-fold scope rather than of any gate: B1 - B0d resolves only
2.23 bps, B2 - B1 only 2.77, B3 - B2 only 2.25, while the directional
information this family is known to carry is 0.5 to 1.4 bps. A contrast that
comes back insignificant is therefore reported as "below what this design can
resolve", never as "no effect". The most sensitive measurement in the run is not
a contrast at all — it is each arm's own difference from the fade, at 0.42 to
0.76 bps.

These figures assume the audit's dispersion. The final report recomputes every
minimum from each arm's realized standard error.

## Preregistered diagnostics

Per arm, gating nothing: `corr(predicted side, prior 15-minute return)` (A0 is
-0.4554), the share of accepted rows agreeing with the prior move (A0 is
0.0455), gross by realized magnitude bin, coverage, realized class balance, and
the realized threshold distribution for the volatility-scaled arms.

## Independent review before the run

Codex attacked this plan and runner on 2026-09-23, before any arm was scored. It
confirmed that `trend_features` and `vol_threshold` read no bar later than the
origin, that the winsorized scale and the magnitude weights take their scale
from TRAIN only, that the STOP quantiles are fitted on STOP, that the 186 reused
checkpoints match B1's recipe exactly and load strictly, and that B5's encoder
replacement leaves B2's initialization untouched across processes. It also
verified origin parity directly on folds 506-605: TRAIN 1,711,809, STOP 28,397
and TEST 28,389 rows, identical with and without the trend channels, zero rows
removed.

Three defects it found are fixed here. The checkpoint resolver now prefers a
file this run wrote over the stopped run's, so a file appearing later cannot
change what `--verify` rebuilds from; the resolved path and digest of every
fold, seed and arm are recorded in `checkpoints.json` and asserted on verify.
The manifest now hashes every module whose code actually executes, not only the
runner. And origin parity is asserted per fold before training rather than left
as a property that happened to hold.

One caveat stands: the arm-level contrasts compare means over each arm's own
accepted subset. They are like-for-like in population but are not paired
same-bar effects.

## Prohibited

No TP, SL or barrier. No execution model beyond the flat 4 bps used for
reporting. No backtest engine. No live order. No new calendar data. No spot
input. No threshold, cap or gate tuned after results are seen. No checkpoint
reused across a different target, feature set or loss.

Retrospective evidence on a window the project has already inspected. It
authorizes nothing.
