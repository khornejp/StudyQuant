# Timeout-settlement corrected Stage 3/Stage 4 rerun: frozen reading rule

Date frozen: 2026-08-17.  This document supersedes
`STAGE4_SOURCE_RETRAIN_PREREGISTRATION.md`; it is written before any corrected
run result exists.

Commit `5716d6b` corrected threshold selection so a row that reaches the
45-bar horizon without touching TP or SL is settled at its horizon-bar close,
with the stated round-trip cost.  Execution and the two screens already used
that settlement.  The correction can change the selected validation threshold,
which can change the rows that trade in the four stored out-of-sample test
windows.  Therefore all four arms are rerun, with no change to the frozen
geometry, cost, gate, data period, model defaults, or hyperparameters.

## Frozen arms and primary measure

Each arm uses the same four disjoint walk-forward test windows.  The primary
measure is `run_summary.json` at `oos_trading.gated`: the trade-weighted
`long_net_bps_trade_weighted` and `entries_total`.  It is a fold-test-slice
score, not a position-constrained backtest or a claim of live performance.

| arm | sources | geometry | output directory |
| --- | --- | --- | --- |
| S3-A | none | TP 0.4% / SL 0.2% | `artifacts/stage3_h45_tp004_sl002_q80_timeoutfix` |
| S3-B | none | TP 0.4% / SL 0.4% | `artifacts/stage3_h45_tp004_sl004_q80_timeoutfix` |
| S4-A | funding and premium-index archives | TP 0.4% / SL 0.2% | `artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix` |
| S4-B | funding and premium-index archives | TP 0.4% / SL 0.4% | `artifacts/stage4_h45_tp004_sl004_q80_sources_timeoutfix` |

No legacy Stage 3 or Stage 4 bps/count is a comparator in this reading rule.

## Reading axis 1: do collected sources help?

Compare S4-A only with corrected S3-A, and S4-B only with corrected S3-B.
For an arm:

- **Helped:** S4 net bps is strictly higher than S3 net bps and S4 has at
  least S3's `entries_total`.
- **No material change:** S4 is within +/-0.25 bps of S3 and has at least
  S3's `entries_total`.
- **Hurt:** S4 is lower by more than 0.25 bps and has at least S3's
  `entries_total`.
- **Count-confounded:** S4 has fewer entries.  It cannot be called helped,
  unchanged, or hurt from this comparison, regardless of its bps result.

The sources help only if both arms are helped.  If neither is helped nor hurt,
the result is no material improvement.  Any combination of arm outcomes,
including a count-confounded arm, is reported as **mixed** and not collapsed
into a source-success claim.

## Reading axis 2: did the timeout correction change the picture?

This is a separate historical-sensitivity comparison.  For each corrected arm,
compare it only with the like-for-like pre-`5716d6b` arm of the same source
state and barrier geometry.  It does not assess whether sources help, and its
direction is not a quality verdict: the corrected settlement is canonical.

- **No material change:** corrected bps is within +/-0.25 bps of its legacy
  value and corrected entries are at least the legacy count.
- **Material change, count-supported:** corrected bps differs by more than
  0.25 bps and corrected entries are at least the legacy count.  Report the
  signed bps and count differences; do not label this "better" or "worse."
- **Count-confounded:** corrected entries are fewer than legacy entries.
  Report the signed bps and count differences, but do not use a more selective
  corrected trade set to claim that the correction improved or did not change
  the picture.
- **Count change without a bps conclusion:** corrected entries differ but bps
  is within +/-0.25 bps, while the corrected count is lower.  Report this as
  count-confounded, not as no change.

The timeout conclusion is reported per arm.  Different arm outcomes remain
mixed.  It must never be substituted for the corrected S4-versus-S3 source
comparison above.

## Frozen commands

Run these commands sequentially under the GPU lease.  They intentionally omit
`--feature-cache`.  The source-free commands intentionally omit both archive
flags.  The output paths are new, so the historical artifacts remain intact.

