#!/usr/bin/env python3
"""Compare two backtest_summary.json runs, broken down by regime and side.

The pipeline tells the operator to judge Phase 4 (regime model) against
Phase 4.5 (multi-horizon pilot) "on net sharpe / MDD", but nothing else in
the repo aggregates PnL by the axes that actually explain a difference:
which regime routed the trade, and which side it took. Everything needed is
already in backtest_summary.json's trades[] (entry_regime, model_side,
trade_return_pct), so this reads the two summaries and prints the split.

Returns come from `trade_return_pct` -- the EQUITY return (pnl scaled by the
fraction actually bet), not the price return -- so a Kelly-sized run is
summarized on what the account really earned.

Two return columns, because they answer different questions:
  sum_ret  = sum of the subset's trade returns. Additive, so subsets sum to
             the whole: this is each bucket's CONTRIBUTION.
  comp_ret = (1+r1)(1+r2)... - 1 over the subset alone. This is what a
             standalone account trading ONLY that subset would have made; it
             does NOT sum across buckets, and for the full set it still is
             not the reported net_total_return because the real account
             compounds trades in time order at varying size.
Neither equals `net_total_return`, which is read straight from the summary.

Sharpe here is the same per-trade mean/std the backtest reports (no
annualization), so the headline numbers reconcile with backtest_summary.json.

Usage:
    python compare_backtests.py \
        artifacts/backtest_results/backtest_summary.json \
        artifacts/backtest_results_multi_horizon/backtest_summary.json

    # single run, just the breakdown
    python compare_backtests.py artifacts/backtest_results/backtest_summary.json

Run it from the repo root: the per-trade Sharpe is imported from
btcusdt_quant.backtest rather than reimplemented here, because this report's
numbers are meant to reconcile with backtest_summary.json and a second copy of
the formula was free to drift from it.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from btcusdt_quant.backtest import per_trade_sharpe

# run_config fields that must match for two runs to be comparable at all.
# A difference here means the runs traded different windows, barriers, or
# sizing, so no metric below is a like-for-like comparison.
COMPARABILITY_KEYS: tuple[str, ...] = (
    "backtest_start",
    "backtest_end",
    "execution_horizon",
    "exec_tp_pct",
    "exec_sl_pct",
    # The whole StrategyConfig: thresholds, ATR multipliers, TP/SL floors and
    # use_atr_pricing all change the barrier actually executed.
    "strategy_config",
    "long_threshold_override",
    "short_threshold_override",
    "position_size",
    "initial_equity",
    "tp_sl_method",
    "kelly_enabled",
    "kelly_multiplier",
    "kelly_lookback_bars",
    "kelly_holding_period_bars",
)

# Top-level result fields with the same requirement.
COMPARABILITY_TOP_KEYS: tuple[str, ...] = (
    "round_trip_cost_pct",
    "min_hold_bars",
    "cooldown_bars",
    "threshold_floor",
)


def _sharpe(returns: list[float]) -> float:
    """Per-trade Sharpe of a slice, using the backtest's own formula.

    Imported rather than reimplemented: this report's numbers are meant to
    reconcile with backtest_summary.json, and a second copy of the formula was
    free to drift from it (it already carried its own copy of the noise floor).

    backtest.py's MIN_TRADES_FOR_RISK_METRICS floor is deliberately NOT applied
    here: the breakdown cells are narrow by construction (regime x side x
    month), and the n= column next to each one already shows the sample size.
    """
    return per_trade_sharpe(returns)


def _profit_factor(returns: list[float]) -> float:
    """NaN for an empty slice -- undefined, not 0.0.

    0.0 is the value of the WORST possible slice (every trade a loser), so a
    grid cell that simply had no trades used to print `pf 0.00` and read as a
    catastrophe. _sharpe already returns NaN there; this now matches.
    """
    if not returns:
        return float("nan")
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def _reported(backtest: dict, key: str, spec: str) -> str:
    """Format a metric READ FROM the summary, which may legitimately be null.

    backtest.py reports an undefined risk metric (fewer trades than
    risk_metrics_min_trades, zero return dispersion, no losing trade) as
    NaN/inf, and those serialize to `null`. Defaulting a missing key to 0.0
    would print a metric that was never computed as if it were flat.
    """
    value = backtest.get(key)
    if value is None:
        return "n/a"
    return format(float(value), spec)


def _compounded(returns: list[float]) -> float:
    """Standalone compounded return of this subset, in trade order."""
    equity = 1.0
    for r in returns:
        equity *= 1.0 + r
    return equity - 1.0


def _stats(returns: list[float]) -> dict[str, float]:
    wins = sum(1 for r in returns if r > 0)
    return {
        "trades": len(returns),
        "sum_trade_returns": sum(returns),
        "compounded_subset_return": _compounded(returns),
        # NaN, not 0.0, on an empty slice: 0% is the win rate of a cell where
        # every trade lost, and an empty cell has no win rate at all. _sharpe and
        # _profit_factor already say NaN there.
        "win_rate": wins / len(returns) if returns else float("nan"),
        "sharpe": _sharpe(returns),
        "profit_factor": _profit_factor(returns),
    }


def _fmt(s: dict[str, float]) -> str:
    pf = s["profit_factor"]
    pf_text = "inf" if math.isinf(pf) else f"{pf:.2f}"
    return (
        f"n={int(s['trades']):>6}  sum_ret={s['sum_trade_returns']:+8.4%}  "
        f"comp_ret={s['compounded_subset_return']:+8.4%}  "
        f"win={s['win_rate']:6.1%}  sharpe={s['sharpe']:+7.4f}  pf={pf_text:>6}"
    )


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    backtest = payload.get("backtest")
    if backtest is None:
        raise ValueError(f"{path} has no 'backtest' key (is this a backtest_summary.json?)")
    return backtest


def _returns(trade: dict) -> float:
    """Equity return of a trade, falling back to price return on old artifacts."""
    value = trade.get("trade_return_pct")
    if value is None:
        # Pre-size-weighting artifact: price return, valid only for fixed size.
        return float(trade.get("net_pnl_pct", trade.get("pnl_pct", 0.0)))
    return float(value)


def _has_equity_returns(trades: list[dict]) -> bool:
    return bool(trades) and all(t.get("trade_return_pct") is not None for t in trades)


def _reconcile(trades: list[dict], backtest: dict) -> None:
    """The trade list must reproduce the reported account return, exactly.

    _close_trade advances equity by `net_pnl_pct * position_size * equity`, and
    `trade_return_pct` IS `net_pnl_pct * position_size`, so
    equity_next = equity * (1 + trade_return_pct). Only one trade is open at a
    time, so the whole run telescopes into prod(1 + trade_return_pct) - 1 ==
    net_total_return -- even under Kelly, where the size varies per trade.
    A mismatch means the trades[] array and the equity curve disagree: a
    corrupted artifact, a serialization bug, or a sizing field that stopped
    feeding the equity update.

    Skipped for legacy artifacts without trade_return_pct, where the fallback
    is a price return that legitimately does not compound to the equity result.
    """
    if not _has_equity_returns(trades):
        print("  reconcile     skipped (legacy artifact: no trade_return_pct on every trade)")
        return
    compounded = _compounded([_returns(t) for t in trades])
    reported = float(backtest.get("net_total_return", 0.0))
    # The equity curve accumulates in dollar space while this compounds in unit
    # space, so the two drift by ~n*eps (~1e-11 over 50k trades). A pure
    # rel_tol collapses to abs_tol near break-even -- exactly where a
    # cost-heavy, high-turnover strategy lands -- so abs_tol must sit above
    # that float noise. 1e-9 of return is 1e-7 of a percent: far below anything
    # worth reading, and ~100x above the drift.
    if not math.isclose(compounded, reported, rel_tol=1e-9, abs_tol=1e-9):
        print(f"  RECONCILE FAIL compounded trade returns={compounded:+.10f} != net_total_return={reported:+.10f} "
              f"(diff {abs(compounded - reported):.3e})")
        print("                 the trades[] array does not reproduce the equity curve -- treat every")
        print("                 number in this report as suspect until the artifact is regenerated")
    else:
        print(f"  reconcile     OK (compounded trade returns == net_total_return, diff {abs(compounded - reported):.1e})")


def _threshold_report(backtest: dict) -> None:
    """Did the floor override what training learned?

    A threshold-selection change (e.g. --threshold-horizon) only reaches
    execution for the sides whose learned value clears --threshold-floor.
    Where the floor binds, the learned threshold was discarded and the run
    says nothing about the training change.
    """
    effective = backtest.get("effective_thresholds") or {}
    if not effective:
        return
    floor = backtest.get("threshold_floor", 0.0)
    print(f"\n  thresholds (floor={floor})")
    bound = 0
    total = 0
    for regime in sorted(effective):
        row = effective[regime] or {}
        for side in ("long", "short"):
            learned = row.get(f"learned_{side}")
            eff = row.get(f"effective_{side}")
            if eff is None:
                continue
            if learned is None:
                # Side never trained for this regime (direction policy), so
                # there is no learned value the floor could have overridden.
                note = "no learned value (side not trained)"
            else:
                total += 1
                if abs(float(learned) - float(eff)) > 1e-9:
                    note = "FLOOR/OVERRIDE BINDS -- learned value discarded"
                    bound += 1
                else:
                    note = "learned value used"
            learned_text = "    n/a" if learned is None else f"{float(learned):7.4f}"
            print(f"    {regime + '/' + side:<14} learned={learned_text}  effective={float(eff):7.4f}   {note}")
    if total and bound == total:
        print("    WARNING: every threshold was overridden -- this run cannot show the effect")
        print("             of any threshold-selection change (lower --threshold-floor to see it)")


def summarize(name: str, backtest: dict) -> None:
    trades = backtest.get("trades", [])
    print(f"\n{'=' * 88}\n{name}\n{'=' * 88}")

    config = backtest.get("run_config") or {}
    if config:
        strategy = config.get("strategy_config") or {}
        print(f"  window={config.get('backtest_start')}..{config.get('backtest_end')}  "
              f"exec_horizon={config.get('execution_horizon')}  "
              f"tp/sl={config.get('exec_tp_pct')}/{config.get('exec_sl_pct')}  "
              f"pos_size={config.get('position_size')}  kelly={config.get('kelly_enabled')}")
        print(f"  strategy={strategy.get('name')}  atr_pricing={strategy.get('use_atr_pricing')}  "
              f"thresholds={strategy.get('long_threshold')}/{strategy.get('short_threshold')}  "
              f"overrides={config.get('long_threshold_override')}/{config.get('short_threshold_override')}")
    else:
        print("  (no run_config in this artifact -- regenerate to enable comparability checks)")

    # A regime whose side model is entirely ABSENT emits no signal on that
    # side, so the kelly skip counters stay 0 and only this field records that
    # the run was one-directional there. Printed before the no-trades return so
    # an all-refused one-directional run still surfaces it.
    missing = backtest.get("missing_side_models") or {}
    if missing:
        detail = ", ".join(f"{regime}/{'+'.join(sides)}" for regime, sides in sorted(missing.items()))
        print(f"  WARNING       missing side models: {detail} -- one-directional in those regimes, NOT comparable")

    if not trades:
        print("  no trades")
        _threshold_report(backtest)
        return

    overall = [_returns(t) for t in trades]
    print(f"  OVERALL       {_fmt(_stats(overall))}")
    print(f"  reported      net_total_return={_reported(backtest, 'net_total_return', '+.4%')}  "
          f"net_sharpe={_reported(backtest, 'net_sharpe', '+.4f')}  "
          f"gross_sharpe={_reported(backtest, 'gross_sharpe', '+.4f')}  "
          f"max_drawdown={_reported(backtest, 'max_drawdown', '.4%')}")
    print("  (net_total_return is the real compounded account result; per-bucket sum_ret/comp_ret")
    print("   below are contribution and standalone-subset views, and will not equal it)")
    _reconcile(trades, backtest)

    kelly = backtest.get("kelly_sizing") or {}
    if kelly.get("enabled"):
        print(f"  kelly         avg_frac={kelly.get('avg_fraction', 0):.4f} "
              f"(cap={kelly.get('cap')})  skipped_no_edge={kelly.get('entries_skipped_no_edge', 0)}")
        shorts = kelly.get("shorts_skipped_no_short_model", 0)
        longs = kelly.get("longs_skipped_no_long_model", 0)
        if shorts:
            print(f"  WARNING       {shorts} SELL signals refused (no short-success model): this run is LONG-ONLY")
        if longs:
            print(f"  WARNING       {longs} BUY signals refused (no long-success model): this run is SHORT-ONLY")

    by_regime: dict[str, list[float]] = defaultdict(list)
    by_side: dict[str, list[float]] = defaultdict(list)
    by_cell: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_month: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        regime = trade.get("entry_regime") or "(none)"
        side = trade.get("model_side") or trade.get("side") or "(none)"
        value = _returns(trade)
        by_regime[regime].append(value)
        by_side[side].append(value)
        by_cell[(regime, side)].append(value)
        entry = str(trade.get("entry_time", ""))
        if len(entry) >= 7:
            by_month[entry[:7]].append(value)

    print("\n  by regime")
    for key in sorted(by_regime):
        print(f"    {key:<14} {_fmt(_stats(by_regime[key]))}")
    print("\n  by side")
    for key in sorted(by_side):
        print(f"    {key:<14} {_fmt(_stats(by_side[key]))}")
    print("\n  by regime x side")
    for regime, side in sorted(by_cell):
        print(f"    {regime + '/' + side:<14} {_fmt(_stats(by_cell[(regime, side)]))}")
    if len(by_month) > 1:
        print("\n  by month")
        for key in sorted(by_month):
            print(f"    {key:<14} {_fmt(_stats(by_month[key]))}")

    _threshold_report(backtest)


def _comparability_warnings(a: dict, b: dict) -> list[str]:
    warnings: list[str] = []
    for key in COMPARABILITY_TOP_KEYS:
        if a.get(key) != b.get(key):
            warnings.append(f"{key} differs ({a.get(key)} vs {b.get(key)})")
    cfg_a = a.get("run_config") or {}
    cfg_b = b.get("run_config") or {}
    if not cfg_a or not cfg_b:
        warnings.append("run_config missing from at least one artifact -- cannot verify the runs are comparable")
    else:
        for key in COMPARABILITY_KEYS:
            if cfg_a.get(key) != cfg_b.get(key):
                warnings.append(f"run_config.{key} differs ({cfg_a.get(key)} vs {cfg_b.get(key)})")
    return warnings


def head_to_head(path_a: Path, a: dict, path_b: Path, b: dict) -> None:
    print(f"\n{'=' * 88}\nHEAD TO HEAD\n{'=' * 88}")
    warnings = _comparability_warnings(a, b)
    if warnings:
        print("  NOT LIKE-FOR-LIKE:")
        for warning in warnings:
            print(f"    - {warning}")
    else:
        print("  run_config and cost/gating settings match on every checked field")

    print(f"\n  {'metric':<20} {'A':>14} {'B':>14}   winner")
    # Higher is better unless noted. trade_count is deliberately NOT scored:
    # more trades is not better (a model can churn its way to a worse PF), it
    # is context for reading the per-trade metrics beside it.
    scored = (
        ("net_total_return", True),
        ("net_sharpe", True),
        ("gross_sharpe", True),
        ("profit_factor", True),
        ("max_drawdown", False),
        ("win_rate", True),
    )
    for key, higher_is_better in scored:
        # A metric can be null (undefined: too few trades, zero dispersion) or
        # NaN on a legacy artifact. Either way there is nothing to score, and
        # neither can be fed to a numeric format.
        va, vb = a.get(key), b.get(key)
        comparable = (
            isinstance(va, (int, float)) and isinstance(vb, (int, float))
            and not (math.isnan(va) or math.isnan(vb))
        )
        if comparable and va != vb:
            winner = "A" if ((va > vb) == higher_is_better) else "B"
        else:
            winner = "-"
        ta_text = "n/a" if va is None else f"{float(va):.4f}"
        tb_text = "n/a" if vb is None else f"{float(vb):.4f}"
        print(f"  {key:<20} {ta_text:>14} {tb_text:>14}   {winner}")

    ta, tb = int(a.get("trade_count", 0)), int(b.get("trade_count", 0))
    print(f"  {'trade_count':<20} {ta:>14,} {tb:>14,}   {'(context, not scored)'}")
    print(f"  {'  difference':<20} {'':>14} {tb - ta:>+14,}")

    print("\n  A = " + str(path_a))
    print("  B = " + str(path_b))
    print("\n  Caveats:")
    print("   - per-trade sharpe/profit_factor are not comparable across runs with very")
    print("     different trade counts (Kelly's no-edge skip changes the trade population)")
    print("   - the regime model and the multi-horizon pilot also differ in base-model")
    print("     tuning (Optuna vs default params), so this is a challenger comparison,")
    print("     not a clean horizon-blend A/B")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("summaries", nargs="+", help="one or two backtest_summary.json paths")
    args = parser.parse_args()
    if len(args.summaries) > 2:
        print("pass at most two summaries")
        return 1

    loaded = []
    for raw in args.summaries:
        path = Path(raw)
        if not path.is_file():
            print(f"not found: {path}")
            return 1
        loaded.append((path, load(path)))

    for path, backtest in loaded:
        summarize(str(path), backtest)

    if len(loaded) == 2:
        (path_a, a), (path_b, b) = loaded
        head_to_head(path_a, a, path_b, b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
