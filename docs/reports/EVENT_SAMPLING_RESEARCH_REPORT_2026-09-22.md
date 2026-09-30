# Binance futures event sampling: research and measured outcome

Date: 2026-09-22. No order, maker-fill simulation, TP/SL optimization, fee
deduction, spot series, or model retraining was performed. These new outputs
have not had the requested independent review in a new session.

## External evidence and limits

- Easley, López de Prado and O'Hara, *The Volume Clock* (2012): activity time
  need not match wall-clock time. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2034858
- Hudson & Thames's CUSUM implementation samples only after a thresholded
  cumulative price move; event sampling is causal only if the input and dynamic
  threshold are known at the signal time. https://github.com/hudson-and-thames/mlfinlab/blob/master/mlfinlab/filters/filters.py
- Cont, Kukanov and Stoikov, *The Price Impact of Order Book Events*: book
  order-flow imbalance relates to very short-term price impact. This is NOT
  evidence that our 1-minute Binance kline taker-sell share predicts 15-minute
  futures direction. https://arxiv.org/abs/1011.6402
- Original PatchTST code offers self-supervised pretraining and fine-tuning;
  its main published task is long-term forecasting, not proof of BTCUSDT
  short-entry edge. https://github.com/yuqinie98/PatchTST
- Binance USD-M public kline fields include taker-buy base volume, so the
  causal trigger is constructible from live closed futures klines. It still
  lacks book depth and passive limit-order fill information.
  https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/market-data/rest-api/Kline-Candlestick-Data

## Frozen experiments

1. `PATCHTST_ORIGIN_GRID_ALIASING_PLAN_2026-09-22.md` and
   `out/audit_patchtst_origin_grid_aliasing.py` ->
   `out/patchtst_origin_grid_aliasing_20260922.json`. On the 2024-05-10 to
   2025-12-31 continuous-200 calendar, 5,458 groups of consecutive origins
   had an H15 close return <=-50bp; 1,331 (24.39%) contained a 15-minute grid
   origin. For H60 <=-100bp, 854/2,570 (33.23%) did. These are overlapping
   future-label windows, not independent crash events or a trade opportunity
   count. The aliasing screen gate passed, warranting a causal-event test.
2. `PATCHTST_CAUSAL_SELL_FLOW_TRIGGER_PLAN_2026-09-22.md` and
   `out/audit_patchtst_causal_sell_flow_trigger.py` ->
   `out/patchtst_causal_sell_flow_trigger_20260922.json`. A predeclared
   down-candle, >=60% taker-sell-share, >=3x trailing-day-volume-median
   trigger with 15-minute cooldown produced 5,081 2026 H1 signals. H15 strict
   down precision was 47.35%, against 50.23% for all minute origins and
   48.20% for the same trigger constrained to the grid. Mean hypothetical
   short close-to-close H15 return was -0.315bp before cost. It captured
   220/1,759 H15 50bp future-drop origin groups versus 49 for the grid-only
   trigger, but failed the primary direction gates. Reject this trigger.
3. `PATCHTST_SELL_FLOW_HORIZON_RESPONSE_PLAN_2026-09-22.md` and
   `out/audit_patchtst_sell_flow_horizon_response.py` ->
   `out/patchtst_sell_flow_horizon_response_20260922.json`. On those exact
   5,081 origins, strict short direction was 46.86%, 46.82%, 47.23%, 47.35%,
   47.43%, and 47.84% at H1/3/5/15/30/60. No horizon reached the 57%
   direction plus 4bp mean-gross exploratory gate. Shortening the horizon
   does not rescue this trigger.

## Decision

Clock aliasing is real at the level of outcome-labeled start windows, but it
is not itself predictive information. The first causal sell-flow trigger
selected *more* large-drop windows while getting short direction wrong more
often. Do not optimize its thresholds or TP/SL on the inspected dates, and do
not infer a maker-fillable edge from close-to-close returns.

Before another model or more data, audit the existing source timing, labels,
features and causal information content. Candidate quality and direction
accuracy must be measured separately. Do not repeat loss/threshold sweeps or
infer that new data alone can solve a failure on existing history. No L2
purchase follows from this result: the prior six isolated L2 days did not
establish value.

An attempted new-data step redundantly fetched 2026-07-01 through 2026-08-31
Binance USD-M BTCUSDT 1-minute klines into
`artifacts/fresh_2026q3_archive`. Coverage metadata reports 62/62 dates,
89,280/89,280 canonical rows, no missing dates. However the repository already
has this H2 period under `out/btcusdt_sources_20260701_20260907`, and prior
experiments evaluated 2026-07-02 through 2026-08-31 (see
`SESSION_STATE_2026-09-14.md`). The new download is **not a new holdout** and
must not be presented as one. No July-Aug labels were inspected in this new
analysis or used to choose a model. Per user direction, stop further data
collection and focus on the existing historical failure.

## Existing-data timing issue found during source search

