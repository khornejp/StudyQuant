from btcusdt_quant.sim import intrabar

def test_symmetric_bar_near_half():
    p = intrabar.first_touch_probability(100, 101, 99, 100, stop=99, take=101, side=1, n_paths=2000)
    assert .35 < p < .65

def test_close_at_high_favours_take_last():
    p = intrabar.first_touch_probability(100, 101, 99, 101, stop=99, take=101, side=1, n_paths=2000)
    assert p > .5   # path ends at high, so the low (stop) was more likely reached first

def test_resimulate_ambiguous_redraws_and_requires_take():
    import numpy as np, pandas as pd, pytest
    t = pd.date_range("2024-01-01", periods=3, freq="1min", tz="UTC")
    m = pd.DataFrame({"open_time": t, "open": 100., "high": [100., 101.5, 100.], "low": [100., 98.5, 100.], "close": 100.})
    trades = pd.DataFrame({"exit_time": [t[1]] * 50, "exit_reason": "stop", "side": 1, "units": 1.0,
                           "entry_price": 100.0, "exit_price": 99.0, "gross_bps": np.log(.99) * 1e4,
                           "fee_bps": 4.0, "funding_bps": 0.0, "net_bps": np.log(.99) * 1e4 - 4})
    with pytest.raises(ValueError, match="take_bps"):
        intrabar.resimulate_ambiguous(trades, m, 0)
    out = intrabar.resimulate_ambiguous(trades.assign(take_bps=100.0), m, 0)
    assert 0 < (out.exit_reason == "take_resampled").sum() < 50
    assert np.allclose(out.loc[out.exit_reason == "take_resampled", "net_bps"], np.log(1.01) * 1e4 - 4)
