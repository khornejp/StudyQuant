# R2-22

## (a) module_tests

| test_files | last_line | returncode |
| --- | --- | --- |
| 7 | 53 passed, 5 warnings in 18.61s | 0 |

## funding_module

| settlement_rows | max_normalization_error_seconds | rate_2021_01_08_00 | rate_2021_01_08_08 |
| --- | --- | --- | --- |
| 7119 | 0.04700000 | 0.00213517 | 0.00092044 |

## definition_changes

| item | before | after | rows | max_abs_difference |
| --- | --- | --- | --- | --- |
| settlement_rate_offset_hours | -8 | 0 | 7119 | nan |
| r2_15_g2_funding_feature | next_funding_rate | funding_rate | 3417120 | 0.00000000 |

## (b) experiment_summary

| experiment | boundary | cell_count | row_count | old_net_min_bps | old_net_median_bps | old_net_max_bps | new_net_min_bps | new_net_median_bps | new_net_max_bps | delta_min_bps | delta_q05_bps | delta_q25_bps | delta_median_bps | delta_q75_bps | delta_q95_bps | delta_max_bps | sign_changed_n | sign_changed_row_n | sign_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-14 | PESS | 813 | 1626 | -68699.16562346 | -140.39001034 | 35384.22965313 | -69251.56922493 | -193.19146456 | 34886.26894251 | -2368.11100120 | -720.42772303 | -167.98003580 | -10.91465414 | -1.56942509 | 4.23949229 | 488.27450190 | 15 | 15 | A3\|1d\|168\|trail2\|LS;A3\|1d\|24\|signal\|L;A3\|1h\|168\|trail2\|L;A4\|1h\|10/2\|trail2\|LS;A4\|1h\|10/3\|trail2\|LS;A4\|1h\|10/4\|trail2\|LS;A4\|1h\|10/4\|trail3\|L;A5\|1h\|25\|signal\|LS;A5\|1h\|25\|trail2\|LS;C4\|4h\|engulf/trend4h\|signal\|S;D2\|1d\|NR7\|signal\|S;F1\|1h\|10/24\|signal\|LS;G1\|1m\|us/30\|signal\|LS;G3\|1d\|weekday\|signal\|L;G3\|1d\|weekday\|signal\|LS |
| R2-14 | OPT | 813 | 1626 | -68699.16562346 | -140.39001034 | 35384.22965313 | -68086.28292493 | -119.32488954 | 35725.98504251 | -703.91118656 | -126.81025916 | 0.00000000 | 5.61025004 | 56.17531320 | 624.77059720 | 2249.73551279 | 6 | 6 | B2\|15m\|30/70/12\|signal\|L;F1\|1h\|10/24\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|S;F2\|4h\|--/fade/4\|signal\|L;F2\|4h\|--/fade/4\|signal\|LS |
| R2-17 | PESS | 2682 | 8046 | -207724.77051324 | 1405.30101402 | 45977.44555885 | -209710.37231324 | 1330.94648884 | 45428.31955706 | -5050.61071080 | -1168.99572181 | -431.51383113 | -142.29205152 | -16.85449997 | -0.66042501 | 27.99756237 | 42 | 42 | A3\|1h\|1080\|trail2\|LS;A3\|1h\|360\|trail2\|S;A3\|1h\|360\|trail3\|L;A3\|1h\|480\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F1\|4h\|w90\|q15\|h8\|L;F3_global_ls_account\|15m\|w180\|q10\|median48\|LS;F3_global_ls_account\|15m\|w180\|q15\|median48\|LS;F3_global_ls_account\|15m\|w60\|q15\|h8\|L;F3_global_ls_account\|1h\|w180\|q15\|h4\|LS;F3_global_ls_account\|4h\|w180\|q15\|h4\|S;F3_global_ls_account\|4h\|w180\|q15\|h8\|L;F3_global_ls_account\|4h\|w180\|q15\|h8\|S;F3_global_ls_account\|4h\|w180\|q2.5\|h4\|LS;F3_global_ls_account\|4h\|w180\|q20\|h4\|LS;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h8\|L;F3_global_ls_account\|4h\|w90\|q5\|h4\|S;F3_taker_ls_ratio\|15m\|w30\|q5\|h48\|LS;F3_taker_ls_ratio\|1h\|w180\|q2.5\|h4\|LS;F3_taker_ls_ratio\|1h\|w180\|q5\|h12\|LS;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|1h\|w60\|q20\|h12\|L;F3_taker_ls_ratio\|1h\|w90\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h48\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|median48\|S;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|S;F3_taker_ls_ratio\|4h\|w30\|q5\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q5\|h12\|S;F3_taker_ls_ratio\|4h\|w60\|q5\|h4\|S;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h12\|L;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w90\|q5\|h4\|S |
| R2-17 | OPT | 2682 | 8046 | -207724.77051324 | 1405.30101402 | 45977.44555885 | -205690.88341324 | 1426.18824740 | 46255.11465041 | -1024.18489606 | -268.17237675 | 0.53576347 | 29.22665509 | 316.18731219 | 1222.10485091 | 4767.10878920 | 33 | 34 | A3\|1d\|480\|signal\|S;A3\|1h\|360\|trail3\|L;A3\|4h\|240\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F3_global_ls_account\|15m\|w30\|q15\|median48\|L;F3_global_ls_account\|15m\|w60\|q15\|median48\|L;F3_global_ls_account\|15m\|w90\|q10\|median48\|L;F3_global_ls_account\|1h\|w180\|q20\|h4\|S;F3_global_ls_account\|1h\|w180\|q20\|h8\|S;F3_global_ls_account\|4h\|w30\|q15\|h24\|L;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h24\|L;F3_global_ls_account\|4h\|w60\|q5\|h4\|L;F3_taker_ls_ratio\|15m\|w180\|q15\|h24\|L;F3_taker_ls_ratio\|15m\|w30\|q5\|h24\|LS;F3_taker_ls_ratio\|1h\|w180\|q15\|h48\|L;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w60\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h12\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|h24\|S;F3_taker_ls_ratio\|4h\|w30\|q2.5\|h48\|LS;F3_taker_ls_ratio\|4h\|w30\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w60\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w90\|q10\|h48\|LS;F3_taker_ls_ratio\|4h\|w90\|q2.5\|median48\|S;F3_taker_ls_ratio\|4h\|w90\|q5\|median48\|S |
| R2-18 | PESS | 48 | 960 | -16068.05844630 | 166.00739408 | 27082.24716574 | -16412.55629662 | 134.80101429 | 25870.26505871 | -1211.98210702 | -599.94734062 | -174.94169995 | -30.85734700 | -1.60019997 | 2.04300499 | 52.87729978 | 4 | 6 | R-F3\|tail=5\|direction=LS;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-18 | OPT | 48 | 960 | -16068.05844630 | 166.00739408 | 27082.24716574 | -16390.22679662 | 170.60089632 | 28117.91295871 | -663.62525063 | -322.23291532 | -35.42604997 | 1.49589915 | 35.46069939 | 575.94680837 | 1229.66889743 | 5 | 6 | R-E1\|z=2\|direction=LS;R-F4\|tail=5\|direction=L;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-19 | PESS | 6 | 18 | 1038.65349264 | 11223.60277858 | 35293.52228478 | 1035.80459264 | 11166.54862858 | 34883.27988478 | -410.24240000 | -283.36477000 | -184.56552500 | -59.99985000 | -9.46122500 | -1.89592000 | -1.19790000 | 0 | 0 |  |
| R2-19 | OPT | 6 | 18 | 1038.65349264 | 11223.60277858 | 35293.52228478 | 1039.76309264 | 11264.62197858 | 35723.99598478 | 0.56610000 | 0.56610000 | 8.05800000 | 48.13505000 | 170.71840000 | 299.63643000 | 430.47370000 | 0 | 0 |  |

