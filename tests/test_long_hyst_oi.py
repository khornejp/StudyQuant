"""Checks for out/run_long_hyst_oi_20261010.py (synthetic data + the latest LH run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("lh", ROOT / "out/run_long_hyst_oi_20261010.py")
lh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lh)
b2, b5, MIN = lh.b2, lh.b5, lh.b2.MIN


def synth_market(days=800, seed=3, vol=6e-4):
    rng = np.random.default_rng(seed)
    n = 1440 * days
    reg = np.repeat(rng.choice([-1, 1], n // (1440 * 20) + 1), 1440 * 20)[:n]
    c = 100 * np.exp(np.cumsum(rng.normal(reg * 2e-5, vol, n)))
    o = np.concatenate([[c[0]], c[:-1]])
    t = b2.START.value + np.arange(n) * MIN
    ft = b2.START.value + np.arange(0, n, 480) * MIN + 8_000_000
    return b2.Market(t, o, np.maximum(o, c) * 1.002, np.minimum(o, c) * 0.998, c, np.ones(n), np.full(n, 0.5),
                     ft, rng.normal(1e-4, 1e-4, len(ft)))


def synth_met(m, seed=5):
    rng = np.random.default_rng(seed)
    av = np.arange(m.t[0] + 5 * MIN, m.t[-1], 5 * MIN)
    oi = 1e4 * np.exp(np.cumsum(rng.normal(0, 3e-3, len(av))))
    met = pd.DataFrame({"available_time": pd.to_datetime(av, utc=True), "oi": oi})
    return met.drop(index=range(3000, 3400)).reset_index(drop=True)      # a gap -> stale/missing OI


@pytest.fixture(scope="module")
def syn():
    m = synth_market()
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    met = synth_met(m)
    return m, dec4, st, met, lh.oi_state(met, st["T"])


def test_grid():
    assert len(lh.GRID) == 9 and lh.BASE in lh.GRID and len({lh.cid(*g) for g in lh.GRID}) == 9


def test_oi_state_causal_and_z(syn):
    m, dec4, st, met, oi = syn
    T = st["T"]
    f = np.isfinite(oi["oi_t"])
    assert np.all(oi["avail_t"][f] <= T[f]) and np.all(T[f] - oi["avail_t"][f] <= 10 * MIN)
    f24 = np.isfinite(oi["oi_24"])
    assert np.all(oi["avail_24"][f24] <= T[f24] - b2.DAY) and np.all(T[f24] - b2.DAY - oi["avail_24"][f24] <= 10 * MIN)
    assert (~f).any()                                                  # gap gives NaN (age > 10m)
    d, z = oi["doi"], oi["zoi"]
    assert np.all(np.isnan(z[:540]))
    rng = np.random.default_rng(0)
    for k in rng.choice(np.flatnonzero(np.isfinite(z)), 50, replace=False):
        s = d[max(0, k - 1080):k]
        s = s[np.isfinite(s)]
        med = np.median(s)
        assert len(s) >= 540 and np.isclose(z[k], (d[k] - med) / (1.4826 * np.median(np.abs(s - med))))
    # future tamper leaves the past unchanged
    mt = met.copy()
    cut = T[len(T) // 2]
    mt.loc[mt.available_time.array.asi8 > cut, "oi"] *= 3
    o2 = lh.oi_state(mt, T)
    k = len(T) // 2 + 1
    assert np.array_equal(oi["zoi"][:k], o2["zoi"][:k], equal_nan=True)


def test_hysteresis_rules(syn):
    _, _, st, _, oi = syn
    base = lh.long_hysteresis_signal(st, None, *lh.BASE)
    ref = b5.core_signal(st, lh.B5_PICK)
    assert np.array_equal(base["side"] == 1, ref["side"] == 1)
    sc, svi = st["score"][lh.TREND], st["svi"][lh.SW]
    for se, ve, g in lh.GRID:
        s = lh.long_hysteresis_signal(st, oi["zoi"], se, ve, g)["side"]
        prev = np.concatenate([[0], s[:-1]])
        start = (prev == 0) & (s == 1)
        with np.errstate(invalid="ignore"):
            assert np.all(sc[start] >= 0.5) and np.all(svi[start] >= 0.1)
            if g is not None:
                assert np.all(oi["zoi"][start] >= g)                   # NaN never starts (fail-closed)
            held = (prev == 1) & (s == 1)
            assert np.all(sc[held] >= se) and np.all(svi[held] >= ve)
        nr = ~np.isfinite(st["w"][lh.VOL]) | ~np.isfinite(sc) | ~np.isfinite(svi)
        assert np.all(s[nr] == 0)
        if g is not None:
            lh.no_forced_exit(lh.long_hysteresis_signal(st, oi["zoi"], se, ve, None), {"side": s})
    # lower exits only extend holding
    a = lh.long_hysteresis_signal(st, None, 0.5, 0.1, None)["side"]
    b = lh.long_hysteresis_signal(st, None, 0.0, 0.0, None)["side"]
    assert np.all(b >= a) and b.sum() > a.sum()


def test_gate_does_not_close_held(syn):
    _, _, st, _, oi = syn
    off = lh.long_hysteresis_signal(st, oi["zoi"], 0.25, 0.05, None)
    z = oi["zoi"].copy()
    on = lh.long_hysteresis_signal(st, z, 0.25, 0.05, -0.5)
    i = np.flatnonzero(on["side"] == 1)
    z2 = z.copy()
    z2[i[0] + 1:] = np.nan                                             # gate fails after first entry
    on2 = lh.long_hysteresis_signal(st, z2, 0.25, 0.05, -0.5)
    run_end = i[0] + np.argmax(on["side"][i[0]:] == 0)
    assert np.all(on2["side"][i[0]:run_end] == 1) and np.all(on2["side"][run_end:] == 0)
    lh.no_forced_exit(off, on)


def test_select_rules():
    cm = pd.DataFrame({"config_id": ["a", "b", "c", "d"], "dev_eligible": [False, True, True, True],
                       "dev_score": [9.0, 1.0, 1.0, -1.0], "DEV-B_net4": [0, 5.0, 5.0, 9.0],
                       "DEV-A_net4": [0, 1.0, 2.0, 9.0], "DEV-FULL_mdd": [1.0, 5.0, 9.0, 1.0]})
    assert lh.select(cm, -0.329384) == ("c", True)
    assert lh.select(cm.assign(dev_eligible=False), -0.329384) == ("a", False)
    R = {(o, p): {"TEST": {"long_net4": 1.0}} for o in lh.OFFSETS for p in lh.PENS}
    boot = {("TEST", bl): 0.1 for bl in lh.BLOCKS}
    assert lh.test_success(R, boot)["SUCCESS"]
    boot[("TEST", 120)] = -0.1
    assert not lh.test_success(R, boot)["SUCCESS"]


def test_run_outputs():
    runs = sorted(r for r in lh.OUT_BASE.glob("LH-*") if (r / "manifest.json").exists()) if lh.OUT_BASE.exists() else []
    if not runs:
        pytest.skip("no LH run output")
    man = json.loads((runs[-1] / "manifest.json").read_text(encoding="utf-8"))
    cm = pd.read_parquet(runs[-1] / "config_metrics.parquet")
    assert len(cm) == 9 and man["counts"]["sims"] == 54
    p = man["parity_b5_long_sleeve"]
    assert p["trades_equal"] and p["cells_max_abs_diff"] <= 1e-6 and p["daily_max_abs_diff"] <= 1e-6
    assert len(pd.read_parquet(runs[-1] / "fold_metrics.parquet")) == 54 * 4
    dec = pd.read_parquet(runs[-1] / "decisions.parquet")
    assert (dec.decision_available_time - dec.bar_time == pd.Timedelta(minutes=1)).all()
    f = dec.oi_T_available_time.notna()
    assert (dec.oi_T_available_time[f] <= dec.decision_available_time[f]).all()
