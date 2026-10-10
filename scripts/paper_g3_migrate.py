"""Explicit G3 behavior-hash migration / reset (the only ways past g3.MISMATCH).

A G3 sleeve whose stored state was produced by other code / inputs / params / start fails closed (g3_health
last_error behavior_hash_mismatch, stale 1). After reviewing the change, run with paper_catalog.py stopped:

    venv_btcusdt\\Scripts\\python.exe scripts\\paper_g3_migrate.py --config config/paper.toml --book G3_LONG [--apply]

  default   print the stored and the new hash, change nothing.
  --apply   same book start only: append a MIGRATION event (old / new hash, reason) and re-stamp the stored state
            with the new hash; position, orders and history unchanged. A changed book start is rejected.
  --reset   book start changed: append a RESET event (old hash, old start, the whole old state incl. any open
            position, which is abandoned) and replace the state with a FLAT one at the new start (new hash). The new
            start must lie on a later UTC day than the old state's last processed bar (so no bar is processed twice
            and no daily_pnl day is shared); it opens a new epoch: ledger, Book and daily_pnl count only the new
            epoch, earlier events, trades and daily rows stay as the record.
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


def migrate(store: PaperStore, book: str, start: pd.Timestamp, config_hash: str, reason: str, apply: bool = False,
            reset: bool = False) -> dict:
    row = store.connection.execute("SELECT state FROM g3_state WHERE book=?", (book,)).fetchone()
    if row is None:
        raise SystemExit(f"{book}: no stored state (nothing to migrate)")
    state = json.loads(row[0])
    start = pd.Timestamp(start)
    new = g3.behavior_hash(book, start)
    moved = state["start"] != start.value
    out = {"book": book, "stored": state.get("behavior_hash"), "new": new, "start_changed": moved, "applied": False}
    if out["stored"] == new or not (apply or reset):
        return out
    if moved and not reset:
        raise SystemExit(f"{book}: book start changed ({utc_text(pd.Timestamp(state['start'], tz='UTC'))} -> "
                         f"{utc_text(start)}): --apply refused, use --reset (flat at the new start)")
    last = pd.Timestamp(state["last_bar"], tz="UTC")
    if reset and not (start - pd.Timedelta(minutes=1) > last and start >= last.floor("D") + pd.Timedelta(days=1)):
        raise SystemExit(f"{book}: --reset needs a start on a UTC day after the last processed bar {utc_text(last)}")
    now = utc_text(pd.Timestamp.now(tz="UTC"))
    if reset:
        kind, payload, state = "RESET", {"old": out["stored"], "new": new, "reason": reason, "old_state": state}, \
            g3.initial_state(start, new)
    else:
        kind, payload, state = "MIGRATION", {"old": out["stored"], "new": new, "reason": reason}, \
            {**state, "behavior_hash": new}
    with store.transaction() as connection:
        connection.execute("INSERT INTO g3_events VALUES (?,?,?,?,?,?,?,?)",
                           (book, int(state["start"]), now, kind, json.dumps(payload), new, config_hash, now))
        connection.execute("UPDATE g3_state SET state=?, last_bar=?, updated_at=? WHERE book=?",
                           (json.dumps(state), utc_text(pd.Timestamp(state["last_bar"], tz="UTC")), now, book))
    return {**out, "applied": kind}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--book", required=True, choices=g3.BOOKS)
    parser.add_argument("--reason", default="reviewed code / config change")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    start = pd.Timestamp(config.book_start_times.get(args.book, config.start_time))
    with PaperStore(config.sqlite_path) as store:
        print(json.dumps(migrate(store, args.book, start, config.hash, args.reason, args.apply, args.reset), indent=1))


if __name__ == "__main__":
    main()
