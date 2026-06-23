from __future__ import annotations

import base64
import contextlib
import importlib
import importlib.util
import io
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


FeatureMatrix = Sequence[Sequence[float]]
_OPTIONAL_IMPORT_FAILURES: dict[str, str] = {}


class OptionalDependencyUnavailable(RuntimeError):
    pass


@runtime_checkable
class ModelAdapter(Protocol):
    @property
    def model_family(self) -> str:
        ...

    def fit(self, feature_matrix: FeatureMatrix, labels: Sequence[int], sample_weight: Sequence[float] | None = None) -> "ModelAdapter":
        ...

    def predict_proba(self, feature_matrix: FeatureMatrix) -> list[float]:
        ...

    def probability(self, values: Mapping[str, float]) -> float:
        ...

    def as_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class ModelSelection:
    adapter: ModelAdapter
    requested_family: str
    selected_family: str
    fallback_allowed: bool
    fallback_used: bool
    fallback_reason: str
    attempted_families: tuple[str, ...]
    unavailable_families: dict[str, str]
    model_params: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "requested_family": self.requested_family,
            "selected_family": self.selected_family,
            "fallback_allowed": self.fallback_allowed,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "attempted_families": list(self.attempted_families),
            "unavailable_families": dict(self.unavailable_families),
            "model_params": dict(self.model_params),
        }


class LightGBMAdapter:
    DEFAULT_PARAMS: Mapping[str, object] = {
        "objective": "binary",
        "n_estimators": 80,
        "learning_rate": 0.05,
        "random_state": 42,
        "use_missing": True,
        "zero_as_missing": False,
        "verbosity": -1,
    }

    def __init__(self, feature_names: Sequence[str] | None = None, model_params: Mapping[str, object] | None = None) -> None:
        self.feature_names = tuple(str(name) for name in feature_names) if feature_names is not None else ()
        self.model_params = _merged_params(self.DEFAULT_PARAMS, model_params)
        self.model: object | None = None

    @property
    def model_family(self) -> str:
        return "lightgbm"

    @staticmethod
    def available() -> bool:
        return "lightgbm" not in _OPTIONAL_IMPORT_FAILURES and importlib.util.find_spec("lightgbm") is not None

    def fit(self, feature_matrix: FeatureMatrix, labels: Sequence[int], sample_weight: Sequence[float] | None = None) -> "LightGBMAdapter":
        lgb = _import_optional_module("lightgbm")

        rows = _matrix_to_float_lists(feature_matrix)
        label_values = [int(label) for label in labels]
        if len(rows) != len(label_values):
            raise ValueError("feature_matrix and labels must have the same length")
        if not self.feature_names:
            self.feature_names = _default_feature_names(rows)
        model = lgb.LGBMClassifier(**self.model_params)
        fit_kwargs: dict[str, object] = {}
        if sample_weight is not None:
            fit_kwargs["sample_weight"] = [float(weight) for weight in sample_weight]
        model.fit(rows, label_values, **fit_kwargs)
        self.model = model
        return self

    def predict_proba(self, feature_matrix: FeatureMatrix) -> list[float]:
        if self.model is None:
            raise RuntimeError("lightgbm adapter must be fitted before predict_proba")
        rows = _matrix_to_float_lists(feature_matrix)
        if hasattr(self.model, "predict_proba"):
            predictions = getattr(self.model, "predict_proba")(rows)
        else:
            predictions = getattr(self.model, "predict")(rows)
        return _positive_class_probabilities(predictions)

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "model_family": self.model_family,
            "feature_names": list(self.feature_names),
            "model_params": dict(self.model_params),
            "missing_policy": {"use_missing": True, "zero_as_missing": False},
            "fitted": self.model is not None,
        }
        payload["weights"] = _feature_importance_map(self.model, self.feature_names)
        serialized = _serialized_booster(self.model)
        if serialized:
            payload["serialized_model"] = serialized
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "LightGBMAdapter":
        feature_names = payload.get("feature_names", ())
        if isinstance(feature_names, str):
            feature_names = (feature_names,)
        feature_names = tuple(str(name) for name in feature_names)
        model_params = payload.get("model_params", {})
        if not isinstance(model_params, Mapping):
            model_params = {}
        adapter = cls(feature_names=feature_names, model_params=model_params)
        serialized = payload.get("serialized_model")
        if not serialized:
            raise ValueError("lightgbm model.json missing serialized_model; retrain with updated code to include serialization")
        try:
            lgb = _import_optional_module("lightgbm")
            booster = lgb.Booster(model_str=str(serialized))
            adapter.model = booster
        except Exception as error:
            raise ValueError(f"failed to load lightgbm serialized model: {error}") from error
        return adapter

    def probability(self, values: Mapping[str, float]) -> float:
        if self.model is None:
            raise RuntimeError("lightgbm adapter must be fitted before probability")
        matrix = _matrix_to_float_lists([[float(values.get(name, 0.0)) for name in self.feature_names]])
        probs = self.predict_proba(matrix)
        return probs[0] if probs else 0.5


