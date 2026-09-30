# PatchTST unsigned-volatility preregistration

Frozen before every fit on 2026-09-28 (Asia/Seoul). This experiment trains a
volatility forecaster. It is not a screen or a trading experiment. It creates no
PnL, fills, side, order, wallet, or live-exchange action.

## Target and loss

At every eligible one-minute origin `t`, the target is exactly

`y(t) = abs(close[t+15] / close[t] - 1) * 1e4` bps.

The last 15 rows and any origin whose `t+15` bar is not fully inside its
TRAIN/STOP/TEST block are ineligible. No signed forward return is constructed.
The model has one Softplus output, and the loss rejects negative predictions or
targets before computing MAE.

The frozen choice is **single-head MAE**. Magnitude is heavy-tailed, so MAE is
less dominated by rare spikes than MSE. A point forecast also maps directly to
the requested Pearson, Spearman, and calibration report; quantile heads would
answer a broader distributional question. Per fold, `y` is divided by the
positive TRAIN median for conditioning. This is a positive constant, so
minimizing scaled MAE is exactly equivalent to minimizing MAE in bps.

## Inputs

Source: `artifacts/btcusdt_2020_2026h1.parquet`, Binance USD-M BTCUSDT one-minute
bars, 2020-01-01 00:00 UTC through 2026-06-30 23:59 UTC. No new or external data.

The ordered 60-bar sequence contains seven nonnegative per-bar primitives:

1. `abs_close_return_bps`: absolute close-to-close log move; local realised move.
2. `high_low_range_bps`: log high/low range; intrabar amplitude.
3. `abs_body_bps`: absolute log close/open body; completed-bar displacement.
4. `upper_wick_bps`: high above max(open, close); upper excursion magnitude.
5. `lower_wick_bps`: min(open, close) above low; lower excursion magnitude.
6. `log1p_quote_volume`: contemporaneous activity scale.
7. `log1p_trade_count`: contemporaneous transaction intensity.

No signed return, EMA gap, z-score, taker imbalance, or funding pressure enters
the sequence. PatchTST is left to derive temporal structure from these primitives.

Static context is aligned to the same origin `t` and contains only information
available by the close of bar `t`:

- `range_240_bps`, `range_1440_bps`: four-hour and one-day high/low regimes;
- `rv_240_bps`, `rv_1440_bps`: four-hour and one-day realised volatility;
- `log1p_quote_volume_sum_240`, `log1p_quote_volume_sum_1440`: longer activity;
- `log1p_trade_count_sum_240`, `log1p_trade_count_sum_1440`: longer intensity;
- `minute_of_week_sin01`, `minute_of_week_cos01`: weekly calendar position,
  shifted to `[0, 1]` so the raw feature set contains no signed quantity.

All scalers use TRAIN only. Sequence scalers use the bars present in TRAIN
sequences; static and target scalers use TRAIN origins. Values are clipped to
`[-10, 10]` only after standardisation.

## Model and optimisation

The encoder is the repository's existing channel-independent PatchTST used by
`MovePatchTST` / `DeepMovePatchTST`: lookback 60, patch 12, stride 6, nine
patches, `d_model=48`, four heads, FFN 96, zero dropout. It has exactly two
Transformer encoder layers. Nothing in the encoder changes.

Only the former three-class head changes. The frozen regression head is
`concat(flattened channel encodings, static context) -> Linear(32) -> GELU ->
Linear(1) -> Softplus`.

The existing optimiser settings are frozen: AdamW, learning rate `1e-3`, weight
decay `1e-5`, batch size 1024, at most 15 epochs, STOP-MAE early stopping with
patience three. Seeds are 42, 43, and 44. No tuning or checkpoint reuse is
allowed, especially none from `out/_archive_pre_meta_2026-09-24/`.

## Walk-forward and fit count

Use the existing 606-fold calendar and only folds **406 through 605 inclusive**.
Every fold has 180 days TRAIN, 3 days STOP, and 3 days TEST. Origins are every
15 minutes, matching the existing runners. Three seeds per fold make exactly
**600 production fits**.

The one-fold smoke is fold 605 with all three seeds. Those are the first three
production checkpoints, not extra fits; the later full run resumes the other
597. A checkpoint may only be loaded from this experiment's output directory.

## Frozen report

Report prediction quality only:

- ensemble Spearman and Pearson pooled and per fold;
- prediction deciles with `n`, mean prediction, mean realised `y`, and the
  decile-10 / decile-1 realised-magnitude ratio;
- stability summaries across folds, UTC year, and UTC month-of-year;
- pooled and fold-level spread across the three individual seeds;
- the identical statistics for zero-fit `range_60`, defined as the trailing
  60-bar `log(max(high) / min(low)) * 1e4` on the same TEST origins.

The supplied prior reference, `range_60` Spearman `+0.4256` on a different
2025-01-01 split, is context only. There is no pass mark, arm selection, or
decision gate.

## Reproducibility and safety

Before fitting, write a SHA-256 manifest covering this plan, the runner, the
tests, architecture/calendar source files, and the input parquet. Save every
checkpoint and per-seed TEST prediction. `--verify` must validate hashes, load
checkpoints, reconstruct predictions and metrics, and perform zero fits.

Print cumulative peak process RSS after data preparation, every fold, and the
report block; abort above 3 GiB. Frozen safety counters are `new_backtests: 0`
and `new_orders: 0`.
