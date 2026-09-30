# Unsigned-volatility abstention backtest preregistration

Frozen on 2026-09-29 (Asia/Seoul), before implementation and before any new
backtest. This plan uses the completed PatchTST excursion forecast as an input.
It does not refit, tune, or select forecast folds. No result from an earlier
trading experiment is a baseline or an input.

## Source, cutoff, and frozen hypothesis

The sole market-data input is
`artifacts/btcusdt_2020_2026h1.parquet`: Binance USD-M BTCUSDT one-minute OHLCV,
ending 2026-06-30 23:59 UTC. The evaluated origins are exactly the 57,400 TEST
origins in
`out/patchtst_excursion_range_20260928/ensemble_predictions.parquet`, covering
folds 406 through 605 and ending 2025-12-31. No external data is collected.

Frozen hypothesis: the rank of the unsigned H15 excursion forecast can improve
the calendar PnL of the fixed prior-15-minute fade by abstaining when expected
movement is low. The forecast supplies size only. Direction, execution, cost,
and PnL are introduced only here.

## Strategy choice

Build rank-only volatility abstention, not volatility-scaled barriers, hold
time, or maker quotes.

- `excursion` is the applicable head because it measures the maximum one-sided
  travel available to one directional position. `range` includes travel on both
  sides and is not used to set a one-position decision.
- A 15-minute forecast does not identify a time-to-travel curve, so a variable
  hold would extrapolate information the model did not estimate.
- One-minute OHLCV cannot establish maker queue position or honest passive-fill
  probability, so it cannot support a quote-width claim.
- A barrier distance would treat a median forecast as a calibrated tail or
  touch level and would add same-bar path ambiguity. Abstention uses only the
  demonstrated ordering information.

The known multiplicative under-prediction is not recalibrated. Every size gate
is a within-fold STOP-distribution rank gate, which is invariant to a positive
multiplicative error. No TEST target, TEST calibration ratio, or TEST quantile
sets a threshold.

## Required concentration before cost

This prerequisite was computed once on the frozen 57,400 eligible TEST origins
before the ordering audit. The direction-only fade has 57,371 nonzero signals
(28,657 short, 28,714 long) and 29 exact-zero prior returns. With zero assigned
to those 29 abstentions, its unconditional calendar gross is exactly
0.618365990154 bps per origin. Clearing the frozen 4-bps round trip therefore
requires the selected set to average more than 4.000000000000 gross bps, a
6.468661057838-fold concentration over the unconditional gross. If all gross
were retained and rejected origins contributed zero, the corresponding upper
selectivity is 0.154591497538, or 15.459149754%; this is an interpretability
benchmark, not a replacement for the frozen STOP-median gate.

For the mandatory side split, short averages 0.532157488201 gross bps per
short signal and therefore needs 7.516571858311-fold concentration (13.303937205%
implied upper selectivity). Long averages 0.705027885194 gross bps per long
signal and needs 5.673534457292-fold concentration (17.625697130% implied upper
selectivity). No audit result may change these break-even requirements or the
gate after the fact.

## Frozen direction and execution

For every TEST origin `t`, form the direction only after bar `t` closes:

```
prior_15m(t) = close[t] / close[t-15] - 1
short signal = prior_15m(t) > 0
long signal  = prior_15m(t) < 0
```

Thus the two side-specific cells are exactly the required
`-sign(prior 15m)` baseline split. Short is the primary result. Long is run and
reported separately and cannot rescue a failed short result. If the prior
return is exactly zero, both sides abstain.

Execution is frozen as follows:

1. Signal after `close[t]` is known.
2. Enter one unit of notional at `open[t+1]`.
3. Exit at `close[t+15]`.
4. Gross basis-point return is
   `side * (close[t+15] / open[t+1] - 1) * 1e4`.
5. Net basis-point return is gross return minus exactly 4 bps: 2 bps per leg,
   Binance USD-M maker 0.0200% times two, with no rebate.

The forecast and execution have a frozen reference-point mismatch. Forecast
excursion measures travel from `close[t]` over bars `t+1..t+15`, while trading
PnL starts at `open[t+1]`. Across the 57,400 origins,
`open[t+1]/close[t]-1` has signed mean -0.000035240714 bps, mean absolute size
0.009040050192 bps, 99th-percentile absolute size 0.103620318176 bps, and
maximum absolute size 3.589283425203 bps. Changing the PnL denominator from
`close[t]` to the frozen `open[t+1]` changes mean fade gross by -0.000216995213
bps. The mismatch is immaterial in the mean and at the 99th percentile relative
to 4 bps, but the 3.589-bps maximum is material for a rare individual origin;
it is disclosed, not corrected or recalibrated.

No slippage, funding, leverage, compounding, liquidation, or inferred intrabar
path is added. The observed bar open and close are fill proxies, not a live-fill
claim. Every required timestamp and price must be finite, positive, and exactly
one minute aligned; otherwise the run aborts rather than changing the origin
set.

Origins are 15 minutes apart. The runner must assert that every position exits
before the next position on the same side-independent calendar can enter. One
position at a time is therefore enforced, not approximated. Every abstention
contributes exactly zero to calendar PnL.

## Frozen size rule and comparison arms

For each fold and each size source, compute that source's median on that fold's
STOP origins. A TEST origin passes when its source value is greater than or
equal to the frozen STOP median. Ties pass. This canonical half-sample split has
no tuned percentile or PnL-selected parameter.

Threshold selection order is fixed: first compute and freeze each deployed
median from that fold's STOP source distribution; only then apply that numeric
threshold to TEST. TEST deciles never choose, move, validate, or replace the
deployed threshold. The complete TEST decile table is reported only as an
ordering diagnostic and is not a selector, coverage optimizer, or rerun trigger.

