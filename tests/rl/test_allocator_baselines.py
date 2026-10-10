"""Static baseline scorer (btcusdt_quant/rl/allocator_baselines.py): grid, linear scoring vs direct computation,
bootstrap, ranking and tie-break. Synthetic data."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import allocator_baselines as BL


def test_grid_and_named():
    W = BL.candidate_grid()
    assert W.shape == (5595, 7) and W.sum(1).max() == 2.0 and set(np.unique(W)) == {0, .25, .5, .75, 1}
    assert len({tuple(r) for r in W}) == 5595
    assert np.isclose(BL.named_baselines()["STATIC_EQUAL_2_7"].sum(), 2.0)


def test_score_matches_direct_computation():
    rng = np.random.default_rng(0)
    T = 24 * 50
    unit = rng.normal(0, 3, (T, 7))
    turn = rng.uniform(0, 1, (T, 7))
    day = np.arange(T) // 24
    W = BL.candidate_grid()[rng.choice(5595, 40, replace=False)]
    idx = BL.stationary_indices(50, n_boot=500)
    sc = BL.score(unit, turn, day, W, idx, chunk=7)
    for i, w in enumerate(W):
        x = unit @ w
        eq = np.r_[0.0, np.cumsum(x)]
        assert np.isclose(sc.net4[i], x.sum()) and np.isclose(sc.turnover[i], (turn @ w).sum())
        assert np.isclose(sc.mdd[i], (np.maximum.accumulate(eq) - eq).max())
        d = pd.Series(x).groupby(day).sum().to_numpy()
        assert np.isclose(sc.boot_p05[i], np.quantile(d[idx].mean(1), 0.05))


def test_rank_lexicographic_and_tie_break():
    W = np.array([[1, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0], [0.5, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0.]])
    mk = lambda net, p, mdd: pd.DataFrame({"net4": net, "boot_p05": p, "mdd": mdd, "turnover": [1.0] * 4})  # noqa
    cells = {"a": mk([5, 5, 5, 4], [1, 1, 1, 9], [3, 3, 3, 0]), "b": mk([6, 5, 9, 9], [1, 1, 1, 9], [3, 3, 3, 0])}
    r = BL.rank(cells, W)
    assert r.cand.tolist()[:3] == [2, 1, 0]          # equal keys -> smaller sum, then lexicographic weights
    assert r.cand.iloc[-1] == 3                       # lowest min net loses despite better p05 / mdd
