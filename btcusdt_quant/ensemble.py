"""Stacking ensemble model adapter."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from . import dataset, models, training


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
    if not isinstance(payload, Mapping):
        return None
    model_family = str(payload.get("model_family", ""))
    if "deterministic_centroid_linear" in model_family:
        from . import training
        return training.LinearClassifier.from_dict(payload)
    if model_family == "lightgbm":
        return models.LightGBMAdapter.from_dict(payload)
    if model_family == "catboost":
        return models.CatBoostAdapter.from_dict(payload)
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
