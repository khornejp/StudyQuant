# PatchTST Gate + CatBoost Direction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Project rule:** Codex implements each task (`codex exec` + stdin), Claude reviews, then runs or returns. **User instruction (2026-10-01): run every stage start to end and report every result as-is. A failed gate is recorded, never used to stop or to filter what is reported.**

**Goal:** On bars where the PatchTST volatility gate fires, estimate P(LONG) and P(SHORT) with CatBoost and trade the more probable side, then measure whether that beats the 4 bps round trip on both sides.

**Architecture:** Two stages. Stage A (existing, frozen): PatchTST `passes_q90` picks the bars. Stage B (new): a walk-forward CatBoost MultiClass model, refit every 3-day fold on an expanding window with in-window feature selection, outputs class probabilities. Four measurement steps follow, each run regardless of the previous result: information precheck, probability quality, one backtest, HOLD-B.

**Tech Stack:** Python 3.14 (`venv_btcusdt`), numpy, pandas, catboost 1.2.10, pytest. Reuses `out/run_patchtst_k45_flow_inference.py` (`mean_influence`, `pw_inference`, `critical_count`, `binomial_tail`), `out/k45_trend_side.py` (`admit`, `net_bps`, `trend_sign`, `trim_top`), `out/k45_defect_audit_20260930/run_audit.py` (gate-file assembly, `test_bounds`).

**Spec:** this plan is its own design record (the user approved the structure in chat on 2026-10-01). Background: `docs/superpowers/specs/2026-10-01-trend-conditioned-side-design.md` §9, `out/k45_trend_side_20261001/REPORT.md`, `out/k45_trend_side_tp_20261001/REPORT.md`.

## Global Constraints

- Round-trip cost `COST = 4.0` bps, fixed. Limit-only; every leg maker.
- Binance USD-M BTCUSDT futures only. **Existing local data only. No downloads.**
- Market: `artifacts/btcusdt_2020_2026h1.parquet` (cutoff 2026-06-30 23:59 UTC).
- Extra local inputs allowed: `artifacts/{book,liquidity,spread,trade}_features_1m.parquet`, funding under `artifacts/funding_2020_2026h1`.
- No `--feature-cache`. `live_orders: 0`. No new PatchTST fits.
- Segments: `DEV = pilot_fold <= 605`, `HOLD_B = pilot_fold >= 606` (HOLD-B already seen; label exploratory).
- Horizon `H = 45` minutes. Decision at the close of origin bar `t`; entry `close[t]`, exit `close[t+45]`.
- Label: `r = 1e4*(close[t+45]/close[t]-1)`; `LONG` if `r > 4`, `SHORT` if `r < -4`, else `NONE`. Class codes `0=SHORT, 1=NONE, 2=LONG`.
- Origin kept only if `t + 45 < test_end_index` of its fold (same boundary as the audit).
- CatBoost params fixed, no tuning: `loss_function="MultiClass", iterations=500, depth=4, learning_rate=0.05, l2_leaf_reg=3, random_seed=20261001, thread_count=-1, verbose=False`.
- Every output directory: `out/k45_gate_direction_20261001/`. Every artifact gets SHA256 in `manifest.json`, plus run time, data cutoff, frozen hypothesis.
- Frozen hypothesis: "PatchTST 게이트 바에서 CatBoost가 고른 더 확률 높은 방향으로 거래하면, 롱과 숏 모두 net이 0보다 크다."

## Review Focus

1. Feature leakage through the label window: a feature computed after `close[t]` (for example a forward-filled 1m microstructure row stamped at `t+1`) must be impossible; join microstructure on `open_time == open_time[t]` only.
2. Training rows whose label window reaches into the fold's STOP or TEST span: purge every training origin with `t + 45 >= stop_start_index`.
3. In-window feature selection must use training rows only; a selection that reads TEST labels makes every later number invalid.
4. A fold with zero gated TEST rows: skip with a logged row, never crash, never fabricate predictions.
5. A class absent from a training window (for example no `NONE`): probabilities must still come out as three columns in fixed order `SHORT, NONE, LONG`.

