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
BOOK_EVERY = 5                # full book replay every 5 cycles (or when new decisions arrive)
DECISION_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_decisions (book TEXT NOT NULL, signal_time TEXT NOT NULL, "
                  "decision_time TEXT, status TEXT NOT NULL, prediction_ts TEXT, available_at TEXT, decided_at TEXT, "
                  "model_id TEXT, PRIMARY KEY(book, signal_time))")
SIGNAL_DAYS = 14
SIGNAL_TABLE = ("CREATE TABLE IF NOT EXISTS catalog_signals (book TEXT NOT NULL, decision_time TEXT NOT NULL, "
                "side INTEGER, entry TEXT, upper REAL, lower REAL, stop_bps REAL, allow_entry INTEGER, "
                "exit_long INTEGER, exit_short INTEGER, M REAL, close REAL, indicators TEXT, model TEXT, "
                "PRIMARY KEY(book, decision_time))")
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
    ctx = catalog.live_context(market, features, store.frame("premium_1m"), funding, predictions)
    return ctx, funding, predictions


def read_decisions(store: PaperStore) -> pd.DataFrame:
    store.connection.execute(DECISION_TABLE)
    frame = pd.read_sql_query("SELECT * FROM catalog_decisions", store.connection)
    for c in ("signal_time", "decision_time", "prediction_ts", "available_at", "decided_at"):
        frame[c] = pd.to_datetime(frame[c], utc=True, format="mixed")
    return frame


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


def recompute_books(store: PaperStore, config, end: pd.Timestamp, ctx=None, funding=None,
                    with_signals: bool = True) -> int:
    if ctx is None:
        ctx, funding, _ = load_context(store)
    decisions = read_decisions(store)
    names = [n for n in config.books if n in catalog.BOOKS]
    trades, daily, positions, signals = [], [], [], []
    end_price = float(ctx.minutes.close.iloc[-1])
    for name in names:
        if with_signals:
            try:     # conditions are shown before a book's T0 too
                signals.append(catalog.signal_rows(name, ctx, end - pd.Timedelta(days=SIGNAL_DAYS)))
            except Exception:
                log.exception("catalog signals %s failed", name)
        start = pd.Timestamp(config.book_start_times.get(name, config.start_time))
        if start >= end:
            continue
        try:
            t, d, held = catalog.run_book(name, ctx, funding, start, end,
                                          decisions.loc[decisions.book == name])
        except Exception:
            log.exception("catalog book %s failed", name)
            continue
        trades.append(t); daily.append(d)
        if held is not None:
            limit = held["max_hold_end"]
            positions.append({"book": name, "side": held["side"], "candidate": catalog.BOOKS[name][0],
                              "entry_time": utc_text(held["entry_time"]), "entry_price": float(held["avg_price"]),
                              "exit_time": utc_text(limit if limit is not None else end),
                              "remaining_minutes": None if limit is None else max(0, int((limit - end) / pd.Timedelta(minutes=1))),
                              "unrealized_bps": float(held["side"] * np.log(end_price / held["avg_price"]) * 1e4 * held["units"]),
                              "updated_at": utc_text(end)})
    trades = pd.concat([t for t in trades if len(t)], ignore_index=True) if any(len(t) for t in trades) else pd.DataFrame()
    daily = pd.concat(daily, ignore_index=True) if daily else pd.DataFrame()
    marks = ",".join("?" * len(names))
    with store.transaction() as connection:
        for table in ("trades", "daily_pnl", "positions"):
            connection.execute(f"DELETE FROM {table} WHERE book IN ({marks})", names)
        for row in positions:
            store.upsert("positions", row, connection)
        for row in trades.itertuples(index=False):
            connection.execute(
                "INSERT INTO trades(book,boundary,candidate,entry_time,exit_time,side,entry_price,exit_price,"
                "gross_bps,cost_bps,funding_bps,net_bps,hold_minutes,exit_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row.book, row.boundary, row.candidate, utc_text(row.entry_time), utc_text(row.exit_time),
                 int(row.side), float(row.entry_price), float(row.exit_price), float(row.gross_bps),
                 float(row.cost_bps), float(row.funding_bps), float(row.net_bps), float(row.hold_minutes),
                 row.exit_reason))
        for row in daily.to_dict("records"):
            store.upsert("daily_pnl", row, connection)
        if with_signals:
            connection.execute("DROP TABLE IF EXISTS catalog_signals")      # rebuilt every 5 min; schema may change
            connection.execute(SIGNAL_TABLE)
        for frame in signals:
            for row in frame.itertuples(index=False):
                connection.execute("INSERT OR REPLACE INTO catalog_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    row.book, utc_text(row.decision_time), int(row.side), str(row.entry),
                    *(None if pd.isna(v) else float(v) for v in (row.upper, row.lower, row.stop_bps)),
                    int(bool(row.allow_entry)), int(bool(row.exit_long)), int(bool(row.exit_short)),
                    *(None if pd.isna(v) else float(v) for v in (row.M, row.close)), row.indicators, row.model))
    return len(names)


def cycle(store: PaperStore, config, device, count: int) -> None:
    last = store.get_meta("last_processed_minute")
    if last is None:
        return
    end = pd.Timestamp(last) + pd.Timedelta(minutes=1)
    train_due_folds(store, end, device)
    written = update_predictions(store, end, device)
    started = time.perf_counter()
    ctx, funding, predictions = load_context(store)
    decided = decide_model_books(store, config, ctx, predictions)
    # books every minute (replay is ~3 s); dashboard condition rows every 5 minutes
    books = recompute_books(store, config, end, ctx, funding, with_signals=count % BOOK_EVERY == 0)
    store.set_meta("catalog_last_run", pd.Timestamp.now(tz="UTC").isoformat())
    log.info("predictions +%d, decisions +%d, %d books in %.1f s (data end %s)", written, decided, books,
             time.perf_counter() - started, end)


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
            # run at :15 of each minute: bars of the new 15 m origin are stored by :10 (paper_run REST at :10)
            time.sleep((15 - pd.Timestamp.now(tz="UTC").second) % 60 or 60)   # next :15, never skip one


if __name__ == "__main__":
    main()
