# K=45 causal admission ordering preregistration

Frozen on 2026-09-30 (Asia/Seoul), before computing this ordering audit. This
is Task B, separate from Task A and run after it. It reuses immutable local
predictions and ledgers and performs zero model fits.

## Prior, question, source, and cutoff

The prior probability of success is low. The earlier fixed-fade selection
layer had `Spearman(q, net) = -0.0007`, every decile was negative, and its top
decile was worse than its bottom decile, so the layer was deleted. Earlier
fold-metric work likewise found every causal selector negative; positive
selectors were lookahead. This audit attacks, rather than confirms, the idea
that a causal admission feature can improve the one-slot book.

The motivating `+3.8679 bps` is not feature-selected evidence. It describes
long candidates grouped only because a prior position happened to be open
when they arrived. That busy-slot state is observable at arrival, but no
causal reason yet says those candidates are better. The ordering audit tests
that missing link.

Use only frozen local Binance USD-M BTCUSDT one-minute futures artifacts:

- the backward and forward K=45 candidate ledgers used by the stop-grid audit;
- their frozen PatchTST excursion/range predictions and per-fold STOP-q90
  thresholds;
- `artifacts/btcusdt_2020_2026h1.parquet` for causal entry-time features;
- the existing stop-grid audit helpers and provenance files.

The data cutoff is `2026-06-30T23:59:00Z`. No spot, DEX, external, wallet, or
authenticated exchange data is allowed. Freeze SHA-256 for this plan, runner,
test, and every input in the run manifest.

## Population and endpoint

Start from every triggered, q90-gated candidate in both arms, whether the
first-come book executed it or not. Apply the existing strict boundary rule
`entry_index + 45 < test_end_index`. Analyze `DOWN_BREAKOUT_LONG` and
`UP_BREAKOUT_SHORT` separately; do not pool their different direction
economics. Identity is `(arm, entry_index)`, K is fixed at 45, there is no
stop, and the endpoint is signed linear K45 return minus one 4 bps round-trip
cost, `none_net_lin_bps`. Assert exact equality to the audit-fix candidate
endpoint.

## Ten causal features

All values must be finite and known by the completed trigger-bar close at
`entry_index`; no later bar may enter a feature.

1. `tau`: integer minutes from forecast origin to first 50 bps crossing.
2. `abs_d_tau_bps`: absolute log move from origin close to entry close.
3. `pred_excursion_bps`: frozen PatchTST prediction at the origin.
4. `pred_range_bps`: frozen PatchTST prediction at the origin.
5. `pred_excursion_over_abs_d`: feature 3 divided by feature 2.
6. `gate_margin_bps`: feature 3 minus that fold's frozen STOP q90 excursion
   threshold.
7. `range_60_entry_bps`: `(max(high)-min(low))/close[entry] * 1e4` over bars
   `entry-59..entry`, inclusive.
8. `rv_240_entry_bps`: square root of the sum of squared close log returns
   ending at `entry`, using returns for `entry-239..entry`, times `1e4`.
9. `utc_hour`: trigger-bar close hour, integer 0..23.
10. `utc_weekday`: trigger-bar close weekday, Monday=0 through Sunday=6.

This is 10 features times 2 arms = 20 primary two-sided ordering tests.
Calendar variables are ordinal audit views of cyclic quantities and therefore
have an explicit interpretation caveat. No other feature, transform, lag,
interaction, arm pooling, or missing-data choice may be added after results.

## Ordering statistics

Within each arm-feature cell, rank the full boundary-clean TEST candidate
population by feature. Continuous features use stable equal-count deciles;
ties are ordered by `(pilot_fold, entry_index)` only to make membership
deterministic. UTC hour and weekday use the same stable rule, while the report
must flag tie splitting and cyclic non-ordinality. For every decile report
count, feature minimum/maximum/mean, mean `none_net_lin_bps`, and the existing
Bartlett fold-HAC 95% interval. Empty fold scores stay zero. Use the unchanged
lag rule: primary `min(60,G-1)`, automatic
`min(G-1,floor(4*(G/100)^(2/9)))`, and automatic only when primary/G > 0.5.

