"""Public Binance USD-M collectors; no credentials or order paths."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from . import futures_metrics as fm
from .engine import PaperEngine
from .store import PaperStore

BASE_URL = "https://fapi.binance.com"
# Binance USD-M serves kline streams only on the /market path; /ws/ acks but sends no klines (verified 2026-10-06).
KLINE_WS_URL = "wss://fstream.binance.com/market/ws/btcusdt@kline_1m"
BOOK_WS_URL = "wss://fstream.binance.com/ws/btcusdt@bookTicker"
LOG = logging.getLogger(__name__)


def _utc_ms(value: object) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def parse_kline(row: list[object]) -> dict[str, object]:
    return {"open_time": pd.to_datetime(int(row[0]), unit="ms", utc=True),
            "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
            "close": float(row[4]), "volume": float(row[5]),
            "quote_volume": float(row[7]), "number_of_trades": int(row[8]),
            "taker_buy_base_volume": float(row[9]),
            "taker_buy_quote_volume": float(row[10]), "closed": True}


def parse_ws_forming(payload: Mapping[str, object]) -> dict[str, object] | None:
    """In-progress bar for display only; never stored as a kline or used by signals."""
    kline = payload.get("k", payload.get("data", {}).get("k", {}))
    if not isinstance(kline, Mapping) or bool(kline.get("x")) or "t" not in kline:
        return None
    return {"open_time": pd.to_datetime(int(kline["t"]), unit="ms", utc=True).isoformat(),
            "open": float(kline["o"]), "high": float(kline["h"]), "low": float(kline["l"]),
            "close": float(kline["c"]), "volume": float(kline["v"]),
            "updated_at": pd.Timestamp.now(tz="UTC").isoformat()}


def parse_ws_kline(message: str | Mapping[str, object]) -> dict[str, object] | None:
    payload = json.loads(message) if isinstance(message, str) else message
    kline = payload.get("k", payload.get("data", {}).get("k", {}))
    if payload.get("e", payload.get("data", {}).get("e")) not in {None, "kline"}:
        return None
    if not isinstance(kline, Mapping) or not bool(kline.get("x")):
        return None
    return {"open_time": pd.to_datetime(int(kline["t"]), unit="ms", utc=True),
            "open": float(kline["o"]), "high": float(kline["h"]),
            "low": float(kline["l"]), "close": float(kline["c"]),
            "volume": float(kline["v"]), "quote_volume": float(kline.get("q", 0)),
            "number_of_trades": int(kline.get("n", 0)),
            "taker_buy_base_volume": float(kline.get("V", 0)),
            "taker_buy_quote_volume": float(kline.get("Q", 0)), "closed": True}


def parse_book_ticker(message: str | Mapping[str, object]) -> dict[str, object] | None:
    payload = json.loads(message) if isinstance(message, str) else message
    payload = payload.get("data", payload)
    if payload.get("e") not in {None, "bookTicker"}:
        return None
    if not {"T", "b", "B", "a", "A"}.issubset(payload):
        return None
    return {"transaction_time": int(payload["T"]),
            "best_bid_price": float(payload["b"]), "best_bid_qty": float(payload["B"]),
            "best_ask_price": float(payload["a"]), "best_ask_qty": float(payload["A"])}


def reduce_book_ticker(rows: list[Mapping[str, object]]) -> dict[str, object] | None:
    """Match out/build_spread_features.reduce_chunk population moments."""
    if not rows:
        return None
    chunk = pd.DataFrame(rows)
    bid = chunk.best_bid_price.to_numpy(float)
    ask = chunk.best_ask_price.to_numpy(float)
    mid = (bid + ask) / 2.0
    ok = np.isfinite(mid) & (mid > 0) & (ask >= bid)
    chunk = chunk.loc[ok].copy()
    if chunk.empty:
        return None
    spread = ((ask - bid) / mid * 10_000.0)[ok]
    bid_qty = chunk.best_bid_qty.to_numpy(float)
    ask_qty = chunk.best_ask_qty.to_numpy(float)
    total = bid_qty + ask_qty
    imbalance = np.where(total > 0, (bid_qty - ask_qty) / np.where(total > 0, total, 1.0),
                         np.nan)
    values = {"minute": pd.to_datetime(chunk.transaction_time.iloc[0], unit="ms", utc=True).floor("min"),
              "spread_bps_mean": float(np.mean(spread)),
              "spread_bps_max": float(np.max(spread)),
              "spread_bps_std": float(np.std(spread, ddof=0)),
              "top_imbalance_mean": float(np.nanmean(imbalance)),
              "quote_update_count": int(len(chunk))}
    values["spread_valid"] = int(all(np.isfinite(values[name]) for name in (
        "spread_bps_mean", "spread_bps_max", "spread_bps_std", "top_imbalance_mean")))
    return values


class BookTickerAggregator:
    def __init__(self, emit: Callable[[dict[str, object]], None]):
        self.emit = emit
        self.minute: pd.Timestamp | None = None
        self.rows: list[dict[str, object]] = []

    def add(self, message: str | Mapping[str, object]) -> bool:
        row = parse_book_ticker(message)
        if row is None:
            return False
        minute = pd.to_datetime(row["transaction_time"], unit="ms", utc=True).floor("min")
        if self.minute is not None and minute > self.minute:
            self.flush()
        if self.minute is not None and minute < self.minute:
            return False
        self.minute = minute
        self.rows.append(row)
        return True

    def flush(self) -> None:
        result = reduce_book_ticker(self.rows)
        if result is not None:
            self.emit(result)
        self.minute, self.rows = None, []


class PublicBinanceClient:
    """Small public-only HTTP client with bounded rate-limit backoff."""

    def __init__(self, base_url: str = BASE_URL,
                 opener: Callable[[urllib.request.Request], object] | None = None):
        self.base_url = base_url.rstrip("/")
        self.opener = opener or (lambda request: urllib.request.urlopen(request, timeout=15))

    def get_raw(self, path: str, parameters: Mapping[str, object]) -> tuple[int, str]:
        """(HTTP status, body text). Unauthenticated: no API key header is ever sent."""
        query = urllib.parse.urlencode(parameters)
        request = urllib.request.Request(f"{self.base_url}{path}?{query}",
                                         headers={"User-Agent": "StudyQuant-paper/1"})
        for attempt in range(3):
            try:
                with self.opener(request) as response:
                    return int(getattr(response, "status", 200)), response.read().decode("utf-8")
            except urllib.error.HTTPError as error:
                if error.code not in {418, 429} or attempt == 2:
                    raise
                time.sleep(min(60.0, float(error.headers.get("Retry-After", 1))))
        raise RuntimeError("unreachable")

    def get(self, path: str, parameters: Mapping[str, object]) -> object:
        return json.loads(self.get_raw(path, parameters)[1])


class Collector:
    def __init__(self, engine: PaperEngine, raw_root: str | Path,
                 client: PublicBinanceClient | None = None,
                 websocket_factory: Callable[..., object] | None = None,
                 futures_lookback: pd.Timedelta = pd.Timedelta(days=1)):
        self.engine = engine
        self.futures_lookback = futures_lookback     # first REST start for a futures table without a cursor
        self._probed: set[str] = set()               # endpoints probed by this process (startup probe)
        self.raw_root = Path(raw_root)
        self.client = client or PublicBinanceClient()
        self._websocket_factory = websocket_factory
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._sockets: list[object] = []
        self._socket_lock = threading.Lock()

    def _audit(self, endpoint: str, payload: object, received: pd.Timestamp) -> None:
        path = self.raw_root / f"{received.strftime('%Y-%m-%d')}.jsonl.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "at", encoding="utf-8") as handle:
            handle.write(json.dumps({"received_at": received.isoformat(),
                                     "endpoint": endpoint, "payload": payload},
                                    separators=(",", ":")) + "\n")

    def collect_once(self, now: object | None = None) -> dict[str, int]:
        """REST gap fill and non-WS datasets. Safe to call every minute."""
        received = pd.Timestamp(now or datetime.now(timezone.utc))
        self._wall_start = pd.Timestamp.now(tz="UTC")     # per-response received_at = received + elapsed wall time
        last = self.engine.store.get_meta("last_processed_minute")
        start = ((pd.Timestamp(last) + pd.Timedelta(minutes=1)) if last else
                 received.floor("min") - pd.Timedelta(minutes=5))
        payload = self.client.get("/fapi/v1/klines", {
            "symbol": "BTCUSDT", "interval": "1m", "startTime": _utc_ms(start), "limit": 1_000})
        self._audit("klines", payload, received)
        rows = [parse_kline(row) for row in payload]
        closed = [row for row in rows if row["open_time"] + pd.Timedelta(minutes=1) <= received]
        inserted = sum(self.engine.process_closed_minute(
            row, received_at=received, source="rest") for row in closed)

        # Premium keeps its own cursor: the kline cursor is advanced by the WebSocket first,
        # so starting from it would only ever ask for the still-open minute.
        premium_cursor = self.engine.store.get_meta("last_premium_minute")
        premium_start = ((pd.Timestamp(premium_cursor) + pd.Timedelta(minutes=1)) if premium_cursor
                         else start)
        premium = self.client.get("/fapi/v1/premiumIndexKlines", {
            "symbol": "BTCUSDT", "interval": "1m", "startTime": _utc_ms(premium_start),
            "limit": 1_000})
        self._audit("premiumIndexKlines", premium, received)
        premium_count = 0
        for row in premium:
            stamp = pd.to_datetime(int(row[0]), unit="ms", utc=True)
            if stamp + pd.Timedelta(minutes=1) <= received:
                self.engine.store.upsert("premium_1m", {
                    "open_time": stamp.isoformat(), "premium_index": float(row[4]),
                    "source": "rest", "received_at": received.isoformat()})
                self.engine.store.set_meta("last_premium_minute", stamp.isoformat())
                premium_count += 1

        futures = self._collect_futures(received)

        stored_funding = self.engine.store.frame("funding")
        # resume after the last raw event time (legacy rows keep a rounded `time`; raw_calc_time is actual)
        funding_start = (pd.to_datetime(stored_funding.raw_calc_time, utc=True, format="mixed").max() +
                         pd.Timedelta(milliseconds=1) if len(stored_funding) else
                         received - pd.Timedelta(hours=9))
        funding = self.client.get("/fapi/v1/fundingRate", {
            "symbol": "BTCUSDT", "startTime": _utc_ms(funding_start), "limit": 1_000})
        self._audit("fundingRate", funding, received)
        interval = self._funding_interval() if funding else None
        funding_count = 0
        for row in funding:
            raw = pd.to_datetime(int(row["fundingTime"]), unit="ms", utc=True)
            # fundingInfo gives the interval in force now: it belongs to the current event only
            hours = interval if interval and raw + pd.Timedelta(hours=interval) > received else None
            self.engine.store_funding(raw, float(row["fundingRate"]), raw_calc_time=raw,
                                      source="rest", received_at=received, interval_hours=hours)
            funding_count += 1
        return {"klines": inserted, "premium": premium_count, **futures, "funding": funding_count}

    def _fetch(self, path: str, parameters: Mapping[str, object]) -> tuple[int | None, object]:
        """Public GET; the raw response is persisted before any parsing. Returns (status, parsed | None)."""
        request_utc = pd.Timestamp.now(tz="UTC")
        get_raw = getattr(self.client, "get_raw", None)
        try:
            if get_raw is not None:
                status, text = get_raw(path, parameters)
            else:                                     # offline/test clients that only expose get()
                status, text = 200, json.dumps(self.client.get(path, parameters), separators=(",", ":"))
        except urllib.error.HTTPError as error:
            body = error.read() if error.fp is not None else b""
            status, text = error.code, (body or b"").decode("utf-8", "replace")
        except Exception as error:
            status, text = None, self._safe_error(error)
        self.last_response_utc = pd.Timestamp.now(tz="UTC")
        self.engine.store.connection.execute(
            "INSERT INTO futures_raw_audit(endpoint,params,request_utc,response_utc,status,sha256,payload) "
            "VALUES(?,?,?,?,?,?,?)",
            (path, json.dumps(dict(parameters), sort_keys=True), request_utc.isoformat(),
             self.last_response_utc.isoformat(), status, hashlib.sha256(text.encode()).hexdigest(), text))
        if status != 200:
            return status, None
        try:
            return status, json.loads(text)
        except ValueError:
            return status, fm.SchemaDrift("invalid JSON")

    def _funding_interval(self) -> float | None:
        _, payload = self._fetch("/fapi/v1/fundingInfo", {})
        if not isinstance(payload, list):
            return None
        row = next((r for r in payload if isinstance(r, Mapping) and r.get("symbol") == "BTCUSDT"), None)
        try:
            hours = float(row["fundingIntervalHours"]) if row else None
        except (KeyError, TypeError, ValueError):
            return None
        return hours if hours and hours > 0 else None

    def _collect_futures(self, received: pd.Timestamp) -> dict[str, int]:
        """Four /futures/data endpoints (period=5m, limit 500, bounded startTime/endTime paging, no API key).
        Fail closed per endpoint on 401/403, schema drift or empty finalized coverage: nothing is stored for it
        (missing rows = mask) and 401/403/drift wait for the periodic capability probe; no auth fallback."""
        store = self.engine.store
        capability = json.loads(store.get_meta("futures_capability") or "{}")
        counts: dict[str, int] = {}
        for endpoint, (table, shift, _) in fm.REST_SPECS.items():
            legacy = endpoint == "/futures/data/globalLongShortAccountRatio"
            counts[table] = 0
            if legacy:
                counts["ls_ratio"] = 0
            state = capability.get(endpoint, {})
            if (endpoint in self._probed and state.get("status") in {"HTTP_401", "HTTP_403", "SCHEMA_DRIFT"}
                    and received - pd.Timestamp(state["checked_at"]) < fm.PROBE_INTERVAL):
                continue
            self._probed.add(endpoint)
            # the global cursor stays the legacy one so ls_ratio keeps its paging semantics
            cursor_key = "last_ls_timestamp" if legacy else f"last_{table}_timestamp"
            cursor = store.get_meta(cursor_key)
            page_start = (pd.Timestamp(cursor) + pd.Timedelta(milliseconds=1) if cursor else
                          (received - self.futures_lookback).floor("5min"))
            payloads, status = [], "OK"
            for _ in range(fm.MAX_PAGES):
                if page_start >= received:
                    break
                page_end = min(page_start + fm.PERIOD * 500, received)
                code, payload = self._fetch(endpoint, {
                    "symbol": "BTCUSDT", "period": "5m", "startTime": _utc_ms(page_start),
                    "endTime": _utc_ms(page_end), "limit": 500})
                if code in {401, 403}:
                    status = f"HTTP_{code}"
                elif code != 200:
                    status = f"ERROR_{code}"
                elif isinstance(payload, fm.SchemaDrift):
                    status = "SCHEMA_DRIFT"
                if status != "OK":
                    break
                payloads.append((payload, received + (self.last_response_utc - self._wall_start)))
                page_start = page_end + pd.Timedelta(milliseconds=1)
            rows: list[dict[str, object]] = []
            if status == "OK":
                try:
                    for payload, page_received in payloads:
                        rows.extend(fm.normalize_rest(endpoint, payload, page_received)[1])
                except fm.SchemaDrift:
                    status, rows = "SCHEMA_DRIFT", []
            if status == "OK":
                # the API rounds startTime down to the period, so the cursor row comes back: count new rows only
                with store.transaction() as connection:
                    new = [row for row in rows if store.put_versioned(table, row, connection) == "inserted"]
                counts[table] = len(new)
                if rows:
                    store.set_meta(cursor_key, max(pd.Timestamp(r["source_timestamp"]) for r in rows).isoformat())
                if legacy:
                    for row in new:
                        # legacy ls_ratio keeps the REST end/availability label (catalog/detector until Task 2/3)
                        store.upsert("ls_ratio", {
                            "timestamp": row["source_timestamp"], "global_ls_account": row["long_short_ratio"],
                            "long_account": row["long_account"], "short_account": row["short_account"],
                            "source": "rest", "received_at": row["received_at"]})
                    counts["ls_ratio"] = len(new)
                latest = store.get_meta(cursor_key)
                newest_final = received.floor("5min") - fm.PERIOD + shift    # REST stamp of the last closed period
                if latest is None or pd.Timestamp(latest) < newest_final - 2 * fm.PERIOD:
                    status = "EMPTY"            # no finalized coverage for the latest periods
            capability[endpoint] = {"status": status, "checked_at": received.isoformat(), "rows": counts[table]}
            if status != "OK":
                LOG.warning("futures metrics %s fail closed: %s", endpoint, status)
        store.set_meta("futures_capability", json.dumps(capability, sort_keys=True))
        return counts

    def on_ws_message(self, message: str | Mapping[str, object],
                      received_at: object | None = None) -> bool:
        row = parse_ws_kline(message)
        if row is None:
            return False
        return self.engine.process_closed_minute(
            row, received_at=received_at or datetime.now(timezone.utc), source="ws")

    def start_streams(self) -> None:
        if self._threads:
            return
        targets = [("paper-kline-ws", self._kline_ws_loop)]
        if self.engine.config.book_ticker_enabled:
            targets.append(("paper-book-ws", self._book_ws_loop))
        for name, target in targets:
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)

    def _connect(self, url: str) -> object:
        if self._websocket_factory is not None:
            return self._websocket_factory(url, timeout=30)
        import websocket
        return websocket.create_connection(url, timeout=30, enable_multithread=True)

    @staticmethod
    def _safe_error(error: BaseException) -> str:
        message = re.sub(r"https?://\S+", "<url>", str(error).replace("\n", " "))[:160]
        return f"ERROR:{type(error).__name__}:{message}" if message else f"ERROR:{type(error).__name__}"

    def _record_ws_error(self, store: PaperStore, source: str,
                         error: BaseException, retries: int) -> None:
        now = pd.Timestamp.now(tz="UTC")
        status = self._safe_error(error)
        store.upsert("collector_health", {"minute": now.floor("min").isoformat(),
                     "source": source, "lag_ms": None, "gaps": 0,
                     "retries": retries, "status": status})
        LOG.warning("%s", status)

    def _remember_socket(self, socket: object) -> None:
        with self._socket_lock:
            self._sockets.append(socket)

    def _forget_socket(self, socket: object) -> None:
        with self._socket_lock:
            if socket in self._sockets:
                self._sockets.remove(socket)

    def _kline_ws_loop(self) -> None:
        retries = 0
        with PaperStore(self.engine.store.path) as store:
            engine = PaperEngine(store, self.engine.config)
            while not self._stop.is_set():
                socket = None
                try:
                    socket = self._connect(KLINE_WS_URL)
                    self._remember_socket(socket)
                    retries = 0
                    connected = time.monotonic()
                    forming_written = 0.0
                    while not self._stop.is_set() and time.monotonic() - connected < 23 * 3600 + 50 * 60:
                        payload = json.loads(socket.recv())
                        forming = parse_ws_forming(payload)
                        if forming is not None and time.monotonic() - forming_written >= 1.0:
                            store.set_meta("forming_kline", json.dumps(forming))
                            forming_written = time.monotonic()
                        row = parse_ws_kline(payload)
                        if row is not None and engine.process_closed_minute(
                                row, received_at=datetime.now(timezone.utc), source="ws"):
                            store.set_meta("ws_closed_events", int(store.get_meta("ws_closed_events") or 0) + 1)
                            store.set_meta("last_ws_closed_at", pd.Timestamp.now(tz="UTC").isoformat())
                except Exception as error:
                    if not self._stop.is_set():
                        retries += 1
                        self._record_ws_error(store, "ws_kline_error", error, retries)
                finally:
                    if socket is not None:
                        self._forget_socket(socket)
                        try:
                            socket.close()
                        except Exception:
                            pass
                self._stop.wait(min(self.engine.config.websocket_reconnect_max_seconds,
                                    2 ** min(retries, 6)))

    def _book_ws_loop(self) -> None:
        retries = 0
        with PaperStore(self.engine.store.path) as store:
            previous_text = store.connection.execute(
                "SELECT MAX(minute) FROM book_ticker_1m").fetchone()[0]

            def emit(values: dict[str, object]) -> None:
                nonlocal previous_text
                received = pd.Timestamp.now(tz="UTC")
                minute = pd.Timestamp(values.pop("minute"))
                gap = 0 if previous_text is None else max(
                    0, int((minute - pd.Timestamp(previous_text)) / pd.Timedelta(minutes=1)) - 1)
                store.upsert("book_ticker_1m", {**values, "minute": minute.isoformat(),
                             "source": "ws", "received_at": received.isoformat()})
                store.upsert("collector_health", {"minute": minute.isoformat(),
                             "source": "book_ticker", "lag_ms": max(0.0, (
                                 received - minute - pd.Timedelta(minutes=1)).total_seconds() * 1000),
                             "gaps": gap, "retries": retries, "status": "GAP" if gap else "OK"})
                previous_text = minute.isoformat()

            aggregator = BookTickerAggregator(emit)
            while not self._stop.is_set():
                socket = None
                try:
                    socket = self._connect(BOOK_WS_URL)
                    self._remember_socket(socket)
                    retries = 0
                    connected = time.monotonic()
                    while not self._stop.is_set() and time.monotonic() - connected < 23 * 3600 + 50 * 60:
                        message = socket.recv()
                        if aggregator.add(message) and self.engine.config.book_ticker_raw_ticks:
                            self._audit("bookTicker", json.loads(message), pd.Timestamp.now(tz="UTC"))
                except Exception as error:
                    if not self._stop.is_set():
                        retries += 1
                        self._record_ws_error(store, "ws_book_error", error, retries)
                finally:
                    if socket is not None:
                        self._forget_socket(socket)
                        try:
                            socket.close()
                        except Exception:
                            pass
                self._stop.wait(min(self.engine.config.websocket_reconnect_max_seconds,
                                    2 ** min(retries, 6)))
            if aggregator.minute is not None and aggregator.minute < pd.Timestamp.now(tz="UTC").floor("min"):
                aggregator.flush()

    def close(self) -> None:
        self._stop.set()
        with self._socket_lock:
            sockets = list(self._sockets)
        for socket in sockets:
            try:
                socket.close()
            except Exception:
                pass
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()


__all__ = ["BOOK_WS_URL", "KLINE_WS_URL", "BookTickerAggregator", "Collector",
           "PublicBinanceClient", "parse_book_ticker", "parse_kline", "parse_ws_kline",
           "reduce_book_ticker"]
