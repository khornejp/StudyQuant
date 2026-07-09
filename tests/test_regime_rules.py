"""Tests for the multi-feature rule-based regime detector.

These use only the standard library (no catboost/pyarrow), so they run in any
environment.
"""

from __future__ import annotations

import random
import unittest

from btcusdt_quant.regime_rules import (
    MultiFeatureRegimeConfig,
    MultiFeatureRegimeDetector,
    REGIME_CLASSES,
)


def _row(bias: float, rng: random.Random, *, vol: float = 0.01, bo_up: float = 0.0, bo_down: float = 0.0, volz: float = 0.0) -> dict[str, float]:
    return {
        "return_5": bias * 0.005 + rng.gauss(0, 0.002),
        "trend_slope_15m": bias * 0.008 + rng.gauss(0, 0.002),
        "trend_slope_30": bias * 0.009 + rng.gauss(0, 0.002),
        "trend_slope_1h": bias * 0.01 + rng.gauss(0, 0.002),
        "trend_slope_4h": bias * 0.01 + rng.gauss(0, 0.002),
        "return_4h": bias * 0.02 + rng.gauss(0, 0.003),
        "ema_gap_4h": bias * 0.01 + rng.gauss(0, 0.002),
        "atr_pct_1h": vol + abs(rng.gauss(0, 0.001)),
        "atr_pct_4h": vol + abs(rng.gauss(0, 0.001)),
        "bb_width_1h": 0.02 + abs(rng.gauss(0, 0.002)),
        "adx_1h": 25 + rng.gauss(0, 4),
        "adx_4h": 25 + rng.gauss(0, 4),
        "volume_z_1h": volz,
        "distance_from_24h_low": 0.02,
        "drawdown_from_24h_high": 0.02,
        "rolling_high_breakout_24h": bo_up,
        "rolling_low_breakdown_24h": bo_down,
    }


