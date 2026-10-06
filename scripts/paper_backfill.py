from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from btcusdt_quant.paper.collector import Collector
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.store import PaperStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed paper DB from existing local Q3 archive")
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--start", default="2026-07-01T00:00:00Z")
    parser.add_argument("--end", default="2026-10-01T00:00:00Z")
    parser.add_argument("--sqlite-path")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.sqlite_path:
        config = replace(config, sqlite_path=args.sqlite_path)
    frame = pd.read_parquet("artifacts/hold_a_2026q3/market_2026q3.parquet")
    features = pd.read_parquet("artifacts/hold_a_2026q3/features_2026q3.parquet",
                               columns=["open_time", "global_ls_account"])
    funding = pd.read_parquet("artifacts/hold_a_2026q3/funding_2026q3.parquet")
    mask = frame.open_time.between(pd.Timestamp(args.start), pd.Timestamp(args.end), inclusive="left")
    with PaperStore(config.sqlite_path) as store:
        engine = PaperEngine(store, config)
        count = engine.process_replay_minutes(frame.loc[mask])
        with store.transaction() as connection:
            for row in features.loc[mask].itertuples(index=False):
                store.upsert("ls_ratio", {"timestamp": row.open_time.isoformat(),
                    "global_ls_account": float(row.global_ls_account), "long_account": None,
                    "short_account": None, "source": "archive",
                    "received_at": row.open_time.isoformat()}, connection)
        # REST LS ratio resumes right after the archive window (first REST end label = args.end).
        store.set_meta("last_ls_timestamp",
                       (pd.Timestamp(args.end) - pd.Timedelta(milliseconds=1)).isoformat())
        for row in funding.itertuples(index=False):
            engine.store_funding(row.funding_time, row.funding_rate, source="archive")
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
    print({"klines": count, "ls_ratio": int(mask.sum()), "funding": len(funding),
           "rest_klines": rest_rows, "source": "artifacts/hold_a_2026q3 + public REST"})


if __name__ == "__main__":
    main()
