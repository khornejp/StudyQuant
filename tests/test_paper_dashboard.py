from __future__ import annotations

import json
import threading
import urllib.request

from btcusdt_quant.paper.dashboard import make_server
from btcusdt_quant.paper.store import PaperStore


def test_dashboard_http_and_json_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # Never inspect repository .env during this test.
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        store.insert("trades", {"book": "H1", "boundary": "PESS", "candidate": None,
            "entry_time": "2026-07-01T00:00:00+00:00", "exit_time": "2026-07-02T00:00:00+00:00",
            "side": 1, "entry_price": 1, "exit_price": 2, "gross_bps": 1,
            "cost_bps": 4, "funding_bps": 0, "net_bps": -3, "hold_minutes": 1440,
            "exit_reason": "MAX_HOLD"})
    server = make_server(path, tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for route in ("/", "/plotly.min.js", "/api/summary", "/api/books",
                      "/api/trades", "/api/signals", "/api/chart", "/api/price",
                      "/api/reference", "/api/health"):
            with urllib.request.urlopen(base + route, timeout=10) as response:
                assert response.status == 200
                payload = response.read()
                if route.startswith("/api/"):
                    data = json.loads(payload)
                    assert data["schema_version"] == 1
                    if route == "/api/health":
                        assert data["telegram"]["label"].startswith("텔레그램:")
                        assert data["notifications"] == {"pending": 0, "failed": 0}
                        assert data["book_ticker"]["rows"] == 0
                    if route == "/api/reference":
                        statuses = {row["timing_status"] for row in data["rows"]}
                        assert "채택:+5분(create_time+5m<T)" in statuses
                        assert "legacy(시각 결함):create_time 즉시 가용" in statuses
    finally:
        server.shutdown(); server.server_close(); thread.join()
