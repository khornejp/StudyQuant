# Independent review and economic audit of the frozen continuous-200 direction classifier

Date: 2026-09-22 (Asia/Seoul). Session: new-session review requested by
`REVIEW_HANDOFF_2026-09-22.md`.

All work below is read-only. No frozen plan, runner or output directory was
modified. No new model was fitted, no backtest engine was run, no order was
placed, and no new calendar data was collected. Scripts used for the new
measurements live in the session scratchpad, not in the repository, because
they are diagnostics rather than a frozen experiment; their full listings are
reproduced in the appendix so any of the numbers can be recomputed.

## 1. Verification result

The no-fit reconstruction requested by the handoff was run:

```
& '.\venv_btcusdt\Scripts\python.exe' -B -u -m out.run_patchtst_direction_classwise_selective_continuous_200 --verify
```

Exit code 0, final output `{"status": "PASS", "all_200_folds_rebuilt": true}`.

That command re-asserts SHA-256 over the runner, the plan, the base module and
every reused checkpoint, rebuilds all TEST predictions from the saved models,
and compares the rebuilt frame against `predictions.parquet` at `atol=2e-6`
plus the full `results.json` comparison. It passed.

Independent reconciliation of the log, done separately from the script's own
assertions:

| Quantity | Handoff claim | Recomputed from the verify log | Match |
| --- | --- | --- | --- |
| Evaluated folds | 198 | 198 fold lines | yes |
| Calendar slots | 406-605, consecutive | ascending, no gaps other than the abstentions | yes |
| Causal abstentions | 427, 428 | exactly `427,428` absent | yes |
| TEST rows | 56,204 | 56,204 | yes |
| Accepted rows | 6,477 | 6,477 | yes |

The reused/new model split (66 reused, 1,122 new) is asserted by the manifest
against on-disk digests inside the `--verify` path and passed there; it was not
separately recounted by hand.

Conclusion: **the frozen continuous-200 artifact is reproducible and its
reported counts are correct.** The `CONTINUOUS_200_FAIL` outcome, selected BA
.554771 against forced BA .525646, stands as reported.

## 2. The question nobody asked: what is this worth in basis points?

Every gate in the frozen plan is an accuracy or precision gate. The plan
explicitly forbids fees, slippage, TP/SL and backtests, so the pipeline has
never converted its accuracy into money. Doing that conversion is what this
audit adds, by joining `predictions.parquet` to
`artifacts/btcusdt_2020_2026h1.parquet` and taking each row's forward 15-bar
return on the model's own predicted side.

### 2.1 How much money is on the table

| Quantity | Value |
| --- | --- |
| Rows | 56,204 |
| Mean forward H15 return | +0.056 bps (t = 0.53, no drift) |
| Mean absolute H15 move | **16.383 bps** — perfect-foresight gross per trade |
| Median absolute move | 11.042 bps |
| Share with \|move\| >= 4 bps | 0.7990 |
| Share with \|move\| >= 25 bps | 0.1922, carrying 52.6% of all movement |
| Share with \|move\| >= 50 bps | 0.0487, carrying 22.8% of all movement |

The user's premise is correct and is now quantified. Eighty percent of these
bars move more than the 4 bps round-trip cost within fifteen minutes, and the
average bar moves four times the cost.

### 2.2 How much of it the model captures

Gross basis points per trade, following the predicted side, before cost:

| Set | n | gross | se | t | median | hit |
| --- | --- | --- | --- | --- | --- | --- |
| Forced-all | 56,204 | +0.525 | 0.106 | 4.97 | +0.979 | .5257 |
| Accepted (frozen q90 gate) | 6,477 | +1.157 | 0.377 | 3.07 | +2.682 | .5547 |
| Rejected | 49,727 | +0.443 | 0.109 | 4.07 | — | .5219 |

Net of the 4 bps round trip the accepted set is **-2.843 bps per trade**. The
break-even hit rate implied by the realized payoff (average win 19.247, average
loss 21.381) is 0.6247 against a realized 0.5547.

The model therefore captures roughly seven percent of the movement that is
present in the tape. That gap, not the BA shortfall, is the real finding.

Per quarter of fifty folds the accepted gross is +2.614 (t = 3.03), +0.499
(t = 0.59), +1.031 (t = 1.58) and +0.575 (t = 0.90). The edge is concentrated
in the first quarter and is not separable from noise afterwards.

### 2.3 Where it loses

Accepted rows stratified by realized absolute move, a diagnostic that could
never be used as a gate:

