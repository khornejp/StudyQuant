"""Explicit G3 behavior-hash migration (the only way past g3.MISMATCH).

A G3 sleeve whose stored state was produced by other code / params / start fails closed (g3_health last_error
behavior_hash_mismatch, stale 1). After reviewing the change, run with paper_catalog.py stopped:

    venv_btcusdt\\Scripts\\python.exe scripts\\paper_g3_migrate.py --config config/paper.toml --book G3_LONG [--apply]

Without --apply it only prints the stored and the new hash. With --apply it appends a MIGRATION event (old / new hash,
reason) to g3_events and re-stamps the stored state with the new hash; positions, orders and history are unchanged.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from btcusdt_quant.paper import g3  # noqa: E402
from btcusdt_quant.paper.config import load_config  # noqa: E402
from btcusdt_quant.paper.store import PaperStore, utc_text  # noqa: E402


def migrate(store: PaperStore, book: str, start: pd.Timestamp, config_hash: str, reason: str, apply: bool) -> dict:
    row = store.connection.execute("SELECT state FROM g3_state WHERE book=?", (book,)).fetchone()
    if row is None:
        raise SystemExit(f"{book}: no stored state (nothing to migrate)")
    state = json.loads(row[0])
    new = g3.behavior_hash(book, start)
    out = {"book": book, "stored": state.get("behavior_hash"), "new": new, "applied": False}
    if not apply or out["stored"] == new:
        return out
    now = utc_text(pd.Timestamp.now(tz="UTC"))
    with store.transaction() as connection:
        connection.execute("INSERT INTO g3_events VALUES (?,?,?,?,?,?,?)", (
            book, now, "MIGRATION", json.dumps({"old": out["stored"], "new": new, "reason": reason}), new,
            config_hash, now))
        connection.execute("UPDATE g3_state SET state=?, updated_at=? WHERE book=?",
                           (json.dumps({**state, "behavior_hash": new}), now, book))
    return {**out, "applied": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--book", required=True, choices=g3.BOOKS)
    parser.add_argument("--reason", default="reviewed code / config change")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    start = pd.Timestamp(config.book_start_times.get(args.book, config.start_time))
    with PaperStore(config.sqlite_path) as store:
        print(json.dumps(migrate(store, args.book, start, config.hash, args.reason, args.apply), indent=1))


if __name__ == "__main__":
    main()
