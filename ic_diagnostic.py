#!/usr/bin/env python3
"""Feature Information Coefficient (IC) diagnostic.

Measures, WITHOUT training or backtesting, whether each feature has any
predictive relationship with future returns. This answers "is there a signal
here at all?" in minutes instead of the hours a full train+backtest cycle
takes.

Method: Spearman rank correlation between each feature's value at bar t and
the realized return from t to t+horizon, for several horizons. Spearman (not
Pearson) is used because it's robust to outliers and doesn't assume a linear
relationship — appropriate for noisy financial features.

|IC| around 0.02-0.05 is considered a weak-but-real signal in quant finance;
|IC| < 0.01 is indistinguishable from noise; |IC| > 0.1 is unusually strong
(worth double-checking for a labeling/look-ahead bug rather than celebrating).

This script:
  1. Loads candles from a Parquet/CSV file
  2. Computes features ONCE (build_feature_rows) -- optionally with metrics
  3. For several horizons, computes the realized forward return directly from
     candle closes (causal: only uses candles at or after t+horizon, which by
     construction lie in the future relative to t -- exactly what training
     labels also do, so this mirrors the actual prediction target)
  4. Computes Spearman IC per feature per horizon (overall, split by
     up/down/range regime if a regime file is given, and per chronological
     fold as mean +/- std so IC drift over time is visible)
  5. Runs leakage heuristics on every feature at the shortest horizon
     (see --fail-on-leak below): a feature is suspicious if it predicts the
     FUTURE return better than it "remembers" the comparable PAST return at
     high magnitude, or if its IC collapses when the feature is used one bar
     late (real alpha at 15m+ horizons survives a 1-minute delay; an
     off-by-one look-ahead does not)
  6. Ranks features by |IC|, flags dead (near-zero) and suspicious (too high)
     features, and writes a CSV

Usage:
    python ic_diagnostic.py --input artifacts/btcusdt_2020_2025.parquet \\
        --regime-file regimes.json --metrics-dir artifacts/metrics \\
        --output artifacts/ic_report

Runs in minutes: no CatBoost, no Optuna, no backtest simulation.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from btcusdt_quant import dataset


def _spearman_ic(x: list[float], y: list[float]) -> tuple[float, int]:
    """Spearman rank correlation between x and y, ignoring non-finite pairs.

    Implemented directly (no scipy dependency) as Pearson correlation of rank
    transforms, which is the standard equivalent. Returns (ic, n_used).
    """
    pairs = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    n = len(pairs)
    if n < 30:
        return (0.0, n)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rx = _rank(xs)
    ry = _rank(ys)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return (0.0, n)
    return (cov / denom, n)


def _rank(values: list[float]) -> list[float]:
    """Average ranks (1-indexed), tie-aware, O(n log n)."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _make_y_cache(values: list[float]) -> tuple[list[float], float, float] | None:
    """Precompute (ranks, mean_rank, rank_var_sum) for a constant y series.

    The forward/past return arrays are identical across all ~180 features, so
    ranking them once instead of per feature roughly halves the whole IC pass.
    Only valid when every value is finite (rank positions shift under the
    pairwise NaN filtering _spearman_ic applies); returns None otherwise so
    callers fall back to the exact path.
    """
    n = len(values)
    if n < 30:
        return None
    for v in values:
        if not math.isfinite(v):
            return None
    ranks = _rank(values)
    mean_rank = (n + 1) / 2.0  # rank sum is n(n+1)/2 even with tie-averaged ranks
    var_sum = sum((r - mean_rank) ** 2 for r in ranks)
    return (ranks, mean_rank, var_sum)


def _spearman_ic_cached(
    x: list[float], y: list[float], y_cache: tuple[list[float], float, float] | None
) -> tuple[float, int]:
    """_spearman_ic reusing precomputed ranks of a constant y series.

    Falls back to the exact pairwise-filtering path when the cache is absent
    or x contains non-finite values (cached y ranks are only valid for the
    full, unfiltered pairing).
    """
    n = len(x)
    if y_cache is None or n < 30:
        return _spearman_ic(x, y)
    for v in x:
        if not math.isfinite(v):
            return _spearman_ic(x, y)
    ry, mean_ry, var_y = y_cache
    rx = _rank(x)
    mean_rx = (n + 1) / 2.0
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return (0.0, n)
    return (cov / denom, n)


