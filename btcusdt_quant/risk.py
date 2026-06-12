from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping


@dataclass(frozen=True)
class RiskPolicy:
    max_leverage: float = 1.0
    max_notional_fraction: float = 0.10
    max_drawdown_warning: float = 0.05
    max_drawdown_reduce: float = 0.08
    max_drawdown_hard_kill: float = 0.12
    funding_blackout_minutes: int = 5
    adl_action_thresholds: Mapping[int, str] = field(default_factory=lambda: {3: "reduce_size", 4: "block_new_entries"})
    clock_drift_thresholds: Mapping[int, str] = field(default_factory=lambda: {500: "block_new_entries", 1000: "hard_kill"})

    def __post_init__(self) -> None:
        if self.max_leverage <= 0.0:
            raise ValueError("max_leverage must be positive")
        if not 0.0 < self.max_notional_fraction <= 1.0:
            raise ValueError("max_notional_fraction must be in (0, 1]")
        if not 0.0 <= self.max_drawdown_warning <= self.max_drawdown_reduce <= self.max_drawdown_hard_kill:
            raise ValueError("drawdown thresholds must be ordered")
        if self.funding_blackout_minutes < 0:
            raise ValueError("funding_blackout_minutes must be non-negative")

    @property
    def max_drawdown_block_entries(self) -> float:
        if self.max_drawdown_hard_kill <= self.max_drawdown_reduce:
            return self.max_drawdown_hard_kill
        return self.max_drawdown_reduce + (self.max_drawdown_hard_kill - self.max_drawdown_reduce) / 2.0


@dataclass(frozen=True)
class DrawdownState:
    peak_equity: float
    current_equity: float
    max_drawdown: float = 0.0
    tier: str = "allow"
    action: str = "allow"

    @property
    def drawdown(self) -> float:
        if self.peak_equity <= 0.0:
            return 0.0
        return max(0.0, (self.peak_equity - self.current_equity) / self.peak_equity)

    def update(self, current_equity: float) -> "DrawdownState":
        peak = max(self.peak_equity, current_equity)
        drawdown = 0.0 if peak <= 0.0 else max(0.0, (peak - current_equity) / peak)
        return replace(self, peak_equity=peak, current_equity=current_equity, max_drawdown=max(self.max_drawdown, drawdown))


@dataclass(frozen=True)
class RiskDecision:
    action: str
    allowed: bool
    reason: str
    gate: str = ""
    tier: str = "allow"
    reduce_factor: float = 1.0
    details: Mapping[str, object] = field(default_factory=dict)


class DrawdownProtocol:
    """Tiered live drawdown fallback: warn -> reduce_size -> block_entries -> hard_kill."""

    def __init__(self, policy: RiskPolicy | None = None, reduce_factor: float = 0.5) -> None:
        if not 0.0 < reduce_factor <= 1.0:
            raise ValueError("reduce_factor must be in (0, 1]")
        self.policy = policy or RiskPolicy()
        self.reduce_factor = reduce_factor

    def evaluate(self, state: DrawdownState) -> RiskDecision:
        drawdown = max(state.drawdown, state.max_drawdown)
        details = {"drawdown": drawdown, "peak_equity": state.peak_equity, "current_equity": state.current_equity}
        if drawdown >= self.policy.max_drawdown_hard_kill:
            return RiskDecision("hard_kill", False, "drawdown hard kill threshold breached", "drawdown", "hard_kill", 0.0, details)
        if drawdown >= self.policy.max_drawdown_block_entries:
            return RiskDecision("block_entries", False, "drawdown block entries threshold breached", "drawdown", "block_entries", 0.0, details)
        if drawdown >= self.policy.max_drawdown_reduce:
            return RiskDecision("reduce_size", True, "drawdown reduce threshold breached", "drawdown", "reduce_size", self.reduce_factor, details)
        if drawdown >= self.policy.max_drawdown_warning:
            return RiskDecision("warn", True, "drawdown warning threshold breached", "drawdown", "warn", 1.0, details)
        return RiskDecision("allow", True, "drawdown policy passed", "drawdown", "allow", 1.0, details)

    def update_and_evaluate(self, state: DrawdownState, current_equity: float) -> tuple[DrawdownState, RiskDecision]:
        updated = state.update(current_equity)
        decision = self.evaluate(updated)
        return replace(updated, tier=decision.tier, action=decision.action), decision
