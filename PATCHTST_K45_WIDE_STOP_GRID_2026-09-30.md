# K=45 wide stop-grid zero-fit preregistration

Frozen at `2026-09-30T09:05:00+09:00`, before any wide-stop outcome was
computed. This is an exploratory ledger recomputation. It does not alter any
existing artifact or the existing `VALIDATION_FAIL` verdict.

## Purpose, frozen hypothesis, sources, and cutoff

Test whether a user-specified 1,000 bps (10% price) stop fires within 45
minutes, and place it in the exact wide grid `{100,200,300,500,1000,2000}`
bps. The frozen hypothesis is that 1,000 bps will rarely fire and will be
close to the no-stop book. This is a hypothesis, not a conclusion or gate.

Use only immutable local Binance USD-M BTCUSDT artifacts:

- `artifacts/btcusdt_2020_2026h1.parquet`;
- `out/patchtst_backward_k45_validation_20260929/k45_ledger.parquet`;
- `out/patchtst_fixed_trigger_hold_sweep_20260929/fixed_hold_ledger.parquet`;
- `out/patchtst_k45_stop_grid_audit_fix_20260930/*`;
- `out/patchtst_k45_stop_grid_matched_decomposition_20260930/*`.

Data cutoff stays `2026-06-30T23:59:00Z`. Record source hashes, this plan
hash, runner/test hashes, frozen hypothesis, cutoff, and results. Counters are
`new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, and
`live_orders: 0`. Peak RSS must not exceed 3 GiB.

## Frozen books and fills

Use K=45, arms `DOWN_BREAKOUT_LONG` and `UP_BREAKOUT_SHORT`, and exactly four
outcomes: `touch`, `gap`, `late`, and `adverse_extreme`. Entry is the close of
`entry_index`; inspect bars `entry_index+1` through `entry_index+45`,
inclusive. Long and short levels are `p0*(1-s/1e4)` and `p0*(1+s/1e4)`.
First crossing wins. Fills retain the audited definitions: stop level,
trigger-bar open only for an opening gap, trigger-bar close, and trigger-bar
low/high for long/short adverse extreme. Cost is one 4 bps round trip.

Apply `entry_index + 45 < test_end_index` before inspecting stop outcomes.
Within each arm, accept a candidate only when its entry is at or after the
current accepted trade exit. Do not queue skipped entries. Rebuild the book
for every stop width. Fill choice cannot change exit index or membership.

## Existing-grid reproduction and combined table

Recompute the frozen `{10,15,20,25,30,40,50,none}` grid with the existing
audited code. Compare all existing decision, span, yearly, would-be,
sensitivity, and shape artifacts against immutable files. A mismatch halts
before wide results are accepted. The combined performance table copies
existing touch/gap/late rows from immutable `span_summary.parquet`; it does
not replace them with newly written values. Formal adverse-extreme rows are
derived from the immutable shadow fields. Append the six wide widths to make
one ordered table `{10,15,20,25,30,40,50,100,200,300,500,1000,2000,none}`.

## Primary activation answer

For every wide width, report executed trade count, stop count/fraction, and
the same totals by arm. Define `NEAR_ZERO` before outcomes as stop fraction
at or below 1.00% for the all-arm total and for each arm. Report the first
width satisfying this definition, if any.

`EQUIVALENT_TO_NONE` requires, for both arms and every fill: identical
executed `entry_index` sets, zero stops, identical trade count, and exactly
equal mean linear net bps to the no-stop book. Assert all conditions. If a
first equivalent width exists, assert every wider tested width is also
equivalent. Otherwise label `NOT_EQUIVALENT_TO_NONE`.

Extend the existing volatility-only prior without using candidates or stop
outcomes. For UTC days with at least 1,000 one-minute close returns, compute
`sigma_45 = 1e4*sqrt(RV_day/n_day*45)` and average the zero-drift Brownian
one-sided first-passage probability
`erfc(stop_bps/(sqrt(2)*sigma_45))`. Reproduce the immutable old prior first.

## Performance and matched-set outputs

For each pooled stop/arm/fill cell report boundary exclusions, boundary-clean
candidates, executed and skipped entries, stop/time exits and fractions,
mean gross/net linear bps, mean gross/net log bps, linear-net win rate,
fixed-$100 total PnL, linear-dollar maximum drawdown, mean/median holding
minutes, and selected HAC 95% interval with rule and lag. Reuse the audited
fold-score Bartlett HAC and its frozen lag-selection rule.

For every wide stop, arm, and four outcomes, compare against no-stop using
matched, added, and dropped identities. Report counts, exact contribution
bps, full difference, reconstruction residual, paired matched difference and
paired HAC 95%, and added trades' mean under the no-stop K45 outcome. Assert
the three contributions reconstruct the full difference within `1e-12` bps.

Write all UTC-year activation and performance rows. Also write matched and
decomposition rows for every UTC year. Expand UTC 2022 in the report and
show the year distribution of 1,000 bps stops.

## Scope and leverage warning

All results are exploratory. Produce no winner, optimal stop, acceptance
condition, or new verdict. Calculations use 1x leverage and fixed $100
notional. A 10% price stop implies a 100% account loss at 10x leverage, while
real liquidation would generally occur first. Do not model leverage or
liquidation in this experiment.

Write a new output directory only, a SHA-256 manifest, and `--verify` that
validates frozen inputs and reconstructs all artifacts with zero fits.
