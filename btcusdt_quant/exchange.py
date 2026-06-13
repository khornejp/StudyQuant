from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from .secrets import ExchangeCredentials


MARKET = "MARKET"
LIMIT = "LIMIT"
TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
STOP_MARKET = "STOP_MARKET"
SUPPORTED_ORDER_TYPES: tuple[str, ...] = (MARKET, LIMIT, TAKE_PROFIT_MARKET, STOP_MARKET)
EXIT_ORDER_TYPES: tuple[str, ...] = (TAKE_PROFIT_MARKET, STOP_MARKET)


@dataclass(frozen=True)
class ExchangeRequest:
    method: str
    url: str
    path: str
    params: Mapping[str, object] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    signed: bool = False


@dataclass(frozen=True)
class ExchangeResponse:
    status_code: int
    payload: object | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    request: ExchangeRequest | None = None
    used_weight_1m: int | None = None
    order_count_10s: int | None = None
    retry_after_seconds: float | None = None
    unknown_execution: bool = False


@dataclass(frozen=True)
class ExchangeOrder:
    symbol: str
    side: str
    order_type: str
    quantity: float
    reduce_only: bool = False
    price: float | None = None
    client_order_id: str | None = None
    status: str = "NEW"
    order_id: int | None = None
    time_in_force: str | None = None
    stop_price: float | None = None
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExchangePosition:
    symbol: str
    quantity: float
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    leverage: float = 0.0
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExchangeAccount:
    total_wallet_balance: float
    available_balance: float
    assets: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ListenKeyState:
    listen_key: str
    status: str = "ACTIVE"
    expires_in_minutes: int = 60
    raw: Mapping[str, object] = field(default_factory=dict)


