# k45_funding_plan_review_20261004 — parquet 표 전체

원본 폴더: out/k45_funding_plan_review_20261004/

## boundary_impact.parquet

행 4 × 열 10

| scope | boundary | trade_instances | boundary_trade_n | boundary_nonzero_offset_n | boundary_cashflow_sum_bps | nonzero_offset_cashflow_sum_bps | floor_minus_raw_boundary_bps | floor_minus_raw_all_events_bps | floor_event_count_minus_raw |
|---|---|---|---|---|---|---|---|---|---|
| R2-19 six candidate trade-instances | entry | 5522 | 1312 | 538 | -719.042 | -145.707 | 145.707 | 37.759 | -45 |
| R2-19 six candidate trade-instances | exit | 5522 | 1216 | 493 | -665.602 | -107.948 | -107.948 | 37.759 | -45 |
| R2-6 model metric trade-instances | entry | 745590 | 24372 | 10947 | -12600.4 | -4831.6 | 4831.6 | 1908.38 | -1527 |
| R2-6 model metric trade-instances | exit | 745590 | 20409 | 9420 | -6409.02 | -2923.22 | -2923.22 | 1908.38 | -1527 |

## candidate_impact.parquet

행 12 × 열 23

| cell_id | family | tf | params | exit | direction | segment | n | old_funding_bps | archive_funding_bps | funding_difference_bps | old_net_bps | archive_net_bps | net_difference_bps | old_net_positive | archive_net_positive | net_sign_changed | funding_sign_changed | old_funding_crossings | archive_funding_event_count | difference_per_trade_bps | difference_pct_abs_old_net | archive_over_old_net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1\|1h\|3\|signal\|L | E1 | 1h | 3 | signal | L | DEV | 375 | -1238.06 | -1401.84 | -163.776 | 14636.4 | 14472.7 | -163.776 | True | True | False | False | 375 | 947 | -0.436737 | -1.11896 | 0.98881 |
| E1\|1h\|3\|signal\|L | E1 | 1h | 3 | signal | L | HOLD_B | 30 | -2.4879 | -3.1205 | -0.6326 | 1447.34 | 1446.71 | -0.6326 | True | True | False | False | 30 | 78 | -0.0210867 | -0.0437077 | 0.999563 |
| E1\|1h\|2\|signal\|L | E1 | 1h | 2 | signal | L | DEV | 583 | -1728.22 | -1928.57 | -200.352 | 15518.4 | 15318 | -200.352 | True | True | False | False | 583 | 1476 | -0.343656 | -1.29106 | 0.987089 |
| E1\|1h\|2\|signal\|L | E1 | 1h | 2 | signal | L | HOLD_B | 49 | -5.491 | -5.7303 | -0.2393 | 1917.81 | 1917.57 | -0.2393 | True | True | False | False | 49 | 124 | -0.00488367 | -0.0124778 | 0.999875 |
| F3\|1h\|10/24\|signal\|LS | F3 | 1h | 10/24 | signal | LS | DEV | 873 | 1267.1 | 1179.38 | -87.7183 | 35384.2 | 35296.5 | -87.7183 | True | True | False | False | 869 | 2602 | -0.100479 | -0.247902 | 0.997521 |
| F3\|1h\|10/24\|signal\|LS | F3 | 1h | 10/24 | signal | LS | HOLD_B | 76 | 32.3691 | 31.769 | -0.6001 | 1182.39 | 1181.79 | -0.6001 | True | True | False | False | 76 | 227 | -0.00789605 | -0.050753 | 0.999492 |
| F3\|1h\|5/24\|signal\|LS | F3 | 1h | 5/24 | signal | LS | DEV | 612 | 873.612 | 781.295 | -92.3174 | 28370.3 | 28278 | -92.3174 | True | True | False | False | 609 | 1823 | -0.150845 | -0.325402 | 0.996746 |
| F3\|1h\|5/24\|signal\|LS | F3 | 1h | 5/24 | signal | LS | HOLD_B | 43 | 19.7078 | 21.3679 | 1.6601 | 1036.99 | 1038.65 | 1.6601 | True | True | False | False | 43 | 128 | 0.038607 | 0.160088 | 1.0016 |
| A3\|4h\|720\|signal\|LS | A3 | 4h | 720 | signal | LS | DEV | 339 | -3960.22 | -3999.4 | -39.1847 | 31309.4 | 31270.2 | -39.1847 | True | True | False | False | 287 | 5990 | -0.115589 | -0.125153 | 0.998748 |
| A3\|4h\|720\|signal\|LS | A3 | 4h | 720 | signal | LS | HOLD_B | 45 | 27.99 | 26.3542 | -1.6358 | 3055.94 | 3054.3 | -1.6358 | True | True | False | False | 38 | 540 | -0.0363511 | -0.0535286 | 0.999465 |
| F4\|1h\|5/4\|signal\|L | F4 | 1h | 5/4 | signal | L | DEV | 1812 | -313.514 | -147.2 | 166.314 | 8056.29 | 8222.6 | 166.314 | True | True | False | False | 992 | 992 | 0.0917848 | 2.0644 | 1.02064 |
| F4\|1h\|5/4\|signal\|L | F4 | 1h | 5/4 | signal | L | HOLD_B | 186 | -0.7368 | 12.8576 | 13.5944 | 1122.4 | 1135.99 | 13.5944 | True | True | False | True | 95 | 95 | 0.0730882 | 1.21119 | 1.01211 |

## family_representative_changes.parquet

행 30 × 열 9

