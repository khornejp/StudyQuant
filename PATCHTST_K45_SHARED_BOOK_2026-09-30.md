# K=45 shared-book zero-fit replay preregistration

Frozen before reading any Task C result. Exploratory only. No winner selection or verdict.

## Question and fixed inputs

- Test the claim that prior `DOWN_BREAKOUT_LONG` and `UP_BREAKOUT_SHORT` results used separate one-position books and that their pooled sum is not executable in one isolated account slot.
- Reuse only the 9,113 boundary-clean candidates in Task B `causal_candidates.parquet` and frozen one-minute market/funding inputs already used by Tasks A/B.
- Predictions are immutable inputs. No fit, retraining, retuning, fold selection, threshold selection, or external data.
- K=45. Entry and scheduled exit use the existing bar-close convention. Eligible only when `entry_index + 45 < test_end_index`.
- No stop. One round-trip cost of 4 bps. Report touch, gap, late, and adverse-extreme labels; with no stop they must be exactly equivalent.

## Books and admission

Candidate order is stable by `(entry_index, signal_index, arm)`. A position occupies `[entry_index, entry_index + 45)`. A candidate executes only when `entry_index >= current_exit_index`; skipped candidates never queue.

Four reported books:

1. `SHARED`: one slot across both arms.
2. `LONG_ONLY`: only `DOWN_BREAKOUT_LONG`, one slot.
3. `SHORT_ONLY`: only `UP_BREAKOUT_SHORT`, one slot.
4. `INFEASIBLE_ARM_SUM`: union of the separately executed long-only and short-only books. Reference only; never label executable.

### Same-index conflict rule

Adopt `DROP_BOTH`: if both arms have candidates at the same `entry_index`, discard both before slot admission. This is symmetric, causal, and avoids choosing direction after seeing outcomes. It applies even when the slot is already occupied; diagnostics separate raw conflict indices from free-slot conflicts.

Rejected deterministic shadows: `LONG_FIRST` and `SHORT_FIRST`. Run both only as frozen sensitivity checks. Report conflict index/candidate counts, free-slot conflict count, and each shadow's executed-set/trade-count changes versus `DROP_BOTH`. Do not select among them from results.

## Existing-book overlap audit

- Recompute arm-specific masks and assert exact equality with Task B `first_come_executed`.
- Count overlap minutes on half-open executed intervals. Primary rate: overlap minutes divided by all one-minute bars from the first eligible entry minute through the latest scheduled exit minute, inclusive of minute cells. Also report overlap divided by union-active minutes.
- Count every executed long/short interval pair with positive intersection.
- Split overlap minutes by UTC calendar year. Attribute an overlap pair to the UTC year containing its first overlapping minute. Report yearly share of all overlap minutes and pairs.

## Performance

For every book and fill label report candidate count, trade count, skipped-entry count, mean net linear bps, mean net log bps, linear win rate, total PnL for fixed $100 notional per trade, linear-dollar maximum drawdown, mean/median hold minutes, and HAC 95% interval.

HAC rule stays frozen: fold-cluster score series on fold grid 0..666, Bartlett lag 60; if lag/grid ratio exceeds 0.5, use automatic lag `floor(4*(G/100)^(2/9))`, capped at G-1. Use normal 1.96 interval. Year tables use folds whose frozen three-day fold start falls in that UTC year. Report selected rule and lag.

Report SHARED arm decomposition: executed and skipped counts, mean net linear bps, share of shared trades, and opposite-arm slot blocks. A candidate is an opposite-arm casualty only when it executes in its own arm-only book, does not execute in SHARED, is not a same-index conflict, and its entry lies inside the currently executed opposite-arm shared interval. Report casualty count and its own arm-only no-stop mean. Report the reverse direction identically.

## Matched-set decomposition

Compare `SHARED - LONG_ONLY` and `SHARED - SHORT_ONLY` by `candidate_id`.

- matched = executed in both books
- added = executed only in SHARED
- dropped = executed only in comparator

Use the existing three-term mean decomposition. Assert matched + added + dropped contribution equals the full mean difference within 1e-12 bps. Report matched paired return difference and frozen HAC 95%. Repeat on trade-level account returns for every leverage.

## Funding and account basis

Attach each frozen funding settlement by the Task A interval `entry_time < funding_time <= exit_time`; at most one settlement per K=45 trade. Funding cost per trade is `position * funding_rate_bps`.

For `L in {1,2,3,5,10,20}`:

- `margin_cost_bps = 4*L`
- `funding_margin_bps = actual_funding_cost_bps*L` per trade, never an arm-average deduction
- `account_net_bps = L*gross_lin_bps - margin_cost_bps - funding_margin_bps`
- account total PnL and drawdown use fixed $100 margin and time-ordered exits

Report funding crossing/payment/receipt counts and mixed-arm funding totals for SHARED. No MMR or liquidation claim: no-stop has no stop-width executability threshold.

## Year and Task B checks

- Produce all-year tables and a 2022 expansion. Include SHARED 2022 long/short trade counts and shares.
- Inspect Task B manifest/results and ordering outputs. If both frozen arms are present with 20 arm-feature cells, record `BOTH_ARMS_COMPLETE`; otherwise run the missing arm's identical ordering audit without changing its rule family.

## Integrity and outputs

- Write a new directory `out/patchtst_k45_shared_book_20260930`; do not modify prior artifacts.
- Freeze plan SHA-256 plus source and input SHA-256 in `manifest.json` before Task C computation.
- `--verify` validates frozen hashes, reconstructs every parquet/JSON/report from inputs, compares outputs, and performs zero fits.
- Hard assertions: four fill labels exactly equal under no-stop; separate-book masks reproduce Task B; all decomposition identities; per-trade funding; peak RSS below 3 GiB.
- Status fields: `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, `live_orders: 0`.