class CatBoostAdapter:
    DEFAULT_PARAMS: Mapping[str, object] = {
        "loss_function": "Logloss",
        "iterations": 80,
        "learning_rate": 0.05,
        "random_seed": 42,
        "verbose": True,
        "allow_writing_files": False,
        "thread_count": -1,
        "task_type": "GPU",
        "devices": "0",
    }

    def __init__(self, feature_names: Sequence[str] | None = None, model_params: Mapping[str, object] | None = None) -> None:
        self.feature_names = tuple(str(name) for name in feature_names) if feature_names is not None else ()
        self.model_params = _merged_params(self.DEFAULT_PARAMS, model_params)
        self.model: object | None = None

    @property
    def model_family(self) -> str:
        return "catboost"

    @staticmethod
    def available() -> bool:
        return "catboost" not in _OPTIONAL_IMPORT_FAILURES and importlib.util.find_spec("catboost") is not None

    def fit(self, feature_matrix: FeatureMatrix, labels: Sequence[int], sample_weight: Sequence[float] | None = None) -> "CatBoostAdapter":
        catboost = _import_optional_module("catboost")

        rows = _matrix_to_float_lists(feature_matrix)
        label_values = [int(label) for label in labels]
        if len(rows) != len(label_values):
            raise ValueError("feature_matrix and labels must have the same length")
        if not self.feature_names:
            self.feature_names = _default_feature_names(rows)
        try:
            model = catboost.CatBoostClassifier(**self.model_params)
            fit_kwargs: dict[str, object] = {}
            if sample_weight is not None:
                fit_kwargs["sample_weight"] = [float(weight) for weight in sample_weight]
            model.fit(rows, label_values, **fit_kwargs)
            self.model = model
        except Exception as e:
            if self.model_params.get("task_type") == "GPU":
                print(f"[CatBoost] GPU training failed ({e}), falling back to CPU...")
                cpu_params = dict(self.model_params)
                cpu_params.pop("task_type", None)
                cpu_params.pop("devices", None)
                model = catboost.CatBoostClassifier(**cpu_params)
                fit_kwargs: dict[str, object] = {}
                if sample_weight is not None:
                    fit_kwargs["sample_weight"] = [float(weight) for weight in sample_weight]
                model.fit(rows, label_values, **fit_kwargs)
                self.model = model
            else:
                raise
        return self

    def predict_proba(self, feature_matrix: FeatureMatrix) -> list[float]:
        if self.model is None:
            raise RuntimeError("catboost adapter must be fitted before predict_proba")
        predictions = getattr(self.model, "predict_proba")(_matrix_to_float_lists(feature_matrix))
        return _positive_class_probabilities(predictions)

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "model_family": self.model_family,
            "feature_names": list(self.feature_names),
            "model_params": dict(self.model_params),
            "fitted": self.model is not None,
        }
        payload["weights"] = _feature_importance_map(self.model, self.feature_names)
        if self.model is not None:
            try:
                import tempfile, os
                with tempfile.NamedTemporaryFile(suffix=".cbm", delete=False) as tmp:
                    tmp_path = tmp.name
                getattr(self.model, "save_model")(tmp_path, format="cbm")
                with open(tmp_path, "rb") as f:
                    payload["serialized_model"] = base64.b64encode(f.read()).decode("ascii")
                os.remove(tmp_path)
            except Exception:
                pass
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CatBoostAdapter":
        feature_names = payload.get("feature_names", ())
        if isinstance(feature_names, str):
            feature_names = (feature_names,)
        feature_names = tuple(str(name) for name in feature_names)
        model_params = payload.get("model_params", {})
        if not isinstance(model_params, Mapping):
            model_params = {}
        adapter = cls(feature_names=feature_names, model_params=model_params)
        serialized = payload.get("serialized_model")
        if not serialized:
            raise ValueError("catboost model.json missing serialized_model; retrain with updated code to include serialization")
        try:
            catboost = _import_optional_module("catboost")
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".cbm", delete=False) as tmp:
                tmp.write(base64.b64decode(str(serialized)))
                tmp_path = tmp.name
            model = catboost.CatBoostClassifier()
            model.load_model(tmp_path)
            adapter.model = model
            os.remove(tmp_path)
        except Exception as error:
            raise ValueError(f"failed to load catboost serialized model: {error}") from error
        return adapter

    def probability(self, values: Mapping[str, float]) -> float:
        if self.model is None:
            raise RuntimeError("catboost adapter must be fitted before probability")
        matrix = _matrix_to_float_lists([[float(values.get(name, 0.0)) for name in self.feature_names]])
        probs = self.predict_proba(matrix)
        return probs[0] if probs else 0.5


