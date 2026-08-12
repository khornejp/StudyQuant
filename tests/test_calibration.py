"""Tests for calibration.py (reliability of the side models' probabilities)
and risk.breakeven_probability, the hurdle the reports are graded against.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from btcusdt_quant import calibration, governance, risk
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


class EnteredPopulationTests(unittest.TestCase):
    """The band must be measured on the bars the strategy can actually enter.

    verify_calibration gates its band stream by the direction policy and the
    range mean-reversion gate before handing it here; these pin the consequence
    of getting that population wrong, which is what the reviewer caught.
    """

    def test_gating_the_population_changes_the_verdict(self) -> None:
        # 100 bars over the threshold. The 50 the entry policy would BLOCK are
        # losers; the 50 it allows are winners. Scoring all 100 says the strategy
        # cannot pay its costs; scoring what it really enters says it can.
        blocked = ([0.6] * 50, [0] * 50)
        enterable = ([0.6] * 50, [1] * 25 + [0] * 25)
        all_bars = (blocked[0] + enterable[0], blocked[1] + enterable[1])

        ungated = decision_band(*all_bars, threshold=0.5, tp_pct=0.010, sl_pct=0.005,
                                round_trip_cost=0.0008)
        gated = decision_band(*enterable, threshold=0.5, tp_pct=0.010, sl_pct=0.005,
                              round_trip_cost=0.0008)

        self.assertAlmostEqual(ungated.observed_rate, 0.25)
        self.assertFalse(ungated.clears_breakeven)
        self.assertAlmostEqual(gated.observed_rate, 0.50)
        self.assertTrue(gated.clears_breakeven)
        self.assertEqual(gated.count, 50)

    def test_share_is_relative_to_the_population_given(self) -> None:
        # 20 enterable bars, 5 of them above the threshold: 25% of ENTERABLE, and
        # the band must not silently divide by some larger universe.
        band = decision_band([0.6] * 5 + [0.2] * 15, [1] * 5 + [0] * 15, threshold=0.5,
                             tp_pct=0.010, sl_pct=0.005)
        self.assertEqual(band.count, 5)
        self.assertAlmostEqual(band.share_of_bars, 0.25)

    def test_no_enterable_bars_is_not_a_zero_win_rate(self) -> None:
        # Every bar blocked by the entry gate: the band has nothing to say, and
        # must not report 0% (which reads as "enters and always loses").
        band = decision_band([], [], threshold=0.5, tp_pct=0.010, sl_pct=0.005)
        self.assertEqual(band.count, 0)
        self.assertTrue(math.isnan(band.observed_rate))
        self.assertFalse(band.clears_breakeven)


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


class ArtifactProvenanceTests(unittest.TestCase):
    def _git_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        input_path = root / "input.csv"
        input_path.write_text("timestamp,close\n1,100\n", encoding="utf-8")
        for args in (("init",), ("add", "input.csv"), ("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        return temporary, root, input_path

    def test_provenance_records_clean_tree_and_input_fingerprint(self) -> None:
        temporary, root, input_path = self._git_repo()
        with temporary:
            provenance, patch_text = governance.capture_provenance(
                resolved_config={"mode": "test"}, input_paths=[input_path], argv=["test"], repository_dir=root,
            )
            expected_hash = governance.sha256_file(input_path)
        self.assertEqual(provenance["state"], governance.PROVENANCE_RECORDED)
        self.assertEqual(provenance["source_revision"]["working_tree"], governance.PROVENANCE_CLEAN)
        self.assertIsNone(provenance["source_revision"]["diff_sha256"])
        self.assertIsNone(patch_text)
        self.assertEqual(provenance["inputs"][0]["sha256"], expected_hash)

    def test_provenance_records_dirty_tree_with_patch_digest(self) -> None:
        temporary, root, input_path = self._git_repo()
        with temporary:
            input_path.write_text("timestamp,close\n1,101\n", encoding="utf-8")
            provenance, patch_text = governance.capture_provenance(
                resolved_config={"mode": "test"}, input_paths=[input_path], repository_dir=root,
            )
        revision = provenance["source_revision"]
        self.assertEqual(revision["working_tree"], governance.PROVENANCE_DIRTY)
        self.assertIsInstance(revision["diff_sha256"], str)
        self.assertEqual(revision["diff_sha256"], governance.sha256_text(patch_text or ""))
        self.assertIn("git diff --binary HEAD", patch_text or "")

    def test_provenance_hashes_large_untracked_files_without_embedding_content(self) -> None:
        temporary, root, _ = self._git_repo()
        with temporary:
            large_file = root / "large.pdf"
            large_file.write_bytes(b"x" * (governance.UNTRACKED_CONTENT_MAX_BYTES + 1))
            expected_hash = governance.sha256_file(large_file)
            provenance, patch_text = governance.capture_provenance(
                resolved_config={"mode": "test"}, repository_dir=root,
            )
        self.assertEqual(provenance["source_revision"]["working_tree"], governance.PROVENANCE_DIRTY)
        self.assertIn("hash-only; content omitted", patch_text or "")
        self.assertIn(expected_hash, patch_text or "")
        self.assertNotIn("eHh4eHh4eHh4", patch_text or "")

    def test_provenance_marks_no_git_and_fingerprint_failure_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing.csv"
            with patch("btcusdt_quant.governance.subprocess.run", side_effect=FileNotFoundError):
                provenance, _ = governance.capture_provenance(
                    resolved_config={"mode": "test"}, input_paths=[missing], repository_dir=root,
                )
            not_repo, _ = governance.capture_provenance(resolved_config={"mode": "test"}, repository_dir=root)
        self.assertEqual(provenance["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["source_revision"]["reason"], "git_binary_unavailable")
        self.assertEqual(provenance["source_revision"]["git_commit"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["inputs"][0]["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["inputs"][0]["sha256"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(not_repo["source_revision"]["reason"], "not_a_git_repository")
        self.assertEqual(not_repo["source_revision"]["working_tree"], governance.PROVENANCE_UNKNOWN)

    def test_provenance_preserves_invocation_when_other_components_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {"mode": "test", "threshold": 0.75}
            with patch("btcusdt_quant.governance._git", side_effect=MemoryError("out of memory")):
                provenance, _ = governance.capture_provenance(
                    resolved_config=config, input_paths=[root / "missing.csv"], argv=["test"], repository_dir=root,
                )
        self.assertEqual(provenance["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["source_revision"]["reason"], "capture_failed:MemoryError:out of memory")
        self.assertEqual(provenance["invocation"]["state"], governance.PROVENANCE_RECORDED)
        self.assertEqual(provenance["invocation"]["resolved_config"], config)
        self.assertEqual(provenance["input_fingerprints"]["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["input_fingerprints"]["reason"], "fingerprint_failed:FileNotFoundError")

    def test_provenance_capture_failure_writes_unknown_artifact_and_preserves_interrupts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            writer = governance.ArtifactWriter(Path(temporary))
            with patch("btcusdt_quant.governance._git", side_effect=MemoryError("out of memory")):
                provenance = writer.write_provenance(resolved_config={"mode": "test"})
            written = json.loads((Path(temporary) / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["state"], governance.PROVENANCE_UNKNOWN)
            self.assertEqual(written["state"], governance.PROVENANCE_UNKNOWN)
            self.assertEqual(
                written["source_revision"]["reason"],
                "capture_failed:MemoryError:out of memory",
            )
            with patch("btcusdt_quant.governance._git", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    writer.write_provenance(resolved_config={"mode": "test"})
            with patch("btcusdt_quant.governance._git", side_effect=SystemExit):
                with self.assertRaises(SystemExit):
                    writer.write_provenance(resolved_config={"mode": "test"})

    def test_provenance_fallback_survives_a_second_failure_in_config_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            writer = governance.ArtifactWriter(Path(temporary))
            with patch("btcusdt_quant.governance._provenance_json_value", side_effect=MemoryError("serializer exhausted")):
                provenance = writer.write_provenance(resolved_config={"mode": "test"}, argv=["test"])
            self.assertEqual(provenance["state"], governance.PROVENANCE_UNKNOWN)
            self.assertEqual(
                provenance["invocation"]["reason"],
                "capture_failed:MemoryError:serializer exhausted",
            )
            self.assertEqual(provenance["source_revision"]["state"], governance.PROVENANCE_RECORDED)
            written = json.loads((Path(temporary) / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(written["state"], governance.PROVENANCE_UNKNOWN)

    def test_provenance_expands_model_bundle_to_per_file_fingerprints(self) -> None:
        temporary, root, _ = self._git_repo()
        with temporary:
            bundle = root / "model_bundle"
            bundle.mkdir()
            model = bundle / "model.json"
            metadata = bundle / "metadata.json"
            model.write_text('{"model":"a"}', encoding="utf-8")
            metadata.write_text('{"threshold":0.5}', encoding="utf-8")
            expected = {
                str(model): governance.sha256_file(model),
                str(metadata): governance.sha256_file(metadata),
            }
            provenance, _ = governance.capture_provenance(
                resolved_config={"mode": "test"}, input_paths=[bundle], repository_dir=root,
            )
        recorded = {entry["path"]: entry["sha256"] for entry in provenance["inputs"]}
        self.assertEqual(recorded, expected)

    def test_backtest_captures_before_decision_preparation(self) -> None:
        from btcusdt_quant import backtest

        order: list[str] = []

        def capture(**_kwargs: object) -> tuple[dict[str, object], None]:
            order.append("capture")
            return {"state": governance.PROVENANCE_RECORDED, "inputs": []}, None

        def prepare(*_args: object) -> list[float | None]:
            order.append("decision_preparation")
            raise RuntimeError("stop after ordering probe")

        with patch.object(backtest.governance, "capture_provenance", side_effect=capture), \
             patch.object(backtest, "_prepare_trend_sma", side_effect=prepare):
            with self.assertRaisesRegex(RuntimeError, "stop after ordering probe"):
                backtest.run_backtest([], trend_filter_sma_bars=1)
        self.assertEqual(order, ["capture", "decision_preparation"])

    def test_file_changed_while_fingerprinted_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.csv"
            path.write_text("before", encoding="utf-8")

            def change_during_hash(target: Path) -> str:
                target.write_text("after-and-longer", encoding="utf-8")
                return "not-a-valid-snapshot"

            with patch("btcusdt_quant.governance.sha256_file", side_effect=change_during_hash):
                entry = governance._fingerprint_input(path)
        self.assertEqual(entry["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(entry["reason"], "fingerprint_failed:file_changed_during_capture")

    def test_dirty_git_evidence_change_during_capture_is_unknown(self) -> None:
        temporary, root, _ = self._git_repo()
        with temporary:
            diff_calls = 0

            def git_side_effect(_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
                nonlocal diff_calls
                if args[:2] == ("rev-parse", "HEAD"):
                    return subprocess.CompletedProcess([], 0, "abc123\n", "")
                if args[:2] == ("status", "--porcelain=v1"):
                    return subprocess.CompletedProcess([], 0, " M tracked.py\n", "")
                if args[:2] == ("diff", "--binary"):
                    diff_calls += 1
                    return subprocess.CompletedProcess([], 0, "old patch\n" if diff_calls == 1 else "new patch\n", "")
                if args[:2] == ("ls-files", "--others"):
                    return subprocess.CompletedProcess([], 0, "", "")
                raise AssertionError(args)

            with patch("btcusdt_quant.governance._git", side_effect=git_side_effect):
                provenance, patch_text = governance.capture_provenance(
                    resolved_config={"mode": "test"}, repository_dir=root,
                )
        self.assertEqual(provenance["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(provenance["source_revision"]["reason"], "working_tree_changed_during_capture")
        self.assertIsNone(patch_text)

    def test_runtime_capture_records_imported_numeric_library_versions(self) -> None:
        import sys

        with patch.dict(sys.modules, {"numpy": object()}), \
             patch("btcusdt_quant.governance.importlib.metadata.version", return_value="1.26.4"):
            runtime = governance._capture_runtime()
        self.assertEqual(runtime["state"], governance.PROVENANCE_RECORDED)
        self.assertEqual(runtime["packages"]["numpy"], "1.26.4")

    def test_training_external_sources_without_paths_downgrades_provenance(self) -> None:
        from btcusdt_quant import training

        captured: dict[str, object] = {"state": governance.PROVENANCE_RECORDED}
        with patch.object(training.governance, "capture_provenance", return_value=(captured, None)), \
             patch.object(training.dataset, "build_dataset", side_effect=RuntimeError("stop after provenance")):
            with self.assertRaisesRegex(RuntimeError, "stop after provenance"):
                training.run_training(Path("candles.csv"), Path("out"), external_sources={"metrics": {}})
        self.assertEqual(captured["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(captured["input_fingerprints"]["reason"], "external_sources_not_fingerprinted")

    def test_training_external_source_paths_are_fingerprinted(self) -> None:
        from btcusdt_quant import training

        captured: dict[str, object] = {"state": governance.PROVENANCE_RECORDED}
        external = Path("external.zip")
        with patch.object(training.governance, "capture_provenance", return_value=(captured, None)) as capture, \
             patch.object(training.dataset, "build_dataset", side_effect=RuntimeError("stop after provenance")):
            with self.assertRaisesRegex(RuntimeError, "stop after provenance"):
                training.run_training(Path("candles.csv"), Path("out"), external_sources={"metrics": {}}, external_source_paths=[external])
        self.assertIn(external, capture.call_args.kwargs["input_paths"])
        self.assertEqual(captured["state"], governance.PROVENANCE_RECORDED)

    def test_backtest_dirty_patch_is_persisted_or_downgraded(self) -> None:
        from btcusdt_quant import cli
        from btcusdt_quant.backtest import BacktestResult

        with tempfile.TemporaryDirectory() as temporary:
            result = BacktestResult(
                provenance={"state": governance.PROVENANCE_RECORDED, "source_revision": {"state": governance.PROVENANCE_RECORDED}},
                provenance_patch="reconstructible patch\n",
            )
            cli.persist_backtest_provenance_patch(Path(temporary), result)
            self.assertEqual((Path(temporary) / "provenance" / "git_diff.patch").read_text(encoding="utf-8"), "reconstructible patch\n")
        result = BacktestResult(
            provenance={"state": governance.PROVENANCE_RECORDED, "source_revision": {"state": governance.PROVENANCE_RECORDED}},
            provenance_patch="patch",
        )
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            cli.persist_backtest_provenance_patch(Path("unwritable"), result)
        self.assertEqual(result.provenance["state"], governance.PROVENANCE_UNKNOWN)
        self.assertEqual(result.provenance["source_revision"]["diff_sha256"], governance.PROVENANCE_UNKNOWN)

    def test_backtest_early_capture_records_cache_path_but_fingerprints_only_hit_artifact(self) -> None:
        from btcusdt_quant import cli, dataset, governance

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            premium = root / "premium"
            premium.mkdir()
            cache = root / "cache"
            cache.mkdir()
            args = SimpleNamespace(
                model_artifact=None, short_model_artifact=None, user_regime_file=None,
                regime_classifier_dir=None, metrics_dir=None, funding_dir=None,
                premium_index_dir=str(premium), feature_cache=str(cache),
            )
            input_path = root / "candles.csv"
            input_path.write_text("timestamp,close\n", encoding="utf-8")
            key = cli._feature_cache_key(input_path, [], None, None, None, str(premium))
            artifact = cache / key / dataset.DATASET_CACHE_FEATURE_ROWS_FILE
            artifact.parent.mkdir()
            artifact.write_text("cached rows", encoding="utf-8")
            unrelated = cache / "another-run" / dataset.DATASET_CACHE_FEATURE_ROWS_FILE
            unrelated.parent.mkdir()
            unrelated.write_text("unrelated cached rows", encoding="utf-8")
            paths = cli.backtest_provenance_input_paths(args, input_path, [])
            provenance, _ = governance.capture_provenance(
                resolved_config={"command": "backtest"}, input_paths=paths,
                repository_dir=Path.cwd(),
            )
            with patch("btcusdt_quant.governance.sha256_file", side_effect=OSError("unreadable")):
                unreadable_provenance, _ = governance.capture_provenance(
                    resolved_config={"command": "backtest"}, input_paths=paths,
                    repository_dir=Path.cwd(),
                )
        self.assertIn(premium, paths)
        self.assertNotIn(cache, paths)
        self.assertIn(artifact, paths)
        self.assertNotIn(unrelated, paths)
        self.assertEqual(cli.backtest_provenance_feature_cache_record(args), {"path": str(cache)})
        fingerprinted_paths = {item["path"] for item in provenance["inputs"]}
        self.assertIn(str(artifact), fingerprinted_paths)
        self.assertNotIn(str(unrelated), fingerprinted_paths)
        unreadable_artifact = next(item for item in unreadable_provenance["inputs"] if item["path"] == str(artifact))
        self.assertEqual(unreadable_artifact["state"], governance.PROVENANCE_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
