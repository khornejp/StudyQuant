"""SQLite WAL storage and daily parquet export for paper trading."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Mapping

import pandas as pd

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS klines_1m (
    open_time TEXT PRIMARY KEY, open REAL NOT NULL, high REAL NOT NULL,
    low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
    quote_volume REAL, number_of_trades INTEGER, taker_buy_base_volume REAL,
    taker_buy_quote_volume REAL, source TEXT NOT NULL, received_at TEXT NOT NULL,
    closed INTEGER NOT NULL CHECK (closed = 1)
);
CREATE TABLE IF NOT EXISTS premium_1m (
    open_time TEXT PRIMARY KEY, premium_index REAL NOT NULL,
    source TEXT NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ls_ratio (
    timestamp TEXT PRIMARY KEY, global_ls_account REAL NOT NULL,
    long_account REAL, short_account REAL, source TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS funding (
    time TEXT PRIMARY KEY, rate REAL NOT NULL, raw_calc_time TEXT NOT NULL,
    source TEXT NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, decision_time TEXT NOT NULL,
    entry_time TEXT NOT NULL, book TEXT NOT NULL, candidate TEXT NOT NULL,
    side INTEGER NOT NULL, accepted INTEGER NOT NULL, reason TEXT,
    UNIQUE(book, candidate, decision_time)
);
CREATE TABLE IF NOT EXISTS positions (
    book TEXT PRIMARY KEY, side INTEGER NOT NULL, candidate TEXT,
    entry_time TEXT, entry_price REAL, exit_time TEXT, remaining_minutes INTEGER,
    unrealized_bps REAL NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book TEXT NOT NULL,
    boundary TEXT NOT NULL, candidate TEXT, entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL, side INTEGER NOT NULL, entry_price REAL NOT NULL,
    exit_price REAL NOT NULL, gross_bps REAL NOT NULL, cost_bps REAL NOT NULL,
    funding_bps REAL NOT NULL, net_bps REAL NOT NULL, hold_minutes REAL NOT NULL,
    exit_reason TEXT NOT NULL, UNIQUE(book, boundary, entry_time)
);
CREATE TABLE IF NOT EXISTS daily_pnl (
    book TEXT NOT NULL, boundary TEXT NOT NULL, date TEXT NOT NULL,
    gross_bps REAL NOT NULL, cost_bps REAL NOT NULL, funding_bps REAL NOT NULL,
    net_bps REAL NOT NULL, PRIMARY KEY(book, boundary, date)
);
CREATE TABLE IF NOT EXISTS leverage_state (
    book TEXT PRIMARY KEY, source_book TEXT NOT NULL, status TEXT NOT NULL,
    balance_usd REAL NOT NULL, cumulative_pnl_usd REAL NOT NULL,
    cumulative_return_pct REAL NOT NULL, max_drawdown_usd REAL NOT NULL,
    max_drawdown_pct REAL NOT NULL, liquidated_at TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leverage_positions (
    book TEXT PRIMARY KEY, source_book TEXT NOT NULL, side INTEGER NOT NULL,
    candidate TEXT, entry_time TEXT NOT NULL, entry_price REAL NOT NULL,
    mark_price REAL NOT NULL,
    notional_usd REAL NOT NULL, margin_usd REAL NOT NULL,
    liquidation_price REAL NOT NULL, liquidation_distance_pct REAL NOT NULL,
    unrealized_pnl_usd REAL NOT NULL, balance_usd REAL NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leverage_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book TEXT NOT NULL,
    source_book TEXT NOT NULL, candidate TEXT, entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL, side INTEGER NOT NULL, entry_price REAL NOT NULL,
    exit_price REAL NOT NULL, notional_usd REAL NOT NULL, margin_usd REAL NOT NULL,
    initial_liquidation_price REAL NOT NULL, liquidation_price REAL NOT NULL,
    max_adverse_pnl_usd REAL NOT NULL, liquidated INTEGER NOT NULL,
    gross_pnl_usd REAL NOT NULL, cost_usd REAL NOT NULL, funding_usd REAL NOT NULL,
    pnl_usd REAL NOT NULL, balance_before_usd REAL NOT NULL,
    balance_after_usd REAL NOT NULL, hold_minutes REAL NOT NULL,
    exit_reason TEXT NOT NULL, UNIQUE(book, entry_time)
);
CREATE TABLE IF NOT EXISTS leverage_daily (
    book TEXT NOT NULL, date TEXT NOT NULL, balance_usd REAL NOT NULL,
    day_pnl_usd REAL NOT NULL, max_drawdown_usd REAL NOT NULL,
    max_drawdown_pct REAL NOT NULL, PRIMARY KEY(book, date)
);
CREATE TABLE IF NOT EXISTS leverage_skips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book TEXT NOT NULL,
    source_book TEXT NOT NULL, entry_time TEXT NOT NULL, candidate TEXT,
    reason TEXT NOT NULL, UNIQUE(book, entry_time)
);
CREATE TABLE IF NOT EXISTS collector_health (
    minute TEXT NOT NULL, source TEXT NOT NULL, lag_ms REAL,
    gaps INTEGER NOT NULL DEFAULT 0, retries INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL, PRIMARY KEY(minute, source)
);
CREATE TABLE IF NOT EXISTS book_ticker_1m (
    minute TEXT PRIMARY KEY, spread_bps_mean REAL, spread_bps_max REAL,
    spread_bps_std REAL, top_imbalance_mean REAL, quote_update_count INTEGER NOT NULL,
    spread_valid INTEGER NOT NULL, source TEXT NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT,
    sent_at TEXT, last_error TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT NOT NULL,
    event_time TEXT NOT NULL, column_name TEXT NOT NULL, live_value TEXT,
    archive_value TEXT, detected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_book_time ON signals(book, decision_time);
CREATE INDEX IF NOT EXISTS idx_trades_book_time ON trades(book, entry_time);
CREATE INDEX IF NOT EXISTS idx_leverage_trades_book_time
    ON leverage_trades(book, entry_time);
CREATE INDEX IF NOT EXISTS idx_notifications_delivery
    ON notifications(status, next_attempt_at, id);
"""

