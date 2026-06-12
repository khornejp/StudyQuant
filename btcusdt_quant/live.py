from __future__ import annotations

import json
import queue
import threading
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Mapping, Sequence

from . import data, dataset


class RateLimitError(RuntimeError):
    pass


class RateLimitBackoffActive(RateLimitError):
    pass


class RateLimitHardBanActive(RateLimitError):
    pass


class RateLimitBudgetExceeded(RateLimitError):
    pass


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float, clock=monotonic) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.clock = clock
        self.tokens = capacity
        self.updated_at = clock()

    def refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now

    def consume(self, weight: float) -> bool:
        self.refill()
        if weight > self.tokens:
            return False
        self.tokens -= weight
        return True


class RateLimitManager:
    def __init__(self, limit_per_minute: int = 2400, emergency_reserved_ratio: float = 0.20, clock=monotonic) -> None:
        normal_capacity = limit_per_minute * (1.0 - emergency_reserved_ratio)
        emergency_capacity = limit_per_minute * emergency_reserved_ratio
        self.normal_bucket = TokenBucket(normal_capacity, normal_capacity / 60.0, clock)
        self.emergency_bucket = TokenBucket(emergency_capacity, emergency_capacity / 60.0, clock)
        self.backoff_active = False
        self.hard_ban_active = False

    def acquire(self, endpoint: str, weight: int) -> None:
        if self.hard_ban_active:
            raise RateLimitHardBanActive(endpoint)
        if self.backoff_active:
            raise RateLimitBackoffActive(endpoint)
        if not self.normal_bucket.consume(weight):
            raise RateLimitBudgetExceeded(endpoint)

    def acquire_emergency(self, endpoint: str, weight: int) -> None:
        if self.hard_ban_active:
            raise RateLimitHardBanActive(endpoint)
        if not self.emergency_bucket.consume(weight):
            raise RateLimitBudgetExceeded(endpoint)

    def observe_status(self, status_code: int) -> str:
        if status_code == 418:
            self.hard_ban_active = True
            return "hard_kill"
        if status_code == 429:
            self.backoff_active = True
            return "block_new_entries"
        return "allow"


@dataclass(frozen=True)
class PositionState:
    symbol: str
    quantity: float = 0.0


class OneWayPositionGuard:
    def can_enter(self, state: PositionState, signal_side: str) -> tuple[bool, str]:
        if state.quantity != 0.0:
            return False, "position_qty != 0 blocks new entry in one-way mode"
        if signal_side not in {"BUY", "SELL"}:
            return False, "invalid signal side"
        return True, "flat position allows entry"


@dataclass(frozen=True)
class SizingResult:
    quantity: float
    notional: float
    required_margin: float
    accepted: bool
    reason: str


class PositionSizer:
    def fixed_notional(
        self,
        entry_price: float,
        account_balance_usdt: float,
        trade_notional_ratio: float,
        leverage: float,
        min_qty: float,
        qty_step: float,
        max_notional_fraction: float,
    ) -> SizingResult:
        if entry_price <= 0 or account_balance_usdt <= 0 or leverage <= 0 or qty_step <= 0:
            return SizingResult(0.0, 0.0, 0.0, False, "invalid sizing input")
        notional = account_balance_usdt * trade_notional_ratio
        max_notional = account_balance_usdt * max_notional_fraction
        if notional > max_notional:
            return SizingResult(0.0, notional, notional / leverage, False, "max_notional_fraction breached")
        raw_qty = notional / entry_price
        quantity = floor(raw_qty / qty_step) * qty_step
        if quantity < min_qty:
            return SizingResult(quantity, notional, notional / leverage, False, "below_min_qty")
        return SizingResult(quantity, notional, notional / leverage, True, "accepted")


@dataclass(frozen=True)
class MockOrder:
    order_id: int
    symbol: str
    side: str
    order_type: str
    quantity: float
    status: str
    reduce_only: bool


class MockExchangeAdapter:
    """Deterministic exchange adapter; never performs network I/O."""

    def __init__(self) -> None:
        self.orders: list[MockOrder] = []
        self.network_enabled = False

    def submit_order(self, symbol: str, side: str, order_type: str, quantity: float, reduce_only: bool = False) -> MockOrder:
        if self.network_enabled:
            raise RuntimeError("live network access is forbidden in local scaffold")
        if symbol != "BTCUSDT":
            raise ValueError("only BTCUSDT fixture is supported")
        if side not in {"BUY", "SELL"}:
            raise ValueError("invalid side")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        order = MockOrder(999_999_000 + len(self.orders), symbol, side, order_type, quantity, "MOCK_ACCEPTED", reduce_only)
        self.orders.append(order)
        return order


@dataclass(frozen=True)
class FundingEvent:
    funding_time: datetime
    funding_rate: float