## r2_14_INCL

| rows | cells | funding_min_bps | funding_median_bps | funding_max_bps | event_count_sum |
| --- | --- | --- | --- | --- | --- |
| 1626 | 813 | -6774.69420000 | 0.00000000 | 7061.99980000 | 2000613 |

## sign_changes

| experiment | boundary | sign_changed_n | sign_changed_cells |
| --- | --- | --- | --- |
| R2-14 | PESS | 15 | A3\|1d\|168\|trail2\|LS;A3\|1d\|24\|signal\|L;A3\|1h\|168\|trail2\|L;A4\|1h\|10/2\|trail2\|LS;A4\|1h\|10/3\|trail2\|LS;A4\|1h\|10/4\|trail2\|LS;A4\|1h\|10/4\|trail3\|L;A5\|1h\|25\|signal\|LS;A5\|1h\|25\|trail2\|LS;C4\|4h\|engulf/trend4h\|signal\|S;D2\|1d\|NR7\|signal\|S;F1\|1h\|10/24\|signal\|LS;G1\|1m\|us/30\|signal\|LS;G3\|1d\|weekday\|signal\|L;G3\|1d\|weekday\|signal\|LS |
| R2-14 | OPT | 6 | B2\|15m\|30/70/12\|signal\|L;F1\|1h\|10/24\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|LS;F2\|4h\|+-/fade/4\|signal\|S;F2\|4h\|--/fade/4\|signal\|L;F2\|4h\|--/fade/4\|signal\|LS |
| R2-17 | PESS | 42 | A3\|1h\|1080\|trail2\|LS;A3\|1h\|360\|trail2\|S;A3\|1h\|360\|trail3\|L;A3\|1h\|480\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F1\|4h\|w90\|q15\|h8\|L;F3_global_ls_account\|15m\|w180\|q10\|median48\|LS;F3_global_ls_account\|15m\|w180\|q15\|median48\|LS;F3_global_ls_account\|15m\|w60\|q15\|h8\|L;F3_global_ls_account\|1h\|w180\|q15\|h4\|LS;F3_global_ls_account\|4h\|w180\|q15\|h4\|S;F3_global_ls_account\|4h\|w180\|q15\|h8\|L;F3_global_ls_account\|4h\|w180\|q15\|h8\|S;F3_global_ls_account\|4h\|w180\|q2.5\|h4\|LS;F3_global_ls_account\|4h\|w180\|q20\|h4\|LS;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h8\|L;F3_global_ls_account\|4h\|w90\|q5\|h4\|S;F3_taker_ls_ratio\|15m\|w30\|q5\|h48\|LS;F3_taker_ls_ratio\|1h\|w180\|q2.5\|h4\|LS;F3_taker_ls_ratio\|1h\|w180\|q5\|h12\|LS;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|1h\|w60\|q20\|h12\|L;F3_taker_ls_ratio\|1h\|w90\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h48\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|median48\|S;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w30\|q20\|h8\|S;F3_taker_ls_ratio\|4h\|w30\|q5\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q5\|h12\|S;F3_taker_ls_ratio\|4h\|w60\|q5\|h4\|S;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h12\|L;F3_taker_ls_ratio\|4h\|w90\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w90\|q5\|h4\|S |
| R2-17 | OPT | 33 | A3\|1d\|480\|signal\|S;A3\|1h\|360\|trail3\|L;A3\|4h\|240\|trail2\|LS;F1\|1h\|w30\|q20\|h8\|S;F1\|1h\|w90\|q10\|h24\|LS;F1\|1h\|w90\|q15\|h8\|LS;F1\|4h\|w60\|q20\|h48\|S;F1\|4h\|w60\|q20\|h8\|S;F1\|4h\|w60\|q5\|h24\|S;F3_global_ls_account\|15m\|w30\|q15\|median48\|L;F3_global_ls_account\|15m\|w60\|q15\|median48\|L;F3_global_ls_account\|15m\|w90\|q10\|median48\|L;F3_global_ls_account\|1h\|w180\|q20\|h4\|S;F3_global_ls_account\|1h\|w180\|q20\|h8\|S;F3_global_ls_account\|4h\|w30\|q15\|h24\|L;F3_global_ls_account\|4h\|w30\|q15\|h4\|S;F3_global_ls_account\|4h\|w60\|q5\|h24\|L;F3_global_ls_account\|4h\|w60\|q5\|h4\|L;F3_taker_ls_ratio\|15m\|w180\|q15\|h24\|L;F3_taker_ls_ratio\|15m\|w30\|q5\|h24\|LS;F3_taker_ls_ratio\|1h\|w180\|q15\|h48\|L;F3_taker_ls_ratio\|1h\|w30\|q2.5\|h48\|S;F3_taker_ls_ratio\|1h\|w60\|q5\|h12\|LS;F3_taker_ls_ratio\|4h\|w180\|q20\|h12\|L;F3_taker_ls_ratio\|4h\|w180\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w180\|q5\|h24\|S;F3_taker_ls_ratio\|4h\|w30\|q2.5\|h48\|LS;F3_taker_ls_ratio\|4h\|w30\|q20\|median48\|L;F3_taker_ls_ratio\|4h\|w60\|q2.5\|h24\|LS;F3_taker_ls_ratio\|4h\|w60\|q20\|h8\|L;F3_taker_ls_ratio\|4h\|w90\|q10\|h48\|LS;F3_taker_ls_ratio\|4h\|w90\|q2.5\|median48\|S;F3_taker_ls_ratio\|4h\|w90\|q5\|median48\|S |
| R2-18 | PESS | 4 | R-F3\|tail=5\|direction=LS;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-18 | OPT | 5 | R-E1\|z=2\|direction=LS;R-F4\|tail=5\|direction=L;R-G2\|pre=30\|post=30\|direction=S;R-G2\|pre=30\|post=60\|direction=S;R-G2\|pre=60\|post=30\|direction=L |
| R2-19 | PESS | 0 |  |
| R2-19 | OPT | 0 |  |

