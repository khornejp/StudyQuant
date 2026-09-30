# PatchTST short method research correction

## Corrected conclusion

The model did learn direction. The failed interpretation came from evaluating
a large-drop classifier with an economic score that mixed TP, SL and a constant
timeout payoff. That score is neither the probability of a large drop nor the
conditional probability that TP beats SL.

The no-fit audit is reproducible with `out/audit_short_patchtst_method.py`; its
output is `out/short_patchtst_method_reaudit_20260915/audit.json`.

| Estimand and score | Pooled AUC | Mean fold AUC | Folds > 0.5 |
|---|---:|---:|---:|
| 60bps TP vs SL/timeout: `P(TP)` | 0.687316 | 0.635491 | 25/28 |
| TP vs SL only: `P(TP)` | 0.600663 | 0.570675 | 21/28 |
| TP vs SL only: `P(TP)/(P(TP)+P(SL))` | 0.586331 | 0.560504 | 22/28 |
| TP vs SL only: old expected-net score | 0.532275 | 0.499731 | 17/28 |

The prior claim that the model could not learn direction is therefore retracted.
The economic failure remains real: all payoffs were recomputed from source OHLC
and 4bps was subtracted exactly once.

## What was wrong

### 1. Three distinct questions used one score

- Event detection asks whether the 60bps downside barrier wins at all. Its score
  is `P(TP)` and its negative class is both SL and timeout.
- Resolved direction asks which barrier wins if either wins. Its score is the
  conditional probability `P(TP)/(P(TP)+P(SL))`; timeout rows are excluded.
- Trading asks for conditional expected payoff. Its score must include the
  conditional timeout return, not a constant timeout mean.

The registered score used
`60*P(TP)-20*P(SL)+stop_timeout_mean*P(timeout)-4`. Substituting
`P(SL)=1-P(TP)-P(timeout)` shows that a positive timeout mean rewards timeout
probability heavily. It can therefore rank “avoid SL / likely timeout” above
“large drop”, exactly what the selected-class breakdown showed.

### 2. The class head entangled volatility and direction

TP is only 13.00% of valid rows, SL 55.53%, timeout 31.47%. A single unweighted
three-class likelihood mostly learns event intensity and the majority SL class.
The feature audit confirms this:

- `atr_pct` alone has TP-vs-all AUC 0.682290, nearly the model's 0.687316.
- Removing `atr_pct` drops TP AUC by 0.010869 and resolved-direction AUC by
  0.007736.
- Other useful volatility fields are `rv_15`, `high_low_range` and `rv_5`.
- Direction-specific incremental fields include `short_voladj_return_5`,
  `estimated_funding_pressure_uncapped`, `short_return_1`, `body_pct`,
  `taker_sell_imbalance_15m/5m` and EMA gaps.

Thus `P(TP)` is strong partly because it detects volatility. A profitable short
also needs a separate conditional-down decision to reject high-volatility SLs.

### 3. Timeout payoff was not modeled conditionally

Timeout terminal return varies by input. Replacing
`E[R_timeout | timeout,x]` with one preceding-three-day mean discards this
variation and makes the expected-value rank unstable. A timeout-only regression
head is required if timeout remains an economic outcome.

### 4. The local model is PatchTST-style, not the canonical classifier

