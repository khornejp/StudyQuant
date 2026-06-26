from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

from . import data, dataset, features, live, training


DEFAULT_FEE_RATE_PER_SIDE = 0.0002
DEFAULT_SLIPPAGE_RATE_PER_SIDE = 0.0002
DEFAULT_ROUND_TRIP_COST_PCT = 2.0 * (DEFAULT_FEE_RATE_PER_SIDE + DEFAULT_SLIPPAGE_RATE_PER_SIDE)


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
    fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
    slippage_rate_per_side: float = DEFAULT_SLIPPAGE_RATE_PER_SIDE,
    models_by_regime: Mapping[str, object] | None = None,
    user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None,
    default_regime: str | None = None,
    start_date: str | None = None,
    feature_rows: Sequence[dataset.FeatureRow] | None = None,
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
    equity = initial_equity
    gross_equity = initial_equity
    peak_equity = initial_equity
    active_trade: BacktestTrade | None = None
    bar_count = 0
    next_entry_index = 0
    returns: list[float] = []

    if feature_rows is None:
        feature_rows = dataset.build_feature_rows(candles, user_regime_periods=user_regime_periods)

    start_dt = None
    if start_date is not None:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)

    for i, candle in enumerate(candles):
        # Skip trading before start_date (but feature_rows still computed with full history)
        if start_dt is not None and candle.open_time < start_dt:
            continue

        result.signal_counts.setdefault("HOLD", 0)
        result.signal_counts.setdefault("BUY", 0)
        result.signal_counts.setdefault("SELL", 0)

        # Model inference (regime-aware if models_by_regime provided)
        signal = "HOLD"
        if models_by_regime is not None and i < len(feature_rows):
            regime = feature_rows[i].user_regime
            if regime is not None and regime in models_by_regime:
                # Check if models_by_regime is a RegimeModelBundle with direction policy
                regime_bundle = models_by_regime.get(regime)
                if hasattr(regime_bundle, 'direction_policy'):
                    # New structure: RegimeModelBundle with long/short models
                    allowed_directions = regime_bundle.direction_policy.get(regime, {"LONG", "SHORT"})
                    features_dict = feature_rows[i].features
                    
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
                        
                        lt = long_threshold if long_threshold is not None else strategy.long_threshold
                        st = short_threshold if short_threshold is not None else strategy.short_threshold
                        
                        entry_signal, _, _ = evaluate_entry_signal(
                            long_prob, short_prob,
                            long_threshold=lt,
                            short_threshold=st,
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
                    lt = long_threshold if long_threshold is not None else strategy.long_threshold
                    st = short_threshold if short_threshold is not None else strategy.short_threshold
                    if prob > lt and prob >= 0.55:
                        signal = "BUY"
                    elif prob < st and prob <= 0.45:
                        signal = "SELL"
                    else:
                        signal = "HOLD"
            elif default_regime is not None and default_regime in models_by_regime:
                # Use default regime model
                active_model = models_by_regime[default_regime]
                features_dict = feature_rows[i].features
                prob = active_model.probability(features_dict)
                lt = long_threshold if long_threshold is not None else strategy.long_threshold
                st = short_threshold if short_threshold is not None else strategy.short_threshold
                if prob > lt and prob >= 0.55:
                    signal = "BUY"
                elif prob < st and prob <= 0.45:
                    signal = "SELL"
                else:
                    signal = "HOLD"
        elif model is not None and i < len(feature_rows):
            features_dict = feature_rows[i].features
            prob = model.probability(features_dict)
            lt = long_threshold if long_threshold is not None else strategy.long_threshold
            st = short_threshold if short_threshold is not None else strategy.short_threshold
            if prob > lt and prob >= 0.55:
                signal = "BUY"
            elif prob < st and prob <= 0.45:
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
                if hit_tp and can_exit_for_barrier:
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
            )

    # Close any remaining open trade at last candle
    if active_trade is not None:
        last_candle = candles[-1]
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
    result.max_drawdown = 1.0 - equity / peak_equity if peak_equity > 0 else 0.0
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
    feature_rows: Sequence[dataset.FeatureRow] | None = None,
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
            feature_rows=feature_rows,
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
