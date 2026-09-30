# K=45 stop-grid audit-fix preregistration

Frozen at `2026-09-30T00:24:00+09:00`, before any stop-grid outcome was
computed. This is a zero-fit ledger recomputation. Existing artifacts and the
existing `VALIDATION_FAIL` verdict remain unchanged.

## Purpose, source, and cutoff

Apply the return-unit, TEST-boundary, and inference audit fixes before an
exploratory K=45 stop grid. Use only these existing local Binance USD-M
BTCUSDT sources:

- `artifacts/btcusdt_2020_2026h1.parquet`;
- `out/patchtst_backward_k45_validation_20260929/k45_ledger.parquet`;
- `out/patchtst_fixed_trigger_hold_sweep_20260929/fixed_hold_ledger.parquet`.

The frozen data cutoff is `2026-06-30T23:59:00Z`. The runner manifest records
SHA-256 for this plan, its hash file, runner, test, market data, ledgers, and
upstream provenance files. No external data, checkpoint load, fit, order,
wallet, or authenticated exchange action is allowed. Counters are
`new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, and
`live_orders: 0`. Peak RSS must remain at or below 3 GiB.

## Frozen audit order and reproduction gates

The runner must execute these stages in order. It writes `verification.json`
with all reproduction gates before computing any stop result. A failed gate
halts the run.

### 1-1. Log and linear return separation

For signed position `q` in `{+1,-1}`, entry `p0`, exit `p1`, and one 4 bps
round-trip cost:

```text
gross_log_bps = 1e4 * q * log(p1/p0)
net_log_bps   = gross_log_bps - 4
gross_lin_bps = 1e4 * q * (p1/p0 - 1)
net_lin_bps   = gross_lin_bps - 4
pnl_usd_100   = net_lin_bps / 100
```

Linear fields are primary for PnL, win rate, summaries, and drawdown. Log
fields remain for exact legacy reproduction. The gates and their units are:

| population | metric | unit | expected | decimals |
|---|---|---|---:|---:|
| folds 0--405, concurrent primary | net_log_bps | log bps | +0.0192 | 4 |
| folds 0--405, concurrent primary | net_lin_bps | linear bps | +0.9266 | 4 |
| folds 0--405, single primary | net_log_bps | log bps | -2.0251 | 4 |
| folds 0--405, single primary | net_lin_bps | linear bps | -1.2361 | 4 |
| pooled, single primary | net_log_bps | log bps | -0.3552 | 4 |
| pooled, single primary | net_lin_bps | linear bps | +0.3010 | 4 |
| UTC 2022, single primary | net_log_bps | log bps | -4.504 | 3 |

Every reproduction table has an explicit unit column. In particular, the
2022 value is never compared with a linear field.

### 1-2. TEST-boundary clearing before stops

For every candidate, compute `scheduled_exit_index = entry_index + K` before
looking at high, low, open, a stop result, or an early exit. The scheduled
exit bar close must be no later than the origin fold's exclusive TEST end,
implemented as `scheduled_exit_index < test_end_index`. Exclude failures
before constructing any stop book. A stop may not rescue an otherwise
boundary-crossing trade.

K=45 is the only performance grid. K=70 is boundary audit only. The K=45
backward gate is 32 exclusions among 6,225 candidates and primary
`net_log_bps` changing from `+0.0192` to `-0.2133` before the single-position
filter. Report K=45 and K=70 exclusion counts by source, span, and arm.

### 1-3. Fold-score HAC

CR1 is replaced by a fold-score HAC interval. For trade-weighted mean `mu`,
fold score `s_g = sum_i(y_gi - mu)`, and `N` trades, use Bartlett weights
`w_h = 1 - h/(L+1)` and

```text
V(mu) = [G/(G-1)] / N^2 *
        [sum_g s_g^2 + 2*sum_{h=1}^L w_h*sum_{g=h+1}^G s_g*s_{g-h}].
