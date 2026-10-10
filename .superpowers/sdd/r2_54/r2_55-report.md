# R2-55 implement + historical test run 1 — report

Freeze: `out/k45_rl_r2_48_20261007/r2_55_k0607_c0_freeze.json`, sha256 `93da69ce3175b9bf6cca59fb2f46b43d06ac0b81d226346b04bc09141696379d` (verified; FROZEN; amendments REBASE_2026-10-10 suspended by REBASE_BACK_2026-10-10, then HISTORICAL_TEST_2026-10-10). Parent R2-52A `r2_52a_exit_freeze.json` sha256 `d1d56efa...` (verified). No freeze edits.

## Result

- **All 4 families FAIL. Keep the current AX books.** No switch. Test run count: 1 (`r2_55/test/test_runs.jsonl`).
- OCO_C0 and K13 pass the statistical gate (Holm adj p 0.0020, lower bound > 0). They fail only on per-pair worst-position gates.
- E1 and K14 fail the statistical gate.
- The causal guard changes only the OCO-entry ids (K06 x2, K07 x2, K14). The other 25 current ids and K01_FLIP give identical trades with the guard on.

## Implementation

- Causal guard: `SimConfig.causal_guard` (default False, `repr=False`, so default reprs stay byte-identical). It applies to R2_52A/R2_52B only; BASE + guard raises `bad config`. The `reference._simulate_r2_52a` and `core._adaptive_loop` paths skip the reverse, native flag, AX flag and anchor-state checks of a held-component row when `decision_time <= fill minute`. A skipped row does not use up a one-shot anchor. V3 and stops are not affected.
- AXC0: `build_variant(..., ax=True, axc0=True)` applies `Spec.axc0`, defined only for the 10 changed ids. Other ids raise, and `axc0` without `ax` raises.
  - `legacy.e1_axc0` (K04, and the E1-15 component only of B1-B3): `anchor_upper`/`anchor_lower` = prior-20-bar high/low of the 15 m row (stored at fill, never updated); `anchor_price` = completed 15 m close. The E1 rolling AX flags are off. A2/F3/F3W rows are untouched.
  - `volatility.oco_c0` (K06 hourly, K07 15 m): anchors = decision close C0 (`ind_close`) of the filling OCO row.
  - `trend.k13_axc0`: `exit_long = (side == -1)` (all three signs -1) and `exit_short = (side == 1)`. A 0 or NaN sign gives no exit. Strict reentry means no reversal on the same row.
  - `trend.k14_axc0`: session OCO rows store C0 (the completed opening-range close) as both anchors; the inert 5 m rows store nothing.
- Default path byte-identical (verified): a pre-edit vs post-edit hash of 29 ids + K01_FLIP covered the BASE table, AX table, core trades+minute pnl (2025-06..2026-01, k 1.5) and reference trades+pnl (2025-12-20..2026-01). All 30 were equal. Paper uses `build_variant(ax=True)` + `SimConfig(exit_policy="R2_52A")`, so it is unchanged. No live DB/config writes, no restarts.
- Tests: `tests/sim/test_r2_55_axc0.py` (71) covers:
  - guard per exit kind x side x engine;
  - one-shot anchor preserved; market-entry equality case; BASE rejection and repr;
  - core==reference with guard on random cases (R2_52A and R2_52B); the guard changes some random cases;
  - long/short `<=`/`>=` thresholds and component isolation; K13 loss of unanimity ignored and opposite unanimity exits;
  - table tests for each family; core==reference on real AXC0 K04/K14 tables.
- Runner: `scripts/sim_r2_55.py` with `select` / `test`.

## k selection (pre-2026, R2-52A rolling W01-W10, k {1,1.5,2}, tie 2.0)

Registry 5694 -> 5724 (+30, checked before and after). W10 k for AXC0 (AX W10 k from `r2_52a/selected_k.csv` in brackets):
B1 1.0 [2.0], B2 1.0 [2.0], B3 1.0 [1.0], K04 2.0 [1.0], K06_k0.5 2.0 [2.0], K06_k1.0 2.0 [2.0], K07_k0.5 2.0 [1.5], K07_k1.0 2.0 [2.0], K13 2.0 [2.0], K14 2.0 [1.5]. K01_FLIP AX k 2.0 (`r2_52a_flip` W10).
Interpretation: selection used the family repair only, with no guard. This matches the paired AX k, which was selected without the guard, and the k_source text "only its frozen family repair".
Files: `r2_55/selection/selected_k.csv`, `manifest.json`.

