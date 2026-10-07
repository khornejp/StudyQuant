import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, reference, schema
from tests.sim.test_reference import flat_minutes, T0

SIMS = [reference.simulate, core.simulate]
M = pd.Timedelta(minutes=1)

def sig(rows):
    base = {"entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 240,
            "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True,
            "component": 1}
    return schema.validate(pd.DataFrame([{**base, **r} for r in rows]))

def run(sim, s, m, **kw):
    return sim(s, m, T0, T0 + pd.Timedelta(days=1), reference.SimConfig(include_funding=False, **kw))

@pytest.mark.parametrize("sim", SIMS)
def test_multi_row_exits_before_entries(sim):
    s = sig([{"decision_time": T0, "side": 1, "component": 3},
             {"decision_time": T0 + 30 * M, "side": 1, "component": 1},       # priority row, cannot reverse
             {"decision_time": T0 + 30 * M, "side": -1, "component": 3}])     # reverses component 3
    t = run(sim, s, flat_minutes(), reentry="stop_and_reverse").trades
    assert t.exit_reason.iloc[0] == "reverse" and t.exit_time.iloc[0] == T0 + 31 * M
    assert t.side.iloc[1] == 1 and t.entry_time.iloc[1] == T0 + 31 * M      # priority row enters

def test_duplicate_decision_component_rejected():
    with pytest.raises(ValueError, match="duplicate decision"):
        sig([{"decision_time": T0, "side": 1}, {"decision_time": T0, "side": -1}])

@pytest.mark.parametrize("sim", SIMS)
def test_flag_only_from_same_component(sim):
    s = sig([{"decision_time": T0, "side": 1, "component": 2},
             {"decision_time": T0 + 15 * M, "side": 0, "component": 1, "exit_long": True},
             {"decision_time": T0 + 30 * M, "side": 0, "component": 2, "exit_long": True}])
    t = run(sim, s, flat_minutes()).trades
    assert len(t) == 1 and t.exit_reason.iloc[0] == "flag" and t.exit_time.iloc[0] == T0 + 31 * M

@pytest.mark.parametrize("sim", SIMS)
def test_no_max_hold_when_zero(sim):
    r = run(sim, sig([{"decision_time": T0, "side": 1, "max_hold_min": 0}]), flat_minutes())
    assert r.trades.empty and np.isclose(r.minute_pnl.sum(), -2.0)

@pytest.mark.parametrize("sim", SIMS)
def test_native_fixed_stop(sim):
    m = flat_minutes(); m.loc[40, "low"] = 98.0
    t = run(sim, sig([{"decision_time": T0, "side": 1, "stop_bps": 100}]), m).trades.iloc[0]
    assert t.exit_reason == "stop" and np.isclose(t.exit_price, 100 * np.exp(-0.01))

@pytest.mark.parametrize("sim", SIMS)
def test_detexit_exp_levels_and_harmonic_avg(sim):
    m = flat_minutes(); m.loc[20:, ["open", "high", "low", "close"]] = 110.0; m.loc[60, "low"] = 90.0
    s = sig([{"decision_time": T0, "side": 1, "stop_bps": 500, "take_bps": 5000},
             {"decision_time": T0 + 30 * M, "side": 1, "stop_bps": 500, "take_bps": 5000}])
    t = run(sim, s, m, exit_style="DETEXIT").trades
    avg = 1 / (.5 / 100 + .5 / 110)
    assert set(t.exit_reason) == {"stop"} and np.allclose(t.exit_price, avg * np.exp(-.05))

@pytest.mark.parametrize("sim", SIMS)
def test_detexit_checks_entry_minute(sim):
    m = flat_minutes(); m.loc[1, "low"] = 90.0
    t = run(sim, sig([{"decision_time": T0, "side": 1, "stop_bps": 300, "take_bps": 300}]), m,
            exit_style="DETEXIT").trades
    assert t.exit_reason.tolist() == ["stop"] and t.exit_time.iloc[0] == T0 + M

@pytest.mark.parametrize("sim", SIMS)
def test_detexit_same_minute_breakeven_after_take(sim):
    m = flat_minutes(); m.loc[30, "high"] = 106.0; m.loc[30, "low"] = 99.0
    t = run(sim, sig([{"decision_time": T0, "side": 1, "stop_bps": 500, "take_bps": 500}]), m,
            exit_style="DETEXIT").trades
    assert t.exit_reason.tolist() == ["take", "breakeven"] and (t.exit_time == T0 + 30 * M).all()
    assert np.isclose(t.exit_price.iloc[1], 100.0)

@pytest.mark.parametrize("sim", SIMS)
@pytest.mark.parametrize("side", [1, -1])
def test_same_minute_breakeven_at_exact_average(sim, side):
    m = flat_minutes()
    if side == 1:
        m.loc[30, "high"] = 106.0; m.loc[30, "low"] = 100.0          # low touches the average exactly
    else:
        m.loc[30, "low"] = 94.0; m.loc[30, "high"] = 100.0
    t = run(sim, sig([{"decision_time": T0, "side": side, "stop_bps": 500, "take_bps": 500}]), m,
            exit_style="DETEXIT").trades
    assert t.exit_reason.tolist() == ["take", "breakeven"]

def test_core_reports_open_position():
    r = run(core.simulate, sig([{"decision_time": T0, "side": -1, "max_hold_min": 0}]), flat_minutes())
    p = r.open_position
    assert p["side"] == -1 and p["units"] == 1.0 and p["entry_time"] == T0 + M and p["max_hold_end"] is None
    closed = run(core.simulate, sig([{"decision_time": T0, "side": 1, "max_hold_min": 30}]), flat_minutes())
    assert closed.open_position is None
