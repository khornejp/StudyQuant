# NM-B1-20261010 new-model batch-1

cutoff 2026-10-08 00:00:00+00:00; costs 4 bps rt (8 report-only)

## vt_tsmom: model=vt_tsmom|lookback_set=1d_4|deadband=0.25|target_vol=0.6|offset=2
verdict FAIL_BOOT; eligible True (n_eligible 6); kill []; insufficient []; o5 stress net4 {'DEV': 17274.820539314125, 'TEST': 1516.9085292978052}

| metric | DEV | TEST |
|---|---|---|
| all_net4_bps | 1.693e+04 | 1561 |
| all_net8_bps | 1.679e+04 | 1533 |
| all_gross_bps | 2.155e+04 | 1532 |
| all_funding_bps | -4480 | 57.4 |
| all_trades | 37 | 7 |
| long_net4_bps | 1.291e+04 | 382.4 |
| long_trades | 26 | 2 |
| short_net4_bps | 4014 | 1179 |
| short_trades | 11 | 5 |
| all_win | 0.2973 | 0.5714 |
| mdd_bps | 9219 | 2292 |
| sharpe_daily_ann | 0.4524 | 0.5584 |
| fill_rate | 0.9487 | 1 |
| positive_month_ratio | 0.2609 | 0.25 |
| boot_mean_day_p05 | -3.836 | -11.1 |
| open_positions | 1 | 1 |

## cascade_proxy: model=cascade_proxy|q_ret=0.975|q_oi=0.1|q_range=0.975|vol_mult=3|hold=720|offset=2
verdict KILL; eligible False (n_eligible 0); kill ['DEV-short', 'TEST-long', 'TEST-short']; insufficient []; o5 stress net4 {'DEV': 4553.369741343796, 'TEST': -1676.2820681590288}

| metric | DEV | TEST |
|---|---|---|
| all_net4_bps | 4981 | -1476 |
| all_net8_bps | 2413 | -1796 |
| all_gross_bps | 7553 | -1162 |
| all_funding_bps | -3.641 | 5.393 |
| all_trades | 642 | 80 |
| long_net4_bps | 7708 | -603.3 |
| long_trades | 366 | 46 |
| short_net4_bps | -2726 | -872.9 |
| short_trades | 276 | 34 |
| all_win | 0.514 | 0.4375 |
| mdd_bps | 9476 | 2363 |
| sharpe_daily_ann | 0.2617 | -1.023 |
| fill_rate | 0.9483 | 0.9302 |
| positive_month_ratio | 0.4918 | 0.4 |
| boot_mean_day_p05 | -4.053 | -14.2 |
| open_positions | 0 | 0 |

## crowd_disagreement: model=crowd_disagreement|gap=2.5|top_min=0.5|oi_filter=doi60>=0|hold=240|offset=2
verdict KILL; eligible True (n_eligible 16); kill ['TEST-long', 'TEST-short']; insufficient []; o5 stress net4 {'DEV': 13838.236373889642, 'TEST': -1406.7018394217284}

| metric | DEV | TEST |
|---|---|---|
| all_net4_bps | 1.146e+04 | -1651 |
| all_net8_bps | 5520 | -2371 |
| all_gross_bps | 1.701e+04 | -922.6 |
| all_funding_bps | 385.5 | -8.337 |
| all_trades | 1484 | 180 |
| long_net4_bps | 5337 | -1235 |
| long_trades | 724 | 118 |
| short_net4_bps | 6119 | -415.8 |
| short_trades | 760 | 62 |
| all_win | 0.4811 | 0.4278 |
| mdd_bps | 4887 | 2016 |
| sharpe_daily_ann | 0.835 | -1.931 |
| fill_rate | 0.8244 | 0.786 |
| positive_month_ratio | 0.4528 | 0.5 |
| boot_mean_day_p05 | 0.9403 | -13.12 |
| open_positions | 0 | 0 |

### vt_tsmom top5 by TEST_worst_side_net4

| variant_id                                                            |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:----------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=vt_tsmom|lookback_set=4h_3|deadband=0.5|target_vol=0.4|offset=2 |            20098.4 |               -1995.8 |              2556.0 |                  969.7 |                51 |
| model=vt_tsmom|lookback_set=4h_3|deadband=0.5|target_vol=0.4|offset=5 |            20137.6 |               -1907.2 |              2532.4 |                  915.8 |                51 |
| model=vt_tsmom|lookback_set=4h_4|deadband=0.5|target_vol=0.4|offset=2 |            27186.5 |               -2952.9 |              2450.0 |                  768.0 |                39 |
| model=vt_tsmom|lookback_set=4h_4|deadband=0.5|target_vol=0.4|offset=5 |            26318.9 |               -2692.8 |              2471.3 |                  764.2 |                39 |
| model=vt_tsmom|lookback_set=4h_3|deadband=0.5|target_vol=0.2|offset=2 |            12769.4 |                -696.0 |              1663.6 |                  760.6 |                51 |

### vt_tsmom top5 by DEV_score

