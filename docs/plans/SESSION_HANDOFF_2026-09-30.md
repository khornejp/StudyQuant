# Session handoff, 2026-09-30

State at the moment the session stopped. Nothing is running: all monitors were stopped and every
`codex.exe` was killed by PID (`TaskStop` alone does not kill it).

## Where the work stands

The long-only K=45 breakout-fade book is the only executable configuration left, and **its headline
number does not survive a trimmed mean**. Everything else tested today came back negative.

| experiment | artifact | verdict |
|---|---|---|
| backtest audit | `out/patchtst_k45_stop_grid_audit_fix_20260930/` | 3 defects found and fixed |
| stop grid 0.1%–20% | `out/patchtst_k45_wide_stop_grid_20260930/` | every width loses to no stop |
| A account basis | `out/patchtst_k45_account_target_stop_grid_20260930/` | account return degrades monotonically with leverage |
| B own-candidate features | `out/patchtst_k45_causal_admission_ordering_20260930/` | `NO_ORDERING`, 0 of 20 |
| C shared book | `out/patchtst_k45_shared_book_20260930/` | prior "pooled" was INFEASIBLE; long-only best |
| D short-signal veto | `out/patchtst_k45_short_signal_veto_20260930/` | `NO_ORDERING`, 0 of 5 |
| E power fix + F taker flow | `out/patchtst_k45_flow_inference_20260930/` | `FLOW_REGRESSION_GATE_FAILED` |

## The two findings that matter

**1. `LONG_ONLY +0.4550 bps` rests on two trades.** Reproduce with

```python
d = pd.read_parquet("out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet")
ex = d[(d.arm == "DOWN_BREAKOUT_LONG") & (d.first_come_executed == True)]
r = 1e4 * (close[ex.scheduled_exit_index] / close[ex.entry_index] - 1) - 4
```

`n=3066`, mean `+0.4550`, total `+1395.1 bps` = `$13.95`. Median `+5.9749`, sd `114.2`, skew `-1.11`,
min `-1173`, max `+808`. Dropping the best 1 trade gives `+0.1916`; **dropping the best 2 gives
`-0.0171`** and the sign flips. Best 10 → `-1.3572`. Best 30 (top 1%) → `-3.6113`. An iid bootstrap
of 20,000 draws gives 95% CI `[-3.566, +4.409]` with `P(mean <= 0) = 0.407`.

The claim "long-only +0.4550 is the executable best" was retracted.

**2. No experiment ever computed a drift baseline, and it is favourable.** A random 45-minute long
over the same span (`n=2,879,368`, and identically on the 15-minute grid) nets **`-3.7834 bps`**
after the same 4 bps. The strategy nets `+0.4550`, so it beats indiscriminate longing by
**`+4.2384 bps`** — gross `+4.4550` against `+0.2166`. The gate and trigger do produce roughly
4.24 bps of gross edge; the 4 bps round trip consumes almost exactly that.

## The one open question

Finding 1 and finding 2 may be the same fact. The audit handed to Codex ends with it:

> **Does a gross advantage over random longs survive after removing the top 2 trades?**

If no, the gate and trigger did nothing and the line is closed. If yes, the problem becomes cost
alone, not signal.

## Other defects found, not yet resolved

| # | defect | changes conclusions? |
|---|---|---|
| 3 | entry and exit both at `close` of the deciding bar (`run_patchtst_fixed_trigger_hold_sweep.py:145`, `run_patchtst_k45_stop_grid_audit_fix.py:176`) | no — next-open/next-open gives `+0.4587`, difference `+0.0037`, t `0.22` |
| 4 | purge/embargo is exactly zero: `train_end == stop_start`, `stop_end == test_start` (`run_short_patchtst_3day_cadence_pilot.py:43-47`) while labels span `t+1..t+15` | unmeasured; violates the repo's own contract |
| 5 | two calendars pooled: `fold_plan()` asserts 606 folds ending 2026-01-01, but `pilot_fold` runs 0–666; folds 606–666 (61 folds, 712 candidates) come from another generator | unmeasured |
| 6 | candidates per fold: mean 15.39, median 8, max 203 across 592 folds | partly addressed by monthly blocking in E |

## What was in flight when the session stopped

`scratchpad/codex_defect_audit_round1.md` was dispatched to Codex and **killed before it produced
output**. Re-send that file to resume:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox - < codex_defect_audit_round1.md
```

The scratchpad is session-scoped, so copy the brief out of it before relying on the path.

## Environment note

`psutil` vanished from the Python 3.14 environment mid-session and every runner imports it
unguarded at `run_patchtst_k45_stop_grid_audit_fix.py:12`. It was reinstalled (7.2.2). If a runner
dies at import, check that first.
