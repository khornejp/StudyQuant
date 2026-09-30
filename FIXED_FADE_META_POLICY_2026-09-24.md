# Fixed-Fade Meta-Policy preregistration — 2026-09-24

## Status and frozen hypothesis

This plan was written before any M1–M4 fit. All earlier experimental results
were discarded before this run. No discarded metric or checkpoint is an input,
comparison, or motivation. The experiment is retrospective: folds 406–605 and
their dates are not an untouched holdout. No live order, authenticated exchange
action, or wallet is authorized (`new_orders: 0`). The frozen claim is narrow:
once direction is fixed opposite the prior H15 move, `X(t)` may rank origins
whose terminal fade clears observed funding and 4 bps round-trip cost.

Data source: local Binance USD-M BTCUSDT one-minute futures parquet and public
monthly funding-rate archives, collected locally by 2026-08-14. Market/funding
cutoff is 2026-06-30 UTC; evaluated fold 605 ends 2025-12-31 UTC. The run hashes
this plan, every executed source module, every input parquet, all funding ZIP
inputs, and the zero-fit pre-fit record before fitting.

## Decisions made before fit

1. **Fold grid.** Use folds 406–605 from the fixed 180-day TRAIN / 3-day STOP /
   3-day TEST calendar. Two hundred consecutive 3-day TEST blocks give paired
   resolution for the registered 0.25%–5% coverage curves without changing the
   calendar between arms. No earlier outcome selected this grid. Data-quality
   folds are abstained before fitting and shared by clock arms.
2. **Side handling.** Every eligible non-tie origin uses
   `s=-sign(log(close[t]/close[t-15]))`. Side is never an output head. Short and
   long are frozen and reported separately. Exact equality to the negative
   prior sign is asserted. Correlation is reported only when both signs occur;
   a single-signed population reports null instead of treating undefined
   correlation as failure.
3. **Funding.** For a positive funding rate, a long pays and a short receives:
   `funding_bps=s*sum(rate)*1e4` over `t < settlement <= t+h`, and
   `r_net=s*return_h*1e4-4-funding_bps`. Funding is label-only future
   information. Raw Binance event timestamps are floored to their containing
   UTC minute because the archive can carry millisecond jitter. Entry `close[t]`
   is the end of minute `t`, simultaneous with the start of minute `t+1`. A
   settlement stamped at `t+1` is therefore included. This conservative
   boundary charges a simultaneous payment.
4. **Eligibility and pinned features.** M0–M3 use clock origins with
   `valid & book_fresh & trade_fresh & side!=0 & known_label`. M4 replaces only
   the origin marks. The 35 upstream channels, in order, are:

   ```text
   short_return_1, short_return_3, short_return_5, short_return_10,
   short_return_15, short_body, short_close_location, short_shadow_rejection,
   short_ema_gap_5, short_ema_gap_10, short_ema_gap_15, short_close_zscore_5,
   short_close_zscore_10, short_close_zscore_15, short_voladj_return_5,
   taker_sell_imbalance_1m, taker_sell_imbalance_3m,
   taker_sell_imbalance_5m, taker_sell_imbalance_15m,
   taker_sell_impulse_3_15, signed_sell_volume_intensity_5m,
   short_return_5_x_oi_change_5m, short_return_15_x_oi_change_15m,
   long_crowding_change_5m, taker_sell_ls_change_5m,
   premium_short_pressure_change_5m, estimated_funding_pressure_uncapped,
   funding_pressure_change_5m, funding_pressure_change_15m,
   funding_pressure_acceleration_15m, high_low_range, body_pct, rv_5, rv_15,
   atr_pct
   ```

   Five appended channels are `ema_5_slope`, `ema_20_slope`, `bb_squeeze_20`,
   `return_sign_run_15`, and `ema_gap_5_minus_15`. Code asserts the 35+5 order;
   each new manifest records it directly. No archived manifest supplies it.
5. **Execution convention.** Feature cutoff and decision use completed minute
   `t`; label entry is `close[t]`; terminal exit is `close[t+h]`. This is a
   diagnostic, not an executable next-open backtest. The 4 bps charge is a
   conservative synthetic round-trip cost.

## Frozen labels, models, and arms

