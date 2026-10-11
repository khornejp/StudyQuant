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
