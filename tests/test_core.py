from __future__ import annotations

import csv
import io
import importlib.util
import json
import threading
import tempfile
import unittest
import urllib.error
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Mapping, cast
from unittest import mock
import warnings

import btcusdt_quant.dataset as dataset
from btcusdt_quant import data, features, governance, live, training
from btcusdt_quant.cli import main, run_collect, run_demo, run_live, run_train


def make_stream_candles(rows: int) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 2, 0, 0)
    candles: list[data.Candle] = []
    previous_close = 100000.0
    for index in range(rows):
        open_price = previous_close
        close = 100000.0 + index * 10.0
        candles.append(
            data.Candle(
                open_time=base.replace(minute=index),
                open=open_price,
                high=max(open_price, close) + 5.0,
                low=min(open_price, close) - 5.0,
                close=close,
                volume=10.0 + index,
                quote_volume=(10.0 + index) * close,
                number_of_trades=100 + index,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=5.0 * close,
            )
        )
        previous_close = close
    return candles


def make_archive_csv(day: str = "2024-01-01", rows: int = 3, header: str | None = None) -> str:
    fields = header or ",".join(dataset.ARCHIVE_CSV_FIELDS)
    lines = [fields]
    base = dataset.parse_open_time(f"{day}T00:00:00+00:00")
    for index in range(rows):
        open_time = int((base + timedelta(minutes=index)).timestamp() * 1000)
        close_time = open_time + 59_999
        price = 100000.0 + index
        values = {
            "open_time": open_time,
            "open": price,
            "high": price + 2.0,
            "low": price - 2.0,
            "close": price + 1.0,
            "volume": 10.0 + index,
            "close_time": close_time,
            "quote_volume": (10.0 + index) * price,
            "count": 100 + index,
            "taker_buy_volume": 5.0,
            "taker_buy_quote_volume": 5.0 * price,
            "ignore": 0,
        }
        lines.append(",".join(str(values[name]) for name in fields.split(",")))
    return "\n".join(lines) + "\n"


def make_archive_zip(csv_text: str, name: str = "BTCUSDT-1m.csv") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, csv_text)
    return buffer.getvalue()


class FakeArchiveResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeArchiveResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class DataPipelineTests(unittest.TestCase):
    def label_for_path(self, path: list[tuple[float, float, float, float, int]]) -> dataset.LabeledRow:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base.replace(minute=index),
                open=values[0],
                high=values[1],
                low=values[2],
                close=values[3],
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
                gap_flag=values[4],
                repaired=bool(values[4]),
            )
            for index, values in enumerate(path)
        ]
        feature_row = dataset.FeatureRow(0, candles[0].open_time, {}, candles[0].gap_flag, candles[0].repaired, False)
        labeled = dataset.attach_labels([feature_row], candles, horizon=3, label_threshold=0.0002)
        self.assertEqual(len(labeled), 1)
        return labeled[0]

    def test_canonical_timeline_repairs_gaps(self) -> None:
        candles = data.CanonicalTimelineBuilder().build(data.local_fixture())
        self.assertEqual(len(candles), 8)
        self.assertEqual(sum(candle.gap_flag for candle in candles), 2)
        self.assertEqual(candles[3].gap_length, 1)
        self.assertEqual(candles[4].gap_length, 2)
        self.assertEqual(data.max_gap_run([candle.gap_flag for candle in candles], 120), 2)

    def test_gap_policy_allows_low_live_gap_ratio(self) -> None:
        decision = data.GapContaminationGovernance().decide("volume_trade_flow_features", 0.03, 1, live=True)
        self.assertEqual(decision.action, "allow")

    def test_live_gap_policy_warning_zone_is_reachable_for_all_groups(self) -> None:
        policy = data.GapContaminationGovernance()
        for group in ("volume_trade_flow_features", "volatility_features", "price_return_features"):
            self.assertEqual(policy.decide(group, 0.05, 1, live=True).action, "allow")
            self.assertEqual(policy.decide(group, 0.15, 1, live=True).action, "warn")
            self.assertEqual(policy.decide(group, 0.25, 1, live=True).action, "block_new_entries")

    def test_offline_fixture_dataset_builds_features_and_labels(self) -> None:
        build = dataset.build_dataset()
        self.assertEqual(build.source, "offline_expanded_fixture")
        self.assertGreater(build.gap_report.repaired_rows, 0)
        self.assertGreater(len(build.labeled_rows), 100)
        self.assertEqual(set(build.feature_names), set(dataset.FEATURE_NAMES))
        self.assertTrue({row.label for row in build.labeled_rows}.issubset({0, 1}))
        self.assertTrue({row.label_reason for row in build.labeled_rows}.issubset(set(dataset.LABEL_REASON_BUCKETS)))
        self.assertGreater(sum(row.label for row in build.labeled_rows), 0)

    def test_feature_registry_expanded(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        self.assertGreaterEqual(len(registry_features), 30)
        self.assertGreaterEqual(len(dataset.FEATURE_NAMES), 30)

    def test_feature_registry_has_categories(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        categories = {feature["category"] for feature in registry_features}
        self.assertEqual(categories, {f"F{index:02d}" for index in range(1, 16)})

    def test_feature_registry_all_features_active(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        pending_features = [feature for feature in registry_features if feature.get("scaffold_status") == "pending_data_source"]
        # F11/F12 are now active — no pending features should remain
        self.assertFalse(pending_features, "all features should be active; no pending_data_source features")
        active_names = set(dataset.FEATURE_NAMES)
        all_names = {feature["feature_name"] for feature in registry_features}
        self.assertEqual(active_names, all_names, "FEATURE_NAMES must include all registered features")
        self.assertTrue({"spread", "bid_ask_imbalance", "adl_indicator", "funding_rate"}.issubset(active_names), "F11/F12 features must be active")

    def test_warmup_invalid_derived_from_feature_registry(self) -> None:
        original_formulas = dataset.FEATURE_FORMULAS
        try:
            dataset.FEATURE_FORMULAS = (
                {"feature_name": "synthetic_feature", "formula": "test", "lookback": 5, "min_samples": 5, "warmup_rule": "strict"},
            )
            base = data.utc_minute(2026, 1, 1, 0, 0)
            candles = [
                data.Candle(
                    open_time=base.replace(minute=index),
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
                for index in range(6)
            ]
            rows = dataset.build_feature_rows(candles)
            self.assertEqual([row.warmup_invalid for row in rows], [True, True, True, True, False, False])
            labeled = dataset.attach_labels(rows, candles, horizon=1, label_threshold=0.0)
            self.assertEqual([row.index for row in labeled], [4])
            self.assertFalse(labeled[0].warmup_invalid)
        finally:
            dataset.FEATURE_FORMULAS = original_formulas

    def test_triple_barrier_tp_first(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.11, 99.98, 100.08, 0),
                (100.08, 100.08, 100.0, 100.04, 0),
                (100.04, 100.05, 100.0, 100.04, 0),
            ]
        )
        self.assertEqual(row.label, 1)
        self.assertEqual(row.label_reason, "tp_first")

    def test_triple_barrier_sl_first(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.04, 99.94, 99.96, 0),
                (99.96, 100.0, 99.96, 99.98, 0),
                (99.98, 100.0, 99.97, 99.98, 0),
            ]
        )
        self.assertEqual(row.label, 0)
        self.assertEqual(row.label_reason, "sl_first")

    def test_triple_barrier_timeout(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.04, 99.98, 100.01, 0),
                (100.01, 100.04, 99.98, 100.02, 0),
                (100.02, 100.04, 99.98, 100.01, 0),
            ]
        )
        self.assertEqual(row.label, 0)
        self.assertEqual(row.label_reason, "timeout_no_tp")

    def test_triple_barrier_same_bar_bullish(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.11, 99.94, 100.04, 0),
                (100.04, 100.04, 100.0, 100.02, 0),
                (100.02, 100.04, 100.0, 100.02, 0),
            ]
        )
        self.assertEqual(row.label, 1)
        self.assertEqual(row.label_reason, "tp_first")

    def test_triple_barrier_same_bar_bearish(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.11, 99.94, 99.96, 0),
                (99.96, 100.0, 99.96, 99.98, 0),
                (99.98, 100.0, 99.97, 99.98, 0),
            ]
        )
        self.assertEqual(row.label, 0)
        self.assertEqual(row.label_reason, "sl_first")

    def test_triple_barrier_ambiguous(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.11, 99.94, 100.0, 0),
                (100.0, 100.04, 99.98, 100.01, 0),
                (100.01, 100.04, 99.98, 100.01, 0),
            ]
        )
        self.assertEqual(row.label, 0)
        self.assertEqual(row.label_reason, "ambiguous_path")

    def test_triple_barrier_gap_cross_timeout(self) -> None:
        row = self.label_for_path(
            [
                (100.0, 100.0, 100.0, 100.0, 0),
                (100.0, 100.04, 99.98, 100.0, 1),
                (100.0, 100.04, 99.98, 100.01, 0),
                (100.01, 100.04, 99.98, 100.01, 0),
            ]
        )
        self.assertEqual(row.label, 0)
        self.assertEqual(row.label_reason, "gap_cross_timeout")

    def test_local_csv_dataset_builds_canonical_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            lines = ["open_time,open,high,low,close,volume,quote_volume,number_of_trades"]
            base = data.utc_minute(2026, 1, 1, 0, 0)
            for index in range(18):
                if index == 4:
                    continue
                price = 100000.0 + index * 20.0
                lines.append(f"{(base.replace(minute=index)).isoformat()},{price},{price + 5.0},{price - 5.0},{price + 2.0},10.0,{price * 10.0},100")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            build = dataset.build_dataset(path, horizon=5)
            self.assertEqual(build.raw_rows, 17)
            self.assertEqual(build.gap_report.repaired_rows, 1)
            self.assertGreater(len(build.labeled_rows), 0)

    def test_collect_writes_offline_fixture_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "collected.csv"
            summary = run_collect(output, rows=32)
            self.assertFalse(summary["network_used"])
            self.assertEqual(summary["rows"], 32)
            self.assertTrue(output.exists())
            loaded = dataset.load_csv_candles(output)
            self.assertEqual(len(loaded), 32)

    def test_public_downloader_requires_explicit_network_opt_in(self) -> None:
        downloader = dataset.PublicKlineDownloader()
        with self.assertRaises(RuntimeError):
            downloader.fetch_klines(limit=1)

    def test_collect_rejects_non_positive_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_collect(Path(tmp) / "invalid.csv", rows=0)


