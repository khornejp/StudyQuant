from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq

from out import run_k45_hold_a_data_r2_26 as runner


def test_output_feature_columns_and_dtypes_match_reference() -> None:
    actual = pq.ParquetFile(runner.ARTIFACT / "features_2026q3.parquet").schema_arrow
    expected = pq.ParquetFile(runner.REFERENCE_FEATURES).schema_arrow
    assert actual.equals(expected)


def test_output_excludes_pre_hold_a_rows() -> None:
    times = pd.read_parquet(runner.ARTIFACT / "features_2026q3.parquet", columns=["open_time"])
    assert len(times) == runner.EXPECTED_MINUTES
    assert times.open_time.min() == runner.HOLD_START
    assert times.open_time.max() == runner.HOLD_END


def test_funding_has_276_settlements() -> None:
    funding = pd.read_parquet(runner.ARTIFACT / "funding_2026q3.parquet")
    assert len(funding) == runner.EXPECTED_SETTLEMENTS == 276
    assert funding.funding_time.nunique() == 276


def test_parity_comparison_detects_intentional_change() -> None:
    expected = pd.DataFrame({"integer": pd.Series([1, 2], dtype="int64"), "floating": [1.0, 2.0]})
    changed = expected.copy()
    changed.loc[1, "floating"] += 2e-9
    result = runner.compare_frames(changed, expected)
    assert result.set_index("column").loc["floating", "mismatch_rows"] == 1