class ModelFactory:
    SUPPORTED_FAMILIES: tuple[str, ...] = ("lightgbm", "catboost", "auto", "stacking_ensemble", "pytorch_multitask")

    def create(
        self,
        family: str = "auto",
        feature_names: Sequence[str] | None = None,
        model_params: Mapping[str, object] | None = None,
        fallback_allowed: bool = True,
    ) -> ModelAdapter:
        return self.select(family, feature_names, model_params, fallback_allowed).adapter

    def select(
        self,
        family: str = "auto",
        feature_names: Sequence[str] | None = None,
        model_params: Mapping[str, object] | None = None,
        fallback_allowed: bool = True,
    ) -> ModelSelection:
        requested = _normalize_family(family)
        attempted: list[str] = []
        unavailable: dict[str, str] = {}
        for candidate in _candidate_families(requested, fallback_allowed):
            attempted.append(candidate)
            if self._is_available(candidate):
                adapter = self._adapter(candidate, feature_names, model_params)
                return _selection(adapter, requested, candidate, fallback_allowed, attempted, unavailable, model_params)
            unavailable[candidate] = f"optional dependency '{_module_name(candidate)}' is not installed"
        raise OptionalDependencyUnavailable(_selection_error(requested, attempted, unavailable))

    def fit(
        self,
        family: str,
        feature_matrix: FeatureMatrix,
        labels: Sequence[int],
        feature_names: Sequence[str] | None = None,
        sample_weight: Sequence[float] | None = None,
        model_params: Mapping[str, object] | None = None,
        fallback_allowed: bool = True,
    ) -> ModelSelection:
        requested = _normalize_family(family)
        attempted: list[str] = []
        unavailable: dict[str, str] = {}
        for candidate in _candidate_families(requested, fallback_allowed):
            attempted.append(candidate)
            try:
                adapter = self._adapter(candidate, feature_names, model_params)
                adapter.fit(feature_matrix, labels, sample_weight=sample_weight)
                return _selection(adapter, requested, candidate, fallback_allowed, attempted, unavailable, model_params)
            except (OptionalDependencyUnavailable, ImportError, ModuleNotFoundError) as error:
                unavailable[candidate] = str(error)
                if not fallback_allowed:
                    raise
            except Exception as error:
                if not fallback_allowed:
                    raise
                unavailable[candidate] = f"fit failed: {error}"
        raise OptionalDependencyUnavailable(_selection_error(requested, attempted, unavailable))

    def _adapter(self, family: str, feature_names: Sequence[str] | None, model_params: Mapping[str, object] | None) -> ModelAdapter:
        if family == "lightgbm":
            return LightGBMAdapter(feature_names, model_params)
        if family == "catboost":
            return CatBoostAdapter(feature_names, model_params)
        if family == "pytorch_multitask":
            from . import multitask_nn
            params = dict(model_params or {})
            return multitask_nn.MultitaskNNAdapter(
                input_dim=int(params.get("input_dim", 0)),
                hidden_dims=tuple(int(v) for v in params.get("hidden_dims", [128, 64])),
                task=str(params.get("task", "profitability")),
                feature_names=tuple(feature_names) if feature_names is not None else (),
                epochs=int(params.get("epochs", 100)),
                batch_size=int(params.get("batch_size", 256)),
                learning_rate=float(params.get("learning_rate", 1e-3)),
                weight_decay=float(params.get("weight_decay", 1e-5)),
                early_stopping_patience=int(params.get("early_stopping_patience", 10)),
            )
        raise ValueError(f"unsupported model family: {family}")

    def _is_available(self, family: str) -> bool:
        if family == "lightgbm":
            return LightGBMAdapter.available()
        if family == "catboost":
            return CatBoostAdapter.available()
        if family == "pytorch_multitask":
            return _pytorch_available()
        return family in {"stacking_ensemble"}