DATASET_TABLE = {
    "klines_1m": "klines_1m",
    "premium_1m": "premium_1m",
    "ls_ratio_5m": "ls_ratio",
    "funding": "funding",
    "book_ticker_1m": "book_ticker_1m",
}


def utc_text(value: object) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return stamp.tz_convert("UTC").isoformat()


class PaperStore:
    """Small synchronous store; one writer and concurrent WAL readers."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript(SCHEMA)
        current = self.get_meta("schema_version")
        if current is not None and int(current) != SCHEMA_VERSION:
            self.connection.close()
            raise RuntimeError(f"unsupported schema version: {current}")
        self.set_meta("schema_version", str(SCHEMA_VERSION))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "PaperStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit all minute effects together or roll all back."""
        if self.connection.in_transaction:
            raise RuntimeError("nested transactions are not supported")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except BaseException:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_meta(self, key: str, value: object) -> None:
        self.connection.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        if not self.connection.in_transaction:
            self.connection.commit()

    def upsert(self, table: str, row: Mapping[str, object],
               connection: sqlite3.Connection | None = None) -> None:
        if table not in {"klines_1m", "premium_1m", "ls_ratio", "funding",
                         "positions", "daily_pnl", "collector_health", "book_ticker_1m",
                         "leverage_state", "leverage_positions", "leverage_daily"}:
            raise ValueError(f"upsert table not allowed: {table}")
        values = dict(row)
        columns = list(values)
        sql = (f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES "
               f"({','.join('?' for _ in columns)})")
        target = connection or self.connection
        target.execute(sql, tuple(values[name] for name in columns))
        if connection is None:
            target.commit()

    def insert(self, table: str, row: Mapping[str, object],
               connection: sqlite3.Connection | None = None) -> int:
        if table not in {"signals", "trades", "revisions", "leverage_trades",
                         "leverage_skips"}:
            raise ValueError(f"insert table not allowed: {table}")
        values = dict(row)
        columns = list(values)
        target = connection or self.connection
        cursor = target.execute(
            f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) VALUES "
            f"({','.join('?' for _ in columns)})",
            tuple(values[name] for name in columns))
        if connection is None:
            target.commit()
        return int(cursor.lastrowid or 0)

    def frame(self, table: str, where: str = "", parameters: Iterable[object] = ()) -> pd.DataFrame:
        allowed = set(DATASET_TABLE.values()) | {
            "signals", "positions", "trades", "daily_pnl", "collector_health", "revisions",
            "notifications", "meta", "leverage_state", "leverage_positions",
            "leverage_trades", "leverage_daily", "leverage_skips"}
        if table not in allowed:
            raise ValueError(f"read table not allowed: {table}")
        suffix = f" WHERE {where}" if where else ""
        return pd.read_sql_query(f"SELECT * FROM {table}{suffix}", self.connection,
                                 params=tuple(parameters))

    def export_day(self, day: date | str, root: str | Path) -> list[Path]:
        """Atomically export one UTC day with stable research-facing names."""
        day_text = str(day)
        start = pd.Timestamp(day_text, tz="UTC")
        end = start + pd.Timedelta(days=1)
        start_text, end_text = start.isoformat(), end.isoformat()
        destination = Path(root)
        outputs: list[Path] = []
        for dataset, table in DATASET_TABLE.items():
            time_column = ("timestamp" if table == "ls_ratio" else "time" if table == "funding"
                           else "minute" if table == "book_ticker_1m" else "open_time")
            frame = self.frame(table, f"{time_column}>=? AND {time_column}<?",
                               (start_text, end_text))
            if frame.empty:
                continue
            rename = {"timestamp": "open_time", "time": "funding_time", "rate": "funding_rate"}
            frame = frame.rename(columns={key: value for key, value in rename.items() if key in frame})
            path = destination / dataset / (f"{day_text[:7]}.parquet" if dataset == "funding"
                                             else f"{day_text}.parquet")
            path.parent.mkdir(parents=True, exist_ok=True)
            if dataset == "funding" and path.exists():
                frame = pd.concat([pd.read_parquet(path), frame], ignore_index=True)
                frame = frame.drop_duplicates("funding_time", keep="last").sort_values("funding_time")
            temporary = path.with_suffix(path.suffix + ".tmp")
            frame.to_parquet(temporary, index=False)
            temporary.replace(path)
            outputs.append(path)
        ledger = self.frame("trades", "entry_time>=? AND entry_time<?", (start_text, end_text))
        daily = self.frame("daily_pnl", "date=?", (day_text,))
        for book_name in sorted(set(ledger.get("book", ())) | set(daily.get("book", ()))):
            for suffix, frame in (("trades", ledger.loc[ledger.book.eq(book_name)]),
                                  ("daily", daily.loc[daily.book.eq(book_name)])):
                path = destination / "ledger" / f"{book_name}_{suffix}.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
                combined = pd.concat([existing, frame], ignore_index=True).drop_duplicates()
                temporary = path.with_suffix(path.suffix + ".tmp")
                combined.to_parquet(temporary, index=False)
                temporary.replace(path)
                outputs.append(path)
        self.set_meta("last_daily_export", json.dumps({"day": day_text,
                                                       "files": [str(path) for path in outputs]}))
        return outputs


__all__ = ["PaperStore", "SCHEMA_VERSION", "utc_text"]
