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

from . import data, dataset, features, governance, models, monitoring, sources
from .exchange import MARKET, STOP_MARKET, TAKE_PROFIT_MARKET, ExchangeAdapter, ExchangeOrder, MockExchangeAdapter
from .risk import DrawdownProtocol, DrawdownState, RiskDecision, RiskPolicy, strategy_reward_risk_decision


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
        self.backoff_reset_time = 0.0
        self.hard_ban_active = False
        self._clock = clock

    def acquire(self, endpoint: str, weight: int) -> None:
        self._check_backoff_expired()
        if self.hard_ban_active:
            raise RateLimitHardBanActive(endpoint)
        if self.backoff_active:
            raise RateLimitBackoffActive(endpoint)
        if not self.normal_bucket.consume(weight):
            raise RateLimitBudgetExceeded(endpoint)

    def acquire_emergency(self, endpoint: str, weight: int) -> None:
        self._check_backoff_expired()
        if self.hard_ban_active:
            raise RateLimitHardBanActive(endpoint)
        if not self.emergency_bucket.consume(weight):
            raise RateLimitBudgetExceeded(endpoint)

    def observe_status(self, status_code: int, retry_after: float | None = None) -> str:
        if status_code == 418:
            self.hard_ban_active = True
            return "hard_kill"
        if status_code == 429:
            self.backoff_active = True
            if retry_after is not None and retry_after > 0:
                self.backoff_reset_time = self._clock() + retry_after
            else:
                self.backoff_reset_time = self._clock() + 60.0  # default 60s
            return "block_new_entries"
        return "allow"

    def _check_backoff_expired(self) -> None:
        if self.backoff_active and self._clock() >= self.backoff_reset_time:
            self.backoff_active = False
            self.backoff_reset_time = 0.0


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
STRATEGY_PROFILE_CHOICES = ("conservative", "balanced", "aggressive")


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    long_threshold: float
    short_threshold: float
    tp_pct: float
    sl_pct: float
    atr_multiplier_tp: float
    atr_multiplier_sl: float
    min_reward_risk: float
    # Minimum TP/SL as an absolute fraction of entry price. ATR-derived
    # deltas on BTCUSDT 1m are often ~0.05%, which is below the ~0.08%
    # round-trip cost, so a winning trade still loses money. These floors
    # clamp the ATR-based deltas up to a cost-aware minimum. Defaults are
    # set to 4x / 2x the default 0.08% round-trip cost. Setting either to
    # 0.0 disables that floor (legacy behavior).
    min_tp_floor_pct: float = 0.0032
    min_sl_floor_pct: float = 0.0016
    # When False, ATR-based sizing is disabled and TP/SL are taken exactly
    # from the floors (or tp_pct/sl_pct if floors are 0). This is used by the
    # TP/SL sweep so the backtest trades exactly the barrier the model was
    # labeled/trained against, rather than a larger ATR-derived barrier.
    use_atr_pricing: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.long_threshold <= 1.0:
            raise ValueError("long_threshold must be in [0, 1]")
        if not 0.0 <= self.short_threshold <= 1.0:
            raise ValueError("short_threshold must be in [0, 1]")
        if self.tp_pct <= 0.0 or self.sl_pct <= 0.0:
            raise ValueError("tp_pct and sl_pct must be positive")
        if self.atr_multiplier_tp <= 0.0 or self.atr_multiplier_sl <= 0.0:
            raise ValueError("ATR multipliers must be positive")
        if self.min_reward_risk < 0.0:
            raise ValueError("min_reward_risk must be non-negative")
        if self.min_tp_floor_pct < 0.0 or self.min_sl_floor_pct < 0.0:
            raise ValueError("TP/SL floors must be non-negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "long_threshold": self.long_threshold,
            "short_threshold": self.short_threshold,
            "tp_pct": self.tp_pct,
            "sl_pct": self.sl_pct,
            "atr_multiplier_tp": self.atr_multiplier_tp,
            "atr_multiplier_sl": self.atr_multiplier_sl,
            "min_reward_risk": self.min_reward_risk,
            "min_tp_floor_pct": self.min_tp_floor_pct,
            "min_sl_floor_pct": self.min_sl_floor_pct,
        }


@dataclass(frozen=True)
class RegimeStrategyProfile:
    regime: str
    strategy: StrategyConfig


# TP/SL design notes:
#   - min_tp_floor_pct / min_sl_floor_pct are cost-aware absolute floors
#     (default 0.32% / 0.16% = 4x / 2x the 0.08% round-trip cost).
#   - ATR multipliers are raised so that in higher-volatility periods the
#     ATR-derived delta can exceed the floor and adapt upward, while calm
#     periods fall back to the floor. On BTCUSDT 1m, atr_pct is often
#     ~0.03-0.06%, so multipliers in the 6-12 range put ATR deltas in the
#     same 0.2-0.7% neighborhood as the floors.
#   - TP:SL kept near 2:1 for a positive reward:risk baseline.
_BALANCED_DEFAULT_STRATEGY = StrategyConfig("balanced_default", 0.50, 0.50, 0.010, 0.005, 8.0, 4.0, 1.0, 0.0032, 0.0016)
_BALANCED_REGIME_STRATEGIES: dict[str, RegimeStrategyProfile] = {
    "high_volatility": RegimeStrategyProfile("high_volatility", StrategyConfig("balanced_high_volatility", 0.45, 0.55, 0.015, 0.010, 10.0, 6.0, 1.0, 0.0048, 0.0024)),
    "ranging": RegimeStrategyProfile("ranging", StrategyConfig("balanced_ranging", 0.52, 0.48, 0.008, 0.004, 6.0, 3.0, 1.0, 0.0024, 0.0012)),
    "trending": RegimeStrategyProfile("trending", StrategyConfig("balanced_trending", 0.48, 0.52, 0.010, 0.005, 8.0, 4.0, 1.0, 0.0032, 0.0016)),
}
DEFAULT_STRATEGY_PROFILES: Mapping[str, RegimeStrategyProfile] = _BALANCED_REGIME_STRATEGIES


def strategy_for_regime(
    active_regime: str | None,
    strategy_profile: str = "balanced",
    long_threshold_override: float | None = None,
    short_threshold_override: float | None = None,
) -> StrategyConfig:
    if strategy_profile not in STRATEGY_PROFILE_CHOICES:
        raise ValueError(f"unsupported strategy profile: {strategy_profile}")
    base = _BALANCED_REGIME_STRATEGIES.get(str(active_regime or "")).strategy if active_regime in _BALANCED_REGIME_STRATEGIES else _BALANCED_DEFAULT_STRATEGY
    if strategy_profile == "balanced":
        result = base
    elif strategy_profile == "conservative":
        result = StrategyConfig(
            f"conservative_{base.name}",
            min(0.95, base.long_threshold + 0.03),
            max(0.05, base.short_threshold - 0.03),
            base.tp_pct,
            base.sl_pct,
            base.atr_multiplier_tp,
            base.atr_multiplier_sl,
            max(base.min_reward_risk, 1.25),
            base.min_tp_floor_pct,
            base.min_sl_floor_pct,
            base.use_atr_pricing,
        )
    else:
        result = StrategyConfig(
            f"aggressive_{base.name}",
            max(0.05, base.long_threshold - 0.03),
            min(0.95, base.short_threshold + 0.03),
            base.tp_pct * 1.10,
            base.sl_pct * 1.10,
            base.atr_multiplier_tp * 1.10,
            base.atr_multiplier_sl * 1.10,
            min(base.min_reward_risk, 0.80),
            base.min_tp_floor_pct * 1.10,
            base.min_sl_floor_pct * 1.10,
            base.use_atr_pricing,
        )
    # Apply explicit CLI threshold overrides last so they win over the
    # profile-derived thresholds. Previously --long-threshold/--short-threshold
    # were parsed but never wired through, so user-supplied thresholds were
    # silently ignored in both live and backtest.
    if long_threshold_override is not None or short_threshold_override is not None:
        import dataclasses as _dc
        overrides: dict[str, float] = {}
        if long_threshold_override is not None:
            overrides["long_threshold"] = long_threshold_override
        if short_threshold_override is not None:
            overrides["short_threshold"] = short_threshold_override
        result = _dc.replace(result, **overrides)
    return result


