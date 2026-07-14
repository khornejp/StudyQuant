from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence


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


def strategy_reward_risk_decision(reward_risk: float | None, min_reward_risk: float, strategy_name: str = "") -> RiskDecision:
    if min_reward_risk < 0.0:
        raise ValueError("min_reward_risk must be non-negative")
    details = {"min_reward_risk": min_reward_risk, "strategy": strategy_name}
    if reward_risk is None:
        return RiskDecision("allow", True, "strategy reward/risk not supplied", "strategy", details=details)
    checked_reward_risk = float(reward_risk)
    details = {**details, "reward_risk": checked_reward_risk}
    if checked_reward_risk < min_reward_risk:
        return RiskDecision("block_new_entries", False, "strategy reward/risk below minimum", "strategy", "block_entries", 0.0, details)
    return RiskDecision("allow", True, "strategy reward/risk accepted", "strategy", details=details)


@dataclass(frozen=True)
class KellySizingConfig:
    """Kelly-criterion position sizing (Chan, Quantitative Trading 2ed, ch.6).

    Continuous Kelly: f* = m / s^2 where m and s^2 are the expected excess
    return and return variance measured over the SAME period — here the trade
    holding period. The edge from expected_edge() is per-trade, but the
    variance estimated from 1-minute bar returns is per-bar, so it must be
    scaled by holding_period_bars (variance grows linearly with horizon under
    the i.i.d. approximation) before dividing; skipping that scaling inflates
    f* by roughly the holding period in bars and pins the output to the cap.
    kelly_multiplier=0.5 is the Half-Kelly default: Chan's own study trades
    ~18.5% of growth rate for a ~43% smaller max drawdown and ~50% lower
    volatility, which is the sane default for a leveraged crypto account.

    The Kelly output is a LEVERAGE SUGGESTION, not a mandate: callers must cap
    it with RiskPolicy.max_leverage (max_leverage becomes the cap, the Kelly
    value the dynamic size below it). variance estimation on 1-minute bars is
    noisy, so variance_lookback_bars should cover at least several hours and
    the value should be re-estimated at recalc_interval_bars, not every bar.
    """

    kelly_multiplier: float = 0.5
    variance_lookback_bars: int = 1440
    holding_period_bars: int = 60
    recalc_interval_bars: int = 60
    variance_floor: float = 1e-10

    def __post_init__(self) -> None:
        if not 0.0 < self.kelly_multiplier <= 1.0:
            raise ValueError("kelly_multiplier must be in (0, 1]")
        if self.variance_lookback_bars <= 1:
            raise ValueError("variance_lookback_bars must be > 1")
        if self.holding_period_bars <= 0:
            raise ValueError("holding_period_bars must be positive")
        if self.recalc_interval_bars <= 0:
            raise ValueError("recalc_interval_bars must be positive")
        if self.variance_floor <= 0.0:
            raise ValueError("variance_floor must be positive")


def expected_edge(
    probability: float,
    tp_pct: float,
    sl_pct: float,
    round_trip_cost: float = 0.0,
) -> float:
    """Per-trade expected return for a binary TP/SL outcome, NET of costs.

    A win realizes tp_pct minus the round-trip cost; a loss realizes sl_pct
    PLUS that cost. Sizing on the gross barriers instead would size (and
    enter) trades the backtest then books at a loss: with tp=0.30%,
    sl=0.15% and a 0.08% round trip, gross break-even sits at p=0.333 while
    net break-even is p=0.511 -- an entire band of losing trades looks
    profitable to a cost-blind Kelly.

    Returns a negative edge (no bet) when the TP does not even cover the
    round trip, since such a trade cannot win after costs.
    """
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    if tp_pct < 0.0 or sl_pct < 0.0:
        raise ValueError("tp_pct and sl_pct must be non-negative")
    if round_trip_cost < 0.0:
        raise ValueError("round_trip_cost must be non-negative")
    net_win = tp_pct - round_trip_cost
    net_loss = sl_pct + round_trip_cost
    if net_win <= 0.0:
        return -net_loss
    return probability * net_win - (1.0 - probability) * net_loss


def return_variance(returns: Sequence[float], lookback: int | None = None) -> float:
    """Population variance of the trailing `lookback` BARS of returns.

    The lookback slice is taken BEFORE dropping non-finite entries, so the
    window always spans the intended trailing wall-clock bars; NaN/gap bars
    inside the window are skipped, not back-filled with older history.
    """
    values = list(returns)
    if lookback is not None and lookback > 0:
        values = values[-lookback:]
    values = [r for r in values if math.isfinite(r)]
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


def kelly_leverage(
    edge: float,
    variance: float,
    config: KellySizingConfig | None = None,
    max_leverage: float | None = None,
) -> float:
    """Fractional-Kelly leverage: kelly_multiplier * edge / variance, capped.

    `edge` and `variance` must be measured over the SAME period (both
    per-trade or both per-bar); mixing units inflates or deflates f* by the
    holding-period ratio. kelly_leverage_for_signal handles the scaling.

    Returns 0.0 when the edge is non-positive (no bet) or the variance is not
    meaningfully positive (cannot size without a variance estimate — refusing
    to trade is safer than dividing by a floor and returning a huge number).
    """
    cfg = config or KellySizingConfig()
    if edge <= 0.0:
        return 0.0
    if not math.isfinite(variance) or variance < cfg.variance_floor:
        return 0.0
    leverage = cfg.kelly_multiplier * edge / variance
    if max_leverage is not None:
        leverage = min(leverage, max_leverage)
    return max(0.0, leverage)


def kelly_leverage_for_signal(
    probability: float,
    tp_pct: float,
    sl_pct: float,
    recent_returns: Sequence[float],
    policy: RiskPolicy | None = None,
    config: KellySizingConfig | None = None,
    cap: float | None = None,
    round_trip_cost: float = 0.0,
) -> float:
    """End-to-end sizing: model probability + TP/SL geometry + recent variance.

    This is the SINGLE implementation of the probability + barriers + window
    -> fraction pipeline; backtest (kelly_fraction_for_entry) and live
    (PositionSizer.kelly_notional) both delegate here so their sizing can
    never drift apart. `recent_returns` are per-BAR returns; the per-bar
    variance is scaled by holding_period_bars so both Kelly inputs are
    per-trade quantities.

    `cap` overrides the default cap of RiskPolicy.max_leverage (the policy
    limit reinterpreted as the ceiling on the Kelly output); callers whose
    natural cap is an equity fraction or notional ratio pass it here.

    `round_trip_cost` is 2*(fee + slippage); pass the SAME value the
    execution layer charges so Kelly's entry filter agrees with realized PnL.
    """
    cfg = config or KellySizingConfig()
    if cap is None:
        cap = (policy or RiskPolicy()).max_leverage
    edge = expected_edge(probability, tp_pct, sl_pct, round_trip_cost)
    bar_variance = return_variance(recent_returns, cfg.variance_lookback_bars)
    trade_variance = bar_variance * cfg.holding_period_bars
    return kelly_leverage(edge, trade_variance, cfg, cap)


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
