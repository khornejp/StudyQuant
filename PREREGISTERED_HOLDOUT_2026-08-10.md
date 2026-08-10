# Preregistered holdout evaluation — frozen 2026-08-10

Written **before** the model is retrained and before any of the holdout is
scored. Nothing below may be changed after the first result is read. If it is
changed, this document is void and the holdout is spent.

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

2020–2025 is therefore spent. This is the one evaluation left.

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
```

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

## Holdout composition

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

- **ACCEPT** — net > 0 over the full holdout, AND 2025 H1 positive, AND no
  half-year worse than −2 bps. Verdict is "promising, not proven": n ≈ 200 is
  one window, not a track record.
- **REJECT** — net ≤ 0 over the full holdout.
- **INCONCLUSIVE** — fewer than 100 entries. The apparatus, not the edge, is
  what failed; report it as such and do not reinterpret the number.

A result between these is REJECT. There is no fourth branch, and no rerun with
a different quantile, gate, or window — that is what spending a holdout means.

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