---

### Task 1: Gated-bar dataset

**Files:**
- Create: `out/k45_gate_direction.py` (pure functions shared by all tasks)
- Create: `out/run_k45_gate_direction_dataset.py`
- Test: `tests/test_k45_gate_direction.py`

**Interfaces:**
- Produces:
  - `H = 45`, `COST = 4.0`, `CLASSES = ("SHORT", "NONE", "LONG")`
  - `label_45(close: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]` returns `(r_bps float, cls int8 in {0,1,2})`
  - Output `out/k45_gate_direction_20261001/dataset.parquet` with columns: `pilot_fold, signal_index, open_time, test_end_index, r45_bps, cls, trend_30d, trend_7d, ret_30d_bps, ret_7d_bps,` every registry feature column (prefix `f_`), every microstructure column (prefix `m_`).

- [ ] **Step 1: Failing tests**

```python
import numpy as np
import pandas as pd
import pytest

from out import k45_gate_direction as gd


def test_label_45_thresholds_are_strict():
    close = np.full(200, 100.0)
    close[45] = 100.0399        # +3.99 bps -> NONE
    close[46] = 100.0401        # > +4 -> LONG
    close[47] = 99.9599         # < -4 -> SHORT
    r, cls = gd.label_45(close, np.array([0, 1, 2]))
    assert cls.tolist() == [1, 2, 0]
    assert r[0] == pytest.approx(3.99)


def test_label_45_refuses_out_of_range():
    with pytest.raises(IndexError):
        gd.label_45(np.ones(50), np.array([10]))
```

- [ ] **Step 2: Run** `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_gate_direction.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement in `out/k45_gate_direction.py`**

```python
"""PatchTST gate + CatBoost direction: shared pure functions."""
from __future__ import annotations

import numpy as np

H = 45
COST = 4.0
CLASSES = ("SHORT", "NONE", "LONG")


