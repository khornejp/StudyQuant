#!/usr/bin/env python3
"""
Convert CSV candles to Parquet for faster loading.
Usage: python convert_to_parquet.py [input_csv] [output_parquet]
"""
import sys
from pathlib import Path

from btcusdt_quant import dataset


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/real_btcusdt_1m.csv")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".parquet")
    
    print(f"Converting {input_path} -> {output_path}")
    
    # Load CSV
    print("Loading CSV...")
    candles = dataset.load_csv_candles(input_path)
    print(f"Loaded {len(candles)} candles")
    
    # Save as Parquet
    print("Saving Parquet...")
    dataset.write_candles_parquet(output_path, candles)
    
    # Compare sizes
    csv_size = input_path.stat().st_size / (1024 * 1024)
    pq_size = output_path.stat().st_size / (1024 * 1024)
    
    print(f"Done!")
    print(f"CSV size:  {csv_size:.2f} MB")
    print(f"Parquet size: {pq_size:.2f} MB ({pq_size/csv_size*100:.1f}% of CSV)")
    
    # Quick load test
    import time
    start = time.time()
    _ = dataset.load_csv_candles(input_path)
    csv_time = time.time() - start
    
    start = time.time()
    _ = dataset.load_parquet_candles(output_path)
    pq_time = time.time() - start
    
    print(f"CSV load time:  {csv_time:.3f}s")
    print(f"Parquet load time: {pq_time:.3f}s ({pq_time/csv_time*100:.1f}% of CSV)")


if __name__ == "__main__":
    main()
