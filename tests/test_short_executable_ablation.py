import numpy as np
import pandas as pd

from btcusdt_quant.short_executable_ablation import FEATURE_SETS, next_open_short_return


def test_next_open_target_uses_executable_entry_and_exact_horizon_close() -> None:
    frame = pd.DataFrame({
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "close": [99.0, 100.0, 98.0, 105.0, 100.0],
    })
    gross = next_open_short_return(frame, horizon=2)
    np.testing.assert_allclose(gross[:3], [1.0 - 98.0 / 101.0, 1.0 - 105.0 / 102.0, 1.0 - 100.0 / 103.0])
    assert np.isnan(gross[3:]).all()
    changed = frame.copy()
    changed.loc[0, "close"] = 1_000_000.0
    assert next_open_short_return(changed, horizon=2)[0] == gross[0]


def test_next_open_target_rejects_invalid_horizon() -> None:
    frame = pd.DataFrame({"open": [100.0], "close": [100.0]})
    try:
        next_open_short_return(frame, horizon=0)
    except ValueError as error:
        assert str(error) == "horizon must be positive"
    else:
        raise AssertionError("invalid horizon accepted")


def test_feature_ablation_sets_are_exact_and_nested() -> None:
    assert {name: len(features) for name, features in FEATURE_SETS.items()} == {
        "direction_10": 10,
        "funding_6": 6,
        "direction_funding_16": 16,
        "all_47": 47,
    }
    assert set(FEATURE_SETS["direction_10"]).isdisjoint(FEATURE_SETS["funding_6"])
    assert set(FEATURE_SETS["direction_funding_16"]) == (
        set(FEATURE_SETS["direction_10"]) | set(FEATURE_SETS["funding_6"])
    )
