"""Live R2-44 PatchTST predictions and the R2-52A AX paper books (both read-only research code).

Every cycle: train any due weekly fold, append 15 m predictions, recompute every active AX source book and its x3
overlay and replace only those books' rows (trades / daily_pnl / positions / catalog_fills and the source's own
<source>_x3 leverage_* rows), source and x3 in the same transaction. Retired books are never touched.
Usage: python scripts/paper_catalog.py [--once]
"""
from __future__ import annotations
import argparse, json, logging, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd, torch  # noqa: E402
from btcusdt_quant.paper import catalog, detector, g3, leverage  # noqa: E402
from btcusdt_quant.paper.config import load_config  # noqa: E402
from btcusdt_quant.paper.store import (PaperStore, exclusive_lock, refuse_missing_funding_backfill,  # noqa: E402,F401
                                       refuse_pending_switch, utc_text)
from btcusdt_quant.paper.trade_ids import migrate as migrate_trade_ids  # noqa: E402

CYCLE_SECONDS = 60            # predictions and live decisions every minute
SIGNAL_EVERY = 5              # dashboard condition history is heavier; refresh every 5 cycles
DECISION_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_decisions (book TEXT NOT NULL, signal_time TEXT NOT NULL, "
                  "decision_time TEXT, status TEXT NOT NULL, prediction_ts TEXT, available_at TEXT, decided_at TEXT, "
                  "model_id TEXT, PRIMARY KEY(book, signal_time))")
SIGNAL_DAYS = 14
SIGNAL_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_signals (book TEXT NOT NULL, decision_time TEXT NOT NULL, "
                "side INTEGER, entry TEXT, upper REAL, lower REAL, stop_bps REAL, expiry_min INTEGER, allow_entry INTEGER, "
                "exit_long INTEGER, exit_short INTEGER, M REAL, close REAL, indicators TEXT, model TEXT, "
                "PRIMARY KEY(book, decision_time))")
FILL_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_fills (book TEXT NOT NULL, signal_time TEXT NOT NULL, "
              "fill_time TEXT NOT NULL, side INTEGER NOT NULL, fill_price REAL NOT NULL, "
              "PRIMARY KEY(book, signal_time, fill_time, side, fill_price))")
AX_STATE_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_ax_state (book TEXT NOT NULL, position_id INTEGER NOT NULL, "
                  "status TEXT NOT NULL, side INTEGER, entry_time TEXT, entry_price REAL, k REAL, e_head TEXT, "
                  "e0_bps REAL, e_t_bps REAL, r0_bps REAL, r_bps REAL, hard_stop REAL, trail_armed INTEGER, "
                  "best_price REAL, trail_stop REAL, anchor_upper REAL, anchor_lower REAL, updated_at TEXT, "
                  "PRIMARY KEY(book, position_id))")
AX_EVENT_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_ax_events (book TEXT NOT NULL, position_id INTEGER NOT NULL, "
                  "event_time TEXT NOT NULL, event_type TEXT NOT NULL, event_seq INTEGER NOT NULL, payload TEXT, "
                  "PRIMARY KEY(book, position_id, event_time, event_type, event_seq))")      # immutable: INSERT OR IGNORE
LEVERAGE_TABLES = ("leverage_state", "leverage_positions", "leverage_trades", "leverage_daily", "leverage_skips")
log = logging.getLogger("paper_catalog")


def train_due_folds(store: PaperStore, now: pd.Timestamp, device) -> None:
    due = [t for t in detector.retrain_times(now) if not detector.checkpoint_path(t).exists()]
    if not due:
        return
    log.info("training %d detector folds: %s", len(due), [str(t.date()) for t in due])
    data = detector.build_data(*detector.combined_inputs(store.connection))
    detector.LIVE_DIR.mkdir(parents=True, exist_ok=True)
    for retrain in due:
        checkpoint, _ = detector.train(data, retrain, device)
        path = detector.checkpoint_path(retrain)
        tmp = path.with_suffix(".tmp"); torch.save(checkpoint, tmp); tmp.replace(path)
        log.info("fold %s trained in %.0f s", retrain.date(), checkpoint["elapsed_seconds"])


