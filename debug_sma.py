#!/usr/bin/env python3
from pathlib import Path
from btcusdt_quant import dataset
from fast_features import compute_features_fast

candles = dataset.load_csv_candles(Path('artifacts/real_btcusdt_1m.csv'))
sample = candles[:100]

# Original
orig_rows = dataset.build_feature_rows(sample)

# Fast
fast_df = compute_features_fast(sample)

idx = 50
print(f'Index {idx}:')
print(f'  close = {candles[idx].close}')
print(f'  Original sma_20_60_spread = {orig_rows[idx].features["sma_20_60_spread"]}')
print(f'  Fast sma_20_60_spread = {fast_df["sma_20_60_spread"].iloc[idx]}')
print(f'  Fast sma_20 = {fast_df["sma_20"].iloc[idx]}')
print(f'  Fast sma_60 = {fast_df["sma_60"].iloc[idx]}')
print(f'  Calculated: {(fast_df["sma_20"].iloc[idx] - fast_df["sma_60"].iloc[idx]) / candles[idx].close}')
