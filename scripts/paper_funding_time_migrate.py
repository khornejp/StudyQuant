"""R2-54: move legacy rounded funding.time to the actual raw_calc_time (stopped DB only; dry run by default).

Run with paper_run.py and paper_catalog.py stopped (both locks are taken). --apply backs the DB up with the sqlite
backup API, checks the backup with PRAGMA integrity_check, refuses on primary-key collisions, then updates in one
transaction. The JSON report lists the affected rows and a funding ledger diff: every stored trade (trades: its own
PESS/OPT boundary; leverage_trades: PESS) repriced with book.reprice on the funding events before vs after.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from btcusdt_quant.paper import book  # noqa: E402
from btcusdt_quant.paper.store import exclusive_lock  # noqa: E402


def _funding(connection: sqlite3.Connection, column: str) -> pd.DataFrame:
    frame = pd.read_sql_query(f"SELECT {column} AS time, rate FROM funding", connection)
    frame["time"] = pd.to_datetime(frame.time, utc=True, format="mixed").astype("datetime64[ns, UTC]")
    return frame.sort_values("time", kind="stable").drop_duplicates("time", keep="last").reset_index(drop=True)


def ledger_diff(connection: sqlite3.Connection) -> dict[str, object]:
    before, after = _funding(connection, "time"), _funding(connection, "raw_calc_time")
    legs = [pd.read_sql_query("SELECT 'trades' AS ledger, id, book, boundary, entry_time, exit_time, side, "
                              "entry_price, exit_price FROM trades", connection)]
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name='leverage_trades'").fetchone():
        legs.append(pd.read_sql_query("SELECT 'leverage_trades' AS ledger, id, book, 'PESS' AS boundary, entry_time, "
                                      "exit_time, side, entry_price, exit_price FROM leverage_trades", connection))
    trades = pd.concat([leg for leg in legs if len(leg)] or legs[:1], ignore_index=True)
    rows = []
    for boundary, group in trades.groupby("boundary"):
        old = book.reprice(group, before, boundary, 0.0)
        new = book.reprice(group, after, boundary, 0.0)
        changed = (old.funding_bps.sub(new.funding_bps).abs() > 1e-12) | old.funding_event_count.ne(
            new.funding_event_count)
        for index in group.index[changed.to_numpy()]:
            rows.append({"ledger": group.ledger[index], "id": int(group.id[index]), "book": group.book[index],
                         "boundary": boundary, "entry_time": str(group.entry_time[index]),
                         "exit_time": str(group.exit_time[index]), "side": int(group.side[index]),
                         "before_funding_bps": float(old.funding_bps[index]),
                         "after_funding_bps": float(new.funding_bps[index]),
                         "before_events": int(old.funding_event_count[index]),
                         "after_events": int(new.funding_event_count[index])})
    return {"trades_checked": len(trades), "changed": len(rows), "rows": rows,
            "method": "book.reprice funding_bps/event count, cost 0, stored legs; not a full strategy replay"}


def run(db: str | Path, backup: str | Path, apply: bool = False) -> dict[str, object]:
    db, backup = Path(db), Path(backup)
    with ExitStack() as locks:
        for suffix in (".run.lock", ".catalog.lock"):           # services must be stopped
            locks.enter_context(exclusive_lock(db.with_suffix(suffix)))
        connection = sqlite3.connect(db, isolation_level=None)
        try:
            affected = [dict(zip(("time", "raw_calc_time", "rate", "source"), row)) for row in connection.execute(
                "SELECT time, raw_calc_time, rate, source FROM funding WHERE time<>raw_calc_time ORDER BY time")]
            collisions = [row[0] for row in connection.execute(
                "SELECT f.raw_calc_time FROM funding f JOIN funding g ON g.time=f.raw_calc_time AND g.rowid<>f.rowid "
                "WHERE f.time<>f.raw_calc_time")]
            report: dict[str, object] = {"db": str(db), "affected": len(affected), "rows": affected,
                                         "collisions": collisions, "ledger_diff": ledger_diff(connection),
                                         "applied": False}
            if not apply:
                return report
            if collisions:
                raise SystemExit(f"funding time collision, not applied: {collisions[:5]}")
            if backup.exists():
                raise SystemExit(f"backup exists, refusing to overwrite: {backup}")
            with sqlite3.connect(backup) as target:
                connection.backup(target)
                report["backup_integrity"] = target.execute("PRAGMA integrity_check").fetchone()[0]
            if report["backup_integrity"] != "ok":
                raise SystemExit(f"backup integrity_check failed: {report['backup_integrity']}")
            connection.execute("BEGIN IMMEDIATE")
            try:
                changed = connection.execute("UPDATE funding SET time=raw_calc_time WHERE time<>raw_calc_time").rowcount
                if changed != len(affected):
                    raise RuntimeError(f"updated {changed} rows, expected {len(affected)}")
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            report.update(applied=True, backup=str(backup), updated=changed,
                          db_integrity=connection.execute("PRAGMA integrity_check").fetchone()[0])
            return report
        finally:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--backup", help="default: <db>.pre_r2_54_funding.sqlite")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--report", help="write the JSON report here")
    args = parser.parse_args()
    db = Path(args.db)
    report = run(db, args.backup or db.with_suffix(".pre_r2_54_funding.sqlite"), args.apply)
    text = json.dumps(report, indent=1, default=str)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"rows", "ledger_diff"}} |
                     {"ledger_changed": report["ledger_diff"]["changed"]}, default=str))


if __name__ == "__main__":
    main()
