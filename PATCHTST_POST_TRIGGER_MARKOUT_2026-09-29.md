# PatchTST post-trigger signed-markout preregistration

Status: design-only preregistration, revised and re-frozen on 2026-09-29 13:48
Asia/Seoul before any exploration outcome was computed.
No exploration, confirmation, model fit, or outcome calculation has been run
under this plan.

## Prior decision and scope

`TRAVEL_ORDERING_FAIL` from the prior two-sided-breakout plan stands unchanged.
This plan cannot overturn that result, authorize its Stage 2, or reuse its strict
nine-adjacent-monotone gate. Prior experimental results are discarded and are
not baselines here.

The new question is narrower: after a fixed observed displacement, is the
signed movement in the crossing direction positive, and does that post-trigger
movement increase with the frozen unsigned PatchTST size forecast? Realised
excursion includes pre-trigger travel and therefore cannot answer this question.

This is a fixed-horizon markout study, not PnL or an execution backtest. There
is no cost, fill model, order, wallet action, authenticated exchange action, or
live-trading claim.

## Source, audit timestamp, and cutoff

- Source: `artifacts/btcusdt_2020_2026h1.parquet`, Binance USD-M BTCUSDT
  one-minute OHLCV.
- Source SHA-256:
  `6ad4dba7c55550e380426b4397b55dfbea3bcb318e37632971d82cad8cf6ada4`.
- Data cutoff: `2026-06-30T23:59:00+00:00`.
- Source audit time: `2026-09-29T13:40:01+09:00`.
- The exact half-open confirmation interval `[2026-01-01, 2026-07-01)`
  contains 260,640 unique, consecutive one-minute bars. The supplied 262,109
  count is not reproduced by the frozen local source and is not used.
- No external data will be collected.

Frozen hypothesis: on the current lineage's untouched 2026 H1 forecast span,
the selected fixed displacement has positive PatchTST-q90 calendar markout,
and raw post-trigger signed markout has a positive global within-fold trend
against frozen predicted-size decile.

## Frozen model, cadence, and prediction

The model and feature contract are exactly those in
`out/patchtst_excursion_range_20260928/manifest.json`, whose SHA-256 is
`a9d1907bb0d95f15afabfd811f40d91bd0af16d06565b048927e160bfa9ca073`:

- the same two-head PatchTST architecture, inputs, target definitions, loss,
  optimiser settings, early stopping, and seeds `42, 43, 44`;
- rolling 180-day TRAIN, 3-day STOP, and 3-day TEST windows;
- 15-minute origin spacing and `H = 15` one-minute bars;
- predicted size is only the three-seed mean `pred_excursion_bps`; the range
  head is not an alternative prediction;
- per-fold STOP-only thresholds and deciles; no TEST or confirmation value sets
  a threshold.

For each fold, form the ensemble STOP distribution of
`pred_excursion_bps`. Its linear 10%, ..., 90% quantiles define decile cuts.
Assign TEST values with `searchsorted(cuts, value, side="right") + 1`, retaining
duplicate cuts and empty cells. The PatchTST gate is
`A_patch = 1{pred_excursion_bps >= STOP q90}`; ties pass. This is the frozen q90
definition. No alternative gate or `c` is allowed.

The proposed absolute gate `pred_excursion_bps > 4` is rejected as a no-op,
not tested as an alternative. The user-reported zero-fit audit on the same raw
source placed predicted-excursion deciles between 12.1 and 38.0 bps, so even D1
clears 4 bps. The distribution-relative STOP q90 gate above remains unchanged.

The same audit, reported on 2026-09-29 before this revision and before this
plan's exploration, found negative H15 gross markout for unconditional
`continuation_1m` (-0.2437 bps), `continuation_5m` (-0.3730 bps), and
`ema5_over_ema20` (-0.4586 bps), while `fade_15m` was positive (+0.4415 bps).
In the causal trailing-volatility top decile their signs strengthened rather
than reversed: -0.8100, -1.1367, -1.2915, and +1.3116 bps respectively. These
numbers motivate two added descriptive baselines but are not imported into any
result, selector, or gate.

## Frozen markout outcome

Only completed one-minute closes are used. This avoids inventing intrabar order
when a one-minute high and low cross both levels. For origin `t`, let
`C_t = close[t]` and, for `k = 1, ..., 15`, define

```
d_i(k) = 1e4 * log(close[t+k] / C_t)
tau_i(X) = min{k : |d_i(k)| >= X}
s_i(X) = sign(d_i(tau_i(X)))
P_tau_i = close[t + tau_i(X)]
P_H = close[t + 15]
Z_i(X) = 1{tau_i(X) <= 15} * s_i(X) * 1e4 * log(P_H / P_tau_i)
```

