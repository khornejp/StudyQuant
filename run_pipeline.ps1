# BTCUSDT Pipeline - Sequential Download (Fixed)
# Uses python collect-archive CLI (verified stable)

$ErrorActionPreference = "Stop"

$periods = @(
    # 2023-2024 Only (Binance archive reliable data)
    @{Label="UP2023-01"; Start="2023-01-01"; End="2023-02-16"; Dir="artifacts/futures_up_2023_01"},
    @{Label="UP2023-03"; Start="2023-03-10"; End="2023-04-14"; Dir="artifacts/futures_up_2023_03"},
    @{Label="UP2023-06"; Start="2023-06-15"; End="2023-07-13"; Dir="artifacts/futures_up_2023_06"},
    @{Label="UP2023-10"; Start="2023-10-16"; End="2023-12-08"; Dir="artifacts/futures_up_2023_10"},
    @{Label="UP2024-01"; Start="2024-01-23"; End="2024-03-14"; Dir="artifacts/futures_up_2024_01"},
    @{Label="UP2024-05"; Start="2024-05-01"; End="2024-06-07"; Dir="artifacts/futures_up_2024_05"},
    @{Label="UP2024-09"; Start="2024-09-06"; End="2024-10-29"; Dir="artifacts/futures_up_2024_09"},
    @{Label="UP2024-11"; Start="2024-11-05"; End="2024-12-17"; Dir="artifacts/futures_up_2024_11"},
    @{Label="DN2023-02"; Start="2023-02-16"; End="2023-03-10"; Dir="artifacts/futures_down_2023_02"},
    @{Label="DN2023-07"; Start="2023-07-13"; End="2023-09-11"; Dir="artifacts/futures_down_2023_07"},
    @{Label="DN2024-01"; Start="2024-01-01"; End="2024-01-23"; Dir="artifacts/futures_down_2024_01"},
    @{Label="DN2024-03"; Start="2024-03-14"; End="2024-05-01"; Dir="artifacts/futures_down_2024_03"},
    @{Label="DN2024-06"; Start="2024-06-07"; End="2024-08-05"; Dir="artifacts/futures_down_2024_06"},
    @{Label="DN2024-12"; Start="2024-12-17"; End="2024-12-31"; Dir="artifacts/futures_down_2024_12"},
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
files = sorted(glob.glob('$($p.Dir)/BTCUSDT-1m-*.csv'))
if not files: exit(0)
t = pa.concat_tables([pv.read_csv(f) for f in files])
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

Write-Host "`n=== STEP 3: Combine ===" -ForegroundColor Cyan
python -c "
import pyarrow.parquet as pq, pyarrow.compute as pc, pyarrow as pa, glob

def combine(pattern, out):
    f = sorted(glob.glob(pattern))
    if not f: return
    t = pa.concat_tables([pq.read_table(x) for x in f])
    t = t.take(pc.sort_indices(t, sort_keys=[('open_time','ascending')]))
    pq.write_table(t, out)
    print(f'{out}: {t.num_rows} rows')

combine('artifacts/futures_up_*.parquet', 'artifacts/training_up.parquet')
combine('artifacts/futures_down_*.parquet', 'artifacts/training_down.parquet')
combine('artifacts/futures_range_*.parquet', 'artifacts/training_range.parquet')

allf = sorted(glob.glob('artifacts/training_*.parquet'))
if allf:
    t = pa.concat_tables([pq.read_table(f) for f in allf])
    t = t.take(pc.sort_indices(t, sort_keys=[('open_time','ascending')]))
    pq.write_table(t, 'artifacts/training_combined.parquet')
    print(f'Training: {t.num_rows} rows')
"

Write-Host "`n=== STEP 4: Train ===" -ForegroundColor Cyan
python -m btcusdt_quant train --input artifacts/training_combined.parquet --ensemble --regime-aware --output artifacts/regime_stacking_model

Write-Host "`n=== STEP 5: Backtest ===" -ForegroundColor Cyan
python -m btcusdt_quant backtest --input artifacts/futures_backtest_2025.parquet --model-artifact artifacts/regime_stacking_model --output artifacts/backtest_results

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
