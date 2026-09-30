# Post-selection temporal backtest — frozen 2026-08-10, reclassified 2026-08-11

**This is not a holdout verdict.** It was written as one; an adversarial review
established it is not, and the title now says so. What it is: a temporal
backtest of a model whose training stops at 2024-12-31, evaluated over
2025-01-01..2026-06-30, where the *configuration* was partly selected using
knowledge of that same period. Read the "What this can and cannot show"
section before the numbers.

Written before the model was retrained and before any result was read. The
values below did not change afterwards. Two things did, and both are recorded
here rather than quietly absorbed: `--long-only` was added to the codebase
because the frozen command would not execute, and the classification of the
whole exercise was downgraded.

## Why this exists

Two adversarial reviews reached the same finding: the fold test slices have
become a tuning surface. `fold_test_predictions.csv` exports the realised
payoff of every fold test row, and the volatility gate, the entry quantile and
the 200-day trend window were all *evaluated* against it. The window length was
fixed before measuring, but the decision to use a trend filter at all came from
reading those payoffs. So the +1.98 bps / t=+2.47 figure is exploratory.

The CPCV stability run did not repair this. It reported 12 of 15 folds
positive, but 86% of the filtered entries fall in calendar 2021 and 2022
contributes none, so the folds reuse one regime. `summarise_fold_trading` now
reports `fold_vote_is_independent_evidence`, which is `False` for that run.

2020–2025 is therefore spent.

## What this can and cannot show

**Can**: the model is genuinely out of sample at the model-fitting level.
Training stops at 2024-12-31 and the evaluation starts the next day, so no
labelled row from the evaluation period reached the estimator. A collapse here
is real evidence against the candidate, and that asymmetry is worth having.

**Cannot**: it cannot establish an edge. Fold-3 test payoffs covering
2025-02-28..2025-10-16 were read *before* the trend filter and the entry
quantile were chosen, and 2025 H1 — the uptrend this evaluation leans on — sits
inside that window. A researcher who already knows the period rewards a
directional long filter is not testing that filter when applying it there. So:

- A negative result says **this configuration failed**. That is narrower than
  it sounds, and an earlier revision of this document overstated it. I argued a
  negative would falsify the broader edge claim while a positive proved
  nothing; an adversarial review rejected the asymmetry and it is retracted.
  A negative obtained under a configuration selected with knowledge of part of
  the period tells you about that configuration. If it then motivates the next
  configuration on the same window, that is re-mining under another name.
- **Therefore: whatever this returns, it does not license another attempt on
  2025-01-01..2026-06-30.** A successor candidate needs future data that
  neither the model nor the researcher has seen. That is the only remaining
  path to an edge claim, and no amount of care with this window substitutes.
- ACCEPT below means "survived an engineering check", never "has an edge".
- The claim of an edge needs a window untouched at BOTH levels — model and
  researcher. No such window exists in the current data. It has to be future
  data.

`--long-only` deepens this. It removes every low-score SELL and routes the
rolling quantile through a single-model path the CLI had refused outright.
That is a change to the traded strategy and its selection rule, not only to
the plumbing that runs it, whatever the original text below says.

## The frozen configuration

Training:

```
--input artifacts/btcusdt_2020_2026h1.parquet
--metrics-dir artifacts/metrics
--training-end 2024-12-31
--horizon 45
--tp-pct 0.004 --sl-pct 0.002
--label-threshold 0.0004
--round-trip-cost 0.0004
--target profitability
--vol-gate-feature rv_60 --vol-gate-min 0.0013057422 --vol-gate-train-only
```

Evaluation:

```
--backtest-start 2025-01-01 --backtest-end 2026-06-30
--exec-tp-pct 0.004 --exec-sl-pct 0.002 --fixed-tp-sl --tp-floor 0.004 --sl-floor 0.002
--maker-fill-window 5 --maker-exit
--vol-gate-feature rv_60 --vol-gate-min 0.0013057422
--entry-quantile 0.02 --entry-quantile-warmup 1000
--trend-filter-sma 288000
--position-size 0.1
--long-only
```

`--long-only` was added after this document was written and before any result
was read. **It is a material change to the traded strategy, not plumbing.** An
earlier revision called it plumbing; that was wrong and is retracted here.

What actually happened: the frozen command would not execute. The single-model
branch resolved its cutoffs inline and never consulted the rolling quantile,
and the CLI refused `--entry-quantile` without a two-sided model. Both guarded
a real hazard -- on that branch a short fires because the single score is LOW,
so a top-fraction (high) quantile gates it backwards.

But the repair changes what gets traded: every low-score SELL is removed, and a
dynamic cutoff with a warmup now decides entries on a path that previously used
a fixed one. Different bars trade. That is a selection rule.

So this does not restore evidentiary validity, and adding it cannot: the
configuration frozen above was never executable as written, which means no
version of this run tests a strategy that was fully specified before the
evaluation period was available. It is one more reason the exercise is a
post-selection check rather than a holdout -- not a repair that makes it one.

### The short side is DEFERRED, not dropped

This evaluation scores the long side alone, but the intended system trades both
directions. The short side is held back because five successive short models
have failed -- most recently 0 of 4 folds at a pooled -2.08 bps (t=-3.75),
losing even in the fold covering a -41% crash -- and putting a known-losing
book into a holdout would spend the window on a question already answered.

