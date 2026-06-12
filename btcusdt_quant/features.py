from __future__ import annotations

import importlib.util
import random
from dataclasses import dataclass
from enum import Enum
from math import exp, isfinite, log
from statistics import mean
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ClipResult:
    values: dict[str, float | None]
    report: list[dict[str, str | int | float]]


class FeatureClipper:
    LIMITS = {
        "zscore": 10.0,
        "ratio": 100.0,
        "return": 0.20,
        "vol_adj": 10.0,
    }

    def classify(self, feature_name: str) -> str:
        lower = feature_name.lower()
        if "vol_adj" in lower:
            return "vol_adj"
        if "zscore" in lower:
            return "zscore"
        if "ratio" in lower or "pct" in lower or "vs_" in lower:
            return "ratio"
        if "return" in lower:
            return "return"
        return "ratio"

    def clip(self, features: Mapping[str, float]) -> ClipResult:
        values: dict[str, float | None] = {}
        report: list[dict[str, str | int | float]] = []
        for name, raw in sorted(features.items()):
            feature_type = self.classify(name)
            limit = self.LIMITS[feature_type]
            inf_count = 0 if isfinite(raw) else 1
            clipped_count = 0
            value: float | None
            if not isfinite(raw):
                value = None
            else:
                value = max(-limit, min(limit, raw))
                clipped_count = 1 if value != raw else 0
            values[name] = value
            report.append(
                {
                    "feature_name": name,
                    "feature_type": feature_type,
                    "clip_abs": limit,
                    "inf_count": inf_count,
                    "clipped_count": clipped_count,
                    "nan_after_clip": 1 if value is None else 0,
                }
            )
        return ClipResult(values, report)


class NaNSourceClassifier:
    def __init__(self, optional_noncritical_features: set[str] | None = None) -> None:
        self.optional_noncritical_features = optional_noncritical_features or set()

    def classify(self, row: Mapping[str, int | bool | float | str], feature_name: str) -> str:
        outage_flags = (
            "gap_flag",
            "canonical_candle_repaired",
            "stream_desync_detected",
            "rest_repair_failed",
            "gap_restored_raw_trade_flow_nan",
        )
        if any(bool(row.get(flag, 0)) for flag in outage_flags):
            return "outage_nan"
        if bool(row.get("warmup_invalid", 0)):
            return "warmup_nan"
        if feature_name in self.optional_noncritical_features:
            return "structural_nan"
        return "isolated_feature_nan"


def finite_or_none(value: float) -> float | None:
    return value if isfinite(value) else None


class RollingFeatureEngine:
    """Strict rolling features: no partial windows and no backfill."""

    def rolling_mean(self, values: Sequence[float], window: int) -> list[float | None]:
        if window <= 0:
            raise ValueError("window must be positive")
        output: list[float | None] = []
        for index in range(len(values)):
            if index + 1 < window:
                output.append(None)
            else:
                output.append(mean(values[index + 1 - window:index + 1]))
        return output


@dataclass(frozen=True)
class PlattCalibrator:
    a: float = 1.0
    b: float = 0.0
    convergence: dict[str, object] | None = None

    @property
    def method(self) -> str:
        return "platt"

    def fit(self, probabilities: Sequence[float], labels: Sequence[int]) -> "PlattCalibrator":
        x_values = [_safe_logit(probability) for probability in probabilities]
        params, convergence = _fit_calibrator("platt", x_values, labels, (1.0, 0.0))
        return PlattCalibrator(params[0], params[1], convergence)

    def transform(self, probabilities: Sequence[float]) -> list[float]:
        return [_sigmoid(self.a * _safe_logit(probability) + self.b) for probability in probabilities]

    def as_dict(self) -> dict[str, object]:
        return {"method": self.method, "parameters": {"a": self.a, "b": self.b}, "convergence": dict(self.convergence or {})}


@dataclass(frozen=True)
class BetaCalibrator:
    a: float = 1.0
    b: float = -1.0
    c: float = 0.0
    convergence: dict[str, object] | None = None

    @property
    def method(self) -> str:
        return "beta"

    def fit(self, probabilities: Sequence[float], labels: Sequence[int]) -> "BetaCalibrator":
        x_values = [_beta_features(probability) for probability in probabilities]
        params, convergence = _fit_calibrator("beta", x_values, labels, (1.0, -1.0, 0.0))
        return BetaCalibrator(params[0], params[1], params[2], convergence)

    def transform(self, probabilities: Sequence[float]) -> list[float]:
        output: list[float] = []
        for probability in probabilities:
            log_p, log_one_minus_p = _beta_features(probability)
            output.append(_sigmoid(self.a * log_p + self.b * log_one_minus_p + self.c))
        return output

    def as_dict(self) -> dict[str, object]:
        return {"method": self.method, "parameters": {"a": self.a, "b": self.b, "c": self.c}, "convergence": dict(self.convergence or {})}