class ArchiveDownloaderTests(unittest.TestCase):
    def test_archive_downloader_downloads_single_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_archive_zip(make_archive_csv(rows=2))
            urlopen = mock.Mock(return_value=FakeArchiveResponse(payload))
            downloader = dataset.BinanceArchiveDownloader(urlopen=urlopen, sleep=lambda _: None)
            summary = downloader.download_range("2024-01-01", "2024-01-01", Path(tmp), Path(tmp) / "checkpoint.json")
            self.assertEqual(summary.downloaded_days, 1)
            self.assertEqual(summary.failed_days, 0)
            self.assertTrue((Path(tmp) / "BTCUSDT-1m-2024-01-01.zip").exists())
            self.assertTrue((Path(tmp) / "BTCUSDT-1m-2024-01-01.csv").exists())
            self.assertEqual(len(dataset.load_archive_candles(Path(tmp))), 2)

    def test_archive_downloader_resumes_from_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"last_completed_date": "2024-01-01", "downloaded_files": ["BTCUSDT-1m-2024-01-01.zip"], "failed_dates": []}),
                encoding="utf-8",
            )
            payload = make_archive_zip(make_archive_csv(day="2024-01-02", rows=1))
            urlopen = mock.Mock(return_value=FakeArchiveResponse(payload))
            downloader = dataset.BinanceArchiveDownloader(urlopen=urlopen, sleep=lambda _: None)
            summary = downloader.download_range("2024-01-01", "2024-01-02", Path(tmp), checkpoint)
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(summary.last_completed_date, "2024-01-02")
            self.assertIn("BTCUSDT-1m-2024-01-02.zip", summary.downloaded_files)

    def test_archive_downloader_retry_on_429(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            http_429 = urllib.error.HTTPError("https://example.test/archive.zip", 429, "rate limited", {}, None)
            payload = make_archive_zip(make_archive_csv(rows=1))
            urlopen = mock.Mock(side_effect=[http_429, FakeArchiveResponse(payload)])
            sleep = mock.Mock()
            downloader = dataset.BinanceArchiveDownloader(urlopen=urlopen, sleep=sleep)
            summary = downloader.download_range("2024-01-01", "2024-01-01", Path(tmp), Path(tmp) / "checkpoint.json")
            self.assertEqual(summary.downloaded_days, 1)
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(1.0)

    def test_archive_downloader_validates_csv_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            malformed = make_archive_csv(header="open_time,open,high,low,close,volume", rows=1)
            urlopen = mock.Mock(return_value=FakeArchiveResponse(make_archive_zip(malformed)))
            downloader = dataset.BinanceArchiveDownloader(urlopen=urlopen, sleep=lambda _: None)
            summary = downloader.download_range("2024-01-01", "2024-01-01", Path(tmp), Path(tmp) / "checkpoint.json")
            self.assertEqual(summary.downloaded_days, 0)
            self.assertEqual(summary.failed_dates, ("2024-01-01",))
            self.assertFalse((Path(tmp) / "BTCUSDT-1m-2024-01-01.csv").exists())

    def test_archive_downloader_checkpoint_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint.json"
            urlopen = mock.Mock(return_value=FakeArchiveResponse(make_archive_zip(make_archive_csv(rows=1))))
            downloader = dataset.BinanceArchiveDownloader(urlopen=urlopen, sleep=lambda _: None)
            downloader.download_range("2024-01-01", "2024-01-01", Path(tmp), checkpoint)
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(set(payload), {"last_completed_date", "downloaded_files", "failed_dates"})
            self.assertEqual(payload["last_completed_date"], "2024-01-01")
            self.assertEqual(payload["downloaded_files"], ["BTCUSDT-1m-2024-01-01.zip"])
            self.assertEqual(payload["failed_dates"], [])

    def test_build_dataset_from_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            (archive / "BTCUSDT-1m-2024-01-01.csv").write_text(make_archive_csv(rows=30), encoding="utf-8")
            build = dataset.build_dataset(archive_dir=archive, horizon=10)
            self.assertEqual(build.source, archive.as_posix())
            self.assertEqual(build.raw_rows, 30)
            self.assertEqual(build.gap_report.canonical_rows, 30)
            self.assertGreater(len(build.labeled_rows), 0)

    def test_cli_collect_archive_runs(self) -> None:
        class FakeDownloader:
            def download_range(self, start_date: str, end_date: str, output_dir: Path, checkpoint_file: Path | None = None) -> dataset.ArchiveDownloadSummary:
                output_dir.mkdir(parents=True, exist_ok=True)
                checkpoint = checkpoint_file or output_dir / "checkpoint.json"
                checkpoint.write_text(
                    json.dumps({"last_completed_date": end_date, "downloaded_files": [f"{end_date}_BTCUSDT-1m.zip"], "failed_dates": []}),
                    encoding="utf-8",
                )
                return dataset.ArchiveDownloadSummary(output_dir, checkpoint, start_date, end_date, 1, 1, 0, end_date, (f"{end_date}_BTCUSDT-1m.zip",), ())

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("btcusdt_quant.cli.dataset.BinanceArchiveDownloader", return_value=FakeDownloader()):
                code = main(["collect-archive", "--start", "2024-01-01", "--end", "2024-01-01", "--output", tmp, "--allow-public-network"])
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "checkpoint.json").exists())


