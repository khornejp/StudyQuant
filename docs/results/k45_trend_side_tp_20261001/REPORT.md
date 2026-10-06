# Stage 2: trend-conditioned side TP — exploratory result

Label: `EXPLORATORY_AFTER_DEV_FAIL`. Stage 1 DEV failed; this run proceeds only by explicit user decision.

DEV selection: None; Bonferroni alpha = 0.01666667.
HOLD-B gate: NOT_RUN_NO_DEV_SELECTION.

Book occupancy remains fixed through `entry + 45` regardless of an earlier TP fill. TP never creates a new admission opportunity.

## Net grid

| segment | TP bps | arm | n | net mean bps | one-sided p |
|---|---:|---|---:|---:|---:|
| DEV | 50 | BOOK | 2794 | -0.833527 | 0.721214 |
| DEV | 50 | DOWN_BREAKOUT_LONG | 1392 | 0.325617 | 0.449378 |
| DEV | 50 | UP_BREAKOUT_SHORT | 1402 | -1.984403 | 0.848108 |
| DEV | 100 | BOOK | 2794 | 0.198570 | 0.458077 |
| DEV | 100 | DOWN_BREAKOUT_LONG | 1392 | 1.463301 | 0.278036 |
| DEV | 100 | UP_BREAKOUT_SHORT | 1402 | -1.057139 | 0.684066 |
| DEV | 150 | BOOK | 2794 | 0.725592 | 0.351332 |
| DEV | 150 | DOWN_BREAKOUT_LONG | 1392 | 1.307686 | 0.304185 |
| DEV | 150 | UP_BREAKOUT_SHORT | 1402 | 0.147649 | 0.479176 |

## Paired TP minus no-TP

Same admitted trades; daily Politis-White inference is two-sided.

| segment | TP bps | arm | n | paired mean bps | two-sided p |
|---|---:|---|---:|---:|---:|
| DEV | 50 | BOOK | 2794 | -0.151111 | 0.924154 |
| DEV | 50 | DOWN_BREAKOUT_LONG | 1392 | -1.645686 | 0.377981 |
| DEV | 50 | UP_BREAKOUT_SHORT | 1402 | 1.332804 | 0.584721 |
| DEV | 100 | BOOK | 2794 | 0.880987 | 0.568772 |
| DEV | 100 | DOWN_BREAKOUT_LONG | 1392 | -0.508002 | 0.664167 |
| DEV | 100 | UP_BREAKOUT_SHORT | 1402 | 2.260068 | 0.40863 |
| DEV | 150 | BOOK | 2794 | 1.408008 | 0.322334 |
| DEV | 150 | DOWN_BREAKOUT_LONG | 1392 | -0.663616 | nan |
| DEV | 150 | UP_BREAKOUT_SHORT | 1402 | 3.464857 | 0.20074 |
