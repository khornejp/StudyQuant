import sqlite3

import pytest

from btcusdt_quant.paper.store import PaperStore
from btcusdt_quant.paper.trade_ids import migrate

COLS = ("book,boundary,candidate,entry_time,exit_time,side,entry_price,exit_price,gross_bps,cost_bps,funding_bps,"
        "net_bps,hold_minutes,exit_reason")


def _insert(c, book, boundary, entry, verb="INSERT"):
    c.execute(f"{verb} INTO trades({COLS}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (book, boundary, "x", entry, "2026-10-10T15:00:00+00:00", -1, 1.0, 1.0, 0, 0, 0, 0, 1, "T"))


def _ids(c):
    return c.execute("SELECT book, boundary, entry_time, trade_id FROM trades ORDER BY id").fetchall()


def test_backfill_format_shared_id_idempotent_and_view(tmp_path):
    with PaperStore(tmp_path / "p.sqlite") as store:
        c = store.connection
        for boundary in ("PESS", "OPT"):
            _insert(c, "K07_k0.5_AX", boundary, "2026-10-10T14:26:00+00:00")
        _insert(c, "B1", "PESS", "2026-10-10T23:26:05.123000+09:00")      # non-UTC offset, milliseconds
        assert migrate(c) == 3
        rows = _ids(c)
        assert [r[3] for r in rows] == ["K07_k0.5_AX-20261010-142600-000"] * 2 + ["B1-20261010-142605-123"]
        assert migrate(c) == 0 and _ids(c) == rows                          # idempotent, ids unchanged
        assert c.execute("SELECT COUNT(*) FROM trades_pess").fetchone()[0] == 2
        assert {r[0] for r in c.execute("SELECT boundary FROM trades_pess")} == {"PESS"}
        assert c.execute("SELECT COUNT(*) FROM (SELECT trade_id, boundary FROM trades GROUP BY 1, 2 "
                         "HAVING COUNT(*) > 1)").fetchone()[0] == 0


def test_trigger_sets_id_on_every_insert_path_and_unique(tmp_path):
    with PaperStore(tmp_path / "p.sqlite") as store:
        c = store.connection
        assert migrate(c) == 0
        _insert(c, "G3_LONG", "PESS", "2026-10-10T03:59:00+00:00", "INSERT OR IGNORE")    # g3.py path
        _insert(c, "G3_LONG", "PESS", "2026-10-10T03:59:00+00:00", "INSERT OR IGNORE")    # ignored duplicate
        store.insert("trades", dict(zip(COLS.split(","), ("K13_AX", "OPT", "x", "2026-10-10T14:02:00+00:00",
                                                           "2026-10-10T15:00:00+00:00", 1, 1.0, 1.0, 0, 0, 0, 0, 1,
                                                           "T"))))                          # store.insert path
        assert [r[3] for r in _ids(c)] == ["G3_LONG-20261010-035900-000", "K13_AX-20261010-140200-000"]
        with pytest.raises(sqlite3.IntegrityError):     # UNIQUE(trade_id, boundary)
            c.execute(f"INSERT INTO trades({COLS},trade_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      ("K13_AX", "OPT", "x", "2026-10-10T14:03:00+00:00", "2026-10-10T15:00:00+00:00", 1, 1.0, 1.0,
                       0, 0, 0, 0, 1, "T", "K13_AX-20261010-140200-000"))
        with pytest.raises(sqlite3.IntegrityError):     # existing UNIQUE(book, boundary, entry_time) kept
            _insert(c, "K13_AX", "OPT", "2026-10-10T14:02:00+00:00")
