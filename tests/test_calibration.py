"""Tests for calibration.py (reliability of the side models' probabilities)
and risk.breakeven_probability, the hurdle the reports are graded against.
"""
from __future__ import annotations

import math
import unittest

from btcusdt_quant import calibration, risk
from btcusdt_quant.calibration import (
    MIN_BIN_SAMPLES,
    brier_score,
    decision_band,
    expected_calibration_error,
    reliability_curve,
)


class BreakevenProbabilityTests(unittest.TestCase):
    def test_matches_the_barrier_economics_in_the_handoff(self) -> None:
        # The barrier that could not win: tp 0.30% / sl 0.15%, 0.08% round trip.
        # Nominal 2:1 reward:risk, but net 0.22 vs 0.23 -- 51.1% to break even.
        self.assertAlmostEqual(risk.breakeven_probability(0.003, 0.0015, 0.0008), 0.5111, places=4)
        # The barrier the pipeline retrained on: 1.00% / 0.50%. 38.7%.
        self.assertAlmostEqual(risk.breakeven_probability(0.010, 0.005, 0.0008), 0.3867, places=4)

    def test_is_the_zero_of_expected_edge(self) -> None:
        # The two must agree by construction: sizing enters exactly where the
        # break-even is cleared, and a drift between them would size losers.
        for tp, sl, cost in ((0.010, 0.005, 0.0008), (0.003, 0.0015, 0.0008), (0.02, 0.02, 0.0)):
            p = risk.breakeven_probability(tp, sl, cost)
            self.assertAlmostEqual(risk.expected_edge(p, tp, sl, cost), 0.0, places=12)

    def test_costless_symmetric_barrier_is_a_coin_flip(self) -> None:
        self.assertAlmostEqual(risk.breakeven_probability(0.01, 0.01, 0.0), 0.5)

    def test_tp_below_cost_has_no_breakeven(self) -> None:
        # No win rate makes this trade profitable, so there is no hurdle to
        # report -- NaN, not 1.0 (which would read as "needs a perfect model").
        self.assertTrue(math.isnan(risk.breakeven_probability(0.0005, 0.005, 0.0008)))


class ReliabilityCurveTests(unittest.TestCase):
    def test_perfectly_calibrated_model_has_zero_ece(self) -> None:
        # 200 bars at p=0.25 where the event happens exactly 25% of the time,
        # and 200 at p=0.75 happening 75% of the time.
        probabilities = [0.25] * 200 + [0.75] * 200
        outcomes = ([1] * 50 + [0] * 150) + ([1] * 150 + [0] * 50)
        report = reliability_curve(probabilities, outcomes)
        self.assertAlmostEqual(report.ece, 0.0, places=12)
        self.assertAlmostEqual(report.overall_gap, 0.0, places=12)

    def test_overconfident_model_is_caught(self) -> None:
        # The pathology from the 2025 run: the model says 0.52, it happens 17%.
        probabilities = [0.52] * 300
        outcomes = [1] * 51 + [0] * 249
        report = reliability_curve(probabilities, outcomes)
        self.assertAlmostEqual(report.observed_rate, 0.17)
        # Positive overall_gap = the model OVERSTATES the event.
        self.assertGreater(report.overall_gap, 0.34)
        self.assertAlmostEqual(report.ece, 0.35, places=2)

    def test_accuracy_blind_spot_is_visible_here(self) -> None:
        # A monotone squash toward 0.5 leaves the RANKING (and so the accuracy
        # and the AUC) untouched while destroying the probabilities. This is the
        # failure the whole module exists to catch, and the ECE must see it.
        honest = [0.05] * 100 + [0.95] * 100
        squashed = [0.45] * 100 + [0.55] * 100
        outcomes = ([0] * 95 + [1] * 5) + ([1] * 95 + [0] * 5)
        self.assertLess(reliability_curve(honest, outcomes).ece, 0.01)
        self.assertGreater(reliability_curve(squashed, outcomes).ece, 0.35)

    def test_bins_are_equal_width_not_equal_mass(self) -> None:
        # Probabilities squashed into one narrow band must land in ONE bin --
        # that concentration is the finding. Equal-mass bins would spread it
        # across the curve and hide it.
        report = reliability_curve([0.51, 0.52, 0.53, 0.54], [1, 0, 1, 0], bin_count=10)
        populated = [b for b in report.bins if b.count]
        self.assertEqual(len(populated), 1)
        self.assertEqual(populated[0].count, 4)
        self.assertAlmostEqual(populated[0].lower, 0.5)

    def test_probability_of_one_lands_in_the_last_bin(self) -> None:
        report = reliability_curve([1.0], [1], bin_count=10)
        self.assertEqual(report.bins[-1].count, 1)

    def test_empty_bins_report_nan_not_zero(self) -> None:
        report = reliability_curve([0.05] * 30, [0] * 30, bin_count=10)
        self.assertTrue(math.isnan(report.bins[5].observed_rate))
        self.assertTrue(math.isnan(report.bins[5].mean_predicted))

    def test_thin_bins_are_excluded_from_ece(self) -> None:
        # A 2-sample bin sitting on the diagonal must not flatter a model whose
        # populated bin is badly off.
        probabilities = [0.95] * 2 + [0.55] * MIN_BIN_SAMPLES
        outcomes = [1] * 2 + [0] * MIN_BIN_SAMPLES
        report = reliability_curve(probabilities, outcomes)
        self.assertAlmostEqual(report.ece, 0.55, places=2)

    def test_ece_is_nan_when_no_bin_is_measurable(self) -> None:
        # Not 0.0: no bin has enough samples to say anything, and a zero here
        # would read as perfect calibration.
        report = reliability_curve([0.5, 0.5], [1, 0])
        self.assertTrue(math.isnan(report.ece))

    def test_rejects_impossible_inputs(self) -> None:
        with self.assertRaises(ValueError):
            reliability_curve([0.5], [1, 0])          # length mismatch
        with self.assertRaises(ValueError):
            reliability_curve([1.5], [1])             # outside [0, 1]
        with self.assertRaises(ValueError):
            reliability_curve([float("nan")], [1])    # non-finite
        with self.assertRaises(ValueError):
            reliability_curve([0.5], [2])             # not a binary outcome
        with self.assertRaises(ValueError):
            reliability_curve([0.5], [1], bin_count=0)


