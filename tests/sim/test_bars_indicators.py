import numpy as np, pandas as pd
from btcusdt_quant.sim import bars, indicators

def minutes(n, start="2024-01-01"):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    c = np.arange(1, n + 1, dtype=float)
    return pd.DataFrame({"open_time": t, "open": c, "high": c + .5, "low": c - .5, "close": c,
                         "volume": 1., "quote_volume": 1., "number_of_trades": 1, "taker_buy_base_volume": .25})

def test_aggregate_complete_only_and_decision_time():
    b = bars.aggregate(minutes(31), 15)
    assert len(b) == 2                                   # 31st minute starts an incomplete bar
    assert b.decision_time.iloc[0] == pd.Timestamp("2024-01-01 00:15", tz="UTC")
    assert b.open.iloc[0] == 1 and b.close.iloc[0] == 15 and b.high.iloc[0] == 15.5 and b.volume.iloc[0] == 15

def test_ema_matches_recursion():
    x = pd.Series([1., 2., 3.]); a = 2 / (2 + 1)
    expected = [1., a * 2 + (1 - a) * 1, None]; expected[2] = a * 3 + (1 - a) * expected[1]
    assert np.allclose(indicators.ema(x, 2), expected)

def test_rsi_all_up_is_100():
    assert indicators.rsi(pd.Series(np.arange(30, dtype=float)), 14).iloc[-1] == 100

def test_bollinger_population_std():
    out = indicators.bollinger(pd.Series([1., 2., 3.]), n=3, k=2)
    std = np.std([1, 2, 3])
    assert np.isclose(out.upper.iloc[-1], 2 + 2 * std)

def test_zscore_past_excludes_current():
    x = pd.Series([0., 0., 0., 10.])
    z = indicators.zscore_past(x, 3, 3)
    assert np.isinf(z.iloc[3]) or np.isnan(z.iloc[3])   # past std 0
    y = pd.Series([1., 2., 3., 100.])
    assert np.isclose(indicators.zscore_past(y, 3, 3).iloc[3], (100 - 2) / np.std([1, 2, 3]))

def test_vwap_resets_each_utc_day():
    m = minutes(2 * 1440, start="2024-01-01")
    b = bars.aggregate(m, 15)
    v = indicators.vwap_utc(b)
    first_next_day = b.index[b.bar_start.eq(pd.Timestamp("2024-01-02", tz="UTC"))][0]
    assert np.isclose(v.loc[first_next_day], (b.loc[first_next_day, ["high", "low", "close"]].mean()))