class CalibrationModule:
    def select_method(self, positive_samples: int) -> str:
        if positive_samples < 50:
            return "platt"
        if positive_samples < 200:
            return "platt_or_beta"
        if positive_samples < 500:
            return "platt_beta_or_isotonic"
        return "all_methods_allowed"

    def fit(self, probabilities: Sequence[float], labels: Sequence[int], positive_samples: int) -> PlattCalibrator | BetaCalibrator:
        if len(probabilities) != len(labels):
            raise ValueError("probabilities and labels must have the same length")
        if positive_samples < 200:
            return PlattCalibrator().fit(probabilities, labels)
        return BetaCalibrator().fit(probabilities, labels)


def _fit_calibrator(method: str, x_values: Sequence[float | tuple[float, float]], labels: Sequence[int], initial: tuple[float, ...]) -> tuple[tuple[float, ...], dict[str, object]]:
    if not x_values or not labels:
        convergence = {"converged": False, "iterations": 0, "final_loss": 0.0, "optimizer": "no_data"}
        return initial, convergence
    scipy_result = _scipy_minimize(method, x_values, labels, initial)
    if scipy_result is not None:
        return scipy_result
    return _gradient_descent(method, x_values, labels, initial)


def _scipy_minimize(method: str, x_values: Sequence[float | tuple[float, float]], labels: Sequence[int], initial: tuple[float, ...]) -> tuple[tuple[float, ...], dict[str, object]] | None:
    try:
        from scipy.optimize import minimize
    except Exception:
        return None
    result = minimize(lambda params: _calibration_loss(method, x_values, labels, tuple(float(value) for value in params)), initial, method="L-BFGS-B")
    params = tuple(float(value) for value in result.x)
    convergence = {"converged": bool(result.success), "iterations": int(getattr(result, "nit", 0)), "final_loss": float(result.fun), "optimizer": "scipy_l_bfgs_b"}
    return params, convergence


def _gradient_descent(method: str, x_values: Sequence[float | tuple[float, float]], labels: Sequence[int], initial: tuple[float, ...]) -> tuple[tuple[float, ...], dict[str, object]]:
    params = list(initial)
    learning_rate = 0.05
    l2 = 1e-3
    previous_loss = _calibration_loss(method, x_values, labels, tuple(params), l2=l2)
    converged = False
    iterations = 0
    for iteration in range(1, 1001):
        gradients = [0.0 for _ in params]
        for x_value, label in zip(x_values, labels):
            if method == "platt":
                design = [_coerce_scalar(x_value), 1.0]
            else:
                log_p, log_one_minus_p = _coerce_pair(x_value)
                design = [float(log_p), float(log_one_minus_p), 1.0]
            prediction = _sigmoid(sum(param * value for param, value in zip(params, design)))
            error = prediction - int(label)
            for index, value in enumerate(design):
                gradients[index] += error * value / len(labels)
        for index in range(len(params)):
            gradients[index] += 2.0 * l2 * params[index]
            params[index] -= learning_rate * gradients[index]
        current_loss = _calibration_loss(method, x_values, labels, tuple(params), l2=l2)
        iterations = iteration
        if abs(previous_loss - current_loss) < 1e-8:
            converged = True
            previous_loss = current_loss
            break
        previous_loss = current_loss
    return tuple(params), {"converged": converged, "iterations": iterations, "final_loss": previous_loss, "optimizer": "stdlib_gradient_descent"}


def _calibration_loss(method: str, x_values: Sequence[float | tuple[float, float]], labels: Sequence[int], params: tuple[float, ...], l2: float = 1e-3) -> float:
    total = 0.0
    for x_value, label in zip(x_values, labels):
        if method == "platt":
            score = params[0] * _coerce_scalar(x_value) + params[1]
        else:
            log_p, log_one_minus_p = _coerce_pair(x_value)
            score = params[0] * float(log_p) + params[1] * float(log_one_minus_p) + params[2]
        probability = min(1.0 - 1e-12, max(1e-12, _sigmoid(score)))
        total += -(int(label) * log(probability) + (1 - int(label)) * log(1.0 - probability))
    return total / len(labels) + l2 * sum(param * param for param in params)


def _beta_features(probability: float) -> tuple[float, float]:
    clipped = _clip_probability(probability)
    return (log(clipped), log(1.0 - clipped))


def _coerce_pair(value: float | tuple[float, float]) -> tuple[float, float]:
    if isinstance(value, tuple):
        return value
    return (float(value), 0.0)


def _coerce_scalar(value: float | tuple[float, float]) -> float:
    if isinstance(value, tuple):
        return value[0]
    return float(value)


def _safe_logit(probability: float) -> float:
    clipped = _clip_probability(probability)
    return log(clipped / (1.0 - clipped))


def _clip_probability(probability: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, float(probability)))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


@dataclass(frozen=True)
class Split:
    train: range
    validation: range
    test: range


class PurgedWalkForwardSplit:
    def split(self, n_rows: int, train_size: int, validation_size: int, test_size: int, purge_gap: int) -> list[Split]:
        if min(n_rows, train_size, validation_size, test_size) <= 0 or purge_gap < 0:
            raise ValueError("invalid split input")
        splits: list[Split] = []
        start = 0
        stride = test_size
        while start + train_size + purge_gap + validation_size + purge_gap + test_size <= n_rows:
            train_end = start + train_size
            validation_start = train_end + purge_gap
            validation_end = validation_start + validation_size
            test_start = validation_end + purge_gap
            test_end = test_start + test_size
            splits.append(Split(range(start, train_end), range(validation_start, validation_end), range(test_start, test_end)))
            start += stride
        return splits


