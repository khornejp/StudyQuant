"""R2-52B adaptive hard stop + separate trail (freeze out/k45_rl_r2_48_20261007/r2_52b_exit_freeze.json):
S0=clip(k*E0,300,500), S_t=min(S_{t-1},clip(k*E_t,300,500)); A0=min(k*E0,300), A_t=min(A_{t-1},k*E_t,300); trail armed
on prior-minute MFE >= A0, giveback 0.5*A_t; the more protective level is the active stop. Hand cases on both
simulators plus a core/reference differential. Expected prices are literals computed by hand (100*exp(-x/1e4))."""
import math
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, reference
from tests.sim.test_adaptive_exit import MODS, OHLC, at, flat, ledger_ok, same_state, sig, random_case

B = "R2_52B"


def run(mod, s, m, e=None, e_min=None, k_minute=None, **kw):
    cfg = reference.SimConfig(**{"include_funding": False, "exit_policy": B, **kw})
    return mod.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg, e_bps=e,
                        e_min_bps=e if e is not None and e_min is None else e_min, k_minute=k_minute)


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_hard_stop_floor_300(mod, side):
    m = flat(); m.loc[30, "low" if side == 1 else "high"] = 100 * math.exp(-side * .025)   # 250 adverse: no stop
    r = run(mod, sig([{"at": 15, "side": side}]), m, close_at_end=True)                   # k*E0 = 100 -> S0 = 300
    assert r.trades.exit_reason.tolist() == ["data_end"]
    m.loc[40, "low" if side == 1 else "high"] = 100 * math.exp(-side * .031)
    t = run(mod, sig([{"at": 15, "side": side}]), m).trades.iloc[0]
    assert t.exit_time == at(40) and t.exit_reason == "stop"
    assert abs(t.exit_price - (97.04455335485082 if side == 1 else 103.0454533953517)) < 1e-9


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_hard_stop_cap_500_and_gap(mod, side):
    s = sig([{"at": 15, "side": side, "e0_bps": 1000.0}])                                   # 1000 -> S0 = 500
    m = flat(); m.loc[30, "low" if side == 1 else "high"] = 100 * math.exp(-side * .045)
    assert run(mod, s, m, close_at_end=True).trades.exit_reason.tolist() == ["data_end"]
    m.loc[40, "low" if side == 1 else "high"] = 100 * math.exp(-side * .06)
    t = run(mod, s, m).trades.iloc[0]
    assert t.exit_time == at(40) and t.exit_reason == "stop"
    assert abs(t.exit_price - (95.1229424500714 if side == 1 else 105.12710963760242)) < 1e-9
    m = flat(); m.loc[40:, OHLC] = 100 * math.exp(-side * .07)                              # gap: fill at the open
    r = run(mod, s, m)
    assert np.isclose(r.trades.gross_bps.iloc[0], -700) and r.trades.exit_reason.iloc[0] == "stop" and ledger_ok(r)


@MODS
def test_s_tightens_only_within_clip_and_missing_e_keeps_s(mod):
    s = sig([{"at": 15, "side": 1, "k": 2.0, "e0_bps": 200.0}])                              # S0 = 400, A0 = 300
    m = flat(); m.loc[30, "low"] = 100 * math.exp(-.035); m.loc[50, "low"] = 100 * math.exp(-.035)
    e = np.full(len(m), np.nan); e[40:45] = 40.0; e[45:48] = 300.0                          # 2*40=80 -> clip 300
    r = run(mod, s, m, e)
    t = r.trades.iloc[0]
    assert t.exit_time == at(50) and abs(t.exit_price - 97.04455335485082) < 1e-9             # 350 > 300 after tighten
    m = flat(); m.loc[30, "low"] = 100 * math.exp(-.041)
    e = np.full(len(m), np.nan); e[20:] = 240.0                                             # 2*240=480 -> S = 400
    t = run(mod, s, m, e).trades.iloc[0]
    assert t.exit_time == at(30) and abs(t.exit_price - 96.07894391523232) < 1e-9
    p = run(mod, s, flat(), e).open_position
    assert p["s0_bps"] == 400.0 and p["s_bps"] == 400.0 and p["r0_bps"] == 300.0 and p["r_bps"] == 300.0


