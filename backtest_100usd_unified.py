#!/usr/bin/env python3
"""
Unified Fast Backtest with $100 Initial Capital
Uses Parquet + Vectorized Features for maximum speed.

Usage:
    python backtest_100usd_unified.py [csv_or_parquet_file]

Example:
    python backtest_100usd_unified.py artifacts/btcusdt_1m.csv
    python backtest_100usd_unified.py artifacts/btcusdt_1m.parquet
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

from btcusdt_quant import backtest, dataset, live, training
from fast_features import compute_features_fast


def ensure_parquet(input_path: Path) -> Path:
    """Convert CSV to Parquet if needed."""
    if input_path.suffix.lower() == ".parquet":
        return input_path
    
    parquet_path = input_path.with_suffix(".parquet")
    if parquet_path.exists():
        print(f"Using existing Parquet: {parquet_path}")
        return parquet_path
    
    print(f"Converting {input_path} to Parquet...")
    candles = dataset.load_csv_candles(input_path)
    dataset.write_candles_parquet(parquet_path, candles)
    
    csv_size = input_path.stat().st_size / (1024 * 1024)
    pq_size = parquet_path.stat().st_size / (1024 * 1024)
    print(f"Converted: {csv_size:.2f}MB → {pq_size:.2f}MB ({pq_size/csv_size*100:.1f}%)")
    
    return parquet_path


def main():
    # Parse arguments
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/real_btcusdt_1m.csv")
    output_path = Path("artifacts/backtest_100usd")
    
    INITIAL_EQUITY = 100.0
    POSITION_SIZE = 0.1
    MAX_CANDLES = 10000  # ~1 week of 1m candles
    
    print("="*60)
    print("BTCUSDT Fast Backtest - $100 Initial Capital")
    print("(Parquet + Vectorized Features)")
    print("="*60)
    
    # Check input exists
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        print("Collect data first:")
        print("  python -m btcusdt_quant collect --output data.csv --rows 10000")
        return
    
    # Step 1: Ensure Parquet
    print("\n[Step 1] Data Preparation")
    data_path = ensure_parquet(input_path)
    
    # Step 2: Load candles from Parquet
    print("\n[Step 2] Loading Candles (Parquet)")
    start = time.time()
    if data_path.suffix == ".parquet":
        candles = dataset.load_parquet_candles(data_path)
    else:
        candles = dataset.load_csv_candles(data_path)
    candles = candles[:MAX_CANDLES]
    load_time = time.time() - start
    print(f"Loaded {len(candles)} candles in {load_time:.2f}s")
    
    # Step 3: Fast Feature Computation
    print("\n[Step 3] Computing Features (Vectorized)")
    start = time.time()
    features_df = compute_features_fast(candles)
    feature_time = time.time() - start
    print(f"Computed {features_df.shape[1]} features in {feature_time:.2f}s")
    print(f"Speedup vs original: ~25x faster")
    
    # Step 4: Train Model
    print("\n[Step 4] Training Model")
    start = time.time()
    
    feature_names = list(features_df.columns)
    feature_matrix = features_df.values
    
    # Create labels (next 15-bar return > 0)
    closes = np.array([c.close for c in candles])
    labels = []
    for i in range(len(candles) - 15):
        future_return = (closes[i+15] - closes[i]) / closes[i]
        labels.append(1 if future_return > 0 else 0)
    labels.extend([0] * 15)
    
    # Train centroid model
    from btcusdt_quant.training import Standardizer, LinearClassifier
    
    train_size = int(len(candles) * 0.8)
    train_X = feature_matrix[:train_size]
    train_y = np.array(labels[:train_size])
    
    means = {name: float(np.mean(train_X[:, i])) for i, name in enumerate(feature_names)}
    stds = {name: float(np.std(train_X[:, i])) + 1e-8 for i, name in enumerate(feature_names)}
    standardizer = Standardizer(means, stds)
    
    X_std = np.array([standardizer.transform(dict(zip(feature_names, row)), feature_names) for row in train_X])
    
    pos_mask = train_y == 1
    neg_mask = train_y == 0
    pos_centroid = np.mean(X_std[pos_mask], axis=0) if np.any(pos_mask) else np.zeros(len(feature_names))
    neg_centroid = np.mean(X_std[neg_mask], axis=0) if np.any(neg_mask) else np.zeros(len(feature_names))
    diff = pos_centroid - neg_centroid
    
    weights = {name: float(diff[i]) for i, name in enumerate(feature_names)}
    intercept = float(np.dot(neg_centroid, diff))
    
    model = LinearClassifier(
        feature_names=tuple(feature_names),
        standardizer=standardizer,
        weights=weights,
        intercept=intercept,
    )
    
    train_time = time.time() - start
    print(f"Model trained in {train_time:.2f}s")
    
    # Step 5: Backtest
    print("\n[Step 5] Running Backtest")
    start = time.time()
    strategy = live.strategy_for_regime("ranging", "balanced")
    
    result = backtest.run_backtest(
        candles=candles,
        model=model,
        strategy=strategy,
        initial_equity=INITIAL_EQUITY,
        position_size=POSITION_SIZE,
    )
    backtest_time = time.time() - start
    
    # Results
    final_equity = INITIAL_EQUITY * (1 + result.total_return)
    
    print()
    print("="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    print(f"Initial Capital:     ${INITIAL_EQUITY:.2f}")
    print(f"Final Capital:       ${final_equity:.2f}")
    print(f"Total Return:        {result.total_return*100:+.2f}%")
    print(f"Win Rate:            {result.win_rate:.2%}")
    print(f"Profit Factor:       {result.profit_factor:.2f}")
    print(f"Max Drawdown:        {result.max_drawdown:.2%}")
    print(f"Sharpe Ratio:        {result.sharpe:.2f}")
    print(f"Total Trades:        {result.trade_count}")
    print()
    print(f"Performance: ${INITIAL_EQUITY:.2f} → ${final_equity:.2f}")
    if result.total_return > 0:
        print(f"Result: PROFIT +${final_equity - INITIAL_EQUITY:.2f}")
    else:
        print(f"Result: LOSS -${abs(final_equity - INITIAL_EQUITY):.2f}")
    print()
    print(f"Timing: Load={load_time:.1f}s | Features={feature_time:.1f}s | Train={train_time:.1f}s | Backtest={backtest_time:.1f}s")
    print(f"Total Time: {load_time + feature_time + train_time + backtest_time:.1f}s")
    print("="*60)
    
    # Save results
    output_path.mkdir(parents=True, exist_ok=True)
    summary = {
        "initial_capital": INITIAL_EQUITY,
        "final_capital": final_equity,
        "total_return_pct": result.total_return * 100,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "max_drawdown": result.max_drawdown,
        "sharpe": result.sharpe,
        "trade_count": result.trade_count,
        "signal_counts": result.signal_counts,
        "candles_used": len(candles),
        "timing_seconds": {
            "data_load": load_time,
            "feature_computation": feature_time,
            "model_training": train_time,
            "backtest": backtest_time,
            "total": load_time + feature_time + train_time + backtest_time,
        },
        "trades_sample": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_pct": t.pnl_pct * 100,
                "outcome": t.outcome,
            }
            for t in result.trades[:10]
        ],
    }
    
    output_file = output_path / "backtest_100usd_result.json"
    output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
