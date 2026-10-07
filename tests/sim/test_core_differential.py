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

@pytest.mark.parametrize("seed", range(4))
def test_core_matches_reference_oco_funding_slippage(seed):
    s, m = random_case(seed)
    rng = np.random.default_rng(100 + seed)
    oco = rng.random(len(s)) < .3
    mid = m.set_index("open_time").close.reindex(s.decision_time).to_numpy()
    s.loc[oco, "entry"] = "oco"
    s.loc[oco, "upper"] = mid[oco] * 1.002
    s.loc[oco, "lower"] = mid[oco] * 0.998
    s.loc[oco, "expiry_min"] = 30
    cfg = reference.SimConfig(include_funding=True, exit_style="DETEXIT", stop_slippage_bps=1.5)
    a = reference.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    b = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    assert len(a.trades) > 0 and (a.trades.funding_bps != 0).any()
    pd.testing.assert_frame_equal(a.trades.reset_index(drop=True), b.trades.reset_index(drop=True), atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9)

def test_random_cases_trade():
    s, m = random_case(0)
    r = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], reference.SimConfig(include_funding=False))
    assert len(r.trades) >= 10 and r.trades.exit_reason.nunique() >= 3

@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("exit_style", ["NATIVE", "DETEXIT"])
def test_core_matches_reference_multi_component(seed, exit_style):
    s, m = random_case(seed)
    rng = np.random.default_rng(200 + seed)
    extra = s.loc[rng.random(len(s)) < .2].copy()
    extra["component"] = 2
    extra["side"] = rng.choice([-1, 1], len(extra))
    s = schema.validate(pd.concat([s.assign(component=1), extra]).sort_values("decision_time", kind="stable"))
    cfg = reference.SimConfig(include_funding=False, exit_style=exit_style, reentry="stop_and_reverse")
    a = reference.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    b = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], cfg)
    pd.testing.assert_frame_equal(a.trades.reset_index(drop=True), b.trades.reset_index(drop=True), atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9)
