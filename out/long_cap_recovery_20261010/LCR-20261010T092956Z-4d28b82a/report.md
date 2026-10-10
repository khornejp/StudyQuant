# LONG-CAP-RECOVERY LCR-20261010T092956Z-4d28b82a

Pick `LCR-g-1.5-NONE-a4-x+0.0-h6` (LCR_DEV_BEST_INELIGIBLE). PASS=False COMPLEMENT_PASS=False. Eligible 0/48. Sims 288. Runtime 366.7s.

## Selected, primary cell (offset 2 / pen 0.5) per window

| window | net4 | net8 | gross | funding | entries | closed | open_n | open_mtm | win | fill | mdd | sharpe | exposure_days | turnover | pnl_days_pos | pnl_days_neg | pnl_days_zero | pnl_days_nonzero | top1 | top3 | active_months | pos_month_ratio | boot20 | boot60 | boot120 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV-FULL | 2178.3 | 2138.3 | 2235.9 | -17.7 | 11 | 11 | 0 | 0.0 | 0.8 | 1.0 | 458.4 | 0.8 | 10.0 | 20.0 | 13 | 9 | 2170 | 22 | 0.3 | 0.7 | 11 | 0.8 | 0.3 | 0.4 | 0.4 |
| DEV-A | 1149.1 | 1137.2 | 1164.7 | -3.7 | 3 | 3 | 0 | 0.0 | 0.7 | 1.0 | 253.2 | 0.7 | 3.0 | 5.9 | 4 | 2 | 1455 | 6 | 0.6 | 1.0 | 3 | 0.7 | -0.0 | -0.0 | -0.0 |
| DEV-B | 1029.2 | 1001.1 | 1071.2 | -13.9 | 8 | 8 | 0 | 0.0 | 0.9 | 1.0 | 458.4 | 1.0 | 7.0 | 14.1 | 9 | 7 | 715 | 16 | 0.3 | 0.8 | 8 | 0.9 | 0.3 | 0.5 | 0.6 |
| TEST | -702.2 | -709.6 | -697.1 | 2.4 | 2 | 2 | 0 | 0.0 | 0.0 | 1.0 | 868.1 | -1.4 | 1.9 | 3.7 | 0 | 4 | 276 | 4 | -0.0 | -0.0 | 2 | 0.0 | -5.8 | -5.0 | -4.4 |
| TEST-JanJul | -702.2 | -709.6 | -697.1 | 2.4 | 2 | 2 | 0 | 0.0 | 0.0 | 1.0 | 868.1 | -1.6 | 1.9 | 3.7 | 0 | 4 | 208 | 4 | -0.0 | -0.0 | 2 | 0.0 | -7.7 | -5.9 | -5.9 |
| TEST-AugSep | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0.0 | nan | nan | 0.0 | nan | 0.0 | 0.0 | 0 | 0 | 61 | 0 | nan | nan | 0 | nan | 0.0 | 0.0 | 0.0 |
| TEST-Oct | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0.0 | nan | nan | 0.0 | nan | 0.0 | 0.0 | 0 | 0 | 7 | 0 | nan | nan | 0 | nan | 0.0 | 0.0 | 0.0 |

## Selected, 6 cells net4 per window

| window | o2_p0.5 | o2_p1.0 | o2_p2.0 | o5_p0.5 | o5_p1.0 | o5_p2.0 |
|---|---|---|---|---|---|---|
| DEV-FULL | 2178.3 | 2163.8 | 2163.8 | 2208.9 | 2209.0 | 2204.4 |
| DEV-A | 1149.1 | 1149.1 | 1149.1 | 1158.4 | 1158.4 | 1153.5 |
| DEV-B | 1029.2 | 1014.7 | 1014.7 | 1050.6 | 1050.6 | 1050.8 |
| TEST | -702.2 | -702.2 | -662.8 | -696.8 | -696.8 | -696.8 |
| TEST-JanJul | -702.2 | -702.2 | -662.8 | -696.8 | -696.8 | -696.8 |
| TEST-AugSep | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TEST-Oct | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Bootstrap p05 mean/day (selected, primary)

| window | boot20 | boot60 | boot120 |
|---|---|---|---|
| DEV-FULL | 0.317 | 0.352 | 0.415 |
| DEV-A | -0.037 | -0.037 | -0.037 |
| DEV-B | 0.322 | 0.459 | 0.560 |
| TEST | -5.813 | -5.016 | -4.445 |

