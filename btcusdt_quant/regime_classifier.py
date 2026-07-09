"""Leakage-safe regime probability classifier (Method B, stage 2).

Produces per-bar p_up/p_range/p_down probabilities that the entry (long/short)
models can use as FEATURES, instead of a hard regime bucket. The critical
constraint: if a row's own regime label was seen by the classifier that
predicts it, the entry model would learn from a probability the classifier
partly "memorized" rather than genuinely inferred -- severe overfitting that
would show up as a gap between training-period and true out-of-sample
(e.g. 2025) performance.

This module solves that with STRICT WALK-FORWARD out-of-fold (OOF) prediction:
split the training period into K chronological folds; each fold's rows
(except the first, which has no prior data) are predicted by a classifier
trained ONLY on chronologically EARLIER folds, with a purge gap immediately
before the fold boundary so no training row's label-formation window overlaps
a predicted row. No fold's classifier ever sees a future row -- training data
for fold i is strictly a subset of rows before fold i's start. This is
stricter than "purged K-fold" (Lopez de Prado's K-fold variant, which lets a
fold's training set include chronologically LATER folds too): here, nothing
later is ever used, matching how a live classifier could actually have been
trained at that point in time.

The unavoidable cost of strict walk-forward: the FIRST fold has no prior data
at all, so it gets no OOF prediction (excluded, not fabricated) -- those rows'
F18 regime-probability features degrade to 0.0, the same "not enough history
yet" convention used elsewhere in this codebase (e.g. weekly-MA warmup,
multi-timeframe features before the first closed bar).

The FINAL deployed classifier (for live use) is trained once on the complete
dataset, same as everything else in this project.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Mapping, Sequence

REGIME_CLASSES: tuple[str, ...] = ("down", "range", "up")


@dataclass(frozen=True)
class Fold:
    """One purged K-fold split: predict_indices get OOF predictions from a
    classifier trained on train_indices (everything else, minus the purge
    gap around this fold's boundary)."""

    fold_id: int
    train_indices: list[int]
    predict_indices: list[int]


def build_walk_forward_folds(n_rows: int, n_folds: int, purge_gap: int) -> list[Fold]:
    """Chronologically contiguous K folds, each trained ONLY on earlier folds.

    Row i belongs to fold i // fold_size (roughly equal-sized contiguous
    chronological blocks). For fold f (f >= 1), train_indices is every row in
    folds 0..f-1 EXCEPT the last `purge_gap` rows immediately before fold f's
    start (purged so a training row whose label-formation window overlaps
    fold f's boundary can't leak information about it). Fold 0 is NOT
    returned: it has no prior data to train on, so it cannot get a leakage-
    safe OOF prediction under strict walk-forward -- callers must treat those
    rows as "no OOF available" (see generate_oof_regime_probabilities), the
    same warmup convention used elsewhere in this codebase rather than
    fabricating a prediction from nothing.

    Critically: NO fold's training set ever includes a row from a LATER fold.
    This differs from classic "purged K-fold" (which trains each fold on ALL
    other folds, including future ones) -- that lets a fold's classifier
    implicitly calibrate against the future's distribution, which we avoid
    here entirely to mirror what a live classifier could actually have known
    at each point in time.
    """
    if n_rows <= 0:
        raise ValueError("n_rows must be positive")
    if n_folds < 2:
        raise ValueError("n_folds must be >= 2 (need at least one prior fold to train on)")
    if purge_gap < 0:
        raise ValueError("purge_gap must be non-negative")
    fold_size = max(1, n_rows // n_folds)
    boundaries: list[tuple[int, int]] = []
    start = 0
    for f in range(n_folds):
        end = n_rows if f == n_folds - 1 else min(n_rows, start + fold_size)
        boundaries.append((start, end))
        start = end
        if start >= n_rows:
            break
    folds: list[Fold] = []
    for fold_id, (fstart, fend) in enumerate(boundaries):
        if fstart >= fend:
            continue
        if fold_id == 0:
            continue  # no prior data -- excluded, not fabricated (see docstring)
        predict_indices = list(range(fstart, fend))
        purge_lo = max(0, fstart - purge_gap)
        train_indices = list(range(0, purge_lo))
        folds.append(Fold(fold_id=fold_id, train_indices=train_indices, predict_indices=predict_indices))
    return folds


# A fold classifier is any callable: (train_X, train_y, train_w, predict_X) ->
# list of per-row {class_name: probability} dicts for predict_X, in order.
# This makes the OOF machinery fully testable without CatBoost (inject a
# deterministic dummy) while remaining pluggable with a real multiclass
# CatBoostAdapter in the user's environment.
FoldClassifierFn = Callable[
    [Sequence[Sequence[float]], Sequence[str], Sequence[float] | None, Sequence[Sequence[float]]],
    list[dict[str, float]],
]


def generate_oof_regime_probabilities(
    feature_rows: Sequence[Sequence[float]],
    labels: Sequence[str],
    fit_predict_fn: FoldClassifierFn,
    n_folds: int = 5,
    purge_gap: int = 60,
    sample_weight: Sequence[float] | None = None,
) -> list[dict[str, float]]:
    """Leakage-safe, strictly-causal out-of-fold regime probabilities.

    Returns one {class_name: probability} dict per row, in the original row
    order. Every row from fold 1 onward is predicted by a classifier trained
    ONLY on chronologically earlier rows (never a future row, never its own
    label). Fold 0's rows (no prior data exists to train on) get a neutral
    default {"up": 1/3, "range": 1/3, "down": 1/3} -- explicitly "no signal
    yet", not a fabricated confident prediction; this is the same convention
    other warmup-limited features in this codebase use.
    """
    n = len(feature_rows)
    if len(labels) != n:
        raise ValueError("feature_rows and labels must have the same length")
    neutral = {c: 1.0 / len(REGIME_CLASSES) for c in REGIME_CLASSES}
    folds = build_walk_forward_folds(n, n_folds, purge_gap)
    oof: list[dict[str, float]] = [dict(neutral) for _ in range(n)]
    covered_by_fold = {i for fold in folds for i in fold.predict_indices}
    for fold in folds:
        train_x = [feature_rows[i] for i in fold.train_indices]
        train_y = [labels[i] for i in fold.train_indices]
        train_w = [sample_weight[i] for i in fold.train_indices] if sample_weight is not None else None
        predict_x = [feature_rows[i] for i in fold.predict_indices]
        if len(set(train_y)) < 2 or not predict_x:
            # Degenerate fold (e.g. tiny dataset): fall back to neutral
            # rather than fabricating confidence from nothing.
            preds = [dict(neutral) for _ in predict_x]
        else:
            preds = fit_predict_fn(train_x, train_y, train_w, predict_x)
        for local_idx, row_idx in enumerate(fold.predict_indices):
            oof[row_idx] = preds[local_idx]
    uncovered = n - len(covered_by_fold)
    if uncovered > 0:
        print(f"[regime_classifier] {uncovered} row(s) in fold 0 have no prior data -> neutral (1/3,1/3,1/3) default")
    return oof


def verify_no_fold_leakage(folds: Sequence[Fold]) -> None:
    """Raise if any fold's predict_indices intersect its own train_indices.

    This is the single most important safety check in this module: it proves
    mechanically (not just by code review) that no row's label was available
    to the classifier that predicts it.
    """
    for fold in folds:
        overlap = set(fold.train_indices) & set(fold.predict_indices)
        if overlap:
            raise RuntimeError(f"fold {fold.fold_id}: {len(overlap)} rows leak between train and predict sets")


# ---------------------------------------------------------------------------
# Transition-zone sample weighting
# ---------------------------------------------------------------------------

def transition_zone_sample_weights(
    regime_labels: Sequence[str],
    row_times: Sequence[datetime],
    zone: timedelta = timedelta(days=1),
    downweight: float = 0.1,
) -> list[float]:
    """Downweight rows within `zone` of a hand-labeled regime boundary.

    Manual regime boundaries are approximate -- the market usually weakens or
    strengthens gradually around the labeled changeover date, so forcing the
    classifier to sharply match a hard label right at the boundary teaches it
    a false crispness. Rows within `zone` on EITHER side of a label change get
    weight `downweight` (default 0.1, not 0 -- fully excluding them would
    also discard the (uncertain but real) information that a transition is
    happening); everything else gets weight 1.0.
    """
    n = len(regime_labels)
    if len(row_times) != n:
        raise ValueError("regime_labels and row_times must have the same length")
    weights = [1.0] * n
    change_indices = [i for i in range(1, n) if regime_labels[i] != regime_labels[i - 1]]
    for change_idx in change_indices:
        change_time = row_times[change_idx]
        lo = change_time - zone
        hi = change_time + zone
        # Bounded local scan outward from the change point (transitions are
        # sparse relative to n, so this stays cheap without a full n^2 scan).
        i = change_idx
        while i >= 0 and row_times[i] >= lo:
            weights[i] = min(weights[i], downweight)
            i -= 1
        i = change_idx
        while i < n and row_times[i] <= hi:
            weights[i] = min(weights[i], downweight)
            i += 1
    return weights


# ---------------------------------------------------------------------------
# Smoothing: rolling-mean probabilities + minimum duration + confidence gate
# ---------------------------------------------------------------------------

@dataclass
class SmoothingConfig:
    rolling_window: int = 30  # bars to average probabilities over
    min_duration_bars: int = 60  # a new regime must persist this long before it's accepted
    confidence_threshold: float = 0.45  # below this, keep the previous regime


def smooth_regime_probabilities(
    probabilities: Sequence[Mapping[str, float]],
    config: SmoothingConfig | None = None,
) -> tuple[list[dict[str, float]], list[str]]:
    """Rolling-mean the raw per-bar probabilities, then apply hysteresis.

    Returns (smoothed_probabilities, assigned_regime_sequence). Mirrors and
    generalizes RegimeDetector's existing min_regime_run_bars hysteresis
    (which only gates a hard discrete label) to operate on continuous
    probabilities: a candidate regime switch must (a) have rolling-mean
    confidence >= confidence_threshold and (b) be the argmax for
    min_duration_bars consecutive raw bars before it's accepted; otherwise
    the previous assigned regime is kept.
    """
    cfg = config or SmoothingConfig()
    n = len(probabilities)
    if n == 0:
        return [], []
    smoothed: list[dict[str, float]] = []
    window: list[Mapping[str, float]] = []
    for p in probabilities:
        window.append(p)
        if len(window) > cfg.rolling_window:
            window.pop(0)
        avg = {c: sum(float(w.get(c, 0.0)) for w in window) / len(window) for c in REGIME_CLASSES}
        smoothed.append(avg)

    assigned: list[str] = []
    current_regime: str | None = None
    pending_regime: str | None = None
    pending_run = 0
    for avg in smoothed:
        candidate = max(REGIME_CLASSES, key=lambda c: avg[c])
        candidate_conf = avg[candidate]
        if current_regime is None:
            # Bootstrap: accept the first confident-enough read immediately;
            # otherwise default to "range" (the conservative no-strong-trend
            # assumption) until confidence arrives.
            current_regime = candidate if candidate_conf >= cfg.confidence_threshold else "range"
            pending_regime, pending_run = None, 0
            assigned.append(current_regime)
            continue
        if candidate == current_regime or candidate_conf < cfg.confidence_threshold:
            pending_regime, pending_run = None, 0
            assigned.append(current_regime)
            continue
        # candidate differs from current AND is confident enough -> must
        # persist for min_duration_bars consecutive raw reads before flipping.
        if candidate == pending_regime:
            pending_run += 1
        else:
            pending_regime, pending_run = candidate, 1
        if pending_run >= cfg.min_duration_bars:
            current_regime = candidate
            pending_regime, pending_run = None, 0
        assigned.append(current_regime)
    return smoothed, assigned


# ---------------------------------------------------------------------------
# Evaluation: macro F1, confusion matrix, up<->down vs range asymmetry
# ---------------------------------------------------------------------------

@dataclass
class RegimeClassifierEvaluation:
    macro_f1: float
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    confusion_matrix: dict[str, dict[str, int]]  # confusion_matrix[true][predicted] = count
    up_down_confusion_count: int  # true=up,pred=down OR true=down,pred=up -- the dangerous kind
    range_confusion_count: int  # true/pred crosses range<->trend but not up<->down directly
    accuracy: float


def evaluate_regime_classifier(true_labels: Sequence[str], predicted_labels: Sequence[str]) -> RegimeClassifierEvaluation:
    """Macro F1 + confusion matrix + the up<->down vs range asymmetry check.

    up<->down confusion is flagged separately because it is the most
    dangerous error (a model that thinks it's in an uptrend when the market
    is actually falling will route to the wrong side entirely); range<->trend
    confusion is comparatively benign (it just misses/over-restricts a
    direction rather than actively pointing the wrong way).
    """
    n = len(true_labels)
    if len(predicted_labels) != n:
        raise ValueError("true_labels and predicted_labels must have the same length")
    confusion: dict[str, dict[str, int]] = {t: {p: 0 for p in REGIME_CLASSES} for t in REGIME_CLASSES}
    for t, p in zip(true_labels, predicted_labels):
        if t in confusion and p in confusion[t]:
            confusion[t][p] += 1
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1_scores: list[float] = []
    for c in REGIME_CLASSES:
        tp = confusion[c][c]
        fp = sum(confusion[t][c] for t in REGIME_CLASSES if t != c)
        fn = sum(confusion[c][p] for p in REGIME_CLASSES if p != c)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision[c] = prec
        recall[c] = rec
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_scores.append(f1)
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    up_down = confusion["up"]["down"] + confusion["down"]["up"]
    range_confusion = (
        confusion["up"]["range"] + confusion["range"]["up"]
        + confusion["down"]["range"] + confusion["range"]["down"]
    )
    correct = sum(confusion[c][c] for c in REGIME_CLASSES)
    accuracy = correct / n if n > 0 else 0.0
    return RegimeClassifierEvaluation(
        macro_f1=macro_f1,
        per_class_precision=precision,
        per_class_recall=recall,
        confusion_matrix=confusion,
        up_down_confusion_count=up_down,
        range_confusion_count=range_confusion,
        accuracy=accuracy,
    )


# ---------------------------------------------------------------------------
# Persistable multiclass classifier (for routing, not just entry-model
# features) -- see module-level note in cli.py's run_train_regime_classifier
# for why this exists: backtest is offline batch inference over history (no
# "live serving" needed at all), and live is just "load this file, call
# predict_proba once per bar with the current causal F17 features" -- exactly
# how the long/short entry models are already loaded and called. The
# project's existing CatBoostAdapter can't be reused as-is: its
# predict_proba assumes binary classification (returns only the positive
# class's probability), which is wrong for a 3-class up/range/down model.
# ---------------------------------------------------------------------------

class RegimeClassifierModel:
    """A trained multiclass CatBoost model, persistable via .cbm (same format
    CatBoostAdapter uses for the entry models), returning {class: probability}
    dicts rather than a single positive-class probability."""

    def __init__(self, feature_names: Sequence[str], model: object | None = None) -> None:
        self.feature_names = tuple(feature_names)
        self.model = model

    def predict_proba(self, feature_rows: Sequence[Sequence[float]]) -> list[dict[str, float]]:
        if self.model is None:
            raise RuntimeError("RegimeClassifierModel must be fitted/loaded before predict_proba")
        raw = self.model.predict_proba(list(feature_rows))
        # Column order follows model.classes_ (the actual labels seen during
        # fit), not a fixed REGIME_CLASSES assumption -- see
        # _catboost_multiclass_fold_classifier's docstring for why a fixed
        # enumerate(row) assumption silently misaligns columns when a class
        # was underrepresented or missing during fit.
        label_to_int = {c: i for i, c in enumerate(REGIME_CLASSES)}
        int_to_label = {i: c for c, i in label_to_int.items()}
        seen_classes = list(getattr(self.model, "classes_", range(len(REGIME_CLASSES))))
        column_labels = [int_to_label[int(cls)] for cls in seen_classes]
        out: list[dict[str, float]] = []
        for row in raw:
            values = list(row.tolist()) if hasattr(row, "tolist") else list(row)
            row_probs = {c: 0.0 for c in REGIME_CLASSES}
            for col_label, v in zip(column_labels, values):
                row_probs[col_label] = float(v)
            out.append(row_probs)
        return out

    def save(self, path: str) -> None:
        if self.model is None:
            raise RuntimeError("cannot save an unfitted RegimeClassifierModel")
        self.model.save_model(path, format="cbm")

    @classmethod
    def load(cls, path: str, feature_names: Sequence[str]) -> "RegimeClassifierModel":
        try:
            import catboost
        except ImportError as exc:
            raise RuntimeError("loading a RegimeClassifierModel requires catboost") from exc
        model = catboost.CatBoostClassifier()
        model.load_model(path)
        return cls(feature_names=feature_names, model=model)


def route_regime_causal(
    feature_rows: Sequence[Sequence[float]],
    classifier: RegimeClassifierModel,
    smoothing_config: "SmoothingConfig | None" = None,
) -> tuple[list[dict[str, float]], list[str]]:
    """Single source of truth for regime routing: run the SAVED classifier
    over a causal feature series (training-bucket assignment, backtest, and
    live all call this) and apply the same smoothing/hysteresis.

    Returns (raw_probabilities, assigned_regimes). Consistency matters more
    than any single step here: whatever this function outputs for a given
    F17 feature vector must be identical whether it's called during training
    (to decide which regime's model a row's data contributes to) or at
    backtest/live time (to decide which regime's model to consult) -- a
    mismatch between the two would be a train/serve skew bug.
    """
    raw_probs = classifier.predict_proba(feature_rows)
    _, assigned = smooth_regime_probabilities(raw_probs, smoothing_config)
    return raw_probs, assigned