## Historical test run 1: [2026-01-01, 2026-10-08)

- Inputs: R2-54 FINAL snapshot verified by `run_r2_54_stageb.verify_snapshot(read_frames=True)` (manifest sha `b748d364...`, every artifact hash plus the taker archive-only rows assertion). Context: `test_context()` (pre-2026 warm-up + snapshot 1 m market/metrics/premium/Stage-A). Ledger funding: PESS at actual settlement times (`sb.ledger_settlements`).
- Setup: both arms R2_52A + `causal_guard=True`, flat at 2026-01-01, constant W10 k. The run ends with a data_end close, which does not count as a completed position.
- Daily series: every UTC day zero-filled, 280 days. MDD is computed on the 1 m MTM cumulative ledger (gate); the daily version is reported alongside.
- Bootstrap: centered PW stationary bootstrap, 2000 reps, seed 0; Holm over the 4 families.

| family | mean d/day (4 bps) | 95% CI | raw p | Holm adj p | stat gate | member pairs failing | decision |
|---|---|---|---|---|---|---|---|
| K13_OPPOSITE_CONSENSUS | +45.58 | [24.54, 68.16] | 0.0005 | 0.0020 | PASS | K13 (worst) | FAIL |
| PREDICTED_OCO_C0 | +31.11 | [20.32, 42.37] | 0.0005 | 0.0020 | PASS | K07_k0.5 (worst) | FAIL |
| E1_15_BREAKOUT_LEVEL | +7.44 | [-0.56, 16.02] | 0.0395 | 0.0790 | fail | B3 (MDD), K04 (worst, MDD) | FAIL |
| K14_ORB_C0 | +5.96 | [-7.06, 18.70] | 0.1814 | 0.1814 | fail | K14 (worst) | FAIL |

Per pair (AXC0 vs AX, guard on both; net in bps; "pos" = completed/total positions; worst = worst position incl. cutoff mark; MDD = 1 m ledger):

| pair | d4 | d8 | C0 net4 / AX net4 | C0 net8 / AX net8 | pos C0 / AX | worst C0 / AX | MDD C0 / AX | pair |
|---|---|---|---|---|---|---|---|---|
| B1 | +1594.9 | +222.9 | 571.1 / -1023.8 | -2416.9 / -2639.8 | 746/747, 403/404 | -304.0 / -304.8 | 3377 / 4550 | pass |
| B2 | +1617.3 | +737.3 | 862.9 / -754.4 | -1221.1 / -1958.4 | 520/521, 300/301 | -304.0 / -304.3 | 2158 / 4015 | pass |
| B3 | +1588.9 | +1668.9 | 2347.8 / 758.9 | 475.8 / -1193.1 | 467/468, 487/488 | -304.0 / -304.0 | 1609 / 1525 | fail MDD |
| K04 | +3533.5 | +3777.5 | 2587.3 / -946.2 | 1731.3 / -2046.2 | 214/214, 275/275 | -183.4 / -142.3 | 1383 / 1306 | fail worst, MDD |
| K06_k0.5 | +822.5 | +3894.5 | -12323.4 / -13145.8 | -17807.4 / -21701.8 | 1370/1371, 2139/2139 | -304.0 / -304.0 | 13190 / 13712 | pass |
| K06_k1.0 | +5476.8 | +7140.8 | -268.1 / -5744.9 | -3704.1 / -10844.9 | 859/859, 1275/1275 | -245.7 / -304.0 | 3718 / 5944 | pass |
| K07_k0.5 | +15511.1 | +31239.1 | -10048.8 / -25559.9 | -18784.8 / -50023.9 | 2183/2184, 6115/6116 | -203.8 / -189.6 | 11301 / 25586 | fail worst |
| K07_k1.0 | +13033.7 | +21305.7 | -6926.9 / -19960.6 | -12610.9 / -33916.6 | 1420/1421, 3489/3489 | -304.0 / -304.0 | 7837 / 20007 | pass |
| K13 | +12762.5 | +25454.5 | -5073.6 / -17836.1 | -8829.6 / -34284.1 | 938/939, 4112/4112 | -304.0 / -218.6 | 8119 / 17916 | fail worst |
| K14 | +1667.8 | +2219.8 | -2129.0 / -3796.9 | -4805.0 / -7024.9 | 669/669, 807/807 | -168.0 / -103.4 | 3938 / 4292 | fail worst |

