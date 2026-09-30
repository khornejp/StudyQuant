# Zero-Fit BBO / Trade Target Equivalence Preregistration — R1 Amendment

Date frozen: 2026-09-25 KST

Status: repaired plan approved and frozen before R1 measurement. This file must not change after its SHA-256 is
embedded in `btcusdt_quant/target_equivalence.py`.

The completed artifact at `out/zero_fit_target_equivalence_20260925/` is
superseded because it measured touch fills instead of trade-through fills. Its
Parquet file is intact: `outcomes.parquet` has 3,695,504 rows and 22 columns and
matches its manifest hash. File corruption is not a reason for supersession.

## Purpose and hypothesis

Measure whether a full-span BTCUSDT USD-M trade-through opportunity target can
replace the shorter-span BBO target. No model is fitted. No order is sent. BBO
is the audit reference, not another model arm.

Frozen hypothesis: a trade-derived target is equivalent only if every gate
below passes without changing the estimator, thresholds, population, or window
after results are observed.

## Sources, cutoff, and window

- Binance public USD-M BTCUSDT monthly `bookTicker` ZIPs in
  `artifacts/bookticker/`.
- Binance public USD-M BTCUSDT daily `aggTrades` ZIPs in
  `artifacts/aggtrades/`.
- Existing feature artifact `artifacts/spread_features_1m.parquet` is included
  in provenance only. It is not used to construct references or targets.
- Data cutoff: 2024-04-01 06:46:00 UTC.
- Inclusive candidate-origin window: 2023-05-16 11:49:00 UTC through
  2024-04-01 06:46:00 UTC, on every UTC minute boundary.
- BTCUSDT tick size: 0.1 USDT.

The manifest hashes this plan, source, and every input ZIP used. Only public,
unauthenticated historical files are read.

## Shared target construction

AggTrades are ordered by `(transact_time, agg_trade_id)`. Duplicate, reversed,
or non-consecutive IDs fail input validation. Buyer aggressor means
`is_buyer_maker=False`; seller aggressor means `True`.

For reference `M`, side, and offset `x in {1, 2, 5, 10}` bp:

- short quote: `ceilTick(M * (1 + x / 10000))`;
- long quote: `floorTick(M * (1 - x / 10000))`;
- short fill: first buyer-aggressive trade in `(origin, origin + 60s]` with
  price at least one tick above the quote (`price >= quote + 0.1`);
- long fill: first seller-aggressive trade in `(origin, origin + 60s]` with
  price at least one tick below the quote (`price <= quote - 0.1`).

This is a trade-through opportunity, not a queue fill. Let its first crossing
time be `tau`. Conditional 60-second markout is:

- long: `10000 * log(endpoint / quote)`;
- short: `-10000 * log(endpoint / quote)`.

Fill and conditional markout remain separate. All three arms use the same
origin grid and aggTrade fill stream. Only `M` and the endpoint source change.

## Three frozen arms

### BBO reference

Origin `M` is the latest BBO midpoint strictly before the origin, matching the
trade arms. The markout endpoint retains BBO source semantics and is the latest
BBO midpoint at or before its query time. The BBO update must be no more than
1,000 ms old. Monthly BBO rows
are sorted by `(transaction_time, update_id)` before as-of lookup. Crossed,
zero, non-finite, duplicate-key, or reversed inputs fail validation.

### Bounce-corrected trade

For query time `u`, take adjacent opposite-aggressor pairs whose second trade
timestamp lies in `[u - 60s, u)` and whose gap is at most 100 ms. For second
trade `i`, `s_i=+1` for buyer aggressor and `-1` for seller aggressor:

`S_hat(u) = median(s_i * 10000 * (P_i / P_(i-1) - 1))`.

Require at least 20 pairs. No fallback. Let `h_hat=S_hat/2`. The last trade
strictly before `u` must be no more than 1,000 ms old:

`M(u) = P_last / (1 + s_last * h_hat / 10000)`.

The endpoint uses the first trade at or after `tau + 60s`, with delay no more
than 1,000 ms, then applies the same trailing-pair correction at that trade's
timestamp. The endpoint is invalid if either freshness or pair count fails.
The endpoint cache is scoped to one origin and shared by both sides and all
offsets. `raw` never calls the bounce estimator; the prior defect was
per-offset cache reinitialisation.

### Raw last trade

