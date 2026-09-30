# Pure-direction horizon information report

Date: 2026-09-19 (Asia/Seoul)

## Result

H15 was selected without using the later evaluation period. The frozen gate
result was `HORIZON_INFORMATION_FAIL` only because the paired bootstrap lower
bound was -0.00239; every other gate passed. Independent recovery verification
passed.

The original calculation completed but failed JSON serialization on a NumPy
boolean after writing its three result tables. The frozen runner/output were
preserved. A serialization-only recovery copied the hash-pinned tables,
converted scalar types, and independently rebuilt the complete audit from raw
data. No analytical setting changed.

## Development selection: 2021-02 through 2023-09

All horizons had 140/140 eligible TRAIN-internal three-day blocks.

| Horizon | Mean oriented AUC | Median |
|---:|---:|---:|
|15|**0.553207**|0.552782|
|20|0.550232|0.551621|
|25|0.548107|0.545834|
|30|0.545408|0.544590|
|35|0.540473|0.539048|
|40|0.536577|0.539618|
|45|0.535729|0.536486|
|50|0.533862|0.534576|
|55|0.530875|0.529503|
|60|0.532239|0.535776|

The decline was broadly monotonic. H15 was frozen before reading the later
evaluation metrics.

## Later evaluation: 2023-11 through 2025-12

- H15 mean/median AUC: 0.546261 / 0.553051.
- H15 above 0.5: 12/14 folds.
- H60 mean AUC: 0.526723.
- H15 gain: +0.019537; wins: 9/14.
- Paired fold bootstrap 95% interval: [-0.002385, 0.040998].

This was strong enough to motivate attention to H15 but not enough to pass the
pre-registered information gate alone. Existing independent H1..H15 model
evidence was therefore treated as corroborating context, not as a retroactive
change to this gate.

No model, backtest or order was created by this audit.
