import numpy as np
import pandas as pd

from btcusdt_quant.sim.strategies import CATALOG, levels


def _bars(highs, lows=None, closes=None, freq="60min"):
    n = len(highs)
    t = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    highs = np.asarray(highs, float)
    lows = highs - 2 if lows is None else np.asarray(lows, float)
    closes = highs - 1 if closes is None else np.asarray(closes, float)
    return pd.DataFrame({"bar_start": t, "decision_time": t + pd.Timedelta(freq), "open": closes,
                         "high": highs, "low": lows, "close": closes})


def test_reject_trades_against_pierced_level():
    b = _bars([101, 99, 101], lows=[95, 89, 98], closes=[99, 91, 101])
    side = levels._reject(b, above=[100, 100, 100], below=[90, 90, 90])
    assert side.tolist() == [-1, 1, 0]          # closed back under / back over / closed beyond: no trade


def test_swing_high_is_known_only_after_five_bars():
    highs = [1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1, 1]
    swings = levels._swings(_bars(highs), "high", 1)
    assert swings.tolist() == [10.0]
    h = _bars(highs)
    assert swings.index[0] == h.decision_time.iloc[10]     # swing bar 5 + 5 right-hand bars
    before = levels._asof(swings, pd.Series([h.decision_time.iloc[10] - pd.Timedelta(minutes=1)]))
    assert np.isnan(before[0])


def test_catalog_registers_level_family():
    assert {"K25", "K26", "K27", "K28", "K29", "K30"} <= set(CATALOG)
    assert all(CATALOG[k].family == "levels" and CATALOG[k].gate == "LOW" for k in ("K25", "K26", "K27", "K28"))
    assert CATALOG["K29"].family == "levels" and CATALOG["K29"].gate == "LOW"
    assert CATALOG["K30"].family == "levels" and CATALOG["K30"].gate == "HIGH"
    assert CATALOG["K29"].e_head == CATALOG["K30"].e_head == "4h"