`M` is the last trade strictly before the origin, no more than 1,000 ms old.
The endpoint is the first trade at or after `tau + 60s`, with delay no more than
1,000 ms. No bounce correction is applied.

## Frozen equivalence gate

The gate is unchanged:

```text
common valid origins        >= 99% overall, >= 98% in every month
fill agreement              >= 99% per side and per offset
markout mean difference     |.| <= 0.02 bp
markout MAE                 <= 0.10 bp
markout |difference| p99    <= 0.50 bp
Pearson and Spearman        >= 0.995 each
```

Evaluate all three pairwise comparisons: BBO versus bounce-corrected trade,
BBO versus raw last trade, and bounce-corrected versus raw last trade.

An origin is common-valid for a pair only when both arms have valid targets for
all eight side-offset combinations. Coverage uses all candidate origins as its
denominator. Fill agreement uses common-valid origins. Markout statistics use
rows filled by both arms.

The coverage gate applies overall and to every calendar month. Fill agreement
applies to every side-offset cell and every side-offset-month cell. Markout
mean difference, MAE, absolute-difference p99, Pearson, and Spearman apply
overall and to each requested split: offset, side, and calendar month. A split
with no paired markouts, or a correlation split with fewer than two nonconstant
observations, is unevaluable and fails. Report mean, MAE, p50, p90, p99, max,
Pearson, Spearman, and count for every split. Quantiles and max use absolute
markout differences; mean is signed candidate-minus-reference difference.

Any failed pairwise gate stops target promotion. No automatic repair, new
threshold, estimator change, window change, or population change is allowed.

## Sharding, staging, restart, and memory contract

- Logical output shards are UTC days. Computation occurs in UTC-hour blocks.
  Any Parquet part is automatically split before 5,000,000 rows.
- Every monthly BBO ZIP is read exactly once per staging attempt with a
  500,000-row CSV chunk size. Rows are staged by `date/hour`, sorted by
  `(transaction_time, update_id)`, and duplicate-checked per hourly block.
  `update_id` is dropped immediately after that check.
- For each hourly compute block, the eligible fill interval runs from its first
  candidate origin through 60,000 ms after its last candidate origin. Context
  is BBO 1,000 ms before through 60,000 ms after that interval, and aggTrades
  60,100 ms before through 61,000 ms after it. This also governs the partial
  first and last hours. Context rows never become candidate origins or output
  rows.
- All Parquet and JSON writes use a `.partial` path, verify the Parquet footer
  where applicable, then atomically rename. `_SUCCESS` is written last for each
  staging block, logical day shard, and complete run.
- Restart accepts a staging block or logical shard only when `_SUCCESS`, its
  metadata, all declared files and all Parquet footers validate. It removes
  only run-owned incomplete work directories, replays their source ZIP, skips
  validated completed units, checks frozen hashes, and never accepts a
  `.partial` file as complete.
- Peak process RSS is sampled during every block, printed with the running
  maximum, and hard-fails above 3 GiB. Preflight requires at least 100 GiB free
  on the output volume.

## Drop and population analysis

Every origin drop has exactly one frozen cause: `stale_trade`,
`pair_count_lt_20`, or `boundary_context_missing`. The bounce origin drops when
trade freshness fails or fewer than 20 eligible pairs exist. A non-zero
`boundary_context_missing` count aborts before any gate is computed. Report
count and rate by cause overall, by UTC hour, by month, and by trailing
60-second aggTrade intensity bins `0-49`, `50-99`, `100-199`, `200-499`,
`500-999`, and `1000+`.

A kept origin is drop-adjacent when the immediately preceding or following
minute origin is bounce-dropped. Compare BBO/bounce agreement on kept-adjacent
versus kept-nonadjacent origins. Also compare BBO/raw agreement on bounce-kept,
bounce-dropped, and kept-adjacent origins so dropped periods remain measurable.
These are descriptive population-bias checks and cannot repair a failed gate.

## Outputs and verification

Write a SHA-256 manifest, origin-level data, side-offset outcomes, full split
tables, results, and verdict under `out/zero_fit_target_equivalence_20260925_r1/`.
`--verify` checks all frozen input/source/plan hashes and reconstructs results
from row-level outputs. It performs zero fits and sends zero orders.

Required counters in every result and manifest:

```text
new_model_fits: 0
new_orders: 0
```

The full-span study must not start in this run.