def _fold_ic_stats(
    x: list[float],
    y: list[float],
    n_folds: int,
    y_fold_caches: list[tuple[list[float], float, float] | None] | None = None,
) -> tuple[float, float, int]:
    """Per-fold Spearman IC over contiguous chronological chunks.

    Returns (mean, std, folds_used). Folds with fewer than 30 finite pairs are
    skipped rather than reported as IC=0, which would fake stability. std is
    population std over the used folds (0.0 when only one fold survives).
    """
    n = len(x)
    if n_folds < 2 or n < n_folds * 30:
        return (0.0, 0.0, 0)
    fold_ics: list[float] = []
    for k in range(n_folds):
        lo = k * n // n_folds
        hi = (k + 1) * n // n_folds
        cache = y_fold_caches[k] if y_fold_caches is not None else None
        ic, n_used = _spearman_ic_cached(x[lo:hi], y[lo:hi], cache)
        if n_used >= 30:
            fold_ics.append(ic)
    if not fold_ics:
        return (0.0, 0.0, 0)
    mean = sum(fold_ics) / len(fold_ics)
    var = sum((v - mean) ** 2 for v in fold_ics) / len(fold_ics)
    return (mean, var ** 0.5, len(fold_ics))


def _leak_flags(ic_now: float, ic_lag1: float, ic_past: float) -> list[str]:
    """Leakage heuristics for one feature at one horizon.

    "fwd>past": |IC| vs the future return exceeds 0.10 AND exceeds |IC| vs the
    same-length PAST return. A causal feature built from price history should
    correlate at least as strongly with the window it has already seen; the
    reverse asymmetry at high magnitude means the feature encodes future bars.

    "lag1-collapse": |IC| >= 0.05 but using the feature one bar late destroys
    more than half of it. Genuine predictive signal at >=15m horizons decays
    smoothly over minutes; a hard collapse from a single-bar delay is the
    signature of an off-by-one (same-bar future) leak.

    Both are heuristics for triage -- the gold-standard confirmation remains a
    truncation-invariance test (see verify_weekly_causality.py).
    """
    flags: list[str] = []
    if abs(ic_now) > 0.10 and abs(ic_now) > abs(ic_past):
        flags.append("fwd>past")
    if abs(ic_now) >= 0.05 and abs(ic_lag1) < 0.5 * abs(ic_now):
        flags.append("lag1-collapse")
    return flags


def _past_returns(candles: list, horizon: int) -> list[float]:
    """Causal backward return: (close[t] - close[t-horizon]) / close[t-horizon].

    The mirror image of _forward_returns, used only by the leakage heuristic
    to ask "does this feature predict the future better than it remembers the
    past?". Bars with no lookback get NaN.
    """
    n = len(candles)
    out = [float("nan")] * n
    for i in range(horizon, n):
        base = candles[i - horizon].close
        if base == 0.0:
            continue
        out[i] = (candles[i].close - base) / base
    return out


