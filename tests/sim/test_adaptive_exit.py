"""R2-52A adaptive exit policy (freeze out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json): hand cases on both
simulators plus a core/reference differential."""
import math
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, costs, reference, schema

T0 = pd.Timestamp("2024-01-01", tz="UTC")
MODS = pytest.mark.parametrize("mod", [reference, core], ids=["reference", "core"])
OHLC = ["open", "high", "low", "close"]


def flat(n=200, price=100.0, start=T0):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    p = np.full(n, price)
    return pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p, "volume": 1.,
                         "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .5})


def sig(rows, t0=T0):
    base = {"entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 30,
            "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True,
            "e0_bps": 100.0, "k": 1.0, "anchor_upper": np.nan, "anchor_lower": np.nan, "anchor_price": np.nan}
    return schema.validate(pd.DataFrame([{**base, **r, "decision_time": t0 + pd.Timedelta(minutes=r["at"])}
                                         for r in rows]).drop(columns="at"))


def run(mod, s, m, e=None, **kw):
    cfg = reference.SimConfig(**{"include_funding": False, "exit_policy": "R2_52A", **kw})
    return mod.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg, e_bps=e)


def at(k, t0=T0):
    return t0 + pd.Timedelta(minutes=k)


def ledger_ok(r):
    return np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum(), atol=1e-9)


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_hard_stop_touch_and_gap(mod, side):
    m = flat(); m.loc[30, "low" if side == 1 else "high"] = 100 * math.exp(-side * .02)
    t = run(mod, sig([{"at": 15, "side": side}]), m).trades.iloc[0]
    assert t.entry_time == at(16) and t.entry_price == 100.0              # delay 1: decision 15 fills at open 16
    assert t.exit_time == at(30) and t.exit_reason == "stop" and np.isclose(t.exit_price, 100 * math.exp(-side * .01))
    m = flat(); m.loc[30:, OHLC] = 100 * math.exp(-side * .03)             # gap through: fill at the actual open
    r = run(mod, sig([{"at": 15, "side": side}]), m)
    t = r.trades.iloc[0]
    assert t.exit_time == at(30) and t.exit_reason == "stop" and np.isclose(t.exit_price, 100 * math.exp(-side * .03))
    assert np.isclose(t.gross_bps, -300) and ledger_ok(r)


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_trail_armed_after_mfe_and_gives_back_half_r(mod, side):
    m = flat(); m.loc[20:, OHLC] = 100 * math.exp(side * .01)
    best = 100 * math.exp(side * .012)
    m.loc[20, "high" if side == 1 else "low"] = best                       # MFE 120 >= R0 100: armed from minute 21
    trail = best * math.exp(-side * .005)
    m.loc[25, "low" if side == 1 else "high"] = 100 * math.exp(side * .005)   # beyond trail, inside hard stop
    t = run(mod, sig([{"at": 15, "side": side}]), m).trades.iloc[0]
    assert t.exit_time == at(25) and t.exit_reason == "trail" and np.isclose(t.exit_price, trail)


@MODS
def test_trail_no_same_minute_lookahead(mod):
    m = flat(); m.loc[20:, OHLC] = 101.0
    m.loc[20, ["high", "low"]] = [101.2, 100.6]       # arms and falls below the would-be trail in the same minute
    m.loc[22, "low"] = 100.6
    t = run(mod, sig([{"at": 15, "side": 1}]), m).trades.iloc[0]
    assert t.exit_time == at(22) and t.exit_reason == "trail"


@MODS
def test_r_tightens_only_and_missing_e_keeps_r(mod):
    m = flat(); m.loc[35, "low"] = 99.6; m.loc[40, "low"] = 99.4
    s = sig([{"at": 15, "side": 1}])
    e = np.full(len(m), np.nan); e[16] = 50.0                    # entry minute: R_t starts at the next minute
    e[20:30] = 50.0; e[30:33] = 200.0                            # wider E never widens R; NaN keeps it
    t = run(mod, s, m, e).trades.iloc[0]
    assert t.exit_time == at(40) and np.isclose(t.exit_price, 100 * math.exp(-.005))
    m.loc[16, "low"] = 99.4                                      # entry bar uses R0, not the minute-16 E
    t = run(mod, s, m, e).trades.iloc[0]
    assert t.exit_time == at(40)
    s = sig([{"at": 15, "side": 1, "e0_bps": 1000.0}])           # R0 capped at 300
    m = flat(); m.loc[30, "low"] = 90.0
    assert np.isclose(run(mod, s, m).trades.exit_price.iloc[0], 100 * math.exp(-.03))


