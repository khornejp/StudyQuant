# Zero-Fit Liquidity Markout-Horizon Sweep Preregistration

Frozen: 2026-09-28 12:15:00 KST, before measurement.

R1 control-only amendment frozen: 2026-09-28 12:34:01 KST. The first run
aborted before reports were written because its 60-second fill-state
denominator did not reproduce the supplied frozen control. No 5/10/30-second
result was inspected. R1 defines an evaluated fill as frozen fill AND valid
endpoint, and uses all origins with finite frozen raw quotes as the denominator,
matching the supplied control. A frozen fill without a valid endpoint therefore
contributes zero and is not an evaluated fill; no origin is dropped.

R2 control-only amendment frozen: 2026-09-28 12:46:29 KST. R1 aborted before
reports because retaining 77 origin-offset rows with neither side evaluable
produced `-1.0949` instead of the supplied `-1.0950` 1-bp control. No horizon
report was inspected. R2 excludes an origin-offset-horizon only when neither
side is evaluable. One evaluable side remains sufficient. This exactly states
the frozen control population without changing an observed horizon result.

Status: frozen. The SHA-256 of this file is pinned in
`btcusdt_quant/liquidity_horizon_sweep.py`. Any edit invalidates the run.

## Question and boundary

Test whether the negative two-sided raw last-trade quote value in
`out/zero_fit_target_equivalence_20260925_r1/` is caused by the frozen
60-second post-fill holding assumption. This is a zero-fit diagnostic. It does
not relax or re-run the target-equivalence gate, promote a target, fit a model,
start a full-span model study, collect data, or send an order.

Source: frozen `raw` arm outcome shards and staged public Binance USD-M
BTCUSDT `aggTrades` from the R1 run. Data cutoff: 2024-04-01 06:46:00 UTC.
Measurement window: all 322 R1 shard days, 2023-05-16 11:49:00 UTC through
the cutoff. The hypothesis came from these same shards, so this is a
confirmatory in-sample mechanism diagnostic, not an independent out-of-sample
test of predictive improvement.

Required counters are `new_model_fits: 0` and `new_orders: 0`.

## Frozen construction

Reuse every raw-arm origin, quote, side, offset, fill flag, and millisecond fill
time `tau` without rebuilding them. Offsets remain 1, 2, 5, and 10 bp. Sweep
post-fill markout horizons 5, 10, 30, and 60 seconds. For a filled side and
horizon `h`, endpoint is the first staged aggTrade at or after `tau + h`, with
delay at most 1,000 ms. Long markout is
`10000 * log(endpoint / quote)`; short markout is its sign reverse. An unfilled
side contributes zero. Per the R1 amendment, a frozen fill with no valid
endpoint is treated as an unevaluated fill and contributes zero. Include every
origin-offset pair with finite frozen long and short raw quotes and at least one
evaluable side at that horizon.

For each origin-offset-horizon:

- `Y = evaluated_long_fill * long_markout + evaluated_short_fill * short_markout`;
- `both`, `one`, and `none` denote two, one, and zero filled sides;
- `trade_rate = P(both or one)`;
- `fill_rate = E[(long_fill + short_fill) / 2]`;
- realised double-to-one ratio is `P(both) / P(one)`;
- break-even ratio is `-Y_one / Y_both` when `Y_both > 0` and `Y_one < 0`.

Report `Y_both`, `Y_one`, `P(both)`, `P(one)`, mean `Y`, both ratios,
`trade_rate`, and `fill_rate` by horizon, offset, and volatility decile. Also
report each horizon-offset pooled across volatility for the 60-second control.

The 60-second control must reproduce the frozen raw filled-row endpoint-valid
mask and markout to absolute tolerance `1e-9` bp. The resulting rounded pooled
statistics must reproduce the prior measurement. Failure aborts the run.

## Frozen causal cells

Let `M_t` be the last aggTrade strictly before minute origin `t`, no more than
1,000 ms old. Let `r_t = 10000 * log(M_t / M_(t-1m))`. At origin `t`, the
causal volatility score is the mean of `abs(r)` over the 15 one-minute moves
ending at `t`; the trailing direction is the sign of
`10000 * log(M_t / M_(t-15m))`, labelled `down`, `flat`, or `up`. All 16 prices
must be valid consecutive minute observations. Thus every input is known by
the quote origin.

Assign global volatility deciles with `pandas.qcut(score, 10)` over valid
origins. This descriptive full-window rank partition is frozen before outcome
measurement and is not a fitted predictor. Primary liquidity cells pool all
three direction labels. Require at least 500 observations for a cell to count
toward the verdict.

## Horizon-fix criterion

Define `Spearman(trade_rate, mean Y)` across the 40 primary
offset-by-volatility cells at each horizon. `rho <= -0.8` remains strongly
negative.

The horizon is the mechanical fix only if, at the same horizon:

1. at least one direction-pooled cell with `n >= 500` has `fill_rate > 0.2`
   and mean `Y > 0`; and
2. the 40-cell Spearman correlation is greater than `-0.8`.

Report the first horizon satisfying the positive-cell condition and the first
horizon satisfying both conditions. This is a gross, pre-fee criterion. A pass
opens a separately preregistered fee test; it does not establish fee-accessible
profitability. If no gross-positive liquid cell exists, the liquidity line is
closed under these horizons.

## Fade-disguise check

Report the 120 direction-conditional cells per horizon: offset by volatility
decile by `down`/`flat`/`up`. For each cell report all liquidity metrics plus:

- plain fade payoff on exactly those eligible origins, where fade signal is
  `-sign(trailing 15-minute move)` and payoff is that signal times the raw
  last-trade return from origin to the first trade at or after `origin + h`
  within 1,000 ms;
- Pearson correlation, within the same horizon-offset-volatility universe,
  between the binary decision to quote only that direction cell and the fade
  signal;
- mean `Y` for the matching direction-pooled volatility cell.

Any direction-conditional positive cell whose pooled mean `Y` is not positive
is labelled `positive_disappears_when_direction_removed` and is not a
liquidity result. Direction-conditional cells never satisfy the horizon-fix
criterion.

## Execution, outputs, and verification

Read only validated R1 shard and staging parts. Check every used part against
its existing metadata SHA-256. Process one UTC day at a time. Print block peak
and running peak RSS; abort above 3 GiB. Atomic writes use `.partial` then
rename. Save daily sufficient-statistic shards, frozen causal origin features,
CSV reports, `results.json`, and a manifest under
`out/zero_fit_liquidity_horizon_sweep_20260928/`.

`--verify` checks frozen plan, source, R1 manifest, every recorded input and
output hash, reconstructs all reports from daily sufficient-statistic shards,
and confirms both zero counters. It performs zero fits and sends zero orders.
