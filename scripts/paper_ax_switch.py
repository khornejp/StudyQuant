"""R2-52A paper switch (out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json paper_rollout.retirement): one-shot.

Run with paper_run.py and paper_catalog.py stopped (both locks are taken and held). Phases and recovery: see
switch(); every input is validated before the first write, the DB is backed up to <db>.pre_r2_52a.sqlite. effective_switch_time = the open of the first minute after the
last processed minute. Every open retired 1x / x3 position is closed at that open (MIGRATION_END, normal exit fee,
PESS funding up to the switch, no synthetic entry fee); the retired books are snapshotted, their per-table row
counts and hashes are recorded before and after, and the new AX configuration (27 sources, 27 x3, telegram x3 only)
is written. Paper only: the price comes from the store or Binance public REST klines (no authenticated action).
Usage: python scripts/paper_ax_switch.py [--config config/paper.toml] [--out-config config/paper.toml]
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, sys, tomllib
from contextlib import ExitStack
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd  # noqa: E402
from btcusdt_quant.paper import book, catalog, leverage  # noqa: E402
from btcusdt_quant.paper.collector import PublicBinanceClient, parse_kline  # noqa: E402
from btcusdt_quant.paper.config import PaperConfig, load_config  # noqa: E402
from btcusdt_quant.paper.store import SCHEMA_VERSION, PaperStore, exclusive_lock, utc_text  # noqa: E402

MANIFEST = ROOT / "out/k45_rl_r2_48_20261007/r2_52a/paper_switch_manifest.json"
FREEZE = ROOT / "out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json"
SELECTED_K = catalog.SELECTED_K
TABLES = ("trades", "daily_pnl", "positions", "signals", "catalog_decisions", "catalog_signals", "catalog_fills",
          "leverage_state", "leverage_positions", "leverage_trades", "leverage_daily", "leverage_skips")
REASON = "MIGRATION_END"


def retired_books(old: PaperConfig) -> tuple[str, ...]:
    """Immutable snapshot: books, comparison_books and every x3 book built from leverage_books before the switch."""
    sources = old.books if old.leverage_books is None else old.leverage_books
    return tuple(sorted(set(old.books) | set(old.comparison_books) | {f"{name}_x3" for name in sources}))


def config_toml(old: PaperConfig, switch: pd.Timestamp, retired: tuple[str, ...]) -> str:
    """paper_rollout.configuration: 27 AX sources, the 26 non-primary as comparison, 27 leverage sources, primary
    C1_AX, telegram = the 27 derived x3 names, every AX start at effective_switch_time."""
    start = switch.strftime("%Y-%m-%dT%H:%M:%SZ")
    books = catalog.AX_BOOKS
    values = {**asdict(old), "books": books, "comparison_books": tuple(n for n in books if n != "C1_AX"),
              "leverage_books": books, "primary_book": "C1_AX", "telegram_books": catalog.X3_BOOKS,
              "book_start_times": {n: start for n in books}, "retired_books": retired, "start_time": start}
    PaperConfig(**values)                 # validate before writing

    def literal(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (tuple, list)):
            return "[" + ", ".join(literal(v) for v in value) + "]"
        if isinstance(value, dict):
            return "{ " + ", ".join(f"{json.dumps(k)} = {literal(v)}" for k, v in value.items()) + " }"
        return json.dumps(value, ensure_ascii=False)
    lines = ["# R2-52A AX paper configuration (scripts/paper_ax_switch.py); retired books stay in the DB as the record",
             f"# effective_switch_time = {start}", "[paper]"]
    lines += [f"{key} = {literal(value)}" for key, value in values.items() if value is not None]
    return "\n".join(lines) + "\n"


def retired_hashes(store, books) -> dict:
    """Per-table row count and sha256 of the retired books' rows (sorted, surrogate id excluded); `store` is a
    PaperStore or a (read-only) sqlite3 connection."""
    connection = getattr(store, "connection", store)
    out = {}
    names = sorted(books)
    marks = ",".join("?" * len(names))
    for table in TABLES:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                          (table,)).fetchone()
        frame = (pd.read_sql_query(f"SELECT * FROM {table} WHERE book IN ({marks})", connection, params=names)
                 if exists and names else pd.DataFrame())
        frame = frame.drop(columns=[c for c in ("id",) if c in frame])
        text = frame.sort_values(list(frame.columns)).to_csv(index=False) if len(frame) else ""
        out[table] = {"rows": int(len(frame)), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    return out


def public_open(switch: pd.Timestamp) -> float:
    """Open of the switch minute from Binance USD-M public klines (unauthenticated GET, same as the collector)."""
    rows = PublicBinanceClient().get("/fapi/v1/klines", {"symbol": "BTCUSDT", "interval": "1m",
                                                         "startTime": int(switch.timestamp() * 1000), "limit": 1})
    if not rows:
        raise SystemExit(f"no USD-M BTCUSDT 1m kline at {switch}")
    kline = parse_kline(rows[0])
    if kline["open_time"] != switch:          # exactly the switch minute; no other price source
        raise SystemExit(f"no USD-M BTCUSDT 1m kline at {switch} yet")
    return float(kline["open"])


def position_units(position, closes: pd.Series) -> float:
    """Units of an open 1x position (DETEXIT legs are 0.5): the stored mark unrealized_bps divided by one unit's
    mark at the last close before updated_at; 1.0 when the mark cannot tell."""
    mark = closes.get(pd.Timestamp(position.updated_at) - pd.Timedelta(minutes=1))
    move = None if mark is None else int(position.side) * np.log(float(mark) / float(position.entry_price)) * 1e4
    if move is None or abs(move) < 1e-3:
        return 1.0
    return round(float(position.unrealized_bps) / move, 3)       # ponytail: multi-leg avg price -> approximate


def _close_1x(store, connection, position, switch, price, funding, closes) -> None:
    units = position_units(position, closes)
    trade = pd.DataFrame([{"entry_time": position.entry_time, "exit_time": switch, "side": int(position.side),
                           "entry_price": float(position.entry_price), "exit_price": price}])
    for boundary in ("PESS", "OPT"):
        priced = book.reprice(trade, funding, boundary, 4.0).iloc[0]
        values = (units * float(priced.gross_bps), units * 4.0, units * float(priced.funding_bps),
                  units * float(priced.net_bps))
        # a DETEXIT position whose TAKE leg is already booked keeps one merged row per entry (catalog convention)
        merged = connection.execute(
            "UPDATE trades SET exit_time=?, exit_price=?, gross_bps=gross_bps+?, cost_bps=cost_bps+?, "
            "funding_bps=funding_bps+?, net_bps=net_bps+?, hold_minutes=?, exit_reason=exit_reason||'+'||? "
            "WHERE book=? AND boundary=? AND entry_time=?",
            (utc_text(switch), price, *values, float(priced.hold_minutes), REASON, position.book, boundary,
             utc_text(position.entry_time))).rowcount
        if not merged:
            store.insert("trades", {"book": position.book, "boundary": boundary, "candidate": position.candidate,
                                    "entry_time": utc_text(position.entry_time), "exit_time": utc_text(switch),
                                    "side": int(position.side), "entry_price": float(position.entry_price),
                                    "exit_price": price, "gross_bps": values[0], "cost_bps": values[1],
                                    "funding_bps": values[2], "net_bps": values[3],
                                    "hold_minutes": float(priced.hold_minutes), "exit_reason": REASON}, connection)
        # the realized ledger never held the open position: book its minute components by day
        minute = book.minute_components(trade.assign(entry_time=pd.Timestamp(position.entry_time)),
                                        closes, funding, boundary, 4.0)
        minute = minute.loc[minute.index >= pd.Timestamp(position.entry_time)]
        for day, part in minute.groupby(minute.index.strftime("%Y-%m-%d")):
            values = part.sum()
            connection.execute(
                "INSERT INTO daily_pnl(book,boundary,date,gross_bps,cost_bps,funding_bps,net_bps) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(book,boundary,date) DO UPDATE SET gross_bps=gross_bps+excluded.gross_bps,"
                "cost_bps=cost_bps+excluded.cost_bps,funding_bps=funding_bps+excluded.funding_bps,"
                "net_bps=net_bps+excluded.net_bps",
                (position.book, boundary, day, *(units * float(values[c]) for c in
                                                 ("gross_bps", "cost_bps", "funding_bps", "net_bps"))))


def _close_x3(store, connection, position, switch, price, funding) -> None:
    """Retired x3 at the switch open with the leverage.simulate_book order: the open is tested against the
    funding-adjusted liquidation price first (LIQUIDATED at that price, balance 0), else MIGRATION_END."""
    side, notional, margin = int(position.side), float(position.notional_usd), float(position.margin_usd)
    entry, entry_price = pd.Timestamp(position.entry_time), float(position.entry_price)
    funding_usd = sum(leverage._funding_cashflows(funding, side, notional, entry, switch).values())
    liq = leverage.liquidation_price(entry_price, side, margin, notional, .004, funding_usd)
    entry_fee = notional * 4.0 / 20_000.0
    state = pd.read_sql_query("SELECT * FROM leverage_state WHERE book=?", connection, params=(position.book,))
    before = float(state.balance_usd.iloc[0]) if len(state) else float(position.balance_usd)
    liquidated = price <= liq if side > 0 else price >= liq
    if liquidated:          # existing liquidation rule: fill at the liquidation price, the whole margin is lost
        exit_price, gross, cost, pnl, reason = liq, -margin - funding_usd + entry_fee, entry_fee, -margin, "LIQUIDATED"
    else:
        exit_price, reason = price, REASON
        gross = notional * side * (price / entry_price - 1.0)
        cost = notional * 4.0 / 10_000.0                       # the existing x3 rule: round trip booked at the close
        pnl = gross + funding_usd - cost
    after = 0.0 if liquidated else before + pnl
    store.insert("leverage_trades", {
        "book": position.book, "source_book": position.source_book, "candidate": position.candidate,
        "entry_time": utc_text(entry), "exit_time": utc_text(switch), "side": side,
        "entry_price": entry_price, "exit_price": exit_price, "notional_usd": notional,
        "margin_usd": margin, "initial_liquidation_price": float(position.liquidation_price),
        "liquidation_price": liq, "max_adverse_pnl_usd": min(0.0, pnl), "liquidated": int(liquidated),
        "gross_pnl_usd": gross, "cost_usd": cost, "funding_usd": funding_usd, "pnl_usd": pnl,
        "balance_before_usd": before, "balance_after_usd": after,
        "hold_minutes": float((switch - entry) / pd.Timedelta(minutes=1)), "exit_reason": reason}, connection)
    budget = 100.0
    connection.execute("UPDATE leverage_state SET balance_usd=?, cumulative_pnl_usd=?, cumulative_return_pct=?, "
                       "updated_at=?, status=CASE WHEN ? THEN 'LIQUIDATED' ELSE status END, "
                       "liquidated_at=CASE WHEN ? THEN ? ELSE liquidated_at END WHERE book=?",
                       (after, after - budget, (after / budget - 1) * 100, utc_text(switch), int(liquidated),
                        int(liquidated), utc_text(switch), position.book))
    day = switch.strftime("%Y-%m-%d")
    prior = connection.execute("SELECT balance_usd FROM leverage_daily WHERE book=? AND date<? ORDER BY date DESC "
                               "LIMIT 1", (position.book, day)).fetchone()
    previous = budget if prior is None else float(prior[0])
    connection.execute("INSERT INTO leverage_daily(book,date,balance_usd,day_pnl_usd,max_drawdown_usd,max_drawdown_pct) "
                       "VALUES(?,?,?,?,0,0) ON CONFLICT(book,date) DO UPDATE SET balance_usd=excluded.balance_usd,"
                       "day_pnl_usd=excluded.day_pnl_usd", (position.book, day, after, after - previous))


PHASES = ("validated", "backed_up", "staged", "in_transaction", "committed", "config_replaced", "manifest_replaced")


def backup_path(db: Path) -> Path:
    return Path(db).with_name(Path(db).stem + ".pre_r2_52a.sqlite")


def _staged(path: Path) -> Path:
    return Path(path).with_name(Path(path).name + ".r2_52a.tmp")


def _fail(fail_at, phase) -> None:
    """Test hook: raise right after the named phase (PHASES)."""
    if fail_at == phase:
        raise RuntimeError(f"injected failure after {phase}")


def read_only(db: Path) -> sqlite3.Connection:
    """Zero-write view of the DB: immutable when no -wal exists (the locks guarantee no writer); otherwise plain
    read-only on the existing -wal/-shm. Never creates files, never changes the DB bytes."""
    db = Path(db).resolve()
    if not db.exists():
        raise SystemExit(f"database missing: {db}")
    wal = Path(str(db) + "-wal")
    uri = db.as_uri() + ("?mode=ro" if wal.exists() else "?mode=ro&immutable=1")
    return sqlite3.connect(uri, uri=True)


def _meta(connection, key):
    row = connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return None if row is None else row[0]


def _frame(connection, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table}", connection)


def _validate(old: PaperConfig, out_config: Path, manifest_path: Path, ro: sqlite3.Connection, price) -> dict:
    """Every input and data check, read-only and before anything is written: freeze, selected_k, names, config,
    ledgers as of the switch, directory writability, disk space, and the exact switch-minute open."""
    if not FREEZE.exists():
        raise SystemExit(f"freeze missing: {FREEZE}")
    rollout = json.loads(FREEZE.read_text(encoding="utf-8"))["paper_rollout"]
    if tuple(rollout["new_books"]) != catalog.AX_BOOKS:
        raise SystemExit("catalog.AX_BOOKS differs from the freeze new_books")
    if rollout["presentation_addendum_2026-10-08"]["name_list"] != catalog.NAMES:
        raise SystemExit("catalog.NAMES differs from the freeze name_list")
    if not SELECTED_K.exists():
        raise SystemExit(f"research k selection missing: {SELECTED_K}")
    picks = catalog.paper_k(SELECTED_K)
    missing = sorted({catalog.BOOKS[n][0] for n in catalog.AX_BOOKS} - set(picks))
    if missing:
        raise SystemExit(f"no paper k for {missing}")
    version = _meta(ro, "schema_version")
    if version is None or int(version) != SCHEMA_VERSION:
        raise SystemExit(f"unsupported schema version {version} (expected {SCHEMA_VERSION})")
    last = _meta(ro, "last_processed_minute")
    if last is None:
        raise SystemExit("no processed minute")
    at = pd.Timestamp(last) + pd.Timedelta(minutes=1)          # effective_switch_time
    retired = retired_books(old)
    text = config_toml(old, at, retired)
    PaperConfig(**{k: tuple(v) if isinstance(v, list) else v for k, v in tomllib.loads(text)["paper"].items()})
    funding = _frame(ro, "funding")[["time", "rate"]]
    funding["time"] = pd.to_datetime(funding.time, utc=True, format="mixed")
    funding = funding.sort_values("time").reset_index(drop=True)
    bars = _frame(ro, "klines_1m")[["open_time", "close"]]
    closes = pd.Series(bars.close.to_numpy(float), index=pd.to_datetime(bars.open_time, utc=True))
    positions = _frame(ro, "positions")
    positions = positions.loc[positions.book.isin(retired)].reset_index(drop=True)
    x3 = _frame(ro, "leverage_positions")
    x3 = x3.loc[x3.book.isin(retired)].reset_index(drop=True)
    for frame in (positions, x3):
        if (pd.to_datetime(frame.entry_time, utc=True) >= at).any():
            raise SystemExit("a retired position opened at/after the switch; the ledgers are not as of the switch")
    before = retired_hashes(ro, retired)
    db = Path(old.sqlite_path)
    for target in (out_config, manifest_path, backup_path(db)):
        directory = Path(target).resolve().parent
        if not (directory.is_dir() and os.access(directory, os.W_OK)):
            raise SystemExit(f"not a writable directory: {directory}")
    size = db.stat().st_size + sum(Path(str(db) + s).stat().st_size for s in ("-wal",) if Path(str(db) + s).exists())
    free = shutil.disk_usage(backup_path(db).resolve().parent).free
    if free < 2 * size:
        raise SystemExit(f"free disk {free} < 2 x DB size {size}")
    open_price = float((price or public_open)(at))           # exact USD-M BTCUSDT 1m open; no fallback source
    if not (np.isfinite(open_price) and open_price > 0):
        raise SystemExit(f"invalid switch open {open_price}")
    closes.loc[at] = open_price          # the exit minute: the leg ends at the switch open
    return {"at": at, "retired": retired, "text": text, "price": open_price, "funding": funding,
            "closes": closes.sort_index(), "positions": positions, "x3": x3, "before": before,
            "paper_k": {n: picks[catalog.BOOKS[n][0]] for n in catalog.AX_BOOKS}}


def _backup(ro: sqlite3.Connection, db: Path) -> Path:
    target = backup_path(db)
    out = None
    try:
        out = sqlite3.connect(target)      # sqlite3's context manager does not close; close explicitly
        ro.backup(out)
        check = _integrity(out)
    except Exception as error:             # any failure: no partial backup survives, no DB write follows
        if out is not None:
            out.close()
        target.unlink(missing_ok=True)
        raise SystemExit(f"backup failed: {type(error).__name__}: {error}")
    out.close()
    if check != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit(f"backup integrity_check failed: {check}")
    return target


def _integrity(connection: sqlite3.Connection) -> str:
    return connection.execute("PRAGMA integrity_check").fetchone()[0]


def _finalize(store: PaperStore, out_config: Path, manifest_path: Path, pending: dict, fail_at=None) -> dict:
    """After the DB commit (idempotent; a rerun resumes here): config backup + atomic replace, manifest."""
    text = pending.pop("config_text")
    staged = _staged(out_config)
    if out_config.exists() and out_config.read_text(encoding="utf-8") != text:
        backup = out_config.with_name(out_config.stem + ".pre_r2_52a.toml")
        if not backup.exists():
            shutil.copy2(out_config, backup)
    staged.write_text(text, encoding="utf-8")
    new = load_config(staged)
    staged.replace(out_config)
    _fail(fail_at, "config_replaced")
    manifest = {**pending, "created_utc": datetime.now(timezone.utc).isoformat(), "ax_config_path": str(out_config),
                "paper_config_hash": new.hash, "retired_after": retired_hashes(store, pending["retired_books"])}
    staged_manifest = _staged(manifest_path)
    staged_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    staged_manifest.replace(manifest_path)
    _fail(fail_at, "manifest_replaced")
    store.set_meta("r2_52a_switch_phase", "done")
    return manifest


def switch(old: PaperConfig, out_config: Path, manifest_path: Path = MANIFEST, price=None, fail_at=None) -> dict:
    """Phases: validate (read-only, zero-write) -> DB backup (sqlite backup API + integrity_check) -> stage config
    temp file -> one DB transaction (closes + meta, r2_52a_switch_phase='committed') -> finalize (config replace,
    manifest, phase='done'). paper_run's and paper_catalog's locks are held throughout; a run that failed after the
    commit resumes at finalize when rerun, and the processes refuse to start while the phase is 'committed'."""
    db, out_config, manifest_path = Path(old.sqlite_path), Path(out_config), Path(manifest_path)
    with ExitStack() as locks:
        for suffix in (".run.lock", ".catalog.lock"):
            try:
                locks.enter_context(exclusive_lock(db.with_suffix(suffix)))
            except RuntimeError:
                raise SystemExit(f"paper_run.py or paper_catalog.py is running ({suffix} held): stop both first")
        ro = read_only(db)
        try:
            phase = _meta(ro, "r2_52a_switch_phase")
            if phase == "done" or (phase is None and _meta(ro, "r2_52a_effective_switch_time")):
                raise SystemExit("R2-52A switch already applied: " + str(_meta(ro, "r2_52a_effective_switch_time")))
            if phase is None:
                plan = _validate(old, out_config, manifest_path, ro, price)
                _fail(fail_at, "validated")
                _backup(ro, db)
                _fail(fail_at, "backed_up")
        finally:
            ro.close()
        with PaperStore(db, init_schema=False) as store:      # no write at open; the first write is the transaction
            if phase == "committed":
                return _finalize(store, out_config, manifest_path, json.loads(store.get_meta("r2_52a_switch_pending")),
                                 fail_at)
            at, retired, text, price = plan["at"], plan["retired"], plan["text"], plan["price"]
            config_hash = hashlib.sha256(text.encode()).hexdigest()
            pending = {"source": "scripts/paper_ax_switch.py", "freeze": str(FREEZE),
                       "effective_switch_time": at.isoformat(), "switch_open_price": price,
                       "retired_books": list(retired), "closed_1x_positions": plan["positions"].book.tolist(),
                       "closed_x3_positions": plan["x3"].book.tolist(), "active_books": list(catalog.AX_BOOKS),
                       "visible_books": list(catalog.X3_BOOKS), "paper_k": plan["paper_k"],
                       "ax_config_hash": config_hash, "db_backup": str(backup_path(db)),
                       "retired_before": plan["before"], "config_text": text}
            _staged(out_config).write_text(text, encoding="utf-8")
            _fail(fail_at, "staged")
            with store.transaction() as connection:
                PaperStore.create_schema(connection)     # e.g. notifications_dead on a DB from older code
                for position in plan["positions"].itertuples(index=False):
                    _close_1x(store, connection, position, at, price, plan["funding"], plan["closes"])
                for position in plan["x3"].itertuples(index=False):
                    _close_x3(store, connection, position, at, price, plan["funding"])
                for key, value in (("r2_52a_effective_switch_time", at.isoformat()),
                                   ("r2_52a_retired_books", json.dumps(retired)),
                                   ("r2_52a_ax_config_hash", config_hash),
                                   ("r2_52a_switch_pending", json.dumps(pending, ensure_ascii=False)),
                                   ("r2_52a_switch_phase", "committed")):
                    connection.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET "
                                       "value=excluded.value", (key, value))
                _fail(fail_at, "in_transaction")          # rolls the whole transaction back
            _fail(fail_at, "committed")
            return _finalize(store, out_config, manifest_path, pending, fail_at)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--out-config", default="config/paper.toml")
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()
    manifest = switch(load_config(args.config), Path(args.out_config), Path(args.manifest))
    print(json.dumps({k: manifest[k] for k in ("effective_switch_time", "switch_open_price", "closed_1x_positions",
                                              "closed_x3_positions", "ax_config_hash", "db_backup")}, indent=1))


if __name__ == "__main__":
    main()
