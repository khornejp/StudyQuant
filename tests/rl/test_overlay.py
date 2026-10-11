"""Residual-gross overlay: g = 0 equals the plain event run; partial gross scales the entry; G3 activation cancels a
pending NEW order or forces an early exit; gross profile accounting."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import event_sim as ES, overlay as OV
from tests.rl.test_event_sim import market


def plain(m, dec, side, hold, lo, hi):
    return ES.simulate_event(m.o, m.h, m.l, m.c, dec, side, np.ones(len(dec)), np.full(len(dec), hold), 2, 15, 0.5,
                             lo, hi)


def test_zero_gross_equals_event_sim():
    m = market()
    rng = np.random.default_rng(3)
    dec = np.arange(239, m.N, 240)
    side = rng.choice([-1, 0, 1], len(dec))
    a, oa = plain(m, dec, side, 240, 1000, m.N - 500)
    b, ob, st = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, side, 240, 2, 15, 0.5, 1000, m.N - 500, np.zeros(m.N))
    assert a.equals(b) and oa.equals(ob)
    assert st["forced_exit"] == st["order_cancelled"] == st["entry_limited"] == 0 and st["max_total_gross"] <= 1.0


def test_partial_gross_scales_weight():
    m = market(seed=4)
    dec = np.arange(239, m.N, 240)
    tr, od, st = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, np.ones(len(dec), int), 240, 2, 15, 0.5, 0, m.N,
                                     np.full(m.N, 1.5))
    assert len(tr) and np.allclose(tr.entry_weight_frozen, 0.5) and st["entry_limited"] == len(od)
    _, od2, st2 = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, np.ones(len(dec), int), 240, 2, 15, 0.5, 0, m.N,
                                      np.full(m.N, 2.0))
    assert len(od2) == 0 and st2["entry_blocked"] > 0


def test_activation_forces_exit_or_cancel():
    m = market(seed=5)
    dec = np.arange(239, m.N, 240)
    side = np.ones(len(dec), int)
    base, _ = plain(m, dec, side, 240, 0, m.N)
    r = base.iloc[0]
    g = np.zeros(m.N)
    b = int(r.entry_idx) + 100                      # G3 goes to 1.5 mid-hold
    g[b:b + 30] = 1.5
    tr, _, st = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, side, 240, 2, 15, 0.5, 0, m.N, g)
    assert st["forced_exit"] >= 1 and int(tr.iloc[0].exit_decision_idx) == b - 1
    g = np.zeros(m.N)
    g[int(r.decision_idx) + 1:] = 1.5               # active from the order's first bar: entry capped to 0.5
    tr2, _, _ = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, side, 240, 2, 15, 0.5, 0, m.N, g)
    assert np.isclose(tr2.iloc[0].entry_weight_frozen, 0.5)
    r = base[base.entry_idx >= base.decision_idx + 2].iloc[0]
    g = np.zeros(m.N)
    g[int(r.decision_idx) + 2:] = 1.5               # activation after order placement: cancel before fill bar
    _, od3, st3 = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec[dec >= r.decision_idx], side[dec >= r.decision_idx],
                                      240, 2, 15, 0.5, 0, m.N, g)
    assert not od3.iloc[0].filled and st3["order_cancelled"] >= 1


def test_gross_profile():
    tr = pd.DataFrame({"side": [1], "entry_weight_frozen": [0.8], "decision_idx": [10], "entry_idx": [13],
                       "entry_px": [1.0], "exit_decision_idx": [20], "exit_idx": [22], "exit_px": [1.0],
                       "open_at_end": [False]})
    od = pd.DataFrame({"decision_idx": [2, 10], "side": [1, 1], "weight": [0.8, 0.8], "filled": [False, True]})
    g = OV.gross_profile(40, tr, od, 5, 40)
    exp = np.zeros(40)
    exp[3:8] = 0.8
    exp[11:23] = 0.8
    assert np.allclose(g, exp)
