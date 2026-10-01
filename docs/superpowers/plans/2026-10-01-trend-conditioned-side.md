# Trend-Conditioned Side + TP Exit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Project rule overrides the sub-skill choice:** Codex implements each task (`codex exec` + stdin), Claude reviews, then runs or returns.

> **2026-10-01 change: HOLD-A is withdrawn.** Project rule: existing local data only. Task 7, `holda_gate`, and Review Focus item 5 are void; do not implement them. Judging uses DEV and HOLD-B only, and HOLD-B results are labelled exploratory.

**Goal:** Test whether fading only in the direction of the 30-day trend makes both K=45 arms net-positive, then whether a fixed TP raises per-trade net, judged on DEV and HOLD-B.

**Architecture:** One pure-function module `out/k45_trend_side.py` holds the trend sign, side filter, PnL, TP exit, and gate logic. Two thin runners call it: stage 1 and stage 2. Candidates come from the frozen parquet. No new model fits.

**Tech Stack:** Python 3.14, numpy, pandas, pytest. Reuses `out/run_patchtst_k45_flow_inference.py` (`mean_influence`, `pw_inference`).

**Spec:** `docs/superpowers/specs/2026-10-01-trend-conditioned-side-design.md`

## Global Constraints

- Round-trip cost `COST = 4.0` bps, fixed.
- Limit-only; every leg is maker. TP fills at the TP price when touched.
- Binance USD-M BTCUSDT futures only. No spot, no DEX.
- `live_orders: 0`, `new_orders: 0`. No new model fits in this plan.
- Hold `HOLD = 45` minutes. Trigger, gate, and entry are unchanged.
- Single-position first-come book (`admit` semantics from `out/k45_defect_audit_20260930/run_audit.py:92-100`).
- Trend lookback `TREND_LOOKBACK = 43200` (primary). `7d = 10080` is report-only.
- Candidates: `out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet`.
- Market: `artifacts/btcusdt_2020_2026h1.parquet`. Do not use `--feature-cache`.
- Existing outputs are immutable. New outputs go to new directories.
- Gate thresholds are frozen and never lowered after seeing results.

## Review Focus

1. Trend lookback before data start (`signal_index < 43200`): expect no trade, never a wrapped negative index.
2. Trend exactly zero: expect no trade.
3. TP touched on the entry bar itself: expect no fill on that bar; the TP window starts at `entry + 1`.
4. TP and 45-minute exit on the same bar: expect a TP fill (the limit rests first).
5. HOLD-A index basis differs from the in-sample parquet: the judge must read the basis from the sealed manifest and fail loudly on mismatch.

Also: if Politis–White returns `UNMEASURABLE`, the CI is NaN and `dev_gate` must return `FAIL` (NaN > 0 is False). Task 2 pins it:

```python
def test_dev_gate_nan_ci_fails():
    assert ts.dev_gate(1.0, float("nan"), {ts.LONG: 1.0, ts.SHORT: 1.0})["status"] == "FAIL"
```

---

### Task 1: Core functions — trend, side filter, PnL

**Files:**
- Create: `out/k45_trend_side.py`
- Test: `tests/test_k45_trend_side.py`

**Interfaces:**
- Produces:
  - `LONG = "DOWN_BREAKOUT_LONG"`, `SHORT = "UP_BREAKOUT_SHORT"`, `COST = 4.0`, `HOLD = 45`, `TREND_LOOKBACK = 43200`
  - `trend_sign(close: np.ndarray, signal_index: np.ndarray, lookback: int) -> np.ndarray[int8]` (values −1, 0, +1; 0 when there is not enough history)
  - `side_mask(arm: np.ndarray, trend: np.ndarray) -> np.ndarray[bool]`
  - `net_bps(close: np.ndarray, entry: np.ndarray, exit_: np.ndarray, position: np.ndarray) -> np.ndarray[float]`
  - `admit(entries: np.ndarray, hold: int = HOLD) -> np.ndarray[bool]`

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest

from out import k45_trend_side as ts


def test_trend_sign_is_causal_and_zero_without_history():
    close = np.array([100., 101., 99., 99., 102.])
    got = ts.trend_sign(close, np.array([0, 1, 2, 3, 4]), lookback=2)
    assert got.tolist() == [0, 0, -1, -1, 1]