def update_predictions(store: PaperStore, now: pd.Timestamp, device) -> int:
    detector.ensure_table(store.connection)
    last = store.connection.execute(f"SELECT MAX(timestamp) FROM {detector.TABLE}").fetchone()[0]
    start = detector.ARCHIVE_END if last is None else pd.Timestamp(last) + pd.Timedelta(minutes=15)
    folds = [t for t in detector.retrain_times(now) if detector.checkpoint_path(t).exists()]   # latest trained model serves until the next one exists
    if not folds:
        return 0
    backfill = start < now - pd.Timedelta(days=detector.PREDICT_DAYS - 1)
    data = (detector.build_data(*detector.combined_inputs(store.connection), with_targets=False) if backfill
            else detector.recent_data(store.connection, now))
    origins = pd.DatetimeIndex(data.origins)
    origins = origins[origins >= start]
    written = 0
    for k, retrain in enumerate(folds):
        upper = folds[k + 1] if k + 1 < len(folds) else pd.Timestamp.max.tz_localize("UTC")
        chosen = origins[(origins >= max(retrain, start)) & (origins < upper)] if k else origins[origins < upper]
        if not len(chosen):
            continue
        checkpoint = torch.load(detector.checkpoint_path(retrain), weights_only=False, map_location="cpu")
        values = detector.predict(data, checkpoint, chosen, device)
        with store.transaction() as connection:
            written += detector.write_predictions(connection, chosen, retrain, values,
                                                  source="backfill" if backfill else "live")
    return written


def load_context(store: PaperStore):
    market = store.frame("klines_1m")
    features = store.frame("ls_ratio").rename(columns={"timestamp": "open_time"})
    funding = store.frame("funding")[["time", "rate"]]
    funding["time"] = pd.to_datetime(funding.time, utc=True, format="mixed")
    funding = funding.sort_values("time").reset_index(drop=True)
    predictions = detector.read_predictions(store.connection)
    predictions.attrs["minute"] = detector.read_predictions(store.connection, detector.MINUTE_TABLE)
    ctx = catalog.live_context(market, features, store.frame("premium_1m"), funding, predictions)
    return ctx, funding, predictions


def read_decisions(store: PaperStore) -> pd.DataFrame:
    store.connection.execute(DECISION_TABLE)
    frame = pd.read_sql_query("SELECT * FROM catalog_decisions", store.connection)
    for c in ("signal_time", "decision_time", "prediction_ts", "available_at", "decided_at"):
        frame[c] = pd.to_datetime(frame[c], utc=True, format="mixed")
    return frame


def ensure_catalog_tables(connection) -> None:
    connection.execute(SIGNAL_TABLE)
    have = {row[1] for row in connection.execute("PRAGMA table_info(catalog_signals)")}
    if "expiry_min" not in have:
        connection.execute("ALTER TABLE catalog_signals ADD COLUMN expiry_min INTEGER")
    connection.execute(FILL_TABLE)
    connection.execute(AX_STATE_TABLE)
    connection.execute(AX_EVENT_TABLE)


def active_books(config) -> list[str]:
    retired = set(getattr(config, "retired_books", ()))
    return [n for n in config.books if (n in catalog.BOOKS or n in g3.BOOKS) and n not in retired]


def decide_model_books(store: PaperStore, config, ctx, predictions: pd.DataFrame) -> int:
    """Record each model-dependent signal once, when its bound prediction is first observed (Codex rule)."""
    now = pd.Timestamp.now(tz="UTC")
    known = read_decisions(store)
    events = []
    for name in (n for n in active_books(config) if catalog.needs_model(n)):
        start = pd.Timestamp(config.book_start_times.get(name, config.start_time))
        if start > now:
            continue
        mine = set(known.loc[known.book == name, "signal_time"].map(lambda t: t.isoformat()))
        try:
            events += catalog.decide(name, catalog.raw_table(name, ctx), predictions, mine, now, start)
        except Exception:
            log.exception("decision %s failed", name)
    with store.transaction() as connection:
        for e in events:
            connection.execute("INSERT OR IGNORE INTO catalog_decisions VALUES (?,?,?,?,?,?,?,?)", (
                e["book"], utc_text(e["signal_time"]), None if e["decision_time"] is None else utc_text(e["decision_time"]),
                e["status"], None if pd.isna(e["prediction_ts"]) else utc_text(e["prediction_ts"]),
                None if pd.isna(e["available_at"]) else utc_text(e["available_at"]),
                None if e["decided_at"] is None else utc_text(e["decided_at"]), e["model_id"]))
    return len(events)


