# R2-16

## 0

| cutoff | seed_n | window_n | cost_bps | live | hold_b_exploratory | parity_exact | parity_total |
|---|---|---|---|---|---|---|---|
| 2026-06-30T23:59:00+00:00 | 3 | 6 | 4.00000000 | 0 | 1 | 11 | 11 |

## 1

| window | spearman_mean | spearman_DEV_mean | spearman_HOLD_B_mean | B_C_cell_seed_both_positive | B_C_cells | all_3seed_both_positive_cells | same_sign_both_segments_cells |
|---|---|---|---|---|---|---|---|
| 30d | 0.00118865 | 0.01392753 | -0.01155022 | 0 | 58 | 0 | 23 |
| 90d | 0.00617791 | 0.02079251 | -0.00843668 | 15 | 58 | 0 | 24 |
| 180d | 0.01168116 | 0.03510040 | -0.01173807 | 15 | 58 | 2 | 33 |
| 365d | 0.00896711 | 0.04066823 | -0.02273401 | 14 | 58 | 1 | 31 |
| expanding | 0.03491571 | 0.04558629 | 0.02424514 | 42 | 58 | 8 | 31 |
| weighted_90d | 0.01406128 | 0.04122119 | -0.01309863 | 9 | 58 | 0 | 22 |

## 2

| window | family | cells | all_3seed_both_positive_cells | same_sign_both_segments_cells |
|---|---|---|---|---|
| 180d | B | 40 | 2 | 27 |
| 180d | C | 18 | 0 | 6 |
| 30d | B | 40 | 0 | 23 |
| 30d | C | 18 | 0 | 0 |
| 365d | B | 40 | 1 | 25 |
| 365d | C | 18 | 0 | 6 |
| 90d | B | 40 | 0 | 22 |
| 90d | C | 18 | 0 | 2 |
| expanding | B | 40 | 3 | 22 |
| expanding | C | 18 | 5 | 9 |
| weighted_90d | B | 40 | 0 | 18 |
| weighted_90d | C | 18 | 0 | 4 |
| 180d | TOTAL | 58 | 2 | 33 |
| 30d | TOTAL | 58 | 0 | 23 |
| 365d | TOTAL | 58 | 1 | 31 |
| 90d | TOTAL | 58 | 0 | 24 |
| expanding | TOTAL | 58 | 8 | 31 |
| weighted_90d | TOTAL | 58 | 0 | 22 |