# System spec — what btcusdt_quant actually does

Written 2026-08-18 from the code at commit `dff6a03`, not from earlier documents.
Every claim carries a `file:line` so it can be checked without trusting this page.
Where a default differs from what recent runs used, both are given.

This describes the machine. It contains no assessment of whether the strategy works.

---

## 1. Features

`FEATURE_DEFINITIONS` contains **196** definitions.  `active_feature_names()` excludes only definitions whose scaffold status is `pending_data_source` or `disabled_scale_dependent`, leaving **180** registry-active model inputs. `feature_registry.py:77-78` `feature_registry.py:351-382` The current README instead says “107 of 107” across F01–F12, so it disagrees with the registry. `README.md:4-14`

The table gives each registry group: definition count / registry-active count; source; inclusive lookback/minimum-sample range in one-minute bars; warmup rule; and required flags (training/live).  `strict`, `state`, and `none` are the registry values; a range means individual definitions in that group differ.

| Group | Definitions / active | Source | Lookback/min samples | Warmup | Required T/L |
|---|---:|---|---|---|---|
| F01 `price_return_features` | 13 / 13 | `klines_1m` | 2–61 | strict | yes / yes `feature_registry.py:78-90` |
| F02 `trend_ma_features` | 14 / 14 | `klines_1m` | 5–60 | strict | yes / yes `feature_registry.py:91-104` |
| F03 `volatility_features` | 13 / 13 | `klines_1m` | 6–121 | strict | yes / yes `feature_registry.py:105-117` |
| F04 `volume_trade_flow_features` | 12 / 11 | `klines_1m` | 1–60 | strict | yes / yes `feature_registry.py:118-130` |
| F05 `candle_structure_features` | 10 / 10 | `klines_1m` | 1–20 | strict | yes / yes `feature_registry.py:131-140` |
| F06 `gap_data_quality_features` | 8 / 8 | `klines_1m` | 1–120 | state | yes / yes `feature_registry.py:141-148` |
| F07 `regime_normalization_features` | 8 / 8 | `klines_1m` | 5–75 | strict | yes / yes `feature_registry.py:149-156` |
| F08 `volatility_adjusted_return_features` | 6 / 6 | `klines_1m` | 121 | strict | yes / yes `feature_registry.py:157-162` |
| F09 `volatility_adjusted_trend_features` | 4 / 4 | `klines_1m` | 61 | strict | yes / yes `feature_registry.py:163-166` |
| F10 `volatility_adjusted_candle_flow_features` | 5 / 5 | `klines_1m` | 61 | strict | yes / yes `feature_registry.py:167-171` |
| F11 `microstructure_features` | 7 / 0 | `depth_snapshot` | 1 | state | yes / yes `feature_registry.py:172-184` |
| F12 `exchange_funding_safety_features` | 8 / 8 | `adl_quantile`, `funding_rate`, `mark_price_1m`, `premium_index_1m`, `leverage_bracket` | 1 | state | yes / yes `feature_registry.py:185-192` |
| F13 `higher_timeframe_features` | 7 / 7 | `klines_1m` | 504,000 | strict | yes / yes `feature_registry.py:193-211` |
| F14 `time_session_features` | 8 / 8 | `klines_1m` | 1 | none | yes / yes `feature_registry.py:212-220` |
| F15 `momentum_indicator_features` and range-reversion entries | 25 / 17 | `klines_1m` | 8–70 | strict | yes / yes `feature_registry.py:221-254` |
| F16 `derivatives_metrics_features` | 11 / 11 | `metrics` | 1–1,440 | none or strict | yes / **no** `feature_registry.py:255-271` |
| F17 `multi_timeframe_features` | 34 / 34 | `klines_1m` | 150–4,800 | strict | yes / yes `feature_registry.py:272-314` |
| F18 `regime_probability_features` | 3 / 3 | `regime_classifier` | 1 | none | yes / **no** `feature_registry.py:315-326` |

