from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping, Sequence

from . import data, dataset, features, live


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
        from datetime import datetime as _dt
        _s = _dt.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
        _e = _parse_end_exclusive(end_date) if end_date else None
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


DEFAULT_FEE_RATE_PER_SIDE = 0.0002
DEFAULT_SLIPPAGE_RATE_PER_SIDE = 0.0002
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


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    total_return: float = 0.0
    gross_total_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    trade_count: int = 0
    signal_counts: dict[str, int] = field(default_factory=dict)
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE
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

    def as_dict(self) -> dict[str, object]:
        return {
            "total_return": self.total_return,
            "net_total_return": self.total_return,
            "gross_total_return": self.gross_total_return,
            "cost_impact_return": self.gross_total_return - self.total_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "trade_count": len(self.trades),
            "signal_counts": self.signal_counts,
            "fee_rate_per_side": self.fee_rate_per_side,
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
                }
                for t in self.trades
            ],
        }


def _validate_cost_rates(fee_rate_per_side: float, slippage_rate_per_side: float) -> None:
    if not isfinite(fee_rate_per_side):
        raise ValueError("fee_rate_per_side must be finite")
    if not isfinite(slippage_rate_per_side):
        raise ValueError("slippage_rate_per_side must be finite")
    if fee_rate_per_side < 0.0:
        raise ValueError("fee_rate_per_side must be non-negative")
    if slippage_rate_per_side < 0.0:
        raise ValueError("slippage_rate_per_side must be non-negative")


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
) -> tuple[float, float, float]:
    gross_pnl_pct = _trade_gross_pnl_pct(trade, exit_price)
    fee_pct = fee_rate_per_side * 2.0
    slippage_pct = slippage_rate_per_side * 2.0
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
) -> BacktestResult:
    """Run a simple backtest on historical candles.

    Parameters
    ----------
    candles: historical 1m candles
    model: trained model (optional; if None, uses random signals)
    strategy: strategy config for thresholds and TP/SL (defaults to balanced)
    initial_equity: starting equity
    position_size: fraction of equity per trade
    tp_sl_method: 'fixed_pct' or 'atr_pct'
    label_horizon: bars to hold before forced exit
    min_hold_bars: minimum bars to hold before allowing TP/SL exit
    cooldown_bars: bars to wait after exit before re-entry
    long_threshold: override strategy long threshold (default uses strategy.long_threshold)
    short_threshold: override strategy short threshold (default uses strategy.short_threshold)
    """
    if strategy is None:
        strategy = live.strategy_for_regime(None, "balanced")
    if exec_tp_pct is not None and exec_sl_pct is not None:
        # Align EXECUTION barriers with the model's LABEL barriers: force fixed
        # (non-ATR) TP/SL equal to the triple-barrier tp_pct/sl_pct the model was
        # trained on. Without this the backtest executed ATR-based barriers
        # (e.g. ~0.84%/0.42%) while the model predicted a +0.30%/-0.15% outcome,
        # a train/execution mismatch. Pass the SAME tp/sl used for --tp-pct/--sl-pct.
        import dataclasses as _dc
        strategy = _dc.replace(
            strategy,
            tp_pct=exec_tp_pct,
            sl_pct=exec_sl_pct,
            min_tp_floor_pct=exec_tp_pct,
            min_sl_floor_pct=exec_sl_pct,
            use_atr_pricing=False,
        )
    _validate_cost_rates(fee_rate_per_side, slippage_rate_per_side)
    if label_horizon <= 0:
        raise ValueError("label_horizon must be positive")
    if min_hold_bars < 0:
        raise ValueError("min_hold_bars must be non-negative")
    if min_hold_bars > label_horizon:
        raise ValueError("min_hold_bars must not exceed label_horizon")
    if cooldown_bars < 0:
        raise ValueError("cooldown_bars must be non-negative")
    result = BacktestResult()
    result.fee_rate_per_side = fee_rate_per_side
    result.slippage_rate_per_side = slippage_rate_per_side
    result.round_trip_cost_pct = 2.0 * (fee_rate_per_side + slippage_rate_per_side)
    result.min_hold_bars = min_hold_bars
    result.cooldown_bars = cooldown_bars
    result.threshold_floor = threshold_floor
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
    returns: list[float] = []

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
            from datetime import datetime as _dt
            _diag_start = _dt.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
            _diag_end = _parse_end_exclusive(end_date) if end_date else None
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

    start_dt = None
    end_dt = None
    if start_date is not None or end_date is not None:
        from datetime import datetime
        if start_date is not None:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        if end_date is not None:
            # Without an explicit end the backtest silently runs to END OF FILE.
            # end_date closes the window explicitly. Date-only values include
            # the whole final day (exclusive next-midnight bound).
            end_dt = _parse_end_exclusive(end_date)

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
                    allowed_directions = apply_range_mean_reversion_gate(regime, features_dict, allowed_directions)
                    
                    long_prob = None
                    short_prob = None
                    
                    if "LONG" in allowed_directions and hasattr(regime_bundle, 'long_models') and regime in regime_bundle.long_models:
                        long_prob = regime_bundle.long_models[regime].probability(features_dict)
                    
                    if "SHORT" in allowed_directions and hasattr(regime_bundle, 'short_models') and regime in regime_bundle.short_models:
                        short_prob = regime_bundle.short_models[regime].probability(features_dict)
                    
                    if long_prob is not None or short_prob is not None:
                        from btcusdt_quant.live import evaluate_entry_signal
                        long_prob = long_prob if long_prob is not None else 0.0
                        short_prob = short_prob if short_prob is not None else 0.0
                        
                        lt, st = _resolve_backtest_thresholds(regime_bundle, regime, long_threshold, short_threshold, strategy, threshold_floor)
                        _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = regime, long_prob, short_prob, lt, st
                        
                        entry_signal, _, _ = evaluate_entry_signal(
                            long_prob, short_prob,
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
                    allowed_directions = apply_range_mean_reversion_gate(default_regime, features_dict, allowed_directions)
                    long_prob = None
                    short_prob = None
                    if "LONG" in allowed_directions and hasattr(regime_bundle, 'long_models') and default_regime in regime_bundle.long_models:
                        long_prob = regime_bundle.long_models[default_regime].probability(features_dict)
                    if "SHORT" in allowed_directions and hasattr(regime_bundle, 'short_models') and default_regime in regime_bundle.short_models:
                        short_prob = regime_bundle.short_models[default_regime].probability(features_dict)
                    if long_prob is not None or short_prob is not None:
                        from btcusdt_quant.live import evaluate_entry_signal
                        long_prob = long_prob if long_prob is not None else 0.0
                        short_prob = short_prob if short_prob is not None else 0.0
                        lt, st = _resolve_backtest_thresholds(regime_bundle, default_regime, long_threshold, short_threshold, strategy, threshold_floor)
                        _ctx_regime, _ctx_long_prob, _ctx_short_prob, _ctx_lt, _ctx_st = default_regime, long_prob, short_prob, lt, st
                        entry_signal, _, _ = evaluate_entry_signal(
                            long_prob, short_prob, long_threshold=lt, short_threshold=st,
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
            if prob > lt:
                signal = "BUY"
            elif prob < st:
                signal = "SELL"
            else:
                signal = "HOLD"

        result.signal_counts[signal] += 1

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

                equity, gross_equity, pnl_pct = _close_trade(
                    active_trade,
                    candle.open_time.isoformat(),
                    exit_price,
                    outcome,
                    equity,
                    gross_equity,
                    position_size,
                    fee_rate_per_side,
                    slippage_rate_per_side,
                )
                result.total_fees += active_trade.fee_paid
                result.total_slippage += active_trade.slippage_paid
                result.total_costs += active_trade.cost_paid
                peak_equity = max(peak_equity, equity)
                max_drawdown_pct = max(max_drawdown_pct, 1.0 - equity / peak_equity if peak_equity > 0 else 0.0)
                result.trades.append(active_trade)
                returns.append(pnl_pct)
                active_trade = None
                bar_count = 0
                if cooldown_bars > 0:
                    next_entry_index = i + cooldown_bars + 1

        # Enter new trade
        if active_trade is None and signal in {"BUY", "SELL"} and i >= next_entry_index:
            entry_price = candle.close
            tp_price, sl_price, decision = live.optimized_tp_sl(
                entry_price, signal, feature_rows[i].features if i < len(feature_rows) else {}, strategy
            )
            active_trade = BacktestTrade(
                entry_time=candle.open_time.isoformat(),
                exit_time="",
                side=signal,
                entry_price=entry_price,
                exit_price=0.0,
                tp_price=tp_price,
                sl_price=sl_price,
                pnl_pct=0.0,
                outcome="",
                strategy=strategy.name,
                entry_regime=_ctx_regime,
                long_probability=_ctx_long_prob,
                short_probability=_ctx_short_prob,
                used_threshold=_ctx_lt if signal == "BUY" else _ctx_st,
                model_side="long" if signal == "BUY" else "short",
                entry_probability=_ctx_long_prob if signal == "BUY" else _ctx_short_prob,
            )

    # Close any remaining open trade at the last IN-WINDOW candle (not the
    # file's last candle, which may lie past the backtest window).
    if active_trade is not None and last_in_window_candle is not None:
        last_candle = last_in_window_candle
        exit_price = last_candle.close
        equity, gross_equity, pnl_pct = _close_trade(
            active_trade,
            last_candle.open_time.isoformat(),
            exit_price,
            "OPEN_AT_END",
            equity,
            gross_equity,
            position_size,
            fee_rate_per_side,
            slippage_rate_per_side,
        )
        result.total_fees += active_trade.fee_paid
        result.total_slippage += active_trade.slippage_paid
        result.total_costs += active_trade.cost_paid
        peak_equity = max(peak_equity, equity)
        max_drawdown_pct = max(max_drawdown_pct, 1.0 - equity / peak_equity if peak_equity > 0 else 0.0)
        result.trades.append(active_trade)
        returns.append(pnl_pct)

    # Compute metrics
    result.total_return = (equity - initial_equity) / initial_equity
    result.gross_total_return = (gross_equity - initial_equity) / initial_equity
    result.trade_count = len(result.trades)
    if result.trades:
        wins = sum(1 for t in result.trades if t.pnl_pct > 0)
        result.win_rate = wins / len(result.trades)
        gross_profit = sum(t.pnl_pct for t in result.trades if t.pnl_pct > 0)
        gross_loss = abs(sum(t.pnl_pct for t in result.trades if t.pnl_pct < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    result.max_drawdown = max_drawdown_pct
    if returns:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std = variance ** 0.5
        result.sharpe = avg_return / std if std > 0 else 0.0
    return result


def compare_strategies(
    candles: Sequence[data.Candle],
    model: object | None = None,
    strategies: Mapping[str, live.StrategyConfig] | None = None,
    initial_equity: float = 10000.0,
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
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
) -> dict[str, object]:
    """Backtest multiple strategies and return comparison."""
    if strategies is None:
        strategies = {
            "balanced": live.strategy_for_regime(None, "balanced"),
            "conservative": live.strategy_for_regime(None, "conservative"),
            "aggressive": live.strategy_for_regime(None, "aggressive"),
        }
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
    results: dict[str, BacktestResult] = {}
    for name, strategy in strategies.items():
        results[name] = run_backtest(
            candles,
            model,
            strategy,
            initial_equity,
            fee_rate_per_side=fee_rate_per_side,
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
        )

    best_strategy = max(results, key=lambda k: results[k].total_return)
    return {
        "best_strategy": best_strategy,
        "best_total_return": results[best_strategy].total_return,
        "best_gross_total_return": results[best_strategy].gross_total_return,
        "best_win_rate": results[best_strategy].win_rate,
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
                "trade_count": r.trade_count,
                "total_fees": r.total_fees,
                "total_slippage": r.total_slippage,
                "total_costs": r.total_costs,
            }
            for name, r in results.items()
        },
    }
