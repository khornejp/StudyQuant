"""Pytest-wide safeguards for deterministic, CPU-only unit-test training.

Production CatBoost defaults to GPU 0.  Test code must opt into that path with
``model_params={"task_type": "GPU", "devices": "0"}`` so an ordinary unit
test cannot reserve the shared GPU merely by constructing a CatBoostAdapter.
GPU lease tests retain that explicit opt-in and cover the GPU-specific routing
behaviour without starting a CUDA fit.
"""

from __future__ import annotations

from collections.abc import Mapping
import os

from btcusdt_quant import models


def pytest_configure() -> None:
    """Run every pytest CatBoost fit on CPU unless the test explicitly opts in."""
    # Child CLI processes do not import this conftest.py.  Keep the flag in
    # their inherited environment so their default adapters are CPU too.
    os.environ["STUDYQUANT_TEST_CATBOOST_DEFAULT_DEVICE"] = "CPU"
    production_defaults: Mapping[str, object] = models.CatBoostAdapter.DEFAULT_PARAMS
    test_defaults = dict(production_defaults)
    test_defaults.pop("task_type", None)
    test_defaults.pop("devices", None)
    models.CatBoostAdapter.DEFAULT_PARAMS = test_defaults
