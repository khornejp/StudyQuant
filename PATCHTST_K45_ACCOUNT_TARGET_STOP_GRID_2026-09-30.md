# K=45 account-target stop-grid zero-fit preregistration

Frozen at `2026-09-30T15:42:43+09:00`, before any previously unmeasured stop
outcome was computed. This is an exploratory ledger replay. It cannot select a
winner, an optimal width, or a new acceptance verdict.

## Purpose, hypothesis, sources, and cutoff

Close the interpolation gap for account-loss targets `A in {10%, 20%}` and
accounting leverage `L in {1, 2, 3, 5, 10, 20}`. Measure exact requested price
stops under both definitions:

- gross target: `s = A/L`;
- net target: `s = A/L - 0.04%`, where the 4 bps round trip is inside the
  account target.

The frozen hypothesis is only that exact replay can materially differ from
nearest-grid substitution because every stop width rebuilds the non-overlapping
trade book. No interpolation is allowed.

Use only frozen local Binance USD-M BTCUSDT inputs:

- `artifacts/btcusdt_2020_2026h1.parquet`;
- `artifacts/funding_2020_2026h1/*.zip`;
- the frozen K=45 candidate ledgers and audit artifacts consumed by
  `out/run_patchtst_k45_stop_grid_audit_fix.py`;
- `out/patchtst_k45_stop_grid_audit_fix_20260930/*`;
- `out/patchtst_k45_wide_stop_grid_20260930/*`.

Data cutoff remains `2026-06-30T23:59:00Z`. Freeze source, input, plan, and
test SHA-256 hashes in the manifest. Counters are `new_model_fits: 0`,
`new_orders: 0`, `external_data_added: 0`, and `live_orders: 0`. Peak RSS must
not exceed 3 GiB.

## Exact derived grid

The 24 requested mappings and exact bps widths are:

| L | A | definition | stop bps | price % |
|---:|---:|---|---:|---:|
| 1 | 10% | gross | 1000 | 10 |
| 1 | 10% | net | 996 | 9.96 |
| 1 | 20% | gross | 2000 | 20 |
| 1 | 20% | net | 1996 | 19.96 |
| 2 | 10% | gross | 500 | 5 |
| 2 | 10% | net | 496 | 4.96 |
| 2 | 20% | gross | 1000 | 10 |
| 2 | 20% | net | 996 | 9.96 |
| 3 | 10% | gross | 333.333333333333... | 3.333333333333... |
| 3 | 10% | net | 329.333333333333... | 3.293333333333... |
| 3 | 20% | gross | 666.666666666667... | 6.666666666667... |
| 3 | 20% | net | 662.666666666667... | 6.626666666667... |
| 5 | 10% | gross | 200 | 2 |
| 5 | 10% | net | 196 | 1.96 |
| 5 | 20% | gross | 400 | 4 |
| 5 | 20% | net | 396 | 3.96 |
| 10 | 10% | gross | 100 | 1 |
| 10 | 10% | net | 96 | 0.96 |
| 10 | 20% | gross | 200 | 2 |
| 10 | 20% | net | 196 | 1.96 |
| 20 | 10% | gross | 50 | 0.5 |
| 20 | 10% | net | 46 | 0.46 |
| 20 | 20% | gross | 100 | 1 |
| 20 | 20% | net | 96 | 0.96 |

After exact duplicate removal, replay these 18 widths:
`{46, 50, 96, 100, 196, 200, 329.333333333333..., 333.333333333333...,
396, 400, 496, 500, 662.666666666667..., 666.666666666667..., 996,
1000, 1996, 2000}` bps. Repeating thirds use IEEE-754 values produced by
`1000/3`, `1000/3-4`, `2000/3`, and `2000/3-4`; they are not rounded to a
different grid cell.

The six overlaps with the requested grid are `{50,100,200,500,1000,2000}`.
Before accepting results, independently rebuild all 13 prior finite widths
`{10,15,20,25,30,40,50,100,200,300,500,1000,2000}` and compare prior ledgers,
summaries, priors, activation, performance, and matched decomposition artifacts.
Any mismatch halts the run.

## Frozen execution and inference

Use K=45, arms `DOWN_BREAKOUT_LONG` and `UP_BREAKOUT_SHORT`, and fill rules
`touch`, `gap`, `late`, and `adverse_extreme`. Apply
`entry_index + 45 < test_end_index` before inspecting any stop outcome. Rebuild
each arm/width book with the existing entry-time, no-simultaneous-position
filter. Do not queue skipped entries. Fill choice cannot change exit index or
book membership. Keep the existing fold-score Bartlett HAC, primary lag 60,
and frozen fallback rule.

There are 18 unique widths x 2 arms x 4 fills = 144 nominal pooled cells.
The 24 requested mappings x 2 arms x 4 fills = 192 account pooled cells.
Matched-set decomposition has 144 pooled cells and 864 UTC-year cells for the
six years 2021--2026. These cells are multiple exploratory comparisons. This
grid must not be used for width selection or a winner claim.

## Funding and account accounting

Load actual settlement timestamps and rates from the local funding ZIP archive.
For every ledger row, count events satisfying
`entry_time < funding_time <= effective_exit_time`, matching
`btcusdt_quant/live.py:214`. `effective_exit_time` is exact exit time when
known; for an intrabar touch/adverse stop it is the trigger-bar open because
funding settles at bar open and the stop occurs within that bar. At most one
settlement can occur in a 45-minute trade. A positive rate is a long cost and
a short credit; a negative rate reverses those signs.

Measure arm-specific unconditional funding cost from each executed no-stop
book. Reproduce the supplied long checks: 3,066 trades, 285 settlement
crossings, 9.2955%, conditional mean 1.2432 bps, unconditional mean 0.1156 bps,
239 payments and 46 receipts. Do not copy the long mean to short.

Attach both columns to every trade: its actual settlement cost and its arm's
no-stop unconditional average cost. Report both accounting methods and their
difference. For each leverage mapping report:

`margin_cost_bps = 4*L`

`funding_margin_bps = L*mean(actual trade funding cost bps)`

`net_account_bps = L*mean(gross_lin_bps) - margin_cost_bps - funding_margin_bps`

`account_return_pct = net_account_bps/100`

Repeat with the arm-average funding deduction. Leverage changes accounting
only. Do not simulate liquidation, margin calls, position sizing, or new orders.

## MMR threshold

Use `L < 1/(s + m(1-s) + f - a)`. Set added margin `a=0` because this replay
adds none. Set `f=(4 + cell mean actual funding cost bps)/10000`; do not set
fees or funding to zero. Solve each arm/fill cell as
`m < (1/L - s - f)/(1-s)` and emit
`EXECUTABLE_IF_MMR_BELOW_x.xxxx%`. Also retain the arm-average funding version
for comparison. This is a conditional threshold only because the repository
contains no BTCUSDT maintenance-margin tier schedule.

## Outputs and verification

Report all prior performance columns, both funding/account methods, MMR
thresholds, exact activations, full matched/added/dropped decomposition with
identity assertions, paired differences and HAC, UTC-year tables, a 2022
expansion, and a final mapping table. Any missing mapping must say `미측정` and
give a reason; expected missing count is zero because every derived width is
replayed directly.

Write only a new output directory. `--verify` must validate the frozen
manifest and output hashes, reconstruct every table and report, and finish
with zero fits and RSS below 3 GiB.
