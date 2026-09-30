# 2026 H1 frozen evaluation

Frozen: 2026-08-18, before this evaluation is run.

## Scope and status of the window

Evaluate **only** 2026-01-01 through 2026-06-30 (both dates inclusive).
The four completed arms all used `--training-end 2025-12-31`; thus this is
out of sample for model fitting.  Funding and premium-index archives cover the
period, so the selected source-backed arm has train/serve source parity.  No
data after 2026-06-30 may be supplied or used: it is reserved for the live
transition.

This is **not a pristine researcher holdout**.  `PREREGISTERED_HOLDOUT_2026-08-10.md`
previously read a longer, overlapping window (2025-01-01 through 2026-06-30)
and returned `INCONCLUSIVE` at 50 trades under its then-100-trade floor.
Those numbers were seen.  No configuration was changed because of them.  This
freeze is therefore a fixed, model-OOS evaluation of the present rule, not an
unseen-window edge claim.

## One arm, chosen now

The sole arm is **S4-A**:
`artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix/model.json`.

It is the source-backed 45-bar model with TP 0.4% and SL 0.2%.  It is selected
before the 2026-H1 result and from recorded design facts, not from this
evaluation: it is the source-parity arm, and its 2:1 gross barrier geometry
requires a 40.0% net-cost break-even TP hit rate, versus 55.0% for the
0.4%/0.4% arm.  The stage-4 rerun record also makes it identifiable as S4-A;
the other three arms are not run or compared after this result.  This is a
single-arm test, not a new source or geometry selection exercise.

## Frozen trading rule

* **Model and data:** the S4-A artifact above; the canonical candle parquet,
  metrics archive, funding archive, and premium-index archive named in the
  command below.
* **Geometry and horizon:** fixed TP `0.004`, fixed SL `0.002`, and 45 one-minute
  bars.  The execution barriers equal the training-label barriers.
* **Gate:** admit a candidate only when `rv_60 >= 0.0013057161122560501`.
  This is reused exactly from S4-A's recorded fold-0 training-slice 0.80
  quantile (`run_summary.json`), not recomputed on 2026.  A new evaluation-window
  quantile would let the evaluated window choose its own gate.
* **Entry threshold:** `0.40` (`--long-threshold 0.40`).  This is the fixed
  40.0% net-cost barrier break-even probability for this 0.4%/0.2% geometry,
  used as a rule rather than fitted to 2026 H1.  It is therefore a defensible
  final-model cutoff even though S4-A does not persist a final-refit
  `selected_thresholds` value.  The four persisted fold thresholds (`0.3928`,
  `0.4039`, `0.4001`, `0.4045`; median `0.4020`) remain validation-only choices
  for their respective fold fits, and are not being selected among or optimized
  on this window; their close agreement with the pre-existing 0.40 barrier
  rule is corroboration, not the selection procedure.

  The original proposed balanced-profile default, `0.50`, is expressly
  rejected as unreachable.  In S4-A's pre-evaluation,
  training-period `fold_test_predictions.csv` (1,326,240 rows), the maximum
  probability is `0.4609` (p99.9 `0.4386`, p99 `0.4208`, p95 `0.4062`, median
  `0.3702`): 116,317 rows, or **8.770%**, are at least `0.40`; 180 (0.014%)
  are at least `0.45`; and zero are at least `0.50`.  Thus `0.50` would
  guarantee no recorded historical entries and make this evaluation incapable
  of measuring the rule.  The fixed `0.40` admits 8.770% of those
  training-period rows before the separately frozen volatility gate and
  execution constraints.  The 2026-H1 admission count may differ.

  The artifact did fit beta probability calibrators on purged walk-forward
  folds (recorded mean test Brier `0.23323`, ECE `0.00607`), so scores near
  `0.40` have historical binary-label calibration support.  That does **not**
  establish that `0.40` is an economic decision boundary: calibration concerns
  the binary TP-before-SL label, while realized economics also depend on
  limit fills, timeouts, fees, the gate, and distribution shift.  The rule is
  frozen on that limited basis; the evaluation's net-bps result remains the
  economic measurement.
* **Direction and sizing:** long-only; fixed `0.10` equity fraction per filled
  trade.  No Kelly sizing.
* **Execution and costs:** a resting limit entry may fill only in the following
  five bars at a touch (no penetration buffer); all exits (TP, SL, timeout, and
  open-at-end) are resting limits.  Both legs use the unchanged maker fee of
  `0.0002`, no slippage: `0.0004` round trip.  This is the project's
  limit-only premise, not a taker or slippage sensitivity run.

The range gate and every other CLI default remain at their existing defaults;
this command changes only the explicitly frozen entry threshold and does not
change TP, SL, horizon, gate, or cost defaults.

## Reading rule

There is **no minimum-trade-count branch** and no `INCONCLUSIVE` result due to
count.  A selective gate yielding few trades is an observed property of the
rule, not a failed apparatus.

Report, for all filled long trades in the full window:

1. trade-weighted net bps per trade;
2. trade count;
3. TP hit rate, `TP exits / (TP exits + SL exits)`, with a two-sided 95% Wilson
   interval; also report timeout and open-at-end counts separately; and
4. the 40.0% net-cost barrier break-even rate alongside that hit rate.

The hit rate is a geometry diagnostic; it does not replace net bps because
timeout settlement occurs at the horizon close.  A result **fails the frozen
rule** if there is at least one filled trade and full-window trade-weighted net
bps per trade is less than or equal to zero.  It survives this specific
evaluation only if that number is positive.  With zero filled trades, report
zero trades and unavailable hit-rate/net-bps statistics; this is neither a
count-based failure nor evidence that the rule earns a return.

Regardless of outcome, this evaluation cannot establish a generalizable edge,
live fill probability or queue priority, resilience to fees/slippage outside
the limit-only premise, performance after 2026-06-30, a two-sided strategy, or
independence from the already observed overlapping 18-month window.  It does
not authorize a rerun with another arm, threshold, gate, geometry, cost,
horizon, or subset of this window.

## Exact command — do not run until review is complete

```powershell
venv_btcusdt/Scripts/python.exe -m btcusdt_quant backtest --input artifacts/btcusdt_2020_2026h1.parquet --metrics-dir artifacts/metrics --funding-dir artifacts/funding_2020_2026h1 --premium-index-dir artifacts/premium_index_2020_2026h1 --model-artifact artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix/model.json --output artifacts/frozen_evaluation_2026_h1_s4a --backtest-start 2026-01-01 --backtest-end 2026-06-30 --horizon 45 --exec-tp-pct 0.004 --exec-sl-pct 0.002 --fixed-tp-sl --tp-floor 0.004 --sl-floor 0.002 --vol-gate-feature rv_60 --vol-gate-min 0.0013057161122560501 --long-only --long-threshold 0.40 --position-size 0.1 --maker-fill-window 5 --maker-fill-penetration-bps 0 --maker-exit
```

Do not alter or remove `--long-threshold 0.40`, or append
`--entry-quantile`, `--threshold-floor`, `--vol-gate-train-quantile`, or any
post-2026-06-30 input.