| variant_id                                                             |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:-----------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=vt_tsmom|lookback_set=1d_4|deadband=0.25|target_vol=0.6|offset=5 |            17274.8 |                4181.7 |              1516.9 |                  388.5 |                 6 |
| model=vt_tsmom|lookback_set=1d_3|deadband=0.5|target_vol=0.4|offset=5  |            45850.7 |                3552.9 |              1025.8 |                  196.7 |                11 |
| model=vt_tsmom|lookback_set=1d_4|deadband=0.25|target_vol=0.6|offset=2 |            16927.6 |                4014.3 |              1561.1 |                  382.4 |                 7 |
| model=vt_tsmom|lookback_set=1d_3|deadband=0.5|target_vol=0.4|offset=2  |            45628.5 |                3417.1 |              1006.7 |                  187.8 |                11 |
| model=vt_tsmom|lookback_set=1d_3|deadband=0.5|target_vol=0.6|offset=5  |            46159.1 |                3299.1 |               816.4 |                  244.6 |                11 |

### cascade_proxy top5 by TEST_worst_side_net4

| variant_id                                                                           |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:-------------------------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=2|hold=720|offset=5  |            -5536.9 |               -5519.9 |               672.3 |                  200.4 |                94 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=3|hold=720|offset=5  |             -986.6 |               -2857.2 |               535.4 |                  145.3 |                86 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=2|hold=720|offset=2  |            -3721.3 |               -5722.9 |               857.9 |                  134.1 |                98 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=3|hold=720|offset=2  |              202.8 |               -3182.5 |               762.6 |                  111.0 |                90 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.975|vol_mult=2|hold=720|offset=5 |            -1945.5 |               -3820.8 |               440.6 |                  101.0 |                79 |

### cascade_proxy top5 by DEV_score

| variant_id                                                                           |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:-------------------------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=cascade_proxy|q_ret=0.975|q_oi=0.1|q_range=0.975|vol_mult=3|hold=720|offset=5  |             4553.4 |               -2056.2 |             -1676.3 |                -1123.8 |                78 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.1|q_range=0.975|vol_mult=3|hold=720|offset=2  |             4981.3 |               -2726.3 |             -1476.2 |                 -872.9 |                80 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=3|hold=720|offset=5  |             -986.6 |               -2857.2 |               535.4 |                  145.3 |                86 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.95|vol_mult=3|hold=720|offset=2  |              202.8 |               -3182.5 |               762.6 |                  111.0 |                90 |
| model=cascade_proxy|q_ret=0.975|q_oi=0.05|q_range=0.975|vol_mult=3|hold=720|offset=5 |            -1467.5 |               -3226.4 |               191.2 |                  -67.1 |                72 |

### crowd_disagreement top5 by TEST_worst_side_net4

| variant_id                                                                        |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:----------------------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=crowd_disagreement|gap=2.5|top_min=1.0|oi_filter=doi60>=0|hold=60|offset=5  |            -5275.0 |               -3329.6 |             -1069.5 |                 -571.1 |               207 |
| model=crowd_disagreement|gap=2.5|top_min=1.0|oi_filter=doi60>=0|hold=60|offset=2  |            -9173.8 |               -4607.5 |             -1129.0 |                 -729.2 |               253 |
| model=crowd_disagreement|gap=2.5|top_min=0.0|oi_filter=none|hold=240|offset=2     |             6626.2 |                2707.0 |             -1379.2 |                 -735.7 |               319 |
| model=crowd_disagreement|gap=1.5|top_min=1.0|oi_filter=doi60>=0|hold=240|offset=5 |             8747.9 |                3967.4 |              -904.5 |                 -758.0 |               113 |
| model=crowd_disagreement|gap=2.0|top_min=1.0|oi_filter=doi60>=0|hold=240|offset=5 |             9259.1 |                3833.6 |             -1560.1 |                 -783.9 |               111 |

### crowd_disagreement top5 by DEV_score

| variant_id                                                                        |   DEV_all_net4_bps |   DEV_worst_side_net4 |   TEST_all_net4_bps |   TEST_worst_side_net4 |   TEST_all_trades |
|:----------------------------------------------------------------------------------|-------------------:|----------------------:|--------------------:|-----------------------:|------------------:|
| model=crowd_disagreement|gap=2.5|top_min=0.5|oi_filter=doi60>=0|hold=240|offset=5 |            13838.2 |                5349.5 |             -1406.7 |                 -947.7 |               151 |
| model=crowd_disagreement|gap=2.5|top_min=1.0|oi_filter=doi60>=0|hold=240|offset=5 |             9552.1 |                2636.3 |             -1728.7 |                -1235.9 |                98 |
| model=crowd_disagreement|gap=2.5|top_min=0.5|oi_filter=doi60>=0|hold=240|offset=2 |            11455.7 |                5336.9 |             -1651.0 |                -1235.1 |               180 |
| model=crowd_disagreement|gap=2.0|top_min=1.0|oi_filter=doi60>=0|hold=240|offset=5 |             9259.1 |                3833.6 |             -1560.1 |                 -783.9 |               111 |
| model=crowd_disagreement|gap=2.5|top_min=1.0|oi_filter=doi60>=0|hold=240|offset=2 |             8982.0 |                4124.6 |             -1349.8 |                -1182.4 |               119 |
