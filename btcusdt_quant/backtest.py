from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from . import data, dataset, features, live, training


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


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    total_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    trade_count: int = 0
    signal_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "total_return": self.total_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "trade_count": len(self.trades),
            "signal_counts": self.signal_counts,
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
                    "outcome": t.outcome,
                    "strategy": t.strategy,
                }
                for t in self.trades
            ],
        }


def run_backtest(
    candles: Sequence[data.Candle],
    model: training.LinearClassifier | None,
    strategy: live.StrategyConfig,
    initial_equity: float = 10000.0,
    position_size: float = 0.1,
    tp_sl_method: str = "fixed_pct",
    label_horizon: int = 15,
) -> BacktestResult:
    """Run a simple backtest on historical candles.

    Parameters
    ----------
    candles: historical 1m candles
    model: trained model (optional; if None, uses random signals)
    strategy: strategy config for thresholds and TP/SL
    initial_equity: starting equity
    position_size: fraction of equity per trade
    tp_sl_method: 'fixed_pct' or 'atr_pct'
    label_horizon: bars to hold before forced exit
    """
    result = BacktestResult()
    equity = initial_equity
    peak_equity = initial_equity
    active_trade: BacktestTrade | None = None
    bar_count = 0
    returns: list[float] = []

    feature_rows = dataset.build_feature_rows(candles)

    for i, candle in enumerate(candles):
        result.signal_counts.setdefault("HOLD", 0)
        result.signal_counts.setdefault("BUY", 0)
        result.signal_counts.setdefault("SELL", 0)

        # Model inference
        if model is not None and i < len(feature_rows):
            features_dict = feature_rows[i].features
            prob = model.probability(features_dict)
            signal = live.select_signal(prob, "ranging", strategy, reward_risk=2.0)
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

            if hit_tp or hit_sl or bar_count >= label_horizon:
                if hit_tp:
                    exit_price = active_trade.tp_price
                    outcome = "TP"
                elif hit_sl:
                    exit_price = active_trade.sl_price
                    outcome = "SL"
                else:
                    outcome = "TIMEOUT"

                if active_trade.side == "BUY":
                    pnl_pct = (exit_price - active_trade.entry_price) / active_trade.entry_price
                else:
                    pnl_pct = (active_trade.entry_price - exit_price) / active_trade.entry_price

                trade_pnl = pnl_pct * position_size * equity
                equity += trade_pnl
                peak_equity = max(peak_equity, equity)
                active_trade.exit_time = candle.open_time.isoformat()
                active_trade.exit_price = exit_price
                active_trade.pnl_pct = pnl_pct
                active_trade.outcome = outcome
                result.trades.append(active_trade)
                returns.append(pnl_pct)
                active_trade = None
                bar_count = 0

        # Enter new trade
        if active_trade is None and signal in {"BUY", "SELL"}:
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
        if active_trade.side == "BUY":
            pnl_pct = (exit_price - active_trade.entry_price) / active_trade.entry_price
        else:
            pnl_pct = (active_trade.entry_price - exit_price) / active_trade.entry_price
        trade_pnl = pnl_pct * position_size * equity
        equity += trade_pnl
        active_trade.exit_time = last_candle.open_time.isoformat()
        active_trade.exit_price = exit_price
        active_trade.pnl_pct = pnl_pct
        active_trade.outcome = "OPEN_AT_END"
        result.trades.append(active_trade)
        returns.append(pnl_pct)

    # Compute metrics
    result.total_return = (equity - initial_equity) / initial_equity
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
    model: training.LinearClassifier | None,
    strategies: Mapping[str, live.StrategyConfig],
    initial_equity: float = 10000.0,
) -> dict[str, object]:
    """Backtest multiple strategies and return comparison."""
    results: dict[str, BacktestResult] = {}
    for name, strategy in strategies.items():
        results[name] = run_backtest(candles, model, strategy, initial_equity)

    best_strategy = max(results, key=lambda k: results[k].total_return)
    return {
        "best_strategy": best_strategy,
        "best_total_return": results[best_strategy].total_return,
        "best_win_rate": results[best_strategy].win_rate,
        "comparison": {
            name: {
                "total_return": r.total_return,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "max_drawdown": r.max_drawdown,
                "sharpe": r.sharpe,
                "trade_count": r.trade_count,
            }
            for name, r in results.items()
        },
    }