`q=P(r_net,15>0|X)` uses BCE. `m=E[r_net,15|X]` uses squared error after a
TRAIN-only mean-absolute-return scale. M1 loss is `BCE + MSE`. The pinned
encoder has two 48-wide, four-head Transformer layers and a 32-wide output MLP.
AdamW uses learning rate 0.001, weight decay 0.00001, batch size 1024, seeds
42/43/44, maximum 15 epochs, patience 3, and TRAIN-only channel
standardisation. Every learned arm fits fresh in this run. Epoch selection uses
STOP loss. Ensemble STOP `q` alone fits coverage thresholds; TEST never fits a
threshold. Frozen curves are 0.25%, 0.5%, 1%, 2%, and 5%; primary is 0.5%.
Acceptance uses `q>=threshold`, so tied scores can raise realised coverage above
target. Realised TEST coverage is always reported.

- **M0:** fresh fixed fade on every eligible clock origin, zero fits.
- **M1:** two heads (`q`, `m`), terminal H15 exit.
- **M2:** M1 plus q25/q50/q75 pinball heads for H15 fixed-side MFE and MAE;
  auxiliary loss weight 0.25. These heads never alter exit or selection.
- **M3:** M1 plus q25 pinball heads for `r_h-r_15`, `h in {30,45,60}`;
  auxiliary loss weight 0.25. Extend stepwise to the longest horizon for which
  every preceding q25 is strictly positive; otherwise exit H15.
- **M4:** exact M1 model/loss fit fresh on causal dollar-bar origins. For UTC
  day `d`, `Theta_d=median(total quote_volume of each complete calendar day
  d-30..d-1)/96`. A complete day has 1,440 unique, minute-aligned records from
  00:00 through 23:59 UTC. If any calendar day is missing or incomplete, day
  `d` emits no dollar origins. Accumulation is continuous across eligible UTC
  midnights. Equality closes the current minute, overshoot is carried by
  subtraction, and at most one origin is emitted per minute. M4 is paired with
  the current run's clock-trained M1 rescored on the same dollar origins. This
  controls scored returns but not training-population shift; the contrast is a
  bundled policy comparison and cannot identify dollar sampling as the cause.

M2/M3/M4 each change one registered policy item relative to M1. M3 comparisons
use H60-complete common origins. Barrier exits (+10/-10 and +20/-10, same-minute
dual touch against the position) are diagnostics only.

## Pre-fit zero-fit measurements

Frozen from `out/fixed_fade_meta_policy_20260924/prefit.json`, generated with
zero fits, zero backtests, and zero orders:

- 158 folds are evaluable: 406, 408–411, 413, 415–417, 420, 422, 424–426,
  429–439, 441–443, 445–448, 450–453, 455, 457–460, 462–474, 476, 478,
  480–483, 485, 487–497, 499, 502–509, 511, 513–520, 522–523, 525,
  527–544, 546, 548–551, 553–556, 558–560, 562–572, 574, 576–583,
  585–586, 588, 590–595, 597–600, 602, and 604.
- 42 folds abstain: 407, 412, 414, 418, 419, 421, 423, 427, 428, 440, 444,
  449, 454, 456, 461, 475, 477, 479, 484, 486, 498, 500, 501, 510, 512,
  521, 524, 526, 545, 547, 552, 557, 561, 573, 575, 584, 587, 589, 596,
  601, 603, and 605. Exact arm/split counts are frozen in `prefit.json`.
- Eligible TEST origins: 44,932 total; 22,564 long; 22,368 short. Exactly 21
  otherwise feature-valid clock origins are excluded because prior H15 is flat.
- `z=1` base rate: 0.418721623787056 overall, 0.4178780358092537 long,
  0.4195726037195994 short. Target is not degenerate under the registered
  5%–95% rule. Fixed-side correlation is -0.9999999999999998.
- Overall H15 means in bps: gross 0.6102815254612025, funding
  0.001083791062049105, net -3.390802265600847.
- Long H15 means in bps: gross 0.6144848193786346, funding
  0.017121897713170478, net -3.4026370783345357.
- Short H15 means in bps: gross 0.6060414001056523, funding
  -0.015094849785407198, net -3.3788637501089407.
- Overall net distribution: rows 44,932; std 25.33471941223341; SE
  0.11951935028855717; t -28.370320432753253; min -373.9635402742429;
  q01 -79.51257525089954; q05 -40.06704072677358; q25
  -13.873402000321052; median -3.1239145485560913; q75 7.905393680810561;
  q95 32.45365085482432; q99 65.06316207506191; max 364.6310721234709.