F11 is registry-inactive because the available archive is percentage-band cumulative depth, not reproducible top-of-book data; using offline constants against live snapshots would make a train/live discrepancy. `feature_registry.py:172-177` The one inactive F04 feature and eight inactive F15 features are `disabled_scale_dependent`: they are excluded as direct model inputs because their absolute dollar/price scale can act as an era proxy and can saturate the clipper; some remain computed as dependencies. `feature_registry.py:128-130` `feature_registry.py:224-246` `feature_registry.py:351-364`

There is a second, per-run exclusion. Training defaults to removing inputs reported as source fallback/mock constants. `training.py:87-92` The latest source-backed record (`stage4_h45_tp004_sl002_q80_sources_timeoutfix`) therefore used **174** features and excluded exactly six: `adl_indicator`, `mark_price_basis`, `leverage_bracket_utilization`, `regime_prob_up`, `regime_prob_range`, and `regime_prob_down`. `artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix/run_summary.json:1` `funding_rate`, `next_funding_rate`, `minutes_to_next_funding`, `funding_blackout_active`, and `premium_index` were retained in that artifact’s feature list, i.e. rescued by the supplied funding and premium-index archives rather than treated as fallback. `artifacts/stage4_h45_tp004_sl002_q80_sources_timeoutfix/model_card.json:1` The training removal itself takes the source report’s `fallback_features` and drops them from the feature-name tuple. `training.py:330-348`

### Why the six cannot simply be collected

- `mark_price_basis` needs a `markPriceKlines` path that does not exist here, and that
  bucket has 50 missing days inside the training window.
- `leverage_bracket_utilization` and `adl_indicator` are account/exchange state with no
  reconstructible public history.
- `regime_prob_*` are another model's output (`regime_classifier.py`), deliberately
  withheld from these runs. Note F18 is `required_for_live = no`.

Without the archives the same runs excluded **11** and used **169** features
(`stage3_h45_tp004_sl002_q80_timeoutfix/run_summary.json`).

## 2. Labels

`dataset.triple_barrier_label_long` and its short counterpart, `dataset.py:2345`.
Docstring: *"Return the binary TP-first class plus its executable settlement reason."*

**The value is binary**: `1` = TP touched first, `0` = everything else. The reason
string carries what actually happened.

| reason | meaning |
|---|---|
| `long_tp_first` / `short_tp_first` | TP reached before SL, label 1 |
| `long_sl_first` / `short_sl_first` | SL reached first, label 0 |
| `long_timeout` / `short_timeout` | neither barrier touched in the horizon, label 0 |

Touch tests are side-specific (`dataset.py:2365`, `dataset.py:2391`):

```
long :  tp_touched = high >= tp_level     sl_touched = low  <= sl_level
short:  tp_touched = low  <= tp_level     sl_touched = high >= sl_level
```

**Same-bar TP+SL resolves by candle direction, per side.** Probed and confirmed:

| bar | long | short |
|---|---|---|
| bullish (close > open) | TP | SL |
| bearish (close < open) | SL | TP |
| doji (close == open) | SL | SL |

A doji is SL for both sides because each requires a strict inequality in its own
favour. This tie-break was previously inverted for shorts.

**Label 0 is not a loss.** A timeout settles at the horizon-bar close, not at `-sl`
(`dataset.py:2352`). Before commit `5716d6b`, threshold selection priced a timeout at
`-sl_pct` while execution and both screens settled it at the horizon close: 130 bps per
timeout row. Since `dff6a03`, `realized_payoffs` is **required** rather than optional —
a missing or short vector raises instead of falling back to labels.

---

## 3. Decision path, in order

1. **Feature construction** over the whole file; the longest warmup needs roughly 350
   days of history before the first usable row.
