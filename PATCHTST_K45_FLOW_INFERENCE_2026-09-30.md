# K=45 flow inference and retrospective power diagnostic preregistration

Frozen on 2026-09-30 at 20:51 Asia/Seoul, before opening any F-1 outcome.
This plan reuses only frozen local Binance USD-M BTCUSDT futures artifacts.
Predictions are immutable inputs. The data cutoff is
`2026-06-30T23:59:00Z`.

The experiment performs zero model fits, sends zero orders, adds zero external
market data, and permits no live action. K is 45 minutes, the trading rule is
long-only, there is no stop, and one round-trip cost is 4 bps.

## Ordered execution and interpretation

1. Freeze this plan and its SHA-256.
2. Apply method E to Tasks B and D. These results are labeled
   `RETROSPECTIVE_DIAGNOSTIC`; they cannot reverse either prior `NO_ORDERING`,
   unlock the Task D veto, select a feature, or produce a new verdict.
3. Build the trial ledger from frozen manifests and freeze `M_ledger` and
   `alpha_adjusted=0.05/(M_ledger+1)` before reading F-1 outcomes.
4. Open the F-1 outcomes and run the one preregistered primary regression.
5. Run the conditional long book only if every F-1 regression gate passes.
6. Do not run F-2, CSCV, DSR, or CPCV. Recombining existing prediction blocks
   would be `frozen OOS block-path recombination`, not CPCV, and is not run.
7. Reconstruct all applicable artifacts under `--verify` and enforce peak RSS
   below 3 GiB.

## E-1: calendar blocks chosen without outcomes

The candidate units were `{UTC week, UTC calendar month, UTC quarter}`. The
selection rule used only candidate counts:

1. at least 48 total blocks;
2. for continuous tests, at least 80% of blocks have at least 20 candidates;
3. for binary tests, at least 80% of blocks have at least five candidates in
   each group;
4. choose the shortest unit satisfying the applicable rules.

The outcome-blind geometry was: 287 weeks with median 11 candidates and only
24.4% at `n>=20`; 66 months with median 62 candidates and 93.9% at `n>=20`;
22 quarters, below the 48-block minimum. Task D's binary split had both groups
at `n>=5` in 56 of 66 months. UTC calendar month is therefore fixed. A trade
whose 45-minute exit crosses a month boundary is excluded only from monthly
direction calculations, not from the pooled endpoint.

Continuous B/D cells use a monthly standardized-rank slope. Task D's binary
cell uses a monthly active-minus-inactive mean difference. F-1 uses its
preregistered adjusted binary coefficient within each month. A cell needs at
least 48 valid months.

### Exact direction gate

For a prespecified direction and `G_m` valid months, define

```text
k_+(G_m) = min{k : sum_{j=k}^{G_m} C(G_m,j) 2^(-G_m) <= 0.05}.
p_dir+(G_m,k) = sum_{j=k}^{G_m} C(G_m,j) 2^(-G_m).
```

The old `ceil(0.60 G_m)` rule is replaced before outcomes by this exact fixed
binomial critical count. At `G_m=66`, 60% means 40 months, but
`P[Binom(66,0.5)>=40]=0.0544284822`, not about 4.5%. The prespecified positive
F-1 direction therefore requires `k_+(66)=41` positive months
(`41/66=62.1212%`), whose exact one-sided null tail is `0.0320087521`.

B/D chose direction from the pooled result, so their retrospective diagnostic
uses the two-sided rule

```text
k_+-(G_m) = min{k : min(1, 2 p_dir+(G_m,k)) <= 0.05}.
```

At `G_m=66`, this requires 42 agreeing months and has exact two-sided tail
`0.0355827245`. This distinction prevents a data-chosen sign from receiving a
one-sided threshold.

The bootstrap and direction gates use the same observations and are not
independent. For their intersection, the conservative null-probability upper
bound is

```text
min(alpha_adjusted, p_dir+(G_m,k_+(G_m)))
```

for F-1, not their product. A product may be shown only as an explicitly
counterfactual independence calculation.

## E-2: corrected Politis-White stationary bootstrap

