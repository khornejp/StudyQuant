# PatchTST backward extension and K=45 validation preregistration

Frozen at `2026-09-29T16:19:47+09:00`, before the first backward-extension fit.
This run is a **lineage-specific reverse-time validation**, not fresh OOS.
The model lineage and K selection were developed on later dates, so this result
must not be described as a pristine historical holdout or independent OOS test.

## Source and frozen forecast extension

Use only `artifacts/btcusdt_2020_2026h1.parquet`: existing local Binance USD-M
BTCUSDT one-minute OHLCV, cutoff `2026-06-30T23:59:00Z`. No external data,
authenticated exchange action, or live order is allowed.

Preserve the exact 606-fold calendar and the complete model, target, feature,
normalization, optimizer, and seed contract frozen in
`PATCHTST_EXCURSION_RANGE_2026-09-28.md`. Extend forecasts backward only to TEST
folds 0 through 405, covering `[2021-01-08T00:00:00Z,
2024-05-10T00:00:00Z)`. Each fold keeps 180 days TRAIN, 3 days STOP, 3 days
TEST, and 15-minute origins. Fold 0 TRAIN is
`[2020-07-09T00:00:00Z, 2021-01-05T00:00:00Z)`.

Seeds remain 42, 43, and 44. Exactly `406 * 3 = 1,218` new fits are authorized.
Checkpoints may load only from this run's directory. The frozen folds 406--605
artifact and every other checkpoint tree are forbidden inputs. The original
artifact must remain unchanged and pass its own zero-fit `--verify` after this
run completes.

## Frozen K selection and strategy

Fix `K=45` minutes as the only hold. It was selected from the later exploratory
six-value hold sweep by the one-SE rule: choose the shortest candidate whose
primary-arm pooled mean net was within one fold-cluster standard error of the
best candidate. No other K, gate, trigger, cost, or strategy variant is allowed.

For each fold, average its three seed predictions on STOP and TEST. Set the
gate to the linear STOP q90 of predicted excursion; TEST ties pass. At every
gated TEST origin `t`, inspect completed closes for `k=1,...,15`:

```
d(k) = 1e4 * log(close[t+k] / close[t])
tau  = min{k : abs(d(k)) >= 50}
entry_index = t + tau
exit_index  = entry_index + 45
```

No crossing means no trade. Entry uses the observed completed-close overshoot.
The primary arm is `DOWN_BREAKOUT_LONG`; its gross return is
`1e4*log(close[exit]/close[entry])`. The retained negative control is
`UP_BREAKOUT_SHORT`; its gross return is the negative of that value. Subtract
4 bps round trip once. No rebate, funding, extra slippage, fill model,
compounding, or sizing rule is added.

## Frozen inference and four acceptance conditions

For each arm, estimate mean net return with intercept-only OLS and CR1 covariance
clustered by TEST fold. Use correction `G/(G-1)` and the two-sided 95% Student-t
critical value with `G-1` degrees of freedom.

Estimate `DOWN_BREAKOUT_LONG - UP_BREAKOUT_SHORT` by OLS on the stacked trade
ledger with an intercept and a primary-arm indicator. The indicator coefficient
is the difference in arm means. Use the same fold-clustered CR1 correction and
two-sided 95% interval, with clusters taken over the stacked ledger.

Only these four conditions determine the verdict, in this order:

1. Shared realised trigger rate outside 20%--60%, inclusive, gives
   `POPULATION_MISMATCH`.
2. Each arm must have at least 30 non-empty TEST-fold clusters.
3. Primary-arm mean net and its CR1 two-sided 95% lower bound must both exceed
   zero.
4. Primary-minus-control mean difference and its fold-CR1 two-sided 95% lower
   bound must both exceed zero.

If condition 1 passes but any of conditions 2--4 fails, verdict is
`VALIDATION_FAIL`. If all four pass, verdict is
`LINEAGE_REVERSE_TIME_VALIDATED`. No other verdict, condition, subgroup result,
or permission follows.

## Frozen descriptive reports

For each UTC origin year and both arms, report trade count, mean gross bps,
mean net bps, fold-CR1 two-sided 95% interval, and total PnL under $100 fixed
notional per trade. Per-year results are descriptive only and never gate the
verdict. This includes no special 2022 condition.

Report realised concurrency for each arm and both arms combined. Treat a trade
as open on the half-open minute interval `[entry_index, exit_index)`. Report
maximum concurrency, mean concurrency over the complete minute clock from the
first TEST origin through the last realised exit, and mean concurrency on
active minutes. These values are descriptive only.

`net_bps / 100` is each trade's standalone dollar PnL on fixed $100 notional.
Its sum does not model shared capital, margin, leverage, compounding, liquidation,
or the capital required by overlapping positions.

## Reproducibility and safety

Write all checkpoints and outputs to
`out/patchtst_backward_k45_validation_20260929/`. Freeze a separate manifest
covering this plan and hash file, runner, test, imported forecast/calendar/helper
sources, original folds 406--605 manifest, and input parquet. Write separate
checkpoint and output SHA-256 indexes.

`--verify` must validate hashes, load all 1,218 local checkpoints, reconstruct
forecasts, gates, ledgers, statistics, concurrency, tables, report, and verdict,
and perform zero fits. Print peak process RSS and abort above 3 GiB. Frozen
counters are `new_model_fits: 1218`, `new_orders: 0`, `external_data_added: 0`,
and `live_orders: 0`.
