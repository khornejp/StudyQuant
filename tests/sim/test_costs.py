import numpy as np, pandas as pd
from btcusdt_quant.sim import costs

def test_fee_per_partial_fill():
    assert costs.fee_bps(1.0) == 2.0 and costs.fee_bps(.5) == 1.0

def test_funding_matches_reference_module():
    entry = pd.Timestamp("2024-01-01 07:00", tz="UTC"); exit_ = pd.Timestamp("2024-01-01 09:00", tz="UTC")
    value = costs.funding_bps(1, entry, exit_)
    ref = costs._funding_module().trade_funding(1, entry, exit_, costs._settlements(), "PESS")
    assert np.isclose(value, sum(ref))

def test_slippage_scales_and_caps():
    assert costs.slippage_bps(1, 10, 20, k=.5) == .5 * 20 * .1
    assert costs.slippage_bps(100, 10, 20, k=.5) == 10

def test_latency_sampler_rounds_up_minimum_one():
    draw = costs.latency_sampler(np.array([1000.0]), np.random.default_rng(0))
    assert draw() == 1
    draw = costs.latency_sampler(np.array([61000.0]), np.random.default_rng(0))
    assert draw() == 2

def test_funding_archive_independent_of_cwd(tmp_path, monkeypatch):
    costs._settlements.cache_clear()
    monkeypatch.chdir(tmp_path)
    try:
        assert len(costs._settlements()) > 7000
    finally:
        costs._settlements.cache_clear()