The provider repository has an open report of a `metrics` timestamp convention
change: https://github.com/binance/binance-public-data/issues/491 . Our local
ZIPs show an end-labeled 5-minute range on 2026-06-20, but start-labeled
ranges on 2026-06-22, 24 and 25; 2026-06-12 is another isolated start-labeled
day. This local boundary differs from the issue's reported 2026-06-25 date,
so do not copy a hard-coded change date. A separate frozen content-alignment
preflight is in `BINANCE_METRICS_TIMESTAMP_SHIFT_PLAN_2026-09-22.md` and
`out/binance_metrics_timestamp_shift_20260922.json`.

The archived taker buy/sell ratio on 2026-06-20 matches the *preceding* 5m
window (r=.99934, median absolute error .00013). On 2026-06-22/24/25 it
matches the *following* 5m window (r=.99924/.99970/.99938), proving the raw
label no longer always equals availability time. The current loader joins
`create_time <= signal_time` (`btcusdt_quant/metrics_source.py`); using the
start-labeled rows without a 5m availability shift can leak future metrics.
Quarantine those rows in any future feature build until a separately reviewed
source-aware fix. This does **not** explain the continuous-200 failure ending
in 2025, and does not change its frozen outcome.

## Existing OOS: where the short model loses the big drops

`PATCHTST_LARGE_MOVE_ROUTING_PLAN_2026-09-22.md` and
`out/patchtst_large_move_routing_20260922.json` join the frozen 56,204
continuous-200 H15 predictions to the existing futures close vector; saved
strict-direction labels match reconstructed labels exactly. Of 1,384
>=50bp H15 declines, only 51 (3.68%) received an accepted-short signal;
186 (13.44%) were accepted **long** and 1,147 (82.88%) were abstained.
Of 1,353 >=50bp rises, 91 were accepted short. P(down) AUC separating
large-down from large-up was 0.4658, worse than random on this
future-conditioned subset. This is a diagnostic, not a causal selection or
sign-inversion rule. It isolates the problem: the current classifier ranks
big moves in the wrong direction, so easing its confidence gate or changing
exit rules cannot solve the short-direction failure.

Before any economic backtest, a new-session review must also reconcile the
current Binance-vs-stale-Bitget fee assumptions and market-order-vs-limit-only
execution mismatch. Keep real orders disabled.

## Direction-failure analysis and retraining boundary

The 200-fold reference was **already refitted from original features at each
three-day fold** (1,122 new neural fits; 66 reused checkpoints). A separate
20-prior-fold logistic meta-score used saved, chronologically earlier OOS
predictions plus the prior 15-minute move. It is a causal diagnostic, **not**
an end-to-end retrain. Its frozen exploratory gate failed: on the late 100
folds, all-origin AUC moved 0.529898 -> 0.530558, while future-conditioned
>=50bp down-vs-up AUC worsened 0.470913 -> 0.468267. See
`PATCHTST_TREND_REVERSAL_META_PLAN_2026-09-22.md` and
`out/patchtst_trend_reversal_meta_20260922.json`. These OOS outcomes had
already been inspected, so this is not independent confirmation.

Across all 56,204 origins, frozen PatchTST direction AUC was 0.534309, but
on the 2,737 origins with absolute H15 return >=50bp it was 0.465816.
The existing endpoint LightGBM scored 0.488048 on that same extreme subset.
The PatchTST extreme AUC was below 0.5 in six of seven calendar quarters.
A descriptive seven-day block bootstrap gave [0.4490, 0.4840] for the
PatchTST extreme AUC. Conditioning on a **future** magnitude is solely a
failure diagnostic, never a deployable gate.

For the 3,188 accepted-short origins, hypothetical H15 close-to-close gross
mean was +0.9574bp. On the 142 accepted-short >=50bp future extremes it was
-26.3592bp: 51 correct large declines averaged +65.4753bp; 91 wrong large
rises averaged -77.8270bp. Ex-post removing all extremes leaves +2.2309bp
mean on 3,046 origins. This ex-post filter cannot be traded; the number is
also below an illustrative 4bp maker-plus-maker round trip, before any
fill/exit effects. Actual fee tier and maker fills remain unverified.

The decision is **not** to tune the confidence threshold, TP/SL, or another
score stacker. The next research test, if authorized, is one pre-registered,
paired **from-raw-features retrain** on the existing data: hold the 3-day
walk-forward splits, 35 futures features, model capacity, seed set and
training budget fixed; compare the existing strict H15 BCE model against one
short-event-aware objective with an ex-ante all-origin score. Include all
origins in evaluation, then separately report the future-conditioned
>=50bp diagnostic, large-up false alarms, selected-short gross, and fold/
quarter stability. Earlier three-way event and weighted-tail objectives
already failed in other experiments; the new objective must be demonstrably
different and specified before looking at its TEST results. A failed paired
retrain should end this model/feature-family iteration, not start another
threshold/loss sweep. The 2026 history has also been inspected and must not
be called pristine holdout. No new calendar data is required for this test.