| family | old_cell_id | old_daily_sharpe | proxy_cell_id | proxy_archive_sharpe | exact_cell_id | exact_archive_sharpe | proxy_changed | exact_changed |
|---|---|---|---|---|---|---|---|---|
| A1 | A1\|4h\|50/200\|trail2\|L | 0.944275 | A1\|4h\|50/200\|trail2\|L | 0.943678 | A1\|4h\|50/200\|trail2\|L | 0.943934 | False | False |
| A2 | A2\|4h\|55/10\|signal\|L | 0.906944 | A2\|4h\|55/10\|signal\|L | 0.905059 | A2\|4h\|55/10\|signal\|L | 0.905891 | False | False |
| A3 | A3\|4h\|720\|signal\|LS | 0.800353 | A3\|4h\|720\|signal\|LS | 0.799352 | A3\|4h\|720\|signal\|LS | 0.799642 | False | False |
| A4 | A4\|4h\|10/3\|signal\|L | 0.602044 | A4\|4h\|10/3\|signal\|L | 0.599892 | A4\|4h\|10/3\|signal\|L | 0.600443 | False | False |
| A5 | A5\|4h\|25\|trail2\|L | 0.783048 | A5\|4h\|25\|trail2\|L | 0.780024 | A5\|4h\|25\|trail2\|L | 0.781158 | False | False |
| A6 | A6\|1h\|40/60\|signal\|L | 0.363393 | A6\|1h\|40/60\|signal\|L | 0.364315 | A6\|1h\|40/60\|signal\|L | 0.364188 | False | False |
| B1 | B1\|15m\|2.5/12\|signal\|L | -0.275373 | B1\|15m\|2.5/12\|signal\|L | -0.277527 | B1\|15m\|2.5/12\|signal\|L | -0.277507 | False | False |
| B2 | B2\|1h\|20/80/4\|signal\|L | 0.670647 | B2\|1h\|20/80/4\|signal\|L | 0.679102 | B2\|1h\|20/80/4\|signal\|L | 0.676401 | False | False |
| B3 | B3\|1h\|3\|signal\|L | 0.0283035 | B3\|1h\|3\|signal\|L | 0.0400775 | B3\|1h\|3\|signal\|L | 0.040087 | False | False |
| B4 | B4\|1h\|20/5\|signal\|L | -0.432174 | B4\|1h\|20/5\|signal\|L | -0.421766 | B4\|1h\|20/5\|signal\|L | -0.42214 | False | False |
| C1 | C1\|1h\|20/12\|limit\|L | 0.837606 | C1\|1h\|20/12\|limit\|L | 0.832553 | C1\|1h\|20/12\|limit\|L | 0.83342 | False | False |
| C2 | C2\|4h\|20\|signal\|L | 0.385202 | C2\|4h\|20\|signal\|L | 0.386959 | C2\|4h\|20\|signal\|L | 0.387001 | False | False |
| C3 | C3\|4h\|inside\|signal\|L | 0.875279 | C3\|4h\|inside\|signal\|L | 0.873587 | C3\|4h\|inside\|signal\|L | 0.874471 | False | False |
| C4 | C4\|4h\|pin/trend4h\|signal\|S | 0.276383 | C4\|4h\|pin/trend4h\|signal\|S | 0.277794 | C4\|4h\|pin/trend4h\|signal\|S | 0.277959 | False | False |
| C5 | C5\|4h\|3\|signal\|L | 0.27078 | C5\|4h\|3\|signal\|L | 0.269531 | C5\|4h\|3\|signal\|L | 0.269783 | False | False |
| D1 | D1\|1h\|20\|signal\|L | -0.14229 | D1\|4h\|20\|signal\|S | -0.146596 | D1\|4h\|20\|signal\|S | -0.146744 | True | True |
| D2 | D2\|4h\|NR4\|signal\|L | 0.55303 | D2\|4h\|NR4\|signal\|L | 0.548711 | D2\|4h\|NR4\|signal\|L | 0.549393 | False | False |
| E1 | E1\|1h\|3\|signal\|L | 1.14824 | E1\|1h\|3\|signal\|L | 1.13539 | E1\|1h\|3\|signal\|L | 1.1377 | False | False |
| E2 | E2\|1h\|4h/follow/5\|signal\|L | 0.441069 | E2\|1h\|4h/follow/5\|signal\|L | 0.430464 | E2\|1h\|4h/follow/5\|signal\|L | 0.43049 | False | False |
| E3 | E3\|1h\|revert\|signal\|L | 0.137393 | E3\|1h\|revert\|signal\|L | 0.14622 | E3\|1h\|revert\|signal\|L | 0.146101 | False | False |
| F1 | F1\|1h\|5/24\|signal\|LS | 0.749494 | F1\|1h\|5/24\|signal\|LS | 0.726274 | F1\|1h\|5/24\|signal\|LS | 0.727087 | False | False |
| F2 | F2\|4h\|--/fade/24\|signal\|L | 0.305203 | F2\|4h\|--/fade/24\|signal\|L | 0.309724 | F2\|4h\|--/fade/24\|signal\|L | 0.31017 | False | False |
| F3 | F3\|1h\|10/24\|signal\|LS | 1.4856 | F3\|1h\|10/24\|signal\|LS | 1.48191 | F3\|1h\|10/24\|signal\|LS | 1.48366 | False | False |
| F4 | F4\|1h\|5/4\|signal\|L | 0.598889 | F4\|1h\|5/4\|signal\|L | 0.611252 | F4\|1h\|5/4\|signal\|L | 0.610979 | False | False |
| G1 | G1\|1m\|us/60\|signal\|L | 0.647023 | G1\|1m\|us/60\|signal\|L | 0.651567 | G1\|1m\|us/60\|signal\|L | 0.652392 | False | False |
| G2 | G2\|1m\|before/60/60\|signal\|L | 0.791497 | G2\|1m\|before/60/60\|signal\|L | 0.74564 | G2\|1m\|before/60/60\|signal\|L | 0.745175 | False | False |
| G3 | G3\|1d\|1\|signal\|L | 0.739098 | G3\|1d\|1\|signal\|L | 0.741109 | G3\|1d\|1\|signal\|L | 0.741943 | False | False |
| H1 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.149235 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.149444 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.149588 | False | False |
| H2 | H2\|1h\|40/60/funding5\|signal\|L | 0.506216 | H2\|1h\|40/60/funding5\|signal\|L | 0.505041 | H2\|1h\|40/60/funding5\|signal\|L | 0.505077 | False | False |
| H3 | H3\|1h\|4h20/60/C2\|signal\|S | -0.0873438 | H3\|1h\|4h20/60/C2\|signal\|S | -0.0851001 | H3\|1h\|4h20/60/C2\|signal\|S | -0.0851372 | False | False |

## initial_cell_changes.parquet

행 218 × 열 18

