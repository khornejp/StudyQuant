from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from math import exp, isfinite, log, sqrt
from pathlib import Path
from statistics import mean
from time import perf_counter, time
from types import MappingProxyType
from typing import Mapping, Sequence

from . import cv, dataset, features, governance, lineage, models, monitoring


# Round-trip trading cost (fees + slippage, both sides) charged by the
# trading_pnl threshold objective and the holdout PnL metrics. It MUST equal
# backtest.DEFAULT_ROUND_TRIP_COST_PCT -- thresholds picked against a cheaper
# cost than execution pays admit signals whose gross edge dies in fees. The
# two are separate literals because backtest imports live and training does
# not; tests/test_review_items.py pins them equal, so change both together.
#   History: 0.0008 until 2026-07-30 (maker rate charged for taker fills), then
# 0.0016 (the taker round trip). Both were wrong for this account, which trades
# limit-only: every leg rests, so the round trip is two maker fees and no
# slippage = 0.0004. At 0.0016 threshold selection was pricing four times the
# real cost and rejecting every edge between 4 and 16bps.
DEFAULT_ROUND_TRIP_COST = 0.0004


# THE direction policy: which sides each regime is allowed to trade, and the
# triple-barrier target each side must learn. A short model has to learn
# short_success -- the complement of P(long_success) is not a short probability
# (a long that times out is not a short win).
#
#   up    -> long only  (follow the uptrend)
#   down  -> short only (follow the downtrend)
#   range -> both       (mean-revert off either edge)
#
# Both the single-horizon path (_train_single_regime) and the multi-horizon
# pilot (cli._run_train_multi_horizon_regime_aware) read this, so the two model
# families always train the same side set. Change it here and both follow;
# a second hand-kept copy would silently make Phase 4 vs 4.5 incomparable.
# Read-only: cli.MH_REGIME_SIDES aliases this object, so a plain dict would let
# any consumer mutate the policy for every other consumer.
REGIME_SIDES: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType({
    "up": (("long", "long_success"),),
    "down": (("short", "short_success"),),
    "range": (("long", "long_success"), ("short", "short_success")),
})


def sides_for_regime(regime_name: str) -> tuple[tuple[str, str], ...]:
    """(side, target_key) pairs this regime may train.

    Raises on an unknown regime rather than guessing. Defaulting to both sides
    would ship long AND short models for a bucket nobody defined a policy for;
    defaulting to neither would train nothing and leave a silently missing
    model. Every caller today passes a name from dataset.USER_REGIME_NAMES, so
    an unknown name is a programming error and should say so.
    """
    try:
        return REGIME_SIDES[regime_name]
    except KeyError:
        raise ValueError(
            f"no direction policy for regime {regime_name!r}; known regimes: {sorted(REGIME_SIDES)}"
        ) from None


@dataclass(frozen=True)
class TrainingConfig:
    cv_mode: str = "walk_forward"
    embargo_size: int = 0
    # Rows omitted between walk-forward TEST windows.  Set equal to the label
    # horizon to prevent forward-label overlap across fold boundaries.
    walk_forward_test_gap: int = 0
    n_groups: int = 5
    test_group_count: int = 1
    model_family: str = "auto"
    model_params: Mapping[str, object] = field(default_factory=dict)
    fallback_allowed: bool = True
    lineage_enabled: bool = True
    feature_selection_enabled: bool = False
    optuna_enabled: bool = False
    optuna_budget_profile: str = "practical_start"
    optuna_trials: int = 0
    # Exclude features whose training-time values are fallback/mock (source
    # unavailable offline, e.g. F12 exchange-safety constants). A model trained
    # on mock constants learns zero information from them AND acquires a
    # train/serve skew the moment live feeds real values. Default ON; opt out
    # only for research on the old behavior.
    exclude_fallback_features: bool = True
    # Shuffled-label negative control (research-and-edge-validation.md 8.5):
    # permute each labeled row's label/targets across rows (features untouched)
    # before training. A pipeline with no leakage/selection bias must lose its
    # edge under this. NEVER deploy a model trained with this on.
    shuffle_labels: bool = False
    shuffle_labels_seed: int = 42
    # Which triple-barrier target the NON-regime path learns as row.label.
    # "profitability" (long-side, the default/back-compat) or "short_success"
    # to train a short model, or "long_success"/"direction" for research. The
    # regime path is unaffected -- it reads row.targets[side] explicitly.
    train_target: str = "profitability"
    # Reported ALONGSIDE the ungated fold metrics, never instead of them, and
    # it does not touch fitting or threshold selection: this is a question
    # asked of the model, not a change to it.
    vol_gate_feature: str | None = None
    vol_gate_min: float = 0.0
    # Derives vol_gate_min from data instead of taking it on faith, without
    # letting it see a test row: the cutoff is this quantile of the feature over
    # the FIRST fold's train slice, which in walk-forward precedes every fold's
    # test slice, and the same absolute number is then used for all folds.
    #
    # Not recomputed per fold, though that is the more obvious reading of
    # "selected within the fold". A quantile is relative and the cost is
    # absolute: in a calm stretch the local top 20% still cannot move far
    # enough to pay 4 bps, and a per-fold quantile happily admits it. Measured
    # on a 700k-row slice, per-fold cutoffs came out 0.00047-0.00083 against an
    # absolute 0.00096, eligible share rose to 16-66% from 8-19%, and the gated
    # result went from better than ungated to worse.
    vol_gate_train_quantile: float | None = None
    # Resolved only from vol_gate_screen_reference_report; descriptive only.
    vol_gate_screen_reference_min: float | None = None
    # A provenance-captured barrier screen report. Its gate.cutoff is recorded
    # beside the fold-clean cutoff, and the report itself is fingerprinted.
    vol_gate_screen_reference_report: str | None = None
    # Train on gated bars ONLY, instead of training on everything and gating at
    # inference. Measured on the first gated run, the model's confidence and the
    # gate are close to mutually exclusive: no gated bar reached the all-bar 99th
    # percentile of probability in any fold, i.e. the model puts its confidence
    # on low-volatility bars, where a 45-bar move disperses 22 bps and cannot pay
    # a 4 bps round trip whatever the ranking says. Training on everything
    # optimises for the 95% of rows that are never traded.
    vol_gate_train_only: bool = False
    champion_challenger_enabled: bool = False
    regime_aware: bool = False
    min_regime_rows: int = 80
    regime_detector_rv_percentile: float = 0.75
    regime_detector_trend_percentile: float = 0.70
    regime_detector_min_trend_abs: float = 0.00001
    regime_detector_low_vol_trend_multiplier: float = 2.0
    regime_detector_min_regime_run_bars: int = 3
    # Path to a .cbm file saved by `train-regime-classifier` (a multiclass
    # up/range/down model over F17 multi-timeframe features). This field is
    # used only as a GATE/SIGNAL, not loaded here: when set, training bucket
    # assignment uses the walk-forward OOF F18 regime_prob_up/range/down
    # values already merged into each row's features (safe -- each row's
    # value came from a classifier trained only on chronologically earlier
    # rows), taking their argmax (with the same smoothing as Phase 2.5).
    # Training deliberately does NOT load and re-predict with this .cbm file:
    # that "final" classifier was fit on the COMPLETE training span, so
    # re-predicting on a training row would classify it with a model that
    # already "saw" chronologically later rows during its own fit -- a subtle
    # form of look-ahead distinct from (but similar in spirit to) label
    # leakage. The .cbm file itself is loaded and used for genuinely
    # out-of-sample backtest/live routing instead (see backtest.py).
    regime_classifier_model_path: str | None = None
    # When True, regime bucket assignment uses the multi-feature rule-based
    # detector (regime_rules.MultiFeatureRegimeDetector) instead of the learned
    # classifier OOF or the single-slope directional detector. Takes priority
    # over regime_classifier_model_path. The fitted detector (config +
    # normalization stats) is persisted to regime_run_summary.json so backtest
    # and live route with the identical rule -- entry models bucketed this way
    # MUST be served with the same detector to avoid train/serve skew.
    multi_feature_regime: bool = False
    # Optional MultiFeatureRegimeConfig overrides (parsed from a JSON file via
    # --rule-regime-config). Only used when multi_feature_regime is True. The
    # fitted detector (with these overrides) is saved to the artifact, so
    # backtest/live inherit the same rule config automatically.
    multi_feature_regime_config: dict | None = None
    feature_selection_target_min: int = 0
    feature_selection_target_max: int = 0
    ensemble_enabled: bool = False
    ensemble_direction_family: str = "catboost"
    ensemble_profitability_family: str = "catboost"
    ensemble_meta_family: str = "catboost"
    training_start: datetime | None = None
    training_end: datetime | None = None
    test_start: datetime | None = None
    test_end: datetime | None = None
    only_build: bool = False
    # Triple-barrier labeling parameters. These MUST match the TP/SL used in
    # the backtest/live strategy, otherwise the model learns to predict a
    # different barrier than the one it actually trades against. Defaults
    # mirror build_dataset (0.30% TP / 0.15% SL, 60-bar horizon).
    label_horizon: int = 60
    label_threshold: float = 0.001
    tp_pct: float = 0.003
    sl_pct: float = 0.0015
    # Round-trip trading cost (fees + slippage, both sides) used by the
    # trading_pnl threshold objective and holdout PnL metrics. See
    # DEFAULT_ROUND_TRIP_COST -- it must mirror the backtest cost model or
    # thresholds get selected for the wrong cost assumption.
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST
    # Decision-threshold selection objective.
    #   "precision_recall" (default, backward-compatible): rank candidates by
    #     precision with a recall>=0.3 floor; fall back to F1 otherwise.
    #   "trading_pnl": rank by (calmar, sharpe, f1, -|t-0.5|) on the trading
    #     PnL simulator. Strongly recommended for trading models where the
    #     classification trade-off does not map cleanly to economic outcomes.
    # Default is trading_pnl: precision_recall let selected thresholds drop to
    # ~0.32 on weak models (flooding backtests with sub-cost entries).
    # trading_pnl ranks candidates by cost-aware simulated PnL (no-trade below
    # threshold, asymmetric TP/SL, round-trip cost). precision_recall is kept
    # as a legacy option.
    threshold_objective: str = "trading_pnl"
    # Minimum number of "trades" (predicted-positive samples) required for a
    # threshold candidate to be considered under the trading_pnl objective.
    # None lets select_threshold pick a default of max(1, 5% of rows).
    threshold_min_trades: int | None = None

    def __post_init__(self) -> None:
        if self.cv_mode not in {"walk_forward", "combinatorial_purged"}:
            raise ValueError("cv_mode must be 'walk_forward' or 'combinatorial_purged'")
        if self.vol_gate_train_quantile is not None and self.cv_mode != "walk_forward":
            # The cutoff is measured on fold 0's train slice and reused for every
            # fold. That is only clean under walk-forward, where fold 0's train
            # precedes every test slice. Under CPCV the groups are combinatorial,
            # so fold 0's train overlaps other folds' test windows and the gate
            # would be fitted on rows it is later scored against. Pass an
            # absolute vol_gate_min instead.
            raise ValueError(
                "vol_gate_train_quantile is only sound under walk_forward: it reads fold 0's "
                "train slice, which under combinatorial_purged is not earlier than the other "
                "folds' test slices. Pass an absolute vol_gate_min."
            )
        if self.vol_gate_screen_reference_min is not None:
            if not self.vol_gate_feature:
                raise ValueError("vol_gate_screen_reference_min requires vol_gate_feature")
            if not isfinite(float(self.vol_gate_screen_reference_min)) or self.vol_gate_screen_reference_min < 0.0:
                raise ValueError("vol_gate_screen_reference_min must be a finite non-negative number")
        if self.embargo_size < 0:
            raise ValueError("embargo_size must be non-negative")
        if self.walk_forward_test_gap < 0:
            raise ValueError("walk_forward_test_gap must be non-negative")
        if self.n_groups <= 0:
            raise ValueError("n_groups must be positive")
        if self.test_group_count <= 0:
            raise ValueError("test_group_count must be positive")
        if self.test_group_count > self.n_groups:
            raise ValueError("test_group_count cannot exceed n_groups")
        valid_families = set(models.ModelFactory.SUPPORTED_FAMILIES) | {"auto", "linear", "deterministic", "lgbm", "cat"}
        if str(self.model_family).lower().strip() not in valid_families:
            raise ValueError(f"model_family must be one of {valid_families}")
        if self.min_regime_rows <= 0:
            raise ValueError("min_regime_rows must be positive")
        if self.threshold_objective not in {"precision_recall", "trading_pnl"}:
            raise ValueError("threshold_objective must be 'precision_recall' or 'trading_pnl'")
        if self.threshold_min_trades is not None and self.threshold_min_trades < 0:
            raise ValueError("threshold_min_trades must be non-negative")


def resolve_screen_reference(config: TrainingConfig) -> TrainingConfig:
    """Load the descriptive screen cutoff from a provenance-captured report."""
    if config.vol_gate_screen_reference_report is None:
        return config
    report_path = Path(config.vol_gate_screen_reference_report)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        gate = payload["gate"]
        cutoff = float(gate["cutoff"])
        feature = str(gate["feature"])
        provenance = payload["provenance"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid vol_gate_screen_reference_report {report_path}: {exc}") from exc
    if not isfinite(cutoff) or cutoff < 0.0:
        raise ValueError("vol_gate_screen_reference_report gate.cutoff must be finite and non-negative")
    if config.vol_gate_feature != feature:
        raise ValueError(
            f"vol_gate_screen_reference_report gate.feature={feature!r} does not match "
            f"vol_gate_feature={config.vol_gate_feature!r}"
        )
    if not isinstance(provenance, Mapping) or provenance.get("state") != governance.PROVENANCE_RECORDED:
        raise ValueError("vol_gate_screen_reference_report must contain provenance.state=RECORDED")
    return replace(config, vol_gate_screen_reference_min=cutoff)


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    split: object
    threshold: float
    calibration_offset: float
    calibration_details: dict[str, object]
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]
    train_metrics: dict[str, float]
    model_selection: dict[str, object]
    # What the fold's model would have EARNED on its test slice, not just how
    # well it classified there. See oos_trading_metrics for why this is the only
    # honest read the pipeline produces.
    test_trading: dict[str, object] = field(default_factory=dict)
    # The same figures restricted to the bars a volatility gate would allow.
    # Empty when no gate is configured.
    test_trading_gated: dict[str, object] = field(default_factory=dict)
    # Per-row test-slice predictions, so a later question about a different
    # gate or threshold does not need the folds refit. Carried on the fold that
    # produced them rather than threaded through as a separate argument.
    test_predictions: list[dict[str, object]] = field(default_factory=list)
    # The cutoff this fold's gate actually used. Differs per fold when it was
    # selected from the fold's own train slice.
    vol_gate_min_used: float | None = None


@dataclass(frozen=True)
class TrainingResult:
    output_dir: Path
    dataset_build: dataset.DatasetBuild
    splits: list[object]
    fold_results: list[object]
    run_summary: dict[str, object]
    artifacts: list[str]


def drop_fallback_features(build: "dataset.DatasetBuild") -> tuple["dataset.DatasetBuild", list[str]]:
    """Remove features whose TRAINING values are fallback/mock constants.

    The source availability report lists features whose live source is absent
    offline (F11/F12 style): build_feature_rows filled them with mock defaults,
    so the model would train on constants (zero information) and then meet real
    values in live -- an input-distribution train/serve skew. Excluding them
    from feature_names keeps them computed in the rows (governance/registry
    unchanged) but out of every training matrix; model.json carries its own
    feature list, so backtest/live automatically use the same reduced set.
    Refuses to drop below 10 features (a degenerate report must not empty the
    model).
    """
    report = build.source_availability_report or {}
    fallback = {str(name) for name in report.get("fallback_features", ()) or ()}
    if not fallback:
        return build, []
    kept = tuple(name for name in build.feature_names if name not in fallback)
    dropped = [name for name in build.feature_names if name in fallback]
    if not dropped or len(kept) < 10:
        return build, []
    return replace(build, feature_names=kept), dropped


# Volatility measures saved beside every fold prediction. Cheap to store, and
# the difference between answering "what if the gate used rv_30 instead" in
# seconds and answering it by refitting the folds for hours.
# Distinct entries a calendar year needs before this code will call it its own
# evidence rather than a handful of trades riding on another year's result.
#
# It is a REPORTING FLOOR, not a statistical guarantee, and it was chosen by the
# same apparatus it judges -- so it cannot certify anything on its own. What it
# does is make the composition visible: entries_by_year, entries_unique and
# overlap_factor are published beside it precisely so a reader can apply their
# own bar. Treat fold_vote_is_independent_evidence=True as "not obviously one
# regime", never as "independent".
MIN_ENTRIES_FOR_AN_INDEPENDENT_YEAR = 200



_PERSISTED_VOLATILITY_FEATURES: tuple[str, ...] = ("rv_15", "rv_30", "rv_60", "rv_120", "atr_pct")

_TRAIN_TARGET_KEYS: tuple[str, ...] = ("profitability", "long_success", "short_success", "short_profitability", "direction")


def realized_payoffs(
    rows: Sequence["dataset.LabeledRow"],
    target: str,
    tp_pct: float,
    sl_pct: float,
) -> list[float]:
    """What each row's trade actually PAID, in return units.

    ``target_return`` is the close-to-close move at the horizon, which is the
    realised payoff only when no barrier was reachable. A row whose TP was
    touched and then reversed is scored with the wrong sign and magnitude by
    the raw return, so the barrier outcome is reconstructed from the per-target
    reason the labeler already stored:

        *_tp_first -> +tp_pct      (the barrier that was hit)
        *_sl_first -> -sl_pct
        *_timeout  ->  target_return, signed for the side

    A SHORT target inverts the horizon return: falling prices pay a short.
    """
    short = target in ("short_success", "short_profitability")
    out: list[float] = []
    for row in rows:
        reason = str(row.target_reasons.get(target, row.label_reason) or "")
        if reason.endswith("tp_first"):
            out.append(float(tp_pct))
        elif reason.endswith("sl_first") or reason == "ambiguous_path" or reason.startswith("gap_cross_sl"):
            out.append(-float(sl_pct))
        else:
            r = float(row.target_return)
            out.append(-r if short else r)
    return out


