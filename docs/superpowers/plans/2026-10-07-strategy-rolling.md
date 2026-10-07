# Strategy Catalog Rolling Backtest (Plan 2 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the 24-technique catalog (K01–K24) plus composite books B1–B3 on the Plan 1 engine (`btcusdt_quant/sim/`) for every gate × exit combination, over the spec §5 rolling schedule, and produce comparison baseline ② ("previous-window best technique applied to the next window").

**Architecture:** Each technique is a pure function that turns complete bars and causal inputs into a signal table (Plan 1 `schema`). A gate step and an exit-style step turn one table into the four (gate × exit) variants. `core.simulate` runs every variant once over 2022-03-01..2026-01-01 with indicator warm-up from 2020. One runner slices the minute ledger into the rolling windows, picks the validation-window winner, and writes all results.

**Tech Stack:** Python 3.14 (`venv_btcusdt`), pandas, numpy, numba (Plan 1 core), pytest, `concurrent.futures.ProcessPoolExecutor` (≤ 8 workers).

**Spec:** `docs/superpowers/specs/2026-10-07-rl-trading-design.md` §3 (and §1, §2.1 position/fills, §5 rolling, §7). Technique definitions: `out/k45_strategy_engine_r2_47_20261007/BRIEF.md` §2–§3 (R2-47 catalog, read-only). K02–K05 and B1–B3: `out/run_k45_vol_gated_backtest_r2_45.py` (`build_fast_signals`, `simulate_fast`). DETEXIT: `out/run_k45_vol_gated_exits_r2_46.py` (`E_COLUMN`, `_thresholds`, `simulate_exit`). Plan 1: `docs/superpowers/plans/2026-10-07-sim-engine.md`.

## Global Constraints

- No git commit unless the user asks. Replace every commit step with "record changed files in the ledger".
- Do not modify `btcusdt_quant/paper/`, `artifacts/live/live.sqlite`, stage-1 outputs `out/k45_vol_detector_*`, R2-39/R2-45/R2-46/R2-47 outputs, or `docs/` other than this plan.
- Do not use `btcusdt_quant/backtest/` (R2-47 code, discarded by spec §2). Everything new lives under `btcusdt_quant/sim/`.
- P&L unit: one unlevered unit, bps. Primary cost 4 bps round trip (2 bps per side, every partial fill). Report 0/4/8/12 bps. No $100, leverage or sizing.
- Data: market `artifacts/btcusdt_2020_2026h1.parquet`; metrics usable when `create_time + 5 min < T`; funding after its settlement time; premium bar after its `close_time`; complete bars only; missing minutes never interpolated.
- Detector predictions are read-only (`out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw`). Values are already bps (median `prediction_exc_4h` ≈ 96).
- Strategy results use 2022-03-01 onward only; 2020-01..2022-02 is warm-up. **Nothing at or after 2026-01-01 is simulated or reported** (2026H1 is the spec §6 one-shot final check).
- Same-T policy: `reentry="strict"` for every combination except K01, which keeps R2-39's `stop_and_reverse` so it equals comparison baseline ① exactly.
- Parameters are the BRIEF §2 values. No parameter search; results never change definitions.
- CPU workers ≤ 8. No downloads, orders, or authenticated calls.
- Keep every result, passing or not (spec §0, §3).

## Review Focus

- A composite book (B1–B3) holding F3-30 must close it on an opposite F3-30 signal even when a higher-priority component (A2-30) fires at the same T, and must then choose the new entry by priority (Task 1 `test_multi_row_exits_before_entries`).
- A DETEXIT entry whose own entry minute touches the stop must exit in that minute (R2-46 checks from the entry bar) (Task 1 `test_detexit_checks_entry_minute`).
- A detector-prediction gap (last day of each stage-1 segment, or E missing) must block new entries for gated and DETEXIT variants but never exits (Task 2 `test_gate_missing_blocks_entry_only`).
- A strategy signal computed at T must not change when bars after T are appended (Task 3 `test_no_lookahead_all_strategies`, run for every catalog entry).
- A rolling window with zero trades for a combination must report net 0 with `zero_reason`, and the guard must reject it otherwise (Task 8 `test_zero_trade_window_has_reason`).

