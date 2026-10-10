"""Per-decision-hold event simulator (btcusdt_quant/rl/event_sim.py) == Batch-2 simulate(kind="event") for a
constant hold; mixed holds respected."""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.rl import event_sim as ES

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("nm_b2_es_t", ROOT / "out/run_new_model_batch2_20261010.py")
b2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b2
spec.loader.exec_module(b2)


def market(n=30 * 1440, seed=0):
    rng = np.random.default_rng(seed)
    c = 40_000 * np.exp(np.cumsum(rng.normal(0, 6e-4, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 5e-4, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 5e-4, n))
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * 60_000_000_000).astype(np.int64)
    return b2.Market(t, o, h, l, c, np.ones(n), np.ones(n), t[::480].copy(), np.zeros(len(t[::480])))


def test_constant_hold_equals_batch2():
    m = market()
    rng = np.random.default_rng(1)
    dec = np.arange(239, m.N, 240)
    side = rng.choice([-1, 0, 1], len(dec))
    for hold in (240, 1440):
        for off, pen in ((2, 0.5), (5, 2.0)):
            a, oa = b2.simulate(m, "event", dec, side, np.ones(len(dec)), off, 60, pen, 1000, m.N - 500, hold=hold)
            b, ob = ES.simulate_event(m.o, m.h, m.l, m.c, dec, side, np.ones(len(dec)), np.full(len(dec), hold), off, 60,
                                      pen, 1000, m.N - 500)
            assert a.equals(b) and oa.equals(ob)


def test_mixed_hold_respected():
    m = market(seed=2)
    dec = np.arange(239, m.N, 240)
    side = -np.ones(len(dec), int)
    hold = np.where(np.arange(len(dec)) < len(dec) // 2, 240, 1440)
    tr, _ = ES.simulate_event(m.o, m.h, m.l, m.c, dec, side, np.ones(len(dec)), hold, 2, 60, 0.5, 0, m.N)
    done = tr[~tr.open_at_end]
    held = (done.exit_decision_idx - done.entry_idx).to_numpy()
    first = done.decision_idx.to_numpy() < dec[len(dec) // 2]
    assert (held[first] == 240).all() and (held[~first] == 1440).all()
