# BTCUSDT Pipeline - Sequential Download (Fixed)
# Uses python collect-archive CLI (verified stable)

$ErrorActionPreference = "Stop"

$periods = @(
    # 2020-2024 Full range (headerless CSV fix applied)
    @{Label="UP2020-01"; Start="2020-01-01"; End="2020-02-13"; Dir="artifacts/futures_up_2020_01"},
    @{Label="UP2020-03"; Start="2020-03-13"; End="2020-05-11"; Dir="artifacts/futures_up_2020_03"},
    @{Label="UP2020-07"; Start="2020-07-20"; End="2020-09-01"; Dir="artifacts/futures_up_2020_07"},
    @{Label="UP2020-10"; Start="2020-10-08"; End="2021-01-08"; Dir="artifacts/futures_up_2020_10"},
    @{Label="UP2021-01"; Start="2021-01-27"; End="2021-04-14"; Dir="artifacts/futures_up_2021_01"},
    @{Label="UP2021-07"; Start="2021-07-20"; End="2021-09-07"; Dir="artifacts/futures_up_2021_07"},
    @{Label="UP2021-09"; Start="2021-09-29"; End="2021-11-10"; Dir="artifacts/futures_up_2021_09"},
    @{Label="UP2022-01"; Start="2022-01-24"; End="2022-03-28"; Dir="artifacts/futures_up_2022_01"},
    @{Label="UP2023-01"; Start="2023-01-01"; End="2023-02-16"; Dir="artifacts/futures_up_2023_01"},
    @{Label="UP2023-03"; Start="2023-03-10"; End="2023-04-14"; Dir="artifacts/futures_up_2023_03"},
    @{Label="UP2023-06"; Start="2023-06-15"; End="2023-07-13"; Dir="artifacts/futures_up_2023_06"},
    @{Label="UP2023-10"; Start="2023-10-16"; End="2023-12-08"; Dir="artifacts/futures_up_2023_10"},
    @{Label="UP2024-01"; Start="2024-01-23"; End="2024-03-14"; Dir="artifacts/futures_up_2024_01"},
    @{Label="UP2024-05"; Start="2024-05-01"; End="2024-06-07"; Dir="artifacts/futures_up_2024_05"},
    @{Label="UP2024-09"; Start="2024-09-06"; End="2024-10-29"; Dir="artifacts/futures_up_2024_09"},
    @{Label="UP2024-11"; Start="2024-11-05"; End="2024-12-17"; Dir="artifacts/futures_up_2024_11"},
    @{Label="DN2020-02"; Start="2020-02-13"; End="2020-03-13"; Dir="artifacts/futures_down_2020_02"},
    @{Label="DN2021-01"; Start="2021-01-08"; End="2021-01-27"; Dir="artifacts/futures_down_2021_01"},
    @{Label="DN2021-04"; Start="2021-04-14"; End="2021-07-20"; Dir="artifacts/futures_down_2021_04"},
    @{Label="DN2021-09"; Start="2021-09-07"; End="2021-09-29"; Dir="artifacts/futures_down_2021_09"},
    @{Label="DN2021-11"; Start="2021-11-10"; End="2022-01-24"; Dir="artifacts/futures_down_2021_11"},
    @{Label="DN2022-03"; Start="2022-03-28"; End="2022-05-12"; Dir="artifacts/futures_down_2022_03"},
    @{Label="DN2022-05"; Start="2022-05-12"; End="2022-06-18"; Dir="artifacts/futures_down_2022_05"},
    @{Label="DN2022-08"; Start="2022-08-15"; End="2022-09-21"; Dir="artifacts/futures_down_2022_08"},
    @{Label="DN2022-11"; Start="2022-11-05"; End="2022-11-21"; Dir="artifacts/futures_down_2022_11"},
    @{Label="DN2023-02"; Start="2023-02-16"; End="2023-03-10"; Dir="artifacts/futures_down_2023_02"},
    @{Label="DN2023-07"; Start="2023-07-13"; End="2023-09-11"; Dir="artifacts/futures_down_2023_07"},
    @{Label="DN2024-01"; Start="2024-01-01"; End="2024-01-23"; Dir="artifacts/futures_down_2024_01"},
    @{Label="DN2024-03"; Start="2024-03-14"; End="2024-05-01"; Dir="artifacts/futures_down_2024_03"},
    @{Label="DN2024-06"; Start="2024-06-07"; End="2024-08-05"; Dir="artifacts/futures_down_2024_06"},
    @{Label="DN2024-12"; Start="2024-12-17"; End="2024-12-31"; Dir="artifacts/futures_down_2024_12"},
    @{Label="RG2020-05"; Start="2020-05-11"; End="2020-07-20"; Dir="artifacts/futures_range_2020_05"},
    @{Label="RG2020-09"; Start="2020-09-01"; End="2020-10-08"; Dir="artifacts/futures_range_2020_09"},
    @{Label="RG2022-06"; Start="2022-06-18"; End="2022-08-15"; Dir="artifacts/futures_range_2022_06"},
    @{Label="RG2022-09"; Start="2022-09-21"; End="2022-11-05"; Dir="artifacts/futures_range_2022_09"},
    @{Label="RG2022-11"; Start="2022-11-21"; End="2022-12-31"; Dir="artifacts/futures_range_2022_11"},
    @{Label="RG2023-04"; Start="2023-04-14"; End="2023-06-15"; Dir="artifacts/futures_range_2023_04"},
    @{Label="RG2023-09"; Start="2023-09-11"; End="2023-10-16"; Dir="artifacts/futures_range_2023_09"},
    @{Label="RG2023-12"; Start="2023-12-08"; End="2023-12-31"; Dir="artifacts/futures_range_2023_12"},
    @{Label="RG2024-08"; Start="2024-08-05"; End="2024-09-06"; Dir="artifacts/futures_range_2024_08"},
    @{Label="BT2025"; Start="2025-01-01"; End="2025-06-30"; Dir="artifacts/futures_backtest_2025"}
)

