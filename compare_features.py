#!/usr/bin/env python3
"""Compare original vs fast feature computation."""
import numpy as np
from pathlib import Path
from btcusdt_quant import dataset
from fast_features import compute_features_fast

candles = dataset.load_csv_candles(Path('artifacts/real_btcusdt_1m.csv'))
sample = candles[:100]

print("Computing with original method...")
orig_rows = dataset.build_feature_rows(sample)

print("Computing with fast method...")
fast_df = compute_features_fast(sample)

# Compare at candle index 50 (after warmup)
idx = 50
orig_features = orig_rows[idx].features

print(f"\nComparison at candle index {idx} (after warmup):")
print("="*100)
print(f"{'Feature':<30} {'Original':>15} {'Fast':>15} {'Diff':>15} {'Match?':>8}")
print("-"*100)

mismatches = []
for feat in sorted(orig_features.keys()):
    if feat in fast_df.columns:
        orig_val = float(orig_features[feat])
        fast_val = float(fast_df[feat].iloc[idx])
        diff = abs(orig_val - fast_val)
        
        match = diff < 1e-10
        status = "OK" if match else "MISMATCH"
        
        if not match:
            mismatches.append((feat, orig_val, fast_val, diff))
        
        if len(mismatches) <= 10 or match:
            print(f"{feat:<30} {orig_val:>15.6e} {fast_val:>15.6e} {diff:>15.2e} {status:>8}")

print()
if mismatches:
    print(f"MISMATCHES FOUND: {len(mismatches)} features")
    print("Showing first 10 mismatches:")
    for feat, orig, fast, diff in mismatches[:10]:
        print(f"  {feat}: orig={orig:.6e}, fast={fast:.6e}, diff={diff:.2e}")
else:
    print("ALL FEATURES MATCH!")

print(f"\nTotal features compared: {len([f for f in orig_features if f in fast_df.columns])}")
print(f"Features in original only: {len([f for f in orig_features if f not in fast_df.columns])}")
print(f"Features in fast only: {len([f for f in fast_df.columns if f not in orig_features])}")
