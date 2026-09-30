# K=45 short-signal veto preregistration

Frozen on 2026-09-30 (Asia/Seoul), before computing any Task D ordering or
book result. This is an exploratory zero-fit test. It cannot select a winner,
change the existing validation verdict, or authorize trading.

## Prior, source, cutoff, and hypothesis

The prior probability of success is low. Earlier causal selectors in this
repository usually failed ordering gates. Task C supplied a post-hoc clue:
relative to `LONG_ONLY`, the shared book dropped 804 long trades whose mean was
-9.6111 bps, but the added short trades lost more than those dropped longs
saved. The values 804, -9.6111 bps, and the informal “remove 804 and gain about
4.03 bps” arithmetic are not Task D results. They are only upstream
reproduction checks and motivation.

The frozen hypothesis is: a live opposite-arm short trigger contains causal
information about the subsequent K=45 return of an arriving long candidate.
If the ordering gate passes, reject that long candidate without entering the
short trade. The slot remains empty.

This feature family differs from Task B. Task B tested ten attributes of the
long candidate itself. Task D tests whether an already observed signal from
the opposite arm exists and describes that signal. Task B's `NO_ORDERING`
therefore does not exclude this hypothesis.

Use only immutable local Binance USD-M BTCUSDT futures artifacts from Tasks B
and C and their already frozen market and funding inputs. Predictions remain
inputs. The data cutoff is `2026-06-30T23:59:00Z`. No spot, DEX, external,
wallet, or authenticated exchange data is allowed.

## Population and endpoint

Use all boundary-clean `DOWN_BREAKOUT_LONG` candidates in Task B
`causal_candidates.parquet`, whether `LONG_ONLY` executed them or not. Preserve
the existing rule `entry_index + 45 < test_end_index`, K=45, no stop, and one
4 bps round-trip cost. Endpoint is Task B `none_net_lin_bps`; assert exact
equality to the frozen audit endpoint. Candidate identity is `candidate_id`.

Opposite-arm triggers are all boundary-clean `UP_BREAKOUT_SHORT` candidates in
that same frozen ledger, regardless of whether any prior book executed them.
A short trigger at index `s` is live on the half-open interval `[s, s+45)`.
A same-index trigger is already known at the completed trigger-bar close and is
therefore active for a long candidate at that index. This convention uses no
future bar or future signal.

## Five preregistered opposite-arm features

For a long candidate at index `t`, compute only:

1. `short_signal_active`: one when at least one short trigger has
   `s <= t < s+45`, otherwise zero.
2. `short_signal_age_min`: `t-s` for the most recent short trigger with
   `s <= t`.
3. `short_signal_count_60m`: number of short triggers in `[t-59, t]`.
4. `short_gate_margin`: frozen `gate_margin_bps` of the most recent short
   trigger with `s <= t`.
5. `short_abs_d_tau_bps`: frozen `abs_d_tau_bps` of that same trigger.

If no prior short trigger exists, features 2, 4, and 5 stay missing. Do not
impute, add a sentinel, or turn missingness into a sixth feature. Report the
missing count and rank each continuous feature on finite rows only.
`short_signal_active` and `short_signal_count_60m` remain defined for every
long candidate. Assert every nonmissing age and count uses only indices at or
before `t`.

This is five primary tests. They are correlated and were motivated by the same
post-hoc clue, so multiple-testing risk is high. Keep Task B's more conservative
two-arm family cutoff `p <= 0.0025`; do not relax it to `0.05/5` after reducing
the family.

## Ordering audit and hard gate

For continuous features, use Task B's unchanged stable equal-count deciles,
with ties broken only by `(pilot_fold, entry_index)`. For
`short_signal_count_60m`, use the same stable deciles and report tie splitting.
For `short_signal_active`, report exactly two bins, inactive then active.

For every feature/bin report count, missing count, feature minimum, maximum and
mean, mean `none_net_lin_bps`, and the existing Bartlett fold-HAC 95% interval.
Use the unchanged fold grid and lag rule: primary `min(60,G-1)`, automatic
`min(G-1,floor(4*(G/100)^(2/9)))`, and automatic only when primary/G exceeds
0.5.

For every feature report pooled Spearman; Task B's fold-clustered CR1
two-sided standardized-rank test; highest-bin minus lowest-bin with Task B's
fold-score HAC construction; every fold's Spearman; median, minimum, maximum,
nonfinite count, negative count, and share agreeing with the pooled direction.

