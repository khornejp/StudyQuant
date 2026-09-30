# PatchTST payoff ladder plan

Date: 2026-09-23 (Asia/Seoul)

Continues `PATCHTST_MOVE_TARGET_LADDER_2026-09-23.md`, whose seven arms all
failed. One arm did not fail quietly: B4, which replaced cross-entropy with an
objective denominated in basis points, returned +1.964 bps at t = 4.58, cut the
large-move loss from -12.246 to -1.891, and was the only arm with a positive
difference from the fade rule (+0.466, t = 1.93 against a preregistered 2.0).
This ladder starts from B4 and asks three questions it could not answer.

## Objective

Find whether B4's edge over the fade rule is real, and whether it grows when the
model is given order-book and trade-activity inputs, a payoff that follows the
price path, or origins chosen by event rather than by clock. Measure in basis
points. Do not tune after seeing results.

## The ladder

Every arm is H15 only, three seeds, two encoder layers, ternary +/-10 bps target,
and B4's expected-basis-points objective. Only the listed change differs.

| Arm | Folds | Inputs | Payoff the loss maximizes | Origins | Contrast |
| --- | --- | --- | --- | --- | --- |
| B4 | 506-605 | 40 | terminal H15 return | every 15 min | already run |
| C0 | 406-605 | 40 | terminal H15 return | every 15 min | C0 - B4 = sample size |
| C1 | 406-605 | **50** | terminal H15 return | every 15 min | C1 - C0 = the new inputs |
| C3 | 406-605 | 50 | terminal H15 return | **CUSUM events** | C3 - C1 = event sampling |

## Why no arm trains on a barrier payoff

The first draft of this plan carried two barrier arms. Before any of them was
scored, the thirteen geometries below were priced directly on B4's own 3,022
accepted signals — the real model, the real bars, no retraining:

| Exit | Gross bps | Share of the endpoint's |
| --- | --- | --- |
| terminal | **+1.964** | — |
| +40 / -20 | +1.697 | 86% |
| +50 / -50 | +1.499 | 76% |
| +20 / -20 | +1.440 | 73% |
| +10 / -10 | +0.907 | 46% |
| +5 / -5 | +0.283 | 14% |

Every geometry from +/-5 to +/-50 earned less than holding to the endpoint. A
barrier truncates the wins the model does get while the 4 bps cost stays fixed,
and even +/-50, which resolves on only 8.7% of trades, gives up a quarter of the
edge. The audit had already reached the same conclusion on nine geometries used
as exits; this is a second, independent measurement on a different model.

Two measurements against, none for. The barrier arms are therefore dropped and
the GPU time goes to the lever that has never been tested. **Both geometries are
still scored for every arm**, so the decision stays visible in the results rather
than only in this paragraph.

## Where CUSUM applies

A smoke run showed the threshold keeps 7.4% of bars, which leaves about 21 STOP
origins in a three-day window against the 200 the accept rule's q90 needs. Event
sampling therefore chooses what the model **trains** on; STOP keeps the full grid
so the reject option is calibrated on a dense sample, and TEST keeps the full
grid for every arm so the scores compare. `C3 - C1` is then exactly the effect of
learning from events instead of from the clock.

## Abstained folds, and why

The preflight abstains where a window is too thin to work with, and all arms
share the list: **418, 427, 428**, leaving 197 evaluated.

| Fold | STOP origins | Cause |
| --- | --- | --- |
| 418 | 192 | its STOP window opens 2024-06-12, a day whose bookDepth archive holds a single snapshot at 23:59 |
| 427 | 99 | the same fold the frozen `continuous_200` run abstained on, for its own reasons |
| 428 | 20 | likewise |

An earlier draft blamed fold 418 on the missing 2024-04-18 file. That was wrong:
2024-04-18 falls inside 418's TRAIN window, which still holds 1,310 origins. The
cause is 2024-06-12.

## Withdrawn: the barrier-payoff section below

C2 and C2a were removed before any arm was scored, for the reason given above.
The section that follows described how they would have worked and is kept so the
decision is legible, not because the run tests it. **No arm in this run trains on
a barrier payoff.** Both geometries are scored for every arm, per side.

## Why C2 would have changed the payoff and not the label

B4's objective is `-(exposure * r)`. It never reads the class label, so giving it
a triple-barrier label would change nothing at all. The path enters through `r`:
in C2 and C3, `r` is the payoff of a trade that exits at the first barrier
touched within fifteen bars — `+10` bps if the price touched +10 before -10,
`-10` if the reverse, and the terminal return if neither. Same bars, same
threshold as the label; only what the model is paid for changes.

This creates a comparability problem and it is not hidden. C0 and C1 are trained
to earn the endpoint; C2 and C3 are trained to earn a barrier exit. **Every arm
is therefore scored both ways**: `gross_terminal` on the endpoint exit, which is
comparable across the whole ladder and is what the gate uses, and
`gross_barrier` on the first-touch exit, reported beside it. An arm that wins on
its own payoff but loses on the terminal score has changed the strategy, not
improved the model, and the report says so.