| \|H15\| | n | hit | mean signed bps |
| --- | --- | --- | --- |
| 0-4 | 1,059 | .5165 | +0.103 |
| 4-10 | 1,457 | .5580 | +0.857 |
| 10-25 | 2,237 | .5914 | +3.184 |
| 25-50 | 1,226 | .5620 | +4.169 |
| **50+** | **498** | **.4438** | **-12.246** |

The 498 large-move rows, 7.7% of the accepted set, destroy 6,098 bps against
the 13,592 bps earned by everything else.

## 3. Three proposed repairs, all falsified on existing data

Before recommending anything, each obvious repair was measured.

### 3.1 A path-dependent exit does not help; it hurts

The frozen design exits at the fixed H15 endpoint, which looks like the worst
possible exit. It is not.

On the accepted set the maximum favorable excursion averages +19.814 bps while
the maximum adverse excursion averages -21.241 bps. The path is almost exactly
symmetric, so a take-profit truncates winners without truncating losers. First
touch accounting over the fifteen bars, with same-bar ambiguity resolved
against the position:

| TP / SL | gross, same bar against | gross, same bar for | net @ 4 bps |
| --- | --- | --- | --- |
| terminal exit (frozen) | +1.157 | +1.157 | -2.843 |
| 8 / 8 | +0.267 | +0.810 | -3.733 |
| 12 / 12 | +0.487 | +0.772 | -3.513 |
| 20 / 8 | +0.932 | +1.135 | -3.068 |
| 20 / 20 | +0.651 | +0.719 | -3.349 |

All nine geometries come in below the endpoint under either same-bar rule, so
the tie-break is not what decides it. The margin is not uniform, though: under
the favourable rule 20 / 8 trails the endpoint by 0.022 bps. **The claim this
supports is that these nine geometries fail on this signal, not that barriers in
general are a dead lever.**

### 3.2 Four global confidence cutoffs, ranked with lookahead, all fall short

Ranking the full 56,204 origins by confidence **on TEST itself** — deliberate
lookahead, therefore an optimistic ceiling — and taking the top slice:

| top | n | gross | t | net @ 4 bps |
| --- | --- | --- | --- | --- |
| 11.5% | 6,463 | +1.366 | 3.45 | -2.634 |
| 5.0% | 2,810 | +2.103 | 3.14 | -1.897 |
| 1.0% | 562 | +2.822 | 1.73 | -1.178 |
| 0.1% | 56 | +2.605 | 0.46 | -1.395 |

None of these reaches 4 bps, and significance disappears below the 2% slice.

**Correction.** An earlier version of this section called that an upper bound
and concluded that coverage is not a lever. That inference was wrong. The frozen
accept rule fits a threshold per fold and per predicted class, so it selects a
different subset than any single global confidence prefix; a global top-k is not
the supremum over the rules that are actually available. Sweeping every prefix
rather than these four finds a better one — 705 rows, 1.254% coverage,
**+3.269 bps** — which is above the +2.822 quoted here and still below the 4 bps
cost. What the section supports is that these cutoffs fail, and that the best
global prefix anywhere on this curve does not clear cost. It does not establish
that no STOP-fitted rule could.

### 3.3 An expected-value gate is worse than a confidence gate

Magnitude is genuinely predictable ex ante. A purely causal trailing-volatility
proxy (standard deviation of the previous sixty one-minute log returns, scaled
by sqrt(15)) correlates 0.4407 with the realized absolute H15 move, against
0.0935 for the classifier's own confidence. Deciles of the resulting expected
value rank move size cleanly, from 11.91 bps in the bottom decile to 30.49 bps
in the top.

It does not help:

| Ranked by | top 5% gross | top 1% gross |
| --- | --- | --- |
| confidence | +2.103 | +2.822 |
| trailing vol alone | +0.630 | +0.352 |
| edge x trailing vol (60) | +1.482 | +0.505 |
| edge x trailing vol (240) | +1.606 | +1.879 |

The top expected-value decile has mean absolute move 30.49 bps and still
returns only +1.056 bps gross.

**Correction.** An earlier version explained this by saying directional skill
decays as move size grows. Tested directly, that mechanism is not supported.
Directional accuracy against trailing volatility has no trend over the full
population (p = 0.365); on accepted rows the slope is -0.001356 per bp at
p = 0.071 and is not monotone, with hit rates by volatility decile running
.579, .552, .560, .557, .565, .573, .560, .533, .559, .509. What is real is the
collapse conditioned on the *realized* move — the top realized-magnitude decile
hits .4583 for -9.266 bps — but that is a diagnostic conditioned after the fact,
not the ex-ante quantity an expected-value gate ranks on. The finding that
stands is narrower: ranking by `edge x volatility` fails on this data. Why it
fails is not established here, and this section is not evidence that a magnitude
head is useless in general.

