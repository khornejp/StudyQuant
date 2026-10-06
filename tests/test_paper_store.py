from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from btcusdt_quant.paper.store import PaperStore


def _bar(time: str, close: float = 2.0) -> dict[str, object]:
    return {"open_time": pd.Timestamp(time).isoformat(), "open": 1.0, "high": 3.0,
            "low": .5, "close": close, "volume": 4.0, "quote_volume": 5.0,
            "number_of_trades": 6, "taker_buy_base_volume": 2.0,
            "taker_buy_quote_volume": 2.5, "source": "archive",
            "received_at": pd.Timestamp(time).isoformat(), "closed": 1}


def test_store_wal_transaction_rollback_and_resume(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        assert store.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        with pytest.raises(RuntimeError):
            with store.transaction() as connection:
                store.upsert("klines_1m", _bar("2026-07-01T00:00:00Z"), connection)
                store.set_meta("last_processed_minute", "bad")
                raise RuntimeError("kill")
        assert store.frame("klines_1m").empty
        assert store.get_meta("last_processed_minute") is None
        with store.transaction() as connection:
            store.upsert("klines_1m", _bar("2026-07-01T00:00:00Z"), connection)
            connection.execute("INSERT INTO meta(key,value) VALUES(?,?)", (
                "last_processed_minute", "2026-07-01T00:00:00+00:00"))
    with PaperStore(path) as resumed:
        assert len(resumed.frame("klines_1m")) == 1
        assert resumed.get_meta("last_processed_minute") == "2026-07-01T00:00:00+00:00"
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    with pytest.raises(RuntimeError, match="unsupported schema version"):
        PaperStore(path)


def test_daily_parquet_export(tmp_path) -> None:
    with PaperStore(tmp_path / "live.sqlite") as store:
        store.upsert("klines_1m", _bar("2026-07-01T00:00:00Z"))
        store.upsert("klines_1m", _bar("2026-07-02T00:00:00Z", 9.0))
        store.upsert("book_ticker_1m", {"minute": "2026-07-01T00:00:00+00:00",
            "spread_bps_mean": 1, "spread_bps_max": 2, "spread_bps_std": .1,
            "top_imbalance_mean": .2, "quote_update_count": 3, "spread_valid": 1,
            "source": "ws", "received_at": "2026-07-01T00:01:00+00:00"})
        paths = store.export_day("2026-07-01", tmp_path / "daily")
    path = tmp_path / "daily" / "klines_1m" / "2026-07-01.parquet"
    assert path in paths
    result = pd.read_parquet(path)
    assert result.close.tolist() == [2.0]
    assert tmp_path / "daily" / "book_ticker_1m" / "2026-07-01.parquet" in paths
