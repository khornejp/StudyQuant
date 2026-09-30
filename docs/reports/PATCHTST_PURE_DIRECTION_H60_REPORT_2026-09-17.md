# PatchTST pure direction H60 pilot result

Status: complete — `DIRECTION_FAIL`; independent verification PASS.

Plan: `PATCHTST_PURE_DIRECTION_H60_PLAN_2026-09-17.md`.
Runner/verifier: `out/run_patchtst_pure_direction_h60.py`,
`out/verify_patchtst_pure_direction_h60.py`.
Output: `out/patchtst_pure_direction_h60_20260917`.

## Implemented separation

The active new experimental task predicts P(futures close[t+60]<close[t]) from
the preceding 60 one-minute bars. It has one output and unweighted BCE. Exact
unchanged terminal closes are excluded and counted; both former same-minute
barrier outcomes are eligible if terminal direction is defined. TP/SL, fees,
slippage, maker fill, funding cash flows and leverage are absent from the label,
loss and pass gates. Legacy first-touch runners/checkpoints remain unchanged.

This is specifically terminal H60 direction, not maximum intrahorizon decline,
a complete forecast of all future minutes, or execution profitability. Earlier
H1..H15 direction models and the multi-task E0 terminal H60 output existed;
this pilot isolates one H60 direction head with the rolling180d/stop3d/OOS3d
schedule, limited causal supervised tuning and three seeds. It does not claim
that pure directional classification itself is newly invented.

## Causal tuning and support

Four lr/wd combinations were evaluated on three internal chronological blocks
inside the first outer TRAIN only. Selected lr0.0003, wd0.001, batch1024;
mean internal validation BCE 0.68604856. The lr0.0003/wd0.00001 arm was almost
identical at 0.68604926; this does not demonstrate a meaningful weight-decay
advantage. Parameters were locked before outer OOS predictions. Encoder size,
dropout and early-stop schedule were not tuned.

Twenty-eight of the 30 fixed historical calendar candidates were available.
Fold56 had only189 stop origins; fold119 had zero test origins. They were not
replaced. Each seed evaluated 7,900 origins, for 23,700 prediction rows total;
those three copies are not independent samples. Test ties excluded: three
origins per seed. The run made96 neural fits (12 tuning plus84 outer fits) and
28 same-row logistic baseline fits, elapsed1,206.2 seconds. No backtest/orders.

## Direction-only results

| Seed | Pooled AUC | Mean-fold AUC | Accuracy | Balanced accuracy | Folds AUC>0.5 | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 0.521234 | 0.520856 | 51.443% | 51.441% | 21/28 | 0.695788 | 0.251258 |
| 43 | 0.519590 | 0.522836 | 50.924% | 50.914% | 21/28 | 0.695834 | 0.251300 |
| 44 | 0.520286 | 0.523040 | 51.684% | 51.677% | 20/28 | 0.695941 | 0.251345 |

Observed down rate is49.886%. Same-row logistic benchmark: AUC0.514195,
accuracy50.304%, balanced accuracy50.289%, log loss0.694270, Brier0.250544.
PatchTST ranks better than this linear benchmark but has worse proper scores.

The preceding-three-day direction prior achieves accuracy51.595%, balanced
accuracy51.587%, log loss0.694767 and Brier0.250798. All three neural seeds
miss both proper-scoring gates. Their direction discrimination gates do pass.
The train-only prior's log loss0.693151/Brier0.250002 is also better than all
neural seeds. Most gross accuracy advantage is not clearly beyond local class
frequency; seed44's balanced-accuracy improvement over the stop prior is only
about0.091 percentage points, and the other seeds trail that prior.

Fixed p_down>=0.6 diagnostics produce down precision58.37%/57.34%/54.94% on
245/218/233 origins across the three seeds. These overlapping, inspected tail
subsets are small and seed-sensitive. Do not pick0.6 as a new policy threshold
from these outcomes or infer profitability. No net/gross trade gate was used.

## Interpretation and next boundary

The label now matches the agreed terminal-direction question. Its three-seed
AUC around0.52 suggests weak predictive ranking on this historical diagnostic;
it does not prove a strong or statistically confirmed new tradable edge. The
failed probability gates do not mean that no direction was learned, nor do
they identify a label calculation error. It is also incorrect to compare this
AUC directly with the old TP-vs-SL AUC: the outcomes are different questions.

Stop expansion and TP/SL backtesting under this pilot's frozen criteria. Keep
direction first and do not restore barrier outcomes into the training target.
The next diagnostic should distinguish insufficient directional input signal
from a model/optimization fit problem before increasing capacity or changing
losses. Probability calibration, if tested separately, cannot itself improve
within-fold ranking or the zero-logit sign decision when it is only a positive
temperature rescaling. Improving proper scores alone must not be sold as a
large gain in direction accuracy.

The dates were already inspected project-wide; this new treatment is not a
pristine final holdout. Future historical/2026 replication must state that
limitation, and only genuinely new forward data can be untouched confirmation.

## Verification records

Pre-fit checks passed: strict sign/ties, H60 boundary purge, one-output shape/
gradient, and a simple BCE-learning check. Every outer model passed stop-BCE
replay and save/restore equality. A mid-run source-close check independently
validated the first37 saved outputs. Full independent source/scaler/tuning/
prediction/metric/gate verification is recorded separately in verification.json.
It passed for all28 available folds, all84 outer models and all23,700 rows.