@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_trail_arm_on_a0_and_giveback_on_a(mod, side):
    m = flat(); m.loc[20:, OHLC] = 100 * math.exp(side * .0115)
    best = 100 * math.exp(side * .012)
    m.loc[20, "high" if side == 1 else "low"] = best                                        # MFE 120 >= A0 100
    m.loc[25, "low" if side == 1 else "high"] = 100 * math.exp(side * .0105)               # 15 bps below best
    t = run(mod, sig([{"at": 15, "side": side}]), m, close_at_end=True).trades.iloc[0]
    assert t.exit_reason == "data_end"                                                      # giveback 50 not reached
    e = np.full(len(m), np.nan); e[22:] = 20.0                                              # A_t = 20 -> giveback 10
    t = run(mod, sig([{"at": 15, "side": side}]), m, e).trades.iloc[0]
    assert t.exit_time == at(25) and t.exit_reason == "trail" and np.isclose(t.exit_price, best * math.exp(-side * .001))
    m.loc[20, "high" if side == 1 else "low"] = 100 * math.exp(side * .0099)               # MFE 99 < A0: not armed
    m.loc[20:, OHLC] = 100 * math.exp(side * .0099)
    m.loc[25, "low" if side == 1 else "high"] = 100.0
    assert run(mod, sig([{"at": 15, "side": side}]), m, e, close_at_end=True).trades.exit_reason.tolist() == ["data_end"]


@MODS
def test_trail_no_same_minute_lookahead_and_hard_before_arm(mod):
    m = flat(); m.loc[20:, OHLC] = 101.0
    m.loc[20, ["high", "low"]] = [101.2, 100.6]                     # arms and falls below the trail in the same minute
    m.loc[22, "low"] = 100.6
    t = run(mod, sig([{"at": 15, "side": 1}]), m).trades.iloc[0]
    assert t.exit_time == at(22) and t.exit_reason == "trail"
    m = flat(); m.loc[20:, OHLC] = 100 * math.exp(.012)
    m.loc[22:, OHLC] = 96.0                                          # armed trail gaps through: open fill, trail wins
    t = run(mod, sig([{"at": 15, "side": 1}]), m).trades.iloc[0]
    assert t.exit_time == at(22) and t.exit_reason == "trail" and t.exit_price == 96.0


@MODS
@pytest.mark.parametrize("entry", ["market", "oco"])
def test_entry_bar_tested_against_s0(mod, entry):
    m = flat()
    if entry == "market":
        m.loc[16, "low"] = 98.0                                      # 202 adverse: inside S0 300 (R2_52A would stop)
        s = sig([{"at": 15, "side": 1}])
        fill, row = 100.0, 16
    else:
        m.loc[20, ["high", "low"]] = [101.5, 99.6]
        s = sig([{"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": 95.0, "expiry_min": 60}])
        fill, row = 101.0, 20
    assert run(mod, s, m, np.full(len(m), 100.0), close_at_end=True).trades.exit_reason.tolist() == ["data_end"]
    m.loc[row, "low"] = fill * math.exp(-.031)
    r = run(mod, s, m, np.full(len(m), 100.0))
    t = r.trades.iloc[0]
    assert t.entry_time == t.exit_time and t.exit_reason == "stop" and np.isclose(t.exit_price, fill * math.exp(-.03))
    assert ledger_ok(r)


@MODS
def test_k_schedule_locked_on_position(mod):
    m = flat(); m.loc[150, "low"] = 100 * math.exp(-.035)
    k = np.where(np.arange(len(m)) < 100, 4.0, 1.0)                  # entry at k=4: S0 = clip(400) = 400
    e = np.full(len(m), 100.0); e_min = np.full(len(m), np.nan)
    r = run(mod, sig([{"at": 15, "side": 1}]), m, e, e_min, k_minute=k, close_at_end=True)
    assert r.trades.exit_reason.tolist() == ["data_end"]