def test_trend_sign_zero_when_flat():
    close = np.array([100., 100., 100.])
    assert ts.trend_sign(close, np.array([2]), lookback=2).tolist() == [0]


def test_side_mask_takes_long_in_uptrend_short_in_downtrend_nothing_flat():
    arm = np.array([ts.LONG, ts.SHORT, ts.LONG, ts.SHORT, ts.LONG])
    trend = np.array([1, 1, -1, -1, 0], dtype=np.int8)
    assert ts.side_mask(arm, trend).tolist() == [True, False, False, True, False]


def test_net_bps_signs_and_cost():
    close = np.array([100., 101., 100.])
    got = ts.net_bps(close, np.array([0, 1]), np.array([1, 2]), np.array([1., -1.]))
    assert got == pytest.approx([96.0, 1e4 * (1 - 100 / 101) - 4])


def test_admit_blocks_overlap_and_frees_at_hold():
    assert ts.admit(np.array([10, 20, 55, 56]), hold=45).tolist() == [True, False, True, False]
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_k45_trend_side.py -v`
Expected: FAIL with `ImportError` / `ModuleNotFoundError: out.k45_trend_side`

- [ ] **Step 3: Implement**

```python
"""Trend-conditioned side filter for the K=45 breakout fade.

Spec: docs/superpowers/specs/2026-10-01-trend-conditioned-side-design.md
"""
from __future__ import annotations

import numpy as np

LONG = "DOWN_BREAKOUT_LONG"
SHORT = "UP_BREAKOUT_SHORT"
COST = 4.0
HOLD = 45
TREND_LOOKBACK = 43_200
TREND_LOOKBACK_REPORT = 10_080


def trend_sign(close: np.ndarray, signal_index: np.ndarray, lookback: int) -> np.ndarray:
    close = np.asarray(close, float)
    s = np.asarray(signal_index, np.int64)
    out = np.zeros(len(s), np.int8)
    ok = s >= lookback
    out[ok] = np.sign(np.log(close[s[ok]] / close[s[ok] - lookback])).astype(np.int8)
    return out


def side_mask(arm: np.ndarray, trend: np.ndarray) -> np.ndarray:
    arm = np.asarray(arm)
    trend = np.asarray(trend)
    return ((arm == LONG) & (trend == 1)) | ((arm == SHORT) & (trend == -1))


def net_bps(close: np.ndarray, entry: np.ndarray, exit_: np.ndarray,
            position: np.ndarray) -> np.ndarray:
    close = np.asarray(close, float)
    gross = 1e4 * (close[np.asarray(exit_, np.int64)] / close[np.asarray(entry, np.int64)] - 1)
    return np.asarray(position, float) * gross - COST


def admit(entries: np.ndarray, hold: int = HOLD) -> np.ndarray:
    entries = np.asarray(entries, np.int64)
    accepted = np.zeros(len(entries), bool)
    busy_until = -1
    for i in np.argsort(entries, kind="stable"):
        if int(entries[i]) >= busy_until:
            accepted[i] = True
            busy_until = int(entries[i]) + hold
    return accepted
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_k45_trend_side.py -v`
Expected: 5 PASS

- [ ] **Step 5: Reproduce the frozen baseline with these functions (guard)**

Add to the test file:

```python
import pandas as pd
from pathlib import Path

CAND = Path("out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet")
MARKET = Path("artifacts/btcusdt_2020_2026h1.parquet")


@pytest.mark.skipif(not CAND.exists() or not MARKET.exists(), reason="frozen data absent")
def test_reproduces_long_only_0455():
    d = pd.read_parquet(CAND)
    close = pd.read_parquet(MARKET, columns=["close"])["close"].to_numpy(float)
    ex = d[(d.arm == ts.LONG) & d.first_come_executed]
    r = ts.net_bps(close, ex.entry_index, ex.scheduled_exit_index, np.ones(len(ex)))
    assert len(ex) == 3066
    assert r.mean() == pytest.approx(0.4550, abs=5e-5)
```

Run: `python -m pytest tests/test_k45_trend_side.py -v` → 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add out/k45_trend_side.py tests/test_k45_trend_side.py
git commit -m "feat: trend sign, side filter and PnL core for the K=45 trend-side test"
```

---

### Task 2: Gate evaluator

**Files:**
- Modify: `out/k45_trend_side.py` (append)
- Test: `tests/test_k45_trend_side.py` (append)