What that means for reading the result:

- A long-only ACCEPT does **not** clear the system for live trading. It clears
  one leg of it. The short leg remains unsolved and is the larger open problem,
  because the long edge is directional and stands aside in downtrends: without a
  working short, the strategy is flat for months at a time (2026 H1: zero
  entries) and the equity curve is not what a two-sided system would produce.
- Sizing, exposure and drawdown figures from a long-only run understate a
  two-sided system and must not be quoted as if they described one.
- The short side needs its own preregistered holdout when a candidate exists.
  This document does not authorise reusing 2025-2026 H1 for it: that window is
  spent by the long evaluation below, whatever its outcome.

Short-side work resumes after this evaluation, on its own data and its own
freeze -- not by adding a short leg to whatever this run produces.

### Where each number came from, and why it is not fitted to the holdout

| value | origin |
|---|---|
| `tp 0.004 / sl 0.002` | screened on 2020–2025 *gated training bars* for resolution rate; 97.85% resolve, the highest of ten candidates, chosen under a stated rule (≥90% resolved, then minimum payoff variance) |
| `rv_60 >= 0.0013057422` | quantile 0.80 of the walk-forward fold-0 train slice, **2020-12-16 to 2022-08-22** — over two years before the holdout starts |
| `entry quantile 0.02` | the selectivity at which the sign flipped in the fold analysis. **This one was chosen by reading fold test payoffs.** It is the weakest link in this document and is recorded as such. |
| `warmup 1000` | used throughout the fold analysis; sized so the selected 2% tail holds ~20 observations before trading |
| `SMA 288000` (200 daily bars) | a convention, fixed before measuring. Two alternatives (a -20% drawdown cap, and both combined) were computed afterwards and are NOT used |
| `cost 4 bps` | 2 × 0.02% maker, limit-only premise, no slippage |

## Evaluation-window composition

| window | move | bars passing gate **and** trend filter |
|---|---:|---:|
| 2025 H1 | +15.7% | 8,548 |
| 2025 H2 | −17.4% | 1,308 |
| 2026 H1 | −31.3% | 0 |

About 197 entries expected at the top-2% cut. 2025 H1 is the only uptrend this
project has ever held out; the claim under test is that the edge is directional,
so an uptrend is the window that can actually falsify it.

## Predictions, stated in advance

1. **2026 H1 produces approximately zero entries.** The trend filter should
   refuse a −31% downtrend outright. Already observed on the current model, and
   it must hold for the retrained one.
2. **2025 H1 carries almost all the entries** and is where the result is
   decided.
3. **The point estimate lands between 0 and +2.5 bps per trade.** The fold
   figure was +1.98; a holdout number materially above that is more likely to
   indicate a wiring fault than a better edge, and will be investigated as one
   rather than reported as a win.

## Decision rule, fixed in advance

Read the **trade-weighted** mean net bps over the whole 18 months, and the
per-half-year breakdown. Not the plain fold mean, and not the total return.

Evaluate in this order. The first branch that matches wins; earlier revisions
left INCONCLUSIVE and REJECT both matching a sparse losing run, which would
have let the reading be chosen after the fact -- exactly where sparse data
makes it most tempting.

1. **INCONCLUSIVE** — fewer than 100 entries, *checked first and regardless of
   sign*. The apparatus failed, not the edge. Report it as such and do not
   reinterpret the number in either direction. A sparse loss is not a
   falsification any more than a sparse win is a confirmation.
2. **ACCEPT** — at least 100 entries, net > 0 over the full window, 2025 H1
   positive, and no half-year worse than −2 bps. This means "survived an
   engineering check on a post-selection period". It is not evidence of edge
   and must not be quoted as one; see "What this can and cannot show".
3. **REJECT** — everything else at 100 entries or more.

A result between these is REJECT. There is no fourth branch, and no rerun with
a different quantile, gate, or window: re-running until a configuration passes
is the failure mode this document exists to prevent, and it applies just as
much to a post-selection check as to a real holdout.

## What is NOT permitted after reading the result

- Changing any value in the frozen configuration and re-running on this window
- Reporting a subset of the holdout that looks better than the whole
- Adding the short side back because the long side underperformed. The short
  side is deferred on its own evidence, and reintroducing it to rescue a weak
  long result would be fitting the direction mix to this window
- Treating "2026 H1 lost nothing" as evidence of anything: zero trades is the
  filter working, not the strategy earning

## Experiment ledger

Gates, thresholds and windows evaluated against fold test payoffs before this
freeze, all of which contribute to the multiple-testing burden:

- volatility gate: rv_60 at the training top quintile; also examined rv_15,
  rv_30, rv_120, atr_pct as candidate gate features (not run)
- entry rule: fixed trained threshold; retrospective top 0.1/0.2/0.5/1/2/5/10/
  25/50%; causal rolling top 2/5/10% at windows expanding/2000/5000
- direction filter: close > SMA200d; drawdown > −20%; both
- barrier: ten (tp, sl) pairs screened
- training scope: full-span with inference gate; gated bars only
- CV: walk-forward 4-fold; CPCV 6 groups choose 2 (15 folds)

Roughly 30 configurations have touched these payoffs. At that count a t of +2.5
on one of them is not surprising by itself, which is the reason this holdout
exists.
