from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper.collector import (BOOK_WS_URL, Collector, parse_ws_kline,
                                           reduce_book_ticker)
from btcusdt_quant.paper.config import PaperConfig
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper import rules
from btcusdt_quant.paper.store import PaperStore


def test_ws_closed_bar_only() -> None:
    message = {"k": {"t": 0, "o": "1", "h": "2", "l": ".5", "c": "1.5",
                       "v": "3", "q": "4", "n": 5, "V": "1", "Q": "2", "x": False}}
    assert parse_ws_kline(message) is None
    message["k"]["x"] = True
    assert parse_ws_kline(json.dumps(message))["close"] == 1.5


def test_collector_recorded_responses_and_gap(tmp_path) -> None:
    start = pd.Timestamp("2026-07-01T00:00:00Z")
    kline = lambda minute: [int((start + pd.Timedelta(minutes=minute)).timestamp() * 1000),
        "1", "2", ".5", "1.5", "3", 0, "4", 5, "1", "2", 0]
    responses = {
        "/fapi/v1/klines": [kline(0), kline(2)],
        "/fapi/v1/premiumIndexKlines": [kline(0)],
        "/futures/data/globalLongShortAccountRatio": [{"timestamp": int(start.timestamp()*1000),
            "longShortRatio": "1.1", "longAccount": ".52", "shortAccount": ".48"}],
        "/fapi/v1/fundingRate": [{"fundingTime": int(start.timestamp()*1000),
                                   "fundingRate": ".0001"}],
    }

    class Client:
        def get(self, path, parameters):
            return responses[path]

    with PaperStore(tmp_path / "live.sqlite") as store:
        collector = Collector(PaperEngine(store), tmp_path / "raw", Client())
        result = collector.collect_once(start + pd.Timedelta(minutes=4))
        assert result == {"klines": 2, "premium": 1, "ls_ratio": 1, "funding": 1}
        assert store.frame("collector_health").gaps.tolist() == [0, 1]
        assert len(store.frame("funding")) == 1
    assert list((tmp_path / "raw").glob("*.jsonl.gz"))


def test_ls_ratio_pages_from_cursor_after_long_outage(tmp_path) -> None:
    # The real endpoint returns the latest rows when endTime is missing; a 3-day outage must still fill.
    start = pd.Timestamp("2026-10-01T00:00:00Z")
    now = start + pd.Timedelta(days=3)
    every = [int((start + pd.Timedelta(minutes=5 * i)).timestamp() * 1000) for i in range(864)]
    calls = []

    class Client:
        def get(self, path, parameters):
            if path == "/futures/data/globalLongShortAccountRatio":
                calls.append(parameters)
                assert "endTime" in parameters
                rows = [t for t in every if parameters["startTime"] <= t <= parameters["endTime"]]
                return [{"timestamp": t, "longShortRatio": "1.1", "longAccount": ".52",
                         "shortAccount": ".48"} for t in rows[:parameters["limit"]]]
            return []

    with PaperStore(tmp_path / "live.sqlite") as store:
        store.set_meta("last_ls_timestamp", (start - pd.Timedelta(minutes=5)).isoformat())
        Collector(PaperEngine(store), tmp_path / "raw", Client()).collect_once(now)
        stored = pd.to_datetime(store.frame("ls_ratio").timestamp, utc=True)
        assert len(stored) == 864 and stored.min() == start
        assert len(calls) == 2
        assert store.get_meta("last_ls_timestamp") == pd.to_datetime(every[-1], unit="ms", utc=True).isoformat()


def test_funding_normalization_rejects_bad_time(tmp_path) -> None:
    with PaperStore(tmp_path / "live.sqlite") as store:
        engine = PaperEngine(store)
        engine.store_funding("2026-07-01T00:00:00.007Z", .0001)
        assert store.frame("funding").time.tolist() == ["2026-07-01T00:00:00+00:00"]
        with pytest.raises(ValueError, match="60s"):
            engine.store_funding("2026-07-01T00:02:00Z", .0001)