```

Empty folds have score zero. Negative numerical variance is floored at zero.
Use fixed normal critical value 1.96. The structural primary lag is
`L_primary = min(60, G-1)`, reflecting 180 training days / 3-day fold spacing.
The data-independent alternative is
`L_auto = min(G-1, floor(4*(G/100)^(2/9)))`. Always report both intervals.
Select the alternative interval exactly when `L_primary/G > 0.5`; otherwise
select the primary. The rule depends only on `G`, never results, ACF, or
residual inspection. Thus folds 606--666 use the alternative rule rather than
the degenerate 60-of-61 interval.

## Frozen performance grid and books

Use stop widths `{10,15,20,25,30,40,50,none}` bps, K=45, arms
`DOWN_BREAKOUT_LONG` and `UP_BREAKOUT_SHORT`, and fills `{touch,gap,late}`:
48 reported cells. Each arm has its own one-position book. Within an arm,
sort by completed-close entry and signal index; accept when
`entry_index >= current_exit_index`; skip overlaps immediately without a
queue. Recompute the book for every stop width. Fill mode cannot change stop
bar, exit index, trade count, stop count, or holding time.

Entry is the close of `entry_index`. Exclude the entry bar. Inspect bars
`entry_index+1` through `entry_index+45`, inclusive. Long stop is
`p0*(1-s/1e4)` and fires when low crosses it; short stop is
`p0*(1+s/1e4)` and fires when high crosses it. First crossing wins, including
the scheduled exit bar.

- `touch`: stop level, optimistic;
- `gap`: triggering-bar open if already beyond the stop, otherwise stop level;
- `late`: triggering-bar close.

`late` is the requested delayed-fill scenario, but is not a mathematical
worst bound: a bar can cross the stop and recover before its close. Therefore
also report, without adding a fourth grid cell, the same-bar adverse-extreme
shadow fill (long at low, short at high), which is the strict OHLC-observed
within-bar adverse bound. Do not call either shadow a realizable quote.

For `none`, all three fill rows must be identical and an assert enforces it.
The touch-gap-late table reports the signed requested difference
`late mean net_lin_bps - touch mean net_lin_bps`, its absolute bracket width,
and the adverse-extreme shadow width. Mark a finite-stop cell
`UNMEASURABLE` when the absolute late-touch width exceeds its stop width.

## Time fields

Market `open_time` labels the start of a one-minute bar. A close-price entry
uses `entry_time = open_time[entry_index] + 1 minute`; a time or late close
exit uses the analogous bar-close time. An open-gap fill uses the triggering
bar open time. Intrabar touch fills have no exact timestamp: store the exit
bar open and close times, set `exit_time` missing, and set
`exit_time_exact=False`. A non-gap `gap` fill is also an intrabar touch and
uses the same treatment.

## Honest prior fixed before outcomes

This prior uses market close volatility only, never the candidate ledger,
triggered trades, stops, results, or model outputs. For each complete-enough
UTC day (at least 1,000 one-minute returns), calculate close-to-close realized
variance and `sigma_45 = 1e4*sqrt(RV_day/n_day*45)`. Under a zero-drift
Brownian first-passage approximation, daily one-sided hit probability is
`erfc(stop_bps/(sqrt(2)*sigma_45))`; average probabilities across the 2,373
eligible days through the cutoff.

| stop bps | prior stop fraction |
|---:|---:|
| 10 | 0.8028537226 |
| 15 | 0.7122980474 |
| 20 | 0.6291678359 |
| 25 | 0.5539298841 |
| 30 | 0.4865397553 |
| 40 | 0.3737344850 |
| 50 | 0.2864169368 |
| none | 0 |

The 10 bps stop lies well inside the 50 bps entry trigger noise and may stop
most trades quickly for roughly `10 + 4 = 14` bps loss before gap/late
uncertainty. An absolute actual-minus-prior error above 0.15 is pre-labelled
`PRIOR_MISS`; it is information about trigger conditioning, non-Gaussian
paths, and/or volatility clustering, not permission to refit the prior.

Write `TIGHT_STOP_DOES_NOT_WORK` exactly when every width in `{10,15,20}` has
pooled primary executed-stop fraction at least 0.50 and its optimistic touch
mean `net_lin_bps` is no greater than pooled primary `none-touch`. Otherwise
write `CRITERION_NOT_MET`. This is a precommitted descriptive sentence, not a
model acceptance verdict or winner selection.

## Frozen reports and interpretation

Report folds 0--405, 406--605, 606--666, pooled, and each UTC year. Per cell
report candidates, executed and skipped signals, stop count/fraction, mean
hold, log and linear gross/net, linear win rate, fixed-$100 total PnL, linear
closed-trade drawdown, and both HAC intervals plus the selected rule. Report
stopped-trade actual versus no-stop K45 would-be outcome, loss reductions,
profit cuts, and would-be win rate. Report mechanical grid shape and adjacent
differences, but no winner, optimal stop, acceptance condition, or verdict.

`--verify` validates frozen hashes, rebuilds all gates, boundaries, 48 cells,
books, summaries, shadows, drawdowns, tables, and report with zero fits, and
prints peak RSS. Existing output directories and artifacts are immutable.