class ExternalSourcesCollectorTests(unittest.TestCase):
    def test_collector_requires_allow_network(self) -> None:
        collector = dataset.ExternalSourcesCollector(allow_network=False)
        with self.assertRaises(RuntimeError):
            collector.fetch_funding_rate_history()

    def test_collector_build_sources_returns_empty_without_network(self) -> None:
        collector = dataset.ExternalSourcesCollector(allow_network=False)
        candles = make_stream_candles(5)
        sources = collector.build_external_sources_for_candles(candles)
        self.assertEqual(sources, {})

    def test_collector_build_sources_maps_candles(self) -> None:
        with mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_funding_rate_history") as mock_funding, \
             mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_mark_price_klines") as mock_mark, \
             mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_premium_index_klines") as mock_premium:
            mock_funding.return_value = [
                {"fundingTime": 1704067200000, "fundingRate": 0.0001, "markPrice": 42000.0}
            ]
            mock_mark.return_value = [
                {"open_time": 1704067200000, "open": 41990.0, "high": 42010.0, "low": 41980.0, "close": 42000.0}
            ]
            mock_premium.return_value = [
                {"open_time": 1704067200000, "open": 0.0001, "high": 0.0002, "low": 0.0001, "close": 0.00015}
            ]
            collector = dataset.ExternalSourcesCollector(allow_network=True)
            candles = make_stream_candles(5)
            sources = collector.build_external_sources_for_candles(candles)
            self.assertGreater(len(sources), 0)
            # Verify that at least the first candle has external sources
            first_time = candles[0].open_time
            if first_time in sources:
                self.assertIn("funding_rate", sources[first_time])
                self.assertIn("mark_price_1m", sources[first_time])

    def test_collector_fallback_when_api_fails(self) -> None:
        with mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_funding_rate_history") as mock_funding, \
             mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_mark_price_klines") as mock_mark, \
             mock.patch("btcusdt_quant.dataset.ExternalSourcesCollector.fetch_premium_index_klines") as mock_premium:
            mock_funding.return_value = []
            mock_mark.side_effect = urllib.error.URLError("network error")
            mock_premium.side_effect = urllib.error.URLError("network error")
            collector = dataset.ExternalSourcesCollector(allow_network=True)
            candles = make_stream_candles(5)
            sources = collector.build_external_sources_for_candles(candles)
            self.assertGreater(len(sources), 0)
            # Should fallback to approximation for mark price
            first_time = candles[0].open_time
            if first_time in sources:
                mark_data = sources[first_time].get("mark_price_1m", {})
                self.assertIn("mark_price", mark_data)


class DataQualityEdgeTests(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[tuple[object, ...]], header: str = "open_time,open,high,low,close,volume,quote_volume,number_of_trades") -> None:
        lines = [header]
        for row in rows:
            lines.append(",".join(str(value) for value in row))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_load_csv_rejects_duplicate_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            timestamp = data.utc_minute(2026, 1, 1, 0, 0).isoformat()
            self.write_csv(path, [(timestamp, 100.0, 101.0, 99.0, 100.5, 1.0, 100.0, 1), (timestamp, 101.0, 102.0, 100.0, 101.5, 1.0, 100.0, 1)])
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)

    def test_load_csv_rejects_negative_prices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            timestamp = data.utc_minute(2026, 1, 1, 0, 0).isoformat()
            self.write_csv(path, [(timestamp, -100.0, 101.0, 99.0, 100.5, 1.0, 100.0, 1)])
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)

    def test_load_csv_rejects_zero_volume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            self.write_csv(
                path,
                [
                    (base.replace(minute=0).isoformat(), 100.0, 101.0, 99.0, 100.5, 0.0, 100.0, 1),
                    (base.replace(minute=1).isoformat(), 100.5, 101.5, 100.0, 101.0, 0.0, 100.0, 1),
                ],
            )
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)

    def test_load_csv_rejects_reverse_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            self.write_csv(
                path,
                [
                    (base.replace(minute=1).isoformat(), 100.5, 101.5, 100.0, 101.0, 1.0, 100.0, 1),
                    (base.replace(minute=0).isoformat(), 100.0, 101.0, 99.0, 100.5, 1.0, 100.0, 1),
                ],
            )
            loaded = dataset.load_csv_candles(path)
            self.assertEqual([candle.open_time for candle in loaded], sorted(candle.open_time for candle in loaded))

    def test_load_csv_rejects_invalid_ohlc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            timestamp = data.utc_minute(2026, 1, 1, 0, 0).isoformat()
            self.write_csv(path, [(timestamp, 100.0, 99.0, 101.0, 100.5, 1.0, 100.0, 1)])
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)
            self.write_csv(path, [(timestamp, 100.0, 101.0, 99.0, 101.5, 1.0, 100.0, 1)])
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)

    def test_load_csv_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candles.csv"
            self.write_csv(path, [(100.0, 101.0, 99.0, 100.5, 1.0)], header="open,high,low,close,volume")
            with self.assertRaises(ValueError):
                dataset.load_csv_candles(path)

    def test_expanded_fixture_has_expected_gap_pattern(self) -> None:
        canonical = data.CanonicalTimelineBuilder().build(dataset.expanded_fixture(180))
        gap_indexes = [index for index, candle in enumerate(canonical) if candle.gap_flag == 1]
        self.assertEqual(gap_indexes, [37, 38, 119, 177])

    def test_canonical_timeline_rejects_empty_input(self) -> None:
        self.assertEqual(data.CanonicalTimelineBuilder().build([]), [])

    def test_build_feature_rows_handles_all_nan_features(self) -> None:
        nan = float("nan")
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(base.replace(minute=index), nan, nan, nan, nan, nan, nan, 0, nan, nan)
            for index in range(3)
        ]
        rows = dataset.build_feature_rows(candles)
        self.assertEqual(len(rows), 3)
        registry = dataset.feature_formula_registry()
        mock_features = {str(f["feature_name"]) for f in registry["features"] if f.get("scaffold_status") == "mock_implemented"}
        # F11/F12 features compute from external_sources (or fallback defaults) and do not depend on OHLCV
        external_source_features = {str(f["feature_name"]) for f in registry["features"] if f.get("source") in {"depth_snapshot", "adl_quantile", "funding_rate", "mark_price_1m", "premium_index_1m", "leverage_bracket"}}
        # F14 time/session features are computed from open_time (timestamp), not OHLCV values
        time_features = {"hour", "minute", "day_of_week", "session_asia", "session_europe", "session_us", "session_overlap", "weekend_flag"}
        # F15 momentum indicators have neutral default values during warmup
        momentum_defaults = {"rsi_7", "rsi_14"}  # RSI neutral = 50.0 during warmup
        for row in rows:
            self.assertEqual(set(row.features), set(dataset.FEATURE_NAMES))
            for name, value in row.features.items():
                if name in mock_features or name in external_source_features or name in time_features or name in momentum_defaults:
                    # Features with mock defaults, external source fallbacks, or time-based features return values even when OHLCV inputs are NaN
                    self.assertIsNotNone(value)
                else:
                    self.assertTrue(value == 0.0 or value != value or value is None, f"feature {name} must be 0.0 or NaN or None when all inputs are NaN")