def optimized_tp_sl(entry_price: float, side: str, features: Mapping[str, float], strategy: StrategyConfig) -> tuple[float, float, dict[str, object]]:
    if entry_price <= 0.0:
        raise ValueError("entry_price must be positive")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    atr_value = features.get("atr_pct")
    if getattr(strategy, "use_atr_pricing", True) and atr_value is not None and float(atr_value) > 0.0:
        tp_delta = strategy.atr_multiplier_tp * float(atr_value)
        sl_delta = strategy.atr_multiplier_sl * float(atr_value)
        pricing_method = "atr_pct"
    elif not getattr(strategy, "use_atr_pricing", True):
        # Fixed mode: take TP/SL exactly from the floors (fallback to tp_pct/
        # sl_pct if a floor is 0). Used by the sweep for label/backtest parity.
        tp_delta = strategy.min_tp_floor_pct if strategy.min_tp_floor_pct > 0.0 else strategy.tp_pct
        sl_delta = strategy.min_sl_floor_pct if strategy.min_sl_floor_pct > 0.0 else strategy.sl_pct
        pricing_method = "fixed_floor"
    else:
        tp_delta = strategy.tp_pct
        sl_delta = strategy.sl_pct
        pricing_method = "fixed_pct"
    # Cost-aware floor: ATR-derived deltas on BTCUSDT 1m are frequently below
    # the round-trip trading cost, which makes even winning trades unprofitable.
    # Clamp both deltas up to their configured minimum so TP/SL are always a
    # meaningful multiple of cost. This keeps ATR's adaptivity in high-vol
    # periods while preventing degenerate sub-cost barriers in calm periods.
    floored = False
    if strategy.min_tp_floor_pct > 0.0 and tp_delta < strategy.min_tp_floor_pct:
        tp_delta = strategy.min_tp_floor_pct
        floored = True
    if strategy.min_sl_floor_pct > 0.0 and sl_delta < strategy.min_sl_floor_pct:
        sl_delta = strategy.min_sl_floor_pct
        floored = True
    if side == "BUY":
        tp_price = entry_price * (1.0 + tp_delta)
        sl_price = entry_price * (1.0 - sl_delta)
    else:
        tp_price = entry_price * (1.0 - tp_delta)
        sl_price = entry_price * (1.0 + sl_delta)
    reward_risk = tp_delta / sl_delta if sl_delta > 0.0 else 0.0
    decision = {
        "strategy": strategy.as_dict(),
        "side": side,
        "entry_price": entry_price,
        "tp_delta": tp_delta,
        "sl_delta": sl_delta,
        "take_profit_price": tp_price,
        "stop_loss_price": sl_price,
        "reward_risk": reward_risk,
        "pricing_method": pricing_method,
        "floor_applied": floored,
    }
    return tp_price, sl_price, decision


