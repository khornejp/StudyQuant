#!/usr/bin/env python3
"""Validate the metrics archive downloader + dedup + 1m alignment on REAL data.

Run this in your environment (which has network) BEFORE we build metrics
features. It downloads a few days of BTCUSDT metrics, inspects the raw schema,
counts create_time duplicates, and shows the 5m -> 1m as-of alignment so you
can confirm the assumptions hold on actual Binance data.

Usage:
    python validate_metrics.py 2020-09-01 2020-09-03
    python validate_metrics.py 2024-01-01 2024-01-02
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from btcusdt_quant import metrics_source as ms


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python validate_metrics.py START_DATE END_DATE (YYYY-MM-DD)")
        return 1
    start, end = sys.argv[1], sys.argv[2]
    out_dir = Path("artifacts/metrics_validation")

    print(f"Downloading BTCUSDT metrics {start} -> {end} ...")
    downloader = ms.BinanceMetricsDownloader()
    rows = downloader.download_range(start, end, out_dir)
    print(f"  got {len(rows):,} deduped rows\n")

    if not rows:
        print("No rows. Either the range predates metrics (~2020-09) or a network issue.")
        return 1

    # 1. Schema / value sanity
    print("=== First 3 rows ===")
    for r in rows[:3]:
        print(f"  {r.create_time.isoformat()}  {r.values}")

    # 2. Observation cadence (should be ~5 minutes)
    print("\n=== Cadence (gaps between consecutive create_times) ===")
    from collections import Counter
    gaps = Counter()
    for a, b in zip(rows, rows[1:]):
        secs = int((b.create_time - a.create_time).total_seconds())
        gaps[secs] += 1
    for secs, n in sorted(gaps.items())[:8]:
        print(f"  {secs}s ({secs//60}m): {n} times")

    # 3. Duplicate detection on RAW (pre-dedup) data from the files on disk
    raw = []
    import zipfile, io
    for zp in sorted(out_dir.glob("*.zip")):
        try:
            with zipfile.ZipFile(io.BytesIO(zp.read_bytes())) as z:
                name = [x for x in z.namelist() if x.endswith(".csv")][0]
                raw.extend(ms.parse_metrics_csv_text(z.read(name).decode("utf-8")))
        except Exception as e:
            print(f"  (skip {zp.name}: {e})")
    from collections import Counter as C
    ct_counts = C(r.create_time for r in raw)
    dups = {t: c for t, c in ct_counts.items() if c > 1}
    print(f"\n=== Duplicate create_time (raw, pre-dedup) ===")
    print(f"  raw rows: {len(raw):,}, unique create_time: {len(ct_counts):,}, duplicated timestamps: {len(dups):,}")
    for t, c in list(dups.items())[:3]:
        same = [r.values for r in raw if r.create_time == t]
        identical = all(v == same[0] for v in same)
        print(f"    {t.isoformat()} x{c}  values_identical={identical}")

    # 4. 5m -> 1m alignment preview (first hour)
    print("\n=== 5m -> 1m as-of alignment (first ~15 minutes) ===")
    t0 = rows[0].create_time.replace(second=0, microsecond=0)
    minutes = [t0 + timedelta(minutes=i) for i in range(15)]
    aligned = ms.align_metrics_to_minutes(rows, minutes)
    for m in minutes:
        oi = aligned.get(m, {}).get("sum_open_interest", "<none>")
        print(f"    {m.strftime('%Y-%m-%d %H:%M')}  OI={oi}")

    # 5. Derived features preview (change-rates + z-scores)
    print("\n=== Derived features (5m grid, first few ticks) ===")
    feats = ms.compute_metrics_features(rows)
    grid = sorted(feats)[:8]
    for t in grid:
        f = feats[t]
        print(f"    {t.strftime('%H:%M')}  oi_chg5m={f['oi_change_rate_5m']:+.5f} "
              f"oi_chg30m={f['oi_change_rate_30m']:+.5f} oi_z={f['oi_zscore_1d']:+.2f} "
              f"tt_ls={f['toptrader_ls_account']:.3f} taker={f['taker_ls_ratio']:.3f}")
    print(f"\n  emits {len(ms.METRICS_FEATURE_NAMES)} features: {', '.join(ms.METRICS_FEATURE_NAMES)}")

    print("\nOK. If cadence is ~300s, duplicates share identical create_time, and")
    print("the 1m alignment holds each 5m value for 5 bars, the utils are correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
