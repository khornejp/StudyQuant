# C0 sequential replay preregistration

Date: 2026-09-24 (Asia/Seoul)

## Status and claim boundary

This is one new backtest and zero new orders. It performs zero fits. It only
prices the frozen C0 predictions in
`out/patchtst_payoff_ladder_20260923/predictions.parquet` against the frozen
BTCUSDT USD-M one-minute bars in
`artifacts/btcusdt_2020_2026h1.parquet`.

Folds 406-605 have been inspected repeatedly. This is a retrospective ledger,
not a holdout. It makes no profitability claim. The hypothesis is frozen before
this runner is executed: next-open execution and a single-position constraint
should preserve the already measured conclusion that 4 bps round-trip cost
overwhelms C0's gross return.

Source timestamp: payoff-ladder artifact frozen on 2026-09-23; replay specified
on 2026-09-24. Data cutoff: ladder test windows end 2025-12-31 UTC. The bars file
extends through 2026-06-30, but the replay reads only indexes referenced by the
frozen predictions and their 16-minute execution boundary.

## Frozen replay contract

- Consider folds 406-605. Folds 418, 427, and 428 are forced flat; the other 197
  folds must be exactly the folds present in frozen C0 predictions.
- Use only `arm == "C0"` and `accepted == True`.
- Signal minute `i` closes before entry at `open[i+1]`.
- Exit at `open[i+16]`, for exactly 15 minutes of exposure.
- UP is long. DOWN is short.
- Exit and re-entry at the same open are adjacent, not overlapping.
- Keep at most one open position, with fixed 1x notional.
- Deduct 4 bps per completed round trip.
- Funding, slippage, and queue fill are excluded, not set to zero.

Candidate trades are processed by entry index. Before each candidate, positions
whose exit index is less than or equal to its entry index are closed. A candidate
is skipped only when one position remains open.

## Outputs

The artifact directory is `out/c0_sequential_replay_20260924/`.

- `ledger.parquet`: one row per executed trade, including fold, signal/entry/exit
  indexes and timestamps, side, confidence, gross, cost, net, funding-settlement
  count, 1x equity, and drawdown.
- `daily.parquet` and `monthly.parquet`: gross, cost, and net bps booked at trade
  exit. Every calendar day/month in the replay span is present. Abstentions,
  non-exit minutes, and flat periods contribute zero.
- `results.json`: aggregate metrics, timing delta, configuration arithmetic,
  funding materiality, and post-hoc diagnostics.
- `manifest.json` and `output_sha256.json`: SHA-256 lineage and output integrity.

The equity curve reinvests 100% of current wealth at fixed 1x on each sequential
trade. This is arithmetic compounding, not a margin or liquidation simulation.

## Funding decision

Funding remains excluded to preserve the stated replay contract. A trade spans a
settlement when `entry_timestamp < settlement <= exit_timestamp`, with settlements
at 00:00, 08:00, and 16:00 UTC. The output reports the crossing count and does not
record funding as zero.

Materiality is decided by a sign bound, not an assumed realized rate. The replay
reports the average favourable funding per crossed settlement required to offset
the entire negative net result. It also reports a deliberately generous +10 bps
per crossing sensitivity. If that sensitivity still leaves total net negative,
funding exclusion does not change the sign at this scale. Exact realized funding
PnL is outside this frozen two-input replay.

## Configuration arithmetic and diagnostics

Constant sizing uses `net_bps(k) = k * (gross_bps - 4 bps)`. Thus `k=0` is flat
and every `k>0` preserves the sign of arithmetic expectancy. Long-only and
short-only are reported separately. Concurrency caps 1, 2, 4, and unlimited are
replayed from the same candidates; a cap cannot help when candidate intervals do
not overlap.

Confidence prefixes retain the top `ceil(fraction * accepted rows)` by frozen
confidence for 75%, 50%, 25%, and 10%. These were chosen after inspecting the
window. Every result is labelled `POST_HOC_DIAGNOSTIC_NOT_POLICY`; none is a
strategy or acceptance gate.

## Verification

Before reading predictions, the runner verifies every source hash in the payoff
ladder's own manifest and the ladder output hashes for its manifest and prediction
parquet. The replay manifest then hashes its source modules, this plan, the frozen
prediction parquet, and the full bars parquet.

`--verify` repeats those checks, rebuilds the ledger and every reported number
from the two frozen inputs, checks stored output hashes, and compares all parquet
and JSON outputs. It never imports a model, reads a checkpoint, fits, or derives
signals again.
