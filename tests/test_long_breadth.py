"""Checks for out/run_long_breadth_20261010.py (synthetic data + the latest LB run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("lb", ROOT / "out/run_long_breadth_20261010.py")
lb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lb)
b2, b5, MIN = lb.b2, lb.b5, lb.b2.MIN


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


@pytest.fixture(scope="module")
def syn():
    m = synth_market()
    dec4 = np.arange(239, m.N, 240)
    return m, dec4, b5.build_state(m, dec4)


def test_grid():
    assert len(lb.GRID) == 9 and lb.BASE in lb.GRID and len({lb.cid(*g) for g in lb.GRID}) == 9


def test_baseline_matches_b5_and_monotone(syn):
    m, dec4, st = syn
    base = lb.long_signal(st, *lb.BASE)
    ref = b5.core_signal(st, lb.B5_PICK)
    assert np.array_equal(base["side"] == 1, ref["side"] == 1)
    assert np.allclose(base["w"][base["side"] == 1], ref["w"][ref["side"] == 1])
    for g in lb.GRID:
        s = lb.long_signal(st, *g)
        assert np.all(s["side"] >= base["side"]) and set(np.unique(s["side"])) <= {0, 1}
        assert np.all(s["w"][s["side"] == 0] == 0) and np.all(s["w"] <= 1)


def test_not_ready_flat(syn):
    _, _, st = syn
    s = lb.long_signal(st, 0.30, 0.0)
    nr = ~np.isfinite(st["w"][lb.VOL]) | ~np.isfinite(st["score"][lb.TREND])
    assert nr.any() and np.all(s["side"][nr] == 0)


def test_trade_partition_and_top_share(syn):
    m, dec4, st = syn
    s = lb.long_signal(st, 0.30, 0.0)
    tr, od = b2.simulate(m, "state", dec4, s["side"], s["w"], 2, b2.TTL_TREND, 0.5, 0, m.N)
    bk = b2.Book(m, tr, od, 0, m.N)
    a, b = 1440 * 200, 1440 * 600
    part = lb.trade_part(bk, a, b)
    assert len(part) and np.isclose(part.sum(), bk.window(a, b)["net4"])
    assert lb.top_share(np.array([3.0, 1.0, -2.0]), 2.0, 1) == 1.5 and lb.top_share(np.array([3.0, 1.0, -2.0]), 2.0, 3) == 1.0


def test_select_and_success_rules():
    cm = pd.DataFrame({"config_id": ["a", "b", "c"], "dev_eligible": [False, True, True],
                       "dev_score": [9.0, 1.0, 1.0], "DEV-FULL_mdd": [1.0, 5.0, 3.0]})
    assert lb.select(cm) == ("c", True)
    assert lb.select(cm.assign(dev_eligible=False)) == ("a", False)
    R = {(o, p): {"TEST": {"long_net4": 1.0, "long_closed": 30}} for o in lb.OFFSETS for p in lb.PENS}
    boot = {("TEST", bl): 0.1 for bl in lb.BLOCKS}
    assert lb.test_success(R, boot)["SUCCESS"]
    R[(5, 2.0)]["TEST"]["long_net4"] = -1.0
    assert not lb.test_success(R, boot)["SUCCESS"]


def test_run_outputs():
    runs = sorted(r for r in lb.OUT_BASE.glob("LB-*") if (r / "manifest.json").exists()) if lb.OUT_BASE.exists() else []
    if not runs:
        pytest.skip("no LB run output")
    man = json.loads((runs[-1] / "manifest.json").read_text(encoding="utf-8"))
    cm = pd.read_parquet(runs[-1] / "config_metrics.parquet")
    assert len(cm) == 9 and man["counts"]["sims"] == 54
    assert man["parity"]["max_abs_diff_4dp"] <= 5e-5 and man["parity"]["cells_max_abs_diff_vs_b5"] <= 1e-6
    assert len(pd.read_parquet(runs[-1] / "fold_metrics.parquet")) == 54 * 4