The official PatchTST supervised implementation retains every encoded patch and
sets the head width to `d_model * patch_num`; its flatten head consumes all patch
representations. The local model keeps only the ninth/last encoded patch token
per channel. [Official PatchTST backbone](https://github.com/yuqinie98/PatchTST/blob/main/PatchTST_supervised/layers/PatchTST_backbone.py)

The maintained Hugging Face classifier exposes CLS/mean pooling and an explicit
`channel_attention` option. The local model has neither a CLS token nor channel
attention. [PatchTST classification documentation](https://huggingface.co/docs/transformers/model_doc/patchtst)

The nonlinear-head failure does not reject feature interactions: that head was
added only after each channel had already been reduced to its last patch token,
and it was trained with the same entangled target and misinterpreted score.

### 5. Cross-variable relationships need an explicit path

PatchTST's defining channel-independent encoder applies shared weights to each
univariate channel. That is useful for temporal representation but does not
itself learn attention between price, volatility, order flow, OI and funding.
[PatchTST official description](https://github.com/yuqinie98/PatchTST)

Architectures designed for multivariate relationships provide the missing
mechanism:

- iTransformer treats variables as tokens so self-attention learns multivariate
  correlations. [Official iTransformer implementation](https://github.com/thuml/iTransformer)
- Crossformer explicitly alternates cross-time and cross-dimension attention.
  [ICLR 2023 paper](https://openreview.net/pdf?id=vSVLM2j9eie)
- TFT performs sample-dependent variable selection and gating before temporal
  processing. [International Journal of Forecasting paper](https://doi.org/10.1016/j.ijforecast.2021.03.012)

For this project the minimal useful relation layer is not a whole new model. It
is one channel-attention block over PatchTST channel summaries, tested only after
the target heads are correctly factorized.

## Empirical feature relationships

Six endpoint pairs have absolute Pearson correlation at least 0.90:

- `short_return_1` / `short_body`: 0.999926;
- `short_ema_gap_10` / `short_ema_gap_15`: 0.979262;
- `rv_15` / `atr_pct`: 0.956104;
- `short_ema_gap_5` / `short_ema_gap_10`: 0.942893;
- `short_close_zscore_10` / `short_close_zscore_15`: 0.927838;
- `short_return_3` / `short_ema_gap_5`: 0.912140.

Several fields slightly improve AUC when removed, including shadow rejection,
close location, crowding change and 3m taker imbalance. These findings are
contaminated OOS diagnostics and must not be used to hand-pick a feature subset.
They do show that 35 nominal columns are not 35 independent signals.

The economically relevant hypotheses to model explicitly are interactions, not
more copies of adjacent windows:

- volatility × signed return: large movement versus large downside movement;
- volatility × taker-sell imbalance: expansion with aggressive selling;
- return × OI change: new directional positioning versus deleveraging;
- funding/crowding × sell flow: crowded longs plus a liquidation trigger;
- premium pressure × spot-perpetual return gap: derivative-led downside.

## Correct target/loss decomposition

The smallest corrected model uses three heads on one temporal encoder:

1. `p_resolved = P(TP or SL before H60)` — volatility/event-intensity BCE;
2. `p_down = P(TP | resolved)` — direction BCE only on resolved rows;
3. `mu_timeout = E[terminal short bps | timeout,x]` — timeout-only Huber loss.

Then:

```text
P(TP)      = p_resolved * p_down
P(SL)      = p_resolved * (1 - p_down)
P(timeout) = 1 - p_resolved
EV_net     = 60*P(TP) - 20*P(SL) + P(timeout)*mu_timeout - 4
```

This separates movement intensity, direction and unresolved payoff while
preserving a calibrated likelihood. Do not begin with class weights or focal
loss because they change probability calibration. If conditional direction AUC
remains insufficient, add a small pairwise ranking term alongside BCE rather
than replacing the likelihood.

TP and SL are mutually exclusive first-hitting events. A later extension should
predict their event-time distribution as discrete competing risks, not ten
separate horizon labels. DeepHit directly models first-hitting time and cause and
adds a cause-specific ranking loss to likelihood. [AAAI DeepHit paper](https://ojs.aaai.org/index.php/AAAI/article/view/11842)

## Threshold correction

`q90` is a trade-budget/rank cap, not a break-even threshold. Once probabilities
and timeout payoff are calibrated, the economic rule is `EV_net > 0`; a q90 cap
may be added separately to limit frequency. The preceding three-day q90 drifted
substantially: depending on the score it selected 11.8–15.4% of the following
OOS rows. It should not be interpreted as a calibrated 10% or profitable gate.

Causal rechecks found no currently profitable rule: q90 expected-net remained
-3.389bps net; exploratory q99 `P(TP)` reached +2.261bps gross but still
-1.739bps net. These inspected tails cannot authorize a threshold change.

## Experiment order

1. M1 factorized-risk pilot: keep the current encoder/features/cadence fixed and
   change only the three heads, masked losses and exact EV formula. Use 30 new
   midpoint folds not used in either prior pilot. Primary direction metric is
   `p_down` on resolved TP/SL; TP-event metric is `p_resolved*p_down` on all rows.
2. M2 canonical PatchTST classification: only if M1 learns both tasks but is
   economically weak, replace last-token reduction with all-patch/CLS pooling
   and one channel-attention block. Keep M1 heads/loss fixed.
3. M3 competing-risk time head: only if M2 passes direction/calibration, predict
   TP@1..60, SL@1..60 and timeout with likelihood plus cause-specific ranking.
4. L2 information-value work remains deferred. Existing features already show
   learnable direction; microstructure data may improve it but is not the first
   correction.

No result above authorizes all 606 folds, an execution backtest or live orders.