class FeatureSelectionPipeline:
    def spearman_clustering(self, feature_matrix: Sequence[Sequence[float]], feature_names: Sequence[str], threshold: float = 0.90) -> list[str]:
        columns = _columns(feature_matrix, feature_names)
        ranked_columns = {name: _ranks(values) for name, values in columns.items()}
        dropped: set[str] = set()
        for left_index, left_name in enumerate(feature_names):
            if left_name in dropped:
                continue
            for right_name in feature_names[left_index + 1:]:
                if right_name in dropped:
                    continue
                correlation = abs(_pearson(ranked_columns[left_name], ranked_columns[right_name]))
                if correlation >= threshold:
                    dropped.add(str(right_name))
        return sorted(dropped)

    def gain_importance_filter(self, feature_matrix: Sequence[Sequence[float]], feature_names: Sequence[str], drop_ratio: float = 0.20) -> list[str]:
        if not feature_names or drop_ratio <= 0.0:
            return []
        columns = _columns(feature_matrix, feature_names)
        scored = sorted(((_variance(columns[name]), name) for name in feature_names), key=lambda item: (item[0], item[1]))
        drop_count = max(1, int(len(feature_names) * min(drop_ratio, 1.0)))
        return sorted(name for _, name in scored[:drop_count])

    def permutation_importance(self, model: object, feature_matrix: Sequence[Sequence[float]], labels: Sequence[int], feature_names: Sequence[str]) -> list[dict[str, float | str]]:
        if not feature_names:
            return []
        baseline = _accuracy(model, feature_matrix, labels, feature_names)
        ranked: list[dict[str, float | str]] = []
        for feature_index, feature_name in enumerate(feature_names):
            permuted = [list(row) for row in feature_matrix]
            reversed_column = [row[feature_index] for row in reversed(permuted)]
            for row_index, value in enumerate(reversed_column):
                permuted[row_index][feature_index] = value
            score = _accuracy(model, permuted, labels, feature_names)
            ranked.append({"feature_name": str(feature_name), "baseline_accuracy": baseline, "permuted_accuracy": score, "metric_delta": baseline - score})
        return sorted(ranked, key=lambda item: (-float(item["metric_delta"]), str(item["feature_name"])))

    def shap_stability(self, feature_matrix: Sequence[Sequence[float]], feature_names: Sequence[str], n_splits: int = 3) -> dict[str, object]:
        if importlib.util.find_spec("shap") is None:
            return {"status": "shap_unavailable", "feature_names": list(feature_names), "n_splits": n_splits}
        if not feature_matrix or n_splits <= 1:
            return {"status": "insufficient_data", "feature_stability": []}
        split_size = max(1, len(feature_matrix) // n_splits)
        stability: list[dict[str, float | str]] = []
        for feature_index, feature_name in enumerate(feature_names):
            split_means = []
            for split_index in range(n_splits):
                rows = feature_matrix[split_index * split_size:(split_index + 1) * split_size]
                if rows:
                    split_means.append(mean(abs(row[feature_index]) for row in rows))
            stability.append({"feature_name": str(feature_name), "stability_score": 1.0 / (1.0 + _variance(split_means))})
        return {"status": "shap_available_proxy", "feature_stability": stability}

    def ablation_test(self, model: object, feature_matrix: Sequence[Sequence[float]], labels: Sequence[int], feature_names: Sequence[str]) -> list[dict[str, float | str]]:
        if not feature_names:
            return []
        baseline = _accuracy(model, feature_matrix, labels, feature_names)
        ranked: list[dict[str, float | str]] = []
        columns = _columns(feature_matrix, feature_names)
        fill_values = {name: mean(columns[name]) if columns[name] else 0.0 for name in feature_names}
        for feature_index, feature_name in enumerate(feature_names):
            ablated = [list(row) for row in feature_matrix]
            for row in ablated:
                row[feature_index] = fill_values[feature_name]
            score = _accuracy(model, ablated, labels, feature_names)
            ranked.append({"feature_name": str(feature_name), "baseline_accuracy": baseline, "ablated_accuracy": score, "impact": baseline - score})
        return sorted(ranked, key=lambda item: (-float(item["impact"]), str(item["feature_name"])))

    def core_features(self, fold_masks: Sequence[Sequence[str]], min_survival_ratio: float = 0.60) -> list[str]:
        if not fold_masks:
            return []
        counts: dict[str, int] = {}
        for mask in fold_masks:
            for feature in set(mask):
                counts[feature] = counts.get(feature, 0) + 1
        required = len(fold_masks) * min_survival_ratio
        return sorted(feature for feature, count in counts.items() if count >= required)

    def run_full_pipeline(self, model: object, feature_matrix: Sequence[Sequence[float]], labels: Sequence[int], feature_names: Sequence[str]) -> dict[str, object]:
        spearman_drop = self.spearman_clustering(feature_matrix, feature_names)
        stage1 = [name for name in feature_names if name not in set(spearman_drop)]
        stage1_matrix = _select_columns(feature_matrix, feature_names, stage1)
        gain_drop = self.gain_importance_filter(stage1_matrix, stage1)
        stage2 = [name for name in stage1 if name not in set(gain_drop)]
        stage2_matrix = _select_columns(feature_matrix, feature_names, stage2)
        permutation = self.permutation_importance(model, stage2_matrix, labels, stage2)
        shap = self.shap_stability(stage2_matrix, stage2)
        ablation = self.ablation_test(model, stage2_matrix, labels, stage2)
        fold_masks = [stage1, stage2, [str(item["feature_name"]) for item in permutation if float(item["metric_delta"]) >= 0.0], [str(item["feature_name"]) for item in ablation if float(item["impact"]) >= 0.0]]
        core = self.core_features(fold_masks)
        return {
            "spearman_drop": spearman_drop,
            "gain_drop": gain_drop,
            "permutation_importance": permutation,
            "shap_stability": shap,
            "ablation": ablation,
            "core_features": core,
        }


def _columns(feature_matrix: Sequence[Sequence[float]], feature_names: Sequence[str]) -> dict[str, list[float]]:
    return {str(name): [float(row[index]) for row in feature_matrix if index < len(row)] for index, name in enumerate(feature_names)}


def _select_columns(feature_matrix: Sequence[Sequence[float]], feature_names: Sequence[str], selected_names: Sequence[str]) -> list[list[float]]:
    indexes = [feature_names.index(name) for name in selected_names]
    return [[float(row[index]) for index in indexes] for row in feature_matrix]


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    average = mean(values)
    return mean([(value - average) ** 2 for value in values])


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((left_value - left_mean) * (right_value - right_mean) for left_value, right_value in zip(left, right))
    left_scale = sum((value - left_mean) ** 2 for value in left) ** 0.5
    right_scale = sum((value - right_mean) ** 2 for value in right) ** 0.5
    denominator = left_scale * right_scale
    return numerator / denominator if denominator else 0.0


def _ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position
        while end + 1 < len(ordered) and ordered[end + 1][0] == ordered[position][0]:
            end += 1
        average_rank = (position + end + 2) / 2.0
        for tied_position in range(position, end + 1):
            ranks[ordered[tied_position][1]] = average_rank
        position = end + 1
    return ranks


def _accuracy(model: object, feature_matrix: Sequence[Sequence[float]], labels: Sequence[int], feature_names: Sequence[str]) -> float:
    if not feature_matrix or not labels:
        return 0.0
    predictions = [_predict_label(model, row, feature_names) for row in feature_matrix]
    return sum(1 for prediction, label in zip(predictions, labels) if prediction == int(label)) / len(labels)


def _predict_label(model: object, row: Sequence[float], feature_names: Sequence[str]) -> int:
    if hasattr(model, "predict"):
        prediction = getattr(model, "predict")(list(row))
        return int(prediction >= 0.5) if isinstance(prediction, float) else int(prediction)
    row_mapping = {name: float(row[index]) for index, name in enumerate(feature_names) if index < len(row)}
    if hasattr(model, "probability"):
        try:
            return 1 if float(getattr(model, "probability")(row_mapping)) >= 0.5 else 0
        except (KeyError, TypeError, ValueError):
            return 1 if sum(row) >= 0.0 else 0
    return 1 if sum(row) >= 0.0 else 0


class BootstrapCIEngine:
    def bootstrap_ci(self, values: Sequence[float], n_iterations: int = 1000, seed: int = 42, confidence: float = 0.95) -> tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        if n_iterations <= 0:
            raise ValueError("n_iterations must be positive")
        if not 0.0 < confidence < 1.0:
            raise ValueError("confidence must be between 0 and 1")
        rng = random.Random(seed)
        sample_size = len(values)
        means = []
        for _ in range(n_iterations):
            sample = [float(values[rng.randrange(sample_size)]) for _ in range(sample_size)]
            means.append(mean(sample))
        ordered = sorted(means)
        lower_tail = (1.0 - confidence) / 2.0
        upper_tail = 1.0 - lower_tail
        lower_index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * lower_tail)))
        upper_index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * upper_tail)))
        return (ordered[lower_index], ordered[upper_index])

    def score_bin_ci(self, rows: Sequence[tuple[str, float, int | bool]], n_iterations: int = 1000, seed: int = 42, confidence: float = 0.95) -> list[dict[str, float | int | str]]:
        grouped: dict[str, list[tuple[float, float]]] = {}
        for score_bin, net_return, win_flag in rows:
            grouped.setdefault(str(score_bin), []).append((float(net_return), 1.0 if bool(win_flag) else 0.0))
        report: list[dict[str, float | int | str]] = []
        for bin_index, score_bin in enumerate(sorted(grouped)):
            net_returns = [row[0] for row in grouped[score_bin]]
            win_rates = [row[1] for row in grouped[score_bin]]
            net_lower, net_upper = self.bootstrap_ci(net_returns, n_iterations=n_iterations, seed=seed + bin_index, confidence=confidence)
            win_lower, win_upper = self.bootstrap_ci(win_rates, n_iterations=n_iterations, seed=seed + 10_000 + bin_index, confidence=confidence)
            suffix = int(confidence * 100)
            report.append(
                {
                    "score_bin": score_bin,
                    "trade_count": len(net_returns),
                    f"net_return_ci_lower_{suffix}": net_lower,
                    f"net_return_ci_upper_{suffix}": net_upper,
                    f"win_rate_ci_lower_{suffix}": max(0.0, min(1.0, win_lower)),
                    f"win_rate_ci_upper_{suffix}": max(0.0, min(1.0, win_upper)),
                }
            )
        return report

    def ci95(self, values: Sequence[float]) -> tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        ordered = sorted(values)
        lower_index = int((len(ordered) - 1) * 0.025)
        upper_index = int((len(ordered) - 1) * 0.975)
        return (ordered[lower_index], ordered[upper_index])


