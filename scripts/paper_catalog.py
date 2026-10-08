"""Live R2-44 PatchTST predictions and R2-48 catalog paper books (both read-only research code).

Every cycle: train any due weekly fold, append 15 m predictions, recompute every catalog book and replace only
those books' rows in trades / daily_pnl / positions. Usage: python scripts/paper_catalog.py [--once]
"""
from __future__ import annotations
import argparse, logging, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd, torch  # noqa: E402
from btcusdt_quant.paper import catalog, detector  # noqa: E402
from btcusdt_quant.paper.config import load_config  # noqa: E402
from btcusdt_quant.paper.store import PaperStore, utc_text  # noqa: E402

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


def decide_model_books(store: PaperStore, config, ctx, predictions: pd.DataFrame) -> int:
    """Record each model-dependent signal once, when its bound prediction is first observed (Codex rule)."""
    now = pd.Timestamp.now(tz="UTC")
    known = read_decisions(store)
    events = []
    for name in (n for n in config.books if n in catalog.BOOKS and catalog.needs_model(n)):
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


def recompute_books(store: PaperStore, config, end: pd.Timestamp, ctx=None, funding=None,
                    with_signals: bool = True) -> int:
    if ctx is None:
        ctx, funding, _ = load_context(store)
    decisions = read_decisions(store)
    names = [n for n in config.books if n in catalog.BOOKS]
    results, signals = {}, {}
    end_price = float(ctx.minutes.close.iloc[-1])
    for name in names:
        if with_signals:
            try:     # conditions are shown before a book's T0 too
                signals[name] = catalog.signal_rows(name, ctx, end - pd.Timedelta(days=SIGNAL_DAYS))
            except Exception:
                log.exception("catalog signals %s failed", name)
        start = pd.Timestamp(config.book_start_times.get(name, config.start_time))
        if start >= end:
            results[name] = (pd.DataFrame(), pd.DataFrame(), None, pd.DataFrame())
            continue
        try:
            t, d, held = catalog.run_book(name, ctx, funding, start, end,
                                          decisions.loc[decisions.book == name])
            position = None
            if held is not None:
                limit = held.get("max_hold_end")       # grid books have no max-hold end
                legs = held.get("legs", [])
                unrealized = (sum(float(leg["side"]) * np.log(end_price / float(leg["entry_price"])) * 1e4
                                  * float(leg["units"]) for leg in legs) if legs else
                              float(held["side"] * np.log(end_price / held["avg_price"]) * 1e4 * held["units"]))
                position = {"book": name, "side": held["side"], "candidate": catalog.BOOKS[name][0],
                            "entry_time": utc_text(held["entry_time"]), "entry_price": float(held["avg_price"]),
                            "exit_time": utc_text(limit if limit is not None else end),
                            "remaining_minutes": None if limit is None else max(
                                0, int((limit - end) / pd.Timedelta(minutes=1))),
                            "unrealized_bps": float(unrealized), "updated_at": utc_text(end)}
            fills = catalog.fill_rows(name, t, held, decisions.loc[decisions.book == name])
            if not fills.empty:
                fills = fills.loc[fills.signal_time >= end - pd.Timedelta(days=SIGNAL_DAYS)].reset_index(drop=True)
            results[name] = (t, d, position, fills)
        except Exception:
            log.exception("catalog book %s failed", name)
    published = 0
    with store.transaction() as connection:
        ensure_catalog_tables(connection)
        for index, (name, (trades, daily, position, fills)) in enumerate(results.items()):
            savepoint = f"catalog_book_{index}"
            connection.execute(f"SAVEPOINT {savepoint}")
            try:
                for table in ("trades", "daily_pnl", "positions", "catalog_fills"):
                    connection.execute(f"DELETE FROM {table} WHERE book=?", (name,))
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
    with PaperStore(config.sqlite_path) as store:
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