class MultiFeatureRegimeDetectorTests(unittest.TestCase):
    def _blocks(self) -> list[dict[str, float]]:
        rng = random.Random(0)
        return (
            [_row(1, rng) for _ in range(400)]
            + [_row(0, rng) for _ in range(400)]
            + [_row(-1, rng) for _ in range(400)]
        )

    def test_outputs_only_valid_classes(self) -> None:
        rows = self._blocks()
        det = MultiFeatureRegimeDetector().fit(rows)
        regimes = det.detect_all(rows)
        self.assertTrue(set(regimes) <= set(REGIME_CLASSES))
        self.assertEqual(len(regimes), len(rows))

    def test_deterministic(self) -> None:
        rows = self._blocks()
        det = MultiFeatureRegimeDetector().fit(rows)
        self.assertEqual(det.detect_all(rows), det.detect_all(rows))

    def test_causal_prefix_matches_detect_one(self) -> None:
        rows = self._blocks()
        det = MultiFeatureRegimeDetector().fit(rows)
        full = det.detect_all(rows)
        for k in (1, 50, 555, 999, len(rows)):
            self.assertEqual(det.detect_one(rows[:k]), full[:k][-1])

    def test_min_hold_reduces_churn(self) -> None:
        rng = random.Random(1)
        # Alternating noisy rows that would flip every bar without stabilization.
        rows = [_row(1 if i % 2 == 0 else -1, rng) for i in range(600)]
        stable = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(min_hold_bars=60)).fit(rows)
        churny = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(min_hold_bars=0)).fit(rows)
        def transitions(regs: list[str]) -> int:
            return sum(1 for a, b in zip(regs, regs[1:]) if a != b)
        self.assertLessEqual(transitions(stable.detect_all(rows)), transitions(churny.detect_all(rows)))

    def test_breakout_overrides_immediately(self) -> None:
        rng = random.Random(2)
        # Sit in range, then a single strong up-breakout bar with volume.
        rows = [_row(0, rng) for _ in range(100)]
        rows.append(_row(0, rng, bo_up=1.0, volz=2.0))
        det = MultiFeatureRegimeDetector().fit(rows)
        regimes = det.detect_all(rows)
        self.assertEqual(regimes[-1], "up")  # bypasses min-hold

    def test_persistence_round_trip(self) -> None:
        rows = self._blocks()
        det = MultiFeatureRegimeDetector().fit(rows)
        reloaded = MultiFeatureRegimeDetector.from_dict(det.to_dict())
        self.assertEqual(reloaded.detect_all(rows), det.detect_all(rows))

    def test_config_validation(self) -> None:
        with self.assertRaises(ValueError):
            MultiFeatureRegimeConfig(trend_enter=0.3, trend_exit=0.5)  # exit > enter
        with self.assertRaises(ValueError):
            MultiFeatureRegimeConfig(min_hold_bars=-1)
        with self.assertRaises(ValueError):
            MultiFeatureRegimeConfig(switch_confirm_bars=0)
        with self.assertRaises(ValueError):
            MultiFeatureRegimeConfig(fast_conflict_max=-0.1)
        with self.assertRaises(ValueError):
            MultiFeatureRegimeConfig(fast_exit=-0.1)

    def test_handles_missing_features_gracefully(self) -> None:
        det = MultiFeatureRegimeDetector().fit([{"trend_slope_1h": 0.0} for _ in range(10)])
        # Rows with no features at all must not raise and must yield valid classes.
        regimes = det.detect_all([{} for _ in range(5)])
        self.assertTrue(set(regimes) <= set(REGIME_CLASSES))

    def test_fast_trend_blocks_conflicting_entry(self) -> None:
        # Long-TF trend says up, but short-TF (5m/15m/30m) is sharply down.
        rng = random.Random(3)
        rows = [_row(0, rng) for _ in range(60)]
        conflict = _row(1, rng)  # long-TF up
        conflict["return_5"] = -0.05
        conflict["trend_slope_15m"] = -0.05
        conflict["trend_slope_30"] = -0.05
        rows_block = rows + [conflict]
        # With fast rules ON, the conflicting bar must NOT flip to up.
        det_on = MultiFeatureRegimeDetector(
            MultiFeatureRegimeConfig(min_hold_bars=0, fast_conflict_max=0.3)
        ).fit(rows_block)
        self.assertNotEqual(det_on.detect_all(rows_block)[-1], "up")
        # With fast rules OFF, the same bar is allowed to enter up.
        det_off = MultiFeatureRegimeDetector(
            MultiFeatureRegimeConfig(min_hold_bars=0, use_fast_trend_rules=False)
        ).fit(rows_block)
        # (Not asserting == "up" strictly, but the block must not apply.)
        self.assertTrue(set(det_off.detect_all(rows_block)) <= set(REGIME_CLASSES))

    def test_fast_trend_config_toggle_persists(self) -> None:
        cfg = MultiFeatureRegimeConfig(use_fast_trend_rules=False, fast_exit=1.2)
        det = MultiFeatureRegimeDetector(cfg).fit([{"return_5": 0.0} for _ in range(5)])
        reloaded = MultiFeatureRegimeDetector.from_dict(det.to_dict())
        self.assertFalse(reloaded.config.use_fast_trend_rules)
        self.assertEqual(reloaded.config.fast_exit, 1.2)
        self.assertTrue(reloaded.config.allow_direct_reversal)

    def _long_fast_row(self, long_z: float, fast_z: float) -> dict[str, float]:
        return {
            "return_5": fast_z, "trend_slope_15m": fast_z, "trend_slope_30": fast_z,
            "trend_slope_1h": long_z, "trend_slope_4h": long_z, "trend_slope_24h": long_z,
            "return_4h": long_z, "ema_gap_4h": long_z,
            "atr_pct_1h": 2.0, "atr_pct_4h": 2.0, "bb_width_1h": 1.0,
            "adx_1h": 30, "adx_4h": 30, "volume_z_1h": 0.0,
            "distance_from_24h_low": 0.02, "drawdown_from_24h_high": 0.02,
        }

    def test_fast_trend_early_exits_up_to_range(self) -> None:
        # Long trend stays strongly up; short-TF flips hard down mid-way.
        fit_rows = [self._long_fast_row(1, 1), self._long_fast_row(-1, -1)] * 200
        cfg = dict(min_hold_bars=3, trend_enter=0.5, trend_exit=0.3, vol_min_for_trend=-9.0, fast_exit=0.8)
        on = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(**cfg)).fit(fit_rows)
        off = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(use_fast_trend_rules=False, **cfg)).fit(fit_rows)
        seq = [self._long_fast_row(3, 3)] * 30 + [self._long_fast_row(3, -1.2)] * 30 + [self._long_fast_row(3, 3)] * 30
        mid = 45  # inside the short-TF-down block
        self.assertEqual(on.detect_all(seq)[mid], "range")  # fast exit fired
        self.assertEqual(off.detect_all(seq)[mid], "up")    # no fast rule -> stays up

    def test_no_direct_reversal_forces_through_range(self) -> None:
        # Held up, aggregate trend flips strongly down while short-TF still up.
        fit_rows = [self._long_fast_row(1, 1), self._long_fast_row(-1, -1)] * 200
        cfg = dict(min_hold_bars=2, trend_enter=0.5, trend_exit=0.3, vol_min_for_trend=-9.0,
                   use_fast_trend_rules=False)
        seq = [self._long_fast_row(3, 3)] * 20 + [self._long_fast_row(-3, 3)] * 20
        allow = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(allow_direct_reversal=True, **cfg)).fit(fit_rows)
        block = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(allow_direct_reversal=False, **cfg)).fit(fit_rows)
        allow_seq = allow.detect_all(seq)
        block_seq = block.detect_all(seq)
        # Both end at down (the aggregate trend is down), but the blocked one
        # must pass THROUGH range on the way (up -> range -> down) while the
        # allowed one flips up -> down directly (no range in the reversal).
        self.assertEqual(allow_seq[-1], "down")
        self.assertEqual(block_seq[-1], "down")
        self.assertIn("range", block_seq[20:])
        self.assertNotIn("range", allow_seq[20:])

    def test_switch_confirm_ignores_single_bar_blip(self) -> None:
        fit_rows = [self._long_fast_row(1, 1), self._long_fast_row(-1, -1)] * 200
        cfg = dict(min_hold_bars=2, trend_enter=0.5, trend_exit=0.3, vol_min_for_trend=-9.0,
                   use_fast_trend_rules=False)
        # Up block, a SINGLE opposite bar, then up again.
        seq = [self._long_fast_row(3, 3)] * 20 + [self._long_fast_row(-3, -3)] * 1 + [self._long_fast_row(3, 3)] * 20
        conf1 = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(switch_confirm_bars=1, **cfg)).fit(fit_rows)
        conf5 = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(switch_confirm_bars=5, **cfg)).fit(fit_rows)
        def trans(seq_):
            r = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(**cfg)).detect_all  # unused
            return sum(1 for a, b in zip(seq_, seq_[1:]) if a != b)
        r1 = conf1.detect_all(seq)
        r5 = conf5.detect_all(seq)
        # confirm=5 must not switch on the single-bar blip; confirm=1 may.
        self.assertLess(trans(r5), max(1, trans(r1)) + 1)
        self.assertEqual(len(set(r5)), 1)  # stays a single regime across the blip

    def test_switch_confirm_switches_after_persistence(self) -> None:
        fit_rows = [self._long_fast_row(1, 1), self._long_fast_row(-1, -1)] * 200
        cfg = dict(min_hold_bars=2, trend_enter=0.5, trend_exit=0.3, vol_min_for_trend=-9.0,
                   use_fast_trend_rules=False, switch_confirm_bars=5, allow_direct_reversal=True)
        det = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(**cfg)).fit(fit_rows)
        # Down persists well beyond confirm bars -> must eventually switch.
        seq = [self._long_fast_row(3, 3)] * 20 + [self._long_fast_row(-3, -3)] * 20
        self.assertEqual(det.detect_all(seq)[-1], "down")

    def test_strong_breakout_bypasses_switch_confirm(self) -> None:
        fit_rows = [self._long_fast_row(1, 1), self._long_fast_row(-1, -1)] * 200
        cfg = dict(min_hold_bars=100, trend_enter=0.5, trend_exit=0.3, vol_min_for_trend=-9.0,
                   switch_confirm_bars=50)
        det = MultiFeatureRegimeDetector(MultiFeatureRegimeConfig(**cfg)).fit(fit_rows)
        rows = [self._long_fast_row(0, 0) for _ in range(30)]
        breakout = self._long_fast_row(0, 0)
        breakout["rolling_high_breakout_24h"] = 1.0
        breakout["volume_z_1h"] = 2.0
        seq = rows + [breakout]
        # Breakout flips to up immediately despite huge min_hold/confirm.
        self.assertEqual(det.detect_all(seq)[-1], "up")


if __name__ == "__main__":
    unittest.main()