MINUTE_KEEP = pd.Timedelta(days=3)


def update_minute_predictions(store: PaperStore, now: pd.Timestamp, device) -> int:
    """Fresh 30m/1h/4h heads every minute, 12h/24h held from the latest 15-minute prediction (mixed mode)."""
    detector.ensure_table(store.connection)
    folds = [t for t in detector.retrain_times(now) if detector.checkpoint_path(t).exists()]
    grid = detector.read_predictions(store.connection)
    if not folds or not len(grid):
        return 0
    last = store.connection.execute(f"SELECT MAX(timestamp) FROM {detector.MINUTE_TABLE}").fetchone()[0]
    start = now - pd.Timedelta(minutes=30) if last is None else pd.Timestamp(last) + pd.Timedelta(minutes=1)
    data = detector.recent_data(store.connection, now, every_minute=True)
    origins = pd.DatetimeIndex(data.origins)
    origins = origins[(origins >= start) & (origins <= now)]
    if not len(origins):
        return 0
    names = [f"prediction_{t}" for t in detector.target_names()]
    grid_t = pd.DatetimeIndex(grid.timestamp).as_unit("ns").asi8
    written = 0
    for k, retrain in enumerate(folds):
        upper = folds[k + 1] if k + 1 < len(folds) else pd.Timestamp.max.tz_localize("UTC")
        chosen = origins[(origins >= retrain) & (origins < upper)]
        if not len(chosen):
            continue
        checkpoint = torch.load(detector.checkpoint_path(retrain), weights_only=False, map_location="cpu")
        fresh = detector.predict(data, checkpoint, chosen, device)
        pos = np.searchsorted(grid_t, chosen.as_unit("ns").asi8, side="right") - 1
        keep = pos >= 0
        if not keep.any():
            continue
        held = grid[names].to_numpy(float)[pos[keep]]
        with store.transaction() as connection:
            written += detector.write_predictions(connection, chosen[keep], retrain,
                                                  detector.mix_minute(fresh[keep], held), table=detector.MINUTE_TABLE)
    store.connection.execute(f"DELETE FROM {detector.MINUTE_TABLE} WHERE timestamp < ?",
                             ((now - MINUTE_KEEP).isoformat(),))
    return written


def _x3(name: str, result, minutes, funding, start, end):
    """x3 overlay of one AX source: the same adaptive result (accepted fills, source exits with phase, the open
    position as _active); no independent signal, E, stop or max hold."""
    source = result.attrs.get("source")
    if source is None:
        source = pd.DataFrame(columns=["entry_time", "exit_time", "side", "entry_price", "exit_price", "exit_reason",
                                       "exit_phase", "candidate", "_active"])
    return leverage.simulate_book(source, minutes, funding, name, start, end)


def _ax_rows(name: str, trades, held, ctx, end):
    """catalog_ax_state for the open position and immutable ENTRY/EXIT events per position."""
    legs = trades.attrs.get("legs", pd.DataFrame())
    events = []
    for leg in legs.itertuples(index=False):
        pid = int(leg.position_id)
        events.append((name, pid, utc_text(leg.entry_time), "ENTRY", 0, json.dumps(
            {"side": int(leg.side), "price": float(leg.entry_price)})))
        events.append((name, pid, utc_text(leg.exit_time), "EXIT", 0, json.dumps(
            {"price": float(leg.exit_price), "reason": str(leg.exit_reason).upper()})))
    state = None
    if held is not None:
        state = catalog.ax_state(name, held, ctx, end)
        events.append((name, state["position_id"], utc_text(held["entry_time"]), "ENTRY", 0, json.dumps(
            {"side": state["side"], "price": state["entry_price"], "k": state["k"], "e0_bps": state["e0_bps"],
             "r0_bps": state["r0_bps"]})))
    return state, events


def _write_x3(store: PaperStore, connection, result) -> None:
    state = dict(result.state)
    state["liquidated_at"] = None if state["liquidated_at"] is None else utc_text(state["liquidated_at"])
    state["updated_at"] = utc_text(state["updated_at"])
    store.upsert("leverage_state", state, connection)
    if result.position is not None:
        position = {**result.position, "entry_time": utc_text(result.position["entry_time"]),
                    "updated_at": utc_text(result.position["updated_at"])}
        store.upsert("leverage_positions", position, connection)
    for row in result.trades.to_dict("records"):
        store.insert("leverage_trades", {**row, "entry_time": utc_text(row["entry_time"]),
                                         "exit_time": utc_text(row["exit_time"])}, connection)
    for row in result.daily.to_dict("records"):
        store.upsert("leverage_daily", row, connection)
    for row in result.skips.to_dict("records"):
        store.insert("leverage_skips", {**row, "entry_time": utc_text(row["entry_time"])}, connection)


