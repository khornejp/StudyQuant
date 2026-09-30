# K=45 stop-grid matched-set decomposition preregistration

Frozen at `2026-09-30T04:42:45+09:00`, before this decomposition was
computed. This is a zero-fit analysis of immutable local artifacts. It does
not change the existing `VALIDATION_FAIL` verdict or any prior output.

## Purpose, hypothesis, source, and cutoff

The full-book stop-minus-none contrast mixes a within-trade stop effect with
book-composition effects because early stop exits change later admissions.
The frozen exploratory hypothesis is only that both components may exist; no
direction, winning stop, optimum, or acceptance rule is predicted.

Use only:

- `out/patchtst_k45_stop_grid_audit_fix_20260930/decision_ledger.parquet`;
- `out/patchtst_backward_k45_validation_20260929/k45_ledger.parquet`;
- `out/patchtst_fixed_trigger_hold_sweep_20260929/fixed_hold_ledger.parquet`;
- the audit-fix runner and its frozen provenance files.

The data cutoff remains `2026-06-30T23:59:00Z`. The new manifest freezes
SHA-256 for this plan, hash file, runner, test, and every input. Counters must
remain `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, and
`live_orders: 0`. Peak RSS must not exceed 3 GiB. Cost remains one 4 bps
round trip. The existing decision ledger already applies the scheduled
`entry_index + 45 < test_end_index` exclusion before inspecting any stop.

## Identity and populations

Analyze finite stops `{10,15,20,25,30,40,50}`, both arms, and stop outcomes
`{touch,gap,late,adverse_extreme}`. `adverse_extreme` uses the existing
strict OHLC-observed shadow: trigger-bar low for long and high for short.

Within each arm and stop, trade identity is `entry_index`. Assert that each
book has at most one executed trade for an identity and that fill mode never
changes membership. Let:

- `M`: entry indices executed by both none and stop books;
- `A`: entry indices executed only by the stop book;
- `D`: entry indices executed only by the none book.

Report pooled results for every arm/stop/outcome. Also report the same
decomposition for UTC 2022, with special report rows for pooled long stop 10,
pooled short stop 10, and 2022 long stop 15. UTC-year membership follows the
existing `origin_year_utc` field.

## Matched stop effect and HAC

For each trade in `M`, form the paired score
`d_i = stop_net_lin_bps_i - none_net_lin_bps_i`. Report `|M|`, both means,
the mean paired difference, and its HAC 95% interval. Build each fold score
directly from paired differences, `s_g = sum_i(d_gi - mean(d))`; never form
two separate mean intervals and subtract them. Keep empty fold scores at
zero. Reuse the audit-fix Bartlett HAC formula, normal critical value 1.96,
`L_primary=min(60,G-1)`, `L_auto=min(G-1,floor(4*(G/100)^(2/9)))`, and choose
auto exactly when `L_primary/G > 0.5`.

## Exact three-part decomposition

For each arm/stop/outcome, let `nS=|M|+|A|`, `nN=|M|+|D|`, and use these
means: stop outcomes `muS_M`, `muS_A`; none K45 outcomes `muN_M`, `muN_D`.
Decompose the full-book difference exactly as:

```text
matched contribution = |M|/nS * (muS_M - muN_M)
added contribution   = |A|/nS * (muS_A - muN_M)
dropped contribution = |D|/nN * (muN_M - muN_D)
```

Assert within `1e-12` bps that their sum equals
`mean(stop book)-mean(none book)`. Report counts, raw group means, reference
mean `muN_M`, each contribution, and the reconstruction residual. Empty-set
contributions are zero and their unavailable means are null. The added rows
also report their counterfactual K45 none-rule mean from
`would_be_net_lin_bps`; this descriptive mean is not substituted into the
identity above.

## Added-trade description

For every arm/stop, describe `A` without a verdict:

- count by UTC year;
- mean stop outcome and mean counterfactual K45 none-rule `net_lin_bps`;
- `tau_50` count, mean, standard deviation, and 10/25/50/75/90 percentiles;
- the same tau summary for `M`, plus added-minus-matched mean and median and
  a descriptive two-sample KS statistic and p-value;
- the none-book accepted predecessor that blocked each added entry: its
  fixed scheduled holding time and remaining overlap at the added entry.

Find the blocker by replay order: the latest previously accepted none trade
in the same arm whose `exit_index` is strictly greater than the added
`entry_index`. Assert every added entry has such a blocker. Tau and blocker
descriptions depend only on book membership, so do not duplicate them by fill
mode. State numerically whether added trades are positive or negative under
the none K45 rule; do not turn that description into a decision.

## Adverse-extreme promotion and measurability

Retain the 48-row pooled table indexed by stop, arm, and requested fill
`{touch,gap,late}`. Add formal columns for adverse-extreme mean
`net_lin_bps`, its absolute width from touch, and measurement status. For a
finite stop, status is `UNMEASURABLE` exactly when
`abs(adverse_extreme_mean - touch_mean) > stop_bps`; otherwise it is
`MEASURABLE`. Do not use late-touch width for this status. None remains
`NOT_APPLICABLE`. Report the count of each status without hiding cells.

## Outputs and verification

Write a new output directory only. Include manifest, status, results,
verification, SHA-256 output manifest, 48-row main table, matched table,
decomposition table, UTC 2022 decomposition, added-trade yearly and tau
tables, blocker ledger/summary, and report. `--verify` must validate frozen
hashes, rebuild every table and assertion from frozen inputs, compare all
artifacts, reconstruct the report, perform zero fits, and print peak RSS.

All results are exploratory. Produce no winner, optimal stop, acceptance
condition, or new verdict.