class ExchangeAdapter(Protocol):
    network_enabled: bool

    def submit_order(
        self,
        symbol: str | ExchangeOrder,
        side: str | None = None,
        order_type: str | None = None,
        quantity: float | None = None,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> ExchangeOrder:
        ...

    def query_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> ExchangeOrder | None:
        ...

    def get_position(self, symbol: str) -> ExchangePosition:
        ...

    def get_account(self) -> ExchangeAccount:
        ...

    def get_listen_key(self) -> ListenKeyState:
        ...

    def keepalive_listen_key(self, listen_key: str) -> ListenKeyState:
        ...

    def delete_listen_key(self, listen_key: str) -> ListenKeyState:
        ...


HttpTransport = Callable[[ExchangeRequest], ExchangeResponse]
MockOrder = ExchangeOrder


class MockExchangeAdapter:
    """Deterministic exchange adapter; never performs network I/O."""

    def __init__(self) -> None:
        self.orders: list[ExchangeOrder] = []
        self.network_enabled = False
        self.listen_key = "mock_listen_key"

    def submit_order(
        self,
        symbol: str | ExchangeOrder,
        side: str | None = None,
        order_type: str | None = None,
        quantity: float | None = None,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> ExchangeOrder:
        if self.network_enabled:
            raise RuntimeError("live network access is forbidden in local scaffold")
        order = _coerce_order(symbol, side, order_type, quantity, reduce_only, **kwargs)
        self._validate_order(order)
        accepted = replace(order, order_id=999_999_000 + len(self.orders), status="MOCK_ACCEPTED")
        self.orders.append(accepted)
        return accepted

    def query_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> ExchangeOrder | None:
        if symbol != "BTCUSDT":
            raise ValueError("only BTCUSDT fixture is supported")
        for order in self.orders:
            if order_id is not None and order.order_id == order_id:
                return order
            if client_order_id is not None and order.client_order_id == client_order_id:
                return order
        return None

    def get_position(self, symbol: str) -> ExchangePosition:
        if symbol != "BTCUSDT":
            raise ValueError("only BTCUSDT fixture is supported")
        return ExchangePosition(symbol, 0.0)

    def get_account(self) -> ExchangeAccount:
        return ExchangeAccount(total_wallet_balance=10_000.0, available_balance=10_000.0)

    def get_listen_key(self) -> ListenKeyState:
        return ListenKeyState(self.listen_key, status="MOCK_ACTIVE")

    def keepalive_listen_key(self, listen_key: str) -> ListenKeyState:
        if listen_key != self.listen_key:
            raise ValueError("unknown mock listen key")
        return ListenKeyState(listen_key, status="MOCK_KEEPALIVE")

    def delete_listen_key(self, listen_key: str) -> ListenKeyState:
        if listen_key != self.listen_key:
            raise ValueError("unknown mock listen key")
        return ListenKeyState(listen_key, status="MOCK_DELETED")

    @staticmethod
    def _validate_order(order: ExchangeOrder) -> None:
        if order.symbol != "BTCUSDT":
            raise ValueError("only BTCUSDT fixture is supported")
        if order.side not in {"BUY", "SELL"}:
            raise ValueError("invalid side")
        if order.order_type not in SUPPORTED_ORDER_TYPES:
            raise ValueError("invalid order type")
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")


class BinanceUsdMFuturesTestnetAdapter:
    """Signed Binance USD-M futures adapter with explicit network opt-in."""

    BASE_URL = "https://testnet.binancefuture.com"

    def __init__(
        self,
        credentials: ExchangeCredentials,
        allow_signed_network: bool = False,
        recv_window_ms: int = 5000,
        transport: HttpTransport | None = None,
        base_url: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if recv_window_ms <= 0:
            raise ValueError("recv_window_ms must be positive")
        self.credentials = credentials
        self.allow_signed_network = allow_signed_network
        self.recv_window_ms = recv_window_ms
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.clock = clock
        self.transport = transport or self._urllib_transport
        self.network_enabled = allow_signed_network
        self.last_response: ExchangeResponse | None = None

    def submit_order(
        self,
        symbol: str | ExchangeOrder,
        side: str | None = None,
        order_type: str | None = None,
        quantity: float | None = None,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> ExchangeOrder:
        order = _coerce_order(symbol, side, order_type, quantity, reduce_only, **kwargs)
        order = self._ensure_client_order_id(order)
        params: dict[str, object] = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.order_type,
            "quantity": _decimal_text(order.quantity),
            "newClientOrderId": order.client_order_id or "",
        }
        if order.reduce_only:
            params["reduceOnly"] = "true"
        if order.price is not None:
            params["price"] = _decimal_text(order.price)
        if order.time_in_force is not None:
            params["timeInForce"] = order.time_in_force
        if order.stop_price is not None:
            params["stopPrice"] = _decimal_text(order.stop_price)
        response = self._send("POST", "/fapi/v1/order", params, signed=True)
        if response.status_code == 503:
            queried = self.query_order(order.symbol, client_order_id=order.client_order_id)
            if queried is not None:
                return queried
            self.last_response = replace(response, unknown_execution=True)
            return replace(order, status="UNKNOWN", raw={"http_status": 503, "clientOrderId": order.client_order_id or ""})
        parsed = self._order_from_response(response, fallback=order)
        return parsed

    def query_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> ExchangeOrder | None:
        if order_id is None and client_order_id is None:
            raise ValueError("order_id or client_order_id is required")
        params: dict[str, object] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        response = self._send("GET", "/fapi/v1/order", params, signed=True)
        if response.status_code == 200 and isinstance(response.payload, Mapping):
            return _order_from_payload(response.payload)
        return None

    def get_position(self, symbol: str) -> ExchangePosition:
        response = self._send("GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)
        payload = response.payload
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            for row in payload:
                if isinstance(row, Mapping) and row.get("symbol") == symbol:
                    return _position_from_payload(row)
        if isinstance(payload, Mapping):
            return _position_from_payload(payload)
        return ExchangePosition(symbol, 0.0, raw={"http_status": response.status_code})

    def get_account(self) -> ExchangeAccount:
        response = self._send("GET", "/fapi/v2/account", {}, signed=True)
        if isinstance(response.payload, Mapping):
            payload = response.payload
            return ExchangeAccount(
                total_wallet_balance=_float_value(payload.get("totalWalletBalance")),
                available_balance=_float_value(payload.get("availableBalance")),
                assets=tuple(payload.get("assets", ())) if isinstance(payload.get("assets", ()), Sequence) else tuple(),
                raw=payload,
            )
        return ExchangeAccount(0.0, 0.0, raw={"http_status": response.status_code})

    def get_listen_key(self) -> ListenKeyState:
        response = self._send("POST", "/fapi/v1/listenKey", {}, signed=False, api_key_required=True)
        if isinstance(response.payload, Mapping):
            listen_key = str(response.payload.get("listenKey", ""))
            return ListenKeyState(listen_key, status="ACTIVE", raw=response.payload)
        return ListenKeyState("", status="ERROR", raw={"http_status": response.status_code})

    def keepalive_listen_key(self, listen_key: str) -> ListenKeyState:
        response = self._send("PUT", "/fapi/v1/listenKey", {"listenKey": listen_key}, signed=False, api_key_required=True)
        status = "KEEPALIVE" if 200 <= response.status_code < 300 else "ERROR"
        return ListenKeyState(listen_key, status=status, raw=_mapping_payload(response.payload, response.status_code))

    def delete_listen_key(self, listen_key: str) -> ListenKeyState:
        response = self._send("DELETE", "/fapi/v1/listenKey", {"listenKey": listen_key}, signed=False, api_key_required=True)
        status = "DELETED" if 200 <= response.status_code < 300 else "ERROR"
        return ListenKeyState(listen_key, status=status, raw=_mapping_payload(response.payload, response.status_code))

    def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, object],
        signed: bool,
        api_key_required: bool = True,
    ) -> ExchangeResponse:
        if (signed or api_key_required) and not self.allow_signed_network:
            raise RuntimeError("signed Binance network access requires allow_signed_network=True")
        request = self._build_request(method, path, params, signed=signed, api_key_required=api_key_required)
        response = self.transport(request)
        parsed = _with_rate_limit_headers(response, request)
        self.last_response = parsed
        return parsed

    def _build_request(
        self,
        method: str,
        path: str,
        params: Mapping[str, object],
        signed: bool,
        api_key_required: bool = True,
    ) -> ExchangeRequest:
        query_params: dict[str, object] = dict(params)
        if signed:
            query_params["timestamp"] = self._timestamp_ms()
            query_params["recvWindow"] = self.recv_window_ms
            query_string = urllib.parse.urlencode(query_params)
            query_params["signature"] = self._signature(query_string)
        query_string = urllib.parse.urlencode(query_params)
        url = f"{self.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        headers = {"User-Agent": "btcusdt-quant-signed-adapter/0.1"}
        if api_key_required:
            headers["X-MBX-APIKEY"] = self.credentials.api_key
        return ExchangeRequest(method=method.upper(), url=url, path=path, params=query_params, headers=headers, signed=signed)

    def _signature(self, query_string: str) -> str:
        return hmac.new(self.credentials.api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()

    def _timestamp_ms(self) -> int:
        return int(self.clock() * 1000)

    def _urllib_transport(self, request: ExchangeRequest) -> ExchangeResponse:
        urllib_request = urllib.request.Request(request.url, data=request.body, headers=dict(request.headers), method=request.method)
        try:
            with urllib.request.urlopen(urllib_request, timeout=10) as response:
                payload = _decode_payload(response.read())
                return ExchangeResponse(response.getcode(), payload=payload, headers=dict(response.headers), request=request)
        except urllib.error.HTTPError as error:
            payload = _decode_payload(error.read())
            return ExchangeResponse(error.code, payload=payload, headers=dict(error.headers), request=request)

    def _ensure_client_order_id(self, order: ExchangeOrder) -> ExchangeOrder:
        if order.client_order_id:
            return order
        prefix = "btcusdt_quant"
        return replace(order, client_order_id=f"{prefix}_{self._timestamp_ms()}")

    def _order_from_response(self, response: ExchangeResponse, fallback: ExchangeOrder) -> ExchangeOrder:
        if isinstance(response.payload, Mapping):
            return _order_from_payload(response.payload)
        status = "ACCEPTED" if 200 <= response.status_code < 300 else "REJECTED"
        return replace(fallback, status=status, raw={"http_status": response.status_code})


class BinanceUsdMFuturesProdAdapter(BinanceUsdMFuturesTestnetAdapter):
    BASE_URL = "https://fapi.binance.com"

    def __init__(
        self,
        credentials: ExchangeCredentials,
        environment: str = "testnet",
        allow_prod: bool = False,
        approval_artifacts: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        if environment != "prod":
            raise RuntimeError("production adapter requires environment='prod'")
        if not allow_prod:
            raise RuntimeError("production adapter requires allow_prod=True")
        if approval_artifacts is None:
            raise RuntimeError("production adapter requires approval artifacts")
        from . import governance

        ok, errors = governance.verify_manifest(Path(approval_artifacts))
        if not ok:
            joined = "; ".join(errors)
            raise RuntimeError(f"production adapter requires valid approval artifacts: {joined}")
        semantic_ok, semantic_errors = governance.ApprovalValidator().validate(Path(approval_artifacts))
        if not semantic_ok:
            joined = "; ".join(semantic_errors)
            raise RuntimeError(f"production adapter requires semantic approval validation: {joined}")
        super().__init__(credentials, base_url=self.BASE_URL, **kwargs)


def parse_rate_limit_headers(headers: Mapping[str, object]) -> tuple[int | None, int | None, float | None]:
    used_weight = _int_header(headers, "X-MBX-USED-WEIGHT-1M")
    order_count = _int_header(headers, "X-MBX-ORDER-COUNT-10S")
    retry_after = _float_header(headers, "Retry-After")
    return used_weight, order_count, retry_after


def _coerce_order(
    symbol: str | ExchangeOrder,
    side: str | None,
    order_type: str | None,
    quantity: float | None,
    reduce_only: bool,
    **kwargs: Any,
) -> ExchangeOrder:
    if isinstance(symbol, ExchangeOrder):
        return symbol
    if side is None or order_type is None or quantity is None:
        raise ValueError("symbol, side, order_type, and quantity are required")
    return ExchangeOrder(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=float(quantity),
        reduce_only=reduce_only,
        price=kwargs.get("price"),
        client_order_id=kwargs.get("client_order_id"),
        time_in_force=kwargs.get("time_in_force"),
        stop_price=kwargs.get("stop_price"),
    )


def _order_from_payload(payload: Mapping[str, object]) -> ExchangeOrder:
    return ExchangeOrder(
        symbol=str(payload.get("symbol", "")),
        side=str(payload.get("side", "")),
        order_type=str(payload.get("type", payload.get("order_type", ""))),
        quantity=_float_value(payload.get("origQty", payload.get("quantity", payload.get("executedQty", 0.0)))),
        reduce_only=_bool_value(payload.get("reduceOnly", False)),
        price=_optional_float(payload.get("price")),
        client_order_id=_optional_str(payload.get("clientOrderId", payload.get("newClientOrderId"))),
        status=str(payload.get("status", "")),
        order_id=_optional_int(payload.get("orderId")),
        time_in_force=_optional_str(payload.get("timeInForce")),
        stop_price=_optional_float(payload.get("stopPrice")),
        raw=payload,
    )


def _position_from_payload(payload: Mapping[str, object]) -> ExchangePosition:
    return ExchangePosition(
        symbol=str(payload.get("symbol", "")),
        quantity=_float_value(payload.get("positionAmt", payload.get("quantity", 0.0))),
        entry_price=_float_value(payload.get("entryPrice", 0.0)),
        unrealized_pnl=_float_value(payload.get("unRealizedProfit", payload.get("unrealizedPnl", 0.0))),
        leverage=_float_value(payload.get("leverage", 0.0)),
        raw=payload,
    )


def _with_rate_limit_headers(response: ExchangeResponse, request: ExchangeRequest) -> ExchangeResponse:
    used_weight, order_count, retry_after = parse_rate_limit_headers(response.headers)
    return replace(
        response,
        request=response.request or request,
        used_weight_1m=used_weight,
        order_count_10s=order_count,
        retry_after_seconds=retry_after,
    )


def _decode_payload(raw: bytes) -> object | None:
    if not raw:
        return None
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _mapping_payload(payload: object | None, status_code: int) -> Mapping[str, object]:
    if isinstance(payload, Mapping):
        return payload
    return {"http_status": status_code}


def _header_value(headers: Mapping[str, object], name: str) -> object | None:
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return value
    return None


def _int_header(headers: Mapping[str, object], name: str) -> int | None:
    value = _header_value(headers, name)
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _float_header(headers: Mapping[str, object], name: str) -> float | None:
    value = _header_value(headers, name)
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _float_value(value: object) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _decimal_text(value: float) -> str:
    return format(value, "f").rstrip("0").rstrip(".")
