# NM-B2-20261010T065219Z-97244bea new-model batch-2

parent NM-B1-20261010; cutoff 2026-10-08 00:00:00+00:00; costs maker 4 bps rt (8 report-only); runtime 172.2s

## V DEV_PICK: family=V|blend=slow|db=0.5|tv=0.2|gate=0.0|sizing=conviction|offset=2
eligible False (n_eligible 0); verdict KILL; DEV score -0.06067; adaptive score 0.1777
boot p05 mean/day TEST 20/60/120 ['-0.4547', '-0.2194', '-0.1334']; DEV-FULL ['-0.05227', '0.159', '0.2653']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | 1726 | 902 | 824 | 261 |
| net8 | 1665 | 867 | 798 | 248 |
| gross | 2107 | 1182 | 924 | 275 |
| funding | -319 | -245 | -74 | -1.698 |
| closed | 399 | 224 | 175 | 82 |
| long_net4 | 1430 | 561 | 869 | 211 |
| long_closed | 257 | 108 | 149 | 27 |
| short_net4 | 296 | 341 | -44 | 50 |
| short_closed | 142 | 116 | 26 | 55 |
| open_n | 0 | 1 | 0 | 0 |
| open_mtm | 0 | 4.651 | 0 | 0 |
| win | 0.2707 | 0.2812 | 0.2571 | 0.3049 |
| mdd_1m | 1336 | 1336 | 327 | 138 |
| sharpe | 0.5705 | 0.3915 | 1.307 | 1.194 |
| fill_notional_rate | 0.9399 | 0.9287 | 0.9554 | 0.9529 |
| pos_month_ratio | 0.541 | 0.4865 | 0.625 | 0.4 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL 1726/1430/296; DEV-A 902/561/341; DEV-B 824/869/-44; TEST 261/211/50
- o2_p1.0: DEV-FULL 1694/1429/266; DEV-A 899/560/339; DEV-B 796/869/-73; TEST 259/210/49
- o2_p2.0: DEV-FULL 1662/1403/259; DEV-A 868/534/334; DEV-B 794/869/-75; TEST 242/200/42
- o5_p0.5: DEV-FULL 1715/1413/302; DEV-A 881/540/341; DEV-B 834/873/-40; TEST 267/212/55
- o5_p1.0: DEV-FULL 1683/1412/271; DEV-A 878/539/340; DEV-B 805/874/-69; TEST 266/212/54
- o5_p2.0: DEV-FULL 1635/1419/215; DEV-A 833/547/286; DEV-B 802/873/-70; TEST 259/203/56

### V top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=V|blend=fast|db=0.5|tv=0.2|gate=0.0|sizing=binary|offset=2 | False | -0.7528 | 3891 | -550 | 1079 | 430 | 134 | 124 |
| family=V|blend=fast|db=0.5|tv=0.2|gate=-0.25|sizing=binary|offset=2 | False | -0.1085 | 4530 | -79 | 1031 | 430 | 134 | 117 |
| family=V|blend=slow|db=0.5|tv=0.2|gate=-0.25|sizing=binary|offset=2 | False | -0.7292 | 5706 | -533 | 1380 | 403 | 27 | 55 |
| family=V|blend=slow|db=0.5|tv=0.2|gate=0.0|sizing=binary|offset=2 | False | -1.119 | 5308 | -818 | 1380 | 403 | 27 | 55 |
| family=V|blend=slow|db=0.5|tv=0.4|gate=-0.25|sizing=binary|offset=2 | False | -1.458 | 10323 | -1066 | 1609 | 392 | 27 | 55 |

