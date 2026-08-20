from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from btcusdt_quant import data, dataset, features


def _candles(count: int = 48) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 1, 0, 0)
    return [
        data.Candle(
            open_time=base + timedelta(minutes=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=10.0,
            quote_volume=1000.0,
            number_of_trades=100,
            taker_buy_base_volume=5.0,
            taker_buy_quote_volume=500.0,
        )
        for index in range(count)
    ]


class StatusDictionarySharingTests(unittest.TestCase):
    def test_build_and_label_rows_share_identical_status_dictionaries(self) -> None:
        original = features.FeatureClipper.clip_values_only

        def no_nan_statuses(clipper: features.FeatureClipper, values: object):
            return {name: 0.0 if value is None else value for name, value in original(clipper, values).items()}  # type: ignore[arg-type]

        with mock.patch.object(features.FeatureClipper, "clip_values_only", no_nan_statuses):
            rows = dataset.build_feature_rows(_candles(), _parallel=False)

        self.assertGreater(len(rows), 1)
        self.assertEqual(len({id(row.source_availability_status) for row in rows}), 1)
        self.assertEqual(len({id(row.feature_availability_status) for row in rows}), 1)

        labeled = dataset.attach_labels(rows, _candles(), horizon=1, label_threshold=0.0, include_warmup=True)
        self.assertTrue(labeled)
        self.assertIs(labeled[0].source_availability_status, rows[0].source_availability_status)
        self.assertIs(labeled[0].feature_availability_status, rows[0].feature_availability_status)

    def test_different_nan_statuses_are_not_merged(self) -> None:
        original = features.FeatureClipper.clip_values_only
        call_index = 0

        def alternating_nan_statuses(clipper: features.FeatureClipper, values: object):
            nonlocal call_index
            clipped = {name: 0.0 if value is None else value for name, value in original(clipper, values).items()}  # type: ignore[arg-type]
            if call_index % 2 == 0:
                clipped["return_1"] = None
            call_index += 1
            return clipped

        with mock.patch.object(features.FeatureClipper, "clip_values_only", alternating_nan_statuses):
            rows = dataset.build_feature_rows(_candles(), _parallel=False)

        self.assertEqual(len({id(row.source_availability_status) for row in rows}), 1)
        status_ids_by_content: dict[tuple[tuple[str, str], ...], set[int]] = {}
        for row in rows:
            content = tuple(sorted(row.feature_availability_status.items()))
            status_ids_by_content.setdefault(content, set()).add(id(row.feature_availability_status))
        # Warmup status can create another legitimate content, but every
        # content must still have precisely one shared dictionary object.
        self.assertGreater(len(status_ids_by_content), 1)
        self.assertTrue(all(len(ids) == 1 for ids in status_ids_by_content.values()))
        self.assertGreater(len({id(row.feature_availability_status) for row in rows}), 1)

    def test_parquet_load_interns_status_dictionaries(self) -> None:
        source_status = {"metrics": "A"}
        feature_status = {"return_1": "A"}
        rows = [
            dataset.FeatureRow(index, candle.open_time, {"return_1": 0.0}, 0, False, False, source_status, feature_status)
            for index, candle in enumerate(_candles(3))
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rows.parquet"
            dataset._write_rows_parquet(path, rows, ("return_1",), labeled=False)
            loaded = dataset._load_feature_rows_parquet(
                path, stored_feature_names=("return_1",), expected_feature_names=None, allow_missing_features=False
            )
        self.assertEqual(len({id(row.source_availability_status) for row in loaded}), 1)
        self.assertEqual(len({id(row.feature_availability_status) for row in loaded}), 1)
