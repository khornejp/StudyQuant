import math
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim.reference import SimConfig
from btcusdt_quant.sim.strategies import grid
from tests.sim.test_strategies_catalog import T0, synthetic

CFG = SimConfig(include_funding=False)
G = 100.0          # step bps = 0.5 x predicted range_1h of 200; first grid: decision 00:15, live from 00:16


def ctx_for(close, predicted_hours=1):
    times = pd.date_range(T0, periods=4 * predicted_hours, freq="15min", tz="UTC")
    regime = pd.DataFrame({"timestamp": times, "M": .1, "L": .1, "prediction_range_1h": 2 * G})
    return synthetic(close, spread=0.0, regime=regime)        # open = close per minute, so fills happen at opens


def path(*segments, n=6 * 60):
    close = np.full(n, 100.0)
    for minute, value in segments:
        close[minute:] = value
    return close


def run(ctx):
    return grid.simulate_grid(ctx, T0, T0 + pd.Timedelta(days=2), gated=False, config=CFG)


def test_grid_fills_and_takes_one_step():
    t = run(ctx_for(path((20, 99.0), (30, 100.0)))).trades       # buy level 99.005 fills at 99; take 99.995
    first = t.iloc[0]
    assert (first.side, first.exit_reason, first.entry_price, first.exit_price) == (1, "take", 99.0, 100.0)
    assert np.isclose(first.units, 1 / 3) and np.isclose(first.gross_bps, math.log(100 / 99) * 1e4 / 3)
    assert np.isclose(first.fee_bps, 4 / 3)


def test_grid_stop_closes_all():
    t = run(ctx_for(path((20, 99.0), (21, 98.0), (22, 97.0), (23, 96.5), (24, 95.9)))).trades
    stops = t.loc[t.exit_reason == "stop"]
    assert len(stops) == 3 and (stops.exit_price == 95.9).all()   # below 100 * exp(-0.04) = 96.08, gap at open


def test_grid_window_end_closes_at_open():
    t = run(ctx_for(path((20, 99.0)))).trades
    assert t.exit_reason.tolist() == ["max_hold"] and t.exit_time.iloc[0] == T0 + pd.Timedelta(minutes=16 + 240)


@pytest.mark.parametrize("seed", range(5))
def test_grid_ledger_identity_random(seed):
    rng = np.random.default_rng(seed)
    r = run(ctx_for(100 * np.exp(np.cumsum(rng.normal(0, 2e-3, 6 * 60)))))
    assert len(r.trades) > 0 and np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum(), atol=1e-9)
