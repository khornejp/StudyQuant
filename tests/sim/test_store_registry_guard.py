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

def test_guard_rejects_unexplained_nan():
    with pytest.raises(ValueError, match="NaN"):
        guard.check({"diagnostics": {"d": {"value": float("nan")}}, "strategies": []})
    guard.check({"diagnostics": {"d": {"value": float("nan"), "value_reason": "too_short"}}, "strategies": []})