## Eligibility counts

{"dev_elig_cells": 12, "dev_elig_closed": 0, "dev_elig_fill": 48, "dev_elig_posdays": 14, "dev_eligible": 0}

## Top 5 by DEV sort (eligible pool if any)

| config_id | dev_eligible | dev_pos_delta | dev_score | dev_cell_floor_pd | dev_abs_pearson | DEV-FULL_comb_mdd | TEST_net4 | TEST_worst_cell | TEST_boot60 |
|---|---|---|---|---|---|---|---|---|---|
| LCR-g-1.5-NONE-a4-x+0.0-h6 | False | 4 | -0.037 | 0.787 | 0.003 | 3673.244 | -702.181 | -702.181 | -5.016 |
| LCR-g-1.5-NONE-a4-x-0.5-h6 | False | 4 | -0.037 | 0.787 | 0.003 | 3673.244 | -702.181 | -702.181 | -5.016 |
| LCR-g-1.5-NONE-a4-x+0.0-h3 | False | 3 | -0.049 | 0.152 | 0.002 | 3673.244 | -349.139 | -349.139 | -2.423 |
| LCR-g-1.5-NONE-a4-x-0.5-h3 | False | 3 | -0.049 | 0.152 | 0.003 | 3673.244 | -308.461 | -308.461 | -2.129 |
| LCR-g-2.0-NONE-a4-x+0.0-h6 | False | 1 | -0.037 | 0.154 | 0.002 | 3673.244 | -702.181 | -702.181 | -5.016 |

## Top 5 by TEST worst cell (report only)

| config_id | dev_eligible | dev_score | TEST_worst_cell | TEST_net4 | TEST_closed | TEST_boot20 | TEST_boot60 | TEST_boot120 |
|---|---|---|---|---|---|---|---|---|
| LCR-g-1.5-NONE-a4-x-0.5-h3 | False | -0.049 | -308.461 | -308.461 | 4 | -2.284 | -2.129 | -1.689 |
| LCR-g-1.5-FUND-a4-x-0.5-h3 | False | -0.070 | -308.461 | -308.461 | 4 | -2.284 | -2.129 | -1.689 |
| LCR-g-2.0-FUND-a4-x-0.5-h3 | False | -0.070 | -308.461 | -308.461 | 4 | -2.284 | -2.129 | -1.689 |
| LCR-g-2.0-NONE-a4-x-0.5-h3 | False | -0.436 | -308.461 | -308.461 | 4 | -2.284 | -2.129 | -1.689 |
| LCR-g-1.5-PREM-a4-x-0.5-h3 | False | -0.070 | -326.502 | -326.502 | 3 | -2.471 | -2.194 | -1.818 |

## Combined-long vs S180 (primary)

| window | net4 | s180_net4 | delta_net4 | mdd | s180_mdd | delta_mdd | sharpe | s180_sharpe | closed | funding | pos_days | delta_positive_days | delta_nonzero_days | boot20 | boot60 | boot120 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV-FULL | 25174.48 | 22996.23 | 2178.25 | 3673.24 | 3673.24 | 0.00 | 1.39 | 1.28 | 112 | -2989.98 | 317 | 13 | 21 | 5.45 | 5.39 | 5.76 |
| DEV-A | 18339.09 | 17190.00 | 1149.09 | 3673.24 | 3673.24 | 0.00 | 1.42 | 1.35 | 68 | -2275.50 | 221 | 4 | 5 | 4.65 | 4.46 | 4.87 |
| DEV-B | 6835.38 | 5806.23 | 1029.16 | 1808.28 | 1894.68 | -86.40 | 1.32 | 1.14 | 44 | -714.48 | 96 | 9 | 16 | 0.96 | 1.83 | 2.89 |
| TEST | 981.93 | 1684.12 | -702.18 | 1280.24 | 1046.31 | 233.93 | 0.58 | 1.05 | 16 | -75.19 | 35 | 0 | 4 | -5.72 | -5.42 | -4.85 |
| TEST-JanJul | -838.54 | -136.36 | -702.18 | 1222.41 | 684.80 | 537.61 | -1.30 | -0.28 | 11 | 6.31 | 9 | 0 | 4 | -9.25 | -8.02 | -7.16 |
| TEST-AugSep | 1863.17 | 1863.17 | 0.00 | 1046.31 | 1046.31 | 0.00 | 2.73 | 2.73 | 5 | -76.11 | 23 | 0 | 0 | 1.99 | 8.77 | 13.83 |
| TEST-Oct | -42.69 | -42.69 | 0.00 | 510.66 | 510.66 | 0.00 | -0.74 | -0.74 | 0 | -5.38 | 3 | 0 | 0 | -40.24 | -6.10 | -6.10 |

