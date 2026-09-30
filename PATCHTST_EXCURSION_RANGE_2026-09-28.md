# PatchTST excursion/range preregistration

Frozen before every fit on 2026-09-28 (Asia/Seoul). This experiment asks one
question: can the existing two-layer PatchTST encoder predict the unsigned size
of the next 15 minutes' price movement? It is a prediction experiment only. It
contains no trading side, PnL, costs, fills, orders, wallet action, or live
exchange action.

## Source, cutoff, and frozen hypothesis

The only input parquet is `artifacts/btcusdt_2020_2026h1.parquet`: Binance USD-M
BTCUSDT one-minute OHLCV, ending 2026-06-30 23:59 UTC. No external or new data
is collected. The evaluated calendar remains inside the older frozen
walk-forward interval and ends 2025-12-31.

Frozen hypothesis: recent unsigned bar geometry, activity, longer volatility
context, and calendar position contain enough persistence for PatchTST to rank
future excursion and range. `range_60` is a strong zero-fit reference, not a
gate. No pass mark, model-selection arm, or permission decision follows from
the result.

## Targets and loss

For an origin at the close of one-minute bar `t`, use exactly bars `t+1` through
`t+15`, inclusive:

```
excursion(t) = max(max(high[t+1:t+16]) / close[t] - 1,
                   1 - min(low[t+1:t+16]) / close[t]) * 1e4

range(t)     = (max(max(high[t+1:t+16]), close[t])
                - min(min(low[t+1:t+16]), close[t])) / close[t] * 1e4
```

This anchored range definition is frozen before any fit. The original unanchored
span contradicted the intended two-head decomposition: with
`u = maxH / close[t] - 1` and `d = 1 - minL / close[t]`, it made
`range - excursion = min(u, d)`, which is negative when the future window stays
strictly on one side of `close[t]`. The full-source audit found 34,529 such
complete minute origins; the fixed-origin audit found 544 of 57,599 origins.
Including `close[t]` in the span makes
`range - excursion = min(max(u, 0), max(d, 0))`, the distance covered on the
smaller side. `excursion` is unchanged: `maxH >= minL` prevents both `u` and `d`
from being negative.

Both targets are nonnegative basis points. `range >= excursion` is asserted
before training and verification. The withdrawn terminal target
`abs(close[t+15] / close[t] - 1)` is not computed and is not a model head.

Each head uses MAE in basis points. The joint loss is
`0.5 * MAE(excursion) + 0.5 * MAE(range)`. MAE is frozen because both targets
have heavy right tails; unlike MSE, isolated spikes cannot dominate the fit.
The two scales are already close (measured means 33.5 and 41.7 bps), so neither
target is normalized or reweighted. The loss rejects any negative or nonfinite
target. No signed forward quantity reaches it.

## Inputs

The ordered 60-bar sequence has seven nonnegative per-bar primitives. PatchTST
must derive its own temporal structure; no return z-score, EMA gap, taker
imbalance, funding pressure, or direction feature is supplied.

1. `abs_close_log_return_bps`: local realized movement between adjacent closes.
2. `high_low_log_range_bps`: completed-bar intrabar amplitude.
3. `abs_body_log_bps`: completed-bar open/close displacement without direction.
4. `upper_wick_log_bps`: nonnegative upper excursion within the bar.
5. `lower_wick_log_bps`: nonnegative lower excursion within the bar.
6. `log1p_quote_volume`: contemporaneous notional activity.
7. `log1p_trade_count`: contemporaneous transaction intensity.

Static context is aligned to the same origin `t` and is computed through bar
`t`, never after it:

1. `range_240_bps`: four-hour high/low regime beyond the 60-bar encoder view.
2. `range_1440_bps`: one-day high/low regime.
3. `rv_240_bps`: four-hour square-root sum of squared close log returns.
4. `rv_1440_bps`: one-day realized volatility.
5. `log1p_quote_volume_sum_240`: four-hour notional activity.
6. `log1p_quote_volume_sum_1440`: one-day notional activity.
7. `log1p_trade_count_sum_240`: four-hour transaction activity.
8. `log1p_trade_count_sum_1440`: one-day transaction activity.
9. `minute_of_week_sin01`: weekly calendar phase, shifted to `[0, 1]`.
10. `minute_of_week_cos01`: orthogonal weekly calendar phase, shifted to
    `[0, 1]`.