class BrierScoreTests(unittest.TestCase):
    def test_known_value(self) -> None:
        self.assertAlmostEqual(brier_score([1.0, 0.0], [1, 0]), 0.0)
        self.assertAlmostEqual(brier_score([0.5, 0.5], [1, 0]), 0.25)

    def test_nan_on_empty_sample(self) -> None:
        self.assertTrue(math.isnan(brier_score([], [])))


class DecisionBandTests(unittest.TestCase):
    def test_grades_only_the_bars_above_the_threshold(self) -> None:
        # Below the cutoff the model is right; above it (where the money goes)
        # it is wrong. A pooled win rate would hide that; the band must not.
        probabilities = [0.2] * 50 + [0.6] * 50
        outcomes = [0] * 50 + ([1] * 15 + [0] * 35)
        band = decision_band(probabilities, outcomes, threshold=0.5, tp_pct=0.010, sl_pct=0.005,
                             round_trip_cost=0.0008)
        self.assertEqual(band.count, 50)
        self.assertAlmostEqual(band.share_of_bars, 0.5)
        self.assertAlmostEqual(band.observed_rate, 0.30)
        self.assertAlmostEqual(band.breakeven_rate, 0.3867, places=4)
        self.assertFalse(band.clears_breakeven)
        self.assertLess(band.margin, 0.0)

    def test_clears_breakeven_when_the_realized_rate_is_good_enough(self) -> None:
        band = decision_band([0.6] * 100, [1] * 45 + [0] * 55, threshold=0.5,
                             tp_pct=0.010, sl_pct=0.005, round_trip_cost=0.0008)
        self.assertAlmostEqual(band.observed_rate, 0.45)
        self.assertTrue(band.clears_breakeven)

    def test_threshold_above_every_prediction_enters_nothing(self) -> None:
        # The range-regime failure mode: a floor above the model's whole output
        # range means zero trades, which must read as "never enters", not as a
        # 0% win rate.
        band = decision_band([0.35] * 100, [1] * 40 + [0] * 60, threshold=0.45,
                             tp_pct=0.010, sl_pct=0.005)
        self.assertEqual(band.count, 0)
        self.assertTrue(math.isnan(band.observed_rate))
        self.assertFalse(band.clears_breakeven)

    def test_no_barrier_means_no_verdict(self) -> None:
        # Without a barrier there is no hurdle; inventing 0.5 would pass or fail
        # the model against a trade it never took.
        band = decision_band([0.6] * 50, [1] * 30 + [0] * 20, threshold=0.5)
        self.assertTrue(math.isnan(band.breakeven_rate))
        self.assertFalse(band.clears_breakeven)

    def test_reliability_curve_carries_the_band(self) -> None:
        report = reliability_curve([0.6] * 50, [1] * 20 + [0] * 30, threshold=0.5,
                                   tp_pct=0.010, sl_pct=0.005, round_trip_cost=0.0008)
        self.assertIsNotNone(report.decision)
        self.assertAlmostEqual(report.decision.observed_rate, 0.40)
        self.assertTrue(report.decision.clears_breakeven)

    def test_rejects_threshold_outside_probability_range(self) -> None:
        with self.assertRaises(ValueError):
            decision_band([0.5], [1], threshold=1.5)


class ReportSerializationTests(unittest.TestCase):
    def test_as_dict_is_json_safe_after_json_safe(self) -> None:
        import json

        from btcusdt_quant.backtest import json_safe

        # A report with undefined cells (empty bins, unmeasurable ECE) must not
        # write NaN literals into the artifact.
        report = reliability_curve([0.5, 0.5], [1, 0], threshold=0.9)
        text = json.dumps(json_safe(report.as_dict()))
        self.assertNotIn("NaN", text)
        payload = json.loads(text)
        self.assertIsNone(payload["ece"])
        self.assertIsNone(payload["decision_band"]["observed_rate"])
        self.assertEqual(payload["count"], 2)


if __name__ == "__main__":
    unittest.main()
