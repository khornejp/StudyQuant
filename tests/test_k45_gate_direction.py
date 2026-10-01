import numpy as np
import pandas as pd
import pytest

from out import k45_gate_direction as gd


def test_label_45_thresholds_are_strict():
    close = np.full(200, 100.0)
    close[45] = 100.0399
    close[46] = 100.0401
    close[47] = 99.9599
    r, cls = gd.label_45(close, np.array([0, 1, 2]))
    assert cls.tolist() == [1, 2, 0]
    assert r[0] == pytest.approx(3.99)


def test_label_45_refuses_out_of_range():
    with pytest.raises(IndexError):
        gd.label_45(np.ones(50), np.array([10]))


def test_microstructure_join_is_exact_time_only():
    bars = pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    })
    micro = pd.DataFrame({"open_time": bars.open_time.iloc[[0, 2]], "x": [1.0, 3.0]})
    from out import run_k45_gate_direction_dataset as ds

    got = ds.join_exact(bars.iloc[[1]], micro, prefix="m_")
    assert np.isnan(got["m_x"].iloc[0])
