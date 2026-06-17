#!/usr/bin/env python3
from pathlib import Path
from btcusdt_quant import dataset

candles = dataset.load_csv_candles(Path('artifacts/real_btcusdt_1m.csv'))
c = candles[50]
print(f'Candle 50:')
print(f'  volume: {c.volume}')
print(f'  taker_buy_base_volume: {c.taker_buy_base_volume}')
print(f'  taker_buy_quote_volume: {c.taker_buy_quote_volume}')
print(f'  Expected taker_ratio: {c.taker_buy_base_volume / c.volume}')
print(f'  Expected taker_quote_ratio: {c.taker_buy_quote_volume / c.quote_volume}')

orig_rows = dataset.build_feature_rows(candles[:100])
print(f'Original taker_ratio: {orig_rows[50].features["taker_ratio"]}')
print(f'Original taker_quote_ratio: {orig_rows[50].features["taker_quote_ratio"]}')