Continuous-feature monotonicity is unchanged from Task B:

- at least 8 of 9 adjacent decile-mean changes follow pooled-rho direction;
- absolute Spearman between decile number and decile mean is at least 0.80,
  with the pooled-rho sign.

Binary `short_signal_active` cannot support a ten-bin shape claim. Its frozen
substitute requires both bins to contain at least 100 candidates and the
active-minus-inactive HAC 95% interval to exclude zero in pooled-rho direction.
The usual fold-direction requirement still applies. No synthetic deciles or
within-bin tie order may manufacture monotonicity.

A continuous cell passes only if all Task B conditions hold: absolute pooled
rho at least 0.05, both monotonicity conditions, clustered two-sided p at most
0.0025, directional highest-minus-lowest HAC interval, and at least 60% of
finite fold Spearman values in pooled direction. The binary cell passes only
if absolute pooled rho is at least 0.05, clustered p is at most 0.0025, both
groups have at least 100 rows, active-minus-inactive HAC is directional, and
at least 60% of finite fold values agree.

The veto replay is unlocked only if `short_signal_active` itself passes. A
continuous feature cannot unlock a rule that does not use that feature. If it
does not pass, status is `NO_ORDERING`; write the complete audit and stop.
Do not simulate any book or baseline.

## Conditional veto replay and baselines

Run this section only after the binary hard gate passes.

- `LONG_ONLY`: reproduce Task C's one-slot long book. Required upstream gate:
  3,066 trades and mean +0.4550 bps within report rounding.
- `SHORT_SIGNAL_VETO`: before slot admission, reject every long candidate with
  `short_signal_active=1`. Rejected candidates never queue. No short is traded.
- `RANDOM_EXCLUDE_seed`: for 1,000 fixed seeds 42 through 1041, randomly reject
  exactly the same number of candidate arrivals as the veto rejected, without
  replacement, then replay the same one-slot book.
- `RATE_ONLY`: make a deterministic, outcome-blind periodic mask with exactly
  the veto's candidate-pass count. For candidate ordinal `i` among `N`, target
  pass count `M`, accept when
  `floor((i+1)*M/N) > floor(i*M/N)`. Then replay the same one-slot book.
- `OPPOSITE_VETO`: accept a long candidate only while
  `short_signal_active=1`, then replay the same one-slot book.

The matched random object is the number of rejected candidate arrivals, not a
post-hoc force-match of executed trades. Report random trade-count and mean
distributions. Veto percentile is the empirical rank
`(1 + count(random_mean <= veto_mean)) / 1001`; no seed may be selected.

For every deterministic rule and the random aggregate/distribution, report
candidate count, trade count, candidate pass rate, executed admission rate,
mean net linear bps, HAC 95%, total PnL at fixed $100 notional, maximum
drawdown, and win rate. Produce pooled, every UTC year, and explicit 2022
tables.

Against `LONG_ONLY`, decompose each deterministic rule by candidate identity
into matched, added, and dropped sets. Use the existing exact three-term mean
identity, assert reconstruction residual no more than `1e-12` bps, and report
the paired matched difference with HAC.

Attach real funding using Task C's frozen rule
`entry_time < funding_time <= exit_time`. For leverage
`L in {1,2,3,5,10,20}`, report `margin_cost_bps=4L`, per-trade actual funding,
account mean/total PnL/maximum drawdown, and account matched decomposition.
Never replace per-trade funding with an arm average. No MMR or liquidation
claim is permitted.

## Integrity, outputs, and safety

Write only `out/patchtst_k45_short_signal_veto_20260930`. Freeze this plan's
SHA-256 before implementation and freeze plan, source, test, and all input
hashes in `manifest.json` before Task D computation. Outputs always include
the enriched long-candidate ledger, all bin rows, ordering summary, all fold
Spearman rows, report, results, status, verification, and SHA-256 output
manifest. Conditional book artifacts must not exist after `NO_ORDERING`.

`--verify` validates frozen hashes, rebuilds every applicable output, compares
all artifacts, and performs zero fits. Print peak RSS and abort above 3 GiB.
Frozen counters are `new_model_fits: 0`, `new_orders: 0`,
`external_data_added: 0`, and `live_orders: 0`.