---

## File Structure

| File | Responsibility |
|---|---|
| `btcusdt_quant/sim/schema.py` (modify) | Multi-row decisions (unique `decision_time`+`component`) |
| `btcusdt_quant/sim/reference.py`, `core.py` (modify) | Engine semantics in Task 1 |
| `btcusdt_quant/sim/regime.py` | M/L causal percentiles, E lookup, gate masks |
| `btcusdt_quant/sim/rolling.py` | Spec §5 window schedule (shared with Plan 3) |
| `btcusdt_quant/sim/strategies/__init__.py` | `CATALOG`, `Spec` dataclass, `build_variant()` |
| `btcusdt_quant/sim/strategies/context.py` | `Context`: loaded inputs + cached complete bars |
| `btcusdt_quant/sim/strategies/legacy.py` | K01–K05, B1–B3 |
| `btcusdt_quant/sim/strategies/volatility.py` | K06–K09 |
| `btcusdt_quant/sim/strategies/grid.py` | K10 grid signals + its own unit-fraction simulator |
| `btcusdt_quant/sim/strategies/trend.py` | K11–K14 |
| `btcusdt_quant/sim/strategies/reversion.py` | K15–K17 |
| `btcusdt_quant/sim/strategies/futures.py` | K18–K24 |
| `scripts/sim_strategy_rolling.py` | Runner: all combos, windows, baseline ②, outputs |
| `tests/sim/test_engine_v2.py`, `test_regime_rolling.py`, `test_strategies_*.py`, `test_strategy_runner.py` | Tests |

---

### Task 1: Engine semantics needed by the catalog

**Files:**
- Modify: `btcusdt_quant/sim/schema.py`, `btcusdt_quant/sim/reference.py`, `btcusdt_quant/sim/core.py`, `scripts/sim_c1x_parity.py` (no behaviour change; re-run only)
- Test: `tests/sim/test_engine_v2.py`

**Interfaces:**
- Consumes: Plan 1 `schema.validate`, `reference.simulate`, `core.simulate`, `SimConfig`.
- Produces (both simulators, identical):
  1. `schema.validate` accepts several rows per `decision_time` when their `component` values differ; rows keep input order within a decision (that order is the priority). Duplicate (`decision_time`, `component`) raises `ValueError("duplicate decision")`.
  2. At one execution minute: first every row's exit check (reverse / flag), then every row's entry in order. A row acts on a held position only if `row.component == pos.component` (reverse, flags, and the DETEXIT add-on).
  3. `max_hold_min <= 0` means no max hold.
  4. NATIVE with finite `stop_bps`: fixed stop at `entry_avg·exp(−side·stop_bps/1e4)`, no take, no breakeven (K14 opposite edge, K10 not via this path).
  5. DETEXIT aligned to R2-46: levels `avg·exp(∓side·E/1e4)` (stop `−`, take `+`); `avg` is the harmonic unit average `Σu / Σ(u/price)`; touches are checked in the entry minute (and after an add-on, with the new levels); after a take, a breakeven touch in the same minute fills at `avg` (not the open).

