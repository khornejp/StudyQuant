"""Signal store helpers: token state (hold / exit flags / age), markout maturity and EWMA, research timeline as-of."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import signal_store as SG

M = SG.MIN_NS


def test_token_state_hold_exit_age():
    clk = np.arange(0, 100 * M, 5 * M, dtype=np.int64)
    ev_t = np.array([10 * M, 50 * M]); ev_s = np.array([1, -1], np.int8); ev_e = np.array([5.0, 7.0])
    st = SG.token_state(clk, ev_t, ev_s, ev_e, np.zeros(0, np.int64), np.array([70 * M]), hold_min=30)
    side = dict(zip(clk // M, st["side"]))
    assert side[5] == 0 and side[10] == 1 and side[35] == 1 and side[40] == 0      # hold 30 m
    assert side[50] == -1 and side[65] == -1 and side[70] == 0                    # short ended by exit flag
    assert st["age_min"][clk // M == 20][0] == 10 and st["strength"][clk // M == 55][0] == 7.0
    st0 = SG.token_state(clk, ev_t, ev_s, ev_e, np.zeros(0, np.int64), np.zeros(0, np.int64), hold_min=0)
    assert st0["side"][clk // M == 45][0] == 1                                  # hold 0: until the next event


def test_markout_matured_only_and_ewma():
    n = 2000
    side = np.zeros(n, np.int8); side[100:] = 1
    C = 100 * np.exp(np.cumsum(np.full(n, 1e-4)))
    mk = SG.markouts(side, C)
    lag = 60 // 5
    assert np.isnan(mk["mk60_mean"][:100 + lag]).all()                          # no markout before maturity
    want = (C[100 + lag] / C[100] - 1) * 1e4 - 4
    assert np.isclose(mk["mk60_mean"][100 + lag], want, atol=1e-4) and mk["mk60_hit"][100 + lag] == 1.0
    assert mk["mk60_count"][-1] > mk["mk60_count"][500] > 0


def test_timeline_asof():
    tl = pd.DataFrame({"minute_time": [0, 10 * M], "available_time": [M, 11 * M], "available": [True, True],
                       "base_side": [1, 0], "base_weight": [0.5, 0.0], "signal_active": [True, False]})
    clk = np.arange(0, 20 * M, 5 * M, dtype=np.int64)
    st = SG.timeline_state(clk, tl)
    assert st["side"].tolist() == [0, 1, 1, 0] and st["strength"][1] == 0.5 and st["available"].tolist() == [0, 1, 1, 1]
