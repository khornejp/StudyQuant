"""Signed-size maker kernel: parity with the Batch-2 sleeve path (state kind, one position) and order/risk properties."""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import maker_kernel as MK

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("nm_b2_mk_t", ROOT / "out/run_new_model_batch2_20261010.py")
b2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b2
spec.loader.exec_module(b2)


def market(n=40 * 1440, seed=0, vol=6e-4):
    rng = np.random.default_rng(seed)
    c = 40_000 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 5e-4, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 5e-4, n))
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * 60_000_000_000).astype(np.int64)
    ft = t[::480].copy()
    fr = rng.normal(1e-4, 2e-4, len(ft))
    return b2.Market(t, o, h, l, c, np.ones(n), np.ones(n), ft, fr)


def kernel(m, off, pen):
    return MK.Kernel(m.o, m.h, m.l, m.c, m.t, m.ft, m.fr, off, pen)


@pytest.mark.parametrize("seed,side,off,pen", [(1, 1, 2, 0.5), (2, -1, 5, 2.0), (3, 1, 5, 1.0)])
def test_parity_with_batch2_state_sleeve(seed, side, off, pen):
    m = market(seed=seed)
    rng = np.random.default_rng(seed + 10)
    dec = np.arange(239, m.N - 2000, 240)
    tgt = side * (rng.random(len(dec)) < 0.5).astype(int)
    tr, od = b2.simulate(m, "state", dec, tgt, np.ones(len(dec)), off, 60, pen, 0, m.N)
    bk = b2.Book(m, tr, od, 0, m.N)
    k = kernel(m, off, pen)
    k.reset(int(dec[0]))
    for q in range(len(dec)):
        k.step(float(tgt[q]), 240 if q + 1 < len(dec) else 1440)
    hi = int(dec[-1]) + 1440
    closed = tr[~tr.open_at_end]
    assert len(closed) > 20
    end = int(closed.exit_idx.max()) + 1                    # compare where the sleeve path has no open-at-end mark
    assert np.allclose(k.pnl[:end], bk.pnl[:end], rtol=0, atol=1e-9)
    assert hi <= m.N


def test_properties_reselect_cancel_reversal_funding():
    m = market(seed=5, vol=1e-5)                            # near-flat prices: entry orders rarely fill
    k = kernel(m, 5, 2.0)
    i = k.reset(1000)
    k.step(1.0, 5)
    exp0 = k.st[MK.S_PEXP]
    k.step(1.0, 5)                                          # same target re-selected: TTL not reset
    assert k.st[MK.S_PEND] == 0 or k.st[MK.S_PEXP] == exp0
    k.step(0.5, 5)                                          # changed target: replacement rests from i + 2
    if k.st[MK.S_PEND]:
        assert k.st[MK.S_PSTART] == i + 10 + 2 and k.st[MK.S_PTGT] == 0.5
    m = market(seed=6)
    k = kernel(m, 2, 0.5)
    k.reset(500)
    sides = []
    for q in range(400):
        tg = [1.0, -1.0, 0.25, -0.75, 0.0][q % 5]
        k.step(tg, 60)
        sides.append(k.st[MK.S_U])
    u = k.upath[501:k.i + 1]
    assert np.abs(u).max() <= 1.0 + 1e-12
    du = np.diff(np.r_[0.0, u])
    assert not np.any((np.r_[0.0, u[:-1]] * u) < -1e-12)     # never long and short across one minute (flat between)
    assert np.isclose(k.pnl.sum(), k.st[MK.S_EQ]) and k.st[MK.S_FILLS] > 50
    assert np.all(np.isin(np.round(np.abs(du[np.abs(du) > 0]) * 4, 9), [1, 2, 3, 4, 5, 6, 7, 8]))


def test_funding_pess_min_rule_and_kill():
    m = market(seed=7)
    k = kernel(m, 2, 0.5)
    k.reset(100, kill=True)
    for _ in range(50):
        assert k.step(1.0, 60)["effective_target"] == 0.0
    assert k.st[MK.S_U] == 0 and k.pnl.sum() == 0.0
    k = kernel(m, 2, 0.5)
    k.reset(100)
    for _ in range(200):
        k.step(1.0, 60)
    s = np.flatnonzero(np.isfinite(k.frate))
    s = s[(s > 200) & (s < k.i)]
    held = s[(k.upath[s - 1] == 1.0) & (k.upath[s] == 1.0)]
    assert len(held) > 3


def test_position_stop_forces_flat():
    m = market(seed=8)
    m.c[5000:] = m.c[5000:] * np.linspace(1.0, 0.9, m.N - 5000)      # -10 % slide
    m.o[5000:] = np.r_[m.c[4999], m.c[5000:-1]]
    m.h[:] = np.maximum(m.h, np.maximum(m.o, m.c))
    m.l[:] = np.minimum(m.l, np.minimum(m.o, m.c))
    k = kernel(m, 2, 0.5)
    k.reset(4000)
    for _ in range(300):
        k.step(1.0, 60)
    u = k.upath[4001:k.i + 1]
    first = int(np.argmax(u == 1.0))
    assert u[first] == 1.0 and np.any(u[first:] == 0.0)          # target 1 throughout, yet flattened by the stop
    assert k.st[MK.S_PSTOP] >= 1 and k.st[MK.S_DNFL] >= 1 and k.st[MK.S_DSZ] >= 1.0 and k.st[MK.S_DE2S] > 0
    assert k.st[MK.S_DNRE] >= 1 and k.st[MK.S_DFL] <= 0


def test_reward_decomposition():
    m = market(seed=9)
    k = kernel(m, 2, 0.5)
    i = k.reset(2000)
    r = k.step(1.0, 60)
    rv = MK.rv24h(m.c)
    d = MK.step_reward(k.pnl, k.upath, rv, float(np.median(rv[1440:])), i, r["j"], r["d_target"])
    assert np.isclose(d["net4"], r["net4"]) and d["blocks"] == 12
    assert np.isclose(d["reward"], d["net4"] - d["idle"] - d["turnover"]) and np.isclose(d["turnover"], 0.05)
    assert np.isclose(MK.gamma(30 * 1440), 0.5)


def _partial_reduce_case(mod):
    """Long 1.0 with a live partial reduce (target 0.5, dq -0.5, limit far above) when the position stop fires."""
    n = 400
    c = np.full(n, 100.0)
    c[200:] = 94.0                                                  # -600 bps: position stop at minute 200
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c), np.minimum(o, c)
    t = (np.arange(n) * 60_000_000_000).astype(np.int64)
    st = np.zeros(mod.S_NSTATE)
    st[mod.S_U], st[mod.S_Q] = 1.0, 1.0 / 100.0
    st[mod.S_PEND], st[mod.S_PDQ], st[mod.S_PLIM] = 1.0, -0.5, 1000.0
    st[mod.S_PSTART], st[mod.S_PEXP], st[mod.S_PKIND], st[mod.S_PTGT] = 101, 10_000, mod.K_RED, 0.5
    pnl, up = np.zeros(n), np.zeros(n)
    mod.advance(o, h, l, c, (t // 86_400_000_000_000).astype(np.int64), np.full(n, np.nan), st, pnl, up, 100, 201,
                0.5, 2.0, 0.5)
    return st


def test_partial_reduce_stop_becomes_full_flatten():
    st = _partial_reduce_case(MK)
    assert st[MK.S_FPOS] == 1 and st[MK.S_PEND] == 1 and st[MK.S_PTGT] == 0.0
    assert st[MK.S_PDQ] == -1.0 and st[MK.S_PKIND] == MK.K_RED and st[MK.S_PSTOP] == 1
