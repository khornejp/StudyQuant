# Stage 1: trend-conditioned side — result

Run 2026-10-01. Inputs: `causal_candidates.parquet` (frozen), `artifacts/btcusdt_2020_2026h1.parquet` (cutoff 2026-06-30). New model fits 0. Frozen hypothesis: "느린 추세 방향으로만 fade하면, 두 팔 모두 net이 0보다 크다."

## Verdict

**DEV gate: FAIL** (frozen criteria; not lowered). HOLD-B: FAIL (exploratory).

| segment | n book | net mean | trim top-2 | PW 95% CI | p | monthly + share |
|---|---|---|---|---|---|---|
| DEV 30d | 2,794 | −0.682 | −1.295 | [−4.191, 2.985] | 0.645 | 0.52 |
| HOLD-B 30d | 242 | −7.819 | −10.227 | [−18.518, 4.173] | 0.910 | 0.17 |
| DEV 7d (report) | 2,805 | −4.928 | −5.385 | [−8.491, −1.268] | 0.996 | 0.40 |

Reference: long-only book +0.455, shared book −0.521.

## Arm × trend, all candidates (net bps)

| arm | trend | DEV n | DEV net | HOLD-B n | HOLD-B net |
|---|---|---|---|---|---|
| LONG | up | 2,072 | **+3.19** | 95 | +10.44 |
| LONG | down | 2,246 | +0.44 | 279 | +1.66 |
| SHORT | down | 2,082 | −1.47 | 242 | −12.74 |
| SHORT | up | 2,001 | −6.26 | 96 | +5.89 |

Random 45-min trade in the trend direction (DEV): up-trend long −3.34, down-trend short −3.90.

## Reading

- The trend split moves both arms in the predicted direction on DEV: long +2.75, short +4.79.
- The short arm stays below cost even in down-trends (gross +2.53 against 4 bps). The short loses the book.
- HOLD-B reverses the short ordering (short in up-trend +5.89, in down-trend −12.74). The short-side trend effect is unstable.
- Long in up-trend is the only cell above cost on both segments. It is a post-hoc cell, not the frozen rule. Any test of it is a new hypothesis and exploratory.

## Next per plan

DEV failed for the frozen rule, so stage 2 (TP) does not run. Next candidate: 3-class target (spec §9).