class FundingEventManager:
    def funding_pnl(self, side: str, position_notional: float, entry_time: datetime, exit_time: datetime, events: Sequence[FundingEvent]) -> float:
        pnl = 0.0
        for event in events:
            if entry_time < event.funding_time <= exit_time:
                if side == "LONG":
                    pnl -= position_notional * event.funding_rate
                elif side == "SHORT":
                    pnl += position_notional * event.funding_rate
                else:
                    raise ValueError("side must be LONG or SHORT")
        return pnl

    def blackout_active(self, minutes_to_next_funding: int, blackout_min: int = 5) -> bool:
        return 0 <= minutes_to_next_funding <= blackout_min


class GhostFillPrevention:
    def safe_market_exit(self, active_exit_orders: int, position_qty: float, cancel_resolved: bool) -> str:
        if active_exit_orders > 0 and not cancel_resolved:
            return "hard_kill"
        if position_qty == 0.0:
            return "no_market_exit_needed"
        return "market_exit_submitted"


class EmergencyCloseExecutor:
    def close(self, priority: int, retries: int, max_retries: int = 2) -> str:
        if priority != 0:
            return "queued"
        if retries > max_retries:
            return "hard_kill"
        return "emergency_close_submitted"


@dataclass(frozen=True)
class GapDetection:
    stream_desync_detected: bool
    missing_open_times: list[datetime]
    anomaly: str | None
    consecutive_missing: int
    expected_next_open_time: datetime | None


@dataclass(frozen=True)
class LiveRunResult:
    output: Path
    summary: dict[str, object]
    canonical: list[data.Candle]
    feature_rows: list[dataset.FeatureRow]


class StreamGapDetector:
    def __init__(self, cadence: timedelta = timedelta(minutes=1), desync_threshold: int = 3) -> None:
        self.cadence = cadence
        self.desync_threshold = desync_threshold
        self.last_seen_open_time: datetime | None = None
        self.expected_next_open_time: datetime | None = None
        self.consecutive_missing = 0

    def observe(self, candle: data.Candle) -> GapDetection:
        missing: list[datetime] = []
        anomaly: str | None = None
        if self.expected_next_open_time is not None and candle.open_time > self.expected_next_open_time:
            current = self.expected_next_open_time
            while current < candle.open_time:
                missing.append(current)
                current += self.cadence
            self.consecutive_missing = len(missing)
            if self.consecutive_missing >= self.desync_threshold:
                anomaly = "stream_desync"
            elif self.consecutive_missing > 1:
                anomaly = "gap_cross_timeout"
        elif self.expected_next_open_time is not None and candle.open_time == self.expected_next_open_time:
            self.consecutive_missing = 0

        if self.last_seen_open_time is None or candle.open_time >= self.last_seen_open_time:
            self.last_seen_open_time = candle.open_time
            self.expected_next_open_time = candle.open_time + self.cadence
        return GapDetection(bool(missing), missing, anomaly, self.consecutive_missing, self.expected_next_open_time)

    def check_timeout(self, now: datetime) -> GapDetection:
        if self.expected_next_open_time is None or now < self.expected_next_open_time + self.cadence:
            return GapDetection(False, [], None, self.consecutive_missing, self.expected_next_open_time)
        missing: list[datetime] = []
        current = self.expected_next_open_time
        while current + self.cadence <= now:
            missing.append(current)
            current += self.cadence
        self.consecutive_missing = len(missing)
        anomaly = None
        if self.consecutive_missing >= self.desync_threshold:
            anomaly = "stream_desync"
        elif self.consecutive_missing > 1:
            anomaly = "gap_cross_timeout"
        return GapDetection(True, missing, anomaly, self.consecutive_missing, self.expected_next_open_time)


