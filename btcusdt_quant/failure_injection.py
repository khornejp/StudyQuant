from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping, Sequence

from . import data, governance


class ExchangeFault(str, Enum):
    HTTP_429 = "HTTP_429"
    HTTP_418 = "HTTP_418"
    HTTP_503 = "HTTP_503"
    TIMEOUT = "TIMEOUT"
    ORDER_UNKNOWN = "ORDER_UNKNOWN"
    LISTENKEY_EXPIRED = "LISTENKEY_EXPIRED"


class WebSocketFault(str, Enum):
    DISCONNECT = "DISCONNECT"
    DUPLICATE_CANDLE = "DUPLICATE_CANDLE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    GAP_STORM = "GAP_STORM"


class ScriptExhaustedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScriptedHttpResponse:
    status_code: int
    payload: object | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    reason: str = ""

    def json(self) -> object | None:
        return self.payload


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    retry_statuses: tuple[int, ...] = (429, 503)
    retry_after_cap_seconds: float = 60.0
    exponential_backoff_base_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.retry_after_cap_seconds <= 0.0:
            raise ValueError("retry_after_cap_seconds must be positive")
        if self.exponential_backoff_base_seconds <= 0.0:
            raise ValueError("exponential_backoff_base_seconds must be positive")


@dataclass(frozen=True)
class ScriptedHttpResult:
    response: ScriptedHttpResponse | None
    error: BaseException | None
    attempts: int
    capped: bool
    scheduled_backoffs: tuple[float, ...]


@dataclass(frozen=True)
class ScriptedWebSocketEvent:
    event_type: str
    candle: data.Candle | None = None
    fault: ExchangeFault | WebSocketFault | None = None
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FailureScenario:
    name: str
    fault: ExchangeFault | WebSocketFault
    expected_action: str
    http_script: tuple[ScriptedHttpResponse | BaseException, ...] = ()
    websocket_script: tuple[ScriptedWebSocketEvent, ...] = ()
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    fallback_metric: str | None = None
    fallback_value: float | bool | int = True
    description: str = ""


class ScriptedHttpTransport:
    """Deterministic HTTP transport backed by an in-memory script."""

    def __init__(self, script: Sequence[ScriptedHttpResponse | BaseException]) -> None:
        self._script: deque[ScriptedHttpResponse | BaseException] = deque(script)
        self.calls: list[dict[str, object]] = []
        self.scheduled_backoffs: list[float] = []

    @property
    def remaining(self) -> int:
        return len(self._script)

    def request(self, method: str, endpoint: str, payload: Mapping[str, object] | None = None, weight: int = 1) -> ScriptedHttpResponse:
        if not self._script:
            raise ScriptExhaustedError(f"no scripted HTTP response for {method} {endpoint}")
        self.calls.append({"method": method, "endpoint": endpoint, "payload": dict(payload or {}), "weight": weight})
        next_item = self._script.popleft()
        if isinstance(next_item, BaseException):
            raise next_item
        return next_item

    def request_with_retries(
        self,
        method: str,
        endpoint: str,
        retry_policy: RetryPolicy | None = None,
        payload: Mapping[str, object] | None = None,
        weight: int = 1,
    ) -> ScriptedHttpResult:
        policy = retry_policy or RetryPolicy()
        last_response: ScriptedHttpResponse | None = None
        last_error: BaseException | None = None
        attempts = 0

        for attempt in range(1, policy.max_attempts + 1):
            attempts = attempt
            try:
                response = self.request(method, endpoint, payload, weight)
            except TimeoutError as error:
                last_error = error
                if attempt >= policy.max_attempts:
                    break
                self.scheduled_backoffs.append(self._exponential_backoff(attempt, policy))
                continue
            except ScriptExhaustedError as error:
                last_error = error
                break

            last_response = response
            if response.status_code not in policy.retry_statuses:
                return ScriptedHttpResult(response, None, attempts, False, tuple(self.scheduled_backoffs))
            if attempt >= policy.max_attempts:
                break
            self.scheduled_backoffs.append(self._response_backoff(response, attempt, policy))

        return ScriptedHttpResult(last_response, last_error, attempts, True, tuple(self.scheduled_backoffs))

    @staticmethod
    def _response_backoff(response: ScriptedHttpResponse, attempt: int, policy: RetryPolicy) -> float:
        retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), policy.retry_after_cap_seconds)
            except ValueError:
                return policy.retry_after_cap_seconds
        return ScriptedHttpTransport._exponential_backoff(attempt, policy)

    @staticmethod
    def _exponential_backoff(attempt: int, policy: RetryPolicy) -> float:
        return min(policy.exponential_backoff_base_seconds * (2 ** max(0, attempt - 1)), policy.retry_after_cap_seconds)


