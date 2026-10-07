from __future__ import annotations

import json
import re
import time
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper import rules
from btcusdt_quant.paper.dashboard import make_server
from btcusdt_quant.paper.dashboard.server import (
    _condition_inputs, _condition_value, _connect_ro, _display_condition_details,
)
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


def test_leverage_book_dashboard_payload(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    stamp = "2026-10-06T03:00:00+00:00"
    with PaperStore(path) as store:
        store.set_meta("last_processed_minute", stamp)
        store.upsert("leverage_state", {"book": "C1_x3", "source_book": "C1",
            "status": "RUNNING", "balance_usd": 112.0, "cumulative_pnl_usd": 12.0,
            "cumulative_return_pct": 12.0, "max_drawdown_usd": 5.0,
            "max_drawdown_pct": 4.5, "liquidated_at": None, "updated_at": stamp})
        store.upsert("leverage_positions", {"book": "C1_x3", "source_book": "C1",
            "side": 1, "candidate": "F3", "entry_time": stamp, "entry_price": 100.0,
            "mark_price": 105.0, "notional_usd": 336.0, "margin_usd": 112.0,
            "liquidation_price": 67.1, "liquidation_distance_pct": 36.1,
            "unrealized_pnl_usd": 16.7, "balance_usd": 112.0, "updated_at": stamp})
        store.upsert("leverage_daily", {"book": "C1_x3", "date": "2026-10-06",
            "balance_usd": 112.0, "day_pnl_usd": 12.0, "max_drawdown_usd": 5.0,
            "max_drawdown_pct": 4.5})
    server, thread, base = _serve(path, tmp_path, books=("C1",), start_time=stamp)
    try:
        books = _get(base, "/api/books")["rows"]
        performance = _get(base, "/api/performance?book=C1_x3")
        positions = _get(base, "/api/positions?book=C1_x3")["rows"]
    finally:
        server.shutdown(); server.server_close(); thread.join()
    leveraged = next(row for row in books if row["book"] == "C1_x3")
    assert leveraged["display_book"] == "C1 ×3" and leveraged["balance_usd"] == 112.0
    assert performance["summary"]["leverage"] and performance["summary"]["status"] == "RUNNING"
    assert positions[0]["liquidation_price"] == 67.1


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
        conditions = _get(base, "/api/conditions?book=C1&tf=5m")
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
    assert conditions["schema_version"] == 3 and conditions["book"] == "C1"
    assert conditions["tf"] == "5m" and len(conditions["legs"]) == 2
    assert conditions["summary"]["estimate_label"] == "현재까지 데이터 기준"
    assert {leg["kind"] for leg in conditions["legs"]} == {"contrarian", "breakout"}
    assert all({"long_account_pct", "upper_pct", "lower_pct", "distance_to_short",
                "distance_to_long"} <= set(leg) for leg in conditions["legs"])
    assert [(row["kind"], row["price"]) for row in markers["rows"]] == [
        ("entry", 101.5), ("exit", 109.5)]
    assert all(row["trade_id"] == 1 and row["net_bps"] == -14 for row in markers["rows"])


def test_open_position_entry_is_marked_on_chart(tmp_path) -> None:
    # Live bug: markers came only from closed trades, so an open entry never showed on the chart.
    path = tmp_path / "live.sqlite"
    stamp = "2026-07-01T00:05:00+00:00"
    with PaperStore(path) as store:
        store.upsert("positions", {"book": "C1", "side": 1, "candidate": rules.F3,
            "entry_time": stamp, "entry_price": 101.5, "exit_time": "2026-07-02T00:05:00+00:00",
            "remaining_minutes": 1400, "unrealized_bps": -5.0, "updated_at": stamp})
    server, thread, base = _serve(path, tmp_path, books=("C1",), start_time="2026-07-01T00:00:00Z")
    try:
        markers = _get(base, "/api/markers?book=C1")["rows"]
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert [(row["kind"], row["side"], row["price"], row["exit_reason"]) for row in markers] == [
        ("entry", 1, 101.5, "보유 중")]
    assert markers[0]["time"] == int(pd.Timestamp(stamp).timestamp())


def test_condition_ratio_percent_and_both_distances() -> None:
    row = pd.Series({
        "decision_time": pd.Timestamp("2026-10-06T01:00:00Z"),
        "global_ls_account": 1.06, "lower_threshold": 0.984, "upper_threshold": 1.83,
        "volume_zscore": np.nan, "prior_high_20": np.nan, "prior_low_20": np.nan,
        "close": 100.0, "volume": 10.0, "required_volume": np.nan, "side": 0,
    })
    value = _condition_value(row)
    assert value is not None
    assert value["long_account_pct"] == pytest.approx(1.06 / 2.06 * 100)
    assert value["upper_pct"] == pytest.approx(1.83 / 2.83 * 100)
    assert value["lower_pct"] == pytest.approx(.984 / 1.984 * 100)
    assert value["distance_to_short"] == pytest.approx({
        "ratio": 1.83 - 1.06,
        "pct_points": 1.83 / 2.83 * 100 - 1.06 / 2.06 * 100,
    })
    assert value["distance_to_long"] == pytest.approx({
        "ratio": 1.06 - .984,
        "pct_points": 1.06 / 2.06 * 100 - .984 / 1.984 * 100,
    })


def test_breakout_required_volume_hits_z3_and_prior_low_is_shifted() -> None:
    frame = pd.DataFrame({
        "volume": np.linspace(10.0, 31.0, 22),
        "low": np.array([100, 98, 99, 97, 96, 95, 94, 93, 92, 91, 90,
                         89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79], dtype=float),
    })
    actual = _display_condition_details(frame, rules.E1)
    required = actual.required_volume.iloc[19]
    window = np.r_[frame.volume.iloc[:19].to_numpy(), required]
    zscore = (required - window.mean()) / window.std(ddof=0)
    assert zscore == pytest.approx(3.0, abs=1e-9)
    expected_low = frame.low.rolling(20).min().shift()
    pd.testing.assert_series_equal(actual.prior_low_20, expected_low,
                                   check_names=False)


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
    assert "T0 이후 거래가 표시됩니다" in html
    assert 'id="conditionPanes"' in html and 'id="conditionSummary"' in html
    assert "지난 정시 실제 사용" in html and "다음 정시 예상" in html
    assert "직전 20봉 저가(참고)" in html
    assert "롱 계정 비율 %" in html and "필요 거래량 BTC" in html
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
        started = time.perf_counter()
        c1 = _get(base, "/api/conditions?book=C1&tf=1h")
        c1_seconds = time.perf_counter() - started
        started = time.perf_counter()
        c4 = _get(base, "/api/conditions?book=C4&tf=1h")
        c4_seconds = time.perf_counter() - started
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert candles["rows"] and len(candles["rows"]) <= 2_000
    pessimistic = [row for row in trades["rows"] if row["boundary"] == "PESS"]
    assert trades["rows"] and len(markers["rows"]) == 2 * len(pessimistic)
    assert status["market"]["latest_price"] == candles["latest_price"]
    assert max(c1_seconds, c4_seconds) < 1.0
    assert {"generated_at", "data_cutoff", "source", "summary", "legs"} <= set(c1)
    assert {"holding", "holding_text", "next_decision_time", "next_decision_kst",
            "minutes_remaining", "estimate_label", "legs"} <= set(c1["summary"])
    assert {"decision_time", "global_ls_account", "lower_threshold", "upper_threshold",
            "volume_zscore", "prior_high_20", "close", "side", "condition_met",
            "direction", "signal_status", "signal_reason"} <= set(c1["legs"][0]["rows"][0])
    assert {"long_account_pct", "upper_pct", "lower_pct", "distance_to_short",
            "distance_to_long"} <= set(c1["summary"]["legs"][0]["last_decision"])
    actual = {leg["candidate"]: [(row["decision_time"], row["side"])
                                  for row in leg["rows"] if row["condition_met"]]
              for leg in c1["legs"] + c4["legs"]}
    with _connect_ro(replay) as connection:
        market, features, display_start, source = _condition_inputs(connection)
    assert source.endswith("frozen Q3 replay artifacts")
    for candidate in (rules.F3, rules.F3_W30, rules.E1):
        expected = rules.signals(market, features, candidate)
        expected = expected.loc[expected.bar_start.ge(display_start) & expected.side.ne(0)]
        assert actual[candidate] == [
            (row.decision_time.isoformat(), int(row.side))
            for row in expected.itertuples(index=False)]


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


def test_buy_hold_anchors_at_t0_minute_and_comparison_counts_open_position() -> None:
    import sqlite3

    from btcusdt_quant.paper.dashboard.server import _performance

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    for table in ("daily_pnl", "trades"):
        connection.execute(f"create table {table} (book text, boundary text, date text, net_bps real, entry_time text)")
    connection.execute("create table klines_1m (open_time text, open real, close real, closed integer)")
    connection.executemany("insert into klines_1m values (?,?,?,1)", [
        ("2026-10-06T02:59:00+00:00", 99.0, 99.0), ("2026-10-06T03:00:00+00:00", 100.0, 100.5)])
    connection.execute("create table positions (book text, side integer, unrealized_bps real)")
    connection.execute("insert into positions values ('C1', 1, -254.0)")
    # T0 falls inside the 2026-10-06 daily bar, which opens at 102 (before T0)
    prices = [{"time_utc": "2026-10-06T00:00:00Z", "open": 102.0, "close": 98.0}]
    summary = _performance(connection, "C1", prices, "2026-10-06T03:00:00Z")["summary"]
    buy_hold = float(np.log(98 / 100) * 10_000)
    assert round(summary["buy_hold_bps"], 6) == round(buy_hold, 6)
    assert summary["unrealized_bps"] == -254.0
    assert round(summary["vs_buy_hold_bps"], 6) == round(0.0 - 254.0 - buy_hold, 6)


@pytest.mark.parametrize("tf", ["1m", "5m", "15m", "1h", "4h", "1d"])
def test_default_candle_window_works_for_every_timeframe(tmp_path, tf) -> None:
    # The page requests candles without from/to; "1m"/"5m" must not be read as pandas month offsets.
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        for i in range(30):
            stamp = (pd.Timestamp("2026-07-01T00:00:00Z") + pd.Timedelta(minutes=i)).isoformat()
            store.upsert("klines_1m", {"open_time": stamp, "open": 1.0, "high": 1.0, "low": 1.0,
                                       "close": 1.0, "volume": 1.0, "source": "test",
                                       "received_at": stamp, "closed": 1})
    server, thread, base = _serve(path, tmp_path, books=("C1",))
    try:
        candles = _get(base, f"/api/candles?tf={tf}")
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert "error" not in candles and candles["rows"]


def test_forming_bar_is_display_only_and_merged_into_last_bucket(tmp_path) -> None:
    import json as _json

    path = tmp_path / "live.sqlite"
    start = pd.Timestamp("2026-07-01T00:00:00Z")
    with PaperStore(path) as store:
        for i in range(3):
            stamp = (start + pd.Timedelta(minutes=i)).isoformat()
            store.upsert("klines_1m", {"open_time": stamp, "open": 10.0, "high": 11.0, "low": 9.0,
                                       "close": 10.0, "volume": 1.0, "source": "test",
                                       "received_at": stamp, "closed": 1})
        store.set_meta("forming_kline", _json.dumps({
            "open_time": (start + pd.Timedelta(minutes=3)).isoformat(), "open": 10.0, "high": 15.0,
            "low": 10.0, "close": 14.0, "volume": 2.0, "updated_at": "2026-07-01T00:03:30+00:00"}))
        closed_rows = len(store.frame("klines_1m"))
    server, thread, base = _serve(path, tmp_path, books=("C1",))
    try:
        one = _get(base, "/api/candles?tf=1m")
        five = _get(base, "/api/candles?tf=5m")
        status = _get(base, "/api/status")
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert len(one["rows"]) == 4 and one["rows"][-1]["forming"] and one["rows"][-1]["close"] == 14.0
    assert len(five["rows"]) == 1 and five["rows"][0]["high"] == 15.0 and five["rows"][0]["volume"] == 5.0
    assert status["market"]["latest_price"] == 14.0
    assert closed_rows == 3


def test_conditions_two_year_cached_response_under_one_second(tmp_path) -> None:
    path = tmp_path / "two_year.sqlite"
    with PaperStore(path) as store:
        connection = store.connection
        connection.execute("BEGIN")
        connection.execute("""
            WITH RECURSIVE n(i) AS (VALUES(0) UNION ALL SELECT i+1 FROM n WHERE i<1051199)
            INSERT INTO klines_1m
            SELECT strftime('%Y-%m-%dT%H:%M:%S+00:00',1704067200+i*60,'unixepoch'),
                   10000+(i%1000),10001+(i%1000),9999+(i%1000),10000.5+(i%1000),
                   10+(i%60),0,0,0,0,'test',
                   strftime('%Y-%m-%dT%H:%M:%S+00:00',1704067200+i*60,'unixepoch'),1
            FROM n
        """)
        connection.execute("""
            WITH RECURSIVE n(i) AS (VALUES(0) UNION ALL SELECT i+1 FROM n WHERE i<210239)
            INSERT INTO ls_ratio
            SELECT strftime('%Y-%m-%dT%H:%M:%S+00:00',1704067200+i*300,'unixepoch'),
                   1.0+(i%200)/100.0,NULL,NULL,'archive',
                   strftime('%Y-%m-%dT%H:%M:%S+00:00',1704067200+i*300,'unixepoch')
            FROM n
        """)
        connection.commit()
    server, thread, base = _serve(path, tmp_path, books=("C1",))
    try:
        started = time.perf_counter()
        payload = _get(base, "/api/conditions?book=C1&tf=1h")
        elapsed = time.perf_counter() - started
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert elapsed < 1.0
    assert len(payload["legs"]) == 2
    assert all(len(leg["rows"]) == 17_520 for leg in payload["legs"])


def test_public_dashboard_never_shows_secret_fragments(tmp_path, monkeypatch) -> None:
    # The dashboard is shared publicly through a tunnel; even masked key/token fragments must not appear.
    from btcusdt_quant.paper.dashboard import server as dashboard_server

    monkeypatch.setattr(dashboard_server, "credential_status",
                        lambda: {"loaded": True, "api_key": "abcd...wxyz", "api_secret": "efgh...stuv"})
    monkeypatch.setattr(dashboard_server, "telegram_status",
                        lambda: {"configured": True, "token": "8974...HQac",
                                 "label": "텔레그램: 설정됨 (8974...HQac)"})
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    server, thread, base = _serve(path, tmp_path, books=("C1",))
    try:
        bodies = [urllib.request.urlopen(base + route).read().decode("utf-8")
                  for route in ("/api/health", "/api/status")]
    finally:
        server.shutdown(); server.server_close(); thread.join()
    for body in bodies:
        assert "wxyz" not in body and "stuv" not in body and "HQac" not in body


def test_buy_hold_empty_before_book_start() -> None:
    import sqlite3

    from btcusdt_quant.paper.dashboard.server import _performance

    connection = sqlite3.connect(":memory:")
    for table in ("daily_pnl", "trades"):
        connection.execute(f"create table {table} (book text, boundary text, date text, net_bps real, entry_time text)")
    connection.execute("create table klines_1m (open_time text, open real, close real, closed integer)")
    connection.execute("insert into klines_1m values ('2026-10-07T05:00:00+00:00', 100, 100, 1)")
    prices = [{"time_utc": "2026-10-07T00:00:00Z", "open": 102.0, "close": 98.0}]
    summary = _performance(connection, "K09", prices, "2026-10-07T06:00:00Z")["summary"]
    assert summary["buy_hold_bps"] is None and summary["vs_buy_hold_bps"] is None
