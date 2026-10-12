"""Gate-0 scaler: default fixed 2021 fit (same arrays every month); 'expanding' refits per month."""
import importlib.util
from pathlib import Path
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pra_g0", ROOT / "scripts/precompute_rl_allocator.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def _cache(rows=1000, seed=0):
    rng = np.random.default_rng(seed)
    tok = rng.normal(size=(rows, 44, 20)).astype(np.float32)
    tok[:, :, :6] = rng.integers(-1, 2, size=(rows, 44, 6))
    return {"tok": tok, "mkt": rng.normal(size=(rows, 60)).astype(np.float32)}


def test_fixed_default_and_expanding(monkeypatch):
    clk = np.arange(1000, dtype=np.int64) * 86_400_000_000_000 // 4 + np.int64(1_611_964_800_000_000_000)  # 2021-01-30 + 6h steps
    c = _cache()
    M._FEATS_CACHE.clear()
    assert M.SCALER_MODE == "fixed2021"
    m1 = int(clk[300]); m2 = int(clk[900])
    a = M.a6_feats(c, clk, m1, 1000)
    b = M.a6_feats(c, clk, m2, 1000)
    assert a is b                                            # one 2021 fit, never refit
    e1 = M.a6_feats(c, clk, m1, 1000, mode="expanding")
    e2 = M.a6_feats(c, clk, m2, 1000, mode="expanding")
    assert not np.array_equal(e1[0], e2[0])                  # expanding refits month by month
