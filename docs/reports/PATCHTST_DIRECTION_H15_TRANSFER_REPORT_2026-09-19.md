# PatchTST H15 target-transfer report

Date: 2026-09-19 (Asia/Seoul)

## Result

`H15_TARGET_TRANSFER_FAIL`; independent verification `PASS`.

Retraining the current joint PatchTST for H15 produced a real improvement over
the saved H60 model when both were scored on identical H15 labels, but the gain
was concentrated in the earlier three folds. It did not pass the frozen later
three-fold stability gate.

The original runner stopped after six fits because it assumed every H60 origin
was a non-tie H15 origin. The correction used the strict H15/H60 origin
intersection, hash-reused those six models and fitted twelve new ones. Only two
of 1,687 origins were removed. All metrics use the same 1,685 H15 labels.

## Three-seed ensembles

| Scope | Arm | Pooled AUC | Mean-fold AUC | Mean daily AUC | Balanced accuracy | Log loss | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
|All 6|H60-trained|0.543993|0.552535|0.556386|52.820%|0.690706|0.248783|
|All 6|H15-trained|**0.552198**|**0.564425**|**0.571223**|**54.173%**|**0.690147**|**0.248492**|
|Late 3|H60-trained|**0.531842**|0.552120|0.554515|**52.297%**|0.691816|0.249335|
|Late 3|H15-trained|0.531595|**0.553496**|**0.560554**|51.262%|**0.691263**|**0.249061**|

Across all six folds, H15 gained +0.00821 pooled AUC, +0.01189 mean-fold AUC,
+0.01484 mean daily AUC and +1.352 percentage points balanced accuracy, with
5/6 fold wins and better proper scores. It beat the project's H60 context
benchmarks and won both metrics in at least two individual seeds.

On folds 348/453/598, however, pooled AUC changed -0.00025, mean-fold AUC only
+0.00138 and balanced accuracy -1.035 percentage points. This failure exposed
useful complementary behavior rather than a stable standalone replacement.

No TP/SL, cost, backtest or order was used.