def recompute_books(store: PaperStore, config, end: pd.Timestamp, ctx=None, funding=None,
                    with_signals: bool = True) -> int:
    if ctx is None:
        ctx, funding, _ = load_context(store)
    decisions = read_decisions(store)
    names = active_books(config)
    results, signals, g3_starts = {}, {}, {}
    end_price = float(ctx.minutes.close.iloc[-1])
    for name in names:
        if name in g3.BOOKS:      # G3 sleeves: incremental, append-only (g3.run_cycle below); no x3 / signals
            start = pd.Timestamp(config.book_start_times.get(name, config.start_time))
            if start < end:
                g3_starts[name] = start
            continue
        if with_signals:
            try:     # conditions are shown before a book's T0 too
                signals[name] = catalog.signal_rows(name, ctx, end - pd.Timedelta(days=SIGNAL_DAYS))
            except Exception:
                log.exception("catalog signals %s failed", name)
        start = pd.Timestamp(config.book_start_times.get(name, config.start_time))
        if start >= end:
            continue
        try:
            t, d, held = catalog.run_book(name, ctx, funding, start, end, decisions.loc[decisions.book == name])
            position = None
            if held is not None:
                unrealized = sum(float(leg["side"]) * np.log(end_price / float(leg["entry_price"])) * 1e4
                                 * float(leg["units"]) for leg in held.get("legs", []))
                position = {"book": name, "side": held["side"], "candidate": catalog.BOOKS[name][0],
                            "entry_time": utc_text(held["entry_time"]), "entry_price": float(held["avg_price"]),
                            "exit_time": None, "remaining_minutes": None,      # no max hold (paper_rollout.position_row)
                            "unrealized_bps": float(unrealized), "updated_at": utc_text(end)}
            fills = catalog.fill_rows(name, t, held, decisions.loc[decisions.book == name])
            if not fills.empty:
                fills = fills.loc[fills.signal_time >= end - pd.Timedelta(days=SIGNAL_DAYS)].reset_index(drop=True)
            x3 = _x3(name, t, ctx.minutes, funding, start, end)
            state, events = _ax_rows(name, t, held, ctx, end)
            results[name] = (t, d, position, fills, x3, state, events)
        except Exception:
            log.exception("catalog book %s failed", name)
    published = 0
    with store.transaction() as connection:
        ensure_catalog_tables(connection)
        for index, (name, (trades, daily, position, fills, x3, state, events)) in enumerate(results.items()):
            savepoint = f"catalog_book_{index}"
            connection.execute(f"SAVEPOINT {savepoint}")
            try:
                for table in ("trades", "daily_pnl", "positions", "catalog_fills"):
                    connection.execute(f"DELETE FROM {table} WHERE book=?", (name,))
                for table in LEVERAGE_TABLES:          # only this active source's own x3 overlay
                    connection.execute(f"DELETE FROM {table} WHERE book=?", (f"{name}_x3",))
                if position is not None:
                    store.upsert("positions", position, connection)
                for row in trades.itertuples(index=False):
                    connection.execute(
                        "INSERT INTO trades(book,boundary,candidate,entry_time,exit_time,side,entry_price,exit_price,"
                        "gross_bps,cost_bps,funding_bps,net_bps,hold_minutes,exit_reason) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (row.book, row.boundary, row.candidate, utc_text(row.entry_time), utc_text(row.exit_time),
                         int(row.side), float(row.entry_price), float(row.exit_price), float(row.gross_bps),
                         float(row.cost_bps), float(row.funding_bps), float(row.net_bps), float(row.hold_minutes),
                         row.exit_reason))
                for row in daily.to_dict("records"):
                    store.upsert("daily_pnl", row, connection)
                for row in fills.itertuples(index=False):
                    connection.execute("INSERT INTO catalog_fills VALUES (?,?,?,?,?)", (
                        row.book, utc_text(row.signal_time), utc_text(row.fill_time), int(row.side),
                        float(row.fill_price)))
                _write_x3(store, connection, x3)
                connection.execute("UPDATE catalog_ax_state SET status='CLOSED' WHERE book=? AND status='OPEN' "
                                   "AND position_id IS NOT ?", (name, None if state is None else state["position_id"]))
                if state is not None:
                    connection.execute(f"INSERT OR REPLACE INTO catalog_ax_state ({','.join(state)}) VALUES "
                                       f"({','.join('?' * len(state))})", tuple(state.values()))
                connection.executemany("INSERT OR IGNORE INTO catalog_ax_events VALUES (?,?,?,?,?,?)", events)
            except Exception:
                connection.execute(f"ROLLBACK TO {savepoint}")
                connection.execute(f"RELEASE {savepoint}")
                log.exception("catalog publish %s failed", name)
            else:
                connection.execute(f"RELEASE {savepoint}")
                published += 1
        if with_signals:
            for index, (name, frame) in enumerate(signals.items()):
                savepoint = f"catalog_signal_{index}"
                connection.execute(f"SAVEPOINT {savepoint}")
                try:
                    connection.execute("DELETE FROM catalog_signals WHERE book=?", (name,))
                    for row in frame.itertuples(index=False):
                        connection.execute("INSERT INTO catalog_signals "
                            "(book,decision_time,side,entry,upper,lower,stop_bps,expiry_min,allow_entry,exit_long,"
                            "exit_short,M,close,indicators,model) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                            row.book, utc_text(row.decision_time), int(row.side), str(row.entry),
                            *(None if pd.isna(v) else float(v) for v in
                              (row.upper, row.lower, row.stop_bps, row.expiry_min)),
                            int(bool(row.allow_entry)), int(bool(row.exit_long)), int(bool(row.exit_short)),
                            *(None if pd.isna(v) else float(v) for v in (row.M, row.close)), row.indicators, row.model))
                except Exception:
                    connection.execute(f"ROLLBACK TO {savepoint}")
                    connection.execute(f"RELEASE {savepoint}")
                    log.exception("catalog signal publish %s failed", name)
                else:
                    connection.execute(f"RELEASE {savepoint}")
    if g3_starts:       # own transactions per sleeve; errors land in g3_health
        try:
            published += g3.run_cycle(store, g3_starts, ctx.minutes, funding, end, config.hash)
        except Exception:
            log.exception("g3 cycle failed")
    return published