## 4. What the model actually learned

The classifier is a mean-reverter, and not a subtle one.

- `corr(predicted side, prior 15-minute return) = -0.4554`
- On accepted rows the predicted side agrees with the prior 15-minute move on
  **4.55%** of trades. It fades 95.45% of the time.

A one-line rule with no model, no features and no training — take the side
opposite the prior fifteen-minute move — earns +0.602 bps (t = 5.70) across all
56,204 origins.

On the classifier's own 6,477 accepted bars:

| Rule on the same bars | n | gross | se | t |
| --- | --- | --- | --- | --- |
| Model's predicted side | 6,477 | +1.157 | 0.377 | 3.07 |
| Plain fade of the prior 15 minutes | 6,477 | **+1.340** | 0.377 | 3.55 |
| Model minus fade | 6,477 | **-0.184** | 0.146 | -1.26 |

The two agree on 95.41% of accepted bars, and where they differ the model is on
the worse side. **The directional head contributes nothing measurable over a
one-line reversion rule, and the point estimate of its contribution is
negative.** What the pipeline did produce is a selection effect: the fade rule
earns +1.340 bps on the accepted bars against +0.505 on the rejected ones and
+0.602 overall, so the gate does concentrate the reversion edge by roughly a
factor of two. The value is in the gate, not in the direction.

Two things were checked before that was written down. First, whether it is a
tautology: the model was trained where reversion pays, so of course it fades.
Isolating the 297 accepted bars where the model and the fade take opposite
sides answers it — the model's side is worse there by 4.004 bps (t = -1.260), so
its independent directional judgement shows no gain, and the finding is not
circular. Second, whether a paired test is the right one when the two sides
agree 95% of the time. It is: agreeing bars contribute exactly zero to the
difference and drop out, and the pooled t matches the discordant-only t. The
95% confidence interval on the difference is about [-0.470, +0.102], so the
claim this supports is "no measurable improvement", not "proven equivalent";
and the ordinary t ignores time clustering, which would widen it further.

This also explains section 2.3 without any appeal to noise. Large moves
continue the prior fifteen-minute move 52.83% of the time, while the model
fades 95.45% of the time, so it is structurally on the wrong side of exactly
the bin that carries a quarter of all price movement. Flipping the side
against strong prior moves was tested and does not repair it: at a 60 bps prior
threshold the accepted gross moves from +1.157 to +1.437, still -2.563 net.

## 5. Verdict on the design

The handoff asked whether the design is sound. It is internally consistent,
causally clean and reproducible — and it is aimed at the wrong quantity in
three places, of which only the third turned out to matter.

1. **The target discards magnitude.** BCE on the sign of the H15 return gives a
   one-basis-point bar and an eighty-basis-point bar identical gradient weight.
   Twenty percent of rows move less than the cost and are pure noise, yet
   consume twenty percent of the gradient. This is real. Section 3.3 shows that
   *ranking* by a magnitude proxy does not produce basis points, which is a
   weaker statement: ranking reorders what a model already learned, while the
   target changes what it learns. Raising the training target above the noise
   floor is therefore still untested here, and is the first rung of the
   follow-up experiment.
2. **The accept rule ranks by confidence, not by expected value.** Also real,
   and section 3.3 shows that this particular expected-value proxy does not
   beat confidence on this signal.
3. **The learned function is short-horizon mean reversion worth about
   0.6 bps.** This is the binding defect. It is a genuine microstructure
   effect, it is statistically solid at t = 5.70, and it is roughly one sixth
   of the round-trip cost. No gate, loss function, exit rule or architecture
   can turn a 0.6 bps effect into a 4 bps one.

The correct reading of `CONTINUOUS_200_FAIL` is therefore not "the classifier
needs a better threshold." It is that 1,188 neural fits rediscovered the
bid-ask bounce, and the bounce does not pay a 4 bps toll.

## 6. What the literature says, and what follows

Relevant external work, none of it previously applied in this project:

- *Algorithmic crypto trading using information-driven bars, triple barrier
  labeling and deep learning*, Financial Innovation 11(1), 2025. CUSUM-filtered
  event sampling combined with triple-barrier labeling beats time bars and
  next-bar prediction on BTC and ETH tick data from 2018 to mid-2023, with
  consistently positive performance after transaction costs. The paper's stated
  diagnosis of next-bar labeling — that it "tends to learn from many noisy
  observations" — is precisely what section 4 measured here.
  https://link.springer.com/article/10.1186/s40854-025-00866-w