class FeatureGovernanceTests(unittest.TestCase):
    def test_feature_clipper_bounds_and_inf_to_nan(self) -> None:
        result = features.FeatureClipper().clip({"return_1": 0.5, "return_5_vol_adj": 11.0, "close_zscore_60": 12.0, "volume_ratio": float("inf")})
        self.assertEqual(result.values["return_1"], 0.2)
        self.assertEqual(result.values["return_5_vol_adj"], 10.0)
        self.assertEqual(result.values["close_zscore_60"], 10.0)
        self.assertIsNone(result.values["volume_ratio"])

    def test_nan_source_classifier_distinguishes_outage(self) -> None:
        classifier = features.NaNSourceClassifier(optional_noncritical_features={"optional_feature"})
        self.assertEqual(classifier.classify({"gap_flag": 1}, "volume"), "outage_nan")
        self.assertEqual(classifier.classify({"warmup_invalid": 1}, "return_120"), "warmup_nan")
        self.assertEqual(classifier.classify({}, "optional_feature"), "structural_nan")

    def test_spearman_clustering_removes_correlated(self) -> None:
        matrix = [[float(index), float(index * 2), float(10 - index)] for index in range(10)]
        dropped = features.FeatureSelectionPipeline().spearman_clustering(matrix, ["a", "b", "c"], threshold=0.90)
        self.assertIn("b", dropped)

    def test_gain_importance_filter_drops_bottom(self) -> None:
        matrix = [[float(index), 1.0, float(index % 2)] for index in range(10)]
        dropped = features.FeatureSelectionPipeline().gain_importance_filter(matrix, ["high", "flat", "low"], drop_ratio=0.34)
        self.assertEqual(dropped, ["flat"])

    def test_permutation_importance_ranks_features(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0

        matrix = [[0.0, 1.0], [0.1, 0.0], [0.9, 0.0], [1.0, 1.0]]
        labels = [0, 0, 1, 1]
        ranked = features.FeatureSelectionPipeline().permutation_importance(ThresholdModel(), matrix, labels, ["signal", "noise"])
        self.assertEqual(ranked[0]["feature_name"], "signal")
        self.assertGreater(float(ranked[0]["metric_delta"]), 0.0)

    def test_shap_stability_scaffold(self) -> None:
        report = features.FeatureSelectionPipeline().shap_stability([[1.0], [2.0], [3.0]], ["a"])
        self.assertIn(report["status"], {"shap_unavailable", "shap_available_proxy", "insufficient_data"})

    def test_ablation_test_impact(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0

        matrix = [[0.0, 1.0], [0.1, 0.0], [0.9, 0.0], [1.0, 1.0]]
        labels = [0, 0, 1, 1]
        ranked = features.FeatureSelectionPipeline().ablation_test(ThresholdModel(), matrix, labels, ["signal", "noise"])
        self.assertEqual(ranked[0]["feature_name"], "signal")
        self.assertGreater(float(ranked[0]["impact"]), 0.0)

    def test_full_pipeline_returns_core_features(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0

        matrix = [[0.0, 1.0, 0.0], [0.1, 1.0, 1.0], [0.9, 1.0, 0.0], [1.0, 1.0, 1.0]]
        report = features.FeatureSelectionPipeline().run_full_pipeline(ThresholdModel(), matrix, [0, 0, 1, 1], ["signal", "flat", "noise"])
        self.assertIn("core_features", report)
        core_features = cast(list[str], report["core_features"])
        self.assertIn("signal", core_features)

    def test_feature_selection_bounds_trim_to_max(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0
        matrix = [[0.0, 1.0, 0.0], [0.1, 1.0, 1.0], [0.9, 1.0, 0.0], [1.0, 1.0, 1.0]]
        pipeline = features.FeatureSelectionPipeline(target_max_features=2)
        report = pipeline.run_full_pipeline(ThresholdModel(), matrix, [0, 0, 1, 1], ["signal", "flat", "noise"])
        self.assertIn("core_features_bounded", report)
        bounded = cast(list[str], report["core_features_bounded"])
        self.assertLessEqual(len(bounded), 2)

    def test_feature_selection_bounds_backfill_to_min(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0
        matrix = [[0.0, 1.0, 0.0], [0.1, 1.0, 1.0], [0.9, 1.0, 0.0], [1.0, 1.0, 1.0]]
        pipeline = features.FeatureSelectionPipeline(target_min_features=5)
        report = pipeline.run_full_pipeline(ThresholdModel(), matrix, [0, 0, 1, 1], ["signal", "flat", "noise"])
        self.assertIn("core_features_bounded", report)
        bounded = cast(list[str], report["core_features_bounded"])
        # With only 3 features total, backfill can only reach 3
        self.assertGreaterEqual(len(bounded), 2)
        self.assertLessEqual(len(bounded), 3)

    def test_feature_selection_bounds_disabled_when_zero(self) -> None:
        class ThresholdModel:
            def predict(self, row: list[float]) -> int:
                return 1 if row[0] >= 0.5 else 0
        matrix = [[0.0, 1.0, 0.0], [0.1, 1.0, 1.0], [0.9, 1.0, 0.0], [1.0, 1.0, 1.0]]
        pipeline = features.FeatureSelectionPipeline()
        report = pipeline.run_full_pipeline(ThresholdModel(), matrix, [0, 0, 1, 1], ["signal", "flat", "noise"])
        self.assertIn("core_features_bounded", report)
        bounded = cast(list[str], report["core_features_bounded"])
        core = cast(list[str], report["core_features"])
        self.assertEqual(bounded, core)

    def test_bootstrap_ci_deterministic_with_seed(self) -> None:
        engine = features.BootstrapCIEngine()
        first = engine.bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=7)
        second = engine.bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=7)
        self.assertEqual(first, second)

    def test_bootstrap_ci_1000_iterations(self) -> None:
        lower, upper = features.BootstrapCIEngine().bootstrap_ci([0.0, 1.0], n_iterations=1000, seed=1)
        self.assertLessEqual(lower, upper)
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 1.0)

    def test_score_bin_ci_groups_correctly(self) -> None:
        rows = [("low", -0.01, 0), ("low", 0.02, 1), ("high", 0.03, 1)]
        report = features.BootstrapCIEngine().score_bin_ci(rows, n_iterations=100, seed=3)
        by_bin = {row["score_bin"]: row for row in report}
        self.assertEqual(by_bin["low"]["trade_count"], 2)
        self.assertEqual(by_bin["high"]["trade_count"], 1)

    def test_score_bin_ci_win_rate_bounds(self) -> None:
        rows = [("mid", -0.01, 0), ("mid", 0.02, 1), ("mid", 0.03, 1)]
        report = features.BootstrapCIEngine().score_bin_ci(rows, n_iterations=100, seed=4)
        self.assertGreaterEqual(float(report[0]["win_rate_ci_lower_95"]), 0.0)
        self.assertLessEqual(float(report[0]["win_rate_ci_upper_95"]), 1.0)

    def test_platt_calibrator_improves_brier(self) -> None:
        probabilities = [0.40, 0.45, 0.55, 0.60] * 8
        labels = [0, 0, 1, 1] * 8
        calibrator = features.PlattCalibrator().fit(probabilities, labels)
        calibrated = calibrator.transform(probabilities)
        raw_brier = sum((probability - label) ** 2 for probability, label in zip(probabilities, labels)) / len(labels)
        calibrated_brier = sum((probability - label) ** 2 for probability, label in zip(calibrated, labels)) / len(labels)
        self.assertLess(calibrated_brier, raw_brier)

    def test_beta_calibrator_bounded_output(self) -> None:
        probabilities = [0.05, 0.10, 0.80, 0.95] * 60
        labels = [0, 0, 1, 1] * 60
        calibrator = features.BetaCalibrator().fit(probabilities, labels)
        calibrated = calibrator.transform([0.001, 0.5, 0.999])
        self.assertTrue(all(0.0 <= probability <= 1.0 for probability in calibrated))

    def test_calibration_module_selects_platt_for_small_samples(self) -> None:
        calibrator = features.CalibrationModule().fit([0.4, 0.6], [0, 1], positive_samples=1)
        self.assertIsInstance(calibrator, features.PlattCalibrator)

    def test_calibration_module_selects_beta_for_large_samples(self) -> None:
        probabilities = [0.2, 0.8] * 100
        labels = [0, 1] * 100
        calibrator = features.CalibrationModule().fit(probabilities, labels, positive_samples=200)
        self.assertIsInstance(calibrator, features.BetaCalibrator)

    def test_calibration_convergence_reported(self) -> None:
        calibrator = features.PlattCalibrator().fit([0.3, 0.4, 0.6, 0.7], [0, 0, 1, 1])
        report = cast(Mapping[str, object], calibrator.as_dict()["convergence"])
        self.assertIn("converged", report)
        self.assertIn("iterations", report)
        self.assertIn("final_loss", report)

    def test_champion_challenger_three_tiers_exist(self) -> None:
        self.assertEqual(features.ChallengerLifecycle.SHADOW.value, "shadow")
        self.assertEqual(features.ChallengerLifecycle.CANARY_5.value, "canary_5")
        self.assertEqual(features.ChallengerLifecycle.FULL_PROMOTION.value, "full_promotion")
        manager = features.ChampionChallengerManager()
        self.assertEqual(manager.CANARY_STAGES[features.ChallengerLifecycle.SHADOW].traffic_percent, 0)
        self.assertEqual(manager.CANARY_STAGES[features.ChallengerLifecycle.CANARY_5].traffic_percent, 5)
        self.assertEqual(manager.CANARY_STAGES[features.ChallengerLifecycle.FULL_PROMOTION].traffic_percent, 100)

    def test_canary_advance_5_to_20_to_50_to_100(self) -> None:
        manager = features.ChampionChallengerManager()
        metrics = {"elapsed_seconds": 60, "mdd": 0.10, "calmar": 3.0, "latency_p99_ms": 50.0, "psi": 0.05}
        first = manager.advance_canary(features.ChallengerLifecycle.CANARY_5, metrics)
        self.assertEqual(first["next_stage"], "canary_20")
        self.assertEqual(first["traffic_percent"], 20)
        second = manager.advance_canary(str(first["next_stage"]), metrics)
        self.assertEqual(second["next_stage"], "canary_50")
        self.assertEqual(second["traffic_percent"], 50)
        third = manager.advance_canary(str(second["next_stage"]), metrics)
        self.assertEqual(third["next_stage"], "full_promotion")
        self.assertEqual(third["traffic_percent"], 100)

    def test_canary_rollback_on_mdd_breach(self) -> None:
        result = features.ChampionChallengerManager().advance_canary(
            "canary_5",
            {"elapsed_seconds": 60, "mdd": 0.16, "calmar": 3.0, "latency_p99_ms": 50.0, "psi": 0.05},
        )
        self.assertEqual(result["action"], "rollback_to_champion")
        self.assertEqual(result["next_stage"], "rejected")
        reasons = result["reasons"]
        if not isinstance(reasons, list):
            self.fail("rollback reasons must be a list")
        self.assertIn("MDD exceeds 15%", reasons)

    def test_rollback_sla_within_10_30_seconds(self) -> None:
        result = features.ChampionChallengerManager().rollback_to_champion("canary mdd breach")
        self.assertEqual(result["action"], "rollback_to_champion")
        elapsed_seconds = result["elapsed_seconds"]
        if not isinstance(elapsed_seconds, int):
            self.fail("elapsed_seconds must be an int")
        self.assertGreaterEqual(elapsed_seconds, 10)
        self.assertLessEqual(elapsed_seconds, 30)
        self.assertTrue(result["sla_met"])

    def test_shadow_rejection_before_min_duration(self) -> None:
        result = features.ChampionChallengerManager().advance_canary(
            "shadow",
            {"shadow_days": 29, "signal_count": 100, "mdd_delta": 0.0, "calmar_delta": 0.0},
        )
        self.assertEqual(result["action"], "reject")
        reasons = result["reasons"]
        if not isinstance(reasons, list):
            self.fail("shadow rejection reasons must be a list")
        self.assertIn("shadow duration too short", reasons)

    def test_promotion_gates_all_required(self) -> None:
        manager = features.ChampionChallengerManager()
        report = manager.evaluate_shadow_metrics(
            {
                "shadow_days": 30,
                "signal_count": 100,
                "mdd_delta": 0.0,
                "calmar_delta": 0.0,
                "sharpe": 1.0,
                "mdd": 0.14,
                "calmar": 2.1,
                "score_bin_ci": [(0.01, 0.03)],
                "threshold_flip_rate": 0.04,
                "latency_p99_ms": 99.0,
                "psi": 0.09,
            }
        )
        self.assertTrue(report["passed"])
        checked_gates = report["checked_gates"]
        if not isinstance(checked_gates, list):
            self.fail("checked_gates must be a list")
        self.assertEqual(set(checked_gates), set(manager.PROMOTION_GATES))
        rejected = manager.evaluate_shadow_metrics(
            {
                "shadow_days": 30,
                "signal_count": 100,
                "mdd_delta": 0.0,
                "calmar_delta": 0.0,
                "sharpe": 0.9,
                "mdd": 0.15,
                "calmar": 2.0,
                "score_bin_ci": [(-0.01, 0.01)],
                "threshold_flip_rate": 0.05,
                "latency_p99_ms": 100.0,
                "psi": 0.10,
            }
        )
        self.assertFalse(rejected["passed"])
        rejected_reasons = rejected["reasons"]
        if not isinstance(rejected_reasons, list):
            self.fail("rejected reasons must be a list")
        self.assertEqual(len(rejected_reasons), 7)

    def test_optuna_study_runner_fallback_without_optuna(self) -> None:
        def blocked_import(name: str, globals: Mapping[str, object] | None = None, locals: Mapping[str, object] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> object:
            if name == "optuna":
                raise ImportError("blocked optional optuna")
            return original_import(name, globals, locals, fromlist, level)

        class SumModel:
            def predict(self, row: list[float]) -> float:
                return 1.0 if sum(row) >= 0.0 else 0.0

        original_import = __import__
        with mock.patch("builtins.__import__", side_effect=blocked_import):
            result = features.OptunaStudyRunner().run_study(lambda params: SumModel(), [[-1.0], [1.0], [-0.5], [0.5]], [0, 1, 0, 1], 2, "research_fast")
        self.assertFalse(result["optuna_available"])
        self.assertEqual(result["best_params"], {"threshold": 0.5})
        trial_history = result["trial_history"]
        if not isinstance(trial_history, list):
            self.fail("trial_history must be a list")
        self.assertEqual(len(trial_history), 1)

    def test_optuna_study_runner_returns_best_params(self) -> None:
        if importlib.util.find_spec("optuna") is None:
            self.skipTest("optuna is optional and not installed")

        class SumModel:
            def fit(self, feature_matrix: list[list[float]], labels: list[int]) -> None:
                self.rows = len(feature_matrix)

            def predict(self, row: list[float]) -> float:
                return 1.0 if sum(row) >= 0.0 else 0.0

        result = features.OptunaStudyRunner().run_study(lambda params: SumModel(), [[-1.0], [1.0], [-0.5], [0.5], [0.8], [-0.8]], [0, 1, 0, 1, 1, 0], 2, "research_fast")
        self.assertTrue(result["optuna_available"])
        self.assertIsInstance(result["best_params"], dict)
        trial_history = result["trial_history"]
        if not isinstance(trial_history, list):
            self.fail("trial_history must be a list")
        self.assertGreaterEqual(len(trial_history), 1)

    def test_optuna_objective_includes_mdd_p90(self) -> None:
        description = features.OptunaStudyRunner.OBJECTIVE_DESCRIPTION
        self.assertIn("MDD(p90)", description)
        self.assertIn("100 shuffled", description)

    def test_optuna_budget_profiles_has_objective(self) -> None:
        profiles = features.OptunaBudgetProfiles()
        for name in profiles.PROFILES:
            profile = profiles.get_profile_with_objective(name)
            self.assertIn("trials", profile)
            self.assertIn("bootstrap_samples", profile)
            self.assertIn("objective_description", profile)
            self.assertIn("MDD(p90)", str(profile["objective_description"]))


class LiveSafetyTests(unittest.TestCase):
    def test_rate_limit_budget_and_status_actions(self) -> None:
        manager = live.RateLimitManager(limit_per_minute=10)
        manager.acquire("GET /fapi/v1/klines", 8)
        with self.assertRaises(live.RateLimitBudgetExceeded):
            manager.acquire("GET /fapi/v1/klines", 1)
        self.assertEqual(manager.observe_status(429), "block_new_entries")
        self.assertEqual(manager.observe_status(418), "hard_kill")

    def test_one_way_position_guard_blocks_existing_position(self) -> None:
        allowed, reason = live.OneWayPositionGuard().can_enter(live.PositionState("BTCUSDT", 0.1), "BUY")
        self.assertFalse(allowed)
        self.assertIn("blocks new entry", reason)

    def test_position_sizer_enforces_notional_fraction(self) -> None:
        result = live.PositionSizer().fixed_notional(100000.0, 10000.0, 0.5, 1.0, 0.001, 0.001, 0.1)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "max_notional_fraction breached")

    def test_mock_exchange_never_uses_network(self) -> None:
        adapter = live.MockExchangeAdapter()
        order = adapter.submit_order("BTCUSDT", "BUY", "LIMIT", 0.001)
        self.assertEqual(order.status, "MOCK_ACCEPTED")
        self.assertFalse(adapter.network_enabled)


class RiskBoundaryTests(unittest.TestCase):
    def test_position_sizer_rejects_invalid_input(self) -> None:
        sizer = live.PositionSizer()
        invalid_cases = [
            (0.0, 1000.0, 0.01, 1.0, 0.001, 0.001, 0.1),
            (100000.0, 0.0, 0.01, 1.0, 0.001, 0.001, 0.1),
            (100000.0, 1000.0, 0.01, 0.0, 0.001, 0.001, 0.1),
            (100000.0, 1000.0, 0.01, 1.0, 0.001, 0.0, 0.1),
        ]
        for args in invalid_cases:
            result = sizer.fixed_notional(*args)
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason, "invalid sizing input")

    def test_position_sizer_enforces_min_qty(self) -> None:
        result = live.PositionSizer().fixed_notional(100000.0, 100.0, 0.001, 1.0, 0.001, 0.001, 0.1)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "below_min_qty")

    def test_position_sizer_enforces_qty_step(self) -> None:
        result = live.PositionSizer().fixed_notional(100.0, 1000.0, 0.1234, 1.0, 0.1, 0.1, 1.0)
        self.assertTrue(result.accepted)
        self.assertAlmostEqual(result.quantity, 1.2)
        self.assertAlmostEqual(result.quantity / 0.1, round(result.quantity / 0.1))

    def test_position_sizer_emergency_budget_exhaustion(self) -> None:
        manager = live.RateLimitManager(limit_per_minute=10, emergency_reserved_ratio=0.20)
        manager.acquire_emergency("POST /fapi/v1/order", 2)
        with self.assertRaises(live.RateLimitBudgetExceeded):
            manager.acquire_emergency("POST /fapi/v1/order", 1)

    def test_rate_limit_manager_429_backoff_resets(self) -> None:
        manager = live.RateLimitManager(limit_per_minute=10)
        self.assertEqual(manager.observe_status(429), "block_new_entries")
        with self.assertRaises(live.RateLimitBackoffActive):
            manager.acquire("GET /fapi/v1/klines", 1)

    def test_rate_limit_manager_418_hard_ban_all_calls(self) -> None:
        manager = live.RateLimitManager(limit_per_minute=10)
        self.assertEqual(manager.observe_status(418), "hard_kill")
        with self.assertRaises(live.RateLimitHardBanActive):
            manager.acquire("GET /fapi/v1/klines", 1)
        with self.assertRaises(live.RateLimitHardBanActive):
            manager.acquire_emergency("POST /fapi/v1/order", 1)

    def test_one_way_position_guard_rejects_invalid_side(self) -> None:
        allowed, reason = live.OneWayPositionGuard().can_enter(live.PositionState("BTCUSDT", 0.0), "HOLD")
        self.assertFalse(allowed)
        self.assertEqual(reason, "invalid signal side")

    def test_one_way_position_guard_allows_flat_position(self) -> None:
        allowed, reason = live.OneWayPositionGuard().can_enter(live.PositionState("BTCUSDT", 0.0), "BUY")
        self.assertTrue(allowed)
        self.assertEqual(reason, "flat position allows entry")