## selection_changes

| experiment | selection | old | pess | opt | old_pess_changed | old_opt_changed | boundary_equal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R2-14 | A1 | A1\|4h\|50/200\|trail2\|L | A1\|4h\|50/200\|trail2\|L | A1\|4h\|50/200\|trail2\|L | 0 | 0 | 1 |
| R2-14 | A2 | A2\|4h\|55/10\|signal\|L | A2\|4h\|55/10\|signal\|L | A2\|4h\|55/10\|signal\|L | 0 | 0 | 1 |
| R2-14 | A3 | A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | A3\|4h\|720\|signal\|LS | 0 | 0 | 1 |
| R2-14 | A4 | A4\|4h\|10/3\|signal\|L | A4\|4h\|10/3\|signal\|L | A4\|4h\|10/3\|signal\|L | 0 | 0 | 1 |
| R2-14 | A5 | A5\|4h\|25\|trail2\|L | A5\|4h\|25\|trail2\|L | A5\|4h\|25\|trail2\|L | 0 | 0 | 1 |
| R2-14 | A6 | A6\|1h\|40/60\|signal\|L | A6\|1h\|40/60\|signal\|L | A6\|1h\|40/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | B1 | B1\|15m\|2.5/12\|signal\|L | B1\|15m\|2.5/12\|signal\|L | B1\|15m\|2.5/12\|signal\|L | 0 | 0 | 1 |
| R2-14 | B2 | B2\|1h\|20/80/4\|signal\|L | B2\|1h\|20/80/4\|signal\|L | B2\|1h\|20/80/4\|signal\|L | 0 | 0 | 1 |
| R2-14 | B3 | B3\|1h\|3\|signal\|L | B3\|1h\|3\|signal\|L | B3\|1h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | B4 | B4\|1h\|20/5\|signal\|L | B4\|1h\|20/5\|signal\|L | B4\|1h\|20/5\|signal\|L | 0 | 0 | 1 |
| R2-14 | C1 | C1\|1h\|20/12\|limit\|L | C1\|1h\|20/12\|limit\|L | C1\|1h\|20/12\|limit\|L | 0 | 0 | 1 |
| R2-14 | C2 | C2\|4h\|20\|signal\|L | C2\|4h\|20\|signal\|L | C2\|4h\|20\|signal\|L | 0 | 0 | 1 |
| R2-14 | C3 | C3\|4h\|inside\|signal\|L | C3\|4h\|inside\|signal\|L | C3\|4h\|inside\|signal\|L | 0 | 0 | 1 |
| R2-14 | C4 | C4\|4h\|pin/trend4h\|signal\|S | C4\|4h\|pin/trend4h\|signal\|S | C4\|4h\|pin/trend4h\|signal\|S | 0 | 0 | 1 |
| R2-14 | C5 | C5\|4h\|3\|signal\|L | C5\|4h\|3\|signal\|L | C5\|4h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | D1 | D1\|1h\|20\|signal\|L | D1\|4h\|20\|signal\|S | D1\|1h\|20\|signal\|L | 1 | 0 | 0 |
| R2-14 | D2 | D2\|4h\|NR4\|signal\|L | D2\|4h\|NR4\|signal\|L | D2\|4h\|NR4\|signal\|L | 0 | 0 | 1 |
| R2-14 | E1 | E1\|1h\|3\|signal\|L | E1\|1h\|3\|signal\|L | E1\|1h\|3\|signal\|L | 0 | 0 | 1 |
| R2-14 | E2 | E2\|1h\|4h/follow/5\|signal\|L | E2\|1h\|4h/follow/5\|signal\|L | E2\|1h\|4h/follow/5\|signal\|L | 0 | 0 | 1 |
| R2-14 | E3 | E3\|1h\|revert\|signal\|L | E3\|1h\|revert\|signal\|L | E3\|1h\|revert\|signal\|L | 0 | 0 | 1 |
| R2-14 | F1 | F1\|1h\|5/24\|signal\|LS | F1\|1h\|5/24\|signal\|LS | F1\|1h\|5/24\|signal\|LS | 0 | 0 | 1 |
| R2-14 | F2 | F2\|4h\|--/fade/24\|signal\|L | F2\|4h\|--/fade/24\|signal\|L | F2\|4h\|--/fade/24\|signal\|L | 0 | 0 | 1 |
| R2-14 | F3 | F3\|1h\|10/24\|signal\|LS | F3\|1h\|10/24\|signal\|LS | F3\|1h\|10/24\|signal\|LS | 0 | 0 | 1 |
| R2-14 | F4 | F4\|1h\|5/4\|signal\|L | F4\|1h\|5/4\|signal\|L | F4\|1h\|5/4\|signal\|L | 0 | 0 | 1 |
| R2-14 | G1 | G1\|1m\|us/60\|signal\|L | G1\|1m\|us/60\|signal\|L | G1\|1m\|us/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | G2 | G2\|1m\|before/60/60\|signal\|L | G2\|1m\|before/60/60\|signal\|L | G2\|1m\|before/60/60\|signal\|L | 0 | 0 | 1 |
| R2-14 | G3 | G3\|1d\|1\|signal\|L | G3\|1d\|1\|signal\|L | G3\|1d\|1\|signal\|L | 0 | 0 | 1 |
| R2-14 | H1 | H1\|4h\|55/20/squeeze10\|signal\|L | H1\|4h\|55/20/squeeze10\|signal\|L | H1\|4h\|55/20/squeeze10\|signal\|L | 0 | 0 | 1 |
| R2-14 | H2 | H2\|1h\|40/60/funding5\|signal\|L | H2\|1h\|40/60/funding5\|signal\|L | H2\|1h\|40/60/funding5\|signal\|L | 0 | 0 | 1 |
| R2-14 | H3 | H3\|1h\|4h20/60/C2\|signal\|S | H3\|1h\|4h20/60/C2\|signal\|S | H3\|1h\|4h20/60/C2\|signal\|S | 0 | 0 | 1 |
| R2-15 | T | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | A1\|4h\|50/200\|trail2\|L;A2\|4h\|55/10\|signal\|L;A3\|4h\|720\|signal\|LS;A4\|4h\|10/3\|signal\|L;A5\|4h\|25\|trail2\|L;A6\|1h\|40/60\|signal\|L | 0 | 0 | 1 |
| R2-15 | G | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/4\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/4\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | B1\|15m\|2.5/4\|signal\|L;B2\|15m\|30/70/12\|signal\|L;C1\|1h\|20/12\|limit\|L;C2\|15m\|20\|signal\|L;C3\|4h\|inside\|signal\|LS;C4\|4h\|pin/trend4h\|signal\|S;E1\|1h\|3\|signal\|L;E2\|1h\|4h/follow/5\|signal\|L;F1\|1h\|5/24\|signal\|LS;F2\|4h\|-+/fade/4\|signal\|L;F3\|1h\|10/24\|signal\|LS;F4\|1h\|5/4\|signal\|L;G1\|1m\|us/60\|signal\|L;G2\|1m\|before/60/60\|signal\|L | 0 | 1 | 0 |
| R2-18 | long | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | R-TAIL\|q=0.01\|method=EXPANDING_OOS\|direction=L | 0 | 0 | 1 |
| R2-18 | short | R-F3\|tail=10\|direction=S | R-F3\|tail=10\|direction=S | R-F3\|tail=10\|direction=S | 0 | 0 | 1 |
| R2-19 | frozen_candidates | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | E1\|1h\|3\|signal\|L;E1\|1h\|2\|signal\|L;F3\|1h\|10/24\|signal\|LS;F3\|1h\|5/24\|signal\|LS;A3\|4h\|720\|signal\|LS;F4\|1h\|5/4\|signal\|L;BUY_HOLD | 0 | 0 | 1 |

