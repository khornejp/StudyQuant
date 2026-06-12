from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import floor
from time import monotonic
from typing import Sequence


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