## E DEV_PICK: family=E|zthr=2.0|hold=30|offset=2
eligible False (n_eligible 0); verdict LOW_N+KILL; DEV score -1.814; adaptive score -0.08103
boot p05 mean/day TEST 20/60/120 ['-0.3494', '-0.2934', '-0.2553']; DEV-FULL ['-4.029', '-4.052', '-4.013']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | -4258 | -2873 | -1385 | 356 |
| net8 | -7142 | -4705 | -2437 | 196 |
| gross | -1374 | -1041 | -333 | 516 |
| funding | 0 | 0 | 0 | 0 |
| closed | 721 | 458 | 263 | 40 |
| long_net4 | -1360 | -222 | -1138 | 379 |
| long_closed | 455 | 286 | 169 | 37 |
| short_net4 | -2898 | -2651 | -247 | -23 |
| short_closed | 266 | 172 | 94 | 3 |
| open_n | 0 | 0 | 0 | 0 |
| open_mtm | 0 | 0 | 0 | 0 |
| win | 0.4494 | 0.441 | 0.4639 | 0.525 |
| mdd_1m | 4435 | 3975 | 1591 | 161 |
| sharpe | -0.7272 | -0.6336 | -1.293 | 1.724 |
| fill_notional_rate | 0.8901 | 0.9051 | 0.8651 | 0.8511 |
| pos_month_ratio | 0.4464 | 0.4722 | 0.4 | 0.3333 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL -4258/-1360/-2898; DEV-A -2873/-222/-2651; DEV-B -1385/-1138/-247; TEST 356/379/-23
- o2_p1.0: DEV-FULL -4479/-1298/-3182; DEV-A -2875/-210/-2665; DEV-B -1605/-1088/-517; TEST 369/391/-23
- o2_p2.0: DEV-FULL -5824/-2281/-3542; DEV-A -3481/-675/-2806; DEV-B -2343/-1606/-736; TEST 535/510/25
- o5_p0.5: DEV-FULL -3417/-691/-2726; DEV-A -2095/271/-2366; DEV-B -1322/-962/-360; TEST 552/560/-8.182
- o5_p1.0: DEV-FULL -3599/-836/-2763; DEV-A -2194/108/-2302; DEV-B -1405/-945/-461; TEST 539/554/-15
- o5_p2.0: DEV-FULL -3517/-665/-2852; DEV-A -1986/362/-2348; DEV-B -1531/-1026/-505; TEST 365/451/-86

### E top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=E|zthr=2.5|hold=30|offset=2 | False | -1.969 | -5026 | -864 | 250 | 0 | 18 | 0 |
| family=E|zthr=2.5|hold=120|offset=2 | False | -3.174 | -5008 | -692 | 475 | 0 | 18 | 0 |
| family=E|zthr=2.0|hold=30|offset=2 | False | -1.814 | -4258 | -1138 | 356 | -23 | 37 | 3 |
| family=E|zthr=2.0|hold=120|offset=2 | False | -2.144 | -3209 | -1567 | 457 | -32 | 37 | 3 |
| family=E|zthr=1.5|hold=30|offset=2 | False | -2.543 | -5652 | -1859 | -153 | -128 | 83 | 34 |

## F DEV_PICK: family=F|qI=0.9|qOI=0.8|resp=0.0|hold=60|offset=2
eligible False (n_eligible 0); verdict KILL; DEV score -0.4115; adaptive score -0.348
boot p05 mean/day TEST 20/60/120 ['-1.258', '-1.168', '-1.062']; DEV-FULL ['-0.4599', '-0.4813', '-0.4834']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | -267 | 59 | -326 | -147 |
| net8 | -627 | -81 | -546 | -267 |
| gross | 95 | 200 | -104 | -27 |
| funding | -2.723 | -0.657 | -2.066 | -0.3093 |
| closed | 90 | 35 | 55 | 30 |
| long_net4 | 141 | 166 | -26 | -84 |
| long_closed | 58 | 18 | 40 | 18 |
| short_net4 | -408 | -107 | -301 | -63 |
| short_closed | 32 | 17 | 15 | 12 |
| open_n | 0 | 0 | 0 | 0 |
| open_mtm | 0 | 0 | 0 | 0 |
| win | 0.4111 | 0.5429 | 0.3273 | 0.3333 |
| mdd_1m | 515 | 315 | 496 | 207 |
| sharpe | -0.3631 | 0.184 | -0.8479 | -1.12 |
| fill_notional_rate | 0.7087 | 0.7 | 0.7143 | 0.6818 |
| pos_month_ratio | 0.4595 | 0.5 | 0.4118 | 0.2222 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL -267/141/-408; DEV-A 59/166/-107; DEV-B -326/-26/-301; TEST -147/-84/-63
- o2_p1.0: DEV-FULL -229/170/-400; DEV-A 26/129/-102; DEV-B -256/42/-297; TEST -163/-101/-63
- o2_p2.0: DEV-FULL -1138/-496/-642; DEV-A -386/-214/-172; DEV-B -753/-283/-470; TEST -174/-127/-47
- o5_p0.5: DEV-FULL -291/98/-389; DEV-A 86/167/-82; DEV-B -377/-69/-308; TEST -154/-97/-57
- o5_p1.0: DEV-FULL -279/34/-312; DEV-A 169/169/0.1646; DEV-B -448/-135/-313; TEST -151/-104/-47
- o5_p2.0: DEV-FULL -723/-292/-431; DEV-A -255/-192/-63; DEV-B -467/-99/-368; TEST 4.9/-30/35

