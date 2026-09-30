from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.fixed_fade_meta import (
    apply_coverage_threshold,
    assert_fixed_side,
    dollar_bar_origins,
    eligibility_mask,
    fit_coverage_threshold,
    fixed_fade_labels,
    settlement_rate_vector,
)
from out import run_fixed_fade_meta_policy as runner


def _ohlc(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return close * 1.001, close * 0.999


def test_label_arithmetic_includes_signed_funding_for_short_and_long() -> None:
    short_close = np.r_[np.linspace(100.0, 115.0, 16), np.full(15, 115.0)]
    high, low = _ohlc(short_close)
    rates = np.zeros(len(short_close)); rates[30] = 0.001
    short = fixed_fade_labels(short_close, high, low, rates)
    assert short.side[15] == -1
    assert short.gross_bps[15][15] == pytest.approx(0.0)
    assert short.funding_bps[15][15] == pytest.approx(-10.0)
    assert short.net_bps[15][15] == pytest.approx(6.0)
    assert short.profitable[15] == 1

    long_close = np.r_[np.linspace(115.0, 100.0, 16), np.full(15, 100.0)]
    high, low = _ohlc(long_close)
    rates = np.zeros(len(long_close)); rates[30] = 0.001
    long = fixed_fade_labels(long_close, high, low, rates)
    assert long.side[15] == 1
    assert long.funding_bps[15][15] == pytest.approx(10.0)
    assert long.net_bps[15][15] == pytest.approx(-14.0)
    assert long.profitable[15] == 0


def test_fixed_side_assertion_rejects_any_learned_or_flipped_side() -> None:
    side = np.array([-1, 1, -1, 1], dtype=np.int8)
    prior = -side
    eligible = np.ones(4, dtype=bool)
    assert assert_fixed_side(side, prior, eligible) == pytest.approx(-1.0)
    assert assert_fixed_side(np.array([-1, -1]), np.array([1, 1]), np.ones(2, bool)) is None
    mutated = side.copy(); mutated[2] *= -1
    with pytest.raises(AssertionError, match="fixed side"):
        assert_fixed_side(mutated, prior, eligible)


def test_coverage_threshold_has_no_test_argument_or_test_dependence() -> None:
    stop_q = np.array([0.1, 0.2, 0.8, 0.9])
    threshold = fit_coverage_threshold(stop_q, 0.25)
    assert threshold == pytest.approx(np.quantile(stop_q, 0.75, method="linear"))
    assert np.array_equal(apply_coverage_threshold([threshold, 1.0], threshold), [False, True])
    assert np.array_equal(apply_coverage_threshold([0.7, 0.95], threshold), [False, True])


def test_primary_coverage_gate_rejects_m4_smoke_overshoot() -> None:
    rows = pd.DataFrame({
        "side": np.resize([-1, 1], 100),
        "prior_sign": np.resize([1, -1], 100),
        "z": np.resize([0, 1], 100),
        "q": np.linspace(0.1, 0.9, 100),
        "constant_q": np.full(100, 0.5),
        "m_bps": np.zeros(100),
        "constant_m_bps": np.zeros(100),
        "net_bps": np.zeros(100),
        "gross_bps": np.full(100, 4.0),
        "funding_bps": np.zeros(100),
        "h15_abs_move_bps": np.zeros(100),
        "barrier_symmetric_bps": np.zeros(100),
        "barrier_wide_bps": np.zeros(100),
        "pilot_fold": np.zeros(100, dtype=int),
        "open_time": pd.date_range("2026-01-01", periods=100, freq="15min", tz="UTC"),
        **{
            runner.coverage_name(coverage): np.arange(100) < (20 if coverage == runner.PRIMARY_COVERAGE else 5)
            for coverage in runner.COVERAGES
        },
    })
    assert runner.arm_report(rows)["primary_coverage_tracks_target"] is False


def test_dollar_bar_equality_closes_current_minute_and_carries_overshoot() -> None:
    complete_day = pd.date_range("2026-01-01", periods=1_440, freq="min", tz="UTC")
    partial_day = pd.date_range("2026-01-02", periods=3, freq="min", tz="UTC")
    next_day = pd.DatetimeIndex([pd.Timestamp("2026-01-03", tz="UTC")])
    times = complete_day.append(partial_day).append(next_day)
    volume = np.zeros(len(times)); volume[:2] = 10.0; volume[1_440:1_443] = [4.0, 6.0, 25.0]
    result = dollar_bar_origins(times, volume, prior_days=1, bars_per_day=2)
    assert np.isnan(result.threshold[:1_440]).all()
    assert result.threshold[1_440:1_443].tolist() == [10.0, 10.0, 10.0]
    assert np.isnan(result.threshold[-1])  # Partial Jan 2 cannot seed Jan 3.
    assert result.marked[1_440:1_443].tolist() == [False, True, True]
    assert result.crossings == 3
    assert result.collapsed_crossings == 1


def test_funding_at_entry_boundary_includes_t_plus_1_but_excludes_t() -> None:
    close = np.r_[np.linspace(100.0, 115.0, 16), np.full(15, 115.0)]
    high, low = _ohlc(close)
    times = pd.date_range("2026-01-01", periods=len(close), freq="min", tz="UTC")
    rates = settlement_rate_vector(
        times,
        [times[15] + pd.Timedelta(milliseconds=2), times[16] + pd.Timedelta(milliseconds=1)],
        [0.003, 0.001],
    )
    labels = fixed_fade_labels(close, high, low, rates)
    assert labels.side[15] == -1
    assert labels.funding_bps[15][15] == pytest.approx(-10.0)


def test_flat_prior_window_has_zero_side_and_no_eligible_label() -> None:
    close = np.full(31, 100.0)
    high, low = _ohlc(close)
    labels = fixed_fade_labels(close, high, low, np.zeros(len(close)))
    assert labels.side[15] == 0
    assert labels.profitable[15] == -1
    assert np.isnan(labels.net_bps[15][15])


def test_eligibility_mask_requires_features_non_tie_and_known_label() -> None:
    actual = eligibility_mask(
        [True, False, True, True],
        [1, 1, 0, -1],
        [1, 1, -1, -1],
    )
    assert actual.tolist() == [True, False, False, False]


def test_verify_refuses_a_changed_input_hash(tmp_path, monkeypatch) -> None:
    root = tmp_path / "run"
    root.mkdir()
    plan = tmp_path / "plan.md"
    changed = tmp_path / "input.txt"
    plan.write_text("frozen plan", encoding="utf-8")
    changed.write_text("changed", encoding="utf-8")
    runner.write(root / "prefit.json", {"evaluated_folds": [406], "abstained_folds": {}})
    runner.write(root / "manifest.json", {
        "source_sha256": {str(changed): "0" * 64},
        "input_parquet_sha256": {},
        "input_other_sha256": {},
        "plan_sha256": runner.sha256(plan),
        "evaluated_folds": [406],
    })
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "PLAN", plan)
    with pytest.raises(AssertionError, match="source_sha256 mismatch"):
        runner.execute(verify=True)