**Interfaces:**
- Consumes: `LONG`, `SHORT` from Task 1.
- Produces:
  - `dev_gate(book_mean: float, ci_lower: float, cell_means: dict[str, float]) -> dict` with keys `status` (`"PASS"`, `"ONE_ARM_PASS"`, `"FAIL"`), `passing_arms` (list[str])
  - `holdb_gate(book_mean: float) -> str` (`"PASS"`/`"FAIL"`)
  - `holda_gate(book_mean: float, trimmed_top2_mean: float) -> str`
  - `trim_top(values: np.ndarray, k: int) -> float`

- [ ] **Step 1: Write the failing tests**

```python
def test_dev_gate_requires_all_three():
    ok = ts.dev_gate(1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})
    assert ok == {"status": "PASS", "passing_arms": [ts.LONG, ts.SHORT]}
    assert ts.dev_gate(1.0, -0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})["status"] == "FAIL"
    assert ts.dev_gate(-1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: 0.5})["status"] == "FAIL"


def test_dev_gate_one_arm():
    got = ts.dev_gate(1.0, 0.1, {ts.LONG: 2.0, ts.SHORT: -0.5})
    assert got == {"status": "ONE_ARM_PASS", "passing_arms": [ts.LONG]}


def test_dev_gate_zero_is_not_positive():
    assert ts.dev_gate(0.0, 0.1, {ts.LONG: 1.0, ts.SHORT: 1.0})["status"] == "FAIL"


def test_trim_top_removes_largest():
    assert ts.trim_top(np.array([1., 2., 100., 50.]), 2) == pytest.approx(1.5)


def test_hold_gates():
    assert ts.holdb_gate(0.01) == "PASS" and ts.holdb_gate(0.0) == "FAIL"
    assert ts.holda_gate(1.0, 0.1) == "PASS" and ts.holda_gate(1.0, -0.1) == "FAIL"
```

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/test_k45_trend_side.py -v` → new tests FAIL with `AttributeError`.

- [ ] **Step 3: Implement**

```python
def trim_top(values: np.ndarray, k: int) -> float:
    v = np.sort(np.asarray(values, float))
    return float(v[:len(v) - k].mean())


def dev_gate(book_mean: float, ci_lower: float, cell_means: dict[str, float]) -> dict:
    passing = [arm for arm in (LONG, SHORT) if cell_means.get(arm, float("nan")) > 0]
    if not (book_mean > 0 and ci_lower > 0) or not passing:
        return {"status": "FAIL", "passing_arms": []}
    return {"status": "PASS" if len(passing) == 2 else "ONE_ARM_PASS", "passing_arms": passing}


def holdb_gate(book_mean: float) -> str:
    return "PASS" if book_mean > 0 else "FAIL"


def holda_gate(book_mean: float, trimmed_top2_mean: float) -> str:
    return "PASS" if book_mean > 0 and trimmed_top2_mean > 0 else "FAIL"
```

- [ ] **Step 4: Run to verify pass** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add out/k45_trend_side.py tests/test_k45_trend_side.py
git commit -m "feat: frozen pass gates for DEV, HOLD-B and HOLD-A"
```

---

### Task 3: Stage 1 runner (DEV + HOLD-B)

**Files:**
- Create: `out/run_k45_trend_side.py`
- Test: `tests/test_k45_trend_side.py` (append a smoke test on a synthetic frame)

**Interfaces:**
- Consumes: Task 1 and Task 2 functions; `flow.mean_influence`, `flow.pw_inference` from `out/run_patchtst_k45_flow_inference.py`.
- Produces:
  - `stage1(cands: pd.DataFrame, close: np.ndarray, lookback: int) -> dict[str, pd.DataFrame]` with keys `book`, `cells`, `baseline`, `monthly`
  - Output dir `out/k45_trend_side_20261001/` containing `book.parquet`, `cells.parquet`, `baseline.parquet`, `monthly.parquet`, `gates.json`, `manifest.json`, `REPORT.md`

Segments: `DEV = pilot_fold <= 605`, `HOLD_B = pilot_fold >= 606`.

- [ ] **Step 1: Write the failing smoke test**

