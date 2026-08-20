from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from btcusdt_quant import data, dataset


def _alternating_candles(count: int = 16) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 1, 0, 0)
    closes = [100.0 if index % 2 == 0 else 102.0 for index in range(count)]
    return [
        data.Candle(
            open_time=base + timedelta(minutes=index),
            open=closes[index - 1] if index else closes[index],
            high=closes[index] * 1.001,
            low=closes[index] * 0.999,
            close=closes[index],
            volume=10.0,
            quote_volume=1000.0,
            number_of_trades=100,
            taker_buy_base_volume=5.0,
            taker_buy_quote_volume=500.0,
        )
        for index in range(count)
    ]


def _feature_rows(candles: list[data.Candle]) -> list[dataset.FeatureRow]:
    return [
        dataset.FeatureRow(index, candle.open_time, {"return_1": 0.0}, 0, False, False)
        for index, candle in enumerate(candles)
    ]


def _assert_shared_by_content(test: unittest.TestCase, rows: list[dataset.LabeledRow], attribute: str) -> None:
    ids_by_content: dict[tuple[tuple[str, object], ...], set[int]] = {}
    for row in rows:
        value = getattr(row, attribute)
        ids_by_content.setdefault(tuple(sorted(value.items())), set()).add(id(value))
    test.assertGreater(len(ids_by_content), 1)
    test.assertTrue(all(len(ids) == 1 for ids in ids_by_content.values()))
    test.assertEqual(len({id(getattr(row, attribute)) for row in rows}), len(ids_by_content))


class LabelDictionarySharingTests(unittest.TestCase):
    def test_attach_labels_shares_targets_and_reasons_by_content(self) -> None:
        candles = _alternating_candles()
        rows = dataset.attach_labels(_feature_rows(candles), candles, horizon=1, label_threshold=0.0, include_warmup=True)

        self.assertGreater(len(rows), 2)
        _assert_shared_by_content(self, rows, "targets")
        _assert_shared_by_content(self, rows, "target_reasons")
        self.assertIsNot(rows[0].targets, rows[1].targets)
        self.assertIsNot(rows[0].target_reasons, rows[1].target_reasons)

    def test_parquet_load_interns_targets_and_target_reasons(self) -> None:
        candles = _alternating_candles()
        rows = dataset.attach_labels(_feature_rows(candles), candles, horizon=1, label_threshold=0.0, include_warmup=True)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "labeled.parquet"
            dataset._write_rows_parquet(path, rows, ("return_1",), labeled=True)
            loaded = dataset._load_labeled_rows_parquet(
                path, stored_feature_names=("return_1",), expected_feature_names=None, allow_missing_features=False
            )

        _assert_shared_by_content(self, loaded, "targets")
        _assert_shared_by_content(self, loaded, "target_reasons")
