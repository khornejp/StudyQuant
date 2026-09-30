"""No-fit contracts for the unsigned PatchTST volatility run."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from out import run_patchtst_volatility as run


def test_target_is_absolute_t_plus_15_and_tail_is_unknown():
    close = np.full(32, 100.0)
    close[15] = 99.0
    close[16] = 102.0
    target = run.magnitude_target(close)
    assert target[0] == pytest.approx(100.0)
    assert target[1] == pytest.approx(200.0)
    assert (target[:-15] >= 0).all()
    assert np.isnan(target[-15:]).all()


def test_t_plus_15_must_close_inside_block():
    size = 120
    times = pd.date_range("2026-01-01", periods=size, freq="min", tz="UTC")
    data = run.Prepared(
        times,
        np.ones((size, len(run.SEQUENCE_NAMES)), np.float32),
        np.ones((size, len(run.STATIC_NAMES)), np.float32),
        np.ones(size, np.float32),
        np.ones(size, np.float32),
        np.ones(size, bool),
    )
    indices = run.block_indices(data, "2026-01-01 00:00", "2026-01-01 01:00")
    assert indices.tolist() == [0, 15, 30]
    assert times[indices[-1] + 15] + pd.Timedelta(minutes=1) <= times[60]
    assert 45 not in indices


def test_regression_head_shape_nonnegative_and_two_layers():
    torch.manual_seed(42)
    model = run.VolatilityPatchTST().eval()
    assert len(model.encoder.layers) == 2
    with torch.no_grad():
        output = model(
            torch.randn(3, run.LOOKBACK, len(run.SEQUENCE_NAMES)),
            torch.randn(3, len(run.STATIC_NAMES)),
        )
    assert output.shape == (3,)
    assert torch.isfinite(output).all()
    assert (output >= 0).all()


def test_static_context_is_aligned_to_sequence_origin():
    sequence = np.arange(100 * 2, dtype=np.float32).reshape(100, 2)
    static = np.arange(100 * 3, dtype=np.float32).reshape(100, 3)
    indices = np.array([59, 80])
    seq, context = run.model_inputs(
        sequence,
        static,
        indices,
        np.zeros(2, np.float32),
        np.full(2, 100.0, np.float32),
        np.zeros(3, np.float32),
        np.full(3, 100.0, np.float32),
    )
    np.testing.assert_array_equal(seq[:, -1], sequence[indices] / 100.0)
    np.testing.assert_array_equal(context, static[indices] / 100.0)
    assert seq.shape == (2, 60, 2)


def test_no_signed_quantity_can_reach_loss():
    assert run.magnitude_mae(torch.tensor([1.0]), torch.tensor([2.0])).item() == pytest.approx(1.0)
    with pytest.raises(ValueError, match="signed quantity"):
        run.magnitude_mae(torch.tensor([-1.0]), torch.tensor([2.0]))
    with pytest.raises(ValueError, match="signed quantity"):
        run.magnitude_mae(torch.tensor([1.0]), torch.tensor([-2.0]))


def test_preregistered_scale_and_safety_contract():
    assert run.FOLDS == tuple(range(406, 606))
    assert run.SEEDS == (42, 43, 44)
    assert len(run.FOLDS) * len(run.SEEDS) == 600
    assert run.RSS_LIMIT_GIB == 3.0
    source = run.Path(run.__file__).read_text(encoding="utf-8")
    assert "new_backtests\": 0" in source
    assert "new_orders\": 0" in source
    assert "_archive_pre_meta_2026-09-24" not in source.split("forbidden_checkpoint_root")[0]


def test_decile_report_has_calibration_and_ratio():
    realised = np.arange(1, 101, dtype=float)
    table = run.decile_table(realised, realised)
    assert [row["decile"] for row in table["rows"]] == list(range(1, 11))
    assert sum(row["n"] for row in table["rows"]) == 100
    assert table["top_bottom_realised_ratio"] > 1
