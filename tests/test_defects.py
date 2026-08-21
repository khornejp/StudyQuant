"""Regression tests for the defects fixed in the 2026-08 maintenance round."""
from __future__ import annotations

import unittest
import importlib.util
from datetime import timedelta
from unittest.mock import patch


class FoldLogTests(unittest.TestCase):
    def test_fold_log_preserves_small_entry_count_and_no_entry_state(self) -> None:
        from btcusdt_quant.training import format_oos_trading_log, oos_trading_metrics

        small = oos_trading_metrics([.9] * 4 + [.1] * 10_076, [.004] * 10_080, .5)
        rendered = format_oos_trading_log(small)
        self.assertIn("rows 10080, entries 4 (0.040%)", rendered)
        empty = oos_trading_metrics([.1] * 10, [.004] * 10, .5)
        self.assertIn("entries 0 (0.000%)", format_oos_trading_log(empty))
        self.assertIn("not-measured (no entries)", format_oos_trading_log(empty))


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed in the pinned venv")
class PytorchAdapterTests(unittest.TestCase):
    def test_weights_reach_weighted_bce_objective(self) -> None:
        import numpy as np
        import torch
        from btcusdt_quant.multitask_nn import MultitaskNNAdapter

        adapter = MultitaskNNAdapter(hidden_dims=(), epochs=1, batch_size=2, learning_rate=0.0)
        scheduler_values: list[float] = []

        class Scheduler:
            def step(self, value: float) -> None:
                scheduler_values.append(value)

        # Derive the synthetic loss from each example's label so it remains
        # paired with that example's weight when the production DataLoader
        # shuffles the batch.  The weighted mean is
        # (1 * 1 + 3 * 3) / (1 + 3) == 2.5, rather than 2.0 unweighted or
        # 5.0 if normalized by batch size.
        def synthetic_bce(logits: torch.Tensor, labels: torch.Tensor, *, reduction: str) -> torch.Tensor:
            self.assertEqual(reduction, "none")
            return logits * 0 + torch.where(labels == 0, 1.0, 3.0)

        with patch("btcusdt_quant.multitask_nn.F.binary_cross_entropy_with_logits", side_effect=synthetic_bce) as bce, \
             patch("btcusdt_quant.multitask_nn.torch.optim.lr_scheduler.ReduceLROnPlateau", return_value=Scheduler()):
            adapter.fit([[0.0], [1.0]], [0, 1], sample_weight=[1.0, 3.0])
        self.assertEqual(bce.call_count, 1)
        self.assertAlmostEqual(scheduler_values[0], 2.5)

    def test_adapter_is_single_head_not_an_invented_second_task(self) -> None:
        import torch
        from btcusdt_quant.multitask_nn import MultitaskNNAdapter

        adapter = MultitaskNNAdapter(hidden_dims=(), epochs=1, batch_size=2)
        adapter.fit([[0.0], [1.0]], [0, 1])
        state_keys = set(adapter._ensure_model().state_dict())
        self.assertIn("head.linear.weight", state_keys)
        self.assertFalse(any("direction_head" in key or "profitability_head" in key for key in state_keys))
        self.assertEqual(adapter.as_dict()["task"], "single_binary_label")


class SharedPriorGateTests(unittest.TestCase):
    def test_shared_prior_gate_records_window_and_test_purge_proof(self) -> None:
        from btcusdt_quant import cv, data, dataset, training

        start = data.utc_minute(2025, 1, 1, 0, 0)
        rows = [dataset.LabeledRow(
            index=i, open_time=start + timedelta(minutes=i), features={"rv_60": float(i)},
            label=0, label_reason="timeout_no_tp", target_return=0.0, gap_flag=0,
            repaired=False, warmup_invalid=False, targets={}, target_reasons={},
        ) for i in range(1_000)]
        config = training.TrainingConfig(
            vol_gate_feature="rv_60", vol_gate_train_quantile=.8,
            vol_gate_derivation="shared_prior_reserve", shared_prior_reserve_rows=200,
            walk_forward_train_size=200, walk_forward_validation_size=100,
            walk_forward_test_size=100, walk_forward_test_gap=10, label_horizon=10,
        )
        splits = training.configured_splits(len(rows), 10, config, cv.sample_intervals_from_labeled_rows(rows, 10))
        cutoff, proof = training.derive_shared_prior_volatility_gate(rows, "rv_60", .8, config, splits)
        self.assertEqual(cutoff, 160.0)
        self.assertEqual(proof["derivation_indices"], {"start": 0, "stop_exclusive": 200, "count": 200})
        self.assertEqual(proof["fold_test_starts"], [520, 630, 740, 850])
        self.assertEqual(proof["test_purge_boundary"], 510)
        self.assertTrue(proof["assertion_passed"])
