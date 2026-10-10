"""R2-55 (out/k45_rl_r2_48_20261007/r2_55_k0607_c0_freeze.json): causal guard (SimConfig.causal_guard) on both
simulators, the four AXC0 family repairs (build_variant(..., ax=True, axc0=True)) and core/reference equality."""
import math
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, reference
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, legacy
from tests.sim.test_adaptive_exit import MODS, at, flat, ledger_ok, random_case, run, same_state, sig

CHANGED = ["B1", "B2", "B3", "K04", "K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0", "K13", "K14"]
START, END = pd.Timestamp("2022-10-01", tz="UTC"), pd.Timestamp("2023-02-01", tz="UTC")
STATE = ["ax_exit_long", "ax_exit_short", "anchor_upper", "anchor_lower", "anchor_price", "anchor_once"]


def e_wide(m):
    """E = 300 every minute (R0 capped at 300: stops far away), no R_t updates."""
    return np.full(len(m), 300.0), np.full(len(m), np.nan)


def oco_case(side, extra):
    """OCO placed at 15 (upper 101 / lower 99) fills at minute 20: fill_time = at(20)."""
    m = flat()
    m.loc[20, "high" if side == 1 else "low"] = 101.5 if side == 1 else 98.5
    rows = [{"at": 15, "side": 0, "entry": "oco", "upper": 101.0, "lower": 99.0, "expiry_min": 30,
             "anchor_upper": 101.0, "anchor_lower": 99.0}] + extra
    return sig(rows), m


# ---- causal guard: same-or-earlier close ignored, later close accepted ----
@MODS
@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("kind", ["state", "flag", "ax_flag", "reverse"])
def test_guard_ignores_close_at_fill_minute(mod, side, kind):
    key = "long" if side == 1 else "short"
    row = {"state": {"anchor_price": 100.0}, "flag": {f"exit_{key}": True}, "ax_flag": {f"ax_exit_{key}": True},
           "reverse": {"side": -side}}[kind]
    s, m = oco_case(side, [{"at": 20, "side": 0, **row}, {"at": 25, "side": 0, **row}])
    e, e_min = e_wide(m)
    reason = {"state": "state", "flag": "flag", "ax_flag": "flag", "reverse": "reverse"}[kind]
    off = run(mod, s, m, e, e_min).trades.iloc[0]
    on = run(mod, s, m, e, e_min, causal_guard=True).trades.iloc[0]
    assert off.entry_time == on.entry_time == at(20) and off.side == on.side == side
    assert off.exit_time == at(21) and off.exit_reason == reason          # decision 20 == fill minute: legacy exits
    assert on.exit_time == at(26) and on.exit_reason == reason            # guard: only the later close (25 > 20)


@MODS
def test_guard_keeps_anchor_once_for_the_first_post_fill_close(mod):
    s, m = oco_case(1, [{"at": 20, "side": 0, "anchor_price": 101.2},
                        {"at": 25, "side": 0, "anchor_price": 100.0}])
    s = s.assign(anchor_once=np.where(s.entry == "oco", 1.0, np.nan))
    e, e_min = e_wide(m)
    assert run(mod, s, m, e, e_min).trades.empty                          # legacy: 20 consumed the one-shot anchor
    t = run(mod, s, m, e, e_min, causal_guard=True).trades
    assert t.exit_time.tolist() == [at(26)] and t.exit_reason.tolist() == ["state"]


@MODS
def test_guard_market_entry_later_rows_unchanged(mod):
    m = flat()
    s = sig([{"at": 15, "side": 1, "anchor_upper": 100.5}, {"at": 16, "side": 0, "anchor_price": 100.0},
             {"at": 30, "side": 0, "anchor_price": 100.4}])
    assert run(mod, s, m).trades.exit_time.tolist() == [at(17)]             # close 16 == fill minute 16
    assert run(mod, s, m, causal_guard=True).trades.exit_time.tolist() == [at(31)]


