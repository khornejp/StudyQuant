"""Causal regime router (btcusdt_quant/rl/allocator_router.py) and the opt-in 90d/180d lookbacks."""
import numpy as np
from btcusdt_quant.rl import allocator_router as AR
from btcusdt_quant.rl import allocator_state as ast


def test_top2_positive_available_only():
    sc = np.array([[5, 3, np.nan, 9, -1, 0.5, 2],
                   [-1, -2, -3, -4, -5, -6, -7],
                   [1, 1, 1, 1, 1, 1, 1.0]])
    av = np.array([[1, 1, 1, 0, 1, 1, 1], [1] * 7, [0, 1, 1, 1, 1, 1, 1]], bool)
    lv = AR.router_levels(sc, av)
    assert lv[0].tolist() == [4, 4, 0, 0, 0, 0, 0]          # 9 unavailable, NaN skipped
    assert lv[1].tolist() == [0] * 7                         # nothing positive -> all OFF
    assert lv[2].tolist() == [0, 4, 4, 0, 0, 0, 0]           # tie -> sleeve order, unavailable skipped
    assert (lv > 0).sum(1).max() <= 2


def test_long_mtm_is_opt_in(monkeypatch=None):
    import importlib.util, sys
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("tas_t", Path(__file__).with_name("test_allocator_state.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    mk, met, prem, ft, fr, grid, led = m.world()
    T = m.T_GRID[:50]
    a = ast.sleeve_channels("S", grid, led, mk["c"], T)
    b = ast.sleeve_channels("S", grid, led, mk["c"], T, long_mtm=True)
    assert "S_mtm_90d" not in a and [c for c in b.columns if c in a.columns] == list(a.columns)
    assert set(b.columns) - set(a.columns) == {"S_mtm_90d", "S_mtm_180d"}
    for c in a.columns:
        assert np.array_equal(a[c].to_numpy(), b[c].to_numpy(), equal_nan=True)
    assert np.allclose(np.nan_to_num(b.S_mtm_180d), np.nan_to_num(b.S_mtm_90d))   # 40-day world: same window
