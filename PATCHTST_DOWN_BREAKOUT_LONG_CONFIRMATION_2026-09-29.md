# PatchTST two-arm breakout confirmation preregistration

Arm A was frozen on 2026-09-29T14:46:11+09:00, before this run computed any
quantity from the 2026 H1 confirmation window and before any confirmation fit.

## Frozen amendment made during forecasting

Arm B was added and frozen on 2026-09-29T14:54:34+09:00. At that time fitting
was in progress, exactly 18 fold-606-plus checkpoints existed, and no
confirmation-window strategy outcome had been computed or observed. The 18
checkpoints contained model weights and predictions only; no strategy ledger,
result, report, or calendar PnL artifact existed. The pre-amendment plan hash
was `d5b2ad4517a79221b480f25903c54da277eb14d20ab89452293046038eddc9a3`.

This amendment is admissible because neither arm's confirmation outcome was
available, the forecasting model does not use either trading rule, and the
model, features, folds, seeds, gate, trigger, entry, exit, horizon, cost, and
notional remain unchanged. Completed forecast checkpoints remain valid. The
runner was stopped before evaluation, amended, and may resume only from its
own confirmation checkpoints.

Arm B was already specified as an up-breakout negative control. This amendment
promotes the symmetric up-breakout short rule to a separately accepted arm.
Its hypothesis comes only from the exploration window, where it measured gross
`-0.5663` bps per trade with `t = -0.42`. Arm B therefore enters confirmation
with a frozen prior of flat, not promising.

## Provenance and selection debt

Source is the existing local Binance USD-M BTCUSDT one-minute OHLCV parquet,
`artifacts/btcusdt_2020_2026h1.parquet`, with cutoff
`2026-06-30T23:59:00Z`. No new or external data is allowed.

Exploration covered folds 406--605, 2024-05-10 through 2025-12-30, using the
per-fold STOP q90 PatchTST excursion gate. A post-hoc decomposition over four
triggers, two breakout sides, and two positions selected one of sixteen cells:
50-bps down breakout followed by a long position. The exploration result is
selection evidence only, not confirmation evidence.

The confirmation interval is `[2026-01-01T00:00:00Z,
2026-07-01T00:00:00Z)`. It is unused by folds 406--605 and this forecast
lineage. It is not globally pristine: discarded earlier work inspected 2026 H1
repeatedly. The result is therefore lineage-specific confirmation, not a claim
of an untouched market holdout.

## Frozen hypotheses

- Arm A: among gated origins, a completed-close 50-bps DOWN breakout is
  followed by positive net H15 return for a LONG position after 4 bps cost.
- Arm B: among the same gated origins, a completed-close 50-bps UP breakout is
  followed by positive net H15 return for a SHORT position after 4 bps cost.

Each arm has its own acceptance. Neither arm can rescue the other. No
alternative trigger, side rule, position, horizon, gate quantile, cost, model,
feature, seed, cadence, entry, or exit may be tried on the confirmation window.
Any such variation voids the run.

## Frozen forecast extension

Use the exact model and feature contract in
`PATCHTST_EXCURSION_RANGE_2026-09-28.md` and
`out/patchtst_excursion_range_20260928/manifest.json`: same two-head PatchTST,
targets, features, normalization, AdamW settings, early stopping, 180-day
TRAIN, 3-day STOP, 3-day TEST, 15-minute origins, and seeds 42, 43, and 44.

Extend the unchanged three-day calendar to folds 606--666 inclusive. Each fold
gets three new fits, exactly `61 * 3 = 183` completed checkpoints. Checkpoints
may load only from this confirmation output directory. Nothing in
`out/_archive_pre_meta_2026-09-24/`, the folds 406--605 forecast directory, or
any other directory may be reused. TEST origins are clipped to the confirmation
interval, while each fold retains its full frozen TRAIN and STOP blocks.

## Frozen gate and trade rules

For each fold, average its three seed predictions on STOP and TEST. Compute the
linear STOP q90 of `pred_excursion_bps`; TEST ties pass.

For each gated TEST origin `t`, use completed closes for `k = 1,...,15`:

```
d(k) = 1e4 * log(close[t+k] / close[t])
tau  = min{k : abs(d(k)) >= 50}
```

No trigger exists when that set is empty. The conservative completed-close
rule includes overshoot: entry is `close[t+tau]`, not the unobserved exact
barrier price. Exit is `close[t+15]`. A trigger first seen at `k=15` is a trade
with zero gross return and -4 bps net.

Arm A requires `d(tau) < 0` and takes LONG:

```
gross_bps = 1e4 * log(close[t+15] / close[t+tau])
net_bps   = gross_bps - 4
pnl_usd   = net_bps / 100
```

Arm B requires `d(tau) > 0` and takes SHORT:

```
gross_bps = 1e4 * log(close[t+tau] / close[t+15])
net_bps   = gross_bps - 4
pnl_usd   = net_bps / 100
```

`pnl_usd` uses fixed $100 notional per trade and the exploration's linear-bps
convention. No compounding, sizing change, fill model, rebate, funding, or live
order is allowed.

The shared realised trigger rate is the count of gated origins crossing either
side at 50 bps divided by all gated origins. Its frozen exploration
admissibility band is 20.00%--60.00%, inclusive. Each arm's side-specific count
and rate are descriptive; they do not replace or alter the shared frozen band.

## Frozen inference and separate acceptance

For each arm separately, the 95% two-sided lower bound is the intercept-only
OLS mean with CR1 cluster-robust covariance by TEST fold, finite-sample
correction `G/(G-1)`, and Student-t critical value `t(0.975, G-1)`, where `G`
is that arm's number of nonempty trade folds. At least two nonempty fold
clusters are required. No IID, bootstrap, alternative clustering, or one-sided
replacement may rescue either arm.

Verdict order is frozen:

1. A shared trigger rate outside 20.00%--60.00% gives both arms
   `POPULATION_MISMATCH`, not pass or fail.
2. An arm with no trades, fewer than two trade-fold clusters, mean net at or
   below zero, or a clustered lower bound at or below zero gets
   `CONFIRMATION_FAIL`.
3. An arm gets `CONFIRMED` only when its mean net and clustered lower bound are
   both strictly above zero.
4. Arm verdicts are always reported separately. Neither verdict changes the
   other.
5. If both arm means turn positive, flag a possible window effect. If both arms
   pass, report `BOTH_ARMS_CONFIRMED_WINDOW_EFFECT`: the likely reading is a
   window effect, not the exploration asymmetry.

Arm B's acceptance was frozen with this amendment before any confirmation
strategy outcome was computed or seen.

## Frozen report and safety

For both arms report trade count, long/short split, gross and net bps per trade,
fixed-$100 total, win rate (`net_bps > 0`), UTC-date calendar PnL,
chronological cumulative-PnL max drawdown in bps and dollars, clustered
estimate and lower bound, side-specific trigger count and rate, and the shared
realised trigger rate against the exploration band. Save per-origin forecasts
and both arm ledgers.

Hash this amended document before resumed fitting. The run manifest must record
both plan hashes and the amendment evidence, then hash the amended plan, runner,
test, imported model/calendar sources, frozen prior forecast manifest, and
input parquet. `--verify` must validate hashes, load the 183 local checkpoints,
reconstruct forecasts, gates, both ledgers, metrics, and verdicts, and perform
zero fits. Print peak process RSS and abort above 3 GiB. Frozen counters are
`new_orders: 0`, `external_data_added: 0`, and `live_orders: 0`.
