from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from btcusdt_quant.paper.collector import Collector
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.futures_metrics import backfill_funding, backfill_metrics
from btcusdt_quant.paper.store import PaperStore

METRICS_DIRS = ["artifacts/metrics", "artifacts/hold_a_2026q3/metrics", "artifacts/metrics_2026q4"]
FUNDING_DIRS = ["artifacts/funding_2020_2026h1", "artifacts/hold_a_2026q3/funding"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed paper DB from local public archives (+ missing metrics days)")
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--start", default="2026-07-01T00:00:00Z", help="kline/legacy ls_ratio seed start")
    parser.add_argument("--end", default="2026-10-01T00:00:00Z", help="kline/legacy ls_ratio seed end (exclusive)")
    parser.add_argument("--metrics-start", default="2026-01-01", help="futures metrics/funding first UTC day")
    parser.add_argument("--metrics-end", default="2026-10-08", help="futures metrics/funding last UTC day (inclusive)")
    parser.add_argument("--metrics-dir", action="append", help="local metrics zip dirs searched first")
    parser.add_argument("--download-dir", default=METRICS_DIRS[-1], help="where missing metrics days are saved")
    parser.add_argument("--sqlite-path")
    parser.add_argument("--futures-only", action="store_true",
                        help="only the four futures metrics tables + funding events (no klines, no REST)")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.sqlite_path:
        config = replace(config, sqlite_path=args.sqlite_path)
    with PaperStore(config.sqlite_path) as store:
        engine = PaperEngine(store, config)
        metrics = backfill_metrics(store, args.metrics_start, args.metrics_end, args.metrics_dir or METRICS_DIRS,
                                   args.download_dir)
        funding = backfill_funding(engine, args.metrics_start, args.metrics_end, FUNDING_DIRS)
        summary = {"metrics": {k: v for k, v in metrics.items() if k != "files"},
                   "metrics_files": len(metrics["files"]), "funding": funding}
        if not args.futures_only:
            frame = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet")
            mask = frame.open_time.between(pd.Timestamp(args.start), pd.Timestamp(args.end), inclusive="left")
            summary["klines"] = engine.process_replay_minutes(frame.loc[mask])
            # Legacy ls_ratio from raw archive metrics once: timestamp = archive create_time (period start);
            # readers add the +5 min availability (the old features-parquet copy shifted twice).
            rows = store.connection.execute(
                "SELECT create_time, long_short_ratio, received_at FROM futures_global_ls_5m WHERE source='archive' "
                "AND long_short_ratio IS NOT NULL AND create_time>=? AND create_time<?",
                (pd.Timestamp(args.start).isoformat(), pd.Timestamp(args.end).isoformat())).fetchall()
            with store.transaction() as connection:
                for create_time, value, received_at in rows:
                    store.upsert("ls_ratio", {"timestamp": create_time, "global_ls_account": float(value),
                                 "long_account": None, "short_account": None, "source": "archive",
                                 "received_at": received_at}, connection)
            summary["ls_ratio"] = len(rows)
            # REST LS ratio resumes right after the archive window (first REST end label = args.end).
            store.set_meta("last_ls_timestamp",
                           (pd.Timestamp(args.end) - pd.Timedelta(milliseconds=1)).isoformat())
            rest_rows = 0
            if not args.local_only:
                collector = Collector(engine, f"{config.data_root}/raw")
                try:
                    for _ in range(100):
                        result = collector.collect_once()
                        rest_rows += result["klines"]
                        if result["klines"] < 1_000:
                            break
                finally:
                    collector.close()
            summary["rest_klines"] = rest_rows
    print(json.dumps({**summary, "source": "Binance USD-M BTCUSDT public archives + public REST"}, default=str))


if __name__ == "__main__":
    main()