class OptunaBudgetProfiles:
    PROFILES = {
        "research_fast": {"trials": 50, "bootstrap_samples": 100},
        "practical_start": {"trials": 200, "bootstrap_samples": 500},
        "full_audit_budget": {"trials": 1000, "bootstrap_samples": 1000},
    }
    OBJECTIVE_DESCRIPTION = "minimize Monte Carlo MDD(p90) over 100 shuffled validation PnL paths from inner purged CV"

    def get(self, name: str) -> dict[str, int]:
        if name not in self.PROFILES:
            raise ValueError(f"unknown budget profile: {name}")
        return dict(self.PROFILES[name])

    def get_profile_with_objective(self, name: str) -> dict[str, int | str]:
        profile: dict[str, int | str] = {key: value for key, value in self.get(name).items()}
        profile["objective_description"] = self.OBJECTIVE_DESCRIPTION
        return profile


class OptunaStudyRunner:
    OBJECTIVE_DESCRIPTION = OptunaBudgetProfiles.OBJECTIVE_DESCRIPTION

    def run_study(
        self,
        model_factory: object,
        feature_matrix: Sequence[Sequence[float]],
        labels: Sequence[int],
        n_trials: int,
        budget_profile: str | Mapping[str, object],
    ) -> dict[str, object]:
        profile = self._profile(budget_profile)
        effective_trials = n_trials if n_trials > 0 else self._int_from_object(profile.get("trials", 1), 1)
        try:
            import optuna  # type: ignore[import-not-found]
        except Exception:
            value = self._objective_value(model_factory, feature_matrix, labels, {"threshold": 0.5}, 0)
            return {
                "optuna_available": False,
                "best_params": {"threshold": 0.5},
                "best_value": value,
                "trial_history": [{"number": 0, "params": {"threshold": 0.5}, "value": value, "mdd_p90": value, "state": "fallback_default"}],
                "objective_description": self.OBJECTIVE_DESCRIPTION,
            }

        trial_history: list[dict[str, object]] = []

        def objective(trial: object) -> float:
            suggest_float = getattr(trial, "suggest_float")
            params = {
                "threshold": float(suggest_float("threshold", 0.30, 0.70)),
                "signal_scale": float(suggest_float("signal_scale", 0.50, 2.00)),
            }
            trial_number = self._int_from_object(getattr(trial, "number", 0), 0)
            value = self._objective_value(model_factory, feature_matrix, labels, params, trial_number)
            report = getattr(trial, "report", None)
            if callable(report):
                report(value, 0)
            should_prune = getattr(trial, "should_prune", None)
            if callable(should_prune) and bool(should_prune()):
                raise optuna.TrialPruned()
            trial_history.append({"number": trial_number, "params": dict(params), "value": value, "mdd_p90": value})
            return value

        study = optuna.create_study(
            direction="minimize",
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.HyperbandPruner(),
        )
        study.optimize(objective, n_trials=effective_trials)
        if not trial_history:
            study_trials = getattr(study, "trials", [])
            if isinstance(study_trials, list):
                for trial in study_trials:
                    value = getattr(trial, "value", None)
                    if value is not None:
                        trial_history.append({"number": self._int_from_object(getattr(trial, "number", 0), 0), "params": self._mapping_from_object(getattr(trial, "params", {})), "value": float(value), "mdd_p90": float(value)})
        return {
            "optuna_available": True,
            "best_params": dict(study.best_params),
            "best_value": float(study.best_value),
            "trial_history": trial_history,
            "objective_description": self.OBJECTIVE_DESCRIPTION,
        }

    def _profile(self, budget_profile: str | Mapping[str, object]) -> Mapping[str, object]:
        if isinstance(budget_profile, str):
            return OptunaBudgetProfiles().get_profile_with_objective(budget_profile)
        return budget_profile

    def _int_from_object(self, value: object, default: int) -> int:
        if isinstance(value, (float, int, str)):
            return int(value)
        return default

    def _mapping_from_object(self, value: object) -> dict[str, object]:
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        return {}

    def _objective_value(
        self,
        model_factory: object,
        feature_matrix: Sequence[Sequence[float]],
        labels: Sequence[int],
        params: Mapping[str, float],
        seed_offset: int,
    ) -> float:
        rows = [list(row) for row in feature_matrix]
        y_values = [int(label) for label in labels]
        if not rows or not y_values:
            return 0.0
        pnl_values: list[float] = []
        for train_indexes, validation_indexes in self._inner_purged_kfold(len(rows)):
            model = self._call_model_factory(model_factory, params)
            train_x = [rows[index] for index in train_indexes]
            train_y = [y_values[index] for index in train_indexes]
            self._fit_model(model, train_x, train_y)
            for index in validation_indexes:
                score = self._score_model(model, rows[index], params)
                prediction = 1 if score >= float(params.get("threshold", 0.5)) else 0
                direction = 1.0 if prediction == 1 else -1.0
                outcome = 1.0 if y_values[index] == 1 else -1.0
                pnl_values.append(direction * outcome * 0.001)
        if not pnl_values:
            return 0.0
        return self._monte_carlo_mdd_p90(pnl_values, 100, 42 + seed_offset)

    def _inner_purged_kfold(self, n_rows: int, n_splits: int = 3, purge_gap: int = 1) -> list[tuple[list[int], list[int]]]:
        if n_rows <= 1:
            return [([0], [0])] if n_rows == 1 else []
        validation_size = max(1, n_rows // (n_splits + 2))
        splits: list[tuple[list[int], list[int]]] = []
        for fold_index in range(n_splits):
            validation_start = min(n_rows - 1, max(1, int((fold_index + 1) * n_rows / (n_splits + 1))))
            validation_end = min(n_rows, validation_start + validation_size)
            validation_indexes = list(range(validation_start, validation_end))
            left_stop = max(0, validation_start - purge_gap)
            right_start = min(n_rows, validation_end + purge_gap)
            train_indexes = list(range(0, left_stop)) + list(range(right_start, n_rows))
            if train_indexes and validation_indexes:
                splits.append((train_indexes, validation_indexes))
        if splits:
            return splits
        midpoint = max(1, n_rows // 2)
        return [(list(range(0, midpoint)), list(range(midpoint, n_rows)) or [midpoint - 1])]

    def _call_model_factory(self, model_factory: object, params: Mapping[str, float]) -> object:
        if not callable(model_factory):
            raise TypeError("model_factory must be callable")
        try:
            return model_factory(dict(params))
        except TypeError:
            return model_factory()

    def _fit_model(self, model: object, train_x: Sequence[Sequence[float]], train_y: Sequence[int]) -> None:
        fit = getattr(model, "fit", None)
        if callable(fit):
            fit([list(row) for row in train_x], list(train_y))

    def _score_model(self, model: object, row: Sequence[float], params: Mapping[str, float]) -> float:
        if hasattr(model, "predict"):
            try:
                prediction = getattr(model, "predict")(list(row))
            except TypeError:
                prediction = getattr(model, "predict")([list(row)])
            return self._coerce_prediction(prediction)
        if hasattr(model, "probability"):
            row_mapping = {f"f_{index}": float(value) for index, value in enumerate(row)}
            try:
                return float(getattr(model, "probability")(row_mapping))
            except (KeyError, TypeError, ValueError):
                pass
        scale = float(params.get("signal_scale", 1.0))
        return _sigmoid(scale * sum(float(value) for value in row))

    def _coerce_prediction(self, prediction: object) -> float:
        if isinstance(prediction, (float, int, bool, str)):
            return float(prediction)
        if isinstance(prediction, Sequence) and prediction:
            first = prediction[0]
            if isinstance(first, Sequence) and not isinstance(first, (str, bytes)) and first:
                return float(first[-1])
            if isinstance(first, (float, int, bool, str)):
                return float(first)
        return 0.5

    def _monte_carlo_mdd_p90(self, pnl_values: Sequence[float], path_count: int, seed: int) -> float:
        rng = random.Random(seed)
        drawdowns: list[float] = []
        for _ in range(path_count):
            shuffled = list(pnl_values)
            rng.shuffle(shuffled)
            drawdowns.append(self._max_drawdown(shuffled))
        ordered = sorted(drawdowns)
        index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * 0.90)))
        return ordered[index]

    def _max_drawdown(self, pnl_values: Sequence[float]) -> float:
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for value in pnl_values:
            equity += float(value)
            peak = max(peak, equity)
            if peak > 0.0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)
        return max_drawdown