## hypothesis

| experiment | variant | PESS | OPT | status |
| --- | --- | --- | --- | --- |
| R2-14 | primary | 0 | 0 | 확정 |
| R2-17 | primary | 1 | 1 | 확정 |
| R2-18 | primary | 0 | 1 | 경계 의존 |
| R2-19 | primary | 0 | 0 | 확정 |
| R2-15 | full_primary | 1 | 1 | 확정 |
| R2-15 | full_trend | 0 | 0 | 확정 |
| R2-15 | no_next_primary | 1 | 1 | 확정 |
| R2-15 | no_next_trend | 0 | 1 | 경계 의존 |

## (c) r2_15_full_no_next

| rows | full_feature_count | no_next_feature_count | net_difference_min_bps | net_difference_median_bps | net_difference_max_bps | sharpe_difference_min | sharpe_difference_median | sharpe_difference_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240 | 216 | 215 | -8666.20920937 | 0.00000000 | 6207.13775074 | -3.12903310 | 0.00000000 | 2.73373923 |

## r2_15_variants

| boundary | variant | feature_count | hypothesis_pass | trend_hypothesis_pass | passing_cells |
| --- | --- | --- | --- | --- | --- |
| PESS | full | 216 | 1 | 0 | 12 |
| OPT | full | 216 | 1 | 0 | 11 |
| PESS | no_next | 215 | 1 | 0 | 13 |
| OPT | no_next | 215 | 1 | 1 | 12 |

