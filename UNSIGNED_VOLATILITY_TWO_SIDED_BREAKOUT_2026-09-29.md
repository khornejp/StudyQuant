# Unsigned-volatility two-sided breakout backtest plan

Status: Stage 1 design accepted and frozen on 2026-09-29 Asia/Seoul. Stage 2
and Stage 3 remain unauthorized. No payoff computation is authorized by this
freeze.

## Decision and scope

The prior reading is substantially correct. The old experiment fixed direction
as `-sign(prior 15m)` and let the unsigned forecast decide only whether that
fixed fade traded. Its realised-excursion oracle therefore measures the value
of perfect size information for that fade/terminal-exit pairing. It does not
bound every use of an unsigned forecast.

Two qualifications are required.

1. Oracle D10 losing under both fade sides supports average continuation at the
   H15 terminal close on these origins. Excursion itself contains neither sign
   nor path order, so it does not establish that every large move continues.
2. The reported +2.358 bps is the best observed decile cell, not a mathematical
   upper bound even for every possible selector within the old pairing.

This round tests one minimal replacement: an unsigned forecast arms a symmetric
breakout, then observed price action chooses the side. No direction forecast or
prior-return side enters the primary policy.

This redesign was chosen after inspecting results on the same 57,400 TEST
origins. Its result is therefore exploratory strategy evidence, not a pristine
confirmatory out-of-sample result. Freezing the design prevents further tuning
inside this round but cannot remove that prior exposure. No new external data
will be added to repair that limitation.

Do not run or extend aggregate PnL for the old fixed-fade design.

## Source, cutoff, and forecast input

- Market source: `artifacts/btcusdt_2020_2026h1.parquet`, Binance USD-M
  BTCUSDT one-minute OHLCV, ending 2026-06-30 23:59 UTC.
- Evaluation set: the exact 57,400 TEST origins in folds 406 through 605 from
  `out/patchtst_excursion_range_20260928/ensemble_predictions.parquet`, ending
  2025-12-30 23:30 UTC.
- Forecast input: frozen three-seed `pred_excursion_bps`. No checkpoint, fold,
  feature, calibration, or prediction is refit or selected by payoff.
- Every STOP prediction is reconstructed from the frozen checkpoints with
  `fit_missing=False`. TEST prediction values come from the frozen ensemble.
- `range_60` and realised excursion are recomputed from raw OHLCV and checked
  against the frozen forecast artifact. No old PnL or baseline value is reused.
- Required fit count: exactly zero.

Frozen hypothesis: fold-STOP top-decile unsigned-excursion states contain enough
future travel that a symmetric breakout, whose side is selected by the market,
improves conservative calendar PnL over no trade and fresh causal baselines.

## Single geometry; no sweep

### Frozen trigger decision

Use the fixed 4-bps trigger. The question in this round is: **does a high
unsigned-size forecast select states with more follow-through after the same
fixed, cost-sized displacement?** The forecast chooses when to arm; observed
price action chooses direction at a common distance. This deliberately does
not test follow-through per unit of predicted travel.

A proportional trigger such as `c * pred_excursion_bps` is rejected for this
round. It would keep trigger rates more nearly constant across the predicted
size distribution and would ask a different question. Running it beside the
fixed trigger would create a post-hoc geometry sweep on the same origins.

Mean observed `|H15|` travel is 16.38 bps, so the fixed trigger may be reached
on most armed origins. If so, this policy is substantively a first-move side
picker inside a forecast gate, not a selector of rare large breakouts. That is
an intended, falsifiable interpretation rather than a reason to change the
geometry. Stage 1 must report the realised conservative close-confirmation
rate among PatchTST fold-STOP-q90-gated TEST origins, before any Stage 2 payoff
is authorized.

Let `C_t = close[t]`, known before any order may fill. Let the fixed round-trip
cost be `c = 4 bps`, equal to maker 0.0200% per leg with no rebate. Define:

```
upper_t = C_t * (1 + 4 / 10000)
lower_t = C_t * (1 - 4 / 10000)
```

The 4-bps trigger is cost-anchored, not selected from prior breakout results.
The arm lasts only through bar `t+15`, matching the forecast horizon. There is
no trigger grid, hold grid, gate grid, barrier scaling, TP, SL, trailing stop,
or rerun at a nearby value. The previously reported 25-cell breakout sweep is
motivation only; none of its values or results enters selection or a baseline.

This is the smallest linear-futures policy that removes the fixed fade side.
It does not create a pure absolute-move payoff. A linear futures position still
needs a path rule, and profit after entry still needs follow-through. The oracle
phases below test that missing bridge. Options, simultaneous long/short
positions, and synthetic straddles are outside this dataset and scope.

## Two execution views

Both views use information available only after `close[t]`, hold at most one
position, exit no later than `close[t+15]`, subtract exactly 4 bps once for a
completed round trip, and assign zero to an unfilled arm or abstention.

### Conservative primary execution

For `k = 1, ..., 14`, inspect completed closes in time order.