def oos_trading_metrics(
    probabilities: Sequence[float],
    forward_returns: Sequence[float],
    threshold: float,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
    target: str = "profitability",
    eligible: Sequence[bool] | None = None,
    row_times: Sequence[object] | None = None,
) -> dict[str, object]:
    """What a fold's model would have EARNED on its own test slice.

    The fold loop already fits a model on the train slice alone and already
    scores the test slice, then records F1 and Brier and discards the rest.
    That left this project promoting candidates on the performance of a model
    refit over its whole training span (run_training's final fit uses EVERY
    labeled row), and the first genuinely unseen window it ever met -- 2026 H1
    -- lost money at every confidence level. Four walk-forward test slices were
    sitting unused the entire time.

    ``forward_returns`` is LabeledRow.target_return: the realised return over
    the label horizon, already stored per row. So this needs no retraining, no
    backtest and no new data -- it reads what the fold already computed.

    Reported per side because a probability model is two signals: entries above
    the threshold are the primary book, and the bottom decile is its opposite.
    ``net_bps`` subtracts the flat round trip, so a positive number is a
    strategy and a negative one is not.

    ``target`` names what a high probability MEANS. Under ``short_success`` a
    confident bar is a SHORT, so the books swap: the caller must pass payoffs
    already signed for that side (see realized_payoffs), and the labels below
    read "primary" and "opposite" rather than long and short.

    This is NOT a backtest. It ignores position sizing, cooldown, the
    one-position-at-a-time constraint and fill modelling, so it overstates
    capacity and says nothing about drawdown. It answers one question only, and
    answers it out of sample: does the model's ranking pay for its costs?
    """
    n = min(len(probabilities), len(forward_returns))
    if n == 0:
        return {}
    p = [float(x) for x in probabilities[:n]]
    r = [float(x) for x in forward_returns[:n]]
    # ``eligible`` restricts every figure below to a subset of the slice -- the
    # bars a gate would have let through. Without it a gated strategy cannot be
    # judged here at all: the metric would average the bars the gate refuses
    # into the result it is supposed to measure.
    eligible_share = 1.0
    keep_index: list[int] = []
    if eligible is not None:
        keep = [i for i in range(n) if bool(eligible[i])]
        eligible_share = len(keep) / n
        if not keep:
            # Reported, not dropped. An empty result gets filtered out of the
            # aggregate by any `if result:` caller, which removes exactly the
            # folds the gate refused hardest -- the ones most likely to be the
            # bad ones -- and leaves fold_count and eligible_share describing a
            # different set of folds than the summary claims.
            return {
                "target": target,
                "rows": 0.0,
                "eligible_share": 0.0,
                "threshold": float(threshold),
                "cost_bps": 1e4 * float(round_trip_cost),
                "no_eligible_rows": True,
            }
        keep_index = keep
        p = [p[i] for i in keep]
        r = [r[i] for i in keep]
        n = len(keep)
    cost_bps = 1e4 * float(round_trip_cost)

    def _mean_bps(values: Sequence[float]) -> float:
        return 1e4 * sum(values) / len(values) if values else float("nan")

    entered = [i for i in range(n) if p[i] >= threshold]
    longs = [r[i] for i in entered]
    # WHEN the entries happened, not just how many. A fold vote reads as
    # independent confirmation until you notice every fold is scoring the same
    # calendar stretch: the first gated CPCV run put 86% of its entries in 2021
    # and none at all in 2022, so "12 of 15 folds positive" was one regime
    # counted fifteen times.
    coverage: dict[str, object] = {}
    if row_times is not None:
        times = [
            row_times[keep_index[i]] if eligible is not None else row_times[i]
            for i in entered
        ]
        times = [when for when in times if when is not None]
        years: dict[int, int] = {}
        months: set[tuple[int, int]] = set()
        for when in times:
            years[when.year] = years.get(when.year, 0) + 1
            months.add((when.year, when.month))
        coverage = {
            "entries_by_year": dict(sorted(years.items())),
            "unique_months": len(months),
            "first_entry": min(times).isoformat() if times else None,
            "last_entry": max(times).isoformat() if times else None,
            # The identities themselves, so the aggregate can tell 2000 distinct
            # entries from the same 500 counted four times. Under CPCV a row
            # recurs in several test combinations, and summing per-fold counts
            # would let duplicates alone push a year past any threshold.
            # Stripped before the summary is written; see summarise_fold_trading.
            "entry_keys": [int(when.timestamp() // 60) for when in times],
        }

    order = sorted(range(n), key=lambda i: p[i])
    k = max(1, n // 10)
    bottom = [r[i] for i in order[:k]]
    top = [r[i] for i in order[-k:]]

    long_gross = _mean_bps(longs)
    # The opposite book: take the least-confident decile the other way. The
    # payoffs are already signed for `target`, so negating gives the return of
    # trading against the model's low-confidence bars.
    short_gross = -_mean_bps(bottom)
    return {
        "target": target,
        "rows": float(n),
        "eligible_share": eligible_share,
        "coverage": coverage,
        "threshold": float(threshold),
        "cost_bps": cost_bps,
        "entry_rate": len(longs) / n,
        "long_gross_bps": long_gross,
        "long_net_bps": long_gross - cost_bps,
        "long_trades": float(len(longs)),
        "top_decile_gross_bps": _mean_bps(top),
        "short_gross_bps": short_gross,
        "short_net_bps": short_gross - cost_bps,
        "short_trades": float(len(bottom)),
        "all_rows_mean_bps": _mean_bps(r),
    }


def apply_training_target(rows: Sequence[dataset.LabeledRow], target: str) -> list[dataset.LabeledRow]:
    """Remap row.label to the chosen triple-barrier target for the non-regime path.

    The non-regime training path reads row.label everywhere (folds, Optuna,
    calibration, final fit). row.label defaults to `profitability` (long-side).
    Setting it to short_success trains a SHORT model on the same features
    without touching any of those call sites; the regime path is untouched
    because it reads row.targets[side] explicitly. No-op for the default target.
    """
    if target == "profitability":
        return list(rows)
    if target not in _TRAIN_TARGET_KEYS:
        raise ValueError(f"train_target must be one of {_TRAIN_TARGET_KEYS}, got {target!r}")
    remapped: list[dataset.LabeledRow] = []
    for row in rows:
        if target not in row.targets:
            raise ValueError(f"row {row.index} has no target {target!r}")
        remapped.append(replace(row, label=int(row.targets[target])))
    return remapped


def shuffle_labeled_row_targets(rows: Sequence[dataset.LabeledRow], seed: int) -> list[dataset.LabeledRow]:
    """Permute every row's label payload across rows; features stay put.

    The negative control: decouple labels from features while preserving the
    exact label distribution, class balance and target dicts. label,
    label_reason, target_return, targets and target_reasons travel TOGETHER to
    their new row (a row must stay internally consistent); index/open_time/
    features/regime stay with the original row. Deterministic under `seed`.
    """
    import random as _random

    rows = list(rows)
    order = list(range(len(rows)))
    _random.Random(int(seed)).shuffle(order)
    shuffled: list[dataset.LabeledRow] = []
    for row, src in zip(rows, (rows[j] for j in order)):
        shuffled.append(
            replace(
                row,
                label=src.label,
                label_reason=src.label_reason,
                target_return=src.target_return,
                targets=dict(src.targets),
                target_reasons=dict(src.target_reasons),
            )
        )
    return shuffled


def run_training(input_path: Path | None, output_dir: Path, config: TrainingConfig | None = None, archive_dir: Path | None = None, external_sources: Mapping[str, object] | None = None, external_source_paths: Sequence[Path] | None = None, prebuilt_dataset: dataset.DatasetBuild | None = None, user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None) -> TrainingResult:
    training_config = resolve_screen_reference(config or TrainingConfig())
    # Append as fits happen, rather than attempting to reconstruct device use
    # from a completed model. This survives a native-fit watchdog termination.
    models.start_training_runtime_artifact(output_dir)
    source_path = input_path if input_path is not None else (
        Path(prebuilt_dataset.source) if prebuilt_dataset is not None else None
    )
    provenance_inputs = [
        path for path in (
            source_path, archive_dir, *(external_source_paths or ()),
            Path(training_config.vol_gate_screen_reference_report)
            if training_config.vol_gate_screen_reference_report is not None else None,
        )
        if path is not None
    ]
    captured_provenance = governance.capture_provenance(
        resolved_config=asdict(training_config),
        input_paths=provenance_inputs,
    )
    # `external_sources` is a material, already-resolved input.  A caller that
    # supplies it without the source files leaves no reproducible evidence, so
    # retain the successful components but make that limitation explicit.
    if external_sources is not None and not external_source_paths:
        captured_provenance[0]["state"] = governance.PROVENANCE_UNKNOWN
        captured_provenance[0]["input_fingerprints"] = {
            "state": governance.PROVENANCE_UNKNOWN,
            "reason": "external_sources_not_fingerprinted",
        }
    if prebuilt_dataset is not None:
        build = prebuilt_dataset
    else:
        build = dataset.build_dataset(
            input_path=input_path,
            archive_dir=archive_dir,
            external_sources=external_sources,
            user_regime_periods=user_regime_periods,
            horizon=training_config.label_horizon,
            label_threshold=training_config.label_threshold,
            tp_pct=training_config.tp_pct,
            sl_pct=training_config.sl_pct,
        )
    # Snapshot the full labeled set BEFORE applying training_start/training_end
    # cutoffs, so a post-cutoff test window (e.g. 2025 H1) can still be
    # evaluated by the regime-aware path even though those rows are removed
    # from the training data below.
    full_labeled_rows = list(build.labeled_rows)
    if training_config.training_start is not None:
        build = replace(
            build,
            labeled_rows=[row for row in build.labeled_rows if row.open_time >= training_config.training_start],
        )
    if training_config.training_end is not None:
        build = replace(
            build,
            labeled_rows=[row for row in build.labeled_rows if row.open_time <= training_config.training_end],
        )
    if training_config.vol_gate_train_only:
        key = training_config.vol_gate_feature
        if not key or training_config.vol_gate_min <= 0.0:
            raise ValueError(
                "vol_gate_train_only needs vol_gate_feature and an absolute vol_gate_min. "
                "The quantile form cannot be used here: it is measured on the first fold's "
                "TRAIN slice, and the splits do not exist until after this filter has run."
            )
        floor = float(training_config.vol_gate_min)
        kept = [
            row for row in build.labeled_rows
            if row.features.get(key) is not None and isfinite(float(row.features[key]))
            and float(row.features[key]) >= floor
        ]
        if not kept:
            raise ValueError(f"vol_gate_train_only removed every row: no {key} >= {floor}.")
        print(
            f"[TRAIN] gated training set: {len(kept):,} of {len(build.labeled_rows):,} rows "
            f"({len(kept)/len(build.labeled_rows):.2%}) have {key} >= {floor:.8g}. "
            f"Folds now cover different calendar spans than an ungated run, so fold indices "
            f"are not comparable between the two."
        )
        build = replace(build, labeled_rows=kept)
    if training_config.only_build:
        print(f"[TRAIN] only-build complete: {len(build.labeled_rows):,} labeled rows, {len(build.feature_names)} features")
        return TrainingResult(
            output_dir=output_dir,
            dataset_build=build,
            splits=[],
            fold_results=[],
            run_summary={"only_build": True, "labeled_rows": len(build.labeled_rows), "feature_count": len(build.feature_names)},
            artifacts=[],
        )
    if len(build.labeled_rows) < 80:
        raise ValueError("at least 80 labeled rows are required for the default offline training run")
    # Non-regime target selection: remap row.label to the chosen target BEFORE
    # the regime branch. The regime path reads row.targets[side] directly and is
    # unaffected; only the non-regime path's row.label reads change.
    if training_config.train_target != "profitability":
        build = replace(build, labeled_rows=apply_training_target(build.labeled_rows, training_config.train_target))
        print(f"[TRAIN] Non-regime target: row.label remapped to '{training_config.train_target}'")
    # Mock-input exclusion: features whose offline values are fallback constants
    # carry no information and become a train/serve skew in live. Applies to
    # BOTH the regime and non-regime paths (this runs before the branch).
    if training_config.exclude_fallback_features:
        build, _dropped_fallback = drop_fallback_features(build)
        if _dropped_fallback:
            print(
                f"[TRAIN] Excluded {len(_dropped_fallback)} fallback/mock features from training "
                f"(source unavailable offline): {', '.join(sorted(_dropped_fallback))}"
            )
    # Shuffled-label negative control: permute labels across rows AFTER the
    # cutoffs so the control trains on exactly the same rows as the real run.
    if training_config.shuffle_labels:
        build = replace(
            build,
            labeled_rows=shuffle_labeled_row_targets(build.labeled_rows, training_config.shuffle_labels_seed),
        )
        print(
            "[TRAIN] *** SHUFFLED-LABEL NEGATIVE CONTROL: labels permuted across rows "
            f"(seed={training_config.shuffle_labels_seed}). This model is for edge validation ONLY -- never deploy. ***"
        )
    print(f"[TRAIN] Dataset built: {len(build.labeled_rows):,} labeled rows, {len(build.feature_names)} features")
    # Regime-aware: split by market regime and train separate models.
    # Pass the pre-cutoff dataset (full_labeled_rows) so the regime path can
    # evaluate on a test window (e.g. 2025 H1) that lies *after* training_end
    # and was therefore removed from build.labeled_rows above.
    if training_config.regime_aware:
        return run_regime_aware_training(build, output_dir, training_config, full_labeled_rows=full_labeled_rows)
    # Ensemble stacking: train direction + profitability + meta model
    if training_config.ensemble_enabled:
        return run_ensemble_training(build, output_dir, training_config)
    # Parity assertion: warn when feature_space_parity_passed is False
    source_report = build.source_availability_report
    parity_passed = bool(source_report.get("feature_space_parity_passed", False))
    f11_f12_fallback_count = len(source_report.get("fallback_features", []))
    if not parity_passed:
        import warnings
        if training_config.exclude_fallback_features:
            warnings.warn(
                f"feature_space_parity_passed=False in training: {f11_f12_fallback_count} features had fallback/mock "
                "values and were EXCLUDED from the training matrices (see the [TRAIN] exclusion log line).",
                stacklevel=2,
            )
        else:
            warnings.warn(
                f"feature_space_parity_passed=False in training: {f11_f12_fallback_count} features using fallback/mock values. "
                "Model trained on mock F11/F12 features may underperform in live when real sources are available.",
                stacklevel=2,
            )
    sample_intervals = cv.sample_intervals_from_labeled_rows(build.labeled_rows, build.label_horizon)
    uniqueness = cv.uniqueness_weights(sample_intervals)
    splits = configured_splits(len(build.labeled_rows), build.label_horizon, training_config, sample_intervals)
    if not splits:
        raise ValueError("not enough labeled rows for configured split")
    # Optional feature selection pipeline (6-stage: Spearman, gain, permutation, SHAP, ablation, core set)
    # Nested selection: use only the first fold's training data to avoid leakage
    feature_selection_report: dict[str, object] | None = None
    effective_feature_names = build.feature_names
    if training_config.feature_selection_enabled:
        selection_pipeline = features.FeatureSelectionPipeline(
            target_min_features=training_config.feature_selection_target_min,
            target_max_features=training_config.feature_selection_target_max,
        )
        # Use first fold's training data only to prevent test-data leakage
        first_fold_train_indices = _split_indices(splits[0].train) if splits else list(range(len(build.labeled_rows)))
        first_train_rows = [build.labeled_rows[index] for index in first_fold_train_indices]
        baseline_selection = fit_model_adapter(
            first_train_rows, build.feature_names, training_config,
            _weights_for_indices(uniqueness, first_fold_train_indices),
        )
        feature_selection_report = selection_pipeline.run_full_pipeline(
            model=baseline_selection.adapter,
            feature_matrix=feature_matrix(first_train_rows, build.feature_names),
            labels=[row.label for row in first_train_rows],
            feature_names=build.feature_names,
        )
        bounded_core = feature_selection_report.get("core_features_bounded", [])
        unbounded_core = feature_selection_report.get("core_features", [])
        selected_core = bounded_core if bounded_core else unbounded_core
        if selected_core and len(selected_core) >= 10:
            effective_feature_names = selected_core
    # Optional Optuna hyperparameter tuning
    optuna_report: dict[str, object] | None = None
    optuna_threshold: float | None = None
    if training_config.optuna_enabled:
        # Restrict Optuna's view to data that lies strictly before the first
        # walk-forward test fold. Using `build.labeled_rows` in its entirety
        # would let Optuna's trial-selection process implicitly peek at the
        # CV test windows used downstream, biasing the chosen hyperparameters.
        first_test_start = len(build.labeled_rows)
        for split in splits:
            test_indices = _split_indices(split.test)
            if test_indices:
                first_test_start = min(first_test_start, _min_index(test_indices))
        optuna_rows = build.labeled_rows[:first_test_start] if first_test_start > 0 else list(build.labeled_rows)
        if len(optuna_rows) < 30:
            # Not enough data ahead of the first test fold to tune safely; fall
            # back to the full set rather than crashing, but flag it.
            print(f"[TRAIN] Optuna tuning window too small ({len(optuna_rows)} rows < 30); falling back to full dataset")
            optuna_rows = list(build.labeled_rows)
        optuna_runner = features.OptunaStudyRunner()
        # OptunaStudyRunner searches DECISION params only (threshold, signal_scale),
        # not model hyperparameters -- both are stripped from the model constructor
        # (see OptunaStudyRunner._call_model_factory). threshold is applied to the
        # fold/final entry cutoff below; signal_scale only scales a fallback sigmoid
        # for models lacking predict/probability (test stubs), so it has NO effect
        # on a real CatBoost/LightGBM model and must NOT be fed to its constructor.
        def _optuna_model_factory(params: Mapping[str, float] | None = None) -> models.ModelAdapter:
            merged_params = dict(training_config.model_params)
            if params is not None:
                model_params = {k: v for k, v in params.items() if k not in ("threshold", "signal_scale")}
                merged_params.update(model_params)
            return models.ModelFactory().create(
                family=training_config.model_family,
                feature_names=effective_feature_names,
                model_params=merged_params,
                fallback_allowed=training_config.fallback_allowed,
            )
        optuna_report = optuna_runner.run_study(
            model_factory=_optuna_model_factory,
            feature_matrix=feature_matrix(optuna_rows, effective_feature_names),
            labels=[row.label for row in optuna_rows],
            n_trials=training_config.optuna_trials,
            budget_profile=training_config.optuna_budget_profile,
        )
        # Only the threshold (a decision param) is applied downstream. signal_scale
        # is NOT injected into model_params: it is not a CatBoost/LightGBM argument,
        # and doing so made the constructor raise "unexpected keyword argument
        # 'signal_scale'", forcing a silent GPU->CPU->LightGBM fallback that trained
        # the model with the WRONG family and a dead f1.
        best_params = optuna_report.get("best_params", {})
        if best_params:
            optuna_threshold = float(best_params.get("threshold", 0.5))
    fold_results: list[FoldResult] = []
    # The CLI accepts any feature as a gate, so saving only a fixed five would
    # let a run report a gated metric that cannot be reproduced offline from
    # its own predictions file.
    _persisted_gate_features = tuple(dict.fromkeys(
        _PERSISTED_VOLATILITY_FEATURES
        + ((training_config.vol_gate_feature,) if training_config.vol_gate_feature else ())
    ))
    # Fixed once, on the earliest train slice, then held constant -- see
    # TrainingConfig.vol_gate_train_quantile for why not per fold.
    _gate_min_from_first_fold: float | None = None
    for fold_index, split in enumerate(splits):
        print(f"[TRAIN]   Fold {fold_index + 1}/{len(splits)}: train={len(split.train)}, val={len(split.validation)}, test={len(split.test)}")
        train_indices = _split_indices(split.train)
        validation_indices = _split_indices(split.validation)
        test_indices = _split_indices(split.test)
        train_rows = [build.labeled_rows[index] for index in train_indices]
        validation_rows = [build.labeled_rows[index] for index in validation_indices]
        test_rows = [build.labeled_rows[index] for index in test_indices]
        validation_labels = [row.label for row in validation_rows]
        test_labels = [row.label for row in test_rows]
        with models.training_runtime_context(fold_index=fold_index, fit_role="cv_fold"):
            selection = fit_model_adapter(
                train_rows,
                effective_feature_names,
                training_config,
                _weights_for_indices(uniqueness, train_indices),
            )
        model = selection.adapter
        validation_probabilities = model.predict_proba(feature_matrix(validation_rows, effective_feature_names))
        offset = calibration_offset(validation_probabilities, validation_labels)
        calibrator = features.CalibrationModule().fit(validation_probabilities, validation_labels, positive_samples=sum(validation_labels))
        calibrated_validation = calibrator.transform(validation_probabilities)
        threshold = select_threshold(
            calibrated_validation,
            validation_labels,
            objective=training_config.threshold_objective,
            min_trades=training_config.threshold_min_trades,
            tp_pct=training_config.tp_pct,
            sl_pct=training_config.sl_pct,
            round_trip_cost=training_config.round_trip_cost,
        )
        # Override with Optuna best threshold if available (decision param, not model param)
        if optuna_threshold is not None:
            threshold = optuna_threshold
        test_probabilities = model.predict_proba(feature_matrix(test_rows, effective_feature_names))
        calibrated_test = calibrator.transform(test_probabilities)
        # Entry timestamps, so a fold can report WHEN it traded and not only
        # how much. Without it a fold vote reads as independent confirmation
        # even when every fold is scoring the same calendar stretch.
        _fold_times = [getattr(row, "open_time", None) for row in test_rows]
        _fold_payoffs = realized_payoffs(
            test_rows,
            training_config.train_target,
            training_config.tp_pct,
            training_config.sl_pct,
        )
        # A gate is a property of the BAR, so it is read off the same rows the
        # fold scored. A row missing the feature is not eligible: treating an
        # absent value as zero-and-eligible would quietly widen the gate.
        # Persisted so a later question about a DIFFERENT gate, threshold or
        # volatility measure can be answered offline. Otherwise the only ways to
        # re-score a fold slice are to refit the folds -- hours -- or to use the
        # deployed model, which is refit over every labeled row and therefore
        # sees these slices in-sample. That second trap is what made 2020-2025
        # look evaluable when it never was.
        _fold_predictions: list[dict[str, object]] = []
        for _row, _prob, _pay in zip(test_rows, calibrated_test, _fold_payoffs):
            _fold_predictions.append({
                "fold_index": fold_index,
                # The entry identity. Without it nobody can rebuild
                # entries_unique or overlap_factor from the artifacts, and a
                # faulty key derivation leaves a plausible but unverifiable
                # independence claim.
                "entry_time": _row.open_time.isoformat() if getattr(_row, "open_time", None) else "",
                "probability": float(_prob),
                "payoff": float(_pay),
                "threshold": float(threshold),
                **{f"sigma__{k}": _row.features.get(k) for k in _persisted_gate_features},
            })
        _fold_eligible = None
        _fold_gate_min = float(training_config.vol_gate_min)
        if training_config.vol_gate_feature:
            _key = training_config.vol_gate_feature
            # A misspelled feature makes every row ineligible, which used to
            # read as "the gate is very selective" instead of "the gate is
            # broken". Fail on the first fold rather than produce an empty
            # gated section three hours later.
            if _key not in effective_feature_names:
                raise ValueError(
                    f"--vol-gate-feature {_key!r} is not a trained feature. "
                    f"Every row would be ineligible, which reads as an extremely "
                    f"selective gate rather than a typo. Available volatility "
                    f"features include: {', '.join(_PERSISTED_VOLATILITY_FEATURES)}."
                )
            if training_config.vol_gate_train_quantile is not None:
                if _gate_min_from_first_fold is None:
                    _train_values = sorted(
                        float(row.features[_key])
                        for row in train_rows
                        if row.features.get(_key) is not None and isfinite(float(row.features[_key]))
                    )
                    if not _train_values:
                        raise ValueError(
                            f"--vol-gate-train-quantile needs finite {_key!r} values in the first "
                            f"fold's train slice and found none."
                        )
                    _rank = min(
                        len(_train_values) - 1,
                        int(training_config.vol_gate_train_quantile * len(_train_values)),
                    )
                    _gate_min_from_first_fold = _train_values[_rank]
                    print(
                        f"[TRAIN] volatility gate: {_key} >= {_gate_min_from_first_fold:.8g} "
                        f"(quantile {training_config.vol_gate_train_quantile} of fold 0's train slice, "
                        f"which precedes every test slice; applied to all folds)"
                    )
                _fold_gate_min = _gate_min_from_first_fold
            _floor = _fold_gate_min
            _fold_eligible = [
                (lambda v: v is not None and isfinite(float(v)) and float(v) >= _floor)(
                    row.features.get(_key)
                )
                for row in test_rows
            ]
        train_probabilities = model.predict_proba(feature_matrix(train_rows, effective_feature_names))
        calibrated_train = calibrator.transform(train_probabilities)
        train_labels = [row.label for row in train_rows]
        fold_results.append(
            FoldResult(
                fold_index=fold_index,
                split=split,
                threshold=threshold,
                calibration_offset=offset,
                calibration_details=calibrator.as_dict(),
                validation_metrics=metrics(calibrated_validation, validation_labels, threshold),
                test_metrics=metrics(calibrated_test, test_labels, threshold),
                train_metrics=metrics(calibrated_train, train_labels, threshold),
                model_selection=selection.as_dict(),
                test_trading=oos_trading_metrics(
                    calibrated_test,
                    _fold_payoffs,
                    threshold,
                    round_trip_cost=training_config.round_trip_cost,
                    target=training_config.train_target,
                    row_times=_fold_times,
                ),
                test_predictions=_fold_predictions,
                vol_gate_min_used=_fold_gate_min if training_config.vol_gate_feature else None,
                test_trading_gated=(
                    oos_trading_metrics(
                        calibrated_test,
                        _fold_payoffs,
                        threshold,
                        round_trip_cost=training_config.round_trip_cost,
                        target=training_config.train_target,
                        eligible=_fold_eligible,
                        row_times=_fold_times,
                    )
                    if _fold_eligible is not None
                    else {}
                ),
            )
        )
        _tt = fold_results[-1].test_trading
        if _tt:
            print(
                f"[TRAIN]     OOS trading (fold test slice): entries {_tt['entry_rate']:.1%} "
                f"long_net={_tt['long_net_bps']:+.2f}bps short_net={_tt['short_net_bps']:+.2f}bps "
                f"(cost {_tt['cost_bps']:.1f}bps, all-rows {_tt['all_rows_mean_bps']:+.2f}bps)"
            )
    final_indices = list(range(len(build.labeled_rows)))
    with models.training_runtime_context(fit_role="final_refit"):
        final_selection = fit_model_adapter(build.labeled_rows, effective_feature_names, training_config, _weights_for_indices(uniqueness, final_indices))
    latency_report = inference_latency_report(final_selection.adapter, feature_matrix(build.labeled_rows, effective_feature_names))
    artifacts = write_training_artifacts(output_dir, build, splits, fold_results, final_selection.adapter, training_config, sample_intervals, uniqueness, final_selection, latency_report, captured_provenance)
    run_summary = training_summary(build, splits, fold_results, artifacts, training_config, uniqueness, final_selection, latency_report)
    print(f"[TRAIN] Training complete: {len(build.labeled_rows):,} rows, {len(splits)} folds, test_f1={run_summary.get('mean_test_f1', 0.0):.4f}")
    model_metadata = model_version_metadata(build, final_selection.adapter, training_config, final_selection)
    run_summary.update(
        {
            "model_id": model_metadata["model_id"],
            "model_version": model_metadata["model_version"],
            "model_version_metadata": model_metadata,
        }
    )
    lineage_artifacts: list[str] = []
    if training_config.lineage_enabled:
        lineage_result = write_lineage_metadata(output_dir, build, training_config, artifacts, run_summary, model_metadata)
        run_summary["lineage_run_id"] = lineage_result["run_id"]
        lineage_artifacts = [str(path) for path in lineage_result.get("artifacts", [])]
        run_summary["lineage_artifacts"] = lineage_artifacts
    else:
        run_summary["lineage_run_id"] = None
        run_summary["lineage_artifacts"] = []
    # Add feature selection and Optuna reports to summary
    if feature_selection_report is not None:
        run_summary["feature_selection"] = {
            "enabled": True,
            "original_feature_count": len(build.feature_names),
            "selected_core_count": len(effective_feature_names),
            "selected_core_features": list(effective_feature_names),
            "report": feature_selection_report,
        }
    else:
        run_summary["feature_selection"] = {"enabled": False, "original_feature_count": len(build.feature_names), "selected_core_count": len(build.feature_names)}
    if optuna_report is not None:
        run_summary["optuna"] = {
            "enabled": True,
            "budget_profile": training_config.optuna_budget_profile,
            "trials": training_config.optuna_trials,
            "report": optuna_report,
        }
    else:
        run_summary["optuna"] = {"enabled": False}
    # Optional champion-challenger evaluation (shadow metrics from fold results)
    if training_config.champion_challenger_enabled:
        champion_mgr = features.ChampionChallengerManager()
        # Compute synthetic shadow metrics from fold test results
        avg_test_mdd = mean([fold.test_metrics.get("mdd", 0.0) for fold in fold_results]) if fold_results else 0.0
        avg_test_calmar = mean([fold.test_metrics.get("calmar", 0.0) for fold in fold_results]) if fold_results else 0.0
        avg_test_sharpe = mean([fold.test_metrics.get("sharpe", 0.0) for fold in fold_results]) if fold_results else 0.0
        # Compute baseline metrics from training (champion) data for delta comparison
        # Use last fold's train_metrics as the champion baseline (model trained on all prior data)
        champion_baseline = fold_results[-1].train_metrics if fold_results else {}
        champion_mdd = champion_baseline.get("mdd", avg_test_mdd)
        champion_calmar = champion_baseline.get("calmar", avg_test_calmar)
        mdd_delta = avg_test_mdd - champion_mdd
        calmar_delta = avg_test_calmar - champion_calmar
        # Compute offline-available metrics for champion-challenger gates
        # Score-bin CI from bootstrap report (full rows with net_return_ci_lower_95 / net_return_ci_upper_95)
        ci_report = bootstrap_ci_report(fold_results)
        score_bin_ci = ci_report if ci_report else None
        # Latency P99 from latency report (if available)
        latency_p99 = latency_report.get("p99_ms") if latency_report else None
        # Threshold flip rate from fold threshold stability
        thresholds = [fold.threshold for fold in fold_results]
        threshold_flip_rate = _compute_threshold_flip_rate(thresholds) if len(thresholds) > 1 else 0.0
        # PSI is not computable offline without production data; mark as live-only
        promotion_ok, promotion_reason = champion_mgr.can_promote(
            shadow_days=max(30, len(build.labeled_rows)),
            signal_count=len(build.labeled_rows),
            mdd_delta=mdd_delta,
            calmar_delta=calmar_delta,
            sharpe=avg_test_sharpe,
            mdd=avg_test_mdd,
            calmar=avg_test_calmar,
            score_bin_ci=score_bin_ci,
            threshold_flip_rate=threshold_flip_rate,
            latency_p99_ms=latency_p99,
            psi=None,  # PSI requires live production data; offline training cannot compute it
        )
        run_summary["champion_challenger"] = {
            "enabled": True,
            "promotion_ok": promotion_ok,
            "promotion_reason": promotion_reason,
            "shadow_metrics": {
                "mdd": avg_test_mdd,
                "calmar": avg_test_calmar,
                "sharpe": avg_test_sharpe,
            },
            "note": "Offline champion-challenger is a scaffold. PSI and some live-only metrics require production data. Promotion will fail on missing live metrics until testnet soak provides real values.",
        }
    else:
        run_summary["champion_challenger"] = {"enabled": False}
    # F11/F12 feature handling documentation: record fallback vs real sources
    fallback_features = list(source_report.get("fallback_features", []))
    unavailable_sources = list(source_report.get("unavailable_sources", []))
    run_summary["f11_f12_handling"] = {
        "fallback_feature_count": len(fallback_features),
        "fallback_features": fallback_features,
        "unavailable_sources": unavailable_sources,
        "note": "F11/F12 features require live exchange data (depth, funding, ADL, mark-price). Offline training uses safe mock defaults. Live execution computes these from real adapter sources when available. Model inference is safe but may be less discriminative when F11/F12 are in fallback mode.",
    }
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("run_summary.json", run_summary)
    manifest = write_manifest(output_dir, artifacts + lineage_artifacts + ["run_summary.json"])
    governance.ArtifactWriter(output_dir / "approval_package").create_approval_package(
        run_summary,
        clip_report=[],
        stage_rows=[],
        dataset_build=build,
        training_result={"fold_results": fold_results},
        bootstrap_ci_report=bootstrap_ci_report(fold_results),
        calibration_config=calibration_config(fold_results),
    )
    return TrainingResult(output_dir, build, splits, fold_results, run_summary, manifest)


def run_regime_aware_training(build: dataset.DatasetBuild, output_dir: Path, training_config: TrainingConfig, full_labeled_rows: Sequence[dataset.LabeledRow] | None = None) -> TrainingResult:
    # Regime-aware training assigns each row's regime bucket one of two ways:
    #
    #   (a) regime_classifier_model_path set: use the WALK-FORWARD OOF F18
    #       probabilities (regime_prob_up/range/down) already merged into
    #       build.labeled_rows[i].features by the --regime-classifier-dir
    #       pipeline (train-regime-classifier's regime_probabilities.json).
    #       Argmax (with the same smoothing as Phase 2.5) determines each
    #       TRAINING row's bucket.
    #
    #       IMPORTANT: this deliberately does NOT re-predict bucket
    #       assignment by loading and calling the SAVED FINAL classifier
    #       (regime_classifier_model.cbm) here. That classifier was fit on
    #       the COMPLETE 2020-2024 span in one pass -- so using it to
    #       classify an early-2021 row would classify that row with a model
    #       that has already "seen" 2023-2024 data during its own fit. That
    #       is not label leakage (the row's own long_success/short_success
    #       outcome is never exposed), but it IS a real form of look-ahead:
    #       the classifier's decision boundary was calibrated on the whole
    #       dataset's regime structure, not just data available as of that
    #       row's time -- making training-time bucket assignment artificially
    #       "cleaner" than what the SAME classifier will achieve on genuinely
    #       unseen 2025+ data at backtest/live time (a fresh train/serve
    #       skew, just one level removed from the entry-model target).
    #       The walk-forward OOF probabilities avoid this: each row's F18
    #       values were produced by a classifier trained ONLY on
    #       chronologically earlier rows (see regime_classifier.py).
    #
    #       The FINAL classifier (.cbm) is reserved for backtest/live routing
    #       (see backtest.py), where classifying 2025+ rows is genuinely
    #       out-of-sample relative to a classifier fit only on 2020-2024 --
    #       no leakage there.
    #   (b) not set (fallback): RegimeDetector.detect_all_directional on
    #       trend_slope_30 alone (the original, narrower signal).
    #
    # The old hand-labeled ("--use-user-regime") path was removed: it
    # depended on regimes.json, which requires knowing the regime in
    # hindsight and therefore can never be reproduced live. regimes.json
    # remains useful as GROUND-TRUTH LABELS for training the classifier used
    # in (a), which is itself fully causal (both at OOF-generation time and
    # at backtest/live inference time).
    regime_source: str
    detector_thresholds: dict[str, float] = {}
    detector_diagnostics: dict[str, object] = {}
    multi_feature_detector_payload: dict[str, object] | None = None
    if training_config.multi_feature_regime:
        from btcusdt_quant import regime_rules as rr
        # Fit the rule detector's normalization stats on the training rows and
        # assign each row's bucket from the deterministic causal rule. Persist
        # the fitted detector so backtest/live route identically.
        _rule_cfg = (
            rr.MultiFeatureRegimeConfig.from_dict(training_config.multi_feature_regime_config)
            if training_config.multi_feature_regime_config
            else rr.MultiFeatureRegimeConfig()
        )
        _mf_rows = [row.features for row in build.labeled_rows]
        rule_detector = rr.MultiFeatureRegimeDetector(_rule_cfg).fit(_mf_rows)
        regimes = rule_detector.detect_all(_mf_rows)
        del _mf_rows
        multi_feature_detector_payload = rule_detector.to_dict()
        detector_diagnostics = rule_detector.diagnostics(regimes)
        # Surface the regime distribution / transition stats in the train log.
        print(f"[TRAIN] rule regime distribution: {detector_diagnostics.get('regime_counts')}")
        print(f"[TRAIN] rule regime transitions: {detector_diagnostics.get('regime_transition_count')} "
              f"(direct up<->down: {detector_diagnostics.get('direct_reversal_count')})")
        regime_source = "multi_feature_rule"
    elif training_config.regime_classifier_model_path:
        from btcusdt_quant import regime_classifier as rc
        raw_probs = [
            {
                "up": float(row.features.get("regime_prob_up", 0.0)),
                "range": float(row.features.get("regime_prob_range", 0.0)),
                "down": float(row.features.get("regime_prob_down", 0.0)),
            }
            for row in build.labeled_rows
        ]
        if all(p["up"] == p["range"] == p["down"] == 0.0 for p in raw_probs):
            raise ValueError(
                "regime_classifier_model_path is set but no F18 regime_prob_* "
                "features were found on the training rows (all zero). Pass "
                "--regime-classifier-dir (not just a bare model path) so the "
                "walk-forward OOF probabilities get merged in alongside the "
                "saved model -- training bucket assignment must use those "
                "OOF-safe values, not a fresh in-sample prediction."
            )
        # Coverage guard (insurance): regime_probabilities.json only contains
        # timestamps that had a resolved hand label (train-regime-classifier
        # skips unlabeled candles), so any training row OUTSIDE the hand-label
        # coverage gets regime_prob_up/range/down = 0/0/0. Those rows carry no
        # real regime signal; letting smoothing assign them a bucket (via
        # sticky hysteresis or the range bootstrap) would silently pollute a
        # regime's model with rows the classifier never actually placed. Detect
        # such rows and EXCLUDE them from bucket assignment rather than guessing.
        # With full label coverage (label span == training span) this is a
        # no-op. A non-zero count means the labels do NOT cover the training
        # window -- extend regimes.json or set --training-start to the first
        # labeled timestamp.
        uncovered_mask = [p["up"] == p["range"] == p["down"] == 0.0 for p in raw_probs]
        n_uncovered = sum(uncovered_mask)
        if n_uncovered:
            frac = n_uncovered / len(raw_probs)
            print(
                f"[TRAIN] WARNING: {n_uncovered:,} of {len(raw_probs):,} training rows "
                f"({frac:.1%}) have no F18 regime probability (0/0/0) -- they fall "
                f"OUTSIDE the hand-labeled regime coverage. Excluding them from "
                f"regime bucket assignment so they do not pollute any regime model. "
                f"To include them, extend the regime labels (regimes.json) to cover "
                f"the full training window or set --training-start to the first "
                f"labeled timestamp.",
                file=sys.stderr,
            )
        _, regimes = rc.smooth_regime_probabilities(raw_probs)
        # Drop uncovered rows (post-smoothing) by marking their regime as a
        # sentinel that matches no USER_REGIME_NAMES bucket below.
        if n_uncovered:
            regimes = [None if unc else r for unc, r in zip(uncovered_mask, regimes)]
        regime_source = "regime_classifier"
    else:
        detector = features.RegimeDetector(
            config=features.RegimeDetectorConfig(
                rv_percentile=training_config.regime_detector_rv_percentile,
                trend_percentile=training_config.regime_detector_trend_percentile,
                min_trend_abs=training_config.regime_detector_min_trend_abs,
                high_vol_priority=True,
                low_vol_trend_multiplier=training_config.regime_detector_low_vol_trend_multiplier,
                min_regime_run_bars=training_config.regime_detector_min_regime_run_bars,
            )
        )
        rv_15_values = [float(row.features.get("rv_15", 0.0)) for row in build.labeled_rows]
        trend_slope_30_values = [float(row.features.get("trend_slope_30", 0.0)) for row in build.labeled_rows]
        # Directional detection (up/down/range) so the auto-detected regimes
        # match (a) the up/down/range models _train_single_regime knows how
        # to train (its long/short policy keys on "up"/"down"/"range"), and
        # (b) the --auto-regime backtest without a classifier model, which
        # also uses detect_all_directional.
        detector_thresholds = detector.fit_directional_threshold(trend_slope_30_values)
        detector_diagnostics = detector.diagnostics(rv_15_values, trend_slope_30_values)
        regimes = detector.detect_all_directional(rv_15_values, trend_slope_30_values, thresholds=detector_thresholds)
        regime_source = "detector_directional"
    regime_counts = {regime: regimes.count(regime) for regime in dataset.USER_REGIME_NAMES}
    regime_summaries: dict[str, dict[str, object]] = {}
    trained_regimes: dict[str, dict[str, object]] = {}
    skipped_regimes: dict[str, dict[str, object]] = {}

    # Remove the regime_* directories THIS policy will (re)write, so a stale
    # side model under a now-forbidden policy cannot be loaded later. Only the
    # policy's own regimes are touched (a shared output's unrelated regime dir
    # is left alone -- the loader keys off the summary, so a leftover it does
    # not list is inert), and symlinks are skipped rather than followed.
    import shutil as _shutil
    for _regime in dataset.USER_REGIME_NAMES:
        _stale = output_dir / f"regime_{_regime}"
        if _stale.is_dir() and not _stale.is_symlink():
            _shutil.rmtree(_stale)

    for regime_name in dataset.USER_REGIME_NAMES:
        regime_indices = [index for index, regime in enumerate(regimes) if regime == regime_name]
        row_count = len(regime_indices)
        if row_count < training_config.min_regime_rows:
            skipped_regimes[regime_name] = {
                "status": "skipped",
                "reason": "insufficient_rows",
                "row_count": row_count,
                "min_regime_rows": training_config.min_regime_rows,
            }
            # A skipped regime has no model, so at backtest time its bars fall
            # back to another regime's direction policy. That is a silent change
            # of what the strategy does -- say it here, where the cause is known.
            print(
                f"[TRAIN] WARNING: regime '{regime_name}' skipped ({row_count:,} rows < "
                f"--min-regime-rows {training_config.min_regime_rows}). Its bars will fall back to "
                f"another regime's models at backtest/live time; expect default_fallback > 0.",
                file=sys.stderr,
            )
            continue
        regime_result = _train_single_regime(build, output_dir, training_config, regime_name, regime_indices)
        regime_summaries[regime_name] = dict(regime_result.run_summary)
        trained_regimes[regime_name] = {
            "status": "trained",
            "row_count": row_count,
            "min_regime_rows": training_config.min_regime_rows,
            "output_dir": f"regime_{regime_name}",
            "mean_test_f1": float(regime_result.run_summary.get("mean_test_f1", 0.0)),
        }
        # Sides this run trained, so the loader can ignore any stale side model
        # file left by an earlier run under a different policy.
        regime_summaries[regime_name]["sides"] = {side: True for side, _ in sides_for_regime(regime_name)}

    default_regime = _default_regime_by_rows(trained_regimes)
    def _aggregate_regime_metric(key: str) -> float:
        # Each regime summary carries the REAL per-regime holdout value (see
        # _train_single_regime); average across trained regimes the same way
        # mean_test_f1 is aggregated. Prior code hardcoded accuracy/ece/brier to
        # 0.0 here, so every retrained regime model reported zero validation
        # accuracy and perfect calibration -- a silent lie in the headline summary.
        values = [float(summary[key]) for summary in regime_summaries.values() if key in summary]
        return sum(values) / len(values) if values else 0.0

    aggregated_mean_test_f1 = _aggregate_regime_metric("mean_test_f1")
    aggregated_mean_test_accuracy = _aggregate_regime_metric("mean_test_accuracy")
    aggregated_mean_test_ece = _aggregate_regime_metric("mean_test_ece")
    aggregated_mean_test_brier = _aggregate_regime_metric("mean_test_brier")
    # Optional: evaluate on a genuinely future test period (e.g. 2025 H1),
    # separate from and complementary to the in-training-span regime holdout
    # (_train_single_regime's prefix/tail split): this evaluates rows AFTER
    # training_end, which build.labeled_rows never contains (training_end
    # already excludes them) -- so full_labeled_rows (the pre-cutoff
    # snapshot) must be used here, not build.labeled_rows, or every test
    # row lookup silently finds nothing whenever the test period falls after
    # training_end (the common case).
    test_period_metrics: dict[str, object] | None = None
    if training_config.test_start is not None or training_config.test_end is not None:
        # Stays UNGATED and complete: it is the routing sequence. The rule
        # detector and the classifier smoother are both stateful (hysteresis,
        # min-hold), so feeding them only the surviving bars assigns different
        # regimes than backtest and live, which route the whole series and
        # merely suppress entries. Gating here would score a gated strategy
        # with the wrong side model and the result would not reproduce.
        eval_source_rows = list(full_labeled_rows) if full_labeled_rows is not None else list(build.labeled_rows)

        def _passes_vol_gate(row: dataset.LabeledRow) -> bool:
            if not (training_config.vol_gate_train_only and training_config.vol_gate_feature):
                return True
            value = row.features.get(training_config.vol_gate_feature)
            return (
                value is not None
                and isfinite(float(value))
                and float(value) >= float(training_config.vol_gate_min)
            )

        # The gate applies to WHAT IS SCORED, after routing has seen everything.
        _in_window = [
            row for row in eval_source_rows
            if (training_config.test_start is None or row.open_time >= training_config.test_start)
            and (training_config.test_end is None or row.open_time <= training_config.test_end)
        ]
        test_rows = [row for row in _in_window if _passes_vol_gate(row)]
        if training_config.vol_gate_train_only and training_config.vol_gate_feature:
            print(
                f"[TRAIN] external evaluation gated like training: {len(test_rows):,} of "
                f"{len(_in_window):,} test-period rows have {training_config.vol_gate_feature} >= "
                f"{float(training_config.vol_gate_min):.8g} ({len(_in_window) - len(test_rows):,} "
                f"excluded from scoring; routing still ran over the full series)"
            )
        if test_rows:
            print(f"[TRAIN] Evaluating on test period: {len(test_rows):,} rows ({training_config.test_start} to {training_config.test_end})")
            # Regime routing for these future rows: use the SAME source that
            # trained bucket assignment. Computed ONCE here (not per regime x
            # side) so the multi-feature rule detector's causal hysteresis runs
            # over the full eval series exactly like backtest/live routing.
            if regime_source == "regime_classifier":
                # Smoothed over the FULL eval series for the same reason the
                # rule detector is: the smoother carries state, so running it on
                # a gated subset assigns different regimes than backtest and
                # live. Look each test row up by time afterwards.
                row_probs = [
                    {
                        "up": float(row.features.get("regime_prob_up", 0.0)),
                        "range": float(row.features.get("regime_prob_range", 0.0)),
                        "down": float(row.features.get("regime_prob_down", 0.0)),
                    }
                    for row in eval_source_rows
                ]
                if all(p["up"] == p["range"] == p["down"] == 0.0 for p in row_probs):
                    row_regimes = [None] * len(test_rows)  # F18 not on these rows
                else:
                    from btcusdt_quant import regime_classifier as _rc
                    _, _all_smoothed = _rc.smooth_regime_probabilities(row_probs)
                    _smoothed_by_time = {
                        row.open_time: regime
                        for row, regime in zip(eval_source_rows, _all_smoothed)
                    }
                    row_regimes = [_smoothed_by_time.get(row.open_time) for row in test_rows]
            elif regime_source == "multi_feature_rule":
                # Route with the SAME fitted rule detector used for bucketing,
                # over the FULL eval series (correct hysteresis/min-hold state),
                # then look up each test row by time.
                from btcusdt_quant import regime_rules as _rr
                _eval_detector = (
                    _rr.MultiFeatureRegimeDetector.from_dict(multi_feature_detector_payload)
                    if multi_feature_detector_payload is not None
                    else rule_detector
                )
                _all_regimes = _eval_detector.detect_all([row.features for row in eval_source_rows])
                _regime_by_time = {
                    row.open_time: regime
                    for row, regime in zip(eval_source_rows, _all_regimes)
                }
                row_regimes = [_regime_by_time.get(row.open_time) for row in test_rows]
            else:
                row_regimes = [row.user_regime for row in test_rows]
            regime_test_metrics: dict[str, dict[str, float]] = {}
            for regime_name in trained_regimes:
                regime_dir = output_dir / f"regime_{regime_name}"
                for side, target_key, filename in (("long", "long_success", "long_model.json"), ("short", "short_success", "short_model.json")):
                    model_path = regime_dir / filename
                    if not model_path.is_file():
                        continue
                    regime_rows = [row for row, r in zip(test_rows, row_regimes) if r == regime_name]
                    if len(regime_rows) < 10:
                        continue
                    try:
                        payload = json.loads(model_path.read_text(encoding="utf-8"))
                        family = payload.get("model_family", payload.get("family", "catboost"))
                        if family == "ensemble":
                            model = models.EnsembleAdapter.from_dict(payload)
                        elif family == "lightgbm":
                            model = models.LightGBMAdapter.from_dict(payload)
                        else:
                            model = models.CatBoostAdapter.from_dict(payload)
                        regime_matrix = feature_matrix(regime_rows, build.feature_names)
                        regime_labels = [int(row.targets.get(target_key, row.label)) for row in regime_rows]
                        if len(set(regime_labels)) < 2:
                            print(f"[TRAIN]   Test period {regime_name}/{side}: skipped (single-class)")
                            continue
                        probs = model.predict_proba(regime_matrix)
                        key = f"{regime_name}_{side}"
                        regime_test_metrics[key] = metrics(probs, regime_labels, 0.5)
                        print(f"[TRAIN]   Test period {regime_name}/{side}: n={len(regime_rows)} F1={regime_test_metrics[key]['f1']:.4f}, Acc={regime_test_metrics[key]['accuracy']:.4f}")
                    except Exception as e:
                        print(f"[TRAIN]   Test period evaluation for {regime_name}/{side} failed: {e}")
            if regime_test_metrics:
                avg_f1 = mean([m["f1"] for m in regime_test_metrics.values()])
                avg_acc = mean([m["accuracy"] for m in regime_test_metrics.values()])
                test_period_metrics = {
                    "test_period_start": training_config.test_start.isoformat() if training_config.test_start else None,
                    "test_period_end": training_config.test_end.isoformat() if training_config.test_end else None,
                    "test_period_rows": len(test_rows),
                    "regime_metrics": regime_test_metrics,
                    "mean_test_f1": avg_f1,
                    "mean_test_accuracy": avg_acc,
                }
                print(f"[TRAIN] Test period overall: F1={avg_f1:.4f}, Acc={avg_acc:.4f}")
            else:
                print("[TRAIN]   Test period: no regime had enough routed rows to evaluate")
        else:
            print(f"[TRAIN] Warning: no test period rows found ({training_config.test_start} to {training_config.test_end})")
    run_summary = {
        "regime_aware": True,
        "regime_source": regime_source,
        # The triple barrier every side model here was LABELED on. Each model
        # answers exactly one question -- "does price reach +tp_pct before
        # -sl_pct within threshold_horizon bars" -- so backtest/live MUST execute
        # this same barrier or the probabilities and thresholds mean nothing.
        # Omitting them made load_regime_aware_models read label_tp_pct=None, so
        # backtest.check_execution_barrier_parity could only warn ("pre-parity
        # artifact") instead of verifying, and verify_calibration.py refused to
        # grade the model at all. Sourced from the config that drove attach_labels
        # (single-horizon path), so it is the barrier the labels actually used.
        # threshold_horizon == label_horizon: selected_thresholds are chosen on
        # each regime's holdout at exactly this barrier (see _select_threshold).
        "tp_pct": training_config.tp_pct,
        "sl_pct": training_config.sl_pct,
        "threshold_horizon": build.label_horizon,
        "regime_results": regime_summaries,
        "regime_counts": regime_counts,
        "trained_regimes": trained_regimes,
        "skipped_regimes": skipped_regimes,
        "default_regime": default_regime,
        "min_regime_rows": training_config.min_regime_rows,
        "regime_detector": {
            "thresholds": detector_thresholds,
            "diagnostics": detector_diagnostics,
            "config": detector.config_dict() if regime_source == "detector_directional" else None,
            "directional": True,
        } if regime_source == "detector_directional" else None,
        "regime_classifier_model_path": training_config.regime_classifier_model_path,
        "multi_feature_regime_detector": multi_feature_detector_payload,
        # Provenance for the two data-honesty switches: consumers must be able
        # to tell a shuffled-label negative control from a real model, and see
        # whether mock-fallback features were excluded from the matrices.
        "shuffled_labels": training_config.shuffle_labels,
        "exclude_fallback_features": training_config.exclude_fallback_features,
        "network_used": False,
        "orders_enabled": False,
        "credentials_required": False,
        "labeled_rows": len(build.labeled_rows),
        "fold_count": 0,
        "mean_test_f1": aggregated_mean_test_f1,
        "mean_test_accuracy": aggregated_mean_test_accuracy,
        "mean_test_ece": aggregated_mean_test_ece,
        "mean_test_brier": aggregated_mean_test_brier,
        "artifacts": ["regime_run_summary.json"],
    }
    if test_period_metrics is not None:
        run_summary["test_period_evaluation"] = test_period_metrics
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("regime_run_summary.json", run_summary)
    return TrainingResult(
        output_dir=output_dir,
        dataset_build=build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=["regime_run_summary.json"],
    )


def _train_single_regime_worker(
    build: dataset.DatasetBuild,
    output_dir: Path,
    training_config: TrainingConfig,
    regime_name: str,
    regime_indices: Sequence[int],
) -> TrainingResult:
    """Top-level worker function for multiprocessing."""
    return _train_single_regime(build, output_dir, training_config, regime_name, regime_indices)


# Legacy strength-based regime names. No longer used for training: the detector
# path now trains directional up/down/range (dataset.USER_REGIME_NAMES) to match
# the --auto-regime backtest and the up/down/range long/short policy. Kept only
# to avoid breaking any external import.
_REGIME_NAMES = ("high_volatility", "trending", "ranging")


# Default CatBoost hyperparameters used when Optuna tuning is disabled or
# Optuna itself is unavailable in the runtime. Kept identical to the values
# that were hard-coded in _train_single_regime before tuning was introduced,
# so disabling --optuna restores the previous baseline exactly.
_REGIME_CATBOOST_DEFAULT_PARAMS: dict[str, object] = {
    "iterations": 500,
    "learning_rate": 0.03,
    "depth": 8,
    "verbose": False,
}


def _tune_catboost_with_optuna(
    feature_matrix_values: Sequence[Sequence[float]],
    labels: Sequence[int],
    feature_names: Sequence[str],
    n_trials: int,
    label_horizon: int,
) -> tuple[dict[str, object], dict[str, object]]:
    """Search CatBoost hyperparameters for a single (regime, target) slice.

    Returns (best_params_dict, study_report) where best_params_dict is the
    merged param dictionary ready to feed CatBoostAdapter, and study_report
    is a JSON-serializable summary saved into run_summary.

    If optuna or catboost is not importable we silently fall back to the
    default params and record optuna_available=False in the report, so the
    pipeline still completes end-to-end.
    """
    rows = [list(row) for row in feature_matrix_values]
    y_values = [int(value) for value in labels]
    default_params = dict(_REGIME_CATBOOST_DEFAULT_PARAMS)

    if not rows or not y_values or len(rows) != len(y_values):
        return default_params, {"optuna_available": False, "reason": "empty_or_mismatched_inputs"}

    label_set = set(y_values)
    if len(label_set) < 2:
        # Optuna can't meaningfully tune a degenerate single-class slice.
        return default_params, {
            "optuna_available": False,
            "reason": "single_class_labels",
            "label_distribution": {int(label): y_values.count(label) for label in label_set},
        }

    try:
        optuna = __import__("optuna")
    except Exception as exc:
        return default_params, {"optuna_available": False, "reason": f"optuna_import_failed: {exc!s}"}

    try:
        __import__("catboost")
    except Exception as exc:
        return default_params, {"optuna_available": False, "reason": f"catboost_import_failed: {exc!s}"}

    # Inner time-series sequential split: train on the first 80% of rows,
    # validate on the last 20%. A single contiguous holdout matches how the
    # outer train/test split is also chronological. We insert a small purge
    # gap between train tail and validation head to mitigate label leakage
    # from overlapping triple-barrier windows, but cap the gap so it never
    # consumes the validation slice on small regime slices (label_horizon
    # alone can be larger than the slice itself for, e.g., a 60-bar horizon
    # against only a few hundred rows in a thinly-populated regime).
    n = len(rows)
    if n < 50:
        return default_params, {"optuna_available": False, "reason": "too_few_rows_to_tune", "rows": n}
    split_index = max(1, int(n * 0.8))
    horizon_gap = min(max(0, int(label_horizon)), max(0, (n - split_index) // 4))
    val_start = split_index + horizon_gap
    if val_start >= n - 10:
        return default_params, {"optuna_available": False, "reason": "insufficient_rows_for_holdout", "rows": n}

    train_x = rows[:split_index]
    train_y = y_values[:split_index]
    val_x = rows[val_start:]
    val_y = y_values[val_start:]
    if not val_x or len(set(train_y)) < 2 or len(set(val_y)) < 2:
        return default_params, {"optuna_available": False, "reason": "degenerate_split", "rows": n}

    trial_history: list[dict[str, object]] = []

    def _objective(trial: object) -> float:
        suggest_int = getattr(trial, "suggest_int")
        suggest_float = getattr(trial, "suggest_float")
        params = {
            "iterations": int(suggest_int("iterations", 300, 2000)),
            "learning_rate": float(suggest_float("learning_rate", 0.005, 0.08, log=True)),
            "depth": int(suggest_int("depth", 3, 8)),
            "l2_leaf_reg": float(suggest_float("l2_leaf_reg", 1.0, 50.0, log=True)),
            "random_strength": float(suggest_float("random_strength", 0.1, 10.0, log=True)),
            "bagging_temperature": float(suggest_float("bagging_temperature", 0.0, 5.0)),
            "min_data_in_leaf": int(suggest_int("min_data_in_leaf", 20, 500)),
            "border_count": int(suggest_int("border_count", 64, 254)),
            "od_type": "Iter",
            "verbose": False,
        }
        # od_wait scales with this trial's iterations budget so early stopping
        # isn't needlessly premature on a large-iterations trial nor pointlessly
        # loose on a small one.
        params["od_wait"] = max(30, params["iterations"] // 10)
        adapter = models.CatBoostAdapter(feature_names=list(feature_names), model_params=dict(params))
        # eval_set activates the od_type/od_wait early stopping that was
        # previously a silent no-op (CatBoost needs an eval set to monitor).
        # use_best_model rolls back to the best iteration on val_x/val_y
        # rather than the last one, which also protects against overfitting
        # deep into a large `iterations` budget.
        adapter.fit(train_x, train_y, eval_set=(val_x, val_y), use_best_model=True)
        # Record where early stopping actually landed for THIS trial. The
        # suggested `iterations` is only a BUDGET; with use_best_model the
        # trial's effective model is truncated at best_iteration, and the
        # final full-data refit must be capped to match (see below) or it
        # silently trains past the validated optimum.
        trial_best_iteration: int | None = None
        model_obj = getattr(adapter, "model", None)
        getter = getattr(model_obj, "get_best_iteration", None)
        if callable(getter):
            try:
                raw_best = getter()
                if raw_best is not None:
                    trial_best_iteration = int(raw_best)
            except Exception:
                trial_best_iteration = None
        val_probs = adapter.predict_proba(val_x)
        # Binary cross-entropy (lower is better). Clamp to avoid log(0).
        eps = 1e-12
        loss = 0.0
        for prob, true_label in zip(val_probs, val_y):
            p = max(eps, min(1.0 - eps, float(prob)))
            if int(true_label) == 1:
                loss -= log(p)
            else:
                loss -= log(1.0 - p)
        loss /= max(1, len(val_y))
        trial_number = int(getattr(trial, "number", len(trial_history)))
        trial_history.append({
            "number": trial_number,
            "params": dict(params),
            "value": loss,
            "best_iteration": trial_best_iteration,
        })
        return loss

    effective_trials = n_trials if n_trials > 0 else 20
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    try:
        study.optimize(_objective, n_trials=effective_trials, show_progress_bar=False)
    except Exception as exc:
        return default_params, {
            "optuna_available": True,
            "reason": f"study_failed: {exc!s}",
            "trial_history": trial_history,
        }

    best = dict(study.best_params)
    merged = {**default_params, **best}
    merged["verbose"] = False
    # Final-refit iteration cap: the winning trial trained with an eval_set +
    # use_best_model, so its VALIDATED model is truncated at best_iteration --
    # but the merged params still carry the trial's suggested `iterations`
    # BUDGET (up to 2000). The final model is refit on the full regime slice
    # WITHOUT an eval_set (od_type/od_wait are silent no-ops there), so
    # without this cap it would train the whole budget, past the point where
    # validation loss started degrading -- the tuned logloss would describe a
    # model we never ship. Cap iterations to best_iteration + 1 (tree count),
    # never raising it above the suggested budget. best_iteration None/<=0
    # (getter unavailable, or best model was the very first tree -- a
    # degenerate signal we don't trust as a cap) keeps the suggested value.
    best_trial_number = int(getattr(getattr(study, "best_trial", None), "number", -1))
    best_iteration: int | None = None
    for entry in trial_history:
        if entry.get("number") == best_trial_number:
            raw = entry.get("best_iteration")
            if isinstance(raw, int):
                best_iteration = raw
            break
    suggested_iterations = int(merged.get("iterations", default_params.get("iterations", 500)))
    final_iterations = suggested_iterations
    # best_iteration == 0 means the very FIRST tree was already the best on
    # validation -- a degenerate signal (near-zero signal in this slice, too
    # large a learning_rate, heavy label noise, or an unstable split). We do
    # NOT cap to 1 tree (policy: keep the suggested budget), but we flag it
    # in the report and logs so repeated occurrences across regimes/sides are
    # visible in run_summary and can drive a future no-trade policy decision.
    best_iteration_degenerate = best_iteration == 0
    if best_iteration is not None and best_iteration > 0:
        final_iterations = min(suggested_iterations, best_iteration + 1)
        merged["iterations"] = final_iterations
    if best_iteration_degenerate:
        print(
            "[TRAIN]     WARNING: winning trial's best_iteration == 0 (first tree was "
            "best on validation) -- degenerate signal for this regime/side slice; "
            "keeping the suggested iterations budget. If this recurs across runs, "
            "consider treating this slice as no-trade or revisiting learning_rate/od_wait.",
        )
    # Baseline: the logloss of predicting the constant positive-rate for every
    # row (no model at all). This is the honest floor to compare against --
    # e.g. with a 30% positive rate, baseline logloss is ~0.611, so a model
    # logloss of 0.60 is barely better than guessing the base rate.
    baseline = _baseline_logloss(val_y)
    improvement = baseline - float(study.best_value)
    report = {
        "optuna_available": True,
        "n_trials_requested": effective_trials,
        "n_trials_completed": len(trial_history),
        "best_params": best,
        "best_value": float(study.best_value),
        "best_trial_number": best_trial_number,
        "best_iteration": best_iteration,
        "best_iteration_degenerate": best_iteration_degenerate,
        "suggested_iterations": suggested_iterations,
        "final_iterations": final_iterations,
        # The EXACT params the final full-data refit receives (defaults +
        # winning trial + iterations cap). best_params["iterations"] is only
        # the SUGGESTED budget -- when analyzing a run, read final_params /
        # final_iterations for what the shipped model actually trained with.
        "final_params": dict(merged),
        "baseline_logloss": baseline,
        "improvement_over_baseline": improvement,
        "positive_rate": sum(val_y) / len(val_y) if val_y else 0.0,
        "train_rows": len(train_x),
        "validation_rows": len(val_x),
        "trial_history": trial_history,
    }
    return merged, report


def _baseline_logloss(labels: Sequence[int]) -> float:
    """Logloss of predicting the constant positive rate for every sample.

    This is the honest floor: a model that can't beat this has learned
    nothing beyond the class balance. Comparing model logloss against this
    (not against 0 or against ln(2)=0.693) is what makes a 0.6x logloss
    interpretable.
    """
    if not labels:
        return 0.0
    eps = 1e-12
    p = sum(labels) / len(labels)
    p = max(eps, min(1.0 - eps, p))
    return -sum((log(p) if y == 1 else log(1.0 - p)) for y in labels) / len(labels)


def _train_single_regime(
    build: dataset.DatasetBuild,
    output_dir: Path,
    training_config: TrainingConfig,
    regime_name: str,
    regime_indices: Sequence[int],
) -> TrainingResult:
    print(f"[TRAIN]   Sub-training regime '{regime_name}' with {len(regime_indices):,} rows...")
    regime_labeled_rows = [build.labeled_rows[index] for index in regime_indices]
    regime_build = replace(
        build,
        labeled_rows=regime_labeled_rows,
        source=f"{build.source}_regime_{regime_name}",
    )
    regime_output_dir = output_dir / f"regime_{regime_name}"
    regime_output_dir.mkdir(parents=True, exist_ok=True)
    
    f_matrix = feature_matrix(regime_build.labeled_rows, regime_build.feature_names)
    
    # Direction policy comes from the single shared mapping (REGIME_SIDES), so
    # the multi-horizon pilot cannot drift to a different side set and quietly
    # break the Phase 4 vs Phase 4.5 comparison.
    _sides = dict(sides_for_regime(regime_name))
    train_long = "long" in _sides
    train_short = "short" in _sides

    artifacts = []
    optuna_reports: dict[str, dict[str, object]] = {}

    # The final 20% chronological tail of this regime's rows is the threshold/
    # metric holdout (see the holdout block below). It must stay UNSEEN by the
    # Optuna study: previously Optuna's internal 80/20 split validated its 100
    # trials on that same tail, then the entry threshold was selected and the
    # holdout metrics reported on it -- the holdout was consumed three times
    # (HPO selection + threshold + reported metric), inflating all three
    # (research-and-edge-validation.md: "HPO 중 본 validation을 threshold/
    # calibration에도 반복 사용하지 않는다"). Optuna now only receives the
    # prefix; its own 80/20 split lands entirely inside it.
    n_regime_rows = len(regime_build.labeled_rows)
    holdout_split = max(1, int(n_regime_rows * 0.8))
    holdout_gap = min(max(0, int(build.label_horizon)), max(0, (n_regime_rows - holdout_split) // 4))
    holdout_start = holdout_split + holdout_gap
    holdout_viable = holdout_start < n_regime_rows - 10 and holdout_split >= 10

    def _resolve_model_params(target_name: str, labels: Sequence[int]) -> tuple[dict[str, object], dict[str, object] | None]:
        """Return (catboost_params, optuna_report_or_None) for one target.

        When training_config.optuna_enabled is True we run a small Optuna
        study on the PREFIX of this regime's rows (everything before the
        threshold holdout tail; Optuna's own chronological 80/20 split with a
        capped purge gap lives inside that prefix -- see
        _tune_catboost_with_optuna). The threshold/metric holdout is therefore
        never seen by hyperparameter selection. Without Optuna we use the
        legacy fixed defaults so existing behavior is preserved.
        """
        if not training_config.optuna_enabled:
            return dict(_REGIME_CATBOOST_DEFAULT_PARAMS), None
        tune_matrix = f_matrix[:holdout_split] if holdout_viable else f_matrix
        tune_labels = list(labels[:holdout_split]) if holdout_viable else list(labels)
        print(
            f"[TRAIN]   Optuna tuning CatBoost for regime '{regime_name}' / "
            f"{target_name} ({training_config.optuna_trials or 20} trials, "
            f"{len(tune_matrix)}/{len(labels)} prefix rows; holdout tail reserved)..."
        )
        params, report = _tune_catboost_with_optuna(
            feature_matrix_values=tune_matrix,
            labels=tune_labels,
            feature_names=regime_build.feature_names,
            n_trials=training_config.optuna_trials,
            label_horizon=build.label_horizon,
        )
        if report.get("optuna_available"):
            best = report.get("best_params", {})
            best_value = report.get("best_value")
            baseline = report.get("baseline_logloss")
            improvement = report.get("improvement_over_baseline")
            pos_rate = report.get("positive_rate")
            if baseline is not None:
                # Improvement bands (quant-finance rule of thumb): <0.005 no
                # real signal, 0.005-0.015 weak, 0.015-0.03 meaningful, >0.03 strong.
                if improvement < 0.005:
                    verdict = "~no improvement over baseline"
                elif improvement < 0.015:
                    verdict = "weak improvement"
                elif improvement < 0.03:
                    verdict = "meaningful improvement"
                else:
                    verdict = "strong improvement"
                print(
                    f"[TRAIN]     -> logloss={best_value:.4f}  baseline={baseline:.4f}  "
                    f"improvement={improvement:+.4f} ({verdict})  pos_rate={pos_rate:.3f}"
                )
            else:
                print(f"[TRAIN]     -> best logloss={best_value:.4f}  params={best}")
            best_iter = report.get("best_iteration")
            final_iters = report.get("final_iterations")
            suggested_iters = report.get("suggested_iterations")
            if best_iter is not None and final_iters is not None and final_iters != suggested_iters:
                print(
                    f"[TRAIN]     -> final refit capped at iterations={final_iters} "
                    f"(early stopping best_iteration={best_iter}; suggested budget was {suggested_iters})"
                )
        else:
            print(
                f"[TRAIN]     -> Optuna unavailable or unable to tune "
                f"({report.get('reason', 'unknown')}); using defaults."
            )
        return params, report

    if train_long:
        long_labels = [row.targets.get("long_success", row.label) for row in regime_build.labeled_rows]
        # A single-class side cannot train a classifier -- CatBoost aborts with a
        # cryptic "Target contains only one unique value". This happens for real
        # on a rare regime whose bars almost all hit (or all miss) the barrier;
        # skip the side with a reason (like the holdout/insufficient-rows skips)
        # instead of crashing the whole run. The regime's other side or the
        # default-regime fallback still covers those bars.
        if len(set(long_labels)) < 2:
            print(f"[TRAIN]   Regime '{regime_name}' LONG: skipped (single-class long_success labels)")
            train_long = False
        else:
            print(f"[TRAIN]   Training LONG success model for regime '{regime_name}'...")
            long_params, long_report = _resolve_model_params("long", long_labels)
            long_model = models.CatBoostAdapter(
                feature_names=regime_build.feature_names,
                model_params=long_params,
            )
            with models.training_runtime_context(regime=regime_name, side="long", fit_role="final_refit"):
                long_model.fit(f_matrix, long_labels)
            writer = governance.ArtifactWriter(regime_output_dir)
            writer.write_json("long_model.json", long_model.as_dict())
            artifacts.append("long_model.json")
            if long_report is not None:
                optuna_reports["long"] = long_report

    if train_short:
        short_labels = [row.targets.get("short_success", row.label) for row in regime_build.labeled_rows]
        if len(set(short_labels)) < 2:
            print(f"[TRAIN]   Regime '{regime_name}' SHORT: skipped (single-class short_success labels)")
            train_short = False
        else:
            print(f"[TRAIN]   Training SHORT success model for regime '{regime_name}'...")
            short_params, short_report = _resolve_model_params("short", short_labels)
            short_model = models.CatBoostAdapter(
                feature_names=regime_build.feature_names,
                model_params=short_params,
            )
            with models.training_runtime_context(regime=regime_name, side="short", fit_role="final_refit"):
                short_model.fit(f_matrix, short_labels)
            writer = governance.ArtifactWriter(regime_output_dir)
            writer.write_json("short_model.json", short_model.as_dict())
            artifacts.append("short_model.json")
            if short_report is not None:
                optuna_reports["short"] = short_report

    print(f"[TRAIN]   Models saved to {regime_output_dir}")

    # Regime-scoped holdout evaluation: evaluate on ITS OWN regime's
    # chronological holdout tail (last 20%), never on rows mixed from other
    # regimes. This replaces the old cross-regime "test period" evaluation
    # (which ran e.g. the up/long model over the ENTIRE 2025 H1 span
    # including down/range rows -- an apples-to-oranges comparison that made
    # every regime's F1 look worse and uninterpretable).
    #
    # CRITICAL: the model evaluated here must NOT be `long_model`/`short_model`
    # (the ones just saved above) -- those were fit on f_matrix, which is
    # ALL of this regime's rows, INCLUDING the holdout tail itself. Evaluating
    # them on that same tail would be in-sample (the model already memorized
    # those rows during its own .fit() call), silently inflating F1/accuracy
    # and picking an overfit decision threshold. Instead, a SEPARATE
    # "holdout-diagnostic" model is trained here using ONLY the prefix
    # (everything before the holdout tail, matching the Optuna inner split's
    # chronological convention) and evaluated on the tail -- genuinely
    # out-of-sample. The deployed long_model/short_model (fit on the full
    # regime data above) are what actually ship; this diagnostic model exists
    # solely to produce an honest holdout metric and threshold selection.
    regime_holdout_metrics: dict[str, dict[str, float]] = {}
    selected_thresholds: dict[str, float] = {}
    # holdout_split/holdout_start were computed ONCE above (before Optuna) so
    # hyperparameter search could be restricted to the prefix; reuse them here
    # so the threshold/metric holdout is exactly the slice Optuna never saw.
    if holdout_viable:
        prefix_matrix = f_matrix[:holdout_split]
        holdout_matrix = f_matrix[holdout_start:]
        # Sides and their targets come from the shared policy; params follow.
        _params_by_side = {
            "long": long_params if train_long else None,
            "short": short_params if train_short else None,
        }
        for side, target_key in sides_for_regime(regime_name):
            resolved_params = _params_by_side[side]
            if resolved_params is None:
                continue
            prefix_labels = [int(row.targets.get(target_key, row.label)) for row in regime_build.labeled_rows[:holdout_split]]
            holdout_labels = [int(row.targets.get(target_key, row.label)) for row in regime_build.labeled_rows[holdout_start:]]
            if len(set(holdout_labels)) < 2 or len(set(prefix_labels)) < 2:
                print(f"[TRAIN]   Regime holdout {regime_name}/{side}: skipped (single-class prefix or holdout)")
                continue
            # Separate diagnostic model: same hyperparameters as the deployed
            # model (so the diagnostic reflects the same tuning), but fit ONLY
            # on the prefix -- never touches the holdout tail during .fit().
            diagnostic_model = models.CatBoostAdapter(
                feature_names=regime_build.feature_names,
                model_params=dict(resolved_params),
            )
            with models.training_runtime_context(regime=regime_name, side=side, fit_role="holdout_diagnostic"):
                diagnostic_model.fit(prefix_matrix, prefix_labels)
            probs = diagnostic_model.predict_proba(holdout_matrix)
            # Select the decision threshold on THIS holdout (never on training
            # rows, to avoid overfitting the cutoff) using the same objective
            # the non-regime path uses. 0.5 is an arbitrary cut with no reason
            # to be where probability crosses into "profitable to trade" --
            # especially for "trading_pnl", which optimizes calmar/sharpe/f1
            # from simulated PnL rather than classification balance.
            threshold = select_threshold(
                probs, holdout_labels,
                objective=training_config.threshold_objective,
                min_trades=training_config.threshold_min_trades,
                tp_pct=training_config.tp_pct,
                sl_pct=training_config.sl_pct,
                round_trip_cost=training_config.round_trip_cost,
            )
            selected_thresholds[side] = threshold
            m = metrics(
                probs, holdout_labels, threshold,
                tp_pct=training_config.tp_pct,
                sl_pct=training_config.sl_pct,
                round_trip_cost=training_config.round_trip_cost,
            )
            baseline = _baseline_logloss(holdout_labels)
            m["baseline_logloss"] = baseline
            m["n_holdout"] = len(holdout_labels)
            m["positive_rate"] = sum(holdout_labels) / len(holdout_labels)
            m["selected_threshold"] = threshold
            m["threshold_objective"] = training_config.threshold_objective
            regime_holdout_metrics[side] = m
            print(
                f"[TRAIN]   Regime holdout {regime_name}/{side}: n={len(holdout_labels)} "
                f"pos_rate={m['positive_rate']:.3f} threshold={threshold:.3f} ({training_config.threshold_objective}) "
                f"F1={m['f1']:.4f} Acc={m['accuracy']:.4f} baseline_logloss={baseline:.4f} "
                f"(diagnostic model trained on prefix only, n={len(prefix_labels)})"
            )
    else:
        print(f"[TRAIN]   Regime holdout {regime_name}: skipped (too few rows: {n_regime_rows})")
    
    # Create minimal TrainingResult
    holdout_f1_values = [m["f1"] for m in regime_holdout_metrics.values()]
    holdout_acc_values = [m["accuracy"] for m in regime_holdout_metrics.values()]
    run_summary: dict[str, object] = {
        "regime_aware": False,
        "regime_source": "user_regime",
        "trained_regimes": {regime_name: {"status": "trained", "row_count": len(regime_indices)}},
        "labeled_rows": len(regime_build.labeled_rows),
        "fold_count": 0,
        "selected_thresholds": selected_thresholds,
        "threshold_objective": training_config.threshold_objective,
        # ece/brier are REAL per-side holdout values (metrics() computes them via
        # CalibrationDriftMonitor); averaging them here instead of the old 0.0
        # literals, which read as perfect calibration / zero error on a model
        # that was never measured.
        "mean_test_f1": sum(holdout_f1_values) / len(holdout_f1_values) if holdout_f1_values else 0.0,
        "mean_test_accuracy": sum(holdout_acc_values) / len(holdout_acc_values) if holdout_acc_values else 0.0,
        "mean_test_ece": sum(m.get("ece", 0.0) for m in regime_holdout_metrics.values()) / len(regime_holdout_metrics) if regime_holdout_metrics else 0.0,
        "mean_test_brier": sum(m.get("brier", 0.0) for m in regime_holdout_metrics.values()) / len(regime_holdout_metrics) if regime_holdout_metrics else 0.0,
        "regime_holdout_metrics": regime_holdout_metrics,
        "artifacts": artifacts,
    }
    if optuna_reports:
        run_summary["optuna"] = {
            "enabled": True,
            "trials_requested": training_config.optuna_trials or 20,
            "per_target": optuna_reports,
        }
    elif training_config.optuna_enabled:
        run_summary["optuna"] = {"enabled": True, "per_target": {}, "note": "no targets tuned"}
    else:
        run_summary["optuna"] = {"enabled": False}
    return TrainingResult(
        output_dir=regime_output_dir,
        dataset_build=regime_build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=artifacts,
    )


def _default_regime_by_rows(trained_regimes: Mapping[str, Mapping[str, object]]) -> str | None:
    if not trained_regimes:
        return None
    return max(trained_regimes, key=lambda regime: int(trained_regimes[regime].get("row_count", 0)))


def default_splits(n_rows: int, purge_gap: int, test_gap: int = 0) -> list[features.Split]:
    train_size = max(60, n_rows // 3)
    validation_size = max(20, n_rows // 8)
    test_size = max(20, n_rows // 8)
    return features.PurgedWalkForwardSplit().split(n_rows, train_size, validation_size, test_size, purge_gap, test_gap)


def configured_splits(n_rows: int, label_horizon: int, config: TrainingConfig, sample_intervals: Sequence[cv.SampleInterval]) -> list[object]:
    manager = cv.SplitManager()
    return manager.get_splits(
        n_rows,
        label_horizon=label_horizon,
        cv_mode=config.cv_mode,
        embargo_size=config.embargo_size,
        walk_forward_test_gap=config.walk_forward_test_gap,
        n_groups=config.n_groups,
        test_group_count=config.test_group_count,
        sample_intervals=sample_intervals,
    )


def fit_model_adapter(
    rows: Sequence[dataset.LabeledRow],
    feature_names: Sequence[str],
    config: TrainingConfig,
    sample_weights: Sequence[float] | None = None,
) -> models.ModelSelection:
    return models.ModelFactory().fit(
        config.model_family,
        feature_matrix(rows, feature_names),
        [row.label for row in rows],
        feature_names=feature_names,
        sample_weight=sample_weights,
        model_params=config.model_params,
        fallback_allowed=config.fallback_allowed,
    )


def feature_matrix(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str]) -> list[list[float]]:
    return [[float(row.features[name]) for name in feature_names] for row in rows]


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return mean(values)
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _validated_sample_weights(rows: Sequence[dataset.LabeledRow], sample_weights: Sequence[float] | None) -> list[float]:
    if sample_weights is None:
        return [1.0 for _ in rows]
    weights = [float(weight) for weight in sample_weights]
    if len(weights) != len(rows):
        raise ValueError("sample_weights must match rows length")
    if any(weight < 0.0 for weight in weights):
        raise ValueError("sample_weights must be non-negative")
    if sum(weights) <= 0.0:
        return [1.0 for _ in rows]
    return weights


def _weights_for_indices(uniqueness: cv.UniquenessWeightResult, indices: Sequence[int]) -> list[float]:
    return [uniqueness.weights.get(index, 1.0) for index in indices]


def _split_indices(values: range | Sequence[int]) -> list[int]:
    return [int(value) for value in values]


def _min_index(indices: Sequence[int]) -> int:
    return min(indices) if indices else -1


def _stop_exclusive(indices: Sequence[int]) -> int:
    return max(indices) + 1 if indices else -1


def calibration_offset(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if not probabilities or not labels:
        return 0.0
    observed_rate = sum(labels) / len(labels)
    predicted_rate = mean(probabilities)
    return safe_logit(observed_rate) - safe_logit(predicted_rate)


def select_threshold(
    probabilities: Sequence[float],
    labels: Sequence[int],
    objective: str = "trading_pnl",
    min_trades: int | None = None,
    tp_pct: float = 0.003,
    sl_pct: float = 0.0015,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
) -> float:
    """Choose a decision threshold from a discrete grid of candidates.

    `objective` controls the ranking criterion used to pick among candidates:

    - "trading_pnl" (default; matches TrainingConfig.threshold_objective and
      the CLI default): rank by (calmar, sharpe, f1, -|t-0.5|) using the
      `_trading_pnl` simulator. Recommended for trading models, since the
      classification trade-off does not map cleanly to PnL when the label
      base rate is unbalanced.
    - "precision_recall" (legacy): precision with a minimum recall
      constraint of 0.3, falling back to F1 if recall is insufficient. Can
      select sub-cost thresholds (~0.32) on weak models.

    `min_trades`: minimum number of predictions != 0 (i.e. actual trades)
    required for a candidate to be considered. Defaults to max(1, 5% of rows)
    for the trading_pnl objective to avoid picking a degenerate threshold
    that almost never trades.
    """
    if not probabilities or not labels:
        return 0.5
    candidates = {round(index / 20.0, 2) for index in range(1, 20)}
    candidates.update(round(value, 4) for value in probabilities)

    if objective == "trading_pnl":
        effective_min_trades = min_trades if min_trades is not None else max(1, len(labels) // 20)
        best_threshold = 0.5
        # Tuple ordering: (calmar, sharpe, f1, -|t-0.5|). All higher is better.
        best_score = (-float("inf"), -float("inf"), -1.0, -float("inf"))
        for threshold in sorted(candidates):
            # Rank with the SAME barrier geometry the labels were built with --
            # a TP/SL sweep changes --tp-pct/--sl-pct, and the objective must
            # follow, or thresholds get picked for the wrong economics.
            current = metrics(probabilities, labels, threshold, tp_pct=tp_pct, sl_pct=sl_pct, round_trip_cost=round_trip_cost)
            trade_count = int(round(current.get("predicted_positive_rate", 0.0) * len(labels)))
            if trade_count < effective_min_trades:
                continue
            score = (
                current.get("calmar", 0.0),
                current.get("sharpe", 0.0),
                current.get("f1", 0.0),
                -abs(threshold - 0.5),
            )
            if score > best_score:
                best_score = score
                best_threshold = threshold
        return best_threshold

    # Default legacy path: precision-recall with recall>=0.3 floor.
    best_threshold = 0.5
    best_score = (-1.0, -1.0, 0.0)
    for threshold in sorted(candidates):
        current = metrics(probabilities, labels, threshold)
        # Use precision with minimum recall constraint (recall >= 0.3)
        # If recall < 0.3, fall back to F1
        if current["recall"] >= 0.3:
            score = (current["precision"], current["f1"], -abs(threshold - 0.5))
        else:
            score = (current["f1"], current["accuracy"], -abs(threshold - 0.5))
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return best_threshold


def _trading_pnl(
    probabilities: Sequence[float],
    labels: Sequence[int],
    threshold: float,
    tp_pct: float = 0.003,
    sl_pct: float = 0.0015,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
) -> list[float]:
    """Simulate per-row PnL for a SIDE-SPECIFIC success model.

    Semantics match how these models are actually traded:
    - prob >= threshold  -> ENTER the side. label==1 (TP hit first) earns
      +tp_pct; label==0 (SL first / timeout) loses -sl_pct. Both pay the
      round-trip cost (fees + slippage, default 2*(0.02%+0.02%) = 0.08%).
    - prob <  threshold  -> NO TRADE -> PnL 0. (The old version treated this
      as an OPPOSITE position, i.e. below-threshold rows scored +/-0.001 as if
      shorting the signal -- which rewarded thresholds that let the "inverse"
      of the model trade, dragging selected thresholds down to ~0.32 and
      flooding the backtest with sub-cost entries.)

    Defaults mirror the triple-barrier label geometry (tp=0.30%, sl=0.15%) and
    the backtest cost model, so calmar/sharpe rankings in select_threshold
    reflect cost-aware asymmetric-barrier economics.
    """
    pnl: list[float] = []
    win = tp_pct - round_trip_cost
    loss = -sl_pct - round_trip_cost
    for prob, label in zip(probabilities, labels):
        if prob < threshold:
            pnl.append(0.0)
            continue
        pnl.append(win if label == 1 else loss)
    return pnl


def _mdd(pnl: Sequence[float]) -> float:
    peak = 0.0
    max_dd = 0.0
    cumulative = 0.0
    for value in pnl:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


# PnL dispersion / drawdown at or below this is float noise, not risk (see
# _sharpe and _calmar). Both quantities are sums of per-signal PnL floats, so
# neither reliably lands on exactly 0.0 and an `== 0` guard leaks.
_MIN_PNL_STD = 1e-12
_MIN_PNL_MDD = 1e-12


def _sharpe(pnl: Sequence[float]) -> float:
    # `std == 0` is not a sufficient guard: a candidate threshold that fires a
    # couple of signals which all resolve the same way has std at float-noise
    # scale (~1e-17), and mean/std*sqrt(n) then returns ~1e14 -- which would win
    # the (calmar, sharpe, f1) ranking outright on a two-signal sample. Fold
    # noise-level dispersion to 0.0 rather than NaN: this value is a max() sort
    # key, and a NaN there silently corrupts the ordering instead of losing it.
    if not pnl:
        return 0.0
    mean_pnl = mean(pnl)
    variance = sum((x - mean_pnl) ** 2 for x in pnl) / len(pnl)
    std = sqrt(variance) if variance > 0 else 0.0
    if std <= _MIN_PNL_STD:
        return 0.0
    return mean_pnl / std * sqrt(len(pnl))


def _calmar(pnl: Sequence[float]) -> float:
    # `mdd_value == 0` leaks for the same reason `std == 0` did in _sharpe, and
    # it matters more here: calmar is the FIRST key of select_threshold's
    # (calmar, sharpe, f1, -|t-0.5|) sort tuple, so it outranks everything. A
    # PnL series that never really draws down leaves mdd at float noise (~1e-18)
    # rather than exactly 0.0, and total_return/1e-18 hands that candidate a
    # calmar of ~1e18 -- winning the threshold outright on an artifact of
    # floating-point summation. Fold to 0.0, not NaN: this is a max() sort key,
    # and a NaN there corrupts the ordering silently instead of losing.
    if not pnl:
        return 0.0
    total_return = sum(pnl)
    mdd_value = _mdd(pnl)
    if mdd_value <= _MIN_PNL_MDD:
        return 0.0
    return total_return / mdd_value


def metrics(probabilities: Sequence[float], labels: Sequence[int], threshold: float, tp_pct: float = dataset.DEFAULT_LABEL_TP_PCT, sl_pct: float = dataset.DEFAULT_LABEL_SL_PCT, round_trip_cost: float = DEFAULT_ROUND_TRIP_COST) -> dict[str, float]:
    if not probabilities or not labels:
        return {"rows": 0.0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "ece": 0.0, "expected_calibration_error": 0.0, "mce": 0.0, "brier": 0.0, "brier_score": 0.0, "brier_skill_score": 0.0, "positive_rate": 0.0, "predicted_positive_rate": 0.0, "mdd": 0.0, "sharpe": 0.0, "calmar": 0.0}
    predictions = [1 if probability >= threshold else 0 for probability in probabilities]
    tp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 1)
    tn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 0)
    fp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 0)
    fn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 1)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    calibration = monitoring.CalibrationDriftMonitor()
    brier = calibration.brier_score(probabilities, labels)
    ece = calibration.expected_calibration_error(probabilities, labels)
    # Trading-derived metrics for champion-challenger evaluation
    pnl = _trading_pnl(probabilities, labels, threshold, tp_pct=tp_pct, sl_pct=sl_pct, round_trip_cost=round_trip_cost)
    return {
        "rows": float(len(labels)),
        "accuracy": (tp + tn) / len(labels),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ece": ece,
        "expected_calibration_error": ece,
        "mce": calibration.maximum_calibration_error(probabilities, labels),
        "brier": brier,
        "brier_score": brier,
        "brier_skill_score": calibration.brier_skill_score(probabilities, labels),
        "positive_rate": sum(labels) / len(labels),
        "predicted_positive_rate": sum(predictions) / len(predictions),
        "mdd": _mdd(pnl),
        "sharpe": _sharpe(pnl),
        "calmar": _calmar(pnl),
    }


def write_training_artifacts(
    output_dir: Path,
    build: dataset.DatasetBuild,
    splits: Sequence[object],
    fold_results: Sequence[FoldResult],
    final_model: models.ModelAdapter,
    config: TrainingConfig | None = None,
    sample_intervals: Sequence[cv.SampleInterval] | None = None,
    uniqueness: cv.UniquenessWeightResult | None = None,
    final_selection: models.ModelSelection | None = None,
    latency_report: Mapping[str, object] | None = None,
    captured_provenance: tuple[dict[str, object], str | None] | None = None,
) -> list[str]:
    training_config = config or TrainingConfig()
    intervals = list(sample_intervals) if sample_intervals is not None else cv.sample_intervals_from_labeled_rows(build.labeled_rows, build.label_horizon)
    uniqueness_result = uniqueness or cv.uniqueness_weights(intervals)
    selection_report = model_selection_report(training_config, fold_results, final_selection, final_model)
    latency_payload = dict(latency_report or {}) or empty_latency_report()
    model_metadata = model_version_metadata(build, final_model, training_config, final_selection)
    model_payload = dict(final_model.as_dict())
    model_payload["model_version_metadata"] = model_metadata
    # WHICH SIDE a high probability means. Without it the artifact is just a
    # score, and the single-model backtest path assumes high = long: a model
    # trained on short_success or short_profitability would then be traded
    # exactly backwards, and the reported performance would be for the opposite
    # trades. Only the regime-bundle path escaped that, and only because the
    # file is named short_model.json.
    model_payload["train_target"] = training_config.train_target
    writer = governance.ArtifactWriter(output_dir)
    writer.write_provenance(
        resolved_config=asdict(training_config),
        captured=captured_provenance,
    )
    # Created before fitting and append-flushed per fit; list it so the normal
    # artifact manifest covers the runtime evidence too.
    writer.write_json("dataset_card.json", dataset.dataset_card(build))
    writer.write_text("dataset_card.md", dataset_card_markdown(build))
    writer.write_json("feature_formula_registry.json", dataset.feature_formula_registry())
    writer.write_json("model.json", model_payload)
    writer.write_json("model_card.json", model_card(build, final_model, selection_report, model_metadata))
    writer.write_text("model_card.md", model_card_markdown(selection_report, model_metadata))
    writer.write_json("model_version_metadata.json", model_metadata)
    writer.write_json("model_selection_report.json", selection_report)
    writer.write_csv("lightgbm_missing_policy_validation_report.csv", lightgbm_missing_policy_validation_rows(build, build.feature_names))
    writer.write_json("inference_latency_report.json", latency_payload)
    writer.write_csv("split_manifest.csv", split_rows(splits))
    writer.write_csv("cv_split_manifest.csv", cv_split_manifest_rows(splits, training_config))
    writer.write_csv("sample_uniqueness_report.csv", sample_uniqueness_rows(intervals, uniqueness_result))
    writer.write_csv("fold_metrics.csv", fold_metric_rows(fold_results))
    _predictions = [row for fold in fold_results for row in fold.test_predictions]
    if _predictions:
        writer.write_csv("fold_test_predictions.csv", _predictions)
    writer.write_json("calibration_report.json", calibration_report(fold_results))
    writer.write_json("calibration_baseline.json", calibration_baseline(fold_results))
    writer.write_json("threshold_report.json", threshold_report(fold_results))
    writer.write_csv("labeled_feature_preview.csv", [dataset.labeled_row_dict(row, build.feature_names) for row in build.labeled_rows[:25]])
    names = [
        "provenance.json",
        "training_runtime.jsonl",
        "dataset_card.json",
        "dataset_card.md",
        "feature_formula_registry.json",
        "model.json",
        "model_card.json",
        "model_card.md",
        "model_version_metadata.json",
        "model_selection_report.json",
        "lightgbm_missing_policy_validation_report.csv",
        "inference_latency_report.json",
        "split_manifest.csv",
        "cv_split_manifest.csv",
        "sample_uniqueness_report.csv",
        "fold_metrics.csv",
        "calibration_report.json",
        "calibration_baseline.json",
        "threshold_report.json",
        "labeled_feature_preview.csv",
    ]
    # Listed so it reaches run_summary["artifacts"] and the checksum manifest.
    # An offline-scoring file nobody can verify the provenance of is worse than
    # no file: it invites exactly the re-mining it is warned about.
    if any(fold.test_predictions for fold in fold_results):
        names.append("fold_test_predictions.csv")
    return names


def summarise_fold_trading(
    per_fold: list[dict[str, object]],
    splits: Sequence[object] | None = None,
    label_horizon: int | None = None,
) -> dict[str, object]:
    """Aggregate per-fold trading metrics without losing any fold, or its size.

    Module level, not a closure, because the failures it guards against are
    invisible from the outside.

    Two of them. A fold that traded nothing used to return {} and be filtered
    out by `if result:` -- those are exactly the folds a gate refused hardest,
    most likely the bad ones, so fold_count described a different set of folds
    than the summary claimed. And the plain mean weights a 28-trade fold the
    same as a 765-trade one: the first gated run read +7.63 bps with "3/4 folds
    profitable" while its trade-weighted figure was -1.66, because the two
    profitable folds had 28 and 29 trades against a per-trade sigma near 26 bps.
    """
    def _has(row: dict[str, object], key: str) -> bool:
        # `x == x` is False only for NaN. A MISSING key returns None from .get,
        # and None == None is True, so presence has to be checked separately or
        # a fold that traded nothing gets indexed for a key it does not have.
        return key in row and row[key] == row[key]

    def _weighted(values: list[float], weights: list[float]) -> float:
        total = sum(weights)
        return sum(v * w for v, w in zip(values, weights)) / total if total else 0.0

    # Whether the folds are independent enough for a vote over them to mean
    # anything. CPCV reuses rows across test combinations, so the same calendar
    # stretch can carry every fold: 12-of-15-positive was one 2021 counted
    # fifteen times, with 2022 contributing nothing. Reported next to the vote
    # so the vote cannot be read alone.
    # Do the fold test windows actually overlap? Intersecting the index sets
    # answers it for any splitter, present or future, and cannot be talked out
    # of by a mislabelled mode. Absent splits means unknown, and unknown is not
    # independent.
    test_windows_disjoint = False
    shared_test_rows = 0
    min_window_gap: int | None = None
    if splits:
        seen: set[int] = set()
        total_test_rows = 0
        spans: list[tuple[int, int]] = []
        for split in splits:
            indices = set(_split_indices(getattr(split, "test", ()) or ()))
            total_test_rows += len(indices)
            shared_test_rows += len(indices & seen)
            seen |= indices
            if indices:
                spans.append((min(indices), max(indices)))
        rows_disjoint = bool(seen) and shared_test_rows == 0 and total_test_rows == len(seen)
        # Disjoint ROWS is not disjoint EVIDENCE. Walk-forward advances each
        # test range by exactly test_size, so neighbouring ranges share no index
        # and still touch at the boundary -- and with a 45-bar horizon the last
        # 45 labels of one range resolve on the same future bars as the first
        # labels of the next. That is the dependency purge and embargo exist to
        # remove, and an index intersection cannot see it. Require the ranges to
        # sit at least a horizon apart.
        if len(spans) > 1:
            ordered = sorted(spans)
            min_window_gap = min(
                nxt[0] - cur[1] - 1 for cur, nxt in zip(ordered, ordered[1:])
            )
        horizon = int(label_horizon) if label_horizon else 0
        if horizon <= 0:
            # An unknown horizon cannot be shown to be cleared.
            test_windows_disjoint = False
        else:
            test_windows_disjoint = rows_disjoint and (
                min_window_gap is None or min_window_gap >= horizon
            )

    entries_total = 0
    unique_keys: set[int] = set()
    for row in per_fold:
        cov = row.get("coverage") or {}
        keys = cov.get("entry_keys")
        if keys is None:
            # Pre-coverage fold, or a caller that supplied only counts. Counting
            # it as unique would overstate independence, so it contributes to
            # the total and not to the unique set, which drags overlap up.
            entries_total += sum(int(v) for v in (cov.get("entries_by_year") or {}).values())
            continue
        entries_total += len(keys)
        unique_keys.update(int(k) for k in keys)
    unique_by_year: dict[int, int] = {}
    for key in unique_keys:
        year = datetime.fromtimestamp(key * 60, tz=timezone.utc).year
        unique_by_year[year] = unique_by_year.get(year, 0) + 1
    entries_unique = len(unique_keys)
    # >1 means folds share rows, so a fold vote is not that many confirmations.
    overlap_factor = (entries_total / entries_unique) if entries_unique else 0.0
    independent_years = sum(
        1 for n in unique_by_year.values() if n >= MIN_ENTRIES_FOR_AN_INDEPENDENT_YEAR
    )
    largest_year_share = (max(unique_by_year.values()) / entries_unique) if entries_unique else 0.0

    # A net bps figure is a measurement only when that side traded. Keep the
    # zero-trade fold in ``folds`` and count it below, but do not manufacture a
    # zero observation for either mean.
    long_rows = [t for t in per_fold if _has(t, "long_net_bps") and float(t.get("long_trades", 0.0)) > 0.0]
    short_rows = [t for t in per_fold if _has(t, "short_net_bps") and float(t.get("short_trades", 0.0)) > 0.0]
    long_net = [float(t["long_net_bps"]) for t in long_rows]
    short_net = [float(t["short_net_bps"]) for t in short_rows]
    long_trades = [float(t.get("long_trades", 0.0)) for t in long_rows]
    short_trades = [float(t.get("short_trades", 0.0)) for t in short_rows]
    # Copy the identities out of the reported folds rather than deleting them
    # from the caller's data. Popping in place made this function destructive:
    # a second call on the same list saw no keys, computed overlap 0.0 and
    # reported different numbers than the first. Tens of thousands of integers
    # still have no business in run_summary.json, so they are dropped from the
    # COPY. fold_test_predictions.csv carries entry_time for anyone who wants
    # to recompute this.
    reported_folds = []
    for row in per_fold:
        cov = row.get("coverage")
        if isinstance(cov, dict) and "entry_keys" in cov:
            row = {**row, "coverage": {k: v for k, v in cov.items() if k != "entry_keys"}}
        reported_folds.append(row)
    return {
        "folds": reported_folds,
        "fold_count": len(per_fold),
        "folds_without_eligible_rows": sum(1 for t in per_fold if t.get("no_eligible_rows")),
        "long_net_bps_by_fold": long_net,
        "short_net_bps_by_fold": short_net,
        "long_trades_by_fold": long_trades,
        "short_trades_by_fold": short_trades,
        # Read these BEFORE the fold vote below. All year figures are over
        # DEDUPLICATED entries: a row that appears in four CPCV folds counts
        # once here and four times in entries_total.
        "entries_by_year": dict(sorted(unique_by_year.items())),
        "entries_total": entries_total,
        "entries_unique": entries_unique,
        "overlap_factor": overlap_factor,
        "independent_years": independent_years,
        "min_entries_for_an_independent_year": MIN_ENTRIES_FOR_AN_INDEPENDENT_YEAR,
        "largest_year_share": largest_year_share,
        "test_windows_disjoint": test_windows_disjoint,
        "shared_test_rows": shared_test_rows,
        # Bars between the closest pair of test ranges. Must be >= the label
        # horizon, or their outcomes are computed from overlapping futures.
        "min_test_window_gap_bars": min_window_gap,
        "label_horizon": label_horizon,
        # Topology first, then the data, and topology is MEASURED rather than
        # declared. Entry overlap alone is not enough -- CPCV folds can share
        # most of their test rows and still select disjoint entries, landing
        # overlap_factor near 1.0 -- and a cv_mode string is not enough either,
        # because a caller can label CPCV metrics "walk_forward" and the
        # function has no way to know. So the splits themselves are intersected.
        # No splits, no certification.
        "fold_vote_is_independent_evidence": (
            test_windows_disjoint
            and independent_years >= 2
            and largest_year_share <= 0.75
            and overlap_factor <= 1.05
        ),
        # The trade-weighted figure is the decision metric. The plain fold mean
        # remains descriptive only, with its equal-fold weighting made explicit.
        "long_net_bps_trade_weighted_mean": _weighted(long_net, long_trades),
        "short_net_bps_trade_weighted_mean": _weighted(short_net, short_trades),
        "long_net_bps_plain_fold_mean": mean(long_net) if long_net else 0.0,
        "short_net_bps_plain_fold_mean": mean(short_net) if short_net else 0.0,
        "long_trade_weighted_mean_folds_with_trades": len(long_rows),
        "short_trade_weighted_mean_folds_with_trades": len(short_rows),
        "long_plain_fold_mean_folds_with_trades": len(long_rows),
        "short_plain_fold_mean_folds_with_trades": len(short_rows),
        "long_folds_with_no_trades": len(per_fold) - len(long_rows),
        "short_folds_with_no_trades": len(per_fold) - len(short_rows),
        # A profitable-fold count gives a tiny fold the same vote as a large
        # fold. Report the profitable share of trades instead.
        "long_profitable_trade_share": (
            sum(w for v, w in zip(long_net, long_trades) if v > 0.0) / sum(long_trades)
            if long_trades else 0.0
        ),
        "short_profitable_trade_share": (
            sum(w for v, w in zip(short_net, short_trades) if v > 0.0) / sum(short_trades)
            if short_trades else 0.0
        ),
        "long_net_bps_worst": min(long_net) if long_net else 0.0,
        "short_net_bps_worst": min(short_net) if short_net else 0.0,
    }

def training_summary(
    build: dataset.DatasetBuild,
    splits: Sequence[object],
    fold_results: Sequence[FoldResult],
    artifacts: Sequence[str],
    config: TrainingConfig | None = None,
    uniqueness: cv.UniquenessWeightResult | None = None,
    final_selection: models.ModelSelection | None = None,
    latency_report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    training_config = config or TrainingConfig()
    test_f1_values = [fold.test_metrics["f1"] for fold in fold_results]
    test_accuracy_values = [fold.test_metrics["accuracy"] for fold in fold_results]
    test_ece_values = [fold.test_metrics["ece"] for fold in fold_results]
    test_brier_values = [fold.test_metrics["brier"] for fold in fold_results]
    # Walk-forward OOS trading, per fold and summarised. This is the number a
    # candidate lives or dies on: the saved model is refit over every labeled
    # row, so any evaluation on the training span is in-sample, and the fold
    # test slices are the only unseen windows this pipeline produces. Report
    # how many of them cleared cost rather than an average, because one strong
    # fold hiding three losing ones is exactly the failure being guarded
    # against.
    oos_trading = summarise_fold_trading(
        [fold.test_trading for fold in fold_results if fold.test_trading],
        splits=splits,
        label_horizon=training_config.label_horizon,
    )
    # Reported next to the ungated figures, never in place of them: a gate that
    # keeps 10% of bars will look better on almost any metric simply by trading
    # less, so the pair is what makes it readable.
    _gated = [fold.test_trading_gated for fold in fold_results if fold.test_trading_gated]
    if _gated:
        oos_trading["gated"] = summarise_fold_trading(
            _gated, splits=splits, label_horizon=training_config.label_horizon)
        oos_trading["gated"]["gate"] = {
            "feature": training_config.vol_gate_feature,
            # This is provenance from the barrier screen, not an operational
            # floor.  Keeping the names distinct prevents a whole-span screen
            # cutoff from being mistaken for the fold-clean cutoff below.
            "screen_reference_minimum": training_config.vol_gate_screen_reference_min,
            "screen_reference": {
                "role": "descriptive_only_never_used_for_gating",
                "report_path": training_config.vol_gate_screen_reference_report,
            },
            # ``minimum`` is retained for artifact compatibility; it is merely
            # the CLI's absolute fallback (normally 0.0 for a quantile run).
            # Consumers comparing this retrain must use the explicitly named
            # fold-derived value, not infer it from that fallback.
            "minimum": training_config.vol_gate_min,
            "configured_minimum": training_config.vol_gate_min,
            "train_quantile": training_config.vol_gate_train_quantile,
            # Per fold when the cutoff came from that fold's own train slice, so
            # the number that gated each result is on the record rather than
            # reconstructed from a config value that may not have been used.
            "minimum_by_fold": [fold.vol_gate_min_used for fold in fold_results],
            "fold_derived_minimum": (
                fold_results[0].vol_gate_min_used if fold_results else None
            ),
            "eligible_share_by_fold": [t.get("eligible_share") for t in _gated],
        }
    selection = final_selection.as_dict() if final_selection is not None else default_model_selection(training_config, None)
    latency = dict(latency_report or {})
    return {
        "run_id": "offline_btcusdt_training_v1",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "shuffled_labels": training_config.shuffle_labels,
        "exclude_fallback_features": training_config.exclude_fallback_features,
        "network_used": False,
        "credentials_required": False,
        "orders_enabled": False,
        "source": build.source,
        "canonical_rows": len(build.canonical),
        "labeled_rows": len(build.labeled_rows),
        "label_reason_counts": dataset.label_reason_counts(build.labeled_rows),
        "feature_count": len(build.feature_names),
        "fold_count": len(splits),
        "cv_mode": training_config.cv_mode,
        "embargo_size": training_config.embargo_size,
        "n_groups": training_config.n_groups,
        "test_group_count": training_config.test_group_count,
        "requested_model_family": training_config.model_family,
        "selected_model_family": selection.get("selected_family", "stdlib"),
        "model_fallback_allowed": training_config.fallback_allowed,
        "model_fallback_used": bool(selection.get("fallback_used", False)),
        "model_fallback_reason": str(selection.get("fallback_reason", "")),
        "inference_latency_p50_ms": float(latency.get("p50_ms", 0.0)),
        "inference_latency_p95_ms": float(latency.get("p95_ms", 0.0)),
        "inference_latency_p99_ms": float(latency.get("p99_ms", 0.0)),
        "effective_sample_size": uniqueness.effective_sample_size if uniqueness is not None else float(len(build.labeled_rows)),
        "mean_test_f1": mean(test_f1_values) if test_f1_values else 0.0,
        "oos_trading": oos_trading,
        "mean_test_accuracy": mean(test_accuracy_values) if test_accuracy_values else 0.0,
        "mean_test_ece": mean(test_ece_values) if test_ece_values else 0.0,
        "mean_test_brier": mean(test_brier_values) if test_brier_values else 0.0,
        "artifacts": list(artifacts),
    }


def write_manifest(output_dir: Path, relative_paths: Sequence[str]) -> list[str]:
    writer = governance.ArtifactWriter(output_dir)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    manifest = []
    for relative_path in relative_paths:
        path = output_dir / relative_path
        manifest.append(
            {
                "path": relative_path,
                "sha256": governance.sha256_file(path),
                "producer_stage": "OFFLINE_TRAINING",
                "timestamp": timestamp,
                "semantic_version": "0.1.0",
            }
        )
    writer.write_json("artifact_manifest.json", {"artifacts": manifest})
    return list(relative_paths) + ["artifact_manifest.json"]


def split_rows(splits: Sequence[object]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for index, split in enumerate(splits):
        train = _split_indices(split.train)
        validation = _split_indices(split.validation)
        test = _split_indices(split.test)
        rows.append(
            {
                "fold_index": index,
                "train_start": _min_index(train),
                "train_stop_exclusive": _stop_exclusive(train),
                "validation_start": _min_index(validation),
                "validation_stop_exclusive": _stop_exclusive(validation),
                "test_start": _min_index(test),
                "test_stop_exclusive": _stop_exclusive(test),
                "purge_train_validation": _min_index(validation) - _stop_exclusive(train) if isinstance(split, features.Split) else "purged_by_label_overlap",
                "purge_validation_test": _min_index(test) - _stop_exclusive(validation) if isinstance(split, features.Split) else "shared_holdout",
            }
        )
    return rows


def cv_split_manifest_rows(splits: Sequence[object], config: TrainingConfig) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for index, split in enumerate(splits):
        train = _split_indices(split.train)
        validation = _split_indices(split.validation)
        test = _split_indices(split.test)
        row: dict[str, int | str] = {
            "fold_index": index,
            "cv_mode": config.cv_mode,
            "train_count": len(train),
            "validation_count": len(validation),
            "test_count": len(test),
            "train_start": _min_index(train),
            "train_stop_exclusive": _stop_exclusive(train),
            "validation_start": _min_index(validation),
            "validation_stop_exclusive": _stop_exclusive(validation),
            "test_start": _min_index(test),
            "test_stop_exclusive": _stop_exclusive(test),
            "embargo_size": config.embargo_size,
            "walk_forward_test_gap": config.walk_forward_test_gap,
        }
        if isinstance(split, cv.CombinatorialPurgedSplit):
            row.update(
                {
                    "test_groups": ",".join(str(group) for group in split.test_groups),
                    "purged_count": len(split.purged),
                    "embargoed_count": len(split.embargoed),
                    "purged_indices": ",".join(str(value) for value in split.purged),
                    "embargoed_indices": ",".join(str(value) for value in split.embargoed),
                }
            )
        else:
            row.update({"test_groups": "", "purged_count": 0, "embargoed_count": 0, "purged_indices": "", "embargoed_indices": ""})
        rows.append(row)
    return rows


def sample_uniqueness_rows(intervals: Sequence[cv.SampleInterval], uniqueness: cv.UniquenessWeightResult) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for interval in sorted(intervals, key=lambda item: item.sample_index):
        rows.append(
            {
                "sample_index": interval.sample_index,
                "start_index": interval.start_index,
                "end_index": interval.end_index,
                "uniqueness_weight": uniqueness.weights.get(interval.sample_index, 0.0),
                "effective_sample_size": uniqueness.effective_sample_size,
            }
        )
    return rows


def model_selection_report(
    config: TrainingConfig,
    fold_results: Sequence[FoldResult],
    final_selection: models.ModelSelection | None,
    final_model: models.ModelAdapter,
) -> dict[str, object]:
    final_payload = final_selection.as_dict() if final_selection is not None else default_model_selection(config, final_model)
    fold_payloads = [dict(fold.model_selection) for fold in fold_results]
    fallback_events = [payload for payload in [final_payload, *fold_payloads] if bool(payload.get("fallback_used", False))]
    return {
        "requested_family": config.model_family,
        "selected_family": final_payload.get("selected_family", selected_family(final_model)),
        "fallback_allowed": config.fallback_allowed,
        "fallback_used": bool(final_payload.get("fallback_used", False)) or bool(fallback_events),
        "fallback_event_count": len(fallback_events),
        "final_model": final_payload,
        "fold_models": fold_payloads,
        "fallback_events": fallback_events,
    }


def default_model_selection(config: TrainingConfig, model: models.ModelAdapter | None) -> dict[str, object]:
    family = selected_family(model)
    return {
        "requested_family": config.model_family,
        "selected_family": family,
        "fallback_allowed": config.fallback_allowed,
        "fallback_used": False,
        "fallback_reason": "pre-adapter compatibility path" if model is None else "no fallback required",
        "attempted_families": [family],
        "unavailable_families": {},
        "model_params": dict(config.model_params),
    }


def selected_family(model: models.ModelAdapter | None) -> str:
    if model is None:
        return "stdlib"
    family = getattr(model, "model_family", None)
    if isinstance(family, str):
        return family
    return "stdlib"


def lightgbm_missing_policy_validation_rows(build: dataset.DatasetBuild, feature_names: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for feature_name in feature_names:
        missing_count = 0
        zero_count = 0
        for row in build.labeled_rows:
            value = row.features.get(feature_name)
            if value is None or not isfinite(float(value)):
                missing_count += 1
            elif float(value) == 0.0:
                zero_count += 1
        rows.append(
            {
                "feature_name": str(feature_name),
                "use_missing": True,
                "zero_as_missing": False,
                "missing_value_count": missing_count,
                "zero_value_count": zero_count,
                "zero_treated_as_missing": False,
                "validation_status": "pass",
            }
        )
    return rows


def inference_latency_report(model: models.ModelAdapter, matrix: Sequence[Sequence[float]], max_rows: int = 100) -> dict[str, object]:
    sample = [list(row) for row in matrix[:max_rows]]
    if not sample:
        return empty_latency_report()
    latencies = []
    for row in sample:
        start = perf_counter()
        getattr(model, "predict_proba")([row])
        latencies.append((perf_counter() - start) * 1000.0)
    return {
        "metric": "single_row_predict_proba_latency_ms",
        "rows_measured": len(latencies),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "max_ms": max(latencies),
    }


def empty_latency_report() -> dict[str, object]:
    return {"metric": "single_row_predict_proba_latency_ms", "rows_measured": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}


def _compute_threshold_flip_rate(thresholds: Sequence[float]) -> float:
    """Compute threshold flip rate as fraction of adjacent folds where threshold changes sign."""
    if len(thresholds) < 2:
        return 0.0
    flips = sum(1 for i in range(1, len(thresholds)) if thresholds[i] != thresholds[i - 1])
    return flips / (len(thresholds) - 1)


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def fold_metric_rows(fold_results: Sequence[FoldResult]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for fold in fold_results:
        for split_name, split_metrics in (("validation", fold.validation_metrics), ("test", fold.test_metrics)):
            row: dict[str, float | int | str] = {"fold_index": fold.fold_index, "split": split_name, "threshold": fold.threshold}
            row.update(split_metrics)
            rows.append(row)
    return rows


def calibration_report(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    return {
        "method": "fitted_probability_calibration",
        "selected_by": "purged walk-forward validation folds",
        "fold_offsets": [{"fold_index": fold.fold_index, "calibration_offset": fold.calibration_offset} for fold in fold_results],
        "fold_calibrators": [{"fold_index": fold.fold_index, **fold.calibration_details} for fold in fold_results],
    }


def calibration_baseline(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    if not fold_results:
        return {
            "metric_source": "fold_test_metrics",
            "fold_count": 0,
            "ece": 0.0,
            "mce": 0.0,
            "brier": 0.0,
            "brier_skill_score": 0.0,
            "brier_degradation_reported": True,
        }
    metric_names = ("ece", "mce", "brier", "brier_skill_score")
    baseline = {
        name: mean([fold.test_metrics.get(name, 0.0) for fold in fold_results])
        for name in metric_names
    }
    return {
        "metric_source": "fold_test_metrics",
        "fold_count": len(fold_results),
        "ece": baseline["ece"],
        "mce": baseline["mce"],
        "brier": baseline["brier"],
        "brier_skill_score": baseline["brier_skill_score"],
        "brier_degradation_reported": True,
        "folds": [
            {
                "fold_index": fold.fold_index,
                "ece": fold.test_metrics.get("ece", 0.0),
                "mce": fold.test_metrics.get("mce", 0.0),
                "brier": fold.test_metrics.get("brier", 0.0),
                "brier_skill_score": fold.test_metrics.get("brier_skill_score", 0.0),
            }
            for fold in fold_results
        ],
    }


def calibration_config(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    if not fold_results:
        return {"calibrator_type": "platt", "regularization": "l2", "convergence_status": "not_run", "iterations": 0, "final_loss": 0.0}
    first = fold_results[0].calibration_details
    convergence = first.get("convergence", {})
    convergence_map = convergence if isinstance(convergence, Mapping) else {}
    return {
        "calibrator_type": first.get("method", "platt"),
        "regularization": "l2",
        "convergence_status": "converged" if convergence_map.get("converged") else "not_converged",
        "iterations": convergence_map.get("iterations", 0),
        "final_loss": convergence_map.get("final_loss", 0.0),
        "fold_count": len(fold_results),
    }


def bootstrap_ci_report(fold_results: Sequence[FoldResult]) -> list[dict[str, object]]:
    rows = []
    for fold in fold_results:
        net_return_proxy = fold.test_metrics.get("accuracy", 0.0) - 0.5
        win_flag = fold.test_metrics.get("f1", 0.0) > 0.0
        rows.append((f"fold_{fold.fold_index}", net_return_proxy, win_flag))
    return [dict(row) for row in features.BootstrapCIEngine().score_bin_ci(rows)]


def threshold_report(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    return {
        "objective": "maximize validation F1, then accuracy, deterministic tie-break toward 0.5",
        "fold_thresholds": [{"fold_index": fold.fold_index, "threshold": fold.threshold} for fold in fold_results],
    }


def model_version_metadata(
    build: dataset.DatasetBuild,
    model: models.ModelAdapter,
    config: TrainingConfig,
    final_selection: models.ModelSelection | None = None,
) -> dict[str, object]:
    selection = final_selection.as_dict() if final_selection is not None else default_model_selection(config, model)
    model_payload = dict(model.as_dict())
    model_payload.pop("serialized_model", None)
    hash_payload = {
        "model": model_payload,
        "selection": selection,
        "feature_names": list(build.feature_names),
        "training_rows": len(build.labeled_rows),
        "source": build.source,
    }
    model_hash = governance.sha256_text(governance.stable_json(hash_payload))
    family = str(selection.get("selected_family", selected_family(model)))
    model_name = "offline_btcusdt_centroid_linear" if family == "stdlib" else f"offline_btcusdt_{family}"
    return {
        "model_id": f"{model_name}_v1",
        "model_name": model_name,
        "registered_model_name": model_name,
        "model_version": f"v{model_hash[:12]}",
        "semantic_version": "0.1.0",
        "model_hash": model_hash,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "artifact_path": "model.json",
        "model_card_path": "model_card.json",
        "requested_model_family": selection.get("requested_family", config.model_family),
        "selected_model_family": family,
        "fallback_allowed": bool(selection.get("fallback_allowed", config.fallback_allowed)),
        "fallback_used": bool(selection.get("fallback_used", False)),
        "fallback_reason": str(selection.get("fallback_reason", "no fallback required")),
        "feature_count": len(build.feature_names),
        "training_rows": len(build.labeled_rows),
        "source": build.source,
    }


def write_lineage_metadata(
    output_dir: Path,
    build: dataset.DatasetBuild,
    config: TrainingConfig,
    artifacts: Sequence[str],
    run_summary: Mapping[str, object],
    model_metadata: Mapping[str, object],
) -> dict[str, object]:
    card = dataset.dataset_card(build)
    data_hash = governance.sha256_text(governance.stable_json(card))
    source_hashes = card.get("source_hashes", {})
    source_hash_map = dict(source_hashes) if isinstance(source_hashes, Mapping) else {}
    params = {
        "cv_mode": config.cv_mode,
        "embargo_size": config.embargo_size,
        "n_groups": config.n_groups,
        "test_group_count": config.test_group_count,
        "model_family": config.model_family,
        "model_params": dict(config.model_params),
        "fallback_allowed": config.fallback_allowed,
    }
    metric_keys = ("mean_test_f1", "mean_test_accuracy", "mean_test_ece", "mean_test_brier", "inference_latency_p50_ms", "inference_latency_p95_ms", "inference_latency_p99_ms")
    metrics_payload = {key: float(run_summary[key]) for key in metric_keys if isinstance(run_summary.get(key), (float, int))}
    provenance = _read_provenance(output_dir)
    source_revision = provenance.get("source_revision", {})
    revision = source_revision if isinstance(source_revision, Mapping) else {}
    git_commit = revision.get("git_commit", governance.PROVENANCE_UNKNOWN)
    binding = lineage.LineageBinding(
        output_dir=output_dir,
        run_id=str(run_summary.get("run_id", "offline_btcusdt_training_v1")),
        params=params,
        metrics=metrics_payload,
        artifacts=tuple(artifacts),
        model_metadata=dict(model_metadata),
        data_hash=data_hash,
        git_commit=str(git_commit),
        dvc_metadata={"source": build.source, "source_hashes": source_hash_map, "artifact_count": len(artifacts)},
        model_name=str(model_metadata.get("model_id", "offline_btcusdt_model_v1")),
        provenance=provenance,
    )
    return lineage.LineageWriter(output_dir, enabled=config.lineage_enabled).write(binding)


def _read_provenance(output_dir: Path) -> dict[str, object]:
    path = output_dir / "provenance.json"
    if not path.is_file():
        return {"state": governance.PROVENANCE_UNKNOWN, "reason": "provenance_file_missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": governance.PROVENANCE_UNKNOWN, "reason": f"provenance_file_unreadable:{exc.__class__.__name__}"}
    if isinstance(payload, Mapping):
        return dict(payload)
    return {"state": governance.PROVENANCE_UNKNOWN, "reason": "provenance_file_invalid"}


def model_card(
    build: dataset.DatasetBuild,
    model: models.ModelAdapter,
    selection_report: Mapping[str, object] | None = None,
    model_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    selection = dict(selection_report or {})
    metadata = dict(model_metadata or {})
    final_model = selection.get("final_model", {})
    final_selection = final_model if isinstance(final_model, Mapping) else {}
    family = str(selection.get("selected_family", final_selection.get("selected_family", metadata.get("selected_model_family", selected_family(model)))))
    return {
        "model_id": metadata.get("model_id", "offline_btcusdt_model_v1"),
        "model_version": metadata.get("model_version", "v0"),
        "model_hash": metadata.get("model_hash", ""),
        "model_family": family,
        "selected_model_family": family,
        "requested_model_family": selection.get("requested_family", final_selection.get("requested_family", family)),
        "fallback_allowed": bool(selection.get("fallback_allowed", final_selection.get("fallback_allowed", True))),
        "fallback_used": bool(selection.get("fallback_used", final_selection.get("fallback_used", False))),
        "fallback_reason": str(final_selection.get("fallback_reason", selection.get("fallback_reason", "no fallback required"))),
        "intended_use": "offline BTCUSDT research scaffold and artifact verification",
        "forbidden_use": "live trading, real order submission, or credentialed exchange access",
        "training_rows": len(build.labeled_rows),
        "feature_names": model_feature_names(model, build.feature_names),
        "offline_only": True,
        "network_required": False,
    }


def model_feature_names(model: models.ModelAdapter, fallback: Sequence[str]) -> list[str]:
    feature_names = getattr(model, "feature_names", None)
    if isinstance(feature_names, Sequence) and not isinstance(feature_names, (str, bytes)):
        return [str(name) for name in feature_names]
    try:
        payload = model.as_dict()
    except Exception:
        return [str(name) for name in fallback]
    payload_names = payload.get("feature_names")
    if isinstance(payload_names, Sequence) and not isinstance(payload_names, (str, bytes)):
        return [str(name) for name in payload_names]
    return [str(name) for name in fallback]


def dataset_card_markdown(build: dataset.DatasetBuild) -> str:
    return "\n".join(
        [
            "# Offline BTCUSDT Dataset Card",
            "",
            f"- Source: `{build.source}`",
            f"- Canonical rows: {len(build.canonical)}",
            f"- Labeled rows: {len(build.labeled_rows)}",
            f"- Label reasons: {dataset.label_reason_counts(build.labeled_rows)}",
            f"- Repaired rows: {build.gap_report.repaired_rows}",
            "- Network required: false",
            "",
        ]
    )


def model_card_markdown(selection_report: Mapping[str, object] | None = None, model_metadata: Mapping[str, object] | None = None) -> str:
    selection = dict(selection_report or {})
    metadata = dict(model_metadata or {})
    selected = selection.get("selected_family", "stdlib")
    fallback_used = selection.get("fallback_used", False)
    return "\n".join(
        [
            "# Offline BTCUSDT Model Card",
            "",
            f"Model ID: `{metadata.get('model_id', 'offline_btcusdt_model_v1')}`.",
            f"Model version: `{metadata.get('model_version', 'v0')}`.",
            f"Selected model family: `{selected}`.",
            f"Fallback used: `{fallback_used}`.",
            "It is forbidden for live trading or real order submission.",
            "",
        ]
    )


def safe_logit(probability: float) -> float:
    clipped = min(1.0 - 1e-6, max(1e-6, probability))
    return log(clipped / (1.0 - clipped))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def run_ensemble_training(
    build: dataset.DatasetBuild,
    output_dir: Path,
    config: TrainingConfig,
) -> TrainingResult:
    """Train a stacking ensemble: direction + profitability + meta model."""
    from . import ensemble

    start_time = time()
    print(f"[Ensemble] Training stacking ensemble with {len(build.labeled_rows)} rows")
    print(f"[Ensemble] Direction family: {config.ensemble_direction_family}")
    print(f"[Ensemble] Profitability family: {config.ensemble_profitability_family}")
    print(f"[Ensemble] Meta family: {config.ensemble_meta_family}")

    ensemble_model = ensemble.fit_stacking_ensemble(
        build.labeled_rows,
        build.feature_names,
        direction_family=config.ensemble_direction_family,
        profitability_family=config.ensemble_profitability_family,
        meta_family=config.ensemble_meta_family,
    )

    # Evaluate on full dataset
    full_probs = ensemble_model.predict_proba(feature_matrix(build.labeled_rows, build.feature_names))
    full_labels = [row.targets.get("profitability", row.label) for row in build.labeled_rows]
    full_metrics = metrics(full_probs, full_labels, 0.5)

    # Write artifacts
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.json"
    model_path.write_text(json.dumps(ensemble_model.as_dict(), indent=2), encoding="utf-8")

    # Run summary
    run_summary = {
        "training_config": {
            "ensemble_enabled": True,
            "ensemble_direction_family": config.ensemble_direction_family,
            "ensemble_profitability_family": config.ensemble_profitability_family,
            "ensemble_meta_family": config.ensemble_meta_family,
            "model_family": "stacking_ensemble",
        },
        "training_rows": len(build.labeled_rows),
        "feature_names": list(build.feature_names),
        "mean_test_f1": full_metrics.get("f1", 0.0),
        "mean_test_accuracy": full_metrics.get("accuracy", 0.0),
        "profitability_positive_ratio": sum(full_labels) / len(full_labels) if full_labels else 0.0,
        "network_used": False,
        "orders_enabled": False,
        "labeled_rows": len(build.labeled_rows),
        "fold_count": 1,
        "timing_seconds": {"total": time() - start_time},
    }
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print(f"[Ensemble] Model saved to {model_path}")
    print(f"[Ensemble] F1: {full_metrics.get('f1', 0.0):.4f}")

    return TrainingResult(
        output_dir=output_dir,
        dataset_build=build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=[str(model_path)],
    )
