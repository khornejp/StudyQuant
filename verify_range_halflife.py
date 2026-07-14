#!/usr/bin/env python3
"""Measure the Ornstein-Uhlenbeck half-life of mean reversion in range regimes.

The range-regime pipeline assumes a FIXED 20-bar mean-reversion window
everywhere: range_position_20 / bb_zscore / vwap_deviation_zscore in
feature_registry.py, and apply_range_mean_reversion_gate in backtest.py /
live.py. That 20 was never calibrated against the data -- this script
measures the actual speed of mean reversion so the window can be justified
or corrected.

Method (Chan, Quantitative Trading 2ed, Example 7.5): fit the OU
discretization dz[t] = theta * (z[t-1] - mean) + noise by OLS. theta < 0
means the series pulls back toward its mean, and the half-life of a
deviation is -ln(2)/theta bars. A rolling z-score window is well matched
when it spans roughly 1-3 half-lives: much shorter and the "mean" it
reverts to is noise, much longer and the gate reacts too slowly.

For each range period in regimes.json (and, as a contrast baseline, each
up/down period) the script reports the half-life of the close series, then
compares the range-regime median against the fixed 20-bar assumption.

Usage:
    python verify_range_halflife.py --input artifacts/btcusdt_2020_2025.parquet \\
        --regime-file regimes.json [--window-bars 20]

Diagnostic only: exit code 0 with a report, 1 on unusable input. It does not
fail on a mismatched window -- read the recommendation and decide.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from btcusdt_quant import dataset


def estimate_ou_halflife(values: list[float]) -> float:
    """OU half-life in bars via OLS of dz on demeaned lagged z.

    Returns +inf when the series does not mean-revert (theta >= 0) and NaN
    when there are too few points for a meaningful fit.
    """
    z = [v for v in values if math.isfinite(v)]
    n = len(z)
    if n < 60:
        return float("nan")
    prevz = z[:-1]
    dz = [z[i + 1] - z[i] for i in range(n - 1)]
    mean_prev = sum(prevz) / len(prevz)
    x = [v - mean_prev for v in prevz]
    denom = sum(v * v for v in x)
    if denom == 0.0:
        return float("nan")
    theta = sum(a * b for a, b in zip(x, dz)) / denom
    if theta >= 0.0:
        return float("inf")
    return -math.log(2.0) / theta


def build_series(closes: list[float], kind: str, window: int = 60) -> list[float]:
    """Return the series the OU model is fitted to.

    A raw BTC price series has a large drift and time-varying volatility, so
    an OU fit on it mostly measures the trend, not the mean reversion the
    range gate cares about. The two derived series remove the drift by
    referencing a rolling local mean, which is what range_position_20 /
    vwap_deviation_zscore effectively do. Bars before the window fills are
    NaN so estimate_ou_halflife skips them.

    `window` is the DETREND window and must stay independent of the window
    under test: a rolling z-score of width W mechanically mean-reverts on a
    ~W scale, so detrending with the very window you are validating would
    manufacture the answer. Non-positive closes are treated as missing in
    both branches rather than poisoning the rolling statistics.
    """
    n = len(closes)
    if kind == "close":
        return list(closes)
    if window < 2:
        raise ValueError("detrend window must be >= 2")
    out = [float("nan")] * n
    if kind == "vwap_deviation":
        # Rolling sum over the last `window` VALID closes; a non-positive
        # close contributes nothing and is not counted, mirroring log_zscore.
        running = 0.0
        count = 0
        for i, px in enumerate(closes):
            if px > 0.0:
                running += px
                count += 1
            if i >= window:
                old = closes[i - window]
                if old > 0.0:
                    running -= old
                    count -= 1
            if i >= window - 1 and count > 0 and px > 0.0:
                mean = running / count
                if mean != 0.0:
                    out[i] = px / mean - 1.0
        return out
    if kind == "log_zscore":
        # Rolling mean/variance via running sums (O(n)), matching the
        # vwap_deviation branch instead of re-summing the window per bar.
        logs = [math.log(px) if px > 0.0 else float("nan") for px in closes]
        s = 0.0
        s2 = 0.0
        count = 0
        for i, v in enumerate(logs):
            if math.isfinite(v):
                s += v
                s2 += v * v
                count += 1
            if i >= window:
                old = logs[i - window]
                if math.isfinite(old):
                    s -= old
                    s2 -= old * old
                    count -= 1
            if i >= window - 1 and count >= 2 and math.isfinite(v):
                mean = s / count
                var = s2 / count - mean * mean
                if var > 0.0:
                    out[i] = (v - mean) / math.sqrt(var)
        return out
    raise ValueError(f"unsupported series: {kind}")


def _fmt_halflife(hl: float) -> str:
    if math.isnan(hl):
        return "n/a (too short)"
    if math.isinf(hl):
        return "no mean reversion"
    return f"{hl:,.1f} bars"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="path to candle Parquet or CSV")
    parser.add_argument("--regime-file", default=None, help="regimes.json; without it only the full-series half-life is reported")
    parser.add_argument("--window-bars", type=int, default=20, help="the fixed rolling window under test (default 20, matching range_position_20)")
    parser.add_argument(
        "--series",
        default="close",
        choices=["close", "vwap_deviation", "log_zscore"],
        help=(
            "series the OU model is fitted to. 'close' (default) is the raw price -- BTC's drift and "
            "heteroskedasticity make a raw-price OU fit unstable, so treat it as a reference point. "
            "'vwap_deviation' (close/rolling_vwap_60 - 1) and 'log_zscore' (rolling z-score of log price) "
            "are drift-removed and scale-free, and are the series the range gate actually reasons about."
        ),
    )
    parser.add_argument(
        "--detrend-window",
        type=int,
        default=60,
        help=(
            "rolling window used to remove drift for --series vwap_deviation / log_zscore (default 60). "
            "Deliberately INDEPENDENT of --window-bars: a rolling z-score of width W mean-reverts on a ~W "
            "scale by construction, so detrending with the window under test would manufacture the verdict. "
            "Keep it comfortably longer than --window-bars."
        ),
    )
    args = parser.parse_args()
    if args.window_bars <= 0:
        print("--window-bars must be a positive integer", file=sys.stderr)
        return 1
    if args.detrend_window < 2:
        print("--detrend-window must be >= 2", file=sys.stderr)
        return 1
    if args.series != "close" and args.detrend_window <= args.window_bars:
        print(
            f"--detrend-window ({args.detrend_window}) must exceed --window-bars ({args.window_bars}): "
            "detrending with the window under test makes the half-life an artifact of that window",
            file=sys.stderr,
        )
        return 1

    input_path = Path(args.input)
    print(f"Loading candles from {input_path} ...")
    candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
    print(f"  {len(candles):,} candles loaded")
    if len(candles) < 60:
        print("Not enough candles for a half-life estimate.", file=sys.stderr)
        return 1

    closes = [c.close for c in candles]
    times = [c.open_time for c in candles]
    series = build_series(closes, args.series, args.detrend_window)
    print(f"\nSeries under test: {args.series}" + ("" if args.series == "close" else f" (detrend window {args.detrend_window} bars)"))
    if args.series == "close":
        print("  (raw price: drift and heteroskedasticity make this fit unstable -- rerun with")
        print("   --series vwap_deviation or --series log_zscore before retuning the window)")
    print(f"Full series half-life: {_fmt_halflife(estimate_ou_halflife(series))}")
    print("(expected to be huge or 'no mean reversion' on raw close -- BTC trends over multi-year windows;")
    print(" the question is whether RANGE periods revert on a scale near the fixed window)")

    if not args.regime_file:
        print("\nNo --regime-file given; cannot break down by regime. Done.")
        return 0

    periods = dataset.load_user_regime_periods(Path(args.regime_file))
    print(f"\nLoaded {len(periods)} regime periods from {args.regime_file}")

    range_halflives: list[float] = []
    print(f"\n{'regime':<7} {'start':<12} {'end_excl':<12} {'bars':>10} {'half-life':>22}")
    for period in periods:
        # The derived series is built over the FULL history, so slicing it by
        # period keeps each bar's rolling reference intact (causal, no leak).
        segment = [series[i] for i in range(len(series)) if period.start <= times[i] < period.end_exclusive]
        hl = estimate_ou_halflife(segment)
        print(f"{period.regime:<7} {period.start:%Y-%m-%d}   {period.end_exclusive:%Y-%m-%d}   {len(segment):>10,} {_fmt_halflife(hl):>22}")
        if period.regime == "range" and math.isfinite(hl):
            range_halflives.append(hl)

    print(f"\n=== Range-regime verdict (fixed window under test: {args.window_bars} bars) ===")
    if not range_halflives:
        print("  no range period produced a finite half-life: either the regime file has no")
        print("  range periods overlapping this candle window, or 'range' periods do not")
        print("  actually mean-revert -- in which case the mean-reversion gate itself is suspect.")
        return 0

    range_halflives.sort()
    median_hl = range_halflives[len(range_halflives) // 2]
    ratio = median_hl / args.window_bars
    print(f"  finite range-period half-lives: {len(range_halflives)}")
    print(f"  median: {median_hl:,.1f} bars  |  min: {range_halflives[0]:,.1f}  |  max: {range_halflives[-1]:,.1f}")
    print(f"  median / window = {ratio:,.2f}")
    if 1.0 <= ratio <= 3.0:
        print(f"  OK: the {args.window_bars}-bar window spans ~1-3 half-lives of the measured reversion; the fixed window is defensible.")
    elif ratio < 1.0:
        print(f"  MISMATCH: reversion is FASTER than the window (half-life < {args.window_bars} bars).")
        print(f"  The gate reacts too slowly; consider a window near {max(2, round(median_hl)):d}-{max(3, round(3 * median_hl)):d} bars.")
    else:
        print(f"  MISMATCH: reversion is SLOWER than the window (half-life ~{median_hl:,.0f} bars).")
        print(f"  A {args.window_bars}-bar z-score reverts to local noise, not the range mean; consider a window near {round(median_hl):d}-{round(3 * median_hl):d} bars,")
        print("  and TP/SL timeouts in range trades should allow at least one half-life to elapse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
