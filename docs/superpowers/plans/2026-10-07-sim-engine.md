# Simulation Engine (Plan 1 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `btcusdt_quant/sim/`, a verified, fast, reproducible BTCUSDT futures backtest engine that later plans use for the 24-strategy rolling backtest and as the reinforcement-learning simulator.

**Architecture:** Pure-function data/bars/indicator modules feed a signal table into two independent simulators — a slow, obvious `reference.py` and a numba `core.py` — that must agree to 1e-9 bps. One minute-level mark-to-market ledger is the only accounting source. Feature store, experiment registry and a result guard wrap every run.

**Tech Stack:** Python 3.14 (`venv_btcusdt`), pandas, numpy, pyarrow, numba, hypothesis, mutmut, scipy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-07-rl-trading-design.md` (§1, §2). Plans 2–4 cover §3–§6 and parity A4.

## Global Constraints

- Package path `btcusdt_quant/sim/`. Never create `btcusdt_quant/backtest/` (it shadows the existing `btcusdt_quant/backtest.py`).
- Do not modify `btcusdt_quant/paper/`, the live DB `artifacts/live/live.sqlite`, stage-1 outputs under `out/k45_vol_detector_*`, or `docs/` other than this plan.
- No git commit unless the user asks (user instruction 2026-10-07: "커밋은 아직"). Replace every "Commit" step with "Record changed files in the task report".
- P&L unit: one unlevered unit, bps. Primary cost 4 bps round trip (2 bps per side, charged on every partial fill). No $100, leverage or sizing in reported metrics; leverage helpers exist only for later use.
- Availability rules: global/top LS, OI, taker LS ratio usable when `create_time + 5 minutes < T`; funding usable after its actual publish time; premium bar usable after its `close_time`; a bar is usable only after it is complete; missing minutes are never interpolated.
- Decision cadence 15 minutes for RL; strategies may use 5m/15m/30m/1h/4h complete bars.
- Same-T policy is explicit: `reentry="strict"` drops every entry decided at a time T when a position was held at T (even if it closes at T+delay); `reentry="stop_and_reverse"` allows the R2-39/C1_X behaviour (close then enter at the same execution minute). C1_X parity uses `stop_and_reverse`; new strategies default to `strict`.
- Same-minute stop and take-profit touch: stop wins. Gap through a level: fill at that minute's open.
- CPU workers ≤ 8. No downloads, orders or authenticated exchange calls.

## Review Focus

- A decision at the exact minute a position exits under `reentry="strict"` must not open a new position (Task 6, `test_strict_drops_entry_at_exit_minute`).
- A minute whose high touches the take-profit and whose low touches the stop must exit at the stop (Task 6, `test_stop_wins_same_minute`).
- A gap opening beyond the stop must fill at the minute open, not the stop level (Task 4, `test_stop_gap_fills_at_open`).
- A position still open at a segment boundary must contribute only in-segment mark-to-market P&L (Task 6, `test_segment_boundary_mtm`).
- A detector-prediction gap (last day of each stage-1 segment) must block new entries but allow exits (Task 6, `test_missing_gate_blocks_entry_not_exit`).

---

## File Structure

| File | Responsibility |
|---|---|
| `btcusdt_quant/sim/__init__.py` | Public exports |
| `btcusdt_quant/sim/provenance.py` | File/tree sha256, input manifest, verification |
| `btcusdt_quant/sim/data.py` | Load minutes, metrics, premium, funding, predictions with availability times |
| `btcusdt_quant/sim/bars.py` | Complete-bar aggregation |
| `btcusdt_quant/sim/indicators.py` | EMA, Wilder ATR/RSI, Bollinger, Keltner, Supertrend, UTC VWAP, past z-score |
| `btcusdt_quant/sim/orders.py` | Market/stop/limit/OCO fill rules on one minute bar |
| `btcusdt_quant/sim/costs.py` | Fee per partial fill, funding cashflow (wraps `out/k45_funding.py`), slippage (B2), latency sampling (B3), mark price (B4) |
| `btcusdt_quant/sim/schema.py` | Signal table schema + validation |
| `btcusdt_quant/sim/reference.py` | Slow, obvious event simulator and minute ledger |
| `btcusdt_quant/sim/core.py` | numba simulator with identical semantics |
| `btcusdt_quant/sim/intrabar.py` | Brownian-bridge intrabar ordering sensitivity (B1) |
| `btcusdt_quant/sim/analytics.py` | PW bootstrap CI, HAC mean CI, DSR, CSCV/PBO, White RC, Hansen SPA, Monte Carlo |
| `btcusdt_quant/sim/store.py` | Hash-keyed parquet feature store (C3) |
| `btcusdt_quant/sim/registry.py` | Experiment registry + ledger append (D1) |
| `btcusdt_quant/sim/guard.py` | Result guard (D2) |
| `scripts/sim_c1x_parity.py` | C1_X reproduction pre-check |
| `tests/sim/test_*.py` | Unit, differential, property tests |
| `setup.cfg` `[mutmut]` section | Mutation-test config (A3) |

---

### Task 1: Dependencies and package skeleton

**Files:**
- Create: `btcusdt_quant/sim/__init__.py`, `tests/sim/__init__.py`, `tests/sim/test_env.py`

**Interfaces:**
- Produces: importable package `btcusdt_quant.sim`.

- [ ] **Step 1: Install tools**

Run: `venv_btcusdt\Scripts\python.exe -m pip install numba hypothesis mutmut`
Expected: success. If numba has no wheel for Python 3.14, STOP and report to the user (do not downgrade Python silently); Task 7 then uses a numpy-vectorized fallback the user must approve.

- [ ] **Step 2: Write the failing test**

```python
# tests/sim/test_env.py
def test_sim_package_and_tools_import():
    import numba, hypothesis  # noqa: F401
    import btcusdt_quant.sim as sim
    import btcusdt_quant.backtest as legacy
    assert sim.__name__ == "btcusdt_quant.sim"
    assert legacy.__file__.endswith("backtest.py")  # legacy module not shadowed
```

- [ ] **Step 3: Run it, expect FAIL** (`ModuleNotFoundError: btcusdt_quant.sim`)

Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/sim/test_env.py -q`

- [ ] **Step 4: Create package**

```python
# btcusdt_quant/sim/__init__.py
"""Verified BTCUSDT futures simulation engine (spec 2026-10-07-rl-trading-design)."""
```
Create empty `tests/sim/__init__.py`.

- [ ] **Step 5: Run, expect PASS.** Record changed files.

---

### Task 2: Provenance and data loaders

**Files:**
- Create: `btcusdt_quant/sim/provenance.py`, `btcusdt_quant/sim/data.py`
- Test: `tests/sim/test_data.py`

**Interfaces:**
- Produces:
  - `provenance.file_sha256(path: Path) -> str`
  - `provenance.tree_sha256(root: Path, pattern: str) -> dict` with keys `files, sha256`
  - `provenance.verify(recorded: dict, current: dict) -> None` (raises `ValueError` listing mismatches)
  - `data.load_minutes(path=MARKET_PATH) -> DataFrame[open_time, open, high, low, close, volume, quote_volume, number_of_trades, taker_buy_base_volume]` (UTC, contiguous 1-minute; raises on gaps)
  - `data.load_metrics(root=METRICS_DIR) -> DataFrame[available_time, global_ls, top_ls, oi, oi_value, taker_lsr]`
  - `data.load_premium(root=PREMIUM_DIR) -> DataFrame[available_time, premium]` where `available_time = close_time + 1 ms`
  - `data.load_predictions(root=PREDICTIONS_DIR) -> DataFrame[timestamp, retrain_time, segment, prediction_<target> x15]`
  - `data.asof(values_time: DatetimeIndex, values: ndarray, decisions: DatetimeIndex, ttl: Timedelta | None) -> ndarray` (strictly earlier, NaN if none or stale)

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_data.py
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import data, provenance

def test_asof_strictly_earlier_and_ttl():
    times = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:05", "2024-01-01 00:10"], utc=True))
    decisions = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:10", "2024-01-01 00:10:00.001", "2024-01-01 01:00"], utc=True))
    out = data.asof(times, np.array([1.0, 2.0]), decisions, ttl=pd.Timedelta(minutes=15))
    assert out[0] == 1.0          # value at 00:10 not usable at exactly 00:10
    assert out[1] == 2.0
    assert np.isnan(out[2])       # 50 minutes old > ttl

