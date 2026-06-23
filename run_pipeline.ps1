# BTCUSDT Pipeline - Correct Pipeline Order
# 1. Download 2020-2024 as ONE continuous dataset for proper weekly MA50 computation
# 2. Download 2025 backtest data separately
# 3. Generate user_regime_periods.json
# 4. Train with user regimes (50-week warmup auto-excluded)
# 5. Backtest on 2025 data

$ErrorActionPreference = "Stop"

# User-defined regime periods (used for labeling, NOT for data downloading)
$regimePeriods = @(
    # 2020
    @{Regime="up";     Start="2020-01-01"; End="2020-02-13"},
    @{Regime="down";   Start="2020-02-13"; End="2020-03-13"},
    @{Regime="up";     Start="2020-03-13"; End="2020-05-11"},
    @{Regime="range";  Start="2020-05-11"; End="2020-07-20"},
    @{Regime="up";     Start="2020-07-20"; End="2020-09-01"},
    @{Regime="range";  Start="2020-09-01"; End="2020-10-08"},
    @{Regime="up";     Start="2020-10-08"; End="2021-01-08"},
    # 2021
    @{Regime="down";   Start="2021-01-08"; End="2021-01-27"},
    @{Regime="up";     Start="2021-01-27"; End="2021-04-14"},
    @{Regime="down";   Start="2021-04-14"; End="2021-07-20"},
    @{Regime="up";     Start="2021-07-20"; End="2021-09-07"},
    @{Regime="down";   Start="2021-09-07"; End="2021-09-29"},
    @{Regime="up";     Start="2021-09-29"; End="2021-11-10"},
    @{Regime="down";   Start="2021-11-10"; End="2022-01-24"},
    # 2022
    @{Regime="up";     Start="2022-01-24"; End="2022-03-28"},
    @{Regime="down";   Start="2022-03-28"; End="2022-05-12"},
    @{Regime="down";   Start="2022-05-12"; End="2022-06-18"},
    @{Regime="range";  Start="2022-06-18"; End="2022-08-15"},
    @{Regime="down";   Start="2022-08-15"; End="2022-09-21"},
    @{Regime="range";  Start="2022-09-21"; End="2022-11-05"},
    @{Regime="down";   Start="2022-11-05"; End="2022-11-21"},
    @{Regime="range";  Start="2022-11-21"; End="2022-12-31"},
    # 2023
    @{Regime="up";     Start="2023-01-01"; End="2023-02-16"},
    @{Regime="down";   Start="2023-02-16"; End="2023-03-10"},
    @{Regime="up";     Start="2023-03-10"; End="2023-04-14"},
    @{Regime="range";  Start="2023-04-14"; End="2023-06-15"},
    @{Regime="up";     Start="2023-06-15"; End="2023-07-13"},
    @{Regime="down";   Start="2023-07-13"; End="2023-09-11"},
    @{Regime="range";  Start="2023-09-11"; End="2023-10-16"},
    @{Regime="up";     Start="2023-10-16"; End="2023-12-08"},
    @{Regime="range";  Start="2023-12-08"; End="2023-12-31"},
    # 2024
    @{Regime="down";   Start="2024-01-01"; End="2024-01-23"},
    @{Regime="up";     Start="2024-01-23"; End="2024-03-14"},
    @{Regime="down";   Start="2024-03-14"; End="2024-05-01"},
    @{Regime="up";     Start="2024-05-01"; End="2024-06-07"},
    @{Regime="down";   Start="2024-06-07"; End="2024-08-05"},
    @{Regime="range";  Start="2024-08-05"; End="2024-09-06"},
    @{Regime="up";     Start="2024-09-06"; End="2024-10-29"},
    @{Regime="up";     Start="2024-11-05"; End="2024-12-17"},
    @{Regime="down";   Start="2024-12-17"; End="2024-12-31"}
)

# Standard Binance kline columns (for headerless CSV detection)
$BINANCE_COLS = @(
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
)

function Convert-CsvToParquet($csvDir, $outputParquet) {
    Write-Host "  Converting CSVs to Parquet: $outputParquet" -ForegroundColor Yellow
    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa

BINANCE_COLS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
]

def read_csv_safe(path):
    with open(path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    first_field = first_line.split(',')[0] if first_line else ''
    is_header = not (first_field.replace('.', '').replace('-', '').isdigit())
    if is_header:
        return pv.read_csv(path)
    else:
        return pv.read_csv(path, read_options=pv.ReadOptions(column_names=BINANCE_COLS))

files = sorted(glob.glob('$csvDir/BTCUSDT-1m-*.csv'))
if not files:
    print('ERROR: No CSV files found in $csvDir')
    exit(1)
tables = [read_csv_safe(f) for f in files]
t = pa.concat_tables(tables)
names = []
for c in t.column_names:
    if c=='count': names.append('number_of_trades')
    elif c=='taker_buy_volume': names.append('taker_buy_base_volume')
    else: names.append(c)
t = t.rename_columns(names)
t = t.select([n for n in names if n not in ('close_time','ignore')])
pq.write_table(t, '$outputParquet')
print(f'  {t.num_rows} rows ({t.num_rows/60/24:.0f} days)')
"
}

