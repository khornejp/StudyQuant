# Offline BTCUSDT Data and Training Pipeline

Implemented in this pass:

- `btcusdt_quant.dataset` loads local CSV candles or a deterministic expanded offline fixture.
- `python -m btcusdt_quant collect --output artifacts/collected/btcusdt_1m.csv` writes fixture candles to a local CSV for reproducible collection tests.
- Unsigned public kline download is available only with the explicit `--allow-public-network` flag; the default path performs no network I/O.
- Candles are normalized onto the canonical 1-minute timeline with repaired gap rows and a gap report.
- A small stdlib feature matrix is built with strict warm-up handling and forward-return labels.
- `btcusdt_quant.training` runs deterministic purged walk-forward training with no network, credentials, WebSockets, or order paths.
- The trainer uses a lightweight centroid linear classifier, validation-fold calibration offset, and deterministic threshold selection.
- `python -m btcusdt_quant train --output artifacts/training [--input local.csv]` writes verifiable artifacts:
  - `dataset_card.json` / `dataset_card.md`
  - `model_card.json` / `model_card.md`
  - `feature_formula_registry.json`
  - `split_manifest.csv`
  - `fold_metrics.csv`
  - `calibration_report.json`
  - `threshold_report.json`
  - `labeled_feature_preview.csv`
  - `run_summary.json`
  - `artifact_manifest.json`

CSV input is local-first. Required columns are `open_time`, `open`, `high`, `low`, `close`, and `volume`; optional kline-style columns include `quote_volume`, `number_of_trades`, `taker_buy_base_volume`, and `taker_buy_quote_volume`.

The default training configuration requires at least 80 labeled rows after warm-up and label-horizon filtering. The built-in fixture default (`collect --rows 240` or `train` without `--input`) satisfies this requirement.

Remaining production-only gaps:

- Binance signed REST/testnet integration, account reconciliation, listenKey lifecycle, and rate-limit header validation.
- Robust public collection pagination, backfill checkpointing, and retry/429 header handling beyond the explicit single-batch public kline downloader.
- WebSocket ingestion, stream gap repair against REST backfill, and live/train feature parity tests.
- Full 70+ feature registry, microstructure sources, and production feature selection governance.
- LightGBM/CatBoost/Optuna model adapters, larger lockbox evaluation, and bootstrap confidence intervals around trading PnL.
- Live order safety tests, ghost-fill exchange failure injection, emergency close drills, and human approval gates.

The default training command is deliberately offline and safe for CI/local tests. It is not a live trading system.
