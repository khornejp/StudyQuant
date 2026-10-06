from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from btcusdt_quant.paper.collector import Collector
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.notify import TelegramNotifier
from btcusdt_quant.paper.store import PaperStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run public-data paper collector")
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--minutes", type=int, default=0, help="0 runs until Ctrl+C")
    parser.add_argument("--sqlite-path")
    parser.add_argument("--data-root")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.sqlite_path or args.data_root:
        config = replace(config, sqlite_path=args.sqlite_path or config.sqlite_path,
                         data_root=args.data_root or config.data_root)
    # One collector per DB: a second instance (e.g. scheduler + manual start) exits instead of double-writing.
    import msvcrt
    lock = open(Path(config.sqlite_path).with_suffix(".run.lock"), "a+")
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        sys.exit(f"paper_run already running for {config.sqlite_path}")
    with PaperStore(config.sqlite_path) as store:
        collector = Collector(PaperEngine(store, config), f"{config.data_root}/raw")
        notifier = TelegramNotifier(store.path, config)
        completed = 0
        last_day = None
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        collector.start_streams()
        notifier.start()
        try:
            while not args.minutes or completed < args.minutes:
                try:
                    cycle_start = store.get_meta("last_processed_minute")
                    print(collector.collect_once(), flush=True)
                    current_day = store.get_meta("last_processed_minute")
                    if current_day:
                        engine_end = pd.Timestamp(current_day) + pd.Timedelta(minutes=1)
                        collector.engine.replay_books(config.start_time, engine_end,
                                                      publish_open_positions=True)
                    current_day = current_day[:10] if current_day else None
                    if last_day and current_day != last_day:
                        store.export_day(last_day, f"{config.data_root}/daily")
                        notifier.publish_daily_summary(last_day)
                    notifier.publish_store_events(cycle_start)
                    notifier.publish_health_alerts(config.data_root, cycle_start)
                    last_day = current_day
                except Exception as error:
                    notifier.enqueue(
                        f"alert:engine:{type(error).__name__}:{pd.Timestamp.now(tz='UTC').floor('h').isoformat()}",
                        "alert", {"kind": "엔진 오류", "detail": type(error).__name__})
                    logging.exception("paper cycle failed: %s", type(error).__name__)
                completed += 1
                if not args.minutes or completed < args.minutes:
                    delay = max(1.0, 62.0 - pd.Timestamp.now(tz="UTC").second)
                    time.sleep(delay)
        finally:
            collector.close()
            notifier.close()


if __name__ == "__main__":
    main()