### F top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=F|qI=0.9|qOI=0.8|resp=0.25|hold=720|offset=2 | False | -1.651 | -2596 | -1207 | 1228 | 455 | 32 | 24 |
| family=F|qI=0.8|qOI=0.8|resp=0.0|hold=720|offset=2 | False | -1.474 | -1770 | -1078 | 1586 | 288 | 32 | 34 |
| family=F|qI=0.8|qOI=0.6|resp=0.0|hold=720|offset=2 | False | -2.628 | -7887 | -1729 | 1236 | 201 | 57 | 55 |
| family=F|qI=0.9|qOI=0.6|resp=0.25|hold=720|offset=2 | False | -1.821 | -4198 | -1331 | 1064 | 119 | 42 | 40 |
| family=F|qI=0.8|qOI=0.8|resp=0.0|hold=240|offset=2 | False | -2.324 | -3563 | -1699 | 493 | -57 | 38 | 37 |

## G DEV_PICK: family=G|svi_w=42|g=0.1|trend=(42, 168, 504)|db=0.5|tv=0.2|offset=2
eligible False (n_eligible 0); verdict KILL; DEV score -0.9422; adaptive score 3.84
boot p05 mean/day TEST 20/60/120 ['2.073', '4.124', '5.257']; DEV-FULL ['0.4459', '0.7476', '1.069']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | 7681 | 6949 | 731 | 3038 |
| net8 | 7065 | 6597 | 468 | 2949 |
| gross | 9544 | 8265 | 1278 | 3136 |
| funding | -1247 | -964 | -283 | -8.778 |
| closed | 371 | 227 | 144 | 42 |
| long_net4 | 8340 | 6920 | 1420 | 1075 |
| long_closed | 207 | 118 | 89 | 13 |
| short_net4 | -659 | 30 | -689 | 1963 |
| short_closed | 164 | 109 | 55 | 29 |
| open_n | 0 | 0 | 0 | 0 |
| open_mtm | 0 | 0 | 0 | 0 |
| win | 0.3369 | 0.348 | 0.3194 | 0.3571 |
| mdd_1m | 1843 | 1599 | 1843 | 1070 |
| sharpe | 0.7396 | 0.9889 | 0.218 | 1.954 |
| fill_notional_rate | 0.9372 | 0.9192 | 0.9623 | 0.9265 |
| pos_month_ratio | 0.4493 | 0.4667 | 0.4167 | 0.5556 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL 7681/8340/-659; DEV-A 6949/6920/30; DEV-B 731/1420/-689; TEST 3038/1075/1963
- o2_p1.0: DEV-FULL 7767/8417/-650; DEV-A 6872/6837/35; DEV-B 895/1580/-685; TEST 2981/1044/1937
- o2_p2.0: DEV-FULL 7431/8355/-924; DEV-A 6668/6855/-187; DEV-B 764/1500/-736; TEST 2986/1027/1959
- o5_p0.5: DEV-FULL 7671/8255/-584; DEV-A 6879/6805/74; DEV-B 791/1450/-658; TEST 3078/1084/1994
- o5_p1.0: DEV-FULL 7703/8325/-622; DEV-A 6835/6796/39; DEV-B 868/1529/-661; TEST 3136/1084/2051
- o5_p2.0: DEV-FULL 7284/8128/-843; DEV-A 6597/6806/-210; DEV-B 688/1321/-633; TEST 3097/1093/2004

