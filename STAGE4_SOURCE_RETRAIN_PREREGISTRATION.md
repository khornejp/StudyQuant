# SUPERSEDED — Stage 4 source retrain: frozen reading rule

**Superseded on 2026-08-17 by
`STAGE4_SOURCE_TIMEOUT_FIX_RERUN_PREREGISTRATION.md`.** Commit `5716d6b`
corrected timeout settlement in production threshold selection: a horizon
timeout had been scored as `-sl_pct` there while execution and both screens
settled it at the horizon close. Consequently the Stage 3 threshold/EV figures
and trade counts quoted below (`-3.2427` / `1,114` and `-2.6332` / `7,533`)
were made on the contaminated selection path. They are retained as historical
record only and **must not be quoted or used as comparators**. The replacement
document preregisters corrected Stage 3 and Stage 4 reruns and keeps the source
effect separate from the timeout-fix effect.

Date frozen: 2026-08-16.  Stage 4 repeats the two already-selected 45-bar
geometries over the same four walk-forward test windows as Stage 3, adding the
available funding and premium-index inputs.  It is a one-seed, reused-window
comparison, not a new geometry-selection exercise or an independent holdout.

The primary result for each arm is the gated, trade-weighted long net bps in
`run_summary.json` and its `entries_total`.  The pre-run Stage 3 comparators
are:

| arm | geometry | Stage 3 trade-weighted net bps | Stage 3 trades |
| --- | --- | ---: | ---: |
| A | TP 0.4% / SL 0.2% | -3.2427 | 1,114 |
| B | TP 0.4% / SL 0.4% | -2.6332 | 7,533 |

For an arm to count as **helped**, Stage 4 must have a strictly higher
trade-weighted net-bps result *and* at least its Stage 3 trade count.  A result
within +/-0.25 bps of that arm's comparator, with at least its Stage 3 trade
count, counts as **no material change**.  A strictly lower result by more than
0.25 bps, with at least its Stage 3 trade count, counts as **hurt**.  Any
result with fewer Stage 4 trades is count-confounded and is reported as such;
it cannot be called helped or hurt from this comparison, even if its bps is
better or worse.

The sources are considered to have helped this run only if **both** arms meet
the arm-level helped rule.  If neither arm meets it and neither meets the
arm-level hurt rule, the run establishes no material improvement under this
rule.  Mixed arm-level outcomes are reported as mixed, not collapsed into a
single success claim.  These rules are descriptive safeguards against a
smaller set of selected trades, not significance tests or evidence of live
performance.

## Per-fit watchdog calibration

Stage 4 retains the native-fit watchdog, but the bound is now row-scaled. The
calibration is the two completed Stage 3 commands: arm A elapsed **11,782 s**
(3:16:22) and arm B elapsed **17,234 s** (4:47:14). Each command performed
four 884,160-row fold fits and one 2,652,480-row final refit: **6,189,120
fit-rows** in total. The slower arm B therefore supplies a deliberately
conservative rate of 17,234 / 6,189,120 seconds per fit-row. This is an
end-to-end rate, not a reconstructed CatBoost-only time, so it already
includes non-fit work; the watchdog then adds **50% headroom**.

For both arms, Stage 4 has the same fit sizes, so the applied limits are:

| arm | fit | rows | calibrated limit |
| --- | --- | ---: | ---: |
| A | folds 1--4 (each) | 884,160 | 3,693 s (61m 33s) |
| A | final refit | 2,652,480 | 10,800 s (3h; operational ceiling) |
| B | folds 1--4 (each) | 884,160 | 3,693 s (61m 33s) |
| B | final refit | 2,652,480 | 10,800 s (3h; operational ceiling) |

The uncapped final calculation is 11,079 s (3h 4m 39s); it is capped at three
hours so a stuck native extension is still forcibly terminated within a
reasonable unattended window. Each `fit_started` and `fit_timeout` event in
`training_runtime.jsonl` records the applied `watchdog_timeout_seconds`.
