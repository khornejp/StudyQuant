#!/usr/bin/env python3
"""
Fast Backtest with $100 Initial Capital using Parquet + Feature Caching
Usage: python test_backtest_fast.py

This script optimizes backtest speed by:
1. Loading data from Parquet (faster for large files)
2. Caching computed features to avoid recomputation
3. Using a subset of core features for quick testing
"""
import json
import time
from pathlib import Path

from btcusdt_quant import backtest, dataset, live, training


def load_or_build_features(candles_path: Path, cache_path: Path) -> list:
    """Load features from cache or build and cache them."""
    from btcusdt_quant import dataset
    cache_dir = dataset.dataset_cache_dir(cache_path)
    if cache_dir.exists():
        print(f"Loading cached features from {cache_dir}...")
        return dataset.load_feature_rows_cache(cache_path, expected_feature_names=dataset.FEATURE_NAMES)

    print("Building features (this may take a while)...")
    candles = dataset.load_parquet_candles(candles_path) if candles_path.suffix == '.parquet' else dataset.load_csv_candles(candles_path)
    features = dataset.build_feature_rows(candles)

    print(f"Caching features to {cache_dir}...")
    dataset.save_feature_rows_cache(cache_path, features, dataset.FEATURE_NAMES)
    return features


def main():
    # Configuration
    INPUT_PATH = Path("artifacts/btcusdt_1m_2024_01_02.parquet")
    CSV_FALLBACK = Path("artifacts/btcusdt_1m_2024_01_02.csv")
    CACHE_PATH = Path("artifacts/feature_cache.pkl")
    OUTPUT_PATH = Path("artifacts/backtest_100usd_fast")
    
    INITIAL_EQUITY = 100.0
    POSITION_SIZE = 0.1
    MAX_CANDLES = 5000  # Quick test with subset
    
    print("="*60)
    print("BTCUSDT Fast Backtest - $100 Initial Capital")
    print("="*60)
    
    # Check data exists
    if not INPUT_PATH.exists() and not CSV_FALLBACK.exists():
        print(f"Error: Data file not found!")
        print(f"Expected: {INPUT_PATH} or {CSV_FALLBACK}")
        return
    
    data_path = INPUT_PATH if INPUT_PATH.exists() else CSV_FALLBACK
    print(f"Using data: {data_path}")
    
    # Load candles
    print("Loading candles...")
    start = time.time()
    if data_path.suffix == '.parquet':
        candles = dataset.load_parquet_candles(data_path)
    else:
        candles = dataset.load_csv_candles(data_path)
    load_time = time.time() - start
    print(f"Loaded {len(candles)} candles in {load_time:.2f}s")
    
    # Use subset
    candles = candles[:MAX_CANDLES]
    print(f"Using first {len(candles)} candles (~{len(candles)//60} hours)")
    
    # Load or build features with caching
    # Note: We rebuild for the subset
    print("Building features...")
    start = time.time()
    feature_rows = dataset.build_feature_rows(candles)
    feature_time = time.time() - start
    print(f"Features built in {feature_time:.2f}s")
    print(f"Feature count: {len(feature_rows[0].features) if feature_rows else 0}")
    
    # Train model
    print("Training model...")
    start = time.time()
    config = training.TrainingConfig(
        model_family="stdlib",
        n_groups=3,
        test_group_count=1,
        min_regime_rows=50,
    )
    
    build = dataset.build_dataset(input_path=data_path)
    train_rows = build.labeled_rows[:min(len(build.labeled_rows), 3000)]
    weights = [1.0] * len(train_rows)
    
    model_result = training.fit_fold(train_rows, build.feature_names, config, weights)
    model = model_result.adapter
    train_time = time.time() - start
    print(f"Model trained in {train_time:.2f}s")
    
    # Strategy
    strategy = live.strategy_for_regime("ranging", "balanced")
    
    # Run backtest
    print("Running backtest...")
    start = time.time()
    result = backtest.run_backtest(
        candles=candles,
        model=model,
        strategy=strategy,
        initial_equity=INITIAL_EQUITY,
        position_size=POSITION_SIZE,
    )
    backtest_time = time.time() - start
    print(f"Backtest completed in {backtest_time:.2f}s")
    
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
    print(f"Signal Counts:       {result.signal_counts}")
    print()
    print(f"Timing: Load={load_time:.1f}s | Features={feature_time:.1f}s | Train={train_time:.1f}s | Backtest={backtest_time:.1f}s")
    print()
    
    # Save results
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
        "signal_counts": result.signal_counts,
        "candles_used": len(candles),
        "timing": {
            "data_load_seconds": load_time,
            "feature_build_seconds": feature_time,
            "model_train_seconds": train_time,
            "backtest_seconds": backtest_time,
        },
        "trades_sample": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_pct": t.pnl_pct,
                "outcome": t.outcome,
            }
            for t in result.trades[:10]
        ],
    }
    
    output_file = OUTPUT_PATH / "backtest_100usd_fast.json"
    output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Results saved to: {output_file}")
    print("="*60)


if __name__ == "__main__":
    main()
