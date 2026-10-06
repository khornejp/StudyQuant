"""127.0.0.1-only, read-only paper trading dashboard and JSON API."""

from __future__ import annotations

import csv
import io
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

from ..config import credential_status, telegram_status

STATIC = Path(__file__).with_name("index.html")
VENDOR = Path(__file__).with_name("vendor")
REPO_ROOT = Path(__file__).resolve().parents[3]
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
DEFAULT_BOOKS = ("C1", "F3", "E1", "C4")
MAX_CANDLES = 2_000


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _connect_ro(path: Path) -> sqlite3.Connection:
    """Open SQLite without schema migration, WAL mutation, or any other write."""
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _has_table(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _frame(connection: sqlite3.Connection, table: str, where: str = "",
           parameters: tuple[object, ...] = ()) -> pd.DataFrame:
    if not _has_table(connection, table):
        return pd.DataFrame()
    suffix = f" WHERE {where}" if where else ""
    return pd.read_sql_query(f"SELECT * FROM {table}{suffix}", connection, params=parameters)


def _meta(connection: sqlite3.Connection, key: str) -> str | None:
    if not _has_table(connection, "meta"):
        return None
    row = connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return None if row is None else str(row[0])


def _utc(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat()


def _candle_rows(connection: sqlite3.Connection, tf: str, start: str | None,
                 end: str | None) -> tuple[list[dict[str, object]], dict[str, object]]:
    if tf not in TF_SECONDS:
        raise ValueError("tf must be one of 1m,5m,15m,1h,4h,1d")
    seconds = TF_SECONDS[tf]
    last_row = connection.execute(
        "SELECT open_time, close FROM klines_1m WHERE closed=1 ORDER BY open_time DESC LIMIT 1"
    ).fetchone()
    if last_row is None:
        return [], {"latest_price": None, "latest_time": None}
    last_time = _utc(str(last_row["open_time"]))
    assert last_time is not None
    end_stamp = _utc(end) or (last_time + pd.Timedelta(minutes=1))
    start_stamp = _utc(start)
    if start_stamp is None:
        start_stamp = last_time.floor(tf) - pd.Timedelta(seconds=seconds * (MAX_CANDLES - 1))
    if end_stamp <= start_stamp:
        raise ValueError("to must be later than from")
    start_epoch = int(start_stamp.timestamp()) // seconds * seconds
    end_epoch = int(end_stamp.timestamp())
    # Indexed range probes avoid a million-row GROUP BY when 1d candles cover two years.
    rows = connection.execute("""
        WITH RECURSIVE bins(epoch) AS (
            VALUES(?) UNION ALL SELECT epoch+? FROM bins
            WHERE epoch+? < ? LIMIT ?
        ), ranges AS (
            SELECT epoch, MAX(epoch,?) AS lower_epoch, MIN(epoch+?,?) AS upper_epoch FROM bins
        ), candles AS (
            SELECT epoch,
                (SELECT open FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')
                 ORDER BY open_time LIMIT 1) AS open,
                (SELECT MAX(high) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS high,
                (SELECT MIN(low) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS low,
                (SELECT close FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')
                 ORDER BY open_time DESC LIMIT 1) AS close,
                (SELECT SUM(volume) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS volume
            FROM ranges
        )
        SELECT * FROM candles WHERE open IS NOT NULL ORDER BY epoch
    """, (start_epoch, seconds, seconds, end_epoch, MAX_CANDLES,
           int(start_stamp.timestamp()), seconds, end_epoch)).fetchall()
    payload = [{"time": int(row["epoch"]),
                "time_utc": datetime.fromtimestamp(int(row["epoch"]), timezone.utc).isoformat().replace("+00:00", "Z"),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"])} for row in rows]
    return payload, {"latest_price": float(last_row["close"]), "latest_time": _iso(last_time)}


def _trade_markers(trades: pd.DataFrame) -> list[dict[str, object]]:
    if trades.empty:
        return []
    if "boundary" in trades and trades.boundary.eq("PESS").any():
        trades = trades.loc[trades.boundary.eq("PESS")]
    rows: list[dict[str, object]] = []
    for trade in trades.sort_values("entry_time").to_dict("records"):
        side = int(trade["side"])
        common = {"trade_id": int(trade["id"]), "side": side,
                  "side_label": "롱" if side > 0 else "숏"}
        rows.append({**common, "kind": "entry", "time": int(_utc(trade["entry_time"]).timestamp()),
                     "time_utc": trade["entry_time"], "price": float(trade["entry_price"]),
                     "net_bps": float(trade["net_bps"]), "exit_reason": trade["exit_reason"]})
        rows.append({**common, "kind": "exit", "time": int(_utc(trade["exit_time"]).timestamp()),
                     "time_utc": trade["exit_time"], "price": float(trade["exit_price"]),
                     "net_bps": float(trade["net_bps"]), "exit_reason": trade["exit_reason"]})
    return rows


def _drawdown(values: pd.Series) -> pd.Series:
    return values.cummax().clip(lower=0) - values


def _performance(connection: sqlite3.Connection, book: str,
                 daily_prices: list[dict[str, object]] | None = None,
                 start_time: str | None = None) -> dict[str, object]:
    daily = _frame(connection, "daily_pnl", "book=?", (book,))
    trades = _frame(connection, "trades", "book=?", (book,))
    series: list[dict[str, object]] = []
    summary: dict[str, object] = {"book": book, "trade_count": 0, "win_rate": None,
                                  "net_pess_bps": 0.0, "net_opt_bps": 0.0,
                                  "max_drawdown_bps": 0.0, "buy_hold_bps": None,
                                  "vs_buy_hold_bps": None}
    if not trades.empty:
        pess = trades.loc[trades.boundary.eq("PESS")] if "boundary" in trades else trades
        summary["trade_count"] = int(len(pess))
        summary["win_rate"] = None if pess.empty else float((pess.net_bps > 0).mean())
    if not daily.empty:
        for boundary, part in daily.groupby("boundary", sort=True):
            part = part.sort_values("date")
            cumulative = part.net_bps.astype(float).cumsum()
            drawdown = _drawdown(cumulative)
            series.append({"name": str(boundary), "date": part.date.astype(str).tolist(),
                           "cumulative_net_bps": cumulative.tolist(),
                           "drawdown_bps": drawdown.tolist()})
            summary[f"net_{str(boundary).lower()}_bps"] = float(cumulative.iloc[-1])
            if boundary == "PESS":
                summary["max_drawdown_bps"] = float(drawdown.max())
        monthly = (daily.assign(month=daily.date.astype(str).str[:7])
                   .groupby(["month", "boundary"], as_index=False).net_bps.sum())
        monthly_rows = _records(monthly)
    else:
        monthly_rows = []
    if daily_prices is None:
        daily_prices, _ = _candle_rows(connection, "1d", None, None)
    prices = pd.DataFrame(daily_prices or [])
    if start_time is not None and not prices.empty:
        # Buy-and-hold is the paper benchmark, so it starts at T0 like the books (none before T0).
        prices = prices.loc[pd.to_datetime(prices.time_utc, utc=True) >= _utc(start_time)]
    if not prices.empty:
        buy_hold = np.log(prices.close.astype(float) / float(prices.open.iloc[0])) * 10_000
        series.append({"name": "BUY_HOLD", "date": prices.time_utc.str[:10].tolist(),
                       "cumulative_net_bps": buy_hold.tolist(),
                       "drawdown_bps": _drawdown(buy_hold).tolist()})
        summary["buy_hold_bps"] = float(buy_hold.iloc[-1])
        summary["vs_buy_hold_bps"] = float(summary["net_pess_bps"]) - float(buy_hold.iloc[-1])
    return {"schema_version": 2, "book": book, "summary": summary,
            "series": series, "monthly": monthly_rows}


def _book_rows(connection: sqlite3.Connection, book_names: tuple[str, ...],
               start_time: str | None) -> list[dict[str, object]]:
    positions, trades, daily = (_frame(connection, name) for name in ("positions", "trades", "daily_pnl"))
    last = _meta(connection, "last_processed_minute")
    names = list(dict.fromkeys((*book_names, *sorted(set(trades.get("book", ())) |
                                                   set(positions.get("book", ()))))))
    started = start_time is None or (last is not None and _utc(last) >= _utc(start_time))
    next_funding = _iso(_utc(last).floor("8h") + pd.Timedelta(hours=8)) if last else None
    rows = []
    for name in names:
        trade_part = trades.loc[trades.book.eq(name)] if not trades.empty else trades
        position = positions.loc[positions.book.eq(name)] if not positions.empty else positions
        daily_part = daily.loc[daily.book.eq(name)] if not daily.empty else daily
        net = {boundary: float(part.net_bps.sum())
               for boundary, part in daily_part.groupby("boundary")} if not daily_part.empty else {}
        pess = trade_part.loc[trade_part.boundary.eq("PESS")] if (
            not trade_part.empty and "boundary" in trade_part) else trade_part
        cumulative = daily_part.loc[daily_part.boundary.eq("PESS"), "net_bps"].cumsum(
            ) if not daily_part.empty else pd.Series(dtype=float)
        rows.append({"book": name, "position": None if position.empty else _records(position)[0],
                     "trades": int(len(pess)),
                     "net_bps": float(daily_part.net_bps.sum()) if not daily_part.empty else 0.0,
                     "net_pess_bps": net.get("PESS", 0.0), "net_opt_bps": net.get("OPT", 0.0),
                     "win_rate": None if pess.empty else float((pess.net_bps > 0).mean()),
                     "max_drawdown_bps": 0.0 if cumulative.empty else float(_drawdown(cumulative).max()),
                     "next_funding": next_funding,
                     "status": "running" if started else f"T0 대기 ({start_time})"})
    return rows


class DashboardServer(ThreadingHTTPServer):
    store_path: Path
    data_root: Path


def _handler(store_path: Path, data_root: Path, books: tuple[str, ...] = (),
             start_time: str | None = None) -> type[BaseHTTPRequestHandler]:
    configured_books = books or DEFAULT_BOOKS

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, value: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(value)

        def _json(self, value: object, status: int = 200) -> None:
            self._send(json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode(),
                       "application/json; charset=utf-8", status)

        def _csv(self, frame: pd.DataFrame) -> None:
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(frame.columns))
            writer.writeheader(); writer.writerows(_records(frame))
            self._send(stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed, query = urlparse(self.path), parse_qs(urlparse(self.path).query)
            try:
                static = {"/": (STATIC, "text/html; charset=utf-8"),
                          "/vendor/lightweight-charts.standalone.production.js":
                              (VENDOR / "lightweight-charts.standalone.production.js", "application/javascript; charset=utf-8"),
                          "/vendor/LICENSE": (VENDOR / "LICENSE", "text/plain; charset=utf-8"),
                          "/vendor/README.md": (VENDOR / "README.md", "text/markdown; charset=utf-8")}
                if parsed.path in static:
                    path, content_type = static[parsed.path]
                    self._send(path.read_bytes(), content_type); return
                if parsed.path == "/plotly.min.js":
                    self._send(get_plotlyjs().encode(), "application/javascript; charset=utf-8"); return
                with _connect_ro(store_path) as connection:
                    if self._v2(connection, parsed.path, query): return
                    if self._v1(connection, parsed.path, query): return
                self._json({"error": "not found"}, 404) if parsed.path.startswith("/api/") else self._send(
                    b"not found", "text/plain", 404)
            except (ValueError, TypeError) as error:
                self._json({"error": str(error)}, 400)

        def _v2(self, connection: sqlite3.Connection, path: str,
                query: dict[str, list[str]]) -> bool:
            if path == "/api/candles":
                tf = query.get("tf", ["1h"])[0]
                rows, latest = _candle_rows(connection, tf, query.get("from", [None])[0],
                                            query.get("to", [None])[0])
                self._json({"schema_version": 2, "tf": tf, "max_rows": MAX_CANDLES,
                            "rows": rows, **latest}); return True
            if path == "/api/markers":
                book = query.get("book", [configured_books[0]])[0]
                self._json({"schema_version": 2, "book": book,
                            "rows": _trade_markers(_frame(connection, "trades", "book=?", (book,)))})
                return True
            if path in {"/api/positions", "/api/positions.csv"}:
                frame = _frame(connection, "positions")
                if query.get("book") and not frame.empty: frame = frame.loc[frame.book.eq(query["book"][0])]
                self._csv(frame) if path.endswith(".csv") else self._json({"schema_version": 2, "rows": _records(frame)})
                return True
            if path in {"/api/trades", "/api/trades.csv", "/api/signals", "/api/signals.csv"}:
                table = "trades" if "trades" in path else "signals"
                time_column = "entry_time" if table == "trades" else "decision_time"
                clauses, parameters = [], []
                if query.get("book"): clauses.append("book=?"); parameters.append(query["book"][0])
                if query.get("from"): clauses.append(f"{time_column}>=?"); parameters.append(_iso(_utc(query["from"][0])))
                if query.get("to"): clauses.append(f"{time_column}<?"); parameters.append(_iso(_utc(query["to"][0])))
                frame = _frame(connection, table, " AND ".join(clauses), tuple(parameters))
                if not frame.empty: frame = frame.sort_values(time_column, ascending=False, kind="stable")
                self._csv(frame) if path.endswith(".csv") else self._json({"schema_version": 1, "rows": _records(frame)})
                return True
            if path == "/api/performance":
                self._json(_performance(connection, query.get("book", [configured_books[0]])[0], start_time=start_time)); return True
            if path == "/api/status":
                self._json(self._status(connection)); return True
            return False

        def _v1(self, connection: sqlite3.Connection, path: str,
                query: dict[str, list[str]]) -> bool:
            if path == "/api/summary":
                positions, trades, signals, daily = (_frame(connection, name) for name in
                                                      ("positions", "trades", "signals", "daily_pnl"))
                self._json({"schema_version": 1, "books": sorted(set(trades.get("book", ()))),
                            "position_count": len(positions), "trade_count": len(trades),
                            "signal_count": len(signals), "daily_count": len(daily)}); return True
            if path == "/api/books":
                self._json({"schema_version": 1, "rows": _book_rows(connection, configured_books, start_time)}); return True
            if path == "/api/chart":
                rows = []
                daily_prices, _ = _candle_rows(connection, "1d", None, None)
                for book in configured_books:
                    for item in _performance(connection, book, daily_prices, start_time)["series"]:
                        rows.append({"book": book if item["name"] != "BUY_HOLD" else "BUY_HOLD",
                                     "boundary": item["name"], **{key: item[key] for key in
                                     ("date", "cumulative_net_bps", "drawdown_bps")}, "monthly": {}})
                self._json({"schema_version": 1, "series": rows}); return True
            if path == "/api/price":
                candles, _ = _candle_rows(connection, "1h", None, None)
                trades = _frame(connection, "trades")
                markers = [] if trades.empty else _records(trades[["book", "entry_time", "exit_time",
                                                                   "entry_price", "exit_price", "side"]])
                self._json({"schema_version": 1, "price": [{"open_time": x["time_utc"], "close": x["close"]}
                                                            for x in candles], "markers": markers}); return True
            if path == "/api/reference":
                self._json({"schema_version": 1, "rows": self._reference()}); return True
            if path == "/api/health":
                status = self._status(connection)
                self._json({"schema_version": 1, "mode": "paper", "last_update": status["last_update_utc"],
                            "latest": status["sources"], "revision_count": status["reconcile"]["revision_count"],
                            "latency": status["latency"], "ws_closed_events": status["ws_closed_events"],
                            "notifications": status["notifications"], "book_ticker": status["book_ticker"],
                            "disk_free_ratio": status["disk_free_ratio"], "disk_warning": status["disk_warning"],
                            "credentials": credential_status(), "telegram": status["telegram"]}); return True
            return False

        def _reference(self) -> list[dict[str, object]]:
            rows = []
            timing_path = REPO_ROOT / "out/k45_ls_ratio_timing_r2_35_20261006/performance.parquet"
            if timing_path.exists():
                frame = pd.read_parquet(timing_path)
                frame = frame.loc[frame.delay_min.isin((0, 5)) & frame.cost_bps.eq(4)].copy()
                frame["timing_status"] = frame.delay_min.map({
                    5: "채택:+5분(create_time+5m<T)", 0: "legacy(시각 결함):create_time 즉시 가용"})
                frame["reference_primary"] = frame.delay_min.eq(5); rows.extend(_records(frame))
            e1_path = REPO_ROOT / "out/k45_candidate_compare_r2_23_20261004/metrics.parquet"
            if e1_path.exists():
                frame = pd.read_parquet(e1_path)
                frame = frame.loc[frame.candidate.eq("E1|1h|3|signal|L") &
                                  frame.segment.isin(("DEV_COMMON", "HOLD_B"))].copy()
                frame["timing_status"] = "not-affected:no-ls-ratio"; frame["reference_primary"] = True
                rows.extend(_records(frame))
            return rows

        def _status(self, connection: sqlite3.Connection) -> dict[str, object]:
            now = pd.Timestamp.now(tz="UTC")
            last = _meta(connection, "last_processed_minute")
            if last is None:
                last = connection.execute("SELECT MAX(open_time) FROM klines_1m").fetchone()[0]
            last_stamp, start_stamp = _utc(last), _utc(start_time)
            started = start_stamp is None or now >= start_stamp
            elapsed_days = 0 if not started or start_stamp is None else int((now - start_stamp).total_seconds() // 86400)
            latest_health, recent_health = pd.DataFrame(), pd.DataFrame()
            if _has_table(connection, "collector_health"):
                latest_health = pd.read_sql_query("""
                    SELECT * FROM collector_health ORDER BY minute DESC LIMIT 10000
                """, connection)
                latest_health = (latest_health.sort_values("minute", ascending=False)
                                 .drop_duplicates("source").sort_values("source"))
                recent_health = _frame(connection, "collector_health", "minute>=?",
                                       (_iso((last_stamp or now) - pd.Timedelta(hours=24)),))
            latency = [{"source": source, "count": len(part),
                        "p50_ms": float(part.lag_ms.quantile(.5)), "p95_ms": float(part.lag_ms.quantile(.95))}
                       for source, part in recent_health.dropna(subset=["lag_ms"]).groupby("source")]
            gap_count = int(recent_health.gaps.sum()) if not recent_health.empty else 0
            stale = last_stamp is None or (now >= last_stamp and now - last_stamp > pd.Timedelta(minutes=3))
            delayed = stale or not latency or max((x["p95_ms"] for x in latency), default=0) > 10_000
            state = "갭" if gap_count else "지연" if delayed else "정상"
            counts: dict[str, int] = {}
            if _has_table(connection, "notifications"):
                counts = {str(row[0]): int(row[1]) for row in connection.execute(
                    "SELECT status, COUNT(*) FROM notifications GROUP BY status")}
            ticker_count, ticker_last, ticker_gaps = 0, None, 0
            if _has_table(connection, "book_ticker_1m"):
                ticker_row = connection.execute(
                    "SELECT COUNT(*), MIN(minute), MAX(minute) FROM book_ticker_1m").fetchone()
                ticker_count, ticker_first, ticker_last = int(ticker_row[0]), ticker_row[1], ticker_row[2]
                if ticker_count > 1:
                    span = (_utc(ticker_last) - _utc(ticker_first)) / pd.Timedelta(minutes=1)
                    ticker_gaps = max(0, int(span) + 1 - ticker_count)
            revision_count = (int(connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0])
                              if _has_table(connection, "revisions") else 0)
            usage = shutil.disk_usage(data_root if data_root.exists() else data_root.parent)
            market_rows, latest = _candle_rows(connection, "1m",
                                                _iso((last_stamp or now) - pd.Timedelta(hours=24)), None)
            change = None if not market_rows else (float(latest["latest_price"]) / float(market_rows[0]["open"]) - 1) * 100
            return {"schema_version": 2, "mode": "paper", "symbol": "BTCUSDT", "contract": "무기한",
                    "market": {**latest, "change_24h_pct": change},
                    "t0": {"start_time": start_time, "state": "진행" if started else "대기", "elapsed_days": elapsed_days},
                    "collector": {"state": state, "gap_count_24h": gap_count},
                    "sources": _records(latest_health), "latency": latency,
                    "last_update_utc": None if last_stamp is None else _iso(last_stamp),
                    "last_refresh_utc": _iso(now), "last_refresh_kst": now.tz_convert("Asia/Seoul").isoformat(),
                    "ws_closed_events": int(_meta(connection, "ws_closed_events") or 0),
                    "notifications": {"pending": int(counts.get("pending", 0)), "failed": int(counts.get("failed", 0))},
                    "book_ticker": {"rows": ticker_count, "gaps": ticker_gaps,
                                    "last_update": ticker_last},
                    "reconcile": {"result": "일치" if revision_count == 0 else "불일치",
                                  "revision_count": revision_count},
                    "disk_free_ratio": usage.free / usage.total, "disk_warning": usage.free / usage.total < .10,
                    "telegram": telegram_status()}

    return Handler


def make_server(store_path: str | Path, data_root: str | Path,
                host: str = "127.0.0.1", port: int = 8765, books: tuple[str, ...] = (),
                start_time: str | None = None) -> DashboardServer:
    if host != "127.0.0.1":
        raise ValueError("dashboard must bind 127.0.0.1")
    path = Path(store_path)
    if not path.exists():
        raise FileNotFoundError(path)
    server = DashboardServer((host, port), _handler(path, Path(data_root), tuple(books), start_time))
    server.store_path, server.data_root = path, Path(data_root)
    return server


__all__ = ["DashboardServer", "make_server"]