### G top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=G|svi_w=180|g=0.1|trend=(42, 168, 504)|db=0.5|tv=0.4|offset=2 | False | -3.088 | 20068 | -2257 | 4395 | 1671 | 14 | 16 |
| family=G|svi_w=180|g=0.1|trend=(42, 168, 504)|db=0.25|tv=0.4|offset=2 | False | -5.117 | 18684 | -3741 | 3735 | 1430 | 8 | 16 |
| family=G|svi_w=42|g=0.1|trend=(6, 18, 42)|db=0.5|tv=0.4|offset=2 | False | -3.012 | 5128 | -2202 | 2894 | 1359 | 51 | 58 |
| family=G|svi_w=180|g=0.1|trend=(42, 168, 504)|db=0.25|tv=0.2|offset=2 | False | -2.686 | 11898 | -1963 | 2879 | 1358 | 8 | 16 |
| family=G|svi_w=42|g=0.1|trend=(42, 168, 504)|db=0.5|tv=0.4|offset=2 | False | -1.98 | 10270 | -1448 | 4210 | 1309 | 13 | 29 |

## H DEV_PICK: family=H|h=2|lam=10.0|q=0.9|offset=2
eligible False (n_eligible 0); verdict LOW_N+KILL; DEV score 0.07413; adaptive score 0
boot p05 mean/day TEST 20/60/120 ['0', '0', '0']; DEV-FULL ['0.0921', '0.003175', '-0.03811']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | 1788 | 1629 | 159 | 0 |
| net8 | 1688 | 1553 | 135 | 0 |
| gross | 1830 | 1641 | 189 | 0 |
| funding | 58 | 64 | -6.534 | 0 |
| closed | 25 | 19 | 6 | 0 |
| long_net4 | 314 | 209 | 105 | 0 |
| long_closed | 8 | 3 | 5 | 0 |
| short_net4 | 1474 | 1420 | 54 | 0 |
| short_closed | 17 | 16 | 1 | 0 |
| open_n | 0 | 0 | 0 | 0 |
| open_mtm | 0 | 0 | 0 | 0 |
| win | 0.64 | 0.6316 | 0.6667 | nan |
| mdd_1m | 729 | 729 | 406 | 0 |
| sharpe | 0.7694 | 0.9434 | 0.3842 | nan |
| fill_notional_rate | 0.9615 | 0.95 | 1 | nan |
| pos_month_ratio | 0.7143 | 0.75 | 0.6667 | nan |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL 1788/314/1474; DEV-A 1629/209/1420; DEV-B 159/105/54; TEST 0/0/0
- o2_p1.0: DEV-FULL 1788/314/1474; DEV-A 1629/209/1420; DEV-B 159/105/54; TEST 0/0/0
- o2_p2.0: DEV-FULL 1767/250/1517; DEV-A 1601/146/1454; DEV-B 166/104/63; TEST 0/0/0
- o5_p0.5: DEV-FULL 1689/289/1401; DEV-A 1494/149/1344; DEV-B 196/139/56; TEST 0/0/0
- o5_p1.0: DEV-FULL 1707/307/1401; DEV-A 1494/149/1344; DEV-B 214/157/56; TEST 0/0/0
- o5_p2.0: DEV-FULL 1098/68/1029; DEV-A 1179/149/1029; DEV-B -81/-81/0; TEST 0/0/0

### H top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=H|h=2|lam=0.1|q=0.8|offset=2 | False | -0.02607 | 3872 | -19 | 0 | 0 | 0 | 0 |
| family=H|h=2|lam=0.1|q=0.9|offset=2 | False | 0.07413 | 1759 | 54 | 0 | 0 | 0 | 0 |
| family=H|h=18|lam=10.0|q=0.8|offset=2 | False | -1.188 | 897 | 626 | 1204 | 0 | 1 | 0 |
| family=H|h=18|lam=1.0|q=0.9|offset=2 | False | -0.262 | 1840 | 0 | 0 | 0 | 0 | 0 |
| family=H|h=18|lam=1.0|q=0.8|offset=2 | False | -0.7998 | 1268 | 570 | 1204 | 0 | 1 | 0 |

