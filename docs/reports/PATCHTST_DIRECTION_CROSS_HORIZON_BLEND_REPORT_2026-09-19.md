# PatchTST H15/H60 cross-horizon blend report

Date: 2026-09-19 (Asia/Seoul)

## Outcome

`CROSS_HORIZON_BLEND_PASS`. Independent verification: `PASS`.

The fixed, unweighted 50:50 probability mean of the H60-trained and H15-trained
three-seed ensembles is the first current direction candidate to pass both the
all-six and later-three improvement requirements. Both constituents were
scored in the same H15 probability/label space on exactly 1,685 common origins.

No ensemble weight, threshold, fold, or metric was selected after looking at
the result. No new model fit was needed for this blend. There was no TP/SL,
fee, slippage, backtest, spot input, or order.

## All six folds

| Arm | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
|H60-trained|0.543993|0.552535|0.556386|52.820%|0.690706|0.248783|
|H15-trained|0.552198|0.564425|**0.571223**|54.173%|0.690147|0.248492|
|50:50 blend|**0.552636**|**0.564762**|0.570457|**54.333%**|**0.689926**|**0.248391**|

Versus H60, the blend gained +0.00864 pooled AUC, +0.01223 mean-fold AUC and
+1.512 percentage points balanced accuracy, won 5/6 fold AUCs, and improved
both proper scores. Versus H15, it also improved pooled/mean-fold AUC,
balanced accuracy, log loss and Brier; mean daily AUC was 0.00077 lower.

## Later folds 348/453/598

| Arm | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
|H60-trained|0.531842|0.552120|0.554515|52.297%|0.691816|0.249335|
|H15-trained|0.531595|0.553496|0.560554|51.262%|0.691263|0.249061|
|50:50 blend|**0.534956**|**0.557439**|**0.562402**|**53.152%**|**0.691146**|**0.249002**|

The blend beat both constituents in every frozen aggregate metric and in 2/3
fold AUC comparisons against each. Relative to H60, later balanced accuracy
improved +0.855 percentage points; relative to H15, +1.890 points. All three
late folds had blend balanced accuracy above 0.53: 0.5335, 0.5495 and 0.5435.

## Interpretation and boundary

The useful mechanism is target-timescale diversity. The H60-trained model
already ranks H15 direction surprisingly well; the H15 model adds short-horizon
specific information but has a less stable 0.5 boundary in recent folds. Their
fixed average reduces those complementary errors. This is not evidence that
H15 alone should replace H60.

The requested direction improvement has been achieved under the frozen pilot
gate. The next legitimate step is broader walk-forward replication of this
exact recipe—same two models, three seeds, 50:50 probability mean and H15
label—without weight/threshold tuning. It is not yet an economic or live-trading
approval. Only after broader direction replication should TP/SL and execution
economics be revisited.

Verification pinned the source artifact, rebuilt the blend predictions,
recomputed independent metrics/gates, and matched every saved row and hash.