- Long net distribution: rows 22,564; std 26.10208122031996; SE
  0.17376691512502063; t -19.58161641925006; min -358.2898459457256; q01
  -81.99245237838619; q05 -40.82204383947646; q25 -14.011606553146091;
  median -3.235997809911014; q75 8.069350224578335; q95 32.77180569385017;
  q99 68.0865848059737; max 364.6310721234709.
- Short net distribution: rows 22,368; std 24.53690905788386; SE
  0.16406134824718183; t -20.595123630327603; min -373.9635402742429; q01
  -76.84420767288613; q05 -39.17275286120557; q25 -13.751533587887828;
  median -3.0138524296490186; q75 7.767643206496981; q95
  31.964578059153457; q99 61.5842895626655; max 245.48022351949484.
- Funding settlement exposure: 1,253 origins, share 0.02788658417163714,
  spanning 1,253 settlements.
- Primary 0.5% STOP support per fold: min 1.24 expected rows, median 1.435,
  max 1.435; 158 folds are below 2 expected rows; the registered
  `enough_for_stable_per_fold_tail` flag is false.
- Model-free M0 phase-balanced gross measurements:

  | Coverage | Step | Phases | Rows/phase min | median | max | Gross mean across phases | Min phase | Max phase |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | 0.0025 | 400 | 400 | 112 | 112.0 | 113 | 0.609661094612707 | -8.046761032407863 | 8.051847784486007 |
  | 0.005 | 200 | 200 | 224 | 225.0 | 225 | 0.6103299286515621 | -3.8489128535450456 | 4.898427544128727 |
  | 0.01 | 100 | 100 | 449 | 449.0 | 450 | 0.6102606606618025 | -1.8668568460444923 | 2.885137364375609 |
  | 0.02 | 50 | 50 | 898 | 899.0 | 899 | 0.6104086047394585 | -1.3899717702554077 | 2.37390887349725 |
  | 0.05 | 20 | 20 | 2,246 | 2,247.0 | 2,247 | 0.6103386594544489 | -0.47012882888472546 | 1.4046744902006971 |

M0 has no ranking score. Deterministic every-k subsamples cover every phase;
no phase is selected.

## Gates frozen before fit

- Primary M1 at 0.5%: selected mean net > 0 bps.
- M1 selected net 95% lower bound > 0 from a 7-day moving-block bootstrap,
  2,000 draws, seed 20260924.
- Per-origin paired utility `I(accepted)*net - M0_net` has t >= 2.
- Stability: selected mean net > 0 bps at 0.25% and 1%.
- M2, M3, and M4 each beat their registered same-origin M1 comparator at paired
  t >= 2 or drop. The M4 interpretation remains limited as stated above.

Reported, not gated: full coverage curve, predictive BCE/MSE and constant
baselines, fixed-side correlation when defined, short/long split, realised
`abs(price_return)>=50 bps` bin, symmetric/wide barrier payoffs, actual TEST
coverage, funding contribution, fold concentration, and cost stress at 1.5x/2x.

## Run discipline

`--prefit` performs zero fits and writes measurements. `--limit 1` is the only
authorised smoke and fits the first evaluable fold, expected to be 406.
`--verify` hashes inputs and reconstructs the recorded run from current-run
checkpoints with zero fits. Full grid is not authorized. If all 200 folds are
evaluable, later full budget is 2,400 fresh fits.

## Amendment 1 — 2026-09-24 23:14 KST

This amendment replaces only the coverage-selection paragraph under **Frozen
labels, models, and arms** and the complete **Gates frozen before fit** section.
The original text remains above as an audit trail. The reason is the frozen
zero-fit result in `out/fixed_fade_meta_policy_20260924/prefit.json`: a 0.5%
tail contains only 1.24–1.435 expected STOP rows in every evaluable fold, so the
registered primary lever cannot be estimated on a three-day STOP grid. Data
source and cutoff remain the local Binance USD-M BTCUSDT futures inputs through
2026-06-30 UTC. No new external data, model fit, backtest, or order informed
this amendment.

### Replacement coverage section

The registered curves remain 0.25%, 0.5%, 1%, 2%, and 5%, but 5% replaces
0.5% as the sole primary coverage. At 5%, the 44,932 frozen TEST origins imply
2,246–2,247 selected rows and each ordinary clock STOP contributes about
12–14 boundary-tail rows. This is still a noisy per-fold quantile, but it is
the largest registered coverage and the only option A repair that does not
discard more support. The 2% curve is the one lower stability shoulder; 0.25%,
0.5%, and 1% are diagnostic only.

