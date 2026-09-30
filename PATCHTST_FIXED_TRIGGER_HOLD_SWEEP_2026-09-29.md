# PatchTST fixed-trigger hold sweep preregistration

Frozen at `2026-09-29T15:35:25+09:00`, before running this sweep or computing
any fixed-hold outcome. This experiment is exploratory. It follows a failed
fixed-endpoint breakout test and cannot produce a confirmation verdict.

## Defect and scope

The superseded rule entered at the first completed-close trigger `tau` inside
`t+1,...,t+15` but exited at `t+15`. Its exposure was therefore `15-tau`
minutes, not a controlled 15-minute hold. A trigger at `tau=15` paid the full
4 bps round-trip cost with zero gross exposure. The old hold/outcome table was
also confounded because `tau` measures trigger speed.

This run replaces only the exit rule. It does not alter the forecast, gate,
trigger, entry price, arm direction, cost, origin population, or input data.
No model fitting, external data, live action, or authenticated exchange action
is allowed.

## Frozen inputs and spans

Source market data is the existing local Binance USD-M BTCUSDT one-minute
OHLCV file `artifacts/btcusdt_2020_2026h1.parquet`, with data cutoff
`2026-06-30T23:59:00Z`.

Reuse only these existing zero-fit forecast outputs:

- `out/patchtst_post_trigger_markout_20260929/exploration_origins.parquet`
  for origins from `2024-05-10` through `2025-12-30` and its stored per-fold
  STOP-q90 PatchTST gate.
- `out/patchtst_down_breakout_long_confirmation_20260929/ensemble_predictions.parquet`
  for origins from `2026-01-01` through `2026-06-30` and its stored per-fold
  STOP-q90 PatchTST gate.

Report `2024-05-10..2025-12-30`, `2026-01-01..2026-06-30`, and their pooled
sample separately. The pooled sample is not an independent third test.

## Frozen trigger, entry, arms, and exit

For every gated origin `t`, inspect completed one-minute closes only:

```
d(k) = 1e4 * log(close[t+k] / close[t]),  k = 1,...,15
tau  = min{k : abs(d(k)) >= 50}
```

No trade exists when the set is empty. Entry is the observed overshoot price
`close[t+tau]`, not the unobserved exact barrier price.

- Down breakout, `d(tau) < 0`: take a long position.
- Up breakout, `d(tau) > 0`: take a short position.

Freeze the six fixed holds:

```
K = 15, 20, 30, 45, 60, 70 minutes
exit_index = t + tau + K
```

Every available trade at a given `K` therefore has exactly `K` minutes between
entry and exit. Long gross return is
`1e4*log(close[exit]/close[entry])`; short gross return is its negative. Net
return subtracts 4 bps once. Fixed-$100 PnL is `net_bps/100`, without
compounding, sizing, rebates, funding, slippage additions, or fill modeling.

An exit beyond the market-data cutoff is right-censored, reported, and excluded
from return summaries. It is never filled with an earlier bar or a forced
endpoint. All origins remain in population and trigger counts.

## Frozen reporting

For each span, arm, and `K`, report available trades, censored exits, mean gross
bps, mean net bps, win rate, mean fixed-$100 PnL, and total fixed-$100 PnL.

Measure trigger speed with bins that exactly invert the prior remaining-bars
table:

- `tau=1-5` (old remaining bars `10-14`)
- `tau=6-9` (old remaining bars `6-9`)
- `tau=10-12` (old remaining bars `3-5`)
- `tau=13-14` (old remaining bars `1-2`)
- `tau=15` (old remaining bars `0`)

For every span, arm, `K`, and speed bin, report trade count, censored count,
mean gross bps, mean net bps, and total fixed-$100 PnL. These strata measure
the trigger-speed confound; they do not create verdicts.

Also report the old-rule zero-exposure count `tau=15`, its fraction of triggered
trades, and the 4 bps / $0.04 pure cost per such $100 trade, by span, arm, and
both arms combined. The user-supplied historical audit value, 159 of 2,217
trades in the first span, is a required reproduction check.

The parameter family contains 12 rules: six holds times two arms. Reporting two
spans plus their dependent pooled view creates 36 arm-by-hold-by-span summaries.
Speed-bin rows are descriptive decompositions. No multiplicity-adjusted or
unadjusted pass/fail verdict, winner selection, or confirmation claim follows.

## Meaning of the 15-minute gate at K=70

At `K=70`, the gate still identifies origins with high forecast near-term
`t+1..t+15` travel. Volatility persistence can make that state informative
beyond 15 minutes, so the gate is not meaningless. It is not a matched-horizon
70-minute forecast, however, and it supplies no directional or duration
justification for a 70-minute hold. The `K=70` result is therefore an
exploratory persistence probe only.

An honest matched-horizon version would freeze a target measuring excursion or
range through 70 minutes, fit and calibrate its per-fold STOP-q90 gate without
using test outcomes, then evaluate a preselected hold on fresh out-of-sample
data. Re-gating during the trade would define a different adaptive strategy and
requires a separate preregistration.

## Reproducibility and safety

Hash this document before tests or execution. The run manifest must hash the
plan, hash file, runner, test, exact upstream forecast artifacts and hash
indexes, and market parquet. `--verify` must validate those hashes, reconstruct
triggers, fixed exits, ledgers, all summaries, and the report with zero fits.
Print process peak RSS and abort above 3 GiB.

Frozen counters are `new_model_fits: 0`, `new_orders: 0`,
`external_data_added: 0`, and `live_orders: 0`.