- *Exploring Microstructural Dynamics in Cryptocurrency Limit Order Books*,
  arXiv 2506.05764. On BTC/USDT, simpler models with better-engineered and
  better-filtered inputs match or exceed DeepLOB and Conv1D+LSTM. Input quality
  dominates architectural depth. https://arxiv.org/abs/2506.05764
- *The Label Horizon Paradox*, arXiv 2602.03395. Single fixed-horizon return
  targets are a poor supervision signal; multi-horizon supervision improves
  out-of-sample IC and Sharpe and stabilizes across regimes.
  https://arxiv.org/pdf/2602.03395
- Direction-aware and asymmetric loss functions for financial forecasting
  report 2.0 to 6.1 percentage point directional-accuracy gains over MSE/MAE
  baselines. Useful, but section 3.3 indicates that accuracy gains of that size
  would not close this particular gap.

Two of these point at the same place: the sampling scheme and the label, not
the head. The current pipeline is time bars plus fixed-horizon sign — exactly
the baseline the 2025 crypto paper reports beating after costs.

One caution against over-reading that. Section 3.1 found barriers actively
harmful on these origins. The difference the literature claims is that barriers
are applied to *event-selected* origins rather than to every time bar, so the
two results are not yet in contradiction — but the untested part is the event
selection, not the barrier.

## 7. Recommended next hypothesis

Ranked by expected payoff against cost of falsification. All use existing data.

**First: train a continuation model on event-selected origins.** The measured
structural defect is that the system has no continuation capability whatsoever
(4.55% agreement with the prior move) while 52.83% of large moves are
continuations and large moves carry 23% of all movement. A model whose origins
are CUSUM breakout events rather than every minute, and whose target is whether
the move extends, is a genuinely distinct learning objective rather than
another threshold sweep. It attacks the one bin where the current system is
anti-predictive. The matched baseline is trivial and must be included: plain
momentum on the same event origins.

**Second: replace time-bar sampling with information-driven bars.** Dollar or
volume bars over the same history, same features, same PatchTST, same folds —
an ablation that isolates the sampling scheme. Cheap, because nothing but the
index construction changes.

**Third, and this should be stated plainly rather than buried:** the measured
directional information in this family is between 0.5 and 1.4 bps per trade,
against a 4 bps round trip. That is the same conclusion already recorded in
`configuration-exhausted-cost-is-the-binding-constraint`, now reproduced on a
completely different model family. Any candidate that does not show a gross
edge of at least 6 to 8 bps on its own out-of-sample origins should be
abandoned early, because the remainder is swallowed by cost.

Deliberately not recommended: another confidence or quantile sweep, a magnitude
head on this classifier, TP/SL tuning, new calendar data, spot inputs, live
orders.

## 8. Limitations

- The Codex cross-examination mandated by this project's work loop ran on
  2026-09-23 after the usage limit reset. Every figure in sections 2 and 4 was
  reproduced independently to six decimals. It also found three overstatements,
  each corrected in place above: the conviction ceiling was not an upper bound
  (3.2), the decay-with-size mechanism was not supported when tested directly
  (3.3), and the barrier conclusion holds only for the nine geometries tried
  (3.1). The corrections narrow the claims; none of them reverses a result.
- Sections 3.2 and 3.3 deliberately rank on TEST. They are optimistic estimates
  used to kill hypotheses, and no positive claim is made from them. As 3.2 now
  records, an optimistic estimate is not the same thing as an upper bound.
- Section 3.1 assumes a fill at first touch of a bar high or low. Both same-bar
  tie-break rules are now reported, because the margin under the favourable rule
  is as small as 0.022 bps. It is an approximation of execution, not a backtest.
- The fade baseline in section 4 uses the prior fifteen closes and is causal,
  but it is a diagnostic rule, not a strategy proposal; its +0.602 bps is far
  below cost and it is reported only to attribute the model's output.
- No claim of profitability, executability or live readiness is made anywhere
  in this document.

## Appendix: diagnostic scripts

The four scratchpad scripts used above are `ev_audit.py` (section 2),
`mfe_audit.py` (3.1), `conviction_ev.py` (3.2 and 3.3), `reversion_test.py` and
`attrib.py` (section 4). Each reads only `predictions.parquet` and
`artifacts/btcusdt_2020_2026h1.parquet`, asserts that `open_time` matches the
bar index before computing anything, and re-derives `target_down` from the
price series as a parity check against the frozen labels. That parity assertion
passed in every script, which is itself an independent confirmation that the
frozen label polarity is correct: `target_down == 1` if and only if the forward
fifteen-bar return is negative.