For each cell report pooled Spearman rho; a fold-clustered CR1 two-sided test
of the equivalent standardized-rank slope; decile-10 minus decile-1 with each
fold score equal to `sum_D10((y-mu10)/n10) - sum_D1((y-mu1)/n1)` before the
same Bartlett lag and finite-cluster correction; every fold's Spearman; its median,
minimum, maximum, nonfinite count, and negative-fold count.

Monotonicity is frozen as both:

- at least 8 of the 9 adjacent decile-mean changes have the rho direction;
- `|Spearman(decile number, decile mean net)| >= 0.80` with the same sign.

## Hard ordering gate

An arm-feature cell passes only if all are true:

1. pooled `|Spearman| >= 0.05`;
2. both monotonicity conditions above pass;
3. fold-clustered two-sided `p <= 0.0025` (Bonferroni `0.05/20`);
4. the decile-10 minus decile-1 HAC 95% interval excludes zero in the pooled
   rho direction;
5. at least 60% of finite per-fold Spearman values have that direction.

If no cell passes, status is `NO_ORDERING`, write the complete audit and stop.
Do not simulate admission rules, random baselines, thinning baselines, or any
book. This stop is the preregistered honest result.

## Conditional admission replay

Run this section only if at least one cell passes. It remains exploratory and
cannot produce a winner or verdict because feature/direction promotion used
the same TEST ordering audit.

For each passing arm-feature independently, admit an arriving signal only
when its arm slot is empty and its feature is on the favorable side of a
single threshold. Direction is the sign of the preregistered ordering result.
The threshold is the median of that feature among causal triggered candidates
from that fold's TRAIN and STOP blocks only. TEST values, returns, future
signals, and knowledge that a better signal will arrive may not set or change
the threshold. No multivariable combination, fitted selector, threshold sweep,
fold selection, stop-loss, or queue is allowed.

Replay these baselines beside each passing rule:

- first-come: current single-position rule;
- random: 20 fixed seeds 42..61, with the TRAIN/STOP estimated threshold-pass
  probability for that fold and arm;
- rate-only: admit every `n`th idle signal, where
  `n=max(1, round(1 / TRAIN_STOP_pass_probability))`.

The random and rate-only rules must be causal sequential replays. Report their
realized TEST admission rates; do not force a post-hoc TEST count match. A
threshold rule that does not exceed the rate-only baseline is descriptive
evidence of occupancy-rate change, not feature information.

For first-come, every passing threshold rule, every random seed and its
aggregate, and rate-only, report candidate count, trade count, admission rate,
mean `net_lin_bps`, HAC 95%, total $100 PnL, maximum drawdown, and mean holding
minutes. Report pooled, every UTC year, and an explicit 2022 table. Repeat the
no-stop result under the four requested labels `touch`, `gap`, `late`, and
`adverse_extreme`, and assert exact equality across all four.

Against first-come, decompose each rule's trade identities into matched,
added, and dropped sets with the existing exact three-part contribution
identity. Assert reconstruction residual <= `1e-12` bps and report paired HAC
for matched differences.

## Reproducibility and safety

Outputs are a new directory only. Always include manifest, status, results,
verification, SHA-256 output manifest, the enriched causal candidate ledger,
all feature decile rows, ordering summaries, and fold Spearman rows. Conditional
book artifacts exist only if the hard gate passes. `--verify` must validate all
frozen hashes, rebuild every applicable table and report, compare artifacts,
and perform zero fits.

Print peak RSS and abort above 3 GiB. Frozen counters are
`new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, and
`live_orders: 0`. The analysis is exploratory: no winner selection, acceptance
condition, production permission, or revised verdict is allowed.