If no completed close crosses by `t+15`, set `Z_i(X) = 0`. A crossing first
seen at `t+15` is a realised trigger and has `Z_i(X) = 0` by definition. Every
eligible origin remains in the vector; there is no conditioning on triggering.
There is no intrabar touch variant, barrier outcome, alternate horizon, or
additional outcome.

The user-fixed trigger family is exactly `X in {10, 20, 30, 50}` bps. It is an
acknowledged four-value sweep. Exploration reports all four in fixed numeric
order and may not omit, replace, or rerun a value after inspection.

## Realised-rate contract and trigger selection

For each trigger define its PatchTST-q90 realised rate as

```
r_X = count(A_patch = 1 and tau_i(X) <= 15) / count(A_patch = 1)
```

The admissible band is fixed separately for every trigger:

| X (bps) | admissible q90 realised rate |
|---:|---:|
| 10 | 20.00% to 60.00%, inclusive |
| 20 | 20.00% to 60.00%, inclusive |
| 30 | 20.00% to 60.00%, inclusive |
| 50 | 20.00% to 60.00%, inclusive |

The common band requires at least about 1,100 exploration triggers at the
expected q90 sample size while rejecting a nearly-always-on trigger. A trigger
outside its band ends permanently; it cannot motivate a nearby replacement.

The one confirmation trigger is chosen without reading any `Z` value:

1. discard triggers whose exploration `r_X` is outside its fixed band;
2. among survivors, choose the trigger minimizing `|r_X - 0.35|`;
3. an exact tie selects the larger `X`;
4. if none survives, return `NO_CONFIRMATION_TRIGGER` and do not fit or run
   confirmation.

Every exploration `Z` result remains sealed until this rate-only choice and its
input counts are written and hashed. Selection therefore does not use the
outcome later tested. Carrying all four into confirmation and a family-of-four
multiplicity correction is unnecessary under this rule. The confirmation
window is nevertheless not pristine history: discarded prior work repeatedly
inspected 2026 H1. It is only untouched by folds 406--605 and the current
forecast lineage, not a claim of globally pristine holdout evidence.

The selected trigger must again have `r_X` inside `[20.00%, 60.00%]` on
confirmation. Failure returns `CONFIRM_TRIGGER_RATE_FAIL`; no replacement is
selected.

## Exploration: report only, no verdict

- Prediction span: the exact 57,400 TEST origins in folds 406--605,
  `2024-05-10` through `2025-12-30 23:30 UTC`.
- Frozen TEST prediction artifact:
  `out/patchtst_excursion_range_20260928/ensemble_predictions.parquet`, SHA-256
  `4fa6ab24d4543398d4f595b02765f904f39000a364631c4620edb88d297fa66b`.
- Existing checkpoints reconstruct ensemble STOP predictions with zero fits.
- Report all four triggers: total and q90 trigger counts/rates, mean raw `Z`,
  PatchTST-q90 calendar mean, global trend statistic and interval, decile
  counts/means, all fresh baselines, and the rate-only selection inputs.
- Label every table and machine-readable row `exploratory`.
- Exploration produces no pass/fail verdict. Its `Z` values cannot select the
  confirmation trigger, change a band, or alter confirmation rules.

## Confirmation window and fit budget

Confirmation uses origins in `[2026-01-01T00:00:00Z,
2026-07-01T00:00:00Z)`. Extend the unchanged three-day calendar through folds
`606--666`, inclusive:

- 61 folds total;
- folds 606 and 666 contribute only the in-window portions;
- 59 full folds contribute 287 complete H15 origins each;
- each boundary fold contributes 191 complete origins;
- expected confirmation origins: `59 * 287 + 2 * 191 = 17,315`;
- three seeds per fold, exactly `61 * 3 = 183` new model fits;
- one two-head fit produces the frozen excursion prediction; there is no fit
  per trigger or baseline.

No fold 406--605 contains this interval in TRAIN, STOP, or TEST. Confirmation
must not start until exploration has written and hashed the rate-only trigger
choice. Fits 606--666 may not be reused to revise that choice.

## Single confirmation test family

Let `X*` be the rate-only selected trigger. Compute raw `Z_i = Z_i(X*)` for
every confirmation origin. Define the full-calendar PatchTST vector

```
Y_patch_i = A_patch_i * Z_i
```

Thus ungated and untriggered rows are zero but remain present. Confirmation
passes only if all three gates hold:

