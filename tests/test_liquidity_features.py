"""Guards for the liquidity channels.

Each of these pins one defect review found in the first draft: a print gate that
silently demanded one trade more than it said, a mask that Amihud did not
inherit, a surge that divided by a near-zero median and called the infinity
valid, and a negative-share report computed over the wrong denominator.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import build_liquidity_features as liquidity


def prints(prices, quantities=None, buyer_maker=None, minute="2024-01-01 00:00"):
    n = len(prices)
    return pd.DataFrame({
        "price": np.asarray(prices, float),
        "quantity": np.ones(n) if quantities is None else np.asarray(quantities, float),
        "signed_qty": (np.ones(n) if quantities is None else np.asarray(quantities, float))
        * (np.where(np.asarray(buyer_maker, bool), -1.0, 1.0) if buyer_maker is not None else 1.0),
        "minute": pd.to_datetime([minute] * n, utc=True),
    })


def test_the_print_gate_means_what_it_says():
    # exactly MIN_PRINTS trades must pass; the pairs are one fewer and must not
    # secretly raise the bar
    rng = np.random.default_rng(0)
    exact = prints(100 + rng.normal(0, .5, liquidity.MIN_PRINTS),
                   buyer_maker=rng.integers(0, 2, liquidity.MIN_PRINTS).astype(bool))
    out = liquidity.summarise(exact)
    assert np.isfinite(out.volume.iloc[0]), "MIN_PRINTS trades must clear the gate"

    short = prints(100 + rng.normal(0, .5, liquidity.MIN_PRINTS - 1),
                   buyer_maker=rng.integers(0, 2, liquidity.MIN_PRINTS - 1).astype(bool))
    assert np.isnan(liquidity.summarise(short).volume.iloc[0])


def test_amihud_inherits_the_same_gate_as_kyle():
    # a one-print minute used to yield a finite Amihud of 100.0
    tiny = prints([100.0], quantities=[0.01], buyer_maker=[False])
    per_minute = liquidity.summarise(tiny).set_index("minute")
    assert np.isnan(per_minute.volume.iloc[0]), "volume must be masked, not merely small"

    bars = pd.DataFrame({
        "open_time": pd.to_datetime(["2023-12-31 23:59", "2024-01-01 00:00"], utc=True),
        "close": [100.0, 101.0]})
    table = liquidity.features(per_minute, bars)
    assert table.amihud_illiquidity.isna().all(), "Amihud must not survive a failed gate"
    assert not table.liquidity_valid.any()


def test_a_near_zero_reference_does_not_make_an_infinite_surge():
    index = pd.date_range("2024-01-01", periods=400, freq="min", tz="UTC")
    per_minute = pd.DataFrame({"volume": np.full(400, 10.0),
                               "kyle_lambda": np.full(400, 1e-320),
                               "mid": np.full(400, 100.0)}, index=index)
    per_minute.index.name = "minute"
    bars = pd.DataFrame({"open_time": index, "close": np.full(400, 100.0)})
    table = liquidity.features(per_minute, bars)
    assert np.isfinite(table.kyle_lambda_surge.dropna()).all(), "no inf may escape"
    assert not table.liquidity_valid.to_numpy()[np.isinf(table.kyle_lambda_surge.to_numpy())].any()


def test_kyle_can_come_out_negative():
    # selling into a rising print sequence gives a negative slope; an estimator
    # that cannot produce one is a magnitude, not a slope
    rng = np.random.default_rng(3)
    n = 60
    price = 100 + np.cumsum(rng.normal(0, .3, n))
    signed = -np.diff(price, prepend=price[0])       # flow that opposes the move
    frame = pd.DataFrame({"price": price, "quantity": np.abs(signed) + .1,
                          "signed_qty": signed,
                          "minute": pd.to_datetime(["2024-01-01 00:00"] * n, utc=True)})
    assert liquidity.summarise(frame).kyle_lambda.iloc[0] < 0


def test_kyle_is_positive_when_buying_pushes_price_up():
    n = 60
    step = np.r_[0.0, np.full(n - 1, 0.1)]
    price = 100 + np.cumsum(step)
    frame = pd.DataFrame({"price": price, "quantity": np.ones(n),
                          "signed_qty": np.ones(n),          # every print a buy
                          "minute": pd.to_datetime(["2024-01-01 00:00"] * n, utc=True)})
    value = liquidity.summarise(frame).kyle_lambda.iloc[0]
    assert np.isnan(value) or value >= 0, "constant flow gives no slope, never a wrong sign"


def test_amihud_uses_the_bars_own_return():
    index = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    per_minute = pd.DataFrame({"volume": [10.0, 10.0, 10.0],
                               "kyle_lambda": [0.01, 0.01, 0.01],
                               "mid": [100.0, 100.0, 100.0]}, index=index)
    per_minute.index.name = "minute"
    bars = pd.DataFrame({"open_time": index, "close": [100.0, 101.0, 100.0]})
    table = liquidity.features(per_minute, bars)
    # bar 1 moved 100 -> 101, which is +100 bps, on volume 10: 10 bps per unit
    assert table.amihud_illiquidity.iloc[1] == pytest.approx(10.0, rel=1e-6)
    moved = bars.copy()
    moved.loc[2, "close"] = 200.0            # a later bar must not reach back
    assert liquidity.features(per_minute, moved).amihud_illiquidity.iloc[1] == \
        pytest.approx(table.amihud_illiquidity.iloc[1])