Sequence channel means and standard deviations use TRAIN origins only. Static
means and standard deviations also use TRAIN origins only. Both inputs are
clipped to `[-10, 10]` after standardization. This numerical standardization
does not create a directional market quantity.

## Model and optimization

Use the encoder defined by `prior.MovePatchTST` / `DeepMovePatchTST`. Their
import chain currently requires a historical `results.json` that was moved to
the forbidden archive, so the runner must not restore that output merely to
import a class. It therefore inherits the same underlying existing
`ShortPatchTST` and applies the exact `DeepMovePatchTST` two-layer encoder
definition. Both prior source files are hashed. The encoder stays unchanged:
lookback 60, patch length 12, stride 6, nine patch tokens, `d_model=48`, four
attention heads, FFN width 96, GELU, zero dropout, and exactly two Transformer
encoder layers.

Delete the former three-class head. Concatenate the flattened shared channel
encodings with the ten standardized static inputs. Two separate regression
heads each use `Linear(..., 32) -> GELU -> Linear(32, 1) -> Softplus`, one for
excursion and one for range. Softplus keeps both predictions nonnegative. No
other encoder or optimization change is allowed.

Use AdamW with learning rate `1e-3`, weight decay `1e-5`, batch size 1024, at
most 15 epochs, and patience-three early stopping on the equal-weight STOP MAE.
Seeds are 42, 43, and 44. No checkpoint outside this experiment directory may
be loaded. In particular, nothing under
`out/_archive_pre_meta_2026-09-24/` may be reused.

## Walk-forward and fit count

Use the repository's frozen 606-fold calendar. Evaluate folds 406 through 605,
inclusive. Every fold has 180 days TRAIN, 3 days STOP, and 3 days TEST. Origins
occur every 15 minutes, and a target is eligible only when its complete
`t+1..t+15` window lies inside its own TRAIN, STOP, or TEST block.

Three seeds per fold make exactly 600 authorized production fits. The one-fold
smoke uses fold 605 and all three seeds. Those checkpoints count as the first
three production fits; a later full run resumes the remaining 597. The fold
range and seed count are not changed.

## Frozen report

For excursion and range separately, report the PatchTST three-seed ensemble
and zero-fit `range_60` side by side. Define `range_60` at origin `t` as
`(max(high[t-59:t+1]) - min(low[t-59:t+1])) / close[t] * 1e4`.

For each predictor/target pair report:

- pooled and per-fold Spearman and Pearson correlation;
- pooled prediction deciles with row count, mean prediction, mean realized
  target, and decile-10 / decile-1 realized-target ratio;
- the same decile means as the calibration table;
- stability by fold and by UTC calendar month;
- for PatchTST, each seed's pooled metrics and the spread across seeds.

For the two-head pair, report pooled, per-fold, and calendar-month Spearman and
Pearson correlations between predicted and realized `range - excursion`, the
share of folds with positive gap Spearman, the share of nonnegative predicted
gaps, and gap MAE. This is the incremental information carried by two heads.

The supplied full-history `range_60` Spearman values, +0.7100 against excursion
and +0.7740 against range, are reference context only. Smoke results cover one
fold and must not be compared as if they were the full history.

## Reproducibility, verification, and safety

Before the first fit, write a SHA-256 plan hash and a manifest covering this
plan, the runner, its test, every imported architecture/calendar source used by
the runner, and the input parquet. Save every checkpoint and per-seed TEST
prediction. `--verify` must validate hashes, load checkpoints, reconstruct
predictions and every metric, and perform zero fits.

Print cumulative peak process RSS after data preparation, every completed
fold, and report generation. Abort above 3 GiB. Frozen counters are
`new_backtests: 0` and `new_orders: 0`.