For every registered coverage, positive selected net requires
`selected gross mean > 4 bps + selected funding mean`. Using the frozen
all-origin funding mean only as a scale reference, the gross hurdle is
4.0010837911 bps at 0.25%, 0.5%, 1%, 2%, and 5%; the selected funding mean is
reported and supplies the actual hurdle. With the frozen conditional net means
(+15.8466536705 bps for `z=1`, -17.2484290357 bps for `z=0`), unchanged payoff
magnitudes would require a selected `z=1` rate above 52.1178%, versus the
41.8722% base rate. At 5%, the model must therefore lift about 2,247 origins by
10.25 percentage points, or 1.245x. This is demanding but testable; it is not
claimed as established predictive improvement.

The STOP cutoff is still fitted without TEST labels or TEST scores. Acceptance
is now `q > threshold`; a score exactly on the boundary abstains. This replaces
the old `q >= threshold` rule. It prevents a tied or degenerate boundary from
silently accepting the entire tie block. It cannot hide score-distribution
shift: aggregate realised TEST coverage must lie in the frozen 4%–6% band or
the arm fails its coverage gate. In addition, at least 90% of evaluable folds
must individually realise 2%–10% coverage; this prevents high- and low-coverage
months from cancelling in the aggregate. Actual aggregate and fold coverage is
always reported.

The smoke M4 overshoot was not caused by ties or NumPy's linear quantile. On
fold 406, all 231 STOP and 174 TEST ensemble scores were unique and no TEST
score equalled any cutoff. M4 STOP q99/max were 0.520434/0.529043, while TEST
q95/max were 0.603604/0.646433. The 0.5% cutoff therefore admitted 24/174
(13.79%); at the amended 5% target it would admit 35/174 (20.11%). This is a
STOP-to-TEST score-distribution shift and fails the new coverage gate. The
clock-trained M1 rescored on the same dollar origins also admits 26/174
(14.94%) at 5%, so the shift is not unique to the M4 fit; the dollar-origin
population is implicated.

M4 is not dropped. Zero-fit counts show 159/200 folds have at least 200 M4 STOP
origins; 158 remain available for its paired M1 comparison. At 5%, the M4 STOP
tail has median 14.125 rows; 41 folds have fewer than 10 and one has fewer than
5. M4 is measurable only as its existing 158-fold paired policy comparison and
only if both M4 and M1-on-M4 realise 4%–6% aggregate coverage and at least 90%
of their folds lie in the 2%–10% band. The deciding measurement is that paired
OOS coverage result plus its registered paired utility t-stat; fold 406 alone
is diagnostic and cannot drop M4.

Options B and C are rejected. A 200-row 0.5% STOP tail needs about 40,000 clock
origins, or 416.7 days. Rolling that window every three days preserves 200
disjoint TEST blocks only by making TRAIN end about 417 days before each TEST
and by giving adjacent STOP windows 414/417 = 99.28% overlap; the 600-day TEST
span then contains only about 1.44 independent STOP-window lengths. Requiring
non-overlapping STOP calibration leaves at most one full calibration window in
the TEST span. The return blocks can still produce a nominal t-stat, but the
threshold has essentially no independent temporal replication.

A causal C rule could pool only STOP scores whose windows end strictly before
the current TEST. At roughly 287 clock scores per evaluable fold, a 40,000-row
expanding pool first becomes available after about 140 folds, leaving only 18
of the 158 frozen evaluable folds, about 5,166 TEST origins and only about 26
selected rows at 0.5%. Raw q is also not exchangeable across independently
refitted per-fold models; fold 406 already shows material STOP-to-TEST shift.
C would be reconsidered only after a zero-fit score-drift audit reports, by
fold and arm, STOP q50/q95/q99, next-TEST exceedance, KS distance, and realised
coverage using strictly prior pools. It is not part of this experiment.

### Replacement gates

- Primary M1 coverage is 5%; aggregate realised TEST coverage must be 4%–6%,
  and at least 90% of folds must individually realise 2%–10% coverage.
- Primary M1 selected mean net must be greater than 0 bps, equivalently its
  selected gross mean must exceed `4 bps + selected funding mean`.
- The 7-day moving-block bootstrap lower 95% bound of primary M1 selected net
  must be greater than 0, using 2,000 draws and seed 20260924.
- Per-origin paired utility `I(accepted)*net - M0_net` must have t >= 2.
- M1 selected mean net at the 2% lower shoulder must be greater than 0 bps.
- M2 and M3 must meet the full primary coverage gate and beat their registered
  same-origin M1 comparator at paired t >= 2 or drop.
