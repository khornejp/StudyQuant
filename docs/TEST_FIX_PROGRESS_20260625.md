# Test Fix Progress Report

## Date: 2026-06-25
## Commit: a80816f (base) + test fixes

---

## Fixes Applied

### 1. `backtest.py` — Missing `feature_rows` parameter
- **Issue**: `compare_strategies()` referenced `feature_rows` internally but it was not in the function signature, causing `UnboundLocalError`.
- **Fix**: Added `feature_rows: Sequence[dataset.FeatureRow] | None = None` parameter to the signature.

### 2. `fast_features.py` — Missing F14/F15 features
- **Issue**: After adding 22 new scalping features (F14 Time/Session + F15 Momentum) to `feature_registry.py` and `dataset.py`, `fast_features.py` still only computed the original 115 features. When `compute_features_fast()` tried to select columns via `FEATURE_NAMES` (now 137 features), a `KeyError` occurred.
- **Fix**: Added complete F14/F15 vectorized computation to `compute_features_fast()`:
  - F14: `hour`, `minute`, `day_of_week`, `session_asia/europe/us/overlap`, `weekend_flag`
  - F15: `rsi_7/14`, `macd_line/signal/hist`, `bb_width_20`, `bb_percent_b`, `ema_5/20/60_slope`, `rolling_vwap_20/60`, `price_vs_rolling_vwap_20/60`

### 3. `tests/test_v718.py` — Category count expectation
- **Issue**: `test_all_categories_f01_through_f12_present` asserted only F01-F13 exist.
- **Fix**: Updated test name and assertion to expect F01-F15.

### 4. `tests/test_core.py` — Category count expectation
- **Issue**: `test_feature_registry_has_categories` asserted only F01-F13 exist.
- **Fix**: Updated assertion to expect F01-F15.

### 5. `btcusdt_quant/dataset.py` — `bb_percent_b` warmup value
- **Issue**: During warmup period (`index + 1 < window`), `_bb_series()` appended `0.5` for `bb_percent_b`. The test `test_build_feature_rows_handles_all_nan_features` expects `0.0` or `NaN` when inputs are invalid.
- **Fix**: Changed warmup fallback from `0.5` to `0.0`.

### 6. `tests/test_v718.py` — Backtest cooldown default
- **Issue**: `test_backtest_cost_impact_scales_with_trade_count` created only 20 candles and expected >=10 trades. But `run_backtest()` default `cooldown_bars=30` caused re-entry to be blocked until bar 32, resulting in only 1 trade.
- **Fix**: Added `cooldown_bars=0` to the test's `run_backtest()` call.

### 7. `tests/test_core.py` — Small dataset horizon mismatch
- **Issue**: `test_build_dataset_from_archive` (30 rows) and `test_local_csv_dataset_builds_canonical_timeline` (17 rows) used default `horizon=60`. `attach_labels` skips rows where `future_index >= len(candles)`, so ALL rows were skipped, producing 0 labeled rows.
- **Fix**: Passed smaller `horizon` values (`horizon=10` and `horizon=5` respectively) appropriate for the small test datasets.
  - **Note**: These tests were already failing before Phase 0-3 changes (verified by checking out commit `1c0be6b`). They are pre-existing bugs, not regressions.

---

## Remaining Issues (Pre-existing / Not Regressions)

### Training split errors — "not enough labeled rows for configured split"
**Affected tests**:
- `test_optuna_enabled_produces_report`
- `test_optuna_model_factory_uses_params`
- `test_optuna_params_affect_artifacts`
- `test_end_to_end_default_cli_path_collect_train_live`
- `test_cli_advanced_args_wired_to_training`
- `test_cli_collect_train_live_pipeline`

**Root cause**: These tests collect `rows=240` fixture data, which yields ~180 labeled rows after feature warmup and label horizon. The `PurgedWalkForwardSplit` requires:
```
train_size (60) + purge_gap (60) + validation_size (22) + purge_gap (60) + test_size (22) = 224
```
Since 180 < 224, zero splits are generated → `ValueError`.

**Recommended fix**: Increase `rows=240` to `rows=500` (or higher) in these tests, OR pass a smaller `horizon` to `build_dataset()` in the test setup.

---

## Test Status Summary

| Fix | Status |
|-----|--------|
| `compare_strategies` parameter | Verified passing |
| `fast_features.py` F14/F15 | Verified passing |
| Category F01-F15 assertions | Verified passing |
| `bb_percent_b` warmup | Verified passing |
| Backtest cooldown | Verified passing |
| Small dataset horizon | Verified passing |
| Training split (6 tests) | Needs `rows=240` → `rows=500` |

---

## Files Modified

- `btcusdt_quant/backtest.py`
- `btcusdt_quant/dataset.py`
- `fast_features.py`
- `tests/test_core.py`
- `tests/test_v718.py`

## How to Continue

1. Apply `rows=500` (or `horizon=10`) to the 6 training tests listed above.
2. Run full test suite: `python -m unittest discover -s tests`
3. If all pass, commit and push.
