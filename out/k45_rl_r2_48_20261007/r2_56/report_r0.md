# R2-56 continuous-ledger replay

window 2026-01-01 00:00:00+00:00 .. 2026-10-08 00:00:00+00:00 (exclusive); 4 bps round trip maker flat, no slippage, PESS funding; 8 bps report-only

| candidate | net4 | net8 | trades | win | long4 | short4 | L/S n | MDD | worst |
|---|---|---|---|---|---|---|---|---|---|
| B3_AXC0 | 2347.8 | 475.8 | 468 | 0.470 | 506.7 | 1841.2 | 293/175 | 1609.4 | -304.0 |
| K04_AXC0 | 2587.3 | 1731.3 | 214 | 0.243 | 2587.3 | 0.0 | 214/0 | 1383.1 | -183.4 |
| C1_F_V5+E_V1a | 4820.2 | 4292.2 | 132 | 0.439 | 3002.0 | 1818.2 | 102/30 | 1185.8 | -416.0 |
| C1_F_V5r+E_V1a | 4563.9 | 4039.9 | 131 | 0.450 | 2829.7 | 1734.3 | 101/30 | 1185.8 | -416.0 |
| C4_F_V0+E_V1a | 5237.2 | 3899.2 | 335 | 0.442 | 2946.7 | 2290.5 | 193/142 | 1793.3 | -321.0 |
| SWITCH_C1C4 | 3436.6 | 2696.6 | 185 | 0.470 | 2320.7 | 1115.9 | 115/70 | 1725.6 | -360.8 |

## monthly net 4 bps

| candidate | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 |
|---|---|---|---|---|---|---|---|---|---|---|
| B3_AXC0 | 532.8 | 732.3 | 559.7 | -176.3 | -60.6 | 363.5 | -836.6 | 1095.3 | 226.1 | -88.4 |
| K04_AXC0 | -122.7 | 58.7 | -89.3 | 288.5 | 14.3 | -1.4 | -46.4 | 1743.2 | 635.1 | 107.3 |
| C1_F_V5+E_V1a | 574.2 | 860.0 | -289.3 | 634.3 | 190.6 | 1461.8 | 193.2 | 1249.6 | 504.7 | -558.9 |
| C1_F_V5r+E_V1a | 574.2 | 860.0 | -289.3 | 488.8 | 190.6 | 1374.7 | 193.2 | 1220.1 | 504.7 | -553.1 |
| C4_F_V0+E_V1a | 580.6 | 1433.4 | 139.8 | 602.0 | 658.1 | 1760.7 | -741.5 | 670.8 | 470.7 | -337.4 |
| SWITCH_C1C4 | -588.6 | 1472.6 | -639.5 | 262.6 | 156.1 | 1128.1 | -92.4 | 1315.9 | 1000.9 | -579.2 |

## components (4 bps)

- C1_F_V5+E_V1a: E1/V1a 2207.8 (38), F3/V5 2612.4 (94)
- C1_F_V5r+E_V1a: E1/V1a 2207.8 (38), F3/V5r 2356.2 (93)
- C4_F_V0+E_V1a: E1/V1a 2685.5 (31), F3-w30/V0 2551.7 (304)
- SWITCH_C1C4: E1/V1a 2210.6 (43), F3-w30/V0 2370.9 (107), F3/V5 -1144.9 (35)

## native reference

| candidate | window | net4 | net8 | trades | MDD | worst |
|---|---|---|---|---|---|---|
| B3_AXC0 | 2023-09-01..2026-01-01 | 3174.5 | -1181.5 | 1089 | 4564.4 | -305.9 |
| K04_AXC0 | 2023-09-01..2026-01-01 | 2678.6 | -25.4 | 676 | 1683.8 | -304.0 |
| C1_F_V5+E_V1a | 2023-01-01..2026-01-01 | 17105.3 | 14881.3 | 556 | 3418.7 | -1060.1 |
| C1_F_V5r+E_V1a | 2023-01-01..2026-01-01 | 17337.2 | 15117.2 | 555 | 3409.1 | -1048.5 |
| C4_F_V0+E_V1a | 2023-01-01..2026-01-01 | 12079.9 | 7043.9 | 1260 | 4270.9 | -637.5 |
| SWITCH_C1C4 | 2023-01-01..2026-01-01 | 12924.8 | 10084.8 | 710 | 4563.1 | -637.5 |

## parity