class GovernanceTests(unittest.TestCase):
    def test_pipeline_stage_enforcer_rejects_skips(self) -> None:
        enforcer = governance.PipelineStageEnforcer()
        with self.assertRaises(governance.PipelineStageError):
            enforcer.complete("SCHEMA_VALIDATION")
        for stage in governance.PIPELINE_STAGES:
            enforcer.complete(stage)
        self.assertEqual(len(enforcer.completed), 13)

    def test_fallback_policy_is_deterministic(self) -> None:
        self.assertEqual(governance.fallback_action("gap_ratio_20", 0.20), "block_new_entries")
        self.assertEqual(governance.fallback_action("dataset_card_hash_mismatch", True), "hard_kill")
        self.assertEqual(governance.fallback_action("unknown", 0), "allow")

    def test_seven_stage_fallback_chain(self) -> None:
        self.assertEqual(
            governance.FALLBACK_ACTION_CHAIN,
            (
                "warn_only",
                "raise_threshold",
                "reduce_size",
                "no_trade_current_bar",
                "block_new_entries",
                "rollback_to_champion",
                "hard_kill",
            ),
        )
        engine = governance.MonitoringSLOEngine()
        actions = engine.evaluate(
            {
                "ece_drift": 0.06,
                "calibration_ece": 0.12,
                "rolling_7d_net_expectancy": -0.01,
                "critical_feature_missing_rate_current_bar": 0.01,
                "schema_violation_count": 1,
                "champion_challenger_degradation": True,
                "http_418_detected": True,
            }
        )
        self.assertEqual(actions["ece_drift"], "warn_only")
        self.assertEqual(actions["calibration_ece"], "raise_threshold")
        self.assertEqual(actions["rolling_7d_net_expectancy"], "reduce_size")
        self.assertEqual(actions["critical_feature_missing_rate_current_bar"], "no_trade_current_bar")
        self.assertEqual(actions["schema_violation_count"], "block_new_entries")
        self.assertEqual(actions["champion_challenger_degradation"], "rollback_to_champion")
        self.assertEqual(actions["http_418_detected"], "hard_kill")

    def test_demo_generates_verifiable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_demo(output)
            self.assertFalse(summary["network_used"])
            ok, errors = governance.verify_manifest(output)
            self.assertTrue(ok, errors)
            manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
            paths = {artifact["path"] for artifact in manifest["artifacts"]}
            self.assertIn("dataset_card.json", paths)
            self.assertIn("dataset_card.yaml", paths)
            self.assertIn("model_card.json", paths)
            self.assertIn("model_card.yaml", paths)
            self.assertIn("column_data_contract.csv", paths)
            self.assertIn("train_live_feature_parity_report.csv", paths)
            self.assertIn("monitoring_slo_report.csv", paths)
            self.assertIn("lineage_manifest.json", paths)

    def test_approval_package_uses_actual_feature_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_demo(output)
            registry = json.loads((output / "feature_formula_registry.json").read_text(encoding="utf-8"))
            registry_features = cast(list[dict[str, object]], registry["features"])
            expected_features = cast(list[dict[str, object]], dataset.feature_formula_registry()["features"])
            self.assertEqual(len(registry_features), len(expected_features))
            self.assertGreaterEqual(len(registry_features), 30)

    def test_approval_package_uses_actual_calibration_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_demo(output)
            text = (output / "calibration_config.yaml").read_text(encoding="utf-8")
            self.assertIn("calibrator_type:", text)
            self.assertIn("convergence_status:", text)
            self.assertNotIn("scaffold_not_fitted", text)

    def test_approval_package_no_mock_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_demo(output)
            with (output / "bootstrap_ci_report.csv").open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertGreater(sum(int(row["trade_count"]) for row in rows), 0)
            self.assertNotIn("mock", (output / "model_card.json").read_text(encoding="utf-8"))
            self.assertNotIn("mock", (output / "security_compliance_signoff.yaml").read_text(encoding="utf-8"))

    def test_manifest_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "artifact_manifest.json").write_text(
                '{"artifacts":[{"path":"../README.md","sha256":"bad"}]}',
                encoding="utf-8",
            )
            ok, errors = governance.verify_manifest(output)
            self.assertFalse(ok)
            self.assertIn("unsafe artifact path: ../README.md", errors)

    def test_rolling_feature_engine_strict_warmup_none_for_insufficient_window(self) -> None:
        self.assertEqual(features.RollingFeatureEngine().rolling_mean([1.0, 2.0, 3.0], 2), [None, 1.5, 2.5])

    def test_calibration_module_selects_platt_for_small_samples(self) -> None:
        calibrator = features.CalibrationModule().fit([0.4, 0.6], [0, 1], positive_samples=1)
        self.assertIsInstance(calibrator, features.PlattCalibrator)

    def test_calibration_module_selects_beta_for_large_samples(self) -> None:
        calibrator = features.CalibrationModule().fit([0.2, 0.8] * 100, [0, 1] * 100, positive_samples=200)
        self.assertIsInstance(calibrator, features.BetaCalibrator)

    def test_purged_walk_forward_split_generates_non_overlapping_folds(self) -> None:
        splits = features.PurgedWalkForwardSplit().split(20, 5, 3, 3, 1)
        self.assertEqual(len(splits), 3)
        for split in splits:
            self.assertFalse(set(split.train) & set(split.validation))
            self.assertFalse(set(split.validation) & set(split.test))
            self.assertFalse(set(split.train) & set(split.test))

    def test_feature_selection_pipeline_core_features_survival_rule(self) -> None:
        self.assertEqual(features.FeatureSelectionPipeline().core_features([["a", "b"], ["a"], ["a", "c"]]), ["a"])

    def test_bootstrap_ci_engine_deterministic_percentile_bounds(self) -> None:
        self.assertEqual(features.BootstrapCIEngine().ci95([-0.1, 0.0, 0.1]), (-0.1, 0.0))

    def test_optuna_budget_profiles_returns_trials_and_bootstrap_samples(self) -> None:
        profile = features.OptunaBudgetProfiles().get("practical_start")
        self.assertEqual(profile["trials"], 200)
        self.assertEqual(profile["bootstrap_samples"], 500)

    def test_champion_challenger_manager_promotion_gates(self) -> None:
        accepted, reason = features.ChampionChallengerManager().can_promote(
            30, 100, -0.01, 0.01,
            sharpe=1.5, mdd=0.10, calmar=2.5,
            score_bin_ci=[{"lower": 0.01, "upper": 0.05}],
            threshold_flip_rate=0.02, latency_p99_ms=50.0, psi=0.05,
        )
        self.assertTrue(accepted)
        self.assertEqual(reason, "promotion gates passed")

    def test_data_quality_gate_blocks_on_schema_violation(self) -> None:
        result = governance.DataQualityGate().evaluate(1, 0.0, False)
        self.assertEqual(result.action, "block_new_entries")
        self.assertFalse(result.approval_eligible)

    def test_data_quality_gate_hard_kills_on_hash_mismatch(self) -> None:
        result = governance.DataQualityGate().evaluate(0, 0.0, True)
        self.assertEqual(result.action, "hard_kill")
        self.assertFalse(result.approval_eligible)

    def test_source_grade_manager_passes_parity_for_grade_a(self) -> None:
        report = governance.SourceGradeManager().grade("klines_1m", True, True)
        self.assertEqual(report["availability_grade"], "A")
        self.assertTrue(report["train_live_feature_parity_passed"])

    def test_monitoring_slo_engine_maps_gap_ratio_to_block(self) -> None:
        self.assertEqual(governance.MonitoringSLOEngine().evaluate({"gap_ratio_20": 0.20})["gap_ratio_20"], "block_new_entries")

    def test_clock_drift_monitor_hard_kills_at_1000ms(self) -> None:
        self.assertEqual(governance.ClockDriftMonitor().action(1000), "hard_kill")

    def test_adl_monitor_blocks_at_quantile_4(self) -> None:
        self.assertEqual(governance.ADLMonitor().action(4), "block_new_entries")

    def test_funding_event_manager_blackout_active_near_funding(self) -> None:
        self.assertTrue(live.FundingEventManager().blackout_active(3))

    def test_funding_event_manager_no_blackout_far_from_funding(self) -> None:
        self.assertFalse(live.FundingEventManager().blackout_active(6))

    def test_ghost_fill_prevention_hard_kills_on_unresolved_exit_orders(self) -> None:
        self.assertEqual(live.GhostFillPrevention().safe_market_exit(1, 0.1, False), "hard_kill")

    def test_ghost_fill_prevention_allows_exit_after_cancel_resolved(self) -> None:
        self.assertEqual(live.GhostFillPrevention().safe_market_exit(1, 0.1, True), "market_exit_submitted")

    def test_emergency_close_executor_submits_on_priority_zero(self) -> None:
        self.assertEqual(live.EmergencyCloseExecutor().close(0, 0), "emergency_close_submitted")

    def test_emergency_close_executor_queues_on_nonzero_priority(self) -> None:
        self.assertEqual(live.EmergencyCloseExecutor().close(1, 0), "queued")

    def test_emergency_close_executor_hard_kills_after_max_retries(self) -> None:
        self.assertEqual(live.EmergencyCloseExecutor().close(0, 3, max_retries=2), "hard_kill")

    def test_ml_and_ops_scaffold_modules(self) -> None:
        self.assertEqual(features.RollingFeatureEngine().rolling_mean([1.0, 2.0, 3.0], 2), [None, 1.5, 2.5])
        self.assertEqual(features.CalibrationModule().select_method(40), "platt")
        self.assertEqual(len(features.PurgedWalkForwardSplit().split(20, 5, 3, 3, 1)), 3)
        self.assertEqual(features.FeatureSelectionPipeline().core_features([["a", "b"], ["a"], ["a", "c"]]), ["a"])
        self.assertEqual(features.BootstrapCIEngine().ci95([-0.1, 0.0, 0.1]), (-0.1, 0.0))
        self.assertEqual(features.OptunaBudgetProfiles().get("practical_start")["trials"], 200)
        self.assertTrue(features.ChampionChallengerManager().can_promote(30, 100, -0.01, 0.01, sharpe=1.5, mdd=0.10, calmar=2.5, score_bin_ci=[{"lower": 0.01, "upper": 0.05}], threshold_flip_rate=0.02, latency_p99_ms=50.0, psi=0.05)[0])
        self.assertEqual(governance.DataQualityGate().evaluate(1, 0.0, False).action, "block_new_entries")
        self.assertTrue(governance.SourceGradeManager().grade("klines_1m", True, True)["train_live_feature_parity_passed"])
        self.assertEqual(governance.MonitoringSLOEngine().evaluate({"gap_ratio_20": 0.20})["gap_ratio_20"], "block_new_entries")
        self.assertEqual(governance.ClockDriftMonitor().action(1000), "hard_kill")
        self.assertEqual(governance.ADLMonitor().action(4), "block_new_entries")

    def test_execution_safety_modules(self) -> None:
        self.assertTrue(live.FundingEventManager().blackout_active(3))
        self.assertEqual(live.GhostFillPrevention().safe_market_exit(1, 0.1, False), "hard_kill")
        self.assertEqual(live.EmergencyCloseExecutor().close(0, 0), "emergency_close_submitted")


