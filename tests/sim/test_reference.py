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

@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("exit_style", ["NATIVE", "DETEXIT"])
def test_ledger_identity_random(seed, exit_style):
    rng = np.random.default_rng(seed)
    m = flat_minutes(2000)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(m))))
    open_ = np.r_[100.0, close[:-1]]
    m["open"], m["close"] = open_, close
    m["high"] = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 5e-4, len(m))))
    m["low"] = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 5e-4, len(m))))
    rows = [{"decision_time": T0 + pd.Timedelta(minutes=15 * k), "side": int(rng.choice([-1, 0, 1])),
             "stop_bps": 30.0, "take_bps": 60.0, "max_hold_min": int(rng.choice([30, 120]))} for k in range(1, 120)]
    r = reference.simulate(sig(rows), m, T0, T0 + pd.Timedelta(days=3),
                           reference.SimConfig(include_funding=False, exit_style=exit_style))
    assert len(r.trades) > 5
    assert np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum(), atol=1e-9)

def test_stop_exit_at_level_without_slippage_by_default():
    m = flat_minutes(); m.loc[30, "low"] = 90.0
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1, "stop_bps": 500, "take_bps": 900}])
    t = run(s, m, exit_style="DETEXIT").trades.iloc[0]
    assert t.exit_reason == "stop" and np.isclose(t.exit_price, 100 * np.exp(-.05))   # R2-46 log levels

def test_bad_config_rejected():
    m = flat_minutes(); s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 1}])
    for kw in ({"reentry": "loose"}, {"exit_style": "OTHER"}):
        with pytest.raises(ValueError, match="bad config"):
            run(s, m, **kw)

def test_oco_not_filled_at_expiry_minute_and_full_unit():
    m = flat_minutes(); m.loc[76, "high"] = 102.0          # expiry = 16 + 60 = minute 76
    s = sig([{"decision_time": T0 + pd.Timedelta(minutes=15), "side": 0, "entry": "oco",
              "upper": 101.0, "lower": 99.0, "expiry_min": 60}])
    assert run(s, m).trades.empty
    m.loc[75, "high"] = 102.0
    t = run(s, m).trades.iloc[0]
    assert t.entry_time == T0 + pd.Timedelta(minutes=75) and t.units == 1.0

def test_position_opened_at_first_minute_marks_gap():
    m = flat_minutes(); m.loc[1:, ["open", "high", "low", "close"]] = 101.0
    s = sig([{"decision_time": T0 - pd.Timedelta(minutes=1), "side": 1, "max_hold_min": 60}])
    r = run(s, m)
    assert r.trades.entry_time.iloc[0] == T0
    assert np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum())

def test_schema_rejects_bad_side():
    with pytest.raises(ValueError, match="bad side"):
        sig([{"decision_time": T0, "side": 2}])
