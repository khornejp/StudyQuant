"""U35 universe / family map / DEV funding snap."""
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import u35


def test_universe_and_families():
    assert len(u35.UNIVERSE) == 35 and len(set(u35.UNIVERSE)) == 35 and len(u35.AX_NEW) == 28
    assert u35.UNIVERSE[:32] == u35.PAPER_BOOKS and set(u35.EXISTING7) <= set(u35.UNIVERSE)
    assert set(u35.FAMILY.values()) == set(u35.FAMILIES)
    for b in u35.AX_NEW:                                     # AX families follow the research catalog Spec.family
        assert u35.FAMILY[b] == u35.catalog_family(b)


def test_scheduled_funding_snap():
    t = pd.to_datetime(["2024-01-01T08:00:00.007Z", "2024-01-01T15:59:59.5Z"], utc=True)
    f = u35.scheduled(pd.DataFrame({"time": t, "rate": [1e-4, -2e-4]}))
    assert f.time.dt.hour.tolist() == [8, 16] and np.allclose(f.rate, [1e-4, -2e-4])
    with pytest.raises(ValueError):
        u35.scheduled(pd.DataFrame({"time": pd.to_datetime(["2024-01-01T08:02:00Z"], utc=True), "rate": [0.0]}))


def test_settlement_grid_fail_closed_and_guard():
    from btcusdt_quant.sim import costs
    from btcusdt_quant.rl.sleeve_precompute import TestAccessError
    ok = pd.DataFrame({"time": pd.to_datetime(["2024-01-01T00:00Z", "2024-01-01T08:00Z", "2024-01-01T16:00Z"], utc=True),
                       "rate": [1e-4, -2e-4, 3e-4]})
    u35.assert_settlement_grid(ok)
    off = ok.copy()
    off.loc[1, "time"] = pd.Timestamp("2024-01-01T08:00:00.007Z")
    with pytest.raises(ValueError):
        u35.assert_settlement_grid(off)                          # off-grid (ms) refused
    with pytest.raises(ValueError):
        u35.assert_settlement_grid(pd.concat([ok, ok.iloc[[1]]]).sort_values("time"))   # duplicate refused
    with pytest.raises(TestAccessError):
        u35.assert_settlement_grid(pd.DataFrame({"time": pd.to_datetime(["2026-01-01T00:00Z"], utc=True), "rate": [0.0]}))
    with u35.no_full_settlements():
        with pytest.raises(TestAccessError):
            costs._settlement_arrays()                           # full folder never opened
        with u35.dev_settlements(ok):
            ft, fr = costs._settlement_arrays()
            assert len(ft) == 3
            # action-mode open position: settlements up to the data end + 1 ns, PESS, DEV table only
            ev = costs.funding_events(1, pd.Timestamp("2023-12-31T23:00Z"), pd.Timestamp("2024-01-01T16:00Z")
                                      + pd.Timedelta(1, "ns"), "PESS")
            assert np.allclose([v for _, v in ev], [-1.0, 2.0, -3.0])
        with pytest.raises(TestAccessError):
            costs._settlement_arrays()