The audit already tested nine TP/SL geometries as *exits* and every one came in
below the terminal exit, with the best trailing by 0.022 bps. What is untested is
training the model to *seek* a barrier while the comparison stays honest.

## The new inputs (C1 onward)

Ten channels added to the 40, built from feeds the project had never used:

| Channel | Source | What it measures |
| --- | --- | --- |
| `book_imbalance_1pct` | bookDepth | resting size just below vs just above |
| `book_imbalance_5pct` | bookDepth | the same across the whole +/-5% band |
| `book_depth_total` | bookDepth | total resting size against its own 6h median |
| `book_slope_1_5` | bookDepth | near-band size as a share of far-band size |
| `book_depth_change_5m` | bookDepth | how fast the book is thinning |
| `trade_count` | aggTrades | prints per minute |
| `mean_trade_size` | aggTrades | average print size |
| `taker_buy_share` | aggTrades | share of volume where the buyer crossed |
| `trade_count_surge` | aggTrades | prints against their own 6h median |
| `big_trade_share` | aggTrades | share of volume in the day's largest 1% of prints |

A linear screen run before this plan found these add +0.0012 held-out AUC over
the existing 35, which is noise. That screen is kept and is not a reason to drop
the arm: it probes a linear combination while the model is a transformer, and it
scores direction while B4's objective is paid in basis points. `trade_count`
correlates 0.3663 with the size of the next move and 0.4977 with its direction —
a route to helping a magnitude-weighted objective that a direction AUC cannot
see. C1 - C0 settles it either way, and a null result validates the cheap screen
for future use.

Coverage: bookDepth starts 2023-01-01, aggTrades earlier, and both cover
99.8% of the origins in folds 406-605. Both exist as live streams
(`btcusdt@depth`, `btcusdt@aggTrade`), so train and serve can see the same thing.
Any conclusion here is limited to 2023 onward, because the feeds do not reach
further back.

## CUSUM event sampling (C3)

Instead of an origin every fifteen minutes, take an origin when the cumulative
absolute log return since the last origin exceeds a threshold set to the
trailing 60-bar volatility. Quiet stretches stop generating training rows. The
threshold is causal and preregistered here; it is not to be tuned afterwards.
Measured on the current origins, 79.91% of bars touch +/-10 bps within fifteen
minutes while only 50.18% end there, so a clock-sampled endpoint view is
discarding most of the movement the tape offers.

## Scope

Folds 406 through 605 inclusive, 200 consecutive folds, train windows from
2023-11-09, test through 2025-12-31. Three arms x 200 folds x 3 seeds = 1,800
models, of which B4's 300 are byte-identical to C0's folds 506-605 and are
reused. About 1,500 new fits, roughly seven hours.

Every arm scores the same origins — those where the order-book and trade feeds
are both fresh, 99.8% of the fold range — so C0, which does not read those
inputs, is still measured on the rows C1 can see. Without that the input
contrast would compare two different populations. C3 alone trains on fewer rows,
because that is what event sampling means; it still scores all of them.

## Frozen gate

Primary metric `gross_terminal`: basis points per trade on accepted rows,
`side * (close[t+15] / close[t] - 1) * 10000`. An arm passes only if:

1. gross positive with t at least 2.0;
2. **gross minus the fade benchmark on the same accepted bars positive with t at
   least 2.0**, the benchmark being `-sign(close[t] / close[t-15] - 1)`;
3. gross on rows whose realized absolute move is at least 50 bps not negative;
4. gross at least 1.0 bps above B4 on the folds they share.

Trade counts, coverage and both sides' row counts are reported, and gate
nothing. The previous ladder's count lines answered a deployability question
inside an experiment about what the model learns, and the t-statistics already
carry sample size; that correction is carried forward rather than re-litigated.
Every arm reports a 95% interval and the smallest effect its own standard error
can resolve, and a contrast below that is reported as unresolvable rather than
as absent.

Net of 4 bps is reported everywhere and gates nothing.

## Preregistered diagnostics

`corr(predicted side, prior 15-minute return)` — B4 sits at -0.4082 and the
frozen baseline at -0.4554; the long and short sides' separate agreement with
the prior move, which told the previous ladder that B3 alone stopped mirroring;
gross by realized magnitude bin; coverage; `gross_barrier` beside
`gross_terminal` for every arm; and, for C3, how many origins CUSUM keeps.

## Prohibited

No TP/SL as an execution rule, only as a training payoff that is scored both
ways. No backtest engine. No live order. No new calendar data. No spot input. No
threshold, cap or gate tuned after results are seen. No checkpoint reused across
a different input set, payoff or sampling scheme.

Retrospective evidence on a window the project has already inspected. It
authorizes nothing.