| experiment | table | cell_id | segment | rank_group | n | crossing_n | crossing_rate | funding_event_n | signed_difference_mean_bps | absolute_difference_mean_bps | difference_total_bps | old_net_mean_bps | new_net_mean_bps | sign_changed | old_rank | new_rank | rank_changed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gate_direction_1 | backtest | margin=0.00 | DEV | DEV | 10688 | 1034 | 0.096744 | 1034 | -0.0258731 | 0.107138 | -276.532 | -4.09225 | -4.11813 | False | 4 | 4 | False |
| gate_direction_1 | backtest | margin=0.05 | DEV | DEV | 8765 | 850 | 0.0969766 | 850 | -0.0347438 | 0.113016 | -304.53 | -4.02862 | -4.06336 | False | 3 | 3 | False |
| gate_direction_1 | backtest | margin=0.10 | DEV | DEV | 6159 | 556 | 0.0902744 | 556 | -0.0451732 | 0.114226 | -278.222 | -3.63285 | -3.67803 | False | 2 | 2 | False |
| gate_direction_1 | backtest | margin=0.20 | DEV | DEV | 2147 | 182 | 0.0847694 | 182 | -0.062287 | 0.144538 | -133.73 | -1.47433 | -1.53661 | False | 1 | 1 | False |
| gate_direction_1 | backtest | margin=0.00 | HOLD_B | HOLD_B | 1124 | 133 | 0.118327 | 133 | -0.00791619 | 0.0462527 | -8.8978 | -3.46135 | -3.46927 | False | 2 | 2 | False |
| gate_direction_1 | backtest | margin=0.05 | HOLD_B | HOLD_B | 886 | 104 | 0.117381 | 104 | -0.00912043 | 0.0449994 | -8.0807 | 0.00567648 | -0.00344394 | True | 1 | 1 | False |
| gate_direction_1 | backtest | margin=0.10 | HOLD_B | HOLD_B | 524 | 60 | 0.114504 | 60 | -0.00809084 | 0.0460363 | -4.2396 | -4.74031 | -4.7484 | False | 3 | 3 | False |
| gate_direction_1 | backtest | margin=0.20 | HOLD_B | HOLD_B | 65 | 9 | 0.138462 | 9 | -0.000904615 | 0.0464677 | -0.0588 | -5.03376 | -5.03466 | False | 4 | 4 | False |
| gate_direction_r2 | r21_arm | LONG\|h=15 | DEV | DEV\|LONG | 6699 | 210 | 0.031348 | 210 | -0.036441 | 0.0430114 | -244.118 | -2.60545 | -2.64189 | False | 3 | 3 | False |
| gate_direction_r2 | r21_arm | LONG\|h=45 | DEV | DEV\|LONG | 9217 | 911 | 0.0988391 | 911 | -0.107851 | 0.1313 | -994.062 | -2.46856 | -2.57642 | False | 2 | 1 | True |
| gate_direction_r2 | r21_arm | LONG\|h=60 | DEV | DEV\|LONG | 8899 | 1238 | 0.139117 | 1238 | -0.135028 | 0.171552 | -1201.61 | -2.45887 | -2.59389 | False | 1 | 2 | True |
| gate_direction_r2 | r21_arm | SHORT\|h=15 | DEV | DEV\|SHORT | 4032 | 126 | 0.03125 | 126 | 0.0354185 | 0.0479516 | 142.807 | -3.91179 | -3.87638 | False | 2 | 2 | False |
| gate_direction_r2 | r21_arm | SHORT\|h=45 | DEV | DEV\|SHORT | 5216 | 539 | 0.103336 | 539 | 0.0986154 | 0.130063 | 514.378 | -4.62209 | -4.52347 | False | 3 | 3 | False |
| gate_direction_r2 | r21_arm | SHORT\|h=5 | DEV | DEV\|SHORT | 3298 | 43 | 0.0130382 | 43 | 0.0230508 | 0.0269173 | 76.0214 | -1.13345 | -1.1104 | False | 1 | 1 | False |
| gate_direction_r2 | r21_arm | LONG\|h=15 | HOLD_B | HOLD_B\|LONG | 523 | 16 | 0.0305927 | 16 | -6.67304e-05 | 0.0120514 | -0.0349 | -1.12097 | -1.12104 | False | 3 | 3 | False |
| gate_direction_r2 | r21_arm | LONG\|h=45 | HOLD_B | HOLD_B\|LONG | 758 | 102 | 0.134565 | 102 | -0.00898219 | 0.0464753 | -6.8085 | -0.374512 | -0.383494 | False | 2 | 2 | False |
| gate_direction_r2 | r21_arm | LONG\|h=60 | HOLD_B | HOLD_B\|LONG | 821 | 153 | 0.186358 | 153 | -0.0149386 | 0.0753177 | -12.2646 | 0.916198 | 0.90126 | False | 1 | 1 | False |
| gate_direction_r2 | r21_arm | SHORT\|h=15 | HOLD_B | HOLD_B\|SHORT | 265 | 9 | 0.0339623 | 9 | -0.00565283 | 0.0180528 | -1.498 | -1.86212 | -1.86777 | False | 1 | 1 | False |
| gate_direction_r2 | r21_arm | SHORT\|h=45 | HOLD_B | HOLD_B\|SHORT | 446 | 54 | 0.121076 | 54 | 0.0109531 | 0.0571729 | 4.8851 | -3.00236 | -2.9914 | False | 2 | 2 | False |
| gate_direction_r2 | r21_arm | SHORT\|h=5 | HOLD_B | HOLD_B\|SHORT | 111 | 2 | 0.018018 | 2 | 0.00270901 | 0.00270901 | 0.3007 | -3.80171 | -3.799 | False | 3 | 3 | False |
| gate_direction_r2 | r21_decision | MODEL\|SINGLE | DEV | DEV | 7732 | 752 | 0.0972581 | 752 | -0.0300146 | 0.11984 | -232.073 | -2.95187 | -2.98189 | False | 1 | 1 | False |
| gate_direction_r2 | r21_decision | RANDOM_DIRECTION\|SAME_ENTRIES | DEV | DEV | 7732 | 752 | 0.0972581 | 752 | -0.00390974 | 0.11984 | -30.2301 | -4.81645 | -4.82036 | False | 2 | 2 | False |
| gate_direction_r2 | r21_decision | MODEL\|SINGLE | HOLD_B | HOLD_B | 706 | 84 | 0.11898 | 84 | -0.00798541 | 0.045554 | -5.6377 | -2.61626 | -2.62425 | False | 1 | 1 | False |
| gate_direction_r2 | r21_decision | RANDOM_DIRECTION\|SAME_ENTRIES | HOLD_B | HOLD_B | 706 | 84 | 0.11898 | 84 | -0.00570751 | 0.045554 | -4.0295 | -7.0403 | -7.04601 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|ALL | DEV | DEV\|MULTICLASS_0.10 | 10226 | 970 | 0.0948562 | 970 | -0.0520174 | 0.122106 | -531.93 | -2.95828 | -3.01029 | False | 1 | 1 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|CAP3 | DEV | DEV\|MULTICLASS_0.10 | 10226 | 970 | 0.0948562 | 970 | -0.0520174 | 0.122106 | -531.93 | -2.95828 | -3.01029 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|SINGLE | DEV | DEV\|MULTICLASS_0.10 | 6159 | 556 | 0.0902744 | 556 | -0.0451732 | 0.114226 | -278.222 | -3.63285 | -3.67803 | False | 3 | 3 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|ALL | DEV | DEV\|MULTICLASS_0.20 | 2967 | 264 | 0.0889788 | 264 | -0.0631446 | 0.152707 | -187.35 | 0.0519539 | -0.0111906 | True | 1 | 1 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|CAP3 | DEV | DEV\|MULTICLASS_0.20 | 2967 | 264 | 0.0889788 | 264 | -0.0631446 | 0.152707 | -187.35 | 0.0519539 | -0.0111906 | True | 2 | 2 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|SINGLE | DEV | DEV\|MULTICLASS_0.20 | 2147 | 182 | 0.0847694 | 182 | -0.062287 | 0.144538 | -133.73 | -1.47433 | -1.53661 | False | 3 | 3 | False |
| gate_direction_r2 | r22_books | R2-1\|ALL | DEV | DEV\|R2-1 | 14210 | 1430 | 0.100633 | 1430 | -0.0348001 | 0.128891 | -494.509 | -3.49299 | -3.52779 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | R2-1\|CAP3 | DEV | DEV\|R2-1 | 14210 | 1430 | 0.100633 | 1430 | -0.0348001 | 0.128891 | -494.509 | -3.49299 | -3.52779 | False | 3 | 3 | False |
| gate_direction_r2 | r22_books | R2-1\|SINGLE | DEV | DEV\|R2-1 | 7732 | 752 | 0.0972581 | 752 | -0.0300146 | 0.11984 | -232.073 | -2.95187 | -2.98189 | False | 1 | 1 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|ALL | HOLD_B | HOLD_B\|MULTICLASS_0.10 | 767 | 96 | 0.125163 | 96 | -0.0145134 | 0.0496125 | -11.1318 | -2.00224 | -2.01675 | False | 1 | 1 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|CAP3 | HOLD_B | HOLD_B\|MULTICLASS_0.10 | 767 | 96 | 0.125163 | 96 | -0.0145134 | 0.0496125 | -11.1318 | -2.00224 | -2.01675 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.10\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS_0.10 | 524 | 60 | 0.114504 | 60 | -0.00809084 | 0.0460363 | -4.2396 | -4.74031 | -4.7484 | False | 3 | 3 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|ALL | HOLD_B | HOLD_B\|MULTICLASS_0.20 | 72 | 11 | 0.152778 | 11 | -0.0147653 | 0.0558986 | -1.0631 | 4.45165 | 4.43689 | False | 1 | 1 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|CAP3 | HOLD_B | HOLD_B\|MULTICLASS_0.20 | 72 | 11 | 0.152778 | 11 | -0.0147653 | 0.0558986 | -1.0631 | 4.45165 | 4.43689 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS_0.20 | 65 | 9 | 0.138462 | 9 | -0.000904615 | 0.0464677 | -0.0588 | -5.03376 | -5.03466 | False | 3 | 3 | False |
| gate_direction_r2 | r22_books | R2-1\|ALL | HOLD_B | HOLD_B\|R2-1 | 1201 | 156 | 0.129892 | 156 | -0.0016015 | 0.050564 | -1.9234 | -1.44751 | -1.44911 | False | 1 | 1 | False |
| gate_direction_r2 | r22_books | R2-1\|CAP3 | HOLD_B | HOLD_B\|R2-1 | 1201 | 156 | 0.129892 | 156 | -0.0016015 | 0.050564 | -1.9234 | -1.44751 | -1.44911 | False | 2 | 2 | False |
| gate_direction_r2 | r22_books | R2-1\|SINGLE | HOLD_B | HOLD_B\|R2-1 | 706 | 84 | 0.11898 | 84 | -0.00798541 | 0.045554 | -5.6377 | -2.61626 | -2.62425 | False | 3 | 3 | False |
| gate_direction_r2 | r23_backtest | EXCLUDE\|ALL | DEV | DEV | 10463 | 1004 | 0.0959572 | 1004 | -0.0576056 | 0.125452 | -602.728 | -2.09384 | -2.15145 | False | 2 | 2 | False |
| gate_direction_r2 | r23_backtest | EXCLUDE\|SINGLE | DEV | DEV | 6300 | 581 | 0.0922222 | 581 | -0.0473345 | 0.115779 | -298.207 | -2.81162 | -2.85895 | False | 4 | 4 | False |
| gate_direction_r2 | r23_backtest | RESIDUAL\|ALL | DEV | DEV | 11307 | 1096 | 0.0969311 | 1096 | -0.0624689 | 0.129786 | -706.336 | -1.57528 | -1.63775 | False | 1 | 1 | False |
| gate_direction_r2 | r23_backtest | RESIDUAL\|SINGLE | DEV | DEV | 6657 | 626 | 0.0940364 | 626 | -0.0479799 | 0.120382 | -319.402 | -2.18934 | -2.23732 | False | 3 | 3 | False |
| gate_direction_r2 | r23_backtest | EXCLUDE\|ALL | HOLD_B | HOLD_B | 693 | 74 | 0.106782 | 74 | -0.00264343 | 0.0398253 | -1.8319 | -3.36271 | -3.36535 | False | 1 | 1 | False |
| gate_direction_r2 | r23_backtest | EXCLUDE\|SINGLE | HOLD_B | HOLD_B | 480 | 51 | 0.10625 | 51 | -0.00109188 | 0.0388348 | -0.5241 | -6.00999 | -6.01108 | False | 3 | 3 | False |
| gate_direction_r2 | r23_backtest | RESIDUAL\|ALL | HOLD_B | HOLD_B | 726 | 81 | 0.11157 | 81 | -0.00658168 | 0.0400167 | -4.7783 | -3.46445 | -3.47103 | False | 2 | 2 | False |
| gate_direction_r2 | r23_backtest | RESIDUAL\|SINGLE | HOLD_B | HOLD_B | 498 | 60 | 0.120482 | 60 | -0.00268394 | 0.0405871 | -1.3366 | -7.0152 | -7.01789 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|HIGH\|ALL | DEV | DEV\|MULTICLASS\|HIGH\|ALL | 249 | 14 | 0.0562249 | 14 | -0.0371378 | 0.0396703 | -9.2473 | 4.50667 | 4.46953 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|ALL | DEV | DEV\|MULTICLASS\|HIGH\|ALL | 497 | 36 | 0.0724346 | 36 | -0.0824471 | 0.0969859 | -40.9762 | 2.41576 | 2.33331 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|HIGH\|ALL | DEV | DEV\|MULTICLASS\|HIGH\|ALL | 1243 | 100 | 0.0804505 | 100 | -0.129892 | 0.157762 | -161.456 | 3.09955 | 2.96966 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|HIGH\|ALL | DEV | DEV\|MULTICLASS\|HIGH\|ALL | 2485 | 212 | 0.0853119 | 212 | -0.116268 | 0.150045 | -288.926 | 0.886065 | 0.769797 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|HIGH\|SINGLE | DEV | DEV\|MULTICLASS\|HIGH\|SINGLE | 154 | 8 | 0.0519481 | 8 | -0.0377422 | 0.0391071 | -5.8123 | 6.92507 | 6.88733 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|SINGLE | DEV | DEV\|MULTICLASS\|HIGH\|SINGLE | 319 | 24 | 0.0752351 | 24 | -0.105625 | 0.126959 | -33.6945 | 0.0141241 | -0.0915013 | True | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|HIGH\|SINGLE | DEV | DEV\|MULTICLASS\|HIGH\|SINGLE | 847 | 70 | 0.0826446 | 70 | -0.131652 | 0.163738 | -111.509 | -0.384266 | -0.515918 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|HIGH\|SINGLE | DEV | DEV\|MULTICLASS\|HIGH\|SINGLE | 1666 | 134 | 0.0804322 | 134 | -0.113088 | 0.131807 | -188.404 | -0.305732 | -0.418819 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|LOW\|ALL | DEV | DEV\|MULTICLASS\|LOW\|ALL | 249 | 20 | 0.0803213 | 20 | 0.146843 | 0.165765 | 36.564 | -2.468 | -2.32116 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|LOW\|ALL | DEV | DEV\|MULTICLASS\|LOW\|ALL | 497 | 53 | 0.10664 | 53 | 0.142733 | 0.179178 | 70.9383 | -0.900486 | -0.757753 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|LOW\|ALL | DEV | DEV\|MULTICLASS\|LOW\|ALL | 1243 | 127 | 0.102172 | 127 | 0.0984104 | 0.132202 | 122.324 | -3.42533 | -3.32692 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|LOW\|ALL | DEV | DEV\|MULTICLASS\|LOW\|ALL | 2485 | 244 | 0.0981891 | 244 | 0.0898255 | 0.114292 | 223.216 | -6.10811 | -6.01828 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|LOW\|SINGLE | DEV | DEV\|MULTICLASS\|LOW\|SINGLE | 232 | 18 | 0.0775862 | 18 | 0.154793 | 0.172102 | 35.912 | -2.24435 | -2.08956 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|LOW\|SINGLE | DEV | DEV\|MULTICLASS\|LOW\|SINGLE | 449 | 48 | 0.106904 | 48 | 0.151023 | 0.183204 | 67.8095 | -0.584369 | -0.433346 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|LOW\|SINGLE | DEV | DEV\|MULTICLASS\|LOW\|SINGLE | 1039 | 100 | 0.0962464 | 100 | 0.0883705 | 0.1241 | 91.817 | -3.49623 | -3.40786 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|LOW\|SINGLE | DEV | DEV\|MULTICLASS\|LOW\|SINGLE | 1864 | 172 | 0.0922747 | 172 | 0.0780298 | 0.106198 | 145.448 | -5.99703 | -5.919 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|HIGH\|ALL | DEV | DEV\|R21_LONG_EDGE\|HIGH\|ALL | 249 | 17 | 0.0682731 | 17 | -0.0463783 | 0.0489108 | -11.5482 | -5.16398 | -5.21036 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|HIGH\|ALL | DEV | DEV\|R21_LONG_EDGE\|HIGH\|ALL | 497 | 44 | 0.0885312 | 44 | -0.0373801 | 0.140967 | -18.5779 | 6.39869 | 6.36131 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|HIGH\|ALL | DEV | DEV\|R21_LONG_EDGE\|HIGH\|ALL | 1243 | 107 | 0.0860821 | 107 | -0.102043 | 0.15912 | -126.839 | 4.77986 | 4.67781 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|HIGH\|ALL | DEV | DEV\|R21_LONG_EDGE\|HIGH\|ALL | 2485 | 231 | 0.0929577 | 231 | -0.122576 | 0.157596 | -304.6 | 2.2231 | 2.10052 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|HIGH\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|HIGH\|SINGLE | 145 | 9 | 0.062069 | 9 | -0.0462138 | 0.0476634 | -6.701 | -4.05751 | -4.10372 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|HIGH\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|HIGH\|SINGLE | 317 | 27 | 0.0851735 | 27 | -0.0334473 | 0.117131 | -10.6028 | 5.14741 | 5.11396 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|HIGH\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|HIGH\|SINGLE | 844 | 67 | 0.0793839 | 67 | -0.101984 | 0.135222 | -86.0745 | 4.94733 | 4.84535 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|HIGH\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|HIGH\|SINGLE | 1618 | 148 | 0.091471 | 148 | -0.120325 | 0.147251 | -194.686 | 1.58168 | 1.46136 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|LOW\|ALL | DEV | DEV\|R21_LONG_EDGE\|LOW\|ALL | 249 | 26 | 0.104418 | 26 | 0.185813 | 0.266274 | 46.2674 | 0.435704 | 0.621516 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|LOW\|ALL | DEV | DEV\|R21_LONG_EDGE\|LOW\|ALL | 497 | 56 | 0.112676 | 56 | 0.156362 | 0.212911 | 77.712 | -2.56164 | -2.40527 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|LOW\|ALL | DEV | DEV\|R21_LONG_EDGE\|LOW\|ALL | 1243 | 127 | 0.102172 | 127 | 0.123081 | 0.15169 | 152.989 | -6.91151 | -6.78843 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|LOW\|ALL | DEV | DEV\|R21_LONG_EDGE\|LOW\|ALL | 2485 | 261 | 0.10503 | 261 | 0.115508 | 0.136831 | 287.038 | -5.98109 | -5.86558 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|LOW\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|LOW\|SINGLE | 211 | 20 | 0.0947867 | 20 | 0.201829 | 0.234589 | 42.5859 | 2.91171 | 3.11354 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|LOW\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|LOW\|SINGLE | 428 | 44 | 0.102804 | 44 | 0.17223 | 0.200375 | 73.7143 | 0.0999111 | 0.272141 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|LOW\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|LOW\|SINGLE | 1007 | 99 | 0.0983118 | 99 | 0.138169 | 0.153243 | 139.136 | -5.72954 | -5.59137 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|LOW\|SINGLE | DEV | DEV\|R21_LONG_EDGE\|LOW\|SINGLE | 1850 | 188 | 0.101622 | 188 | 0.111544 | 0.128119 | 206.356 | -4.21531 | -4.10376 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|HIGH\|ALL | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|ALL | 249 | 28 | 0.11245 | 28 | 0.201166 | 0.286469 | 50.0903 | -2.75393 | -2.55277 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|HIGH\|ALL | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|ALL | 497 | 56 | 0.112676 | 56 | 0.174541 | 0.226371 | 86.7468 | -2.356 | -2.18146 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|HIGH\|ALL | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|ALL | 1243 | 136 | 0.109413 | 136 | 0.137633 | 0.174072 | 171.078 | -4.38011 | -4.24248 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|HIGH\|ALL | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|ALL | 2485 | 245 | 0.0985915 | 245 | 0.108946 | 0.13744 | 270.73 | -5.75756 | -5.64861 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|HIGH\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|SINGLE | 218 | 23 | 0.105505 | 23 | 0.19845 | 0.252169 | 43.262 | -1.40839 | -1.20994 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|HIGH\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|SINGLE | 425 | 47 | 0.110588 | 47 | 0.152531 | 0.190719 | 64.8255 | -2.64707 | -2.49454 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|HIGH\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|SINGLE | 1005 | 104 | 0.103483 | 104 | 0.130074 | 0.155839 | 130.724 | -3.81749 | -3.68742 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|HIGH\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|HIGH\|SINGLE | 1857 | 174 | 0.0936995 | 174 | 0.0942249 | 0.11978 | 174.976 | -4.48042 | -4.3862 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|LOW\|ALL | DEV | DEV\|R21_SHORT_EDGE\|LOW\|ALL | 249 | 20 | 0.0803213 | 20 | -0.0544843 | 0.0570169 | -13.5666 | 2.66225 | 2.60777 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|LOW\|ALL | DEV | DEV\|R21_SHORT_EDGE\|LOW\|ALL | 497 | 39 | 0.0784708 | 39 | -0.0474419 | 0.124875 | -23.5786 | 1.79286 | 1.74541 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|LOW\|ALL | DEV | DEV\|R21_SHORT_EDGE\|LOW\|ALL | 1243 | 105 | 0.084473 | 105 | -0.0771994 | 0.122059 | -95.9588 | 1.42165 | 1.34445 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|LOW\|ALL | DEV | DEV\|R21_SHORT_EDGE\|LOW\|ALL | 2485 | 205 | 0.082495 | 205 | -0.0893922 | 0.12129 | -222.139 | -0.139218 | -0.228611 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|LOW\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|LOW\|SINGLE | 158 | 11 | 0.0696203 | 11 | -0.048857 | 0.0501873 | -7.7194 | 7.27416 | 7.2253 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|LOW\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|LOW\|SINGLE | 315 | 25 | 0.0793651 | 25 | -0.0767171 | 0.140604 | -24.1659 | 4.84583 | 4.76911 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|LOW\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|LOW\|SINGLE | 832 | 67 | 0.0805288 | 67 | -0.0750456 | 0.112071 | -62.4379 | -1.65949 | -1.73454 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|LOW\|SINGLE | DEV | DEV\|R21_SHORT_EDGE\|LOW\|SINGLE | 1631 | 137 | 0.0839975 | 137 | -0.0944123 | 0.122296 | -153.986 | -2.322 | -2.41641 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|HIGH\|ALL | DEV | DEV\|REGRESSION_RMSE\|HIGH\|ALL | 249 | 14 | 0.0562249 | 14 | 0.0449627 | 0.10062 | 11.1957 | 31.091 | 31.1359 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|HIGH\|ALL | DEV | DEV\|REGRESSION_RMSE\|HIGH\|ALL | 497 | 32 | 0.0643863 | 32 | -0.0189219 | 0.108759 | -9.4042 | 18.209 | 18.1901 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|HIGH\|ALL | DEV | DEV\|REGRESSION_RMSE\|HIGH\|ALL | 1243 | 100 | 0.0804505 | 100 | -0.0846453 | 0.15109 | -105.214 | 5.99335 | 5.9087 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|HIGH\|ALL | DEV | DEV\|REGRESSION_RMSE\|HIGH\|ALL | 2485 | 214 | 0.0861167 | 214 | -0.099125 | 0.139258 | -246.326 | 2.04296 | 1.94384 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|HIGH\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|HIGH\|SINGLE | 165 | 8 | 0.0484848 | 8 | 0.0626248 | 0.114553 | 10.3331 | 23.3071 | 23.3697 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|HIGH\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|HIGH\|SINGLE | 308 | 20 | 0.0649351 | 20 | -0.0447182 | 0.10866 | -13.7732 | 21.9726 | 21.9279 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|HIGH\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|HIGH\|SINGLE | 758 | 55 | 0.0725594 | 55 | -0.0899917 | 0.142208 | -68.2137 | 2.56889 | 2.4789 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|HIGH\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|HIGH\|SINGLE | 1468 | 117 | 0.0797003 | 117 | -0.090773 | 0.127149 | -133.255 | -0.778077 | -0.86885 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|LOW\|ALL | DEV | DEV\|REGRESSION_RMSE\|LOW\|ALL | 249 | 16 | 0.064257 | 16 | 0.190427 | 0.229784 | 47.4163 | 4.69625 | 4.88667 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|LOW\|ALL | DEV | DEV\|REGRESSION_RMSE\|LOW\|ALL | 497 | 39 | 0.0784708 | 39 | 0.155467 | 0.250737 | 77.2673 | 3.22055 | 3.37602 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|LOW\|ALL | DEV | DEV\|REGRESSION_RMSE\|LOW\|ALL | 1243 | 111 | 0.0893001 | 111 | 0.139528 | 0.213576 | 173.433 | 2.44628 | 2.58581 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|LOW\|ALL | DEV | DEV\|REGRESSION_RMSE\|LOW\|ALL | 2485 | 228 | 0.0917505 | 228 | 0.128467 | 0.169795 | 319.24 | -3.18138 | -3.05291 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|LOW\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|LOW\|SINGLE | 218 | 14 | 0.0642202 | 14 | 0.192706 | 0.237128 | 42.01 | 11.9022 | 12.0949 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|LOW\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|LOW\|SINGLE | 399 | 29 | 0.0726817 | 29 | 0.150073 | 0.241519 | 59.879 | 8.45454 | 8.60461 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|LOW\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|LOW\|SINGLE | 916 | 84 | 0.0917031 | 84 | 0.144148 | 0.205481 | 132.039 | 3.66784 | 3.81199 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|LOW\|SINGLE | DEV | DEV\|REGRESSION_RMSE\|LOW\|SINGLE | 1661 | 153 | 0.0921132 | 153 | 0.117761 | 0.153191 | 195.6 | -4.34829 | -4.23053 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|HIGH\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 249 | 18 | 0.0722892 | 18 | 0.015347 | 0.116504 | 3.8214 | 33.2481 | 33.2634 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|HIGH\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 497 | 39 | 0.0784708 | 39 | -0.0353336 | 0.101814 | -17.5608 | 17.9927 | 17.9574 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|HIGH\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 1243 | 103 | 0.082864 | 103 | -0.0854452 | 0.142782 | -106.208 | 6.08925 | 6.0038 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|HIGH\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 2485 | 215 | 0.0865191 | 215 | -0.0989348 | 0.136364 | -245.853 | 3.36079 | 3.26185 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|HIGH\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 177 | 11 | 0.0621469 | 11 | 0.0204718 | 0.125377 | 3.6235 | 28.9733 | 28.9938 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|HIGH\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 347 | 28 | 0.0806916 | 28 | -0.0423242 | 0.117325 | -14.6865 | 18.0771 | 18.0348 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|HIGH\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 806 | 59 | 0.073201 | 59 | -0.0968815 | 0.132086 | -78.0865 | 4.59127 | 4.49439 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|HIGH\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 1526 | 115 | 0.0753604 | 115 | -0.096102 | 0.123196 | -146.652 | 2.52457 | 2.42847 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|LOW\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|ALL | 249 | 19 | 0.0763052 | 19 | 0.120283 | 0.228095 | 29.9505 | 10.7521 | 10.8724 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|LOW\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|ALL | 497 | 41 | 0.082495 | 41 | 0.119289 | 0.20549 | 59.2864 | 0.33433 | 0.453619 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|LOW\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|ALL | 1243 | 120 | 0.0965406 | 120 | 0.118409 | 0.160102 | 147.183 | 1.52616 | 1.64457 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|LOW\|ALL | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|ALL | 2485 | 234 | 0.094165 | 234 | 0.103011 | 0.133573 | 255.982 | -1.69699 | -1.59398 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|LOW\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 235 | 18 | 0.0765957 | 18 | 0.104197 | 0.218431 | 24.4862 | 10.0768 | 10.181 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|LOW\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 429 | 38 | 0.0885781 | 38 | 0.11478 | 0.214646 | 49.2408 | 4.1115 | 4.22628 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|LOW\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 1021 | 95 | 0.093046 | 95 | 0.118457 | 0.16491 | 120.945 | 4.19758 | 4.31604 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|LOW\|SINGLE | DEV | DEV\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 1814 | 174 | 0.0959206 | 174 | 0.0937082 | 0.132195 | 169.987 | -1.54075 | -1.44705 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|HIGH\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|ALL | 27 | 6 | 0.222222 | 6 | -0.0431444 | 0.0847667 | -1.1649 | 17.8967 | 17.8535 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|ALL | 54 | 8 | 0.148148 | 8 | -0.00455556 | 0.0594 | -0.246 | 12.1264 | 12.1218 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|HIGH\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|ALL | 133 | 18 | 0.135338 | 18 | -0.00370301 | 0.0531737 | -0.4925 | 2.35863 | 2.35493 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|HIGH\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|ALL | 266 | 29 | 0.109023 | 29 | -0.00144624 | 0.039268 | -0.3847 | 3.11656 | 3.11512 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|HIGH\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|SINGLE | 24 | 4 | 0.166667 | 4 | -0.00669167 | 0.0535167 | -0.1606 | 5.94758 | 5.94089 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|SINGLE | 47 | 6 | 0.12766 | 6 | 0.016134 | 0.0468787 | 0.7583 | 0.151328 | 0.167462 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|HIGH\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|SINGLE | 107 | 15 | 0.140187 | 15 | 0.00397664 | 0.0559019 | 0.4255 | -10.2198 | -10.2159 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|HIGH\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|HIGH\|SINGLE | 199 | 23 | 0.115578 | 23 | -0.00343568 | 0.040893 | -0.6837 | -3.03809 | -3.04153 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|LOW\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|ALL | 27 | 4 | 0.148148 | 4 | -0.0371185 | 0.0371185 | -1.0022 | -6.3049 | -6.34202 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|LOW\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|ALL | 54 | 6 | 0.111111 | 6 | -0.0458778 | 0.0458778 | -2.4774 | -9.82787 | -9.87374 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|LOW\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|ALL | 133 | 16 | 0.120301 | 16 | -0.00970602 | 0.0526218 | -1.2909 | -14.6627 | -14.6724 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|LOW\|ALL | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|ALL | 266 | 34 | 0.12782 | 34 | -0.0113177 | 0.0613124 | -3.0105 | -9.12045 | -9.13177 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.01\|LOW\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|SINGLE | 26 | 3 | 0.115385 | 3 | -0.0324038 | 0.0324038 | -0.8425 | -16.2439 | -16.2763 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|LOW\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|SINGLE | 50 | 5 | 0.1 | 5 | -0.046354 | 0.046354 | -2.3177 | -9.98563 | -10.032 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.05\|LOW\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|SINGLE | 107 | 12 | 0.11215 | 12 | -0.0168626 | 0.0506589 | -1.8043 | -17.91 | -17.9269 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.10\|LOW\|SINGLE | HOLD_B | HOLD_B\|MULTICLASS\|LOW\|SINGLE | 198 | 25 | 0.126263 | 25 | -0.00534949 | 0.0619505 | -1.0592 | -11.668 | -11.6733 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|ALL | 27 | 6 | 0.222222 | 6 | 0.0280852 | 0.0816037 | 0.7583 | 30.2094 | 30.2375 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|ALL | 54 | 9 | 0.166667 | 9 | 0.0234185 | 0.0560296 | 1.2646 | 32.4375 | 32.4609 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|ALL | 133 | 19 | 0.142857 | 19 | 0.0255564 | 0.0534962 | 3.399 | 18.3496 | 18.3752 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|ALL | 266 | 34 | 0.12782 | 34 | -0.00187256 | 0.0465665 | -0.4981 | 2.90361 | 2.90174 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|SINGLE | 23 | 6 | 0.26087 | 6 | 0.0329696 | 0.0957957 | 0.7583 | 5.48091 | 5.51388 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|SINGLE | 44 | 8 | 0.181818 | 8 | 0.0164477 | 0.0564705 | 0.7237 | 9.23308 | 9.24952 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|SINGLE | 100 | 13 | 0.13 | 13 | 0.013558 | 0.038678 | 1.3558 | 11.4944 | 11.5079 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|HIGH\|SINGLE | 184 | 23 | 0.125 | 23 | -0.0141332 | 0.0432592 | -2.6005 | -1.26921 | -1.28335 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|LOW\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|ALL | 27 | 4 | 0.148148 | 4 | -0.0107481 | 0.0494815 | -0.2902 | -6.83748 | -6.84822 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|LOW\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|ALL | 54 | 9 | 0.166667 | 9 | 0.00726667 | 0.0564852 | 0.3924 | -17.3994 | -17.3921 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|LOW\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|ALL | 133 | 18 | 0.135338 | 18 | 0.00906692 | 0.0552504 | 1.2059 | -13.1798 | -13.1707 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|LOW\|ALL | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|ALL | 266 | 30 | 0.112782 | 30 | 0.0118726 | 0.050765 | 3.1581 | -9.64435 | -9.63247 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.01\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|SINGLE | 26 | 3 | 0.115385 | 3 | 0.00140385 | 0.0388192 | 0.0365 | -4.768 | -4.7666 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.02\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|SINGLE | 44 | 6 | 0.136364 | 6 | -0.007425 | 0.0381295 | -0.3267 | -13.3234 | -13.3308 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.05\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|SINGLE | 104 | 12 | 0.115385 | 12 | 0.0105202 | 0.0516202 | 1.0941 | -17.6073 | -17.5968 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_LONG_EDGE\|share=0.10\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_LONG_EDGE\|LOW\|SINGLE | 203 | 23 | 0.1133 | 23 | 0.011836 | 0.0535966 | 2.4027 | -9.28772 | -9.27588 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|ALL | 27 | 5 | 0.185185 | 5 | -0.0668519 | 0.0808444 | -1.805 | 9.2282 | 9.16135 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|ALL | 54 | 8 | 0.148148 | 8 | -0.045337 | 0.0523333 | -2.4482 | -2.07578 | -2.12111 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|ALL | 133 | 16 | 0.120301 | 16 | -0.0118865 | 0.0419767 | -1.5809 | -10.1234 | -10.1353 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|HIGH\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|ALL | 266 | 31 | 0.116541 | 31 | -0.000346992 | 0.0536575 | -0.0923 | -6.58507 | -6.58542 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|SINGLE | 22 | 4 | 0.181818 | 4 | -0.0747864 | 0.0919591 | -1.6453 | -5.59635 | -5.67114 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|SINGLE | 40 | 6 | 0.15 | 6 | -0.05322 | 0.062665 | -2.1288 | -16.372 | -16.4252 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|SINGLE | 99 | 13 | 0.131313 | 13 | -0.0119859 | 0.0524101 | -1.1866 | -16.6024 | -16.6144 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|HIGH\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|HIGH\|SINGLE | 188 | 23 | 0.12234 | 23 | 0.0112601 | 0.0569824 | 2.1169 | -10.3908 | -10.3795 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|LOW\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|ALL | 27 | 5 | 0.185185 | 5 | 0.00921111 | 0.0925296 | 0.2487 | 10.7514 | 10.7606 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|LOW\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|ALL | 54 | 6 | 0.111111 | 6 | -0.00654259 | 0.057413 | -0.3533 | 5.34477 | 5.33823 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|LOW\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|ALL | 133 | 15 | 0.112782 | 15 | -0.0213496 | 0.0517511 | -2.8395 | 1.47728 | 1.45593 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|LOW\|ALL | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|ALL | 266 | 27 | 0.101504 | 27 | -0.0148421 | 0.0420353 | -3.948 | 5.07874 | 5.0639 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.01\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|SINGLE | 25 | 5 | 0.2 | 5 | 0.009948 | 0.099932 | 0.2487 | 11.2422 | 11.2521 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.02\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|SINGLE | 47 | 5 | 0.106383 | 5 | 0.00529149 | 0.0531553 | 0.2487 | -4.93006 | -4.92477 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.05\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|SINGLE | 108 | 11 | 0.101852 | 11 | -0.0297102 | 0.0417139 | -3.2087 | -3.13823 | -3.16794 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | R21_SHORT_EDGE\|share=0.10\|LOW\|SINGLE | HOLD_B | HOLD_B\|R21_SHORT_EDGE\|LOW\|SINGLE | 199 | 17 | 0.0854271 | 17 | -0.0218151 | 0.0351246 | -4.3412 | -0.0620896 | -0.0839047 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|HIGH\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|ALL | 27 | 1 | 0.037037 | 1 | 0.030837 | 0.030837 | 0.8326 | 54.7176 | 54.7484 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|HIGH\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|ALL | 54 | 6 | 0.111111 | 6 | 0.00283704 | 0.0400333 | 0.1532 | 8.90697 | 8.90981 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|HIGH\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|ALL | 133 | 18 | 0.135338 | 18 | 0.00716617 | 0.0528669 | 0.9531 | 6.17131 | 6.17848 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|HIGH\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|ALL | 266 | 32 | 0.120301 | 32 | 0.00695414 | 0.0400925 | 1.8498 | 2.43482 | 2.44177 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|HIGH\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|SINGLE | 22 | 1 | 0.0454545 | 1 | 0.0378455 | 0.0378455 | 0.8326 | 41.6625 | 41.7003 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|HIGH\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|SINGLE | 37 | 3 | 0.0810811 | 3 | 0.0145568 | 0.0363027 | 0.5386 | 0.18765 | 0.202206 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|HIGH\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|SINGLE | 81 | 9 | 0.111111 | 9 | 0.00518889 | 0.0384926 | 0.4203 | -0.742561 | -0.737372 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|HIGH\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|HIGH\|SINGLE | 146 | 14 | 0.0958904 | 14 | 0.0101171 | 0.031576 | 1.4771 | -5.34993 | -5.33982 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|LOW\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|ALL | 27 | 4 | 0.148148 | 4 | -0.0485481 | 0.0485481 | -1.3108 | 13.0223 | 12.9737 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|LOW\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|ALL | 54 | 8 | 0.148148 | 8 | -0.0212963 | 0.0339444 | -1.15 | 2.03092 | 2.00963 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|LOW\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|ALL | 133 | 17 | 0.12782 | 17 | -0.0120526 | 0.0689759 | -1.603 | -0.900776 | -0.912829 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|LOW\|ALL | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|ALL | 266 | 28 | 0.105263 | 28 | -0.00311429 | 0.0478414 | -0.8284 | -8.62915 | -8.63227 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.01\|LOW\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|SINGLE | 19 | 2 | 0.105263 | 2 | -0.0344947 | 0.0344947 | -0.6554 | 28.8392 | 28.8047 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.02\|LOW\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|SINGLE | 38 | 5 | 0.131579 | 5 | -0.00881316 | 0.0267868 | -0.3349 | 4.27858 | 4.26977 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.05\|LOW\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|SINGLE | 85 | 10 | 0.117647 | 10 | 0.00137882 | 0.0571882 | 0.1172 | -2.45164 | -2.45026 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | REGRESSION_RMSE\|share=0.10\|LOW\|SINGLE | HOLD_B | HOLD_B\|REGRESSION_RMSE\|LOW\|SINGLE | 163 | 19 | 0.116564 | 19 | 0.0175963 | 0.0495141 | 2.8682 | -9.71673 | -9.69914 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|HIGH\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 27 | 3 | 0.111111 | 3 | 0.0393778 | 0.0839704 | 1.0632 | 54.0119 | 54.0513 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|HIGH\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 54 | 7 | 0.12963 | 7 | 0.0221426 | 0.0667352 | 1.1957 | 26.3621 | 26.3843 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|HIGH\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 133 | 21 | 0.157895 | 21 | 0.00691203 | 0.0614895 | 0.9193 | 4.9104 | 4.91731 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|HIGH\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|ALL | 266 | 42 | 0.157895 | 42 | 0.00250865 | 0.0556598 | 0.6673 | 4.9451 | 4.94761 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|HIGH\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 22 | 2 | 0.0909091 | 2 | 0.0104818 | 0.0652091 | 0.2306 | 34.3821 | 34.3925 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|HIGH\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 37 | 3 | 0.0810811 | 3 | 0.00884865 | 0.0413892 | 0.3274 | 15.3696 | 15.3784 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|HIGH\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 80 | 10 | 0.125 | 10 | 0.023035 | 0.0487975 | 1.8428 | -6.12723 | -6.10419 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|HIGH\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|HIGH\|SINGLE | 156 | 20 | 0.128205 | 20 | -0.00335192 | 0.0399955 | -0.5229 | -0.994101 | -0.997453 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|LOW\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|ALL | 27 | 4 | 0.148148 | 4 | -0.0268 | 0.0268 | -0.7236 | 24.5704 | 24.5436 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|LOW\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|ALL | 54 | 7 | 0.12963 | 7 | -0.0136648 | 0.02435 | -0.7379 | 9.55782 | 9.54416 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|LOW\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|ALL | 133 | 14 | 0.105263 | 14 | -0.00270677 | 0.0195564 | -0.36 | -5.04353 | -5.04623 | False | 3 | 3 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|LOW\|ALL | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|ALL | 266 | 30 | 0.112782 | 30 | 0.00773947 | 0.0315492 | 2.0587 | -6.30035 | -6.29261 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.01\|LOW\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 26 | 3 | 0.115385 | 3 | -0.0216885 | 0.0216885 | -0.5639 | 15.8189 | 15.7973 | False | 1 | 1 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.02\|LOW\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 45 | 5 | 0.111111 | 5 | -0.0093 | 0.0221222 | -0.4185 | 1.39828 | 1.38898 | False | 2 | 2 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.05\|LOW\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 108 | 11 | 0.101852 | 11 | -8.42593e-05 | 0.0208343 | -0.0091 | -13.8995 | -13.8995 | False | 4 | 4 | False |
| gate_direction_r2 | r24_tail | WEIGHTED_MULTICLASS\|share=0.10\|LOW\|SINGLE | HOLD_B | HOLD_B\|WEIGHTED_MULTICLASS\|LOW\|SINGLE | 198 | 23 | 0.116162 | 23 | 0.010703 | 0.0388273 | 2.1192 | -8.56017 | -8.54946 | False | 3 | 3 | False |
| trend_side | 30d | DOWN_BREAKOUT_LONG | DEV | 30d\|DEV | 1392 | 130 | 0.0933908 | 130 | -0.209625 | 0.213572 | -291.798 | 1.9713 | 1.76168 | False | 1 | 1 | False |
| trend_side | 30d | UP_BREAKOUT_SHORT | DEV | 30d\|DEV | 1402 | 118 | 0.0841655 | 118 | 0.0244173 | 0.093008 | 34.233 | -3.31721 | -3.29279 | False | 2 | 2 | False |
| trend_side | 30d | DOWN_BREAKOUT_LONG | HOLD_B | 30d\|HOLD_B | 73 | 7 | 0.0958904 | 7 | -0.0233534 | 0.040263 | -1.7048 | 4.06764 | 4.04429 | False | 1 | 1 | False |
| trend_side | 30d | UP_BREAKOUT_SHORT | HOLD_B | 30d\|HOLD_B | 169 | 24 | 0.142012 | 24 | -0.011568 | 0.0502402 | -1.955 | -12.9536 | -12.9652 | False | 2 | 2 | False |
| trend_side | 7d_report_only | DOWN_BREAKOUT_LONG | DEV | 7d_report_only\|DEV | 1253 | 110 | 0.0877893 | 110 | -0.194505 | 0.199868 | -243.715 | -3.42504 | -3.61955 | False | 1 | 1 | False |
| trend_side | 7d_report_only | UP_BREAKOUT_SHORT | DEV | 7d_report_only\|DEV | 1552 | 145 | 0.0934278 | 145 | 0.0481182 | 0.109819 | 74.6794 | -6.14052 | -6.0924 | False | 2 | 2 | False |
| trend_side | 7d_report_only | DOWN_BREAKOUT_LONG | HOLD_B | 7d_report_only\|HOLD_B | 79 | 12 | 0.151899 | 12 | -0.0112076 | 0.0339494 | -0.8854 | 11.2568 | 11.2456 | False | 1 | 1 | False |
| trend_side | 7d_report_only | UP_BREAKOUT_SHORT | HOLD_B | 7d_report_only\|HOLD_B | 163 | 22 | 0.134969 | 22 | -0.0134411 | 0.0586276 | -2.1909 | -13.4913 | -13.5048 | False | 2 | 2 | False |