@MODS
def test_no_entry_without_e(mod):
    m = flat()
    assert run(mod, sig([{"at": 15, "side": 1, "e0_bps": np.nan}]), m).trades.empty
    m.loc[20, "high"] = 102.0
    oco = sig([{"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": 99.0, "expiry_min": 60}])
    assert run(mod, oco, m).trades.empty                        # OCO E0 comes from the series at the fill minute
    m.loc[25, "high"] = 102.0
    e = np.full(len(m), 300.0); e[20] = np.nan
    assert run(mod, oco, m, e, close_at_end=True).trades.empty  # the touched order without E is dropped, not reused
    r = run(mod, oco, m, np.full(len(m), 300.0), close_at_end=True)
    assert r.trades.entry_time.iloc[0] == at(20) and r.trades.exit_reason.iloc[0] == "data_end"


@MODS
@pytest.mark.parametrize("lower,side,price", [(99.5, -1, 99.5), (99.0, -1, 99.0), (99.0, 1, 101.0)])
def test_oco_both_touch(mod, lower, side, price):
    m = flat(); m.loc[20, ["high", "low"]] = [101.5, 98.5]
    if side == 1:
        m.loc[20, "open"] = 100.5                               # nearer to upper
    s = sig([{"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": lower, "expiry_min": 60}])
    r = run(mod, s, m, np.full(len(m), 300.0), close_at_end=True)
    t = r.trades.iloc[0]
    assert t.entry_time == at(20) and t.side == side and t.entry_price == price and t.exit_reason == "data_end"


@MODS
def test_oco_expiry_cancel_and_market_cancel(mod):
    e = np.full(200, 300.0)
    m = flat(); m.loc[76, "high"] = 102.0                       # expiry 16 + 60 = 76: not filled
    oco = {"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": 99.0, "expiry_min": 60}
    assert run(mod, sig([oco]), m, e).trades.empty
    m = flat(); m.loc[20, "high"] = 102.0; m.loc[60, "high"] = 102.0
    s = sig([oco, {**oco, "at": 17}, {"at": 40, "side": 0, "exit_long": True}])
    t = run(mod, s, m, e).trades
    assert len(t) == 1 and t.exit_time.iloc[0] == at(41)        # sibling cancelled at the fill, not reused at 60
    s = sig([oco, {"at": 17, "side": -1}, {"at": 40, "side": 0, "exit_short": True}])
    m = flat(); m.loc[60, "high"] = 102.0
    t = run(mod, s, m, e).trades
    assert len(t) == 1 and t.side.iloc[0] == -1                 # market entry cancels the pending OCO
    s = sig([{"at": 15, "side": 1}, {**oco, "at": 20}, {"at": 40, "side": 0, "exit_long": True}])
    t = run(mod, s, m, e).trades
    assert len(t) == 1                                          # an OCO row seen while held is never placed


@MODS
@pytest.mark.parametrize("entry", ["market", "oco"])
def test_entry_bar_tested_against_hard_stop(mod, entry):
    m = flat()
    if entry == "market":
        m.loc[16, "low"] = 98.0
        s = sig([{"at": 15, "side": 1}])
    else:
        m.loc[20, ["high", "low"]] = [101.5, 99.6]
        s = sig([{"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": 99.0, "expiry_min": 60}])
    r = run(mod, s, m, np.full(len(m), 100.0))
    t = r.trades.iloc[0]
    fill = 100.0 if entry == "market" else 101.0
    assert t.entry_time == t.exit_time and t.exit_reason == "stop" and np.isclose(t.exit_price, fill * math.exp(-.01))
    assert ledger_ok(r)


@MODS
def test_state_exits(mod):
    m = flat()
    s = sig([{"at": 15, "side": 1, "anchor_upper": 100.5, "anchor_lower": 99.5},
             {"at": 20, "side": 0, "anchor_upper": 200.0, "anchor_price": 100.6},   # stored anchor wins: no exit
             {"at": 25, "side": 0, "anchor_price": np.nan},
             {"at": 30, "side": 0, "anchor_price": 100.4}])
    t = run(mod, s, m).trades
    assert len(t) == 1 and t.exit_time.iloc[0] == at(31) and t.exit_reason.iloc[0] == "state"
    s = sig([{"at": 15, "side": -1, "anchor_upper": 100.5, "anchor_lower": 99.5},
             {"at": 30, "side": 0, "anchor_price": 99.6}])
    assert run(mod, s, m).trades.exit_time.iloc[0] == at(31)
    s = sig([{"at": 15, "side": 1}, {"at": 30, "side": -1}, {"at": 40, "side": 1}])  # opposite closes, no reverse
    r = run(mod, s, m)
    assert r.trades.exit_reason.tolist() == ["reverse"] and r.open_position["entry_time"] == at(41)
    s = sig([{"at": 15, "side": 1, "component": 1}, {"at": 30, "side": -1, "component": 2, "exit_long": True}])
    assert run(mod, s, m).trades.empty                          # another component never exits the position