def _selection(
    adapter: ModelAdapter,
    requested: str,
    selected: str,
    fallback_allowed: bool,
    attempted: Sequence[str],
    unavailable: Mapping[str, str],
    model_params: Mapping[str, object] | None,
) -> ModelSelection:
    fallback_used = bool(unavailable) or (requested != "auto" and selected != requested)
    reason = "requested family selected"
    if requested == "auto" and selected != "catboost":
        reason = "auto fallback chain selected first available family"
    if requested != "auto" and selected != requested:
        reason = f"requested family '{requested}' unavailable; selected '{selected}'"
    if not fallback_used:
        reason = "no fallback required"
    return ModelSelection(adapter, requested, selected, fallback_allowed, fallback_used, reason, tuple(attempted), dict(unavailable), dict(model_params or {}))


def _candidate_families(requested: str, fallback_allowed: bool) -> tuple[str, ...]:
    if requested == "auto":
        chain = ("catboost", "lightgbm", "pytorch_multitask")
    elif requested == "lightgbm":
        chain = ("lightgbm", "catboost", "pytorch_multitask")
    elif requested == "catboost":
        chain = ("catboost", "pytorch_multitask")
    elif requested == "pytorch_multitask":
        chain = ("pytorch_multitask", "catboost")
    else:
        raise ValueError(f"unsupported model family: {requested}")
    return chain if fallback_allowed else (chain[0],)


def _normalize_family(family: str) -> str:
    normalized = str(family or "auto").lower().strip()
    aliases = {"lgbm": "lightgbm", "cat": "catboost", "pytorch": "pytorch_multitask", "nn": "pytorch_multitask"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in ModelFactory.SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported model family: {family}")
    return normalized


def _module_name(family: str) -> str:
    return {"lightgbm": "lightgbm", "catboost": "catboost", "pytorch_multitask": "torch"}[family]


def _pytorch_available() -> bool:
    return importlib.util.find_spec("torch") is not None


def _selection_error(requested: str, attempted: Sequence[str], unavailable: Mapping[str, str]) -> str:
    return f"unable to create model family '{requested}' after {list(attempted)}: {dict(unavailable)}"


def _import_optional_module(module_name: str) -> object:
    cached_error = _OPTIONAL_IMPORT_FAILURES.get(module_name)
    if cached_error is not None:
        raise OptionalDependencyUnavailable(f"{module_name} unavailable: {cached_error}")
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return importlib.import_module(module_name)
    except Exception as error:
        _OPTIONAL_IMPORT_FAILURES[module_name] = str(error)
        raise OptionalDependencyUnavailable(f"{module_name} unavailable: {error}") from error


def _merged_params(defaults: Mapping[str, object], overrides: Mapping[str, object] | None) -> dict[str, object]:
    params = dict(defaults)
    params.update(dict(overrides or {}))
    return params


def _default_feature_names(rows: Sequence[Sequence[float]]) -> tuple[str, ...]:
    width = len(rows[0]) if rows else 0
    return tuple(f"f_{index}" for index in range(width))


def _row_mapping(row: Sequence[float], feature_names: Sequence[str]) -> dict[str, float]:
    return {str(name): float(row[index]) if index < len(row) else 0.0 for index, name in enumerate(feature_names)}


def _matrix_to_float_lists(feature_matrix: FeatureMatrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in feature_matrix]


def _positive_class_probabilities(predictions: object) -> list[float]:
    rows = _plain_list(predictions)
    probabilities = []
    for row in rows:
        values = _plain_list(row)
        if len(values) >= 2:
            probabilities.append(_clip_probability(float(values[1])))
        elif values:
            probabilities.append(_clip_probability(float(values[0])))
        else:
            probabilities.append(0.5)
    return probabilities


def _plain_list(value: object) -> list[object]:
    if hasattr(value, "tolist"):
        value = getattr(value, "tolist")()
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError:
        return [value]


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _feature_importance_map(model: object | None, feature_names: Sequence[str]) -> dict[str, float]:
    values: list[object] = []
    if model is not None:
        importance = getattr(model, "feature_importances_", None)
        if importance is None:
            get_importance = getattr(model, "get_feature_importance", None)
            if callable(get_importance):
                try:
                    importance = get_importance()
                except Exception:
                    importance = None
        if importance is not None:
            values = _plain_list(importance)
    return {str(name): float(values[index]) if index < len(values) else 0.0 for index, name in enumerate(feature_names)}


def _serialized_booster(model: object | None) -> str:
    if model is None:
        return ""
    booster = getattr(model, "booster_", None)
    model_to_string = getattr(booster, "model_to_string", None)
    if callable(model_to_string):
        try:
            return str(model_to_string())
        except Exception:
            return ""
    return ""
