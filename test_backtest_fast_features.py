#!/usr/bin/env python3
"""
Fast Backtest using vectorized feature computation.
Uses fast_features.py for 25x speedup.

Usage:
    python test_backtest_fast_features.py
"""
import json
import time
from pathlib import Path

import numpy as np

from btcusdt_quant import backtest, dataset, live, training
from fast_features import compute_features_fast


def main():
    INPUT_PATH = Path("artifacts/real_btcusdt_1m.csv")
    OUTPUT_PATH = Path("artifacts/backtest_fast")
    INITIAL_EQUITY = 100.0
    POSITION_SIZE = 0.1
    MAX_CANDLES = 5000
    
    print("="*60)
    print("Fast Backtest - $100 Initial Capital")
    print("(Using vectorized feature computation)")
    print("="*60)
    
    # Load data
    print("Loading candles...")
    candles = dataset.load_csv_candles(INPUT_PATH)
    candles = candles[:MAX_CANDLES]
    print(f"Using {len(candles)} candles")
    
    # Fast feature computation
    print("Computing features (vectorized)...")
    start = time.time()
    features_df = compute_features_fast(candles)
    feature_time = time.time() - start
    print(f"Features computed in {feature_time:.2f}s ({features_df.shape[1]} features)")
    
    # Train model using fast features
    print("Training model...")
    start = time.time()
    
    # Convert DataFrame to labeled rows
    feature_names = list(features_df.columns)
    feature_matrix = features_df.values
    
    # Create labels (simple: next 15-bar return > 0)
    closes = np.array([c.close for c in candles])
    labels = []
    for i in range(len(candles) - 15):
        future_return = (closes[i+15] - closes[i]) / closes[i]
        labels.append(1 if future_return > 0 else 0)
    labels.extend([0] * 15)  # Pad last 15
    
    # Train model
    config = training.TrainingConfig(model_family="stdlib", n_groups=3, test_group_count=1)
    
    # Use training module's fit function
    from btcusdt_quant.models import ModelFactory
    from btcusdt_quant.training import Standardizer, LinearClassifier
    
    # Simple centroid model
    train_size = int(len(candles) * 0.8)
    train_X = feature_matrix[:train_size]
    train_y = np.array(labels[:train_size])
    
    # Compute standardizer
    means = {name: float(np.mean(train_X[:, i])) for i, name in enumerate(feature_names)}
    stds = {name: float(np.std(train_X[:, i])) + 1e-8 for i, name in enumerate(feature_names)}
    standardizer = Standardizer(means, stds)
    
    # Standardize
    X_std = np.array([standardizer.transform(dict(zip(feature_names, row)), feature_names) for row in train_X])
    
    # Centroid classifier
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
    
    # Backtest
    print("Running backtest...")
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
    print("RESULTS")
    print("="*60)
    print(f"Initial Equity:     ${INITIAL_EQUITY:.2f}")
    print(f"Final Equity:       ${final_equity:.2f}")
    print(f"Total Return:        {result.total_return*100:.2f}%")
    print(f"Win Rate:            {result.win_rate:.2%}")
    print(f"Profit Factor:       {result.profit_factor:.2f}")
    print(f"Max Drawdown:        {result.max_drawdown:.2%}")
    print(f"Sharpe Ratio:        {result.sharpe:.2f}")
    print(f"Total Trades:        {result.trade_count}")
    print()
    print(f"Timing: Features={feature_time:.1f}s | Train={train_time:.1f}s | Backtest={backtest_time:.1f}s")
    print("="*60)
    
    # Save
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    summary = {
        "initial_equity": INITIAL_EQUITY,
        "final_equity": final_equity,
        "total_return_pct": result.total_return * 100,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "max_drawdown": result.max_drawdown,
        "sharpe": result.sharpe,
        "trade_count": result.trade_count,
        "timing": {
            "feature_computation_seconds": feature_time,
            "model_train_seconds": train_time,
            "backtest_seconds": backtest_time,
        },
    }
    output_file = OUTPUT_PATH / "backtest_fast_summary.json"
    output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