def select_signal(probability: float, active_regime: str, strategy: StrategyConfig, reward_risk: float | None = None) -> str:
    risk_decision = strategy_reward_risk_decision(reward_risk, strategy.min_reward_risk, strategy.name)
    if not risk_decision.allowed:
        return "HOLD"
    if probability > strategy.long_threshold:
        return "BUY"
    if probability < strategy.short_threshold:
        return "SELL"
    return "HOLD"


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
    strategy_reward_risk: float | None = None,
    strategy_min_reward_risk: float | None = None,
    strategy_name: str = "",
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
        strategy_reward_risk=strategy_reward_risk,
        strategy_min_reward_risk=strategy_min_reward_risk,
        strategy_name=strategy_name,
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
    tp_order: ExchangeOrder | None = None
    try:
        tp_order = exchange_adapter.submit_order(
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
        sl_order = exchange_adapter.submit_order(
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
        return tp_order, sl_order
    except Exception as submit_error:
        # If SL (or TP) fails, cancel the already-submitted TP to avoid leaving
        # an open position with only one protective order.
        if tp_order is not None:
            cancel_order = getattr(exchange_adapter, "cancel_order", None)
            if callable(cancel_order):
                try:
                    cancel_order(symbol, order_id=tp_order.order_id, client_order_id=tp_order.client_order_id)
                except Exception as cancel_error:
                    raise submit_error from cancel_error
        raise


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
    strategy_reward_risk: float | None,
    strategy_min_reward_risk: float | None,
    strategy_name: str,
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
        strategy_reward_risk,
        strategy_min_reward_risk,
        strategy_name,
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
    strategy_reward_risk: float | None,
    strategy_min_reward_risk: float | None,
    strategy_name: str,
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
    if strategy_min_reward_risk is not None:
        decisions.append(strategy_reward_risk_decision(strategy_reward_risk, strategy_min_reward_risk, strategy_name))
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
    metrics_path: Path | None = None
    alerts_path: Path | None = None
    health_path: Path | None = None


@dataclass(frozen=True)
class MarketEvent:
    candle: data.Candle
    sequence: int = 0


@dataclass(frozen=True)
class GapEvent:
    detection: GapDetection
    repaired_candles: tuple[data.Candle, ...] = ()


@dataclass(frozen=True)
class FeatureEvent:
    canonical: tuple[data.Candle, ...]
    feature_rows: tuple[dataset.FeatureRow, ...]
    source_bundle: sources.MarketSourceBundle
    external_sources: Mapping[str, object] = field(default_factory=dict)
    source_report: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalEvent:
    signal: str
    model_inference: Mapping[str, object]
    feature_row: dataset.FeatureRow | None = None


@dataclass(frozen=True)
class OrderEvent:
    action: str
    orders: tuple[ExchangeOrder, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MonitoringEvent:
    action: str
    row: Mapping[str, object]
    source: str = ""


EventHandler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: Any) -> None:
        event_type = type(event).__name__
        for handler in list(self._handlers.get(event_type, [])):
            handler(event)


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
            websocket = __import__("websocket")
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


def load_model_artifact(path: Path | None, strict: bool = False) -> models.ModelAdapter | None:
    if path is None:
        return None
    if not path.exists():
        if strict:
            raise FileNotFoundError(f"model artifact not found: {path}")
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        if strict:
            raise ValueError(f"model artifact is not a JSON object: {path}")
        return None
    model_family = str(payload.get("model_family", ""))
    try:
        if model_family == "lightgbm":
            return models.LightGBMAdapter.from_dict(payload)
        if model_family == "catboost":
            return models.CatBoostAdapter.from_dict(payload)
        if model_family == "ensemble":
            return models.EnsembleAdapter.from_dict(payload)
        if model_family == "stacking_ensemble":
            from . import ensemble
            return ensemble.StackingEnsembleAdapter.from_dict(payload)
        if model_family == "pytorch_multitask":
            from . import multitask_nn
            return multitask_nn.MultitaskNNAdapter.from_dict(payload)
        if strict:
            raise ValueError(f"unsupported model_family: {model_family}")
        return None
    except ValueError as error:
        if strict:
            raise ValueError(f"model artifact validation failed: {error}") from error
        return None


@dataclass(frozen=True)
class RegimeModelBundle:
    models: dict[str, models.ModelAdapter]
    long_models: dict[str, models.ModelAdapter]
    short_models: dict[str, models.ModelAdapter]
    detector_thresholds: dict[str, float]
    detector_config: features.RegimeDetectorConfig
    detector_diagnostics: Mapping[str, object]
    default_regime: str | None = None
    direction_policy: dict[str, set[str]] | None = None  # regime -> {"LONG"}, {"SHORT"}, {"LONG", "SHORT"}, set()


def load_regime_aware_models(path: Path | None, strict: bool = False) -> RegimeModelBundle | None:
    """Load regime-aware models from a directory containing regime_run_summary.json."""
    if path is None:
        return None
    if not path.exists():
        if strict:
            raise FileNotFoundError(f"regime model directory not found: {path}")
        return None
    summary_path = path / "regime_run_summary.json"
    if not summary_path.exists():
        if strict:
            raise FileNotFoundError(f"regime_run_summary.json not found in {path}")
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    regime_results = summary.get("regime_results", {})
    default_regime = summary.get("default_regime")
    regime_detector = summary.get("regime_detector", {})
    detector_thresholds = _coerce_float_mapping(regime_detector.get("thresholds", {}) if isinstance(regime_detector, Mapping) else {})
    detector_config = _coerce_regime_detector_config(regime_detector.get("config", {}) if isinstance(regime_detector, Mapping) else {})
    detector_diagnostics = regime_detector.get("diagnostics", {}) if isinstance(regime_detector, Mapping) else {}
    if not detector_thresholds:
        detector_thresholds = features.RegimeDetector(detector_config).fit_thresholds((), ())
    loaded_models: dict[str, models.ModelAdapter] = {}
    long_models: dict[str, models.ModelAdapter] = {}
    short_models: dict[str, models.ModelAdapter] = {}
    direction_policy: dict[str, set[str]] = {}
    
    # Support both old (model.json) and new (long_model.json + short_model.json) structures
    for regime_name in list(regime_results.keys()):
        regime_dir = path / f"regime_{regime_name}"
        regime_directions: set[str] = set()
        
        # Try new structure: long_model.json + short_model.json (may have only one)
        long_path = regime_dir / "long_model.json"
        short_path = regime_dir / "short_model.json"
        
        if long_path.exists():
            long_model = load_model_artifact(long_path, strict=strict)
            if long_model is not None:
                long_models[regime_name] = long_model
                loaded_models[regime_name] = long_model
                regime_directions.add("LONG")
        
        if short_path.exists():
            short_model = load_model_artifact(short_path, strict=strict)
            if short_model is not None:
                short_models[regime_name] = short_model
                # Only set as default model if long wasn't loaded
                if regime_name not in loaded_models:
                    loaded_models[regime_name] = short_model
                regime_directions.add("SHORT")
        
        # Fallback to old structure: model.json
        if not regime_directions:
            model_path = regime_dir / "model.json"
            if model_path.exists():
                model = load_model_artifact(model_path, strict=strict)
                if model is not None:
                    loaded_models[regime_name] = model
                    # Old structure defaults to both directions
                    regime_directions = {"LONG", "SHORT"}
        
        if regime_directions:
            direction_policy[regime_name] = regime_directions
    
    if not loaded_models:
        return None
    diagnostics_mapping: Mapping[str, object] = detector_diagnostics if isinstance(detector_diagnostics, Mapping) else {}
    return RegimeModelBundle(
        models=loaded_models,
        long_models=long_models,
        short_models=short_models,
        detector_thresholds=detector_thresholds,
        detector_config=detector_config,
        detector_diagnostics=diagnostics_mapping,
        default_regime=str(default_regime) if isinstance(default_regime, str) else None,
        direction_policy=direction_policy,
    )


def _coerce_float_mapping(payload: object) -> dict[str, float]:
    if not isinstance(payload, Mapping):
        return {}
    values: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (float, int, str)):
            values[str(key)] = float(value)
    return values


def _coerce_regime_detector_config(payload: object) -> features.RegimeDetectorConfig:
    if not isinstance(payload, Mapping):
        return features.RegimeDetectorConfig()
    defaults = features.RegimeDetectorConfig()
    return features.RegimeDetectorConfig(
        rv_percentile=float(payload.get("rv_percentile", defaults.rv_percentile)),
        trend_percentile=float(payload.get("trend_percentile", defaults.trend_percentile)),
        min_trend_abs=float(payload.get("min_trend_abs", defaults.min_trend_abs)),
        high_vol_priority=bool(payload.get("high_vol_priority", defaults.high_vol_priority)),
        low_vol_trend_multiplier=float(payload.get("low_vol_trend_multiplier", defaults.low_vol_trend_multiplier)),
        min_regime_run_bars=int(payload.get("min_regime_run_bars", defaults.min_regime_run_bars)),
    )


def apply_range_mean_reversion_gate(regime: str, features: dict[str, float], allowed_directions: set[str]) -> set[str]:
    """Apply mean-reversion direction gate for the range regime."""
    if regime != "range":
        return allowed_directions

    range_pos = features.get("range_position_20", 0.5)
    if range_pos < 0.25:
        return {"LONG"}
    if range_pos > 0.75:
        return {"SHORT"}
    return set()


# EV (Expected Value) calculation for LONG/SHORT entry decisions
EV_COST_CONFIG = {
    "fee_entry": 0.0002,      # 0.02% Binance taker fee
    "fee_exit": 0.0002,       # 0.02% Binance taker fee
    "slippage": 0.0001,       # 0.01% estimated slippage
    "spread_cost": 0.0001,    # 0.01% estimated spread cost
    "safety_margin": 0.0002,  # 0.02% safety margin
}


def calculate_net_tp_sl(
    gross_tp_pct: float,
    gross_sl_pct: float,
    cost_config: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Calculate net TP/SL after costs."""
    config = cost_config or EV_COST_CONFIG
    total_cost = config["fee_entry"] + config["fee_exit"] + config["slippage"] + config["spread_cost"]
    net_tp = gross_tp_pct - total_cost
    net_sl = -gross_sl_pct - total_cost  # SL is negative, subtract costs
    return net_tp, net_sl


def calculate_long_ev(
    long_prob: float,
    gross_tp_pct: float = 0.0015,
    gross_sl_pct: float = 0.0010,
    cost_config: dict[str, float] | None = None,
) -> float:
    """Calculate Expected Value for LONG entry."""
    net_tp, net_sl = calculate_net_tp_sl(gross_tp_pct, gross_sl_pct, cost_config)
    return long_prob * net_tp + (1.0 - long_prob) * net_sl


def calculate_short_ev(
    short_prob: float,
    gross_tp_pct: float = 0.0015,
    gross_sl_pct: float = 0.0010,
    cost_config: dict[str, float] | None = None,
) -> float:
    """Calculate Expected Value for SHORT entry."""
    net_tp, net_sl = calculate_net_tp_sl(gross_tp_pct, gross_sl_pct, cost_config)
    return short_prob * net_tp + (1.0 - short_prob) * net_sl


def evaluate_entry_signal(
    long_prob: float,
    short_prob: float,
    min_ev: float = 0.0001,
    long_threshold: float = 0.55,
    short_threshold: float = 0.55,
    gross_tp_pct: float = 0.0015,
    gross_sl_pct: float = 0.0010,
    cost_config: dict[str, float] | None = None,
) -> tuple[str, float, float]:
    """Evaluate entry signal based on EV calculation.
    
    Returns:
        (signal, long_ev, short_ev) where signal is "LONG", "SHORT", or "NO_TRADE"
    """
    long_ev = calculate_long_ev(long_prob, gross_tp_pct, gross_sl_pct, cost_config)
    short_ev = calculate_short_ev(short_prob, gross_tp_pct, gross_sl_pct, cost_config)
    
    if long_ev > min_ev and long_prob > long_threshold:
        return "LONG", long_ev, short_ev
    elif short_ev > min_ev and short_prob > short_threshold:
        return "SHORT", long_ev, short_ev
    else:
        return "NO_TRADE", long_ev, short_ev


class LiveEngine:
    def __init__(
        self,
        output: Path,
        dry_run: bool = True,
        allow_public_network: bool = False,
        max_candles: int = 12,
        idle_timeout_seconds: float = 0.2,
        exchange_adapter: ExchangeAdapter | None = None,
        custom_candles: Sequence[data.Candle] | None = None,
        model_artifact_path: Path | None = None,
        source_parity_passed: bool | None = None,
        regime_aware: bool = False,
        strategy_profile: str = "balanced",
        soak_duration_hours: float = 0.0,
        soak_report_interval_minutes: float = 60.0,
        long_threshold_override: float | None = None,
        short_threshold_override: float | None = None,
    ) -> None:
        if strategy_profile not in STRATEGY_PROFILE_CHOICES:
            raise ValueError(f"unsupported strategy profile: {strategy_profile}")
        self.output = output
        self.dry_run = dry_run
        self.allow_public_network = allow_public_network
        self.max_candles = max_candles
        self.idle_timeout_seconds = idle_timeout_seconds
        self.exchange_adapter = exchange_adapter
        self.custom_candles = custom_candles
        self.model_artifact_path = model_artifact_path
        self.source_parity_passed = source_parity_passed
        self.regime_aware = regime_aware
        self.strategy_profile = strategy_profile
        self.long_threshold_override = long_threshold_override
        self.short_threshold_override = short_threshold_override
        self.soak_duration_hours = soak_duration_hours
        self.soak_report_interval_minutes = soak_report_interval_minutes
        self.bus = EventBus()
        self._register_default_handlers()
        self._reset_run_state()

    def _register_default_handlers(self) -> None:
        self.bus.subscribe("MarketEvent", self._handle_market_event)
        self.bus.subscribe("FeatureEvent", self._handle_feature_event)
        self.bus.subscribe("SignalEvent", self._handle_signal_event)
        self.bus.subscribe("MarketEvent", self._monitor_market_event)
        self.bus.subscribe("GapEvent", self._monitor_gap_event)
        self.bus.subscribe("SignalEvent", self._monitor_signal_event)
        self.bus.subscribe("OrderEvent", self._monitor_order_event)
        self.bus.subscribe("MonitoringEvent", self._monitor_monitoring_event)

    def _reset_run_state(self) -> None:
        self.client: WebSocketClient | None = None
        self.backfill: RESTBackfill | None = None
        self.detector = StreamGapDetector()
        self.anomalies: list[str] = []
        self.desync_events = 0
        self.source_errors: dict[str, str] = {}
        self.order_errors: list[str] = []
        self.active_adapter = self.exchange_adapter or MockExchangeAdapter()
        self.drawdown_state = self._initial_drawdown_state()
        self.canonical: list[data.Candle] = []
        self.source_bundle: sources.MarketSourceBundle | None = None
        self.clock_monitor_row: Mapping[str, object] = {}
        self.adl_monitor_row: Mapping[str, object] = {}
        self.funding_monitor_row: Mapping[str, object] = {}
        self.calibration_monitor_row: Mapping[str, object] = {}
        self.monitor_decisions: tuple[Mapping[str, object], ...] = ()
        self.external_sources: dict[str, object] = {}
        self.feature_rows: list[dataset.FeatureRow] = []
        self.source_report: Mapping[str, object] = {}
        self.signal = "HOLD"
        self.model_inference: dict[str, object] = {"probability": None, "signal": "HOLD", "model_loaded": False}
        self.strategy_config = strategy_for_regime(None, self.strategy_profile, self.long_threshold_override, self.short_threshold_override)
        self.strategy_decision: dict[str, object] = {"profile": self.strategy_profile, "strategy": self.strategy_config.as_dict(), "signal": "HOLD"}
        self.bracket_pricing: dict[str, object] | None = None
        self.gap_action = "allow"
        self.soak_start_time: datetime | None = None
        self.soak_last_report_time: datetime | None = None
        self.entry_action = "allow"
        self.exit_action = "allow"
        self.bracket_orders: tuple[ExchangeOrder, ExchangeOrder, ExchangeOrder] | None = None
        self.bracket_error: str | None = None
        self.emergency_close_order: ExchangeOrder | None = None
        self.metrics_registry = monitoring.MetricsRegistry()
        self.alert_manager = monitoring.AlertManager.with_builtin_rules()
        self.active_alerts: list[dict[str, str]] = []
        self.health_status = monitoring.health_from_alerts(())
        self.metrics_path = self.output / "metrics.json"
        self.alerts_path = self.output / "alerts.json"
        self.health_path = self.output / "health.json"
        self._last_regime: object = None
        self.summary: dict[str, object] = {}

    def _initial_drawdown_state(self) -> DrawdownState:
        try:
            initial_account = self.active_adapter.get_account()
            initial_equity = initial_account.available_balance
        except Exception as account_error:
            self.source_errors["initial_account"] = str(account_error)
            initial_equity = 0.0
        return DrawdownState(peak_equity=initial_equity, current_equity=initial_equity)

    def run(self) -> LiveRunResult:
        if not self.dry_run and not self.allow_public_network:
            raise RuntimeError("live mode without --dry-run requires --allow-public-network")
        self._reset_run_state()
        self.soak_start_time = datetime.now(timezone.utc)
        self.soak_last_report_time = self.soak_start_time
        self.client, self.backfill = self._build_stream_components()
        self.client.start()
        try:
            processed = 0
            soak_mode = self.soak_duration_hours > 0
            max_candles = float("inf") if soak_mode else self.max_candles
            while processed < max_candles:
                # Check soak duration termination
                if soak_mode and self.soak_start_time is not None:
                    elapsed_hours = (datetime.now(timezone.utc) - self.soak_start_time).total_seconds() / 3600.0
                    if elapsed_hours >= self.soak_duration_hours:
                        print(f"Soak test completed: {elapsed_hours:.2f} hours elapsed (limit: {self.soak_duration_hours:.2f})")
                        break
                    # Periodic soak report
                    if self.soak_last_report_time is not None:
                        report_interval_hours = self.soak_report_interval_minutes / 60.0
                        time_since_report = (datetime.now(timezone.utc) - self.soak_last_report_time).total_seconds() / 3600.0
                        if time_since_report >= report_interval_hours:
                            self._write_soak_report(processed, elapsed_hours)
                            self.soak_last_report_time = datetime.now(timezone.utc)
                candle = self.client.next_candle(timeout=self.idle_timeout_seconds)
                if candle is None:
                    if isinstance(self.client, MockWebSocketClient) and self.client.is_finished():
                        break
                    self._handle_idle_timeout()
                    continue
                self.bus.publish(MarketEvent(candle=candle, sequence=processed + 1))
                processed += 1
        finally:
            self.client.close()

        self._finalize_after_stream()
        self._write_outputs()
        if self.source_bundle is None:
            raise RuntimeError("live source bundle was not built")
        return LiveRunResult(
            self.output,
            self.summary,
            self.canonical,
            self.feature_rows,
            self.source_bundle,
            self.metrics_path,
            self.alerts_path,
            self.health_path,
        )

    def _build_stream_components(self) -> tuple[WebSocketClient, RESTBackfill]:
        if self.custom_candles is not None:
            fixture = list(self.custom_candles)
            stream_fixture = fixture[: self.max_candles]
            client: WebSocketClient = MockWebSocketClient(stream_fixture)
            fixture_by_time = {candle.open_time: candle for candle in fixture}
            backfill = RESTBackfill(fetcher=lambda open_times: [fixture_by_time[open_time] for open_time in open_times if open_time in fixture_by_time])
        elif self.dry_run:
            fixture = _live_fixture(max(self.max_candles + 4, 12))
            omitted = {5, 6, 9}
            stream_fixture = [candle for index, candle in enumerate(fixture[: self.max_candles]) if index not in omitted]
            client = MockWebSocketClient(stream_fixture)
            fixture_by_time = {candle.open_time: candle for candle in fixture}
            backfill = RESTBackfill(fetcher=lambda open_times: [fixture_by_time[open_time] for open_time in open_times if open_time in fixture_by_time])
        else:
            client = WebSocketClient(allow_network=True)
            backfill = RESTBackfill(allow_network=True)
        return client, backfill

    def _handle_idle_timeout(self) -> None:
        timeout_detection = self.detector.check_timeout(datetime.now(timezone.utc))
        if timeout_detection.stream_desync_detected:
            self.desync_events += 1
            if timeout_detection.anomaly is not None:
                self.anomalies.append(timeout_detection.anomaly)
            self.bus.publish(GapEvent(timeout_detection))

    def _handle_market_event(self, event: Any) -> None:
        if not isinstance(event, MarketEvent):
            raise TypeError("MarketEvent handler received unexpected event")
        detection = self.detector.observe(event.candle)
        if detection.stream_desync_detected:
            self.desync_events += 1
            if detection.anomaly is not None:
                self.anomalies.append(detection.anomaly)
            repaired_candles = self._backfill().backfill_missing(detection.missing_open_times)
            for repaired in repaired_candles:
                self._client().add_candle(repaired)
            self.bus.publish(GapEvent(detection, tuple(repaired_candles)))
        self._update_drawdown(event.candle)

    def _update_drawdown(self, candle: data.Candle) -> None:
        try:
            current_account = self.active_adapter.get_account()
            current_equity = current_account.available_balance
        except Exception as account_error:
            self.source_errors["drawdown_account"] = str(account_error)
            current_equity = candle.close
        self.drawdown_state = self.drawdown_state.update(current_equity)

    def _finalize_after_stream(self) -> None:
        self.canonical = data.CanonicalTimelineBuilder().build(self._client().buffer_snapshot())
        self.source_bundle = build_live_source_bundle(self.canonical, dry_run=self.dry_run)
        self.clock_monitor_row = monitoring.ClockDriftService().evaluate()
        self.adl_monitor_row = monitoring.ADLMonitorService().evaluate(self.source_bundle.adl_quantile)
        self.funding_monitor_row = monitoring.FundingMonitorService().evaluate(self.source_bundle.funding_rate)
        self.calibration_monitor_row = monitoring.CalibrationDriftMonitor().evaluate([], [])
        self.monitor_decisions = (self.clock_monitor_row, self.adl_monitor_row, self.funding_monitor_row, self.calibration_monitor_row)
        for source, row in (
            ("clock", self.clock_monitor_row),
            ("adl", self.adl_monitor_row),
            ("funding", self.funding_monitor_row),
            ("calibration", self.calibration_monitor_row),
        ):
            self.bus.publish(MonitoringEvent(str(row.get("action", "allow")), row, source))
        self.external_sources = self._fetch_external_sources()
        self.feature_rows = dataset.build_feature_rows(self.canonical, source_bundle=self.source_bundle, external_sources=self.external_sources)
        self.source_report = sources.train_live_feature_parity_report(
            dataset.FEATURE_NAMES,
            source_bundle=self.source_bundle,
            feature_registry=dataset.feature_formula_registry()["features"],
            external_sources=self.external_sources,
        )
        self.bus.publish(
            FeatureEvent(
                canonical=tuple(self.canonical),
                feature_rows=tuple(self.feature_rows),
                source_bundle=self.source_bundle,
                external_sources=self.external_sources,
                source_report=self.source_report,
            )
        )

    def _fetch_external_sources(self) -> dict[str, object]:
        external_sources: dict[str, object] = {}
        try:
            depth = self.active_adapter.get_depth("BTCUSDT")
            external_sources["depth_snapshot"] = {
                "best_bid": depth.best_bid,
                "best_ask": depth.best_ask,
                "bid_qty": depth.bid_qty,
                "ask_qty": depth.ask_qty,
                "microprice": depth.microprice,
            }
        except Exception as source_error:
            self.source_errors["depth_snapshot"] = str(source_error)
        try:
            funding = self.active_adapter.get_funding_rate("BTCUSDT")
            external_sources["funding_rate"] = {
                "current_rate": funding.current_rate,
                "next_rate": funding.next_rate,
                "minutes_to_next": funding.minutes_to_next,
            }
        except Exception as source_error:
            self.source_errors["funding_rate"] = str(source_error)
        try:
            adl = self.active_adapter.get_adl_quantile("BTCUSDT")
            external_sources["adl_quantile"] = {"adl_quantile": adl.adl_quantile}
        except Exception as source_error:
            self.source_errors["adl_quantile"] = str(source_error)
        try:
            mark = self.active_adapter.get_mark_price("BTCUSDT")
            external_sources["mark_price_1m"] = {
                "mark_price": mark.mark_price,
                "premium_index": mark.premium_index,
            }
        except Exception as source_error:
            self.source_errors["mark_price_1m"] = str(source_error)
        return external_sources

    def _handle_feature_event(self, event: Any) -> None:
        if not isinstance(event, FeatureEvent):
            raise TypeError("FeatureEvent handler received unexpected event")
        self.canonical = list(event.canonical)
        self.feature_rows = list(event.feature_rows)
        self.source_bundle = event.source_bundle
        self.external_sources = dict(event.external_sources)
        self.source_report = event.source_report
        self._compute_signal()
        latest_row = self.feature_rows[-1] if self.feature_rows else None
        self.bus.publish(SignalEvent(self.signal, self.model_inference, latest_row))

    def _apply_strategy_decision(self, probability: float | None, active_regime: str | None, fallback_signal: str) -> str:
        strategy = strategy_for_regime(active_regime, self.strategy_profile, self.long_threshold_override, self.short_threshold_override)
        threshold_signal = select_signal(probability, active_regime or "", strategy) if probability is not None else fallback_signal
        latest_features = self.feature_rows[-1].features if self.feature_rows else {}
        entry_price = self.canonical[-1].close if self.canonical else 0.0
        reward_risk: float | None = None
        pricing: dict[str, object] | None = None
        if threshold_signal in {"BUY", "SELL"} and entry_price > 0.0:
            _, _, pricing = optimized_tp_sl(entry_price, threshold_signal, latest_features, strategy)
            reward_risk = float(pricing["reward_risk"])
        risk_decision = strategy_reward_risk_decision(reward_risk, strategy.min_reward_risk, strategy.name)
        if probability is not None:
            selected_signal = select_signal(probability, active_regime or "", strategy, reward_risk)
        else:
            selected_signal = threshold_signal if risk_decision.allowed else "HOLD"
        self.strategy_config = strategy
        self.bracket_pricing = pricing
        self.strategy_decision = {
            "profile": self.strategy_profile,
            "active_regime": active_regime,
            "strategy": strategy.as_dict(),
            "probability": probability,
            "threshold_signal": threshold_signal,
            "signal": selected_signal,
            "reward_risk": reward_risk,
            "min_reward_risk": strategy.min_reward_risk,
            "risk_gate_action": risk_decision.action,
            "risk_gate_allowed": risk_decision.allowed,
            "risk_gate_reason": risk_decision.reason,
            "pricing_method": pricing.get("pricing_method") if pricing else None,
        }
        return selected_signal

    def _compute_signal(self) -> None:
        strict_artifact = self.model_artifact_path is not None
        active_regime: str | None = None
        fallback_regime: str | None = None
        
        if self.regime_aware and self.model_artifact_path is not None:
            regime_bundle = load_regime_aware_models(self.model_artifact_path, strict=strict_artifact)
            if regime_bundle is not None and self.feature_rows:
                latest_features = self.feature_rows[-1].features
                latest_row = self.feature_rows[-1]
                
                # Priority 1: Use user_regime from feature row if available
                if hasattr(latest_row, 'user_regime') and latest_row.user_regime is not None:
                    active_regime = latest_row.user_regime
                else:
                    # Priority 2: Fall back to automatic regime detection.
                    # Use DIRECTIONAL detection (up/down/range) so the regime
                    # matches the trained model keys. The base detect() returns
                    # trending/ranging/high_volatility, which never match the
                    # up/down/range models and would silently disable routing.
                    rv_15 = float(latest_features.get("rv_15", 0.0))
                    trend_slope_30 = float(latest_features.get("trend_slope_30", 0.0))
                    detector_config = regime_bundle.detector_config
                    if isinstance(detector_config, dict):
                        detector_config = features.RegimeDetectorConfig(**detector_config)
                    detector = features.RegimeDetector(detector_config)
                    # Calibrate the directional threshold from the trend-slope
                    # history available so far (all buffered feature rows).
                    hist_slopes = [
                        float(r.features.get("trend_slope_30", 0.0))
                        for r in self.feature_rows
                    ]
                    dir_thresholds = detector.fit_directional_threshold(hist_slopes) if hist_slopes else None
                    active_regime = detector.detect_directional(
                        trend_slope_30,
                        thresholds=dir_thresholds,
                        historical_trend_slope_30_values=hist_slopes if not dir_thresholds else None,
                    )
                
                # Get direction policy for this regime
                allowed_directions = regime_bundle.direction_policy.get(active_regime, {"LONG", "SHORT"})
                allowed_directions = apply_range_mean_reversion_gate(active_regime, latest_features, allowed_directions)
                if not allowed_directions:
                    self.signal = "HOLD"
                    self.model_inference = {
                        "probability": None,
                        "signal": self.signal,
                        "model_loaded": True,
                        "regime": active_regime,
                        "fallback_regime": fallback_regime,
                        "allowed_directions": [],
                        "gate_reason": "range_middle",
                    }
                    return
                
                # Get probabilities from available models
                long_prob = None
                short_prob = None
                
                if "LONG" in allowed_directions and active_regime in regime_bundle.long_models:
                    try:
                        long_prob = regime_bundle.long_models[active_regime].probability(latest_features)
                    except Exception:
                        pass
                
                if "SHORT" in allowed_directions and active_regime in regime_bundle.short_models:
                    try:
                        short_prob = regime_bundle.short_models[active_regime].probability(latest_features)
                    except Exception:
                        pass
                
                # Use evaluate_entry_signal if we have at least one probability
                if long_prob is not None or short_prob is not None:
                    long_prob = long_prob if long_prob is not None else 0.0
                    short_prob = short_prob if short_prob is not None else 0.0
                    
                    signal, long_ev, short_ev = evaluate_entry_signal(
                        long_prob, short_prob,
                        min_ev=self.strategy_config.min_ev if hasattr(self.strategy_config, 'min_ev') else 0.0001,
                        long_threshold=self.strategy_config.long_threshold,
                        short_threshold=self.strategy_config.short_threshold,
                    )
                    
                    # Convert to BUY/SELL/HOLD
                    if signal == "LONG":
                        self.signal = "BUY"
                    elif signal == "SHORT":
                        self.signal = "SELL"
                    else:
                        self.signal = "HOLD"
                    
                    self.model_inference = {
                        "probability": max(long_prob, short_prob),
                        "long_prob": long_prob,
                        "short_prob": short_prob,
                        "long_ev": long_ev,
                        "short_ev": short_ev,
                        "signal": self.signal,
                        "model_loaded": True,
                        "regime": active_regime,
                        "fallback_regime": fallback_regime,
                        "allowed_directions": list(allowed_directions),
                    }
                else:
                    # Fall back to default model if available
                    model = regime_bundle.models.get(active_regime)
                    if model is None and regime_bundle.default_regime is not None:
                        model = regime_bundle.models.get(regime_bundle.default_regime)
                        if model is not None:
                            fallback_regime = regime_bundle.default_regime
                    
                    if model is not None:
                        probability = model.probability(latest_features)
                        self.signal = self._apply_strategy_decision(probability, active_regime, "HOLD")
                        self.model_inference = {"probability": probability, "signal": self.signal, "model_loaded": True, "regime": active_regime, "fallback_regime": fallback_regime}
                    else:
                        self.signal = "HOLD"
                        self.model_inference = {"probability": None, "signal": self.signal, "model_loaded": False, "regime": active_regime, "fallback_regime": fallback_regime}
            else:
                self.signal = "HOLD"
                self.model_inference = {"probability": None, "signal": self.signal, "model_loaded": False}
        else:
            model = load_model_artifact(self.model_artifact_path, strict=strict_artifact)
            if model is not None and self.feature_rows:
                latest_features = self.feature_rows[-1].features
                try:
                    probability = model.probability(latest_features)
                    self.signal = self._apply_strategy_decision(probability, active_regime, "HOLD")
                    self.model_inference = {"probability": probability, "signal": self.signal, "model_loaded": True, "regime": active_regime, "fallback_regime": fallback_regime}
                except Exception as inference_error:
                    self.signal = "HOLD"
                    self._apply_strategy_decision(None, active_regime, "HOLD")
                    self.model_inference = {"probability": None, "signal": self.signal, "model_loaded": True, "error": str(inference_error), "regime": active_regime, "fallback_regime": fallback_regime}
            else:
                last_return = data.returns(self.canonical)[-1] if self.canonical else 0.0
                fallback_signal = "BUY" if last_return > 0 else "SELL" if last_return < 0 else "HOLD"
                self.signal = self._apply_strategy_decision(None, active_regime, fallback_signal)
                self.model_inference = {"probability": None, "signal": self.signal, "model_loaded": False, "fallback": "last_return", "regime": active_regime, "fallback_regime": None}
        
        latest_gap_ratio = float(self.feature_rows[-1].features.get("gap_ratio_20", 0.0)) if self.feature_rows else 0.0
        latest_max_gap_run = float(self.feature_rows[-1].features.get("max_gap_run_120", 0.0)) if self.feature_rows else 0.0
        self.gap_action = governance.fallback_action("gap_ratio_20", latest_gap_ratio)
        if self.gap_action == "allow":
            self.gap_action = governance.fallback_action("max_gap_run", latest_max_gap_run)

    def _handle_signal_event(self, event: Any) -> None:
        if not isinstance(event, SignalEvent):
            raise TypeError("SignalEvent handler received unexpected event")
        self.signal = event.signal
        parity_passed = self.source_parity_passed if self.source_parity_passed is not None else bool(self.source_report.get("train_live_feature_parity_passed", False))
        position = self.active_adapter.get_position("BTCUSDT")
        account = self.active_adapter.get_account()
        entry_quantity = 0.001 if self.signal in {"BUY", "SELL"} else 0.0
        entry_price_for_notional = self.canonical[-1].close if self.canonical else 0.0
        entry_notional = entry_quantity * entry_price_for_notional
        self.entry_action = str(
            safe_market_entry(
                position,
                self.signal,
                entry_quantity,
                adapter=self.active_adapter,
                source_parity_passed=parity_passed,
                gap_action=self.gap_action,
                account_balance_usdt=account.available_balance,
                leverage=position.leverage,
                notional=entry_notional,
                drawdown_state=self.drawdown_state,
                monitor_decisions=self.monitor_decisions,
                allow_live_orders=not self.dry_run,
                submit=not self.dry_run and self.signal in {"BUY", "SELL"},
                strategy_reward_risk=float(self.strategy_decision["reward_risk"]) if self.strategy_decision.get("reward_risk") is not None else None,
                strategy_min_reward_risk=self.strategy_config.min_reward_risk,
                strategy_name=self.strategy_config.name,
            )
        )
        self._submit_brackets_if_needed(entry_quantity)
        self.exit_action = str(gap_cross_exit(0.0, False, monitor_decisions=self.monitor_decisions))
        orders: list[ExchangeOrder] = []
        if self.bracket_orders is not None:
            orders.extend(self.bracket_orders)
        if self.emergency_close_order is not None:
            orders.append(self.emergency_close_order)
        self.bus.publish(OrderEvent(self.entry_action, tuple(orders), {"exit_action": self.exit_action, "bracket_error": self.bracket_error or ""}))

    def _monitor_market_event(self, event: Any) -> None:
        if not isinstance(event, MarketEvent):
            raise TypeError("MarketEvent monitor received unexpected event")
        self.metrics_registry.increment("candles_processed")
        self._evaluate_monitoring_alerts()

    def _monitor_gap_event(self, event: Any) -> None:
        if not isinstance(event, GapEvent):
            raise TypeError("GapEvent monitor received unexpected event")
        self.metrics_registry.increment("gap_events")
        self._evaluate_monitoring_alerts()

    def _monitor_signal_event(self, event: Any) -> None:
        if not isinstance(event, SignalEvent):
            raise TypeError("SignalEvent monitor received unexpected event")
        probability = event.model_inference.get("probability")
        self.metrics_registry.set("current_probability", probability)
        regime = event.model_inference.get("regime")
        self.metrics_registry.set("current_regime", regime)
        if regime not in (None, "") and self._last_regime not in (None, "") and regime != self._last_regime:
            self.metrics_registry.increment("regime_transitions")
        if regime not in (None, ""):
            self._last_regime = regime
        if "error" in event.model_inference:
            self.metrics_registry.increment("model_inference_errors")
        latest_gap_ratio = 0.0
        if event.feature_row is not None:
            latest_gap_ratio = float(event.feature_row.features.get("gap_ratio_20", 0.0))
        self.metrics_registry.set("latest_gap_ratio", latest_gap_ratio)
        if self.source_report:
            self.metrics_registry.set("train_live_feature_parity_passed", bool(self.source_report.get("train_live_feature_parity_passed", False)))
        self._evaluate_monitoring_alerts()

    def _monitor_order_event(self, event: Any) -> None:
        if not isinstance(event, OrderEvent):
            raise TypeError("OrderEvent monitor received unexpected event")
        self.metrics_registry.increment("orders_submitted")
        self._evaluate_monitoring_alerts()

    def _monitor_monitoring_event(self, event: Any) -> None:
        if not isinstance(event, MonitoringEvent):
            raise TypeError("MonitoringEvent monitor received unexpected event")
        self.metrics_registry.increment("monitoring_actions")
        self.metrics_registry.set("latest_monitoring_action", event.action)
        if "clock_drift_ms" in event.row:
            self.metrics_registry.set("clock_drift_ms", event.row["clock_drift_ms"])
        self._evaluate_monitoring_alerts()

    def _evaluate_monitoring_alerts(self) -> None:
        snapshot = self.metrics_registry.snapshot()
        self.active_alerts = self.alert_manager.evaluate(snapshot)
        self.health_status = monitoring.health_from_alerts(self.active_alerts)

    def _submit_brackets_if_needed(self, entry_quantity: float) -> None:
        if self.entry_action != "market_entry_submitted" or self.signal not in {"BUY", "SELL"}:
            return
        try:
            entry_price = self.canonical[-1].close if self.canonical else 0.0
            if entry_price <= 0.0:
                recent_market_orders = [
                    order for order in getattr(self.active_adapter, "orders", ())
                    if order.symbol == "BTCUSDT" and order.side == self.signal and order.order_type == MARKET
                ]
                if recent_market_orders:
                    entry_price = float(getattr(recent_market_orders[-1], "avg_fill_price", 0.0) or getattr(recent_market_orders[-1], "price", 0.0) or 0.0)
            if entry_price > 0.0:
                latest_features = self.feature_rows[-1].features if self.feature_rows else {}
                tp_price, sl_price, pricing = optimized_tp_sl(entry_price, self.signal, latest_features, self.strategy_config)
                self.bracket_pricing = pricing
                tp_order, sl_order = submit_take_profit_stop_loss(
                    adapter=self.active_adapter,
                    symbol="BTCUSDT",
                    position_side=self.signal,
                    quantity=entry_quantity,
                    take_profit_price=round(tp_price, 2),
                    stop_loss_price=round(sl_price, 2),
                    allow_live_orders=not self.dry_run,
                )
                entry_orders = [
                    order for order in getattr(self.active_adapter, "orders", ())
                    if order.symbol == "BTCUSDT" and order.side == self.signal and order.order_type == MARKET
                ]
                entry_order = entry_orders[-1] if entry_orders else ExchangeOrder("BTCUSDT", self.signal, MARKET, entry_quantity)
                self.bracket_orders = (entry_order, tp_order, sl_order)
            else:
                self.bracket_error = "bracket_pricing_failed: no valid entry_price from canonical or adapter"
                self.entry_action = "hard_kill"
        except Exception as bracket_exc:
            self.bracket_error = str(bracket_exc)
            self.entry_action = "hard_kill"
            try:
                emergency_exit_side = "SELL" if self.signal == "BUY" else "BUY"
                self.emergency_close_order = self.active_adapter.submit_order(
                    "BTCUSDT",
                    emergency_exit_side,
                    MARKET,
                    entry_quantity,
                    reduce_only=True,
                    client_order_id=f"emergency_close_{int(monotonic())}",
                )
            except Exception as emergency_error:
                self.order_errors.append(f"emergency_close_failed: {emergency_error}")

    def _write_outputs(self) -> None:
        if self.source_bundle is None:
            raise RuntimeError("live source bundle was not built")
        self.output.mkdir(parents=True, exist_ok=True)
        dataset.write_candles_csv(self.output / "live_candles.csv", self.canonical)
        monitoring.MonitoringReportWriter(self.output).write_all(
            [self.clock_monitor_row],
            [self.adl_monitor_row],
            [self.funding_monitor_row],
            [self.calibration_monitor_row],
        )
        self._evaluate_monitoring_alerts()
        self.metrics_path.write_text(json.dumps(self.metrics_registry.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.alerts_path.write_text(json.dumps(self.active_alerts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.health_path.write_text(json.dumps(self.health_status.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.summary = {
            "dry_run": self.dry_run,
            "network_used": not self.dry_run,
            "stream_desync_detected": self.desync_events > 0,
            "anomalies": self.anomalies,
            "backfilled_rows": sum(event["filled"] for event in self._backfill().events),
            "canonical_rows": len(self.canonical),
            "feature_rows": len(self.feature_rows),
            "source_hashes": dict(self.source_report.get("source_hashes", {})),
            "unavailable_sources": list(self.source_report.get("unavailable_sources", ())),
            "train_live_feature_parity_passed": bool(self.source_report.get("train_live_feature_parity_passed", False)),
            "signal": self.signal,
            "model_inference": self.model_inference,
            "strategy_decision": self.strategy_decision,
            "bracket_pricing": self.bracket_pricing,
            "monitoring_actions": [str(row.get("action", "allow")) for row in self.monitor_decisions],
            "metrics_path": self.metrics_path.as_posix(),
            "alerts_path": self.alerts_path.as_posix(),
            "health_path": self.health_path.as_posix(),
            "health": self.health_status.as_dict(),
            "active_alerts": self.active_alerts,
            "entry_action": self.entry_action,
            "exit_action": self.exit_action,
            "bracket_orders": {
                "entry_order_id": self.bracket_orders[0].order_id if self.bracket_orders else None,
                "tp_order_id": self.bracket_orders[1].order_id if self.bracket_orders else None,
                "sl_order_id": self.bracket_orders[2].order_id if self.bracket_orders else None,
            } if self.bracket_orders else None,
            "bracket_error": self.bracket_error,
            "emergency_close_order_id": self.emergency_close_order.order_id if self.emergency_close_order else None,
            "drawdown_state": {
                "peak_equity": self.drawdown_state.peak_equity,
                "current_equity": self.drawdown_state.current_equity,
                "max_drawdown": self.drawdown_state.max_drawdown,
                "tier": self.drawdown_state.tier,
            },
            "output": self.output.as_posix(),
        }
        (self.output / "live_summary.json").write_text(json.dumps(self.summary, indent=2, sort_keys=True), encoding="utf-8")

    def _write_soak_report(self, candles_processed: int, elapsed_hours: float) -> None:
        if self.soak_start_time is None:
            return
        report = {
            "soak_start_time": self.soak_start_time.isoformat(),
            "report_time": datetime.now(timezone.utc).isoformat(),
            "elapsed_hours": round(elapsed_hours, 2),
            "soak_duration_hours": self.soak_duration_hours,
            "candles_processed": candles_processed,
            "candles_per_hour": round(candles_processed / max(elapsed_hours, 0.001), 2),
            "metrics": self.metrics_registry.snapshot(),
            "health": self.health_status.as_dict(),
            "drawdown": {
                "peak_equity": self.drawdown_state.peak_equity,
                "current_equity": self.drawdown_state.current_equity,
                "max_drawdown": self.drawdown_state.max_drawdown,
                "tier": self.drawdown_state.tier,
            },
            "anomalies": self.anomalies,
            "desync_events": self.desync_events,
            "order_errors": self.order_errors,
        }
        soak_path = self.output / f"soak_report_{int(elapsed_hours):04d}h.json"
        soak_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Soak report written: {soak_path} ({elapsed_hours:.2f}h, {candles_processed} candles)")

    def _client(self) -> WebSocketClient:
        if self.client is None:
            raise RuntimeError("live client is not initialized")
        return self.client

    def _backfill(self) -> RESTBackfill:
        if self.backfill is None:
            raise RuntimeError("live backfill is not initialized")
        return self.backfill


def run_live(
    output: Path,
    dry_run: bool = True,
    allow_public_network: bool = False,
    max_candles: int = 12,
    idle_timeout_seconds: float = 0.2,
    exchange_adapter: ExchangeAdapter | None = None,
    custom_candles: Sequence[data.Candle] | None = None,
    model_artifact_path: Path | None = None,
    source_parity_passed: bool | None = None,
    regime_aware: bool = False,
    strategy_profile: str = "balanced",
    soak_duration_hours: float = 0.0,
    soak_report_interval_minutes: float = 60.0,
    long_threshold_override: float | None = None,
    short_threshold_override: float | None = None,
) -> LiveRunResult:
    return LiveEngine(
        output,
        dry_run=dry_run,
        allow_public_network=allow_public_network,
        max_candles=max_candles,
        idle_timeout_seconds=idle_timeout_seconds,
        exchange_adapter=exchange_adapter,
        custom_candles=custom_candles,
        model_artifact_path=model_artifact_path,
        source_parity_passed=source_parity_passed,
        regime_aware=regime_aware,
        strategy_profile=strategy_profile,
        soak_duration_hours=soak_duration_hours,
        soak_report_interval_minutes=soak_report_interval_minutes,
        long_threshold_override=long_threshold_override,
        short_threshold_override=short_threshold_override,
    ).run()


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
