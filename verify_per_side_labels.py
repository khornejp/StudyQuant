"""Independently recompute per-side triple-barrier labels and compare.

The pipeline's own labeller is not used as its own witness: this script reads
the raw OHLC candles and re-derives ``long_success``, ``short_success`` and
``short_profitability`` from the published contract --

    entry price = close of bar t
    scan bars t+1 .. t+horizon inclusive
    long  TP: high >= close*(1+tp)   SL: low  <= close*(1-sl)
    short TP: low  <= close*(1-tp)   SL: high >= close*(1+sl)
    both touched in one bar -> the bar's own direction decides
    no touch -> timeout (0 for *_success; short_profitability settles on the
    horizon return against label_threshold)

-- then compares row by row against what ``build_dataset`` produced with
per-side geometry. A disagreement means the labels the model would be fitted
on are not the labels the geometry implies.

Usage:
    python verify_per_side_labels.py --input artifacts/btcusdt_2020_2026h1.parquet \
        --start 2025-01-01 --end 2025-01-08 --horizon 45 \
        --long-tp 0.004 --long-sl 0.002 --short-tp 0.006 --short-sl 0.012
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from btcusdt_quant import dataset


def independent_labels(
    highs: list[float],
    lows: list[float],
    opens: list[float],
    closes: list[float],
    index: int,
    horizon: int,
    tp_pct: float,
    sl_pct: float,
    side: str,
) -> tuple[int, str]:
    entry = closes[index]
    if side == "long":
        tp_level, sl_level = entry * (1.0 + tp_pct), entry * (1.0 - sl_pct)
    else:
        tp_level, sl_level = entry * (1.0 - tp_pct), entry * (1.0 + sl_pct)
    for j in range(index + 1, index + horizon + 1):
        if side == "long":
            tp_touched, sl_touched = highs[j] >= tp_level, lows[j] <= sl_level
            tp_wins_tie = closes[j] > opens[j]
        else:
            tp_touched, sl_touched = lows[j] <= tp_level, highs[j] >= sl_level
            tp_wins_tie = closes[j] < opens[j]
        if tp_touched and sl_touched:
            return (1, f"{side}_tp_first") if tp_wins_tie else (0, f"{side}_sl_first")
        if tp_touched:
            return 1, f"{side}_tp_first"
        if sl_touched:
            return 0, f"{side}_sl_first"
    return 0, f"{side}_timeout"


def contract_boundary_probes(args: argparse.Namespace) -> tuple[int, list[str]]:
    """Exercise contract edges absent from a particular market window.

    These cases deliberately go through ``attach_labels`` (the production
    integration surface), while their expected values are fixed directly from
    the public OHLC contract.  They never call a triple-barrier function as an
    oracle.
    """
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def candle(offset: int, open_: float, high: float, low: float, close: float) -> dataset.data.Candle:
        return dataset.data.Candle(
            open_time=base + timedelta(minutes=offset), open=open_, high=high, low=low, close=close,
            volume=1.0, quote_volume=100.0, number_of_trades=1,
            taker_buy_base_volume=0.5, taker_buy_quote_volume=50.0,
        )

    def row(c: dataset.data.Candle) -> dataset.FeatureRow:
        return dataset.FeatureRow(0, c.open_time, {}, 0, False, False)

    # exact TP requires >=; bullish dual touch gives TP priority; entry is close.
    cases = [
        ("long_exact_tp", [candle(0, 100, 100, 100, 100), candle(1, 100, 100.4, 100, 100.2)], 0.004, 0.002),
        ("long_bullish_dual_touch", [candle(0, 100, 100, 100, 100), candle(1, 99, 101, 99, 101)], 0.01, 0.01),
        ("long_close_entry", [candle(0, 101, 101, 100, 100), candle(1, 100, 100.5, 99.9, 100.2)], 0.004, 0.002),
    ]
    failures: list[str] = []
    for name, candles, long_tp, long_sl in cases:
        labeled = dataset.attach_labels(
            [row(candles[0])], candles, 1, args.label_threshold,
            long_tp_pct=long_tp, long_sl_pct=long_sl,
            short_tp_pct=args.short_tp, short_sl_pct=args.short_sl,
        )
        actual = labeled[0].targets["long_success"] if labeled else None
        if actual != 1:
            failures.append(f"{name}: pipeline={actual} independent=1")
    return len(failures), failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--horizon", type=int, default=45)
    parser.add_argument("--label-threshold", type=float, default=0.0004)
    parser.add_argument("--long-tp", type=float, required=True)
    parser.add_argument("--long-sl", type=float, required=True)
    parser.add_argument("--short-tp", type=float, required=True)
    parser.add_argument("--short-sl", type=float, required=True)
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    candles = [c for c in dataset.load_parquet_candles(args.input) if start <= c.open_time < end]
    print(f"candles in window: {len(candles):,}")

    build = dataset.build_dataset(
        stream_buffer=candles,
        horizon=args.horizon,
        label_threshold=args.label_threshold,
        long_tp_pct=args.long_tp,
        long_sl_pct=args.long_sl,
        short_tp_pct=args.short_tp,
        short_sl_pct=args.short_sl,
    )
    rows = build.labeled_rows
    # row.index addresses the CANONICAL series (post gap-repair), so the
    # independent recomputation must read the same series or the comparison
    # comes apart on repaired bars.
    canonical = build.canonical
    repaired = sum(1 for c in canonical if getattr(c, "repaired", False))
    print(f"labeled rows: {len(rows):,}  canonical candles: {len(canonical):,}"
          f"  repaired: {repaired:,}")

    highs = [c.high for c in canonical]
    lows = [c.low for c in canonical]
    opens = [c.open for c in canonical]
    closes = [c.close for c in canonical]

    mismatches: dict[str, int] = {"long_success": 0, "short_success": 0, "short_profitability": 0}
    reason_mismatches: dict[str, int] = {
        "long_success": 0, "short_success": 0, "short_profitability": 0,
    }
    first_examples: dict[str, str] = {}
    # Cross-check: would the OTHER side's geometry have produced this label?
    long_under_short_geometry = 0

    for row in rows:
        i = row.index
        if i + args.horizon >= len(canonical):
            continue
        exp_long, exp_long_reason = independent_labels(
            highs, lows, opens, closes, i, args.horizon, args.long_tp, args.long_sl, "long")
        exp_short, exp_short_reason = independent_labels(
            highs, lows, opens, closes, i, args.horizon, args.short_tp, args.short_sl, "short")

        if row.targets["long_success"] != exp_long:
            mismatches["long_success"] += 1
            first_examples.setdefault(
                "long_success",
                f"index {i} {canonical[i].open_time.isoformat()}: pipeline={row.targets['long_success']}"
                f" independent={exp_long} ({exp_long_reason})")
        elif row.target_reasons["long_success"] != exp_long_reason:
            reason_mismatches["long_success"] += 1
            first_examples.setdefault(
                "long_reason",
                f"index {i}: pipeline reason={row.target_reasons['long_success']} independent={exp_long_reason}")

        if row.targets["short_success"] != exp_short:
            mismatches["short_success"] += 1
            first_examples.setdefault(
                "short_success",
                f"index {i} {canonical[i].open_time.isoformat()}: pipeline={row.targets['short_success']}"
                f" independent={exp_short} ({exp_short_reason})")
        elif row.target_reasons["short_success"] != exp_short_reason:
            reason_mismatches["short_success"] += 1
            first_examples.setdefault(
                "short_reason",
                f"index {i}: pipeline reason={row.target_reasons['short_success']} independent={exp_short_reason}")

        target_return = (closes[i + args.horizon] - closes[i]) / closes[i]
        if exp_short_reason == f"short_timeout":
            exp_profit = 1 if -target_return > args.label_threshold else 0
        else:
            exp_profit = exp_short
        if row.targets["short_profitability"] != exp_profit:
            mismatches["short_profitability"] += 1
            first_examples.setdefault(
                "short_profitability",
                f"index {i}: pipeline={row.targets['short_profitability']} independent={exp_profit}")
        else:
            exp_profit_reason = "short_timeout_return" if exp_short_reason == "short_timeout" else exp_short_reason
            if row.target_reasons["short_profitability"] != exp_profit_reason:
                reason_mismatches["short_profitability"] += 1
                first_examples.setdefault(
                    "short_profitability_reason",
                    f"index {i}: pipeline reason={row.target_reasons['short_profitability']}"
                    f" independent={exp_profit_reason}")

        # If the long label were computed on SHORT geometry it would differ on
        # some rows; count how many, so "the sides share a barrier" cannot pass
        # unnoticed.
        alt_long, _ = independent_labels(
            highs, lows, opens, closes, i, args.horizon, args.short_tp, args.short_sl, "long")
        if alt_long != exp_long:
            long_under_short_geometry += 1

    checked = sum(1 for row in rows if row.index + args.horizon < len(canonical))
    print(f"\nrows checked: {checked:,}")
    for name, count in mismatches.items():
        print(f"  {name}: {count} label mismatches")
    for name, count in reason_mismatches.items():
        print(f"  {name}: {count} reason mismatches (label agreed)")
    print(f"  rows where long geometry vs short geometry disagree: {long_under_short_geometry:,}"
          f" ({long_under_short_geometry / checked:.1%} of checked)"
          if checked else "  no rows checked")
    for key, example in first_examples.items():
        print(f"  first {key}: {example}")

    probe_failures, probe_examples = contract_boundary_probes(args)
    print(f"  contract boundary probes: {probe_failures} label mismatches (of 3)")
    for example in probe_examples:
        print(f"  first contract probe: {example}")

    failed = any(mismatches.values()) or any(reason_mismatches.values()) or probe_failures > 0
    if checked and long_under_short_geometry == 0:
        print("\nWARNING: the two geometries never disagree on this window; the per-side"
              " wiring is untested here even though every label matched.")
    print("\nRESULT:", "MISMATCH" if failed else "labels match the geometry contract")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
