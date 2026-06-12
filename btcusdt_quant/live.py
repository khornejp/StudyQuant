from __future__ import annotations

import json
import queue
import threading
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Mapping, Sequence

from . import data, dataset, governance, monitoring, sources
from .exchange import MARKET, STOP_MARKET, TAKE_PROFIT_MARKET, ExchangeAdapter, ExchangeOrder, MockExchangeAdapter, MockOrder
from .risk import DrawdownProtocol, DrawdownState, RiskDecision, RiskPolicy


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
class ExecutionJournalEntry:
    action: str
    reason: str
    order_id: int | None = None
    client_order_id: str | None = None
    symbol: str = "BTCUSDT"
    status: str = ""
    reconciled: bool = False
    timestamp: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


class ExecutionJournal:
    def __init__(self, path: str | Path | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.entries: list[ExecutionJournalEntry] = []

    def record(
        self,
        action: str,
        reason: str,
        order: ExchangeOrder | None = None,
        order_id: int | None = None,
        client_order_id: str | None = None,
        symbol: str = "BTCUSDT",
        status: str = "",
        reconciled: bool = False,
        details: Mapping[str, object] | None = None,
    ) -> ExecutionJournalEntry:
        if order is not None:
            order_id = order.order_id
            client_order_id = order.client_order_id
            symbol = order.symbol
            status = order.status
        entry = ExecutionJournalEntry(
            action=action,
            reason=reason,
            order_id=order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            status=status,
            reconciled=reconciled,
            timestamp=self.clock().astimezone(timezone.utc).isoformat(),
            details=dict(details or {}),
        )
        self.entries.append(entry)
        self.write()
        return entry

    def reconcile(self, adapter: ExchangeAdapter, symbol: str = "BTCUSDT") -> list[ExecutionJournalEntry]:
        reconciled: list[ExecutionJournalEntry] = []
        for entry in self.entries:
            if entry.order_id is None and entry.client_order_id is None:
                reconciled.append(entry)
                continue
            exchange_order = adapter.query_order(symbol, order_id=entry.order_id, client_order_id=entry.client_order_id)
            if exchange_order is None:
                reconciled.append(replace(entry, status=entry.status or "MISSING_ON_EXCHANGE", reconciled=False))
                continue
            reconciled.append(
                replace(
                    entry,
                    order_id=exchange_order.order_id,
                    client_order_id=exchange_order.client_order_id,
                    status=exchange_order.status,
                    reconciled=True,
                    details={**dict(entry.details), "exchange_status": exchange_order.status},
                )
            )
        self.entries = reconciled
        self.write()
        return list(self.entries)

    def rows(self) -> list[dict[str, object]]:
        return [
            {
                "action": entry.action,
                "reason": entry.reason,
                "order_id": entry.order_id,
                "client_order_id": entry.client_order_id,
                "symbol": entry.symbol,
                "status": entry.status,
                "reconciled": entry.reconciled,
                "timestamp": entry.timestamp,
                "details": dict(entry.details),
            }
            for entry in self.entries
        ]

    def write(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else self.path
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.rows(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


_BLOCK_ENTRY_ACTIONS = {"block_entries", "block_new_entries", "drop_sample", "no_trade_current_bar", "rollback_to_champion"}
_HARD_KILL_ACTIONS = {"hard_kill"}
_RESOLVED_ORDER_STATUSES = {"CANCELED", "CANCELLED", "FILLED", "EXPIRED", "REJECTED", "MISSING"}


def safe_market_entry(
    state: PositionState | str | None = None,
    signal_side: str | None = None,
    quantity: float = 0.0,
    adapter: ExchangeAdapter | None = None,
    *,
    symbol: str = "BTCUSDT",
    side: str | None = None,
    policy: RiskPolicy | None = None,
    account_balance_usdt: float | None = None,
    required_margin: float | None = None,
    leverage: float | None = None,
    notional: float | None = None,
    source_parity_passed: bool = True,
    data_quality_action: object = "allow",
    gap_action: object = "allow",
    minutes_to_next_funding: int | None = None,
    adl_quantile: int | None = None,
    clock_drift_ms: int | None = None,
    drawdown_state: DrawdownState | None = None,
    rate_limit_manager: RateLimitManager | None = None,
    rate_limit_endpoint: str = "POST /fapi/v1/order",
    rate_limit_weight: int = 1,
    submit: bool = False,
    allow_live_orders: bool = False,
    client_order_id: str | None = None,
    monitor_decisions: Sequence[Mapping[str, object] | str] | None = None,
    return_decision: bool = False,
) -> str | RiskDecision:
    entry_side = signal_side or side or "BUY"
    position_state = _coerce_position_state(state, symbol)
    decision = _entry_gate_decision(
        position_state,
        entry_side,
        quantity,
        adapter=adapter,
        policy=policy or RiskPolicy(),
        account_balance_usdt=account_balance_usdt,
        required_margin=required_margin,
        leverage=leverage,
        notional=notional,
        source_parity_passed=source_parity_passed,
        data_quality_action=data_quality_action,
        gap_action=gap_action,
        minutes_to_next_funding=minutes_to_next_funding,
        adl_quantile=adl_quantile,
        clock_drift_ms=clock_drift_ms,
        drawdown_state=drawdown_state,
        rate_limit_manager=rate_limit_manager,
        rate_limit_endpoint=rate_limit_endpoint,
        rate_limit_weight=rate_limit_weight,
        submit=submit,
        allow_live_orders=allow_live_orders,
        client_order_id=client_order_id,
        monitor_decisions=monitor_decisions,
    )
    if return_decision:
        return decision
    return decision.action


def submit_entry_with_brackets(
    adapter: ExchangeAdapter | None = None,
    symbol: str = "BTCUSDT",
    side: str = "BUY",
    quantity: float = 0.0,
    take_profit_price: float | None = None,
    stop_loss_price: float | None = None,
    client_order_id_prefix: str | None = None,
    allow_live_orders: bool = False,
) -> tuple[ExchangeOrder, ExchangeOrder, ExchangeOrder]:
    exchange_adapter = adapter or MockExchangeAdapter()
    _ensure_order_submission_allowed(exchange_adapter, allow_live_orders)
    prefix = _client_order_prefix(exchange_adapter, symbol, side, client_order_id_prefix)
    entry = exchange_adapter.submit_order(symbol, side, MARKET, quantity, client_order_id=f"{prefix}_entry")
    take_profit, stop_loss = submit_take_profit_stop_loss(
        exchange_adapter,
        symbol=symbol,
        position_side=side,
        quantity=quantity,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        client_order_id_prefix=prefix,
        allow_live_orders=allow_live_orders,
    )
    return entry, take_profit, stop_loss


def submit_take_profit_stop_loss(
    adapter: ExchangeAdapter | None = None,
    symbol: str = "BTCUSDT",
    position_side: str = "BUY",
    quantity: float = 0.0,
    take_profit_price: float | None = None,
    stop_loss_price: float | None = None,
    client_order_id_prefix: str | None = None,
    allow_live_orders: bool = False,
) -> tuple[ExchangeOrder, ExchangeOrder]:
    if quantity <= 0.0:
        raise ValueError("quantity must be positive")
    if take_profit_price is None or take_profit_price <= 0.0:
        raise ValueError("take_profit_price must be positive")
    if stop_loss_price is None or stop_loss_price <= 0.0:
        raise ValueError("stop_loss_price must be positive")
    exchange_adapter = adapter or MockExchangeAdapter()
    _ensure_order_submission_allowed(exchange_adapter, allow_live_orders)
    exit_side = _exit_side(position_side)
    prefix = _client_order_prefix(exchange_adapter, symbol, position_side, client_order_id_prefix)
    take_profit = exchange_adapter.submit_order(
        ExchangeOrder(
            symbol,
            exit_side,
            TAKE_PROFIT_MARKET,
            quantity,
            reduce_only=True,
            client_order_id=f"{prefix}_tp",
            stop_price=take_profit_price,
        )
    )
    stop_loss = exchange_adapter.submit_order(
        ExchangeOrder(
            symbol,
            exit_side,
            STOP_MARKET,
            quantity,
            reduce_only=True,
            client_order_id=f"{prefix}_sl",
            stop_price=stop_loss_price,
        )
    )
    return take_profit, stop_loss


def wait_until_exit_orders_resolved(
    adapter: ExchangeAdapter,
    symbol: str,
    exit_orders: Sequence[ExchangeOrder],
    max_checks: int = 3,
    cancel_first: bool = True,
) -> RiskDecision:
    if max_checks <= 0:
        raise ValueError("max_checks must be positive")
    cancel_order = getattr(adapter, "cancel_order", None)
    if cancel_first and callable(cancel_order):
        for order in exit_orders:
            cancel_order(symbol, order_id=order.order_id, client_order_id=order.client_order_id)
    unresolved: list[dict[str, object]] = []
    for _ in range(max_checks):
        unresolved = []
        for order in exit_orders:
            queried = adapter.query_order(symbol, order_id=order.order_id, client_order_id=order.client_order_id)
            status = "MISSING" if queried is None else queried.status
            if status not in _RESOLVED_ORDER_STATUSES:
                unresolved.append({"client_order_id": order.client_order_id, "order_id": order.order_id, "status": status})
        if not unresolved:
            return RiskDecision("allow", True, "exit orders resolved", "exit_order_cancel", details={"checks": max_checks})
    return RiskDecision("hard_kill", False, "exit order cancel confirmation unresolved", "exit_order_cancel", "hard_kill", 0.0, {"unresolved": unresolved})


def gap_cross_exit(
    position_qty: float = 0.0,
    gap_cross_detected: bool = True,
    adapter: ExchangeAdapter | None = None,
    *,
    symbol: str = "BTCUSDT",
    active_exit_orders: Sequence[ExchangeOrder] = (),
    cancel_resolved: bool | None = None,
    allow_live_orders: bool = False,
    client_order_id: str | None = None,
    journal: ExecutionJournal | None = None,
    monitor_decisions: Sequence[Mapping[str, object] | str] | None = None,
    return_decision: bool = False,
) -> str | RiskDecision:
    monitor_decision = _monitoring_decision(monitor_decisions)
    if monitor_decision.action == "hard_kill":
        decision = RiskDecision("hard_kill", False, "monitoring hard kill before gap-cross exit", "monitoring", "hard_kill", 0.0)
        return decision if return_decision else decision.action
    if not gap_cross_detected:
        decision = RiskDecision("allow", True, "no gap-cross event", "gap_cross")
        return decision if return_decision else decision.action
    if position_qty == 0.0:
        decision = RiskDecision("no_market_exit_needed", True, "flat position", "gap_cross")
        return decision if return_decision else decision.action
    exchange_adapter = adapter or MockExchangeAdapter()
    if active_exit_orders:
        cancel_decision = RiskDecision("allow", True, "exit orders already resolved", "exit_order_cancel") if cancel_resolved else None
        if cancel_resolved is None:
            cancel_decision = wait_until_exit_orders_resolved(exchange_adapter, symbol, active_exit_orders)
        if cancel_decision is None or not cancel_decision.allowed:
            if journal is not None:
                journal.record("hard_kill", "gap_cross_exit_unresolved_exit_orders", details=dict(cancel_decision.details if cancel_decision is not None else {}))
            decision = RiskDecision("hard_kill", False, "active exit orders unresolved before market exit", "gap_cross", "hard_kill", 0.0)
            return decision if return_decision else decision.action
    _ensure_order_submission_allowed(exchange_adapter, allow_live_orders)
    exit_side = "SELL" if position_qty > 0.0 else "BUY"
    order = exchange_adapter.submit_order(symbol, exit_side, MARKET, abs(position_qty), reduce_only=True, client_order_id=client_order_id)
    if journal is not None:
        journal.record("market_exit_submitted", "gap_cross_exit", order=order)
    decision = RiskDecision("market_exit_submitted", True, "gap-cross reduce-only market exit submitted", "gap_cross", details={"order_id": order.order_id, "client_order_id": order.client_order_id})
    return decision if return_decision else decision.action


class LiveExecutionEngine:
    def __init__(
        self,
        adapter: ExchangeAdapter | None = None,
        policy: RiskPolicy | None = None,
        rate_limit_manager: RateLimitManager | None = None,
        journal: ExecutionJournal | None = None,
        journal_path: str | Path | None = None,
        allow_live_orders: bool = False,
        monitor_decisions: Sequence[Mapping[str, object] | str] | None = None,
    ) -> None:
        self.adapter = adapter or MockExchangeAdapter()
        self.policy = policy or RiskPolicy()
        self.rate_limit_manager = rate_limit_manager or RateLimitManager()
        self.journal = journal or ExecutionJournal(journal_path)
        self.allow_live_orders = allow_live_orders
        self.monitor_decisions = tuple(monitor_decisions or ())

    def safe_market_entry(self, state: PositionState | str | None = None, signal_side: str | None = None, quantity: float = 0.0, return_decision: bool = False, **kwargs: Any) -> str | RiskDecision:
        kwargs.setdefault("monitor_decisions", self.monitor_decisions)
        decision = safe_market_entry(
            state,
            signal_side,
            quantity,
            self.adapter,
            policy=self.policy,
            rate_limit_manager=self.rate_limit_manager,
            allow_live_orders=self.allow_live_orders,
            return_decision=True,
            **kwargs,
        )
        assert isinstance(decision, RiskDecision)
        self.journal.record(decision.action, decision.reason, details={"gate": decision.gate, "tier": decision.tier, **dict(decision.details)})
        return decision if return_decision else decision.action

    def submit_entry_with_brackets(self, symbol: str, side: str, quantity: float, take_profit_price: float, stop_loss_price: float, client_order_id_prefix: str | None = None) -> tuple[ExchangeOrder, ExchangeOrder, ExchangeOrder]:
        orders = submit_entry_with_brackets(
            self.adapter,
            symbol=symbol,
            side=side,
            quantity=quantity,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            client_order_id_prefix=client_order_id_prefix,
            allow_live_orders=self.allow_live_orders,
        )
        for order in orders:
            self.journal.record("order_submitted", "entry_with_brackets", order=order)
        return orders

    def submit_take_profit_stop_loss(self, symbol: str, position_side: str, quantity: float, take_profit_price: float, stop_loss_price: float, client_order_id_prefix: str | None = None) -> tuple[ExchangeOrder, ExchangeOrder]:
        orders = submit_take_profit_stop_loss(
            self.adapter,
            symbol=symbol,
            position_side=position_side,
            quantity=quantity,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            client_order_id_prefix=client_order_id_prefix,
            allow_live_orders=self.allow_live_orders,
        )
        for order in orders:
            self.journal.record("exit_order_submitted", "take_profit_stop_loss", order=order)
        return orders

    def wait_until_exit_orders_resolved(self, symbol: str, exit_orders: Sequence[ExchangeOrder], max_checks: int = 3) -> RiskDecision:
        decision = wait_until_exit_orders_resolved(self.adapter, symbol, exit_orders, max_checks=max_checks)
        self.journal.record(decision.action, decision.reason, details=decision.details)
        return decision

    def gap_cross_exit(
        self,
        position_qty: float = 0.0,
        gap_cross_detected: bool = True,
        active_exit_orders: Sequence[ExchangeOrder] = (),
        monitor_decisions: Sequence[Mapping[str, object] | str] | None = None,
    ) -> str:
        action = gap_cross_exit(
            position_qty,
            gap_cross_detected,
            self.adapter,
            active_exit_orders=active_exit_orders,
            allow_live_orders=self.allow_live_orders,
            journal=self.journal,
            monitor_decisions=self.monitor_decisions if monitor_decisions is None else monitor_decisions,
        )
        return str(action)

    def reconcile_journal(self, symbol: str = "BTCUSDT") -> list[ExecutionJournalEntry]:
        return self.journal.reconcile(self.adapter, symbol)

    def run(self, signals: Sequence[Mapping[str, object]]) -> list[RiskDecision]:
        decisions: list[RiskDecision] = []
        for signal in signals:
            side = str(signal.get("side", "HOLD"))
            if side == "HOLD":
                continue
            position = PositionState(str(signal.get("symbol", "BTCUSDT")), float(signal.get("position_qty", 0.0)))
            decision = self.safe_market_entry(
                position,
                side,
                float(signal.get("quantity", 0.0)),
                return_decision=True,
                account_balance_usdt=_optional_signal_float(signal, "account_balance_usdt"),
                required_margin=_optional_signal_float(signal, "required_margin"),
                leverage=_optional_signal_float(signal, "leverage"),
                notional=_optional_signal_float(signal, "notional"),
                source_parity_passed=bool(signal.get("source_parity_passed", True)),
                data_quality_action=signal.get("data_quality_action", "allow"),
                gap_action=signal.get("gap_action", "allow"),
                minutes_to_next_funding=_optional_signal_int(signal, "minutes_to_next_funding"),
                adl_quantile=_optional_signal_int(signal, "adl_quantile"),
                clock_drift_ms=_optional_signal_int(signal, "clock_drift_ms"),
                submit=bool(signal.get("submit", False)),
            )
            assert isinstance(decision, RiskDecision)
            decisions.append(decision)
        self.journal.write()
        return decisions


def _coerce_position_state(state: PositionState | str | None, symbol: str) -> PositionState:
    if isinstance(state, PositionState):
        return state
    if isinstance(state, str):
        return PositionState(state, 0.0)
    return PositionState(symbol, 0.0)


def _entry_gate_decision(
    state: PositionState,
    signal_side: str,
    quantity: float,
    *,
    adapter: ExchangeAdapter | None,
    policy: RiskPolicy,
    account_balance_usdt: float | None,
    required_margin: float | None,
    leverage: float | None,
    notional: float | None,
    source_parity_passed: bool,
    data_quality_action: object,
    gap_action: object,
    minutes_to_next_funding: int | None,
    adl_quantile: int | None,
    clock_drift_ms: int | None,
    drawdown_state: DrawdownState | None,
    rate_limit_manager: RateLimitManager | None,
    rate_limit_endpoint: str,
    rate_limit_weight: int,
    submit: bool,
    allow_live_orders: bool,
    client_order_id: str | None,
    monitor_decisions: Sequence[Mapping[str, object] | str] | None,
) -> RiskDecision:
    gate_decisions = _non_mutating_entry_gates(
        state,
        signal_side,
        quantity,
        policy,
        account_balance_usdt,
        required_margin,
        leverage,
        notional,
        source_parity_passed,
        data_quality_action,
        gap_action,
        minutes_to_next_funding,
        adl_quantile,
        clock_drift_ms,
        drawdown_state,
        monitor_decisions,
    )
    blocking = _blocking_decision(gate_decisions)
    if blocking is not None:
        return blocking
    rate_limit_decision = _rate_limit_decision(rate_limit_manager, rate_limit_endpoint, rate_limit_weight)
    if not rate_limit_decision.allowed:
        return rate_limit_decision
    gate_decisions.append(rate_limit_decision)
    reduce_decision = next((decision for decision in gate_decisions if decision.action == "reduce_size"), None)
    if reduce_decision is not None:
        return RiskDecision("reduce_size", True, reduce_decision.reason, reduce_decision.gate, reduce_decision.tier, reduce_decision.reduce_factor, {"gates": _decision_rows(gate_decisions)})
    if submit:
        exchange_adapter = adapter or MockExchangeAdapter()
        _ensure_order_submission_allowed(exchange_adapter, allow_live_orders)
        order = exchange_adapter.submit_order(state.symbol, signal_side, MARKET, quantity, client_order_id=client_order_id)
        return RiskDecision("market_entry_submitted", True, "entry gates passed and market entry submitted", "entry", details={"order_id": order.order_id, "client_order_id": order.client_order_id, "gates": _decision_rows(gate_decisions)})
    return RiskDecision("market_entry_allowed", True, "entry gates passed", "entry", details={"gates": _decision_rows(gate_decisions)})


def _non_mutating_entry_gates(
    state: PositionState,
    signal_side: str,
    quantity: float,
    policy: RiskPolicy,
    account_balance_usdt: float | None,
    required_margin: float | None,
    leverage: float | None,
    notional: float | None,
    source_parity_passed: bool,
    data_quality_action: object,
    gap_action: object,
    minutes_to_next_funding: int | None,
    adl_quantile: int | None,
    clock_drift_ms: int | None,
    drawdown_state: DrawdownState | None,
    monitor_decisions: Sequence[Mapping[str, object] | str] | None,
) -> list[RiskDecision]:
    decisions: list[RiskDecision] = []
    allowed, reason = OneWayPositionGuard().can_enter(state, signal_side)
    decisions.append(RiskDecision("allow" if allowed else "block_new_entries", allowed, reason, "position_guard"))
    decisions.append(RiskDecision("allow" if quantity > 0.0 else "block_new_entries", quantity > 0.0, "quantity accepted" if quantity > 0.0 else "quantity must be positive", "quantity"))
    decisions.append(_balance_decision(account_balance_usdt, required_margin, notional, leverage, policy))
    decisions.append(_leverage_decision(leverage, policy))
    decisions.append(RiskDecision("allow" if source_parity_passed else "block_new_entries", source_parity_passed, "source parity passed" if source_parity_passed else "train/live source parity failed", "source_parity"))
    decisions.append(_fallback_action_decision(data_quality_action, "data_quality"))
    decisions.append(_fallback_action_decision(gap_action, "gap_contamination"))
    decisions.append(_funding_decision(minutes_to_next_funding, policy))
    decisions.append(_threshold_action_decision(adl_quantile, policy.adl_action_thresholds, "adl", "ADL quantile policy passed"))
    decisions.append(_threshold_action_decision(clock_drift_ms if clock_drift_ms is None else abs(clock_drift_ms), policy.clock_drift_thresholds, "clock_drift", "clock drift policy passed"))
    if drawdown_state is None:
        decisions.append(RiskDecision("allow", True, "drawdown state not supplied", "drawdown"))
    else:
        decisions.append(DrawdownProtocol(policy).evaluate(drawdown_state))
    decisions.append(_monitoring_decision(monitor_decisions))
    return decisions


def _blocking_decision(decisions: Sequence[RiskDecision]) -> RiskDecision | None:
    for decision in decisions:
        if decision.action in _HARD_KILL_ACTIONS:
            return RiskDecision("hard_kill", False, decision.reason, decision.gate, "hard_kill", 0.0, {"gates": _decision_rows(decisions)})
    for decision in decisions:
        if decision.action in _BLOCK_ENTRY_ACTIONS or not decision.allowed:
            return RiskDecision("block_new_entries", False, decision.reason, decision.gate, "block_entries", 0.0, {"gates": _decision_rows(decisions)})
    return None


def _balance_decision(account_balance_usdt: float | None, required_margin: float | None, notional: float | None, leverage: float | None, policy: RiskPolicy) -> RiskDecision:
    if account_balance_usdt is None:
        return RiskDecision("allow", True, "balance not supplied", "balance")
    if account_balance_usdt <= 0.0:
        return RiskDecision("block_new_entries", False, "account balance must be positive", "balance")
    margin = required_margin
    if margin is None and notional is not None and leverage is not None and leverage > 0.0:
        margin = notional / leverage
    if margin is not None and margin > account_balance_usdt:
        return RiskDecision("block_new_entries", False, "required margin exceeds balance", "balance", details={"required_margin": margin, "account_balance_usdt": account_balance_usdt})
    if notional is not None and notional > account_balance_usdt * policy.max_notional_fraction:
        return RiskDecision("block_new_entries", False, "max_notional_fraction breached", "balance", details={"notional": notional, "max_notional": account_balance_usdt * policy.max_notional_fraction})
    return RiskDecision("allow", True, "balance policy passed", "balance")


def _leverage_decision(leverage: float | None, policy: RiskPolicy) -> RiskDecision:
    if leverage is None:
        return RiskDecision("allow", True, "leverage not supplied", "leverage")
    if leverage <= 0.0:
        return RiskDecision("block_new_entries", False, "leverage must be positive", "leverage")
    if leverage > policy.max_leverage:
        return RiskDecision("block_new_entries", False, "max leverage breached", "leverage", details={"leverage": leverage, "max_leverage": policy.max_leverage})
    return RiskDecision("allow", True, "leverage policy passed", "leverage")


def _fallback_action_decision(value: object, gate: str) -> RiskDecision:
    action = _action_value(value)
    if action in _HARD_KILL_ACTIONS:
        return RiskDecision("hard_kill", False, f"{gate} hard kill", gate, "hard_kill")
    if action in _BLOCK_ENTRY_ACTIONS:
        return RiskDecision("block_new_entries", False, f"{gate} blocks entries", gate, "block_entries")
    if action == "reduce_size":
        return RiskDecision("reduce_size", True, f"{gate} requests size reduction", gate, "reduce_size", 0.5)
    return RiskDecision("allow", True, f"{gate} policy passed", gate)


def _monitoring_decision(decisions: Sequence[Mapping[str, object] | str] | None) -> RiskDecision:
    action = _monitoring_action(decisions)
    if action in _HARD_KILL_ACTIONS:
        return RiskDecision("hard_kill", False, "monitoring hard kill", "monitoring", "hard_kill")
    if action in _BLOCK_ENTRY_ACTIONS:
        return RiskDecision("block_new_entries", False, "monitoring blocks entries", "monitoring", "block_entries")
    if action == "reduce_size":
        return RiskDecision("reduce_size", True, "monitoring requests size reduction", "monitoring", "reduce_size", 0.5)
    return RiskDecision("allow", True, "monitoring policy passed", "monitoring")


def _monitoring_action(decisions: Sequence[Mapping[str, object] | str] | None) -> str:
    priority = {action: index for index, action in enumerate(governance.FALLBACK_ACTIONS)}
    priority["warn"] = priority.get("warn_only", 1)
    priority["block_entries"] = priority.get("block_new_entries", 5)
    selected = "allow"
    for decision in decisions or ():
        action = _decision_action(decision)
        if priority.get(action, 0) > priority.get(selected, 0):
            selected = action
    return selected


def _decision_action(decision: Mapping[str, object] | str) -> str:
    if isinstance(decision, str):
        return decision
    action = decision.get("action")
    if isinstance(action, str):
        return action
    for metric in ("clock_drift_ms", "adl_quantile", "funding_blackout_active", "funding_cost_exceeds_edge", "brier_drift", "ece_drift"):
        if metric in decision:
            return governance.fallback_action(metric, decision[metric])
    return "allow"


def _funding_decision(minutes_to_next_funding: int | None, policy: RiskPolicy) -> RiskDecision:
    if minutes_to_next_funding is None:
        return RiskDecision("allow", True, "funding time not supplied", "funding_blackout")
    active = FundingEventManager().blackout_active(minutes_to_next_funding, policy.funding_blackout_minutes)
    return RiskDecision("block_new_entries" if active else "allow", not active, "funding blackout active" if active else "funding blackout policy passed", "funding_blackout")


def _threshold_action_decision(value: int | None, thresholds: Mapping[int, str], gate: str, allow_reason: str) -> RiskDecision:
    if value is None:
        return RiskDecision("allow", True, f"{gate} not supplied", gate)
    action = "allow"
    for threshold, candidate in sorted(thresholds.items()):
        if value >= threshold:
            action = candidate
    if action in _HARD_KILL_ACTIONS:
        return RiskDecision("hard_kill", False, f"{gate} hard kill threshold breached", gate, "hard_kill")
    if action in _BLOCK_ENTRY_ACTIONS:
        return RiskDecision("block_new_entries", False, f"{gate} blocks entries", gate, "block_entries")
    if action == "reduce_size":
        return RiskDecision("reduce_size", True, f"{gate} requests size reduction", gate, "reduce_size", 0.5)
    return RiskDecision("allow", True, allow_reason, gate)


def _rate_limit_decision(manager: RateLimitManager | None, endpoint: str, weight: int) -> RiskDecision:
    if manager is None:
        return RiskDecision("allow", True, "rate limit manager not supplied", "rate_limit")
    try:
        manager.acquire(endpoint, weight)
        return RiskDecision("allow", True, "rate limit budget acquired", "rate_limit")
    except RateLimitHardBanActive:
        return RiskDecision("hard_kill", False, "rate limit hard ban active", "rate_limit", "hard_kill")
    except (RateLimitBackoffActive, RateLimitBudgetExceeded):
        return RiskDecision("block_new_entries", False, "rate limit entry budget unavailable", "rate_limit", "block_entries")


def _action_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        action = value.get("action")
        return str(action) if action is not None else "allow"
    action = getattr(value, "action", None)
    return str(action) if action is not None else "allow"


def _decision_rows(decisions: Sequence[RiskDecision]) -> list[dict[str, object]]:
    return [
        {
            "gate": decision.gate,
            "action": decision.action,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "tier": decision.tier,
            "reduce_factor": decision.reduce_factor,
        }
        for decision in decisions
    ]


def _ensure_order_submission_allowed(adapter: ExchangeAdapter, allow_live_orders: bool) -> None:
    if getattr(adapter, "network_enabled", False) and not allow_live_orders:
        raise RuntimeError("real order submission requires allow_live_orders=True")


def _client_order_prefix(adapter: ExchangeAdapter, symbol: str, side: str, prefix: str | None) -> str:
    if prefix:
        return prefix
    sequence = len(getattr(adapter, "orders", ()))
    return f"btcusdt_quant_{symbol.lower()}_{side.lower()}_{sequence}"


def _exit_side(position_side: str) -> str:
    if position_side == "BUY":
        return "SELL"
    if position_side == "SELL":
        return "BUY"
    raise ValueError("position_side must be BUY or SELL")


def _optional_signal_float(signal: Mapping[str, object], name: str) -> float | None:
    value = signal.get(name)
    if value in (None, ""):
        return None
    return float(value)


def _optional_signal_int(signal: Mapping[str, object], name: str) -> int | None:
    value = signal.get(name)
    if value in (None, ""):
        return None
    return int(value)


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
    source_bundle: sources.MarketSourceBundle | None = None

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
        while True:
            try:
                self._messages.get_nowait()
            except queue.Empty:
                break
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
    exchange_adapter: ExchangeAdapter | None = None,
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
    source_bundle = build_live_source_bundle(canonical, dry_run=dry_run)
    clock_monitor_row = monitoring.ClockDriftService().evaluate()
    adl_monitor_row = monitoring.ADLMonitorService().evaluate(source_bundle.adl_quantile)
    funding_monitor_row = monitoring.FundingMonitorService().evaluate(source_bundle.funding_rate)
    calibration_monitor_row = monitoring.CalibrationDriftMonitor().evaluate([], [])
    monitor_decisions = (clock_monitor_row, adl_monitor_row, funding_monitor_row, calibration_monitor_row)
    feature_rows = dataset.build_feature_rows(canonical, source_bundle=source_bundle)
    source_report = sources.train_live_feature_parity_report(dataset.FEATURE_NAMES, source_bundle=source_bundle, feature_registry=dataset.feature_formula_registry()["features"])
    last_return = data.returns(canonical)[-1] if canonical else 0.0
    signal = "BUY" if last_return > 0 else "SELL" if last_return < 0 else "HOLD"
    # Determine gap-contamination action from actual gap metrics in the latest feature row
    latest_gap_ratio = float(feature_rows[-1].features.get("gap_ratio_20", 0.0)) if feature_rows else 0.0
    latest_max_gap_run = float(feature_rows[-1].features.get("max_gap_run_120", 0.0)) if feature_rows else 0.0
    gap_action = governance.fallback_action("gap_ratio_20", latest_gap_ratio)
    if gap_action == "allow":
        gap_action = governance.fallback_action("max_gap_run", latest_max_gap_run)
    # Use actual exchange adapter if provided (e.g., testnet), otherwise mock
    active_adapter = exchange_adapter or MockExchangeAdapter()
    entry_action = safe_market_entry(
        "BTCUSDT", signal, 0.001 if signal in {"BUY", "SELL"} else 0.0,
        adapter=active_adapter,
        gap_action=gap_action,
        monitor_decisions=monitor_decisions,
        allow_live_orders=not dry_run,
    )
    exit_action = gap_cross_exit(0.0, False, monitor_decisions=monitor_decisions)
    output.mkdir(parents=True, exist_ok=True)
    dataset.write_candles_csv(output / "live_candles.csv", canonical)
    monitoring.MonitoringReportWriter(output).write_all(
        [clock_monitor_row],
        [adl_monitor_row],
        [funding_monitor_row],
        [calibration_monitor_row],
    )
    summary: dict[str, object] = {
        "dry_run": dry_run,
        "network_used": not dry_run,
        "stream_desync_detected": desync_events > 0,
        "anomalies": anomalies,
        "backfilled_rows": sum(event["filled"] for event in backfill.events),
        "canonical_rows": len(canonical),
        "feature_rows": len(feature_rows),
        "source_hashes": dict(source_report.get("source_hashes", {})),
        "unavailable_sources": list(source_report.get("unavailable_sources", ())),
        "train_live_feature_parity_passed": bool(source_report.get("train_live_feature_parity_passed", False)),
        "signal": signal,
        "monitoring_actions": [str(row.get("action", "allow")) for row in monitor_decisions],
        "entry_action": entry_action,
        "exit_action": exit_action,
        "output": output.as_posix(),
    }
    (output / "live_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return LiveRunResult(output, summary, canonical, feature_rows, source_bundle)


def build_live_source_bundle(candles: Sequence[data.Candle], dry_run: bool = True) -> sources.MarketSourceBundle:
    source_name = "live_mock_source_bundle" if dry_run else "live_stream_source_bundle"
    return sources.bundle_from_candles(candles, source=source_name, include_mock_sources=dry_run)


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
