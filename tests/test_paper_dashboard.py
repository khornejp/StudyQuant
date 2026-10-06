from __future__ import annotations

import json
import re
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper.dashboard import make_server
from btcusdt_quant.paper.store import PaperStore


def _serve(path: Path, data_root: Path, **kwargs):
    server = make_server(path, data_root, port=0, **kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _get(base: str, route: str) -> dict:
    with urllib.request.urlopen(base + route, timeout=10) as response:
        assert response.status == 200
        return json.load(response)


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


def test_books_listed_before_t0(tmp_path) -> None:
    import json
    import threading
    import urllib.request

    from btcusdt_quant.paper.dashboard import make_server
    from btcusdt_quant.paper.store import PaperStore

    with PaperStore(tmp_path / "live.sqlite") as store:
        store.set_meta("last_processed_minute", "2026-10-06T00:00:00+00:00")
    server = make_server(tmp_path / "live.sqlite", tmp_path, port=0, books=("C1", "F3"),
                         start_time="2026-10-07T00:00:00Z")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/books"
        rows = json.load(urllib.request.urlopen(url))["rows"]
    finally:
        server.shutdown()
    assert [row["book"] for row in rows] == ["C1", "F3"]
    assert all(row["status"].startswith("T0 대기") and row["trades"] == 0 for row in rows)


def test_v2_api_schemas_and_candles_match_pandas_resample(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "live.sqlite"
    source = pd.DataFrame({
        "open_time": pd.date_range("2026-07-01", periods=17, freq="min", tz="UTC"),
        "open": [100 + i for i in range(17)],
        "high": [101 + i for i in range(17)],
        "low": [99 + i for i in range(17)],
        "close": [100.5 + i for i in range(17)],
        "volume": [10 + i for i in range(17)],
    })
    with PaperStore(path) as store:
        for row in source.to_dict("records"):
            store.upsert("klines_1m", {**row, "open_time": row["open_time"].isoformat(),
                         "source": "test", "received_at": row["open_time"].isoformat(), "closed": 1})
        store.insert("trades", {"book": "C1", "boundary": "PESS", "candidate": "x",
            "entry_time": source.open_time.iloc[1].isoformat(),
            "exit_time": source.open_time.iloc[9].isoformat(), "side": -1,
            "entry_price": 101.5, "exit_price": 109.5, "gross_bps": -10,
            "cost_bps": 4, "funding_bps": 0, "net_bps": -14,
            "hold_minutes": 8, "exit_reason": "MAX_HOLD"})
    server, thread, base = _serve(path, tmp_path, books=("C1",),
                                  start_time="2026-10-07T00:00:00Z")
    try:
        query = urlencode({"tf": "5m", "from": source.open_time.min().isoformat(),
                           "to": (source.open_time.max() + pd.Timedelta(minutes=1)).isoformat()})
        candles = _get(base, "/api/candles?" + query)
        markers = _get(base, "/api/markers?book=C1")
        positions = _get(base, "/api/positions")
        performance = _get(base, "/api/performance?book=C1")
        status = _get(base, "/api/status")
    finally:
        server.shutdown(); server.server_close(); thread.join()
    expected = (source.set_index("open_time").resample("5min")
                .agg({"open": "first", "high": "max", "low": "min",
                      "close": "last", "volume": "sum"}))
    actual = pd.DataFrame(candles["rows"])
    pd.testing.assert_frame_equal(
        actual[["open", "high", "low", "close", "volume"]].reset_index(drop=True),
        expected[["open", "high", "low", "close", "volume"]].reset_index(drop=True),
        check_dtype=False)
    assert candles["schema_version"] == 2 and candles["tf"] == "5m"
    assert candles["max_rows"] == 2_000 and len(candles["rows"]) == 4
    assert positions == {"schema_version": 2, "rows": []}
    assert performance["schema_version"] == 2 and performance["book"] == "C1"
    assert status["schema_version"] == 2 and status["mode"] == "paper"
    assert [(row["kind"], row["price"]) for row in markers["rows"]] == [
        ("entry", 101.5), ("exit", 109.5)]
    assert all(row["trade_id"] == 1 and row["net_bps"] == -14 for row in markers["rows"])


def test_vendor_is_local_html_has_no_external_scripts_and_bind_is_loopback(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    server, thread, base = _serve(path, tmp_path)
    try:
        html = urllib.request.urlopen(base + "/").read().decode("utf-8")
        vendor = urllib.request.urlopen(
            base + "/vendor/lightweight-charts.standalone.production.js").read()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert b"TradingView Lightweight Charts" in vendor[:200]
    assert 'src="/vendor/lightweight-charts.standalone.production.js"' in html
    assert not re.search(r'<script[^>]+src=["\']https?://', html, re.I)
    assert "T0(2026-10-07 09:00 KST) 이후 거래가 표시됩니다" in html
    with pytest.raises(ValueError, match="127.0.0.1"):
        make_server(path, tmp_path, host="0.0.0.0", port=0)


def test_replay_database_supplies_chart_and_ledger_data() -> None:
    replay = Path(__file__).resolve().parents[1] / "out/paper_system_build_p1_20261006/replay/live.sqlite"
    if not replay.exists():
        pytest.skip("replay database not present")
    server, thread, base = _serve(replay, replay.parent, books=("C1", "F3", "E1", "C4"))
    try:
        candles = _get(base, "/api/candles?tf=1h")
        trades = _get(base, "/api/trades?book=H1")
        markers = _get(base, "/api/markers?book=H1")
        status = _get(base, "/api/status")
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert candles["rows"] and len(candles["rows"]) <= 2_000
    pessimistic = [row for row in trades["rows"] if row["boundary"] == "PESS"]
    assert trades["rows"] and len(markers["rows"]) == 2 * len(pessimistic)
    assert status["market"]["latest_price"] == candles["latest_price"]


def test_buy_hold_benchmark_starts_at_t0() -> None:
    import sqlite3

    from btcusdt_quant.paper.dashboard.server import _performance

    prices = [{"time_utc": "2026-10-05T00:00:00Z", "open": 100.0, "close": 110.0},
              {"time_utc": "2026-10-07T00:00:00Z", "open": 110.0, "close": 121.0}]
    connection = sqlite3.connect(":memory:")
    for table in ("daily_pnl", "trades"):
        connection.execute(f"create table {table} (book text, boundary text, date text, net_bps real, entry_time text)")
    before = _performance(connection, "C1", prices[:1], "2026-10-07T00:00:00Z")["summary"]
    after = _performance(connection, "C1", prices, "2026-10-07T00:00:00Z")["summary"]
    assert before["buy_hold_bps"] is None and before["vs_buy_hold_bps"] is None
    assert round(after["buy_hold_bps"], 6) == round(float(np.log(121 / 110) * 10_000), 6)
