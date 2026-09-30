from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from out import run_patchtst_excursion_range as runner


def synthetic_bars(rows: int = 1502) -> pd.DataFrame:
    close = 100 + np.arange(rows) * 0.01
    open_ = close - 0.002
    return pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=rows, freq="min", tz="UTC"),
        "open": open_, "high": close + 0.02, "low": open_ - 0.02, "close": close,
        "quote_volume": 1_000.0 + np.arange(rows),
        "number_of_trades": 100 + np.arange(rows),
    })


def test_targets_use_t_plus_1_through_t_plus_15_inclusive() -> None:
    high, low, close = np.full(18, 100.0), np.full(18, 100.0), np.full(18, 100.0)
    high[0], low[0] = 999.0, 1.0       # current bar: excluded
    high[1], high[15], low[15] = 101.0, 120.0, 95.0
    high[16] = 150.0                   # t+16: excluded
    target = runner.excursion_range_targets(high, low, close)
    np.testing.assert_allclose(target[0], [2000.0, 2500.0], atol=1e-4)
    assert np.isnan(target[-15:]).all()


def test_range_is_never_below_excursion() -> None:
    rng = np.random.default_rng(42)
    close = np.full(200, 100.0)
    high = 100 + rng.uniform(0, 5, len(close))
    low = 100 - rng.uniform(0, 5, len(close))
    target = runner.excursion_range_targets(high, low, close)
    known = np.isfinite(target).all(axis=1)
    assert (target[known, 1] >= target[known, 0] - 1e-4).all()


def test_range_span_is_anchored_at_origin_close() -> None:
    close = np.full(17, 100.0)

    high = np.full(17, 110.0)
    low = np.full(17, 105.0)
    np.testing.assert_allclose(
        runner.excursion_range_targets(high, low, close)[0], [1000.0, 1000.0], atol=1e-4)

    high.fill(95.0)
    low.fill(90.0)
    np.testing.assert_allclose(
        runner.excursion_range_targets(high, low, close)[0], [1000.0, 1000.0], atol=1e-4)


def test_two_heads_have_expected_shape_and_unchanged_encoder() -> None:
    model = runner.ExcursionRangePatchTST(len(runner.SEQUENCE_NAMES)).eval()
    assert len(model.encoder.layers) == 2
    assert not hasattr(model, "head")
    with torch.no_grad():
        output = model(torch.randn(3, 60, len(runner.SEQUENCE_NAMES)),
                       torch.randn(3, len(runner.STATIC_NAMES)))
    assert output.shape == (3, 2)
    assert (output >= 0).all()
    assert model.excursion_head is not model.range_head


def test_static_inputs_are_aligned_to_origin_not_future() -> None:
    frame = synthetic_bars()
    _, original, _ = runner.build_primitives(frame)
    origin = 1440
    changed = frame.copy()
    changed.loc[origin + 1, ["high", "quote_volume", "number_of_trades"]] = [1000.0, 1e12, 10**9]
    _, altered, _ = runner.build_primitives(changed)
    np.testing.assert_array_equal(original[origin], altered[origin])
    assert not np.array_equal(original[origin + 1], altered[origin + 1])


def test_no_directional_signed_quantity_reaches_loss() -> None:
    sequence, static, _ = runner.build_primitives(synthetic_bars())
    assert np.nanmin(sequence) >= -1e-5
    assert np.nanmin(static) >= -1e-5
    prediction = torch.tensor([[2.0, 3.0], [4.0, 7.0]])
    target = torch.tensor([[1.0, 3.0], [6.0, 8.0]])
    assert torch.isclose(runner.dual_mae(prediction, target), torch.tensor(1.0))
    with pytest.raises(ValueError, match="unsigned"):
        runner.dual_mae(prediction, torch.tensor([[-1.0, 3.0], [6.0, 8.0]]))