def test_predictions_reject_future_retrain(tmp_path):
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:00"], utc=True),
                          "retrain_time": pd.to_datetime(["2024-01-01 00:15"], utc=True),
                          "segment": ["DEV_BACK"]})
    with pytest.raises(ValueError, match="retrain_time after timestamp"):
        data.validate_predictions(frame)

def test_predictions_reject_off_grid():
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:07"], utc=True),
                          "retrain_time": pd.to_datetime(["2024-01-01 00:00"], utc=True),
                          "segment": ["DEV_BACK"]})
    with pytest.raises(ValueError, match="15-minute grid"):
        data.validate_predictions(frame)

def test_minutes_reject_gap():
    t = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:02"], utc=True)
    frame = pd.DataFrame({"open_time": t, "open": 1., "high": 1., "low": 1., "close": 1.,
                          "volume": 1., "quote_volume": 1., "number_of_trades": 1,
                          "taker_buy_base_volume": .5})
    with pytest.raises(ValueError, match="missing minutes"):
        data.validate_minutes(frame)

def test_tree_hash_detects_change(tmp_path):
    (tmp_path / "a.zip").write_bytes(b"x")
    first = provenance.tree_sha256(tmp_path, "*.zip")
    (tmp_path / "a.zip").write_bytes(b"y")
    with pytest.raises(ValueError, match="a.zip|sha256"):
        provenance.verify({"t": first}, {"t": provenance.tree_sha256(tmp_path, "*.zip")})
```

- [ ] **Step 2: Run, expect FAIL** (`ImportError`).

Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/sim/test_data.py -q`

- [ ] **Step 3: Implement**

```python
# btcusdt_quant/sim/provenance.py
from __future__ import annotations
import hashlib
from pathlib import Path

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()

def tree_sha256(root: Path, pattern: str) -> dict:
    files = sorted(Path(root).glob(pattern))
    digest = hashlib.sha256()
    listing = {}
    for item in files:
        value = file_sha256(item)
        listing[item.name] = value
        digest.update(item.name.encode()); digest.update(value.encode())
    return {"files": listing, "sha256": digest.hexdigest()}

def verify(recorded: dict, current: dict) -> None:
    problems = []
    for key, value in recorded.items():
        now = current.get(key)
        if now is None:
            problems.append(f"{key}: missing")
        elif isinstance(value, dict) and "files" in value:
            for name in sorted(set(value["files"]) | set(now["files"])):
                if value["files"].get(name) != now["files"].get(name):
                    problems.append(f"{key}/{name}: sha256 changed")
        elif value != now:
            problems.append(f"{key}: sha256 changed")
    if problems:
        raise ValueError("provenance mismatch: " + "; ".join(problems))
```

```python
# btcusdt_quant/sim/data.py
from __future__ import annotations
import zipfile
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARKET_PATH = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
METRICS_DIR = ROOT / "artifacts/metrics"
PREMIUM_DIR = ROOT / "artifacts/premium_index_2020_2026h1"
PREDICTIONS_DIR = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw"
TARGETS = tuple(f"{k}_{h}" for k in ("range", "rv", "exc") for h in ("30m", "1h", "4h", "12h", "24h"))
MINUTE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume",
                  "number_of_trades", "taker_buy_base_volume"]

def validate_minutes(frame: pd.DataFrame) -> pd.DataFrame:
    step = np.diff(frame.open_time.array.asi8)
    if len(step) and not np.all(step == 60_000_000_000):
        raise ValueError("market has missing minutes; interpolation is forbidden")
    if not (frame.high >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise ValueError("high below open/close/low")
    return frame

def load_minutes(path: Path = MARKET_PATH) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=MINUTE_COLUMNS)
    frame["open_time"] = pd.to_datetime(frame.open_time, utc=True).astype("datetime64[ns, UTC]")
    return validate_minutes(frame.sort_values("open_time").reset_index(drop=True))

def _csv(path: Path, **kwargs) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one csv in {path}")
        return pd.read_csv(archive.open(names[0]), **kwargs)

def load_metrics(root: Path = METRICS_DIR) -> pd.DataFrame:
    frames = [_csv(p) for p in sorted(Path(root).glob("*.zip"))]
    raw = pd.concat(frames, ignore_index=True)
    create = pd.to_datetime(raw.create_time, utc=True).astype("datetime64[ns, UTC]")
    result = pd.DataFrame({
        "available_time": create + pd.Timedelta(minutes=5),
        "global_ls": pd.to_numeric(raw.count_long_short_ratio, errors="coerce"),
        "top_ls": pd.to_numeric(raw.count_toptrader_long_short_ratio, errors="coerce"),
        "oi": pd.to_numeric(raw.sum_open_interest, errors="coerce"),
        "oi_value": pd.to_numeric(raw.sum_open_interest_value, errors="coerce"),
        "taker_lsr": pd.to_numeric(raw.sum_taker_long_short_vol_ratio, errors="coerce")})
    return result.drop_duplicates("available_time", keep="last").sort_values("available_time").reset_index(drop=True)

def load_premium(root: Path = PREMIUM_DIR) -> pd.DataFrame:
    columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
               "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    frames = []
    for path in sorted(Path(root).glob("*.zip")):
        raw = _csv(path, header=None)
        if str(raw.iloc[0, 0]).lower() == "open_time":
            raw = raw.iloc[1:]
        raw.columns = columns
        frames.append(raw[["close_time", "close"]])
    raw = pd.concat(frames, ignore_index=True)
    result = pd.DataFrame({
        "available_time": pd.to_datetime(pd.to_numeric(raw.close_time), unit="ms", utc=True) + pd.Timedelta(milliseconds=1),
        "premium": pd.to_numeric(raw.close, errors="raise")})
    return result.drop_duplicates("available_time", keep="last").sort_values("available_time").reset_index(drop=True)

def validate_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    if (frame.retrain_time > frame.timestamp).any():
        raise ValueError("retrain_time after timestamp: future model used")
    if (frame.timestamp.dt.minute % 15 != 0).any() or (frame.timestamp.dt.second != 0).any():
        raise ValueError("prediction timestamp off the 15-minute grid")
    if frame.timestamp.duplicated().any():
        raise ValueError("duplicate prediction timestamp")
    return frame

def load_predictions(root: Path = PREDICTIONS_DIR) -> pd.DataFrame:
    paths = sorted(Path(root).glob("*/fold_*_predictions.parquet"))
    columns = ["timestamp", "retrain_time", "segment"] + [f"prediction_{t}" for t in TARGETS]
    frame = pd.concat([pd.read_parquet(p, columns=columns) for p in paths], ignore_index=True)
    for c in ("timestamp", "retrain_time"):
        frame[c] = pd.to_datetime(frame[c], utc=True)
    return validate_predictions(frame.sort_values("timestamp").reset_index(drop=True))

def asof(values_time: pd.DatetimeIndex, values: np.ndarray, decisions: pd.DatetimeIndex,
         ttl: pd.Timedelta | None) -> np.ndarray:
    position = np.searchsorted(values_time.asi8, decisions.asi8, side="left") - 1
    out = np.full(len(decisions), np.nan)
    ok = position >= 0
    out[ok] = np.asarray(values, float)[position[ok]]
    if ttl is not None:
        age = np.full(len(decisions), np.iinfo(np.int64).max)
        age[ok] = decisions.asi8[ok] - values_time.asi8[position[ok]]
        out[age > ttl.value] = np.nan
    return out
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Real-data smoke** — Run: `venv_btcusdt\Scripts\python.exe -c "from btcusdt_quant.sim import data as d; m=d.load_minutes(); p=d.load_predictions(); print(len(m), m.open_time.min(), m.open_time.max(), len(p), p.timestamp.min(), p.timestamp.max())"`. Expected: about 3.4M minutes 2020-01-01..2026-06-30 23:59; predictions 2022-03 onward, no exception. Record output in the task report.

---

### Task 3: Bars and indicators

**Files:**
- Create: `btcusdt_quant/sim/bars.py`, `btcusdt_quant/sim/indicators.py`
- Test: `tests/sim/test_bars_indicators.py`

**Interfaces:**
- Produces:
  - `bars.aggregate(minutes: DataFrame, minutes_per_bar: int) -> DataFrame[bar_start, decision_time, open, high, low, close, volume, taker_buy, n]` (complete bars only; `decision_time = bar_start + minutes_per_bar`)
  - `indicators.ema(x, span)`, `indicators.atr(bars, n)` (Wilder), `indicators.rsi(close, n)` (Wilder), `indicators.bollinger(close, n=20, k=2) -> DataFrame[middle, upper, lower]` (ddof=0), `indicators.keltner(bars, n=20, k=1.5) -> DataFrame[middle, upper, lower]` (EMA middle, Wilder ATR), `indicators.supertrend(bars, n=10, k=3) -> Series[direction]` (+1/−1), `indicators.vwap_utc(bars) -> Series`, `indicators.zscore_past(x, window, min_periods) -> Series` (mean/std from strictly earlier values).

- [ ] **Step 1: Write failing tests (hand-computed)**

```python
# tests/sim/test_bars_indicators.py
import numpy as np, pandas as pd
from btcusdt_quant.sim import bars, indicators