## I DEV_PICK: family=I|weeks=104|tail=0.1|hold=480|offset=2
eligible False (n_eligible 0); verdict KILL; DEV score -4.585; adaptive score -13
boot p05 mean/day TEST 20/60/120 ['-22', '-18', '-16']; DEV-FULL ['-14', '-15', '-14']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | -14839 | -9451 | -5388 | -2257 |
| net8 | -23679 | -14961 | -8718 | -3581 |
| gross | -5882 | -3856 | -2026 | -900 |
| funding | -117 | -85 | -33 | -33 |
| closed | 2210 | 1377 | 833 | 331 |
| long_net4 | -6607 | -3256 | -3352 | -2741 |
| long_closed | 1124 | 698 | 426 | 206 |
| short_net4 | -8232 | -6195 | -2037 | 484 |
| short_closed | 1086 | 679 | 407 | 125 |
| open_n | 0 | 1 | 0 | 0 |
| open_mtm | 0 | -4.529 | 0 | 0 |
| win | 0.4765 | 0.4779 | 0.4742 | 0.4622 |
| mdd_1m | 22870 | 18698 | 7875 | 4226 |
| sharpe | -0.6785 | -0.628 | -0.7923 | -0.9532 |
| fill_notional_rate | 0.8464 | 0.8459 | 0.8473 | 0.8665 |
| pos_month_ratio | 0.4333 | 0.3889 | 0.5 | 0.4 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL -14839/-6607/-8232; DEV-A -9451/-3256/-6195; DEV-B -5388/-3352/-2037; TEST -2257/-2741/484
- o2_p1.0: DEV-FULL -18497/-7611/-10886; DEV-A -11706/-4101/-7605; DEV-B -6791/-3510/-3281; TEST -2103/-2805/703
- o2_p2.0: DEV-FULL -21851/-7656/-14195; DEV-A -14672/-4542/-10130; DEV-B -7179/-3114/-4065; TEST -1570/-2892/1322
- o5_p0.5: DEV-FULL -12847/-5379/-7468; DEV-A -7134/-1334/-5800; DEV-B -5713/-4044/-1669; TEST -2075/-3502/1427
- o5_p1.0: DEV-FULL -12908/-4570/-8338; DEV-A -7146/-488/-6658; DEV-B -5762/-4082/-1680; TEST -2889/-4148/1259
- o5_p2.0: DEV-FULL -14262/-4847/-9415; DEV-A -7143/-1003/-6140; DEV-B -7118/-3844/-3274; TEST -2184/-3538/1354

### I top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=I|weeks=208|tail=0.1|hold=480|offset=2 | False | -5.882 | -11339 | -4300 | -1152 | -1173 | 161 | 147 |
| family=I|weeks=208|tail=0.1|hold=240|offset=2 | False | -5.031 | -8700 | 1556 | -3309 | -2043 | 260 | 234 |
| family=I|weeks=104|tail=0.2|hold=480|offset=2 | False | -11 | -27446 | -5147 | -1947 | -2293 | 263 | 248 |
| family=I|weeks=104|tail=0.1|hold=480|offset=2 | False | -4.585 | -14839 | -3352 | -2257 | -2741 | 206 | 125 |
| family=I|weeks=208|tail=0.2|hold=480|offset=2 | False | -6.299 | -14941 | -2860 | -3690 | -2886 | 259 | 220 |

## J DEV_PICK: family=J|lead=30|zthr=2.0|hold=60|offset=2
eligible False (n_eligible 0); verdict KILL; DEV score -1.197; adaptive score -1.763
boot p05 mean/day TEST 20/60/120 ['-3.2', '-2.745', '-2.367']; DEV-FULL ['-3.273', '-3.134', '-3.093']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | -3487 | -1939 | -1549 | -273 |
| net8 | -6975 | -4227 | -2749 | -441 |
| gross | -1132 | -588 | -544 | -126 |
| funding | 1132 | 937 | 195 | 21 |
| closed | 872 | 572 | 300 | 42 |
| long_net4 | -1006 | -190 | -816 | 156 |
| long_closed | 296 | 175 | 121 | 22 |
| short_net4 | -2481 | -1748 | -732 | -429 |
| short_closed | 576 | 397 | 179 | 20 |
| open_n | 0 | 0 | 0 | 0 |
| open_mtm | 0 | 0 | 0 | 0 |
| win | 0.4622 | 0.4685 | 0.45 | 0.5 |
| mdd_1m | 4780 | 3238 | 1683 | 440 |
| sharpe | -0.5633 | -0.4182 | -1.086 | -0.7868 |
| fill_notional_rate | 0.8835 | 0.8854 | 0.8798 | 0.84 |
| pos_month_ratio | 0.4737 | 0.4286 | 0.6 | 0.3333 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL -3487/-1006/-2481; DEV-A -1939/-190/-1748; DEV-B -1549/-816/-732; TEST -273/156/-429
- o2_p1.0: DEV-FULL -4339/-1319/-3021; DEV-A -2119/-245/-1873; DEV-B -2221/-1073/-1147; TEST -308/132/-440
- o2_p2.0: DEV-FULL -6013/-2559/-3453; DEV-A -3469/-1058/-2412; DEV-B -2544/-1502/-1042; TEST -540/-49/-491
- o5_p0.5: DEV-FULL -2318/-431/-1887; DEV-A -1276/154/-1430; DEV-B -1042/-585/-457; TEST -400/93/-494
- o5_p1.0: DEV-FULL -2527/-555/-1972; DEV-A -1206/182/-1388; DEV-B -1321/-737/-584; TEST -418/79/-497
- o5_p2.0: DEV-FULL -3439/-1113/-2327; DEV-A -1434/26/-1460; DEV-B -2006/-1139/-867; TEST -410/63/-473