## initial_experiment_summary.parquet

행 8 × 열 10

| experiment | table | cells | trade_instances | crossing_instances | crossing_rate_weighted | signed_difference_mean_bps_weighted | absolute_difference_mean_bps_weighted | sign_changed_cells | rank_changed_cells |
|---|---|---|---|---|---|---|---|---|---|
| gate_direction_1 | backtest | 8 | 30358 | 2928 | 0.096449 | -0.033411 | 0.107666 | 1 | 0 |
| gate_direction_r2 | r21_arm | 12 | 40285 | 3403 | 0.0844731 | -0.0427455 | 0.102257 | 0 | 2 |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1672 | 0.0990756 | -0.0161158 | 0.113625 | 0 | 0 |
| gate_direction_r2 | r22_books | 18 | 76219 | 7497 | 0.0983613 | -0.0408005 | 0.121648 | 2 | 0 |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 3573 | 0.096245 | -0.0521265 | 0.118694 | 0 | 0 |
| gate_direction_r2 | r24_tail | 160 | 84696 | 7850 | 0.0926844 | 0.0158491 | 0.135738 | 1 | 0 |
| trend_side | 30d | 4 | 3036 | 279 | 0.0918972 | -0.0860425 | 0.144638 | 0 | 0 |
| trend_side | 7d_report_only | 4 | 3047 | 289 | 0.0948474 | -0.0564857 | 0.142144 | 0 | 0 |