- M4 and M1-on-M4 must each meet the full primary coverage gate on their 158
  common evaluable folds, and M4 must beat M1-on-M4 at paired t >= 2 or drop.

Reported, not gated: the full five-point coverage curve, predictive BCE/MSE
and constant baselines, fixed-side correlation when defined, short/long split,
realised `abs(price_return)>=50 bps` bin, symmetric/wide barrier payoffs,
selected funding and gross hurdle, fold-level coverage distribution, funding
contribution, fold concentration, and cost stress at 1.5x/2x.

This amendment is frozen before any amended fit. The prior fold-406 checkpoints
and results belong to the superseded 0.5% design. Amended artifacts use
`out/fixed_fade_meta_policy_20260924_a1/`. Full-grid execution remains
unauthorized.

## Amendment 2 — 2026-09-25 02:57 KST

This amendment registers one coverage-only pilot before any pilot fit. It does
not change Amendment 1's model, features, seeds, cutoff rule, or economics
gates. It decides only whether Amendment 1 has adequate out-of-sample coverage
stability to justify the full grid.

Run M1 only on folds 426, 466, 506, 546, and 586 with seeds 42, 43, and 44:
exactly 15 fresh fits. These five pre-fit-evaluable folds are separated by 40
folds, or 120 calendar days, and span TEST windows from 2024-07-09 through
2025-11-04. The fixed spacing samples the available period without selecting
on outcomes. Fold 406 is excluded from the deciding sample because its scores,
coverage, and economics were already seen.

The launch rule is frozen verbatim:

```text
Launch rule, all three:
 1. 5-fold pooled TEST coverage in 4%-6%
 2. each of the 5 folds individually in 2%-10%
 3. no cutoff, code or data hash mismatch
Pass all three -> authorise the 1,896-fit grid, 1,881 additional fits
Fail any -> discard Amendment 1 outright; do not widen the band
```

TEST labels and economics are not inputs to the coverage verdict. The runner
first writes `scores.parquet` with STOP/TEST q scores only and then writes
`coverage_verdict.json` from those scores, STOP cutoffs, the frozen bands, and
manifest integrity. Only after that file exists does the runner open TEST
outcomes and write `economics.parquet` and `economics.json`. Economics are
reported separately and cannot change the verdict.

Artifacts use
`out/fixed_fade_meta_policy_20260925_coverage_pilot/`, not the Amendment 1
directory. Its manifest records the named folds and arm subset and hashes the
executed sources, this plan, all three input parquets, and funding ZIP inputs.
`--verify` must receive the same named folds and arms, verifies those hashes,
rebuilds outputs from checkpoints with zero fits, and refuses any mismatch.

No full-grid launch, new external data, backtest order, live order,
authenticated exchange action, or wallet action is authorized by this pilot.
This amendment is frozen before tests and fits.

## Amendment 3 — 2026-09-25 04:04 KST

This amendment replaces Amendment 1's complete selection and gate sections and
Amendment 2's conditional full-grid authorization. Amendment 2 returned
`DISCARD_AMENDMENT_1`; its rule explicitly forbids widening the band after a
failure. Amendment 3 does not revive that design under another cutoff.

The evidence is a zero-fit retrospective ordering audit of the 1,237 frozen
pilot TEST origins. It reconstructs the ensemble `m` output from the 15 frozen
M1 checkpoints and joins it to the already-written TEST economics. Source is
the local Binance USD-M BTCUSDT futures data through 2026-06-30 UTC. The audit
is recorded in
`out/fixed_fade_meta_policy_20260925_coverage_pilot/ordering_audit.json` and is
exploratory, not a fresh holdout.

Pooled global-score deciles, low to high, give:

| Decile | Rows | q-ranked net bps | m-ranked net bps |
|---:|---:|---:|---:|
| 1 | 124 | -4.568 | -6.476 |
| 2 | 124 | -2.624 | -3.863 |
| 3 | 123 | -5.189 | -3.144 |
| 4 | 124 | -3.445 | -3.803 |
| 5 | 124 | -3.229 | -1.278 |
| 6 | 123 | -5.470 | -4.838 |
| 7 | 124 | -3.663 | -6.470 |
| 8 | 123 | -5.252 | -4.484 |
| 9 | 124 | -7.210 | -7.360 |
| 10 | 124 | -6.383 | -5.288 |