def _forward_returns(candles: list, horizon: int) -> list[float]:
    """Causal forward return: (close[t+horizon] - close[t]) / close[t].

    Bars within `horizon` of the end of the series get NaN (no future data
    available yet) -- they are excluded from IC, never filled with a guess.
    """
    n = len(candles)
    out = [float("nan")] * n
    for i in range(n - horizon):
        base = candles[i].close
        if base == 0.0:
            continue
        out[i] = (candles[i + horizon].close - base) / base
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="path to candle Parquet or CSV")
    parser.add_argument("--regime-file", default=None, help="optional regimes.json for per-regime IC breakdown")
    parser.add_argument("--metrics-dir", default=None, help="optional metrics archive dir (collect-metrics output)")
    parser.add_argument("--horizons", default="15,30,60,120,240", help="comma-separated horizons in minutes")
    parser.add_argument("--output", default="artifacts/ic_report", help="output directory for the CSV report")
    parser.add_argument("--sample", type=int, default=0, help="if >0, subsample to this many bars (evenly spaced) for a faster preview run")
    parser.add_argument("--ic-folds", type=int, default=5, help="number of chronological folds for fold-wise IC mean/std (0 disables)")
    parser.add_argument("--fail-on-leak", action="store_true", help="exit with code 2 if any feature trips a leakage heuristic (for CI use)")
    args = parser.parse_args()

    horizons = [int(h) for h in args.horizons.split(",") if h.strip()]
    input_path = Path(args.input)

    print(f"Loading candles from {input_path} ...")
    candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
    print(f"  {len(candles):,} candles loaded")

    if args.sample > 0 and len(candles) > args.sample:
        # Keep it a contiguous-enough series for forward-return computation:
        # subsampling by taking a contiguous recent slice is safer than
        # striding, since striding would break the t -> t+horizon adjacency
        # forward returns rely on. Use the most recent `sample` candles.
        candles = candles[-args.sample:]
        print(f"  using most recent {len(candles):,} candles (--sample)")

    user_regime_periods = None
    if args.regime_file:
        user_regime_periods = dataset.load_user_regime_periods(Path(args.regime_file))
        print(f"  loaded regime periods from {args.regime_file}")

    external_sources = None
    if args.metrics_dir:
        from btcusdt_quant import metrics_source
        print(f"Loading metrics from {args.metrics_dir} ...")
        metrics_rows = metrics_source.load_metrics_dir(Path(args.metrics_dir))
        minute_times = [c.open_time for c in candles]
        metrics_by_minute = metrics_source.metrics_features_to_minutes(metrics_rows, minute_times)
        external_sources = {t: {"metrics": feats} for t, feats in metrics_by_minute.items()}
        print(f"  {len(metrics_rows):,} metrics rows -> {len(metrics_by_minute):,} aligned minutes")

    print("Computing features (single pass) ...")
    feature_rows = dataset.build_feature_rows(candles, external_sources=external_sources, user_regime_periods=user_regime_periods)
    print(f"  {len(feature_rows):,} feature rows, {len(dataset.FEATURE_NAMES)} features")

    # Apply the same weekly-MA50 warmup exclusion training uses, so IC is
    # measured on the same population the model actually trains on.
    WEEKLY_WARMUP_BARS = 50 * 7 * 24 * 60
    start_index = 0
    if len(feature_rows) >= WEEKLY_WARMUP_BARS + 80:
        start_index = WEEKLY_WARMUP_BARS
        print(f"  excluding first {WEEKLY_WARMUP_BARS:,} bars (weekly MA50 warmup), matching training")

    max_horizon = max(horizons)
    end_index = len(feature_rows) - max_horizon  # leave room for the longest horizon's forward return
    if end_index <= start_index:
        print("Not enough data after warmup exclusion for the requested horizons.", file=sys.stderr)
        return 1

    rows = feature_rows[start_index:end_index + max_horizon]  # keep extra tail for forward_returns' own indexing
    used_candles = candles[start_index:end_index + max_horizon]
    n = end_index - start_index
    print(f"  IC computed over {n:,} bars (after warmup, minus tail reserved for horizons)")

    user_regimes = [row.user_regime for row in rows[:n]] if user_regime_periods else None

    print("\nComputing forward returns per horizon ...")
    fwd_by_horizon: dict[int, list[float]] = {}
    for h in horizons:
        fwd_by_horizon[h] = _forward_returns(used_candles, h)[:n]

    # Shortest horizon drives the leakage heuristics: it is the most sensitive
    # to a same-bar/off-by-one leak (the leaked bar is the largest fraction of
    # the target window there).
    h0 = min(horizons)
    past_h0 = _past_returns(used_candles, h0)[:n]

    # Everything on the y-side of the ICs is constant across features: rank it
    # once here instead of once per feature (see _make_y_cache). The head/tail
    # trims below reproduce exactly the pairs _spearman_ic's NaN filtering
    # kept: the lag-1 IC pairs feature[t-1] with fwd[t], the past IC drops the
    # first h0 bars that have no lookback return.
    fwd_cache = {h: _make_y_cache(fwd_by_horizon[h]) for h in horizons}
    fold_caches: dict[int, list[tuple[list[float], float, float] | None]] = {}
    if args.ic_folds >= 2:
        for h in horizons:
            y = fwd_by_horizon[h]
            fold_caches[h] = [
                _make_y_cache(y[k * n // args.ic_folds:(k + 1) * n // args.ic_folds])
                for k in range(args.ic_folds)
            ]
    fwd_h0_tail = fwd_by_horizon[h0][1:]
    fwd_h0_tail_cache = _make_y_cache(fwd_h0_tail)
    past_h0_trimmed = past_h0[h0:]
    past_cache = _make_y_cache(past_h0_trimmed)

    regime_indices: dict[str, list[int]] = {}
    regime_fwd: dict[tuple[int, str], list[float]] = {}
    regime_cache: dict[tuple[int, str], tuple[list[float], float, float] | None] = {}
    if user_regimes is not None:
        for regime_name in ("up", "down", "range"):
            regime_indices[regime_name] = [i for i in range(n) if user_regimes[i] == regime_name]
        for h in horizons:
            for regime_name, idx in regime_indices.items():
                if len(idx) >= 30:
                    fr = [fwd_by_horizon[h][i] for i in idx]
                    regime_fwd[(h, regime_name)] = fr
                    regime_cache[(h, regime_name)] = _make_y_cache(fr)

    feature_names = list(dataset.FEATURE_NAMES)
    print(f"\nComputing IC for {len(feature_names)} features x {len(horizons)} horizons ...")
    print("(this is O(features x horizons x n log n); may take a couple minutes for the full feature set)\n")

    results: list[dict[str, object]] = []
    for fi, fname in enumerate(feature_names):
        feature_values = [rows[i].features.get(fname, 0.0) for i in range(n)]
        row_result: dict[str, object] = {"feature": fname}
        for h in horizons:
            ic, n_used = _spearman_ic_cached(feature_values, fwd_by_horizon[h], fwd_cache[h])
            row_result[f"ic_{h}m"] = ic
            row_result[f"n_{h}m"] = n_used
            if args.ic_folds >= 2:
                fold_mean, fold_std, folds_used = _fold_ic_stats(feature_values, fwd_by_horizon[h], args.ic_folds, fold_caches.get(h))
                row_result[f"ic_{h}m_fold_mean"] = fold_mean
                row_result[f"ic_{h}m_fold_std"] = fold_std
                row_result[f"ic_{h}m_folds"] = folds_used
            if user_regimes is not None:
                for regime_name in ("up", "down", "range"):
                    idx = regime_indices[regime_name]
                    if len(idx) >= 30:
                        fv = [feature_values[i] for i in idx]
                        ic_r, _ = _spearman_ic_cached(fv, regime_fwd[(h, regime_name)], regime_cache[(h, regime_name)])
                        row_result[f"ic_{h}m_{regime_name}"] = ic_r
        # Leakage heuristics at the shortest horizon.
        ic_lag1, _ = _spearman_ic_cached(feature_values[:-1], fwd_h0_tail, fwd_h0_tail_cache)
        ic_past, _ = _spearman_ic_cached(feature_values[h0:], past_h0_trimmed, past_cache)
        ic_now = float(row_result.get(f"ic_{h0}m", 0.0))
        row_result[f"ic_{h0}m_lag1"] = ic_lag1
        row_result[f"ic_{h0}m_past"] = ic_past
        row_result["leak_flags"] = ";".join(_leak_flags(ic_now, ic_lag1, ic_past))
        results.append(row_result)
        if (fi + 1) % 20 == 0:
            print(f"  {fi + 1}/{len(feature_names)} features done")

    # Rank by max |IC| across horizons (the "does this feature have ANY signal"
    # question is answered by its best horizon, not necessarily the default 60m).
    def best_abs_ic(r: dict[str, object]) -> float:
        return max(abs(float(r.get(f"ic_{h}m", 0.0))) for h in horizons)

    results.sort(key=best_abs_ic, reverse=True)

    print("\n=== Top 15 features by |IC| (best horizon) ===")
    print(f"{'feature':<32} " + " ".join(f"ic_{h}m".rjust(9) for h in horizons))
    for r in results[:15]:
        vals = " ".join(f"{r.get(f'ic_{h}m', 0.0):+.4f}".rjust(9) for h in horizons)
        print(f"{r['feature']:<32} {vals}")

    print("\n=== Bottom 15 features by |IC| (likely dead / noise) ===")
    for r in results[-15:]:
        vals = " ".join(f"{r.get(f'ic_{h}m', 0.0):+.4f}".rjust(9) for h in horizons)
        print(f"{r['feature']:<32} {vals}")

    if args.ic_folds >= 2:
        # Fold stability at the horizon closest to the 60m default the models
        # actually train on (falls back to the first horizon when absent).
        ph = 60 if 60 in horizons else horizons[0]
        print(f"\n=== Fold-wise IC stability (top 15 by |IC|, {ph}m, {args.ic_folds} chronological folds) ===")
        print(f"{'feature':<32} {'ic':>9} {'fold_mean':>10} {'fold_std':>9}  note")
        for r in results[:15]:
            ic = float(r.get(f"ic_{ph}m", 0.0))
            fm = float(r.get(f"ic_{ph}m_fold_mean", 0.0))
            fs = float(r.get(f"ic_{ph}m_fold_std", 0.0))
            note = "UNSTABLE (std > |mean|)" if fs > abs(fm) else ""
            print(f"{r['feature']:<32} {ic:+9.4f} {fm:+10.4f} {fs:9.4f}  {note}")

    flagged = [r for r in results if r.get("leak_flags")]
    print(f"\n=== Leakage heuristics ({h0}m horizon) ===")
    if flagged:
        print(f"{'feature':<32} {'ic':>9} {'ic_lag1':>9} {'ic_past':>9}  flags")
        for r in flagged:
            print(
                f"{r['feature']:<32} {float(r.get(f'ic_{h0}m', 0.0)):+9.4f} "
                f"{float(r.get(f'ic_{h0}m_lag1', 0.0)):+9.4f} {float(r.get(f'ic_{h0}m_past', 0.0)):+9.4f}  {r['leak_flags']}"
            )
        print("  ^ heuristic triage only -- confirm with a truncation-invariance test (verify_weekly_causality.py pattern) before removing a feature")
    else:
        print("  no feature tripped the leakage heuristics")

    n_dead = sum(1 for r in results if best_abs_ic(r) < 0.01)
    n_weak = sum(1 for r in results if 0.01 <= best_abs_ic(r) < 0.03)
    n_signal = sum(1 for r in results if best_abs_ic(r) >= 0.03)
    n_suspicious = sum(1 for r in results if best_abs_ic(r) > 0.10)
    print("\n=== Summary ===")
    print(f"  dead (|IC|<0.01):        {n_dead}/{len(results)}")
    print(f"  weak (0.01<=|IC|<0.03):  {n_weak}/{len(results)}")
    print(f"  signal (|IC|>=0.03):     {n_signal}/{len(results)}")
    print(f"  suspicious (|IC|>0.10):  {n_suspicious}/{len(results)}  <- double-check these for look-ahead/leakage before trusting them")

    if user_regimes is not None:
        print("\n=== Metrics (F16) features: overall vs per-regime IC at 60m ===")
        from btcusdt_quant import sources as sources_mod
        metrics_only = [f for f in results if f["feature"] in getattr(sources_mod, "METRICS_FEATURES", ())]
        for r in metrics_only:
            up = r.get("ic_60m_up", float("nan"))
            down = r.get("ic_60m_down", float("nan"))
            rng = r.get("ic_60m_range", float("nan"))
            overall = r.get("ic_60m", float("nan"))
            print(f"  {r['feature']:<32} overall={overall:+.4f} up={up:+.4f} down={down:+.4f} range={rng:+.4f}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "ic_report.csv"
    fieldnames = ["feature"] + [f"ic_{h}m" for h in horizons] + [f"n_{h}m" for h in horizons]
    if args.ic_folds >= 2:
        for h in horizons:
            fieldnames.extend([f"ic_{h}m_fold_mean", f"ic_{h}m_fold_std", f"ic_{h}m_folds"])
    fieldnames.extend([f"ic_{h0}m_lag1", f"ic_{h0}m_past", "leak_flags"])
    if user_regimes is not None:
        for h in horizons:
            for regime_name in ("up", "down", "range"):
                fieldnames.append(f"ic_{h}m_{regime_name}")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"\nFull report written to {csv_path}")
    if args.fail_on_leak and flagged:
        print(f"\n--fail-on-leak: {len(flagged)} feature(s) tripped leakage heuristics", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