def test_guard_rejected_on_base():
    m = flat(); s = sig([{"at": 15, "side": 1}])
    cfg = reference.SimConfig(include_funding=False, causal_guard=True)
    for mod in (reference, core):
        with pytest.raises(ValueError, match="bad config"):
            mod.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg)
    assert repr(reference.SimConfig()) == repr(reference.SimConfig(causal_guard=False))
    assert "causal_guard" not in repr(reference.SimConfig())               # default repr byte-identical


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("policy", ["R2_52A", "R2_52B"])
def test_core_matches_reference_with_guard(seed, policy):
    s, m, e, e_min = random_case(seed)
    # every second OCO row fills near its own decision row: make same-minute closes frequent
    kw = {"include_funding": seed % 2 == 0, "close_at_end": True, "stop_slippage_bps": 1.0 * (seed % 3),
          "market_slippage_bps": 0.5 * (seed % 2), "exit_policy": policy, "causal_guard": True}
    a = run(reference, s, m, e, e_min, **kw)
    b = run(core, s, m, e, e_min, **kw)
    assert len(a.trades) >= 10
    pd.testing.assert_frame_equal(a.trades, b.trades, atol=1e-9, rtol=0)
    assert np.allclose(a.minute_pnl.to_numpy(), b.minute_pnl.to_numpy(), atol=1e-9, rtol=0)
    assert same_state(a.open_position, b.open_position) and ledger_ok(a)


def test_guard_changes_random_cases():
    """Rows every 5 min: a 5-min-later close after an OCO fill at a row minute is now ignored somewhere."""
    changed = 0
    for seed in range(10):
        s, m, e, e_min = random_case(seed)
        kw = {"include_funding": False, "close_at_end": True}
        a = run(core, s, m, e, e_min, **kw).trades
        b = run(core, s, m, e, e_min, causal_guard=True, **kw).trades
        changed += not a.equals(b)
    assert changed > 0


# ---- engine semantics of the four repairs ----
@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_frozen_level_thresholds_and_component_isolation(mod, side):
    """E1-15 / C0 anchors: long exits at close <= level, short at >= level (equality exits); other components'
    rows never touch the position."""
    level = 100.5 if side == 1 else 99.5
    inside, through = (100.6, 100.5) if side == 1 else (99.4, 99.5)
    m = flat()
    rows = [{"at": 15, "side": side, "component": legacy.E1_15, "anchor_upper": 100.5, "anchor_lower": 99.5},
            {"at": 30, "side": 0, "component": legacy.A2_30, "anchor_price": 90.0 if side == 1 else 110.0},
            {"at": 45, "side": 0, "component": legacy.E1_15, "anchor_price": inside},
            {"at": 60, "side": 0, "component": legacy.E1_15, "anchor_price": through}]
    for guard in (False, True):
        t = run(mod, sig(rows), m, causal_guard=guard).trades
        assert t.exit_time.tolist() == [at(61)] and t.exit_reason.tolist() == ["state"], level


@MODS
def test_k13_opposite_consensus_only(mod):
    """Loss of unanimity (side 0, no flag) is ignored; opposite unanimity (side -1, exit_long) exits; no reentry."""
    m = flat()
    rows = [{"at": 15, "side": 1, "exit_short": True}, {"at": 30, "side": 0},
            {"at": 45, "side": -1, "exit_long": True}]
    r = run(mod, sig(rows), m, causal_guard=True)
    assert r.trades.exit_time.tolist() == [at(46)] and r.trades.exit_reason.tolist() == ["reverse"]
    assert r.open_position is None


# ---- strategy tables ----
@pytest.fixture(scope="module")
def ctx():
    return Context.load(end=END, start=START)


def tables(ctx, spec_id):
    return (build_variant(ctx, spec_id, gated=False, style="NATIVE", ax=True)[0],
            build_variant(ctx, spec_id, gated=False, style="NATIVE", ax=True, axc0=True)[0])


def same(a, b):
    np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


def test_scope_and_rejections(ctx):
    assert sorted(i for i, s in CATALOG.items() if s.axc0 is not None) == sorted(CHANGED)
    for spec_id in ("K01", "K05", "K30"):
        with pytest.raises(ValueError, match="axc0"):
            build_variant(ctx, spec_id, False, "NATIVE", ax=True, axc0=True)
    with pytest.raises(ValueError, match="axc0"):
        build_variant(ctx, "K04", False, "NATIVE", axc0=True)


@pytest.mark.parametrize("spec_id", CHANGED)
def test_axc0_changes_only_state_columns(ctx, spec_id):
    a, c = tables(ctx, spec_id)
    assert list(a.columns) == list(c.columns) and len(a) == len(c)
    keep = [x for x in a.columns if x not in STATE + ["exit_long", "exit_short"]]
    pd.testing.assert_frame_equal(a[keep], c[keep])
    if spec_id != "K13":
        same(a.exit_long, c.exit_long); same(a.exit_short, c.exit_short)


