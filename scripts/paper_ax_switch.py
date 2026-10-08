"""R2-52A paper switch (out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json paper_rollout.retirement): one-shot.

Run with paper_run.py and paper_catalog.py stopped. effective_switch_time = the open of the first minute after the
last processed minute. Every open retired 1x / x3 position is closed at that open (MIGRATION_END, normal exit fee,
PESS funding up to the switch, no synthetic entry fee); the retired books are snapshotted, their per-table row
counts and hashes are recorded before and after, and the new AX configuration (27 sources, 27 x3, telegram x3 only)
is written. Paper only: the price comes from the store or Binance public REST klines (no authenticated action).
Usage: python scripts/paper_ax_switch.py [--config config/paper.toml] [--out-config config/paper.toml]
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd  # noqa: E402
from btcusdt_quant.paper import book, catalog, leverage  # noqa: E402
from btcusdt_quant.paper.collector import PublicBinanceClient, parse_kline  # noqa: E402
from btcusdt_quant.paper.config import PaperConfig, load_config  # noqa: E402
from btcusdt_quant.paper.store import PaperStore, utc_text  # noqa: E402

MANIFEST = ROOT / "out/k45_rl_r2_48_20261007/r2_52a/paper_switch_manifest.json"
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


def retired_hashes(store: PaperStore, books) -> dict:
    """Per-table row count and sha256 of the retired books' rows (sorted, surrogate id excluded)."""
    out = {}
    names = sorted(books)
    marks = ",".join("?" * len(names))
    for table in TABLES:
        exists = store.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                          (table,)).fetchone()
        frame = (pd.read_sql_query(f"SELECT * FROM {table} WHERE book IN ({marks})", store.connection, params=names)
                 if exists and names else pd.DataFrame())
        frame = frame.drop(columns=[c for c in ("id",) if c in frame])
        text = frame.sort_values(list(frame.columns)).to_csv(index=False) if len(frame) else ""
        out[table] = {"rows": int(len(frame)), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    return out


def public_open(switch: pd.Timestamp) -> float:
    """Open of the switch minute from Binance USD-M public klines (unauthenticated GET, same as the collector)."""
    rows = PublicBinanceClient().get("/fapi/v1/klines", {"symbol": "BTCUSDT", "interval": "1m",
                                                         "startTime": int(switch.timestamp() * 1000), "limit": 1})
    kline = parse_kline(rows[0])
    if kline["open_time"] != switch:
        raise SystemExit(f"no kline at {switch} yet")
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
    side, notional, margin = int(position.side), float(position.notional_usd), float(position.margin_usd)
    entry = pd.Timestamp(position.entry_time)
    funding_usd = sum(leverage._funding_cashflows(funding, side, notional, entry, switch).values())
    gross = notional * side * (price / float(position.entry_price) - 1.0)
    cost = notional * 4.0 / 10_000.0                           # the existing x3 rule: round trip booked at the close
    pnl = gross + funding_usd - cost
    state = pd.read_sql_query("SELECT * FROM leverage_state WHERE book=?", connection, params=(position.book,))
    before = float(state.balance_usd.iloc[0]) if len(state) else float(position.balance_usd)
    after = before + pnl
    store.insert("leverage_trades", {
        "book": position.book, "source_book": position.source_book, "candidate": position.candidate,
        "entry_time": utc_text(entry), "exit_time": utc_text(switch), "side": side,
        "entry_price": float(position.entry_price), "exit_price": price, "notional_usd": notional,
        "margin_usd": margin, "initial_liquidation_price": float(position.liquidation_price),
        "liquidation_price": float(position.liquidation_price), "max_adverse_pnl_usd": min(0.0, pnl), "liquidated": 0,
        "gross_pnl_usd": gross, "cost_usd": cost, "funding_usd": funding_usd, "pnl_usd": pnl,
        "balance_before_usd": before, "balance_after_usd": after,
        "hold_minutes": float((switch - entry) / pd.Timedelta(minutes=1)), "exit_reason": REASON}, connection)
    budget = 100.0
    connection.execute("UPDATE leverage_state SET balance_usd=?, cumulative_pnl_usd=?, cumulative_return_pct=?, "
                       "updated_at=? WHERE book=?", (after, after - budget, (after / budget - 1) * 100, utc_text(switch),
                                                     position.book))
    day = switch.strftime("%Y-%m-%d")
    prior = connection.execute("SELECT balance_usd FROM leverage_daily WHERE book=? AND date<? ORDER BY date DESC "
                               "LIMIT 1", (position.book, day)).fetchone()
    previous = budget if prior is None else float(prior[0])
    connection.execute("INSERT INTO leverage_daily(book,date,balance_usd,day_pnl_usd,max_drawdown_usd,max_drawdown_pct) "
                       "VALUES(?,?,?,?,0,0) ON CONFLICT(book,date) DO UPDATE SET balance_usd=excluded.balance_usd,"
                       "day_pnl_usd=excluded.day_pnl_usd", (position.book, day, after, after - previous))


def switch(old: PaperConfig, out_config: Path, manifest_path: Path = MANIFEST, price=None,
           check_lock: bool = True) -> dict:
    with PaperStore(old.sqlite_path) as store:
        if store.get_meta("r2_52a_effective_switch_time"):
            raise SystemExit("R2-52A switch already applied: " + store.get_meta("r2_52a_effective_switch_time"))
        if check_lock:
            import msvcrt
            with open(Path(old.sqlite_path).with_suffix(".run.lock"), "a+") as lock:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    raise SystemExit("paper_run.py is running: stop it (and paper_catalog.py) first")
        last = store.get_meta("last_processed_minute")
        if last is None:
            raise SystemExit("no processed minute")
        at = pd.Timestamp(last) + pd.Timedelta(minutes=1)          # effective_switch_time
        price = float((price or public_open)(at))
        retired = retired_books(old)
        before = retired_hashes(store, retired)
        funding = store.frame("funding")[["time", "rate"]]
        funding["time"] = pd.to_datetime(funding.time, utc=True, format="mixed")
        funding = funding.sort_values("time").reset_index(drop=True)
        closes = store.frame("klines_1m")[["open_time", "close"]]
        closes = pd.Series(closes.close.to_numpy(float), index=pd.to_datetime(closes.open_time, utc=True))
        closes.loc[at] = price               # the exit minute: the leg ends at the switch open
        closes = closes.sort_index()
        positions = store.frame("positions")
        positions = positions.loc[positions.book.isin(retired)] if not positions.empty else positions
        x3 = store.frame("leverage_positions")
        x3 = x3.loc[x3.book.isin(retired)] if not x3.empty else x3
        if (pd.to_datetime(positions.entry_time, utc=True) >= at).any():
            raise SystemExit("a retired position opened at/after the switch; the ledgers are not as of the switch")
        new_text = config_toml(old, at, retired)
        with store.transaction() as connection:
            for position in positions.itertuples(index=False):
                _close_1x(store, connection, position, at, price, funding, closes)
            for position in x3.itertuples(index=False):
                _close_x3(store, connection, position, at, price, funding)
            config_hash = hashlib.sha256(new_text.encode()).hexdigest()
            for key, value in (("r2_52a_effective_switch_time", at.isoformat()),
                               ("r2_52a_retired_books", json.dumps(retired)),
                               ("r2_52a_ax_config_hash", config_hash)):
                connection.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET "
                                   "value=excluded.value", (key, value))
        after = retired_hashes(store, retired)
    out_config = Path(out_config)
    if out_config.exists():
        shutil.copy2(out_config, out_config.with_name(out_config.stem + ".pre_r2_52a.toml"))
    out_config.write_text(new_text, encoding="utf-8")
    new = load_config(out_config)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "source": "scripts/paper_ax_switch.py",
                "freeze": "out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json",
                "effective_switch_time": at.isoformat(), "switch_open_price": price,
                "retired_books": list(retired), "closed_1x_positions": positions.book.tolist(),
                "closed_x3_positions": x3.book.tolist(), "active_books": list(new.books),
                "visible_books": list(new.telegram_books), "paper_k": {n: catalog.paper_k()[catalog.BOOKS[n][0]]
                                                                       for n in new.books},
                "ax_config_hash": config_hash, "ax_config_path": str(out_config), "paper_config_hash": new.hash,
                "retired_before": before, "retired_after": after}
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/paper.toml")
    parser.add_argument("--out-config", default="config/paper.toml")
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()
    manifest = switch(load_config(args.config), Path(args.out_config), Path(args.manifest))
    print(json.dumps({k: manifest[k] for k in ("effective_switch_time", "switch_open_price", "closed_1x_positions",
                                              "closed_x3_positions", "ax_config_hash")}, indent=1))


if __name__ == "__main__":
    main()