Write-Host "=== STEP 1: Download 2020-2024 Training Data (Continuous) ===" -ForegroundColor Cyan
$trainDir = "artifacts/training_2020_2024"
$trainParquet = "artifacts/training_combined.parquet"
if (Test-Path "$trainDir/BTCUSDT-1m-*.csv") {
    Write-Host "Training data already downloaded, skipping..." -ForegroundColor Gray
} else {
    Write-Host "Downloading 2020-01-01 ~ 2024-12-31 (this may take a while)..." -ForegroundColor Yellow
    python -m btcusdt_quant collect-archive --start 2020-01-01 --end 2024-12-31 --output $trainDir --allow-public-network --min-rows 1000000
    if (-not (Test-Path "$trainDir/BTCUSDT-1m-*.csv")) {
        Write-Host "ERROR: Failed to download training data" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path $trainParquet)) {
    Convert-CsvToParquet $trainDir $trainParquet
} else {
    Write-Host "Training Parquet already exists, skipping conversion..." -ForegroundColor Gray
}

Write-Host "`n=== STEP 2: Download 2025 Backtest Data ===" -ForegroundColor Cyan
$backtestDir = "artifacts/backtest_2025"
$backtestParquet = "artifacts/backtest_2025.parquet"
if (Test-Path "$backtestDir/BTCUSDT-1m-*.csv") {
    Write-Host "Backtest data already downloaded, skipping..." -ForegroundColor Gray
} else {
    Write-Host "Downloading 2025-01-01 ~ 2025-06-30..." -ForegroundColor Yellow
    python -m btcusdt_quant collect-archive --start 2025-01-01 --end 2025-06-30 --output $backtestDir --allow-public-network --min-rows 10000
    if (-not (Test-Path "$backtestDir/BTCUSDT-1m-*.csv")) {
        Write-Host "ERROR: Failed to download backtest data" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path $backtestParquet)) {
    Convert-CsvToParquet $backtestDir $backtestParquet
} else {
    Write-Host "Backtest Parquet already exists, skipping conversion..." -ForegroundColor Gray
}

Write-Host "`n=== STEP 3: Generate user_regime_periods.json ===" -ForegroundColor Cyan
$jsonPeriods = @()
foreach ($p in $regimePeriods) {
    $jsonPeriods += @{
        regime = $p.Regime
        start = $p.Start
        end_exclusive = $p.End
    }
}
$jsonContent = @{
    periods = $jsonPeriods
} | ConvertTo-Json -Depth 3
# Write without BOM (PowerShell 5.1 Out-File adds BOM)
[System.IO.File]::WriteAllText("$PWD\artifacts\user_regime_periods.json", $jsonContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "Generated artifacts/user_regime_periods.json with $($jsonPeriods.Count) periods" -ForegroundColor Green

Write-Host "`n=== STEP 4: Train with user regimes (50-week warmup auto-excluded) ===" -ForegroundColor Cyan
Write-Host "  Model: catboost ensemble (3 models per regime)"
Write-Host "  Regime-aware: user-specified periods"
$env:PYTHONUNBUFFERED=1
python -u -m btcusdt_quant train --input $trainParquet --use-user-regime --user-regime-file artifacts/user_regime_periods.json --output artifacts/regime_model --cache-path artifacts/training_dataset_cache.pkl
$env:PYTHONUNBUFFERED=0

Write-Host "`n=== STEP 5: Backtest on 2025 data ===" -ForegroundColor Cyan
# Merge training + backtest data for correct feature computation (rolling windows need history)
Write-Host "  Merging training(2020-2024) + backtest(2025) for feature continuity..." -ForegroundColor Yellow
python -c "
import pyarrow.parquet as pq
import pyarrow as pa
train = pq.read_table('$trainParquet')
bt = pq.read_table('$backtestParquet')
merged = pa.concat_tables([train, bt])
pq.write_table(merged, 'artifacts/merged_for_backtest.parquet')
print(f'  Merged: {merged.num_rows:,} rows ({train.num_rows:,} train + {bt.num_rows:,} backtest)')
"
python -m btcusdt_quant backtest --input artifacts/merged_for_backtest.parquet --model-artifact artifacts/regime_model --user-regime-file artifacts/user_regime_periods.json --backtest-start 2025-01-01 --output artifacts/backtest_results

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host "Training model: artifacts/regime_model/"
Write-Host "Backtest results: artifacts/backtest_results/"
