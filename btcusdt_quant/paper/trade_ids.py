"""Readable trade ids for the paper `trades` table: "<book>-<YYYYMMDD>-<HHMMSS>-<mmm>" from entry_time UTC.

PESS and OPT rows of one trade share the id (boundary tells them apart). The id is set by a SQLite trigger, not by
the writers: every insert path (engine, catalog, g3, ax switch, old code still running during a rollout) gets it,
and the G3-hashed sources (g3.py, store.py) stay byte-identical. Kept out of store.py on purpose: G3 hashes it.

migrate() is idempotent and safe on every startup: add column, backfill NULL ids, unique index, trigger, view.
leverage_trades is not touched: no boundary column, keyed UNIQUE(book, entry_time).
"""
from __future__ import annotations

import sqlite3

# entry_time is utc_text() ISO ("2026-10-10T14:26:00+00:00"); SQLite date functions normalize the offset to UTC
TRADE_ID_SQL = ("{p}book || '-' || strftime('%Y%m%d-%H%M%S', {p}entry_time) || '-' || "
                "substr(strftime('%f', {p}entry_time), 4, 3)")

STATEMENTS = (
    f"UPDATE trades SET trade_id = {TRADE_ID_SQL.format(p='')} WHERE trade_id IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_trade_id_boundary ON trades(trade_id, boundary)",
    "CREATE TRIGGER IF NOT EXISTS trg_trades_trade_id AFTER INSERT ON trades WHEN NEW.trade_id IS NULL BEGIN "
    f"UPDATE trades SET trade_id = {TRADE_ID_SQL.format(p='NEW.')} WHERE id = NEW.id; END",
    "CREATE VIEW IF NOT EXISTS trades_pess AS SELECT * FROM trades WHERE boundary = 'PESS'",
)


def migrate(connection: sqlite3.Connection) -> int:
    """Apply the trade_id schema in one IMMEDIATE transaction; returns the number of rows backfilled."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        if not any(row[1] == "trade_id" for row in connection.execute("PRAGMA table_info(trades)")):
            connection.execute("ALTER TABLE trades ADD COLUMN trade_id TEXT")
        backfilled = connection.execute(STATEMENTS[0]).rowcount
        for statement in STATEMENTS[1:]:
            connection.execute(statement)
    except BaseException:
        connection.rollback()
        raise
    connection.commit()
    return backfilled


__all__ = ["TRADE_ID_SQL", "migrate"]
