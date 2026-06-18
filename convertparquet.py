"""Convert Binance archive CSVs to Parquet with correct column names."""
import glob
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pyarrow as pa

# 1. Find all CSV files
files = sorted(glob.glob('artifacts/archive_2months/BTCUSDT-1m-*.csv'))
print(f"Found {len(files)} CSV files")

# 2. Read and combine all tables
tables = []
for i, f in enumerate(files):
    table = pv.read_csv(f)
    tables.append(table)
    if (i + 1) % 10 == 0:
        print(f"  Read {i+1}/{len(files)}")

# 3. Combine into one table
combined = pa.concat_tables(tables)
print(f"Combined: {combined.num_rows} rows")

# 4. Rename columns to match expected names
old_names = combined.column_names
new_names = []
for name in old_names:
    if name == 'count':
        new_names.append('number_of_trades')
    elif name == 'taker_buy_volume':
        new_names.append('taker_buy_base_volume')
    else:
        new_names.append(name)

combined = combined.rename_columns(new_names)

# 5. Drop unnecessary columns
columns_to_keep = [n for n in new_names if n not in ('close_time', 'ignore')]
combined = combined.select(columns_to_keep)

print(f"Final columns: {combined.column_names}")

# 6. Write parquet
pq.write_table(combined, 'artifacts/btcusdt_2months.parquet')
print(f"Saved to artifacts/btcusdt_2months.parquet")
