"""Unit tests for Optuna final-refit iteration capping.

_tune_catboost_with_optuna must:
1. record each trial's CatBoost early-stopping best_iteration,
2. cap the merged (final-refit) `iterations` at best_iteration + 1 of the
   winning trial, never above the suggested budget,
3. keep the suggested iterations when best_iteration is None or <= 0,
4. report best_trial_number / best_iteration / suggested_iterations /
   final_iterations consistently.

catboost/optuna are not required: deterministic fakes are injected into
sys.modules and models.CatBoostAdapter is patched, so this runs in any env.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from btcusdt_quant import training


# ---------------------------------------------------------------- fakes ----
class _FakeTrial:
    def __init__(self, number: int) -> None:
        self.number = number
        self.params: dict[str, object] = {}

    def suggest_int(self, name: str, low: int, high: int) -> int:
        value = low + (self.number * 131) % (high - low + 1)
        self.params[name] = int(value)
        return int(value)

    def suggest_float(self, name: str, low: float, high: float, log: bool = False) -> float:
        span = high - low
        value = low + span * ((self.number * 37) % 10) / 10.0
        self.params[name] = float(value)
        return float(value)


class _FakeStudy:
    def __init__(self) -> None:
        self.best_params: dict[str, object] = {}
        self.best_value: float = float("inf")
        self.best_trial: object = types.SimpleNamespace(number=-1)

    def optimize(self, objective, n_trials: int, show_progress_bar: bool = False) -> None:
        for number in range(n_trials):
            trial = _FakeTrial(number)
            value = objective(trial)
            if value < self.best_value:
                self.best_value = value
                self.best_params = dict(trial.params)
                self.best_trial = types.SimpleNamespace(number=number)


def _fake_optuna_module() -> types.ModuleType:
    module = types.ModuleType("optuna")
    module.create_study = lambda direction, sampler=None: _FakeStudy()  # type: ignore[attr-defined]
    samplers = types.ModuleType("optuna.samplers")
    samplers.TPESampler = lambda seed=None: object()  # type: ignore[attr-defined]
    module.samplers = samplers  # type: ignore[attr-defined]
    return module


class _FakeInnerModel:
    def __init__(self, best_iteration: object) -> None:
        self._best_iteration = best_iteration

    def get_best_iteration(self) -> object:
        return self._best_iteration


def _make_fake_adapter(best_iteration_fn):
    """FakeAdapter factory. best_iteration_fn(params) -> value for get_best_iteration."""

    class _FakeAdapter:
        def __init__(self, feature_names=None, model_params=None) -> None:
            self.feature_names = feature_names
            self.model_params = dict(model_params or {})
            self.model: object | None = None

        def fit(self, x, y, sample_weight=None, eval_set=None, use_best_model=False):
            self.model = _FakeInnerModel(best_iteration_fn(self.model_params))
            return self

        def predict_proba(self, x):
            # Loss quality driven ONLY by suggested iterations: the trial
            # whose iterations budget is closest to 700 predicts labels best
            # and therefore wins the study deterministically.
            iters = int(self.model_params.get("iterations", 500))
            err = min(0.45, 0.05 + abs(iters - 700) / 4000.0)
            return [1.0 - err for _ in x]

    return _FakeAdapter


# The objective computes logloss(prob_i, val_y_i) with a CONSTANT prob per
# trial, so the winning trial is simply the one whose constant prob is
# closest to the validation positive rate. With alternating labels
# (pos_rate=0.5), prob = 1 - err is closest to 0.5 when err is largest...
# To keep the winner intuitive (iterations nearest 700 wins), we instead use
# labels that are ~all 1s in validation (pos_rate ~ 1.0): then the SMALLEST
# err (iterations nearest 700) minimizes logloss.
def _dataset(n: int = 200):
    rows = [[float(i), float(i % 7)] for i in range(n)]
    # Train head mixed classes (so tuning isn't rejected). Validation tail
    # (rows 170+ after the 10-bar purge gap) is positive-DOMINATED but keeps
    # one negative so the degenerate-split guard passes: the loss-minimizing
    # constant prob is then ~0.97, so the trial with the SMALLEST error
    # (iterations nearest 700 in the fake) deterministically wins.
    labels = [(i % 2) for i in range(160)] + [1] * (n - 160)
    labels[175] = 0
    return rows, labels


# ---------------------------------------------------------------- tests ----
class OptunaBestIterationTests(unittest.TestCase):
    def _run_tuning(self, best_iteration_fn, n_trials: int = 5):
        rows, labels = _dataset()
        fake_adapter = _make_fake_adapter(best_iteration_fn)
        with mock.patch.dict(sys.modules, {"optuna": _fake_optuna_module(), "catboost": types.ModuleType("catboost")}):
            with mock.patch.object(training.models, "CatBoostAdapter", fake_adapter):
                merged, report = training._tune_catboost_with_optuna(
                    feature_matrix_values=rows,
                    labels=labels,
                    feature_names=["f0", "f1"],
                    n_trials=n_trials,
                    label_horizon=60,
                )
        return merged, report

    def test_final_iterations_capped_at_best_iteration_plus_one(self):
        merged, report = self._run_tuning(lambda params: int(params.get("iterations", 500)) // 4)
        self.assertTrue(report["optuna_available"])
        best_number = report["best_trial_number"]
        entry = next(e for e in report["trial_history"] if e["number"] == best_number)
        self.assertEqual(report["best_iteration"], entry["best_iteration"])
        self.assertIsNotNone(report["best_iteration"])
        expected = min(report["suggested_iterations"], report["best_iteration"] + 1)
        self.assertEqual(report["final_iterations"], expected)
        self.assertEqual(merged["iterations"], expected)
        # In this fake, best_iteration = suggested // 4, so the cap must have
        # actually LOWERED iterations (not a no-op assertion).
        self.assertLess(merged["iterations"], report["suggested_iterations"])
        # Other winning params still flow through the merge.
        self.assertIn("depth", merged)
        # final_params must be the EXACT dict the final refit receives,
        # including the capped iterations (best_params carries only the
        # suggested budget).
        self.assertEqual(report["final_params"], merged)
        self.assertEqual(report["final_params"]["iterations"], expected)
        self.assertEqual(report["best_params"]["iterations"], report["suggested_iterations"])
        self.assertFalse(report["best_iteration_degenerate"])

    def test_none_best_iteration_keeps_suggested_budget(self):
        merged, report = self._run_tuning(lambda params: None)
        self.assertIsNone(report["best_iteration"])
        self.assertEqual(report["final_iterations"], report["suggested_iterations"])
        self.assertEqual(merged["iterations"], report["suggested_iterations"])

    def test_zero_best_iteration_keeps_suggested_budget(self):
        merged, report = self._run_tuning(lambda params: 0)
        self.assertEqual(report["best_iteration"], 0)
        self.assertEqual(report["final_iterations"], report["suggested_iterations"])
        self.assertEqual(merged["iterations"], report["suggested_iterations"])
        # A first-tree-is-best result is a degenerate signal and must be
        # surfaced for run_summary analysis.
        self.assertTrue(report["best_iteration_degenerate"])
        self.assertEqual(report["final_params"], merged)

    def test_none_best_iteration_not_flagged_degenerate(self):
        _, report = self._run_tuning(lambda params: None)
        self.assertFalse(report["best_iteration_degenerate"])

    def test_cap_never_raises_above_suggested(self):
        # Degenerate getter claiming a best_iteration beyond the budget must
        # not INCREASE iterations.
        merged, report = self._run_tuning(lambda params: int(params.get("iterations", 500)) * 3)
        self.assertEqual(report["final_iterations"], report["suggested_iterations"])
        self.assertEqual(merged["iterations"], report["suggested_iterations"])

    def test_trial_history_records_best_iteration_per_trial(self):
        _, report = self._run_tuning(lambda params: int(params.get("iterations", 500)) // 4, n_trials=4)
        self.assertEqual(len(report["trial_history"]), 4)
        for entry in report["trial_history"]:
            self.assertIn("best_iteration", entry)
            self.assertEqual(entry["best_iteration"], int(entry["params"]["iterations"]) // 4)


if __name__ == "__main__":
    unittest.main()