Each test supplies a UTC daily influence-score series from the first through
last eligible date. Days without candidates are zero. The series is centered
before block-length selection and null resampling.

The block selector is frozen as follows. For series length `N`, set
`K_N=max(5,floor(log10(N)))`, `m_max=ceil(sqrt(N))+K_N`, and
`b_max=ceil(min(3 sqrt(N),N/3))`. Find the first run of `K_N` consecutive
sample autocorrelations whose absolute values are below
`2 sqrt(log10(N)/N)`. Let `m_hat` be the lag before that run and set
`M=min(2 max(m_hat,1),m_max)`. Use the trapezoidal flat-top window

```text
lambda(k/M)=1                         when |k/M|<=1/2
            2(1-|k/M|)               when 1/2<|k/M|<=1
            0                         otherwise.
```

With divisor `N` autocovariances, compute

```text
G_hat = 2 sum_{k=1}^M lambda(k/M) k R_hat(k)
g_hat(0) = R_hat(0) + 2 sum_{k=1}^M lambda(k/M) R_hat(k)
D_SB = 2 g_hat(0)^2
b_SB = min(((2 G_hat^2 / D_SB) N)^(1/3), b_max).
```

`D_SB=2 g_hat(0)^2` is the Patton-Politis-White correction. The stationary
bootstrap uses geometric blocks with real expected length `b_SB`, circular
wrapping, 20,000 replications, and seed `20260930`. A nonfinite, zero-variance,
nonpositive spectral, or otherwise degenerate selector is `UNMEASURABLE`; no
favorable fallback is allowed. The selected length, selector diagnostics,
one-sided or two-sided p-value, and 95% interval are artifacts. The old lag-60
and automatic HAC intervals remain sensitivity diagnostics only.

## Trial ledger and research-wide adjustment

Only frozen manifests existing before this plan with an explicit
`primary_test_count` enter the mechanical ledger. Each arm-feature primary cell
becomes one hypothesis signature; exact duplicate signatures and superseded
directories are removed. Replays, fill labels that are asserted identical,
year slices, sensitivity thresholds, diagnostic horizons, account leverage
translations, and the current F-1 test are not counted as prior primary tests.

This rule cannot recover unrecorded research attempts. No complete historical
experiment registry exists, so the number or scale of omitted attempts cannot
be estimated defensibly. `M_ledger` is a lower bound. Applying Bonferroni to a
lower bound under-corrects multiplicity and raises type-I error relative to the
claimed research-wide level. Any F-1 pass must therefore be read as provisional
and materially discounted until an untouched future sample confirms it.

The F-1 bootstrap gate is one-sided and requires
`p_bootstrap <= 0.05/(M_ledger+1)`.

## F-1 fixed feature, threshold, and outcome-blind diagnostics

For each of the 4,692 boundary-clean `DOWN_BREAKOUT_LONG` candidates, define

```text
aligned_path_flow =
  (sum quote_volume - 2 sum taker_buy_quote_volume) / sum quote_volume
```

over bars `(signal_index,entry_index]`, namely `signal_index+1` through
`entry_index`, inclusive. Positive values mean aggressive selling aligned with
the down breakout. `entry_index-signal_index=tau` must hold, every denominator
must be positive, and all source timestamps must be at or before entry.

The primary threshold is only `aligned_path_flow>=0.20`. It means quote-volume
aggressive sell share of at least 60%. It comes from the prior economic trigger,
not from outcome values or split balance.

Outcome-blind threshold counts are frozen below. `0.15`, not `0.20`, is the
most balanced listed split; `0.20` is retained for its prior interpretation.

| threshold | high | low | high share |
|---:|---:|---:|---:|
| 0.05 | 4,218 | 474 | 89.8977% |
| 0.10 | 3,589 | 1,103 | 76.4919% |
| 0.15 | 2,753 | 1,939 | 58.6743% |
| 0.20 | 1,852 | 2,840 | 39.4714% |
| 0.25 | 1,175 | 3,517 | 25.0437% |
| 0.30 | 646 | 4,046 | 13.7681% |
| 0.40 | 158 | 4,534 | 3.3674% |

