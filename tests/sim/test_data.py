import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import data, provenance

def test_asof_strictly_earlier_and_ttl():
    times = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:05", "2024-01-01 00:10"], utc=True))
    decisions = pd.DatetimeIndex(pd.to_datetime(["2024-01-01 00:10", "2024-01-01 00:10:00.001", "2024-01-01 01:00"], utc=True, format="ISO8601"))
    out = data.asof(times, np.array([1.0, 2.0]), decisions, ttl=pd.Timedelta(minutes=15))
    assert out[0] == 1.0          # value at 00:10 not usable at exactly 00:10
    assert out[1] == 2.0
    assert np.isnan(out[2])       # 50 minutes old > ttl

def test_predictions_reject_future_retrain(tmp_path):
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:00"], utc=True),
                          "retrain_time": pd.to_datetime(["2024-01-01 00:15"], utc=True),
                          "segment": ["DEV_BACK"]})
    with pytest.raises(ValueError, match="retrain_time after timestamp"):
        data.validate_predictions(frame)

def test_predictions_reject_off_grid():
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01 00:07"], utc=True),
                          "retrain_time": pd.to_datetime(["2024-01-01 00:00"], utc=True),
                          "segment": ["DEV_BACK"]})
    with pytest.raises(ValueError, match="15-minute grid"):
        data.validate_predictions(frame)

def test_minutes_reject_gap():
    t = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:02"], utc=True)
    frame = pd.DataFrame({"open_time": t, "open": 1., "high": 1., "low": 1., "close": 1.,
                          "volume": 1., "quote_volume": 1., "number_of_trades": 1,
                          "taker_buy_base_volume": .5})
    with pytest.raises(ValueError, match="missing minutes"):
        data.validate_minutes(frame)

def test_tree_hash_detects_change(tmp_path):
    (tmp_path / "a.zip").write_bytes(b"x")
    first = provenance.tree_sha256(tmp_path, "*.zip")
    (tmp_path / "a.zip").write_bytes(b"y")
    with pytest.raises(ValueError, match="a.zip|sha256"):
        provenance.verify({"t": first}, {"t": provenance.tree_sha256(tmp_path, "*.zip")})