def test_policy_validation():
    m = flat(); s = sig([{"at": 15, "side": 1}])
    for kw in ({"exit_style": "DETEXIT"}, {"reentry": "stop_and_reverse"}):
        for mod in (reference, core):
            with pytest.raises(ValueError, match="bad config"):
                run(mod, s, m, **kw)
    assert reference.check_policy(reference.SimConfig(exit_policy=B))


def random_b(seed):
    s, m, e, e_min = random_case(seed)
    rng = np.random.default_rng(500 + seed)
    scale = rng.uniform(1.0, 4.0)                                    # k*E spans below 300, inside and above 500
    return s.assign(k=rng.choice([1.0, 1.5, 2.0, 2.5, 3.0], len(s)), e0_bps=s.e0_bps * scale), m, e * scale, \
        e_min * scale


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("close_at_end", [False, True])
def test_core_matches_reference_r2_52b(seed, close_at_end):
    s, m, e, e_min = random_b(seed)
    kw = {"include_funding": seed % 2 == 0, "close_at_end": close_at_end, "stop_slippage_bps": 1.0 * (seed % 3),
          "market_slippage_bps": 0.5 * (seed % 2)}
    a = run(reference, s, m, e, e_min, **kw)
    b = run(core, s, m, e, e_min, **kw)
    assert len(a.trades) >= 10
    pd.testing.assert_frame_equal(a.trades, b.trades, atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9, rtol=0)
    assert same_state(a.open_position, b.open_position)
    if close_at_end:
        assert ledger_ok(a) and a.open_position is None


@pytest.mark.parametrize("seed", range(6))
def test_core_matches_reference_r2_52b_stops_two_heads_k_schedule(seed):
    s, m, e, e_min = random_b(seed)
    rng = np.random.default_rng(900 + seed)
    m = m.assign(**{c: 100 * (m[c] / 100) ** 4 for c in OHLC})       # 4x log moves: hard stops 300..500 are hit
    e2 = np.column_stack([e, e * 1.7]); e_min2 = np.column_stack([e_min, e_min * 1.7])
    s = s.assign(e_col=s.component.astype(float))
    k = np.where(np.arange(len(m)) < len(m) // 2, rng.choice([1.0, 2.0]), rng.choice([2.5, 3.0]))
    kw = {"include_funding": seed % 2 == 0, "close_at_end": seed % 3 == 0, "stop_slippage_bps": 1.0 * (seed % 3)}
    a = run(reference, s, m, e2, e_min2, k_minute=k, **kw)
    b = run(core, s, m, e2, e_min2, k_minute=k, **kw)
    assert {"stop", "trail"} <= set(a.trades.exit_reason)
    pd.testing.assert_frame_equal(a.trades, b.trades, atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9, rtol=0)
    assert same_state(a.open_position, b.open_position)


def test_r2_52b_differs_from_r2_52a_and_a_state_keys_unchanged():
    s, m, e, e_min = random_b(3)
    cfg = dict(include_funding=False, close_at_end=False)
    a = reference.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], reference.SimConfig(
        exit_policy="R2_52A", **cfg), e_bps=e, e_min_bps=e_min)
    b = reference.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1], reference.SimConfig(
        exit_policy=B, **cfg), e_bps=e, e_min_bps=e_min)
    assert not a.trades.equals(b.trades)
    p = run(core, sig([{"at": 15, "side": 1}]), flat()).open_position
    q = core.simulate(sig([{"at": 15, "side": 1}]), flat(), at(0), at(200),
                      reference.SimConfig(include_funding=False, exit_policy="R2_52A")).open_position
    assert "s_bps" not in q and set(p) - set(q) == {"s0_bps", "s_bps"}
