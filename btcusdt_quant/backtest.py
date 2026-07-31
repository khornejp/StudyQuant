from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping, Sequence

from . import data, dataset, live, risk


def _parse_end_exclusive(value: str):
    """Parse an end-date string into an EXCLUSIVE UTC datetime bound.

    A date-only value ("2025-12-31") means "include that whole day", so it
    becomes 2026-01-01 00:00 exclusive. A value with a time component is used
    as-is (exclusive). Interpreting date-only ends inclusively at 00:00 would
    silently drop all but the first minute of the final day (1,439 of 1,440
    bars on 1m data)."""
    from datetime import datetime as _dt, timedelta as _td
    dt = _dt.fromisoformat(value).replace(tzinfo=timezone.utc)
    if "T" not in value and " " not in value and len(value) == 10:
        dt = dt + _td(days=1)
    return dt


def window_bounds(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    """(inclusive start, EXCLUSIVE end) as UTC datetimes, or None where unbounded.

    The one place the backtest window is turned into bounds. Any other consumer
    that needs "the same rows this backtest evaluated" -- verify_calibration.py
    grading the model on the backtest window, for one -- must slice identically,
    and an off-by-one-day copy of this would put the two reports on different
    samples while both claimed the same window.
    """
    start = None
    end = None
    if start_date is not None:
        from datetime import datetime as _dt
        start = _dt.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    if end_date is not None:
        end = _parse_end_exclusive(end_date)
    return start, end


def apply_multi_feature_routing(
    feature_rows: "Sequence[dataset.FeatureRow]",
    detector,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Run the rule detector ONCE over the full series and return
    (routed_rows, diagnostics). routed_rows carry user_regime; diagnostics are
    sliced to [start_date, end_date]. Lets the CLI route once and share the
    result across compare_strategies and run_backtest instead of each call
    re-running detect_all over ~3.15M rows."""
    import dataclasses as _dc
    detected = detector.detect_all([r.features for r in feature_rows])
    if start_date is not None or end_date is not None:
        _s, _e = window_bounds(start_date, end_date)
        window = [
            regime for row, regime in zip(feature_rows, detected)
            if (_s is None or row.open_time >= _s) and (_e is None or row.open_time < _e)
        ]
    else:
        window = detected
    diag = detector.diagnostics(window)
    routed = [
        _dc.replace(row, user_regime=regime)
        for row, regime in zip(feature_rows, detected)
    ]
    return routed, diag


def _resolve_backtest_thresholds(regime_bundle, regime, long_threshold, short_threshold, strategy, threshold_floor: float = 0.0):
    """Resolve (long, short) entry thresholds with the SAME precedence live uses:
    explicit CLI override > learned per-regime holdout threshold
    (regime_bundle.regime_thresholds[regime], the selected_thresholds saved at
    train time) > the static strategy profile threshold. Previously the backtest
    ignored the learned per-regime thresholds, so its decisions diverged from
    live's.

    threshold_floor: a hard lower bound applied to the learned/strategy value
    (NOT to an explicit CLI override, which the user set deliberately). Learned
    thresholds can select very low (~0.32) on weak models; the floor keeps
    entries above a minimum confidence so sub-cost signals don't flood in."""
    learned = {}
    rt = getattr(regime_bundle, "regime_thresholds", None)
    if isinstance(rt, Mapping):
        learned = rt.get(regime, {}) or {}
    lt = long_threshold if long_threshold is not None else max(float(learned.get("long", strategy.long_threshold)), threshold_floor)
    st = short_threshold if short_threshold is not None else max(float(learned.get("short", strategy.short_threshold)), threshold_floor)
    return lt, st


def apply_exec_barrier(
    strategy: live.StrategyConfig,
    exec_tp_pct: float | None,
    exec_sl_pct: float | None,
) -> live.StrategyConfig:
    """Fold the EXECUTION barrier into a strategy profile, or return it unchanged.

    Aligns execution with the model's LABEL barrier: fixed (non-ATR) TP/SL equal
    to the triple-barrier tp_pct/sl_pct the model was trained on. Without it the
    backtest executed ATR-derived barriers (~0.84%/0.42%) while the model was
    predicting a +0.30%/-0.15% outcome.

    Shared with the profile-degeneracy check, which has to fold the barrier
    EXACTLY as the backtest does -- a second copy that drifted would report two
    profiles as distinguishable while the backtest executed them identically.
    """
    if exec_tp_pct is None or exec_sl_pct is None:
        return strategy
    import dataclasses as _dc
    return _dc.replace(
        strategy,
        tp_pct=exec_tp_pct,
        sl_pct=exec_sl_pct,
        min_tp_floor_pct=exec_tp_pct,
        min_sl_floor_pct=exec_sl_pct,
        use_atr_pricing=False,
    )


def _execution_fingerprint(
    strategy: live.StrategyConfig,
    models_by_regime: Mapping[str, object] | None,
    default_regime: str | None,
    long_threshold: float | None,
    short_threshold: float | None,
    threshold_floor: float,
) -> tuple:
    """Everything about a profile that can still change a trading decision.

    A StrategyConfig has more fields than the backtest reads. min_reward_risk is
    never consulted here (it is a live-only gate), and the ATR multipliers stop
    mattering the moment use_atr_pricing is False. What is left -- the barrier
    and the entry thresholds -- is exactly what exec_tp/sl_pct and the learned
    per-regime thresholds override. Two profiles with the same fingerprint will
    produce byte-identical trades, so comparing them is not a comparison.
    """
    barrier = (
        strategy.tp_pct,
        strategy.sl_pct,
        strategy.min_tp_floor_pct,
        strategy.min_sl_floor_pct,
        strategy.use_atr_pricing,
        # Only reachable while ATR pricing is on; folded in so a profile that
        # differs ONLY in its multipliers is still seen as different when it is.
        strategy.atr_multiplier_tp if strategy.use_atr_pricing else None,
        strategy.atr_multiplier_sl if strategy.use_atr_pricing else None,
    )
    if not models_by_regime:
        # Single-model (or no-model) run: the profile's own thresholds are the
        # gate unless the CLI overrode them.
        thresholds = (
            long_threshold if long_threshold is not None else strategy.long_threshold,
            short_threshold if short_threshold is not None else strategy.short_threshold,
        )
        return barrier + thresholds
    regimes = sorted({*models_by_regime, *(() if default_regime is None else (default_regime,))})
    resolved = tuple(
        _resolve_backtest_thresholds(
            models_by_regime.get(regime), regime, long_threshold, short_threshold, strategy, threshold_floor
        )
        for regime in regimes
    )
    return barrier + resolved


def indistinguishable_profiles(
    strategies: Mapping[str, object],
    models_by_regime: Mapping[str, object] | None = None,
    default_regime: str | None = None,
    exec_tp_pct: float | None = None,
    exec_sl_pct: float | None = None,
    long_threshold: float | None = None,
    short_threshold: float | None = None,
    threshold_floor: float = 0.0,
) -> str | None:
    """Reason the profiles cannot differ in this run, or None if they can.

    aggressive/balanced/conservative differ in exactly three knobs: the entry
    thresholds, tp_pct, and min_reward_risk. In a regime-aware run with
    --exec-tp-pct/--exec-sl-pct, the barrier is overridden by the exec flags and
    the thresholds by the learned per-regime values, while min_reward_risk was
    never read here at all -- so all three profiles execute the same trades and
    the "comparison" reported three identical rows to four decimal places, with
    a best_strategy picked out of a tie.

    Reported instead of silently running three identical backtests: a comparison
    that cannot distinguish its arms is not a weak result, it is not a result.
    """
    if len(strategies) < 2:
        return None
    fingerprints = {
        name: _execution_fingerprint(
            apply_exec_barrier(strategy, exec_tp_pct, exec_sl_pct),
            models_by_regime,
            default_regime,
            long_threshold,
            short_threshold,
            threshold_floor,
        )
        for name, strategy in strategies.items()
    }
    if len(set(fingerprints.values())) > 1:
        return None
    causes = []
    if exec_tp_pct is not None and exec_sl_pct is not None:
        causes.append("the TP/SL barrier is fixed by --exec-tp-pct/--exec-sl-pct")
    if long_threshold is not None or short_threshold is not None:
        causes.append("the entry thresholds are fixed by explicit CLI overrides")
    elif models_by_regime:
        causes.append("the entry thresholds come from the artifact's learned per-regime values")
    reason = " and ".join(causes) if causes else "the profiles resolve to the same barrier and thresholds"
    return (
        f"strategy profiles {sorted(strategies)} resolve to identical execution: {reason}, "
        f"and min_reward_risk (their only other difference) is not read by the backtest. "
        f"Nothing distinguishes them, so no comparison was run."
    )


# Trade-return dispersion at or below this is float noise, not risk (see
# per_trade_sharpe), and the sample size below which per-trade Sharpe and
# profit factor are reported as NaN instead of a number. A 2-trade run has no
# risk metric worth printing; the pipeline was printing one anyway.
MIN_RETURN_STD = 1e-12
MIN_TRADES_FOR_RISK_METRICS = 20

# Executed vs labeled barrier are equal within this; they come from the same
# CLI fractions round-tripped through JSON, so only float repr noise separates
# a true match from an exact one.
_BARRIER_MATCH_TOL = 1e-9

# Bitget USDT-M perpetual, VIP0, no discount and no maker rebate -- the real
# trading account (confirmed 2026-07-30): maker 0.0200%, taker 0.0600%. The two
# are NOT the same number, and the difference decides whether a thin edge lives:
# a taker round trip is 12bps of fee alone. Until 2026-07-30 this module had a
# single DEFAULT_FEE_RATE_PER_SIDE = 0.0002 applied to both sides, i.e. it
# charged the MAKER rate for TAKER fills and under-counted every taker round trip
# by 8bps. Re-tier these two constants (and only these) if the account moves.
# (exchange.py speaks Binance USD-M -- the live path is on hold and its adapter
# has not been re-pointed. Costs follow the account, not the adapter.)
DEFAULT_MAKER_FEE_RATE_PER_SIDE = 0.0002
DEFAULT_TAKER_FEE_RATE_PER_SIDE = 0.0006
# `fee_rate_per_side` throughout this module means the TAKER rate: it is what an
# immediate fill pays, and the exit is modeled taker on every path. The maker
# rate applies only to a resting-limit ENTRY (see _close_trade).
DEFAULT_FEE_RATE_PER_SIDE = DEFAULT_TAKER_FEE_RATE_PER_SIDE
DEFAULT_SLIPPAGE_RATE_PER_SIDE = 0.0002
# Every way a trade can close. Which of these rest as limit orders decides the
# exit fee, and they are NOT interchangeable: TP is a limit that someone crosses
# (maker), SL is a stop that crosses the book to get you out (taker), TIMEOUT is
# a horizon market-close unless you deliberately rest a limit as the horizon
# approaches, and OPEN_AT_END is the harness flattening at the window edge.
EXIT_OUTCOMES = frozenset({"TP", "SL", "TIMEOUT", "OPEN_AT_END"})
# Where a stopped-out trade fills. Not two strictnesses of one model -- two
# different orders (exchange-resident stop vs bot-side stop), so this has to
# match what live would actually place. See run_backtest's sl_fill.
SL_FILL_MODES = frozenset({"barrier", "next_open"})
# Taker in, taker out -- the default execution. 2*(6+2) = 16bps. Training's
# --round-trip-cost must equal this or threshold selection optimizes against a
# cost the backtest does not charge (test_cost_basis_is_shared pins it).
DEFAULT_ROUND_TRIP_COST_PCT = 2.0 * (DEFAULT_FEE_RATE_PER_SIDE + DEFAULT_SLIPPAGE_RATE_PER_SIDE)


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


@dataclass
class BacktestTrade:
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    tp_price: float
    sl_price: float
    pnl_pct: float
    outcome: str
    strategy: str
    gross_pnl_pct: float = 0.0
    fee_pct: float = 0.0
    slippage_pct: float = 0.0
    cost_pct: float = 0.0
    fee_paid: float = 0.0
    slippage_paid: float = 0.0
    cost_paid: float = 0.0
    # Entry-decision context for per-regime / per-side loss attribution:
    # which regime routed this trade, both model probabilities at entry, and
    # the threshold the entered side actually had to clear.
    entry_regime: str | None = None
    long_probability: float | None = None
    short_probability: float | None = None
    used_threshold: float | None = None
    model_side: str | None = None          # "long" | "short"
    entry_probability: float | None = None  # probability of the ENTERED side
    # Equity fraction this trade was actually sized at. None means the
    # backtest's constant position_size was used (Kelly sizing off).
    position_size_used: float | None = None
    # Return ON EQUITY: pnl_pct scaled by the fraction actually bet. With a
    # constant size these are pnl_pct * position_size and the constant
    # cancels in Sharpe; with Kelly they are what the account actually
    # earned, and are what the risk metrics must be computed on.
    trade_return_pct: float = 0.0
    gross_trade_return_pct: float = 0.0
    # True when the entry was a resting limit (maker) fill: entry side pays no
    # fee/slippage (see _close_trade), and the fill only happened because a
    # later bar's price came back to the signal-bar close -- so the trade
    # population is adversely selected (the bars that ran away are the missed
    # ones counted in maker_fill_diagnostics.unfilled).
    entry_maker: bool = False


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    total_return: float = 0.0
    gross_total_return: float = 0.0
    # Simple per-trade means in notional bps -- see the note in as_dict for why
    # these are NOT gross_total_return / trade_count.
    mean_gross_bps_per_trade: float = 0.0
    mean_net_bps_per_trade: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    # Cost-free counterpart of `sharpe`, computed on gross equity returns. Reported
    # side by side with the net value because per-side costs can flip the
    # sign of a high-turnover strategy's Sharpe (Chan ch.3: 5bps per side
    # turned a 0.42 Sharpe into -3.38) -- the gap between the two is the
    # cost drag, and a strategy that only works gross must not ship.
    gross_sharpe: float = 0.0
    # Sample-size floor under which sharpe/gross_sharpe/profit_factor above are
    # NaN. Reported so a consumer reading a NaN knows it is a sample-size veto
    # and not a failed run.
    risk_metrics_min_trades: int = MIN_TRADES_FOR_RISK_METRICS
    trade_count: int = 0
    signal_counts: dict[str, int] = field(default_factory=dict)
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE
    maker_fee_rate_per_side: float = DEFAULT_MAKER_FEE_RATE_PER_SIDE
    slippage_rate_per_side: float = DEFAULT_SLIPPAGE_RATE_PER_SIDE
    round_trip_cost_pct: float = DEFAULT_ROUND_TRIP_COST_PCT
    total_fees: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0
    min_hold_bars: int = 0
    cooldown_bars: int = 0
    # Regime coverage diagnostics: how many evaluated bars had an explicit
    # user_regime vs. fell back to default_regime (because they lay outside
    # every configured regime period). A high fallback share means the
    # regime file does not cover the backtest window, so direction routing is
    # effectively single-regime.
    regime_coverage: dict[str, int] = field(default_factory=dict)
    # Rule-detector regime routing stats (counts/ratios/transitions/durations)
    # so they land in backtest_summary.json for data-driven tuning, not just logs.
    regime_routing_diagnostics: dict[str, object] = field(default_factory=dict)
    # Threshold provenance: the floor applied, and per-regime learned vs
    # effective (post floor/override) entry thresholds actually used, so the
    # summary disambiguates artifact selected_thresholds from what traded.
    threshold_floor: float = 0.0
    effective_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)
    # Kelly sizing diagnostics (empty dict when Kelly sizing is off): the
    # config used, how many entries were skipped for lack of edge, and the
    # distribution of per-trade fractions actually bet.
    kelly_sizing: dict[str, object] = field(default_factory=dict)
    # Run provenance: everything a second run must match for its numbers to be
    # comparable to this one. Without these in the artifact, a head-to-head
    # tool can only diff the metrics and cannot tell whether the two runs even
    # traded the same window with the same barriers and sizing.
    run_config: dict[str, object] = field(default_factory=dict)
    # regime -> sides the direction policy asks for but the loaded artifact
    # cannot serve. A missing side never emits a signal, so no skip counter
    # sees it: without this the run is silently one-directional in that regime.
    missing_side_models: dict[str, list[str]] = field(default_factory=dict)
    # Non-fatal findings from check_execution_barrier_parity: a legacy artifact
    # that cannot prove its barrier, or an allow_barrier_mismatch sweep. Empty
    # on a clean run; a genuine unapproved mismatch raises instead of landing
    # here.
    barrier_warnings: list[str] = field(default_factory=list)
    # Maker limit-fill accounting (empty when maker_fill_window == 0, i.e. the
    # default instant taker fill). placed/filled/unfilled let a reader see the
    # fill rate and how many signals were lost to unfilled limits -- the
    # missed trades that erode a maker strategy's edge.
    maker_fill_diagnostics: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "total_return": self.total_return,
            "net_total_return": self.total_return,
            "gross_total_return": self.gross_total_return,
            "cost_impact_return": self.gross_total_return - self.total_return,
            # Per-trade expectancy as a SIMPLE mean over trades, in notional
            # bps. Deliberately published next to the *_total_return figures
            # because dividing those by trade_count gives a DIFFERENT number:
            # trade PnL compounds on a growing equity, so an equity-weighted
            # per-trade average runs above the simple mean whenever the run is
            # profitable (measured ~12% higher on the 30m maker run: 8.20 vs
            # 7.34 bps). Costs are a per-trade CONSTANT, so an expectancy-vs-
            # cost comparison has to use the simple mean or it mixes bases --
            # which is how a break-even estimate ends up flattering.
            "mean_gross_bps_per_trade": self.mean_gross_bps_per_trade,
            "mean_net_bps_per_trade": self.mean_net_bps_per_trade,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "net_sharpe": self.sharpe,
            "gross_sharpe": self.gross_sharpe,
            "cost_impact_sharpe": self.gross_sharpe - self.sharpe,
            "risk_metrics_min_trades": self.risk_metrics_min_trades,
            "trade_count": len(self.trades),
            "signal_counts": self.signal_counts,
            "fee_rate_per_side": self.fee_rate_per_side,
            "maker_fee_rate_per_side": self.maker_fee_rate_per_side,
            "slippage_rate_per_side": self.slippage_rate_per_side,
            "round_trip_cost_pct": self.round_trip_cost_pct,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "total_costs": self.total_costs,
            "min_hold_bars": self.min_hold_bars,
            "cooldown_bars": self.cooldown_bars,
            "regime_coverage": self.regime_coverage,
            "regime_routing_diagnostics": self.regime_routing_diagnostics,
            "threshold_floor": self.threshold_floor,
            "effective_thresholds": self.effective_thresholds,
            "kelly_sizing": self.kelly_sizing,
            "run_config": self.run_config,
            "missing_side_models": self.missing_side_models,
            "barrier_warnings": self.barrier_warnings,
            "maker_fill_diagnostics": self.maker_fill_diagnostics,
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "tp_price": t.tp_price,
                    "sl_price": t.sl_price,
                    "pnl_pct": t.pnl_pct,
                    "net_pnl_pct": t.pnl_pct,
                    "gross_pnl_pct": t.gross_pnl_pct,
                    "fee_pct": t.fee_pct,
                    "slippage_pct": t.slippage_pct,
                    "cost_pct": t.cost_pct,
                    "fee_paid": t.fee_paid,
                    "slippage_paid": t.slippage_paid,
                    "cost_paid": t.cost_paid,
                    "outcome": t.outcome,
                    "strategy": t.strategy,
                    "entry_regime": t.entry_regime,
                    "long_probability": t.long_probability,
                    "short_probability": t.short_probability,
                    "used_threshold": t.used_threshold,
                    "model_side": t.model_side,
                    "entry_probability": t.entry_probability,
                    "position_size_used": t.position_size_used,
                    "trade_return_pct": t.trade_return_pct,
                    "gross_trade_return_pct": t.gross_trade_return_pct,
                    "entry_maker": t.entry_maker,
                }
                for t in self.trades
            ],
        }