## Correlation / overlap (primary)

| window | pearson | spearman | pearson_both_active | new_exposure_min | s180_exposure_min | both_exposure_min | jaccard | new_entries | new_entry_while_s180_open | entry_decision_pm4h_overlap | new_positive_days_when_s180_nonpositive |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV-FULL | -0.003 | -0.008 | nan | 15833 | 760186 | 0 | 0.000 | 11 | 0 | 0.000 | 13 |
| DEV-A | -0.003 | -0.018 | nan | 4319 | 545286 | 0 | 0.000 | 3 | 0 | 0.000 | 4 |
| DEV-B | -0.003 | -0.000 | nan | 11514 | 214900 | 0 | 0.000 | 8 | 0 | 0.000 | 9 |
| TEST | 0.004 | -0.002 | nan | 2891 | 92562 | 0 | 0.000 | 2 | 0 | 0.000 | 0 |
| TEST-JanJul | -0.001 | -0.009 | nan | 2891 | 23000 | 0 | 0.000 | 2 | 0 | 0.000 | 0 |
| TEST-AugSep | nan | nan | nan | 0 | 59482 | 0 | 0.000 | 0 | 0 | nan | 0 |
| TEST-Oct | nan | nan | nan | 0 | 10080 | 0 | 0.000 | 0 | 0 | nan | 0 |

## Monthly net4 (primary, months with new exposure or P&L)

| month | new_net4 | s180_net4 | combined_net4 |
|---|---|---|---|
| 2021-09 | 475.4 | -160.7 | 314.6 |
| 2023-03 | 728.2 | 1604.6 | 2332.8 |
| 2023-08 | -54.5 | 0.0 | -54.5 |
| 2024-03 | 299.2 | 1120.2 | 1419.4 |
| 2024-05 | 343.7 | 0.0 | 343.7 |
| 2024-06 | -159.1 | -274.6 | -433.7 |
| 2024-07 | 112.6 | 0.0 | 112.6 |
| 2025-02 | 48.6 | 0.0 | 48.6 |
| 2025-03 | 202.5 | 0.0 | 202.5 |
| 2025-08 | 82.8 | 0.0 | 82.8 |
| 2025-11 | 98.8 | 0.0 | 98.8 |
| 2026-02 | -159.7 | 0.0 | -159.7 |
| 2026-06 | -542.5 | 0.0 | -542.5 |

## Events (selected)

{"shocks": 27, "arms": 20, "rearms": 4, "recoveries": 13, "expired": 7, "rearmed_episodes": 4, "target1_decisions": 78, "reentry_without_new_shock": 0}

## Checks

```
{
 "parity_s180": {
  "cells_max_abs_diff": 0.0,
  "boot_max_abs_diff": 0.0,
  "trades_equal": true,
  "n_trades": 116,
  "trades_net4_max_abs_diff": 0.0,
  "daily_max_abs_diff": 0.0
 },
 "prefix_check": {
  "cut": "2026-01-01 00:00:00+00:00",
  "decisions_compared": 13152,
  "features_compared": [
   "T",
   "r4",
   "gap",
   "zr4",
   "oi_T",
   "oi_T_avail",
   "oi_24",
   "oi_24_avail",
   "dOI24",
   "zOI24",
   "taker",
   "taker_avail",
   "ztaker",
   "prem_n",
   "prem4",
   "prem_last_avail",
   "zprem",
   "fund",
   "zfund",
   "fund_time",
   "SVI42",
   "dSVI",
   "zdSVI",
   "w"
  ],
  "tamper": "x1.7 future o/h/l/c, oi, taker_lsr, premium, funding rate",
  "configs_checked": 48,
  "closed_trades_compared": 136
 },
 "selection_tamper": {
  "tampered_test_columns": 35,
  "pick_unchanged": true
 },
 "funding_hand_check_max_abs": 4.3520742565306136e-14,
 "gross_max": 1.0,
 "boundary_crossing_trades": {
  "o2_p0.5": 0,
  "o2_p1.0": 0,
  "o2_p2.0": 0,
  "o5_p0.5": 0,
  "o5_p1.0": 0,
  "o5_p2.0": 0
 }
}
```
