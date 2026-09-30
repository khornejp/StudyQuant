# Short direction information-gap audit

Status: superseded by `PATCHTST_SHORT_METHOD_RESEARCH_CORRECTION_2026-09-15.md`.
Missing microstructure history remains a future limitation, but the saved model
already contains statistically useful direction information. It was hidden by
an incorrect score/evaluation mapping, so information shortage is not the
demonstrated primary cause of the failed pilot.

## Outcome

Stop changing thresholds and model heads on the current 35-feature table. The
60/20 target improved pooled ranking, but neither the linear nor nonlinear
cross-variable head achieved stable within-fold direction or 4bps gross. The
next uncertainty is information availability, not model capacity.

## Local evidence

- The active 35 features contain 1m price/volume/taker flow plus futures OI,
  long/short, funding and premium transformations. They contain no order-book
  depth, spread, microprice, cancellation flow or forced-liquidation feature.
- `btcusdt_quant/feature_registry.py` explicitly keeps F11 order-book features
  disabled as `pending_data_source` to prevent a train/live mismatch.
- `btcusdt_quant/sources.py` defines depth, aggregate-trade and liquidation
  sources, but marks them as not historically available and requires forward
  caching before promotion.
- The unsigned collector `out/collect_short_execution_feed.py` already captures
  Binance USD-M depth updates, BBO and aggregate trades without an account or
  order API. It is a maximum-60-second integrity smoke, not a continuous
  training-data service.
- Local Tardis data covers only six isolated calendar days: 2021-04-01,
  2022-04-01, 2023-10-01, 2024-01-01, 2024-10-01 and 2025-04-01. Compressed
  source size is 3,494,408,254 bytes. This is execution-replay evidence, not
  enough contiguous history for rolling-180-day/3-day walk-forward training.

## Availability and cost conclusion

- Live order book and aggregate trades are available from public Binance
  futures WebSocket streams; collection does not require placing orders.
- Tardis exposes incremental L2, trades and liquidation datasets, but only the
  first day of each month is downloadable without an API key. Therefore the
  local six-day sample cannot be silently treated as a free historical backfill.
- Buying/downloading continuous L2 before proving incremental information value
  would be premature. Conversely, training another PatchTST variant on the same
  35 columns will repeat the identified information bottleneck.

## Cost-minimal next Plan

1. Reuse the six already-downloaded days; spend no money and download nothing.
2. Stream each file once into causal 1m summaries: spread, top-1/top-5 imbalance,
   microprice deviation, depth add/cancel imbalance, aggressive sell ratio and
   trade intensity. Do not retain expanded CSV data.
3. Run a day-blocked information-value screen against an OHLC/taker-flow control
   on the same 60/20 H60 target. This screen decides only whether L2 merits
   collection/backfill; it cannot validate profitability or the 3-day cadence.
4. Require improvement in held-out-day mean AUC and consistency on at least four
   of six days. If it fails, discard L2 and revisit the horizon/project premise.
5. If it passes, choose between (a) free forward collection until enough
   contiguous data exists or (b) paid historical backfill. Only then promote
   microstructure features into the 3-day PatchTST experiment.

No execution backtest or live order is authorized by this audit.