def _validate_cost_rates(
    fee_rate_per_side: float,
    slippage_rate_per_side: float,
    maker_fee_rate_per_side: float = DEFAULT_MAKER_FEE_RATE_PER_SIDE,
) -> None:
    if not isfinite(fee_rate_per_side):
        raise ValueError("fee_rate_per_side must be finite")
    if not isfinite(maker_fee_rate_per_side):
        raise ValueError("maker_fee_rate_per_side must be finite")
    # A NEGATIVE maker fee is legitimate -- liquidity-provider tiers really do
    # pay you to rest an order -- so it is allowed, unlike the other rates. What
    # is refused is a rebate large enough to make the round trip cost nothing:
    # that is free money, and a backtest that models it will always find an
    # "edge". In reality the rebate never exceeds the taker fee it is paired
    # with (Bitget's deepest USDT-M maker rebate is well inside its taker rate),
    # so this rejects typos, not tiers.
    if maker_fee_rate_per_side + fee_rate_per_side < 0.0:
        raise ValueError(
            "maker_fee_rate_per_side + fee_rate_per_side must be non-negative "
            "(a maker rebate cannot exceed the taker fee on the other leg)"
        )
    if not isfinite(slippage_rate_per_side):
        raise ValueError("slippage_rate_per_side must be finite")
    if fee_rate_per_side < 0.0:
        raise ValueError("fee_rate_per_side must be non-negative")
    if slippage_rate_per_side < 0.0:
        raise ValueError("slippage_rate_per_side must be non-negative")