class WebSocketStreamTests(unittest.TestCase):
    def test_websocket_client_mock_receives_fixture(self) -> None:
        fixture = make_stream_candles(3)
        client = live.MockWebSocketClient(fixture)
        client.start()
        try:
            received = [client.next_candle(timeout=0.5) for _ in fixture]
        finally:
            client.close()
        self.assertEqual([candle.open_time for candle in received if candle is not None], [candle.open_time for candle in fixture])
        self.assertEqual(len(client.buffer_snapshot()), 3)

    def test_stream_gap_detector_flags_missing_minute(self) -> None:
        candles = make_stream_candles(3)
        detector = live.StreamGapDetector()
        detector.observe(candles[0])
        detection = detector.observe(candles[2])
        self.assertTrue(detection.stream_desync_detected)
        self.assertEqual(detection.missing_open_times, [candles[1].open_time])
        self.assertIsNone(detection.anomaly)

    def test_rest_backfill_fills_gap(self) -> None:
        candles = make_stream_candles(3)
        backfill = live.RESTBackfill(fetcher=lambda open_times: [candles[1] for _ in open_times])
        repaired = backfill.backfill_missing([candles[1].open_time])
        self.assertEqual(len(repaired), 1)
        self.assertTrue(repaired[0].repaired)
        self.assertEqual(repaired[0].gap_flag, 1)
        self.assertEqual(backfill.events[0]["filled"], 1)

    def test_stream_desync_detected_after_3_missing(self) -> None:
        candles = make_stream_candles(5)
        detector = live.StreamGapDetector()
        detector.observe(candles[0])
        detection = detector.observe(candles[4])
        self.assertTrue(detection.stream_desync_detected)
        self.assertEqual(detection.consecutive_missing, 3)
        self.assertEqual(detection.anomaly, "stream_desync")

    def test_live_engine_produces_canonical_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = live.run_live(Path(tmp), dry_run=True, max_candles=12)
            self.assertTrue(result.summary["stream_desync_detected"])
            self.assertEqual(result.summary["backfilled_rows"], 3)
            self.assertEqual(len(result.canonical), result.summary["canonical_rows"])
            self.assertTrue((Path(tmp) / "live_summary.json").exists())

    def test_cli_live_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["live", "--dry-run", "--output", tmp])
            self.assertEqual(code, 0)
            summary = json.loads((Path(tmp) / "live_summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["network_used"])
            self.assertTrue(summary["stream_desync_detected"])

    def test_websocket_graceful_shutdown(self) -> None:
        client = live.MockWebSocketClient(make_stream_candles(20), interval_seconds=0.01)
        client.start()
        client.close()
        self.assertTrue(client.is_finished())

    def test_websocket_buffer_thread_safe(self) -> None:
        candles = make_stream_candles(40)
        client = live.MockWebSocketClient([], buffer_size=50)

        def add_rows(rows: list[data.Candle]) -> None:
            for candle in rows:
                client.add_candle(candle)
                client.buffer_snapshot()

        threads = [threading.Thread(target=add_rows, args=(candles[index::4],)) for index in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        snapshot = client.buffer_snapshot()
        self.assertEqual(len(snapshot), 40)
        self.assertEqual([candle.open_time for candle in snapshot], sorted(candle.open_time for candle in candles))


class OfflineTrainingTests(unittest.TestCase):
    def test_purged_default_splits_have_no_overlap(self) -> None:
        splits = training.default_splits(140, 3)
        self.assertGreater(len(splits), 0)
        for split in splits:
            self.assertEqual(split.validation.start - split.train.stop, 3)
            self.assertEqual(split.test.start - split.validation.stop, 3)
            self.assertFalse(set(split.train) & set(split.validation))
            self.assertFalse(set(split.validation) & set(split.test))
            self.assertFalse(set(split.train) & set(split.test))

    def test_training_run_generates_verifiable_offline_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_train(output)
            self.assertFalse(summary["network_used"])
            self.assertFalse(summary["credentials_required"])
            self.assertFalse(summary["orders_enabled"])
            ok, errors = governance.verify_manifest(output)
            self.assertTrue(ok, errors)
            manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
            paths = {artifact["path"] for artifact in manifest["artifacts"]}
            self.assertIn("dataset_card.json", paths)
            self.assertIn("model_card.json", paths)
            self.assertIn("feature_formula_registry.json", paths)
            self.assertIn("split_manifest.csv", paths)
            self.assertIn("fold_metrics.csv", paths)
            self.assertIn("calibration_report.json", paths)
            self.assertIn("threshold_report.json", paths)
            dataset_card = json.loads((output / "dataset_card.json").read_text(encoding="utf-8"))
            model_card = json.loads((output / "model_card.json").read_text(encoding="utf-8"))
            self.assertFalse(dataset_card["network_required"])
            self.assertFalse(model_card["network_required"])


class EndToEndArtifactRegressionTests(unittest.TestCase):
    def test_demo_generates_data_driven_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_demo(output)
            dataset_yaml = (output / "dataset_card.yaml").read_text(encoding="utf-8")
            self.assertIn(f"feature_count: {len(dataset.FEATURE_NAMES)}", dataset_yaml)
            calibration_yaml = (output / "calibration_config.yaml").read_text(encoding="utf-8")
            self.assertIn("calibrator_type: platt", calibration_yaml)
            self.assertIn("final_loss:", calibration_yaml)
            self.assertNotIn("not_run_for_local_demo", calibration_yaml)
            with (output / "bootstrap_ci_report.csv").open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertEqual(sum(int(row["trade_count"]) for row in rows), 3)
            self.assertIn("net_return_ci_lower_95", rows[0])
            self.assertIn("win_rate_ci_upper_95", rows[0])

    def test_training_generates_data_driven_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_train(output)
            fold_count_value = summary["fold_count"]
            if not isinstance(fold_count_value, (float, int, str)):
                self.fail("fold_count must be numeric")
            fold_count = int(fold_count_value)
            model = json.loads((output / "model.json").read_text(encoding="utf-8"))
            weights = cast(dict[str, float], model["weights"])
            self.assertEqual(set(weights), set(dataset.FEATURE_NAMES))
            self.assertTrue(any(value != 0.0 for value in weights.values()))
            with (output / "fold_metrics.csv").open("r", newline="", encoding="utf-8") as handle:
                fold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(fold_rows), fold_count * 2)
            self.assertTrue(all(float(row["rows"]) > 0.0 for row in fold_rows))
            calibration_report = json.loads((output / "calibration_report.json").read_text(encoding="utf-8"))
            fold_calibrators = cast(list[dict[str, object]], calibration_report["fold_calibrators"])
            self.assertEqual(len(fold_calibrators), fold_count)
            self.assertTrue(all(row.get("method") in {"platt", "beta"} for row in fold_calibrators))

    def test_artifact_manifest_verifies_all_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo_output = root / "demo"
            training_output = root / "training"
            run_demo(demo_output)
            run_train(training_output)
            demo_ok, demo_errors = governance.verify_manifest(demo_output)
            train_ok, train_errors = governance.verify_manifest(training_output)
            self.assertTrue(demo_ok, demo_errors)
            self.assertTrue(train_ok, train_errors)

    def test_cli_demo_command_runs_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_demo(output)
            self.assertFalse(summary["network_used"])
            self.assertTrue((output / "artifact_manifest.json").exists())

    def test_cli_train_command_runs_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_train(output)
            self.assertFalse(summary["network_used"])
            self.assertTrue((output / "artifact_manifest.json").exists())


class TestDatasetCacheParquet(unittest.TestCase):
    def _build_dataset(self, rows: int = 5, feature_names: tuple[str, ...] = ("return_1", "return_5", "momentum_10", "volatility_20")) -> dataset.DatasetBuild:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        labeled_rows: list[dataset.LabeledRow] = []
        feature_rows: list[dataset.FeatureRow] = []
        for index in range(rows):
            open_time = base + timedelta(minutes=index)
            row_features = {
                "return_1": 0.01 + index * 0.001,
                "return_5": 0.02 + index * 0.001,
                "momentum_10": 0.5 + index * 0.01,
                "volatility_20": 0.3 + index * 0.02,
            }
            feature_rows.append(dataset.FeatureRow(index, open_time, dict(row_features), 0, False, False))
            labeled_rows.append(
                dataset.LabeledRow(
                    index,
                    open_time,
                    dict(row_features),
                    index % 2,
                    "tp_first" if index % 2 else "timeout_no_tp",
                    0.01 if index % 2 else -0.01,
                    0,
                    False,
                    False,
                )
            )
        gap_report = dataset.GapReport(rows, rows, 0, 0.0, 0, base.isoformat(), (base + timedelta(minutes=rows - 1)).isoformat())
        source_report = {
            "feature_space_parity_passed": True,
            "train_live_feature_parity_passed": True,
            "source_hashes": {},
            "unavailable_sources": (),
            "grade_c_sources": (),
            "fallback_features": (),
            "approval_block_reasons": (),
        }
        return dataset.DatasetBuild(
            source="synthetic_cache_fixture",
            symbol="BTCUSDT",
            interval="1m",
            raw_rows=rows,
            canonical=[],
            gap_report=gap_report,
            feature_rows=feature_rows,
            labeled_rows=labeled_rows,
            feature_names=feature_names,
            label_horizon=5,
            label_threshold=0.001,
            source_availability_report=source_report,
        )

    def test_parquet_round_trip_preserves_rows(self) -> None:
        build = self._build_dataset()
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "dataset_cache.pkl"
            dataset.save_dataset_cache(cache_path, build)
            loaded = dataset.load_dataset_cache(cache_path)
        self.assertEqual(len(loaded.labeled_rows), len(build.labeled_rows))
        self.assertEqual(len(loaded.feature_rows), len(build.feature_rows))
        self.assertEqual(loaded.feature_names, build.feature_names)
        self.assertEqual(loaded.labeled_rows[0].features["return_1"], build.labeled_rows[0].features["return_1"])
        self.assertEqual(loaded.feature_rows[0].features["return_1"], build.feature_rows[0].features["return_1"])

    def test_parquet_missing_feature_fills_gracefully(self) -> None:
        build = self._build_dataset(feature_names=("return_1", "return_5"))
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "dataset_cache.pkl"
            dataset.save_dataset_cache(cache_path, build)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                loaded = dataset.load_dataset_cache(
                    cache_path,
                    expected_feature_names=["return_1", "return_5", "momentum_10"],
                    allow_missing_features=True,
                )
        self.assertEqual(loaded.labeled_rows[0].features["momentum_10"], 0.0)
        self.assertEqual(loaded.feature_rows[0].features["momentum_10"], 0.0)
        self.assertTrue(any("momentum_10" in str(warning.message) and "missing" in str(warning.message).lower() for warning in caught))

    def test_parquet_feature_count_mismatch_detected(self) -> None:
        build = self._build_dataset(feature_names=("return_1",))
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "dataset_cache.pkl"
            dataset.save_dataset_cache(cache_path, build)
            with self.assertRaises(ValueError):
                dataset.load_dataset_cache(
                    cache_path,
                    expected_feature_names=["return_1", "return_5"],
                    allow_missing_features=False,
                )

    def test_pkl_path_derives_parquet_cache_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "dataset_cache.pkl"
            cache_dir = dataset.dataset_cache_dir(cache_path)
        cache_dir_str = str(cache_dir).replace("\\", "/").rstrip("/")
        self.assertTrue(cache_dir_str.endswith(".parquet_cache"))


if __name__ == "__main__":
    unittest.main()
