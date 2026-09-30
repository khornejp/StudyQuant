# PatchTST unsigned-magnitude pilot preregistration

Frozen on 2026-09-28 Asia/Seoul before any fit. Source is the existing local
Binance USD-M BTCUSDT one-minute artifact
`artifacts/btcusdt_2020_2026h1.parquet` (nominal cutoff 2026-06-30; the
runtime manifest freezes its SHA-256). No external data is collected.

## Frozen hypothesis and decision

Target at origin `t`:

```
y(t) = |close[t+15] / close[t] - 1| * 1e4
```

`y` is unsigned bps. The model head, target passed to the loss, and every
prediction are nonnegative. No direction, PnL, fills, costs, or long/short
choice enters training or measurement.

Null: ordering the last 60 bars adds no magnitude information beyond matched
rolling aggregates. Sequence order wins only when the mean test Spearman of
the three PatchTST seeds strictly exceeds the matched-information LightGBM
test Spearman. Otherwise the frozen verdict is
`SEQUENCE_ORDER_ADDS_NOTHING_FOR_MAGNITUDE`. The ensemble prediction is the
third side-by-side audit column; every seed and its mean/range are also
reported. A win only proposes a separately preregistered walk-forward run.

## Split and sampling

- Fit: eligible origins sampled every 15 minutes whose `t+15` endpoint is no
  later than 2024-12-31 23:59 UTC.
- Test: eligible origins sampled on the same cadence from
  2025-01-01 00:00 UTC.
- PatchTST, matched LightGBM, and `range_60` use identical test origins.
- The fixed 15-minute cadence makes this a small CPU headroom pilot and avoids
  pretending that heavily overlapping one-minute origins are independent.

## Identical underlying information

PatchTST receives an ordered 60-bar sequence of six per-bar primitives:

1. absolute close log return, bps;
2. log high/low range, bps;
3. absolute log close/open body, bps;
4. `log1p(quote_volume)`;
5. `log1p(number_of_trades)`;
6. taker-buy quote-volume share, clipped to `[0, 1]`.

Signed log return is omitted. These primitives retain short-horizon magnitude,
shape, activity, and flow intensity without handing PatchTST rolling features.

Both models receive the same six static fields at origin `t`, for information
the 60-bar sequence cannot reconstruct:

1. 1440-minute log high/low range, bps;
2. 1440-minute realized volatility, bps;
3. `log1p` 240-minute quote-volume sum;
4. `log1p` 240-minute trade-count sum;
5. sine of minute-of-week;
6. cosine of minute-of-week.

The LightGBM control receives, for each of the six sequence primitives, rolling
mean and population standard deviation over 5/15/30/60 bars plus the current
value, then the identical six static fields. Thus its difference from PatchTST
is aggregation versus order, not source information.

## Fixed models and loss

One loss only: MAE on `y / median(y_train)`. MAE is robust to the long magnitude
tail; quantile heads are deferred. The PatchTST head ends in Softplus.

PatchTST reuses `out.run_short_patchtst.ShortPatchTST`: patch length 12,
stride 6, nine tokens, width 48, four heads, one layer, FFN width 96, dropout
zero. Static fields are concatenated after channel encoding. Fixed training:
AdamW, learning rate `1e-3`, weight decay `1e-4`, batch 512, six epochs, no
early stopping and no search.

Matched LightGBM: `regression_l1`, 300 estimators, learning rate 0.03, 31
leaves, `min_child_samples=100`, full row/column sampling, deterministic seed
42, four CPU threads. No search.

Authorized fit ledger, exactly:

```
PatchTST   3 seeds (42, 43, 44)       3 fits
LightGBM   matched-information control 1 fit
total                                  4 fits
```

No retry may silently create a fifth fit. A durable ledger reserves each fit
before training. Checkpoints permit zero-fit reconstruction.

## Measured context baselines (verbatim)

These are context from a different feature set, not the matched control:

```
range_60 alone                     test Spearman  +0.4256
LightGBM, 22 tabular features                     +0.4366
LightGBM test decile spread        5.936 -> 36.149 bps, 6.09x
```

## Output order and audit

The first printed result is the ordering audit, before loss curves or feature
importance: test Spearman and Pearson, MAE, ten prediction deciles (`n`, mean
prediction, mean realized `y`, top/bottom ratio) for `range_60`, matched
LightGBM, and the mean PatchTST prediction on identical rows; then calibration.
Per-seed scores and mean/min/max/range are printed with it.

The manifest freezes SHA-256 for this plan, its hash file, runner sources, and
the input parquet. `--verify` validates hashes, loads all four checkpoints,
rebuilds features/predictions/metrics, compares saved outputs, and executes zero
fits. Every major block prints peak RSS and aborts at 3 GiB.

Frozen operational counts: `new_backtests: 0`, `new_orders: 0`. No PnL, live
orders, authenticated exchange action, new external data, or artifact under
`out/_archive_pre_meta_2026-09-24/` is used.