1. `r_X*` is inside `[20.00%, 60.00%]`, inclusive.
2. `mean(Y_patch_i) > 0`. Also report `mean(Z_i | A_patch_i=1)`; it has the
   same sign but is not a separate test.
3. The one global trend slope `beta` below is positive and its frozen 95%
   two-sided fold-clustered confidence lower endpoint is strictly above zero.

For gate 3, use raw `Z_i`, not `Y_patch_i`; otherwise zeros introduced by the
q90 gate would create a mechanical trend. Fit one OLS regression over all
confirmation origins:

```
Z_i = fold fixed effect + beta * (predicted_size_decile_i - 5.5) + error_i
```

Use CR1 cluster-robust covariance by TEST fold, finite-sample correction on,
and Student-t critical value `t_(0.975, G-1)` with `G = 61` fold clusters.
The lower endpoint is `beta - t_(0.975,60) * SE_CR1(beta)`. No polynomial,
rank correlation, alternate weighting, alternate clustering, or subgroup may
replace or rescue it.

Report D1--D10 raw `Z` counts, trigger rates, and means for description only.
Adjacent monotonicity is not tested. A nonmonotone decile table cannot fail a
passing global slope, and an attractive cell cannot rescue a failed slope.

Return `POST_TRIGGER_MARKOUT_CONFIRMED` only if all three gates pass. Otherwise
return `POST_TRIGGER_MARKOUT_NOT_CONFIRMED`. The verdict comes only from 2026
H1; exploration cannot produce or rescue it.

## Fresh same-origin baselines

Recompute every baseline from the raw source on exactly the same origin rows,
selected trigger `X*`, `tau`, and horizon. No prior experimental number is
imported.

1. **No trade:** `Y_i = 0`.
2. **Always armed:** `Y_i = Z_i`.
3. **`range_60` gate:** `Y_i = A_range_i * Z_i`, where `A_range` uses that
   fold's STOP-only q90 with ties passing.
4. **Realised-excursion oracle gate:** `Y_i = A_oracle_i * Z_i`, where the
   noncausal anchored H15 realised excursion uses that fold's STOP-only q90.
   This is a labelled oracle baseline only; its pre-trigger travel cannot prove
   the breakout premise.
5. **Matched prior-15m fade:** reuse `A_patch`, `tau`, and `P_tau`, but replace
   crossing direction with
   `f_i = -sign(log(C_t / C_(t-15)))`. Report
   `Y_fade_i = A_patch_i * 1{tau_i<=15} * f_i * 1e4 * log(P_H/P_tau_i)`;
   a zero prior return gives zero.
6. **Matched prior-1m continuation:** reuse `A_patch`, `tau`, and `P_tau`, but
   replace crossing direction with
   `g_i = sign(log(C_t / C_(t-1)))`. Report
   `Y_cont1_i = A_patch_i * 1{tau_i<=15} * g_i * 1e4 * log(P_H/P_tau_i)`;
   a zero prior return gives zero.
7. **Matched EMA5-over-EMA20:** compute causal recursive close EMAs through
   origin `t`, with `alpha_s = 2/(s+1)`, `EMA_s,0 = C_0`, and
   `EMA_s,t = alpha_s*C_t + (1-alpha_s)*EMA_s,t-1`. Reuse `A_patch`, `tau`,
   and `P_tau`, replace crossing direction with
   `e_i = sign(EMA_5,t - EMA_20,t)`, and report
   `Y_ema_i = A_patch_i * 1{tau_i<=15} * e_i * 1e4 * log(P_H/P_tau_i)`;
   an exact tie gives zero.

Report count, gate rate, realised trigger rate, mean calendar markout, mean
armed markout, fold means, and paired mean deltas against PatchTST. These
baselines are descriptive and create no extra confirmation gate. No costs are
subtracted and none is called PnL.

## Freeze, phase, and safety rules

- Before any exploration result, hash this document, the future runner/test,
  market source, frozen exploration predictions, imported source files, and
  every checkpoint used.
- Exploration, rate-only selection, confirmation fits, and confirmation result
  are separate immutable phases. `--verify` must reconstruct the highest
  completed phase without a fit and refuse mutated inputs.
- The model, features, target, prediction head, seeds, fold cadence, q90,
  deciles, horizon, origin spacing, trigger family, rate band, target rate,
  tie-break, outcome, statistic, confidence rule, and baselines are frozen.
- No alternative `c`, trigger, horizon, barrier, outcome, cost, external data,
  or post-hoc subgroup is allowed.
- No phase is authorized by this document alone. The next authorized action is
  only to report this preregistration and fit count before building.

```
exploration_run: false
confirmation_run: false
new_model_fits: 0
new_orders: 0
external_data_added: 0
```