## next_funding_usage.parquet

행 6 × 열 4

| consumer | direct | count | detail |
|---|---|---|---|
| R2-14 G2 before | True | 12 | 12 grid cells call attached.next_funding_rate for direction |
| R2-15 model feature | True | 1197 | fit audits using feature / all fit audits = 1197/2170 |
| R2-15 G2 ctx_signal_strength | True | 1030 | G2 candidate rows; selected G2 rules=1 |
| R2-18 G2 rule candidates | False | 4 | 4 before/pre/post rules call R2-14 _g2_signals |
| generic feature registry | True | 1 | metadata says announced next rate; loader supplies last-settled alias |
| gate-direction dataset | False | 28518 | f_next range=0.0..0.0; selected feature rows=0 |

## rerun_scope.parquet

행 8 × 열 4

| order | scope | action | reason |
|---|---|---|---|
| 1 | funding boundary policy + loader | FIX | sign-aware boundary and one clock |
| 2 | R2-14 | RERUN | PnL, Sharpe, representatives |
| 3 | R2-15 | RERUN | targets, labels, next-rate feature |
| 4 | R2-17 | RERUN | direct R2-14 funding import |
| 5 | R2-18 | RERUN | direct funding and G2 rules |
| 6 | R2-19 | RERUN | candidate list, corrected baseline, floor clock |
| 7 | gate-direction 1/R2/trend-side metrics | REPRICE | models fixed; PnL tables and one sign flip |
| 8 | R2-20/R2-21 | VERIFY ONLY | archive path already used; no R2-14 PnL dependency |

## verdicts.parquet

행 6 × 열 3

| item | verdict | basis |
|---|---|---|
| 1 | PARTIAL | central error holds; 100% is minute-floor/tolerance result, formula exact-match 34.05% |
| 2 | PARTIAL | 6 candidates include >1% changes; family proxy/exact changes=1/1; R2-19 omitted |
| 3 | DISAGREE | direct repricing sign changes=4; memory 0.1156 not reproduced |
| 4 | DISAGREE | boundary rule is sign-dependent; raw-ms and floor differ |
| 5 | DISAGREE | R2-15 fit audits using next feature=1197; G2 pre signal age 7.0-7.5h |
| 6 | PARTIAL | self-critique valid but misses boundary sign, initial sign flip, G2 long selection, duplicate feature |