Write-Host "=== STEP 1: Downloading ===" -ForegroundColor Cyan
$ok = 0; $fail = 0

foreach ($p in $periods) {
    $csvPattern = "$($p.Dir)/BTCUSDT-1m-*.csv"
    if (Test-Path $csvPattern) { Write-Host "[$($p.Label)] Skip (exists)" -ForegroundColor Gray; $ok++; continue }
    
    Write-Host "[$($p.Label)] $($p.Start)~$($p.End)" -ForegroundColor Yellow -NoNewline
    try {
        $out = python -m btcusdt_quant collect-archive --start $p.Start --end $p.End --output $p.Dir --allow-public-network --min-rows 1 2>&1
        if (Test-Path $csvPattern) { Write-Host " OK" -ForegroundColor Green; $ok++ }
        else { Write-Host " FAIL (no CSV)" -ForegroundColor Red; $fail++ }
    } catch { Write-Host " FAIL: $_" -ForegroundColor Red; $fail++ }
}

Write-Host "Result: $ok success, $fail failed"
if ($ok -eq 0) { Write-Host "ERROR: No data!" -ForegroundColor Red; exit 1 }

Write-Host "`n=== STEP 2: CSV to Parquet ===" -ForegroundColor Cyan
foreach ($p in $periods) {
    $parquet = "$($p.Dir).parquet"
    if (Test-Path $parquet) { continue }
    $csvs = (Get-ChildItem "$($p.Dir)/BTCUSDT-1m-*.csv" -ErrorAction SilentlyContinue)
    if (-not $csvs) { continue }
    Write-Host "[$($p.Label)] $($csvs.Count) files" -ForegroundColor Yellow
    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa

# Standard Binance kline columns (before our renaming)
BINANCE_COLS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
]

def read_csv_safe(path):
    # Peek first line to detect header
    with open(path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    first_field = first_line.split(',')[0] if first_line else ''
    # If first field is numeric (timestamp), it's data row = no header
    is_header = not (first_field.replace('.', '').replace('-', '').isdigit())
    if is_header:
        return pv.read_csv(path)
    else:
        return pv.read_csv(path, read_options=pv.ReadOptions(column_names=BINANCE_COLS))

files = sorted(glob.glob('$($p.Dir)/BTCUSDT-1m-*.csv'))
if not files: exit(0)
tables = [read_csv_safe(f) for f in files]
t = pa.concat_tables(tables)
names = []
for c in t.column_names:
    if c=='count': names.append('number_of_trades')
    elif c=='taker_buy_volume': names.append('taker_buy_base_volume')
    else: names.append(c)
t = t.rename_columns(names)
t = t.select([n for n in names if n not in ('close_time','ignore')])
pq.write_table(t, '$parquet')
print(f'  {t.num_rows} rows')
"
}

Write-Host "`n=== STEP 3: Combine ALL periods into single timeline ===" -ForegroundColor Cyan
Write-Host "  This ensures continuous history for proper weekly MA computation"
python -c "
import pyarrow.parquet as pq, pyarrow.compute as pc, pyarrow as pa, glob

files = sorted(glob.glob('artifacts/futures_up_*.parquet') + 
              glob.glob('artifacts/futures_down_*.parquet') + 
              glob.glob('artifacts/futures_range_*.parquet'))
if not files:
    print('ERROR: No parquet files found')
    exit(1)

tables = [pq.read_table(f) for f in files]
combined = pa.concat_tables(tables)
combined = combined.take(pc.sort_indices(combined, sort_keys=[('open_time','ascending')]))
pq.write_table(combined, 'artifacts/training_combined.parquet')

# Also create backtest file if not exists
bt_files = glob.glob('artifacts/futures_backtest_2025.parquet')
if bt_files:
    print(f'Backtest: {bt_files[0]}')

print(f'Training data: {combined.num_rows} rows ({combined.num_rows/60/24:.0f} days)')
print(f'  Regime-aware will auto-classify: high_volatility / trending / ranging')
"

Write-Host "`n=== STEP 4: Train (skip first 50 weeks for valid weekly MA) ===" -ForegroundColor Cyan
python -c "
import pyarrow.parquet as pq, pyarrow as pa
import datetime

t = pq.read_table('artifacts/training_combined.parquet')
start_ms = int(datetime.datetime(2020, 12, 15, tzinfo=datetime.timezone.utc).timestamp() * 1000)
mask = pa.compute.greater_equal(t['open_time'], pa.scalar(start_ms))
t_filtered = t.filter(mask)
pq.write_table(t_filtered, 'artifacts/training_combined.parquet')
print(f'Filtered: {t.num_rows} -> {t_filtered.num_rows} rows (skipped first ~50 weeks)')
"
python -m btcusdt_quant train --input artifacts/training_combined.parquet --ensemble --regime-aware --output artifacts/regime_stacking_model

Write-Host "`n=== STEP 5: Backtest ===" -ForegroundColor Cyan
python -m btcusdt_quant backtest --input artifacts/futures_backtest_2025.parquet --model-artifact artifacts/regime_stacking_model --output artifacts/backtest_results

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
