# PatchTST residual liquidity pilot preregistration

Date: 2026-09-24 (Asia/Seoul)

Status at registration: code not run; no pilot result inspected.

This is a retrospective experiment on folds already inspected by the payoff
ladder. It is not a holdout and cannot confirm an edge. A positive result only
permits the preregistered broader run.

## Frozen hypothesis

The ten book/trade channels in C1 reduced accepted terminal gross relative to
C0. One channel remains causally distinct: `kyle_lambda_surge`, the signed
within-minute price-impact slope divided by its trailing six-hour median. The
hypothesis is that this impact state helps the C0 expected-basis-points model
decide when to keep fading and when to follow the preceding move.

No other liquidity, Amihud, book, trade, spread, label, architecture, objective,
STOP rule, exit, or sampling change is allowed in this pilot.

## Arms and fixed folds

The folds are exactly:

`406, 424, 442, 460, 478, 496, 514, 532, 550, 568, 586, 604`.

- R0: load the payoff ladder's stored C0 checkpoints and rescore them. Zero fits.
- R1: C0's ordered 40-channel matrix with `kyle_lambda_surge` appended as channel
  41. Three seeds per fold, 36 fits.

Both arms use one-minute bars, 15-minute clock origins, H15 terminal returns,
the expected-basis-points objective, the two-layer encoder, classwise STOP q90
rejection, and terminal exit. Barrier returns are diagnostics only.

## Missing-data decision

Use design (b): both arms train, fit the STOP threshold, and score on
`valid & fresh`. Rows where `liquidity_valid` is false receive 0.0 in the added
channel, matching the ladder's `nan_to_num(0.0)` convention. The runner records
the exact TRAIN, STOP, and TEST origin counts removed by the alternative
`valid & fresh & liquidity_valid` mask for every pilot fold.

This keeps R0 and R1 training populations identical, so the added column is the
only model-input difference. The concession is that 0.0 is an out-of-distribution
missing sentinel for a ratio centred near 1.0. Design (a) would make scoring
populations equal but leave stored R0 trained on a wider mask than R1. Repairing
that defect would require refitting R0, adding 36 fits and replacing the requested
zero-fit control. That 72-fit design is reserved only if the recorded mask gap is
large enough to make the sentinel result uninterpretable.

## Channel conditioning and causal cutoff

Apply `sign(x) * log1p(abs(x))`. This preserves the economically meaningful
negative slope and zero sentinel while compressing the unbounded upper tail. It
fits no distribution statistic. The existing encoder mean and standard deviation
remain fitted on each fold's TRAIN rows only and are stored in the checkpoint.

`out/build_liquidity_features.py` is the source contract. Within minute `t`, Kyle
lambda uses at least 10 aggTrades and at least two consecutive within-minute
pairs, ordered by exchange `transact_time, agg_trade_id`. Its reference is a
trailing 360-minute median whose rolling window ends at `t`. The feature cutoff
is the end of minute `t`; the decision is no earlier than `t + 60s`. No source
event after 2026-06-30 UTC is permitted. The pilot keeps C0's existing H15 label
and terminal-exit convention unchanged.

## Primary measurement and falsifiers

For every TEST origin, including rejected origins:

`U_arm(t) = accepted_arm(t) * side_arm(t) * forward_bps(t)`

where UP is +1, DOWN is -1, and any rejected or SMALL decision is 0. Report the
paired mean `dU = mean(U_R1 - U_R0)`, standard error, t statistic, and 95% normal
interval over all pilot TEST origins.

Any one of these falsifies the channel:

1. `dU <= 0`.
2. R1 accepted terminal gross is below R0 accepted terminal gross.
3. C6 incremental gross is `<= 0` on origins where both arms accept, R0 takes
   the fade side, and R1 takes the opposite continuation side. Zero prior moves
   are excluded from C6.

The following are diagnostics, not gates: each arm's accepted gross and t,
R1 minus R0 accepted gross, R1 minus fade, coverage, correlation of side with
the prior H15 move, agreement with that move, gross for realised moves of at
least 50 bps, long and short gross separately, and barrier gross.

## Promotion rule

Record `RESIDUAL_PILOT_PROMOTE_185_FOLDS` only when no falsifier fires,
`dU > 0` with `t >= 2`, and R1 minus fade is positive with `t >= 2`. Otherwise
record either `RESIDUAL_PILOT_FAIL` or
`RESIDUAL_PILOT_POSITIVE_NOT_PROMOTED`. Do not run the remaining 185 folds from
this runner invocation.

## Reproducibility and scope

The manifest must contain SHA-256 hashes for every executed source module, this
plan, every directly read parquet, the frozen C0 inputs, and all 36 reused C0
checkpoints. `--verify` must load checkpoints only, reconstruct predictions and
results, and fail on any hash or value mismatch. `--limit 1` is the sole smoke
path. Record `new_backtests: 0` and `new_orders: 0`.