- [ ] **Step 1: Write failing tests** in `tests/sim/test_engine_v2.py`, each parametrized over `[reference.simulate, core.simulate]` (reuse `flat_minutes`, `T0` from `tests/sim/test_reference.py`):
  - `test_multi_row_exits_before_entries`: rows at T+15 = (component 3 "F3", side −1) held from T+0 long via component 3; at T+30 two rows: (component 1 "A2", side +1) then (component 3, side −1) with `reentry="stop_and_reverse"` → trades: first long closes at T+31 reason `reverse`; new position side +1 component 1 entered at T+31.
  - `test_duplicate_decision_component_rejected`: two rows same T same component → `ValueError("duplicate decision")`.
  - `test_flag_only_from_same_component`: long held by component 2; row component 1 with `exit_long=True` → no exit; row component 2 `exit_long=True` → exit reason `flag`.
  - `test_no_max_hold_when_zero`: `max_hold_min=0`, flat prices, 600 minutes → no trade closes (`trades` empty, minute ledger = −2.0 entry fee).
  - `test_native_fixed_stop`: NATIVE, `stop_bps=100`, low at minute 40 = 98.0 → exit `stop` at `100·exp(−0.01)`.
  - `test_detexit_exp_levels_and_harmonic_avg`: legs at 100 and 110 (0.5 each) → avg = `1/(0.5/100+0.5/110)` = 104.7619…; stop level `avg·exp(−E/1e4)` asserted from the trade's exit price after a forced touch.
  - `test_detexit_checks_entry_minute`: entry minute 16 has low 90 with E=300 → exit `stop` at minute 16.
  - `test_detexit_same_minute_breakeven_after_take`: one bar with high ≥ take and low ≤ avg after entry → reasons `["take", "breakeven"]` both in that minute, breakeven exit price == avg.
- [ ] **Step 2: Run** `venv_btcusdt\Scripts\python.exe -m pytest tests/sim/test_engine_v2.py -q -p no:cacheprovider` → FAIL.
- [ ] **Step 3: Implement** in `reference.py` first (keep it the obvious oracle), then mirror in `core.py`. In `core`, pass decisions as rows sorted by (exec minute, input order) with `exec_start[i]`/`exec_end[i]` index ranges per minute instead of a single `exec_row`.
- [ ] **Step 4: Run** `pytest tests/sim -q -m "not slow"` → all pass, including the 85 differential cases; extend `random_case` with a second component on 20 % of rows and keep the differential test green. Run `pytest tests/sim/test_c1x_parity.py -m slow` → still passed (C1_X uses no DETEXIT, distinct components).
- [ ] **Step 5:** Re-run `scripts/sim_mutation.py`; ledger the scores; add a test for every non-equivalent survivor in the changed lines.

---

### Task 2: Regime, E lookup, gates, rolling schedule

**Files:**
- Create: `btcusdt_quant/sim/regime.py`, `btcusdt_quant/sim/rolling.py`
- Test: `tests/sim/test_regime_rolling.py`

**Interfaces:**
- Consumes: `data.load_predictions()`, `data.TARGETS`.
- Produces:
  - `regime.causal_percentile(values: ndarray, times: DatetimeIndex, days=30, minimum_days=7) -> ndarray` — share of strictly earlier values within the last 30 days that are ≤ current (R2-45 `causal_percentile`, `bisect_right / len`); NaN until 7 days × 96 earlier values exist.
  - `regime.load_regime(predictions) -> DataFrame[timestamp, M, L, prediction_<target>…]` — M = mean of the 9 percentiles {range, rv, exc} × {30m, 1h, 4h}; L = mean of {range, rv, exc} × {12h, 24h}; `skipna=False`.
  - `regime.e_bps(regime_frame, decisions: DatetimeIndex, head: str) -> ndarray` — `prediction_exc_<head>` at the exact decision timestamp, else the latest earlier one if ≤ 24 h old, else NaN (R2-46 `annotate_entries`).
  - `regime.GATES = {"HIGH": lambda M: M >= 2/3, "LOW": lambda M: M <= 1/3}`; `regime.gate_mask(regime_frame, decisions, gate) -> ndarray[bool]` (NaN M → False).
  - `rolling.WINDOWS: list[Window]`, `Window(name, train_start, train_end, val_start, val_end, test_start, test_end)`: train starts 2022-03-01 (expanding); `val_start = test_start − 3 months`, `val_end = test_start`, `train_end = val_start − 1 day` (the 1-day gap before validation); test windows `[2023-09-01, 2023-12-01)`, then every 3 months, the last `[2025-12-01, 2026-01-01)` (10 windows; spec says "about 11"; ending at 2026-01-01 keeps 2026H1 unseen).
