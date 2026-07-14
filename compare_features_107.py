#!/usr/bin/env python3
"""
TDD Validation: Compare all 107 features between original and fast computation.
Expected to FAIL (RED) until all 107 features are implemented in fast_features.py.

Usage:
    python compare_features_107.py
    echo $?  # Should return 1 until GREEN
"""
import sys
from pathlib import Path

from btcusdt_quant import dataset
from btcusdt_quant.dataset import FEATURE_NAMES
from fast_features import compute_features_fast


def compare_all_features():
    print("="*80)
    print("TDD RED: Validating all 107 features")
    print("="*80)
    
    # Load sample candles
    candles = dataset.load_csv_candles(Path('artifacts/real_btcusdt_1m.csv'))
    sample = candles[:100]
    print(f"Using {len(sample)} candles for validation")
    print()
    
    # Original method
    print("Computing with ORIGINAL method (dataset.build_feature_rows)...")
    orig_rows = dataset.build_feature_rows(sample)
    print(f"Original features per row: {len(orig_rows[50].features)}")
    
    # Fast method
    print("Computing with FAST method (compute_features_fast)...")
    fast_df = compute_features_fast(sample)
    print(f"Fast features: {fast_df.shape[1]} columns")
    print()
    
    # Check 1: Column count must be exactly 107
    print("[Check 1] Feature count")
    print(f"  Expected: {len(FEATURE_NAMES)}")
    print(f"  Fast has: {fast_df.shape[1]}")
    if fast_df.shape[1] != len(FEATURE_NAMES):
        print(f"  FAIL: Fast features has {fast_df.shape[1]} columns, expected {len(FEATURE_NAMES)}")
    else:
        print("  PASS")
    print()
    
    # Check 2: All expected features must be present
    print("[Check 2] Feature presence")
    missing_features = [f for f in FEATURE_NAMES if f not in fast_df.columns]
    extra_features = [f for f in fast_df.columns if f not in FEATURE_NAMES]
    
    if missing_features:
        print(f"  FAIL: {len(missing_features)} missing features:")
        for f in missing_features[:20]:
            print(f"    - {f}")
        if len(missing_features) > 20:
            print(f"    ... and {len(missing_features)-20} more")
    else:
        print("  PASS: No missing features")
    
    if extra_features:
        print(f"  INFO: {len(extra_features)} extra features: {extra_features}")
    print()
    
    # Check 3: Numerical comparison for common features
    print("[Check 3] Numerical exactness (diff < 1e-10)")
    common_features = [f for f in FEATURE_NAMES if f in fast_df.columns and f in orig_rows[50].features]
    print(f"  Comparing {len(common_features)} common features")
    print()
    
    mismatches = []
    max_diff_overall = 0.0
    worst_feature = ""
    
    # Compare at multiple indices (after warmup)
    test_indices = [50, 60, 70, 80, 90]
    
    print(f"{'Feature':<35} {'Max Diff':>12} {'Status':>8}")
    print("-"*80)
    
    for feat in common_features:
        max_diff_for_feat = 0.0
        for idx in test_indices:
            if idx < len(orig_rows) and idx < len(fast_df):
                orig_val = float(orig_rows[idx].features.get(feat, 0.0))
                fast_val = float(fast_df[feat].iloc[idx])
                diff = abs(orig_val - fast_val)
                max_diff_for_feat = max(max_diff_for_feat, diff)
        
        if max_diff_for_feat > max_diff_overall:
            max_diff_overall = max_diff_for_feat
            worst_feature = feat
        
        match = max_diff_for_feat < 1e-10
        status = "PASS" if match else "FAIL"
        
        if not match:
            mismatches.append((feat, max_diff_for_feat))
        
        # Print all for visibility
        print(f"{feat:<35} {max_diff_for_feat:>12.2e} {status:>8}")
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total expected features:     {len(FEATURE_NAMES)}")
    print(f"Fast features implemented:   {fast_df.shape[1]}")
    print(f"Missing features:            {len(missing_features)}")
    print(f"Common features compared:    {len(common_features)}")
    print(f"Mismatches (diff >= 1e-10):  {len(mismatches)}")
    print(f"Worst diff:                  {max_diff_overall:.2e} ({worst_feature})")
    print()
    
    if missing_features or mismatches:
        print("STATUS: RED (FAIL) - Not all 107 features match exactly")
        print()
        print("Missing features (need implementation):")
        for f in missing_features:
            print(f"  - {f}")
        print()
        if mismatches:
            print("Mismatched features (need fixes):")
            for feat, diff in mismatches[:10]:
                print(f"  - {feat}: diff={diff:.2e}")
        return 1
    else:
        print("STATUS: GREEN (PASS) - All 107 features match exactly!")
        return 0


if __name__ == "__main__":
    exit_code = compare_all_features()
    sys.exit(exit_code)