```powershell
python -m btcusdt_quant train --input artifacts/btcusdt_2020_2026h1.parquet --metrics-dir artifacts/metrics --training-start 2020-01-01 --training-end 2025-12-31 --output artifacts/stage3_h45_tp004_sl002_q80_timeoutfix --cv-mode walk_forward --walk-forward-test-gap 45 --target profitability --round-trip-cost 0.0004 --horizon 45 --tp-pct 0.004 --sl-pct 0.002 --label-threshold 0.0004 --vol-gate-feature rv_60 --vol-gate-train-quantile 0.8 --vol-gate-screen-reference-report artifacts/barrier_screen_2026-08-12/barrier_screen_report.json

python -m btcusdt_quant train --input artifacts/btcusdt_2020_2026h1.parquet --metrics-dir artifacts/metrics --training-start 2020-01-01 --training-end 2025-12-31 --output artifacts/stage3_h45_tp004_sl004_q80_timeoutfix --cv-mode walk_forward --walk-forward-test-gap 45 --target profitability --round-trip-cost 0.0004 --horizon 45 --tp-pct 0.004 --sl-pct 0.004 --label-threshold 0.0004 --vol-gate-feature rv_60 --vol-gate-train-quantile 0.8 --vol-gate-screen-reference-report artifacts/barrier_screen_2026-08-12/barrier_screen_report.json

python -m btcusdt_quant train --input artifacts/btcusdt_2020_2026h1.parquet --metrics-dir artifacts/metrics --funding-dir artifacts/funding_2020_2026h1 --premium-index-dir artifacts/premium_index_2020_2026h1 --training-start 2020-01-01 --training-end 2025-12-31 --output artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix --cv-mode walk_forward --walk-forward-test-gap 45 --target profitability --round-trip-cost 0.0004 --horizon 45 --tp-pct 0.004 --sl-pct 0.002 --label-threshold 0.0004 --vol-gate-feature rv_60 --vol-gate-train-quantile 0.8 --vol-gate-screen-reference-report artifacts/barrier_screen_2026-08-12/barrier_screen_report.json

python -m btcusdt_quant train --input artifacts/btcusdt_2020_2026h1.parquet --metrics-dir artifacts/metrics --funding-dir artifacts/funding_2020_2026h1 --premium-index-dir artifacts/premium_index_2020_2026h1 --training-start 2020-01-01 --training-end 2025-12-31 --output artifacts/stage4_h45_tp004_sl004_q80_sources_timeoutfix --cv-mode walk_forward --walk-forward-test-gap 45 --target profitability --round-trip-cost 0.0004 --horizon 45 --tp-pct 0.004 --sl-pct 0.004 --label-threshold 0.0004 --vol-gate-feature rv_60 --vol-gate-train-quantile 0.8 --vol-gate-screen-reference-report artifacts/barrier_screen_2026-08-12/barrier_screen_report.json
```

## Pre-run artifact predictions to verify

All four arms should record `threshold_objective: "trading_pnl"`,
`round_trip_cost: 0.0004`, `label_horizon: 45`, and four fold thresholds in
`threshold_report.json`.  The values of those thresholds and all trade/EV
figures are deliberately not predicted.

| configuration | `run_summary.json` expectations |
| --- | --- |
| S3-A and S3-B | `feature_count: 169`; exactly these excluded fallback features: `adl_indicator`, `funding_rate`, `next_funding_rate`, `minutes_to_next_funding`, `funding_blackout_active`, `mark_price_basis`, `premium_index`, `leverage_bracket_utilization`, `regime_prob_up`, `regime_prob_range`, `regime_prob_down`. |
| S4-A and S4-B | `feature_count: 174`; exactly these excluded fallback features: `adl_indicator`, `mark_price_basis`, `leverage_bracket_utilization`, `regime_prob_up`, `regime_prob_range`, `regime_prob_down`. Funding and premium-index inputs therefore account for the five-feature difference. |
| all four | `oos_trading.gated.gate.fold_derived_minimum` and every value in `minimum_by_fold` should be `0.0013057161122560501`; `minimum` and `configured_minimum` should remain the CLI fallback `0.0`; `train_quantile` should be `0.8`; the screen-reference value should be `0.0009614995797164738` and role `descriptive_only_never_used_for_gating`. |

Expected end-to-end wall-clock from the corresponding historical run, before
queueing and with the same machine condition, is: S3-A 11,782 s (3:16:22),
S3-B 17,234 s (4:47:14), S4-A 10,095 s (2:48:15), and S4-B 15,061 s
(4:11:01): about 15:03 total sequentially.  Treat these as planning estimates,
not changed watchdog limits.  `training_runtime.jsonl` should record four
884,160-row fold fits each capped at 3,693 s and a 2,652,480-row final refit
capped at 10,800 s.