class WebSocketClient:
    ENDPOINT = "wss://fstream.binance.com/ws/btcusdt@kline_1m"

    def __init__(self, buffer_size: int = 500, allow_network: bool = False, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or self.ENDPOINT
        self.allow_network = allow_network
        self._messages: queue.Queue[str] = queue.Queue()
        self._buffer: deque[data.Candle] = deque(maxlen=buffer_size)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws_app: Any | None = None
        self.errors: list[str] = []

    def start(self) -> None:
        if not self.allow_network:
            raise RuntimeError("WebSocket streaming requires explicit allow_network=True")
        try:
            import websocket  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("websocket-client is not installed; use live --dry-run or install websocket-client") from error
        self._stop_event.clear()
        self._ws_app = websocket.WebSocketApp(
            self.endpoint,
            on_message=lambda _ws, message: self._messages.put(str(message)),
            on_error=lambda _ws, error: self.errors.append(str(error)),
            on_close=lambda _ws, _code, _message: self._stop_event.set(),
        )
        self._thread = threading.Thread(target=self._ws_app.run_forever, name="btcusdt-kline-websocket", daemon=True)
        self._thread.start()

    def next_candle(self, timeout: float | None = None) -> data.Candle | None:
        try:
            message = self._messages.get(timeout=timeout)
        except queue.Empty:
            return None
        candle = self.parse_message(message)
        if candle is not None:
            self.add_candle(candle)
        return candle

    def add_candle(self, candle: data.Candle) -> None:
        with self._lock:
            by_time = {existing.open_time: existing for existing in self._buffer}
            by_time[candle.open_time] = candle
            ordered = sorted(by_time.values(), key=lambda row: row.open_time)
            self._buffer.clear()
            for row in ordered[-self._buffer.maxlen :]:
                self._buffer.append(row)

    def buffer_snapshot(self) -> list[data.Candle]:
        with self._lock:
            return list(self._buffer)

    def flush_buffer(self) -> list[data.Candle]:
        with self._lock:
            rows = list(self._buffer)
            self._buffer.clear()
            return rows

    def close(self) -> None:
        self._stop_event.set()
        ws_app = self._ws_app
        if ws_app is not None:
            close = getattr(ws_app, "close", None)
            if callable(close):
                close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    stop = close

    @staticmethod
    def parse_message(message: str | bytes | Mapping[str, Any]) -> data.Candle | None:
        payload: Any
        if isinstance(message, bytes):
            payload = json.loads(message.decode("utf-8"))
        elif isinstance(message, str):
            payload = json.loads(message)
        else:
            payload = message
        if not isinstance(payload, Mapping):
            return None
        kline = payload.get("k", payload)
        if not isinstance(kline, Mapping) or not bool(kline.get("x", True)):
            return None
        return data.Candle(
            open_time=_datetime_from_millis(kline["t"]),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            quote_volume=float(kline.get("q", 0.0)),
            number_of_trades=int(float(kline.get("n", 0))),
            taker_buy_base_volume=float(kline.get("V", 0.0)),
            taker_buy_quote_volume=float(kline.get("Q", 0.0)),
        )


class MockWebSocketClient(WebSocketClient):
    def __init__(self, fixture_candles: Sequence[data.Candle] | None = None, buffer_size: int = 500, interval_seconds: float = 0.0) -> None:
        super().__init__(buffer_size=buffer_size, allow_network=False)
        self.fixture_candles = list(fixture_candles) if fixture_candles is not None else _live_fixture(12)
        self.interval_seconds = interval_seconds
        self._finished = threading.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._finished.clear()
        self._thread = threading.Thread(target=self._feed_fixture, name="btcusdt-mock-websocket", daemon=True)
        self._thread.start()

    def _feed_fixture(self) -> None:
        try:
            for candle in self.fixture_candles:
                if self._stop_event.is_set():
                    break
                self._messages.put(json.dumps(_kline_message(candle)))
                if self.interval_seconds > 0.0:
                    self._stop_event.wait(self.interval_seconds)
        finally:
            self._finished.set()

    def is_finished(self) -> bool:
        return self._finished.is_set() and self._messages.empty()

    def close(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._finished.set()


class RESTBackfill:
    def __init__(
        self,
        allow_network: bool = False,
        fetcher: Callable[[Sequence[datetime]], Sequence[data.Candle]] | None = None,
        base_url: str = "https://fapi.binance.com",
        timeout_seconds: int = 10,
    ) -> None:
        self.allow_network = allow_network
        self.fetcher = fetcher
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.events: list[dict[str, object]] = []

    def backfill_missing(self, missing_open_times: Sequence[datetime]) -> list[data.Candle]:
        if not missing_open_times:
            return []
        requested = sorted(missing_open_times)
        if self.fetcher is not None:
            fetched = list(self.fetcher(requested))
        else:
            fetched = self._fetch_public_klines(requested)
        by_time = {candle.open_time: candle for candle in fetched}
        repaired = [self._mark_repaired(by_time[open_time]) for open_time in requested if open_time in by_time]
        self.events.append(
            {
                "event": "rest_backfill",
                "requested": len(requested),
                "filled": len(repaired),
                "first_open_time": requested[0].isoformat(),
                "last_open_time": requested[-1].isoformat(),
            }
        )
        return repaired

    def _fetch_public_klines(self, open_times: Sequence[datetime]) -> list[data.Candle]:
        if not self.allow_network:
            raise RuntimeError("REST backfill requires explicit allow_network=True")
        start = min(open_times)
        end = max(open_times)
        query = urllib.parse.urlencode(
            {
                "symbol": "BTCUSDT",
                "interval": "1m",
                "startTime": _millis_from_datetime(start),
                "endTime": _millis_from_datetime(end + timedelta(minutes=1) - timedelta(milliseconds=1)),
                "limit": min(1500, len(open_times) + 2),
            }
        )
        request = urllib.request.Request(f"{self.base_url}/fapi/v1/klines?{query}", headers={"User-Agent": "btcusdt-quant-live-backfill/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("unexpected kline response payload")
        wanted = set(open_times)
        return [candle for candle in (dataset.candle_from_kline_row(row) for row in payload) if candle.open_time in wanted]

    @staticmethod
    def _mark_repaired(candle: data.Candle) -> data.Candle:
        return replace(candle, repaired=True, gap_flag=1)


def run_live(
    output: Path,
    dry_run: bool = True,
    allow_public_network: bool = False,
    max_candles: int = 12,
    idle_timeout_seconds: float = 0.2,
) -> LiveRunResult:
    if not dry_run and not allow_public_network:
        raise RuntimeError("live mode without --dry-run requires --allow-public-network")
    fixture = _live_fixture(max(max_candles + 4, 12))
    if dry_run:
        omitted = {5, 6, 9}
        stream_fixture = [candle for index, candle in enumerate(fixture[:max_candles]) if index not in omitted]
        client: WebSocketClient = MockWebSocketClient(stream_fixture)
        fixture_by_time = {candle.open_time: candle for candle in fixture}
        backfill = RESTBackfill(fetcher=lambda open_times: [fixture_by_time[open_time] for open_time in open_times if open_time in fixture_by_time])
    else:
        client = WebSocketClient(allow_network=True)
        backfill = RESTBackfill(allow_network=True)

    detector = StreamGapDetector()
    anomalies: list[str] = []
    desync_events = 0
    client.start()
    try:
        processed = 0
        while processed < max_candles:
            candle = client.next_candle(timeout=idle_timeout_seconds)
            if candle is None:
                if isinstance(client, MockWebSocketClient) and client.is_finished():
                    break
                timeout_detection = detector.check_timeout(datetime.now(timezone.utc))
                if timeout_detection.stream_desync_detected:
                    desync_events += 1
                if timeout_detection.stream_desync_detected and timeout_detection.anomaly is not None:
                    anomalies.append(timeout_detection.anomaly)
                continue
            detection = detector.observe(candle)
            if detection.stream_desync_detected:
                desync_events += 1
                if detection.anomaly is not None:
                    anomalies.append(detection.anomaly)
                for repaired in backfill.backfill_missing(detection.missing_open_times):
                    client.add_candle(repaired)
            processed += 1
    finally:
        client.close()

    canonical = data.CanonicalTimelineBuilder().build(client.buffer_snapshot())
    feature_rows = dataset.build_feature_rows(canonical)
    last_return = data.returns(canonical)[-1] if canonical else 0.0
    signal = "BUY" if last_return > 0 else "SELL" if last_return < 0 else "HOLD"
    output.mkdir(parents=True, exist_ok=True)
    dataset.write_candles_csv(output / "live_candles.csv", canonical)
    summary: dict[str, object] = {
        "dry_run": dry_run,
        "network_used": not dry_run,
        "stream_desync_detected": desync_events > 0,
        "anomalies": anomalies,
        "backfilled_rows": sum(event["filled"] for event in backfill.events),
        "canonical_rows": len(canonical),
        "feature_rows": len(feature_rows),
        "signal": signal,
        "output": output.as_posix(),
    }
    (output / "live_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return LiveRunResult(output, summary, canonical, feature_rows)


def _live_fixture(rows: int) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 1, 0, 0)
    candles: list[data.Candle] = []
    previous_close = 100000.0
    for index in range(rows):
        open_price = previous_close
        close = 100000.0 + index * 7.5 + (index % 3) * 2.0
        high = max(open_price, close) + 10.0
        low = min(open_price, close) - 10.0
        volume = 10.0 + index
        candles.append(
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=round(open_price, 8),
                high=round(high, 8),
                low=round(low, 8),
                close=round(close, 8),
                volume=round(volume, 8),
                quote_volume=round(volume * close, 8),
                number_of_trades=100 + index,
                taker_buy_base_volume=round(volume * 0.5, 8),
                taker_buy_quote_volume=round(volume * close * 0.5, 8),
            )
        )
        previous_close = close
    return candles


def _kline_message(candle: data.Candle) -> dict[str, object]:
    return {
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": _millis_from_datetime(candle.open_time),
            "s": "BTCUSDT",
            "i": "1m",
            "o": str(candle.open),
            "h": str(candle.high),
            "l": str(candle.low),
            "c": str(candle.close),
            "v": str(candle.volume),
            "n": candle.number_of_trades,
            "x": True,
            "q": str(candle.quote_volume),
            "V": str(candle.taker_buy_base_volume),
            "Q": str(candle.taker_buy_quote_volume),
        },
    }


def _datetime_from_millis(value: object) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)


def _millis_from_datetime(value: datetime) -> int:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return int(aware.astimezone(timezone.utc).timestamp() * 1000)
