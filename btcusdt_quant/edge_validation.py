"""Out-of-sample edge validation harnesses (house rule 원칙 5·6).

The pipeline can already run a backtest; what it lacked was a way to ask the
questions that decide whether a positive backtest is a real, tradeable edge or
a lucky single number: does it survive higher costs, where does regime routing
lose it, and does it hold across seeds / feature groups / a shuffled-label
negative control.

Every function here is a thin, HONEST wrapper over ``backtest.run_backtest`` —
no metric is invented and no model is silently retrained. Two shapes:

* Single fixed model, vary the CONDITION:
  - ``cost_stress`` re-runs the same model at 1x / 1.5x / 2x fee+slippage.
  - ``routing_comparison`` runs the mandatory 4-way (unified / oracle /
    predicted / detector-diagnostics) over already-trained artifacts.

* Vary the MODEL, compare backtests (the caller supplies the already-trained
  models — this harness never retrains, so it cannot fake an ablation or a
  seed sweep):
  - ``compare_trained_models`` is the engine; ``seed_stability``,
    ``feature_group_ablation`` and ``shuffled_label_control`` are semantic
    wrappers that label its output and add the relevant verdict.

Producing the per-seed / per-ablated-group / shuffled-label models is a
separate training step (run ``train`` N times); this module only compares
their OOS backtests. That boundary is deliberate: an ablation that zeroed a
feature at inference instead of retraining would be train/serve skew, not an
ablation.

Costs, horizon, exec barrier, dates and every other ``run_backtest`` argument
pass straight through via ``**backtest_kwargs`` so a validation run executes
exactly the barrier and window the real backtest does.
"""
from __future__ import annotations

from statistics import pstdev
from typing import Mapping, Sequence

from . import backtest as _bt
from . import data as _data
from . import dataset as _dataset
from . import live as _live

__all__ = [
    "DEFAULT_COST_MULTIPLIERS",
    "trading_metrics",
    "cost_stress",
    "routing_comparison",
    "compare_trained_models",
    "seed_stability",
    "feature_group_ablation",
    "shuffled_label_control",
]

# 1x is the estimated cost; 1.5x and 2x are the stress levels house rule 원칙 5
# requires ("1.5배 비용에서도 대체로 양수, 2배 비용에서 급격히 붕괴하지 않음").
DEFAULT_COST_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0)


def trading_metrics(result: "_bt.BacktestResult") -> dict[str, object]:
    """The stable trading-metric subset every harness reports, NaN/inf-safe.

    Pulls from ``BacktestResult.as_dict`` (the single source of truth for what a
    backtest produced) rather than recomputing, so these numbers can never
    drift from the backtest_summary the same result would write. Non-finite
    metrics become ``null`` via ``backtest.json_safe`` — an undefined metric is
    "no answer" (too few trades, zero dispersion), not zero performance.
    """
    payload = result.as_dict()
    long_trades = sum(1 for t in result.trades if t.side == "BUY")
    short_trades = sum(1 for t in result.trades if t.side == "SELL")
    subset = {
        "trade_count": payload.get("trade_count", 0),
        "net_total_return": payload.get("total_return"),
        "gross_total_return": payload.get("gross_total_return"),
        "net_sharpe": payload.get("net_sharpe"),
        "gross_sharpe": payload.get("gross_sharpe"),
        "win_rate": payload.get("win_rate"),
        "profit_factor": payload.get("profit_factor"),
        "max_drawdown": payload.get("max_drawdown"),
        "total_fees": payload.get("total_fees"),
        "total_slippage": payload.get("total_slippage"),
        "round_trip_cost_pct": payload.get("round_trip_cost_pct"),
        "long_trades": long_trades,
        "short_trades": short_trades,
    }
    return _bt.json_safe(subset)