def cycle(store: PaperStore, config, device, count: int) -> None:
    last = store.get_meta("last_processed_minute")
    if last is None:
        return
    end = pd.Timestamp(last) + pd.Timedelta(minutes=1)
    train_due_folds(store, end, device)
    written = update_predictions(store, end, device)
    written_1m = update_minute_predictions(store, end, device)
    started = time.perf_counter()
    ctx, funding, predictions = load_context(store)
    decided = decide_model_books(store, config, ctx, predictions)
    # books every minute (replay is ~3 s); dashboard condition rows every 5 minutes
    books = recompute_books(store, config, end, ctx, funding, with_signals=count % SIGNAL_EVERY == 0)
    store.set_meta("catalog_last_run", pd.Timestamp.now(tz="UTC").isoformat())
    log.info("predictions +%d (1m +%d), decisions +%d, %d books in %.1f s (data end %s)", written, written_1m,
             decided, books, time.perf_counter() - started, end)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:        # one catalog per DB; scripts/paper_ax_switch.py holds this lock for the whole switch
        lock = exclusive_lock(Path(config.sqlite_path).with_suffix(".catalog.lock"))
        lock.__enter__()
    except RuntimeError:
        sys.exit(f"paper_catalog already running (or a switch is in progress) for {config.sqlite_path}")
    with PaperStore(config.sqlite_path) as store:
        refuse_pending_switch(store)
        refuse_missing_funding_backfill(store)
        migrate_trade_ids(store.connection)
        count = 0
        while True:
            try:
                cycle(store, config, device, count)
            except Exception:
                log.exception("catalog cycle failed")
            if args.once:
                break
            count += 1
            # start as soon as paper_run finishes the next minute (a fixed :15 ran on the previous minute when paper_run was late)
            last = store.get_meta("last_processed_minute")
            while store.get_meta("last_processed_minute") == last:
                time.sleep(1)


if __name__ == "__main__":
    main()
