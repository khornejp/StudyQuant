"""K06-K24 definitions: hand-built series for the level/threshold logic, real-data invariants for the rest."""
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import indicators
from btcusdt_quant.sim.strategies import CATALOG, Context

T0 = pd.Timestamp("2024-01-01", tz="UTC")


def synthetic(close, open_=None, spread=.5, volume=1.0, taker=.5, start=T0, **frames):
    close = np.asarray(close, float)
    open_ = close if open_ is None else np.asarray(open_, float)
    m = pd.DataFrame({"open_time": pd.date_range(start, periods=len(close), freq="1min", tz="UTC"), "open": open_,
                      "high": np.maximum(open_, close) + spread, "low": np.minimum(open_, close) - spread,
                      "close": close, "volume": volume, "quote_volume": 1.0, "number_of_trades": 1,
                      "taker_buy_base_volume": taker})
    empty = {"metrics": pd.DataFrame(columns=["available_time", "global_ls", "top_ls", "oi", "oi_value", "taker_lsr"]),
             "premium": pd.DataFrame(columns=["available_time", "premium"]),
             "funding": pd.DataFrame(columns=["time", "rate"]),
             "regime": pd.DataFrame(columns=["timestamp", "M", "L"])}
    empty.update(frames)
    return Context(minutes=m, end=m.open_time.iloc[-1] + pd.Timedelta(minutes=1), **empty)


def test_k06_oco_levels_from_range_1h():
    regime = pd.DataFrame({"timestamp": [T0 + pd.Timedelta(hours=1)], "M": [.5], "L": [.5],
                           "prediction_range_1h": [100.0]})
    t = CATALOG["K06_k0.5"].build(synthetic(np.full(180, 100.0), regime=regime))
    row = t.loc[t.decision_time == T0 + pd.Timedelta(hours=1)].iloc[0]
    assert row.entry == "oco" and row.expiry_min == 60 and row.max_hold_min == 240 and row.allow_entry
    assert np.isclose(row.upper, 100 * np.exp(.005)) and np.isclose(row.lower, 100 * np.exp(-.005))
    assert not t.loc[t.decision_time == T0 + pd.Timedelta(hours=2), "allow_entry"].iloc[0]   # no prediction


def test_k07_levels_use_exc_1h():
    regime = pd.DataFrame({"timestamp": [T0 + pd.Timedelta(minutes=15)], "M": [.5], "L": [.5],
                           "prediction_exc_1h": [40.0]})
    row = CATALOG["K07_k1.0"].build(synthetic(np.full(30, 100.0), regime=regime)).iloc[0]
    assert np.isclose(row.upper, 100 * np.exp(.004)) and np.isclose(row.lower, 100 * np.exp(-.004))


def test_k14_range_expiry_and_native_stop():
    close = np.full(8 * 60 + 60, 100.0); close[7 * 60 + 10] = 103.0; close[7 * 60 + 20] = 97.0
    t = CATALOG["K14"].build(synthetic(close, spread=0.0))
    row = t.loc[t.decision_time == T0 + pd.Timedelta(hours=7, minutes=30)].iloc[0]
    assert (row.upper, row.lower, row.expiry_min) == (103.0, 97.0, 210)
    assert np.isclose(row.stop_bps, np.log(103 / 97) * 1e4) and row.max_hold_min == 8 * 60 - 31


def test_k17_streak_exactly_n():
    # 15 m bars: 5 up bars then 1 down bar -> short only at the fifth up bar
    close = np.concatenate([np.linspace(100 + 15 * k, 100 + 15 * k + 14, 15) for k in range(5)] + [np.full(15, 160.0)])
    open_ = np.r_[close[0], close[:-1]]
    t = CATALOG["K17_N5"].build(synthetic(close, open_=open_, spread=0.0))
    assert t.side.tolist() == [0, 0, 0, 0, -1, 0]


def test_k18_uses_only_prior_settlements():
    times = pd.date_range(T0, periods=272, freq="8h", tz="UTC")
    rate = np.r_[np.linspace(-1e-4, 1e-4, 270), 5e-4, 0.0]
    t = CATALOG["K18"].build(synthetic(np.full(10, 100.0), funding=pd.DataFrame({"time": times, "rate": rate})))
    assert t.side.iloc[270] == -1 and t.decision_time.iloc[270] == times[270] + pd.Timedelta(minutes=15)
    assert t.side.iloc[271] == 0          # mid-range rate: neither tail


def test_k22_cvd_divergence_short():
    # rising closes with heavy taker buying, then a marginal new high on heavy selling
    n = 22 * 15
    close = np.linspace(100, 110, n); close[-15:] = 110.5
    taker = np.where(np.arange(n) < n - 15, 1.0, 0.0)
    t = CATALOG["K22"].build(synthetic(close, spread=0.0, volume=1.0, taker=taker))
    assert t.side.iloc[-1] == -1


@pytest.fixture(scope="module")
def ctx():
    return Context.load(start=pd.Timestamp("2022-10-01", tz="UTC"), end=pd.Timestamp("2023-04-01", tz="UTC"))


def test_k08_release_after_six_squeeze_bars(ctx):
    b = ctx.bars(15)
    bb, kc = indicators.bollinger(b.close, 20, 2.0), indicators.keltner(b, 20, 1.5)
    inside = ((bb.upper < kc.upper) & (bb.lower > kc.lower)).to_numpy()
    t = CATALOG["K08"].build(ctx)
    hits = np.flatnonzero(t.side.to_numpy() != 0)
    assert len(hits) > 0
    for i in hits:
        assert not inside[i] and inside[i - 6:i].all()
        assert t.side.iloc[i] == np.sign(b.close.iloc[i] - bb.middle.iloc[i])


def test_k09_requires_band_and_rsi(ctx):
    b = ctx.bars(15)
    bb, r = indicators.bollinger(b.close, 20, 2.0), indicators.rsi(b.close, 14)
    t = CATALOG["K09"].build(ctx)
    longs, shorts = t.side.to_numpy() == 1, t.side.to_numpy() == -1
    assert longs.any() and shorts.any()
    assert ((b.close < bb.lower) & (r < 30))[longs].all() and ((b.close > bb.upper) & (r > 70))[shorts].all()


@pytest.mark.parametrize("spec_id,minutes", [("K11_15m", 15), ("K11_1h", 60)])
def test_k11_signal_only_on_cross_bar(ctx, spec_id, minutes):
    b = ctx.bars(minutes)
    diff = (indicators.ema(b.close, 9) - indicators.ema(b.close, 21)).to_numpy()
    t = CATALOG[spec_id].build(ctx)
    for i in np.flatnonzero(t.side.to_numpy() != 0):
        assert np.sign(diff[i]) == t.side.iloc[i] and np.sign(diff[i - 1]) != t.side.iloc[i]


def test_k13_exit_when_any_timeframe_disagrees(ctx):
    t = CATALOG["K13"].build(ctx)
    assert (t.exit_long[t.side == 1] == False).all() and (t.exit_short[t.side == -1] == False).all()  # noqa: E712
    assert (t.exit_long & t.exit_short).sum() > 0


def test_futures_signals_present(ctx):
    for spec_id in ("K15", "K16", "K19", "K20_A", "K20_B", "K21_A", "K21_B", "K23", "K24"):
        t = CATALOG[spec_id].build(ctx)
        assert (t.side != 0).sum() > 0, spec_id
    a, b = CATALOG["K21_A"].build(ctx), CATALOG["K21_B"].build(ctx)
    assert (a.side == -b.side).all()