class ScriptedWebSocketTransport:
    """Deterministic WebSocket event source; it never opens a socket."""

    def __init__(self, script: Sequence[ScriptedWebSocketEvent]) -> None:
        self._script: deque[ScriptedWebSocketEvent] = deque(script)
        self.events_seen: list[ScriptedWebSocketEvent] = []
        self.started = False
        self.closed = False

    @property
    def remaining(self) -> int:
        return len(self._script)

    def start(self) -> None:
        self.started = True
        self.closed = False

    def next_event(self) -> ScriptedWebSocketEvent | None:
        if self.closed or not self._script:
            return None
        event = self._script.popleft()
        self.events_seen.append(event)
        if event.event_type == "disconnect":
            self.closed = True
        return event

    def next_candle(self) -> data.Candle | None:
        while True:
            event = self.next_event()
            if event is None:
                return None
            if event.event_type == "candle":
                return event.candle
            if event.event_type in {"drop", "disconnect", "listen_key_expired"}:
                return None

    def drain(self) -> list[ScriptedWebSocketEvent]:
        events: list[ScriptedWebSocketEvent] = []
        while True:
            event = self.next_event()
            if event is None:
                return events
            events.append(event)

    def close(self) -> None:
        self.closed = True


def fallback_action_for_fault(fault: ExchangeFault | WebSocketFault) -> str:
    if fault == ExchangeFault.HTTP_418:
        return governance.fallback_action("http_418_detected", True)
    if fault == ExchangeFault.HTTP_429:
        return "block_new_entries"
    if fault in {ExchangeFault.HTTP_503, ExchangeFault.TIMEOUT, ExchangeFault.LISTENKEY_EXPIRED}:
        return "block_new_entries"
    if fault == ExchangeFault.ORDER_UNKNOWN:
        return "hard_kill"
    if fault == WebSocketFault.DISCONNECT:
        return "block_new_entries"
    if fault in {WebSocketFault.DUPLICATE_CANDLE, WebSocketFault.OUT_OF_ORDER}:
        return "allow"
    if fault == WebSocketFault.GAP_STORM:
        return governance.fallback_action("max_gap_run", 3)
    return "allow"


def fallback_action_for_scenario(scenario: FailureScenario) -> str:
    if scenario.fallback_metric is not None:
        return governance.fallback_action(scenario.fallback_metric, scenario.fallback_value)
    return fallback_action_for_fault(scenario.fault)


def run_http_scenario(scenario: FailureScenario, method: str = "POST", endpoint: str = "/fapi/v1/order") -> ScriptedHttpResult:
    transport = ScriptedHttpTransport(scenario.http_script)
    return transport.request_with_retries(method, endpoint, scenario.retry_policy)


def all_scenarios() -> tuple[FailureScenario, ...]:
    return (
        http_429_retry_after_scenario(),
        http_418_hard_ban_scenario(),
        http_503_unknown_order_status_scenario(),
        timeout_after_order_submit_scenario(),
        websocket_disconnect_scenario(),
        dropped_websocket_messages_scenario(),
        duplicate_candle_scenario(),
        out_of_order_candle_scenario(),
        listenkey_expired_scenario(),
        cancel_accepted_fill_race_scenario(),
        rest_backfill_missing_candle_scenario(),
    )