- [ ] **Step 1: Tests**: `test_causal_percentile_excludes_current_and_needs_7_days` (constant series → first finite value at index 7·96 equals 1.0; value at T never counts itself); `test_e_lookup_exact_then_prior_24h` (exact hit; 1 h old prior; 25 h old → NaN); `test_gate_missing_blocks_entry_only` (with `strategies.apply_gate`, Task 3: NaN M row gets `allow_entry=False`, its `exit_*` flags unchanged); `test_windows_schedule` (10 windows; first test 2023-09-01; last test end 2026-01-01; every `train_end < val_start`; `val_end == test_start`; no window touches 2026-01-01 or later).
- [ ] **Step 2–4:** FAIL → implement → PASS. Smoke: `load_regime(data.load_predictions())` → print share of NaN M by segment; ledger it.

---

### Task 3: Strategy framework and K01–K05, B1–B3

**Files:**
- Create: `btcusdt_quant/sim/strategies/__init__.py`, `context.py`, `legacy.py`
- Modify: `scripts/sim_c1x_parity.py` (import `legacy.k01_c1x` instead of its local builder)
- Test: `tests/sim/test_strategies_legacy.py`, `tests/sim/test_strategies_common.py`

**Interfaces:**
- Produces:
  - `context.Context` (frozen dataclass): `minutes`, `metrics`, `premium`, `funding` (settlements `time, rate`), `regime` (Task 2), `end: Timestamp` (exclusive, default 2026-01-01); `Context.bars(minutes_per_bar) -> DataFrame` cached `bars.aggregate`; `Context.load(end=...)` classmethod builds all from `data`/`costs`/`regime`; `Context.truncate(t) -> Context` (inputs restricted to what is available before `t`, for look-ahead tests).
  - `strategies.Spec(id: str, family: str, cadence_min: int, hold_min: int, e_head: str, gate: str | None, build: Callable[[Context], DataFrame])` — `gate` is `"HIGH"`, `"LOW"` or `None` (K01); `build` returns a schema table with `component` set, **one row per cadence time** (side 0 rows included, so DETEXIT's add-on sees the very next decision).
  - `strategies.CATALOG: dict[str, Spec]` — ids: `K01, K02, K03, K04, K05, K06_k0.5, K06_k1.0, K07_k0.5, K07_k1.0, K08, K09, K10, K11_15m, K11_1h, K12_30m, K12_1h, K13, K14, K15, K16, K17_N5, K17_N7, K18, K19, K20_A, K20_B, K21_A, K21_B, K22, K23, K24, B1, B2, B3` (34 entries).
  - `strategies.apply_gate(table, ctx, gate) -> table` (sets `allow_entry &= gate_mask`; `None` → unchanged).
  - `strategies.apply_exit(table, ctx, spec, style) -> table`: NATIVE keeps table; DETEXIT sets `stop_bps = take_bps = regime.e_bps(…, spec.e_head)` per row and `allow_entry &= isfinite(E) & E > 0`.
  - `strategies.build_variant(ctx, spec_id, gate: bool, style) -> (table, SimConfig)` — `reentry="stop_and_reverse"` for K01 and `"strict"` otherwise; `exit_style=style`.
- Definitions (copy exactly):
  - K01: R2-39 C1_X (hourly; F3 24 h, E1 20 h; component reverse; `scripts/sim_c1x_parity.c1x_signals` moves here). Gate none, both exits; E head `24h`.
  - K02 F3-30, K03 F3W-30, K04 E1-15, K05 A2-30: R2-45 `build_fast_signals` exactly (F3-30/F3W-30 levels from R2-39 hourly rolling quantiles merged backward onto 30 m decisions, current `global_ls` asof `create_time+5min`; holds F3-30 4 h, F3W-30 12 h, E1-15 5 h; A2-30 has no max hold and exits on `a2_exit_long/short` flags; F3 components reverse on opposite signal). E heads from R2-46 `E_COLUMN` (F3-30 4h, F3W-30 12h, E1-15 4h, A2-30 4h). Gates: K04, K05 HIGH; K02, K03 LOW.
  - B1 `B1_FAST_NONE`, B2 `B2_HIGH_ONLY`, B3 `B3_FIXED_ROUTE`: R2-45 `simulate_fast` priority `(A2-30, E1-15, F3-30, F3W-30)` on the 15 m grid, expressed as four rows per decision in priority order; B2 sets `allow_entry` only where M ≥ 2/3; B3 allows A2/E1 rows where M ≥ 2/3 and F3 rows where M ≤ 1/3 and L < 2/3 (nothing else). B1–B3 have no extra gate axis (gate variant = NONE only). `reentry="strict"` (R2-47 revision 2, item 1).
- [ ] **Step 1: Tests**: `test_k01_matches_parity_script` (K01 table equals the table that produced `out/sim_parity_20261007/c1x_parity.json`; re-run parity → passed); `test_k02_k05_match_r245_signals` (on 2023-01-01..2023-03-01 real data, sides at each 15 m T equal R2-45 `build_fast_signals` columns, loaded by path); `test_b1_trade_list_vs_r245` (B1 under `strict` vs R2-45 `simulate_fast("B1_FAST_NONE")` on 2023 H1: every R2-45 trade not entered at a minute where R2-45 also exited is present with equal entry/exit/side; ledger the count of removed same-minute re-entries, as R2-47 revision 2 asks); `test_no_lookahead_all_strategies` (for every `CATALOG` id: table from `ctx.truncate(t)` equals the full table on decisions ≤ t for 3 random t in 2023; uses a 60-day context to stay fast); `test_one_row_per_cadence` (every id: decision times form a complete grid of `cadence_min` inside the context range, apart from composite rows).
- [ ] **Step 2–4:** FAIL → implement → PASS.

---

### Task 4: Volatility family K06–K09

**Files:** Create `btcusdt_quant/sim/strategies/volatility.py`; Test `tests/sim/test_strategies_volatility.py`

**Interfaces:** Consumes `Context`, `indicators.{bollinger, keltner, rsi}`, `regime.e_bps`. Produces builders registered in `CATALOG`.

Definitions (BRIEF §2; default hold 12 h unless stated; entry T+1 min):
- K06 VB (k ∈ {0.5, 1.0}), cadence 60: OCO at `close_T·exp(±k·range_1h/1e4)` (close of the 1 h bar ending at T stands in for the next hour's open), `expiry_min=60`, hold 240. Missing `range_1h` → no row entry (`allow_entry=False`). E head `1h`. Gate HIGH.
- K07 STRADDLE (k ∈ {0.5, 1.0}), cadence 15: OCO at `close_T·exp(±k·exc_1h/1e4)`, expiry 60, hold 240. E head `1h`. Gate HIGH.
- K08 SQUEEZE, cadence 15: BB(20,2) inside KC(20,1.5) for ≥ 6 consecutive bars, then the first bar where it is not → side = sign(close − BB middle). Native exit: flag when close crosses the opposite KC band (long: close < KC lower; short: close > KC upper), hold 480. E head `4h`. Gate HIGH.
- K09 LOWVOL_MR, cadence 15: long when close < BB lower and RSI(14) < 30; short when close > BB upper and RSI > 70. Exit flag when close crosses the BB middle; hold 240. E head `4h`. Gate LOW.
- [ ] **Step 1: Tests** with hand-built 15 m bars (constant then shaped): `test_k06_oco_levels` (close 100, range_1h 100 bps, k 0.5 → upper `100·exp(0.005)`, lower `100·exp(−0.005)`, expiry 60); `test_k07_levels_use_exc_1h`; `test_k08_needs_six_squeeze_bars` (5 squeeze bars then release → no signal; 6 → signal at release bar's decision time, side from close vs middle); `test_k09_requires_both_band_and_rsi`. Each test also asserts the real-data 2023 trade count > 0 or records `zero_reason` (spec §2.2 "실제 데이터 거래 수").
- [ ] **Step 2–4:** FAIL → implement → PASS.

---

### Task 5: K10 grid with its own unit-fraction simulator

**Files:** Create `btcusdt_quant/sim/strategies/grid.py`; Test `tests/sim/test_strategies_grid.py`

**Interfaces:**
- Consumes: `orders.fill_limit`, `orders.fill_stop`, `costs.fee_bps`, `costs.funding_bps`, `regime`.
- Produces: `grid.simulate_grid(ctx, start, end, gate: bool, config: SimConfig) -> SimResult` (same `TRADE_COLUMNS` and minute-ledger rules as `reference`: mark minute close to close, fees at fills, funding at exit; `sum(minute_pnl) == sum(net_bps)`).
- Rules: at each 15 m decision with no live grid (and gate passing if gated): base = close_T, `g = 0.5·range_1h` bps; buy limits at `base·exp(−j·g/1e4)` and sell limits at `base·exp(+j·g/1e4)`, j = 1..3, each 1/3 unit, active from T+1 min; each filled lot exits by limit one step in its favour (`fill·exp(±g/1e4)`); price through `base·exp(±4g/1e4)` closes every open lot at that stop (stop fill rule); window 4 h, then every open lot closes at the minute open and all orders cancel; next grid only at a decision after the previous ended. Limit fills need trade-through (Plan 1 `fill_limit`). DETEXIT is not defined for a grid: the runner records `zero_reason="DETEXIT not defined for GRID"` for those combinations.
- [ ] **Step 1: Tests**: `test_grid_fills_and_takes_one_step` (price path down one step then back up → one long lot of 1/3 unit, exit reason `take`, gross = g/3 bps, fee = 4/3 bps); `test_grid_stop_closes_all` (path through −4g → all filled lots exit `stop`); `test_grid_window_end_closes_at_open`; `test_grid_ledger_identity_random` (random walk, 10 seeds).
- [ ] **Step 2–4:** FAIL → implement → PASS.

---

### Task 6: Trend family K11–K14

**Files:** Create `btcusdt_quant/sim/strategies/trend.py`; Test `tests/sim/test_strategies_trend.py`

Definitions:
- K11 EMA_X, variants 15m and 1h (cadence = bar): EMA 9/21 cross up → +1, down → −1 on the bar the cross completes; exit = reverse on opposite cross (same component), hold 720. E head `4h`. Gate HIGH.
- K12 SUPERTREND(10,3), variants 30m and 1h: direction change → side = new direction, reverse on next change, hold 720. E head `4h` (30m) / `12h` (1h). Gate HIGH.
- K13 MTF_MOM, cadence 15: sign of last complete 15m, 1h and 4h bar returns all equal → that side; exit flag as soon as any of the three differs; hold 720. E head `4h`. Gate HIGH.
- K14 SESSION_ORB: sessions start 00:00, 07:00, 13:30 UTC; range = high/low of the first 30 minutes; at session start + 30 min one OCO row (upper = range high, lower = range low, `expiry_min=210` so the breakout window ends 4 h after session start); native stop = opposite edge, `stop_bps = log(high/low)·1e4` (NATIVE fixed stop from Task 1); `max_hold_min` = minutes until session start + 8 h measured from the OCO row's execution. E head `4h`. Gate HIGH.
- [ ] **Step 1: Tests**: `test_k11_cross_bar` (hand series crossing on bar k → signal at that bar's decision time only); `test_k12_reverses_on_flip`; `test_k13_exit_when_any_timeframe_disagrees`; `test_k14_range_and_expiry` (07:00 session → OCO row at 07:30 with expiry 210 and stop_bps = log(h/l)·1e4).
- [ ] **Step 2–4:** FAIL → implement → PASS.

---

### Task 7: Reversion K15–K17 and futures-data K18–K24

**Files:** Create `btcusdt_quant/sim/strategies/reversion.py`, `futures.py`; Test `tests/sim/test_strategies_reversion_futures.py`

Definitions (all z-scores from strictly earlier values: `indicators.zscore_past`; "30 days" on a 15 m grid = 2880 bars, on 1 h = 720; min periods = half):
- K15 VWAP_MR, cadence 15: deviation d = close/VWAP_utc − 1; z of d over prior 30 days; z > 2 → −1, z < −2 → +1; exit flag when close crosses VWAP; hold 240. E `4h`. Gate LOW.
- K16 WICK_REV, cadence 5: BRIEF's "close inside the body" is always true, so it is read as "the opposite wick < ATR": lower wick > 3·ATR(14, 5m) and upper wick < ATR → +1; upper wick > 3·ATR and lower wick < ATR → −1; hold 60. E `1h`. Gate LOW.
- K17 STREAK_REV (N ∈ {5, 7}), cadence 15: N consecutive same-colour bars (close > open, or close < open) → opposite side; hold 120. E `1h`. Gate LOW.
- K18 FUNDING_EXT, decision at the first 15 m grid time strictly after each settlement: rate above the prior-90-day (270 settlements, exclusive) 95 % quantile → −1, below 5 % → +1; hold 480. E `12h`. Gate HIGH.
- K19 PREMIUM_MR, cadence 60: z of the 1 h mean premium (bars complete, available after `close_time`) over prior 30 days; > 2 → −1, < −2 → +1; hold 240. E `4h`. Gate LOW.
- K20 OI_PRICE, cadence 60, OI change = log(oi_T / oi_{T−1h}) from metrics asof; z over 30 days. Variant A: z > 2 & 1 h return > 0 → +1, z > 2 & return < 0 → −1. Variant B: z < −2 & return < 0 → +1, z < −2 & return > 0 → −1. Hold 240. E `4h`. Gate HIGH.
- K21 TAKER_IMB, cadence 15: taker buy share = taker_buy/volume of the 15 m bar; z over 30 days. A: z > 2 → +1, z < −2 → −1. B: opposite. Hold 120. E `1h`. Gate HIGH.
- K22 CVD_DIV, cadence 15: CVD = cumulative Σ(2·taker_buy − volume) from the context start; close makes a new 20-bar high (close > max of prior 20 closes) while CVD < CVD at the bar of the prior 20-bar closing high → −1; mirror for lows → +1. Hold 240. E `4h`. Gate HIGH.
- K23 TOPTRADER_LS, cadence 60: `top_ls` asof T; rolling 30-day (720 h) q10/q90 including current like R2-39 F3; ≥ q90 → −1, ≤ q10 → +1; hold 240; reverse on opposite. E `4h`. Gate LOW.
- K24 TAKER_LSR, cadence 15: `taker_lsr` asof T; z over 30 days > 2 → +1, < −2 → −1; hold 120. E `1h`. Gate HIGH.
- [ ] **Step 1: Tests**, one per id with a hand-built frame that crosses the threshold once and asserts side and decision time; plus `test_k18_uses_only_prior_settlements` (current settlement excluded from its own quantile) and `test_k22_cvd_divergence`.
- [ ] **Step 2–4:** FAIL → implement → PASS.

---

### Task 8: Rolling runner and baseline ②

**Files:**
- Create: `scripts/sim_strategy_rolling.py`
- Test: `tests/sim/test_strategy_runner.py`

**Interfaces:**
- Consumes: `CATALOG`, `build_variant`, `grid.simulate_grid`, `core.simulate`, `rolling.WINDOWS`, `analytics`, `guard`, `registry`, `provenance`.
- Produces in `out/k45_rl_r2_48_20261007/strategies/`:
  - `manifest.json`: source, timestamp, data cutoff 2025-12-31, input hashes (`provenance.tree_sha256` for metrics/premium/funding/predictions, `file_sha256` market), catalog ids, combination list and count, frozen hypothesis text from spec §8, code sha256 of `btcusdt_quant/sim/**/*.py`.
  - `combos.parquet`: one row per combination `(id, gate ∈ {NONE, GATED}, exit ∈ {NATIVE, DETEXIT})` (K01 and B1–B3: gate NONE only) with status.
  - `trades/<combo>.parquet`, `daily/<combo>.parquet` (daily net bps at 4 bps, from the minute ledger, 2022-03-01..2025-12-31).
  - `windows.parquet`: per combination × window × part ∈ {val, test}: trades, long/short counts, net at 0/4/8/12 bps (`net_c = net_4 − (c−4)/2·Σ(2·units)`), top-2-removed net, max drawdown, `zero_reason`.
  - `baseline2.parquet`: per test window the combination with the highest validation net at 4 bps (ties → lowest id string) and its test-window daily net; plus the concatenated 2023-09..2025-12 daily series.
  - `summary.json`: per combination over the concatenated test windows: net 4/8 bps, PW mean CI, HAC CI, DSR with `n_trials = registry.cumulative_trials(base=5125) + combination count`, real trade count and 10 sample trades (spec §2.2).
  - `registry.record(out/sim_registry.jsonl, …)` once with `n_trials` = combination count.
- Behaviour: simulate each combination once over minutes 2022-03-01..2026-01-01 (signals use the 2020 warm-up), funding PESS, delay 1; ≤ 8 worker processes; `guard.check` on the summary before writing; a combination that raises is recorded with `status="error"` and the message, and the run continues.
- [ ] **Step 1: Tests**: `test_baseline2_picks_previous_validation_best` (synthetic daily frames for 3 combos over 2 windows → chosen ids and concatenated series exact); `test_zero_trade_window_has_reason` (a combo with no trades yields rows with net 0 and `zero_reason="no trades in window"`; `guard.check` passes; removing the reason makes it raise); `test_cost_rescaling_matches_resimulation` (one small real combo: net at 8 bps from rescaling equals `core.simulate` with `fee_per_side=4.0` within 1e-9); `test_runner_smoke` (`--ids K04 K09 --end 2022-06-01` writes all files; manifest lists 4+4 combos).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Full run** `venv_btcusdt\Scripts\python.exe scripts/sim_strategy_rolling.py` in the background; log to `out/k45_rl_r2_48_20261007/strategies/run.log`. Expected: every combination has status `ok` or a recorded reason; ledger the combination count, runtime, the baseline ② ids per window and its concatenated test net. Report all results unfiltered.

---

## Self-Review Notes

- Spec §3 catalog K01–K24 + B1–B3 (T3–T7), gate NONE/fixed and NATIVE/DETEXIT (T3 `build_variant`, T8 combos), rolling per §5 (T2 `rolling`), baseline ② (T8), keep all results (T8 status + guard). §2.1 position fractions (T5 grid, DETEXIT halves), fills/orders (T1, T5). §2.2 hand-built signal checks and real trade counts with 10 samples (T3–T7 tests, T8 summary).
- Plan 1 engine gaps found while mapping the catalog are all in Task 1: multi-component decisions (B1–B3), component-scoped flags (A2 exits inside composites), no-max-hold (A2), NATIVE fixed stop (K14), R2-46 DETEXIT details (exp levels, harmonic average, entry-minute touch, same-minute breakeven).
- Ten test windows instead of the spec's "about 11": the spec's own range 2023-09..2025-12 in 3-month steps gives 9 full windows plus December 2025; nothing in 2026 is opened.