def label_45(close: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    close = np.asarray(close, float)
    t = np.asarray(t, np.int64)
    if ((t < 0) | (t + H >= len(close))).any():
        raise IndexError("label window exceeds market array")
    r = 1e4 * (close[t + H] / close[t] - 1)
    cls = np.where(r > COST, 2, np.where(r < -COST, 0, 1)).astype(np.int8)
    return r, cls
```

- [ ] **Step 4: Run tests → PASS.**

- [ ] **Step 5: Dataset runner `out/run_k45_gate_direction_dataset.py`**
  1. Gate origins: reproduce filter B of `out/k45_defect_audit_20260930/run_audit.py` (the three prediction sources merged, `passes_q90 == True`, folds 0–666). Folds 406–605 carry no `passes_q90` in `out/patchtst_excursion_range_20260928/ensemble_predictions.parquet`; take it from the same source run_audit uses for that range. Assert the merged gated count equals run_audit's B count before the `signal_index+45<test_end` cut, and record both counts.
  2. `test_end_index` from `run_audit.test_bounds(fold)` mapped to market indices. Keep `signal_index + 45 < test_end_index`.
  3. Labels via `label_45`.
  4. Trend: `trend_30d = trend_sign(close, t, 43200)`, `trend_7d = trend_sign(close, t, 10080)`; `ret_30d_bps`, `ret_7d_bps` as signed log-return bps (NaN without history).
  5. Registry features: build with `btcusdt_quant.dataset.build_feature_rows` (no cache; follow the interning fix in that module) for the full market, then take rows at `signal_index`. Prefix `f_`. Record registry schema hash. If the full build exceeds available memory, build in contiguous chunks with enough warm-up history for the longest lookback in the registry, and assert chunk-boundary rows equal a full build on one 10-day overlap window.
  6. Microstructure: join the four `artifacts/*_features_1m.parquet` files on `open_time == open_time[t]` exactly (no forward fill). Prefix `m_`. Keep their `*_valid` flags as features.
  7. Write `dataset.parquet`, and `dataset_manifest.json` with counts per segment, class shares per segment, missing-share per feature, input SHA256.

Add tests:

```python
def test_microstructure_join_is_exact_time_only():
    bars = pd.DataFrame({"open_time": pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")})
    micro = pd.DataFrame({"open_time": bars.open_time.iloc[[0, 2]], "x": [1.0, 3.0]})
    from out import run_k45_gate_direction_dataset as ds
    got = ds.join_exact(bars.iloc[[1]], micro, prefix="m_")
    assert np.isnan(got["m_x"].iloc[0])
```

(`join_exact(rows: DataFrame, micro: DataFrame, prefix: str) -> DataFrame` is a left merge on `open_time`, columns other than `open_time` renamed with `prefix`.)

- [ ] **Step 6: Run tests → PASS. Run the dataset runner (background + monitor). Claude reviews the manifest: segment counts, class shares, feature missing shares.**
- [ ] **Step 7: Commit tests** (`out/` is git-ignored; the runner and module stay local, as with prior runs).

---

### Task 2: Stage 0 — information precheck (diagnostic only)

**Files:**
- Modify: `out/k45_gate_direction.py` (append)
- Create: `out/run_k45_gate_direction_precheck.py`
- Test: `tests/test_k45_gate_direction.py` (append)

**Interfaces:**
- Produces: `monthly_sign_test(x: np.ndarray, r: np.ndarray, month: np.ndarray, min_rows: int = 30) -> dict` with keys `pooled_spearman`, `n_months`, `agree_months`, `p_one_sided`.
  Months with fewer than `min_rows` rows or zero variance are dropped. `agree_months` counts months whose Spearman sign equals the pooled sign. `p_one_sided = flow.binomial_tail(n_months, agree_months)`.

- [ ] **Step 1: Failing tests**

```python
def test_monthly_sign_test_detects_consistent_relation():
    rng = np.random.default_rng(0)
    month = np.repeat(np.arange(24), 100)
    x = rng.normal(size=len(month))
    r = x + rng.normal(size=len(month))
    got = gd.monthly_sign_test(x, r, month)
    assert got["agree_months"] == 24 and got["p_one_sided"] < 1e-6


def test_monthly_sign_test_drops_thin_and_constant_months():
    month = np.array([0] * 10 + [1] * 50)
    x = np.r_[np.arange(10.), np.zeros(50)]
    got = gd.monthly_sign_test(x, np.arange(60.), month)
    assert got["n_months"] == 0
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
from scipy.stats import spearmanr

from out import run_patchtst_k45_flow_inference as flow


def monthly_sign_test(x, r, month, min_rows: int = 30) -> dict:
    x, r, month = np.asarray(x, float), np.asarray(r, float), np.asarray(month)
    ok = np.isfinite(x) & np.isfinite(r)
    pooled = float(spearmanr(x[ok], r[ok]).statistic) if ok.sum() > 2 and np.ptp(x[ok]) > 0 else float("nan")
    signs = []
    for m in np.unique(month[ok]):
        sel = ok & (month == m)
        if sel.sum() < min_rows or np.ptp(x[sel]) == 0 or np.ptp(r[sel]) == 0:
            continue
        signs.append(np.sign(spearmanr(x[sel], r[sel]).statistic))
    n = len(signs)
    agree = int(sum(s == np.sign(pooled) for s in signs)) if n and np.isfinite(pooled) else 0
    p = flow.binomial_tail(n, agree) if n else float("nan")
    return {"pooled_spearman": pooled, "n_months": n, "agree_months": agree, "p_one_sided": p}
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Runner.** On DEV rows, for every `f_*`, `m_*`, `trend_*`, `ret_*` column, run `monthly_sign_test` against three targets: signed `r45_bps`, `1[cls==LONG]`, `1[cls==SHORT]`. Bonferroni alpha `0.05 / (n_features * 3)`. Write `precheck.parquet` (one row per feature × target) and `precheck.json` with counts of features passing per target. Diagnostic only: Task 3 does not read it.
- [ ] **Step 6: Run, commit tests.**

---

### Task 3: Walk-forward CatBoost with in-window selection

**Files:**
- Modify: `out/k45_gate_direction.py` (append)
- Create: `out/run_k45_gate_direction_walkforward.py`
- Test: `tests/test_k45_gate_direction.py` (append)

**Interfaces:**
- Produces:
  - `select_features(train: pd.DataFrame, columns: list[str], month_col: str = "month", k_min: int = 5, k_fallback: int = 20) -> tuple[list[str], str]` — columns whose `monthly_sign_test` against `r45_bps` has `p_one_sided < 0.05/len(columns)`; if fewer than `k_min`, the `k_fallback` columns with the largest `|pooled_spearman|`; returns `(columns, "GATE" | "FALLBACK")`. Uses training rows only.
  - `predict_proba3(model, X) -> np.ndarray` shape `(n, 3)` ordered `SHORT, NONE, LONG`, filling zero for any class absent from training.
  - Output `predictions.parquet`: `pilot_fold, signal_index, open_time, r45_bps, cls, p_short, p_none, p_long, n_train, selection_mode, n_selected`; `selection.parquet`: fold × selected feature.

Walk-forward per fold `k` in 0..666:
- `stop_start_index` = market index of fold `k`'s STOP start (`test_start − 3 days`).
- Train rows: dataset rows with `signal_index + 45 < stop_start_index` (expanding; purge built in).
- Skip a fold when train has fewer than 1,000 rows or the fold has zero TEST rows; log a `skipped` row with the reason.
- Fit CatBoost with the fixed params on selected features; predict TEST rows of fold `k`.

- [ ] **Step 1: Failing tests**

```python
def test_predict_proba3_fills_missing_class():
    class Stub:
        classes_ = np.array([0, 2])
        def predict_proba(self, X):
            return np.tile([0.3, 0.7], (len(X), 1))
    p = gd.predict_proba3(Stub(), np.zeros((2, 1)))
    assert p.tolist() == [[0.3, 0.0, 0.7], [0.3, 0.0, 0.7]]


def test_select_features_uses_only_given_rows_and_falls_back():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({"month": np.repeat(np.arange(30), 100),
                       "a": rng.normal(size=n), "b": rng.normal(size=n)})
    df["r45_bps"] = rng.normal(size=n)
    cols, mode = gd.select_features(df, ["a", "b"], k_min=5, k_fallback=1)
    assert mode == "FALLBACK" and len(cols) == 1


def test_training_rows_are_purged_before_stop():
    from out import run_k45_gate_direction_walkforward as wf
    ds = pd.DataFrame({"signal_index": [100, 154, 155, 200]})
    assert wf.train_mask(ds, stop_start_index=200).tolist() == [True, True, False, False]
```

(`train_mask(ds, stop_start_index) = ds.signal_index + 45 < stop_start_index`.)

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
def predict_proba3(model, X) -> np.ndarray:
    raw = np.asarray(model.predict_proba(X), float)
    out = np.zeros((raw.shape[0], 3))
    for j, c in enumerate(np.asarray(model.classes_).astype(int)):
        out[:, c] = raw[:, j]
    return out


def select_features(train, columns, month_col="month", k_min=5, k_fallback=20):
    stats = {c: monthly_sign_test(train[c].to_numpy(float), train.r45_bps.to_numpy(float),
                                  train[month_col].to_numpy()) for c in columns}
    alpha = 0.05 / len(columns)
    passed = [c for c, s in stats.items() if s["p_one_sided"] < alpha]
    if len(passed) >= k_min:
        return passed, "GATE"
    ranked = sorted(columns, key=lambda c: -abs(np.nan_to_num(stats[c]["pooled_spearman"])))
    return ranked[:k_fallback], "FALLBACK"
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Runner** as described above; progress log per fold; write `predictions.parquet`, `selection.parquet`, `walkforward_manifest.json` (fold count fitted/skipped, selection-mode counts, param dict, SHA256).
- [ ] **Step 6: Run (background + monitor), commit tests.**

---

### Task 4: Probability quality

**Files:**
- Create: `out/run_k45_gate_direction_quality.py`
- Test: `tests/test_k45_gate_direction.py` (append)

**Interfaces:**
- Produces: `score = p_long − p_short`. `decile_table(score, r) -> DataFrame[decile, n, score_mean, r_mean, long_share, short_share]`; `calibration_table(p, hit, bins=10) -> DataFrame[bin, n, p_mean, hit_rate]`.

Per segment (DEV, HOLD_B):
- `monthly_sign_test(score, r45_bps, month)` — the ordering gate (pass if `p_one_sided < 0.05`).
- Decile table of `score` vs `r45_bps`.
- Calibration of `p_long` vs `cls==LONG` and `p_short` vs `cls==SHORT`.
- Pooled Spearman per side: `p_long` vs `r45` and `p_short` vs `−r45`.
- Write `quality.json`, `deciles.parquet`, `calibration.parquet`.

- [ ] **Step 1: Failing test**

```python
def test_decile_table_is_monotone_on_perfect_score():
    from out import run_k45_gate_direction_quality as q
    s = np.arange(1000.)
    t = q.decile_table(s, s)
    assert t.decile.tolist() == list(range(10))
    assert np.all(np.diff(t.r_mean) > 0)
```

- [ ] **Step 2–4: fail → implement (`pd.qcut(score, 10, labels=False, duplicates="drop")`) → pass.**
- [ ] **Step 5: Run on predictions, commit tests.**

---

### Task 5: One backtest + HOLD-B

**Files:**
- Create: `out/run_k45_gate_direction_backtest.py`
- Test: `tests/test_k45_gate_direction.py` (append)

**Interfaces:**
- Produces: `choose_side(p_long, p_short, margin: float) -> np.ndarray[int8]` (+1 long, −1 short, 0 none): long if `p_long − p_short > margin`, short if `p_short − p_long > margin`, else 0.

Rules (frozen):
- Primary `MARGIN = 0.10`. Report-only margins `(0.0, 0.05, 0.20)`.
- Trades enter at `close[t]`, exit `close[t+45]`, cost 4, single-position book via `k45_trend_side.admit`.
- Per segment and margin: n, net mean, trimmed top-2, daily PW CI (`flow.pw_inference`, greater), per-side n and net, monthly positive share, random-direction baseline on the same gated bars (side drawn ±1 with seed 20261001, same book).
- DEV gate (primary margin): book net > 0, PW CI lower > 0, **both** sides net > 0. HOLD-B gate: book net > 0. Both labelled; HOLD-B exploratory.
- Write `backtest.parquet`, `book_trades.parquet`, `gates.json`, `manifest.json`, `REPORT.md` (all stages summarized, every number as produced).

- [ ] **Step 1: Failing test**

```python
def test_choose_side_margin_is_strict():
    from out import run_k45_gate_direction_backtest as bt
    got = bt.choose_side(np.array([.50, .60, .30, .36]), np.array([.45, .45, .45, .45]), 0.10)
    assert got.tolist() == [0, 1, -1, 0]
```

(`.50−.45 = 0.05` → none; `.60` long by 0.15; `.30` short by 0.15; `.36` vs `.45` is 0.09 → none. Avoid exact-0.10 cases: float rounding makes them unstable.)

- [ ] **Step 2–4: fail → implement → pass.**
- [ ] **Step 5: Run, Claude writes the final summary to the user with every stage's numbers, commit tests, record in engram (`k45/gate-direction-catboost`).**

---

## Execution order (no early stop)

Task 1 → 2 → 3 → 4 → 5. Each task: Codex implements, Claude reviews the diff and runs tests, then runs the runner. A failed gate in Task 2, 4 or 5 is recorded and the next task still runs.