### J top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=J|lead=30|zthr=2.0|hold=480|offset=2 | False | -3.74 | -4962 | -2734 | 674 | 171 | 22 | 15 |
| family=J|lead=30|zthr=1.0|hold=480|offset=2 | False | -7.173 | -13375 | -5243 | -122 | -81 | 97 | 71 |
| family=J|lead=30|zthr=2.0|hold=240|offset=2 | False | -3.705 | -334 | -2708 | 73 | -179 | 22 | 20 |
| family=J|lead=60|zthr=2.0|hold=60|offset=2 | False | -1.473 | -3882 | -613 | -242 | -343 | 21 | 25 |
| family=J|lead=60|zthr=2.0|hold=240|offset=2 | False | -3.088 | -5758 | -2257 | -195 | -367 | 21 | 25 |

## K DEV_PICK: family=K|base=B1|g=1.0|action=veto|tv=0.4|offset=2
eligible True (n_eligible 4); verdict PROFIT_PASS+LOW_N; DEV score 0.9444; adaptive score 0.6334
boot p05 mean/day TEST 20/60/120 ['-14', '-9.613', '-7.12']; DEV-FULL ['-2.742', '-2.209', '-1.015']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | 14680 | 8108 | 6572 | 1369 |
| net8 | 14569 | 8045 | 6524 | 1343 |
| gross | 18256 | 10313 | 7943 | 1320 |
| funding | -3465 | -2142 | -1323 | 75 |
| closed | 36 | 21 | 15 | 6 |
| long_net4 | 11157 | 5276 | 5881 | 177 |
| long_closed | 26 | 14 | 12 | 1 |
| short_net4 | 3522 | 2832 | 690 | 1191 |
| short_closed | 10 | 7 | 3 | 5 |
| open_n | 1 | 1 | 1 | 1 |
| open_mtm | 1562 | 4559 | 1562 | 351 |
| win | 0.2778 | 0.3333 | 0.2 | 0.6667 |
| mdd_1m | 8880 | 7866 | 8880 | 2579 |
| sharpe | 0.4741 | 0.4884 | 0.487 | 0.5006 |
| fill_notional_rate | 0.9664 | 1 | 0.9243 | 1 |
| pos_month_ratio | 0.541 | 0.5676 | 0.5 | 0.4 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL 14680/11157/3522; DEV-A 8108/5276/2832; DEV-B 6572/5881/690; TEST 1369/177/1191
- o2_p1.0: DEV-FULL 14680/11157/3522; DEV-A 8108/5276/2832; DEV-B 6572/5881/690; TEST 1336/177/1159
- o2_p2.0: DEV-FULL 14615/11092/3522; DEV-A 8043/5211/2832; DEV-B 6572/5881/690; TEST 1325/178/1147
- o5_p0.5: DEV-FULL 14688/11144/3544; DEV-A 8081/5236/2846; DEV-B 6606/5908/698; TEST 1354/183/1170
- o5_p1.0: DEV-FULL 14689/11145/3544; DEV-A 8082/5237/2846; DEV-B 6606/5908/698; TEST 1354/183/1170
- o5_p2.0: DEV-FULL 14676/11132/3544; DEV-A 8069/5224/2846; DEV-B 6606/5908/698; TEST 1343/184/1159

