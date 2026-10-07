import math
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, costs, reference, schema
from tests.sim.test_core_differential import random_case
from tests.sim.test_reference import flat_minutes, sig, T0

FIXTURE = Path(__file__).parent / "fixtures" / "core_pre_kernel.pkl.gz"
MIN = pd.Timedelta(minutes=1)
SAR = dict(reentry="stop_and_reverse")


def action_rows(pairs):
    """Target-position rows (C1): only decision_time and side are read in action mode."""
    times, sides = zip(*pairs)
    return schema.validate(pd.DataFrame({"decision_time": list(times), "side": list(sides), "entry": "market",
        "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 0, "stop_bps": np.nan,
        "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True}))


def as_signals(rows):
    """The same targets as plain signal rows for the pre-refactor engine: flat or opposite target exits."""
    return rows.assign(exit_long=rows.side != 1, exit_short=rows.side != -1)


def action_case(seed, flat_end):
    """Random targets on random_case minutes; every settlement minute is also a fill minute."""
    _, m = random_case(seed)
    rng = np.random.default_rng(1000 + seed)
    delay = int(rng.integers(1, 6))
    t = m.open_time
    settle = t[(t.dt.minute == 0) & t.dt.hour.isin([0, 8, 16])] - delay * MIN
    last = t.iloc[-1] - delay * MIN
    times = sorted((set(t.iloc[rng.choice(len(m) - delay - 1, 150, replace=False)]) | set(settle)) - {last}) + [last]
    sides = rng.choice([-1, 0, 1], len(times))
    if flat_end:
        sides[-1] = 0
    return action_rows(list(zip(times, sides))), m, delay


def fixture_cases():
    """(name, signals, minutes, config) frozen from the pre-refactor core (Ruling P1)."""
    out = []
    for seed in range(5):
        s, m = random_case(seed)
        for style in ("NATIVE", "DETEXIT"):
            for reentry in ("strict", "stop_and_reverse"):
                out.append((f"signal_{seed}_{style}_{reentry}", s, m,
                            reference.SimConfig(exit_style=style, reentry=reentry, stop_slippage_bps=1.5)))
    for seed in range(20):
        rows, m, delay = action_case(seed, flat_end=seed % 2 == 1)
        out.append((f"action_{seed}", rows, m,
                    reference.SimConfig(delay_min=delay, include_funding=seed % 2 == 1, **SAR)))
    return out


def run(engine, signals, m, cfg):
    return engine.simulate(signals, m, m.open_time.iloc[0], m.open_time.iloc[-1] + MIN, cfg)


def same(a, b):
    """Parity at rtol=0, atol=1e-9: per-minute pnl, every trade column, final open state."""
    pd.testing.assert_series_equal(a.minute_pnl, b.minute_pnl, rtol=0, atol=1e-9)
    pd.testing.assert_frame_equal(a.trades.reset_index(drop=True), b.trades.reset_index(drop=True), rtol=0, atol=1e-9)
    assert (a.open_position is None) == (b.open_position is None)
    if a.open_position is not None:
        x, y = a.open_position, b.open_position
        for k in x.keys() & y.keys() - {"legs", "units", "avg_price"}:
            assert x[k] == y[k], k
        np.testing.assert_allclose([x["units"], x["avg_price"]], [y["units"], y["avg_price"]], rtol=0, atol=1e-9)
        pd.testing.assert_frame_equal(pd.DataFrame(x["legs"]), pd.DataFrame(y["legs"]), rtol=0, atol=1e-9)


def drive(rows, m, cfg):
    """Replay targets through core.advance_minute alone, the way the RL env will."""
    t_ns = pd.DatetimeIndex(m.open_time).as_unit("ns").asi8
    o, h, l, c = (m[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    exec_ns = pd.DatetimeIndex(rows.decision_time).as_unit("ns").asi8 + cfg.delay_min * core.MINUTE_NS
    target = dict(zip(exec_ns.tolist(), rows.side.tolist()))
    fund = costs._settlement_arrays() if cfg.include_funding else (np.zeros(0, np.int64), np.zeros(0))
    si = np.zeros(len(core.STATE_INT), np.int64); sf = np.zeros(len(core.STATE_FLOAT))
    side = core.STATE_INT.index("side")
    return np.array([core.advance_minute(i, si, sf, o, h, l, c, fund[0], fund[1], t_ns,
                                         int(target.get(int(t_ns[i]), si[side])), cfg.fee_per_side,
                                         cfg.market_slippage_bps) for i in range(len(m))])


def test_market_slippage_is_adverse_both_sides():
    m, s = flat_minutes(), 5.0
    up, down = 100 * (1 + s / 1e4), 100 * (1 - s / 1e4)
    rows = action_rows([(T0 + 15 * MIN, 1), (T0 + 30 * MIN, -1), (T0 + 45 * MIN, 0)])
    cfg = reference.SimConfig(action_mode=True, include_funding=False, fee_per_side=0.0, market_slippage_bps=s, **SAR)
    for engine in (reference, core):
        r = run(engine, rows, m, cfg)
        t = r.trades
        assert t.exit_reason.tolist() == ["reverse", "flag"]
        np.testing.assert_allclose(t.entry_price, [up, down], rtol=0, atol=1e-12)   # long buys up, short sells down
        np.testing.assert_allclose(t.exit_price, [down, up], rtol=0, atol=1e-12)    # long sells down, short buys up
        reversal = r.minute_pnl[T0 + 31 * MIN]                                       # pays both exit and entry
        assert np.isclose(reversal, 2 * math.log(1 - s / 1e4) * 1e4, rtol=0, atol=1e-9)
        assert np.isclose(r.minute_pnl.sum(), t.net_bps.sum(), rtol=0, atol=1e-9)
    s_rows = sig([{"decision_time": T0 + 15 * MIN, "side": -1, "max_hold_min": 60}])    # signal mode, max-hold exit
    for engine in (reference, core):
        t = run(engine, s_rows, m, reference.SimConfig(include_funding=False, market_slippage_bps=s)).trades.iloc[0]
        assert np.isclose(t.entry_price, down) and np.isclose(t.exit_price, up) and t.gross_bps < 0


def test_funding_at_settlement_matches_funding_events():
    m = flat_minutes(2000)
    # fills: long at 08:00 (entry edge), reverse at 16:00 (exit + entry edges), flat at 00:00 (exit edge),
    # long again from 00:30 held over 08:00 to the data end (interior, open at end)
    rows = action_rows([(T0 + 479 * MIN, 1), (T0 + 959 * MIN, -1), (T0 + 1439 * MIN, 0), (T0 + 1469 * MIN, 1)])
    cfg = reference.SimConfig(action_mode=True, fee_per_side=0.0, **SAR)
    end = m.open_time.iloc[-1]
    expect = pd.Series(0.0, index=pd.DatetimeIndex(m.open_time))
    for side, a, b in ((1, 480, 960), (-1, 960, 1440), (1, 1470, None)):
        b_time = end + pd.Timedelta(1, "ns") if b is None else T0 + b * MIN
        for when, value in costs.funding_events(side, T0 + a * MIN, b_time, "PESS"):
            expect[when] += value
    assert (expect != 0).sum() >= 2
    for engine in (reference, core):
        r = run(engine, rows, m, cfg)
        pd.testing.assert_series_equal(r.minute_pnl, expect, rtol=0, atol=1e-9, check_names=False)
        assert np.isclose(r.trades.funding_bps.sum(), expect[:T0 + 1440 * MIN].sum(), rtol=0, atol=1e-9)
    np.testing.assert_allclose(drive(rows, m, cfg), expect.to_numpy(), rtol=0, atol=1e-9)


@pytest.mark.parametrize("seed", range(100))
def test_advance_minute_replays_core_simulate(seed):
    rng = np.random.default_rng(seed)
    rows, m, delay = action_case(seed, flat_end=seed % 2 == 1)
    cfg = reference.SimConfig(action_mode=True, delay_min=delay, include_funding=seed % 3 != 0,
                              fee_per_side=float(rng.choice([0.0, 2.0, 6.0])),
                              market_slippage_bps=float(rng.choice([0.0, 2.5, 10.0])), **SAR)
    ref = run(reference, rows, m, cfg)                      # oracle: the independent slow engine (Ruling P1)
    assert len(ref.trades) > 20
    same(run(core, rows, m, cfg), ref)
    np.testing.assert_allclose(drive(rows, m, cfg), ref.minute_pnl.to_numpy(), rtol=0, atol=1e-9)


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("exit_style", ["NATIVE", "DETEXIT"])
@pytest.mark.parametrize("reentry", ["strict", "stop_and_reverse"])
def test_signal_market_slippage_core_matches_reference(seed, exit_style, reentry):
    s, m = random_case(seed)
    cfg = reference.SimConfig(exit_style=exit_style, reentry=reentry, stop_slippage_bps=1.5, market_slippage_bps=3.0)
    ref = run(reference, s, m, cfg)
    no_slip = run(reference, s, m, reference.SimConfig(exit_style=exit_style, reentry=reentry, stop_slippage_bps=1.5))
    assert ref.minute_pnl.sum() < no_slip.minute_pnl.sum()
    same(run(core, s, m, cfg), ref)


@pytest.fixture(scope="module")
def frozen():
    return pd.read_pickle(FIXTURE)


@pytest.mark.parametrize("case", fixture_cases(), ids=lambda case: case[0])
def test_existing_differential_still_exact(case, frozen):
    """Pre-refactor core outputs (frozen before the kernel existed) are reproduced exactly."""
    name, signals, m, cfg = case
    trades, pnl, open_position = frozen[name]
    old = reference.SimResult(trades, pnl, open_position)
    if name.startswith("action"):
        cfg = reference.SimConfig(**{**cfg.__dict__, "action_mode": True})
        same(run(core, signals, m, cfg), old)
        np.testing.assert_allclose(drive(signals, m, cfg), pnl.to_numpy(), rtol=0, atol=1e-9)
    else:
        same(run(core, signals, m, cfg), old)


def test_action_mode_is_explicit():
    """Ruling P2: max_hold 0 signal rows keep the signal path; action mode rejects configs it does not model."""
    m = flat_minutes()
    rows = action_rows([(T0 + 15 * MIN, 1), (T0 + 30 * MIN, 0)])
    plain = run(core, rows, m, reference.SimConfig(include_funding=False, **SAR))
    assert len(plain.trades) == 0 and plain.open_position is not None       # side 0 without exit flags holds
    for kw in ({"reentry": "strict"}, {"exit_style": "DETEXIT"}, {"close_at_end": True}, {"funding_boundary": "OPT"}):
        for engine in (reference, core):
            with pytest.raises(ValueError, match="bad config"):
                run(engine, rows, m, reference.SimConfig(**{**SAR, **kw, "action_mode": True}))