def test_book_ticker_reducer_matches_research_definition() -> None:
    from out.build_spread_features import reduce_chunk

    minute = pd.Timestamp("2026-10-01T00:00:00Z")
    rows = [
        {"transaction_time": int((minute + pd.Timedelta(seconds=i)).timestamp() * 1000),
         "best_bid_price": bid, "best_bid_qty": bq,
         "best_ask_price": ask, "best_ask_qty": aq}
        for i, bid, bq, ask, aq in [(1, 100, 2, 101, 1), (2, 100.5, 1, 101, 3),
                                    (3, 102, 1, 101, 1)]
    ]
    actual = reduce_book_ticker(rows)
    partial = reduce_chunk(pd.DataFrame(rows)).iloc[0]
    count = float(partial.quote_update_count)
    mean = float(partial.spread_sum / count)
    expected = {"spread_bps_mean": mean, "spread_bps_max": float(partial.spread_max),
                "spread_bps_std": float(np.sqrt(max(partial.spread_sqsum / count - mean ** 2, 0))),
                "top_imbalance_mean": float(partial.imbalance_sum / count),
                "quote_update_count": int(count)}
    for name, value in expected.items():
        assert actual[name] == pytest.approx(value)
    assert actual["spread_valid"] == 1


def test_book_stream_failure_does_not_stop_kline_stream(tmp_path) -> None:
    stamp = pd.Timestamp.now(tz="UTC").floor("min") - pd.Timedelta(minutes=1)
    message = json.dumps({"e": "kline", "k": {"t": int(stamp.timestamp() * 1000),
        "o": "1", "h": "2", "l": ".5", "c": "1.5", "v": "3", "q": "4",
        "n": 5, "V": "1", "Q": "2", "x": True}})

    class KlineSocket:
        def __init__(self):
            self.first = True
            self.closed = False

        def recv(self):
            if self.first:
                self.first = False
                return message
            while not self.closed:
                time.sleep(.01)
            raise OSError("closed")

        def close(self):
            self.closed = True

    def factory(url, timeout):
        if url == BOOK_WS_URL:
            raise OSError("book stream down")
        return KlineSocket()

    config = PaperConfig(sqlite_path=str(tmp_path / "live.sqlite"),
                         websocket_reconnect_max_seconds=.01)
    with PaperStore(config.sqlite_path) as store:
        collector = Collector(PaperEngine(store, config), tmp_path / "raw",
                              websocket_factory=factory)
        collector.start_streams()
        until = time.time() + 3
        while (store.frame("klines_1m").empty or
               store.frame("collector_health", "source='ws_book_error'").empty) and time.time() < until:
            time.sleep(.02)
        collector.close()
        assert len(store.frame("klines_1m")) == 1
        errors = store.frame("collector_health", "source='ws_book_error'")
        assert len(errors) == 1 and errors.status.iloc[0].startswith("ERROR:OSError")


def test_ls_rest_end_label_is_strictly_prior_and_book_is_not_rule_input() -> None:
    bars = pd.DataFrame({"decision_time": pd.to_datetime(["2026-10-01T00:05:00Z"])})
    features = pd.DataFrame({"open_time": pd.to_datetime([
        "2026-10-01T00:00:00Z", "2026-10-01T00:05:00Z"]),
        "global_ls_account": [1.0, 999.0], "source": ["rest", "rest"]})
    assert rules._strict_prior_feature(bars, features, "global_ls_account").tolist() == [1.0]
    assert "book_ticker_1m" not in rules.RULE_INPUT_COLUMNS


def test_premium_uses_own_cursor_when_websocket_advanced_klines(tmp_path) -> None:
    # Live bug: the WebSocket moved the kline cursor to the open minute, so premium was never stored.
    start = pd.Timestamp("2026-10-06T04:53:00Z")
    now = start + pd.Timedelta(minutes=10, seconds=5)
    requested = {}

    class Client:
        def get(self, path, parameters):
            if path == "/fapi/v1/premiumIndexKlines":
                requested["startTime"] = parameters["startTime"]
                return [[int((start + pd.Timedelta(minutes=i)).timestamp() * 1000), "0", "0", "0", "0.0001"]
                        for i in range(1, 11)]
            return []

    with PaperStore(tmp_path / "live.sqlite") as store:
        store.set_meta("last_processed_minute", (now.floor("min") - pd.Timedelta(minutes=1)).isoformat())
        store.set_meta("last_premium_minute", start.isoformat())
        Collector(PaperEngine(store), tmp_path / "raw", Client()).collect_once(now)
        stored = store.frame("premium_1m")
        assert requested["startTime"] == int((start + pd.Timedelta(minutes=1)).timestamp() * 1000)
        assert len(stored) == 9  # the 05:03 bar is still open at 05:03:05
        assert store.get_meta("last_premium_minute") == (start + pd.Timedelta(minutes=9)).isoformat()