def http_429_retry_after_scenario() -> FailureScenario:
    return FailureScenario(
        name="http_429_retry_after",
        fault=ExchangeFault.HTTP_429,
        expected_action="block_new_entries",
        http_script=(
            ScriptedHttpResponse(429, {"code": -1003, "msg": "rate limit"}, {"Retry-After": "2"}, "Too Many Requests"),
            ScriptedHttpResponse(429, {"code": -1003, "msg": "still rate limited"}, {"Retry-After": "120"}, "Too Many Requests"),
            ScriptedHttpResponse(429, {"code": -1003, "msg": "still rate limited"}, {"Retry-After": "120"}, "Too Many Requests"),
        ),
        retry_policy=RetryPolicy(max_attempts=3, retry_statuses=(429,), retry_after_cap_seconds=30.0),
        description="HTTP 429 schedules capped Retry-After backoff and blocks new entries.",
    )


def http_418_hard_ban_scenario() -> FailureScenario:
    return FailureScenario(
        name="http_418_hard_ban",
        fault=ExchangeFault.HTTP_418,
        expected_action="hard_kill",
        http_script=(ScriptedHttpResponse(418, {"code": -1003, "msg": "IP banned"}, {}, "I'm a teapot"),),
        retry_policy=RetryPolicy(max_attempts=1, retry_statuses=()),
        fallback_metric="http_418_detected",
        fallback_value=True,
        description="HTTP 418 hard ban is never retried.",
    )


def http_503_unknown_order_status_scenario() -> FailureScenario:
    return FailureScenario(
        name="http_503_unknown_order_status",
        fault=ExchangeFault.HTTP_503,
        expected_action="block_new_entries",
        http_script=(
            ScriptedHttpResponse(503, {"code": -1008, "msg": "execution status unknown"}, {}, "Service Unavailable"),
            ScriptedHttpResponse(503, {"code": -1008, "msg": "execution status unknown"}, {}, "Service Unavailable"),
            ScriptedHttpResponse(503, {"code": -1008, "msg": "execution status unknown"}, {}, "Service Unavailable"),
        ),
        retry_policy=RetryPolicy(max_attempts=3, retry_statuses=(503,), retry_after_cap_seconds=8.0),
        description="Unknown order status retries are capped and block new entries.",
    )


def timeout_after_order_submit_scenario() -> FailureScenario:
    return FailureScenario(
        name="timeout_after_order_submit",
        fault=ExchangeFault.TIMEOUT,
        expected_action="block_new_entries",
        http_script=(TimeoutError("timeout after order submit"), TimeoutError("timeout after order status check")),
        retry_policy=RetryPolicy(max_attempts=2, retry_statuses=(), retry_after_cap_seconds=4.0),
        description="Submit timeouts stop after capped status reconciliation attempts.",
    )


def websocket_disconnect_scenario() -> FailureScenario:
    candles = _fixture_candles(2)
    return FailureScenario(
        name="websocket_disconnect",
        fault=WebSocketFault.DISCONNECT,
        expected_action="block_new_entries",
        websocket_script=(
            ScriptedWebSocketEvent("candle", candles[0]),
            ScriptedWebSocketEvent("disconnect", fault=WebSocketFault.DISCONNECT),
        ),
        description="WebSocket disconnect blocks new entries until reconnect health passes.",
    )


def dropped_websocket_messages_scenario() -> FailureScenario:
    candles = _fixture_candles(6)
    return FailureScenario(
        name="dropped_websocket_messages",
        fault=WebSocketFault.GAP_STORM,
        expected_action="block_new_entries",
        websocket_script=(
            ScriptedWebSocketEvent("candle", candles[0]),
            ScriptedWebSocketEvent("drop", candles[1], WebSocketFault.GAP_STORM),
            ScriptedWebSocketEvent("drop", candles[2], WebSocketFault.GAP_STORM),
            ScriptedWebSocketEvent("drop", candles[3], WebSocketFault.GAP_STORM),
            ScriptedWebSocketEvent("candle", candles[4]),
        ),
        fallback_metric="max_gap_run",
        fallback_value=3,
        description="Three dropped 1m candles form a gap storm and block new entries.",
    )


