import numpy as np, pandas as pd
from btcusdt_quant.sim import analytics

def test_degenerate_inputs_do_not_raise():
    for f in (analytics.pw_mean_ci, analytics.hac_mean_ci):
        assert f(np.zeros(10))["reason"] == "zero_variance"
        assert f(np.array([]))["reason"] == "empty"
    assert analytics.white_rc(np.zeros((50, 3)))["reason"] == "constant"

def test_hac_mean_matches_simple_mean_and_covers_truth():
    x = np.random.default_rng(1).normal(1.0, 1.0, 5000)
    r = analytics.hac_mean_ci(x)
    assert abs(r["mean"] - x.mean()) < 1e-12 and r["lower"] < 1.0 < r["upper"]

def test_spa_and_white_reject_strong_signal_and_not_noise():
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 1, (1000, 5)); strong = noise.copy(); strong[:, 0] += .3
    assert analytics.white_rc(strong)["p"] < .05 and analytics.hansen_spa(strong)["p"] < .05
    assert analytics.hansen_spa(noise)["p"] > .05

def test_spa_not_more_conservative_than_white_with_bad_models():
    rng = np.random.default_rng(3)
    d = rng.normal(0, 1, (800, 6)); d[:, 0] += .12; d[:, 1:] -= 1.0
    assert analytics.hansen_spa(d)["p"] <= analytics.white_rc(d)["p"] + 1e-9

def test_pbo_drops_duplicate_columns_and_flags_overfit():
    rng = np.random.default_rng(4)
    m = pd.DataFrame(rng.normal(0, 1, (400, 10)))
    m[10] = m[0]
    r = analytics.cscv_pbo(m, splits=8)
    assert r["n_strategies"] == 10
    # a single noise dataset's PBO varies widely (seed 4 gives 0.94); its mean over datasets is ~0.5
    noise = [analytics.cscv_pbo(pd.DataFrame(np.random.default_rng(s).normal(0, 1, (400, 10))), splits=8)["pbo"]
             for s in range(20)]
    assert .35 < np.mean(noise) < .65
    skill = pd.DataFrame(np.random.default_rng(9).normal(0, 1, (400, 10))); skill[0] += .3
    assert analytics.cscv_pbo(skill, splits=8)["pbo"] < .1

def test_dsr_penalises_many_trials():
    x = np.random.default_rng(5).normal(.05, 1, 1000)
    trials = np.random.default_rng(6).normal(0, .03, 500)
    assert analytics.deflated_sharpe(x, trials, 5000)["dsr"] < analytics.deflated_sharpe(x, trials, 2)["dsr"]

def test_monte_carlo_quantiles_ordered():
    r = analytics.trade_monte_carlo(np.array([10., -5., 3., -1.]), reps=2000)
    assert r["final_q05"] <= r["final_median"] <= r["final_q95"]
