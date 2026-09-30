# New-session independent review handoff

User instruction: perform formal review in a new session. This file is a
handoff, not a review or verification result.

## Highest-priority review

1. Read `SESSION_STATE_2026-09-22.md` and the frozen continuous-200 plan.
2. Audit `out/run_patchtst_direction_classwise_selective_continuous_200.py`
   for causal fold boundaries, saved-model path reuse, STOP-only thresholds,
   class-label polarity, output gate math, and all 200 calendar slots.
3. Run the no-fit reconstruction command from `D:\StudyQuant`:

   `& '.\venv_btcusdt\Scripts\python.exe' -B -u -m out.run_patchtst_direction_classwise_selective_continuous_200 --verify`

4. Independently reconcile 56,204 TEST rows, 6,477 accepted rows, 198
   evaluated folds, two causal abstentions, and 66 reused/1,122 new models.
5. Review the later six exploratory outputs for source alignment and gate
   arithmetic, without editing their frozen plans/runners/results. A correction
   needs a new wrapper and output directory.

## Scientific decision boundary

- Frozen continuous result: FAIL, selected BA .554771, forced BA .525646.
- Sparse 28-fold PASS must not be called continuous replication.
- ATR gate and other exploratory variants fail their own frozen criteria.
- No profit, execution, or live-use claim is authorized.
- Dates were repeatedly inspected; later 2026 data are not automatically
  pristine because earlier project experiments also touched parts of 2026.

After review, the defensible next hypothesis is not another q/threshold
sweep. Test a genuinely distinct, ex-ante detectable regime/target and
learning objective on existing data. Do not present new calendar data as the
solution to the current direction failure.

## Later 2026-09-22 event-sampling addendum

Read `EVENT_SAMPLING_RESEARCH_REPORT_2026-09-22.md`. Three separately frozen
new diagnostics examined 15-minute grid aliasing, a causal 1-minute Binance
futures sell-flow trigger, and that trigger's fixed H1/3/5/15/30/60 return
response. Grid aliasing is substantial for *future-labeled origin groups*,
but the actual causal trigger failed H15 short direction (47.35% on 5,081
signals) and every shorter-horizon rescue gate. Verify the timestamp units,
lookahead boundaries, episode counting, cooldown and result arithmetic in a
new session before relying on them. No live orders or net-profit claim.

The local Binance USD-M metrics archive also has a verified content-label
shift in late June 2026; see `BINANCE_METRICS_TIMESTAMP_SHIFT_PLAN_2026-09-22.md`
and `out/binance_metrics_timestamp_shift_20260922.json`. The local transition
is not a clean single day (start-labeled June 12 isolated, then June 22 onward
in sampled June days). Independently review source bytes and any `create_time`
as-of join before using metrics on those dates. This cannot explain the
2024-2025 continuous-200 result.

The 2026 July-Aug klines redundantly collected under
`artifacts/fresh_2026q3_archive` are **not** pristine OOS: the existing H2
source and 2026-09-14 experiments already used that period. Do not call the
duplicate download new validation evidence.

The new existing-data large-move routing audit is in
`PATCHTST_LARGE_MOVE_ROUTING_PLAN_2026-09-22.md` and
`out/patchtst_large_move_routing_20260922.json`: only 51/1,384 >=50bp H15
declines received an accepted-short signal; 186 were accepted long, 1,147
abstained. Independently reconcile the label join and three-way routing.

## Most recent continuation

Read the later-continuation section of `SESSION_STATE_2026-09-22.md`.
The prior-OOS trend-reversal meta-score failed. Raw-feature PatchTST retraining
has **not** started. Review the existing-data evidence first; then write a
frozen Plan for a genuinely distinct learning-objective test. Do not use
new data, TP/SL gates, spot inputs, or live orders as a substitute for better
short/down direction. External skills installed this session are research aids
only; TradingCodex was not attached. Verify Caveman is in the new session's
loaded-skill list before claiming it is active. Do not repeat the unsupported
claim that the user's Claude account is over quota.