def kelly_fraction_for_entry(
    config: risk.KellySizingConfig,
    entry_probability: float | None,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    bar_returns_window: Sequence[float],
    cap: float,
    round_trip_cost: float = 0.0,
) -> float:
    """Per-trade Kelly fraction of equity from the entry's ACTUAL barriers.

    Uses the entered side's model probability and the executed TP/SL
    distances (so ATR-based barriers size correctly too), with the per-bar
    variance of the trailing window scaled to the holding period, and the
    edge taken NET of `round_trip_cost` -- the same 2*(fee+slippage) the
    trade will be charged at close. `cap` is the backtest's fixed
    position_size, reinterpreted as the maximum bet.

    Returns `cap` unchanged when there is no model probability (random-signal
    mode has nothing for Kelly to size on), and 0.0 -- skip the entry -- when
    the Kelly edge is non-positive or the variance window is unusable: a
    signal that clears the entry threshold but has no positive expectancy at
    the executed barriers is exactly the trade Kelly says not to take.
    """
    if entry_probability is None:
        return cap
    if entry_price <= 0.0:
        return 0.0
    tp_pct = abs(tp_price - entry_price) / entry_price
    sl_pct = abs(entry_price - sl_price) / entry_price
    probability = min(1.0, max(0.0, float(entry_probability)))
    return risk.kelly_leverage_for_signal(
        probability,
        tp_pct,
        sl_pct,
        bar_returns_window,
        config=config,
        cap=cap,
        round_trip_cost=round_trip_cost,
    )


def check_execution_barrier_parity(
    regime_bundle: object,
    exec_tp_pct: float | None,
    exec_sl_pct: float | None,
    allow_mismatch: bool = False,
) -> list[str]:
    """Refuse to execute a barrier the loaded models were not labeled on.

    Every side model answers one question: does price reach +tp before -sl
    inside the horizon. Execute 1.00%/0.50% against models labeled on
    0.30%/0.15% and their probabilities are about a trade that was never taken
    -- the entry thresholds, the Kelly edge and the reported win rate are all
    denominated in the wrong barrier. Nothing crashes; the run just reports a
    number that means nothing, which is the failure mode this repo guards
    against hardest.

    Raises ValueError on a genuine mismatch. Returns warnings (never raises) for
    a legacy artifact that does not record its barrier, because there the
    geometry is unknown, not known-wrong.

    allow_mismatch downgrades the error to a warning. No pipeline sets it:
    tp_sl_sweep.sh retrains every cell at its own tp/sl before backtesting it,
    so the sweep's barriers match by construction. It exists for a deliberate
    one-off probe of how a fixed model degrades under a barrier it was not
    trained for -- a sensitivity check, whose output is not performance.
    """
    if exec_tp_pct is None and exec_sl_pct is None:
        return []
    label_tp = getattr(regime_bundle, "label_tp_pct", None)
    label_sl = getattr(regime_bundle, "label_sl_pct", None)
    if label_tp is None or label_sl is None:
        return [
            "artifact does not record the tp_pct/sl_pct its models were labeled on "
            "(pre-parity-check artifact): cannot verify the executed barrier matches "
            "training. Retrain to get the check."
        ]
    mismatched = [
        f"{name}: labeled {labeled:.6g}, executing {executing:.6g}"
        for name, labeled, executing in (
            ("tp_pct", label_tp, exec_tp_pct),
            ("sl_pct", label_sl, exec_sl_pct),
        )
        if executing is not None and abs(float(executing) - float(labeled)) > _BARRIER_MATCH_TOL
    ]
    if not mismatched:
        return []
    detail = "; ".join(mismatched)
    message = (
        f"execution barrier does not match the barrier the models were trained on ({detail}). "
        "The model predicts P(TP before SL) for the LABELED barrier, so every probability, "
        "threshold and win rate in this run would be denominated in a barrier nobody trained "
        "on. Retrain with the new tp/sl, or pass allow_mismatch/--allow-barrier-mismatch if "
        "this is a deliberate TP/SL sweep."
    )
    if allow_mismatch:
        return [f"BARRIER MISMATCH (allowed): {detail}"]
    raise ValueError(message)


def _trade_gross_pnl_pct(trade: BacktestTrade, exit_price: float) -> float:
    if trade.side == "BUY":
        return (exit_price - trade.entry_price) / trade.entry_price
    return (trade.entry_price - exit_price) / trade.entry_price


def _close_trade(
    trade: BacktestTrade,
    exit_time: str,
    exit_price: float,
    outcome: str,
    equity: float,
    gross_equity: float,
    position_size: float,
    fee_rate_per_side: float,
    slippage_rate_per_side: float,
    maker_fee_rate_per_side: float = DEFAULT_MAKER_FEE_RATE_PER_SIDE,
    maker_exit_outcomes: frozenset[str] = frozenset(),
) -> tuple[float, float, float]:
    gross_pnl_pct = _trade_gross_pnl_pct(trade, exit_price)
    # Cost is per LEG and depends on how that leg filled. A resting limit gets
    # the cheaper MAKER fee and pays no slippage -- you named the price, so
    # there is no spread/impact to cross. An immediate fill pays TAKER plus
    # slippage. It is never free: only a rebate tier makes a resting fill cost
    # nothing, and this account has none (Bitget VIP0, maker 0.02% / taker
    # 0.06%, confirmed 2026-07-30).
    #   Both legs used to be modeled wrongly here. Until 2026-07-30 a maker
    # entry paid NO fee at all (over-crediting 2bps/trade); before that both
    # legs were charged the maker rate even for taker fills (under-charging
    # 8bps on a taker round trip); and the exit was hardcoded taker, which
    # understated an exchange that lets you rest TP/SL as limit orders.
    #   Whether the exit rests depends on HOW it closed, which is why the
    # decision lives here (the only place that knows the outcome) rather than
    # being one flag for all exits. See run_backtest's maker_exit_outcomes.
    exit_maker = outcome in maker_exit_outcomes
    entry_fee = maker_fee_rate_per_side if trade.entry_maker else fee_rate_per_side
    exit_fee = maker_fee_rate_per_side if exit_maker else fee_rate_per_side
    fee_pct = entry_fee + exit_fee
    slippage_pct = slippage_rate_per_side * (
        (0.0 if trade.entry_maker else 1.0) + (0.0 if exit_maker else 1.0)
    )
    cost_pct = fee_pct + slippage_pct
    net_pnl_pct = gross_pnl_pct - cost_pct

    trade_notional = position_size * equity
    fee_paid = fee_pct * trade_notional
    slippage_paid = slippage_pct * trade_notional
    net_trade_pnl = net_pnl_pct * trade_notional
    gross_trade_pnl = gross_pnl_pct * position_size * gross_equity

    trade.exit_time = exit_time
    trade.exit_price = exit_price
    trade.pnl_pct = net_pnl_pct
    trade.gross_pnl_pct = gross_pnl_pct
    trade.fee_pct = fee_pct
    trade.slippage_pct = slippage_pct
    trade.cost_pct = cost_pct
    trade.fee_paid = fee_paid
    trade.slippage_paid = slippage_paid
    trade.cost_paid = fee_paid + slippage_paid
    trade.trade_return_pct = net_pnl_pct * position_size
    trade.gross_trade_return_pct = gross_pnl_pct * position_size
    trade.outcome = outcome

    return equity + net_trade_pnl, gross_equity + gross_trade_pnl, net_pnl_pct


