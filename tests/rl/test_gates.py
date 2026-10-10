"""Consistent admission gates (btcusdt_quant/rl/gates.py) and the MA100 entry-veto episode rule; the G3 combined
reference values are reproduced on the local DEV data (skipped when absent)."""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import gates as GT

ROOT = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_boot_matches_batch2():
    b2 = _load("nm_b2_gate_t", "out/run_new_model_batch2_20261010.py")
    x = np.random.default_rng(3).normal(1, 5, 900)
    for bl in (20, 60, 120):
        assert GT.boot_p05(x, bl, n_boot=3000) == b2.stationary_boot_p05(x, bl, n_boot=3000)


def test_evaluate_counts_and_paired():
    rng = np.random.default_rng(0)
    cells = {}
    for k in range(2):
        d = rng.normal(5, 3, GT.N_DAYS)
        cells[f"c{k}"] = {"daily": d, "closed": {y: 40 for y in GT.YEARS}}
    cells["c1"]["closed"][2023] = 10
    base = {c: v["daily"] - 1.0 for c, v in cells.items()}
    r = GT.evaluate(cells, baseline=base)
    assert r["absolute"]["year_cell_net4>0"] == "8/8" and r["absolute"]["year_cell_closed>=30"] == "7/8"
    assert not r["absolute"]["pass"] and r["replacement"]["pass"]
    assert np.isclose(r["cells"]["c0"]["paired_excess"]["net4"], GT.N_DAYS)
    with pytest.raises(ValueError):
        GT.evaluate({"x": {"daily": np.zeros(10), "closed": {y: 0 for y in GT.YEARS}}})


def test_veto_episode_fixed_at_first_decision():
    mod = _load("pra_gate_t", "scripts/precompute_rl_allocator.py")
    side = np.array([0, 1, 1, 1, 0, 1, 1, -1, -1, 0])
    allowed = np.array([1, 0, 1, 1, 1, 1, 0, 0, 1, 1], bool)
    ok, eps = mod.veto_entry_ok(side, allowed)
    assert ok.tolist() == [True, False, False, False, True, True, True, False, False, True]
    assert [(e[0], e[1], e[2], e[3]) for e in eps] == [(1, 3, 1, False), (5, 6, 1, True), (7, 8, -1, False)]


HAVE = (ROOT / "artifacts/btcusdt_2020_2026h1.parquet").exists() and (ROOT / "out/run_lbr_fund_materialize_20261010.py").exists()


@pytest.mark.skipif(not HAVE, reason="local DEV data absent")
def test_g3_combined_reference_values():
    mod = _load("pra_gate_ref_t", "scripts/precompute_rl_allocator.py")
    MAT, m, dec4, st, _ = mod.g3_setup()
    base = mod.g3_combined(MAT.b2, m, dec4, mod.g3_signals(MAT, st))
    r = GT.evaluate({c: {"daily": v["daily"], "closed": v["closed"]} for c, v in base.items()})
    p60 = [x["pooled_boot_p05"]["60"] for x in r["cells"].values()]
    net = [x["pooled_net4"] for x in r["cells"].values()]
    assert r["diagnostics"]["year_cell_block_boot_p05>0"] == "37/72"
    assert r["absolute"]["pooled_boot60_p05>0"] == "6/6"
    assert abs(min(p60) - 5.068) < 5e-4 and abs(max(p60) - 5.872) < 5e-4
    assert abs(min(net) - 16136.077) < 5e-3 and abs(max(net) - 16967.267) < 5e-3