## r2_15_target_label_audit

| pess_targets | opt_targets | target_sets_equal | pess_candidates | opt_candidates | candidate_sets_equal | label_changed_n | labels_equal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 20 | 0 | 25729 | 24422 | 0 | 24 | 0 |

## (d) early_reprice

| experiment | table | cells | trade_instances | crossing_instances | crossing_rate_weighted | signed_difference_mean_bps_weighted | absolute_difference_mean_bps_weighted | sign_changed_cells | rank_changed_cells | boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | 8 | 30358 | 3234 | 0.10652876 | -0.07611311 | 0.12392715 | 1 | 0 | PESS |
| gate_direction_r2 | r21_arm | 12 | 40285 | 3866 | 0.09596624 | -0.08655660 | 0.11701346 | 0 | 2 | PESS |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1773 | 0.10506044 | -0.05487579 | 0.11852717 | 0 | 0 | PESS |
| gate_direction_r2 | r22_books | 18 | 76219 | 8396 | 0.11015626 | -0.08936598 | 0.13981746 | 2 | 0 | PESS |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 4053 | 0.10917466 | -0.09551233 | 0.13835139 | 0 | 0 | PESS |
| gate_direction_r2 | r24_tail | 160 | 84696 | 7774 | 0.09178710 | -0.04446242 | 0.13268834 | 1 | 0 | PESS |
| trend_side | 30d | 4 | 3036 | 280 | 0.09222661 | -0.09121943 | 0.14839572 | 0 | 0 | PESS |
| trend_side | 7d_report_only | 4 | 3047 | 287 | 0.09419101 | -0.06214506 | 0.14507653 | 0 | 0 | PESS |
| trend_side_tp | tp_grid | 9 | 16764 | 1210 | 0.07217848 | -0.06643505 | 0.11253856 | 0 | 9 | PESS |
| gate_direction_1 | backtest | 8 | 30358 | 2622 | 0.08636933 | 0.00722946 | 0.09034534 | 0 | 0 | OPT |
| gate_direction_r2 | r21_arm | 12 | 40285 | 2916 | 0.07238426 | -0.00028115 | 0.08658399 | 0 | 2 | OPT |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1563 | 0.09261673 | 0.02585233 | 0.10271297 | 0 | 0 | OPT |
| gate_direction_r2 | r22_books | 18 | 76219 | 6625 | 0.08692058 | 0.00253540 | 0.10197935 | 0 | 0 | OPT |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 3214 | 0.08657472 | -0.00602671 | 0.09780968 | 0 | 0 | OPT |
| gate_direction_r2 | r24_tail | 160 | 84696 | 8117 | 0.09583688 | 0.05812121 | 0.14166181 | 1 | 0 | OPT |
| trend_side | 30d | 4 | 3036 | 276 | 0.09090909 | -0.08132790 | 0.14008172 | 0 | 0 | OPT |
| trend_side | 7d_report_only | 4 | 3047 | 288 | 0.09451920 | -0.05147457 | 0.13796862 | 0 | 0 | OPT |
| trend_side_tp | tp_grid | 9 | 16764 | 1178 | 0.07026963 | -0.05427707 | 0.10102651 | 0 | 9 | OPT |