def minutes(n, start="2024-01-01"):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    c = np.arange(1, n + 1, dtype=float)
    return pd.DataFrame({"open_time": t, "open": c, "high": c + .5, "low": c - .5, "close": c,
                         "volume": 1., "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .25})

def test_aggregate_complete_only_and_decision_time():
    b = bars.aggregate(minutes(31), 15)
    assert len(b) == 2                                   # 31st minute starts an incomplete bar
    assert b.decision_time.iloc[0] == pd.Timestamp("2024-01-01 00:15", tz="UTC")
    assert b.open.iloc[0] == 1 and b.close.iloc[0] == 15 and b.high.iloc[0] == 15.5 and b.volume.iloc[0] == 15

def test_ema_matches_recursion():
    x = pd.Series([1., 2., 3.]); a = 2 / (2 + 1)
    expected = [1., a * 2 + (1 - a) * 1, None]; expected[2] = a * 3 + (1 - a) * expected[1]
    assert np.allclose(indicators.ema(x, 2), expected)

def test_rsi_all_up_is_100():
    assert indicators.rsi(pd.Series(np.arange(30, dtype=float)), 14).iloc[-1] == 100

def test_bollinger_population_std():
    out = indicators.bollinger(pd.Series([1., 2., 3.]), n=3, k=2)
    std = np.std([1, 2, 3])
    assert np.isclose(out.upper.iloc[-1], 2 + 2 * std)

def test_zscore_past_excludes_current():
    x = pd.Series([0., 0., 0., 10.])
    z = indicators.zscore_past(x, 3, 3)
    assert np.isinf(z.iloc[3]) or np.isnan(z.iloc[3])   # past std 0
    y = pd.Series([1., 2., 3., 100.])
    assert np.isclose(indicators.zscore_past(y, 3, 3).iloc[3], (100 - 2) / np.std([1, 2, 3]))

def test_vwap_resets_each_utc_day():
    m = minutes(2 * 1440, start="2024-01-01")
    b = bars.aggregate(m, 15)
    v = indicators.vwap_utc(b)
    first_next_day = b.index[b.bar_start.eq(pd.Timestamp("2024-01-02", tz="UTC"))][0]
    assert np.isclose(v.loc[first_next_day], (b.loc[first_next_day, ["high", "low", "close"]].mean()))
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
# btcusdt_quant/sim/bars.py
from __future__ import annotations
import pandas as pd

def aggregate(minutes: pd.DataFrame, minutes_per_bar: int) -> pd.DataFrame:
    rule = f"{minutes_per_bar}min"
    g = minutes.set_index("open_time").resample(rule, origin="epoch", label="left", closed="left")
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"), taker_buy=("taker_buy_base_volume", "sum"), n=("close", "size"))
    out = out.loc[out.n == minutes_per_bar].reset_index().rename(columns={"open_time": "bar_start"})
    out["decision_time"] = out.bar_start + pd.Timedelta(minutes=minutes_per_bar)
    return out.reset_index(drop=True)
```

```python
# btcusdt_quant/sim/indicators.py
from __future__ import annotations
import numpy as np, pandas as pd

def ema(x: pd.Series, span: int) -> pd.Series:
    return x.ewm(span=span, adjust=False).mean()

def _wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()

def true_range(b: pd.DataFrame) -> pd.Series:
    prev = b.close.shift()
    return pd.concat([b.high - b.low, (b.high - prev).abs(), (b.low - prev).abs()], axis=1).max(axis=1)

def atr(b: pd.DataFrame, n: int = 14) -> pd.Series:
    return _wilder(true_range(b), n)

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up, down = _wilder(d.clip(lower=0), n), _wilder((-d).clip(lower=0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100 - 100 / (1 + up / down)
    return out.where(down != 0, 100.0)

def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    m = close.rolling(n).mean(); s = close.rolling(n).std(ddof=0)
    return pd.DataFrame({"middle": m, "upper": m + k * s, "lower": m - k * s})

def keltner(b: pd.DataFrame, n: int = 20, k: float = 1.5) -> pd.DataFrame:
    m = ema(b.close, n); a = atr(b, n)
    return pd.DataFrame({"middle": m, "upper": m + k * a, "lower": m - k * a})

def supertrend(b: pd.DataFrame, n: int = 10, k: float = 3.0) -> pd.Series:
    a = atr(b, n).to_numpy(); mid = ((b.high + b.low) / 2).to_numpy(); close = b.close.to_numpy()
    upper, lower = mid + k * a, mid - k * a
    direction = np.ones(len(b), dtype=np.int8)
    fu, fl = upper.copy(), lower.copy()
    for i in range(1, len(b)):
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < fl[i] else 1
        else:
            direction[i] = 1 if close[i] > fu[i] else -1
    return pd.Series(direction, index=b.index)

def vwap_utc(b: pd.DataFrame) -> pd.Series:
    typical = b[["high", "low", "close"]].mean(axis=1)
    day = b.bar_start.dt.floor("D")
    pv = (typical * b.volume).groupby(day).cumsum(); vol = b.volume.groupby(day).cumsum()
    return pv / vol

def zscore_past(x: pd.Series, window: int, min_periods: int) -> pd.Series:
    past = x.shift()
    m = past.rolling(window, min_periods=min_periods).mean()
    s = past.rolling(window, min_periods=min_periods).std(ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (x - m) / s
```

- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 4: Order fill rules

**Files:**
- Create: `btcusdt_quant/sim/orders.py`
- Test: `tests/sim/test_orders.py`

**Interfaces:**
- Produces: `orders.fill_stop(side:int, level:float, o:float, h:float, l:float) -> float | None`, `orders.fill_limit(side, level, o, h, l) -> float | None`, `orders.fill_oco(upper, lower, o, h, l) -> tuple[int, float] | None` (long stop at upper, short stop at lower; if both touched in one minute the side whose level is nearer the open wins; tie → no fill that minute is NOT allowed — choose the short side, the conservative adverse choice for a breakout entry), `orders.exit_touch(side, stop, take, o, h, l) -> tuple[str, float] | None` (`"stop"` wins over `"take"` in the same minute).

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_orders.py
from btcusdt_quant.sim import orders

def test_stop_gap_fills_at_open():
    assert orders.fill_stop(1, 100, o=105, h=106, l=104) == 105
    assert orders.fill_stop(-1, 100, o=95, h=96, l=94) == 95

def test_stop_touch_fills_at_level():
    assert orders.fill_stop(1, 100, o=99, h=101, l=98) == 100
    assert orders.fill_stop(1, 100, o=99, h=99.9, l=98) is None

def test_limit_needs_trade_through():
    assert orders.fill_limit(1, 100, o=101, h=102, l=99.9) == 100
    assert orders.fill_limit(1, 100, o=101, h=102, l=100) is None   # touch only
    assert orders.fill_limit(1, 100, o=99, h=100, l=98) == 99          # opens below: fill at open

def test_oco_both_touched_prefers_nearer_open():
    assert orders.fill_oco(upper=101, lower=95, o=100, h=102, l=94) == (1, 101)

def test_stop_wins_same_minute():
    assert orders.exit_touch(1, stop=99, take=103, o=100, h=104, l=98) == ("stop", 99)
    assert orders.exit_touch(-1, stop=101, take=97, o=100, h=102, l=96) == ("stop", 101)

def test_exit_gap_through_stop_at_open():
    assert orders.exit_touch(1, stop=99, take=103, o=97, h=98, l=96) == ("stop", 97)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
# btcusdt_quant/sim/orders.py
from __future__ import annotations

def fill_stop(side: int, level: float, o: float, h: float, l: float) -> float | None:
    if side == 1:
        return o if o >= level else (level if h >= level else None)
    return o if o <= level else (level if l <= level else None)

def fill_limit(side: int, level: float, o: float, h: float, l: float) -> float | None:
    if side == 1:
        return o if o <= level else (level if l < level else None)
    return o if o >= level else (level if h > level else None)

def fill_oco(upper: float, lower: float, o: float, h: float, l: float) -> tuple[int, float] | None:
    up, down = fill_stop(1, upper, o, h, l), fill_stop(-1, lower, o, h, l)
    if up is not None and down is not None:
        return (1, up) if abs(upper - o) < abs(o - lower) else (-1, down)
    if up is not None:
        return 1, up
    if down is not None:
        return -1, down
    return None

def exit_touch(side: int, stop: float, take: float, o: float, h: float, l: float) -> tuple[str, float] | None:
    stop_price = fill_stop(-side, stop, o, h, l)
    if stop_price is not None:
        return "stop", stop_price
    take_price = fill_limit(-side, take, o, h, l)
    return ("take", take_price) if take_price is not None else None
```

- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 5: Costs, funding, slippage, latency, mark price

**Files:**
- Create: `btcusdt_quant/sim/costs.py`
- Test: `tests/sim/test_costs.py`

**Interfaces:**
- Consumes: `out/k45_funding.py` (`load_settlements()`, `trade_funding(side, entry_time, exit_time, settlements, boundary) -> (interior_bps, edge_bps)`), loaded by file path.
- Produces:
  - `costs.FEE_BPS_PER_SIDE = 2.0`
  - `costs.fee_bps(units: float, per_side: float = 2.0) -> float`
  - `costs.funding_bps(side, entry_time, exit_time, boundary="PESS") -> float`
  - `costs.slippage_bps(notional_units: float, minute_volume_btc: float, minute_range_bps: float, k: float) -> float` = `k * minute_range_bps * min(1, notional_units / max(minute_volume_btc, 1e-9))` (sensitivity only)
  - `costs.latency_sampler(observed_ms: ndarray, rng) -> Callable[[], int]` returning whole minutes `max(1, ceil(ms/60000))`
  - `costs.mark_price(last: float, premium: float) -> float` = `last * (1 + premium)` (B4; used by leverage helpers only)

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_costs.py
import numpy as np, pandas as pd
from btcusdt_quant.sim import costs

def test_fee_per_partial_fill():
    assert costs.fee_bps(1.0) == 2.0 and costs.fee_bps(.5) == 1.0

def test_funding_matches_reference_module():
    entry = pd.Timestamp("2024-01-01 07:00", tz="UTC"); exit_ = pd.Timestamp("2024-01-01 09:00", tz="UTC")
    value = costs.funding_bps(1, entry, exit_)
    ref = costs._funding_module().trade_funding(1, entry, exit_, costs._settlements(), "PESS")
    assert np.isclose(value, sum(ref))

def test_slippage_scales_and_caps():
    assert costs.slippage_bps(1, 10, 20, k=.5) == .5 * 20 * .1
    assert costs.slippage_bps(100, 10, 20, k=.5) == 10

def test_latency_sampler_rounds_up_minimum_one():
    draw = costs.latency_sampler(np.array([1000.0]), np.random.default_rng(0))
    assert draw() == 1
    draw = costs.latency_sampler(np.array([61000.0]), np.random.default_rng(0))
    assert draw() == 2
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
# btcusdt_quant/sim/costs.py
from __future__ import annotations
import importlib.util, math, sys
from functools import lru_cache
from pathlib import Path
from typing import Callable
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE_BPS_PER_SIDE = 2.0

@lru_cache(maxsize=1)
def _funding_module():
    spec = importlib.util.spec_from_file_location("k45_funding", ROOT / "out/k45_funding.py")
    module = importlib.util.module_from_spec(spec); sys.modules["k45_funding"] = module
    spec.loader.exec_module(module)
    return module

@lru_cache(maxsize=1)
def _settlements() -> pd.DataFrame:
    return _funding_module().load_settlements()

def fee_bps(units: float, per_side: float = FEE_BPS_PER_SIDE) -> float:
    return float(per_side * units)

def funding_bps(side: int, entry_time: pd.Timestamp, exit_time: pd.Timestamp, boundary: str = "PESS") -> float:
    interior, edge = _funding_module().trade_funding(side, entry_time, exit_time, _settlements(), boundary)
    return float(interior + edge)

def slippage_bps(notional_units: float, minute_volume_btc: float, minute_range_bps: float, k: float) -> float:
    return float(k * minute_range_bps * min(1.0, notional_units / max(minute_volume_btc, 1e-9)))

def latency_sampler(observed_ms: np.ndarray, rng: np.random.Generator) -> Callable[[], int]:
    values = np.asarray(observed_ms, float)
    def draw() -> int:
        return max(1, math.ceil(float(rng.choice(values)) / 60_000))
    return draw

def mark_price(last: float, premium: float) -> float:
    return float(last * (1.0 + premium))
```

- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 6: Signal schema and reference simulator with minute ledger

**Files:**
- Create: `btcusdt_quant/sim/schema.py`, `btcusdt_quant/sim/reference.py`
- Test: `tests/sim/test_reference.py`

**Interfaces:**
- Consumes: `orders.*`, `costs.fee_bps`, `costs.funding_bps`.
- Produces:
  - `schema.SIGNAL_COLUMNS = ["decision_time", "side", "entry", "upper", "lower", "expiry_min", "max_hold_min", "stop_bps", "take_bps", "exit_long", "exit_short", "allow_entry"]`. `side` ∈ {−1,0,+1}; `entry` ∈ {"market","oco"}; `upper/lower` used by "oco"; `stop_bps/take_bps` NaN when unused; `exit_long/exit_short` bool flags meaning "close a long/short at this decision"; `allow_entry` False blocks new entries (missing gate) but never exits.
  - `schema.validate(signals: DataFrame) -> DataFrame` (sorted unique decision_time, dtypes, enum checks).
  - `reference.SimConfig(delay_min:int=1, reentry:str="strict", exit_style:str="NATIVE", fee_per_side:float=2.0, funding_boundary:str="PESS", stop_slippage_bps:float=0.0, include_funding:bool=True)`
  - `reference.simulate(signals: DataFrame, minutes: DataFrame, start: Timestamp, end: Timestamp, config: SimConfig) -> SimResult` where `SimResult.trades: DataFrame[decision_time, entry_time, exit_time, side, units, entry_price, exit_price, exit_reason, gross_bps, fee_bps, funding_bps, net_bps]` (one row per partial fill pair) and `SimResult.minute_pnl: Series` (bps per minute, index open_time, only minutes in [start,end)).
  - Exit precedence each minute while held: stop/take touch (`orders.exit_touch`, stop wins) → max-hold expiry at `entry_time + max_hold_min` → at a decision time: reverse signal (opposite `side`) or `exit_long/exit_short` flag, executed at `decision + delay`.
  - DETEXIT (`exit_style="DETEXIT"`): enter 0.5 unit; at the next decision with the same side signal and before any stop/take, add 0.5 unit (average entry price); stop = entry_avg·(1 − side·stop_bps/1e4); first take at entry_avg·(1 + side·take_bps/1e4) closes half and moves stop to entry_avg; remaining half follows NATIVE exits or the breakeven stop.
  - `reentry="strict"`: an entry decided at T is dropped if any position was open at T (including one that closes at T+delay). `reentry="stop_and_reverse"`: after an exit executed at T+delay, an entry decided at T is allowed at T+delay.
  - Minute ledger: unrealised mark-to-market from minute close to minute close, realised at fills; fees booked at each fill minute; funding booked at the exit minute; sum(minute_pnl over all time) == sum(trades.net_bps) within 1e-9.

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_reference.py
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import reference, schema

def flat_minutes(n=600, price=100.0, start="2024-01-01"):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    p = np.full(n, price)
    return pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p, "volume": 1.,
                         "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .5})

def sig(rows):
    base = {"entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 240,
            "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True}
    return schema.validate(pd.DataFrame([{**base, **r} for r in rows]))

CFG = reference.SimConfig(include_funding=False)
T0 = pd.Timestamp("2024-01-01", tz="UTC")

def run(signals, minutes, **kw):
    return reference.simulate(signals, minutes, T0, T0 + pd.Timedelta(days=1), reference.SimConfig(include_funding=False, **kw))

def test_market_entry_t_plus_one_and_fee():
    m = flat_minutes(); m.loc[100:, ["open", "high", "low", "close"]] = 101.0
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "max_hold_min": 120}])
    r = run(s, m)
    t = r.trades.iloc[0]
    assert t.entry_time == T0 + pd.Timedelta(minutes=16) and t.entry_price == 100
    assert t.exit_time == T0 + pd.Timedelta(minutes=136) and t.exit_price == 101
    assert np.isclose(t.gross_bps, np.log(101 / 100) * 1e4) and t.fee_bps == 4.0

def test_strict_drops_entry_at_exit_minute():
    m = flat_minutes()
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "max_hold_min": 60},
             {"decision_time": T0 + pd.Timedelta(minutes=75), "side": -1}])   # exit fills at 76 = this entry minute
    assert len(run(s, m, reentry="strict").trades) == 1
    assert len(run(s, m, reentry="stop_and_reverse").trades) == 2

def test_stop_wins_same_minute():
    m = flat_minutes(); m.loc[30, ["high", "low"]] = [110.0, 90.0]
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "stop_bps": 500, "take_bps": 500}])
    r = run(s, m, exit_style="DETEXIT")
    assert set(r.trades.exit_reason) == {"stop"}

def test_detexit_half_take_then_breakeven():
    m = flat_minutes(); m.loc[40, "high"] = 106.0; m.loc[60, "low"] = 99.0
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "stop_bps": 300, "take_bps": 500},
             {"decision_time": T0 + pd.Timedelta(minutes=30), "side": 1, "stop_bps": 300, "take_bps": 500}])
    r = run(s, m, exit_style="DETEXIT")
    reasons = r.trades.sort_values("exit_time").exit_reason.tolist()
    assert reasons == ["take", "breakeven"] and np.isclose(r.trades.units.sum(), 1.0)

def test_missing_gate_blocks_entry_not_exit():
    m = flat_minutes()
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1},
             {"decision_time": T0 + pd.Timedelta(minutes=30), "side": 0, "exit_long": True, "allow_entry": False},
             {"decision_time": T0 + pd.Timedelta(minutes=45), "side": 1, "allow_entry": False}])
    r = run(s, m)
    assert len(r.trades) == 1 and r.trades.exit_reason.iloc[0] == "flag"

def test_segment_boundary_mtm():
    m = flat_minutes(3000); m.loc[1500:, ["open", "high", "low", "close"]] = 110.0
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "max_hold_min": 2000}])
    r = reference.simulate(s, m, T0, T0 + pd.Timedelta(minutes=1000), reference.SimConfig(include_funding=False))
    assert np.isclose(r.minute_pnl.sum(), -2.0)       # only entry fee inside segment, price flat inside
    full = reference.simulate(s, m, T0, T0 + pd.Timedelta(days=3), reference.SimConfig(include_funding=False))
    assert np.isclose(full.minute_pnl.sum(), full.trades.net_bps.sum())

def test_oco_entry():
    m = flat_minutes(); m.loc[20, "high"] = 102.0
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 0, "entry": "oco",
              "upper": 101.0, "lower": 99.0, "expiry_min": 60}])
    t = run(s, m).trades.iloc[0]
    assert t.side == 1 and t.entry_price == 101.0 and t.entry_time == T0 + pd.Timedelta(minutes=20)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement `schema.py`**

```python
# btcusdt_quant/sim/schema.py
from __future__ import annotations
import pandas as pd

SIGNAL_COLUMNS = ["decision_time", "side", "entry", "upper", "lower", "expiry_min", "max_hold_min",
                  "stop_bps", "take_bps", "exit_long", "exit_short", "allow_entry"]

def validate(signals: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in SIGNAL_COLUMNS if c not in signals]
    if missing:
        raise ValueError(f"signal columns missing: {missing}")
    out = signals[SIGNAL_COLUMNS].copy()
    out["decision_time"] = pd.to_datetime(out.decision_time, utc=True)
    out = out.sort_values("decision_time").reset_index(drop=True)
    if out.decision_time.duplicated().any():
        raise ValueError("duplicate decision_time")
    if not out.side.isin([-1, 0, 1]).all() or not out.entry.isin(["market", "oco"]).all():
        raise ValueError("bad side or entry type")
    for c in ("exit_long", "exit_short", "allow_entry"):
        out[c] = out[c].astype(bool)
    out["side"] = out.side.astype(int)
    return out
```

- [ ] **Step 4: Implement `reference.py`** — a minute-by-minute loop that is deliberately simple:

```python
# btcusdt_quant/sim/reference.py
"""Slow, obvious reference simulator. Correctness over speed; core.py must match it."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np, pandas as pd
from . import costs, orders

@dataclass(frozen=True)
class SimConfig:
    delay_min: int = 1
    reentry: str = "strict"
    exit_style: str = "NATIVE"
    fee_per_side: float = 2.0
    funding_boundary: str = "PESS"
    stop_slippage_bps: float = 0.0
    include_funding: bool = True

@dataclass
class SimResult:
    trades: pd.DataFrame
    minute_pnl: pd.Series

@dataclass
class _Leg:
    units: float
    price: float
    time: pd.Timestamp
    decision: pd.Timestamp

@dataclass
class _Position:
    side: int
    legs: list = field(default_factory=list)
    max_hold_end: pd.Timestamp | None = None
    stop: float = math.nan
    take: float = math.nan
    took: bool = False
    stop_bps: float = math.nan
    take_bps: float = math.nan
    pending_add: bool = False

    @property
    def units(self) -> float:
        return sum(l.units for l in self.legs)

    @property
    def avg(self) -> float:
        return sum(l.units * l.price for l in self.legs) / self.units

def simulate(signals: pd.DataFrame, minutes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
             config: SimConfig) -> SimResult:
    if config.reentry not in ("strict", "stop_and_reverse") or config.exit_style not in ("NATIVE", "DETEXIT"):
        raise ValueError("bad config")
    t_index = pd.DatetimeIndex(minutes.open_time)
    o, h, l, c = (minutes[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    by_exec = {}
    for row in signals.itertuples(index=False):
        by_exec.setdefault(pd.Timestamp(row.decision_time) + pd.Timedelta(minutes=config.delay_min), []).append(row)
    pnl = np.zeros(len(minutes))
    trades: list[dict] = []
    pos: _Position | None = None
    pending_oco = None   # (row, expiry_time)

    def book_exit(i: int, units: float, price: float, reason: str) -> None:
        nonlocal pos
        remaining = units
        while remaining > 1e-12 and pos.legs:
            leg = pos.legs[0]; take_units = min(leg.units, remaining)
            gross = pos.side * math.log(price / leg.price) * 1e4 * take_units
            fee = costs.fee_bps(take_units, config.fee_per_side) * 2
            fund = (costs.funding_bps(pos.side, leg.time, t_index[i], config.funding_boundary) * take_units
                    if config.include_funding else 0.0)
            trades.append({"decision_time": leg.decision, "entry_time": leg.time, "exit_time": t_index[i],
                           "side": pos.side, "units": take_units, "entry_price": leg.price, "exit_price": price,
                           "exit_reason": reason, "gross_bps": gross, "fee_bps": fee, "funding_bps": fund,
                           "net_bps": gross - fee + fund})
            pnl[i] += -costs.fee_bps(take_units, config.fee_per_side) + fund
            pnl[i] += pos.side * math.log(price / o[i]) * 1e4 * take_units   # fill-minute move from open
            leg.units -= take_units; remaining -= take_units
            if leg.units <= 1e-12:
                pos.legs.pop(0)
        if not pos.legs:
            pos = None

    def open_leg(i: int, side: int, units: float, price: float, decision: pd.Timestamp, row) -> None:
        nonlocal pos
        if pos is None:
            pos = _Position(side=side, max_hold_end=t_index[i] + pd.Timedelta(minutes=int(row.max_hold_min)),
                            stop_bps=float(row.stop_bps), take_bps=float(row.take_bps),
                            pending_add=config.exit_style == "DETEXIT")
        pos.legs.append(_Leg(units, price, t_index[i], decision))
        pnl[i] += -costs.fee_bps(units, config.fee_per_side)
        pnl[i] += side * math.log(c[i] / price) * 1e4 * units          # entry-minute mark to close
        if config.exit_style == "DETEXIT" and not math.isnan(pos.stop_bps):
            pos.stop = pos.avg * (1 - pos.side * pos.stop_bps / 1e4)
            pos.take = pos.avg * (1 + pos.side * pos.take_bps / 1e4) if not pos.took else math.nan

    for i, now in enumerate(t_index):
        held_at_open = pos is not None
        if pos is not None and i > 0:
            pnl[i] += pos.side * math.log(o[i] / c[i - 1]) * 1e4 * pos.units   # overnight gap mark
        # 1) stop / take touches
        if pos is not None and not math.isnan(pos.stop):
            hit = orders.exit_touch(pos.side, pos.stop, pos.take if not math.isnan(pos.take) else
                                    (1e18 if pos.side == 1 else -1e18), o[i], h[i], l[i])
            if hit is not None:
                kind, price = hit
                if kind == "stop":
                    price *= (1 - pos.side * config.stop_slippage_bps / 1e4)
                    book_exit(i, pos.units, price, "breakeven" if pos.took else "stop")
                else:
                    book_exit(i, pos.units / 2, price, "take")
                    pos.took = True; pos.stop = pos.avg; pos.take = math.nan
        # 2) max hold
        if pos is not None and pos.max_hold_end is not None and now >= pos.max_hold_end:
            book_exit(i, pos.units, o[i], "max_hold")
        # 3) decisions executing this minute
        rows = by_exec.get(now, [])
        exited_now = False
        for row in rows:
            if pos is not None:
                reverse = row.side == -pos.side
                flag = (row.exit_long and pos.side == 1) or (row.exit_short and pos.side == -1)
                if reverse or flag:
                    book_exit(i, pos.units, o[i], "reverse" if reverse else "flag")
                    exited_now = True
                elif pos.pending_add and row.side == pos.side and not pos.took and row.allow_entry:
                    open_leg(i, pos.side, .5, o[i], pd.Timestamp(row.decision_time), row)
                    pos.pending_add = False
                    continue
                elif pos is not None:
                    pos.pending_add = False
            blocked = pos is not None or (config.reentry == "strict" and (held_at_open or exited_now))
            if not blocked and row.allow_entry and row.side != 0 and row.entry == "market":
                open_leg(i, int(row.side), .5 if config.exit_style == "DETEXIT" else 1.0, o[i],
                         pd.Timestamp(row.decision_time), row)
            elif not blocked and row.allow_entry and row.entry == "oco":
                pending_oco = (row, now + pd.Timedelta(minutes=int(row.expiry_min)))
        # 4) pending OCO
        if pos is None and pending_oco is not None:
            row, expiry = pending_oco
            if now >= expiry:
                pending_oco = None
            else:
                hit = orders.fill_oco(float(row.upper), float(row.lower), o[i], h[i], l[i])
                if hit is not None:
                    side, price = hit
                    open_leg(i, side, .5 if config.exit_style == "DETEXIT" else 1.0, price,
                             pd.Timestamp(row.decision_time), row)
                    pending_oco = None
        # 5) mark held position from open to close for legs older than this minute
        if pos is not None:
            for leg in pos.legs:
                if leg.time < now:
                    pnl[i] += pos.side * math.log(c[i] / o[i]) * 1e4 * leg.units
    series = pd.Series(pnl, index=t_index)
    inside = (series.index >= start) & (series.index < end)
    trade_frame = pd.DataFrame(trades)
    return SimResult(trades=trade_frame, minute_pnl=series.loc[inside])
```

Note for the implementer: if `test_segment_boundary_mtm` or the ledger identity fails, fix the ledger so that each unit's P&L is the sum over its holding minutes of `side·log(next mark / previous mark)` with the first mark = fill price and the last mark = exit price; fees at fill minutes; funding at the exit minute. Keep the code obvious — this file is the oracle.

- [ ] **Step 5: Run, expect PASS** for all 7 tests, then add `test_ledger_identity_random` (Task 8 also covers it with hypothesis). Record changed files.

---

### Task 7: numba core with differential test against the reference (A1, C1)

**Files:**
- Create: `btcusdt_quant/sim/core.py`
- Test: `tests/sim/test_core_differential.py`

**Interfaces:**
- Consumes: `schema.validate`, `reference.SimConfig`, `reference.simulate` (oracle).
- Produces: `core.simulate(signals, minutes, start, end, config) -> reference.SimResult` with identical semantics; internally converts to numpy arrays and runs `@numba.njit` `_loop(...)`; funding is added after the loop by calling `costs.funding_bps` per closed leg (not inside numba).

- [ ] **Step 1: Write the failing differential test**

```python
# tests/sim/test_core_differential.py
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, reference, schema

def random_case(seed):
    rng = np.random.default_rng(seed)
    n = 3000
    t = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 8e-4, n)))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 2e-4, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 4e-4, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 4e-4, n)))
    m = pd.DataFrame({"open_time": t, "open": open_, "high": high, "low": low, "close": close, "volume": 1.,
                      "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .5})
    d = t[15::15][:150]
    side = rng.choice([-1, 0, 0, 1], len(d))
    s = schema.validate(pd.DataFrame({"decision_time": d, "side": side, "entry": "market", "upper": np.nan,
        "lower": np.nan, "expiry_min": 0, "max_hold_min": rng.choice([60, 240, 720], len(d)),
        "stop_bps": rng.choice([np.nan, 50.0, 150.0], len(d)), "take_bps": 100.0,
        "exit_long": rng.random(len(d)) < .1, "exit_short": rng.random(len(d)) < .1,
        "allow_entry": rng.random(len(d)) > .05}))
    return s, m

@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("exit_style", ["NATIVE", "DETEXIT"])
@pytest.mark.parametrize("reentry", ["strict", "stop_and_reverse"])
def test_core_matches_reference(seed, exit_style, reentry):
    s, m = random_case(seed)
    cfg = reference.SimConfig(include_funding=False, exit_style=exit_style, reentry=reentry)
    a = reference.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    b = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    pd.testing.assert_frame_equal(a.trades.reset_index(drop=True), b.trades.reset_index(drop=True), atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9)
```

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: core`).

- [ ] **Step 3: Implement `core.py`** by translating `reference.simulate` loop line for line into an `@numba.njit` function over numpy arrays: inputs `o,h,l,c` (float64), per-minute decision slots (`exec_index` int64 array of decisions mapped to minute index, `side`, `entry_code` 0=market 1=oco, `upper`, `lower`, `expiry_min`, `max_hold_min`, `stop_bps`, `take_bps`, `exit_long`, `exit_short`, `allow_entry`), config ints (`reentry_code`, `detexit`), floats (`fee_per_side`, `stop_slip`). Outputs: preallocated arrays for up to `4*len(decisions)` closed legs (entry index, exit index, side, units, entry price, exit price, reason code 0..5 = stop, breakeven, take, max_hold, reverse, flag) and the `pnl` minute array. Python wrapper builds `trades` DataFrame with the same columns and dtypes as reference, adds funding per leg with `costs.funding_bps` when `include_funding`, and slices `minute_pnl` to `[start, end)`. Reason strings map `["stop","breakeven","take","max_hold","reverse","flag"]`. Keep identical floating-point operation order to the reference so results match to 1e-9.

- [ ] **Step 4: Run, expect PASS (80 cases).**
- [ ] **Step 5: Speed check** — Run: `venv_btcusdt\Scripts\python.exe -c "import time,numpy as np,pandas as pd; from tests.sim.test_core_differential import random_case; from btcusdt_quant.sim import core, reference; s,m=random_case(0); cfg=reference.SimConfig(include_funding=False); core.simulate(s,m,m.open_time.iloc[0],m.open_time.iloc[-1],cfg); t=time.perf_counter(); core.simulate(s,m,m.open_time.iloc[0],m.open_time.iloc[-1],cfg); a=time.perf_counter()-t; t=time.perf_counter(); reference.simulate(s,m,m.open_time.iloc[0],m.open_time.iloc[-1],cfg); b=time.perf_counter()-t; print(a,b,b/a)"`. Expected: core at least 20× faster. Record numbers. Record changed files.

---

### Task 8: Property-based tests (A2) and mutation testing (A3)

**Files:**
- Create: `tests/sim/test_properties.py`
- Modify: `setup.cfg` (add `[mutmut]` section; create file if absent)

**Interfaces:**
- Consumes: `reference.simulate`, `core.simulate`, `schema.validate`.

- [ ] **Step 1: Write property tests**

```python
# tests/sim/test_properties.py
import numpy as np, pandas as pd
from hypothesis import given, settings, strategies as st
from btcusdt_quant.sim import core, reference
from tests.sim.test_core_differential import random_case

@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 10_000), exit_style=st.sampled_from(["NATIVE", "DETEXIT"]),
       reentry=st.sampled_from(["strict", "stop_and_reverse"]))
def test_invariants(seed, exit_style, reentry):
    s, m = random_case(seed)
    cfg = reference.SimConfig(include_funding=False, exit_style=exit_style, reentry=reentry)
    r = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg)
    if len(r.trades):
        # ledger identity
        assert np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum(), atol=1e-6)
        # never more than one unit, never entry before its decision + delay
        assert (r.trades.entry_time >= r.trades.decision_time + pd.Timedelta(minutes=1)).all()
        assert (r.trades.exit_time >= r.trades.entry_time).all()
        # strict: no new position decided while another position was open at that decision time
        if reentry == "strict":
            spans = r.trades.groupby("decision_time").agg(start=("entry_time", "min"), end=("exit_time", "max"))
            for decision, row in spans.iterrows():
                others = spans.drop(index=decision)
                overlap = (others.start <= decision) & (decision < others.end)
                assert not overlap.any(), f"entry decided at {decision} while held"

Implementer note: `spans` groups legs by their own `decision_time`, so DETEXIT add-on legs (decided inside their own position) form their own group; exclude groups whose `decision_time` equals an add-on leg's decision before asserting (an add-on leg has the same `side` and an `entry_time` later than the first leg of the overlapping span).

- [ ] **Step 2: Run, expect PASS.**

Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/sim/test_properties.py -q`

- [ ] **Step 3: Mutation config**

```ini
# setup.cfg
[mutmut]
paths_to_mutate=btcusdt_quant/sim/orders.py,btcusdt_quant/sim/reference.py,btcusdt_quant/sim/schema.py
tests_dir=tests/sim
runner=venv_btcusdt\Scripts\python.exe -m pytest tests/sim -x -q
```

- [ ] **Step 4: Run mutation testing**

Run: `venv_btcusdt\Scripts\mutmut.exe run` then `venv_btcusdt\Scripts\mutmut.exe results`
Expected: killed ≥ 90% of mutants in `orders.py` and `reference.py`. For each surviving mutant, add a test that kills it (show the mutant diff and the new test in the task report). Record changed files.

---

### Task 9: Intrabar ordering sensitivity (B1)

**Files:**
- Create: `btcusdt_quant/sim/intrabar.py`
- Test: `tests/sim/test_intrabar.py`

**Interfaces:**
- Produces: `intrabar.first_touch_probability(o, h, l, c, stop, take, side, n_paths=200, seed=0) -> float` — probability the stop is hit before the take under a Brownian bridge constrained to the bar's open/close and to stay within [l, h] (rejection sampling on 60 sub-steps); `intrabar.resimulate_ambiguous(trades: DataFrame, minutes: DataFrame, seed) -> DataFrame` replaces each `exit_reason=="stop"` trade whose minute also touched the take with a random draw (take with probability 1 − p) and returns adjusted net_bps for sensitivity reporting.

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_intrabar.py
from btcusdt_quant.sim import intrabar

def test_symmetric_bar_near_half():
    p = intrabar.first_touch_probability(100, 101, 99, 100, stop=99, take=101, side=1, n_paths=2000)
    assert .35 < p < .65

def test_close_at_high_favours_take_last():
    p = intrabar.first_touch_probability(100, 101, 99, 101, stop=99, take=101, side=1, n_paths=2000)
    assert p > .5   # path ends at high, so the low (stop) was more likely reached first
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```python
# btcusdt_quant/sim/intrabar.py
from __future__ import annotations
import numpy as np, pandas as pd

def _bridge(o, c, steps, rng):
    w = np.cumsum(rng.normal(0, 1, steps)); w -= np.linspace(0, 1, steps) * w[-1]
    scale = max(abs(c - o), 1e-12)
    return o + (c - o) * np.linspace(0, 1, steps) + w / np.sqrt(steps) * scale

def first_touch_probability(o, h, l, c, stop, take, side, n_paths=200, seed=0) -> float:
    rng = np.random.default_rng(seed); stop_first = accepted = 0
    for _ in range(n_paths * 20):
        if accepted >= n_paths:
            break
        p = _bridge(o, c, 60, rng)
        p = l + (p - p.min()) / max(p.max() - p.min(), 1e-12) * (h - l)   # map to observed range
        hit_stop = np.argmax(p <= stop) if side == 1 and (p <= stop).any() else (
            np.argmax(p >= stop) if side == -1 and (p >= stop).any() else None)
        hit_take = np.argmax(p >= take) if side == 1 and (p >= take).any() else (
            np.argmax(p <= take) if side == -1 and (p <= take).any() else None)
        if hit_stop is None or hit_take is None:
            continue
        accepted += 1; stop_first += hit_stop <= hit_take
    return stop_first / accepted if accepted else 1.0

def resimulate_ambiguous(trades: pd.DataFrame, minutes: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed); out = trades.copy()
    bar = minutes.set_index("open_time")
    for i, t in out.loc[out.exit_reason.eq("stop")].iterrows():
        row = bar.loc[t.exit_time]
        take = t.entry_price * (1 + t.side * t.get("take_bps", np.nan) / 1e4)
        if np.isnan(take) or not ((t.side == 1 and row.high >= take) or (t.side == -1 and row.low <= take)):
            continue
        p = first_touch_probability(row.open, row.high, row.low, row.close, t.exit_price, take, t.side)
        if rng.random() > p:
            gross = t.side * np.log(take / t.entry_price) * 1e4 * t.units
            out.loc[i, ["exit_price", "exit_reason", "gross_bps"]] = [take, "take_resampled", gross]
            out.loc[i, "net_bps"] = gross - t.fee_bps + t.funding_bps
    return out
```

- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 10: Analytics (D3)

**Files:**
- Create: `btcusdt_quant/sim/analytics.py`
- Test: `tests/sim/test_analytics.py`

**Interfaces:**
- Produces (every function returns a dict with `value`/`lower`/`p`/`reason`, never raises on degenerate input):
  - `pw_mean_ci(x, reps=2000, seed=0) -> {"mean","lower","upper","block","reason"}` (stationary bootstrap, Politis–White block length)
  - `hac_mean_ci(x, lag=7) -> {"mean","lower","upper","reason"}` (Newey–West)
  - `deflated_sharpe(x, trial_sharpes: ndarray, n_trials: int) -> {"sr","dsr","reason"}` (Bailey–López de Prado; variance of trial Sharpes from `trial_sharpes`)
  - `cscv_pbo(matrix: DataFrame, splits=16) -> {"pbo","n_strategies","reason"}` (drops duplicate columns first)
  - `white_rc(diff: ndarray[T,K], reps=2000, seed=0) -> {"p","reason"}`
  - `hansen_spa(diff: ndarray[T,K], reps=2000, seed=0) -> {"p","reason"}` (consistent SPA: recentring with threshold `-sqrt(2 log log T)·σ/√T`, studentized)
  - `trade_monte_carlo(net: ndarray, reps=10000, seed=0) -> {"final_q05","final_median","final_q95","dd_median","dd_q95","loss_prob"}`

- [ ] **Step 1: Write failing tests with known answers**

```python
# tests/sim/test_analytics.py
import numpy as np, pandas as pd
from btcusdt_quant.sim import analytics

def test_degenerate_inputs_do_not_raise():
    for f in (analytics.pw_mean_ci, analytics.hac_mean_ci):
        assert f(np.zeros(10))["reason"] == "zero_variance"
        assert f(np.array([]))["reason"] == "empty"
    assert analytics.white_rc(np.zeros((50, 3)))["reason"] == "constant"

def test_hac_mean_matches_simple_mean_and_covers_truth():
    x = np.random.default_rng(1).normal(1.0, 1.0, 5000)
    r = analytics.hac_mean_ci(x)
    assert abs(r["mean"] - x.mean()) < 1e-12 and r["lower"] < 1.0 < r["upper"]

def test_spa_and_white_reject_strong_signal_and_not_noise():
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 1, (1000, 5)); strong = noise.copy(); strong[:, 0] += .3
    assert analytics.white_rc(strong)["p"] < .05 and analytics.hansen_spa(strong)["p"] < .05
    assert analytics.hansen_spa(noise)["p"] > .05

def test_spa_not_more_conservative_than_white_with_bad_models():
    rng = np.random.default_rng(3)
    d = rng.normal(0, 1, (800, 6)); d[:, 0] += .12; d[:, 1:] -= 1.0
    assert analytics.hansen_spa(d)["p"] <= analytics.white_rc(d)["p"] + 1e-9

def test_pbo_drops_duplicate_columns_and_flags_overfit():
    rng = np.random.default_rng(4)
    m = pd.DataFrame(rng.normal(0, 1, (400, 10)))
    m[10] = m[0]
    r = analytics.cscv_pbo(m, splits=8)
    assert r["n_strategies"] == 10 and .2 < r["pbo"] < .8

def test_dsr_penalises_many_trials():
    x = np.random.default_rng(5).normal(.05, 1, 1000)
    trials = np.random.default_rng(6).normal(0, .03, 500)
    assert analytics.deflated_sharpe(x, trials, 5000)["dsr"] < analytics.deflated_sharpe(x, trials, 2)["dsr"]

def test_monte_carlo_quantiles_ordered():
    r = analytics.trade_monte_carlo(np.array([10., -5., 3., -1.]), reps=2000)
    assert r["final_q05"] <= r["final_median"] <= r["final_q95"]
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** each function with scipy/numpy:
  - PW block length via the Politis–White (2004, corrected 2009) automatic selector on the series; stationary bootstrap with geometric block lengths of that mean.
  - HAC: Bartlett kernel, `lag` given; CI = mean ± 1.96·sqrt(HAC variance / T).
  - DSR: `SR0 = sqrt(V)·((1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e)))`, `V = var(trial_sharpes)`, then `Φ((SR−SR0)·sqrt(T−1)/sqrt(1−skew·SR+(kurt−1)/4·SR²))`; reasons `zero_variance`, `too_short` (<30).
  - CSCV: split rows into `splits` contiguous blocks, all combinations of half; in-sample best column's out-of-sample rank → logit; PBO = share of logits ≤ 0. Drop duplicate columns with `matrix.T.drop_duplicates().T`.
  - White RC: statistic `max_k sqrt(T)·mean_k`; bootstrap recentred by sample means; p = share of bootstrap max ≥ observed.
  - Hansen SPA: studentize each column by its HAC std; recentre with `μ_k·1{μ_k·sqrt(T)/σ_k ≥ −sqrt(2·log log T)}` (consistent version); statistic `max(0, max_k sqrt(T)·μ_k/σ_k)`.
  - Every function: return `reason="empty"` for empty input, `"zero_variance"`/`"constant"` when std is 0, `"ok"` otherwise.
- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 11: Feature store (C3), registry (D1), result guard (D2)

**Files:**
- Create: `btcusdt_quant/sim/store.py`, `btcusdt_quant/sim/registry.py`, `btcusdt_quant/sim/guard.py`
- Test: `tests/sim/test_store_registry_guard.py`

**Interfaces:**
- Produces:
  - `store.key(name: str, params: dict, inputs: dict) -> str` (sha256 of canonical JSON)
  - `store.get_or_build(root: Path, name, params, inputs, build: Callable[[], DataFrame]) -> DataFrame` (reads `root/<name>/<key>.parquet` if present else builds and writes atomically; writes `<key>.json` with params and inputs)
  - `registry.record(path: Path, entry: dict) -> None` (appends one JSON line with `experiment, timestamp_utc, config_hash, input_hashes, n_trials, result_summary`)
  - `registry.cumulative_trials(path: Path, base: int = 5125) -> int`
  - `guard.check(report: dict) -> None` raising `ValueError` when any strategy has `trade_n == 0` without `zero_reason`, any diagnostic value is a bare string label, or any required metric is NaN without a reason.

- [ ] **Step 1: Write failing tests**

```python
# tests/sim/test_store_registry_guard.py
import pandas as pd, pytest
from btcusdt_quant.sim import guard, registry, store

def test_store_builds_once(tmp_path):
    calls = []
    def build():
        calls.append(1); return pd.DataFrame({"a": [1]})
    a = store.get_or_build(tmp_path, "f", {"n": 1}, {"m": "h"}, build)
    b = store.get_or_build(tmp_path, "f", {"n": 1}, {"m": "h"}, build)
    assert len(calls) == 1 and a.equals(b)
    store.get_or_build(tmp_path, "f", {"n": 2}, {"m": "h"}, build)
    assert len(calls) == 2

def test_registry_counts(tmp_path):
    path = tmp_path / "reg.jsonl"
    registry.record(path, {"experiment": "x", "n_trials": 3})
    registry.record(path, {"experiment": "y", "n_trials": 5})
    assert registry.cumulative_trials(path, base=10) == 18

def test_guard_rejects_label_and_silent_zero():
    with pytest.raises(ValueError, match="label"):
        guard.check({"diagnostics": {"d": "semiannual_yearly_and_rolling_90d"}, "strategies": []})
    with pytest.raises(ValueError, match="zero trades"):
        guard.check({"diagnostics": {}, "strategies": [{"id": "K01", "trade_n": 0}]})
    guard.check({"diagnostics": {"d": {"value": 1.0}}, "strategies": [{"id": "K01", "trade_n": 0, "zero_reason": "no signal in segment"}]})
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** (canonical JSON `json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)`; atomic write via `tmp` + `replace`; guard walks `diagnostics` values and rejects any `str` value; rejects strategies with `trade_n == 0` lacking `zero_reason`; rejects `float('nan')` metrics lacking a sibling `*_reason`).
- [ ] **Step 4: Run, expect PASS.** Record changed files.

---

### Task 12: C1_X reproduction pre-check

**Files:**
- Create: `scripts/sim_c1x_parity.py`
- Test: `tests/sim/test_c1x_parity.py` (marked `@pytest.mark.slow`, runs the script)

**Interfaces:**
- Consumes: `out/run_k45_short_router_r2_39.py` (`load_market`, `load_funding`, `build_signals(bars, funding)`, hourly bars as R2-39 builds them), `core.simulate`, `reference.SimConfig(reentry="stop_and_reverse")`, reference trades `out/k45_short_router_r2_39_20261006/baseline_trades.parquet` (`policy=="C1_X"`).
- Produces: `out/sim_parity_20261007/c1x_parity.json` with `{"passed", "n_expected", "n_actual", "max_abs_diff_net_bps", "first_mismatch"}`.

- [ ] **Step 1: Write the script** — load R2-39 module by path; build its hourly bars and signals exactly as its `run` does (`signals["F3"]`, `signals["E1"]`); convert to the sim signal table: for each decision time, `side = F3 if F3 != 0 else E1`, `max_hold_min = 1440 if F3 chosen else 1200`, `exit_long/exit_short` = F3 reverse flags (`F3 == -1` closes a long F3 position, `F3 == 1` closes a short — only when the held component is F3; encode by emitting `side = F3` on rows where F3 != 0 so the simulator's reverse rule applies, and `side = E1` rows only when F3 == 0); `reentry="stop_and_reverse"`, `delay_min=1`, `include_funding=True`, boundary `PESS`. Run `core.simulate` over the full history; compare per-trade `entry_time, exit_time, side, entry_price, exit_price, net_bps` to the reference rows.

Implementer note: R2-39 only lets F3 reverse an F3 position (E1 positions exit only by max-hold). If the generic reverse rule makes an E1 position close on an F3 −1 signal, add a per-row `exit_long/exit_short` encoding instead (set `side=0`, `exit_*` only when the held component is F3) — this requires tracking the component, so add an optional `component` column to the signal table and a `reverse_components` config tuple (default: all). Document the change in `schema.py` and add a unit test.

- [ ] **Step 2: Write the test**

```python
# tests/sim/test_c1x_parity.py
import json, subprocess, sys
from pathlib import Path
import pytest

@pytest.mark.slow
def test_c1x_parity_exact():
    subprocess.run([sys.executable, "scripts/sim_c1x_parity.py"], check=True)
    result = json.loads(Path("out/sim_parity_20261007/c1x_parity.json").read_text(encoding="utf-8"))
    assert result["passed"] and result["n_actual"] == result["n_expected"]
    assert result["max_abs_diff_net_bps"] < 1e-6
```

- [ ] **Step 3: Run** `venv_btcusdt\Scripts\python.exe -m pytest tests/sim/test_c1x_parity.py -q -m slow`. Expected PASS with `n_expected` equal to the number of C1_X rows in the reference parquet (DEV subset alone is 367 trades, 9,230.67 bps).
- [ ] **Step 4: Full suite** — Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/sim -q` (include slow). All pass. Record changed files and the parity JSON in the task report.

---

## Self-Review Notes

- Spec §2.1 modules: data/provenance (T2), features via indicators+store (T3, T11), orders (T4), position/ledger (T6), fills B1 (T9) B2/B3/B4 (T5), core C1 (T7), analytics D3 (T10), registry D1 and guard D2 (T11). `vec_env` (C2) moves to Plan 3 because it wraps the RL action interface; `signals` (24 strategies) are Plan 2.
- Spec §2.2: A1 (T7 differential), A2 (T8), A3 (T8 mutmut), A4 paper parity is Plan 4, C1_X pre-check (T12).
- Review Focus tests live in T4 and T6.
