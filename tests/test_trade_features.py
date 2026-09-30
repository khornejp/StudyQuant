"""Guards for the trade-activity features.

The one that matters is the big-print threshold. Taking it from the day the
feature describes lets a print at 23:59 change the value at 00:00, which is a
look-ahead that no later test would catch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import build_trade_features as trades


def day(quantities, minutes=None, buys=None):
    n = len(quantities)
    stamps = pd.date_range("2024-01-01", periods=n, freq="s", tz="UTC")
    if minutes is not None:
        stamps = pd.to_datetime(minutes, utc=True)
    return pd.DataFrame({
        "quantity": np.asarray(quantities, float),
        "minute": pd.Series(stamps).dt.floor("min"),
        "aggressive_buy": np.ones(n, bool) if buys is None else np.asarray(buys, bool),
    })


def test_the_big_print_threshold_comes_from_outside_the_day():
    quiet = day([1.0] * 59 + [1000.0])          # the whale prints last
    # with yesterday's threshold of 2.0, the whale counts as big everywhere
    out = trades.summarise(quiet, cut=2.0)
    assert out.big_qty.sum() == pytest.approx(1000.0)
    # and with no previous day the feature is unknown, never guessed
    unknown = trades.summarise(quiet, cut=None)
    assert unknown.big_qty.isna().all()


def test_a_late_print_cannot_change_an_earlier_minute():
    early = pd.to_datetime(["2024-01-01 00:00:10", "2024-01-01 00:00:20"], utc=True)
    late = pd.to_datetime(["2024-01-01 23:59:00"], utc=True)
    without = trades.summarise(day([1.0, 1.0], minutes=early), cut=5.0)
    with_late = trades.summarise(day([1.0, 1.0, 9999.0],
                                     minutes=list(early) + list(late)), cut=5.0)
    first = pd.Timestamp("2024-01-01 00:00", tz="UTC")
    assert without.loc[first].big_qty == with_late.loc[first].big_qty == 0.0
    assert without.loc[first].quantity == with_late.loc[first].quantity


def test_aggression_polarity():
    # is_buyer_maker true means the buyer rested and a seller crossed
    frame = pd.DataFrame({"price": [1.0, 1.0], "quantity": [2.0, 3.0],
                          "transact_time": [0, 1], "is_buyer_maker": [True, False]})
    frame["minute"] = pd.to_datetime(frame.transact_time, unit="ms", utc=True).dt.floor("min")
    frame["aggressive_buy"] = ~frame.is_buyer_maker.astype(bool)
    out = trades.summarise(frame, cut=100.0)
    assert out.buy_qty.iloc[0] == pytest.approx(3.0), "only the crossing buyer counts"


def test_surge_is_measured_against_the_past_not_the_whole_file():
    index = pd.date_range("2024-01-01", periods=500, freq="min", tz="UTC")
    per_minute = pd.DataFrame({"trade_count": np.r_[np.full(499, 10.0), 1000.0],
                               "quantity": np.full(500, 100.0),
                               "buy_qty": np.full(500, 50.0),
                               "big_qty": np.full(500, 10.0)}, index=index)
    out = trades.features(per_minute)
    assert out.trade_count_surge.iloc[-1] > 50, "the spike must read as a spike"
    assert out.trade_count_surge.iloc[300] == pytest.approx(1.0, abs=.01), \
        "a quiet minute before it must not be dragged by the later spike"
