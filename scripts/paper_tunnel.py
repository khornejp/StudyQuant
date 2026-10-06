"""Expose the local dashboard through a Cloudflare Quick Tunnel and announce its URL.

Quick Tunnel URLs change on every start, so each new URL is written to
artifacts/live/tunnel_url.txt and queued as a Telegram alert. The dashboard is
public while the tunnel runs (user decision 2026-10-06: shared view, no password).

    venv_btcusdt\\Scripts\\python.exe scripts\\paper_tunnel.py --config config\\paper.toml
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.notify import TelegramNotifier

URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/paper.toml")
    args = parser.parse_args()
    config = load_config(args.config)
    binary = ROOT / "tools" / "cloudflared.exe"
    target = f"http://127.0.0.1:{config.dashboard_port}"
    process = subprocess.Popen([str(binary), "tunnel", "--no-autoupdate", "--url", target],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace")
    announced = False
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        match = URL.search(line)
        if match and not announced:
            url = match.group(0)
            (ROOT / config.data_root / "tunnel_url.txt").write_text(url + "\n", encoding="utf-8")
            TelegramNotifier(ROOT / config.sqlite_path, config).enqueue(
                f"tunnel:{url}", "alert", {"kind": "대시보드 외부 주소", "detail": url})
            announced = True
    # cloudflared exited; the supervisor restarts us and a new URL is announced.
    sys.exit(process.wait())


if __name__ == "__main__":
    main()
