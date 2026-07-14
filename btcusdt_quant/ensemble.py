"""Stacking ensemble model adapter."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from . import data, dataset, models, training


@dataclass(frozen=True)
class StackingEnsembleAdapter:
    """Stacking ensemble: direction model + profitability model + meta model."""

    feature_names: tuple[str, ...]
    direction_model: models.ModelAdapter
    profitability_model: models.ModelAdapter
    meta_model_family: str
    meta_coefs: list[float]
    meta_intercept: float
    meta_adapter: models.ModelAdapter | None = None

    @property
    def model_family(self) -> str:
        return "stacking_ensemble"

    def fit(
        self,
        feature_matrix: models.FeatureMatrix,
        labels: Sequence[int],
        sample_weight: Sequence[float] | None = None,
    ) -> "StackingEnsembleAdapter":
        raise RuntimeError("StackingEnsembleAdapter must be fitted via fit_stacking_ensemble(), not .fit()")

    def predict_proba(self, feature_matrix: models.FeatureMatrix) -> list[float]:
        result: list[float] = []
        for row in feature_matrix:
            features = dict(zip(self.feature_names, row))
            result.append(self.probability(features))
        return result

    def probability(self, features: Mapping[str, float]) -> float:
        p_direction = float(self.direction_model.probability(features))
        p_profitability = float(self.profitability_model.probability(features))
        if self.meta_adapter is not None:
            meta_features = {"direction_probability": p_direction, "profitability_probability": p_profitability}
            return float(self.meta_adapter.probability(meta_features))
        meta_input = np.array([p_direction, p_profitability])
        logit = float(np.dot(meta_input, self.meta_coefs) + self.meta_intercept)
        prob = 1.0 / (1.0 + np.exp(-logit))
        return float(np.clip(prob, 0.0, 1.0))

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "model_family": self.model_family,
            "feature_names": list(self.feature_names),
            "meta_model_family": self.meta_model_family,
            "meta_coefs": self.meta_coefs,
            "meta_intercept": self.meta_intercept,
            "direction_model": self.direction_model.as_dict(),
            "profitability_model": self.profitability_model.as_dict(),
        }
        if self.meta_adapter is not None:
            result["meta_adapter"] = self.meta_adapter.as_dict()
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "StackingEnsembleAdapter":
        feature_names = tuple(str(name) for name in payload.get("feature_names", ()))
        meta_family = str(payload.get("meta_model_family", "sklearn_logistic"))
        meta_coefs = [float(c) for c in payload.get("meta_coefs", [0.5, 0.5])]
        meta_intercept = float(payload.get("meta_intercept", 0.0))
        direction_payload = payload.get("direction_model", {})
        profitability_payload = payload.get("profitability_model", {})
        direction_model = _load_submodel(direction_payload)
        profitability_model = _load_submodel(profitability_payload)
        if direction_model is None or profitability_model is None:
            raise ValueError("stacking ensemble requires direction_model and profitability_model")
        return cls(
            feature_names=feature_names,
            direction_model=direction_model,
            profitability_model=profitability_model,
            meta_model_family=meta_family,
            meta_coefs=meta_coefs,
            meta_intercept=meta_intercept,
        )


def _load_submodel(payload: object) -> models.ModelAdapter | None:
    """Deserialize any family ModelFactory's fallback chain can produce.

    ModelFactory.fit(fallback_allowed=True) may silently substitute another
    family (e.g. pytorch_multitask when catboost is missing), so every family
    that can come OUT of training must be loadable here or ensembles fail at
    reload time despite having trained and serialized successfully. Nested
    ensembles are included so composed models round-trip too.
    """
    if not isinstance(payload, Mapping):
        return None
    model_family = str(payload.get("model_family", ""))
    if model_family == models.CentroidLinearClassifier.model_family_name:
        return models.CentroidLinearClassifier.from_dict(payload)
    if model_family == "lightgbm":
        return models.LightGBMAdapter.from_dict(payload)
    if model_family == "catboost":
        return models.CatBoostAdapter.from_dict(payload)
    if model_family == "pytorch_multitask":
        from . import multitask_nn
        return multitask_nn.MultitaskNNAdapter.from_dict(payload)
    if model_family == "stacking_ensemble":
        return StackingEnsembleAdapter.from_dict(payload)
    if model_family == "multi_horizon_ensemble":
        return MultiHorizonEnsembleAdapter.from_dict(payload)
    return None


def _fit_meta_model(
    X: np.ndarray,
    y: np.ndarray,
    meta_family: str = "catboost",
) -> models.ModelAdapter:
    """Fit a meta model on base model probabilities and return a ModelAdapter."""
    feature_names = ("direction_probability", "profitability_probability")
    if meta_family == "catboost":
        try:
            import catboost as cb
        except ImportError:
            raise RuntimeError("catboost is not installed; install with: pip install catboost")
        clf = cb.CatBoostClassifier(iterations=50, depth=2, verbose=False, random_seed=42)
        clf.fit(X, y)
        return _SklearnMetaModelAdapter(clf, feature_names)

    raise ValueError(f"unsupported meta model family: {meta_family}")


class _SklearnMetaModelAdapter:
    """Wrapper for sklearn meta models to implement ModelAdapter protocol."""

    def __init__(self, sklearn_model: object, feature_names: Sequence[str] = ()) -> None:
        self._model = sklearn_model
        self.feature_names = tuple(feature_names)
        self._coefs = [0.5, 0.5]
        self._intercept = 0.0

    @property
    def model_family(self) -> str:
        return f"sklearn_{type(self._model).__name__.lower()}"

    def fit(self, feature_matrix: Sequence[Sequence[float]], labels: Sequence[int], sample_weight: Sequence[float] | None = None) -> "_SklearnMetaModelAdapter":
        self._model.fit(feature_matrix, labels, sample_weight=sample_weight)
        return self

    def predict_proba(self, feature_matrix: Sequence[Sequence[float]]) -> list[float]:
        result: list[float] = []
        for probs in self._model.predict_proba(feature_matrix):
            result.append(float(probs[1]))
        return result

    def probability(self, values: Mapping[str, float]) -> float:
        row = [float(values.get(name, 0.0)) for name in self.feature_names]
        probs = self.predict_proba([row])
        return probs[0] if probs else 0.5

    def as_dict(self) -> dict[str, object]:
        import pickle, base64
        return {
            "model_family": self.model_family,
            "feature_names": list(self.feature_names),
            "serialized_model": base64.b64encode(pickle.dumps(self._model)).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "_SklearnMetaModelAdapter":
        import pickle, base64
        feature_names = tuple(str(name) for name in payload.get("feature_names", ()))
        serialized = str(payload.get("serialized_model", ""))
        model = pickle.loads(base64.b64decode(serialized.encode("ascii")))
        return cls(model, feature_names)


@dataclass(frozen=True)
class MultiHorizonEnsembleAdapter:
    """Averages entry probabilities from models trained at different label horizons.

    G-Research crypto forecasting 7th-place pattern: the same features labeled
    at several horizons (e.g. 30/60/90 minutes) produce decorrelated errors,
    and averaging their probabilities beat every single-horizon model. Pilot
    this inside ONE regime before crossing it with regime routing — the
    regime x horizon product multiplies training and serving complexity.
    """

    feature_names: tuple[str, ...]
    horizons: tuple[int, ...]
    horizon_models: tuple[models.ModelAdapter, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if not (len(self.horizons) == len(self.horizon_models) == len(self.weights)):
            raise ValueError("horizons, horizon_models and weights must have equal length")
        if not self.horizons:
            raise ValueError("multi-horizon ensemble needs at least one horizon model")
        # NaN passes every `<`/`<=` check (all NaN comparisons are False) and
        # inf normalizes to NaN, so a corrupted artifact would load here and
        # then serve NaN probabilities. Reject non-finite weights outright.
        if not all(math.isfinite(w) for w in self.weights):
            raise ValueError("weights must all be finite")
        total = sum(self.weights)
        if total <= 0.0 or any(w < 0.0 for w in self.weights):
            raise ValueError("weights must be non-negative with a positive sum")

    @property
    def model_family(self) -> str:
        return "multi_horizon_ensemble"

    def fit(
        self,
        feature_matrix: models.FeatureMatrix,
        labels: Sequence[int],
        sample_weight: Sequence[float] | None = None,
    ) -> "MultiHorizonEnsembleAdapter":
        raise RuntimeError("MultiHorizonEnsembleAdapter must be fitted via fit_multi_horizon_ensemble(), not .fit()")

    def probability(self, features: Mapping[str, float]) -> float:
        total = sum(self.weights)
        blended = sum(
            w * float(model.probability(features))
            for w, model in zip(self.weights, self.horizon_models)
        )
        return min(1.0, max(0.0, blended / total))

    def predict_proba(self, feature_matrix: models.FeatureMatrix) -> list[float]:
        result: list[float] = []
        for row in feature_matrix:
            features = dict(zip(self.feature_names, row))
            result.append(self.probability(features))
        return result

    def as_dict(self) -> dict[str, object]:
        return {
            "model_family": self.model_family,
            "feature_names": list(self.feature_names),
            "horizons": list(self.horizons),
            "weights": list(self.weights),
            "horizon_models": [model.as_dict() for model in self.horizon_models],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MultiHorizonEnsembleAdapter":
        feature_names = tuple(str(name) for name in payload.get("feature_names", ()))
        horizons = tuple(int(h) for h in payload.get("horizons", ()))
        weights = tuple(float(w) for w in payload.get("weights", ()))
        model_payloads = payload.get("horizon_models", [])
        loaded: list[models.ModelAdapter] = []
        for model_payload in model_payloads if isinstance(model_payloads, Sequence) else []:
            model = _load_submodel(model_payload)
            if model is None:
                raise ValueError("multi-horizon ensemble contains an unloadable submodel")
            loaded.append(model)
        return cls(
            feature_names=feature_names,
            horizons=horizons,
            horizon_models=tuple(loaded),
            weights=weights,
        )


def fit_multi_horizon_ensemble(
    feature_rows: Sequence[dataset.FeatureRow],
    candles: Sequence[data.Candle],
    feature_names: Sequence[str],
    horizons: Sequence[int] = (30, 60, 90),
    model_family: str = "catboost",
    label_threshold: float = 0.0002,
    tp_pct: float = 0.01,
    sl_pct: float = 0.005,
    weighting: str = "equal",
    validation_fraction: float = 0.2,
    target_key: str = "profitability",
    weights: Mapping[int, float] | None = None,
) -> MultiHorizonEnsembleAdapter:
    """Train one entry model per horizon on the SAME feature rows, then blend.

    weighting="equal" averages the probabilities; "validation" weights each
    horizon model by its accuracy edge over 0.5 on a chronological tail slice.
    The train slice ends max(horizons) bars before the validation slice so no
    training label's forward window overlaps validation (same purge idea as
    PurgedWalkForwardSplit).

    `target_key` selects which triple-barrier target the models learn:
    "profitability" (the long-side barrier, the backward-compatible default),
    "long_success", or "short_success". A SHORT entry model must be trained on
    short_success -- the complement of P(long_success) is NOT P(short_success)
    (a long that times out is neither), so a model trained on the long target
    cannot price a short.

    `feature_rows` may be a non-contiguous subset (e.g. one regime's bars);
    `candles` must be the FULL series because FeatureRow.index indexes into it.

    `weights`: a {horizon: weight} mapping of blend weights learned elsewhere
    (e.g. by a prefix-only diagnostic fit). Supplying it skips the validation
    split entirely and trains every horizon model on ALL of its labeled rows,
    which is how a deployed model reaches the same 100% training coverage a
    single-horizon model gets without ever choosing its weights on data it
    also trained on. Keyed by horizon, not positional, because this function
    sorts `horizons` internally -- a positional sequence in the caller's order
    would silently attach each weight to the wrong model. `weighting` is
    ignored when this is set.
    """
    if weighting not in ("equal", "validation"):
        raise ValueError("weighting must be 'equal' or 'validation'")
    distinct_horizons = set(int(h) for h in horizons)
    if weights is not None:
        weights = {int(h): float(w) for h, w in weights.items()}
        if set(weights) != distinct_horizons:
            raise ValueError(f"weights must have exactly one entry per distinct horizon: expected {sorted(distinct_horizons)}, got {sorted(weights)}")
        # NaN slips past both `w < 0` and `sum <= 0` (all comparisons with NaN
        # are False), and inf normalizes to NaN -- either would make every
        # blended probability NaN, silently, at serve time.
        if not all(math.isfinite(w) for w in weights.values()):
            raise ValueError("weights must all be finite")
        if any(w < 0.0 for w in weights.values()) or sum(weights.values()) <= 0.0:
            raise ValueError("weights must be non-negative with a positive sum")
    if target_key not in ("profitability", "long_success", "short_success"):
        raise ValueError("target_key must be profitability, long_success or short_success")
    horizons = tuple(sorted(set(int(h) for h in horizons)))
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("horizons must be positive integers")
    if not 0.0 < validation_fraction < 0.5:
        raise ValueError("validation_fraction must be in (0, 0.5)")

    labeled_by_horizon: dict[int, Sequence[dataset.LabeledRow]] = {}
    for horizon in horizons:
        labeled_by_horizon[horizon] = dataset.attach_labels(
            feature_rows,
            candles,
            horizon=horizon,
            label_threshold=label_threshold,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
        )

    n = min(len(rows) for rows in labeled_by_horizon.values())
    if n < 200:
        # attach_labels drops warmup_invalid rows, so a caller can pass plenty
        # of feature rows and still land here -- say which count is short.
        raise ValueError(
            f"need at least 200 labeled rows per horizon for multi-horizon ensemble; "
            f"got {n} from {len(feature_rows)} feature rows (warmup rows are dropped at labeling)"
        )
    if weights is None:
        # Reserve a validation tail (plus a purge gap so no training label's
        # forward window overlaps it) to learn the blend weights. The tail is
        # cut at the SHORTEST horizon's row count so every horizon's validation
        # slice covers the same bars.
        purge_gap = max(horizons)
        validation_start = int(n * (1.0 - validation_fraction))
        train_end = max(0, validation_start - purge_gap)
        if train_end < 100:
            raise ValueError("not enough rows left for training after the purge gap")
    else:
        # Weights were learned elsewhere, so no validation tail is needed and
        # each horizon trains on ALL of its own labeled rows (train_end=None
        # rather than `n`, which would clip the shorter horizons' extra tail).
        validation_start = n
        train_end = None

    factory = models.ModelFactory()
    fitted: list[models.ModelAdapter] = []
    learned_weights: list[float] = []
    for horizon in horizons:
        rows = labeled_by_horizon[horizon]
        train_rows = rows if train_end is None else rows[:train_end]
        matrix = training.feature_matrix(train_rows, feature_names)
        labels = [int(row.targets.get(target_key, row.label)) for row in train_rows]
        if len(set(labels)) < 2:
            raise ValueError(f"target '{target_key}' is single-class over the training slice; cannot fit horizon {horizon}")
        selection = factory.fit(model_family, matrix, labels, feature_names=feature_names)
        adapter = selection.adapter
        fitted.append(adapter)

        if weights is not None:
            continue
        if weighting == "validation":
            validation_rows = rows[validation_start:n]
            validation_matrix = training.feature_matrix(validation_rows, feature_names)
            probabilities = adapter.predict_proba(validation_matrix)
            correct = sum(
                1
                for prob, row in zip(probabilities, validation_rows)
                if (1 if prob >= 0.5 else 0) == int(row.targets.get(target_key, row.label))
            )
            accuracy = correct / len(validation_rows) if validation_rows else 0.5
            # Floor at a tiny epsilon so a below-chance model is (almost)
            # excluded instead of receiving a negative weight.
            learned_weights.append(max(accuracy - 0.5, 1e-6))
        else:
            learned_weights.append(1.0)

    # Keyed lookup, not positional: `horizons` is sorted above, so indexing a
    # caller-ordered sequence would attach each weight to the wrong model.
    final_weights = [weights[h] for h in horizons] if weights is not None else learned_weights
    total = sum(final_weights)
    normalized = tuple(w / total for w in final_weights)
    return MultiHorizonEnsembleAdapter(
        feature_names=tuple(feature_names),
        horizons=horizons,
        horizon_models=tuple(fitted),
        weights=normalized,
    )


def fit_stacking_ensemble(
    labeled_rows: Sequence[dataset.LabeledRow],
    feature_names: Sequence[str],
    direction_family: str = "catboost",
    profitability_family: str = "catboost",
    meta_family: str = "sklearn_logistic",
) -> StackingEnsembleAdapter:
    """Fit a stacking ensemble with leakage-safe chronological split."""
    import numpy as np

    n = len(labeled_rows)
    if n < 200:
        raise ValueError("need at least 200 labeled rows for stacking ensemble")

    # Chronological split: 60% base train, 20% meta train, 20% validation
    base_train_end = int(n * 0.6)
    meta_train_end = int(n * 0.8)

    base_train_rows = labeled_rows[:base_train_end]
    meta_train_rows = labeled_rows[base_train_end:meta_train_end]

    # Train base model 1: direction
    direction_features = training.feature_matrix(base_train_rows, feature_names)
    direction_labels = [row.targets.get("direction", row.label) for row in base_train_rows]
    direction_selection = models.ModelFactory().fit(
        direction_family,
        direction_features,
        direction_labels,
        feature_names=feature_names,
    )
    direction_model = direction_selection.adapter

    # Train base model 2: profitability
    profitability_features = training.feature_matrix(base_train_rows, feature_names)
    profitability_labels = [row.targets.get("profitability", row.label) for row in base_train_rows]
    profitability_selection = models.ModelFactory().fit(
        profitability_family,
        profitability_features,
        profitability_labels,
        feature_names=feature_names,
    )
    profitability_model = profitability_selection.adapter

    # Generate meta features on meta_train slice
    meta_X: list[list[float]] = []
    meta_y: list[int] = []
    for row in meta_train_rows:
        features = {name: float(row.features.get(name, 0.0)) for name in feature_names}
        p_dir = float(direction_model.probability(features))
        p_prof = float(profitability_model.probability(features))
        meta_X.append([p_dir, p_prof])
        meta_y.append(row.targets.get("profitability", row.label))

    # Train meta model
    meta_adapter = _fit_meta_model(np.array(meta_X), np.array(meta_y), meta_family)

    # Extract coefs/intercept for backward-compatible serialization
    meta_coefs = getattr(meta_adapter, "_coefs", [0.5, 0.5])
    meta_intercept = getattr(meta_adapter, "_intercept", 0.0)

    return StackingEnsembleAdapter(
        feature_names=tuple(feature_names),
        direction_model=direction_model,
        profitability_model=profitability_model,
        meta_model_family=meta_family,
        meta_coefs=meta_coefs,
        meta_intercept=meta_intercept,
        meta_adapter=meta_adapter,
    )
