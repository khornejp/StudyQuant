"""127.0.0.1-only stdlib HTTP dashboard and JSON API."""

from __future__ import annotations

import csv
import io
import json
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
from plotly.offline import get_plotlyjs

from ..config import credential_status, telegram_status
from ..store import PaperStore

STATIC = Path(__file__).with_name("index.html")
REPO_ROOT = Path(__file__).resolve().parents[3]


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict("records")


class DashboardServer(ThreadingHTTPServer):
    store_path: Path
    data_root: Path


def _handler(store_path: Path, data_root: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, value: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(value)

        def _json(self, value: object) -> None:
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode()
            self._send(payload, "application/json; charset=utf-8")

        def _frames(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            with PaperStore(store_path) as store:
                return (store.frame("positions"), store.frame("trades"),
                        store.frame("signals"), store.frame("daily_pnl"))

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/":
                self._send(STATIC.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/plotly.min.js":
                self._send(get_plotlyjs().encode(), "application/javascript; charset=utf-8")
                return
            if parsed.path == "/api/summary":
                positions, trades, signals, daily = self._frames()
                self._json({"schema_version": 1, "books": sorted(set(trades.get("book", ()))),
                            "position_count": len(positions), "trade_count": len(trades),
                            "signal_count": len(signals), "daily_count": len(daily)})
                return
            if parsed.path == "/api/books":
                positions, trades, _, daily = self._frames()
                with PaperStore(store_path) as store:
                    last = store.get_meta("last_processed_minute")
                next_funding = None
                if last:
                    stamp = pd.Timestamp(last)
                    next_funding = (stamp.floor("8h") + pd.Timedelta(hours=8)).isoformat()
                rows = []
                for name in sorted(set(trades.get("book", ())) | set(positions.get("book", ()))):
                    trade_part = trades.loc[trades.book.eq(name)]
                    position = positions.loc[positions.book.eq(name)]
                    rows.append({"book": name, "position": None if position.empty else
                                 _records(position)[0], "trades": len(trade_part),
                                 "net_bps": float(daily.loc[daily.book.eq(name), "net_bps"].sum()),
                                 "next_funding": next_funding})
                self._json({"schema_version": 1, "rows": rows})
                return
            if parsed.path in {"/api/trades", "/api/trades.csv"}:
                _, trades, _, _ = self._frames()
                if query.get("book"):
                    trades = trades.loc[trades.book.eq(query["book"][0])]
                trades = trades.sort_values("entry_time", ascending=False, kind="stable")
                if parsed.path.endswith(".csv"):
                    stream = io.StringIO()
                    writer = csv.DictWriter(stream, fieldnames=list(trades.columns))
                    writer.writeheader(); writer.writerows(_records(trades))
                    self._send(stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")
                else:
                    self._json({"schema_version": 1, "rows": _records(trades)})
                return
            if parsed.path == "/api/signals":
                _, _, signals, _ = self._frames()
                self._json({"schema_version": 1, "rows": _records(signals)})
                return
            if parsed.path == "/api/chart":
                _, _, _, daily = self._frames()
                rows = []
                for (name, boundary), part in daily.groupby(["book", "boundary"]):
                    part = part.sort_values("date")
                    cumulative = part.net_bps.cumsum()
                    rows.append({"book": name, "boundary": boundary,
                                 "date": part.date.tolist(),
                                 "cumulative_net_bps": cumulative.tolist(),
                                 "drawdown_bps": (cumulative.cummax() - cumulative).tolist(),
                                 "monthly": part.assign(month=part.date.str[:7]).groupby(
                                     "month").net_bps.sum().to_dict()})
                reference_daily = Path(
                    "out/k45_hold_a_exclude_bookticker_r2_32_20261005/hold_a/daily_pnl.parquet")
                if reference_daily.exists():
                    buy = pd.read_parquet(reference_daily)
                    buy = buy.loc[buy.book.eq("B0") & buy.boundary.eq("PESS") & buy.cost_bps.eq(4)]
                    rows.append({"book": "BUY_HOLD", "boundary": "PESS",
                                 "date": buy.date.astype(str).tolist(),
                                 "cumulative_net_bps": buy.net_bps.cumsum().tolist(),
                                 "drawdown_bps": (buy.net_bps.cumsum().cummax() -
                                                   buy.net_bps.cumsum()).tolist(),
                                 "monthly": buy.assign(month=buy.date.astype(str).str[:7]).groupby(
                                     "month").net_bps.sum().to_dict()})
                self._json({"schema_version": 1, "series": rows})
                return
            if parsed.path == "/api/price":
                with PaperStore(store_path) as store:
                    prices = store.frame("klines_1m")
                    trades = store.frame("trades")
                prices = prices.iloc[::60]
                self._json({"schema_version": 1,
                            "price": _records(prices[["open_time", "close"]]),
                            "markers": _records(trades[["book", "entry_time", "exit_time",
                                                        "entry_price", "exit_price", "side"]])})
                return
            if parsed.path == "/api/reference":
                rows = []
                timing_path = REPO_ROOT / "out/k45_ls_ratio_timing_r2_35_20261006/performance.parquet"
                if timing_path.exists():
                    frame = pd.read_parquet(timing_path)
                    frame = frame.loc[frame.delay_min.isin((0, 5)) & frame.cost_bps.eq(4)]
                    frame["timing_status"] = frame.delay_min.map({
                        5: "채택:+5분(create_time+5m<T)",
                        0: "legacy(시각 결함):create_time 즉시 가용"})
                    frame["reference_primary"] = frame.delay_min.eq(5)
                    rows.extend(_records(frame))
                e1_path = REPO_ROOT / "out/k45_candidate_compare_r2_23_20261004/metrics.parquet"
                if e1_path.exists():
                    frame = pd.read_parquet(e1_path)
                    frame = frame.loc[frame.candidate.eq("E1|1h|3|signal|L") &
                                      frame.segment.isin(("DEV_COMMON", "HOLD_B"))].copy()
                    frame["timing_status"] = "not-affected:no-ls-ratio"
                    frame["reference_primary"] = True
                    rows.extend(_records(frame))
                self._json({"schema_version": 1, "rows": rows})
                return
            if parsed.path == "/api/health":
                with PaperStore(store_path) as store:
                    health = store.frame("collector_health")
                    revisions = store.frame("revisions")
                    notifications = store.frame("notifications")
                    book_ticker = store.frame("book_ticker_1m")
                    mode = "paper"
                    last = store.get_meta("last_processed_minute")
                    ws_closed_events = int(store.get_meta("ws_closed_events") or 0)
                usage = shutil.disk_usage(data_root if data_root.exists() else data_root.parent)
                latency = []
                for source, part in health.dropna(subset=["lag_ms"]).groupby("source"):
                    latency.append({"source": source, "count": len(part),
                                    "p50_ms": float(part.lag_ms.quantile(.5)),
                                    "p95_ms": float(part.lag_ms.quantile(.95))})
                notification_counts = notifications.status.value_counts().to_dict()
                book_last = None if book_ticker.empty else str(book_ticker.minute.max())
                book_gaps = 0
                if len(book_ticker) > 1:
                    minutes = pd.to_datetime(book_ticker.minute, utc=True).sort_values()
                    book_gaps = int(((minutes.diff() / pd.Timedelta(minutes=1)) - 1).clip(lower=0).sum())
                self._json({"schema_version": 1, "mode": mode, "last_update": last,
                            "latest": _records(health.tail(20)), "revision_count": len(revisions),
                            "latency": latency, "ws_closed_events": ws_closed_events,
                            "notifications": {"pending": int(notification_counts.get("pending", 0)),
                                              "failed": int(notification_counts.get("failed", 0))},
                            "book_ticker": {"rows": len(book_ticker), "gaps": book_gaps,
                                            "last_update": book_last},
                            "disk_free_ratio": usage.free / usage.total,
                            "disk_warning": usage.free / usage.total < .10,
                            "credentials": credential_status(),
                            "telegram": telegram_status()})
                return
            self._json({"error": "not found"}) if parsed.path.startswith("/api/") else self._send(
                b"not found", "text/plain", 404)

    return Handler


def make_server(store_path: str | Path, data_root: str | Path,
                host: str = "127.0.0.1", port: int = 8765) -> DashboardServer:
    if host != "127.0.0.1":
        raise ValueError("dashboard must bind 127.0.0.1")
    server = DashboardServer((host, port), _handler(Path(store_path), Path(data_root)))
    server.store_path, server.data_root = Path(store_path), Path(data_root)
    return server


__all__ = ["DashboardServer", "make_server"]