## K RESELECTED_ADAPTIVE: family=K|base=B1|g=1.0|action=flat30|tv=0.4|offset=2
eligible True (n_eligible 4); verdict PROFIT_PASS; DEV score 0.2501; adaptive score 0.7267
boot p05 mean/day TEST 20/60/120 ['-19', '-14', '-11']; DEV-FULL ['-1.225', '-1.086', '0.07842']

| metric | DEV-FULL | DEV-A | DEV-B | TEST |
|---|---|---|---|---|
| net4 | 12370 | 6592 | 5778 | 718 |
| net8 | 10201 | 5301 | 4900 | 179 |
| gross | 17330 | 9548 | 7782 | 1190 |
| funding | -2791 | -1665 | -1126 | 66 |
| closed | 725 | 478 | 247 | 155 |
| long_net4 | 9662 | 4067 | 5595 | 277 |
| long_closed | 451 | 236 | 215 | 19 |
| short_net4 | 2708 | 2526 | 183 | 441 |
| short_closed | 274 | 242 | 32 | 136 |
| open_n | 1 | 0 | 1 | 1 |
| open_mtm | 25 | 0 | 25 | -235 |
| win | 0.4869 | 0.4833 | 0.4939 | 0.4839 |
| mdd_1m | 4984 | 4729 | 4984 | 3296 |
| sharpe | 0.5832 | 0.4766 | 0.7836 | 0.2511 |
| fill_notional_rate | 0.9346 | 0.9476 | 0.916 | 0.8846 |
| pos_month_ratio | 0.541 | 0.5676 | 0.5 | 0.4 |

stress (offset, pen) -> net4 / long / short per window:
- o2_p0.5: DEV-FULL 12370/9662/2708; DEV-A 6592/4067/2526; DEV-B 5778/5595/183; TEST 718/277/441
- o2_p1.0: DEV-FULL 11706/9189/2517; DEV-A 6366/4004/2362; DEV-B 5340/5185/155; TEST 507/205/302
- o2_p2.0: DEV-FULL 10606/8138/2469; DEV-A 5880/3623/2257; DEV-B 4727/4515/212; TEST 172/67/106
- o5_p0.5: DEV-FULL 13022/9948/3075; DEV-A 7019/4211/2807; DEV-B 6004/5737/267; TEST 797/203/594
- o5_p1.0: DEV-FULL 12194/9412/2782; DEV-A 6683/4113/2570; DEV-B 5511/5299/212; TEST 634/231/402
- o5_p2.0: DEV-FULL 10663/8224/2439; DEV-A 5994/3797/2196; DEV-B 4669/4427/243; TEST 552/151/401

### K top5 by TEST worst-side (offset2)

| variant_id | DEV_eligible | DEV_score | DEV-FULL_net4 | DEV-B_worst | TEST_net4 | TEST_worst | TEST_long_closed | TEST_short_closed |
|---|---|---|---|---|---|---|---|---|
| family=K|base=V|g=0.0|action=veto|tv=0.2|offset=2 | False | -2.797 | 6044 | -2045 | 1515 | 400 | 63 | 77 |
| family=K|base=B1|g=1.0|action=flat30|tv=0.4|offset=2 | True | 0.2501 | 12370 | 183 | 718 | 277 | 19 | 136 |
| family=K|base=B1|g=0.0|action=veto|tv=0.4|offset=2 | True | 0.8432 | 14059 | 616 | 1361 | 177 | 1 | 5 |
| family=K|base=B1|g=1.0|action=veto|tv=0.4|offset=2 | True | 0.9444 | 14680 | 690 | 1369 | 177 | 1 | 5 |
| family=K|base=V|g=1.0|action=veto|tv=0.2|offset=2 | False | -2.859 | 4391 | -2090 | 1074 | 141 | 93 | 98 |

## Control: Batch-1 A picks under fixed engine