2. **Volatility gate** on `rv_60`. The cutoff is derived, not typed:
   `--vol-gate-train-quantile 0.8` takes the 0.80 quantile of the **45-day shared-prior reserve**
   only**, which precedes every test slice, and applies that single number to all folds.
   `--vol-gate-derivation fold0_train` preserves the historical fold-0-train
   derivation for reproducible reruns; the emitted artifact names the choice.
   Recent runs used `rv_60 >= 0.0013057161` (`artifacts/rerun_S3A.log`). An absolute
   `--vol-gate-min` exists but must not be set from a whole-span quantile under
   walk-forward: later folds' test rows would then help choose the gate.
3. **Model**: CatBoost predicting **P(TP before SL within the horizon)** for one side.
   It does not predict the timeout probability or the conditional timeout return.
4. **Calibration** fits the probability and explicitly issues no economic verdict. Its
   serialized field reads `economic_decision: unavailable_from_binary_tp_labels`
   (`calibration.py:148`): binary TP labels cannot identify `P(timeout)`, so a
   trade/no-trade decision cannot come from them.
5. **Threshold selection** consumes calibrated validation predictions together with
   realized payoffs — TP `+tp`, SL `-sl`, timeout at the horizon close — then subtracts
   cost. Inputs persist per fold to `threshold_selection_inputs.npz`, 13.32 MiB for four
   331,560-row folds, so a future selection-rule change replays offline without
   refitting. Verified: all four folds re-derive their recorded threshold from the file
   alone (0.3758 / 0.3969 / 0.4016 / 0.4018).
6. **Entry admission**: one active trade and, in the default resting-limit model, one
   pending order (`backtest.py:2105`):

```python
if active_trade is None and pending_order is None and signal in {"BUY", "SELL"} and i >= next_entry_index:
```

   Rejected signals are recorded with reason `active_trade`, `pending_order` or
   `cooldown`. Every leg is a maker limit order; non-fill is not modelled and taker is
   never used.

---

## 4. Costs

`DEFAULT_ROUND_TRIP_COST = 0.0004` (`training.py:28`) — 4 bps, two 2-bps maker legs
under the limit-only premise, no slippage term. Runs pass `--round-trip-cost 0.0004`
explicitly.

---

## 5. Evaluation

- **Splits**: walk-forward, 4 folds, test windows of 331,560 rows each.
- **Purge**: a horizon-sized gap between train and validation and between validation and
  test. `embargo_size` is `0`; that flag applies to combinatorial CV only.
- **Test gap**: `--walk-forward-test-gap 45` separates consecutive test windows by the
  label horizon, so one fold's labels resolve before the next fold's entries begin.
  Probed at the boundary: gap 44 gives not-disjoint, gap 45 gives disjoint, and
  `min_test_window_gap_bars` counts bars strictly between the inclusive windows.
- **Primary metric**: `*_net_bps_trade_weighted_mean`. The equal-weight figure survives
  as `*_net_bps_plain_fold_mean` and is not primary — a four-trade fold once made the
  plain mean read `+11.39` where the trade-weighted figure was `-3.24`.
- **Removed**: the former directional net-mean field and fold-profit count. The latter counted a
  four-trade fold equal to a 956-trade one and is replaced by
  `*_profitable_trade_share`, which weights by trades.
- **Zero-trade folds** appear in `*_folds_with_no_trades` rather than vanishing from a
  denominator.

---

## 6. What the system does not do

- **Short side is deferred, not dropped.** The intended system trades both directions;
  five successive short models failed, so the leg is held back rather than abandoned.
- **Live path is on hold** by decision. A serving route exists in `live.py`; no order is
  placed.
- **No feature cache on runs of record.** The cache key covers the feature schema, not
  the implementation, so an edit leaving the registry entry identical can serve a stale
  matrix that provenance cannot detect. Screens, folds and holdouts run without it.
- **Declared but unimplemented**: aggregate-trade (`sources.py:210`) and liquidation
  (`sources.py:230`) feature names exist but are not built into feature rows, and no
  collector or loader exists for either. Depth (F11) is `pending_data_source`.
- **Binary EV gates fail closed.** The Kelly gate and the regime-aware EV admission
  refuse a TP-before-SL probability by default, because a two-outcome EV misprices the
  timeout population; an explicit waiver exists for research use only.