```python
from out import run_k45_trend_side as run


def test_stage1_on_synthetic_frame():
    n = 200
    close = 100 + np.cumsum(np.full(n, 0.01))           # steady uptrend
    cands = pd.DataFrame({
        "candidate_id": [0, 1, 2],
        "pilot_fold": [0, 0, 0],
        "arm": [ts.LONG, ts.SHORT, ts.LONG],
        "signal_index": [60, 61, 150],
        "entry_index": [61, 62, 151],
        "scheduled_exit_index": [106, 107, 196],
        "entry_time": pd.to_datetime(["2021-01-10", "2021-01-10", "2021-01-11"], utc=True),
    })
    out = run.stage1(cands, close, lookback=50)
    book = out["book"]
    assert book.candidate_id.tolist() == [0, 2]          # short dropped in uptrend
    assert set(out["cells"].columns) >= {"arm", "trend", "n", "gross_mean_bps", "net_mean_bps"}
```

- [ ] **Step 2: Run to verify fail** — `ModuleNotFoundError: out.run_k45_trend_side`.

- [ ] **Step 3: Implement `stage1`**

```python
"""Stage 1: trend-conditioned side on frozen K=45 candidates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from out import k45_trend_side as ts
from out import run_patchtst_k45_flow_inference as flow

ROOT = Path("out/k45_trend_side_20261001")
CAND = Path("out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet")
MARKET = Path("artifacts/btcusdt_2020_2026h1.parquet")
HYPOTHESIS = "느린 추세 방향으로만 fade하면, 두 팔 모두 net이 0보다 크다."


def _position(arm: pd.Series) -> np.ndarray:
    return np.where(arm.to_numpy() == ts.LONG, 1.0, -1.0)


def stage1(cands: pd.DataFrame, close: np.ndarray, lookback: int) -> dict[str, pd.DataFrame]:
    c = cands.copy()
    c["trend"] = ts.trend_sign(close, c.signal_index.to_numpy(), lookback)
    c["position"] = _position(c.arm)
    c["net_bps"] = ts.net_bps(close, c.entry_index, c.scheduled_exit_index, c.position)
    c["gross_bps"] = c.net_bps + ts.COST
    c["taken"] = ts.side_mask(c.arm.to_numpy(), c.trend.to_numpy())
    eligible = c[c.taken].copy()
    eligible["admitted"] = ts.admit(eligible.entry_index.to_numpy())
    book = eligible[eligible.admitted].sort_values("entry_index").reset_index(drop=True)
    cells = (c[c.trend != 0].groupby(["arm", "trend"])
             .agg(n=("net_bps", "size"), gross_mean_bps=("gross_bps", "mean"),
                  net_mean_bps=("net_bps", "mean")).reset_index())
    book_cells = (book.groupby("arm").agg(n=("net_bps", "size"), net_mean_bps=("net_bps", "mean"))
                  .reset_index())
    month = pd.to_datetime(book.entry_time, utc=True).dt.strftime("%Y-%m")
    monthly = book.assign(month=month).groupby("month").net_bps.agg(["size", "mean"]).reset_index()
    return {"book": book, "cells": cells, "book_cells": book_cells, "monthly": monthly}
```

- [ ] **Step 4: Run smoke test** → PASS.

- [ ] **Step 5: Add the random baseline by trend state**

```python
def random_baseline(close: np.ndarray, start: int, stop: int, lookback: int) -> pd.DataFrame:
    """Every minute in [start, stop-HOLD): position follows the trend rule (long if +1, short if -1)."""
    idx = np.arange(start, stop - ts.HOLD)
    trend = ts.trend_sign(close, idx, lookback)
    keep = trend != 0
    idx, trend = idx[keep], trend[keep].astype(float)
    net = ts.net_bps(close, idx, idx + ts.HOLD, trend)
    return pd.DataFrame({"trend": trend, "n": 1, "net": net}).groupby("trend").agg(
        n=("n", "size"), net_mean_bps=("net", "mean")).reset_index()
```

Test:

```python
def test_random_baseline_uptrend_long_is_positive():
    close = 100 + np.cumsum(np.full(400, 0.05))
    b = run.random_baseline(close, 100, 400, lookback=50)
    assert b.trend.tolist() == [1.0]
    assert b.net_mean_bps.iloc[0] > -4
```

Run → PASS.

- [ ] **Step 6: Add `main()` — segment, infer, gate, write**

