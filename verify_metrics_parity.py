"""Verify F16 metrics train/backtest feature parity.

Builds a synthetic Binance-format metrics archive (daily CSV zips on a 5m
grid) plus 3 days of 1m candles, then checks:

1. NON-ZERO: with --metrics-dir-equivalent merging, F16 metrics features
   carry real (non-zero, varying) values after warmup.
2. ZERO-DEGRADE: without metrics, the same features are exactly 0.0 --
   i.e. the skew the v7 analysis warned about is real and this is what a
   metrics-trained model would silently receive from a metrics-less
   backtest.
3. TRAIN==BACKTEST: the shared cli.merge_metrics_external_sources helper
   (now used by BOTH dispatch paths) produces identical feature vectors for
   identical inputs -- same names, same values, every timestamp.
4. PARALLEL==SERIAL with metrics external_sources (chunk slicing keeps the
   ["metrics"] entries intact at chunk boundaries).
"""
from __future__ import annotations

import csv
import io
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from btcusdt_quant import data, dataset
from btcusdt_quant.cli import merge_metrics_external_sources
from btcusdt_quant.metrics_source import METRICS_FEATURE_NAMES

DAYS = 3
N = DAYS * 24 * 60  # 4,320 minute candles (serial path; parallel run uses 60k)
START = datetime(2024, 3, 4, tzinfo=timezone.utc)


def make_candles(n: int) -> list[data.Candle]:
    rng = np.random.default_rng(11)
    noise = rng.normal(0.0, 0.05, n)
    out = []
    for i in range(n):
        px = 100.0 + 3.0 * np.sin(i / 800.0) + noise[i]
        out.append(data.Candle(
            open_time=START + timedelta(minutes=i), open=px, high=px + 0.3,
            low=px - 0.3, close=px + 0.05, volume=10.0, quote_volume=1000.0,
            number_of_trades=100, taker_buy_base_volume=5.0,
            taker_buy_quote_volume=500.0, gap_flag=False, repaired=False))
    return out


def make_metrics_dir(tmp: Path, n_minutes: int) -> Path:
    """Daily zips of 5m-grid metrics CSVs in the archive schema."""
    mdir = tmp / "metrics"
    mdir.mkdir()
    header = ["create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
              "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
              "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]
    n_days = (n_minutes + 24 * 60 - 1) // (24 * 60)
    for d in range(n_days):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        for tick in range(288):  # 5m grid
            ts = START + timedelta(days=d, minutes=5 * tick)
            k = d * 288 + tick
            w.writerow([
                ts.strftime("%Y-%m-%d %H:%M:%S"), "BTCUSDT",
                f"{80000.0 + 50.0 * np.sin(k / 37.0):.3f}",
                f"{(80000.0 + 50.0 * np.sin(k / 37.0)) * 100.0:.3f}",
                f"{1.2 + 0.1 * np.sin(k / 11.0):.4f}",
                f"{1.5 + 0.2 * np.sin(k / 13.0):.4f}",
                f"{0.9 + 0.15 * np.sin(k / 17.0):.4f}",
                f"{1.1 + 0.25 * np.sin(k / 19.0):.4f}",
            ])
        zp = mdir / f"BTCUSDT-metrics-2024-03-{4 + d:02d}.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr(zp.stem + ".csv", buf.getvalue())
    return mdir


def main() -> int:
    candles = make_candles(N)
    with tempfile.TemporaryDirectory() as tmp:
        mdir = make_metrics_dir(Path(tmp), N)

        # Train-path and backtest-path both call THIS helper now.
        ext_train = merge_metrics_external_sources(mdir, candles, None)
        ext_backtest = merge_metrics_external_sources(mdir, candles, None)

        rows_with = dataset.build_feature_rows(candles, external_sources=ext_train, _parallel=False)
        rows_bt = dataset.build_feature_rows(candles, external_sources=ext_backtest, _parallel=False)
        rows_without = dataset.build_feature_rows(candles, _parallel=False)

        present = [n for n in METRICS_FEATURE_NAMES if n in rows_with[0].features]
        if not present:
            print("FAIL: no F16 metrics feature names found in feature rows")
            return 1

        # 1. non-zero after warmup (1d z-scores need 288 ticks; probe last day)
        probe = range(N - 24 * 60, N, 97)
        nz = {n: 0 for n in present}
        for i in probe:
            for n in present:
                if float(rows_with[i].features[n]) != 0.0:
                    nz[n] += 1
        dead = [n for n, c in nz.items() if c == 0]
        if dead:
            print(f"FAIL: metrics features all-zero WITH metrics dir: {dead}")
            return 1
        print(f"OK  1) {len(present)} F16 features carry non-zero values with metrics")

        # 2. exactly zero without metrics (the skew a metrics-less backtest feeds)
        for i in probe:
            for n in present:
                v = float(rows_without[i].features[n])
                if v != 0.0:
                    print(f"FAIL: {n} nonzero WITHOUT metrics at bar {i}: {v}")
                    return 1
        print("OK  2) same features degrade to exactly 0.0 without metrics (skew confirmed real)")

        # 3. train-path vs backtest-path identical vectors (names + values)
        names = list(rows_with[0].features.keys())
        if names != list(rows_bt[0].features.keys()):
            print("FAIL: feature name order differs between paths")
            return 1
        for i in range(0, N, 53):
            a, b = rows_with[i].features, rows_bt[i].features
            for n in names:
                va, vb = float(a[n]), float(b[n])
                if va != vb and not (va != va and vb != vb):
                    print(f"FAIL: train/backtest vector differs at bar {i} feature {n}: {va} vs {vb}")
                    return 1
        print("OK  3) train-path and backtest-path feature vectors identical (shared merge helper)")

    # 4. parallel==serial with metrics external (chunked slicing keeps entries)
    big = make_candles(60_000)
    with tempfile.TemporaryDirectory() as tmp:
        mdir = make_metrics_dir(Path(tmp), 60_000)
        ext = merge_metrics_external_sources(mdir, big, None)
        dataset.os.cpu_count = lambda: 8  # 6 chunks of 10k
        par = dataset.build_feature_rows(big, external_sources=ext, _parallel=True)
        ser = dataset.build_feature_rows(big, external_sources=ext, _parallel=False)
        for i in (0, 9_999, 10_000, 25_000, 49_999, 59_999):
            for n in present:
                va, vb = float(par[i].features[n]), float(ser[i].features[n])
                if va != vb:
                    print(f"FAIL: parallel/serial metrics feature differs at bar {i} {n}: {va} vs {vb}")
                    return 1
        print("OK  4) parallel(sliced) == serial metrics features incl. chunk boundaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