```
{
 "B3_AXC0": {
  "replay": 2347.842551706386,
  "reference": 2347.842551706386,
  "abs_diff": 0.0,
  "match": true
 },
 "K04_AXC0": {
  "replay": 2587.292719709675,
  "reference": 2587.292719709675,
  "abs_diff": 0.0,
  "match": true
 },
 "C_R2_37": {
  "C1_F_V5+E_V1a": {
   "HOLD_B": {
    "replay": 3429.598458620384,
    "reference": 3429.598458620384,
    "abs_diff": 0.0
   },
   "HOLD_A": {
    "replay": 1945.450183991556,
    "reference": 1910.2030977057352,
    "abs_diff": 35.24708628582084
   }
  },
  "C1_F_V5r+E_V1a": {
   "HOLD_B": {
    "replay": 3197.008652251184,
    "reference": 3197.008652251184,
    "abs_diff": 0.0
   },
   "HOLD_A": {
    "replay": 1916.005288508592,
    "reference": 1912.9225856774733,
    "abs_diff": 3.082702831118695
   }
  },
  "C4_F_V0+E_V1a": {
   "HOLD_B": {
    "replay": 5172.550653141716,
    "reference": 5172.550653141716,
    "abs_diff": 0.0
   },
   "HOLD_A": {
    "replay": 398.010445580301,
    "reference": 628.2258343926235,
    "abs_diff": 230.2153888123225
   }
  }
 }
}
```

## overlap 2026

```
{
 "B3_vs_K04": {
  "a": 468,
  "b": 214,
  "shared": 89
 },
 "C1_V5_vs_C4_V0": {
  "a": 132,
  "b": 334,
  "shared": 27
 },
 "C1_V5r_vs_C4_V0": {
  "a": 131,
  "b": 334,
  "shared": 27
 }
}
```

## switch

```
{
 "routing": {
  "book_trades_M_nan": 548,
  "book_trades_route_C4": 711,
  "book_trades": 1623
 },
 "mapping_2023_2025": {
  "C1_F_V5+E_V1a": {
   "M_ge_2/3": {
    "trades": 302,
    "net_4bps": 11732.82444297551
   },
   "else": {
    "trades": 254,
    "net_4bps": 5372.4960855943045
   }
  },
  "C4_F_V0+E_V1a": {
   "M_ge_2/3": {
    "trades": 522,
    "net_4bps": 10817.762697956256
   },
   "else": {
    "trades": 737,
    "net_4bps": 1255.4972059073234
   }
  }
 },
 "M_coverage": {
  "first": "2022-03-01 00:00:00+00:00",
  "last": "2026-10-07 23:45:00+00:00",
  "rows": 161280,
  "M_nan_rows_2023_on": 0
 }
}
```

## causality

- B3_AXC0/K04_AXC0: R2-55 path: decision rows from predictions with logical_available_at <= decision, delay 1 min fill, SimConfig causal_guard=True, k fixed from pre-2026 W10 selection, flat start 2026-01-01; funding settlements from snapshot (Oct REST rows).
- C1/C4: F3 V0: LS value with archive create_time+5m strictly before T (feature cache rule t-6m). V5: LS event evaluated at create_time+5m (here feature open_time+5m), baseline = previous full-hour rolling quantile. V5r: event-level rolling quantile of past events. E1 V1a: partial-hour volume and close through the closed minute, prior 19 completed bars, prior 20-bar high; entry at next minute open. October LS rebuilt from snapshot with the same t-6m rule (verified exact on Q3).
- SWITCH: M = mean of 9 M-target causal percentile ranks vs strictly earlier 30 d predictions (min 7 d); predictions logical_available_at = prediction_ts <= entry minute (asof, age <= 15 min); missing M -> C1 (mapping else-branch); mapping M>=2/3 -> C4 fixed, not fit on 2026.

## deviations

- C1/C4 2026 is one continuous ledger (no reset at 07-01/10-01); R2-37 segmented H1/Q3 closes differ at boundaries (see continuous_vs_segmented).
- C trade counts follow R2-37 (entry < end and exit >= start, includes carried trades); win rate/worst position use full-trade net. AXC0 counts positions opened in-window (flat start).
- AXC0 native window = R2-52A stitched test 2023-09-01..2026-01-01 with per-window R2-55 AXC0 k (causal_guard=True); C/SWITCH native = 2023-01-01..2026-01-01 on the same continuous ledger.
- R2-44 fold predictions miss 2025-12-31 (and 2023-12-31); those decisions have M=NaN -> C1.