The arms, all evaluated on the same 57,400 TEST origins, are:

1. **No trade:** zero PnL at every origin.
2. **PatchTST abstention:** source is the three-seed ensemble
   `pred_excursion_bps`. TEST values come from the frozen ensemble parquet.
   STOP values are reconstructed by inference from the three frozen fold
   checkpoints, then averaged. No fit is allowed.
3. **`range_60` abstention:** replace the model source with
   `(max(high[t-59:t+1]) - min(low[t-59:t+1])) / close[t] * 1e4`; use its own
   fold-STOP median. Direction and execution are unchanged.
4. **Realised-excursion oracle abstention:** replace the source with the exact
   realised H15 `excursion(t)` and use the fold-STOP realised-excursion median.
   TEST selection sees future size and is noncausal by definition. It bounds
   the value of perfect size information for this fixed policy; it is not
   promised to be a mathematical PnL upper bound.
5. **Direction-only baseline:** the same short or long fade without a size
   gate. Execution and cost are unchanged.

No arm changes direction. No arm selects folds. No arm uses the `range` head,
pair gap, or any archived experiment.

## Ordering audit before aggregate PnL

For PatchTST, `range_60`, and oracle separately, form nine cut points from that
fold's STOP source distribution at 10%, 20%, ..., 90%. Assign each TEST value
with `1 + searchsorted(cut_points, value, side="right")`. Duplicate cut points
are retained and empty TEST cells are reported, not repaired from TEST data.

For short and long separately, report pooled and per-fold TEST cells with:

- origin count and directional-signal count;
- mean source size and mean realised excursion;
- mean absolute terminal return;
- mean gross and 4-bps-net return when the directional signal exists;
- net win rate and the share whose gross return clears 4 bps;
- calendar contribution with non-signals represented as zero.

The first executable phase writes `ordering_audit.parquet` and
`ordering_audit.json`, hashes them, and stops. It must not compute or print
aggregate arm PnL. The plan, sources, manifest, and decision rules cannot change
after this audit. Aggregate evaluation is a separate invocation that first
validates the audit hashes.

## Aggregate report

For each side and arm, construct one 57,400-row calendar vector. A row contains
the 4-bps-net return only when both the direction and size gate pass; otherwise
it is zero. Report:

- total and mean calendar net bps;
- gross bps, paid cost, trade count, participation, mean net bps per trade,
  win rate, and profit factor;
- additive-equity maximum drawdown;
- per-fold and UTC-calendar-month calendar PnL;
- paired per-origin and per-fold deltas against no trade, `range_60`, oracle,
  and direction-only.

Uncertainty uses a deterministic circular moving-block bootstrap over the 200
ordered folds: block length 10 folds (about 30 calendar days), 10,000 resamples,
seed 20260929. Report two-sided 95% intervals for each paired mean calendar-PnL
difference. No bootstrap result changes a parameter or causes a rerun.

## Frozen falsifier and verdicts

The primary verdict is short-only. Long receives the same separate diagnostics
and verdict but cannot overturn it.

First test whether this fixed abstention policy has size-information headroom.
If the oracle's lower 95% paired interval is not above zero against each of no
trade, `range_60` abstention, and direction-only, return
`SIZE_POLICY_NO_HEADROOM`. In that case this policy cannot test forecast value,
so the forecast is not credited or blamed.

Only when oracle headroom exists, return `FORECAST_HELPS` if the PatchTST arm's
lower 95% paired interval is above zero against each of no trade, `range_60`
abstention, and direction-only. Otherwise return `FORECAST_DOES_NOT_HELP`.
This is the preregistered falsifier: a positive point estimate, better
Spearman, higher per-trade return, or a favorable isolated fold is insufficient.

The ordering audit is reported before these verdicts but is descriptive; it
cannot alter the frozen median gate or verdict rule.

## Build, manifest, verification, and resource contract

The later build is limited to:

- `out/run_unsigned_volatility_abstention_backtest.py`;
- `tests/test_unsigned_volatility_abstention_backtest.py`;
- `out/unsigned_volatility_abstention_backtest_20260929/` outputs.

Before the ordering audit, write a SHA-256 manifest covering the plan and plan
hash, runner, test, every imported local source, the OHLCV parquet, and all
forecast artifacts used. Forecast coverage is compact but transitive: directly
hash the forecast `manifest.json`, `ensemble_predictions.parquet`,
`checkpoint_sha256.json`, and `output_sha256.json`; validate every file digest
listed by the two forecast hash indexes, including all 600 checkpoints. Mutable
forecast `status.json` and `verification.json` are excluded and never used.

The tests must cover causality/index alignment, exact 4-bps cost, short/long
separation, median-gate ties, STOP-only deciles, abstention zeros, sequential
non-overlap, oracle noncausality labeling, verdict falsifiers, manifest refusal
after mutation, and zero-fit verification.

`--verify` validates all hashes and reconstructs every output authorized for the
current phase. Before aggregate approval it reconstructs STOP inference and the
ordering audit only, compares them with the frozen outputs, and must not build an
aggregate arm-PnL vector. After a separate explicit aggregate approval it also
reconstructs every calendar vector, metric, bootstrap interval, and verdict.
It must call no fit path. The ordering-audit verification reports:

```
new_model_fits: 0
new_backtests: 0
new_orders: 0
aggregate_pnl_computations: 0
```

Print cumulative peak process RSS after artifact validation, STOP inference,
ordering audit, aggregate reporting, and verification. Abort above 3 GiB.
Checkpoint inference must be sequential and release each model before loading
the next. No live orders, authenticated exchange actions, or new data are
permitted.
