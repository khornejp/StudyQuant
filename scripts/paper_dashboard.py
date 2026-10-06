from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.dashboard import make_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve local paper dashboard")
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--sqlite-path")
    parser.add_argument("--data-root")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.sqlite_path or args.data_root or args.port:
        config = replace(config, sqlite_path=args.sqlite_path or config.sqlite_path,
                         data_root=args.data_root or config.data_root,
                         dashboard_port=args.port or config.dashboard_port)
    server = make_server(config.sqlite_path, config.data_root,
                         config.dashboard_host, config.dashboard_port,
                         books=config.books, start_time=config.start_time)
    print(f"http://{config.dashboard_host}:{config.dashboard_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