### model=vt_tsmom|lookback_set=1d_4|deadband=0.25|target_vol=0.6|offset=2
| metric | old DEV | new DEV-FULL | old TEST | new TEST |
|---|---|---|---|---|
| net4 | 16928 | 16930 | 1561 | 1574 |
| net8 | 16788 | 16792 | 1533 | 1548 |
| gross | 21548 | 21548 | 1532 | 1540 |
| funding | -4480 | -4480 | 57 | 60 |
| closed | 37 | 36 | 7 | 6 |
| long_net4 | 12913 | 12913 | 382 | 382 |
| long_closed | 26 | 26 | 2 | 1 |
| short_net4 | 4014 | 4016 | 1179 | 1191 |
| short_closed | 11 | 10 | 5 | 5 |
| open_n | 1 | 1 | 1 | 1 |
| win | 0.2973 | 0.2778 | 0.5714 | 0.6667 |
| mdd_1m | 9219 | 11799 | 2292 | 2468 |
| sharpe | 0.4524 | 0.4525 | 0.5584 | 0.5657 |
| fill_notional_rate | 0.9487 | 0.9459 | 1 | 1 |
| pos_month_ratio | 0.2609 | 0.541 | 0.25 | 0.4 |

### model=vt_tsmom|lookback_set=4h_3|deadband=0.5|target_vol=0.4|offset=2
| metric | old DEV | new DEV-FULL | old TEST | new TEST |
|---|---|---|---|---|
| net4 | 20098 | 20100 | 2556 | 2478 |
| net8 | 18979 | 18983 | 2359 | 2282 |
| gross | 24502 | 24502 | 2780 | 2697 |
| funding | -3285 | -3285 | -26 | -24 |
| closed | 363 | 362 | 51 | 50 |
| long_net4 | 22094 | 22094 | 1586 | 1625 |
| long_closed | 187 | 187 | 17 | 16 |
| short_net4 | -1996 | -1994 | 970 | 853 |
| short_closed | 176 | 175 | 34 | 34 |
| open_n | 1 | 1 | 1 | 1 |
| win | 0.2865 | 0.2845 | 0.2941 | 0.3 |
| mdd_1m | 3830 | 4425 | 2009 | 2659 |
| sharpe | 0.8466 | 0.8467 | 0.9365 | 0.9083 |
| fill_notional_rate | 0.9404 | 0.936 | 0.8361 | 0.9067 |
| pos_month_ratio | 0.4615 | 0.4928 | 0.5556 | 0.6 |

## Data gaps
```
{
 "DEV-FULL": {
  "metrics_5m_missing_from_2020-09-01": 3684,
  "metrics_5m_rows": 561024,
  "premium_missing_min": 201,
  "minutes": 3156480,
  "funding_events": 6576,
  "funding_gaps_gt_8h05": 0,
  "oi_bad_in_present": 469,
  "global_ls_bad_in_present": 5776,
  "top_ls_bad_in_present": 92175,
  "taker_lsr_bad_in_present": 37272
 },
 "DEV-A": {
  "metrics_5m_missing_from_2020-09-01": 505,
  "metrics_5m_rows": 350496,
  "premium_missing_min": 199,
  "minutes": 2103840,
  "funding_events": 4383,
  "funding_gaps_gt_8h05": 0,
  "oi_bad_in_present": 143,
  "global_ls_bad_in_present": 5771,
  "top_ls_bad_in_present": 92165,
  "taker_lsr_bad_in_present": 37272
 },
 "DEV-B": {
  "metrics_5m_missing_from_2020-09-01": 3179,
  "metrics_5m_rows": 210528,
  "premium_missing_min": 2,
  "minutes": 1052640,
  "funding_events": 2193,
  "funding_gaps_gt_8h05": 0,
  "oi_bad_in_present": 326,
  "global_ls_bad_in_present": 5,
  "top_ls_bad_in_present": 10,
  "taker_lsr_bad_in_present": 0
 },
 "TEST": {
  "metrics_5m_missing_from_2020-09-01": 9,
  "metrics_5m_rows": 80640,
  "premium_missing_min": 244,
  "minutes": 403200,
  "funding_events": 840,
  "funding_gaps_gt_8h05": 0,
  "oi_bad_in_present": 0,
  "global_ls_bad_in_present": 0,
  "top_ls_bad_in_present": 0,
  "taker_lsr_bad_in_present": 0
 },
 "F": {
  "oi_nan_5m": 71185,
  "I_nan": 14
 }
}
```