def test_named_fold_selection_preserves_exact_requested_folds() -> None:
    requested = (426, 466, 506, 546, 586)
    assert runner.select_named_folds(tuple(range(406, 606)), requested) == requested
    with pytest.raises(ValueError, match="not evaluable"):
        runner.select_named_folds(tuple(range(406, 606)), (426, 606))


def test_named_arm_subset_fits_only_m1(tmp_path, monkeypatch) -> None:
    calls = []
    data = SimpleNamespace(
        values=np.zeros((1, 1), dtype=np.float32),
        frame=pd.DataFrame({"open_time": pd.to_datetime(["2026-01-01"], utc=True)}),
    )
    monkeypatch.setattr(runner, "origin_indices", lambda *_: np.array([0]))
    monkeypatch.setattr(runner, "coverage_indices", lambda *_: np.array([0]))

    def fake_model(arm, fold, seed, data, train, stop, fit, root):
        calls.append((arm, fold, seed, fit, root))
        return object()

    monkeypatch.setattr(runner, "model", fake_model)
    monkeypatch.setattr(
        runner,
        "decoded_outputs",
        lambda fitted, values, indexes: np.array([[0.5, 0.0]]),
    )
    rows = runner.build_coverage_scores(("M1",), data, (426,), True, tmp_path)
    assert len(calls) == 3
    assert {call[0] for call in calls} == {"M1"}
    assert set(rows.arm) == {"M1"}


def test_coverage_launch_conditions_include_registered_boundaries() -> None:
    boundaries = {1: (2, 100), 2: (10, 100), 3: (4, 100), 4: (6, 100)}
    assert runner.coverage_launch_conditions(boundaries, True)["passed"] is True
    assert runner.coverage_launch_conditions({1: (4, 100)}, True)["passed"] is True
    assert runner.coverage_launch_conditions({1: (6, 100)}, True)["passed"] is True
    assert runner.coverage_launch_conditions({1: (3, 100)}, True)["passed"] is False
    assert runner.coverage_launch_conditions({1: (5, 100)}, False)["passed"] is False


def test_verify_refuses_a_changed_named_fold_list() -> None:
    manifest = {
        "selected_folds": [426, 466, 506, 546, 586],
        "selected_arms": ["M1"],
    }
    with pytest.raises(AssertionError, match="named fold list differs"):
        runner.verify_pilot_manifest(manifest, (426, 466, 506, 546, 585), ("M1",))