```
first k with close[t+k] >= upper_t  -> side = +1
first k with close[t+k] <= lower_t  -> side = -1
entry = open[t+k+1]
exit  = close[t+15]
gross_bps = side * (exit / entry - 1) * 10000
net_bps   = gross_bps - 4
```

If no completed close confirms either boundary by `t+14`, no trade occurs.
A boundary first confirmed at `t+15` cannot be entered before the horizon and
also produces no trade. A close cannot confirm both disjoint boundaries. This
view rejects wick-only touches, removes intrabar order inference, and charges
the observed next-open gap or reversal. It is the only execution view allowed
to support `FORECAST_HELPS`.

The 4-bps fee is the requested accounting contract, not evidence that a live
breakout order would receive maker treatment. This remains an OHLC execution
proxy, with no live-order claim.

### Optimistic trigger-fill bound

For `k = 1, ..., 15`, use the first bar whose high reaches `upper_t` or low
reaches `lower_t`. Fill exactly at the touched boundary and exit at
`close[t+15]`. If both boundaries are first touched in the same minute, choose
the side with the higher terminal payoff. This is explicit future-favourable
tie resolution and an upper bound, not an execution model.

Report separately what separates the two views:

- wick-only triggers rejected by close confirmation;
- first-touch bars that hit both boundaries;
- level-to-next-open entry gaps and sign reversals;
- triggers first observed on `t+15`;
- PnL contribution of each category.

## Arming rule and arms

For each fold and each size source, compute the source's 90th percentile from
that fold's STOP origins only. TEST passes when `source >= frozen STOP q90`;
ties pass. No TEST value sets or moves a threshold. The q90 gate is frozen from
the requested high-predicted-excursion hypothesis; no alternate selectivity is
evaluated.

Recompute every arm on the same raw OHLCV and 57,400-origin calendar:

1. **No trade:** zero at every origin.
2. **Always armed breakout:** same two execution views, no size gate.
3. **`range_60` breakout:** causal `range_60`, fold-STOP q90 gate.
4. **Realised-excursion oracle breakout:** exact future H15 excursion,
   fold-STOP q90 gate. This is noncausal. It bounds perfect target ranking for
   this fixed breakout policy, not every size-based strategy.
5. **PatchTST breakout:** frozen `pred_excursion_bps`, fold-STOP q90 gate.
6. **Fade comparator:** recompute `-sign(prior 15m)` fresh. For every diagnostic
   conditioned on upper/lower breakout side, also force the fade side on the
   same armed origins and, for the matched comparison, the same conservative
   trigger time and entry price. Direction-conditioned breakout cells never
   stand without this comparator and never select a parameter.

For the oracle audit, also report a labelled non-executable travel ceiling:
choose the better future side and best future exit after the 4-bps boundary,
then subtract 4 bps. This is a headroom ceiling only and is never a verdict arm.

## Stage 1: ordering audit, then stop

The first executable invocation writes only an ordering audit. It must not
construct an aggregate strategy PnL vector.

For PatchTST, `range_60`, and realised excursion, derive 10%, ..., 90% cut
points from each fold's STOP distribution and assign TEST deciles with
`searchsorted(cuts, value, side="right") + 1`. Retain duplicate cut points and
empty cells.

Report pooled and per-fold cells with:

- count, source mean, and realised-excursion mean;
- mean absolute H15 terminal return;
- optimistic touch rate and conservative close-confirmation rate;
- time to first touch or confirmation;
- upper, lower, dual-touch, wick-only, and final-bar shares;
- probability that realised excursion reaches 4 bps;
- non-executable oracle travel ceiling before and after the 4-bps cost.

Also report the pooled realised conservative close-confirmation count and rate
inside the PatchTST fold-STOP q90 gate. Label the primary-policy interpretation
`first_move_side_picker` when this rate is at least 80%; otherwise label it
`selective_fixed_distance_breakout`. This label is descriptive and cannot alter
the trigger, gate, later verdict, or phase authorization.

No gross trade return, net trade return, calendar PnL, bootstrap, or strategy
verdict is computed in Stage 1.

Frozen ordering falsifier: PatchTST realised-excursion means must be
nondecreasing from D1 through D10, D10 must exceed D1, and the conservative
confirmation rate in D10 must exceed D1. Failure returns
`TRAVEL_ORDERING_FAIL`; no threshold, geometry, or execution rule may change.

Write, hash, verify, and report Stage 1 before authorizing Stage 2.

## Stage 2: oracle headroom and fresh baselines, then stop

After explicit approval, compute only no trade, always armed, `range_60`,
realised-excursion oracle, and matched fade. PatchTST aggregate PnL remains
uncomputed.

Each arm produces one 57,400-row calendar vector. A row contains net PnL only
when the gate passes and a trade fills; otherwise it is exactly zero. Report
trade count, fill rate, gross, cost, net per trade, mean calendar net, win rate,
profit factor, additive maximum drawdown, fold/month results, and paired deltas.

Use a deterministic circular moving-block bootstrap over 200 ordered folds:
block length 10 folds, 10,000 resamples, seed 20260929. Report two-sided 95%
intervals for paired mean-calendar-PnL differences.

Falsifiers:

