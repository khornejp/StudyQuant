#!/usr/bin/env python3
"""Quick backtest with $100 initial capital on 1-week data."""
import json
from pathlib import Path

from btcusdt_quant import backtest, dataset, live, training

# Config
INPUT_PATH = Path("artifacts/real_btcusdt_1m.csv")
OUTPUT_PATH = Path("artifacts/backtest_100usd")
INITIAL_EQUITY = 100.0  # $100 starting capital
POSITION_SIZE = 0.1     # 10% of equity per trade

print("="*60)
print("BTCUSDT Backtest - $100 Initial Capital")
print("="*60)
print(f"Data: {INPUT_PATH}")
print(f"Initial Equity: ${INITIAL_EQUITY}")
print(f"Position Size: {POSITION_SIZE*100}% per trade")
print()

# Load data
print("Loading candles...")
candles = dataset.load_csv_candles(INPUT_PATH)
print(f"Loaded {len(candles)} candles")

# Build features and train a quick model
print("Building features...")
feature_rows = dataset.build_feature_rows(candles)
print(f"Feature rows: {len(feature_rows)}")

# Quick training with regime-aware
print("Training model...")
config = training.TrainingConfig(
    regime_aware=True,
    n_groups=3,
    test_group_count=1,
    min_regime_rows=50,
)
# Use a subset for quick training
train_candles = candles[:min(len(candles), 2000)]
build = dataset.build_dataset(input_path=INPUT_PATH)

# For simplicity, use a basic model
model = training.fit_fold(
    build.labeled_rows[:min(len(build.labeled_rows), 1500)],
    build.feature_names,
    config,
    [1.0] * min(len(build.labeled_rows), 1500),
)

# Strategy
strategy = live.strategy_for_regime("ranging", "balanced")

# Run backtest
print("Running backtest...")
result = backtest.run_backtest(
    candles=candles,
    model=model.adapter if hasattr(model, 'adapter') else None,
    strategy=strategy,
    initial_equity=INITIAL_EQUITY,
    position_size=POSITION_SIZE,
)

# Results
print()
print("="*60)
print("RESULTS")
print("="*60)
print(f"Initial Equity:     ${INITIAL_EQUITY:.2f}")
print(f"Final Return:        {result.total_return:.4f} ({result.total_return*100:.2f}%)")
print(f"Final Equity:       ${INITIAL_EQUITY * (1 + result.total_return):.2f}")
print(f"Win Rate:            {result.win_rate:.2%}")
print(f"Profit Factor:       {result.profit_factor:.2f}")
print(f"Max Drawdown:        {result.max_drawdown:.2%}")
print(f"Sharpe Ratio:        {result.sharpe:.2f}")
print(f"Total Trades:        {result.trade_count}")
print(f"Signal Counts:       {result.signal_counts}")
print()

# Save results
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
summary = {
    "initial_equity": INITIAL_EQUITY,
    "final_equity": INITIAL_EQUITY * (1 + result.total_return),
    "total_return_pct": result.total_return * 100,
    "win_rate": result.win_rate,
    "profit_factor": result.profit_factor,
    "max_drawdown": result.max_drawdown,
    "sharpe": result.sharpe,
    "trade_count": result.trade_count,
    "signal_counts": result.signal_counts,
    "trades": [
        {
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl_pct": t.pnl_pct,
            "outcome": t.outcome,
        }
        for t in result.trades[:10]  # Save first 10 trades
    ],
}

output_file = OUTPUT_PATH / "backtest_100usd_summary.json"
output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(f"Results saved to: {output_file}")
print("="*60)