@MODS
def test_stop_at_open_beats_state_exit_and_no_reuse(mod):
    m = flat(); m.loc[31:, OHLC] = 97.0
    s = sig([{"at": 15, "side": 1}, {"at": 20, "side": 1}, {"at": 30, "side": -1, "exit_long": True}])
    r = run(mod, s, m)
    assert r.trades.exit_reason.tolist() == ["stop"] and r.trades.exit_price.iloc[0] == 97.0
    assert r.open_position is None                              # neither the held-time entry nor the reverse reopens
    m = flat(); m.loc[30, "low"] = 98.0
    s = sig([{"at": 15, "side": 1}, {"at": 29, "side": 1}, {"at": 30, "side": 1}])
    r = run(mod, s, m)
    assert len(r.trades) == 1 and r.open_position["entry_time"] == at(31)   # no same-minute reentry at 30


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_funding_boundary_pess(mod, side):
    t0 = pd.Timestamp("2024-01-01 07:00", tz="UTC")
    m = flat(120, start=t0)
    s = sig([{"at": 59, "side": side}, {"at": 90, "side": 0, "exit_long": True, "exit_short": True}], t0)
    r = run(mod, s, m, include_funding=True)
    t = r.trades.iloc[0]
    assert t.entry_time == pd.Timestamp("2024-01-01 08:00", tz="UTC")
    assert np.isclose(t.funding_bps, costs.funding_bps(side, t.entry_time, t.exit_time, "PESS"))
    assert (t.funding_bps < 0) == (side == 1) and ledger_ok(r)


@MODS
def test_data_end_close_and_open_state(mod):
    m = flat(); m.loc[100:, OHLC] = 101.0
    s = sig([{"at": 15, "side": 1, "anchor_upper": 99.0}])
    r = run(mod, s, m, close_at_end=True)
    t = r.trades.iloc[0]
    assert t.exit_reason == "data_end" and t.exit_price == 101.0 and t.fee_bps == 4.0 and ledger_ok(r)
    p = run(mod, s, m).open_position
    assert p["r0_bps"] == 100.0 and p["r_bps"] == 100.0 and p["anchor_upper"] == 99.0 and p["max_hold_end"] is None
    assert p["best_price"] == 101.0 and not p["trail_armed"]


def test_bad_config_and_base_default():
    m = flat(); s = sig([{"at": 15, "side": 1}])
    assert reference.SimConfig().exit_policy == "BASE"
    for kw in ({"exit_style": "DETEXIT"}, {"reentry": "stop_and_reverse"}, {"exit_policy": "OTHER"}):
        for mod in (reference, core):
            with pytest.raises(ValueError, match="bad config"):
                run(mod, s, m, **kw)


def random_case(seed):
    rng = np.random.default_rng(seed)
    n = 4000
    t = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 8e-4, n)))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 3e-4, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 4e-4, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 4e-4, n)))
    m = pd.DataFrame({"open_time": t, "open": open_, "high": high, "low": low, "close": close, "volume": 1.,
                      "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .5})
    e = pd.Series(np.where(np.arange(n) % 60 == 0, rng.uniform(20, 160, n), np.nan)).ffill(limit=40).to_numpy()
    d = t[5::5][:700]
    idx = t.get_indexer(d)
    mid = close[idx]
    oco = rng.random(len(d)) < .3
    s = schema.validate(pd.DataFrame({
        "decision_time": d, "side": np.where(oco, 0, rng.choice([-1, 0, 0, 0, 1], len(d))),
        "entry": np.where(oco, "oco", "market"), "upper": mid * 1.002, "lower": mid * 0.998,
        "expiry_min": 30, "max_hold_min": 60, "stop_bps": np.nan, "take_bps": np.nan,
        "exit_long": rng.random(len(d)) < .03, "exit_short": rng.random(len(d)) < .03,
        "allow_entry": rng.random(len(d)) > .05, "component": rng.choice([0, 1], len(d)),
        "e0_bps": np.where(rng.random(len(d)) < .1, np.nan, e[idx]), "k": rng.choice([0.5, 1.0, 2.0], len(d)),
        "anchor_upper": mid * 0.997, "anchor_lower": mid * 1.003,
        "anchor_price": np.where(rng.random(len(d)) < .3, mid, np.nan)}))
    return s, m, e


def same_state(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same_state(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_state(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9
    return a == b


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("close_at_end", [False, True])
def test_core_matches_reference_adaptive(seed, close_at_end):
    s, m, e = random_case(seed)
    kw = {"include_funding": seed % 2 == 0, "close_at_end": close_at_end, "stop_slippage_bps": 1.0 * (seed % 3),
          "market_slippage_bps": 0.5 * (seed % 2)}
    a = run(reference, s, m, e, **kw)
    b = run(core, s, m, e, **kw)
    assert len(a.trades) >= 10 and {"stop", "trail"} <= set(a.trades.exit_reason)
    pd.testing.assert_frame_equal(a.trades, b.trades, atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9, rtol=0)
    assert same_state(a.open_position, b.open_position)
    if close_at_end:
        assert ledger_ok(a) and a.open_position is None