The pooled Spearman relation with realised net is -0.0007 for `q` (two-sided
p=0.9811) and -0.0152 for `m` (p=0.5930). Pooling within-fold decile ranks,
rather than raw independently refitted scores, also has no monotone pattern:
`q` net runs -4.385, -4.340, -3.414, -5.087, -0.319, -6.398, -5.185,
-9.370, -5.246, -3.451 bps; `m` runs -5.587, -7.363, -2.998, -2.016,
-5.415, -2.064, -3.400, -5.978, -5.512, -6.566 bps.

Per-fold decile net means confirm sign instability:

| Fold | Score | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 | Spearman rho |
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 426 | q | -3.076 | -12.621 | 3.322 | -15.731 | 2.966 | 14.624 | -3.408 | -7.365 | -20.020 | 10.561 | 0.0761 |
| 466 | q | -4.433 | 0.581 | -8.112 | -2.607 | 0.667 | -8.475 | -4.942 | 0.277 | -8.825 | -18.394 | -0.0603 |
| 506 | q | -0.915 | -8.257 | -1.053 | -7.966 | 3.447 | -15.444 | -5.875 | -29.461 | 9.045 | -5.368 | -0.0190 |
| 546 | q | -5.429 | -4.584 | -1.721 | -1.376 | -3.480 | -4.195 | -3.093 | -1.254 | -8.384 | -0.853 | 0.0143 |
| 586 | q | -7.093 | -2.379 | -5.092 | -4.828 | -2.914 | -4.560 | -7.468 | -8.473 | -7.231 | 5.913 | 0.0586 |
| 426 | m | -2.304 | -7.924 | -15.359 | 2.100 | -3.683 | -2.710 | 2.380 | -9.690 | 6.004 | -1.294 | 0.1200 |
| 466 | m | -9.862 | -5.032 | 0.710 | 1.725 | -2.435 | 6.373 | -3.644 | -14.882 | -15.952 | -10.971 | -0.0304 |
| 506 | m | -6.655 | -13.066 | -5.060 | -3.938 | -9.421 | -3.791 | -4.679 | -4.114 | -0.518 | -9.426 | -0.0443 |
| 546 | m | -5.839 | -2.171 | -1.168 | -2.319 | -2.637 | -6.357 | -3.279 | -1.623 | -6.232 | -2.812 | -0.0088 |
| 586 | m | -1.161 | -9.188 | -2.132 | -5.016 | -7.905 | -4.336 | -4.034 | -1.901 | -3.144 | -4.973 | 0.0448 |

Neither head supplies a usable ordering on this sample. A monotone isotonic or
positive-slope Platt map preserves ordering and therefore cannot repair it.
The three proposed repairs are rejected:

1. `q > 0.5` abandons coverage control but does not remove cross-fold score
   drift. It selects 23/1,237 rows (1.859%), with -20.685 bps mean net; fold
   counts are 1, 11, 9, 0, and 2. It creates fold-level zero-trade and hot-fold
   concentration without repairing the two-sided spread.
2. A per-fold STOP calibration map could move both hot and cold probability
   scales only if STOP-to-TEST change were a stable monotone distortion. It
   cannot create TEST rank information, and its 287-row STOP fit would add a
   new overfit and extrapolation point. The zero-fit ordering audit is its
   smallest deciding measurement and already falsifies that prerequisite.
3. `m > 4 + funding` abandons coverage for the right economic question, but
   the frozen `m` range is -9.401 to +2.300 bps. It selects zero rows in every
   pilot fold. This is consistent with the earlier cost-aware 0/279 smoke and
   would leave the design unevaluable; `m` also has no realised-net ordering.

The replacement selection policy for this fixed-fade meta-policy is the
constant abstain policy: no `q` threshold, no calibration map, no `m` hurdle,
and no learned arm. M0 remains only the already-recorded diagnostic benchmark;
it is not a deployable arm. This concludes only the frozen fixed-fade q/m
family. It does not claim that no edge is reachable by another side, target,
horizon, or separately preregistered experiment.

The single terminal run is:

```text
python -m out.audit_fixed_fade_ordering
```

It performs exactly zero new fits, zero backtests, and zero orders. The only
full-grid authorization rule remains Amendment 2's three-part launch rule.
Because that rule returned `DISCARD_AMENDMENT_1`, the 1,896-fit grid is not
authorized and no later threshold diagnostic can reverse the decision. Any
future score must start under a new preregistration with an out-of-sample
ordering gate before calibration or coverage is considered.