- Minimum evidence (>= 30 completed positions per arm per pair, full window): met by all 10 pairs.
- Alternative readings do not change any decision:
  - With 8 bps report-only: no pair fails the 8 bps gate anyway.
  - With daily-ledger MDD: K04 passes MDD (1201 vs 1264) but still fails worst; B3 still fails (1531 vs 1327).
- Absolute 4 bps net is negative for most AXC0 books (K06/K07/K13/K14). The pairs show "less bad", not profitable.
- Exit mix: AX K13 exits by flag 4027/4112. AXC0 K13 exits by reverse 693, trail 161, stop 84. Both AX K07s are dominated by state exits (5043 and 3030).

K13 risk (4 bps, AXC0 vs AX):

| | hold p50 h | p95 h | max h | funding bps | exposure share | open at cutoff, age h |
|---|---|---|---|---|---|---|
| AXC0 | 5.25 | 13.57 | 28.0 | -13.06 | 0.867 | 1 position, 21.7 |
| AX | 0.25 | 1.0 | 2.5 | +1.46 | 0.264 | none |

## Guard-only effect: AX with vs without the guard, same window and W10 k

Identical trades: B1, B2, B3, K01, K02, K03, K04, K05, K08, K09, K11_15m, K11_1h, K12_30m, K12_1h, K13, K15, K19, K21_A, K21_B, K23, K24, K26, K29, K30, K01_FLIP (delta 0).

Changed (OCO entries, where a fill-minute close was used as an exit before the guard):

| id | d4 (guard - none) | d8 | net4 guard / none | positions guard / none | MDD guard / none |
|---|---|---|---|---|---|
| K06_k0.5 | -616.2 | -616.2 | -13145.8 / -12529.6 | 2139 / 2139 | 13712 / 13110 |
| K06_k1.0 | +864.0 | +904.0 | -5744.9 / -6608.9 | 1275 / 1285 | 5944 / 6814 |
| K07_k0.5 | +1847.0 | +2603.0 | -25559.9 / -27406.9 | 6116 / 6305 | 25586 / 27647 |
| K07_k1.0 | +331.9 | +651.9 | -19960.6 / -20292.5 | 3489 / 3569 | 20007 / 20338 |
| K14 | +905.2 | +913.2 | -3796.9 / -4702.1 | 807 / 809 | 4292 / 4850 |

Worst position is unchanged for all ids. Because the differential is nonzero, the freeze scope says all pairs restart at the same time if a shadow deployment follows. That point is moot for the decision because all families fail.

## Caveats

- Contamination: the 2026 window was the R2-54 Stage-B test (outcomes seen), as recorded in the amendment. Design diagnostics came from 2023-09..2025-12.
- Choices that are not literal in the freeze:
  - k selection without the guard;
  - MDD on the 1 m ledger;
  - the 8 bps per-pair gate kept as frozen, although the user brief said "8 bps report". Neither reading changes a decision.
- The paper AXC0 shadow books (catalog/config) were not built. They are not needed for the HISTORICAL_TEST decision, and live config is untouched.

## Tests

`tests/sim` + `tests/test_paper_*.py`: 978 passed (24.5 min).

## Files

- Code: `btcusdt_quant/sim/{core,reference}.py`, `btcusdt_quant/sim/strategies/{__init__,legacy,volatility,trend}.py`, `scripts/sim_r2_55.py`, `tests/sim/test_r2_55_axc0.py`.
- Outputs: `out/k45_rl_r2_48_20261007/r2_55/selection/{selected_k.csv,manifest.json}`, `r2_55/test/test_runs.jsonl`, `r2_55/test/run_01/report.json` (+ per-id trades/daily parquet, not committed).