The seven-threshold grid is reported only as outcome-blind counts and a
post-result sensitivity table. It cannot select a threshold, alter a gate, or
rescue the primary result.

The already completed outcome-blind novelty checks remain fixed: Spearman flow
correlations are `+0.1640` with `abs_d_tau_bps`, `-0.1638` with
`log1p(path_quote_volume)`, and `-0.3320` with `tau`; their rank projection has
`R^2=0.1225` and VIF `1.1396`; the minimum within-cell flow standard deviation
over the `abs_d` by volume 5x5 grid is `0.0902`. These checks reject simple
re-expression, not confounding or causal ambiguity.

## F-1 primary regression and gate

Let `rank(v)=(average_rank(v)-0.5)/N`. Fit the single descriptive OLS:

```text
none_net_lin_bps = alpha_UTC_month
                 + beta I(aligned_path_flow>=0.20)
                 + gamma1 rank(abs_d_tau_bps)
                 + gamma2 rank(log1p(path_quote_volume))
                 + gamma3 rank(tau)
                 + error.
```

This is a conditional-mean test, not a predictive model, and does not increment
`new_model_fits`. The F-1 regression gate passes only if all hold:

1. `beta>0`;
2. corrected PW stationary-bootstrap one-sided p-value is at most the frozen
   research-wide adjusted alpha;
3. at least 48 valid months;
4. at least `k_+(G_m)` monthly coefficients are positive.

Only 45-minute K45 net linear bps is a decision endpoint. Identically specified
1-, 5-, and 15-minute net markout regressions, trigger-bar flow, continuous-flow
rank association, and the seven-threshold table are mechanism or sensitivity
diagnostics. They never affect the gate. A shorter-horizon effect cannot rescue
a failed K45 result.

## Conditional executable book and final verdict

Regression-gate passage is only an intermediate step. If it fails, status is
`FLOW_REGRESSION_GATE_FAILED` and no conditional book artifact may exist.

If it passes, replay one long-only slot with candidates ordered by
`(entry_index,signal_index)`. A position occupies
`[entry_index,entry_index+45)`; skipped candidates never queue.

- `LONG_ONLY`: all 4,692 candidates; must reproduce 3,066 trades and mean
  `+0.4550` bps within report rounding.
- `FLOW_INTENSE_ONLY`: admit only the fixed 1,852 primary-high candidates.
- `RATE_ONLY`: deterministic periodic mask keeping exactly 1,852 candidate
  arrivals, using
  `floor((i+1)M/N)>floor(iM/N)`.
- `RANDOM_EXCLUSION`: 1,000 fixed seeds 42 through 1041, each keeping exactly
  1,852 candidate arrivals without replacement before the same sequential
  replay. Report the flow book percentile
  `(1 + count(random_mean<=flow_mean))/1001` and the full distribution.

Report pooled, every UTC year, and 2022; matched/added/dropped decomposition;
trade count, candidate pass rate, mean K45 net bps, PW interval, fixed-$100 PnL,
maximum drawdown, and win rate. No leverage sweep is run.

The final pass requires the `FLOW_INTENSE_ONLY` mean to be positive and its
mean improvement over `LONG_ONLY` to have a 95% PW bootstrap lower bound above
zero. If the regression passes but either book condition fails, final status is
`GATE_PASSED_BOOK_FAILED`. Regression evidence cannot rescue the book. Only if
both conditions pass is status `FLOW_BOOK_IMPROVED_EXPLORATORY`; this remains
research evidence, not production permission.

## Integrity and outputs

Write only `out/patchtst_k45_flow_inference_20260930`. Freeze hashes for this
plan, runner, test, all inputs, and the trial-source manifests. Always emit the
manifest, status, results, report, trial ledger, retrospective E tables, F-1
candidate ledger, regression diagnostics, monthly coefficients, selector
diagnostics, verification, and SHA-256 output manifest. Emit conditional book
artifacts only after the regression gate passes.

Frozen counters are `new_model_fits: 0`, `new_orders: 0`,
`external_data_added: 0`, and `live_orders: 0`.