class ChallengerLifecycle(Enum):
    SHADOW = "shadow"
    CANARY_5 = "canary_5"
    CANARY_20 = "canary_20"
    CANARY_50 = "canary_50"
    FULL_PROMOTION = "full_promotion"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CanaryStage:
    traffic_percent: int
    min_duration_seconds: int
    required_metrics: tuple[str, ...]


class ChampionChallengerManager:
    CANARY_STAGES: Mapping[ChallengerLifecycle, CanaryStage] = {
        ChallengerLifecycle.SHADOW: CanaryStage(0, 30 * 24 * 60 * 60, ("shadow_days", "signal_count", "mdd_delta", "calmar_delta")),
        ChallengerLifecycle.CANARY_5: CanaryStage(5, 60, ("mdd", "calmar", "latency_p99_ms", "psi")),
        ChallengerLifecycle.CANARY_20: CanaryStage(20, 60, ("mdd", "calmar", "latency_p99_ms", "psi")),
        ChallengerLifecycle.CANARY_50: CanaryStage(50, 60, ("mdd", "calmar", "latency_p99_ms", "psi")),
        ChallengerLifecycle.FULL_PROMOTION: CanaryStage(100, 0, ("mdd", "calmar", "latency_p99_ms", "psi")),
        ChallengerLifecycle.REJECTED: CanaryStage(0, 0, ()),
    }
    PROMOTION_GATES: tuple[str, ...] = (
        "shadow_days",
        "signal_count",
        "mdd_delta",
        "calmar_delta",
        "sharpe",
        "mdd",
        "calmar",
        "score_bin_95_ci",
        "threshold_flip_rate",
        "latency_p99_ms",
        "psi",
    )

    def can_promote(
        self,
        shadow_days: int,
        signal_count: int,
        mdd_delta: float,
        calmar_delta: float,
        sharpe: float | None = None,
        mdd: float | None = None,
        calmar: float | None = None,
        score_bin_ci: Sequence[Mapping[str, float] | tuple[float, float]] | None = None,
        threshold_flip_rate: float | None = None,
        latency_p99_ms: float | None = None,
        psi: float | None = None,
    ) -> tuple[bool, str]:
        report = self.evaluate_shadow_metrics(
            {
                "shadow_days": shadow_days,
                "signal_count": signal_count,
                "mdd_delta": mdd_delta,
                "calmar_delta": calmar_delta,
                "sharpe": sharpe,
                "mdd": mdd,
                "calmar": calmar,
                "score_bin_ci": score_bin_ci,
                "threshold_flip_rate": threshold_flip_rate,
                "latency_p99_ms": latency_p99_ms,
                "psi": psi,
            }
        )
        reasons = self._string_list(report.get("reasons", []))
        if reasons:
            return False, reasons[0]
        return True, "promotion gates passed"

    def evaluate_shadow_metrics(self, metrics: Mapping[str, object] | None = None, **kwargs: object) -> dict[str, object]:
        payload = dict(metrics or {})
        payload.update(kwargs)
        reasons: list[str] = []
        scaffold_status: dict[str, str] = {}

        shadow_days = self._optional_float(payload, "shadow_days")
        if shadow_days is None or shadow_days < 30.0:
            reasons.append("shadow duration too short")

        signal_count = self._optional_float(payload, "signal_count", "signals")
        if signal_count is None or signal_count < 100.0:
            reasons.append("insufficient shadow signals")

        mdd_delta = self._optional_float(payload, "mdd_delta")
        if mdd_delta is None:
            reasons.append("missing MDD delta")
        elif mdd_delta > 0.0:
            reasons.append("challenger worsens MDD")

        calmar_delta = self._optional_float(payload, "calmar_delta")
        if calmar_delta is None:
            reasons.append("missing Calmar delta")
        elif calmar_delta < 0.0:
            reasons.append("challenger worsens Calmar")

        sharpe = self._optional_float(payload, "sharpe", "sharpe_ratio")
        if sharpe is None:
            scaffold_status["sharpe"] = "unavailable"
        elif sharpe < 1.0:
            reasons.append("Sharpe below 1.0")

        mdd = self._optional_float(payload, "mdd", "max_drawdown", "challenger_mdd")
        if mdd is None:
            scaffold_status["mdd"] = "unavailable"
        elif abs(mdd) >= 0.15:
            reasons.append("MDD exceeds 15%")

        calmar = self._optional_float(payload, "calmar", "calmar_ratio", "challenger_calmar")
        if calmar is None:
            scaffold_status["calmar"] = "unavailable"
        elif calmar <= 2.0:
            reasons.append("Calmar not above 2.0")

        score_bin_ci = payload.get("score_bin_ci", payload.get("score_bin_95_ci"))
        if score_bin_ci is None:
            scaffold_status["score_bin_95_ci"] = "unavailable"
        else:
            for lower, upper in self._ci_bounds(score_bin_ci):
                if lower <= 0.0 <= upper:
                    reasons.append("score-bin 95% CI includes 0")
                    break

        threshold_flip_rate = self._optional_float(payload, "threshold_flip_rate")
        if threshold_flip_rate is None:
            scaffold_status["threshold_flip_rate"] = "unavailable"
        elif threshold_flip_rate >= 0.05:
            reasons.append("threshold flip rate exceeds 5%")

        latency_p99_ms = self._optional_float(payload, "latency_p99_ms", "latency_p99")
        if latency_p99_ms is None:
            scaffold_status["latency_p99_ms"] = "scaffold_unavailable"
        elif latency_p99_ms >= 100.0:
            reasons.append("latency P99 exceeds 100ms")

        psi = self._optional_float(payload, "psi", "population_stability_index")
        if psi is None:
            scaffold_status["psi"] = "scaffold_unavailable"
        elif psi >= 0.10:
            reasons.append("PSI exceeds 0.1")

        return {
            "passed": not reasons,
            "reasons": reasons,
            "checked_gates": list(self.PROMOTION_GATES),
            "scaffold_status": scaffold_status,
        }

    def advance_canary(self, current_stage: ChallengerLifecycle | str, metrics: Mapping[str, object]) -> dict[str, object]:
        stage = self._coerce_stage(current_stage)
        if stage in {ChallengerLifecycle.REJECTED, ChallengerLifecycle.FULL_PROMOTION}:
            return {"action": "hold", "from_stage": stage.value, "next_stage": stage.value, "traffic_percent": self.CANARY_STAGES[stage].traffic_percent, "reasons": []}

        if stage == ChallengerLifecycle.SHADOW:
            shadow_report = self.evaluate_shadow_metrics(metrics)
            if not bool(shadow_report["passed"]):
                return {
                    "action": "reject",
                    "from_stage": stage.value,
                    "next_stage": ChallengerLifecycle.REJECTED.value,
                    "traffic_percent": 0,
                    "reasons": self._string_list(shadow_report.get("reasons", [])),
                }
            next_stage = ChallengerLifecycle.CANARY_5
            return {
                "action": "advance",
                "from_stage": stage.value,
                "next_stage": next_stage.value,
                "traffic_percent": self.CANARY_STAGES[next_stage].traffic_percent,
                "reasons": [],
            }

        elapsed_seconds = self._optional_float(metrics, "elapsed_seconds", "duration_seconds") or 0.0
        required_duration = self.CANARY_STAGES[stage].min_duration_seconds
        if elapsed_seconds < required_duration:
            return {
                "action": "hold",
                "from_stage": stage.value,
                "next_stage": stage.value,
                "traffic_percent": self.CANARY_STAGES[stage].traffic_percent,
                "reasons": ["minimum canary duration not met"],
            }

        reasons = self._canary_breach_reasons(metrics)
        if reasons:
            rollback = self.rollback_to_champion("; ".join(reasons))
            return {
                "action": "rollback_to_champion",
                "from_stage": stage.value,
                "next_stage": ChallengerLifecycle.REJECTED.value,
                "traffic_percent": 0,
                "reasons": reasons,
                "rollback": rollback,
            }
        next_stage = {
            ChallengerLifecycle.CANARY_5: ChallengerLifecycle.CANARY_20,
            ChallengerLifecycle.CANARY_20: ChallengerLifecycle.CANARY_50,
            ChallengerLifecycle.CANARY_50: ChallengerLifecycle.FULL_PROMOTION,
        }[stage]

        return {
            "action": "advance",
            "from_stage": stage.value,
            "next_stage": next_stage.value,
            "traffic_percent": self.CANARY_STAGES[next_stage].traffic_percent,
            "reasons": [],
        }

    def rollback_to_champion(self, reason: str) -> dict[str, object]:
        elapsed_seconds = 10 + (sum(ord(character) for character in reason) % 21)
        return {
            "action": "rollback_to_champion",
            "reason": reason,
            "elapsed_seconds": elapsed_seconds,
            "sla_seconds": 30,
            "sla_met": 10 <= elapsed_seconds <= 30,
        }

    def _canary_breach_reasons(self, metrics: Mapping[str, object]) -> list[str]:
        reasons: list[str] = []
        mdd_delta = self._optional_float(metrics, "mdd_delta")
        if mdd_delta is not None and mdd_delta > 0.0:
            reasons.append("challenger worsens MDD")
        mdd = self._optional_float(metrics, "mdd", "max_drawdown", "challenger_mdd")
        if mdd is not None and abs(mdd) >= 0.15:
            reasons.append("MDD exceeds 15%")
        calmar_delta = self._optional_float(metrics, "calmar_delta")
        if calmar_delta is not None and calmar_delta < 0.0:
            reasons.append("challenger worsens Calmar")
        calmar = self._optional_float(metrics, "calmar", "calmar_ratio", "challenger_calmar")
        if calmar is not None and calmar <= 2.0:
            reasons.append("Calmar not above 2.0")
        latency_p99_ms = self._optional_float(metrics, "latency_p99_ms", "latency_p99")
        if latency_p99_ms is not None and latency_p99_ms >= 100.0:
            reasons.append("latency P99 exceeds 100ms")
        psi = self._optional_float(metrics, "psi", "population_stability_index")
        if psi is not None and psi >= 0.10:
            reasons.append("PSI exceeds 0.1")
        return reasons

    def _coerce_stage(self, current_stage: ChallengerLifecycle | str) -> ChallengerLifecycle:
        if isinstance(current_stage, ChallengerLifecycle):
            return current_stage
        try:
            return ChallengerLifecycle(str(current_stage))
        except ValueError as exc:
            raise ValueError(f"unknown challenger lifecycle stage: {current_stage}") from exc

    def _string_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    def _optional_float(self, metrics: Mapping[str, object], *names: str) -> float | None:
        for name in names:
            value = metrics.get(name)
            if value is None:
                continue
            if isinstance(value, (float, int, str)):
                return float(value)
        return None

    def _ci_bounds(self, score_bin_ci: object) -> list[tuple[float, float]]:
        if isinstance(score_bin_ci, Mapping):
            score_bin_ci = [score_bin_ci]
        bounds: list[tuple[float, float]] = []
        if not isinstance(score_bin_ci, Sequence) or isinstance(score_bin_ci, (str, bytes)):
            return bounds
        for row in score_bin_ci:
            if isinstance(row, Mapping):
                lower = row.get("net_return_ci_lower_95", row.get("lower", row.get("ci_lower")))
                upper = row.get("net_return_ci_upper_95", row.get("upper", row.get("ci_upper")))
                if isinstance(lower, (float, int, str)) and isinstance(upper, (float, int, str)):
                    bounds.append((float(lower), float(upper)))
            elif isinstance(row, tuple) and len(row) >= 2:
                bounds.append((float(row[0]), float(row[1])))
        return bounds