## early_sign_changes

| experiment | table | cell_id | segment | old_net_mean_bps | new_net_mean_bps_pess | new_net_mean_bps_opt |
| --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | margin=0.05 | HOLD_B | 0.00567648 | -0.01765331 | 0.00748258 |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|ALL | DEV | 0.05195392 | -0.08276155 | 0.04144620 |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|CAP3 | DEV | 0.05195392 | -0.08276155 | 0.04144620 |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|SINGLE | DEV | 0.01412412 | -0.11443857 | -0.01665205 |

## (e) r2_20_r2_21

| experiment | rows | pess_difference_min_bps | pess_difference_median_bps | pess_difference_max_bps | opt_difference_min_bps | opt_difference_median_bps | opt_difference_max_bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R2-20 | 219 | -483.39060000 | -7.96840000 | 237.45110000 | -34.86930000 | 1.15590000 | 882.95240000 |
| R2-21 | 144 | -1341.88870000 | -66.83360000 | -4.64500000 | 4.26520000 | 66.73850000 | 1264.27420000 |

## input_sha

| experiment | rows | matches |
| --- | --- | --- |
| R2-20 | 12 | 11 |
| R2-21 | 7 | 7 |

## input_sha_mismatch

| experiment | path | exists | recorded_sha256 | current_sha256 | sha_match |
| --- | --- | --- | --- | --- | --- |
| R2-20 | D:/StudyQuant/out/run_k45_classic_rules_r2_14.py | 1 | 39f3ebe3491e477a074c81304aec4deadd291d2b33ac8f75639fe71cd4d62eed | 49234a16fe1db525de5b6149379984932d3a8d40b12fd8617a507372885770dc | 0 |