def cost_stress(
    candles: Sequence["_data.Candle"],
    *,
    model: object | None = None,
    models_by_regime: Mapping[str, object] | None = None,
    strategy: "_live.StrategyConfig | None" = None,
    base_fee_rate_per_side: float = _bt.DEFAULT_FEE_RATE_PER_SIDE,
    base_slippage_rate_per_side: float = _bt.DEFAULT_SLIPPAGE_RATE_PER_SIDE,
    multipliers: Sequence[float] = DEFAULT_COST_MULTIPLIERS,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """Re-run the SAME model at each cost multiple; report net at each level.

    The model, signals and barrier are identical across levels — only fee and
    slippage scale — so any change in net expectancy is attributable purely to
    cost. ``survives_1_5x`` / ``survives_2x`` are the house-rule gate: a real
    edge stays positive at 1.5x and does not collapse at 2x.
    """
    if not multipliers:
        raise ValueError("multipliers must not be empty")
    if any(m <= 0.0 for m in multipliers):
        raise ValueError("cost multipliers must be positive")
    _reject_controlled(backtest_kwargs, ("fee_rate_per_side", "slippage_rate_per_side"), "cost_stress")
    # Every level shares the same signals and features -- only cost changes --
    # so build the features once instead of once per multiplier.
    shared_rows = _shared_feature_rows(candles, backtest_kwargs, user_regime_periods=backtest_kwargs.get("user_regime_periods"))  # type: ignore[arg-type]
    run_kwargs = dict(backtest_kwargs)
    if shared_rows is not None:
        run_kwargs["feature_rows"] = shared_rows
    levels: dict[str, object] = {}
    net_by_mult: dict[float, float | None] = {}
    for mult in multipliers:
        result = _bt.run_backtest(
            candles,
            model=model,
            strategy=strategy,
            models_by_regime=models_by_regime,
            fee_rate_per_side=base_fee_rate_per_side * mult,
            slippage_rate_per_side=base_slippage_rate_per_side * mult,
            **run_kwargs,  # type: ignore[arg-type]
        )
        metrics = trading_metrics(result)
        levels[f"{mult:g}x"] = metrics
        net = metrics.get("net_total_return")
        net_by_mult[mult] = float(net) if isinstance(net, (int, float)) else None

    def _positive(mult: float) -> bool:
        net = net_by_mult.get(mult)
        return net is not None and net > 0.0

    return {
        "base_fee_rate_per_side": base_fee_rate_per_side,
        "base_slippage_rate_per_side": base_slippage_rate_per_side,
        "multipliers": list(multipliers),
        "levels": levels,
        "survives_1_5x": _positive(1.5) if 1.5 in net_by_mult else None,
        "survives_2x": _positive(2.0) if 2.0 in net_by_mult else None,
    }


def routing_comparison(
    candles: Sequence["_data.Candle"],
    *,
    models_by_regime: Mapping[str, object],
    unified_model: object,
    user_regime_periods: Sequence["_dataset.UserRegimePeriod"] | None = None,
    regime_detector: object | None = None,
    regime_classifier_model: object | None = None,
    multi_feature_regime_detector: object | None = None,
    strategy: "_live.StrategyConfig | None" = None,
    feature_rows: "Sequence[_dataset.FeatureRow] | None" = None,
    oracle_feature_rows: "Sequence[_dataset.FeatureRow] | None" = None,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """The mandatory 4-way regime comparison (house rule 원칙 6 / regime.md).

    ``feature_rows`` (unified/predicted) and ``oracle_feature_rows`` (oracle,
    carrying the hindsight user_regime) let the caller supply a prebuilt feature
    matrix — e.g. one that merged F16 metrics external_sources so the arms match
    a model trained with ``--metrics-dir``. When omitted the arms build their
    own (predicted/unified plain; oracle from ``user_regime_periods``).


    Same candles, barrier, cost and window for every arm:

    * ``unified``   — one entry model, no regime split (``model=unified_model``).
    * ``oracle``    — regime-per-bucket routing on HINDSIGHT regimes
      (``user_regime_periods``, e.g. regimes.json). Look-ahead by construction:
      a diagnostic UPPER BOUND ("if routing were perfect"), never forward
      performance. Caveat: the entry models were trained on the *detector's*
      bucketing, so oracle here mixes perfect routing with detector-bucketed
      models — still the standard oracle diagnostic, but not a pure ceiling.
    * ``predicted`` — the SAME causal source that trained the models drives
      routing (pass whichever of ``multi_feature_regime_detector`` /
      ``regime_classifier_model`` / ``regime_detector`` the models were trained
      with — passing a different one is train/serve skew, see backtest.py).
    * ``detector_diagnostics`` — the predicted arm's regime counts / ratios /
      transitions over the backtest window.

    Interpretation follows regime.md: oracle good + predicted bad → detector /
    transition problem; oracle bad → label / feature / entry-model problem;
    unified > predicted → the current bucketing is splitting the sample and
    hurting the edge.
    """
    if unified_model is None:
        raise ValueError("unified_model is required for the unified arm")
    predicted_sources = [
        s for s in (regime_detector, regime_classifier_model, multi_feature_regime_detector) if s is not None
    ]
    if len(predicted_sources) != 1:
        raise ValueError(
            "pass exactly one predicted routing source (regime_detector, "
            "regime_classifier_model or multi_feature_regime_detector) — it must "
            "be the SAME source the models were trained with"
        )
    _reject_controlled(
        backtest_kwargs,
        ("model", "models_by_regime", "regime_detector", "regime_classifier_model",
         "multi_feature_regime_detector", "user_regime_periods", "feature_rows"),
        "routing_comparison",
    )

    # unified (no routing) and predicted (detector overwrites user_regime on a
    # COPY) can share one plain feature build; the oracle arm needs rows carrying
    # the hindsight regimes, so it builds its own via user_regime_periods.
    shared_rows = feature_rows if feature_rows is not None else _shared_feature_rows(candles, backtest_kwargs)
    run_kwargs = dict(backtest_kwargs)
    if shared_rows is not None:
        run_kwargs["feature_rows"] = shared_rows

    unified = _bt.run_backtest(candles, model=unified_model, strategy=strategy, **run_kwargs)  # type: ignore[arg-type]

    predicted = _bt.run_backtest(
        candles,
        strategy=strategy,
        models_by_regime=models_by_regime,
        regime_detector=regime_detector,
        regime_classifier_model=regime_classifier_model,
        multi_feature_regime_detector=multi_feature_regime_detector,
        **run_kwargs,  # type: ignore[arg-type]
    )

    arms: dict[str, object] = {
        "unified": trading_metrics(unified),
        "predicted": trading_metrics(predicted),
    }
    oracle_net: float | None = None
    if oracle_feature_rows is not None:
        # Prebuilt oracle rows already carry the hindsight user_regime (and any
        # merged metrics); route on them directly.
        oracle_kwargs = dict(backtest_kwargs)
        oracle_kwargs["feature_rows"] = oracle_feature_rows
        oracle = _bt.run_backtest(candles, strategy=strategy, models_by_regime=models_by_regime, **oracle_kwargs)  # type: ignore[arg-type]
        arms["oracle"] = trading_metrics(oracle)
        oracle_net = _as_float(arms["oracle"].get("net_total_return"))
    elif user_regime_periods is not None:
        oracle = _bt.run_backtest(
            candles,
            strategy=strategy,
            models_by_regime=models_by_regime,
            user_regime_periods=user_regime_periods,
            **backtest_kwargs,  # type: ignore[arg-type]
        )
        arms["oracle"] = trading_metrics(oracle)
        oracle_net = _as_float(arms["oracle"].get("net_total_return"))

    unified_net = _as_float(arms["unified"].get("net_total_return"))
    predicted_net = _as_float(arms["predicted"].get("net_total_return"))

    return {
        "arms": arms,
        "detector_diagnostics": getattr(predicted, "regime_routing_diagnostics", {}),
        "interpretation": _interpret_routing(unified_net, oracle_net, predicted_net),
    }


def compare_trained_models(
    candles: Sequence["_data.Candle"],
    models: Mapping[str, object],
    *,
    baseline_label: str | None = None,
    strategy: "_live.StrategyConfig | None" = None,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """Backtest each already-trained model under identical conditions; compare.

    The engine behind seed-stability, feature-group ablation and the
    shuffled-label control. ``models`` maps a label (seed value, removed group,
    "real"/"shuffled") to a model the CALLER already trained — this function
    never trains, so it cannot fake any of those experiments. Reports per-model
    metrics, the cross-model dispersion of net return / trade count / net
    Sharpe, and (if ``baseline_label`` is given) each model's net delta versus
    that baseline.
    """
    if not models:
        raise ValueError("models must not be empty")
    if baseline_label is not None and baseline_label not in models:
        raise ValueError(f"baseline_label {baseline_label!r} is not one of the models")
    _reject_controlled(backtest_kwargs, ("model",), "compare_trained_models")
    # Same candles across every model -> build the features once and reuse.
    shared_rows = _shared_feature_rows(candles, backtest_kwargs, user_regime_periods=backtest_kwargs.get("user_regime_periods"))  # type: ignore[arg-type]
    run_kwargs = dict(backtest_kwargs)
    if shared_rows is not None:
        run_kwargs["feature_rows"] = shared_rows

    per_model: dict[str, object] = {}
    for label, model in models.items():
        result = _bt.run_backtest(candles, model=model, strategy=strategy, **run_kwargs)  # type: ignore[arg-type]
        per_model[str(label)] = trading_metrics(result)

    report: dict[str, object] = {
        "models": per_model,
        "dispersion": {
            "net_total_return": _dispersion(per_model, "net_total_return"),
            "trade_count": _dispersion(per_model, "trade_count"),
            "net_sharpe": _dispersion(per_model, "net_sharpe"),
        },
    }
    if baseline_label is not None:
        # per_model is keyed by str(label); normalise the lookup so a non-string
        # baseline_label (e.g. an int seed passed directly) doesn't KeyError.
        base_net = _as_float(per_model[str(baseline_label)].get("net_total_return"))
        report["baseline_label"] = baseline_label
        report["net_delta_vs_baseline"] = {
            label: (_as_float(m.get("net_total_return")) - base_net)
            if base_net is not None and _as_float(m.get("net_total_return")) is not None
            else None
            for label, m in per_model.items()
        }
    return report


def seed_stability(
    candles: Sequence["_data.Candle"],
    models_by_seed: Mapping[int | str, object],
    *,
    strategy: "_live.StrategyConfig | None" = None,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """Compare backtests of the SAME configuration trained under different seeds.

    A direction that flips sign or a net return whose spread across seeds
    swamps its mean is an unstable model, not an edge (house rule 원칙 5 /
    research-and-edge-validation.md "여러 seed에서 방향성이 유지됨").
    """
    labelled = {f"seed_{seed}": model for seed, model in models_by_seed.items()}
    report = compare_trained_models(candles, labelled, strategy=strategy, **backtest_kwargs)
    report["experiment"] = "seed_stability"
    return report


def feature_group_ablation(
    candles: Sequence["_data.Candle"],
    models_by_group: Mapping[str, object],
    *,
    full_label: str = "full",
    strategy: "_live.StrategyConfig | None" = None,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """Compare the full model against models RETRAINED with a feature group removed.

    Each key is a removed group (plus one ``full_label`` model trained on
    everything); the caller retrains per group. A group whose removal barely
    changes OOS net return was not carrying the edge, whatever its SHAP rank
    (house rule 원칙 4). ``net_delta_vs_baseline`` is keyed off ``full_label``.
    """
    if full_label not in models_by_group:
        raise ValueError(f"models_by_group must include the full model under {full_label!r}")
    report = compare_trained_models(
        candles, models_by_group, baseline_label=full_label, strategy=strategy, **backtest_kwargs
    )
    report["experiment"] = "feature_group_ablation"
    return report


def shuffled_label_control(
    candles: Sequence["_data.Candle"],
    *,
    real_model: object,
    shuffled_model: object,
    strategy: "_live.StrategyConfig | None" = None,
    **backtest_kwargs: object,
) -> dict[str, object]:
    """Negative control: a model trained on SHUFFLED labels must lose the edge.

    ``shuffled_model`` is trained by the caller on the same features with the
    labels permuted. If it still turns a comparable net profit, the "edge" is
    leakage, threshold overfit, a backtest bug or selection bias, not signal
    (house rule 원칙 5 / research-and-edge-validation.md 8.5). ``edge_vanished``
    is the verdict: real net positive AND shuffled net not positive.
    """
    report = compare_trained_models(
        candles,
        {"real": real_model, "shuffled": shuffled_model},
        baseline_label="real",
        strategy=strategy,
        **backtest_kwargs,
    )
    real_net = _as_float(report["models"]["real"].get("net_total_return"))
    shuffled_net = _as_float(report["models"]["shuffled"].get("net_total_return"))
    report["experiment"] = "shuffled_label_control"
    report["edge_vanished"] = (
        real_net is not None
        and shuffled_net is not None
        and real_net > 0.0
        and shuffled_net <= 0.0
    )
    return report


# -- helpers ---------------------------------------------------------------


def _reject_controlled(backtest_kwargs: Mapping[str, object], names: Sequence[str], func_name: str) -> None:
    """Fail loudly if a caller puts a run_backtest argument the harness sets
    itself into ``backtest_kwargs`` -- otherwise Python raises the opaque
    "got multiple values for keyword argument" from deep inside run_backtest.
    """
    clash = [name for name in names if name in backtest_kwargs]
    if clash:
        raise TypeError(f"{func_name} controls {clash}; do not also pass them in backtest_kwargs")


def _shared_feature_rows(
    candles: Sequence["_data.Candle"],
    backtest_kwargs: Mapping[str, object],
    *,
    user_regime_periods: Sequence["_dataset.UserRegimePeriod"] | None = None,
) -> "list[_dataset.FeatureRow] | None":
    """Build the feature matrix ONCE for reuse across backtests over the same
    candles -- features depend on the candles, not on the model or the cost, so
    rebuilding them per run re-spawns the parallel feature pool (>50k bars) for
    nothing. Returns None -- deferring to run_backtest's own per-run build --
    when the caller already controls ``feature_rows`` or passes
    ``external_sources`` (which change the features), so no input is silently
    dropped. run_backtest copies rows before overwriting user_regime, so one
    shared list is safe to hand to several arms.
    """
    if "feature_rows" in backtest_kwargs or "external_sources" in backtest_kwargs:
        return None
    return _dataset.build_feature_rows(candles, user_regime_periods=user_regime_periods)


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _dispersion(per_model: Mapping[str, Mapping[str, object]], key: str) -> dict[str, float | None]:
    values = [v for v in (_as_float(m.get(key)) for m in per_model.values()) if v is not None]
    if not values:
        return {"min": None, "max": None, "mean": None, "stdev": None, "n": 0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "stdev": pstdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def _interpret_routing(unified: float | None, oracle: float | None, predicted: float | None) -> str:
    if predicted is None or unified is None:
        return "insufficient metrics to interpret routing"
    if oracle is not None:
        if oracle > 0.0 and predicted <= 0.0:
            return "oracle profitable, predicted not: detector / transition / routing-lag problem"
        if oracle <= 0.0:
            return "oracle also unprofitable: label, feature, entry-model or regime-split problem, not the detector"
    if unified > predicted:
        return "unified beats predicted routing: current bucketing splits the sample and hurts the edge"
    return "predicted routing at least matches unified; no routing pathology flagged by net return alone"