- If the optimistic realised-excursion oracle does not have a lower 95% bound
  above zero versus no trade, return `BREAKOUT_NO_HEADROOM`.
- If optimistic headroom exists but the conservative oracle's lower 95% bound
  is not above zero versus each of no trade, always armed, `range_60`, and
  matched fade, return `EXECUTION_DEPENDENT_NO_ROBUST_HEADROOM`.
- Only a conservative oracle pass authorizes Stage 3. Point estimates or the
  optimistic bound cannot authorize it.

Write, hash, verify, and report Stage 2 before authorizing Stage 3.

## Stage 3: frozen forecast evaluation

After separate explicit approval, compute the PatchTST arm without changing
any prior file, hash, threshold, or rule.

Return `FORECAST_HELPS` only if the PatchTST conservative arm's lower 95% paired
interval is above zero versus each of no trade, always armed, `range_60`, and
matched fade. Otherwise return `FORECAST_DOES_NOT_HELP`. Oracle pass remains a
prerequisite. Optimistic results, isolated folds, side cells, or a positive
point estimate cannot rescue failure.

## Sequential and accounting invariants

- Origins remain 15 minutes apart.
- A conservative position enters no earlier than `open[t+2]` and exits at
  `close[t+15]`; the next origin can enter no earlier than `open[t+16]`.
- An optimistic position starts within `t+1..t+15` and exits at
  `close[t+15]`; it cannot overlap the next origin's entry.
- At most one position exists. No pyramiding, opposite-side hedge, or second
  trigger is allowed.
- Unarmed, unconfirmed, ambiguous-conservative, and abstaining origins are zero
  in calendar PnL.
- No slippage debit, funding, leverage, compounding, liquidation, or intrabar
  mark-to-market is added. Entry-gap effects are included through observed
  conservative entry prices.
- All required timestamps and OHLC prices must be finite, positive, consecutive
  one-minute observations. Otherwise abort without changing the origin set.

## Phase 0: allowed local patterns

Use these existing local contracts instead of inventing replacements:

- hash, atomic write, manifest, 3 GiB RSS, STOP-only deciles, market alignment,
  frozen STOP inference, and zero-fit verification from
  `out/run_unsigned_volatility_abstention_backtest.py`;
- target/fold definitions and frozen checkpoint inference from
  `out/run_patchtst_excursion_range.py`;
- post-entry gap, barrier, and timeout conventions as reference from
  `btcusdt_quant/artifact_audit.py` and `btcusdt_quant/backtest.py`;
- first-touch time-order loop as reference from
  `btcusdt_quant/short_direction.py`.

Do not reuse `calendar_net()` or `_cell()` from the old unsigned-abstention
runner because both embed the fixed fade pairing. Do not import the generic
`btcusdt_quant.backtest` cost constant because it documents a different venue.
No existing helper implements the paired optimistic/conservative two-sided
entry contract, so add one small local state function rather than generalizing
the production backtester.

## Build phases after approval

### Phase A: minimal runner and contract test

Add only:

- `out/run_unsigned_volatility_two_sided_breakout.py`;
- `tests/test_unsigned_volatility_two_sided_breakout.py`;
- `out/unsigned_volatility_two_sided_breakout_20260929/` phase outputs.

Copy the provenance/alignment/inference patterns listed in Phase 0. Add one
small breakout resolver shared by every arm. Do not modify the old runner,
forecast checkpoints, ensemble, or market data.

The focused test must cover signal timing, STOP-q90 ties, TEST-threshold
isolation, upper/lower symmetry, wick-only rejection, next-open entry, final-bar
no-fill, optimistic dual-touch upper-bound label, one 4-bps debit, abstention
zeros, no overlap, matched fade, oracle noncausality, phase refusal, manifest
mutation refusal, and zero fit.

Anti-pattern guards: no parameter grid, TEST tuning, model fit, checkpoint
write, generic execution abstraction, old-PnL import, or optimistic-primary
verdict.

### Phase B: Stage 1 only

Freeze plan/source/input hashes. Run tests. Run the ordering-audit invocation,
verify it with zero fits, report it, and stop.

### Phase C: Stage 2 only

Only after approval, validate Stage 1 hashes, run oracle/baseline headroom,
verify every calendar vector and interval, report it, and stop.

### Phase D: Stage 3 only

Only after approval and oracle pass, validate all earlier hashes, run PatchTST
aggregate evaluation, verify it, report the verdict, and stop.

## Manifest and resource contract

The manifest records source, timestamp, data cutoff, TEST cutoff, frozen
hypothesis, plan hash, runner/test hashes, every imported local source, market
hash, forecast manifest/ensemble/hash indexes, all transitive checkpoint and
prediction hashes, phase authorization, and result hashes.

`--verify` reconstructs only the highest authorized phase and refuses mutation
or a missing prerequisite. It calls no fit path. Checkpoints load sequentially
and are released after inference. Abort above 3 GiB peak process RSS.

Every phase reports:

```
new_model_fits: 0
old_design_aggregate_pnl_computations: 0
new_orders: 0
```

No external data, authenticated exchange action, wallet action, or live order
is permitted.