def run_backtest(
    candles: Sequence[data.Candle],
    model: object | None = None,
    strategy: live.StrategyConfig | None = None,
    initial_equity: float = 10000.0,
    position_size: float = 0.1,
    tp_sl_method: str = "fixed_pct",
    label_horizon: int = 60,
    min_hold_bars: int = 0,
    cooldown_bars: int = 30,
    long_threshold: float | None = None,
    short_threshold: float | None = None,
    exec_tp_pct: float | None = None,
    exec_sl_pct: float | None = None,
    threshold_floor: float = 0.0,
    precomputed_routing_diagnostics: dict | None = None,
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
    maker_fee_rate_per_side: float = DEFAULT_MAKER_FEE_RATE_PER_SIDE,
    slippage_rate_per_side: float = DEFAULT_SLIPPAGE_RATE_PER_SIDE,
    models_by_regime: Mapping[str, object] | None = None,
    user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None,
    default_regime: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    feature_rows: Sequence[dataset.FeatureRow] | None = None,
    regime_detector: object | None = None,
    regime_classifier_model: object | None = None,
    multi_feature_regime_detector: object | None = None,
    kelly_config: risk.KellySizingConfig | None = None,
    allow_barrier_mismatch: bool = False,
    range_gate_enabled: bool = True,
    maker_fill_window: int = 0,
    maker_fill_penetration: float = 0.0,
    maker_exit_outcomes: Sequence[str] | None = None,
    sl_fill: str = "barrier",
) -> BacktestResult:
    """Run a simple backtest on historical candles.

    Parameters
    ----------
    candles: historical 1m candles
    model: trained model (optional; if None, uses random signals)
    strategy: strategy config for thresholds and TP/SL (defaults to balanced)
    initial_equity: starting equity
    position_size: fraction of equity per trade; with kelly_config set it is
        reinterpreted as the CAP on the per-trade Kelly fraction
    kelly_config: opt-in fractional-Kelly position sizing (see
        risk.KellySizingConfig and kelly_fraction_for_entry); entries whose
        Kelly edge is non-positive are skipped and reported under
        kelly_sizing["entries_skipped_no_edge"] (kept out of signal_counts,
        whose BUY/SELL/HOLD keys tally per-bar signal decisions, not sizing
        outcomes)
    tp_sl_method: 'fixed_pct' or 'atr_pct'
    label_horizon: bars to hold before forced exit
    min_hold_bars: minimum bars to hold before allowing TP/SL exit
    cooldown_bars: bars to wait after exit before re-entry
    long_threshold: override strategy long threshold (default uses strategy.long_threshold)
    short_threshold: override strategy short threshold (default uses strategy.short_threshold)
    maker_exit_outcomes: which EXIT outcomes price as a resting limit (maker
        fee, no slippage) instead of an immediate fill; any subset of
        EXIT_OUTCOMES, empty/None = all exits taker. Bitget lets TP/SL be
        attached as limit orders when the position is opened, so a resting exit
        is representable there.

        It is per-outcome because the outcomes are not equally credible, and
        the mix decides the verdict rather than decorating it:

        - TP is the honest case. Price reached your level, your limit was
          resting there, someone crossed it. Maker.
        - SL is the optimistic case, and it is optimistic in the tail. A resting
          limit fills only if someone crosses it, and the move that triggers a
          stop is precisely the fast one-way move that blows through the level.
          Then you are not out at -sl_pct -- you are still in, losing more. High
          average BTC volume does not protect you: the risk lives in the
          liquidation cascades where the queue at your price is deepest exactly
          when you need out. Modeling SL as maker understates BOTH the fee and
          the fill price, and this function only models the fee half.
        - TIMEOUT is a horizon market-close unless the strategy deliberately
          rests a limit as the horizon approaches -- which is a different
          strategy (it can miss and hold past the horizon), not a cost setting.
        - OPEN_AT_END is the harness flattening at the window edge, an artifact
          of the backtest window rather than a trade decision.

        Measured on the 30m long (2025): TP 13.4%, SL 29.8%, TIMEOUT 56.8%, and
        break-even needs at least ~44% of exits to rest. So {"TP"} alone loses
        and {"TP","SL","TIMEOUT"} wins -- the answer is entirely in which of
        these you are willing to assume, which is why passing them explicitly
        beats one boolean that quietly assumed all four.
    sl_fill: WHERE a stopped-out trade fills, which is a different execution
        path rather than a stricter version of the same one.

        "barrier" (default) fills at sl_price exactly. That models a stop
        resting AT the exchange (live.py's STOP_MARKET): it triggers intrabar,
        so the fill is at the level plus the slippage constant, and a gap
        through the level is not modeled.

        "next_open" fills at the NEXT bar's open. That models a bot-side stop:
        the bar closes past sl_price, you see it, you send a market order that
        fills on the following bar. It is not merely the pessimistic version --
        it is two-sided, and for mean reversion the sides do not cancel. A bar
        that wicks through the stop and closes back above it does not stop you
        out at all here, and one that does stop you out often opens back in
        your favour; against that, a real gap fills worse than the level ever
        would. Which is right depends on which stop the strategy would actually
        place, so this must match live -- an exchange-resident stop cannot be
        backtested as "next_open", and a bot-side stop cannot be backtested as
        "barrier".

        On the last candle there is no next bar; the trade closes at that
        candle's close instead, still recorded as SL.
    """
    if strategy is None:
        strategy = live.strategy_for_regime(None, "balanced")
    strategy = apply_exec_barrier(strategy, exec_tp_pct, exec_sl_pct)
    _validate_cost_rates(fee_rate_per_side, slippage_rate_per_side, maker_fee_rate_per_side)
    if sl_fill not in SL_FILL_MODES:
        raise ValueError(f"sl_fill must be one of {sorted(SL_FILL_MODES)}, got {sl_fill!r}")
    maker_exit_set = frozenset(str(o).upper() for o in (maker_exit_outcomes or ()))
    unknown = maker_exit_set - EXIT_OUTCOMES
    if unknown:
        raise ValueError(
            f"unknown maker_exit_outcomes {sorted(unknown)}; expected a subset of {sorted(EXIT_OUTCOMES)}"
        )
    if label_horizon <= 0:
        raise ValueError("label_horizon must be positive")
    if min_hold_bars < 0:
        raise ValueError("min_hold_bars must be non-negative")
    if min_hold_bars > label_horizon:
        raise ValueError("min_hold_bars must not exceed label_horizon")
    if maker_fill_window < 0:
        raise ValueError("maker_fill_window must be non-negative")
    if maker_fill_penetration < 0.0:
        raise ValueError("maker_fill_penetration must be non-negative")
    if cooldown_bars < 0:
        raise ValueError("cooldown_bars must be non-negative")
    # Before anything else: the models must have been labeled on the barrier we
    # are about to execute. A mismatch cannot be detected from the results (they
    # look like ordinary bad numbers), so it has to be refused up front.
    barrier_warnings = check_execution_barrier_parity(
        models_by_regime, exec_tp_pct, exec_sl_pct, allow_mismatch=allow_barrier_mismatch
    )
    result = BacktestResult()
    result.barrier_warnings = barrier_warnings
    result.fee_rate_per_side = fee_rate_per_side
    result.maker_fee_rate_per_side = maker_fee_rate_per_side
    result.slippage_rate_per_side = slippage_rate_per_side
    result.round_trip_cost_pct = 2.0 * (fee_rate_per_side + slippage_rate_per_side)
    result.min_hold_bars = min_hold_bars
    result.cooldown_bars = cooldown_bars
    result.threshold_floor = threshold_floor
    # Everything a second run must match to be comparable to this one. The full
    # strategy config is recorded (after the exec_* overrides are folded in),
    # because atr_multiplier_*, the TP/SL floors and use_atr_pricing all change
    # the barrier actually executed -- recording only name/tp/sl would let two
    # runs with different execution look identical in the artifact.
    result.run_config = {
        "backtest_start": start_date,
        "backtest_end": end_date,
        "execution_horizon": label_horizon,
        "exec_tp_pct": exec_tp_pct,
        "exec_sl_pct": exec_sl_pct,
        "strategy_config": strategy.as_dict(),
        "position_size": position_size,
        "initial_equity": initial_equity,
        "tp_sl_method": tp_sl_method,
        "long_threshold_override": long_threshold,
        "short_threshold_override": short_threshold,
        "range_gate_enabled": range_gate_enabled,
        # Both rates, because a run's net is only interpretable against the fee
        # tier it assumed -- and this project has already published numbers that
        # silently used the maker rate for taker fills.
        "fee_rate_per_side": fee_rate_per_side,
        "maker_fee_rate_per_side": maker_fee_rate_per_side,
        "slippage_rate_per_side": slippage_rate_per_side,
        "maker_fill_window": maker_fill_window,
        "maker_exit_outcomes": sorted(maker_exit_set),
        "sl_fill": sl_fill,
        "maker_fill_penetration": maker_fill_penetration,
        "kelly_enabled": kelly_config is not None,
        "kelly_multiplier": kelly_config.kelly_multiplier if kelly_config else None,
        "kelly_lookback_bars": kelly_config.variance_lookback_bars if kelly_config else None,
        "kelly_holding_period_bars": kelly_config.holding_period_bars if kelly_config else None,
    }
    if precomputed_routing_diagnostics is not None:
        result.regime_routing_diagnostics = precomputed_routing_diagnostics
    # Record learned vs effective thresholds per regime (effective = what this
    # run actually gates entries with, after CLI override and floor).
    if models_by_regime:
        for _reg, _bundle in models_by_regime.items():
            _learned = {}
            _rt = getattr(_bundle, "regime_thresholds", None)
            if isinstance(_rt, Mapping):
                _learned = _rt.get(_reg, {}) or {}
            _elt, _est = _resolve_backtest_thresholds(_bundle, _reg, long_threshold, short_threshold, strategy, threshold_floor)
            result.effective_thresholds[_reg] = {
                "learned_long": float(_learned["long"]) if "long" in _learned else None,
                "learned_short": float(_learned["short"]) if "short" in _learned else None,
                "effective_long": _elt,
                "effective_short": _est,
            }
    equity = initial_equity
    gross_equity = initial_equity
    max_drawdown_pct = 0.0
    peak_equity = initial_equity
    active_trade: BacktestTrade | None = None
    bar_count = 0
    next_entry_index = 0
    # Maker limit-fill state (used only when maker_fill_window > 0). A resting
    # order is a dict {side, limit, expiry, features, ctx}; counters feed
    # maker_fill_diagnostics.
    pending_order: dict[str, object] | None = None
    maker_orders_placed = 0
    maker_orders_filled = 0
    # Expiries and Kelly refusals are counted apart: an expiry is the book
    # never coming back to the limit (what fill_rate is about), a refusal is a
    # fill the sizer then declined. Lumping them made fill_rate a statement
    # about two unrelated things.
    maker_orders_expired = 0
    maker_orders_kelly_refused = 0

    if feature_rows is None:
        feature_rows = dataset.build_feature_rows(candles, user_regime_periods=user_regime_periods)

    # Real-time regime routing: exactly one of two sources drives it (in
    # priority order), overwriting feature_rows[i].user_regime so the
    # existing regime-routing logic downstream works unchanged. Both are
    # what a live deployment must do -- future regimes can't be known in
    # advance -- but only ONE of them can have been used to decide which
    # regime bucket each row's TRAINING data went into; using the other one
    # here would silently invoke the up/down/range entry models on regimes
    # they were never trained on (train/serve skew). Callers MUST pass the
    # SAME source (classifier model path, or plain detector) that trained
    # the loaded models_by_regime.
    #   (a) regime_classifier_model: the SAVED FINAL classifier from
    #       train-regime-classifier (fit once on the complete training span,
    #       e.g. 2020-2024), run over F17 multi-timeframe features via
    #       regime_classifier.route_regime_causal. Using this "final"
    #       (in-sample) classifier is safe HERE specifically because
    #       backtest/live candles are chronologically AFTER the training
    #       span the classifier was fit on -- genuinely out-of-sample, no
    #       look-ahead. (Contrast with training.py's bucket assignment,
    #       which deliberately does NOT use this classifier for TRAINING
    #       rows -- see the comment there for why re-predicting on rows the
    #       classifier's own fit already "saw" would be a subtle leak.)
    #   (b) regime_detector: RegimeDetector.detect_all_directional on
    #       trend_slope_30 alone (narrower, legacy fallback).
    if multi_feature_regime_detector is not None and user_regime_periods is None:
        # Multi-feature rule-based routing: the SAME fitted detector used for
        # training bucket assignment (loaded from regime_run_summary.json).
        # Deterministic and causal over F17 features -- takes priority over the
        # learned classifier and the single-slope detector.
        import dataclasses as _dc
        detected = multi_feature_regime_detector.detect_all([r.features for r in feature_rows])
        # detect_all runs over the FULL series (the hysteresis/min-hold state at
        # the backtest start needs the preceding history), but the saved
        # diagnostics must describe ONLY the backtest window -- otherwise a
        # 2025 backtest gets 2020-2025 regime counts/transitions, which is
        # useless for interpreting the 2025 result (previously counts summed to
        # the full 3.15M candles instead of 2025's 525,600).
        if start_date is not None or end_date is not None:
            _diag_start, _diag_end = window_bounds(start_date, end_date)
            detected_window = [
                regime for row, regime in zip(feature_rows, detected)
                if (_diag_start is None or row.open_time >= _diag_start)
                and (_diag_end is None or row.open_time < _diag_end)
            ]
        else:
            detected_window = detected
        _diag = multi_feature_regime_detector.diagnostics(detected_window)
        result.regime_routing_diagnostics = _diag
        print(
            "[BACKTEST] regime routing stats: "
            f"counts={_diag.get('regime_counts')} "
            f"ratios={ {k: round(v, 3) for k, v in _diag.get('regime_ratios', {}).items()} } "
            f"transitions={_diag.get('regime_transition_count')} "
            f"direct_up<->down={_diag.get('direct_reversal_count')} "
            f"avg_duration_bars={ {k: round(v, 1) for k, v in _diag.get('avg_regime_duration_bars', {}).items()} }"
        )
        print(f"[BACKTEST] transitions_by_type: {_diag.get('transition_by_type')}")
        feature_rows = [
            _dc.replace(row, user_regime=regime)
            for row, regime in zip(feature_rows, detected)
        ]
    elif regime_classifier_model is not None and user_regime_periods is None:
        import dataclasses as _dc
        from btcusdt_quant import mtf_features as _mtf, regime_classifier as _rc
        feature_rows_f17 = [_mtf.extract_feature_vector(r.features) for r in feature_rows]
        raw_probs, detected = _rc.route_regime_causal(feature_rows_f17, regime_classifier_model)
        # Inject the SAME regime_prob_up/range/down values entry models saw
        # as F18 features during training (merged from
        # regime_probabilities.json's walk-forward OOF output). Previously
        # only `detected` (the routing decision) was kept and these
        # probabilities were discarded, so backtest/live silently fed entry
        # models regime_prob_*=0.0 (the build_feature_rows default) while
        # training fed them real values -- a train/serve input-distribution
        # mismatch distinct from the routing bucket-assignment issue.
        feature_rows = [
            _dc.replace(
                row,
                user_regime=regime,
                features={
                    **row.features,
                    "regime_prob_up": probs["up"],
                    "regime_prob_range": probs["range"],
                    "regime_prob_down": probs["down"],
                },
            )
            for row, regime, probs in zip(feature_rows, detected, raw_probs)
        ]
    elif regime_detector is not None and user_regime_periods is None:
        import dataclasses as _dc
        trend_slopes = [float(r.features.get("trend_slope_30", 0.0)) for r in feature_rows]
        rv_values = [float(r.features.get("rv_15", 0.0)) for r in feature_rows]
        detected = regime_detector.detect_all_directional(rv_values, trend_slopes)
        feature_rows = [
            _dc.replace(row, user_regime=regime)
            for row, regime in zip(feature_rows, detected)
        ]

    # Without an explicit end the backtest silently runs to END OF FILE.
    # end_date closes the window explicitly; date-only values include the whole
    # final day (exclusive next-midnight bound).
    start_dt, end_dt = window_bounds(start_date, end_date)

    # Trailing per-bar returns for Kelly variance estimation. Bar 0 has no
    # previous close, and a zero previous close cannot produce a return;
    # both are NaN so return_variance skips them instead of guessing.
    bar_returns: list[float] = []
    kelly_skipped_entries = 0
    kelly_skipped_shorts = 0
    kelly_skipped_longs = 0
    # Kelly must size against the cost this run will actually pay. Under the
    # maker model the entry pays the maker fee and no slippage (see
    # _close_trade), so quoting the taker round-trip here would make Kelly
    # refuse entries the run can afford.
    # Kelly has to quote ONE exit cost before knowing how the trade will close,
    # so it takes the taker rate unless EVERY outcome rests. Sizing off the
    # cheaper leg for a trade that then exits taker would over-size it; being
    # too conservative only refuses marginal entries.
    _all_exits_maker = maker_exit_set >= EXIT_OUTCOMES
    _entry_fee = maker_fee_rate_per_side if maker_fill_window > 0 else fee_rate_per_side
    _exit_fee = maker_fee_rate_per_side if _all_exits_maker else fee_rate_per_side
    _slip_legs = (0.0 if maker_fill_window > 0 else 1.0) + (0.0 if _all_exits_maker else 1.0)
    round_trip_cost = _entry_fee + _exit_fee + _slip_legs * slippage_rate_per_side
    if kelly_config is not None:
        bar_returns = [float("nan")] * len(candles)
        for j in range(1, len(candles)):
            prev_close = candles[j - 1].close
            if prev_close > 0.0:
                bar_returns[j] = (candles[j].close - prev_close) / prev_close

    def _open_trade(side, entry_price, entry_time_iso, features, ctx, entry_maker):
        """Build a BacktestTrade (or None if Kelly refuses). ctx is the
        signal-time (regime, long_prob, short_prob, lt, st, genuine_sides).
        Reads the loop's current `i` for the Kelly variance window."""
        nonlocal kelly_skipped_shorts, kelly_skipped_longs, kelly_skipped_entries
        regime, lprob, sprob, lt_, st_, genuine = ctx
        tp_price, sl_price, _decision = live.optimized_tp_sl(entry_price, side, features, strategy)
        trade_size: float | None = None
        if kelly_config is not None:
            entered_side = "long" if side == "BUY" else "short"
            if entered_side not in genuine:
                # See the long note at the taker path: a BUY/SELL with no
                # declared genuine side cannot be Kelly-sized on a real
                # probability. Fail closed, attributed by side.
                if entered_side == "short":
                    kelly_skipped_shorts += 1
                else:
                    kelly_skipped_longs += 1
                return None
            entry_prob = lprob if side == "BUY" else sprob
            window_start = max(0, i + 1 - kelly_config.variance_lookback_bars)
            trade_size = kelly_fraction_for_entry(
                kelly_config, entry_prob, entry_price, tp_price, sl_price,
                bar_returns[window_start:i + 1], position_size, round_trip_cost=round_trip_cost,
            )
            if trade_size <= 0.0:
                kelly_skipped_entries += 1
                return None
        return BacktestTrade(
            entry_time=entry_time_iso, exit_time="", side=side,
            entry_price=entry_price, exit_price=0.0, tp_price=tp_price, sl_price=sl_price,
            pnl_pct=0.0, outcome="", strategy=strategy.name,
            entry_regime=regime, long_probability=lprob, short_probability=sprob,
            used_threshold=lt_ if side == "BUY" else st_,
            model_side="long" if side == "BUY" else "short",
            entry_probability=lprob if side == "BUY" else sprob,
            position_size_used=trade_size, entry_maker=entry_maker,
        )

    last_in_window_candle = None
    for i, candle in enumerate(candles):
        # Trade only inside [start_date, end_date) (features still use full history)
        if start_dt is not None and candle.open_time < start_dt:
            continue
        if end_dt is not None and candle.open_time >= end_dt:
            # Candles are chronological: nothing after this is in-window.
            # break (not continue) so an open trade cannot be force-closed at
            # candles[-1] -- which is the END OF FILE, possibly far past the
            # backtest window once the parquet grows beyond it.
            break
        last_in_window_candle = candle

        result.signal_counts.setdefault("HOLD", 0)
        result.signal_counts.setdefault("BUY", 0)
        result.signal_counts.setdefault("SELL", 0)

        # Entry-decision context recorded onto the trade for attribution.
        _ctx_regime: str | None = None
        _ctx_long_prob: float | None = None
        _ctx_short_prob: float | None = None
        _ctx_lt: float | None = None
        _ctx_st: float | None = None
        # Probability semantics of the path that produced this bar's signal:
        # True on the bundle paths where _ctx_short_prob is a dedicated short
        # model's P(short wins); False on the single-model paths where BOTH
        # ctx slots hold the same P(long/up) and a SELL fires because that
        # value is SMALL -- there the short's win probability is 1 - prob.
        # Which sides carry a GENUINE per-side probability on this bar. The
        # bundle answers for itself (`has_side_probability`); the single-model
        # paths below can only produce P(long_success)-like scores, so they
        # never claim "short". Empty set => the Kelly guard refuses the entry
        # (fail-closed): a signal with no declared side is a routing bug.
        _ctx_genuine_sides: set[str] = set()

        # Model inference (regime-aware if models_by_regime provided)
        signal = "HOLD"
        if models_by_regime is not None and i < len(feature_rows):
            regime = feature_rows[i].user_regime
            if regime is not None and regime in models_by_regime:
                result.regime_coverage["matched"] = result.regime_coverage.get("matched", 0) + 1
            elif default_regime is not None and default_regime in models_by_regime:
                result.regime_coverage["default_fallback"] = result.regime_coverage.get("default_fallback", 0) + 1
            else:
                result.regime_coverage["no_model"] = result.regime_coverage.get("no_model", 0) + 1
            if regime is not None and regime in models_by_regime:
                # Check if models_by_regime is a RegimeModelBundle with direction policy
                regime_bundle = models_by_regime.get(regime)
                if hasattr(regime_bundle, 'direction_policy'):
                    # New structure: RegimeModelBundle with long/short models
                    allowed_directions = regime_bundle.direction_policy.get(regime, {"LONG", "SHORT"})
                    features_dict = feature_rows[i].features
                    if range_gate_enabled:
                        allowed_directions = apply_range_mean_reversion_gate(regime, features_dict, allowed_directions)

                    # Ask the bundle whether it can price each side, instead of
                    # reaching into its dicts and then inventing 0.0 for the
                    # side it cannot. `None` means "cannot price", which is not
                    # the same claim as "zero chance".
                    long_prob = short_prob = None
                    if "LONG" in allowed_directions and regime_bundle.has_side_probability(regime, "long"):
                        long_prob = regime_bundle.probability_for(regime, "long", features_dict)
                    if "SHORT" in allowed_directions and regime_bundle.has_side_probability(regime, "short"):
                        short_prob = regime_bundle.probability_for(regime, "short", features_dict)

                    if long_prob is not None or short_prob is not None:
                        from btcusdt_quant.live import evaluate_entry_signal

                        lt, st = _resolve_backtest_thresholds(regime_bundle, regime, long_threshold, short_threshold, strategy, threshold_floor)
                        _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = regime, long_prob, short_prob, lt, st
                        if long_prob is not None:
                            _ctx_genuine_sides.add("long")
                        if short_prob is not None:
                            _ctx_genuine_sides.add("short")

                        entry_signal, _, _ = evaluate_entry_signal(
                            long_prob if long_prob is not None else 0.0,
                            short_prob if short_prob is not None else 0.0,
                            long_threshold=lt,
                            short_threshold=st,
                            strategy=strategy,
                            features=feature_rows[i].features if i < len(feature_rows) else {},
                        )
                        
                        if entry_signal == "LONG":
                            signal = "BUY"
                        elif entry_signal == "SHORT":
                            signal = "SELL"
                        else:
                            signal = "HOLD"
                    else:
                        signal = "HOLD"
                else:
                    # Legacy structure: single model per regime
                    active_model = regime_bundle
                    features_dict = feature_rows[i].features
                    prob = active_model.probability(features_dict)
                    lt, st = _resolve_backtest_thresholds(regime_bundle, regime, long_threshold, short_threshold, strategy, threshold_floor)
                    _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = regime, prob, prob, lt, st
                    # One model, one score: P(long_success)-like. A SELL here
                    # fires because that value is LOW, which is not a short
                    # win probability, so "short" is never genuine.
                    _ctx_genuine_sides.add("long")
                    # Resolved lt/st (override > learned > strategy, floored) are
                    # the ONLY gate now; the old extra hard gate (prob>=0.55 /
                    # prob<=0.45) silently overrode threshold experiments on the
                    # legacy single-model paths.
                    if prob > lt:
                        signal = "BUY"
                    elif prob < st:
                        signal = "SELL"
                    else:
                        signal = "HOLD"
            elif default_regime is not None and default_regime in models_by_regime:
                # Fallback to the default regime's models when the current bar
                # has no user_regime (e.g. outside any configured regime period).
                regime_bundle = models_by_regime.get(default_regime)
                features_dict = feature_rows[i].features
                if hasattr(regime_bundle, 'direction_policy'):
                    # New structure: route through long/short models with the
                    # default regime's direction policy, mirroring the main path.
                    allowed_directions = regime_bundle.direction_policy.get(default_regime, {"LONG", "SHORT"})
                    if range_gate_enabled:
                        allowed_directions = apply_range_mean_reversion_gate(default_regime, features_dict, allowed_directions)
                    long_prob = short_prob = None
                    if "LONG" in allowed_directions and regime_bundle.has_side_probability(default_regime, "long"):
                        long_prob = regime_bundle.probability_for(default_regime, "long", features_dict)
                    if "SHORT" in allowed_directions and regime_bundle.has_side_probability(default_regime, "short"):
                        short_prob = regime_bundle.probability_for(default_regime, "short", features_dict)
                    if long_prob is not None or short_prob is not None:
                        from btcusdt_quant.live import evaluate_entry_signal
                        lt, st = _resolve_backtest_thresholds(regime_bundle, default_regime, long_threshold, short_threshold, strategy, threshold_floor)
                        _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = default_regime, long_prob, short_prob, lt, st
                        if long_prob is not None:
                            _ctx_genuine_sides.add("long")
                        if short_prob is not None:
                            _ctx_genuine_sides.add("short")
                        entry_signal, _, _ = evaluate_entry_signal(
                            long_prob if long_prob is not None else 0.0,
                            short_prob if short_prob is not None else 0.0,
                            long_threshold=lt, short_threshold=st,
                            strategy=strategy,
                            features=feature_rows[i].features if i < len(feature_rows) else {},
                        )
                        signal = "BUY" if entry_signal == "LONG" else ("SELL" if entry_signal == "SHORT" else "HOLD")
                    else:
                        signal = "HOLD"
                else:
                    # Legacy structure: single model per regime.
                    active_model = regime_bundle
                    prob = active_model.probability(features_dict)
                    lt, st = _resolve_backtest_thresholds(regime_bundle, default_regime, long_threshold, short_threshold, strategy, threshold_floor)
                    _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = default_regime, prob, prob, lt, st
                    _ctx_genuine_sides.add("long")
                    if prob > lt:
                        signal = "BUY"
                    elif prob < st:
                        signal = "SELL"
                    else:
                        signal = "HOLD"
        elif model is not None and i < len(feature_rows):
            features_dict = feature_rows[i].features
            prob = model.probability(features_dict)
            lt = long_threshold if long_threshold is not None else strategy.long_threshold
            st = short_threshold if short_threshold is not None else strategy.short_threshold
            _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = None, prob, prob, lt, st
            _ctx_genuine_sides.add("long")
            if prob > lt:
                signal = "BUY"
            elif prob < st:
                signal = "SELL"
            else:
                signal = "HOLD"

        result.signal_counts[signal] += 1

        # Maker resting-limit model, part 1: try to fill an order placed on an
        # EARLIER bar. This sits ABOVE the exit block on purpose. A maker order
        # fills part-way THROUGH this bar, so the rest of the bar is real,
        # tradeable time and can hit a barrier -- unlike a taker entry at the
        # close, which leaves nothing of the bar behind. Opening below the exit
        # block (as this used to) skipped the fill bar's barrier check entirely,
        # and the fill bar is BY CONSTRUCTION one that moved against the entry
        # (price came back to the limit), so the skipped outcomes were the bad
        # ones: measured 1.34% of fills had already breached SL. Filling here
        # lets the SAME exit logic below resolve the fill bar, with no second
        # copy of the barrier rules. bar_count therefore reaches 1 on the fill
        # bar -- correct, since the position is held for part of it.
        #   Residual OHLC limitation: a BUY's low necessarily comes at/after the
        # fill (price had to fall to the limit), so the SL side is sound, but the
        # high may predate the dip, so a same-bar TP can resolve optimistically.
        # Measured at 0.20% of fills -- accepted.
        # 2) placing a new order stays below, after the exit block.
        if maker_fill_window > 0 and active_trade is None and pending_order is not None:
            if i > int(pending_order["expiry"]):
                pending_order = None
                maker_orders_expired += 1
            else:
                lp = float(pending_order["limit"])
                pside = str(pending_order["side"])
                # Queue-priority proxy: require the price to PENETRATE the
                # limit by maker_fill_penetration (fraction), not merely
                # touch it. A resting order sits behind others at its price;
                # a bare touch may only fill the front of the queue. Needing
                # the market to trade through the level models your order
                # clearing. 0 = touch fills (optimistic).
                if pside == "BUY":
                    hit = candle.low <= lp * (1.0 - maker_fill_penetration)
                else:
                    hit = candle.high >= lp * (1.0 + maker_fill_penetration)
                if hit:
                    opened = _open_trade(
                        pside, lp, candle.open_time.isoformat(),
                        pending_order["features"], pending_order["ctx"], True,
                    )
                    pending_order = None
                    if opened is not None:
                        active_trade = opened
                        bar_count = 0
                        maker_orders_filled += 1
                    else:
                        # The limit DID fill; Kelly then refused to size it.
                        # Counted apart from expiries so fill_rate stays a
                        # statement about the book, not about sizing.
                        maker_orders_kelly_refused += 1

        # Exit active trade if SL/TP hit or horizon exceeded
        if active_trade is not None:
            bar_count += 1
            exit_price = candle.close
            hit_tp = False
            hit_sl = False
            if active_trade.side == "BUY":
                hit_tp = candle.high >= active_trade.tp_price
                hit_sl = candle.low <= active_trade.sl_price
            else:
                hit_tp = candle.low <= active_trade.tp_price
                hit_sl = candle.high >= active_trade.sl_price

            can_exit_for_barrier = bar_count >= min_hold_bars
            if (can_exit_for_barrier and (hit_tp or hit_sl)) or bar_count >= label_horizon:
                # When BOTH barriers are touched in the same candle, we cannot
                # know from OHLC which came first. Mirror the labeling rule in
                # dataset.triple_barrier_label_* (which decides via candle
                # direction: close>open => TP first, else SL first) so the
                # backtest resolves ties the SAME way the model was trained.
                # Previously the backtest always assumed TP first, an
                # optimistic bias that inflated win rate vs the labels.
                both_hit = hit_tp and hit_sl and can_exit_for_barrier
                if both_hit:
                    # Side-specific tie-break matching the labeler:
                    #   long  (BUY):  close > open  => TP first
                    #   short (SELL): close < open  => TP first
                    if active_trade.side == "BUY":
                        tp_first = candle.close > candle.open
                    else:
                        tp_first = candle.close < candle.open
                    if tp_first:
                        exit_price = active_trade.tp_price
                        outcome = "TP"
                    else:
                        exit_price = active_trade.sl_price
                        outcome = "SL"
                elif hit_tp and can_exit_for_barrier:
                    exit_price = active_trade.tp_price
                    outcome = "TP"
                elif hit_sl and can_exit_for_barrier:
                    exit_price = active_trade.sl_price
                    outcome = "SL"
                else:
                    outcome = "TIMEOUT"

                # A bot-side stop does not fill at the level: the bar closes
                # past it, you react, and the market order fills on the next
                # bar's open -- better than the level if the wick reverted,
                # worse if it gapped. Only the SL leg moves; a TP limit and a
                # horizon close are unaffected. No next bar (last candle) means
                # closing at this bar's close, still an SL.
                exit_candle = candle
                if outcome == "SL" and sl_fill == "next_open":
                    if i + 1 < len(candles):
                        exit_candle = candles[i + 1]
                        exit_price = exit_candle.open
                    else:
                        exit_price = candle.close

                equity, gross_equity, _ = _close_trade(
                    active_trade,
                    exit_candle.open_time.isoformat(),
                    exit_price,
                    outcome,
                    equity,
                    gross_equity,
                    active_trade.position_size_used if active_trade.position_size_used is not None else position_size,
                    fee_rate_per_side,
                    slippage_rate_per_side,
                    maker_fee_rate_per_side,
                    maker_exit_set,
                )
                result.total_fees += active_trade.fee_paid
                result.total_slippage += active_trade.slippage_paid
                result.total_costs += active_trade.cost_paid
                peak_equity = max(peak_equity, equity)
                max_drawdown_pct = max(max_drawdown_pct, 1.0 - equity / peak_equity if peak_equity > 0 else 0.0)
                result.trades.append(active_trade)
                active_trade = None
                bar_count = 0
                if cooldown_bars > 0:
                    # Count the cooldown from the bar the position actually
                    # closed on, which a deferred stop pushes forward by one.
                    next_entry_index = (i + 1 if exit_candle is not candle else i) + cooldown_bars + 1

        # ---- Enter new trade ----
        if maker_fill_window <= 0:
            # Default: instant taker fill at the signal-bar close.
            if active_trade is None and signal in {"BUY", "SELL"} and i >= next_entry_index:
                ctx = (_ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st, set(_ctx_genuine_sides))
                feats = feature_rows[i].features if i < len(feature_rows) else {}
                opened = _open_trade(signal, candle.close, candle.open_time.isoformat(), feats, ctx, False)
                if opened is not None:
                    active_trade = opened
                    bar_count = 0
        else:
            # Maker resting-limit model, part 2: place a limit on a fresh
            # signal. Part 1 (filling an order placed on an EARLIER bar) runs
            # ABOVE the exit block -- see the note there for why.
            if active_trade is None and pending_order is None and signal in {"BUY", "SELL"} and i >= next_entry_index:
                pending_order = {
                    "side": signal,
                    "limit": candle.close,
                    "expiry": i + maker_fill_window,
                    "features": feature_rows[i].features if i < len(feature_rows) else {},
                    "ctx": (_ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st, set(_ctx_genuine_sides)),
                }
                maker_orders_placed += 1

    # An order still resting when the window closed never got its verdict.
    # Counting it keeps placed == filled + expired + kelly_refused, so a reader
    # can tell the accounting is complete rather than off by a silent one.
    if pending_order is not None:
        pending_order = None
        maker_orders_expired += 1

    # Close any remaining open trade at the last IN-WINDOW candle (not the
    # file's last candle, which may lie past the backtest window).
    if active_trade is not None and last_in_window_candle is not None:
        last_candle = last_in_window_candle
        exit_price = last_candle.close
        equity, gross_equity, _ = _close_trade(
            active_trade,
            last_candle.open_time.isoformat(),
            exit_price,
            "OPEN_AT_END",
            equity,
            gross_equity,
            active_trade.position_size_used if active_trade.position_size_used is not None else position_size,
            fee_rate_per_side,
            slippage_rate_per_side,
            maker_fee_rate_per_side,
            maker_exit_set,
        )
        result.total_fees += active_trade.fee_paid
        result.total_slippage += active_trade.slippage_paid
        result.total_costs += active_trade.cost_paid
        peak_equity = max(peak_equity, equity)
        max_drawdown_pct = max(max_drawdown_pct, 1.0 - equity / peak_equity if peak_equity > 0 else 0.0)
        result.trades.append(active_trade)

    # Compute metrics
    result.total_return = (equity - initial_equity) / initial_equity
    result.gross_total_return = (gross_equity - initial_equity) / initial_equity
    result.trade_count = len(result.trades)
    if result.trades:
        _n = float(len(result.trades))
        result.mean_gross_bps_per_trade = sum(t.gross_pnl_pct for t in result.trades) / _n * 1e4
        result.mean_net_bps_per_trade = sum(t.pnl_pct for t in result.trades) / _n * 1e4
    # Risk metrics are computed on EQUITY returns (pnl scaled by the fraction
    # actually bet), not on price returns. Under a constant position_size the
    # multiplier cancels in Sharpe and merely rescales profit_factor's ratio,
    # so fixed-size results are unchanged; under Kelly, where each trade bets
    # a different fraction, price-return metrics would weight a 1%-of-equity
    # trade the same as a 10% one and hide exactly what the sizing did.
    # Risk metrics need a sample. Below MIN_TRADES_FOR_RISK_METRICS the Sharpe
    # and profit factor are NaN, not zero and not a lucky number: a 2-trade run
    # that happened to close both at TP reported win_rate 1.0, profit_factor
    # inf, max_drawdown 0 and Sharpe 1.08e14. win_rate and max_drawdown stay
    # populated -- they are descriptive, and their small-sample weakness is
    # legible from trade_count next to them.
    enough_trades = len(result.trades) >= MIN_TRADES_FOR_RISK_METRICS
    if result.trades:
        wins = sum(1 for t in result.trades if t.pnl_pct > 0)
        result.win_rate = wins / len(result.trades)
    if enough_trades:
        gross_profit = sum(t.trade_return_pct for t in result.trades if t.trade_return_pct > 0)
        gross_loss = abs(sum(t.trade_return_pct for t in result.trades if t.trade_return_pct < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    else:
        result.profit_factor = float("nan")
    result.max_drawdown = max_drawdown_pct
    if enough_trades:
        result.sharpe = per_trade_sharpe([t.trade_return_pct for t in result.trades])
        result.gross_sharpe = per_trade_sharpe([t.gross_trade_return_pct for t in result.trades])
    else:
        result.sharpe = float("nan")
        result.gross_sharpe = float("nan")
    result.risk_metrics_min_trades = MIN_TRADES_FOR_RISK_METRICS
    if kelly_config is not None:
        sizes = [t.position_size_used for t in result.trades if t.position_size_used is not None]
        result.kelly_sizing = {
            "enabled": True,
            "cap": position_size,
            "kelly_multiplier": kelly_config.kelly_multiplier,
            "holding_period_bars": kelly_config.holding_period_bars,
            "variance_lookback_bars": kelly_config.variance_lookback_bars,
            "round_trip_cost": round_trip_cost,
            "trades_sized": len(sizes),
            "entries_skipped_no_edge": kelly_skipped_entries,
            # Entries refused because no genuine per-side probability existed:
            # single-model routing (no P(short_success) anywhere) or a regime
            # bundle missing that side's model. Non-zero on one side means the
            # run was effectively one-directional in those regimes.
            "shorts_skipped_no_short_model": kelly_skipped_shorts,
            "longs_skipped_no_long_model": kelly_skipped_longs,
            "avg_fraction": sum(sizes) / len(sizes) if sizes else 0.0,
            "min_fraction": min(sizes) if sizes else 0.0,
            "max_fraction": max(sizes) if sizes else 0.0,
        }
    if maker_fill_window > 0:
        result.maker_fill_diagnostics = {
            "maker_fill_window": maker_fill_window,
            "maker_fill_penetration": maker_fill_penetration,
            "orders_placed": maker_orders_placed,
            "orders_filled": maker_orders_filled,
            # Never touched by the book within the window. This -- not sizing --
            # is what "the maker missed the trade" means.
            "orders_expired": maker_orders_expired,
            # Filled, then declined by Kelly. Zero unless kelly_config is set.
            "orders_kelly_refused": maker_orders_kelly_refused,
            # placed == filled + expired + kelly_refused, by construction.
            "fill_rate": (
                (maker_orders_filled + maker_orders_kelly_refused) / maker_orders_placed
                if maker_orders_placed else 0.0
            ),
        }
    return result


def per_trade_sharpe(returns: Sequence[float]) -> float:
    """Per-trade Sharpe (mean/std of trade returns, no annualization).

    NaN when the ratio is undefined rather than a number that reads as a
    result. `std > 0` was not a sufficient guard: two trades that both closed
    at TP differ only in float noise, so std came out ~1e-18 and the run
    reported a Sharpe of 1.08e14. Dispersion at or below MIN_RETURN_STD is
    noise, not risk, and dividing by it means nothing.

    Public because compare_backtests.py reports the same statistic on slices of
    the same trades: a second copy of the formula there would be free to drift
    from this one, and the two numbers are meant to reconcile.
    """
    if len(returns) < 2:
        return float("nan")
    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
    std = variance ** 0.5
    if std <= MIN_RETURN_STD:
        return float("nan")
    return avg_return / std


def json_safe(payload: object) -> object:
    """Recursively replace non-finite floats with None so json.dumps is valid JSON.

    Python's json.dumps writes bare `NaN` / `Infinity` tokens, which RFC 8259
    does not allow. PowerShell and Python happen to parse them, so the breakage
    is invisible here and shows up in any other consumer (jq rejects the file
    outright).

    The non-finite values are not corruption to be scrubbed: NaN is how this
    module reports a metric that is genuinely undefined (fewer than
    MIN_TRADES_FOR_RISK_METRICS trades, zero return dispersion, an infinite
    profit factor with no losing trade). `null` preserves exactly that -- "no
    value" -- whereas coercing to 0.0 would read as a result.
    """
    if isinstance(payload, float):
        return payload if isfinite(payload) else None
    if isinstance(payload, Mapping):
        return {key: json_safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [json_safe(item) for item in payload]
    return payload


def compare_strategies(
    candles: Sequence[data.Candle],
    model: object | None = None,
    strategies: Mapping[str, live.StrategyConfig] | None = None,
    initial_equity: float = 10000.0,
    position_size: float = 0.1,
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
    maker_fee_rate_per_side: float = DEFAULT_MAKER_FEE_RATE_PER_SIDE,
    slippage_rate_per_side: float = DEFAULT_SLIPPAGE_RATE_PER_SIDE,
    models_by_regime: Mapping[str, object] | None = None,
    user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None,
    default_regime: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    feature_rows: Sequence[dataset.FeatureRow] | None = None,
    regime_detector: object | None = None,
    regime_classifier_model: object | None = None,
    multi_feature_regime_detector: object | None = None,
    exec_tp_pct: float | None = None,
    exec_sl_pct: float | None = None,
    threshold_floor: float = 0.0,
    label_horizon: int = 60,
    maker_exit_outcomes: Sequence[str] | None = None,
    sl_fill: str = "barrier",
    allow_barrier_mismatch: bool = False,
) -> dict[str, object]:
    """Backtest multiple strategies and return comparison."""
    if strategies is None:
        strategies = {
            "balanced": live.strategy_for_regime(None, "balanced"),
            "conservative": live.strategy_for_regime(None, "conservative"),
            "aggressive": live.strategy_for_regime(None, "aggressive"),
        }
    if not strategies:
        # An empty mapping used to surface as a StopIteration/ValueError from the
        # result aggregation, far from the caller that passed nothing to compare.
        raise ValueError("strategies must not be empty; there is nothing to compare")
    # Pre-compute feature rows once for all strategies
    if feature_rows is None:
        feature_rows = dataset.build_feature_rows(candles, user_regime_periods=user_regime_periods)
    # Apply real-time regime routing once on the shared feature rows so every
    # strategy sees identical regimes and the classifier/detector runs a
    # single time. See run_backtest's docstring-equivalent comment for why
    # the classifier model takes priority and why callers must pass the same
    # source that trained models_by_regime.
    if multi_feature_regime_detector is not None and user_regime_periods is None:
        import dataclasses as _dc
        detected = multi_feature_regime_detector.detect_all([r.features for r in feature_rows])
        feature_rows = [
            _dc.replace(row, user_regime=regime)
            for row, regime in zip(feature_rows, detected)
        ]
    elif regime_classifier_model is not None and user_regime_periods is None:
        import dataclasses as _dc
        from btcusdt_quant import mtf_features as _mtf, regime_classifier as _rc
        feature_rows_f17 = [_mtf.extract_feature_vector(r.features) for r in feature_rows]
        raw_probs, detected = _rc.route_regime_causal(feature_rows_f17, regime_classifier_model)
        # Inject the SAME regime_prob_up/range/down values entry models saw
        # as F18 features during training (merged from
        # regime_probabilities.json's walk-forward OOF output). Previously
        # only `detected` (the routing decision) was kept and these
        # probabilities were discarded, so backtest/live silently fed entry
        # models regime_prob_*=0.0 (the build_feature_rows default) while
        # training fed them real values -- a train/serve input-distribution
        # mismatch distinct from the routing bucket-assignment issue.
        feature_rows = [
            _dc.replace(
                row,
                user_regime=regime,
                features={
                    **row.features,
                    "regime_prob_up": probs["up"],
                    "regime_prob_range": probs["range"],
                    "regime_prob_down": probs["down"],
                },
            )
            for row, regime, probs in zip(feature_rows, detected, raw_probs)
        ]
    elif regime_detector is not None and user_regime_periods is None:
        import dataclasses as _dc
        trend_slopes = [float(r.features.get("trend_slope_30", 0.0)) for r in feature_rows]
        rv_values = [float(r.features.get("rv_15", 0.0)) for r in feature_rows]
        detected = regime_detector.detect_all_directional(rv_values, trend_slopes)
        feature_rows = [
            _dc.replace(row, user_regime=regime)
            for row, regime in zip(feature_rows, detected)
        ]
    # Before spending three full passes over the window: can the profiles even
    # produce different trades? When they cannot, run ONE (its numbers are still
    # a useful fixed-size baseline next to the Kelly-sized main backtest) and say
    # why the other arms were dropped, instead of reporting three identical rows
    # and crowning a winner from a tie.
    # long/short_threshold are None here on purpose: compare_strategies does not
    # take the CLI overrides and does not pass them to run_backtest, so the arms
    # resolve thresholds from the learned values or the profile. The fingerprint
    # must be computed against the SAME inputs the arms will actually run with.
    degenerate = indistinguishable_profiles(
        strategies,
        models_by_regime=models_by_regime,
        default_regime=default_regime,
        exec_tp_pct=exec_tp_pct,
        exec_sl_pct=exec_sl_pct,
        threshold_floor=threshold_floor,
    )
    evaluated = strategies
    if degenerate is not None:
        # Run the arm the main backtest itself uses when it is one of them, so
        # the surviving row is labeled with the profile the run actually shipped
        # rather than whichever name sorted first.
        arm = "balanced" if "balanced" in strategies else sorted(strategies)[0]
        evaluated = {arm: strategies[arm]}

    results: dict[str, BacktestResult] = {}
    for name, strategy in evaluated.items():
        results[name] = run_backtest(
            candles,
            model,
            strategy,
            initial_equity,
            position_size,
            fee_rate_per_side=fee_rate_per_side,
            maker_fee_rate_per_side=maker_fee_rate_per_side,
            maker_exit_outcomes=maker_exit_outcomes,
            sl_fill=sl_fill,
            slippage_rate_per_side=slippage_rate_per_side,
            models_by_regime=models_by_regime,
            user_regime_periods=user_regime_periods,
            default_regime=default_regime,
            start_date=start_date,
            end_date=end_date,
            feature_rows=feature_rows,
            exec_tp_pct=exec_tp_pct,
            exec_sl_pct=exec_sl_pct,
            threshold_floor=threshold_floor,
            label_horizon=label_horizon,
            allow_barrier_mismatch=allow_barrier_mismatch,
        )

    # best_strategy is None when the profiles were indistinguishable: there was
    # no contest, and naming a winner of one is how a no-op reads as a finding.
    best_strategy = None if degenerate is not None else max(results, key=lambda k: results[k].total_return)
    evaluated_name = next(iter(results))
    return {
        # Comparison runs are ALWAYS fixed-size (kelly_config is not plumbed
        # here); labeled so a Kelly-sized main backtest in the same summary
        # JSON is not mistaken for an apples-to-apples row.
        "sizing": "fixed_position_size",
        "indistinguishable_profiles": degenerate is not None,
        "indistinguishable_reason": degenerate,
        # Which profiles were actually backtested. Under degeneracy this is the
        # single arm that ran; the others would have reproduced it exactly.
        "profiles_evaluated": sorted(results),
        "profiles_requested": sorted(strategies),
        "best_strategy": best_strategy,
        "best_total_return": results[best_strategy or evaluated_name].total_return,
        "best_gross_total_return": results[best_strategy or evaluated_name].gross_total_return,
        "best_win_rate": results[best_strategy or evaluated_name].win_rate,
        "comparison": {
            name: {
                "total_return": r.total_return,
                "net_total_return": r.total_return,
                "gross_total_return": r.gross_total_return,
                "cost_impact_return": r.gross_total_return - r.total_return,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "max_drawdown": r.max_drawdown,
                "sharpe": r.sharpe,
                "net_sharpe": r.sharpe,
                "gross_sharpe": r.gross_sharpe,
                "cost_impact_sharpe": r.gross_sharpe - r.sharpe,
                "trade_count": r.trade_count,
                "total_fees": r.total_fees,
                "total_slippage": r.total_slippage,
                "total_costs": r.total_costs,
            }
            for name, r in results.items()
        },
    }
