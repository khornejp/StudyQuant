import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, reference, schema
from tests.sim.test_reference import flat_minutes, T0

def _signals(rows):
    base = {"entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 240,
            "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True}
    return schema.validate(pd.DataFrame([{**base, **r} for r in rows]))

@pytest.mark.parametrize("simulate", [reference.simulate, core.simulate])
def test_only_same_component_reverses(simulate):
    m = flat_minutes()
    s = _signals([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "component": 2},
                  {"decision_time": T0 + pd.Timedelta(minutes=30), "side": -1, "component": 1},
                  {"decision_time": T0 + pd.Timedelta(minutes=45), "side": -1, "component": 2}])
    r = simulate(s, m, T0, T0 + pd.Timedelta(days=1), reference.SimConfig(include_funding=False))
    first = r.trades.iloc[0]
    assert first.exit_reason == "reverse" and first.exit_time == T0 + pd.Timedelta(minutes=46)

def test_component_defaults_to_zero():
    s = _signals([{"decision_time": T0, "side": 1}])
    assert (s.component == 0).all()