def duplicate_candle_scenario() -> FailureScenario:
    candles = _fixture_candles(3)
    return FailureScenario(
        name="duplicate_candle",
        fault=WebSocketFault.DUPLICATE_CANDLE,
        expected_action="allow",
        websocket_script=(
            ScriptedWebSocketEvent("candle", candles[0]),
            ScriptedWebSocketEvent("candle", candles[1]),
            ScriptedWebSocketEvent("candle", candles[1], WebSocketFault.DUPLICATE_CANDLE),
            ScriptedWebSocketEvent("candle", candles[2]),
        ),
        description="Duplicate candle is deterministic and safe for idempotent de-duplication.",
    )


def out_of_order_candle_scenario() -> FailureScenario:
    candles = _fixture_candles(4)
    return FailureScenario(
        name="out_of_order_candle",
        fault=WebSocketFault.OUT_OF_ORDER,
        expected_action="allow",
        websocket_script=(
            ScriptedWebSocketEvent("candle", candles[0]),
            ScriptedWebSocketEvent("candle", candles[2], WebSocketFault.OUT_OF_ORDER),
            ScriptedWebSocketEvent("candle", candles[1], WebSocketFault.OUT_OF_ORDER),
            ScriptedWebSocketEvent("candle", candles[3]),
        ),
        description="Out-of-order candle is deterministic and safe for timestamp ordering.",
    )


def listenkey_expired_scenario() -> FailureScenario:
    return FailureScenario(
        name="listenkey_expired",
        fault=ExchangeFault.LISTENKEY_EXPIRED,
        expected_action="block_new_entries",
        websocket_script=(ScriptedWebSocketEvent("listen_key_expired", fault=ExchangeFault.LISTENKEY_EXPIRED, payload={"event": "listenKeyExpired"}),),
        description="Expired user-data listenKey blocks new entries until renewed.",
    )


def cancel_accepted_fill_race_scenario() -> FailureScenario:
    return FailureScenario(
        name="cancel_accepted_fill_race",
        fault=ExchangeFault.ORDER_UNKNOWN,
        expected_action="hard_kill",
        http_script=(
            ScriptedHttpResponse(200, {"orderId": 42, "status": "CANCELED"}, {}, "cancel accepted"),
            ScriptedHttpResponse(200, {"orderId": 42, "status": "FILLED", "lastFilledQty": "0.001"}, {}, "fill raced cancel"),
        ),
        retry_policy=RetryPolicy(max_attempts=1, retry_statuses=()),
        description="A fill racing a cancel is treated as unknown exit state and hard-kills.",
    )


def rest_backfill_missing_candle_scenario() -> FailureScenario:
    candles = _fixture_candles(3)
    missing_time = candles[1].open_time
    return FailureScenario(
        name="rest_backfill_missing_requested_candle",
        fault=WebSocketFault.GAP_STORM,
        expected_action="no_trade_current_bar",
        http_script=(ScriptedHttpResponse(200, {"requested_open_time": missing_time.isoformat(), "klines": []}, {}, "empty backfill"),),
        retry_policy=RetryPolicy(max_attempts=1, retry_statuses=()),
        fallback_metric="critical_feature_missing_rate_current_bar",
        fallback_value=1.0,
        description="Backfill that omits the requested candle disables trading for the current bar.",
    )


def _fixture_candles(rows: int) -> tuple[data.Candle, ...]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[data.Candle] = []
    previous_close = 100000.0
    for index in range(rows):
        open_price = previous_close
        close = 100000.0 + index * 10.0
        candles.append(
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=open_price,
                high=max(open_price, close) + 5.0,
                low=min(open_price, close) - 5.0,
                close=close,
                volume=10.0 + index,
                quote_volume=(10.0 + index) * close,
                number_of_trades=100 + index,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=5.0 * close,
            )
        )
        previous_close = close
    return tuple(candles)