## funding_paths

| experiment | funding_path | loader | clock | manifest_has_funding_input |
| --- | --- | --- | --- | --- |
| R2-20 | artifacts/funding_2020_2026h1 | r212.r26.funding_events/load_funding_dir | raw_ms | 0 |
| R2-21 | artifacts/funding_2020_2026h1 | load_funding_dir | raw_ms | 0 |

## (f) status

| status | items |
| --- | --- |
| 확정 | R2-17;R2-19 |
| 경계 의존 | MULTICLASS_0.20\|ALL;MULTICLASS_0.20\|CAP3;R2-14;R2-15;R2-18;margin=0.05 |

## stage_durations_seconds

| stage | elapsed_seconds |
| --- | --- |
| early_reprice | 5.17298260 |
| r2_14_OPT | 1406.50012500 |
| r2_14_PESS | 1411.48191700 |
| r2_15_audit | 48.80800000 |
| r2_15_full | 4456.30127000 |
| r2_15_no_next | 4435.10992000 |
| r2_15_OPT_full | 4455.22106100 |
| r2_15_OPT_no_next | 4387.08586000 |
| r2_17_OPT | 2236.22800700 |
| r2_17_PESS | 2233.43185400 |
| r2_18_OPT | 330.51209260 |
| r2_18_PESS | 330.80567610 |
| r2_19_OPT | 96.14471720 |
| r2_19_PESS | 96.14511200 |
| r2_20_21_verify | 7.90915450 |

## elapsed_seconds

20.02157730