def test_k04_frozen_breakout_level(ctx):
    a, c = tables(ctx, "K04")
    b = ctx.bars(15).set_index("decision_time")
    idx = pd.DatetimeIndex(c.decision_time)
    same(c.anchor_upper, b.high.rolling(20).max().shift().reindex(idx))
    same(c.anchor_lower, b.low.rolling(20).min().shift().reindex(idx))
    same(c.anchor_price, b.close.reindex(idx))
    assert not (c.ax_exit_long | c.ax_exit_short).any() and c.anchor_once.isna().all()
    entries = c.side.to_numpy() == 1
    assert entries.sum() > 5 and (c.anchor_price[entries] > c.anchor_upper[entries]).all()   # breakout row: close > level


@pytest.mark.parametrize("book", ["B1", "B2", "B3"])
def test_composite_only_e1_component_repaired(ctx, book):
    a, c = tables(ctx, book)
    e1 = (c.component == legacy.E1_15).to_numpy()
    pd.testing.assert_frame_equal(a.loc[~e1].drop(columns=["anchor_upper", "anchor_lower", "anchor_price"]),
                                  c.loc[~e1].drop(columns=["anchor_upper", "anchor_lower", "anchor_price"]))
    assert c.loc[~e1, ["anchor_upper", "anchor_lower", "anchor_price"]].isna().all().all()
    k04 = tables(ctx, "K04")[1].set_index("decision_time")
    part = c.loc[e1].set_index("decision_time")
    for col in ("anchor_upper", "anchor_lower", "anchor_price"):
        same(part[col].reindex(k04.index), k04[col])
    assert not (part.ax_exit_long | part.ax_exit_short).any()


@pytest.mark.parametrize("spec_id", ["K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0"])
def test_oco_c0_anchor(ctx, spec_id):
    a, c = tables(ctx, spec_id)
    raw = CATALOG[spec_id].build(ctx)
    same(c.anchor_upper, raw.ind_close); same(c.anchor_lower, raw.ind_close); same(c.anchor_price, a.anchor_price)
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(c.upper)
        assert ok.any() and ((c.lower[ok] < c.anchor_upper[ok]) & (c.anchor_upper[ok] < c.upper[ok])).all()


def test_k13_opposite_consensus_flags(ctx):
    a, c = tables(ctx, "K13")
    raw = CATALOG["K13"].build(ctx)
    signs = raw[["ind_sign_15m", "ind_sign_1h", "ind_sign_4h"]].to_numpy()
    same(c.exit_long, (signs == -1).all(axis=1)); same(c.exit_short, (signs == 1).all(axis=1))
    same(a.exit_long, ~(signs == 1).all(axis=1))                          # AX: any sign differs
    no_consensus = ~((signs == 1).all(axis=1) | (signs == -1).all(axis=1))
    assert no_consensus.any() and not (c.exit_long | c.exit_short)[no_consensus].any()


def test_k14_c0_anchor(ctx):
    a, c = tables(ctx, "K14")
    oco = (c.entry == "oco").to_numpy()
    same(c.anchor_upper[oco], a.anchor_price[oco]); same(c.anchor_lower[oco], a.anchor_price[oco])
    assert c.loc[~oco, ["anchor_upper", "anchor_lower"]].isna().all().all()
    same(c.anchor_price, a.anchor_price)
    assert ((c.lower[oco] <= c.anchor_upper[oco]) & (c.anchor_upper[oco] <= c.upper[oco])).all()


@pytest.mark.parametrize("spec_id", ["K04", "K14"])
def test_axc0_core_matches_reference_on_real_table(ctx, spec_id):
    c = tables(ctx, spec_id)[1]
    c = c.assign(e0_bps=150.0, k=1.5)
    a, b = pd.Timestamp("2023-01-05", tz="UTC"), pd.Timestamp("2023-01-25", tz="UTC")
    m = ctx.minutes.loc[(ctx.minutes.open_time >= a) & (ctx.minutes.open_time < b)].reset_index(drop=True)
    e = np.full(len(m), 150.0)
    cfg = reference.SimConfig(exit_policy="R2_52A", include_funding=False, close_at_end=True, causal_guard=True)
    x = reference.simulate(c, m, a, b, cfg, e_bps=e, e_min_bps=np.full(len(m), np.nan))
    y = core.simulate(c, m, a, b, cfg, e_bps=e, e_min_bps=np.full(len(m), np.nan))
    assert len(x.trades) > 3
    pd.testing.assert_frame_equal(x.trades, y.trades, atol=1e-9, rtol=0)
    assert np.allclose(x.minute_pnl.to_numpy(), y.minute_pnl.to_numpy(), atol=1e-9)