```python
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _segment_report(cands, close, lookback, label):
    out = stage1(cands, close, lookback)
    book = out["book"]
    frame = book.assign(entry_day=pd.to_datetime(book.entry_time, utc=True).dt.normalize())
    start, end = frame.entry_day.min(), frame.entry_day.max()
    est, raw, _ = flow.mean_influence(frame, "net_bps", start, end)
    inf = flow.pw_inference(est, raw, "greater", f"{label}_book_net")
    lo, hi = int(cands.entry_index.min()), int(cands.scheduled_exit_index.max())
    base = random_baseline(close, lo, hi, lookback)
    cell_means = dict(zip(out["book_cells"].arm, out["book_cells"].net_mean_bps))
    return out, inf, base, cell_means


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    cands = pd.read_parquet(CAND)
    close = pd.read_parquet(MARKET, columns=["close"])["close"].to_numpy(float)
    gates, frames = {}, {}
    for label, part in (("DEV", cands[cands.pilot_fold <= 605]),
                        ("HOLD_B", cands[cands.pilot_fold >= 606])):
        for lb_name, lb in (("30d", ts.TREND_LOOKBACK), ("7d_report_only", ts.TREND_LOOKBACK_REPORT)):
            out, inf, base, cell_means = _segment_report(part, close, lb, f"{label}_{lb_name}")
            book = out["book"]
            key = f"{label}_{lb_name}"
            for name, f in {**out, "baseline": base}.items():
                frames[f"{key}_{name}"] = f
            gates[key] = {
                "n_book": int(len(book)),
                "book_net_mean_bps": float(book.net_bps.mean()),
                "book_net_trim_top2_bps": ts.trim_top(book.net_bps.to_numpy(), 2),
                "pw": inf,
                "cell_means": cell_means,
                "monthly_positive_share": float((out["monthly"]["mean"] > 0).mean()),
            }
            if lb_name == "30d":
                gates[key]["gate"] = (ts.dev_gate(gates[key]["book_net_mean_bps"],
                                                  inf["bootstrap_ci95_lower"], cell_means)
                                      if label == "DEV" else ts.holdb_gate(gates[key]["book_net_mean_bps"]))
    for name, f in frames.items():
        f.to_parquet(ROOT / f"{name}.parquet", index=False)
    (ROOT / "gates.json").write_text(json.dumps(gates, indent=1, default=float), encoding="utf-8")
    (ROOT / "manifest.json").write_text(json.dumps({
        "hypothesis": HYPOTHESIS,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "data_cutoff_utc": "2026-06-30T23:59:00Z",
        "inputs": {str(CAND): _sha(CAND), str(MARKET): _sha(MARKET)},
        "source": {__file__: _sha(Path(__file__)), "out/k45_trend_side.py": _sha(Path("out/k45_trend_side.py"))},
        "new_model_fits": 0, "live_orders": 0,
    }, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests, then commit (do not run `main` yet)**

```bash
python -m pytest tests/test_k45_trend_side.py -v
git add out/run_k45_trend_side.py tests/test_k45_trend_side.py
git commit -m "feat: stage 1 runner for the trend-conditioned side test"
```

---

### Task 4: Run stage 1, write report, adversarial review

**Files:**
- Create: `out/k45_trend_side_20261001/*` (outputs), `out/k45_trend_side_20261001/REPORT.md`

- [ ] **Step 1: Claude reviews Tasks 1–3 diff** before any run. Check the Review Focus items 1–2 against the code.
- [ ] **Step 2: Run** `python -m out.run_k45_trend_side` (background, with a monitor). Expected: `gates.json` has keys `DEV_30d`, `DEV_7d_report_only`, `HOLD_B_30d`, `HOLD_B_7d_report_only`.
- [ ] **Step 3: Write `REPORT.md`** with, per segment: book n, net mean, trimmed top-2, PW CI, cell table (arm × trend), random baseline by trend, monthly positive share, and the gate verdict. Compare against the long-only book (+0.455) and the shared book (−0.521).
- [ ] **Step 4: Adversarial round** — send the report to Codex with "확인 말고 공격하라". Ask specifically: is the 30d trend just re-labelling calendar regime? Does the short cell survive without 2022?
- [ ] **Step 5: Record** the result in engram (`topic_key: k45/trend-side-stage1`).
- [ ] **Step 6: Commit outputs**

```bash
git add out/k45_trend_side_20261001 out/run_k45_trend_side.py
git commit -m "research: stage 1 trend-conditioned side results"
```

**Branch after Task 4:**
- `DEV` `FAIL` for both arms → stop stages 2 and 5. Stage 3-class target spec (spec §9) becomes the next step.
- `ONE_ARM_PASS` or `PASS` → Task 5 on the passing arms only.

---

### Task 5: TP exit function

**Files:**
- Modify: `out/k45_trend_side.py` (append)
- Test: `tests/test_k45_trend_side.py` (append)

**Interfaces:**
- Produces: `tp_exit_net_bps(high, low, close, entry, position, tp_bps: float, hold: int = HOLD) -> tuple[np.ndarray, np.ndarray]` returning `(net_bps, exit_index)`.

Rules: entry price `close[entry]`. TP window is bars `entry+1 .. entry+hold`. A long fills when `high >= entry_price*(1+tp/1e4)`; a short fills when `low <= entry_price*(1-tp/1e4)`. The fill price is the TP price exactly. If TP and the time exit fall on the same bar, TP wins. With no touch, exit at `close[entry+hold]`. Subtract `COST`.

- [ ] **Step 1: Write the failing tests**

```python
def test_tp_long_fills_at_tp_price():
    close = np.array([100., 100., 100., 100.])
    high = np.array([100., 100.4, 101.0, 100.])
    low = close.copy()
    net, ex = ts.tp_exit_net_bps(high, low, close, np.array([0]), np.array([1.]), 50, hold=3)
    assert ex.tolist() == [2] and net == pytest.approx([50 - 4])


def test_tp_not_filled_on_entry_bar():
    close = np.array([100., 100., 100.])
    high = np.array([200., 100., 100.])
    net, ex = ts.tp_exit_net_bps(high, close, close, np.array([0]), np.array([1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([-4])


def test_tp_short_and_same_bar_as_time_exit():
    close = np.array([100., 100., 98.])
    low = np.array([100., 100., 99.4])
    net, ex = ts.tp_exit_net_bps(close, low, close, np.array([0]), np.array([-1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([50 - 4])


def test_tp_untouched_uses_time_exit():
    close = np.array([100., 100., 100.2])
    net, ex = ts.tp_exit_net_bps(close, close, close, np.array([0]), np.array([1.]), 50, hold=2)
    assert ex.tolist() == [2] and net == pytest.approx([20 - 4])
```

- [ ] **Step 2: Run to verify fail** → `AttributeError`.

- [ ] **Step 3: Implement**

```python
def tp_exit_net_bps(high, low, close, entry, position, tp_bps: float, hold: int = HOLD):
    high, low, close = (np.asarray(a, float) for a in (high, low, close))
    entry = np.asarray(entry, np.int64)
    position = np.asarray(position, float)
    net = np.empty(len(entry))
    exit_index = np.empty(len(entry), np.int64)
    for i, (e, p) in enumerate(zip(entry, position)):
        price = close[e]
        target = price * (1 + p * tp_bps / 1e4)
        window = np.arange(e + 1, e + hold + 1)
        hit = high[window] >= target if p > 0 else low[window] <= target
        if hit.any():
            exit_index[i] = window[int(np.argmax(hit))]
            net[i] = tp_bps - COST
        else:
            exit_index[i] = e + hold
            net[i] = p * 1e4 * (close[e + hold] / price - 1) - COST
    return net, exit_index
```

Note: the book slot still frees at `entry + HOLD` (fixed 45-minute occupancy), so admission is unchanged by TP. State this in the report.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit**

```bash
git add out/k45_trend_side.py tests/test_k45_trend_side.py
git commit -m "feat: limit TP exit for the trend-side book"
```

---

### Task 6: Stage 2 runner (TP grid on DEV, verdict on HOLD-B)

**Files:**
- Create: `out/run_k45_trend_side_tp.py`
- Test: `tests/test_k45_trend_side.py` (append)

**Interfaces:**
- Consumes: `stage1`, `tp_exit_net_bps`, `flow.pw_inference`, `dev_gate`, `holdb_gate`. Reads `out/k45_trend_side_20261001/gates.json` for `passing_arms`.
- Produces: `select_tp(results: dict[float, dict]) -> float | None` (the TP with the largest DEV net whose p < `0.05/3`; `None` if none). Outputs in `out/k45_trend_side_tp_20261001/`.

- [ ] **Step 1: Failing test**

```python
from out import run_k45_trend_side_tp as tp


def test_select_tp_bonferroni():
    r = {50.0: {"net": 1.0, "p": 0.01}, 100.0: {"net": 2.0, "p": 0.02}, 150.0: {"net": 0.5, "p": 0.001}}
    assert tp.select_tp(r) == 50.0
    assert tp.select_tp({50.0: {"net": 1.0, "p": 0.02}}) is None
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement**

```python
GRID = (50.0, 100.0, 150.0)
ALPHA = 0.05 / len(GRID)


def select_tp(results: dict[float, dict]) -> float | None:
    ok = {k: v for k, v in results.items() if v["p"] < ALPHA}
    return max(ok, key=lambda k: ok[k]["net"]) if ok else None
```

`main()`: load candidates, market `high/low/close`; for each segment run `stage1(..., ts.TREND_LOOKBACK)`, keep book rows whose `arm` is in `passing_arms`; for each TP in `GRID` compute `tp_exit_net_bps`, daily PW inference (`"greater"`), paired difference vs no-TP; `select_tp` on DEV; apply only the chosen TP to HOLD-B and gate with `holdb_gate`. Write `grid.parquet`, `paired.parquet`, `gates.json`, `manifest.json` (same fields as Task 3).

- [ ] **Step 4: Run tests → pass. Commit.**

```bash
git add out/run_k45_trend_side_tp.py tests/test_k45_trend_side.py
git commit -m "feat: stage 2 TP grid runner with Bonferroni selection"
```

- [ ] **Step 5: Claude review, run in background with monitor, REPORT.md, Codex attack round, engram record (`k45/trend-side-stage2`), commit outputs.**

---

### Task 7: HOLD-A judge (one shot)

**Files:**
- Create: `out/run_k45_holdout_a_judge.py`
- Test: `tests/test_k45_trend_side.py` (append)

**Interfaces:**
- Consumes: `out/k45_holdout_a_2026q3/candidates_sealed.parquet`, `SEALED.json`, `manifest.json` (from the dispatched HOLD-A prep); the frozen rule from Task 4/6 gates (`passing_arms`, chosen TP or `None`).
- Produces: `out/k45_holdout_a_2026q3/JUDGEMENT.json`, `JUDGEMENT.md`.

- [ ] **Step 1: Failing test — seal check fails loudly**

```python
from out import run_k45_holdout_a_judge as judge


def test_judge_refuses_on_hash_mismatch(tmp_path):
    f = tmp_path / "c.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(f)
    with pytest.raises(RuntimeError, match="seal"):
        judge.verify_seal(f, expected_sha="0" * 64)
```

- [ ] **Step 2: Implement `verify_seal`, `verify_index_basis(manifest, close_len)`** (raises `RuntimeError("index basis mismatch")` if the manifest's basis length differs from the concatenated close array), and `main()` that:
  1. Refuses to run if `JUDGEMENT.json` already exists (one shot).
  2. Verifies the seal and index basis.
  3. Loads concatenated `close/high/low` = `artifacts/btcusdt_2020_2026h1.parquet` + `artifacts/btcusdt_2026q3.parquet` in the order recorded in the manifest.
  4. Applies trend (30d), side filter restricted to `passing_arms`, `admit`, then TP (if chosen) or 45-minute exit.
  5. Computes book mean, trimmed top-2, PW CI, and `holda_gate`.
  6. Writes the judgement with the SHA256 of this script, the module, and the frozen gates files.

- [ ] **Step 3: Freeze** — commit the judge script and record its SHA256 in `out/k45_holdout_a_2026q3/FROZEN_JUDGE.json` **before** the run.

```bash
git add out/run_k45_holdout_a_judge.py tests/test_k45_trend_side.py out/k45_holdout_a_2026q3/FROZEN_JUDGE.json
git commit -m "feat: frozen one-shot HOLD-A judge"
```

- [ ] **Step 4: Run once. Report. Codex attack round. engram record (`k45/holdout-a`). Commit outputs.**

Precondition for Task 7: the HOLD-A prep brief (`out/k45_holdout_a_2026q3/BRIEF.md`) has finished and Claude has reviewed its REPORT, including the fold-666 reproduction check.
