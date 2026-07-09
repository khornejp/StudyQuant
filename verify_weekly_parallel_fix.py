"""Verify the parallel weekly-feature fix.

Strategy: monkeypatch weekly_features.compute_weekly_features IN THE PARENT
process to return the GLOBAL row index as every weekly feature value. With
the fix, workers never call compute_weekly_features themselves (they receive
pre-sliced arrays from the parent), so every produced FeatureRow must carry
weekly values equal to its GLOBAL index. Before the fix, each worker
recomputed weekly features on its own chunk (unpatched in the worker), which
for short chunks returns all zeros -- and even under the patch would have
returned CHUNK-LOCAL indices, mismatching the global index for chunks > 0.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from btcusdt_quant import data, dataset, weekly_features

N = 60_000  # > 50k triggers the parallel path; chunk_size floors at 10k -> 6 chunks


def fake_weekly(candles):
    n = len(candles)
    # Parent computes over the FULL series, so values == global index.
    base = [i / 1e6 for i in range(n)]  # small values avoid the feature clipper
    return {
        "weekly_ma20_slope_closed": base,
        "weekly_ma50_slope_closed": base,
        "weekly_ma20_above_ma50": base,
        "weekly_drawdown": base,
        "weekly_vol_contraction": base,
        "close_vs_weekly_ma20": base,
        "close_vs_weekly_ma50": base,
    }


def main() -> int:
    weekly_features.compute_weekly_features = fake_weekly  # parent-only patch
    dataset.weekly_features.compute_weekly_features = fake_weekly
    dataset.os.cpu_count = lambda: 8  # force multi-chunk split (6 chunks of 10k)

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = [
        data.Candle(
            open_time=start + timedelta(minutes=i),
            open=100.0 + 0.001 * i,
            high=100.5 + 0.001 * i,
            low=99.5 + 0.001 * i,
            close=100.1 + 0.001 * i,
            volume=10.0,
            quote_volume=1000.0,
            number_of_trades=100,
            taker_buy_base_volume=5.0,
            taker_buy_quote_volume=500.0,
            gap_flag=False,
            repaired=False,
        )
        for i in range(N)
    ]

    rows = dataset.build_feature_rows(candles, _parallel=True)
    assert len(rows) == N, f"expected {N} rows, got {len(rows)}"

    checked = 0
    bad = []
    for row in rows[:: max(1, N // 500)]:  # sample ~500 rows across all chunks
        v = float(row.features["weekly_drawdown"])
        if abs(v - row.index / 1e6) > 1e-4:  # float32 rounding tolerance
            bad.append((row.index, v))
        checked += 1
    # Also explicitly check rows deep inside later chunks (index > 10k, 20k, 50k)
    for idx in (0, 9_999, 10_000, 25_000, 49_999, 59_999):
        v = float(rows[idx].features["close_vs_weekly_ma50"])
        if abs(v - idx / 1e6) > 1e-4:
            bad.append((idx, v))
        checked += 1

    if bad:
        print(f"FAIL: {len(bad)} misaligned weekly values (global-index mismatch): {bad[:10]}")
        return 1
    print(f"OK: {checked} sampled rows all carry GLOBAL-index-aligned weekly features across parallel chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
